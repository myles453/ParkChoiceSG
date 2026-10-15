import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import build_retrieval_view as bv  # noqa: E402
import train  # noqa: E402
from features import FEATURES_A, FEATURES_B, MIN_US, compute_features  # noqa: E402

T0 = bv.sgt_us(2026, 8, 1)  # an arbitrary Singapore midnight inside the train split


def series(minutes, values):
    return np.array([T0 + m * MIN_US for m in minutes], dtype=np.int64), np.array(values, dtype=np.int64)


def row(df, **kw):
    assert len(df) == 1
    return df.iloc[0]


def test_no_feature_uses_a_row_after_decision():
    mins = list(range(0, 600, 5))
    vals = [i % 17 for i in range(len(mins))]
    seen, lots = series(mins, vals)
    dec = np.array([T0 + 300 * MIN_US])
    base = compute_features(seen, lots, dec, [30])
    # Add poisoned rows strictly after the decision time (huge counts) and a series cut at the decision.
    seen2, lots2 = series(mins + [301, 302, 330], vals + [999, 999, 999])
    order = np.argsort(seen2)
    poisoned = compute_features(seen2[order], lots2[order], dec, [30])
    cut = compute_features(seen[seen <= dec[0]], lots[seen <= dec[0]], dec, [30])
    assert base.equals(cut) and base.equals(poisoned)
    assert base["trailing_max_72h"].isna().all()  # only 5 h of history


def test_stale_current_reading_gives_no_row():
    seen, lots = series([0, 5, 10], [3, 3, 3])
    fresh = compute_features(seen, lots, np.array([T0 + 16 * MIN_US]), [15])  # 6 min old: allowed
    stale = compute_features(seen, lots, np.array([T0 + 16 * MIN_US + 1]), [15])  # 6 min + 1 us old
    assert len(fresh) == 1 and len(stale) == 0
    assert len(compute_features(seen, lots, np.array([T0 - MIN_US]), [15])) == 0  # nothing yet


def test_lags_and_deltas():
    seen, lots = series(range(0, 130, 5), range(0, 130, 5))
    f = row(compute_features(seen, lots, np.array([T0 + 120 * MIN_US]), [30]))
    assert f.current_available == 120 and f.available_lag_15min == 105 and f.available_lag_60min == 60
    assert f.delta_15min == 15 and f.delta_60min == 60
    seen, lots = series([0, 30, 120], [1, 1, 1])  # no row within 4 min of t-15 or t-60
    g = row(compute_features(seen, lots, np.array([T0 + 120 * MIN_US]), [15]))
    assert np.isnan(g.available_lag_15min) and np.isnan(g.delta_60min)


def test_trailing_max_needs_24h_history():
    mins = list(range(0, 80 * 60, 5))
    vals = [5] * len(mins)
    vals[10] = 40  # at minute 50
    seen, lots = series(mins, vals)
    early = row(compute_features(seen, lots, np.array([T0 + 23 * 60 * MIN_US]), [15]))
    late = row(compute_features(seen, lots, np.array([T0 + 24 * 60 * MIN_US]), [15]))
    assert np.isnan(early.trailing_max_72h) and np.isnan(early.ratio_to_trailing_max)
    assert late.trailing_max_72h == 40 and np.isclose(late.ratio_to_trailing_max, 5 / 40)
    after = row(compute_features(seen, lots, np.array([T0 + 75 * 60 * MIN_US]), [15]))  # spike left 72 h window
    assert after.trailing_max_72h == 5
    zero = compute_features(*series(range(0, 30 * 60, 5), [0] * 360), np.array([T0 + 25 * 60 * MIN_US]), [15])
    assert zero.trailing_max_72h.iloc[0] == 0 and np.isnan(zero.ratio_to_trailing_max.iloc[0])


def test_variant_a_has_no_trailing_columns():
    seen, lots = series([0], [1])
    df = compute_features(seen, lots, np.array([T0]), [15], variant_b=False)
    assert list(df.columns) == ["decision_us"] + FEATURES_A
    assert FEATURES_B[:len(FEATURES_A)] == FEATURES_A


