"""Feature function shared by training (pair building) and later LTA/URA scoring.

compute_features() sees only (seen_at, lots_available) rows of ONE carpark. It never takes capacity,
provider update times or any statistic computed from labels. Rows with seen_at after a decision time
are ignored for that decision.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "ml"))
from build_dataset import PUBLIC_HOLIDAYS_2026  # noqa: E402

MIN_US = 60 * 1_000_000
HOUR_US = 60 * MIN_US
DAY_US = 24 * HOUR_US
SGT_OFFSET_US = 8 * HOUR_US
MAX_CURRENT_AGE_US = 6 * MIN_US
LAG_TOLERANCE_US = 4 * MIN_US
LAGS_MIN = (15, 30, 60)
TRAILING_WINDOW_US = 72 * HOUR_US
MIN_HISTORY_US = 24 * HOUR_US
_EPOCH_ORDINAL = 719163  # date(1970, 1, 1).toordinal()
HOLIDAY_DAYS = np.array(sorted(d.toordinal() - _EPOCH_ORDINAL for d in PUBLIC_HOLIDAYS_2026), dtype=np.int64)

FEATURES_A = ["current_available", "available_lag_15min", "available_lag_30min", "available_lag_60min",
              "delta_15min", "delta_60min", "horizon_minutes", "arrival_weekday", "arrival_slot_15min",
              "arrival_is_weekend", "arrival_is_public_holiday"]
FEATURES_B = FEATURES_A + ["trailing_max_72h", "ratio_to_trailing_max"]


def calendar_features(arrival_us: np.ndarray) -> dict[str, np.ndarray]:
    """Weekday (ISO 1-7), 15-minute slot (0-95), weekend and public-holiday flags, in Singapore time."""
    local = np.asarray(arrival_us, dtype=np.int64) + SGT_OFFSET_US
    days = local // DAY_US
    weekday = (days + 3) % 7 + 1  # 1970-01-01 was a Thursday (ISO 4)
    slot = (local % DAY_US) // (15 * MIN_US)
    return {"arrival_weekday": weekday, "arrival_slot_15min": slot,
            "arrival_is_weekend": weekday >= 6, "arrival_is_public_holiday": np.isin(days, HOLIDAY_DAYS)}


def _nearest_within(seen: np.ndarray, target: np.ndarray, limit: np.ndarray, tol: int) -> np.ndarray:
    """Index of the row nearest to target among rows with seen <= limit and |seen - target| <= tol, else -1."""
    n = len(seen)
    i = np.searchsorted(seen, target)  # first row >= target
    lo, hi = np.clip(i - 1, 0, n - 1), np.clip(i, 0, n - 1)
    d_lo = np.where(seen[lo] <= limit, np.abs(seen[lo] - target), np.iinfo(np.int64).max)
    d_hi = np.where(seen[hi] <= limit, np.abs(seen[hi] - target), np.iinfo(np.int64).max)
    pick = np.where(d_lo <= d_hi, lo, hi)  # tie: the earlier row
    best = np.minimum(d_lo, d_hi)
    return np.where(best <= tol, pick, -1)


def _range_max(values: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """max(values[lo..hi]) inclusive per element via a sparse table. Requires lo <= hi."""
    levels = [values]
    k = 1
    while 2 * k <= len(values):
        prev = levels[-1]
        levels.append(np.maximum(prev[:-k], prev[k:]))
        k *= 2
    span = hi - lo + 1
    level = np.floor(np.log2(span)).astype(np.int64)
    out = np.empty(len(lo), dtype=values.dtype)
    for lv in np.unique(level):
        sel = level == lv
        table = levels[lv]
        out[sel] = np.maximum(table[lo[sel]], table[hi[sel] - (1 << lv) + 1])
    return out


def compute_features(seen_us, lots, decision_us, horizons, variant_b: bool = True) -> pd.DataFrame:
    """Features for one carpark, many decision times, many horizons.

    seen_us: int64 microseconds since epoch (UTC), strictly increasing. lots: lots_available per row.
    decision_us: int64 decision times. horizons: minutes. Returns one row per (decision, horizon) for
    decisions that have a current reading at most 6 minutes old; decisions without one produce no row.
    Missing lags, deltas and trailing values are NaN. All feature columns are float32.
    """
    seen = np.asarray(seen_us, dtype=np.int64)
    vals = np.asarray(lots, dtype=np.int64)
    dec = np.atleast_1d(np.asarray(decision_us, dtype=np.int64))
    hz = np.atleast_1d(np.asarray(horizons, dtype=np.int64))
    cols = ["decision_us", *FEATURES_B] if variant_b else ["decision_us", *FEATURES_A]
    if len(seen) == 0 or len(dec) == 0:
        return pd.DataFrame({c: pd.Series(dtype="int64" if c == "decision_us" else "float32") for c in cols})

    cur = np.searchsorted(seen, dec, side="right") - 1  # latest row at or before the decision
    ok = (cur >= 0) & (dec - seen[np.maximum(cur, 0)] <= MAX_CURRENT_AGE_US)
    dec, cur = dec[ok], cur[ok]
    current = vals[cur].astype(np.float32)

    lag_val = {}
    for lag in LAGS_MIN:
        j = _nearest_within(seen, dec - lag * MIN_US, dec, LAG_TOLERANCE_US)
        lag_val[lag] = np.where(j >= 0, vals[np.maximum(j, 0)], np.nan).astype(np.float32)

    per_decision = {"decision_us": dec, "current_available": current,
                    "available_lag_15min": lag_val[15], "available_lag_30min": lag_val[30],
                    "available_lag_60min": lag_val[60],
                    "delta_15min": current - lag_val[15], "delta_60min": current - lag_val[60]}
    if variant_b:
        first = np.searchsorted(seen, dec - TRAILING_WINDOW_US, side="right")  # window (dec-72h, dec]
        first = np.minimum(first, cur)
        tmax = np.full(len(dec), np.nan, dtype=np.float32)
        enough = (dec - seen[0]) >= MIN_HISTORY_US
        if enough.any():
            tmax[enough] = _range_max(vals, first[enough], cur[enough])
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(tmax > 0, current / tmax, np.nan).astype(np.float32)
        per_decision.update(trailing_max_72h=tmax, ratio_to_trailing_max=ratio)

    n_h = len(hz)
    frame = {k: np.repeat(v, n_h) for k, v in per_decision.items()}
    frame["horizon_minutes"] = np.tile(hz, len(dec))
    cal = calendar_features(frame["decision_us"] + frame["horizon_minutes"] * MIN_US)
    frame.update(cal)
    out = pd.DataFrame(frame)
    float_cols = [c for c in cols if c != "decision_us"]
    out[float_cols] = out[float_cols].astype(np.float32)
    return out[cols]
