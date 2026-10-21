"""A live run: a fresh match played at 6x, with the real desk working each key moment as the clock reaches it.

Live mode costs money, so it only covers key moments (goals, big chances, cards, substitutions, formation and
tactic changes, full time), runs at most LIVE_CONCURRENCY of them at once, adds at most LIVE_MAX_COMBOS extra
persona and language combos, and cancels itself once nobody has watched for idle_s. While a key moment (not
full time) is with the desk, the match slows to real time until its checked line is out, at most LIVE_HOLD_CAP_S,
and every change of pace goes out as a `pace` item.

Everything a viewer sees is appended to `history`, in the order it happened, and never ahead of the clock:
index 0 is the match, then events, states and cues at their time, a `thinking` item when a moment starts, and
its `feed` (or `failure`) when the desk publishes, followed by a cue for each published claim. Viewers read the history and wait for more (subscribe).
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import ClassVar

from jahbadh.agents import pipeline
from jahbadh.agents.combos import render_combo
from jahbadh.agents.contracts import DeskStep, FeedItem, Language, Moment, MomentFailure, Persona
from jahbadh.agents.desk import Desk
from jahbadh.agents.moments import detect_moments
from jahbadh.agents.spotlight import spotlight_moment
from jahbadh.api.gate import PriorityGate
from jahbadh.api.overlay import claim_cues
from jahbadh.api.replay import Sleep
from jahbadh.api.stream import MatchInfo, PaceUpdate, RendersUpdate, StepUpdate, StreamEnd, StreamItem
from jahbadh.api.timeline import _sorted, match_timeline
from jahbadh.schemas import Match

log = logging.getLogger(__name__)

KEY_KINDS = ("goal", "big_chance", "card", "substitution", "formation_change", "tactic_change", "full_time")
LIVE_SPEED = 6.0
LIVE_IDLE_S = 60.0
LIVE_CONCURRENCY = 3
LIVE_MAX_COMBOS = 8                                  # every persona and language besides pundit/en
SKIP_LEAD_S = 3.0
LIVE_HOLD_SPEED = 1.0                                # real time, while a key moment is with the desk
LIVE_HOLD_CAP_S = 120.0                              # real seconds one moment may hold the match
PACE_TICK_S = 1.0                                    # the clock moves in ticks this long (real seconds)
DEFAULT_COMBO: tuple[Persona, Language] = ("pundit", "en")


def key_moments(match: Match) -> list[Moment]:
    return [m for m in detect_moments(match) if m.kind in KEY_KINDS]


class LiveRun:
    HOLDS: ClassVar[bool] = True                  # key moments slow the match while the desk checks them

    def __init__(self, run_id: str, match: Match, desk: Desk, speed: float = LIVE_SPEED,
                 sleep: Sleep = asyncio.sleep, now: Callable[[], float] = time.monotonic,
                 idle_s: float = LIVE_IDLE_S):
        model = getattr(desk.client, "model", None) or type(desk.client).__name__
        self._setup(run_id, match, desk, speed, sleep, now, idle_s, mode="live", model=str(model))
        self.moments = key_moments(match)

    def _setup(self, run_id: str, match: Match, desk: Desk | None, speed: float, sleep: Sleep,
               now: Callable[[], float], idle_s: float, mode: str, model: str) -> None:
        """The state every run shares: live here, and ingest in jahbadh.api.ingest."""
        self.run_id, self.match, self.desk, self.speed = run_id, match, desk, speed
        self.sleep, self.now, self.idle_s = sleep, now, idle_s
        self.clock = 0.0
        self.done = False
        self.moments: list[Moment] = []
        self.combos: list[tuple[Persona, Language]] = []
        meta = match.meta
        self.history: list[StreamItem] = [StreamItem(t=0.0, kind="match", data=MatchInfo(
            match_id=meta.match_id, mode=mode, home=meta.home, away=meta.away, speed=speed, precomputed=False,
            model=model, created=datetime.now(UTC).isoformat(), moment_times=[]))]
        self._started: set[str] = set()              # moments that have begun, key or requested
        self._tasks: set[asyncio.Task] = set()        # moments and combo renders still working
        self._english: dict[tuple[str, str], asyncio.Task] = {}   # (moment, persona): its English, rendered once
        self._holds: dict[str, float] = {}           # key moments holding the match at real time: since when
        self._announced: tuple[float, tuple[str, ...]] = (speed, ())   # the pace viewers were last told
        self._closing = False                         # cancel() has begun: nothing new may start
        self._gate: PriorityGate | None = None       # the desk's own moments go ahead of extra versions
        self._changed: asyncio.Event | None = None    # set on every append, wakes the viewers
        self._wake: asyncio.Event | None = None       # set by skip, cuts the pacing sleep short
        self._runner: asyncio.Task | None = None
        self._viewers = 0
        self._idle_since = now()

    # -- the history ----------------------------------------------------------------------------------------

    def _events(self) -> tuple[asyncio.Event, asyncio.Event]:
        if self._changed is None:
            self._changed, self._wake, self._gate = asyncio.Event(), asyncio.Event(), PriorityGate(LIVE_CONCURRENCY)
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
        timeline = await asyncio.to_thread(match_timeline, self.match, precomputed=False)   # about 1.4 s of work
        for item in _sorted(timeline + thinking):
            if self._nobody_watching():
                await self.cancel()
                return
            while item.t > self.clock:                # in ticks, so a hold that starts or ends mid-gap counts
                pace = self._pace()
                target = self.clock
                step = min(item.t - target, pace * PACE_TICK_S)
                await self._wait(step / pace)
                if self.done:
                    return
                if self.clock == target:              # not skipped meanwhile
                    self.clock = target + step
            if item.kind == "thinking":
                self._begin(item.data, at=item.t, hold=self.HOLDS and item.data.kind != "full_time")
            else:
                self._append(item)
        while self._tasks:                            # the last moments are still with the desk
            await asyncio.wait(set(self._tasks), timeout=1.0)
            self._pace()                              # a hold that ended after the last event still says so
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

    def _pace(self) -> float:
        """The speed for the next tick: real time while any key moment holds the match, else the run's speed."""
        now = self.now()
        for moment_id in [m for m, since in self._holds.items() if now - since >= LIVE_HOLD_CAP_S]:
            del self._holds[moment_id]                # stuck: let the match go, the moment keeps working
        self._announce()
        return LIVE_HOLD_SPEED if self._holds else self.speed

    def _announce(self) -> None:
        """Tell viewers the pace, only when it changed."""
        speed = LIVE_HOLD_SPEED if self._holds else self.speed
        if (speed, tuple(self._holds)) != self._announced:
            self._announced = (speed, tuple(self._holds))
            self._append(StreamItem(t=self.clock, kind="pace",
                                    data=PaceUpdate(t=self.clock, speed=speed, holding=list(self._holds))))

    # -- the desk -------------------------------------------------------------------------------------------

    @property
    def finished(self) -> bool:
        """Over, or on its way out: no spotlight, combo or moment may start (and spend) any more."""
        return self.done or self._closing

    def _spawn(self, work) -> None:
        if self.finished:
            work.close()
            return
        task = asyncio.create_task(work)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _begin(self, moment: Moment, at: float, hold: bool = False) -> None:
        self._started.add(moment.id)
        self._append(StreamItem(t=at, kind="thinking", data=moment))
        if hold:                                      # from the moment's own second, never before it
            self._holds[moment.id] = self.now()
            self._announce()
        self._spawn(self._work(moment))

    async def _work(self, moment: Moment) -> None:
        async with self._gate.slot(first=True):
            try:
                item = await pipeline.run_moment(self.desk, moment, on_step=lambda step: self._step(moment.id, step))
            except Exception as e:  # one bad moment (rate limit, bad reply) must never stop the match
                self._append(StreamItem(t=self.clock, kind="failure",
                                        data=MomentFailure(moment_id=moment.id, error=f"{type(e).__name__}: {e}")))
                self._holds.pop(moment.id, None)
                return
        self._step(moment.id, "publish")                # the landed time the page stamps on the line
        self._append(StreamItem(t=self.clock, kind="feed", data=item))
        for cue in claim_cues(item, at=self.clock, precomputed=False):     # right after the line it quotes
            self._append(StreamItem(t=self.clock, kind="cue", data=cue))
        self._holds.pop(moment.id, None)              # the line is out: the match may speed up again
        for persona, language in self.combos:
            self._spawn(self._render(item, persona, language))

    def _step(self, moment_id: str, step: DeskStep) -> None:
        self._append(StreamItem(t=self.clock, kind="step", data=StepUpdate(moment_id=moment_id, step=step, t=self.clock)))

    def _persona_english(self, item: FeedItem, persona: Persona) -> asyncio.Task:
        """The persona's English for one moment, rendered once and shared by every language of that persona."""
        key = (item.moment.id, persona)
        if key not in self._english:
            task = asyncio.create_task(render_combo(self.desk, item, persona, "en"))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            self._english[key] = task
        return self._english[key]

    async def _render(self, item: FeedItem, persona: Persona, language: Language) -> None:
        async with self._gate.slot(first=False):
            try:
                renders, rejections = await asyncio.shield(self._persona_english(item, persona))
                if language != "en":       # translate the shared English, so every version says the same thing
                    with_english = item.model_copy(update={"renders": item.renders + renders})
                    more, rejected = await render_combo(self.desk, with_english, persona, language)
                    renders, rejections = renders + more, rejections + rejected
            except Exception:  # the viewer keeps the English fallback
                log.exception("combo %s/%s for %s failed", persona, language, item.moment.id)
                return
        self._append(StreamItem(t=self.clock, kind="renders", data=RendersUpdate(
            moment_id=item.moment.id, renders=renders, rejections=rejections)))

    async def spotlight(self, player_id: str) -> Moment:
        """A viewer's spotlight on one player, as of now. KeyError for a player who isn't in this match."""
        if self.finished:
            raise RuntimeError("this live match has finished")
        base = spotlight_moment(self.match, player_id, "requested by a viewer", t=self.clock)
        moment_id, n = f"spotlight-{player_id}-{int(self.clock)}", 1
        while moment_id in self._started:             # two asks in one match second are two spotlights
            n += 1
            moment_id = f"spotlight-{player_id}-{int(self.clock)}-{n}"
        moment = base.model_copy(update={"id": moment_id})
        self._events()
        self._begin(moment, at=self.clock)
        return moment

    def add_combo(self, persona: Persona, language: Language) -> bool:
        combo = (persona, language)
        if self.finished:
            return False
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
        if self.finished:
            return
        self._closing = True
        self._holds.clear()
        current = asyncio.current_task()
        pending = [t for t in self._tasks if t is not current]
        if self._runner is not None and self._runner is not current:
            pending.append(self._runner)
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        self._append(StreamItem(t=self.clock, kind="end", data=StreamEnd(reason="cancelled")))
