import pytest

from conftest import intercept, make_match, p, static_tracking, tackle
from jahbadh.analytics.midfield import midfield_control


def test_components_and_mean():
    evs = [p(1, "NBR", 50), p(2, "NBR", 50), p(3, "NBR", 50), p(4, "RMU", 50),   # ball 3 of 4
           tackle(5, "NBR", 50), intercept(6, "RMU", 60)]                          # duels 1 of 2
    pos = {"NBR-6": (50, 30), "NBR-7": (45, 40), "RMU-6": (55, 34)}                # numbers 2 of 3
    r = midfield_control(make_match(evs, tracking=static_tracking(pos, seconds=10)), "NBR")
    assert r.data == {"ball": pytest.approx(0.75), "numbers": pytest.approx(2 / 3), "duels": pytest.approx(0.5)}
    assert r.value == pytest.approx((0.75 + 2 / 3 + 0.5) / 3)
    assert r.evidence_event_ids == [1, 2, 3, 5]


def test_ignores_actions_outside_middle_third():
    r = midfield_control(make_match([p(1, "NBR", 50), p(2, "RMU", 90), tackle(3, "RMU", 20)]), "NBR")
    assert r.data["ball"] == pytest.approx(1.0) and r.data["duels"] is None and r.data["numbers"] is None


def test_goalkeepers_do_not_count_as_midfield_numbers():
    pos = {"NBR-1": (50, 34), "NBR-6": (50, 30), "RMU-6": (55, 34)}  # NBR-1 is the keeper
    r = midfield_control(make_match([], tracking=static_tracking(pos, seconds=5)), "NBR")
    assert r.data["numbers"] == pytest.approx(0.5)


def test_shares_are_complementary(sim_match):
    a, b = midfield_control(sim_match, "NBR"), midfield_control(sim_match, "RMU")
    assert a.value + b.value == pytest.approx(1.0)


def test_empty_window_is_none():
    r = midfield_control(make_match([]), "NBR")
    assert r.value is None and r.note


# Descriptive metric only. A dominance check (midfield control vs field tilt) measured r ~ 0
# over 20 seeds, so agents must not claim "won the midfield, therefore dominated" unless the
# specific match's data shows it.
