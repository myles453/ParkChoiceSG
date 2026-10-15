"""Step 5: evaluate both variants and two baselines on the HDB TEST split only.

    ../ml/.venv/bin/python evaluate.py        # writes reports/evaluation_hdb.md

Nothing is tuned here. Models, calibrators and the train base rate come from train.py's outputs.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import joblib
import numpy as np
import pyarrow.dataset as ds
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from features import FEATURES_B  # noqa: E402
from train import PAIRS, SPLIT_CODE, VARIANTS, load_split, predict_p_free  # noqa: E402

REPORT = HERE / "reports" / "evaluation_hdb.md"
FIRST_MODEL_REPORT = HERE.parent / "ml" / "reports" / "evaluation.md"
HORIZONS = (15, 30, 45, 60, 90)
LOW_COUNT = 10
EPS = 1e-15
METHODS = ("variant_a", "variant_b", "persistence", "always_free")


def log(msg: str) -> None:
    print(f"[evaluate] {msg}", flush=True)


def metrics(y: np.ndarray, p: np.ndarray) -> dict:
    n = int(len(y))
    if n == 0:
        return {"rows": 0, "brier": None, "log_loss": None, "roc_auc": None, "ap_not_free": None}
    p = p.astype(np.float64)
    pc = np.clip(p, EPS, 1 - EPS)
    ll = float(-np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc)))
    return {"rows": n, "brier": float(brier_score_loss(y, p)), "log_loss": ll,
            "roc_auc": float(roc_auc_score(y, p)) if 0 < y.sum() < n else None,
            "ap_not_free": float(average_precision_score(1 - y, 1 - p)) if y.sum() < n else None}


def base_rates(path: Path) -> dict:
    out = {}
    dataset = ds.dataset(path)
    for name, code in SPLIT_CODE.items():
        n = free = 0
        for b in dataset.to_batches(columns=["label_free"], filter=ds.field("split") == code):
            y = b.column("label_free").to_numpy(zero_copy_only=False)
            n += len(y)
            free += int(y.sum())
        out[name] = {"rows": n, "share_free": free / n if n else None}
    return out


def fmt(v, d=4) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    return f"{v:,}" if isinstance(v, (int, np.integer)) else f"{v:.{d}f}"


def table(rows: list[dict], cols: list[str], heads: list[str]) -> str:
    out = ["| " + " | ".join(heads) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    out += ["| " + " | ".join(r[c] if isinstance(r[c], str) else fmt(r[c]) for c in cols) + " |" for r in rows]
    return "\n".join(out)


def metric_rows(y, preds, horizon, mask=None) -> list[dict]:
    rows = []
    for scope in ["all", *HORIZONS]:
        sel = np.ones(len(y), bool) if mask is None else mask.copy()
        if scope != "all":
            sel &= horizon == scope
        for m in METHODS:
            rows.append({"horizon": str(scope), "method": m, **metrics(y[sel], preds[m][sel])})
    return rows


def reliability(y, p) -> list[dict]:
    idx = np.minimum((p * 10).astype(int), 9)
    rows = []
    for b in range(10):
        s = idx == b
        rows.append({"bin": f"{b / 10:.1f}-{(b + 1) / 10:.1f}", "mean_pred": float(p[s].mean()) if s.any() else None,
                     "observed": float(y[s].mean()) if s.any() else None, "rows": int(s.sum())})
    return rows


def first_model_brier() -> dict:
    """Overall and per-horizon Brier of the first (HDB) model, read from its evaluation.md section 1."""
    text = FIRST_MODEL_REPORT.read_text()
    section = text.split("## 1.")[1].split("## 2.")[0]
    out = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 4 and cells[1] == "model":
            out[cells[0]] = float(cells[3])
    head = re.search(r"Overall test Brier: model ([0-9.]+)", text)
    if head:
        out["all"] = float(head.group(1))
    return out


def main() -> None:
    card = json.loads((HERE / "models" / "model_card.json").read_text())
    rates = base_rates(PAIRS)
    train_rate = rates["train"]["share_free"]
    log(f"base rates {rates}")
    X, y, _ = load_split(PAIRS, "test", FEATURES_B)
    y = y.astype(np.int8)
    col = {n: i for i, n in enumerate(FEATURES_B)}
    cur, horizon = X[:, col["current_available"]], X[:, col["horizon_minutes"]].astype(int)
    preds = {"persistence": (cur >= 1).astype(np.float32),
             "always_free": np.full(len(y), train_rate, np.float32)}
    importance = {}
    for key, names in VARIANTS.items():
        art = joblib.load(HERE / "models" / f"variant_{key}.joblib")
        assert art["feature_names"] == names
        preds[f"variant_{key}"] = predict_p_free(art, X[:, [col[n] for n in names]]).astype(np.float32)
        m = art["model"]
        gain, split = m.feature_importance("gain"), m.feature_importance("split")
        importance[key] = sorted(zip(names, gain / gain.sum(), split), key=lambda t: -t[1])
    low = cur <= LOW_COUNT
    free_now = cur >= 1
    changed = free_now != (y == 1)

    tables = {"all": metric_rows(y, preds, horizon), "low": metric_rows(y, preds, horizon, low)}
    cols = ["horizon", "method", "rows", "brier", "log_loss", "roc_auc", "ap_not_free"]
    heads = ["Horizon (min)", "Method", "Rows", "Brier", "Log loss", "ROC AUC", "AP (not free)"]

    def brier(rows, method, horizon="all"):
        return next(r["brier"] for r in rows if r["method"] == method and r["horizon"] == horizon)

    verdict = []
    for v in ("variant_a", "variant_b"):
        for scope, rows in (("overall", tables["all"]), (f"low-count subset (current_available <= {LOW_COUNT})", tables["low"])):
            b, p = brier(rows, v), brier(rows, "persistence")
            verdict.append(f"- {v.replace('_', ' ').title()} {'BEATS' if b < p else 'does NOT beat'} persistence on Brier, "
                           f"{scope}: {b:.5f} vs {p:.5f}.")

    out = ["# HDB evaluation of the retrieval-view models (test split only)", "",
           "**Does each variant beat persistence on Brier score?**", "", *verdict, "",
           "**This evaluation says nothing yet about LTA and URA carparks.** Both variants were trained and tested on "
           "HDB data reshaped to look like an LTA/URA feed. Whether the reshaping is faithful is exactly what "
           "validation on collected LTA/URA readings has to show.", "",
           "Test split: decisions 2026-09-27 to 2026-10-07 14:30 Asia/Singapore. Nothing below was tuned on the test "
           "split: hyperparameters and calibrators were chosen on validation. Log loss clips probabilities to "
           "[1e-15, 1-1e-15]; persistence outputs exactly 0 or 1, so its log loss is dominated by the clip. AP is "
           f"average precision for the \"not free\" class. Always-free predicts the train base rate {train_rate:.5f}.", "",
           "## Base rate of label_free (share free) per split", "",
           table([{"split": k, "rows": v["rows"], "share_free": v["share_free"], "not_free": 1 - v["share_free"]}
                  for k, v in rates.items()], ["split", "rows", "share_free", "not_free"],
                 ["Split", "Rows", "Share free", "Share not free"]), "",
           "## 1. All test rows", "", table(tables["all"], cols, heads), "",
           f"## 2. Low-count subset (current_available <= {LOW_COUNT})", "",
           "Replaces the first model's near-full subset, because no capacity exists here.", "",
           table(tables["low"], cols, heads), ""]
    out += ["## 3. Reliability (10 bins of calibrated p_free, test)", ""]
    for key in ("a", "b"):
        out += [f"Variant {key.upper()}:", "", table(reliability(y, preds[f"variant_{key}"]),
                ["bin", "mean_pred", "observed", "rows"], ["Bin", "Mean predicted", "Observed share free", "Rows"]), ""]
    out += ["## 4. State unchanged vs changed between decision and arrival", "",
            "\"State\" is the free status: current_available >= 1 versus label_free. Unchanged means they agree.", ""]
    rows = []
    for name, sel in (("unchanged", ~changed), ("changed", changed)):
        r = {"group": name, "rows": int(sel.sum())}
        for m in ("variant_a", "variant_b", "persistence"):
            r[m] = metrics(y[sel], preds[m][sel])["brier"]
        rows.append(r)
    out += [table(rows, ["group", "rows", "variant_a", "variant_b", "persistence"],
                  ["Group", "Rows", "Brier A", "Brier B", "Brier persistence"]), ""]
    ref = first_model_brier()
    out += ["## 5. First model (reference only)", "",
            "Copied from ml/reports/evaluation.md. **The row sets differ**: the first model uses the per-carpark HDB "
            "history, capacity, reading age (up to 15 minutes) and source-time readings; these variants use "
            "retrieval-time readings at most 6 minutes old and a different label tolerance, so the numbers are not "
            "a like-for-like comparison.", ""]
    rows = [{"horizon": str(h), "first": ref.get(str(h)), "a": brier(tables["all"], "variant_a", str(h)),
             "b": brier(tables["all"], "variant_b", str(h))} for h in ("all", *HORIZONS)]
    out += [table(rows, ["horizon", "first", "a", "b"], ["Horizon (min)", "First model Brier", "Variant A Brier", "Variant B Brier"]), ""]
    out += ["## 6. Feature importance", "", "Share of total gain, and split count.", ""]
    for key in ("a", "b"):
        out += [f"Variant {key.upper()}:", "", table([{"f": n, "g": g, "s": int(s)} for n, g, s in importance[key]],
                ["f", "g", "s"], ["Feature", "Gain share", "Splits"]), ""]
    out += ["## 7. Training summary", "", "```json", json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "feature_names"}
            for k, v in card["variants"].items()}, indent=1), "```", ""]
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(out))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
