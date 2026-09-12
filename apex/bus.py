"""APEX_GEN5 evidence-event bus (Ch.23 queue priorities; AI.12 Phase 3; G16).

Binding rules implemented:
* In-process ``asyncio`` event bus ONLY — a networked event bus is Wave-Out
  (§9.5-9). No network transport exists here by design.
* Priorities (Ch.23): P0 capital/emergency (highest), P1 setup/forecast/risk,
  P2 routine features/patterns, P3 research/archival (lowest).
* ``P0 = synchronous`` (AI.12): critical events are never buffered — a P0
  publish awaits every matching consumer inline.
* Message ordering preserved (FIFO within a priority lane); no event loss for
  P0/P1. Backpressure is a bounded buffer: when full, the OLDEST P3 then P2
  items are evicted (eviction logged); P0/P1 are never dropped (Ch.23).
* Delivery failures are isolated per consumer and logged; a failing consumer
  never removes an event from the bus (no silent drop).
"""
from __future__ import annotations

import asyncio
import collections
import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Awaitable, Callable, Deque

from apex.identity.uuid_v7 import uuid_v7

__all__ = ["Priority", "BusEvent", "EvictionRecord", "EventBus"]

logger = logging.getLogger("apex.bus")

Handler = Callable[["BusEvent"], Awaitable[None]]


class Priority(IntEnum):
    P0 = 0  # capital alerts, emergency-close signals — never drop, synchronous
    P1 = 1  # major setup, forecast update, risk escalation — never drop
    P2 = 2  # routine features, pattern updates — evictable
    P3 = 3  # research signals, archived outcomes — evictable (first)


@dataclass(frozen=True)
class BusEvent:
    """One labeled evidence/system event on the bus (AI.11: inter-engine
    information flows via labeled evidence events)."""

    topic: str
    payload: Any
    priority: Priority = Priority.P2
    event_id: str = field(default_factory=uuid_v7)
    sequence: int = -1  # assigned by the bus at publish time (monotonic)


@dataclass(frozen=True)
class EvictionRecord:
    evicted_event_id: str
    priority: int
    reason: str


class EventBus:
    """Bounded in-process priority bus.

    * ``publish`` of a P0 event is fully synchronous (awaits all consumers).
    * P1..P3 events enter bounded lanes; the dispatcher delivers in
      priority-then-FIFO order.
    * Overflow evicts oldest P3, then oldest P2 — never P1 (Ch.23).
    """

    def __init__(self, capacity: int = 1024) -> None:
        if capacity < 1:
            raise ValueError("bus capacity must be >= 1")
        self._capacity = capacity
        self._lanes: dict[Priority, Deque[BusEvent]] = {
            Priority.P1: collections.deque(),
            Priority.P2: collections.deque(),
            Priority.P3: collections.deque(),
        }
        self._subscribers: list[tuple[str, Handler]] = []
        self._wake: asyncio.Queue[None] | None = None
        self._sequence = 0
        self.evictions: list[EvictionRecord] = []
        self.published_p0 = 0
        self.delivered_p0 = 0
        self.dropped_low_priority = 0
        self._dispatcher_task: asyncio.Task[None] | None = None
        self._closed = False

    # -- subscription -------------------------------------------------------

    def subscribe(self, topic: str, handler: Handler) -> None:
        """Subscribe ``handler`` to ``topic`` ('*' matches every topic)."""
        self._subscribers.append((topic, handler))

    def _matches(self, topic: str, event: BusEvent) -> list[Handler]:
        return [h for t, h in self._subscribers if t in ("*", topic)]

    # -- publishing ----------------------------------------------------------

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    async def publish(self, event: BusEvent) -> None:
        """Publish an event. P0 is delivered synchronously to all consumers;
        P1..P3 enter the bounded lanes with Ch.23 eviction semantics."""
        if self._closed:
            raise RuntimeError("bus is closed")
        seq = self._next_sequence()
        event = BusEvent(
            topic=event.topic,
            payload=event.payload,
            priority=event.priority,
            event_id=event.event_id,
            sequence=seq,
        )
        if event.priority is Priority.P0:
            # P0 = synchronous; no buffering of critical events (AI.12).
            self.published_p0 += 1
            for handler in self._matches(event.topic, event):
                try:
                    await handler(event)
                except Exception:  # isolate consumer faults; P0 never dropped
                    logger.exception("P0 consumer failed for topic=%s", event.topic)
            self.delivered_p0 += 1
            return
        self._enqueue(event)
        if self._wake is not None:
            self._wake.put_nowait(None)

    def _total_queued(self) -> int:
        return sum(len(d) for d in self._lanes.values())

    def _enqueue(self, event: BusEvent) -> None:
        lane = self._lanes[event.priority]
        if event.priority is Priority.P1:
            # P1 never dropped: make room by evicting P3, then P2 (Ch.23).
            while self._total_queued() >= self._capacity:
                if not self._evict_oldest((Priority.P3, Priority.P2)):
                    # only P1 remains — genuine backpressure; wait is the
                    # fail-closed choice, never a silent drop.
                    raise BufferError("bus full of P1 events (backpressure)")
            lane.append(event)
            return
        # P2/P3: never evict P1; evict oldest P3 then P2 (possibly self-lane).
        if self._total_queued() >= self._capacity:
            if not self._evict_oldest((Priority.P3, Priority.P2)):
                self.dropped_low_priority += 1
                self.evictions.append(
                    EvictionRecord(event.event_id, int(event.priority), "QUEUE_FULL_SELF_DROP")
                )
                logger.warning(
                    "bus full; dropped incoming P%d event %s", int(event.priority), event.event_id
                )
                return
        lane.append(event)

    def _evict_oldest(self, order: tuple[Priority, ...]) -> bool:
        for prio in order:
            lane = self._lanes[prio]
            if lane:
                victim = lane.popleft()
                self.evictions.append(
                    EvictionRecord(victim.event_id, int(prio), "QUEUE_FULL_EVICTION")
                )
                logger.info("evicted oldest P%d event %s (queue full)", int(prio), victim.event_id)
                return True
        return False

    # -- dispatcher -----------------------------------------------------------

    async def start(self) -> None:
        """Start the async dispatcher (single event loop; Ch.23 runtime)."""
        if self._dispatcher_task is None or self._dispatcher_task.done():
            self._wake = asyncio.Queue()
            self._closed = False
            self._dispatcher_task = asyncio.get_running_loop().create_task(self._dispatch())

    async def _dispatch(self) -> None:
        assert self._wake is not None
        while True:
            event = self._pop_next()
            if event is None:
                await self._wake.get()
                continue
            for handler in self._matches(event.topic, event):
                try:
                    await handler(event)
                except Exception:
                    logger.exception("consumer failed for topic=%s", event.topic)

    def _pop_next(self) -> BusEvent | None:
        for prio in (Priority.P1, Priority.P2, Priority.P3):
            lane = self._lanes[prio]
            if lane:
                return lane.popleft()
        return None

    async def drain(self) -> None:
        """Deliver every queued event before returning (test/boot hook)."""
        while True:
            event = self._pop_next()
            if event is None:
                return
            for handler in self._matches(event.topic, event):
                try:
                    await handler(event)
                except Exception:
                    logger.exception("consumer failed for topic=%s", event.topic)

    async def close(self) -> None:
        self._closed = True
        if self._dispatcher_task is not None:
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except (asyncio.CancelledError, Exception):
                pass
            self._dispatcher_task = None
            self._wake = None
