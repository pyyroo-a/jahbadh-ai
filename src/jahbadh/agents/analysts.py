"""The Analyst (what happened) and the Tactical analyst (why), both tool-using agents."""

from jahbadh.agents.contracts import Finding, Findings
from jahbadh.agents.desk import MomentRun
from jahbadh.agents.llm import ask
from jahbadh.agents.prompts import analyst_prompt, tactical_prompt
from jahbadh.agents.tools import ANALYST_TOOLS, TACTICAL_TOOLS


def _known_event(run: MomentRun, event_id: int) -> bool:
    try:
        return run.desk.match.event(event_id).t < run.moment.horizon
    except KeyError:
        return False


def keep_grounded(run: MomentRun, findings: list[Finding]) -> list[Finding]:
    """Drop evidence the agent made up or can't know yet, then any finding left with no evidence."""
    kept = []
    for f in findings:
        metric_ids = [m for m in f.metric_ids if m in run.store]
        event_ids = [e for e in f.event_ids if _known_event(run, e)]
        if metric_ids or event_ids:
            kept.append(f.model_copy(update={"metric_ids": metric_ids, "event_ids": event_ids}))
    return kept


async def analyse(run: MomentRun) -> list[Finding]:
    agent = run.desk.agent("analyst", [run.tools[name] for name in ANALYST_TOOLS])
    return keep_grounded(run, (await ask(agent, analyst_prompt(run), Findings)).findings)


async def explain(run: MomentRun, brief: list[Finding]) -> list[Finding]:
    agent = run.desk.agent("tactical", [run.tools[name] for name in TACTICAL_TOOLS])
    return keep_grounded(run, (await ask(agent, tactical_prompt(run, brief), Findings)).findings)
