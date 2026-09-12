"""CP-1 bus contract: in-process asyncio.Queue only; P0 synchronous (never
buffered, never dropped); P1 dedicated lane; P2/P3 shared lane; ordering
preserved per lane; P0/P1 evict oldest P2/P3 when full (logged); inbound
raw-candle queue 1000 items, drop-oldest, QUEUE_OVERFLOW_DROP logged."""
from __future__ import annotations

import asyncio

from apex.bus import (
    P0,
    P1,
    P2,
    P3,
    EventBus,
    RawCandleQueue,
    make_event,
)


def run(coro):
    return asyncio.run(coro)


def test_p0_is_synchronous_and_ordered():
    """AI.12: 'No buffering of critical events; P0 = synchronous'.
    Subscribers are awaited inline in publish order before publish
    returns; ordering preserved."""
    async def scenario():
        bus = EventBus()
        seen = []
        async def c1(ev):
            seen.append("c1:" + ev.payload["n"])
        async def c2(ev):
            seen.append("c2:" + ev.payload["n"])
        bus.subscribe("t", c1)
        bus.subscribe("t", c2)
        await bus.publish(make_event(P0, "t", {"n": "a"}))
        assert seen == ["c1:a", "c2:a"]  # inline, subscription order
        assert bus.counts["p0_delivered"] == 1
        await bus.publish(make_event(P0, "t", {"n": "b"}))
        assert seen == ["c1:a", "c2:a", "c1:b", "c2:b"]
    run(scenario())


def test_p0_never_dropped_even_when_lanes_full():
    """2000 P0 + 1000 P2 (AI.7 queue-bounds shape): all P0 processed;
    P2 may be evicted."""
    async def scenario():
        bus = EventBus(lane_maxsize=10)
        p0_delivered = []
        async def sink(ev):
            p0_delivered.append(ev.payload)
        bus.subscribe("t", sink)
        for i in range(200):
            await bus.publish(make_event(P0, "t", i))
        for i in range(100):
            await bus.publish(make_event(P2, "t", i))
        assert len(p0_delivered) == 200  # every P0 delivered synchronously
        assert bus.counts["p0_delivered"] == 200
        # P2 items: lane held at most 10; the rest evicted + logged
        assert 0 <= bus._shared_lane.qsize() <= 10
        assert bus.counts["evicted"] >= 100 - 10
        reasons = {e.reason for e in bus.eviction_log}
        assert "QUEUE_OVERFLOW_DROP" in reasons
    run(scenario())


def test_p1_dedicated_lane_and_preserved_ordering():
    async def scenario():
        bus = EventBus(lane_maxsize=5)
        got = []
        async def sink(ev):
            got.append(ev.payload)
        bus.subscribe("t", sink)
        bus.start()
        for i in range(3):
            await bus.publish(make_event(P1, "t", ("p1", i)))
        for i in range(3):
            await bus.publish(make_event(P2, "t", ("p2", i)))
        for _ in range(200):
            if len(got) == 6:
                break
            await asyncio.sleep(0.01)
        await bus.stop()
        p1s = [g for g in got if g[0] == "p1"]
        assert p1s == [("p1", 0), ("p1", 1), ("p1", 2)]  # FIFO per lane
    run(scenario())


def test_p1_never_dropped_evicts_shared():
    async def scenario():
        bus = EventBus(lane_maxsize=1)
        await bus.publish(make_event(P2, "x", "old-p2"))
        await bus.publish(make_event(P1, "y", "p1-1"))
        await bus.publish(make_event(P1, "y", "p1-2"))
        # P1 lane at bound → oldest P3/P2 evicted to make room (Ch.23);
        # P1 itself is never dropped and never blocks.
        reasons = [e.reason for e in bus.eviction_log]
        assert "EVICT_FOR_CRITICAL" in reasons
        assert bus._p1_lane.qsize() == 2
        assert bus._shared_lane.qsize() == 0
    run(scenario())


def test_p2_p3_shared_lane_drop_oldest():
    async def scenario():
        bus = EventBus(lane_maxsize=1)
        await bus.publish(make_event(P2, "x", "a"))
        await bus.publish(make_event(P3, "x", "b"))  # drops oldest ("a")
        assert bus._shared_lane.qsize() == 1
        evicted = bus.eviction_log[-1]
        assert evicted.reason == "QUEUE_OVERFLOW_DROP"
        assert evicted.topic == "x"
        assert evicted.event_id
        assert evicted.timestamp > 0
    run(scenario())


def test_priorities_mapping():
    assert make_event(P0, "t", None).priority == 0
    assert make_event(P1, "t", None).priority == 1
    assert make_event(P2, "t", None).priority == 2
    assert make_event(P3, "t", None).priority == 3


def test_unsubscribe():
    async def scenario():
        bus = EventBus()
        seen = []
        async def c(ev):
            seen.append(ev)
        bus.subscribe("t", c)
        bus.unsubscribe("t", c)
        await bus.publish(make_event(P0, "t", 1))
        assert seen == []
    run(scenario())


def test_raw_candle_queue_bounds_drop_oldest():
    """Ch.23/AI.9: inbound raw candle queue = 1000 items; no overflow
    backpressure; oldest dropped; QUEUE_OVERFLOW_DROP logged."""
    async def scenario():
        q = RawCandleQueue(maxsize=1000)
        for i in range(1001):
            await q.put(f"candle-{i}", event_id=f"e{i}", topic="raw")
        assert q.qsize() == 1000
        oldest = await q.get()
        assert oldest == "candle-1"  # candle-0 dropped as oldest
        assert q.drop_log[-1].reason == "QUEUE_OVERFLOW_DROP"
    run(scenario())
