import pytest

from conftest import make_match, p, pr
from jahbadh.analytics.networks import pass_network


def test_pass_network_edges_and_threshold():
    evs = [pr(i, "NBR", "NBR-4", "NBR-8") for i in range(1, 5)] + [pr(5, "NBR", "NBR-8", "NBR-9")]
    r = pass_network(make_match(evs), "NBR")
    assert r.data["edges"] == [["NBR-4", "NBR-8", 4]] and r.value == 1
    assert r.evidence_event_ids == [1, 2, 3, 4, 5]


def test_nodes_use_attacking_coordinates_and_count_passes():
    evs = [pr(1, "RMU", "RMU-4", "RMU-8", x=80), pr(2, "RMU", "RMU-4", "RMU-8", x=70)]
    node = pass_network(make_match(evs), "RMU").data["nodes"]["RMU-4"]
    assert node["passes"] == 2 and node["pos"] == pytest.approx([30, 34])  # away: ax = 105 - x


def test_failed_passes_and_other_team_are_ignored():
    evs = [pr(1, "NBR", "NBR-4", "NBR-8"), p(2, "RMU", 50)]
    failed = pr(3, "NBR", "NBR-4", "NBR-8").model_copy(update={"outcome": False})
    r = pass_network(make_match(evs + [failed]), "NBR", min_passes=1)
    assert r.evidence_event_ids == [1] and r.data["edges"] == [["NBR-4", "NBR-8", 1]]
