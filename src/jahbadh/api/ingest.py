"""Ingest: synthetic match events from outside the simulator drive the desk as they arrive.

An outside system starts a match with two team sheets, then posts events in our Event schema, in time order, with
optional tracking frames. The clock is the time on the latest event. Template lines, stats and the pitch update for
free; key moments wake the agents only when live mode is on and a live action was spent on this match (the same
3-a-day limit as live mode). The match ends on a second-half PERIOD_END or a close call. Like live mode, the agents
stop once nobody has watched for a minute; the events keep flowing.
"""

import asyncio
import time
from collections.abc import Callable

import pandas as pd
from pydantic import BaseModel

from jahbadh.agents.desk import Desk
from jahbadh.agents.moments import detect_moments
from jahbadh.api.live import KEY_KINDS, LIVE_IDLE_S, LiveRun
from jahbadh.api.overlay import _event_cue, _names
from jahbadh.api.stream import StreamEnd, StreamItem
from jahbadh.api.timeline import event_line, match_state
from jahbadh.schemas import Event, EventType, Match, MatchMeta, Team

INGEST_STALE_S = 600.0             # an ingest match with no events for ten minutes gives up its slot
MATCH_END = 5400.0
WAKE_TYPES = {EventType.GOAL, EventType.SHOT, EventType.CARD, EventType.SUBSTITUTION, EventType.FORMATION_CHANGE,
              EventType.TACTIC_CHANGE}


class IngestStart(BaseModel):
    home: Team
    away: Team
    match_id: str | None = None


class TrackingRow(BaseModel):
    t: float
    entity_id: str
    team_id: str | None = None
    x: float
    y: float


class IngestBatch(BaseModel):
    events: list[Event]
    frames: list[TrackingRow] = []


class IngestError(ValueError):
    """A batch the desk can't accept. Nothing from it is kept."""


def empty_match(run_id: str, start: IngestStart) -> Match:
    meta = MatchMeta(match_id=start.match_id or run_id, seed=0, home=start.home, away=start.away, storyline=[],
                     score={start.home.id: 0, start.away.id: 0})
    tracking = pd.DataFrame({"t": pd.Series(dtype="int64"), "entity_id": pd.Series(dtype="string"),
                             "team_id": pd.Series(dtype="string"), "x": pd.Series(dtype="float64"),
                             "y": pd.Series(dtype="float64")})
    return Match(meta=meta, events=[], tracking=tracking)


class IngestRun(LiveRun):
    def __init__(self, run_id: str, match: Match, desk: Desk | None, now: Callable[[], float] = time.monotonic,
                 idle_s: float = LIVE_IDLE_S, stale_s: float = INGEST_STALE_S):
        model = (getattr(desk.client, "model", None) or type(desk.client).__name__) if desk else "template lines only"
        self._setup(run_id, match, desk, 1.0, asyncio.sleep, now, idle_s, mode="ingest", model=str(model))
        self.history.append(StreamItem(t=0.0, kind="state", data=match_state(match, 0)))
        self.stale_s = stale_s
        self._teams = {match.meta.home.id, match.meta.away.id}
        self._players = {p.id for team in (match.meta.home, match.meta.away) for p in team.players}
        self._next_state = 60.0
        self._last_seen = now()
        self._agents_on = desk is not None
        self._closed = False

    @property
    def agents(self) -> bool:
        return self._agents_on

    @property
    def stale(self) -> bool:
        return not self.done and self.now() - self._last_seen >= self.stale_s

    def _check(self, batch: IngestBatch) -> None:
        if self.finished or self._closed:
            raise IngestError("This ingest match has finished.")
        expected, last_t = len(self.match.events) + 1, self.clock
        for n, e in enumerate(batch.events):
            if e.id != expected + n:
                raise IngestError(f"Expected event id {expected + n} next, got {e.id}.")
            if not last_t <= e.t <= MATCH_END:
                raise IngestError(f"Event {e.id} at {e.t:g} s is out of order (the clock is at {last_t:g} s).")
            if e.team_id not in self._teams:
                raise IngestError(f"Event {e.id} names team {e.team_id}, which isn't playing.")
            for pid in (e.player_id, e.related_player_id):
                if pid and pid not in self._players:
                    raise IngestError(f"Player {pid} in event {e.id} isn't on either team sheet.")
            last_t = e.t
        if any(not 0 <= f.t <= MATCH_END for f in batch.frames):
            raise IngestError("Tracking frames must be between 0 and 5400 s.")

    def _states_up_to(self, t: float) -> None:
        """A state for every whole minute strictly before t that hasn't gone out yet."""
        while self._next_state < t and self._next_state <= MATCH_END:
            self._append(StreamItem(t=self._next_state, kind="state", data=match_state(self.match, self._next_state)))
            self._next_state += 60.0

    async def add(self, batch: IngestBatch) -> int:
        """Accept a batch (or raise IngestError and keep nothing). Returns how many events were taken."""
        self._check(batch)
        self.match.events.extend(batch.events)
        if batch.frames:
            frames = pd.DataFrame([f.model_dump() for f in batch.frames]).astype(self.match.tracking.dtypes.to_dict())
            self.match.tracking = pd.concat([self.match.tracking, frames], ignore_index=True)
        self._last_seen = self.now()
        players, teams = _names(self.match)
        for e in batch.events:
            self._states_up_to(e.t)
            self._append(StreamItem(t=e.t, kind="event", data=event_line(self.match, e)))
            cue = _event_cue(self.match, e, players, teams, precomputed=False)
            if cue is not None:
                self._append(StreamItem(t=e.t, kind="cue", data=cue))
            self.clock = e.t
        if self._agents_on and self._nobody_watching():
            self._agents_on = False                   # nobody is watching: no more model calls
        if self._agents_on and any(e.type in WAKE_TYPES for e in batch.events):
            for m in await asyncio.to_thread(detect_moments, self.match):
                if m.kind in KEY_KINDS and m.kind != "full_time" and m.t < self.clock and m.id not in self._started:
                    self._begin(m, at=self.clock)
        if any(e.type == EventType.PERIOD_END and e.period == 2 for e in batch.events):
            await self.close()
        return len(batch.events)

    async def close(self) -> None:
        """No more events: the last states go out, the desk writes full time (if it's on), then the stream ends."""
        if self._closed or self.finished:
            return
        self._closed = True
        self._states_up_to(self.clock + 1)
        if self._agents_on:
            for m in detect_moments(self.match):
                if m.kind == "full_time":
                    self._begin(m, at=self.clock)
        self._runner = asyncio.create_task(self._finish())

    async def _finish(self) -> None:
        while self._tasks:
            await asyncio.wait(set(self._tasks), timeout=1.0)
        self._append(StreamItem(t=self.clock, kind="end", data=StreamEnd(reason="full_time")))
