"""E11 Regime Engine — Market Regime Classification (APEX_GEN5.md
L11671–12732; contract E11_Regime/4.0.0, schema v4.0.0).

Implements the full chapter in order: §2 vocabulary (X_t ∈ [0,1]^8, bias,
logits/softmax/entropy, T_ij Dirichlet, Gaussian emission η, Hamilton
filter ξ, EWMA μ/Σ λ=0.94, Mahalanobis Turbulence ~ χ²(df=8), BaseRate +
Wilson, hysteresis 3) · §3.1 norms A (180d min-max) / B (180d rolling
sigmoid) / C (momentum categorical → EWMA-smoothed numeric) + bias
w={H4:0.5, H1:0.3, M15:0.2} · §3.2 priority rule tree (K=9: CRISIS >
TRANSITION > EXPANSION > TREND_EXPANSION > TREND_CONTRACTION > TREND >
COMPRESSION > CHOP > RANGE) · §3.3 numerically-stable softmax with
NO probabilistic fallback (CONFIGURATION_INVALID / FAIL_CLOSED) · §3.4
48-candle delayed labeling + Dirichlet α=0.1 · §3.5 one global Gaussian
emission · §3.6 EWMA μ/Σ with +1e-6·I regularization · §3.7 Turbulence
χ² thresholds 15.5073/20.09/26.12 · §3.8 edges (H<L, V=0, gap, DST,
NaN/Inf) · §3.9 BaseRate Wilson CI · §4 streaming reference algorithm ·
§5 regime_state schema (additionalProperties:false — the live-regime gate
flag and H_norm therefore live in the run_engine wrapper, never inside
regime_state) · §6 parameter surface (params/e11_params_v4.yaml is
§9.5-canonical; runtime YAML wins, ADR-P2-008) · §8 battery helpers.

Contradiction log (filed in PHASE2_DECISION_LOG.md §B):
  ISSUE-CP5-009  §3.1 Method-A prose gives x=0.5 for a degenerate window
                 (max−min<ε); §4 pseudocode raises INVALID_E11_HISTORY.
                 Fail-closed pseudocode governs.
  ISSUE-CP5-010  §9 case study compares H_norm=H/ln9 against θ_H (0.73 >
                 0.65); §4 pseudocode, §6 (θ_H unit: nat) and §8.1 GF_01
                 (expected_H_lt 0.7 with expected_Q Q4, which the cascade
                 only grants for raw H < 0.65) compare RAW entropy in nats.
                 Pseudocode governs; H_norm is exposed as a wrapper-level
                 diagnostic only (the §5.1 schema forbids extra keys).
  ISSUE-CP5-011  §3.8 gap adjustment (expansion→1, structure_quality×0.7)
                 is absent from the §4 pseudocode; GF_09 requires it.
                 Implemented in the streaming wrapper post-normalization.
  ISSUE-CP5-012  §3.8 V=0 ⇒ Q1 with x6 moving-average fill, but GF_10
                 shows participation_raw=None ⇒ Q0 CONFIGURATION_INVALID.
                 Resolution: a missing/None required input key always fails
                 closed (Q0, pseudocode); an explicit zero-volume candle
                 (v==0 with participation_raw present or fillable) takes
                 the §3.8 path (fill + Q1 cap + EV_RGM_006).
  ISSUE-CP5-013  EV_RGM_007 is missing from the §5.4 event table but the
                 §4 pseudocode emits it for CONFIGURATION_INVALID /
                 FAIL_CLOSED. Pseudocode governs; the catalog carries it.
  ISSUE-CP5-014  μ0/Σ0/prev_mom initialization is unspecified. Chosen
                 deterministic PIT-safe seeds: μ0 = 0.5·1 (neutral center),
                 Σ0 = 0.05·I (the §9 case-study covariance diagonal scale)
                 + 1e-6·I regularization, prev_mom = 0.5 (the NEUTRAL
                 stationary point, matching case-study candle 1 x8=0.5).
  ISSUE-CP5-015  §8.1 GF_01 expected_vector.momentum_state=0.62 is not
                 reproducible from the Method-C recursion with any neutral
                 seed (0.94·0.5+0.06·1 = 0.53); fixtures are re-derived
                 per §9.5-2 and the document value is logged, never used.
  ISSUE-CP5-016  §8.1 GF_01 expected_state TREND_EXPANSION contradicts its
                 OWN expected_vector through the §3.2 tree (expansion 0.76
                 ≥ 0.6 ∧ participation 0.86 ≥ 0.4 fire EXPANSION first).
                 Re-derived fixture keeps the document raw inputs but a
                 participation window yielding x_part < 0.4, so the
                 expected state is reachable and asserted.
  ISSUE-CP5-017  The §4 pseudocode's EV_RGM_003 guard (hist_raw[-1] !=
                 confirmed_state under status CONFIRMED) is provably dead
                 under its own hysteresis_manager; the §5.4 event table and
                 the §9 case study (candle 6 emits EV003) govern — the
                 event fires on the confirming candle where the CONFIRMED
                 label actually changes (last_confirmed tracking).
  ISSUE-CP5-018  §8.1 GF_05 expected CHOP ∧ Q3 is unreachable: Q3 requires
                 H ≥ 0.65 (⇒ TRANSITION in the tree) or Tur ≥ 15.5 (⇒
                 CRISIS in the tree). Re-derived as CHOP ∧ Q4 with the
                 document inputs kept.
  ISSUE-CP5-019  The §4 pseudocode hysteresis_manager's trailing else
                 confirms a new label after only 2 consecutive raw labels,
                 contradicting §2 ("3 consecutive candles") and its own
                 first branch. §2 governs; the engine tracks the last
                 CONFIRMED label so SUSPECTED candles retain it.

Wave-Out (§9.5-9): next-regime forecast and adaptive ATR E04↔E11 raise
WaveOutError; they are never implemented.
"""

from __future__ import annotations

import datetime
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from apex.data_catalog.contracts import EvidenceEvent, MarketObservation
from apex.engines.base import EngineBase, LifecycleState
from apex.errors import wave_out
from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import sha256_hex
from apex.identity.snapshot import canonical_snapshot_id
from apex.identity.uuid_v7 import uuid_v7
from apex.quality.numerical import eps_for_engine

# ---------------------------------------------------------------------------
# §2 — constants and vocabulary
# ---------------------------------------------------------------------------
ENGINE = "E11_Regime"
CONTRACT_VERSION = "4.0.0"
CONTRACT_LABEL = f"{ENGINE}/{CONTRACT_VERSION}"
SCHEMA_VERSION = "v4.0.0"
ANALYST_VERSION = "4.0.0+" + "0" * 40
EPS = float(eps_for_engine("E11"))       # 1e-8 per Global Contracts §2.2

K = 9                                    # registry-invariant (§4 assertion)
D = 8                                    # X_t dimensionality
REGIMES: Tuple[str, ...] = (
    "CRISIS", "TRANSITION", "EXPANSION", "TREND_EXPANSION",
    "TREND_CONTRACTION", "TREND", "COMPRESSION", "CHOP", "RANGE")
STATE_ENUM: Tuple[str, ...] = REGIMES + ("AMBIGUOUS",)
Q_TAGS: Tuple[str, ...] = ("Q0", "Q1", "Q2", "Q3", "Q4", "Q5")
TRANSITION_STATUSES: Tuple[str, ...] = ("NONE", "SUSPECTED", "CONFIRMED")
VECTOR_KEYS: Tuple[str, ...] = (
    "trendiness", "volatility", "compression", "expansion",
    "liquidity_stability", "participation", "structure_quality",
    "momentum_state")

LAMBDA_EWMA = 0.94                       # RiskMetrics half-life ≈ 11.2
ALPHA_DIRICHLET = 0.1
DELAY_BARS = 48
THETA_H = 0.65                           # nats (ISSUE-CP5-010)
TH_TURB_95 = 15.5073                     # χ²(0.95, df=8)
TH_TURB_99 = 20.09                       # χ²(0.99, df=8)
TH_TURB_999 = 26.12                      # χ²(0.999, df=8)
HYSTERESIS_BARS = 3
ROLLING_WINDOW_DAYS = 180
W_180D_H1 = 4320                         # 180d of H1 candles
COV_REGULARIZATION = 1e-6                # Σ += 1e-6·I (§3.6)
BIAS_WEIGHTS: Dict[str, float] = {"H4": 0.5, "H1": 0.3, "M15": 0.2}
MOMENTUM_CATEGORY_MAP = {"IMPULSIVE": 1.0, "NEUTRAL": 0.0, "EXHAUSTED": -1.0}

# §6 controlled parameter surface (defaults per the chapter table; the
# runtime YAML params/e11_params_v4.yaml is §9.5-canonical and wins).
E11_DEFAULTS: Dict[str, Any] = {
    "entropy_threshold": 0.65,
    "trend_threshold": 0.6,
    "expansion_threshold": 0.5,
    "expansion_state_threshold": 0.6,     # §3.2 EXPANSION branch literal
    "compression_threshold": 0.6,
    "participation_threshold": 0.4,       # §3.2 EXPANSION branch literal
    "participation_low": 0.25,
    "liquidity_low": 0.3,
    "volatility_crisis": 0.85,
    "volatility_compression_max": 0.4,    # §3.2 COMPRESSION branch literal
    "trendiness_range_max": 0.35,         # §3.2 RANGE bias branch literal
    "turbulence_threshold": 15.5073,
    "transition_confirm_bars": 3,
    "ewma_lambda": 0.94,
    "dirichlet_alpha": 0.1,
    "delayed_label_bars": 48,
    "rolling_window_days": 180,
    "bias_neutral_band": 0.2,
    "shock_gap_atr_mult": 2.0,
    "gap_structure_factor": 0.7,          # §3.8 gap edge literal
    "compression_atr_z_boost": 0.15,      # §3.1 Method-A adjustment
    "compression_atr_z_threshold": -1.0,
    "quality_H_Q2": 0.8,
    "quality_Tur_Q2": 20.0,
    "quality_Tur_Q3": 15.5,
    "quality_H_Q5": 0.4,
    "quality_Tur_Q5": 8.0,
    "base_rate_min_n": 30,                # §8.5 cap-at-Q3 sample floor
    "covariance_regularization": 1e-6,
    "K": 9,
}
# YAML (§9.5-canonical) key → internal §6 surface key.
# D49: quality_H_Q2 and quality_H_Q5 become governed YAML values.
YAML_KEY_MAP = {
    "K": "K",
    "theta_H": "entropy_threshold",
    "lambda_ewma": "ewma_lambda",
    "hysteresis_candles": "transition_confirm_bars",
    "dirichlet_alpha": "dirichlet_alpha",
    "transition_delay_candles": "delayed_label_bars",
    "W_180d_H1": "rolling_window_h1",
    "quality_H_Q2": "quality_H_Q2",
    "quality_H_Q5": "quality_H_Q5",
}

