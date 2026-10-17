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
    without_press_up = [c for c in DEMO_STORYLINE if c.kind != "press_height"]
    with_up = mean(ppda(simulate_match(s, storyline=DEMO_STORYLINE), "NBR", 4200, 5400).value for s in SEEDS)
    without = mean(ppda(simulate_match(s, storyline=without_press_up), "NBR", 4200, 5400).value for s in SEEDS)
    assert with_up < 0.85 * without, f"70-90' PPDA with press-up {with_up:.2f} vs without {without:.2f}"


def test_demo_match_shows_the_press_up():
    m = simulate_match(42, storyline=DEMO_STORYLINE)
    assert ppda(m, "NBR", 4200, 5400).value < ppda(m, "NBR", 3000, 4200).value
