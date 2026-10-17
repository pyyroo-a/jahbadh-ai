import asyncio

from fakes import full_time_moment, run_for
from jahbadh.agents.contracts import Claim, ClaimDraft, Draft, Figure, Finding, Moment
from jahbadh.agents.writers import kind_for, rewrite, write
from jahbadh.analytics import before_after, shape

WIDTH_CHANGE = "width_change:RMU:2700-4500:at=3600:window=900"
CLAIM = ClaimDraft(text="Rivermouth have gone 12.5 metres wider since 61'.", metric_ids=[WIDTH_CHANGE], event_ids=[975],
                   figures=[Figure(metric_id=WIDTH_CHANGE, field="value", written="12.5")])


def ft_run(script):
    run = run_for(script, moment=full_time_moment())
    run.store.add(before_after(shape, run.desk.match, "RMU", at_t=3600, value_key="width"))
    return run


def test_write_assigns_ids_and_shows_fields():
    run = ft_run({"writer": [Draft(claims=[CLAIM, CLAIM])]})
    finding = Finding(text="wider", metric_ids=[WIDTH_CHANGE], event_ids=[975])
    claims = asyncio.run(write(run, [finding]))
    assert [c.id for c in claims] == ["full_time-5400:c1", "full_time-5400:c2"]
    assert claims[0].model_dump(exclude={"id"}) == CLAIM.model_dump()
    _, texts, options = run.desk.client.calls[0]
    assert '"before.value"' in texts[-1] and "wider" in texts[-1] and "#975 61'" in texts[-1]
    assert not options.get("tools")                                    # writers get no tools


def test_writer_instructions_carry_the_claim_rules():
    run = ft_run({"writer": [Draft(claims=[])]})
    assert asyncio.run(write(run, [])) == []
    instructions = run.desk.client.calls[0][2]["instructions"]
    assert "figures" in instructions and "written" in instructions and "broadcast minute" in instructions
    assert "recap" in run.desk.client.calls[0][1][-1]                  # full time asks for a recap


def test_rewrite_keeps_ids_by_position():
    run = ft_run({"writer": [Draft(claims=[CLAIM, CLAIM])]})             # an extra claim is ignored
    old = Claim(id="full_time-5400:c2", **CLAIM.model_dump())
    out = asyncio.run(rewrite(run, [(old, ["unsupported number '13'"])], []))
    assert [c.id for c in out] == ["full_time-5400:c2"]
    assert "unsupported number '13'" in run.desk.client.calls[0][1][-1]


def test_rewrite_with_fewer_claims_returns_fewer():
    run = ft_run({"writer": [Draft(claims=[])]})
    old = Claim(id="full_time-5400:c1", **CLAIM.model_dump())
    assert asyncio.run(rewrite(run, [(old, ["nope"])], [])) == []


def test_kind_for():
    assert kind_for(Moment(id="x", kind="full_time", t=5400, label="FT")) == "recap"
    assert kind_for(Moment(id="x", kind="spotlight", t=5400, player_id="RMU-33", label="S")) == "spotlight"
    assert kind_for(Moment(id="x", kind="goal", t=900, label="G")) == "commentary"
