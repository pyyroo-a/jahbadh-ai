"""Synthetic shot speed, added after a match is simulated so the match itself never changes.

The engine doesn't model ball flight, so this is a plain synthetic number, labelled as such wherever it shows.
Close finishes come out slower and placed, and long shots approach a max-effort strike. For scale, a small lab
study of national-team players measured max-effort instep kicks of about 102 to 115 km/h
(https://wnus.usz.edu.pl/cejssm/file/article/download/20440.pdf). No large match dataset was found, so treat
the model as a believable range, not a measurement.

The draws come from their own stream, derived from the seed, never from the match RNG: every event and
tracking row stays exactly as the engine made it (tests/simulator/test_fingerprint.py).
"""

import numpy as np

from jahbadh.pitch import LENGTH, WIDTH
from jahbadh.schemas import EventType, Match

SHOT_SPEED_STREAM = 0x5407
BASE_KMH, PER_METRE_KMH, SD_KMH = 55.0, 1.2, 12.0
MIN_KMH, MAX_KMH = 35.0, 125.0


def shot_speed_kmh(rng: np.random.Generator, distance_m: float) -> float:
    return round(float(np.clip(rng.normal(BASE_KMH + PER_METRE_KMH * distance_m, SD_KMH), MIN_KMH, MAX_KMH)), 1)


def add_shot_speeds(match: Match, seed: int) -> None:
    """Give every SHOT a detail["speed_kmh"], in event order, from the seed's own shot-speed stream."""
    rng = np.random.default_rng([seed, SHOT_SPEED_STREAM])
    home = match.meta.home.id
    for e in match.events:
        if e.type == EventType.SHOT:
            goal_x = LENGTH if e.team_id == home else 0.0
            e.detail["speed_kmh"] = shot_speed_kmh(rng, float(np.hypot(goal_x - e.x, WIDTH / 2 - e.y)))
