"""APEX_GEN5 in-process event bus.

Blueprint: §9.5-10 ("Event bus = in-process asyncio.Queue only"), AI.12 Phase
3 (evidence event bus: "Message ordering preserved; no event loss; P0/P1
priority honored; No buffering of critical events; P0 = synchronous"),
Ch.23/AI.8 alert priorities and queue behavior.

Law implemented here:
- In-process ``asyncio.Queue`` ONLY. A networked bus is Wave-Out (§9.5-9).
- Priorities P0..P3 (Ch.23): P0 capital/emergency alerts; P1 major setup,
  forecast update, risk escalation; P2 routine features/patterns; P3
  research/archived outcomes.
- P0 is SYNCHRONOUS: delivered inline by awaiting every subscriber in
  publish order — never queued, never dropped, never buffered.
- P1 has a dedicated FIFO lane; P2/P3 share one FIFO lane. Ordering is
  preserved per lane.
- P0/P1 are never dropped, even when lanes are full: the oldest P3/P2 item
  is evicted to make room (eviction logged with reason and timestamp).
- The inbound raw-candle queue holds 1000 items; on overflow there is NO
  backpressure — the oldest item is dropped and QUEUE_OVERFLOW_DROP is
  logged (AI.9).
- Ledger writes are synchronous (AI.8): the ledger writer consumes its
  callback inline; a write failure halts execution (CP-7 owns the writer).
"""

from __future__ import annotations

import asyncio
import itertools
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Awaitable, Callable, Deque, Dict, List, Tuple

from apex.identity.uuid_v7 import uuid_v7

P0 = 0
P1 = 1
P2 = 2
P3 = 3

# Governed lane bounds (AI.7/AI.9): shared lane capacity; raw-candle queue.
DEFAULT_LANE_MAXSIZE = 1000
RAW_CANDLE_QUEUE_MAXSIZE = 1000  # Ch.23/AI.9: 1000 items, no backpressure


class Priority(IntEnum):
    P0 = 0
    P1 = 1
    P2 = 2
    P3 = 3


@dataclass(frozen=True)
class BusEvent:
    priority: int          # P0..P3
    topic: str             # routing label (e.g. 'evidence.E01.BOS')
    payload: Any           # event body (dict/object); not mutated by the bus
    event_id: str          # UUIDv7 operational identity (never in snapshots)
    created_at: float      # UTC epoch seconds (operational only)


Consumer = Callable[[BusEvent], Awaitable[None]]


def make_event(priority: int, topic: str, payload: Any) -> BusEvent:
    """Construct a BusEvent with a fresh UUIDv7 event_id."""
    return BusEvent(
        priority=Priority(priority),
        topic=topic,
        payload=payload,
        event_id=uuid_v7(),
        created_at=time.time(),
    )


@dataclass(frozen=True)
class EvictionRecord:
    reason: str
    timestamp: float
    event_id: str
    priority: int
    topic: str