# §5.4 event catalog (+ EV_RGM_007 from the §4 pseudocode, ISSUE-CP5-013).
EVENT_CATALOG: Dict[str, Dict[str, str]] = {
    "EV_RGM_001": {"name": "Regime_State_Update",
                   "condition": "every accepted candle"},
    "EV_RGM_002": {"name": "Transition_Suspected",
                   "condition": "raw != confirmed, repeat count < 3"},
    "EV_RGM_003": {"name": "Transition_Confirmed",
                   "condition": "3-candle hysteresis passed"},
    "EV_RGM_004": {"name": "Regime_Ambiguous", "condition": "H >= θ_H"},
    "EV_RGM_005": {"name": "Turbulence_Alert", "condition": "Tur >= 15.5"},
    "EV_RGM_006": {"name": "Data_Degraded",
                   "condition": "H<L, V=0, contract mismatch, gap/DST"},
    "EV_RGM_007": {"name": "Configuration_Invalid",
                   "condition": "FAIL_CLOSED — no probabilistic fallback"},
}


class EngineParams:
    """Frozen §6 surface; unknown keys rejected (fail-closed). D49: theta_H range [0.3, ln9]."""

    def __init__(self, overrides: Optional[Dict[str, Any]] = None) -> None:
        values = dict(E11_DEFAULTS)
        for key, val in (overrides or {}).items():
            if key not in E11_DEFAULTS:
                raise ValueError(f"UNKNOWN_E11_PARAM_QX: {key}")
            values[key] = val
        if int(values["K"]) != K or len(REGIMES) != K:
            raise ValueError(
                "CONFIGURATION_INVALID: E11 canonical regime registry must "
                "contain exactly 9 classes (T-E11-K9 dimensionality law)")
        # D49: theta_H (entropy_threshold) range widened 0.3-0.9 to 0.3-ln9
        eth = values.get("entropy_threshold")
        if eth is not None:
            try:
                fv = float(eth)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"CONFIGURATION_INVALID: entropy_threshold not a number: {eth}") from exc
            if not math.isfinite(fv) or not (0.3 <= fv <= math.log(9)):
                raise ValueError(
                    f"CONFIGURATION_INVALID: entropy_threshold {fv} outside [0.3, ln9] per D49"
                )
        self._v = values
        for name, val in values.items():
            setattr(self, name, val)

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._v)


def param_hash(params: EngineParams) -> str:
    """Deterministic 12-hex parameter fingerprint (snapshot payload key)."""
    return sha256_hex(canonical_json(params.as_dict()).encode("utf-8"))[:12]


def get_params(overrides: Optional[Dict[str, Any]] = None,
               use_yaml: bool = True) -> EngineParams:
    """§6 + ADR-P2-008: params/e11_params_v4.yaml is §9.5-canonical — the
    runtime YAML values win over the code defaults; explicit ``overrides``
    win over both. A YAML value that disagrees with the chapter default is
    still applied (governed change) but recorded in ``yaml_assertions``."""
    merged: Dict[str, Any] = {}
    assertions: List[str] = []
    if use_yaml:
        from apex.config import load_params
        try:
            raw_yaml = dict(load_params().e11_params)
        except Exception:                      # pragma: no cover - locked
            raw_yaml = {}
        for ykey, internal in YAML_KEY_MAP.items():
            if ykey not in raw_yaml:
                continue
            val = raw_yaml[ykey]
            if internal == "rolling_window_h1":
                # W_180d_H1 is the H1 candle count of the 180d window;
                # it re-asserts rolling_window_days (4320 = 180·24).
                days = int(val) // 24 if int(val) % 24 == 0 else None
                if days is None or days != \
                        int(E11_DEFAULTS["rolling_window_days"]):
                    assertions.append(
                        f"W_180d_H1={val!r} implies {days}d — recorded; "
                        f"rolling_window_days stays 180 unless overridden")
                else:
                    merged["rolling_window_days"] = days
                continue
            default = E11_DEFAULTS.get(internal)
            if default is not None and val != default:
                assertions.append(
                    f"{ykey}={val!r} overrides chapter default "
                    f"{default!r} (ADR-P2-008: runtime YAML wins)")
            if internal in E11_DEFAULTS:
                merged[internal] = val
    if overrides:
        merged.update(overrides)
    params = EngineParams(merged)
    params.yaml_assertions = assertions        # type: ignore[attr-defined]
    return params


# ---------------------------------------------------------------------------
# §3.1 — PIT-safe normalization methods
# ---------------------------------------------------------------------------
def rolling_minmax_norm(raw_t: float, window: Sequence[float]) -> float:
    """Method A: 180-day rolling min-max over history strictly ≤ t−1.
    Degenerate/short/non-finite history fails closed (ISSUE-CP5-009)."""
    if not window or len(window) < 10:
        raise ValueError("INVALID_E11_HISTORY: rolling_minmax_norm requires "
                         "at least 10 prior samples")
    vals = [float(v) for v in window]
    mn, mx = min(vals), max(vals)
    if (not math.isfinite(float(raw_t)) or not math.isfinite(mn)
            or not math.isfinite(mx) or mx <= mn):
        raise ValueError("INVALID_E11_HISTORY: rolling_minmax_norm requires "
                         "finite non-degenerate history")
    return max(0.0, min(1.0, (float(raw_t) - mn) / (mx - mn)))


def rolling_method_b_reference(raw_t: float, window: Sequence[float]) -> Tuple[float, float]:
    """Shared Method-B mean/sigma and original minimum/degeneracy guards.

    Caller supplies lag-one history capped by E11's existing window policy.
    D26-A reuses this reference for the ATR14 consumer projection, without
    changing the pre-existing sigmoid normalization's numerical behavior.
    """
    if not window or len(window) < 20:
        raise ValueError("INVALID_E11_HISTORY: rolling_sigmoid_norm requires "
                         "at least 20 prior samples")
    vals = [float(v) for v in window]
    mu = float(np.mean(vals))
    raw_var = float(np.mean([(v - mu) ** 2 for v in vals]))
    if not math.isfinite(float(raw_t)) or not math.isfinite(mu) \
            or math.sqrt(raw_var) <= EPS:
        # degenerate (constant) history ⇒ fail closed, per the §4 guard
        raise ValueError("INVALID_E11_HISTORY: rolling_sigmoid_norm requires "
                         "finite non-degenerate history")
    sigma = math.sqrt(raw_var + EPS)       # §3.1 Method-B ε-regularized σ
    return mu, sigma


def rolling_sigmoid_norm(raw_t: float, window: Sequence[float]) -> float:
    """Method B: 180-day rolling sigmoid standardization (robust to
    outliers); z clipped to ±10 for numerical stability."""
    mu, sigma = rolling_method_b_reference(raw_t, window)
    z = (float(raw_t) - mu) / sigma
    z = max(-10.0, min(10.0, z))
    return 1.0 / (1.0 + math.exp(-z))


def map_momentum_state(cat: str, prev_num: float,
                       lam: float = LAMBDA_EWMA) -> float:
    """Method C: categorical {IMPULSIVE, NEUTRAL, EXHAUSTED} → {1, 0, −1} →
    (v+1)/2 ∈ {0, 0.5, 1}, EWMA-smoothed with λ=0.94, clipped to [0,1]."""
    if not isinstance(cat, str) or cat.upper() not in MOMENTUM_CATEGORY_MAP:
        raise ValueError("INVALID_E11_FEATURE: momentum_state_raw must be "
                         "IMPULSIVE, NEUTRAL, or EXHAUSTED")
    if not math.isfinite(float(prev_num)) or not 0.0 <= float(prev_num) <= 1.0:
        raise ValueError("INVALID_E11_FEATURE: prev_mom must be finite in "
                         "[0,1]")
    v_num = MOMENTUM_CATEGORY_MAP[cat.upper()]
    x_raw = (v_num + 1.0) / 2.0
    x_smooth = lam * float(prev_num) + (1.0 - lam) * x_raw
    return float(max(0.0, min(1.0, x_smooth)))


def compute_bias(bias_per_tf: Dict[str, float],
                 weights: Optional[Dict[str, float]] = None) -> float:
    """b_t = Σ w_tf·bias_tf / Σ w_tf, w = {H4:0.5, H1:0.3, M15:0.2}.
    Any missing/non-finite required TF fails closed (CONFIGURATION_INVALID)."""
    if weights is None:
        weights = dict(BIAS_WEIGHTS)
    required = ("H4", "H1", "M15")
    if any(tf not in bias_per_tf
           or not math.isfinite(float(bias_per_tf[tf])) for tf in required):
        raise ValueError("CONFIGURATION_INVALID: E11 bias_per_TF requires "
                         "finite H4, H1, and M15 values")
    tot = 0.0
    wsum = 0.0
    for tf, w in weights.items():
        b = max(-1.0, min(1.0, float(bias_per_tf[tf])))
        tot += float(w) * b
        wsum += float(w)
    if wsum <= 0.0:
        raise ValueError("CONFIGURATION_INVALID: E11 bias weights must have "
                         "positive total weight")
    return tot / wsum


REQUIRED_IC_INPUTS: Tuple[str, ...] = (
    "trendiness_raw", "vol_ratio", "expansion_raw", "level_density",
    "participation_raw", "structure_score", "momentum_state_raw",
    "bias_per_TF", "atr_z")


def projected_liquidity_norm(raw: float, history: Sequence[float]) -> float:
    """Owner D26-B Method-A degenerate reference, only for the new E02 IC.

    Legacy callers keep ISSUE-CP5-009 behavior. Short/nonfinite references
    still refuse; only a finite constant reference has the documented 0.5.
    """
    values = [float(value) for value in history]
    if len(values) >= 10 and math.isfinite(float(raw)) and all(math.isfinite(v) for v in values):
        if max(values) == min(values):
            return 0.5
    return rolling_minmax_norm(raw, history)


