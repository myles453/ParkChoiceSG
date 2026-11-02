"""Unit tests for ml/build_dataset.py using small hand-built fixtures (no real data needed)."""
from __future__ import annotations

from datetime import datetime, timedelta
import gzip
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build_dataset as bd  # noqa: E402

SGT = bd.SGT


def sgt(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=SGT)


def snapshot(*parks):
    """parks: (carpark_number, update_datetime, [(lot_type, available, total), ...])"""
    return {"items": [{"timestamp": "x", "carpark_data": [
        {"carpark_number": c, "update_datetime": u,
         "carpark_info": [{"lot_type": lt, "lots_available": av, "total_lots": tot} for lt, av, tot in lots]}
        for c, u, lots in parks]}]}


def write_raw(root: Path, day: str, hhmm: str, payload) -> Path:
    path = root / day / f"{hhmm}.json.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt") as stream:
        json.dump(payload, stream)
    return path


def write_obs(path: Path, rows):
    """rows: (carpark_id, observed 'YYYY-MM-DDTHH:MM[:SS]' SGT, available, total[, first_seen SGT]).
    first_seen defaults to observed_at (the reading was visible the moment it was made)."""
    table = pa.table({
        "carpark_id": pa.array([r[0] for r in rows], pa.string()),
        "observed_at": pa.array([sgt(r[1]) for r in rows], pa.timestamp("us", tz="UTC")),
        "lots_available": pa.array([r[2] for r in rows], pa.int32()),
        "total_lots": pa.array([r[3] for r in rows], pa.int32()),
        "first_seen_at": pa.array([sgt(r[4] if len(r) > 4 else r[1]) for r in rows],
                                  pa.timestamp("us", tz="UTC")),
    })
    pq.write_table(table, path)


def run_pairs(tmp_path, rows) -> pd.DataFrame:
    obs = tmp_path / "observations.parquet"
    write_obs(obs, rows)
    bd.build_pairs(obs, tmp_path / "pairs.parquet", tmp_path / "pairs.manifest.json")
    return pd.read_parquet(tmp_path / "pairs.parquet")


def at(frame, decision: str, horizon: int):
    d = pd.Timestamp(sgt(decision)).tz_convert("UTC")
    return frame[(frame.decision_at == d) & (frame.horizon_minutes == horizon)]


# ------------------------------------------------------------------ stage 1: cleaning rules
def test_clean_keeps_only_car_lots_and_converts_sgt_to_utc():
    payload = snapshot(("ACB", "2026-08-10T12:00:00", [("C", "5", "100"), ("H", "1", "10"), ("Y", "2", "20")]))
    rows, rejected, excluded = bd.clean_snapshot(payload)
    assert rows == [("ACB", datetime(2026, 8, 10, 4, 0, tzinfo=bd.UTC), 5, 100)]
    assert excluded == 2 and not rejected


@pytest.mark.parametrize("lot, reason", [
    (("C", None, 100), "invalid_count"),
    (("C", "abc", 100), "invalid_count"),
    (("C", -1, 100), "invalid_count"),
    (("C", 5.5, 100), "invalid_count"),
    (("C", 5, None), "invalid_count"),
    (("C", 101, 100), "available_exceeds_total"),   # rejected, never clamped to 100
    (("C", 0, 0), "zero_capacity"),
    (("Q", 1, 10), "unknown_lot_type"),
])
def test_clean_rejects_bad_lots(lot, reason):
    rows, rejected, _ = bd.clean_snapshot(snapshot(("ACB", "2026-08-10T12:00:00", [lot])))
    assert rows == [] and rejected == {reason: 1}


def test_clean_zero_available_with_capacity_is_valid():
    rows, rejected, _ = bd.clean_snapshot(snapshot(("ACB", "2026-08-10T12:00:00", [("C", 0, 50)])))
    assert [r[2:] for r in rows] == [(0, 50)] and not rejected


def test_clean_rejects_bad_records_and_future_timestamps():
    payload = snapshot(("ACB", None, [("C", 1, 10)]),
                       ("ACB", "not-a-date", [("C", 1, 10)]),
                       ("a-b", "2026-08-10T12:00:00", [("C", 1, 10)]),
                       ("ACB", "2026-08-10T12:00:00", []),
                       ("ACB", "2026-08-10T12:10:00", [("C", 1, 10)]))  # 10 min after the query time
    rows, rejected, _ = bd.clean_snapshot(payload, sgt("2026-08-10T12:00:00"))
    assert rows == []
    assert rejected == {"missing_timestamp": 1, "invalid_timestamp": 1, "invalid_carpark_id": 1,
                        "missing_lot_records": 1, "future_source_timestamp": 1}


