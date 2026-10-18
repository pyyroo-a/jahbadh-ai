import pytest

from conftest import make_match, p, pass_xy, shot_by
from jahbadh.agents.evidence import resolve
from jahbadh.analytics import attacking_sides, match_stats, shot_map
from jahbadh.schemas import Event, EventType


def test_match_stats_counts():
    evs = [shot_by(1, "NBR", "NBR-9", 0.4, t=100, goal=True),          # x=95: inside the box for home
           shot_by(2, "NBR", "NBR-9", 0.05, t=200),
           Event(id=3, t=300, period=1, team_id="NBR", player_id="NBR-4", type=EventType.FOUL, x=50, y=34),
           Event(id=4, t=301, period=1, team_id="NBR", player_id="NBR-4", type=EventType.CARD, x=50, y=34,
                 detail={"colour": "yellow"}),
           p(5, "NBR", 50), p(6, "RMU", 50)]
    evs[1] = evs[1].model_copy(update={"x": 75.0})                       # 30 m out
    r = match_stats(make_match(evs), "NBR")
    assert r.value == 2 and r.data["shots_inside_box"] == 1 and r.data["shots_outside_box"] == 1
    assert r.data["goals"] == 1 and r.data["xg"] == pytest.approx(0.45)
    assert r.data["fouls"] == 1 and r.data["yellow_cards"] == 1 and r.data["passes"] == 1
    assert r.data["pass_completion"] == pytest.approx(1.0) and r.evidence_event_ids == [1, 2, 3, 4]
    assert match_stats(make_match([]), "NBR").data["pass_completion"] is None


def test_shot_map_uses_the_attacking_frame_and_ids():
    m = make_match([shot_by(7, "RMU", "RMU-9", 0.3, t=100)])            # away shot at x=10 is 95 in its own frame
    r = shot_map(m, "RMU")
    assert r.data["shots"]["7"]["x"] == pytest.approx(95.0) and r.data["shots"]["7"]["inside_box"] is True
    assert r.data["shots"]["7"]["minute"] == 2 and r.evidence_event_ids == [7]
    assert resolve(r, "shots.7.xg") == pytest.approx(0.3)


def test_attacking_sides_shares():
    evs = [pass_xy(1, "NBR", "NBR-4", (60, 34), (80, 60)), pass_xy(2, "NBR", "NBR-4", (60, 34), (80, 60)),
           pass_xy(3, "NBR", "NBR-4", (60, 34), (80, 10)), pass_xy(4, "NBR", "NBR-4", (80, 34), (90, 34)),  # ends in the final third, so it counts too
           pass_xy(5, "NBR", "NBR-4", (40, 34), (60, 34))]                                                 # ends in midfield: not an entry
    r = attacking_sides(make_match(evs), "NBR")
    assert r.data["entries"] == 4 and r.data["side"] == "left" and r.value == pytest.approx(0.5)
    assert r.data["right"] == pytest.approx(0.25) and r.evidence_event_ids == [1, 2, 3, 4]
    empty = attacking_sides(make_match([]), "NBR")
    assert empty.value is None and empty.note


def test_demo_match_totals(sim_match_demo):
    stats = [match_stats(sim_match_demo, t) for t in ("NBR", "RMU")]
    assert sum(s.value for s in stats) == 30 and sum(s.data["shots_inside_box"] for s in stats) == 12
    assert sum(s.data["fouls"] for s in stats) == 27 and sum(s.data["yellow_cards"] for s in stats) == 5
    halves = [match_stats(sim_match_demo, t, 0, 2700).value + match_stats(sim_match_demo, t, 2700, 5400).value
              for t in ("NBR", "RMU")]
    assert sum(halves) == 30


def test_stats_reject_bad_windows(sim_match):
    for fn in (match_stats, shot_map, attacking_sides):
        with pytest.raises(ValueError, match="window"):
            fn(sim_match, "NBR", 600, 300)


def test_shot_map_carries_shot_speed(sim_match):
    shots = shot_map(sim_match, "NBR").data["shots"].values()
    assert shots and all(35 <= s["speed_kmh"] <= 125 for s in shots)


def test_shot_map_speed_is_none_for_shots_without_one():
    s = shot_map(make_match([shot_by(1, "NBR", "NBR-9", 0.2)]), "NBR").data["shots"]["1"]
    assert s["speed_kmh"] is None
