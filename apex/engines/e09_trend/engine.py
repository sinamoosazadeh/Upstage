"""APEX_GEN5 — E09 Trend (v4.0.0).

Blueprint: APEX_GEN5.md L9467–10275 (chapter order mirrored: §1 mission →
§2 vocabulary → §3 math/corrections/edge cases → §4 algorithms →
§5 objects/state/events/schema → §6 parameters → §7 encyclopedic → §8
validation).

Trend is a multi-scale entity: MICRO(5) / SHORT(20) / INTER(60) / MACRO(240),
each carrying a full state vector, combined into a ``TrendStack`` with the
fixed, governed weights ``[0.1, 0.2, 0.3, 0.4]`` (§3.6). This engine is
descriptive only: it issues no buy/sell signal and no position sizing (§1.4).

**AD-line (§3.5, full Wilder):** ``compute_adx_wilder`` returns the complete
``DI+ / DI− / DX / ADX`` line — TR, +DM, −DM, Wilder smoothing of all three,
DI±, DX and the RMA-smoothed ADX — with every documented edge case
(``H<L`` dropped, ``V=0`` low quality, ``TR_smooth=0 ⇒ DI=DX=0``, gap >
2× timeframe ⇒ ``continuity_break``, warm-up until ``t ≥ 2n``).

**Multi-TF (§3.6/§5.2/§7-7/§9.5-14):** the TrendStack is built from the four
scales; HTF input is consumed last-closed only, and the alignment label
(ALIGNED_BULL / ALIGNED_BEAR / CONFLICTING / SIDEWAYS / TRANSITIONING) follows
the governed Bias thresholds.

Degradation paths (P19 — sibling contracts not built at CP-4):
  * E10_Momentum (divergence) absent ⇒ ``MOMENTUM_UNAVAILABLE_DEGRADED_QX``:
    no exhaustion/divergence claim is fabricated.
  * E01 swing points absent ⇒ ``seq_score = 0`` (neutral, §3.1) with
    ``evidence_count = 0`` and a DEGRADED validity — never invented swings.
  * OI (``§1.3`` honest-label contract) MISSING ⇒ explicit event + graceful
    degradation; OI-derived values are never fabricated.

Logged contradictions (PHASE2_DECISION_LOG §B/CP-4):
  ISSUE-CP4-015 (§4 ADX returns unbound DI when ``dx_list`` empty) → canonical
                Wilder seeding.
  ISSUE-CP4-016 (§3.8 ``min(H,1.2)``/``else 1.0 if H>1.2`` vs §4 clip) → §4.
  ISSUE-CP4-017 (§8.4 "correlation > 0.85" vs §8.6 "> 0.9 … threshold 0.85")
                → 0.85 governed threshold.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from apex.data_catalog.contracts import (
    EvidenceEvent,
    LifecycleState,
    MarketObservation,
)
from apex.engines.base import EngineBase
from apex.identity.snapshot import canonical_snapshot_id
from apex.identity.uuid_v7 import uuid_v7
from apex.quality.numerical import eps_for_engine

# ---------------------------------------------------------------------------
# Chapter identity
# ---------------------------------------------------------------------------

ENGINE = "E09_Trend"
CONTRACT_VERSION = "4.0.0"
CONTRACT_LABEL = "E09_Trend.Contract v4.0.0"
ANALYST_VERSION = "4.0.0+" + "0" * 40
EPS = float(eps_for_engine("E09"))            # 1e-12 (§4 / frozen §2.2 row)
PIT_LAG = 1                                   # §5.1 ``pit_lag`` const

SCALES = ("MICRO", "SHORT", "INTER", "MACRO")
W_STACK_CORRECTED = {"MICRO": 0.1, "SHORT": 0.2, "INTER": 0.3, "MACRO": 0.4}
ALIGNMENTS = ("ALIGNED_BULL", "ALIGNED_BEAR", "CONFLICTING", "SIDEWAYS",
              "TRANSITIONING")
QUALITY_LABELS = ("Q0", "Q1", "Q2", "Q3", "Q4", "Q5")
QUALITY_NAMES = {"Q0": "FAIL", "Q1": "WEAK", "Q2": "MODERATE", "Q3": "STRONG",
                 "Q4": "VERY_STRONG", "Q5": "EXCEPTIONAL"}
SCALE_STATES = ("UNKNOWN", "CALCULATING", "VALID", "DEGRADED", "INVALID")
# §1.3 honest-label data availability states.
OI_STATES = ("AVAILABLE", "STALE", "MISSING", "INVALID", "DEGRADED")

MOMENTUM_UNAVAILABLE_REASON = "MOMENTUM_UNAVAILABLE_DEGRADED_QX"
SWINGS_UNAVAILABLE_REASON = "SWINGS_UNAVAILABLE_DEGRADED_QX"
OI_MISSING_REASON = "OI_MISSING_DEGRADED_QX"

TREND_SCALE_REQUIRED = ("scale", "direction", "strength", "quality",
                        "quality_label", "seq_score", "slope_z", "pos", "r2",
                        "adx", "di_plus", "di_minus", "hurst", "mk_z",
                        "evidence_count", "as_of", "snapshot_id",
                        "contract_version")
TREND_STACK_REQUIRED = ("stack", "bias", "alignment", "quality_agg",
                        "snapshot_id", "as_of")

EVENT_CATALOG: Dict[str, Dict[str, str]] = {
    "EV_TRD_001": {"name": "Trend_Initiated",
                   "trigger": "prev dir 0, curr !=0, AND BOS AND slope_z>=th_s "
                              "AND pos>=th_p AND |mk_z|>=crit"},
    "EV_TRD_002": {"name": "Trend_Continued", "trigger": "–"},
    "EV_TRD_003": {"name": "Trend_Exhausted",
                   "trigger": "Divergence present + strength drop >0.2"},
    "EV_TRD_004": {"name": "Trend_Transition",
                   "trigger": "CHoCH + slope sign flip + MK sign flip"},
    "EV_TRD_005": {"name": "Stack_Aligned",
                   "trigger": "all directions the same, |Bias|>=0.7"},
    "EV_TRD_006": {"name": "Stack_Conflicting",
                   "trigger": ">=1 scale opposite to MACRO direction"},
    "EV_TRD_007": {"name": "Sideways_Detected",
                   "trigger": "|H-0.5|<0.1 and ADX<20 and R2<0.3"},
    "EV_TRD_008": {"name": "Quality_Degraded",
                   "trigger": "Q drops >=2 levels within 3 bars"},
}


# ---------------------------------------------------------------------------
# §6 Parameters (defaults verbatim from the chapter table)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EngineParams:
    """E09 governed parameter set (§6 table, defaults verbatim)."""

    window_micro: int = 5
    window_short: int = 20
    window_inter: int = 60
    window_macro: int = 240
    w_a: float = 0.4                      # seq_score weight
    w_b: float = 0.35                     # slope_z weight
    w_c: float = 0.25                     # pos weight
    slope_z_threshold: float = 1.5        # θ_s
    pos_threshold: float = 0.3            # θ_p
    strength_threshold: float = 0.5       # θ_str
    direction_deadband: float = 0.05      # §4 dir cut (±0.05)
    adx_n: int = 14                       # Wilder standard
    mk_crit_z: float = 1.96
    hurst_window: int = 128
    hurst_min_len: int = 8
    transition_confirm_bars: int = 2
    divergence_delta: float = 0.1
    divergence_lookback: int = 20
    divergence_score: float = 0.8
    divergence_min_peak_distance: int = 5   # §7 Ch.3-10
    r2_min_for_q: float = 0.2
    adx_min_for_trend: float = 15.0
    adx_valid_min: float = 10.0           # §5.3 VALID gate
    adx_sideways_max: float = 20.0        # §5.4 EV_TRD_007
    r2_sideways_max: float = 0.3          # §5.4 EV_TRD_007
    hurst_sideways_band: float = 0.1      # |H-0.5| < 0.1
    quality_drop_levels: int = 2          # §5.4 EV_TRD_008
    quality_drop_window: int = 3
    evidence_min: int = 2                 # §5.3 VALID gate
    continuity_gap_mult: float = 2.0      # §3.5 gap > 2× timeframe
    swing_dedup_bars: int = 2             # §3.1 duplicate swing distance
    stack_aligned_bias: float = 0.7       # §5.4 EV_TRD_005
    bias_bull: float = 0.5                # §3.6 aligned thresholds
    bias_bear: float = -0.5
    bias_sideways: float = 0.3
    redundancy_corr_th: float = 0.85      # §8.6 (ISSUE-CP4-017)
    hurst_clip_max: float = 1.2           # §3.8


E09_DEFAULTS: Dict[str, Any] = {
    f.name: f.default for f in EngineParams.__dataclass_fields__.values()}


def get_params(overrides: Optional[Dict[str, Any]] = None) -> EngineParams:
    """Build a parameter set; unknown keys are rejected (fail-closed)."""
    overrides = dict(overrides or {})
    unknown = sorted(set(overrides) - set(E09_DEFAULTS))
    if unknown:
        raise ValueError(f"UNKNOWN_E09_PARAM_QX: {unknown}")
    return EngineParams(**{**E09_DEFAULTS, **overrides})


def scale_windows(params: Optional[EngineParams] = None) -> Dict[str, int]:
    """The four governed scale windows (§6)."""
    p = params or EngineParams()
    return {"MICRO": p.window_micro, "SHORT": p.window_short,
            "INTER": p.window_inter, "MACRO": p.window_macro}


# ---------------------------------------------------------------------------
# §3.1 seq_score · §4 bar validation
# ---------------------------------------------------------------------------


def validate_bar(bar: Dict[str, Any], eps: float = EPS) -> bool:
    """§4/§8.1 FIX_11: ``H < L`` or any non-positive OHLC ⇒ invalid bar."""
    if bar["h"] < bar["l"] - eps:
        return False
    if (bar["c"] <= 0 or bar["h"] <= 0 or bar["l"] <= 0 or bar["o"] <= 0):
        return False
    return True


def dedup_swings(swings: Sequence[Dict[str, Any]],
                 min_distance: int = 2) -> List[Dict[str, Any]]:
    """§3.1 edge case: a duplicate swing at distance < 2 candles is dropped."""
    out: List[Dict[str, Any]] = []
    for s in sorted(swings, key=lambda x: (int(x["idx"]), str(x["type"]))):
        if out and abs(int(s["idx"]) - int(out[-1]["idx"])) < min_distance \
                and s["type"] == out[-1]["type"]:
            continue
        out.append(dict(s))
    return out


def compute_seq_score(swings: Sequence[Dict[str, Any]], window: int,
                      current_idx: int, strict_pit: bool = True
                      ) -> Tuple[float, int]:
    """§3.1 ``seq_score_s = ((N_HH+N_HL) − (N_LH+N_LL)) / N_total``.

    PIT: only swings with ``confirmed_at_idx <= current_idx − 1`` count.
    ``strict_pit=True`` (default) raises on a violation — §8.3: "Violating
    ``confirmed_at_idx <= current_idx-1`` raises an exception".
    ``N_total = 0`` ⇒ 0.0 (neutral).
    """
    if swings is None:
        # E01 absent: no swing evidence is *not* zero evidence in disguise —
        # the caller reports SWINGS_UNAVAILABLE_REASON.
        return 0.0, 0
    relevant: List[Dict[str, Any]] = []
    for s in swings:
        confirmed = int(s.get("confirmed_at_idx", -1))
        if confirmed > current_idx - 1:
            if strict_pit:
                raise ValueError(
                    f"PIT_SWING_VIOLATION_QX: swing {s.get('type')} at idx "
                    f"{s.get('idx')} confirmed_at_idx={confirmed} > "
                    f"{current_idx - 1}")
            continue
        if int(s["idx"]) >= current_idx - window:
            relevant.append(s)
    if not relevant:
        return 0.0, 0
    counts = {t: sum(1 for s in relevant if s["type"] == t)
              for t in ("HH", "HL", "LH", "LL", "EQ")}
    total = sum(counts.values())
    if total == 0:
        return 0.0, 0
    score = (counts["HH"] + counts["HL"] - counts["LH"] - counts["LL"]) / total
    return max(-1.0, min(1.0, score)), total


# ---------------------------------------------------------------------------
# §3.2 OLS with Newey-West HAC
# ---------------------------------------------------------------------------


def ols_slope_newey_west(ts: Sequence[float], ys: Sequence[float],
                         lag_auto: bool = True, eps: float = EPS
                         ) -> Tuple[float, float, float]:
    """§3.2 OLS slope + Newey-West HAC SE + R².

    ``Var_NW(β) = Ω / (Σ(t−t̄)²)²`` with Bartlett weights ``w_l = 1 − l/(L+1)``
    and automatic lag ``L = max(1, floor(4(n/100)^{2/9}))``.
    Edge cases: ``n < 3`` ⇒ (0, inf, 0); ``Var(t) ≈ 0`` ⇒ (0, inf, 0).
    """
    n = len(ys)
    if n < 3 or n != len(ts):
        return 0.0, float("inf"), 0.0
    mx = sum(ts) / n
    my = sum(ys) / n
    cov = sum((t - mx) * (y - my) for t, y in zip(ts, ys))
    var_t = sum((t - mx) ** 2 for t in ts)
    if var_t < eps:
        return 0.0, float("inf"), 0.0
    beta = cov / var_t
    resid = [y - (my + beta * (t - mx)) for t, y in zip(ts, ys)]
    sst = sum((y - my) ** 2 for y in ys)
    ssr = sum(r * r for r in resid)
    r2 = 0.0 if sst < eps else max(0.0, 1 - ssr / max(sst, eps))
    L = 1
    if lag_auto:
        L = max(1, int(4 * (n / 100) ** (2 / 9)))
        L = min(L, n - 1)
    xt = [t - mx for t in ts]
    omega = sum((resid[i] ** 2) * (xt[i] ** 2) for i in range(n))
    for l in range(1, L + 1):
        w = 1 - l / (L + 1)
        gamma = sum(resid[i] * resid[i - l] * xt[i] * xt[i - l]
                    for i in range(l, n))
        omega += 2 * w * gamma
    var_beta = omega / max(var_t ** 2, eps)
    se = math.sqrt(max(var_beta, eps))
    return beta, se, r2


def newey_west_lag(n: int) -> int:
    """§3.2 automatic lag ``L = max(1, floor(4(n/100)^{2/9}))``."""
    return max(1, int(4 * (n / 100) ** (2 / 9)))


# ---------------------------------------------------------------------------
# §3.3 Mann-Kendall with full tie correction
# ---------------------------------------------------------------------------


def mann_kendall_with_tie_correction(x: Sequence[float], tie_eps: float = 1e-12
                                     ) -> Tuple[float, float, float]:
    """§3.3 ``S``, tie-corrected ``Var(S)`` and the continuity-corrected ``z``.

    ``Var(S) = [n(n−1)(2n+5) − Σ_p t_p(t_p−1)(2t_p+5)]/18``;
    ``z = (S−1)/√Var`` if ``S>0``, ``0`` if ``S=0``, ``(S+1)/√Var`` if ``S<0``.
    ``n < 3`` ⇒ (0, 1, 0); ``Var = 0`` (all equal) ⇒ z = 0.
    """
    n = len(x)
    if n < 3:
        return 0.0, 1.0, 0.0
    S = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            if x[j] > x[i] + tie_eps:
                S += 1
            elif x[j] < x[i] - tie_eps:
                S -= 1
    sorted_x = sorted(x)
    tie_counts: List[int] = []
    cnt = 1
    for i in range(1, n):
        if abs(sorted_x[i] - sorted_x[i - 1]) <= tie_eps:
            cnt += 1
        else:
            if cnt > 1:
                tie_counts.append(cnt)
            cnt = 1
    if cnt > 1:
        tie_counts.append(cnt)
    tie_correction = sum(t * (t - 1) * (2 * t + 5) for t in tie_counts)
    var_s = (n * (n - 1) * (2 * n + 5) - tie_correction) / 18.0
    var_s_raw = var_s
    var_s = max(var_s, 1.0)               # §4 division guard
    if S > 0:
        z = (S - 1) / math.sqrt(var_s)
    elif S < 0:
        z = (S + 1) / math.sqrt(var_s)
    else:
        z = 0.0
    return float(S), float(var_s_raw), float(z)


# ---------------------------------------------------------------------------
# §3.4 Hurst with the Anis-Lloyd correction
# ---------------------------------------------------------------------------


def anis_lloyd_expected_rs(n: int) -> float:
    """§3.4 ``E_AL(n)``; ``n > 340`` ⇒ ``sqrt(πn/2)``; ``n <= 1`` ⇒ 0."""
    if n <= 1:
        return 0.0
    if n <= 340:
        s = sum(math.sqrt((n - i) / i) for i in range(1, n))
        ratio = math.exp(math.lgamma((n - 1) / 2) - math.lgamma(n / 2)) \
            / math.sqrt(math.pi)
        return (n - 0.5) / n * ratio * s
    return math.sqrt(math.pi * n / 2)


def hurst_rs_anis_lloyd_corrected(x: Sequence[float], min_len: int = 8,
                                  max_len: Optional[int] = None,
                                  eps: float = EPS) -> Tuple[float, float]:
    """§3.4 R/S Hurst with the Anis-Lloyd bias correction.

    Returns ``(H, r2)``; ``H`` clipped to ``[0, 1.5]`` (§5.1 schema domain).
    Too-short series or fewer than 3 regression points ⇒ ``(0.5, 0.0)`` — the
    random-walk value with zero explanatory power, never a fabricated exponent.
    """
    n = len(x)
    if n < min_len * 2:
        return 0.5, 0.0
    if max_len is None:
        max_len = n // 2
    lens: List[float] = []
    rs: List[float] = []
    length = max_len
    while length >= min_len:
        num_segs = n // length
        if num_segs < 1:
            length //= 2
            continue
        acc_rs = 0.0
        valid_segs = 0
        for k in range(num_segs):
            seg = x[k * length:(k + 1) * length]
            m = sum(seg) / length
            dev = [v - m for v in seg]
            cum = 0.0
            cum_vals: List[float] = []
            for d in dev:
                cum += d
                cum_vals.append(cum)
            R = max(cum_vals) - min(cum_vals) if cum_vals else 0.0
            S = math.sqrt(sum(d * d for d in dev) / length) if length > 1 else 0.0
            if S < eps:
                continue                  # §3.4 edge case: skip the block
            rs_raw = R / S
            e_rs = anis_lloyd_expected_rs(length)
            if e_rs < eps:
                continue
            rs_corr = rs_raw / e_rs * math.sqrt(math.pi * length / 2)
            acc_rs += rs_corr
            valid_segs += 1
        if valid_segs > 0:
            avg_rs = acc_rs / valid_segs
            lens.append(math.log(length))
            rs.append(math.log(max(avg_rs, eps)))
        length //= 2
    if len(lens) < 3:
        return 0.5, 0.0
    beta, _se, r2 = ols_slope_newey_west(lens, rs)
    return max(0.0, min(1.5, beta)), r2


# ---------------------------------------------------------------------------
# §3.5 The AD-line: full Wilder DI+ / DI− / DX / ADX
# ---------------------------------------------------------------------------


def wilder_rma(prev: float, curr: float, n: int) -> float:
    """§2/§3.5 Wilder smoothing ``RMA_t = (RMA_{t−1}(n−1) + x_t)/n``."""
    return (prev * (n - 1) + curr) / n


def directional_movement(h: float, l: float, prev_h: float, prev_l: float
                         ) -> Tuple[float, float]:
    """§3.5 ``+DM`` / ``−DM`` with the corrected mutual-exclusion condition."""
    up = h - prev_h
    down = prev_l - l
    plus = up if (up > down and up > 0) else 0.0
    minus = down if (down > up and down > 0) else 0.0
    return plus, minus


def compute_adx_wilder(bars: Sequence[Dict[str, Any]], n: int = 14,
                       eps: float = EPS) -> Dict[str, Any]:
    """§3.5 full Wilder ADX (the AD-line): ``{di_plus, di_minus, dx, adx,
    tr_smooth, plus_dm_smooth, minus_dm_smooth, n_valid, warmup}``.

    Edge cases, all implemented:
      * ``H < L`` or non-positive OHLC ⇒ the bar pair is dropped (§3.5).
      * fewer than ``n`` directional samples ⇒ zeros + ``warmup=True``.
      * ``n ≤`` samples ``< 2n`` ⇒ ``warmup_2n=True``: the value is produced
        from the Wilder seed but §3.5's "NaN until t >= 2n" confidence
        boundary is not yet met (ISSUE-CP4-018); the scale state carries
        ``ADX_WARMUP_QX``.
      * ``TR_smooth = 0`` ⇒ ``DI+ = DI− = DX = 0`` (§3.5).
      * ``DI+ + DI− ≈ 0`` ⇒ ``DX = 0`` (§2 edge).
    ISSUE-CP4-015: §4's early-return path references unbound ``di_plus``; the
    canonical Wilder seeding (DI from the first smoothed values) is used.
    """
    out: Dict[str, Any] = {"di_plus": 0.0, "di_minus": 0.0, "dx": 0.0,
                           "adx": 0.0, "tr_smooth": 0.0,
                           "plus_dm_smooth": 0.0, "minus_dm_smooth": 0.0,
                           "n_valid": 0, "warmup": True, "warmup_2n": True}
    if len(bars) < 2:
        return out
    trs: List[float] = []
    plus_dms: List[float] = []
    minus_dms: List[float] = []
    for i in range(1, len(bars)):
        if not validate_bar(bars[i]) or not validate_bar(bars[i - 1]):
            continue
        h, l, pc = bars[i]["h"], bars[i]["l"], bars[i - 1]["c"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        plus, minus = directional_movement(h, l, bars[i - 1]["h"],
                                           bars[i - 1]["l"])
        trs.append(tr)
        plus_dms.append(plus)
        minus_dms.append(minus)
    out["n_valid"] = len(trs)
    if len(trs) < n:
        return out                        # warm-up: no fabricated ADX
    # §3.5 "first n bars → warmup, NaN until t >= 2n": the value is produced
    # from the Wilder seed as soon as n directional samples exist (§8.1
    # FIX_04_ADX_KNOWN is canonical at 15 bars), while ``warmup_2n`` carries
    # the chapter's confidence boundary (ISSUE-CP4-018).
    out["warmup_2n"] = len(trs) < 2 * n
    tr_smooth = sum(trs[:n]) / n
    plus_smooth = sum(plus_dms[:n]) / n
    minus_smooth = sum(minus_dms[:n]) / n
    out["warmup"] = False

    def _di(tr_s: float, dm_s: float) -> float:
        if tr_s < eps:
            return 0.0                    # §3.5 TR_smooth = 0
        return 100 * dm_s / tr_s

    def _dx(di_p: float, di_m: float) -> float:
        if (di_p + di_m) <= eps:
            return 0.0
        return 100 * abs(di_p - di_m) / (di_p + di_m)

    di_plus = _di(tr_smooth, plus_smooth)
    di_minus = _di(tr_smooth, minus_smooth)
    dx_list = [_dx(di_plus, di_minus)]
    for idx in range(n, len(trs)):
        tr_smooth = wilder_rma(tr_smooth, trs[idx], n)
        plus_smooth = wilder_rma(plus_smooth, plus_dms[idx], n)
        minus_smooth = wilder_rma(minus_smooth, minus_dms[idx], n)
        di_plus = _di(tr_smooth, plus_smooth)
        di_minus = _di(tr_smooth, minus_smooth)
        dx_list.append(_dx(di_plus, di_minus))
    adx = sum(dx_list[:n]) / n if len(dx_list) >= n else sum(dx_list) / len(dx_list)
    for dxv in dx_list[n:]:
        adx = wilder_rma(adx, dxv, n)
    out.update({"di_plus": di_plus, "di_minus": di_minus,
                "dx": dx_list[-1], "adx": adx, "tr_smooth": tr_smooth,
                "plus_dm_smooth": plus_smooth, "minus_dm_smooth": minus_smooth,
                "warmup_2n": len(trs) < 2 * n})
    return out


def continuity_break(bars: Sequence[Dict[str, Any]], tf_seconds: int,
                     mult: float = 2.0) -> bool:
    """§3.5 UTC continuity: a time gap > 2× the timeframe marks a break."""
    if tf_seconds <= 0 or len(bars) < 2:
        return False
    step_ms = int(tf_seconds * 1000)
    for i in range(1, len(bars)):
        gap = abs(int(bars[i].get("ts", 0)) - int(bars[i - 1].get("ts", 0)))
        if gap > mult * step_ms:
            return True
    return False


def compute_pos_scale(bars: Sequence[Dict[str, Any]], window: int,
                      atr_val: float, eps: float = EPS) -> float:
    """§2 ``pos_s = (C_t − SMA_window)/max(ATR, ε)``."""
    if not bars:
        return 0.0
    recent = bars[-window:] if len(bars) >= window else bars
    sma = sum(b["c"] for b in recent) / len(recent)
    return (bars[-1]["c"] - sma) / max(atr_val, eps)


# ---------------------------------------------------------------------------
# §3 direction/strength · §3.8 trend quality · §2 quality labels
# ---------------------------------------------------------------------------


def trend_direction_and_strength(seq_score: float, slope_z: float, pos: float,
                                 w: Tuple[float, float, float] = (0.4, 0.35, 0.25),
                                 th: float = 0.5,
                                 deadband: float = 0.05
                                 ) -> Tuple[int, float, float]:
    """§4 ``z = wa·seq + wb·slope_z + wc·pos`` → direction, strength, raw z.

    ``direction = +1`` if ``z > 0.05``, ``−1`` if ``z < −0.05``, else ``0``;
    ``strength = min(1, |z|/θ_str)``.
    """
    wa, wb, wc = w
    z = wa * seq_score + wb * slope_z + wc * pos
    direction = 1 if z > deadband else (-1 if z < -deadband else 0)
    strength = min(1.0, abs(z) / max(th, EPS))
    return direction, strength, z


def compute_trend_quality(r2: float, adx: float, hurst: float,
                          h_clip_max: float = 1.2) -> float:
    """§3.8 ``Q_trend = R² · (ADX/100) · H_clip``, clipped to ``[0, 1.5]``.

    ISSUE-CP4-016: §2 says ``min(H, 1.2)`` while §3.8/§4 read
    ``H if 0 ≤ H ≤ 1.2 else 1.0 if H > 1.2 else 0``; the §4 executable form is
    implemented (identical for ``H ≤ 1.2``, and both are clipped to 1.5).
    """
    if hurst < 0:
        h_clip = 0.0
    elif hurst > h_clip_max:
        h_clip = 1.0
    else:
        h_clip = hurst
    return max(0.0, min(1.5, r2 * (adx / 100.0) * h_clip))


def quality_label(q: float, r2: float, adx: float, hurst: float) -> str:
    """§2 Q0–Q5 mapping (Q5 additionally requires R² ≥ 0.7 ∧ ADX ≥ 25 ∧ H ≥ 0.6)."""
    if q >= 1.0 and r2 >= 0.7 and adx >= 25 and hurst >= 0.6:
        return "Q5"
    if q >= 0.75:
        return "Q4"
    if q >= 0.55:
        return "Q3"
    if q >= 0.35:
        return "Q2"
    if q >= 0.15:
        return "Q1"
    return "Q0"


def scale_state(quality_label_: str, evidence_count: int, adx: float,
                strength: float, continuity_broken: bool,
                valid: bool, adx_valid_min: float = 10.0) -> str:
    """§5.3 fate lifecycle ``UNKNOWN → CALCULATING → VALID → DEGRADED → INVALID``."""
    if not valid:
        return "INVALID"
    if quality_label_ == "Q0" or continuity_broken \
            or (adx < adx_valid_min and strength < 0.3):
        return "DEGRADED"
    if quality_label_ != "Q0" and evidence_count >= 2 and adx >= adx_valid_min:
        return "VALID"
    return "CALCULATING"


# ---------------------------------------------------------------------------
# §3.7 Exhaustion via momentum divergence (shared with E10)
# ---------------------------------------------------------------------------


def divergence_exhaustion_check(price_swings: Sequence[Dict[str, Any]],
                                mom_series: Optional[Sequence[float]],
                                current_idx: int, lookback: int = 20,
                                delta: float = 0.1, score: float = 0.8
                                ) -> Dict[str, Any]:
    """§3.7/§4 exhaustion via a price/momentum divergence.

    Bearish: price HH while momentum makes a lower high (``mom < prev − δ``).
    Bullish: the mirror. E10 is the momentum provider; when the series is
    absent (CP-4: E10 lands at CP-5) the result is explicitly degraded —
    no divergence is ever fabricated (P19).
    """
    if mom_series is None:
        return {"is_exhaustion": False, "type": None, "score": 0.0,
                "degraded": True, "degraded_reason": MOMENTUM_UNAVAILABLE_REASON}
    if len(price_swings) < 2 or len(mom_series) < lookback:
        return {"is_exhaustion": False, "type": None, "score": 0.0,
                "degraded": False, "degraded_reason": None}
    price_recent = price_swings[-1]["price"]
    price_prev = price_swings[-2]["price"]
    mom_recent = mom_series[-1]
    mom_prev = mom_series[-2]
    bear_div = (price_recent > price_prev) and (mom_recent < mom_prev - delta)
    bull_div = (price_recent < price_prev) and (mom_recent > mom_prev + delta)
    if bear_div:
        return {"is_exhaustion": True, "type": "BEARISH_DIVERGENCE",
                "score": score, "degraded": False, "degraded_reason": None}
    if bull_div:
        return {"is_exhaustion": True, "type": "BULLISH_DIVERGENCE",
                "score": score, "degraded": False, "degraded_reason": None}
    return {"is_exhaustion": False, "type": None, "score": 0.0,
            "degraded": False, "degraded_reason": None}


def exhaustion_score(div_binary: float, strength: float, adx: float) -> float:
    """§3.7 ``ExhaustionScore = Div_binary · (1 − strength_s) · (1 − ADX/100)``."""
    return div_binary * (1.0 - strength) * (1.0 - adx / 100.0)


# ---------------------------------------------------------------------------
# §5 Objects
# ---------------------------------------------------------------------------


@dataclass
class TrendScale:
    """§5.1 TrendScale object (all required fields validated)."""

    scale: str
    direction: int
    strength: float
    quality: float
    quality_label: str
    seq_score: float
    slope_z: float
    pos: float
    r2: float
    adx: float
    di_plus: float
    di_minus: float
    hurst: float
    mk_z: float
    evidence_count: int
    as_of: int
    snapshot_id: str
    contract_version: str = CONTRACT_VERSION
    pit_lag: int = PIT_LAG
    dx: float = 0.0
    beta: float = 0.0
    state: str = "UNKNOWN"
    continuity_break: bool = False
    degraded_reason: Optional[str] = None

    def to_canonical(self) -> Dict[str, Any]:
        """Canonical payload (``snapshot_id`` excluded)."""
        return {k: getattr(self, k) for k in TREND_SCALE_REQUIRED
                if k != "snapshot_id"}

    def to_dict(self) -> Dict[str, Any]:
        """The published §5.1 object.

        ``snapshot_id`` is derived from ``to_canonical()`` only, so publishing
        the operational extras cannot move it.
        """
        return asdict(self)

    def update_snapshot(self) -> "TrendScale":
        self.snapshot_id = e09_snapshot_id(self.to_canonical())
        return self

    def validate_schema(self) -> None:
        for name in TREND_SCALE_REQUIRED:
            if getattr(self, name, None) is None:
                raise ValueError(f"TREND_SCALE_QX: missing {name}")
        if self.scale not in SCALES:
            raise ValueError(f"TREND_SCALE_QX: scale {self.scale!r}")
        if self.direction not in (-1, 0, 1):
            raise ValueError(f"TREND_SCALE_QX: direction {self.direction!r}")
        if not (0.0 <= self.strength <= 1.0):
            raise ValueError(f"TREND_SCALE_QX: strength {self.strength}")
        if not (0.0 <= self.quality <= 1.5):
            raise ValueError(f"TREND_SCALE_QX: quality {self.quality}")
        if self.quality_label not in QUALITY_LABELS:
            raise ValueError(f"TREND_SCALE_QX: label {self.quality_label!r}")
        if not (-1.0 <= self.seq_score <= 1.0):
            raise ValueError(f"TREND_SCALE_QX: seq_score {self.seq_score}")
        if not (0.0 <= self.r2 <= 1.0):
            raise ValueError(f"TREND_SCALE_QX: r2 {self.r2}")
        if not (0.0 <= self.adx <= 100.0):
            raise ValueError(f"TREND_SCALE_QX: adx {self.adx}")
        if not (-0.1 <= self.hurst <= 1.5):
            raise ValueError(f"TREND_SCALE_QX: hurst {self.hurst}")
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError("TREND_SCALE_QX: contract_version must be 4.0.0")
        if self.pit_lag != PIT_LAG:
            raise ValueError("TREND_SCALE_QX: pit_lag must be 1")
        if self.state not in SCALE_STATES:
            raise ValueError(f"TREND_SCALE_QX: state {self.state!r}")
        if len(self.snapshot_id) != 64:
            raise ValueError("TREND_SCALE_QX: snapshot_id not 64-hex")


@dataclass
class TrendStack:
    """§5.2 TrendStack object."""

    stack: Dict[str, int]
    bias: float
    alignment: str
    quality_agg: float
    snapshot_id: str
    as_of: int
    contract_version: str = CONTRACT_VERSION

    def to_canonical(self) -> Dict[str, Any]:
        return {"stack": dict(self.stack), "bias": self.bias,
                "alignment": self.alignment, "quality_agg": self.quality_agg,
                "as_of": self.as_of}

    def update_snapshot(self) -> "TrendStack":
        self.snapshot_id = e09_snapshot_id(
            {"kind": "TrendStack", **self.to_canonical()})
        return self

    def validate_schema(self) -> None:
        for name in TREND_STACK_REQUIRED:
            if getattr(self, name, None) in (None, "", {}):
                raise ValueError(f"TREND_STACK_QX: missing {name}")
        if set(self.stack) != set(SCALES):
            raise ValueError(f"TREND_STACK_QX: stack keys {sorted(self.stack)}")
        for s, d in self.stack.items():
            if d not in (-1, 0, 1):
                raise ValueError(f"TREND_STACK_QX: {s} direction {d!r}")
        if not (-1.0 <= self.bias <= 1.0):
            raise ValueError(f"TREND_STACK_QX: bias {self.bias}")
        if self.alignment not in ALIGNMENTS:
            raise ValueError(f"TREND_STACK_QX: alignment {self.alignment!r}")
        if len(self.snapshot_id) != 64:
            raise ValueError("TREND_STACK_QX: snapshot_id not 64-hex")


def e09_snapshot_id(payload: Dict[str, Any]) -> str:
    """§5.5 ``snapshot_id = SHA256(canonical_json(canonical_snapshot_payload))``."""
    return canonical_snapshot_id(ENGINE, CONTRACT_VERSION, payload)


def stack_bias(scale_directions: Dict[str, int],
               weights: Optional[Dict[str, float]] = None) -> float:
    """§3.6 ``Bias_trend = Σ w_s · direction_s`` with the governed weights."""
    w = weights or W_STACK_CORRECTED
    if set(w) != set(SCALES):
        raise ValueError("TREND_STACK_QX: weight keys must cover the 4 scales")
    if abs(sum(w.values()) - 1.0) > 1e-9:
        raise ValueError("TREND_STACK_QX: governed weights must sum to 1")
    if set(scale_directions) != set(SCALES):
        raise ValueError("TREND_STACK_QX: scale_directions must cover the "
                         "4 scales")
    return sum(w[s] * scale_directions[s] for s in SCALES)


def stack_alignment(bias: float, scale_directions: Dict[str, int],
                    prev_alignment: Optional[str] = None,
                    params: Optional[EngineParams] = None) -> str:
    """§3.6/§5.2 alignment label from the governed Bias thresholds.

    ``Bias > 0.5`` ⇒ ALIGNED_BULL · ``Bias < −0.5`` ⇒ ALIGNED_BEAR ·
    ``|Bias| ≤ 0.3`` ⇒ SIDEWAYS (or CONFLICTING when ≥ 1 scale opposes MACRO) ·
    otherwise TRANSITIONING (a bias between the two bands).
    """
    p = params or EngineParams()
    macro = scale_directions.get("MACRO", 0)
    opposing = any(scale_directions[s] != 0 and macro != 0
                   and scale_directions[s] != macro
                   for s in SCALES if s != "MACRO")
    if bias > p.bias_bull:
        return "ALIGNED_BULL"
    if bias < p.bias_bear:
        return "ALIGNED_BEAR"
    if abs(bias) <= p.bias_sideways:
        return "CONFLICTING" if opposing else "SIDEWAYS"
    return "TRANSITIONING"


def quality_aggregate(scale_qualities: Dict[str, float],
                      weights: Optional[Dict[str, float]] = None) -> float:
    """Governed-weight aggregate of the per-scale trend qualities."""
    w = weights or W_STACK_CORRECTED
    if set(w) != set(SCALES):
        raise ValueError("TREND_STACK_QX: weight keys must cover the 4 scales")
    if set(scale_qualities) != set(SCALES):
        raise ValueError("TREND_STACK_QX: scale_qualities must cover the "
                         "4 scales")
    return sum(w[s] * scale_qualities[s] for s in SCALES)


# ---------------------------------------------------------------------------
# §8 Statistics (Wilson CI, Pearson redundancy)
# ---------------------------------------------------------------------------


def wilson_ci(p_hat: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    """§8.5 Wilson score interval (z = 1.96 for 95%)."""
    if n <= 0:
        return (0.0, 0.0)
    denom = 1.0 + z * z / n
    centre = p_hat + z * z / (2 * n)
    spread = z * math.sqrt(max(p_hat * (1 - p_hat) / n + z * z / (4 * n * n), 0.0))
    return ((centre - spread) / denom, (centre + spread) / denom)


def pearson(x: Sequence[float], y: Sequence[float]) -> float:
    """§8.6 Pearson r between components; > 0.85 ⇒ redundant."""
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
# §4 Streaming engine
# ---------------------------------------------------------------------------


class TrendEngine:
    """§4 ``TrendEngine`` — per-scale state vector + governed TrendStack.

    Idempotent on ``t_close`` (cache key per §4/§8.2); the cache is bounded at
    1000 entries. All formulas run on CLOSED bars with the one-candle lag of
    §3.9; ``is_closed=False`` produces a Q0/unconfirmed preview and no event.
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        self.params = get_params(params)
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.prev_direction: Dict[str, int] = {s: 0 for s in SCALES}
        self.prev_quality_label: Dict[str, List[str]] = {s: [] for s in SCALES}
        self.prev_alignment: Optional[str] = None
        self.events: List[Dict[str, Any]] = []

    # -- helpers ---------------------------------------------------------
    def _emit(self, code: str, ts: int, **payload: Any) -> Dict[str, Any]:
        event = {"code": code, "name": EVENT_CATALOG[code]["name"], "ts": ts,
                 **payload}
        self.events.append(event)
        return event

    def _scale_state(self, bars: Sequence[Dict[str, Any]],
                     swings: Sequence[Dict[str, Any]], atr: float,
                     W: int, scale: str, tf_seconds: int
                     ) -> TrendScale:
        p = self.params
        current_idx = len(bars) - 1
        seq, ev_count = compute_seq_score(swings, W, current_idx)
        closes = [b["c"] for b in bars[-W:]]
        log_closes = [math.log(max(c, EPS)) for c in closes]
        t = list(range(len(log_closes)))
        beta, se, r2 = ols_slope_newey_west(t, log_closes)
        slope_z = beta / max(se, EPS) if se != float("inf") else 0.0
        pos = compute_pos_scale(bars, W, atr)
        direction, strength, _raw = trend_direction_and_strength(
            seq, slope_z, pos, (p.w_a, p.w_b, p.w_c), p.strength_threshold,
            p.direction_deadband)
        _S, _var, mkz = mann_kendall_with_tie_correction(log_closes)
        hurst, _hr2 = hurst_rs_anis_lloyd_corrected(
            log_closes, p.hurst_min_len,
            min(p.hurst_window, max(len(log_closes) // 2, p.hurst_min_len)))
        adx_window = bars[-max(W, p.adx_n * 3):]
        adx_res = compute_adx_wilder(adx_window, p.adx_n)
        adx = adx_res["adx"]
        q = compute_trend_quality(r2, adx, hurst, p.hurst_clip_max)
        label = quality_label(q, r2, adx, hurst)
        cont_break = continuity_break(adx_window, tf_seconds,
                                      p.continuity_gap_mult)
        valid = all(validate_bar(b) for b in bars[-W:]) and len(bars) >= 2
        state = scale_state(label, ev_count, adx, strength, cont_break, valid,
                            p.adx_valid_min)
        degraded_reason = None
        if ev_count == 0:
            degraded_reason = SWINGS_UNAVAILABLE_REASON
        elif adx_res["warmup"] or adx_res["warmup_2n"]:
            # §3.5: ADX is not trustworthy before t >= 2n (ISSUE-CP4-018).
            degraded_reason = "ADX_WARMUP_QX"
        scale_obj = TrendScale(
            scale=scale, direction=direction, strength=strength, quality=q,
            quality_label=label, seq_score=seq, slope_z=slope_z, pos=pos,
            r2=r2, adx=adx, di_plus=adx_res["di_plus"],
            di_minus=adx_res["di_minus"], hurst=hurst, mk_z=mkz,
            evidence_count=ev_count, as_of=int(bars[-1].get("ts", 0)),
            snapshot_id="", dx=adx_res["dx"], beta=beta, state=state,
            continuity_break=cont_break, degraded_reason=degraded_reason)
        scale_obj.update_snapshot()
        scale_obj.validate_schema()
        return scale_obj

    # -- main entry ------------------------------------------------------
    def process_bar(self, bars: Sequence[Dict[str, Any]],
                    swings: Optional[Sequence[Dict[str, Any]]] = None,
                    atr: float = 0.0,
                    mom_series: Optional[Sequence[float]] = None,
                    tf_seconds: int = 3600,
                    bos_event: Optional[Dict[str, Any]] = None,
                    choch_event: Optional[Dict[str, Any]] = None,
                    oi_state: str = "MISSING") -> Dict[str, Any]:
        """Compute the four scale vectors + TrendStack for the last closed bar.

        ``swings=None`` (E01 absent) ⇒ ``seq_score = 0`` with an explicit
        degraded reason; ``mom_series=None`` (E10 absent, lands at CP-5) ⇒ the
        divergence check degrades instead of fabricating momentum.
        ``oi_state`` follows the §1.3 honest-label contract: ``MISSING`` emits
        an explicit event and never fabricates an OI-derived value.
        """
        p = self.params
        bars = [b for b in bars]
        if not bars:
            raise ValueError("EMPTY_WINDOW_QX: E09 requires a closed window")
        last = bars[-1]
        key = f"{last.get('ts', 0)}_{last.get('c', 0.0)}"
        if key in self.cache:
            return self.cache[key]        # §8.2 idempotency on t_close
        if oi_state not in OI_STATES:
            raise ValueError(f"OI_STATE_QX: {oi_state!r}")
        swings = dedup_swings(list(swings or []), p.swing_dedup_bars)
        if oi_state == "MISSING":
            self._emit("EV_TRD_008", int(last.get("ts", 0)),
                       reason=OI_MISSING_REASON, oi_state="MISSING")
        scales: Dict[str, Dict[str, Any]] = {}
        scale_objs: Dict[str, TrendScale] = {}
        windows = scale_windows(p)
        for s in SCALES:
            obj = self._scale_state(bars, swings, atr, windows[s], s,
                                    tf_seconds)
            scale_objs[s] = obj
            # Publish the whole validated §5.1 object: every
            # TREND_SCALE_REQUIRED key must be observable downstream, not just
            # the subset the stack happens to read.
            scales[s] = obj.to_dict()
        dirs = {s: scale_objs[s].direction for s in SCALES}
        bias = stack_bias(dirs)
        alignment = stack_alignment(bias, dirs, self.prev_alignment, p)
        q_agg = quality_aggregate({s: scale_objs[s].quality for s in SCALES})
        stack = TrendStack(stack=dirs, bias=bias, alignment=alignment,
                           quality_agg=q_agg, snapshot_id="",
                           as_of=int(last.get("ts", 0)))
        stack.update_snapshot()
        stack.validate_schema()

        ts = int(last.get("ts", 0))
        # §5.4 events.
        for s in SCALES:
            obj = scale_objs[s]
            prev = self.prev_direction[s]
            if prev == 0 and obj.direction != 0:
                bos_ok = bool(bos_event)
                if (bos_ok and abs(obj.slope_z) >= p.slope_z_threshold
                        and abs(obj.pos) >= p.pos_threshold
                        and abs(obj.mk_z) >= p.mk_crit_z):
                    self._emit("EV_TRD_001", ts, scale=s,
                               direction=obj.direction, slope_z=obj.slope_z,
                               pos=obj.pos, mk_z=obj.mk_z)
            elif prev != 0 and obj.direction == prev and obj.strength >= 0.5:
                self._emit("EV_TRD_002", ts, scale=s, strength=obj.strength)
            if (choch_event and prev != 0 and obj.direction == -prev
                    and obj.slope_z * prev < 0 and obj.mk_z * prev < 0):
                self._emit("EV_TRD_004", ts, scale=s,
                           confirm_bars=p.transition_confirm_bars)
            history = self.prev_quality_label[s]
            history.append(obj.quality_label)
            if len(history) > p.quality_drop_window:
                history.pop(0)
            if len(history) >= 2:
                drop = (QUALITY_LABELS.index(history[0])
                        - QUALITY_LABELS.index(obj.quality_label))
                if drop >= p.quality_drop_levels:
                    self._emit("EV_TRD_008", ts, scale=s,
                               from_label=history[0], to_label=obj.quality_label)
            self.prev_direction[s] = obj.direction
        if all(dirs[s] == dirs["MACRO"] and dirs[s] != 0 for s in SCALES) \
                and abs(bias) >= p.stack_aligned_bias:
            self._emit("EV_TRD_005", ts, bias=bias, alignment=alignment)
        if any(dirs[s] != 0 and dirs["MACRO"] != 0 and dirs[s] != dirs["MACRO"]
               for s in SCALES if s != "MACRO"):
            self._emit("EV_TRD_006", ts, bias=bias)
        short = scale_objs["SHORT"]
        if (abs(short.hurst - 0.5) < p.hurst_sideways_band
                and short.adx < p.adx_sideways_max
                and short.r2 < p.r2_sideways_max):
            self._emit("EV_TRD_007", ts, hurst=short.hurst, adx=short.adx,
                       r2=short.r2)
        # §3.7 exhaustion (shared with E10).
        div = divergence_exhaustion_check(
            [s for s in swings[-2:]] if swings else [], mom_series,
            len(bars) - 1, p.divergence_lookback, p.divergence_delta,
            p.divergence_score)
        if div["is_exhaustion"] and short.strength < 0.8:
            self._emit("EV_TRD_003", ts, divergence=div["type"],
                       score=div["score"], strength=short.strength)
        payload = {"scales": scales,
                   # The §5.2 TrendStack object, published in full (every
                   # TREND_STACK_REQUIRED key observable, `as_of_bar` kept as
                   # the engine-internal alias).
                   "stack": dict(stack.stack), "as_of": int(stack.as_of),
                   "bias": bias, "alignment": alignment,
                   "quality_agg": q_agg, "snapshot_id": stack.snapshot_id,
                   "stack_snapshot": {s: scale_objs[s].snapshot_id
                                      for s in SCALES},
                   "as_of_bar": ts, "divergence": div,
                   "oi_state": oi_state,
                   "degraded": bool(div.get("degraded")) or not swings,
                   "degraded_reason": (div.get("degraded_reason")
                                       or (SWINGS_UNAVAILABLE_REASON
                                           if not swings else None)),
                   "engine": ENGINE, "contract_version": CONTRACT_VERSION}
        self.cache[key] = payload
        if len(self.cache) > 1000:
            self.cache.pop(next(iter(self.cache)))
        return payload


def observation_to_bar(obs: MarketObservation,
                       timeframe: Optional[str] = None) -> Dict[str, Any]:
    """MarketObservation → the ``{ts,o,h,l,c,v,is_closed}`` bar shape."""
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
               swings: Optional[Sequence[Dict[str, Any]]] = None,
               atr: float = 0.0,
               mom_series: Optional[Sequence[float]] = None,
               tf_seconds: int = 3600,
               bos_event: Optional[Dict[str, Any]] = None,
               choch_event: Optional[Dict[str, Any]] = None,
               oi_state: str = "MISSING",
               params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Batch driver → the TrendState/TrendStack payload for the last bar."""
    engine = TrendEngine(params)
    out = engine.process_bar(bars, swings, atr, mom_series, tf_seconds,
                             bos_event, choch_event, oi_state)
    out["events"] = list(engine.events)
    return out


class E09TrendEngine(EngineBase):
    """E09_Trend on the frozen EngineBase contract (v4.0.0).

    ``compute(symbol, timeframe, as_of, context)``; consumed context keys:
      ``window`` / ``provider`` — closed-candle window (catalog surface)
      ``e09_params``            — §6 overrides (unknown keys rejected)
      ``swings``                — E01 SwingSequence ``[{type, price, idx,
                                  confirmed_at_idx}]`` (PIT: a violation raises)
      ``atr``                   — E04 governed ATR (absent ⇒ pos degrades
                                  against ``ATR_FLOOR``, never recomputed)
      ``mom_series``            — E10 momentum series (absent ⇒ the divergence
                                  branch degrades explicitly)
      ``tf_seconds``            — timeframe length for the §3.5 continuity test
      ``bos_event``/``choch_event`` — E01 structural confirmations
      ``oi_state``              — §1.3 honest-label availability state
    Emits one ``EvidenceEvent`` per scale on ``evidence.E09.{condition_state}``.
    Descriptive only: no orders, no sizing (§1.4).
    """

    engine_id = "E09"
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
            swings=context.get("swings"),
            atr=float(context.get("atr", 0.0)),
            mom_series=context.get("mom_series"),
            tf_seconds=int(context.get("tf_seconds", 3600)),
            bos_event=context.get("bos_event"),
            choch_event=context.get("choch_event"),
            oi_state=str(context.get("oi_state", "MISSING")),
            params=context.get("e09_params"))
        quality = self._window_quality(window_obs)
        return [self._to_evidence(scale, data, symbol, timeframe, quality,
                                  result)
                for scale, data in result["scales"].items()]

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

    def _to_evidence(self, scale: str, data: Dict[str, Any], symbol: str,
                     timeframe: str, quality: float,
                     result: Dict[str, Any]) -> EvidenceEvent:
        ts = int(result["as_of_bar"])
        iso = datetime.datetime.fromtimestamp(
            ts / 1000.0, tz=datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.") + f"{ts % 1000:03d}Z"
        state = str(data["state"])
        explanation = (f"E09 {scale} dir={data['direction']} "
                       f"strength={data['strength']:.4f} Q={data['quality']:.4f}"
                       f"/{data['quality_label']} bias={result['bias']:.4f} "
                       f"{result['alignment']}")
        if data.get("degraded_reason"):
            explanation += f" degraded={data['degraded_reason']}"
        return EvidenceEvent(
            evidence_id=uuid_v7(),
            engine_id=self.engine_id,
            analyst_version=self.analyst_version,
            symbol=symbol, timeframe=timeframe,
            snapshot_id=data["snapshot_id"],
            event_time=iso, availability_time=iso,
            observation_window={"scale": scale, "tf": timeframe,
                                "bars": scale_windows(self.p_default())[scale]},
            feature_snapshot_id=data["snapshot_id"],
            feature_dependencies=("window", "I_Structure_v4",
                                  "I_Volatility_v4",
                                  "I_Momentum_v4(degradable)"),
            condition_state=f"TREND_{scale}_{state}",
            direction=int(data["direction"]),
            strength=float(min(max(data["strength"], 0.0), 1.0)),
            confidence=float(min(max(data["r2"], 0.0), 1.0)),
            quality=float(quality),
            validity="DEGRADED" if state in ("DEGRADED", "INVALID") else "VALID",
            fate_state=LifecycleState.ACTIVE if state == "VALID"
            else LifecycleState.CANDIDATE,
            age=float(data["evidence_count"]),
            decay=math.exp(-data["evidence_count"] /
                           max(scale_windows(self.p_default())[scale], 1)),
            explanation=explanation[:500],
            parameter_version="E09-TRD-V4.0.0/DEFAULTS-v1",
            lineage=(f"scale_{scale}", f"stack_{result['alignment']}"),
            resolution_class=str(data["quality_label"]),
        )

    @staticmethod
    def p_default() -> EngineParams:
        return EngineParams()


__all__ = [
    "ALIGNMENTS", "ANALYST_VERSION", "CONTRACT_LABEL", "CONTRACT_VERSION",
    "E09_DEFAULTS", "E09TrendEngine", "ENGINE", "EPS", "EVENT_CATALOG",
    "EngineParams", "MOMENTUM_UNAVAILABLE_REASON", "OI_MISSING_REASON",
    "OI_STATES", "PIT_LAG", "QUALITY_LABELS", "QUALITY_NAMES", "SCALES",
    "SCALE_STATES", "SWINGS_UNAVAILABLE_REASON", "TREND_SCALE_REQUIRED",
    "TREND_STACK_REQUIRED", "TrendEngine", "TrendScale", "TrendStack",
    "W_STACK_CORRECTED", "anis_lloyd_expected_rs", "compute_adx_wilder",
    "compute_pos_scale", "compute_seq_score", "compute_trend_quality",
    "continuity_break", "dedup_swings", "directional_movement",
    "divergence_exhaustion_check", "e09_snapshot_id", "exhaustion_score",
    "get_params", "hurst_rs_anis_lloyd_corrected",
    "mann_kendall_with_tie_correction", "newey_west_lag",
    "observation_to_bar", "ols_slope_newey_west", "pearson", "quality_aggregate",
    "quality_label", "run_engine", "scale_state", "scale_windows",
    "stack_alignment", "stack_bias", "trend_direction_and_strength",
    "validate_bar", "wilder_rma", "wilson_ci",
]