def test_clean_rejects_structurally_bad_payload():
    with pytest.raises(ValueError):
        bd.clean_snapshot({"items": []})
    with pytest.raises(ValueError):
        bd.clean_snapshot({"items": [{"carpark_data": []}]})


# ------------------------------------------------------------------ stage 1: observations file
def test_conflict_dropped_exact_duplicates_collapsed(tmp_path):
    raw = tmp_path / "raw"
    # same carpark + update time in two files: ACB conflicts across files (different batches), XYZ agrees
    write_raw(raw, "2026-08-10", "1200", snapshot(("ACB", "2026-08-10T11:58:00", [("C", 10, 100)]),
                                                  ("XYZ", "2026-08-10T11:58:00", [("C", 3, 50)]),
                                                  ("OKK", "2026-08-10T11:58:00", [("C", 7, 70)])))
    write_raw(raw, "2026-08-10", "1205", snapshot(("ACB", "2026-08-10T11:58:00", [("C", 11, 100)]),
                                                  ("XYZ", "2026-08-10T11:58:00", [("C", 3, 50)]),
                                                  ("OKK", "2026-08-10T12:03:00", [("C", 8, 70)])))
    manifest = bd.build_observations(raw, tmp_path / "obs.parquet", tmp_path / "obs.manifest.json",
                                     batch_files=1, shards=4)
    frame = pd.read_parquet(tmp_path / "obs.parquet")
    assert sorted(frame.carpark_id) == ["OKK", "OKK", "XYZ"]          # ACB 11:58 dropped entirely
    assert not frame.duplicated(["carpark_id", "observed_at"]).any()
    assert manifest["conflict_count"] == 1
    assert manifest["exact_duplicate_rows_removed"] == 1
    assert manifest["rows"] == 3 and manifest["carpark_count"] == 2
    assert manifest["observed_at_min_utc"].startswith("2026-08-10T03:58")
    assert json.loads((tmp_path / "obs.manifest.json").read_text())["rows"] == 3


def test_build_observations_counts_rejections_and_unreadable_files(tmp_path):
    raw = tmp_path / "raw"
    write_raw(raw, "2026-08-10", "1200", snapshot(("ACB", "2026-08-10T11:58:00", [("C", 10, 100), ("H", 1, 5)]),
                                                  ("BAD", "2026-08-10T11:58:00", [("C", 9, 5)]),
                                                  ("ZER", "2026-08-10T11:58:00", [("C", 0, 0)])))
    (raw / "2026-08-10" / "1205.json.gz").write_bytes(b"not gzip")
    write_raw(raw, "2026-08-10", "1210", {"items": []})
    m = bd.build_observations(raw, tmp_path / "o.parquet", tmp_path / "o.json")
    assert m["rows"] == 1 and m["files_found"] == 3 and m["files_read"] == 1
    assert m["rejected_by_reason"] == {"available_exceeds_total": 1, "zero_capacity": 1}
    assert m["excluded_non_car_lot_records"] == 1
    assert m["files_rejected"] == {"unreadable_gzip": 1, "missing_items": 1}
    schema = pq.read_schema(tmp_path / "o.parquet")
    assert schema.field("observed_at").type == pa.timestamp("us", tz="UTC")


def test_build_observations_with_no_files(tmp_path):
    m = bd.build_observations(tmp_path / "missing", tmp_path / "o.parquet", tmp_path / "o.json")
    assert m["rows"] == 0 and m["carpark_count"] == 0 and len(pd.read_parquet(tmp_path / "o.parquet")) == 0


# ------------------------------------------------------------------ stage 2: label tolerance
def test_label_outside_five_minute_tolerance_yields_no_row(tmp_path):
    rows = [("A", "2026-08-12T11:55", 10, 100),
            ("A", "2026-08-12T12:10:00", 4, 100),    # 10 min after arrival 12:00? see below
            ("A", "2026-08-12T12:25:01", 1, 100)]    # 5 min 1 s after arrival 12:20 -> too late
    # decision 12:00, current = 11:55 (age 5 min). h=15 -> arrival 12:15, first obs >= 12:15 is 12:25:01
    frame = run_pairs(tmp_path, rows)
    assert at(frame, "2026-08-12T12:00", 15).empty
    # h=30 -> arrival 12:30; nothing at/after it -> no row
    assert at(frame, "2026-08-12T12:00", 30).empty


