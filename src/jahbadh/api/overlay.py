"""A timed, machine-readable cue feed that a broadcast graphics system could draw over a match.

Each cue says when to show it (match_time, in match seconds), what it is, who it's about, the value, a short
caption in English, Arabic and Spanish, how long to keep it up, and the evidence behind it. Cues come from
three places and none of them calls a model:
- events: goals, cards, substitutions, formation and press changes, and big or fast shots
- metrics: running alerts (new top speeds, distance milestones) and changes in the game rhythm
- claims: the Referee-approved desk lines, reusing their existing renders

Values from the simulator's synthetic models (shot speed, tracking-based running) carry synthetic=True.
Names are inserted as they are and never translated.
"""

from typing import Literal

from pydantic import BaseModel

from jahbadh.agents.contracts import DeskRun, FeedItem, Language, Persona
from jahbadh.analytics import physical_alerts, rhythm_series
from jahbadh.schemas import Event, EventType, Match, Metric

CueType = Literal["goal", "card", "substitution", "formation_change", "tactic_change", "shot", "sprint_record",
                  "distance_milestone", "rhythm", "claim"]
LANGUAGES: tuple[Language, ...] = ("en", "ar", "es")

DURATION_S: dict[str, float] = {"goal": 12, "card": 8, "substitution": 8, "formation_change": 10, "tactic_change": 8,
                                "shot": 6, "sprint_record": 6, "distance_milestone": 6, "rhythm": 8, "claim": 10}
BIG_SHOT_XG = 0.3
FAST_SHOT_KMH = 100.0
RHYTHM_HOLD_MIN = 3          # a new rhythm label is announced once it has held this many minutes
RHYTHM_FULL_WINDOW_S = 600   # before 10 minutes the rhythm window is still filling up

CUE_PHRASES: dict[str, dict[Language, str]] = {
    "goal": {"en": "GOAL · {player} ({team})", "ar": "هدف · {player} ({team})", "es": "GOL · {player} ({team})"},
    "yellow": {"en": "Yellow card · {player}", "ar": "بطاقة صفراء · {player}", "es": "Tarjeta amarilla · {player}"},
    "red": {"en": "Red card · {player}", "ar": "بطاقة حمراء · {player}", "es": "Tarjeta roja · {player}"},
    "substitution": {"en": "Substitution · {on} on, {off} off", "ar": "تبديل · دخول {on} وخروج {off}",
                     "es": "Cambio · entra {on}, sale {off}"},
    "formation_change": {"en": "{team} switch to {to}", "ar": "{team} يغير الخطة إلى {to}", "es": "{team} pasa al {to}"},
    "press_higher": {"en": "{team} press higher", "ar": "{team} يرفع خط الضغط", "es": "{team} sube su línea de presión"},
    "press_deeper": {"en": "{team} drop deeper", "ar": "{team} يخفض خط الضغط", "es": "{team} baja su línea de presión"},
    "big_chance": {"en": "Big chance · {player}, xG {xg}", "ar": "فرصة كبيرة · {player}، xG {xg}",
                   "es": "Ocasión clara · {player}, xG {xg}"},
    "fast_shot": {"en": "Shot at {kmh} km/h · {player}", "ar": "تسديدة بسرعة {kmh} كم/س · {player}",
                  "es": "Disparo a {kmh} km/h · {player}"},
    "sprint_record": {"en": "Top speed · {player} {kmh} km/h", "ar": "أعلى سرعة · {player} {kmh} كم/س",
                      "es": "Velocidad máxima · {player} {kmh} km/h"},
    "distance_milestone": {"en": "{player} has run {km} km", "ar": "{player} قطع {km} كم",
                           "es": "{player} ya ha recorrido {km} km"},
    "rhythm": {"en": "Game rhythm: {label}", "ar": "إيقاع المباراة: {label}", "es": "Ritmo de juego: {label}"},
}
RHYTHM_LABELS: dict[str, dict[Language, str]] = {
    "controlled": {"en": "controlled", "ar": "منضبط", "es": "controlado"},
    "balanced": {"en": "balanced", "ar": "متوازن", "es": "equilibrado"},
    "chaotic": {"en": "chaotic", "ar": "فوضوي", "es": "caótico"},
}


class OverlayCue(BaseModel):
    id: str
    match_time: float
    minute: int
    type: CueType
    team_id: str | None = None
    player_id: str | None = None
    value: float | None = None
    unit: str | None = None
    text: dict[Language, str]
    duration_s: float
    event_ids: list[int] = []
    metric_ids: list[str] = []
    source: Literal["event", "metric", "claim"]
    synthetic: bool = False
    precomputed: bool = True


