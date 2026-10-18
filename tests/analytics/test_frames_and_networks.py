import pytest

from conftest import make_match, pass_xy, pr
from jahbadh.analytics import pass_network
from jahbadh.analytics.base import frame_range


def test_frame_range_covers_whole_seconds_inside_the_window():
    assert frame_range(0, 5400) == (0, 5399)
    assert frame_range(60, 120) == (60, 119)
    assert frame_range(0.5, 10.5) == (1, 10)
    assert frame_range(10, 10.5) == (10, 10)
    assert frame_range(5399.5, 5400) is None


def test_every_edge_endpoint_is_a_node(sim_match_demo):
    for team in ("NBR", "RMU"):
        net = pass_network(sim_match_demo, team, 3600, 5400, min_passes=1)
        nodes = net.data["nodes"]
        assert all(a in nodes and b in nodes for a, b, _ in net.data["edges"])
        assert all({"pos", "passes", "received"} <= set(n) for n in nodes.values())


def test_a_receiver_who_never_passed_sits_where_they_received():
    # NBR-2 finds NBR-10 (pass_xy's receiver) three times; NBR-10 never passes
    m = make_match([pass_xy(1, "NBR", "NBR-2", (50, 30), (80, 30)),
                    pass_xy(2, "NBR", "NBR-2", (50, 30), (90, 30)),
                    pass_xy(3, "NBR", "NBR-2", (50, 30), (100, 30))])
    net = pass_network(m, "NBR")
    ten = net.data["nodes"]["NBR-10"]
    assert ten["passes"] == 0 and ten["received"] == 3
    assert ten["pos"] == pytest.approx([90, 30])
    assert net.data["nodes"]["NBR-2"]["passes"] == 3 and net.data["nodes"]["NBR-2"]["received"] == 0


def test_a_receiver_with_no_location_keeps_the_edge_and_has_no_position():
    m = make_match([pr(1, "NBR", "NBR-4", "NBR-8")])     # pr passes carry no end point
    net = pass_network(m, "NBR", min_passes=1)
    assert net.data["edges"] == [["NBR-4", "NBR-8", 1]]
    assert net.data["nodes"]["NBR-8"] == {"pos": None, "passes": 0, "received": 1}


def test_an_away_receiver_is_placed_in_the_attacking_frame():
    m = make_match([pass_xy(i, "RMU", "RMU-2", (50, 30), (20, 10)) for i in (1, 2, 3)])
    assert pass_network(m, "RMU").data["nodes"]["RMU-10"]["pos"] == pytest.approx([85, 58])
