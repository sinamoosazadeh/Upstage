"""APEX_GEN5 ledger — Ch.16 L16757–16760 ("Ledger is immutable and
hash-chained … silent rewriting is forbidden — corrections append a
revision"), §16.2 L16918–16930 (matching is a first-class invariant: a SINGLE
SOURCE OF TRUTH for position state — the ledger, reconciled against the
exchange; fills are idempotent under ``fill_id``), Ch.23 L18253–18260
(single writer; every execution-FSM state mutation passes through that one
writer queue), AI.7 L18715 ("Exactly one process writes to the ledger; all
other processes read-only"), AI.8 L18754 (ledger-write idempotency key =
``event_id``, permanent) and AI.12 Phase-6 (event log: event_id, timestamp,
actor, decision, result, P/L).

Acceptance ids implemented here: ``T_LEDGER`` (a covert insert/modify of a
ledger record breaks the hash chain), ``T-LR-001`` (append-only, event_id
unique, 1000 writes monotonic), ``T-LR-002`` (the FSM requires RECONCILED
before the next decision), ``T-LR-003`` (broker-vs-ledger deltas detected and
logged as CORRECTION_EVENT), ``T_MATCH`` (position recomputed from the ledger
== exchange-reported position).

Single-writer enforcement is structural, not conventional:
1. one :class:`LedgerWriter` per physical database — a second construction
   raises ``LedgerSingleWriterError``;
2. every write is queued and applied by EXACTLY ONE writer task, so no two
   writers ever touch one position record (Ch.23 L18258–18260);
3. ``tests/unit/test_ledger_store.py::TestSingleWriterGrep`` greps the whole
   repository: the only ``INSERT INTO ledger`` / ``UPDATE ledger`` /
   ``DELETE FROM ledger`` statements in the tree live in this file.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import (Any, Awaitable, Callable, Dict, List, Mapping, Optional,
                    Sequence, Tuple)

from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import sha256_hex
from apex.identity.uuid_v7 import uuid_v7

CONTRACT_VERSION = "4.0.0"

# ---------------------------------------------------------------------------
# Ch.16 L16814–16840 — second-layer schema `trade_plan` (SL-5 output / SL-6
# input; the Data Plane extension — no frozen column is removed). VERBATIM.
# ---------------------------------------------------------------------------

TRADE_PLAN_DDL = """
CREATE TABLE IF NOT EXISTS trade_plan (   -- SL-5 output, SL-6 input
  proposal_id TEXT PRIMARY KEY,           -- UUIDv7 (decision turn)
  setup_id TEXT NOT NULL,                 -- SetupEvent id
  symbol TEXT, timeframe TEXT,
  direction TEXT CHECK(direction IN ('LONG','SHORT','FLAT')),
  entry_ref TEXT,                         -- entry_logic_ref of the Portfolio Proposal
  stop_price REAL,                        -- stop distance is the root of risk
  target_price REAL,                      -- first target (base RR)
  sized_quantity REAL NOT NULL,           -- Q from the sizing machine (SL-5)
  risk_amount REAL,                       -- current R_allowed
  contract_multiplier REAL,               -- from the symbol catalog
  decision TEXT CHECK(decision IN ('ALLOW','REDUCE','REJECT')),
  vetoes_applied TEXT,                    -- JSON array of activated vetoes
  risk_state TEXT,                        -- NoRisk/LowRisk/MediumRisk/HighRisk/CriticalRisk
  package_version TEXT,                   -- ParameterPackage.version
  snapshot_id TEXT, as_of TEXT, created_utc TEXT, lineage TEXT,
  payload_hash TEXT,                      -- hash(proposal) for the ledger chain
  environment TEXT CHECK(environment IN ('PAPER','LIVE','RESEARCH','BACKTEST'))
);
"""

#: AI.8 L18806–18810: "Audit is immutable; stored in separate ledger table
#: with read-only access."
AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS ledger_audit (
    audit_id TEXT PRIMARY KEY,
    ledger_id TEXT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT,
    timestamp TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS ledger_audit_no_update
BEFORE UPDATE ON ledger_audit
BEGIN SELECT RAISE(ABORT, 'AUDIT_APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS ledger_audit_no_delete
BEFORE DELETE ON ledger_audit
BEGIN SELECT RAISE(ABORT, 'AUDIT_APPEND_ONLY'); END;
"""

TRADE_PLAN_MIGRATION = "M101_cp7_trade_plan"
LEDGER_AUDIT_MIGRATION = "M102_cp7_ledger_audit"

#: Frozen `ledger` columns (Ch.4 Data Plane DDL — CP-1 owns the table; this
#: module only appends rows through the single writer).
LEDGER_COLUMNS: Tuple[str, ...] = (
    "ledger_id", "intent_id", "order_id", "fill_id", "cancel_id",
    "payload_hash", "parent_ids", "until", "raw", "fee", "slippage", "price",
    "quantity", "timestamp")

