"""Press height has to show up in the data, or the agents can't talk about pressing honestly."""

from statistics import mean

import pytest

from jahbadh.analytics.territory import ppda
from jahbadh.schemas import TeamTactics
from jahbadh.simulator import simulate_match
from jahbadh.simulator.storyline import DEMO_STORYLINE
from jahbadh.simulator.teams import DEFAULT_TEAMS

SEEDS = range(1, 11)


def _home_with_press(press: float):
    team_id, name, formation, tactics = DEFAULT_TEAMS[0]
    return team_id, name, formation, tactics.model_copy(update={"press_height": press})


def test_higher_press_lowers_ppda_same_seeds():
    # A/B on identical seeds: only NBR's press height differs
    low = mean(ppda(simulate_match(s, home_spec=_home_with_press(0.3)), "NBR").value for s in SEEDS)
    high = mean(ppda(simulate_match(s, home_spec=_home_with_press(0.9)), "NBR").value for s in SEEDS)
    assert high < 0.75 * low, f"PPDA high press {high:.2f} vs low press {low:.2f}"


def test_default_high_press_team_has_lower_ppda():
    # NBR presses at 0.70, RMU at 0.45
    nbr = mean(ppda(simulate_match(s), "NBR").value for s in SEEDS)
    rmu = mean(ppda(simulate_match(s), "RMU").value for s in SEEDS)
    assert nbr < 0.85 * rmu, f"NBR {nbr:.2f} vs RMU {rmu:.2f}"


def test_demo_press_up_at_70_lowers_nbr_ppda():
    # Same seeds with and without the 70' press-up. A within-match before/after comparison would
    # mix in Rivermouth's 60' back-three switch, which changes the game on its own.
    # A 20-minute window holds only ~6 defensive actions, so per-match PPDA is noisy: pool
    # passes and actions across 20 seeds instead of averaging per-match ratios.
    without_press_up = [c for c in DEMO_STORYLINE if c.kind != "press_height"]

    def pooled(storyline) -> float:
        d = [ppda(simulate_match(s, storyline=storyline), "NBR", 4200, 5400).data for s in range(1, 21)]
        return sum(x["opponent_passes"] for x in d) / sum(x["defensive_actions"] for x in d)

    with_up, without = pooled(DEMO_STORYLINE), pooled(without_press_up)
    assert with_up < 0.95 * without, f"pooled 70-90' PPDA with press-up {with_up:.2f} vs without {without:.2f}"


def test_ppda_in_realistic_range():
    # Real football: intense pressers ~6-9, typical teams ~9-13, low blocks 15+.
    # NBR presses at 0.70 (intense), RMU at 0.45 (a bit below typical).
    matches = [simulate_match(s) for s in SEEDS]
    nbr = [ppda(m, "NBR").value for m in matches]
    rmu = [ppda(m, "RMU").value for m in matches]
    assert 6 <= mean(nbr) <= 10, f"NBR mean PPDA {mean(nbr):.2f}"
    assert 9 <= mean(rmu) <= 15, f"RMU mean PPDA {mean(rmu):.2f}"
    assert all(3 <= v <= 25 for v in nbr + rmu), f"outlier PPDA in {sorted(nbr + rmu)}"


def test_demo_match_shows_the_press_up():
    m = simulate_match(42, storyline=DEMO_STORYLINE)
    assert ppda(m, "NBR", 4200, 5400).value < ppda(m, "NBR", 3000, 4200).value
