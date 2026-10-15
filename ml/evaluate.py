"""Evaluate the short-horizon model, the profile model and the baselines on the TEST split only.

    .venv/bin/python evaluate.py

Writes ml/reports/evaluation.md, ml/reports/evaluation.json, ml/reports/uncovered_carparks.csv and
ml/data/test_predictions.parquet, and adds the test Brier scores to ml/models/model_card.json.
Nothing here is used to tune anything: bands and threshold come from validation data (train.py).
"""
from __future__ import annotations

import argparse
import json
import resource
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from build_dataset import Config, sgt_us
from train import (FEATURE_NAMES, PAIR_FEATURES, StatsLookup, as_frame, choose_bands, dict_encode,
                   feature_matrix, iter_observations, iter_pairs, load_split, observation_cells, reliability)

ML_DIR = Path(__file__).resolve().parent
EPS = 1e-15
HORIZONS = (15, 30, 45, 60, 90)
METHODS = ("model", "persistence", "always_free")
WEEKDAY_SLOT_TARGET = 80


def log(msg: str) -> None:
    print(f"[evaluate] {msg}", flush=True)


def metrics(y: np.ndarray, p: np.ndarray) -> dict:
    """Brier, log loss (p clipped to [1e-15, 1-1e-15]), ROC AUC (free), average precision (NOT free)."""
    n = int(len(y))
    if n == 0:
        return {"rows": 0, "brier": None, "log_loss": None, "roc_auc": None, "ap_not_free": None}
    p64 = p.astype(np.float64)
    pc_ = np.clip(p64, EPS, 1 - EPS)
    ll = float(-np.mean(y * np.log(pc_) + (1 - y) * np.log(1 - pc_)))
    both = 0 < int(y.sum()) < n
    return {"rows": n, "brier": float(brier_score_loss(y, p64)), "log_loss": ll,
            "roc_auc": float(roc_auc_score(y, p64)) if both else None,
            "ap_not_free": float(average_precision_score(1 - y, 1 - p64)) if int(y.sum()) < n else None}


def metric_table(y, preds: dict, horizon, mask=None) -> list[dict]:
    rows = []
    for scope in ["all"] + [h for h in HORIZONS]:
        sel = np.ones(len(y), bool) if mask is None else mask.copy()
        if scope != "all":
            sel &= horizon == scope
        for name in METHODS:
            rows.append({"horizon": scope, "method": name, **metrics(y[sel], preds[name][sel])})
    return rows


def fmt(v, digits=4) -> str:
    return "n/a" if v is None or (isinstance(v, float) and np.isnan(v)) else (f"{v:,}" if isinstance(v, int) else f"{v:.{digits}f}")


