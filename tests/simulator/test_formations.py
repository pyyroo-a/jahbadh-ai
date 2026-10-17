import pytest

from jahbadh.simulator.formations import FORMATIONS, slots_for


def test_every_formation_has_11_slots_and_one_gk():
    assert set(FORMATIONS) == {"4-3-3", "4-4-2", "4-2-3-1", "3-4-3", "3-5-2"}
    for name, slots in FORMATIONS.items():
        assert len(slots) == 11, name
        assert [r for r, _, _ in slots].count("GK") == 1
        assert slots[0][0] == "GK"
        assert all(0 <= ax <= 105 and 0 <= y <= 68 for _, ax, y in slots)


def test_back_line_size_matches_formation_name():
    assert sum(1 for r, _, _ in slots_for("4-3-3") if r in ("CB", "FB")) == 4
    assert sum(1 for r, _, _ in slots_for("3-4-3") if r in ("CB", "FB")) == 3


def test_unknown_formation_raises():
    with pytest.raises(ValueError):
        slots_for("2-3-5")
