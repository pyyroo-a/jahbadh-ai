import pytest

from conftest import make_match, static_tracking
from jahbadh.analytics.overloads import zone_overloads


def test_detects_left_flank_overload():
    # NBR has 4 players in its final-left zone, RMU has 2 there, for 30 seconds
    pos = {"NBR-7": (80, 60), "NBR-8": (78, 58), "NBR-10": (82, 62), "NBR-11": (85, 55),
           "RMU-2": (80, 59), "RMU-5": (83, 61)}
    r = zone_overloads(make_match([], tracking=static_tracking(pos, seconds=30)), "NBR")
    assert r.data["zone"] == "final-left" and r.data["typical"] == "4v2" and r.value == pytest.approx(1.0)
    assert r.evidence_frames == (0, 5399) and r.data["by_zone"]["final-left"] == pytest.approx(1.0)


def test_away_overload_uses_away_view():
    pos = {"RMU-7": (25, 8), "RMU-8": (27, 10), "RMU-10": (23, 6), "NBR-2": (25, 9)}
    r = zone_overloads(make_match([], tracking=static_tracking(pos, seconds=10)), "RMU")
    assert r.data["zone"] == "final-left"  # low y is the away team's left when attacking toward x=0


def test_opponent_goalkeeper_does_not_count():
    # 3 NBR attackers vs RMU's keeper + 1 defender in the box: 3v1 outfield, an overload
    pos = {"NBR-9": (100, 34), "NBR-10": (98, 30), "NBR-11": (99, 38), "RMU-1": (103, 34), "RMU-4": (100, 33)}
    r = zone_overloads(make_match([], tracking=static_tracking(pos, seconds=10)), "NBR")
    assert r.data["zone"] == "final-centre" and r.data["typical"] == "3v1"


def test_headline_zone_ignores_defensive_third():
    # NBR: 3v0 in its own defensive-centre (trivial, always there) and 3v1 in middle-left (interesting)
    pos = {"NBR-2": (20, 34), "NBR-3": (22, 30), "NBR-4": (21, 38),
           "NBR-6": (50, 60), "NBR-7": (52, 58), "NBR-8": (48, 62), "RMU-6": (50, 59)}
    r = zone_overloads(make_match([], tracking=static_tracking(pos, seconds=10)), "NBR")
    assert r.data["zone"] == "middle-left" and r.data["typical"] == "3v1"
    assert r.data["by_zone"]["defensive-centre"] == pytest.approx(1.0)  # still reported, just not the headline


def test_only_defensive_overloads_gives_none_but_keeps_by_zone():
    pos = {"NBR-2": (20, 34), "NBR-3": (22, 30), "NBR-4": (21, 38)}
    r = zone_overloads(make_match([], tracking=static_tracking(pos, seconds=10)), "NBR")
    assert r.value is None and r.note and r.data["by_zone"]["defensive-centre"] == pytest.approx(1.0)


def test_no_overload_returns_none():
    pos = {"NBR-7": (80, 60), "RMU-2": (80, 59)}
    r = zone_overloads(make_match([], tracking=static_tracking(pos, seconds=10)), "NBR")
    assert r.value is None and r.note


def test_demo_storyline_shows_rmu_overload_after_switch(sim_match_demo):
    after = zone_overloads(sim_match_demo, "RMU", 3600, 4500)
    assert after.value is not None
