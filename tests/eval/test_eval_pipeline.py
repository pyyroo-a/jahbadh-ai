import asyncio

from evalfakes import demo_match, full_time_moment, scripted_full_desk_client
from jahbadh.agents.contracts import Claim, Figure, Verdict, Verdicts
from jahbadh.agents.desk import Desk
from jahbadh.agents.pipeline import run_moment
from jahbadh.analytics import field_tilt

DEMO = demo_match()
PLANTED_ID = "full_time-5400:p1"


class StubPlanter:
    """Plants one claim citing NBR's real field tilt, written right or wrong."""

    def __init__(self, written_wrong: bool):
        self.written_wrong, self.recorded = written_wrong, []

    def __call__(self, run, drafts):
        tilt = run.store.add(field_tilt(run.desk.match, "NBR"))
        pct = f"{round(tilt.value * 100) + (15 if self.written_wrong else 0)}%"
        return [Claim(id=PLANTED_ID, text=f"Rivermouth United had {pct} of the final-third passes.",
                      metric_ids=[tilt.id], event_ids=[], figures=[Figure(metric_id=tilt.id, field="value", written=pct)])]

    def is_planted(self, claim_id):
        return claim_id == PLANTED_ID

    def record(self, claim, rejection):
        self.recorded.append((claim.id, rejection))


def run_with(planter, judge_approves=False):
    client = scripted_full_desk_client()
    if judge_approves:
        client.defaults["referee"] = Verdicts(verdicts=[Verdict(claim_id=PLANTED_ID, supported=True, reason="")])
    desk = Desk(client=client, match=DEMO, planter=planter)
    return asyncio.run(run_moment(desk, full_time_moment())), client


def test_a_planted_wrong_number_is_caught_by_layer_one_and_never_published():
    planter = StubPlanter(written_wrong=True)
    item, client = run_with(planter)
    [(cid, rejection)] = planter.recorded
    assert cid == PLANTED_ID and rejection is not None and rejection.layer == "deterministic"
    assert all(c.id != PLANTED_ID for c in item.claims)
    assert all(r.claim_id != PLANTED_ID for r in item.rejections)
    assert [role for role, *_ in client.calls].count("writer") == 1           # never sent back for a rewrite


def test_a_planted_claim_the_referee_misses_is_counted_and_never_published():
    planter = StubPlanter(written_wrong=False)
    item, client = run_with(planter, judge_approves=True)
    [(cid, rejection)] = planter.recorded
    assert cid == PLANTED_ID and rejection is None
    assert all(c.id != PLANTED_ID for c in item.claims)
    assert all(r.claim_id != PLANTED_ID for r in item.renders)
    assert [role for role, *_ in client.calls].count("referee") == 1          # the judge did see it


def test_planted_claims_stay_out_of_the_first_draft_stats():
    item, _ = run_with(StubPlanter(written_wrong=False), judge_approves=True)
    assert item.stats["drafted"] == 0 and item.stats["passed_first"] == 0


def test_no_planter_means_the_desk_is_unchanged():
    item, client = run_with(None)
    assert Desk(client=None, match=DEMO).planter is None
    assert item.claims == [] and item.rejections == [] and item.stats["drafted"] == 0
