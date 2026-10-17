import pandas as pd
import pytest

from jahbadh.schemas import Event, EventType, Match, MatchMeta, Player, Team, TeamTactics

TACTICS = TeamTactics(press_height=0.5, width=0.5, tempo=0.5, directness=0.5)


def _team(team_id: str, name: str) -> Team:
    players = [
        Player(id=f"{team_id}-1", team_id=team_id, name="Keeper", shirt=1, role="GK", starter=True),
        Player(id=f"{team_id}-9", team_id=team_id, name="Striker", shirt=9, role="ST", starter=True),
    ]
    return Team(id=team_id, name=name, formation="4-3-3", tactics=TACTICS, players=players)


@pytest.fixture
def tiny_match() -> Match:
    home, away = _team("NBR", "Northbridge FC"), _team("RMU", "Rivermouth United")
    events = [
        Event(id=1, t=10, period=1, team_id="NBR", player_id="NBR-9", type=EventType.PASS, x=50, y=30, outcome=True),
        Event(id=2, t=20, period=1, team_id="NBR", player_id="NBR-9", type=EventType.SHOT, x=90, y=34, xg=0.2),
        Event(id=3, t=30, period=1, team_id="RMU", player_id="RMU-9", type=EventType.PASS, x=40, y=30, outcome=True),
    ]
    meta = MatchMeta(match_id="tiny", seed=0, home=home, away=away, storyline=[], score={"NBR": 0, "RMU": 0})
    tracking = pd.DataFrame(columns=["t", "entity_id", "team_id", "x", "y"])
    return Match(meta=meta, events=events, tracking=tracking)
