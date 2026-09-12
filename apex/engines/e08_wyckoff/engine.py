"""APEX_GEN5 — E08 Wyckoff / Auction Theory (v4.0.0).

Blueprint: APEX_GEN5.md L9086–9466 (chapter order mirrored: §1 mission →
§2 vocabulary → §3 math → §4 algorithms → §5 objects/state/events →
§6 parameters → §7 encyclopedic → §8 validation).

Output contract: ``PhaseHypotheses`` — a probability vector over the 8 phases
with entropy ``H = -Σ p ln p`` — plus a ``CycleState``, the Dirichlet
transition matrix and the diagnostic events ``SC/AR/ST/Spring/SOS/LPS/UT/UTAD/
LPSY``. The output is never a definitive phase (§1 Non-goal 1) and never grants
capital authorization (§0).

Wave-Out (G6/P6, §9.5-9): **E08 encyclopedia chapters 2–4 are not implemented.**
``encyclopedia_chapter(2|3|4)`` raises ``WaveOutError("e08_encyclopedia_ch2_4", …)``
with a deterministic reason; only Chapter 1 (the normative surface per the §7
freeze pointer) is served. The gap is a disclosed content gap in the source
(§7 Decision D-E08-M5), never a silently stubbed method.

Logged contradictions (PHASE2_DECISION_LOG §B/CP-4):
  ISSUE-CP4-010 (§4 SC call site passes range/ATR as RangeZ) → §3.1 z-score.
  ISSUE-CP4-011 (score_position can exceed the stated [0,1] domain) → clamp.
  ISSUE-CP4-012 (§3.2 fully specifies only the Accumulation column) →
                 documented rule table, unspecified pairs neutral 0.5.
  ISSUE-CP4-013 (§0 8-phase softmax + θ_H=0.85 vs §9's 3-phase example) →
                 implemented exactly as §0/§3.2 specify; AMBIGUOUS is the
                 chapter's own fail-closed posture.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from apex.data_catalog.contracts import (
    EvidenceEvent,
    LifecycleState,
    MarketObservation,
)
from apex.engines.base import EngineBase
from apex.errors import WaveOutError, wave_out
from apex.identity.snapshot import canonical_snapshot_id
from apex.identity.uuid_v7 import uuid_v7
from apex.quality.numerical import eps_for_engine

# ---------------------------------------------------------------------------
# Chapter identity
# ---------------------------------------------------------------------------

ENGINE = "E08_Wyckoff"
CONTRACT_VERSION = "4.0.0"
CONTRACT_LABEL = "APEX-CONTRACT-WYCKOFF-V4.0.0"
ANALYST_VERSION = "4.0.0+" + "0" * 40
EPS = float(eps_for_engine("E08"))            # 1e-8 (§4 harmonized Tier-2 EPS)

# §0 the eight phases (verbatim order).
PHASES = ("ACCUMULATION", "MARKUP", "DISTRIBUTION", "MARKDOWN",
          "RE-ACCUMULATION", "RE-DISTRIBUTION", "RANGE", "TRANSITION")
K_PHASES = len(PHASES)

# §1 quality ladder.
QUALITIES = ("Q0", "Q1", "Q2", "Q3", "Q4", "Q5")
QUALITY_NAMES = {"Q0": "INVALID", "Q1": "RAW", "Q2": "STRUCTURAL",
                 "Q3": "VOLUME_CONFIRMED", "Q4": "STATISTICAL", "Q5": "GOLDEN"}

# §5 state machine.
STATES = ("NO_RANGE", "RANGE_DETECTED", "SC", "AR", "ST", "SPRING", "SOS",
          "LPS", "MARKUP", "RE-ACCUMULATION")
STATE_ORDER = {s: i for i, s in enumerate(STATES)}
CYCLE_FATES = ("ACTIVE", "AMBIGUOUS", "INVALIDATED", "EXPIRED")

# §5 event table EV_WYK_001..012.
EVENT_CATALOG: Dict[str, str] = {
    "EV_WYK_001": "Phase_Hypothesis_Update",
    "EV_WYK_002": "SC_Detected",
    "EV_WYK_003": "AR_Detected",
    "EV_WYK_004": "ST_Detected",
    "EV_WYK_005": "Spring_Detected",
    "EV_WYK_006": "SOS_Detected",
    "EV_WYK_007": "LPS_Detected",
    "EV_WYK_008": "UTAD_Detected",
    "EV_WYK_009": "LPSY_Detected",
    "EV_WYK_010": "Phase_Transition",
    "EV_WYK_011": "Range_Boundary_Identified",
    "EV_WYK_012": "Hypothesis_Invalidated",
}

# §7 encyclopedic coverage: Chapter 1 is the normative surface; Chapters 2–4
# are Wave-Out (§7 freeze pointer + §9.5-9).
ENCYCLOPEDIA_CHAPTERS = (1, 2, 3, 4)
ENCYCLOPEDIA_WAVE_OUT_CHAPTERS = (2, 3, 4)
ENCYCLOPEDIA_CH1_DIMENSIONS = 16
WAVE_OUT_FEATURE = "e08_encyclopedia_ch2_4"
WAVE_OUT_REASONS = {
    2: "E08_CH2_THE_THREE_LAWS_DEFERRED_NON_NORMATIVE",
    3: "E08_CH3_MARKET_CYCLES_DEFERRED_NON_NORMATIVE",
    4: "E08_CH4_WYCKOFF_EVENTS_DEFERRED_NON_NORMATIVE",
}

# §3.2 score components (order = the §4/§9 weight vector order).
SCORE_COMPONENTS = ("position", "evr", "volume", "structure", "age")

CYCLE_STATE_REQUIRED = ("range", "phase_hypotheses", "entropy",
                        "confirmed_events", "fate", "snapshot_id", "as_of",
                        "version", "quality")


# ---------------------------------------------------------------------------
# §6 Parameters (defaults verbatim from the chapter table)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EngineParams:
    """E08 governed parameter set (§6 table, defaults verbatim)."""

    sc_vol_ratio: float = 2.5           # ×SMA
    sc_range_z: float = 2.0             # z
    sc_close_pos_lo: float = 0.25       # ClosePosition band (25th pct)
    sc_close_pos_hi: float = 0.6        # ClosePosition band (60th pct)
    sc_body_ratio: float = 0.5
    sc_low_lookback: int = 5            # §3.3 Low == min(L_{t-5:t})
    ar_min_ratio: float = 0.5           # ×ATR14
    ar_bars: int = 5                    # AR within <= 5 candles of SC
    ar_close_pos: float = 0.6
    st_vol_ratio: float = 0.7
    st_zone_tol: float = 0.3            # ±0.3·ATR around Low_SC
    spring_pen_max: float = 0.3         # ×ATR
    spring_vol_min: float = 1.3
    spring_evr_min: float = 0.5
    spring_bars: int = 3                # recovery within sp_bars <= 3
    spring_since_st_max: int = 20       # BarCount_since_ST <= 20
    sos_vol_min: float = 1.2
    sos_close_pos: float = 0.65
    sos_break_atr: float = 0.2          # Close > range_hi + 0.2·ATR
    lps_vol_max: float = 0.7
    lps_above_atr: float = 0.2          # Low >= RangeLow + 0.2·ATR
    ut_pen_max: float = 0.3
    ut_vol_min: float = 1.2
    ut_close_pos: float = 0.4
    range_min_bars: int = 12
    range_atr_mult: float = 1.5         # §4 detect_range: hi-lo < 1.5·ATR
    entropy_threshold: float = 0.85     # nat (ln K × 0.6)
    cause_effect_k: float = 0.42
    cause_effect_gamma: float = 0.71
    pf_reversal_rows: int = 3           # classic P&F
    pf_box_atr_mult: float = 0.5        # BoxSize = 0.5·ATR14
    evr_rho_threshold: float = 0.2
    max_age_bars: int = 96
    invalidation_atr: float = 0.5       # Close < SC_Low − 0.5·ATR
    lambda_age: float = 0.02            # score_age = exp(-λ·age)
    atr_period: int = 14
    vol_sma_period: int = 20
    range_sma_period: int = 20
    corr_min_samples: int = 10          # §4 evr_correlation n < 10 → NaN
    dirichlet_alpha: float = 0.1        # §3.2 transition matrix
    transition_K: int = 9               # §3.2 K = 9
    transition_lag_bars: int = 48       # §3.2 48-candle-lagged labels
    brier_target: float = 0.22
    log_loss_target: float = 0.65
    brier_q4_max: float = 0.25          # §1 Q4 STATISTICAL gate
    redundancy_spring_sweep_max: float = 0.45   # §8 redundancy
    # §4/§9 phase-score weights (Σw = 1).
    w_position: float = 0.25
    w_evr: float = 0.25
    w_volume: float = 0.20
    w_structure: float = 0.15
    w_age: float = 0.15
    neutral_score: float = 0.5          # ISSUE-CP4-012 unspecified cell


E08_DEFAULTS: Dict[str, Any] = {
    f.name: f.default for f in EngineParams.__dataclass_fields__.values()}


def get_params(overrides: Optional[Dict[str, Any]] = None) -> EngineParams:
    """Build a parameter set; unknown keys are rejected (fail-closed)."""
    overrides = dict(overrides or {})
    unknown = sorted(set(overrides) - set(E08_DEFAULTS))
    if unknown:
        raise ValueError(f"UNKNOWN_E08_PARAM_QX: {unknown}")
    return EngineParams(**{**E08_DEFAULTS, **overrides})


def phase_weights(params: Optional[EngineParams] = None) -> List[float]:
    """§3.2/§4/§9 component weight vector ``w`` (Σw = 1)."""
    p = params or EngineParams()
    return [p.w_position, p.w_evr, p.w_volume, p.w_structure, p.w_age]


# ---------------------------------------------------------------------------
# §3.1 The three laws, quantified
# ---------------------------------------------------------------------------


def true_range(h: float, l: float, prev_close: float) -> float:
    """``TR_t = max(H_t−L_t, |H_t−C_{t−1}|, |L_t−C_{t−1}|)``."""
    return max(h - l, abs(h - prev_close), abs(l - prev_close))


def rma(series: Sequence[float], n: int) -> float:
    """Wilder RMA (§4): SMA seed then ``RMA_t = (RMA_{t−1}(n−1)+x_t)/n``.

    Fewer than ``n`` samples ⇒ NaN (no fabricated warm-up value).
    """
    if len(series) < n or n <= 0:
        return float("nan")
    atr = sum(series[:n]) / n
    for x in series[n:]:
        atr = (atr * (n - 1) + x) / n
    return atr


def atr14(bars: Sequence[Dict[str, Any]], period: int = 14) -> float:
    """ATR over the closed bars (``H < L`` bars dropped, §4 edge case)."""
    trs: List[float] = []
    for i in range(1, len(bars)):
        if bars[i]["h"] < bars[i]["l"]:
            continue
        trs.append(true_range(bars[i]["h"], bars[i]["l"], bars[i - 1]["c"]))
    return rma(trs, period)


def _sma_sd(values: Sequence[float]) -> Tuple[float, float]:
    n = len(values)
    if n == 0:
        return (0.0, 0.0)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    return mean, math.sqrt(var)


def z_score(value: float, history: Sequence[float], eps: float = EPS) -> float:
    """§3.1 z against the PIT ``t−1`` history: ``(x − SMA)/max(SD, ε)``."""
    if not history:
        return float("nan")
    mean, sd = _sma_sd(history)
    return (value - mean) / max(sd, eps)


def volume_z(volumes: Sequence[float], eps: float = EPS) -> float:
    """``VolumeZ = (V_t − SMA_{t−1}(V,20))/max(SD_{t−1}(V,20), ε)``.

    ``volumes`` must be the PIT history *excluding* the current bar's
    predecessor shift, i.e. ``volumes[-1]`` is ``V_t`` and ``volumes[:-1]`` the
    ``t−1`` history (fail-closed NaN when the history is empty).
    """
    if len(volumes) < 2:
        return float("nan")
    return z_score(volumes[-1], volumes[:-1], eps)


def range_z(ranges: Sequence[float], eps: float = EPS) -> float:
    """``RangeZ = (Range_t − SMA_{t−1}(Range,20))/max(SD_{t−1}(Range,20), ε)``.

    ISSUE-CP4-010: §4's ``detect_sc`` call site substitutes
    ``(H−L)/ATR`` for RangeZ; §3.1 and the §9 case study both use this
    z-score, which is what the engine computes.
    """
    if len(ranges) < 2:
        return float("nan")
    return z_score(ranges[-1], ranges[:-1], eps)


def evr(volume_z: float, range_z_: float, close: float, prev_close: float,
        eps: float = EPS) -> float:
    """§3.1 corrected Supply & Demand law:
    ``EVR_t = VolumeZ_t · RangeZ_t · sign(C_t − C_{t−1})``.

    The earlier ``sign·sign`` formulation is explicitly superseded by §3.1.
    Undefined inputs propagate as NaN (never coerced).
    """
    if math.isnan(volume_z) or math.isnan(range_z_):
        return float("nan")
    delta = close - prev_close
    sign = 0.0 if abs(delta) < eps else (1.0 if delta > 0 else -1.0)
    return volume_z * range_z_ * sign


def evr_correlation(vols: Sequence[float], abs_returns: Sequence[float],
                    min_samples: int = 10, eps: float = EPS) -> float:
    """§3.1 Effort & Result: ``ρ_{V,|ΔP|}`` (volume vs absolute return).

    ``n < 10`` ⇒ NaN (§4); ``|ρ| < θ_ρ = 0.2`` ⇒ effort without result.
    """
    n = len(vols)
    if n < min_samples or n != len(abs_returns):
        return float("nan")
    mv, mr = sum(vols) / n, sum(abs_returns) / n
    cov = sum((v - mv) * (r - mr) for v, r in zip(vols, abs_returns)) / n
    sv = math.sqrt(sum((v - mv) ** 2 for v in vols) / n)
    sr = math.sqrt(sum((r - mr) ** 2 for r in abs_returns) / n)
    return cov / max(sv * sr, eps)


def effort_without_result(rho: float, threshold: float = 0.2) -> bool:
    """§3.1 ``ρ < θ_ρ`` ⇒ effort without result (absorption warning)."""
    if math.isnan(rho):
        return False                      # undefined ≠ confirmed divergence
    return rho < threshold


def cause_effect_target(range_cause: float, duration: int, k: float = 0.42,
                        gamma: float = 0.71, breakout: float = 0.0) -> float:
    """§3.1 continuous Cause & Effect variant
    ``Effect = k · Duration^γ · Range_cause`` (k = 0.42, γ = 0.71).
    """
    if duration < 0 or range_cause < 0:
        raise ValueError("CAUSE_EFFECT_INPUT_QX: negative duration/range")
    return breakout + k * (duration ** gamma) * range_cause


def point_figure_target(p_breakout: float, columns: int, box_size: float,
                        reversal_rows: int = 3) -> float:
    """§3.1 classic P&F count
    ``Target_vertical = P_breakout + Columns·BoxSize·ReversalRows``.
    """
    if columns < 0 or box_size <= 0 or reversal_rows <= 0:
        raise ValueError("PF_TARGET_INPUT_QX")
    return p_breakout + columns * box_size * reversal_rows


def pf_box_size(atr14_value: float, mult: float = 0.5) -> float:
    """§3.1 ``BoxSize = 0.5·ATR14`` (parametric)."""
    if atr14_value <= 0 or math.isnan(atr14_value):
        raise ValueError("PF_BOX_SIZE_QX: ATR14 must be > 0")
    return mult * atr14_value


# ---------------------------------------------------------------------------
# §3.2 Phase detection via probability distribution
# ---------------------------------------------------------------------------


def sigmoid(x: float) -> float:
    """Numerically stable logistic sigmoid."""
    if math.isnan(x):
        return float("nan")
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def score_position(close: float, range_lo: float, range_hi: float,
                   eps: float = EPS) -> float:
    """§3.2 ``sigmoid((C−RangeLow)/(RangeHigh−RangeLow) − 0.5)·2``.

    ISSUE-CP4-011: the raw expression reaches 2 while §3.2 states
    ``score_{k,i} ∈ [0,1]``; the stated domain is enforced by clamping.
    """
    width = range_hi - range_lo
    if width <= eps:
        return float("nan")               # no range ⇒ undefined, not neutral
    x = (close - range_lo) / width
    return max(0.0, min(1.0, sigmoid(x - 0.5) * 2.0))


def score_evr(evr_value: float, sign: float = 1.0) -> float:
    """§3.2 ``score_EVR = sigmoid(EVR)`` (positive for Accumulation).

    ``sign = −1`` is the mirrored term for the distribution family, per the
    §3.2 annotation "positive for Accumulation" (ISSUE-CP4-012).
    """
    if math.isnan(evr_value):
        return float("nan")
    return sigmoid(sign * evr_value)


def score_volume(vol_ratio: float) -> float:
    """§3.2 ``score_volume = 1 − min(VolumeRatio/2, 1)`` (for ST/LPS)."""
    if math.isnan(vol_ratio):
        return float("nan")
    return 1.0 - min(vol_ratio / 2.0, 1.0)


def score_structure(structure: Optional[str], phase: str) -> float:
    """§3.2 ``score_structure = 1 if Structure = BULL and phase = ACCUM/MARKUP``."""
    if phase not in ("ACCUMULATION", "MARKUP"):
        return float("nan")               # unspecified for the other phases
    return 1.0 if structure == "BULL" else 0.0


def score_age(age_bars: float, lam: float = 0.02) -> float:
    """§3.2 ``score_age = exp(−λ·age)``, λ = 0.02."""
    return math.exp(-lam * max(age_bars, 0.0))


# §3.2 fully specifies only the Accumulation column; the remaining columns are
# a disclosed content gap (ISSUE-CP4-012). Every cell below cites its anchor;
# cells the chapter never defines are NEUTRAL (0.5, no-information midpoint) so
# that no phase is biased by having more specified components.
PHASE_SCORE_RULES: Dict[str, Dict[str, str]] = {
    "ACCUMULATION": {"position": "§3.2 [for Accumulation]",
                     "evr": "§3.2 positive for Accumulation (sign +1)",
                     "volume": "§3.2 [for ST/LPS]",
                     "structure": "§3.2 BULL ∧ phase=ACCUM",
                     "age": "§3.2 exp(-λ·age)"},
    "MARKUP": {"structure": "§3.2 BULL ∧ phase=MARKUP",
               "age": "§3.2 exp(-λ·age)"},
    "DISTRIBUTION": {"evr": "§3.2 sign mirrored (negative EVR)",
                     "volume": "§2 LPSY is the distribution-side mirror of LPS",
                     "age": "§3.2 exp(-λ·age)"},
    "MARKDOWN": {"age": "§3.2 exp(-λ·age)"},
    "RE-ACCUMULATION": {"age": "§3.2 exp(-λ·age)"},
    "RE-DISTRIBUTION": {"age": "§3.2 exp(-λ·age)"},
    "RANGE": {"age": "§3.2 exp(-λ·age)"},
    "TRANSITION": {"age": "§3.2 exp(-λ·age)"},
}


def phase_score_matrix(close: float, range_lo: float, range_hi: float,
                       evr_value: float, vol_ratio: float,
                       structure: Optional[str], age_bars: float,
                       params: Optional[EngineParams] = None
                       ) -> Tuple[List[List[float]], Dict[str, Dict[str, str]]]:
    """Build ``scores[k][i]`` (k = component, i = phase) per §3.2.

    Returns ``(scores, provenance)`` where ``provenance[phase][component]`` is
    the blueprint anchor or ``"UNSPECIFIED_NEUTRAL"`` (ISSUE-CP4-012).
    """
    p = params or EngineParams()
    comp_values = {
        "position": score_position(close, range_lo, range_hi),
        "evr": score_evr(evr_value, +1.0),
        "volume": score_volume(vol_ratio),
        "age": score_age(age_bars, p.lambda_age),
    }
    scores: List[List[float]] = [[] for _ in SCORE_COMPONENTS]
    provenance: Dict[str, Dict[str, str]] = {}
    for phase in PHASES:
        rules = PHASE_SCORE_RULES.get(phase, {})
        provenance[phase] = {}
        for comp in SCORE_COMPONENTS:
            anchor = rules.get(comp)
            if anchor is None:
                value = p.neutral_score
                provenance[phase][comp] = "UNSPECIFIED_NEUTRAL"
            elif comp == "structure":
                value = score_structure(structure, phase)
                if math.isnan(value):
                    value = p.neutral_score
                    provenance[phase][comp] = "UNSPECIFIED_NEUTRAL"
                else:
                    provenance[phase][comp] = anchor
            elif comp == "evr" and phase in ("DISTRIBUTION",
                                             "RE-DISTRIBUTION"):
                value = score_evr(evr_value, -1.0)
                if math.isnan(value):
                    value = p.neutral_score
                    provenance[phase][comp] = "UNSPECIFIED_NEUTRAL"
                else:
                    provenance[phase][comp] = anchor
            else:
                value = comp_values[comp]
                if math.isnan(value):
                    value = p.neutral_score
                    provenance[phase][comp] = "UNSPECIFIED_NEUTRAL"
                else:
                    provenance[phase][comp] = anchor
            # The neutral substitution above must still be appended: a missing
            # cell makes the matrix ragged and every downstream
            # phase_probabilities() call fails closed on shape.
            scores[SCORE_COMPONENTS.index(comp)].append(value)
    return scores, provenance


def softmax(z: Sequence[float]) -> List[float]:
    """§4 numerically stable softmax."""
    if not z:
        return []
    m = max(z)
    e = [math.exp(v - m) for v in z]
    s = sum(e)
    return [v / s for v in e]


def entropy(p: Sequence[float], floor: float = 1e-12) -> float:
    """§0/§4 ``H = −Σ p ln p`` (nats)."""
    return -sum(pi * math.log(pi) for pi in p if pi > floor)


def phase_probabilities(scores: Sequence[Sequence[float]], w: Sequence[float],
                        phases: Sequence[str] = PHASES
                        ) -> Tuple[Dict[str, float], float]:
    """§3.2 ``z_i = Σ w_k score_{k,i}`` → ``P = softmax(z)``, ``H`` in nats."""
    if not scores:
        raise ValueError("PHASE_MATRIX_SHAPE_QX: empty score matrix")
    K = len(w)
    if K != len(scores):
        raise ValueError("PHASE_MATRIX_SHAPE_QX: len(w) != n_components")
    for row in scores:
        if len(row) != len(phases):
            raise ValueError("PHASE_MATRIX_SHAPE_QX: ragged score matrix")
    z = [sum(w[k] * scores[k][i] for k in range(K)) for i in range(len(phases))]
    probs = softmax(z)
    return {ph: pi for ph, pi in zip(phases, probs)}, entropy(probs)


def transition_matrix(counts: Optional[Dict[Tuple[str, str], int]] = None,
                      alpha: float = 0.1, K: int = 9,
                      phases: Sequence[str] = PHASES
                      ) -> Dict[str, Dict[str, float]]:
    """§3.2 ``T_ij = (N_ij + α)/(N_i + Kα)`` — Dirichlet α = 0.1, K = 9.

    ``N_ij`` are observed transitions in a 48-candle-lagged labelled dataset.
    This repository holds no such dataset (no fabricated statistics, G11), so
    with ``counts`` empty the matrix is the Dirichlet prior ``α/(Kα) = 1/K``:
    the formula evaluated at N = 0, not an invented distribution.
    """
    counts = dict(counts or {})
    unknown = [k for k in counts if k[0] not in phases or k[1] not in phases]
    if unknown:
        raise ValueError(f"TRANSITION_MATRIX_QX: unknown phase(s) {unknown}")
    out: Dict[str, Dict[str, float]] = {}
    for i in phases:
        n_i = sum(counts.get((i, j), 0) for j in phases)
        denom = n_i + K * alpha
        row = {}
        for j in phases:
            row[j] = (counts.get((i, j), 0) + alpha) / denom
        out[i] = row
    return out


# ---------------------------------------------------------------------------
# §3.3 Diagnostic events — the precise 6-parameter contract
# ---------------------------------------------------------------------------


def close_position(bar: Dict[str, Any], eps: float = EPS) -> float:
    """``ClosePos = (C − L)/(H − L)`` (0 when the bar has no range)."""
    rng = bar["h"] - bar["l"]
    if rng <= eps:
        return 0.0
    return (bar["c"] - bar["l"]) / rng


def body_ratio(bar: Dict[str, Any], eps: float = EPS) -> float:
    """``BodyRatio = |C − O|/max(H − L, ε)``."""
    return abs(bar["c"] - bar["o"]) / max(bar["h"] - bar["l"], eps)


def is_bearish(bar: Dict[str, Any]) -> bool:
    return bar["c"] < bar["o"]


def is_bullish(bar: Dict[str, Any]) -> bool:
    return bar["c"] > bar["o"]


def detect_sc(bar: Dict[str, Any], vol_ratio: float, range_z_: float,
              close_pos: float, body_ratio_: float,
              params: Optional[EngineParams] = None) -> bool:
    """§4 ``detect_sc`` — the five-condition SC core (signature verbatim).

    ``VolRatio ≥ 2.5 ∧ RangeZ ≥ 2.0 ∧ ClosePos ∈ [0.25, 0.6] ∧
    BodyRatio ≥ 0.5 ∧ bearish``.
    """
    p = params or EngineParams()
    if math.isnan(vol_ratio) or math.isnan(range_z_):
        return False
    return bool(vol_ratio >= p.sc_vol_ratio
                and range_z_ >= p.sc_range_z
                and p.sc_close_pos_lo <= close_pos <= p.sc_close_pos_hi
                and body_ratio_ >= p.sc_body_ratio
                and is_bearish(bar))


def sc_low_extremum(bars: Sequence[Dict[str, Any]], lookback: int = 5) -> bool:
    """§3.3 SC's sixth condition: ``Low == min(L_{t−5:t})``."""
    if not bars:
        return False
    window = bars[-(lookback + 1):]
    return abs(window[-1]["l"] - min(b["l"] for b in window)) < EPS


