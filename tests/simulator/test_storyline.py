import pytest

from jahbadh.schemas import EventType, ScriptedChange
from jahbadh.simulator import simulate_match
from jahbadh.simulator.formations import FORMATIONS, slots_for
from jahbadh.simulator.storyline import DEMO_STORYLINE, remap_order

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


def test_remap_moves_players_line_by_line():
    # 4-3-3 -> 3-4-3: the new back three must come from the old back four, a full-back steps up to
    # wing-back, and the front three stays the front three. Slot indices: 1-4 back four, 5-7 midfield, 8-10 front.
    order = remap_order("4-3-3", "3-4-3")
    assert order[0] == 0 and sorted(order) == list(range(11))
    assert set(order[1:4]) <= {1, 2, 3, 4}
    assert set(order[8:11]) == {8, 9, 10}


def test_remap_never_pushes_a_deeper_player_ahead_of_a_more_advanced_one():
    names = list(FORMATIONS)
    for old in names:
        for new in names:
            old_ax = [ax for _, ax, _ in slots_for(old)]
            new_ax = [ax for _, ax, _ in slots_for(new)]
            order = remap_order(old, new)
            for i in range(1, 11):
                for j in range(1, 11):
                    if new_ax[i] < new_ax[j] - 10:  # slot i is clearly behind slot j
                        assert old_ax[order[i]] <= old_ax[order[j]], (old, new, i, j)


def test_switch_keeps_defenders_at_the_back(switched):
    m = switched
    roles = {p.id: p.role for p in m.meta.away.players}
    tr = m.tracking[(m.tracking.team_id == "RMU") & m.tracking.t.between(3660, 5399)]
    ax = (105 - tr.groupby("entity_id").x.mean()).drop([p for p in roles if roles[p] == "GK"], errors="ignore")
    deepest, front = ax.nsmallest(3).index, ax.nlargest(3).index
    assert all(roles[p] in ("CB", "FB") for p in deepest)
    assert not any(roles[p] in ("CB", "FB") for p in front)


def test_minute_conventions_agree(demo):
    # ScriptedChange.minute = elapsed whole minutes (the change happens at mm:00 on the clock).
    # Event.minute = broadcast minute, 1-based like a TV clock, so 60:00 shows as 61'.
    # Agents and the UI must quote Event.minute; this pins the relationship so they can never disagree.
    for change in DEMO_STORYLINE:
        events = [e for e in demo.events if e.t == change.minute * 60 and e.team_id == change.team_id
                  and e.type in (EventType.SUBSTITUTION, EventType.FORMATION_CHANGE, EventType.TACTIC_CHANGE)]
        assert events and all(e.minute == change.minute + 1 for e in events)


def test_bad_substitution_raises():
    with pytest.raises(ValueError):
        simulate_match(42, storyline=[ScriptedChange(minute=10, team_id="RMU", kind="substitution",
                                                     player_out="RMU-999", player_in="RMU-998")])
