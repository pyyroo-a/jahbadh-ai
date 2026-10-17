"""Shared helpers for metrics: stable ids and team direction."""

from jahbadh.schemas import Match

MATCH_END = 5400.0


def check_window(start: float, end: float) -> None:
    """Refuse windows outside the match: a metric over a bad window would still look plausible."""
    if not 0 <= start < end <= MATCH_END:
        raise ValueError(f"window {start}-{end} must satisfy 0 <= start < end <= {MATCH_END:g}")


def metric_id(name: str, subject: str, start: float, end: float, **params: object) -> str:
    """Stable id, e.g. "ppda:NBR:0-5400". Pass any non-default parameter that changes the value
    (e.g. margin=1) so two different values can never share an id: "zone_overloads:RMU:0-900:margin=1"."""
    base = f"{name}:{subject}:{int(start)}-{int(end)}"
    return base + "".join(f":{k}={v}" for k, v in sorted(params.items()))


def is_home(match: Match, team_id: str) -> bool:
    match.team(team_id)  # raises KeyError for an unknown team
    return team_id == match.meta.home.id