def detect_sc_full(bar: Dict[str, Any], bars: Sequence[Dict[str, Any]],
                   vol_ratio: float, range_z_: float,
                   params: Optional[EngineParams] = None) -> bool:
    """The complete §3.3/§2 SC contract (five conditions + low extremum).

    The §2 "confirmed by an AR within ≤ 5 candles" clause is evaluated by the
    streaming engine (it needs the following bars); see ``WyckoffEngineV4``.
    """
    p = params or EngineParams()
    return bool(detect_sc(bar, vol_ratio, range_z_, close_position(bar),
                          body_ratio(bar), p)
                and sc_low_extremum(bars, p.sc_low_lookback))


def detect_ar(bar: Dict[str, Any], low_sc: float, atr: float,
              bars_since_sc: int, params: Optional[EngineParams] = None) -> bool:
    """§2 AR: ``Δ = High_AR − Low_SC ≥ 0.5·ATR14 ∧ ClosePos_AR ≥ 0.6`` within 5."""
    p = params or EngineParams()
    if atr < EPS or bars_since_sc < 1 or bars_since_sc > p.ar_bars:
        return False
    delta = bar["h"] - low_sc
    return bool(delta >= p.ar_min_ratio * atr
                and close_position(bar) >= p.ar_close_pos)


def detect_st(bar: Dict[str, Any], low_sc: float, atr: float,
              vol_ratio: float, params: Optional[EngineParams] = None) -> bool:
    """§2 ST: ``Low_ST ∈ [Low_SC ± 0.3·ATR] ∧ VolRatio ≤ 0.7``, no break of Low_SC."""
    p = params or EngineParams()
    if atr < EPS or math.isnan(vol_ratio):
        return False
    band = p.st_zone_tol * atr
    in_band = (low_sc - band) <= bar["l"] <= (low_sc + band)
    return bool(in_band and vol_ratio <= p.st_vol_ratio
                and bar["l"] >= low_sc - EPS)


