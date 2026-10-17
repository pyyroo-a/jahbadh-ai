"""Formation slots in attacking coordinates (team attacks toward ax = 105).

Each slot is (role, ax, y) for the in-possession shape with the ball at
halfway. High y is the team's left side. The GK is always first, then
players run back to front, left to right.
"""

Slot = tuple[str, float, float]

_BACK_FOUR: list[Slot] = [("FB", 25, 60), ("CB", 22, 44), ("CB", 22, 24), ("FB", 25, 8)]
_BACK_THREE: list[Slot] = [("CB", 24, 52), ("CB", 22, 34), ("CB", 24, 16)]
_GK: Slot = ("GK", 5, 34)

FORMATIONS: dict[str, list[Slot]] = {
    "4-3-3": [_GK, *_BACK_FOUR,
              ("CM", 45, 48), ("DM", 40, 34), ("CM", 45, 20),
              ("W", 70, 58), ("ST", 73, 34), ("W", 70, 10)],
    "4-4-2": [_GK, *_BACK_FOUR,
              ("W", 47, 58), ("CM", 45, 42), ("CM", 45, 26), ("W", 47, 10),
              ("ST", 72, 42), ("ST", 72, 26)],
    "4-2-3-1": [_GK, *_BACK_FOUR,
                ("DM", 40, 42), ("DM", 40, 26),
                ("W", 60, 56), ("AM", 60, 34), ("W", 60, 12),
                ("ST", 74, 34)],
    "3-4-3": [_GK, *_BACK_THREE,
              ("W", 50, 63), ("CM", 45, 42), ("CM", 45, 26), ("W", 50, 5),
              ("W", 72, 54), ("ST", 74, 34), ("W", 72, 14)],
    "3-5-2": [_GK, *_BACK_THREE,
              ("W", 48, 62), ("CM", 45, 46), ("DM", 40, 34), ("CM", 45, 22), ("W", 48, 6),
              ("ST", 72, 42), ("ST", 72, 26)],
}


def slots_for(formation: str) -> list[Slot]:
    try:
        return FORMATIONS[formation]
    except KeyError:
        raise ValueError(f"Unknown formation {formation!r}. Known: {sorted(FORMATIONS)}") from None
