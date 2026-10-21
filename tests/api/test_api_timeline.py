import pytest

from apifakes import SHOWCASE_ROOT, demo_match
from jahbadh.agents.evidence import score_at
from jahbadh.analytics import xg_total
from jahbadh.api.overlay import OverlayCue, event_cues, metric_cues
from jahbadh.api.showcase import load_showcases
from jahbadh.api.stream import EventLine, MatchState, StreamEnd, StreamItem
from jahbadh.api.timeline import REPLAY_DESK_LAG_S, event_line, match_state, match_timeline, replay_timeline


def test_the_timeline_holds_every_event_and_a_state_every_minute():
    m = demo_match()
    tl = match_timeline(m)
    assert sum(i.kind == "event" for i in tl) == len(m.events)
    assert [i.t for i in tl if i.kind == "state"] == [60.0 * k for k in range(91)]
    assert [i.t for i in tl] == sorted(i.t for i in tl)
    assert {i.kind for i in tl} == {"event", "state", "cue"} and all(isinstance(i, StreamItem) for i in tl)


def test_events_come_before_the_state_at_the_same_second():
    tl = match_timeline(demo_match())
    at_60 = [i.kind for i in tl if i.t == 60.0]
    assert at_60[-1] == "state" and set(at_60[:-1]) <= {"event", "cue"}


def test_kickoff_state_is_empty():
    s = match_state(demo_match(), 0)
    assert s.score == {"NBR": 0, "RMU": 0} and s.xg == {"NBR": 0.0, "RMU": 0.0} and s.minute == 1
    assert s.momentum is None and s.field_tilt is None and s.ppda == {"NBR": None, "RMU": None} and s.shape == {}
    assert s.formations == {"NBR": "4-3-3", "RMU": "4-3-3"}


def test_a_state_never_counts_the_future():
    m = demo_match()
    s = match_state(m, 900)
    assert s.score == score_at(m, 900) and s.score["NBR"] == 1          # the 15' goal (t 885)
    assert s.xg["NBR"] == pytest.approx(xg_total(m, "NBR", 0, 900).value)
    assert s.shape["RMU"].window == (300.0, 900.0) and s.shape["RMU"].name == "average_positions"
    assert s.minute == 16 and 0 <= s.momentum <= 1 and 0 <= s.field_tilt <= 1


def test_the_formation_switch_shows_in_the_state():
    m = demo_match()
    assert match_state(m, 3600).formations["RMU"] == "4-3-3"           # the switch happens at 60:00
    assert match_state(m, 3660).formations["RMU"] == "3-4-3"


def test_full_time_state_is_minute_90():
    s = match_state(demo_match(), 5400)
    assert s.minute == 90 and s.score == {"NBR": 3, "RMU": 5}


def test_replay_thinks_before_it_publishes():
    show = load_showcases(SHOWCASE_ROOT)["match-042"]
    tl = replay_timeline(show)
    for item in show.desk.items:
        think = next(k for k, i in enumerate(tl) if i.kind == "thinking" and i.data.id == item.moment.id)
        feed = next(k for k, i in enumerate(tl) if i.kind == "feed" and i.data.moment.id == item.moment.id)
        assert think < feed and tl[feed].t == item.moment.t + REPLAY_DESK_LAG_S
    assert tl[-1].kind == "end" and tl[-1].data == StreamEnd(reason="full_time")
    assert [i.t for i in tl] == sorted(i.t for i in tl)
    assert sum(i.kind == "feed" for i in tl) == len(show.desk.items)


def test_event_line_payload_keys_are_the_protocol():
    m = demo_match()
    line = event_line(m, m.event(2))
    assert isinstance(line, EventLine) and line.lines["en"] == "Marek Quill finds Quinn Yilmaz" and line.minute == 1
    assert set(line.model_dump()) == {"id", "t", "minute", "type", "team_id", "player_id", "related_player_id",
                                      "x", "y", "end_x", "end_y", "outcome", "xg", "speed_kmh", "lines", "buildup"}


def test_match_state_payload_keys_are_the_protocol():
    assert set(MatchState.model_fields) == {"t", "minute", "score", "xg", "momentum", "field_tilt", "ppda", "shape",
                                            "formations", "rhythm", "pass_difficulty", "pass_speed", "shots"}


def test_cues_ride_in_the_timeline_at_their_time():
    m = demo_match()
    cues = [i for i in match_timeline(m) if i.kind == "cue"]
    assert len(cues) == len(event_cues(m)) + len(metric_cues(m))
    assert all(i.t == i.data.match_time and isinstance(i.data, OverlayCue) for i in cues)
    assert not any(i.data.type == "claim" for i in cues)                # claims only come with the desk


def test_state_carries_rhythm_and_pass_difficulty():
    m = demo_match()
    s = match_state(m, 3600)
    assert s.rhythm.name == "game_rhythm" and s.rhythm.window == (3000.0, 3600.0)
    assert set(s.pass_difficulty) == {"NBR", "RMU"} and all(0 < v < 1 for v in s.pass_difficulty.values())
    kickoff = match_state(m, 0)
    assert kickoff.rhythm is None and kickoff.pass_difficulty == {"NBR": None, "RMU": None}


def test_claim_cues_arrive_right_after_their_feed_item():
    show = load_showcases(SHOWCASE_ROOT)["match-042"]
    tl = replay_timeline(show)
    for item in show.desk.items:
        feed = next(k for k, i in enumerate(tl) if i.kind == "feed" and i.data.moment.id == item.moment.id)
        mine = [k for k, i in enumerate(tl) if i.kind == "cue" and i.data.type == "claim"
                and i.data.id.startswith(f"claim-{item.moment.id}:")]
        assert len(mine) == len(item.claims) and all(k > feed and tl[k].t == tl[feed].t for k in mine)


def test_event_lines_and_states_carry_pass_speed():
    m = demo_match()
    a_pass = next(e for e in m.events if e.type == "PASS")
    a_shot = next(e for e in m.events if e.type == "SHOT")
    a_card = next(e for e in m.events if e.type == "CARD")
    assert event_line(m, a_pass).speed_kmh == a_pass.detail["speed_kmh"]
    assert event_line(m, a_shot).speed_kmh == a_shot.detail["speed_kmh"]
    assert event_line(m, a_card).speed_kmh is None
    s = match_state(m, 3600)
    assert set(s.pass_speed) == {"NBR", "RMU"} and all(20 <= v <= 100 for v in s.pass_speed.values())
    assert match_state(m, 0).pass_speed == {"NBR": None, "RMU": None}


def test_states_count_shots_per_team():
    from jahbadh.analytics import match_stats
    m = demo_match()
    full = match_state(m, 5400)
    assert full.shots == {t: match_stats(m, t).data["shots"] for t in ("NBR", "RMU")}
    assert match_state(m, 600).shots == {t: match_stats(m, t, 0, 600).data["shots"] for t in ("NBR", "RMU")}
    assert match_state(m, 0).shots == {"NBR": 0, "RMU": 0}
