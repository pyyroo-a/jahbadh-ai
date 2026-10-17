import pytest
from pydantic import ValidationError

from jahbadh.schemas import Event, EventType, TeamTactics


def test_event_minute_is_one_based():
    e = Event(id=1, t=59.9, period=1, team_id="NBR", player_id="NBR-9", type=EventType.PASS, x=50, y=30)
    assert e.minute == 1
    assert Event(**{**e.model_dump(), "t": 60.0}).minute == 2


def test_tactics_reject_out_of_range():
    with pytest.raises(ValidationError):
        TeamTactics(press_height=1.2, width=0.5, tempo=0.5, directness=0.5)


def test_match_event_lookup_and_filter(tiny_match):
    assert tiny_match.event(2).type == EventType.SHOT
    assert [e.id for e in tiny_match.events_of(EventType.PASS, team_id="NBR")] == [1]
    with pytest.raises(KeyError):
        tiny_match.event(999)
    assert tiny_match.opponent_id("NBR") == "RMU"
