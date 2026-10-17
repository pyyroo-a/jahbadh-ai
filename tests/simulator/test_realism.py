"""Simulated matches should look like top-flight football, statistically.

Two kinds of check: the AVERAGE over many seeds must look like a typical
top-flight match (tight ranges), and EVERY match must be plausible (wide
ranges). Requiring every match to sit inside a typical range would fail
even for real football, since some real games are wild.
"""

from collections import Counter
from statistics import mean

import pytest

from jahbadh.schemas import EventType, Match
from jahbadh.simulator import simulate_match

TYPICAL_MEAN = {
    "passes": (750, 1100), "pass_completion": (0.76, 0.86), "shots": (20, 32),
    "xg_total": (2.3, 3.4), "goals": (2.0, 3.6), "fouls": (15, 28), "cards": (1.5, 5),
    "events_total": (1450, 2400),
}
PLAUSIBLE_MATCH = {
    "passes": (600, 1300), "pass_completion": (0.70, 0.92), "shots": (10, 45),
    "xg_total": (0.8, 6.5), "goals": (0, 10), "fouls": (8, 40), "cards": (0, 10),
    "events_total": (1200, 3000),
}
SEEDS = range(1, 11)


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
def summaries() -> dict[int, dict[str, float]]:
    return {seed: match_summary(simulate_match(seed)) for seed in SEEDS}


@pytest.mark.parametrize("stat", list(TYPICAL_MEAN))
def test_average_match_is_typical(summaries, stat):
    lo, hi = TYPICAL_MEAN[stat]
    avg = mean(s[stat] for s in summaries.values())
    assert lo <= avg <= hi, f"mean {stat}={avg:.2f} not in [{lo}, {hi}]"


@pytest.mark.parametrize("seed", SEEDS)
def test_every_match_is_plausible(summaries, seed):
    for k, (lo, hi) in PLAUSIBLE_MATCH.items():
        assert lo <= summaries[seed][k] <= hi, f"seed {seed}: {k}={summaries[seed][k]:.2f} not in [{lo}, {hi}]"


@pytest.mark.parametrize("seed", list(SEEDS)[:5])
def test_both_teams_get_possession(seed):
    m = simulate_match(seed)
    done = Counter(e.team_id for e in m.events_of(EventType.PASS) if e.outcome)
    share = done[m.meta.home.id] / sum(done.values())
    assert 0.35 <= share <= 0.65, f"seed {seed}: home share {share:.2f}"
