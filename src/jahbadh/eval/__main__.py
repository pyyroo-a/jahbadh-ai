"""python -m jahbadh.eval: the Referee eval.

    python -m jahbadh.eval --seeds 1-20 --plants 50 --dry          what would run, no model calls
    python -m jahbadh.eval --seeds 1-20 --plants 50 --limit-matches 1 --out data/eval/pilot
    python -m jahbadh.eval --seeds 1-20 --plants 50 --out data/eval/2026-10-20-referee
    python -m jahbadh.eval showcase                                   today's number check on the showcase (free)

Anything without --dry calls the model and costs money.
"""

import argparse
import asyncio
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from jahbadh.agents.config import MissingSetting, load_settings
from jahbadh.agents.desk import Desk
from jahbadh.agents.llm import make_chat_client
from jahbadh.api.live import key_moments
from jahbadh.api.showcase import load_showcases
from jahbadh.eval.harness import TokenMeter, recheck_showcase, run_eval
from jahbadh.eval.plant import schedule_plants
from jahbadh.eval.report import catch_summary, to_markdown
from jahbadh.simulator import simulate_match

SHOWCASE_ROOT = Path("data/showcase")


def parse_seeds(text: str) -> list[int]:
    """"1-20" or "1,3,7"."""
    if "-" in text:
        a, b = text.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in text.split(",") if x]


def _showcase() -> int:
    result = recheck_showcase(load_showcases(SHOWCASE_ROOT)["match-042"])
    print(f"showcase: {result['published']} published claims, {result['would_fail']} would fail today's number check")
    for cid, reasons in result["failing"]:
        print(f"  {cid}: {'; '.join(reasons)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["showcase"]:
        return _showcase()
    parser = argparse.ArgumentParser(description="Measure the Referee with planted false claims.")
    parser.add_argument("--seeds", default="1-20")
    parser.add_argument("--plants", type=int, default=50)
    parser.add_argument("--limit-matches", type=int)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--out", type=Path, default=Path("data/eval") / f"{date.today().isoformat()}-referee")
    parser.add_argument("--dry", action="store_true", help="say what would run, with no model calls")
    args = parser.parse_args(argv)
    seeds = parse_seeds(args.seeds)
    run_seeds = seeds[:args.limit_matches] if args.limit_matches else seeds

    if args.dry:
        moments = {s: key_moments(simulate_match(s)) for s in seeds}
        schedule = schedule_plants(moments, args.plants)
        kinds = Counter(k for s in run_seeds for k in schedule[s].values())
        print(f"{len(run_seeds)} match{'' if len(run_seeds) == 1 else 'es'}, {sum(len(moments[s]) for s in run_seeds)} key moments, "
              f"{sum(kinds.values())} planted claims ({', '.join(f'{k} {v}' for k, v in sorted(kinds.items()))})")
        return 0

    try:
        settings = load_settings()
        settings.require("foundry_api_key")
    except MissingSetting as e:
        print(e, file=sys.stderr)
        return 2
    meter = TokenMeter()

    def desk_for(match, planter):
        return Desk(client=make_chat_client(settings, http_client=meter.client()), match=match,
                    personas=("pundit",), languages=("en",), effort=settings.reasoning_effort, planter=planter)

    report = asyncio.run(run_eval(seeds, desk_for, args.plants, args.concurrency, run_seeds))
    report.tokens = dict(meter.totals)
    report.showcase = recheck_showcase(load_showcases(SHOWCASE_ROOT)["match-042"])
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (args.out / "report.md").write_text(to_markdown(report), encoding="utf-8")
    s = catch_summary(report)
    print(f"caught {s['caught']} of {s['total']} planted claims; first drafts {report.first_draft['passed']}"
          f"/{report.first_draft['drafted']}; failed moments {report.failures}; tokens {report.tokens} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
