"""Live HDB availability feed: 60 s cache, 5 s timeout, 75 minute in-memory history, warm-up."""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from .features import FUTURE_ALLOWANCE, SGT
from build_dataset import clean_snapshot

LIVE_URL = "https://api.data.gov.sg/v1/transport/carpark-availability"
CACHE_SECONDS = 60
TIMEOUT_SECONDS = 5
HISTORY_WINDOW = timedelta(minutes=75)
WARMUP_MINUTES = (15, 30, 45, 60, 75)

log = logging.getLogger(__name__)


class FeedError(Exception):
    pass


@dataclass(frozen=True)
class Reading:
    observed_at: datetime  # UTC
    lots_available: int
    total_lots: int


def _http_fetch(date_time: datetime | None = None) -> dict:
    params = {"date_time": date_time.astimezone(SGT).isoformat(timespec="seconds")} if date_time else None
    resp = httpx.get(LIVE_URL, params=params, timeout=TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()


def parse_payload(payload: dict, query_time: datetime | None = None) -> dict[str, Reading]:
    """Car-lot readings by carpark, cleaned by build_dataset.clean_snapshot (same rules as training:
    zero capacity, available > total, future timestamps and bad counts are rejected, not repaired).
    A carpark reported twice with different counts is dropped."""
    try:
        rows, _, _ = clean_snapshot(payload, query_time)
    except ValueError as exc:
        raise FeedError(f"unexpected live payload: {exc}") from exc
    seen: dict[str, set] = defaultdict(set)
    for code, observed, avail, total in rows:
        seen[code].add((observed, avail, total))
    return {c: Reading(*v) for c, (v,) in ((c, tuple(s)) for c, s in seen.items() if len(s) == 1)}


class LiveFeed:
    def __init__(self, fetch_fn=None, clock=None, monotonic=None):
        self._fetch = fetch_fn or _http_fetch
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._mono = monotonic or time.monotonic
        self._lock = threading.Lock()
        self._cached: dict[str, Reading] | None = None
        self._cached_at = 0.0
        self._history: dict[str, dict[datetime, int]] = defaultdict(dict)
        self.fetch_count = 0

    def _load(self, date_time: datetime | None) -> dict[str, Reading]:
        self.fetch_count += 1
        try:
            readings = parse_payload(self._fetch(date_time),
                                     date_time or self.clock())
        except FeedError:
            raise
        except Exception as exc:
            raise FeedError(f"{type(exc).__name__}: {exc}") from exc
        if not readings:
            raise FeedError("live feed returned no usable readings")
        self._remember(readings)
        return readings

    def current(self) -> dict[str, Reading]:
        """Latest readings (cached 60 s); raises FeedError if the feed cannot be reached or parsed."""
        with self._lock:
            if self._cached is not None and self._mono() - self._cached_at < CACHE_SECONDS:
                return self._cached
            return self._refresh_locked()

    def refresh(self) -> dict[str, Reading]:
        """Fetch now, ignoring the cache (used by the background poller)."""
        with self._lock:
            return self._refresh_locked()

    def _refresh_locked(self) -> dict[str, Reading]:
        readings = self._load(None)
        self._cached, self._cached_at = readings, self._mono()
        return readings

    def warm_up(self) -> int:
        """Fill the history from snapshots 15..75 minutes ago. A failed call is logged and skipped."""
        done = 0
        for minutes in WARMUP_MINUTES:
            when = self.clock() - timedelta(minutes=minutes)
            try:
                with self._lock:
                    self._load(when)
                done += 1
            except Exception as exc:
                log.warning("history warm-up call for %d minutes ago failed: %s", minutes, exc)
        log.info("history warm-up finished: %d of %d calls succeeded", done, len(WARMUP_MINUTES))
        return done

    def _remember(self, readings: dict[str, Reading]) -> None:
        now = self.clock()
        horizon = now - HISTORY_WINDOW
        for cid, r in readings.items():
            if r.observed_at > now + FUTURE_ALLOWANCE or r.observed_at < horizon:
                continue  # source clock ahead of ours (not causal) or older than the window
            h = self._history[cid]
            h[r.observed_at] = r.lots_available
            for at in [a for a in h if a < horizon]:
                del h[at]

    def history(self, carpark_id: str) -> list[tuple[datetime, int]]:
        with self._lock:
            return sorted(self._history.get(carpark_id, {}).items())
