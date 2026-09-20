"""APEX_GEN5 E02 — Liquidity Engine (E02.Output.v4, engine E02_LIQUIDITY).

Zero inter-engine dependency: input is CLOSED OHLCV (+ optional versioned
L2Snapshot.v1 / SwingInput.v1 / VolumeProfile). Output is context-only,
never a trading signal (NG1–NG5).

Engine file mirrors chapter order (PHASE2_CHECKPOINTS.md §CP-2):
  §3 formulas -> §4 algorithms -> §5 schema/state/events -> §6 params
  -> §7 encyclopedia -> §8 validation.

Wave-Out discipline (§9.5-9): live OFI/VPIN acquisition is Wave-Out — the
formulas exist for provided (research/backtest) snapshots and degrade to
QX/UNAVAILABLE when L2 is absent; no live L2 path exists or is implied.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from apex.data_catalog.contracts import (
    EvidenceEvent,
    LifecycleState,
    MarketObservation,
)
from apex.engines.base import EngineBase
from apex.errors import WaveOutError
from apex.identity.snapshot import canonical_snapshot_id
from apex.identity.uuid_v7 import uuid_v7

ENGINE_CODE = "E02_Liquidity"
CONTRACT_VERSION = "4.0.0"
EPS = 1e-8

# ===========================================================================
# §3 FORMULAS — corrected formulas, PIT, edge cases
# ===========================================================================


@dataclass
class Candle:
    open: float
    high: float
    low: float
    close: float
    volume: float
    bar_index: int
    is_closed: bool
    t_close: int

    def to_dict(self) -> Dict[str, float]:
        return {"open": self.open, "high": self.high, "low": self.low,
                "close": self.close, "volume": self.volume,
                "bar_index": self.bar_index}


@dataclass
class Level:
    lid: str
    price: float
    side: str
    ltype: str
    instances: int
    first_seen: int
    last_touch: int
    touch_count: int
    salience: float
    fate: str
    Q: str
    members: List[float] = field(default_factory=list)
    snapshot_id: str = ""
    atr_at_formation: float = 0.0
    evidence_id: str = ""
    strengthen_count: int = 0


@dataclass
class Pool:
    pid: str
    lo: float
    hi: float
    median: float
    weight: float
    member_level_ids: List[str]
    fate: str
    Q: str
    snapshot_id: str = ""


@dataclass
class SweepEvent:
    kind: str
    side: str
    level_id: str
    penetration: float
    rejection: float
    close_return: float
    volume_ratio: float
    score: float
    at_bar: int
    prereq_checks: Dict[str, bool]
    Q: str
    evidence_id: str = ""
    snapshot_id: str = ""


def compute_TR(c: Candle, prev: Optional[Candle]) -> float:
    if prev is None:
        return c.high - c.low
    return max(c.high - c.low, abs(c.high - prev.close),
               abs(c.low - prev.close))


def compute_ATR_wilder(candles: Sequence[Candle], n: int = 14) -> List[float]:
    """§3.2 stable ATR (Wilder RMA); simple mean over the first n."""
    atr: List[float] = []
    trs: List[float] = []
    for i, c in enumerate(candles):
        tr = compute_TR(c, candles[i - 1] if i > 0 else None)
        trs.append(tr)
        if i < n:
            atr.append(sum(trs) / (i + 1))
        else:
            atr.append((atr[-1] * (n - 1) + tr) / n)
    return atr


def generate_snapshot_id(payload: dict) -> str:
    """Deterministic SHA-256 identity (GLOBAL IDENTITY/PIT contract); the
    engine/contract envelope is applied exactly once (Phase 67A)."""
    return canonical_snapshot_id("E02_Liquidity", CONTRACT_VERSION, payload)


def group_equal_levels_hierarchical(
        prices: Sequence[float], atr_now: float,
        theta_eq: float = 0.15) -> List[Dict[str, Any]]:
    """§3.3 chain-preventing hierarchical grouping: complete-linkage split —
    cluster diameter ≤ D_max = 2·θ_eq·ATR and every member within θ_eq·ATR
    of the cluster median. ATR < ε is INVALID (fail-closed)."""
    if not prices:
        return []
    if atr_now < EPS:
        raise ValueError("INVALID_ATR_QX")
    tol = theta_eq * atr_now
    d_max = 2 * tol
    sorted_prices = sorted(prices)
    groups: List[List[float]] = []
    cur = [sorted_prices[0]]
    for p in sorted_prices[1:]:
        if p - cur[0] <= d_max:
            cur.append(p)
        else:
            groups.append(cur)
            cur = [p]
    groups.append(cur)
    final: List[Dict[str, Any]] = []
    for g in groups:
        stack = [g]
        while stack:
            curg = stack.pop()
            curg_sorted = sorted(curg)
            m = len(curg_sorted)
            median = (curg_sorted[m // 2] if m % 2 == 1
                      else (curg_sorted[m // 2 - 1] + curg_sorted[m // 2]) / 2)
            max_dev = max(abs(x - median) for x in curg_sorted)
            if max_dev <= tol + EPS:
                final.append({"members": curg_sorted, "median": median,
                              "diameter": curg_sorted[-1] - curg_sorted[0]})
            else:
                lower = [x for x in curg_sorted if x <= median]
                upper = [x for x in curg_sorted if x > median]
                if lower:
                    stack.append(lower)
                if upper:
                    stack.append(upper)
    return final


def proximity_htf(p_star: float, p_htf: Optional[float],
                  atr_htf: float) -> float:
    """§2: proximity_HTF = exp(−|p*−p_HTF|/(ATR_HTF+ε)); no HTF level → 0."""
    if p_htf is None:
        return 0.0
    return math.exp(-abs(p_star - p_htf) / (atr_htf + EPS))


def freshness(age_bars: int, lambda_decay: float) -> float:
    """Freshness = exp(−λ·Age) (§2)."""
    return math.exp(-lambda_decay * max(0, age_bars))


def compute_salience(level: Level, current_bar: int, atr_htf: float,
                     p_htf_nearest: Optional[float],
                     type_scores: Dict[str, float], w_t: float = 0.3,
                     w_i: float = 0.3, w_f: float = 0.25, w_p: float = 0.15,
                     lambda_decay: float = 0.02) -> float:
    """§3.4: Salience = w_t·type + w_i·min(instances/3,1) +
    w_f·Freshness + w_p·proximity_HTF (weights 0.3/0.3/0.25/0.15)."""
    age = current_bar - level.last_touch
    fresh = freshness(age, lambda_decay)
    prox = proximity_htf(level.price, p_htf_nearest, atr_htf)
    instances_norm = min(level.instances / 3.0, 1.0)
    type_w = type_scores.get(level.ltype, 0.5)
    sal = w_t * type_w + w_i * instances_norm + w_f * fresh + w_p * prox
    return max(0.0, min(1.0, sal))


def dbscan_1d_optimal(levels: Sequence[Level], eps: float,
                      min_pts: int) -> List[List[Level]]:
    """§3.5/§4 one-dimensional DBSCAN, sorted two-pointer neighborhoods,
    O(n log n). NOTE (ISSUE-CP2-010): the operative pool radius passed by
    callers is 2·θ_eq·ATR·κ (the §3.3 D_max scale) — the §7 Ch.2 examples
    and GF_LIQ_003 fix this scale; §3.5's bare θ_eq·ATR·κ contradicts them."""
    if not levels:
        return []
    sorted_levels = sorted(levels, key=lambda l: l.price)
    n = len(sorted_levels)
    visited = [False] * n
    clusters: List[List[Level]] = []
    left = 0
    for i in range(n):
        if visited[i]:
            continue
        while left < n and sorted_levels[i].price - sorted_levels[left].price > eps:
            left += 1
        right = i
        while right + 1 < n and sorted_levels[right + 1].price \
                - sorted_levels[i].price <= eps:
            right += 1
        neighbor_count = right - left + 1
        if neighbor_count >= min_pts:
            cluster: List[Level] = []
            queue = list(range(left, right + 1))
            seen = set()
            while queue:
                idx = queue.pop(0)
                if idx in seen:
                    continue
                seen.add(idx)
                visited[idx] = True
                cluster.append(sorted_levels[idx])
                l2 = idx
                while l2 > 0 and sorted_levels[idx].price \
                        - sorted_levels[l2 - 1].price <= eps:
                    l2 -= 1
                r2 = idx
                while r2 + 1 < n and sorted_levels[r2 + 1].price \
                        - sorted_levels[idx].price <= eps:
                    r2 += 1
                for nb in range(l2, r2 + 1):
                    if nb not in seen:
                        queue.append(nb)
            uniq = {l.lid: l for l in cluster}.values()
            clusters.append(list(uniq))
    return clusters


def adaptive_min_pts(n_active: int) -> int:
    """minPts = max(2, ceil(log(N_active+1))) (§3.5)."""
    return max(2, math.ceil(math.log(n_active + 1)))


