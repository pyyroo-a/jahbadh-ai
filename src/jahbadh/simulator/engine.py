"""Tick-based match engine: one tick per second, 5400 ticks per match.

Each tick: dead-ball pauses count down, the ball carrier may act (shot,
carry or pass), the defending team may press, tackle or foul, then both
teams move and 23 tracking rows (22 players + ball) are recorded.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from jahbadh.pitch import LENGTH, WIDTH, attack_x, clamp, third
from jahbadh.schemas import Event, EventType, Match, MatchMeta, ScriptedChange, Team
from jahbadh.simulator.formations import slots_for
from jahbadh.simulator.movement import TeamState, step_positions
from jahbadh.simulator.storyline import apply_due_changes
from jahbadh.simulator.teams import DEFAULT_TEAMS, TeamSpec, make_team
from jahbadh.simulator.xg import shot_xg

MATCH_SECONDS = 5400
HALF_SECONDS = 2700

# Starting constants, tuned in Task 7 against top-flight stat ranges.
ACT_BASE, ACT_TEMPO = 0.30, 0.25
CARRY_PROB = 0.15
SHOT_ZONE_AX = 80.0
SHOT_XG_MULT, SHOT_PROB_CAP = 2.0, 0.5
PASS_BASE, PASS_LENGTH_PEN, PASS_PRESSURE_PEN, PASS_FINAL_THIRD_PEN = 0.93, 0.20, 0.15, 0.08
PASS_DISTANCE_SCALE = 20.0
INTERCEPT_SHARE = 0.70
PRESSURE_RADIUS = 2.5
PRESSURE_BASE, PRESSURE_PRESS = 0.25, 0.40
TACKLE_PROB, TACKLE_WIN = 0.06, 0.5
FOUL_PROB, CARD_PROB = 0.012, 0.12
GK_CATCH_SHARE = 0.6
DRIBBLE_MAX = 2.0
PAUSE_OUT, PAUSE_FOUL, PAUSE_GOAL = (20, 40), (25, 45), 60


@dataclass
class _State:
    possession: str
    carrier: int | None            # index into the possession team's on_pitch
    ball: np.ndarray               # (2,) pitch coordinates
    pause: int = 0
    restart: tuple[str, str] | None = None   # (team_id, "kickoff" | "gk" | "nearest")
    pressured_logged: bool = False
    booked: set[str] = field(default_factory=set)


class _Engine:
    def __init__(self, seed: int, match_id: str, storyline: list[ScriptedChange],
                 home_spec: TeamSpec, away_spec: TeamSpec):
        self.rng = np.random.default_rng(seed)
        self.seed, self.match_id, self.storyline = seed, match_id, storyline
        self.teams: dict[str, Team] = {}
        self.states: dict[str, TeamState] = {}
        for spec, is_home in ((home_spec, True), (away_spec, False)):
            team = make_team(*spec, rng=self.rng)
            self.teams[team.id] = team
            self.states[team.id] = self._initial_state(team, is_home)
        self.home_id, self.away_id = home_spec[0], away_spec[0]
        self.score = {self.home_id: 0, self.away_id: 0}
        self.events: list[Event] = []
        self.rows_t: list[np.ndarray] = []
        self.rows_id: list[list[str]] = []
        self.rows_team: list[list[str]] = []
        self.rows_xy: list[np.ndarray] = []
        self.s = _State(possession=self.home_id, carrier=None, ball=np.array([LENGTH / 2, WIDTH / 2]))

    # ---- setup -------------------------------------------------------------
    @staticmethod
    def _initial_state(team: Team, is_home: bool) -> TeamState:
        slots = np.array([(ax, y) for _, ax, y in slots_for(team.formation)], dtype=float)
        slots[:, 0] *= 0.5  # start in own half
        pos = slots if is_home else np.column_stack([LENGTH - slots[:, 0], WIDTH - slots[:, 1]])
        starters = [p.id for p in team.players if p.starter]
        return TeamState(team.id, is_home, team.formation, team.tactics, starters, pos.copy())

    # ---- helpers -----------------------------------------------------------
    def emit(self, t: float, team_id: str, player_id: str | None, type: EventType,
             x: float, y: float, **kw) -> Event:
        x, y = clamp(x, y)
        for k in ("end_x", "end_y"):
            if kw.get(k) is not None:
                kw[k] = float(min(max(kw[k], 0.0), LENGTH if k == "end_x" else WIDTH))
        e = Event(id=len(self.events) + 1, t=float(t), period=1 if t < HALF_SECONDS else 2,
                  team_id=team_id, player_id=player_id, type=type, x=x, y=y, **kw)
        self.events.append(e)
        return e

    def opp(self, team_id: str) -> str:
        return self.away_id if team_id == self.home_id else self.home_id

    def ax(self, team_id: str, x: float) -> float:
        return attack_x(x, self.states[team_id].is_home)

    def carrier_id(self) -> str | None:
        if self.s.carrier is None:
            return None
        return self.states[self.s.possession].on_pitch[self.s.carrier]

    def nearest(self, team_id: str, point: np.ndarray, outfield_only: bool = False) -> tuple[int, float]:
        pos = self.states[team_id].pos
        d = np.hypot(pos[:, 0] - point[0], pos[:, 1] - point[1])
        if outfield_only:
            d[0] = np.inf
        i = int(np.argmin(d))
        return i, float(d[i])

    def give_ball(self, team_id: str, idx: int) -> None:
        self.s.possession, self.s.carrier = team_id, idx
        self.s.ball = self.states[team_id].pos[idx].copy()
        self.s.pressured_logged = False

    def dead_ball(self, restart_team: str, kind: str, pause: tuple[int, int] | int) -> None:
        self.s.carrier = None
        self.s.restart = (restart_team, kind)
        self.s.pause = pause if isinstance(pause, int) else int(self.rng.integers(pause[0], pause[1] + 1))

    def kickoff(self, t: int, team_id: str) -> None:
        self.s.ball = np.array([LENGTH / 2, WIDTH / 2])
        st = self.states[team_id]
        roles = [r for r, _, _ in slots_for(st.formation)]
        idx = roles.index("ST") if "ST" in roles else 10
        st.pos[idx] = self.s.ball
        self.give_ball(team_id, idx)
        self.s.pause, self.s.restart = 0, None
        self.emit(t, team_id, self.carrier_id(), EventType.KICKOFF, *self.s.ball)

    def restart_play(self, t: int) -> None:
        team_id, kind = self.s.restart
        self.s.restart = None
        if kind == "kickoff":
            self.kickoff(t, team_id)
        elif kind == "gk":
            self.give_ball(team_id, 0)
        else:
            idx, _ = self.nearest(team_id, self.s.ball, outfield_only=True)
            self.states[team_id].pos[idx] = self.s.ball
            self.give_ball(team_id, idx)

    # ---- carrier actions ---------------------------------------------------
    def carrier_acts(self, t: int, pressured: bool) -> None:
        team_id = self.s.possession
        st = self.states[team_id]
        pid = self.carrier_id()
        bx, by = self.s.ball
        bax = self.ax(team_id, bx)
        ay = by if st.is_home else WIDTH - by

        if bax > SHOT_ZONE_AX:
            xg = shot_xg(bax, ay, under_pressure=pressured)
            if self.rng.random() < min(SHOT_PROB_CAP, SHOT_XG_MULT * xg):
                self.shoot(t, team_id, pid, xg)
                return

        if self.rng.random() < CARRY_PROB:
            step = self.rng.uniform(3, 8)
            dx = step if st.is_home else -step
            end = np.array(clamp(bx + dx, by + self.rng.normal(0, 2)))
            self.emit(t, team_id, pid, EventType.CARRY, bx, by, end_x=end[0], end_y=end[1], outcome=True)
            self.s.ball = end
            return

        self.pass_ball(t, team_id, pid, pressured)

    def shoot(self, t: int, team_id: str, pid: str | None, xg: float) -> None:
        bx, by = self.s.ball
        goal = bool(self.rng.random() < xg)
        goal_x = LENGTH if self.states[team_id].is_home else 0.0
        shot = self.emit(t, team_id, pid, EventType.SHOT, bx, by, end_x=goal_x, end_y=WIDTH / 2,
                         outcome=goal, xg=round(xg, 4))
        opp = self.opp(team_id)
        if goal:
            self.score[team_id] += 1
            self.emit(t, team_id, pid, EventType.GOAL, bx, by, detail={"shot_id": float(shot.id)})
            self.s.ball = np.array([LENGTH / 2, WIDTH / 2])
            self.dead_ball(opp, "kickoff", PAUSE_GOAL)
        elif self.rng.random() < GK_CATCH_SHARE:
            self.give_ball(opp, 0)
        else:
            self.s.ball = self.states[opp].pos[0].copy()
            self.dead_ball(opp, "gk", PAUSE_OUT)

    def pass_ball(self, t: int, team_id: str, pid: str | None, pressured: bool) -> None:
        st = self.states[team_id]
        bx, by = self.s.ball
        bax = self.ax(team_id, bx)
        opp_pos = self.states[self.opp(team_id)].pos
        weights = np.zeros(11)
        for i in range(11):
            if i == self.s.carrier:
                continue
            rx, ry = st.pos[i]
            length = float(np.hypot(rx - bx, ry - by))
            gain = self.ax(team_id, rx) - bax
            open_ = min(1.0, float(np.min(np.hypot(opp_pos[:, 0] - rx, opp_pos[:, 1] - ry))) / 5.0)
            weights[i] = np.exp(st.tactics.directness * gain / 15.0) * open_ * np.exp(-length / PASS_DISTANCE_SCALE)
        if weights.sum() <= 0:
            weights[[i for i in range(11) if i != self.s.carrier]] = 1.0
        recv = int(self.rng.choice(11, p=weights / weights.sum()))
        rx, ry = st.pos[recv]
        length = float(np.hypot(rx - bx, ry - by))
        into_final = third(self.ax(team_id, rx)) == "final"
        p_ok = (PASS_BASE - PASS_LENGTH_PEN * (length / 40) - PASS_PRESSURE_PEN * pressured
                - PASS_FINAL_THIRD_PEN * into_final)
        p_ok = min(max(p_ok, 0.3), 0.97)

        if self.rng.random() < p_ok:
            self.emit(t, team_id, pid, EventType.PASS, bx, by, end_x=rx, end_y=ry, outcome=True,
                      related_player_id=st.on_pitch[recv])
            self.give_ball(team_id, recv)
            return

        self.emit(t, team_id, pid, EventType.PASS, bx, by, end_x=rx, end_y=ry, outcome=False)
        opp = self.opp(team_id)
        if self.rng.random() < INTERCEPT_SHARE:
            idx, _ = self.nearest(opp, np.array([rx, ry]))
            ix, iy = self.states[opp].pos[idx]
            self.emit(t, opp, self.states[opp].on_pitch[idx], EventType.INTERCEPTION, ix, iy, outcome=True)
            self.give_ball(opp, idx)
        else:
            self.s.ball = np.array(clamp(rx, ry))
            self.dead_ball(opp, "nearest", PAUSE_OUT)

    # ---- defending ---------------------------------------------------------
    def defend(self, t: int, dist: float, def_idx: int) -> None:
        if dist > PRESSURE_RADIUS:
            return
        att = self.s.possession
        dfn = self.opp(att)
        tactics = self.states[dfn].tactics
        def_pid = self.states[dfn].on_pitch[def_idx]
        bx, by = self.s.ball
        if not self.s.pressured_logged and self.rng.random() < PRESSURE_BASE + PRESSURE_PRESS * tactics.press_height:
            self.emit(t, dfn, def_pid, EventType.PRESSURE, bx, by, related_player_id=self.carrier_id())
            self.s.pressured_logged = True
        if self.rng.random() < TACKLE_PROB:
            won = bool(self.rng.random() < TACKLE_WIN)
            self.emit(t, dfn, def_pid, EventType.TACKLE, bx, by, outcome=won,
                      related_player_id=self.carrier_id())
            if won:
                self.give_ball(dfn, def_idx)
            return
        if self.rng.random() < FOUL_PROB:
            self.emit(t, dfn, def_pid, EventType.FOUL, bx, by, related_player_id=self.carrier_id())
            if def_pid not in self.s.booked and self.rng.random() < CARD_PROB:
                self.s.booked.add(def_pid)
                self.emit(t, dfn, def_pid, EventType.CARD, bx, by, detail={"colour": "yellow"})
            self.dead_ball(att, "nearest", PAUSE_FOUL)

    # ---- main loop ---------------------------------------------------------
    def apply_storyline(self, t: int) -> None:
        if not any(c.minute * 60 == t for c in self.storyline):
            return
        carrier = self.carrier_id()
        apply_due_changes(t, self.storyline, self.states, self.teams, self.emit)
        if carrier is not None:
            on_pitch = self.states[self.s.possession].on_pitch
            # carrier keeps the ball after a reshuffle; a subbed-off carrier hands it to his replacement
            self.s.carrier = on_pitch.index(carrier) if carrier in on_pitch else self.s.carrier

    def tick(self, t: int) -> None:
        self.apply_storyline(t)
        if t == 0:
            self.kickoff(t, self.home_id)
        elif t == HALF_SECONDS:
            self.kickoff(t, self.away_id)
        elif self.s.pause > 0:
            self.s.pause -= 1
            if self.s.pause == 0:
                self.restart_play(t)
        elif self.s.carrier is not None:
            att = self.s.possession
            tempo = self.states[att].tactics.tempo
            def_idx, dist = self.nearest(self.opp(att), self.s.ball)
            pressured = dist <= PRESSURE_RADIUS
            if self.rng.random() < ACT_BASE + ACT_TEMPO * tempo:
                self.carrier_acts(t, pressured)
            else:
                self.dribble()
            if self.s.carrier is not None and self.s.possession == att and self.s.pause == 0:
                def_idx, dist = self.nearest(self.opp(att), self.s.ball)
                self.defend(t, dist, def_idx)

        if t == HALF_SECONDS - 1:
            self.emit(t, self.home_id, None, EventType.PERIOD_END, LENGTH / 2, WIDTH / 2)

        self.move_and_record(t)

    def dribble(self) -> None:
        st = self.states[self.s.possession]
        step = self.rng.uniform(0, DRIBBLE_MAX)
        bx, by = self.s.ball
        self.s.ball = np.array(clamp(bx + (step if st.is_home else -step), by + self.rng.normal(0, 0.7)))

    def move_and_record(self, t: int) -> None:
        ball = (float(self.s.ball[0]), float(self.s.ball[1]))
        in_poss_team = self.s.possession if self.s.restart is None else self.s.restart[0]
        for tid, st in self.states.items():
            step_positions(st, ball, tid == in_poss_team, self.rng)
        if self.s.carrier is not None:
            self.states[self.s.possession].pos[self.s.carrier] = self.s.ball
        ids, teams, xy = [], [], []
        for tid, st in self.states.items():
            ids += st.on_pitch
            teams += [tid] * len(st.on_pitch)
            xy.append(st.pos)
        ids.append("BALL")
        teams.append("BALL")
        xy.append(self.s.ball.reshape(1, 2))
        self.rows_t.append(np.full(len(ids), t, dtype=np.int64))
        self.rows_id.append(ids)
        self.rows_team.append(teams)
        self.rows_xy.append(np.vstack(xy))

    def run(self) -> Match:
        for t in range(MATCH_SECONDS):
            self.tick(t)
        xy = np.vstack(self.rows_xy)
        tracking = pd.DataFrame({
            "t": np.concatenate(self.rows_t),
            "entity_id": [i for row in self.rows_id for i in row],
            "team_id": [i for row in self.rows_team for i in row],
            "x": xy[:, 0].astype(float),
            "y": xy[:, 1].astype(float),
        })
        meta = MatchMeta(match_id=self.match_id, seed=self.seed, home=self.teams[self.home_id],
                         away=self.teams[self.away_id], storyline=self.storyline, score=self.score)
        return Match(meta=meta, events=self.events, tracking=tracking)


def simulate_match(seed: int, match_id: str | None = None, storyline: list[ScriptedChange] | None = None,
                   home_spec: TeamSpec = DEFAULT_TEAMS[0], away_spec: TeamSpec = DEFAULT_TEAMS[1]) -> Match:
    return _Engine(seed, match_id or f"match-{seed:03d}", list(storyline or []), home_spec, away_spec).run()
