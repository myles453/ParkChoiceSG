"""Train the short-horizon model and build the profile model for ParkChoiceSG.

    .venv/bin/python train.py            # writes everything under ml/models/ and ml/reports/train_run.json

Steps (see ml/reports/agent-d.md): carpark history stats from train rows, profile model from
observations, LightGBM on a hash-sampled uniform train subset, isotonic calibration on validation.
Pairs are always read in batches and only the needed columns; features are float32.
"""
from __future__ import annotations

import argparse
import json
try:
    import resource
except ImportError:  # Unix-only measurement; inference/training also run on Windows.
    resource = None
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from build_dataset import MAX_CURRENT_AGE_US, PUBLIC_HOLIDAYS_2026, Config

ML_DIR = Path(__file__).resolve().parent
PAIR_FEATURES = [
    "current_available", "current_total_lots", "current_free_ratio", "current_age_seconds",
    "available_lag_15min", "available_lag_30min", "available_lag_60min", "delta_15min", "delta_60min",
    "horizon_minutes", "arrival_weekday", "arrival_slot_15min", "arrival_is_weekend",
    "arrival_is_public_holiday",
]
STATS_FEATURES = ["carpark_free_share", "carpark_slot_free_share"]
FEATURE_NAMES = PAIR_FEATURES + STATS_FEATURES
FORBIDDEN = {"carpark_id", "decision_at", "arrival_at", "split"}
PRIOR_WEIGHT = 20
SAMPLE_MAX = 8_000_000
DAY_TYPES = ("weekday", "saturday", "sunday_ph")
MIN_US = 60 * 1_000_000
DAY_US = 86_400 * 1_000_000
SGT_OFFSET_US = 8 * 3600 * 1_000_000
HOLIDAY_DAYS = np.array(sorted((d - datetime(1970, 1, 1).date()).days for d in PUBLIC_HOLIDAYS_2026))

# At most 5 configurations; chosen by validation log loss only (never the test split).
CONFIGS = [
    dict(num_leaves=31, learning_rate=0.1, min_child_samples=100),
    dict(num_leaves=63, learning_rate=0.1, min_child_samples=200),
    dict(num_leaves=127, learning_rate=0.1, min_child_samples=500),
    dict(num_leaves=255, learning_rate=0.05, min_child_samples=1000),
    dict(num_leaves=63, learning_rate=0.05, min_child_samples=200, reg_lambda=10.0),
]


def log(msg: str) -> None:
    print(f"[train] {msg}", flush=True)


def peak_rss_mb() -> float | None:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0 if resource else None


def check_features(names: list[str]) -> None:
    bad = [n for n in names if n.startswith("label_") or n in FORBIDDEN]
    if bad:
        raise ValueError(f"forbidden columns in the feature list: {bad}")
    if list(names) != FEATURE_NAMES:
        raise ValueError("feature list must be exactly the 16 agreed names, in order")


# ----------------------------------------------------------------------------- reading pairs
def iter_pairs(path: Path, split: str, columns: list[str], batch_rows: int = 1_000_000):
    """Yield pyarrow Tables with only rows of one split, reading the named columns in batches."""
    cols = list(dict.fromkeys(list(columns) + ["split"]))
    for batch in pq.ParquetFile(path).iter_batches(batch_size=batch_rows, columns=cols):
        table = pa.Table.from_batches([batch])
        mask = pc.equal(table.column("split"), split)
        if pc.sum(pc.cast(mask, pa.int8())).as_py():
            yield table.filter(mask)


def dict_encode(table: pa.Table, name: str = "carpark_id"):
    col = table.column(name).combine_chunks().dictionary_encode()
    return col.dictionary.to_pylist(), col.indices.to_numpy(zero_copy_only=False)


