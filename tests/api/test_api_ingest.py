import time

from fastapi.testclient import TestClient

from apifakes import api_settings, demo_match, no_sleep, parse_sse, scripted_full_desk_client
from jahbadh.agents.desk import Desk
from jahbadh.api.app import create_app
from jahbadh.api.personal import player_table

DEMO = demo_match()
TOKEN = {"X-Ingest-Token": "tok"}
FIRST_GOAL = next(e for e in DEMO.events if e.type == "GOAL")


def scripted_desk(match):
    return Desk(client=scripted_full_desk_client(), match=match)


def ingest_app(tmp_path, token="tok", live_mode=False, per_day=3, now=time.monotonic):
    return create_app(api_settings(tmp_path, ingest_token=token, live_mode=live_mode, live_per_day=per_day),
                      desk_factory=scripted_desk, sleep=no_sleep, now=now)


def start_body() -> dict:
    return {"home": DEMO.meta.home.model_dump(mode="json"), "away": DEMO.meta.away.model_dump(mode="json")}


def batch(first: int, last: int) -> dict:
    """Events with ids first..last (inclusive) and the tracking frames up to the last one's second."""
    events = [e for e in DEMO.events if first <= e.id <= last]
    lo, hi = events[0].t, events[-1].t
    tr = DEMO.tracking[(DEMO.tracking["t"] >= lo) & (DEMO.tracking["t"] <= hi)]
    return {"events": [e.model_dump(mode="json") for e in events], "frames": tr.to_dict(orient="records")}


def start(c: TestClient) -> dict:
    r = c.post("/api/ingest", json=start_body(), headers=TOKEN)
    assert r.status_code == 200, r.text
    return r.json()


def test_ingest_is_off_without_a_token_setting(tmp_path):
    with TestClient(ingest_app(tmp_path, token=None)) as c:
        assert c.post("/api/ingest", json=start_body(), headers=TOKEN).status_code == 404
        assert c.get("/api/ingest/ingest-x/stream").status_code == 404
        assert c.get("/api/config").json()["ingest"] == {"on": False, "run_id": None}


def test_writes_need_the_token(tmp_path):
    with TestClient(ingest_app(tmp_path)) as c:
        assert c.post("/api/ingest", json=start_body()).status_code == 401
        assert c.post("/api/ingest", json=start_body(), headers={"X-Ingest-Token": "nope"}).status_code == 401
        assert c.app.state.ingest is None
        rid = start(c)["run_id"]
        assert c.post(f"/api/ingest/{rid}/events", json=batch(1, 5)).status_code == 401
        assert len(c.app.state.ingest.match.events) == 0


def test_events_stream_as_they_arrive(tmp_path):
    with TestClient(ingest_app(tmp_path)) as c:
        reply = start(c)
        rid = reply["run_id"]
        assert reply["agents"] is False and c.get("/api/config").json()["ingest"] == {"on": True, "run_id": rid}
        assert c.post(f"/api/ingest/{rid}/events", json=batch(1, 50), headers=TOKEN).json()["accepted"] == 50
        assert c.post(f"/api/ingest/{rid}/events", json=batch(51, 100), headers=TOKEN).status_code == 200
        assert c.post(f"/api/ingest/{rid}/close", headers=TOKEN).status_code == 200
        msgs = parse_sse(c.get(f"/api/ingest/{rid}/stream").text)
        assert msgs[0]["event"] == "match" and msgs[0]["data"]["mode"] == "ingest" and not msgs[0]["data"]["precomputed"]
        assert [m["data"]["id"] for m in msgs if m["event"] == "event"] == list(range(1, 101))
        assert msgs[-1] == {"event": "end", "id": str(len(msgs) - 1), "data": {"reason": "full_time"}}


def test_a_state_arrives_for_each_minute_crossed(tmp_path):
    with TestClient(ingest_app(tmp_path)) as c:
        rid = start(c)["run_id"]
        last = max(e.id for e in DEMO.events if e.t <= 200)
        c.post(f"/api/ingest/{rid}/events", json=batch(1, last), headers=TOKEN)
        states = [i.t for i in c.app.state.ingest.history if i.kind == "state"]
        assert states == [0.0, 60.0, 120.0, 180.0]


def test_out_of_order_or_repeated_events_are_refused(tmp_path):
    with TestClient(ingest_app(tmp_path)) as c:
        rid = start(c)["run_id"]
        c.post(f"/api/ingest/{rid}/events", json=batch(1, 10), headers=TOKEN)
        run = c.app.state.ingest
        before = (len(run.history), run.clock, len(run.match.events))
        again = c.post(f"/api/ingest/{rid}/events", json=batch(10, 12), headers=TOKEN)        # id 10 repeated
        assert again.status_code == 422 and "11" in again.json()["detail"]
        skipped = c.post(f"/api/ingest/{rid}/events", json=batch(12, 14), headers=TOKEN)      # id 11 missing
        assert skipped.status_code == 422
        late = batch(11, 12)
        late["events"][1]["t"] = 0.0                                                            # back in time
        assert c.post(f"/api/ingest/{rid}/events", json=late, headers=TOKEN).status_code == 422
        assert (len(run.history), run.clock, len(run.match.events)) == before


def test_a_player_off_the_team_sheet_is_refused(tmp_path):
    with TestClient(ingest_app(tmp_path)) as c:
        rid = start(c)["run_id"]
        bad = batch(1, 3)
        bad["events"][2]["player_id"] = "XYZ-1"
        r = c.post(f"/api/ingest/{rid}/events", json=bad, headers=TOKEN)
        assert r.status_code == 422 and "XYZ-1" in r.json()["detail"]
        assert len(c.app.state.ingest.match.events) == 0