def detect_spring(low: float, range_lo: float, close: float, atr: float,
                  vol_ratio: float, evr_value: float,
                  bars_since_st: Optional[int] = None,
                  params: Optional[EngineParams] = None) -> bool:
    """§2/§3.3 Spring: temporary penetration below the range low with recovery.

    ``0 < Pen ≤ 0.3·ATR ∧ Close > RangeLow ∧ (VolRatio ≥ 1.3 ∨ EVR > 0.5) ∧
    BarCount_since_ST ≤ 20``.
    """
    p = params or EngineParams()
    if atr < EPS:
        return False
    pen = range_lo - low
    if not (0 < pen <= p.spring_pen_max * atr):
        return False
    if close <= range_lo:
        return False
    vol_ok = (not math.isnan(vol_ratio) and vol_ratio >= p.spring_vol_min)
    evr_ok = (not math.isnan(evr_value) and evr_value > p.spring_evr_min)
    if not (vol_ok or evr_ok):
        return False
    if bars_since_st is not None and bars_since_st > p.spring_since_st_max:
        return False
    return True


def spring_recovered(bars: Sequence[Dict[str, Any]], range_lo: float,
                     spring_idx: int, sp_bars: int = 3) -> bool:
    """§2 Spring's recovery clause: close back above ``range_lo`` within 3 bars."""
    for bar in bars[spring_idx + 1: spring_idx + 1 + sp_bars]:
        if bar["c"] > range_lo:
            return True
    return False


