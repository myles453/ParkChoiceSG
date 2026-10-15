import json
import math
import shutil
from datetime import datetime, timedelta, timezone

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from service.artifacts import FeatureMismatchError
from service.main import create_app
from service.make_stub_artifacts import FEATURE_NAMES
from service.tests.conftest import NOW, Env, payload

FIELDS = {"carpark_id", "issue_at", "arrival_at", "horizon_minutes", "mode", "p_free", "free", "confidence",
          "current_available", "current_observed_at", "current_reading_stale", "model_version", "status", "fallback_reason"}


def one(env, cp, **kw):
    out = env.predict([cp], **kw)
    assert len(out) == 1 and set(out[0]) == FIELDS
    return out[0]


# ---- health ----
def test_health_loaded(env):
    h = env.client.get("/health").json()
    assert h["artifacts_loaded"] is True and h["model_version"] == "stub-0.0.1"


def test_health_and_predict_when_artifacts_missing(tmp_path):
    c = TestClient(create_app(tmp_path))
    h = c.get("/health").json()
    assert h["artifacts_loaded"] is False and h["model_version"] is None and h["error"]
    r = c.post("/predict", json={"carpark_ids": ["ACB"], "arrival_at": "2030-01-01T00:00:00+08:00"})
    assert r.status_code == 503


# ---- modes ----
def test_short_mode(env):
    r = one(env, "ACB", minutes=30)
    assert r["status"] == "ok" and r["mode"] == "short" and r["fallback_reason"] is None
    assert 0 <= r["p_free"] <= 1 and r["current_available"] == 120
    assert r["current_observed_at"].startswith("2026-10-07T03:59")  # UTC
    assert r["current_reading_stale"] is False
    assert r["horizon_minutes"] == 30 and r["model_version"] == "stub-0.0.1"
    assert r["free"] == (r["p_free"] >= 0.5)


def test_90_minute_boundary(env):
    assert one(env, "ACB", minutes=90)["mode"] == "short"
    assert one(env, "ACB", minutes=90.5)["mode"] == "profile"


def test_stale_reading_uses_profile(env):
    r = one(env, "HE12", minutes=30)  # reading is 20 minutes old
    assert r["mode"] == "profile" and r["status"] == "ok"
    assert "15" in r["fallback_reason"]
    assert r["current_available"] is None and r["current_reading_stale"] is True
    assert r["current_observed_at"].startswith("2026-10-07T03:40")  # kept, UTC


def test_reading_at_exactly_15_minutes_is_fresh(env):
    env.payload = payload({"ACB": (10, 20, 15)})
    r = one(env, "ACB")
    assert r["mode"] == "short" and r["current_reading_stale"] is False and r["current_available"] == 10


def test_stale_reading_nulls_current_available_in_every_mode(env):
    env.payload = payload({"ACB": (10, 20, 16)})
    for minutes in (30, 180):
        r = one(env, "ACB", minutes=minutes)
        assert r["current_available"] is None and r["current_reading_stale"] is True
        assert r["current_observed_at"] is not None


def test_no_reading_leaves_stale_flag_null(env):
    r = one(env, "ZZZZ")
    assert r["current_reading_stale"] is None and r["current_available"] is None


def test_future_dated_reading_not_used(env):
    env.payload = payload({"ACB": (10, 20, -10)})
    r = one(env, "ACB")
    assert r["mode"] == "profile"


def test_long_horizon_profile_values(env):
    # Wed 2026-10-07 14:07 SGT arrival -> weekday slot 56
    arrival = datetime(2026, 10, 7, 14, 7, tzinfo=timezone(timedelta(hours=8)))
    r = one(env, "ACB", arrival=arrival)
    expected = float(np.clip(0.5 + 0.4 * np.sin(56 / 96 * 2 * np.pi), 0, 1))
    assert r["mode"] == "profile" and r["fallback_reason"] is None
    assert r["p_free"] == pytest.approx(expected)


@pytest.mark.parametrize("arrival,day,slot", [
    ("2026-10-07T14:07:00+08:00", "weekday", 56),
    ("2026-10-10T09:20:00+08:00", "saturday", 37),
    ("2026-10-11T23:59:00+08:00", "sunday_ph", 95),
    ("2026-12-25T00:00:00+08:00", "sunday_ph", 0),   # Christmas, a Friday
    ("2026-10-08T15:59:00+00:00", "weekday", 95),    # 23:59 SGT, UTC input converted
])
def test_day_types(env, arrival, day, slot):
    from service.features import day_type, sg_time_parts
    a = datetime.fromisoformat(arrival)
    assert day_type(a) == day and sg_time_parts(a)[1] == slot
    r = one(env, "ACB", arrival=a)
    expected = float(np.clip(0.5 + 0.4 * np.sin(slot / 96 * 2 * np.pi), 0, 1))
    assert r["mode"] == "profile" and r["p_free"] == pytest.approx(expected)


