"""The ingest endpoints: outside events in, the same desk stream out.

Off unless JAHBADH_INGEST_TOKEN is set (every route then 404s). Writes need that token in X-Ingest-Token; reading
the stream, the players and a follow is open, like replay and live. Only one live or ingest run at a time.
"""

import asyncio
import logging
import random
import secrets
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from jahbadh.agents.config import MissingSetting
from jahbadh.api.feeder import pump, start_feed
from jahbadh.api.ingest import IngestBatch, IngestError, IngestRun, IngestStart, empty_match
from jahbadh.api.live_routes import default_desk_factory
from jahbadh.api.personal import PlayerFollow, PlayerRow, player_follow, player_table
from jahbadh.api.replay import to_sse
from jahbadh.simulator import simulate_match

log = logging.getLogger(__name__)

OFF = "Ingest is switched off on this server."
WRONG_TOKEN = "That ingest token isn't right."
LIVE_BUSY = "A live match is running right now. Try again when it ends."

router = APIRouter(prefix="/api/ingest")


def active_ingest(state) -> IngestRun | None:
    run = state.ingest
    return run if run is not None and not run.done and not run.stale else None


def _on(request: Request) -> str:
    token = request.app.state.settings.ingest_token
    if not token:
        raise HTTPException(404, OFF)
    return token


def _writer(request: Request, x_ingest_token: Annotated[str | None, Header()] = None) -> None:
    if not secrets.compare_digest((x_ingest_token or "").encode(), _on(request).encode()):
        raise HTTPException(401, WRONG_TOKEN)


def _run(request: Request, run_id: str) -> IngestRun:
    _on(request)
    run = request.app.state.ingest
    if run is None or run.run_id != run_id:
        raise HTTPException(404, f"No ingest match called {run_id}.")
    return run


@router.post("", dependencies=[Depends(_writer)])
async def start_ingest(request: Request, body: IngestStart) -> dict:
    state = request.app.state
    async with state.live_lock:                       # one live or ingest run at a time
        if state.live is not None and not state.live.done:
            raise HTTPException(409, LIVE_BUSY)
        if (running := active_ingest(state)) is not None:
            raise HTTPException(409, f"An outside feed is already playing ({running.run_id}).")
        run_id = f"ingest-{secrets.token_hex(4)}"
        match = empty_match(run_id, body)
        desk = None
        if state.settings.live_mode and state.limit.remaining() > 0:
            try:
                desk = (state.desk_factory or default_desk_factory)(match)
            except MissingSetting:
                desk = None                           # no keys: template lines and stats only
            if desk is not None and not state.limit.take():
                desk = None
        run = IngestRun(run_id, match, desk, now=state.now)
        run.start()
        state.ingest = run
        return {"run_id": run_id, "agents": run.agents, "remaining": state.limit.remaining()}


@router.post("/demo")
async def demo_feed(request: Request) -> dict:
    """The "Watch an outside feed" button: our demo feeder plays a fresh simulated match into the ingest API over
    HTTP, exactly like an outside system would. If a feed is already playing, you join it."""
    state = request.app.state
    token = _on(request)
    if state.live is not None and not state.live.done:
        raise HTTPException(409, LIVE_BUSY)
    if (running := active_ingest(state)) is not None:
        return {"run_id": running.run_id, "joined": True}
    match = await asyncio.to_thread(simulate_match, random.randint(100, 9999))
    client = state.feeder_client()
    try:
        run_id = await start_feed(client, token, match)
    except Exception:
        await client.aclose()
        if (running := active_ingest(state)) is not None:     # another click started one meanwhile
            return {"run_id": running.run_id, "joined": True}
        raise HTTPException(503, "The demo feed couldn't start just now.") from None

    async def play() -> None:
        try:                                      # the client is already open (start_feed used it), so no "async with"
            await pump(client, token, run_id, match, state.feed_speed, state.sleep)
        except Exception:
            log.exception("the demo feed %s stopped", run_id)
        finally:
            await client.aclose()

    state.feeder = asyncio.create_task(play())
    return {"run_id": run_id, "joined": False}


@router.post("/{run_id}/events", dependencies=[Depends(_writer)])
async def ingest_events(run: Annotated[IngestRun, Depends(_run)], batch: IngestBatch) -> dict:
    try:
        accepted = await run.add(batch)
    except IngestError as e:
        raise HTTPException(422, str(e)) from None
    return {"accepted": accepted, "clock": run.clock}


@router.post("/{run_id}/close", dependencies=[Depends(_writer)])
async def ingest_close(run: Annotated[IngestRun, Depends(_run)]) -> dict:
    await run.close()
    return {"closed": True, "clock": run.clock}


@router.get("/{run_id}/stream", response_class=EventSourceResponse)
async def ingest_stream(run: Annotated[IngestRun, Depends(_run)],
                        last_event_id: Annotated[str | None, Header()] = None) -> AsyncIterator[ServerSentEvent]:
    seen = last_event_id.strip() if last_event_id else ""
    start = int(seen) + 1 if seen.isdigit() else 0
    async for index, item in run.subscribe(start):
        yield to_sse(index, item)


@router.get("/{run_id}/players")
async def ingest_players(run: Annotated[IngestRun, Depends(_run)],
                         t: Annotated[float, Query(ge=0, le=5400)]) -> list[PlayerRow]:
    return await asyncio.to_thread(player_table, run.match, min(t, run.clock))


@router.get("/{run_id}/follow/{player_id}")
async def ingest_follow(run: Annotated[IngestRun, Depends(_run)], player_id: str,
                        t: Annotated[float, Query(ge=0, le=5400)]) -> PlayerFollow:
    try:
        return await asyncio.to_thread(player_follow, run.match, player_id, min(t, run.clock))
    except KeyError:
        raise HTTPException(404, f"No player called {player_id} in this match.") from None
