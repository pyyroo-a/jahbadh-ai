"""Persona: the same approved facts, told for a casual fan or a fantasy player.

The pundit voice is the Writer's own, so it costs nothing. Other personas are rewritten and then re-checked
(numbers check, then the judge in faithful mode), so no new claim can sneak in. Anything that fails falls
back to the pundit line, and the rejection is kept.
"""

from jahbadh.agents.contracts import Claim, Persona, Rejection, RenderedClaim, Rewrites
from jahbadh.agents.desk import MomentRun
from jahbadh.agents.grounding import check_claim, occurrence
from jahbadh.agents.llm import AgentOutputError, ask
from jahbadh.agents.numbers import words_to_digits
from jahbadh.agents.prompts import persona_prompt
from jahbadh.agents.referee import judge
from jahbadh.agents.writers import no_em_dashes

FALLBACK = "persona fallback"


def _pundit(claims: list[Claim]) -> list[RenderedClaim]:
    return [RenderedClaim(claim_id=c.id, persona="pundit", language="en", text=c.text) for c in claims]


async def _render(run: MomentRun, persona: Persona, claims: list[Claim]) -> tuple[list[RenderedClaim], list[Rejection]]:
    try:
        reply = await ask(run.desk.agent("persona"), persona_prompt(persona, [c.text for c in claims]), Rewrites)
        texts = [no_em_dashes(t) for t in reply.texts]
        problem = None if len(texts) == len(claims) else f"persona gave {len(texts)} rewrites for {len(claims)} lines"
    except AgentOutputError as e:
        texts, problem = [], str(e)

    failures: dict[str, tuple[str, list[str]]] = {}
    candidates: list[Claim] = []
    for i, c in enumerate(claims):
        if problem:
            failures[c.id] = (c.text, [problem])
            continue
        said = words_to_digits(texts[i])      # a rewrite may say "three" for "3": the figure follows the number
        kept = [f for f in c.figures if occurrence(words_to_digits(f.written), said)]
        rewrite = c.model_copy(update={"text": texts[i], "figures": kept})
        reasons = check_claim(rewrite, run.desk.match, run.store, run.moment.horizon)
        if reasons:
            failures[c.id] = (texts[i], reasons)
        else:
            candidates.append(rewrite)
    verdicts = await judge(run, candidates, mode="faithful", originals={c.id: c.text for c in claims})
    for rewrite in candidates:
        if verdicts[rewrite.id] is not None:
            failures[rewrite.id] = (rewrite.text, [verdicts[rewrite.id]])
    kept = {r.id: r.text for r in candidates if r.id not in failures}

    renders = [RenderedClaim(claim_id=c.id, persona=persona, language="en", text=kept.get(c.id, c.text),
                             note=None if c.id in kept else FALLBACK) for c in claims]
    rejections = [Rejection(claim_id=cid, text=text, layer="persona", reasons=reasons, attempt=0, persona=persona)
                  for cid, (text, reasons) in failures.items()]
    return renders, rejections


async def render_personas(run: MomentRun, claims: list[Claim]) -> tuple[list[RenderedClaim], list[Rejection]]:
    if not claims:
        return [], []
    renders, rejections = [], []
    for persona in run.desk.personas:
        if persona == "pundit":
            renders += _pundit(claims)
            continue
        r, rej = await _render(run, persona, claims)
        renders += r
        rejections += rej
    return renders, rejections