def _minute(t: float) -> int:
    return min(90, int(t // 60) + 1)


def _say(phrase: str, **values: str) -> dict[Language, str]:
    return {lang: CUE_PHRASES[phrase][lang].format(**values) for lang in LANGUAGES}


def _cue(type: CueType, t: float, text: dict[Language, str], source: str, precomputed: bool, id: str, **kw) -> OverlayCue:
    return OverlayCue(id=id, match_time=t, minute=_minute(t), type=type, text=text, duration_s=DURATION_S[type],
                      source=source, precomputed=precomputed, **kw)


def _names(match: Match) -> tuple[dict[str, str], dict[str, str]]:
    teams = (match.meta.home, match.meta.away)
    return {p.id: p.name for t in teams for p in t.players}, {t.id: t.name for t in teams}


def _team_of(match: Match) -> dict[str, str]:
    return {p.id: t.id for t in (match.meta.home, match.meta.away) for p in t.players}


def _event_cue(match: Match, e: Event, players: dict[str, str], teams: dict[str, str],
               precomputed: bool) -> OverlayCue | None:
    who, team = players.get(e.player_id or "", ""), teams[e.team_id]
    base = dict(id=f"event-{e.id}", team_id=e.team_id, player_id=e.player_id, event_ids=[e.id], source="event",
                precomputed=precomputed)
    if e.type == EventType.GOAL:
        shot = int(e.detail["shot_id"]) if "shot_id" in e.detail else None
        return _cue("goal", e.t, _say("goal", player=who, team=team),
                    **base | {"event_ids": sorted({e.id} | ({shot} if shot else set()))})
    if e.type == EventType.CARD:
        colour = "red" if e.detail.get("colour") == "red" else "yellow"
        return _cue("card", e.t, _say(colour, player=who), **base)
    if e.type == EventType.SUBSTITUTION:
        return _cue("substitution", e.t, _say("substitution", on=players.get(e.related_player_id or "", ""), off=who),
                    **base)
    if e.type == EventType.FORMATION_CHANGE:
        return _cue("formation_change", e.t, _say("formation_change", team=team, to=str(e.detail.get("to"))), **base)
    if e.type == EventType.TACTIC_CHANGE:
        higher = float(e.detail.get("press_height_to", 0)) > float(e.detail.get("press_height_from", 0))
        return _cue("tactic_change", e.t, _say("press_higher" if higher else "press_deeper", team=team), **base)
    if e.type == EventType.SHOT and not e.outcome:          # a scored shot gets the goal cue instead
        xg, kmh = e.xg or 0.0, e.detail.get("speed_kmh")
        if xg >= BIG_SHOT_XG:
            return _cue("shot", e.t, _say("big_chance", player=who, xg=f"{xg:.2f}"), **base, value=xg, unit="xG")
        if kmh is not None and float(kmh) >= FAST_SHOT_KMH:
            return _cue("shot", e.t, _say("fast_shot", player=who, kmh=f"{float(kmh):.0f}"), **base,
                        value=float(kmh), unit="km/h", synthetic=True)
    return None


def event_cues(match: Match, precomputed: bool = True) -> list[OverlayCue]:
    players, teams = _names(match)
    cues = (_event_cue(match, e, players, teams, precomputed) for e in match.events)
    return [c for c in cues if c is not None]


def _alert_cue(alert: Metric, players: dict[str, str], team_of: dict[str, str], precomputed: bool) -> OverlayCue:
    t = float(alert.evidence_frames[1])
    who = players.get(alert.subject, alert.subject)
    if alert.name == "sprint_record":
        text = _say("sprint_record", player=who, kmh=f"{alert.value:.1f}")
    else:
        text = _say("distance_milestone", player=who, km=f"{alert.value:.0f}")
    return _cue(alert.name, t, text, "metric", precomputed, id=f"metric-{alert.id}", player_id=alert.subject,
                team_id=team_of.get(alert.subject),
                value=alert.value, unit=alert.unit, metric_ids=[alert.id], synthetic=True)


def _rhythm_cues(match: Match, precomputed: bool) -> list[OverlayCue]:
    series = [m for m in rhythm_series(match) if m.window[1] >= RHYTHM_FULL_WINDOW_S]
    cues, said = [], None
    for i in range(RHYTHM_HOLD_MIN - 1, len(series)):
        held = {m.data["label"] for m in series[i - RHYTHM_HOLD_MIN + 1:i + 1]}
        label = series[i].data["label"]
        if len(held) == 1 and label != said:
            m = series[i]
            text = {lang: CUE_PHRASES["rhythm"][lang].format(label=RHYTHM_LABELS[label][lang]) for lang in LANGUAGES}
            cues.append(_cue("rhythm", m.window[1], text, "metric", precomputed, id=f"metric-{m.id}", value=m.value,
                             unit=m.unit, metric_ids=[m.id]))
            said = label
    return cues


def metric_cues(match: Match, precomputed: bool = True) -> list[OverlayCue]:
    players, _ = _names(match)
    team_of = _team_of(match)
    alerts = [_alert_cue(a, players, team_of, precomputed) for a in physical_alerts(match)]
    return sorted(alerts + _rhythm_cues(match, precomputed), key=lambda c: c.match_time)


def claim_cues(item: FeedItem, at: float, persona: Persona = "pundit", precomputed: bool = True) -> list[OverlayCue]:
    """One cue per approved claim, in the chosen persona's words, falling back to English for a missing language."""
    renders = {(r.claim_id, r.persona, r.language): r.text for r in item.renders}
    cues = []
    for c in item.claims:
        english = renders.get((c.id, persona, "en"), renders.get((c.id, "pundit", "en"), c.text))
        text = {lang: renders.get((c.id, persona, lang), english) for lang in LANGUAGES}
        cues.append(_cue("claim", at, text, "claim", precomputed, id=f"claim-{c.id}", team_id=item.moment.team_id,
                         player_id=item.moment.player_id, event_ids=list(c.event_ids), metric_ids=list(c.metric_ids)))
    return cues


def overlay_cues(match: Match, desk: DeskRun | None, lag_s: float = 20.0) -> list[OverlayCue]:
    """The whole match's cues in time order; claim cues appear when their moment publishes (moment.t + lag_s)."""
    cues = event_cues(match) + metric_cues(match)
    for item in desk.items if desk else []:
        cues += claim_cues(item, at=item.moment.t + lag_s)
    return sorted(cues, key=lambda c: (c.match_time, c.id))
