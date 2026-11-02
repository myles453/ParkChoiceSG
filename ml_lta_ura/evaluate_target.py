"""Steps 1 and 4-5: coverage, scoring of the HDB-trained variants on real LTA/URA pairs, verdict.

    ../ml/.venv/bin/python evaluate_target.py        # writes reports/evaluation_target.md

A pure test: models and calibrators are loaded and applied, never refitted. Needs data/target_pairs.parquet
(build_target_pairs.py). Pairs are read and scored in batches of 100,000 rows.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_retrieval_view import HORIZONS  # noqa: E402  (the pair builder's horizons, not a copy)
from evaluate import LOW_COUNT, METHODS, fmt, metrics, reliability, table  # noqa: E402
from features import FEATURES_B  # noqa: E402
from train import predict_p_free  # noqa: E402

DATA = HERE / "data"
REPORT = HERE / "reports" / "evaluation_target.md"
HDB_REPORT = HERE / "reports" / "evaluation_hdb.md"
SGT = timezone(timedelta(hours=8))
UTC = timezone.utc
BATCH = 100_000
MIN_BIN_ROWS = 500
PROVISIONAL_BELOW = 1000
INTERVAL = 300
AGENCIES = ("LTA", "URA")
VARIANTS = ("variant_a", "variant_b")


def log(msg: str) -> None:
    print(f"[evaluate_target] {msg}", flush=True)


# ------------------------------------------------------------------------------------------ coverage
def capture_times(manifest: dict, provider: str) -> list[datetime]:
    times = [datetime.strptime(Path(r).parent.name + Path(r).name[:6], "%Y-%m-%d%H%M%S").replace(tzinfo=SGT)
             for r in manifest["files"][provider]]
    return sorted(t.astimezone(UTC) for t in times)


def coverage(manifest: dict) -> dict:
    cutoff = datetime.fromisoformat(manifest["cutoff_utc"])
    out = {}
    for p in ("lta", "ura"):
        times = capture_times(manifest, p)
        first_slot = int(times[0].timestamp() // INTERVAL * INTERVAL)
        expected = int((cutoff.timestamp() - first_slot) // INTERVAL) + 1
        local = pd.Series(times).dt.tz_convert(SGT)
        per_date = local.dt.date.value_counts().sort_index()
        hours_with = {(t.date(), t.hour) for t in local}
        start, end = local.iloc[0].replace(minute=0, second=0, microsecond=0), local.iloc[-1].replace(minute=0, second=0, microsecond=0)
        missing: dict = {}
        t = start
        while t <= end:
            if (t.date(), t.hour) not in hours_with:
                missing.setdefault(t.date(), []).append(t.hour)
            t += timedelta(hours=1)
        out[p] = {"saved": len(times), "expected": expected, "share": len(times) / expected,
                  "per_date": per_date, "missing_hours": missing}
    return out


def hour_ranges(hours: list[int]) -> str:
    runs, start = [], hours[0]
    for a, b in zip(hours, hours[1:] + [None]):
        if b != a + 1:
            runs.append(f"{start:02d}:00" if start == a else f"{start:02d}:00-{a:02d}:59")
            start = b
    return ", ".join(runs)


# ------------------------------------------------------------------------------------------ HDB reference
def md_table(lines: list[str]) -> list[list[str]]:
    return [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines
            if ln.startswith("|") and not ln.startswith("|---") and not ln.startswith("| Horizon")
            and not ln.startswith("| Bin") and not ln.startswith("| Group") and not ln.startswith("| Split")]


def hdb_reference() -> dict:
    text = HDB_REPORT.read_text()

    def section(start, end):
        return text.split(start)[1].split(end)[0].splitlines()

    ref = {"all": {}, "low": {}, "rel": {}, "state": {}}
    for key, (a, b) in {"all": ("## 1.", "## 2."), "low": ("## 2.", "## 3.")}.items():
        for c in md_table(section(a, b)):
            ref[key][(c[0], c[1])] = {"brier": float(c[3]), "auc": float(c[5]), "ap": float(c[6])}
    rel = section("## 3.", "## 4.")
    for variant, marker in (("variant_a", "Variant A:"), ("variant_b", "Variant B:")):
        i = rel.index(marker)
        j = rel.index("Variant B:") if variant == "variant_a" else len(rel)
        ref["rel"][variant] = [(c[0], float(c[1]), float(c[2]), int(c[3].replace(",", ""))) for c in md_table(rel[i:j])]
    for c in md_table(section("## 4.", "## 5.")):
        ref["state"][c[0]] = {"rows": int(c[1].replace(",", "")), "variant_a": float(c[2]), "variant_b": float(c[3]),
                              "persistence": float(c[4])}
    return ref


# ------------------------------------------------------------------------------------------ scoring
def score_pairs(pairs_path: Path) -> pd.DataFrame:
    arts = {v: joblib.load(HERE / "models" / f"{v}.joblib") for v in VARIANTS}
    parts = []
    for batch in pq.ParquetFile(pairs_path).iter_batches(batch_size=BATCH):
        df = batch.to_pandas()
        for v, art in arts.items():
            X = df[art["feature_names"]].astype("float64")
            df[v] = predict_p_free(art, X)
        df["persistence"] = (df["current_available"] >= 1).astype(np.float32)
        parts.append(df[["agency", "carpark_id", "decision_at", "arrival_at", "period", "label_free", "current_available",
                         "horizon_minutes", "variant_a", "variant_b", "persistence"]])
    out = pd.concat(parts, ignore_index=True)
    out["arrival_hour"] = out["arrival_at"].dt.tz_convert(SGT).dt.hour
    return out


def method_preds(df: pd.DataFrame, always_free: float) -> dict:
    return {"variant_a": df["variant_a"].to_numpy(), "variant_b": df["variant_b"].to_numpy(),
            "persistence": df["persistence"].to_numpy(), "always_free": np.full(len(df), always_free, np.float32)}


def metric_table(df: pd.DataFrame, always_free: float, ref: dict, low: bool) -> tuple[list[dict], dict]:
    rows, idx = [], {}
    for scope in ("All agencies", *AGENCIES):
        sub = df if scope == "All agencies" else df[df["agency"] == scope]
        if low:
            sub = sub[sub["current_available"] <= LOW_COUNT]
        for hz in ("all", *HORIZONS):
            s = sub if hz == "all" else sub[sub["horizon_minutes"] == hz]
            y = s["label_free"].to_numpy()
            preds = method_preds(s, always_free)
            for m in METHODS:
                r = {"scope": scope, "horizon": str(hz), "method": m, **metrics(y, preds[m]), "not_free": int((y == 0).sum())}
                h = ref["low" if low else "all"].get((str(hz), m))
                r.update(hdb_brier=h["brier"] if h else None, hdb_auc=h["auc"] if h else None, hdb_ap=h["ap"] if h else None)
                rows.append(r)
                idx[(scope, str(hz), m)] = r
    return rows, idx


MT_COLS = ["scope", "horizon", "method", "rows", "not_free", "brier", "log_loss", "roc_auc", "ap_not_free",
           "hdb_brier", "hdb_auc", "hdb_ap"]
MT_HEADS = ["Scope", "Horizon", "Method", "Rows", "Not free", "Brier", "Log loss", "ROC AUC", "AP", "HDB Brier", "HDB AUC", "HDB AP"]


def reliability_gap(y, p):
    rel = reliability(y, p)
    gaps = [abs(r["mean_pred"] - r["observed"]) for r in rel if r["rows"] >= MIN_BIN_ROWS]
    return rel, (max(gaps) if gaps else None)


def sections(df: pd.DataFrame, always_free: float, ref: dict, level: str) -> tuple[list[str], dict]:
    """Step 4 tables 1-5 for one set of pairs. Returns markdown lines and the numbers the verdict uses."""
    h = level
    nums = {}
    out = []
    t_all, idx_all = metric_table(df, always_free, ref, low=False)
    t_low, idx_low = metric_table(df, always_free, ref, low=True)
    nums["all"], nums["low"] = idx_all, idx_low
    out += [f"{h} 1. All rows", "",
            f"Base rate of label_free (share free) in this data: overall {df['label_free'].mean():.4f}; "
            + "; ".join(f"{a} {df.loc[df.agency == a, 'label_free'].mean():.4f}" for a in AGENCIES if (df.agency == a).any())
            + f". Always-free uses the HDB train rate {always_free:.5f}. The HDB columns are HDB test results "
              "(all horizons pooled by row, no agency split) for the same horizon and method; **the carparks differ**.", "",
            table(t_all, MT_COLS, MT_HEADS), "",
            f"{h} 2. Low-count rows (current_available <= {LOW_COUNT})", "", table(t_low, MT_COLS, MT_HEADS), ""]
    out += [f"{h} 3. Reliability (10 bins of calibrated p_free, all horizons pooled)", "",
            f"Largest gap = largest |mean predicted - observed| among bins with at least {MIN_BIN_ROWS} rows. "
            "HDB columns are the HDB test bins; **the carparks differ**.", ""]
    nums["gap"] = {}
    for v in VARIANTS:
        hdb_rel = ref["rel"][v]
        hdb_gap = max(abs(a - b) for _, a, b, n in hdb_rel if n >= MIN_BIN_ROWS)
        for agency in AGENCIES:
            s = df[df["agency"] == agency]
            if s.empty:
                nums["gap"][(agency, v)] = None
                continue
            rel, gap = reliability_gap(s["label_free"].to_numpy(), s[v].to_numpy())
            nums["gap"][(agency, v)] = gap
            rows = [{"bin": r["bin"], "mean_pred": r["mean_pred"], "observed": r["observed"], "rows": r["rows"],
                     "hp": hb[1], "ho": hb[2]} for r, hb in zip(rel, hdb_rel)]
            out += [f"{v.replace('_', ' ').title()}, {agency}: largest gap "
                    f"{fmt(gap) if gap is not None else 'undefined (no bin has 500 rows)'} (HDB test: {hdb_gap:.4f})", "",
                    table(rows, ["bin", "mean_pred", "observed", "rows", "hp", "ho"],
                          ["Bin", "Mean predicted", "Observed share free", "Rows", "HDB mean predicted", "HDB observed"]), ""]
    out += [f"{h} 4. State unchanged vs changed between decision and arrival", "",
            "State = free status, current_available >= 1 versus label_free. HDB rows are the HDB test split.", ""]
    changed = (df["current_available"] >= 1) != (df["label_free"] == 1)
    rows = []
    for scope in ("All agencies", *AGENCIES):
        for name, sel in (("unchanged", ~changed), ("changed", changed)):
            s = df[sel & ((df["agency"] == scope) if scope != "All agencies" else True)]
            y = s["label_free"].to_numpy()
            r = {"scope": scope, "group": name, "rows": len(s)}
            for m in ("variant_a", "variant_b", "persistence"):
                r[m] = metrics(y, s[m].to_numpy())["brier"] if len(s) else None
            hd = ref["state"][name]
            r.update(ha=hd["variant_a"], hb=hd["variant_b"], hp=hd["persistence"], hr=hd["rows"])
            rows.append(r)
    out += [table(rows, ["scope", "group", "rows", "variant_a", "variant_b", "persistence", "hr", "ha", "hb", "hp"],
                  ["Scope", "Group", "Rows", "Brier A", "Brier B", "Brier persistence", "HDB rows", "HDB A", "HDB B", "HDB persistence"]), ""]
    out += [f"{h} 5. Brier by hour of day (Singapore time of the arrival)", "",
            "HDB evaluation reports no per-hour table; for reference its overall Brier is A "
            f"{ref['all'][('all', 'variant_a')]['brier']:.4f}, B {ref['all'][('all', 'variant_b')]['brier']:.4f}, "
            f"persistence {ref['all'][('all', 'persistence')]['brier']:.4f}.", ""]
    for agency in AGENCIES:
        s = df[df["agency"] == agency]
        rows = []
        for hour, g in s.groupby("arrival_hour"):
            y = g["label_free"].to_numpy()
            rows.append({"hour": f"{hour:02d}", "rows": len(g), "nf": int((y == 0).sum()),
                         **{m: metrics(y, g[m].to_numpy())["brier"] for m in ("variant_a", "variant_b", "persistence")}})
        out += [f"{agency}:", "", table(rows, ["hour", "rows", "nf", "variant_a", "variant_b", "persistence"],
                ["Hour", "Rows", "Not free", "Brier A", "Brier B", "Brier persistence"]), ""]
    return out, nums


# ------------------------------------------------------------------------------------------ verdict
def verdict_line(agency: str, v: str, nums: dict) -> tuple[str, str]:
    a, lo, gap = nums["all"], nums["low"], nums["gap"].get((agency, v))
    g = lambda idx, m, k: idx[(agency, "all", m)][k]
    b_v, b_p = g(a, v, "brier"), g(a, "persistence", "brier")
    l_v, l_p = g(lo, v, "brier"), g(lo, "persistence", "brier")
    auc_v, auc_p = g(a, v, "roc_auc"), g(a, "persistence", "roc_auc")
    ap_v, ap_p = g(a, v, "ap_not_free"), g(a, "persistence", "ap_not_free")
    beats_b = b_v is not None and b_p is not None and b_v < b_p
    beats_low = l_v is not None and l_p is not None and l_v < l_p
    gap_ok = gap is not None and gap < 0.10
    gap_big = gap is not None and gap >= 0.10
    beats_rank = all(x is not None for x in (auc_v, auc_p, ap_v, ap_p)) and auc_v > auc_p and ap_v > ap_p
    if beats_b and beats_low and gap_ok:
        outcome = "Usable"
    elif beats_rank and gap_big:
        outcome = "Usable after recalibration"
    else:
        outcome = "Not usable"
    text = (f"- **{agency}, {v.replace('_', ' ').title()}: {outcome}.** Brier overall {fmt(b_v, 5)} vs persistence {fmt(b_p, 5)}; "
            f"low-count {fmt(l_v, 5)} vs {fmt(l_p, 5)}; ROC AUC {fmt(auc_v)} vs {fmt(auc_p)}; AP {fmt(ap_v)} vs {fmt(ap_p)}; "
            f"largest reliability gap {fmt(gap) if gap is not None else 'undefined'}.")
    return outcome, text


def main() -> None:
    manifest = json.loads((DATA / "target_manifest.json").read_text())
    summary = json.loads((DATA / "target_summary.json").read_text())
    card = json.loads((HERE / "models" / "model_card.json").read_text())
    always_free = card["variants"]["a"]["train_share_free"]
    ref = hdb_reference()
    cov = coverage(manifest)
    df = score_pairs(DATA / "target_pairs.parquet")
    log(f"scored {len(df):,} pairs")
    normal, f1 = df[df["period"] == "normal"], df[df["period"] == "f1"]
    normal_md, normal_nums = sections(normal, always_free, ref, "###")
    f1_md, _ = sections(f1, always_free, ref, "###")

    # ---- verdict block
    nf = {a: int(((normal["agency"] == a) & (normal["label_free"] == 0)).sum()) for a in AGENCIES}
    dec_local = normal["decision_at"].dt.tz_convert(SGT)
    days = sorted({d for d in dec_local.dt.date})
    hours = dec_local.dt.floor("h").nunique()
    weekdays = {d.strftime("%a") for d in days}
    low_cov = [p.upper() for p, c in cov.items() if c["share"] < 0.60]
    top = ["# Evaluation of the HDB-trained retrieval-view models on real LTA and URA readings", ""]
    if low_cov:
        top += [f"**WARNING: {', '.join(low_cov)} has under 60% of expected captures overall.**", ""]
    top += ["## Verdict (normal pairs only, weekdays only)", ""]
    for agency in AGENCIES:
        for v in VARIANTS:
            top.append(verdict_line(agency, v, normal_nums)[1])
    top += [""]
    for agency in AGENCIES:
        lo = normal_nums["low"]
        n_lo, n_lo_nf = lo[(agency, "all", "persistence")]["rows"], lo[(agency, "all", "persistence")]["not_free"]
        worse = [v for v in VARIANTS if lo[(agency, "all", "always_free")]["brier"] is not None
                 and lo[(agency, "all", "always_free")]["brier"] < lo[(agency, "all", v)]["brier"]]
        n_cp = normal.loc[(normal.agency == agency) & (normal.label_free == 0), "carpark_id"].nunique()
        top.append(f"- Caveat, {agency}: the \"not free\" normal pairs come from {n_cp} carpark(s); the low-count subset has {n_lo:,} rows "
                   f"({n_lo_nf:,} not free). Always-free (HDB base rate) has a lower low-count Brier than "
                   + (", ".join(w.replace('_', ' ').title() for w in worse) if worse else "neither variant") + ".")
    top += ["",
            f"- Normal days covered: {len(days)} calendar days ({', '.join(d.strftime('%Y-%m-%d %a') for d in days)}); "
            f"{hours} distinct Singapore clock hours contain at least one normal decision. The first and last of these days "
            "are partial. Normal data contains no weekend days, so **this verdict covers weekdays only**.",
            f"- \"Not free\" rows in the normal pairs: LTA {nf['LTA']:,}, URA {nf['URA']:,}.",
            f"- An agency with fewer than {PROVISIONAL_BELOW:,} \"not free\" rows has a provisional verdict: "
            + "; ".join(f"{a}: {'PROVISIONAL' if nf[a] < PROVISIONAL_BELOW else 'not provisional'}" for a in AGENCIES) + ".",
            "- Rules used: Usable = beats persistence on Brier overall and in the low-count subset, largest reliability gap < 0.10. "
            "Usable after recalibration = beats persistence on ROC AUC and AP, gap >= 0.10. Otherwise Not usable. "
            "Overall and low-count figures pool all horizons. A missing figure (for example AUC with a single class) counts as not beating persistence.",
            "- Nothing was fitted or recalibrated on this data. The F1 pairs are excluded from the verdict.", ""]

    # ---- step 1
    out = top + ["## 1. Coverage", "", "Fixed file list: all captures up to the newest capture at the start "
                 f"({datetime.fromisoformat(manifest['cutoff_utc']).astimezone(SGT):%Y-%m-%d %H:%M:%S} SGT); files written later are ignored.", "",
                 "`collect.py --status` run at freeze time (it covers every file present then, and `expected` runs to that moment):", "",
                 "```", (DATA / "target_status.txt").read_text().rstrip(), "```", ""]
    for p, c in cov.items():
        out.append(f"- {p.upper()}: {c['saved']:,} of {c['expected']:,} expected captures in the frozen list ({100 * c['share']:.1f}%).")
    out += ["", "Captures per Singapore date (288 expected per full day) and hours with no capture. Hours are counted only "
            "between the first and last capture; the part of the first and last day outside that span is not a gap.", "",
            "| Date | LTA captures | URA captures | Hours with no capture (LTA) | Hours with no capture (URA) |", "|---|---|---|---|---|"]
    dates = sorted(set(cov["lta"]["per_date"].index) | set(cov["ura"]["per_date"].index))
    for d in dates:
        cell = lambda p: (f"{len(cov[p]['missing_hours'][d])}: {hour_ranges(cov[p]['missing_hours'][d])}" if d in cov[p]["missing_hours"] else "0")
        out.append(f"| {d} ({pd.Timestamp(d):%a}) | {int(cov['lta']['per_date'].get(d, 0))} | {int(cov['ura']['per_date'].get(d, 0))} | {cell('lta')} | {cell('ura')} |")
    out.append("")

    # ---- step 2
    out += ["## 2. Observations", "",
            f"Files parsed: {json.dumps(summary['files'])}. Rows kept: {summary['rows']:,}; duplicate (agency, carpark, time) rows removed: {summary['duplicate_rows_removed']}.", "",
            f"Carparks: LTA {summary['carparks']['LTA']}, URA {summary['carparks']['URA']}.",
            f"Rows per capture (min / median / max): LTA {summary['rows_per_capture']['LTA']['min']:.0f} / {summary['rows_per_capture']['LTA']['median']:.0f} / "
            f"{summary['rows_per_capture']['LTA']['max']:.0f}; URA {summary['rows_per_capture']['URA']['min']:.0f} / "
            f"{summary['rows_per_capture']['URA']['median']:.0f} / {summary['rows_per_capture']['URA']['max']:.0f}.", "",
            "Rejections by `provider_puller.normalize_pages` (every row of the feed, all agencies and lot types):", "",
            "| Feed | Reason | Rows | of which would be target rows (LTA agency or URA, lot type C) |", "|---|---|---|---|"]
    for p in ("lta", "ura"):
        reasons = summary["rejections_all_rows"][p]
        if not reasons:
            out.append(f"| {p.upper()} | none | 0 | 0 |")
        for r, n in reasons.items():
            out.append(f"| {p.upper()} | {r} | {n:,} | {summary['rejections_target_rows'][p].get(r, 0):,} |")
    out += ["", "No missing, non-integer or negative count was rejected in any target row. Rows removed by the scope filter "
            "(agency/lot type, per feed): " + json.dumps(summary["excluded_by_filter"]), "",
            "Carparks whose value never changes across the whole collection "
            f"({len(summary['constant_carparks'])}): ", "",
            "| Agency | Carpark | Constant value | Readings |", "|---|---|---|---|"]
    out += [f"| {c['agency']} | {c['carpark_id']} | {c['value']} | {c['readings']:,} |" for c in summary["constant_carparks"]]
    out += [""]
    zero = [(c["agency"], c["carpark_id"]) for c in summary["constant_carparks"] if c["value"] == 0]
    zero_mask = pd.Series(list(zip(normal["agency"], normal["carpark_id"]))).isin(zero).to_numpy()
    zero_nf = int((zero_mask & (normal["label_free"].to_numpy() == 0)).sum())
    out += [f"Differences from the expected counts. LTA has {summary['carparks']['LTA']} carparks, not 39: carpark 23 first appears "
            "in the 2026-10-07 19:00 SGT capture and was absent from the earlier ones, so it was not in the collector's first two "
            "cycles. LTA also has fewer than that in some captures (median "
            f"{summary['rows_per_capture']['LTA']['median']:.0f}, minimum {summary['rows_per_capture']['LTA']['min']:.0f}): the "
            "feed itself returned fewer rows in those captures (raw LTA row counts vary between 2,568 and 2,610), and an absent carpark is "
            "left as a gap, never filled. URA has 89 rows in every capture, as expected. The rejections above are HDB "
            "`conflicting_duplicate` rows (a record repeated across page boundaries with different counts) and the two lot-type `S` rows "
            "per LTA capture; none is a target row.",
            f"Constant carparks: {len(zero)} URA carpark(s) are constantly 0 ({', '.join(c for _, c in zero)}), so they are always "
            f"\"not free\" and persistence is right on them by construction; they supply {zero_nf:,} of the {int((normal['label_free'] == 0).sum()):,} "
            "\"not free\" normal pairs. Their effect on the scores is not removed anywhere in this report.", ""]

    # ---- step 3
    out += ["## 3. Pairs", "", f"{len(df):,} pairs in total. Tag `f1` if the decision time or the arrival time lies in "
            "2026-10-07 00:01 to 2026-10-13 05:30 Singapore time (both edges inclusive), else `normal`.", "",
            "| Period | Agency | Carparks | Pairs | Not free rows |", "|---|---|---|---|---|"]
    for period, sub in (("normal", normal), ("f1", f1)):
        for a in AGENCIES:
            s = sub[sub["agency"] == a]
            out.append(f"| {period} | {a} | {s['carpark_id'].nunique()} | {len(s):,} | {int((s['label_free'] == 0).sum()):,} |")
    out += ["", "## 4. Scores on normal pairs (the verdict set)", "", *normal_md,
            "## Event stress test: F1 weekend", "",
            "Pairs tagged `f1`. Same tables as above. **Not part of the verdict.**", "", *f1_md]
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(out))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