def compute_state_vector(inputs: Dict[str, Any],
                         history: Dict[str, List[float]],
                         prev_mom: float) -> Tuple[Dict[str, float], float]:
    """§3.1 full X_t ∈ [0,1]^8 + bias. Every required IC input present and
    finite; non-finite or missing ⇒ fail closed (never a synthetic 0.5)."""
    missing = [k for k in REQUIRED_IC_INPUTS
               if k not in inputs or inputs[k] is None]
    if missing:
        raise ValueError(
            f"CONFIGURATION_INVALID: missing required E11 inputs: {missing}")
    raw_trend = float(inputs["trendiness_raw"])
    raw_vol_ratio = float(inputs["vol_ratio"])
    raw_exp = float(inputs["expansion_raw"])
    raw_liq = float(inputs.get("liquidity_raw", inputs["level_density"]))
    raw_part = float(inputs["participation_raw"])
    raw_sq = float(inputs["structure_score"])
    atr_z = float(inputs["atr_z"])
    if not all(math.isfinite(x) for x in
               (raw_trend, raw_vol_ratio, raw_exp, raw_liq, raw_part, raw_sq,
                atr_z)):
        raise ValueError("INVALID_E11_FEATURE: non-finite raw input")

    x_trend = rolling_sigmoid_norm(raw_trend, history.get("trend", []))
    x_vol = rolling_minmax_norm(raw_vol_ratio, history.get("vol", []))
    x_comp = 1.0 - x_vol                   # base definition
    if atr_z < E11_DEFAULTS["compression_atr_z_threshold"]:
        x_comp = min(1.0, x_comp + E11_DEFAULTS["compression_atr_z_boost"])
    x_exp = rolling_sigmoid_norm(raw_exp, history.get("exp", []))
    x_liq = (projected_liquidity_norm(raw_liq, history.get("liq", []))
             if "liquidity_raw" in inputs else rolling_minmax_norm(raw_liq, history.get("liq", [])))
    if "oi_state" in inputs:
        # Owner D23: shared train/runtime participation mapping, no OI=0.
        x_part = (1.0 / (1.0 + math.exp(-raw_part)) if raw_part >= 0
                  else math.exp(raw_part) / (1.0 + math.exp(raw_part)))
    else:
        x_part = rolling_sigmoid_norm(raw_part, history.get("part", []))
    x_sq = rolling_sigmoid_norm(raw_sq, history.get("sq", []))
    x_mom = map_momentum_state(str(inputs["momentum_state_raw"]), prev_mom)
    bias = compute_bias(dict(inputs["bias_per_TF"]))

    vec = {"trendiness": x_trend, "volatility": x_vol, "compression": x_comp,
           "expansion": x_exp, "liquidity_stability": x_liq,
           "participation": x_part, "structure_quality": x_sq,
           "momentum_state": x_mom}
    for key in vec:
        if not math.isfinite(vec[key]):
            raise ValueError(f"INVALID_E11_FEATURE: non-finite {key}")
        vec[key] = max(0.0, min(1.0, vec[key]))
    return vec, bias


def vector_to_array(vec: Dict[str, float]) -> np.ndarray:
    return np.array([vec[k] for k in VECTOR_KEYS], dtype=float)