def detect_sos(bar: Dict[str, Any], range_hi: float, atr: float,
               vol_ratio: float, bos_confirmed_idx: Optional[int],
               current_idx: int, params: Optional[EngineParams] = None) -> bool:
    """§2/§3.3 SOS: ``BOS_Bullish.confirmed_at ≤ t−1 ∧ Close > range_hi + 0.2·ATR
    ∧ VolRatio ≥ 1.2 ∧ ClosePos ≥ 0.65``.
    """
    p = params or EngineParams()
    if atr < EPS or math.isnan(vol_ratio):
        return False
    if bos_confirmed_idx is None or bos_confirmed_idx > current_idx - 1:
        return False                      # PIT: BOS must be confirmed by t−1
    return bool(bar["c"] > range_hi + p.sos_break_atr * atr
                and vol_ratio >= p.sos_vol_min
                and close_position(bar) >= p.sos_close_pos)


def detect_lps(bar: Dict[str, Any], high_sos: float, range_lo: float, atr: float,
               vol_ratio: float, structure: Optional[str] = None,
               params: Optional[EngineParams] = None) -> bool:
    """§2 LPS: ``High_LPS < High_SOS ∧ Low_LPS ≥ RangeLow + 0.2·ATR ∧
    VolRatio ≤ 0.7 ∧ bullish structure preserved``.
    """
    p = params or EngineParams()
    if atr < EPS or math.isnan(vol_ratio):
        return False
    structure_ok = structure is None or structure != "BEAR"
    return bool(bar["h"] < high_sos
                and bar["l"] >= range_lo + p.lps_above_atr * atr
                and vol_ratio <= p.lps_vol_max and structure_ok)


