"""The evidence a moment's claims can stand on, and compact text views of it for the agents.

Every metric a tool computes goes into the moment's EvidenceStore. Summaries flatten each metric into
`fields` (dotted paths to citable numbers), and the Referee resolves the same paths against the full
metric, so what a writer sees and what gets checked always line up.
"""

from jahbadh.agents.contracts import Moment
from jahbadh.pitch import LENGTH, WIDTH, attack_x, third
from jahbadh.schemas import Event, EventType, Match, Metric

PASS_LIKE = (EventType.PASS, EventType.CARRY)
WON_OR_LOST = (EventType.TACKLE, EventType.INTERCEPTION)


class EvidenceStore:
    def __init__(self, match: Match):
        self.match = match
        self._metrics: dict[str, Metric] = {}

    def add(self, metric: Metric) -> Metric:
        self._metrics[metric.id] = metric
        return metric

    def get(self, metric_id: str) -> Metric:
        return self._metrics[metric_id]

    def __contains__(self, metric_id: object) -> bool:
        return metric_id in self._metrics

    def metrics(self) -> list[Metric]:
        return list(self._metrics.values())


def clock(t: float) -> str:
    return f"{int(t // 60):02d}:{int(t % 60):02d}"


def broadcast_window(window: tuple[float, float]) -> str:
    """The broadcast minutes of a window's first and last second, e.g. (3600, 4500) is 61'-75'."""
    start, end = window
    return f"{int(start // 60) + 1}'-{int((end - 1) // 60) + 1}'"


def resolve(metric: Metric, field: str) -> float | str | None:
    """A citable value: "value", or a dotted path into data such as "before.value" or "by_zone.final-left"."""
    if field == "value":
        return metric.value
    node: object = metric.data
    for part in field.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"{metric.id} has no field {field}")
        node = node[part]
    if isinstance(node, (dict, list)):
        raise KeyError(f"{metric.id} field {field} is not a single value")
    return node


SHARE_UNITS = {"share", "home_share", "share_of_seconds"}
SHARE_DATA_KEYS = {"pass_completion", "involvement", "ball", "numbers", "duels", "left", "centre", "right", "by_zone"}


def is_share(metric: Metric, field: str) -> bool:
    """Can this field honestly be written as a percentage? Only fractions of a whole are."""
    if field in ("value", "before.value", "after.value"):
        return metric.unit in SHARE_UNITS
    return field.split(".")[0] in SHARE_DATA_KEYS


def _round(v: object) -> object:
    return round(v, 3) if isinstance(v, float) else v


def _is_scalar(v: object) -> bool:
    return v is None or isinstance(v, (int, float, str))


def _fields(metric: Metric) -> dict:
    fields = {"value": _round(metric.value)}
    change = metric.name.endswith("_change")
    for key, v in metric.data.items():
        if _is_scalar(v):
            fields[key] = _round(v)
        elif isinstance(v, dict):
            subkeys = ["value"] if change and key in ("before", "after") else list(v)
            for sub in subkeys:
                if _is_scalar(v.get(sub)):
                    fields[f"{key}.{sub}"] = _round(v[sub])
    return fields


