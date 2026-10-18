"""A live run: a fresh match played at 6x, with the real desk working each key moment as the clock reaches it.

Live mode costs money, so it only covers key moments (goals, big chances, cards, substitutions, formation and
tactic changes, full time), runs at most LIVE_CONCURRENCY of them at once, adds at most LIVE_MAX_COMBOS extra
persona and language combos, and cancels itself once nobody has watched for idle_s.

Everything a viewer sees is appended to `history`, in the order it happened, and never ahead of the clock:
index 0 is the match, then events, states and cues at their time, a `thinking` item when a moment starts, and
its `feed` (or `failure`) when the desk publishes. Viewers read the history and wait for more (subscribe).
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

from jahbadh.agents import pipeline
from jahbadh.agents.combos import render_combo
from jahbadh.agents.contracts import FeedItem, Language, Moment, MomentFailure, Persona
from jahbadh.agents.desk import Desk
from jahbadh.agents.moments import detect_moments
from jahbadh.agents.spotlight import spotlight_moment
from jahbadh.api.replay import Sleep
from jahbadh.api.stream import MatchInfo, RendersUpdate, StreamEnd, StreamItem
from jahbadh.api.timeline import _sorted, match_timeline
from jahbadh.schemas import Match

log = logging.getLogger(__name__)

KEY_KINDS = ("goal", "big_chance", "card", "substitution", "formation_change", "tactic_change", "full_time")
LIVE_SPEED = 6.0
LIVE_IDLE_S = 60.0
LIVE_CONCURRENCY = 3
LIVE_MAX_COMBOS = 2
SKIP_LEAD_S = 3.0
DEFAULT_COMBO: tuple[Persona, Language] = ("pundit", "en")


def key_moments(match: Match) -> list[Moment]:
    return [m for m in detect_moments(match) if m.kind in KEY_KINDS]


class LiveRun:
    def __init__(self, run_id: str, match: Match, desk: Desk, speed: float = LIVE_SPEED,
                 sleep: Sleep = asyncio.sleep, now: Callable[[], float] = time.monotonic,
                 idle_s: float = LIVE_IDLE_S):
        self.run_id, self.match, self.desk, self.speed = run_id, match, desk, speed
        self.sleep, self.now, self.idle_s = sleep, now, idle_s
        self.clock = 0.0
        self.done = False
        self.moments = key_moments(match)
        self.combos: list[tuple[Persona, Language]] = []
        meta = match.meta
        model = getattr(desk.client, "model", None) or type(desk.client).__name__
        self.history: list[StreamItem] = [StreamItem(t=0.0, kind="match", data=MatchInfo(
            match_id=meta.match_id, mode="live", home=meta.home, away=meta.away, speed=speed, precomputed=False,
            model=str(model), created=datetime.now(UTC).isoformat(), moment_times=[]))]
        self._started: set[str] = set()              # moments that have begun, key or requested
        self._tasks: set[asyncio.Task] = set()        # moments and combo renders still working
        self._gate: asyncio.Semaphore | None = None
        self._changed: asyncio.Event | None = None    # set on every append, wakes the viewers
        self._wake: asyncio.Event | None = None       # set by skip, cuts the pacing sleep short
        self._runner: asyncio.Task | None = None
        self._viewers = 0
        self._idle_since = now()

    # -- the history ----------------------------------------------------------------------------------------

    def _events(self) -> tuple[asyncio.Event, asyncio.Event]:
        if self._changed is None:
            self._changed, self._wake, self._gate = asyncio.Event(), asyncio.Event(), asyncio.Semaphore(LIVE_CONCURRENCY)
        return self._changed, self._wake

    def _append(self, item: StreamItem) -> None:
        if self.done:
            return
        self.history.append(item)
        if item.kind == "end":
            self.done = True
        self._events()[0].set()

    async def subscribe(self, start: int = 0) -> AsyncIterator[tuple[int, StreamItem]]:
        """The history from `start`, then each new item as it lands, until the end."""
        changed, _ = self._events()
        self._viewers += 1
        try:
            i = start
            while True:
                while i < len(self.history):
                    item = self.history[i]
                    yield i, item
                    i += 1
                    if item.kind == "end":
                        return
                if self.done:
                    return
                changed.clear()
                await changed.wait()
        finally:
            self._viewers -= 1
            if self._viewers == 0:
                self._idle_since = self.now()

    # -- the clock ------------------------------------------------------------------------------------------

    def start(self) -> None:
        self._events()
        self._runner = asyncio.create_task(self._run())

    def _nobody_watching(self) -> bool:
        return self._viewers == 0 and self.now() - self._idle_since >= self.idle_s

    async def _wait(self, delay: float) -> None:
        """The pacing sleep, cut short by skip()."""
        _, wake = self._events()
        wake.clear()
        sleeper, woken = asyncio.ensure_future(self.sleep(delay)), asyncio.ensure_future(wake.wait())
        try:
            await asyncio.wait({sleeper, woken}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for f in (sleeper, woken):
                f.cancel()

    async def _run(self) -> None:
        try:
            await self._play()
        except asyncio.CancelledError:
            raise
        except Exception:                             # a bug must never leave viewers waiting forever
            log.exception("live run %s stopped", self.run_id)
            await self.cancel()

    async def _play(self) -> None:
        thinking = [StreamItem(t=m.t, kind="thinking", data=m) for m in self.moments]
        for item in _sorted(match_timeline(self.match) + thinking):
            if self._nobody_watching():
                await self.cancel()
                return
            while item.t > self.clock:
                target = self.clock
                await self._wait((item.t - target) / self.speed)
                if self.done:
                    return
                if self.clock == target:              # not skipped meanwhile
                    self.clock = item.t
            if item.kind == "thinking":
                self._begin(item.data, at=item.t)
            else:
                self._append(item)
        while self._tasks:                            # the last moments are still with the desk
            await asyncio.wait(set(self._tasks), timeout=1.0)
            if self._nobody_watching():
                await self.cancel()
                return
        self._append(StreamItem(t=self.clock, kind="end", data=StreamEnd(reason="full_time")))

    def skip(self) -> float | None:
        """Jump to just before the next moment; the events in between still go out, as a burst."""
        upcoming = [m.t for m in self.moments if m.id not in self._started and m.t > self.clock]
        if self.done or not upcoming:
            return None
        self.clock = max(self.clock, min(upcoming) - SKIP_LEAD_S)
        self._events()[1].set()
        return self.clock

    # -- the desk -------------------------------------------------------------------------------------------

    def _spawn(self, work) -> None:
        task = asyncio.create_task(work)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _begin(self, moment: Moment, at: float) -> None:
        self._started.add(moment.id)
        self._append(StreamItem(t=at, kind="thinking", data=moment))
        self._spawn(self._work(moment))

    async def _work(self, moment: Moment) -> None:
        async with self._gate:
            try:
                item = await pipeline.run_moment(self.desk, moment)
            except Exception as e:  # one bad moment (rate limit, bad reply) must never stop the match
                self._append(StreamItem(t=self.clock, kind="failure",
                                        data=MomentFailure(moment_id=moment.id, error=f"{type(e).__name__}: {e}")))
                return
        self._append(StreamItem(t=self.clock, kind="feed", data=item))
        for persona, language in self.combos:
            self._spawn(self._render(item, persona, language))

    async def _render(self, item: FeedItem, persona: Persona, language: Language) -> None:
        async with self._gate:
            try:
                renders, rejections = await render_combo(self.desk, item, persona, language)
            except Exception:  # the viewer keeps the English fallback
                log.exception("combo %s/%s for %s failed", persona, language, item.moment.id)
                return
        self._append(StreamItem(t=self.clock, kind="renders", data=RendersUpdate(
            moment_id=item.moment.id, renders=renders, rejections=rejections)))

    async def spotlight(self, player_id: str) -> Moment:
        """A viewer's spotlight on one player, as of now. KeyError for a player who isn't in this match."""
        base = spotlight_moment(self.match, player_id, "requested by a viewer", t=self.clock)
        moment = base.model_copy(update={"id": f"spotlight-{player_id}-{int(self.clock)}"})
        self._events()
        self._begin(moment, at=self.clock)
        return moment

    def add_combo(self, persona: Persona, language: Language) -> bool:
        combo = (persona, language)
        if combo == DEFAULT_COMBO or combo in self.combos:
            return True
        if len(self.combos) >= LIVE_MAX_COMBOS:
            return False
        self.combos.append(combo)
        if self._changed is not None:                 # inside a running loop: render what already published
            for item in self.history:
                if item.kind == "feed":
                    self._spawn(self._render(item.data, persona, language))
        return True

    async def cancel(self) -> None:
        """Stop the clock and the desk: pending moments are dropped and no more model calls go out."""
        if self.done:
            return
        current = asyncio.current_task()
        pending = [t for t in self._tasks if t is not current]
        if self._runner is not None and self._runner is not current:
            pending.append(self._runner)
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        self._append(StreamItem(t=self.clock, kind="end", data=StreamEnd(reason="cancelled")))