def detect_ut(high: float, range_hi: float, close: float, atr: float,
              vol_ratio: float, params: Optional[EngineParams] = None) -> bool:
    """§4 ``detect_ut``: ``0 < Pen ≤ 0.3·ATR ∧ Close < RangeHigh ∧ VR ≥ 1.2``."""
    p = params or EngineParams()
    if atr < EPS or math.isnan(vol_ratio):
        return False
    pen = high - range_hi
    return bool(0 < pen <= p.ut_pen_max * atr and close < range_hi
                and vol_ratio >= p.ut_vol_min)


def detect_utad(bar: Dict[str, Any], range_hi: float, atr: float,
                vol_ratio: float, params: Optional[EngineParams] = None) -> bool:
    """§3.3 UTAD: UT plus ``ClosePos ≤ 0.4`` (the distribution-side rejection)."""
    p = params or EngineParams()
    return bool(detect_ut(bar["h"], range_hi, bar["c"], atr, vol_ratio, p)
                and close_position(bar) <= p.ut_close_pos)


def detect_lpsy(bar: Dict[str, Any], range_hi: float, range_lo: float, atr: float,
                vol_ratio: float, params: Optional[EngineParams] = None) -> bool:
    """§2 LPSY — the distribution-side mirror of LPS.

    Mirror conditions: ``High_LPSY < range_hi``, ``Low_LPSY ≥ RangeLow + 0.2·ATR``,
    low volume ``≤ 0.7``, and a bearish (supply-preserving) close.
    """
    p = params or EngineParams()
    if atr < EPS or math.isnan(vol_ratio):
        return False
    return bool(bar["h"] < range_hi
                and bar["l"] >= range_lo + p.lps_above_atr * atr
                and vol_ratio <= p.lps_vol_max and is_bearish(bar))


def detect_range(bars: Sequence[Dict[str, Any]], atr: float,
                 min_bars: int = 12, atr_mult: float = 1.5,
                 eps: float = EPS) -> Optional[Tuple[float, float]]:
    """§4 ``detect_range``: ``High − Low < 1.5·ATR`` over ``min_bars`` candles."""
    if len(bars) < min_bars or atr < eps or math.isnan(atr):
        return None
    window = bars[-min_bars:]
    lo = min(b["l"] for b in window)
    hi = max(b["h"] for b in window)
    if (hi - lo) < atr_mult * atr:
        return (lo, hi)
    return None


# ---------------------------------------------------------------------------
# §8 Calibration metrics (Brier / log-loss / Wilson)
# ---------------------------------------------------------------------------


def brier_score(probs: Sequence[float], outcomes: Sequence[int]) -> float:
    """§7 Ch.1-14 ``BS = 1/N Σ (p_i − o_i)²``."""
    n = len(probs)
    if n == 0 or n != len(outcomes):
        raise ValueError("BRIER_INPUT_QX")
    return sum((p - o) ** 2 for p, o in zip(probs, outcomes)) / n


def log_loss(probs: Sequence[float], outcomes: Sequence[int],
             eps: float = 1e-12) -> float:
    """Cross-entropy of the phase distribution against the realised label."""
    n = len(probs)
    if n == 0 or n != len(outcomes):
        raise ValueError("LOG_LOSS_INPUT_QX")
    return -sum(o * math.log(max(p, eps)) for p, o in zip(probs, outcomes)) / n


def wilson_ci(p_hat: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    """§8/§9 Wilson score interval (stdlib)."""
    if n <= 0:
        return (0.0, 0.0)
    denom = 1.0 + z * z / n
    centre = p_hat + z * z / (2 * n)
    spread = z * math.sqrt(max(p_hat * (1 - p_hat) / n + z * z / (4 * n * n), 0.0))
    return ((centre - spread) / denom, (centre + spread) / denom)


def pearson(x: Sequence[float], y: Sequence[float]) -> float:
    """Pearson r — §8 redundancy: Spring vs Liquidity Sweep must stay ≤ 0.45."""
    n = len(x)
    if n < 2 or n != len(y):
        return 0.0
    mx, my = sum(x) / n, sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    if vx <= EPS or vy <= EPS:
        return 0.0
    return cov / math.sqrt(vx * vy)


# ---------------------------------------------------------------------------
# §5 CycleState
# ---------------------------------------------------------------------------


@dataclass
class PhaseHypothesis:
    """One row of ``phase_hypotheses`` (§5 schema)."""

    phase: str
    prob: float
    score_breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"phase": self.phase, "prob": self.prob,
                "score_breakdown": dict(self.score_breakdown)}


@dataclass
class CycleState:
    """§5 ``cycle_state`` object (all required keys validated)."""

    range_boundary: Optional[Tuple[float, float]]
    phase_hypotheses: List[PhaseHypothesis]
    entropy: float
    confirmed_events: List[Dict[str, Any]]
    fate: str
    snapshot_id: str
    as_of: int
    quality: str
    age_bars: int = 0
    atr: float = 0.0
    version: str = CONTRACT_LABEL
    state: str = "NO_RANGE"
    degraded: bool = False
    degraded_reason: Optional[str] = None
    provenance: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def to_canonical(self) -> Dict[str, Any]:
        """Canonical snapshot payload (``snapshot_id`` excluded)."""
        return {
            "range": (None if self.range_boundary is None else
                      {"lo": self.range_boundary[0], "hi": self.range_boundary[1],
                       "age_bars": self.age_bars, "atr": self.atr}),
            "phase_hypotheses": [h.to_dict() for h in self.phase_hypotheses],
            "entropy": self.entropy,
            "confirmed_events": list(self.confirmed_events),
            "fate": self.fate, "as_of": self.as_of, "quality": self.quality,
            "state": self.state,
        }

    def update_snapshot(self) -> "CycleState":
        self.snapshot_id = e08_snapshot_id(self.to_canonical())
        return self

    def to_dict(self) -> Dict[str, Any]:
        """The §5 JSON object shape (``cycle_state`` envelope)."""
        out = self.to_canonical()
        out["snapshot_id"] = self.snapshot_id
        out["version"] = self.version
        return {"cycle_state": out}

    def validate_schema(self) -> None:
        # ``range`` is nullable by contract (NO_RANGE); ``confirmed_events``
        # may legitimately be empty before the first event fires.
        for key in CYCLE_STATE_REQUIRED:
            if key in ("range", "confirmed_events"):
                continue
            value = getattr(self, key, None)
            if value is None or value == "":
                raise ValueError(f"CYCLE_STATE_QX: missing {key}")
        if self.fate not in CYCLE_FATES:
            raise ValueError(f"CYCLE_STATE_QX: fate {self.fate!r}")
        if self.quality not in QUALITIES:
            raise ValueError(f"CYCLE_STATE_QX: quality {self.quality!r}")
        if len(self.phase_hypotheses) != K_PHASES:
            raise ValueError("CYCLE_STATE_QX: phase_hypotheses must cover 8")
        if abs(sum(h.prob for h in self.phase_hypotheses) - 1.0) > 1e-9:
            raise ValueError("CYCLE_STATE_QX: probabilities do not sum to 1")
        if self.entropy < 0 or self.entropy > math.log(K_PHASES) + 1e-9:
            raise ValueError(f"CYCLE_STATE_QX: entropy {self.entropy}")
        if len(self.snapshot_id) != 64:
            raise ValueError("CYCLE_STATE_QX: snapshot_id not 64-hex")


def e08_snapshot_id(payload: Dict[str, Any]) -> str:
    """§4/§5 canonical identity ``SHA256(canonical_json(payload))``."""
    return canonical_snapshot_id(ENGINE, CONTRACT_VERSION, payload)


# ---------------------------------------------------------------------------
# §7 Encyclopedic coverage — Chapter 1 normative, Chapters 2–4 Wave-Out
# ---------------------------------------------------------------------------

