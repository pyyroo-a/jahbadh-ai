"""The desk's web API: config, the replay stream and the built UI.

Run it with: uvicorn jahbadh.api.app:create_app --factory --port 8000
"""

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.staticfiles import StaticFiles

from jahbadh.agents.desk import Desk
from jahbadh.api.config import ApiSettings, load_api_settings
from jahbadh.api.replay import Sleep, paced, to_sse
from jahbadh.api.showcase import Showcase, load_showcases
from jahbadh.api.stream import MatchInfo, StreamItem
from jahbadh.api.timeline import replay_timeline
from jahbadh.schemas import Match

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


def create_app(settings: ApiSettings | None = None, desk_factory: DeskFactory | None = None,
               sleep: Sleep = asyncio.sleep, now: Callable[[], float] = time.monotonic) -> FastAPI:
    settings = settings or load_api_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.showcases = load_showcases(settings.showcase_dir)
        app.state.timelines = {mid: replay_timeline(s) for mid, s in app.state.showcases.items()}
        yield

    app = FastAPI(title="Jahbadh desk", lifespan=lifespan)
    app.state.settings, app.state.desk_factory, app.state.sleep, app.state.now = settings, desk_factory, sleep, now

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/api/config")
    def config(request: Request) -> dict:
        shows = request.app.state.showcases.values()
        return {
            "live_mode": settings.live_mode,
            "live_remaining": 0,
            "showcases": [{"match_id": s.desk.match_id, "home": s.match.meta.home.name,
                           "away": s.match.meta.away.name, "score": s.match.meta.score,
                           "model": s.desk.model, "created": s.desk.created} for s in shows],
        }

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
        async for index, item in paced(items, speed, start=start, from_t=from_t, sleep=sleep):
            yield to_sse(index + 1, item)          # timeline items are numbered from 1

    if (settings.web_dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=settings.web_dist, html=True), name="ui")
    return app
