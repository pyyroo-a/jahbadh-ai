"""Pitch geometry. Origin bottom-left; home attacks toward x = LENGTH all match."""

from typing import Literal

LENGTH = 105.0
WIDTH = 68.0


def clamp(x: float, y: float) -> tuple[float, float]:
    return float(min(max(x, 0.0), LENGTH)), float(min(max(y, 0.0), WIDTH))


def attack_x(x: float, team_is_home: bool) -> float:
    """x as seen by a team attacking toward x = 105."""
    return x if team_is_home else LENGTH - x


def lane(y: float, team_is_home: bool) -> Literal["left", "centre", "right"]:
    """Lane from the attacking team's point of view (thirds of the width)."""
    ay = y if team_is_home else WIDTH - y  # left side = high ay
    if ay >= WIDTH * 2 / 3:
        return "left"
    if ay < WIDTH / 3:
        return "right"
    return "centre"


def third(ax: float) -> Literal["defensive", "middle", "final"]:
    if ax < 35:
        return "defensive"
    if ax < 70:
        return "middle"
    return "final"
