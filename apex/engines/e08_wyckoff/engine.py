"""APEX_GEN5 E08 — Wyckoff / Auction Theory engine (v4.0.0).

Blueprint: APEX_GEN5.md L9086–9466 (chapter order mirrored: §3 formulas →
§4 algorithms → §5 objects/state/events → §6 params → §7 encyclopedia →
§8 validation hooks). The Wyckoff engine models the Wyckoff method
(1910/1931) + Pruden/Villahermosa as calibrated probabilistic hypotheses:
output is ``PhaseHypotheses`` (a probability vector over 8 phases) with
entropy ``H = -Σ p ln p``, a Dirichlet transition matrix, a ``CycleState``,
and diagnostic events SC/AR/ST/Spring/SOS/LPS/UT/UTAD/LPSY. Never a
definitive phase label without an attached probability, never a direct
entry/exit signal.

Three laws quantified: Supply & Demand via the corrected
``EVR = VolumeZ * RangeZ * sign(ΔC)``; Cause & Effect via P&F count +
continuous ``Effect = k·Duration^γ·Range_cause`` (k=0.42, γ=0.71);
Effort & Result via ``ρ_{V,|ΔP|}`` with θ_ρ=0.2 divergence.

Encyclopedia chapters 2–4 are Wave-Out (raise WaveOutError, never stub
silently — §9.5-9 / G6 / D-E08-M5): chapter 1 (Historical Foundation) is
complete; chapters 2–4 remain deferred non-normative reference in the
source and MUST raise ``WaveOutError("e08_encyclopedia_ch2_4", ...)``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from apex.data_catalog.contracts import (
    EvidenceEvent,
    LifecycleState,
    MarketObservation,
)
from apex.engines.base import EngineBase
from apex.errors import wave_out
from apex.identity.snapshot import canonical_snapshot_id
from apex.identity.uuid_v7 import uuid_v7
from apex.quality.numerical import eps_for_engine

ENGINE = "E08_Wyckoff"
CONTRACT_VERSION = "4.0.0"          # APEX-CONTRACT-WYCKOFF-V4.0.0
ANALYST_VERSION = "4.0.0+" + "0" * 40
EPS = float(eps_for_engine("E08"))          # 1e-8 (§2.2 E08 row)

PHASES = ("ACCUMULATION", "MARKUP", "DISTRIBUTION", "MARKDOWN",
          "RE-ACCUMULATION", "RE-DISTRIBUTION", "RANGE", "TRANSITION")
N_PHASES = len(PHASES)

EVENT_CATALOG = {
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

QUALITIES = ("Q0_INVALID", "Q1_RAW", "Q2_STRUCTURAL", "Q3_VOLUME_CONFIRMED",
             "Q4_STATISTICAL", "Q5_GOLDEN")
FATES = ("NO_RANGE", "RANGE_DETECTED", "SC", "AR", "ST", "SPRING", "SOS",
         "LPS", "MARKUP", "RE-ACCUMULATION", "INVALIDATED", "EXPIRED",
         "AMBIGUOUS")


# ---------------------------------------------------------------------------
# §6 Parameters (frozen in-package defaults, ISSUE-CP2-006 pattern)
# ---------------------------------------------------------------------------
E08_DEFAULTS: Dict[str, Any] = {
    "sc_vol_ratio": 2.5,        # SC VolRatio >= 2.5
    "sc_range_z": 2.0,          # SC RangeZ >= 2.0
    "sc_close_lo": 0.25,        # SC ClosePos ∈ [0.25, 0.6]
    "sc_close_hi": 0.6,
    "sc_body_ratio": 0.5,       # SC BodyRatio >= 0.5
    "ar_min_ratio": 0.5,        # AR Δ >= 0.5*ATR
    "ar_max_bars": 5,           # AR within <=5 candles
    "ar_close_pos": 0.6,        # AR ClosePos >= 0.6
    "st_tol_atr": 0.3,          # ST Low ∈ [Low_SC ± 0.3*ATR]
    "st_vol_ratio": 0.7,        # ST VolRatio <= 0.7
    "spring_pen_max": 0.3,      # Spring Pen ∈ (0, 0.3*ATR]
    "spring_vol_min": 1.3,      # Spring VolRatio >= 1.3
    "spring_evr_min": 0.5,      # (VolRatio>=1.3 OR EVR>0.5)
    "spring_bars": 3,           # recovery within <=3 candles
    "sos_vol_min": 1.2,         # SOS VolRatio >= 1.2
    "sos_close_pos": 0.65,      # SOS ClosePos >= 0.65
    "sos_atr_dist": 0.2,        # SOS Close > range_hi + 0.2*ATR
    "lps_vol_max": 0.7,         # LPS VolRatio <= 0.7
    "lps_atr_dist": 0.2,        # LPS Low >= range_lo + 0.2*ATR
    "ut_pen_max": 0.3,          # UT/UTAD Pen ∈ (0, 0.3*ATR]
    "ut_vol_min": 1.2,          # UT VolRatio >= 1.2
    "ut_close_pos": 0.4,        # UTAD ClosePos <= 0.4
    "range_min_bars": 12,       # §6 range_min_bars
    "range_atr_mult": 1.5,      # §4 detect_range High-Low < 1.5*ATR
    "entropy_threshold": 0.85,  # H >= 0.85 nat → AMBIGUOUS
    "evr_rho_threshold": 0.2,   # ρ < 0.2 → effort without result
    "cause_effect_k": 0.42,     # log-log OLS k
    "cause_effect_gamma": 0.71,  # log-log OLS γ
    "pf_box_mult": 0.5,         # P&F BoxSize = 0.5*ATR14
    "pf_reversal_rows": 3,      # P&F ReversalRows = 3 (classic)
    "max_age_bars": 96,         # EXPIRED if age > 96
    "atr_period": 14,           # Wilder ATR14
    "score_weights": (0.25, 0.25, 0.2, 0.15, 0.15),  # §4 w (Σ=1)
    "age_lambda": 0.02,         # score_age = exp(-λ·age)
    "dirichlet_alpha": 0.1,     # transition-matrix Dirichlet prior
    "invalid_atr_mult": 0.5,    # INVALIDATED if Close < SC_Low - 0.5*ATR
}


def get_params(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = dict(E08_DEFAULTS)
    for key, value in (overrides or {}).items():
        if key not in E08_DEFAULTS:
            raise ValueError(f"UNKNOWN_E08_PARAM_QX:{key}")
        params[key] = value
    weights = tuple(params["score_weights"])
    if abs(sum(weights) - 1.0) > 1e-9:
        raise ValueError("E08_SCORE_WEIGHTS_SUM_QX")
    params["score_weights"] = weights
    return params


# ---------------------------------------------------------------------------
# §4 core formula functions (PIT-safe; deterministic)
# ---------------------------------------------------------------------------
def rma(series: Sequence[float], n: int) -> float:
    """Wilder RMA (PIT-safe). NaN if len < n."""
    if len(series) < n:
        return float("nan")
    atr = sum(series[:n]) / n
    for x in series[n:]:
        atr = (atr * (n - 1) + x) / n
    return atr


def softmax(z: Sequence[float]) -> List[float]:
    m = max(z)
    e = [math.exp(v - m) for v in z]
    s = sum(e)
    return [v / s for v in e]


def entropy(p: Sequence[float]) -> float:
    return -sum(pi * math.log(pi) for pi in p if pi > 1e-12)


def detect_sc(bar: Dict[str, Any], vol_ratio: float, range_z: float,
              close_pos: float, body_ratio: float) -> bool:
    """§3.3 SC — selling climax (vol/range/close-position/body, bearish)."""
    return (vol_ratio >= 2.5 and range_z >= 2.0 and
            0.25 <= close_pos <= 0.6 and body_ratio >= 0.5 and
            bar["c"] < bar["o"])


def detect_spring(low: float, range_lo: float, close: float, atr: float,
                  vol_ratio: float, evr: float) -> bool:
    """§3.3 Spring — temporary penetration below range low, recover."""
    pen = range_lo - low
    return (0 < pen <= 0.3 * atr and close > range_lo and
            (vol_ratio >= 1.3 or evr > 0.5))


def detect_ut(high: float, range_hi: float, close: float, atr: float,
              vol_ratio: float) -> bool:
    """§3.3 UT/UTAD — temporary penetration above range high, fail to hold."""
    pen = high - range_hi
    return (0 < pen <= 0.3 * atr and close < range_hi and
            vol_ratio >= 1.2)


def detect_ar(high_ar: float, low_sc: float, atr: float, close_pos: float,
              ar_min_ratio: float = 0.5,
              ar_close_pos: float = 0.6) -> bool:
    """§3.3 AR — rally following SC: Δ >= 0.5·ATR ∧ ClosePos >= 0.6."""
    return (high_ar - low_sc) >= ar_min_ratio * atr and \
        close_pos >= ar_close_pos


def detect_st(low_st: float, low_sc: float, atr: float, vol_ratio: float,
              st_tol_atr: float = 0.3, st_vol_ratio: float = 0.7) -> bool:
    """§3.3 ST — retest of SC zone: Low ∈ [Low_SC ± 0.3·ATR] ∧ VR<=0.7 ∧
    no break of Low_SC."""
    return (abs(low_st - low_sc) <= st_tol_atr * atr and low_st >= low_sc and
            vol_ratio <= st_vol_ratio)


def detect_sos(bos_bullish_confirmed: bool, close: float, range_hi: float,
               atr: float, vol_ratio: float, close_pos: float,
               sos_vol_min: float = 1.2, sos_close_pos: float = 0.65,
               sos_atr_dist: float = 0.2) -> bool:
    """§3.3 SOS — BOS Bullish ∧ Close > range_hi+0.2·ATR ∧ VR>=1.2 ∧
    ClosePos>=0.65."""
    return (bos_bullish_confirmed and close > range_hi + sos_atr_dist * atr
            and vol_ratio >= sos_vol_min and close_pos >= sos_close_pos)


def detect_lps(high_lps: float, high_sos: float, low_lps: float,
               range_lo: float, atr: float, vol_ratio: float,
               lps_vol_max: float = 0.7,
               lps_atr_dist: float = 0.2) -> bool:
    """§3.3 LPS — low-volume pullback above range low, structure preserved."""
    return (high_lps < high_sos and low_lps >= range_lo + lps_atr_dist * atr
            and vol_ratio <= lps_vol_max)


def phase_probabilities(scores: Sequence[Sequence[float]],
                        w: Sequence[float],
                        phases: Sequence[str],
                        ) -> Tuple[Dict[str, float], float]:
    """§3.2 phase detection — softmax(Σ w_k score_k,i) + entropy."""
    I = len(phases)
    z = [sum(w[k] * scores[k][i] for k in range(len(w))) for i in range(I)]
    p = softmax(z)
    H = entropy(p)
    return {ph: pi for ph, pi in zip(phases, p)}, H


def cause_effect_target(range_cause: float, duration: int, k: float = 0.42,
                        gamma: float = 0.71,
                        breakout: float = 0.0) -> float:
    """§3.1 Cause & Effect (continuous) — Effect = breakout + k·D^γ·Range."""
    return breakout + k * (duration ** gamma) * range_cause


def pf_target(breakout: float, columns: int, box_size: float,
              reversal_rows: int = 3) -> float:
    """§3.1 Cause & Effect (P&F) — Target = P_breakout + Col·Box·RevRows."""
    return breakout + columns * box_size * reversal_rows


def evr_correlation(vols: Sequence[float],
                    abs_returns: Sequence[float]) -> float:
    """§3.1 Effort & Result ρ_{V,|ΔP|} (NaN if n < 10)."""
    n = len(vols)
    if n < 10:
        return float("nan")
    mv = sum(vols) / n
    mr = sum(abs_returns) / n
    cov = sum((v - mv) * (r - mr) for v, r in zip(vols, abs_returns)) / n
    sv = math.sqrt(sum((v - mv) ** 2 for v in vols) / n)
    sr = math.sqrt(sum((r - mr) ** 2 for r in abs_returns) / n)
    return cov / max(sv * sr, EPS)


def detect_range(bars: Sequence[Dict[str, Any]], atr: float,
                 min_bars: int = 12,
                 atr_mult: float = 1.5) -> Optional[Tuple[float, float]]:
    """§4 detect_range — High-Low < 1.5·ATR over min_bars candles."""
    if len(bars) < min_bars:
        return None
    lo = min(b["l"] for b in bars[-min_bars:])
    hi = max(b["h"] for b in bars[-min_bars:])
    if (hi - lo) < atr_mult * atr:
        return (lo, hi)
    return None


def transition_matrix(n_obs: Optional[Sequence[Sequence[int]]] = None,
                      alpha: float = 0.1) -> List[List[float]]:
    """§3.2 Dirichlet-smoothed transition matrix T_ij = (N_ij+α)/(N_i+Kα).
    With no observed counts (no fabricated dataset), every row is the
    uniform Dirichlet prior 1/K."""
    K = N_PHASES
    if n_obs is None:
        return [[1.0 / K] * K for _ in range(K)]
    out: List[List[float]] = []
    for row in n_obs:
        n_i = sum(row)
        out.append([(n_ij + alpha) / (n_i + K * alpha) for n_ij in row])
    return out


def brier_score(probs: Sequence[float], outcomes: Sequence[int]) -> float:
    """§7 Ch.1 Brier score BS = 1/N Σ (p_i - o_i)^2."""
    n = len(outcomes)
    if n == 0:
        return 0.0
    return sum((p - o) ** 2 for p, o in zip(probs, outcomes)) / n


def wilson_ci(p_hat: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    denom = 1 + z * z / n
    centre = (p_hat + z * z / (2 * n)) / denom
    half = z * math.sqrt((p_hat * (1 - p_hat) / n + z * z / (4 * n * n))) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


# ---------------------------------------------------------------------------
# §3.2 phase score components (normalized sigmoids / gated scores)
# ---------------------------------------------------------------------------
def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def score_position(close: float, range_lo: float, range_hi: float) -> float:
    """score_position = sigmoid((Close-RangeLow)/(RangeHigh-RangeLow) - 0.5)*2
    (the §3.2 accumulation-position score)."""
    if range_hi <= range_lo:
        return 0.0
    return _sigmoid((close - range_lo) / (range_hi - range_lo) - 0.5) * 2.0


def score_evr(evr: float) -> float:
    return _sigmoid(evr)


def score_volume(vol_ratio: float) -> float:
    """score_volume = 1 - min(VolRatio/2, 1) (ST/LPS low-volume preference)."""
    return 1.0 - min(vol_ratio / 2.0, 1.0)


def score_structure(structure: str, phase: str) -> float:
    """score_structure = 1 if BULL structure and ACCUM/MARKUP phase."""
    bull = structure == "BULL"
    accum_family = phase in ("ACCUMULATION", "MARKUP", "RE-ACCUMULATION")
    bear = structure == "BEAR"
    dist_family = phase in ("DISTRIBUTION", "MARKDOWN", "RE-DISTRIBUTION")
    if bull and accum_family:
        return 1.0
    if bear and dist_family:
        return 1.0
    return 0.0


def score_age(age: float, lam: float = 0.02) -> float:
    return math.exp(-lam * age)


# ---------------------------------------------------------------------------
# §4 Wyckoff engine (streaming)
# ---------------------------------------------------------------------------
@dataclass
class CycleState:
    phase_hypotheses: Dict[str, float]
    entropy: float
    fate: str
    range_lo: Optional[float] = None
    range_hi: Optional[float] = None
    age_bars: int = 0
    atr: float = 0.0
    confirmed_events: List[Dict[str, Any]] = field(default_factory=list)
    snapshot_id: str = ""
    quality: str = "Q0_INVALID"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "range": {"lo": self.range_lo, "hi": self.range_hi,
                      "age_bars": self.age_bars, "atr": self.atr},
            "phase_hypotheses": self.phase_hypotheses,
            "entropy": self.entropy,
            "confirmed_events": self.confirmed_events,
            "fate": self.fate,
            "snapshot_id": self.snapshot_id,
            "quality": self.quality,
        }


class WyckoffEngineV4:
    """§4 WyckoffEngineV4 — streaming, idempotent per (bar_ts, range)."""

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        self.params = get_params(params)
        self.range_lo: Optional[float] = None
        self.range_hi: Optional[float] = None
        self.range_age = 0
        self.atr = 0.0
        self.sc_low: Optional[float] = None
        self.sc_bar: Optional[Dict[str, Any]] = None
        self.sos_high: Optional[float] = None
        self.events: List[Dict[str, Any]] = []
        self.phases_history: List[Dict[str, Any]] = []
        self._idem: Dict[str, str] = {}

    def _canonical_state(self, bar: Dict[str, Any], probs: Dict[str, float],
                         H: float, fate: str, sc: bool) -> Dict[str, Any]:
        return {"input": bar, "state": {"phase_hypotheses": probs,
                                        "entropy": H, "fate": fate,
                                        "sc": sc}}

    def _snapshot_id(self, bar: Dict[str, Any], probs: Dict[str, float],
                     H: float, fate: str, sc: bool) -> str:
        return canonical_snapshot_id(
            ENGINE, CONTRACT_VERSION,
            self._canonical_state(bar, probs, H, fate, sc))

    def process_bar(self, bar: Dict[str, Any], atr: float, vol_ratio: float,
                    close_pos: float, evr: float,
                    bos_event: Optional[Dict[str, Any]],
                    structure: str = "BULL") -> Dict[str, Any]:
        # Edge cases (§1/§4)
        if bar["h"] < bar["l"]:
            return {"fate": "Q0_INVALID", "reason": "H<L"}
        if atr < EPS:
            return {"fate": "Q0_INVALID", "reason": "ATR=0"}
        self.atr = atr
        # Streaming range tracking (running lo/hi + age)
        if self.range_lo is None:
            self.range_lo = bar["l"]
            self.range_hi = bar["h"]
            self.range_age = 1
        else:
            self.range_lo = min(self.range_lo, bar["l"])
            self.range_hi = max(self.range_hi, bar["h"])
            self.range_age += 1
        range_z = (bar["h"] - bar["l"]) / max(atr, EPS)
        body_ratio = abs(bar["c"] - bar["o"]) / max(bar["h"] - bar["l"], EPS)
        # Event detection (6-parameter contract)
        sc = detect_sc(bar, vol_ratio, range_z, close_pos, body_ratio)
        spring = detect_spring(bar["l"], self.range_lo, bar["c"], atr,
                               vol_ratio, evr)
        ut = detect_ut(bar["h"], self.range_hi, bar["c"], atr, vol_ratio)
        bos_bull = bool(bos_event and bos_event.get("kind") == "BOS" and
                        bos_event.get("direction") == "UP")
        sos = detect_sos(bos_bull, bar["c"], self.range_hi, atr, vol_ratio,
                         close_pos, self.params["sos_vol_min"],
                         self.params["sos_close_pos"],
                         self.params["sos_atr_dist"])
        if sc and self.sc_low is None:
            self.sc_low = bar["l"]
            self.sc_bar = bar
            self.events.append({"kind": "SC", "ts": bar.get("ts_close", 0),
                                "price": bar["c"], "vol_ratio": vol_ratio})
        if sos and self.sos_high is None:
            self.sos_high = bar["h"]
            self.events.append({"kind": "SOS", "ts": bar.get("ts_close", 0),
                                "price": bar["c"], "vol_ratio": vol_ratio})
        # Phase probabilities (governed score computation)
        phases = list(PHASES)
        w = list(self.params["score_weights"])
        sp = score_position(bar["c"], self.range_lo, self.range_hi)
        se = score_evr(evr)
        sv = score_volume(vol_ratio)
        age = float(self.range_age)
        scores = _phase_scores(sp, se, sv, structure, age, self.params)
        probs, H = phase_probabilities(scores, w, phases)
        fate = "AMBIGUOUS" if H >= self.params["entropy_threshold"] else \
            "ACTIVE"
        # INVALIDATED / EXPIRED
        if self.sc_low is not None and \
                bar["c"] < self.sc_low - self.params["invalid_atr_mult"] * atr:
            fate = "INVALIDATED"
        if self.range_age > self.params["max_age_bars"]:
            fate = "EXPIRED"
        snap_id = self._snapshot_id(bar, probs, H, fate, sc)
        quality = self._quality(H, sc, bos_bull, vol_ratio, probs)
        return {
            "phase_hypotheses": probs, "entropy": H, "fate": fate,
            "snapshot_id": snap_id, "sc": sc, "spring": spring, "ut": ut,
            "sos": sos, "quality": quality, "range": {
                "lo": self.range_lo, "hi": self.range_hi,
                "age_bars": self.range_age, "atr": atr},
        }

    def _quality(self, H: float, sc: bool, bos: bool, vol_ratio: float,
                 probs: Dict[str, float]) -> str:
        if self.sc_bar is None and not bos:
            return "Q1_RAW"
        if self.sc_bar is not None:
            if H < self.params["entropy_threshold"]:
                return "Q4_STATISTICAL"
            return "Q3_VOLUME_CONFIRMED"
        return "Q2_STRUCTURAL"


def _phase_scores(sp: float, se: float, sv: float, structure: str,
                  age: float, params: Dict[str, Any]) -> List[List[float]]:
    """Build the K×8 score matrix (§3.2). 5 components: position, evr,
    volume, structure, age — each scored per phase."""
    sa = score_age(age, params["age_lambda"])
    rows: List[List[float]] = []
    # position row: accumulation-family phases favor high position score;
    # distribution-family favor low (mirror).
    rows.append([sp if ph in ("ACCUMULATION", "RE-ACCUMULATION", "MARKUP")
                 else 1.0 - sp for ph in PHASES])
    rows.append([se if ph in ("ACCUMULATION", "RE-ACCUMULATION", "MARKUP")
                 else 1.0 - se for ph in PHASES])
    rows.append([sv if ph in ("DISTRIBUTION", "RE-DISTRIBUTION", "MARKDOWN")
                 else sv for ph in PHASES])
    rows.append([score_structure(structure, ph) for ph in PHASES])
    rows.append([sa] * N_PHASES)
    return rows


def run_engine(bars: Sequence[Dict[str, Any]],
               params: Optional[Dict[str, Any]] = None,
               atr_series: Optional[Sequence[float]] = None,
               vol_ratios: Optional[Sequence[float]] = None,
               structure_events: Optional[Sequence[Dict[str, Any]]] = None,
               symbol: str = "",
               timeframe: str = "6h",
               ) -> Dict[str, Any]:
    """Batch driver over a closed-candle window."""
    p = get_params(params)
    eng = WyckoffEngineV4(p)
    results: List[Dict[str, Any]] = []
    struct_by_idx: Dict[int, Dict[str, Any]] = {
        int(e.get("valid_at_idx", e.get("idx", 0))): e
        for e in (structure_events or [])}
    for i, bar in enumerate(bars):
        atr = float(atr_series[i]) if atr_series is not None and \
            i < len(atr_series) else _atr_local(bars, i, p["atr_period"])
        vr = float(vol_ratios[i]) if vol_ratios is not None and \
            i < len(vol_ratios) else _vol_ratio_local(bars, i)
        evr = _evr_local(bars, i)
        close_pos = (bar["c"] - bar["l"]) / max(bar["h"] - bar["l"], EPS)
        bos = struct_by_idx.get(i)
        results.append(eng.process_bar(bar, atr, vr, close_pos, evr, bos))
    last = results[-1] if results else {}
    return {
        "engine": ENGINE,
        "results": results,
        "cycle_state": last,
        "events": eng.events,
        "phases_history": eng.phases_history,
    }


def _tr(bar: Dict[str, Any], prev_close: float) -> float:
    return max(bar["h"] - bar["l"], abs(bar["h"] - prev_close),
               abs(bar["l"] - prev_close))


def _atr_local(bars: Sequence[Dict[str, Any]], idx: int, n: int) -> float:
    if idx < 1:
        return bars[idx]["h"] - bars[idx]["l"]
    trs = []
    for j in range(1, idx + 1):
        if bars[j]["h"] < bars[j]["l"]:
            continue
        trs.append(_tr(bars[j], bars[j - 1]["c"]))
    if not trs:
        return 0.0
    return rma(trs, n) if len(trs) >= n else (sum(trs) / len(trs))


def _vol_ratio_local(bars: Sequence[Dict[str, Any]], idx: int,
                     lookback: int = 20) -> float:
    if idx < 1:
        return 1.0
    vols = [b.get("v", 0) for b in bars[max(0, idx - lookback):idx]]
    if not vols:
        return 1.0
    sma = sum(vols) / len(vols)
    return bars[idx].get("v", 0) / max(sma, EPS)


def _evr_local(bars: Sequence[Dict[str, Any]], idx: int,
               lookback: int = 20) -> float:
    if idx < 1:
        return 0.0
    seg = bars[max(0, idx - lookback):idx + 1]
    vols = [b.get("v", 0) for b in seg]
    ranges = [b["h"] - b["l"] for b in seg]
    vz = _zscore(bars[idx].get("v", 0), vols)
    rz = _zscore(bars[idx]["h"] - bars[idx]["l"], ranges)
    sign = 1.0 if bars[idx]["c"] >= bars[idx - 1]["c"] else -1.0
    return vz * rz * sign


def _zscore(x: float, series: Sequence[float]) -> float:
    if len(series) < 2:
        return 0.0
    m = sum(series) / len(series)
    sd = math.sqrt(sum((v - m) ** 2 for v in series) / len(series))
    return (x - m) / max(sd, EPS)


# ---------------------------------------------------------------------------
# Encyclopedia accessor — chapter 1 complete; chapters 2–4 Wave-Out
# ---------------------------------------------------------------------------
_ENCYCLOPEDIA_CH1 = {
    "chapter": 1,
    "title": "Historical Foundation",
    "definition": ("The Wyckoff method traces to Tape Reading, 1910.",
                   "Phase detection via the softmax + entropy framework."),
    "history": ("Wyckoff's 1910 Tape Reading; the 1931 Method; Pruden's "
                "2007 Three Skills; Villahermosa's 2021 Wyckoff 2.0; "
                "integration with Volume Profile."),
    "mechanics": ("The cause/effect cycle; accumulation as absorption."),
    "institutional_read": ("The 'Composite Man' is a hypothesis, not an "
                           "established fact; TWAP/VWAP execution is the "
                           "practical analogue."),
    "retail_read": "Post-hoc labeling; false Springs mistaken from noise.",
    "mtf": "The HTF phase is decisive; HTF DISTRIBUTION + LTF ACCUMULATION ⇒ caution.",
    "entry": "Only SOS/LPS following SC/Spring, with Structure BOS confirmation.",
    "risk": "Late confirmation; high entropy ⇒ abstention; stop 0.5·ATR below Spring.",
    "failure_modes": ["entropy>=0.85 ⇒ AMBIGUOUS", "event from noise (VolRatio<1.0)"],
    "statistics": "Brier score BS = 1/N Σ (p_i - o_i)^2; target BS<0.22.",
    "applications": ("Input to Regime (ACCUMULATION@0.7 ⇒ RANGE) and to "
                     "Setup."),
}


def encyclopedia_chapter(chapter: int) -> Dict[str, Any]:
    """§7 encyclopedia accessor. Chapter 1 (Historical Foundation) is the
    complete normative reference; chapters 2–4 are deferred non-normative
    in the source and are Wave-Out — raise, never stub (§9.5-9 / G6)."""
    if chapter == 1:
        return dict(_ENCYCLOPEDIA_CH1)
    if chapter in (2, 3, 4):
        raise wave_out("e08_encyclopedia_ch2_4",
                       f"e08_encyclopedia_ch{chapter}_deferred_non_normative")
    raise ValueError(f"UNKNOWN_E08_ENCYCLOPEDIA_CHAPTER_QX:{chapter}")


# --------------------------------------------------------------------------
# EngineBase binding (frozen CP-1 contract; consumed, never patched)
# --------------------------------------------------------------------------
def observation_to_bar(obs: MarketObservation) -> Dict[str, Any]:
    ts = obs.timestamp
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        ts_ms = int(dt.timestamp() * 1000)
    except (ValueError, AttributeError):
        ts_ms = 0
    return {"o": float(obs.open), "h": float(obs.high),
            "l": float(obs.low), "c": float(obs.close),
            "v": float(obs.volume), "ts_close": ts_ms,
            "symbol": obs.symbol}


class E08WyckoffEngine(EngineBase):
    """E08_Wyckoff on the frozen EngineBase contract (v4.0.0).

    compute(symbol, timeframe, as_of, context): window via context['window']
    or a sync WindowProvider. Consumed context keys: window, provider, bars,
    e08_params, atr_series (E04-governed ATR), vol_ratios (E03-governed),
    structure_events (E01 BOS/CHoCH), regime (E11 — optional, event-driven;
    absent → degraded, MARKUP/MARKDOWN validity not asserted). Produces
    phase-hypothesis evidence on topics evidence.E08.* .
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
        bars = [observation_to_bar(o) for o in window_obs]
        params = get_params(context.get("e08_params"))
        result = run_engine(
            bars, params,
            atr_series=context.get("atr_series"),
            vol_ratios=context.get("vol_ratios"),
            structure_events=context.get("structure_events"),
            symbol=symbol, timeframe=timeframe)
        quality = self._window_quality(window_obs)
        out: List[EvidenceEvent] = []
        for i, res in enumerate(result["results"]):
            out.append(self._to_evidence(res, symbol, timeframe, quality,
                                         bars, i))
        return out

    def _resolve_window(self, symbol: str, timeframe: str, as_of: str,
                        context: Dict[str, Any]) -> List[MarketObservation]:
        window = context.get("window")
        if window is not None:
            return list(window)
        provider = context.get("provider")
        if provider is None:
            raise ValueError("MISSING_WINDOW_CONTEXT_QX")
        import inspect
        bars = context.get("bars", 300)
        result = provider.get_window(symbol, timeframe, as_of, bars)
        if inspect.isawaitable(result):
            try:
                __import__("asyncio").get_running_loop()
            except RuntimeError:
                return list(__import__("asyncio").run(result))
            raise ValueError(
                "MISSING_WINDOW_CONTEXT_QX (async provider inside a running "
                "loop — pass context['window'])")
        return list(result)

    @staticmethod
    def _window_quality(window_obs: Sequence[MarketObservation]) -> float:
        if not window_obs:
            return 0.0
        comps = [float(o.completeness_pct or 0) / 100.0 for o in window_obs]
        return min(1.0, sum(comps) / len(comps))

    def _to_evidence(self, res: Dict[str, Any], symbol: str, timeframe: str,
                     quality: float, bars: Sequence[Dict[str, Any]],
                     idx: int) -> EvidenceEvent:
        probs = res.get("phase_hypotheses", {})
        if not probs:
            return self._empty_evidence(symbol, timeframe, quality, idx)
        top_phase = max(probs, key=lambda k: probs[k])
        ts_ms = bars[idx].get("ts_close", 0)
        as_of_iso = datetime.fromtimestamp(
            ts_ms / 1000.0, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.") + f"{ts_ms % 1000:03d}Z"
        ent = float(res.get("entropy", 0.0))
        fate = res.get("fate", "ACTIVE")
        qtag = res.get("quality", "Q1_RAW")
        resolution = qtag.split("_", 1)[0] if qtag.startswith("Q") else "Q0"
        if resolution not in ("Q0", "Q1", "Q2", "Q3", "Q4", "Q5"):
            resolution = "Q0"
        direction = 1 if top_phase in ("ACCUMULATION", "MARKUP",
                                       "RE-ACCUMULATION") else (
            -1 if top_phase in ("DISTRIBUTION", "MARKDOWN",
                                "RE-DISTRIBUTION") else 0)
        return EvidenceEvent(
            evidence_id=uuid_v7(),
            engine_id=self.engine_id,
            analyst_version=self.analyst_version,
            symbol=symbol, timeframe=timeframe,
            snapshot_id=res.get("snapshot_id", ""),
            event_time=as_of_iso,
            availability_time=as_of_iso,
            observation_window={"bar_idx": idx, "tf": timeframe},
            feature_snapshot_id=res.get("snapshot_id", ""),
            feature_dependencies=("window", "atr_series", "vol_ratios",
                                  "structure_events"),
            condition_state=f"EV_WYK_PHASE_{top_phase}_{fate}",
            direction=direction,
            strength=float(min(max(probs.get(top_phase, 0.0), 0.0), 1.0)),
            confidence=float(1.0 - min(ent / math.log(N_PHASES), 1.0)),
            quality=float(quality),
            validity="VALID" if fate in ("ACTIVE", "AMBIGUOUS") else
            "DEGRADED",
            fate_state=LifecycleState.ACTIVE,
            age=None,
            decay=None,
            explanation=(f"E08 phase {top_phase} p={probs.get(top_phase, 0):.4f} "
                         f"H={ent:.4f} fate={fate} {qtag}"),
            parameter_version="E08-WYCKOFF-V4.0.0/DEFAULTS-v1",
            lineage=(f"bar_{idx}",),
            resolution_class=resolution,
        )

    def _empty_evidence(self, symbol: str, timeframe: str, quality: float,
                        idx: int) -> EvidenceEvent:
        return EvidenceEvent(
            evidence_id=uuid_v7(),
            engine_id=self.engine_id,
            analyst_version=self.analyst_version,
            symbol=symbol, timeframe=timeframe,
            snapshot_id=canonical_snapshot_id(ENGINE, CONTRACT_VERSION,
                                              {"empty": idx}),
            event_time="1970-01-01T00:00:00.000Z",
            availability_time="1970-01-01T00:00:00.000Z",
            observation_window={"bar_idx": idx, "tf": timeframe},
            feature_snapshot_id="",
            feature_dependencies=("window",),
            condition_state="EV_WYK_NO_HYPOTHESIS",
            direction=0,
            strength=0.0,
            confidence=0.0,
            quality=float(quality),
            validity="DEGRADED",
            fate_state=LifecycleState.CANDIDATE,
            age=None,
            decay=None,
            explanation="E08 no phase hypothesis (insufficient history)",
            parameter_version="E08-WYCKOFF-V4.0.0/DEFAULTS-v1",
            lineage=(f"bar_{idx}",),
            resolution_class="Q0",
        )
