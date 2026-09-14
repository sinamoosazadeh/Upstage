"""CP-7 integration — the WHOLE PAPER loop on a fixture clock against the fake
Toobit responder (a test double only; nothing here reaches a network).

Composition root, one event loop, one ledger writer (Ch.23 L18253–18260):

    FixtureClock (UTC, deterministic, monotone)
      → StartupReconciliation: STARTING → SELF_TEST → RECONCILING → READY
        (nine SBOM pins, schema version, clock drift, ladder state, then the
        broker reconciliation against the fake venue)
      → Scheduler: the 140-cell grid, semaphore 4, the nine contract stages,
        HTF last-closed only, leverage = min over ALL caps
      → the ``execution`` stage hands the CP-6 proposal + adjudication to
        build_trade_plan → ExecutionFSM.submit → ToobitAdapter (5 operations,
        signed) → the fake responder → ACK/fill
      → record_fill → place_protection (STOP + LIMIT, GTC, reduceOnly) →
        activate_management → close_position (stop-gap attribution, OUTCOME) →
        reconcile (T_MATCH / T-LR-002 / T-LR-003) → RECONCILED
      → the ledger single writer appends every event; verify_chain() recomputes
        every payload hash and the parent linkage at the end
      → EventBus → the alert bridge → SignalingPlane (token bucket, idempotency,
        retry, durable outbox, Agg-only in-memory chart) → the fake transport
      → ControlPlane: OWNER/USER roles, Busy Guard, Emergency ratchet + nonce,
        Panic Lock, update_id replay — every effect through the handler seam.

Also asserted: a drifted clock boots DEGRADED and NO cell runs; a lost ack ends
in RECOVERY_REQUIRED with a P0 alert and exactly one submission (never a
resubmit); the loop is deterministic over two independent runs; no secret
material reaches the ledger, the wire or a Telegram message.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from apex.bus import EventBus, Priority
from apex.config import Config
from apex.data_catalog.contracts import CORE10_SYMBOLS, TIMEFRAMES_14
from apex.data_catalog.store import sqlite_store as ss
from apex.errors import get_error_code
from apex.execution import fsm as F
from apex.execution.toobit_adapter import ToobitAdapter
from apex.execution.toobit_map import LEVERAGE_CAP_BY_TF
from apex.ledger import store as LS
from apex.scheduler import clock as C
from apex.telegram import control_plane as CP
from apex.telegram import signaling as SG

TEST_KEY = "TEST_KEY_CP7"
TEST_SECRET = "TEST_SECRET_CP7"
START = "2026-01-01T00:00:00.000Z"
OWNER = "-1001234567890"
USER = "-1009999999999"
WATCHDOG = "-2001234567890"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def signed_env(monkeypatch):
    monkeypatch.setenv("APEX_ENV", "PAPER")
    monkeypatch.setenv("APEX_ALLOW_SIGNED", "1")
    monkeypatch.setenv("TOOBIT_API_KEY", TEST_KEY)
    monkeypatch.setenv("TOOBIT_API_SECRET", TEST_SECRET)


@pytest.fixture()
def store(tmp_path):
    sqlite = ss.SQLiteStore(str(tmp_path / "apex.sqlite3"))
    run(sqlite.open())
    yield sqlite
    run(sqlite.close())


@dataclass
class LoopProposal:
    """CP-6's StrategyProposal shape (HANDOFF_CP6 §INTERFACES 1)."""
    proposal_id: str
    setup_id: str
    direction: str = "LONG"
    stop: float = 99.0
    targets: Tuple[float, ...] = (103.0, 106.0)
    entry_logic_ref: str = "E-01/BOS"
    snapshot_id: str = "sn-loop-0001"

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self) | {"targets": list(self.targets)}


def loop_adjudication(**overrides) -> Dict[str, Any]:
    base = {"decision": "ALLOW", "sized_quantity": 0.10, "vetoes_applied": [],
            "sizing": {"R_allowed": 10.0}, "snapshot_id": "sn-loop-0001"}
    base.update(overrides)
    return base


class FakeTelegram:
    """Transport double for the signaling plane (G9)."""

    def __init__(self) -> None:
        self.sent: List[Dict[str, Any]] = []

    async def send_message(self, chat_id: str, text: str, parse_mode: str,
                           reply_markup=None) -> Dict[str, Any]:
        return await self._record("message", chat_id, text, parse_mode,
                                  reply_markup, None)

    async def send_photo(self, chat_id: str, photo: bytes, caption,
                         parse_mode: str, reply_markup=None) -> Dict[str, Any]:
        return await self._record("photo", chat_id, caption, parse_mode,
                                  reply_markup, photo)

    async def _record(self, kind, chat_id, text, parse_mode, reply_markup,
                      photo):
        self.sent.append({"kind": kind, "chat_id": str(chat_id), "text": text,
                          "parse_mode": parse_mode, "photo": photo,
                          "reply_markup": reply_markup})
        return {"message_id": str(9000 + len(self.sent)), "chat_id": str(chat_id)}


