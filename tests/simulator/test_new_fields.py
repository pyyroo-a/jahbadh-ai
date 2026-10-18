"""Pass success odds and the synthetic shot speed, the two fields added on 18 Oct (Plan 3, Task 1a)."""

from functools import cache

import numpy as np

from jahbadh.schemas import EventType
from jahbadh.simulator import simulate_match
from jahbadh.simulator.shot_speed import shot_speed_kmh
from jahbadh.simulator.storyline import DEMO_STORYLINE


@cache
def demo():
    return simulate_match(42, storyline=DEMO_STORYLINE)


def test_every_pass_carries_its_success_odds():
    passes = [e for e in demo().events if e.type == EventType.PASS]
    odds = [e.detail["p_success"] for e in passes]
    assert all(0.3 <= p <= 0.97 for p in odds)
    done = [e.detail["p_success"] for e in passes if e.outcome]
    missed = [e.detail["p_success"] for e in passes if not e.outcome]
    assert sum(done) / len(done) > sum(missed) / len(missed)        # harder passes fail more often


def test_every_shot_has_a_synthetic_speed():
    shots = [e for e in demo().events if e.type == EventType.SHOT]
    assert shots and all(35 <= e.detail["speed_kmh"] <= 125 for e in shots)
    again = simulate_match(42, storyline=DEMO_STORYLINE)
    assert [e.detail["speed_kmh"] for e in shots] == [e.detail["speed_kmh"] for e in again.events
                                                       if e.type == EventType.SHOT]


def test_other_events_get_no_new_fields():
    others = [e for e in demo().events if e.type not in (EventType.PASS, EventType.SHOT)]
    assert not any({"p_success", "speed_kmh"} & set(e.detail) for e in others)


def test_longer_shots_are_faster_on_average():
    rng = np.random.default_rng(0)
    near = [shot_speed_kmh(rng, 8) for _ in range(500)]
    far = [shot_speed_kmh(rng, 30) for _ in range(500)]
    assert sum(far) / 500 > sum(near) / 500 + 20
    assert all(35 <= v <= 125 for v in near + far)
