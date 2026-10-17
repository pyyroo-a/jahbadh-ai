"""Zone overloads: where a team outnumbers the opponent's outfield players.

The pitch is split into a 3 x 3 grid from the team's point of view:
thirds (defensive / middle / final) by lanes (left / centre / right).
Zone names look like "final-left".

Every zone's share is reported in data["by_zone"], but the headline zone
only comes from the middle and final thirds: a team's own defensive third is
almost always "overloaded" (centre-backs vs a lone striker), which says nothing.
"""

import numpy as np
import pandas as pd

from jahbadh.analytics.base import is_home, metric_id
from jahbadh.pitch import LENGTH, WIDTH
from jahbadh.schemas import Match, Metric

HEADLINE_THIRDS = ("middle", "final")


def _zones(rows: pd.DataFrame, home: bool) -> pd.Series:
    ax = rows["x"] if home else LENGTH - rows["x"]
    ay = rows["y"] if home else WIDTH - rows["y"]  # high ay = the team's left
    thirds = np.select([ax < 35, ax < 70], ["defensive", "middle"], "final")
    lanes = np.select([ay >= WIDTH * 2 / 3, ay < WIDTH / 3], ["left", "right"], "centre")
    return pd.Series(np.char.add(np.char.add(thirds.astype(str), "-"), lanes.astype(str)), index=rows.index)


def zone_overloads(match: Match, team_id: str, start: float = 0, end: float = 5400, margin: int = 2) -> Metric:
    tr = match.tracking
    rows = tr[(tr["t"] >= start) & (tr["t"] < end)]
    opp_id = match.opponent_id(team_id)
    opp_keepers = {p.id for p in match.team(opp_id).players if p.role == "GK"}
    ours = rows[rows["team_id"] == team_id]
    theirs = rows[(rows["team_id"] == opp_id) & ~rows["entity_id"].isin(opp_keepers)]
    home = is_home(match, team_id)
    n_seconds = rows["t"].nunique()

    counts = pd.DataFrame({
        "ours": ours.groupby(["t", _zones(ours, home)]).size(),
        "theirs": theirs.groupby(["t", _zones(theirs, home)]).size(),
    }).fillna(0).astype(int)
    counts.index.names = ["t", "zone"]
    over = counts[counts["ours"] - counts["theirs"] >= margin].reset_index()

    common = dict(id=metric_id("zone_overloads", team_id, start, end, **({"margin": margin} if margin != 2 else {})), name="zone_overloads", subject=team_id,
                  window=(start, end), unit="share_of_seconds", evidence_frames=(int(start), int(end) - 1))
    by_zone = (over.groupby("zone")["t"].nunique() / n_seconds).sort_index() if n_seconds else pd.Series()
    headline = by_zone[[z.split("-")[0] in HEADLINE_THIRDS for z in by_zone.index]]
    if headline.empty:
        return Metric(**common, value=None, data={"by_zone": {z: float(v) for z, v in by_zone.items()}},
                      note=f"No middle- or final-third zone where {team_id} outnumbered the opponent "
                           f"by {margin}+ in this window.")

    zone = headline.idxmax()  # ties go to the alphabetically first zone (sorted index)
    in_zone = over[over["zone"] == zone]
    labels = in_zone["ours"].astype(str) + "v" + in_zone["theirs"].astype(str)
    typical = labels.value_counts().sort_index().idxmax()
    return Metric(**common, value=float(by_zone[zone]),
                  data={"zone": zone, "typical": typical, "by_zone": {z: float(v) for z, v in by_zone.items()}})
