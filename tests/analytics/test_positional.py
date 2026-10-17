import pytest

from conftest import make_match, static_tracking
from jahbadh.analytics.positional import average_positions, heatmap, shape
from jahbadh.schemas import EventType


def test_heatmap_sums_to_one_and_respects_window(sim_match):
    h = heatmap(sim_match, "NBR", 0, 600)
    assert sum(map(sum, h.data["grid"])) == pytest.approx(1.0)
    assert h.evidence_frames == (0, 599)
    assert h.data["cells"] == [21, 14] and h.value == 11 * 600


def test_heatmap_is_in_attacking_coordinates():
    # an away player standing near x=10 (deep in the attacking end for the away team) lands in the last columns
    m = make_match([], tracking=static_tracking({"RMU-9": (10, 34)}, seconds=60))
    grid = heatmap(m, "RMU-9", 0, 60).data["grid"]
    assert max(range(21), key=lambda c: sum(grid[c])) >= 18


def test_subbed_player_only_counts_on_pitch_seconds(sim_match_demo):
    sub = sim_match_demo.events_of(EventType.SUBSTITUTION)[0]
    assert heatmap(sim_match_demo, sub.related_player_id, 0, 3600).value is None
    assert heatmap(sim_match_demo, sub.player_id, 3000, 4200).value == 600


def test_average_positions_are_in_attacking_coordinates():
    m = make_match([], tracking=static_tracking({"RMU-9": (10, 60), "RMU-2": (80, 34)}, seconds=5))
    r = average_positions(m, "RMU")
    assert r.data["players"]["RMU-9"] == pytest.approx([95, 8]) and r.value == 2


def test_shape_line_height_uses_second_deepest():
    m = make_match([], tracking=static_tracking({"NBR-2": (20, 10), "NBR-3": (25, 30), "NBR-4": (40, 50),
                                                  "NBR-9": (70, 34), "NBR-1": (5, 34)}, seconds=10))
    s = shape(m, "NBR")
    assert s["line_height"].value == pytest.approx(25)
    assert s["length"].value == pytest.approx(50) and s["width"].value == pytest.approx(40)
    assert {k: v.name for k, v in s.items()} == {"line_height": "line_height", "length": "length", "width": "width"}
