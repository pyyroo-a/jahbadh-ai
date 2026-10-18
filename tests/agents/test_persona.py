import asyncio

from fakes import grounded_claim
from jahbadh.agents.contracts import Rewrites, Verdict, Verdicts
from jahbadh.agents.persona import render_personas


def test_pundit_is_free_and_casual_is_checked():
    run, good = grounded_claim(personas=("pundit", "casual"))
    pct = good.figures[0].written
    casual_text = f"Northbridge FC spent loads of time near goal: {pct} of the final-third passes."
    run.desk.client.script["persona"] = [Rewrites(texts=[casual_text])]
    run.desk.client.script["referee"] = [Verdicts(verdicts=[Verdict(claim_id=good.id, supported=True, reason="same")])]
    renders, rejected = asyncio.run(render_personas(run, [good]))
    assert [(r.persona, r.language, r.text, r.note) for r in renders] == \
        [("pundit", "en", good.text, None), ("casual", "en", casual_text, None)] and rejected == []
    roles = [c[0] for c in run.desk.client.calls]
    assert roles == ["persona", "referee"] and "casual" in run.desk.client.calls[0][1][-1]


def test_a_persona_may_drop_a_number_but_not_add_one():
    run, good = grounded_claim(personas=("pundit", "casual"))
    run.desk.client.script["persona"] = [Rewrites(texts=["Northbridge FC lived in the final third."])]
    run.desk.client.script["referee"] = [Verdicts(verdicts=[Verdict(claim_id=good.id, supported=True, reason="same")])]
    renders, rejected = asyncio.run(render_personas(run, [good]))
    assert renders[1].text == "Northbridge FC lived in the final third." and rejected == []


def test_new_number_falls_back_to_pundit():
    run, good = grounded_claim(personas=("pundit", "casual"))
    run.desk.client.script["persona"] = [Rewrites(texts=["They had 99% of it, wow."])]
    renders, rejected = asyncio.run(render_personas(run, [good]))
    casual = next(r for r in renders if r.persona == "casual")
    assert casual.text == good.text and casual.note == "persona fallback"
    assert rejected[0].layer == "persona" and rejected[0].persona == "casual"
    assert rejected[0].text == "They had 99% of it, wow." and rejected[0].reasons == ["unsupported number '99'"]


def test_unfaithful_rewrite_falls_back():
    run, good = grounded_claim(personas=("pundit", "fantasy"))
    run.desk.client.script["persona"] = [Rewrites(texts=["Northbridge FC dominated because of their captain."])]
    run.desk.client.script["referee"] = [Verdicts(verdicts=[Verdict(claim_id=good.id, supported=False, reason="adds a cause")])]
    renders, rejected = asyncio.run(render_personas(run, [good]))
    assert renders[1].note == "persona fallback" and rejected[0].reasons == ["adds a cause"]


def test_length_mismatch_falls_back():
    run, good = grounded_claim(personas=("pundit", "fantasy"))
    run.desk.client.script["persona"] = [Rewrites(texts=[])]
    renders, rejected = asyncio.run(render_personas(run, [good]))
    assert next(r for r in renders if r.persona == "fantasy").note == "persona fallback"
    assert rejected[0].persona == "fantasy"


def test_nothing_to_render_makes_no_calls():
    run, _ = grounded_claim(personas=("pundit", "casual"))
    assert asyncio.run(render_personas(run, [])) == ([], []) and run.desk.client.calls == []


def test_persona_lines_never_publish_em_dashes():
    run, good = grounded_claim(personas=("pundit", "casual"))
    pct = good.figures[0].written
    run.desk.client.script["persona"] = [Rewrites(texts=[f"Northbridge FC lived up there \u2014 {pct} of the final-third passes."])]
    run.desk.client.script["referee"] = [Verdicts(verdicts=[Verdict(claim_id=good.id, supported=True, reason="same")])]
    renders, _ = asyncio.run(render_personas(run, [good]))
    assert renders[1].text == f"Northbridge FC lived up there, {pct} of the final-third passes."


def test_faithful_mode_allows_plain_explanations_of_terms():
    # live run: 6 of 11 casual lines fell back because explaining "xG" counted as a new fact
    from jahbadh.agents.prompts import INSTRUCTIONS
    assert "explanation of a standard term" in INSTRUCTIONS["referee"]


def test_the_fantasy_style_reports_and_never_forecasts():
    # showcase run: 48 of 65 fantasy rewrites fell back, nearly all for adding forecasts like "will negatively
    # affect his fantasy output"; the faithful judge was right, so the style must stop asking for them
    from jahbadh.agents.prompts import PERSONA_STYLES, persona_prompt
    style = PERSONA_STYLES["fantasy"]
    assert "never predict" in style and "points" in style and "minutes" in style
    assert "never predict" in persona_prompt("fantasy", ["A line."])


def test_a_persona_may_write_a_number_as_a_word():
    # casual rewrites often turn "3 goals" into "three goals"; the figure must follow the word, not be dropped
    from jahbadh.agents.contracts import Figure
    from jahbadh.analytics import match_stats
    run, good = grounded_claim(personas=("pundit", "casual"))
    stats = run.store.add(match_stats(run.desk.match, "NBR"))
    goals = stats.data["goals"]
    good = good.model_copy(update={"text": f"Northbridge FC scored {goals} goals.", "metric_ids": [stats.id],
                                   "figures": [Figure(metric_id=stats.id, field="goals", written=str(goals))]})
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
    casual = f"Northbridge FC banged in {words[goals]} goals."
    run.desk.client.script["persona"] = [Rewrites(texts=[casual])]
    run.desk.client.script["referee"] = [Verdicts(verdicts=[Verdict(claim_id=good.id, supported=True, reason="same")])]
    renders, rejected = asyncio.run(render_personas(run, [good]))
    assert renders[1].text == casual and rejected == []