def _wait_for(c: TestClient, kind: str, timeout: float = 30.0):
    deadline = time.monotonic() + timeout
    while not any(i.kind == kind for i in c.app.state.ingest.history):
        assert time.monotonic() < deadline, f"no {kind} arrived"
        time.sleep(0.02)


def test_a_goal_wakes_the_agents_and_one_match_spends_one_action(tmp_path):
    with TestClient(ingest_app(tmp_path, live_mode=True)) as c:
        reply = start(c)
        rid = reply["run_id"]
        assert reply["agents"] is True and c.app.state.limit.remaining() == 2
        c.post(f"/api/ingest/{rid}/events", json=batch(1, FIRST_GOAL.id + 5), headers=TOKEN)
        _wait_for(c, "feed")
        feeds = [i.data.moment for i in c.app.state.ingest.history if i.kind == "feed"]
        assert any(m.kind == "goal" and m.t == FIRST_GOAL.t for m in feeds)
        assert c.app.state.limit.remaining() == 2


def test_no_actions_left_means_template_lines_only(tmp_path):
    with TestClient(ingest_app(tmp_path, live_mode=True, per_day=0)) as c:
        reply = start(c)
        assert reply["agents"] is False
        c.post(f"/api/ingest/{reply['run_id']}/events", json=batch(1, FIRST_GOAL.id + 5), headers=TOKEN)
        kinds = {i.kind for i in c.app.state.ingest.history}
        assert "event" in kinds and "thinking" not in kinds


def test_live_and_ingest_never_run_at_once(tmp_path):
    async def blocked(_s: float) -> None:
        import asyncio
        await asyncio.Event().wait()
    with TestClient(ingest_app(tmp_path, live_mode=True)) as c:
        start(c)
        r = c.post("/api/live")
        assert r.status_code == 409 and "outside feed" in r.json()["detail"]
        assert c.app.state.limit.remaining() == 2
    app = ingest_app(tmp_path / "b", live_mode=True)
    app.state.sleep = blocked
    with TestClient(app) as c:
        assert c.post("/api/live").status_code == 200
        r = c.post("/api/ingest", json=start_body(), headers=TOKEN)
        assert r.status_code == 409 and "live match" in r.json()["detail"]
        assert c.app.state.limit.remaining() == 2


def test_full_time_event_ends_the_stream(tmp_path):
    with TestClient(ingest_app(tmp_path)) as c:
        rid = start(c)["run_id"]
        ids = [e.id for e in DEMO.events]
        for lo in range(1, ids[-1] + 1, 400):
            assert c.post(f"/api/ingest/{rid}/events", json=batch(lo, min(lo + 399, ids[-1])), headers=TOKEN).status_code == 200
        msgs = parse_sse(c.get(f"/api/ingest/{rid}/stream").text)
        assert msgs[-1]["data"] == {"reason": "full_time"}
        assert [m["data"]["t"] for m in msgs if m["event"] == "state"][-1] == 5400.0


def test_nobody_watching_stops_the_agents_but_not_the_events(tmp_path):
    clock = [0.0]
    with TestClient(ingest_app(tmp_path, live_mode=True, now=lambda: clock[0])) as c:
        rid = start(c)["run_id"]
        clock[0] = 61.0                                                       # nobody has watched for a minute
        c.post(f"/api/ingest/{rid}/events", json=batch(1, FIRST_GOAL.id + 5), headers=TOKEN)
        kinds = [i.kind for i in c.app.state.ingest.history]
        assert "event" in kinds and "thinking" not in kinds


def test_players_never_run_past_the_latest_event(tmp_path):
    with TestClient(ingest_app(tmp_path)) as c:
        rid = start(c)["run_id"]
        c.post(f"/api/ingest/{rid}/events", json=batch(1, FIRST_GOAL.id + 5), headers=TOKEN)
        run = c.app.state.ingest
        got = c.get(f"/api/ingest/{rid}/players?t=5400").json()
        assert got == [r.model_dump(mode="json") for r in player_table(run.match, run.clock)]
        assert c.get(f"/api/ingest/{rid}/follow/NBR-72?t=5400").json()["t"] == run.clock
        assert c.get("/api/ingest/ingest-nope/players?t=1").status_code == 404


def test_resume_by_last_event_id(tmp_path):
    with TestClient(ingest_app(tmp_path)) as c:
        rid = start(c)["run_id"]
        c.post(f"/api/ingest/{rid}/events", json=batch(1, 30), headers=TOKEN)
        c.post(f"/api/ingest/{rid}/close", headers=TOKEN)
        full = parse_sse(c.get(f"/api/ingest/{rid}/stream").text)
        assert parse_sse(c.get(f"/api/ingest/{rid}/stream", headers={"Last-Event-ID": "5"}).text) == full[6:]


def test_an_ingest_moment_reports_its_steps(tmp_path):
    with TestClient(ingest_app(tmp_path, live_mode=True)) as c:
        rid = start(c)["run_id"]
        c.post(f"/api/ingest/{rid}/events", json=batch(1, FIRST_GOAL.id + 5), headers=TOKEN)
        _wait_for(c, "feed")
        history = c.app.state.ingest.history
        goal = next(i.data.moment.id for i in history if i.kind == "feed")
        steps = [i.data.step for i in history if i.kind == "step" and i.data.moment_id == goal]
        assert steps[0] == "analyst" and steps[-1] == "publish"