# ----------------------------------------------------------------------------- history features
def accumulate_carpark_stats(pairs_path: Path, batch_rows: int = 1_000_000) -> pd.DataFrame:
    """Grouped (carpark, slot) free/row counts over train rows only, built batch by batch."""
    parts, pending_rows = [], 0
    for table in iter_pairs(pairs_path, "train", ["carpark_id", "arrival_slot_15min", "label_free"], batch_rows):
        names, idx = dict_encode(table)
        frame = pd.DataFrame({
            "c": idx, "slot": table.column("arrival_slot_15min").to_numpy().astype(np.int16),
            "free": table.column("label_free").to_numpy().astype(np.int64)})
        grouped = frame.groupby(["c", "slot"], sort=False)["free"].agg(["sum", "count"]).reset_index()
        grouped["carpark_id"] = np.asarray(names, dtype=object)[grouped["c"].to_numpy()]
        parts.append(grouped[["carpark_id", "slot", "sum", "count"]])
        pending_rows += len(grouped)
        if pending_rows > 5_000_000:
            parts = [pd.concat(parts).groupby(["carpark_id", "slot"], sort=False).sum().reset_index()]
            pending_rows = len(parts[0])
    if not parts:
        return pd.DataFrame(columns=["carpark_id", "slot", "sum", "count"])
    return pd.concat(parts).groupby(["carpark_id", "slot"], sort=False).sum().reset_index()


def make_carpark_stats(counts: pd.DataFrame, prior: int = PRIOR_WEIGHT) -> pd.DataFrame:
    """carpark_stats.parquet: slot -1 row = carpark share (slot value empty); others smoothed to it."""
    if counts.empty:
        return pd.DataFrame({"carpark_id": pd.Series(dtype=object), "slot_15min": pd.Series(dtype="int16"),
                             "carpark_free_share": pd.Series(dtype="float32"),
                             "carpark_slot_free_share": pd.Series(dtype="float32")})
    cp = counts.groupby("carpark_id")[["sum", "count"]].sum()
    cp["share"] = cp["sum"] / cp["count"]
    slots = counts.join(cp["share"], on="carpark_id")
    slots["slot_share"] = (slots["sum"] + prior * slots["share"]) / (slots["count"] + prior)
    top = pd.DataFrame({"carpark_id": cp.index.to_numpy(), "slot_15min": -1,
                        "carpark_free_share": cp["share"].to_numpy(), "carpark_slot_free_share": np.nan})
    body = pd.DataFrame({"carpark_id": slots["carpark_id"].to_numpy(), "slot_15min": slots["slot"].to_numpy(),
                         "carpark_free_share": slots["share"].to_numpy(),
                         "carpark_slot_free_share": slots["slot_share"].to_numpy()})
    out = pd.concat([top, body], ignore_index=True).sort_values(["carpark_id", "slot_15min"], ignore_index=True)
    out["slot_15min"] = out["slot_15min"].astype("int16")
    out["carpark_free_share"] = out["carpark_free_share"].astype("float32")
    out["carpark_slot_free_share"] = out["carpark_slot_free_share"].astype("float32")
    return out


class StatsLookup:
    """Join carpark_stats values to rows by carpark and arrival slot; unknown keys stay NaN."""

    def __init__(self, stats: pd.DataFrame):
        top = stats[stats["slot_15min"] == -1]
        self.index = pd.Index(top["carpark_id"].to_numpy())
        self.carpark = top["carpark_free_share"].to_numpy(np.float32)
        self.slot = np.full((len(self.index), 96), np.nan, dtype=np.float32)
        body = stats[stats["slot_15min"] >= 0]
        rows = self.index.get_indexer(body["carpark_id"].to_numpy())
        keep = rows >= 0
        self.slot[rows[keep], body["slot_15min"].to_numpy()[keep]] = body["carpark_slot_free_share"].to_numpy()[keep]

    def lookup(self, names: list, idx: np.ndarray, slots: np.ndarray):
        mapped = self.index.get_indexer(np.asarray(names, dtype=object))
        rows = mapped[idx]
        known = rows >= 0
        safe = np.where(known, rows, 0)
        cp = np.where(known, self.carpark[safe], np.nan).astype(np.float32)
        sl = np.where(known, self.slot[safe, slots.astype(np.int64)], np.nan).astype(np.float32)
        return cp, sl


def feature_matrix(table: pa.Table, lookup: StatsLookup) -> np.ndarray:
    """(rows, 16) float32 in FEATURE_NAMES order. Missing values stay NaN; nothing is filled."""
    check_features(FEATURE_NAMES)
    X = np.empty((table.num_rows, len(FEATURE_NAMES)), dtype=np.float32)
    for j, name in enumerate(PAIR_FEATURES):
        X[:, j] = table.column(name).to_numpy()
    names, idx = dict_encode(table)
    slots = table.column("arrival_slot_15min").to_numpy()
    X[:, 14], X[:, 15] = lookup.lookup(names, idx, slots)
    return X


