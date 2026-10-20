"""The demo feeder: plays a simulated match into the ingest API over HTTP, exactly like an outside system would.

    python -m jahbadh.api.feeder --url http://127.0.0.1:8000 --seed 7 --speed 6

It reads the token from JAHBADH_INGEST_TOKEN. Each real second it posts the next `speed` match seconds of events and
tracking frames, so the desk sees the match unfold at that speed. The server's "Watch an outside feed" button runs
the same code against its own public address.
"""

import argparse
import asyncio
import os
import sys
from collections.abc import Awaitable, Callable, Iterator

import httpx2

from jahbadh.schemas import Match
from jahbadh.simulator import simulate_match

Sleep = Callable[[float], Awaitable[None]]


def _headers(token: str) -> dict[str, str]:
    return {"X-Ingest-Token": token}


def batches(match: Match, seconds: int) -> Iterator[dict]:
    """The match in blocks of `seconds` match seconds: that block's events and tracking frames."""
    tracking = match.tracking
    for lo in range(0, 5401, seconds):
        hi = lo + seconds
        events = [e.model_dump(mode="json") for e in match.events if lo <= e.t < hi]
        frames = tracking[(tracking["t"] >= lo) & (tracking["t"] < hi)].to_dict(orient="records")
        if events or frames:
            yield {"events": events, "frames": frames}


async def start_feed(client: httpx2.AsyncClient, token: str, match: Match) -> str:
    body = {"home": match.meta.home.model_dump(mode="json"), "away": match.meta.away.model_dump(mode="json"),
            "match_id": match.meta.match_id}
    reply = await client.post("/api/ingest", json=body, headers=_headers(token))
    reply.raise_for_status()
    return reply.json()["run_id"]


async def pump(client: httpx2.AsyncClient, token: str, run_id: str, match: Match, speed: float = 6.0,
               sleep: Sleep = asyncio.sleep) -> None:
    """One batch of `speed` match seconds every real second, then close. Stops if the desk turns a batch away."""
    for body in batches(match, max(1, round(speed))):
        reply = await client.post(f"/api/ingest/{run_id}/events", json=body, headers=_headers(token))
        if reply.status_code != 200:
            break
        await sleep(1.0)
    await client.post(f"/api/ingest/{run_id}/close", headers=_headers(token))


async def feed_match(client: httpx2.AsyncClient, token: str, seed: int, speed: float = 6.0,
                     sleep: Sleep = asyncio.sleep) -> str:
    match = await asyncio.to_thread(simulate_match, seed)
    run_id = await start_feed(client, token, match)
    await pump(client, token, run_id, match, speed, sleep)
    return run_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Play a simulated match into the desk's ingest API.")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--speed", type=float, default=6.0)
    args = parser.parse_args(argv)
    token = os.environ.get("JAHBADH_INGEST_TOKEN")
    if not token:
        print("Set JAHBADH_INGEST_TOKEN to the server's ingest token first.", file=sys.stderr)
        return 2

    async def run() -> str:
        async with httpx2.AsyncClient(base_url=args.url, timeout=30) as client:
            return await feed_match(client, token, args.seed, args.speed)

    print(f"fed {asyncio.run(run())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
