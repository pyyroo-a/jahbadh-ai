import pytest

from conftest import intercept, make_match, mirror, p, tackle
from jahbadh.analytics.territory import field_tilt, ppda


def test_field_tilt_counts_final_third_passes_only():
    # NBR: 3 final-third passes (x=80) + 1 own-half; RMU (away, attacking x=0): 1 final-third pass at x=20
    m = make_match([p(1, "NBR", 80), p(2, "NBR", 80), p(3, "NBR", 80), p(4, "NBR", 30), p(5, "RMU", 20)])
    nbr = field_tilt(m, "NBR")
    assert nbr.value == pytest.approx(0.75) and nbr.evidence_event_ids == [1, 2, 3]
    assert field_tilt(m, "RMU").value == pytest.approx(0.25)


def test_field_tilt_mirrors(sim_match):
    assert field_tilt(sim_match, "NBR").value == pytest.approx(field_tilt(mirror(sim_match), "NBR").value)


def test_ppda_ratio_and_evidence():
    # RMU makes 10 passes in its own defensive 60%; NBR makes 2 defensive actions there
    m = make_match([p(i, "RMU", 90) for i in range(1, 11)] + [tackle(11, "NBR", 85), intercept(12, "NBR", 80)])
    r = ppda(m, "NBR")
    assert r.value == pytest.approx(5.0) and r.evidence_event_ids == [11, 12]


def test_ppda_ignores_actions_outside_the_zone():
    # a tackle deep in NBR's own half (RMU attack_x = 85) is outside RMU's defensive 60%
    m = make_match([p(1, "RMU", 90), p(2, "RMU", 90), tackle(3, "NBR", 85), tackle(4, "NBR", 20)])
    assert ppda(m, "NBR").value == pytest.approx(2.0)


def test_ppda_mirrors(sim_match):
    assert ppda(sim_match, "RMU").value == pytest.approx(ppda(mirror(sim_match), "RMU").value)


def test_empty_windows_return_none_with_note():
    m = make_match([p(1, "RMU", 90)])
    assert ppda(m, "NBR").value is None and ppda(m, "NBR").note
    empty_tilt = field_tilt(m, "NBR", 0, 60)
    assert empty_tilt.value is None and empty_tilt.note
