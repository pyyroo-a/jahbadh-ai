"""The analytics library as agent tools.

Tools take clock minutes (0 to 90; the switch on the hour is minute 60) and never see past the
moment's horizon, so live commentary can't leak the future. Each tool records every metric it computes
in the moment's EvidenceStore and returns a compact JSON summary. Errors come back as {"error": ...}
for the model to read, never as exceptions.

xg_timeline and momentum_series are left out on purpose: they are whole-match chart series for the
UI, and in live mode they would show the agents the future.
"""

import functools
import json
from collections.abc import Callable
from typing import Literal

from jahbadh import analytics as an
from jahbadh.agents.evidence import EvidenceStore, describe_event, summarize
from jahbadh.schemas import EventType, Match, Metric

MAX_EVENT_LINES = 40
MAX_ALERTS = 15
NOISY_EVENTS = (EventType.PRESSURE, EventType.CARRY)

ChangeMetric = Literal["xg", "field_tilt", "ppda", "midfield_control", "zone_overloads", "line_height", "length",
                       "width", "player_impact"]
RankBy = Literal["value", "progressive_passes", "ball_wins", "final_third_entries", "xa", "xg", "pressures"]

ANALYST_TOOLS = ("list_events", "get_xg", "get_momentum", "get_match_stats", "get_player_impact", "rank_players")


def _safe(fn: Callable[..., str]) -> Callable[..., str]:
    @functools.wraps(fn)
    def wrapper(*args, **kwargs) -> str:
        try:
            return fn(*args, **kwargs)
        except (KeyError, ValueError) as e:
            return json.dumps({"error": str(e).strip("'\"")})
    return wrapper


