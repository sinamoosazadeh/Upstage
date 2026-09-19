"""APEX_GEN5 E01 — Structure Engine (APEX-CONTRACT-STRUCT-V4.0.0).

Producer: E01_Structure. Consumers: E02_Liquidity, E09_Trend, E11_Regime
(no runtime dependency — versioned-schema event bus only).

Engine file mirrors chapter order (PHASE2_CHECKPOINTS.md §CP-2):
  §3 formulas -> §4 flows -> §5 schema -> §6 params -> §7 state/coverage
  -> §8 validation. Sections are banner-marked below.

Foundation surfaces CONSUMED (never patched): apex.engines.base.EngineBase,
apex.identity.{canonical_json,uuid_v7,snapshot,hashes},
apex.data_catalog.{contracts,catalog}, apex.quality.numerical.eps_for_engine.

Wave-Out discipline (§9.5-9): dynamic Williams k is Wave-Out — requesting it
raises WaveOutError; k is fixed at the §6 governed default (GC-D: k=2).
"""
from __future__ import annotations

import math
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

ENGINE_CODE = "E01_Structure"
CONTRACT_ID = "APEX-CONTRACT-STRUCT-V4.0.0"
ENGINE_NAME_FOR_IDENTITY = "E01_Structure"   # canonical_snapshot_id engine arg
CONTRACT_VERSION_FOR_IDENTITY = "4.0.0"

# ===========================================================================
# §3 FORMULAS — Complete Mathematical Framework (corrected formulas, edge cases)
# ===========================================================================


