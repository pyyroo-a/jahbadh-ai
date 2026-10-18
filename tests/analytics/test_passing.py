import pytest

from conftest import make_match, pass_xy
from jahbadh.analytics import pass_quality


def odds(e, p_success, outcome=True):
    return e.model_copy(update={"detail": {"p_success": p_success}, "outcome": outcome})


def passes():
    return [odds(pass_xy(1, "NBR", "NBR-2", (50, 30), (70, 30)), 0.9),                  # 20 m, easy
            odds(pass_xy(2, "NBR", "NBR-2", (50, 30), (90, 30)), 0.5),                  # 40 m, hard, completed
            odds(pass_xy(3, "NBR", "NBR-4", (50, 30), (80, 30)), 0.4, outcome=False),   # 30 m, missed
            odds(pass_xy(4, "RMU", "RMU-2", (50, 30), (20, 30)), 0.6)]                  # the other team


def test_pass_quality_counts_accuracy_length_and_difficulty():
    q = pass_quality(make_match(passes()), "NBR")
    assert q.name == "pass_quality" and q.unit == "difficulty" and q.subject == "NBR"
    assert q.data["attempted"] == 3 and q.data["completed"] == 2
    assert q.data["accuracy"] == pytest.approx(2 / 3)
    assert q.data["mean_length_m"] == pytest.approx(30.0)
    assert q.value == pytest.approx((0.1 + 0.5 + 0.6) / 3) and q.data["mean_difficulty"] == q.value
    assert q.evidence_event_ids == [1, 2, 3]


def test_the_hardest_completed_pass_is_named():
    q = pass_quality(make_match(passes()), "NBR")
    assert q.data["hardest_completed"] == {"event_id": 2, "difficulty": pytest.approx(0.5)}


def test_a_player_subject_only_counts_their_passes():
    q = pass_quality(make_match(passes()), "NBR-4")
    assert q.data["attempted"] == 1 and q.data["completed"] == 0 and q.data["hardest_completed"] is None
    assert q.value == pytest.approx(0.6)


def test_no_odds_means_no_difficulty():
    q = pass_quality(make_match([pass_xy(1, "NBR", "NBR-2", (50, 30), (70, 30))]), "NBR")
    assert q.value is None and q.note and q.data["attempted"] == 1 and q.data["accuracy"] == 1.0


def test_no_passes_means_no_value():
    q = pass_quality(make_match(passes()), "NBR", 600, 900)
    assert q.value is None and q.note and q.data["attempted"] == 0


def test_pass_quality_rejects_bad_windows_and_subjects(sim_match):
    with pytest.raises(ValueError, match="window"):
        pass_quality(sim_match, "NBR", 600, 300)
    with pytest.raises(KeyError):
        pass_quality(sim_match, "XYZ")


def test_on_the_demo_match_completed_passes_were_easier(sim_match):
    q = pass_quality(sim_match, "RMU")
    assert 0.03 <= q.value <= 0.7 and q.data["hardest_completed"]["difficulty"] >= q.value
