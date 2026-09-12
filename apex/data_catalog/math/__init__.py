"""APEX_GEN5 data-catalog math tier (§3.12 module layout: `math/`).

Shared deterministic indicator math for the ATOM/MOLECULAR feature tiers.
All functions are pure Decimal-path computations on canonical OHLCV/OI
history. Guard discipline: denominators are floored (division guards,
§2.2); NaN/Inf never return silently — callers set Q_formula_valid=0.
"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Sequence, Tuple

from apex.data_catalog.contracts import MarketObservation

# Frozen defaults (mirrored in params/quality_weights_v1.yaml; callers pass
# them in — this module never imports params, keeping math pure).
SMA_N = 20          # §2.2 volume_ratio: SMA_n, n=20
ATR_N = 14          # §2.2 normalized_range: ATR_n over 14 bars
RSI_N = 14          # standard Wilder RSI period

_EPS = Decimal("1e-12")  # Tier-1 floor (division guards)


def _d(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _guard(denominator: Decimal, eps: Decimal = _EPS) -> Decimal:
    """Division guard: max(|denominator|, eps) preserves sign; never 0."""
    return denominator if abs(denominator) >= eps else (
        eps if denominator >= 0 else -eps
    )


def sma(values: Sequence[Decimal], n: int) -> Optional[Decimal]:
    if len(values) < n:
        return None
    total = sum(values[-n:], Decimal(0))
    return total / Decimal(n)


def ema(values: Sequence[Decimal], n: int) -> Optional[Decimal]:
    if len(values) < n:
        return None
    alpha = Decimal(2) / Decimal(n + 1)
    seed = sum(values[:n], Decimal(0)) / Decimal(n)
    result = seed
    for v in values[n:]:
        result = alpha * _d(v) + (Decimal(1) - alpha) * result
    return result


def rma(values: Sequence[Decimal], n: int) -> Optional[Decimal]:
    """Wilder's Running Moving Average (RMA): x + (prev−x)/n."""
    if len(values) < n:
        return None
    result = sum(values[:n], Decimal(0)) / Decimal(n)
    for v in values[n:]:
        result = (result * Decimal(n - 1) + _d(v)) / Decimal(n)
    return result


def true_range(obs: MarketObservation,
               prev_close: Optional[Decimal]) -> Optional[Decimal]:
    """TR_t = max(H−L, |H−C_prev|, |L−C_prev|). Needs the previous close."""
    if prev_close is None:
        return None
    hl = obs.high - obs.low
    hc = abs(obs.high - prev_close)
    lc = abs(obs.low - prev_close)
    return max(hl, hc, lc)


def atr_simple(window: Sequence[MarketObservation], n: int = ATR_N) -> Optional[Decimal]:
    """ATR_n = simple mean of TR over n bars (§2.2 'ATR_n over 14 bars')."""
    if len(window) < n + 1:
        return None
    trs: List[Decimal] = []
    for i, obs in enumerate(window[1:], start=1):
        tr = true_range(obs, window[i - 1].close)
        if tr is None:
            return None
        trs.append(tr)
    if len(trs) < n:
        return None
    return sum(trs[-n:], Decimal(0)) / Decimal(n)


def atr_wilder(window: Sequence[MarketObservation], n: int = ATR_N) -> Optional[Decimal]:
    """Wilder-smoothed ATR: ATR_t = (ATR_{t−1}·(n−1) + TR_t)/n,
    seeded by the simple mean of the first n TRs."""
    if len(window) < n + 1:
        return None
    trs: List[Decimal] = []
    for i, obs in enumerate(window[1:], start=1):
        tr = true_range(obs, window[i - 1].close)
        if tr is None:
            return None
        trs.append(tr)
    if len(trs) < n:
        return None
    result = sum(trs[:n], Decimal(0)) / Decimal(n)
    for tr in trs[n:]:
        result = (result * Decimal(n - 1) + tr) / Decimal(n)
    return result


def vwap(window: Sequence[MarketObservation]) -> Optional[Decimal]:
    """Rolling VWAP over the supplied window:
    Σ(typical_price·V) / ΣV (guard: ΣV < ε → None ⇒ degraded)."""
    if not window:
        return None
    pv = Decimal(0)
    vv = Decimal(0)
    for obs in window:
        typical = (obs.high + obs.low + obs.close) / Decimal(3)
        pv += typical * obs.volume
        vv += obs.volume
    if abs(vv) < _EPS:
        return None
    return pv / vv


def obv_series(window: Sequence[MarketObservation]) -> Optional[Decimal]:
    """On-Balance Volume at the last bar of the window."""
    if not window:
        return None
    result = Decimal(0)
    prev = None
    for obs in window:
        if prev is not None:
            if obs.close > prev.close:
                result += obs.volume
            elif obs.close < prev.close:
                result -= obs.volume
        prev = obs.close
    return result


def rsi_wilder(closes: Sequence[Decimal], n: int = RSI_N) -> Optional[Decimal]:
    """Wilder RSI over n periods. 100 − 100/(1+RS); flat series → 100."""
    if len(closes) < n + 1:
        return None
    gains: List[Decimal] = []
    losses: List[Decimal] = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(diff if diff > 0 else Decimal(0))
        losses.append(-diff if diff < 0 else Decimal(0))
    if len(gains) < n:
        return None
    avg_gain = sum(gains[:n], Decimal(0)) / Decimal(n)
    avg_loss = sum(losses[:n], Decimal(0)) / Decimal(n)
    for i in range(n, len(gains)):
        avg_gain = (avg_gain * Decimal(n - 1) + gains[i]) / Decimal(n)
        avg_loss = (avg_loss * Decimal(n - 1) + losses[i]) / Decimal(n)
    if avg_loss == 0:
        return Decimal(100)
    rs = avg_gain / avg_loss
    return Decimal(100) - (Decimal(100) / (Decimal(1) + rs))


