"""Tactical analytics. Every function returns Metric objects carrying their evidence."""

from jahbadh.analytics.compare import before_after
from jahbadh.analytics.momentum import momentum, momentum_series
from jahbadh.analytics.networks import pass_network
from jahbadh.analytics.overloads import zone_overloads
from jahbadh.analytics.positional import average_positions, heatmap, shape
from jahbadh.analytics.shots import xg_timeline, xg_total
from jahbadh.analytics.territory import field_tilt, ppda

__all__ = [
    "average_positions", "before_after", "field_tilt", "heatmap", "momentum", "momentum_series",
    "pass_network", "ppda", "shape", "xg_timeline", "xg_total", "zone_overloads",
]
