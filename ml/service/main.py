"""FastAPI app: GET /health, POST /predict. Run from ml/: uvicorn service.main:app"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from .artifacts import Artifacts, ArtifactError, FeatureMismatchError, load_artifacts
from .engine import Engine
from .live import LiveFeed

log = logging.getLogger(__name__)
_pkg_log = logging.getLogger(__package__ or "service")
if not _pkg_log.handlers:  # uvicorn configures only its own loggers; make this package's INFO lines visible
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    _pkg_log.addHandler(_handler)
    _pkg_log.setLevel(logging.INFO)
DEFAULT_DIR = Path(__file__).resolve().parents[1] / "models"
MAX_CARPARKS = 200
POLL_SECONDS = 60


class PredictRequest(BaseModel):
    carpark_ids: list[str] = Field(min_length=1, max_length=MAX_CARPARKS)
    arrival_at: datetime

    @field_validator("arrival_at")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("arrival_at must be timezone-aware")
        return v


class CurrentRequest(BaseModel):
    carpark_ids: list[str] = Field(min_length=1, max_length=MAX_CARPARKS)


class PredictResult(BaseModel):
    carpark_id: str
    issue_at: datetime
    arrival_at: datetime
    horizon_minutes: float
    mode: str | None
    p_free: float | None = Field(ge=0, le=1)
    free: bool | None
    confidence: str | None
    current_available: int | None
    current_observed_at: datetime | None
    current_reading_stale: bool | None
    model_version: str
    status: str
    fallback_reason: str | None


def create_app(artifact_dir: str | Path | None = None, feed: LiveFeed | None = None,
               poll_seconds: float = POLL_SECONDS) -> FastAPI:
    """Startup raises FeatureMismatchError if the model needs a feature this service cannot build."""
    directory = Path(artifact_dir or os.environ.get("PARKCHOICE_ARTIFACT_DIR") or DEFAULT_DIR)
    state: dict = {"art": None, "engine": None, "error": None}
    try:
        art: Artifacts = load_artifacts(directory)
        state.update(art=art, engine=Engine(art, feed or LiveFeed()))
    except FeatureMismatchError:
        raise
    except ArtifactError as exc:
        state["error"] = str(exc)
        log.error("artefacts not loaded: %s", exc)

    async def poll_forever(live: LiveFeed):
        await asyncio.to_thread(live.warm_up)  # failed warm-up calls are logged inside
        while True:
            try:
                readings = await asyncio.to_thread(live.refresh)
                log.info("background poll: %d carparks fetched; next in %ss", len(readings), poll_seconds)
            except Exception as exc:
                log.warning("background poll failed: %s", exc)
            await asyncio.sleep(poll_seconds)

    @asynccontextmanager
    async def lifespan(_app):
        task = asyncio.create_task(poll_forever(state["engine"].feed)) if state["engine"] else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    app = FastAPI(title="ParkChoiceSG availability forecast", lifespan=lifespan)

    @app.get("/health")
    def health():
        art = state["art"]
        return {"artifacts_loaded": art is not None, "model_version": art.version if art else None,
                "trained_at": art.trained_at if art else None, "error": state["error"]}

    @app.post("/predict", response_model=list[PredictResult])
    def predict(req: PredictRequest):
        engine: Engine | None = state["engine"]
        if engine is None:
            raise HTTPException(503, f"model artefacts not loaded: {state['error']}")
        if req.arrival_at < engine.feed.clock():
            raise HTTPException(422, "arrival_at is in the past")
        return engine.predict(req.carpark_ids, req.arrival_at)

    @app.post('/current')
    def current(req: CurrentRequest):
        """Share the same cached source readings used by the classifier."""
        engine = state['engine']
        if engine is None:
            raise HTTPException(503,'Current availability service is unavailable')
        try:
            readings = engine.feed.current()
        except Exception:
            raise HTTPException(503,'HDB feed is unavailable') from None
        now = engine.feed.clock()
        results=[]
        for cid in req.carpark_ids:
            reading=readings.get(cid)
            if reading is None: continue
            age=now-reading.observed_at
            fresh=timedelta(0)<=age<=timedelta(minutes=15)
            results.append({'carpark_id':cid,'available_lots':reading.lots_available,
                'total_lots':reading.total_lots,'timestamp':reading.observed_at,
                'status':'fresh_source_update' if fresh else 'stale',
                'timestamp_kind':'source_update','feed':'hdb_live_service'})
        return results

    return app


app = create_app()
