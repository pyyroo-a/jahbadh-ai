"""Player impact: what one player contributed, and how.

The headline value is expected goal involvement (xG + xA), a standard
metric. Everything else lives in `data` so the agents can tell the right
story for any position: a holding midfielder with zero xGI can still top
the ball-wins or progressive-passes rankings.
"""

from jahbadh.analytics.base import is_home, metric_id
from jahbadh.pitch import attack_x, third
from jahbadh.schemas import Event, EventType, Match, Metric

NOT_TOUCHES = {EventType.SUBSTITUTION, EventType.CARD, EventType.KICKOFF, EventType.PERIOD_END, EventType.GOAL,
               EventType.FORMATION_CHANGE, EventType.TACTIC_CHANGE}
ASSIST_WINDOW_S = 15.0


def _keeps_chain(e: Event) -> bool:
    """Opponent events that don't touch the ball: pressure, and tackles that didn't win it."""
    return e.type in NOT_TOUCHES or e.type == EventType.PRESSURE or (e.type == EventType.TACKLE and not e.outcome)
PROGRESSIVE_M = 10.0


def _team_of(match: Match, player_id: str) -> str:
    for team in (match.meta.home, match.meta.away):
        if any(p.id == player_id for p in team.players):
            return team.id
    raise KeyError(player_id)


def _assister(match: Match, shot: Event) -> Event | None:
    """The team's most recent successful pass to the shooter, within 15 s, with no opponent event in between."""
    idx = next(i for i, e in enumerate(match.events) if e.id == shot.id)
    for e in reversed(match.events[:idx]):
        if shot.t - e.t > ASSIST_WINDOW_S:
            return None
        if e.team_id != shot.team_id and not _keeps_chain(e):
            return None  # the opponent got involved
        if e.team_id == shot.team_id and e.type == EventType.PASS and e.outcome:
            return e if e.related_player_id == shot.player_id else None
    return None


def player_impact(match: Match, player_id: str, start: float = 0, end: float = 5400) -> Metric:
    team_id = _team_of(match, player_id)
    home = is_home(match, team_id)
    window_events = match.events_of(team_id=team_id, start=start, end=end)
    team_touches = [e for e in window_events if e.player_id and e.type not in NOT_TOUCHES]
    mine = [e for e in window_events if e.player_id == player_id]
    touches = [e for e in mine if e.type not in NOT_TOUCHES]

    tr = match.tracking
    seconds = int(((tr["entity_id"] == player_id) & (tr["t"] >= start) & (tr["t"] < end)).sum())
    common = dict(id=metric_id("player_impact", player_id, start, end), name="player_impact", subject=player_id,
                  window=(start, end), unit="xGI", evidence_frames=(int(start), int(end) - 1))
    if seconds == 0:
        return Metric(**common, value=None, data={"minutes": 0.0},
                      note="Player was not on the pitch in this window.")

    def of(*types: EventType, ok: bool | None = None) -> list[Event]:
        return [e for e in mine if e.type in types and (ok is None or bool(e.outcome) == ok)]

    passes, done = of(EventType.PASS), of(EventType.PASS, ok=True)
    shots, goals = of(EventType.SHOT), of(EventType.GOAL)
    scored = [s for s in shots if s.outcome]  # goals counted from scored shots, the same way assists are
    progressive = [e for e in done if e.end_x is not None
                   and attack_x(e.end_x, home) - attack_x(e.x, home) >= PROGRESSIVE_M]
    entries = [e for e in of(EventType.PASS, EventType.CARRY, ok=True) if e.end_x is not None
               and third(attack_x(e.x, home)) != "final" and third(attack_x(e.end_x, home)) == "final"]
    ball_wins = of(EventType.TACKLE, EventType.INTERCEPTION, ok=True)
    pressures = of(EventType.PRESSURE)
    assisted = [s for s in match.events_of(EventType.SHOT, team_id=team_id, start=start, end=end)
                if s.player_id != player_id and (a := _assister(match, s)) is not None and a.player_id == player_id]

    xg = sum(s.xg or 0.0 for s in shots)
    xa = sum(s.xg or 0.0 for s in assisted)
    data = {
        "touches": len(touches),
        "involvement": len(touches) / len(team_touches) if team_touches else 0.0,
        "passes": len(passes),
        "pass_completion": len(done) / len(passes) if passes else None,
        "progressive_passes": len(progressive),
        "final_third_entries": len(entries),
        "shots": len(shots),
        "xg": xg,
        "goals": len(scored),
        "xa": xa,
        "assists": sum(1 for s in assisted if s.outcome),
        "ball_wins": len(ball_wins),
        "pressures": len(pressures),
        "minutes": seconds / 60,
        "heatmap_id": metric_id("heatmap", player_id, start, end),
    }
    evidence = {e.id for e in touches + goals + ball_wins + pressures + assisted}
    return Metric(**common, value=xg + xa, data=data, evidence_event_ids=sorted(evidence))


def player_rankings(match: Match, team_id: str | None = None, start: float = 0, end: float = 5400,
                    by: str = "value", n: int = 3) -> list[Metric]:
    tr = match.tracking
    rows = tr[(tr["t"] >= start) & (tr["t"] < end) & (tr["entity_id"] != "BALL")]
    if team_id is not None:
        match.team(team_id)  # unknown team -> KeyError, not an empty ranking
        rows = rows[rows["team_id"] == team_id]
    impacts = [player_impact(match, pid, start, end) for pid in sorted(rows["entity_id"].unique())]

    def key(m: Metric) -> float:
        v = m.value if by == "value" else m.data.get(by)
        return float("-inf") if v is None else float(v)

    return sorted(impacts, key=lambda m: (-key(m), m.subject))[:n]
