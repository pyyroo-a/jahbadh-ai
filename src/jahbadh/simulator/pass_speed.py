"""Synthetic pass speed, added after a match is simulated so the match itself never changes.

The engine ticks in whole seconds and doesn't model ball flight, so the ball's real speed can't be read from the
events: on the demo match, pass length over the time to the next event gave a median of 76 km/h and a top of
249 km/h (measured 19 Oct). Like shot speed, this is a plain synthetic number, labelled as such wherever it shows:
longer passes are struck harder, kept in a believable range. Treat it as a range, not a measurement.

The draws come from their own stream, derived from the seed, never from the match RNG: every event and tracking
row stays exactly as the engine made it (tests/simulator/test_fingerprint.py).
"""

import numpy as np

from jahbadh.schemas import EventType, Match

PASS_SPEED_STREAM = 0x9A55
BASE_KMH, PER_METRE_KMH, SD_KMH = 30.0, 1.0, 6.0
MIN_KMH, MAX_KMH = 20.0, 100.0


def pass_speed_kmh(rng: np.random.Generator, length_m: float) -> float:
    return round(float(np.clip(rng.normal(BASE_KMH + PER_METRE_KMH * length_m, SD_KMH), MIN_KMH, MAX_KMH)), 1)


def add_pass_speeds(match: Match, seed: int) -> None:
    """Give every PASS (completed or not) a detail["speed_kmh"], in event order, from the seed's own stream."""
    rng = np.random.default_rng([seed, PASS_SPEED_STREAM])
    for e in match.events:
        if e.type == EventType.PASS:
            e.detail["speed_kmh"] = pass_speed_kmh(rng, float(np.hypot(e.end_x - e.x, e.end_y - e.y)))
