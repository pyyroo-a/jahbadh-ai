"""Shared helpers for metrics: stable ids and team direction."""

from jahbadh.schemas import Match


def metric_id(name: str, subject: str, start: float, end: float) -> str:
    return f"{name}:{subject}:{int(start)}-{int(end)}"


def is_home(match: Match, team_id: str) -> bool:
    match.team(team_id)  # raises KeyError for an unknown team
    return team_id == match.meta.home.id
