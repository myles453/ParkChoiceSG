"""Parity: service features == the stored pairs.parquet features, on real data."""
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

from service.features import PAIR_FEATURES, build_features

DATA = Path(__file__).resolve().parents[2] / "data"
N_ROWS = 50


def _sample(pairs: pd.DataFrame) -> pd.DataFrame:
    """50 rows, seeded: half with a missing 60-minute lag (to test NaN parity), half without."""
    missing = pairs[pairs["available_lag_60min"].isna()]
    present = pairs[pairs["available_lag_60min"].notna()]
    return pd.concat([missing.sample(N_ROWS // 2, random_state=0),
                      present.sample(N_ROWS - N_ROWS // 2, random_state=0)])


def test_features_match_pairs_parquet():
    if not (DATA / "pairs.parquet").exists() or not (DATA / "observations.parquet").exists():
        pytest.fail("ml/data/pairs.parquet or observations.parquet is missing")
    if "first_seen_at" not in pq.read_schema(DATA / "observations.parquet").names:
        pytest.fail("observations.parquet has no first_seen_at column yet (Agent B is adding it); "
                    "the parity test must only use readings known at decision time")
    pairs = _sample(pd.read_parquet(DATA / "pairs.parquet"))
    assert len(pairs) == N_ROWS and pairs["carpark_id"].nunique() > 1
    obs = pd.read_parquet(DATA / "observations.parquet",
                          filters=[("carpark_id", "in", sorted(pairs["carpark_id"].unique()))])
    by_carpark = {k: g for k, g in obs.groupby("carpark_id")}
    checked = 0
    for row in pairs.itertuples(index=False):
        g = by_carpark[row.carpark_id]
        known = g[(g["first_seen_at"] <= row.decision_at) & (g["observed_at"] <= row.decision_at)]
        readings = list(zip(known["observed_at"], known["lots_available"]))
        cur = known.loc[known["observed_at"].idxmax()]
        got = build_features(readings, int(cur["total_lots"]), row.decision_at, row.arrival_at)
        for name in PAIR_FEATURES:
            want = getattr(row, name)
            have = got[name]
            if name == "current_free_ratio":
                have = np.float32(have)
            if isinstance(want, float) and math.isnan(want):
                assert math.isnan(have), f"{name}: stored NaN, service {have} ({row.carpark_id} {row.decision_at})"
            else:
                assert not (isinstance(have, float) and math.isnan(have)), \
                    f"{name}: stored {want}, service NaN ({row.carpark_id} {row.decision_at})"
                assert float(have) == float(want), \
                    f"{name}: stored {want}, service {have} ({row.carpark_id} {row.decision_at})"
        checked += 1
    assert checked == N_ROWS
