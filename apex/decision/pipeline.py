"""APEX_GEN5 — Decision Engine + Strategy Arbitration (Ch.12 AF.1–AF.5,
Ch.14 §14.1; blueprint L15751–15847 and L15848–15971).

"Decision ranks surviving candidates by economic utility. It proposes. It does
not veto." (Ch.14 heading)

Frozen contract
---------------
* ``EU = P(W)·G − (1 − P(W))·L − C − R_penalty`` in units of R:
  ``R = |entry − stop|``, ``RR = target_distance / stop_distance``,
  ``G = RR·R``, ``L = R``, ``C = fee + half_spread + slippage_model``
  (execution-layer cost model, ``slippage_model = α_spread·|size/ADV|``);
  ``EU_dollar = EU_unit · sized_quantity · ContractMultiplier · price_scale``.
* Eligibility (all must hold): setup_valid ∧ forecast_quality_ok ∧
  conflict_state ≠ HARD_CONFLICT ∧ Q_raw ≥ Q_min(tf) ∧ freshness_ok ∧
  data_trust ≥ 0.30 ∧ P ≥ P_min(tf) ∧ C ≥ C_min. A failure of the last two is
  ``INSUFFICIENT_EVIDENCE`` — never a guess-based entry.
* Candidate generation: ``RR = max(0.5, target/stop)``, the SL-2 monotonicity
  check first, ``EU`` descending with tie-breakers (higher P, higher C, lower
  U, lower RR).
* Strategy arbitration (Ch.12): regime-window hard filter, family-status
  ineligibility (DEGRADING/DEMOTED), advisory same-direction composite ranking
  capped by ``correlation_cap``, opposite-direction default **NO-TRADE** unless
  the score gap exceeds a governed ``direction_conflict_threshold``, and a
  structured REASON for every output. Arbitration never issues orders, never
  allocates capital, never overrides a veto — and it reads the risk ceilings
  only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from apex.config import load_params
from apex.fabric.conflict import HARD_CONFLICT, monotone_ok
from apex.fabric.context import data_trust_floor, q_min_tf
from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import sha256_hex

CONTRACT_VERSION = "4.0.0"

# The StrategyProposal / Portfolio-Proposal output shapes (§14.1, AF.1).
PORTFOLIO_PROPOSAL_FIELDS: Tuple[str, ...] = (
    "setup_id", "direction", "entry_logic_ref", "stop", "targets",
    "sizing_request", "EU", "PUC", "conflict_state", "snapshot_id",
)
ARBITRATION_REASON_FIELDS: Tuple[str, ...] = (
    "decision", "top_candidate", "score", "conflict_type", "threshold_check",
    "family_status_filter",
)
NO_TRADE = "NO_TRADE"
TRADE = "TRADE"
INELIGIBLE_FAMILIES: Tuple[str, ...] = ("DEGRADING", "DEMOTED")
MIN_RR = 0.5                      # §14.1: RR = max(0.5, target/stop)


class DecisionError(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}{('::' + detail) if detail else ''}")
        self.reason = reason
        self.detail = detail


def _risk_cfg() -> Dict[str, Any]:
    return load_params()["risk_defaults"]


def governed_limits() -> Dict[str, Any]:
    r = _risk_cfg()
    return {"max_candidates": int(r["max_candidates"]),
            "correlation_cap": float(r["correlation_cap"]),
            "data_trust_floor": data_trust_floor(),
            "cost_R_floor": float(r["cost_R_floor"]),
            "direction_conflict_threshold": 0.15}


def slippage_model(*, order_size: float, adv: Optional[float],
                   alpha_spread: Optional[float] = None) -> Dict[str, Any]:
    """Execution-layer cost model: ``slippage = α_spread · |order_size / ADV|``.

    ``ADV`` (or α) unavailable ⇒ the term is UNAVAILABLE and reported as such:
    it is never replaced by zero, and the caller's ``cost_R`` floor still
    applies (Ch.13: "if spread UNAVAILABLE, cost_R ≥ 0.05").
    """
    if order_size < 0:
        raise DecisionError("ORDER_SIZE_QX", str(order_size))
    if adv is None or adv <= 0 or alpha_spread is None:
        return {"slippage": None, "available": False,
                "reason": "SLIPPAGE_MODEL_UNAVAILABLE",
                "impact": None}
    impact = abs(order_size) / float(adv)
    return {"slippage": float(alpha_spread) * impact, "available": True,
            "reason": "OK", "impact": impact}


def units_of_r(*, entry: float, stop: float, target: float) -> Dict[str, float]:
    """``R = |entry − stop|`` and ``RR = target_distance / stop_distance``
    (frozen; ``RR`` floored at 0.5)."""
    stop_distance = abs(float(entry) - float(stop))
    if stop_distance <= 0:
        raise DecisionError("RISK_UNIT_QX",
                            "entry == stop: R must be > 0 (never divide by it)")
    target_distance = abs(float(target) - float(entry))
    rr = max(MIN_RR, target_distance / stop_distance)
    return {"R": stop_distance, "RR": rr, "G": rr * stop_distance,
            "L": stop_distance, "stop_distance": stop_distance,
            "target_distance": target_distance}


def economic_utility(*, p: float, rr: float, cost_unit: float,
                     r_penalty: float) -> float:
    """``EU_unit = P·RR − (1−P)·1 − C_unit − R_penalty`` (multiples of R)."""
    if not (0.0 <= p <= 1.0):
        raise DecisionError("P_QX", str(p))
    if rr < MIN_RR:
        raise DecisionError("RR_QX", str(rr))
    if math.isinf(r_penalty):
        return -math.inf
    return p * rr - (1.0 - p) * 1.0 - float(cost_unit) - float(r_penalty)


def eu_dollar(*, eu_unit: float, sized_quantity: float,
              contract_multiplier: float = 1.0, price_scale: float = 1.0) -> float:
    if math.isinf(eu_unit):
        return float("-inf") if eu_unit < 0 else float("inf")
    return eu_unit * sized_quantity * contract_multiplier * price_scale


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------

def eligibility(checks: Mapping[str, Any]) -> Dict[str, Any]:
    """The frozen 8-condition conjunction. Any unmet condition is reported by
    name; ``P < P_min`` or ``C < C_min`` additionally yields
    ``INSUFFICIENT_EVIDENCE`` (never a guess-based entry)."""
    required = ("setup_valid", "forecast_quality_ok", "conflict_state",
                "q_raw", "timeframe", "freshness_ok", "data_trust", "p",
                "p_min_tf", "c", "c_min")
    missing = [k for k in required if k not in checks]
    if missing:
        raise DecisionError("ELIGIBILITY_INPUT_QX", ",".join(missing))
    fails: List[str] = []
    if not bool(checks["setup_valid"]):
        fails.append("SETUP_INVALID")
    if not bool(checks["forecast_quality_ok"]):
        fails.append("FORECAST_QUALITY_FAIL")
    if str(checks["conflict_state"]) == HARD_CONFLICT:
        fails.append("HARD_CONFLICT")
    q_min = q_min_tf(checks["timeframe"])
    if float(checks["q_raw"]) < q_min:
        fails.append("Q_RAW_BELOW_MIN_TF")
    if not bool(checks["freshness_ok"]):
        fails.append("FRESHNESS_FAIL")
    if float(checks["data_trust"]) < data_trust_floor():
        fails.append("DATA_TRUST_BELOW_FLOOR")
    if float(checks["p"]) < float(checks["p_min_tf"]):
        fails.append("BELOW_P_MIN")
    if float(checks["c"]) < float(checks["c_min"]):
        fails.append("BELOW_C_MIN")
    verdict = "ELIGIBLE" if not fails else (
        "INSUFFICIENT_EVIDENCE" if ("BELOW_P_MIN" in fails
                                   or "BELOW_C_MIN" in fails) else "INELIGIBLE")
    return {"eligible": not fails, "verdict": verdict, "failed": fails,
            "q_min_tf": q_min, "note": "a failed condition never becomes a "
                                       "permission; it removes one"}


# ---------------------------------------------------------------------------
# Candidate generation and ranking
# ---------------------------------------------------------------------------

def generate_candidates(setups: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """§14.1 pseudocode: for every eligible setup and side, the monotonicity
    check runs first (``if not monotone_ok(proposal): continue``), then EU."""
    out: List[Dict[str, Any]] = []
    for setup in setups:
        for side in ("LONG", "SHORT"):
            u = units_of_r(entry=float(setup["entry"]),
                           stop=float(setup["stop"]),
                           target=float(setup["target"]))
            is_risk_increase = bool(setup.get("is_risk_increase", False))
            rising = bool(setup.get("uncertainty_is_rising", False))
            if not monotone_ok(is_risk_increase=is_risk_increase,
                               uncertainty_is_rising=rising):
                continue                    # SL-2: refused before ranking
            eu = economic_utility(p=float(setup["P"]), rr=u["RR"],
                                 cost_unit=float(setup.get("cost_unit", 0.0)),
                                 r_penalty=float(setup.get("r_penalty", 0.0)))
            out.append({"setup_id": setup["setup_id"], "side": side,
                        "EU": eu, "P": float(setup["P"]),
                        "C": float(setup.get("C", 0.0)),
                        "RR": u["RR"], "U_sum": float(setup.get("U_sum", 0.0)),
                        "R": u["R"], "setup": setup})
    return out


def rank(candidates: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """EU descending; ties: higher P, higher C, lower U, lower RR."""
    return sorted(candidates, key=lambda c: (-float(c["EU"]), -float(c["P"]),
                                             -float(c["C"]), float(c["U_sum"]),
                                             float(c["RR"])))


def select(candidates: Sequence[Mapping[str, Any]], *, environment: str = "PAPER"
           ) -> Dict[str, Any]:
    """Cap the selection at the governed ``max_candidates`` (3). The Risk
    Kernel owns everything beyond that; this layer never allocates."""
    ordered = rank(candidates)
    limit = governed_limits()["max_candidates"]
    return {"selected": ordered[:limit], "considered": len(ordered),
            "max_candidates": limit, "environment": environment,
            "authority_note": "selection is by EU only, up to the "
                               "exposure/capital caps; Risk Kernel unbypassed"}


# ---------------------------------------------------------------------------
# Strategy arbitration (Ch.12)
# ---------------------------------------------------------------------------

def regime_window_ok(playbook: Mapping[str, Any], regime: str) -> bool:
    """AF.3 Rule 1: a regime window that does not contain the current E11
    regime never produces a candidate (architectural filter, not a score)."""
    window = playbook.get("regime_window")
    if window is None:
        raise DecisionError("ARBITRATION_WINDOW_QX",
                            "a playbook without a regime window cannot be "
                            "adjudicated (AF.3 Rule 1)")
    return str(regime) in {str(w) for w in window}


def family_status_ok(status: str) -> bool:
    """AF.3 Rule 2: DEGRADING/DEMOTED families are architecturally ineligible."""
    return str(status).upper() not in INELIGIBLE_FAMILIES


def composite_rank_score(playbook: Mapping[str, Any], *,
                         alignment_cap: Optional[float] = None) -> Dict[str, Any]:
    """AF.3 Rule 3 — bounded advisory composite: playbook quality, alignment
    (capped by ``correlation_cap``) and recency. All weights governed; no
    hardcoded constant is invented here."""
    caps = governed_limits()
    cap = caps["correlation_cap"] if alignment_cap is None else float(
        alignment_cap)
    weights = playbook.get("composite_weights")
    if not weights:
        raise DecisionError("ARBITRATION_WEIGHTS_QX",
                            "composite weights are governed (SL-12); none "
                            "supplied — refusing to invent a default")
    w = {k: float(v) for k, v in weights.items()}
    if set(w) != {"quality", "alignment", "recency"}:
        raise DecisionError("ARBITRATION_WEIGHT_KEYS_QX", ",".join(sorted(w)))
    total = sum(w.values())
    if total <= 0:
        raise DecisionError("ARBITRATION_WEIGHTS_EMPTY_QX")
    q = float(playbook.get("quality", 0.0))
    a = min(float(playbook.get("alignment", 0.0)), cap) / cap if cap else 0.0
    r = float(playbook.get("recency", 0.0))
    score = (w["quality"] / total) * q + (w["alignment"] / total) * a \
        + (w["recency"] / total) * r
    return {"score": max(0.0, min(1.0, score)), "capped_alignment": a,
            "correlation_cap": cap, "weights_normalized":
            {k: v / total for k, v in w.items()}}


def arbitrate(candidates: Sequence[Mapping[str, Any]], *, regime: str,
              family_statuses: Mapping[str, str],
              threshold: Optional[float] = None) -> Dict[str, Any]:
    """AF.3 gatekeeper + ranking, AF.4 NO-TRADE as a first-class output.

    ``candidates``: ``{playbook_id, family_id, direction, regime_window,
    composite_weights, quality, alignment, recency}``.
    """
    thr = governed_limits()["direction_conflict_threshold"] if threshold is None \
        else float(threshold)
    eligible: List[Dict[str, Any]] = []
    excluded_window = 0
    excluded_status = 0
    for cand in candidates:
        if not regime_window_ok(cand, regime):
            excluded_window += 1
            continue
        status = family_statuses.get(cand["family_id"], "ACCUMULATING")
        if not family_status_ok(status):
            excluded_status += 1
            continue
        scored = dict(cand)
        scored["composite"] = composite_rank_score(cand)
        scored["family_status"] = status
        eligible.append(scored)
    eligible.sort(key=lambda c: -c["composite"]["score"])
    longs = [c for c in eligible if str(c["direction"]).upper() == "LONG"]
    shorts = [c for c in eligible if str(c["direction"]).upper() == "SHORT"]
    base_reason = {
        "decision": NO_TRADE, "top_candidate": None, "score": "N/A",
        "conflict_type": "NONE", "threshold_check": "N/A",
        "family_status_filter": (f"{excluded_status}_FAMILIES_EXCLUDED"
                                if excluded_status else "ACTIVE_FAMILIES"),
        "excluded": {"regime_window": excluded_window,
                     "family_status": excluded_status},
        "eligible_count": len(eligible),
    }
    if not eligible:
        return {"proposal": None, "reason": base_reason, "ranked": []}
    if longs and shorts:
        gap = longs[0]["composite"]["score"] - shorts[0]["composite"]["score"]
        check = "PASS" if abs(gap) > thr else "FAIL"
        if check == "FAIL":
            return {"proposal": None,
                    "reason": {**base_reason, "conflict_type":
                               "OPPOSITE_DIRECTION", "threshold_check": "FAIL",
                               "score": round(abs(gap), 12)},
                    "ranked": eligible}
        pick = longs[0] if gap > 0 else shorts[0]
        return {"proposal": _proposal_from(pick),
                "reason": {**base_reason, "decision": TRADE, "top_candidate":
                           pick["playbook_id"], "conflict_type":
                           "OPPOSITE_DIRECTION", "threshold_check": "PASS",
                           "score": pick["composite"]["score"]},
                "ranked": eligible}
    top = eligible[0]
    return {"proposal": _proposal_from(top),
            "reason": {**base_reason, "decision": TRADE,
                       "top_candidate": top["playbook_id"],
                       "score": top["composite"]["score"]},
            "ranked": eligible}


def _proposal_from(winner: Mapping[str, Any]) -> Dict[str, Any]:
    return {"playbook_id": winner["playbook_id"],
            "family_id": winner["family_id"],
            "direction": str(winner["direction"]).upper(),
            "composite_score": winner["composite"]["score"],
            "family_status": winner.get("family_status"),
            "authority": "STRATEGY_ARBITRATION",
            "is_order": False, "allocates_capital": False}


# ---------------------------------------------------------------------------
# StrategyProposal (the only shape CP-7 consumes)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StrategyProposal:
    """The output contract consumed downstream. A proposal is a policy
    selection: it is never an order and never carries sizing beyond a
    *request*."""

    setup_id: str
    direction: str                  # LONG | SHORT | NO_TRADE
    entry_logic_ref: str
    stop: Optional[float]
    targets: Tuple[float, ...]
    sizing_request: Dict[str, Any]
    EU: float
    PUC: Dict[str, Any]
    conflict_state: str
    snapshot_id: str
    arbitration_reason: Dict[str, Any] = field(default_factory=dict)
    contract_version: str = CONTRACT_VERSION

    FORBIDDEN_FIELDS: Tuple[str, ...] = ("order", "order_type", "client_order_id",
                                        "leverage", "margin_mode", "position_id")

    def __post_init__(self) -> None:
        if self.direction not in ("LONG", "SHORT", NO_TRADE):
            raise DecisionError("PROPOSAL_DIRECTION_QX", self.direction)
        if self.direction == NO_TRADE and (self.stop is not None
                                          or self.targets):
            raise DecisionError("PROPOSAL_NO_TRADE_QX",
                                "a NO-TRADE proposal carries no plan")
        if not self.snapshot_id:
            raise DecisionError("PROPOSAL_SNAPSHOT_QX",
                                "lineage is mandatory (snapshot_id)")
        missing = [f for f in PORTFOLIO_PROPOSAL_FIELDS
                   if not hasattr(self, f)]
        if missing:
            raise DecisionError("PROPOSAL_SCHEMA_QX", ",".join(missing))
        for f in self.FORBIDDEN_FIELDS:
            if f in self.sizing_request:
                raise DecisionError("PROPOSAL_AUTHORITY_QX",
                                    f"sizing_request may not carry {f}")

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in PORTFOLIO_PROPOSAL_FIELDS} | {
            "arbitration_reason": dict(self.arbitration_reason),
            "contract_version": self.contract_version}

    @property
    def proposal_id(self) -> str:
        return "sp-" + sha256_hex(canonical_json(self.to_dict()))[:32]


def build_proposal(*, setup_id: str, direction: str, entry_logic_ref: str,
                   stop: Optional[float], targets: Sequence[float],
                   p_hat: float, u: float, c: float, conflict_state: str,
                   snapshot_id: str, r_penalty: float, cost_unit: float,
                   entry: Optional[float] = None,
                   arbitration_reason: Optional[Mapping[str, Any]] = None,
                   ) -> StrategyProposal:
    if direction == NO_TRADE:
        return StrategyProposal(
            setup_id=setup_id, direction=NO_TRADE,
            entry_logic_ref=entry_logic_ref, stop=None, targets=(),
            sizing_request={"requested": False, "reason": "NO_TRADE"},
            EU=float("-inf"),
            PUC={"P": p_hat, "U": u, "C": c}, conflict_state=conflict_state,
            snapshot_id=snapshot_id,
            arbitration_reason=dict(arbitration_reason or {}))
    if entry is None or stop is None or not targets:
        raise DecisionError("PROPOSAL_PLAN_QX",
                            "a trade proposal needs entry, stop and targets")
    u_r = units_of_r(entry=entry, stop=stop, target=float(targets[0]))
    eu = economic_utility(p=p_hat, rr=u_r["RR"], cost_unit=cost_unit,
                         r_penalty=r_penalty)
    return StrategyProposal(
        setup_id=setup_id, direction=direction.upper(),
        entry_logic_ref=entry_logic_ref, stop=float(stop),
        targets=tuple(float(t) for t in targets),
        sizing_request={"requested": True, "R_unit": u_r["R"],
                        "RR": u_r["RR"], "stop_distance": u_r["stop_distance"],
                        "target_distance": u_r["target_distance"]},
        EU=eu, PUC={"P": p_hat, "U": u, "C": c},
        conflict_state=conflict_state, snapshot_id=snapshot_id,
        arbitration_reason=dict(arbitration_reason or {}))


__all__ = ["ARBITRATION_REASON_FIELDS", "CONTRACT_VERSION",
           "INELIGIBLE_FAMILIES", "MIN_RR", "NO_TRADE",
           "PORTFOLIO_PROPOSAL_FIELDS", "StrategyProposal", "TRADE",
           "DecisionError", "arbitrate", "build_proposal",
           "composite_rank_score", "economic_utility", "eligibility",
           "eu_dollar", "family_status_ok", "governed_limits",
           "generate_candidates", "rank", "regime_window_ok", "select",
           "slippage_model", "units_of_r"]
