import ast
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import build_retrieval_view as brv  # noqa: E402
import build_target_pairs as btp  # noqa: E402
import features  # noqa: E402
from provider_puller import normalize_pages  # noqa: E402

SGT = timezone(timedelta(hours=8))
RECEIVED = datetime(2026, 10, 14, 4, 0, tzinfo=timezone.utc)


def us(*args, extra_us=0):
    return int(datetime(*args, tzinfo=SGT).timestamp() * 1_000_000) + extra_us


def lta_record(agency, cid, lots=5, lot_type="C"):
    return {"Agency": agency, "CarParkID": cid, "LotType": lot_type, "AvailableLots": lots, "Area": "", "Development": ""}


def test_lta_feed_rows_with_agency_hdb_or_ura_are_excluded():
    records = [lta_record("LTA", "1"), lta_record("HDB", "A1"), lta_record("URA", "B0001"),
               lta_record("LTA", "2", lot_type="H"), lta_record("LTA", "3", lots=0)]
    rows, rejected = normalize_pages([(records, RECEIVED)], "lta_datamall")
    kept = btp.select_rows(rows, "lta")
    assert sorted((r["agency"], r["carpark_id"]) for r in kept) == [("LTA", "1"), ("LTA", "3")]
    assert any(r["lots_available"] == 0 for r in kept)  # a zero is a valid reading, not dropped
    assert rejected == []


def test_ura_rows_all_kept_and_bad_counts_rejected_not_corrected():
    records = [{"carparkNo": "A0001", "lotType": "C", "lotsAvailable": "12"},
               {"carparkNo": "A0002", "lotType": "C", "lotsAvailable": "-3"},
               {"carparkNo": "A0003", "lotType": "C", "lotsAvailable": "x"},
               {"carparkNo": "A0004", "lotType": "C"},
               {"carparkNo": "A0005", "lotType": "M", "lotsAvailable": "7"}]
    rows, rejected = normalize_pages([(records, RECEIVED)], "ura_direct")
    kept = btp.select_rows(rows, "ura")
    assert [(r["carpark_id"], r["lots_available"]) for r in kept] == [("A0001", 12)]
    assert len(rejected) == 3


def test_feature_and_pair_code_is_imported_not_copied():
    assert brv.compute_features is features.compute_features
    assert btp.brv is brv and btp.FEATURES_B is features.FEATURES_B
    for name in ("build_target_pairs.py", "evaluate_target.py"):
        tree = ast.parse((HERE / name).read_text())
        defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        assigned = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
        assert not defined & {"compute_features", "_nearest_within", "_range_max", "calendar_features", "pairs_for_carpark"}
        assert not assigned & {"HORIZONS", "LAGS_MIN", "LABEL_TOLERANCE_US", "MAX_CURRENT_AGE_US", "LAG_TOLERANCE_US"}
    imports = {a.name for n in ast.walk(ast.parse((HERE / "build_target_pairs.py").read_text()))
               if isinstance(n, ast.Import) for a in n.names}
    assert "build_retrieval_view" in imports


def test_pairs_built_with_the_reused_grid_horizons_and_label_rule():
    brv_start, brv_last = brv.TRAIN_START, brv.LAST_DECISION
    try:
        start = us(2026, 10, 13, 6, 0)
        brv.TRAIN_START, brv.LAST_DECISION = start, start + 60 * 60 * 1_000_000
        brv.VALID_START = brv.TEST_START = us(2100, 1, 1)
        seen = np.arange(start - 60 * 60 * 1_000_000, start + 4 * 60 * 60 * 1_000_000, 5 * 60 * 1_000_000, dtype=np.int64)
        p = brv.pairs_for_carpark("X", seen, np.full(len(seen), 3, dtype=np.int64))
    finally:
        brv.TRAIN_START, brv.LAST_DECISION = brv_start, brv_last
    assert set(p["horizon_minutes"].astype(int)) == set(brv.HORIZONS)
    assert (p["label_free"] == 1).all() and (p["split"] == 0).all()
    assert (p["decision_at"].dt.minute % 15 == 0).all()


def test_no_fitting_function_is_called_in_evaluate_target():
    tree = ast.parse((HERE / "evaluate_target.py").read_text())
    banned = {"fit", "fit_transform", "partial_fit", "train", "refit", "cv", "fit_predict"}
    constructors = {"IsotonicRegression", "LGBMClassifier", "LGBMRegressor", "Booster", "Dataset"}
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            called.add(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", ""))
    assert not called & banned
    assert not called & constructors


def test_f1_tag_at_both_window_edges():
    tag = lambda d, a: bool(btp.f1_tag([d], [a])[0])
    start, end = us(2026, 10, 7, 0, 1), us(2026, 10, 13, 5, 30)
    assert btp.F1_START_US == start and btp.F1_END_US == end
    hour = 60 * 60 * 1_000_000
    # decision exactly at the start edge and one microsecond before it
    assert tag(start, start + hour)
    assert not tag(start - 1 - 15 * 60 * 1_000_000, start - 1)
    # arrival exactly on the start edge, decision before
    assert tag(start - 15 * 60 * 1_000_000, start)
    # decision exactly at the end edge, and one microsecond after it
    assert tag(end, end + hour)
    assert not tag(end + 1, end + hour)
    # decision before the end, arrival after it: still f1 because the decision is inside
    assert tag(end - 15 * 60 * 1_000_000, end + 15 * 60 * 1_000_000)
    # fully outside on either side
    assert not tag(us(2026, 10, 6, 12, 0), us(2026, 10, 6, 13, 0))
    assert not tag(us(2026, 10, 14, 12, 0), us(2026, 10, 14, 13, 0))