# ---- features ----
class Recorder:
    def __init__(self):
        self.X = None

    def predict_proba(self, X):
        self.X = X.copy()
        return np.tile([0.3, 0.7], (len(X), 1))


def test_lag_features_from_live_history(env):
    rec = Recorder()
    art = _art(env)
    art.model = rec
    # readings observed at T-15, T-10, T-5, T; each polled one minute after it was observed
    for off, lots in [(-15, 100), (-10, 110), (-5, 120), (0, 130)]:
        env.now = NOW + timedelta(minutes=off + 1)
        env.payload = payload({"ACB": (lots, 200, 1)}, env.now)
        env.mono += 100
        env.client.post("/predict", json={"carpark_ids": ["ACB"],
                                          "arrival_at": (env.now + timedelta(minutes=30)).isoformat()})
    row = rec.X.iloc[0]
    assert list(rec.X.columns) == FEATURE_NAMES
    # issue = T+1 min: lag15 target T-14 -> nearest T-15 (100); lag30 target T-29 is >10 min from any reading
    assert row["current_available"] == 130 and row["available_lag_15min"] == 100
    assert math.isnan(row["available_lag_30min"]) and math.isnan(row["available_lag_60min"])
    assert row["delta_15min"] == 30 and math.isnan(row["delta_60min"])
    assert row["current_total_lots"] == 200 and row["current_age_seconds"] == 60
    assert row["current_free_ratio"] == pytest.approx(0.65) and row["horizon_minutes"] == 30
    assert row["arrival_weekday"] == 3 and row["arrival_is_weekend"] == 0 and row["arrival_is_public_holiday"] == 0


def test_lag_left_empty_without_history(env):
    rec = Recorder()
    _art(env).model = rec
    one(env, "ACB")
    row = rec.X.iloc[0]
    for c in ("available_lag_15min", "available_lag_30min", "available_lag_60min", "delta_15min", "delta_60min"):
        assert math.isnan(row[c])


def test_history_trimmed_to_75_minutes(env):
    for ago in (80, 74, 5):
        env.now = NOW + timedelta(minutes=80 - ago)
        env.payload = payload({"ACB": (10, 20, ago)}, env.now)
        env.mono += 100
        env.client.post("/predict", json={"carpark_ids": ["ACB"],
                                          "arrival_at": (env.now + timedelta(minutes=10)).isoformat()})
    assert [at for at, _ in env.feed.history("ACB")] == [env.now - timedelta(minutes=5)]  # 74 aged out, 80 never kept


def test_nan_from_model_is_model_error_with_profile_p(env):
    class Bad(Recorder):
        def predict_proba(self, X):
            return np.tile([np.nan, np.nan], (len(X), 1))
    _art(env).model = Bad()
    r = one(env, "ACB")
    assert r["status"] == "model_error" and r["mode"] == "profile" and "short_model_failed" in r["fallback_reason"]
    assert 0 <= r["p_free"] <= 1


def test_raising_model_is_model_error_never_ok(env):
    class Boom:
        def predict_proba(self, X):
            raise RuntimeError("kaput")
    _art(env).model = Boom()
    out = env.predict(["ACB", "BM29"])
    assert {r["status"] for r in out} == {"model_error"} and all("kaput" in r["fallback_reason"] for r in out)


def test_model_error_without_profile_cell_has_null_p(env):
    env.now = datetime(2026, 10, 10, 3, 0, tzinfo=timezone.utc)  # Saturday; TPM1 has no Saturday cells
    env.payload = payload({"TPM1": (5, 20, 1)}, env.now)

    class Boom:
        def predict_proba(self, X):
            raise RuntimeError("kaput")
    _art(env).model = Boom()
    r = one(env, "TPM1", minutes=30)
    assert r["status"] == "model_error" and r["p_free"] is None and r["confidence"] is None


