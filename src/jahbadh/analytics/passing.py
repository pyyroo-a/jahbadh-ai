"""Pass quality: how far, how accurate, and how hard the passes were. Also pass speed (synthetic).

Difficulty is 1 minus the simulator's own chance that the pass would be completed (each PASS keeps it as
detail["p_success"], 0.3 to 0.97). It's the simulator's model of a hard pass (longer, under pressure, into
the final third), not a real-world expected-pass model, so it reads as a synthetic rating.
"""

from math import hypot

from jahbadh.analytics.base import check_window, metric_id
from jahbadh.schemas import EventType, Match, Metric


def _team_of(match: Match, subject: str) -> str | None:
    """None when the subject is a team, else the player's team. Raises KeyError for anything else."""
    if subject in (match.meta.home.id, match.meta.away.id):
        return None
    for team in (match.meta.home, match.meta.away):
        if any(p.id == subject for p in team.players):
            return team.id
    raise KeyError(subject)


def pass_quality(match: Match, subject: str, start: float = 0, end: float = 5400) -> Metric:
    check_window(start, end)
    player_team = _team_of(match, subject)
    team = player_team or subject
    passes = [e for e in match.events_of(EventType.PASS, team_id=team, start=start, end=end)
              if player_team is None or e.player_id == subject]
    completed = [e for e in passes if e.outcome]
    lengths = [hypot(e.end_x - e.x, e.end_y - e.y) for e in passes if e.end_x is not None and e.end_y is not None]
    rated = [(e, 1 - float(e.detail["p_success"])) for e in passes if "p_success" in e.detail]
    hardest = max(((e, d) for e, d in rated if e.outcome), key=lambda ed: (ed[1], -ed[0].id), default=None)
    mean_difficulty = sum(d for _, d in rated) / len(rated) if rated else None
    data = {"attempted": len(passes), "completed": len(completed),
            "accuracy": len(completed) / len(passes) if passes else None,
            "mean_length_m": sum(lengths) / len(lengths) if lengths else None,
            "mean_difficulty": mean_difficulty,
            "hardest_completed": None if hardest is None else {"event_id": hardest[0].id, "difficulty": hardest[1]}}
    note = None
    if not passes:
        note = "No passes in this window."
    elif not rated:
        note = "These passes carry no success odds (the match was saved before they were recorded)."
    return Metric(id=metric_id("pass_quality", subject, start, end), name="pass_quality", subject=subject,
                  window=(start, end), value=mean_difficulty, unit="difficulty",
                  evidence_event_ids=[e.id for e in passes], data=data, note=note)


def pass_speed(match: Match, subject: str, start: float = 0, end: float = 5400) -> Metric:
    """Mean synthetic ball speed of a team's or player's passes (detail["speed_kmh"], from the simulator)."""
    check_window(start, end)
    player_team = _team_of(match, subject)
    team = player_team or subject
    passes = [e for e in match.events_of(EventType.PASS, team_id=team, start=start, end=end)
              if (player_team is None or e.player_id == subject) and "speed_kmh" in e.detail]
    speeds = [float(e.detail["speed_kmh"]) for e in passes]
    return Metric(id=metric_id("pass_speed", subject, start, end), name="pass_speed", subject=subject,
                  window=(start, end), value=round(sum(speeds) / len(speeds), 1) if speeds else None, unit="km/h",
                  evidence_event_ids=[e.id for e in passes],
                  data={"passes": len(passes), "max": max(speeds, default=None), "synthetic": True},
                  note=None if passes else "No passes with a simulated speed in this window.")
