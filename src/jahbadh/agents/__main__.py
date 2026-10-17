"""Run the desk over a saved match:

    python -m jahbadh.agents data/generated/match-042 [--limit N] [--personas pundit,casual,fantasy]
        [--languages en,ar,es] [--concurrency 3] [--no-spotlight] [--mermaid]

Writes MATCH_DIR/desk.json with every approved claim, render and rejection, and prints a summary.
"""

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path
from typing import get_args

from jahbadh.agents.config import MissingSetting, load_settings
from jahbadh.agents.contracts import Language, Persona
from jahbadh.agents.desk import Desk
from jahbadh.agents.llm import make_chat_client
from jahbadh.agents.localize import AzureTranslator
from jahbadh.agents.moments import detect_moments
from jahbadh.agents.pipeline import run_desk, workflow_mermaid
from jahbadh.agents.spotlight import spotlight_moments
from jahbadh.simulator.io import load_match


def _choices(raw: str, allowed: tuple[str, ...], what: str) -> tuple[str, ...]:
    picked = tuple(x.strip() for x in raw.split(",") if x.strip())
    unknown = [x for x in picked if x not in allowed]
    if unknown or not picked:
        raise ValueError(f"unknown {what}: {', '.join(unknown) or '(none)'}; pick from {', '.join(allowed)}")
    return picked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Jahbadh agent desk over a saved match.")
    parser.add_argument("match_dir", type=Path)
    parser.add_argument("--limit", type=int, help="only the earliest N moments (full time is always kept)")
    parser.add_argument("--personas", default="pundit,casual,fantasy")
    parser.add_argument("--languages", default="en,ar,es")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--no-spotlight", action="store_true", help="skip the player spotlights")
    parser.add_argument("--mermaid", action="store_true", help="print the per-moment workflow and exit")
    args = parser.parse_args(argv)

    try:
        personas = _choices(args.personas, get_args(Persona), "persona")
        languages = _choices(args.languages, get_args(Language), "language")
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    match = load_match(args.match_dir)
    if args.mermaid:
        print(workflow_mermaid(Desk(client=None, match=match)))
        return 0

    settings = load_settings()
    try:
        client = make_chat_client(settings)
        translator = AzureTranslator(settings) if any(lang != "en" for lang in languages) else None
    except MissingSetting as e:
        print(e, file=sys.stderr)
        return 2

    moments = detect_moments(match)
    if not args.no_spotlight:
        spotlights = spotlight_moments(match)
        moments = moments[:-1] + spotlights + moments[-1:]          # full time stays last
    if args.limit is not None:
        full_time = moments[-1]
        moments = moments[:args.limit] + ([full_time] if full_time not in moments[:args.limit] else [])

    desk = Desk(client=client, match=match, translator=translator, personas=personas, languages=languages,
                effort=settings.reasoning_effort)
    run = asyncio.run(run_desk(desk, moments, concurrency=args.concurrency))
    out = args.match_dir / "desk.json"
    out.write_text(run.model_dump_json(indent=2), encoding="utf-8")

    drafted = sum(i.stats["drafted"] for i in run.items)
    passed = sum(i.stats["passed_first"] for i in run.items)
    layers = Counter(r.layer for i in run.items for r in i.rejections)
    latency = sum(i.latency_s for i in run.items) / len(run.items) if run.items else 0.0
    print(f"{len(moments)} moments, {len(run.failures)} failed -> {out}")
    print(f"approved claims: {sum(len(i.claims) for i in run.items)}")
    print(f"first-draft pass rate: {passed}/{drafted}" + (f" ({passed / drafted:.0%})" if drafted else ""))
    print("rejections by layer: " + (", ".join(f"{k} {v}" for k, v in sorted(layers.items())) or "none"))
    print(f"mean latency per moment: {latency:.1f} s")
    for f in run.failures:
        print(f"failed {f.moment_id}: {f.error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
