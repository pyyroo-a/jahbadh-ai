import pytest
from fastapi.testclient import TestClient

from apifakes import api_settings as settings, last_t, parse_sse, recording_sleep
from jahbadh.api.app import create_app
from jahbadh.api.overlay import overlay_cues
from jahbadh.api.personal import METRIC_CHOICES, player_follow
from jahbadh.api.timeline import REPLAY_DESK_LAG_S


@pytest.fixture(scope="module")
def desk(tmp_path_factory):
    sleep, slept = recording_sleep()
    with TestClient(create_app(settings(tmp_path_factory.mktemp("state")), sleep=sleep)) as c:
        yield c, slept


@pytest.fixture
def c(desk):
    desk[1].clear()
    return desk[0]


@pytest.fixture(scope="module")
def show(desk):
    return desk[0].app.state.showcases["match-042"]


def _main_stream_cues(timeline) -> list[str]:
    return [i.data.id for i in timeline if i.kind == "cue"]


def test_overlay_json_and_schema(c, show):
    cues = c.get("/api/replay/match-042/overlay").json()
    assert [q["match_time"] for q in cues] == sorted(q["match_time"] for q in cues)
    assert all(q["precomputed"] is True for q in cues)
    assert sorted(q["id"] for q in cues) == sorted(q.id for q in overlay_cues(show.match, show.desk, REPLAY_DESK_LAG_S))
    assert [q["id"] for q in cues] == _main_stream_cues(c.app.state.timelines["match-042"])  # same order as streamed
    schema = c.get("/api/overlay/schema").json()
    assert "match_time" in schema["properties"] and "text" in schema["required"]
    assert c.get("/api/replay/match-999/overlay").status_code == 404


def test_overlay_stream_sends_only_cues_then_ends(c):
    timeline = c.app.state.timelines["match-042"]
    msgs = parse_sse(c.get("/api/replay/match-042/overlay/stream?speed=6").text)
    cues = _main_stream_cues(timeline)
    assert [m["data"]["id"] for m in msgs[:-1]] == cues and {m["event"] for m in msgs[:-1]} == {"cue"}
    assert [m["id"] for m in msgs] == [str(i) for i in range(1, len(cues) + 2)]
    assert msgs[-1]["event"] == "end" and msgs[-1]["data"] == {"reason": "full_time"}


def test_overlay_stream_is_paced_and_resumes(desk):
    c, slept = desk
    timeline = c.app.state.timelines["match-042"]
    slept.clear()
    parse_sse(c.get("/api/replay/match-042/overlay/stream?speed=6").text)
    assert sum(slept) == pytest.approx(last_t(timeline) / 6)
    slept.clear()
    msgs = parse_sse(c.get("/api/replay/match-042/overlay/stream?from_t=3600", headers={"Last-Event-ID": "10"}).text)
    assert msgs[0]["id"] == "11" and sum(slept) == pytest.approx((last_t(timeline) - 3600) / 6)
    assert c.get("/api/replay/match-999/overlay/stream").status_code == 404


def test_follow_endpoint_and_unknown_player(c, show):
    got = c.get("/api/replay/match-042/follow/RMU-33?t=1318")
    assert got.status_code == 200
    assert got.json() == player_follow(show.match, "RMU-33", 1318).model_dump(mode="json")
    assert c.get("/api/replay/match-042/follow/XYZ-1?t=600").status_code == 404
    assert c.get("/api/replay/match-999/follow/RMU-33?t=600").status_code == 404
    assert c.get("/api/replay/match-042/follow/RMU-33?t=5401").status_code == 422
    assert c.get("/api/replay/match-042/follow/RMU-33").status_code == 422


def test_config_lists_the_metric_choices(c):
    choices = c.get("/api/config").json()["metric_choices"]
    assert choices == [m.model_dump() for m in METRIC_CHOICES.values()]
    assert [m["key"] for m in choices] == ["xg", "ppda", "field_tilt", "momentum", "pass_difficulty", "rhythm"]
