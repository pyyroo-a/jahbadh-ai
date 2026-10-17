"""Before/after comparisons around a moment, e.g. "since the 60th minute, X changed by Y"."""

from typing import Callable

from jahbadh.analytics.base import MATCH_END, metric_id
from jahbadh.schemas import Match, Metric


def before_after(fn: Callable[..., Metric | dict[str, Metric]], match: Match, subject: str, at_t: float,
                 window_s: float = 900, value_key: str | None = None) -> Metric:
    if not (0 < at_t < MATCH_END and window_s > 0):
        raise ValueError(f"window around {at_t} needs time on both sides inside the match and a positive length")
    b_start, a_end = max(0.0, at_t - window_s), min(MATCH_END, at_t + window_s)
    before, after = fn(match, subject, b_start, at_t), fn(match, subject, at_t, a_end)
    if value_key is not None:
        before, after = before[value_key], after[value_key]
    name = f"{before.name}_change"
    missing = before.value is None or after.value is None
    frames = [f for f in (before.evidence_frames, after.evidence_frames) if f is not None]
    return Metric(
        id=metric_id(name, subject, b_start, a_end, at=int(at_t), window=int(window_s)),
        name=name,
        subject=subject,
        window=(b_start, a_end),
        value=None if missing else after.value - before.value,
        unit=before.unit,
        evidence_event_ids=sorted(set(before.evidence_event_ids) | set(after.evidence_event_ids)),
        evidence_frames=(min(f[0] for f in frames), max(f[1] for f in frames)) if frames else None,
        data={"before": before.model_dump(), "after": after.model_dump(), "at_t": at_t},
        note="One side of the comparison has no value." if missing else None,
    )
