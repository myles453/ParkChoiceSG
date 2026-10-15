import json
import socket
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from service.live import LiveFeed
from service.main import create_app
from service.make_stub_artifacts import make_stub_artifacts

NOW = datetime(2026, 10, 7, 4, 0, tzinfo=timezone.utc)  # Wed 12:00 Singapore


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*a, **k):
        raise AssertionError("tests must not use the real network")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


@pytest.fixture(scope="session")
def stub_dir(tmp_path_factory):
    return make_stub_artifacts(tmp_path_factory.mktemp("stub"))


def sgt(minutes_ago: float, now: datetime = NOW) -> str:
    """Provider-style timezone-less Singapore timestamp."""
    return (now - timedelta(minutes=minutes_ago) + timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%S")


def payload(records: dict[str, tuple[int, int, float]], now: datetime = NOW) -> dict:
    """records: carpark -> (available, total, minutes_ago)."""
    return {"items": [{"timestamp": "x", "carpark_data": [
        {"carpark_number": cp, "update_datetime": sgt(ago, now),
         "carpark_info": [{"total_lots": str(t), "lot_type": "C", "lots_available": str(a)}]}
        for cp, (a, t, ago) in records.items()]}]}


class Env:
    def __init__(self, stub_dir):
        self.now = NOW
        self.mono = 1000.0
        self.payload = payload({"ACB": (120, 200, 1), "BM29": (0, 100, 2), "HE12": (50, 80, 20)})
        self.error: Exception | None = None
        self.calls = 0
        self.dated_calls = []
        self.dated_error: Exception | None = None
        self.dated_payload = lambda when: payload({"ACB": (50, 200, 0)}, when)
        self.feed = LiveFeed(fetch_fn=self._fetch, clock=lambda: self.now, monotonic=lambda: self.mono)
        self.app = create_app(stub_dir, self.feed)
        self.client = TestClient(self.app)

    def _fetch(self, date_time=None):
        if date_time is not None:
            self.dated_calls.append(date_time)
            if self.dated_error:
                raise self.dated_error
            return self.dated_payload(date_time)
        self.calls += 1
        if self.error:
            raise self.error
        return self.payload

    def predict(self, ids, minutes=30, arrival=None):
        arrival = arrival or (self.now + timedelta(minutes=minutes))
        r = self.client.post("/predict", json={"carpark_ids": ids, "arrival_at": arrival.isoformat()})
        assert r.status_code == 200, r.text
        return r.json()

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)
        self.mono += seconds


@pytest.fixture
def env(stub_dir):
    return Env(stub_dir)
