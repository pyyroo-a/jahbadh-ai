"""Rolling momentum: which team has been more threatening recently."""

from jahbadh.analytics.base import is_home, metric_id
from jahbadh.pitch import attack_x, third
from jahbadh.schemas import EventType, Match, Metric

FINAL_THIRD_PASS_THREAT = 0.02  # a successful final-third pass counts as 0.02 xG of threat


def momentum(match: Match, at_t: float, window_s: float = 600) -> Metric:
    """Home team's share of threat (shot xG + 0.02 per successful final-third pass) in the window ending at at_t."""
    if not (0 < at_t <= 5400 and window_s > 0):
        raise ValueError(f"window ending at {at_t} with length {window_s} must end inside the match and be positive")
    start = max(0.0, at_t - window_s)
    threat, evidence = {}, []
    for tid in (match.meta.home.id, match.meta.away.id):
        shots = match.events_of(EventType.SHOT, team_id=tid, start=start, end=at_t)
        passes = [e for e in match.events_of(EventType.PASS, team_id=tid, start=start, end=at_t)
                  if e.outcome and third(attack_x(e.x, is_home(match, tid))) == "final"]
        threat[tid] = sum(s.xg or 0.0 for s in shots) + FINAL_THIRD_PASS_THREAT * len(passes)
        evidence += [e.id for e in shots + passes]
    home, away = threat[match.meta.home.id], threat[match.meta.away.id]
    total = home + away
    return Metric(
        id=metric_id("momentum", "MATCH", start, at_t),
        name="momentum",
        subject="MATCH",
        window=(start, at_t),
        value=home / total if total else None,
        unit="home_share",
        evidence_event_ids=sorted(evidence),
        data={"home": home, "away": away},
        note=None if total else "Neither team created any threat in this window.",
    )


def momentum_series(match: Match, step_s: float = 60, window_s: float = 600) -> list[Metric]:
    n = int(5400 // step_s)
    return [momentum(match, at_t=step_s * (i + 1), window_s=window_s) for i in range(n)]
