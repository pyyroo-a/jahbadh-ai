"""Which moments the desk talks about. Deterministic, so the desk never misses a goal, and the LLM only
runs about 20 to 30 times a match instead of on every pass.

Thresholds were measured on seeds 42, 1, 2, 3 and 7 before they were fixed here: goals 2 to 8, unscored
shots with xG >= 0.3 at 0 to 1, cards 1 to 5, swings 3 to 5 per match.
"""

from collections import defaultdict

from jahbadh.agents.contracts import Moment, MomentKind
from jahbadh.analytics import momentum_series
from jahbadh.schemas import Event, EventType, Match

BIG_CHANCE_XG = 0.3
SWING_DELTA = 0.4           # change in the home team's share of threat
SWING_LOOKBACK_MIN = 10
SWING_COOLDOWN_MIN = 10
CHECK_IN_MINUTES = (10, 20, 30, 40, 50, 60, 70, 80)
CHECK_IN_CLEARANCE_S = 120
STORYLINE = (EventType.SUBSTITUTION, EventType.FORMATION_CHANGE, EventType.TACTIC_CHANGE)


def _minute(t: float) -> int:
    return min(90, int(t // 60) + 1)


def detect_moments(match: Match) -> list[Moment]:
    names = {p.id: p.name for team in (match.meta.home, match.meta.away) for p in team.players}
    team_name = {t.id: t.name for t in (match.meta.home, match.meta.away)}
    moments: list[tuple[MomentKind, float, str | None, list[int], str]] = []
    storyline: dict[tuple[str, float], list[Event]] = defaultdict(list)

    for e in match.events:
        m = _minute(e.t)
        if e.type == EventType.GOAL:
            shot_id = int(e.detail["shot_id"]) if "shot_id" in e.detail else None
            ids = [shot_id, e.id] if shot_id is not None else [e.id]
            moments.append(("goal", e.t, e.team_id, ids,
                            f"{m}' Goal for {team_name[e.team_id]} ({names.get(e.player_id, 'unknown')})"))
        elif e.type == EventType.SHOT and not e.outcome and (e.xg or 0) >= BIG_CHANCE_XG:
            moments.append(("big_chance", e.t, e.team_id, [e.id],
                            f"{m}' Big chance for {team_name[e.team_id]} ({names.get(e.player_id, 'unknown')})"))
        elif e.type == EventType.CARD:
            moments.append(("card", e.t, e.team_id, [e.id],
                            f"{m}' Card for {names.get(e.player_id, 'unknown')} ({team_name[e.team_id]})"))
        elif e.type in STORYLINE:
            storyline[(e.team_id, e.t)].append(e)

    for (team_id, t), events in storyline.items():
        types = {e.type for e in events}
        name, m = team_name[team_id], _minute(t)
        if EventType.FORMATION_CHANGE in types:
            to = next(e.detail.get("to") for e in events if e.type == EventType.FORMATION_CHANGE)
            kind, label = "formation_change", f"{m}' {name} switch to {to}"
        elif EventType.TACTIC_CHANGE in types:
            kind, label = "tactic_change", f"{m}' {name} change their press"
        else:
            kind, label = "substitution", f"{m}' Substitution for {name}"
        moments.append((kind, t, team_id, [e.id for e in events], label))

    series = [s.value for s in momentum_series(match)]
    last = -SWING_COOLDOWN_MIN
    for i in range(SWING_LOOKBACK_MIN, len(series)):
        before, now = series[i - SWING_LOOKBACK_MIN], series[i]
        if before is None or now is None or i - last < SWING_COOLDOWN_MIN:
            continue
        delta = now - before
        if abs(delta) >= SWING_DELTA:
            team_id = match.meta.home.id if delta > 0 else match.meta.away.id
            t = (i + 1) * 60.0
            moments.append(("momentum_swing", t, team_id, [], f"{_minute(t)}' Momentum swings to {team_name[team_id]}"))
            last = i

    for m in CHECK_IN_MINUTES:
        t = m * 60.0
        if all(abs(t - other[1]) > CHECK_IN_CLEARANCE_S for other in moments if other[0] != "check_in"):
            moments.append(("check_in", t, None, [], f"{_minute(t)}' Tactical check-in"))

    moments.append(("full_time", 5400.0, None, [], "Full time"))
    moments.sort(key=lambda mo: (mo[1], mo[0] == "full_time"))

    out, seen = [], defaultdict(int)
    for kind, t, team_id, ids, label in moments:
        base = f"{kind}-{int(t)}"
        seen[base] += 1
        mid = base if seen[base] == 1 else f"{base}-{seen[base]}"
        out.append(Moment(id=mid, kind=kind, t=t, team_id=team_id, event_ids=ids, label=label))
    return out
