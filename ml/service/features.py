"""Decision-time features for the short-horizon classifier.

Mirrors ml/build_dataset.py (compute_features / pairs_for_carpark), the source of truth: same
column names, units and rules. Constants and the holiday list are imported, never copied.
Missing lags stay NaN; nothing is filled or interpolated.
"""
from __future__ import annotations

import math
import sys
from datetime import datetime
from pathlib import Path

_ML_DIR = Path(__file__).resolve().parents[1]
if str(_ML_DIR) not in sys.path:
    sys.path.insert(0, str(_ML_DIR))

from build_dataset import (  # noqa: E402
    FUTURE_ALLOWANCE,
    LAG_TOLERANCE_US,
    MAX_CURRENT_AGE_US,
    MIN_US,
    PUBLIC_HOLIDAYS_2026,
    SGT,
    to_us,
)

LAGS_MIN = (15, 30, 60)
NAN = float("nan")

PAIR_FEATURES = [
    "current_available", "current_total_lots", "current_free_ratio", "current_age_seconds",
    "available_lag_15min", "available_lag_30min", "available_lag_60min", "delta_15min", "delta_60min",
    "horizon_minutes", "arrival_weekday", "arrival_slot_15min", "arrival_is_weekend",
    "arrival_is_public_holiday",
]
STATS_FEATURES = ["carpark_free_share", "carpark_slot_free_share"]
BUILDABLE_FEATURES = PAIR_FEATURES + STATS_FEATURES
# Longest look-back the lag rule can use (lag + tolerance); the live history must cover it.
REQUIRED_HISTORY_MINUTES = max(LAGS_MIN) + LAG_TOLERANCE_US // MIN_US


def sg_time_parts(ts: datetime) -> tuple[int, int, bool]:
    """(ISO weekday 1-7, 15-minute slot 0-95, public holiday) in Singapore time."""
    local = ts.astimezone(SGT)
    return local.isoweekday(), local.hour * 4 + local.minute // 15, local.date() in PUBLIC_HOLIDAYS_2026


def day_type(ts: datetime) -> str:
    """Profile day type; public holidays (build_dataset list) count as sunday_ph."""
    weekday, _, holiday = sg_time_parts(ts)
    if weekday == 7 or holiday:
        return "sunday_ph"
    return "saturday" if weekday == 6 else "weekday"


def _lag(times_us: list[int], lots: list[int], target_us: int, decision_us: int):
    """Nearest reading to target within LAG_TOLERANCE_US (earlier wins ties), never after decision."""
    best = None
    for t, v in zip(times_us, lots):
        d = abs(t - target_us)
        if d <= LAG_TOLERANCE_US and t <= decision_us and (best is None or d < best[0]
                                                           or (d == best[0] and t < best[1])):
            best = (d, t, v)
    return None if best is None else best[2]


def build_features(readings: list[tuple[datetime, int]], total_lots: int, issue_at: datetime,
                   arrival_at: datetime) -> dict[str, float]:
    """The pairs.parquet feature columns for one carpark.

    readings: distinct (observed_at, lots_available) known by issue_at; later ones are ignored.
    total_lots: capacity of the current (latest) reading. Raises ValueError if there is no
    reading at or before issue_at or it is older than MAX_CURRENT_AGE_US.
    """
    decision = to_us(issue_at)
    known = sorted((to_us(at), v) for at, v in readings if to_us(at) <= decision)
    if not known:
        raise ValueError("no reading at or before the issue time")
    times = [t for t, _ in known]
    lots = [v for _, v in known]
    age = decision - times[-1]
    if age > MAX_CURRENT_AGE_US:
        raise ValueError("current reading is too old")
    cur = lots[-1]
    feats: dict[str, float] = {
        "current_available": cur,
        "current_total_lots": total_lots,
        "current_free_ratio": cur / total_lots,
        "current_age_seconds": age // 1_000_000,
    }
    lag_values = {}
    for m in LAGS_MIN:
        lag_values[m] = _lag(times, lots, decision - m * MIN_US, decision)
        feats[f"available_lag_{m}min"] = NAN if lag_values[m] is None else lag_values[m]
    feats["delta_15min"] = NAN if lag_values[15] is None else cur - lag_values[15]
    feats["delta_60min"] = NAN if lag_values[60] is None else cur - lag_values[60]
    weekday, slot, holiday = sg_time_parts(arrival_at)
    feats["horizon_minutes"] = (to_us(arrival_at) - decision) / MIN_US
    feats["arrival_weekday"] = weekday
    feats["arrival_slot_15min"] = slot
    feats["arrival_is_weekend"] = weekday >= 6
    feats["arrival_is_public_holiday"] = holiday
    return feats


def add_carpark_stats(feats: dict, stats: dict, carpark_id: str, slot: int) -> dict:
    """Join carpark_stats.parquet values by carpark and arrival slot; absent rows stay NaN."""
    def get(slot_key: int, column: str) -> float:
        v = stats.get((carpark_id, slot_key), {}).get(column)
        return NAN if v is None or not math.isfinite(v) else v

    feats["carpark_free_share"] = get(-1, "carpark_free_share")
    feats["carpark_slot_free_share"] = get(slot, "carpark_slot_free_share")
    return feats
