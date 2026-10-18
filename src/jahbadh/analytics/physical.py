"""Physical output from the 1 Hz tracking: distance covered, top speed, and name-tagged alerts.

Speed is the raw step between two consecutive seconds (d metres in one second is d * 3.6 km/h), and distance
is the sum of those steps. Some steps are not running: positions sometimes jump in one second, for example
when the simulator pins a new ball carrier onto the ball. The movement model caps a real step at
MAX_SPEED toward the target plus noise clipped at 2 sd on each axis, about 33.3 km/h, so any faster step is
a reposition. Those are left out and counted (40 steps on seed 42, 48 and 44 on seeds 1 and 7, measured
18 Oct). The tracking is synthetic, so these numbers describe the simulated match: outfield distances run
about 13 km, a little above the 10 to 12 km of real top-flight football, because simulated positions jitter
a little every second.
"""

import numpy as np
import pandas as pd

from jahbadh.analytics.base import check_window, frame_range, metric_id
from jahbadh.schemas import Match, Metric
from jahbadh.simulator.movement import MAX_SPEED, NOISE_SD

MAX_RUN_KMH = (MAX_SPEED + 2 * NOISE_SD * 2 ** 0.5) * 3.6     # fastest step the movement model allows
SPRINT_RECORD_MIN_KMH = 30.0
DISTANCE_MILESTONES_KM = (5.0, 10.0)


def _steps(match: Match) -> pd.DataFrame:
    """One row per player per one-second step: t is the later second, the step covers frames t - 1 and t."""
    cached = getattr(match, "_physical_steps", None)
    if cached is not None and cached[0] is match.tracking:
        return cached[1]
    tr = match.tracking[match.tracking["entity_id"] != "BALL"].sort_values(["entity_id", "t"])
    g = tr.groupby("entity_id", sort=False)
    step_m = np.hypot(g["x"].diff(), g["y"].diff())
    ok = g["t"].diff() == 1
    steps = pd.DataFrame({"t": tr["t"][ok], "entity_id": tr["entity_id"][ok], "step_m": step_m[ok]})
    steps["kmh"] = steps["step_m"] * 3.6
    steps["kept"] = steps["kmh"] <= MAX_RUN_KMH
    steps = steps.sort_values(["t", "entity_id"], kind="stable").reset_index(drop=True)
    match._physical_steps = (match.tracking, steps)
    return steps


def _known_player(match: Match, player_id: str) -> None:
    if not any(p.id == player_id for team in (match.meta.home, match.meta.away) for p in team.players):
        raise KeyError(player_id)


def player_physical(match: Match, player_id: str, start: float = 0, end: float = 5400) -> Metric:
    check_window(start, end)
    _known_player(match, player_id)
    frames = frame_range(start, end)
    common = dict(id=metric_id("physical", player_id, start, end), name="physical", subject=player_id,
                  window=(start, end), unit="km", evidence_frames=frames)
    tr = match.tracking
    seen = 0 if frames is None else int(((tr["entity_id"] == player_id) & (tr["t"] >= frames[0])
                                         & (tr["t"] <= frames[1])).sum())
    if seen == 0:
        return Metric(**common, value=None, note="Player was not on the pitch in this window.")
    s = _steps(match)
    s = s[(s["entity_id"] == player_id) & (s["t"] - 1 >= frames[0]) & (s["t"] <= frames[1])]
    kept = s[s["kept"]]
    top = kept.loc[kept["kmh"].idxmax()] if len(kept) else None
    data = {"distance_km": float(kept["step_m"].sum() / 1000),
            "top_speed_kmh": None if top is None else float(top["kmh"]),
            "top_speed_t": None if top is None else float(top["t"]),
            "minutes": seen / 60, "excluded_steps": int((~s["kept"]).sum())}
    return Metric(**common, value=data["distance_km"], data=data)


def physical_alerts(match: Match, end: float = 5400) -> list[Metric]:
    """New match-wide top speeds (at least SPRINT_RECORD_MIN_KMH) and each player's distance milestones, by time."""
    check_window(0, end)
    s = _steps(match)
    s = s[s["kept"] & (s["t"] < end)]
    alerts: list[tuple[float, str, Metric]] = []

    record = 0.0
    for t, pid, kmh in zip(s["t"], s["entity_id"], s["kmh"]):
        if kmh > record:
            if kmh >= SPRINT_RECORD_MIN_KMH:
                alerts.append((t, pid, Metric(
                    id=metric_id("sprint_record", pid, t - 1, t + 1), name="sprint_record", subject=pid,
                    window=(float(t - 1), float(t + 1)), value=float(kmh), unit="km/h",
                    evidence_frames=(int(t - 1), int(t)), data={"previous_record_kmh": record or None})))
            record = float(kmh)

    cum = s.assign(km=s.groupby("entity_id")["step_m"].cumsum() / 1000)
    for km in DISTANCE_MILESTONES_KM:
        first = cum[cum["km"] >= km].groupby("entity_id", sort=False).head(1)
        for t, pid, total in zip(first["t"], first["entity_id"], first["km"]):
            alerts.append((t, pid, Metric(
                id=metric_id("distance_milestone", pid, 0, t + 1, km=km), name="distance_milestone", subject=pid,
                window=(0.0, float(t + 1)), value=km, unit="km", evidence_frames=(0, int(t)),
                data={"distance_km": float(total)})))
    return [m for _, _, m in sorted(alerts, key=lambda a: (a[0], a[2].name, a[1]))]
