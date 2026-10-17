import numpy as np

from jahbadh.schemas import TeamTactics
from jahbadh.simulator.formations import slots_for
from jahbadh.simulator.teams import DEFAULT_TEAMS, make_team

TACTICS = TeamTactics(press_height=0.5, width=0.5, tempo=0.5, directness=0.5)


def test_make_team_is_deterministic_and_complete():
    t1 = make_team("NBR", "Northbridge FC", "4-3-3", TACTICS, np.random.default_rng(7))
    t2 = make_team("NBR", "Northbridge FC", "4-3-3", TACTICS, np.random.default_rng(7))
    assert t1 == t2
    assert len(t1.players) == 16 and sum(p.starter for p in t1.players) == 11
    assert len({p.shirt for p in t1.players}) == 16
    assert all(p.id == f"NBR-{p.shirt}" for p in t1.players)


def test_starter_roles_follow_formation_slots_and_bench_mix():
    t = make_team("RMU", "Rivermouth United", "3-4-3", TACTICS, np.random.default_rng(1))
    starters = [p for p in t.players if p.starter]
    assert [p.role for p in starters] == [r for r, _, _ in slots_for("3-4-3")]
    assert sorted(p.role for p in t.players if not p.starter) == sorted(["GK", "CB", "CM", "W", "ST"])


def test_default_teams_are_the_demo_pair():
    ids = [spec[0] for spec in DEFAULT_TEAMS]
    assert ids == ["NBR", "RMU"]
    assert DEFAULT_TEAMS[0][3].press_height == 0.7 and DEFAULT_TEAMS[1][3].directness == 0.55