def zscore(values: Sequence[Decimal], n: int) -> Optional[Decimal]:
    """(last − SMA_n) / σ_n (population). σ < ε → 0 (flat series)."""
    if len(values) < n:
        return None
    recent = values[-n:]
    mean = sum(recent, Decimal(0)) / Decimal(n)
    var = sum((v - mean) ** 2 for v in recent) / Decimal(n)
    sigma = var.sqrt()
    last = values[-1]
    if sigma < _EPS:
        return Decimal(0)
    return (last - mean) / sigma


def slope_ols(values: Sequence[Decimal], n: int) -> Optional[Decimal]:
    """Least-squares slope of the last n values (x = 0..n−1)."""
    if len(values) < n:
        return None
    recent = values[-n:]
    x_mean = Decimal(n - 1) / Decimal(2)
    y_mean = sum(recent, Decimal(0)) / Decimal(n)
    num = Decimal(0)
    den = Decimal(0)
    for x, y in enumerate(recent):
        num += (Decimal(x) - x_mean) * (y - y_mean)
        den += (Decimal(x) - x_mean) ** 2
    if abs(den) < _EPS:
        return Decimal(0)
    return num / den


def hurst_rs(values: Sequence[Decimal]) -> Optional[Decimal]:
    """Hurst exponent via R/S analysis on log-price deviations.

    Lags from 8 to min(len//2, 32); slope of log(R/S) over log(lag).
    Insufficient data (fewer than 24 points) → None (degraded, no guess).
    """
    if len(values) < 24:
        return None
    prices = [float(v) for v in values]
    logs = [math.log(max(p, 1e-300)) for p in prices]
    lags = range(8, min(len(logs) // 2, 32) + 1)
    xs: List[float] = []
    ys: List[float] = []
    for lag in lags:
        rs_values: List[float] = []
        for start in range(0, len(logs) - lag, lag):
            segment = logs[start:start + lag]
            mean = sum(segment) / len(segment)
            dev = [x - mean for x in segment]
            cum = []
            total = 0.0
            for d in dev:
                total += d
                cum.append(total)
            r = max(cum) - min(cum)
            if r <= 0:
                continue
            var = sum(d * d for d in dev) / len(dev)
            s = math.sqrt(max(var, 1e-300))
            rs_values.append(r / s)
        if not rs_values:
            continue
        rs_mean = sum(rs_values) / len(rs_values)
        if rs_mean <= 0:
            continue
        xs.append(math.log(lag))
        ys.append(math.log(rs_mean))
    if len(xs) < 3:
        return None
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den = sum((x - x_mean) ** 2 for x in xs)
    if den == 0:
        return None
    return Decimal(str(num / den))


def parkinson(window: Sequence[MarketObservation]) -> Optional[Decimal]:
    """σ = sqrt( (1/(4·n·ln2)) · Σ ln(H/L)² ) over the window."""
    if len(window) < 2:
        return None
    n = len(window)
    total = Decimal(0)
    for obs in window:
        if obs.low <= 0 or obs.high <= 0:
            return None
        hl = float(obs.high / obs.low)
        total += Decimal(str(math.log(hl) ** 2))
    factor = Decimal(1) / (Decimal(4) * Decimal(n) * Decimal(str(math.log(2))))
    return (factor * total).sqrt()


def garman_klass(window: Sequence[MarketObservation]) -> Optional[Decimal]:
    """σ² = (1/n)·Σ [0.5·ln(H/L)² − (2ln2−1)·ln(C/O)²]."""
    if len(window) < 2:
        return None
    n = len(window)
    c1 = Decimal(str(math.log(2))) * Decimal(2) - Decimal(1)
    total = Decimal(0)
    for obs in window:
        if min(obs.high, obs.low, obs.open, obs.close) <= 0:
            return None
        a = math.log(float(obs.high / obs.low)) ** 2
        b = math.log(float(obs.close / obs.open)) ** 2
        total += Decimal("0.5") * Decimal(str(a)) - c1 * Decimal(str(b))
    variance = total / Decimal(n)
    if variance < 0:
        return None
    return variance.sqrt()


def rogers_satchell(window: Sequence[MarketObservation]) -> Optional[Decimal]:
    """σ² = (1/n)·Σ [ln(H/C)·ln(H/O) + ln(L/C)·ln(L/O)]."""
    if len(window) < 2:
        return None
    n = len(window)
    total = Decimal(0)
    for obs in window:
        if min(obs.high, obs.low, obs.open, obs.close) <= 0:
            return None
        term = (
            math.log(float(obs.high / obs.close))
            * math.log(float(obs.high / obs.open))
            + math.log(float(obs.low / obs.close))
            * math.log(float(obs.low / obs.open))
        )
        total += Decimal(str(term))
    variance = total / Decimal(n)
    if variance < 0:
        return None
    return variance.sqrt()


def quantize(value: Decimal, digits: int) -> Decimal:
    """ROUND_HALF_UP quantization to `digits` decimal places (§2.2)."""
    quantum = Decimal(1).scaleb(-digits)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)
