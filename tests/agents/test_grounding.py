"""The Referee's first layer: pure Python, no LLM. Every id must exist, every number must match its metric at
the precision it is written, and minutes follow the broadcast rule."""

from fakes import demo_match, make_match, p
from jahbadh.agents.contracts import Claim, Figure
from jahbadh.agents.evidence import EvidenceStore, score_at
from jahbadh.agents.grounding import check_claim
from jahbadh.analytics import before_after, field_tilt
from jahbadh.schemas import EventType

TILT = "field_tilt:NBR:0-600"


def setup():
    m = make_match([p(1, "NBR", 80, t=100), p(2, "NBR", 80, t=200), p(3, "NBR", 80, t=300), p(4, "RMU", 20, t=400),
                    p(5, "NBR", 80, t=4000)])
    store = EvidenceStore(m)
    tilt = store.add(field_tilt(m, "NBR", 0, 600))      # 0.75, 3 of 4
    return m, store, tilt


def claim(text, figures=(), metric_ids=None, event_ids=()):
    return Claim(id="m:c1", text=text, metric_ids=[TILT] if metric_ids is None else metric_ids,
                 event_ids=list(event_ids), figures=list(figures))


def check(c, horizon=601.0):
    m, store, _ = setup()
    return check_claim(c, m, store, horizon)


def fig(written, field="value", metric_id=TILT):
    return Figure(metric_id=metric_id, field=field, written=written)


def test_good_claim_passes():
    assert check(claim("Northbridge had 75% of final-third passes, 3 of them theirs.", [fig("75%"), fig("3", "team_passes")])) == []


def test_wrong_number_is_rejected():
    assert check(claim("Northbridge had 80% of final-third passes.", [fig("80%")])) == \
        ["'80%' does not match field_tilt:NBR:0-600 value = 0.750"]


def test_number_without_figure_is_rejected():
    assert check(claim("Northbridge had 75% of it with 11 players.", [fig("75%")])) == ["unsupported number '11'"]


def test_figure_problems():
    assert check(claim("They had 75% of it.", [fig("75%", metric_id="ppda:NBR:0-600")])) == \
        ["figure cites ppda:NBR:0-600 which is not in the evidence"]          # one reason per bad number
    assert check(claim("They had 75% of it.", [fig("75%", field="nope")])) == [f"{TILT} has no field nope"]
    assert check(claim("They had most of it.", [fig("75%")])) == ["'75%' is not in the text"]


def test_a_figure_does_not_cover_a_longer_number():
    assert check(claim("They made 13 passes.", [fig("3", "team_passes")])) == \
        ["'3' is not in the text", "unsupported number '13'"]


def test_unknown_ids_and_future_events():
    r = check(claim("x", metric_ids=["ppda:NBR:0-1"], event_ids=[999, 5]))
    assert "unknown metric ppda:NBR:0-1" in r and "unknown event 999" in r and "event 5 is after this moment" in r


def test_no_evidence():
    assert check(claim("Big game.", metric_ids=[])) == ["no evidence cited"]


def test_minutes_follow_the_broadcast_rule():
    assert check(claim("Since 1' they have tilted it, up to 10'.")) == []                  # window 0-600 shows as 1'-10'
    assert check(claim("Their pass in 2' and the spell from 1'.", event_ids=[1])) == []    # event 1 is at t=100, so 2'
    off_by_one = claim("Their pass in 1' set it up.", metric_ids=[], event_ids=[1])
    assert check(off_by_one) == ["minute 1' is not backed by the evidence"]
    assert check(claim("It turned in the 10th minute.")) == []
    assert check(claim("It turned in minute 11.")) == ["minute 11' is not backed by the evidence"]


def test_durations_follow_cited_windows():
    m = demo_match()
    store = EvidenceStore(m)
    change = store.add(before_after(field_tilt, m, "RMU", at_t=3600))       # 15 minutes either side
    c = Claim(id="x:c1", text="In the 15 minutes after the switch their tilt moved, over 30 minutes in all.",
              metric_ids=[change.id], event_ids=[], figures=[])
    assert check_claim(c, m, store, 5400) == []
    bad = c.model_copy(update={"text": "In the 20 minutes after the switch their tilt moved."})
    assert check_claim(bad, m, store, 5400) == ["unsupported duration '20 minutes'"]


def test_formation_and_true_score_pass_but_a_wrong_score_fails():
    m = demo_match()
    store = EvidenceStore(m)
    switch = next(e for e in m.events if e.type == EventType.FORMATION_CHANGE)
    s = score_at(m, switch.t + 1)
    ok = Claim(id="x:c1", text=f"Rivermouth went to a 3-4-3 at 61' with the score at {s['NBR']}-{s['RMU']}.",
               metric_ids=[], event_ids=[switch.id], figures=[])
    assert check_claim(ok, m, store, switch.t + 1) == []
    wrong = ok.model_copy(update={"text": "Rivermouth went to a 3-4-3 at 61' with the score at 9-9."})
    assert check_claim(wrong, m, store, switch.t + 1) == ["unsupported number '9'", "unsupported number '9'"]
    made_up = ok.model_copy(update={"text": "Rivermouth went to a 5-3-2 at 61'."})
    assert check_claim(made_up, m, store, switch.t + 1) == \
        ["unsupported number '5'", "unsupported number '3'", "unsupported number '2'"]


def test_percent_only_for_shares():
    # live run: momentum's raw threat (away 0.61 xG of threat) was written as "61%" and passed
    from fakes import shot
    from jahbadh.analytics import momentum
    m = make_match([shot(1, "NBR", 0.2, t=100), shot(2, "RMU", 0.61, t=200)])
    store = EvidenceStore(m)
    mo = store.add(momentum(m, at_t=600))
    as_pct = Claim(id="m:c1", text="Rivermouth had 61% of the threat.", metric_ids=[mo.id], event_ids=[],
                   figures=[Figure(metric_id=mo.id, field="away", written="61%")])
    assert check_claim(as_pct, m, store, 601) == [f"'61%' is a percentage but {mo.id} away is not a share"]
    share = as_pct.model_copy(update={"text": "Northbridge had 25% of the threat.",
                                      "figures": [Figure(metric_id=mo.id, field="value", written="25%")]})
    assert check_claim(share, m, store, 601) == []
