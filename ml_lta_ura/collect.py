"""Collect one LTA and one URA carpark-availability capture every 5 minutes.

Raw captures: data/raw/<provider>/YYYY-MM-DD/HHMMSS.json.gz (name = Singapore
retrieval time; the exact UTC time is stored inside). Cycle log: data/raw/events.jsonl.

    python collect.py            run until stopped
    python collect.py --status   report captures per provider

Keys come from data-pipeline/.env via provider_puller. Nothing here logs a key.
"""
from __future__ import annotations

import argparse
import fcntl
import gzip
import json
import logging
import math
import os
import signal
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "data-pipeline"))
import provider_puller  # noqa: E402  (reused: env loading, requests, token, pagination)

SGT = timezone(timedelta(hours=8))
UTC = timezone.utc
INTERVAL = 300
RETRIES = 4  # retries after the first attempt
BACKOFF = (2, 4, 8, 16)
PROVIDERS = ("lta", "ura")
REQUIRED_KEYS = {"lta": "LTA_ACCOUNT_KEY", "ura": "URA_ACCESS_KEY"}
DEFAULT_DATA = ROOT / "data" / "raw"
log = logging.getLogger("collect")


# ---------------------------------------------------------------- scheduling
def next_slot(now: float, interval: int = INTERVAL) -> float:
    """First grid time at or after `now`. Missed slots are never made up."""
    return math.ceil(now / interval) * interval


def run_forever(run_cycle, clock=time.time, wait=None, stop: threading.Event | None = None,
                interval: int = INTERVAL):
    """Single-threaded loop: a cycle never overlaps the next, and an overrun skips slots."""
    stop = stop or threading.Event()
    wait = wait or stop.wait
    while not stop.is_set():
        slot = next_slot(clock(), interval)
        delay = slot - clock()
        if delay > 0:
            wait(delay)
            if stop.is_set():
                break
        run_cycle(slot)
        skipped = round((next_slot(clock(), interval) - slot) / interval) - 1
        if skipped > 0:
            log.warning("cycle overran: skipped %d slot(s)", skipped)


# ------------------------------------------------------------------ fetching
def _retryable(exc: Exception) -> bool:
    if isinstance(exc, HTTPError):
        return exc.code == 429 or exc.code >= 500
    return True


def with_retries(fn, sleep=time.sleep):
    """Return (result, attempts); raise the last error after 1 + RETRIES attempts."""
    for attempt in range(RETRIES + 1):
        try:
            return fn(), attempt + 1
        except Exception as exc:
            if attempt == RETRIES or not _retryable(exc):
                exc.attempts = attempt + 1  # type: ignore[attr-defined]
                raise
            sleep(BACKOFF[attempt])


def fetch(provider: str) -> list[tuple[dict, datetime]]:
    """All pages of the availability feed as (payload, retrieved_at). No URA details or rates."""
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        if provider == "lta":
            _, artifacts = provider_puller.collect_lta(directory)
        else:
            _, artifacts, _ = provider_puller.collect_ura(directory, include_rates=False)
        pages = []
        for art in artifacts:
            with gzip.open(art["path"], "rb") as f:
                pages.append((json.loads(f.read()), datetime.fromisoformat(art["retrieved_at"])))
    return pages


def row_count(provider: str, pages) -> int:
    key = "value" if provider == "lta" else "Result"
    return sum(len(p.get(key) or []) for p, _ in pages)


