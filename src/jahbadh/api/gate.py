"""A concurrency limit with a fast lane: the desk's own moments go ahead of the extra versions viewers add.

At most `limit` holders at once. When a place frees, a waiting `first` caller gets it before any other waiting
caller; within each group the order is first come, first served. A caller cancelled while waiting simply
leaves the queue.
"""

import asyncio
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class PriorityGate:
    def __init__(self, limit: int):
        self.limit = limit
        self._busy = 0
        self._first: deque[asyncio.Future[None]] = deque()
        self._rest: deque[asyncio.Future[None]] = deque()

    def _hand_on(self) -> None:
        """Give free places to the waiters, fast lane first."""
        while self._busy < self.limit:
            queue = self._first if self._first else self._rest
            if not queue:
                return
            waiter = queue.popleft()
            if not waiter.done():
                self._busy += 1
                waiter.set_result(None)

    @asynccontextmanager
    async def slot(self, first: bool) -> AsyncIterator[None]:
        if self._busy < self.limit and not self._first and not self._rest:
            self._busy += 1
        else:
            waiter = asyncio.get_running_loop().create_future()
            (self._first if first else self._rest).append(waiter)
            try:
                await waiter
            except asyncio.CancelledError:
                if waiter.done() and not waiter.cancelled():   # handed a place just as it was cancelled
                    self._busy -= 1
                    self._hand_on()
                elif waiter in self._first or waiter in self._rest:
                    (self._first if waiter in self._first else self._rest).remove(waiter)
                raise
        try:
            yield
        finally:
            self._busy -= 1
            self._hand_on()
