"""The docs say what the code and the eval say: no dashes the user doesn't want, the README quotes the committed eval
word for word, and the video script fits the hackathon's two minutes."""

import re
from pathlib import Path

from jahbadh.eval.harness import EvalReport
from jahbadh.eval.report import to_markdown

ROOT = Path(__file__).resolve().parents[1]
DASHES = re.compile("[–—]")


def latest_report() -> EvalReport:
    """The newest dated eval run in the repo (a local pilot folder doesn't count)."""
    path = sorted(ROOT.glob("data/eval/20*/report.json"))[-1]
    return EvalReport.model_validate_json(path.read_text(encoding="utf-8"))


def test_no_em_or_en_dashes_in_the_docs():
    files = [ROOT / "README.md", ROOT / "web/src/state/labels.ts", *sorted((ROOT / "docs").glob("*.md"))]
    found = [f"{f.relative_to(ROOT)}:{n}" for f in files
             for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1) if DASHES.search(line)]
    assert found == []


def test_the_readme_quotes_the_eval_exactly():
    lines = to_markdown(latest_report()).splitlines()
    catch = next(line for line in lines if line.startswith("The Referee caught"))
    first = next(line for line in lines if line.startswith("Real first drafts"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert catch in readme and first in readme


def test_the_docs_count_what_the_eval_counted():
    report = latest_report()
    lines = to_markdown(report).splitlines()
    tainted = next(line for line in lines if "came from a draft the Referee also rejected" in line)
    claims = f"{report.numbers['matching']} of {report.numbers['checked']} published claims"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    submission = (ROOT / "docs/submission.md").read_text(encoding="utf-8")
    assert tainted in readme
    assert claims in readme and claims in submission
    assert "336 numbers" not in readme + submission


def test_the_video_script_fits_in_two_minutes():
    script = (ROOT / "docs/video-script.md").read_text(encoding="utf-8")
    seconds = [int(m) for m in re.findall(r"^\|\s*\d+\s*\|\s*(\d+)\s*\|", script, flags=re.MULTILINE)]
    assert len(seconds) >= 5 and sum(seconds) < 120
