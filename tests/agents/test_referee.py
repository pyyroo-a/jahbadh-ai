import asyncio

from fakes import full_time_moment, grounded_claim, run_for
from jahbadh.agents.contracts import Claim, Verdict, Verdicts
from jahbadh.agents.grounding import check_claim
from jahbadh.agents.referee import judge, referee


def test_the_helper_claim_really_passes_layer_one():
    run, good = grounded_claim()
    assert check_claim(good, run.desk.match, run.store, run.moment.horizon) == []


def test_deterministic_failures_never_reach_the_llm():
    run = run_for({"referee": []}, moment=full_time_moment())
    bad = Claim(id="x:c1", text="They scored 99 goals.", metric_ids=[], event_ids=[], figures=[])
    approved, rejected = asyncio.run(referee(run, [bad], attempt=0))
    assert approved == [] and rejected[0].layer == "deterministic" and run.desk.client.calls == []
    assert rejected[0].reasons == ["no evidence cited", "unsupported number '99'"] and rejected[0].text == bad.text


def test_semantic_rejection_is_recorded():
    run, good = grounded_claim()
    run.desk.client.script["referee"] = [Verdicts(verdicts=[Verdict(claim_id=good.id, supported=False,
                                                                    reason="says wider, metric says narrower")])]
    approved, rejected = asyncio.run(referee(run, [good], attempt=1))
    assert approved == [] and rejected[0].layer == "semantic" and rejected[0].attempt == 1
    assert rejected[0].reasons == ["says wider, metric says narrower"]


def test_missing_verdict_fails_closed():
    run, good = grounded_claim()
    run.desk.client.script["referee"] = [Verdicts(verdicts=[])]
    approved, rejected = asyncio.run(referee(run, [good], attempt=0))
    assert approved == [] and rejected[0].reasons == ["referee gave no verdict"]


def test_referee_outage_fails_closed():
    run, good = grounded_claim()
    run.desk.client.script["referee"] = ["not json", "still not json"]
    assert asyncio.run(judge(run, [good])) == {good.id: "referee unavailable"}


def test_supported_claim_is_approved():
    run, good = grounded_claim()
    run.desk.client.script["referee"] = [Verdicts(verdicts=[Verdict(claim_id=good.id, supported=True, reason="ok")])]
    assert asyncio.run(referee(run, [good], attempt=0)) == ([good], [])


def test_judge_sees_the_claim_and_its_evidence():
    run, good = grounded_claim()
    run.desk.client.script["referee"] = [Verdicts(verdicts=[Verdict(claim_id=good.id, supported=True, reason="ok")])]
    asyncio.run(judge(run, [good]))
    _, texts, options = run.desk.client.calls[0]
    assert good.id in texts[-1] and good.text in texts[-1] and good.metric_ids[0] in texts[-1]
    assert "midfield control" in options["instructions"].lower() and not options.get("tools")


def test_faithful_mode_compares_against_the_original():
    run, good = grounded_claim()
    rewrite = good.model_copy(update={"text": "Northbridge FC lived in the final third."})
    run.desk.client.script["referee"] = [Verdicts(verdicts=[Verdict(claim_id=good.id, supported=True, reason="same")])]
    assert asyncio.run(judge(run, [rewrite], mode="faithful", originals={good.id: good.text})) == {good.id: None}
    prompt = run.desk.client.calls[0][1][-1]
    assert good.text in prompt and rewrite.text in prompt


def test_the_judge_checks_which_side_a_share_favours_and_that_words_fit_numbers():
    # showcase run: "Northbridge pinned Rivermouth back" was published with Northbridge's field tilt at 16%, and
    # "a high-quality chance (xG 0.19)" passed too; the numbers were right, the words were not
    from jahbadh.agents.prompts import INSTRUCTIONS
    judge, writer = INSTRUCTIONS["referee"], INSTRUCTIONS["writer"]
    for rule in ("below 50%", "pinning", "under 0.3 xG", "space or time", "quarter"):
        assert rule in judge
    for rule in ("below 50%", "under 0.3 xG"):
        assert rule in writer