TRADE_PLAN_COLUMNS: Tuple[str, ...] = (
    "proposal_id", "setup_id", "symbol", "timeframe", "direction", "entry_ref",
    "stop_price", "target_price", "sized_quantity", "risk_amount",
    "contract_multiplier", "decision", "vetoes_applied", "risk_state",
    "package_version", "snapshot_id", "as_of", "created_utc", "lineage",
    "payload_hash", "environment")

ENVIRONMENTS: Tuple[str, ...] = ("PAPER", "LIVE", "RESEARCH", "BACKTEST")
DIRECTIONS: Tuple[str, ...] = ("LONG", "SHORT", "FLAT")
DECISIONS: Tuple[str, ...] = ("ALLOW", "REDUCE", "REJECT")

#: Reconciliation delta tolerance (AI.9 L18831: "broker position != ledger
#: position, delta > ±1 unit" ⇒ block new entries, audit the delta, emit
#: RECONCILE_FAILURE).
RECONCILE_DELTA_TOLERANCE_UNITS = 1.0


class LedgerError(RuntimeError):
    """Fail-closed ledger violation with a deterministic reason code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}" + (f": {detail}" if detail else ""))


class LedgerSingleWriterError(LedgerError):
    """AI.7 L18715: exactly one writer per ledger."""


class LedgerNotReconciled(LedgerError):
    """T-LR-002: the FSM requires RECONCILED before the next decision."""


@dataclass(frozen=True)
class LedgerEntry:
    """One appended ledger record (immutable after write)."""
    ledger_id: str
    event_id: str
    event_type: str
    actor: str
    intent_id: Optional[str]
    order_id: Optional[str]
    fill_id: Optional[str]
    cancel_id: Optional[str]
    payload_hash: str
    parent_ids: Tuple[str, ...]
    until: Optional[str]
    timestamp: str
    price: Optional[str]
    quantity: Optional[str]
    fee: Optional[str]
    slippage: Optional[str]
    raw: Mapping[str, Any]

    @property
    def decision(self) -> Optional[str]:
        return self.raw.get("decision")

    @property
    def result(self) -> Optional[str]:
        return self.raw.get("result")

    @property
    def pnl(self) -> Optional[str]:
        return self.raw.get("pnl")

    def to_row(self) -> Tuple[Any, ...]:
        """Project onto the frozen Ch.5 ledger DDL (L14507–14522).

        That DDL carries ``CHECK(typeof(fee)='text')`` /
        ``CHECK(typeof(price)='text')`` / ``CHECK(typeof(quantity)='text')``, so
        SQL NULL is REJECTED for those columns: an absent money value is stored
        as the empty TEXT ``''`` and mapped back to ``None`` on read
        (ISSUE-CP7-008). Money that IS present stays a Decimal TEXT string.
        """
        return (self.ledger_id, self.intent_id, self.order_id, self.fill_id,
                self.cancel_id, self.payload_hash,
                json.dumps(list(self.parent_ids), separators=(",", ":"),
                           sort_keys=True),
                self.until,
                canonical_json(dict(self.raw)),
                _money_text(self.fee), _money_text(self.slippage),
                _money_text(self.price), _money_text(self.quantity),
                self.timestamp)


def utc_now_ms() -> str:
    now = _dt.datetime.now(_dt.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


#: While a reconciliation failure blocks the ledger, only the audit of that
#: failure and its resolution may be appended (AI.9 L18831: block new entries,
#: audit the delta — never silently repair).
_ALLOWED_WHILE_BLOCKED: Tuple[str, ...] = ("CORRECTION_EVENT",
                                           "RECONCILE_RESOLVED")

#: One active writer per physical database (AI.7 single-writer law).
_ACTIVE_WRITERS: Dict[str, "LedgerWriter"] = {}


def active_writer(db_path: str) -> Optional["LedgerWriter"]:
    return _ACTIVE_WRITERS.get(_resolve(db_path))


def _resolve(db_path: str) -> str:
    from pathlib import Path
    return str(Path(db_path).resolve())


class LedgerWriter:
    """The single ledger writer (Ch.23 L18253–18260).

    ``store`` is an OPEN :class:`apex.data_catalog.store.sqlite_store.SQLiteStore`
    (CP-1's frozen store is consumed, never patched). All writes are queued and
    applied by one writer task; reads are lock-free (WAL, AI.7 L18717).
    """

    def __init__(self, store: Any, *, actor: str = "LEDGER",
                 clock: Optional[Callable[[], str]] = None,
                 maxsize: int = 1000) -> None:
        self._store = store
        self._db = store.db
        self.path = _resolve(getattr(store, "path", ":memory:"))
        existing = _ACTIVE_WRITERS.get(self.path)
        if existing is not None and existing is not self and not existing.closed:
            raise LedgerSingleWriterError(
                "LEDGER_SINGLE_WRITER_VIOLATION",
                f"a LedgerWriter is already active for {self.path} (AI.7 "
                "L18715: exactly one process writes to the ledger)")
        _ACTIVE_WRITERS[self.path] = self
        self._actor = actor
        self._clock = clock if clock is not None else utc_now_ms
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._task: Optional[asyncio.Task] = None
        self._closed = False
        self._written = 0
        self._head: Optional[str] = None       # last payload_hash (chain head)
        self._migrations_applied: List[str] = []
        self._blocked: Optional[str] = None    # divergence ⇒ new entries blocked

    # -- lifecycle ----------------------------------------------------------
    @property
    def db(self) -> Any:
        """The CP-1 store connection (read-only use by other CP-7 modules: the
        boot self-test reads ``schema_migrations`` and the ladder table). No
        other module may write through it — the writer queue is the only write
        path (AI.7 L18715)."""
        return self._db

    @property
    def closed(self) -> bool:
        return self._closed

    async def initialize(self) -> Dict[str, Any]:
        """Apply the CP-7 migrations (trade_plan, ledger_audit) through CP-1's
        ``schema_migrations`` bookkeeping, invoke the CP-6 ladder-state hook
        (ADR-P2-004 / HANDOFF_CP6 §INTERFACES 4) and recover the chain head."""
        from apex.risk.kernel import apply_ladder_state_migration
        await self._db.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                               "(migration_name TEXT PRIMARY KEY, applied_at "
                               "TEXT NOT NULL)")
        for name, script in ((TRADE_PLAN_MIGRATION, TRADE_PLAN_DDL),
                             (LEDGER_AUDIT_MIGRATION, AUDIT_DDL)):
            cur = await self._db.execute(
                "SELECT 1 FROM schema_migrations WHERE migration_name=?", (name,))
            if await cur.fetchone():
                continue
            await self._db.executescript(script)
            await self._db.execute(
                "INSERT INTO schema_migrations (migration_name, applied_at) "
                "VALUES (?,?)", (name, self._clock()))
            await self._db.commit()
            self._migrations_applied.append(name)
        ladder = await apply_ladder_state_migration(self._db)
        self._head = await self._recover_head()
        return {"migrations": tuple(self.applied_migrations()),
                "ladder_state": ladder, "chain_head": self._head}

    def applied_migrations(self) -> Tuple[str, ...]:
        from apex.risk.kernel import LADDER_STATE_MIGRATION
        return (TRADE_PLAN_MIGRATION, LEDGER_AUDIT_MIGRATION,
                LADDER_STATE_MIGRATION)

    async def start(self) -> "LedgerWriter":
        """Start the ONE writer task (Ch.23: single ledger writer queue)."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._writer_loop(),
                                             name="apex-ledger-writer")
        return self

    async def stop(self) -> None:
        """Drain, then stop the writer task and release the single-writer slot."""
        if self._task is not None:
            await self._queue.join()
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._closed = True
        if _ACTIVE_WRITERS.get(self.path) is self:
            _ACTIVE_WRITERS.pop(self.path, None)

    async def __aenter__(self) -> "LedgerWriter":
        await self.initialize()
        return await self.start()

    async def __aexit__(self, *exc: Any) -> None:
        await self.stop()

    async def _writer_loop(self) -> None:
        while True:
            item = await self._queue.get()
            try:
                entry, future = item
                try:
                    written = await self._apply(entry)
                    if not future.done():
                        future.set_result(written)
                except Exception as exc:            # fail-closed, never silent
                    if not future.done():
                        future.set_exception(exc)
            finally:
                self._queue.task_done()

    async def _apply(self, entry: LedgerEntry) -> LedgerEntry:
        """Link + hash + write ONE record, in writer order.

        The parent link and the payload hash are computed HERE, not by the
        producer: with 1000 concurrent appends (T-LR-001) a producer-side head
        would be stale and the chain would fork. One writer ⇒ one linear chain.
        """
        parents = list(entry.parent_ids)
        if self._head is not None:
            parents.append(self._head)
        chain_payload = {**dict(entry.raw), "parent_ids": parents}
        payload_hash = sha256_hex(canonical_json(chain_payload))
        entry = replace(entry, parent_ids=tuple(parents),
                        payload_hash=payload_hash, raw=chain_payload)
        await self._db.execute(
            "INSERT INTO ledger (" + ",".join(LEDGER_COLUMNS) + ") VALUES ("
            + ",".join("?" * len(LEDGER_COLUMNS)) + ")", entry.to_row())
        await self._db.execute(
            "INSERT INTO ledger_audit (audit_id, ledger_id, actor, action, "
            "detail, timestamp) VALUES (?,?,?,?,?,?)",
            (f"aud-{uuid_v7()}", entry.ledger_id, entry.actor,
             entry.event_type, canonical_json({"intent_id": entry.intent_id,
                                              "order_id": entry.order_id,
                                              "fill_id": entry.fill_id,
                                              "result": entry.result,
                                              "pnl": entry.pnl}),
             entry.timestamp))
        await self._db.commit()          # synchronous: no buffering (AI.7 L18712)
        self._written += 1
        self._head = payload_hash
        return entry

    # -- write API ----------------------------------------------------------
    async def append(self, *, event_type: str, actor: Optional[str] = None,
                     intent_id: Optional[str] = None,
                     order_id: Optional[str] = None,
                     fill_id: Optional[str] = None,
                     cancel_id: Optional[str] = None,
                     price: Optional[Any] = None,
                     quantity: Optional[Any] = None,
                     fee: Optional[Any] = None,
                     slippage: Optional[Any] = None,
                     until: Optional[str] = None,
                     parents: Optional[Sequence[str]] = None,
                     timestamp: Optional[str] = None,
                     **payload: Any) -> LedgerEntry:
        """Queue one append and await the single writer's confirmation.

        Money/price values are stored as TEXT Decimal strings (P8/G11: the
        store boundary is TEXT-Decimal, never float).
        """
        if self._closed:
            raise LedgerError("LEDGER_WRITER_CLOSED",
                              "the writer is stopped — fail-closed, no write")
        if not event_type:
            raise LedgerError("EVENT_TYPE_REQUIRED")
        if self._blocked is not None and event_type not in _ALLOWED_WHILE_BLOCKED:
            raise LedgerError(
                "LEDGER_BLOCKED_PENDING_RECONCILE",
                f"reconciliation failed ({self._blocked}) — new entries are "
                "blocked until a reconcile matches; only CORRECTION_EVENT and "
                "RECONCILE_RESOLVED records may be appended (AI.9 L18831)")
        ts = timestamp or self._clock()
        event_id = f"ev-{uuid_v7()}"
        ledger_id = f"lg-{uuid_v7()}"
        # Caller-declared links only; the writer adds the chain link to the
        # current head at apply time (Ch.16 L16757) so that concurrent appends
        # can never fork the chain.
        parent_ids = list(parents or [])
        raw: Dict[str, Any] = {
            "event_id": event_id, "event_type": event_type,
            "actor": actor or self._actor, "timestamp": ts,
            "ledger_id": ledger_id,
            "intent_id": intent_id, "order_id": order_id, "fill_id": fill_id,
            "cancel_id": cancel_id,
            "decision": payload.pop("decision", None),
            "result": payload.pop("result", None),
            "pnl": _decimal_str(payload.pop("pnl", None)),
            "payload": {k: _jsonable(v) for k, v in payload.items()},
        }
        # ``parents`` are the caller-declared links (e.g. a correction's
        # ``supersedes``); the chain link to the current head is added by the
        # writer at apply time, and so is the payload hash.
        entry = LedgerEntry(
            ledger_id=ledger_id, event_id=event_id, event_type=event_type,
            actor=raw["actor"], intent_id=intent_id, order_id=order_id,
            fill_id=fill_id, cancel_id=cancel_id, payload_hash="",
            parent_ids=tuple(parent_ids), until=until, timestamp=ts,
            price=_decimal_str(price), quantity=_decimal_str(quantity),
            fee=_decimal_str(fee), slippage=_decimal_str(slippage),
            raw=raw)
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        await self._queue.put((entry, future))
        return await future

    async def append_fsm_transition(self, *, intent_id: str, from_state: str,
                                    to_state: str, reason: str,
                                    trigger: str, **payload: Any) -> LedgerEntry:
        """Every execution-FSM state mutation passes through this one writer
        queue (Ch.23 L18255–18257)."""
        payload.setdefault("result", to_state)
        return await self.append(
            event_type="FSM_TRANSITION", intent_id=intent_id,
            from_state=from_state, to_state=to_state, reason=reason,
            trigger=trigger, **payload)

    async def append_fill(self, *, intent_id: str, fill_id: str,
                          order_id: Optional[str] = None, price: Any,
                          quantity: Any, fee: Any = None,
                          slippage: Any = None, **payload: Any) -> LedgerEntry:
        """Fills are idempotent under ``fill_id`` (Ch.16 L16919–16921)."""
        existing = await self.find_by_fill(fill_id)
        if existing is not None:
            return existing
        return await self.append(event_type="FILL", intent_id=intent_id,
                                 fill_id=fill_id, order_id=order_id,
                                 price=price, quantity=quantity, fee=fee,
                                 slippage=slippage, result="FILLED", **payload)

    async def append_trade_plan(self, plan: Mapping[str, Any]) -> LedgerEntry:
        """Materialize the Ch.16 `trade_plan` row + its ledger chain record."""
        row = _trade_plan_row(plan)
        await self._db.execute(
            "INSERT INTO trade_plan (" + ",".join(TRADE_PLAN_COLUMNS)
            + ") VALUES (" + ",".join("?" * len(TRADE_PLAN_COLUMNS)) + ")", row)
        await self._db.commit()
        return await self.append(
            event_type="TRADE_PLAN", intent_id=str(plan.get("proposal_id")),
            decision=str(plan.get("decision")), result="TRADE_PLAN_MATERIALIZED",
            trade_plan={k: _jsonable(v) for k, v in plan.items()},
            snapshot_id=plan.get("snapshot_id"))

    async def append_outcome(self, outcome: Mapping[str, Any]) -> LedgerEntry:
        """Append into the frozen `outcome` DDL (CP-1) + the ledger chain.

        Ch.16 L16912–16918 (stop-gap handling): the record carries BOTH
        ``intended_stop`` and ``actual_fill`` and the difference is attributed
        as ``STOP_GAP_SLIPPAGE``.
        """
        row = _outcome_row(outcome)
        await self._db.execute(
            "INSERT INTO outcome (outcome_id, entry_price, exit_price, pnl, "
            "fees, slippage, mfe, mae, duration, exit_reason, risk_used, "
            "forecast, setup_id, regime, context) VALUES ("
            + ",".join("?" * 15) + ")", row)
        await self._db.commit()
        return await self.append(
            event_type="OUTCOME", intent_id=str(outcome.get("setup_id")),
            pnl=outcome.get("pnl"), result=str(outcome.get("exit_reason")),
            outcome={k: _jsonable(v) for k, v in outcome.items()})

    async def append_correction(self, *, supersedes: str, reason: str,
                                delta: Optional[Mapping[str, Any]] = None,
                                **payload: Any) -> LedgerEntry:
        """Corrections APPEND a revision; the original is never rewritten
        (P12/Ch.16 L16759). T-LR-003 logs broker-vs-ledger deltas this way."""
        return await self.append(
            event_type="CORRECTION_EVENT", parents=[supersedes],
            until=self._clock(), result="SUPERSEDED", reason=reason,
            delta={k: _jsonable(v) for k, v in dict(delta or {}).items()},
            supersedes=supersedes, **payload)

    # -- read API (lock-free, WAL) -----------------------------------------
    async def read_ledger(self, *, limit: Optional[int] = None
                          ) -> List[LedgerEntry]:
        sql = "SELECT " + ",".join(LEDGER_COLUMNS) + " FROM ledger ORDER BY rowid"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        cur = await self._db.execute(sql)
        rows = await cur.fetchall()
        return [_row_to_entry(r) for r in rows]

    async def find_by_fill(self, fill_id: str) -> Optional[LedgerEntry]:
        cur = await self._db.execute(
            "SELECT " + ",".join(LEDGER_COLUMNS) + " FROM ledger WHERE fill_id=?",
            (fill_id,))
        row = await cur.fetchone()
        return _row_to_entry(row) if row else None

    async def find_by_intent(self, intent_id: str) -> List[LedgerEntry]:
        cur = await self._db.execute(
            "SELECT " + ",".join(LEDGER_COLUMNS) + " FROM ledger WHERE intent_id=? "
            "ORDER BY rowid", (intent_id,))
        return [_row_to_entry(r) for r in await cur.fetchall()]

    async def trade_plans(self, *, environment: Optional[str] = None
                          ) -> List[Dict[str, Any]]:
        sql = "SELECT " + ",".join(TRADE_PLAN_COLUMNS) + " FROM trade_plan"
        args: Tuple[Any, ...] = ()
        if environment is not None:
            sql += " WHERE environment=?"
            args = (environment,)
        cur = await self._db.execute(sql, args)
        rows = await cur.fetchall()
        return [dict(zip(TRADE_PLAN_COLUMNS, r)) for r in rows]

    async def positions_from_ledger(self) -> Dict[str, Dict[str, Any]]:
        """T_MATCH: the single source of truth for position state — the
        position recomputed from the ledger (Ch.16 L16919–16921).

        Net quantity per symbol from FILL records (signed by direction) and
        volume-weighted average entry price, both in Decimal.
        """
        entries = await self.read_ledger()
        positions: Dict[str, Dict[str, Any]] = {}
        for e in entries:
            if e.event_type != "FILL" or e.quantity is None or e.price is None:
                continue
            payload = dict(dict(e.raw).get("payload") or {})
            symbol = str(payload.get("symbol") or "UNKNOWN")
            side = str(payload.get("side") or "").upper()
            if side not in ("BUY_OPEN", "SELL_OPEN", "SELL_CLOSE", "BUY_CLOSE"):
                # never guess a direction the wire map does not define (G6)
                raise LedgerError("FILL_SIDE_QX", f"{symbol}: {side!r}")
            qty = Decimal(e.quantity)
            px = Decimal(e.price)
            # ONE_WAY sign law: every BUY_* adds, every SELL_* removes.
            signed = qty if side.startswith("BUY") else -qty
            pos = positions.setdefault(
                symbol, {"symbol": symbol, "net_quantity": Decimal("0"),
                         "open_cost": Decimal("0"),
                         "open_quantity": Decimal("0"), "fills": 0,
                         "fill_ids": []})
            pos["net_quantity"] += signed
            if side.endswith("_OPEN"):
                pos["open_cost"] += qty * px
                pos["open_quantity"] += qty
            pos["fills"] += 1
            pos["fill_ids"].append(e.fill_id)
        for pos in positions.values():
            net: Decimal = pos["net_quantity"]
            opened: Decimal = pos["open_quantity"]
            # volume-weighted average ENTRY price = opening cost / opened qty
            # (Ch.16 L16919–16921); a partial close never re-prices the entry.
            pos["average_entry_price"] = (
                str((pos["open_cost"] / opened).quantize(Decimal("1e-12")))
                if opened else None)
            pos["net_quantity"] = str(net)
            pos["open_cost"] = str(pos["open_cost"])
            pos["open_quantity"] = str(opened)
            pos["direction"] = ("LONG" if net > 0 else "SHORT" if net < 0
                                else "FLAT")
        return positions

    async def reconcile_against_exchange(
            self, exchange_positions: Sequence[Mapping[str, Any]], *,
            tolerance_units: float = RECONCILE_DELTA_TOLERANCE_UNITS
    ) -> Dict[str, Any]:
        """T_MATCH / T_RECONCILE / T-LR-003: compare the ledger-derived
        position with the exchange-reported one.

        Every divergence is (a) detected, (b) logged as a CORRECTION_EVENT,
        (c) an alert-worthy ``RECONCILE_FAILURE`` (AI.9 L18831) and forces
        ``RECOVERY_REQUIRED`` in the FSM — new entries are blocked, never
        silently repaired.
        """
        ledger = await self.positions_from_ledger()
        deltas: List[Dict[str, Any]] = []
        seen = set()
        for ex in exchange_positions:
            symbol = str(ex.get("symbol"))
            seen.add(symbol)
            ex_qty = Decimal(str(ex.get("quantity", ex.get("positionAmt", "0")) or 0))
            led = ledger.get(symbol)
            led_qty = Decimal(led["net_quantity"]) if led else Decimal("0")
            delta = ex_qty - led_qty
            if abs(delta) > Decimal(str(tolerance_units)):
                deltas.append({"symbol": symbol, "exchange_quantity": str(ex_qty),
                               "ledger_quantity": str(led_qty),
                               "delta": str(delta),
                               "alert": "RECONCILE_FAILURE"})
        for symbol, led in ledger.items():
            if symbol in seen or Decimal(led["net_quantity"]) == 0:
                continue
            deltas.append({"symbol": symbol, "exchange_quantity": "0",
                           "ledger_quantity": led["net_quantity"],
                           "delta": str(-Decimal(led["net_quantity"])),
                           "alert": "RECONCILE_FAILURE"})
        for d in deltas:
            await self.append_correction(
                supersedes=self._head or "GENESIS", reason="BROKER_LEDGER_DELTA",
                delta=d, symbol=d["symbol"])
        if deltas:
            self._blocked = f"{len(deltas)} broker-ledger delta(s)"
        elif self._blocked is not None:
            resolved, self._blocked = self._blocked, None
            await self.append(event_type="RECONCILE_RESOLVED",
                              result="RECONCILED", reason="BROKER_LEDGER_MATCH",
                              previously_blocked=resolved,
                              delta_count=0)
        return {"agree": not deltas, "delta_count": len(deltas), "deltas": deltas,
                "action": None if not deltas else "RECOVERY_REQUIRED",
                "new_entries_blocked": bool(deltas),
                "blocked_reason": self._blocked,
                "rule": "AI.9 L18831 delta > ±1 unit ⇒ block new entries, audit "
                        "the delta, emit RECONCILE_FAILURE; Ch.16 L16755 "
                        "divergence forces RECOVERY_REQUIRED"}

    async def require_reconciled(self, intent_id: str) -> Dict[str, Any]:
        """T-LR-002: the execution FSM requires RECONCILED before the next
        decision; an attempt to advance without it is rejected."""
        if self._blocked is not None:
            raise LedgerNotReconciled(
                "T-LR-002_LEDGER_BLOCKED",
                f"the ledger is blocked pending reconciliation ({self._blocked}) "
                "— no decision may advance (AI.9 L18831)")
        entries = await self.find_by_intent(intent_id)
        states = [str(e.raw.get("result")) for e in entries]
        reconciled = "RECONCILED" in states
        if not reconciled:
            raise LedgerNotReconciled(
                "T-LR-002_NOT_RECONCILED",
                f"intent {intent_id} has no RECONCILED ledger record "
                f"(states={states})")
        return {"intent_id": intent_id, "reconciled": True, "states": states}

    async def verify_chain(self) -> Dict[str, Any]:
        """T_LEDGER: recompute every payload hash and the parent linkage.

        A covert INSERT (bypassing the writer) breaks the parent linkage; a
        covert MODIFY breaks the payload hash — and is additionally blocked at
        the schema level by CP-1's ``LEDGER_APPEND_ONLY`` triggers.
        """
        rows = await self.read_ledger()
        head: Optional[str] = None
        breaks: List[Dict[str, Any]] = []
        for index, entry in enumerate(rows):
            recomputed = sha256_hex(canonical_json(dict(entry.raw)))
            if recomputed != entry.payload_hash:
                breaks.append({"index": index, "ledger_id": entry.ledger_id,
                               "kind": "PAYLOAD_HASH_MISMATCH",
                               "stored": entry.payload_hash,
                               "recomputed": recomputed})
            if head is not None and head not in entry.parent_ids:
                breaks.append({"index": index, "ledger_id": entry.ledger_id,
                               "kind": "PARENT_LINK_BROKEN",
                               "expected_parent": head,
                               "parent_ids": list(entry.parent_ids)})
            head = entry.payload_hash
        event_ids = [e.event_id for e in rows]
        return {"records": len(rows), "intact": not breaks, "breaks": breaks,
                "head": head,
                "event_ids_unique": len(set(event_ids)) == len(event_ids),
                "sequence_monotonic": _monotonic(rows),
                "rule": "Ch.16 L16757 hash-chained, append-only; T_LEDGER"}

    async def _recover_head(self) -> Optional[str]:
        cur = await self._db.execute(
            "SELECT payload_hash FROM ledger ORDER BY rowid DESC LIMIT 1")
        row = await cur.fetchone()
        return str(row[0]) if row else None

    @property
    def written(self) -> int:
        return self._written

    @property
    def head(self) -> Optional[str]:
        return self._head

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def blocked(self) -> bool:
        """True while a reconciliation failure blocks new entries."""
        return self._blocked is not None

    @property
    def blocked_reason(self) -> Optional[str]:
        return self._blocked


