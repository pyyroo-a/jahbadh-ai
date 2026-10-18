import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apifakes import api_settings as settings, last_t, parse_sse, recording_sleep
from jahbadh.api.app import create_app
from jahbadh.api.config import ApiSettings, load_api_settings
from jahbadh.api.replay import paced
from jahbadh.api.stream import StreamEnd, StreamItem


@pytest.fixture(scope="module")
def desk(tmp_path_factory):
    """One app for the module (loading the showcase takes a few seconds), with a recording sleep."""
    sleep, slept = recording_sleep()
    with TestClient(create_app(settings(tmp_path_factory.mktemp("state")), sleep=sleep)) as c:
        yield c, slept


@pytest.fixture
def c(desk):
    client, slept = desk
    slept.clear()
    return client


@pytest.fixture
def slept(desk):
    return desk[1]


@pytest.fixture(scope="module")
def show(desk):
    return desk[0].app.state.showcases["match-042"]


@pytest.fixture(scope="module")
def timeline(desk):
    return desk[0].app.state.timelines["match-042"]


def test_health_and_config(c, show):
    assert c.get("/api/health").json() == {"ok": True}
    cfg = c.get("/api/config").json()
    assert cfg["live_mode"] is False and cfg["live_remaining"] == 0
    assert [s["match_id"] for s in cfg["showcases"]] == ["match-042"]
    meta = show.match.meta
    assert cfg["showcases"][0] == {"match_id": "match-042", "home": meta.home.name, "away": meta.away.name,
                                   "score": meta.score, "model": show.desk.model, "created": show.desk.created}


def test_replay_streams_everything_then_ends(c, show):
    msgs = parse_sse(c.get("/api/replay/match-042/stream").text)
    assert msgs[0]["event"] == "match" and msgs[0]["id"] == "0"
    info = msgs[0]["data"]
    assert info["precomputed"] is True and info["mode"] == "replay" and info["speed"] == 6
    assert info["moment_times"] == sorted(i.moment.t for i in show.desk.items)
    assert info["model"] == show.desk.model and info["created"] == show.desk.created
    assert sum(m["event"] == "event" for m in msgs) == len(show.match.events)
    assert sum(m["event"] == "feed" for m in msgs) == len(show.desk.items)
    assert [m["id"] for m in msgs] == [str(i) for i in range(len(msgs))]
    assert msgs[-1] == {"event": "end", "id": str(len(msgs) - 1), "data": {"reason": "full_time"}}


def test_replay_is_paced_by_match_time(c, slept, timeline):
    parse_sse(c.get("/api/replay/match-042/stream?speed=6").text)
    assert sum(slept) == pytest.approx(last_t(timeline) / 6)


def test_from_t_sends_the_past_at_once(c, slept, show, timeline):
    msgs = parse_sse(c.get("/api/replay/match-042/stream?speed=6&from_t=3600").text)
    assert sum(slept) == pytest.approx((last_t(timeline) - 3600) / 6)
    assert sum(m["event"] == "event" for m in msgs) == len(show.match.events)


def test_last_event_id_resumes_after_that_item(c, timeline):
    msgs = parse_sse(c.get("/api/replay/match-042/stream", headers={"Last-Event-ID": "100"}).text)
    assert msgs[0]["id"] == "101" and all(m["event"] != "match" for m in msgs)
    assert len(msgs) == len(timeline) - 100 and msgs[-1]["event"] == "end"


def test_unknown_match_and_bad_speed(c):
    assert c.get("/api/replay/match-999/stream").status_code == 404
    assert c.get("/api/replay/match-042/stream?speed=0").status_code == 422
    assert c.get("/api/replay/match-042/stream?speed=61").status_code == 422
    assert c.get("/api/replay/match-042/stream?from_t=5401").status_code == 422


def test_the_built_ui_is_served_at_the_root(tmp_path):
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<p>desk</p>")
    with TestClient(create_app(settings(tmp_path, web_dist=tmp_path / "dist"))) as c:
        assert "desk" in c.get("/").text
        assert c.get("/api/health").json() == {"ok": True}


def _items(*ts: float) -> list[StreamItem]:
    return [StreamItem(t=t, kind="end", data=StreamEnd(reason="full_time")) for t in ts]


async def _run(gen) -> list:
    return [x async for x in gen]


def test_paced_waits_for_each_later_item_and_bursts_the_rest():
    sleep, slept = recording_sleep()
    out = asyncio.run(_run(paced(_items(0, 0, 60, 60, 120), speed=6, sleep=sleep)))
    assert [i for i, _ in out] == [0, 1, 2, 3, 4] and slept == [10.0, 10.0]
    slept.clear()
    out = asyncio.run(_run(paced(_items(0, 30, 60, 120), speed=6, start=2, from_t=90, sleep=sleep)))
    assert [i for i, _ in out] == [2, 3] and slept == [5.0]


def test_desk_settings_read_on_and_off(tmp_path, monkeypatch):
    for var in ("JAHBADH_LIVE_MODE", "JAHBADH_LIVE_PER_DAY", "JAHBADH_STATE_DIR"):
        monkeypatch.delenv(var, raising=False)
    env = tmp_path / ".env"
    env.write_text("JAHBADH_LIVE_MODE=on\nJAHBADH_LIVE_PER_DAY=2\nJAHBADH_STATE_DIR=\n")
    s = load_api_settings(env)
    assert s.live_mode is True and s.live_per_day == 2 and s.state_dir == Path("data/state")   # empty = unset
    monkeypatch.setenv("JAHBADH_LIVE_MODE", "off")
    assert load_api_settings(env).live_mode is False
    monkeypatch.setenv("JAHBADH_LIVE_MODE", "TRUE")
    assert load_api_settings(None).live_mode is True
    monkeypatch.delenv("JAHBADH_LIVE_MODE")
    assert load_api_settings(None) == ApiSettings()