def compute_pool_weight(levels_in_pool: Sequence[Level], eps: float) -> float:
    """§3.5: W_pool = Σ salience·√instances·exp(−dist/ε)."""
    if not levels_in_pool:
        return 0.0
    prices = [l.price for l in levels_in_pool]
    p_med = sorted(prices)[len(prices) // 2]
    w = 0.0
    for l in levels_in_pool:
        dist_factor = math.exp(-abs(l.price - p_med) / (eps + EPS))
        w += l.salience * math.sqrt(l.instances) * dist_factor
    return w


def detect_sweep(candle: Candle, level: Level, atr_now: float,
                 volume_sma20: float, sweep_min_pen: float = 0.1,
                 sweep_min_rej: float = 0.2,
                 last_sweep_bar_of_level: int = -999,
                 volume_profile_ok: bool = True
                 ) -> Tuple[str, Dict[str, bool], float]:
    """§3.6 five prerequisites (P1–P5) + SweepScore. Any failure with P1∧P2
    satisfied → WICK_ONLY; otherwise NONE."""
    prereq = {"P1_valid_level": False, "P2_penetration": False,
              "P3_rejection": False, "P4_temporal": False,
              "P5_data_quality": False}
    if candle.high < candle.low or candle.volume <= 0 or atr_now <= EPS:
        return "NONE", prereq, 0.0
    if (level.fate in ("ACTIVE", "STRENGTHENED")
            and level.Q in ("Q1", "Q2")
            and level.first_seen <= candle.bar_index - 1):
        prereq["P1_valid_level"] = True
    else:
        return "WICK_ONLY", prereq, 0.0
    if level.side == "SELL_SIDE":
        pen_abs = max(0.0, candle.high - level.price)
    else:
        pen_abs = max(0.0, level.price - candle.low)
    penetration = pen_abs / max(atr_now, EPS)
    if penetration >= sweep_min_pen:
        prereq["P2_penetration"] = True
    body_top = max(candle.open, candle.close)
    body_bottom = min(candle.open, candle.close)
    if level.side == "SELL_SIDE":
        wick = candle.high - body_top
    else:
        wick = body_bottom - candle.low
    range_c = candle.high - candle.low + EPS
    rejection = wick / range_c
    close_return = 0.0
    if penetration > EPS:
        if level.side == "SELL_SIDE":
            close_return = ((level.price - candle.close)
                            / (penetration * atr_now + EPS)
                            if candle.close < level.price else 0.0)
        else:
            close_return = ((candle.close - level.price)
                            / (penetration * atr_now + EPS)
                            if candle.close > level.price else 0.0)
    if rejection >= sweep_min_rej and close_return >= 0.3:
        prereq["P3_rejection"] = True
    if (level.last_touch < candle.bar_index
            and (candle.bar_index - last_sweep_bar_of_level) >= 3):
        prereq["P4_temporal"] = True
    if candle.volume > 0 and volume_profile_ok:
        prereq["P5_data_quality"] = True
    all_ok = all(prereq.values())
    if not all_ok:
        if prereq["P1_valid_level"] and prereq["P2_penetration"]:
            return "WICK_ONLY", prereq, 0.0
        return "NONE", prereq, 0.0
    norm_pen = math.tanh(penetration / 0.5)
    norm_rej = min(rejection / 0.8, 1.0)
    norm_close = min(max(close_return, 0) / 1.5, 1.0)
    vol_ratio = candle.volume / (volume_sma20 + EPS)
    norm_vol = min(math.log1p(vol_ratio) / math.log1p(3), 1.0)
    false_wick_penalty = 1.0 if (wick > 2 * abs(candle.open - candle.close)
                                 + EPS and close_return < 0.2) else 0.0
    w_p, w_r, w_c, w_v, w_f = 0.25, 0.25, 0.2, 0.2, 0.1
    score = (w_p * norm_pen + w_r * norm_rej + w_c * norm_close
             + w_v * norm_vol - w_f * false_wick_penalty)
    score = max(0.0, min(1.0, score))
    return "SWEEP", prereq, score


def compute_OFI_from_L2_snapshots(snapshots: Sequence[Dict[str, float]]
                                  ) -> List[float]:
    """§3.8 Cont et al. (2013) OFI: OFI_t = e_b − e_a (§4 reference; the
    §7 Ch.4 worked example's e_a sign for a price-up move contradicts the
    formula and GF_LIQ_008 — the fixture is canonical: p_ask↑ → e_a = +q_a)."""
    ofi_series: List[float] = []
    for i in range(1, len(snapshots)):
        prev = snapshots[i - 1]
        cur = snapshots[i]
        if cur["p_ask"] > prev["p_ask"]:
            ea = cur["q_ask"]
        elif cur["p_ask"] < prev["p_ask"]:
            ea = -prev["q_ask"]
        else:
            ea = cur["q_ask"] - prev["q_ask"]
        if cur["p_bid"] > prev["p_bid"]:
            eb = cur["q_bid"]
        elif cur["p_bid"] < prev["p_bid"]:
            eb = -prev["q_bid"]
        else:
            eb = cur["q_bid"] - prev["q_bid"]
        ofi_series.append(eb - ea)
    return ofi_series


def vpin_from_buckets(buckets: Sequence[Dict[str, float]], sigma: float,
                      n_buckets_for_vpin: int = 50) -> float:
    """§3.8 BVC VPIN over volume buckets (Q4)."""
    if len(buckets) < 2:
        return 0.0
    sigma = max(sigma, EPS)
    buy_vols = []
    for b in buckets[-n_buckets_for_vpin:]:
        phi = 0.5 * (1 + math.erf(b["dP"] / (sigma * math.sqrt(2))))
        buy_vols.append(b["V"] * phi)
    tail = buckets[-n_buckets_for_vpin:]
    imbalance = sum(abs(vb * 2 - tail[i]["V"])
                    for i, vb in enumerate(buy_vols))
    total_v = sum(b["V"] for b in tail)
    vpin = imbalance / (total_v + EPS)
    return max(0.0, min(1.0, vpin))


def compute_VPIN(candles: Sequence[Candle], bucket_volume: float,
                 sigma_lookback: int = 50,
                 n_buckets_for_vpin: int = 50) -> float:
    """§4 reference: bucket candles by volume, then BVC (Q4)."""
    buckets: List[Dict[str, float]] = []
    cur_vol = 0.0
    cur_start: Optional[float] = None
    cur_prices: List[float] = []
    for c in candles:
        if cur_start is None:
            cur_start = c.close
        cur_vol += c.volume
        cur_prices.append(c.close)
        if cur_vol >= bucket_volume:
            dP = cur_prices[-1] - cur_start
            buckets.append({"V": cur_vol, "dP": dP})
            cur_vol = 0.0
            cur_start = None
            cur_prices = []
    if len(buckets) < 2:
        return 0.0
    dPs = [b["dP"] for b in buckets]
    sigma = statistics.pstdev(dPs[-sigma_lookback:]) if len(dPs) >= 2 else 1.0
    sigma = max(sigma, EPS)
    return vpin_from_buckets(buckets, sigma, n_buckets_for_vpin)


def kyle_lambda(price_changes: Sequence[float],
                volumes: Sequence[float]) -> Optional[float]:
    """§3.8 Kyle's λ: λ = Cov(ΔP,Q)/Var(Q)."""
    n = min(len(price_changes), len(volumes))
    if n < 3:
        return None
    dp = price_changes[-n:]
    q = volumes[-n:]
    mean_dp = sum(dp) / n
    mean_q = sum(q) / n
    cov = sum((dp[i] - mean_dp) * (q[i] - mean_q) for i in range(n)) / n
    var_q = sum((x - mean_q) ** 2 for x in q) / n
    if var_q < EPS:
        return None
    return cov / var_q


def glosten_milgrom_half_spread(vpin: float, sigma: float) -> float:
    """§3.8: half-spread ≈ ασ with α estimated from VPIN."""
    return vpin * sigma


def identify_liquidity_voids_LVN(
        levels: Sequence[Level], volume_profile: Dict[float, float],
        atr_now: float, void_gap_mult: float = 2.5,
        lvn_percentile: float = 15.0) -> List[Dict[str, Any]]:
    """§2/§3.9 LVN Void: gap ≥ void_gap·ATR between adjacent sorted levels,
    aggregated volume inside ≤ lvn_percentile% of total profile volume, and
    no ACTIVE level strictly inside. (The §4 reference's bin-count
    percentile fails GF_LIQ_007 — ISSUE-CP2-011; §2's aggregated-share
    reading is authoritative and satisfies the fixture.)"""
    if not levels or atr_now <= EPS:
        return []
    sorted_levels = sorted(levels, key=lambda l: l.price)
    vols = list(volume_profile.values())
    if not vols:
        return []
    total = sum(vols)
    if total <= EPS:
        return []
    lvn_thresh = lvn_percentile / 100.0 * total
    voids: List[Dict[str, Any]] = []
    for i in range(len(sorted_levels) - 1):
        p_a = sorted_levels[i].price
        p_b = sorted_levels[i + 1].price
        gap = p_b - p_a
        if gap >= void_gap_mult * atr_now:
            inside_vols = [v for price_bin, v in volume_profile.items()
                           if p_a < price_bin < p_b]
            inside_sum = sum(inside_vols)
            active_inside = any(p_a < l.price < p_b for l in sorted_levels)
            if inside_vols and inside_sum <= lvn_thresh and not active_inside:
                voids.append({"lo": p_a, "hi": p_b, "gap_ATR": gap / atr_now,
                              "max_vol_inside": max(inside_vols),
                              "volume_inside": inside_sum,
                              "lvn_threshold": lvn_thresh,
                              "type": "VOID"})
    return voids


def merton_hit_probability(distance_atr: float, atr: float,
                           sigma_ret: float, T_bars: int,
                           lambda_j: float = 0.02, mu_j: float = 0.0,
                           sigma_j: float = 0.02,
                           price: Optional[float] = None) -> float:
    """§3.7 Merton jump-diffusion hit probability (Q4).

    P_Merton ≈ 2Φ(−d/(σ_eff√T)) + λ_J·T·Φ(−(d−|μ_J|)/σ_J),
    σ_eff = sqrt(σ² + λ_J(μ_J² + σ_J²)).

    Distance is converted to log/return units first: with `price` given,
    d = distance_price/price (the §9 Step-10 conversion); without, the ATR
    proxy d = distance_atr·σ_ret (one ATR ≈ one σ_ret return) — both
    reproduce §9 and GF_LIQ_012; the raw §4 form contradicts both
    (ISSUE-CP2-012)."""
    if price is not None and price > EPS:
        d = (distance_atr * atr) / price
    else:
        d = distance_atr * sigma_ret
    sigma_eff = math.sqrt(sigma_ret ** 2 + lambda_j * (mu_j ** 2 + sigma_j ** 2))
    sigma_eff = max(sigma_eff, EPS)
    arg = -abs(d) / (sigma_eff * math.sqrt(T_bars + EPS))
    p_brown = 2 * (0.5 * (1 + math.erf(arg / math.sqrt(2))))
    p_jump = lambda_j * T_bars * 0.5 * (
        1 + math.erf((-abs(d) + abs(mu_j)) / (sigma_j * math.sqrt(2) + EPS)))
    p_total = min(1.0, p_brown + p_jump)
    return max(0.0, p_total)


def brownian_hit_probability(distance_atr: float, atr: float,
                             sigma_ret: float, T_bars: int,
                             price: Optional[float] = None) -> float:
    """Plain Brownian baseline 2Φ(−d/(σ√T)) for comparison (§3.7)."""
    if price is not None and price > EPS:
        d = (distance_atr * atr) / price
    else:
        d = distance_atr * sigma_ret
    arg = -abs(d) / (max(sigma_ret, EPS) * math.sqrt(T_bars + EPS))
    return max(0.0, 2 * (0.5 * (1 + math.erf(arg / math.sqrt(2)))))


def estimate_merton_parameters(candles: Sequence[Candle],
                               lookback: int = 100) -> Dict[str, float]:
    """§3.7 estimation: σ from 100-candle log returns; λ_J from the observed
    rate of >3σ jumps; μ_J/σ_J from jump returns (defaults when sparse)."""
    closes = [c.close for c in candles[-(lookback + 1):]]
    if len(closes) < 3:
        return {"sigma_ret": 0.02, "lambda_j": 0.02, "mu_j": 0.0,
                "sigma_j": 0.02, "n": len(closes)}
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    mu = sum(rets) / len(rets)
    sigma_ret = math.sqrt(sum((r - mu) ** 2 for r in rets) / len(rets))
    sigma_ret = max(sigma_ret, EPS)
    jumps = [r for r in rets if abs(r) > 3 * sigma_ret]
    lambda_j = len(jumps) / len(rets)
    if len(jumps) >= 2:
        mu_j = sum(jumps) / len(jumps)
        sigma_j = math.sqrt(sum((j - mu_j) ** 2 for j in jumps)
                            / len(jumps))
    else:
        mu_j, sigma_j = 0.0, 0.02
    return {"sigma_ret": sigma_ret, "lambda_j": lambda_j, "mu_j": mu_j,
            "sigma_j": max(sigma_j, EPS), "n": len(rets)}


def detect_raid(sweeps: Sequence[Dict[str, Any]],
                raid_window: int = 3) -> List[Dict[str, Any]]:
    """§2: Raid = >=2 same-direction levels swept in continuous succession
    within <= raid_window candles (GF_LIQ_006)."""
    by_side: Dict[str, List[Dict[str, Any]]] = {}
    for s in sweeps:
        by_side.setdefault(s.get("side", "SELL_SIDE"), []).append(s)
    raids: List[Dict[str, Any]] = []
    for side, ss in by_side.items():
        ss = sorted(ss, key=lambda x: x["at"])
        for i in range(len(ss)):
            window = [x for x in ss
                      if 0 <= x["at"] - ss[i]["at"] <= raid_window]
            if len(window) >= 2:
                raids.append({"side": side, "count": len(window),
                              "sweeps": window})
                break
    return raids


def wilson_ci(p_hat: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    """§8.5 Wilson CI."""
    if n <= 0:
        raise ValueError("WILSON_N_MUST_BE_POSITIVE")
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
            ) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def poisson_significance(instances: int, expected: float) -> float:
    """Encyclopedia Ch.1 §1: Poisson significance test for level validity —
    P(X ≥ instances) under Poisson(expected); p < 0.05 → significant."""
    if expected <= EPS:
        return 0.0
    term = math.exp(-expected)
    cumulative = term
    for k in range(instances):
        term *= expected / (k + 1)
        cumulative += term if k < instances - 1 else 0.0
    # P(X >= instances) = 1 - P(X <= instances-1)
    term = math.exp(-expected)
    cum_le = term
    for k in range(1, instances):
        term *= expected / k
        cum_le += term
    return max(0.0, min(1.0, 1.0 - cum_le))


def jaccard_index(a: set, b: set) -> float:
    """Encyclopedia Ch.2 §14: pool stability via Jaccard (>0.5 = stable)."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ===========================================================================
# §4 ALGORITHMS — streaming engine (idempotent, O(m log m) per candle)
# ===========================================================================

UTC_ACTIVITY_WINDOWS: List[Tuple[str, float, float]] = [
    ("UTC_W0", 0.0, 7.0), ("UTC_W1", 7.0, 12.5),
    ("UTC_W2", 12.5, 21.0), ("UTC_W3", 21.0, 24.0),
]


def utc_window_of(hour_float: float) -> str:
    for name, lo, hi in UTC_ACTIVITY_WINDOWS:
        if lo <= hour_float < hi:
            return name
    return "UTC_W3"   # 24.0 boundary folds to the last window


def detect_swing_extremes(candles: Sequence[Candle], k: int = 2
                          ) -> List[Dict[str, Any]]:
    """E02-internal confirmed swing detection (k-bar local extremes) — the
    touch source for SWING_EXTREME levels. E01 swings arrive via
    SwingInput.v1 (feed_touches) when available (§1.2)."""
    out: List[Dict[str, Any]] = []
    n = len(candles)
    if n < 2 * k + 1:
        return out
    for t in range(k, n - k):
        c = candles[t]
        left_h = max(candles[t - i].high for i in range(1, k + 1))
        right_h = max(candles[t + i].high for i in range(1, k + 1))
        if c.high > left_h and c.high > right_h:
            out.append({"price": c.high, "bar": c.bar_index, "kind": "HIGH"})
        left_l = min(candles[t - i].low for i in range(1, k + 1))
        right_l = min(candles[t + i].low for i in range(1, k + 1))
        if c.low < left_l and c.low < right_l:
            out.append({"price": c.low, "bar": c.bar_index, "kind": "LOW"})
    return out


class LiquidityEngineV4:
    """Streaming liquidity engine (§4). State: levels, pools, last-sweep
    bookkeeping, candle history. Idempotent per bar_index."""

    def __init__(self, theta_eq: float = 0.15, sweep_min_pen: float = 0.1,
                 sweep_min_rej: float = 0.2, lambda_decay: float = 0.02,
                 kappa: float = 1.0, raid_window: int = 3,
                 level_expiry_bars: int = 96, invalid_break_atr: float = 1.5,
                 void_gap: float = 2.5, lvn_percentile: float = 15.0,
                 salience_weights: Optional[Dict[str, float]] = None,
                 type_scores: Optional[Dict[str, float]] = None,
                 sweep_weights: Optional[List[float]] = None,
                 volume_profile_bars: int = 100, vp_bins: int = 50):
        self.theta_eq = theta_eq
        self.sweep_min_pen = sweep_min_pen
        self.sweep_min_rej = sweep_min_rej
        self.lambda_decay = lambda_decay
        self.kappa = kappa
        self.raid_window = raid_window
        self.level_expiry_bars = level_expiry_bars
        self.invalid_break_atr = invalid_break_atr
        self.void_gap = void_gap
        self.lvn_percentile = lvn_percentile
        self.salience_weights = salience_weights or {
            "w_t": 0.3, "w_i": 0.3, "w_f": 0.25, "w_p": 0.15}
        self.type_scores = type_scores or {
            "EQUAL_HIGH": 1.0, "EQUAL_LOW": 1.0,
            "UTC_ACTIVITY_WINDOW_EXTREME": 0.9, "SWING_EXTREME": 0.8,
            "RANGE_EDGE": 0.6, "VOID_EDGE": 0.5}
        self.sweep_weights = sweep_weights or [0.25, 0.25, 0.2, 0.2, 0.1]
        self.volume_profile_bars = volume_profile_bars
        self.vp_bins = vp_bins
        self.levels: Dict[str, Level] = {}
        self.pools: Dict[str, Pool] = {}
        self.last_sweep_bar: Dict[str, int] = {}
        self.candles: List[Candle] = []
        self.events: List[Dict[str, Any]] = []
        self.open_voids: List[Dict[str, Any]] = []
        self.sweep_log: List[Dict[str, Any]] = []
        self._window_extreme: Dict[str, Dict[str, Any]] = {}
        self.htf_levels: List[Dict[str, Any]] = []
        self.atr_htf: float = 0.0
        self.l2_available = False
        self.ofi_series: List[float] = []
        self.vpin: Optional[float] = None
        self._pending_touches: List[Tuple[float, int, str]] = []
        # D35(e) P2: ISSUE-031-pattern within-run ATR(14) prefix memo,
        # (candles list, length, last value) or None when cold. The
        # engine never escapes its run, candles are append-only with
        # immutable OHLC, so identity+length keys are exact; any mismatch
        # falls back to the verbatim full recomputation.
        self._atr14_memo = None

    # -- input wiring ----------------------------------------------------
    def set_htf(self, htf_levels: Sequence[Dict[str, Any]],
                atr_htf: float) -> None:
        """HTF level list + ATR_HTF for proximity_HTF (§3.4); absent →
        proximity = 0 (no fabricated HTF)."""
        self.htf_levels = list(htf_levels or [])
        self.atr_htf = float(atr_htf or 0.0)

    def feed_touches(self, touches: Sequence[Dict[str, Any]]) -> None:
        """SwingInput.v1 external touches: {price, bar_index, type, confirmed}."""
        for t in touches or []:
            if not t.get("confirmed", True):
                continue
            self._ingest_touch(float(t["price"]), int(t["bar_index"]),
                               t.get("ltype", "SWING_EXTREME"))

    def _nearest_htf(self, price: float) -> Optional[float]:
        if not self.htf_levels:
            return None
        return min((abs(price - float(h["price"])), float(h["price"]))
                   for h in self.htf_levels)[1]

    def _atr_wilder14_last(self) -> float:
        """Last value of compute_ATR_wilder(self.candles, 14), memoized.

        D35(e) P2, ISSUE-031 pattern: within one run the candles list only
        grows and its OHLC never mutates, so when the list identity and
        length match the memo the repeated O(n) Wilder loop collapses to
        an O(1) extension that repeats the verbatim loop's final Wilder
        iteration identically (same operands, same order, bitwise same).
        The SMA warmup phase (length <= 14), empty candles (0.0, exactly
        as the _ingest_touch guard), and any identity/length mismatch
        use the verbatim full recomputation. No formula change.
        """
        n = 14
        candles = self.candles
        if not candles:
            return 0.0
        memo = self._atr14_memo
        # Identity (not id()) keys the memo: the memoed list stays alive
        # via this same reference, so address reuse can never alias it,
        # and a copied engine still hits only on its own equal list.
        if memo is not None and memo[0] is candles and memo[1] == len(candles):
            return memo[2]
        if memo is not None and memo[0] is candles and len(candles) > memo[1] > n:
            value = memo[2]
            for i in range(memo[1], len(candles)):
                tr = compute_TR(candles[i], candles[i - 1])
                value = (value * (n - 1) + tr) / n
            self._atr14_memo = (candles, len(candles), value)
            return value
        value = compute_ATR_wilder(candles, n)[-1]
        self._atr14_memo = (candles, len(candles), value)
        return value

    # -- core streaming ---------------------------------------------------
    def on_new_closed_candle(self, c: Candle,
                             htfs: Optional[Sequence[Dict[str, Any]]] = None,
                             l2_snapshots: Optional[
                                 Sequence[Dict[str, float]]] = None
                             ) -> List[Dict[str, Any]]:
        """Process one closed candle; returns the events it produced."""
        if any(x.bar_index == c.bar_index for x in self.candles):
            return []
        if c.high < c.low:
            self.events.append({"event_type": "EV_LIQ_000", "at_bar":
                                c.bar_index, "level_id": "", "Q": "Q0",
                                "evidence_id": uuid_v7(),
                                "snapshot_id": generate_snapshot_id(
                                    {"invalid": c.bar_index}),
                                "payload": {"high": c.high, "low": c.low}})
            return [self.events[-1]]
        self.candles.append(c)
        atr_now = self._atr_wilder14_last()
        vol_sma = (sum(x.volume for x in self.candles[-20:])
                   / min(20, len(self.candles)))
        new_events: List[Dict[str, Any]] = []
        # retry cold-start queued touches now that ATR exists
        if self._pending_touches and atr_now > EPS:
            pending, self._pending_touches = self._pending_touches, []
            for price, bar, ltype in pending:
                new_events.extend(self._ingest_touch(price, bar, ltype))
        if htfs:
            self.set_htf(htfs.get("levels", []), htfs.get("atr_htf", 0.0))
        if l2_snapshots:
            self.l2_available = True
            self.ofi_series = compute_OFI_from_L2_snapshots(l2_snapshots)
        else:
            self.l2_available = False

        # 1) touch ingestion: internal swing extremes confirmed this bar
        for sw in self._new_swing_confirmed():
            evs = self._ingest_touch(sw["price"], sw["bar"],
                                     "SWING_EXTREME")
            new_events.extend(evs)
        # UTC activity-window extremes (completed windows)
        new_events.extend(self._ingest_window_extreme(c, atr_now))
        # range edges (rolling 20-bar extremes, on change)
        new_events.extend(self._ingest_range_edges(atr_now))

        # 2) salience refresh + fate transitions
        new_events.extend(self._update_fates(c, atr_now))

        # 3) sweep detection over ACTIVE levels
        new_events.extend(self._detect_sweeps(c, atr_now, vol_sma))

        # 4) pools (DBSCAN over ACTIVE levels)
        new_events.extend(self._update_pools(atr_now))

        # 5) voids (LVN) + fills
        new_events.extend(self._update_voids(c, atr_now))

        # 6) VPIN (Q4 statistical context; bucket_volume = SMA×0.5)
        if len(self.candles) >= 20:
            bucket_volume = max(vol_sma * 0.5, EPS)
            self.vpin = compute_VPIN(self.candles, bucket_volume)
        self.events.extend(new_events)
        return new_events

    # -- helpers ----------------------------------------------------------
    def _new_swing_confirmed(self) -> List[Dict[str, Any]]:
        out = []
        n = len(self.candles)
        k = 2
        if n < 2 * k + 1:
            return out
        t = n - 1 - k
        c = self.candles[t]
        left_h = max(self.candles[t - i].high for i in range(1, k + 1))
        right_h = max(self.candles[t + i].high for i in range(1, k + 1))
        if c.high > left_h and c.high > right_h:
            out.append({"price": c.high, "bar": c.bar_index, "kind": "HIGH"})
        left_l = min(self.candles[t - i].low for i in range(1, k + 1))
        right_l = min(self.candles[t + i].low for i in range(1, k + 1))
        if c.low < left_l and c.low < right_l:
            out.append({"price": c.low, "bar": c.bar_index, "kind": "LOW"})
        return out

    def _ingest_touch(self, price: float, bar: int,
                      ltype: str) -> List[Dict[str, Any]]:
        """Merge into an existing equal-level group (§3.3 tolerance) or form
        a new level (§9 Step 1/2/3 semantics). Touches arriving before the
        ATR warmup exists are queued deterministically (cold-start swings)."""
        atr_now = self._atr_wilder14_last()
        if atr_now <= EPS:
            self._pending_touches.append((price, bar, ltype))
            return []
        tol = self.theta_eq * atr_now
        side = self._side_of(price)
        events: List[Dict[str, Any]] = []
        candidates = [(abs(price - lv.price), lid, lv)
                      for lid, lv in self.levels.items()
                      if lv.side == side
                      and lv.fate in ("FORMED", "ACTIVE", "STRENGTHENED")
                      and abs(price - lv.price) <= tol]
        stream_bar = (self.candles[-1].bar_index if self.candles else bar)
        if candidates:
            _, lid, lv = min(candidates)
            lv.members.append(price)
            lv.instances = len(lv.members)
            lv.touch_count += 1
            lv.last_touch = bar
            lv.price = sorted(lv.members)[len(lv.members) // 2]
            lv.strengthen_count += 1
            if lv.instances >= 2 and lv.ltype in ("SWING_EXTREME",
                                                  "UTC_ACTIVITY_WINDOW_"
                                                  "EXTREME", "RANGE_EDGE",
                                                  "VOID_EDGE"):
                lv.ltype = ("EQUAL_HIGH" if side == "SELL_SIDE"
                            else "EQUAL_LOW")
            sid = generate_snapshot_id({"lid": lid, "inst":
                                        lv.instances, "bar": bar})
            ev = {"event_type": "EV_LIQ_002", "at_bar": stream_bar,
                  "level_id": lid,
                  "Q": lv.Q, "evidence_id": uuid_v7(), "snapshot_id": sid,
                  "payload": {"price": lv.price, "instances": lv.instances,
                              "members": lv.members, "touch_bar": bar}}
            events.append(ev)
            if lv.fate == "ACTIVE":
                lv.fate = "STRENGTHENED"
        else:
            lid = f"lvl_{price:.10g}_{bar}"
            lv = Level(lid=lid, price=price, side=side, ltype=ltype,
                       instances=1, first_seen=bar, last_touch=bar,
                       touch_count=1, salience=0.0, fate="FORMED", Q="Q1",
                       members=[price], atr_at_formation=atr_now,
                       snapshot_id=generate_snapshot_id({"lid": lid}),
                       evidence_id=uuid_v7())
            self.levels[lid] = lv
            sid = generate_snapshot_id({"lid": lid, "formed": bar})
            ev = {"event_type": "EV_LIQ_001", "at_bar": stream_bar,
                  "level_id": lid,
                  "Q": "Q1", "evidence_id": uuid_v7(), "snapshot_id": sid,
                  "payload": {"price": price, "ltype": ltype,
                              "atr_at_formation": atr_now,
                              "touch_bar": bar}}
            events.append(ev)
        return events

    def _side_of(self, price: float) -> str:
        if not self.candles:
            return "SELL_SIDE"
        return "BUY_SIDE" if price < self.candles[-1].close else "SELL_SIDE"

    def _ingest_window_extreme(self, c: Candle,
                               atr_now: float) -> List[Dict[str, Any]]:
        """UTC activity-window extremes (§6 utc_activity_windows): when a
        window boundary is crossed, the completed window's high/low become
        UTC_ACTIVITY_WINDOW_EXTREME touches (fixed UTC boundaries — DST only
        affects local display, §3.1)."""
        events: List[Dict[str, Any]] = []
        hour = ((c.t_close // 3600) % 24) + (c.t_close % 3600) / 3600.0
        window = utc_window_of(hour)
        prev_window = getattr(self, "_last_window", None)
        tracker = self._window_extreme.get(window)
        if tracker is None:
            self._window_extreme[window] = {"high": c.high, "low": c.low,
                                            "high_bar": c.bar_index,
                                            "low_bar": c.bar_index}
        else:
            if c.high > tracker["high"]:
                tracker["high"] = c.high
                tracker["high_bar"] = c.bar_index
            if c.low < tracker["low"]:
                tracker["low"] = c.low
                tracker["low_bar"] = c.bar_index
        if prev_window is not None and prev_window != window:
            done = self._window_extreme.get(prev_window)
            if done:
                events.extend(self._ingest_touch(
                    done["high"], done["high_bar"],
                    "UTC_ACTIVITY_WINDOW_EXTREME"))
                events.extend(self._ingest_touch(
                    done["low"], done["low_bar"],
                    "UTC_ACTIVITY_WINDOW_EXTREME"))
                # the completed window instance is retired; a later
                # same-name window (next UTC day) starts a fresh tracker
                self._window_extreme.pop(prev_window, None)
        self._last_window = window
        return events

    def _ingest_range_edges(self, atr_now: float) -> List[Dict[str, Any]]:
        """Rolling 20-bar range edges as RANGE_EDGE touches (§2 level
        sources: 'a range edge')."""
        if len(self.candles) < 20 or atr_now <= EPS:
            return []
        window = self.candles[-20:]
        hi = max(c.high for c in window)
        lo = min(c.low for c in window)
        events: List[Dict[str, Any]] = []
        for price, kind in ((hi, "RANGE_EDGE_HI"), (lo, "RANGE_EDGE_LO")):
            tol = self.theta_eq * atr_now
            existing = [lv for lv in self.levels.values()
                        if abs(lv.price - price) <= tol
                        and lv.fate in ("FORMED", "ACTIVE", "STRENGTHENED")]
            if not existing:
                events.extend(self._ingest_touch(
                    price, window[-1].bar_index, "RANGE_EDGE"))
        return events

    def _update_fates(self, c: Candle,
                      atr_now: float) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        p_htf_nearest_cache: Dict[str, Optional[float]] = {}
        for lid, lv in list(self.levels.items()):
            if lv.fate in ("SWEPT", "INVALIDATED", "EXPIRED"):
                continue
            # ACTIVE from formation_bar + 1 (PIT)
            if lv.fate == "FORMED" and c.bar_index >= lv.first_seen + 1:
                lv.fate = "ACTIVE"
            p_htf = p_htf_nearest_cache.get(lv.side)
            if p_htf is None:
                p_htf = self._nearest_htf(lv.price)
                p_htf_nearest_cache[lv.side] = p_htf
            lv.salience = compute_salience(
                lv, c.bar_index, self.atr_htf, p_htf, self.type_scores,
                self.salience_weights["w_t"], self.salience_weights["w_i"],
                self.salience_weights["w_f"], self.salience_weights["w_p"],
                self.lambda_decay)
            # Q2 upgrade (§1.5)
            if (lv.instances >= 3 and lv.salience >= 0.7
                    and (c.bar_index - lv.first_seen) <= self.level_expiry_bars
                    / 2 and lv.strengthen_count >= 1):
                lv.Q = "Q2"
            # short ATR sample → Q3 (§1.5)
            if len(self.candles) < 14 and lv.Q == "Q1":
                lv.Q = "Q3"
            # expiry
            age = c.bar_index - lv.last_touch
            if (age > self.level_expiry_bars or lv.salience < 0.1) \
                    and lv.fate != "FORMED":
                lv.fate = "EXPIRED"
                events.append({"event_type": "EV_LIQ_011", "at_bar":
                               c.bar_index, "level_id": lid, "Q": lv.Q,
                               "evidence_id": uuid_v7(),
                               "snapshot_id": generate_snapshot_id(
                                   {"lid": lid, "expired": c.bar_index}),
                               "payload": {"age": age,
                                           "salience": lv.salience}})
                continue
            # invalidation: close beyond the level WITHOUT return — a
            # SELL_SIDE level (above price) is broken upward, a BUY_SIDE
            # level (below price) is broken downward
            if lv.fate in ("ACTIVE", "STRENGTHENED"):
                if lv.side == "SELL_SIDE" and c.close > lv.price \
                        + self.invalid_break_atr * atr_now:
                    lv.fate = "INVALIDATED"
                    events.append({
                        "event_type": "EV_LIQ_013", "at_bar": c.bar_index,
                        "level_id": lid, "Q": lv.Q,
                        "evidence_id": uuid_v7(),
                        "snapshot_id": generate_snapshot_id(
                            {"lid": lid, "inv": c.bar_index}),
                        "payload": {"close": c.close, "price": lv.price,
                                    "break_atr": (c.close - lv.price)
                                    / max(atr_now, EPS)}})
                elif lv.side == "BUY_SIDE" and c.close < lv.price \
                        - self.invalid_break_atr * atr_now:
                    lv.fate = "INVALIDATED"
                    events.append({
                        "event_type": "EV_LIQ_013", "at_bar": c.bar_index,
                        "level_id": lid, "Q": lv.Q,
                        "evidence_id": uuid_v7(),
                        "snapshot_id": generate_snapshot_id(
                            {"lid": lid, "inv": c.bar_index}),
                        "payload": {"close": c.close, "price": lv.price,
                                    "break_atr": (lv.price - c.close)
                                    / max(atr_now, EPS)}})
        return events

    def _detect_sweeps(self, c: Candle, atr_now: float,
                       vol_sma: float) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for lid, lv in list(self.levels.items()):
            if lv.fate not in ("ACTIVE", "STRENGTHENED"):
                continue
            kind, prereq, score = detect_sweep(
                c, lv, atr_now, vol_sma, self.sweep_min_pen,
                self.sweep_min_rej, self.last_sweep_bar.get(lid, -999),
                volume_profile_ok=True)
            if kind == "SWEEP":
                lv.fate = "SWEPT"
                self.last_sweep_bar[lid] = c.bar_index
                side_name = ("BuySide" if lv.side == "BUY_SIDE"
                             else "SellSide")
                ev_type = ("EV_LIQ_005" if lv.side == "BUY_SIDE"
                           else "EV_LIQ_006")
                pen_abs = (max(0.0, c.high - lv.price)
                           if lv.side == "SELL_SIDE"
                           else max(0.0, lv.price - c.low))
                body_top = max(c.open, c.close)
                wick = (c.high - body_top if lv.side == "SELL_SIDE"
                        else min(c.open, c.close) - c.low)
                rejection = wick / (c.high - c.low + EPS)
                penetration = pen_abs / max(atr_now, EPS)
                close_return = (abs(lv.price - c.close)
                                / (penetration * atr_now + EPS)
                                if penetration > EPS else 0.0)
                sweep_ev = SweepEvent(
                    kind="SWEEP", side=lv.side, level_id=lid,
                    penetration=penetration, rejection=rejection,
                    close_return=close_return,
                    volume_ratio=(c.volume / (vol_sma + EPS)),
                    score=score, at_bar=c.bar_index, prereq_checks=prereq,
                    Q="Q1" if lv.Q == "Q1" else "Q2",
                    evidence_id=uuid_v7(),
                    snapshot_id=generate_snapshot_id(
                        {"lid": lid, "sweep": c.bar_index}))
                self.sweep_log.append({"level_id": lid, "side": lv.side,
                                       "at_bar": c.bar_index,
                                       "score": score})
                events.append({"event_type": ev_type, "at_bar": c.bar_index,
                               "level_id": lid, "Q": sweep_ev.Q,
                               "evidence_id": sweep_ev.evidence_id,
                               "snapshot_id": sweep_ev.snapshot_id,
                               "payload": {"score": score, "side":
                                           side_name,
                                           "prereq": prereq}})
            elif kind == "WICK_ONLY":
                events.append({
                    "event_type": "EV_LIQ_007", "at_bar": c.bar_index,
                    "level_id": lid, "Q": "Q3",
                    "evidence_id": uuid_v7(),
                    "snapshot_id": generate_snapshot_id(
                        {"lid": lid, "wick": c.bar_index}),
                    "payload": {"prereq": prereq}})
        # Raid: >=2 same-direction sweeps within raid_window bars
        for side in ("BUY_SIDE", "SELL_SIDE"):
            recent = [s for s in self.sweep_log
                      if s["side"] == side
                      and c.bar_index - s["at_bar"] <= self.raid_window]
            if len(recent) >= 2:
                already = {e["level_id"] for e in events
                           if e["event_type"] == "EV_LIQ_008"
                           and e["payload"].get("side") == side}
                if not already:
                    events.append({
                        "event_type": "EV_LIQ_008", "at_bar": c.bar_index,
                        "level_id": recent[-1]["level_id"], "Q": "Q2",
                        "evidence_id": uuid_v7(),
                        "snapshot_id": generate_snapshot_id(
                            {"raid": side, "bar": c.bar_index}),
                        "payload": {"side": side,
                                    "count": len(recent),
                                    "scores": [r["score"] for r in recent]}})
        return events

    def _update_pools(self, atr_now: float) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        active = [lv for lv in self.levels.values()
                  if lv.fate in ("ACTIVE", "STRENGTHENED")]
        if not active or atr_now <= EPS:
            return events
        eps_pool = 2 * self.theta_eq * atr_now * self.kappa
        min_pts = adaptive_min_pts(len(active))
        clusters = dbscan_1d_optimal(active, eps_pool, min_pts)
        new_member_sets: Dict[str, set] = {}
        for cluster in clusters:
            prices = [l.price for l in cluster]
            lo, hi = min(prices), max(prices)
            pid = f"pool_{lo:.10g}_{hi:.10g}"
            weight = compute_pool_weight(cluster, eps_pool)
            median = sorted(prices)[len(prices) // 2]
            new_member_sets[pid] = {l.lid for l in cluster}
            if pid not in self.pools:
                self.pools[pid] = Pool(pid=pid, lo=lo, hi=hi, median=median,
                                       weight=weight,
                                       member_level_ids=[l.lid for l in
                                                         cluster],
                                       fate="ACTIVE", Q="Q1",
                                       snapshot_id=generate_snapshot_id(
                                           {"pid": pid, "members": sorted(
                                               new_member_sets[pid])}))
                events.append({"event_type": "EV_LIQ_003",
                               "at_bar": self.candles[-1].bar_index,
                               "level_id": pid, "Q": "Q1",
                               "evidence_id": uuid_v7(),
                               "snapshot_id": self.pools[pid].snapshot_id,
                               "payload": {"weight": weight, "lo": lo,
                                           "hi": hi}})
            else:
                pool = self.pools[pid]
                if not new_member_sets[pid].issubset(set(pool.member_level_ids)):
                    pool.member_level_ids = [l.lid for l in cluster]
                    pool.weight = weight
                    events.append({
                        "event_type": "EV_LIQ_004",
                        "at_bar": self.candles[-1].bar_index,
                        "level_id": pid, "Q": "Q1", "evidence_id": uuid_v7(),
                        "snapshot_id": generate_snapshot_id(
                            {"pid": pid, "exp": sorted(new_member_sets[pid])}),
                        "payload": {"weight": weight, "lo": lo, "hi": hi}})
        # pool swept when every member is terminal
        for pid, pool in self.pools.items():
            if pool.fate == "ACTIVE" and pool.member_level_ids:
                states = [self.levels[m].fate for m in pool.member_level_ids
                          if m in self.levels]
                if states and all(s in ("SWEPT", "INVALIDATED", "EXPIRED")
                                  for s in states):
                    pool.fate = "SWEPT"
                    events.append({
                        "event_type": "EV_LIQ_012",
                        "at_bar": self.candles[-1].bar_index,
                        "level_id": pid, "Q": "Q1",
                        "evidence_id": uuid_v7(),
                        "snapshot_id": generate_snapshot_id(
                            {"pid": pid, "swept": 1}),
                        "payload": {"weight": pool.weight}})
        return events

    def _volume_profile(self) -> Dict[float, float]:
        """§3.9 VP over the last 100 candles, 50 bins; a candle contributes
        its volume to every bin its [L,H] range spans."""
        window = self.candles[-self.volume_profile_bars:]
        if not window:
            return {}
        lo = min(c.low for c in window)
        hi = max(c.high for c in window)
        if hi <= lo:
            return {lo: sum(c.volume for c in window)}
        width = (hi - lo) / self.vp_bins
        profile: Dict[float, float] = {}
        for c in window:
            b0 = int((c.low - lo) / width)
            b1 = int((c.high - lo) / width)
            per_bin = c.volume / max(1, b1 - b0 + 1)
            for b in range(max(0, b0), min(self.vp_bins - 1, b1) + 1):
                key = round(lo + (b + 0.5) * width, 10)
                profile[key] = profile.get(key, 0.0) + per_bin
        return profile

    def _update_voids(self, c: Candle, atr_now: float
                      ) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        active = [lv for lv in self.levels.values()
                  if lv.fate in ("ACTIVE", "STRENGTHENED")]
        profile = self._volume_profile()
        if not profile or atr_now <= EPS:
            return events
        voids = identify_liquidity_voids_LVN(
            active, profile, atr_now, self.void_gap, self.lvn_percentile)
        for v in voids:
            key = (round(v["lo"], 10), round(v["hi"], 10))
            if key not in [(round(x["lo"], 10), round(x["hi"], 10))
                           for x in self.open_voids]:
                v["formed_bar"] = c.bar_index
                v["lvn_threshold_bin"] = None
                self.open_voids.append(v)
                events.append({
                    "event_type": "EV_LIQ_009", "at_bar": c.bar_index,
                    "level_id": f"void_{v['lo']:.10g}_{v['hi']:.10g}",
                    "Q": "Q5", "evidence_id": uuid_v7(),
                    "snapshot_id": generate_snapshot_id(
                        {"void": key, "bar": c.bar_index}),
                    "payload": {"lo": v["lo"], "hi": v["hi"],
                                "gap_ATR": v["gap_ATR"],
                                "volume_inside": v["volume_inside"]}})
        # fills: full traversal within void_fill_bars + volume >= 1.5x thresh
        total = sum(profile.values())
        for v in list(self.open_voids):
            traversed = (c.low <= v["lo"] and c.high >= v["hi"])
            if not traversed:
                continue
            inside = sum(vol for price, vol in profile.items()
                         if v["lo"] < price < v["hi"])
            if inside >= 1.5 * (self.lvn_percentile / 100.0 * total):
                self.open_voids.remove(v)
                events.append({
                    "event_type": "EV_LIQ_010", "at_bar": c.bar_index,
                    "level_id": f"void_{v['lo']:.10g}_{v['hi']:.10g}",
                    "Q": "Q5", "evidence_id": uuid_v7(),
                    "snapshot_id": generate_snapshot_id(
                        {"void_fill": (round(v["lo"], 10),
                                       round(v["hi"], 10)),
                         "bar": c.bar_index}),
                    "payload": {"lo": v["lo"], "hi": v["hi"],
                                "volume_inside": inside}})
                # VOID_EDGE touches at the filled boundaries (§2 level types)
                events.extend(self._ingest_touch(
                    v["lo"], c.bar_index, "VOID_EDGE"))
                events.extend(self._ingest_touch(
                    v["hi"], c.bar_index, "VOID_EDGE"))
        return events

    # -- output -----------------------------------------------------------
    def output(self) -> Dict[str, Any]:
        """E02.Output.v4 (§5.1)."""
        levels_out = []
        for lv in self.levels.values():
            levels_out.append({
                "lid": lv.lid, "price": lv.price, "side": lv.side,
                "ltype": lv.ltype, "instances": lv.instances,
                "first_seen": lv.first_seen, "last_touch": lv.last_touch,
                "touch_count": lv.touch_count, "salience": lv.salience,
                "fate": lv.fate, "Q": lv.Q, "snapshot_id": lv.snapshot_id,
                "evidence_id": lv.evidence_id, "members": lv.members,
                "atr_at_formation": lv.atr_at_formation})
        pools_out = [{
            "pid": p.pid, "lo": p.lo, "hi": p.hi, "median": p.median,
            "weight": p.weight, "member_level_ids": p.member_level_ids,
            "fate": p.fate, "Q": p.Q, "snapshot_id": p.snapshot_id}
            for p in self.pools.values()]
        q_summary: Dict[str, int] = {}
        for lv in self.levels.values():
            q_summary[lv.Q] = q_summary.get(lv.Q, 0) + 1
        return {
            "version": CONTRACT_VERSION, "engine": "E02_LIQUIDITY",
            "generated_at_bar": (self.candles[-1].bar_index
                                 if self.candles else -1),
            "snapshot_id": generate_snapshot_id(
                {"levels": len(levels_out), "pools": len(pools_out),
                 "events": len(self.events)}),
            "levels": levels_out, "pools": pools_out, "events": self.events,
            "Q_summary": q_summary}


# ===========================================================================
# §5 SCHEMA — events catalog, level state machine, versioning
# ===========================================================================

EVENT_CATALOG: Dict[str, str] = {
    "EV_LIQ_000": "INVALID_CANDLE (Q0)",
    "EV_LIQ_001": "Level_Formed",
    "EV_LIQ_002": "Strengthened",
    "EV_LIQ_003": "Pool_Formed",
    "EV_LIQ_004": "Pool_Expanded",
    "EV_LIQ_005": "Sweep_BuySide",
    "EV_LIQ_006": "Sweep_SellSide",
    "EV_LIQ_007": "WickOnly",
    "EV_LIQ_008": "Raid",
    "EV_LIQ_009": "Void_Identified",
    "EV_LIQ_010": "Void_Filled",
    "EV_LIQ_011": "Level_Expired",
    "EV_LIQ_012": "Pool_Swept",
    "EV_LIQ_013": "Level_Invalidated",
}
LEVEL_FATES = ("FORMED", "ACTIVE", "STRENGTHENED", "SWEPT", "INVALIDATED",
               "EXPIRED")
LEVEL_FATE_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "FORMED": ("ACTIVE",),
    "ACTIVE": ("STRENGTHENED", "SWEPT", "INVALIDATED", "EXPIRED"),
    "STRENGTHENED": ("STRENGTHENED", "ACTIVE", "SWEPT", "INVALIDATED",
                     "EXPIRED"),
    "SWEPT": (), "INVALIDATED": (), "EXPIRED": (),
}
LEVEL_SIDES = ("BUY_SIDE", "SELL_SIDE")
LEVEL_TYPES = ("EQUAL_HIGH", "EQUAL_LOW", "UTC_ACTIVITY_WINDOW_EXTREME",
               "SWING_EXTREME", "RANGE_EDGE", "VOID_EDGE")
Q_TAGS = ("Q0", "Q1", "Q2", "Q3", "Q4", "Q5", "QX")
POOL_FATES = ("ACTIVE", "SWEPT", "EXPIRED")


def validate_level_row(row: Dict[str, Any]) -> None:
    """E02.Output.v4 levels[] required-fields check (§5.4 schema)."""
    required = ("lid", "price", "side", "ltype", "instances", "first_seen",
                "last_touch", "touch_count", "salience", "fate", "Q",
                "snapshot_id", "evidence_id", "members", "atr_at_formation")
    for k in required:
        if row.get(k) is None:
            raise ValueError(f"level missing required field {k!r}")
    if row["side"] not in LEVEL_SIDES:
        raise ValueError(f"level side {row['side']!r} invalid")
    if row["ltype"] not in LEVEL_TYPES:
        raise ValueError(f"level ltype {row['ltype']!r} invalid")
    if row["fate"] not in LEVEL_FATES:
        raise ValueError(f"level fate {row['fate']!r} invalid")
    if row["Q"] not in Q_TAGS:
        raise ValueError(f"level Q {row['Q']!r} invalid")
    if row["price"] <= 0:
        raise ValueError("level price must be > 0")
    if not (0.0 <= row["salience"] <= 1.0):
        raise ValueError("salience must be within [0,1]")


def validate_pool_row(row: Dict[str, Any]) -> None:
    required = ("pid", "lo", "hi", "median", "weight", "member_level_ids",
                "fate", "Q", "snapshot_id")
    for k in required:
        if row.get(k) is None:
            raise ValueError(f"pool missing required field {k!r}")
    if row["fate"] not in POOL_FATES:
        raise ValueError(f"pool fate {row['fate']!r} invalid")


def validate_event_row(row: Dict[str, Any]) -> None:
    required = ("event_type", "at_bar", "level_id", "Q", "evidence_id",
                "snapshot_id", "payload")
    for k in required:
        if row.get(k) is None:
            raise ValueError(f"event missing required field {k!r}")
    if not row["event_type"].startswith("EV_LIQ_"):
        raise ValueError(f"event_type {row['event_type']!r} invalid")
    if row["Q"] not in Q_TAGS:
        raise ValueError(f"event Q {row['Q']!r} invalid")


def load_output(data: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
    """§8.7 serialization compatibility: a v3 payload loads with a Q3
    warning (never a crash); v4 loads clean. Removing a field without a
    MAJOR bump is prohibited — structural validators below enforce the
    v4 required set."""
    version = str(data.get("version", ""))
    warning = None
    if not version.startswith("4."):
        warning = ("Q3_LEGACY_SCHEMA_VERSION: loading "
                   f"{version or 'unknown'} through the v4 loader — "
                   "documented defaults applied to new fields")
        data = dict(data)
        data["version"] = CONTRACT_VERSION
        data.setdefault("Q_summary", {})
    for row in data.get("levels", []):
        validate_level_row(row)
    for row in data.get("pools", []):
        validate_pool_row(row)
    for row in data.get("events", []):
        validate_event_row(row)
    return data, warning


# ===========================================================================
# §6 PARAMS — governed table (§6; frozen defaults)
# ===========================================================================

E02_DEFAULTS: Dict[str, Any] = {
    "theta_eq": 0.15,            # xATR, 0.05–0.4
    "kappa": 1.0,                # DBSCAN calibration, 0.8–1.5
    "sweep_min_pen": 0.10,       # xATR, 0.05–0.5
    "sweep_min_rejection": 0.20, # ratio, 0–0.6
    "sweep_weights": [0.25, 0.25, 0.2, 0.2, 0.1],
    "lambda_decay": 0.02,        # 1/bar, 0.001–0.1
    "lambda_fast": 0.08, "lambda_slow": 0.01,   # dual decay
    "salience_weights": {"w_t": 0.3, "w_i": 0.3, "w_f": 0.25, "w_p": 0.15},
    "void_gap": 2.5,             # xATR, 1.0–5.0
    "lvn_percentile": 15.0,      # %, 5–25
    "raid_window": 3,            # bars, 1–10
    "level_expiry_bars": 96,     # bars, 24–240
    "invalid_break_atr": 1.5,    # xATR, 0.5–3.0
    "sweep_cooldown_bars": 3,
    "utc_activity_windows": [("UTC_W0", 0.0, 7.0), ("UTC_W1", 7.0, 12.5),
                             ("UTC_W2", 12.5, 21.0), ("UTC_W3", 21.0, 24.0)],
    "type_score": {"EQUAL_HIGH": 1.0, "EQUAL_LOW": 1.0,
                   "UTC_ACTIVITY_WINDOW_EXTREME": 0.9,
                   "SWING_EXTREME": 0.8, "RANGE_EDGE": 0.6,
                   "VOID_EDGE": 0.5},
    "merton": {"lambda_j": 0.02, "mu_j": 0.0, "sigma_j": 0.02},
    "T_hit": 100,                # bars, 10–500
    "volume_profile_bars": 100, "vp_bins": 50,
    "min_candles": 50,
}


def get_params(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = dict(E02_DEFAULTS)
    if overrides:
        unknown = set(overrides) - set(params)
        if unknown:
            raise ValueError(f"unknown E02 params: {sorted(unknown)}")
        params.update(overrides)
    return params


# ===========================================================================
# §7 ENCYCLOPEDIA — computational bits (Ch.1 Poisson, Ch.2 Jaccard, Ch.3/4)
# ===========================================================================
# (poisson_significance, jaccard_index defined in §3 block — encyclopedia
#  dimensions 1/2/14 computational content. Ch.4's OFI/VPIN/Merton/Kyle/GM
#  formulas are in §3/§4 above; narrative dimensions live in docstrings.)


# ===========================================================================
# §8 VALIDATION — battery helpers (each §8 clause becomes an executed test)
# ===========================================================================


def run_engine(candles: Sequence[Candle],
               params: Optional[Dict[str, Any]] = None,
               htfs: Optional[Dict[str, Any]] = None,
               l2_snapshots: Optional[Sequence[Dict[str, float]]] = None,
               ) -> LiquidityEngineV4:
    p = params or get_params()
    eng = LiquidityEngineV4(
        theta_eq=p["theta_eq"], sweep_min_pen=p["sweep_min_pen"],
        sweep_min_rej=p["sweep_min_rejection"],
        lambda_decay=p["lambda_decay"], kappa=p["kappa"],
        raid_window=p["raid_window"],
        level_expiry_bars=p["level_expiry_bars"],
        invalid_break_atr=p["invalid_break_atr"],
        void_gap=p["void_gap"], lvn_percentile=p["lvn_percentile"],
        salience_weights=p["salience_weights"],
        type_scores=p["type_score"], sweep_weights=p["sweep_weights"],
        volume_profile_bars=p["volume_profile_bars"], vp_bins=p["vp_bins"])
    for c in candles:
        eng.on_new_closed_candle(c, htfs=htfs, l2_snapshots=l2_snapshots)
    return eng


def sweep_outcomes(sweep_log: Sequence[Dict[str, Any]],
                   candles: Sequence[Candle], atr_now: float,
                   horizon: int = 5) -> Tuple[float, int]:
    """§8.4 ground truth: a sweep is 'genuine' when price reverses > 0.5·ATR
    within 5 candles. Returns (genuine_rate, n_evaluated) — in-window past
    outcomes only (PIT)."""
    n_genuine = 0
    n_eval = 0
    by_bar = {c.bar_index: c for c in candles}
    for s in sweep_log:
        fut = [by_bar[s["at_bar"] + i] for i in range(1, horizon + 1)
               if s["at_bar"] + i in by_bar]
        if not fut:
            continue
        n_eval += 1
        base = by_bar[s["at_bar"]].close
        # reversal = move back toward/through the level against the sweep
        if s["side"] == "SELL_SIDE":
            move = max(f.close - base for f in fut)
        else:
            move = max(base - f.close for f in fut)
        if move > 0.5 * max(atr_now, EPS):
            n_genuine += 1
    if n_eval == 0:
        return (0.0, 0)
    return (n_genuine / n_eval, n_eval)


def no_future_leak_check(candles: Sequence[Candle]) -> bool:
    """§8.3: for every level with first_seen = t, no event at at_bar ≤ t
    used it. Iterates events sorted by at_bar; each Sweep must satisfy
    level.first_seen ≤ event.at_bar − 1."""
    eng = run_engine(candles)
    for ev in sorted(eng.events, key=lambda e: e["at_bar"]):
        lid = ev["level_id"]
        if lid not in eng.levels:
            continue
        lv = eng.levels[lid]
        if ev["event_type"] in ("EV_LIQ_005", "EV_LIQ_006", "EV_LIQ_007"):
            if not (lv.first_seen <= ev["at_bar"] - 1):
                return False
    return True


def ablation_sweep_score(candle: Candle, level: Level, atr_now: float,
                         vol_sma20: float) -> Dict[str, float]:
    """§8.4: SweepScore recomputed with each component removed."""
    _, _, full = detect_sweep(candle, level, atr_now, vol_sma20)
    pen = (max(0.0, candle.high - level.price) if level.side == "SELL_SIDE"
           else max(0.0, level.price - candle.low)) / max(atr_now, EPS)
    body_top = max(candle.open, candle.close)
    wick = (candle.high - body_top if level.side == "SELL_SIDE"
            else min(candle.open, candle.close) - candle.low)
    rejection = wick / (candle.high - candle.low + EPS)
    close_return = (abs(level.price - candle.close)
                    / (pen * atr_now + EPS) if pen > EPS else 0.0)
    vol_ratio = candle.volume / (vol_sma20 + EPS)
    norm = {"pen": math.tanh(pen / 0.5),
            "rej": min(rejection / 0.8, 1.0),
            "close": min(max(close_return, 0) / 1.5, 1.0),
            "vol": min(math.log1p(vol_ratio) / math.log1p(3), 1.0)}
    w = {"pen": 0.25, "rej": 0.25, "close": 0.2, "vol": 0.2}
    out = {"full": full}
    for comp in ("pen", "rej", "close", "vol"):
        out[f"without_{comp}"] = full - w[comp] * norm[comp]
    return out


# ===========================================================================
# EngineBase integration — frozen v4.0.0 contract surface
# ===========================================================================

ANALYST_VERSION = "4.0.0+" + "0" * 40


def _canon(obj: Any) -> str:
    from apex.identity.canonical_json import canonical_json
    return canonical_json(obj)


def _sha_of(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def observation_to_candle(obs: MarketObservation) -> Candle:
    from apex.data_catalog.contracts import parse_utc_ms
    return Candle(open=float(obs.open), high=float(obs.high),
                  low=float(obs.low), close=float(obs.close),
                  volume=float(obs.volume or 0),
                  bar_index=obs.sequence, is_closed=True,
                  t_close=int(parse_utc_ms(obs.timestamp).timestamp()))


class E02LiquidityEngine(EngineBase):
    """E02_Liquidity on the frozen EngineBase contract (v4.0.0).

    compute(symbol, timeframe, as_of, context): window via context['window']
    or a sync WindowProvider (context['provider']); optional context keys:
    htf ({levels, atr_htf}), l2_snapshots, bars. All emitted evidence is
    direction-neutral (NG1/NG3): sweeps report the event, never a predicted
    direction."""

    engine_id = "E02"
    analyst_version = ANALYST_VERSION
    code_revision = "0" * 40

    def compute(self, symbol: str, timeframe: str, as_of: str,
                context: Optional[Dict[str, Any]] = None
                ) -> List[EvidenceEvent]:
        context = context or {}
        window_obs = self._resolve_window(symbol, timeframe, as_of, context)
        if not window_obs:
            return []
        candles = [observation_to_candle(o) for o in window_obs]
        params = get_params(context.get("e02_params"))
        eng = run_engine(candles, params,
                         htfs=context.get("htf"),
                         l2_snapshots=context.get("l2_snapshots"))
        atr_now = (compute_ATR_wilder(candles, 14)[-1] if candles else 0.0)
        genuine_rate, n_eval = sweep_outcomes(eng.sweep_log, candles, atr_now)
        conf_lb = wilson_ci(genuine_rate, n_eval)[0] if n_eval > 0 else 0.0
        quality = self._window_quality(window_obs)
        input_hash = _sha_of(_canon([c.to_dict() for c in candles]))
        replay = self.build_replay_key(
            symbol, timeframe, as_of, input_hash, "E02-LIQ-V4.0.0-DEFAULTS",
            _canon({"theta_eq": params["theta_eq"],
                    "kappa": params["kappa"]}))
        cached = self.replay_lookup(replay)
        if cached is not None:
            return cached
        result = [self._to_evidence(ev, symbol, timeframe, as_of, candles,
                                     quality, conf_lb, n_eval, eng)
                  for ev in eng.events]
        self.replay_store(replay, result)
        return result

    @staticmethod
    def _window_quality(window_obs: Sequence[MarketObservation]) -> float:
        if not window_obs:
            return 0.0
        comps = [float(o.completeness_pct or 0) / 100.0 for o in window_obs]
        return min(1.0, sum(comps) / len(comps))

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

    def _to_evidence(self, ev: Dict[str, Any], symbol: str, timeframe: str,
                     as_of: str, candles: Sequence[Candle], quality: float,
                     conf_lb: float, n_eval: int,
                     eng: LiquidityEngineV4) -> EvidenceEvent:
        et = ev["event_type"]
        payload = ev.get("payload", {})
        strength = self._event_strength(ev, eng)
        q_tag = ev.get("Q", "Q1")
        last_close_ms = candles[-1].t_close * 1000 if candles else 0
        age_bars = max(0, (candles[-1].bar_index - ev["at_bar"])
                       if candles else 0)
        from apex.identity.canonical_json import canonical_json as _cj
        return EvidenceEvent(
            evidence_id=uuid_v7(),
            engine_id=self.engine_id,
            analyst_version=self.analyst_version,
            symbol=symbol, timeframe=timeframe,
            snapshot_id=ev.get("snapshot_id") or generate_snapshot_id(
                {"event": et, "t": ev.get("at_bar")}),
            event_time=_iso_from_ms(ev["at_bar"], candles),
            availability_time=_iso_from_ms(ev["at_bar"], candles),
            observation_window={"bars": len(candles),
                                "first": candles[0].bar_index,
                                "last": candles[-1].bar_index},
            feature_snapshot_id=_sha_of(_cj(
                {"window": [c.bar_index for c in candles[-20:]]})),
            feature_dependencies=("window",),
            condition_state=et,
            direction=0,
            strength=float(strength),
            confidence=float(conf_lb if n_eval > 0 else 0.0),
            quality=float(quality),
            validity="VALID" if q_tag not in ("Q0",) else "INVALID",
            fate_state=LifecycleState.ACTIVE if q_tag != "Q0"
            else LifecycleState.CANDIDATE,
            age=float(age_bars),
            decay=float(math.exp(-0.1 * age_bars)),
            explanation=f"{EVENT_CATALOG.get(et, et)} level={ev.get('level_id')}",
            parameter_version="E02-LIQ-V4.0.0/DEFAULTS-v1",
            lineage=tuple(f"candle_{c.bar_index}" for c in candles[-20:]),
            resolution_class=q_tag if q_tag in Q_TAGS else "Q1",
        )

    @staticmethod
    def _event_strength(ev: Dict[str, Any], eng: LiquidityEngineV4) -> float:
        """Intensity on the engine's own scale — chapter quantities only."""
        et = ev["event_type"]
        payload = ev.get("payload", {})
        if et in ("EV_LIQ_005", "EV_LIQ_006"):
            return float(payload.get("score", 0.0))
        if et == "EV_LIQ_008":
            scores = payload.get("scores", [0.0])
            return float(sum(scores) / max(1, len(scores)))
        if et in ("EV_LIQ_001", "EV_LIQ_002", "EV_LIQ_011"):
            lid = ev.get("level_id", "")
            lv = eng.levels.get(lid)
            return float(lv.salience) if lv is not None else 0.0
        if et in ("EV_LIQ_003", "EV_LIQ_004", "EV_LIQ_012"):
            return float(payload.get("weight", 0.0))
        if et == "EV_LIQ_009":
            return float(payload.get("gap_ATR", 0.0))
        if et == "EV_LIQ_010":
            return float(payload.get("volume_inside", 0.0))
        if et == "EV_LIQ_013":
            return float(payload.get("break_atr", 0.0))
        return 0.0


def _iso_from_ms(bar_index: int, candles: Sequence[Candle]) -> str:
    for c in candles:
        if c.bar_index == bar_index:
            import datetime
            return datetime.datetime.fromtimestamp(
                c.t_close, tz=datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.") + f"{(c.t_close % 1) * 1000:03.0f}Z"
    import datetime
    ts = candles[-1].t_close if candles else 0
    return datetime.datetime.fromtimestamp(
        ts, tz=datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.") + f"{(ts % 1) * 1000:03.0f}Z"
