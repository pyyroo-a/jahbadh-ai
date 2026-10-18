import asyncio

from fakes import ToolCall, demo_match, full_time_moment, run_for
from jahbadh.agents.analysts import analyse, explain
from jahbadh.agents.contracts import Finding, Findings
from jahbadh.agents.tools import ANALYST_TOOLS, TACTICAL_TOOLS

WIDTH_CHANGE = "width_change:RMU:2700-4500:at=3600:window=900"
COMPARE = ToolCall("compare_before_after", {"metric": "width", "subject_id": "RMU", "at_minute": 60, "window_minutes": 15})


def test_tactical_uses_tools_and_keeps_only_grounded_findings():
    real = Finding(text="RMU got wider", metric_ids=[WIDTH_CHANGE], event_ids=[])
    fake = Finding(text="made up", metric_ids=["ppda:XXX:0-1"], event_ids=[])
    run = run_for({"tactical": [COMPARE, Findings(findings=[real, fake])]}, moment=full_time_moment())  # horizon 5400
    assert asyncio.run(explain(run, [])) == [real] and WIDTH_CHANGE in run.store


def test_tactical_cannot_see_past_the_switch():
    # at the 61' switch the horizon is 3601, so the before/after window shrinks to 1 s and the 900 s id never exists
    stale = Finding(text="RMU got wider", metric_ids=[WIDTH_CHANGE], event_ids=[])
    run = run_for({"tactical": [COMPARE, Findings(findings=[stale])]})
    assert asyncio.run(explain(run, [])) == [] and "width_change:RMU:3599-3601:at=3600:window=1" in run.store


def test_tactical_gets_every_tool_and_the_analyst_brief():
    brief = [Finding(text="Rivermouth switched to a back three", metric_ids=[], event_ids=[975])]
    run = run_for({"tactical": [Findings(findings=[])]})
    asyncio.run(explain(run, brief))
    _, texts, options = run.desk.client.calls[0]
    assert sorted(t.name for t in options["tools"]) == sorted(TACTICAL_TOOLS)
    assert "Rivermouth switched to a back three" in texts[-1]


def test_analyst_only_gets_analyst_tools():
    run = run_for({"analyst": [Findings(findings=[])]})
    asyncio.run(analyse(run))
    tools = run.desk.client.calls[0][2]["tools"]
    assert sorted(t.name for t in tools) == sorted(ANALYST_TOOLS)


def test_prompts_carry_the_moment_and_rules():
    run = run_for({"analyst": [Findings(findings=[])]})
    asyncio.run(analyse(run))
    role, texts, options = run.desk.client.calls[0]
    assert role == "analyst" and "3-4-3" in texts[-1] and "61'" in texts[-1]
    assert "broadcast minute" in options["instructions"] and "descriptive" in options["instructions"]


def test_findings_citing_future_events_are_dropped():
    m = demo_match()
    late = next(e for e in m.events if e.t > 4000)
    run = run_for({"analyst": [Findings(findings=[Finding(text="later", metric_ids=[], event_ids=[late.id])])]})
    assert asyncio.run(analyse(run)) == []


def test_finding_keeps_its_good_evidence_and_loses_the_bad():
    m = demo_match()
    switch = next(e for e in m.events if e.type == "FORMATION_CHANGE")
    mixed = Finding(text="switch", metric_ids=["nope"], event_ids=[switch.id, 999999])
    run = run_for({"analyst": [Findings(findings=[mixed])]})
    assert asyncio.run(analyse(run)) == [Finding(text="switch", metric_ids=[], event_ids=[switch.id])]


def test_a_team_recap_investigates_that_teams_side():
    from jahbadh.agents.prompts import analyst_prompt
    from jahbadh.agents.spotlight import team_recap_moments
    run = run_for({}, moment=team_recap_moments(demo_match())[1])
    prompt = analyst_prompt(run)
    assert "from this moment's team's side" in prompt and "The team is RMU." in prompt
    assert "no cheering, no blame" in prompt and "Full-time recap for Rivermouth United" in prompt