def make_tools(match: Match, store: EvidenceStore, horizon: float) -> dict[str, Callable[..., str]]:
    def window(from_minute: float, to_minute: float) -> tuple[float, float]:
        start, end = max(0.0, from_minute * 60), min(to_minute * 60, horizon)
        if start >= end:
            raise ValueError(f"empty window: minutes {from_minute} to {to_minute}, and data stops at "
                             f"minute {horizon / 60:.2f}")
        return start, end

    def keep(metric: Metric) -> dict:
        return summarize(store.add(metric))

    def out(value: dict | list) -> str:
        return json.dumps(value)

    @_safe
    def list_events(from_minute: float = 0, to_minute: float = 90, event_type: str | None = None,
                    team_id: str | None = None) -> str:
        """List match events as one-line descriptions (id, broadcast minute, team, type, players, details),
        latest last, at most 40. event_type is one of PASS, CARRY, SHOT, GOAL, TACKLE, INTERCEPTION, PRESSURE,
        FOUL, CARD, SUBSTITUTION, FORMATION_CHANGE, TACTIC_CHANGE. PRESSURE and CARRY are left out unless asked for."""
        start, end = window(from_minute, to_minute)
        wanted = EventType(event_type.upper()) if event_type else None
        if team_id is not None:
            match.team(team_id)
        events = [e for e in match.events_of(wanted, team_id, start, end) if wanted or e.type not in NOISY_EVENTS]
        return out([describe_event(match, e) for e in events[-MAX_EVENT_LINES:]])

    @_safe
    def get_xg(team_id: str, from_minute: float = 0, to_minute: float = 90) -> str:
        """Total expected goals (xG) of a team's shots in a window. Higher means better chances created."""
        return out(keep(an.xg_total(match, team_id, *window(from_minute, to_minute))))

    @_safe
    def get_momentum(at_minute: float, window_minutes: float = 10) -> str:
        """Home team's share of attacking threat (shot xG plus final-third passes) over the window_minutes
        before at_minute. 0.5 is even, above 0.5 the home team is on top, below 0.5 the away team."""
        at_t = min(at_minute * 60, horizon)
        return out(keep(an.momentum(match, at_t, window_minutes * 60)))

    @_safe
    def get_field_tilt(team_id: str, from_minute: float = 0, to_minute: float = 90) -> str:
        """Team's share of both teams' successful final-third passes: who is pinning whom back. 0.5 is even."""
        return out(keep(an.field_tilt(match, team_id, *window(from_minute, to_minute))))

    @_safe
    def get_ppda(defending_team_id: str, from_minute: float = 0, to_minute: float = 90) -> str:
        """Passes per defensive action (PPDA): opponent passes allowed in their own defensive 60% per tackle,
        interception or foul there by the defending team. Lower means a more intense press."""
        return out(keep(an.ppda(match, defending_team_id, *window(from_minute, to_minute))))

    @_safe
    def get_shape(team_id: str, from_minute: float = 0, to_minute: float = 90) -> str:
        """Team shape in metres, median over the window: line_height (how high the defensive line sits, from
        the team's own goal), length (depth of the outfield block) and width (how wide it stretches)."""
        metrics = an.shape(match, team_id, *window(from_minute, to_minute))
        return out([keep(metrics[k]) for k in ("line_height", "length", "width")])

    @_safe
    def get_heatmap(subject_id: str, from_minute: float = 0, to_minute: float = 90) -> str:
        """Where a team or player (subject_id) spent its time, as the top zones (third and lane, from that
        team's attacking point of view, left is the attacking left) with their share of samples."""
        return out(keep(an.heatmap(match, subject_id, *window(from_minute, to_minute))))

    @_safe
    def get_average_positions(team_id: str, from_minute: float = 0, to_minute: float = 90) -> str:
        """Average x, y position in metres of each of a team's players, in the team's attacking direction
        (x toward the opponent goal at 105, y from 0 on the right to 68 on the left)."""
        return out(keep(an.average_positions(match, team_id, *window(from_minute, to_minute))))

    @_safe
    def get_zone_overloads(team_id: str, from_minute: float = 0, to_minute: float = 90, margin: int = 2) -> str:
        """Where a team outnumbered the opponent's outfield players by at least margin, as a share of seconds.
        Headline zone comes from the middle and final thirds; typical gives the usual count like 4v2."""
        start, end = window(from_minute, to_minute)
        return out(keep(an.zone_overloads(match, team_id, start, end, margin=margin)))

    @_safe
    def get_pass_network(team_id: str, from_minute: float = 0, to_minute: float = 90) -> str:
        """Who passes to whom: the strongest passing links (passer, receiver, count) for a team."""
        return out(keep(an.pass_network(match, team_id, *window(from_minute, to_minute))))

    @_safe
    def get_midfield_control(team_id: str, from_minute: float = 0, to_minute: float = 90) -> str:
        """Descriptive share of the middle third: ball (passes), numbers (players present) and duels won.
        It describes the midfield; never use it as the cause of anything."""
        return out(keep(an.midfield_control(match, team_id, *window(from_minute, to_minute))))

    @_safe
    def compare_before_after(metric: ChangeMetric, subject_id: str, at_minute: float,
                             window_minutes: float = 15) -> str:
        """Change in a metric for a team (or a player, for player_impact) after at_minute versus before it,
        over equal windows on each side. value is after minus before; before.value and after.value are the
        two sides. Windows shrink to the data available on both sides."""
        at_t = at_minute * 60
        window_s = min(window_minutes * 60, at_t, horizon - at_t)
        if window_s <= 0:
            raise ValueError(f"no data on both sides of minute {at_minute} yet")
        if metric in ("line_height", "length", "width"):
            return out(keep(an.before_after(an.shape, match, subject_id, at_t, window_s, value_key=metric)))
        fn = {"xg": an.xg_total, "field_tilt": an.field_tilt, "ppda": an.ppda, "midfield_control": an.midfield_control,
              "zone_overloads": an.zone_overloads, "player_impact": an.player_impact}[metric]
        return out(keep(an.before_after(fn, match, subject_id, at_t, window_s)))

    @_safe
    def get_match_stats(team_id: str, period: Literal["first_half", "second_half", "match"] = "match") -> str:
        """A team's match stats for the first half (0 to 45), second half (45 to 90) or whole match: shots,
        shots inside and outside the penalty box, goals, xG, fouls committed, yellow cards, passes and pass
        completion."""
        start, end = {"first_half": (0, 45), "second_half": (45, 90), "match": (0, 90)}[period]
        return out(keep(an.match_stats(match, team_id, *window(start, end))))

    @_safe
    def get_shot_map(team_id: str, from_minute: float = 0, to_minute: float = 90) -> str:
        """Every shot by a team: id, broadcast minute, shooter, xG, goal or not, inside the penalty box or not,
        and synthetic shot speed in km/h. Cite one shot's xG with field "shots.<id>.xg", its speed "shots.<id>.speed_kmh"."""
        return out(keep(an.shot_map(match, team_id, *window(from_minute, to_minute))))

    @_safe
    def get_attacking_sides(team_id: str, from_minute: float = 0, to_minute: float = 90) -> str:
        """Where a team's attacks went: shares of successful passes and carries into the final third that ended
        on the left, centre or right (from that team's point of view); side is the busiest lane."""
        return out(keep(an.attacking_sides(match, team_id, *window(from_minute, to_minute))))

    @_safe
    def get_player_impact(player_id: str, from_minute: float = 0, to_minute: float = 90) -> str:
        """One player's contribution: value is expected goal involvement (xG + xA); fields also hold touches,
        passes, pass completion, progressive passes, final-third entries, shots, goals, assists, ball wins,
        pressures and minutes played."""
        return out(keep(an.player_impact(match, player_id, *window(from_minute, to_minute))))

    @_safe
    def rank_players(by: RankBy = "value", team_id: str | None = None, from_minute: float = 0,
                     to_minute: float = 90, n: int = 3) -> str:
        """Top n players (both teams, or one team) by a player impact field. value is expected goal
        involvement; ball_wins and progressive_passes find the quieter standouts."""
        start, end = window(from_minute, to_minute)
        ranked = an.player_rankings(match, team_id, start, end, by=by, n=max(1, min(n, 10)))
        return out([keep(m) for m in ranked])

    @_safe
    def get_physical(player_id: str, from_minute: float = 0, to_minute: float = 90) -> str:
        """One player's running: distance covered in km (value), top speed in km/h and when, and minutes on the
        pitch. From the synthetic 1 Hz tracking; jumps faster than any run are left out and counted."""
        return out(keep(an.player_physical(match, player_id, *window(from_minute, to_minute))))

    @_safe
    def get_physical_alerts(to_minute: float = 90) -> str:
        """Name-tagged running alerts up to to_minute, latest last (at most 15): sprint_record when a player sets
        a new match-wide top speed of at least 30 km/h, distance_milestone when a player first passes 5 or 10 km."""
        alerts = an.physical_alerts(match, end=min(to_minute * 60, horizon))
        return out([keep(m) for m in alerts[-MAX_ALERTS:]])

    @_safe
    def get_pass_quality(subject_id: str, from_minute: float = 0, to_minute: float = 90) -> str:
        """Passing by a team or player: attempted, completed, accuracy, mean length in metres and mean difficulty
        (value, 0 easy to 1 hard, from the simulator's own success odds), plus the hardest completed pass."""
        return out(keep(an.pass_quality(match, subject_id, *window(from_minute, to_minute))))

    @_safe
    def get_game_rhythm(from_minute: float = 0, to_minute: float = 90) -> str:
        """How settled the match is: possession changes per minute (value), passes per minute, passes per
        possession, and label (controlled, balanced or chaotic, against thresholds measured over ten matches)."""
        return out(keep(an.game_rhythm(match, *window(from_minute, to_minute))))

    tools = [list_events, get_xg, get_momentum, get_field_tilt, get_ppda, get_shape, get_heatmap,
             get_average_positions, get_zone_overloads, get_pass_network, get_midfield_control,
             compare_before_after, get_match_stats, get_shot_map, get_attacking_sides, get_player_impact, rank_players,
             get_physical, get_physical_alerts, get_pass_quality, get_game_rhythm]
    return {fn.__name__: fn for fn in tools}


TACTICAL_TOOLS = ("list_events", "get_xg", "get_momentum", "get_field_tilt", "get_ppda", "get_shape", "get_heatmap",
                  "get_average_positions", "get_zone_overloads", "get_pass_network", "get_midfield_control",
                  "compare_before_after", "get_match_stats", "get_shot_map", "get_attacking_sides", "get_player_impact",
                  "rank_players", "get_physical", "get_physical_alerts", "get_pass_quality", "get_game_rhythm")
