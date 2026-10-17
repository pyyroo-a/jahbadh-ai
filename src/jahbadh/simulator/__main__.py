"""Generate a synthetic match: python -m jahbadh.simulator --seed 42 [--demo-storyline] [--out data/generated]"""

import argparse
from pathlib import Path

from jahbadh.simulator import simulate_match
from jahbadh.simulator.io import save_match
from jahbadh.simulator.storyline import DEMO_STORYLINE


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic Jahbadh match.")
    parser.add_argument("--seed", type=int, required=True, help="match seed (same seed, same match)")
    parser.add_argument("--demo-storyline", action="store_true", help="apply the scripted demo moments")
    parser.add_argument("--out", type=Path, default=Path("data/generated"), help="parent output folder")
    args = parser.parse_args()

    match = simulate_match(args.seed, storyline=DEMO_STORYLINE if args.demo_storyline else None)
    out_dir = args.out / match.meta.match_id
    save_match(match, out_dir)

    home, away = match.meta.home, match.meta.away
    print(f"{home.name} {match.meta.score[home.id]} - {match.meta.score[away.id]} {away.name}")
    print(f"{len(match.events)} events, {len(match.tracking)} tracking rows -> {out_dir}")


if __name__ == "__main__":
    main()
