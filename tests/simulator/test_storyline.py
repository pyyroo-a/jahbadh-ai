import pytest

from jahbadh.schemas import EventType, ScriptedChange
from jahbadh.simulator import simulate_match
from jahbadh.simulator.storyline import DEMO_STORYLINE

SWITCH = [ScriptedChange(minute=60, team_id="RMU", kind="formation", value="3-4-3")]


@pytest.fixture(scope="module")
def switched():
    return simulate_match(42, storyline=SWITCH)


@pytest.fixture(scope="module")
def demo():
    return simulate_match(42, storyline=DEMO_STORYLINE)


def test_formation_change_event_and_shape(switched):
    fc = switched.events_of(EventType.FORMATION_CHANGE, team_id="RMU")
    assert len(fc) == 1 and fc[0].t == 3600 and fc[0].detail == {"from": "4-3-3", "to": "3-4-3"}


def test_back_line_goes_from_four_to_three(switched):
    m = switched

    def deep_players(start, end):
        # size of RMU's back line: outfield players within 8 m of the deepest one (by mean
        # attacking-x). Relative, so it holds however high the block sits in that spell.
        tr = m.tracking[(m.tracking.team_id == "RMU") & m.tracking.t.between(start, end - 1)]
        gk = next(p.id for p in m.meta.away.players if p.role == "GK" and p.starter)
        ax = 105 - tr[tr.entity_id != gk].groupby("entity_id").x.mean()
        return int((ax < ax.min() + 8).sum())

    assert deep_players(2700, 3600) == 4
    assert deep_players(3660, 5400) == 3


def test_substitution_swaps_tracking_entity(demo):
    sub = demo.events_of(EventType.SUBSTITUTION)[0]
    tr = demo.tracking
    assert sub.t == 3600 and sub.team_id == "RMU"
    assert tr[tr.entity_id == sub.player_id].t.max() == 3599
    assert tr[tr.entity_id == sub.related_player_id].t.min() == 3600


def test_demo_storyline_roles_resolve_to_real_players(demo):
    sub = demo.events_of(EventType.SUBSTITUTION)[0]
    roles = {p.id: p.role for p in demo.meta.away.players}
    assert roles[sub.player_id] == "CM" and roles[sub.related_player_id] == "W"


def test_press_change_event(demo):
    tc = demo.events_of(EventType.TACTIC_CHANGE, team_id="NBR")
    assert len(tc) == 1 and tc[0].t == 4200
    assert tc[0].detail == {"press_height_from": 0.7, "press_height_to": 0.85}


def test_bad_substitution_raises():
    with pytest.raises(ValueError):
        simulate_match(42, storyline=[ScriptedChange(minute=10, team_id="RMU", kind="substitution",
                                                     player_out="RMU-999", player_in="RMU-998")])
