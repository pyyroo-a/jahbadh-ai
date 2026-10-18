"""Midfield control: who owns the middle third.

Three shares of the two-team total, each in [0, 1]:
  ball     successful passes that start in the middle third
  numbers  outfield players in the middle third, summed over tracking seconds
  duels    successful tackles and interceptions in the middle third
The value is the plain mean of whichever components have data.
"""

from jahbadh.analytics.base import check_window, frame_range, is_home, metric_id
from jahbadh.pitch import LENGTH, attack_x, third
from jahbadh.schemas import EventType, Match, Metric

DUELS = (EventType.TACKLE, EventType.INTERCEPTION)


def _share(ours: float, theirs: float) -> float | None:
    total = ours + theirs
    return ours / total if total else None


def midfield_control(match: Match, team_id: str, start: float = 0, end: float = 5400) -> Metric:
    check_window(start, end)
    opp = match.opponent_id(team_id)

    def in_middle(tid: str, x: float) -> bool:
        return third(attack_x(x, is_home(match, tid))) == "middle"

    def middle_events(tid: str, types: tuple[EventType, ...]) -> list:
        return [e for e in match.events_of(team_id=tid, start=start, end=end)
                if e.type in types and e.outcome and in_middle(tid, e.x)]

    passes = {tid: middle_events(tid, (EventType.PASS,)) for tid in (team_id, opp)}
    duels = {tid: middle_events(tid, DUELS) for tid in (team_id, opp)}

    tr = match.tracking
    rows = tr[(tr["t"] >= start) & (tr["t"] < end)]
    keepers = {p.id for tid in (team_id, opp) for p in match.team(tid).players if p.role == "GK"}
    rows = rows[rows["team_id"].isin([team_id, opp]) & ~rows["entity_id"].isin(keepers)]
    home_ax = rows["x"].where(rows["team_id"] == match.meta.home.id, LENGTH - rows["x"])
    mid = rows[(home_ax >= 35) & (home_ax < 70)]
    numbers = mid.groupby("team_id").size()

    data = {
        "ball": _share(len(passes[team_id]), len(passes[opp])),
        "numbers": _share(float(numbers.get(team_id, 0)), float(numbers.get(opp, 0))),
        "duels": _share(len(duels[team_id]), len(duels[opp])),
    }
    present = [v for v in data.values() if v is not None]
    return Metric(
        id=metric_id("midfield_control", team_id, start, end),
        name="midfield_control",
        subject=team_id,
        window=(start, end),
        value=sum(present) / len(present) if present else None,
        unit="share",
        evidence_event_ids=sorted(e.id for tid in (team_id, opp) for e in passes[tid] + duels[tid]),
        evidence_frames=frame_range(start, end),
        data=data,
        note=None if present else "No midfield passes, players or duels in this window.",
    )
