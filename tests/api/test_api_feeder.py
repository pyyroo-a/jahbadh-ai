import time

import httpx2
from fastapi.testclient import TestClient

from apifakes import api_settings, no_sleep, parse_sse
from jahbadh.api import ingest_routes
from jahbadh.api.app import create_app
from jahbadh.simulator import simulate_match


def feeder_app(tmp_path, token="tok"):
    app = create_app(api_settings(tmp_path, ingest_token=token), sleep=no_sleep)
    app.state.feed_speed = 120.0                  # two match minutes a batch keeps the test quick
    app.state.feeder_client = lambda: httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="http://desk")
    return app


def _done(c: TestClient, timeout: float = 120.0):
    deadline = time.monotonic() + timeout
    while not (c.app.state.ingest and c.app.state.ingest.done):
        assert time.monotonic() < deadline, "the feed never finished"
        time.sleep(0.05)


def test_the_feeder_sends_a_whole_match_in_order_and_closes(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_routes.random, "randint", lambda a, b: 7)
    with TestClient(feeder_app(tmp_path)) as c:
        rid = c.post("/api/ingest/demo").json()["run_id"]
        _done(c)
        msgs = parse_sse(c.get(f"/api/ingest/{rid}/stream").text)
        assert [m["data"]["id"] for m in msgs if m["event"] == "event"] == [e.id for e in simulate_match(7).events]
        assert msgs[-1]["data"] == {"reason": "full_time"}
        assert len(c.app.state.ingest.match.tracking) == len(simulate_match(7).tracking)   # frames came too


def test_the_demo_button_starts_one_feed(tmp_path):
    with TestClient(feeder_app(tmp_path)) as c:
        c.app.state.feed_speed = 1.0              # slow, so the first feed is still going
        c.app.state.sleep = _blocked
        first = c.post("/api/ingest/demo").json()["run_id"]
        assert c.post("/api/ingest/demo").json()["run_id"] == first
        assert c.get("/api/config").json()["ingest"]["run_id"] == first


async def _blocked(_s: float) -> None:
    import asyncio
    await asyncio.Event().wait()


def test_the_demo_button_is_off_without_ingest(tmp_path):
    with TestClient(feeder_app(tmp_path, token=None)) as c:
        assert c.post("/api/ingest/demo").status_code == 404
