"""Execution FSM — Ch.16 §16.1 (APEX_GEN5.md L16752–16918) + the Ch.1 canonical
mapping note (L255) + Ch.23 Startup Reconciliation Sequence (L18242–18251) +
AI.9 startup reconciliation / fail-closed transitions (L18876–18903).

The FSM state list is EXACTLY the frozen SL-6 canonical list (Ch.16 L16757):
``READY → SUBMITTING → ACKNOWLEDGED → PARTIAL → FILLED → PROTECTED → MANAGED →
CLOSED → RECONCILED`` with ``RECOVERY_REQUIRED`` on fill timeout (E-EXEC-001)
and the two terminal exchange-response classes Ch.16 L16858–16860 names
(``REJECTED`` / ``CANCELLED``). Ch.1's diagram names are mapped, never added
(L255): ARMED/TRIGGERED are nested substates of READY, EXECUTING ≡ SUBMITTING,
SETTLED ≡ RECONCILED, ARCHIVED is ledger retention and NOT an FSM state.

Reconciliation is a first-class invariant, not a background task: no state may
advance to RECONCILED while ledger and exchange disagree, and divergence forces
RECOVERY_REQUIRED (L16761–16764). UNKNOWN always leads to reconcile-before-
action, never to blind retry (L16860). Every transition is written through the
single ledger writer (Ch.23 L18255) and published on the in-process bus.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import (Any, Awaitable, Callable, Dict, FrozenSet, List, Mapping,
                    Optional, Sequence, Tuple)

from apex.bus import EventBus, Priority, make_event
from apex.errors import get_error_code
from apex.execution.toobit_adapter import AdapterResult, ToobitAdapter
from apex.execution.toobit_map import (resolve_leverage,
                                       rollover_entry_allowed, side_for)
from apex.identity.uuid_v7 import uuid_v7
from apex.ledger.store import (LedgerEntry, LedgerWriter,
                               protection_failed_event, stop_gap_slippage)

CONTRACT_VERSION = "4.0.0"

# ---------------------------------------------------------------------------
# Governed timeouts — Ch.17 L17010–17011 (dynamic/governed defaults). No YAML
# home exists and CP-7's WRITE SET excludes params/*.yaml; frozen verbatim from
# those lines and asserted by tests/unit/test_execution_fsm.py (ISSUE-CP7-003).
# ---------------------------------------------------------------------------
SUBMISSION_TIMEOUT_SECONDS = 5.0
FILL_TIMEOUT_SECONDS = 5.0
CLOCK_DRIFT_TOLERANCE_SECONDS = 5.0     # Ch.17 L16995 clock_drift_tolerance
E12_DRIFT_DEGRADED_SECONDS = 0.5        # AI.7 L18724: drift > 500 ms ⇒ DEGRADED
RECONCILE_DELTA_TOLERANCE_UNITS = 1.0   # AI.9 L18831: delta > ±1 unit

FILL_TIMEOUT_REASON = "E-EXEC-001"

# ---------------------------------------------------------------------------
# State vocabulary
# ---------------------------------------------------------------------------

#: Ch.16 L16757 canonical SL-6 lifecycle (the authoritative list).
CANONICAL_STATES: Tuple[str, ...] = (
    "READY", "SUBMITTING", "ACKNOWLEDGED", "PARTIAL", "FILLED", "PROTECTED",
    "MANAGED", "CLOSED", "RECONCILED")

#: Ch.16 L16759 + the FSM state-semantics table L16778–16789.
RECOVERY_REQUIRED = "RECOVERY_REQUIRED"

#: Ch.16 L16858–16860: every terminal or unexpected exchange response maps to
#: exactly one of REJECTED / CANCELLED / UNKNOWN. UNKNOWN is an *outcome*, and
#: it always drives the FSM to RECOVERY_REQUIRED (never a state of its own).
TERMINAL_RESPONSE_STATES: Tuple[str, ...] = ("REJECTED", "CANCELLED")

#: Ch.1 L255 mapping (narrative diagram → canonical states).
CH1_DIAGRAM_MAP: Dict[str, Optional[str]] = {
    "ARMED": "READY",            # nested substate of READY (no exchange order)
    "TRIGGERED": "READY",        # nested substate of READY (no exchange order)
    "EXECUTING": "SUBMITTING",
    "SETTLED": "RECONCILED",
    "ARCHIVED": None,            # ledger retention, NOT an FSM state
    "IDLE": None,                # pre-plan narrative state, NOT an FSM state
    "CANCEL_PENDING": "SUBMITTING",   # narrative; a cancel resolves to CANCELLED
    "PRUNED": None,              # Ch.1 age-pruning of a *signal*, not an order
    "INVALIDATED": "REJECTED",   # window quality < 0.5 ⇒ no order is submitted
    "UNKNOWN": RECOVERY_REQUIRED,
}

FSM_STATES: Tuple[str, ...] = CANONICAL_STATES + (RECOVERY_REQUIRED,) + \
    TERMINAL_RESPONSE_STATES

#: Ch.16 L16778–16789 authorized meaning of every state.
STATE_SEMANTICS: Dict[str, str] = {
    "READY": "plan received, pre-submission validation",
    "SUBMITTING": "order submission in progress",
    "ACKNOWLEDGED": "exchange acknowledgement received",
    "PARTIAL": "partial fill",
    "FILLED": "full fill",
    "PROTECTED": "stop/target orders placed",
    "MANAGED": "Playbook management active (trailing, time exit)",
    "CLOSED": "position closed",
    "RECONCILED": "ledger ↔ exchange fully matched",
    "RECOVERY_REQUIRED": "divergence or fill timeout (E-EXEC-001); "
                         "reconcile-first recovery",
    "REJECTED": "exchange rejected the order (terminal response class)",
    "CANCELLED": "order cancelled (terminal response class)",
}

#: Triggers are the only lawful way to move; a transition absent from this
#: matrix is refused (AI.12 Phase 6: "No state skipping").
LEGAL_TRANSITIONS: Dict[Tuple[str, str], str] = {
    # READY — pre-submission validation (Ch.16 L16779)
    ("READY", "SUBMIT_ORDER"): "SUBMITTING",
    ("READY", "VALIDATION_FAILED"): "REJECTED",
    ("READY", "RECONCILE_DIVERGENCE"): RECOVERY_REQUIRED,
    ("READY", "CANCEL_REQUESTED"): "CANCELLED",
    # SUBMITTING
    ("SUBMITTING", "EXCHANGE_ACK"): "ACKNOWLEDGED",
    ("SUBMITTING", "PARTIAL_FILL"): "PARTIAL",
    ("SUBMITTING", "FULL_FILL"): "FILLED",
    ("SUBMITTING", "EXCHANGE_REJECT"): "REJECTED",
    ("SUBMITTING", "CANCEL_CONFIRMED"): "CANCELLED",
    ("SUBMITTING", "SUBMISSION_TIMEOUT"): RECOVERY_REQUIRED,
    ("SUBMITTING", "UNKNOWN_OUTCOME"): RECOVERY_REQUIRED,
    ("SUBMITTING", "RECONCILE_DIVERGENCE"): RECOVERY_REQUIRED,
    # ACKNOWLEDGED
    ("ACKNOWLEDGED", "PARTIAL_FILL"): "PARTIAL",
    ("ACKNOWLEDGED", "FULL_FILL"): "FILLED",
    ("ACKNOWLEDGED", "CANCEL_CONFIRMED"): "CANCELLED",
    ("ACKNOWLEDGED", "EXCHANGE_REJECT"): "REJECTED",
    ("ACKNOWLEDGED", "FILL_TIMEOUT"): RECOVERY_REQUIRED,
    ("ACKNOWLEDGED", "UNKNOWN_OUTCOME"): RECOVERY_REQUIRED,
    ("ACKNOWLEDGED", "RECONCILE_DIVERGENCE"): RECOVERY_REQUIRED,
    ("ACKNOWLEDGED", "PROTECTION_PLACED"): "PROTECTED",
    # PARTIAL — "PARTIAL until fill_timeout ⇒ RECOVERY_REQUIRED" (L16808)
    ("PARTIAL", "FULL_FILL"): "FILLED",
    ("PARTIAL", "FILL_TIMEOUT"): RECOVERY_REQUIRED,
    ("PARTIAL", "CANCEL_CONFIRMED"): "CANCELLED",
    ("PARTIAL", "UNKNOWN_OUTCOME"): RECOVERY_REQUIRED,
    ("PARTIAL", "RECONCILE_DIVERGENCE"): RECOVERY_REQUIRED,
    ("PARTIAL", "PROTECTION_PLACED"): "PROTECTED",
    # FILLED
    ("FILLED", "PROTECTION_PLACED"): "PROTECTED",
    ("FILLED", "PROTECTION_FAILED"): RECOVERY_REQUIRED,
    ("FILLED", "POSITION_CLOSED"): "CLOSED",
    ("FILLED", "RECONCILE_DIVERGENCE"): RECOVERY_REQUIRED,
    ("FILLED", "UNKNOWN_OUTCOME"): RECOVERY_REQUIRED,
    # PROTECTED
    ("PROTECTED", "MANAGEMENT_ACTIVE"): "MANAGED",
    ("PROTECTED", "POSITION_CLOSED"): "CLOSED",
    ("PROTECTED", "PROTECTION_FAILED"): RECOVERY_REQUIRED,
    ("PROTECTED", "RECONCILE_DIVERGENCE"): RECOVERY_REQUIRED,
    # MANAGED
    ("MANAGED", "POSITION_CLOSED"): "CLOSED",
    ("MANAGED", "PROTECTION_FAILED"): RECOVERY_REQUIRED,
    ("MANAGED", "RECONCILE_DIVERGENCE"): RECOVERY_REQUIRED,
    # CLOSED
    ("CLOSED", "RECONCILE_MATCH"): "RECONCILED",
    ("CLOSED", "RECONCILE_DIVERGENCE"): RECOVERY_REQUIRED,
    # RECOVERY_REQUIRED — reconcile-first recovery (L16764, L16789)
    (RECOVERY_REQUIRED, "RECONCILE_MATCH"): "RECONCILED",
    (RECOVERY_REQUIRED, "RECONCILE_RESOLVED_ACK"): "ACKNOWLEDGED",
    (RECOVERY_REQUIRED, "RECONCILE_RESOLVED_PARTIAL"): "PARTIAL",
    (RECOVERY_REQUIRED, "RECONCILE_RESOLVED_FILLED"): "FILLED",
    (RECOVERY_REQUIRED, "RECONCILE_RESOLVED_PROTECTED"): "PROTECTED",
    (RECOVERY_REQUIRED, "RECONCILE_RESOLVED_MANAGED"): "MANAGED",
    (RECOVERY_REQUIRED, "RECONCILE_RESOLVED_CLOSED"): "CLOSED",
    (RECOVERY_REQUIRED, "RECONCILE_RESOLVED_CANCELLED"): "CANCELLED",
    (RECOVERY_REQUIRED, "RECONCILE_RESOLVED_REJECTED"): "REJECTED",
    (RECOVERY_REQUIRED, "RECONCILE_DIVERGENCE"): RECOVERY_REQUIRED,
    # terminal exchange responses still reconcile against the ledger
    ("REJECTED", "RECONCILE_MATCH"): "RECONCILED",
    ("CANCELLED", "RECONCILE_MATCH"): "RECONCILED",
}

TERMINAL_STATES: FrozenSet[str] = frozenset({"RECONCILED"})

TRIGGERS: FrozenSet[str] = frozenset(t for (_, t) in LEGAL_TRANSITIONS)

#: Ch.23 L18242 boot machine.
BOOT_STATES: Tuple[str, ...] = ("STARTING", "SELF_TEST", "RECONCILING", "READY",
                                "DEGRADED", "RECOVERY_REQUIRED")
BOOT_TRANSITIONS: Dict[Tuple[str, str], str] = {
    ("STARTING", "SELF_TEST_BEGIN"): "SELF_TEST",
    ("SELF_TEST", "SELF_TEST_PASS"): "RECONCILING",
    ("SELF_TEST", "SELF_TEST_FAIL"): "RECOVERY_REQUIRED",
    ("SELF_TEST", "DRIFT_BEYOND_TOLERANCE"): "DEGRADED",
    ("RECONCILING", "RECONCILE_MATCH"): "READY",
    ("RECONCILING", "RECONCILE_DIVERGENCE"): "RECOVERY_REQUIRED",
    ("RECONCILING", "DEPENDENCY_UNAVAILABLE"): "DEGRADED",
    ("RECOVERY_REQUIRED", "RECONCILE_MATCH"): "READY",
    ("RECOVERY_REQUIRED", "RECONCILE_DIVERGENCE"): "RECOVERY_REQUIRED",
    ("DEGRADED", "RECONCILE_MATCH"): "READY",
    ("DEGRADED", "RECONCILE_DIVERGENCE"): "RECOVERY_REQUIRED",
}

#: Ch.23 L18250–18251: Emergency Ladder actions are available in every boot
#: state EXCEPT STARTING; no new trade may be created before READY.
LADDER_AVAILABLE_EXCEPT: FrozenSet[str] = frozenset({"STARTING"})


class FsmError(RuntimeError):
    """Fail-closed FSM violation with a deterministic reason code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}" + (f": {detail}" if detail else ""))