class PaperLoop:
    """The CP-7 composition root: everything bound to ONE event loop."""

    def __init__(self, store, tmp_path: Path, *, drift: float = 0.0,
                 fill_mode: str = "immediate", lose_ack: int = 0,
                 with_adapter: bool = True) -> None:
        self.store = store
        self.tmp_path = tmp_path
        self.drift = drift
        self.fill_mode = fill_mode
        self.lose_ack = lose_ack
        self.with_adapter = with_adapter
        self.clock = C.FixtureClock(START)
        self.events: List[Any] = []
        self.alerts: List[Dict[str, Any]] = []
        self.telegram = FakeTelegram()
        self.calls: List[Dict[str, Any]] = []
        self.executed: List[Dict[str, Any]] = []
        self.refusals: List[Dict[str, Any]] = []
        self.bus: Optional[EventBus] = None
        self.ledger: Optional[LS.LedgerWriter] = None
        self.adapter: Optional[ToobitAdapter] = None
        self.responder = None
        self.signaling: Optional[SG.SignalingPlane] = None
        self.control: Optional[CP.ControlPlane] = None
        self.scheduler: Optional[C.Scheduler] = None
        self.boot_verdict: Dict[str, Any] = {}
        self.paused = False

    # -- wiring -------------------------------------------------------------
    async def start(self) -> "PaperLoop":
        from fake_toobit_responder import FakeToobitResponder

        self.ledger = LS.LedgerWriter(self.store, clock=_LedgerClock(START))
        await self.ledger.initialize()
        await self.ledger.start()

        if self.with_adapter:
            self.responder = FakeToobitResponder(
                api_key=TEST_KEY, api_secret=TEST_SECRET,
                server_time_ms=self.clock.now_ms(), balance="10000",
                clock=self.clock.monotonic)
            if self.fill_mode != "none":
                self.responder.set_fill_mode(self.fill_mode)
            if self.lose_ack:
                self.responder.lose_next_ack(self.lose_ack)
            self.adapter = ToobitAdapter(config=Config(),
                                         transport=self.responder,
                                         utc_now=self.clock.utc_now,
                                         clock=self.clock.monotonic)

        self.bus = EventBus()
        self.bus.subscribe("execution.fsm.transition", self._on_event)
        self.bus.subscribe("execution.boot", self._on_event)
        self.bus.subscribe("scheduler.cell", self._on_event)
        self.bus.subscribe("telegram.message", self._on_event)
        self._bus_task = self.bus.start()

        self.signaling = SG.SignalingPlane(transport=self.telegram,
                                           clock=self.clock.monotonic,
                                           utc_now=self.clock.utc_now,
                                           ledger=self.ledger, bus=self.bus,
                                           owner_chat_id=OWNER,
                                           watchdog_chat_id=WATCHDOG)
        self.control = CP.ControlPlane(
            signaling=self.signaling,
            access=CP.AccessControl(owner_chat_ids=[OWNER],
                                    user_chat_ids=[USER, WATCHDOG]),
            clock=self.clock.monotonic, utc_now=self.clock.utc_now,
            handlers=self._control_handlers(), bus=self.bus,
            environment="PAPER", paper_balance="10000")
        self.scheduler = C.Scheduler(clock=self.clock, bus=self.bus,
                                     handlers=self._stage_handlers(),
                                     drift_seconds=self.drift)
        return self

    async def stop(self) -> None:
        if self.bus is not None:
            await self.bus.stop()
        if self.ledger is not None and not self.ledger.closed:
            await self.ledger.stop()

    async def drain(self, times: int = 20) -> None:
        for _ in range(times):
            await asyncio.sleep(0)

    def _control_handlers(self) -> Dict[str, Any]:
        """One handler per control-plane effect, each recording its own name."""

        def build(name: str):
            async def effect(payload: Dict[str, Any]) -> Dict[str, Any]:
                self.calls.append({"effect": name, **payload})
                if name == "EMERGENCY_PAUSE":
                    self.paused = True
                if name == "EMERGENCY_SAFE_MODE":
                    self.safe_mode = True
                return {"ok": True, "effect": name, "applied": True}

            return effect

        return {name: build(name) for name in
                ("EMERGENCY_PAUSE", "EMERGENCY_DISABLE_NEW",
                 "EMERGENCY_CANCEL_ALL", "EMERGENCY_CLOSE_ALL",
                 "EMERGENCY_SAFE_MODE", "EXPORT", "BACKTEST_RUN")}

    def _grid_handlers(self) -> Dict[str, Any]:
        """All nine stages as recorders: the 140-cell grid tests measure the
        scheduler's own laws (bound, caps, HTF policy), not 140 venue round
        trips."""
        return {stage: self._passthrough_stage(stage)
                for stage in C.PIPELINE_STAGES}

    def _stage_handlers(self) -> Dict[str, Any]:
        handlers = {}
        for stage in C.PIPELINE_STAGES:
            handlers[stage] = (self._execution_stage if stage == "execution"
                               else self._passthrough_stage(stage))
        return handlers

    def _passthrough_stage(self, stage: str):
        async def handler(payload: Dict[str, Any]) -> Dict[str, Any]:
            await asyncio.sleep(0)      # a real stage yields to the loop
            return {"stage": stage, "cell_id": payload["cell_id"],
                    "detail": f"{stage} complete"}

        return handler

    async def _execution_stage(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """The ninth stage: the projection from CP-6 to the venue and back."""
        if self.paused or self.control.safe_mode:
            refusal = {"cell_id": payload["cell_id"], "refused": "SYSTEM_PAUSED"}
            self.refusals.append(refusal)
            return {"stage": "execution", "cell_id": payload["cell_id"],
                    "refused": "SYSTEM_PAUSED",
                    "detail": "SYSTEM_PAUSED — Emergency pause is active; no "
                              "new order was sent"}
        cell = C.BundleCell(payload["symbol"], payload["timeframe"])
        record = await self.trade_cell(cell, price="100")
        self.executed.append(record)
        return {"stage": "execution", "cell_id": payload["cell_id"],
                "detail": f"{record['final_state']} intent={record['intent_id']}",
                **{k: record[k] for k in ("outcome", "filled", "protected",
                                          "closed", "reconciled", "leverage")}}

    # -- boot ---------------------------------------------------------------
    async def boot(self, **kwargs) -> Dict[str, Any]:
        machine = F.StartupReconciliation(ledger=self.ledger,
                                          adapter=self.adapter,
                                          bus=self.bus,
                                          clock=self.clock.monotonic,
                                          utc_now=self.clock.utc_now,
                                          environment="PAPER",
                                          drift_seconds=self.drift, **kwargs)
        self.boot_verdict = await machine.run()
        self.boot_state = machine.state
        return self.boot_verdict

    # -- one cell, end to end ----------------------------------------------
    async def trade_cell(self, cell: C.BundleCell, *, price: str = "100",
                         intent_id: Optional[str] = None,
                         exit_price: str = "103") -> Dict[str, Any]:
        proposal = LoopProposal(proposal_id=f"pr-{cell.cell_id}",
                                setup_id=f"su-{cell.cell_id}")
        plan = F.build_trade_plan(
            proposal=proposal, adjudication=loop_adjudication(),
            symbol=cell.symbol, timeframe=cell.timeframe, environment="PAPER",
            as_of=self.clock.utc_now(), capital=10000.0,
            contract_multiplier=1.0, risk_state="LowRisk",
            package_version="4.0.0", created_utc=self.clock.utc_now(),
            lineage=f"loop:{cell.cell_id}")
        await self._seed_setup(proposal.setup_id, cell)
        # the intent_id becomes the wire clientOrderId: venue-legal characters
        # only (no colon), and short enough for the 36-character limit.
        machine = F.ExecutionFSM(
            intent_id=intent_id or f"i-{cell.symbol}-{cell.timeframe}",
                                 ledger=self.ledger, adapter=self.adapter,
                                 bus=self.bus, clock=self.clock.monotonic,
                                 utc_now=self.clock.utc_now,
                                 environment="PAPER")
        submitted = await machine.submit(plan, price=price)
        record: Dict[str, Any] = {"cell_id": cell.cell_id,
                                  "intent_id": machine.intent_id,
                                  "outcome": submitted["outcome"],
                                  "state": machine.state,
                                  "leverage": plan.leverage,
                                  "quantity": plan.sized_quantity,
                                  "filled": False, "protected": False,
                                  "closed": False, "reconciled": False}
        if machine.state in ("ACKNOWLEDGED", "PARTIAL"):
            await machine.record_fill(fill_id=f"f-{cell.cell_id}", price=price,
                                      quantity=plan.sized_quantity)
            await machine.advance("FULL_FILL")
        record["filled"] = machine.state in ("FILLED", "PROTECTED", "MANAGED")
        if record["filled"]:
            protection = await machine.place_protection(
                stop_price=plan.stop_price, target_price=plan.target_price)
            record["protected"] = bool(protection["protected"])
            if record["protected"]:
                await machine.activate_management()
                # the target leg fills: the exit is a FILL of its own, so the
                # position recomputed from the ledger returns to flat (T_MATCH).
                await machine.record_fill(fill_id=f"x-{cell.cell_id}",
                                          price=exit_price,
                                          quantity=plan.sized_quantity,
                                          side="SELL_CLOSE")
                closed = await machine.close_position(
                    exit_price=exit_price, quantity=plan.sized_quantity,
                    exit_reason="TARGET_1", setup_id=proposal.setup_id,
                    pnl=str(Decimal(exit_price) - Decimal(price)))
                record["closed"] = machine.state == "CLOSED"
                record["stop_gap"] = closed["stop_gap"]
                reconciled = await machine.reconcile()
                record["reconciled"] = machine.state == "RECONCILED"
                record["reconcile"] = {k: reconciled[k]
                                       for k in ("agree", "delta")}
        record["final_state"] = machine.state
        return record

    async def _seed_setup(self, setup_id: str, cell: C.BundleCell) -> None:
        await self.store.db.execute(
            "INSERT OR IGNORE INTO setup_candidate (setup_id, timestamp, "
            "symbol, timeframe, direction, quality, snapshot_id) VALUES "
            "(?,?,?,?,?,?,?)",
            (setup_id, self.clock.utc_now(), cell.symbol, cell.timeframe,
             "BULLISH", "Q2", "sn-loop-0001"))
        await self.store.db.commit()

    # -- bus → alert bridge (Ch.23 alert policy) ---------------------------
    async def _on_event(self, event) -> None:
        self.events.append(event)
        payload = event.payload or {}
        if event.topic != "execution.fsm.transition":
            return
        if payload.get("to") != F.RECOVERY_REQUIRED:
            return
        metric = ("protection_failed"
                  if payload.get("trigger") == "PROTECTION_FAILED"
                  else "execution_recovery_required")
        verdict = await self.signaling.emit_alert(
            alert="EXEC_RECOVERY", metric=metric, threshold="any occurrence",
            observed=str(payload.get("reason") or payload.get("trigger")),
            snapshot_id=str(payload.get("intent_id", "")),
            escalation_note="immediate OWNER")
        self.alerts.append(verdict)

    # -- views --------------------------------------------------------------
    async def ledger_rows(self, event_type: Optional[str] = None
                          ) -> List[LS.LedgerEntry]:
        rows = await self.ledger.read_ledger()
        return [r for r in rows if event_type is None
                or r.event_type == event_type]

    def event_topics(self) -> List[str]:
        return [e.topic for e in self.events]

    def order_posts(self) -> List[Any]:
        return self.responder.calls_to("/api/v1/futures/order", "POST")


class _LedgerClock:
    """Deterministic monotone ledger timestamps (1 ms apart)."""

    def __init__(self, start: str) -> None:
        moment = start.replace("Z", "+00:00")
        import datetime as dt
        self._ms = int(dt.datetime.fromisoformat(moment).timestamp() * 1000)

    def __call__(self) -> str:
        self._ms += 1
        import datetime as dt
        moment = dt.datetime.fromtimestamp(self._ms / 1000.0, dt.timezone.utc)
        return moment.strftime("%Y-%m-%dT%H:%M:%S.") + \
            f"{moment.microsecond // 1000:03d}Z"


async def loop_body(store, tmp_path, body, **kwargs):
    """Run ``body(loop)`` inside one event loop with one writer."""
    paper = PaperLoop(store, tmp_path, **kwargs)
    await paper.start()
    try:
        return await body(paper)
    finally:
        await paper.stop()


def scenario(store, tmp_path, body, **kwargs):
    return run(loop_body(store, tmp_path, body, **kwargs))


# ---------------------------------------------------------------------------
# 1. The whole loop, clean boot → READY → one cell traded → RECONCILED
# ---------------------------------------------------------------------------

class TestCleanLoop:
    def test_boot_reaches_ready_before_any_order_is_sent(self, store, tmp_path):
        async def body(p):
            verdict = await p.boot()
            return verdict, p.boot_state, len(p.order_posts())

        verdict, state, posts = scenario(store, tmp_path, body)
        assert verdict["boot_state"] == "READY"
        assert verdict["new_trades_allowed"] is True
        assert state == "READY"
        assert [c["name"] for c in verdict["checks"]][:4] == \
            ["dependencies", "schema_version", "clock_sync", "ladder_state"]
        assert all(c["status"] == "PASS" for c in verdict["checks"])
        assert posts == 0                      # reconcile-first, nothing traded

    def test_one_cell_runs_the_full_fsm_lifecycle_to_reconciled(self, store,
                                                                tmp_path):
        async def body(p):
            await p.boot()
            record = await p.trade_cell(C.BundleCell("BTCUSDT", "1h"))
            await p.drain()
            return record

        record = scenario(store, tmp_path, body, fill_mode="none")
        assert record["outcome"] == "ACKNOWLEDGED"
        assert record["filled"] is True
        assert record["protected"] is True
        assert record["closed"] is True
        assert record["reconciled"] is True
        assert record["final_state"] == "RECONCILED"
        assert record["stop_gap"] is None      # a target exit has no stop gap

    def test_the_ledger_carries_the_whole_lifecycle_and_verifies(self, store,
                                                                 tmp_path):
        async def body(p):
            await p.boot()
            await p.trade_cell(C.BundleCell("ETHUSDT", "15m"))
            rows = await p.ledger_rows()
            chain = await p.ledger.verify_chain()
            closing = [r for r in rows if r.event_type == "FSM_TRANSITION"][-1]
            return [r.event_type for r in rows], chain, closing

        types, chain, closing = scenario(store, tmp_path, body, fill_mode="none")
        assert chain["intact"] is True
        assert chain["breaks"] == []
        assert chain["records"] == len(types)
        assert types.count("FSM_TRANSITION") == 7      # the seven lifecycle edges
        assert types.count("FILL") == 2                # entry leg + exit leg
        assert types.count("TRADE_PLAN") == 1          # materialized pre-submit
        assert "OUTCOME" in types
        assert types[0] == "TRADE_PLAN"                # the plan comes first
        # the reconcile evidence lives on the closing transition (T_MATCH)
        assert closing.raw["payload"]["to_state"] == "RECONCILED"
        assert Decimal(closing.raw["payload"]["evidence"]["delta"]) == 0
        assert "T_MATCH" in closing.raw["payload"]["reason"]

    def test_a_broker_ledger_delta_blocks_new_entries_until_it_matches(self,
                                                                       store,
                                                                       tmp_path):
        """AI.9 L18831 / T-LR-002 / T-LR-003 inside the whole loop: a delta
        beyond ±1 unit is detected, logged as a CORRECTION_EVENT, blocks every
        new entry (and the next decision), and only a matching reconcile writes
        RECONCILE_RESOLVED and lifts the block."""

        async def body(p):
            await p.boot()
            await p.trade_cell(C.BundleCell("BTCUSDT", "1h"))
            diverged = await p.ledger.reconcile_against_exchange(
                [{"symbol": "BTCUSDT", "quantity": "9"}])
            blocked_write = None
            try:
                await p.ledger.append_fill(intent_id="i-blocked",
                                           fill_id="f-blocked", price="100",
                                           quantity="0.10", symbol="BTCUSDT",
                                           side="BUY_OPEN")
            except LS.LedgerError as exc:
                blocked_write = exc.reason
            blocked_decision = None
            try:
                await p.ledger.require_reconciled("i-BTCUSDT-1h")
            except LS.LedgerNotReconciled as exc:
                blocked_decision = exc.reason
            resolved = await p.ledger.reconcile_against_exchange(
                [{"symbol": "BTCUSDT", "quantity": "0"}])
            after = await p.ledger.append_fill(intent_id="i-after",
                                               fill_id="f-after", price="100",
                                               quantity="0.10",
                                               symbol="BTCUSDT",
                                               side="BUY_OPEN")
            types = [r.event_type for r in await p.ledger_rows()]
            chain = await p.ledger.verify_chain()
            return diverged, blocked_write, blocked_decision, resolved, \
                after.event_type, types, chain

        diverged, blocked_write, blocked_decision, resolved, after, types, \
            chain = scenario(store, tmp_path, body, fill_mode="none")
        assert diverged["agree"] is False
        assert diverged["delta_count"] == 1
        assert diverged["action"] == "RECOVERY_REQUIRED"
        assert diverged["new_entries_blocked"] is True
        assert blocked_write == "LEDGER_BLOCKED_PENDING_RECONCILE"
        assert blocked_decision == "T-LR-002_LEDGER_BLOCKED"
        assert resolved["agree"] is True
        assert resolved["new_entries_blocked"] is False
        assert after == "FILL"                 # writes are allowed again
        assert types.count("CORRECTION_EVENT") == 1
        assert types.count("RECONCILE_RESOLVED") == 1
        assert chain["intact"] is True         # the chain survived the block

    def test_the_wire_received_exactly_the_five_operations(self, store,
                                                           tmp_path):
        async def body(p):
            await p.boot()
            await p.trade_cell(C.BundleCell("BTCUSDT", "1h"))
            calls = [(c.method, c.path) for c in p.responder.calls]
            return calls, p.responder.signature_violations()

        calls, violations = scenario(store, tmp_path, body, fill_mode="none")
        assert violations == []                # every signed call verified
        used = {path for _, path in calls}
        # the five operations' endpoints (op 3 covers the order state AND the
        # RECONCILING fills query), plus the unsigned server-time read.
        assert used <= {"/api/v1/time", "/api/v1/futures/order",
                        "/api/v1/futures/positions", "/api/v1/futures/openOrders",
                        "/api/v1/futures/userTrades", "/api/v1/futures/balance",
                        "/api/v1/futures/marginType", "/api/v1/futures/leverage",
                        "/api/v1/futures/batchOrders"}
        # the execution surface never fetches MARKET DATA — that is the ingest
        # stage's job, and reaching for it here would be an unowned call.
        assert not used & {"/api/v1/futures/klines", "/api/v1/futures/exchangeInfo",
                           "/api/v1/futures/commissionRate"}
        posts = [c for c in calls if c == ("POST", "/api/v1/futures/order")]
        assert len(posts) == 3                 # entry + stop + target

    def test_money_is_text_decimal_at_the_store_boundary(self, store, tmp_path):
        async def body(p):
            await p.boot()
            await p.trade_cell(C.BundleCell("BTCUSDT", "1h"))
            rows = await p.store.db.execute(
                "SELECT typeof(price), typeof(quantity), typeof(fee) FROM ledger")
            return await rows.fetchall()

        kinds = scenario(store, tmp_path, body, fill_mode="none")
        assert kinds
        for price_kind, quantity_kind, fee_kind in kinds:
            assert price_kind == "text"
            assert quantity_kind == "text"
            assert fee_kind == "text"

    def test_positions_recomputed_from_the_ledger_agree_with_the_venue(self,
                                                                       store,
                                                                       tmp_path):
        async def body(p):
            await p.boot()
            await p.trade_cell(C.BundleCell("BTCUSDT", "1h"))
            ledger_positions = await p.ledger.positions_from_ledger()
            exchange = await p.adapter.query_open_positions()
            return ledger_positions, exchange

        ledger_positions, exchange = scenario(store, tmp_path, body,
                                              fill_mode="none")
        net = {s: Decimal(str(v["net_quantity"])) for s, v
               in ledger_positions.items()}
        assert net["BTCUSDT"] == Decimal("0")              # closed, flat
        assert exchange.ok is True

    def test_the_bus_carried_the_transitions_and_the_boot(self, store, tmp_path):
        async def body(p):
            await p.boot()
            await p.trade_cell(C.BundleCell("BTCUSDT", "1h"))
            await p.drain()
            return p.event_topics(), [int(e.priority) for e in p.events]

        topics, priorities = scenario(store, tmp_path, body, fill_mode="none")
        assert "execution.boot" in topics
        assert topics.count("execution.fsm.transition") == 7
        assert all(p in (0, 1, 2, 3) for p in priorities)

    def test_the_leverage_is_the_minimum_over_all_caps(self, store, tmp_path):
        async def body(p):
            await p.boot()
            records = [await p.trade_cell(C.BundleCell("BTCUSDT", tf))
                       for tf in ("1m", "1h", "1mo")]
            return [(r["cell_id"], r["leverage"]) for r in records]

        seen = scenario(store, tmp_path, body, fill_mode="none")
        assert seen == [("BTCUSDT:1m", 2.0), ("BTCUSDT:1h", 4.0),
                        ("BTCUSDT:1mo", 5.0)]
        for _, leverage in seen:
            assert leverage < 125


# ---------------------------------------------------------------------------
# 2. The scheduler drives the grid
# ---------------------------------------------------------------------------

class TestSchedulerInLoop:
    def test_a_cell_close_runs_the_nine_stages_and_trades_once(self, store,
                                                               tmp_path):
        async def body(p):
            await p.boot()
            cells = (C.BundleCell("BTCUSDT", "1h"),)
            p.scheduler = C.Scheduler(clock=p.clock, bus=p.bus, cells=cells,
                                      handlers=p._stage_handlers())
            runs = await p.scheduler.run_due()
            await p.drain()
            return runs, p.executed

        runs, executed = scenario(store, tmp_path, body, fill_mode="none")
        assert len(runs) == 1
        assert runs[0].status == "COMPLETE"
        assert [s.stage for s in runs[0].stages] == list(C.PIPELINE_STAGES)
        assert len(executed) == 1
        assert executed[0]["final_state"] == "RECONCILED"
        assert runs[0].leverage == LEVERAGE_CAP_BY_TF["1h"]

    def test_a_full_burst_stays_inside_the_four_cell_bound(self, store,
                                                           tmp_path):
        async def body(p):
            await p.boot()
            p.scheduler = C.Scheduler(clock=p.clock, bus=p.bus,
                                      handlers=p._grid_handlers())
            runs = await p.scheduler.run_burst(C.universe_cells())
            return p.scheduler.concurrent_peak, len(runs), \
                sorted({r.status for r in runs}), p.scheduler.semaphore_value

        peak, count, statuses, bound = scenario(store, tmp_path, body,
                                                fill_mode="none")
        assert bound == 4
        assert count == 140
        assert 1 < peak <= 4
        assert statuses == ["COMPLETE"]

    def test_every_cell_trades_at_or_below_its_timeframe_cap(self, store,
                                                             tmp_path):
        async def body(p):
            await p.boot()
            p.scheduler = C.Scheduler(clock=p.clock, bus=p.bus,
                                      handlers=p._grid_handlers())
            runs = await p.scheduler.run_burst(C.universe_cells())
            return [(r.cell_id, r.leverage) for r in runs]

        rows = scenario(store, tmp_path, body, fill_mode="none")
        assert len(rows) == 140
        for cell_id, leverage in rows:
            tf = cell_id.split(":")[1]
            assert leverage <= LEVERAGE_CAP_BY_TF[tf], cell_id

    def test_the_htf_policy_is_last_closed_only_in_every_payload(self, store,
                                                                 tmp_path):
        async def body(p):
            seen = []

            async def handler(payload):
                seen.append(payload["htf_policy"])
                return {"detail": "ok"}

            p.scheduler = C.Scheduler(clock=p.clock, bus=p.bus,
                                      handlers={s: handler
                                                for s in C.PIPELINE_STAGES})
            await p.scheduler.run_burst(C.universe_cells())
            return seen

        policies = scenario(store, tmp_path, body)
        assert len(policies) == 140 * 9
        assert set(policies) == {"LAST_CLOSED_ONLY"}

    def test_an_emergency_pause_stops_the_execution_stage_only(self, store,
                                                               tmp_path):
        async def body(p):
            await p.boot()
            p.paused = True
            cells = (C.BundleCell("BTCUSDT", "1h"),)
            p.scheduler = C.Scheduler(clock=p.clock, bus=p.bus, cells=cells,
                                      handlers=p._stage_handlers())
            runs = await p.scheduler.run_due()
            return runs[0].status, runs[0].stages[-1].detail, p.executed, \
                len(p.order_posts()), p.refusals

        status, result, executed, posts, p_refusals = scenario(
            store, tmp_path, body, fill_mode="none")
        assert status == "COMPLETE"            # the pipeline ran, the order did not
        assert result.startswith("SYSTEM_PAUSED")
        assert executed == []
        assert posts == 0
        assert p_refusals == [{"cell_id": "BTCUSDT:1h",
                               "refused": "SYSTEM_PAUSED"}]


# ---------------------------------------------------------------------------
# 3. Drift: DEGRADED boot, no cell runs, nothing reaches the venue
# ---------------------------------------------------------------------------

class TestDriftBlocksTheLoop:
    def test_drift_beyond_tolerance_degrades_the_boot(self, store, tmp_path):
        async def body(p):
            verdict = await p.boot()
            return verdict["boot_state"], verdict["new_trades_allowed"], \
                verdict["drift_blocks_new_trades"], verdict["drift_seconds"]

        state, allowed, blocked, drift = scenario(store, tmp_path, body,
                                                  drift=6.0)
        assert state == "DEGRADED"
        assert allowed is False
        assert blocked is True
        assert drift == 6.0

    def test_e12_drift_over_500ms_also_blocks_new_trades(self, store, tmp_path):
        async def body(p):
            verdict = await p.boot()
            return verdict["boot_state"], verdict["new_trades_allowed"]

        assert scenario(store, tmp_path, body, drift=0.6) == ("DEGRADED", False)

    def test_no_cell_runs_and_the_venue_is_never_called(self, store, tmp_path):
        async def body(p):
            await p.boot()
            runs = await p.scheduler.run_due(limit=10)
            return [r.status for r in runs], [r.reason for r in runs], \
                len(p.responder.calls), p.executed

        statuses, reasons, calls, executed = scenario(store, tmp_path, body,
                                                      drift=6.0)
        assert statuses == ["BLOCKED"] * 10
        assert set(reasons) == {"CLOCK_DRIFT_BEYOND_TOLERANCE"}
        assert calls == 0
        assert executed == []


# ---------------------------------------------------------------------------
# 4. Lost ack → RECOVERY_REQUIRED, one submission, P0 alert
# ---------------------------------------------------------------------------

class TestRecoveryInLoop:
    def test_a_lost_ack_never_resubmits_and_raises_a_p0_alert(self, store,
                                                              tmp_path):
        async def body(p):
            await p.boot()
            p.responder.lose_next_ack(1)     # armed AFTER the boot queries
            record = await p.trade_cell(C.BundleCell("BTCUSDT", "1h"))
            await p.drain()
            return record, len(p.order_posts()), p.alerts, \
                [int(e.priority) for e in p.events
                 if e.topic == "execution.fsm.transition"][-1], \
                [m["text"] for m in p.telegram.sent]

        record, posts, alerts, priority, texts = scenario(
            store, tmp_path, body, fill_mode="none")
        assert record["outcome"] == "UNKNOWN"
        assert record["final_state"] == F.RECOVERY_REQUIRED
        assert record["filled"] is False
        assert posts == 1                      # exactly ONE submission
        assert len(alerts) == 1
        assert alerts[0]["alert"] == "EXEC_RECOVERY"
        assert alerts[0]["emitted"] is True
        assert alerts[0]["priority"] == int(Priority.P0)
        assert priority == int(Priority.P0)
        assert "EXEC_RECOVERY" in texts[0].replace("\\", "")   # MarkdownV2

    def test_recovery_reconciliation_runs_the_seven_ai9_checks(self, store,
                                                               tmp_path):
        async def body(p):
            await p.boot()
            p.responder.lose_next_ack(1)
            await p.trade_cell(C.BundleCell("BTCUSDT", "1h"))
            machine = F.StartupReconciliation(
                ledger=p.ledger, adapter=p.adapter, bus=p.bus,
                clock=p.clock.monotonic, utc_now=p.clock.utc_now,
                environment="PAPER",
                feature_replay_provider=lambda: {"consistent": True},
                pattern_provider=lambda: {"consistent": True})
            return await machine.run_recovery_reconciliation()

        verdict = scenario(store, tmp_path, body, fill_mode="none")
        assert [c["name"] for c in verdict["checks"]] == [
            "ledger_integrity", "raw_hash_chain", "broker_reconciliation",
            "feature_replay", "pattern_reevaluation", "risk_recheck",
            "fsm_state"]
        # with the research providers wired and the venue flat on both sides,
        # recovery RESUMEs; without them it HALTs (asserted by the unit battery).
        assert verdict["action"] == "RESUME"
        assert verdict["passed"] is True

    def test_a_protection_failure_closes_at_market_and_escalates(self, store,
                                                                 tmp_path):
        async def body(p):
            await p.boot()
            plan = F.build_trade_plan(
                proposal=LoopProposal("pr-p", "su-p"),
                adjudication=loop_adjudication(), symbol="BTCUSDT",
                timeframe="1h", environment="PAPER", as_of=p.clock.utc_now(),
                capital=10000.0, contract_multiplier=1.0,
                created_utc=p.clock.utc_now())
            await p._seed_setup("su-p", C.BundleCell("BTCUSDT", "1h"))
            machine = F.ExecutionFSM(intent_id="i-prot", ledger=p.ledger,
                                     adapter=p.adapter, bus=p.bus,
                                     clock=p.clock.monotonic,
                                     utc_now=p.clock.utc_now,
                                     environment="PAPER")
            await machine.submit(plan, price="100", quantity="0.10")
            await machine.record_fill(fill_id="f-p", price="100",
                                      quantity="0.10")
            await machine.advance("FULL_FILL")
            p.responder.fail_next(-1022, 1)     # the protective stop is refused
            result = await machine.place_protection(stop_price="99",
                                                    target_price="103")
            await p.drain()
            return result, machine.state, p.alerts, \
                len(await p.ledger_rows("PROTECTION_FAILED"))

        result, state, alerts, rows = scenario(store, tmp_path, body,
                                               fill_mode="none")
        assert result["protected"] is False
        assert result["emergency_path"] == "PLAYBOOK_EMERGENCY_CLOSE_AT_MARKET"
        assert result["escalation"] == "OWNER"
        assert state == F.RECOVERY_REQUIRED
        assert rows == 1
        assert [a["alert"] for a in alerts] == ["EXEC_RECOVERY"]


# ---------------------------------------------------------------------------
# 5. The control plane guards the loop
# ---------------------------------------------------------------------------

class TestControlPlaneInLoop:
    def test_a_user_cannot_reach_research_or_emergency(self, store, tmp_path):
        async def body(p):
            research = await p.control.handle_callback(USER, "RESEARCH")
            emergency = await p.control.handle_callback(USER, "EMERGENCY:L5")
            return research, emergency

        research, emergency = scenario(store, tmp_path, body)
        assert research["screen"] == "ACCESS_DENIED"
        assert research["reason"] == "RESEARCH_ONLY + BLOCK"
        assert emergency["reason"] == "OWNER_ONLY"
        assert emergency["ok"] is False

    def test_an_owner_emergency_pause_stops_the_next_cell(self, store, tmp_path):
        async def body(p):
            await p.boot()
            pending = await p.control.handle_callback(OWNER, "EMERGENCY:L1")
            nonce = pending["nonce"]
            confirmed = await p.control.handle_callback(
                OWNER, f"CONFIRM:{nonce}:YES:EMERGENCY_L1")
            cells = (C.BundleCell("BTCUSDT", "1h"),)
            p.scheduler = C.Scheduler(clock=p.clock, bus=p.bus, cells=cells,
                                      handlers=p._stage_handlers())
            runs = await p.scheduler.run_due()
            return confirmed["ok"], p.paused, runs[0].stages[-1].detail, \
                len(p.order_posts()), [c["effect"] for c in p.calls]

        ok, paused, result, posts, calls = scenario(store, tmp_path, body,
                                                    fill_mode="none")
        assert ok is True
        assert paused is True
        assert result.startswith("SYSTEM_PAUSED")
        assert posts == 0
        assert calls == ["EMERGENCY_PAUSE"]

    def test_the_busy_guard_refuses_a_second_concurrent_run(self, store,
                                                            tmp_path):
        async def body(p):
            first = await p.control.handle_callback(OWNER, "BACKTEST_RUN:BT-1")
            p.control.busy.try_acquire("BT-2")
            second = await p.control.handle_callback(OWNER, "BACKTEST_RUN:BT-3")
            return first["ok"], second["ok"], second["error_code"], \
                second["stop_button"]

        first_ok, second_ok, code, stop = scenario(store, tmp_path, body)
        assert first_ok is True
        assert second_ok is False
        assert code == get_error_code("E-VAL-020").code
        assert stop is True

    def test_the_panic_lock_broadcasts_and_blocks_callbacks(self, store,
                                                            tmp_path):
        async def body(p):
            locked = await p.control.handle_command(OWNER, "/lock")
            blocked = await p.control.handle_callback(OWNER, "SCREEN:TRADING")
            myid = await p.control.handle_command(OWNER, "/myid")
            unlock = await p.control.handle_command(USER, "/unlock")
            released = await p.control.handle_command(OWNER, "/unlock")
            return locked, blocked, myid["ok"], unlock["ok"], released["ok"], \
                [m["text"] for m in p.telegram.sent]

        locked, blocked, myid_ok, user_unlock, owner_unlock, texts = scenario(
            store, tmp_path, body)
        assert locked["locked"] is True
        assert blocked["ok"] is False
        assert blocked["reason"] == "PANIC_LOCK_ENGAGED"
        assert myid_ok is True
        assert user_unlock is False
        assert owner_unlock is True
        assert len(texts) == 4                 # lock EN+FA, unlock EN+FA
        assert any("PANIC LOCK ENGAGED" in t for t in texts)
        assert any("قفل اضطراری" in t for t in texts)

    def test_a_replayed_update_never_trades_twice(self, store, tmp_path):
        async def body(p):
            first = await p.control.handle_callback(
                OWNER, "BACKTEST_RUN:BT-7", update_id=4242)
            second = await p.control.handle_callback(
                OWNER, "BACKTEST_RUN:BT-7", update_id=4242)
            return first["ok"], second["replayed"], \
                len([c for c in p.calls if c["effect"] == "BACKTEST_RUN"])

        assert scenario(store, tmp_path, body) == (True, True, 1)


# ---------------------------------------------------------------------------
# 6. Signaling inside the loop
# ---------------------------------------------------------------------------

class TestSignalingInLoop:
    def test_a_confirmed_setup_signal_carries_an_in_memory_chart(self, store,
                                                                 tmp_path):
        async def body(p):
            await p.boot()
            record = await p.trade_cell(C.BundleCell("BTCUSDT", "1h"))
            chart = SG.render_chart(
                ohlcv=[[i, 100, 101, 99, 100.5, 10] for i in range(30)],
                layers=["BOS", "FVG", "OrderBlock"], quality="Q2",
                snapshot_id="sn-loop-0001", lineage=f"loop:{record['cell_id']}")
            result = await p.signaling.send(SG.SignalMessage(
                signal_id=f"setup-{record['intent_id']}", chat_id=OWNER,
                text="Setup CONFIRMED — BTCUSDT 1h LONG entry 100, stop 99, "
                     "target 103 (Q2, 5–20 candles)",
                timestamp_utc=p.clock.utc_now(), snapshot_id="sn-loop-0001",
                image=chart["image"], caption="BTCUSDT 1h — BOS + FVG"))
            return result, chart, p.telegram.sent[-1], record

        result, chart, sent, record = scenario(store, tmp_path, body,
                                               fill_mode="none")
        assert record["final_state"] == "RECONCILED"
        assert result.sent is True
        assert result.quality == "Q2"
        assert result.state == "ACTIVE"
        assert chart["width"] == 1200 and chart["height"] == 800
        assert chart["backend"] == "Agg"
        assert chart["filesystem_stored"] is False
        assert sent["kind"] == "photo"
        assert sent["photo"][:8] == b"\x89PNG\r\n\x1a\n"
        assert sent["parse_mode"] == "MarkdownV2"

    def test_no_chart_file_is_ever_written_to_disk(self, store, tmp_path):
        async def body(p):
            await p.boot()
            await p.trade_cell(C.BundleCell("BTCUSDT", "1h"))
            SG.render_chart(ohlcv=[[0, 1, 2, 1.5, 1.6, 3]], layers=["BOS"])
            return sorted(f.suffix for f in tmp_path.rglob("*") if f.is_file())

        suffixes = scenario(store, tmp_path, body, fill_mode="none")
        assert set(suffixes) <= {".sqlite3", ".sqlite3-shm", ".sqlite3-wal"}
        assert not any(s in (".png", ".jpg", ".jpeg", ".pdf") for s in suffixes)

    def test_the_same_signal_is_never_sent_twice(self, store, tmp_path):
        async def body(p):
            message = SG.SignalMessage(signal_id="sig-loop", chat_id=OWNER,
                                       text="Setup CONFIRMED",
                                       timestamp_utc=p.clock.utc_now())
            first = await p.signaling.send(message)
            second = await p.signaling.send(message)
            return first.sent, second.sent, second.error_code, \
                len(p.telegram.sent)

        assert scenario(store, tmp_path, body) == (
            True, False, get_error_code("E-TELE-007").code, 1)

    def test_the_alert_audit_trail_lands_in_the_ledger(self, store, tmp_path):
        async def body(p):
            await p.boot()
            await p.signaling.emit_alert(alert="STORAGE",
                                         metric="device_storage",
                                         threshold="> 80% capacity",
                                         observed=0.91, snapshot_id="sn-1")
            rows = await p.ledger_rows("ALERT")
            return rows, p.signaling.alert_audit

        rows, audit = scenario(store, tmp_path, body)
        assert len(rows) == 1
        assert rows[0].raw["payload"]["alert"]["alert"] == "STORAGE"
        assert len(audit) == 1


# ---------------------------------------------------------------------------
# 7. Determinism + no secrets
# ---------------------------------------------------------------------------

class TestLoopDeterminism:
    def test_two_independent_runs_project_identically(self, store, tmp_path,
                                                      tmp_path_factory):
        other = tmp_path_factory.mktemp("loop-b")
        other_store = ss.SQLiteStore(str(other / "apex.sqlite3"))
        run(other_store.open())

        async def body(p):
            await p.boot()
            record = await p.trade_cell(C.BundleCell("BTCUSDT", "1h"))
            rows = await p.ledger_rows()
            return {
                "record": {k: v for k, v in record.items()
                           if k not in ("intent_id",)},
                "types": [r.event_type for r in rows],
                "boot": [c["name"] + c["status"] for c in p.boot_verdict["checks"]],
                "wire": [(c.method, c.path,
                          {k: v for k, v in c.params.items()
                           if k not in ("timestamp", "recvWindow")})
                         for c in p.responder.calls],
            }

        try:
            first = scenario(store, tmp_path, body, fill_mode="none")
            second = scenario(other_store, other, body, fill_mode="none")
        finally:
            run(other_store.close())
        assert first["types"] == second["types"]
        assert first["boot"] == second["boot"]
        assert first["record"] == second["record"]
        for left, right in zip(first["wire"], second["wire"]):
            assert left[0] == right[0]
            assert left[1] == right[1]
            assert {k: v for k, v in left[2].items() if k != "signature"} == \
                {k: v for k, v in right[2].items() if k != "signature"}

    def test_no_secret_material_reaches_the_ledger_or_a_message(self, store,
                                                                tmp_path):
        async def body(p):
            await p.boot()
            await p.trade_cell(C.BundleCell("BTCUSDT", "1h"))
            await p.signaling.send(SG.SignalMessage(
                signal_id="sig-secret-scan", chat_id=OWNER,
                text="Setup CONFIRMED — balance 10,000 USDT",
                timestamp_utc=p.clock.utc_now()))
            rows = await p.ledger_rows()
            return [json.dumps(r.raw, default=str) for r in rows], \
                [json.dumps(m, default=str) for m in p.telegram.sent], \
                [json.dumps({"params": c.params, "headers": c.headers},
                            default=str) for c in p.responder.calls]

        ledger_text, telegram_text, wire_text = scenario(store, tmp_path, body,
                                                         fill_mode="none")
        for blob in ledger_text + telegram_text:
            assert TEST_SECRET not in blob
            assert TEST_KEY not in blob
        # the API key IS carried by the signed request (as the venue requires);
        # the secret never is — it only ever signs.
        assert all(TEST_SECRET not in blob for blob in wire_text)
        assert any(TEST_KEY in blob for blob in wire_text)

    def test_the_environment_is_paper_everywhere(self, store, tmp_path):
        async def body(p):
            await p.boot()
            await p.trade_cell(C.BundleCell("BTCUSDT", "1h"))
            plans = await p.ledger_rows("TRADE_PLAN")
            return [r.raw["payload"]["trade_plan"]["environment"]
                    for r in plans], p.control.environment, \
                p.boot_verdict["environment"]

        environments, control_env, boot_env = scenario(store, tmp_path, body,
                                                       fill_mode="none")
        assert environments == ["PAPER"]
        assert control_env == "PAPER"
        assert boot_env == "PAPER"

    def test_the_loop_never_leaves_the_agg_backend(self, store, tmp_path):
        import matplotlib

        async def body(p):
            await p.boot()
            SG.render_chart(ohlcv=[[0, 1, 2, 1.5, 1.6, 3]], layers=["BOS"])
            return matplotlib.get_backend()

        assert scenario(store, tmp_path, body, fill_mode="none").lower() == "agg"
