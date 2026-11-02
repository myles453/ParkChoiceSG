"""Turn raw HDB carpark-availability snapshots into observations, then into training pairs.

Stage 1 (observations): ml/data/raw/hdb/YYYY-MM-DD/HHMM.json.gz -> ml/data/observations.parquet
                        (+ observations.manifest.json). first_seen_at is the earliest snapshot time
                        (from the file path) of any file containing the (carpark_id, observed_at) pair.
Stage 2 (pairs):        observations.parquet -> ml/data/pairs.parquet (+ pairs.manifest.json)

    python build_dataset.py                    # both stages
    python build_dataset.py --stage observations
    python build_dataset.py --stage pairs

Both stages rebuild their output from scratch, so rerunning on the complete download is safe.
All stored timestamps are UTC; Singapore time is used only for weekday / slot / holiday
features and for the split boundaries.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import sys
import zlib

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Read-only reuse of the data pipeline's parsing helpers (timestamp: naive -> Singapore time -> UTC;
# count: strict non-negative integer, rejects bool/float/negative/missing).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data-pipeline"))
from puller import count as parse_count  # noqa: E402
from puller import timestamp as parse_timestamp  # noqa: E402

ML_DIR = Path(__file__).resolve().parent
UTC = timezone.utc
SGT = timezone(timedelta(hours=8))
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
US = timedelta(microseconds=1)
MIN_US = 60 * 1_000_000
DAY_US = 86_400 * 1_000_000
SGT_OFFSET_US = 8 * 3600 * 1_000_000


def to_us(moment: datetime) -> int:
    return (moment - EPOCH) // US


def sgt_us(year, month, day, hour=0, minute=0) -> int:
    return to_us(datetime(year, month, day, hour, minute, tzinfo=SGT))


# ---------------------------------------------------------------------------------------------
# Project settings
# ---------------------------------------------------------------------------------------------
HORIZONS = (15, 30, 45, 60, 90)
DECISION_STEP_MIN = 15
MAX_CURRENT_AGE_US = 15 * MIN_US
LAG_TOLERANCE_US = 10 * MIN_US
LABEL_TOLERANCE_US = 5 * MIN_US
FUTURE_ALLOWANCE = timedelta(minutes=2)  # puller.normalize: source clock may lead query time by 2 min
SPLIT_NAMES = ("train", "validation", "test")

# 2026 Singapore public holidays (Singapore dates, in-lieu days included).
# Source: Ministry of Manpower public-holiday list, https://www.mom.gov.sg/employment-practices/public-holidays
# (cross-checked against https://www.malaymail.com/news/singapore/2025/06/16/mark-your-calendars-singaporeans-get-six-long-weekends-in-2026-for-travel-sleep-ins-or-just-escaping-the-boss/180547).
# Hari Raya Puasa and Hari Raya Haji were listed "subject to confirmation"; both fall outside the
# 2026-07-15..2026-10-07 data window, as does everything except National Day (+ in-lieu Monday).
PUBLIC_HOLIDAYS_2026 = frozenset(date(2026, m, d) for m, d in [
    (1, 1),              # New Year's Day
    (2, 17), (2, 18),    # Chinese New Year
    (3, 21),             # Hari Raya Puasa
    (4, 3),              # Good Friday
    (5, 1),              # Labour Day
    (5, 27),             # Hari Raya Haji
    (5, 31), (6, 1),     # Vesak Day (Sunday) + in lieu
    (8, 9), (8, 10),     # National Day (Sunday) + in lieu
    (11, 8), (11, 9),    # Deepavali (Sunday) + in lieu
    (12, 25),            # Christmas Day
])


@dataclass(frozen=True)
class Config:
    """Shared date range and chronological split rules (all boundaries are Singapore midnight)."""
    start_us: int = sgt_us(2026, 7, 15)           # first decision time, inclusive
    validation_start_us: int = sgt_us(2026, 9, 16)
    test_start_us: int = sgt_us(2026, 9, 27)
    end_us: int = sgt_us(2026, 10, 8)             # exclusive; last 5-minute stamp is 10-07 23:55
    holidays: frozenset = field(default_factory=lambda: PUBLIC_HOLIDAYS_2026)

    @property
    def edges(self) -> np.ndarray:
        return np.array([self.start_us, self.validation_start_us, self.test_start_us, self.end_us],
                        dtype=np.int64)

    def split_code(self, t_us: np.ndarray) -> np.ndarray:
        """0 train, 1 validation, 2 test, -1 outside the data range."""
        t_us = np.asarray(t_us, dtype=np.int64)
        code = np.searchsorted(self.edges, t_us, side="right") - 1
        code[(t_us < self.start_us) | (t_us >= self.end_us)] = -1
        return code

    def decision_grid(self) -> np.ndarray:
        return np.arange(self.start_us, self.end_us, DECISION_STEP_MIN * MIN_US, dtype=np.int64)


OBS_SCHEMA = pa.schema([
    ("carpark_id", pa.string()),
    ("observed_at", pa.timestamp("us", tz="UTC")),
    ("lots_available", pa.int32()),
    ("total_lots", pa.int32()),
    ("first_seen_at", pa.timestamp("us", tz="UTC")),  # earliest snapshot (file-path time) containing the pair
])

PAIR_SCHEMA = pa.schema([
    ("carpark_id", pa.string()),
    ("decision_at", pa.timestamp("us", tz="UTC")),
    ("arrival_at", pa.timestamp("us", tz="UTC")),
    ("split", pa.string()),
    ("horizon_minutes", pa.int16()),
    ("current_available", pa.int32()),
    ("current_total_lots", pa.int32()),
    ("current_free_ratio", pa.float32()),
    ("current_age_seconds", pa.int32()),
    ("available_lag_15min", pa.int32()),
    ("available_lag_30min", pa.int32()),
    ("available_lag_60min", pa.int32()),
    ("delta_15min", pa.int32()),
    ("delta_60min", pa.int32()),
    ("arrival_weekday", pa.int8()),
    ("arrival_slot_15min", pa.int8()),
    ("arrival_is_weekend", pa.bool_()),
    ("arrival_is_public_holiday", pa.bool_()),
    ("label_available", pa.int32()),
    ("label_free", pa.int8()),
    ("label_offset_seconds", pa.int32()),
])


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def atomic_write_json(path: Path, payload: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------------------------
# Stage 1: raw snapshots -> observations
# ---------------------------------------------------------------------------------------------
KNOWN_LOT_TYPES = {"C", "M", "H", "Y"}  # puller.normalize vocabulary; only "C" (car) is kept
CODE_PATTERN = re.compile(r"[A-Z0-9]+")


def file_time_from_path(path: Path) -> datetime | None:
    """Query time encoded in .../YYYY-MM-DD/HHMM.json.gz (Singapore time), as an aware datetime."""
    try:
        name = path.name.split(".")[0]
        return datetime.strptime(f"{path.parent.name} {name}", "%Y-%m-%d %H%M").replace(tzinfo=SGT)
    except ValueError:
        return None


def clean_snapshot(payload, query_time: datetime | None = None, rejected_by_carpark: Counter | None = None):
    """Apply puller.normalize's rules to one API response, keeping lot type "C" only.

    Returns (rows, rejected, excluded_non_car). rows are (carpark_id, observed_at_utc, available,
    total). Raises ValueError for a payload whose structure puller.normalize would also refuse;
    the caller then discards the whole file. Invalid entries are rejected, never repaired.
    If rejected_by_carpark is given it receives (reason, carpark_id) counts for lot-level rejections.
    """
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        raise ValueError("missing_items")
    rows, rejected, excluded = [], Counter(), 0
    for item in items:
        parks = item.get("carpark_data") if isinstance(item, dict) else None
        if not isinstance(parks, list) or not parks:
            raise ValueError("missing_carpark_data")
        for park in parks:
            try:
                code = park["carpark_number"].strip().upper()
                if not CODE_PATTERN.fullmatch(code):
                    raise ValueError("invalid_carpark_id")
                try:
                    observed = parse_timestamp(park["update_datetime"])
                except ValueError as exc:
                    raise ValueError("missing_timestamp" if str(exc) == "missing_timestamp"
                                     else "invalid_timestamp") from None
                if query_time is not None and observed > query_time + FUTURE_ALLOWANCE:
                    raise ValueError("future_source_timestamp")
                lots = park["carpark_info"]
                if not isinstance(lots, list) or not lots:
                    raise ValueError("missing_lot_records")
            except (KeyError, TypeError, AttributeError):
                rejected["missing_or_malformed_field"] += 1
                continue
            except ValueError as exc:
                rejected[str(exc)] += 1
                continue
            for lot in lots:
                try:
                    kind = lot["lot_type"].strip().upper()
                    if kind not in KNOWN_LOT_TYPES:
                        raise ValueError("unknown_lot_type")
                    if kind != "C":
                        excluded += 1
                        continue
                    available, total = parse_count(lot["lots_available"]), parse_count(lot["total_lots"])
                    if available > total:
                        raise ValueError("available_exceeds_total")
                    if total == 0:
                        raise ValueError("zero_capacity")
                    rows.append((code, observed, available, total))
                except (KeyError, TypeError, AttributeError):
                    rejected["missing_or_malformed_field"] += 1
                    if rejected_by_carpark is not None:
                        rejected_by_carpark[("missing_or_malformed_field", code)] += 1
                except ValueError as exc:
                    rejected[str(exc)] += 1
                    if rejected_by_carpark is not None:
                        rejected_by_carpark[(str(exc), code)] += 1
    return rows, rejected, excluded


def shard_of(carpark_id: str, shards: int) -> int:
    return zlib.crc32(carpark_id.encode()) % shards


PAIR_KEY = ["carpark_id", "observed_at", "lots_available", "total_lots"]


def collapse_duplicates(frame: pd.DataFrame) -> pd.DataFrame:
    """Merge identical readings, keeping the earliest first_seen_at."""
    return frame.groupby(PAIR_KEY, as_index=False, sort=False)["first_seen_at"].min()


def rows_to_frame(rows) -> pd.DataFrame:
    table = pa.table({
        "carpark_id": pa.array([r[0] for r in rows], type=pa.string()),
        "observed_at": pa.array([r[1] for r in rows], type=pa.timestamp("us", tz="UTC")),
        "lots_available": pa.array([r[2] for r in rows], type=pa.int32()),
        "total_lots": pa.array([r[3] for r in rows], type=pa.int32()),
        "first_seen_at": pa.array([r[4] for r in rows], type=pa.timestamp("us", tz="UTC")),
    })
    return table.to_pandas()


def build_observations(raw_dir: Path, out_path: Path, manifest_path: Path,
                       batch_files: int = 200, shards: int = 16) -> dict:
    """Read every raw file in batches, clean, then dedupe/conflict-check one hash shard at a time.

    A carpark always falls in the same shard, so a conflict between files from different batches
    is still found, and memory is bounded by one batch or one shard.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work = out_path.parent / "_observations_work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    files = sorted(raw_dir.rglob("*.json.gz")) if raw_dir.exists() else []
    stats = {"files_found": len(files), "files_read": 0, "files_rejected": Counter(),
             "unreadable_files_sample": [], "rejected_by_reason": Counter(),
             "excluded_non_car_lot_records": 0, "rows_accepted": 0,
             "rejected_by_carpark": Counter(), "files_with_rejection": Counter()}
    batch_rows, batch_no = [], 0
    after_batch_dedupe = 0

    def flush():
        nonlocal batch_rows, batch_no, after_batch_dedupe
        if not batch_rows:
            return
        frame = collapse_duplicates(rows_to_frame(batch_rows))
        after_batch_dedupe += len(frame)
        names = frame["carpark_id"].unique()
        mapping = {n: shard_of(n, shards) for n in names}
        frame["_shard"] = frame["carpark_id"].map(mapping)
        for shard, part in frame.groupby("_shard"):
            directory = work / f"shard={shard:03d}"
            directory.mkdir(exist_ok=True)
            pq.write_table(pa.Table.from_pandas(part.drop(columns="_shard"), schema=OBS_SCHEMA,
                                                preserve_index=False),
                           directory / f"batch-{batch_no:06d}.parquet")
        batch_no += 1
        batch_rows = []

    for number, path in enumerate(files, 1):
        try:
            with gzip.open(path, "rb") as stream:
                payload = json.loads(stream.read())
            query_time = file_time_from_path(path)
            if query_time is None:
                raise ValueError("unparseable_path_time")  # first_seen_at cannot be derived
            by_carpark = Counter()
            rows, rejected, excluded = clean_snapshot(payload, query_time, by_carpark)
        except ValueError as exc:  # includes json.JSONDecodeError and UnicodeDecodeError
            reason = str(exc) if str(exc) in ("missing_items", "missing_carpark_data",
                                              "unparseable_path_time") else "invalid_json"
            stats["files_rejected"][reason] += 1
            if len(stats["unreadable_files_sample"]) < 20:
                stats["unreadable_files_sample"].append(str(path.relative_to(raw_dir)))
            continue
        except (OSError, EOFError, zlib.error):
            stats["files_rejected"]["unreadable_gzip"] += 1
            if len(stats["unreadable_files_sample"]) < 20:
                stats["unreadable_files_sample"].append(str(path.relative_to(raw_dir)))
            continue
        stats["files_read"] += 1
        stats["rejected_by_reason"].update(rejected)
        stats["rejected_by_carpark"].update(by_carpark)
        stats["files_with_rejection"].update(by_carpark.keys())
        stats["excluded_non_car_lot_records"] += excluded
        stats["rows_accepted"] += len(rows)
        first_seen = query_time.astimezone(UTC)
        batch_rows.extend((c, o, av, tot, first_seen) for c, o, av, tot in rows)
        if number % batch_files == 0 or len(batch_rows) >= 2_000_000:
            flush()
        if number % 2000 == 0:
            log(f"stage 1: {number}/{len(files)} files")
    flush()

    tmp_out = out_path.with_name(out_path.name + ".tmp")
    writer = pq.ParquetWriter(tmp_out, OBS_SCHEMA, compression="zstd")
    after_global_dedupe = conflict_keys = final_rows = 0
    carparks, lo, hi = set(), None, None
    seen_delay = []
    for directory in sorted(work.glob("shard=*")):
        frame = collapse_duplicates(pd.read_parquet(directory))
        after_global_dedupe += len(frame)
        key = ["carpark_id", "observed_at"]
        clash = frame.duplicated(key, keep=False)  # same key, different counts (exact dupes are gone)
        conflict_keys += int(frame.loc[clash, key].drop_duplicates().shape[0])
        frame = frame.loc[~clash].sort_values(key, kind="stable")
        if len(frame):
            seen_delay.append(((frame["first_seen_at"] - frame["observed_at"]).dt.total_seconds()
                               .to_numpy(dtype=np.float32)))
            final_rows += len(frame)
            carparks.update(frame["carpark_id"].unique())
            lo = frame["observed_at"].min() if lo is None else min(lo, frame["observed_at"].min())
            hi = frame["observed_at"].max() if hi is None else max(hi, frame["observed_at"].max())
            writer.write_table(pa.Table.from_pandas(frame, schema=OBS_SCHEMA, preserve_index=False))
    writer.close()
    os.replace(tmp_out, out_path)
    shutil.rmtree(work, ignore_errors=True)
    delay = np.concatenate(seen_delay) if seen_delay else np.array([], dtype=np.float32)

    def delay_summary(values):
        if len(values) == 0:
            return {"count": 0, "median_seconds": None, "p90_seconds": None, "max_seconds": None}
        return {"count": int(len(values)), "median_seconds": float(np.median(values)),
                "p90_seconds": float(np.percentile(values, 90)), "max_seconds": float(values.max())}

    def sgt(ts):
        return None if ts is None else ts.tz_convert("Asia/Singapore").isoformat()

    manifest = {
        "raw_dir": str(raw_dir),
        "files_found": stats["files_found"],
        "files_read": stats["files_read"],
        "files_rejected": dict(stats["files_rejected"]),
        "unreadable_files_sample": stats["unreadable_files_sample"],
        "car_lot_rows_accepted": stats["rows_accepted"],
        "excluded_non_car_lot_records": stats["excluded_non_car_lot_records"],
        "rejected_by_reason": dict(stats["rejected_by_reason"]),
        "rejected_total": int(sum(stats["rejected_by_reason"].values())),
        "exact_duplicate_rows_removed": stats["rows_accepted"] - after_global_dedupe,
        "conflict_count": conflict_keys,
        "conflict_note": "keys (carpark_id, observed_at) seen with different counts; all their rows dropped",
        "rows": final_rows,
        "carpark_count": len(carparks),
        "observed_at_min_utc": None if lo is None else lo.isoformat(),
        "observed_at_max_utc": None if hi is None else hi.isoformat(),
        "observed_at_min_sgt": sgt(lo),
        "observed_at_max_sgt": sgt(hi),
        "first_seen_minus_observed_seconds": {
            "definition": "first_seen_at - observed_at, i.e. the reading's age when the earliest "
                          "snapshot containing it was queried; negative = source clock ahead of query time",
            "younger_than_15min": delay_summary(delay[delay < 15 * 60]),
            "all_rows": delay_summary(delay),
            "rows_15min_or_older": int((delay >= 15 * 60).sum()),
            "rows_negative": int((delay < 0).sum()),
        },
        "rejected_carparks_top": [
            {"reason": r, "carpark_id": c, "lot_records": n, "files": stats["files_with_rejection"][(r, c)]}
            for (r, c), n in stats["rejected_by_carpark"].most_common(20)],
        "reject_note": "rejected_by_reason counts carpark entries (record-level reasons) or lot "
                       "records (count/capacity reasons); non-car lot records are excluded, not rejected",
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


# ---------------------------------------------------------------------------------------------
# Stage 2: observations -> pairs
# ---------------------------------------------------------------------------------------------
def nearest_within(t: np.ndarray, target: np.ndarray, tolerance: int):
    """Index of the observation nearest to each target (earlier one wins ties) and a validity mask."""
    j = np.searchsorted(t, target, side="left")
    left = np.clip(j - 1, 0, len(t) - 1)
    right = np.clip(j, 0, len(t) - 1)
    d_left = np.abs(target - t[left])
    d_right = np.abs(t[right] - target)
    use_right = d_right < d_left
    best = np.where(use_right, right, left)
    return best, np.where(use_right, d_right, d_left) <= tolerance


def nearest_known(t, avail, d, target, tolerance):
    """Like nearest_within, but only among observations already known at decision time d.

    Fast path: the nearest observation overall. If that one was not yet known at d (avail > d),
    fall back to scanning the tolerance window for the nearest known one (rare).
    """
    best, ok = nearest_within(t, target, tolerance)
    bad = ok & (avail[best] > d)
    for i in np.flatnonzero(bad):
        lo = np.searchsorted(t, target[i] - tolerance, side="left")
        hi = np.searchsorted(t, target[i] + tolerance, side="right")
        cand = np.arange(lo, hi)
        cand = cand[avail[cand] <= d[i]]
        if len(cand) == 0:
            ok[i] = False
            continue
        dist = np.abs(t[cand] - target[i])
        best[i] = cand[np.argmin(dist)]  # argmin returns the earliest on ties
    return best, ok


def compute_features(t: np.ndarray, a: np.ndarray, n: np.ndarray, first_seen: np.ndarray,
                     decisions: np.ndarray):
    """Decision-time features for one carpark. t (observed_at) is sorted, unique epoch-microseconds.

    An observation may feed a feature only if it was known at the decision time: observed_at <=
    decision AND first_seen_at <= decision, i.e. max(observed_at, first_seen_at) <= decision.
    The current reading is the known observation with the greatest observed_at. Returns
    (keep, features) where keep masks `decisions` (a current reading exists and, by observed_at,
    is at most 15 minutes old).
    """
    avail = np.maximum(t, first_seen)
    order = np.argsort(avail, kind="stable")
    newest = np.maximum.accumulate(t[order])           # greatest observed_at among those known so far
    k = np.searchsorted(avail[order], decisions, side="right") - 1
    has = k >= 0
    idx = np.searchsorted(t, newest[np.maximum(k, 0)])  # position of that observation (t is unique)
    age = decisions - t[idx]
    keep = has & (age <= MAX_CURRENT_AGE_US)
    d, idx, age = decisions[keep], idx[keep], age[keep]
    feats = {"decision": d, "current_available": a[idx].astype(np.int64),
             "current_total_lots": n[idx].astype(np.int64), "current_age_seconds": age // 1_000_000}
    for lag in (15, 30, 60):
        best, ok = nearest_known(t, avail, d, d - lag * MIN_US, LAG_TOLERANCE_US)
        assert not (ok & (avail[best] > d)).any()  # causal guard
        feats[f"available_lag_{lag}min"] = (a[best].astype(np.int64), ok)
    return keep, feats


@dataclass
class PairStats:
    decisions_total: int = 0
    decisions_skipped_no_or_stale_current: int = 0
    candidates_no_label: int = 0
    candidates_crossing_split: int = 0
    rows: np.ndarray = field(default_factory=lambda: np.zeros((3, len(HORIZONS)), dtype=np.int64))
    not_free: np.ndarray = field(default_factory=lambda: np.zeros((3, len(HORIZONS)), dtype=np.int64))


def pairs_for_carpark(carpark_id: str, t, a, n, first_seen, decisions, cfg: Config, stats: PairStats):
    """All training rows for one carpark as a pyarrow Table (or None)."""
    stats.decisions_total += len(decisions)
    keep, f = compute_features(t, a, n, first_seen, decisions)
    stats.decisions_skipped_no_or_stale_current += int((~keep).sum())
    d = f["decision"]
    if len(d) == 0:
        return None
    nd, nh = len(d), len(HORIZONS)
    arrival = d[:, None] + np.array(HORIZONS, dtype=np.int64)[None, :] * MIN_US
    j = np.searchsorted(t, arrival.ravel(), side="left").reshape(nd, nh)  # first obs at/after arrival
    exists = j < len(t)
    jj = np.minimum(j, len(t) - 1)
    offset = t[jj] - arrival
    found = exists & (offset <= LABEL_TOLERANCE_US)
    sd = cfg.split_code(d)[:, None]
    same = (sd >= 0) & (sd == cfg.split_code(arrival.ravel()).reshape(nd, nh)) \
        & (sd == cfg.split_code(t[jj].ravel()).reshape(nd, nh))
    stats.candidates_no_label += int((~found).sum())
    stats.candidates_crossing_split += int((found & ~same).sum())
    mask = found & same
    k = int(mask.sum())
    if k == 0:
        return None

    def flat(values):  # per-decision column -> per-(decision, horizon) rows kept by mask
        return np.broadcast_to(values[:, None], (nd, nh))[mask]

    label = a[jj][mask].astype(np.int64)
    split_rows = np.broadcast_to(sd, (nd, nh))[mask]
    horizon_idx = np.broadcast_to(np.arange(nh)[None, :], (nd, nh))[mask]
    np.add.at(stats.rows, (split_rows, horizon_idx), 1)
    np.add.at(stats.not_free, (split_rows, horizon_idx), (label < 1).astype(np.int64))

    arr = arrival[mask]
    local = arr + SGT_OFFSET_US
    days = local // DAY_US
    weekday = (days + 3) % 7 + 1  # 1970-01-01 was a Thursday (ISO 4)
    holiday_days = np.array(sorted((h - date(1970, 1, 1)).days for h in cfg.holidays), dtype=np.int64)
    cur_av, cur_tot = flat(f["current_available"]), flat(f["current_total_lots"])

    def lag_column(name):
        values, ok = f[name]
        return pa.array(flat(values), type=pa.int32(), mask=~flat(ok))

    lag15, ok15 = f["available_lag_15min"]
    lag60, ok60 = f["available_lag_60min"]
    delta15 = pa.array(cur_av - flat(lag15), type=pa.int32(), mask=~flat(ok15))
    delta60 = pa.array(cur_av - flat(lag60), type=pa.int32(), mask=~flat(ok60))
    names = np.array(SPLIT_NAMES, dtype=object)
    table = pa.table({
        "carpark_id": pa.repeat(pa.scalar(carpark_id), k),
        "decision_at": pa.array(flat(d), type=PAIR_SCHEMA.field("decision_at").type),
        "arrival_at": pa.array(arr, type=PAIR_SCHEMA.field("arrival_at").type),
        "split": pa.array(names[split_rows], type=pa.string()),
        "horizon_minutes": pa.array(np.array(HORIZONS)[horizon_idx], type=pa.int16()),
        "current_available": pa.array(cur_av, type=pa.int32()),
        "current_total_lots": pa.array(cur_tot, type=pa.int32()),
        "current_free_ratio": pa.array(cur_av / cur_tot, type=pa.float32()),
        "current_age_seconds": pa.array(flat(f["current_age_seconds"]), type=pa.int32()),
        "available_lag_15min": lag_column("available_lag_15min"),
        "available_lag_30min": lag_column("available_lag_30min"),
        "available_lag_60min": lag_column("available_lag_60min"),
        "delta_15min": delta15,
        "delta_60min": delta60,
        "arrival_weekday": pa.array(weekday, type=pa.int8()),
        "arrival_slot_15min": pa.array((local % DAY_US) // (15 * MIN_US), type=pa.int8()),
        "arrival_is_weekend": pa.array(weekday >= 6, type=pa.bool_()),
        "arrival_is_public_holiday": pa.array(np.isin(days, holiday_days), type=pa.bool_()),
        "label_available": pa.array(label, type=pa.int32()),
        "label_free": pa.array((label >= 1).astype(np.int8), type=pa.int8()),
        "label_offset_seconds": pa.array(offset[mask] // 1_000_000, type=pa.int32()),
    }, schema=PAIR_SCHEMA)
    return table


def build_pairs(obs_path: Path, out_path: Path, manifest_path: Path, cfg: Config | None = None) -> dict:
    cfg = cfg or Config()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    table = pq.read_table(obs_path, columns=["carpark_id", "observed_at", "lots_available", "total_lots",
                                       "first_seen_at"])
    col = table["carpark_id"].combine_chunks().dictionary_encode()
    names = np.array(col.dictionary.to_pylist(), dtype=object)
    rank = np.argsort(np.argsort(names)) if len(names) else np.array([], dtype=np.int64)
    codes = rank[col.indices.to_numpy(zero_copy_only=False)] if len(names) else np.array([], dtype=np.int64)
    t = table["observed_at"].cast(pa.int64()).to_numpy()
    a = table["lots_available"].to_numpy()
    n = table["total_lots"].to_numpy()
    fs = table["first_seen_at"].cast(pa.int64()).to_numpy()
    del table, col
    order = np.lexsort((t, codes))
    t, a, n, fs, codes = t[order], a[order], n[order], fs[order], codes[order]
    del order
    sorted_names = np.sort(names)
    bounds = np.searchsorted(codes, np.arange(len(sorted_names) + 1))
    del codes

    decisions = cfg.decision_grid()
    stats = PairStats()
    tmp_out = out_path.with_name(out_path.name + ".tmp")
    writer = pq.ParquetWriter(tmp_out, PAIR_SCHEMA, compression="zstd")
    pending, pending_rows = [], 0
    for i, name in enumerate(sorted_names):
        lo, hi = bounds[i], bounds[i + 1]
        part = pairs_for_carpark(str(name), t[lo:hi], a[lo:hi], n[lo:hi], fs[lo:hi], decisions, cfg, stats)
        if part is not None:
            pending.append(part)
            pending_rows += part.num_rows
        if pending_rows >= 1_000_000:
            writer.write_table(pa.concat_tables(pending))
            pending, pending_rows = [], 0
        if (i + 1) % 200 == 0:
            log(f"stage 2: {i + 1}/{len(sorted_names)} carparks, {int(stats.rows.sum())} rows")
    if pending:
        writer.write_table(pa.concat_tables(pending))
    writer.close()
    os.replace(tmp_out, out_path)

    def share(zero, total):
        return None if total == 0 else round(float(zero) / float(total), 6)

    rows_split = stats.rows.sum(axis=1)
    zeros_split = stats.not_free.sum(axis=1)
    manifest = {
        "rows": int(stats.rows.sum()),
        "carpark_count": len(sorted_names),
        "horizons_minutes": list(HORIZONS),
        "rows_per_split": {s: int(rows_split[i]) for i, s in enumerate(SPLIT_NAMES)},
        "rows_per_horizon": {str(h): int(stats.rows[:, i].sum()) for i, h in enumerate(HORIZONS)},
        "label_free_0_share_overall": share(stats.not_free.sum(), stats.rows.sum()),
        "label_free_0_share_per_split": {s: share(zeros_split[i], rows_split[i])
                                         for i, s in enumerate(SPLIT_NAMES)},
        "rows_per_split_and_horizon": {s: {str(h): int(stats.rows[i, j]) for j, h in enumerate(HORIZONS)}
                                       for i, s in enumerate(SPLIT_NAMES)},
        "decisions_considered": stats.decisions_total,
        "decisions_skipped_no_or_stale_current": stats.decisions_skipped_no_or_stale_current,
        "candidates_dropped_no_label": stats.candidates_no_label,
        "candidates_dropped_crossing_split": stats.candidates_crossing_split,
        "split_rules": {
            "train": "decision 2026-07-15 00:00 .. 2026-09-15 23:59 SGT",
            "validation": "2026-09-16 .. 2026-09-26 SGT",
            "test": "2026-09-27 .. 2026-10-07 SGT",
            "purge": "a row is kept only if decision_at, arrival_at and the label observation's "
                     "observed_at fall in the same split",
        },
        "feature_rule": "features use only observations with observed_at <= decision_at AND "
                        "first_seen_at <= decision_at; labels are selected by observed_at only",
        "observations": str(obs_path),
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", choices=["observations", "pairs", "all"], default="all")
    parser.add_argument("--data-dir", type=Path, default=ML_DIR / "data")
    parser.add_argument("--batch-files", type=int, default=200, help="raw files per memory batch")
    args = parser.parse_args()
    data = args.data_dir
    if args.stage in ("observations", "all"):
        manifest = build_observations(data / "raw" / "hdb", data / "observations.parquet",
                                      data / "observations.manifest.json", batch_files=args.batch_files)
        print(json.dumps(manifest, indent=2))
    if args.stage in ("pairs", "all"):
        manifest = build_pairs(data / "observations.parquet", data / "pairs.parquet",
                               data / "pairs.manifest.json")
        print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
