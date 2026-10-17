import asyncio

import pytest
from azure.ai.translation.text.models import TranslatedTextItem, TranslationText

from fakes import FakeTranslator, demo_match, grounded_claim
from jahbadh.agents.config import MissingSetting, Settings
from jahbadh.agents.contracts import RenderedClaim, Rewrites
from jahbadh.agents.localize import AzureTranslator, keep_terms, localize, survives


def en(claim, persona="pundit"):
    return RenderedClaim(claim_id=claim.id, persona=persona, language="en", text=claim.text)


def test_survives_accepts_arabic_digits_and_spanish_commas():
    assert survives("Field tilt 79% and 0.79 xG for Northbridge FC", "ميل الملعب ٧٩٪ و ٠٫٧٩ لـ Northbridge FC",
                    ["Northbridge FC"]) == []
    assert survives("0.79 xG", "0,79 xG", []) == []
    assert survives("Rivermouth went to a 3-4-3", "ريفرماوث 3-4-3", []) == []


def test_survives_catches_changed_numbers_and_lost_names():
    r = survives("Northbridge FC had 79%", "Puente Norte tuvo 80%", ["Northbridge FC"])
    assert r == ["number 79 missing", "extra number 80", "name 'Northbridge FC' missing"]


def test_keep_terms_cover_teams_and_players():
    m = demo_match()
    terms = keep_terms(m)
    assert {"Northbridge FC", "Rivermouth United", "NBR", "RMU"} <= set(terms)
    assert all(p.name in terms for t in (m.meta.home, m.meta.away) for p in t.players)


def test_polished_translation_is_used_when_it_survives():
    run, good = grounded_claim(languages=("en", "ar"), translator=FakeTranslator())
    run.desk.client.script["polish"] = [Rewrites(texts=[f"[ar*] {good.text}"])]
    renders, rejected = asyncio.run(localize(run, [en(good)]))
    assert [(r.language, r.text, r.note) for r in renders] == [("ar", f"[ar*] {good.text}", None)] and rejected == []
    assert "Arabic" in run.desk.client.calls[0][1][-1] and f"[ar] {good.text}" in run.desk.client.calls[0][1][-1]


def test_raw_translation_when_polish_breaks_a_number():
    run, good = grounded_claim(languages=("en", "es"), translator=FakeTranslator())
    run.desk.client.script["polish"] = [Rewrites(texts=["Northbridge FC tuvo 99% de los pases."])]
    renders, rejected = asyncio.run(localize(run, [en(good)]))
    assert renders[0].text == f"[es] {good.text}" and renders[0].note == "raw translation"
    assert rejected[0].language == "es" and any("99" in r for r in rejected[0].reasons)


def test_falls_back_to_raw_then_english():
    run, good = grounded_claim(languages=("en", "es"), translator=FakeTranslator(mangle=lambda t: "sin numeros"))
    run.desk.client.script["polish"] = [Rewrites(texts=["tampoco"])]
    renders, rejected = asyncio.run(localize(run, [en(good)]))
    assert renders[0].text == good.text and renders[0].note == "english fallback"
    assert len(rejected) == 1 and rejected[0].layer == "localization" and rejected[0].language == "es"


def test_every_persona_and_language_is_rendered():
    run, good = grounded_claim(languages=("en", "ar", "es"), translator=FakeTranslator())
    run.desk.client.defaults["polish"] = Rewrites(texts=[])          # length mismatch: raw translation is used
    renders, _ = asyncio.run(localize(run, [en(good), en(good, "casual")]))
    assert sorted((r.persona, r.language) for r in renders) == \
        [("casual", "ar"), ("casual", "es"), ("pundit", "ar"), ("pundit", "es")]
    assert all(r.claim_id == good.id for r in renders)


def test_names_are_sent_as_keep_terms():
    t = FakeTranslator()
    run, good = grounded_claim(languages=("en", "ar"), translator=t)
    run.desk.client.script["polish"] = [Rewrites(texts=[f"[ar] {good.text}"])]
    asyncio.run(localize(run, [en(good)]))
    assert t.calls[0][1] == "ar" and "Northbridge FC" in t.calls[0][2]


def test_english_only_makes_no_calls():
    t = FakeTranslator()
    run, good = grounded_claim(languages=("en",), translator=t)
    assert asyncio.run(localize(run, [en(good)])) == ([], []) and t.calls == [] and run.desk.client.calls == []


def test_azure_translator_wraps_names_in_notranslate(monkeypatch):
    sent = []
    tr = AzureTranslator(Settings(translator_key="k", translator_region="uaenorth"))
    reply = [TranslatedTextItem(translations=[TranslationText(language="es",
                                                              text='<span class="notranslate">Northbridge FC</span> ganó &amp; más')])]
    monkeypatch.setattr(tr.client, "translate", lambda body: sent.extend(body) or reply)
    assert tr.translate(["Northbridge FC won & more"], "es", ["Northbridge FC"]) == ["Northbridge FC ganó & más"]
    assert sent[0].text_type == "html" and sent[0].language == "en" and sent[0].targets[0].language == "es"
    assert sent[0].text == '<span class="notranslate">Northbridge FC</span> won &amp; more'


def test_azure_translator_protects_minute_marks(monkeypatch):
    # live Spanish turned "by 61'" into "a 61 pies" (61 feet): minute marks must not be translated
    sent = []
    tr = AzureTranslator(Settings(translator_key="k", translator_region="uaenorth"))
    monkeypatch.setattr(tr.client, "translate", lambda body: sent.extend(body) or [
        TranslatedTextItem(translations=[TranslationText(language="es", text="x")])])
    tr.translate(["They scored by 61' and 7.5 xG."], "es", [])
    assert sent[0].text == "They scored by <span class=\"notranslate\">61'</span> and 7.5 xG."


def test_azure_translator_needs_key_and_region():
    with pytest.raises(MissingSetting, match="TRANSLATOR_KEY"):
        AzureTranslator(Settings(translator_region="uaenorth"))
