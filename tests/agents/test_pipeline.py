"""The full grounding loop for one moment, run through the Agent Framework workflow with scripted agents."""

import asyncio
import re

from fakes import FakeTranslator, ScriptedChatClient, ToolCall, demo_match, full_time_moment
from jahbadh.agents import pipeline
from jahbadh.agents.contracts import (ClaimDraft, Draft, Figure, Finding, Findings, Moment, Rewrites, Verdict,
                                      Verdicts)
from jahbadh.agents.desk import Desk
from jahbadh.agents.pipeline import run_desk, run_moment, workflow_mermaid
from jahbadh.analytics import field_tilt

TILT = "field_tilt:NBR:0-5400"


def pct(offset: int = 0) -> str:
    return f"{round(field_tilt(demo_match(), 'NBR').value * 100) + offset}%"


def draft_with(written: str) -> Draft:
    return Draft(claims=[ClaimDraft(text=f"Northbridge FC had {written} of the final-third passes.", metric_ids=[TILT],
                                    event_ids=[], figures=[Figure(metric_id=TILT, field="value", written=written)])])


def good_draft() -> Draft:
    return draft_with(pct())


def bad_number_draft() -> Draft:
    return draft_with(pct(10))


def all_supported():
    """A referee reply that approves every claim id it is shown."""
    def reply(messages, options):
        ids = re.findall(r"^- (\S+:c\d+)", messages[-1].text, flags=re.M)
        return Verdicts(verdicts=[Verdict(claim_id=i, supported=True, reason="ok") for i in ids])
    return reply


def same_text_rewrite():
    """A persona reply that returns the lines unchanged."""
    def reply(messages, options):
        return Rewrites(texts=re.findall(r"^\d+\. (.*)$", messages[-1].text, flags=re.M))
    return reply


def scripted_moment(writer_replies, referee_replies, persona_replies=(), polish_replies=(), **desk_kw):
    script = {
        "analyst": [Findings(findings=[])],
        "tactical": [ToolCall("get_field_tilt", {"team_id": "NBR"}),
                     Findings(findings=[Finding(text="Northbridge pinned them back", metric_ids=[TILT], event_ids=[])])],
        "writer": list(writer_replies), "referee": list(referee_replies),
        "persona": list(persona_replies), "polish": list(polish_replies),
    }
    return Desk(client=ScriptedChatClient(script), match=demo_match(), **desk_kw), full_time_moment()


def test_happy_path_publishes_approved_claims():
    item = asyncio.run(run_moment(*scripted_moment(writer_replies=[good_draft()], referee_replies=[all_supported()])))
    assert len(item.claims) == 1 and item.rejections == []
    assert item.stats == {"drafted": 1, "passed_first": 1, "rewritten": 0, "dropped": 0}
    assert [m.id for m in item.metrics] == item.claims[0].metric_ids
    assert [(r.persona, r.language) for r in item.renders] == [("pundit", "en")] and item.latency_s >= 0


def test_one_rewrite_then_publish():
    item = asyncio.run(run_moment(*scripted_moment(writer_replies=[bad_number_draft(), good_draft()],
                                                   referee_replies=[all_supported()])))
    assert len(item.claims) == 1 and item.stats["rewritten"] == 1 and item.stats["passed_first"] == 0
    assert item.claims[0].id == "full_time-5400:c1"
    assert item.rejections[0].layer == "deterministic" and item.rejections[0].attempt == 0


def test_rewrite_sees_the_referees_reasons():
    desk, moment = scripted_moment(writer_replies=[bad_number_draft(), good_draft()], referee_replies=[all_supported()])
    asyncio.run(run_moment(desk, moment))
    rewrite_prompt = [texts[-1] for role, texts, _ in desk.client.calls if role == "writer"][1]
    assert "does not match" in rewrite_prompt and pct(10) in rewrite_prompt


def test_second_failure_drops_the_claim_and_keeps_both_rejections():
    item = asyncio.run(run_moment(*scripted_moment(writer_replies=[bad_number_draft(), bad_number_draft()],
                                                   referee_replies=[])))
    assert item.claims == [] and item.stats["dropped"] == 1 and [r.attempt for r in item.rejections] == [0, 1]


def test_zero_claims_publishes_an_empty_item():
    desk, moment = scripted_moment(writer_replies=[Draft(claims=[])], referee_replies=[])
    item = asyncio.run(run_moment(desk, moment))
    assert item.claims == [] and item.renders == [] and item.stats["drafted"] == 0
    assert [role for role, _, _ in desk.client.calls] == ["analyst", "tactical", "tactical", "writer"]


def test_one_failing_moment_does_not_stop_the_run(monkeypatch):
    desk, moment = scripted_moment(writer_replies=[good_draft()], referee_replies=[all_supported()])
    broken = Moment(id="check_in-600", kind="check_in", t=600, label="11' Tactical check-in")
    real = pipeline.analyse

    async def flaky(run):
        if run.moment.id == broken.id:
            raise RuntimeError("429 rate limited")
        return await real(run)

    monkeypatch.setattr(pipeline, "analyse", flaky)        # pipeline must call analyse through its module namespace
    run = asyncio.run(run_desk(desk, [broken, moment], concurrency=2))
    assert [i.moment.id for i in run.items] == [moment.id]
    assert run.failures[0].moment_id == broken.id and "rate limited" in run.failures[0].error
    assert run.match_id == desk.match.meta.match_id and run.model


def test_full_pipeline_renders_every_combo():
    desk, moment = scripted_moment(writer_replies=[good_draft()], referee_replies=[all_supported(), all_supported()],
                                   persona_replies=[same_text_rewrite()], polish_replies=[Rewrites(texts=[])] * 2,
                                   personas=("pundit", "casual"), languages=("en", "ar"), translator=FakeTranslator())
    item = asyncio.run(run_moment(desk, moment))
    assert sorted((r.persona, r.language) for r in item.renders) == \
        [("casual", "ar"), ("casual", "en"), ("pundit", "ar"), ("pundit", "en")]


def test_workflow_diagram_shows_the_rewrite_loop():
    desk = Desk(client=None, match=demo_match())
    chart = workflow_mermaid(desk)
    assert "referee -. conditional .-> writer" in chart and "referee -. conditional .-> persona" in chart
