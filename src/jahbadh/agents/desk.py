"""The desk for one match, and a run for one moment (its own evidence store and tools)."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from agent_framework import Agent

from jahbadh.agents.contracts import Claim, Language, Moment, Persona, Rejection
from jahbadh.agents.evidence import EvidenceStore
from jahbadh.agents.llm import AgentName, make_agent
from jahbadh.agents.prompts import INSTRUCTIONS
from jahbadh.agents.tools import make_tools
from jahbadh.schemas import Match


class Translator(Protocol):
    def translate(self, texts: list[str], to: str, keep: list[str]) -> list[str]: ...


class Planter(Protocol):
    """The eval's hook: adds known-false claims to the first drafts and hears what the Referee made of them."""
    def __call__(self, run: "MomentRun", drafts: list[Claim]) -> list[Claim]: ...
    def is_planted(self, claim_id: str) -> bool: ...
    def record(self, claim: Claim, rejection: Rejection | None) -> None: ...


@dataclass
class Desk:
    client: Any                      # any Agent Framework chat client; None is fine for drawing the workflow
    match: Match
    translator: Translator | None = None
    personas: tuple[Persona, ...] = ("pundit",)
    languages: tuple[Language, ...] = ("en",)
    effort: str = "low"
    planter: Planter | None = None   # only the eval sets this; planted claims are checked, then dropped

    def agent(self, name: AgentName, tools: Sequence[Callable] = ()) -> Agent:
        return make_agent(self.client, name, INSTRUCTIONS[name], tools, self.effort)

    def start(self, moment: Moment) -> "MomentRun":
        store = EvidenceStore(self.match)
        return MomentRun(desk=self, moment=moment, store=store, tools=make_tools(self.match, store, moment.horizon))


@dataclass
class MomentRun:
    desk: Desk
    moment: Moment
    store: EvidenceStore
    tools: dict[str, Callable[..., str]] = field(default_factory=dict)
