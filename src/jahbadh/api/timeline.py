"""One ordered timeline per match: every event with its lines, a match state every minute, overlay cues and the
desk's moments.

Everything is cut at the clock: a state at t only uses data before t, so a timeline played up to any second
never shows the future. Replay adds the precomputed desk: "thinking" when a moment starts and its feed item
REPLAY_DESK_LAG_S match seconds later, so the desk visibly works even though the output is already made. A claim
cue follows its feed item at the same second, so a graphics client never shows a line the desk hasn't published.
"""

from jahbadh import analytics as an
from jahbadh.agents.evidence import formation_at, score_at
from jahbadh.api.lines import event_lines
from jahbadh.api.overlay import claim_cues, event_cues, metric_cues
from jahbadh.api.showcase import Showcase
from jahbadh.api.stream import EventLine, MatchState, StreamEnd, StreamItem
from jahbadh.schemas import Event, Match

REPLAY_DESK_LAG_S = 20.0
STATE_STEP_S = 60
STATE_WINDOW_S = 600
MATCH_END = 5400
ORDER = {"event": 0, "cue": 0, "thinking": 1, "state": 2, "feed": 3, "failure": 3, "end": 9}
CLAIM_CUE_ORDER = 4                       # right after the feed item it quotes


def _minute(t: float) -> int:
    return min(90, int(t // 60) + 1)


def match_state(match: Match, t: float) -> MatchState:
    teams = [match.meta.home.id, match.meta.away.id]
    formations = {team: formation_at(match, team, t) for team in teams}
    if t <= 0:
        return MatchState(t=0.0, minute=1, score={team: 0 for team in teams}, xg={team: 0.0 for team in teams},
                          momentum=None, field_tilt=None, ppda={team: None for team in teams}, shape={},
                          formations=formations, rhythm=None, pass_difficulty={team: None for team in teams})
    start = max(0.0, t - STATE_WINDOW_S)
    return MatchState(
        t=float(t), minute=_minute(t), score=score_at(match, t),
        xg={team: float(an.xg_total(match, team, 0, t).value or 0.0) for team in teams},
        momentum=an.momentum(match, t, STATE_WINDOW_S).value,
        field_tilt=an.field_tilt(match, teams[0], start, t).value,
        ppda={team: an.ppda(match, team, start, t).value for team in teams},
        shape={team: an.average_positions(match, team, start, t) for team in teams},
        formations=formations, rhythm=an.game_rhythm(match, start, t),
        pass_difficulty={team: an.pass_quality(match, team, start, t).value for team in teams})


def event_line(match: Match, e: Event) -> EventLine:
    return EventLine(id=e.id, t=e.t, minute=e.minute, type=e.type, team_id=e.team_id, player_id=e.player_id,
                     related_player_id=e.related_player_id, x=e.x, y=e.y, end_x=e.end_x, end_y=e.end_y,
                     outcome=e.outcome, xg=e.xg, lines=event_lines(match, e))


def _order(i: StreamItem) -> int:
    return CLAIM_CUE_ORDER if i.kind == "cue" and i.data.source == "claim" else ORDER[i.kind]


def _sorted(items: list[StreamItem]) -> list[StreamItem]:
    return sorted(items, key=lambda i: (i.t, _order(i)))       # stable: events keep their id order


def match_timeline(match: Match) -> list[StreamItem]:
    items = [StreamItem(t=e.t, kind="event", data=event_line(match, e)) for e in match.events]
    items += [StreamItem(t=float(t), kind="state", data=match_state(match, t))
              for t in range(0, MATCH_END + 1, STATE_STEP_S)]
    items += [StreamItem(t=c.match_time, kind="cue", data=c) for c in event_cues(match) + metric_cues(match)]
    return _sorted(items)


def replay_timeline(show: Showcase) -> list[StreamItem]:
    items = match_timeline(show.match)
    for item in show.desk.items:
        items.append(StreamItem(t=item.moment.t, kind="thinking", data=item.moment))
        at = item.moment.t + REPLAY_DESK_LAG_S
        items.append(StreamItem(t=at, kind="feed", data=item))
        items += [StreamItem(t=at, kind="cue", data=c) for c in claim_cues(item, at=at)]
    items = _sorted(items)
    return items + [StreamItem(t=items[-1].t, kind="end", data=StreamEnd(reason="full_time"))]
