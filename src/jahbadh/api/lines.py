"""Template lines for every event, in English, Arabic and Spanish. No model, no cost.

Each line states exactly what the event records and nothing more. Names (players and teams) and formations go
in as they are and are never translated. A failed pass records no receiver and no reason (cut out, loose or out
of play), so its line only says it went astray. The minute is not in the line; the UI shows it next to it.
"""

from jahbadh.agents.contracts import Language
from jahbadh.schemas import Event, EventType, Match

LANGUAGES: tuple[Language, ...] = ("en", "ar", "es")

PHRASES: dict[str, dict[Language, str]] = {
    "kickoff": {"en": "Kick-off for {team}", "ar": "ركلة البداية لـ{team}", "es": "Saque inicial de {team}"},
    "pass": {"en": "{player} finds {other}", "ar": "{player} يمرر إلى {other}", "es": "{player} encuentra a {other}"},
    "pass_failed_to": {"en": "{player}'s pass to {other} goes astray", "ar": "تمريرة {player} إلى {other} لم تصل",
                       "es": "El pase de {player} a {other} no llega"},
    "pass_failed": {"en": "{player}'s pass goes astray", "ar": "تمريرة {player} لم تصل",
                    "es": "El pase de {player} no llega"},
    "carry": {"en": "{player} carries the ball forward", "ar": "{player} يتقدم بالكرة",
              "es": "{player} conduce el balón"},
    "carry_failed": {"en": "{player} loses the ball on the carry", "ar": "{player} يفقد الكرة أثناء التقدم",
                     "es": "{player} pierde el balón en la conducción"},
    "shot_scored": {"en": "{player} shoots and scores (xG {xg})", "ar": "{player} يسدد ويسجل (xG {xg})",
                    "es": "{player} dispara y marca (xG {xg})"},
    "shot": {"en": "{player} shoots, no goal (xG {xg})", "ar": "تسديدة من {player} دون هدف (xG {xg})",
             "es": "Disparo de {player}, sin gol (xG {xg})"},
    "goal": {"en": "GOAL! {player} scores for {team}", "ar": "هدف! {player} يسجل لـ{team}",
             "es": "¡GOL! {player} marca para {team}"},
    "pressure_on": {"en": "{player} presses {other}", "ar": "{player} يضغط على {other}",
                    "es": "{player} presiona a {other}"},
    "pressure": {"en": "{player} closes down", "ar": "{player} يضغط", "es": "{player} presiona"},
    "tackle_won": {"en": "{player} wins the ball with a tackle", "ar": "{player} يستخلص الكرة بتدخل",
                   "es": "{player} recupera el balón con una entrada"},
    "tackle_lost": {"en": "{player} goes in for the tackle but misses", "ar": "{player} يتدخل لكنه لا يستخلص الكرة",
                    "es": "{player} intenta la entrada pero no recupera el balón"},
    "interception": {"en": "{player} intercepts", "ar": "{player} يقطع الكرة", "es": "{player} intercepta el balón"},
    "interception_failed": {"en": "{player} can't cut it out", "ar": "{player} يفشل في قطع الكرة",
                            "es": "{player} no logra interceptar"},
    "foul_on": {"en": "Foul by {player} on {other}", "ar": "خطأ من {player} على {other}",
                "es": "Falta de {player} sobre {other}"},
    "foul": {"en": "Foul by {player}", "ar": "خطأ من {player}", "es": "Falta de {player}"},
    "yellow": {"en": "Yellow card for {player}", "ar": "بطاقة صفراء لـ{player}", "es": "Tarjeta amarilla para {player}"},
    "red": {"en": "Red card for {player}", "ar": "بطاقة حمراء لـ{player}", "es": "Tarjeta roja para {player}"},
    "substitution": {"en": "Substitution for {team}: {other} on, {player} off",
                     "ar": "تبديل في {team}: دخول {other} وخروج {player}", "es": "Cambio en {team}: entra {other}, sale {player}"},
    "formation_change": {"en": "{team} switch from {old} to {new}", "ar": "{team} يغير الخطة من {old} إلى {new}",
                         "es": "{team} pasa del {old} al {new}"},
    "press_higher": {"en": "{team} push their press higher", "ar": "{team} يرفع خط الضغط",
                     "es": "{team} sube su línea de presión"},
    "press_deeper": {"en": "{team} drop their press deeper", "ar": "{team} يخفض خط الضغط",
                     "es": "{team} baja su línea de presión"},
    "half_time": {"en": "Half time", "ar": "نهاية الشوط الأول", "es": "Descanso"},
    "full_time": {"en": "Full time", "ar": "نهاية المباراة", "es": "Final del partido"},
}


def _phrase(e: Event) -> str:
    t, ok, other = e.type, bool(e.outcome), e.related_player_id is not None
    if t == EventType.KICKOFF:
        return "kickoff"
    if t == EventType.PASS:
        return "pass" if ok and other else "pass_failed_to" if other else "pass_failed"
    if t == EventType.CARRY:
        return "carry" if ok else "carry_failed"
    if t == EventType.SHOT:
        return "shot_scored" if ok else "shot"
    if t == EventType.GOAL:
        return "goal"
    if t == EventType.PRESSURE:
        return "pressure_on" if other else "pressure"
    if t == EventType.TACKLE:
        return "tackle_won" if ok else "tackle_lost"
    if t == EventType.INTERCEPTION:
        return "interception" if ok else "interception_failed"
    if t == EventType.FOUL:
        return "foul_on" if other else "foul"
    if t == EventType.CARD:
        return "red" if e.detail.get("colour") == "red" else "yellow"
    if t == EventType.SUBSTITUTION:
        return "substitution"
    if t == EventType.FORMATION_CHANGE:
        return "formation_change"
    if t == EventType.TACTIC_CHANGE:
        higher = float(e.detail.get("press_height_to", 0)) > float(e.detail.get("press_height_from", 0))
        return "press_higher" if higher else "press_deeper"
    return "half_time" if e.period == 1 else "full_time"            # PERIOD_END


def event_lines(match: Match, e: Event) -> dict[Language, str]:
    teams = {t.id: t.name for t in (match.meta.home, match.meta.away)}
    names = {p.id: p.name for t in (match.meta.home, match.meta.away) for p in t.players}
    team = teams.get(e.team_id, e.team_id)
    values = {"team": team, "player": names.get(e.player_id or "", team),
              "other": names.get(e.related_player_id or "", ""), "xg": f"{e.xg or 0:.2f}",
              "old": str(e.detail.get("from", "")), "new": str(e.detail.get("to", ""))}
    phrase = PHRASES[_phrase(e)]
    return {lang: phrase[lang].format(**values) for lang in LANGUAGES}
