"""Guard: new simulated fields must never change a match.

fingerprints.json was recorded from the simulator before pass odds and shot speed existed (18 Oct, commit
77152cf), on Windows. Every event and tracking row must hash the same, with only the new detail keys left out.

Exact float bytes differ between platforms (the maths library can round the last binary digit differently), so
the exact check runs on Windows only, where it was recorded. portable_fingerprints.json (19 Oct, recorded from the
same unchanged simulator) holds two checks that must pass everywhere, the Linux deploy included:
  structure: every event's id, type, second, period, team, players and outcome, the score, and the tracking rows;
  micrometre: every number rounded to 6 decimals.
If structure ever differs on a platform, that platform plays a different match, and the showcase would not line up.
"""

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from jahbadh.schemas import Match
from jahbadh.simulator import simulate_match
from jahbadh.simulator.storyline import DEMO_STORYLINE

NEW_DETAIL_KEYS = {"p_success", "speed_kmh"}
FINGERPRINTS = Path(__file__).with_name("fingerprints.json")
PORTABLE = Path(__file__).with_name("portable_fingerprints.json")
SEEDS = {"42": True, "1": False, "7": False}       # seed -> demo storyline
DIGITS = 6


def _rounded(value, digits: int):
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, dict):
        return {k: _rounded(v, digits) for k, v in value.items()}
    if isinstance(value, list):
        return [_rounded(v, digits) for v in value]
    return value


def fingerprint(match: Match, digits: int | None = None) -> str:
    h = hashlib.sha256()
    for e in match.events:
        row = e.model_dump(mode="json")
        row["detail"] = {k: v for k, v in row["detail"].items() if k not in NEW_DETAIL_KEYS}
        h.update(json.dumps(row if digits is None else _rounded(row, digits), sort_keys=True).encode())
    tracking = match.tracking if digits is None else match.tracking.round({"x": digits, "y": digits})
    h.update(pd.util.hash_pandas_object(tracking, index=False).values.tobytes())
    return h.hexdigest()


def structure(match: Match) -> str:
    h = hashlib.sha256(json.dumps(match.meta.score, sort_keys=True).encode())
    for e in match.events:
        h.update(json.dumps([e.id, e.type, e.t, e.period, e.team_id, e.player_id, e.related_player_id, e.outcome]).encode())
    h.update(pd.util.hash_pandas_object(match.tracking[["t", "entity_id", "team_id"]], index=False).values.tobytes())
    return h.hexdigest()


def simulate(seed: str) -> Match:
    return simulate_match(int(seed), storyline=DEMO_STORYLINE if SEEDS[seed] else None)


@pytest.mark.skipif(sys.platform != "win32", reason="exact bytes were recorded on Windows; the portable checks run here")
@pytest.mark.parametrize("seed", SEEDS)
def test_matches_are_unchanged(seed):
    assert fingerprint(simulate(seed)) == json.loads(FINGERPRINTS.read_text())[seed]


@pytest.mark.parametrize("seed", SEEDS)
def test_matches_are_the_same_match_on_every_platform(seed):
    match, recorded = simulate(seed), json.loads(PORTABLE.read_text())[seed]
    assert structure(match) == recorded["structure"], "a different match: other events, ids or players"
    assert fingerprint(match, DIGITS) == recorded["micrometre"], "the same events, but numbers differ beyond 1e-6"
