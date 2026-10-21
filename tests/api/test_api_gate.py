import asyncio

from jahbadh.api.gate import PriorityGate


async def enter(gate: PriorityGate, first: bool, name: str, order: list[str], release: asyncio.Event) -> None:
    async with gate.slot(first):
        order.append(name)
        await release.wait()


async def settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


def test_a_free_gate_lets_callers_straight_in():
    async def go():
        gate, order, release = PriorityGate(2), [], asyncio.Event()
        tasks = [asyncio.create_task(enter(gate, False, n, order, release)) for n in ("a", "b")]
        await settle()
        assert order == ["a", "b"]
        release.set()
        await asyncio.gather(*tasks)
    asyncio.run(go())


def test_a_waiting_moment_goes_before_waiting_versions():
    async def go():
        gate, order = PriorityGate(1), []
        hold, rest = asyncio.Event(), asyncio.Event()
        rest.set()
        first = asyncio.create_task(enter(gate, False, "a", order, hold))
        await settle()
        waiting = [asyncio.create_task(enter(gate, f, n, order, rest))
                   for f, n in ((False, "v1"), (False, "v2"), (True, "m"))]
        await settle()
        assert order == ["a"]
        hold.set()
        await asyncio.gather(first, *waiting)
        assert order == ["a", "m", "v1", "v2"]
    asyncio.run(go())


def test_a_caller_cancelled_while_waiting_gives_up_its_turn():
    async def go():
        gate, order = PriorityGate(1), []
        hold, rest = asyncio.Event(), asyncio.Event()
        rest.set()
        first = asyncio.create_task(enter(gate, False, "a", order, hold))
        await settle()
        quitter = asyncio.create_task(enter(gate, True, "b", order, rest))
        patient = asyncio.create_task(enter(gate, False, "c", order, rest))
        await settle()
        quitter.cancel()
        await settle()
        hold.set()
        await asyncio.gather(first, patient)
        assert order == ["a", "c"]
        await asyncio.wait_for(enter(gate, False, "d", order, rest), timeout=1)   # no place was lost
        assert order == ["a", "c", "d"]
    asyncio.run(go())
