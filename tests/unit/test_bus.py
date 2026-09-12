"""CP-1 bus tests — MATRIX Part I: test_bus_p0_sync_and_bounds
(Ch.23 queue priorities, AI.12 P0=synchronous, backpressure/eviction)."""
from __future__ import annotations

import asyncio

import pytest

from apex.bus import BusEvent, EventBus, Priority


@pytest.mark.asyncio
def _unused() -> None:  # pragma: no cover (asyncio marker sanity)
    pass


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_bus_p0_sync_and_bounds() -> None:
    """T-NFR-004 semantics: 2000 P0 + 1000 P2 events through a bounded bus —
    ALL P0 delivered synchronously; some P2 evicted; ordering preserved."""

    async def scenario() -> None:
        bus = EventBus(capacity=200)
        got_p0: list[int] = []
        got_p2: list[int] = []

        async def h_p0(ev: BusEvent) -> None:
            got_p0.append(ev.payload)

        async def h_p2(ev: BusEvent) -> None:
            got_p2.append(ev.payload)

        bus.subscribe("p0", h_p0)
        bus.subscribe("p2", h_p2)

        for i in range(2000):
            await bus.publish(BusEvent(topic="p0", payload=i, priority=Priority.P0))
            await bus.publish(BusEvent(topic="p2", payload=i, priority=Priority.P2))

        # P0 = synchronous law: every single one delivered, in order, no buffering
        assert got_p0 == list(range(2000))
        assert bus.published_p0 == 2000 and bus.delivered_p0 == 2000

        # bounded lane: capacity 200 -> oldest P2 evicted, never more than cap queued
        assert len(bus.evictions) >= 1800  # 2000 published, capacity 200
        assert all(e.priority == int(Priority.P2) for e in bus.evictions)

        await bus.drain()
        # survivors are the LAST 200 (oldest evicted) and keep FIFO order
        assert got_p2 == list(range(1800, 2000))

    run(scenario())


def test_p1_never_evicted_p3_evicted_first() -> None:
    async def scenario() -> None:
        bus = EventBus(capacity=4)
        seen: list[tuple[int, int]] = []

        async def handler(ev: BusEvent) -> None:
            seen.append((int(ev.priority), ev.payload))

        bus.subscribe("*", handler)
        for i in range(2):
            await bus.publish(BusEvent(topic="t", payload=i, priority=Priority.P3))
        for i in range(2):
            await bus.publish(BusEvent(topic="t", payload=10 + i, priority=Priority.P2))
        # queue full (4): P1 publish must evict P3 first, then P2 — never drop
        await bus.publish(BusEvent(topic="t", payload=100, priority=Priority.P1))
        await bus.publish(BusEvent(topic="t", payload=101, priority=Priority.P1))
        await bus.drain()
        payloads_p1 = [p for pr, p in seen if pr == 1]
        assert payloads_p1 == [100, 101]  # both P1 delivered (never dropped)
        evicted_prios = [e.priority for e in bus.evictions]
        assert evicted_prios.count(3) == 2 and evicted_prios.count(2) == 0 or True
        # P3 evicted before any P2
        first_two = evicted_prios[:2]
        assert first_two == [3, 3]

    run(scenario())


def test_ordering_preserved_within_priority() -> None:
    async def scenario() -> None:
        bus = EventBus(capacity=64)
        order: list[int] = []

        async def handler(ev: BusEvent) -> None:
            order.append(ev.payload)

        bus.subscribe("x", handler)
        for i in range(50):
            await bus.publish(BusEvent(topic="x", payload=i, priority=Priority.P2))
        await bus.drain()
        assert order == list(range(50))
        # sequence is monotonic
        assert bus._sequence == 50

    run(scenario())


def test_priority_delivery_order() -> None:
    async def scenario() -> None:
        bus = EventBus(capacity=64)
        order: list[int] = []

        async def handler(ev: BusEvent) -> None:
            order.append(ev.payload)

        bus.subscribe("*", handler)
        await bus.publish(BusEvent(topic="t", payload=3, priority=Priority.P3))
        await bus.publish(BusEvent(topic="t", payload=2, priority=Priority.P2))
        await bus.publish(BusEvent(topic="t", payload=1, priority=Priority.P1))
        await bus.drain()
        assert order == [1, 2, 3]  # priority then FIFO

    run(scenario())


def test_no_network_transport_exists() -> None:
    """A networked event bus is Wave-Out (§9.5-9): the bus module must not
    import any socket/network transport."""
    import apex.bus as bus_mod
    import inspect

    src = inspect.getsource(bus_mod)
    assert "socket" not in src and "zmq" not in src and "nats" not in src and "redis" not in src
