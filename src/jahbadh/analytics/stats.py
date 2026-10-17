"""Match stats, shot maps and attacking sides: the numbers every match centre shows.

All computed from data the simulator already records (shot positions, fouls, cards, passes). Blocked,
saved and off-target shots and corners are not simulated, so they are not here.
"""

from jahbadh.analytics.base import check_window, is_home, metric_id
from jahbadh.pitch import LENGTH, WIDTH, attack_x, lane, third
from jahbadh.schemas import EventType, Match, Metric

BOX_DEPTH = 16.5
BOX_HALF_WIDTH = 20.16
ENTRY_TYPES = (EventType.PASS, EventType.CARRY)


def in_box(ax: float, y: float) -> bool:
    """Inside the penalty area the team attacks (ax from attack_x)."""
    return ax >= LENGTH - BOX_DEPTH and abs(y - WIDTH / 2) <= BOX_HALF_WIDTH


def match_stats(match: Match, team_id: str, start: float = 0, end: float = 5400) -> Metric:
    check_window(start, end)
    home = is_home(match, team_id)
    events = match.events_of(team_id=team_id, start=start, end=end)
    shots = [e for e in events if e.type == EventType.SHOT]
    inside = [s for s in shots if in_box(attack_x(s.x, home), s.y)]
    fouls = [e for e in events if e.type == EventType.FOUL]
    cards = [e for e in events if e.type == EventType.CARD]
    passes = [e for e in events if e.type == EventType.PASS]
    data = {
        "shots": len(shots),
        "shots_inside_box": len(inside),
        "shots_outside_box": len(shots) - len(inside),
        "goals": sum(1 for s in shots if s.outcome),
        "xg": sum(s.xg or 0.0 for s in shots),
        "fouls": len(fouls),
        "yellow_cards": len(cards),
        "passes": len(passes),
        "pass_completion": sum(1 for e in passes if e.outcome) / len(passes) if passes else None,
    }
    return Metric(id=metric_id("match_stats", team_id, start, end), name="match_stats", subject=team_id,
                  window=(start, end), value=float(len(shots)), unit="shots", data=data,
                  evidence_event_ids=sorted(e.id for e in shots + fouls + cards))


def shot_map(match: Match, team_id: str, start: float = 0, end: float = 5400) -> Metric:
    """Every shot in the team's attacking frame (x toward 105, high y = left), keyed by event id."""
    check_window(start, end)
    home = is_home(match, team_id)
    shots = match.events_of(EventType.SHOT, team_id=team_id, start=start, end=end)
    data = {}
    for s in shots:
        ax, ay = attack_x(s.x, home), s.y if home else WIDTH - s.y
        data[str(s.id)] = {"minute": s.minute, "player_id": s.player_id, "x": ax, "y": ay, "xg": s.xg or 0.0,
                           "goal": bool(s.outcome), "inside_box": in_box(ax, ay)}
    return Metric(id=metric_id("shot_map", team_id, start, end), name="shot_map", subject=team_id,
                  window=(start, end), value=float(len(shots)), unit="shots", data={"shots": data},
                  evidence_event_ids=[s.id for s in shots])


def attacking_sides(match: Match, team_id: str, start: float = 0, end: float = 5400) -> Metric:
    """Where a team's attacks go: successful passes and carries that end in its final third, by lane."""
    check_window(start, end)
    home = is_home(match, team_id)
    entries = [e for e in match.events_of(team_id=team_id, start=start, end=end)
               if e.type in ENTRY_TYPES and e.outcome and e.end_x is not None and e.end_y is not None
               and third(attack_x(e.end_x, home)) == "final"]
    common = dict(id=metric_id("attacking_sides", team_id, start, end), name="attacking_sides", subject=team_id,
                  window=(start, end), unit="share", evidence_event_ids=sorted(e.id for e in entries))
    if not entries:
        return Metric(**common, value=None, data={"entries": 0},
                      note="No successful passes or carries into the final third in this window.")
    lanes = [lane(e.end_y, home) for e in entries]
    shares = {side: lanes.count(side) / len(lanes) for side in ("left", "centre", "right")}
    side = min(shares, key=lambda s: (-shares[s], s))              # ties go alphabetically
    return Metric(**common, value=shares[side], data=shares | {"entries": len(entries), "side": side})