# ---------------------------------------------------------------------------
# §3.3 — softmax classifier (canonical: d=8 in, K=9 out, no fallback)
# ---------------------------------------------------------------------------
def compute_logits_softmax(vec: Dict[str, float], W: np.ndarray,
                           b: np.ndarray
                           ) -> Tuple[List[float], List[float], float]:
    """z_r = W_r·X + b_r; numerically-stable softmax (max-subtracted);
    H = −Σ p ln p (raw nats). Any incompatible tensor or simplex violation
    ⇒ CONFIGURATION_INVALID — no uniform/random/clipped/synthetic fallback."""
    W = np.asarray(W, dtype=float)
    b = np.asarray(b, dtype=float)
    if W.shape != (K, D) or b.shape != (K,):
        raise ValueError("CONFIGURATION_INVALID: E11 requires W=(9,8) and "
                         "b=(9,)")
    if not np.all(np.isfinite(W)) or not np.all(np.isfinite(b)):
        raise ValueError("CONFIGURATION_INVALID: non-finite E11 W/b")
    x = vector_to_array(vec)
    if x.shape != (D,) or not np.all(np.isfinite(x)):
        raise ValueError("CONFIGURATION_INVALID: E11 state vector must be "
                         "finite with shape (8,)")
    logits = W @ x + b
    m = float(np.max(logits))
    exp_l = np.exp(logits - m)
    sum_exp = float(np.sum(exp_l))
    if not math.isfinite(sum_exp) or sum_exp <= 0.0:
        raise ValueError("CONFIGURATION_INVALID: non-finite E11 softmax "
                         "denominator")
    probs = exp_l / sum_exp
    prob_sum = float(np.sum(probs))
    if not math.isfinite(prob_sum) or prob_sum <= 0.0:
        raise ValueError("CONFIGURATION_INVALID: invalid E11 probability "
                         "simplex")
    probs = probs / prob_sum
    final_sum = float(np.sum(probs))
    if not math.isfinite(final_sum) or not math.isclose(
            final_sum, 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("CONFIGURATION_INVALID: E11 probability simplex "
                         "invariant violated")
    H = -float(np.sum([p * math.log(p) for p in probs if p > 0.0]))
    return [float(z) for z in logits], [float(p) for p in probs], H


def entropy_normalized(H: float) -> float:
    """H_norm = H / ln K ∈ [0,1] — wrapper-level diagnostic only
    (ISSUE-CP5-010; the §5.1 schema forbids extra regime_state keys)."""
    return float(H) / math.log(K)


# ---------------------------------------------------------------------------
# §3.2 — priority-ordered rule tree
# ---------------------------------------------------------------------------
def rule_tree_priority(vec: Dict[str, float], bias: float, H: float,
                       turb: float, probs: List[float],
                       params: Optional[EngineParams] = None
                       ) -> Dict[str, Any]:
    """Risk-driven ordering CRISIS > TRANSITION > EXPANSION >
    TREND_EXPANSION > TREND_CONTRACTION > TREND > COMPRESSION > CHOP >
    RANGE. Entropy is compared in raw nats (ISSUE-CP5-010)."""
    p = params or EngineParams()
    v = vec
    if turb >= float(p.turbulence_threshold) \
            or v["volatility"] >= float(p.volatility_crisis):
        state = "CRISIS"
        reason = (f"turbulence={turb:.2f} vol={v['volatility']:.2f} >=thr")
    elif H >= float(p.entropy_threshold):
        state = "TRANSITION"
        reason = f"entropy={H:.3f}>= {float(p.entropy_threshold)}"
    elif v["expansion"] >= float(p.expansion_state_threshold) \
            and v["participation"] >= float(p.participation_threshold):
        state = "EXPANSION"
        reason = (f"expansion {v['expansion']:.2f} + part "
                  f"{v['participation']:.2f}")
    elif v["trendiness"] >= float(p.trend_threshold) \
            and v["expansion"] >= float(p.expansion_threshold):
        state = "TREND_EXPANSION"
        reason = f"trend {v['trendiness']:.2f}+exp {v['expansion']:.2f}"
    elif v["trendiness"] >= float(p.trend_threshold) \
            and v["compression"] >= float(p.compression_threshold):
        state = "TREND_CONTRACTION"
        reason = f"trend+compression {v['compression']:.2f}"
    elif v["trendiness"] >= float(p.trend_threshold):
        state = "TREND"
        reason = f"trendiness {v['trendiness']:.2f}"
    elif v["compression"] >= float(p.compression_threshold) \
            and v["volatility"] <= float(p.volatility_compression_max):
        state = "COMPRESSION"
        reason = f"compression {v['compression']:.2f} vol low"
    elif v["participation"] <= float(p.participation_low) \
            and v["liquidity_stability"] <= float(p.liquidity_low):
        state = "CHOP"
        reason = (f"part {v['participation']:.2f} liq "
                  f"{v['liquidity_stability']:.2f}")
    else:
        if abs(bias) < float(p.bias_neutral_band) \
                and v["trendiness"] < float(p.trendiness_range_max):
            state, reason = "RANGE", f"no trend bias {bias:.2f}"
        else:
            state, reason = "RANGE", "default_no_trend"
    return {"state": state, "reason": reason, "bias": bias, "entropy": H,
            "turbulence": turb, "probs": probs}


# ---------------------------------------------------------------------------
# §3.6/§3.7 — EWMA reference state, Turbulence, Gaussian emission
# ---------------------------------------------------------------------------
def ewma_update(mu_prev: np.ndarray, Sigma_prev: np.ndarray, x_t: np.ndarray,
                lam: float = LAMBDA_EWMA,
                reg: float = COV_REGULARIZATION
                ) -> Tuple[np.ndarray, np.ndarray]:
    """μ_{t+1} = λμ_t + (1−λ)X_t; Σ_{t+1} = λΣ_t + (1−λ)·diff·diffᵀ + εI.
    PIT: classifying candle t uses (μ_{t−1}, Σ_{t−1}); X_t only updates the
    NEXT state."""
    mu_prev = np.asarray(mu_prev, dtype=float)
    Sigma_prev = np.asarray(Sigma_prev, dtype=float)
    x_t = np.asarray(x_t, dtype=float)
    if mu_prev.shape != (D,) or Sigma_prev.shape != (D, D) \
            or not np.all(np.isfinite(mu_prev)) \
            or not np.all(np.isfinite(Sigma_prev)):
        raise ValueError("CONFIGURATION_INVALID: E11 global mu/Sigma shape "
                         "or finiteness invalid")
    mu_new = lam * mu_prev + (1.0 - lam) * x_t
    diff = x_t - mu_prev
    Sigma_new = lam * Sigma_prev + (1.0 - lam) * np.outer(diff, diff)
    Sigma_new = Sigma_new + reg * np.eye(D)
    return mu_new, Sigma_new


def cholesky_or_fail(Sigma: np.ndarray) -> np.ndarray:
    """Deterministic fail-closed numerical policy: Σ must already carry the
    canonical +1e-6·I regularization; a failed Cholesky is a configuration
    error, never silently patched."""
    Sigma = np.asarray(Sigma, dtype=float)
    if Sigma.shape != (D, D) or not np.all(np.isfinite(Sigma)):
        raise ValueError("CONFIGURATION_INVALID: E11 covariance dimensions "
                         "invalid")
    try:
        return np.linalg.cholesky(Sigma)
    except np.linalg.LinAlgError as exc:
        raise ValueError("CONFIGURATION_INVALID: E11 covariance is not "
                         "positive definite after canonical "
                         "regularization") from exc


def mahalanobis_turbulence(x_t: np.ndarray, mu_prev: np.ndarray,
                           Sigma_prev: np.ndarray) -> float:
    """Tur_t = (X_t−μ_{t−1})ᵀ Σ_{t−1}⁻¹ (X_t−μ_{t−1}) ~ χ²(df=8) under H0."""
    x_t = np.asarray(x_t, dtype=float)
    mu_prev = np.asarray(mu_prev, dtype=float)
    if x_t.shape != (D,) or mu_prev.shape != (D,):
        raise ValueError("CONFIGURATION_INVALID: E11 covariance dimensions "
                         "invalid")
    L = cholesky_or_fail(Sigma_prev)
    diff = x_t - mu_prev
    y = np.linalg.solve(L, diff)
    tur = float(np.dot(y, y))
    if not math.isfinite(tur):
        raise ValueError("CONFIGURATION_INVALID: non-finite E11 turbulence")
    return tur


def gaussian_log_emission(x_t: np.ndarray, mu_prev: np.ndarray,
                          Sigma_prev: np.ndarray) -> float:
    """§3.5 ln η = −½[d·ln2π + ln|Σ| + Mahalanobis²] — one global Gaussian
    reference state is canonical (no regime-specific fork)."""
    L = cholesky_or_fail(Sigma_prev)
    log_det = 2.0 * float(np.sum(np.log(np.diag(L))))
    tur = mahalanobis_turbulence(x_t, mu_prev, Sigma_prev)
    return -0.5 * (D * math.log(2.0 * math.pi) + log_det + tur)


# ---------------------------------------------------------------------------
# §3.4/§2 — Hamilton filter, delayed labeling, Dirichlet T estimation
# ---------------------------------------------------------------------------
def hamilton_filter_step(xi_prev: np.ndarray, T: np.ndarray,
                         eta: np.ndarray
                         ) -> Tuple[np.ndarray, np.ndarray]:
    """ξ_{t+1|t} = Tᵀξ_{t|t−1} (normalized); ξ_{t|t} ∝ ξ_{t+1|t} ⊙ η_t.
    With the canonical single global Gaussian, η is regime-independent and
    the update reduces to the normalized Markov prediction."""
    xi_prev = np.asarray(xi_prev, dtype=float)
    T = np.asarray(T, dtype=float)
    eta = np.asarray(eta, dtype=float)
    if xi_prev.shape != (K,) or T.shape != (K, K) or eta.shape != (K,):
        raise ValueError("CONFIGURATION_INVALID: E11 Hamilton filter "
                         "dimensionality (K=9)")
    xi_pred = T.T @ xi_prev
    xi_pred = xi_pred / (float(np.sum(xi_pred)) + EPS)
    num = xi_pred * eta
    den = float(np.sum(num)) + EPS
    xi_filt = num / den
    return xi_pred, xi_filt


def apply_delayed_labels(rule_labels: Sequence[str],
                         confirmed: Sequence[bool],
                         delay: int = DELAY_BARS) -> List[str]:
    """§3.4 r_t^final = r_t^rule if confirmed by BOS/CHoCH in [t+1, t+48],
    else AMBIGUOUS. Labels younger than ``delay`` bars are not final yet
    (returned as AMBIGUOUS) — T is trained only on data up to t−delay."""
    out: List[str] = []
    n = len(rule_labels)
    for t in range(n):
        if t + delay >= n or not bool(confirmed[t]):
            out.append("AMBIGUOUS")
        else:
            out.append(str(rule_labels[t]))
    return out


def estimate_T_dirichlet(sequences: Sequence[Tuple[str, str]],
                         alpha: float = ALPHA_DIRICHLET) -> Dict[str, Any]:
    """Canonical E11 transition estimator: exactly K=9 regimes and a 9×9
    row-stochastic matrix; the registry is explicit (deriving K from
    observed labels could silently shrink the matrix — v4 violation)."""
    canonical_regimes = list(REGIMES)
    if len(canonical_regimes) != K:
        raise AssertionError(
            "E11 canonical regime registry must contain exactly 9 classes")
    idx = {r: i for i, r in enumerate(canonical_regimes)}
    counts = np.zeros((K, K))
    for fr, to in sequences:
        if fr not in idx or to not in idx:
            raise ValueError(
                f"CONFIGURATION_INVALID: unknown E11 regime label: {fr}->{to}")
        counts[idx[fr], idx[to]] += 1
    denom = counts.sum(axis=1, keepdims=True) + K * alpha
    T = (counts + alpha) / denom
    return {"T": T.tolist(), "regimes": canonical_regimes,
            "counts": counts.tolist(), "alpha": float(alpha)}


# ---------------------------------------------------------------------------
# §2/§5.2 — hysteresis (3 consecutive candles) + quality cascade
# ---------------------------------------------------------------------------
def hysteresis_manager(history_states: Sequence[str], new_state: str,
                       confirm_bars: int = HYSTERESIS_BARS,
                       confirmed_prev: Optional[str] = None
                       ) -> Tuple[str, str]:
    """§2: r* changes only if ``confirm_bars`` (3) CONSECUTIVE raw labels
    repeat the new state; otherwise the previous confirmed label is
    retained and the change is flagged SUSPECTED. First candle adopts its
    raw label as CONFIRMED (lifecycle NONE→STABLE, §5.2).

    ISSUE-CP5-019: the §4 pseudocode's trailing else-branch returns
    ``(new_state, CONFIRMED)`` whenever the previous RAW label equals the
    new one — confirming after only 2 consecutive labels and contradicting
    both §2 and its own 3-consecutive first branch. The §2 vocabulary
    governs; ``confirmed_prev`` is tracked explicitly so a SUSPECTED candle
    retains the last CONFIRMED label (not the last raw one)."""
    hist = list(history_states)
    if not hist:
        return new_state, "CONFIRMED"
    if confirmed_prev is not None and new_state == confirmed_prev:
        # no label change is being proposed — stable continuation
        return confirmed_prev, "CONFIRMED"
    seq = hist[-(confirm_bars - 1):] + [new_state]
    if len(seq) >= confirm_bars and all(
            s == new_state for s in seq[-confirm_bars:]):
        return new_state, "CONFIRMED"
    fallback = confirmed_prev if confirmed_prev is not None else hist[-1]
    return str(fallback), "SUSPECTED"


def quality_score(vec: Dict[str, float], H: float, Tur: float,
                  data_ok: bool, contract_ok: bool,
                  params: Optional[EngineParams] = None) -> str:
    """Q cascade (raw-nats entropy — ISSUE-CP5-010): Q0 invalid data, Q1
    contract mismatch, Q2 H≥0.8 ∨ Tur≥20, Q3 H≥0.65 ∨ Tur≥15.5, Q5 H<0.4 ∧
    Tur<8, else Q4."""
    p = params or EngineParams()
    if not data_ok:
        return "Q0"
    if not contract_ok:
        return "Q1"
    if H >= float(p.quality_H_Q2) or Tur >= float(p.quality_Tur_Q2):
        return "Q2"
    if H >= float(p.entropy_threshold) or Tur >= float(p.quality_Tur_Q3):
        return "Q3"
    if H < float(p.quality_H_Q5) and Tur < float(p.quality_Tur_Q5):
        return "Q5"
    return "Q4"


def apply_quality_caps(q: str, caps: Sequence[Optional[str]]) -> str:
    """Order-limited caps (e.g. V=0 ⇒ Q1 per §3.8; BaseRate n_r<30 ⇒ Q3 per
    §8.5): the result is the worst of q and every cap."""
    order = ["Q0", "Q1", "Q2", "Q3", "Q4", "Q5"]
    idx = order.index(q) if q in order else 0
    for cap in caps:
        if cap in order:
            idx = min(idx, order.index(cap))
    return order[idx]


# ---------------------------------------------------------------------------
# §3.9 — BaseRate with Wilson CI
# ---------------------------------------------------------------------------
def wilson_ci(p_hat: Optional[float], n: int, z: float = 1.96
              ) -> Tuple[float, float]:
    """Wilson 95% CI; n=0 or p None ⇒ (0, 0) (never a guess)."""
    if p_hat is None or n <= 0:
        return 0.0, 0.0
    denom = 1.0 + z * z / n
    center = p_hat + z * z / (2 * n)
    rad = z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
    return (center - rad) / denom, (center + rad) / denom


def base_rates_report(outcomes: Sequence[Tuple[str, bool]]
                      ) -> Dict[str, Dict[str, Any]]:
    """BR(Y|r) = #{Y∧r}/#{r} with Wilson CI per regime (§3.9)."""
    out: Dict[str, Dict[str, Any]] = {}
    for regime in REGIMES:
        rows = [ok for r, ok in outcomes if r == regime]
        n = len(rows)
        k_hits = sum(1 for ok in rows if ok)
        p = (k_hits / n) if n else None
        lo, hi = wilson_ci(p, n)
        out[regime] = {"n": n, "k": k_hits, "p": p,
                       "wilson_ci": [lo, hi] if n else None}
    return out


def base_rate_quality_cap(state: str, base_rates: Dict[str, Any],
                          min_n: int = 30) -> Optional[str]:
    """§8.5: if n_r < 30 for the active regime, Q is capped at Q3."""
    row = (base_rates or {}).get(state)
    if isinstance(row, dict) and int(row.get("n", 0)) < min_n:
        return "Q3"
    return None


# ---------------------------------------------------------------------------
# §4 — streaming engine (idempotent, PIT-safe, fail-closed)
# ---------------------------------------------------------------------------
class RegimeEngine:
    """§4 ``process_candle_stream`` as a stateful object. One CLOSED candle
    per ``update``; a duplicate ``as_of`` returns the cached output without
    touching internal state (§5.2 idempotency)."""

    def __init__(self, params: Optional[EngineParams] = None,
                 W: Optional[Sequence[Any]] = None,
                 b: Optional[Sequence[Any]] = None,
                 T: Optional[Dict[str, Any]] = None,
                 history: Optional[Dict[str, List[float]]] = None,
                 mu0: Optional[Sequence[float]] = None,
                 Sigma0: Optional[Sequence[Any]] = None,
                 prev_mom: Optional[float] = 0.5,
                 base_rates: Optional[Dict[str, Any]] = None,
                 symbol: str = "UNKNOWN", timeframe: str = "1h",
                 parameter_package_id: str = "e11_params_v4",
                 code_revision: str = "0" * 40,
                 classifier_artifact_sha256: Optional[str] = None) -> None:
        self.p = params or EngineParams()
        self.W = None if W is None else np.asarray(W, dtype=float)
        self.b = None if b is None else np.asarray(b, dtype=float)
        self.T = T                         # {"T": 9×9, "regimes": [...]} | None
        self.base_rates = dict(base_rates or {})
        self.history_windows: Dict[str, List[float]] = {
            "trend": list((history or {}).get("trend", [])),
            "vol": list((history or {}).get("vol", [])),
            "exp": list((history or {}).get("exp", [])),
            "liq": list((history or {}).get("liq", [])),
            "part": list((history or {}).get("part", [])),
            "sq": list((history or {}).get("sq", [])),
        }
        w = int(self.p.rolling_window_days) * 24      # H1-equivalent cap
        self._win_cap = max(w, W_180D_H1)
        # ISSUE-CP5-014 deterministic PIT-safe seeds
        self.mu = (np.full(D, 0.5) if mu0 is None
                   else np.asarray(mu0, dtype=float))
        self.Sigma = (0.05 * np.eye(D) + COV_REGULARIZATION * np.eye(D)
                      if Sigma0 is None else np.asarray(Sigma0, dtype=float))
        self.prev_mom = prev_mom
        self.last_confirmed: Optional[str] = None
        self.x_part_hist: List[float] = []
        self.hist_raw_states: List[str] = []
        self.xi = np.full(K, 1.0 / K)      # Hamilton filter state
        self.symbol = symbol
        self.timeframe = timeframe
        self.parameter_package_id = parameter_package_id
        self.code_revision = code_revision
        # P2: the validated artifact identity is recorded in snapshot param_hash.
        self._phash = classifier_artifact_sha256 or param_hash(self.p)
        self.last_as_of: Optional[int] = None
        self.last_output: Optional[Dict[str, Any]] = None
        self.last_vec: Optional[Dict[str, float]] = None
        self.bar_index = 0
        self.contract_versions = {"E09": "v4.0.0", "E10": "v4.0.0",
                                  "E04": "v4.0.0"}

    # -- edges ---------------------------------------------------------------
    @staticmethod
    def _contracts_ok(ic_inputs: Dict[str, Any]) -> bool:
        for key in ("e09_version", "e10_version", "e04_version"):
            raw = ic_inputs.get(key)
            if raw is None:
                continue
            digits = "".join(ch for ch in str(raw).split("/")[-1]
                             if ch.isdigit() or ch == ".")
            parts = [seg for seg in digits.split(".") if seg]
            if not parts:
                return False               # unparseable ⇒ mismatch
            try:
                if int(parts[0]) != 4:
                    return False
            except ValueError:
                return False
        return True

    def _fail_closed(self, error: str, as_of: int,
                     event: str = "EV_RGM_007") -> Dict[str, Any]:
        return {"error": error, "Q": "Q0", "event": event,
                "state": "FAIL_CLOSED", "as_of": int(as_of)}

    def _degraded(self, error: str, as_of: int, q: str = "Q0") -> Dict[str, Any]:
        return {"error": error, "Q": q, "event": "EV_RGM_006",
                "state": "AMBIGUOUS", "as_of": int(as_of)}

    # -- main entry -----------------------------------------------------------
    def update(self, candle: Dict[str, Any]) -> Dict[str, Any]:
        """Returns {"regime_state": {...§5.1...}, "events": [...]} for an
        accepted candle, or the pseudocode's fail-closed/degraded dicts."""
        as_of = int(candle.get("as_of", candle.get("ts", 0)) or 0)
        # §5.2 idempotency: duplicate as_of ⇒ cached output, state untouched
        if self.last_as_of is not None and as_of == self.last_as_of \
                and self.last_output is not None:
            return self.last_output
        try:
            # §3.8 H<L edge
            if float(candle.get("h", 0.0)) < float(candle.get("l", 0.0)):
                return self._degraded("H<L", as_of)
            # §3.8 DST/time edge: offset > 2× timeframe ⇒ Data_Degraded
            tf_seconds = candle.get("timeframe_seconds", 3600)
            if self.last_as_of is not None and as_of - self.last_as_of > \
                    2 * int(tf_seconds) * 1000:
                self._pending_time_degraded = True   # Q1 cap + EV_RGM_006
            else:
                self._pending_time_degraded = False
            if self.prev_mom is None:
                return self._fail_closed(
                    "CONFIGURATION_INVALID: missing prev_mom", as_of)
            ic_inputs = dict(candle.get("ic_inputs") or {})
            zero_volume = float(candle.get("v", candle.get("volume", 1.0))
                                or 0.0) == 0.0
            if zero_volume:
                # §3.8/ISSUE-CP5-012: V=0 ⇒ participation_raw=0 path with
                # moving-average fill; missing key entirely still fails Q0
                # inside compute_state_vector unless a fill exists.
                if ic_inputs.get("participation_raw") is None \
                        and self.x_part_hist:
                    ic_inputs["participation_raw"] = 0.0
                    ic_inputs["_x6_fill"] = float(
                        np.mean(self.x_part_hist[-20:]))
                elif ic_inputs.get("participation_raw") is None:
                    ic_inputs["participation_raw"] = 0.0
            vec, bias = compute_state_vector(
                ic_inputs, self.history_windows, float(self.prev_mom))
            if zero_volume and "_x6_fill" in ic_inputs:
                vec["participation"] = max(
                    0.0, min(1.0, float(ic_inputs["_x6_fill"])))
            x_np = vector_to_array(vec)
            if x_np.shape != (D,) or not np.all(np.isfinite(x_np)):
                return self._fail_closed(
                    "CONFIGURATION_INVALID: state vector shape/finiteness",
                    as_of)
            # §3.8 gap edge (ISSUE-CP5-011): |O_t − C_{t−1}|/ATR_{t−1} > 2
            if candle.get("is_gap") or self._gap_detected(candle):
                vec["expansion"] = 1.0
                vec["structure_quality"] = max(
                    0.0, vec["structure_quality"]
                    * float(self.p.gap_structure_factor))
                x_np = vector_to_array(vec)
            mu_prev = self.mu
            Sigma_prev = self.Sigma
            if mu_prev is None or Sigma_prev is None \
                    or np.shape(mu_prev) != (D,) \
                    or np.shape(Sigma_prev) != (D, D):
                return self._fail_closed(
                    "CONFIGURATION_INVALID: E11 global mu/Sigma missing",
                    as_of)
            turb = mahalanobis_turbulence(x_np, mu_prev, Sigma_prev)
            if self.W is None or self.b is None:
                return self._fail_closed(
                    "CONFIGURATION_INVALID: E11 requires W=(9,8) and b=(9,)",
                    as_of)
            if np.shape(self.W) != (K, D) or np.shape(self.b) != (K,):
                return self._fail_closed(
                    "CONFIGURATION_INVALID: E11 requires W=(9,8) and b=(9,)",
                    as_of)
            logits, probs, H = compute_logits_softmax(vec, self.W, self.b)
            if len(probs) != K or not math.isclose(
                    float(np.sum(probs)), 1.0, rel_tol=0.0, abs_tol=1e-12):
                return self._fail_closed(
                    "CONFIGURATION_INVALID: simplex invariant", as_of)
            rule_out = rule_tree_priority(vec, bias, H, turb, probs, self.p)
            confirmed_state, transition_status = hysteresis_manager(
                self.hist_raw_states, rule_out["state"],
                int(self.p.transition_confirm_bars),
                confirmed_prev=self.last_confirmed)
            mu_new, Sigma_new = ewma_update(
                mu_prev, Sigma_prev, x_np, float(self.p.ewma_lambda),
                float(self.p.covariance_regularization))
            # Hamilton filter (diagnostic; η regime-independent §3.5)
            if self.T is not None and "T" in self.T:
                eta = np.full(K, math.exp(gaussian_log_emission(
                    x_np, mu_prev, Sigma_prev)))
                _pred, xi_filt = hamilton_filter_step(
                    self.xi, np.asarray(self.T["T"], dtype=float), eta)
                self.xi = xi_filt
            contract_ok = self._contracts_ok(ic_inputs)
            q = quality_score(vec, H, turb, data_ok=True,
                              contract_ok=contract_ok, params=self.p)
            caps: List[Optional[str]] = []
            if "oi_state" in ic_inputs and ic_inputs["oi_state"] != "AVAILABLE":
                caps.append("Q4")  # D23: Q5 requires every dependency healthy.
            if zero_volume:
                caps.append("Q1")                     # §3.8 V=0
            if self._pending_time_degraded:
                caps.append("Q1")                     # §3.8 DST/offset
            if not contract_ok:
                caps.append("Q1")
            br_cap = base_rate_quality_cap(
                confirmed_state, self.base_rates,
                int(self.p.base_rate_min_n))
            if br_cap is not None:
                caps.append(br_cap)                   # §8.5
            q = apply_quality_caps(q, caps)
            input_hash = str(candle.get("input_hash") or sha256_hex(
                canonical_json(_canonical_ic(ic_inputs)).encode("utf-8")))
            payload = {
                "contract_versions": dict(self.contract_versions),
                "symbol": str(candle.get("symbol", self.symbol)),
                "timeframe": str(candle.get("timeframe", self.timeframe)),
                "as_of": as_of,
                "input_hash": input_hash,
                "parameter_package_id": self.parameter_package_id,
                "param_hash": self._phash,
                "code_revision": self.code_revision,
                "vector": vec,
                "bias": bias,
                "logits": logits,
                "probs": probs,
                "state_raw": rule_out["state"],
                "state": confirmed_state,
                "entropy": H,
                "turbulence": turb,
                "transition_matrix": self.T,
                "base_rates": self.base_rates,
                "Q": q,
            }
            if "oi_state" in ic_inputs:
                payload["dependency_state"] = {
                    "oi_state": ic_inputs["oi_state"],
                    "contributing_features": dict(ic_inputs.get("contributing_features", {}))}
            sid = canonical_snapshot_id(ENGINE, CONTRACT_VERSION, payload)
            regime_state = {
                "vector": vec,
                "bias": bias,
                "probs": probs,
                "logits": logits,
                "entropy": H,
                "turbulence": turb,
                "state": confirmed_state,
                "state_raw": rule_out["state"],
                "reason": rule_out["reason"],
                "regime_transition": transition_status,
                "transition_matrix": self.T,
                "base_rates": self.base_rates,
                "Q": q,
                "as_of": as_of,
                "snapshot_id": sid,
                "engine_version": CONTRACT_VERSION,
                "contract_versions": dict(self.contract_versions),
            }
            events: List[Dict[str, Any]] = [
                {"type": "EV_RGM_001", "state": confirmed_state,
                 "snapshot_id": sid, "as_of": as_of}]
            if transition_status == "SUSPECTED":
                events.append({
                    "type": "EV_RGM_002",
                    "from": self.hist_raw_states[-1]
                    if self.hist_raw_states else "UNKNOWN",
                    "to": rule_out["state"], "entropy": H, "as_of": as_of})
            elif transition_status == "CONFIRMED" \
                    and self.last_confirmed is not None \
                    and self.last_confirmed != confirmed_state:
                # §5.4 semantics (ISSUE-CP5-017): the §4 pseudocode's
                # EV_RGM_003 guard (hist_raw[-1] != confirmed) is provably
                # dead under its own hysteresis_manager; the event table +
                # case study govern — emit on the confirming candle where
                # the CONFIRMED label actually changed.
                events.append({
                    "type": "EV_RGM_003", "from": self.last_confirmed,
                    "to": confirmed_state, "reason": rule_out["reason"],
                    "transition_matrix": self.T, "as_of": as_of})
            if H >= float(self.p.entropy_threshold):
                events.append({"type": "EV_RGM_004", "entropy": H,
                               "probs": probs, "as_of": as_of})
            if turb >= float(self.p.turbulence_threshold):
                events.append({"type": "EV_RGM_005", "turbulence": turb,
                               "mu": [float(v) for v in mu_prev],
                               "sigma_diag": [float(v) for v in
                                              np.diag(Sigma_prev)],
                               "as_of": as_of})
            if zero_volume or self._pending_time_degraded or not contract_ok:
                events.append({"type": "EV_RGM_006", "Q": q,
                               "error_code":
                                   "V_ZERO" if zero_volume else
                                   ("TIME_OFFSET" if
                                    self._pending_time_degraded
                                    else "CONTRACT_MISMATCH"),
                               "as_of": as_of})
            # PIT state advance (only AFTER classification)
            self.mu = mu_new
            self.Sigma = Sigma_new
            self.prev_mom = vec["momentum_state"]
            self.hist_raw_states = (self.hist_raw_states
                                    + [rule_out["state"]])[-20:]
            self.last_confirmed = confirmed_state
            self._append_history(ic_inputs, vec)
            self.last_as_of = as_of
            self.last_vec = vec
            self.bar_index += 1
            out = {"regime_state": regime_state, "events": events}
            self.last_output = out
            return out
        except ValueError as exc:
            # §4 blanket fail-closed path: CONFIGURATION_INVALID /
            # INVALID_E11_* / any numeric-policy violation ⇒ Q0 AMBIGUOUS
            # with EV_RGM_006 (the GF_10 document shape). Only the explicit
            # W/b/μ/Σ/prev_mom guards above emit EV_RGM_007 FAIL_CLOSED.
            return self._degraded(str(exc), as_of)

    _pending_time_degraded = False

    def _gap_detected(self, candle: Dict[str, Any]) -> bool:
        prev_close = candle.get("prev_close")
        atr_prev = candle.get("atr_prev")
        if prev_close is None or atr_prev is None:
            return False
        try:
            gap = abs(float(candle["o"]) - float(prev_close))
            atr = float(atr_prev)
        except (KeyError, TypeError, ValueError):
            return False
        if atr <= EPS:
            return False
        return gap / atr > float(self.p.shock_gap_atr_mult)

    def _append_history(self, ic_inputs: Dict[str, Any],
                        vec: Dict[str, float]) -> None:
        raw_map = (("trend", "trendiness_raw"), ("vol", "vol_ratio"),
                   ("exp", "expansion_raw"), ("liq", "level_density"),
                   ("part", "participation_raw"), ("sq", "structure_score"))
        for win, key in raw_map:
            val = (ic_inputs.get("liquidity_raw", ic_inputs.get(key))
                   if win == "liq" else ic_inputs.get(key))
            if val is not None and math.isfinite(float(val)):
                buf = self.history_windows[win]
                buf.append(float(val))
                if len(buf) > self._win_cap:
                    del buf[:len(buf) - self._win_cap]
        self.x_part_hist.append(vec["participation"])
        if len(self.x_part_hist) > 200:
            del self.x_part_hist[:len(self.x_part_hist) - 200]

    def warmup_ok(self) -> bool:
        """Method A needs ≥10 and Method B ≥20 prior samples per window."""
        return all(len(self.history_windows[w]) >= 20
                   for w in ("trend", "exp", "part", "sq")) and all(
            len(self.history_windows[w]) >= 10 for w in ("vol", "liq"))


def _canonical_ic(ic_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """JSON-safe copy of ic_inputs for hashing (no private fill keys)."""
    return {k: v for k, v in sorted(ic_inputs.items())
            if not str(k).startswith("_")}


# ---------------------------------------------------------------------------
# §5.1 — schema validation (additionalProperties:false semantics)
# ---------------------------------------------------------------------------
REGIME_STATE_REQUIRED: Tuple[str, ...] = (
    "vector", "state", "entropy", "turbulence", "Q", "as_of", "snapshot_id",
    "engine_version")
REGIME_STATE_ALLOWED: Tuple[str, ...] = REGIME_STATE_REQUIRED + (
    "bias", "probs", "logits", "state_raw", "reason", "regime_transition",
    "transition_matrix", "base_rates", "contract_versions")


def validate_state_schema(state: Dict[str, Any]) -> None:
    """§5.1 RegimeState conformance. Raises ValueError on any violation —
    including extra keys (additionalProperties:false)."""
    import re
    for key in REGIME_STATE_REQUIRED:
        if key not in state:
            raise ValueError(f"E11_STATE_SCHEMA_QX: missing {key}")
    extra = set(state) - set(REGIME_STATE_ALLOWED)
    if extra:
        raise ValueError(
            f"E11_STATE_SCHEMA_QX: additionalProperties false — {sorted(extra)}")
    vec = state["vector"]
    if set(vec) != set(VECTOR_KEYS):
        raise ValueError("E11_STATE_SCHEMA_QX: vector must carry exactly the "
                         "8 canonical components")
    for key in VECTOR_KEYS:
        val = float(vec[key])
        if not math.isfinite(val) or not 0.0 <= val <= 1.0:
            raise ValueError(f"E11_STATE_SCHEMA_QX: vector.{key} range [0,1]")
    if "bias" in state and not -1.0 <= float(state["bias"]) <= 1.0:
        raise ValueError("E11_STATE_SCHEMA_QX: bias range [-1,1]")
    if "probs" in state:
        probs = state["probs"]
        if len(probs) != K:
            raise ValueError("E11_STATE_SCHEMA_QX: probs must have exactly "
                             "9 items (T-E11-K9)")
        if any(float(p) < 0.0 or float(p) > 1.0 for p in probs):
            raise ValueError("E11_STATE_SCHEMA_QX: probs range [0,1]")
        if not math.isclose(float(sum(probs)), 1.0, rel_tol=0.0,
                            abs_tol=1e-9):
            raise ValueError("E11_STATE_SCHEMA_QX: probs simplex sum")
    if "logits" in state and len(state["logits"]) != K:
        raise ValueError("E11_STATE_SCHEMA_QX: logits must have exactly 9 "
                         "items")
    if state["state"] not in STATE_ENUM:
        raise ValueError("E11_STATE_SCHEMA_QX: state enum")
    if "reason" in state and len(str(state["reason"])) < 3:
        raise ValueError("E11_STATE_SCHEMA_QX: reason minLength 3")
    if "regime_transition" in state \
            and state["regime_transition"] not in TRANSITION_STATUSES:
        raise ValueError("E11_STATE_SCHEMA_QX: regime_transition enum")
    if float(state["entropy"]) < 0 or float(state["turbulence"]) < 0:
        raise ValueError("E11_STATE_SCHEMA_QX: entropy/turbulence minimum 0")
    if state["Q"] not in Q_TAGS:
        raise ValueError("E11_STATE_SCHEMA_QX: Q enum")
    if not isinstance(state["as_of"], int):
        raise ValueError("E11_STATE_SCHEMA_QX: as_of integer unix ms")
    if not re.match(r"^[0-9a-f]{64}$", str(state["snapshot_id"])):
        raise ValueError("E11_STATE_SCHEMA_QX: snapshot_id pattern")
    tm = state.get("transition_matrix")
    if tm is not None:
        if not isinstance(tm, dict) or "T" not in tm or "regimes" not in tm:
            raise ValueError("E11_STATE_SCHEMA_QX: transition_matrix shape")
        if len(tm["T"]) != K or any(len(row) != K for row in tm["T"]):
            raise ValueError("E11_STATE_SCHEMA_QX: transition_matrix must be "
                             "9×9 (T-E11-K9)")


# ---------------------------------------------------------------------------
# §8 — battery helpers
# ---------------------------------------------------------------------------
def deterministic_replay_check(candles: Sequence[Dict[str, Any]],
                               make_engine: Any) -> bool:
    """§8.2: two from-scratch runs must produce identical snapshot_ids."""
    def run() -> List[Any]:
        eng = make_engine()
        return [eng.update(c).get("regime_state", {}).get("snapshot_id")
                for c in candles]
    return run() == run()


def no_future_leak_check(make_engine: Any,
                         candles: Sequence[Dict[str, Any]],
                         t_index: int,
                         alt_ic_inputs: Sequence[Dict[str, Any]]) -> bool:
    """§8.3 future-shuffle test: replacing every ic_inputs payload AFTER
    ``t_index`` with different (shuffled) values must leave the regime_state
    vector AT ``t_index`` bit-identical — X_t depends only on history ≤ t−1
    and the candle t itself."""
    def run(cnds: Sequence[Dict[str, Any]]) -> Optional[Dict[str, float]]:
        eng = make_engine()
        vec: Optional[Dict[str, float]] = None
        for i, c in enumerate(cnds):
            out = eng.update(c)
            if i == t_index:
                st = out.get("regime_state")
                vec = dict(st["vector"]) if st else None
        return vec

    base = run(candles)
    shuffled: List[Dict[str, Any]] = []
    for i, c in enumerate(candles):
        if i > t_index and alt_ic_inputs:
            c2 = dict(c)
            c2["ic_inputs"] = dict(alt_ic_inputs[(i - t_index - 1)
                                                 % len(alt_ic_inputs)])
            shuffled.append(c2)
        else:
            shuffled.append(dict(c))
    after = run(shuffled)
    if base is None or after is None:
        return base is None and after is None
    return all(base[k] == after[k] for k in VECTOR_KEYS)


def serialize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """§8.7 wire serialization: floats to 6 decimal places; snapshot_id is
    content-bound and unaffected by the wire rounding."""
    def rnd(v: Any) -> Any:
        if isinstance(v, float):
            return round(v, 6)
        if isinstance(v, dict):
            return {k: rnd(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [rnd(x) for x in v]
        return v
    return rnd(dict(state))


def load_v3_adapter(payload: Dict[str, Any]) -> Dict[str, Any]:
    """§8.7: loading a v3.0.0 file in the v4.0.0 engine goes through
    migration and temporarily emits Q1. Unknown/ambiguous shapes fail
    closed."""
    version = str(payload.get("version") or payload.get("schema_version")
                  or "")
    if not version.startswith("3."):
        raise ValueError("E11_V3_ADAPTER_QX: not a v3 payload")
    st = payload.get("regime_state") or payload.get("state")
    if not isinstance(st, dict) or "state" not in st:
        raise ValueError("E11_V3_ADAPTER_QX: ambiguous v3 shape")
    return {"contract_version": CONTRACT_LABEL,
            "schema_version": SCHEMA_VERSION, "engine_code": ENGINE,
            "as_of": int(st.get("as_of", payload.get("as_of", 0))),
            "state": str(st["state"]), "Q": "Q1",
            "migrated_from": version}


def redundancy_report(series_a: Sequence[float],
                      series_b: Sequence[float]) -> Dict[str, Any]:
    """§8.6: |corr(x_i, x_j)| > 0.85 for 30 consecutive days ⇒ redundancy
    alert; one component must be dropped or reweighted."""
    a = np.asarray(list(series_a), dtype=float)
    b = np.asarray(list(series_b), dtype=float)
    if a.shape != b.shape or a.size < 2 or float(np.std(a)) <= EPS \
            or float(np.std(b)) <= EPS:
        return {"corr": None, "redundancy_alert": False}
    corr = float(np.corrcoef(a, b)[0, 1])
    return {"corr": corr, "redundancy_alert": abs(corr) > 0.85}


def calibration_report(base_rates: Dict[str, Dict[str, Any]],
                       bins: Sequence[Tuple[float, bool]] = ()
                       ) -> Dict[str, Any]:
    """§8.5: per-regime n/k/p + Wilson CI; n_r < 30 caps Q at Q3. ECE over
    (max p, realized accuracy) bins when supplied."""
    out: Dict[str, Any] = {"base_rates": dict(base_rates),
                           "q3_caps": [], "ece": None}
    for regime, row in (base_rates or {}).items():
        if isinstance(row, dict) and int(row.get("n", 0)) < 30:
            out["q3_caps"].append(regime)
    if bins:
        nb = len(bins)
        ece = 0.0
        for conf, ok in bins:
            ece += abs(float(conf) - (1.0 if ok else 0.0)) / nb
        out["ece"] = ece
    return out


# ---------------------------------------------------------------------------
# §4 batch driver + Wave-Out + EngineBase binding
# ---------------------------------------------------------------------------
LIVE_GATE_OFF_REASON = (
    "LIVE_REGIME_GATE_DISABLED: enabling live regime gating requires "
    "Phase-7 deployment and explicit Owner approval (AI.2 L19046–19048); "
    "default OFF is the only lawful build-time state.")


def forecast_next_regime(*_args: Any, **_kwargs: Any) -> Any:
    """§9.5-9 Wave-Out: E11 next-regime forecast is NOT implemented."""
    raise wave_out("e11_next_regime_forecast",
                   "NEXT_REGIME_FORECAST_WAVE_OUT: E11 next-regime forecast "
                   "is Wave-Out (§9.5-9) — raise, never build.")


def run_engine(candles: Sequence[Dict[str, Any]],
               params: Optional[Dict[str, Any]] = None,
               W: Optional[Sequence[Any]] = None,
               b: Optional[Sequence[Any]] = None,
               T: Optional[Dict[str, Any]] = None,
               history: Optional[Dict[str, List[float]]] = None,
               mu0: Optional[Sequence[float]] = None,
               Sigma0: Optional[Sequence[Any]] = None,
               prev_mom: Optional[float] = 0.5,
               base_rates: Optional[Dict[str, Any]] = None,
               symbol: str = "UNKNOWN", timeframe: str = "1h",
               as_of_ms: Optional[int] = None,
               live_regime_gate: bool = False,
               classifier_artifact_sha256: Optional[str] = None) -> Dict[str, Any]:
    """Batch driver → the last RegimeState + every event fired. The
    live-regime gate flag lives in THIS wrapper (never inside regime_state —
    §5.1 additionalProperties:false) and is OFF unless the caller asserts
    Phase-7 + Owner approval; the engine never self-enables."""
    p = params if isinstance(params, EngineParams) else get_params(params)
    if int(p.as_dict()["K"]) != K:
        raise ValueError("CONFIGURATION_INVALID: E11 K must be exactly 9 "
                         "(T-E11-K9)")
    eng = RegimeEngine(p, W=W, b=b, T=T, history=history, mu0=mu0,
                       Sigma0=Sigma0, prev_mom=prev_mom,
                       base_rates=base_rates, symbol=symbol,
                       timeframe=timeframe,
                       classifier_artifact_sha256=classifier_artifact_sha256)
    state: Dict[str, Any] = {"quality": "QX",
                             "reason": "INSUFFICIENT_HISTORY_Q1",
                             "as_of": int(as_of_ms or 0)}
    events: List[Dict[str, Any]] = []
    for candle in candles:
        if not eng.warmup_ok():
            # accumulate history from raw inputs while below the norm floors
            ic = dict(candle.get("ic_inputs") or {})
            for win, key in (("trend", "trendiness_raw"),
                             ("vol", "vol_ratio"), ("exp", "expansion_raw"),
                             ("liq", "level_density"),
                             ("part", "participation_raw"),
                             ("sq", "structure_score")):
                val = (ic.get("liquidity_raw", ic.get(key))
                       if win == "liq" else ic.get(key))
                if val is not None and math.isfinite(float(val)):
                    eng.history_windows[win].append(float(val))
            state = {"quality": "QX", "reason": "INSUFFICIENT_HISTORY_Q1",
                     "as_of": int(candle.get("as_of",
                                             candle.get("ts", 0)) or 0)}
            continue
        out = eng.update(candle)
        if "regime_state" in out:
            state = out["regime_state"]
            events.extend(out["events"])
        else:
            state = out
            events.append({"type": out.get("event", "EV_RGM_006"),
                           "error": out.get("error"),
                           "as_of": int(out.get("as_of", 0))})
    if as_of_ms is not None and "as_of" in state:
        state = dict(state)
        state["as_of"] = int(as_of_ms)
    gate_enabled = bool(live_regime_gate)
    return {
        "regime_state": state,
        "dependency_state": ({
            "oi_state": candles[-1]["ic_inputs"]["oi_state"],
            "contributing_features": dict(candles[-1]["ic_inputs"].get("contributing_features", {}))}
            if candles and "oi_state" in candles[-1].get("ic_inputs", {}) else {}),
        "events": events,
        "engine": ENGINE,
        "contract_version": CONTRACT_VERSION,
        "n_bars": int(eng.bar_index),
        "H_norm": (entropy_normalized(float(state["entropy"]))
                   if "entropy" in state else None),
        "xi_filtered": [float(v) for v in eng.xi],
        "live_regime_gate": {
            "enabled": gate_enabled,
            "reason": LIVE_GATE_OFF_REASON if not gate_enabled
            else "LIVE_REGIME_GATE_ENABLED_BY_CALLER: Phase-7 + Owner "
                 "approval asserted at the call site",
        },
    }


def catalog_events(
    state: Dict[str, Any], params: Optional[EngineParams] = None
) -> List[Dict[str, Any]]:
    """§5.4 catalog rows fired by a regime_state (empty for refusals).

    D49: uses float(p.entropy_threshold) from governed params, never
    E11.THETA_H constant. THETA_H stays exported unused per C5.
    """
    events: List[Dict[str, Any]] = []
    if "state" not in state or "entropy" not in state:
        return events
    p = params or get_params()
    as_of = int(state.get("as_of", 0))
    events.append({"code": "EV_RGM_001", "as_of": as_of, "state": state})
    if state.get("regime_transition") == "SUSPECTED":
        events.append({"code": "EV_RGM_002", "as_of": as_of, "state": state})
    elif state.get("regime_transition") == "CONFIRMED":
        events.append({"code": "EV_RGM_003", "as_of": as_of, "state": state})
    if float(state["entropy"]) >= float(p.entropy_threshold):
        events.append({"code": "EV_RGM_004", "as_of": as_of, "state": state})
    if float(state["turbulence"]) >= TH_TURB_95:
        events.append({"code": "EV_RGM_005", "as_of": as_of, "state": state})
    if state.get("Q") in ("Q0", "Q1"):
        events.append({"code": "EV_RGM_006", "as_of": as_of, "state": state})
    return events


def e11_snapshot_id(payload: Dict[str, Any]) -> str:
    """§5.3 canonical snapshot identity (global contract delegation)."""
    return canonical_snapshot_id(ENGINE, CONTRACT_VERSION, payload)


def observation_to_candle(obs: MarketObservation,
                          ic_inputs: Optional[Dict[str, Any]] = None
                          ) -> Dict[str, Any]:
    """MarketObservation → the §4 candle shape (ic_inputs carried through)."""
    ts_ms = 0
    try:
        dt = datetime.datetime.fromisoformat(
            str(obs.timestamp).replace("Z", "+00:00"))
        ts_ms = int(dt.timestamp() * 1000)
    except (ValueError, AttributeError):
        ts_ms = 0
    return {"o": float(obs.open), "h": float(obs.high), "l": float(obs.low),
            "c": float(obs.close), "v": float(obs.volume), "ts": ts_ms,
            "as_of": ts_ms, "symbol": obs.symbol,
            "timeframe": obs.timeframe,
            "is_closed": (obs.status == "CLOSED") if obs.status else True,
            "ic_inputs": dict(ic_inputs or {})}


class E11RegimeEngine(EngineBase):
    """E11_Regime on the frozen EngineBase contract (v4.0.0).

    ``compute(symbol, timeframe, as_of, context)``; consumed context keys:
      ``candles``   — §4 candle dicts with ``ic_inputs`` (authoritative)
      ``window`` / ``provider`` — MarketObservation fallback (ic_inputs per
                      candle via ``ic_inputs_list`` when supplied)
      ``W``, ``b``  — trained classifier tensors (None ⇒ fail-closed
                      EV_RGM_007 at update time — no uniform fallback)
      ``T``, ``history``, ``mu0``, ``Sigma0``, ``prev_mom``, ``base_rates``
      ``e11_params`` — §6 overrides (unknown keys rejected)
      ``live_regime_gate`` — default False (Phase-7 + Owner approval)
      ``forecast`` / ``next_regime`` / ``adaptive_atr`` — Wave-Out ⇒ raise
    Emits one EvidenceEvent per §5.4 catalog event on the final state, on
    ``evidence.E11.{condition_state}``. Context only: ``direction = 0``
    (NG1 — regime is a veto/context input, never a standalone mandate).
    """

    engine_id = "E11"
    analyst_version = ANALYST_VERSION
    code_revision = "0" * 40

    _CONF_BY_Q = {"Q5": 1.0, "Q4": 0.9, "Q3": 0.7, "Q2": 0.5, "Q1": 0.3,
                  "Q0": 0.0, "QX": 0.0}

    def compute(self, symbol: str, timeframe: str, as_of: str,
                context: Optional[Dict[str, Any]] = None
                ) -> List[EvidenceEvent]:
        context = context or {}
        if context.get("forecast") or context.get("next_regime"):
            forecast_next_regime()           # raises WaveOutError
        if context.get("adaptive_atr") or context.get("adaptive_period"):
            raise wave_out("adaptive_atr_e04_e11",
                           "ADAPTIVE_ATR_WAVE_OUT: adaptive ATR E04↔E11 is "
                           "Wave-Out (§9.5-9) — raise, never build.")
        candles = self._resolve_candles(symbol, timeframe, as_of, context)
        if not candles:
            return []
        result = run_engine(
            candles, params=context.get("e11_params"),
            W=context.get("W"), b=context.get("b"), T=context.get("T"),
            history=context.get("history"), mu0=context.get("mu0"),
            Sigma0=context.get("Sigma0"), prev_mom=context.get(
                "prev_mom", 0.5),
            base_rates=context.get("base_rates"), symbol=symbol,
            timeframe=timeframe,
            live_regime_gate=bool(context.get("live_regime_gate", False)),
            classifier_artifact_sha256=context.get("classifier_artifact_sha256"))
        self._last_result = result
        state = result["regime_state"]
        if "snapshot_id" not in state:
            return []                        # QX/Q0 refusal — nothing built
        quality = self._window_quality(candles)
        # CP-14.5 C3: resolve the governed EngineParams ONCE, here, with the
        # same rule run_engine applies (an EngineParams passes through, any
        # other value is an override dict for get_params), and hand them to
        # catalog_events. Values are unchanged — no numeric path is touched.
        e11_params = context.get("e11_params")
        params = (e11_params if isinstance(e11_params, EngineParams)
                  else get_params(e11_params))
        return [self._to_evidence(item, symbol, timeframe, quality, state,
                                  result)
                for item in catalog_events(state, params)]

    def _resolve_candles(self, symbol: str, timeframe: str, as_of: str,
                         context: Dict[str, Any]) -> List[Dict[str, Any]]:
        candles = context.get("candles")
        if candles is not None:
            return list(candles)
        window = context.get("window")
        if window is None:
            provider = context.get("provider")
            if provider is None:
                raise ValueError("MISSING_WINDOW_CONTEXT_QX")
            import asyncio
            import inspect
            bars = context.get("bars", 300)
            res = provider.get_window(symbol, timeframe, as_of, bars)
            if inspect.isawaitable(res):
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    window = list(asyncio.run(res))
                else:
                    raise ValueError("MISSING_WINDOW_CONTEXT_QX (async "
                                     "provider inside a running loop — pass "
                                     "context['candles'] or "
                                     "context['window'])")
            else:
                window = list(res)
        ic_list = context.get("ic_inputs_list") or []
        return [observation_to_candle(obs, ic_list[i] if i < len(ic_list)
                                      else None)
                for i, obs in enumerate(window)]

    @staticmethod
    def _window_quality(candles: Sequence[Dict[str, Any]]) -> float:
        if not candles:
            return 0.0
        ok = sum(1 for c in candles
                 if float(c.get("h", 0)) >= float(c.get("l", 0)))
        return ok / len(candles)

    def _to_evidence(self, item: Dict[str, Any], symbol: str,
                     timeframe: str, quality: float, state: Dict[str, Any],
                     result: Dict[str, Any]) -> EvidenceEvent:
        code = str(item["code"])
        name = EVENT_CATALOG[code]["name"]
        ts = int(state["as_of"])
        iso = datetime.datetime.fromtimestamp(
            ts / 1000.0, tz=datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.") + f"{ts % 1000:03d}Z"
        q = str(state["Q"])
        regime = str(state["state"])
        probs = [float(p) for p in state["probs"]]
        p_max = max(probs) if probs else 0.0
        h_norm = entropy_normalized(float(state["entropy"]))
        if code == "EV_RGM_001":
            condition = f"EV_RGM_001_{regime}"
            strength = max(0.0, min(1.0, 1.0 - h_norm))
        elif code == "EV_RGM_005":
            condition = "EV_RGM_005_TURBULENCE_ALERT"
            strength = max(0.0, min(1.0, float(state["turbulence"])
                                    / TH_TURB_999))
        elif code == "EV_RGM_004":
            condition = "EV_RGM_004_REGIME_AMBIGUOUS"
            strength = max(0.0, min(1.0, h_norm))
        else:
            condition = f"{code}_{name.upper()}"
            strength = max(0.0, min(1.0, p_max))
        explanation = (
            f"E11 {code} {name} regime={regime} raw={state['state_raw']} "
            f"H={float(state['entropy']):.4f} (norm {h_norm:.4f}) "
            f"Tur={float(state['turbulence']):.4f} p_max={p_max:.4f} "
            f"Q={q} transition={state.get('regime_transition')} "
            f"gate={'ON' if result['live_regime_gate']['enabled'] else 'OFF'}"
        )
        return EvidenceEvent(
            evidence_id=uuid_v7(),
            engine_id=self.engine_id,
            analyst_version=self.analyst_version,
            symbol=symbol, timeframe=timeframe,
            snapshot_id=str(state["snapshot_id"]),
            event_time=iso, availability_time=iso,
            observation_window={"timeframe": timeframe, "K": K,
                                "as_of_ms": ts, **result.get("dependency_state", {})},
            feature_snapshot_id=str(state["snapshot_id"]),
            feature_dependencies=("E09_Trend.v4(bias)",
                                  "E10_Momentum.v4(momentum_state)",
                                  "E04_Volatility.v4(atr_z)",
                                  "E03_Volume.v4(participation)",
                                  "E02_Liquidity.v4(level_density)"),
            condition_state=condition,
            direction=0,                     # context/veto engine (NG1)
            strength=float(strength),
            confidence=float(self._CONF_BY_Q.get(q, 0.3)),
            quality=float(quality),
            validity="VALID" if q in ("Q3", "Q4", "Q5") else "DEGRADED",
            fate_state=LifecycleState.ACTIVE if q in ("Q3", "Q4", "Q5")
            else LifecycleState.CANDIDATE,
            age=float(max(result.get("n_bars", 1), 1)),
            decay=math.exp(-1.0 / DELAY_BARS),
            explanation=explanation[:500],
            parameter_version="E11-RGM-V4.0.0/e11_params_v4",
            lineage=(f"lambda_{self._lambda_tag()}", f"q_{q}"),
            resolution_class=q,
        )

    @staticmethod
    def _lambda_tag() -> str:
        return str(E11_DEFAULTS["ewma_lambda"])

    _last_result: Optional[Dict[str, Any]] = None


__all__ = [
    "ALPHA_DIRICHLET", "ANALYST_VERSION", "BIAS_WEIGHTS",
    "CONTRACT_LABEL", "CONTRACT_VERSION", "COV_REGULARIZATION", "D",
    "DELAY_BARS", "E11RegimeEngine", "E11_DEFAULTS", "ENGINE", "EPS",
    "EVENT_CATALOG", "EngineParams", "HYSTERESIS_BARS", "K", "LAMBDA_EWMA",
    "LIVE_GATE_OFF_REASON", "MOMENTUM_CATEGORY_MAP", "Q_TAGS", "REGIMES",
    "REGIME_STATE_ALLOWED", "REGIME_STATE_REQUIRED", "REQUIRED_IC_INPUTS",
    "RegimeEngine",
    "STATE_ENUM", "THETA_H", "TH_TURB_95", "TH_TURB_99", "TH_TURB_999",
    "TRANSITION_STATUSES", "VECTOR_KEYS", "W_180D_H1",
    "apply_delayed_labels", "apply_quality_caps", "base_rate_quality_cap",
    "base_rates_report", "calibration_report", "catalog_events",
    "cholesky_or_fail", "compute_bias", "compute_logits_softmax",
    "compute_state_vector", "deterministic_replay_check", "e11_snapshot_id",
    "entropy_normalized", "estimate_T_dirichlet", "ewma_update",
    "forecast_next_regime", "gaussian_log_emission", "get_params",
    "hamilton_filter_step", "hysteresis_manager", "load_v3_adapter",
    "mahalanobis_turbulence", "map_momentum_state",
    "no_future_leak_check", "observation_to_candle", "param_hash",
    "quality_score", "redundancy_report", "rolling_minmax_norm",
    "rolling_sigmoid_norm", "rule_tree_priority", "run_engine",
    "serialize_state", "validate_state_schema", "vector_to_array",
    "wilson_ci",
]
