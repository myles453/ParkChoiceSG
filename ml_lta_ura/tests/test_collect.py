"""collect.py tests. HTTP is mocked at provider_puller.get_json; no network, no real keys."""
import gzip
import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import collect  # noqa: E402
import provider_puller  # noqa: E402

FAKE_LTA_KEY = "LTAKEY-SECRET-123"
FAKE_URA_KEY = "URAKEY-SECRET-456"
FAKE_TOKEN = "URATOKEN-SECRET-789"
T0 = datetime(2026, 10, 7, 4, 2, 3, tzinfo=timezone.utc)  # 12:02:03 SGT


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setenv("LTA_ACCOUNT_KEY", FAKE_LTA_KEY)
    monkeypatch.setenv("URA_ACCESS_KEY", FAKE_URA_KEY)


def lta_rows(n, start=0):
    return [{"CarParkID": f"L{i}", "Area": "", "Development": "x", "Location": "1 2",
             "AvailableLots": 5, "LotType": "C", "Agency": "LTA"} for i in range(start, start + n)]


def fake_get_json(lta_fail=False, ura_fail=None):
    def get_json(url, headers=None):
        if "datamall" in url:
            if lta_fail:
                raise URLError("boom " + FAKE_LTA_KEY)
            skip = int(url.split("$skip=")[1]) if "$skip=" in url else 0
            payload = {"value": lta_rows(500 if skip == 0 else 3, skip)}
        elif "insertNewToken" in url:
            payload = {"Status": "Success", "Result": FAKE_TOKEN}
        else:
            if ura_fail:
                raise ura_fail
            payload = {"Status": "Success", "Result": [
                {"carparkNo": "A0001", "lotType": "C", "lotsAvailable": "12"}]}
        raw = json.dumps(payload).encode()
        return payload, raw, T0
    return get_json


# ------------------------------------------------------------------ schedule
def test_next_slot_on_five_minute_grid():
    assert collect.next_slot(1000) == 1200
    assert collect.next_slot(1200) == 1200
    assert collect.next_slot(1200.01) == 1500


def test_grid_skips_overrun_slot():
    now = [1000.0]
    stop = threading.Event()
    slots = []

    def wait(seconds):
        now[0] += seconds

    def cycle(slot):
        slots.append(slot)
        # first cycle runs 700 s: slots 1500 and 1800 are missed
        now[0] += 700 if len(slots) == 1 else 10
        if len(slots) == 2:
            stop.set()

    collect.run_forever(cycle, clock=lambda: now[0], wait=wait, stop=stop)
    assert slots == [1200, 2100]
    assert all(s % 300 == 0 for s in slots)


def test_cycles_never_overlap():
    now, active, peak, stop = [0.0], [0], [0], threading.Event()
    n = []

    def cycle(slot):
        active[0] += 1
        peak[0] = max(peak[0], active[0])
        now[0] += 400
        active[0] -= 1
        n.append(slot)
        if len(n) == 3:
            stop.set()

    collect.run_forever(cycle, clock=lambda: now[0], wait=lambda s: now.__setitem__(0, now[0] + s), stop=stop)
    assert peak[0] == 1


# ------------------------------------------------------------ provider failure
def test_one_provider_failing_does_not_stop_the_other(tmp_path, monkeypatch):
    monkeypatch.setattr(provider_puller, "get_json", fake_get_json(lta_fail=True))
    events = collect.run_cycle(1_000_000_200, tmp_path, sleep=lambda s: None)
    by = {e["provider"]: e for e in events}
    assert by["lta"]["status"] == "failed" and by["lta"]["error_type"] == "URLError"
    assert by["lta"]["attempts"] == collect.RETRIES + 1
    assert by["ura"]["status"] == "ok" and by["ura"]["rows"] == 1
    assert len(list((tmp_path / "ura").glob("*/*.json.gz"))) == 1
    assert not (tmp_path / "lta").exists()
    lines = (tmp_path / "events.jsonl").read_text().splitlines()
    assert len(lines) == 2


def test_ok_cycle_saves_all_pages_and_utc_time(tmp_path, monkeypatch):
    monkeypatch.setattr(provider_puller, "get_json", fake_get_json())
    events = collect.run_cycle(1_000_000_200, tmp_path, sleep=lambda s: None)
    by = {e["provider"]: e for e in events}
    assert by["lta"]["rows"] == 503 and by["ura"]["rows"] == 1
    f = tmp_path / "lta" / "2026-10-07" / "120203.json.gz"
    data = json.loads(gzip.open(f).read())
    assert data["retrieved_at_utc"] == "2026-10-07T04:02:03+00:00"
    assert len(data["pages"]) == 2
    assert FAKE_TOKEN not in json.dumps(data)


