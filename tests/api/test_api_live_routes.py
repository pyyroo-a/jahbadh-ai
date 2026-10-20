import asyncio

import pytest
from fastapi.testclient import TestClient

from apifakes import api_settings, no_sleep, parse_sse, scripted_full_desk_client
from jahbadh.agents.config import MissingSetting, Settings
from jahbadh.agents.desk import Desk
from jahbadh.api import live_routes
from jahbadh.api.app import create_app
from jahbadh.api.live_routes import default_desk_factory


def scripted_desk(match) -> Desk:
    return Desk(client=scripted_full_desk_client(), match=match)


def live_app(tmp_path, per_day=3, sleep=no_sleep, desk_factory=scripted_desk, **kw):
    return create_app(api_settings(tmp_path, live_mode=True, live_per_day=per_day), desk_factory=desk_factory,
                      sleep=sleep, **kw)


async def blocked(_s: float) -> None:
    await asyncio.Event().wait()           # the clock never moves, so the run is still going


def finish(c: TestClient, run_id: str) -> list[dict]:
    return parse_sse(c.get(f"/api/live/{run_id}/stream").text)


def test_live_is_off_unless_switched_on(tmp_path):
    with TestClient(create_app(api_settings(tmp_path), desk_factory=scripted_desk, sleep=no_sleep)) as c:
        r = c.post("/api/live")
        assert r.status_code == 403 and "switched off" in r.json()["detail"] and "Replay" in r.json()["detail"]
        assert not (tmp_path / "live.json").exists()


def test_start_watch_and_finish(tmp_path):
    with TestClient(live_app(tmp_path)) as c:
        r = c.post("/api/live").json()
        assert r["joined"] is False and r["remaining"] == 2 and r["run_id"].startswith("live-")
        msgs = finish(c, r["run_id"])
        assert msgs[0]["event"] == "match" and msgs[0]["data"]["mode"] == "live"
        assert msgs[0]["data"]["precomputed"] is False and msgs[-1]["data"]["reason"] == "full_time"
        assert any(m["event"] == "feed" for m in msgs)
        assert [m["id"] for m in msgs] == [str(i) for i in range(len(msgs))]
        resumed = parse_sse(c.get(f"/api/live/{r['run_id']}/stream", headers={"Last-Event-ID": "10"}).text)
        assert resumed[0]["id"] == "11" and resumed == msgs[11:]
        assert c.get("/api/live/live-1-nope/stream").status_code == 404


def test_a_second_start_joins_the_running_match_for_free(tmp_path):
    with TestClient(live_app(tmp_path, sleep=blocked)) as c:
        first = c.post("/api/live").json()
        again = c.post("/api/live").json()
        assert again == {"run_id": first["run_id"], "joined": True, "remaining": 2}
        assert c.get("/api/config").json()["live_remaining"] == 2


def test_daily_cap_returns_429_with_a_friendly_message(tmp_path):
    with TestClient(live_app(tmp_path, per_day=1)) as c:
        finish(c, c.post("/api/live").json()["run_id"])
        r = c.post("/api/live")
        assert r.status_code == 429
        assert "today's live runs (1 a day)" in r.json()["detail"] and "Replay is still open" in r.json()["detail"]
    with TestClient(live_app(tmp_path, per_day=1)) as c:      # a restart doesn't reset the count
        assert c.post("/api/live").status_code == 429


def test_spotlight_counts_against_the_cap_and_checks_the_player(tmp_path):
    with TestClient(live_app(tmp_path, per_day=2, sleep=blocked)) as c:
        rid = c.post("/api/live").json()["run_id"]
        run = c.app.state.live
        player = run.match.meta.away.players[0].id
        assert c.post(f"/api/live/{rid}/spotlight", json={"player_id": "XYZ-1"}).status_code == 404
        r = c.post(f"/api/live/{rid}/spotlight", json={"player_id": player})
        assert r.status_code == 200 and r.json() == {"moment_id": f"spotlight-{player}-0"}
        r = c.post(f"/api/live/{rid}/spotlight", json={"player_id": player})
        assert r.status_code == 429 and "Replay is still open" in r.json()["detail"]
        assert c.post("/api/live/live-1-nope/spotlight", json={"player_id": player}).status_code == 404


