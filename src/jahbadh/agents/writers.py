"""The Writer: turns findings into structured, evidence-tagged claims. It has no tools on purpose."""

from typing import Literal

from jahbadh.agents.contracts import Claim, Draft, Finding, Moment
from jahbadh.agents.desk import MomentRun
from jahbadh.agents.llm import ask
from jahbadh.agents.prompts import rewrite_prompt, writer_prompt

WriterKind = Literal["commentary", "recap", "spotlight"]


def kind_for(moment: Moment) -> WriterKind:
    return {"full_time": "recap", "spotlight": "spotlight"}.get(moment.kind, "commentary")


async def write(run: MomentRun, findings: list[Finding]) -> list[Claim]:
    draft = await ask(run.desk.agent("writer"), writer_prompt(run, findings, kind_for(run.moment)), Draft)
    return [Claim(id=f"{run.moment.id}:c{i}", **c.model_dump()) for i, c in enumerate(draft.claims, 1)]


async def rewrite(run: MomentRun, rejected: list[tuple[Claim, list[str]]], findings: list[Finding]) -> list[Claim]:
    """Fixed versions of rejected claims. They keep the original ids by position; extras are ignored."""
    draft = await ask(run.desk.agent("writer"), rewrite_prompt(run, rejected, findings), Draft)
    return [Claim(id=old.id, **new.model_dump()) for (old, _), new in zip(rejected, draft.claims)]
