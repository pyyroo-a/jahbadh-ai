"""The desk's web API: config, the replay stream, the live desk and the built UI.

Run it with: uvicorn jahbadh.api.app:create_app --factory --port 8000
"""

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated

import httpx2
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.staticfiles import StaticFiles

from jahbadh.agents.desk import Desk
from jahbadh.api.config import ApiSettings, load_api_settings
from jahbadh.api.limits import DailyLimit
from jahbadh.api.ingest_routes import active_ingest, router as ingest_router
from jahbadh.api.live_routes import router as live_router
from jahbadh.api.overlay import OverlayCue
from jahbadh.api.personal import METRIC_CHOICES, PlayerFollow, PlayerRow, player_follow, player_table
from jahbadh.api.replay import Sleep, paced, to_sse
from jahbadh.api.showcase import Showcase, load_showcases
from jahbadh.api.stream import MatchInfo, StreamItem
from jahbadh.api.timeline import replay_timeline
from jahbadh.schemas import Match
from jahbadh.telemetry import setup_tracing

DeskFactory = Callable[[Match], Desk]


def _showcase(request: Request, match_id: str) -> Showcase:
    show = request.app.state.showcases.get(match_id)
    if show is None:
        raise HTTPException(404, f"No replay called {match_id}.")
    return show


def _resume_from(last_event_id: str | None, n_items: int) -> int | None:
    """The timeline position after the last id the browser saw, or None for a fresh start."""
    if last_event_id is None or not last_event_id.strip().isdigit():
        return None
    return min(int(last_event_id), n_items)


def _cue_timeline(items: list[StreamItem]) -> list[StreamItem]:
    """Only the cues, in the main stream's order, then the same end."""
    return [i for i in items if i.kind == "cue"] + [items[-1]]


def create_app(settings: ApiSettings | None = None, desk_factory: DeskFactory | None = None,
               sleep: Sleep = asyncio.sleep, now: Callable[[], float] = time.monotonic) -> FastAPI:
    settings = settings or load_api_settings()
    tracing = setup_tracing()                      # before the app exists, so its requests are traced too

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.showcases = load_showcases(settings.showcase_dir)
        app.state.timelines = {mid: replay_timeline(s) for mid, s in app.state.showcases.items()}
        app.state.cue_timelines = {mid: _cue_timeline(items) for mid, items in app.state.timelines.items()}
        yield
        if app.state.feeder is not None:
            app.state.feeder.cancel()
        for run in (app.state.live, app.state.ingest):   # stopping the server never leaves model calls running
            if run is not None:
                await run.cancel()

    app = FastAPI(title="Jahbadh desk", lifespan=lifespan)
    app.state.settings, app.state.desk_factory, app.state.sleep, app.state.now = settings, desk_factory, sleep, now
    app.state.tracing = tracing
    app.state.limit = DailyLimit(settings.state_dir / "live.json", settings.live_per_day)
    app.state.live, app.state.live_lock = None, asyncio.Lock()
    app.state.ingest, app.state.feeder, app.state.feed_speed = None, None, 6.0
    app.state.feeder_client = lambda: httpx2.AsyncClient(base_url=settings.self_url, timeout=30)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/api/config")
    def config(request: Request) -> dict:
        shows = request.app.state.showcases.values()
        return {
            "live_mode": settings.live_mode,
            "live_remaining": request.app.state.limit.remaining() if settings.live_mode else 0,
            "showcases": [{"match_id": s.desk.match_id, "home": s.match.meta.home.name,
                           "away": s.match.meta.away.name, "score": s.match.meta.score,
                           "model": s.desk.model, "created": s.desk.created} for s in shows],
            "metric_choices": [c.model_dump() for c in METRIC_CHOICES.values()],
            "ingest": {"on": bool(settings.ingest_token),
                       "run_id": run.run_id if (run := active_ingest(request.app.state)) else None},
        }

    async def play(items: list[StreamItem], speed: float, from_t: float,
                   start: int) -> AsyncIterator[ServerSentEvent]:
        async for index, item in paced(items, speed, start=start, from_t=from_t, sleep=sleep):
            yield to_sse(index + 1, item)          # timeline items are numbered from 1

    @app.get("/api/replay/{match_id}/stream", response_class=EventSourceResponse)
    async def replay_stream(
        request: Request,
        show: Annotated[Showcase, Depends(_showcase)],
        speed: Annotated[float, Query(ge=1, le=60)] = 6,
        from_t: Annotated[float, Query(ge=0, le=5400)] = 0,
        last_event_id: Annotated[str | None, Header()] = None,
    ) -> AsyncIterator[ServerSentEvent]:
        items: list[StreamItem] = request.app.state.timelines[show.desk.match_id]
        start = _resume_from(last_event_id, len(items))
        if start is None:
            meta = show.match.meta
            yield ServerSentEvent(event="match", id="0", data=MatchInfo(
                match_id=meta.match_id, mode="replay", home=meta.home, away=meta.away, speed=speed,
                precomputed=True, model=show.desk.model, created=show.desk.created,
                moment_times=sorted(i.moment.t for i in show.desk.items)))
            start = 0
        async for message in play(items, speed, from_t, start):
            yield message

    @app.get("/api/overlay/schema")
    def overlay_schema() -> dict:
        return OverlayCue.model_json_schema()

    @app.get("/api/replay/{match_id}/overlay")
    def replay_overlay(request: Request, show: Annotated[Showcase, Depends(_showcase)]) -> list[OverlayCue]:
        return [i.data for i in request.app.state.cue_timelines[show.desk.match_id][:-1]]

    @app.get("/api/replay/{match_id}/overlay/stream", response_class=EventSourceResponse)
    async def replay_overlay_stream(
        request: Request,
        show: Annotated[Showcase, Depends(_showcase)],
        speed: Annotated[float, Query(ge=1, le=60)] = 6,
        from_t: Annotated[float, Query(ge=0, le=5400)] = 0,
        last_event_id: Annotated[str | None, Header()] = None,
    ) -> AsyncIterator[ServerSentEvent]:
        items: list[StreamItem] = request.app.state.cue_timelines[show.desk.match_id]
        async for message in play(items, speed, from_t, _resume_from(last_event_id, len(items)) or 0):
            yield message

    @app.get("/api/replay/{match_id}/follow/{player_id}")
    def replay_follow(show: Annotated[Showcase, Depends(_showcase)], player_id: str,
                      t: Annotated[float, Query(ge=0, le=5400)]) -> PlayerFollow:
        try:
            return player_follow(show.match, player_id, t)
        except KeyError:
            raise HTTPException(404, f"No player called {player_id} in this match.") from None

    @app.get("/api/replay/{match_id}/players")
    def replay_players(show: Annotated[Showcase, Depends(_showcase)],
                       t: Annotated[float, Query(ge=0, le=5400)]) -> list[PlayerRow]:
        return player_table(show.match, t)

    app.include_router(live_router)
    app.include_router(ingest_router)
    if (settings.web_dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=settings.web_dist, html=True), name="ui")
    return app
