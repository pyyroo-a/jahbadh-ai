"""Showcase matches: a real, precomputed desk run that replay mode streams for free.

A showcase folder holds showcase.json (the seed and whether the demo storyline was on) and desk.json (the real
output of python -m jahbadh.agents, never edited by hand). No Parquet is committed: the simulator is seeded,
so the match is rebuilt from its seed, and the loader refuses a desk that doesn't fit the rebuilt match.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from jahbadh.agents.contracts import DeskRun
from jahbadh.analytics.base import MATCH_END
from jahbadh.schemas import Match
from jahbadh.simulator import simulate_match
from jahbadh.simulator.storyline import DEMO_STORYLINE

NOTE_FILE, DESK_FILE = "showcase.json", "desk.json"


class ShowcaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class Showcase:
    match: Match
    desk: DeskRun
    seed: int


def load_showcase(folder: Path) -> Showcase:
    folder = Path(folder)
    note = json.loads((folder / NOTE_FILE).read_text(encoding="utf-8"))
    desk = DeskRun.model_validate_json((folder / DESK_FILE).read_text(encoding="utf-8"))
    seed = int(note["seed"])
    match = simulate_match(seed, storyline=DEMO_STORYLINE if note.get("demo_storyline") else None)
    if desk.match_id != match.meta.match_id:
        raise ShowcaseError(f"{folder}: desk.json is for {desk.match_id}, seed {seed} gives {match.meta.match_id}")
    known = {e.id for e in match.events}
    for item in desk.items:
        if not 0 <= item.moment.t <= MATCH_END:
            raise ShowcaseError(f"{folder}: moment {item.moment.id} at t={item.moment.t:g} is outside the match")
        for claim in item.claims:
            missing = [e for e in claim.event_ids if e not in known]
            if missing:
                raise ShowcaseError(f"{folder}: claim {claim.id} cites events {missing} the match doesn't have")
    return Showcase(match=match, desk=desk, seed=seed)


def load_showcases(root: Path) -> dict[str, Showcase]:
    """Every complete showcase folder under root, keyed by match id. A broken one fails loudly."""
    root = Path(root)
    if not root.is_dir():
        return {}
    shows = [load_showcase(f) for f in sorted(root.iterdir())
             if (f / NOTE_FILE).is_file() and (f / DESK_FILE).is_file()]
    return {s.desk.match_id: s for s in shows}
