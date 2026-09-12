"""APEX_GEN5 E04 — VOLATILITY ENGINE (v4.0.0).

Blueprint: APEX_GEN5.md L4955–5601 (chapter order §0→§10 mirrored here:
§3 formulas → §4 algorithms → §5 objects/state/events → §6 params →
§7 encyclopedic algorithmic notes → §8 validation hooks).

Mission (§1.1): precise, neutral, PIT-safe measurement of volatility
level, regime, behavior and distribution. E04 NEVER produces a Buy/Sell
signal (non-directional by contract; §1.4) — it emits Context consumed by
other engines: E03 takes the ATR scalar (I_Volatility_v4 mirror of the
Phase-80 I_Volume_v4 pattern, CP-2 handoff cross-engine note), E01 takes
BOS context exchange for EV_VLT_005 (§1.3), E11 takes
VolatilityState.regime only (§1.3).

Two-tier epsilon (G11/§2.2): arithmetic EPS = 1e-12 (frozen §2.2 table,
apex.quality.numerical.eps_for_engine("E04")); published ATR is floored
at the ATR floor 1e-8.

Wave-Out (§9.5-9/G6): adaptive ATR E04↔E11 is NOT implemented — any
adaptive-period request raises WaveOutError("adaptive_atr_e04_e11").
"""

from __future__ import annotations

import math
from collections import deque
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

# --------------------------------------------------------------------------
# §3/§4 constants — EPS per Global Contracts §2.2 (E04 operational EPS,
# frozen Tier-2 table). The blueprint §4 reference block opens with
# `EPS=1e-12`; we consume the frozen table value instead of hardcoding.
# --------------------------------------------------------------------------
EPS = float(eps_for_engine("E04"))          # 1e-12 (§2.2 E04 row)
ATR_FLOOR = 1e-8                            # §2.2 ATR floor (G11)

ENGINE = "E04_Volatility"
CONTRACT_VERSION = "4.0.0"
CONTRACT_LABEL = "APEX-Contract-Volatility v4.0.0"
ANALYST_VERSION = "4.0.0+" + "0" * 40      # SemVer + git40 (owner stamps)

REGIMES = ("VERY_LOW", "LOW", "NORMAL", "ELEVATED", "EXTREME")
REGIME_ORDER = {name: i for i, name in enumerate(REGIMES)}

# §3.12 / §6 k targeting jump table (Risk Committee)
K_TARGETING = {"VERY_LOW": 1.5, "LOW": 1.8, "NORMAL": 2.0,
               "ELEVATED": 2.5, "EXTREME": 3.0}

# §9.5-8 universality: 14 frozen timeframes (8h ✓, no 3d — Round-2 decree)
TF_SECONDS: Dict[str, int] = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "8h": 28800,
    "12h": 43200, "1d": 86400, "1w": 604800, "1mo": 2592000,
}


# --------------------------------------------------------------------------
# §6 Parameters — Full Table with Governance (frozen in-package defaults,
# ISSUE-CP2-006 six-YAML law; blueprint literals, no runtime retuning).
# --------------------------------------------------------------------------
E04_DEFAULTS: Dict[str, Any] = {
    "atr_short": 14,            # §6 Wilder classic
    "atr_long": 50,             # §6 governed
    "hv_window": 30,            # §6 governed
    "boll_period": 20,          # §6 governed
    "boll_k": 2.0,              # §6 Fixed
    "squeeze_vr": 0.75,         # §6 θ_sq
    "squeeze_bw": 0.12,         # §6 θ_sq,w
    "squeeze_rz": -0.5,         # §3.8 RangeZ bound of the squeeze state
    "hyst_enter_vr": 0.70,      # §7 Ch.1-12/Ch.3-12 hysteresis enter
    "hyst_enter_bw": 0.12,      # §7 Ch.3-12 enter BW bound
    "hyst_enter_bars": 3,       # §5 EV_VLT_003 sustained 3 bars
    "hyst_exit_vr": 0.80,       # §7 hysteresis exit
    "hyst_exit_bw": 0.15,       # §7 Ch.3-12 exit BW bound
    "extreme_z": 3.5,           # §6 EV_VLT_008
    "expansion_z": 3.0,         # §5 EV_VLT_005 RangeZ>3
    "compression_vr": 0.6,      # §5 EV_VLT_006
    "compression_bw": 0.12,     # §5 EV_VLT_006
    "compression_rz": -1.5,     # §5 EV_VLT_006
    "regime_window_days": 180,  # §6 (4320 1H bars, §3.9)
    "regime_quantiles": (15, 35, 75, 95),   # §3.9
    "cluster_window": 200,      # §6 governed
    "cluster_p_thr": 0.65,      # §5 EV_VLT_007
    "cluster_span_bars": 50,    # §5 EV_VLT_007 "over 50 bars"
    "ewma_lambda": 0.94,        # §6 RiskMetrics convention
    "k_targeting": dict(K_TARGETING),       # §6 Risk Committee
    "winsorize_tr_mult": 10,    # §6 MAD-based
    "epsilon": EPS,             # §6 (§2.2 E04 operational EPS)
    "ljung_m": 20,              # §6 Box convention
    "range_z_window": 20,       # §2 RangeZ rolling window n
    "annualization_days": 365,  # §3.2 crypto
    "min_bars": 50,             # warmup floor (CP-2 parity; §8.2 500-bar
                                # replay uses this as the emit gate)
    "garch_min_obs": 100,       # §4 garch_mle_fit insufficient bound
    "nondir_min_obs": 30,       # §4 nondirectional_test bound
    "nondir_corr_thr": 0.08,    # §3.11 |Corr|<0.08 pass bound
    "nondir_p_thr": 0.05,       # §3.11 p>0.05 pass bound
    "drift_consec_days": 3,     # §8.8 three consecutive failures
    "gap_atr_mult": 8,          # §7 Ch.1-10 gap > 8×ATR winsorized
    "locked_market_bars": 5,    # §7 Ch.1-10 H=L=O=C, V=0 five bars
}