def md_table(rows: list[dict], cols: list[str], heads: list[str] | None = None) -> str:
    heads = heads or cols
    out = ["| " + " | ".join(heads) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for r in rows:
        out.append("| " + " | ".join(fmt(r[c]) if not isinstance(r[c], str) else r[c] for c in cols) + " |")
    return "\n".join(out)


def band_report(y: np.ndarray, p: np.ndarray, free_threshold: float, bands: dict) -> list[dict]:
    high, medium = bands["high"], bands["medium"]
    defs = [("High (p >= high)", p >= high), ("Medium (medium <= p < high)", (p >= medium) & (p < high)),
            ("Low (p < medium)", p < medium), ("Predicted free (p >= free_threshold)", p >= free_threshold),
            ("Predicted not free (p < free_threshold)", p < free_threshold)]
    return [{"band": name, "rows": int(m.sum()), "observed_free": float(y[m].mean()) if m.any() else None}
            for name, m in defs]


def predict(bundle, X: np.ndarray) -> np.ndarray:
    """Exactly the service's call sequence: predict_proba(DataFrame)[:, 1] then calibrator.predict."""
    raw = bundle["model"].predict_proba(as_frame(X))[:, 1]
    return bundle["calibrator"].predict(raw).astype(np.float32)


def evaluate_test(pairs_path: Path, bundle, lookup: StatsLookup, base_rate: float, out_pred: Path):
    ys, ps, pers, hs, ratio = [], [], [], [], []
    writer = None
    schema = pa.schema([("carpark_id", pa.string()), ("decision_at", pa.timestamp("us", tz="UTC")),
                        ("horizon_minutes", pa.int16()), ("p_free", pa.float32())])
    tmp = out_pred.with_name(out_pred.name + ".tmp")
    writer = pq.ParquetWriter(tmp, schema, compression="zstd")
    cols = PAIR_FEATURES + ["carpark_id", "decision_at", "label_free"]
    for table in iter_pairs(pairs_path, "test", cols):
        X = feature_matrix(table, lookup)
        p = predict(bundle, X)
        writer.write_table(pa.table({
            "carpark_id": table.column("carpark_id"), "decision_at": table.column("decision_at"),
            "horizon_minutes": table.column("horizon_minutes").cast(pa.int16()), "p_free": pa.array(p)}, schema=schema))
        ys.append(table.column("label_free").to_numpy().astype(np.int8))
        ps.append(p)
        pers.append((X[:, 0] >= 1).astype(np.float32))
        hs.append(X[:, 9].astype(np.int16))
        ratio.append(X[:, 2])
    writer.close()
    tmp.replace(out_pred)
    y, h = np.concatenate(ys), np.concatenate(hs)
    p_model = np.concatenate(ps)
    preds = {"model": p_model, "persistence": np.concatenate(pers),
             "always_free": np.full(len(y), base_rate, dtype=np.float32)}
    return y, preds, h, np.concatenate(ratio)


def evaluate_profile(obs_path: Path, profile: pd.DataFrame, base_rate: float, cfg: Config):
    """Profile vs always-free on observations of test dates (the profile never saw them)."""
    idx = profile.set_index(["carpark_id", "day_type", "slot_15min"])["p_free"]
    ys, ps, missing, total = [], [], 0, 0
    day_names = np.array(["weekday", "saturday", "sunday_ph"], dtype=object)
    for t, obs in iter_observations(obs_path, cfg.test_start_us, cfg.end_us):
        dt, slot = observation_cells(obs)
        keys = pd.MultiIndex.from_arrays([t.column("carpark_id").to_numpy(zero_copy_only=False),
                                          day_names[dt], slot.astype(np.int16)])
        p = idx.reindex(keys).to_numpy(np.float64)
        y = (t.column("lots_available").to_numpy() >= 1).astype(np.int8)
        known = ~np.isnan(p)
        total += len(y)
        missing += int((~known).sum())
        ys.append(y[known])
        ps.append(p[known].astype(np.float32))
    y, p = np.concatenate(ys), np.concatenate(ps)
    return y, p, {"observations": total, "without_profile_cell": missing,
                  "base_rate_free": float(y.mean()), "always_free_p": base_rate}


def coverage(obs_path: Path, stats: pd.DataFrame, profile: pd.DataFrame, out_csv: Path) -> dict:
    last = {}
    for batch in pq.ParquetFile(obs_path).iter_batches(batch_size=4_000_000, columns=["carpark_id", "observed_at"]):
        t = pa.Table.from_batches([batch])
        g = pd.DataFrame({"c": t.column("carpark_id").to_numpy(zero_copy_only=False),
                          "t": t.column("observed_at").cast(pa.int64()).to_numpy()}).groupby("c")["t"].max()
        for c, v in g.items():
            if v > last.get(c, -(1 << 62)):
                last[c] = v
    universe = sorted(last)
    train_cp = set(stats.loc[stats["slot_15min"] == -1, "carpark_id"])
    weekday = profile[profile["day_type"] == "weekday"].groupby("carpark_id")["slot_15min"].nunique()
    prof80 = set(weekday[weekday >= WEEKDAY_SLOT_TARGET].index)
    uncovered = [c for c in universe if c not in train_cp and c not in prof80]
    rows = pd.DataFrame({"carpark_id": uncovered,
                         "last_update_time": [pd.Timestamp(last[c], unit="us", tz="UTC").isoformat() for c in uncovered]})
    rows.to_csv(out_csv, index=False)
    return {"carparks_in_observations": len(universe), "with_train_row": len(train_cp),
            "with_profile_80_weekday_slots": len(prof80), "uncovered": len(uncovered)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=ML_DIR / "data")
    ap.add_argument("--models-dir", type=Path, default=ML_DIR / "models")
    ap.add_argument("--reports-dir", type=Path, default=ML_DIR / "reports")
    args = ap.parse_args()
    t0 = time.time()
    cfg = Config()
    pairs, obs = args.data_dir / "pairs.parquet", args.data_dir / "observations.parquet"
    bundle = joblib.load(args.models_dir / "short_horizon.joblib")
    card = json.loads((args.models_dir / "model_card.json").read_text())
    stats = pd.read_parquet(args.models_dir / "carpark_stats.parquet")
    profile = pd.read_parquet(args.models_dir / "profile.parquet")
    lookup = StatsLookup(stats)
    base_rate = float(card["train_base_rate_free"])
    manifest = json.loads((args.data_dir / "pairs.manifest.json").read_text())

    # validation reliability (the data the threshold and bands come from)
    Xv, yv = load_split(pairs, "validation", lookup)
    pv = predict(bundle, Xv)
    del Xv
    val_rel = reliability(yv, pv)
    ft, bands = choose_bands(yv, pv)
    if abs(ft - card["free_threshold"]) > 1e-9 or bands != card["confidence_bands"]:
        log(f"note: bands recomputed here ({ft}, {bands}) differ slightly from the card; using the card")
        ft, bands = card["free_threshold"], card["confidence_bands"]
    val_bands = band_report(yv, pv, ft, bands)

    y, preds, h, ratio = evaluate_test(pairs, bundle, lookup, base_rate, args.data_dir / "test_predictions.parquet")
    log(f"test rows {len(y)}")
    overall = metric_table(y, preds, h)
    near_full = metric_table(y, preds, h, mask=ratio < 0.10)
    test_rel = reliability(y, preds["model"])
    test_bands = band_report(y, preds["model"], ft, bands)

    def brier(table, method, scope="all"):
        return next(r["brier"] for r in table if r["method"] == method and r["horizon"] == scope)

    verdict_nf = brier(near_full, "model") < brier(near_full, "persistence")
    verdict_all = brier(overall, "model") < brier(overall, "persistence")

    py, pp, pinfo = evaluate_profile(obs, profile, base_rate, cfg)
    prof_tbl = [{"method": "profile", **metrics(py, pp)},
                {"method": "always_free", **metrics(py, np.full(len(py), base_rate, np.float32))}]
    cov = coverage(obs, stats, profile, args.reports_dir / "uncovered_carparks.csv")

    split_rows = manifest["rows_per_split"]
    split_base = {s: (None if v is None else 1 - v) for s, v in manifest["label_free_0_share_per_split"].items()}
    result = {"overall": overall, "near_full": near_full, "test_reliability": test_rel.to_dict("records"),
              "validation_reliability": val_rel.to_dict("records"), "validation_bands": val_bands,
              "test_bands": test_bands, "profile": prof_tbl, "profile_info": pinfo, "coverage": cov,
              "free_threshold": ft, "confidence_bands": bands, "base_rate_free_per_split": split_base,
              "rows_per_split": split_rows, "model_beats_persistence_near_full": bool(verdict_nf),
              "model_beats_persistence_overall": bool(verdict_all)}
    (args.reports_dir / "evaluation.json").write_text(json.dumps(result, indent=2, default=str))

    card["test_brier"] = {s: {m: brier(overall, m, s) for m in METHODS} for s in ["all"] + list(HORIZONS)}
    card["test_brier_near_full_current_free_ratio_lt_0.10"] = {m: brier(near_full, m) for m in METHODS}
    (args.models_dir / "model_card.json").write_text(json.dumps(card, indent=2, default=str))

    head = ("**The model BEATS persistence on Brier score in the near-full subset (current_free_ratio < 0.10): "
            f"{brier(near_full, 'model'):.5f} vs {brier(near_full, 'persistence'):.5f}.**" if verdict_nf else
            "**The model does NOT beat persistence on Brier score in the near-full subset "
            f"(current_free_ratio < 0.10): model {brier(near_full, 'model'):.5f} vs persistence "
            f"{brier(near_full, 'persistence'):.5f}.**")
    head += (f"\n\nOverall test Brier: model {brier(overall, 'model'):.5f}, persistence "
             f"{brier(overall, 'persistence'):.5f}, always-free {brier(overall, 'always_free'):.5f}"
             f" ({'model better' if verdict_all else 'model NOT better than persistence'} overall).")
    mcols = ["horizon", "method", "rows", "brier", "log_loss", "roc_auc", "ap_not_free"]
    mheads = ["Horizon (min)", "Method", "Rows", "Brier", "Log loss", "ROC AUC", "AP (not free)"]
    for tbl in (overall, near_full):
        for r in tbl:
            r["horizon"] = str(r["horizon"])
    rcols = ["bin", "mean_predicted", "observed_free", "rows"]
    rheads = ["Bin", "Mean predicted", "Observed share free", "Rows"]
    bcols = ["band", "rows", "observed_free"]
    bheads = ["Band", "Rows", "Observed share free"]
    md = f"""# Evaluation (test split only)

{head}

Test split: decisions 2026-09-27 to 2026-10-07 14:30 Asia/Singapore. Nothing below was tuned on the test split.
Log loss clips probabilities to [1e-15, 1-1e-15]; persistence outputs exactly 0 or 1, so its log loss is dominated by the clip and is not comparable. AP is average precision for the "not free" class.

## Base rate of label_free = 1 (share free) and rows per split

| Split | Rows | Share free | Share not free |
|---|---|---|---|
""" + "\n".join(f"| {s} | {split_rows[s]:,} | {fmt(None if split_base[s] is None else split_base[s], 5)} | "
                f"{fmt(manifest['label_free_0_share_per_split'][s], 5)} |" for s in split_rows) + f"""

Always-free baseline predicts the train base rate {base_rate:.5f}.

## 1. All test rows, overall and per horizon

{md_table(overall, mcols, mheads)}

## 2. Near-full subset (current_free_ratio < 0.10)

{md_table(near_full, mcols, mheads)}

## 3. Reliability, short-horizon model on test (10 bins)

{md_table(test_rel.to_dict("records"), rcols, rheads)}

Validation reliability (used to choose the threshold and bands):

{md_table(val_rel.to_dict("records"), rcols, rheads)}

## 4. Threshold and confidence bands

Rule (applied to validation data only, on calibrated p_free):
- free_threshold = **{ft}**: the lowest reliability-bin lower edge from which every bin above it has an observed free share of at least 0.5.
- High lower bound = **{bands['high']}**: the lowest 0.01 bin edge from which every validation bin of width 0.01 (with at least 500 rows) has an observed free share of at least 99%.
- Medium lower bound = **{bands['medium']}**: the same with 90%, capped at the High bound. Below Medium is Low.
- The first version of this rule used the free share of all rows at or above a cut. It gave High = 0.45 on validation, because about 7.4M rows near p = 1 swamp the average. I found that on validation data, replaced it with the per-bin rule above, and reran. The test split was not used to choose either rule.

Test split, rows and observed share free per band:

{md_table(test_bands, bcols, bheads)}

Same bands on validation (for comparison):

{md_table(val_bands, bcols, bheads)}

## 5. Profile model, 24-hour horizon, test dates

The profile uses only train and validation dates, so the horizon does not change its prediction. Every test-date observation (stale ones excluded, each counted once at its observed_at) is scored against its carpark, day type and slot cell. Observations with no profile cell: {pinfo['without_profile_cell']:,} of {pinfo['observations']:,}, excluded from the metrics. Observed share free on the scored rows: {pinfo['base_rate_free']:.5f}.

{md_table(prof_tbl, ["method", "rows", "brier", "log_loss", "roc_auc", "ap_not_free"], ["Method", "Rows", "Brier", "Log loss", "ROC AUC", "AP (not free)"])}

## 6. Coverage

- Carparks in observations.parquet: {cov['carparks_in_observations']:,}
- With at least 1 train row: {cov['with_train_row']:,}
- With a profile cell for at least {WEEKDAY_SLOT_TARGET} of the 96 weekday slots: {cov['with_profile_80_weekday_slots']:,}
- With neither (no usable data), written to `ml/reports/uncovered_carparks.csv` with the last observed_at each reported: {cov['uncovered']:,}

Carparks that were rejected in every raw file never reach observations.parquet, so they are not in this count and have no last update time.
"""
    (args.reports_dir / "evaluation.md").write_text(md)
    log(f"done in {time.time() - t0:.0f}s, peak RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} MB")


if __name__ == "__main__":
    main()