def _monotonic(rows: Sequence[LedgerEntry]) -> bool:
    """T-LR-001: 1000 ledger writes, sequence monotonic, no overwrites."""
    if len(rows) < 2:
        return True
    return all(rows[i].ledger_id != rows[i + 1].ledger_id and
               rows[i].timestamp <= rows[i + 1].timestamp
               for i in range(len(rows) - 1))


# ---------------------------------------------------------------------------
# row helpers (TEXT-Decimal at the store boundary — P8/G11)
# ---------------------------------------------------------------------------

def _money_text(value: Any) -> str:
    """TEXT encoding for the CHECK-constrained money columns ('' when absent)."""
    if value is None or value == "":
        return ""
    return str(value) if isinstance(value, str) else str(Decimal(str(value)))


def _money_or_none(value: Any) -> Optional[str]:
    return None if value in (None, "") else str(value)


def _decimal_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    return str(Decimal(str(value)))


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _row_to_entry(row: Sequence[Any]) -> LedgerEntry:
    (ledger_id, intent_id, order_id, fill_id, cancel_id, payload_hash,
     parent_ids, until, raw, fee, slippage, price, quantity, timestamp) = row
    parsed_raw = json.loads(raw) if raw else {}
    parents = json.loads(parent_ids) if parent_ids else []
    return LedgerEntry(
        ledger_id=str(ledger_id), event_id=str(parsed_raw.get("event_id", "")),
        event_type=str(parsed_raw.get("event_type", "")),
        actor=str(parsed_raw.get("actor", "")), intent_id=intent_id,
        order_id=order_id, fill_id=fill_id, cancel_id=cancel_id,
        payload_hash=str(payload_hash), parent_ids=tuple(parents), until=until,
        timestamp=str(timestamp), price=_money_or_none(price),
        quantity=_money_or_none(quantity), fee=_money_or_none(fee),
        slippage=_money_or_none(slippage), raw=parsed_raw)