class EventBus:
    """In-process priority bus. Created per process; no network surface.

    ``subscribe`` registers an async consumer for a topic; ``publish``
    routes by priority: P0 inline (synchronous), P1 dedicated lane, P2/P3
    shared lane. A background ``dispatch`` task drains lanes FIFO.
    """

    def __init__(self, lane_maxsize: int = DEFAULT_LANE_MAXSIZE) -> None:
        self._lane_maxsize = lane_maxsize
        # P1 lane: capacity-bounded ONLY by eviction pressure on the shared
        # lane (Ch.23: P0/P1 are never dropped even when the queue is full).
        self._p1_lane: asyncio.Queue[BusEvent] = asyncio.Queue()
        self._shared_lane: asyncio.Queue[BusEvent] = asyncio.Queue(maxsize=lane_maxsize)
        self._subscribers: Dict[str, List[Consumer]] = {}
        self._evictions: Deque[EvictionRecord] = __import__(
            "collections").deque(maxlen=4096)
        self._dispatcher: asyncio.Task | None = None
        self._counts: Dict[str, int] = {"p0_delivered": 0, "evicted": 0,
                                        "raw_dropped": 0}

    # -- subscription -------------------------------------------------------
    def subscribe(self, topic: str, consumer: Consumer) -> None:
        """Register an async consumer. Multiple consumers per topic are
        delivered in subscription order (ordering preserved)."""
        self._subscribers.setdefault(topic, []).append(consumer)

    def unsubscribe(self, topic: str, consumer: Consumer) -> None:
        subs = self._subscribers.get(topic, [])
        if consumer in subs:
            subs.remove(consumer)

    # -- publish ------------------------------------------------------------
    async def publish(self, event: BusEvent) -> None:
        """Route by priority.

        P0 (synchronous consumer law, AI.12): every subscriber is awaited
        inline, in subscription order — never buffered, never dropped.
        P1: dedicated lane. P2/P3: shared lane. Enqueue never raises when
        full: P0/P1 evict the oldest shared-lane item; P2/P3 drop the
        oldest item (QUEUE_OVERFLOW_DROP), all logged.
        """
        if event.priority == Priority.P0:
            for consumer in self._subscribers.get(event.topic, []):
                await consumer(event)  # synchronous, in publish order
            self._counts["p0_delivered"] += 1
            return
        if event.priority == Priority.P1:
            # P1 is never dropped and never blocks: when the lane is at the
            # governed bound, the oldest P3/P2 item yields to make room.
            if self._p1_lane.qsize() >= self._lane_maxsize:
                self._evict_shared_for_critical(event)
            await self._p1_lane.put(event)
            return
        # P2/P3 shared lane
        if self._shared_lane.full():
            dropped = self._shared_lane.get_nowait()
            self._record_eviction("QUEUE_OVERFLOW_DROP", dropped)
            self._counts["evicted"] += 1
        await self._shared_lane.put(event)

    def _evict_shared_for_critical(self, event: BusEvent) -> None:
        """P0/P1 are never dropped even when the lane is full: the oldest
        P3/P2 item is evicted to make room (Ch.23 critical-alert
        preservation). Eviction is logged with reason and timestamp."""
        try:
            victim = self._shared_lane.get_nowait()
        except asyncio.QueueEmpty:
            # shared lane is empty: reuse its slot by pulling nothing —
            # nothing to evict; put below will fail if lane still full.
            return
        self._record_eviction("EVICT_FOR_CRITICAL", victim)
        self._counts["evicted"] += 1

    def _record_eviction(self, reason: str, event: BusEvent) -> None:
        self._evictions.append(EvictionRecord(
            reason=reason,
            timestamp=time.time(),
            event_id=event.event_id,
            priority=int(event.priority),
            topic=event.topic,
        ))

    # -- delivery -----------------------------------------------------------
    async def dispatch(self) -> None:
        """Drain lanes FIFO forever. P1 lane is drained before the shared
        lane when both are non-empty; ordering within each lane is
        preserved. Stop via ``stop_dispatch``."""
        while True:
            try:
                if not self._p1_lane.empty():
                    event = self._p1_lane.get_nowait()
                else:
                    event = self._shared_lane.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(0)
                continue
            for consumer in self._subscribers.get(event.topic, []):
                await consumer(event)

    def start(self) -> asyncio.Task:
        """Start the background dispatch task (single event loop model)."""
        if self._dispatcher is None or self._dispatcher.done():
            self._dispatcher = asyncio.create_task(self.dispatch())
        return self._dispatcher

    async def stop(self) -> None:
        if self._dispatcher is not None and not self._dispatcher.done():
            self._dispatcher.cancel()
            try:
                await self._dispatcher
            except asyncio.CancelledError:
                pass
            self._dispatcher = None

    # -- observability ------------------------------------------------------
    @property
    def eviction_log(self) -> List[EvictionRecord]:
        return list(self._evictions)

    @property
    def counts(self) -> Dict[str, int]:
        return dict(self._counts)


class RawCandleQueue:
    """Inbound raw-candle queue (Ch.23/AI.9): 1000 items, NO overflow
    backpressure — on overflow the OLDEST item is dropped and
    QUEUE_OVERFLOW_DROP is logged. In-process asyncio.Queue only."""

    def __init__(self, maxsize: int = RAW_CANDLE_QUEUE_MAXSIZE) -> None:
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._drops: Deque[EvictionRecord] = __import__(
            "collections").deque(maxlen=4096)

    async def put(self, candle: Any, event_id: str, topic: str) -> None:
        if self._queue.full():
            oldest = self._queue.get_nowait()
            self._drops.append(EvictionRecord(
                reason="QUEUE_OVERFLOW_DROP",
                timestamp=time.time(),
                event_id=getattr(oldest, "event_id", event_id),
                priority=P2,
                topic=topic,
            ))
        await self._queue.put(candle)

    async def get(self) -> Any:
        return await self._queue.get()

    def qsize(self) -> int:
        return self._queue.qsize()

    @property
    def drop_log(self) -> List[EvictionRecord]:
        return list(self._drops)
