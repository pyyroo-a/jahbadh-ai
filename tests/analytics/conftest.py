"""Tiny hand-built matches so metric maths can be checked exactly.

Both teams are 4-3-3 with predictable ids: shirt 1 is the starting GK,
shirts 2 to 11 follow the formation's slot order, 12 to 16 are subs.
"""

import pandas as pd
import pytest

from jahbadh.schemas import Event, EventType, Match, MatchMeta, Player, Team, TeamTactics
from jahbadh.simulator import simulate_match
from jahbadh.simulator.formations import slots_for
from jahbadh.simulator.storyline import DEMO_STORYLINE

TACTICS = TeamTactics(press_height=0.5, width=0.5, tempo=0.5, directness=0.5)
BENCH = ["GK", "CB", "CM", "W", "ST"]
TRACKING_COLUMNS = ["t", "entity_id", "team_id", "x", "y"]


def make_team(team_id: str, name: str) -> Team:
    roles = [r for r, _, _ in slots_for("4-3-3")] + BENCH
    players = [Player(id=f"{team_id}-{i + 1}", team_id=team_id, name=f"{team_id} Player {i + 1}",
                      shirt=i + 1, role=role, starter=i < 11) for i, role in enumerate(roles)]
    return Team(id=team_id, name=name, formation="4-3-3", tactics=TACTICS, players=players)


def make_match(events: list[Event], tracking: pd.DataFrame | None = None) -> Match:
    meta = MatchMeta(match_id="test", seed=0, home=make_team("NBR", "Northbridge FC"),
                     away=make_team("RMU", "Rivermouth United"), storyline=[], score={"NBR": 0, "RMU": 0})
    if tracking is None:
        tracking = pd.DataFrame({c: pd.Series(dtype="int64" if c == "t" else "float64" if c in "xy" else "str")
                                 for c in TRACKING_COLUMNS})
    return Match(meta=meta, events=events, tracking=tracking)


def mirror(match: Match) -> Match:
    """Swap home and away and rotate the pitch 180 degrees: every team-relative metric should be unchanged."""
    def flip(e: Event) -> Event:
        upd = {"x": 105 - e.x, "y": 68 - e.y}
        if e.end_x is not None:
            upd |= {"end_x": 105 - e.end_x, "end_y": 68 - e.end_y}
        return e.model_copy(update=upd)

    meta = match.meta.model_copy(update={"home": match.meta.away, "away": match.meta.home})
    tracking = match.tracking.assign(x=105 - match.tracking.x, y=68 - match.tracking.y)
    return Match(meta=meta, events=[flip(e) for e in match.events], tracking=tracking)


def _ev(id: int, team: str, type: EventType, x: float, t: float | None, **kw) -> Event:
    return Event(id=id, t=float(id) if t is None else t, period=1, team_id=team, player_id=f"{team}-9",
                 type=type, x=x, y=kw.pop("y", 34.0), **kw)


def p(id: int, team: str, x: float, t: float | None = None, y: float = 34.0) -> Event:
    """Successful pass starting at pitch x."""
    return _ev(id, team, EventType.PASS, x, t, y=y, outcome=True, related_player_id=f"{team}-10")


def shot(id: int, team: str, xg: float, t: float | None = None) -> Event:
    return _ev(id, team, EventType.SHOT, 95.0 if team == "NBR" else 10.0, t, xg=xg, outcome=False)


def tackle(id: int, team: str, x: float, t: float | None = None) -> Event:
    return _ev(id, team, EventType.TACKLE, x, t, outcome=True)


def intercept(id: int, team: str, x: float, t: float | None = None) -> Event:
    return _ev(id, team, EventType.INTERCEPTION, x, t, outcome=True)


@pytest.fixture(scope="session")
def sim_match() -> Match:
    return simulate_match(42, storyline=DEMO_STORYLINE)
