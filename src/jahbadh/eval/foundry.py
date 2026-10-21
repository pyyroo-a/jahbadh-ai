"""The Referee eval in Foundry: the committed report as rows, scored by code-based checks (no model calls).

One row per planted claim (was it caught, and by which layer) and one row for the whole run (first drafts that
passed, figures re-checked, latency): the report keeps those as run totals, so that is what goes up. A row only
carries its own columns; the rest arrive as NaN, and each check skips a row without its columns, so every
metric is the mean over the rows it applies to.

    python -m jahbadh.eval upload data/eval/2026-10-19-referee --project https://<foundry>.services.ai.azure.com/api/projects/<project>

Needs the `eval` extra (azure-ai-evaluation) and `az login`. That package wants pandas below 3 while the app runs
pandas 3, so it lives in its own venv and never in the app's:

    python -m venv .venv-eval
    .venv-eval/Scripts/python -m pip install -e ".[eval]"
    .venv-eval/Scripts/python -m jahbadh.eval upload ...
"""

import json
import math
from pathlib import Path

from azure.ai.evaluation import evaluate

from jahbadh.eval.harness import EvalReport


def report_rows(report: EvalReport) -> list[dict]:
    plants = [{"row": "plant", "kind": p.kind, "caught": p.caught, "layer": p.layer} for p in report.plants]
    run = {"row": "run", "passed_first": report.first_draft["passed"], "drafted": report.first_draft["drafted"],
           "numbers_checked": report.numbers["checked"], "numbers_matching": report.numbers["matching"],
           "latency_mean": report.latency_s["mean"]}
    return plants + [run]


def write_rows(report: EvalReport, folder: Path) -> Path:
    path = folder / "rows.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in report_rows(report)) + "\n", encoding="utf-8")
    return path


def _given(*values) -> bool:
    """A column this row really has: missing ones come in as NaN (or None)."""
    return all(v is not None and not (isinstance(v, float) and math.isnan(v)) for v in values)


def caught(*, caught: bool | None = None) -> dict:
    return {"caught": 1.0 if caught else 0.0} if _given(caught) else {}


def first_draft(*, passed_first: int | None = None, drafted: int | None = None) -> dict:
    return {"first_draft_rate": passed_first / drafted} if _given(passed_first, drafted) and drafted else {}


def numbers(*, numbers_checked: int | None = None, numbers_matching: int | None = None) -> dict:
    if not (_given(numbers_checked, numbers_matching) and numbers_checked):
        return {}
    return {"numbers_matching_rate": numbers_matching / numbers_checked}


def latency(*, latency_mean: float | None = None) -> dict:
    return {"latency_mean_s": latency_mean} if _given(latency_mean) else {}


EVALUATORS = {"caught": caught, "first_draft": first_draft, "numbers": numbers, "latency": latency}


def upload_to_foundry(report_dir: Path, project_endpoint: str) -> str:
    """Score the run's rows and log them to the Foundry project; returns the link to the run in the portal."""
    report = EvalReport.model_validate_json((report_dir / "report.json").read_text(encoding="utf-8"))
    data = write_rows(report, report_dir)
    date = report_dir.name.removesuffix("-referee")
    result = evaluate(data=str(data), evaluators=EVALUATORS, evaluation_name=f"jahbadh-referee-{date}",
                      azure_ai_project=project_endpoint, output_path=str(report_dir / "foundry-result.json"))
    return result.get("studio_url") or "uploaded (Foundry gave no link)"