def test_label_exactly_five_minutes_after_is_kept_and_offset_recorded(tmp_path):
    rows = [("A", "2026-08-12T11:55", 10, 100), ("A", "2026-08-12T12:20:00", 0, 100)]
    frame = run_pairs(tmp_path, rows)
    row = at(frame, "2026-08-12T12:00", 15)       # arrival 12:15, label at 12:20:00 = +300 s
    assert len(row) == 1
    r = row.iloc[0]
    assert (r.label_available, r.label_free, r.label_offset_seconds) == (0, 0, 300)
    assert at(frame, "2026-08-12T12:00", 60).empty


def test_label_uses_first_observation_at_or_after_arrival(tmp_path):
    rows = [("A", "2026-08-12T11:55", 10, 100), ("A", "2026-08-12T12:14", 99, 100),   # before arrival: ignored
            ("A", "2026-08-12T12:15", 3, 100), ("A", "2026-08-12T12:16", 50, 100)]
    r = at(run_pairs(tmp_path, rows), "2026-08-12T12:00", 15).iloc[0]
    assert (r.label_available, r.label_free, r.label_offset_seconds) == (3, 1, 0)


# ------------------------------------------------------------------ stage 2: stale current
def test_stale_current_reading_yields_no_row(tmp_path):
    rows = [("A", "2026-08-12T11:44:59", 10, 100),    # age 15:01 at 12:00 -> stale
            ("A", "2026-08-12T12:15", 5, 100)]
    assert at(run_pairs(tmp_path, rows), "2026-08-12T12:00", 15).empty


def test_current_reading_exactly_fifteen_minutes_old_is_kept(tmp_path):
    rows = [("A", "2026-08-12T11:45:00", 10, 100), ("A", "2026-08-12T12:15", 5, 100)]
    r = at(run_pairs(tmp_path, rows), "2026-08-12T12:00", 15).iloc[0]
    assert r.current_age_seconds == 900 and r.current_available == 10


def test_no_current_reading_at_all_yields_no_row(tmp_path):
    rows = [("A", "2026-08-12T12:30", 10, 100), ("A", "2026-08-12T13:00", 5, 100)]
    assert at(run_pairs(tmp_path, rows), "2026-08-12T12:00", 30).empty


# ------------------------------------------------------------------ stage 2: split rules
def test_pair_crossing_split_boundary_is_dropped(tmp_path):
    rows = [("A", "2026-09-15T23:30", 10, 100), ("A", "2026-09-15T23:45", 9, 100),
            ("A", "2026-09-15T23:50", 8, 100), ("A", "2026-09-16T00:00", 7, 100),
            ("A", "2026-09-16T00:15", 6, 100)]
    frame = run_pairs(tmp_path, rows)
    # decision 23:45 train, arrival 00:00 validation (label exists) -> dropped
    assert at(frame, "2026-09-15T23:45", 15).empty
    # decision 23:30 train, arrival 23:45 train (label 23:50) -> kept as train
    kept = at(frame, "2026-09-15T23:30", 15)
    assert len(kept) == 1 and kept.iloc[0].split == "train"
    # decision 00:00 validation with arrival 00:15 validation -> kept as validation
    val = at(frame, "2026-09-16T00:00", 15)
    assert len(val) == 1 and val.iloc[0].split == "validation"
    # no row ever has decision, arrival and label in different splits
    cfg = bd.Config()
    d = frame.decision_at.astype("int64").to_numpy()
    arrival = frame.arrival_at.astype("int64").to_numpy()
    names = np.array(bd.SPLIT_NAMES)
    assert (names[cfg.split_code(d)] == frame.split.to_numpy()).all()
    assert (names[cfg.split_code(arrival)] == frame.split.to_numpy()).all()


def test_split_code_boundaries():
    cfg = bd.Config()
    sgt_code = lambda s: int(cfg.split_code(np.array([bd.to_us(sgt(s))]))[0])  # noqa: E731
    assert sgt_code("2026-07-14T23:59:59") == -1
    assert sgt_code("2026-07-15T00:00") == 0
    assert sgt_code("2026-09-15T23:59:59") == 0
    assert sgt_code("2026-09-16T00:00") == 1
    assert sgt_code("2026-09-26T23:59:59") == 1
    assert sgt_code("2026-09-27T00:00") == 2
    assert sgt_code("2026-10-07T23:59:59") == 2
    assert sgt_code("2026-10-08T00:00") == -1


