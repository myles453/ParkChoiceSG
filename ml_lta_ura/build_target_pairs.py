"""Steps 1-3 of the LTA/URA target test: freeze the file list, parse raw captures, build pairs.

    ../ml/.venv/bin/python build_target_pairs.py            # freeze (first run only), view, pairs
    ../ml/.venv/bin/python build_target_pairs.py --stage view|pairs

First run records the newest capture time in data/target_manifest.json together with the exact list of raw
files at that moment. Later runs reuse that list and ignore files written after it. Nothing is fitted here.
Outputs: data/target_view.parquet, data/target_pairs.parquet, data/target_summary.json,
data/target_status.txt (collect.py --status at freeze time).
"""
from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "data-pipeline"))
import build_retrieval_view as brv  # noqa: E402  (pair builder, horizons, label rule: reused, not copied)
from features import FEATURES_B, MIN_US  # noqa: E402
from provider_puller import normalize_pages  # noqa: E402

RAW = HERE / "data" / "raw"
DATA = HERE / "data"
MANIFEST = DATA / "target_manifest.json"
VIEW = DATA / "target_view.parquet"
PAIRS = DATA / "target_pairs.parquet"
SUMMARY = DATA / "target_summary.json"
STATUS_TXT = DATA / "target_status.txt"
SGT = timezone(timedelta(hours=8))
UTC = timezone.utc
FEEDS = {"lta": "lta_datamall", "ura": "ura_direct"}
PAGE_KEY = {"lta": "value", "ura": "Result"}

# Singapore Grand Prix road closures, Singapore time. Both edges are inclusive.
F1_START_US = int(datetime(2026, 10, 7, 0, 1, tzinfo=SGT).timestamp() * 1_000_000)
F1_END_US = int(datetime(2026, 10, 13, 5, 30, tzinfo=SGT).timestamp() * 1_000_000)


def log(msg: str) -> None:
    print(f"[target] {msg}", file=sys.stderr, flush=True)


def f1_tag(decision_us, arrival_us) -> np.ndarray:
    """True where the decision time or the arrival time lies in the F1 window (edges inclusive)."""
    d, a = np.asarray(decision_us, dtype=np.int64), np.asarray(arrival_us, dtype=np.int64)
    return ((d >= F1_START_US) & (d <= F1_END_US)) | ((a >= F1_START_US) & (a <= F1_END_US))


def file_time(path: Path) -> datetime:
    """Capture time from <provider>/YYYY-MM-DD/HHMMSS.json.gz (name is Singapore time)."""
    return datetime.strptime(path.parent.name + path.name[:6], "%Y-%m-%d%H%M%S").replace(tzinfo=SGT).astimezone(UTC)


def freeze() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    files = {p: sorted(RAW.joinpath(p).glob("*/*.json.gz")) for p in FEEDS}
    cutoff = max(file_time(f) for fs in files.values() for f in fs)
    status = subprocess.run([sys.executable, str(HERE / "collect.py"), "--status"], cwd=HERE,
                            capture_output=True, text=True, check=True).stdout
    DATA.mkdir(exist_ok=True)
    STATUS_TXT.write_text(status)
    manifest = {"cutoff_utc": cutoff.isoformat(),
                "frozen_at_utc": datetime.now(UTC).isoformat(),
                "files": {p: [str(f.relative_to(RAW)) for f in fs if file_time(f) <= cutoff] for p, fs in files.items()}}
    MANIFEST.write_text(json.dumps(manifest, indent=1))
    return manifest


# ------------------------------------------------------------------------------------------ step 2
def select_rows(rows: list[dict], provider: str) -> list[dict]:
    """Car lots only. From the LTA feed only agency LTA (its HDB and URA rows copy other agencies' carparks)."""
    keep = [r for r in rows if r["lot_type"] == "C"]
    if provider == "lta":
        keep = [r for r in keep if r["agency"] == "LTA"]
    return keep


def is_target_record(record, provider: str) -> bool:
    """Whether a rejected raw record would have been a target row (car lot, agency LTA in the LTA feed)."""
    if not isinstance(record, dict):
        return False
    try:
        if provider == "lta":
            return (str(record.get("Agency")).strip().upper() == "LTA"
                    and str(record.get("LotType")).strip().upper() == "C")
        return str(record.get("lotType")).strip().upper() == "C"
    except Exception:
        return False


def parse_file(args):
    provider, rel = args
    try:
        with gzip.open(RAW / rel, "rb") as stream:
            doc = json.loads(stream.read())
        seen = datetime.fromisoformat(doc["retrieved_at_utc"])
        pages = [(p["payload"][PAGE_KEY[provider]], datetime.fromisoformat(p["retrieved_at_utc"])) for p in doc["pages"]]
        rows, rejected = normalize_pages(pages, FEEDS[provider])
    except Exception as exc:  # unreadable file: counted, never repaired
        return provider, rel, f"unreadable:{type(exc).__name__}", [], Counter(), Counter(), Counter()
    kept = select_rows(rows, provider)
    out = [(r["agency"], r["carpark_id"], int(seen.timestamp() * 1_000_000), r["lots_available"]) for r in kept]
    all_rej, target_rej = Counter(), Counter()
    for rej in rejected:
        all_rej[rej["reason"]] += 1
        if is_target_record(rej["record"], provider):
            target_rej[rej["reason"]] += 1
    kept_ids = {id(r) for r in kept}
    dropped = Counter(f"{r['agency']}/{r['lot_type']}" for r in rows if id(r) not in kept_ids)
    return provider, rel, "ok", out, all_rej, target_rej, dropped


