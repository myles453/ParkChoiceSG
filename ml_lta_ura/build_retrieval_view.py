"""Steps 1 and 3: HDB raw snapshots -> a view that looks like an LTA/URA feed.

    ../ml/.venv/bin/python build_retrieval_view.py              # both stages
    ../ml/.venv/bin/python build_retrieval_view.py --stage view   # step 1 only
    ../ml/.venv/bin/python build_retrieval_view.py --stage pairs  # step 3: data/hdb_pairs.parquet

For every snapshot file the car-lot count of each carpark is kept as that snapshot showed it, with
seen_at = snapshot time from the file path. The provider's update time is used once, to drop readings
more than 15 minutes older than the snapshot (frozen carparks), and is then discarded. total_lots is
discarded. Output: data/hdb_view.parquet (agency, carpark_id, seen_at, lots_available), sorted by
(carpark_id, seen_at), one row group per hash shard so no carpark spans two row groups.
"""
from __future__ import annotations

import argparse
import gzip
import json
import shutil
import sys
import zlib
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
ML_DIR = HERE.parent / "ml"
sys.path.insert(0, str(HERE))
sys.path.append(str(ML_DIR))
from build_dataset import clean_snapshot, file_time_from_path  # noqa: E402

RAW_DIR = ML_DIR / "data" / "raw" / "hdb"
OUT = HERE / "data" / "hdb_view.parquet"
MAX_READING_AGE_US = 15 * 60 * 1_000_000
SHARDS = 16
SCHEMA = pa.schema([
    ("agency", pa.string()),
    ("carpark_id", pa.string()),
    ("seen_at", pa.timestamp("us", tz="UTC")),
    ("lots_available", pa.int32()),
])


def log(msg: str) -> None:
    print(f"[view] {msg}", file=sys.stderr, flush=True)


def process_file(path: Path):
    """Return (status, rows, stats). rows are (carpark_id, seen_at_us, lots_available)."""
    try:
        with gzip.open(path, "rb") as stream:
            payload = json.loads(stream.read())
        snap = file_time_from_path(path)
        if snap is None:
            return "unparseable_path_time", [], {}
        rows, _, _ = clean_snapshot(payload, snap)
    except Exception as exc:  # unreadable file: skipped and counted, never repaired
        return f"unreadable:{type(exc).__name__}", [], {}
    snap_us = int(snap.timestamp() * 1_000_000)
    stats = Counter()
    by_code: dict[str, set] = {}
    for code, observed, available, _total in rows:
        observed_us = int(observed.timestamp() * 1_000_000)
        if snap_us - observed_us > MAX_READING_AGE_US:
            stats["dropped_stale_reading"] += 1
            continue
        by_code.setdefault(code, set()).add(available)
    out = []
    for code, counts in by_code.items():
        if len(counts) > 1:  # two different counts in one snapshot: ambiguous, drop
            stats["dropped_conflict_in_snapshot"] += 1
            continue
        out.append((code, snap_us, next(iter(counts))))
    stats["kept"] = len(out)
    return "ok", out, stats


