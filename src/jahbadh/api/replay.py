"""Playing a timeline: pacing items by match time at a chosen speed, and turning them into SSE messages."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi.sse import ServerSentEvent

from jahbadh.api.stream import StreamItem

Sleep = Callable[[float], Awaitable[None]]


def to_sse(index: int, item: StreamItem) -> ServerSentEvent:
    return ServerSentEvent(data=item.data, event=item.kind, id=str(index))


async def paced(items: list[StreamItem], speed: float, start: int = 0, from_t: float = 0.0,
                sleep: Sleep = asyncio.sleep) -> AsyncIterator[tuple[int, StreamItem]]:
    """(index, item) for items[start:], each once the clock reaches its t.

    The clock starts at from_t, or at the last item already sent when resuming, whichever is later. Anything at
    or before the clock goes out at once (the catch-up burst for a seek); a later item waits its gap / speed.
    """
    clock = max(from_t, items[start - 1].t if start else 0.0)
    for index in range(start, len(items)):
        item = items[index]
        if item.t > clock:
            await sleep((item.t - clock) / speed)
            clock = item.t
        yield index, item
