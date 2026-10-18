from fakes import demo_match, make_match, pr, static_tracking
from jahbadh.agents.spotlight import spotlight_moment, spotlight_moments, team_recap_moments
from jahbadh.analytics import player_rankings


def test_spotlights_pick_distinct_players_with_real_numbers():
    m = demo_match()
    ms = spotlight_moments(m)
    assert 1 <= len(ms) <= 3 and len({x.player_id for x in ms}) == len(ms)
    top = player_rankings(m, None, 0, 5400, by="value", n=1)[0]
    assert ms[0].player_id == top.subject and ms[0].kind == "spotlight" and ms[0].t == 5400
    assert all(x.label.startswith("Spotlight: ") and x.id == f"spotlight-{x.player_id}" for x in ms)


def test_angle_with_nobody_above_zero_is_skipped():
    m = make_match([pr(1, "NBR", "NBR-4", "NBR-9")],
                   tracking=static_tracking({"NBR-4": (50, 34), "NBR-9": (60, 34)}, seconds=60))
    assert spotlight_moments(m, t=60) == []


def test_spotlight_moment_for_any_player():
    m = demo_match()
    player = m.meta.away.players[3]
    mo = spotlight_moment(m, player.id, "on request")
    assert mo.team_id == "RMU" and mo.player_id == player.id and mo.label == f"Spotlight: {player.name} (on request)"


def test_one_team_recap_per_club_home_first():
    ms = team_recap_moments(demo_match())
    assert [(m.id, m.team_id, m.kind, m.t) for m in ms] == [("team_recap-NBR", "NBR", "team_recap", 5400),
                                                            ("team_recap-RMU", "RMU", "team_recap", 5400)]
    assert [m.label for m in ms] == ["Full-time recap for Northbridge FC", "Full-time recap for Rivermouth United"]
