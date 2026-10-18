"""The desk's stream protocol: what each server-sent message carries, in both replay and live mode.

Every message is one kind with one model. Index 0 is always `match`; the rest come in time order. Plan 2's
Moment, FeedItem and MomentFailure travel as they are. Turning a StreamItem into an SSE message lives with the
code that streams (jahbadh.api.replay), so this module stays plain pydantic.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from jahbadh.agents.contracts import Language, Rejection, RenderedClaim
from jahbadh.schemas import EventType, Metric, Team

StreamKind = Literal["match", "event", "state", "thinking", "feed", "failure", "renders", "cue", "end"]


class MatchInfo(BaseModel):
    match_id: str
    mode: Literal["replay", "live"]
    home: Team
    away: Team
    speed: float
    precomputed: bool
    model: str | None = None
    created: str | None = None
    moment_times: list[float] = []      # replay only, for "skip to next moment": times, never labels


class EventLine(BaseModel):
    id: int
    t: float
    minute: int
    type: EventType
    team_id: str
    player_id: str | None
    related_player_id: str | None
    x: float
    y: float
    end_x: float | None
    end_y: float | None
    outcome: bool | None
    xg: float | None
    lines: dict[Language, str]


class MatchState(BaseModel):
    """The match at one second: score and xG so far, the rest over the last 10 minutes."""
    t: float
    minute: int
    score: dict[str, int]
    xg: dict[str, float]
    momentum: float | None            # home team's share of threat
    field_tilt: float | None          # home team's share of final-third passes
    ppda: dict[str, float | None]     # keyed by the defending team
    shape: dict[str, Metric]          # average_positions per team, in that team's attacking frame
    formations: dict[str, str]
    rhythm: Metric | None             # game_rhythm, controlled to chaotic
    pass_difficulty: dict[str, float | None]   # each team's mean pass difficulty


class RendersUpdate(BaseModel):
    moment_id: str
    renders: list[RenderedClaim]
    rejections: list[Rejection]


class StreamEnd(BaseModel):
    reason: Literal["full_time", "cancelled"]


@dataclass(frozen=True)
class StreamItem:
    t: float
    kind: StreamKind
    data: BaseModel