def test_pair_whose_label_falls_after_data_range_is_dropped(tmp_path):
    rows = [("A", "2026-10-07T23:40", 10, 100), ("A", "2026-10-08T00:05", 5, 100)]
    assert at(run_pairs(tmp_path, rows), "2026-10-07T23:30", 30).empty


# ------------------------------------------------------------------ stage 2: features
def test_features_lags_deltas_and_calendar(tmp_path):
    rows = [("A", "2026-08-10T10:58", 20, 100),   # lag60 target 11:00 -> within 10 min
            ("A", "2026-08-10T11:42", 12, 100),   # lag15 target 11:45 (3 min away)
            ("A", "2026-08-10T11:25", 15, 100),   # lag30 target 11:30 (5 min away)
            ("A", "2026-08-10T12:00", 10, 80),
            ("A", "2026-08-10T12:15", 4, 80)]
    r = at(run_pairs(tmp_path, rows), "2026-08-10T12:00", 15).iloc[0]
    assert (r.current_available, r.current_total_lots, r.current_age_seconds) == (10, 80, 0)
    assert r.current_free_ratio == pytest.approx(10 / 80)
    assert (r.available_lag_15min, r.available_lag_30min, r.available_lag_60min) == (12, 15, 20)
    assert (r.delta_15min, r.delta_60min) == (10 - 12, 10 - 20)
    assert r.horizon_minutes == 15
    # arrival 12:15 SGT on Monday 2026-08-10 (National Day in lieu)
    assert (r.arrival_weekday, r.arrival_slot_15min) == (1, 49)
    assert not r.arrival_is_weekend and r.arrival_is_public_holiday


def test_lag_left_empty_when_no_reading_within_ten_minutes(tmp_path):
    rows = [("A", "2026-08-11T11:30", 20, 100),   # lag15 target 11:45 -> 15 min away: too far
            ("A", "2026-08-11T12:00", 10, 80), ("A", "2026-08-11T12:15", 4, 80)]
    r = at(run_pairs(tmp_path, rows), "2026-08-11T12:00", 15).iloc[0]
    assert pd.isna(r.available_lag_15min) and pd.isna(r.delta_15min)
    assert r.available_lag_30min == 20           # target 11:30 exactly
    assert pd.isna(r.available_lag_60min) and pd.isna(r.delta_60min)


def test_weekend_slot_and_midnight_are_singapore_time(tmp_path):
    # 2026-08-15 is a Saturday, 2026-08-16 a Sunday (neither is a holiday)
    rows = [("A", "2026-08-15T23:30", 10, 80), ("A", "2026-08-15T23:45", 3, 80), ("A", "2026-08-16T00:00", 2, 80)]
    frame = run_pairs(tmp_path, rows)
    sat = at(frame, "2026-08-15T23:30", 15).iloc[0]    # arrival Sat 23:45 SGT
    assert (sat.arrival_weekday, sat.arrival_slot_15min) == (6, 95)
    assert sat.arrival_is_weekend and not sat.arrival_is_public_holiday
    sun = at(frame, "2026-08-15T23:45", 15).iloc[0]    # arrival Sun 00:00 SGT (still Sat 16:00 UTC)
    assert (sun.arrival_weekday, sun.arrival_slot_15min) == (7, 0)
    assert sun.arrival_is_weekend


def test_horizons_produce_one_row_each(tmp_path):
    base = datetime(2026, 8, 12, 12, 0, tzinfo=SGT)
    rows = [("A", "2026-08-12T12:00", 10, 100)] + [
        ("A", (base + timedelta(minutes=h)).replace(tzinfo=None).isoformat(), 10 - i, 100)
        for i, h in enumerate(bd.HORIZONS)]
    frame = run_pairs(tmp_path, rows)
    sub = frame[frame.decision_at == pd.Timestamp(base).tz_convert("UTC")]
    assert sorted(sub.horizon_minutes) == list(bd.HORIZONS)


