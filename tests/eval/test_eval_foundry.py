"""The Referee eval as Foundry rows and code-based checks (no model calls). Skipped where azure-ai-evaluation is
not installed (CI); install it with the `eval` extra."""

import json
from pathlib import Path

import pytest

pytest.importorskip("azure.ai.evaluation")

from jahbadh.eval import foundry  # noqa: E402
from jahbadh.eval.__main__ import main  # noqa: E402
from jahbadh.eval.harness import EvalReport  # noqa: E402
from jahbadh.eval.report import catch_summary  # noqa: E402

RUN = Path("data/eval/2026-10-19-referee")
ENDPOINT = "https://jahbadh-foundry.services.ai.azure.com/api/projects/jahbadh"


def committed() -> EvalReport:
    return EvalReport.model_validate_json((RUN / "report.json").read_text(encoding="utf-8"))


def test_rows_cover_every_plant_and_the_run():
    report = committed()
    rows = foundry.report_rows(report)
    plants = [r for r in rows if r["row"] == "plant"]
    runs = [r for r in rows if r["row"] == "run"]
    assert len(plants) == len(report.plants) == 47
    assert {(r["kind"], r["caught"], r["layer"]) for r in plants} == {(p.kind, p.caught, p.layer) for p in report.plants}
    assert runs == [{"row": "run", "passed_first": 196, "drafted": 442, "numbers_checked": 336,
                     "numbers_matching": 336, "latency_mean": 51.3}]


def test_evaluate_runs_the_code_checks_offline(tmp_path):
    report = committed()
    report.plants[0].caught = False                  # one miss, so the catch rate is not trivially 1
    data = foundry.write_rows(report, tmp_path)
    result = foundry.evaluate(data=str(data), evaluators=foundry.EVALUATORS, output_path=str(tmp_path / "result.json"))
    summary = catch_summary(report)
    metrics = result["metrics"]
    assert metrics["caught.caught"] == pytest.approx(summary["caught"] / summary["total"])
    assert metrics["first_draft.first_draft_rate"] == pytest.approx(196 / 442)
    assert metrics["numbers.numbers_matching_rate"] == pytest.approx(1.0)
    assert metrics["latency.latency_mean_s"] == pytest.approx(51.3)


def test_the_checks_skip_rows_without_their_columns():
    nan = float("nan")
    assert foundry.caught(caught=nan) == {}
    assert foundry.first_draft(passed_first=nan, drafted=nan) == {}
    assert foundry.caught(caught=True) == {"caught": 1.0}
    assert foundry.latency(latency_mean=51.3) == {"latency_mean_s": 51.3}


def test_upload_sends_the_rows_to_the_project(tmp_path, monkeypatch):
    seen = {}

    def fake_evaluate(**kw):
        seen.update(kw)
        return {"studio_url": "https://ai.azure.com/evaluation/123", "metrics": {}, "rows": []}

    monkeypatch.setattr(foundry, "evaluate", fake_evaluate)
    run = tmp_path / "2026-10-19-referee"
    run.mkdir()
    (run / "report.json").write_text((RUN / "report.json").read_text(encoding="utf-8"), encoding="utf-8")
    url = foundry.upload_to_foundry(run, ENDPOINT)
    assert url == "https://ai.azure.com/evaluation/123"
    assert seen["azure_ai_project"] == ENDPOINT and seen["evaluation_name"] == "jahbadh-referee-2026-10-19"
    assert set(seen["evaluators"]) == {"caught", "first_draft", "numbers", "latency"}
    rows = [json.loads(line) for line in Path(seen["data"]).read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 48


def test_the_cli_uploads_a_run(tmp_path, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(foundry, "upload_to_foundry", lambda d, p: calls.append((d, p)) or "https://ai.azure.com/x")
    assert main(["upload", str(RUN), "--project", ENDPOINT]) == 0
    assert calls == [(RUN, ENDPOINT)] and "https://ai.azure.com/x" in capsys.readouterr().out