def get_params(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Frozen defaults + governed overrides (unknown keys rejected)."""
    params = dict(E04_DEFAULTS)
    for key, value in (overrides or {}).items():
        if key not in E04_DEFAULTS:
            raise ValueError(f"UNKNOWN_E04_PARAM_QX:{key}")
        params[key] = value
    return params


# --------------------------------------------------------------------------
# §3.10/§3.11 distribution functions — formula authority is §3 (p = 1−F);
# the §4 reference block's coarse step-function p-values are illustrative
# pseudocode (ISSUE-CP3-003). Implemented with stdlib math only (SBOM law).
# --------------------------------------------------------------------------
def _lower_incomplete_gamma_ratio(a: float, x: float) -> float:
    """Regularized lower incomplete gamma P(a, x) — series / CF."""
    if x < 0:
        raise ValueError("NEGATIVE_CHI2_ARGUMENT_QX")
    if x == 0:
        return 0.0
    if x < a + 1.0:
        # series: P(a,x) = e^-x x^a Σ Γ(a)/Γ(a+k+1) x^k
        ap = a
        s = 1.0 / a
        term = s
        for _ in range(1000):
            ap += 1.0
            term *= x / ap
            s += term
            if abs(term) < abs(s) * 1e-15:
                break
        return s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    # continued fraction for Q(a,x), return 1−Q
    b = x + 1.0 - a
    c = 1e300
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-300:
            d = 1e-300
        c = b + an / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    q = math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
    return 1.0 - q


def chi2_sf(q: float, m: int) -> float:
    """p = 1 − F_χ²(Q; m) — exact §3.10 definition."""
    if q <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - _lower_incomplete_gamma_ratio(m / 2.0,
                                                                  q / 2.0)))


def _betacf(a: float, b: float, x: float) -> float:
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, 1000):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def _regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_bt = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
             + a * math.log(x) + b * math.log(1.0 - x))
    bt = math.exp(ln_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_sf_two_sided(t: float, dof: int) -> float:
    """Two-sided p-value of Student's t (§3.11 t-test)."""
    if dof <= 0:
        return 1.0
    x = dof / (dof + t * t)
    return max(0.0, min(1.0, _regularized_incomplete_beta(dof / 2.0, 0.5, x)))


# --------------------------------------------------------------------------
# §3.1 ATR — Wilder RMA
# --------------------------------------------------------------------------
def true_range(h: float, l: float, c_prev: Optional[float]
               ) -> Tuple[float, str]:
    """TR_t = max(H−L, |H−C_prev|, |L−C_prev|); H<L → (0, Q0) (§3.1)."""
    if h < l - EPS:
        return 0.0, "Q0"
    if c_prev is None or (isinstance(c_prev, float) and math.isnan(c_prev)):
        return max(h - l, 0.0), "Q1"
    return max(h - l, abs(h - c_prev), abs(l - c_prev)), "Q1"


class WilderATR:
    """§3.1 Wilder RMA: seed = mean of first n Q1+ TRs, then
    ATR_t = (ATR_{t−1}(n−1)+TR_t)/n. Q0 freezes ATR (§3.1 edge case)."""

    def __init__(self, n: int = 14):
        self.n = int(n)
        self.tr_buf: deque = deque(maxlen=self.n)
        self.atr: Optional[float] = None

    def update(self, tr: float, qtag: str) -> Tuple[float, str]:
        if qtag == "Q0":
            return (self.atr if self.atr is not None else float("nan")), "Q0"
        self.tr_buf.append(tr)
        if self.atr is None:
            if len(self.tr_buf) < self.n:
                return float("nan"), "Q1"
            self.atr = sum(self.tr_buf) / self.n
            return self.atr, "Q2"
        self.atr = (self.atr * (self.n - 1) + tr) / self.n
        return self.atr, "Q2"


# --------------------------------------------------------------------------
# §3.3 Range estimators with gap correction
# --------------------------------------------------------------------------
def parkinson_raw(highs: Sequence[float], lows: Sequence[float]) -> float:
    n = len(highs)
    s = 0.0
    for h, l in zip(highs, lows):
        if h <= 0 or l <= 0 or h < l:
            continue
        s += math.log(h / l) ** 2
    return math.sqrt(s / (4 * math.log(2) * n)) if n > 0 else float("nan")


def overnight_var(opens: Sequence[float], closes_prev: Sequence[float]) -> float:
    s = 0.0
    cnt = 0
    for o, cp in zip(opens, closes_prev):
        if o <= 0 or cp <= 0:
            continue
        s += math.log(o / cp) ** 2
        cnt += 1
    return s / cnt if cnt > 0 else 0.0


def oc_var(opens: Sequence[float], closes: Sequence[float]) -> float:
    s = 0.0
    cnt = 0
    for o, c in zip(opens, closes):
        if o <= 0 or c <= 0:
            continue
        s += math.log(c / o) ** 2
        cnt += 1
    return s / cnt if cnt > 0 else 0.0


def rogers_satchell(opens: Sequence[float], highs: Sequence[float],
                    lows: Sequence[float], closes: Sequence[float]) -> float:
    s = 0.0
    cnt = 0
    for o, h, l, c in zip(opens, highs, lows, closes):
        if min(o, h, l, c) <= 0:
            continue
        s += (math.log(h / c) * math.log(h / o)
              + math.log(l / c) * math.log(l / o))
        cnt += 1
    return math.sqrt(s / cnt) if cnt > 0 else float("nan")


def garman_klass(opens: Sequence[float], highs: Sequence[float],
                 lows: Sequence[float], closes: Sequence[float]) -> float:
    """§3.3 GK; negative per-bar contributions floored to 0 (§3.3 + §2)."""
    s = 0.0
    cnt = 0
    for o, h, l, c in zip(opens, highs, lows, closes):
        if min(o, h, l, c) <= 0:
            continue
        term = (0.5 * math.log(h / l) ** 2
                - (2 * math.log(2) - 1) * math.log(c / o) ** 2)
        s += max(term, 0.0)
        cnt += 1
    return math.sqrt(max(s / cnt, 0.0)) if cnt > 0 else float("nan")


def yang_zhang(opens: Sequence[float], highs: Sequence[float],
               lows: Sequence[float], closes: Sequence[float],
               closes_prev: Sequence[float]) -> float:
    """§3.3 YZ: σ² = ON² + k·OC² + (1−k)·RS², k=0.34/(1.34+(n+1)/(n−1))."""
    n = len(opens)
    if n < 2:
        return float("nan")
    on = overnight_var(opens, closes_prev)
    oc = oc_var(opens, closes)
    rs = rogers_satchell(opens, highs, lows, closes)
    if math.isnan(rs):
        return float("nan")
    k = 0.34 / (1.34 + (n + 1) / (n - 1))
    var = on + k * oc + (1 - k) * (rs ** 2)
    return math.sqrt(max(var, 0.0))


def parkinson_adjusted(highs: Sequence[float], lows: Sequence[float],
                       opens: Sequence[float],
                       closes_prev: Sequence[float]) -> float:
    """§0(b)/§3.3 adjusted Parkinson: σ² = σ_ON² + σ_P,raw²."""
    on = overnight_var(opens, closes_prev)
    pr = parkinson_raw(highs, lows)
    if math.isnan(pr):
        return float("nan")
    return math.sqrt(on + pr ** 2)


# --------------------------------------------------------------------------
# §3.2 Realized volatility
# --------------------------------------------------------------------------
def realized_var(returns: Sequence[float]) -> float:
    """RV = Σ r² (§3.2)."""
    return sum(r * r for r in returns)


def annualized_hv(rv: float, tf_seconds: int, days: int = 365) -> float:
    """§3.2 HV = sqrt(RV × 365) scaled to the timeframe (crypto 365d)."""
    if rv < 0 or tf_seconds <= 0:
        return float("nan")
    bars_per_year = days * 86400.0 / tf_seconds
    return math.sqrt(rv * bars_per_year)


# --------------------------------------------------------------------------
# §3.4 GARCH(1,1) full MLE (deterministic restart grid; no PRNG — §3.4)
# --------------------------------------------------------------------------
def garch_mle_fit(returns: Sequence[float],
                  min_obs: int = 100) -> Dict[str, Any]:
    n = len(returns)
    if n < min_obs:
        return {"omega": float("nan"), "alpha": float("nan"),
                "beta": float("nan"), "status": "insufficient"}
    mean = sum(returns) / n
    eps = [r - mean for r in returns]
    var = sum(e * e for e in eps) / n
    if var <= 0:
        return {"omega": float("nan"), "alpha": float("nan"),
                "beta": float("nan"), "status": "diverged"}

    def nll(params: Sequence[float]) -> float:
        o, a, b = params
        if o <= 0 or a < 0 or b < 0 or a + b >= 0.999999:
            return 1e12
        sig2 = var
        ll = 0.0
        for i in range(n):
            if i == 0:
                sig2 = o / (1 - a - b) if a + b < 1 else var
            else:
                sig2 = o + a * (eps[i - 1] ** 2) + b * sig2
                sig2 = max(sig2, 1e-12)
            ll += 0.5 * (math.log(2 * math.pi) + math.log(sig2)
                         + eps[i] ** 2 / sig2)
        return ll

    best_ll = 1e18
    best: Optional[List[float]] = None
    starts = [(0.1 * var, 0.1, 0.8), (0.05 * var, 0.15, 0.8),
              (0.2 * var, 0.05, 0.85)]
    omega_grid = [0.01 * var, 0.05 * var, 0.1 * var, 0.2 * var,
                  0.35 * var, 0.5 * var]
    alpha_grid = [0.02, 0.05, 0.1, 0.15, 0.2]
    beta_grid = [0.6, 0.7, 0.8, 0.85, 0.9, 0.92]
    starts.extend((o, a, b) for o in omega_grid for a in alpha_grid
                  for b in beta_grid if a + b < 0.999)
    for o, a, b in starts:
        params = [o, a, b]
        ll = nll(params)
        for scale in (0.80, 0.90, 1.00, 1.10, 1.25):
            for da in (-0.02, 0.0, 0.02):
                for db in (-0.03, 0.0, 0.03):
                    new = [params[0] * scale, max(0, params[1] + da),
                           max(0, params[2] + db)]
                    if new[1] + new[2] >= 0.999:
                        continue
                    nl = nll(new)
                    if nl < ll:
                        ll = nl
                        params = new
        if ll < best_ll:
            best_ll = ll
            best = params
    if best is None:
        return {"omega": float("nan"), "alpha": float("nan"),
                "beta": float("nan"), "status": "diverged"}
    o, a, b = best
    longv = o / (1 - a - b) if a + b < 1 else var
    return {"omega": o, "alpha": a, "beta": b, "long_var": longv,
            "neg_ll": best_ll, "status": "fitted"}


def ewma_vol_step(prev_var: float, r_prev: float, lam: float = 0.94) -> float:
    """§3.5 EWMA σ_t² = λσ_{t−1}² + (1−λ)r_{t−1}²."""
    return lam * prev_var + (1.0 - lam) * r_prev * r_prev


# --------------------------------------------------------------------------
# §3.6 HAR-RV (OLS + Newey-West HAC SE, lag 5)
# --------------------------------------------------------------------------
def _solve_linear(a: List[List[float]], b: List[float]) -> List[float]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-15:
            raise ValueError("SINGULAR_HAR_DESIGN_QX")
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(n):
            if r != col and abs(m[r][col]) > 0:
                factor = m[r][col] / m[col][col]
                for c in range(col, n + 1):
                    m[r][c] -= factor * m[col][c]
    return [m[i][n] / m[i][i] for i in range(n)]


def har_rv_fit(rv_series: Sequence[float], nw_lag: int = 5) -> Dict[str, Any]:
    """§3.6 RV_{t+1} = β0 + βd·RV + βw·RV_5 + βm·RV_22 + ε, NW HAC SEs."""
    n = len(rv_series)
    if n < 23 + nw_lag + 2:
        return {"status": "insufficient"}
    y, x_d, x_w, x_m = [], [], [], []
    for t in range(22, n - 1):
        rv_w = sum(rv_series[t - i] for i in range(5)) / 5.0
        rv_m = sum(rv_series[t - i] for i in range(22)) / 22.0
        y.append(rv_series[t + 1])
        x_d.append(rv_series[t])
        x_w.append(rv_w)
        x_m.append(rv_m)
    m = len(y)
    if m < nw_lag + 5:
        return {"status": "insufficient"}
    X = [[1.0, x_d[i], x_w[i], x_m[i]] for i in range(m)]
    XtX = [[sum(X[k][i] * X[k][j] for k in range(m)) for j in range(4)]
           for i in range(4)]
    Xty = [sum(X[k][i] * y[k] for k in range(m)) for i in range(4)]
    try:
        beta = _solve_linear(XtX, Xty)
    except ValueError:
        return {"status": "singular"}
    resid = [y[k] - sum(X[k][i] * beta[i] for i in range(4))
             for k in range(m)]
    # Newey-West sandwich (Bartlett kernel, lag nw_lag)
    xt_resid = [sum(X[k][i] * resid[k] for k in range(m)) for i in range(4)]
    S = [[0.0] * 4 for _ in range(4)]
    for lag in range(-nw_lag, nw_lag + 1):
        w = 1.0 - abs(lag) / (nw_lag + 1.0)
        for i in range(4):
            for j in range(4):
                acc = 0.0
                for k in range(max(0, -lag), min(m, m - lag)):
                    acc += X[k + lag][i] * resid[k + lag] * X[k][j] * resid[k]
                S[i][j] += w * acc
    try:
        XtX_inv_rows = [_solve_linear(XtX, e) for e in
                        [[1.0 if i == j else 0.0 for j in range(4)]
                         for i in range(4)]]
    except ValueError:
        return {"status": "singular", "beta": beta}
    meat = [[sum(sum(XtX_inv_rows[i][a2] * S[a2][b2] * XtX_inv_rows[b2][j]
                      for b2 in range(4)) for a2 in range(4))
             for j in range(4)] for i in range(4)]
    se = [math.sqrt(max(meat[i][i], 0.0)) for i in range(4)]
    return {"status": "fitted", "beta0": beta[0], "beta_d": beta[1],
            "beta_w": beta[2], "beta_m": beta[3],
            "newey_west_se": tuple(se), "n": m}


# --------------------------------------------------------------------------
# §3.7 Bollinger width · §3.8 VolRatio/RangeZ · §3.9 quantiles
# --------------------------------------------------------------------------
def bollinger_width(closes: Sequence[float], n: int = 20, k: float = 2.0
                    ) -> Tuple[float, float, float, float]:
    if len(closes) < n:
        return (float("nan"),) * 4
    win = closes[-n:]
    sma = sum(win) / n
    var = sum((x - sma) ** 2 for x in win) / n
    std = math.sqrt(var)
    up = sma + k * std
    low = sma - k * std
    width = (up - low) / max(sma, EPS)
    return width, sma, up, low


def vol_ratio(atr_s: float, atr_l: float) -> float:
    if math.isnan(atr_s) or math.isnan(atr_l) or atr_l < EPS:
        return float("nan")
    return atr_s / max(atr_l, EPS)


def range_z(cur: float, hist: Sequence[float]) -> float:
    if len(hist) < 20:
        return float("nan")
    mu = sum(hist) / len(hist)
    var = sum((x - mu) ** 2 for x in hist) / len(hist)
    sig = math.sqrt(var)
    return (cur - mu) / max(sig, EPS)


def rolling_quantiles(series: Sequence[float], window: int,
                      qs: Sequence[int]) -> Dict[int, float]:
    """§3.9 Percentile via linear interpolation over the PIT window."""
    if len(series) <= window:
        return {q: float("nan") for q in qs}
    data = sorted(series[-window:])
    m = len(data)
    res: Dict[int, float] = {}
    for q in qs:
        idx = (q / 100.0) * (m - 1)
        lo = int(math.floor(idx))
        hi = int(math.ceil(idx))
        res[q] = data[lo] if lo == hi else (
            data[lo] * (1 - (idx - lo)) + data[hi] * (idx - lo))
    return res


def regime_from_hv(hv: float, quantiles: Dict[int, float]) -> str:
    """§3.9 banding: VERY_LOW < q15 ≤ LOW < q35 ≤ NORMAL < q75 ≤
    ELEVATED < q95 ≤ EXTREME."""
    if any(math.isnan(v) for v in quantiles.values()):
        return "NORMAL"   # warmup: no quantile context → baseline (§1.1)
    if hv < quantiles[15]:
        return "VERY_LOW"
    if hv < quantiles[35]:
        return "LOW"
    if hv < quantiles[75]:
        return "NORMAL"
    if hv < quantiles[95]:
        return "ELEVATED"
    return "EXTREME"


# --------------------------------------------------------------------------
# §3.10 Ljung-Box (squared returns) · §3.11 non-directionality
# --------------------------------------------------------------------------
def ljung_box(r2: Sequence[float], m: int = 20) -> Tuple[float, float]:
    n = len(r2)
    if n <= m + 1:
        return float("nan"), float("nan")
    mean = sum(r2) / n
    denom = sum((x - mean) ** 2 for x in r2)
    if denom < EPS:
        return 0.0, 1.0
    rhos = []
    for k in range(1, m + 1):
        num = sum((r2[i] - mean) * (r2[i - k] - mean) for i in range(k, n))
        rhos.append(num / denom)
    Q = n * (n + 2) * sum(r ** 2 / (n - ki - 1)
                          for ki, r in enumerate(rhos))
    return Q, chi2_sf(Q, m)


def cluster_persistence(regimes: Sequence[str], target: str) -> float:
    """§2 Cluster Persistence, Laplace-smoothed (§4 reference)."""
    n_tr = n_same = 0
    for i in range(1, len(regimes)):
        if regimes[i - 1] == target:
            n_tr += 1
            if regimes[i] == target:
                n_same += 1
    return (n_same + 1) / (n_tr + 2) if n_tr > 0 else 0.5


def wilson_ci(p_hat: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    """§8.5 Wilson interval."""
    if n <= 0:
        return (0.0, 1.0)
    denom = 1.0 + z * z / n
    centre = p_hat + z * z / (2 * n)
    half = z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
    return ((centre - half) / denom, (centre + half) / denom)


def nondirectional_test(ret_next: Sequence[float], vol_cur: Sequence[float],
                        min_obs: int = 30
                        ) -> Tuple[float, float, float, Tuple[float, float]]:
    """§3.11 Corr(r_{t+1}, σ_t), t-stat, two-sided p, Fisher-z 95% CI."""
    n = min(len(ret_next), len(vol_cur))
    if n < min_obs:
        return float("nan"), float("nan"), float("nan"), (
            float("nan"), float("nan"))
    x = list(ret_next[:n])
    y = list(vol_cur[:n])
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    denx = sum((xi - mx) ** 2 for xi in x)
    deny = sum((yi - my) ** 2 for yi in y)
    den = math.sqrt(denx * deny)
    if den < EPS:
        return 0.0, 0.0, 1.0, (-1.0, 1.0)
    corr = num / den
    corr = max(-1.0 + 1e-12, min(1.0 - 1e-12, corr))
    t = corr * math.sqrt((n - 2) / max(1 - corr * corr, EPS))
    p = t_sf_two_sided(t, n - 2)
    z = 0.5 * math.log((1 + corr) / (1 - corr))
    lo_z, hi_z = z - 1.96 / math.sqrt(n - 3), z + 1.96 / math.sqrt(n - 3)
    return corr, t, p, (math.tanh(lo_z), math.tanh(hi_z))


# --------------------------------------------------------------------------
# §3.12 Volatility targeting
# --------------------------------------------------------------------------
def vol_targeting(risk_budget: float, atr: float, regime: str,
                  k_map: Optional[Dict[str, float]] = None) -> float:
    k = (k_map or K_TARGETING).get(regime, 2.0)
    if atr < EPS or risk_budget <= 0:
        return 0.0
    return risk_budget / (k * atr)


# --------------------------------------------------------------------------
# §5 VolatilityState v4.0.0 object
# --------------------------------------------------------------------------
VOLATILITY_STATE_REQUIRED = (
    "regime", "atr14_wilder", "atr50_wilder", "vol_ratio", "range_z",
    "hv30", "parkinson_adj", "gk", "rs", "yz", "ewma_vol", "garch_vol",
    "boll_width", "squeeze", "cluster_p", "ljung_q", "nondir_corr",
    "q_tag", "as_of", "snapshot_id", "contract_version",
)

EVENT_CATALOG = {
    "EV_VLT_001": "Regime_Up",
    "EV_VLT_002": "Regime_Down",
    "EV_VLT_003": "Squeeze_Start",
    "EV_VLT_004": "Squeeze_End",
    "EV_VLT_005": "Expansion_Breakout",
    "EV_VLT_006": "Compression_Alert",
    "EV_VLT_007": "Clustering_State",
    "EV_VLT_008": "Extreme_Move",
}


def snapshot_id(content_dict: Dict[str, Any]) -> str:
    """§4 snapshot_id(content_dict) — canonical snapshot form (§9.5-5)."""
    return canonical_snapshot_id(ENGINE, CONTRACT_VERSION, content_dict)


def _finite_or_zero(value: float) -> float:
    """§4 error handling: non-finite intermediates are quarantined and
    never serialized into standard JSON."""
    return value if math.isfinite(value) else 0.0


@dataclass
class VolatilityState:
    """§5 VolatilityState v4.0.0 (21 required contract fields)."""

    regime: str = "NORMAL"
    atr14_wilder: float = 0.0
    atr50_wilder: float = 0.0
    vol_ratio: float = 0.0
    range_z: float = 0.0
    hv30: float = 0.0
    parkinson_adj: float = 0.0
    gk: float = 0.0
    rs: float = 0.0
    yz: float = 0.0
    ewma_vol: float = 0.0
    garch_vol: float = 0.0
    boll_width: float = 0.0
    squeeze: bool = False
    cluster_p: float = 0.5
    ljung_q: float = 0.0
    nondir_corr: float = 0.0
    q_tag: str = "Q1"
    as_of: int = 0
    snapshot_id: str = ""
    contract_version: str = CONTRACT_LABEL

    def to_canonical(self) -> Dict[str, Any]:
        return {
            "regime": self.regime,
            "atr14_wilder": round(self.atr14_wilder, 10),
            "atr50_wilder": round(self.atr50_wilder, 10),
            "vol_ratio": round(self.vol_ratio, 10),
            "range_z": round(self.range_z, 10),
            "hv30": round(self.hv30, 10),
            "parkinson_adj": round(self.parkinson_adj, 10),
            "gk": round(self.gk, 10),
            "rs": round(self.rs, 10),
            "yz": round(self.yz, 10),
            "ewma_vol": round(self.ewma_vol, 10),
            "garch_vol": round(self.garch_vol, 10),
            "boll_width": round(self.boll_width, 10),
            "squeeze": self.squeeze,
            "cluster_p": round(self.cluster_p, 10),
            "ljung_q": round(self.ljung_q, 10),
            "nondir_corr": round(self.nondir_corr, 10),
            "q_tag": self.q_tag,
            "as_of": self.as_of,
            "contract_version": self.contract_version,
        }

    def update_snapshot(self) -> None:
        self.snapshot_id = snapshot_id(self.to_canonical())


def load_state(payload: Dict[str, Any]) -> VolatilityState:
    """§8.7 serialization compatibility: v4.0.0 payloads load; a v3 payload
    raises an explicit error (breaking change — the Wilder-RMA correction)."""
    version = payload.get("contract_version", "")
    if not str(version).endswith("v4.0.0"):
        raise ValueError(
            "E04_V3_PAYLOAD_REJECTED: v4.0.0 is a breaking change relative "
            "to v3 (Wilder-RMA correction); deserializing a v3 payload is "
            "an explicit error, never a silent reinterpretation (§8.7)")
    missing = [k for k in VOLATILITY_STATE_REQUIRED
               if k not in payload or payload[k] is None]
    if missing:
        raise ValueError(f"E04_STATE_MISSING_FIELDS_QX:{sorted(missing)}")
    state = VolatilityState(
        regime=payload["regime"], atr14_wilder=float(payload["atr14_wilder"]),
        atr50_wilder=float(payload["atr50_wilder"]),
        vol_ratio=float(payload["vol_ratio"]),
        range_z=float(payload["range_z"]), hv30=float(payload["hv30"]),
        parkinson_adj=float(payload["parkinson_adj"]),
        gk=float(payload["gk"]), rs=float(payload["rs"]),
        yz=float(payload["yz"]), ewma_vol=float(payload["ewma_vol"]),
        garch_vol=float(payload["garch_vol"]),
        boll_width=float(payload["boll_width"]),
        squeeze=bool(payload["squeeze"]),
        cluster_p=float(payload["cluster_p"]),
        ljung_q=float(payload["ljung_q"]),
        nondir_corr=float(payload["nondir_corr"]),
        q_tag=payload["q_tag"], as_of=int(payload["as_of"]),
        snapshot_id=payload["snapshot_id"])
    state.update_snapshot()
    return state


# --------------------------------------------------------------------------
# §4/§5 Streaming engine
# --------------------------------------------------------------------------
@dataclass
class VolatilityEvidence:
    """Per-bar engine output (Context for other engines, §0)."""

    state: VolatilityState
    events: List[Dict[str, Any]] = field(default_factory=list)
    atr_scalar: float = 0.0     # I_Volatility_v4 scalar for E03 (CP-2 note)
    position_size_hint: float = 0.0  # §3.12 (Context only, never a signal)


class VolatilityEngineV4:
    """Streaming E04 engine (§4 algorithms, §5 events, §7 hysteresis).

    ingest_bar(bar) consumes closed candles {ts, o, h, l, c, v} and
    returns VolatilityEvidence; idempotent on (ts, c, v); the last
    unclosed candle is never consumed (caller's PIT duty).
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None,
                 timeframe: str = "1h", risk_budget: float = 0.0):
        self.p = get_params(params)
        self.timeframe = timeframe
        self.risk_budget = risk_budget
        self.tf_seconds = TF_SECONDS.get(timeframe, 3600)
        self.atr_s = WilderATR(self.p["atr_short"])
        self.atr_l = WilderATR(self.p["atr_long"])
        self.bars: List[Dict[str, Any]] = []
        self.trs: List[float] = []
        self.returns: List[float] = []
        self.ranges: List[float] = []
        self.regimes: List[str] = []
        self.hv_series: List[float] = []
        self.ewma_var: Optional[float] = None
        self.garch_state: Dict[str, Any] = {"status": "insufficient"}
        self.in_squeeze = False
        self.squeeze_streak = 0
        self.prev_regime: Optional[str] = None
        self.drift_streak = 0
        self.nondir_fallback = False      # §8.8 RS fallback flag
        self.locked_streak = 0
        self.last_error: Optional[Dict[str, Any]] = None
        self._seen_keys: set = set()
        self.garch_refit_cadence = 20     # background-job cadence (§4 note)
        self._bar_count = 0

    # -- Wave-Out guard (§9.5-9: adaptive ATR E04↔E11) --------------------
    def request_adaptive_atr(self, regime_source: str = "E11") -> None:
        raise wave_out(
            "adaptive_atr_e04_e11",
            f"ADAPTIVE_ATR_WAVE_OUT: adaptive ATR (E04<->E11) is Wave-Out "
            f"(G6/§9.5-9); request via {regime_source} rejected")

    def _winsorize_tr(self, tr: float) -> Tuple[float, bool]:
        """§3.1 winsorize TR > 10×median(TR_20) at the 99th percentile."""
        window = self.trs[-20:]
        if len(window) < 5:
            return tr, False
        med = sorted(window)[len(window) // 2]
        if tr > self.p["winsorize_tr_mult"] * max(med, EPS):
            ordered = sorted(window + [tr])
            idx = max(0, int(math.ceil(0.99 * len(ordered))) - 1)
            return ordered[idx], True
        return tr, False

    def ingest_bar(self, bar: Dict[str, Any]) -> Optional[VolatilityEvidence]:
        key = (bar.get("ts"), bar.get("c"), bar.get("v"))
        if key in self._seen_keys:          # idempotency (§4)
            return None
        self._seen_keys.add(key)
        o, h, l, c = (float(bar["o"]), float(bar["h"]),
                      float(bar["l"]), float(bar["c"]))
        v = float(bar.get("v", 0.0))
        ts = int(bar.get("ts", 0))

        events: List[Dict[str, Any]] = []
        prev_close = self.bars[-1]["c"] if self.bars else None

        # §7 Ch.1-10 failure modes -------------------------------------
        locked = (h == l == o == c and v == 0)
        self.locked_streak = self.locked_streak + 1 if locked else 0
        if h < l:
            self.last_error = {"code": "INVALID_OHLC_H_LT_L",
                               "quality": "Q0", "as_of_ts": ts}
            return None                       # §2 Q0 defective, rejected

        tr_raw, qtag = true_range(h, l, prev_close)
        tr, winsorized = self._winsorize_tr(tr_raw) if qtag != "Q0" else (
            tr_raw, False)

        # §3.1 ATR recurrences (Q0 freezes — handled inside WilderATR)
        atr_s_val, _ = self.atr_s.update(tr, qtag)
        atr_l_val, _ = self.atr_l.update(tr, qtag)

        # §7 Ch.1-10: gap > 8×ATR winsorized + Extreme_Move flag
        gap_extreme = False
        if (prev_close is not None and not math.isnan(atr_s_val)
                and atr_s_val > 0
                and abs(prev_close - o) > self.p["gap_atr_mult"] * atr_s_val):
            gap_extreme = True

        self.bars.append({"ts": ts, "o": o, "h": h, "l": l, "c": c, "v": v})
        self.trs.append(tr)
        self.ranges.append(h - l)
        if prev_close is not None and prev_close > 0:
            self.returns.append(math.log(c / prev_close))
        self._bar_count += 1
        n = len(self.bars)

        if self._bar_count < 2:
            return None                       # need one return basis

        # §3.2 realized volatility / HV (annualized, crypto 365)
        hv_win = self.p["hv_window"]
        rv30 = realized_var(self.returns[-hv_win:])
        hv30 = annualized_hv(rv30, self.tf_seconds,
                             self.p["annualization_days"])
        self.hv_series.append(hv30)

        # §3.5 EWMA (σ0 seeded from sample variance of first 20 obs)
        r_last = self.returns[-1]
        if self.ewma_var is None:
            if len(self.returns) >= 20:
                seed = sum(x * x for x in self.returns[:20]) / 20.0
                self.ewma_var = seed
            else:
                self.ewma_var = r_last * r_last
        else:
            self.ewma_var = ewma_vol_step(self.ewma_var, r_last,
                                          self.p["ewma_lambda"])
        ewma_vol = math.sqrt(max(self.ewma_var, 0.0))

        # §3.3 window estimators (PIT window = last hv_win closed bars)
        win = self.bars[-hv_win:]
        opens = [b["o"] for b in win]
        highs = [b["h"] for b in win]
        lows = [b["l"] for b in win]
        closes = [b["c"] for b in win]
        closes_prev = [self.bars[i - 1]["c"]
                       for i in range(n - len(win), n)]
        gk = garman_klass(opens, highs, lows, closes)
        rs = rogers_satchell(opens, highs, lows, closes)
        yz = yang_zhang(opens, highs, lows, closes, closes_prev)
        park_adj = parkinson_adjusted(highs, lows, opens, closes_prev)
        if self.nondir_fallback:              # §8.8 RS fallback
            yz = rs

        # §3.4 GARCH (deterministic grid; refit cadence = background job)
        if (len(self.returns) >= self.p["garch_min_obs"]
                and self._bar_count % self.garch_refit_cadence == 0):
            fit = garch_mle_fit(self.returns[-max(
                self.p["garch_min_obs"], 200):], self.p["garch_min_obs"])
            self.garch_state = fit
        if self.garch_state.get("status") == "fitted":
            o_g = self.garch_state["omega"]
            a_g = self.garch_state["alpha"]
            b_g = self.garch_state["beta"]
            sig2_prev = self.garch_state.get("last_sig2",
                                             self.garch_state["long_var"])
            sig2 = o_g + a_g * (r_last ** 2) + b_g * sig2_prev
            self.garch_state["last_sig2"] = sig2
            garch_vol = math.sqrt(max(sig2, 0.0))
            garch_degraded = False
        else:
            # §3.4.1 fallback authorization boundary: EWMA fallback with a
            # degraded provenance flag; never a gate bypass.
            garch_vol = ewma_vol
            garch_degraded = True

        # §3.6 HAR-RV (diagnostic; non-finite-safe)
        rv_series = [x * x for x in self.returns]
        har = har_rv_fit(rv_series) if len(rv_series) > 40 else {
            "status": "insufficient"}

        # §3.7 Bollinger width
        closes_all = [b["c"] for b in self.bars]
        bw, sma20, bb_up, bb_low = bollinger_width(
            closes_all, self.p["boll_period"], self.p["boll_k"])

        # §3.8 VolRatio squeeze state + RangeZ
        vr = vol_ratio(atr_s_val, atr_l_val)
        rz = range_z(self.ranges[-1], self.ranges[-self.p["range_z_window"]
                                                  - 1:-1])
        squeeze_state = (not math.isnan(vr) and not math.isnan(bw)
                         and not math.isnan(rz)
                         and vr <= self.p["squeeze_vr"]
                         and bw <= self.p["squeeze_bw"]
                         and rz <= self.p["squeeze_rz"])

        # §3.9 regime quantiles over the 180-day PIT window excluding HV_t
        regime_window_bars = max(
            30, int(round(self.p["regime_window_days"] * 86400.0
                          / self.tf_seconds)))
        quantiles = rolling_quantiles(self.hv_series[:-1], regime_window_bars,
                                      self.p["regime_quantiles"])
        regime = regime_from_hv(hv30, quantiles)
        self.regimes.append(regime)

        # §3.10/§3.11/§2 clustering + non-directionality
        r2_series = [x * x for x in self.returns]
        ljung_q, ljung_p = ljung_box(r2_series, self.p["ljung_m"])
        cluster_p = cluster_persistence(self.regimes[-self.p[
            "cluster_window"]:], regime)
        if len(self.returns) >= self.p["nondir_min_obs"] + 1:
            sigma_hist = []
            lam = self.p["ewma_lambda"]
            var_acc = self.returns[0] ** 2
            for r in self.returns[:-1]:
                var_acc = lam * var_acc + (1 - lam) * r * r
                sigma_hist.append(math.sqrt(var_acc))
            corr, t_stat, p_val, ci = nondirectional_test(
                self.returns[1:], sigma_hist, self.p["nondir_min_obs"])
        else:
            corr, t_stat, p_val, ci = (float("nan"),) * 2 + (
                float("nan"), (float("nan"), float("nan")))

        # Q-tag ladder (§2 Q-tags + §8.5/§8.6 downgrades)
        q_tag = "Q1"
        if len(self.returns) >= hv_win:
            q_tag = "Q2"
        if (math.isfinite(gk) and math.isfinite(rs) and math.isfinite(yz)
                and yz > EPS):
            agreement = abs(gk - rs) / yz
            if agreement < 0.25 and q_tag == "Q2":
                q_tag = "Q3"                       # §2 Q3 cross-check
            if agreement > 0.4:
                q_tag = "Q2"                       # §8.6 inconsistency
        if (math.isfinite(atr_s_val) and math.isfinite(yz) and yz > 0
                and c > 0 and atr_s_val / (yz * c) > 3):
            q_tag = "Q2"                           # §8.6 ATR overestimate
        if garch_degraded and q_tag in ("Q3",):
            q_tag = "Q2"                           # §3.4.1 degraded flag
        if self.locked_streak >= self.p["locked_market_bars"]:
            q_tag = "Q0"                           # §7 Ch.1-10 locked market
        ci_lo, ci_hi = wilson_ci(cluster_p, max(1, len(self.regimes) - 1))
        if q_tag == "Q3" and (ci_hi - ci_lo) > 0.25:
            q_tag = "Q2"                           # §8.5 wide CI downgrade

        # §5 events -----------------------------------------------------
        if self.prev_regime is not None and regime != self.prev_regime:
            if REGIME_ORDER[regime] > REGIME_ORDER[self.prev_regime]:
                events.append(self._event("EV_VLT_001", ts, regime=regime,
                                          vol_ratio=vr, atr14=atr_s_val))
            else:
                events.append(self._event("EV_VLT_002", ts, regime=regime,
                                          vol_ratio=vr, atr14=atr_s_val))
        self.prev_regime = regime

        # squeeze hysteresis machine (§7 Ch.1-12 / Ch.3-12)
        enter_cond = (not math.isnan(vr) and not math.isnan(bw)
                      and vr < self.p["hyst_enter_vr"]
                      and bw < self.p["hyst_enter_bw"])
        exit_cond = (not math.isnan(vr) and not math.isnan(bw)
                     and (vr > self.p["hyst_exit_vr"]
                          or bw > self.p["hyst_exit_bw"]))
        if not self.in_squeeze:
            self.squeeze_streak = (self.squeeze_streak + 1
                                   if enter_cond else 0)
            if self.squeeze_streak >= self.p["hyst_enter_bars"]:
                self.in_squeeze = True
                events.append(self._event("EV_VLT_003", ts, regime=regime,
                                          vol_ratio=vr, boll_width=bw,
                                          atr14=atr_s_val, q_tag=q_tag))
        else:
            if exit_cond:
                self.in_squeeze = False
                self.squeeze_streak = 0
                events.append(self._event("EV_VLT_004", ts, regime=regime,
                                          vol_ratio=vr, boll_width=bw,
                                          atr14=atr_s_val))
                if (not math.isnan(rz) and rz > self.p["expansion_z"]):
                    events.append(self._event(
                        "EV_VLT_005", ts, regime=regime, range_z=rz,
                        bos_required=True,
                        note="EV_VLT_005 requires a BOS from E01 "
                             "(§5/§1.3 APEX-Contract-Structure v4.2); "
                             "the context chain confirms it downstream"))
            else:
                self.squeeze_streak = 0

        if (not math.isnan(vr) and not math.isnan(bw) and not math.isnan(rz)
                and vr < self.p["compression_vr"]
                and bw < self.p["compression_bw"]
                and rz < self.p["compression_rz"]):
            events.append(self._event("EV_VLT_006", ts, vol_ratio=vr,
                                      boll_width=bw, range_z=rz))

        if (len(self.regimes) >= self.p["cluster_span_bars"]
                and cluster_p > self.p["cluster_p_thr"]):
            events.append(self._event("EV_VLT_007", ts, cluster_p=cluster_p,
                                      regime=regime))

        if (not math.isnan(rz) and rz > self.p["extreme_z"]) or gap_extreme:
            events.append(self._event("EV_VLT_008", ts, range_z=rz,
                                      gap_extreme=gap_extreme))

        if winsorized:
            self.last_error = {"code": "TR_WINSORIZED_Q0_SUSPECT",
                               "quality": "Q0", "as_of_ts": ts}

        # §8.8 daily non-directionality check (per-bar evaluation; PIT
        # alignment as_of == close time). Three consecutive failures →
        # drift warning + Rogers-Satchell fallback.
        if math.isfinite(corr):
            if abs(corr) > self.p["nondir_corr_thr"] and p_val <= self.p[
                    "nondir_p_thr"]:
                self.drift_streak += 1
            else:
                self.drift_streak = 0
            if self.drift_streak >= self.p["drift_consec_days"]:
                self.nondir_fallback = True
                events.append(self._event(
                    "EV_VLT_002", ts, drift_warning=True,
                    note="non-directionality failed 3 consecutive periods; "
                         "fallback to Rogers-Satchell (§8.8)"))

        # §3.12 targeting (Context only; RiskBudget supplied by caller)
        pos_hint = vol_targeting(self.risk_budget, max(atr_s_val, 0.0),
                                 regime, self.p["k_targeting"])

        state = VolatilityState(
            regime=regime,
            atr14_wilder=max(_finite_or_zero(atr_s_val), 0.0),
            atr50_wilder=max(_finite_or_zero(atr_l_val), 0.0),
            vol_ratio=_finite_or_zero(vr),
            range_z=_finite_or_zero(rz),
            hv30=_finite_or_zero(hv30),
            parkinson_adj=_finite_or_zero(park_adj),
            gk=_finite_or_zero(gk),
            rs=_finite_or_zero(rs),
            yz=_finite_or_zero(yz),
            ewma_vol=_finite_or_zero(ewma_vol),
            garch_vol=_finite_or_zero(garch_vol),
            boll_width=_finite_or_zero(bw),
            squeeze=squeeze_state,
            cluster_p=_finite_or_zero(cluster_p),
            ljung_q=_finite_or_zero(ljung_q),
            nondir_corr=_finite_or_zero(corr),
            q_tag=q_tag,
            as_of=ts)
        state.update_snapshot()

        atr_published = max(atr_s_val if math.isfinite(atr_s_val) else 0.0,
                            ATR_FLOOR)
        return VolatilityEvidence(
            state=state, events=events, atr_scalar=atr_published,
            position_size_hint=pos_hint)

    @staticmethod
    def _event(code: str, ts: int, **payload: Any) -> Dict[str, Any]:
        return {"event_type": code,
                "event_name": EVENT_CATALOG[code],
                "as_of": ts,
                "contract_version": CONTRACT_LABEL,
                **payload}

    def output(self) -> Dict[str, Any]:
        """E04.Output.v4 — machine-readable engine summary."""
        return {
            "engine": ENGINE,
            "version": CONTRACT_VERSION,
            "bars": len(self.bars),
            "regime": self.regimes[-1] if self.regimes else None,
            "in_squeeze": self.in_squeeze,
            "garch_status": self.garch_state.get("status"),
            "nondir_fallback": self.nondir_fallback,
            "last_error": self.last_error,
        }


def run_engine(bars: Sequence[Dict[str, Any]],
               params: Optional[Dict[str, Any]] = None,
               timeframe: str = "1h",
               risk_budget: float = 0.0) -> Dict[str, Any]:
    """Pure batch entry point over closed candles (CP-2 parity)."""
    eng = VolatilityEngineV4(params, timeframe=timeframe,
                             risk_budget=risk_budget)
    evidences: List[VolatilityEvidence] = []
    for b in bars:
        ev = eng.ingest_bar(b)
        if ev is not None:
            evidences.append(ev)
    return {
        "engine": eng,
        "states": [e.state for e in evidences],
        "events": [evt for e in evidences for evt in e.events],
        "atr_series": [e.atr_scalar for e in evidences],
    }


# --------------------------------------------------------------------------
# EngineBase binding (frozen CP-1 contract; consumed, never patched)
# --------------------------------------------------------------------------
def observation_to_bar(obs: MarketObservation, timeframe: str) -> Dict[str, Any]:
    ts = obs.timestamp
    try:
        import datetime
        dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        ts_ms = int(dt.timestamp() * 1000)
    except (ValueError, AttributeError):
        ts_ms = 0
    return {"ts": ts_ms, "o": float(obs.open), "h": float(obs.high),
            "l": float(obs.low), "c": float(obs.close),
            "v": float(obs.volume), "tf": timeframe}


class E04VolatilityEngine(EngineBase):
    """E04_Volatility on the frozen EngineBase contract (v4.0.0).

    compute(symbol, timeframe, as_of, context): window via
    context['window'] or a sync WindowProvider (ISSUE-CP2-007 pattern).
    Publishes: per-bar VolatilityState evidence (topic evidence.E04.*),
    and the I_Volatility_v4 ATR scalar series E03 consumes via
    context['atr_prev'] (CP-2 cross-engine note).
    context keys: window, provider, bars, e04_params, risk_budget,
    adaptive_atr (any truthy value → WaveOutError)."""

    engine_id = "E04"
    analyst_version = ANALYST_VERSION
    code_revision = "0" * 40

    def compute(self, symbol: str, timeframe: str, as_of: str,
                context: Optional[Dict[str, Any]] = None
                ) -> List[EvidenceEvent]:
        context = context or {}
        if context.get("adaptive_atr") or context.get("adaptive_period"):
            # §9.5-9 Wave-Out: adaptive ATR E04↔E11 — raise, never build.
            raise wave_out("adaptive_atr_e04_e11",
                           "ADAPTIVE_ATR_WAVE_OUT: adaptive ATR period "
                           "selection (E04<->E11) is Wave-Out (G6/§9.5-9)")
        window_obs = self._resolve_window(symbol, timeframe, as_of, context)
        if not window_obs:
            return []
        bars = [observation_to_bar(o, timeframe) for o in window_obs]
        params = get_params(context.get("e04_params"))
        risk_budget = float(context.get("risk_budget", 0.0))
        out = run_engine(bars, params, timeframe=timeframe,
                         risk_budget=risk_budget)
        input_hash = self._hash_bars(bars)
        replay = self.build_replay_key(
            symbol, timeframe, as_of, input_hash,
            "E04-VLT-V4.0.0-DEFAULTS",
            str(sorted((k, str(v)) for k, v in params.items()
                       if k in ("atr_short", "atr_long", "hv_window",
                                "ewma_lambda", "ljung_m"))))
        cached = self.replay_lookup(replay)
        if cached is not None:
            return cached
        quality = self._window_quality(window_obs)
        events = [self._to_evidence(ev, symbol, timeframe, quality)
                  for ev in out["states"] if ev.snapshot_id]
        self.replay_store(replay, events)
        return events

    def atr_series_for(self, symbol: str, timeframe: str, as_of: str,
                       context: Optional[Dict[str, Any]] = None
                       ) -> List[float]:
        """I_Volatility_v4 mirror: the ATR scalar series E03's
        context['atr_prev'] consumes (CP-2 handoff cross-engine note)."""
        context = context or {}
        window_obs = self._resolve_window(symbol, timeframe, as_of, context)
        if not window_obs:
            return []
        bars = [observation_to_bar(o, timeframe) for o in window_obs]
        params = get_params(context.get("e04_params"))
        out = run_engine(bars, params, timeframe=timeframe)
        atr_series = list(out["atr_series"])
        # align 1:1 with the window: leading warmup bars carry the ATR
        # floor (never a fabricated value, never NaN)
        while len(atr_series) < len(bars):
            atr_series.insert(0, ATR_FLOOR)
        return atr_series

    # -- helpers (same contract surface as the CP-2 engines) ---------------
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

    @staticmethod
    def _hash_bars(bars: List[Dict[str, Any]]) -> str:
        import hashlib
        import json
        payload = json.dumps(
            [{k: b[k] for k in ("ts", "o", "h", "l", "c", "v")}
             for b in bars], sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _to_evidence(self, state: VolatilityState, symbol: str,
                     timeframe: str, quality: float) -> EvidenceEvent:
        import datetime
        as_of_iso = datetime.datetime.fromtimestamp(
            state.as_of / 1000.0, tz=datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.") + f"{state.as_of % 1000:03d}Z"
        condition = (f"{state.regime}"
                     + ("_SQUEEZE" if state.squeeze else ""))
        return EvidenceEvent(
            evidence_id=uuid_v7(),
            engine_id=self.engine_id,
            analyst_version=self.analyst_version,
            symbol=symbol, timeframe=timeframe,
            snapshot_id=state.snapshot_id,
            event_time=as_of_iso,
            availability_time=as_of_iso,
            observation_window={"bars": 0, "tf": timeframe},
            feature_snapshot_id=state.snapshot_id,
            feature_dependencies=("window",),
            condition_state=f"EV_VLT_STATE_{condition}",
            direction=0,                       # §1.4 non-directional
            strength=float(min(max(state.vol_ratio, 0.0), 10.0)),
            confidence=1.0 if state.q_tag in ("Q3", "Q4") else 0.5,
            quality=float(quality),
            validity="VALID" if state.q_tag != "Q0" else "DEGRADED",
            fate_state=LifecycleState.ACTIVE,
            age=0.0,
            decay=1.0,
            explanation=(f"E04 volatility state: regime={state.regime} "
                         f"atr14={state.atr14_wilder} vr={state.vol_ratio} "
                         f"q={state.q_tag}"),
            parameter_version="E04-VLT-V4.0.0/DEFAULTS-v1",
            lineage=(f"as_of_{state.as_of}",),
            resolution_class=state.q_tag,
        )
