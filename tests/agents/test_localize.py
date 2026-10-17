import asyncio

import pytest
from azure.ai.translation.text.models import TranslatedTextItem, TranslationText

from fakes import FakeTranslator, demo_match, fake_translation, grounded_claim
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
    raw = fake_translation(good.text, "ar", keep_terms(run.desk.match))
    polished = raw + " تم"
    run.desk.client.script["polish"] = [Rewrites(texts=[polished])]
    renders, rejected = asyncio.run(localize(run, [en(good)]))
    assert [(r.language, r.text, r.note) for r in renders] == [("ar", polished, None)] and rejected == []
    assert "Arabic" in run.desk.client.calls[0][1][-1] and raw in run.desk.client.calls[0][1][-1]


def test_raw_translation_when_polish_breaks_a_number():
    run, good = grounded_claim(languages=("en", "es"), translator=FakeTranslator())
    run.desk.client.script["polish"] = [Rewrites(texts=["Northbridge FC tuvo 99% de los pases."])]
    renders, rejected = asyncio.run(localize(run, [en(good)]))
    assert renders[0].text == fake_translation(good.text, "es", keep_terms(run.desk.match))
    assert renders[0].note == "raw translation"
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
    assert sent[0].text == ("They scored by <span class=\"notranslate\">61'</span> and "
                            "<span class=\"notranslate\">7.5</span> xG.")


def test_azure_translator_needs_key_and_region():
    with pytest.raises(MissingSetting, match="TRANSLATOR_KEY"):
        AzureTranslator(Settings(translator_region="uaenorth"))


def test_untranslated_output_is_caught():
    # live run: 4 of 22 Arabic lines were really English, because the polish pass sometimes answered in English
    src = "Rivermouth full back Tomas Lindqvist committed a foul in his defensive third and was booked."
    english = "Rivermouth full back Tomas Lindqvist was booked for a foul in his defensive third."
    assert "not in Arabic" in survives(src, english, ["Tomas Lindqvist"], "ar")
    assert "looks untranslated" in survives(src, english, ["Tomas Lindqvist"], "es")


def test_real_translations_pass_the_language_check():
    src = "Northbridge FC had 79% of the final-third passes and 1.13 xG by 61'."
    es = "Northbridge FC tuvo el 79% de los pases en el último tercio y 1,13 xG por 61'."
    ar = ("Northbridge FC سجل 79٪ من التمريرات "
          "و1.13 xG بحلول 61'.")
    assert survives(src, es, ["Northbridge FC"], "es") == [] and survives(src, ar, ["Northbridge FC"], "ar") == []


def test_english_polish_falls_back_to_the_raw_translation():
    run, good = grounded_claim(languages=("en", "ar"), translator=FakeTranslator())
    run.desk.client.script["polish"] = [Rewrites(texts=[good.text])]
    renders, rejected = asyncio.run(localize(run, [en(good)]))
    assert renders[0].note == "raw translation" and "not in Arabic" in "; ".join(rejected[0].reasons)


def test_azure_translator_keeps_numbers_as_digits(monkeypatch):
    # live run: "1 ball win" and "5 goals" came back as Arabic number words, so good lines fell back to English
    sent = []
    tr = AzureTranslator(Settings(translator_key="k", translator_region="uaenorth"))
    monkeypatch.setattr(tr.client, "translate", lambda body: sent.extend(body) or [
        TranslatedTextItem(translations=[TranslationText(language="ar", text="x")])])
    tr.translate(["He had 1 ball win, 5 goals and 79% completion."], "ar", [])
    assert sent[0].text == ('He had <span class="notranslate">1</span> ball win, <span class="notranslate">5</span> '
                            'goals and <span class="notranslate">79%</span> completion.')


def test_a_translator_outage_keeps_english_and_logs_it():
    # final review: F0 throttling raised out of localize and failed the moment, English claims included
    def down(text):
        raise RuntimeError("429 too many requests")
    run, good = grounded_claim(languages=("en", "ar"), translator=FakeTranslator(mangle=down))
    renders, rejected = asyncio.run(localize(run, [en(good)]))
    assert [(r.language, r.text, r.note) for r in renders] == [("ar", good.text, "english fallback")]
    assert rejected[0].reasons == ["translator unavailable: RuntimeError: 429 too many requests"]
    assert run.desk.client.calls == []                                   # no polish call for nothing


def test_short_names_are_protected_and_checked():
    # final review: commentary says "Rasmus" and "Rivermouth", which were neither protected nor checked
    m = demo_match()
    terms = keep_terms(m)
    assert {"Rasmus", "Rivermouth", "Northbridge"} <= set(terms)
    assert survives("Rasmus had 1.13 xG in total.", "Rasmus tuvo 1,13 xG en total.", terms, "es") == []
    assert "name 'Rasmus' missing" in survives("Rasmus scored 1.13 xG.", "\u0631\u0627\u0633\u0645\u0648\u0633 1.13 xG", terms, "ar")
