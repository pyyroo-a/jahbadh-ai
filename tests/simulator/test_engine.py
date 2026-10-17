import pandas as pd
import pytest

from jahbadh.schemas import EventType
from jahbadh.simulator import simulate_match


@pytest.fixture(scope="module")
def m():
    return simulate_match(seed=42)


def test_same_seed_same_match_different_seed_differs():
    a, b, c = simulate_match(1), simulate_match(1), simulate_match(2)
    assert [e.model_dump() for e in a.events] == [e.model_dump() for e in b.events]
    pd.testing.assert_frame_equal(a.tracking, b.tracking)
    assert [e.model_dump() for e in a.events] != [e.model_dump() for e in c.events]


def test_match_id_defaults_from_seed(m):
    assert m.meta.match_id == "match-042" and m.meta.seed == 42


def test_tracking_shape(m):
    assert m.tracking["t"].min() == 0 and m.tracking["t"].max() == 5399
    assert (m.tracking.groupby("t").size() == 23).all()
    assert list(m.tracking.columns) == ["t", "entity_id", "team_id", "x", "y"]
    assert m.tracking["x"].between(0, 105).all() and m.tracking["y"].between(0, 68).all()


def test_events_are_ordered_unique_and_valid(m):
    ids = [e.id for e in m.events]
    assert ids == list(range(1, len(ids) + 1))
    assert all(a.t <= b.t for a, b in zip(m.events, m.events[1:]))
    assert all(0 <= e.x <= 105 and 0 <= e.y <= 68 for e in m.events)
    assert all(e.xg is not None for e in m.events_of(EventType.SHOT))
    assert all(e.related_player_id for e in m.events_of(EventType.PASS) if e.outcome)


def test_score_matches_goal_events(m):
    for tid in (m.meta.home.id, m.meta.away.id):
        assert m.meta.score[tid] == len(m.events_of(EventType.GOAL, team_id=tid))


def test_kickoffs_and_period_end(m):
    ko = m.events_of(EventType.KICKOFF)
    assert [(e.t, e.team_id) for e in ko][:1] == [(0, m.meta.home.id)]
    assert any(e.t == 2700 and e.team_id == m.meta.away.id for e in ko)
    assert len(m.events_of(EventType.PERIOD_END)) == 1


def test_no_player_gets_two_yellows(m):
    booked = [e.player_id for e in m.events_of(EventType.CARD)]
    assert len(booked) == len(set(booked))
