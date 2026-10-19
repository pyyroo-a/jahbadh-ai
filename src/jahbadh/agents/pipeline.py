"""The orchestrator: one Microsoft Agent Framework workflow per moment, and a concurrent run over a match.

    Analyst -> Tactical -> Writer -> Referee --(rejected, first time)--> Writer
                                        |
                                        +--(otherwise)--> Persona -> Localize -> Publish

Every executor receives and sends the same MomentState. A rejected claim gets one rewrite; if the rewrite
fails too it is dropped. Every rejection is kept, because the UI shows them on purpose.
"""

import asyncio
import time
from datetime import UTC, datetime
from typing import Never

from agent_framework import Executor, Workflow, WorkflowBuilder, WorkflowContext, WorkflowViz, handler
from pydantic import BaseModel

from jahbadh.agents.analysts import analyse, explain
from jahbadh.agents.contracts import (Claim, DeskRun, FeedItem, Finding, Moment, MomentFailure, Rejection,
                                      RenderedClaim)
from jahbadh.agents.desk import Desk, MomentRun
from jahbadh.agents.llm import AgentOutputError
from jahbadh.agents.localize import localize
from jahbadh.agents.persona import render_personas
from jahbadh.agents.referee import referee
from jahbadh.agents.writers import rewrite, write


class MomentState(BaseModel):
    moment: Moment
    findings: list[Finding] = []
    approved: list[Claim] = []
    pending: list[Claim] = []
    retry: list[tuple[Claim, list[str]]] = []
    rejections: list[Rejection] = []
    renders: list[RenderedClaim] = []
    attempt: int = 0
    stats: dict[str, int] = {"drafted": 0, "passed_first": 0, "rewritten": 0, "dropped": 0}


class _Step(Executor):
    def __init__(self, step_id: str, run: MomentRun):
        super().__init__(id=step_id)
        self.run = run


class AnalystStep(_Step):
    @handler
    async def handle(self, state: MomentState, ctx: WorkflowContext[MomentState]) -> None:
        await ctx.send_message(state.model_copy(update={"findings": await analyse(self.run)}))


class TacticalStep(_Step):
    @handler
    async def handle(self, state: MomentState, ctx: WorkflowContext[MomentState]) -> None:
        found = await explain(self.run, state.findings)
        await ctx.send_message(state.model_copy(update={"findings": state.findings + found}))


class WriterStep(_Step):
    @handler
    async def handle(self, state: MomentState, ctx: WorkflowContext[MomentState]) -> None:
        stats = dict(state.stats)
        if state.retry:
            try:
                claims = await rewrite(self.run, state.retry, state.findings)
            except AgentOutputError:
                claims = []         # a broken rewrite drops the retries, never the claims already approved
            stats["rewritten"] += len(claims)
            stats["dropped"] += len(state.retry) - len(claims)     # claims the writer gave up on
            update = {"pending": claims, "retry": [], "attempt": 1}
        else:
            claims = await write(self.run, state.findings)
            stats["drafted"] += len(claims)
            if self.run.desk.planter:             # the eval's false claims ride along, outside the stats
                claims = claims + self.run.desk.planter(self.run, claims)
            update = {"pending": claims}
        await ctx.send_message(state.model_copy(update=update | {"stats": stats}))


class RefereeStep(_Step):
    @handler
    async def handle(self, state: MomentState, ctx: WorkflowContext[MomentState]) -> None:
        approved, rejections = await referee(self.run, state.pending, state.attempt)
        planter = self.run.desk.planter
        if planter:                               # record each planted claim's verdict, then drop it for good
            planted = {c.id: c for c in state.pending if planter.is_planted(c.id)}
            for cid, claim in planted.items():
                planter.record(claim, next((r for r in rejections if r.claim_id == cid), None))
            approved = [c for c in approved if c.id not in planted]
            rejections = [r for r in rejections if r.claim_id not in planted]
        rejected_ids = {r.claim_id for r in rejections}
        reasons = {r.claim_id: r.reasons for r in rejections}
        failed = [c for c in state.pending if c.id in rejected_ids]
        stats = dict(state.stats)
        if state.attempt == 0:
            stats["passed_first"] += len(approved)
            retry = [(c, reasons[c.id]) for c in failed]
        else:
            stats["dropped"] += len(failed)
            retry = []
        await ctx.send_message(state.model_copy(update={
            "approved": state.approved + approved, "pending": [], "retry": retry,
            "rejections": state.rejections + rejections, "stats": stats}))


