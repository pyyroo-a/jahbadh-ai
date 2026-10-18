"""Tactical analytics. Every function returns Metric objects carrying their evidence."""

from jahbadh.analytics.compare import before_after
from jahbadh.analytics.midfield import midfield_control
from jahbadh.analytics.momentum import momentum, momentum_series
from jahbadh.analytics.networks import pass_network
from jahbadh.analytics.overloads import zone_overloads
from jahbadh.analytics.physical import physical_alerts, player_physical
from jahbadh.analytics.players import player_impact, player_rankings
from jahbadh.analytics.positional import average_positions, heatmap, shape
from jahbadh.analytics.shots import xg_timeline, xg_total
from jahbadh.analytics.stats import attacking_sides, match_stats, shot_map
from jahbadh.analytics.territory import field_tilt, ppda

__all__ = [
    "attacking_sides", "average_positions", "before_after", "field_tilt", "heatmap", "match_stats", "midfield_control", "momentum", "momentum_series",
    "pass_network", "physical_alerts", "player_impact", "player_physical", "player_rankings", "ppda", "shape", "shot_map", "xg_timeline", "xg_total", "zone_overloads",
]