def _trade_plan_row(plan: Mapping[str, Any]) -> Tuple[Any, ...]:
    """Validate + project a trade plan onto the frozen Ch.16 DDL columns."""
    environment = str(plan.get("environment", "PAPER"))
    if environment not in ENVIRONMENTS:
        raise LedgerError("ENVIRONMENT_QX",
                          f"{environment} — SHADOW does not exist (§9.5-9)")
    direction = plan.get("direction")
    if direction not in DIRECTIONS:
        raise LedgerError("DIRECTION_QX", str(direction))
    decision = plan.get("decision")
    if decision not in DECISIONS:
        raise LedgerError("DECISION_QX", str(decision))
    if plan.get("sized_quantity") is None:
        raise LedgerError("SIZED_QUANTITY_REQUIRED")
    if not plan.get("proposal_id") or not plan.get("setup_id"):
        raise LedgerError("TRADE_PLAN_IDENTITY_REQUIRED",
                          "proposal_id and setup_id are NOT NULL")
    vetoes = plan.get("vetoes_applied", [])
    payload_hash = str(plan.get("payload_hash")
                       or sha256_hex(canonical_json(
                           {k: _jsonable(v) for k, v in plan.items()})))
    return (str(plan["proposal_id"]), str(plan["setup_id"]),
            plan.get("symbol"), plan.get("timeframe"), direction,
            plan.get("entry_ref"),
            None if plan.get("stop_price") is None else float(plan["stop_price"]),
            None if plan.get("target_price") is None else float(plan["target_price"]),
            float(plan["sized_quantity"]),
            None if plan.get("risk_amount") is None else float(plan["risk_amount"]),
            None if plan.get("contract_multiplier") is None
            else float(plan["contract_multiplier"]),
            decision,
            json.dumps(list(vetoes), separators=(",", ":"), sort_keys=True),
            plan.get("risk_state"), plan.get("package_version"),
            plan.get("snapshot_id"), plan.get("as_of"),
            plan.get("created_utc") or utc_now_ms(), plan.get("lineage"),
            payload_hash, environment)