def test_spotlight_after_full_time_is_refused_for_free(tmp_path):
    with TestClient(live_app(tmp_path)) as c:
        rid = c.post("/api/live").json()["run_id"]
        finish(c, rid)
        player = c.app.state.live.match.meta.home.players[0].id
        r = c.post(f"/api/live/{rid}/spotlight", json={"player_id": player})
        assert r.status_code == 409 and r.json()["detail"] == "This match has finished."
        assert c.get("/api/config").json()["live_remaining"] == 2


def test_skip_moves_the_clock(tmp_path):
    with TestClient(live_app(tmp_path, sleep=blocked)) as c:
        rid = c.post("/api/live").json()["run_id"]
        first = c.app.state.live.moments[0]
        assert c.post(f"/api/live/{rid}/skip").json() == {"clock": first.t - 3}
        assert c.post("/api/live/live-1-nope/skip").status_code == 404


def test_combo_rejects_unknown_personas(tmp_path):
    with TestClient(live_app(tmp_path, sleep=blocked)) as c:
        rid = c.post("/api/live").json()["run_id"]
        assert c.post(f"/api/live/{rid}/combo", json={"persona": "robot", "language": "en"}).status_code == 422
        assert c.post(f"/api/live/{rid}/combo", json={"persona": "casual", "language": "fr"}).status_code == 422
        accepted = [c.post(f"/api/live/{rid}/combo", json={"persona": p, "language": lang}).json()["accepted"]
                    for p, lang in (("casual", "en"), ("pundit", "ar"), ("fantasy", "es"))]
        assert accepted == [True, True, False]


def test_combo_after_full_time_says_the_match_has_finished(tmp_path):
    with TestClient(live_app(tmp_path)) as c:
        rid = c.post("/api/live").json()["run_id"]
        finish(c, rid)
        assert c.post(f"/api/live/{rid}/combo", json={"persona": "casual", "language": "en"}).json() == \
            {"accepted": False, "reason": "finished"}


def test_a_third_combo_says_the_limit_is_reached(tmp_path):
    with TestClient(live_app(tmp_path, sleep=blocked)) as c:
        rid = c.post("/api/live").json()["run_id"]
        replies = [c.post(f"/api/live/{rid}/combo", json={"persona": p, "language": lang}).json()
                   for p, lang in (("casual", "en"), ("pundit", "ar"), ("fantasy", "es"))]
        assert replies == [{"accepted": True, "reason": None}, {"accepted": True, "reason": None},
                           {"accepted": False, "reason": "limit"}]


def test_config_reports_live_runs_left(tmp_path):
    with TestClient(live_app(tmp_path, per_day=3)) as c:
        assert c.get("/api/config").json()["live_mode"] is True
        assert c.get("/api/config").json()["live_remaining"] == 3
        finish(c, c.post("/api/live").json()["run_id"])
        assert c.get("/api/config").json()["live_remaining"] == 2


def test_a_server_without_keys_answers_503_and_spends_nothing(tmp_path):
    def no_keys(_match):
        raise MissingSetting("Missing FOUNDRY_API_KEY.")

    with TestClient(live_app(tmp_path, desk_factory=no_keys)) as c:
        r = c.post("/api/live")
        assert r.status_code == 503 and r.json()["detail"] == "Live mode is not set up on this server."
        assert c.get("/api/config").json()["live_remaining"] == 3 and c.app.state.live is None


def test_the_default_desk_needs_the_keys(monkeypatch):
    monkeypatch.setattr(live_routes, "load_settings", lambda *a, **k: Settings())     # a server with no .env
    with pytest.raises(MissingSetting):
        default_desk_factory(None)


def test_shutting_down_cancels_a_live_run(tmp_path):
    with TestClient(live_app(tmp_path, sleep=blocked)) as c:
        c.post("/api/live")
        run = c.app.state.live
    assert run.done and run.history[-1].data.reason == "cancelled"


