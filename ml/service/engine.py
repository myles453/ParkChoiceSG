"""Forecast logic: short mode (classifier + calibrator) or profile mode (lookup)."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from .artifacts import Artifacts
from .features import MAX_CURRENT_AGE_US, add_carpark_stats, build_features, day_type, sg_time_parts
from .live import FeedError, LiveFeed

SHORT_MAX_MINUTES = 90
MAX_READING_AGE = timedelta(microseconds=MAX_CURRENT_AGE_US)

log = logging.getLogger(__name__)


class Engine:
    def __init__(self, artifacts: Artifacts, feed: LiveFeed):
        self.art = artifacts
        self.feed = feed

    def _result(self, cid, issue_at, arrival_at, horizon, reading, **kw) -> dict:
        p = kw.pop("p_free", None)
        if p is not None and not (math.isfinite(p) and 0.0 <= p <= 1.0):
            raise ValueError(f"p_free out of range: {p}")  # never emit an invalid probability
        stale = None if reading is None else issue_at - reading.observed_at > MAX_READING_AGE
        res = {
            "carpark_id": cid, "issue_at": issue_at, "arrival_at": arrival_at,
            "horizon_minutes": round(horizon, 2), "mode": None, "p_free": p,
            "free": None if p is None else p >= self.art.free_threshold,
            "confidence": None if p is None else self.art.confidence(p),
            "current_available": None if reading is None or stale else reading.lots_available,
            "current_observed_at": reading.observed_at if reading else None,
            "current_reading_stale": stale,
            "model_version": self.art.version, "status": "ok", "fallback_reason": None,
        }
        res.update(kw)
        return res

    def _profile(self, cid: str, arrival_at: datetime):
        _, slot, _ = sg_time_parts(arrival_at)
        cell = self.art.profile.get((cid, day_type(arrival_at), slot))
        return cell[0] if cell and cell[1] > 0 else None

    def predict(self, carpark_ids: list[str], arrival_at: datetime) -> list[dict]:
        issue_at = self.feed.clock()
        horizon = (arrival_at - issue_at).total_seconds() / 60.0
        feed_error = None
        readings: dict = {}
        try:
            readings = self.feed.current()
        except FeedError as exc:
            feed_error = str(exc)
            log.warning("live feed unavailable: %s", exc)

        results: dict[int, dict] = {}
        short: list[tuple[int, str, object]] = []
        for i, cid in enumerate(carpark_ids):
            shown = readings.get(cid)
            reading_problem = None
            if shown is not None:
                if shown.observed_at > issue_at:
                    reading_problem = "current_reading_after_issue_time"
                elif issue_at - shown.observed_at > MAX_READING_AGE:
                    reading_problem = "current_reading_older_than_15_min"
            in_profile = cid in self.art.profile_carparks
            if not in_profile and (feed_error is not None or shown is None):
                reason = "carpark not in live feed or profile" if feed_error is None else \
                    f"carpark not in profile; live feed unavailable: {feed_error}"
                results[i] = self._result(cid, issue_at, arrival_at, horizon, None,
                                          status="unknown_carpark", fallback_reason=reason)
                continue
            if feed_error is None and shown is not None and reading_problem is None \
                    and horizon <= SHORT_MAX_MINUTES:
                short.append((i, cid, shown))
                continue
            if feed_error is not None:
                status, reason = "live_feed_unavailable", feed_error
            else:
                status, reason = "ok", None
                if horizon <= SHORT_MAX_MINUTES:
                    reason = reading_problem or "no_current_reading"
            results[i] = self._profile_result(cid, issue_at, arrival_at, horizon,
                                              None if feed_error else shown, status, reason)

        if short:
            self._predict_short(short, issue_at, arrival_at, horizon, results)
        return [results[i] for i in range(len(carpark_ids))]

    def _profile_result(self, cid, issue_at, arrival_at, horizon, reading, status, reason) -> dict:
        p = self._profile(cid, arrival_at)
        if p is None:
            msg = "no profile cell for carpark/day type/slot"
            return self._result(cid, issue_at, arrival_at, horizon, reading, mode="profile",
                                status="insufficient_history" if status == "ok" else status,
                                fallback_reason=f"{msg}; {reason}" if reason else msg)
        return self._result(cid, issue_at, arrival_at, horizon, reading, mode="profile", p_free=p,
                            status=status, fallback_reason=reason)

    def _predict_short(self, short, issue_at, arrival_at, horizon, results) -> None:
        _, slot, _ = sg_time_parts(arrival_at)
        try:
            rows = []
            for _, cid, reading in short:
                hist = [(at, v) for at, v in self.feed.history(cid) if at <= issue_at]
                if not any(at == reading.observed_at for at, _ in hist):
                    hist.append((reading.observed_at, reading.lots_available))
                feats = build_features(hist, reading.total_lots, issue_at, arrival_at)
                feats = add_carpark_stats(feats, self.art.carpark_stats, cid, slot)
                rows.append([feats[n] for n in self.art.feature_names])
            X = pd.DataFrame(rows, columns=self.art.feature_names, dtype=float)
            raw = np.asarray(self.art.model.predict_proba(X))[:, 1]
            cal = np.asarray(self.art.calibrator.predict(raw), dtype=float)
            if cal.shape != raw.shape or not np.all(np.isfinite(cal)):
                raise ValueError("non-finite calibrated probability")
            cal = np.clip(cal, 0.0, 1.0)
        except Exception as exc:
            log.exception("short-horizon prediction failed; returning profile with model_error")
            for i, cid, reading in short:
                results[i] = self._profile_result(cid, issue_at, arrival_at, horizon, reading, "model_error",
                                                  f"short_model_failed: {type(exc).__name__}: {exc}")
            return
        for (i, cid, reading), p in zip(short, cal):
            results[i] = self._result(cid, issue_at, arrival_at, horizon, reading, mode="short", p_free=float(p))