def _hot_zones(metric: Metric) -> list[list]:
    grid, (nx, ny) = metric.data["grid"], metric.data["cells"]
    shares: dict[str, float] = {}
    for i in range(nx):
        for j in range(ny):
            x, y = (i + 0.5) * LENGTH / nx, (j + 0.5) * WIDTH / ny
            lane = "left" if y >= WIDTH * 2 / 3 else "right" if y < WIDTH / 3 else "centre"
            zone = f"{third(x)}-{lane}"
            shares[zone] = shares.get(zone, 0.0) + grid[i][j]
    top = sorted(shares.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    return [[zone, round(share, 2)] for zone, share in top if share > 0]


def _extra(metric: Metric) -> dict | None:
    if metric.name == "heatmap" and "grid" in metric.data:
        return {"hot_zones": _hot_zones(metric)}
    if metric.name == "shot_map":
        return {"shots": [[int(i), s["minute"], s["player_id"], round(s["xg"], 2), s["goal"], s["inside_box"]]
                          for i, s in metric.data["shots"].items()]}
    if metric.name == "pass_network":
        return {"top_edges": metric.data.get("edges", [])[:5]}
    if metric.name == "average_positions":
        return {"players": {pid: [round(x, 1), round(y, 1)] for pid, (x, y) in metric.data.get("players", {}).items()}}
    return None


def summarize(metric: Metric) -> dict:
    summary = {"id": metric.id, "name": metric.name, "subject": metric.subject,
               "window": broadcast_window(metric.window), "unit": metric.unit, "note": metric.note,
               "fields": _fields(metric)}
    extra = _extra(metric)
    if extra is not None:
        summary["extra"] = extra
    return summary


def _names(match: Match) -> dict[str, str]:
    return {p.id: p.name for team in (match.meta.home, match.meta.away) for p in team.players}


def describe_event(match: Match, e: Event) -> str:
    """One line per event, e.g. "#975 61' RMU FORMATION_CHANGE 4-3-3 -> 3-4-3"."""
    names = _names(match)
    parts = [f"#{e.id} {e.minute}' {e.team_id} {e.type}"]
    if e.player_id and e.type != EventType.SUBSTITUTION:
        parts.append(names.get(e.player_id, e.player_id))
    home = e.team_id == match.meta.home.id
    if e.type in PASS_LIKE:
        if e.related_player_id:
            parts.append(f"to {names.get(e.related_player_id, e.related_player_id)}")
        parts.append("complete" if e.outcome else "incomplete")
    elif e.type == EventType.SHOT:
        parts.append(f"xG {e.xg or 0:.2f}, {'scored' if e.outcome else 'no goal'}")
    elif e.type in WON_OR_LOST:
        parts.append("won the ball" if e.outcome else "did not win the ball")
    elif e.type == EventType.FORMATION_CHANGE:
        parts.append(f"{e.detail.get('from')} -> {e.detail.get('to')}")
    elif e.type == EventType.SUBSTITUTION:
        parts.append(f"off: {names.get(e.player_id, e.player_id)}, on: {names.get(e.related_player_id, e.related_player_id)}")
    elif e.type == EventType.TACTIC_CHANGE:
        parts.append(f"press height {e.detail.get('press_height_from')} -> {e.detail.get('press_height_to')}")
    elif e.type == EventType.CARD:
        parts.append(f"{e.detail.get('colour', 'yellow')} card")
    if e.type not in (EventType.FORMATION_CHANGE, EventType.TACTIC_CHANGE, EventType.SUBSTITUTION,
                      EventType.KICKOFF, EventType.PERIOD_END):
        parts.append(f"({third(attack_x(e.x, home))} third)")
    return " ".join(parts)


def score_at(match: Match, t: float) -> dict[str, int]:
    score = {match.meta.home.id: 0, match.meta.away.id: 0}
    for e in match.events:
        if e.type == EventType.GOAL and e.t < t:
            score[e.team_id] += 1
    return score


def formation_at(match: Match, team_id: str, t: float) -> str:
    formation = match.team(team_id).formation
    for e in match.events:
        if e.type == EventType.FORMATION_CHANGE and e.team_id == team_id and e.t < t:
            formation = str(e.detail.get("to", formation))
    return formation


def moment_context(match: Match, moment: Moment) -> str:
    """Plain-text facts every agent gets about a moment: teams, score, trigger events and players."""
    home, away, h = match.meta.home, match.meta.away, moment.horizon
    score = score_at(match, h)
    lines = [
        f"Match: {home.name} ({home.id}, home) vs {away.name} ({away.id}, away).",
        f"Moment: {moment.label}, at {moment.minute}' (match clock {clock(moment.t)}).",
        f"You only know what happened before match clock {clock(h)}.",
        f"Score then: {home.name} {score[home.id]}, {away.name} {score[away.id]}.",
        f"Formations then: {home.id} {formation_at(match, home.id, h)}, {away.id} {formation_at(match, away.id, h)}.",
    ]
    if moment.event_ids:
        lines.append("Trigger events:")
        lines += [f"- {describe_event(match, match.event(i))}" for i in moment.event_ids]
    lines.append("Players (role is the natural position, not the current slot):")
    for team in (home, away):
        lines += [f"- {p.id} {p.name}, {team.id}, {p.role}, {'starter' if p.starter else 'sub'}" for p in team.players]
    return "\n".join(lines)