# ------------------------------------------------------------------ stage 2: no look-ahead
def test_features_never_use_observations_after_decision_time():
    cfg = bd.Config()
    rng = np.random.default_rng(0)
    start = bd.sgt_us(2026, 8, 12, 9)
    t = np.sort(start + rng.choice(np.arange(0, 6 * 3600, 30), size=200, replace=False) * 1_000_000)
    a = rng.integers(0, 100, size=t.size).astype(np.int32)
    n = np.full(t.size, 100, dtype=np.int32)
    decisions = cfg.decision_grid()
    decisions = decisions[(decisions >= start) & (decisions <= start + 6 * 3600 * 1_000_000)]
    keep, full = bd.compute_features(t, a, n, t, decisions)
    for i, d in enumerate(full["decision"]):
        past = t <= d
        keep_p, trunc = bd.compute_features(t[past], a[past], n[past], t[past], np.array([d]))
        assert keep_p.all()
        for key, value in full.items():
            if isinstance(value, tuple):
                assert trunc[key][1][0] == value[1][i]
                if value[1][i]:
                    assert trunc[key][0][0] == value[0][i]
            else:
                assert trunc[key][0] == value[i]


def test_changing_future_observations_does_not_change_features(tmp_path):
    base = [("A", "2026-08-12T11:50", 10, 100), ("A", "2026-08-12T11:30", 14, 100),
            ("A", "2026-08-12T10:58", 18, 100)]
    future_a = base + [("A", "2026-08-12T12:20", 1, 100), ("A", "2026-08-12T12:21", 2, 100)]
    future_b = base + [("A", "2026-08-12T12:20", 77, 100), ("A", "2026-08-12T12:21", 88, 100)]
    one = at(run_pairs(tmp_path, future_a), "2026-08-12T12:00", 15)
    two = at(run_pairs(tmp_path, future_b), "2026-08-12T12:00", 15)
    features = [c for c in one.columns if not c.startswith("label_")]
    assert len(one) == len(two) == 1
    pd.testing.assert_frame_equal(one[features].reset_index(drop=True), two[features].reset_index(drop=True))
    assert one.iloc[0].label_available != two.iloc[0].label_available


def test_manifest_counts_match_parquet(tmp_path):
    rows = [("A", "2026-08-12T12:00", 10, 100), ("A", "2026-08-12T12:15", 0, 100),
            ("A", "2026-08-12T12:30", 2, 100), ("B", "2026-08-12T12:00", 5, 50), ("B", "2026-08-12T12:15", 0, 50)]
    frame = run_pairs(tmp_path, rows)
    m = json.loads((tmp_path / "pairs.manifest.json").read_text())
    assert m["rows"] == len(frame)
    assert m["rows_per_split"]["train"] == (frame.split == "train").sum()
    assert m["rows_per_horizon"]["15"] == (frame.horizon_minutes == 15).sum()
    assert m["label_free_0_share_overall"] == pytest.approx((frame.label_free == 0).mean())
    assert (frame.label_free == (frame.label_available >= 1).astype(int)).all()


# ------------------------------------------------------------------ first_seen_at
def test_first_seen_at_is_earliest_file_containing_the_pair(tmp_path):
    raw = tmp_path / "raw"
    same = ("ACB", "2026-08-10T11:58:00", [("C", 10, 100)])
    write_raw(raw, "2026-08-10", "1210", snapshot(same))   # a later file repeating the same reading
    write_raw(raw, "2026-08-10", "1200", snapshot(same))   # earliest file, written second on purpose
    write_raw(raw, "2026-08-10", "1205", snapshot(("ACB", "2026-08-10T12:03:00", [("C", 9, 100)])))
    bd.build_observations(raw, tmp_path / "o.parquet", tmp_path / "o.json", batch_files=1, shards=2)
    frame = pd.read_parquet(tmp_path / "o.parquet").sort_values("observed_at")
    assert list(frame.first_seen_at) == [pd.Timestamp("2026-08-10T12:00", tz="Asia/Singapore"),
                                         pd.Timestamp("2026-08-10T12:05", tz="Asia/Singapore")]
    assert str(frame.first_seen_at.dt.tz) == "UTC"
    assert pq.read_schema(tmp_path / "o.parquet").field("first_seen_at").type == pa.timestamp("us", tz="UTC")


def test_manifest_first_seen_delay_distribution(tmp_path):
    raw = tmp_path / "raw"
    # first_seen - observed: 60 s, 120 s, 300 s, and one 20-minute-old reading (excluded from the summary)
    write_raw(raw, "2026-08-10", "1200", snapshot(("A", "2026-08-10T11:59:00", [("C", 1, 10)]),
                                                  ("B", "2026-08-10T11:58:00", [("C", 1, 10)]),
                                                  ("C", "2026-08-10T11:55:00", [("C", 1, 10)]),
                                                  ("D", "2026-08-10T11:40:00", [("C", 1, 10)])))
    m = bd.build_observations(raw, tmp_path / "o.parquet", tmp_path / "o.json")
    d = m["first_seen_minus_observed_seconds"]
    assert d["younger_than_15min"] == {"count": 3, "median_seconds": 120.0,
                                       "p90_seconds": pytest.approx(264.0), "max_seconds": 300.0}
    assert d["rows_15min_or_older"] == 1 and d["all_rows"]["max_seconds"] == 1200.0


