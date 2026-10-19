import asyncio
import json

import httpx2

from evalfakes import SHOWCASE_ROOT, scripted_full_desk_client
from jahbadh.agents.contracts import Verdicts
from jahbadh.agents.desk import Desk
from jahbadh.api.showcase import load_showcases
from jahbadh.eval import __main__ as cli
from jahbadh.eval.harness import EvalReport, TokenMeter, recheck_showcase, run_eval
from jahbadh.eval.plant import PlantResult
from jahbadh.eval.report import catch_summary, to_markdown


def plant(n: int, caught: bool, kind="wrong_number", layer="deterministic") -> PlantResult:
    return PlantResult(seed=1 + n % 20, moment_id=f"goal-{n}", claim_id=f"goal-{n}:p1", kind=kind, source_claim_id=None,
                       text="x", caught=caught, source_rejected=False, layer=layer if caught else None, reasons=["r"] if caught else [])


def report_with(caught: int, total: int, matches: int = 20) -> EvalReport:
    return EvalReport(seeds=list(range(1, matches + 1)), model="gpt-5-mini", created="2026-10-19T00:00:00+00:00",
                      moments=240, failures=0, first_draft={"passed": 120, "drafted": 230},
                      rejections_by_layer={"deterministic": 60, "semantic": 50},
                      plants=[plant(n, n < caught) for n in range(total)], plants_planned=total, unplaced=[],
                      numbers={"checked": 300, "matching": 296},
                      latency_s={"mean": 98.0, "p50": 95.0, "p90": 130.0, "max": 160.0}, tokens=None, showcase=None)


def test_the_markdown_leads_with_the_catch_line():
    md = to_markdown(report_with(caught=47, total=50))
    first = next(line for line in md.splitlines() if line and not line.startswith("#"))
    assert first == "The Referee caught 47 of 50 planted false claims across 20 matches."


def test_the_markdown_shows_the_first_draft_rate_next_to_it():
    md = to_markdown(report_with(caught=47, total=50))
    assert "Real first drafts that passed the Referee unchanged: 120 of 230 (52%)." in md
    assert "—" not in md and "–" not in md


def test_the_catch_summary_splits_by_kind_and_layer():
    s = catch_summary(report_with(caught=3, total=5))
    assert s["caught"] == 3 and s["total"] == 5
    assert s["by_kind"]["wrong_number"] == {"caught": 3, "total": 5} and s["by_layer"] == {"deterministic": 3}


def test_a_scripted_eval_runs_end_to_end():
    def desk_for(match, planter):
        client = scripted_full_desk_client()
        client.defaults["referee"] = Verdicts(verdicts=[])       # no verdict: the judge fails closed
        return Desk(client=client, match=match, planter=planter)

    report = asyncio.run(run_eval([1], desk_for, total_plants=3))
    assert report.seeds == [1] and report.failures == 0 and report.moments > 0
    assert report.plants_planned == 3
    # empty drafts leave only the made-up event to plant; the other two kinds are reported as unplaced
    assert [p.kind for p in report.plants] == ["made_up_event"] and report.plants[0].caught
    assert sorted(report.unplaced) == ["wrong_minute", "wrong_number"]


def test_the_meter_counts_tokens_from_responses_api_replies():
    meter = TokenMeter()
    usage = {"usage": {"input_tokens": 10, "output_tokens": 5, "output_tokens_details": {"reasoning_tokens": 3}}}

    async def go():
        async with meter.client(transport=httpx2.MockTransport(lambda r: httpx2.Response(200, json=usage))) as c:
            await c.post("https://example.test/openai/v1/responses", json={})
            await c.post("https://example.test/openai/v1/responses", json={})

    asyncio.run(go())
    assert meter.totals == {"calls": 2, "input": 20, "output": 10, "reasoning": 6}


def test_dry_run_makes_no_model_call(capsys, monkeypatch):
    monkeypatch.setattr(cli, "make_chat_client", lambda *a, **k: (_ for _ in ()).throw(AssertionError("model")))
    assert cli.main(["--seeds", "1-2", "--plants", "5", "--dry"]) == 0
    out = capsys.readouterr().out
    assert "2 matches" in out and "5 planted claims" in out


def test_the_showcase_recheck_counts_todays_layer_one_failures():
    result = recheck_showcase(load_showcases(SHOWCASE_ROOT)["match-042"])
    assert result["published"] == 66 and result["would_fail"] == 17            # measured 19 Oct, as in Plan 3
    assert len(result["failing"]) == 17
    json.dumps(result)


def test_the_markdown_says_when_a_catch_came_with_a_rejected_source_draft():
    report = report_with(caught=3, total=5)
    report.plants[0] = report.plants[0].model_copy(update={"source_rejected": True})
    assert "1 of the 3 caught claims came from a draft the Referee also rejected in the same check." in to_markdown(report)
