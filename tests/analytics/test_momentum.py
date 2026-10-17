import pytest

from conftest import make_match, p, shot
from jahbadh.analytics.momentum import momentum, momentum_series


def test_momentum_favours_team_with_more_threat():
    m = make_match([shot(1, "NBR", xg=0.4, t=500), p(2, "RMU", 20, t=550)])
    r = momentum(m, at_t=600)
    assert r.value == pytest.approx(0.4 / (0.4 + 0.02)) and set(r.evidence_event_ids) == {1, 2}
    assert r.subject == "MATCH" and r.window == (0, 600)
    # raw threat in xG units, named so nobody reads them as shares (a live writer called 0.978 an "away share")
    assert r.data == {"home_threat": pytest.approx(0.4), "away_threat": pytest.approx(0.02)}


def test_momentum_ignores_events_outside_window():
    m = make_match([shot(1, "NBR", xg=0.4, t=10), shot(2, "RMU", xg=0.2, t=1000)])
    assert momentum(m, at_t=1100).value == pytest.approx(0.0)


def test_momentum_none_when_quiet():
    r = momentum(make_match([]), at_t=600)
    assert r.value is None and r.note


def test_series_length(sim_match):
    series = momentum_series(sim_match)
    assert len(series) == 90
    assert series[0].window == (0, 60) and series[-1].window == (4800, 5400)
