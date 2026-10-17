import numpy as np
import pytest

from jahbadh.schemas import TeamTactics
from jahbadh.simulator.formations import slots_for
from jahbadh.simulator.movement import TeamState

TACTICS = TeamTactics(press_height=0.7, width=0.6, tempo=0.6, directness=0.4)


def _state(team_id: str, is_home: bool) -> TeamState:
    slots = np.array([(ax, y) for _, ax, y in slots_for("4-3-3")], dtype=float)
    pos = slots if is_home else np.column_stack([105 - slots[:, 0], 68 - slots[:, 1]])
    return TeamState(
        team_id=team_id,
        is_home=is_home,
        formation="4-3-3",
        tactics=TACTICS,
        on_pitch=[f"{team_id}-{i}" for i in range(1, 12)],
        pos=pos.copy(),
    )


@pytest.fixture
def home_state() -> TeamState:
    return _state("NBR", True)


@pytest.fixture
def away_state_same_shape() -> TeamState:
    return _state("RMU", False)
