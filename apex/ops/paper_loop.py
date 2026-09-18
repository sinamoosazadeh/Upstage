"""Ch.23 L18253–18266 + Ch.18 W.6/W.8 — the 24/7 PAPER runtime (the long loop).

CP-7 shipped `scripts/run_apex.py demo`: the whole PAPER chain, once, on a
fixture clock. This module is the *continuous* form — one process that boots
reconcile-first, then each cycle runs the frozen 140-cell scheduler with the
nine declared stages, executes whatever governed plan the decision bridge has
produced (the SL-5 → SL-6 hand-off), manages the positions it opened, keeps the
owner informed, protects itself (watchdog heartbeat, storage guard, drift block)
and answers Telegram.

Signal source (declared, never silent)
--------------------------------------
The plan seam is ``plan_provider(symbol, timeframe, as_of) -> Mapping | None``
— the shape of ``TradePlan.to_dict()`` / ``build_trade_plan`` (CP-6's frozen
interface). Two facts shape it:

* the execution FSM materializes the ``trade_plan`` row **at submit time**
  (Ch.16 "materialized BEFORE anything is sent"), so the table is the durable
  *record* of a submission, not an inbox — the runtime therefore reads it to
  refuse double materialization (``PLAN_ALREADY_MATERIALIZED``), never to
  invent work;
* the producer that fills the seam (engines → fabric → setup → forecast → risk
  → plan) is a separate increment and is named as such: without a provider the
  ``setup`` stage refuses with ``NO_PLAN_PROVIDER`` and ``features``/``engines``
  report ``DECLARED_SKIP``. No cell run ever pretends evidence was produced.

Fail-closed everywhere
----------------------
* boot not READY ⇒ the loop runs **read-only**: no plan is executed, and the
  refusal names the boot verdict;
* a cell without market data, a cell without a plan, an out-of-universe or
  disabled interval, a REJECT decision, a malformed plan or a spent per-cycle
  trade budget each produce a NAMED refusal — never a silent skip and never a
  fabricated fill;
* a fill is only recorded when the venue reports it (``apply_adapter_result``);
  otherwise the order stays working and reconciliation owns it.

CONTRACT_VERSION 4.0.0.
"""

from __future__ import annotations

import asyncio
import json
import time
from decimal import Decimal, InvalidOperation
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from apex.config import Config
from apex.data_catalog.contracts import CORE10_SYMBOLS, TIMEFRAMES_14
from apex.execution import fsm as F
from apex.execution.toobit_map import side_for
from apex.ledger import store as LS
from apex.scheduler import clock as C

CONTRACT_VERSION = "4.0.0"

#: The declared signal source of this increment (see the module docstring).
SIGNAL_SOURCE_DECISION_BRIDGE = "DECISION_BRIDGE"
SIGNAL_SOURCE_ENGINE_BRIDGE = "ENGINE_BRIDGE"

#: Bars requested for a cell's PIT window (engines declare 300 by default).
WINDOW_BARS = 300
#: How many venue polls a fresh order gets before the cycle moves on.
FILL_POLL_ATTEMPTS = 3
FILL_POLL_DELAY = 0.0          # tests inject a delay; 0 keeps cycles fast

#: The frozen columns of Ch.16's ``trade_plan`` row.
#: The frozen Ch.16 `trade_plan` columns — aliased from the ledger writer so
#: the SELECT can never drift from the DDL it reads (ISSUE-CP9-003: this
#: tuple previously named two columns the frozen table does not carry, and
#: every plan lookup died with `no such column: leverage`).
TRADE_PLAN_FIELDS: Tuple[str, ...] = LS.TRADE_PLAN_COLUMNS


