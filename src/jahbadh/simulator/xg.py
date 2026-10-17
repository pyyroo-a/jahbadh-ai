"""Expected goals from shot distance and the angle the goal mouth subtends."""

import math

GOAL_X = 105.0
POST_LOW, POST_HIGH = 30.34, 37.66

INTERCEPT = -1.0
DIST_COEF = -0.10
ANGLE_COEF = 1.5
PRESSURE_PENALTY = 0.4


def shot_xg(ax: float, y: float, under_pressure: bool = False) -> float:
    """xG for a shot at (ax, y) in attacking coordinates (goal at ax = 105)."""
    dx = GOAL_X - ax
    distance = math.hypot(dx, 34.0 - y)
    angle = abs(math.atan2(POST_HIGH - y, dx) - math.atan2(POST_LOW - y, dx))
    logit = INTERCEPT + DIST_COEF * distance + ANGLE_COEF * angle
    if under_pressure:
        logit -= PRESSURE_PENALTY
    xg = 1.0 / (1.0 + math.exp(-logit))
    return min(max(xg, 0.01), 0.95)
