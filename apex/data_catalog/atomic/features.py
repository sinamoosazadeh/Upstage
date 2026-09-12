"""APEX_GEN5 ATOM feature tier — features 01–44 of the 74-feature registry
(§3.12). Computed per closed candle, 1-candle lookback, validity 1 candle,
no decay (ATOM tier rules). Universal guards: H<L → INVALID, H−L<ε →
DEGRADED, is_closed=false → CANDIDATE. PIT-safe: computed only on CLOSED
candles; no future leak; L1-only, non-repainting.

Formula authority within CP-1's assigned text:
- §2.2 core formulas implemented exactly (body_ratio, upper/lower wick,
  close_position, normalized_range, volume_ratio, return_k; ROUND_HALF_UP,
  documented digit plans, division guards).
- Standard indicator definitions used by the frozen text (SMA/EMA/RMA/
  Wilder, ATR_14, TR, VWAP, OBV, RSI_14, z-scores, OLS slope, Hurst R/S,
  Parkinson, Garman–Klass, Rogers–Satchell) — via apex.data_catalog.math.
- Features whose formulas are named but not defined in CP-1's assigned
  ranges (k_*/theta_* families, GARCH parameterization, theta_body/vol/
  invalid) are registered (contract complete, §3.13) and compute to
  status UNAVAILABLE with a deterministic reason — fail-closed, never a
  guessed formula (recorded in DECISION_LOG §B/CP-1; owners: E02/E03
  chapters, CP-2/CP-3).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

from apex.data_catalog import math as m
from apex.data_catalog.contracts import MarketObservation

# compute(window, params, context) -> (value, q_formula_valid, status, reason)
ComputeFn = Callable[
    [List[MarketObservation], Dict[str, Any], Dict[str, Any]],
    Tuple[Optional[Any], float, str, str],
]

_EPS_RANGE = Decimal("1e-12")
_TIER1 = Decimal("1e-12")
_ATR_FLOOR = Decimal("1e-8")  # §2.2 Tier-2 ATR floor


def _guard(window: List[MarketObservation], need_prev_close: bool = False,
           min_bars: int = 1) -> Optional[Tuple[str, str]]:
    """Universal guards (H<L → INVALID; range<ε → DEGRADED; open candle →
    CANDIDATE; insufficient bars → UNAVAILABLE). Returns (status, reason)
    or None when the candle passes."""
    if not window:
        return "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    obs = window[-1]
    if obs.status != "CLOSED":
        return "CANDIDATE", "NOT_CLOSED_CANDLE"
    if obs.high < obs.low:
        return "INVALID", "H_LT_L_QX"
    if obs.high - obs.low < _EPS_RANGE:
        return "DEGRADED", "RANGE_BELOW_EPS_Q2"
    if len(window) < min_bars + (1 if need_prev_close else 0):
        return "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    return None


def _q(guard_result: Optional[Tuple[str, str]]) -> float:
    return 1.0 if guard_result is None else 0.0


# ---------------------------------------------------------------------------
# §2.2 exact formulas (quantized per the frozen digit plan)
# ---------------------------------------------------------------------------

def _f01_body_ratio(window, params, context):
    g = _guard(window)
    if g:
        return None, 0.0, g[0], g[1]
    obs = window[-1]
    rng = m._guard(obs.high - obs.low, _EPS_RANGE)
    value = m.quantize(abs(obs.close - obs.open) / rng, 6)
    return value, 1.0, "OK", ""


def _f02_upper_wick(window, params, context):
    g = _guard(window)
    if g:
        return None, 0.0, g[0], g[1]
    obs = window[-1]
    rng = m._guard(obs.high - obs.low, _EPS_RANGE)
    value = m.quantize((obs.high - max(obs.open, obs.close)) / rng, 6)
    return value, 1.0, "OK", ""


def _f03_lower_wick(window, params, context):
    g = _guard(window)
    if g:
        return None, 0.0, g[0], g[1]
    obs = window[-1]
    rng = m._guard(obs.high - obs.low, _EPS_RANGE)
    value = m.quantize((min(obs.open, obs.close) - obs.low) / rng, 6)
    return value, 1.0, "OK", ""


def _f04_close_position(window, params, context):
    g = _guard(window)
    if g:
        return None, 0.0, g[0], g[1]
    obs = window[-1]
    rng = m._guard(obs.high - obs.low, _EPS_RANGE)
    value = m.quantize((obs.close - obs.low) / rng, 4)
    return value, 1.0, "OK", ""


def _f05_range(window, params, context):
    g = _guard(window)
    if g:
        return None, 0.0, g[0], g[1]
    obs = window[-1]
    return m.quantize(obs.high - obs.low, 10), 1.0, "OK", ""


def _f06_body_size(window, params, context):
    g = _guard(window)
    if g:
        return None, 0.0, g[0], g[1]
    obs = window[-1]
    return m.quantize(abs(obs.close - obs.open), 10), 1.0, "OK", ""


def _f07_is_bullish(window, params, context):
    g = _guard(window)
    if g:
        return None, 0.0, g[0], g[1]
    return Decimal(1) if window[-1].close >= window[-1].open else Decimal(0), 1.0, "OK", ""


def _f08_is_bearish(window, params, context):
    g = _guard(window)
    if g:
        return None, 0.0, g[0], g[1]
    return Decimal(1) if window[-1].close < window[-1].open else Decimal(0), 1.0, "OK", ""


def _f09_tr(window, params, context):
    g = _guard(window, need_prev_close=True)
    if g:
        return None, 0.0, g[0], g[1]
    tr = m.true_range(window[-1], window[-2].close)
    return m.quantize(tr, 10), 1.0, "OK", ""


def _f10_atr_t(window, params, context):
    """ATR_t — Wilder-smoothed ATR_14 at bar t (seeded by the simple mean)."""
    n = int(params.get("atr_period", 14))
    if len(window) < n + 1:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    obs = window[-1]
    if obs.status != "CLOSED":
        return None, 0.0, "CANDIDATE", "NOT_CLOSED_CANDLE"
    if obs.high < obs.low:
        return None, 0.0, "INVALID", "H_LT_L_QX"
    value = m.atr_wilder(window, n)
    if value is None:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    return m.quantize(value, 10), 1.0, "OK", ""


def _f11_atr(window, params, context):
    """ATR — ATR_n over 14 bars (§2.2 normalized_range input)."""
    n = int(params.get("atr_period", 14))
    if len(window) < n + 1:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    obs = window[-1]
    if obs.status != "CLOSED":
        return None, 0.0, "CANDIDATE", "NOT_CLOSED_CANDLE"
    if obs.high < obs.low:
        return None, 0.0, "INVALID", "H_LT_L_QX"
    value = m.atr_simple(window, n)
    if value is None:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    if value < _ATR_FLOOR:
        return None, 0.0, "DEGRADED", "ATR_BELOW_FLOOR_Q2"
    return m.quantize(value, 10), 1.0, "OK", ""


def _f12_sma(window, params, context):
    n = int(params.get("sma_period", 20))
    if len(window) < n:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    value = m.sma([o.close for o in window], n)
    return m.quantize(value, 10), 1.0, "OK", ""


def _f13_ema(window, params, context):
    n = int(params.get("sma_period", 20))
    if len(window) < n:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    value = m.ema([o.close for o in window], n)
    return m.quantize(value, 10), 1.0, "OK", ""


def _f14_rma(window, params, context):
    n = int(params.get("atr_period", 14))
    if len(window) < n:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    value = m.rma([o.close for o in window], n)
    return m.quantize(value, 10), 1.0, "OK", ""


def _f15_wilder(window, params, context):
    n = int(params.get("atr_period", 14))
    if len(window) < n:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    value = m.rma([o.close for o in window], n)
    return m.quantize(value, 10), 1.0, "OK", ""


def _f16_vwap(window, params, context):
    if len(window) < 1:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    value = m.vwap(window)
    if value is None:
        return None, 0.0, "DEGRADED", "VWAP_DENOM_BELOW_EPS_Q2"
    return m.quantize(value, 10), 1.0, "OK", ""


def _f17_obv(window, params, context):
    if len(window) < 1:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    value = m.obv_series(window)
    return m.quantize(value, 8), 1.0, "OK", ""


def _f18_rsi(window, params, context):
    n = int(params.get("rsi_period", 14))
    if len(window) < n + 1:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    value = m.rsi_wilder([o.close for o in window], n)
    return m.quantize(value, 4), 1.0, "OK", ""


def _f19_volume_z(window, params, context):
    n = int(params.get("sma_period", 20))
    if len(window) < n:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    value = m.zscore([o.volume for o in window], n)
    return m.quantize(value, 4), 1.0, "OK", ""


def _f20_vol_ratio(window, params, context):
    n = int(params.get("sma_period", 20))
    if len(window) < n + 1:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    sma_prev = m.sma([o.volume for o in window[:-1]], n)
    if sma_prev is None:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    if sma_prev == 0:
        return None, 0.0, "DEGRADED", "SMA_VOLUME_ZERO_Q2"
    value = window[-1].volume / sma_prev
    return m.quantize(value, 4), 1.0, "OK", ""


def _f21_oi_z(window, params, context):
    n = int(params.get("sma_period", 20))
    ois = [o.oi for o in window if o.oi is not None]
    if len(ois) < n:
        return None, 0.0, "MISSING", "OI_MISSING_QX"  # never coerce OI to 0
    value = m.zscore(ois, n)
    return m.quantize(value, 4), 1.0, "OK", ""


def _unavailable_engine_owned(feature_name: str) -> ComputeFn:
    """Fail-closed compute for registry slots whose formulas are named in
    §3.12 but defined in a later engine chapter (E02/E03) — no guessed
    formula is ever computed."""

    def _fn(window, params, context):
        g = _guard(window)
        if g:
            return None, 0.0, g[0], g[1]
        return None, 0.0, "UNAVAILABLE", f"FORMULA_OWNER_ENGINE_CHAPTER_{feature_name}"

    return _fn


def _f31_theta_maxage(window, params, context):
    """theta_maxAge — PRUNE threshold: 100 bars (§2.1 state machine:
    'PRUNED (older than theta_maxAge, 100 bars)')."""
    g = _guard(window)
    if g:
        return None, 0.0, g[0], g[1]
    return Decimal(100), 1.0, "OK", ""


def _f32_return_k(window, params, context):
    """return_k = (C_t / C_{t−k}) − 1 for k=1,5,20 (§2.2, 10 digits).
    C_{t−k}=0 → DEGRADED with Q_formula_valid=0 (never silent)."""
    if len(window) < 21:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    obs = window[-1]
    if obs.status != "CLOSED":
        return None, 0.0, "CANDIDATE", "NOT_CLOSED_CANDLE"
    out: Dict[str, Decimal] = {}
    for k in (1, 5, 20):
        base = window[-1 - k].close
        if base == 0:
            return None, 0.0, "DEGRADED", "CLOSE_T_MINUS_K_ZERO_Q2"
        out[f"k{k}"] = m.quantize((obs.close / base) - Decimal(1), 10)
    return out, 1.0, "OK", ""


def _f33_normalized_range(window, params, context):
    """(H−L)/max(ATR_14, ε_range), 4 digits (§2.2)."""
    n = int(params.get("atr_period", 14))
    g = _guard(window)
    if g:
        return None, 0.0, g[0], g[1]
    if len(window) < n + 1:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    atr = m.atr_simple(window, n)
    if atr is None:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    value = (window[-1].high - window[-1].low) / m._guard(atr, _EPS_RANGE)
    return m.quantize(value, 4), 1.0, "OK", ""


def _f34_range_z(window, params, context):
    n = int(params.get("sma_period", 20))
    if len(window) < n:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    ranges = [o.high - o.low for o in window]
    value = m.zscore(ranges, n)
    return m.quantize(value, 4), 1.0, "OK", ""


def _f35_slope(window, params, context):
    n = int(params.get("sma_period", 20))
    if len(window) < n:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    value = m.slope_ols([o.close for o in window], n)
    return m.quantize(value, 10), 1.0, "OK", ""


def _f36_hurst(window, params, context):
    value = m.hurst_rs([o.close for o in window])
    if value is None:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    return m.quantize(value, 4), 1.0, "OK", ""


def _f37_parkinson(window, params, context):
    value = m.parkinson(window)
    if value is None:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    return m.quantize(value, 10), 1.0, "OK", ""


def _f38_garman_klass(window, params, context):
    value = m.garman_klass(window)
    if value is None:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    return m.quantize(value, 10), 1.0, "OK", ""


def _f39_rogers_satchell(window, params, context):
    value = m.rogers_satchell(window)
    if value is None:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    return m.quantize(value, 10), 1.0, "OK", ""


def _f40_garch(window, params, context):
    """GARCH(1,1): parameters (ω, α, β) are not defined in CP-1's assigned
    text → fail-closed UNAVAILABLE (no invented parameterization)."""
    g = _guard(window)
    if g:
        return None, 0.0, g[0], g[1]
    return None, 0.0, "UNAVAILABLE", "GARCH_PARAMETERS_NOT_IN_CP1_TEXT"


def _f41_volume_ratio(window, params, context):
    """§2.2 exact: V / max(SMA_20(V) on t−1, ε_volume), 8 digits.
    SMA on bar t−1 (no future leak); SMA=0 → large-but-finite via floor."""
    n = int(params.get("sma_period", 20))
    if len(window) < n + 1:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    obs = window[-1]
    if obs.status != "CLOSED":
        return None, 0.0, "CANDIDATE", "NOT_CLOSED_CANDLE"
    if obs.volume is None:
        return None, 0.0, "MISSING", "VOLUME_MISSING_QX"
    sma_prev = m.sma([o.volume for o in window[:-1]], n)
    if sma_prev is None:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    if sma_prev == 0:
        return None, 0.0, "DEGRADED", "SMA_VOLUME_ZERO_Q2"
    eps_volume = _TIER1  # Tier-1 floor on the Decimal path (§2.2)
    value = obs.volume / m._guard(sma_prev, eps_volume)
    return m.quantize(value, 8), 1.0, "OK", ""


# ---------------------------------------------------------------------------
# Compute table (alias → function)
# ---------------------------------------------------------------------------

COMPUTERS: Dict[str, ComputeFn] = {
    "body_ratio": _f01_body_ratio,
    "upper_wick_ratio": _f02_upper_wick,
    "lower_wick_ratio": _f03_lower_wick,
    "close_position": _f04_close_position,
    "range": _f05_range,
    "body_size": _f06_body_size,
    "is_bullish": _f07_is_bullish,
    "is_bearish": _f08_is_bearish,
    "TR_t": _f09_tr,
    "ATR_t": _f10_atr_t,
    "ATR": _f11_atr,
    "SMA": _f12_sma,
    "EMA": _f13_ema,
    "RMA": _f14_rma,
    "Wilder": _f15_wilder,
    "VWAP": _f16_vwap,
    "OBV": _f17_obv,
    "RSI": _f18_rsi,
    "VolumeZ": _f19_volume_z,
    "VolRatio": _f20_vol_ratio,
    "OI_z": _f21_oi_z,
    "k_disp": _unavailable_engine_owned("K_DISP"),
    "k_eq": _unavailable_engine_owned("K_EQ"),
    "k_minW": _unavailable_engine_owned("K_MINW"),
    "k_sweep": _unavailable_engine_owned("K_SWEEP"),
    "theta_disp": _unavailable_engine_owned("THETA_DISP"),
    "theta_eq": _unavailable_engine_owned("THETA_EQ"),
    "theta_minW": _unavailable_engine_owned("THETA_MINW"),
    "theta_sweep": _unavailable_engine_owned("THETA_SWEEP"),
    "theta_depth": _unavailable_engine_owned("THETA_DEPTH"),
    "theta_maxAge": _f31_theta_maxage,
    "return_k": _f32_return_k,
    "normalized_range": _f33_normalized_range,
    "RangeZ": _f34_range_z,
    "Slope": _f35_slope,
    "Hurst": _f36_hurst,
    "Parkinson": _f37_parkinson,
    "Garman-Klass": _f38_garman_klass,
    "Rogers-Satchell": _f39_rogers_satchell,
    "GARCH": _f40_garch,
    "volume_ratio": _f41_volume_ratio,
    "theta_body": _unavailable_engine_owned("THETA_BODY"),
    "theta_vol": _unavailable_engine_owned("THETA_VOL"),
    "theta_invalid": _unavailable_engine_owned("THETA_INVALID"),
}

# (num, alias, full_id) — exact §3.12 identifiers (naming integrity, P20).
ATOM_ENTRIES = [
    (1, "body_ratio", "APEX.L00.ATOM.CNDL.BODY_RATIO.RATIO.V1"),
    (2, "upper_wick_ratio", "APEX.L00.ATOM.CNDL.UPPER_WICK_R.RATIO.V1"),
    (3, "lower_wick_ratio", "APEX.L00.ATOM.CNDL.LOWER_WICK_R.RATIO.V1"),
    (4, "close_position", "APEX.L00.ATOM.CNDL.CLOSE_POSITI.RATIO.V1"),
    (5, "range", "APEX.L00.ATOM.CNDL.RANGE.RATIO.V1"),
    (6, "body_size", "APEX.L00.ATOM.CNDL.BODY_SIZE.RATIO.V1"),
    (7, "is_bullish", "APEX.L00.ATOM.CNDL.IS_BULLISH.RATIO.V1"),
    (8, "is_bearish", "APEX.L00.ATOM.CNDL.IS_BEARISH.RATIO.V1"),
    (9, "TR_t", "APEX.L00.ATOM.CNDL.TR_T.RATIO.V1"),
    (10, "ATR_t", "APEX.L00.ATOM.CNDL.ATR_T.RATIO.V1"),
    (11, "ATR", "APEX.L00.ATOM.CNDL.ATR.RATIO.V1"),
    (12, "SMA", "APEX.L00.ATOM.CNDL.SMA.RATIO.V1"),
    (13, "EMA", "APEX.L00.ATOM.CNDL.EMA.RATIO.V1"),
    (14, "RMA", "APEX.L00.ATOM.CNDL.RMA.RATIO.V1"),
    (15, "Wilder", "APEX.L00.ATOM.CNDL.WILDER.RATIO.V1"),
    (16, "VWAP", "APEX.L00.ATOM.CNDL.VWAP.RATIO.V1"),
    (17, "OBV", "APEX.L00.ATOM.CNDL.OBV.RATIO.V1"),
    (18, "RSI", "APEX.L00.ATOM.CNDL.RSI.RATIO.V1"),
    (19, "VolumeZ", "APEX.L00.ATOM.CNDL.VOLUMEZ.RATIO.V1"),
    (20, "VolRatio", "APEX.L00.ATOM.CNDL.VOLRATIO.RATIO.V1"),
    (21, "OI_z", "APEX.L00.ATOM.CNDL.OI_Z.RATIO.V1"),
    (22, "k_disp", "APEX.L00.ATOM.CNDL.K_DISP.RATIO.V1"),
    (23, "k_eq", "APEX.L00.ATOM.CNDL.K_EQ.RATIO.V1"),
    (24, "k_minW", "APEX.L00.ATOM.CNDL.K_MINW.RATIO.V1"),
    (25, "k_sweep", "APEX.L00.ATOM.CNDL.K_SWEEP.RATIO.V1"),
    (26, "theta_disp", "APEX.L00.ATOM.CNDL.THETA_DISP.RATIO.V1"),
    (27, "theta_eq", "APEX.L00.ATOM.CNDL.THETA_EQ.RATIO.V1"),
    (28, "theta_minW", "APEX.L00.ATOM.CNDL.THETA_MINW.RATIO.V1"),
    (29, "theta_sweep", "APEX.L00.ATOM.CNDL.THETA_SWEEP.RATIO.V1"),
    (30, "theta_depth", "APEX.L00.ATOM.CNDL.THETA_DEPTH.RATIO.V1"),
    (31, "theta_maxAge", "APEX.L00.ATOM.CNDL.THETA_MAXAGE.RATIO.V1"),
    (32, "return_k", "APEX.L00.ATOM.CNDL.RETURN_K.RATIO.V1"),
    (33, "normalized_range", "APEX.L00.ATOM.CNDL.NORMALIZED_R.RATIO.V1"),
    (34, "RangeZ", "APEX.L00.ATOM.CNDL.RANGEZ.RATIO.V1"),
    (35, "Slope", "APEX.L00.ATOM.CNDL.SLOPE.RATIO.V1"),
    (36, "Hurst", "APEX.L00.ATOM.CNDL.HURST.RATIO.V1"),
    (37, "Parkinson", "APEX.L00.ATOM.CNDL.PARKINSON.RATIO.V1"),
    (38, "Garman-Klass", "APEX.L00.ATOM.CNDL.GARMAN-KLASS.RATIO.V1"),
    (39, "Rogers-Satchell", "APEX.L00.ATOM.CNDL.ROGERS-SATCH.RATIO.V1"),
    (40, "GARCH", "APEX.L00.ATOM.CNDL.GARCH.RATIO.V1"),
    (41, "volume_ratio", "APEX.L00.ATOM.CNDL.VOLUME_RATIO.RATIO.V1"),
    (42, "theta_body", "APEX.L00.ATOM.CNDL.THETA_BODY.RATIO.V1"),
    (43, "theta_vol", "APEX.L00.ATOM.CNDL.THETA_VOL.RATIO.V1"),
    (44, "theta_invalid", "APEX.L00.ATOM.CNDL.THETA_INVALI.RATIO.V1"),
]

assert len(ATOM_ENTRIES) == 44
assert set(COMPUTERS) == {alias for _, alias, _ in ATOM_ENTRIES}
