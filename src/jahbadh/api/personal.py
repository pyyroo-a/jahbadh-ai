"""Personalisation that costs no model call: follow one player, or track one metric.

Player follow is computed numbers only: what one player did up to the clock. The narrative comes from claims
the Referee already approved (filtered in the browser), the precomputed spotlights, and in live mode a
spotlight on request. Single-metric mode reads the per-minute match state; METRIC_CHOICES says which state
field each choice plots and which metric names count as a claim "about" it.
"""

from pydantic import BaseModel

from jahbadh import analytics as an
from jahbadh.analytics.base import MATCH_END, metric_id
from jahbadh.schemas import Match, Metric


class PlayerFollow(BaseModel):
    player_id: str
    t: float
    on_pitch: bool
    impact: Metric
    heatmap: Metric
    physical: Metric
    passing: Metric
    event_ids: list[int]


class MetricChoice(BaseModel):
    key: str
    label: str
    state_field: str
    metric_names: list[str]


METRIC_CHOICES: dict[str, MetricChoice] = {c.key: c for c in (
    MetricChoice(key="xg", label="xG", state_field="xg", metric_names=["xg_total", "shot_map", "player_impact"]),
    MetricChoice(key="ppda", label="PPDA", state_field="ppda", metric_names=["ppda"]),
    MetricChoice(key="field_tilt", label="Field tilt", state_field="field_tilt", metric_names=["field_tilt"]),
    MetricChoice(key="momentum", label="Momentum", state_field="momentum", metric_names=["momentum"]),
    MetricChoice(key="pass_difficulty", label="Pass difficulty", state_field="pass_difficulty",
                 metric_names=["pass_quality"]),
    MetricChoice(key="rhythm", label="Game rhythm", state_field="rhythm", metric_names=["game_rhythm"]),
)}


def _empty(name: str, player_id: str, unit: str) -> Metric:
    return Metric(id=metric_id(name, player_id, 0, 0), name=name, subject=player_id, window=(0.0, 0.0),
                  value=None, unit=unit, note="Nothing has happened yet.")


def _on_pitch(match: Match, player_id: str, t: float) -> bool:
    frame = max(0, min(int(MATCH_END) - 1, int(t) - 1))
    tr = match.tracking
    return bool(((tr["entity_id"] == player_id) & (tr["t"] == frame)).any())


def player_follow(match: Match, player_id: str, t: float) -> PlayerFollow:
    """What one player has done in [0, t): impact, heatmap, running and passing, plus every event they're in."""
    if not 0 <= t <= MATCH_END:
        raise ValueError(f"time {t} must be between 0 and {MATCH_END:g}")
    impact = an.player_impact(match, player_id, 0, t) if t > 0 else None   # raises KeyError for unknown players
    if impact is None:
        an.player_physical(match, player_id, 0, 1)                         # same KeyError at kickoff
        metrics = [_empty("player_impact", player_id, "xGI"), _empty("heatmap", player_id, "samples"),
                   _empty("physical", player_id, "km"), _empty("pass_quality", player_id, "difficulty")]
    else:
        metrics = [impact, an.heatmap(match, player_id, 0, t), an.player_physical(match, player_id, 0, t),
                   an.pass_quality(match, player_id, 0, t)]
    events = [e.id for e in match.events if e.t < t and player_id in (e.player_id, e.related_player_id)]
    return PlayerFollow(player_id=player_id, t=t, on_pitch=_on_pitch(match, player_id, t), impact=metrics[0],
                        heatmap=metrics[1], physical=metrics[2], passing=metrics[3], event_ids=sorted(events))