def test_calendar_features_singapore_time():
    seen, lots = series([0], [1])
    # 2026-08-09 is a Sunday and National Day; 23:50 SGT + 15 min arrives Monday 2026-08-10 (in lieu)
    d = bv.sgt_us(2026, 8, 9, 23, 50)
    f = row(compute_features(np.array([d]), lots, np.array([d]), [15]))
    assert f.arrival_weekday == 1 and f.arrival_slot_15min == 0 and f.arrival_is_public_holiday == 1
    assert f.arrival_is_weekend == 0


def test_pair_crossing_a_split_is_dropped():
    # Readings every 5 minutes either side of the train/validation boundary (2026-09-16 00:00 SGT).
    start = bv.VALID_START - 3 * 60 * MIN_US
    seen = np.arange(start, start + 6 * 60 * MIN_US, 5 * MIN_US, dtype=np.int64)
    lots = np.ones(len(seen), dtype=np.int64)
    p = bv.pairs_for_carpark("X1", seen, lots)
    dec = p["decision_at"].dt.as_unit("us").astype("int64").to_numpy()
    arr = p["arrival_at"].dt.as_unit("us").astype("int64").to_numpy()
    assert len(p) > 0
    assert ((dec < bv.VALID_START) == (arr < bv.VALID_START)).all()
    # decision 23:45 on 09-15 with horizon 30 arrives in validation: must be absent
    crossing = (dec == bv.VALID_START - 15 * MIN_US) & (arr - dec == 30 * MIN_US)
    assert not crossing.any()
    inside = (dec == bv.VALID_START - 15 * MIN_US) & (arr - dec == 15 * MIN_US)
    assert not inside.any()  # arrival 00:00 is already validation
    assert (p.loc[dec == bv.VALID_START - 30 * MIN_US, "horizon_minutes"] == 15).any()  # arrival 23:45 stays in train


def test_pair_needs_a_label_row_within_6_minutes():
    start = bv.VALID_START + 24 * 60 * MIN_US
    seen = np.array([start + m * MIN_US for m in (0, 5, 10, 15, 40)], dtype=np.int64)
    lots = np.array([1, 1, 1, 0, 1])
    p = bv.pairs_for_carpark("X2", seen, lots)
    dec = (p["decision_at"].dt.as_unit("us").astype("int64").to_numpy())
    arr = (p["arrival_at"].dt.as_unit("us").astype("int64").to_numpy())
    sel = (dec == start) & (arr == start + 15 * MIN_US)
    assert sel.sum() == 1 and p.loc[sel, "label_free"].iloc[0] == 0
    assert not ((dec == start) & (arr == start + 30 * MIN_US)).any()  # next row is 10 min after arrival


def test_saved_artefacts_load(tmp_path):
    rng = np.random.default_rng(0)
    X = rng.normal(size=(2000, len(FEATURES_B))).astype(np.float32)
    y = (X[:, 0] + rng.normal(size=2000) > 0).astype(np.int8)
    cfg = [{"learning_rate": 0.2, "num_leaves": 7, "min_data_in_leaf": 20, "feature_fraction": 1.0}]
    model, cal, info = train.fit_variant(X[:1500], y[:1500], X[1500:], y[1500:], FEATURES_B, cfg, num_threads=2)
    path = tmp_path / "variant_b.joblib"
    train.save_variant(path, model, cal, FEATURES_B)
    import joblib
    art = joblib.load(path)
    assert set(art) == {"model", "calibrator", "feature_names"} and art["feature_names"] == FEATURES_B
    p = train.predict_p_free(art, X[:10])
    assert p.shape == (10,) and ((p >= 0) & (p <= 1)).all()
    wild = train.predict_p_free(art, np.full((1, len(FEATURES_B)), 1e6, np.float32))
    assert 0 <= wild[0] <= 1
    assert info["chosen_config"] == cfg[0]
