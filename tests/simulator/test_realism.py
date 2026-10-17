"""Simulated matches should look like top-flight football, statistically."""

from collections import Counter

import pytest

from jahbadh.schemas import EventType, Match
from jahbadh.simulator import simulate_match

RANGES = {
    "passes": (700, 1150), "pass_completion": (0.74, 0.90), "shots": (14, 36),
    "xg_total": (1.4, 4.8), "goals": (0, 8), "fouls": (12, 35), "cards": (0, 9),
    "events_total": (1400, 2800),
}
SEEDS = [1, 2, 3, 4, 5]


def match_summary(m: Match) -> dict[str, float]:
    counts = Counter(e.type for e in m.events)
    passes = m.events_of(EventType.PASS)
    return {
        "passes": len(passes),
        "pass_completion": sum(bool(e.outcome) for e in passes) / max(len(passes), 1),
        "shots": counts[EventType.SHOT],
        "xg_total": sum(e.xg for e in m.events_of(EventType.SHOT)),
        "goals": counts[EventType.GOAL],
        "fouls": counts[EventType.FOUL],
        "cards": counts[EventType.CARD],
        "events_total": len(m.events),
    }


@pytest.fixture(scope="module")
def matches() -> dict[int, Match]:
    return {seed: simulate_match(seed) for seed in SEEDS}


@pytest.mark.parametrize("seed", SEEDS)
def test_match_stats_in_top_flight_ranges(matches, seed):
    stats = match_summary(matches[seed])
    for k, (lo, hi) in RANGES.items():
        assert lo <= stats[k] <= hi, f"seed {seed}: {k}={stats[k]:.2f} not in [{lo}, {hi}]"


@pytest.mark.parametrize("seed", SEEDS)
def test_both_teams_get_possession(matches, seed):
    m = matches[seed]
    done = Counter(e.team_id for e in m.events_of(EventType.PASS) if e.outcome)
    share = done[m.meta.home.id] / sum(done.values())
    assert 0.35 <= share <= 0.65, f"seed {seed}: home share {share:.2f}"
