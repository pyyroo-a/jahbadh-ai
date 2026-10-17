import pytest

from conftest import make_match, shot
from jahbadh.analytics.shots import xg_timeline, xg_total


def test_xg_total_sums_and_cites_shots():
    m = make_match([shot(1, "NBR", xg=0.3), shot(2, "NBR", xg=0.1), shot(3, "RMU", xg=0.5)])
    r = xg_total(m, "NBR")
    assert r.value == pytest.approx(0.4) and r.evidence_event_ids == [1, 2]
    assert r.id == "xg_total:NBR:0-5400" and r.unit == "xG" and r.window == (0, 5400)


def test_xg_total_respects_window():
    m = make_match([shot(1, "NBR", xg=0.3, t=100), shot(2, "NBR", xg=0.1, t=3000)])
    assert xg_total(m, "NBR", 0, 2700).value == pytest.approx(0.3)


def test_xg_timeline_accumulates():
    m = make_match([shot(1, "NBR", xg=0.3, t=100), shot(2, "NBR", xg=0.1, t=3000)])
    r = xg_timeline(m, "NBR")
    assert r.value == pytest.approx(0.4)
    assert r.data["points"] == [[100.0, pytest.approx(0.3)], [3000.0, pytest.approx(0.4)]]
