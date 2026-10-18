import pytest

from fakes import demo_match, make_match, p, static_tracking
from jahbadh.agents.contracts import Moment
from jahbadh.agents.evidence import (EvidenceStore, broadcast_window, describe_event, formation_at, moment_context,
                                     is_share, resolve, score_at, summarize)
from jahbadh.analytics import before_after, field_tilt, heatmap, zone_overloads
from jahbadh.schemas import EventType


def test_broadcast_window():
    assert broadcast_window((3600, 4500)) == "61'-75'" and broadcast_window((0, 5400)) == "1'-90'"


def test_store_roundtrip():
    m = make_match([p(1, "NBR", 80), p(2, "RMU", 20)])
    store = EvidenceStore(m)
    tilt = store.add(field_tilt(m, "NBR"))
    assert tilt.id in store and store.get(tilt.id) is tilt and store.metrics() == [tilt]
    with pytest.raises(KeyError):
        store.get("nope")


def test_summary_fields_are_citable():
    s = summarize(field_tilt(make_match([p(1, "NBR", 80), p(2, "RMU", 20)]), "NBR"))
    assert s["window"] == "1'-90'" and s["fields"] == {"value": 0.5, "team_passes": 1, "opponent_passes": 1}


def test_change_metric_exposes_before_and_after():
    r = before_after(field_tilt, demo_match(), "RMU", at_t=3600)
    f = summarize(r)["fields"]
    assert set(f) == {"value", "before.value", "after.value", "at_t"}
    assert resolve(r, "before.value") == r.data["before"]["value"]


def test_resolve_nested_and_missing():
    r = zone_overloads(demo_match(), "RMU", 3600, 4500, margin=1)
    zone = r.data["zone"]
    assert resolve(r, f"by_zone.{zone}") == r.value and resolve(r, "typical") == r.data["typical"]
    with pytest.raises(KeyError):
        resolve(r, "by_zone.nowhere")


def test_heatmap_hot_zones():
    m = make_match([], tracking=static_tracking({"NBR-9": (90, 60)}, seconds=10))
    assert summarize(heatmap(m, "NBR-9", 0, 10))["extra"]["hot_zones"] == [["final-left", 1.0]]


def test_describe_formation_change_uses_broadcast_minute():
    m = demo_match()
    e = next(e for e in m.events if e.type == EventType.FORMATION_CHANGE)
    line = describe_event(m, e)
    assert line.startswith(f"#{e.id} 61' RMU FORMATION_CHANGE") and "4-3-3 -> 3-4-3" in line


def test_describe_pass_names_both_players():
    m = demo_match()
    e = next(e for e in m.events if e.type == EventType.PASS and e.outcome)
    line = describe_event(m, e)
    names = {pl.id: pl.name for t in (m.meta.home, m.meta.away) for pl in t.players}
    assert names[e.player_id] in line and names[e.related_player_id] in line


def test_score_and_formation_at():
    m = demo_match()
    first_goal = next(e for e in m.events if e.type == EventType.GOAL)
    assert sum(score_at(m, first_goal.t).values()) == 0
    assert sum(score_at(m, first_goal.t + 1).values()) == 1
    assert formation_at(m, "RMU", 3599) == "4-3-3" and formation_at(m, "RMU", 3601) == "3-4-3"


def test_moment_minute_and_horizon():
    mo = Moment(id="goal-901", kind="goal", t=901.4, label="x")
    assert mo.minute == 16 and mo.horizon == 902.0
    assert Moment(id="ft", kind="full_time", t=5400, label="FT").minute == 90
    assert Moment(id="ft", kind="full_time", t=5400, label="FT").horizon == 5400.0


def test_moment_context_lists_teams_score_and_players():
    m = demo_match()
    switch = next(e for e in m.events if e.type == EventType.FORMATION_CHANGE)
    ctx = moment_context(m, Moment(id="x", kind="formation_change", t=switch.t, event_ids=[switch.id],
                                   team_id="RMU", label="61' switch"))
    assert m.meta.home.name in ctx and m.meta.away.name in ctx and "3-4-3" in ctx
    assert describe_event(m, switch) in ctx and m.meta.away.players[0].name in ctx


def test_accuracy_reads_as_a_percentage():
    from jahbadh.analytics import pass_quality
    q = pass_quality(demo_match(), "NBR")
    assert is_share(q, "accuracy") and not is_share(q, "value") and not is_share(q, "mean_length_m")


def test_describe_shot_includes_its_synthetic_speed():
    m = demo_match()
    shot = next(e for e in m.events if e.type == EventType.SHOT)
    assert f"speed {shot.detail['speed_kmh']:.0f} km/h" in describe_event(m, shot)
