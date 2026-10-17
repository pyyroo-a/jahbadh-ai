"""Regression tests for the Plan 1 review findings (assists, metric ids, unknown teams)."""

import pytest

from conftest import make_match, pr, shot_by, static_tracking
from jahbadh.analytics import (before_after, field_tilt, heatmap, pass_network, player_impact, player_rankings,
                               xg_timeline, xg_total, zone_overloads)
from jahbadh.schemas import Event, EventType


def _ev(id, team, type, t, outcome=None):
    return Event(id=id, t=t, period=1, team_id=team, player_id=f"{team}-4", type=type, x=80, y=34, outcome=outcome)


def test_opponent_pressure_or_failed_tackle_does_not_break_an_assist():
    evs = [pr(1, "NBR", "NBR-8", "NBR-9", t=100), _ev(2, "RMU", EventType.PRESSURE, 101),
           _ev(3, "RMU", EventType.TACKLE, 102, outcome=False), shot_by(4, "NBR", "NBR-9", xg=0.3, t=103)]
    m = make_match(evs, tracking=static_tracking({"NBR-8": (60, 30), "NBR-9": (90, 34)}, seconds=200))
    assert player_impact(m, "NBR-8").data["xa"] == pytest.approx(0.3)


def test_won_tackle_still_breaks_an_assist():
    evs = [pr(1, "NBR", "NBR-8", "NBR-9", t=100), _ev(2, "RMU", EventType.TACKLE, 101, outcome=True),
           shot_by(3, "NBR", "NBR-9", xg=0.3, t=103)]
    m = make_match(evs, tracking=static_tracking({"NBR-8": (60, 30), "NBR-9": (90, 34)}, seconds=200))
    assert player_impact(m, "NBR-8").data["xa"] == 0


def test_metric_ids_include_parameters_that_change_the_value(sim_match):
    assert zone_overloads(sim_match, "RMU", 3600, 4500).id == "zone_overloads:RMU:3600-4500"  # defaults unchanged
    assert zone_overloads(sim_match, "RMU", 3600, 4500, margin=1).id != zone_overloads(sim_match, "RMU", 3600, 4500).id
    assert pass_network(sim_match, "RMU", min_passes=1).id != pass_network(sim_match, "RMU").id
    assert heatmap(sim_match, "RMU", grid=(10, 7)).id != heatmap(sim_match, "RMU").id


def test_before_after_ids_differ_when_clamped_windows_coincide(sim_match):
    a = before_after(field_tilt, sim_match, "RMU", at_t=600)
    b = before_after(field_tilt, sim_match, "RMU", at_t=700, window_s=800)
    assert a.window == b.window and a.id != b.id


@pytest.mark.parametrize("fn", [xg_total, xg_timeline])
def test_unknown_team_raises_instead_of_returning_zero(sim_match, fn):
    with pytest.raises(KeyError):
        fn(sim_match, "Northbridge")


def test_rankings_unknown_team_raises(sim_match):
    with pytest.raises(KeyError):
        player_rankings(sim_match, team_id="nbr")
