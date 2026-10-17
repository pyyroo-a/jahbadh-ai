"""Every windowed metric refuses a window that isn't inside the match, instead of returning a plausible number."""

import pytest

from jahbadh.analytics import (average_positions, field_tilt, heatmap, midfield_control, momentum, pass_network,
                               player_impact, player_rankings, ppda, shape, xg_total, zone_overloads)

TEAM_FNS = [xg_total, field_tilt, ppda, average_positions, shape, zone_overloads, pass_network, midfield_control, heatmap]
BAD = [(600, 300), (300, 300), (-60, 600), (0, 6000)]


@pytest.mark.parametrize("fn", TEAM_FNS, ids=lambda f: f.__name__)
@pytest.mark.parametrize("start,end", BAD)
def test_team_metrics_reject_bad_windows(sim_match, fn, start, end):
    with pytest.raises(ValueError, match="window"):
        fn(sim_match, "NBR", start, end)


@pytest.mark.parametrize("start,end", BAD)
def test_player_metrics_reject_bad_windows(sim_match, start, end):
    pid = sim_match.meta.home.players[0].id
    with pytest.raises(ValueError, match="window"):
        player_impact(sim_match, pid, start, end)
    with pytest.raises(ValueError, match="window"):
        player_rankings(sim_match, None, start, end)


@pytest.mark.parametrize("kw", [{"at_t": 0}, {"at_t": 6000}, {"at_t": 600, "window_s": 0}])
def test_momentum_rejects_bad_windows(sim_match, kw):
    with pytest.raises(ValueError, match="window"):
        momentum(sim_match, **kw)


def test_whole_match_window_still_works(sim_match):
    assert xg_total(sim_match, "NBR", 0, 5400).value is not None
