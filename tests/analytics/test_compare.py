import pytest

from jahbadh.analytics.compare import before_after
from jahbadh.analytics.positional import shape
from jahbadh.analytics.territory import field_tilt


def test_before_after_on_field_tilt(sim_match_demo):
    r = before_after(field_tilt, sim_match_demo, "RMU", at_t=3600)
    assert r.name == "field_tilt_change"
    assert r.data["before"]["window"] == (2700.0, 3600.0) and r.data["after"]["window"] == (3600.0, 4500.0)
    assert r.value == pytest.approx(r.data["after"]["value"] - r.data["before"]["value"])
    assert set(r.evidence_event_ids) == set(r.data["before"]["evidence_event_ids"]) | set(
        r.data["after"]["evidence_event_ids"])


def test_before_after_clamps_to_match_bounds(sim_match_demo):
    r = before_after(field_tilt, sim_match_demo, "NBR", at_t=300)
    assert r.data["before"]["window"] == (0.0, 300.0)
    assert before_after(field_tilt, sim_match_demo, "NBR", at_t=5200).data["after"]["window"] == (5200.0, 5400.0)


def test_before_after_with_dict_metric(sim_match_demo):
    r = before_after(shape, sim_match_demo, "RMU", at_t=3600, value_key="width")
    assert r.name == "width_change" and r.unit == "m"
    assert r.value == pytest.approx(r.data["after"]["value"] - r.data["before"]["value"])


def test_before_after_none_when_a_side_is_empty(sim_match_demo):
    r = before_after(field_tilt, sim_match_demo, "NBR", at_t=0)
    assert r.value is None and r.note
