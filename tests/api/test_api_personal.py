import pytest

from apifakes import demo_match, parse_sse
from jahbadh import analytics as an
from jahbadh.api.personal import METRIC_CHOICES, player_follow


def test_follow_never_sees_the_future():
    m = demo_match()
    f = player_follow(m, "RMU-33", 1318)
    assert f.player_id == "RMU-33" and f.t == 1318 and f.on_pitch
    for metric in (f.impact, f.heatmap, f.physical, f.passing):
        assert metric.window == (0.0, 1318.0) and metric.subject == "RMU-33"
    assert [f.impact.name, f.heatmap.name, f.physical.name, f.passing.name] == \
        ["player_impact", "heatmap", "physical", "pass_quality"]
    assert f.impact.data["goals"] == 1                                   # the 22' goal (t 1317)
    assert f.event_ids and all(m.event(i).t < 1318 for i in f.event_ids)
    mine = {e.id for e in m.events if e.t < 1318 and "RMU-33" in (e.player_id, e.related_player_id)}
    assert set(f.event_ids) == mine and f.event_ids == sorted(f.event_ids)


def test_follow_at_kickoff_is_empty():
    f = player_follow(demo_match(), "RMU-33", 0)
    assert f.event_ids == [] and f.on_pitch
    assert all(x.value is None and x.window == (0.0, 0.0) and x.note for x in (f.impact, f.heatmap, f.physical, f.passing))


def test_a_sub_who_has_not_come_on_is_off_the_pitch():
    m = demo_match()
    sub = next(e.related_player_id for e in m.events if e.type.value == "SUBSTITUTION")
    assert not player_follow(m, sub, 1800).on_pitch and player_follow(m, sub, 4000).on_pitch


def test_follow_rejects_an_unknown_player_and_a_bad_time():
    with pytest.raises(KeyError):
        player_follow(demo_match(), "XYZ-1", 600)
    with pytest.raises(ValueError):
        player_follow(demo_match(), "RMU-33", 6000)


def test_metric_choices_name_real_state_fields_and_metrics():
    m = demo_match()
    real = {an.xg_total(m, "NBR").name, an.shot_map(m, "NBR").name, an.player_impact(m, "RMU-33").name,
            an.ppda(m, "NBR").name, an.field_tilt(m, "NBR").name, an.momentum(m, 600).name,
            an.pass_quality(m, "NBR").name, an.game_rhythm(m).name}
    assert list(METRIC_CHOICES) == ["xg", "ppda", "field_tilt", "momentum", "pass_difficulty", "rhythm"]
    assert [c.label for c in METRIC_CHOICES.values()] == ["xG", "PPDA", "Field tilt", "Momentum", "Pass difficulty",
                                                          "Game rhythm"]
    assert all(c.key == k and c.state_field == k for k, c in METRIC_CHOICES.items())
    assert {n for c in METRIC_CHOICES.values() for n in c.metric_names} == real


def test_parse_sse_reads_events_and_skips_pings():
    text = 'event: tick\ndata: {"t":0}\nid: 1\n\n: ping\n\nevent: end\ndata: {"reason": "full_time"}\n\n'
    assert parse_sse(text) == [{"event": "tick", "data": {"t": 0}, "id": "1"},
                               {"event": "end", "data": {"reason": "full_time"}}]