def test_retry_then_success(tmp_path, monkeypatch):
    calls = {"n": 0}
    base = fake_get_json()

    def flaky(url, headers=None):
        if "eservice" in url and "invokeUraDS" in url:
            calls["n"] += 1
            if calls["n"] < 3:
                raise HTTPError(url, 503, "x", {}, None)
        return base(url, headers)

    monkeypatch.setattr(provider_puller, "get_json", flaky)
    sleeps = []
    ev = collect.run_provider("ura", 1_000_000_200, tmp_path, sleep=sleeps.append)
    assert ev["status"] == "ok" and ev["attempts"] == 3 and sleeps == [2, 4]


def test_client_error_is_not_retried(tmp_path, monkeypatch):
    monkeypatch.setattr(provider_puller, "get_json",
                        fake_get_json(ura_fail=HTTPError("u", 403, "forbidden", {}, None)))
    ev = collect.run_provider("ura", 1_000_000_200, tmp_path, sleep=lambda s: None)
    assert ev["status"] == "failed" and ev["attempts"] == 1 and ev["http_status"] == 403


# -------------------------------------------------------------- atomic write
def test_atomic_write_leaves_no_partial_file(tmp_path, monkeypatch):
    target = tmp_path / "ura" / "2026-10-07" / "120203.json.gz"
    collect.atomic_write_gz(target, {"a": 1})
    assert json.loads(gzip.open(target).read()) == {"a": 1}
    assert [p.name for p in target.parent.iterdir()] == ["120203.json.gz"]

    # a failure mid-write must leave the old file intact and no temp file behind
    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(collect.os, "fsync", boom)
    with pytest.raises(OSError):
        collect.atomic_write_gz(target, {"a": 2})
    assert json.loads(gzip.open(target).read()) == {"a": 1}
    assert [p.name for p in target.parent.iterdir()] == ["120203.json.gz"]


def test_temp_name_is_not_counted_as_capture(tmp_path):
    d = tmp_path / "lta" / "2026-10-07"
    d.mkdir(parents=True)
    (d / ".120203.json.gz.tmp").write_bytes(b"x")
    assert collect.list_captures(tmp_path, "lta") == []


# --------------------------------------------------------------------- no key
def test_no_log_line_contains_a_key(tmp_path, monkeypatch, caplog):
    caplog.set_level("DEBUG")
    # failing LTA whose exception text embeds the key; URA token present in successful flow
    monkeypatch.setattr(provider_puller, "get_json", fake_get_json(lta_fail=True))
    collect.run_cycle(1_000_000_200, tmp_path, sleep=lambda s: None)
    monkeypatch.setattr(provider_puller, "get_json", fake_get_json())
    collect.run_cycle(1_000_000_500, tmp_path, sleep=lambda s: None)
    text = (tmp_path / "events.jsonl").read_text() + caplog.text
    for secret in (FAKE_LTA_KEY, FAKE_URA_KEY, FAKE_TOKEN):
        assert secret not in text
    assert "AccountKey" not in text and "AccessKey" not in text
    assert all(json.loads(l) for l in (tmp_path / "events.jsonl").read_text().splitlines())


def test_missing_key_stops(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("URA_ACCESS_KEY")
    monkeypatch.setattr(provider_puller, "load_local_env", lambda: None)
    assert collect.main(["--data-dir", str(tmp_path)]) == 2
    assert "URA_ACCESS_KEY" in capsys.readouterr().err


# -------------------------------------------------------------------- status
def test_status_counts_and_gaps(tmp_path):
    for hhmm in ("120000", "120500", "121000", "122000", "122500"):  # 10-minute hole
        collect.atomic_write_gz(tmp_path / "lta" / "2026-10-07" / f"{hhmm}.json.gz", {})
    now = datetime(2026, 10, 7, 4, 25, 0, tzinfo=timezone.utc)  # 12:25 SGT
    out = collect.status(tmp_path, now)
    assert "saved         : 5" in out and "expected      : 6" in out and "83.3%" in out
    assert "0:10:00" in out
    assert "no captures" in out  # ura
