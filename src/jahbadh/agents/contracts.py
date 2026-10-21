"""Typed contracts between the desk's agents.

Models passed to the model as a response_format (Findings, Draft, Verdicts, Rewrites and what they
contain) have no dict fields, because strict JSON schema mode can't express free-form objects.
"""

from math import floor
from typing import Literal

from pydantic import BaseModel

from jahbadh.schemas import Metric

MomentKind = Literal["goal", "big_chance", "card", "substitution", "formation_change", "tactic_change",
                     "momentum_swing", "check_in", "full_time", "spotlight", "team_recap"]
Persona = Literal["pundit", "casual", "fantasy"]
Language = Literal["en", "ar", "es"]
# The desk's steps a viewer can watch finish. Persona and Localize are part of "publish".
DeskStep = Literal["analyst", "tactical", "writer", "referee", "rewrite", "recheck", "publish"]
Layer = Literal["deterministic", "semantic", "persona", "localization"]


class Moment(BaseModel):
    id: str
    kind: MomentKind
    t: float
    team_id: str | None = None
    player_id: str | None = None
    event_ids: list[int] = []
    label: str

    @property
    def minute(self) -> int:
        """Broadcast minute, capped at 90 so full time reads 90'."""
        return min(90, int(self.t // 60) + 1)

    @property
    def horizon(self) -> float:
        """Agents only see data before this time, so live commentary never knows the future."""
        return min(5400.0, float(floor(self.t) + 1))


# LLM output models

class Finding(BaseModel):
    text: str
    metric_ids: list[str]
    event_ids: list[int]


class Findings(BaseModel):
    findings: list[Finding]


class Figure(BaseModel):
    metric_id: str
    field: str
    written: str


class ClaimDraft(BaseModel):
    text: str
    metric_ids: list[str]
    event_ids: list[int]
    figures: list[Figure]


class Draft(BaseModel):
    claims: list[ClaimDraft]


class Verdict(BaseModel):
    claim_id: str
    supported: bool
    reason: str


class Verdicts(BaseModel):
    verdicts: list[Verdict]


class Rewrites(BaseModel):
    texts: list[str]


# Desk records

class Claim(ClaimDraft):
    id: str


class Rejection(BaseModel):
    claim_id: str
    text: str
    layer: Layer
    reasons: list[str]
    attempt: int
    persona: Persona | None = None
    language: Language | None = None


class RenderedClaim(BaseModel):
    claim_id: str
    persona: Persona
    language: Language
    text: str
    note: str | None = None


class FeedItem(BaseModel):
    moment: Moment
    claims: list[Claim]
    renders: list[RenderedClaim]
    rejections: list[Rejection]
    metrics: list[Metric]
    stats: dict[str, int]
    latency_s: float


class MomentFailure(BaseModel):
    moment_id: str
    error: str


class DeskRun(BaseModel):
    match_id: str
    model: str
    created: str
    items: list[FeedItem]
    failures: list[MomentFailure]
