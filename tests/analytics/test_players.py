import pytest

from conftest import make_match, pass_xy, pr, shot_by, static_tracking, tackle
from jahbadh.analytics.players import player_impact, player_rankings
from jahbadh.schemas import EventType


def test_xa_credits_the_passer_of_the_shot():
    evs = [pr(1, "NBR", "NBR-8", "NBR-9", t=100), shot_by(2, "NBR", "NBR-9", xg=0.3, t=104)]
    m = make_match(evs, tracking=static_tracking({"NBR-8": (60, 30), "NBR-9": (90, 34)}, seconds=200))
    assert player_impact(m, "NBR-8").data["xa"] == pytest.approx(0.3)
    assert player_impact(m, "NBR-8").value == pytest.approx(0.3)      # xG 0 + xA 0.3
    assert player_impact(m, "NBR-9").value == pytest.approx(0.3)      # xG 0.3 + xA 0
    assert 2 in player_impact(m, "NBR-8").evidence_event_ids


def test_assist_counts_only_goals():
    evs = [pr(1, "NBR", "NBR-8", "NBR-9", t=100), shot_by(2, "NBR", "NBR-9", xg=0.3, t=104, goal=True),
           pr(3, "NBR", "NBR-8", "NBR-9", t=200), shot_by(4, "NBR", "NBR-9", xg=0.1, t=203)]
    m = make_match(evs, tracking=static_tracking({"NBR-8": (60, 30), "NBR-9": (90, 34)}, seconds=300))
    d = player_impact(m, "NBR-8").data
    assert d["assists"] == 1 and d["xa"] == pytest.approx(0.4)
    assert player_impact(m, "NBR-9").data["goals"] == 1


def test_no_xa_if_opponent_touched_it_or_too_late():
    evs = [pr(1, "NBR", "NBR-8", "NBR-9", t=100), tackle(2, "RMU", 80, t=101), shot_by(3, "NBR", "NBR-9", xg=0.3, t=103),
           pr(4, "NBR", "NBR-8", "NBR-9", t=300), shot_by(5, "NBR", "NBR-9", xg=0.2, t=330)]
    m = make_match(evs, tracking=static_tracking({"NBR-8": (60, 30), "NBR-9": (90, 34)}, seconds=400))
    assert player_impact(m, "NBR-8").data["xa"] == 0


def test_progressive_passes_and_final_third_entries():
    evs = [pass_xy(1, "NBR", "NBR-6", (40, 34), (55, 34)),     # progressive, no entry
           pass_xy(2, "NBR", "NBR-6", (60, 34), (75, 34)),     # progressive + entry
           pass_xy(3, "NBR", "NBR-6", (50, 34), (45, 34))]     # backwards
    d = player_impact(make_match(evs, tracking=static_tracking({"NBR-6": (50, 34)}, seconds=10)), "NBR-6").data
    assert d["progressive_passes"] == 2 and d["final_third_entries"] == 1 and d["passes"] == 3
    assert d["pass_completion"] == pytest.approx(1.0) and d["touches"] == 3 and d["involvement"] == pytest.approx(1.0)


def test_away_player_progression_uses_away_direction():
    d = player_impact(make_match([pass_xy(1, "RMU", "RMU-6", (60, 34), (45, 34))],
                                 tracking=static_tracking({"RMU-6": (60, 34)}, seconds=10)), "RMU-6").data
    assert d["progressive_passes"] == 1


def test_involvement_and_minutes_for_a_sub(sim_match_demo):
    sub = sim_match_demo.events_of(EventType.SUBSTITUTION)[0]
    r = player_impact(sim_match_demo, sub.related_player_id)
    assert r.data["minutes"] == pytest.approx(30.0) and 0 <= r.data["involvement"] <= 1
    assert r.data["heatmap_id"] == f"heatmap:{sub.related_player_id}:0-5400"
    late = player_impact(sim_match_demo, sub.related_player_id, 0, 3600)
    assert late.value is None and late.note


def test_rankings_sorted_and_filtered(sim_match):
    top = player_rankings(sim_match, team_id="RMU", by="ball_wins", n=3)
    assert len(top) == 3 and all(r.subject.startswith("RMU") for r in top)
    assert [r.data["ball_wins"] for r in top] == sorted((r.data["ball_wins"] for r in top), reverse=True)


def test_rankings_by_value_cover_both_teams(sim_match):
    top = player_rankings(sim_match, n=5)
    assert len(top) == 5 and [r.value for r in top] == sorted((r.value for r in top), reverse=True)
