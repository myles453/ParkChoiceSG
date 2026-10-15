"""Load and validate the model artefacts shared with the training agent."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd

from .features import BUILDABLE_FEATURES

DAY_TYPES = {"weekday", "saturday", "sunday_ph"}


class ArtifactError(Exception):
    pass


class FeatureMismatchError(ArtifactError):
    """The model needs features this service cannot build. Fatal at startup."""


@dataclass
class Artifacts:
    model: object
    calibrator: object
    feature_names: list[str]
    profile: dict[tuple[str, str, int], tuple[float, int]]
    profile_carparks: set[str]
    carpark_stats: dict[tuple[str, int], dict[str, float]]
    version: str
    free_threshold: float
    high: float
    medium: float
    trained_at: str | None

    def confidence(self, p: float) -> str:
        """High/Medium/Low from the lower bounds on p_free in model_card.json."""
        if p >= self.high:
            return "High"
        return "Medium" if p >= self.medium else "Low"


def _parse_bands(raw) -> tuple[float, float]:
    """Only {"high": x, "medium": y}: lower bounds on p_free, 0 <= y <= x <= 1."""
    if not isinstance(raw, dict) or set(raw) != {"high", "medium"}:
        raise ArtifactError('confidence_bands must be exactly {"high": x, "medium": y}')
    for k, v in raw.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ArtifactError(f"confidence_bands.{k} must be a number, got {v!r}")
    high, medium = float(raw["high"]), float(raw["medium"])
    if not 0.0 <= medium <= high <= 1.0:
        raise ArtifactError("confidence_bands needs 0 <= medium <= high <= 1")
    return high, medium


def load_artifacts(directory: str | Path) -> Artifacts:
    d = Path(directory)
    try:
        bundle = joblib.load(d / "short_horizon.joblib")
        card = json.loads((d / "model_card.json").read_text())
        prof = pd.read_parquet(d / "profile.parquet")
        stats = pd.read_parquet(d / "carpark_stats.parquet")
    except Exception as exc:  # missing/corrupt file
        raise ArtifactError(f"cannot read artefacts in {d}: {exc}") from exc

    for key in ("model", "calibrator", "feature_names"):
        if key not in bundle:
            raise ArtifactError(f"short_horizon.joblib lacks '{key}'")
    if not hasattr(bundle["model"], "predict_proba") or not hasattr(bundle["calibrator"], "predict"):
        raise ArtifactError("model needs predict_proba and calibrator needs predict")
    names = list(bundle["feature_names"])
    for key in ("version", "free_threshold", "confidence_bands"):
        if key not in card:
            raise ArtifactError(f"model_card.json lacks '{key}'")
    if "feature_names" in card and list(card["feature_names"]) != names:
        raise ArtifactError("feature_names differ between model_card.json and short_horizon.joblib")
    missing_features = [n for n in names if n not in BUILDABLE_FEATURES]
    if missing_features:
        raise FeatureMismatchError(
            f"service cannot build these model features: {missing_features}; it can build {BUILDABLE_FEATURES}")
    thr = float(card["free_threshold"])
    if not 0.0 <= thr <= 1.0:
        raise ArtifactError("free_threshold must be within [0, 1]")
    high, medium = _parse_bands(card["confidence_bands"])

    missing = {"carpark_id", "day_type", "slot_15min", "p_free", "n_samples"} - set(prof.columns)
    if missing:
        raise ArtifactError(f"profile.parquet lacks columns {sorted(missing)}")
    if not set(prof["day_type"].unique()) <= DAY_TYPES:
        raise ArtifactError("profile.parquet has unknown day_type values")
    index: dict = {}
    for cp, dt, slot, p, n in zip(prof["carpark_id"], prof["day_type"], prof["slot_15min"],
                                  prof["p_free"], prof["n_samples"]):
        if p is None or not math.isfinite(float(p)) or not 0.0 <= float(p) <= 1.0:
            continue  # unusable cell: treated as missing, never filled
        index[(str(cp), str(dt), int(slot))] = (float(p), int(n))

    missing = {"carpark_id", "slot_15min", "carpark_free_share", "carpark_slot_free_share"} - set(stats.columns)
    if missing:
        raise ArtifactError(f"carpark_stats.parquet lacks columns {sorted(missing)}")
    cstats: dict = {}
    for cp, slot, fs, ss in zip(stats["carpark_id"], stats["slot_15min"], stats["carpark_free_share"],
                                stats["carpark_slot_free_share"]):
        cstats[(str(cp), int(slot))] = {"carpark_free_share": float(fs), "carpark_slot_free_share": float(ss)}

    return Artifacts(
        model=bundle["model"], calibrator=bundle["calibrator"], feature_names=names,
        profile=index, profile_carparks={k[0] for k in index}, carpark_stats=cstats,
        version=str(card["version"]), free_threshold=thr, high=high, medium=medium,
        trained_at=card.get("trained_at"),
    )
