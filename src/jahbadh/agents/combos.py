"""Any persona and language for a moment that has already published, rendered only when someone asks.

Live mode publishes the pundit in English and renders other combos on demand. The re-checks run against the
moment's own metrics (restore_run), so a rewrite can only stand on numbers the Referee already approved.
"""

from dataclasses import replace

from jahbadh.agents.contracts import FeedItem, Language, Persona, Rejection, RenderedClaim
from jahbadh.agents.desk import Desk, MomentRun
from jahbadh.agents.evidence import EvidenceStore
from jahbadh.agents.localize import localize
from jahbadh.agents.persona import render_personas


def restore_run(desk: Desk, item: FeedItem) -> MomentRun:
    """A run for a published moment whose store holds exactly its metrics. No tools: nothing new is computed."""
    store = EvidenceStore(desk.match)
    for metric in item.metrics:
        store.add(metric)
    return MomentRun(desk=desk, moment=item.moment, store=store, tools={})


def _renders(item: FeedItem, persona: Persona, language: Language) -> list[RenderedClaim]:
    by_claim = {r.claim_id: r for r in item.renders if r.persona == persona and r.language == language}
    return [by_claim[c.id] for c in item.claims if c.id in by_claim]


def has_combo(item: FeedItem, persona: Persona, language: Language) -> bool:
    return len(_renders(item, persona, language)) == len(item.claims)


async def render_combo(desk: Desk, item: FeedItem, persona: Persona,
                       language: Language) -> tuple[list[RenderedClaim], list[Rejection]]:
    """Only the renders and rejections this combo adds: the persona in English if missing, then the translation."""
    if not item.claims or has_combo(item, persona, language):
        return [], []
    new: list[RenderedClaim] = []
    rejections: list[Rejection] = []
    english = _renders(item, persona, "en")
    if len(english) < len(item.claims):
        english, rejected = await render_personas(restore_run(replace(desk, personas=(persona,)), item), item.claims)
        new += english
        rejections += rejected
    if language != "en":
        localized, rejected = await localize(restore_run(replace(desk, languages=(language,)), item), english)
        new += localized
        rejections += rejected
    return new, rejections