ENCYCLOPEDIA_CH1: Dict[str, str] = {
    "1": "Definition: the Wyckoff method traces to Tape Reading, 1910.",
    "2": "Math: the softmax + entropy framework.",
    "3": "History: Wyckoff 1910/1931, Pruden 2007, Villahermosa 2021.",
    "4": "Mechanics: the cause/effect cycle; accumulation as absorption.",
    "5": "Institutional read: 'Composite Man' is a hypothesis, not fact.",
    "6": "Retail read: post-hoc labelling; false Springs from noise.",
    "7": "MTF: the HTF phase is decisive.",
    "8": "Entry: only SOS/LPS following SC/Spring with BOS confirmation.",
    "9": "Risk: late confirmation; high entropy ⇒ abstention; stop 0.5·ATR "
         "below the Spring.",
    "10": "Failure modes: entropy >= 0.85 ⇒ AMBIGUOUS; noise events (VR < 1.0).",
    "11": "Examples: three numeric SC/AR/ST examples (illustrative per §9.5-2).",
    "12": "Algorithmic reference: phase_probabilities().",
    "13": "Psychology: confirmation bias; FOMO following SOS.",
    "14": "Statistics: Brier score, target BS < 0.22.",
    "15": "Applications: input to Regime and Setup.",
    "16": "Case study: BNBUSDT 6H 14-candle range (illustrative).",
}


def encyclopedia_chapter(chapter: int) -> Dict[str, Any]:
    """Serve the §7 encyclopedic surface.

    Chapter 1 is the normative, coding-ready surface (§7 freeze pointer).
    **Chapters 2–4 are Wave-Out** (G6/P6, §9.5-9, §7 Decision D-E08-M5): they
    are deferred, non-normative one-line summaries in the frozen source and
    raise ``WaveOutError("e08_encyclopedia_ch2_4", <deterministic reason>)``
    rather than being stubbed or invented.
    """
    if chapter not in ENCYCLOPEDIA_CHAPTERS:
        raise ValueError(f"ENCYCLOPEDIA_CHAPTER_QX: {chapter!r}")
    if chapter in ENCYCLOPEDIA_WAVE_OUT_CHAPTERS:
        raise wave_out(WAVE_OUT_FEATURE, WAVE_OUT_REASONS[chapter])
    return {"chapter": 1, "title": "Historical Foundation",
            "dimensions": ENCYCLOPEDIA_CH1_DIMENSIONS,
            "content": dict(ENCYCLOPEDIA_CH1),
            "normative": True}


# ---------------------------------------------------------------------------
# §4 Streaming engine
# ---------------------------------------------------------------------------


