"""The desk's stream protocol: what each server-sent message carries, in both replay and live mode.

Every message is one kind with one model. Index 0 is always `match`; the rest come in time order. Plan 2's
Moment, FeedItem and MomentFailure travel as they are. Turning a StreamItem into an SSE message lives with the
code that streams (jahbadh.api.replay), so this module stays plain pydantic.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from jahbadh.agents.contracts import DeskStep, Language, Rejection, RenderedClaim
from jahbadh.schemas import EventType, Metric, Team

StreamKind = Literal["match", "event", "state", "thinking", "feed", "failure", "renders", "cue", "end", "step", "pace"]


class MatchInfo(BaseModel):
    match_id: str
    mode: Literal["replay", "live", "ingest"]
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
    speed_kmh: float | None           # synthetic ball speed, on passes and shots only
    lines: dict[Language, str]
    buildup: list["EventLine"] | None = None    # goals only: the move's steps in order, the shot last


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
    pass_speed: dict[str, float | None]        # each team's mean synthetic pass speed, km/h
    shots: dict[str, int]                      # each team's shots so far


class RendersUpdate(BaseModel):
    moment_id: str
    renders: list[RenderedClaim]
    rejections: list[Rejection]


class StepUpdate(BaseModel):
    """One of the desk's steps finished for a moment, at match second t (live and ingest only)."""
    moment_id: str
    step: DeskStep
    t: float


class PaceUpdate(BaseModel):
    """From match second t the clock runs at `speed`; `holding` names the key moments slowing it, earliest first."""
    t: float
    speed: float
    holding: list[str]


class StreamEnd(BaseModel):
    reason: Literal["full_time", "cancelled"]


@dataclass(frozen=True)
class StreamItem:
    t: float
    kind: StreamKind
    data: BaseModel
