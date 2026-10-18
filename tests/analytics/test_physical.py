import pandas as pd
import pytest

from conftest import TRACKING_COLUMNS, make_match
from jahbadh.analytics import physical_alerts, player_physical
from jahbadh.analytics.physical import MAX_RUN_KMH, SPRINT_RECORD_MIN_KMH
from jahbadh.simulator.movement import MAX_SPEED, NOISE_SD


def run(speed_ms: float, seconds: int, jump_at: int | None = None, pid: str = "NBR-9") -> pd.DataFrame:
    """One player running along x at a steady speed for t = 0..seconds-1, optionally with a 50 m jump."""
    rows, x = [], 5.0
    for t in range(seconds):
        if t:
            x += 50.0 if t == jump_at else speed_ms
        rows.append((t, pid, pid.split("-")[0], x, 34.0))
    return pd.DataFrame(rows, columns=TRACKING_COLUMNS).astype({"t": "int64", "x": "float64", "y": "float64"})


def test_distance_and_top_speed_from_a_steady_run():
    phys = player_physical(make_match([], run(5.0, 61)), "NBR-9", 0, 61)
    assert phys.value == pytest.approx(0.3)                  # 60 steps of 5 m
    assert phys.data["top_speed_kmh"] == pytest.approx(18.0)
    assert phys.data["minutes"] == pytest.approx(61 / 60) and phys.data["excluded_steps"] == 0
    assert phys.name == "physical" and phys.unit == "km" and phys.evidence_frames == (0, 60)


def test_a_teleport_is_not_a_sprint():
    phys = player_physical(make_match([], run(5.0, 61, jump_at=30)), "NBR-9", 0, 61)
    assert phys.data["excluded_steps"] == 1
    assert phys.data["top_speed_kmh"] == pytest.approx(18.0)
    assert phys.value == pytest.approx(59 * 5 / 1000)


def test_the_cap_is_the_fastest_step_the_movement_model_allows():
    # 7 m/s toward the target plus noise clipped at 2 sd on each axis: 9.26 m in one second
    assert MAX_RUN_KMH == pytest.approx((MAX_SPEED + 2 * NOISE_SD * 2 ** 0.5) * 3.6)
    assert MAX_RUN_KMH == pytest.approx(33.3, abs=0.05)


def test_a_step_faster_than_the_model_allows_is_left_out():
    phys = player_physical(make_match([], run(9.7, 3)), "NBR-9", 0, 3)       # 34.9 km/h
    assert phys.data["excluded_steps"] == 2 and phys.data["top_speed_kmh"] is None


def test_a_window_only_counts_its_own_steps():
    phys = player_physical(make_match([], run(5.0, 61)), "NBR-9", 10, 20)
    assert phys.value == pytest.approx(9 * 5 / 1000)         # frames 10..19, 9 steps


def test_a_player_off_the_pitch_has_no_distance(sim_match):
    seen = set(sim_match.tracking["entity_id"])
    bench = next(p.id for p in sim_match.meta.home.players if p.id not in seen)
    phys = player_physical(sim_match, bench)
    assert phys.value is None and phys.note


def test_physical_rejects_bad_windows_and_unknown_players(sim_match):
    with pytest.raises(ValueError, match="window"):
        player_physical(sim_match, "NBR-9", 600, 300)
    with pytest.raises(KeyError):
        player_physical(sim_match, "XYZ-1")


def test_a_sprint_record_names_the_player_and_its_frames():
    alerts = physical_alerts(make_match([], run(9.0, 30)))   # 32.4 km/h from the first step, under the cap
    first = [a for a in alerts if a.name == "sprint_record"]
    assert len(first) == 1                                   # a steady run sets the record once
    a = first[0]
    assert a.subject == "NBR-9" and a.value == pytest.approx(32.4) and a.unit == "km/h"
    assert a.window == (0.0, 2.0) and a.evidence_frames == (0, 1)


def test_alerts_on_the_demo_match(sim_match):
    alerts = physical_alerts(sim_match)
    records = [a.value for a in alerts if a.name == "sprint_record"]
    assert records and records == sorted(records) and len(records) == len(set(records))
    assert all(SPRINT_RECORD_MIN_KMH <= r <= MAX_RUN_KMH for r in records)
    miles = [(a.subject, a.value) for a in alerts if a.name == "distance_milestone"]
    assert miles and len(miles) == len(set(miles)) and {v for _, v in miles} <= {5.0, 10.0}
    assert [a.window[1] for a in alerts] == sorted(a.window[1] for a in alerts)
    assert len({a.id for a in alerts}) == len(alerts)


def test_alerts_stop_at_the_horizon(sim_match):
    assert all(a.window[1] <= 1200 for a in physical_alerts(sim_match, end=1200))
