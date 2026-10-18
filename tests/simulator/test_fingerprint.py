"""Guard: new simulated fields must never change a match.

fingerprints.json was recorded from the simulator before pass odds and shot speed existed (18 Oct, commit
77152cf). Every event and tracking row must hash the same, with only the new detail keys left out.
"""

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from jahbadh.schemas import Match
from jahbadh.simulator import simulate_match
from jahbadh.simulator.storyline import DEMO_STORYLINE

NEW_DETAIL_KEYS = {"p_success", "speed_kmh"}
FINGERPRINTS = Path(__file__).with_name("fingerprints.json")
SEEDS = {"42": True, "1": False, "7": False}       # seed -> demo storyline


def fingerprint(match: Match) -> str:
    h = hashlib.sha256()
    for e in match.events:
        row = e.model_dump(mode="json")
        row["detail"] = {k: v for k, v in row["detail"].items() if k not in NEW_DETAIL_KEYS}
        h.update(json.dumps(row, sort_keys=True).encode())
    h.update(pd.util.hash_pandas_object(match.tracking, index=False).values.tobytes())
    return h.hexdigest()


def simulate(seed: str) -> Match:
    return simulate_match(int(seed), storyline=DEMO_STORYLINE if SEEDS[seed] else None)


@pytest.mark.parametrize("seed", SEEDS)
def test_matches_are_unchanged(seed):
    assert fingerprint(simulate(seed)) == json.loads(FINGERPRINTS.read_text())[seed]
