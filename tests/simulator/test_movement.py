import numpy as np

from jahbadh.simulator.movement import MAX_SPEED, NOISE_SD, step_positions, target_positions


def test_block_pushes_up_when_ball_advances(home_state):
    back = target_positions(home_state, ball=(30, 34), in_possession=True)[:, 0].mean()
    fwd = target_positions(home_state, ball=(80, 34), in_possession=True)[:, 0].mean()
    assert fwd - back > 20


def test_away_team_targets_are_mirrored(home_state, away_state_same_shape):
    h = target_positions(home_state, ball=(52.5, 34), in_possession=True)
    a = target_positions(away_state_same_shape, ball=(52.5, 34), in_possession=True)
    assert np.allclose(a[:, 0], 105 - h[:, 0], atol=1e-6)


def test_nearest_defender_presses_ball(home_state):
    t = target_positions(home_state, ball=(40, 20), in_possession=False)
    assert np.min(np.hypot(t[:, 0] - 40, t[:, 1] - 20)) < 0.5


def test_goalkeeper_stays_near_goal(home_state):
    t = target_positions(home_state, ball=(100, 34), in_possession=True)
    assert 2 <= t[0, 0] <= 18


def test_speed_cap_and_never_off_pitch(home_state):
    rng = np.random.default_rng(1)
    for ball in [(0, 0), (105, 68), (105, 0)] * 50:
        before = home_state.pos.copy()
        step_positions(home_state, ball, in_possession=False, rng=rng)
        assert (np.hypot(*(home_state.pos - before).T) <= MAX_SPEED + 4 * NOISE_SD).all()
        assert (home_state.pos[:, 0] >= 0).all() and (home_state.pos[:, 0] <= 105).all()
        assert (home_state.pos[:, 1] >= 0).all() and (home_state.pos[:, 1] <= 68).all()
