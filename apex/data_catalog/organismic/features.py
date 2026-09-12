"""APEX_GEN5 ORGANISMIC (Context) feature tier — features 45–73 of the
74-feature registry (§3.12). 50-candle lookback (49 warmup), validity
50–500 candles, exponential decay exp(-0.02*age), confidence scaled by
regime confidence (0.85*Q_formula_valid*regime_confidence).

Context inputs: these features take canonical OHLCV+OI plus
regime_state / temporal_window / MTF state (L2 evidence for some). At CP-1
the context fabric and E12 temporal windows are not built yet (CP-5/CP-6),
so context-gated features return status UNAVAILABLE with a deterministic
reason — the AI.6 missing-data permission model applied literally (missing
context never grants permission; nothing is synthesized). OI-dependent
features return MISSING/UNAVAILABLE when OI is absent (T-DC-004/T-OM-002:
OI is NEVER substituted with 0).

- F49 `funding_rate` is REMOVED / OUT-OF-CONTRACT (§3.12): the slot is
  registered (absent-by-design) and every lookup returns UNAVAILABLE.
- F56 `market_profile` is a Wave-Out item (§9.5-9): ALWAYS UNAVAILABLE.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

from apex.data_catalog.contracts import MarketObservation, parse_utc_ms

ComputeFn = Callable[
    [List[MarketObservation], Dict[str, Any], Dict[str, Any]],
    Tuple[Optional[Any], float, str, str],
]


def _base_guard(window: List[MarketObservation]) -> Optional[Tuple[str, str]]:
    if not window:
        return "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    obs = window[-1]
    if obs.status != "CLOSED":
        return "CANDIDATE", "NOT_CLOSED_CANDLE"
    if obs.high < obs.low:
        return "INVALID", "H_LT_L_QX"
    return None


def _context_gated(requirement: str) -> ComputeFn:
    """Fail-closed compute for features requiring context state that a
    later stage owns (regime fabric CP-6, E12 temporal windows CP-5,
    L2/order-flow data — never synthesized at Layer-1)."""

    def _fn(window, params, context):
        g = _base_guard(window)
        if g:
            return None, 0.0, g[0], g[1]
        present = context.get(requirement)
        if present is None:
            return None, 0.0, "UNAVAILABLE", f"CONTEXT_{requirement}_NOT_BUILT"
        return None, 0.0, "UNAVAILABLE", f"CONTEXT_{requirement}_NOT_BUILT"

    return _fn


def _removed(feature: str) -> ComputeFn:
    def _fn(window, params, context):
        return None, 0.0, "UNAVAILABLE", f"REMOVED_OUT_OF_CONTRACT_{feature}"

    return _fn


def _f45_open_interest_delta(window, params, context):
    """OI_t − OI_{t−1}. OI missing → MISSING (never 0)."""
    g = _base_guard(window)
    if g:
        return None, 0.0, g[0], g[1]
    if len(window) < 2:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    cur, prev = window[-1].oi, window[-2].oi
    if cur is None or prev is None:
        return None, 0.0, "MISSING", "OI_MISSING_QX"
    from apex.data_catalog.math import quantize
    return quantize(cur - prev, 8), 1.0, "OK", ""


def _f68_time_of_day(window, params, context):
    """UTC hour of the candle timestamp (0..23)."""
    g = _base_guard(window)
    if g:
        return None, 0.0, g[0], g[1]
    try:
        ts = parse_utc_ms(window[-1].timestamp)
    except ValueError:
        return None, 0.0, "INVALID", "INVALID_UTC_TIMESTAMP"
    return Decimal(ts.hour), 1.0, "OK", ""


def _f69_day_of_week(window, params, context):
    """ISO weekday of the candle timestamp (1=Mon .. 7=Sun)."""
    g = _base_guard(window)
    if g:
        return None, 0.0, g[0], g[1]
    try:
        ts = parse_utc_ms(window[-1].timestamp)
    except ValueError:
        return None, 0.0, "INVALID", "INVALID_UTC_TIMESTAMP"
    return Decimal(ts.isoweekday()), 1.0, "OK", ""


COMPUTERS: Dict[str, ComputeFn] = {
    "open_interest_delta": _f45_open_interest_delta,
    "taker_buy_volume": _context_gated("L2_ORDER_FLOW"),
    "taker_sell_volume": _context_gated("L2_ORDER_FLOW"),
    "funding_rate": _removed("F49"),
    "liquidation_volume": _context_gated("L2_ORDER_FLOW"),
    "bid_ask_spread": _context_gated("L2_ORDER_BOOK"),
    "order_book_imbalance": _context_gated("L2_ORDER_BOOK"),
    "cvd": _context_gated("L2_ORDER_FLOW"),
    "delta": _context_gated("L2_ORDER_FLOW"),
    "footprint": _context_gated("L2_ORDER_FLOW"),
    "volume_profile": _context_gated("E03_VOLUME_PROFILE"),
    "market_profile": _removed("WAVE_OUT"),
    "temporal_window_high": _context_gated("E12_TEMPORAL_WINDOW"),
    "temporal_window_low": _context_gated("E12_TEMPORAL_WINDOW"),
    "temporal_window_vwap": _context_gated("E12_TEMPORAL_WINDOW"),
    "temporal_window_range": _context_gated("E12_TEMPORAL_WINDOW"),
    "temporal_window_return": _context_gated("E12_TEMPORAL_WINDOW"),
    "htf_trend": _context_gated("E09_HTF_EVIDENCE"),
    "htf_bos": _context_gated("E01_HTF_EVIDENCE"),
    "htf_choch": _context_gated("E01_HTF_EVIDENCE"),
    "htf_fvg": _context_gated("E05_HTF_EVIDENCE"),
    "htf_ob": _context_gated("E06_HTF_EVIDENCE"),
    "htf_liquidity": _context_gated("E02_HTF_EVIDENCE"),
    "time_of_day": _f68_time_of_day,
    "day_of_week": _f69_day_of_week,
    "temporal_window": _context_gated("E12_TEMPORAL_WINDOW"),
    "utc_activity_window": _context_gated("E12_TEMPORAL_WINDOW"),
    "news_event": _context_gated("NEWS_FEED"),
    "volatility_regime": _context_gated("E11_REGIME"),
}

# (num, alias, full_id, status-note)
ORGN_ENTRIES = [
    (45, "open_interest_delta", "APEX.L00.ORGN.CTXT.OPEN_INTERES.SCORE.V1", "ACTIVE"),
    (46, "taker_buy_volume", "APEX.L00.ORGN.CTXT.TAKER_BUY_VO.SCORE.V1", "ACTIVE"),
    (47, "taker_sell_volume", "APEX.L00.ORGN.CTXT.TAKER_SELL_V.SCORE.V1", "ACTIVE"),
    (48, "liquidation_volume", "APEX.L00.ORGN.CTXT.LIQUIDATION_.SCORE.V1", "ACTIVE"),
    (49, "funding_rate", "APEX.L00.ORGN.CTXT.FUNDING_RATE.SCORE.V1", "REMOVED"),
    (50, "bid_ask_spread", "APEX.L00.ORGN.CTXT.BID_ASK_SPRE.SCORE.V1", "ACTIVE"),
    (51, "order_book_imbalance", "APEX.L00.ORGN.CTXT.ORDER_BOOK_I.SCORE.V1", "ACTIVE"),
    (52, "cvd", "APEX.L00.ORGN.CTXT.CVD.SCORE.V1", "ACTIVE"),
    (53, "delta", "APEX.L00.ORGN.CTXT.DELTA.SCORE.V1", "ACTIVE"),
    (54, "footprint", "APEX.L00.ORGN.CTXT.FOOTPRINT.SCORE.V1", "ACTIVE"),
    (55, "volume_profile", "APEX.L00.ORGN.CTXT.VOLUME_PROFI.SCORE.V1", "ACTIVE"),
    (56, "market_profile", "APEX.L00.ORGN.CTXT.MARKET_PROFI.SCORE.V1", "WAVE_OUT"),
    (57, "temporal_window_high", "APEX.L00.ORGN.CTXT.UTC_ACTIVITY_WINDOW_HIGH.SCORE.V1", "ACTIVE"),
    (58, "temporal_window_low", "APEX.L00.ORGN.CTXT.UTC_ACTIVITY_WINDOW_LOW.SCORE.V1", "ACTIVE"),
    (59, "temporal_window_vwap", "APEX.L00.ORGN.CTXT.UTC_ACTIVITY_WINDOW_VWAP.SCORE.V1", "ACTIVE"),
    (60, "temporal_window_range", "APEX.L00.ORGN.CTXT.UTC_ACTIVITY_WINDOW_RANG.SCORE.V1", "ACTIVE"),
    (61, "temporal_window_return", "APEX.L00.ORGN.CTXT.UTC_ACTIVITY_WINDOW_RETU.SCORE.V1", "ACTIVE"),
    (62, "htf_trend", "APEX.L00.ORGN.CTXT.HTF_TREND.SCORE.V1", "ACTIVE"),
    (63, "htf_bos", "APEX.L00.ORGN.CTXT.HTF_BOS.SCORE.V1", "ACTIVE"),
    (64, "htf_choch", "APEX.L00.ORGN.CTXT.HTF_CHOCH.SCORE.V1", "ACTIVE"),
    (65, "htf_fvg", "APEX.L00.ORGN.CTXT.HTF_FVG.SCORE.V1", "ACTIVE"),
    (66, "htf_ob", "APEX.L00.ORGN.CTXT.HTF_OB.SCORE.V1", "ACTIVE"),
    (67, "htf_liquidity", "APEX.L00.ORGN.CTXT.HTF_LIQUIDIT.SCORE.V1", "ACTIVE"),
    (68, "time_of_day", "APEX.L00.ORGN.CTXT.TIME_OF_DAY.SCORE.V1", "ACTIVE"),
    (69, "day_of_week", "APEX.L00.ORGN.CTXT.DAY_OF_WEEK.SCORE.V1", "ACTIVE"),
    (70, "temporal_window", "APEX.L00.ORGN.CTXT.UTC_ACTIVITY_WINDOW.SCORE.V1", "ACTIVE"),
    (71, "utc_activity_window", "APEX.L00.ORGN.CTXT.UTC_ACTIVITY_WINDOW.SCORE.V1", "ACTIVE"),
    (72, "news_event", "APEX.L00.ORGN.CTXT.NEWS_EVENT.SCORE.V1", "ACTIVE"),
    (73, "volatility_regime", "APEX.L00.ORGN.CTXT.VOLATILITY_R.SCORE.V1", "ACTIVE"),
]

assert len(ORGN_ENTRIES) == 29  # 45..73 inclusive (slot 49 included)
assert set(COMPUTERS) == {alias for _, alias, _, _ in ORGN_ENTRIES}
