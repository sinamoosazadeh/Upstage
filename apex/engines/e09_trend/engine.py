"""APEX_GEN5 E09 — Trend engine (v4.0.0).

Blueprint: APEX_GEN5.md L9467–10275 (chapter order mirrored: §3 formulas →
§4 algorithms → §5 objects/state/events/schema → §6 params → §7 notes →
§8 validation hooks). Multi-scale trend: 4 formal scales MICRO(5) /
SHORT(20) / INTER(60) / MACRO(240), each carrying direction, strength,
quality, seq_score, slope_z, pos, adx, hurst, mk_z, r2_ols. TrendStack
weights are fixed and governed w = [0.1, 0.2, 0.3, 0.4].

Design anchors: seq_score = (N_HH+N_HL−N_LH−N_LL)/N_total; OLS slope with
Newey-West HAC (L = floor(4·(n/100)^(2/9))); Mann-Kendall with exact
tie-correction Var(S) = [n(n-1)(2n+5) − Σ t(t-1)(2t+5)]/18; Hurst with
Anis-Lloyd bias correction; full Wilder ADX (TR, ±DM, DI±, DX, ADX);
Q_trend = R²·(ADX/100)·H_clip clipped to [0,1.5]. Exhaustion linked to
price-momentum divergence (shared implementation with E10).

Versioned dependencies: E01 (Swing Points), E04 (ATR), E10 (Momentum —
optional, divergence). Output is TrendState/TrendStack/Events, never a
buy/sell signal.
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
from apex.identity.snapshot import canonical_snapshot_id
from apex.identity.uuid_v7 import uuid_v7
from apex.quality.numerical import eps_for_engine

ENGINE = "E09_Trend"
CONTRACT_VERSION = "4.0.0"
ANALYST_VERSION = "4.0.0+" + "0" * 40
EPS = float(eps_for_engine("E09"))          # 1e-12 (§2.2 E09 row)

SCALES = ("MICRO", "SHORT", "INTER", "MACRO")
W_STACK_CORRECTED = {"MICRO": 0.1, "SHORT": 0.2, "INTER": 0.3, "MACRO": 0.4}

ALIGNMENTS = ("ALIGNED_BULL", "ALIGNED_BEAR", "CONFLICTING", "SIDEWAYS",
              "TRANSITIONING")

EVENT_CATALOG = {
    "EV_TRD_001": "Trend_Initiated",
    "EV_TRD_002": "Trend_Continued",
    "EV_TRD_003": "Trend_Exhausted",
    "EV_TRD_004": "Trend_Transition",
    "EV_TRD_005": "Stack_Aligned",
    "EV_TRD_006": "Stack_Conflicting",
    "EV_TRD_007": "Sideways_Detected",
    "EV_TRD_008": "Quality_Degraded",
}

STATE_FATES = ("UNKNOWN", "CALCULATING", "VALID", "DEGRADED", "INVALID")


# ---------------------------------------------------------------------------
# §6 Parameters (frozen in-package defaults, ISSUE-CP2-006 pattern)
# ---------------------------------------------------------------------------
E09_DEFAULTS: Dict[str, Any] = {
    "windows": {"MICRO": 5, "SHORT": 20, "INTER": 60, "MACRO": 240},
    "w_a_b_c": (0.4, 0.35, 0.25),   # seq/slope_z/pos directional weights Σ=1
    "slope_z_threshold": 1.5,       # θ_s
    "pos_threshold": 0.3,           # θ_p (×ATR)
    "strength_th": 0.5,             # θ_str
    "adx_n": 14,                    # Wilder standard
    "mk_crit_z": 1.96,              # MK critical z
    "hurst_window": 128,            # hurst_window
    "hurst_min_len": 8,             # hurst_min_len
    "stack_weights": (0.1, 0.2, 0.3, 0.4),   # MICRO..MACRO
    "transition_confirm_bars": 2,   # transition confirm
    "divergence_delta": 0.1,        # E10 divergence Δ
    "r2_min_for_Q": 0.2,            # quality gate
    "adx_min_for_trend": 15,        # adx min (crypto-adjusted)
    "adx_valid_min": 10,            # §5.3 VALID gate
    "strength_deg_min": 0.3,        # §5.3 DEGRADED gate
}


def get_params(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = dict(E09_DEFAULTS)
    for key, value in (overrides or {}).items():
        if key not in E09_DEFAULTS:
            raise ValueError(f"UNKNOWN_E09_PARAM_QX:{key}")
        params[key] = value
    for tup in ("w_a_b_c", "stack_weights"):
        vals = tuple(params[tup])
        if abs(sum(vals) - 1.0) > 1e-9:
            raise ValueError(f"E09_{tup.upper()}_SUM_QX")
        params[tup] = vals
    return params


# ---------------------------------------------------------------------------
# §4 core formula functions (PIT-safe; deterministic)
# ---------------------------------------------------------------------------
def validate_bar(bar: Dict[str, Any]) -> bool:
    """§4 validate_bar — H<L or non-positive price ⇒ invalid."""
    if bar["h"] < bar["l"] - EPS:
        return False
    if bar["c"] <= 0 or bar["h"] <= 0 or bar["l"] <= 0 or bar["o"] <= 0:
        return False
    return True


def compute_seq_score(swings: Sequence[Dict[str, Any]], window: int,
                      current_idx: int) -> Tuple[float, int]:
    """§3.1 seq_score = (HH+HL − LH−LL)/N_total over confirmed swings."""
    relevant = [s for s in swings
                if s["confirmed_at_idx"] <= current_idx - 1 and
                s["idx"] >= current_idx - window]
    if not relevant:
        return 0.0, 0
    n_hh = sum(1 for s in relevant if s["type"] == "HH")
    n_hl = sum(1 for s in relevant if s["type"] == "HL")
    n_lh = sum(1 for s in relevant if s["type"] == "LH")
    n_ll = sum(1 for s in relevant if s["type"] == "LL")
    n_eq = sum(1 for s in relevant if s["type"] == "EQ")
    total = n_hh + n_hl + n_lh + n_ll + n_eq
    if total == 0:
        return 0.0, 0
    score = (n_hh + n_hl - n_lh - n_ll) / total
    return max(-1.0, min(1.0, score)), total


def ols_slope_newey_west(ts: Sequence[float], ys: Sequence[float],
                         lag_auto: bool = True
                         ) -> Tuple[float, float, float]:
    """§3.2 OLS slope with Newey-West HAC (L = floor(4·(n/100)^(2/9)))."""
    n = len(ys)
    if n < 3:
        return 0.0, float("inf"), 0.0
    mx = sum(ts) / n
    my = sum(ys) / n
    cov = sum((t - mx) * (y - my) for t, y in zip(ts, ys))
    var_t = sum((t - mx) ** 2 for t in ts)
    if var_t < EPS:
        return 0.0, float("inf"), 0.0
    beta = cov / var_t
    resid = [y - (my + beta * (t - mx)) for t, y in zip(ts, ys)]
    sst = sum((y - my) ** 2 for y in ys)
    ssr = sum(r * r for r in resid)
    r2 = 0.0 if sst < EPS else max(0.0, 1 - ssr / max(sst, EPS))
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
    var_beta = omega / max(var_t ** 2, EPS)
    se = math.sqrt(max(var_beta, EPS))
    return beta, se, r2


def mann_kendall_with_tie_correction(x: Sequence[float]
                                     ) -> Tuple[float, float, float]:
    """§3.3 Mann-Kendall with exact tie correction."""
    n = len(x)
    if n < 3:
        return 0.0, 1.0, 0.0
    S = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            if x[j] > x[i]:
                S += 1
            elif x[j] < x[i]:
                S -= 1
    sorted_x = sorted(x)
    tie_counts: List[int] = []
    cnt = 1
    for i in range(1, n):
        if abs(sorted_x[i] - sorted_x[i - 1]) < 1e-12:
            cnt += 1
        else:
            if cnt > 1:
                tie_counts.append(cnt)
            cnt = 1
    if cnt > 1:
        tie_counts.append(cnt)
    tie_correction = sum(t * (t - 1) * (2 * t + 5) for t in tie_counts)
    var_s = (n * (n - 1) * (2 * n + 5) - tie_correction) / 18.0
    var_s = max(var_s, 1.0)
    if S > 0:
        z = (S - 1) / math.sqrt(var_s)
    elif S < 0:
        z = (S + 1) / math.sqrt(var_s)
    else:
        z = 0.0
    return float(S), float(var_s), float(z)


def anis_lloyd_expected_rs(n: int) -> float:
    """§3.4 Anis-Lloyd bias correction E[R/S]_n."""
    if n <= 1:
        return 0.0
    if n <= 340:
        s = 0.0
        for i in range(1, n):
            s += math.sqrt((n - i) / i)
        lg1 = math.lgamma((n - 1) / 2)
        lg2 = math.lgamma(n / 2)
        ratio = math.exp(lg1 - lg2) / math.sqrt(math.pi)
        return (n - 0.5) / n * ratio * s
    return math.sqrt(math.pi * n / 2)


def hurst_rs_anis_lloyd_corrected(x: Sequence[float], min_len: int = 8,
                                  max_len: Optional[int] = None
                                  ) -> Tuple[float, float]:
    """§3.4 Hurst via Anis-Lloyd-corrected R/S + log-log regression."""
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
            cum_vals: List[float] = []
            cum = 0.0
            for d in dev:
                cum += d
                cum_vals.append(cum)
            R = max(cum_vals) - min(cum_vals) if cum_vals else 0.0
            S = math.sqrt(sum(d * d for d in dev) / length) if length > 1 \
                else 0.0
            if S < EPS:
                continue
            rs_raw = R / S
            e_rs = anis_lloyd_expected_rs(length)
            if e_rs < EPS:
                continue
            rs_corr = rs_raw / e_rs * math.sqrt(math.pi * length / 2)
            acc_rs += rs_corr
            valid_segs += 1
        if valid_segs > 0:
            avg_rs = acc_rs / valid_segs
            lens.append(math.log(length))
            rs.append(math.log(max(avg_rs, EPS)))
        length //= 2
    if len(lens) < 3:
        return 0.5, 0.0
    beta, _se, r2 = ols_slope_newey_west(lens, rs)
    H = max(0.0, min(1.5, beta))
    return H, r2


def wilder_rma(prev: float, curr: float, n: int) -> float:
    return (prev * (n - 1) + curr) / n


def compute_adx_wilder(bars: Sequence[Dict[str, Any]], n: int = 14
                       ) -> Dict[str, float]:
    """§3.5 full Wilder ADX (TR, ±DM, DI±, DX, ADX)."""
    if len(bars) < 2:
        return {"di_plus": 0.0, "di_minus": 0.0, "dx": 0.0, "adx": 0.0,
                "tr_smooth": 0.0}
    trs: List[float] = []
    plus_dms: List[float] = []
    minus_dms: List[float] = []
    for i in range(1, len(bars)):
        if not validate_bar(bars[i]) or not validate_bar(bars[i - 1]):
            continue
        h = bars[i]["h"]
        l = bars[i]["l"]
        pc = bars[i - 1]["c"]
        up = h - bars[i - 1]["h"]
        down = bars[i - 1]["l"] - l
        tr = max(h - l, abs(h - pc), abs(l - pc))
        plus = up if up > down and up > 0 else 0.0
        minus = down if down > up and down > 0 else 0.0
        trs.append(tr)
        plus_dms.append(plus)
        minus_dms.append(minus)
    if len(trs) < n:
        return {"di_plus": 0.0, "di_minus": 0.0, "dx": 0.0, "adx": 0.0,
                "tr_smooth": 0.0}
    tr_smooth = sum(trs[:n]) / n
    plus_smooth = sum(plus_dms[:n]) / n
    minus_smooth = sum(minus_dms[:n]) / n
    dx_list: List[float] = []
    di_plus = di_minus = 0.0
    for idx in range(n, len(trs)):
        tr_smooth = wilder_rma(tr_smooth, trs[idx], n)
        plus_smooth = wilder_rma(plus_smooth, plus_dms[idx], n)
        minus_smooth = wilder_rma(minus_smooth, minus_dms[idx], n)
        di_plus = 100 * plus_smooth / max(tr_smooth, EPS)
        di_minus = 100 * minus_smooth / max(tr_smooth, EPS)
        dx = 100 * abs(di_plus - di_minus) / max(di_plus + di_minus, EPS) \
            if (di_plus + di_minus) > EPS else 0.0
        dx_list.append(dx)
    if not dx_list:
        return {"di_plus": di_plus, "di_minus": di_minus, "dx": 0.0,
                "adx": 0.0, "tr_smooth": tr_smooth}
    adx = sum(dx_list[:n]) / n if len(dx_list) >= n else \
        sum(dx_list) / len(dx_list)
    for dxv in dx_list[n:]:
        adx = wilder_rma(adx, dxv, n)
    final_di_plus = 100 * plus_smooth / max(tr_smooth, EPS)
    final_di_minus = 100 * minus_smooth / max(tr_smooth, EPS)
    final_dx = 100 * abs(final_di_plus - final_di_minus) / \
        max(final_di_plus + final_di_minus, EPS) if \
        (final_di_plus + final_di_minus) > EPS else 0.0
    return {"di_plus": final_di_plus, "di_minus": final_di_minus,
            "dx": final_dx, "adx": adx, "tr_smooth": tr_smooth}


def compute_pos_scale(bars: Sequence[Dict[str, Any]], window: int,
                      atr_val: float) -> float:
    """§4 pos = (C − SMA_window)/max(ATR, eps)."""
    if not bars:
        return 0.0
    recent = bars[-window:] if len(bars) >= window else bars
    sma = sum(b["c"] for b in recent) / len(recent)
    c = bars[-1]["c"]
    return (c - sma) / max(atr_val, EPS)


def trend_direction_and_strength(seq_score: float, slope_z: float,
                                 pos: float,
                                 w: Tuple[float, float, float] =
                                 (0.4, 0.35, 0.25),
                                 th: float = 0.5
                                 ) -> Tuple[int, float, float]:
    """§4 direction/strength from z = wa·seq + wb·slope_z + wc·pos."""
    wa, wb, wc = w
    z = wa * seq_score + wb * slope_z + wc * pos
    dir_ = 1 if z > 0.05 else (-1 if z < -0.05 else 0)
    strength = min(1.0, abs(z) / max(th, EPS))
    return dir_, strength, z


def compute_trend_quality(r2: float, adx: float, hurst: float) -> float:
    """§3.8 Q_trend = R²·(ADX/100)·H_clip, clipped to [0,1.5].

    H_clip follows §3.8 (formula authority): H if 0<=H<=1.2, else 1.0 if
    H>1.2, else 0.0. (The §0 'min(H,1.0)' and §2 'min(H,1.2)' phrasings
    differ from §3.8 and §4; recorded as ISSUE-CP4-003 — §3.8 applied.)
    """
    if hurst < 0.0:
        h_clip = 0.0
    elif hurst > 1.2:
        h_clip = 1.0
    else:
        h_clip = hurst
    return max(0.0, min(1.5, r2 * (adx / 100.0) * h_clip))


def quality_label(q: float, r2: float, adx: float, hurst: float) -> str:
    """§4 quality_label — Q5 additionally requires r2>=0.7, adx>=25,
    hurst>=0.6 (§4 executable reference; §2 table is the conceptual band)."""
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


def divergence_exhaustion_check(price_swings: Sequence[Dict[str, Any]],
                                mom_series: Sequence[float],
                                current_idx: int,
                                lookback: int = 20,
                                delta: float = 0.1) -> Dict[str, Any]:
    """§3.7 Exhaustion via momentum divergence (shared with E10).

    Bearish: price HH but momentum LH; Bullish: price LL but momentum HL.
    """
    if len(price_swings) < 2 or len(mom_series) < lookback:
        return {"is_exhaustion": False, "type": None, "score": 0.0}
    price_recent = price_swings[-1].get("price", 0)
    price_prev = price_swings[-2].get("price", price_recent) if \
        len(price_swings) >= 2 else price_recent
    mom_recent = mom_series[-1]
    mom_prev = mom_series[-2] if len(mom_series) >= 2 else mom_recent
    bear_div = (price_recent > price_prev) and (mom_recent < mom_prev - delta)
    bull_div = (price_recent < price_prev) and (mom_recent > mom_prev + delta)
    if bear_div:
        return {"is_exhaustion": True, "type": "BEARISH_DIVERGENCE",
                "score": 0.8}
    if bull_div:
        return {"is_exhaustion": True, "type": "BULLISH_DIVERGENCE",
                "score": 0.8}
    return {"is_exhaustion": False, "type": None, "score": 0.0}


def wilson_ci(p_hat: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    """§8.5 Wilson interval."""
    if n <= 0:
        return 0.0, 1.0
    denom = 1 + z * z / n
    centre = (p_hat + z * z / (2 * n)) / denom
    half = z * math.sqrt((p_hat * (1 - p_hat) / n + z * z / (4 * n * n))) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def alignment_of(bias: float) -> str:
    """§3.6/§5.2 TrendStack alignment from bias."""
    if bias > 0.5:
        return "ALIGNED_BULL"
    if bias < -0.5:
        return "ALIGNED_BEAR"
    if abs(bias) <= 0.3:
        return "SIDEWAYS"
    return "CONFLICTING"


# ---------------------------------------------------------------------------
# §4 TrendEngine (streaming + cache)
# ---------------------------------------------------------------------------
@dataclass
class TrendScale:
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scale": self.scale, "direction": self.direction,
            "strength": self.strength, "quality": self.quality,
            "quality_label": self.quality_label,
            "seq_score": self.seq_score, "slope_z": self.slope_z,
            "pos": self.pos, "r2": self.r2, "adx": self.adx,
            "di_plus": self.di_plus, "di_minus": self.di_minus,
            "hurst": self.hurst, "mk_z": self.mk_z,
            "evidence_count": self.evidence_count,
        }


class TrendEngine:
    """§4 TrendEngine — streaming over closed candles with cache."""

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        self.params = get_params(params)
        self.cache: Dict[str, Dict[str, Any]] = {}

    def process_bar(self, bars: Sequence[Dict[str, Any]],
                    swings: Sequence[Dict[str, Any]], atr: float,
                    mom_series: Sequence[float]) -> Dict[str, Any]:
        key = f"{bars[-1].get('t_close', 0)}_{bars[-1]['c']}"
        if key in self.cache:
            return self.cache[key]
        scales = list(SCALES)
        windows = self.params["windows"]
        result_scales: Dict[str, Dict[str, Any]] = {}
        for s in scales:
            W = windows[s]
            seq_score, ev_count = compute_seq_score(swings, W, len(bars) - 1)
            closes = [b["c"] for b in bars[-W:]]
            log_closes = [math.log(max(c, EPS)) for c in closes]
            t = list(range(len(log_closes)))
            beta, se, r2 = ols_slope_newey_west(t, log_closes)
            slope_z = beta / max(se, EPS) if se != float("inf") else 0.0
            pos = compute_pos_scale(bars, W, atr)
            dir_, strength, _raw = trend_direction_and_strength(
                seq_score, slope_z, pos, w=tuple(self.params["w_a_b_c"]),
                th=self.params["strength_th"])
            _S, _v, mkz = mann_kendall_with_tie_correction(log_closes)
            hurst, _ = hurst_rs_anis_lloyd_corrected(
                log_closes, min_len=self.params["hurst_min_len"])
            adx_res = compute_adx_wilder(
                bars[-max(W, self.params["adx_n"] * 3):],
                n=self.params["adx_n"])
            q = compute_trend_quality(r2, adx_res["adx"], hurst)
            qlabel = quality_label(q, r2, adx_res["adx"], hurst)
            result_scales[s] = {
                "direction": dir_, "strength": strength, "quality": q,
                "quality_label": qlabel, "seq_score": seq_score,
                "slope_z": slope_z, "pos": pos, "r2": r2,
                "adx": adx_res["adx"], "di_plus": adx_res["di_plus"],
                "di_minus": adx_res["di_minus"], "hurst": hurst,
                "mk_z": mkz, "evidence_count": ev_count,
            }
        bias = sum(W_STACK_CORRECTED[s] * result_scales[s]["direction"]
                   for s in scales)
        snapshot_payload = {
            "as_of": bars[-1].get("t_close", 0),
            "symbol": bars[-1].get("symbol", "UNKNOWN"),
            "interval": bars[-1].get("interval", "UNKNOWN"),
            "scales": result_scales,
        }
        sid = canonical_snapshot_id(ENGINE, CONTRACT_VERSION,
                                    snapshot_payload)
        out = {"scales": result_scales, "bias": bias, "snapshot_id": sid,
               "as_of_bar": bars[-1].get("t_close", 0),
               "alignment": alignment_of(bias)}
        self.cache[key] = out
        if len(self.cache) > 1000:
            self.cache.pop(next(iter(self.cache)))
        return out


def run_engine(bars: Sequence[Dict[str, Any]],
               params: Optional[Dict[str, Any]] = None,
               swings: Optional[Sequence[Dict[str, Any]]] = None,
               atr: float = 0.0,
               mom_series: Optional[Sequence[float]] = None,
               symbol: str = "",
               timeframe: str = "1h",
               ) -> Dict[str, Any]:
    """Batch driver — one TrendStack over the closed-candle window."""
    p = get_params(params)
    eng = TrendEngine(p)
    swings = list(swings or [])
    mom = list(mom_series or [])
    if atr <= 0:
        atr = _atr_estimate(bars, p["adx_n"])
    result = eng.process_bar(bars, swings, atr, mom)
    divergence = divergence_exhaustion_check(
        swings, mom, len(bars) - 1, delta=p["divergence_delta"])
    result["divergence"] = divergence
    result["events"] = _detect_events(result, divergence, p)
    result["symbol"] = symbol
    result["timeframe"] = timeframe
    return result


def _atr_estimate(bars: Sequence[Dict[str, Any]], n: int) -> float:
    trs = []
    for i in range(1, len(bars)):
        if bars[i]["h"] < bars[i]["l"]:
            continue
        trs.append(max(bars[i]["h"] - bars[i]["l"],
                       abs(bars[i]["h"] - bars[i - 1]["c"]),
                       abs(bars[i]["l"] - bars[i - 1]["c"])))
    if not trs:
        return EPS
    if len(trs) >= n:
        atr = sum(trs[:n]) / n
        for x in trs[n:]:
            atr = (atr * (n - 1) + x) / n
        return atr
    return sum(trs) / len(trs)


def _detect_events(result: Dict[str, Any],
                   divergence: Dict[str, Any],
                   p: Dict[str, Any]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    scales = result["scales"]
    bias = result["bias"]
    macro_dir = scales.get("MACRO", {}).get("direction", 0)
    # Stack aligned
    dirs = {s: scales[s]["direction"] for s in SCALES}
    if all(d == 1 for d in dirs.values()) and abs(bias) >= 0.7:
        events.append({"code": "EV_TRD_005", "name": "Stack_Aligned"})
    if any(d == -macro_dir for d in dirs.values() if macro_dir != 0):
        events.append({"code": "EV_TRD_006", "name": "Stack_Conflicting"})
    # Sideways
    hursts = [scales[s]["hurst"] for s in SCALES]
    adxs = [scales[s]["adx"] for s in SCALES]
    r2s = [scales[s]["r2"] for s in SCALES]
    if (all(abs(h - 0.5) < 0.1 for h in hursts) and
            max(adxs) < 20 and max(r2s) < 0.3):
        events.append({"code": "EV_TRD_007", "name": "Sideways_Detected"})
    if divergence.get("is_exhaustion"):
        events.append({"code": "EV_TRD_003", "name": "Trend_Exhausted",
                       "type": divergence["type"]})
    return events


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
            "v": float(obs.volume), "t_close": ts_ms,
            "symbol": obs.symbol, "interval": obs.timeframe}


class E09TrendEngine(EngineBase):
    """E09_Trend on the frozen EngineBase contract (v4.0.0).

    compute(symbol, timeframe, as_of, context): window via context['window']
    or a sync WindowProvider. Consumed context keys: window, provider, bars,
    e09_params, swings (E01 Swing Points), atr (E04), mom_series (E10 —
    optional, divergence). Produces TrendState/TrendStack evidence on
    topics evidence.E09.* .
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
        bars = [observation_to_bar(o) for o in window_obs]
        params = get_params(context.get("e09_params"))
        atr = float(context.get("atr", 0.0))
        result = run_engine(
            bars, params,
            swings=context.get("swings"),
            atr=atr,
            mom_series=context.get("mom_series"),
            symbol=symbol, timeframe=timeframe)
        quality = self._window_quality(window_obs)
        out: List[EvidenceEvent] = []
        for s in SCALES:
            out.append(self._to_evidence(result, s, symbol, timeframe,
                                         quality))
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

    def _to_evidence(self, result: Dict[str, Any], scale: str, symbol: str,
                     timeframe: str, quality: float) -> EvidenceEvent:
        sc = result["scales"].get(scale, {})
        ts_ms = result.get("as_of_bar", 0)
        as_of_iso = datetime.fromtimestamp(
            ts_ms / 1000.0, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.") + f"{ts_ms % 1000:03d}Z"
        qlabel = sc.get("quality_label", "Q0")
        direction = int(sc.get("direction", 0))
        return EvidenceEvent(
            evidence_id=uuid_v7(),
            engine_id=self.engine_id,
            analyst_version=self.analyst_version,
            symbol=symbol, timeframe=timeframe,
            snapshot_id=result.get("snapshot_id", ""),
            event_time=as_of_iso,
            availability_time=as_of_iso,
            observation_window={"scale": scale, "tf": timeframe},
            feature_snapshot_id=result.get("snapshot_id", ""),
            feature_dependencies=("window", "swings", "atr", "mom_series"),
            condition_state=f"EV_TRD_STATE_{scale}_{qlabel}",
            direction=direction,
            strength=float(min(max(sc.get("strength", 0.0), 0.0), 1.0)),
            confidence=float(min(1.0, abs(sc.get("mk_z", 0.0)) / 3.0)),
            quality=float(quality),
            validity="VALID" if qlabel != "Q0" else "DEGRADED",
            fate_state=LifecycleState.ACTIVE,
            age=None,
            decay=None,
            explanation=(f"E09 {scale} dir={direction} "
                         f"strength={sc.get('strength', 0):.4f} "
                         f"Q={sc.get('quality', 0):.4f} "
                         f"slope_z={sc.get('slope_z', 0):.4f} "
                         f"adx={sc.get('adx', 0):.2f} "
                         f"hurst={sc.get('hurst', 0):.3f} "
                         f"mk_z={sc.get('mk_z', 0):.3f}"),
            parameter_version="E09-TREND-V4.0.0/DEFAULTS-v1",
            lineage=(f"{scale}",),
            resolution_class=qlabel,
        )