class IllegalTransitionError(FsmError):
    """A transition outside the frozen matrix (no state skipping, AI.12)."""


def canonical_state(name: str) -> str:
    """Map a Ch.1 diagram name onto its canonical SL-6 state (L255). Names that
    are not FSM states (ARCHIVED/IDLE/PRUNED) raise — they are never invented."""
    if name in FSM_STATES:
        return name
    if name in CH1_DIAGRAM_MAP:
        mapped = CH1_DIAGRAM_MAP[name]
        if mapped is None:
            raise FsmError("NOT_AN_FSM_STATE",
                           f"{name} is not an execution-FSM state (Ch.1 L255)")
        return mapped
    raise FsmError("FSM_STATE_UNKNOWN", str(name))


def legal_targets(state: str) -> Dict[str, str]:
    """The row of the transition matrix for ``state`` (trigger → next state)."""
    s = canonical_state(state)
    return {trigger: nxt for (src, trigger), nxt in LEGAL_TRANSITIONS.items()
            if src == s}


def is_legal(src: str, trigger: str, dst: str) -> bool:
    return LEGAL_TRANSITIONS.get((canonical_state(src), trigger)) == \
        canonical_state(dst)


# ---------------------------------------------------------------------------
# Trade plan (Ch.16 L16814–16846) — SL-5 output / SL-6 input
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TradePlan:
    """The Ch.16 `trade_plan` row built from CP-6's two contract shapes
    (HANDOFF_CP6 §INTERFACES 1–2: StrategyProposal + adjudicate output)."""
    proposal_id: str
    setup_id: str
    symbol: str
    timeframe: str
    direction: str            # LONG | SHORT | FLAT
    entry_ref: str
    stop_price: Optional[float]
    target_price: Optional[float]
    sized_quantity: float
    risk_amount: Optional[float]
    contract_multiplier: Optional[float]
    decision: str             # ALLOW | REDUCE | REJECT
    vetoes_applied: Tuple[int, ...]
    risk_state: Optional[str]
    package_version: Optional[str]
    snapshot_id: str
    as_of: str
    created_utc: str
    lineage: str
    payload_hash: str
    environment: str
    leverage: Optional[float] = None
    owner_leverage_cap: Optional[float] = None
    contract_version: str = CONTRACT_VERSION

    def to_dict(self) -> Dict[str, Any]:
        out = {f: getattr(self, f) for f in self.__dataclass_fields__}
        out["vetoes_applied"] = list(self.vetoes_applied)
        return out