def test_carpark_stats_joined_by_carpark_and_slot(env):
    from service.make_stub_artifacts import STATS_CARPARKS
    rec = Recorder()
    _art(env).model = rec
    env.payload = payload({"ACB": (10, 20, 1), "TPM1": (10, 20, 1)})
    arrival = NOW + timedelta(minutes=30)  # 12:30 SGT -> slot 50
    env.predict(["ACB", "TPM1"], arrival=arrival)
    acb, tpm = rec.X.iloc[0], rec.X.iloc[1]
    assert acb["carpark_free_share"] == pytest.approx(0.6)
    assert acb["carpark_slot_free_share"] == pytest.approx(np.clip(0.6 + 0.3 * np.sin(50 / 96 * 2 * np.pi), 0, 1))
    assert math.isnan(tpm["carpark_free_share"]) and math.isnan(tpm["carpark_slot_free_share"])
    assert "TPM1" not in STATS_CARPARKS


def test_unbuildable_feature_refuses_to_start(stub_dir, tmp_path):
    import joblib
    d = tmp_path / "art"
    shutil.copytree(stub_dir, d)
    bundle = joblib.load(d / "short_horizon.joblib")
    bundle["feature_names"] = FEATURE_NAMES + ["mystery_feature", "other_one"]
    joblib.dump(bundle, d / "short_horizon.joblib")
    card = json.loads((d / "model_card.json").read_text())
    card["feature_names"] = bundle["feature_names"]
    (d / "model_card.json").write_text(json.dumps(card))
    with pytest.raises(FeatureMismatchError, match=r"mystery_feature.*other_one"):
        create_app(d)


def test_calibrator_applied_and_clipped(env):
    class Cal:
        def predict(self, x):
            return np.full(len(x), 1.7)
    _art(env).calibrator = Cal()
    _art(env).model = Recorder()
    r = one(env, "ACB")
    assert r["p_free"] == 1.0 and r["confidence"] == "High"


# ---- statuses ----
def test_unknown_carpark(env):
    r = one(env, "NOPE")
    assert r["status"] == "unknown_carpark" and r["p_free"] is None and r["free"] is None
    assert r["confidence"] is None and r["mode"] is None


def test_insufficient_history_profile_hole(env):
    env.payload = payload({"TPM1": (10, 20, 1)})
    sat = datetime(2026, 10, 10, 12, 0, tzinfo=timezone(timedelta(hours=8)))
    r = one(env, "TPM1", arrival=sat)
    assert r["status"] == "insufficient_history" and r["p_free"] is None and r["mode"] == "profile"


@pytest.mark.parametrize("err", [httpx.ReadTimeout("timeout"), httpx.ConnectError("down"), ValueError("bad json")])
def test_live_feed_failure_falls_back(env, err):
    env.error = err
    r = one(env, "ACB", minutes=30)
    assert r["status"] == "live_feed_unavailable" and r["mode"] == "profile"
    assert r["fallback_reason"] and r["current_available"] is None
    assert 0 <= r["p_free"] <= 1  # profile value, not a guess labelled ok


def test_live_feed_failure_unknown_carpark(env):
    env.error = httpx.ConnectError("down")
    r = one(env, "NOPE")
    assert r["status"] == "unknown_carpark" and r["p_free"] is None and "unavailable" in r["fallback_reason"]


def test_malformed_payload_is_feed_failure(env):
    env.payload = {"items": []}
    assert one(env, "ACB")["status"] == "live_feed_unavailable"


def test_invalid_readings_dropped_not_guessed(env):
    env.payload = payload({"ACB": (300, 200, 1), "BM29": (-1, 100, 1), "HE12": (5, 80, 1)})
    out = {r["carpark_id"]: r for r in env.predict(["ACB", "BM29", "HE12"])}
    assert out["HE12"]["mode"] == "short"
    assert out["ACB"]["current_available"] is None and out["ACB"]["fallback_reason"] == "no_current_reading"
    assert out["BM29"]["current_available"] is None


def test_zero_available_is_valid_reading(env):
    r = one(env, "BM29")
    assert r["mode"] == "short" and r["current_available"] == 0


def test_non_car_lots_ignored(env):
    env.payload = {"items": [{"carpark_data": [{"carpark_number": "ACB", "update_datetime": "2026-10-07T11:59:00",
                    "carpark_info": [{"total_lots": "9", "lot_type": "Y", "lots_available": "3"}]}]}]}
    assert one(env, "ACB")["status"] == "live_feed_unavailable"  # nothing usable at all


def test_never_ok_without_probability(env):
    out = env.predict(["ACB", "BM29", "HE12", "NOPE", "TPM1"], minutes=30)
    for r in out:
        assert (r["status"] == "ok") == (r["p_free"] is not None) or r["status"] == "live_feed_unavailable"
        assert r["p_free"] is None or 0 <= r["p_free"] <= 1


