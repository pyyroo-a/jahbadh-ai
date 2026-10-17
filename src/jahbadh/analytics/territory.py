"""Territory and pressing: field tilt and PPDA."""

from jahbadh.analytics.base import is_home, metric_id
from jahbadh.pitch import attack_x, third
from jahbadh.schemas import EventType, Match, Metric

PPDA_ZONE_AX = 63.0  # opponent's defensive 60% of the pitch, in the opponent's attacking coordinates
DEFENSIVE_ACTIONS = (EventType.TACKLE, EventType.INTERCEPTION, EventType.FOUL)


def field_tilt(match: Match, team_id: str, start: float = 0, end: float = 5400) -> Metric:
    """Team's share of all successful passes that start in the passer's final third."""
    final_third = {
        tid: [e for e in match.events_of(EventType.PASS, team_id=tid, start=start, end=end)
              if e.outcome and third(attack_x(e.x, is_home(match, tid))) == "final"]
        for tid in (team_id, match.opponent_id(team_id))
    }
    ours, total = final_third[team_id], sum(len(v) for v in final_third.values())
    return Metric(
        id=metric_id("field_tilt", team_id, start, end),
        name="field_tilt",
        subject=team_id,
        window=(start, end),
        value=len(ours) / total if total else None,
        unit="share",
        evidence_event_ids=[e.id for e in ours],
        note=None if total else "No successful final-third passes by either team in this window.",
    )


def ppda(match: Match, defending_team_id: str, start: float = 0, end: float = 5400) -> Metric:
    """Opponent passes in its defensive 60% per defensive action there. Lower means a more intense press."""
    opp = match.opponent_id(defending_team_id)
    opp_home = is_home(match, opp)

    def in_zone(x: float) -> bool:
        return attack_x(x, opp_home) < PPDA_ZONE_AX

    passes = [e for e in match.events_of(EventType.PASS, team_id=opp, start=start, end=end) if in_zone(e.x)]
    actions = [e for e in match.events_of(team_id=defending_team_id, start=start, end=end)
               if e.type in DEFENSIVE_ACTIONS and in_zone(e.x)]
    return Metric(
        id=metric_id("ppda", defending_team_id, start, end),
        name="ppda",
        subject=defending_team_id,
        window=(start, end),
        value=len(passes) / len(actions) if actions else None,
        unit="passes/def_action",
        evidence_event_ids=[e.id for e in actions],
        data={"opponent_passes": len(passes), "defensive_actions": len(actions)},
        note=None if actions else "No defensive actions in the pressing zone in this window.",
    )