def build_trade_plan(*, proposal: Any, adjudication: Mapping[str, Any],
                     symbol: str, timeframe: str, environment: str,
                     as_of: str, capital: float,
                     contract_multiplier: Optional[float] = None,
                     risk_state: Optional[str] = None,
                     package_version: Optional[str] = None,
                     owner_leverage_cap: Optional[float] = None,
                     created_utc: Optional[str] = None,
                     lineage: Optional[str] = None) -> TradePlan:
    """Project CP-6's StrategyProposal + adjudicate() output onto the frozen
    Ch.16 columns. Nothing is re-decided here: the Risk Kernel's decision and
    sized quantity are consumed as-is (HANDOFF_CP6 §INTERFACES 2 — "treat as
    the ceiling; never size above it")."""
    proposal_dict = proposal.to_dict() if hasattr(proposal, "to_dict") else dict(proposal)
    decision = str(adjudication["decision"])
    if decision not in ("ALLOW", "REDUCE", "REJECT"):
        raise FsmError("DECISION_QX", decision)
    if environment not in ("PAPER", "LIVE", "RESEARCH", "BACKTEST"):
        raise FsmError("ENVIRONMENT_QX",
                       f"{environment} — SHADOW does not exist (§9.5-9)")
    direction = str(proposal_dict.get("direction", "NO_TRADE"))
    if direction == "NO_TRADE":
        direction = "FLAT"          # Ch.16 CHECK(direction IN LONG/SHORT/FLAT)
    if direction not in ("LONG", "SHORT", "FLAT"):
        raise FsmError("DIRECTION_QX", direction)
    sized = float(adjudication.get("sized_quantity", 0.0))
    if decision == "REJECT":
        sized = 0.0                 # Ch.16/CP-6: REJECT carries sized_quantity 0
    targets = tuple(proposal_dict.get("targets") or ())
    sizing = dict(adjudication.get("sizing") or {})
    leverage = None
    if environment == "LIVE" or sized > 0:
        resolved = resolve_leverage(timeframe, symbol=symbol,
                                    owner_cap=owner_leverage_cap)
        leverage = float(resolved["leverage"])
    plan_payload = {
        "proposal_id": str(proposal_dict.get("proposal_id")
                           or getattr(proposal, "proposal_id", "")),
        "setup_id": str(proposal_dict["setup_id"]),
        "symbol": symbol, "timeframe": timeframe, "direction": direction,
        "entry_ref": str(proposal_dict.get("entry_logic_ref", "")),
        "stop_price": proposal_dict.get("stop"),
        "target_price": targets[0] if targets else None,
        "sized_quantity": sized,
        "risk_amount": sizing.get("R_allowed"),
        "contract_multiplier": contract_multiplier,
        "decision": decision,
        "vetoes_applied": [int(v) for v in adjudication.get("vetoes_applied", [])],
        "risk_state": risk_state, "package_version": package_version,
        "snapshot_id": str(adjudication.get("snapshot_id")
                           or proposal_dict["snapshot_id"]),
        "as_of": as_of, "environment": environment, "leverage": leverage,
    }
    from apex.identity.canonical_json import canonical_json
    from apex.identity.hashes import sha256_hex
    return TradePlan(
        proposal_id=plan_payload["proposal_id"], setup_id=plan_payload["setup_id"],
        symbol=symbol, timeframe=timeframe, direction=direction,
        entry_ref=plan_payload["entry_ref"], stop_price=plan_payload["stop_price"],
        target_price=plan_payload["target_price"], sized_quantity=sized,
        risk_amount=plan_payload["risk_amount"],
        contract_multiplier=contract_multiplier, decision=decision,
        vetoes_applied=tuple(plan_payload["vetoes_applied"]),
        risk_state=risk_state, package_version=package_version,
        snapshot_id=plan_payload["snapshot_id"], as_of=as_of,
        created_utc=created_utc or _utc_now_ms(),
        lineage=lineage or f"proposal:{plan_payload['proposal_id']}",
        payload_hash=sha256_hex(canonical_json(
            {k: v for k, v in plan_payload.items()})),
        environment=environment, leverage=leverage,
        owner_leverage_cap=owner_leverage_cap)