# ---- cache ----
def test_cache_60_seconds(env):
    one(env, "ACB"); one(env, "BM29")
    assert env.calls == 1
    env.advance(59); one(env, "ACB"); assert env.calls == 1
    env.advance(2); one(env, "ACB"); assert env.calls == 2


def test_failure_not_cached(env):
    env.error = httpx.ReadTimeout("t")
    one(env, "ACB"); one(env, "ACB")
    assert env.calls == 2
    env.error = None
    assert one(env, "ACB")["status"] == "ok"


def test_timeout_is_5_seconds(monkeypatch):
    from service import live
    seen = {}

    def fake_get(url, timeout, params=None):
        seen.update(url=url, timeout=timeout, params=params)
        raise httpx.ConnectError("blocked")
    monkeypatch.setattr(live.httpx, "get", fake_get)
    with pytest.raises(live.FeedError):
        live.LiveFeed().current()
    assert seen == {"url": "https://api.data.gov.sg/v1/transport/carpark-availability", "timeout": 5, "params": None}


# ---- config comes from model_card.json ----
def test_threshold_and_bands_read_from_card(stub_dir, tmp_path):
    d = tmp_path / "art"
    shutil.copytree(stub_dir, d)
    card = json.loads((d / "model_card.json").read_text())
    card["free_threshold"] = 0.99
    card["confidence_bands"] = {"high": 0.9, "medium": 0.1}
    card["version"] = "other-9"
    (d / "model_card.json").write_text(json.dumps(card))
    e = Env(d)
    arrival = datetime(2026, 10, 7, 14, 7, tzinfo=timezone(timedelta(hours=8)))
    r = one(e, "ACB", arrival=arrival)
    assert r["model_version"] == "other-9" and r["free"] is False and r["confidence"] == "Medium"


@pytest.mark.parametrize("bands", [
    {"high": [0.8, 1.0], "medium": [0.5, 0.8], "low": [0.0, 0.5]},   # old range format is gone
    {"high": 0.8, "medium": 0.5, "low": 0.0},
    {"high": 0.4, "medium": 0.5},
    {"high": 1.5, "medium": 0.5},
    {"high": "0.8", "medium": 0.5},
    {"high": 0.8},
])
def test_bad_band_config_fails_to_load(stub_dir, tmp_path, bands):
    d = tmp_path / "art"
    shutil.copytree(stub_dir, d)
    card = json.loads((d / "model_card.json").read_text())
    card["confidence_bands"] = bands
    (d / "model_card.json").write_text(json.dumps(card))
    assert TestClient(create_app(d)).get("/health").json()["artifacts_loaded"] is False


def test_confidence_lower_bounds(env):
    art = _art(env)
    assert [art.confidence(p) for p in (1.0, 0.8, 0.79, 0.5, 0.49, 0.0)] == \
        ["High", "High", "Medium", "Medium", "Low", "Low"]


def test_missing_carpark_stats_file_fails_to_load(stub_dir, tmp_path):
    d = tmp_path / "art"
    shutil.copytree(stub_dir, d)
    (d / "carpark_stats.parquet").unlink()
    assert TestClient(create_app(d)).get("/health").json()["artifacts_loaded"] is False


def test_feature_name_mismatch_fails_to_load(stub_dir, tmp_path):
    d = tmp_path / "art"
    shutil.copytree(stub_dir, d)
    card = json.loads((d / "model_card.json").read_text())
    card["feature_names"] = card["feature_names"][::-1]
    (d / "model_card.json").write_text(json.dumps(card))
    assert TestClient(create_app(d)).get("/health").json()["artifacts_loaded"] is False


# ---- request validation ----
@pytest.mark.parametrize("body", [
    {"carpark_ids": [], "arrival_at": "2026-10-07T13:00:00+08:00"},
    {"carpark_ids": ["ACB"], "arrival_at": "2026-10-07T13:00:00"},          # naive
    {"carpark_ids": ["ACB"], "arrival_at": "2026-10-07T11:00:00+08:00"},    # past
    {"carpark_ids": ["ACB"], "arrival_at": "garbage"},
    {"arrival_at": "2026-10-07T13:00:00+08:00"},
])
def test_bad_requests_rejected(env, body):
    assert env.client.post("/predict", json=body).status_code == 422


