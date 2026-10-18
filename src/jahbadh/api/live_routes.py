"""The live desk endpoints: start or join a fresh match, watch it, skip ahead, ask for a spotlight or a combo.

Everything that calls the model sits behind the off switch (JAHBADH_LIVE_MODE) and the daily limit. A live action
is only spent once it really starts: a server without keys, an unknown player or a finished match costs nothing.
"""

import asyncio
import random
import secrets
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from jahbadh.agents.config import MissingSetting, load_settings
from jahbadh.agents.contracts import Language, Persona
from jahbadh.agents.desk import Desk
from jahbadh.agents.llm import make_chat_client
from jahbadh.agents.localize import AzureTranslator
from jahbadh.api.live import LiveRun
from jahbadh.api.replay import to_sse
from jahbadh.schemas import Match
from jahbadh.simulator import simulate_match
from jahbadh.simulator.storyline import DEMO_STORYLINE

OFF = "Live mode is switched off on this server. Replay is the very same desk, precomputed."
NOT_SET_UP = "Live mode is not set up on this server."
CAP = "Live mode has used all of today's live runs ({n} a day). Replay is still open, and it is the same desk."
FINISHED = "This match has finished."

router = APIRouter(prefix="/api/live")


def default_desk_factory(match: Match) -> Desk:
    """The real desk: Foundry for the agents, Azure AI Translator for the extra languages."""
    settings = load_settings()
    return Desk(client=make_chat_client(settings), match=match, translator=AzureTranslator(settings),
                personas=("pundit",), languages=("en",), effort=settings.reasoning_effort)


class SpotlightRequest(BaseModel):
    player_id: str


class ComboRequest(BaseModel):
    persona: Persona
    language: Language


def _cap_reached(request: Request) -> HTTPException:
    return HTTPException(429, CAP.format(n=request.app.state.settings.live_per_day))


def _run(request: Request, run_id: str) -> LiveRun:
    run = request.app.state.live
    if run is None or run.run_id != run_id:
        raise HTTPException(404, f"No live match called {run_id}.")
    return run


@router.post("")
async def start_live(request: Request) -> dict:
    state = request.app.state
    if not state.settings.live_mode:
        raise HTTPException(403, OFF)
    async with state.live_lock:                       # two starts at once make one run and one join
        run: LiveRun | None = state.live
        if run is not None and not run.done:
            return {"run_id": run.run_id, "joined": True, "remaining": state.limit.remaining()}
        if state.limit.remaining() <= 0:
            raise _cap_reached(request)
        seed = random.randint(100, 9999)
        match = await asyncio.to_thread(simulate_match, seed, storyline=DEMO_STORYLINE)
        try:
            desk = (state.desk_factory or default_desk_factory)(match)
        except MissingSetting:
            raise HTTPException(503, NOT_SET_UP) from None
        if not state.limit.take():
            raise _cap_reached(request)
        run = LiveRun(f"live-{seed}-{secrets.token_hex(3)}", match, desk, sleep=state.sleep, now=state.now)
        state.live = run
        run.start()
        return {"run_id": run.run_id, "joined": False, "remaining": state.limit.remaining()}


@router.get("/{run_id}/stream", response_class=EventSourceResponse)
async def live_stream(run: Annotated[LiveRun, Depends(_run)],      # a 404 has to come before the stream starts
                      last_event_id: Annotated[str | None, Header()] = None) -> AsyncIterator[ServerSentEvent]:
    seen = last_event_id.strip() if last_event_id else ""
    start = int(seen) + 1 if seen.isdigit() else 0    # the match message is index 0, so a resume skips it
    async for index, item in run.subscribe(start):
        yield to_sse(index, item)


@router.post("/{run_id}/skip")
async def live_skip(request: Request, run_id: str) -> dict:
    return {"clock": _run(request, run_id).skip()}


@router.post("/{run_id}/spotlight")
async def live_spotlight(request: Request, run_id: str, body: SpotlightRequest) -> dict:
    run = _run(request, run_id)
    if run.done:
        raise HTTPException(409, FINISHED)
    players = {p.id for team in (run.match.meta.home, run.match.meta.away) for p in team.players}
    if body.player_id not in players:
        raise HTTPException(404, f"No player called {body.player_id} in this match.")
    if not request.app.state.limit.take():
        raise _cap_reached(request)
    moment = await run.spotlight(body.player_id)
    return {"moment_id": moment.id}


@router.post("/{run_id}/combo")
async def live_combo(request: Request, run_id: str, body: ComboRequest) -> dict:
    run = _run(request, run_id)
    if run.done:                                      # the history is closed, so renders would be wasted calls
        return {"accepted": False}
    return {"accepted": run.add_combo(body.persona, body.language)}