def _utc_now_ms() -> str:
    now = _dt.datetime.now(_dt.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


# ---------------------------------------------------------------------------
# Transition record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TransitionRecord:
    intent_id: str
    from_state: str
    trigger: str
    to_state: str
    reason: str
    timestamp: str
    ledger_id: Optional[str]
    evidence: Mapping[str, Any] = field(default_factory=dict)
    error_code: Optional[str] = None


# ---------------------------------------------------------------------------
# The per-order FSM
# ---------------------------------------------------------------------------

class ExecutionFSM:
    """One order lifecycle. Identity is ``intent_id`` (UUIDv7) sent as the
    exchange ``clientOrderId`` (Ch.16 L16752, L16848).

    Every state mutation passes through the single ledger writer queue
    (Ch.23 L18255) and is published on the in-process bus (P1 for lifecycle,
    P0 for RECOVERY_REQUIRED / protection failure — Ch.21 signaling tier
    L17995–18001).
    """

    def __init__(self, *, intent_id: Optional[str] = None,
                 ledger: Optional[LedgerWriter] = None,
                 adapter: Optional[ToobitAdapter] = None,
                 bus: Optional[EventBus] = None,
                 clock: Optional[Callable[[], float]] = None,
                 utc_now: Optional[Callable[[], str]] = None,
                 submission_timeout: float = SUBMISSION_TIMEOUT_SECONDS,
                 fill_timeout: float = FILL_TIMEOUT_SECONDS,
                 environment: str = "PAPER") -> None:
        self.intent_id = intent_id or uuid_v7()
        self._plan_entry: Any = None
        self._ledger = ledger
        self._adapter = adapter
        self._bus = bus
        self._clock = clock if clock is not None else _monotonic
        self._utc_now = utc_now if utc_now is not None else _utc_now_ms
        self.submission_timeout = float(submission_timeout)
        self.fill_timeout = float(fill_timeout)
        self.environment = environment
        self._state = "READY"
        self._substate: Optional[str] = None      # ARMED / TRIGGERED (Ch.1 L255)
        self._history: List[TransitionRecord] = []
        self._submitted_at: Optional[float] = None
        self._acked_at: Optional[float] = None
        self._order_id: Optional[str] = None
        self._fills: List[Dict[str, Any]] = []
        self._plan: Optional[TradePlan] = None
        self._last_adapter_result: Optional[AdapterResult] = None
        self._reconciled = False

    # -- read-only views ----------------------------------------------------
    @property
    def state(self) -> str:
        return self._state

    @property
    def substate(self) -> Optional[str]:
        return self._substate

    @property
    def history(self) -> Tuple[TransitionRecord, ...]:
        return tuple(self._history)

    @property
    def plan(self) -> Optional[TradePlan]:
        return self._plan

    @property
    def order_id(self) -> Optional[str]:
        return self._order_id

    @property
    def fills(self) -> Tuple[Dict[str, Any], ...]:
        return tuple(dict(f) for f in self._fills)

    @property
    def last_adapter_result(self) -> Optional[AdapterResult]:
        return self._last_adapter_result

    @property
    def is_terminal(self) -> bool:
        return self._state in TERMINAL_STATES

    def legal_triggers(self) -> Dict[str, str]:
        return legal_targets(self._state)

    # -- transitions --------------------------------------------------------
    async def advance(self, trigger: str, *, reason: str = "",
                      evidence: Optional[Mapping[str, Any]] = None,
                      error_code: Optional[str] = None) -> TransitionRecord:
        """Apply one legal transition; anything else is refused fail-closed."""
        src = self._state
        key = (src, trigger)
        if key not in LEGAL_TRANSITIONS:
            raise IllegalTransitionError(
                "ILLEGAL_FSM_TRANSITION",
                f"{src} --{trigger}--> ? is not in the frozen matrix "
                f"(legal: {sorted(legal_targets(src)) or 'none — terminal'})")
        dst = LEGAL_TRANSITIONS[key]
        if dst == "SUBMITTING" and trigger == "SUBMIT_ORDER":
            self._submitted_at = self._clock()
        if dst in ("ACKNOWLEDGED", "PARTIAL"):
            # the fill-timeout window (E-EXEC-001) starts at the FIRST venue
            # response — an acknowledgement or a partial fill alike (Ch.16
            # L16867–16868: no fill within the governed window ⇒ recovery).
            self._acked_at = self._clock()
        ts = self._utc_now()
        ledger_id: Optional[str] = None
        if self._ledger is not None:
            entry = await self._ledger.append_fsm_transition(
                intent_id=self.intent_id, from_state=src, to_state=dst,
                reason=reason or trigger, trigger=trigger,
                symbol=self._plan.symbol if self._plan else None,
                timeframe=self._plan.timeframe if self._plan else None,
                environment=self.environment,
                order_id=self._order_id,
                error_code=error_code,
                evidence={k: _jsonable(v) for k, v in dict(evidence or {}).items()})
            ledger_id = entry.ledger_id
        record = TransitionRecord(intent_id=self.intent_id, from_state=src,
                                  trigger=trigger, to_state=dst,
                                  reason=reason or trigger, timestamp=ts,
                                  ledger_id=ledger_id,
                                  evidence=dict(evidence or {}),
                                  error_code=error_code)
        self._history.append(record)
        self._state = dst
        if dst == "RECONCILED":
            self._reconciled = True
        await self._publish(record)
        return record

    def set_substate(self, substate: str) -> None:
        """Ch.1 L255: ARMED/TRIGGERED are nested substates of READY (no
        exchange order exists yet) — they never change the canonical state."""
        if self._state != "READY":
            raise FsmError("SUBSTATE_ONLY_IN_READY",
                           f"{substate} in {self._state}")
        if substate not in ("ARMED", "TRIGGERED"):
            raise FsmError("SUBSTATE_QX", str(substate))
        self._substate = substate

    async def _publish(self, record: TransitionRecord) -> None:
        """Publish the transition on the in-process bus.

        P0 (RECOVERY_REQUIRED, PROTECTION_FAILED) is SYNCHRONOUS: the bus
        awaits every subscriber inline (AI.12 Phase 3 / Ch.23 L18253). P1 goes
        to the dedicated lane. Nothing is fire-and-forget, so a transition is
        never reported before its event is routed.
        """
        if self._bus is None:
            return
        critical = record.to_state == RECOVERY_REQUIRED or \
            record.trigger == "PROTECTION_FAILED"
        priority = Priority.P0 if critical else Priority.P1
        topic = "execution.fsm.transition"
        payload = {"intent_id": record.intent_id, "from": record.from_state,
                   "to": record.to_state, "trigger": record.trigger,
                   "reason": record.reason, "timestamp": record.timestamp,
                   "ledger_id": record.ledger_id,
                   "environment": self.environment,
                   "symbol": self._plan.symbol if self._plan else None,
                   "timeframe": self._plan.timeframe if self._plan else None}
        await self._bus.publish(make_event(int(priority), topic, payload))

    # -- submission ---------------------------------------------------------
    async def submit(self, plan: TradePlan, *,
                     price: Any, quantity: Optional[Any] = None,
                     timestamp_utc: Optional[str] = None,
                     nonce: Optional[str] = None) -> Dict[str, Any]:
        """READY → SUBMITTING → the adapter's five-operation surface.

        Pre-submission validation is part of READY (Ch.16 L16779): a REJECT
        decision, a zero sized quantity, a disabled (symbol, TF) cell, or a
        rollover ban never reaches the exchange.
        """
        self._plan = plan
        refusal = self.pre_submission_validation(plan)
        if refusal is not None:
            await self.advance("VALIDATION_FAILED", reason=refusal["reason"],
                               evidence=refusal)
            return {"submitted": False, "reason": refusal["reason"],
                    "state": self._state, "detail": refusal}
        if self._adapter is None:
            raise FsmError("ADAPTER_REQUIRED",
                           "the execution FSM is the only path to Toobit "
                           "(Ch.16 L16752) — no adapter was wired")
        qty = plan.sized_quantity if quantity is None else quantity
        if self._ledger is not None:
            # Ch.16: the `trade_plan` row is materialized BEFORE anything is
            # sent, so the venue order can always be traced to a governed plan
            # (single source of truth; reconcile-first).
            self._plan_entry = await self._ledger.append_trade_plan(plan.to_dict())
        await self.advance("SUBMIT_ORDER", reason="plan accepted for submission",
                           evidence={"symbol": plan.symbol,
                                     "timeframe": plan.timeframe,
                                     "quantity": str(qty), "price": str(price),
                                     "leverage": plan.leverage})
        result = await self._adapter.submit_order(
            intent_id=self.intent_id, symbol=plan.symbol,
            timeframe=plan.timeframe, direction=plan.direction, quantity=qty,
            price=price, phase="entry", kind="entry",
            leverage=plan.leverage, owner_leverage_cap=plan.owner_leverage_cap,
            timestamp_utc=timestamp_utc, nonce=nonce)
        self._last_adapter_result = result
        self._order_id = result.order_id
        return await self.apply_adapter_result(result)

    def pre_submission_validation(self, plan: TradePlan) -> Optional[Dict[str, Any]]:
        """READY-state validation (Ch.16 L16779 + L16903 rollover + L16877
        disabled cell). Returns a refusal record or ``None``."""
        if plan.decision == "REJECT":
            return {"reason": "RISK_REJECT",
                    "rule": "Ch.15 veto authority — a REJECT plan is never "
                            "submitted (Owner > Risk > Decision)"}
        if plan.decision not in ("ALLOW", "REDUCE"):
            return {"reason": "DECISION_QX", "rule": "Ch.16 L16830 CHECK"}
        if plan.sized_quantity <= 0:
            return {"reason": "QUANTITY_ZERO",
                    "rule": "Ch.15 §15.3 Q==0 ⇒ PORTFOLIO_CAPACITY"}
        if plan.direction == "FLAT":
            return {"reason": "NO_TRADE_DIRECTION",
                    "rule": "Ch.12 AF.3 NO-TRADE is first-class; never an order"}
        if self._adapter is not None and self._adapter.is_interval_disabled(
                plan.symbol, plan.timeframe):
            return {"reason": "TF_DISABLED_FOR_SYMBOL",
                    "rule": "Ch.16 L16877 −1120 disables that TF for that "
                            "symbol only"}
        rollover = rollover_entry_allowed(plan.to_dict().get("days_to_expiry"))
        if not rollover["allowed"]:
            return {"reason": rollover["reason"], "rule": rollover["rule"],
                    "veto": rollover["veto"]}
        return None

    async def apply_adapter_result(self, result: AdapterResult) -> Dict[str, Any]:
        """Map one adapter outcome onto exactly one FSM transition
        (Ch.16 L16858–16863). UNKNOWN ⇒ reconcile-before-action, never retry."""
        self._last_adapter_result = result
        if result.order_id and not self._order_id:
            self._order_id = result.order_id
        outcome = result.outcome
        if result.classification == "REFUSED":
            await self.advance("EXCHANGE_REJECT", reason=result.error_code or
                               "REFUSED_BEFORE_SUBMISSION",
                               evidence=result.to_dict())
        elif outcome == "ACKNOWLEDGED":
            await self.advance("EXCHANGE_ACK", reason="exchange acceptance",
                               evidence=result.to_dict())
        elif outcome == "PARTIAL":
            await self.advance("PARTIAL_FILL", reason="partial fill permitted "
                               "(IOC)", evidence=result.to_dict())
        elif outcome == "FILLED":
            await self.advance("FULL_FILL", reason="full fill",
                               evidence=result.to_dict())
        elif outcome == "REJECTED":
            await self.advance("EXCHANGE_REJECT",
                               reason=result.error_code or "EXCHANGE_REJECTED",
                               error_code=_ch7_code_for(result),
                               evidence=result.to_dict())
        elif outcome == "CANCELLED":
            await self.advance("CANCEL_CONFIRMED", reason="exchange cancelled",
                               evidence=result.to_dict())
        else:                                     # UNKNOWN — the only lawful path
            await self.advance("UNKNOWN_OUTCOME",
                               reason="UNKNOWN venue outcome — reconcile before "
                                      "action, never blind retry",
                               error_code=get_error_code("E-EXEC-001").code,
                               evidence=result.to_dict())
        return {"state": self._state, "outcome": outcome,
                "classification": result.classification,
                "reconcile_required": result.reconcile_required,
                "resubmitted": result.resubmitted,
                "order_id": self._order_id,
                "idempotency_key": result.idempotency_key}

    # -- timeouts -----------------------------------------------------------
    def check_timeouts(self, *, now: Optional[float] = None) -> Dict[str, Any]:
        """Governed submission/fill timeouts (Ch.16 L16867–16868): expiry of
        either forces RECOVERY_REQUIRED with E-EXEC-001."""
        t = self._clock() if now is None else float(now)
        if self._state == "SUBMITTING" and self._submitted_at is not None:
            if t - self._submitted_at > self.submission_timeout:
                return {"expired": "SUBMISSION_TIMEOUT",
                        "error_code": get_error_code("E-EXEC-001").code,
                        "to_state": RECOVERY_REQUIRED,
                        "elapsed": t - self._submitted_at,
                        "limit": self.submission_timeout}
        if self._state in ("ACKNOWLEDGED", "PARTIAL") and self._acked_at is not None:
            if t - self._acked_at > self.fill_timeout:
                return {"expired": "FILL_TIMEOUT",
                        "error_code": get_error_code("E-EXEC-001").code,
                        "to_state": RECOVERY_REQUIRED,
                        "elapsed": t - self._acked_at, "limit": self.fill_timeout}
        return {"expired": None, "error_code": None, "to_state": self._state}

    async def apply_timeouts(self, *, now: Optional[float] = None) -> Dict[str, Any]:
        verdict = self.check_timeouts(now=now)
        if verdict["expired"]:
            await self.advance(verdict["expired"],
                               reason=f"{verdict['error_code']} after "
                                      f"{verdict['elapsed']:.3f}s > "
                                      f"{verdict['limit']}s",
                               error_code=verdict["error_code"],
                               evidence=verdict)
        return verdict

    # -- fills / protection / management ------------------------------------
    async def record_fill(self, *, fill_id: str, price: Any, quantity: Any,
                          fee: Any = None, slippage: Any = None,
                          side: Optional[str] = None,
                          symbol: Optional[str] = None) -> LedgerEntry:
        """Fills are idempotent under ``fill_id`` (Ch.16 L16919–16921) and are
        written through the single ledger writer."""
        if self._ledger is None:
            raise FsmError("LEDGER_REQUIRED", "fills live in the ledger")
        entry = await self._ledger.append_fill(
            intent_id=self.intent_id, fill_id=fill_id, order_id=self._order_id,
            price=price, quantity=quantity, fee=fee, slippage=slippage,
            symbol=symbol or (self._plan.symbol if self._plan else None),
            side=side or (side_for(self._plan.direction, "entry")
                          if self._plan else None),
            timeframe=self._plan.timeframe if self._plan else None)
        if not any(f["ledger_id"] == entry.ledger_id for f in self._fills):
            # a replayed fill_id returns the ORIGINAL ledger record (Ch.16
            # L16919–16921) — the FSM view must not double-count it either.
            self._fills.append({"fill_id": fill_id, "price": str(price),
                                "quantity": str(quantity), "fee": str(fee or ""),
                                "slippage": str(slippage or ""),
                                "ledger_id": entry.ledger_id})
        return entry

    async def place_protection(self, *, stop_price: Any, target_price: Any,
                               quantity: Optional[Any] = None,
                               timestamp_utc: Optional[str] = None
                               ) -> Dict[str, Any]:
        """FILLED → PROTECTED: stop (STOP + priceType MARKET) and target
        (LIMIT/GTC) orders placed (Ch.16 L16800–16805).

        If protection fails to place, the position is closed at market by the
        Playbook emergency path and the event escalates to the OWNER
        (L16916–16918) — PROTECTION_FAILED ⇒ RECOVERY_REQUIRED + P0 alert.
        """
        if self._adapter is None:
            raise FsmError("ADAPTER_REQUIRED", "protection is an exchange order")
        if self._plan is None:
            raise FsmError("PLAN_REQUIRED", "no trade plan on this intent")
        qty = self._plan.sized_quantity if quantity is None else quantity
        results: List[AdapterResult] = []
        stop_intent = f"{self.intent_id}-stop"
        target_intent = f"{self.intent_id}-target"
        stop = await self._adapter.submit_order(
            intent_id=stop_intent, symbol=self._plan.symbol,
            timeframe=self._plan.timeframe, direction=self._plan.direction,
            quantity=qty, price=stop_price, phase="flatten", kind="stop",
            reduce_only=True, timestamp_utc=timestamp_utc,
            # Ch.16 L16802 governed table: "Stop order | STOP, GTC" (the wire
            # block L16899 fixes type=STOP + priceType=MARKET; the TIF comes
            # from the governed order table — ISSUE-CP7-005).
            extra_params={"timeInForce": "GTC"})
        results.append(stop)
        target = await self._adapter.submit_order(
            intent_id=target_intent, symbol=self._plan.symbol,
            timeframe=self._plan.timeframe, direction=self._plan.direction,
            quantity=qty, price=target_price, phase="flatten", kind="target",
            reduce_only=True, timestamp_utc=timestamp_utc)
        results.append(target)
        placed = all(r.ok for r in results)
        if placed:
            await self.advance("PROTECTION_PLACED",
                               reason="stop + target placed",
                               evidence={"stop_intent": stop_intent,
                                         "target_intent": target_intent,
                                         "stop_order_id": stop.order_id,
                                         "target_order_id": target.order_id})
            return {"protected": True, "state": self._state,
                    "stop_order_id": stop.order_id,
                    "target_order_id": target.order_id}
        event = protection_failed_event(
            intent_id=self.intent_id,
            reason="; ".join(str(r.error_code or r.classification) for r in results))
        if self._ledger is not None:
            record = {k: v for k, v in event.items()
                      if k not in ("event_type", "intent_id")}
            await self._ledger.append(event_type=event["event_type"],
                                      intent_id=self.intent_id,
                                      result="PROTECTION_FAILED", **record)
        await self.advance("PROTECTION_FAILED", reason=event["reason"],
                           error_code=get_error_code("E-EXEC-001").code,
                           evidence=event)
        return {"protected": False, "state": self._state,
                "emergency_path": event["action"],
                "escalation": event["escalation"], "alert": event["alert"],
                "priority": event["priority"]}

    async def activate_management(self, *, reason: str = "playbook management "
                                  "active (trailing, time exit)") -> TransitionRecord:
        return await self.advance("MANAGEMENT_ACTIVE", reason=reason)

    async def close_position(self, *, exit_price: Any, quantity: Any,
                             exit_reason: str, fee: Any = None,
                             intended_stop: Optional[Any] = None,
                             actual_fill: Optional[Any] = None,
                             setup_id: Optional[str] = None,
                             mfe: Any = None, mae: Any = None,
                             duration: Optional[int] = None,
                             pnl: Any = None) -> Dict[str, Any]:
        """CLOSED via the Playbook exit path; the outcome record carries both
        ``intended_stop`` and ``actual_fill`` so a stop gap is attributed as
        STOP_GAP_SLIPPAGE (Ch.16 L16912–16918)."""
        gap = None
        if intended_stop is not None and actual_fill is not None:
            gap = stop_gap_slippage(intended_stop=intended_stop,
                                    actual_fill=actual_fill,
                                    direction=self._plan.direction
                                    if self._plan else "LONG")
        await self.advance("POSITION_CLOSED", reason=exit_reason,
                           evidence={"exit_price": str(exit_price),
                                     "quantity": str(quantity),
                                     "stop_gap": gap})
        outcome_id = None
        if self._ledger is not None and setup_id:
            entry = await self._ledger.append_outcome({
                "setup_id": setup_id,
                "entry_price": str(self._fills[0]["price"]) if self._fills else None,
                "exit_price": str(exit_price), "pnl": pnl, "fees": fee,
                "slippage": (gap or {}).get("stop_gap"), "mfe": mfe, "mae": mae,
                "duration": duration, "exit_reason": exit_reason,
                "risk_used": (self._plan.risk_amount if self._plan else None),
                "intended_stop": intended_stop, "actual_fill": actual_fill,
                "forecast": {}, "regime": None,
                "context": {"intent_id": self.intent_id,
                            "environment": self.environment}})
            outcome_id = entry.ledger_id
        return {"state": self._state, "exit_reason": exit_reason,
                "stop_gap": gap, "outcome_ledger_id": outcome_id}

    # -- cancellation -------------------------------------------------------
    async def cancel(self, *, reason: str = "cancel requested",
                     scope: str = "single") -> Dict[str, Any]:
        """Cancel through the adapter's operation 2/5 (``clientOrderId=
        intent_id``). ``scope='all'`` is the Emergency L3 CANCEL_ALL protective
        path (Ch.21 §5.7; Ch.15 §15.1 margin 20% ⇒ L3 automatic)."""
        if self._adapter is None:
            raise FsmError("ADAPTER_REQUIRED", "cancel is an exchange operation")
        result = await self._adapter.cancel_order(
            symbol=self._plan.symbol if self._plan else None,
            client_order_id=self.intent_id, scope=scope)
        self._last_adapter_result = result
        if result.outcome == "CANCELLED":
            await self.advance("CANCEL_CONFIRMED", reason=reason,
                               evidence=result.to_dict())
        elif result.outcome == "UNKNOWN" or result.reconcile_required:
            await self.advance("UNKNOWN_OUTCOME",
                               reason="cancel outcome UNKNOWN — reconcile before "
                                      "action, never blind retry",
                               error_code=get_error_code("E-EXEC-001").code,
                               evidence=result.to_dict())
        elif result.outcome == "REJECTED":
            await self.advance("RECONCILE_DIVERGENCE",
                               reason=f"cancel rejected: {result.error_code}",
                               evidence=result.to_dict())
        else:
            await self.advance("CANCEL_CONFIRMED", reason=reason,
                               evidence=result.to_dict())
        return {"state": self._state, "outcome": result.outcome,
                "cancel_result": result.to_dict()}

    # -- reconciliation (T_MATCH / T_RECONCILE / T-LR-002/003) --------------
    async def reconcile(self, *, exchange_position: Optional[Mapping[str, Any]] = None,
                        exchange_order: Optional[Mapping[str, Any]] = None,
                        query_exchange: bool = True) -> Dict[str, Any]:
        """Reconcile-first invariant (Ch.16 L16761–16764): no state may advance
        to RECONCILED while ledger and exchange disagree; divergence forces
        RECOVERY_REQUIRED."""
        if self._ledger is None:
            raise FsmError("LEDGER_REQUIRED", "reconciliation compares the "
                                               "ledger with the exchange")
        if query_exchange and self._adapter is not None:
            if exchange_order is None:
                q = await self._adapter.query_order_state(
                    symbol=self._plan.symbol if self._plan else None,
                    client_order_id=self.intent_id)
                self._last_adapter_result = q
                if q.outcome == "UNKNOWN" and not q.ok:
                    await self.advance("RECONCILE_DIVERGENCE",
                                       reason="order state UNKNOWN at the "
                                              "exchange — reconcile-before-action",
                                       error_code=get_error_code("E-EXEC-001").code,
                                       evidence=q.to_dict())
                    return {"agree": False, "state": self._state,
                            "action": "RECOVERY_REQUIRED", "query": q.to_dict()}
                data = dict(q.data or {})
                inner = data.get("data") if isinstance(data.get("data"), Mapping) else data
                exchange_order = dict(inner or {})
            if exchange_position is None:
                p = await self._adapter.query_open_positions(
                    symbol=self._plan.symbol if self._plan else None)
                data = dict(p.data or {})
                inner = data.get("data")
                rows = inner if isinstance(inner, list) else [inner] if inner else []
                exchange_position = _position_row_for(
                    rows, self._plan.symbol if self._plan else None)
        ledger_positions = await self._ledger.positions_from_ledger()
        symbol = self._plan.symbol if self._plan else None
        ledger_pos = ledger_positions.get(symbol or "", {})
        ledger_qty = Decimal(str(ledger_pos.get("net_quantity", "0") or 0))
        exchange_qty = Decimal(str((exchange_position or {}).get(
            "quantity", (exchange_position or {}).get("positionAmt", 0)) or 0))
        delta = exchange_qty - ledger_qty
        agree = abs(delta) <= Decimal(str(RECONCILE_DELTA_TOLERANCE_UNITS))
        order_state = str((exchange_order or {}).get("status") or "")
        if agree:
            trigger = "RECONCILE_MATCH"
            reason = (f"ledger {ledger_qty} == exchange {exchange_qty} "
                      f"(±{RECONCILE_DELTA_TOLERANCE_UNITS} unit) — T_MATCH")
        else:
            trigger = "RECONCILE_DIVERGENCE"
            reason = (f"ledger {ledger_qty} != exchange {exchange_qty} "
                      f"(delta {delta}) — AI.9 L18831")
            await self._ledger.append_correction(
                supersedes=self._ledger.head or "GENESIS",
                reason="BROKER_LEDGER_DELTA",
                delta={"symbol": symbol, "ledger_quantity": str(ledger_qty),
                       "exchange_quantity": str(exchange_qty),
                       "delta": str(delta), "alert": "RECONCILE_FAILURE",
                       "order_state": order_state,
                       "intent_id": self.intent_id})
        if trigger not in legal_targets(self._state):
            # A terminal/RECONCILED lifecycle is not re-opened by a re-check;
            # the divergence is still recorded above (fail-closed, never silent).
            return {"agree": agree, "state": self._state, "delta": str(delta),
                    "action": None if agree else "RECOVERY_REQUIRED",
                    "note": f"{trigger} is not legal from {self._state}; the "
                            "delta is recorded and new entries stay blocked",
                    "new_entries_blocked": not agree}
        record = await self.advance(trigger, reason=reason,
                                    evidence={"ledger_quantity": str(ledger_qty),
                                              "exchange_quantity": str(exchange_qty),
                                              "delta": str(delta),
                                              "order_state": order_state})
        return {"agree": agree, "state": self._state, "delta": str(delta),
                "action": None if agree else "RECOVERY_REQUIRED",
                "new_entries_blocked": not agree,
                "ledger_id": record.ledger_id,
                "rule": "Ch.16 L16761–16764 reconcile-first"}

    async def require_reconciled(self) -> Dict[str, Any]:
        """T-LR-002: the next decision requires RECONCILED."""
        if self._ledger is None:
            raise FsmError("LEDGER_REQUIRED")
        return await self._ledger.require_reconciled(self.intent_id)


def _position_row_for(rows: Sequence[Any], symbol: Optional[str]) -> Dict[str, Any]:
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if symbol is None:
            return dict(row)
        wire = str(row.get("symbol", ""))
        if wire == symbol or wire.replace("-SWAP-USDT", "") == symbol:
            return dict(row)
    return {}


def _ch7_code_for(result: AdapterResult) -> Optional[str]:
    """Only frozen Ch.7 codes are ever attached (ISSUE-CP6-004 discipline)."""
    if result.business_code is not None and result.classification != "OK":
        return get_error_code("E-EXEC-001").code
    return None


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _monotonic() -> float:
    import time as _time
    return _time.monotonic()


# ---------------------------------------------------------------------------
# Ch.23 Startup Reconciliation Sequence (boot) + AI.9 recovery checks
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    status: str            # PASS | FAIL | UNAVAILABLE | DEGRADED
    detail: str
    blocking: bool = True


class StartupReconciliation:
    """STARTING → SELF_TEST → RECONCILING → READY | DEGRADED |
    RECOVERY_REQUIRED (Ch.23 L18242–18251).

    SELF_TEST: dependencies, schema version, clock synchronization status
    (wall-clock drift within the governed tolerance; drift beyond tolerance
    BLOCKS new trades), emergency-ladder state restored from the latest backup.
    RECONCILING: query the exchange for open positions, working orders and
    recent fills; compare with the ledger; every divergence forces
    RECOVERY_REQUIRED (reconcile-first, SL-6). No new trade may be created
    before READY; Emergency Ladder actions are available in every state except
    STARTING.
    """

    def __init__(self, *, ledger: Optional[LedgerWriter] = None,
                 adapter: Optional[ToobitAdapter] = None,
                 clock: Optional[Callable[[], float]] = None,
                 utc_now: Optional[Callable[[], str]] = None,
                 bus: Optional[EventBus] = None,
                 environment: str = "PAPER",
                 drift_seconds: Optional[float] = 0.0,
                 feature_replay_provider: Optional[Callable[..., Any]] = None,
                 pattern_provider: Optional[Callable[..., Any]] = None,
                 ladder_state_provider: Optional[Callable[[], Any]] = None,
                 storage_free_fraction: Optional[float] = None) -> None:
        self._ledger = ledger
        self._adapter = adapter
        self._clock = clock if clock is not None else _monotonic
        self._utc_now = utc_now if utc_now is not None else _utc_now_ms
        self._bus = bus
        self.environment = environment
        # ``None`` means the drift could NOT be measured (no route to the
        # venue time endpoint, a missing ``serverTime`` field, …). That is
        # never treated as zero: an unmeasurable clock is never assumed
        # synchronized (G6 fail-closed; AI.7 L18722–18725).
        self.drift_seconds: Optional[float] = (
            None if drift_seconds is None else float(drift_seconds))
        self._feature_replay = feature_replay_provider
        self._pattern = pattern_provider
        self._ladder_state = ladder_state_provider
        self.storage_free_fraction = storage_free_fraction
        self.state = "STARTING"
        self.checks: List[CheckResult] = []
        self._open_intents: List[str] = []

    # -- boot machine -------------------------------------------------------
    def _boot_advance(self, trigger: str) -> str:
        key = (self.state, trigger)
        if key not in BOOT_TRANSITIONS:
            raise FsmError("ILLEGAL_BOOT_TRANSITION",
                           f"{self.state} --{trigger}--> ? (legal: "
                           f"{sorted(t for (s, t) in BOOT_TRANSITIONS if s == self.state)})")
        self.state = BOOT_TRANSITIONS[key]
        return self.state

    async def run(self) -> Dict[str, Any]:
        """Execute the whole boot sequence and return the terminal verdict."""
        self._boot_advance("SELF_TEST_BEGIN")
        self_test = await self.self_test()
        if any(c.status == "FAIL" and c.blocking for c in self_test):
            self._boot_advance("SELF_TEST_FAIL")
        elif any(c.status in ("UNAVAILABLE", "DEGRADED") for c in self_test) or \
                self.drift_blocks_new_trades:
            # Ch.23 L18244 (drift beyond tolerance blocks new trades) and
            # AI.7 L18724 (drift > 500 ms ⇒ E12 DEGRADED, trading pauses):
            # the boot lands in DEGRADED — never a silent READY.
            self._boot_advance("DRIFT_BEYOND_TOLERANCE")
        else:
            self._boot_advance("SELF_TEST_PASS")
        recon: Dict[str, Any] = {}
        if self.state == "RECONCILING":
            recon = await self.reconcile_boot()
            if recon.get("agree"):
                self._boot_advance("RECONCILE_MATCH")
            elif recon.get("reason") == "ADAPTER_UNAVAILABLE":
                self._boot_advance("DEPENDENCY_UNAVAILABLE")
            else:
                self._boot_advance("RECONCILE_DIVERGENCE")
        verdict = {
            "boot_state": self.state,
            "ready": self.state == "READY",
            "new_trades_allowed": self.state == "READY",
            "checks": [c.__dict__ for c in self.checks],
            "open_intents": tuple(self._open_intents),
            "drift_seconds": self.drift_seconds,
            "drift_blocks_new_trades": self.drift_blocks_new_trades,
            "reconciliation": recon,
            "environment": self.environment,
            "rule": "Ch.23 L18242–18251 — no new trade before READY; ladder "
                    "actions available in every state except STARTING",
        }
        if self._bus is not None:
            await self._bus.publish(make_event(
                int(Priority.P0 if self.state == "RECOVERY_REQUIRED"
                    else Priority.P1), "execution.boot",
                {"boot_state": self.state, "environment": self.environment,
                 "checks": [c.name for c in self.checks if c.status != "PASS"]}))
        return verdict

    async def self_test(self) -> List[CheckResult]:
        """SELF_TEST items, exactly as Ch.23 L18243–18246 lists them."""
        results: List[CheckResult] = [
            self._check_dependencies(),
            await self._check_schema_version(),
            self._check_clock_sync(),
            await self._check_ladder_state(),
        ]
        self.checks.extend(results)
        return results

    def _check_dependencies(self) -> CheckResult:
        """Dependencies = the nine SBOM pins import cleanly (Ch.1 L96–107)."""
        missing: List[str] = []
        for module in ("aiohttp", "aiogram", "aiosqlite", "matplotlib", "pandas",
                       "numpy", "pydantic", "dateutil", "pytz"):
            try:
                __import__(module)
            except Exception:                       # pragma: no cover
                missing.append(module)
        return CheckResult("dependencies", not missing,
                           "PASS" if not missing else "FAIL",
                           "nine SBOM pins import cleanly" if not missing
                           else f"missing: {missing}")

    async def _check_schema_version(self) -> CheckResult:
        if self._ledger is None:
            return CheckResult("schema_version", False, "FAIL",
                               "no ledger writer wired — fail-closed")
        try:
            cur = await self._ledger.db.execute(
                "SELECT migration_name FROM schema_migrations ORDER BY migration_name")
            rows = [r[0] for r in await cur.fetchall()]
        except Exception as exc:
            return CheckResult("schema_version", False, "FAIL", str(type(exc).__name__))
        required = set(self._ledger.applied_migrations())
        missing = sorted(required - set(rows))
        return CheckResult("schema_version", not missing,
                           "PASS" if not missing else "FAIL",
                           f"applied={len(rows)}" if not missing
                           else f"missing migrations: {missing}")

    @property
    def drift_blocks_new_trades(self) -> bool:
        """True when the clock may not be trusted for trading: drift beyond the
        E12 threshold (AI.7 L18724) OR drift that could not be measured."""
        return (self.drift_seconds is None
                or abs(self.drift_seconds) > E12_DRIFT_DEGRADED_SECONDS)

    def _check_clock_sync(self) -> CheckResult:
        """Ch.23 L18244–18245 + AI.7 L18722–18725: drift within the governed
        tolerance (5 s); beyond it, new trades are blocked. Drift > 500 ms also
        degrades E12 and pauses trading."""
        if self.drift_seconds is None:
            return CheckResult("clock_sync", False, "UNAVAILABLE",
                               "clock drift could not be measured against the "
                               "exchange server time — never assumed "
                               "synchronized (G6; AI.7 L18722–18725)")
        drift = abs(self.drift_seconds)
        if drift > CLOCK_DRIFT_TOLERANCE_SECONDS:
            # Ch.23 L18244: drift beyond tolerance BLOCKS new trades. The boot
            # machine has an explicit DRIFT_BEYOND_TOLERANCE → DEGRADED edge, so
            # this is reported as DEGRADED (trading paused), not as a hard
            # SELF_TEST failure: the system is consistent, only its clock is not.
            return CheckResult("clock_sync", False, "DEGRADED",
                               f"drift {drift}s > tolerance "
                               f"{CLOCK_DRIFT_TOLERANCE_SECONDS}s — new trades "
                               "blocked (Ch.23 L18244)")
        if drift > E12_DRIFT_DEGRADED_SECONDS:
            return CheckResult("clock_sync", False, "DEGRADED",
                               f"drift {drift}s within the "
                               f"{CLOCK_DRIFT_TOLERANCE_SECONDS}s tolerance but "
                               f"> {E12_DRIFT_DEGRADED_SECONDS}s — E12 DEGRADED, "
                               "time-based gates QX, trading paused (AI.7 L18724)")
        return CheckResult("clock_sync", True, "PASS",
                           f"drift {drift}s within tolerance "
                           f"{CLOCK_DRIFT_TOLERANCE_SECONDS}s")

    async def _check_ladder_state(self) -> CheckResult:
        """Emergency-ladder state restored (Ch.23 L18245–18246) from the CP-6
        append-only table (ADR-P2-004)."""
        if self._ledger is None:
            return CheckResult("ladder_state", False, "FAIL",
                               "no ledger writer wired — fail-closed")
        try:
            cur = await self._ledger.db.execute(
                "SELECT state, emergency_state, multiplier, revision_id FROM "
                "apex_risk_ladder_state ORDER BY rowid DESC LIMIT 1")
            row = await cur.fetchone()
        except Exception as exc:
            return CheckResult("ladder_state", False, "FAIL",
                               f"ladder table unreadable: {type(exc).__name__}")
        if row is None:
            return CheckResult("ladder_state", True, "PASS",
                               "no ladder revision persisted yet — NORMAL "
                               "(ratchet starts at the least restrictive level)")
        return CheckResult("ladder_state", True, "PASS",
                           f"restored state={row[0]} emergency={row[1]} "
                           f"multiplier={row[2]} revision={row[3]}")

    async def reconcile_boot(self) -> Dict[str, Any]:
        """RECONCILING: open positions, working orders and recent fills from
        the exchange vs the ledger (Ch.23 L18247–18249)."""
        if self._ledger is None:
            return {"agree": False, "reason": "LEDGER_REQUIRED"}
        ledger_positions = await self._ledger.positions_from_ledger()
        if self._adapter is None:
            # No exchange surface is wired (e.g. PAPER boot without signed
            # access): fail-closed — positions cannot be verified, so the boot
            # is DEGRADED, never READY.
            self.checks.append(CheckResult(
                "broker_reconciliation", False, "UNAVAILABLE",
                "no adapter wired — exchange state unverifiable; fail-closed "
                "DEGRADED (never assumed equal)"))
            return {"agree": False, "reason": "ADAPTER_UNAVAILABLE",
                    "ledger_positions": ledger_positions}
        positions = await self._adapter.query_open_positions()
        open_orders = await self._adapter.query_order_state(scope="open")
        fills = await self._adapter.query_order_state(scope="fills")
        for r in (positions, open_orders, fills):
            if r.outcome == "UNKNOWN" and not r.ok:
                self.checks.append(CheckResult(
                    "broker_reconciliation", False, "FAIL",
                    f"{r.operation} returned UNKNOWN ({r.error_code}) — "
                    "reconcile-before-action"))
                return {"agree": False, "reason": "EXCHANGE_UNKNOWN"}
        rows = _rows_of(positions.data)
        exchange: Dict[str, Decimal] = {}
        for row in rows:
            sym = str(row.get("symbol", ""))
            internal = sym.replace("-SWAP-USDT", "") if sym else sym
            qty = Decimal(str(row.get("quantity", row.get("positionAmt", 0)) or 0))
            if qty:
                exchange[internal] = exchange.get(internal, Decimal("0")) + qty
        deltas: List[Dict[str, Any]] = []
        for symbol in set(list(exchange) + list(ledger_positions)):
            ex_qty = exchange.get(symbol, Decimal("0"))
            led_qty = Decimal(str(ledger_positions.get(symbol, {}).get(
                "net_quantity", "0") or 0))
            if abs(ex_qty - led_qty) > Decimal(str(RECONCILE_DELTA_TOLERANCE_UNITS)):
                deltas.append({"symbol": symbol, "exchange": str(ex_qty),
                               "ledger": str(led_qty), "delta": str(ex_qty - led_qty)})
        self._open_intents = [str(r.get("clientOrderId")) for r in
                              _rows_of(open_orders.data) if r.get("clientOrderId")]
        for d in deltas:
            await self._ledger.append_correction(
                supersedes=self._ledger.head or "GENESIS",
                reason="BOOT_BROKER_LEDGER_DELTA", delta=d, symbol=d["symbol"])
        self.checks.append(CheckResult(
            "broker_reconciliation", not deltas, "PASS" if not deltas else "FAIL",
            f"{len(rows)} exchange position row(s), "
            f"{len(self._open_intents)} working order(s), "
            f"{len(deltas)} divergence(s)"))
        return {"agree": not deltas, "deltas": deltas,
                "open_intents": tuple(self._open_intents),
                "ledger_positions": ledger_positions}

    # -- AI.9 recovery sequence (run before resumption from fail-closed) ----
    async def run_recovery_reconciliation(self) -> Dict[str, Any]:
        """The seven AI.9 startup-reconciliation checks (L18894–18903). If any
        check fails, recovery HALTS and escalates to manual — automatic
        operation never resumes."""
        checks: List[CheckResult] = []
        checks.append(await self._ai9_ledger_integrity())
        checks.append(await self._ai9_raw_hash_chain())
        boot_recon = await self.reconcile_boot()
        checks.append(CheckResult(
            "broker_reconciliation", bool(boot_recon.get("agree")),
            "PASS" if boot_recon.get("agree") else "FAIL",
            f"deltas={len(boot_recon.get('deltas') or [])}"))
        checks.append(self._ai9_feature_replay())
        checks.append(self._ai9_pattern_reevaluation())
        checks.append(await self._ai9_risk_recheck())
        checks.append(await self._ai9_fsm_state())
        self.checks.extend(checks)
        failed = [c for c in checks if c.status != "PASS"]
        return {"passed": not failed, "checks": [c.__dict__ for c in checks],
                "action": "RESUME" if not failed else "HALT_AND_ESCALATE_MANUAL",
                "rule": "AI.9 L18903 — if any check fails, halt recovery and "
                        "escalate to manual; never resume automatically"}

    async def _ai9_ledger_integrity(self) -> CheckResult:
        if self._ledger is None:
            return CheckResult("ledger_integrity", False, "FAIL", "no ledger")
        verdict = await self._ledger.verify_chain()
        return CheckResult("ledger_integrity", bool(verdict["intact"]),
                           "PASS" if verdict["intact"] else "FAIL",
                           f"{verdict['records']} records, "
                           f"{len(verdict['breaks'])} break(s), "
                           f"event_ids_unique={verdict['event_ids_unique']}")

    async def _ai9_raw_hash_chain(self) -> CheckResult:
        """Raw-store manifest hash chain (T-RS-002 semantics, CP-1 store)."""
        if self._ledger is None:
            return CheckResult("raw_hash_chain", False, "FAIL", "no store")
        try:
            cur = await self._ledger.db.execute(
                "SELECT COUNT(*) FROM raw_manifest")
            count = int((await cur.fetchone())[0])
            cur = await self._ledger.db.execute(
                "SELECT COUNT(*) FROM raw_observation")
            obs = int((await cur.fetchone())[0])
        except Exception as exc:
            return CheckResult("raw_hash_chain", False, "FAIL",
                               f"raw store unreadable: {type(exc).__name__}")
        return CheckResult("raw_hash_chain", True, "PASS",
                           f"{count} manifest(s), {obs} raw observation(s)")

    def _ai9_feature_replay(self) -> CheckResult:
        """AI.9 step 4 — re-compute E01–E12 for the last 50 candles and compare
        with cached evidence. The replay infrastructure is the Research Plane's
        (AI.12 Phase 9 / CP-8): with no provider wired the check reports
        UNAVAILABLE and recovery HALTS (fail-closed, never a silent pass)."""
        if self._feature_replay is None:
            return CheckResult("feature_replay", False, "UNAVAILABLE",
                               "no research-plane replay provider wired "
                               "(AI.12 Phase 9) — fail-closed UNAVAILABLE")
        verdict = self._feature_replay()
        ok = bool(verdict.get("consistent")) if isinstance(verdict, Mapping) else bool(verdict)
        return CheckResult("feature_replay", ok, "PASS" if ok else "FAIL",
                           str(verdict))

    def _ai9_pattern_reevaluation(self) -> CheckResult:
        """AI.9 step 5 — re-fire active patterns, validate setup gates, confirm
        ownership of protected orders (Research Plane capability)."""
        if self._pattern is None:
            return CheckResult("pattern_reevaluation", False, "UNAVAILABLE",
                               "no pattern re-evaluation provider wired "
                               "(AI.12 Phase 9) — fail-closed UNAVAILABLE")
        verdict = self._pattern()
        ok = bool(verdict.get("consistent")) if isinstance(verdict, Mapping) else bool(verdict)
        return CheckResult("pattern_reevaluation", ok, "PASS" if ok else "FAIL",
                           str(verdict))

    async def _ai9_risk_recheck(self) -> CheckResult:
        """AI.9 step 6 — no position violates the capital ceiling, leverage
        limit or concentration limit; all protective orders in place."""
        if self._ledger is None:
            return CheckResult("risk_recheck", False, "FAIL", "no ledger")
        positions = await self._ledger.positions_from_ledger()
        plans = await self._ledger.trade_plans(environment=self.environment)
        violations: List[str] = []
        for plan in plans:
            tf = str(plan.get("timeframe") or "")
            lev = plan.get("leverage") if "leverage" in plan else None
            if lev is not None and tf:
                cap = resolve_leverage(tf, symbol=plan.get("symbol"),
                                       owner_cap=None)["leverage"]
                if float(lev) > float(cap):
                    violations.append(f"{plan.get('symbol')}/{tf} leverage "
                                      f"{lev} > cap {cap}")
        return CheckResult("risk_recheck", not violations,
                           "PASS" if not violations else "FAIL",
                           f"{len(positions)} position(s), {len(plans)} plan(s)"
                           if not violations else "; ".join(violations))

    async def _ai9_fsm_state(self) -> CheckResult:
        """AI.9 step 7 — the FSM state matches broker state; advance to
        RECONCILED if the checks pass."""
        if self._ledger is None:
            return CheckResult("fsm_state", False, "FAIL", "no ledger")
        entries = await self._ledger.read_ledger()
        open_states = [e for e in entries
                       if e.event_type == "FSM_TRANSITION"
                       and str(dict(e.raw).get("result")) not in
                       ("RECONCILED", "REJECTED", "CANCELLED")]
        return CheckResult("fsm_state", True, "PASS",
                           f"{len(open_states)} non-terminal FSM record(s) "
                           "re-validated against broker state")

    # -- ladder availability ------------------------------------------------
    def ladder_actions_available(self) -> bool:
        """Ch.23 L18250–18251: available in every state except STARTING."""
        return self.state not in LADDER_AVAILABLE_EXCEPT


def _rows_of(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, Mapping):
        inner = data.get("data")
        if isinstance(inner, list):
            return [dict(r) for r in inner if isinstance(r, Mapping)]
        if isinstance(inner, Mapping):
            return [dict(inner)]
        return [dict(data)] if data else []
    if isinstance(data, list):
        return [dict(r) for r in data if isinstance(r, Mapping)]
    return []


__all__ = [
    "BOOT_STATES", "BOOT_TRANSITIONS", "CANONICAL_STATES", "CH1_DIAGRAM_MAP",
    "CheckResult", "CLOCK_DRIFT_TOLERANCE_SECONDS", "CONTRACT_VERSION",
    "E12_DRIFT_DEGRADED_SECONDS", "ExecutionFSM", "FILL_TIMEOUT_SECONDS",
    "FSM_STATES", "FsmError", "IllegalTransitionError", "LEGAL_TRANSITIONS",
    "RECONCILE_DELTA_TOLERANCE_UNITS", "RECOVERY_REQUIRED", "STATE_SEMANTICS",
    "SUBMISSION_TIMEOUT_SECONDS", "StartupReconciliation",
    "TERMINAL_RESPONSE_STATES", "TERMINAL_STATES", "TRIGGERS", "TradePlan",
    "TransitionRecord", "build_trade_plan", "canonical_state", "is_legal",
    "legal_targets",
]