# ------------------------------------------------------------------- storage
def atomic_write_gz(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    try:
        with open(tmp, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
            gz.write(json.dumps(obj, separators=(",", ":")).encode())
            gz.flush()
            raw.flush()
            os.fsync(raw.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def capture_path(data_dir: Path, provider: str, retrieved: datetime) -> Path:
    local = retrieved.astimezone(SGT)
    return data_dir / provider / local.strftime("%Y-%m-%d") / (local.strftime("%H%M%S") + ".json.gz")


def append_event(data_dir: Path, event: dict) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    with open(data_dir / "events.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(event, separators=(",", ":")) + "\n")
        f.flush()
        os.fsync(f.fileno())


# --------------------------------------------------------------------- cycle
def run_provider(provider: str, slot: float, data_dir: Path, sleep=time.sleep) -> dict:
    started = time.monotonic()
    event = {"time": datetime.fromtimestamp(slot, UTC).isoformat(), "provider": provider}
    try:
        pages, attempts = with_retries(lambda: fetch(provider), sleep)
        retrieved = max(t for _, t in pages).astimezone(UTC)
        atomic_write_gz(capture_path(data_dir, provider, retrieved), {
            "schema": 1, "provider": provider, "retrieved_at_utc": retrieved.isoformat(),
            "slot_utc": event["time"],
            "pages": [{"retrieved_at_utc": t.astimezone(UTC).isoformat(), "payload": p} for p, t in pages]})
        event.update(status="ok", rows=row_count(provider, pages), attempts=attempts, error_type=None)
    except Exception as exc:  # one provider failing must not stop the other
        event.update(status="failed", rows=0, attempts=getattr(exc, "attempts", 1),
                     error_type=type(exc).__name__)
        if isinstance(exc, HTTPError):
            event["http_status"] = exc.code
    event["duration_s"] = round(time.monotonic() - started, 2)
    append_event(data_dir, event)
    log.info("%s %s rows=%s %.1fs %s", provider, event["status"], event["rows"],
             event["duration_s"], event["error_type"] or "")
    return event


def run_cycle(slot: float, data_dir: Path = DEFAULT_DATA, sleep=time.sleep) -> list[dict]:
    return [run_provider(p, slot, data_dir, sleep) for p in PROVIDERS]


# -------------------------------------------------------------------- status
def list_captures(data_dir: Path, provider: str) -> list[datetime]:
    times = []
    for f in (data_dir / provider).glob("*/*.json.gz"):
        try:
            local = datetime.strptime(f.parent.name + f.name[:6], "%Y-%m-%d%H%M%S")
        except ValueError:
            continue
        times.append(local.replace(tzinfo=SGT).astimezone(UTC))
    return sorted(times)


def status(data_dir: Path = DEFAULT_DATA, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    out = []
    for provider in PROVIDERS:
        times = list_captures(data_dir, provider)
        out.append(f"== {provider.upper()} ==")
        if not times:
            out.append("  no captures")
            continue
        first_slot = math.floor(times[0].timestamp() / INTERVAL) * INTERVAL
        expected = int((now.timestamp() - first_slot) // INTERVAL) + 1
        fmt = lambda t: t.astimezone(SGT).strftime("%Y-%m-%d %H:%M:%S SGT")
        out += [f"  first capture : {fmt(times[0])}", f"  last capture  : {fmt(times[-1])}",
                f"  saved         : {len(times)}", f"  expected      : {expected}",
                f"  percent saved : {100 * len(times) / expected:.1f}%"]
        gaps = sorted(((b - a, a, b) for a, b in zip(times, times[1:])), reverse=True)[:5]
        out.append("  5 longest gaps:" if gaps else "  gaps: none (single capture)")
        out += [f"    {str(g).split('.')[0]:>10}  {fmt(a)} -> {fmt(b)}" for g, a, b in gaps]
    return "\n".join(out)


# ---------------------------------------------------------------------- main
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--status", action="store_true", help="print capture statistics and exit")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--cycles", type=int, help="stop after this many cycles (default: run forever)")
    args = parser.parse_args(argv)
    if args.status:
        print(status(args.data_dir))
        return 0
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    try:
        provider_puller.load_local_env()
    except ValueError as exc:
        print(f"Cannot read data-pipeline/.env: {exc}", file=sys.stderr)
        return 2
    missing = [k for k in REQUIRED_KEYS.values() if not os.environ.get(k)]
    if missing:
        print(f"Missing in data-pipeline/.env: {', '.join(missing)}. Add the key(s); not collecting.", file=sys.stderr)
        return 2
    args.data_dir.mkdir(parents=True, exist_ok=True)
    lock = open(args.data_dir / ".collect.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Another collector is already running on this data directory.", file=sys.stderr)
        return 3
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    done = 0

    def cycle(slot):
        nonlocal done
        run_cycle(slot, args.data_dir)
        done += 1
        if args.cycles and done >= args.cycles:
            stop.set()

    log.info("collector started, data=%s", args.data_dir)
    run_forever(cycle, stop=stop)
    log.info("collector stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
