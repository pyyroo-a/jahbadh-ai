"""Player spotlights and per-club recaps: the extra full-time moments, data-true.

Three angles so the quieter heroes get a turn too: expected goal involvement, progressive passes and ball
wins. Each angle picks a different player, and an angle where nobody did anything is skipped.
"""

from jahbadh.agents.contracts import Moment
from jahbadh.analytics import player_rankings
from jahbadh.schemas import Match

SPOTLIGHT_ANGLES = (("value", "most expected goal involvement"),
                    ("progressive_passes", "most progressive passes"),
                    ("ball_wins", "most ball wins"))


def spotlight_moment(match: Match, player_id: str, angle_label: str, t: float = 5400) -> Moment:
    for team in (match.meta.home, match.meta.away):
        for p in team.players:
            if p.id == player_id:
                return Moment(id=f"spotlight-{player_id}", kind="spotlight", t=t, team_id=team.id,
                              player_id=player_id, label=f"Spotlight: {p.name} ({angle_label})")
    raise KeyError(player_id)


def team_recap_moments(match: Match, t: float = 5400) -> list[Moment]:
    """One full-time recap per club, home first, told from that club's side (favourite-club mode)."""
    return [Moment(id=f"team_recap-{team.id}", kind="team_recap", t=t, team_id=team.id,
                   label=f"Full-time recap for {team.name}") for team in (match.meta.home, match.meta.away)]


def spotlight_moments(match: Match, t: float = 5400) -> list[Moment]:
    chosen: list[Moment] = []
    for key, label in SPOTLIGHT_ANGLES:
        for m in player_rankings(match, None, 0, t, by=key, n=5):
            value = m.value if key == "value" else m.data.get(key)
            if not value or value <= 0:
                break                       # rankings are sorted, so nobody further down did better
            if all(c.player_id != m.subject for c in chosen):
                chosen.append(spotlight_moment(match, m.subject, label, t))
                break
    return chosen