def build(raw_dir: Path, out_path: Path, workers: int) -> dict:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work = out_path.parent / "_view_work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    files = sorted(raw_dir.rglob("*.json.gz"))
    totals, statuses = Counter(), Counter()
    batch, batch_no = [], 0

    def flush():
        nonlocal batch, batch_no
        if not batch:
            return
        frame = pd.DataFrame(batch, columns=["carpark_id", "seen_us", "lots_available"])
        frame["_shard"] = frame["carpark_id"].map(
            {c: zlib.crc32(c.encode()) % SHARDS for c in frame["carpark_id"].unique()})
        for shard, part in frame.groupby("_shard"):
            d = work / f"shard={shard:03d}"
            d.mkdir(exist_ok=True)
            part.drop(columns="_shard").to_parquet(d / f"b{batch_no:05d}.parquet", index=False)
        batch, batch_no = [], batch_no + 1

    with Pool(workers) as pool:
        for n, (status, rows, stats) in enumerate(pool.imap(process_file, files, chunksize=20), 1):
            statuses[status] += 1
            totals.update(stats)
            batch.extend(rows)
            if len(batch) >= 2_000_000:
                flush()
            if n % 4000 == 0:
                log(f"{n}/{len(files)} files")
    flush()

    tmp = out_path.with_name(out_path.name + ".tmp")
    writer = pq.ParquetWriter(tmp, SCHEMA, compression="zstd")
    final_rows, carparks, dupes = 0, set(), 0
    for d in sorted(work.glob("shard=*")):
        frame = pd.read_parquet(d)
        before = len(frame)
        frame = frame.drop_duplicates(["carpark_id", "seen_us"]).sort_values(["carpark_id", "seen_us"])
        dupes += before - len(frame)  # same file read twice would be the only cause; expected 0
        assert not (carparks & set(frame["carpark_id"].unique())), "carpark spans shards"
        carparks.update(frame["carpark_id"].unique())
        table = pa.table({
            "agency": pa.array(["HDB"] * len(frame), pa.string()),
            "carpark_id": pa.array(frame["carpark_id"], pa.string()),
            "seen_at": pa.array(frame["seen_us"].to_numpy(), pa.timestamp("us", tz="UTC")),
            "lots_available": pa.array(frame["lots_available"].to_numpy(), pa.int32()),
        })
        writer.write_table(table, row_group_size=len(frame) + 1)  # exactly one row group per shard
        final_rows += len(frame)
    writer.close()
    tmp.replace(out_path)
    shutil.rmtree(work, ignore_errors=True)
    manifest = {"files_found": len(files), "file_statuses": dict(statuses), "rows": final_rows,
                "carparks": len(carparks), "duplicate_rows_removed": dupes,
                "dropped_stale_reading": totals["dropped_stale_reading"],
                "dropped_conflict_in_snapshot": totals["dropped_conflict_in_snapshot"]}
    (out_path.parent / "hdb_view.manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


# ---------------------------------------------------------------------------------------------
# Step 3: pairs
# ---------------------------------------------------------------------------------------------
from datetime import datetime, timedelta, timezone  # noqa: E402

import numpy as np  # noqa: E402

from features import FEATURES_B, MIN_US, compute_features  # noqa: E402

PAIRS_OUT = HERE / "data" / "hdb_pairs.parquet"
HORIZONS = (15, 30, 45, 60, 90)
SGT = timezone(timedelta(hours=8))
LABEL_TOLERANCE_US = 6 * MIN_US


def sgt_us(y, m, d, hh=0, mm=0) -> int:
    return int(datetime(y, m, d, hh, mm, tzinfo=SGT).timestamp() * 1_000_000)


TRAIN_START = sgt_us(2026, 7, 15)
VALID_START = sgt_us(2026, 9, 16)
TEST_START = sgt_us(2026, 9, 27)
LAST_DECISION = sgt_us(2026, 10, 7, 14, 30)  # inclusive
SPLIT_NAMES = ("train", "validation", "test")
PAIR_COLUMNS = ["carpark_id", "decision_at", "arrival_at", "split", "label_free", "sample_hash"] + FEATURES_B


def split_code(t_us: np.ndarray) -> np.ndarray:
    """0 train, 1 validation, 2 test (open-ended), -1 before the data range."""
    return np.searchsorted([TRAIN_START, VALID_START, TEST_START], t_us, side="right") - 1


def uniform_hash32(carpark_id: str, decision_us: np.ndarray, hz_index: np.ndarray) -> np.ndarray:
    """Deterministic uniform uint32 per (carpark, decision, horizon); uses no label. splitmix64 finaliser."""
    x = (np.uint64(zlib.crc32(carpark_id.encode())) << np.uint64(40)) ^ \
        (decision_us // MIN_US).astype(np.uint64) * np.uint64(8) ^ hz_index.astype(np.uint64)
    with np.errstate(over="ignore"):
        x = x + np.uint64(0x9E3779B97F4A7C15)
        x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        x = x ^ (x >> np.uint64(31))
    return (x >> np.uint64(32)).astype(np.uint32)


def pairs_for_carpark(carpark_id: str, seen: np.ndarray, lots: np.ndarray) -> pd.DataFrame:
    grid = np.arange(TRAIN_START, LAST_DECISION + 1, 15 * MIN_US, dtype=np.int64)
    feats = compute_features(seen, lots, grid, HORIZONS, variant_b=True)
    if feats.empty:
        return feats.assign(carpark_id=[])
    dec = feats["decision_us"].to_numpy()
    hz = feats["horizon_minutes"].to_numpy().astype(np.int64)
    arrival = dec + hz * MIN_US
    j = np.searchsorted(seen, arrival, side="left")  # first row at or after arrival
    jc = np.minimum(j, len(seen) - 1)
    has = (j < len(seen)) & (seen[jc] - arrival <= LABEL_TOLERANCE_US)
    label_seen = seen[jc]
    d_split = split_code(dec)
    keep = has & (d_split == split_code(arrival)) & (d_split == split_code(label_seen))
    feats = feats.loc[keep].reset_index(drop=True)
    dec, arrival, d_split = dec[keep], arrival[keep], d_split[keep]
    out = feats.drop(columns=["decision_us"])
    hz_index = np.searchsorted(HORIZONS, hz[keep])
    out.insert(0, "carpark_id", carpark_id)
    out.insert(1, "decision_at", pd.to_datetime(dec, unit="us", utc=True))
    out.insert(2, "arrival_at", pd.to_datetime(arrival, unit="us", utc=True))
    out.insert(3, "split", d_split.astype(np.int8))
    out.insert(4, "label_free", (lots[jc[keep]] >= 1).astype(np.int8))
    out.insert(5, "sample_hash", uniform_hash32(carpark_id, dec, hz_index))
    return out


def build_pairs(view_path: Path = OUT, out_path: Path = PAIRS_OUT) -> dict:
    pf = pq.ParquetFile(view_path)
    tmp = out_path.with_name(out_path.name + ".tmp")
    writer, rows, per_split = None, 0, Counter()
    seen_carparks: set = set()
    for g in range(pf.num_row_groups):
        t = pf.read_row_group(g, columns=["carpark_id", "seen_at", "lots_available"]).to_pandas()
        t["seen_us"] = t["seen_at"].dt.as_unit("us").astype("int64")
        ids = t["carpark_id"].to_numpy()
        starts = np.flatnonzero(np.r_[True, ids[1:] != ids[:-1]])
        ends = np.r_[starts[1:], len(ids)]
        parts = []
        for a, b in zip(starts, ends):
            cid = ids[a]
            assert cid not in seen_carparks, "carpark spans row groups"
            seen_carparks.add(cid)
            parts.append(pairs_for_carpark(cid, t["seen_us"].to_numpy()[a:b], t["lots_available"].to_numpy()[a:b]))
        frame = pd.concat([p for p in parts if len(p)], ignore_index=True)
        table = pa.Table.from_pandas(frame, preserve_index=False)
        writer = writer or pq.ParquetWriter(tmp, table.schema, compression="zstd")
        writer.write_table(table, row_group_size=1_000_000)
        rows += len(frame)
        for k, v in frame.groupby("split").size().items():
            per_split[SPLIT_NAMES[k]] += int(v)
        log(f"pairs: row group {g + 1}/{pf.num_row_groups}, {rows:,} rows")
        del t, parts, frame, table
    writer.close()
    tmp.replace(out_path)
    manifest = {"rows": rows, "rows_per_split": dict(per_split), "carparks": len(seen_carparks)}
    (out_path.parent / "hdb_pairs.manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["view", "pairs", "both"], default="both")
    ap.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    if args.stage in ("view", "both"):
        log(json.dumps(build(args.raw_dir, args.out, args.workers), indent=2))
    if args.stage in ("pairs", "both"):
        log(json.dumps(build_pairs(args.out), indent=2))
