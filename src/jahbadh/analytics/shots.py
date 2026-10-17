"""Shot-based metrics: total xG and the cumulative xG timeline."""

from jahbadh.analytics.base import is_home, metric_id
from jahbadh.schemas import EventType, Match, Metric


def xg_total(match: Match, team_id: str, start: float = 0, end: float = 5400) -> Metric:
    is_home(match, team_id)  # unknown team -> KeyError, never a confident 0
    shots = match.events_of(EventType.SHOT, team_id=team_id, start=start, end=end)
    return Metric(
        id=metric_id("xg_total", team_id, start, end),
        name="xg_total",
        subject=team_id,
        window=(start, end),
        value=sum(s.xg or 0.0 for s in shots),
        unit="xG",
        evidence_event_ids=[s.id for s in shots],
    )


def xg_timeline(match: Match, team_id: str) -> Metric:
    is_home(match, team_id)
    shots = match.events_of(EventType.SHOT, team_id=team_id)
    points, cum = [], 0.0
    for s in shots:
        cum += s.xg or 0.0
        points.append([s.t, cum])
    return Metric(
        id=metric_id("xg_timeline", team_id, 0, 5400),
        name="xg_timeline",
        subject=team_id,
        window=(0, 5400),
        value=cum,
        unit="xG",
        evidence_event_ids=[s.id for s in shots],
        data={"points": points},
    )