def _demo_seed(monkeypatch) -> None:
    monkeypatch.setattr(live_routes.random, "randint", lambda a, b: 42)       # seed 42: the demo match


def _holding_at(app, t: float):
    """A sleep that lets the clock run until t, then holds it there."""
    async def sleep(_s: float) -> None:
        run = app.state.live
        if run is not None and run.clock >= t:
            await asyncio.Event().wait()
    return sleep


def _wait_for_clock(c: TestClient, t: float) -> float:
    import time
    deadline = time.monotonic() + 30
    while c.app.state.live.clock < t:
        assert time.monotonic() < deadline, "the live clock never got there"
        time.sleep(0.02)
    return c.app.state.live.clock


def test_live_overlay_never_runs_past_the_clock(tmp_path, monkeypatch):
    _demo_seed(monkeypatch)
    app = live_app(tmp_path)
    app.state.sleep = _holding_at(app, 1200)
    with TestClient(app) as c:
        rid = c.post("/api/live").json()["run_id"]
        clock = _wait_for_clock(c, 1200)
        cues = c.get(f"/api/live/{rid}/overlay").json()
        assert cues and all(q["match_time"] <= clock for q in cues) and not any(q["precomputed"] for q in cues)
        assert [q["match_time"] for q in cues] == sorted(q["match_time"] for q in cues)
        assert c.get("/api/live/live-1-nope/overlay").status_code == 404


def test_live_overlay_stream_sends_only_cues_then_ends(tmp_path):
    with TestClient(live_app(tmp_path)) as c:
        rid = c.post("/api/live").json()["run_id"]
        msgs = parse_sse(c.get(f"/api/live/{rid}/overlay/stream").text)
        cues = [i.data.id for i in c.app.state.live.history if i.kind == "cue"]
        assert [m["data"]["id"] for m in msgs[:-1]] == cues and {m["event"] for m in msgs[:-1]} == {"cue"}
        assert [m["id"] for m in msgs] == [str(i) for i in range(1, len(cues) + 2)]
        assert msgs[-1]["event"] == "end" and msgs[-1]["data"] == {"reason": "full_time"}
        resumed = parse_sse(c.get(f"/api/live/{rid}/overlay/stream", headers={"Last-Event-ID": "5"}).text)
        assert resumed == msgs[5:]
        assert c.get("/api/live/live-1-nope/overlay/stream").status_code == 404


def test_live_follow_is_clamped_to_the_clock(tmp_path, monkeypatch):
    from jahbadh.api.personal import player_follow
    _demo_seed(monkeypatch)
    app = live_app(tmp_path)
    app.state.sleep = _holding_at(app, 600)
    with TestClient(app) as c:
        rid = c.post("/api/live").json()["run_id"]
        clock = _wait_for_clock(c, 600)
        got = c.get(f"/api/live/{rid}/follow/RMU-33?t=5400").json()
        assert got["t"] == clock and got == player_follow(c.app.state.live.match, "RMU-33", clock).model_dump(mode="json")
        assert c.get(f"/api/live/{rid}/follow/RMU-33?t=100").json()["t"] == 100
        assert c.get(f"/api/live/{rid}/follow/XYZ-1?t=100").status_code == 404
        assert c.get(f"/api/live/{rid}/follow/RMU-33?t=5401").status_code == 422
        assert c.get("/api/live/live-1-nope/follow/RMU-33?t=100").status_code == 404


def test_live_players_never_run_past_the_clock(tmp_path, monkeypatch):
    from jahbadh.api.personal import player_table
    _demo_seed(monkeypatch)
    app = live_app(tmp_path)
    app.state.sleep = _holding_at(app, 600)
    with TestClient(app) as c:
        rid = c.post("/api/live").json()["run_id"]
        clock = _wait_for_clock(c, 600)
        got = c.get(f"/api/live/{rid}/players?t=5400").json()
        assert got == [r.model_dump(mode="json") for r in player_table(c.app.state.live.match, clock)]
        assert c.get(f"/api/live/{rid}/players?t=5401").status_code == 422
        assert c.get("/api/live/live-1-nope/players?t=100").status_code == 404
