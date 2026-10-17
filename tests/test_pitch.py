from jahbadh.pitch import attack_x, clamp, lane, third


def test_attack_x_mirrors_for_away():
    assert attack_x(90, team_is_home=True) == 90
    assert attack_x(90, team_is_home=False) == 15


def test_lane_is_from_attacker_view():
    assert lane(60, team_is_home=True) == "left"  # home attacks +x, so high y is their left
    assert lane(60, team_is_home=False) == "right"


def test_clamp_and_third():
    assert clamp(-3, 70) == (0.0, 68.0)
    assert third(20) == "defensive" and third(50) == "middle" and third(80) == "final"