OUTCOME_COLUMNS: Tuple[str, ...] = (
    "outcome_id", "entry_price", "exit_price", "pnl", "fees", "slippage",
    "mfe", "mae", "duration", "exit_reason", "risk_used", "forecast",
    "setup_id", "regime", "context")


def _outcome_row(outcome: Mapping[str, Any]) -> Tuple[Any, ...]:
    """Frozen `outcome` DDL (CP-1) + Ch.16 L16912–16918 stop-gap attribution."""
    if not outcome.get("setup_id"):
        raise LedgerError("OUTCOME_SETUP_ID_REQUIRED",
                          "outcome.setup_id is the FK to setup_candidate")
    intended = outcome.get("intended_stop")
    actual = outcome.get("actual_fill")
    slippage = outcome.get("slippage")
    if intended is not None and actual is not None and slippage is None:
        slippage = str(Decimal(str(actual)) - Decimal(str(intended)))
    return (str(outcome.get("outcome_id") or f"oc-{uuid_v7()}"),
            _decimal_str(outcome.get("entry_price")),
            _decimal_str(outcome.get("exit_price")),
            _decimal_str(outcome.get("pnl")),
            _decimal_str(outcome.get("fees")),
            _decimal_str(slippage),
            _decimal_str(outcome.get("mfe")), _decimal_str(outcome.get("mae")),
            None if outcome.get("duration") is None else int(outcome["duration"]),
            outcome.get("exit_reason"), _decimal_str(outcome.get("risk_used")),
            json.dumps(_jsonable(outcome.get("forecast") or {}),
                       separators=(",", ":"), sort_keys=True),
            str(outcome["setup_id"]), outcome.get("regime"),
            json.dumps(_jsonable(outcome.get("context") or {}),
                       separators=(",", ":"), sort_keys=True))