def as_frame(X: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame(X, columns=FEATURE_NAMES)


# ----------------------------------------------------------------------------- reproducible sample
def _splitmix64(x: np.ndarray) -> np.ndarray:
    with np.errstate(over="ignore"):
        x = x + np.uint64(0x9E3779B97F4A7C15)
        x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        return x ^ (x >> np.uint64(31))


def row_hash(names: list, idx: np.ndarray, decision_us: np.ndarray) -> np.ndarray:
    """64-bit hash of (carpark_id, decision_at); identical whatever the batching or row order."""
    crc = np.array([zlib.crc32(n.encode()) for n in names], dtype=np.uint64)[idx]
    return _splitmix64(_splitmix64(crc) ^ decision_us.astype(np.int64).view(np.uint64))


def sample_fraction(n_train: int, cap: int = SAMPLE_MAX) -> float:
    return 1.0 if n_train <= cap else 0.98 * cap / n_train


def hash_keep(hashes: np.ndarray, fraction: float) -> np.ndarray:
    if fraction >= 1.0:
        return np.ones(len(hashes), dtype=bool)
    return hashes < np.uint64(int(fraction * 2.0 ** 64))


def load_train_sample(pairs_path: Path, lookup: StatsLookup, n_train: int, cap: int = SAMPLE_MAX):
    frac = sample_fraction(n_train, cap)
    Xs, ys, hs = [], [], []
    cols = PAIR_FEATURES + ["carpark_id", "decision_at", "label_free"]
    for table in iter_pairs(pairs_path, "train", cols):
        names, idx = dict_encode(table)
        dec = table.column("decision_at").cast(pa.int64()).to_numpy()
        h = row_hash(names, idx, dec)
        keep = hash_keep(h, frac)
        if not keep.any():
            continue
        sub = table.filter(pa.array(keep))
        Xs.append(feature_matrix(sub, lookup))
        ys.append(sub.column("label_free").to_numpy().astype(np.int8))
        hs.append(h[keep])
    X, y, h = np.concatenate(Xs), np.concatenate(ys), np.concatenate(hs)
    if len(y) > cap:  # rare: keep the lowest hashes, still reproducible and label-independent
        order = np.argsort(h, kind="stable")[:cap]
        X, y, h = X[order], y[order], h[order]
    return X, y


def load_split(pairs_path: Path, split: str, lookup: StatsLookup):
    Xs, ys = [], []
    for table in iter_pairs(pairs_path, split, PAIR_FEATURES + ["carpark_id", "label_free"]):
        Xs.append(feature_matrix(table, lookup))
        ys.append(table.column("label_free").to_numpy().astype(np.int8))
    return np.concatenate(Xs), np.concatenate(ys)


# ----------------------------------------------------------------------------- profile model
def day_type_codes(local_days: np.ndarray) -> np.ndarray:
    """0 weekday, 1 saturday, 2 sunday_ph (Sunday or a PUBLIC_HOLIDAYS_2026 date) from SGT epoch days."""
    wd = (local_days + 3) % 7  # 1970-01-01 was a Thursday; Monday = 0
    code = np.where(wd == 5, 1, np.where(wd == 6, 2, 0))
    return np.where(np.isin(local_days, HOLIDAY_DAYS), 2, code)


def observation_cells(t_us: np.ndarray):
    local = t_us + SGT_OFFSET_US
    days = local // DAY_US
    return day_type_codes(days), ((local % DAY_US) // (15 * MIN_US)).astype(np.int16)


def iter_observations(obs_path: Path, start_us: int, end_us: int, batch_rows: int = 2_000_000):
    """Observations in [start_us, end_us) that were not stale when first seen. Each counts once."""
    cols = ["carpark_id", "observed_at", "lots_available", "first_seen_at"]
    for batch in pq.ParquetFile(obs_path).iter_batches(batch_size=batch_rows, columns=cols):
        t = pa.Table.from_batches([batch])
        obs = t.column("observed_at").cast(pa.int64()).to_numpy()
        seen = t.column("first_seen_at").cast(pa.int64()).to_numpy()
        ok = (obs >= start_us) & (obs < end_us) & (seen - obs <= MAX_CURRENT_AGE_US)
        if ok.any():
            yield t.filter(pa.array(ok)), obs[ok]


def build_profile(obs_path: Path, start_us: int, end_us: int, prior: int = PRIOR_WEIGHT) -> pd.DataFrame:
    parts = []
    for t, obs in iter_observations(obs_path, start_us, end_us):
        dt, slot = observation_cells(obs)
        frame = pd.DataFrame({"carpark_id": t.column("carpark_id").to_numpy(zero_copy_only=False),
                              "dt": dt, "slot": slot,
                              "free": (t.column("lots_available").to_numpy() >= 1).astype(np.int64)})
        parts.append(frame.groupby(["carpark_id", "dt", "slot"], sort=False)["free"]
                     .agg(["sum", "count"]).reset_index())
    if not parts:
        return pd.DataFrame(columns=["carpark_id", "day_type", "slot_15min", "p_free", "n_samples"])
    cells = pd.concat(parts).groupby(["carpark_id", "dt", "slot"], sort=False).sum().reset_index()
    cp = cells.groupby("carpark_id")[["sum", "count"]].sum()
    cells = cells.join((cp["sum"] / cp["count"]).rename("cp_share"), on="carpark_id")
    cells["p_free"] = (cells["sum"] + prior * cells["cp_share"]) / (cells["count"] + prior)
    out = pd.DataFrame({
        "carpark_id": cells["carpark_id"], "day_type": np.array(DAY_TYPES, dtype=object)[cells["dt"].to_numpy()],
        "slot_15min": cells["slot"].astype("int16"), "p_free": cells["p_free"].astype("float32"),
        "n_samples": cells["count"].astype("int64")})
    return out.sort_values(["carpark_id", "day_type", "slot_15min"], ignore_index=True)


# ----------------------------------------------------------------------------- bands
def reliability(y: np.ndarray, p: np.ndarray, bins: int = 10) -> pd.DataFrame:
    b = np.minimum((p * bins).astype(int), bins - 1)
    g = pd.DataFrame({"b": b, "p": p, "y": y}).groupby("b")
    out = g.agg(mean_predicted=("p", "mean"), observed_free=("y", "mean"), rows=("y", "size")).reset_index()
    out.insert(1, "bin", [f"{i / bins:.1f}-{(i + 1) / bins:.1f}" for i in out["b"]])
    return out.drop(columns="b")


def choose_bands(y: np.ndarray, p: np.ndarray, high_target=0.99, medium_target=0.90, min_rows=500):
    """Rule, applied to VALIDATION data only (calibrated p_free):
    free_threshold: lowest reliability-bin (width 0.1) lower edge from which every bin above has an observed
        free share >= 0.5 (so calling "free" is right more often than not).
    high / medium: the lowest 0.01 bin edge c such that every bin of width 0.01 at or above c holding at least
        500 validation rows has an observed free share >= 99% (high) or >= 90% (medium). The check is per bin,
        not cumulative, because the huge mass of rows near p=1 would hide poor bins in a cumulative share.
        medium is capped at high."""
    rel = reliability(y, p)
    obs_by_edge = {float(r.bin.split("-")[0]): r.observed_free for r in rel.itertuples()}
    free_threshold, below_ok = 0.5, None
    for edge in sorted(obs_by_edge, reverse=True):
        if obs_by_edge[edge] >= 0.5:
            below_ok = edge
        else:
            break
    if below_ok is not None:
        free_threshold = below_ok

    fine = np.minimum((p * 100).astype(int), 99)
    rows = np.bincount(fine, minlength=100)
    free = np.bincount(fine, weights=y.astype(np.float64), minlength=100)

    def cut_for(target):
        cut = 1.0
        for b in range(99, -1, -1):
            if rows[b] < min_rows:
                continue
            if free[b] / rows[b] >= target:
                cut = b / 100
            else:
                break
        return float(cut)

    high, medium = cut_for(high_target), cut_for(medium_target)
    return float(free_threshold), {"high": float(high), "medium": float(min(medium, high))}


# ----------------------------------------------------------------------------- model
def fit_best_model(Xt, yt, Xv, yv, threads: int, configs=CONFIGS, n_estimators=2000):
    import lightgbm as lgb
    from sklearn.metrics import log_loss
    best, results = None, []
    Xt_df, Xv_df = as_frame(Xt), as_frame(Xv)
    for i, cfg in enumerate(configs[:5]):
        t0 = time.time()
        m = lgb.LGBMClassifier(objective="binary", n_estimators=n_estimators, n_jobs=threads,
                               random_state=0, verbose=-1, **cfg)
        m.fit(Xt_df, yt, eval_set=[(Xv_df, yv)], eval_metric="binary_logloss",
              callbacks=[lgb.early_stopping(50, verbose=False)])
        raw = m.predict_proba(Xv_df)[:, 1]
        ll = float(log_loss(yv, np.clip(raw, 1e-15, 1 - 1e-15)))
        results.append({"config": cfg, "best_iteration": int(m.best_iteration_ or n_estimators),
                        "val_logloss": ll, "seconds": round(time.time() - t0, 1)})
        log(f"config {i + 1}: {results[-1]}")
        if best is None or ll < best[0]:
            best = (ll, m, raw)
    return best[1], best[2], results


def train_all(pairs_path: Path, obs_path: Path, models_dir: Path, threads: int, sample_cap: int = SAMPLE_MAX,
              configs=CONFIGS, n_estimators=2000, cfg: Config | None = None) -> dict:
    from sklearn.isotonic import IsotonicRegression
    cfg = cfg or Config()
    models_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    counts = accumulate_carpark_stats(pairs_path)
    stats = make_carpark_stats(counts)
    stats.to_parquet(models_dir / "carpark_stats.parquet", index=False)
    n_train = int(counts["count"].sum())
    base_rate = float(counts["sum"].sum() / n_train)
    log(f"carpark stats: {len(stats)} rows, {n_train} train rows, base rate free {base_rate:.5f} "
        f"({time.time() - t0:.0f}s)")
    lookup = StatsLookup(stats)

    profile = build_profile(obs_path, cfg.start_us, cfg.test_start_us)
    profile.to_parquet(models_dir / "profile.parquet", index=False)
    log(f"profile: {len(profile)} cells, {profile['carpark_id'].nunique()} carparks")

    Xt, yt = load_train_sample(pairs_path, lookup, n_train, sample_cap)
    log(f"train sample {len(yt)} rows")
    Xv, yv = load_split(pairs_path, "validation", lookup)
    log(f"validation {len(yv)} rows, base rate free {yv.mean():.5f}")
    model, raw_val, results = fit_best_model(Xt, yt, Xv, yv, threads, configs, n_estimators)
    sample_size = int(len(yt))
    del Xt, yt
    calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(raw_val.astype(np.float64), yv)
    p_val = calibrator.predict(raw_val.astype(np.float64))
    free_threshold, bands = choose_bands(yv, p_val)
    check_features(FEATURE_NAMES)
    joblib.dump({"model": model, "calibrator": calibrator, "feature_names": list(FEATURE_NAMES)},
                models_dir / "short_horizon.joblib")
    iso = lambda us: datetime.fromtimestamp(us / 1e6, tz=timezone.utc).isoformat()
    card = {
        "version": "short-horizon-lgbm-" + datetime.now(timezone.utc).strftime("%Y%m%d"),
        "free_threshold": free_threshold, "confidence_bands": bands,
        "trained_at": datetime.now(timezone.utc).isoformat(), "feature_names": list(FEATURE_NAMES),
        "train_sample_size": sample_size, "train_rows_total": n_train, "train_base_rate_free": base_rate,
        "validation_base_rate_free": float(yv.mean()),
        "split_dates": {"train": "2026-07-15 to 2026-09-15", "validation": "2026-09-16 to 2026-09-26",
                        "test": "2026-09-27 to 2026-10-07 14:30 (Asia/Singapore)"},
        "chosen_hyperparameters": model.get_params(), "hyperparameter_search": results,
        "band_rule": choose_bands.__doc__,
    }
    (models_dir / "model_card.json").write_text(json.dumps(card, indent=2, default=str))
    return card


def main() -> None:
    import os
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=ML_DIR / "data")
    ap.add_argument("--models-dir", type=Path, default=ML_DIR / "models")
    ap.add_argument("--threads", type=int, default=max(1, (os.cpu_count() or 3) - 2))
    ap.add_argument("--sample-max", type=int, default=SAMPLE_MAX)
    args = ap.parse_args()
    t0 = time.time()
    card = train_all(args.data_dir / "pairs.parquet", args.data_dir / "observations.parquet",
                     args.models_dir, args.threads, args.sample_max)
    peak = peak_rss_mb()
    run = {"wall_seconds": round(time.time() - t0, 1), "peak_rss_mb": round(peak, 1) if peak is not None else None,
           "threads": args.threads, "train_sample_size": card["train_sample_size"]}
    (ML_DIR / "reports").mkdir(exist_ok=True)
    (ML_DIR / "reports" / "train_run.json").write_text(json.dumps(run, indent=2))
    log(f"done: {run}")


if __name__ == "__main__":
    main()
