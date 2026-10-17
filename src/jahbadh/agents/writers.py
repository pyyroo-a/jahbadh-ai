"""The Writer: turns findings into structured, evidence-tagged claims. It has no tools on purpose."""

import re
from typing import Literal

from jahbadh.agents.contracts import Claim, ClaimDraft, Draft, Finding, Moment
from jahbadh.agents.desk import MomentRun
from jahbadh.agents.grounding import occurrence
from jahbadh.agents.llm import ask
from jahbadh.agents.prompts import rewrite_prompt, writer_prompt

WriterKind = Literal["commentary", "recap", "spotlight"]

EM_DASH = re.compile(r"\s*\u2014\s*|\s+\u2013\s+")   # em dash anywhere, or a spaced en dash
EN_DASH = "\u2013"


MINUTE_MARK = re.compile(r"^\d{1,2}['’]$")


def no_em_dashes(text: str) -> str:
    return EM_DASH.sub(", ", text).replace(EN_DASH, "-")


def tidy(run: MomentRun, draft: ClaimDraft) -> ClaimDraft:
    """Fix bookkeeping, never truth: no em dashes, figures only for numbers really in the text (minutes have
    their own rule, so a minute is never a figure), a figure's metric listed as evidence when it is in the store,
    and an event figure's event listed too. Every number left still has to pass the Referee."""
    text = no_em_dashes(draft.text)
    figures = [f for f in draft.figures if occurrence(f.written, text) and not MINUTE_MARK.match(f.written)]
    metric_ids = list(dict.fromkeys(draft.metric_ids + [f.metric_id for f in figures if f.metric_id in run.store]))
    event_ids = list(draft.event_ids)
    for f in figures:
        raw = f.metric_id.removeprefix("event:")
        if f.metric_id.startswith("event:") and raw.isdigit() and int(raw) not in event_ids:
            event_ids.append(int(raw))
    return draft.model_copy(update={"text": text, "figures": figures, "metric_ids": metric_ids, "event_ids": event_ids})


def kind_for(moment: Moment) -> WriterKind:
    return {"full_time": "recap", "spotlight": "spotlight"}.get(moment.kind, "commentary")


async def write(run: MomentRun, findings: list[Finding]) -> list[Claim]:
    draft = await ask(run.desk.agent("writer"), writer_prompt(run, findings, kind_for(run.moment)), Draft)
    return [Claim(id=f"{run.moment.id}:c{i}", **tidy(run, c).model_dump()) for i, c in enumerate(draft.claims, 1)]


async def rewrite(run: MomentRun, rejected: list[tuple[Claim, list[str]]], findings: list[Finding]) -> list[Claim]:
    """Fixed versions of rejected claims. They keep the original ids by position; extras are ignored."""
    draft = await ask(run.desk.agent("writer"), rewrite_prompt(run, rejected, findings), Draft)
    return [Claim(id=old.id, **tidy(run, new).model_dump()) for (old, _), new in zip(rejected, draft.claims)]
