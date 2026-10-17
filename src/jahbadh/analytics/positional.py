"""Tracking-based metrics: heatmaps, average positions and team shape.

Everything is reported in the subject team's attacking coordinates
(attacking toward x = 105, high y = the team's left), so a heatmap
always reads left to right as attacking, whichever side the team is on.
"""

import numpy as np
import pandas as pd

from jahbadh.analytics.base import is_home, metric_id
from jahbadh.pitch import LENGTH, WIDTH
from jahbadh.schemas import Match, Metric


def _window(match: Match, start: float, end: float) -> pd.DataFrame:
    tr = match.tracking
    return tr[(tr["t"] >= start) & (tr["t"] < end)]


def _attacking(rows: pd.DataFrame, home: bool) -> pd.DataFrame:
    return rows if home else rows.assign(x=LENGTH - rows["x"], y=WIDTH - rows["y"])


def _subject_team(match: Match, subject: str) -> str:
    if subject in (match.meta.home.id, match.meta.away.id):
        return subject
    for team in (match.meta.home, match.meta.away):
        if any(p.id == subject for p in team.players):
            return team.id
    raise KeyError(subject)


def _goalkeepers(match: Match, team_id: str) -> set[str]:
    return {p.id for p in match.team(team_id).players if p.role == "GK"}


def heatmap(match: Match, subject: str, start: float = 0, end: float = 5400,
            grid: tuple[int, int] = (21, 14)) -> Metric:
    team_id = _subject_team(match, subject)
    rows = _window(match, start, end)
    rows = rows[rows["team_id"] == team_id] if subject == team_id else rows[rows["entity_id"] == subject]
    rows = _attacking(rows, is_home(match, team_id))
    n = len(rows)
    common = dict(id=metric_id("heatmap", subject, start, end, **({"grid": f"{grid[0]}x{grid[1]}"} if tuple(grid) != (21, 14) else {})), name="heatmap", subject=subject,
                  window=(start, end), unit="samples", evidence_frames=(int(start), int(end) - 1))
    if n == 0:
        return Metric(**common, value=None, data={"cells": list(grid)},
                      note="Subject was not on the pitch in this window.")
    counts, _, _ = np.histogram2d(rows["x"], rows["y"], bins=grid, range=[[0, LENGTH], [0, WIDTH]])
    return Metric(**common, value=float(n),
                  data={"grid": (counts / n).tolist(), "cells": list(grid), "samples": n})


def average_positions(match: Match, team_id: str, start: float = 0, end: float = 5400) -> Metric:
    rows = _window(match, start, end)
    rows = _attacking(rows[rows["team_id"] == team_id], is_home(match, team_id))
    means = rows.groupby("entity_id")[["x", "y"]].mean()
    players = {pid: [float(r.x), float(r.y)] for pid, r in means.iterrows()}
    return Metric(id=metric_id("average_positions", team_id, start, end), name="average_positions",
                  subject=team_id, window=(start, end), value=float(len(players)), unit="players",
                  evidence_frames=(int(start), int(end) - 1), data={"players": players},
                  note=None if players else "No tracking for this team in this window.")


def shape(match: Match, team_id: str, start: float = 0, end: float = 5400) -> dict[str, Metric]:
    """Median over seconds of: line height (2nd-deepest outfielder), length and width of the outfield block."""
    rows = _window(match, start, end)
    rows = rows[(rows["team_id"] == team_id) & ~rows["entity_id"].isin(_goalkeepers(match, team_id))]
    rows = _attacking(rows, is_home(match, team_id))
    g = rows.groupby("t")
    per_second = pd.DataFrame({
        "n": g.size(),
        "length": g["x"].max() - g["x"].min(),
        "width": g["y"].max() - g["y"].min(),
    })
    # nth(1) after sorting by x = the second-deepest outfielder each second (a proxy for the offside line)
    second = rows.sort_values(["t", "x"]).groupby("t").nth(1).set_index("t")["x"]
    per_second["second_deepest"] = second
    per_second = per_second[per_second["n"] >= 2]
    values = {
        "line_height": per_second["second_deepest"].median() if len(per_second) else None,
        "length": per_second["length"].median() if len(per_second) else None,
        "width": per_second["width"].median() if len(per_second) else None,
    }
    return {
        key: Metric(id=metric_id(key, team_id, start, end), name=key, subject=team_id, window=(start, end),
                    value=None if v is None else float(v), unit="m", evidence_frames=(int(start), int(end) - 1),
                    note=None if v is not None else "Not enough outfield tracking in this window.")
        for key, v in values.items()
    }