def test_manifest_names_carparks_rejected_every_file(tmp_path):
    raw = tmp_path / "raw"
    for hhmm in ("1200", "1205"):
        write_raw(raw, "2026-08-10", hhmm, snapshot(("S1", "2026-08-10T11:58:00", [("S", 0, 0)]),
                                                    ("Z1", "2026-08-10T11:58:00", [("C", 0, 0)]),
                                                    ("OK", "2026-08-10T11:58:00", [("C", 1, 5)])))
    m = bd.build_observations(raw, tmp_path / "o.parquet", tmp_path / "o.json")
    top = {(r["reason"], r["carpark_id"]): (r["lot_records"], r["files"]) for r in m["rejected_carparks_top"]}
    assert top == {("unknown_lot_type", "S1"): (2, 2), ("zero_capacity", "Z1"): (2, 2)}


def test_observation_seen_after_decision_is_not_a_feature_but_can_be_a_label(tmp_path):
    # observed 11:56 (before the 12:00 decision) but first seen 12:05 (after it)
    rows = [("A", "2026-08-12T11:50", 10, 100),
            ("A", "2026-08-12T11:56", 7, 100, "2026-08-12T12:05"),
            ("A", "2026-08-12T12:15", 5, 100)]
    r = at(run_pairs(tmp_path, rows), "2026-08-12T12:00", 15).iloc[0]
    # current reading is the 11:50 one; age is decision time minus observed_at
    assert (r.current_available, r.current_age_seconds) == (10, 600)
    assert r.available_lag_15min == 10 and 7 not in (r.current_available, r.available_lag_15min,
                                                      r.available_lag_30min, r.available_lag_60min)
    # the same kind of observation may still be the label (selected by observed_at, first_seen_at ignored)
    rows2 = [("A", "2026-08-12T11:40", 10, 100), ("A", "2026-08-12T12:01", 3, 100, "2026-08-12T12:30")]
    lab = at(run_pairs(tmp_path, rows2), "2026-08-12T11:45", 15).iloc[0]   # arrival 12:00
    assert (lab.label_available, lab.label_offset_seconds) == (3, 60)


def test_late_seen_observations_are_excluded_from_current_and_every_lag(tmp_path):
    late = "2026-08-12T13:00"
    base = [("A", "2026-08-12T10:58", 20, 100), ("A", "2026-08-12T11:31", 15, 100),
            ("A", "2026-08-12T11:46", 12, 100), ("A", "2026-08-12T11:50", 11, 100),
            ("A", "2026-08-12T11:57", 10, 100), ("A", "2026-08-12T12:15", 4, 100)]
    # all visible: current 11:57, lag15 nearest 11:46
    r = at(run_pairs(tmp_path, base), "2026-08-12T12:00", 15).iloc[0]
    assert (r.current_available, r.available_lag_15min, r.available_lag_30min, r.available_lag_60min) == (10, 12, 15, 20)
    # 11:46 and 11:57 first seen at 13:00: current falls back to 11:50, lag15 to the nearest known (11:50)
    delayed = [row + (late,) if row[1] in ("2026-08-12T11:46", "2026-08-12T11:57") else row for row in base]
    r = at(run_pairs(tmp_path, delayed), "2026-08-12T12:00", 15).iloc[0]
    assert (r.current_available, r.current_age_seconds) == (11, 600)
    assert (r.available_lag_15min, r.available_lag_30min, r.available_lag_60min) == (11, 15, 20)
    assert (r.delta_15min, r.delta_60min) == (0, 11 - 20)
    # a lag with only delayed readings in its window is left empty; with no known current reading, no row
    only_late = [row + (late,) if row[1] != "2026-08-12T12:15" else row for row in base]
    assert at(run_pairs(tmp_path, only_late), "2026-08-12T12:00", 15).empty
    lag_empty = [row + (late,) if row[1] in ("2026-08-12T11:31",) else row for row in base]
    assert pd.isna(at(run_pairs(tmp_path, lag_empty), "2026-08-12T12:00", 15).iloc[0].available_lag_30min)