def scaled_epsilon(candles: Sequence[Dict[str, Any]], tick: float = 0.01) -> float:
    """ε_s = max(tick×0.5, median_20(C)×1e-8, 1e-12) (§3.1)."""
    closes = [c["C"] for c in candles[-20:] if c.get("C") is not None]
    if not closes:
        return max(tick * 0.5, 1e-12)
    med = sorted(closes)[len(closes) // 2]
    return max(tick * 0.5, med * 1e-8, 1e-12)


def candle_range(c: Dict[str, Any]) -> float:
    """R_t = H_t − L_t (Q1)."""
    return c["H"] - c["L"]


def candle_body(c: Dict[str, Any]) -> float:
    """B_t = |C_t − O_t| (Q1)."""
    return abs(c["C"] - c["O"])


def upper_wick(c: Dict[str, Any]) -> float:
    """UW_t = H_t − max(O_t, C_t) (Q1)."""
    return c["H"] - max(c["O"], c["C"])


def lower_wick(c: Dict[str, Any]) -> float:
    """LW_t = min(O_t, C_t) − L_t (Q1)."""
    return min(c["O"], c["C"]) - c["L"]


def body_ratio(c: Dict[str, Any], eps: float) -> float:
    """BodyRatio_t = B_t / max(R_t, ε_s) (§3.1, PIT-safe)."""
    return candle_body(c) / max(candle_range(c), eps)


def close_position(c: Dict[str, Any], eps: float) -> float:
    """ClosePos_t = (C_t − L_t)/max(R_t, ε_s) ∈ [0,1] (§3.1)."""
    return (c["C"] - c["L"]) / max(candle_range(c), eps)


def true_range(c: Dict[str, Any], prev: Optional[Dict[str, Any]]) -> float:
    """TR_t = max(H−L, |H−C_{t-1}|, |L−C_{t-1}|, |G_t|) (§3.2; the |G_t| term
    is dominated by the other two for valid candles — kept for fidelity)."""
    if prev is None:
        return candle_range(c)
    gap = abs(c["O"] - prev["C"])
    return max(candle_range(c), abs(c["H"] - prev["C"]),
               abs(c["L"] - prev["C"]), gap)


class _ATRWindow(tuple):
    """One immutable pipeline window; memoize identical native ATR requests.

    This cache never escapes a run, changes arithmetic order, or substitutes
    an indicator. Input candle dictionaries are read-only in run_pipeline.
    """
    def __new__(cls, values):
        window = super().__new__(cls, values)
        window._atr_sma_cache = {}
        return window

    def __getitem__(self, key):
        value = super().__getitem__(key)
        if isinstance(key, slice) and key.start in (None, 0) and key.step in (None, 1):
            prefix = type(self)(value)
            prefix._atr_sma_cache = self._atr_sma_cache
            return prefix
        return value


def atr_sma(candles: Sequence[Dict[str, Any]], n: int = 14,
            idx: int = -1) -> float:
    """ATR_n(t) SMA form over TR (§3.2). Insufficient history is a Q1 warmup
    state, not a numerical estimate — raises ValueError (§4.1)."""
    cache = candles._atr_sma_cache if isinstance(candles, _ATRWindow) else None
    base = len(candles) if idx == -1 else idx + 1
    if cache is not None and n + 1 <= base <= len(candles) and (n, base) in cache:
        return cache[n, base]
    if len(candles) < n + 1:
        raise ValueError("INSUFFICIENT_HISTORY_Q1")
    trs: List[float] = []
    for i in range(1, base):
        c = candles[i]
        p = candles[i - 1]
        if c["H"] < c["L"]:
            continue
        trs.append(true_range(c, p))
    if len(trs) < n:
        raise ValueError("INSUFFICIENT_HISTORY_Q1")
    value = sum(trs[-n:]) / n
    if cache is not None:
        cache[n, base] = value
    return value


def atr_wilder(candles: Sequence[Dict[str, Any]], n: int = 14) -> List[float]:
    """Wilder RMA ATR series (§3.2 alternative form)."""
    atr: List[float] = []
    trs: List[float] = []
    for i, c in enumerate(candles):
        tr = true_range(c, candles[i - 1] if i > 0 else None)
        trs.append(tr)
        if i < n:
            atr.append(sum(trs) / (i + 1))
        else:
            atr.append((atr[-1] * (n - 1) + tr) / n)
    return atr


def sma_until(arr: Sequence[float], m: int, until_idx: int) -> float:
    """SMA over arr[:until_idx] (PIT: excludes the current bar, §3.8)."""
    slice_arr = [x for x in arr[:until_idx] if x is not None]
    if not slice_arr:
        raise ValueError("INSUFFICIENT_HISTORY_Q1")
    if len(slice_arr) < m:
        return sum(slice_arr) / len(slice_arr)
    return sum(slice_arr[-m:]) / m


def displacement(candles: Sequence[Dict[str, Any]], t_idx: int, m: int = 20,
                 eps: float = 1e-12) -> float:
    """Disp_t = R_t / max(SMA_m(R)_{t-1}, ε_s) — SMA strictly up to t−1 (§3.8)."""
    ranges = [candle_range(c) for c in candles]
    return candle_range(candles[t_idx]) / max(sma_until(ranges, m, t_idx), eps)


def vol_ratio(candles: Sequence[Dict[str, Any]], t_idx: int, m: int = 20,
              eps: float = 1e-12) -> float:
    """VR_t = 0 if V_t=0 else V_t / max(SMA_m(V)_{t-1}, ε_s) (§3.8)."""
    if candles[t_idx].get("V", 0) == 0:
        return 0.0
    vols = [cc.get("V", 0) for cc in candles]
    return candles[t_idx]["V"] / max(sma_until(vols, m, t_idx), eps)


def break_mag(close: float, level: float, atr_now: float, eps: float) -> float:
    """Corrected BreakMag: |C_t − P_level| / max(ATR_n(t), ε_s) (§3.6)."""
    return abs(close - level) / max(atr_now, eps)


def strength_B(bm: float) -> float:
    """B = σ(BreakMag − 1) (§3.9)."""
    return 1.0 / (1.0 + math.exp(-(bm - 1.0)))


def strength_D(disp: float, theta_disp: float) -> float:
    """D = min(Disp_t/θ_disp, 1) (§3.9)."""
    return min(disp / theta_disp, 1.0)


def strength_V(vr: float) -> float:
    """V = min(VolRatio_t/2, 1); V=0 stays 0 (§3.9)."""
    return min(vr / 2.0, 1.0)


def strength_C(c: Dict[str, Any], eps: float, bullish: bool) -> float:
    """C = ClosePos for BOS↑, 1−ClosePos for BOS↓ (§3.9)."""
    cp = close_position(c, eps)
    return cp if bullish else 1.0 - cp


def s_struct(bm: float, disp: float, vr: float, c: Dict[str, Any], eps: float,
             bullish: bool, w_b: float = 0.38, w_d: float = 0.27,
             w_v: float = 0.19, w_c: float = 0.16,
             theta_disp: float = 1.5) -> Dict[str, float]:
    """S_struct = w_b·B + w_d·D + w_v·V + w_c·C with OOS weights (§3.9)."""
    B = strength_B(bm)
    D = strength_D(disp, theta_disp)
    V = strength_V(vr)
    C = strength_C(c, eps, bullish)
    return {"B": B, "D": D, "V": V, "C": C,
            "S": w_b * B + w_d * D + w_v * V + w_c * C}


def dynamic_k(atr_ratio: float, alpha: float) -> int:
    """Dynamic Williams k is Wave-Out (§9.5-9): raise, never implement."""
    raise WaveOutError("dynamic_williams_k",
                       "WAVE_OUT_DYNAMIC_WILLIAMS_K")


def t_htf(atr_htf: float) -> float:
    """T_HTF = 0.15 × ATR_HTF (§3.10)."""
    return 0.15 * atr_htf


def swing_depth(p: float, p_prev: float, atr_now: float, eps: float) -> float:
    """d_s = |P_s − P_prev| / max(ATR_n(t_s), ε_s) (§3.5)."""
    return abs(p - p_prev) / max(atr_now, eps)


def redundancy(p: float, p_prev: float, t_htf_now: float, eps: float) -> float:
    """redundancy = exp(−|P_i − P_{i-1}|/T_HTF) (§3.5)."""
    return math.exp(-abs(p - p_prev) / max(t_htf_now, eps))


def wilson_ci(p_hat: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson 95% CI (§3.12)."""
    if n <= 0:
        raise ValueError("WILSON_N_MUST_BE_POSITIVE")
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
            ) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def false_break_rate(bos_events: Sequence[Dict[str, Any]],
                     candles: Sequence[Dict[str, Any]], atr_now: float,
                     h: int = 8, eps: float = 1e-12) -> Tuple[float, int]:
    """p̂_fail = #{BOS : max_{i=1..H}|C_{t+i}−C_t| < 0.2·ATR} / N_BOS (§3.12).
    Outcomes use only in-window past candles (no future leak); BOS events
    without a full outcome window are not counted (honest n)."""
    total = 0
    failed = 0
    for bos in bos_events:
        t = bos["candle_index"]
        window = candles[t + 1:t + 1 + h]
        if not window:
            continue
        total += 1
        move = max(abs(cc["C"] - candles[t]["C"]) for cc in window)
        if move < 0.2 * max(atr_now, eps):
            failed += 1
    if total == 0:
        return (0.0, 0)
    return (failed / total, total)


# ===========================================================================
# §4 ALGORITHMS — complete, runnable flows (streaming, idempotent)
# ===========================================================================


def generate_snapshot_id(payload: Dict[str, Any]) -> str:
    """snapshot_id = SHA256(canonical_json(canonical_snapshot_payload)) —
    the global deterministic identity (GLOBAL IDENTITY/PIT contract)."""
    return canonical_snapshot_id(ENGINE_NAME_FOR_IDENTITY,
                                 CONTRACT_VERSION_FOR_IDENTITY, payload)


def detect_swings_williams(candles: Sequence[Dict[str, Any]], k: int = 2,
                           tick: float = 0.01) -> List[Dict[str, Any]]:
    """Generalized Williams fractal (§3.3/§4.2): H_t > left_max + ε and
    H_t ≥ right_max + ε (≥ + ε handles equal-level cases). Confirmation
    only at t+k after that candle closes (PIT). Complexity O(N·k)."""
    eps = scaled_epsilon(candles, tick)
    swings: List[Dict[str, Any]] = []
    n = len(candles)
    if n < 2 * k + 1:
        return swings
    for t in range(k, n - k):
        c_t = candles[t]
        if c_t["H"] < c_t["L"] - eps:
            continue
        left_max = max(candles[t - i]["H"] for i in range(1, k + 1))
        right_max = max(candles[t + i]["H"] for i in range(1, k + 1))
        if c_t["H"] > left_max + eps and c_t["H"] >= right_max + eps:
            swings.append({
                "type": "HIGH", "price": c_t["H"], "index": t,
                "timestamp": c_t["close_time"],
                "confirmed_at": candles[t + k]["close_time"],
                "method": "WILLIAMS", "k": k, "q_tag": "Q2",
                "snapshot_id": generate_snapshot_id(
                    {"t": t, "p": c_t["H"], "k": k}),
            })
        left_min = min(candles[t - i]["L"] for i in range(1, k + 1))
        right_min = min(candles[t + i]["L"] for i in range(1, k + 1))
        if c_t["L"] < left_min - eps and c_t["L"] <= right_min - eps:
            swings.append({
                "type": "LOW", "price": c_t["L"], "index": t,
                "timestamp": c_t["close_time"],
                "confirmed_at": candles[t + k]["close_time"],
                "method": "WILLIAMS", "k": k, "q_tag": "Q2",
                "snapshot_id": generate_snapshot_id(
                    {"t": t, "p": c_t["L"], "k": k}),
            })
    return swings


def detect_swings_gann(candles: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Gann swing (§3.4/§4.3 + §8.1 FIX_002, Ch.3 §11 case study).

    A Gann swing marks the extreme of a completed leg: a Gann LOW is emitted
    at the lowest low of a down-leg when the first higher low prints
    (L_t > L_{t-1} after falling lows), a Gann HIGH symmetrically at the
    highest high of an up-leg when highs turn down. Trend alternates — and
    per the GSH formula (§3.4) a Gann HIGH requires SWING_prev=LOW, so the
    alternation opens with a LOW (the §9 case study's initial Gann Low at
    C1); FIX_002 (lows 99, 98, 97, 97.1 → exactly [LOW@2, price 97]) pins
    the turn-bar confirmation semantics (see ISSUE-CP2-003).
    """
    swings: List[Dict[str, Any]] = []
    n = len(candles)
    trend: Optional[int] = None
    trough_idx = 0
    peak_idx = 0
    for t in range(1, n):
        c_prev = candles[t - 1]
        c = candles[t]
        if c["H"] < c["L"]:
            continue
        if trend != 1 and c["L"] > c_prev["L"]:
            swings.append({
                "type": "LOW", "price": candles[trough_idx]["L"],
                "index": trough_idx,
                "timestamp": candles[trough_idx]["close_time"],
                "confirmed_at": c["close_time"],
                "method": "GANN", "q_tag": "Q2",
                "snapshot_id": generate_snapshot_id(
                    {"t": trough_idx, "p": candles[trough_idx]["L"],
                     "gann": "up"}),
            })
            trend = 1
            peak_idx = t
        elif trend == 1 and c["H"] < c_prev["H"]:
            swings.append({
                "type": "HIGH", "price": candles[peak_idx]["H"],
                "index": peak_idx,
                "timestamp": candles[peak_idx]["close_time"],
                "confirmed_at": c["close_time"],
                "method": "GANN", "q_tag": "Q2",
                "snapshot_id": generate_snapshot_id(
                    {"t": peak_idx, "p": candles[peak_idx]["H"],
                     "gann": "down"}),
            })
            trend = -1
            trough_idx = t
        # track running extremes of the current leg
        if c["L"] < candles[trough_idx]["L"]:
            trough_idx = t
        if c["H"] > candles[peak_idx]["H"]:
            peak_idx = t
    return swings


def is_outside_bar(c: Dict[str, Any], prev: Dict[str, Any]) -> bool:
    """Gann Outside Bar: H_t > H_{t-1} ∧ L_t < L_{t-1} (§3.4)."""
    return c["H"] > prev["H"] and c["L"] < prev["L"]


def is_inside_bar(c: Dict[str, Any], prev: Dict[str, Any]) -> bool:
    """Gann Inside Bar: H_t ≤ H_{t-1} ∧ L_t ≥ L_{t-1} (§3.4)."""
    return c["H"] <= prev["H"] and c["L"] >= prev["L"]


def merge_and_prune_swings(swings_w: List[Dict[str, Any]],
                           swings_g: List[Dict[str, Any]],
                           candles: Sequence[Dict[str, Any]], atr_n: int = 14,
                           theta_depth: float = 0.8, theta_maxAge: int = 120,
                           tick: float = 0.01,
                           htf_swings: Optional[List[Dict[str, Any]]] = None,
                           redundancy_thr: float = 0.9
                           ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Merge Williams+Gann, dedup cross-method duplicates within ±2 candles
    of the same type (the merge exists to collapse Williams/Gann overlap of
    one extreme; same-method neighbors flow to the depth/redundancy pruner —
    §8.1 FIX_009), then prune by depth/age/redundancy (§3.5/§4.4). Gann
    final confirmation (§3.4): a Gann swing survives only if it overlaps a
    same-type Williams fractal within ±2 candles or its depth ≥ 1.2."""
    eps = scaled_epsilon(candles, tick)
    all_sw = sorted(swings_w + swings_g, key=lambda x: x["index"])
    deduped: List[Dict[str, Any]] = []
    for s in all_sw:
        if not deduped:
            deduped.append(s)
            continue
        last = deduped[-1]
        cross_method_overlap = (
            abs(s["index"] - last["index"]) <= 2
            and s["type"] == last["type"]
            and s.get("method") != last.get("method"))
        if not cross_method_overlap:
            deduped.append(s)
        else:
            if s["type"] == "HIGH" and s["price"] > last["price"]:
                deduped[-1] = s
            elif s["type"] == "LOW" and s["price"] < last["price"]:
                deduped[-1] = s

    def _atr_at(idx: int) -> float:
        """ATR_n(t_s) as of the swing's own bar (§3.5). Bars before the ATR
        warmup borrow the earliest computable ATR (deterministic, causal)."""
        end = min(max(idx, atr_n) + 1, len(candles))
        try:
            return atr_sma(candles[:end], atr_n)
        except ValueError:
            return max(candle_range(c) for c in candles)

    active: List[Dict[str, Any]] = []
    pruned: List[Dict[str, Any]] = []
    williams_idx = [s["index"] for s in swings_w]
    for i, s in enumerate(deduped):
        if i == 0:
            active.append(s)
            continue
        prev = active[-1]
        at = _atr_at(s["index"])
        t_h = 0.15 * at
        depth = swing_depth(s["price"], prev["price"], at, eps)
        s["depth"] = depth
        is_external = False
        if htf_swings:
            for hs in htf_swings:
                if abs(s["price"] - hs["price"]) <= t_h:
                    is_external = True
                    break
        s["is_external"] = is_external
        red = redundancy(s["price"], prev["price"], t_h, eps)
        s["redundancy"] = red
        age = len(candles) - s["index"]
        if (s.get("method") == "GANN"
                and s["type"] in ("HIGH", "LOW")):
            overlaps = any(
                abs(s["index"] - wi) <= 2 and s["type"] == w["type"]
                for wi, w in ((w["index"], w) for w in swings_w))
            if not overlaps and depth < 1.2:
                s["fate"] = "PRUNED"
                s["prune_reason"] = "gann_final_confirmation_failed"
                pruned.append(s)
                continue
        if depth < theta_depth and not is_external:
            s["fate"] = "PRUNED"
            s["prune_reason"] = f"depth {depth:.2f}<{theta_depth}"
            pruned.append(s)
            continue
        if age > theta_maxAge and not is_external:
            s["fate"] = "PRUNED"
            s["prune_reason"] = f"age {age}>{theta_maxAge}"
            pruned.append(s)
            continue
        if red > redundancy_thr:
            s["fate"] = "PRUNED"
            s["prune_reason"] = f"redundancy {red:.2f}>{redundancy_thr}"
            pruned.append(s)
            continue
        s["fate"] = "ACTIVE"
        active.append(s)
    return active, pruned


def detect_gaps(candles: Sequence[Dict[str, Any]], gamma_gap: float = 1.8,
                atr_n: int = 14,
                atr_override: Optional[float] = None
                ) -> List[Dict[str, Any]]:
    """Gap events (§3.2/§4.5): |G_t| > γ_gap·ATR_n(t−1); BREAKAWAY when
    |G| > 2·ATR and (H−L)/ATR > 1.5 (§4.5 algorithm; see ISSUE-CP2-005 for
    the §3.2 VR variant)."""
    gaps: List[Dict[str, Any]] = []
    for t in range(1, len(candles)):
        c_prev = candles[t - 1]
        c = candles[t]
        if c_prev["H"] < c_prev["L"] or c["H"] < c["L"]:
            continue
        gap = c["O"] - c_prev["C"]
        if atr_override is None and t < atr_n + 1:
            continue   # ATR warmup
        at = (atr_override if atr_override is not None
              else atr_sma(candles[:t], atr_n))
        if abs(gap) > gamma_gap * at:
            gaps.append({
                "event_type": "EV_STR_014_GAP",
                "index": t, "gap": gap,
                "gap_atr": abs(gap) / max(at, 1e-12),
                "type": ("BREAKAWAY" if abs(gap) > 2 * at
                         and (c["H"] - c["L"]) / max(at, 1e-12) > 1.5
                         else "COMMON"),
                "timestamp": c["open_time"],
                "snapshot_id": generate_snapshot_id({"t": t, "gap": gap}),
            })
    return gaps


def _eligible_levels(swings: Sequence[Dict[str, Any]], kind: str, t_idx: int,
                     max_levels: int) -> List[Dict[str, Any]]:
    """Level stack: the most recent opposing swings with index < t−1
    (§4.6 eligibility filter)."""
    levels = [s for s in swings
              if s["type"] == kind and s.get("fate", "ACTIVE") != "PRUNED"
              and s["index"] < t_idx - 1]
    levels = sorted(levels, key=lambda x: x["index"], reverse=True)
    return levels[:max_levels]


def detect_bos(candles: Sequence[Dict[str, Any]],
               swings: Sequence[Dict[str, Any]], atr_n: int = 14,
               break_policy: str = "CLOSE", break_min_mag: float = 0.3,
               disp_min: float = 1.5, tick: float = 0.01, max_levels: int = 3,
               weights: Optional[Dict[str, float]] = None,
               atr_override: Optional[float] = None
               ) -> List[Dict[str, Any]]:
    """Multi-level BOS (§3.6/§4.6). Level indexing follows §3.6 ("L_1 is the
    nearest opposing swing and L_k the farthest") in price-adjacency order —
    the order price encounters when approaching — per §8.1 FIX_004 and §9
    Step 5 (the §4.6 recency enumeration is superseded; ISSUE-CP2-002)."""
    events: List[Dict[str, Any]] = []
    if not swings:
        return events
    if atr_override is None and len(candles) < atr_n:
        return events
    w = weights or {"w_b": 0.38, "w_d": 0.27, "w_v": 0.19, "w_c": 0.16}
    eps = scaled_epsilon(candles, tick)
    swing_highs = [s for s in swings if s["type"] == "HIGH"]
    swing_lows = [s for s in swings if s["type"] == "LOW"]
    for t_idx, c in enumerate(candles):
        if c["H"] < c["L"]:
            continue
        if t_idx < 1:
            continue   # displacement warmup: SMA_m(R) on t−1 needs ≥1 bar
        if atr_override is None and t_idx + 1 < atr_n + 1:
            continue   # ATR warmup (INSUFFICIENT_HISTORY_Q1 bar band)
        at = (atr_override if atr_override is not None
              else atr_sma(candles[:t_idx + 1], atr_n))
        ranges = [cc["H"] - cc["L"] for cc in candles]
        vols = [cc.get("V", 0) for cc in candles]
        disp = (c["H"] - c["L"]) / max(sma_until(ranges, 20, t_idx), eps)
        vol_r = 0 if c.get("V", 0) == 0 else (
            c["V"] / max(sma_until(vols, 20, t_idx), eps))
        for bullish, stack in ((True, swing_highs), (False, swing_lows)):
            eligible = [s for s in stack
                        if s["index"] < t_idx - 1
                        and s.get("fate", "ACTIVE") != "PRUNED"]
            eligible = sorted(eligible, key=lambda x: x["index"],
                              reverse=True)[:max_levels]
            if bullish:
                broken = [lv for lv in eligible
                          if c["C"] > lv["price"] + 1e-12]
            else:
                broken = [lv for lv in eligible
                          if c["C"] < lv["price"] - 1e-12]
            # price-adjacency order: bullish ascending, bearish descending
            broken = sorted(broken, key=lambda x: x["price"],
                            reverse=not bullish)
            for level_idx, level in enumerate(broken, start=1):
                P_level = level["price"]
                cond_close = (c["C"] > P_level + 1e-12 if bullish
                              else c["C"] < P_level - 1e-12)
                cond_body = (min(c["O"], c["C"]) > P_level + eps if bullish
                             else max(c["O"], c["C"]) < P_level - eps)
                cond_disp = cond_close and disp >= disp_min
                policy_ok = (cond_close if break_policy == "CLOSE"
                             else (cond_body if break_policy == "BODY"
                                   else cond_disp))
                if not policy_ok:
                    continue
                bm = break_mag(c["C"], P_level, at, eps)
                if bm < break_min_mag:
                    continue
                st = s_struct(bm, disp, vol_r, c, eps, bullish,
                              w["w_b"], w["w_d"], w["w_v"], w["w_c"],
                              theta_disp=disp_min)
                events.append({
                    "event_type": ("EV_STR_007_BOS_BULLISH" if bullish
                                   else "EV_STR_008_BOS_BEARISH"),
                    "level_index": level_idx,
                    "price_level": P_level,
                    "break_price": c["C"],
                    "break_mag": bm,
                    "disp": disp,
                    "vol_ratio": vol_r,
                    "strength": st,
                    "candle_index": t_idx,
                    "timestamp": c["close_time"],
                    "policy": break_policy,
                    "q_tag": "Q3" if st["S"] > 0.6 else "Q2",
                    "snapshot_id": generate_snapshot_id(
                        {"t": t_idx, "P": P_level, "c": c["C"],
                         "i": level_idx}),
                    "level_snapshot_id": level.get("snapshot_id"),
                })
    return events


def _structure_state_up_to(swings: Sequence[Dict[str, Any]],
                           idx: int) -> str:
    """Recent HH/HL vs LH/LL classification (§4.7)."""
    recent = [s for s in swings if s["index"] < idx][-4:]
    if len(recent) < 2:
        return "RANGE"
    highs = [s for s in recent if s["type"] == "HIGH"]
    lows = [s for s in recent if s["type"] == "LOW"]
    if len(highs) >= 2 and len(lows) >= 2:
        if (highs[-1]["price"] > highs[-2]["price"]
                and lows[-1]["price"] > lows[-2]["price"]):
            return "BULL"
        if (highs[-1]["price"] < highs[-2]["price"]
                and lows[-1]["price"] < lows[-2]["price"]):
            return "BEAR"
    return "RANGE"


def detect_choch(candles: Sequence[Dict[str, Any]],
                 swings: Sequence[Dict[str, Any]],
                 bos_events: Sequence[Dict[str, Any]], atr_n: int = 14,
                 accept_wicks: bool = False,
                 tick: float = 0.01,
                 atr_override: Optional[float] = None
                 ) -> List[Dict[str, Any]]:
    """CHoCH/MSS — four explicit PIT-safe conditions (§3.7/§4.7)."""
    events: List[Dict[str, Any]] = []
    eps = scaled_epsilon(candles, tick)
    swing_highs = [s for s in swings if s["type"] == "HIGH"]
    swing_lows = [s for s in swings if s["type"] == "LOW"]
    for t_idx, c in enumerate(candles):
        if c["H"] < c["L"]:
            continue
        if atr_override is None and t_idx + 1 < atr_n + 1:
            continue   # ATR warmup
        state_prev = _structure_state_up_to(swings, t_idx)
        if state_prev == "RANGE":
            continue
        at = (atr_override if atr_override is not None
              else atr_sma(candles[:t_idx + 1], atr_n))
        if state_prev == "BEAR":
            lhs = [s for s in swing_highs if s["index"] < t_idx]
            if not lhs:
                continue
            last_lh = lhs[-1]
            cond_price = c["C"] > last_lh["price"] + (0 if accept_wicks else eps)
            cond_body = (True if accept_wicks
                         else min(c["O"], c["C"]) > last_lh["price"] + eps)
            time_order = last_lh["index"] < t_idx
            prev_bos_bear = any(
                be["candle_index"] < t_idx
                and be["event_type"] == "EV_STR_008_BOS_BEARISH"
                for be in bos_events)
            if cond_price and cond_body and time_order and prev_bos_bear:
                bm = break_mag(c["C"], last_lh["price"], at, eps)
                events.append({
                    "event_type": "EV_STR_009_CHOCHE_BULLISH",
                    "price_level": last_lh["price"],
                    "break_price": c["C"],
                    "break_mag": bm,
                    "candle_index": t_idx,
                    "timestamp": c["close_time"],
                    "prev_state": state_prev,
                    "new_state": "BULL",
                    "q_tag": "Q3",
                    "snapshot_id": generate_snapshot_id(
                        {"t": t_idx, "P": last_lh["price"], "choch": "bull"}),
                })
        elif state_prev == "BULL":
            hls = [s for s in swing_lows if s["index"] < t_idx]
            if not hls:
                continue
            last_hl = hls[-1]
            cond_price = c["C"] < last_hl["price"] - (0 if accept_wicks else eps)
            cond_body = (True if accept_wicks
                         else max(c["O"], c["C"]) < last_hl["price"] - eps)
            time_order = last_hl["index"] < t_idx
            prev_bos_bull = any(
                be["candle_index"] < t_idx
                and be["event_type"] == "EV_STR_007_BOS_BULLISH"
                for be in bos_events)
            if cond_price and cond_body and time_order and prev_bos_bull:
                bm = break_mag(c["C"], last_hl["price"], at, eps)
                events.append({
                    "event_type": "EV_STR_010_CHOCHE_BEARISH",
                    "price_level": last_hl["price"],
                    "break_price": c["C"],
                    "break_mag": bm,
                    "candle_index": t_idx,
                    "timestamp": c["close_time"],
                    "prev_state": state_prev,
                    "new_state": "BEAR",
                    "q_tag": "Q3",
                    "snapshot_id": generate_snapshot_id(
                        {"t": t_idx, "P": last_hl["price"], "choch": "bear"}),
                })
    return events


def detect_retest_and_invalidation(
        candles: Sequence[Dict[str, Any]],
        bos_events: Sequence[Dict[str, Any]], atr_n: int = 14,
        retest_tol_atr: float = 0.25, expiry_bars: int = 48,
        inv_thr: float = 0.5, tick: float = 0.01,
        atr_override: Optional[float] = None
        ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Retest (§3.11: |C_{t'}−P| ≤ κ·ATR, close-based — ISSUE-CP2-004),
    invalidation (C beyond level ± θ_inv·ATR with BM_inv ≥ 0.5), expiry
    window (§4.8 flow order retained: retest checked first)."""
    retests: List[Dict[str, Any]] = []
    invalids: List[Dict[str, Any]] = []
    eps = scaled_epsilon(candles, tick)
    for bos in bos_events:
        P = bos["price_level"]
        t_bos = bos["candle_index"]
        is_bull = "BULLISH" in bos["event_type"]
        for t_idx in range(t_bos + 1, min(len(candles),
                                          t_bos + expiry_bars + 1)):
            c = candles[t_idx]
            if c["H"] < c["L"]:
                continue
            if atr_override is None and t_idx + 1 < atr_n + 1:
                continue   # ATR warmup
            at = (atr_override if atr_override is not None
                  else atr_sma(candles[:t_idx + 1], atr_n))
            tol = retest_tol_atr * at
            if abs(c["C"] - P) <= tol:
                retests.append({
                    "event_type": "EV_STR_011_RETEST",
                    "bos_snapshot_id": bos["snapshot_id"],
                    "bos_event_type": bos["event_type"],
                    "price_level": P,
                    "retest_price": c["C"],
                    "retest_tol": tol,
                    "candle_index": t_idx,
                    "timestamp": c["close_time"],
                    "tol_atr": retest_tol_atr,
                    "q_tag": "Q2",
                    "snapshot_id": generate_snapshot_id(
                        {"t": t_idx, "P": P, "retest": 1}),
                })
                break
            if is_bull:
                if c["C"] < P - inv_thr * at:
                    bm = break_mag(c["C"], P, at, eps)
                    invalids.append({
                        "event_type": "EV_STR_013_INVALIDATION",
                        "bos_snapshot_id": bos["snapshot_id"],
                        "bos_event_type": bos["event_type"],
                        "price_level": P,
                        "invalid_price": c["C"],
                        "break_mag": bm,
                        "candle_index": t_idx,
                        "timestamp": c["close_time"],
                        "q_tag": "Q2",
                        "snapshot_id": generate_snapshot_id(
                            {"t": t_idx, "P": P, "inv": 1}),
                    })
                    break
            else:
                if c["C"] > P + inv_thr * at:
                    bm = break_mag(c["C"], P, at, eps)
                    invalids.append({
                        "event_type": "EV_STR_013_INVALIDATION",
                        "bos_snapshot_id": bos["snapshot_id"],
                        "bos_event_type": bos["event_type"],
                        "price_level": P,
                        "invalid_price": c["C"],
                        "break_mag": bm,
                        "candle_index": t_idx,
                        "timestamp": c["close_time"],
                        "q_tag": "Q2",
                        "snapshot_id": generate_snapshot_id(
                            {"t": t_idx, "P": P, "inv": 1}),
                    })
                    break
    return retests, invalids


def detect_wick_rejection(candles: Sequence[Dict[str, Any]],
                          swings: Sequence[Dict[str, Any]], atr_n: int = 14,
                          tick: float = 0.01,
                          atr_override: Optional[float] = None
                          ) -> List[Dict[str, Any]]:
    """EV_STR_012 — wick above a prior swing high, close back below it
    (§4.8: the reference algorithm defines the rejection at swing highs)."""
    events: List[Dict[str, Any]] = []
    eps = scaled_epsilon(candles, tick)
    for t, c in enumerate(candles):
        if c["H"] < c["L"]:
            continue
        if atr_override is None and t + 1 < atr_n + 1:
            continue   # ATR warmup
        at = (atr_override if atr_override is not None
              else atr_sma(candles[:t + 1], atr_n))
        recent_highs = [s for s in swings
                        if s["type"] == "HIGH" and s["index"] < t][-1:]
        for rh in recent_highs:
            if c["H"] > rh["price"] + eps and c["C"] < rh["price"] - eps:
                if abs(c["H"] - rh["price"]) / max(at, eps) > 0.2:
                    events.append({
                        "event_type": "EV_STR_012_WICK_REJECTION",
                        "price_level": rh["price"],
                        "wick_high": c["H"],
                        "close": c["C"],
                        "candle_index": t,
                        "timestamp": c["close_time"],
                        "q_tag": "Q2",
                        "snapshot_id": generate_snapshot_id(
                            {"t": t, "P": rh["price"], "wick": 1}),
                    })
    return events


def compute_mtf_bias(states_by_tf: Dict[str, str],
                     tf_weights: Dict[str, float],
                     bias_threshold: float = 0.5) -> Dict[str, Any]:
    """Multi-scale bias (§3.10/§4.9)."""
    mapping = {"BULL": 1, "BEAR": -1, "RANGE": 0}
    bias = 0.0
    for tf, w in tf_weights.items():
        bias += w * mapping.get(states_by_tf.get(tf, "RANGE"), 0)
    label = "NEUTRAL"
    if bias > bias_threshold:
        label = "BULL"
    elif bias < -bias_threshold:
        label = "BEAR"
    return {"bias_value": bias, "bias_label": label, "weights": tf_weights,
            "snapshot_id": generate_snapshot_id({"bias": bias})}


# ===========================================================================
# §5 SCHEMA — objects, state machines, events, versioning, snapshot_id
# ===========================================================================

SWINGPOINT_REQUIRED: Tuple[str, ...] = (
    "type", "price", "index", "timestamp", "confirmed_at", "method",
    "q_tag", "snapshot_id", "version")
STRUCTURE_EVENT_REQUIRED: Tuple[str, ...] = (
    "event_type", "price_level", "break_price", "break_mag", "candle_index",
    "timestamp", "q_tag", "snapshot_id", "version")
SWING_TYPES = ("HIGH", "LOW")
SWING_METHODS = ("WILLIAMS", "GANN", "ZIGZAG")
SWING_FATES = ("CANDIDATE", "CONFIRMED", "ACTIVE", "PRUNED", "INVALIDATED",
               "EXPIRED", "RETESTED")
Q_TAGS = ("Q0", "Q1", "Q2", "Q3", "Q4", "Q5")
BREAK_POLICIES = ("CLOSE", "BODY", "DISPLACEMENT")
STRUCTURE_EVENT_TYPES = (
    "EV_STR_000_INVALID_CANDLE", "EV_STR_001_SWING_HIGH_CANDIDATE",
    "EV_STR_002_SWING_LOW_CANDIDATE", "EV_STR_003_SWING_HIGH_CONFIRMED",
    "EV_STR_004_SWING_LOW_CONFIRMED", "EV_STR_005_SWING_PRUNED",
    "EV_STR_006_SWING_EXTERNAL_CONFIRMED", "EV_STR_007_BOS_BULLISH",
    "EV_STR_008_BOS_BEARISH", "EV_STR_009_CHOCHE_BULLISH",
    "EV_STR_010_CHOCHE_BEARISH", "EV_STR_011_RETEST",
    "EV_STR_012_WICK_REJECTION", "EV_STR_013_INVALIDATION",
    "EV_STR_014_GAP", "EV_STR_015_EXTERNAL_VALIDATION",
    "EV_STR_016_BIAS_BULLISH", "EV_STR_017_BIAS_BEARISH",
    "EV_STR_018_STRENGTH_UPDATE", "EV_STR_019_EXPIRY",
    "EV_STR_020_BIAS_UPDATE")

EVENT_CATALOG: Dict[str, Dict[str, str]] = {
    "EV_STR_000": {"name": "INVALID_CANDLE", "q": "Q0"},
    "EV_STR_001": {"name": "SWING_HIGH_CANDIDATE", "q": "Q1"},
    "EV_STR_002": {"name": "SWING_LOW_CANDIDATE", "q": "Q1"},
    "EV_STR_003": {"name": "SWING_HIGH_CONFIRMED", "q": "Q2"},
    "EV_STR_004": {"name": "SWING_LOW_CONFIRMED", "q": "Q2"},
    "EV_STR_005": {"name": "SWING_PRUNED", "q": "Q2"},
    "EV_STR_006": {"name": "SWING_EXTERNAL_CONFIRMED", "q": "Q3"},
    "EV_STR_007": {"name": "BOS_BULLISH", "q": "Q2/Q3"},
    "EV_STR_008": {"name": "BOS_BEARISH", "q": "Q2/Q3"},
    "EV_STR_009": {"name": "CHOCH_BULLISH", "q": "Q3"},
    "EV_STR_010": {"name": "CHOCH_BEARISH", "q": "Q3"},
    "EV_STR_011": {"name": "RETEST", "q": "Q2"},
    "EV_STR_012": {"name": "WICK_REJECTION", "q": "Q2"},
    "EV_STR_013": {"name": "INVALIDATION", "q": "Q2"},
    "EV_STR_014": {"name": "GAP", "q": "Q1/Q2"},
    "EV_STR_015": {"name": "EXTERNAL_VALIDATION", "q": "Q3"},
    "EV_STR_016": {"name": "BIAS_BULLISH", "q": "Q3"},
    "EV_STR_017": {"name": "BIAS_BEARISH", "q": "Q3"},
    "EV_STR_018": {"name": "STRENGTH_UPDATE", "q": "Q5"},
    "EV_STR_019": {"name": "EXPIRY", "q": "Q2"},
    "EV_STR_020": {"name": "BIAS_UPDATE", "q": "Q3"},
}

# Swing fate state machine (§5.3): forward-only transitions.
SWING_FATE_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "CANDIDATE": ("CONFIRMED", "PRUNED"),
    "CONFIRMED": ("ACTIVE", "PRUNED"),
    "ACTIVE": ("RETESTED", "INVALIDATED", "EXPIRED", "PRUNED"),
    "RETESTED": ("ACTIVE", "INVALIDATED", "EXPIRED", "PRUNED"),
    "INVALIDATED": (),
    "EXPIRED": (),
    "PRUNED": (),
}

# Overall market state machine (§5.3). The blueprint's fourth transition
# source line reads "AUTC_W2 --no BOS in expiry--> RANGE"; the four named
# states are BULL/BEAR/RANGE/TRANSITION, so the garbled token is read as
# TRANSITION (ISSUE-CP2-001).
MARKET_STATES = ("BULL", "BEAR", "RANGE", "TRANSITION")
MARKET_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "BULL": ("BULL", "TRANSITION", "RANGE"),
    "BEAR": ("BEAR", "TRANSITION", "RANGE"),
    "RANGE": ("BULL", "BEAR", "RANGE"),
    "TRANSITION": ("BULL", "BEAR", "RANGE", "TRANSITION"),
}


class StructureState:
    """Event-driven structural state (§5.3 table, strict transitions only)."""

    def __init__(self) -> None:
        self.state = "RANGE"

    def on_event(self, event: Dict[str, Any]) -> str:
        et = event.get("event_type", "")
        s = 0.0
        if isinstance(event.get("strength"), dict):
            s = event["strength"].get("S", 0.0)
        if et == "EV_STR_007_BOS_BULLISH":
            if self.state in ("BULL", "TRANSITION"):
                self.state = "BULL"
            elif self.state == "RANGE" and s > 0.6:
                self.state = "BULL"
            # BEAR -> BULL direct is not a legal transition (ignored)
        elif et == "EV_STR_008_BOS_BEARISH":
            if self.state in ("BEAR", "TRANSITION"):
                self.state = "BEAR"
            elif self.state == "RANGE" and s > 0.6:
                self.state = "BEAR"
            # BULL -> BEAR direct is not a legal transition (ignored)
        elif et == "EV_STR_009_CHOCHE_BULLISH":
            if self.state == "BEAR":
                self.state = "TRANSITION"
        elif et == "EV_STR_010_CHOCHE_BEARISH":
            if self.state == "BULL":
                self.state = "TRANSITION"
        elif et == "EV_STR_019_EXPIRY":
            if self.state == "TRANSITION":
                self.state = "RANGE"
        return self.state


def validate_swingpoint(sw: Dict[str, Any]) -> None:
    """SwingPoint V4 schema required-fields check (§5.1)."""
    for k in SWINGPOINT_REQUIRED:
        if sw.get(k) in (None, ""):
            raise ValueError(f"SwingPoint missing required field {k!r}")
    if sw["type"] not in SWING_TYPES:
        raise ValueError(f"SwingPoint type {sw['type']!r} invalid")
    if sw["method"] not in SWING_METHODS:
        raise ValueError(f"SwingPoint method {sw['method']!r} invalid")
    if sw["q_tag"] not in Q_TAGS:
        raise ValueError(f"SwingPoint q_tag {sw['q_tag']!r} invalid")
    if sw["version"] != "4.0.0":
        raise ValueError(f"SwingPoint version {sw['version']!r} != 4.0.0")
    if sw["price"] <= 0:
        raise ValueError("SwingPoint price must be > 0")
    if len(sw["snapshot_id"]) != 64:
        raise ValueError("SwingPoint snapshot_id must be 64-hex")


def validate_structure_event(ev: Dict[str, Any]) -> None:
    """BOS/CHoCH Event V4 schema required-fields check (§5.2)."""
    for k in STRUCTURE_EVENT_REQUIRED:
        if ev.get(k) in (None, ""):
            raise ValueError(f"Structure event missing required field {k!r}")
    if ev["event_type"] not in STRUCTURE_EVENT_TYPES:
        raise ValueError(f"event_type {ev['event_type']!r} not in catalog")
    if ev["q_tag"] not in Q_TAGS:
        raise ValueError(f"q_tag {ev['q_tag']!r} invalid")
    if ev["break_mag"] < 0:
        raise ValueError("break_mag must be >= 0")
    if ev["version"] != "4.0.0":
        raise ValueError(f"version {ev['version']!r} != 4.0.0")


def with_schema_version(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach the const version 4.0.0 required by both V4 schemas."""
    for ev in events:
        ev.setdefault("version", "4.0.0")
    return events


# ===========================================================================
# §6 PARAMS — full governed table (§6; frozen defaults, never retuned in code)
# ===========================================================================

# The §9.5 tree names exactly six params YAMLs and none hosts E01's §6
# engine table; Params (apex.config) is keyed to those six names and is
# FROZEN CP-1 surface. Interim (ISSUE-CP2-006): the engine's §6 defaults
# live here as a frozen, single-source table; YAML-backed values (tick_size)
# are loaded from params/universe_v1.yaml at runtime.
E01_DEFAULTS: Dict[str, Any] = {
    "k_williams": 2,            # candles, 1..5 (GC-D: Williams k=2)
    "atr_n": 14,                # candles, 7..50
    "zigzag_threshold": 2.0,    # xATR, 1..5
    "break_policy": "CLOSE",    # CLOSE/BODY/DISPLACEMENT
    "break_min_mag": 0.3,       # xATR, 0.1..1.0
    "disp_min": 1.5,            # xSMA(R), 1..3
    "eq_tol": 0.15,             # xATR, 0.05..0.4
    "retest_tol_kappa": 0.25,   # xATR, 0.05..0.5
    "expiry_bars": 48,          # candles, 12..240
    "accept_wicks": False,      # policy
    "theta_depth": 0.8,         # xATR, 0.3..2.0
    "theta_maxAge": 120,        # candles, 30..300 (E01 §6; F31 keeps §2.1's 100)
    "theta_ext": 1.0,           # xATR, 0.5..2.0
    "gamma_gap": 1.8,           # xATR, 1..3
    "T_HTF": 0.15,              # xATR_HTF, 0.05..0.3
    "strength_weights": {"w_b": 0.38, "w_d": 0.27, "w_v": 0.19, "w_c": 0.16},
    "tf_weights": {"1D": 0.6, "1W": 0.4},
    "bias_threshold": 0.5,      # 0.1..0.9
    "max_levels": 3,            # 1..5
    "redundancy_thr": 0.9,      # 0.8..0.98
    "tick_size": None,          # dynamic — exchange info (universe_v1.yaml)
    "min_candles": 50,
}


def get_params(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Frozen §6 defaults, optionally overridden (governed change process
    only). Returns a fresh dict; callers never mutate the table."""
    params = dict(E01_DEFAULTS)
    if overrides:
        unknown = set(overrides) - set(params)
        if unknown:
            raise ValueError(f"unknown E01 params: {sorted(unknown)}")
        params.update(overrides)
    return params


def resolve_tick_size(symbol: str, params: Any = None) -> float:
    """tick_size is dynamic exchange info: from params/universe_v1.yaml
    (ISSUE-CP1-009 additive keys); fail-closed if the symbol is unknown."""
    if params is None:
        from apex.config import load_params
        params = load_params()
    ticks = params["universe"].get("tick_size", {})
    if symbol not in ticks:
        raise ValueError(f"tick_size unknown for {symbol} (universe_v1.yaml)")
    return float(ticks[symbol])


# ===========================================================================
# §7 ENCYCLOPEDIC COVERAGE — computational micro-structure metrics (Ch.1–5)
# ===========================================================================


def candle_features(c: Dict[str, Any], atr_now: float,
                    eps: float) -> Dict[str, Any]:
    """Ch.2 §12: BodyRatio, wicks, ClosePos and a Q-tag; doji when
    BodyRatio < 0.1 and Range/ATR > 0.7."""
    rng = candle_range(c)
    br = body_ratio(c, eps)
    cp = close_position(c, eps)
    doji = br <= 0.1 and rng / max(atr_now, eps) > 0.7
    q = "Q0" if c["H"] < c["L"] else "Q1"
    return {"body_ratio": br, "upper_wick": upper_wick(c),
            "lower_wick": lower_wick(c), "close_pos": cp,
            "range": rng, "is_doji": doji, "q_tag": q}


def stop_context(bos_event: Dict[str, Any], atr_now: float) -> Dict[str, Any]:
    """Ch.1/Ch.5 §9 risk context: stop at P ∓ 0.5·ATR by direction; if
    S < 0.5 the size is halved. Descriptive only — never a signal."""
    bullish = "BULLISH" in bos_event["event_type"]
    level = bos_event["price_level"]
    s = bos_event.get("strength", {}).get("S", 0.0)
    return {"stop_level": level - 0.5 * atr_now if bullish
            else level + 0.5 * atr_now,
            "halve_size": s < 0.5, "s_struct": s}


# ===========================================================================
# §8 VALIDATION — battery helpers (each §8 clause becomes an executed test)
# ===========================================================================


def deterministic_replay_hash(candles: Sequence[Dict[str, Any]],
                              params: Optional[Dict[str, Any]] = None
                              ) -> str:
    """§8.2: run the full pipeline, hash the canonical JSON of the event
    list (snapshot_ids derive from candle timestamps, never wall-clock)."""
    output = run_pipeline(candles, params or get_params())
    return _sha_of(_canon(output["events"]))


def _sha_of(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_CORE_EVENT_TYPES = ("EV_STR_007", "EV_STR_008", "EV_STR_009", "EV_STR_010",
                     "EV_STR_011", "EV_STR_012", "EV_STR_013", "EV_STR_014")


def no_future_leak_check(candles: Sequence[Dict[str, Any]],
                         params: Optional[Dict[str, Any]] = None
                         ) -> bool:
    """§8.3: for each t, set candles[t+1].H = 10·ATR (a fake future candle),
    run the engine only up through t, and compare events before/after —
    they must be identical. Additionally, early events (candle_index ≤
    t−k−1) must be invariant when the window grows (no reach-ahead)."""
    p = params or get_params()
    k = p["k_williams"]

    def _core_ids(output: Dict[str, Any], cut: int) -> set:
        return {e["snapshot_id"] for e in output["events"]
                if e.get("snapshot_id") is not None
                and e.get("candle_index") is not None
                and e["candle_index"] <= cut
                and e["event_type"].startswith(_CORE_EVENT_TYPES)}

    full = run_pipeline(candles, p)
    for t in range(p["min_candles"], len(candles) - 1):
        before = run_pipeline(candles[:t + 1], p)
        mutated = [dict(c) for c in candles[:t + 2]]
        at = 1.0
        if t + 1 >= p["atr_n"] + 1:
            try:
                at = atr_sma(candles[:t + 1], p["atr_n"])
            except ValueError:
                at = 1.0
        mutated[t + 1]["H"] = mutated[t + 1]["H"] + 10 * max(at, 1e-12)
        after = run_pipeline(mutated[:t + 1], p)
        if _canon(before["events"]) != _canon(after["events"]):
            return False
        cut = t - k - 1
        if cut >= 0 and _core_ids(before, cut) != _core_ids(full, cut):
            return False
        early_swings_before = {s["snapshot_id"] for s in before["swings"]
                               if s["index"] <= cut}
        early_swings_full = {s["snapshot_id"] for s in full["swings"]
                             if s["index"] <= cut}
        if early_swings_before != early_swings_full:
            return False
    return True


def _canon(obj: Any) -> str:
    """Canonical JSON of any JSON-safe object (deterministic)."""
    from apex.identity.canonical_json import canonical_json
    return canonical_json(obj)


def ablation_strength(bos_event: Dict[str, Any]) -> Dict[str, float]:
    """§8.4: S_struct recomputed with each component removed (B/D/V/C)."""
    st = bos_event["strength"]
    w = E01_DEFAULTS["strength_weights"]
    s_full = st["S"]
    out = {"full": s_full}
    for comp, wkey in (("B", "w_b"), ("D", "w_d"), ("V", "w_v"), ("C", "w_c")):
        out[f"without_{comp}"] = s_full - w[wkey] * st[comp]
    return out


def run_pipeline(candles: Sequence[Dict[str, Any]],
                 params: Optional[Dict[str, Any]] = None
                 ) -> Dict[str, Any]:
    """Full §4.10 streaming flow over a closed-candle window (pure function
    of the window — deterministic, replay-safe)."""
    p = params or get_params()
    invalid = [{"event_type": "EV_STR_000_INVALID_CANDLE", "q_tag": "Q0",
                "candle": {"O": c["O"], "H": c["H"], "L": c["L"], "C": c["C"]}}
               for c in candles if c["H"] < c["L"]]
    clean = _ATRWindow(c for c in candles if not c["H"] < c["L"])
    if len(clean) < p["min_candles"]:
        return {"events": with_schema_version(invalid), "swings": [],
                "state": "RANGE", "bias": None}
    k = p["k_williams"]
    sw_w = detect_swings_williams(clean, k=k, tick=p["tick_size"] or 0.01)
    sw_g = detect_swings_gann(clean)
    active, pruned = merge_and_prune_swings(
        sw_w, sw_g, clean, atr_n=p["atr_n"], theta_depth=p["theta_depth"],
        theta_maxAge=p["theta_maxAge"], tick=p["tick_size"] or 0.01)
    gaps = detect_gaps(clean, gamma_gap=p["gamma_gap"], atr_n=p["atr_n"])
    bos = detect_bos(clean, active, atr_n=p["atr_n"],
                     break_policy=p["break_policy"],
                     break_min_mag=p["break_min_mag"],
                     disp_min=p["disp_min"], tick=p["tick_size"] or 0.01,
                     max_levels=p["max_levels"],
                     weights=p["strength_weights"])
    choch = detect_choch(clean, active, bos, atr_n=p["atr_n"],
                         accept_wicks=p["accept_wicks"],
                         tick=p["tick_size"] or 0.01)
    retests, invalids_ev = detect_retest_and_invalidation(
        clean, bos, atr_n=p["atr_n"], retest_tol_atr=p["retest_tol_kappa"],
        expiry_bars=p["expiry_bars"], tick=p["tick_size"] or 0.01)
    wicks = detect_wick_rejection(clean, active, atr_n=p["atr_n"],
                                  tick=p["tick_size"] or 0.01)
    state_machine = StructureState()
    for ev in sorted(bos + choch, key=lambda e: e["candle_index"]):
        state_machine.on_event(ev)
    all_events = (bos + choch + retests + invalids_ev + wicks + gaps + invalid)
    return {"events": with_schema_version(all_events), "swings": active,
            "pruned": pruned, "state": state_machine.state, "bias": None}


class StructureEngineStreaming:
    """§4.10 streaming engine: one closed candle in, new events out.
    Idempotent per candle (re-feeding the same candle returns no events);
    the full event list stays deduplicated by snapshot_id."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        if config and "dynamic_k" in config:
            raise WaveOutError("dynamic_williams_k",
                               "WAVE_OUT_DYNAMIC_WILLIAMS_K")
        self.config = config or get_params()
        self.candles: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []
        self._seen: set = set()

    def on_new_candle(self, candle: Dict[str, Any]) -> List[Dict[str, Any]]:
        if candle["H"] < candle["L"]:
            return [{"event_type": "EV_STR_000_INVALID_CANDLE",
                     "q_tag": "Q0",
                     "candle": {"O": candle["O"], "H": candle["H"],
                                "L": candle["L"], "C": candle["C"]}}]
        if self.candles and self.candles[-1].get("close_time") == candle.get(
                "close_time"):
            return []   # idempotent re-feed
        self.candles.append(candle)
        if len(self.candles) < self.config.get("min_candles", 50):
            return []
        output = run_pipeline(self.candles, self.config)
        fresh: List[Dict[str, Any]] = []
        for ev in output["events"]:
            key = ev.get("snapshot_id") or repr(sorted(ev.items()))
            if key not in self._seen:
                self._seen.add(key)
                self.events.append(ev)
                fresh.append(ev)
        return fresh


# ===========================================================================
# EngineBase integration — the frozen v4.0.0 contract surface (CP-1 base.py)
# ===========================================================================

ANALYST_VERSION = "4.0.0+" + "0" * 40   # SemVer + git40 (owner stamps git40)

_DIRECTION_MAP = {
    "EV_STR_007_BOS_BULLISH": 1, "EV_STR_009_CHOCHE_BULLISH": 1,
    "EV_STR_016_BIAS_BULLISH": 1, "EV_STR_008_BOS_BEARISH": -1,
    "EV_STR_010_CHOCHE_BEARISH": -1, "EV_STR_017_BIAS_BEARISH": -1,
}


def observation_to_candle(obs: MarketObservation, timeframe: str,
                          tf_seconds: int) -> Dict[str, Any]:
    """MarketObservation (store/catalog window) → §4 candle dict. Values
    cross the engine boundary as floats; identity/ordering metadata kept."""
    from apex.data_catalog.contracts import parse_utc_ms
    close_dt = parse_utc_ms(obs.timestamp)
    open_dt = close_dt - _timedelta_seconds(tf_seconds)
    return {
        "O": float(obs.open), "H": float(obs.high), "L": float(obs.low),
        "C": float(obs.close), "V": float(obs.volume or 0),
        "open_time": open_dt.strftime("%Y-%m-%dT%H:%M:%S.") +
        f"{open_dt.microsecond // 1000:03d}Z",
        "close_time": obs.timestamp,
        "availability_time": obs.availability_time,
        "bar_index": obs.sequence, "tf": timeframe, "symbol": obs.symbol,
        "content_hash": obs.content_hash(),
    }


def _timedelta_seconds(seconds: int):
    import datetime
    return datetime.timedelta(seconds=seconds)


class E01StructureEngine(EngineBase):
    """E01_Structure on the frozen EngineBase contract (v4.0.0).

    compute(symbol, timeframe, as_of, context):
      - window: context["window"] (streamed per-candle window from the data
        plane — the §4.10 model) or a synchronous WindowProvider
        (apex.data_catalog.catalog.WindowProvider); an async provider
        without a context window is fail-closed (MISSING_WINDOW_CONTEXT_QX)
        — see ISSUE-CP2-007.
      - context may carry: htf_swings, states_by_tf, atr_prev, provider.
      - returns validated 24-field EvidenceEvents (deterministic payloads;
        evidence_id is operational UUIDv7, never inside snapshot payloads).
    """

    engine_id = "E01"
    analyst_version = ANALYST_VERSION
    code_revision = "0" * 40

    def compute(self, symbol: str, timeframe: str, as_of: str,
                context: Optional[Dict[str, Any]] = None
                ) -> List[EvidenceEvent]:
        context = context or {}
        window_obs = self._resolve_window(symbol, timeframe, as_of, context)
        if not window_obs:
            return []
        tf_seconds = self._tf_seconds(timeframe)
        candles = [observation_to_candle(o, timeframe, tf_seconds)
                   for o in window_obs]
        tick = context.get("tick_size")
        if tick is None:
            tick = resolve_tick_size(symbol, self._params)
        params = get_params(context.get("e01_params"))
        params["tick_size"] = tick
        self.set_eps_inputs(tick, [c["C"] for c in candles[-20:]])
        _ = self.eps   # frozen scaled EPS (fail-closed if inputs missing)
        output = run_pipeline(candles, params)
        events = output["events"]
        if context.get("states_by_tf"):
            bias = compute_mtf_bias(context["states_by_tf"],
                                    params["tf_weights"],
                                    params["bias_threshold"])
            events = events + [{
                "event_type": "EV_STR_020_BIAS_UPDATE",
                "bias_value": bias["bias_value"],
                "bias_label": bias["bias_label"],
                "price_level": bias["bias_value"],
                "break_price": bias["bias_value"],
                "break_mag": abs(bias["bias_value"]),
                "candle_index": len(candles) - 1,
                "timestamp": candles[-1]["close_time"],
                "q_tag": "Q3",
                "snapshot_id": bias["snapshot_id"],
            }]
        for ev in events:
            if ev["event_type"] in (
                    "EV_STR_007_BOS_BULLISH", "EV_STR_008_BOS_BEARISH",
                    "EV_STR_009_CHOCHE_BULLISH", "EV_STR_010_CHOCHE_BEARISH"):
                validate_structure_event(ev)
        bos_events = [e for e in events
                      if e["event_type"].startswith("EV_STR_007")
                      or e["event_type"].startswith("EV_STR_008")]
        at = (atr_sma(candles, params["atr_n"])
              if len(candles) > params["atr_n"] else None)
        p_hat, n_out = (0.0, 0)
        if at is not None:
            p_fail, n_out = false_break_rate(bos_events, candles, at)
            p_hat = 1.0 - p_fail
        conf_lb = (wilson_ci(p_hat, n_out)[0] if n_out > 0 else 0.0)
        quality = self._window_quality(window_obs)
        input_hash = _sha_of(_canon([
            {"O": c["O"], "H": c["H"], "L": c["L"], "C": c["C"],
             "V": c["V"], "close_time": c["close_time"]} for c in candles]))
        replay = self.build_replay_key(
            symbol, timeframe, as_of, input_hash,
            "E01-STRUCT-V4.0.0-DEFAULTS", _canon(_param_view(params)))
        cached = self.replay_lookup(replay)
        if cached is not None:
            return cached
        result = [self._to_evidence(ev, symbol, timeframe, as_of, candles,
                                    quality, conf_lb, n_out, window_obs)
                  for ev in events]
        self.replay_store(replay, result)
        return result

    # -- helpers --------------------------------------------------------
    @staticmethod
    def _tf_seconds(timeframe: str) -> int:
        from apex.quality.pit import TF_DURATION_SECONDS
        return TF_DURATION_SECONDS[timeframe]

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

    def _to_evidence(self, ev: Dict[str, Any], symbol: str, timeframe: str,
                     as_of: str, candles: Sequence[Dict[str, Any]],
                     quality: float, conf_lb: float, n_out: int,
                     window_obs: Sequence[MarketObservation]) -> EvidenceEvent:
        et = ev["event_type"]
        direction = _DIRECTION_MAP.get(et, 0)
        # RETEST carries its parent BOS id in bos_snapshot_id but the event
        # itself is neutral context; INVALIDATION of a bullish break is a
        # bearish outcome and vice versa (event-type semantics only).
        if et == "EV_STR_013_INVALIDATION":
            parent_bull = "BULLISH" in str(ev.get("bos_event_type", ""))
            direction = -1 if parent_bull else 1
        strength = self._event_strength(ev)
        q_tag = ev.get("q_tag", "Q1")
        availability = ev.get("timestamp") or as_of
        age_bars = max(0, len(candles) - 1 - ev.get("candle_index",
                                                    len(candles) - 1))
        explanation = (f"{et} level={ev.get('price_level')} "
                       f"break_mag={ev.get('break_mag')}")
        if et == "EV_STR_014_GAP":
            explanation = f"{et} gap={ev.get('gap')} type={ev.get('type')}"
        lineage = tuple(o.content_hash() for o in window_obs[-20:])
        return EvidenceEvent(
            evidence_id=uuid_v7(),
            engine_id=self.engine_id,
            analyst_version=self.analyst_version,
            symbol=symbol, timeframe=timeframe,
            snapshot_id=ev.get("snapshot_id") or generate_snapshot_id(
                {"event": et, "t": ev.get("candle_index")}),
            event_time=ev.get("timestamp") or as_of,
            availability_time=availability,
            observation_window={"bars": len(candles),
                                "first": candles[0]["close_time"],
                                "last": candles[-1]["close_time"]},
            feature_snapshot_id=_sha_of(_canon(
                {"window": [c["close_time"] for c in candles[-20:]]})),
            feature_dependencies=("window",),
            condition_state=et,
            direction=direction,
            strength=float(strength),
            confidence=float(conf_lb if n_out > 0 else 0.0),
            quality=float(quality),
            validity="VALID" if q_tag != "Q0" else "INVALID",
            fate_state=(LifecycleState.CONFIRMED if q_tag in ("Q2", "Q3")
                        else LifecycleState.CANDIDATE),
            age=float(age_bars),
            decay=float(math.exp(-0.1 * age_bars)),
            explanation=explanation,
            parameter_version="E01-STRUCT-V4.0.0/DEFAULTS-v1",
            lineage=lineage,
            resolution_class=q_tag if q_tag in (
                "Q0", "Q1", "Q2", "Q3", "Q4", "Q5") else "Q1",
        )

    @staticmethod
    def _event_strength(ev: Dict[str, Any]) -> float:
        """Intensity on the engine's own scale — chapter quantities only."""
        et = ev["event_type"]
        if et in ("EV_STR_007_BOS_BULLISH", "EV_STR_008_BOS_BEARISH"):
            return float(ev["strength"]["S"])
        if et in ("EV_STR_009_CHOCHE_BULLISH", "EV_STR_010_CHOCHE_BEARISH",
                  "EV_STR_013_INVALIDATION"):
            return float(ev["break_mag"])
        if et == "EV_STR_011_RETEST":
            tol = float(ev.get("retest_tol", 1.0)) or 1.0
            prox = 1.0 - abs(float(ev["retest_price"])
                             - float(ev["price_level"])) / tol
            return max(0.0, min(1.0, prox))
        if et == "EV_STR_012_WICK_REJECTION":
            return float(abs(ev["wick_high"] - ev["price_level"]))
        if et == "EV_STR_014_GAP":
            return float(ev["gap_atr"])
        if et.startswith("EV_STR_00"):
            return 0.0
        return 0.0


def _param_view(params: Dict[str, Any]) -> Dict[str, Any]:
    """JSON-safe parameter view for replay keys (deterministic)."""
    view = dict(params)
    tick = view.get("tick_size")
    view["tick_size"] = float(tick) if tick is not None else None
    return view
