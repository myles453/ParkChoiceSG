"""Backfill HDB carpark-availability snapshots, one raw file per timestamp (Singapore time).

Files land at <output>/YYYY-MM-DD/HHMM.json.gz and hold the unmodified API response.
Resumable: a timestamp is skipped when its file already is valid gzip containing valid JSON.

    python backfill_hdb.py --start 2026-10-06T00:00 --end 2026-10-07T23:55
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import gzip
import json
import os
from pathlib import Path
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data-pipeline"))
from puller import LIVE_URL, SGT  # noqa: E402  (read-only reuse of the pipeline's constants)

MAX_ATTEMPTS = 6
RETRYABLE = (429, 500, 502, 503, 504)
PROGRESS_EVERY = 200
MAX_TIMESTAMP_DRIFT = timedelta(minutes=15)  # same freshness bound as puller.normalize


def parse_sgt(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    return result.replace(tzinfo=SGT) if result.tzinfo is None else result.astimezone(SGT)


def fetch(when: datetime) -> bytes:
    """Same request approach as puller.get_json, with 6 attempts and exponential backoff."""
    url = LIVE_URL + "?" + urlencode({"date_time": when.isoformat()})
    headers = {"Accept": "application/json", "User-Agent": "ParkChoiceSG-ml-backfill"}
    for attempt in range(MAX_ATTEMPTS):
        try:
            with urlopen(Request(url, headers=headers), timeout=30) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code not in RETRYABLE or attempt == MAX_ATTEMPTS - 1:
                raise
            retry_after = exc.headers.get("Retry-After", "")
            delay = min(int(retry_after), 60) if retry_after.isdigit() else 2 ** (attempt + 1)
        except (URLError, TimeoutError, ConnectionError):
            if attempt == MAX_ATTEMPTS - 1:
                raise
            delay = 2 ** (attempt + 1)
        time.sleep(delay)
    raise RuntimeError("request_failed")


def has_carparks(payload) -> bool:
    items = payload.get("items") if isinstance(payload, dict) else None
    return isinstance(items, list) and any(
        isinstance(i, dict) and isinstance(i.get("carpark_data"), list) and i["carpark_data"] for i in items)


def timestamp_drift(payload, when: datetime) -> timedelta:
    """Gap between the requested time and the snapshot time the API reports.

    For times not yet reached the API silently returns the *current* snapshot, so a
    response far from the requested time must not be filed under that time.
    """
    stamps = [datetime.fromisoformat(i["timestamp"]) for i in payload["items"] if i.get("timestamp")]
    return abs(max(stamps) - when) if stamps else timedelta.max


def valid_file(path: Path) -> bool:
    try:
        with gzip.open(path, "rb") as stream:
            json.load(stream)
        return True
    except (OSError, EOFError, ValueError):
        return False


def snapshot_path(output: Path, when: datetime) -> Path:
    return output / when.strftime("%Y-%m-%d") / when.strftime("%H%M.json.gz")


class Backfill:
    def __init__(self, output: Path, total: int):
        self.output, self.total = output, total
        self.lock = threading.Lock()
        self.saved = self.skipped = self.failed = self.empty = self.requests = 0
        self.started = time.monotonic()

    def record(self, name: str, when: datetime, **detail):
        line = json.dumps({"timestamp": when.isoformat(), **detail})
        with self.lock, (self.output / name).open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    def process(self, when: datetime):
        path = snapshot_path(self.output, when)
        outcome = "skipped"
        if not (path.exists() and valid_file(path)):
            try:
                if when > datetime.now(SGT):
                    raise ValueError("future_timestamp: the API would return the current snapshot")
                raw = fetch(when)
                with self.lock:
                    self.requests += 1
                payload = json.loads(raw)
                if not has_carparks(payload):
                    outcome = "empty"
                    self.record("empty.jsonl", when)
                elif timestamp_drift(payload, when) > MAX_TIMESTAMP_DRIFT:
                    outcome = "failed"
                    self.record("failed.jsonl", when, error="timestamp_mismatch",
                                detail=f"response timestamp {payload['items'][0].get('timestamp')}")
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
                    tmp.write_bytes(gzip.compress(raw))
                    os.replace(tmp, path)
                    outcome = "saved"
            except Exception as exc:  # persistent failure: record and keep going
                outcome = "failed"
                self.record("failed.jsonl", when, error=type(exc).__name__, detail=str(exc)[:200])
        with self.lock:
            setattr(self, outcome, getattr(self, outcome) + 1)
            done = self.saved + self.skipped + self.failed + self.empty
            if done % PROGRESS_EVERY == 0 or done == self.total:
                rate = self.requests / max(time.monotonic() - self.started, 1e-9)
                print(f"done={done} remaining={self.total - done} saved={self.saved} "
                      f"skipped={self.skipped} failed={self.failed} empty={self.empty} "
                      f"req/s={rate:.2f}", flush=True)


def main():
    default_output = Path(__file__).resolve().parent / "data" / "raw" / "hdb"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="Singapore time, e.g. 2026-10-06T00:00")
    parser.add_argument("--end", required=True, help="Singapore time, inclusive")
    parser.add_argument("--step-minutes", type=int, default=5)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=default_output)
    args = parser.parse_args()
    start, end = parse_sgt(args.start), parse_sgt(args.end)
    if end < start or args.step_minutes < 1 or args.workers < 1:
        parser.error("need start <= end, --step-minutes >= 1, --workers >= 1")
    step = timedelta(minutes=args.step_minutes)
    times = [start + i * step for i in range(int((end - start) / step) + 1)]
    args.output.mkdir(parents=True, exist_ok=True)
    job = Backfill(args.output, len(times))
    print(f"{len(times)} timestamps, {start.isoformat()} .. {times[-1].isoformat()}, "
          f"workers={args.workers}", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(job.process, times))
    elapsed = time.monotonic() - job.started
    print(f"finished in {elapsed:.0f}s: saved={job.saved} skipped={job.skipped} "
          f"failed={job.failed} empty={job.empty}")


if __name__ == "__main__":
    main()
