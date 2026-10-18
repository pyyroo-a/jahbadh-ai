import pytest

from conftest import intercept, make_match, p, tackle
from jahbadh.analytics import game_rhythm, rhythm_series
from jahbadh.analytics.rhythm import CHAOS_MIN, CONTROL_MAX, label_for
from jahbadh.schemas import Event, EventType


def test_alternating_possession_counts_every_change():
    evs = [p(1, "NBR", 50, t=0), intercept(2, "RMU", 50, t=30), tackle(3, "NBR", 50, t=60), p(4, "RMU", 50, t=90),
           Event(id=5, t=95, period=1, team_id="NBR", player_id="NBR-4", type=EventType.FOUL, x=50, y=34)]
    r = game_rhythm(make_match(evs), 0, 120)
    assert r.name == "game_rhythm" and r.subject == "MATCH" and r.unit == "changes/min"
    assert r.data["changes"] == 3 and r.value == pytest.approx(1.5) and r.data["minutes"] == pytest.approx(2)
    assert r.data["passes_per_minute"] == pytest.approx(1.0)
    assert r.data["passes_per_possession"] == pytest.approx(0.5)      # 2 passes over 4 possessions
    assert r.evidence_event_ids == [2, 3, 4]                         # the events that changed possession
    assert r.data["label"] == "controlled"


def test_a_lost_tackle_and_a_foul_are_not_on_the_ball():
    lost = tackle(2, "RMU", 50, t=30).model_copy(update={"outcome": False})
    r = game_rhythm(make_match([p(1, "NBR", 50, t=0), lost, p(3, "NBR", 50, t=60)]), 0, 120)
    assert r.data["changes"] == 0


def test_labels_use_the_measured_thresholds():
    assert (CONTROL_MAX, CHAOS_MIN) == (2.12, 2.80)
    assert label_for(CONTROL_MAX - 0.01) == "controlled"
    assert label_for(2.4) == "balanced"
    assert label_for(CHAOS_MIN + 0.01) == "chaotic"


def test_an_empty_window_has_no_rhythm():
    r = game_rhythm(make_match([p(1, "NBR", 50, t=0)]), 600, 900)
    assert r.value == 0.0 and r.data["changes"] == 0 and r.data["passes_per_possession"] is None


def test_rhythm_rejects_bad_windows(sim_match):
    with pytest.raises(ValueError, match="window"):
        game_rhythm(sim_match, 600, 300)


def test_series_steps_every_minute_over_the_last_ten(sim_match):
    series = rhythm_series(sim_match)
    assert len(series) == 90 and series[0].window == (0.0, 60.0) and series[-1].window == (4800.0, 5400.0)
    assert all(m.data["label"] in ("controlled", "balanced", "chaotic") for m in series)
