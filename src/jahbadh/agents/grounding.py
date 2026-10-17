"""Referee layer 1: the deterministic grounding check. No LLM, so it is fast, free and can't be argued with.

A claim passes only if every id it cites exists (and is not in the future), every figure matches its
metric at the precision it is written, every minute, duration, formation and score in the text is backed
by the evidence, and no other number is left over.
"""

import re

from jahbadh.agents.contracts import Claim, Figure
from jahbadh.agents.evidence import EvidenceStore, is_share, resolve, score_at
from jahbadh.agents.numbers import NUMBER, number_matches
from jahbadh.schemas import Event, EventType, Match, Metric

MINUTE_PATTERNS = [re.compile(r"(?<![\d.])(\d{1,2})['’]"),
                   re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)[- ]minute\b"),
                   re.compile(r"\bminute (\d{1,2})\b")]
DURATION = re.compile(r"\b(\d{1,2}) minutes?\b")
FORMATION = re.compile(r"\b\d(?:-\d){2,3}\b")
SCORE = re.compile(r"\b(\d{1,2})-(\d{1,2})\b")
FIELD_NAME = re.compile(r"\b[a-z]+(?:_[a-z]+)+\b")      # e.g. home_threat: written for code, not viewers


def occurrence(written: str, text: str) -> re.Match | None:
    """`written` as a whole number in text: "3" is not found inside "13" or "3.5"."""
    return re.search(r"(?<![\d.])" + re.escape(written) + r"(?!\d|\.\d)", text)


def _cut(text: str, span: tuple[int, int]) -> str:
    return text[:span[0]] + " " + text[span[1]:]


def _broadcast(t: float) -> int:
    return int(t // 60) + 1


def _metric_minutes(m: Metric) -> set[int]:
    start, end = m.window
    minutes = {_broadcast(start), _broadcast(end - 1)}
    if isinstance(m.data.get("at_t"), (int, float)):
        minutes.add(_broadcast(m.data["at_t"]))
    return minutes


def _metric_durations(m: Metric) -> set[float]:
    start, end = m.window
    durations = {(end - start) / 60}
    at_t = m.data.get("at_t")
    if isinstance(at_t, (int, float)):
        durations |= {(at_t - start) / 60, (end - at_t) / 60}
    return durations


def _formations(match: Match, horizon: float) -> set[str]:
    known = {match.meta.home.formation, match.meta.away.formation}
    for e in match.events:
        if e.type == EventType.FORMATION_CHANGE and e.t < horizon:
            known |= {str(e.detail.get("from")), str(e.detail.get("to"))}
    return known


EVENT_FIELDS = ("xg",)


def _figure_source(fig: Figure, claim: Claim, store: EvidenceStore,
                   known_events: dict[int, Event]) -> tuple[bool, float | str | None, bool]:
    """(is the figure's source cited evidence, the value it points at, may it be a percentage).
    A figure cites a metric field, or "event:<id>" with field "xg" for a shot's xG from its event line."""
    if fig.metric_id.startswith("event:"):
        raw = fig.metric_id.removeprefix("event:")
        event = known_events.get(int(raw)) if raw.isdigit() else None
        if event is None:
            return False, None, False
        return True, getattr(event, fig.field) if fig.field in EVENT_FIELDS else None, False
    if fig.metric_id not in claim.metric_ids or fig.metric_id not in store:
        return False, None, False
    metric = store.get(fig.metric_id)
    try:
        return True, resolve(metric, fig.field), is_share(metric, fig.field)
    except KeyError:
        return True, None, False


def check_claim(claim: Claim, match: Match, store: EvidenceStore, horizon: float) -> list[str]:
    reasons: list[str] = []
    if not claim.metric_ids and not claim.event_ids:
        reasons.append("no evidence cited")

    metrics = []
    for mid in claim.metric_ids:
        if mid in store:
            metrics.append(store.get(mid))
        else:
            reasons.append(f"unknown metric {mid}")
    events = []
    for eid in claim.event_ids:
        try:
            e = match.event(eid)
        except KeyError:
            reasons.append(f"unknown event {eid}")
            continue
        if e.t >= horizon:
            reasons.append(f"event {eid} is after this moment")
        else:
            events.append(e)

    text = claim.text
    known_events = {e.id: e for e in events}
    for fig in claim.figures:
        found = occurrence(fig.written, text)
        cited, value, share = _figure_source(fig, claim, store, known_events)
        if not cited:
            reasons.append(f"figure cites {fig.metric_id} which is not in the evidence")
        elif found is None:
            reasons.append(f"'{fig.written}' is not in the text")
        else:
            if value is None:
                reasons.append(f"{fig.metric_id} has no field {fig.field}")
            elif "%" in fig.written and not share:
                reasons.append(f"'{fig.written}' is a percentage but {fig.metric_id} {fig.field} is not a share")
            elif not number_matches(fig.written, value):
                shown = f"{value:.3f}" if isinstance(value, float) else value
                reasons.append(f"'{fig.written}' does not match {fig.metric_id} {fig.field} = {shown}")
        if found is not None:
            text = _cut(text, found.span())

    allowed_minutes = {e.minute for e in events} | {mm for m in metrics for mm in _metric_minutes(m)}
    for pattern in MINUTE_PATTERNS:
        while found := pattern.search(text):
            if int(found.group(1)) not in allowed_minutes:
                reasons.append(f"minute {found.group(1)}' is not backed by the evidence")
            text = _cut(text, found.span())

    durations = {d for m in metrics for d in _metric_durations(m)}
    while found := DURATION.search(text):
        if not any(abs(int(found.group(1)) - d) < 1e-6 for d in durations):
            reasons.append(f"unsupported duration '{found.group(0)}'")
        text = _cut(text, found.span())

    formations = _formations(match, horizon)
    for found in reversed(list(FORMATION.finditer(text))):
        if found.group(0) in formations:
            text = _cut(text, found.span())

    score = score_at(match, horizon)
    goals = list(score.values())
    allowed_scores = {f"{goals[0]}-{goals[1]}", f"{goals[1]}-{goals[0]}"}
    for found in reversed(list(SCORE.finditer(text))):
        if found.group(0) in allowed_scores:
            text = _cut(text, found.span())

    reasons += [f"unsupported number '{token}'" for token in NUMBER.findall(text)]
    reasons += [f"field name '{name}' in the text" for name in FIELD_NAME.findall(claim.text)]
    return reasons
