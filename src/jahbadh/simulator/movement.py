"""Per-tick player movement toward formation slots that shift with the ball.

Targets are worked out in attacking coordinates (team attacks toward
ax = 105, high y is the team's left) and converted back to pitch
coordinates. For the away team that's a 180 degree rotation.
"""

from dataclasses import dataclass

import numpy as np

from jahbadh.pitch import LENGTH, WIDTH
from jahbadh.schemas import TeamTactics
from jahbadh.simulator.formations import slots_for

MAX_SPEED = 7.0          # metres per second
NOISE_SD = 0.8           # metres, truncated at 2 sd
BALL_FOLLOW = 0.5        # block shift per metre of ball advance
POSSESSION_PUSH = 8.0    # extra push up when in possession
PRESS_PUSH = 10.0        # out of possession: +/- 5 m around press_height 0.5
GK_RANGE = (2.0, 18.0)


@dataclass
class TeamState:
    team_id: str
    is_home: bool
    formation: str
    tactics: TeamTactics
    on_pitch: list[str]
    pos: np.ndarray  # (11, 2) pitch coordinates, index-aligned with formation slots


def _to_attacking(xy: np.ndarray, is_home: bool) -> np.ndarray:
    return xy if is_home else np.column_stack([LENGTH - xy[:, 0], WIDTH - xy[:, 1]])


def target_positions(team: TeamState, ball: tuple[float, float], in_possession: bool) -> np.ndarray:
    slots = np.array([(ax, y) for _, ax, y in slots_for(team.formation)], dtype=float)
    bx, by = _to_attacking(np.array([ball], dtype=float), team.is_home)[0]
    t = team.tactics

    shift = BALL_FOLLOW * (bx - LENGTH / 2)
    shift += POSSESSION_PUSH if in_possession else PRESS_PUSH * (t.press_height - 0.5)
    target = slots.copy()
    target[:, 0] += shift
    if in_possession:
        target[:, 1] = WIDTH / 2 + (slots[:, 1] - WIDTH / 2) * (1 + 0.3 * t.width)
    else:
        target[:, 1] = slots[:, 1] + (by - slots[:, 1]) * 0.3 * (1 - t.width)
    target[0, 0] = np.clip(target[0, 0], *GK_RANGE)
    target[0, 1] = slots[0, 1] + (by - slots[0, 1]) * 0.15

    if not in_possession:
        current = _to_attacking(team.pos, team.is_home)
        dist = np.hypot(current[1:, 0] - bx, current[1:, 1] - by)
        n_press = 2 if t.press_height > 0.6 else 1
        for idx in np.argsort(dist, kind="stable")[:n_press] + 1:
            target[idx] = (bx, by)

    target[:, 0] = np.clip(target[:, 0], 0, LENGTH)
    target[:, 1] = np.clip(target[:, 1], 0, WIDTH)
    return _to_attacking(target, team.is_home)  # same rotation converts back


def step_positions(team: TeamState, ball: tuple[float, float], in_possession: bool,
                   rng: np.random.Generator, dt: float = 1.0) -> None:
    target = target_positions(team, ball, in_possession)
    delta = target - team.pos
    dist = np.hypot(delta[:, 0], delta[:, 1])
    scale = np.minimum(1.0, (MAX_SPEED * dt) / np.maximum(dist, 1e-9))
    noise = np.clip(rng.normal(0.0, NOISE_SD, size=delta.shape), -2 * NOISE_SD, 2 * NOISE_SD)
    new = team.pos + delta * scale[:, None] + noise
    new[:, 0] = np.clip(new[:, 0], 0, LENGTH)
    new[:, 1] = np.clip(new[:, 1], 0, WIDTH)
    team.pos = new
