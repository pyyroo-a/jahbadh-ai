import asyncio

from fakes import FakeTranslator, grounded_claim
from jahbadh.agents.combos import has_combo, render_combo, restore_run
from jahbadh.agents.contracts import FeedItem, RenderedClaim, Rewrites, Verdict, Verdicts


def published(extra_renders=()):
    """A published full-time item: one grounded claim, its pundit/en render, the metric it stands on."""
    run, claim = grounded_claim(translator=FakeTranslator())
    renders = [RenderedClaim(claim_id=claim.id, persona="pundit", language="en", text=claim.text), *extra_renders]
    item = FeedItem(moment=run.moment, claims=[claim], renders=renders, rejections=[], metrics=run.store.metrics(),
                    stats={}, latency_s=0.0)
    run.desk.client.defaults["polish"] = Rewrites(texts=[])          # polish breaks: the raw translation is used
    return run.desk, item, claim


def roles(desk):
    return [c[0] for c in desk.client.calls]


def test_an_existing_combo_costs_nothing():
    desk, item, _ = published()
    assert asyncio.run(render_combo(desk, item, "pundit", "en")) == ([], []) and desk.client.calls == []
    assert has_combo(item, "pundit", "en") and not has_combo(item, "casual", "en")


def test_casual_spanish_renders_the_persona_then_translates_it():
    desk, item, claim = published()
    casual = f"Northbridge FC lived near goal: {claim.figures[0].written} of the final-third passes."
    desk.client.script["persona"] = [Rewrites(texts=[casual])]
    desk.client.script["referee"] = [Verdicts(verdicts=[Verdict(claim_id=claim.id, supported=True, reason="same")])]
    renders, rejections = asyncio.run(render_combo(desk, item, "casual", "es"))
    assert [(r.persona, r.language) for r in renders] == [("casual", "en"), ("casual", "es")]
    assert renders[0].text == casual and all(r.claim_id == claim.id for r in renders)
    assert desk.translator.calls[0][:2] == ([casual], "es")
    assert roles(desk) == ["persona", "referee", "polish"]
    assert [r.layer for r in rejections] == ["localization"]          # the raw translation is logged, as always


def test_pundit_arabic_only_translates():
    desk, item, claim = published()
    renders, _ = asyncio.run(render_combo(desk, item, "pundit", "ar"))
    assert [(r.persona, r.language) for r in renders] == [("pundit", "ar")]
    assert "persona" not in roles(desk) and desk.translator.calls[0][:2] == ([claim.text], "ar")


def test_a_persona_english_render_already_there_is_reused():
    desk, item, claim = published()
    item = item.model_copy(update={"renders": item.renders + [
        RenderedClaim(claim_id=claim.id, persona="casual", language="en", text="Casual words.")]})
    renders, _ = asyncio.run(render_combo(desk, item, "casual", "es"))
    assert [(r.persona, r.language) for r in renders] == [("casual", "es")]
    assert "persona" not in roles(desk) and desk.translator.calls[0][0] == ["Casual words."]


def test_a_rewrite_with_a_wrong_number_falls_back_to_the_pundit_line():
    desk, item, claim = published()
    desk.client.script["persona"] = [Rewrites(texts=["They had 99% of it, wow."])]
    renders, rejections = asyncio.run(render_combo(desk, item, "fantasy", "en"))
    assert renders[0].text == claim.text and renders[0].note == "persona fallback"
    assert rejections[0].layer == "persona" and rejections[0].reasons == ["unsupported number '99'"]


def test_no_claims_means_nothing_to_render():
    desk, item, _ = published()
    empty = item.model_copy(update={"claims": [], "renders": []})
    assert asyncio.run(render_combo(desk, empty, "casual", "ar")) == ([], []) and desk.client.calls == []


def test_restore_run_checks_against_the_items_own_metrics():
    desk, item, _ = published()
    run = restore_run(desk, item)
    assert [m.id for m in run.store.metrics()] == [m.id for m in item.metrics] and run.tools == {}
    assert run.moment == item.moment and run.desk is desk