def _art(env):
    # the engine's artefacts object, reached through the route closure
    for route in env.app.routes:
        if getattr(route, "path", "") == "/predict":
            cl = {n: c.cell_contents for n, c in zip(route.endpoint.__code__.co_freevars, route.endpoint.__closure__)}
            return cl["state"]["art"]
    raise AssertionError


def test_twenty_carparks_one_request(env):
    ids = ["ACB", "BM29", "HE12", "TPM1"] * 5
    assert len(env.predict(ids)) == 20 and env.calls == 1


# ---- live parser / warm-up / poller ----
def test_zero_capacity_carpark_rejected(env):
    env.payload = payload({"ACB": (0, 0, 1), "HE12": (5, 80, 1)})
    out = {r["carpark_id"]: r for r in env.predict(["ACB", "HE12"])}
    assert out["ACB"]["current_available"] is None and out["ACB"]["mode"] == "profile"
    assert out["HE12"]["mode"] == "short"


def test_conflicting_duplicate_records_dropped(env):
    p = payload({"ACB": (5, 20, 1), "HE12": (5, 80, 1)})
    p["items"][0]["carpark_data"].append(
        {**p["items"][0]["carpark_data"][0],
         "carpark_info": [{"total_lots": "20", "lot_type": "C", "lots_available": "6"}]})
    env.payload = p
    assert one(env, "ACB")["current_available"] is None


def test_warm_up_calls_at_15_to_75_minutes_and_fills_history(env):
    env.dated_payload = lambda when: payload({"ACB": (100, 200, 0)}, when)  # observed exactly at query time
    assert env.feed.warm_up() == 5
    expected = [env.now - timedelta(minutes=m) for m in (15, 30, 45, 60, 75)]
    assert env.dated_calls == expected
    assert all(c.utcoffset() is not None for c in env.dated_calls)
    assert len(env.feed.history("ACB")) == 5


def test_warm_up_failure_is_logged_and_skipped(env, caplog):
    n = []

    def flaky(when):
        n.append(when)
        if len(n) in (2, 3):
            raise httpx.ReadTimeout("slow")
        return payload({"ACB": (100, 200, 1)}, when)
    env.dated_payload = flaky
    assert env.feed.warm_up() == 3 and len(n) == 5
    assert "warm-up call for 30 minutes ago failed" in caplog.text


def test_warm_up_then_features_use_history(env):
    rec = Recorder()
    _art(env).model = rec
    env.dated_payload = lambda when: payload({"ACB": (100 + int((env.now - when).total_seconds() // 60), 200, 1)}, when)
    env.feed.warm_up()
    one(env, "ACB")
    row = rec.X.iloc[0]
    assert row["available_lag_15min"] == 115 and row["available_lag_30min"] == 130 and row["available_lag_60min"] == 160
    assert row["delta_60min"] == 120 - 160


def test_http_fetch_sends_date_time_with_plus_08(monkeypatch):
    from service import live
    seen = {}

    def fake_get(url, timeout, params=None):
        seen["params"] = params
        raise httpx.ConnectError("blocked")
    monkeypatch.setattr(live.httpx, "get", fake_get)
    with pytest.raises(httpx.ConnectError):
        live._http_fetch(datetime(2026, 10, 7, 3, 45, tzinfo=timezone.utc))
    assert seen["params"] == {"date_time": "2026-10-07T11:45:00+08:00"}


def test_background_task_warms_up_then_polls(stub_dir):
    import time
    e = Env(stub_dir)
    e.app = create_app(stub_dir, e.feed, poll_seconds=0.05)
    with TestClient(e.app):
        deadline = time.time() + 5
        while e.calls < 3 and time.time() < deadline:
            time.sleep(0.02)
    assert len(e.dated_calls) == 5 and e.calls >= 3  # polls bypass the 60 s cache


def test_warm_up_and_each_poll_are_logged_at_info(stub_dir, caplog):
    import logging
    import time
    e = Env(stub_dir)
    e.app = create_app(stub_dir, e.feed, poll_seconds=0.05)
    with caplog.at_level(logging.INFO, logger="service"):
        with TestClient(e.app):
            deadline = time.time() + 5
            while e.calls < 2 and time.time() < deadline:
                time.sleep(0.02)
    text = caplog.text
    assert "history warm-up finished: 5 of 5 calls succeeded" in text
    assert text.count("background poll:") >= 2


def test_service_logger_has_a_handler_so_uvicorn_shows_info_lines():
    import logging
    import service.main  # noqa: F401
    lg = logging.getLogger("service")
    assert lg.handlers and lg.level == logging.INFO
