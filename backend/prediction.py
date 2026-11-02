"""Prediction contracts, validation and prospective forecast recording."""
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
from math import isfinite
from pathlib import Path
from threading import Lock
from typing import Protocol

_audit_lock=Lock()


@dataclass(frozen=True)
class PredictionRequest:
    """Ask for one carpark's availability at the driver's arrival time."""
    agency: str
    carpark_id: str
    issued_at: datetime
    arrival_at: datetime


@dataclass(frozen=True)
class Prediction:
    """Forecast or reasoned non-forecast. p_free is the chance of a free lot."""
    status: str
    agency: str
    carpark_id: str
    issued_at: datetime
    arrival_at: datetime
    available_lots: float | None = None
    confidence: str | None = None
    model_version: str | None = None
    history_cutoff: datetime | None = None
    sample_count: int | None = None
    p_free: float | None = None
    mode: str | None = None
    fallback_reason: str | None = None


class AvailabilityPredictor(Protocol):
    """Any forecaster the recommender can call; lets tests swap in stubs."""
    ready: bool
    def predict(self, request: PredictionRequest) -> Prediction: ...


class PendingPredictor:
    """No fake forecasts or confidence while the model is being trained."""
    ready = False

    def predict(self, request: PredictionRequest) -> Prediction:
        return Prediction('prediction_pending', request.agency, request.carpark_id,
                          request.issued_at, request.arrival_at)


def valid_prediction(value: Prediction, request: PredictionRequest) -> bool:
    """Check identity, time and value contract; this does not validate accuracy."""
    if not isinstance(value, Prediction) or value.status != 'ok':
        return False
    try:
        if value.p_free is not None:
            # The shipped classifier predicts P(at least one free lot), not a count.
            # Keep the service's actual issue time; do not relabel it as request time.
            return (value.agency == request.agency and value.carpark_id == request.carpark_id
                    and value.arrival_at == request.arrival_at
                    and request.issued_at <= value.issued_at <= datetime.now(timezone.utc)
                    and value.issued_at < value.arrival_at
                    and value.available_lots is None
                    and type(value.p_free) in (int, float) and isfinite(value.p_free)
                    and 0 <= value.p_free <= 1
                    and value.confidence in {'high', 'medium', 'low'}
                    and isinstance(value.model_version, str) and bool(value.model_version.strip())
                    and value.mode == 'short'
                    and isinstance(value.history_cutoff, datetime)
                    and value.history_cutoff.utcoffset() is not None
                    and value.history_cutoff <= value.issued_at
                    and value.issued_at-value.history_cutoff <= timedelta(minutes=15))
        return (value.agency == request.agency and value.carpark_id == request.carpark_id
                and value.arrival_at == request.arrival_at and value.issued_at == request.issued_at
                and isinstance(value.available_lots, (int, float)) and not isinstance(value.available_lots, bool)
                and isfinite(value.available_lots) and value.available_lots >= 0
                and value.confidence in {'high','medium','low'}
                and isinstance(value.model_version, str) and bool(value.model_version.strip())
                and isinstance(value.history_cutoff, datetime) and value.history_cutoff.utcoffset() is not None
                and value.history_cutoff <= request.issued_at <= request.arrival_at
                and request.issued_at-value.history_cutoff <= timedelta(minutes=15)
                and type(value.sample_count) is int and value.sample_count > 0)
    except (TypeError, ValueError, OverflowError):
        return False


def record_forecast(prediction: Prediction, baseline: dict | None,
                    path: Path | None = None) -> None:
    """Save valid issued forecasts before outcomes; no driver origin/destination.

    The local single-process prototype appends JSON lines. A deployed service
    will need durable shared storage; this file is not a trained model dataset.
    """
    path=path or Path(__file__).with_name('data')/'forecasts'/'issued.jsonl'
    recorded=datetime.now(timezone.utc)
    if recorded >= prediction.arrival_at:
        raise ValueError('Forecast target has already passed')
    event={**asdict(prediction), 'recorded_at':recorded,
           'forecast_id':f'{prediction.agency}/{prediction.carpark_id}/{prediction.issued_at.isoformat()}',
           'baseline':baseline}
    line=json.dumps(event,default=lambda x:x.isoformat(),allow_nan=False)+'\n'
    with _audit_lock:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('a',encoding='utf-8') as stream:
            stream.write(line)
