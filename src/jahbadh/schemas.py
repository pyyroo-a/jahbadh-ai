"""Core data contracts shared by the simulator, analytics and agents."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

Unit = Field(ge=0.0, le=1.0)

Role = Literal["GK", "CB", "FB", "DM", "CM", "AM", "W", "ST"]


class TeamTactics(BaseModel):
    press_height: float = Unit
    width: float = Unit
    tempo: float = Unit
    directness: float = Unit


class Player(BaseModel):
    id: str
    team_id: str
    name: str
    shirt: int
    role: Role
    starter: bool


class Team(BaseModel):
    id: str = Field(pattern=r"^[A-Z]{3}$")
    name: str
    formation: str
    tactics: TeamTactics
    players: list[Player]


class EventType(StrEnum):
    KICKOFF = "KICKOFF"
    PASS = "PASS"
    CARRY = "CARRY"
    SHOT = "SHOT"
    GOAL = "GOAL"
    TACKLE = "TACKLE"
    INTERCEPTION = "INTERCEPTION"
    PRESSURE = "PRESSURE"
    FOUL = "FOUL"
    CARD = "CARD"
    SUBSTITUTION = "SUBSTITUTION"
    FORMATION_CHANGE = "FORMATION_CHANGE"
    TACTIC_CHANGE = "TACTIC_CHANGE"
    PERIOD_END = "PERIOD_END"


class Event(BaseModel):
    id: int
    t: float
    period: Literal[1, 2]
    team_id: str
    player_id: str | None
    type: EventType
    x: float
    y: float
    end_x: float | None = None
    end_y: float | None = None
    outcome: bool | None = None
    xg: float | None = None
    related_player_id: str | None = None
    detail: dict[str, str | float] = {}

    @property
    def minute(self) -> int:
        return int(self.t // 60) + 1


class ScriptedChange(BaseModel):
    minute: int
    team_id: str
    kind: Literal["formation", "press_height", "substitution"]
    value: str | float | None = None
    player_out: str | None = None
    player_in: str | None = None


class MatchMeta(BaseModel):
    match_id: str
    seed: int
    home: Team
    away: Team
    storyline: list[ScriptedChange]
    score: dict[str, int]


@dataclass
class Match:
    meta: MatchMeta
    events: list[Event]
    tracking: pd.DataFrame

    def team(self, team_id: str) -> Team:
        for t in (self.meta.home, self.meta.away):
            if t.id == team_id:
                return t
        raise KeyError(team_id)

    def opponent_id(self, team_id: str) -> str:
        home, away = self.meta.home.id, self.meta.away.id
        if team_id not in (home, away):
            raise KeyError(team_id)
        return away if team_id == home else home

    def events_of(
        self,
        type: EventType | None = None,
        team_id: str | None = None,
        start: float = 0,
        end: float = 5400,
    ) -> list[Event]:
        return [
            e
            for e in self.events
            if (type is None or e.type == type)
            and (team_id is None or e.team_id == team_id)
            and start <= e.t < end
        ]

    def event(self, id: int) -> Event:
        if not hasattr(self, "_by_id") or len(self._by_id) != len(self.events):
            self._by_id = {e.id: e for e in self.events}
        return self._by_id[id]


class Metric(BaseModel):
    id: str
    name: str
    subject: str
    window: tuple[float, float]
    value: float | None
    unit: str
    evidence_event_ids: list[int] = []
    evidence_frames: tuple[int, int] | None = None
    data: dict = {}
    note: str | None = None
