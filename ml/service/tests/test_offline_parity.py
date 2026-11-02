"""Offline parity: the service's p_free == data/test_predictions.parquet, on real test rows.

200 seeded test-split rows (100 with current_free_ratio < 0.10, 50 with a missing lag). For each,
the carpark's readings known at decision time (first_seen_at and observed_at <= decision_at) go
through Engine.predict (feature building, carpark_stats join, model, calibrator) with the real
artefacts in ml/models. Uses real data, so it fails (not skips) when the files are missing.
"""
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from service.artifacts import load_artifacts
from service.engine import Engine
from service.live import Reading

ML = Path(__file__).resolve().parents[2]
TOLERANCE = 1e-6
LAGS = ["available_lag_15min", "available_lag_30min", "available_lag_60min"]
COLS = ["carpark_id", "decision_at", "arrival_at", "horizon_minutes", "current_free_ratio", *LAGS]


class ReplayFeed:
    """Stands in for LiveFeed: serves the readings known at one decision time."""

    def __init__(self):
        self.now: datetime | None = None
        self.readings: dict[str, list[tuple[datetime, int, int]]] = {}

    def clock(self):
        return self.now

    def current(self):
        out = {}
        for cid, rs in self.readings.items():
            at, avail, total = max(rs)
            out[cid] = Reading(at, avail, total)
        return out

    def history(self, cid):
        return sorted((at, avail) for at, avail, _ in self.readings.get(cid, []))


def sample_rows(pairs: pd.DataFrame) -> pd.DataFrame:
    """25 rows with a missing lag + 75 with all lags, in each of the low and not-low groups."""
    missing = pairs[LAGS].isna().any(axis=1)
    low = pairs["current_free_ratio"] < 0.10
    groups = [(low, missing, 25), (low, ~missing, 75), (~low, missing, 25), (~low, ~missing, 75)]
    return pd.concat([pairs[g & m].sample(n, random_state=0) for g, m, n in groups], ignore_index=True)


@pytest.fixture(scope="module")
def parity_rows():
    for f in ("data/pairs.parquet", "data/observations.parquet", "data/test_predictions.parquet",
              "models/model_card.json"):
        if not (ML / f).exists():
            pytest.fail(f"ml/{f} is missing")
    pairs = pd.read_parquet(ML / "data/pairs.parquet", filters=[("split", "==", "test")], columns=COLS)
    rows = sample_rows(pairs)
    del pairs
    preds = pd.read_parquet(ML / "data/test_predictions.parquet")
    rows = rows.merge(preds, on=["carpark_id", "decision_at", "horizon_minutes"], how="left", validate="1:1")
    return rows


def test_service_p_free_matches_test_predictions(parity_rows):
    rows = parity_rows
    assert len(rows) == 200
    assert (rows["current_free_ratio"] < 0.10).sum() == 100
    assert rows[LAGS].isna().any(axis=1).sum() >= 40
    assert rows["p_free"].notna().all(), "some sampled rows are absent from test_predictions.parquet"

    obs = pd.read_parquet(ML / "data/observations.parquet",
                          filters=[("carpark_id", "in", sorted(rows["carpark_id"].unique()))])
    by_carpark = {k: g for k, g in obs.groupby("carpark_id")}
    engine = Engine(load_artifacts(ML / "models"), ReplayFeed())

    bad = []
    for r in rows.itertuples(index=False):
        g = by_carpark[r.carpark_id]
        known = g[(g["first_seen_at"] <= r.decision_at) & (g["observed_at"] <= r.decision_at)]
        engine.feed.now = r.decision_at.to_pydatetime()
        engine.feed.readings = {r.carpark_id: list(zip(known["observed_at"].dt.to_pydatetime(),
                                                       known["lots_available"].astype(int),
                                                       known["total_lots"].astype(int)))}
        (res,) = engine.predict([r.carpark_id], r.arrival_at.to_pydatetime())
        assert res["status"] == "ok" and res["mode"] == "short", res
        if not abs(res["p_free"] - float(r.p_free)) <= TOLERANCE:
            bad.append((r.carpark_id, r.decision_at, res["p_free"], float(r.p_free)))
    assert not bad, f"{len(bad)} of {len(rows)} rows differ by more than {TOLERANCE}: {bad[:5]}"
