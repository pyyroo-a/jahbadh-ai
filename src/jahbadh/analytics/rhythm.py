"""Game rhythm: is the match controlled, or is the ball changing hands all the time?

An on-ball event is a pass, carry, shot, interception or a tackle that won the ball. Possession changes
when two consecutive on-ball events belong to different teams. The rhythm is changes per minute, alongside
the tempo (passes per minute) and how many passes a possession lasts.

The labels are fixed against measured simulator output, never chosen to fit a moment: over seeds 1 to 10
(no storyline), 90 ten-minute windows ranged 1.40 to 4.00 changes per minute, with the 25th percentile at
2.12 and the 75th at 2.80 (measured 18 Oct). Below the first is "controlled", above the second "chaotic".
"""

from typing import Literal

from jahbadh.analytics.base import check_window, metric_id
from jahbadh.schemas import Event, EventType, Match, Metric

CONTROL_MAX = 2.12
CHAOS_MIN = 2.80
ON_BALL = (EventType.PASS, EventType.CARRY, EventType.SHOT, EventType.INTERCEPTION)

Label = Literal["controlled", "balanced", "chaotic"]


def label_for(changes_per_minute: float) -> Label:
    if changes_per_minute < CONTROL_MAX:
        return "controlled"
    if changes_per_minute > CHAOS_MIN:
        return "chaotic"
    return "balanced"


def _on_ball(e: Event) -> bool:
    return e.type in ON_BALL or (e.type == EventType.TACKLE and bool(e.outcome))


def game_rhythm(match: Match, start: float = 0, end: float = 5400) -> Metric:
    check_window(start, end)
    events = [e for e in match.events_of(start=start, end=end) if _on_ball(e)]
    changed = [b for a, b in zip(events, events[1:]) if a.team_id != b.team_id]
    minutes = (end - start) / 60
    passes = sum(e.type == EventType.PASS for e in events)
    possessions = len(changed) + 1 if events else 0
    rate = len(changed) / minutes
    return Metric(id=metric_id("game_rhythm", "MATCH", start, end), name="game_rhythm", subject="MATCH",
                  window=(start, end), value=rate, unit="changes/min", evidence_event_ids=[e.id for e in changed],
                  data={"changes": len(changed), "minutes": minutes, "passes_per_minute": passes / minutes,
                        "passes_per_possession": passes / possessions if possessions else None,
                        "label": label_for(rate)})


def rhythm_series(match: Match, step_s: float = 60, window_s: float = 600) -> list[Metric]:
    """The rhythm over the window ending at every step, like momentum_series."""
    return [game_rhythm(match, max(0.0, step_s * (i + 1) - window_s), step_s * (i + 1))
            for i in range(int(5400 // step_s))]
