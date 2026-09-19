"""APEX_GEN5 — Statistical Forecast (P / U / C) (Ch.13 §13.1, L15751–15853).

"Forecast answers only: probability that target is touched before stop within
the playbook horizon, given PIT evidence. Until a walk-forward package exists,
the uninformative prior is ``p_raw = 0.5``. That prior may run in RESEARCH and
PAPER. **It cannot pass the forecast gates for LIVE capital.**"

Frozen contract implemented here
--------------------------------
* Forecast event (exact, PIT-stamped):
  ``{target_condition, stop_condition, horizon, entry_ref, symbol, timeframe,
  timestamp}``; semantics ``P(T before S within H | X)``.
* Bootstrap P model: ``p_raw = 1/(1+exp(−(β0+β·x)))`` with **β=0, β0=0 ⇒
  p_raw = 0.5**, ``Q_forecast = 0.5``; ``x`` is the frozen 12-feature vector
  ``[s_struct, s_liq, s_vol, s_fvg, s_ob, trend_stack, momentum_z,
  regime_entropy, vol_quantile, temporal_core_flag, log_rr, log_cost_R]``.
* Composite estimator: ``p_hat = w_f·p_f + w_b·p_b + w_r·p_r + w_e·p_e`` with
  ``Σw = 1`` (governed); a component whose ``n_obs`` is below its governed
  minimum (default 30) **shifts weight toward the Bayesian component
  (shrinkage)** — weights are never silently zeroed; when the AI ensemble is
  unavailable its ``p_e`` is dropped and its weight redistributed across the
  statistical components (never zero-substitution).
* Uncertainty / confidence: ``U = clip(0.5·U_cal + 0.3·U_ood + 0.2·U_dis, 0, 1)``
  and ``C = clip(1 − U, 0, 1)``; the P/U/C binding names ``C = 1 − max(U)``
  over the six named components — both laws are computed and reported, with
  the component vector as the source of truth.
* Economic utility: ``EU = p_hat·RR − (1−p_hat)·1 − cost_R − R_penalty`` with
  ``R_penalty`` 0/0/0.10/0.25/+∞ by risk state; if the spread is UNAVAILABLE
  then ``cost_R ≥ 0.05`` (frozen floor, ``cost_R_floor`` in the params file).
* Horizon/decay: ``H = min(4 × average holding period, H_max(tf))``, decay
  ``exp(−λ·age)`` with ``λ = 0.1`` per bar (aligned with ``Q_window``).
* Invalidation (immutable): exactly the seven reasons ``INV 1..7``; a record
  receives ``{state: INVALIDATED, reason, at, trigger_observation_id}`` and is
  **never silently deleted**.

No walk-forward/optimizer package exists in the freeze, so the calibrated
paths (Platt/isotonic ``p_hat``, WFO packages) are represented by an explicit
*package required* refusal — never a fabricated calibration.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from apex.config import load_params
from apex.errors import wave_out

CONTRACT_VERSION = "4.0.0"

# Frozen feature vector (Ch.13 §13.1) — order is normative.
X_FEATURES: Tuple[str, ...] = (
    "s_struct", "s_liq", "s_vol", "s_fvg", "s_ob", "trend_stack",
    "momentum_z", "regime_entropy", "vol_quantile", "temporal_core_flag",
    "log_rr", "log_cost_R",
)
X_FEATURE_COUNT = 12

BOOTSTRAP_P = 0.5
BOOTSTRAP_Q_FORECAST = 0.5

# INV 1..7 (canonical set, listed order) — immutable, never extended here.
INVALIDATION_REASONS: Tuple[str, ...] = (
    "TARGET_REACHED", "INVALIDATION", "HORIZON_EXPIRED", "REGIME_SHIFT",
    "QUALITY_DEGRADED", "PACKAGE_INVALIDATED", "SOURCE_STALE",
)

UNCERTAINTY_COMPONENTS: Tuple[str, ...] = (
    "disagreement", "sampling", "calibration", "data_quality", "regime_shift",
    "tail_risk",
)

# Ch.13 §13.1 composite weights (governed; equal split is the documented
# 4-component shape with Σw = 1 and is used only as the reported default).
COMPOSITE_WEIGHTS: Dict[str, float] = {
    "w_f": 0.30, "w_b": 0.30, "w_r": 0.30, "w_e": 0.10,
}
MIN_OBS_DEFAULT = 30
DECAY_LAMBDA_PER_BAR = 0.1
HORIZON_MULTIPLE = 4

# Calibration reporting thresholds (desirable values, not permissions).
CALIBRATION_THRESHOLDS: Dict[str, float] = {
    "brier_desirable": 0.25, "log_loss_desirable": 0.70,
    "rolling_calibration_error_rollback": 0.10,
}


class ForecastError(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}{('::' + detail) if detail else ''}")
        self.reason = reason
        self.detail = detail


def cost_r_floor() -> float:
    return float(load_params()["risk_defaults"]["cost_R_floor"])


def r_penalty_for(risk_state: str) -> float:
    """``R_penalty`` 0/0/0.10/0.25/+∞ by risk_state (Ch.13 §13.1, and the
    same Medium/High values carried by ``params/risk_defaults_v1.yaml``)."""
    s = str(risk_state).upper()
    table = {"NORISK": 0.0, "LOWRISK": 0.0, "MEDIUMRISK": 0.10,
             "HIGHRISK": 0.25, "CRITICALRISK": math.inf}
    if s not in table:
        raise ForecastError("RISK_STATE_QX", s)
    p = load_params()["risk_defaults"]
    if s == "MEDIUMRISK":
        return float(p["R_penalty_medium"])
    if s == "HIGHRISK":
        return float(p["R_penalty_high"])
    return table[s]


def h_max_tf(timeframe: str) -> Optional[int]:
    """``H_max(tf)`` is a governed parameter; the freeze documents no numeric
    table, so an unavailable ceiling is reported as UNAVAILABLE (never a
    guess) and the horizon falls back to ``4 × average holding period``."""
    c = load_params()["setup_weights"]
    table = c.get("forecast_h_max_bars") or {}
    if timeframe in table:
        return int(table[timeframe])
    return None


# ---------------------------------------------------------------------------
# Forecast event
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ForecastEvent:
    """The exact frozen event shape (PIT-stamped)."""

    target_condition: str
    stop_condition: str
    horizon: int
    entry_ref: str
    symbol: str
    timeframe: str
    timestamp: int

    def __post_init__(self) -> None:
        if self.horizon <= 0:
            raise ForecastError("HORIZON_QX", str(self.horizon))
        if not self.symbol or not self.timeframe:
            raise ForecastError("EVENT_KEY_QX")
        if not self.target_condition or not self.stop_condition:
            raise ForecastError("EVENT_CONDITIONS_QX",
                                "target and stop conditions are both mandatory")

    def to_dict(self) -> Dict[str, Any]:
        return {"target_condition": self.target_condition,
                "stop_condition": self.stop_condition,
                "horizon": self.horizon, "entry_ref": self.entry_ref,
                "symbol": self.symbol, "timeframe": self.timeframe,
                "timestamp": self.timestamp}


@dataclass
class ForecastRecord:
    """P/U/C record with the immutable invalidation contract."""

    event: ForecastEvent
    p_raw: float
    p_hat: float
    uncertainty: Dict[str, Any]
    u: float
    c: float
    q_forecast: float
    cost_r: float
    r_penalty: float
    eu: float
    eligible_environments: Tuple[str, ...]
    bootstrap_prior: bool
    contract_version: str = CONTRACT_VERSION
    state: str = "ACTIVE"
    invalidation: Optional[Dict[str, Any]] = None
    components: Dict[str, Any] = field(default_factory=dict)

    def invalidate(self, reason: str, *, at: int,
                   trigger_observation_id: str) -> "ForecastRecord":
        """The seven reasons are immutable: a record already invalidated is
        never re-labelled and never deleted (T_FORECAST_INV)."""
        if reason not in INVALIDATION_REASONS:
            raise ForecastError("FORECAST_INVALIDATION_REASON_QX", str(reason))
        if not trigger_observation_id:
            raise ForecastError("FORECAST_INVALIDATION_LINEAGE_QX",
                               "trigger_observation_id is mandatory")
        if self.invalidation is not None:
            raise ForecastError("FORECAST_INVALIDATION_IMMUTABLE",
                                f"already {self.invalidation['reason']}")
        self.invalidation = {"state": "INVALIDATED", "reason": reason,
                             "at": int(at),
                             "trigger_observation_id": trigger_observation_id}
        self.state = "INVALIDATED"
        return self

    def is_admissible(self, environment: str) -> bool:
        if self.state != "ACTIVE":
            return False
        return str(environment).upper() in self.eligible_environments

    def to_dict(self) -> Dict[str, Any]:
        return {"event": self.event.to_dict(), "P": self.p_hat,
                "U": self.u, "C": self.c, "U_components": dict(self.uncertainty),
                "Q_forecast": self.q_forecast, "cost_R": self.cost_r,
                "R_penalty": self.r_penalty, "EU": self.eu,
                "p_raw": self.p_raw, "bootstrap_prior": self.bootstrap_prior,
                "eligible_environments": list(self.eligible_environments),
                "state": self.state, "invalidation": self.invalidation,
                "components": dict(self.components),
                "contract_version": self.contract_version}


# ---------------------------------------------------------------------------
# The bootstrap P model (never a fabricated calibration)
# ---------------------------------------------------------------------------

def logistic_bootstrap_p(x: Mapping[str, float], *, beta0: float = 0.0,
                         beta: float = 0.0) -> float:
    """``p_raw = 1/(1+exp(−(β0+β·x)))`` with β=0, β0=0 ⇒ 0.5.

    The vector must be the complete frozen 12-feature vector: a missing
    feature is an UNAVAILABLE input, never a zero (SL-14).
    """
    missing = [k for k in X_FEATURES if k not in x]
    if missing:
        raise ForecastError("FORECAST_FEATURE_VECTOR_QX",
                            "missing " + ",".join(missing))
    extra = sorted(set(x) - set(X_FEATURES))
    if extra:
        raise ForecastError("FORECAST_FEATURE_VECTOR_QX", "unknown " +
                            ",".join(extra))
    for k in X_FEATURES:
        v = float(x[k])
        if v != v or v in (float("inf"), float("-inf")):
            raise ForecastError("FORECAST_FEATURE_NONFINITE_QX", k)
    z = beta0 + beta * sum(float(x[k]) for k in X_FEATURES)
    return 1.0 / (1.0 + math.exp(-z))


def uncertainty_from(u_cal: float, u_ood: float, u_dis: float) -> float:
    """``U = clip(0.5·U_cal + 0.3·U_ood + 0.2·U_dis, 0, 1)``."""
    for name, v in (("U_cal", u_cal), ("U_ood", u_ood), ("U_dis", u_dis)):
        if not (0.0 <= float(v) <= 1.0) or float(v) != float(v):
            raise ForecastError("UNCERTAINTY_INPUT_QX", name)
    return max(0.0, min(1.0, 0.5 * float(u_cal) + 0.3 * float(u_ood)
                        + 0.2 * float(u_dis)))


def economic_utility(p_hat: float, rr: float, cost_r: float,
                     r_penalty: float, *, spread_available: bool = True
                     ) -> Dict[str, float]:
    """``EU = p_hat·RR − (1−p_hat)·1 − cost_R − R_penalty`` (multiples of R).

    Spread UNAVAILABLE ⇒ ``cost_R ≥ cost_R_floor`` (0.05, frozen) is enforced
    here, so a missing spread can never improve the utility.
    """
    if not (0.0 <= p_hat <= 1.0):
        raise ForecastError("P_HAT_QX", str(p_hat))
    if rr < 0:
        raise ForecastError("RR_QX", str(rr))
    floor = cost_r_floor()
    cost = float(cost_r)
    if not spread_available:
        cost = max(cost, floor)
    eu = p_hat * rr - (1.0 - p_hat) * 1.0 - cost - r_penalty
    return {"EU": eu, "cost_R": cost, "cost_R_floor": floor,
            "spread_available": bool(spread_available),
            "R_penalty": r_penalty, "RR": rr, "P": p_hat}


def composite_estimate(components: Mapping[str, Mapping[str, Any]], *,
                       weights: Optional[Mapping[str, float]] = None,
                       min_obs: int = MIN_OBS_DEFAULT,
                       environment: str = "PAPER") -> Dict[str, Any]:
    """The calibrated, PIT-safe composite estimator.

    ``components`` keys are ``f``/``b``/``r``/``e``, each a mapping with
    ``p``, ``n_obs`` (and optionally ``confidence``/``uncertainty``).
    Rules: (1) Σw = 1 after normalization; (2) ``n_obs < min_obs`` shifts that
    component's weight to the Bayesian component (shrinkage, never zeroing);
    (3) an absent ``e`` has its weight redistributed across the statistical
    components; (4) a component whose ``p`` is missing is dropped from the
    numerator **and** the denominator (no zero-substitution) and reported.
    """
    w = dict(weights or COMPOSITE_WEIGHTS)
    unknown = sorted(set(w) - {"w_f", "w_b", "w_r", "w_e"})
    if unknown:
        raise ForecastError("COMPOSITE_WEIGHT_QX", ",".join(unknown))
    present: Dict[str, float] = {}
    dropped: List[str] = []
    label = {"f": "w_f", "b": "w_b", "r": "w_r", "e": "w_e"}
    for key in ("f", "b", "r", "e"):
        comp = components.get(key)
        if not comp or comp.get("p") is None:
            dropped.append(key)
            continue
        p = float(comp["p"])
        if not (0.0 <= p <= 1.0):
            raise ForecastError("COMPONENT_P_QX", key)
        present[key] = w[label[key]]
    if not present:
        # Fail closed: with no component there is no forecast. This is the
        # vacuous-pass guard of the forecast layer (mirrors Ch.8 §8.0).
        return {"p_hat": None, "weights": {}, "dropped": dropped,
                "shrinkage": [], "reason": "FORECAST_NO_COMPONENTS",
                "eligible_environments": (), "state": "UNAVAILABLE"}
    # ensemble unavailable ⇒ redistribute its weight across the statistical
    # components (never zero-substitution)
    if "e" not in present and "e" not in dropped:
        dropped.append("e")
    if "e" not in present:
        stat = [k for k in present if k != "e"]
        if stat:
            share = w["w_e"] / len(stat)
            for k in stat:
                present[k] += share
            present.pop("e", None)
    # small-sample shrinkage toward the Bayesian component
    shrinkage: List[str] = []
    if "b" in present:
        for k in [x for x in present if x != "b"]:
            n = int(components[k].get("n_obs", 0))
            if n < min_obs:
                shift = present[k] / 2.0
                present[k] -= shift
                present["b"] += shift
                shrinkage.append(k)
    total = sum(present.values())
    if total <= 0:
        raise ForecastError("COMPOSITE_WEIGHTS_EMPTY_QX")
    weights_n = {k: v / total for k, v in present.items()}
    p_hat = sum(weights_n[k] * float(components[k]["p"]) for k in weights_n)
    u_cal = max(float(c.get("uncertainty", 0.0)) for c in components.values()
                if c) if components else 0.0
    max_c = max(float(c.get("confidence", 0.0)) for c in components.values()
                if c) if components else 0.0
    u = uncertainty_from(u_cal, u_cal, 1.0 - max_c)
    c_val = max(0.0, min(1.0, 1.0 - u))
    return {"p_hat": p_hat, "weights": weights_n, "dropped": dropped,
            "shrinkage": shrinkage, "U": u, "C": c_val,
            "reason": "COMPOSITE_OK", "state": "ACTIVE"}


def horizon_bars(average_holding_period: int, timeframe: str) -> Dict[str, Any]:
    """``H = min(4 × avg holding period, H_max(tf))`` with a documented
    UNAVAILABLE ceiling (never an invented one)."""
    if average_holding_period <= 0:
        raise ForecastError("HORIZON_INPUT_QX", str(average_holding_period))
    candidate = HORIZON_MULTIPLE * int(average_holding_period)
    h_max = h_max_tf(timeframe)
    if h_max is None:
        return {"horizon": candidate, "h_max": None,
                "reason": "H_MAX_UNAVAILABLE_GOVERNED",
                "governed_fallback": "4 × average holding period"}
    return {"horizon": min(candidate, h_max), "h_max": h_max,
            "reason": "HORIZON_CAPPED", "governed_fallback": None}


def decay(age_bars: float, lam: float = DECAY_LAMBDA_PER_BAR) -> float:
    """Forecast decay ``exp(−λ·age)``, λ = 0.1 per bar (aligned Q_window)."""
    if age_bars < 0 or lam <= 0:
        raise ForecastError("DECAY_INPUT_QX", f"age={age_bars} λ={lam}")
    return math.exp(-lam * age_bars)


# ---------------------------------------------------------------------------
# Forecast construction
# ---------------------------------------------------------------------------

def build_forecast(event: ForecastEvent, *, x: Mapping[str, float],
                   p_hat: Optional[float] = None,
                   uncertainty: Optional[Mapping[str, float]] = None,
                   q_forecast: Optional[float] = None,
                   rr: float = 1.0, cost_r: float = 0.0,
                   risk_state: str = "NORISK",
                   spread_available: bool = True,
                   package: Optional[Mapping[str, Any]] = None,
                   environment: str = "PAPER",
                   age_bars: float = 0.0) -> ForecastRecord:
    """Assemble the P/U/C record for one forecast event.

    Bootstrap-only rule (verbatim from §13.1): with no calibrated walk-forward
    package, ``p_raw = 0.5`` and the record is eligible for RESEARCH/PAPER (and
    BACKTEST) only — LIVE capital is refused deterministically, never silently
    degraded.
    """
    p_raw = logistic_bootstrap_p(x)
    bootstrap = package is None
    if p_hat is None:
        p_hat = float(package["p_hat"]) if (package and "p_hat" in package) \
            else p_raw
    if str(environment).upper() == "LIVE" and bootstrap:
        raise ForecastError("FORECAST_BOOTSTRAP_NOT_LIVE_ELIGIBLE",
                            "LIVE requires a calibrated package")
    supplied = dict(uncertainty or {})
    model = supplied.pop("model_version", None)
    snapshot = supplied.pop("e11_snapshot_id", None)
    if model is not None:
        if (model != "cp14_paper_bootstrap_uncertainty-v1"
                or environment != "PAPER" or not bootstrap or not snapshot
                or q_forecast not in (None, .5)):
            raise ForecastError("FORECAST_UNCERTAINTY_MODEL_QX", str(model))
        consumed = ("calibration", "ood", "disagreement")
        if supplied.get("calibration") != .5 or supplied.get("ood") != .5:
            raise ForecastError("FORECAST_UNCERTAINTY_MODEL_QX", "bootstrap constants")
    else:
        consumed = ("calibration", "data_quality", "disagreement")
    u_map = {}
    for k, value in supplied.items():
        if model and k not in consumed and value != {"state": "UNAVAILABLE"}:
            raise ForecastError("UNCERTAINTY_COMPONENT_QX", k)
        if k not in (*UNCERTAINTY_COMPONENTS, "ood"):
            raise ForecastError("UNCERTAINTY_COMPONENT_QX", k)
        if value == {"state": "UNAVAILABLE"} and k not in consumed:
            u_map[k] = value
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ForecastError("UNCERTAINTY_COMPONENT_QX", k)
        u_map[k] = float(value)
    if any(k not in u_map for k in consumed):
        raise ForecastError("FORECAST_UNCERTAINTY_UNAVAILABLE", ",".join(consumed))
    for k in UNCERTAINTY_COMPONENTS:
        u_map.setdefault(k, {"state": "UNAVAILABLE"})
    u = uncertainty_from(*(u_map[k] for k in consumed))
    u_structured = u
    c_val = 1.0 - u
    r_pen = r_penalty_for(risk_state)
    eu = economic_utility(p_hat, rr, cost_r, r_pen,
                         spread_available=spread_available)
    if q_forecast is None:
        q_forecast = BOOTSTRAP_Q_FORECAST if bootstrap else float(
            package.get("q_forecast", BOOTSTRAP_Q_FORECAST))
    if bootstrap:
        eligible = ("RESEARCH", "PAPER", "BACKTEST")
    else:
        eligible = ("RESEARCH", "PAPER", "BACKTEST", "LIVE")
    if str(environment).upper() == "LIVE" and bootstrap:
        # deterministic refusal (never a guess-based entry)
        raise ForecastError("FORECAST_BOOTSTRAP_NOT_LIVE_ELIGIBLE",
                            "LIVE capital requires a calibrated WFO package "
                            "(Setup Gates 10/12 fail until it exists)")
    return ForecastRecord(
        event=event, p_raw=p_raw, p_hat=float(p_hat),
        uncertainty=u_map, u=u, c=c_val, q_forecast=float(q_forecast),
        cost_r=eu["cost_R"], r_penalty=r_pen, eu=eu["EU"],
        eligible_environments=eligible, bootstrap_prior=bootstrap,
        components={"eu": eu, "decay": decay(age_bars),
                    "c_from_u": c_val, "u_structured": u_structured,
                    "uncertainty_model": model, "e11_snapshot_id": snapshot,
                    "horizon": event.horizon})


def require_calibrated_package(package: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Wave-Out seam: the optimizer-produced walk-forward package is not part
    of this freeze; asking for calibrated outputs raises, it never stubs."""
    if package is None:
        raise wave_out("optimizer_live_yaml_write",
                       "FORECAST_PACKAGE_NOT_IN_FREEZE")
    return dict(package)


def platt_or_isotonic_oos(*_args: Any, **_kw: Any) -> None:
    """``p_hat`` = Platt/isotonic OOS (never on the decision bar) — the OOS
    calibration machinery belongs to the optimizer phase and is Wave-Out."""
    raise wave_out("optimizer_live_yaml_write",
                   "FORECAST_OOS_CALIBRATION_NOT_IN_FREEZE")


__all__ = ["BOOTSTRAP_P", "BOOTSTRAP_Q_FORECAST", "CALIBRATION_THRESHOLDS",
           "COMPOSITE_WEIGHTS", "CONTRACT_VERSION", "DECAY_LAMBDA_PER_BAR",
           "HORIZON_MULTIPLE", "INVALIDATION_REASONS", "MIN_OBS_DEFAULT",
           "UNCERTAINTY_COMPONENTS", "X_FEATURES", "X_FEATURE_COUNT",
           "ForecastError", "ForecastEvent", "ForecastRecord",
           "build_forecast", "composite_estimate", "cost_r_floor", "decay",
           "economic_utility", "h_max_tf", "horizon_bars",
           "logistic_bootstrap_p", "platt_or_isotonic_oos",
           "require_calibrated_package", "r_penalty_for", "uncertainty_from"]