def build_view(manifest: dict, workers: int = 8) -> dict:
    jobs = [(p, rel) for p, rels in manifest["files"].items() for rel in rels]
    rows, statuses = [], Counter()
    rej_all, rej_target, excluded = {p: Counter() for p in FEEDS}, {p: Counter() for p in FEEDS}, {p: Counter() for p in FEEDS}
    with Pool(workers) as pool:
        for n, (provider, rel, status, out, ra, rt, ex) in enumerate(pool.imap(parse_file, jobs, chunksize=20), 1):
            statuses[(provider, status)] += 1
            rows.extend(out)
            rej_all[provider].update(ra)
            rej_target[provider].update(rt)
            excluded[provider].update(ex)
            if n % 1000 == 0:
                log(f"parsed {n}/{len(jobs)} files")
    frame = pd.DataFrame(rows, columns=["agency", "carpark_id", "seen_us", "lots_available"])
    dupes = int(frame.duplicated(["agency", "carpark_id", "seen_us"]).sum())
    frame = frame.drop_duplicates(["agency", "carpark_id", "seen_us"]).sort_values(["agency", "carpark_id", "seen_us"])
    table = pa.table({"agency": pa.array(frame["agency"], pa.string()), "carpark_id": pa.array(frame["carpark_id"], pa.string()),
                      "seen_at": pa.array(frame["seen_us"].to_numpy(), pa.timestamp("us", tz="UTC")),
                      "lots_available": pa.array(frame["lots_available"].to_numpy(), pa.int32())})
    pq.write_table(table, VIEW, compression="zstd")
    per_capture = frame.groupby(["agency", "seen_us"]).size().groupby("agency").agg(["min", "median", "max", "count"])
    g = frame.groupby(["agency", "carpark_id"])["lots_available"]
    stats = g.agg(["nunique", "count", "min", "max"]).reset_index()
    constant = stats[stats["nunique"] == 1]
    summary = {"files": {f"{p}:{s}": n for (p, s), n in statuses.items()}, "rows": len(frame), "duplicate_rows_removed": dupes,
               "carparks": {a: int(n) for a, n in frame.groupby("agency")["carpark_id"].nunique().items()},
               "rows_per_capture": {a: {k: float(v) for k, v in r.items()} for a, r in per_capture.iterrows()},
               "rejections_all_rows": {p: dict(c) for p, c in rej_all.items()},
               "rejections_target_rows": {p: dict(c) for p, c in rej_target.items()},
               "excluded_by_filter": {p: dict(c) for p, c in excluded.items()},
               "constant_carparks": [{"agency": r.agency, "carpark_id": r.carpark_id, "value": int(r["min"]), "readings": int(r["count"])}
                                     for _, r in constant.iterrows()]}
    SUMMARY.write_text(json.dumps(summary, indent=1))
    return summary


# ------------------------------------------------------------------------------------------ step 3
def build_pairs() -> dict:
    """Pairs through build_retrieval_view.pairs_for_carpark (same grid, horizons, tolerances, label rule).

    That function reads its time range and split boundaries from module globals. They are set here so that the
    whole collection is one range and nothing is split; the function itself is untouched. Every pair is test data.
    """
    pf = pq.read_table(VIEW).to_pandas()
    pf["seen_us"] = pf["seen_at"].dt.as_unit("us").astype("int64")
    first, last = int(pf["seen_us"].min()), int(pf["seen_us"].max())
    step = 15 * MIN_US
    far = int(datetime(2100, 1, 1, tzinfo=UTC).timestamp() * 1_000_000)
    brv.TRAIN_START, brv.LAST_DECISION = first // step * step, last // step * step
    brv.VALID_START = brv.TEST_START = far
    parts = []
    for (agency, cid), grp in pf.groupby(["agency", "carpark_id"], sort=True):
        p = brv.pairs_for_carpark(cid, grp["seen_us"].to_numpy(), grp["lots_available"].to_numpy())
        if len(p):
            p.insert(0, "agency", agency)
            parts.append(p)
    frame = pd.concat(parts, ignore_index=True).drop(columns=["split", "sample_hash"])
    dec = frame["decision_at"].dt.as_unit("us").astype("int64").to_numpy()
    arr = frame["arrival_at"].dt.as_unit("us").astype("int64").to_numpy()
    frame["period"] = np.where(f1_tag(dec, arr), "f1", "normal")
    cols = ["agency", "carpark_id", "decision_at", "arrival_at", "period", "label_free", *FEATURES_B]
    frame[cols].to_parquet(PAIRS, index=False, compression="zstd")
    manifest = {"rows": len(frame), "horizons": list(brv.HORIZONS), "label_tolerance_min": brv.LABEL_TOLERANCE_US // MIN_US,
                "first_decision": str(pd.to_datetime(brv.TRAIN_START, unit="us", utc=True)),
                "last_decision": str(pd.to_datetime(brv.LAST_DECISION, unit="us", utc=True))}
    (DATA / "target_pairs.manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["view", "pairs", "both"], default="both")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    man = freeze()
    log(f"cutoff {man['cutoff_utc']}; files " + ", ".join(f"{p}={len(v)}" for p, v in man["files"].items()))
    if args.stage in ("view", "both"):
        s = build_view(man, args.workers)
        log(json.dumps({k: s[k] for k in ("files", "rows", "carparks", "rows_per_capture")}, indent=1))
    if args.stage in ("pairs", "both"):
        log(json.dumps(build_pairs(), indent=1))
