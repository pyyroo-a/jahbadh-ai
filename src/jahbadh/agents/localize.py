"""Localization: Arabic and Spanish via Azure AI Translator, an LLM polish for football terms, and a
deterministic check that every number and name survived. No LLM judge reads Arabic or Spanish.

Only text is translated: claim ids and evidence never change. Fallbacks go polished, then raw, then English.
"""

import asyncio
import html
import re
from collections import Counter, defaultdict

from azure.ai.translation.text import TextTranslationClient
from azure.ai.translation.text.models import TranslateInputItem, TranslationTarget
from azure.core.credentials import AzureKeyCredential

from jahbadh.agents.config import Settings
from jahbadh.agents.contracts import Rejection, RenderedClaim, Rewrites
from jahbadh.agents.desk import MomentRun
from jahbadh.agents.llm import AgentOutputError, ask
from jahbadh.agents.numbers import numeric_tokens
from jahbadh.agents.prompts import polish_prompt
from jahbadh.agents.writers import no_em_dashes
from jahbadh.schemas import Match

TAG = re.compile(r"</?span[^>]*>")
MINUTE_MARK = re.compile(r"(?<![\d.])\d{1,2}['’]")
NUMBER_MARK = re.compile(r"(?<![\d.])\d+(?:\.\d+)?%?(?![\d.])")


class AzureTranslator:
    def __init__(self, settings: Settings):
        settings.require("translator_key", "translator_region")
        self.client = TextTranslationClient(endpoint=settings.translator_endpoint,
                                            credential=AzureKeyCredential(settings.translator_key.get_secret_value()),
                                            region=settings.translator_region)

    def translate(self, texts: list[str], to: str, keep: list[str]) -> list[str]:
        """Translate English texts in one request, with every keep term wrapped so Translator leaves it alone."""
        terms = sorted({html.escape(k, quote=False) for k in keep if k}, key=len, reverse=True)
        # minute marks and numbers too: live Spanish turned "61'" into "61 pies" (61 feet), and live Arabic
        # turned "5 goals" into number words, which fails the digit check
        pattern = re.compile("|".join([re.escape(t) for t in terms] + [MINUTE_MARK.pattern, NUMBER_MARK.pattern]))

        def protect(text: str) -> str:
            return pattern.sub(lambda m: f'<span class="notranslate">{m.group(0)}</span>', html.escape(text, quote=False))

        items = [TranslateInputItem(text=protect(t), language="en", text_type="html",
                                    targets=[TranslationTarget(language=to)]) for t in texts]
        result = self.client.translate(body=items)
        return [html.unescape(TAG.sub("", item.translations[0].text)) for item in result]


def keep_terms(match: Match) -> list[str]:
    """Names Translator must leave alone and the survival check looks for: full names, plus the short forms
    commentary actually uses (surnames like "Rasmus", team short names like "Rivermouth")."""
    teams = [match.meta.home, match.meta.away]
    players = [p for t in teams for p in t.players]
    terms = ([t.name for t in teams] + [t.id for t in teams] + [p.name for p in players]
             + [t.name.split()[0] for t in teams] + [p.name.split()[-1] for p in players])
    return list(dict.fromkeys(terms))


ARABIC_LETTER = re.compile(r"[\u0600-\u06FF]")
ENGLISH_WORD = re.compile(r"[A-Za-z]{4,}")


def _looks_untranslated(source: str, translated: str, keep: list[str]) -> bool:
    """Half or more of the source's real English words (names aside) still there means it wasn't translated."""
    def words(text: str) -> set[str]:
        for k in keep:
            text = text.replace(k, " ")
        return {w.lower() for w in ENGLISH_WORD.findall(text)}
    src = words(source)
    # with fewer than 3 content words a shared word like "total" decides it, so don't judge
    return len(src) >= 3 and len(src & words(translated)) / len(src) >= 0.5


def survives(source: str, translated: str, keep: list[str], language: str | None = None) -> list[str]:
    """Reasons the translation lost or changed something, or isn't in the target language at all.
    Numbers are compared after digit normalisation."""
    want, got = Counter(numeric_tokens(source)), Counter(numeric_tokens(translated))
    reasons = [f"number {n} missing" for n in (want - got).elements()]
    reasons += [f"extra number {n}" for n in (got - want).elements()]
    reasons += [f"name '{k}' missing" for k in keep if k in source and k not in translated]
    if language == "ar" and not ARABIC_LETTER.search(translated):
        reasons.append("not in Arabic")
    elif language and _looks_untranslated(source, translated, keep):
        reasons.append("looks untranslated")
    return reasons


async def _polish(run: MomentRun, language: str, sources: list[str], raw: list[str]) -> list[str] | None:
    try:
        texts = (await ask(run.desk.agent("polish"), polish_prompt(language, sources, raw), Rewrites)).texts
    except AgentOutputError:
        return None
    return [no_em_dashes(t) for t in texts] if len(texts) == len(raw) else None


async def localize(run: MomentRun, renders: list[RenderedClaim]) -> tuple[list[RenderedClaim], list[Rejection]]:
    english = [r for r in renders if r.language == "en"]
    languages = [lang for lang in run.desk.languages if lang != "en"]
    if not english or not languages:
        return [], []
    keep = keep_terms(run.desk.match)
    by_persona: dict[str, list[RenderedClaim]] = defaultdict(list)
    for r in english:
        by_persona[r.persona].append(r)

    out, rejections = [], []
    for language in languages:
        for persona, group in by_persona.items():
            sources = [r.text for r in group]
            try:
                raw = await asyncio.to_thread(run.desk.translator.translate, sources, language, keep)
            except Exception as e:  # throttling or an outage must not cost the English claims
                for r in group:
                    out.append(r.model_copy(update={"language": language, "note": "english fallback"}))
                    rejections.append(Rejection(claim_id=r.claim_id, text=r.text, layer="localization",
                                                reasons=[f"translator unavailable: {type(e).__name__}: {e}"],
                                                attempt=0, persona=persona, language=language))
                continue
            polished = await _polish(run, language, sources, raw)
            for i, r in enumerate(group):
                tried = []
                if polished is not None:
                    reasons = survives(r.text, polished[i], keep, language)
                    if not reasons:
                        out.append(r.model_copy(update={"language": language, "text": polished[i]}))
                        continue
                    tried.append(f"polished: {'; '.join(reasons)}")
                else:
                    tried.append("polish unavailable")
                reasons = survives(r.text, raw[i], keep, language)
                if not reasons:
                    out.append(r.model_copy(update={"language": language, "text": raw[i], "note": "raw translation"}))
                    text = polished[i] if polished is not None else raw[i]
                else:
                    tried.append(f"raw: {'; '.join(reasons)}")
                    out.append(r.model_copy(update={"language": language, "note": "english fallback"}))
                    text = raw[i]
                rejections.append(Rejection(claim_id=r.claim_id, text=text, layer="localization", reasons=tried,
                                            attempt=0, persona=persona, language=language))
    return out, rejections
