import pytest

from fakes import demo_match, make_match, shot_by
from jahbadh.agents.moments import detect_moments
from jahbadh.schemas import Event, EventType
from jahbadh.simulator import simulate_match


def kinds(ms):
    return [(m.kind, m.minute) for m in ms]


def test_goal_and_big_chance_rules():
    evs = [shot_by(1, "NBR", "NBR-9", 0.5, t=100, goal=True),
           Event(id=2, t=101, period=1, team_id="NBR", player_id="NBR-9", type=EventType.GOAL, x=105, y=34,
                 detail={"shot_id": 1.0}),
           shot_by(3, "RMU", "RMU-9", 0.29, t=1000), shot_by(4, "RMU", "RMU-9", 0.3, t=1300)]
    ms = detect_moments(make_match(evs))
    goal = next(m for m in ms if m.kind == "goal")
    assert goal.event_ids == [1, 2] and goal.team_id == "NBR" and goal.minute == 2
    assert [m.event_ids for m in ms if m.kind == "big_chance"] == [[4]]


def test_card_is_a_moment():
    card = Event(id=1, t=300, period=1, team_id="RMU", player_id="RMU-4", type=EventType.CARD, x=50, y=34,
                 detail={"colour": "yellow"})
    assert [(m.kind, m.event_ids, m.team_id) for m in detect_moments(make_match([card])) if m.kind == "card"] == \
        [("card", [1], "RMU")]


def test_storyline_events_at_the_same_second_are_one_moment():
    ms = detect_moments(demo_match())
    switch = [m for m in ms if m.kind == "formation_change"]
    assert len(switch) == 1 and switch[0].minute == 61 and len(switch[0].event_ids) == 2
    assert not any(m.kind == "substitution" and m.t == switch[0].t for m in ms)
    assert any(m.kind == "tactic_change" and m.minute == 71 for m in ms)


def test_check_ins_make_room_for_real_moments():
    evs = [shot_by(1, "NBR", "NBR-9", 0.4, t=590)]    # big chance 10 s before the 10' check-in
    ks = kinds(detect_moments(make_match(evs)))
    assert ("big_chance", 10) in ks and ("check_in", 11) not in ks and ("check_in", 21) in ks


def test_momentum_swing():
    evs = [shot_by(i, "NBR", "NBR-9", 0.2, t=60 * i) for i in range(1, 10)] + \
          [shot_by(20 + i, "RMU", "RMU-9", 0.2, t=600 + 60 * i) for i in range(1, 10)]
    swings = [m for m in detect_moments(make_match(evs)) if m.kind == "momentum_swing"]
    # worked by hand: at t=900 the home share is 1.0/1.8 = 0.556 against 1.0 at t=300, a drop of 0.444
    assert swings and swings[0].team_id == "RMU" and swings[0].t == 900


def test_full_time_is_always_last():
    ms = detect_moments(make_match([]))
    assert ms[-1].kind == "full_time" and ms[-1].t == 5400 and ms[-1].minute == 90


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_moment_count_is_in_the_spec_range(seed):
    assert 12 <= len(detect_moments(simulate_match(seed))) <= 35


def test_ids_are_unique_and_sorted():
    ms = detect_moments(demo_match())
    assert len({m.id for m in ms}) == len(ms) and [m.t for m in ms] == sorted(m.t for m in ms)