def stop_gap_slippage(*, intended_stop: Any, actual_fill: Any,
                      direction: str) -> Dict[str, Any]:
    """Ch.16 L16912–16918: the ledger records BOTH ``intended_stop`` and
    ``actual_fill``; the difference is attributed as ``STOP_GAP_SLIPPAGE`` and
    the sizing machine uses the REALIZED worst loss (not modeled R) next."""
    intended = Decimal(str(intended_stop))
    actual = Decimal(str(actual_fill))
    if str(direction).upper() == "LONG":
        gap = intended - actual          # a fill BELOW the stop is the gap
    elif str(direction).upper() == "SHORT":
        gap = actual - intended
    else:
        raise LedgerError("DIRECTION_QX", str(direction))
    exceeded = gap > 0
    return {"intended_stop": str(intended), "actual_fill": str(actual),
            "stop_gap": str(gap), "exceeded": exceeded,
            "attribution": "STOP_GAP_SLIPPAGE" if exceeded else None,
            "next_risk_input": "REALIZED_WORST_LOSS" if exceeded else "MODELED_R",
            "rule": "Ch.16 L16912–16918"}


def protection_failed_event(*, intent_id: str, reason: str) -> Dict[str, Any]:
    """Ch.16 L16916–16918: if stop protection fails to place
    (PROTECTION_FAILED) the position is closed at market by the Playbook
    emergency path and the event escalates to the OWNER."""
    return {"event_type": "PROTECTION_FAILED", "intent_id": intent_id,
            "reason": reason, "action": "PLAYBOOK_EMERGENCY_CLOSE_AT_MARKET",
            "escalation": "OWNER", "alert": "EXEC_RECOVERY", "priority": "P0",
            "rule": "Ch.16 L16916–16918"}


__all__ = [
    "AUDIT_DDL", "CONTRACT_VERSION", "DECISIONS", "DIRECTIONS", "ENVIRONMENTS",
    "LEDGER_AUDIT_MIGRATION", "LEDGER_COLUMNS", "LedgerError", "LedgerEntry",
    "LedgerNotReconciled", "LedgerSingleWriterError", "LedgerWriter",
    "OUTCOME_COLUMNS", "RECONCILE_DELTA_TOLERANCE_UNITS", "TRADE_PLAN_COLUMNS",
    "TRADE_PLAN_DDL", "TRADE_PLAN_MIGRATION", "active_writer",
    "protection_failed_event", "stop_gap_slippage", "utc_now_ms",
]