class PaperLoopError(RuntimeError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class CellRefusal(PaperLoopError):
    """A NAMED refusal inside one pipeline stage (the cell halts, loudly)."""


# ---------------------------------------------------------------------------
# The durable plan record (Ch.16 trade_plan)
# ---------------------------------------------------------------------------

class PlanQueue:
    """Read access to the ``trade_plan`` table.

    A row exists exactly when the execution FSM materialized it, so this class
    answers "has this plan already been sent?" — it is the idempotency guard of
    the runtime, not a source of work.
    """

    def __init__(self, store: Any, ledger: Any, *,
                 environment: str = "PAPER") -> None:
        self.store = store
        self.ledger = ledger
        self.environment = environment

    async def materialized_ids(self) -> Dict[str, Dict[str, Any]]:
        """``proposal_id → row`` for the plans already materialized."""
        cursor = await self.store.db.execute(
            "SELECT " + ",".join(TRADE_PLAN_FIELDS) + " FROM trade_plan "
            "WHERE environment = ? ORDER BY created_utc, proposal_id",
            (self.environment,))
        rows = await cursor.fetchall()
        out: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            record = dict(row) if isinstance(row, Mapping) else {
                key: row[index] for index, key in enumerate(TRADE_PLAN_FIELDS)}
            out[str(record["proposal_id"])] = record
        return out

    async def counts(self) -> Dict[str, int]:
        materialized = await self.materialized_ids()
        ledger = await self.ledger.read_ledger()
        sent = {str(e.intent_id) for e in ledger
                if e.event_type == "TRADE_PLAN" and e.intent_id}
        return {"materialized": len(materialized),
                "sent": len(sent & set(materialized))}


def normalize_plan(source: Mapping[str, Any]) -> F.TradePlan:
    """A ``TradePlan.to_dict()``-shaped mapping (or a ``trade_plan`` row) → the
    frozen :class:`TradePlan`.

    A malformed plan is REFUSED (never guessed at): the error detail lists the
    exact columns that failed, and nothing is submitted.
    """
    problems: List[str] = []
    vetoes: Any = source.get("vetoes_applied") or []
    if isinstance(vetoes, str):
        try:
            vetoes = json.loads(vetoes or "[]")
        except (ValueError, json.JSONDecodeError):
            problems.append("vetoes_applied")
            vetoes = []
    try:
        vetoes_tuple = tuple(int(v) for v in (vetoes or ()))
    except (TypeError, ValueError):
        problems.append("vetoes_applied")
        vetoes_tuple = ()
    try:
        quantity = float(source.get("sized_quantity"))
    except (TypeError, ValueError):
        quantity = float("nan")
        problems.append("sized_quantity")
    if not quantity or quantity != quantity or quantity <= 0:
        problems.append("sized_quantity<=0")
    if str(source.get("decision")) not in ("ALLOW", "REDUCE", "REJECT"):
        problems.append("decision")
    if str(source.get("direction")) not in ("LONG", "SHORT", "FLAT"):
        problems.append("direction")
    if (source.get("stop_price") is None) != (source.get("target_price") is None):
        problems.append("stop/target pair")
    if not source.get("proposal_id") or not source.get("setup_id"):
        problems.append("identity")
    if problems:
        raise CellRefusal("PLAN_MALFORMED", ",".join(sorted(set(problems))))
    return F.TradePlan(
        proposal_id=str(source["proposal_id"]), setup_id=str(source["setup_id"]),
        symbol=str(source.get("symbol") or ""),
        timeframe=str(source.get("timeframe") or ""),
        direction=str(source["direction"]),
        entry_ref=str(source.get("entry_ref") or ""),
        stop_price=_f(source.get("stop_price")),
        target_price=_f(source.get("target_price")),
        sized_quantity=quantity, risk_amount=_f(source.get("risk_amount")),
        contract_multiplier=_f(source.get("contract_multiplier")),
        decision=str(source["decision"]), vetoes_applied=vetoes_tuple,
        risk_state=source.get("risk_state"),
        package_version=source.get("package_version"),
        snapshot_id=str(source.get("snapshot_id") or ""),
        as_of=str(source.get("as_of") or ""),
        created_utc=str(source.get("created_utc") or ""),
        lineage=str(source.get("lineage") or ""),
        payload_hash=str(source.get("payload_hash") or ""),
        environment=str(source.get("environment") or "PAPER"),
        leverage=_f(source.get("leverage")),
        owner_leverage_cap=_f(source.get("owner_leverage_cap")))


def _f(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fill_from_result(result: Any, plan: F.TradePlan,
                     *, suffix: str = "") -> Optional[Dict[str, str]]:
    """Extract the EXECUTED price/quantity from a venue result.

    Returns ``None`` when the venue did not report both numbers — a fill is
    never inferred (fail-closed; the order then stays working and the next
    reconciliation owns it).
    """
    if getattr(result, "outcome", None) not in ("FILLED", "PARTIAL"):
        return None
    data = dict(getattr(result, "data", None) or {})
    inner = data.get("data")
    inner = dict(inner) if isinstance(inner, Mapping) else data
    price = inner.get("avgPrice") or inner.get("price") or inner.get("fillPrice")
    quantity = (inner.get("executedQty") or inner.get("quantity")
                or inner.get("filledQty"))
    if price is None or quantity is None:
        return None
    fill_id = str(inner.get("tradeId") or inner.get("fillId")
                  or getattr(result, "order_id", "") or plan.proposal_id)
    return {"fill_id": f"{fill_id}{suffix}", "price": str(price),
            "quantity": str(quantity), "order_id": str(getattr(result, "order_id",
                                                              "") or "")}


async def last_closed_price(store: Any, symbol: str, timeframe: str,
                            as_of: str) -> Optional[str]:
    """The PIT-safe reference price: the CLOSE of the last closed bar at
    ``as_of``. Never a live tick, never a fabricated number."""
    window = await store.get_window(symbol, timeframe, as_of, 1)
    if not window:
        return None
    close = window[-1].close
    return str(close) if close is not None else None


# ---------------------------------------------------------------------------
# The runtime
# ---------------------------------------------------------------------------

class PaperRuntime:
    """One event loop, one ledger writer, one scheduler — the long run."""

    def __init__(self, *, config: Optional[Config] = None, store: Any,
                 ledger: LS.LedgerWriter, bus: Any = None,
                 adapter: Any = None, signaling: Any = None,
                 control: Any = None, gateway: Any = None,
                 watchdog: Any = None,
                 clock: Optional[C.Clock] = None,
                 environment: str = "PAPER",
                 cells: Optional[Sequence[Any]] = None,
                 notifier: Optional[Callable[[str], Awaitable[Any]]] = None,
                 plan_provider: Optional[Callable[..., Any]] = None,
                 catch_up: Optional[Callable[[int], Awaitable[Any]]] = None,
                 signal_source: str = SIGNAL_SOURCE_DECISION_BRIDGE,
                 max_trades_per_cycle: int = 4,
                 max_cells_per_cycle: Optional[int] = None,
                 fill_poll_attempts: int = FILL_POLL_ATTEMPTS,
                 fill_poll_delay: float = FILL_POLL_DELAY,
                 now: Optional[Callable[[], float]] = None) -> None:
        self.config = config or Config()
        self.store = store
        self.ledger = ledger
        self.bus = bus
        self.adapter = adapter
        self.signaling = signaling
        self.control = control
        self.gateway = gateway
        self.watchdog = watchdog
        self.clock: C.Clock = clock if clock is not None else C.SystemClock()
        self.environment = environment
        self.cells = tuple(cells) if cells is not None else ()
        self.notifier = notifier
        self.plan_provider = plan_provider
        self.catch_up = catch_up
        self._catch_up_failed: Dict[str, Any] = {}
        self._context_preparation_failed: Dict[str, Any] = {}
        self.signal_source = signal_source
        self.max_trades_per_cycle = int(max_trades_per_cycle)
        self.max_cells_per_cycle = (None if max_cells_per_cycle is None
                                    else int(max_cells_per_cycle))
        self.fill_poll_attempts = int(fill_poll_attempts)
        self.fill_poll_delay = float(fill_poll_delay)
        self._now = now or time.time
        self.plans = PlanQueue(store, ledger, environment=environment)
        self.scheduler = C.Scheduler(
            clock=self.clock, bus=bus, cells=self.cells or None,
            environment=environment, handlers=self._stage_handlers())
        self.boot_verdict: Dict[str, Any] = {}
        self.cycles: List[Dict[str, Any]] = []
        self.working: Dict[str, F.ExecutionFSM] = {}
        self.trades: List[Dict[str, Any]] = []
        self._budget_taken = 0        # per-cycle admission reservations
        self.refusals: List[Dict[str, Any]] = []
        self._last_close: Dict[str, int] = {}
        self._stopped = False

    # -- lifecycle -----------------------------------------------------------
    async def boot(self, *, drift_seconds: Optional[float] = 0.0, **kwargs: Any
                   ) -> Dict[str, Any]:
        machine = F.StartupReconciliation(
            ledger=self.ledger, adapter=self.adapter, bus=self.bus,
            clock=self.clock.monotonic, utc_now=self.clock.utc_now,
            environment=self.environment, drift_seconds=drift_seconds,
            **kwargs)
        self.boot_verdict = await machine.run()
        return self.boot_verdict

    @property
    def trading_enabled(self) -> bool:
        return bool(self.boot_verdict.get("new_trades_allowed"))

    # -- stages --------------------------------------------------------------
    def _stage_handlers(self) -> Dict[str, Any]:
        return {
            "ingest": self._stage_ingest,
            "quality": self._stage_quality,
            "features": self._stage_features,
            "engines": self._stage_engines,
            "setup": self._stage_setup,
            "gates": self._stage_gates,
            "risk": self._stage_risk,
            "decision": self._stage_decision,
            "execution": self._stage_execution,
        }

    async def _stage_ingest(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        window = await self.store.get_window(payload["symbol"], payload["timeframe"],
                                             payload["as_of"], WINDOW_BARS)
        if not window:
            raise CellRefusal("NO_MARKET_DATA",
                              f"{payload['cell_id']} has no bars at or before "
                              f"{payload['as_of']} — run `bootstrap` first")
        self._state(payload)["window"] = list(window)
        return {"detail": f"window={len(window)} bars "
                          f"last_closed={window[-1].timestamp}"}

    async def _stage_quality(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        window = self._state(payload).get("window") or []
        open_bars = [o for o in window if getattr(o, "status", "CLOSED") != "CLOSED"]
        if open_bars:
            raise CellRefusal("DATA_QUALITY_QX",
                              f"{len(open_bars)} non-CLOSED bars in the window")
        return {"detail": f"window accepted (CLOSED only) · "
                          f"last_availability="
                          f"{getattr(window[-1], 'availability_time', None)}"}

    async def _stage_features(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """Declared skip: this increment consumes governed plans and does not
        produce engine evidence — and it never pretends otherwise."""
        if self.signal_source == SIGNAL_SOURCE_DECISION_BRIDGE:
            return {"detail": "DECLARED_SKIP signal_source=DECISION_BRIDGE "
                              "(the engine→evidence bridge is a separate "
                              "increment; plans enter through plan_provider)"}
        if self.signal_source == SIGNAL_SOURCE_ENGINE_BRIDGE:
            raise CellRefusal("ENGINE_BRIDGE_PENDING",
                              "signal_source=ENGINE_BRIDGE requested but the "
                              "engine→setup bridge is not wired in this "
                              "increment")
        count = await self._evidence_count(payload["symbol"], payload["timeframe"])
        if count == 0:
            raise CellRefusal("NO_EVIDENCE_FOR_CELL",
                              f"{payload['cell_id']} has no admitted evidence")
        return {"detail": f"evidence_rows={count}"}

    async def _stage_engines(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        if self.signal_source == SIGNAL_SOURCE_ENGINE_BRIDGE:
            raise CellRefusal("ENGINE_BRIDGE_PENDING",
                              "signal_source=ENGINE_BRIDGE requested but the "
                              "engine→setup bridge is not wired in this "
                              "increment")
        return {"detail": "DECLARED_SKIP signal_source=DECISION_BRIDGE "
                          "(the plan seam is the frozen SL-5 → SL-6 interface)"}

    def _take_budget(self) -> bool:
        """Reserve one slot of this cycle's trade budget.

        Cells are scheduled CONCURRENTLY (the scheduler's semaphore is 4), so
        counting only the trades already appended would let two cells admit at
        once. The budget is therefore reserved at admission — fail-closed,
        never over-trading; a plan refused later in the chain does not refund
        the reservation.
        """
        if self._budget_taken >= self.max_trades_per_cycle:
            return False
        self._budget_taken += 1
        return True

    async def _stage_setup(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        if payload["cell_id"] in self._catch_up_failed:
            raise CellRefusal("CATCH_UP_FAILED",
                              self._catch_up_failed[payload["cell_id"]]["error_code"])
        if payload["cell_id"] in self._context_preparation_failed:
            failed = self._context_preparation_failed[payload["cell_id"]]
            raise CellRefusal(failed["reason"], failed["detail"])
        # The cycle trade budget is checked BEFORE the plan is asked for: once
        # it is exhausted the cell halts by name instead of materializing work
        # that can never be sent (the execution stage keeps the same guard).
        if not self._take_budget():
            raise CellRefusal("TRADE_BUDGET_REACHED",
                              f"max_trades_per_cycle="
                              f"{self.max_trades_per_cycle}")
        plan = await self._resolve_plan(payload)
        self._state(payload)["plan"] = plan
        return {"detail": f"plan={plan.get('proposal_id')} "
                          f"setup={plan.get('setup_id')} "
                          f"decision={plan.get('decision')}"}

    async def _stage_gates(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        plan = self._state(payload).get("plan") or {}
        symbol, timeframe = str(plan.get("symbol")), str(plan.get("timeframe"))
        if (symbol, timeframe) != (payload["symbol"], payload["timeframe"]):
            raise CellRefusal("PLAN_CELL_MISMATCH",
                              f"{symbol}:{timeframe} != {payload['cell_id']}")
        if symbol not in CORE10_SYMBOLS or timeframe not in TIMEFRAMES_14:
            raise CellRefusal("PLAN_CELL_OUT_OF_UNIVERSE", f"{symbol}:{timeframe}")
        if str(plan.get("environment")) != self.environment:
            raise CellRefusal("PLAN_ENVIRONMENT_MISMATCH",
                              f"{plan.get('environment')} != {self.environment}")
        if str(plan.get("decision")) == "REJECT":
            raise CellRefusal("PLAN_REJECTED_BY_RISK",
                              "the Risk Kernel's REJECT verdict is final")
        if self.adapter is not None and hasattr(self.adapter, "is_interval_disabled"):
            if self.adapter.is_interval_disabled(symbol, timeframe):
                raise CellRefusal("INTERVAL_DISABLED_FOR_CELL",
                                  f"{symbol}:{timeframe} (business code −1120)")
        materialized = await self.plans.materialized_ids()
        if str(plan.get("proposal_id")) in materialized:
            raise CellRefusal("PLAN_ALREADY_MATERIALIZED",
                              f"{plan.get('proposal_id')} already has a "
                              f"trade_plan row (never send a plan twice)")
        # ISSUE-CP9-004: `outcome.setup_id` is a FK to `setup_candidate`
        # (frozen Ch.5 DDL), so
        # a plan whose setup row does not exist could never be closed and
        # booked: refuse it NOW, by name, instead of dying at outcome time
        # (fail-closed; no orphan trade_plan rows, no half-executed plans).
        setup_id = str(plan.get("setup_id") or "")
        if not await self._setup_exists(setup_id):
            raise CellRefusal("NO_SETUP_ROW_FOR_PLAN",
                              f"setup_id={setup_id!r} is not in "
                              "setup_candidate (the outcome FK keys on it)")
        return {"detail": "pre_submission_gates=PASS"}

    async def _stage_risk(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        plan = self._state(payload).get("plan") or {}
        issues: List[str] = []
        if float(plan.get("sized_quantity") or 0) <= 0:
            issues.append("sized_quantity<=0")
        if plan.get("risk_amount") is not None and float(plan["risk_amount"]) < 0:
            issues.append("risk_amount<0")
        if str(plan.get("decision")) == "REDUCE" and plan.get("risk_amount") is None:
            issues.append("REDUCE without risk_amount")
        if issues:
            raise CellRefusal("RISK_REVALIDATION_FAILED", ",".join(issues))
        return {"detail": f"risk_state={plan.get('risk_state')} "
                          f"vetoes={list(plan.get('vetoes_applied') or [])} "
                          f"(no re-adjudication: the kernel's verdict is "
                          f"autonomous)"}

    async def _stage_decision(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        plan = normalize_plan(self._state(payload).get("plan") or {})
        self._state(payload)["plan_obj"] = plan
        return {"detail": f"trade_plan={plan.proposal_id} qty={plan.sized_quantity} "
                          f"stop={plan.stop_price} target={plan.target_price}"}

    async def _stage_execution(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        state = self._state(payload)
        plan: F.TradePlan = state["plan_obj"]
        if not self.trading_enabled:
            raise CellRefusal("BOOT_NOT_READY",
                              f"boot_state={self.boot_verdict.get('boot_state')} "
                              f"new_trades_allowed=False")
        if len(self.trades) >= self.max_trades_per_cycle:
            raise CellRefusal("TRADE_BUDGET_REACHED",
                              f"max_trades_per_cycle={self.max_trades_per_cycle}")
        price = await last_closed_price(self.store, plan.symbol, plan.timeframe,
                                        payload["as_of"])
        if price is None:
            raise CellRefusal("NO_PRICE_FOR_CELL", "no closed bar to price against")
        record = await self.execute_plan(plan, price=price,
                                         timestamp_utc=payload["as_of"])
        state["trade"] = record
        return {"detail": f"intent={record['intent_id']} state={record['state']} "
                          f"fill={record.get('fill')} protected="
                          f"{record.get('protected')}"}

    async def _resolve_plan(self, payload: Mapping[str, Any]
                            ) -> Mapping[str, Any]:
        """Ask the decision bridge for this cell's plan (the frozen SL-5 → SL-6
        seam). No provider ⇒ a NAMED refusal, never a fabricated plan."""
        if self.plan_provider is None:
            raise CellRefusal(
                "NO_PLAN_PROVIDER",
                "no plan provider is wired: the engine → fabric → setup → "
                "forecast → risk → plan bridge is a separate increment "
                "(PHASE2_HANDOFF_WIRING §REMAINING WORK)")
        provided = self.plan_provider(payload["symbol"], payload["timeframe"],
                                      payload["as_of"])
        plan = await provided if hasattr(provided, "__await__") else provided
        if plan is None:
            raise CellRefusal("NO_PLAN_FOR_CELL",
                              f"{payload['cell_id']} has no governed plan at "
                              f"{payload['as_of']}")
        if not isinstance(plan, Mapping):
            raise CellRefusal("PLAN_TYPE_QX", type(plan).__name__)
        return dict(plan)

    async def _setup_exists(self, setup_id: str) -> bool:
        if not setup_id:
            return False
        cursor = await self.store.db.execute(
            "SELECT 1 FROM setup_candidate WHERE setup_id=? LIMIT 1",
            (setup_id,))
        return await cursor.fetchone() is not None

    async def _evidence_count(self, symbol: str, timeframe: str) -> int:
        cursor = await self.store.db.execute(
            "SELECT COUNT(*) FROM evidence_event WHERE symbol=? AND timeframe=?",
            (symbol, timeframe))
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    def _state(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        holder = payload.get("context") or {}
        return holder.setdefault("cell_state", {})

    # -- one plan, end to end ------------------------------------------------
    async def execute_plan(self, plan: F.TradePlan, *, price: Any,
                           timestamp_utc: Optional[str] = None
                           ) -> Dict[str, Any]:
        """submit → observe → record fill → protect → manage (one plan)."""
        machine = F.ExecutionFSM(
            intent_id=f"i-{str(plan.proposal_id)[-12:]}", ledger=self.ledger,
            adapter=self.adapter, bus=self.bus, clock=self.clock.monotonic,
            utc_now=self.clock.utc_now, environment=self.environment)
        submitted = await machine.submit(plan, price=price,
                                         timestamp_utc=timestamp_utc)
        # The FSM returns a venue answer whenever the adapter round-trip
        # happened (``apply_adapter_result``), and a validation refusal when it
        # never left READY (``submit``). A REFUSED classification means the
        # adapter's own guard stopped the order before the exchange saw it —
        # that is NOT a submission either (fail-closed record).
        accepted = ("outcome" in submitted
                    and submitted.get("classification") != "REFUSED")
        record: Dict[str, Any] = {
            "proposal_id": plan.proposal_id, "intent_id": machine.intent_id,
            "symbol": plan.symbol, "timeframe": plan.timeframe,
            "direction": plan.direction, "price_source": "LAST_CLOSED_BAR",
            "price": str(price), "submitted": accepted,
            "outcome": submitted.get("outcome"), "state": machine.state,
            "fill": None, "protected": False,
            "reason": submitted.get("reason") or (
                "REFUSED_BEFORE_SUBMISSION"
                if submitted.get("classification") == "REFUSED" else None)}
        if not accepted:
            self.refusals.append({"cell": f"{plan.symbol}:{plan.timeframe}",
                                  **record})
            self.trades.append(record)
            return record
        if machine.state == "FILLED":
            # The venue answered the SUBMISSION itself with a fill: the numbers
            # come from that response — no second FSM transition (the frozen
            # matrix has none from FILLED) and no re-query.
            observed = await self._record_submission_fill(machine, plan)
        else:
            observed = await self._observe_fill(machine, plan)
        record["fill"] = observed
        if observed.get("filled"):
            protection = await machine.place_protection(
                stop_price=plan.stop_price, target_price=plan.target_price)
            record["protected"] = bool(protection.get("protected"))
            if record["protected"]:
                await machine.activate_management()
            self.working[machine.intent_id] = machine
        record["state"] = machine.state
        self.trades.append(record)
        return record

    async def _record_submission_fill(self, machine: F.ExecutionFSM,
                                      plan: F.TradePlan) -> Dict[str, Any]:
        """Record the fill the SUBMISSION response reported (source
        SUBMIT_RESULT) — or refuse to record incomplete venue numbers."""
        result = machine.last_adapter_result
        fill = fill_from_result(result, plan) if result is not None else None
        if fill is None:
            return {"filled": False, "outcome": "FILLED", "attempt": 1,
                    "source": "SUBMIT_RESULT", "reason": "FILL_DATA_INCOMPLETE"}
        await machine.record_fill(fill_id=fill["fill_id"], price=fill["price"],
                                  quantity=fill["quantity"], symbol=plan.symbol)
        return {"filled": True, "outcome": "FILLED", "attempt": 1,
                "source": "SUBMIT_RESULT", "fill_id": fill["fill_id"],
                "price": fill["price"], "quantity": fill["quantity"]}

    async def _observe_fill(self, machine: F.ExecutionFSM,
                            plan: F.TradePlan) -> Dict[str, Any]:
        """Ask the venue (never the ledger, never a guess) whether the order
        filled. ``scope='single'`` is the Ch.16 keyed query."""
        if self.adapter is None:
            return {"filled": False, "reason": "NO_ADAPTER"}
        for attempt in range(max(1, self.fill_poll_attempts)):
            result = await self.adapter.query_order_state(
                symbol=plan.symbol, client_order_id=machine.intent_id,
                scope="single")
            if result.outcome == "ACKNOWLEDGED" and \
                    machine.state in ("ACKNOWLEDGED", "PARTIAL"):
                # a repeated ACK is not a second transition (Ch.16: exactly one
                # transition per adapter outcome) — poll again instead.
                applied = {"outcome": machine.state, "state": machine.state,
                           "classification": result.classification}
            else:
                applied = await machine.apply_adapter_result(result)
            if applied.get("outcome") in ("FILLED", "PARTIAL"):
                fill = fill_from_result(result, plan)
                if fill is None:
                    # The FSM knows it filled; the venue did not report the
                    # numbers, so nothing is recorded — protect, never invent.
                    return {"filled": False, "outcome": applied["outcome"],
                            "attempt": attempt + 1, "source": "VENUE_QUERY",
                            "reason": "FILL_DATA_INCOMPLETE"}
                await machine.record_fill(
                    fill_id=fill["fill_id"], price=fill["price"],
                    quantity=fill["quantity"], symbol=plan.symbol)
                return {"filled": True, "outcome": applied["outcome"],
                        "attempt": attempt + 1, "source": "VENUE_QUERY",
                        "fill_id": fill["fill_id"], "price": fill["price"],
                        "quantity": fill["quantity"]}
            if applied.get("outcome") in ("REJECTED", "CANCELLED"):
                return {"filled": False, "outcome": applied["outcome"],
                        "attempt": attempt + 1, "source": "VENUE_QUERY"}
            if self.fill_poll_delay:
                await asyncio.sleep(self.fill_poll_delay)
        return {"filled": False, "outcome": "ACKNOWLEDGED",
                "source": "VENUE_QUERY", "reason": "FILL_NOT_OBSERVED_YET"}

    async def manage_positions(self, *, as_of: str) -> List[Dict[str, Any]]:
        """Exit management: a MANAGED position closes when the last closed bar
        reaches its stop or first target. Nothing is closed on a guess."""
        actions: List[Dict[str, Any]] = []
        for intent_id, machine in list(self.working.items()):
            if machine.state != "MANAGED" or machine._plan is None:
                continue
            plan = machine._plan
            price = await last_closed_price(self.store, plan.symbol,
                                            plan.timeframe, as_of)
            if price is None:
                continue
            entry = machine._fills[0]["price"] if getattr(machine, "_fills", None) else None
            quantity = plan.sized_quantity
            stop, target = plan.stop_price, plan.target_price
            try:
                last = Decimal(price)
            except (InvalidOperation, TypeError):
                continue
            reason = None
            if stop is not None and (
                    (plan.direction == "LONG" and last <= Decimal(str(stop)))
                    or (plan.direction == "SHORT" and last >= Decimal(str(stop)))):
                reason = "STOP"
            elif target is not None and (
                    (plan.direction == "LONG" and last >= Decimal(str(target)))
                    or (plan.direction == "SHORT" and last <= Decimal(str(target)))):
                reason = "TARGET_1"
            if reason is None:
                continue
            pnl = None
            exit_result = await self.adapter.submit_order(
                intent_id=f"{intent_id}-exit", symbol=plan.symbol,
                timeframe=plan.timeframe, direction=plan.direction,
                quantity=quantity, price=price, phase="flatten", kind="exit",
                reduce_only=True, timestamp_utc=as_of)
            fill = fill_from_result(exit_result, plan, suffix="-exit")
            if fill is None:
                # not (yet) filled at the venue: the position stays open and the
                # next cycle re-evaluates — never a booked exit on a guess.
                actions.append({"intent_id": intent_id, "exit_reason": reason,
                                "state": machine.state, "filled": False,
                                "outcome": getattr(exit_result, "outcome", None),
                                "note": "exit order not filled at the venue"})
                continue
            await machine.record_fill(
                fill_id=fill["fill_id"], price=fill["price"],
                quantity=fill["quantity"], symbol=plan.symbol,
                # Ch.16 ONE_WAY side map: an exit is a FLATTEN phase
                side=side_for(plan.direction, "flatten"))
            try:
                move = Decimal(fill["price"]) - Decimal(str(entry or fill["price"]))
                if plan.direction == "SHORT":
                    move = -move
                pnl = str(move * Decimal(str(quantity)))
            except (InvalidOperation, TypeError):
                pnl = None
            closed = await machine.close_position(
                exit_price=fill["price"], quantity=fill["quantity"],
                exit_reason=reason, setup_id=plan.setup_id, pnl=pnl)
            reconciled = await machine.reconcile()
            actions.append({"intent_id": intent_id, "exit_reason": reason,
                            "exit_price": fill["price"], "state": machine.state,
                            "filled": True, "pnl": pnl,
                            "stop_gap": closed.get("stop_gap"),
                            "reconciled": reconciled.get("agree")})
            self.working.pop(intent_id, None)
        return actions

    # -- one cycle -----------------------------------------------------------
    async def run_cycle(self, *, now_ms: Optional[int] = None) -> Dict[str, Any]:
        moment = self.clock.now_ms() if now_ms is None else int(now_ms)
        as_of = _ms_to_iso(moment)
        self._budget_taken = 0
        cycle: Dict[str, Any] = {"cycle": len(self.cycles) + 1, "as_of": as_of,
                                 "signal_source": self.signal_source,
                                 "trading_enabled": self.trading_enabled}
        cycle["catch_up"] = (await self.catch_up(moment) if self.catch_up else
                             {"cells_checked": 0, "cells_updated": 0,
                              "bars_ingested": 0, "failures": []})
        self._catch_up_failed = {row["cell"]: row
                                 for row in cycle["catch_up"]["failures"]}
        if self.watchdog is not None:
            cycle["heartbeat"] = await _maybe_await(self.watchdog.heartbeat())
        cycle["storage"] = await self._storage_guard()
        if self.gateway is not None:
            cycle["telegram"] = await self.gateway.run_once()
        # The scheduler's law is "on each TF close run the stages for THAT
        # cell": a cell runs once per close, and a cell whose close has not
        # advanced since the previous cycle is not run again.
        due = [item for item in self.scheduler.due_cells(now_ms=moment)
               if item[1] > self._last_close.get(item[0].cell_id, -1)]
        if self.max_cells_per_cycle is not None:
            due = due[:self.max_cells_per_cycle]
        # G1: all expensive source preparation completes before run_cell
        # starts its latency clock. D22 failures never enter preparation;
        # a failed source must not fall back to its previous cached success.
        self._context_preparation_failed = {}
        preparation = {"cells_checked": 0, "cells_prepared": 0, "failures": []}
        prepare = getattr(self.plan_provider, "prepare", None)
        if callable(prepare):
            for cell, close in due:
                if cell.cell_id in self._catch_up_failed:
                    continue
                preparation["cells_checked"] += 1
                try:
                    await _maybe_await(prepare(cell.symbol, cell.timeframe, _ms_to_iso(close)))
                    preparation["cells_prepared"] += 1
                except Exception as exc:
                    failed = {"cell": cell.cell_id,
                              "reason": getattr(exc, "reason", "ENGINE_CONTEXT_PREPARATION_FAILED"),
                              "detail": getattr(exc, "detail", type(exc).__name__)}
                    self._context_preparation_failed[cell.cell_id] = failed
                    preparation["failures"].append(failed)
        cycle["context_preparation"] = preparation
        tasks = [asyncio.create_task(self.scheduler.run_cell(
                    cell, close_ms=close, context={"cell_state": {}}))
                 for cell, close in due]
        runs = list(await asyncio.gather(*tasks)) if tasks else []
        import dataclasses
        cycle["cell_runs"] = [dataclasses.asdict(run) for run in runs]
        cycle["cells_due"] = len(due)
        cycle["cells_complete"] = sum(1 for r in runs if r.status == "COMPLETE")
        cycle["cells_halted"] = sum(1 for r in runs if r.status == "HALTED")
        cycle["cells_blocked"] = sum(1 for r in runs if r.status == "BLOCKED")
        halt_reasons: Dict[str, int] = {}
        halt_stages: Dict[str, int] = {}
        for run in runs:
            if run.status != "HALTED":
                continue
            failed = [st for st in run.stages if st.status == "FAIL"]
            stage = failed[-1].stage if failed else str(run.reason or "").split(
                ":", 1)[-1]
            code = _refusal_code(failed[-1]) if failed else str(run.reason)
            halt_reasons[code] = halt_reasons.get(code, 0) + 1
            halt_stages[stage] = halt_stages.get(stage, 0) + 1
        cycle["halt_reasons"] = halt_reasons
        cycle["halt_stages"] = halt_stages
        for run in runs:
            if (run.cell_id in self._catch_up_failed
                    or run.cell_id in self._context_preparation_failed):
                continue
            self._last_close[run.cell_id] = max(
                self._last_close.get(run.cell_id, -1), int(run.close_ms))
        cycle["trades"] = [r for r in runs if r.status == "COMPLETE"]
        cycle["managed"] = await self.manage_positions(as_of=as_of)
        cycle["open_intents"] = sorted(self.working)
        if self.notifier is not None:
            await self._report(cycle)
        self.cycles.append(_plain(cycle))
        return cycle

    async def _storage_guard(self) -> Dict[str, Any]:
        """AI.7/Ch.23: free-space floor + the > 80 % STORAGE alert, evaluated
        by the CP-8 policy function (one source of truth for the thresholds)."""
        import os
        import shutil
        from apex.ops.backup import storage_guard
        usage = shutil.disk_usage(self._storage_root())
        total = usage.total or 1
        verdict = storage_guard(free_fraction=usage.free / total)
        verdict["free_mb"] = round(usage.free / (1024.0 * 1024.0), 1)
        if self.signaling is not None and verdict["storage_alert"]:
            verdict["alert"] = await self.signaling.check_storage(
                used_fraction=verdict["used_fraction"], snapshot_id="paper-loop")
        return verdict

    def _db_path(self) -> str:
        return self.config.sqlite_path or "."

    def _storage_root(self) -> str:
        """The volume that hosts the database (fail-closed: an uncreated data
        directory is measured through its nearest existing parent)."""
        import os
        target = self._db_path()
        if os.path.exists(target):
            return target
        parent = os.path.dirname(target) or "."
        return parent if os.path.exists(parent) else "."

    async def _report(self, cycle: Mapping[str, Any]) -> None:
        text = (f"cycle {cycle['cycle']}: cells={cycle['cells_due']} "
                f"complete={cycle['cells_complete']} "
                f"halted={cycle['cells_halted']} "
                f"blocked={cycle['cells_blocked']} "
                f"trades={len(cycle['trades'])} open={len(cycle['open_intents'])}")
        await self.notifier(text)

    # -- the long run --------------------------------------------------------
    async def run(self, *, cycles: Optional[int] = None,
                  interval: float = 60.0,
                  stop: Optional[Callable[[], bool]] = None,
                  sleep: Optional[Callable[[float], Awaitable[None]]] = None
                  ) -> Dict[str, Any]:
        waiter = sleep or asyncio.sleep
        rounds = 0
        while not self._stopped and not (stop is not None and stop()):
            if cycles is not None and rounds >= int(cycles):
                break
            if self._control_paused():
                # the Emergency pause reaches the loop through the control
                # plane's handler seam — the loop honours it (read-only tick).
                await waiter(interval)
                rounds += 1
                continue
            await self.run_cycle()
            rounds += 1
            if cycles is not None and rounds >= int(cycles):
                break
            if stop is not None and stop():
                break
            await waiter(interval)
        chain = await self.ledger.verify_chain()
        return {"cycles": rounds, "trades": len(self.trades),
                "open_intents": sorted(self.working),
                "refusals": len(self.refusals),
                "ledger_chain_intact": bool(chain.get("intact")),
                "signal_source": self.signal_source,
                "boot_state": self.boot_verdict.get("boot_state"),
                "contract_version": CONTRACT_VERSION}

    def _control_paused(self) -> bool:
        control = self.control
        if control is None:
            return False
        return bool(getattr(control, "paused", False)
                    or getattr(control, "new_positions_disabled", False))

    def stop(self) -> None:
        self._stopped = True


def _refusal_code(stage: Any) -> str:
    """The NAMED refusal inside one failed stage (never a bare stage name)."""
    detail = str(getattr(stage, "detail", "") or "")
    for prefix in ("CellRefusal: ", "PaperLoopError: "):
        if detail.startswith(prefix):
            detail = detail[len(prefix):]
            break
    return detail.split(":", 1)[0].strip() or str(getattr(stage, "stage", ""))


async def _maybe_await(value: Any) -> Any:
    """The watchdog's ``heartbeat()`` is synchronous by design; the loop must
    accept either form so a future async variant cannot silently stop beating."""
    import inspect
    if inspect.isawaitable(value):
        return await value
    return value


def _ms_to_iso(ms: int) -> str:
    import datetime as dt
    moment = dt.datetime.fromtimestamp(ms / 1000.0, dt.timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z"


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "to_dict"):
        return _plain(value.to_dict())
    return str(value)


__all__ = [
    "CONTRACT_VERSION", "CellRefusal", "FILL_POLL_ATTEMPTS", "PaperLoopError",
    "PaperRuntime", "PlanQueue", "SIGNAL_SOURCE_DECISION_BRIDGE",
    "SIGNAL_SOURCE_ENGINE_BRIDGE", "TRADE_PLAN_FIELDS", "WINDOW_BARS",
    "fill_from_result", "last_closed_price", "normalize_plan",
]
