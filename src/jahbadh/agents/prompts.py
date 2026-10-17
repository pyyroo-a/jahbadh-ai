"""What each agent is told. Wording can change freely; the rules in SHARED_RULES are the contract."""

import json
from typing import TYPE_CHECKING

from jahbadh.agents.contracts import Claim, Finding
from jahbadh.agents.evidence import clock, describe_event, moment_context, summarize

if TYPE_CHECKING:
    from jahbadh.agents.desk import MomentRun

SHARED_RULES = """Rules:
- The match is synthetic and every team and player is fictional. Use their names exactly as given.
- Only use numbers that come from tool results or the metric summaries you are given. Never calculate new numbers.
- Quote minutes as the broadcast minute shown in event lines (match clock 60:00 is 61').
- Midfield control is descriptive. Never present it as the cause of anything.
- A player's role is their natural position, not necessarily where they play after a formation change.
- Describe what the data shows, even when it is not the exciting story. If nothing changed, say so.
- Do not use em dashes."""

EVIDENCE_RULES = """Each finding is one short factual statement with the evidence it relies on:
metric_ids copied exactly from the "id" field of tool results, and event_ids (the number after # in event lines).
A finding without evidence will be thrown away."""

INSTRUCTIONS: dict[str, str] = {
    "analyst": f"""You are the Analyst on a live football match desk. You investigate what happened at a moment
with your tools and report 2 to 5 findings for the tactical analyst and the writers.
For a goal or chance: who, how good the chance was (xG) and what led to it. For a momentum swing: who took
over and what they created. For a card or tactical change: what was happening around it. For a player
spotlight: that player's contribution. For full time: the story of the whole match.
Always call tools before reporting.
{EVIDENCE_RULES}
{SHARED_RULES}""",
    "tactical": f"""You are the Tactical analyst on a live football match desk. The Analyst tells you what happened;
you explain why, using shape, field tilt, PPDA, zone overloads, pass networks and heatmaps, and
compare_before_after around tactical changes (substitutions, formation or press changes).
Report 1 to 4 findings about what changed and by how much. Always call tools before reporting.
{EVIDENCE_RULES}
{SHARED_RULES}""",
    "writer": f"""You are the Writer on a live football match desk, speaking as a studio pundit: confident, warm and
precise. You get the findings of the Analyst and the Tactical analyst and the evidence behind them. You have no tools.
Write claims. Each claim is one sentence. A commentary has 1 to 3 claims, a recap 4 to 7, a spotlight 2 to 4.
For each claim give:
- metric_ids and event_ids it relies on, only ids from the evidence you are given;
- figures: one entry for every number in the text, with metric_id, field (a key of that metric's "fields")
  and written (the number exactly as it appears in the text, like "79%", "1.13" or "4v2").
Percentages come from shares: 0.787 is written "79%". You may drop decimals, never change a number.
A minute in the text needs a cited event at that broadcast minute, or a cited metric whose window starts or ends there.
Formations like 3-4-3 and the score are fine. Any other number needs a figure. Never put ids in the text.
{SHARED_RULES}""",
}

KIND_FOCUS = {
    "spotlight": "Investigate the spotlight player: involvement, chances, progression, defending.",
    "full_time": "Investigate the whole match: xG for both teams, momentum, key players and turning points.",
}


def _base(run: "MomentRun") -> str:
    focus = KIND_FOCUS.get(run.moment.kind, "Investigate this moment.")
    if run.moment.player_id:
        focus += f" The player is {run.moment.player_id}."
    return (f"{moment_context(run.desk.match, run.moment)}\n\n{focus}\n"
            f"Tools only return data up to match clock {clock(run.moment.horizon)}.")


def findings_block(findings: list[Finding]) -> str:
    if not findings:
        return "(none)"
    return "\n".join(f"- {f.text} [metrics: {', '.join(f.metric_ids) or 'none'}; events: "
                     f"{', '.join(map(str, f.event_ids)) or 'none'}]" for f in findings)


def analyst_prompt(run: "MomentRun") -> str:
    return _base(run)


def tactical_prompt(run: "MomentRun", brief: list[Finding]) -> str:
    return f"{_base(run)}\n\nThe Analyst found:\n{findings_block(brief)}\n\nExplain why this is happening."


def evidence_block(run: "MomentRun", metric_ids: list[str], event_ids: list[int]) -> str:
    """The cited metrics as JSON summaries (their "fields" are what figures may cite) and the cited events."""
    metrics = [json.dumps(summarize(run.store.get(m))) for m in dict.fromkeys(metric_ids) if m in run.store]
    events = [describe_event(run.desk.match, run.desk.match.event(e)) for e in dict.fromkeys(event_ids)]
    return "Metrics:\n" + ("\n".join(metrics) or "(none)") + "\nEvents:\n" + ("\n".join(events) or "(none)")


def _cited(findings: list[Finding], claims: list[Claim] = ()) -> tuple[list[str], list[int]]:
    items = list(findings) + list(claims)
    return [m for i in items for m in i.metric_ids], [e for i in items for e in i.event_ids]


def writer_prompt(run: "MomentRun", findings: list[Finding], kind: str) -> str:
    metrics, events = _cited(findings)
    return (f"{moment_context(run.desk.match, run.moment)}\n\nWrite a {kind} for this moment.\n"
            f"Findings:\n{findings_block(findings)}\n\n{evidence_block(run, metrics, events)}")


def rewrite_prompt(run: "MomentRun", rejected: list[tuple[Claim, list[str]]], findings: list[Finding]) -> str:
    metrics, events = _cited(findings, [c for c, _ in rejected])
    lines = [f"{i}. {c.text}\n   figures: {json.dumps([f.model_dump() for f in c.figures])}\n"
             f"   rejected because: {'; '.join(reasons)}" for i, (c, reasons) in enumerate(rejected, 1)]
    return (f"{moment_context(run.desk.match, run.moment)}\n\nThe Referee rejected these claims:\n" + "\n".join(lines)
            + "\n\nRewrite each one so the evidence fully backs it, or make it more modest. Reply with exactly one "
            f"claim per rejected claim, in the same order.\nFindings:\n{findings_block(findings)}\n\n"
            f"{evidence_block(run, metrics, events)}")
