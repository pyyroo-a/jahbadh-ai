"""A goal's build-up: the move from when the scoring team last won the ball to the shot. No model, no cost.

Only events before the goal are read, so live and an outside feed (which only know the past) get the same move
as replay. Walking back from the shot, the scoring team's completed passes and carries are kept; their own won
tackle or interception is kept and starts the move; a foul by the other team is kept (the free kick) and the
move goes on. The walk stops at the other team's pass, carry, shot or won challenge, at the scoring team's own
failed pass or carry, earlier shot or foul, and at a kick-off, half time or an earlier goal. Everything else
(pressures, failed challenges, cards, changes) is skipped. Nothing is added or moved: the shot keeps the end
point it was recorded with.
"""

from jahbadh.schemas import Event, EventType

ON_THE_BALL = (EventType.PASS, EventType.CARRY)
CHALLENGES = (EventType.TACKLE, EventType.INTERCEPTION)
BREAKS = (EventType.KICKOFF, EventType.PERIOD_END, EventType.GOAL)


def _anchor(before: list[Event], goal: Event) -> int | None:
    """Where the shot sits in `before`, or None when the goal names no shot."""
    if "shot_id" not in goal.detail:
        return None
    shot_id = int(goal.detail["shot_id"])
    return next((i for i in range(len(before) - 1, -1, -1) if before[i].id == shot_id), None)


def goal_buildup(events: list[Event], goal: Event) -> list[Event]:
    """The move's events in match order, the shot last (or the goal itself when it has no shot)."""
    at = next(i for i in range(len(events) - 1, -1, -1) if events[i].id == goal.id)
    before = events[:at]
    shot = _anchor(before, goal)
    anchor, start = (before[shot], shot) if shot is not None else (goal, at)
    team, kept = goal.team_id, [anchor]
    for e in reversed(before[:start]):
        if e.type in BREAKS:
            break
        if e.team_id != team:
            if e.type in (*ON_THE_BALL, EventType.SHOT) or (e.type in CHALLENGES and e.outcome):
                break
            if e.type == EventType.FOUL:
                kept.append(e)
            continue
        if e.type in (EventType.SHOT, EventType.FOUL) or (e.type in ON_THE_BALL and not e.outcome):
            break
        if e.type in CHALLENGES and e.outcome:
            kept.append(e)
            break
        if e.type in ON_THE_BALL:
            kept.append(e)
    return kept[::-1]
