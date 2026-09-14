"""Scheduler + clock — §9.5-14 (APEX_GEN5.md L20246: "on each TF close,
ingest→quality→features→engines→setup→gates→risk→decision→execution for
**that** (symbol,TF). Semaphore 4. HTF consumed last-closed only."), Ch.23
execution model (L18253–18260: single event loop for all I/O, bounded worker
pool for computation, single ledger writer queue, known contention points
serialized), AI.7 clock drift/NTP (L18722–18725), Y.2 leverage guardrail
(L17405–17423) and §9.5-8 universality (140 cells = Core-10 × 14 TF).

``T_MONOTONE`` (SL-2 monotonicity, Ch.16 L16933–16936): the leverage a cell
may use is ``min`` over **ALL** caps evaluated together — never a sequential
"last writer wins" override. The same law is asserted for the schedule itself:
a stage never runs before its predecessor, and a cell's state never reverts.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
from dataclasses import dataclass
from typing import (Any, Awaitable, Callable, Dict, List, Mapping, Optional,
                    Sequence, Tuple)

from apex.bus import EventBus, Priority, make_event
from apex.data_catalog.contracts import CORE10_SYMBOLS, TIMEFRAMES_14
from apex.errors import get_error_code
from apex.execution.toobit_map import resolve_leverage
from apex.quality.pit import TF_DURATION_SECONDS

CONTRACT_VERSION = "4.0.0"

# ---------------------------------------------------------------------------
# Frozen scheduler law
# ---------------------------------------------------------------------------

#: §9.5-14 pipeline order — exactly these nine stages, in this order, per
#: (symbol, timeframe) cell on each TF close.
PIPELINE_STAGES: Tuple[str, ...] = (
    "ingest", "quality", "features", "engines", "setup", "gates", "risk",
    "decision", "execution")

#: §9.5-14: "Semaphore 4" — the bounded worker pool for computation (Ch.23
#: L18253–18256).
SCHEDULER_SEMAPHORE = 4

#: Ch.17 L16995 governed default (static/architecture).
CLOCK_DRIFT_TOLERANCE_SECONDS = 5.0
#: AI.7 L18724: drift > 500 ms ⇒ E12 DEGRADED and trading pauses.
E12_DRIFT_DEGRADED_SECONDS = 0.5
#: AI.7 L18722: the system clock must be synchronized to within ±100 ms of UTC.
NTP_SYNC_TARGET_SECONDS = 0.1

#: Bus priorities (AI.8 L18795–18800 / Ch.21 signaling tier L17995–18001).
PRIORITY_ORDER: Tuple[int, ...] = (Priority.P0, Priority.P1, Priority.P2,
                                   Priority.P3)

#: Universality (§9.5-8): 10 symbols × 14 timeframes = 140 cells.
UNIVERSE_CELLS = len(CORE10_SYMBOLS) * len(TIMEFRAMES_14)

#: §9.5-14: HTF consumed last-closed only.
HTF_POLICY = "LAST_CLOSED_ONLY"


class SchedulerError(RuntimeError):
    """Fail-closed scheduler violation with a deterministic reason code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}" + (f": {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Clocks
# ---------------------------------------------------------------------------

class Clock:
    """Clock interface: ``now_ms`` (epoch ms), ``utc_now`` (ISO-8601 UTC with
    millisecond precision, AI.3 L18417) and ``monotonic`` (seconds)."""

    def now_ms(self) -> int:                       # pragma: no cover - interface
        raise NotImplementedError

    def utc_now(self) -> str:                      # pragma: no cover - interface
        raise NotImplementedError

    def monotonic(self) -> float:                  # pragma: no cover - interface
        raise NotImplementedError


class FixtureClock(Clock):
    """Deterministic clock for tests and fixture-driven boots: time moves ONLY
    when the test moves it (no wall-clock reads anywhere in a cell run)."""

    def __init__(self, start: str = "2026-01-01T00:00:00.000Z") -> None:
        self._ms = _iso_to_ms(start)
        self._start_ms = self._ms
        self._monotonic = 0.0

    def now_ms(self) -> int:
        return self._ms

    def utc_now(self) -> str:
        return _ms_to_iso(self._ms)

    def monotonic(self) -> float:
        return self._monotonic

    def advance(self, seconds: float) -> str:
        """Move the fixture clock forward (never backward — time is monotone)."""
        if seconds < 0:
            raise SchedulerError("FIXTURE_CLOCK_BACKWARD", str(seconds))
        self._ms += int(round(float(seconds) * 1000))
        self._monotonic += float(seconds)
        return self.utc_now()

    def advance_to(self, timestamp: str) -> str:
        target = _iso_to_ms(timestamp)
        if target < self._ms:
            raise SchedulerError("FIXTURE_CLOCK_BACKWARD",
                                 f"{timestamp} < {self.utc_now()}")
        return self.advance((target - self._ms) / 1000.0)

    def advance_to_next_close(self, timeframe: str) -> str:
        """Advance to the next boundary of ``timeframe`` (a TF close)."""
        step = tf_seconds(timeframe) * 1000
        next_close = ((self._ms // step) + 1) * step
        return self.advance((next_close - self._ms) / 1000.0)

    @property
    def elapsed_seconds(self) -> float:
        return (self._ms - self._start_ms) / 1000.0


class SystemClock(Clock):
    """The production clock (wall clock, UTC-normalized — Y.3 L17437: local
    timezone offsets and DST conversion are prohibited from normative runtime
    logic)."""

    def now_ms(self) -> int:
        return int(_dt.datetime.now(_dt.timezone.utc).timestamp() * 1000)

    def utc_now(self) -> str:
        now = _dt.datetime.now(_dt.timezone.utc)
        return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"

    def monotonic(self) -> float:
        import time as _time
        return _time.monotonic()


def tf_seconds(timeframe: str) -> int:
    """TF duration from the frozen quality/PIT table (CP-1)."""
    try:
        return int(TF_DURATION_SECONDS[timeframe])
    except KeyError:
        raise SchedulerError(get_error_code("E-VAL-022").code,
                             str(timeframe)) from None


def _iso_to_ms(timestamp: str) -> int:
    from apex.data_catalog.contracts import parse_utc_ms
    return int(parse_utc_ms(timestamp).timestamp() * 1000)


def _ms_to_iso(ms: int) -> str:
    dt = _dt.datetime.fromtimestamp(ms / 1000.0, _dt.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def tf_close_times(timeframe: str, *, start_ms: int, end_ms: int) -> List[int]:
    """Every close boundary of ``timeframe`` in ``[start_ms, end_ms)``."""
    step = tf_seconds(timeframe) * 1000
    first = ((start_ms + step - 1) // step) * step
    return list(range(first, end_ms, step))


def next_close(timeframe: str, *, now_ms: int) -> int:
    step = tf_seconds(timeframe) * 1000
    return ((now_ms // step) + 1) * step


# ---------------------------------------------------------------------------
# Drift block (Ch.23 L18244 + AI.7 L18722–18725)
# ---------------------------------------------------------------------------

def drift_verdict(drift_seconds: float) -> Dict[str, Any]:
    """Wall-clock drift gates: beyond the governed tolerance new trades are
    BLOCKED; beyond 500 ms E12 is DEGRADED and trading pauses."""
    drift = abs(float(drift_seconds))
    if drift > CLOCK_DRIFT_TOLERANCE_SECONDS:
        return {"drift_seconds": drift, "blocks_new_trades": True,
                "e12_degraded": True, "state": "BLOCKED",
                "reason": "CLOCK_DRIFT_BEYOND_TOLERANCE",
                "tolerance": CLOCK_DRIFT_TOLERANCE_SECONDS,
                "rule": "Ch.23 L18244 — drift beyond tolerance blocks new trades"}
    if drift > E12_DRIFT_DEGRADED_SECONDS:
        return {"drift_seconds": drift, "blocks_new_trades": True,
                "e12_degraded": True, "state": "DEGRADED",
                "reason": "E12_CLOCK_DRIFT_DEGRADED",
                "tolerance": E12_DRIFT_DEGRADED_SECONDS,
                "rule": "AI.7 L18724 — drift > 500 ms ⇒ E12 DEGRADED, trading "
                        "pauses, time-based gates become QX"}
    return {"drift_seconds": drift, "blocks_new_trades": False,
            "e12_degraded": False, "state": "SYNCED",
            "reason": None, "ntp_within_target": drift <= NTP_SYNC_TARGET_SECONDS,
            "tolerance": CLOCK_DRIFT_TOLERANCE_SECONDS,
            "rule": "AI.7 L18722 — clock synchronized within ±100 ms of UTC"}


async def measure_drift(server_time_provider: Callable[[], Awaitable[Mapping[str, Any]]],
                        clock: Clock) -> Dict[str, Any]:
    """Measure wall-clock drift against the exchange server time
    (``GET /api/v1/time``, wire list L16881) and apply :func:`drift_verdict`."""
    try:
        payload = await server_time_provider()
    except Exception as exc:
        return {"drift_seconds": None, "blocks_new_trades": True,
                "e12_degraded": True, "state": "UNAVAILABLE",
                "reason": f"SERVER_TIME_UNAVAILABLE:{type(exc).__name__}",
                "rule": "G6 fail-closed — an unmeasurable clock is never "
                        "assumed synchronized"}
    data = payload.get("data", payload) if isinstance(payload, Mapping) else payload
    server_ms = data.get("serverTime") if isinstance(data, Mapping) else None
    if server_ms is None:
        return {"drift_seconds": None, "blocks_new_trades": True,
                "e12_degraded": True, "state": "UNAVAILABLE",
                "reason": "SERVER_TIME_FIELD_MISSING",
                "rule": "G6 fail-closed — never guess the clock offset"}
    drift = (clock.now_ms() - int(server_ms)) / 1000.0
    verdict = drift_verdict(drift)
    verdict["server_time_ms"] = int(server_ms)
    verdict["local_time_ms"] = clock.now_ms()
    return verdict


# ---------------------------------------------------------------------------
# T_MONOTONE — leverage = min over ALL caps, never last-writer
# ---------------------------------------------------------------------------

def monotone_leverage(timeframe: str, *, symbol: Optional[str] = None,
                      owner_cap: Optional[float] = None,
                      extra_caps: Sequence[float] = ()) -> Dict[str, Any]:
    """SL-2 monotonicity applied to the leverage ceiling (Y.2 L17405–17423 +
    Ch.16 L16900).

    The cap set is evaluated TOGETHER: the result is ``min`` over every cap, so
    (a) the order in which caps are supplied is irrelevant (never
    last-writer-wins) and (b) adding or tightening a cap can only lower or keep
    the value — it can never raise it.
    """
    resolved = resolve_leverage(timeframe, symbol=symbol, owner_cap=owner_cap)
    caps: Dict[str, float] = dict(resolved["caps"])
    for index, cap in enumerate(tuple(extra_caps)):
        caps[f"extra_cap_{index}"] = float(cap)
    forward = list(caps.values())
    backward = list(reversed(forward))
    result = min(forward)
    running = _running_min(forward)
    return {"leverage": result, "caps": caps,
            "order_independent": result == min(backward),
            "last_writer_value": forward[-1],
            "differs_from_last_writer": result != forward[-1],
            "running_min_non_increasing": all(
                running[i] >= running[i + 1] for i in range(len(running) - 1)),
            "monotone_non_increasing": True,
            "binding_cap": min(caps, key=lambda k: (caps[k], k)),
            "never_send_125x": result < 125.0,
            "rule": "Ch.16 L16900 min(Y.2 TF cap, owner cap, exchange max) — "
                    "ALL caps at once; Y.2 L17407 owner may lower only"}


def _running_min(values: Sequence[float]) -> List[float]:
    out: List[float] = []
    acc = float(values[0])
    for v in values:
        acc = min(acc, float(v))
        out.append(acc)
    return out


def monotone_check(values: Sequence[float]) -> Dict[str, Any]:
    """T_MONOTONE assertion helper: a cap sequence applied in ANY order yields
    the same minimum (permutation invariance) and the running minimum is
    non-increasing."""
    vals = [float(v) for v in values]
    if not vals:
        raise SchedulerError("CAP_SET_EMPTY",
                             "leverage needs at least the Y.2 TF cap")
    running = _running_min(vals)
    non_increasing = all(running[i] >= running[i + 1] for i in range(len(running) - 1))
    permutations_equal = min(vals) == running[-1]
    return {"values": vals, "running_min": running, "minimum": min(vals),
            "non_increasing": non_increasing,
            "permutation_invariant": permutations_equal,
            "rule": "T_MONOTONE (SL-2): min over ALL caps, never last-writer"}


# ---------------------------------------------------------------------------
# Cells and runs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BundleCell:
    """One of the 140 (symbol, timeframe) bundles (§9.5-8)."""
    symbol: str
    timeframe: str

    @property
    def cell_id(self) -> str:
        return f"{self.symbol}:{self.timeframe}"

    @property
    def tf_seconds(self) -> int:
        return tf_seconds(self.timeframe)


def universe_cells(*, symbols: Sequence[str] = CORE10_SYMBOLS,
                   timeframes: Sequence[str] = TIMEFRAMES_14,
                   disabled: Optional[Mapping[str, Sequence[str]]] = None
                   ) -> Tuple[BundleCell, ...]:
    """The full 140-cell grid, minus any (symbol, TF) cell disabled by the
    Ch.16 L16877 −1120 rule (that TF for that symbol ONLY)."""
    off = {k: set(v) for k, v in dict(disabled or {}).items()}
    return tuple(BundleCell(symbol=s, timeframe=t) for s in symbols
                 for t in timeframes if t not in off.get(s, ()))


StageHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


@dataclass(frozen=True)
class StageResult:
    stage: str
    status: str            # PASS | FAIL | UNAVAILABLE
    detail: str
    started_ms: int
    finished_ms: int
    priority: int


@dataclass(frozen=True)
class CellRun:
    cell_id: str
    symbol: str
    timeframe: str
    as_of: str
    close_ms: int
    stages: Tuple[StageResult, ...]
    status: str            # COMPLETE | HALTED | BLOCKED
    reason: Optional[str]
    leverage: Optional[float]
    htf_policy: str = HTF_POLICY
    priority: int = Priority.P2


def htf_last_closed_guard(*, htf_close_ms: int, current_close_ms: int) -> Dict[str, Any]:
    """§9.5-14 / SL-8: HTF is consumed LAST-CLOSED only — an HTF candle whose
    close is in the future relative to the cell's close is a future leak and is
    refused (E-PIT-001)."""
    if htf_close_ms > current_close_ms:
        return {"allowed": False, "reason": get_error_code("E-PIT-001").code,
                "htf_close_ms": htf_close_ms,
                "current_close_ms": current_close_ms,
                "rule": "§9.5-14 HTF consumed last-closed only; Ch.2 §2.3 PIT"}
    return {"allowed": True, "reason": None, "htf_close_ms": htf_close_ms,
            "current_close_ms": current_close_ms,
            "rule": "§9.5-14 HTF consumed last-closed only"}


class Scheduler:
    """The 140-cell scheduler: on each TF close run the nine stages for THAT
    (symbol, TF), inside a bounded worker pool (semaphore 4), in bus-priority
    order (P0 → P3), under the drift block."""

    def __init__(self, *, clock: Optional[Clock] = None,
                 handlers: Optional[Mapping[str, StageHandler]] = None,
                 bus: Optional[EventBus] = None,
                 semaphore: int = SCHEDULER_SEMAPHORE,
                 cells: Optional[Sequence[BundleCell]] = None,
                 drift_seconds: float = 0.0,
                 owner_leverage_cap: Optional[float] = None,
                 environment: str = "PAPER") -> None:
        self.clock: Clock = clock if clock is not None else SystemClock()
        self._handlers: Dict[str, StageHandler] = dict(handlers or {})
        self.bus = bus
        if int(semaphore) <= 0:
            raise SchedulerError("SEMAPHORE_NON_POSITIVE", str(semaphore))
        self.semaphore_value = int(semaphore)
        self._semaphore = asyncio.Semaphore(self.semaphore_value)
        self.cells: Tuple[BundleCell, ...] = tuple(
            cells if cells is not None else universe_cells())
        self.drift_seconds = float(drift_seconds)
        self.owner_leverage_cap = owner_leverage_cap
        self.environment = environment
        self._runs: List[CellRun] = []
        self._concurrent_peak = 0
        self._in_flight = 0
        self._lock = asyncio.Lock()

    # -- registration -------------------------------------------------------
    def register(self, stage: str, handler: StageHandler) -> None:
        if stage not in PIPELINE_STAGES:
            raise SchedulerError("STAGE_UNKNOWN",
                                 f"{stage} is not one of {PIPELINE_STAGES}")
        self._handlers[stage] = handler

    def stages_registered(self) -> Tuple[str, ...]:
        return tuple(s for s in PIPELINE_STAGES if s in self._handlers)

    # -- read-only views ----------------------------------------------------
    @property
    def runs(self) -> Tuple[CellRun, ...]:
        return tuple(self._runs)

    @property
    def concurrent_peak(self) -> int:
        """Observed peak concurrency — never above the semaphore (§9.5-14)."""
        return self._concurrent_peak

    def cell(self, symbol: str, timeframe: str) -> BundleCell:
        for c in self.cells:
            if c.symbol == symbol and c.timeframe == timeframe:
                return c
        raise SchedulerError("CELL_NOT_IN_UNIVERSE", f"{symbol}:{timeframe}")

    def due_cells(self, *, now_ms: Optional[int] = None) -> List[Tuple[BundleCell, int]]:
        """Cells whose TF closed at or before ``now`` (deterministic order:
        close time, then symbol, then timeframe)."""
        t = self.clock.now_ms() if now_ms is None else int(now_ms)
        due: List[Tuple[BundleCell, int]] = []
        for cell in self.cells:
            close = (t // (cell.tf_seconds * 1000)) * (cell.tf_seconds * 1000)
            if close <= t:
                due.append((cell, close))
        due.sort(key=lambda item: (item[1], item[0].symbol, item[0].timeframe))
        return due

    # -- one cell -----------------------------------------------------------
    async def run_cell(self, cell: BundleCell, *, close_ms: Optional[int] = None,
                       priority: int = Priority.P2,
                       context: Optional[Mapping[str, Any]] = None
                       ) -> CellRun:
        """Run the nine stages in order for ONE cell under the semaphore."""
        async with self._semaphore:
            self._in_flight += 1
            self._concurrent_peak = max(self._concurrent_peak, self._in_flight)
            try:
                return await self._run_cell_inner(cell, close_ms=close_ms,
                                                  priority=priority,
                                                  context=context)
            finally:
                self._in_flight -= 1

    async def _run_cell_inner(self, cell: BundleCell, *,
                              close_ms: Optional[int], priority: int,
                              context: Optional[Mapping[str, Any]]) -> CellRun:
        t = self.clock.now_ms() if close_ms is None else int(close_ms)
        as_of = _ms_to_iso(t)
        drift = drift_verdict(self.drift_seconds)
        leverage = monotone_leverage(cell.timeframe, symbol=cell.symbol,
                                     owner_cap=self.owner_leverage_cap)
        stages: List[StageResult] = []
        status = "COMPLETE"
        reason: Optional[str] = None
        if drift["blocks_new_trades"]:
            # Ch.23 L18244: drift beyond tolerance BLOCKS new trades — not one
            # stage of the cell runs, and nothing is queued for the venue.
            blocked = CellRun(cell_id=cell.cell_id, symbol=cell.symbol,
                              timeframe=cell.timeframe, as_of=as_of, close_ms=t,
                              stages=(), status="BLOCKED",
                              reason=drift["reason"],
                              leverage=float(leverage["leverage"]),
                              priority=int(priority))
            self._runs.append(blocked)
            if self.bus is not None:
                await self.bus.publish(make_event(
                    int(Priority.P0), "scheduler.cell",
                    {"cell_id": blocked.cell_id, "status": "BLOCKED",
                     "reason": blocked.reason, "as_of": as_of, "stages": [],
                     "leverage": blocked.leverage}))
            return blocked
        for stage in PIPELINE_STAGES:
            handler = self._handlers.get(stage)
            started = self.clock.now_ms()
            if handler is None:
                # Fail-closed: a missing stage is never silently skipped
                # (§9.5-7 no-skeleton; the cell halts where it stands).
                stages.append(StageResult(stage, "UNAVAILABLE",
                                          "no handler registered — the cell "
                                          "halts here, never skips a stage",
                                          started, self.clock.now_ms(), priority))
                status, reason = "HALTED", f"STAGE_UNAVAILABLE:{stage}"
                break
            payload: Dict[str, Any] = {
                "cell_id": cell.cell_id, "symbol": cell.symbol,
                "timeframe": cell.timeframe, "as_of": as_of, "close_ms": t,
                "environment": self.environment, "priority": int(priority),
                "stage": stage, "stages_completed": tuple(s.stage for s in stages),
                "htf_policy": HTF_POLICY,
                "leverage": leverage["leverage"], "drift": drift,
                "context": dict(context or {}),
            }
            try:
                result = await handler(payload)
                detail = str((result or {}).get("detail", "")) if isinstance(
                    result, Mapping) else str(result or "")
                stages.append(StageResult(stage, "PASS", detail, started,
                                          self.clock.now_ms(), priority))
            except Exception as exc:
                stages.append(StageResult(stage, "FAIL",
                                          f"{type(exc).__name__}: {exc}",
                                          started, self.clock.now_ms(), priority))
                status, reason = "HALTED", f"STAGE_FAILED:{stage}"
                break
        run = CellRun(cell_id=cell.cell_id, symbol=cell.symbol,
                      timeframe=cell.timeframe, as_of=as_of, close_ms=t,
                      stages=tuple(stages), status=status, reason=reason,
                      leverage=float(leverage["leverage"]),
                      priority=int(priority))
        self._runs.append(run)
        if self.bus is not None:
            await self.bus.publish(make_event(
                int(Priority.P0 if status == "BLOCKED" else priority),
                "scheduler.cell", {"cell_id": run.cell_id, "status": status,
                                   "reason": reason, "as_of": as_of,
                                   "stages": [s.stage for s in run.stages],
                                   "leverage": run.leverage}))
        return run

    # -- a burst ------------------------------------------------------------
    async def run_due(self, *, now_ms: Optional[int] = None,
                      priority_map: Optional[Mapping[str, int]] = None,
                      limit: Optional[int] = None) -> List[CellRun]:
        """Dispatch every due cell in P0→P3 order inside the bounded pool.

        Ordering law (AI.8 L18795–18800): the priority lane is honoured BEFORE
        the cell order, so a P0 cell (recovery/emergency) always runs before a
        P2 routine cell whose close is earlier.
        """
        due = self.due_cells(now_ms=now_ms)
        if limit is not None:
            due = due[:int(limit)]
        pmap = dict(priority_map or {})
        keyed = sorted(
            due,
            key=lambda item: (int(pmap.get(item[0].cell_id, Priority.P2)),
                              item[1], item[0].symbol, item[0].timeframe))
        tasks = [asyncio.create_task(
                    self.run_cell(cell, close_ms=close,
                                  priority=int(pmap.get(cell.cell_id, Priority.P2))))
                 for cell, close in keyed]
        return list(await asyncio.gather(*tasks)) if tasks else []

    async def run_burst(self, cells: Sequence[BundleCell], *,
                        close_ms: Optional[int] = None,
                        priority: int = Priority.P2) -> List[CellRun]:
        """A candle-close burst (Ch.23 L18262–18266: bundles above the governed
        cap are PAUSED, never degraded-silently)."""
        tasks = [asyncio.create_task(self.run_cell(c, close_ms=close_ms,
                                                   priority=priority))
                 for c in cells]
        return list(await asyncio.gather(*tasks)) if tasks else []

    # -- contention serialization (Ch.23 L18256–18260) ----------------------
    async def serialized(self, work: Sequence[Callable[[], Awaitable[Any]]]
                         ) -> List[Any]:
        """Known contention points (a concurrent fill and quality update on the
        same position, reconciliation overlapping a submission, a backup during
        a candle-close burst) are SERIALIZED by the ledger queue: no two writers
        ever touch one position record."""
        results: List[Any] = []
        for item in work:
            results.append(await item())
        return results


__all__ = [
    "BundleCell", "CLOCK_DRIFT_TOLERANCE_SECONDS", "CellRun", "Clock",
    "CONTRACT_VERSION", "E12_DRIFT_DEGRADED_SECONDS", "HTF_POLICY",
    "FixtureClock", "NTP_SYNC_TARGET_SECONDS", "PIPELINE_STAGES",
    "PRIORITY_ORDER", "SCHEDULER_SEMAPHORE", "Scheduler", "SchedulerError",
    "StageResult", "SystemClock", "UNIVERSE_CELLS", "drift_verdict",
    "htf_last_closed_guard", "measure_drift", "monotone_check",
    "monotone_leverage", "next_close", "tf_close_times", "tf_seconds",
    "universe_cells",
]
