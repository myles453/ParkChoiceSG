"""Step 4: train variants A and B (LightGBM binary on label_free), calibrate on validation.

    ../ml/.venv/bin/python train.py

Train rows: a uniform hash sample (sample_hash, derived from carpark/decision/horizon only, never the
label) of at most 8 million rows. Validation rows (all of them) drive early stopping and the isotonic
calibrator. Writes models/variant_a.joblib, models/variant_b.joblib (dict: model, calibrator,
feature_names) and models/model_card.json. Nothing here reads the test split.
"""
from __future__ import annotations

import json
import os
import resource
import sys
import time
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pyarrow.dataset as ds
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import log_loss

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from features import FEATURES_A, FEATURES_B  # noqa: E402

PAIRS = HERE / "data" / "hdb_pairs.parquet"
MODELS = HERE / "models"
MAX_TRAIN_ROWS = 8_000_000
SAMPLE_TARGET = 7_900_000  # aim below the cap so the hash sample cannot exceed it
NUM_THREADS = max(1, (os.cpu_count() or 3) - 2)
VARIANTS = {"a": FEATURES_A, "b": FEATURES_B}
SPLIT_CODE = {"train": 0, "validation": 1, "test": 2}

# At most five configurations per variant.
CONFIGS = [
    {"learning_rate": 0.1, "num_leaves": 63, "min_data_in_leaf": 200, "feature_fraction": 1.0},
    {"learning_rate": 0.1, "num_leaves": 127, "min_data_in_leaf": 500, "feature_fraction": 0.9},
    {"learning_rate": 0.05, "num_leaves": 63, "min_data_in_leaf": 1000, "feature_fraction": 0.8},
    {"learning_rate": 0.05, "num_leaves": 255, "min_data_in_leaf": 2000, "feature_fraction": 0.8},
    {"learning_rate": 0.1, "num_leaves": 31, "min_data_in_leaf": 100, "feature_fraction": 1.0},
]
MAX_ROUNDS, EARLY_STOP = 1500, 50


def log(msg: str) -> None:
    print(f"[train] {msg}", flush=True)


def load_split(path: Path, split: str, columns: list[str], hash_below: int | None = None,
               extra: list[str] | None = None, batch_rows: int = 500_000):
    """Read one split in batches; return (X float32, y int8, extras dict). Never loads the whole file."""
    dataset = ds.dataset(path)
    flt = ds.field("split") == SPLIT_CODE[split]
    if hash_below is not None:
        flt = flt & (ds.field("sample_hash") < hash_below)
    extra = extra or []
    xs, ys, ex = [], [], {c: [] for c in extra}
    for batch in dataset.to_batches(columns=columns + ["label_free"] + extra, filter=flt, batch_size=batch_rows):
        xs.append(np.column_stack([batch.column(c).to_numpy(zero_copy_only=False).astype(np.float32)
                                   for c in columns]))
        ys.append(batch.column("label_free").to_numpy(zero_copy_only=False).astype(np.int8))
        for c in extra:
            ex[c].append(batch.column(c).to_numpy(zero_copy_only=False))
    X = np.concatenate(xs) if xs else np.empty((0, len(columns)), np.float32)
    y = np.concatenate(ys) if ys else np.empty(0, np.int8)
    return X, y, {c: (np.concatenate(v) if v else np.empty(0)) for c, v in ex.items()}


def fit_variant(Xtr, ytr, Xva, yva, names: list[str], configs=CONFIGS, num_threads: int = NUM_THREADS):
    """Try each config, keep the one with the lowest validation log loss, fit the isotonic calibrator."""
    dparams = {"feature_pre_filter": False}  # lets min_data_in_leaf differ per config
    dtrain = lgb.Dataset(Xtr, ytr, feature_name=names, params=dparams, free_raw_data=False)
    dvalid = lgb.Dataset(Xva, yva, reference=dtrain, feature_name=names, params=dparams, free_raw_data=False)
    tried, best = [], None
    for cfg in configs[:5]:
        params = {"objective": "binary", "metric": "binary_logloss", "num_threads": num_threads,
                  "verbose": -1, "seed": 7, **cfg}
        t0 = time.time()
        model = lgb.train(params, dtrain, num_boost_round=MAX_ROUNDS, valid_sets=[dvalid],
                          callbacks=[lgb.early_stopping(EARLY_STOP, verbose=False)])
        raw = model.predict(Xva, num_iteration=model.best_iteration)
        loss = float(log_loss(yva, raw, labels=[0, 1]))
        tried.append({**cfg, "best_iteration": int(model.best_iteration), "validation_log_loss": loss,
                      "seconds": round(time.time() - t0, 1)})
        log(f"  {tried[-1]}")
        if best is None or loss < best[0]:
            best = (loss, model, raw, cfg)
    _, model, raw, cfg = best
    calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    calibrator.fit(raw, yva)
    return model, calibrator, {"chosen_config": cfg, "configs_tried": tried}


def save_variant(path: Path, model, calibrator, names: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "calibrator": calibrator, "feature_names": list(names)}, path)


def predict_p_free(artefact: dict, X: np.ndarray) -> np.ndarray:
    model = artefact["model"]
    raw = model.predict(X, num_iteration=model.best_iteration)
    return artefact["calibrator"].predict(raw)


def main() -> None:
    manifest = json.loads((PAIRS.parent / "hdb_pairs.manifest.json").read_text())
    n_train = manifest["rows_per_split"]["train"]
    frac = min(1.0, SAMPLE_TARGET / n_train)
    threshold = int(frac * 2**32)
    log(f"cores={os.cpu_count()} num_threads={NUM_THREADS}; train rows {n_train:,}, sample fraction {frac:.4f}")
    card = {"cores": os.cpu_count(), "num_threads": NUM_THREADS, "train_rows_available": n_train,
            "train_sample_fraction": frac, "max_train_rows": MAX_TRAIN_ROWS, "variants": {}}
    for key, names in VARIANTS.items():
        Xtr, ytr, _ = load_split(PAIRS, "train", names, hash_below=threshold)
        assert len(ytr) <= MAX_TRAIN_ROWS, len(ytr)
        Xva, yva, _ = load_split(PAIRS, "validation", names)
        log(f"variant {key.upper()}: train {len(ytr):,} rows (free {ytr.mean():.4f}), validation {len(yva):,}")
        model, calibrator, info = fit_variant(Xtr, ytr, Xva, yva, names)
        save_variant(MODELS / f"variant_{key}.joblib", model, calibrator, names)
        card["variants"][key] = {"feature_names": names, "train_rows_used": int(len(ytr)),
                                 "train_share_free": float(ytr.mean()), "validation_rows": int(len(yva)),
                                 "validation_share_free": float(yva.mean()),
                                 "best_iteration": int(model.best_iteration), **info}
        del Xtr, Xva
    card["peak_rss_gb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 2)
    (MODELS / "model_card.json").write_text(json.dumps(card, indent=2))
    log("done")


if __name__ == "__main__":
    main()
