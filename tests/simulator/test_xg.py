from jahbadh.simulator.xg import shot_xg


def test_penalty_spot_is_around_quarter():
    assert 0.20 <= shot_xg(94, 34) <= 0.30


def test_long_range_central_is_low():
    assert shot_xg(80, 34) < 0.06


def test_closer_and_central_is_higher():
    assert shot_xg(100, 34) > shot_xg(94, 34) > shot_xg(94, 10)


def test_pressure_lowers_xg_and_bounds_hold():
    assert shot_xg(94, 34, under_pressure=True) < shot_xg(94, 34)
    assert 0.01 <= shot_xg(104.9, 34) <= 0.95
    assert 0.01 <= shot_xg(105, 0) <= 0.95  # on the goal line, wide: no division by zero
