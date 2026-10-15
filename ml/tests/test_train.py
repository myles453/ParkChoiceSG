"""Tests for ml/train.py on small hand-built fixtures (no real data needed)."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import train as tr  # noqa: E402
from build_dataset import SGT, Config  # noqa: E402

UTC = timezone.utc


def make_pairs(seed=0, per_split=300, carparks=("A", "B", "C")) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    starts = {"train": datetime(2026, 8, 3, tzinfo=UTC), "validation": datetime(2026, 9, 20, tzinfo=UTC),
              "test": datetime(2026, 10, 1, tzinfo=UTC)}
    frames = []
    for split, start in starts.items():
        n = per_split
        cp = rng.choice(list(carparks), n)
        dec = [start + timedelta(minutes=15 * int(k)) for k in rng.integers(0, 400, n)]
        avail = rng.integers(0, 50, n)
        horizon = rng.choice([15, 30, 45, 60, 90], n)
        arrival = [d + timedelta(minutes=int(h)) for d, h in zip(dec, horizon)]
        slot = np.array([(a.astimezone(SGT).hour * 4 + a.astimezone(SGT).minute // 15) for a in arrival])
        lag = lambda: np.where(rng.random(n) > 0.2, avail + rng.integers(-3, 4, n), np.nan)
        l15, l30, l60 = lag(), lag(), lag()
        frames.append(pd.DataFrame({
            "carpark_id": cp, "decision_at": pd.to_datetime(dec, utc=True).astype("datetime64[us, UTC]"),
            "arrival_at": pd.to_datetime(arrival, utc=True).astype("datetime64[us, UTC]"), "split": split,
            "horizon_minutes": horizon.astype("int16"), "current_available": avail,
            "current_total_lots": 60, "current_free_ratio": (avail / 60).astype("float32"),
            "current_age_seconds": rng.integers(0, 900, n), "available_lag_15min": l15,
            "available_lag_30min": l30, "available_lag_60min": l60, "delta_15min": avail - l15,
            "delta_60min": avail - l60, "arrival_weekday": 1, "arrival_slot_15min": slot.astype("int8"),
            "arrival_is_weekend": False, "arrival_is_public_holiday": False,
            "label_available": avail, "label_free": (rng.random(n) < 0.7 + 0.2 * (avail > 5)).astype("int8"),
            "label_offset_seconds": 0}))
    return pd.concat(frames, ignore_index=True)


def write_pairs(path: Path, df: pd.DataFrame) -> Path:
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path, row_group_size=200)
    return path


@pytest.fixture
def pairs_path(tmp_path):
    return write_pairs(tmp_path / "pairs.parquet", make_pairs())


def test_hash_sample_is_reproducible_and_independent_of_order():
    names = ["A", "B", "C"]
    idx = np.array([0, 1, 2, 0, 1, 2] * 100)
    dec = (np.arange(600, dtype=np.int64) * 900_000_000) + 1_790_000_000_000_000
    h1 = tr.row_hash(names, idx, dec)
    h2 = tr.row_hash(names, idx, dec)
    assert (h1 == h2).all()
    perm = np.random.default_rng(1).permutation(600)
    assert (tr.row_hash(names, idx[perm], dec[perm]) == h1[perm]).all()
    keep = tr.hash_keep(h1, 0.3)
    assert np.array_equal(keep[perm], tr.hash_keep(h1[perm], 0.3))
    assert 0.2 < keep.mean() < 0.4
    # a smaller fraction selects a subset of a bigger fraction
    assert (tr.hash_keep(h1, 0.1) <= tr.hash_keep(h1, 0.3)).all()
    # the same (carpark, decision) hashes the same even if the carpark's dictionary index differs
    assert tr.row_hash(["C", "B", "A"], np.array([2]), dec[:1])[0] == tr.row_hash(names, np.array([0]), dec[:1])[0]


def test_sample_never_exceeds_cap_and_is_stable(pairs_path):
    stats = tr.make_carpark_stats(tr.accumulate_carpark_stats(pairs_path))
    lookup = tr.StatsLookup(stats)
    n = 300
    X1, y1 = tr.load_train_sample(pairs_path, lookup, n, cap=100)
    X2, y2 = tr.load_train_sample(pairs_path, lookup, n, cap=100)
    assert 0 < len(y1) <= 100
    assert np.array_equal(y1, y2) and np.array_equal(X1, X2, equal_nan=True)
    Xall, yall = tr.load_train_sample(pairs_path, lookup, n, cap=10_000)
    assert len(yall) == n  # under the cap: every row, no sampling


def test_no_label_column_reaches_feature_matrix(pairs_path):
    assert len(tr.FEATURE_NAMES) == 16 and tr.FEATURE_NAMES[:14] == tr.PAIR_FEATURES
    assert tr.FEATURE_NAMES[14:] == ["carpark_free_share", "carpark_slot_free_share"]
    assert not any(n.startswith("label_") or n in tr.FORBIDDEN for n in tr.FEATURE_NAMES)
    with pytest.raises(ValueError):
        tr.check_features(tr.FEATURE_NAMES + ["label_free"])
    stats = tr.make_carpark_stats(tr.accumulate_carpark_stats(pairs_path))
    lookup = tr.StatsLookup(stats)
    cols = tr.PAIR_FEATURES + ["carpark_id", "label_free", "label_available"]
    table = next(tr.iter_pairs(pairs_path, "validation", cols))
    X = tr.feature_matrix(table, lookup)
    assert X.shape[1] == 16 and X.dtype == np.float32
    flipped = table.set_column(table.schema.get_field_index("label_free"), "label_free",
                               pa.array(1 - table.column("label_free").to_numpy()))
    assert np.array_equal(tr.feature_matrix(flipped, lookup), X, equal_nan=True)


def test_history_features_come_from_train_rows_only(tmp_path):
    df = make_pairs(seed=3)
    df = df[~((df["split"] != "train") & (df["carpark_id"] == "C"))]
    df = pd.concat([df, df.iloc[:0]])
    # carpark D appears only in validation
    extra = df[df["split"] == "validation"].head(5).copy()
    extra["carpark_id"] = "D"
    df = pd.concat([df, extra], ignore_index=True)
    p1 = write_pairs(tmp_path / "a.parquet", df)
    flipped = df.copy()
    mask = flipped["split"] != "train"
    flipped.loc[mask, "label_free"] = 1 - flipped.loc[mask, "label_free"]
    p2 = write_pairs(tmp_path / "b.parquet", flipped)
    s1 = tr.make_carpark_stats(tr.accumulate_carpark_stats(p1))
    s2 = tr.make_carpark_stats(tr.accumulate_carpark_stats(p2))
    pd.testing.assert_frame_equal(s1, s2)  # validation/test labels cannot change the stats
    assert "D" not in set(s1["carpark_id"])
    lookup = tr.StatsLookup(s1)
    table = next(tr.iter_pairs(p1, "validation", tr.PAIR_FEATURES + ["carpark_id"]))
    X = tr.feature_matrix(table, lookup)
    ids = np.asarray(table.column("carpark_id").to_pylist())
    assert np.isnan(X[ids == "D", 14:]).all()  # no train rows: both values empty
    train = df[df["split"] == "train"]
    for cp in ("A", "B"):
        share = train.loc[train["carpark_id"] == cp, "label_free"].mean()
        assert np.allclose(X[ids == cp, 14], share, atol=1e-6)
    top = s1[s1["slot_15min"] == -1]
    assert top["carpark_slot_free_share"].isna().all()


def test_slot_share_is_smoothed_towards_carpark_share():
    counts = pd.DataFrame({"carpark_id": ["A", "A"], "slot": [10, 11], "sum": [10, 0], "count": [10, 30]})
    stats = tr.make_carpark_stats(counts)
    share = 10 / 40
    row = stats[(stats["carpark_id"] == "A") & (stats["slot_15min"] == 10)].iloc[0]
    assert row["carpark_free_share"] == pytest.approx(share)
    assert row["carpark_slot_free_share"] == pytest.approx((10 + 20 * share) / (10 + 20))


def test_profile_day_types_staleness_and_cutoff(tmp_path):
    def us(text):
        return datetime.fromisoformat(text).replace(tzinfo=SGT).astimezone(UTC)
    rows = [  # carpark, observed (SGT), available, first_seen (SGT)
        ("A", "2026-08-10T09:00", 3, "2026-08-10T09:02"),    # National Day in lieu (Mon) -> sunday_ph
        ("A", "2026-08-10T09:05", 0, "2026-08-10T09:06"),
        ("A", "2026-08-11T09:00", 5, "2026-08-11T09:01"),    # normal Tuesday
        ("A", "2026-08-15T09:00", 5, "2026-08-15T09:01"),    # Saturday
        ("A", "2026-08-11T10:00", 5, "2026-08-11T12:00"),    # stale when first seen -> excluded
        ("A", "2026-09-28T09:00", 5, "2026-09-28T09:01"),    # test date -> excluded
    ]
    df = pd.DataFrame({"carpark_id": [r[0] for r in rows],
                       "observed_at": pd.to_datetime([us(r[1]) for r in rows]).astype("datetime64[us, UTC]"),
                       "lots_available": np.array([r[2] for r in rows], dtype="int32"), "total_lots": 10,
                       "first_seen_at": pd.to_datetime([us(r[3]) for r in rows]).astype("datetime64[us, UTC]")})
    path = tmp_path / "obs.parquet"
    df.to_parquet(path, index=False)
    cfg = Config()
    prof = tr.build_profile(path, cfg.start_us, cfg.test_start_us, prior=20)
    got = {(r.day_type, r.slot_15min): (r.n_samples, r.p_free) for r in prof.itertuples()}
    assert set(got) == {("sunday_ph", 36), ("weekday", 36), ("saturday", 36)}
    assert got[("sunday_ph", 36)][0] == 2 and got[("weekday", 36)][0] == 1
    cp_share = 3 / 4  # carpark level: the four counted observations are free 1, 0, 1, 1
    assert got[("sunday_ph", 36)][1] == pytest.approx((1 + 20 * cp_share) / (2 + 20), rel=1e-5)
    assert list(prof.columns) == ["carpark_id", "day_type", "slot_15min", "p_free", "n_samples"]


def test_choose_bands_returns_valid_service_bands():
    rng = np.random.default_rng(0)
    p = rng.random(20_000)
    y = (rng.random(20_000) < p).astype(np.int8)
    thr, bands = tr.choose_bands(y, p)
    assert 0 <= thr <= 1 and 0 <= bands["medium"] <= bands["high"] <= 1
    assert set(bands) == {"high", "medium"}


def test_saved_artefacts_load_through_service_loader(tmp_path):
    pytest.importorskip("lightgbm")
    from service.artifacts import load_artifacts
    pairs = write_pairs(tmp_path / "pairs.parquet", make_pairs(seed=5, per_split=500))
    rows = []
    t0 = datetime(2026, 8, 3, 9, 0, tzinfo=SGT).astimezone(UTC)
    for k in range(60):
        for cp in ("A", "B"):
            t = t0 + timedelta(minutes=5 * k)
            rows.append((cp, t, k % 4, 10, t + timedelta(minutes=1)))
    obs = pd.DataFrame(rows, columns=["carpark_id", "observed_at", "lots_available", "total_lots", "first_seen_at"])
    obs["observed_at"] = obs["observed_at"].astype("datetime64[us, UTC]")
    obs["first_seen_at"] = obs["first_seen_at"].astype("datetime64[us, UTC]")
    obs_path = tmp_path / "obs.parquet"
    obs.to_parquet(obs_path, index=False)
    out = tmp_path / "models"
    card = tr.train_all(pairs, obs_path, out, threads=2, sample_cap=400,
                        configs=[dict(num_leaves=7, learning_rate=0.2, min_child_samples=5)], n_estimators=20)
    assert card["train_sample_size"] <= 400 and card["feature_names"] == tr.FEATURE_NAMES
    art = load_artifacts(out)
    assert art.feature_names == tr.FEATURE_NAMES
    X = pd.DataFrame(np.zeros((3, 16), dtype=np.float32), columns=art.feature_names)
    X.iloc[:, 14:] = np.nan
    p = art.calibrator.predict(art.model.predict_proba(X)[:, 1])
    assert p.shape == (3,) and np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all()
    assert art.confidence(0.0) in {"High", "Medium", "Low"}