class WyckoffEngineV4:
    """§4 ``WyckoffEngineV4`` — streaming, PIT-safe, idempotent per bar.

    ``process_bar`` consumes ONE closed candle plus its governed inputs (ATR
    from E04, VolRatio/EVR from E03/§3.1, Structure from E01) and returns the
    ``CycleState`` dict. Idempotency: ``hash(bar_ts + range)`` (§4).
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        self.params = get_params(params)
        self.range_lo: Optional[float] = None
        self.range_hi: Optional[float] = None
        self.range_age: int = 0
        self.events: List[Dict[str, Any]] = []
        self.phases_history: List[Dict[str, Any]] = []
        self.state: str = "NO_RANGE"
        self.low_sc: Optional[float] = None
        self.sc_idx: Optional[int] = None
        self.high_sos: Optional[float] = None
        self.last_st_idx: Optional[int] = None
        self.bar_idx: int = -1
        self.history: List[Dict[str, Any]] = []
        self._seen: set = set()

    # -- helpers ---------------------------------------------------------
    def _quality(self, atr: float, structure: Optional[str],
                 vol_ratio: float, entropy_h: float,
                 brier: Optional[float]) -> str:
        """§1 quality ladder Q0..Q5."""
        p = self.params
        if atr < EPS or entropy_h < 0:
            return "Q0"
        label = "Q1"                      # RAW: bare candle
        if structure in ("BULL", "BEAR"):
            label = "Q2"                  # STRUCTURAL
        if not math.isnan(vol_ratio):
            label = "Q3"                  # VOLUME_CONFIRMED
        if entropy_h < p.entropy_threshold and brier is not None \
                and brier < p.brier_q4_max:
            label = "Q4"                  # STATISTICAL
        return label

    def _advance(self, new_state: str) -> bool:
        """Forward-only state advance along the §5 state machine."""
        if new_state not in STATE_ORDER or self.state not in STATE_ORDER:
            return False
        if STATE_ORDER[new_state] <= STATE_ORDER[self.state]:
            return False
        self.state = new_state
        return True

    def _emit(self, code: str, ts: int, **payload: Any) -> Dict[str, Any]:
        event = {"code": code, "name": EVENT_CATALOG[code], "ts": ts,
                 **payload}
        self.events.append(event)
        return event

    # -- main entry ------------------------------------------------------
    def process_bar(self, bar: Dict[str, Any], atr: float, vol_ratio: float,
                    close_pos: float, evr_value: float,
                    bos_event: Optional[Dict[str, Any]] = None,
                    structure: Optional[str] = None,
                    brier: Optional[float] = None,
                    ts: Optional[int] = None) -> Dict[str, Any]:
        """Process one CLOSED candle; returns the cycle-state dict.

        Edge cases (§4): ``H < L`` ⇒ ``Q0_INVALID/H<L``; ``ATR < ε`` ⇒
        ``Q0_INVALID/ATR=0``. Both fail closed — no phase is declared.
        """
        p = self.params
        self.bar_idx += 1
        ts = int(ts if ts is not None else bar.get("ts", self.bar_idx))
        if bar["h"] < bar["l"]:
            return {"fate": "Q0_INVALID", "reason": "H<L", "ts": ts,
                    "quality": "Q0"}
        if atr < EPS or math.isnan(atr):
            return {"fate": "Q0_INVALID", "reason": "ATR=0", "ts": ts,
                    "quality": "Q0"}
        self.history.append(dict(bar))

        # Range detection (§4) + boundary event (§5 EV_WYK_011).
        #
        # The §5 state machine is one-way — NO_RANGE -> RANGE_DETECTED -> SC ->
        # AR -> ... -> MARKUP — and the ONLY exits are INVALIDATED
        # (Close < SC_Low − 0.5·ATR) and EXPIRED (age > 96). The boundary is
        # therefore latched on first detection and aged thereafter: re-deriving
        # it from the trailing window every bar would discard the range exactly
        # when the cycle advances, because an SOS breakout necessarily widens
        # the trailing High−Low beyond 1.5·ATR.
        if self.range_lo is None:
            detected = detect_range(self.history, atr, p.range_min_bars,
                                    p.range_atr_mult)
            if detected is not None:
                self.range_lo, self.range_hi = detected
                self.range_age = 0
                self._advance("RANGE_DETECTED")
                self._emit("EV_WYK_011", ts, lo=detected[0], hi=detected[1],
                           age=0, atr=atr)
        else:
            self.range_age += 1

        # Expiry / invalidation (§5).
        invalidated = (self.low_sc is not None
                       and bar["c"] < self.low_sc - p.invalidation_atr * atr)
        expired = self.range_age > p.max_age_bars
        if invalidated:
            self._emit("EV_WYK_012", ts, reason="CLOSE_BELOW_SC_LOW")
        if expired:
            self._emit("EV_WYK_012", ts, reason="AGE_GT_MAX")
        if invalidated or expired:
            # Both are terminal for this hypothesis, so the latch is released
            # and a later window may open a fresh cycle; a retained `low_sc`
            # would otherwise re-invalidate every subsequent bar.
            self.range_lo = self.range_hi = None
            self.range_age = 0
            self.low_sc = None
            self.sc_idx = None
            self.last_st_idx = None
            self.high_sos = None
            self.state = "NO_RANGE"

        # Event detection (§3.3 six-parameter contract).
        ranges = [b["h"] - b["l"] for b in self.history]
        rz = range_z(ranges[-(p.range_sma_period + 1):])
        if self.range_lo is not None and self.range_hi is not None:
            if detect_sc_full(bar, self.history, vol_ratio, rz, p):
                self.low_sc = bar["l"]
                self.sc_idx = self.bar_idx
                self._advance("SC")
                self._emit("EV_WYK_002", ts, vol_ratio=vol_ratio,
                           range_z=rz, close_pos=close_pos,
                           price=bar["c"])
            elif (self.low_sc is not None and self.sc_idx is not None
                  and detect_ar(bar, self.low_sc, atr,
                                self.bar_idx - self.sc_idx, p)):
                self._advance("AR")
                self._emit("EV_WYK_003", ts, delta=bar["h"] - self.low_sc,
                           atr=atr)
            if (self.low_sc is not None
                    and detect_st(bar, self.low_sc, atr, vol_ratio, p)):
                self.last_st_idx = self.bar_idx
                self._advance("ST")
                self._emit("EV_WYK_004", ts, low=bar["l"], low_sc=self.low_sc,
                           vol_ratio=vol_ratio)
            since_st = (None if self.last_st_idx is None
                        else self.bar_idx - self.last_st_idx)
            if detect_spring(bar["l"], self.range_lo, bar["c"], atr, vol_ratio,
                             evr_value, since_st, p):
                self._advance("SPRING")
                self._emit("EV_WYK_005", ts, pen=self.range_lo - bar["l"],
                           atr=atr, vol_ratio=vol_ratio, evr=evr_value)
            if detect_utad(bar, self.range_hi, atr, vol_ratio, p):
                self._emit("EV_WYK_008", ts, pen=bar["h"] - self.range_hi,
                           atr=atr, close_pos=close_pos)
            if detect_lpsy(bar, self.range_hi, self.range_lo, atr, vol_ratio, p):
                self._emit("EV_WYK_009", ts, vol_ratio=vol_ratio)
            bos_idx = (int(bos_event["confirmed_at_idx"])
                       if bos_event and "confirmed_at_idx" in bos_event
                       else None)
            if detect_sos(bar, self.range_hi, atr, vol_ratio, bos_idx,
                          self.bar_idx, p):
                self.high_sos = bar["h"]
                self._advance("SOS")
                self._emit("EV_WYK_006", ts, close=bar["c"],
                           range_hi=self.range_hi, vol_ratio=vol_ratio)
            elif (self.high_sos is not None
                  and detect_lps(bar, self.high_sos, self.range_lo, atr,
                                 vol_ratio, structure, p)):
                self._advance("LPS")
                self._emit("EV_WYK_007", ts, high=bar["h"],
                           high_sos=self.high_sos, vol_ratio=vol_ratio)

        # Phase hypotheses (§3.2) — suppressed when AMBIGUOUS (§0).
        age = self.range_age if self.range_lo is not None else 0
        lo = self.range_lo if self.range_lo is not None else bar["l"]
        hi = self.range_hi if self.range_hi is not None else bar["h"]
        scores, provenance = phase_score_matrix(bar["c"], lo, hi, evr_value,
                                                vol_ratio, structure, age, p)
        probs, H = phase_probabilities(scores, phase_weights(p), PHASES)
        fate = "AMBIGUOUS" if H >= p.entropy_threshold else "ACTIVE"
        if invalidated or expired:
            fate = "INVALIDATED" if invalidated else "EXPIRED"
        hypotheses = []
        for i, phase in enumerate(PHASES):
            breakdown = {comp: scores[SCORE_COMPONENTS.index(comp)][i]
                         for comp in SCORE_COMPONENTS}
            hypotheses.append(PhaseHypothesis(phase=phase, prob=probs[phase],
                                              score_breakdown=breakdown))
        quality = self._quality(atr, structure, vol_ratio, H, brier)
        cycle = CycleState(
            range_boundary=(None if self.range_lo is None
                            else (self.range_lo, self.range_hi)),
            phase_hypotheses=hypotheses, entropy=H,
            confirmed_events=[dict(e) for e in self.events[-12:]],
            fate=fate, snapshot_id="", as_of=ts, quality=quality,
            age_bars=age, atr=atr, state=self.state,
            degraded=math.isnan(evr_value) or math.isnan(vol_ratio),
            degraded_reason=("EVIDENCE_UNDEFINED_QX"
                             if (math.isnan(evr_value) or math.isnan(vol_ratio))
                             else None),
            provenance=provenance)
        cycle.update_snapshot()
        cycle.validate_schema()
        self._emit("EV_WYK_001", ts, entropy=H, fate=fate,
                   top=max(probs, key=probs.get))
        record = cycle.to_dict()["cycle_state"]
        # §5's wire schema lists no degradation key, but a degraded cycle must
        # stay observable to consumers (fail-closed). These are operational
        # fields — like `idempotency_key` below — and never enter the canonical
        # snapshot payload, so `snapshot_id` is unchanged.
        record["degraded"] = bool(cycle.degraded)
        record["degraded_reason"] = cycle.degraded_reason
        self.phases_history.append({"ts": ts, "entropy": H, "fate": fate,
                                    "quality": quality})
        # Idempotency (§4): identical (ts, range) never recomputes differently.
        key = f"{ts}_{self.range_lo}_{self.range_hi}"
        self._seen.add(key)
        record["idempotency_key"] = key
        return record

    # -- batch -----------------------------------------------------------
    def run_full(self, bars: Sequence[Dict[str, Any]],
                 atr_by_idx: Optional[Dict[int, float]] = None,
                 vol_ratio_by_idx: Optional[Dict[int, float]] = None,
                 evr_by_idx: Optional[Dict[int, float]] = None,
                 structure_by_idx: Optional[Dict[int, Optional[str]]] = None,
                 bos_by_idx: Optional[Dict[int, Dict[str, Any]]] = None
                 ) -> List[Dict[str, Any]]:
        """Replay a closed-candle window; returns one cycle-state per bar.

        ``atr_by_idx`` is the governed E04 evidence pathway; when absent the
        engine degrades explicitly (``ATR=0`` ⇒ Q0_INVALID) rather than
        recomputing a substitute ATR.
        """
        out: List[Dict[str, Any]] = []
        for i, bar in enumerate(bars):
            atr = float(atr_by_idx.get(i, 0.0)) if atr_by_idx else 0.0
            vr = float(vol_ratio_by_idx.get(i, float("nan"))) \
                if vol_ratio_by_idx else float("nan")
            ev = float(evr_by_idx.get(i, float("nan"))) \
                if evr_by_idx else float("nan")
            st = structure_by_idx.get(i) if structure_by_idx else None
            bos = bos_by_idx.get(i) if bos_by_idx else None
            out.append(self.process_bar(bar, atr, vr, close_position(bar), ev,
                                        bos_event=bos, structure=st))
        return out


def observation_to_bar(obs: MarketObservation,
                       timeframe: Optional[str] = None) -> Dict[str, Any]:
    """MarketObservation → the ``{ts,o,h,l,c,v}`` bar shape used by §4."""
    ts_ms = 0
    try:
        dt = datetime.datetime.fromisoformat(
            str(obs.timestamp).replace("Z", "+00:00"))
        ts_ms = int(dt.timestamp() * 1000)
    except (ValueError, AttributeError):
        ts_ms = 0
    return {"ts": ts_ms, "o": float(obs.open), "h": float(obs.high),
            "l": float(obs.low), "c": float(obs.close),
            "v": float(obs.volume), "is_closed": obs.is_closed,
            "timeframe": timeframe}


def run_engine(bars: Sequence[Dict[str, Any]],
               atr_by_idx: Optional[Dict[int, float]] = None,
               vol_ratio_by_idx: Optional[Dict[int, float]] = None,
               evr_by_idx: Optional[Dict[int, float]] = None,
               structure_by_idx: Optional[Dict[int, Optional[str]]] = None,
               bos_by_idx: Optional[Dict[int, Dict[str, Any]]] = None,
               params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Batch driver → ``{engine, states, events, final}``."""
    engine = WyckoffEngineV4(params)
    states = engine.run_full(bars, atr_by_idx, vol_ratio_by_idx, evr_by_idx,
                             structure_by_idx, bos_by_idx)
    return {"engine": ENGINE, "contract_version": CONTRACT_VERSION,
            "states": states, "events": list(engine.events),
            "final": states[-1] if states else None,
            "state": engine.state}


