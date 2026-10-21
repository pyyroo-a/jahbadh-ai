from apifakes import demo_match
from jahbadh.api.buildup import goal_buildup
from jahbadh.api.timeline import event_line
from jahbadh.schemas import Event, EventType

DEMO = demo_match()


def ids_for(goal_id: int) -> list[int]:
    return [e.id for e in goal_buildup(DEMO.events, DEMO.event(goal_id))]


# The showcase match (seed 42, demo storyline), measured 21 Oct.

def test_a_won_tackle_starts_the_move():                 # Quill 27'
    assert ids_for(421) == [415, 416, 418, 419, 420]


def test_a_foul_by_the_other_team_stays_and_the_move_goes_on():      # Quill 42', ten steps with a free kick
    steps = goal_buildup(DEMO.events, DEMO.event(601))
    assert [e.id for e in steps] == [586, 588, 589, 591, 593, 594, 595, 597, 599, 600]
    assert steps[6].type == EventType.FOUL and steps[6].team_id == "RMU"


def test_a_shot_straight_after_the_ball_changed_hands_is_only_the_shot():   # Rasmus 47'
    assert ids_for(692) == [691]


def test_the_shot_ends_where_it_was_recorded():
    home, away = goal_buildup(DEMO.events, DEMO.event(601))[-1], goal_buildup(DEMO.events, DEMO.event(692))[-1]
    assert (home.end_x, home.end_y) == (105.0, 34.0) and (away.end_x, away.end_y) == (0.0, 34.0)


def test_only_goal_lines_carry_a_build_up():
    goal = event_line(DEMO, DEMO.event(601))
    assert [s.id for s in goal.buildup] == ids_for(601) and goal.buildup[-1].lines["en"].startswith("Marek Quill")
    assert event_line(DEMO, DEMO.event(600)).buildup is None


# Hand-built moves: NBR scores, RMU defends.

def ev(id: int, type: EventType, team: str = "NBR", outcome: bool | None = True, **kw) -> Event:
    player = "NBR-9" if team == "NBR" else "RMU-4"
    return Event(id=id, t=float(id), period=1, team_id=team, player_id=player, type=type, x=50.0, y=34.0,
                 outcome=outcome, **kw)


def scored(*before: Event, shot: bool = True) -> tuple[list[Event], Event]:
    """The events, a shot (unless shot=False) and the goal, numbered on from the last event given."""
    n = before[-1].id + 1 if before else 1
    events = list(before)
    if shot:
        events.append(ev(n, EventType.SHOT, end_x=105.0, end_y=34.0))
        goal = ev(n + 1, EventType.GOAL, outcome=None, detail={"shot_id": float(n)})
    else:
        goal = ev(n, EventType.GOAL, outcome=None)
    return events + [goal], goal


def ids(events: list[Event], goal: Event) -> list[int]:
    return [e.id for e in goal_buildup(events, goal)]


def test_events_after_the_goal_are_never_used():
    events, goal = scored(ev(1, EventType.PASS))
    events += [ev(4, EventType.PASS), ev(5, EventType.PASS, team="RMU")]       # an outside feed's later events
    assert ids(events, goal) == [1, 2]


def test_an_own_failed_pass_ends_the_move():
    assert ids(*scored(ev(1, EventType.PASS, outcome=False), ev(2, EventType.PASS))) == [2, 3]


def test_an_earlier_own_shot_ends_the_move():
    events, goal = scored(ev(1, EventType.PASS), ev(2, EventType.SHOT, outcome=False, end_x=105.0, end_y=34.0),
                          ev(3, EventType.PASS))
    assert ids(events, goal) == [3, 4]


def test_a_kickoff_ends_the_move_and_is_not_kept():
    assert ids(*scored(ev(1, EventType.KICKOFF, outcome=None), ev(2, EventType.PASS))) == [2, 3]


def test_pressures_cards_and_failed_challenges_are_skipped():
    events, goal = scored(ev(1, EventType.PASS), ev(2, EventType.PRESSURE, team="RMU", outcome=None),
                          ev(3, EventType.TACKLE, team="RMU", outcome=False),
                          ev(4, EventType.CARD, team="RMU", outcome=None), ev(5, EventType.CARRY))
    assert ids(events, goal) == [1, 5, 6]


def test_the_other_teams_won_ball_ends_the_move():
    events, goal = scored(ev(1, EventType.PASS), ev(2, EventType.INTERCEPTION, team="RMU"), ev(3, EventType.PASS))
    assert ids(events, goal) == [3, 4]


def test_a_goal_without_a_shot_ends_with_the_goal_itself():
    assert ids(*scored(ev(1, EventType.PASS), shot=False)) == [1, 2]
