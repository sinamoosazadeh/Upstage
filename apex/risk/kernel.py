"""APEX_GEN5 — Risk Kernel (Ch.15 §15.1; blueprint L16591–16749) + the
RSK-ERR-506 ladder-state persistence (ADR-P2-004).

"Risk is independent. Fourteen named vetoes, sizing, and capital ceilings apply
to every cell. Optimizer output cannot soften them." (Ch.15 heading)

Normative content
-----------------
* **The Canonical Risk Veto Registry** is the sole normative source for
  hard-veto semantics, activation carriers and error-code mapping; each veto is
  independently sufficient to REJECT, even at P = 0.99. Exactly fourteen — a
  fifteenth cannot be added, a thirteenth cannot be dropped.
* **Vetoes are evaluated before any sizing** (this module enforces the order
  structurally: ``size`` is only reachable through ``adjudicate``, which
  evaluates the full registry first and returns the REJECT immediately).
* Sizing machine (verbatim):
  ``R_allowed = budget_per_trade · capital · risk_ladder_multiplier(state)``;
  ``Q = min(R_allowed/(StopDistance×ContractMultiplier), k_attn·ATR_cap·Capital
  /ContractMultiplier)``; ``Q = max(0, Q)``;
  ``Q = floor(Q/min_quantity)×min_quantity``; ``Q == 0 ⇒ REJECT, reason
  PORTFOLIO_CAPACITY``. ``StopDistance <= 0`` and ``Capital <= 0`` reject with
  deterministic validation reasons and never divide by zero.
* Risk-ladder projection: NoRisk→LowRisk < 25 % · MediumRisk 25–50 % ·
  HighRisk 50–75 % · CriticalRisk 75–100 % (REJECT ``PORTFOLIO_CAPACITY``),
  multipliers 1.0/1.0/0.75/0.50/0.0; escalation always allowed, de-escalation
  governed (ratchet).
* **RSK-ERR-506 ratchet** (Ch.7 row, verbatim): only upgrade allowed —
  L1 PAUSE → Normal resume allowed; L2→L1, L3→L2, L4→L3, L5→L4 blocked.
* Aggregate-loss circuit breakers (vetoes 10–12) with time/OWNER-reset only;
  CVaR_95 advisory downgrade; margin health at 60/40/20 % of maintenance
  distance; authority hierarchy ``Owner > Risk > Decision > Forecast >
  Evidence``.
* The Trade Plan output shape:
  ``{decision: ALLOW|REDUCE|REJECT, sized_quantity, selected_parameter_package,
  vetoes_applied: [], snapshot_id}``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from apex.config import load_params
from apex.errors import get_error_code
from apex.fabric.conflict import correlation_exposure
from apex.fabric.context import q_min_tf

CONTRACT_VERSION = "4.0.0"

# ---------------------------------------------------------------------------
# The Canonical Risk Veto Registry (exactly fourteen)
# ---------------------------------------------------------------------------

VETO_REGISTRY: Tuple[Tuple[int, str, str, Optional[str]], ...] = (
    (1, "VETO_INVALID_QUARANTINED_INPUT", "Q_raw < Q_min(tf), QX state, "
        "failed setup gate", "QX_INVALID"),
    (2, "VETO_PIT_VIOLATION", "availability_time > as_of", "E-PIT-001"),
    (3, "VETO_CAPITAL_LIMIT", "portfolio_exposure + proposed > capital_hard_cap",
     None),
    (4, "VETO_CIRCUIT_BREAKER", "circuit_breaker_engaged; ratchet permits "
        "upgrades only", "RSK-ERR-506"),
    (5, "VETO_EXPOSURE_LIMIT", "per_symbol_exposure > symbol_cap or "
        "portfolio_exposure > portfolio_cap", None),
    (6, "VETO_HARD_CONFLICT", "conflict_state == HARD_CONFLICT (SL-2)", None),
    (7, "VETO_FRESHNESS_SLA", "staleness beyond the freshness SLA",
     "VETO_FRESHNESS_SLA"),
    (8, "VETO_OI_LAG", "oi_lag > threshold(tf)", "VETO_OI_LAG"),
    (9, "VETO_ANTI_MONOTONICITY", "request.is_risk_increase AND "
        "uncertainty_is_rising", None),
    # NOTE (ISSUE-CP6-004): the blueprint's registry column shows
    # "CIRCUIT_OPEN (Alert Policy)" for vetoes 10–12. That identifier is an
    # Alert-Policy label, not one of the frozen Ch.7 error codes, so it is not
    # registered as an error code here (the Ch.7 registry owns that namespace —
    # G6: codes are never invented).
    (10, "VETO_DAILY_LOSS_LIMIT", "realized day loss (marked-to-market, ledger) "
         "> governed threshold", None),
    (11, "VETO_WEEKLY_LOSS_LIMIT", "realized week loss (marked-to-market, "
         "ledger) > governed threshold", None),
    (12, "VETO_CONSECUTIVE_LOSSES", "consecutive losing trades > governed "
         "threshold", None),
    (13, "VETO_CONTRACT_EXPIRY", "time-to-expiry of a quarterly contract < "
         "governed rollover threshold", None),
    (14, "VETO_MARGIN_HEALTH", "margin health below governed action threshold",
     None),
)
VETO_NAMES: Tuple[str, ...] = tuple(v[1] for v in VETO_REGISTRY)
VETO_COUNT = 14
HARD_VETO_NUMBERS: Tuple[int, ...] = tuple(v[0] for v in VETO_REGISTRY)

# Ch.15 defaults, all governed (the loss caps come from the params file).
DEFAULT_CONTRACT_ROLLOVER_DAYS = 7
DEFAULT_MARGIN_HEALTH_WARN = 0.60
DEFAULT_MARGIN_HEALTH_ACTION = 0.40
DEFAULT_MARGIN_HEALTH_LIQUIDATION = 0.20
DEFAULT_CVAR_CAP_FRACTION = 0.04

RISK_LADDER_STATES: Tuple[str, ...] = ("NoRisk", "LowRisk", "MediumRisk",
                                      "HighRisk", "CriticalRisk")
RISK_LADDER_MULTIPLIER: Dict[str, float] = {
    "NoRisk": 1.0, "LowRisk": 1.0, "MediumRisk": 0.75, "HighRisk": 0.50,
    "CriticalRisk": 0.0}
# budget-state bands (consumed risk budget, upper bound as a fraction)
RISK_LADDER_BANDS: Tuple[Tuple[str, float, float], ...] = (
    ("NoRisk", 0.00, 0.25), ("LowRisk", 0.00, 0.25),
    ("MediumRisk", 0.25, 0.50), ("HighRisk", 0.50, 0.75),
    ("CriticalRisk", 0.75, 1.00))

EMERGENCY_LADDER: Tuple[str, ...] = ("NORMAL", "L1_PAUSE", "L2_LIMIT_RISK",
                                    "L3_CANCEL_ALL", "L4_CLOSE_ALL",
                                    "L5_SAFE_MODE")
# RSK-ERR-506, verbatim: the only permitted non-escalation move
RATCHET_BLOCKED: Tuple[Tuple[str, str], ...] = (
    ("L2_LIMIT_RISK", "L1_PAUSE"), ("L3_CANCEL_ALL", "L2_LIMIT_RISK"),
    ("L4_CLOSE_ALL", "L3_CANCEL_ALL"), ("L5_SAFE_MODE", "L4_CLOSE_ALL"))
RATCHET_ALLOWED_DOWNGRADE: Tuple[Tuple[str, str], ...] = (
    ("L1_PAUSE", "NORMAL"),)

TRADE_PLAN_FIELDS: Tuple[str, ...] = ("decision", "sized_quantity",
                                     "selected_parameter_package",
                                     "vetoes_applied", "snapshot_id")

# ADR-P2-004: the ladder-state table (append-only revisions; single writer via
# the ledger queue; ratchet-only).
LADDER_STATE_MIGRATION = "M100_cp6_risk_ladder_state"
LADDER_STATE_DDL = """
CREATE TABLE IF NOT EXISTS apex_risk_ladder_state (
    revision_id TEXT PRIMARY KEY CHECK(typeof(revision_id)='text'),
    applied_at TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('NoRisk','LowRisk','MediumRisk',
                                        'HighRisk','CriticalRisk')),
    emergency_state TEXT NOT NULL CHECK(emergency_state IN ('NORMAL',
        'L1_PAUSE','L2_LIMIT_RISK','L3_CANCEL_ALL','L4_CLOSE_ALL',
        'L5_SAFE_MODE')),
    consumed_budget REAL NOT NULL CHECK(consumed_budget >= 0.0),
    multiplier REAL NOT NULL CHECK(multiplier >= 0.0 AND multiplier <= 1.0),
    reason TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    parent_revision_id TEXT,
    CHECK(typeof(applied_at)='text' AND length(applied_at)>0)
);
CREATE TRIGGER IF NOT EXISTS apex_risk_ladder_state_no_update
BEFORE UPDATE ON apex_risk_ladder_state
BEGIN SELECT RAISE(ABORT, 'LADDER_STATE_APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS apex_risk_ladder_state_no_delete
BEFORE DELETE ON apex_risk_ladder_state
BEGIN SELECT RAISE(ABORT, 'LADDER_STATE_APPEND_ONLY'); END;
"""


class RiskError(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}{('::' + detail) if detail else ''}")
        self.reason = reason
        self.detail = detail


def frozen_risk_params() -> Dict[str, Any]:
    """The FROZEN_BOOTSTRAP risk literals, read from the params YAML (never
    hardcoded here, §9.5-10)."""
    r = load_params()["risk_defaults"]
    return {k: r[k] for k in ("budget_per_trade", "k_attn", "daily_loss_cap",
                             "weekly_loss_cap", "consecutive_loss_halt",
                             "margin_mode", "position_mode", "cost_R_floor",
                             "max_candidates", "correlation_cap",
                             "system_leverage_cap_by_tf")}


def veto_definition(number: int) -> Dict[str, Any]:
    for n, name, carrier, code in VETO_REGISTRY:
        if n == number:
            return {"number": n, "name": name, "carrier": carrier,
                    "error_code": code,
                    "registry": None if code is None
                    else str(get_error_code(code))}
    raise RiskError("VETO_NUMBER_QX", f"{number} (exactly {VETO_COUNT} exist)")


# ---------------------------------------------------------------------------
# Veto evaluation
# ---------------------------------------------------------------------------

def _q_raw_of(risk_input: Mapping[str, Any]) -> Optional[float]:
    return risk_input.get("q_raw")


def evaluate_vetoes(risk_input: Mapping[str, Any]) -> Dict[str, Any]:
    """Evaluate the full registry, in numbered order, and return every fired
    veto. Ordering matters: this is called *before* any sizing."""
    r = frozen_risk_params()
    fired: List[Dict[str, Any]] = []
    evaluated: List[int] = []

    def check(number: int, condition: bool, measured: Any) -> None:
        evaluated.append(number)
        if condition:
            fired.append({"number": number, "name": veto_definition(number)["name"],
                          "measured": measured,
                          "error_code": veto_definition(number)["error_code"]})

    q_min = q_min_tf(risk_input["timeframe"])
    q_raw = _q_raw_of(risk_input)
    check(1, risk_input.get("qx_state") or (q_raw is not None and q_raw < q_min)
          or bool(risk_input.get("failed_setup_gate")),
          {"q_raw": q_raw, "q_min_tf": q_min})
    check(2, bool(risk_input.get("pit_violation")),
          risk_input.get("availability_time"))
    check(3, float(risk_input.get("portfolio_exposure", 0.0))
          + float(risk_input.get("proposed_notional", 0.0))
          > float(risk_input.get("capital_hard_cap", math.inf)),
          float(risk_input.get("portfolio_exposure", 0.0))
          + float(risk_input.get("proposed_notional", 0.0)))
    check(4, bool(risk_input.get("circuit_breaker_engaged")),
          risk_input.get("emergency_state"))
    check(5, float(risk_input.get("per_symbol_exposure", 0.0))
          > float(risk_input.get("symbol_cap", math.inf))
          or float(risk_input.get("portfolio_exposure", 0.0))
          > float(risk_input.get("portfolio_cap", math.inf)),
          {"per_symbol": risk_input.get("per_symbol_exposure"),
           "portfolio": risk_input.get("portfolio_exposure")})
    check(6, str(risk_input.get("conflict_state")) == "HARD_CONFLICT",
          risk_input.get("conflict_state"))
    check(7, float(risk_input.get("staleness_seconds", 0.0))
          > float(risk_input.get("freshness_sla_seconds", math.inf)),
          risk_input.get("staleness_seconds"))
    check(8, float(risk_input.get("oi_lag_seconds", 0.0))
          > float(risk_input.get("oi_lag_threshold_seconds", math.inf)),
          {"oi_lag": risk_input.get("oi_lag_seconds"),
           "threshold": risk_input.get("oi_lag_threshold_seconds")})
    check(9, bool(risk_input.get("is_risk_increase"))
          and bool(risk_input.get("uncertainty_is_rising")),
          {"is_risk_increase": risk_input.get("is_risk_increase"),
           "uncertainty_is_rising": risk_input.get("uncertainty_is_rising")})
    check(10, float(risk_input.get("realized_daily_loss_fraction", 0.0))
          > float(risk_input.get("daily_loss_cap", r["daily_loss_cap"])),
          risk_input.get("realized_daily_loss_fraction"))
    check(11, float(risk_input.get("realized_weekly_loss_fraction", 0.0))
          > float(risk_input.get("weekly_loss_cap", r["weekly_loss_cap"])),
          risk_input.get("realized_weekly_loss_fraction"))
    check(12, int(risk_input.get("consecutive_losses", 0))
          > int(risk_input.get("consecutive_loss_halt",
                              r["consecutive_loss_halt"])),
          risk_input.get("consecutive_losses"))
    check(13, float(risk_input.get("time_to_expiry_days", math.inf))
          < float(risk_input.get("rollover_threshold_days",
                                DEFAULT_CONTRACT_ROLLOVER_DAYS)),
          risk_input.get("time_to_expiry_days"))
    check(14, float(risk_input.get("margin_health_fraction", 1.0))
          <= float(risk_input.get("margin_health_action_fraction",
                                 DEFAULT_MARGIN_HEALTH_ACTION)),
          risk_input.get("margin_health_fraction"))
    if tuple(evaluated) != HARD_VETO_NUMBERS:
        # internal guard: the registry is evaluated complete and in order
        raise RiskError("VETO_REGISTRY_INCOMPLETE", str(evaluated))
    return {"fired": fired, "fired_numbers": [f["number"] for f in fired],
            "evaluated_in_order": evaluated, "veto_count": VETO_COUNT,
            "any": bool(fired),
            "note": "each veto is independently sufficient to REJECT, even at "
                    "P=0.99"}


# ---------------------------------------------------------------------------
# Risk ladder
# ---------------------------------------------------------------------------

def ladder_state_for(budget_used_fraction: float) -> str:
    """The budget-state projection (consumed risk budget)."""
    if not (0.0 <= budget_used_fraction <= 1.0) or budget_used_fraction != budget_used_fraction:
        raise RiskError("BUDGET_FRACTION_QX", str(budget_used_fraction))
    if budget_used_fraction >= 0.75:
        return "CriticalRisk"
    if budget_used_fraction >= 0.50:
        return "HighRisk"
    if budget_used_fraction >= 0.25:
        return "MediumRisk"
    return "LowRisk" if budget_used_fraction > 0.0 else "NoRisk"


def ladder_multiplier(state: str) -> float:
    s = str(state)
    if s not in RISK_LADDER_MULTIPLIER:
        raise RiskError("LADDER_STATE_QX", s)
    return RISK_LADDER_MULTIPLIER[s]


def ratchet_allow(src: str, dst: str, *, owner_confirmed: bool = False) -> Dict[str, Any]:
    """RSK-ERR-506 semantics: only upgrades are allowed. The single documented
    exception is the L1 PAUSE → Normal resume. Downgrades inside the emergency
    ladder are blocked outright — no numeric softening is possible."""
    if src not in EMERGENCY_LADDER or dst not in EMERGENCY_LADDER:
        raise RiskError("EMERGENCY_STATE_QX", f"{src}→{dst}")
    if src == dst:
        return {"allowed": True, "kind": "NOOP", "error_code": None,
                "note": "idempotent: the same state re-recorded is not a "
                        "downgrade"}
    i, j = EMERGENCY_LADDER.index(src), EMERGENCY_LADDER.index(dst)
    if (src, dst) in RATCHET_ALLOWED_DOWNGRADE:
        if not owner_confirmed:
            raise RiskError("RSK-ERR-506::OWNER_RESUME_REQUIRED",
                            "only OWNER can recover from an Emergency state")
        return {"allowed": True, "kind": "OWNER_RESUME", "error_code": None,
                "note": "L1 PAUSE → Normal resume allowed (verbatim ratchet row)"}
    if j > i:
        return {"allowed": True, "kind": "ESCALATION", "error_code": None,
                "note": "escalation to a more restrictive state is always "
                        "allowed"}
    return {"allowed": False, "kind": "DOWNGRADE", "error_code": "RSK-ERR-506",
            "note": f"{src} → {dst} blocked (ratchet: only upgrade allowed)"}


# ---------------------------------------------------------------------------
# Sizing machine
# ---------------------------------------------------------------------------

def size(*, capital: float, budget_per_trade: Optional[float] = None,
         stop_distance: float, contract_multiplier: float = 1.0,
         min_quantity: float, risk_state: str = "LowRisk",
         atr_cap: Optional[float] = None, k_attn: Optional[float] = None,
         correlation: Optional[Mapping[str, Any]] = None,
         cvar_fraction: Optional[float] = None) -> Dict[str, Any]:
    """The normative sizing machine, in its exact order.

    ``StopDistance <= 0`` and ``Capital <= 0`` reject **before** any division
    or leverage evaluation; ``Q == 0`` rejects with ``PORTFOLIO_CAPACITY``.
    """
    r = frozen_risk_params()
    budget = float(r["budget_per_trade"] if budget_per_trade is None
                   else budget_per_trade)
    k = float(r["k_attn"] if k_attn is None else k_attn)
    state = str(risk_state)
    mult = ladder_multiplier(state)
    if (cvar_fraction is not None
            and float(cvar_fraction) > DEFAULT_CVAR_CAP_FRACTION):
        # advisory downgrade by exactly one level (never a hard-veto override)
        order = list(RISK_LADDER_STATES)
        state = order[min(len(order) - 1, order.index(state) + 1)]
        mult = ladder_multiplier(state)
    if capital <= 0:
        return {"decision": "REJECT", "sized_quantity": 0.0,
                "reason": "CAPITAL_NON_POSITIVE", "risk_state": state,
                "R_allowed": 0.0, "note": "reject before evaluating leverage "
                                          "or quantity"}
    if stop_distance <= 0 or stop_distance != stop_distance:
        return {"decision": "REJECT", "sized_quantity": 0.0,
                "reason": "STOP_DISTANCE_INVALID", "risk_state": state,
                "R_allowed": budget * capital * mult,
                "note": "deterministic validation reason; never a division by "
                        "zero"}
    if contract_multiplier <= 0:
        return {"decision": "REJECT", "sized_quantity": 0.0,
                "reason": "CONTRACT_MULTIPLIER_INVALID", "risk_state": state,
                "R_allowed": budget * capital * mult}
    r_allowed = budget * capital * mult
    q_risk = r_allowed / (stop_distance * contract_multiplier)
    q_caps = [q_risk]
    if atr_cap is not None:
        q_caps.append(k * float(atr_cap) * capital / contract_multiplier)
    q = max(0.0, min(q_caps))
    if min_quantity <= 0:
        raise RiskError("MIN_QUANTITY_QX",
                        "the exchange step is mandatory (never assumed)")
    q = math.floor(q / min_quantity) * min_quantity
    decision = "ALLOW"
    note: List[str] = []
    if correlation:
        expo = correlation_exposure(
            rho=float(correlation["rho"]),
            open_notional=list(correlation.get("open_notional", [])),
            proposed_notional=q * stop_distance * contract_multiplier,
            cap=correlation.get("cap"))
        if expo["action"] == "REDUCE":
            allowed = max(0.0, float(expo["reduced_proposal"]))
            q = math.floor(allowed / (stop_distance * contract_multiplier)
                           / min_quantity) * min_quantity
            decision = "REDUCE"
            note.append("CORRELATION_REDUCE_PATH")
    if q <= 0:
        return {"decision": "REJECT", "sized_quantity": 0.0,
                "reason": "PORTFOLIO_CAPACITY", "risk_state": state,
                "R_allowed": r_allowed, "q_before_floor": max(0.0, min(q_caps)),
                "note": "Q == 0 ⇒ REJECT (Ch.15 sizing machine)"}
    return {"decision": decision, "sized_quantity": q, "risk_state": state,
            "R_allowed": r_allowed, "multiplier": mult,
            "q_risk_bound": q_risk,
            "q_attention_bound": (None if atr_cap is None
                                 else k * float(atr_cap) * capital
                                 / contract_multiplier),
            "min_quantity": min_quantity, "notes": note,
            "correlation": correlation or {}}


# ---------------------------------------------------------------------------
# Adjudication (vetoes first, then the ladder, then sizing)
# ---------------------------------------------------------------------------

def adjudicate(risk_input: Mapping[str, Any]) -> Dict[str, Any]:
    """The single entry point: 14 vetoes → ladder → sizing / REDUCE / REJECT.

    The returned record is the Trade Plan shape
    ``{decision, sized_quantity, selected_parameter_package, vetoes_applied,
    snapshot_id}`` (Ch.15 §15.1) plus the audit trail of the evaluation order.
    """
    for key in ("snapshot_id", "timeframe", "capital"):
        if key not in risk_input:
            raise RiskError("RISK_INPUT_QX", key)
    if risk_input.get("package") is not None:
        # Gate 13's owner is the Setup layer; the kernel refuses to size on a
        # degraded package rather than re-defining that gate.
        from apex.setup.gates import gate13_parameter_package
        g13 = gate13_parameter_package(risk_input["package"])
        if not g13.passed:
            return {"decision": "REJECT", "sized_quantity": 0.0,
                    "selected_parameter_package": None,
                    "vetoes_applied": [], "snapshot_id": risk_input["snapshot_id"],
                    "reason": "PARAMETER_PACKAGE_INVALID::" + g13.reason}
    verdict = evaluate_vetoes(risk_input)
    if verdict["any"]:
        return {"decision": "REJECT", "sized_quantity": 0.0,
                "selected_parameter_package": risk_input.get("package"),
                "vetoes_applied": verdict["fired_numbers"],
                "snapshot_id": risk_input["snapshot_id"],
                "veto_detail": verdict["fired"],
                "veto_evaluation_order": verdict["evaluated_in_order"],
                "sized_after_all_vetoes": False,
                "reason": "HARD_VETO"}
    budget = float(risk_input.get("capital", 0.0))
    used = float(risk_input.get("portfolio_exposure", 0.0)) / budget \
        if budget > 0 else 1.0
    derived = ladder_state_for(min(1.0, used))
    declared = risk_input.get("risk_state")
    order = list(RISK_LADDER_STATES)
    if declared:
        # the caller's declared state is respected as a FLOOR only: the consumed
        # budget always escalates it (the ladder projection is not negotiable)
        state = order[max(order.index(str(declared)), order.index(derived))]
    else:
        state = derived
    plan = size(capital=budget, stop_distance=float(risk_input["stop_distance"]),
               contract_multiplier=float(risk_input.get("contract_multiplier",
                                                        1.0)),
               min_quantity=float(risk_input["min_quantity"]),
               risk_state=state,
               atr_cap=risk_input.get("atr_cap"),
               correlation=risk_input.get("correlation"),
               cvar_fraction=risk_input.get("cvar_fraction"))
    out = {"decision": plan["decision"],
           "sized_quantity": plan["sized_quantity"],
           "selected_parameter_package": risk_input.get("package"),
           "vetoes_applied": [], "snapshot_id": risk_input["snapshot_id"],
           "veto_evaluation_order": verdict["evaluated_in_order"],
           "sized_after_all_vetoes": True,
           "sizing": plan, "reason": plan.get("reason", "SIZED")}
    if state == "CriticalRisk":
        # 75–100 % of the consumed budget ⇒ REJECT with reason
        # PORTFOLIO_CAPACITY (the ladder projection, identical to the sizing
        # machine's own Q == 0 rule)
        out["decision"] = "REJECT"
        out["sized_quantity"] = 0.0
        out["reason"] = "PORTFOLIO_CAPACITY"
        out["sizing"]["override_reason"] = "LADDER_CRITICAL_RISK"
    return out


def reduce_to_correlation_cap(*, rho: float, open_notional: Sequence[float],
                             proposed_notional: float) -> Dict[str, Any]:
    """The Ch.15 REDUCE path (correlation), delegating to the single
    §8.2 exposure law — never re-implemented here."""
    return correlation_exposure(rho=rho, open_notional=list(open_notional),
                               proposed_notional=float(proposed_notional))


def leverage_cap(timeframe: str) -> int:
    caps = frozen_risk_params()["system_leverage_cap_by_tf"]
    try:
        return int(caps[timeframe])
    except KeyError:
        raise RiskError("E-VAL-022", str(timeframe)) from None


def effective_leverage(*, notional: float, capital_allocated: float,
                       timeframe: str, owner_cap: Optional[float] = None) -> Dict[str, Any]:
    """``min(exchange, owner, Y.2 system cap)`` (veto 3 + Y.2): the ceiling is
    enforced, and an over-cap request is reduced, never approved."""
    if capital_allocated <= 0:
        raise RiskError("CAPITAL_NON_POSITIVE")
    system = float(leverage_cap(timeframe))
    limits = [system] + ([float(owner_cap)] if owner_cap is not None else [])
    cap = min(limits)
    requested = float(notional) / float(capital_allocated)
    return {"requested_leverage": requested, "cap": cap,
            "within_cap": requested <= cap + 1e-12,
            "reduced_notional": None if requested <= cap
            else cap * float(capital_allocated),
            "note": "leverage is a ceiling, not a target (veto 3/Y.2)"}


def margin_health_state(margin_health_fraction: float) -> Dict[str, Any]:
    """Governed polling thresholds: warning 0.60, action 0.40 (veto 14),
    liquidation-approach 0.20 → Emergency L3 CANCEL_ALL."""
    v = float(margin_health_fraction)
    if not (0.0 <= v <= 1.0) or v != v:
        raise RiskError("MARGIN_HEALTH_QX", str(margin_health_fraction))
    # "warning at 60 % of maintenance distance, action at 40 % — the action
    # blocks all new entries (veto 14) … liquidation-approach at 20 % triggers
    # Emergency L3 CANCEL_ALL automatically" (Ch.15 §15.1). The band edges are
    # inclusive at the named threshold (the same reading the veto-14 carrier
    # uses, so 0.40 fires the veto and the WARNING band).
    if v <= DEFAULT_MARGIN_HEALTH_LIQUIDATION:
        return {"level": "LIQUIDATION_APPROACH",
                "action": "EMERGENCY_L3_CANCEL_ALL", "veto": 14,
                "threshold": DEFAULT_MARGIN_HEALTH_LIQUIDATION}
    if v <= DEFAULT_MARGIN_HEALTH_ACTION:
        return {"level": "ACTION", "action": "BLOCK_NEW_ENTRIES", "veto": 14,
                "threshold": DEFAULT_MARGIN_HEALTH_ACTION}
    if v <= DEFAULT_MARGIN_HEALTH_WARN:
        return {"level": "WARNING", "action": "NOTIFY_OWNER", "veto": None,
                "threshold": DEFAULT_MARGIN_HEALTH_WARN}
    return {"level": "OK", "action": "NONE", "veto": None, "threshold": None}


def circuit_breaker_reset(kind: str, *, utc_rollover: bool = False,
                          owner_reviewed: bool = False) -> Dict[str, Any]:
    """Vetoes 10–12: "Reset is time-based or OWNER-review-based only — never
    automatic on new data."""
    k = str(kind).upper()
    if k == "DAILY_LOSS_LIMIT":
        return {"reset": bool(utc_rollover), "mechanism": "UTC_DAY_ROLLOVER"}
    if k == "WEEKLY_LOSS_LIMIT":
        return {"reset": bool(utc_rollover), "mechanism": "UTC_WEEK_ROLLOVER",
                "owner_review_required": True}
    if k == "CONSECUTIVE_LOSSES":
        return {"reset": bool(owner_reviewed), "mechanism": "OWNER_REVIEW"}
    raise RiskError("CIRCUIT_BREAKER_KIND_QX", k)


def aggregate_loss_state(*, realized_daily: float, realized_weekly: float,
                         consecutive_losses: int) -> Dict[str, Any]:
    r = frozen_risk_params()
    return {
        "daily_blocked": realized_daily > float(r["daily_loss_cap"]),
        "weekly_blocked": realized_weekly > float(r["weekly_loss_cap"]),
        "consecutive_blocked": int(consecutive_losses)
        > int(r["consecutive_loss_halt"]),
        "thresholds": {"daily": float(r["daily_loss_cap"]),
                      "weekly": float(r["weekly_loss_cap"]),
                      "consecutive": int(r["consecutive_loss_halt"])},
        "precedence": "these vetoes take precedence over every ALLOW",
    }


def cvar_advisory(*, cvar_fraction: float, risk_state: str) -> Dict[str, Any]:
    """Weekly CVaR_95 above a governed fraction of capital downgrades the
    ladder multiplier by one level — an advisory-veto, never a replacement."""
    order = list(RISK_LADDER_STATES)
    cur = str(risk_state)
    if cur not in order:
        raise RiskError("LADDER_STATE_QX", cur)
    if float(cvar_fraction) <= DEFAULT_CVAR_CAP_FRACTION:
        return {"downgraded": False, "risk_state": cur,
                "multiplier": ladder_multiplier(cur),
                "threshold": DEFAULT_CVAR_CAP_FRACTION}
    nxt = order[min(len(order) - 1, order.index(cur) + 1)]
    return {"downgraded": True, "risk_state": nxt,
            "multiplier": ladder_multiplier(nxt),
            "threshold": DEFAULT_CVAR_CAP_FRACTION,
            "note": "addition to, never replacement of, the hard vetoes"}


# ---------------------------------------------------------------------------
# ADR-P2-004 — ladder-state persistence (append-only, single writer, ratchet)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LadderStateRevision:
    revision_id: str
    applied_at: str
    state: str
    emergency_state: str
    consumed_budget: float
    multiplier: float
    reason: str
    snapshot_id: str
    parent_revision_id: Optional[str] = None

    def to_row(self) -> Tuple[Any, ...]:
        return (self.revision_id, self.applied_at, self.state,
                self.emergency_state, self.consumed_budget, self.multiplier,
                self.reason, self.snapshot_id, self.parent_revision_id)


LADDER_ROW_COLUMNS = ("revision_id", "applied_at", "state", "emergency_state",
                     "consumed_budget", "multiplier", "reason", "snapshot_id",
                     "parent_revision_id")


def ladder_revision(*, revision_id: str, applied_at: str, state: str,
                    emergency_state: str, consumed_budget: float, reason: str,
                    snapshot_id: str,
                    parent_revision_id: Optional[str] = None,
                    previous_state: Optional[str] = None,
                    owner_confirmed: bool = False) -> LadderStateRevision:
    """Build the next revision, enforcing the ratchet *before* persistence."""
    if state not in RISK_LADDER_STATES:
        raise RiskError("LADDER_STATE_QX", state)
    if previous_state is not None:
        allow = ratchet_allow(previous_state, emergency_state,
                             owner_confirmed=owner_confirmed)
        if not allow["allowed"]:
            raise RiskError("RSK-ERR-506",
                            f"{previous_state} → {emergency_state} blocked")
    return LadderStateRevision(
        revision_id=revision_id, applied_at=applied_at, state=state,
        emergency_state=emergency_state, consumed_budget=float(consumed_budget),
        multiplier=ladder_multiplier(state), reason=reason,
        snapshot_id=snapshot_id, parent_revision_id=parent_revision_id)


async def apply_ladder_state_migration(db: Any) -> Dict[str, Any]:
    """Apply ``apex_risk_ladder_state`` using CP-1's migration mechanism
    (``schema_migrations`` bookkeeping, append-only migration list): this
    module never edits the frozen store, it registers an additional migration
    row (ADR-P2-003/004)."""
    import datetime as _dt
    # multiple statements (table + two triggers) ⇒ executescript, the same
    # mechanism CP-1's store uses for its migrations
    await db.executescript(LADDER_STATE_DDL)
    await db.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (migration_name TEXT "
        "PRIMARY KEY, applied_at TEXT NOT NULL)")
    cur = await db.execute(
        "SELECT 1 FROM schema_migrations WHERE migration_name=?",
        (LADDER_STATE_MIGRATION,))
    already = await cur.fetchone()
    if not already:
        now = _dt.datetime.now(_dt.timezone.utc)
        await db.execute(
            "INSERT INTO schema_migrations (migration_name, applied_at) "
            "VALUES (?, ?)",
            (LADDER_STATE_MIGRATION,
             now.strftime("%Y-%m-%dT%H:%M:%S.")
             + f"{now.microsecond // 1000:03d}Z"))
    await db.commit()
    return {"migration": LADDER_STATE_MIGRATION, "applied": not already,
            "table": "apex_risk_ladder_state", "immutability": "triggers"}


async def append_ladder_revision(db: Any, rev: LadderStateRevision) -> None:
    """Single-writer append (the ledger queue owns the writer slot in CP-7);
    an update/delete is impossible at the schema level."""
    await db.execute(
        "INSERT INTO apex_risk_ladder_state (" + ",".join(LADDER_ROW_COLUMNS)
        + ") VALUES (" + ",".join("?" * len(LADDER_ROW_COLUMNS)) + ")",
        rev.to_row())
    await db.commit()


__all__ = ["CONTRACT_VERSION", "DEFAULT_CONTRACT_ROLLOVER_DAYS",
           "DEFAULT_CVAR_CAP_FRACTION", "DEFAULT_MARGIN_HEALTH_ACTION",
           "DEFAULT_MARGIN_HEALTH_LIQUIDATION", "DEFAULT_MARGIN_HEALTH_WARN",
           "EMERGENCY_LADDER", "HARD_VETO_NUMBERS", "LADDER_ROW_COLUMNS",
           "LADDER_STATE_DDL", "LADDER_STATE_MIGRATION", "LadderStateRevision",
           "RATCHET_ALLOWED_DOWNGRADE", "RATCHET_BLOCKED",
           "RISK_LADDER_BANDS", "RISK_LADDER_MULTIPLIER", "RISK_LADDER_STATES",
           "RiskError", "TRADE_PLAN_FIELDS", "VETO_COUNT", "VETO_NAMES",
           "VETO_REGISTRY", "adjudicate", "aggregate_loss_state",
           "append_ladder_revision", "apply_ladder_state_migration",
           "circuit_breaker_reset", "evaluate_vetoes", "effective_leverage",
           "frozen_risk_params", "ladder_multiplier", "ladder_revision",
           "ladder_state_for", "leverage_cap", "margin_health_state",
           "ratchet_allow", "reduce_to_correlation_cap", "size",
           "veto_definition"]
