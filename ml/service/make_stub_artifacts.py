"""Create small fake artefacts for tests. NOT a trained model: synthetic data only.

    python -m service.make_stub_artifacts <output_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression

from .features import BUILDABLE_FEATURES

STUB_CARPARKS = ["ACB", "BM29", "HE12", "TPM1"]
STATS_CARPARKS = ["ACB", "BM29", "HE12"]  # TPM1 deliberately has no carpark_stats rows
FEATURE_NAMES = list(BUILDABLE_FEATURES)
CARD = {
    "version": "stub-0.0.1", "free_threshold": 0.5, "trained_at": "2026-10-01T00:00:00+00:00",
    "confidence_bands": {"high": 0.8, "medium": 0.5},
    "feature_names": FEATURE_NAMES,
}


def make_stub_artifacts(directory: str | Path, seed: int = 0) -> Path:
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    n = 600
    total = rng.integers(50, 400, n).astype(float)
    latest = np.floor(total * rng.random(n)) * (rng.random(n) > 0.2)

    def lag(scale, miss):
        return np.where(rng.random(n) > miss, latest + rng.integers(-scale, scale + 1, n), np.nan)

    X = pd.DataFrame({
        "current_available": latest, "current_total_lots": total, "current_free_ratio": latest / total,
        "current_age_seconds": rng.integers(0, 900, n).astype(float),
        "available_lag_15min": lag(3, 0.1), "available_lag_30min": lag(6, 0.2),
        "available_lag_60min": lag(10, 0.3), "horizon_minutes": rng.random(n) * 90,
        "arrival_weekday": rng.integers(1, 8, n).astype(float),
        "arrival_slot_15min": rng.integers(0, 96, n).astype(float),
        "carpark_free_share": np.where(rng.random(n) > 0.1, rng.random(n), np.nan),
        "carpark_slot_free_share": np.where(rng.random(n) > 0.1, rng.random(n), np.nan),
    })
    X["delta_15min"] = latest - X["available_lag_15min"]
    X["delta_60min"] = latest - X["available_lag_60min"]
    X["arrival_is_weekend"] = (X["arrival_weekday"] >= 6).astype(float)
    X["arrival_is_public_holiday"] = (rng.random(n) < 0.05).astype(float)
    X = X[FEATURE_NAMES]
    y = (rng.random(n) < 1 / (1 + np.exp(-(latest - 5) / 8))).astype(int)
    model = HistGradientBoostingClassifier(max_iter=30, random_state=seed).fit(X, y)
    raw = model.predict_proba(X)[:, 1]
    calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(raw, y)
    joblib.dump({"model": model, "calibrator": calibrator, "feature_names": FEATURE_NAMES},
                d / "short_horizon.joblib")

    rows = []
    for k, cp in enumerate(STUB_CARPARKS):
        for dt in ("weekday", "saturday", "sunday_ph"):
            for slot in range(96):
                if cp == "TPM1" and dt == "saturday":
                    continue  # deliberate hole: exercises insufficient_history
                p = float(np.clip(0.5 + 0.4 * np.sin((slot + 12 * k) / 96 * 2 * np.pi), 0, 1))
                rows.append((cp, dt, slot, p, 20 + slot))
    pd.DataFrame(rows, columns=["carpark_id", "day_type", "slot_15min", "p_free", "n_samples"]
                 ).to_parquet(d / "profile.parquet", index=False)
    stats_rows = []
    for k, cp in enumerate(STATS_CARPARKS):
        share = 0.6 + 0.1 * k
        stats_rows.append((cp, -1, share, np.nan))
        stats_rows += [(cp, slot, share, float(np.clip(share + 0.3 * np.sin(slot / 96 * 2 * np.pi), 0, 1)))
                       for slot in range(96)]
    pd.DataFrame(stats_rows, columns=["carpark_id", "slot_15min", "carpark_free_share",
                                      "carpark_slot_free_share"]).to_parquet(d / "carpark_stats.parquet", index=False)
    (d / "model_card.json").write_text(json.dumps(CARD, indent=2))
    return d


if __name__ == "__main__":
    out = make_stub_artifacts(sys.argv[1] if len(sys.argv) > 1 else "stub_artifacts")
    print(f"stub artefacts written to {out}")
