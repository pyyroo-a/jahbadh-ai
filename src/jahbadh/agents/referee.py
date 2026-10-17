"""The Referee: the deterministic check first, then an LLM judge on the claims that survive it.

The judge fails closed: a claim with no verdict, or a judge that can't answer, is rejected.
"""

from typing import Literal

from jahbadh.agents.contracts import Claim, Rejection, Verdicts
from jahbadh.agents.desk import MomentRun
from jahbadh.agents.grounding import check_claim
from jahbadh.agents.llm import AgentOutputError, ask
from jahbadh.agents.prompts import judge_prompt


async def judge(run: MomentRun, claims: list[Claim], mode: Literal["support", "faithful"] = "support",
                originals: dict[str, str] | None = None) -> dict[str, str | None]:
    """claim id -> None when supported, else the reason. One call for the whole batch."""
    if not claims:
        return {}
    try:
        reply = await ask(run.desk.agent("referee"), judge_prompt(run, claims, mode, originals), Verdicts)
    except AgentOutputError:
        return {c.id: "referee unavailable" for c in claims}
    verdicts = {v.claim_id: v for v in reply.verdicts}
    result: dict[str, str | None] = {}
    for c in claims:
        v = verdicts.get(c.id)
        result[c.id] = "referee gave no verdict" if v is None else None if v.supported else (v.reason or "not supported")
    return result


async def referee(run: MomentRun, claims: list[Claim], attempt: int) -> tuple[list[Claim], list[Rejection]]:
    """Approved claims and one Rejection per failed claim. Only claims that pass layer 1 cost an LLM call."""
    rejections, survivors = [], []
    for c in claims:
        reasons = check_claim(c, run.desk.match, run.store, run.moment.horizon)
        if reasons:
            rejections.append(Rejection(claim_id=c.id, text=c.text, layer="deterministic", reasons=reasons, attempt=attempt))
        else:
            survivors.append(c)
    verdicts = await judge(run, survivors)
    approved = []
    for c in survivors:
        if verdicts[c.id] is None:
            approved.append(c)
        else:
            rejections.append(Rejection(claim_id=c.id, text=c.text, layer="semantic", reasons=[verdicts[c.id]],
                                        attempt=attempt))
    return approved, rejections