class PersonaStep(_Step):
    @handler
    async def handle(self, state: MomentState, ctx: WorkflowContext[MomentState]) -> None:
        renders, rejections = await render_personas(self.run, state.approved)
        await ctx.send_message(state.model_copy(update={"renders": renders,
                                                        "rejections": state.rejections + rejections}))


class LocalizeStep(_Step):
    @handler
    async def handle(self, state: MomentState, ctx: WorkflowContext[MomentState]) -> None:
        renders, rejections = await localize(self.run, state.renders)
        await ctx.send_message(state.model_copy(update={"renders": state.renders + renders,
                                                        "rejections": state.rejections + rejections}))


class PublishStep(_Step):
    @handler
    async def handle(self, state: MomentState, ctx: WorkflowContext[Never, FeedItem]) -> None:
        cited = dict.fromkeys(m for c in state.approved for m in c.metric_ids)
        await ctx.yield_output(FeedItem(moment=state.moment, claims=state.approved, renders=state.renders,
                                        rejections=state.rejections, metrics=[self.run.store.get(m) for m in cited],
                                        stats=state.stats, latency_s=0.0))


def build_workflow(run: MomentRun) -> Workflow:
    analyst, tactical, writer = AnalystStep("analyst", run), TacticalStep("tactical", run), WriterStep("writer", run)
    ref, persona = RefereeStep("referee", run), PersonaStep("persona", run)
    loc, publish = LocalizeStep("localize", run), PublishStep("publish", run)
    return (WorkflowBuilder(start_executor=analyst, name="moment")
            .add_edge(analyst, tactical)
            .add_edge(tactical, writer)
            .add_edge(writer, ref)
            .add_edge(ref, writer, condition=lambda s: bool(s.retry))
            .add_edge(ref, persona, condition=lambda s: not s.retry)
            .add_edge(persona, loc)
            .add_edge(loc, publish)
            .build())


async def run_moment(desk: Desk, moment: Moment) -> FeedItem:
    started = time.perf_counter()
    result = await build_workflow(desk.start(moment)).run(MomentState(moment=moment))
    outputs = result.get_outputs()
    if not outputs:
        raise RuntimeError(f"moment {moment.id} finished without publishing")
    return outputs[0].model_copy(update={"latency_s": round(time.perf_counter() - started, 2)})


async def run_desk(desk: Desk, moments: list[Moment], concurrency: int = 3) -> DeskRun:
    """Run every moment, at most `concurrency` at once. A failing moment is recorded and the rest carry on."""
    gate = asyncio.Semaphore(concurrency)

    async def one(moment: Moment) -> FeedItem | MomentFailure:
        async with gate:
            try:
                return await run_moment(desk, moment)
            except Exception as e:  # one bad moment (rate limit, bad reply) must never stop the match
                return MomentFailure(moment_id=moment.id, error=f"{type(e).__name__}: {e}")

    results = await asyncio.gather(*(one(m) for m in moments))
    model = getattr(desk.client, "model", None) or type(desk.client).__name__
    return DeskRun(match_id=desk.match.meta.match_id, model=str(model), created=datetime.now(UTC).isoformat(),
                   items=sorted((r for r in results if isinstance(r, FeedItem)), key=lambda i: i.moment.t),
                   failures=[r for r in results if isinstance(r, MomentFailure)])


def workflow_mermaid(desk: Desk) -> str:
    """The per-moment workflow as a Mermaid flowchart (no model calls)."""
    full_time = Moment(id="full_time-5400", kind="full_time", t=5400, label="Full time")
    return WorkflowViz(build_workflow(desk.start(full_time))).to_mermaid()