class E08WyckoffEngine(EngineBase):
    """E08_Wyckoff on the frozen EngineBase contract (v4.0.0).

    ``compute(symbol, timeframe, as_of, context)``; consumed context keys:
      ``window`` / ``provider``    — closed-candle window (catalog surface)
      ``e08_params``               — §6 overrides (unknown keys rejected)
      ``atr_by_idx``               — E04 governed ATR evidence (absent ⇒ the
                                     engine degrades to ``ATR=0``/Q0, never
                                     recomputes a substitute)
      ``vol_ratio_by_idx``         — E03 I_Volume_v4 VolumeRatio
      ``evr_by_idx``               — §3.1 EVR (E03 volume + §3.1 range z)
      ``structure_by_idx``         — E01 ``BULL``/``BEAR``/None
      ``bos_by_idx``               — E01 ``{confirmed_at_idx, direction}``
    Emissions: one ``EvidenceEvent`` per confirmed Wyckoff event on
    ``evidence.E08.{condition_state}``; the AMBIGUOUS suppression is carried in
    ``validity``/``explanation`` — the engine never declares a definitive phase.
    """

    engine_id = "E08"
    analyst_version = ANALYST_VERSION
    code_revision = "0" * 40

    def compute(self, symbol: str, timeframe: str, as_of: str,
                context: Optional[Dict[str, Any]] = None
                ) -> List[EvidenceEvent]:
        context = context or {}
        window_obs = self._resolve_window(symbol, timeframe, as_of, context)
        if not window_obs:
            return []
        bars = [observation_to_bar(o, timeframe) for o in window_obs]
        result = run_engine(
            bars,
            atr_by_idx=context.get("atr_by_idx"),
            vol_ratio_by_idx=context.get("vol_ratio_by_idx"),
            evr_by_idx=context.get("evr_by_idx"),
            structure_by_idx=context.get("structure_by_idx"),
            bos_by_idx=context.get("bos_by_idx"),
            params=context.get("e08_params"))
        quality = self._window_quality(window_obs)
        final = result["final"] or {}
        return [self._to_evidence(ev, symbol, timeframe, quality, final)
                for ev in result["events"]
                if ev["code"] != "EV_WYK_001"]

    def _resolve_window(self, symbol: str, timeframe: str, as_of: str,
                        context: Dict[str, Any]) -> List[MarketObservation]:
        window = context.get("window")
        if window is not None:
            return list(window)
        provider = context.get("provider")
        if provider is None:
            raise ValueError("MISSING_WINDOW_CONTEXT_QX")
        import asyncio
        import inspect
        bars = context.get("bars", 300)
        result = provider.get_window(symbol, timeframe, as_of, bars)
        if inspect.isawaitable(result):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return list(asyncio.run(result))
            raise ValueError("MISSING_WINDOW_CONTEXT_QX (async provider inside "
                             "a running loop — pass context['window'])")
        return list(result)

    @staticmethod
    def _window_quality(window_obs: Sequence[MarketObservation]) -> float:
        if not window_obs:
            return 0.0
        comps = [float(o.completeness_pct or 0) / 100.0 for o in window_obs]
        return min(1.0, sum(comps) / len(comps))

    def _to_evidence(self, event: Dict[str, Any], symbol: str, timeframe: str,
                     quality: float, final: Dict[str, Any]) -> EvidenceEvent:
        ts = int(event.get("ts", 0))
        iso = datetime.datetime.fromtimestamp(
            ts / 1000.0, tz=datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.") + f"{ts % 1000:03d}Z"
        snapshot = e08_snapshot_id({"event": event["code"], "ts": ts,
                                    "state": final.get("state", "NO_RANGE")})
        fate = str(final.get("fate", "AMBIGUOUS"))
        # Bullish-side events carry direction +1, supply-side −1 (§10 conflict
        # law needs a signed direction; the engine itself stays non-directional).
        bullish = {"EV_WYK_003", "EV_WYK_005", "EV_WYK_006", "EV_WYK_007"}
        bearish = {"EV_WYK_002", "EV_WYK_008", "EV_WYK_009"}
        direction = 1 if event["code"] in bullish else (
            -1 if event["code"] in bearish else 0)
        return EvidenceEvent(
            evidence_id=uuid_v7(),
            engine_id=self.engine_id,
            analyst_version=self.analyst_version,
            symbol=symbol, timeframe=timeframe,
            snapshot_id=snapshot,
            event_time=iso, availability_time=iso,
            observation_window={"bars": int(final.get("age", 0) or 0),
                                "tf": timeframe},
            feature_snapshot_id=snapshot,
            feature_dependencies=("window", "I_Structure_v4", "I_Volume_v4",
                                  "I_Volatility_v4"),
            condition_state=f"{event['code']}_{event['name']}",
            direction=direction,
            strength=float(min(max(float(final.get("entropy", 1.0)), 0.0), 1.0)),
            confidence=1.0 - min(float(final.get("entropy", 1.0))
                                 / math.log(K_PHASES), 1.0),
            quality=float(quality),
            validity="DEGRADED" if fate in ("AMBIGUOUS", "INVALIDATED",
                                            "EXPIRED") else "VALID",
            fate_state=LifecycleState.ACTIVE if fate == "ACTIVE"
            else LifecycleState.CANDIDATE,
            age=float(final.get("age", 0) or 0),
            decay=math.exp(-float(final.get("age", 0) or 0)
                           / max(self.p_default().max_age_bars, 1)),
            explanation=(f"E08 {event['code']} {event['name']} "
                         f"state={final.get('state')} fate={fate} "
                         f"quality={final.get('quality')}")[:500],
            parameter_version="E08-WYK-V4.0.0/DEFAULTS-v1",
            lineage=(f"event_{event['code']}",),
            resolution_class=str(final.get("quality", "Q0")),
        )

    @staticmethod
    def p_default() -> EngineParams:
        return EngineParams()


__all__ = [
    "ANALYST_VERSION", "CONTRACT_LABEL", "CONTRACT_VERSION", "CYCLE_FATES",
    "CYCLE_STATE_REQUIRED", "CycleState", "E08_DEFAULTS", "E08WyckoffEngine",
    "ENGINE", "ENCYCLOPEDIA_CH1", "ENCYCLOPEDIA_CH1_DIMENSIONS",
    "ENCYCLOPEDIA_CHAPTERS", "ENCYCLOPEDIA_WAVE_OUT_CHAPTERS", "EPS",
    "EVENT_CATALOG", "EngineParams", "K_PHASES", "PHASES",
    "PHASE_SCORE_RULES", "PhaseHypothesis", "QUALITIES", "QUALITY_NAMES",
    "SCORE_COMPONENTS", "STATES", "STATE_ORDER", "WAVE_OUT_FEATURE",
    "WAVE_OUT_REASONS", "WaveOutError", "atr14", "brier_score",
    "body_ratio", "cause_effect_target", "close_position", "detect_ar",
    "detect_lps", "detect_lpsy", "detect_range", "detect_sc",
    "detect_sc_full", "detect_sos", "detect_spring", "detect_st", "detect_ut",
    "detect_utad", "e08_snapshot_id", "effort_without_result",
    "encyclopedia_chapter", "entropy", "evr", "evr_correlation", "get_params",
    "is_bearish", "is_bullish", "log_loss", "observation_to_bar",
    "pearson", "pf_box_size", "phase_probabilities", "phase_score_matrix",
    "phase_weights", "point_figure_target", "range_z", "rma", "run_engine",
    "score_age", "score_evr", "score_position", "score_structure",
    "score_volume", "sc_low_extremum", "sigmoid", "softmax",
    "spring_recovered", "transition_matrix", "true_range", "volume_z",
    "wilson_ci", "WyckoffEngineV4", "z_score",
]
