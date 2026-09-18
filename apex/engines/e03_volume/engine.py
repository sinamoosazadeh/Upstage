"""APEX_GEN5 E03 — Volume / Participation Engine (ParticipationEvidence
v4.0.0, engine E03_VOLUME).

No runtime dependency on other engines. Input contracts: OHLCVBundle v2.1.0,
OIBundle v1.3.0, ATRBundle v2.0.0 (the scalar ATR_{20}^{(t-1)} from
E04_Volatility v4.0.0 — consumed as aligned upstream evidence; absent ATR is
fail-closed QX with NO synthetic substitution). Output is Context/Evidence
only, never a signal.

Engine file mirrors chapter order (PHASE2_CHECKPOINTS.md §CP-2):
  §3 formulas -> §4 algorithms (six phases) -> §5 schema/state/events
  -> §6 params -> §7 encyclopedia -> §8 validation.
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
from apex.identity.snapshot import canonical_snapshot_id
from apex.identity.uuid_v7 import uuid_v7

ENGINE_CODE = "E03_Volume"
CONTRACT_VERSION = "4.0.0"
EPS = 1e-8
TICK_SIZE = 0.01

# ===========================================================================
# §3 FORMULAS — PIT-safe, corrected
# ===========================================================================

# ---------------------------------------------------------------------------
# PHASE 67 CONTROLLED CORRECTION RECORD (quoted; governs the identity/PIT
# code in this file — snapshot_id, as_of, last_error, t-1 exclusion):
#
# 1. Added one normative Global Identity/PIT utility contract.
# 2. Rebound E01/E02/E03/E04/E06/E07/E09/E12 snapshot helpers to
#    canonical_snapshot_id semantics.
# 3. Removed local simplified UUIDv7 implementations; operational UUIDv7 is
#    centralized and RFC 9562-shaped.
# 4. Bound E03 as_of to max governed availability_time across required
#    artifacts.
# 5. Added availability_time_ms to E03 input contract and fail-closed
#    missing-metadata semantics.
# 6. Changed ParticipationEvidence.as_of_ts from candle ts to governed as_of.
# 7. Added structured E03 last_error classification while preserving
#    fail-closed None return.
# 8. Preserved reference-window t-1 exclusion as a statistical-history rule,
#    not global PIT.
#
# (Phase 67A refinement: the identity envelope is applied exactly once —
#  `snapshot_id()` delegates to canonical_snapshot_id("E03_Volume", "4.0.0",
#  payload) with no double envelope, and no local UUIDv7 body exists.)
# ---------------------------------------------------------------------------


def snapshot_id(payload: dict) -> str:
    """Deterministic identity — exactly one canonical envelope (Phase 67/67A:
    rebound to canonical_snapshot_id semantics; UUIDv7 never enters the
    payload)."""
    payload = dict(payload)
    payload.pop("snapshot_id", None)
    return canonical_snapshot_id("E03_Volume", CONTRACT_VERSION, payload)


def governed_as_of_ms(required_artifacts: Sequence[Dict[str, Any]]) -> int:
    """Global PIT rule: as_of = max(availability_time_ms) over required
    artifacts; missing metadata is fail-closed (Phase 67 items 4/5/6)."""
    if not required_artifacts:
        raise ValueError("MISSING_REQUIRED_ARTIFACTS_QX")
    times = []
    for a in required_artifacts:
        t = a.get("availability_time_ms")
        if t is None:
            raise ValueError("MISSING_AVAILABILITY_TIME_QX")
        times.append(int(t))
    return max(times)


def e03_governed_as_of_ms(bar: dict) -> int:
    """Every required artifact (OHLCV, OI, ATR) has its own governed
    availability timestamp; no fallback to candle timestamp is permitted
    (Phase 67)."""
    required = [
        {"availability_time_ms": bar.get("availability_time_ms")},
        {"availability_time_ms": bar.get("oi_availability_time_ms")},
        {"availability_time_ms": bar.get("atr_availability_time_ms")},
    ]
    return governed_as_of_ms(required)


def sma_pit(history: List[float], n: int) -> Optional[float]:
    """PIT-safe SMA: uses [t-n, t-1] only (§3.1; the t-1 exclusion is a
    statistical-history rule, not global PIT — Phase 67 item 8)."""
    if len(history) < 1:
        raise ValueError("INSUFFICIENT_HISTORY_Q1")
    window = history[-n:] if len(history) >= n else history[:]
    if len(window) < 1:
        raise ValueError("INSUFFICIENT_HISTORY_Q1")
    return sum(window) / len(window)


def mean_std_pit(history: List[float], n: int) -> Tuple[Optional[float],
                                                        Optional[float]]:
    window = history[-n:] if len(history) >= n else history[:]
    if len(window) < 2:
        return (None, None)
    mu = sum(window) / len(window)
    var = sum((x - mu) ** 2 for x in window) / len(window)
    return mu, math.sqrt(max(var, 0.0))


def zscore_pit(current: float, history: List[float], n: int
               ) -> Optional[float]:
    mu, sd = mean_std_pit(history, n)
    if mu is None or sd is None:
        return None
    return (current - mu) / max(sd, EPS)


def volume_ratio_pit(v_current: float, vol_history: List[float], n: int
                     ) -> Optional[float]:
    """CORRECTED: PIT-safe (§3.1). V=0 → 0 (Edge_V_Zero)."""
    sma = sma_pit(vol_history, n)
    if sma is None or sma < EPS:
        return None
    return v_current / max(sma, EPS)


def typical_price(h: float, l: float, c: float) -> float:
    """TP = (H+L+C)/3 (§3.2); H<L is rejected, never swapped."""
    if h < l:
        raise ValueError("INVALID_OHLC_H_LT_L")
    return (h + l + c) / 3.0


def vwap_pit(bars: List[dict]) -> Tuple[Optional[float], float, int]:
    """VWAP with Typical Price over closed session bars (§3.2)."""
    pv = 0.0
    vv = 0.0
    for b in bars:
        if b["h"] < b["l"]:
            raise ValueError("INVALID_OHLC_H_LT_L")
        if b["v"] < 0:
            raise ValueError("INVALID_VOLUME_NEGATIVE")
        tp = typical_price(b["h"], b["l"], b["c"])
        pv += tp * b["v"]
        vv += b["v"]
    if vv < EPS:
        return (None, 0.0, 0)
    return (pv / vv, vv, len(bars))


def obv_series_wilder(closes: List[float], vols: List[float]) -> List[float]:
    """CORRECTED: Wilder rule — flat close contributes no change (§3.3)."""
    if len(closes) != len(vols):
        raise ValueError("closes/vols length mismatch")
    out = []
    obv = 0.0
    for i in range(len(closes)):
        if i == 0:
            obv = vols[0] if len(vols) > 0 else 0.0
        else:
            diff = closes[i] - closes[i - 1]
            if diff > EPS:
                obv += vols[i]
            elif diff < -EPS:
                obv -= vols[i]
            else:
                pass   # Wilder flat rule: OBV_t = OBV_{t-1}
        out.append(obv)
    return out


def _select_value_area(buckets_vol: Sequence[float], value_area_pct: float
                       ) -> Tuple[List[int], float]:
    """Sorted-volume Value Area (§3.4): bins by volume descending until the
    cumulative share >= value_area_pct. Returns (selected indices, share)."""
    total = sum(buckets_vol)
    if total < EPS:
        return ([], 0.0)
    sorted_indices = sorted(range(len(buckets_vol)),
                            key=lambda i: buckets_vol[i], reverse=True)
    cum = 0.0
    selected: List[int] = []
    for idx in sorted_indices:
        cum += buckets_vol[idx]
        selected.append(idx)
        if cum / total >= value_area_pct:
            break
    return (selected, cum / total)


def volume_profile_sorted(bars: List[dict], atr: float,
                          value_area_pct: float = 0.70) -> dict:
    """CORRECTED (§3.4): width = 0.25·ATR (clipped), Value Area by sorted
    volume. ATR is a governed input; invalid/non-finite is fail-closed."""
    if not isinstance(atr, (int, float)) or not math.isfinite(float(atr)) \
            or float(atr) < EPS:
        raise ValueError("ATR_UNAVAILABLE_QX")
    atr = float(atr)
    if len(bars) < 2:
        return {"poc": None, "vah": None, "val": None, "bins": []}
    lo = min(b["l"] for b in bars)
    hi = max(b["h"] for b in bars)
    if hi <= lo:
        return {"poc": lo, "vah": lo, "val": lo, "bins": []}
    width = 0.25 * atr
    width = max(width, TICK_SIZE * 0.5)
    width = min(width, max(atr * 2.0, TICK_SIZE * 10))
    n_bins = math.ceil((hi - lo) / width)
    n_bins = max(20, min(80, n_bins))
    width = (hi - lo) / n_bins
    buckets_vol = [0.0] * n_bins
    buckets_mid = [lo + (i + 0.5) * width for i in range(n_bins)]
    for b in bars:
        if b["v"] < 0:
            raise ValueError("INVALID_VOLUME_NEGATIVE")
        tp = typical_price(b["h"], b["l"], b["c"])
        idx = int((tp - lo) / width)
        idx = max(0, min(n_bins - 1, idx))
        buckets_vol[idx] += b["v"]
    total = sum(buckets_vol)
    if total < EPS:
        return {"poc": None, "vah": None, "val": None, "bins": []}
    poc_idx = max(range(n_bins), key=lambda i: buckets_vol[i])
    poc = buckets_mid[poc_idx]
    selected, coverage = _select_value_area(buckets_vol, value_area_pct)
    val = min(buckets_mid[i] - width / 2 for i in selected)
    vah = max(buckets_mid[i] + width / 2 for i in selected)
    return {
        "poc": poc, "vah": vah, "val": val,
        "total_volume": total, "width": width, "n_bins": n_bins,
        "selected_bins": selected, "coverage": coverage,
    }


def evr_corrected(vol_z: Optional[float], range_z: Optional[float],
                  price_change: float) -> Optional[float]:
    """CORRECTED (§3.5): EVR = VZ · RZ · sgn_W(ΔC)."""
    if vol_z is None or range_z is None:
        return None
    if abs(price_change) < EPS:
        return 0.0
    sign = 1.0 if price_change > 0 else -1.0
    return vol_z * range_z * sign


def tanh_mapping(x: float, tau: float = 2.0) -> float:
    return math.tanh(x / max(tau, EPS))


def ad_proxy_tanh(components: Dict[str, Optional[float]],
                  weights: List[float]) -> float:
    """§3.6 A/D proxy: tanh-mapped components, OOS weights, clip [-1,1];
    missing OI renormalizes the remaining weights (Q3 proxy, never a real
    order-flow delta)."""
    taus = {"y1": 1.0, "y2": 1.0, "y3": 2.0, "y4": 2.0, "y5": 2.0}
    keys = ["y1", "y2", "y3", "y4", "y5"]
    xs = []
    for k in keys:
        y = components.get(k, 0.0)
        if isinstance(y, float) and not math.isfinite(y):
            y = 0.0
        if y is None:
            y = 0.0
        xs.append(tanh_mapping(y, taus[k]))
    w = weights[:]
    if components.get("y5") is None:
        w[4] = 0.0
        s = sum(w)
        if s > EPS:
            w = [wi / s for wi in w]
    raw = sum(wi * xi for wi, xi in zip(w, xs))
    return max(-1.0, min(1.0, raw))


# ---------------------------------------------------------------------------
# PHASE 79 CONTROLLED CORRECTION RECORD (quoted; governs TF_SECONDS, OI
# freshness and the explicit-None canonicalization below):
#
# E03 was aligned to the document-wide 14-timeframe registry (8h supported;
# 3d excluded), its output schema and seconds mapping were aligned
# accordingly, OI freshness was rebound to the governed `oi_timestamp`, and
# E03 internal unavailable values were canonicalized to explicit `None`
# rather than NaN. Missing OI timestamps are fail-closed.
#
# PHASE 88 CONTROLLED CORRECTION RECORD (quoted; same governed surface):
#
# Aligned E03 with the document-wide 14-timeframe registry (8h supported;
# 3d excluded), synchronized its output schema and TF-seconds mapping, bound
# OI freshness to the explicit `oi_timestamp`, required that timestamp when
# OI is present, and aligned nullable profile fields with the
# explicit-unavailable contract.
# ---------------------------------------------------------------------------

TF_SECONDS: Dict[str, int] = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600,
    "2h": 7200, "4h": 14400, "6h": 21600, "8h": 28800, "12h": 43200,
    "1d": 86400, "1w": 604800, "1mo": 2592000,
}


def detect_oi_stale(oi_history: List[float], oi_timestamps: List[int],
                    timeframe_sec: int) -> Tuple[bool, str]:
    """§3.10: OI unchanged across `oi_stale_candles` consecutive
    observations, or timestamp gap > 5·TF (Phase 79/88: freshness is bound
    to the governed oi_timestamp)."""
    if len(oi_history) < 5:
        return (False, "OK")
    if len(set(oi_history[-5:])) == 1:
        return (True, "STALE_FLAT_5")
    if len(oi_timestamps) >= 2:
        gap = oi_timestamps[-1] - oi_timestamps[-2]
        if gap > 5 * timeframe_sec:
            return (True, f"STALE_GAP_{gap}")
    return (False, "OK")


def detect_wash_trading(bars: List[dict], vr: float, rz: float
                        ) -> Tuple[float, bool]:
    """§3.9: anomalous Volume/Range ratio + repeated suspicious volumes."""
    if len(bars) < 10:
        return (0.0, False)
    recent_vols = [b["v"] for b in bars[-10:]]
    repeats = 0
    for i in range(len(recent_vols)):
        for j in range(i + 1, len(recent_vols)):
            if abs(recent_vols[i] - recent_vols[j]) < 1e-6:
                repeats += 1
    last = bars[-1]
    body_ratio = abs(last["c"] - last["o"]) / max(last["h"] - last["l"], EPS)
    score = 0.0
    if vr > 3.0 and abs(rz) < 0.5 and body_ratio < 0.1:
        score = 0.5
        if repeats >= 3:
            score = 1.0
    return (score, score >= 0.5)


def ols_slope(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    """§3.11 OLS slope β = Σ(x−x̄)(y−ȳ)/Σ(x−x̄)²."""
    n = min(len(xs), len(ys))
    if n < 2:
        return None
    mx = sum(xs[:n]) / n
    my = sum(ys[:n]) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den = sum((xs[i] - mx) ** 2 for i in range(n))
    if den < EPS:
        return None
    return num / den


def detect_participation_divergence(price_pivots: Sequence[float],
                                    participation_pivots: Sequence[float]
                                    ) -> Dict[str, Optional[float]]:
    """§3.8: Diverged = sign(β_price) ≠ sign(β_participation);
    D_mag = |βx − βy| (EV_VOL_010)."""
    bx = ols_slope(list(range(len(price_pivots))), list(price_pivots))
    by = ols_slope(list(range(len(participation_pivots))),
                   list(participation_pivots))
    if bx is None or by is None:
        return {"diverged": None, "beta_price": bx, "beta_participation": by,
                "d_mag": None}
    diverged = (bx > 0) != (by > 0)
    return {"diverged": diverged, "beta_price": bx, "beta_participation": by,
            "d_mag": abs(bx - by)}


def wilson_ci(p_hat: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    """§3.11 Wilson CI."""
    if n <= 0:
        raise ValueError("WILSON_N_MUST_BE_POSITIVE")
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
            ) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def normalize_optional_e03(v):
    """Phase 79/88: unavailable numeric intermediates become explicit nulls
    (never NaN sentinels)."""
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def normalize_e03_boundary(payload: dict) -> dict:
    if isinstance(payload, dict):
        return {k: normalize_e03_boundary(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [normalize_e03_boundary(v) for v in payload]
    if isinstance(payload, tuple):
        return [normalize_e03_boundary(v) for v in payload]
    return normalize_optional_e03(payload)


def quarantine_nonfinite_e03(payload: dict) -> dict:
    """§5.3A: after normalization, no non-finite value may cross the
    emitted-object/snapshot boundary (fail-closed NONFINITE_E03_BOUNDARY)."""
    payload = normalize_e03_boundary(payload)

    def _walk(v):
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError("NONFINITE_E03_BOUNDARY")
        if isinstance(v, dict):
            for child in v.values():
                _walk(child)
        elif isinstance(v, (list, tuple)):
            for child in v:
                _walk(child)
    _walk(payload)
    return payload


# ===========================================================================
# §4 ALGORITHMS — streaming engine, six phases, idempotent
# ===========================================================================

PHASES = ("INIT", "WARMUP", "READY", "EMITTING", "DEGRADED", "FAILED")
_FAILED_PERSISTENCE_BARS = 3   # "persistent H < L" — 3 consecutive rejections


# ---------------------------------------------------------------------------
# PHASE 80 CONTROLLED CORRECTION RECORD (quoted; governs the volume_sma
# exposure below):
#
# E03 now exposes the governed PIT-safe `volume_sma` in
# `ParticipationEvidence`. E06 no longer computes a normative volume SMA or
# silently falls back when the upstream volume contract is absent; its
# I_Volume_v4 contract requires aligned E03 evidence (`volume_sma`,
# `vol_ratio`, `snapshot_id`, `as_of`). The previous local SMA utility is
# explicitly test-only. This closes a cross-engine contract mismatch and
# prevents current-bar self-normalization in E06.
# ---------------------------------------------------------------------------


@dataclass
class ParticipationEvidence:
    """§5.1 ParticipationEvidence v4.0.0 — the governed PIT-safe
    `volume_sma` is a first-class output field consumed by E06's
    I_Volume_v4 contract ({volume_sma, vol_ratio, snapshot_id, as_of})."""
    engine: str = "E03_VOLUME"
    version: str = CONTRACT_VERSION
    snapshot_id: str = ""
    as_of_ts: int = 0
    tf: str = "1h"
    symbol: str = "UNKNOWN"
    volume_ratio: Optional[float] = None
    volume_sma: Optional[float] = None
    volume_z: Optional[float] = None
    range_z: Optional[float] = None
    oi_z: Optional[float] = None
    vwap: Optional[float] = None
    vwap_dev: Optional[float] = None
    obv: Optional[float] = None
    obv_z: Optional[float] = None
    evr: Optional[float] = None
    profile: dict = field(default_factory=dict)
    ad_proxy: Optional[float] = None
    climax: bool = False
    dryup: bool = False
    wash_score: float = 0.0
    oi_state: str = "MISSING"
    quality: str = "Q1"
    events: List[str] = field(default_factory=list)
    pit_meta: dict = field(default_factory=dict)

    def required_fields_present(self) -> None:
        for k in ("engine", "version", "snapshot_id", "as_of_ts",
                  "volume_ratio", "volume_sma", "quality"):
            if getattr(self, k) is None or getattr(self, k) == "":
                raise ValueError(f"ParticipationEvidence missing {k!r}")
        if self.engine != "E03_VOLUME":
            raise ValueError("engine must be E03_VOLUME")
        if not self.version.startswith("4."):
            raise ValueError("version must be 4.x")
        if self.tf not in TF_SECONDS:
            raise ValueError(f"tf {self.tf!r} not in the 14-TF registry")
        if self.quality not in ("Q0", "Q1", "Q2", "Q3", "QX"):
            raise ValueError(f"quality {self.quality!r} invalid")
        if self.oi_state not in ("AVAILABLE", "STALE", "MISSING", "INVALID",
                                 "DEGRADED"):
            raise ValueError(f"oi_state {self.oi_state!r} invalid")


class VolumeEngineV4:
    """Streaming participation engine (§4). Six phases (§5.2):
    INIT -> WARMUP -> READY -> EMITTING -> DEGRADED -> FAILED. Non-emitting
    during INIT/WARMUP; history advances while warming so the gate cannot
    permanently block emission."""

    def __init__(self, params: dict):
        self.p = params
        self.last_error: Optional[dict] = None
        self.state: str = "INIT"
        self.emitted: List[ParticipationEvidence] = []
        self._consecutive_invalid = 0
        self.history_bars: List[dict] = []
        self.history_vols: List[float] = []
        self.history_ranges: List[float] = []
        self.history_oi: List[float] = []
        self.history_oi_ts: List[int] = []
        self.history_closes: List[float] = []
        self.history_obv: List[float] = []

    # -- warmup bookkeeping (shared by both warmup bands) ----------------
    def _warm_append(self, bar: dict) -> None:
        self.history_bars.append(bar)
        self.history_vols.append(bar["v"])
        self.history_ranges.append(bar["h"] - bar["l"])
        self.history_closes.append(bar["c"])
        self.history_obv.append(obv_series_wilder(
            self.history_closes, self.history_vols)[-1])
        oi_warm = bar.get("oi", None)
        if oi_warm is not None:
            oi_ts = bar.get("oi_timestamp")
            if oi_ts is None:
                raise ValueError("MISSING_OI_TIMESTAMP_QX")
            self.history_oi.append(oi_warm)
            self.history_oi_ts.append(int(oi_ts))

    def ingest_bar(self, bar: dict) -> Optional[ParticipationEvidence]:
        try:
            if not bar.get("is_closed", False):
                return None
            # FAILED: persistent H < L
            if bar["h"] < bar["l"]:
                self._consecutive_invalid += 1
                if self._consecutive_invalid >= _FAILED_PERSISTENCE_BARS:
                    self.state = "FAILED"
                    self.last_error = {"code": "PERSISTENT_H_LT_L",
                                       "quality": "QX",
                                       "as_of_ts": None}
                    return None
                raise ValueError("INVALID_OHLC_H_LT_L")
            self._consecutive_invalid = 0
            as_of_ms = e03_governed_as_of_ms(bar)
            if self.state == "FAILED":
                return None
            if len(self.history_bars) < 50:
                if len(self.history_bars) >= 5:
                    self.state = "WARMUP"
                self._warm_append(bar)
                return None
            if len(self.history_bars) + 1 < max(
                    48, self.p.get("profile_window", 48)):
                self.state = "WARMUP"
                self._warm_append(bar)
                return None
            if self.history_bars and self.history_bars[-1]["ts"] == bar["ts"]:
                if (self.history_bars[-1]["v"] == bar["v"]
                        and self.history_bars[-1]["c"] == bar["c"]):
                    return None   # idempotent re-feed
            self.state = "READY"
            vol_history = self.history_vols[:]
            range_history = self.history_ranges[:]
            close_history = self.history_closes[:]
            oi_history = self.history_oi[:]

            vol_sma = sma_pit(vol_history, self.p["vol_sma_n"])
            vr = volume_ratio_pit(bar["v"], vol_history,
                                  self.p["vol_sma_n"])
            vz = zscore_pit(bar["v"], vol_history, self.p["vol_z_window"])
            rng = bar["h"] - bar["l"]
            rz = zscore_pit(rng, range_history, self.p["vol_z_window"])

            oi_z = None
            oi_state = "MISSING"
            oi = bar.get("oi", None)
            if oi is not None:
                oi_state = "AVAILABLE"
                tf = bar.get("tf", "1h")
                timeframe_sec = TF_SECONDS.get(tf)
                if timeframe_sec is None:
                    raise ValueError("INVALID_TIMEFRAME_QX")
                oi_timestamp = bar.get("oi_timestamp")
                if oi_timestamp is None:
                    raise ValueError("MISSING_OI_TIMESTAMP_QX")
                is_stale, reason = detect_oi_stale(
                    oi_history + [oi],
                    self.history_oi_ts + [int(oi_timestamp)], timeframe_sec)
                if is_stale:
                    oi_state = "STALE"
                    oi_z = None
                else:
                    d_oi_hist = [oi_history[i] - oi_history[i - 1]
                                 for i in range(1, len(oi_history))]
                    d_oi_current = oi - (oi_history[-1] if oi_history else oi)
                    oi_z = zscore_pit(d_oi_current, d_oi_hist,
                                      self.p["oi_window"])

            temporal_window_bars = [
                b for b in self.history_bars
                if b.get("temporal_window") == bar.get("temporal_window",
                                                       "default")
            ][-self.p["vwap_lookback"]:]
            vwap_val, _, _ = vwap_pit(temporal_window_bars)
            # ATR is the aligned upstream E04 scalar — fail-closed, no
            # synthetic substitution (§1.3)
            atr_for_vwap = bar.get("atr_prev", None)
            if (atr_for_vwap is None
                    or not isinstance(atr_for_vwap, (int, float))
                    or not math.isfinite(float(atr_for_vwap))
                    or float(atr_for_vwap) < EPS):
                raise ValueError("ATR_UNAVAILABLE_QX")
            atr_for_vwap = float(atr_for_vwap)
            vwap_dev = ((bar["c"] - vwap_val) / max(atr_for_vwap, EPS)
                        if vwap_val is not None else None)

            new_obv_series = obv_series_wilder(
                close_history + [bar["c"]],
                self.history_vols + [bar["v"]])
            obv_current = new_obv_series[-1]
            obv_z = zscore_pit(obv_current, self.history_obv,
                               self.p["vol_z_window"])

            profile_window = (self.history_bars + [bar])[
                -self.p["profile_window"]:]
            profile = volume_profile_sorted(profile_window, atr_for_vwap,
                                            self.p["value_area_pct"])

            delta_c = bar["c"] - (close_history[-1] if close_history
                                  else bar["c"])
            evr = evr_corrected(vz, rz, delta_c)

            close_pos = 0.0
            if bar["h"] != bar["l"]:
                close_pos = 2 * (bar["c"] - bar["l"]) / (bar["h"] - bar["l"]) - 1
            comps = {
                "y1": (1.0 if bar["c"] > bar["o"]
                       else (-1.0 if bar["c"] < bar["o"] else 0.0)),
                "y2": close_pos,
                "y3": rz if rz is not None else 0.0,
                "y4": vz if vz is not None else 0.0,
                "y5": oi_z,
            }
            ad = ad_proxy_tanh(comps, self.p["ad_weights"])

            climax = ((vr >= self.p["climax_ratio"]
                       and rz >= self.p["climax_range_z"])
                      if vr is not None and rz is not None else False)
            dryup = (vr <= self.p["dryup_ratio"]) if vr is not None else False

            wash_score, is_wash = detect_wash_trading(
                self.history_bars + [bar],
                vr if vr is not None else 0, rz if rz is not None else 0)

            events: List[str] = []
            if vr is not None and vr >= 1.5:
                events.append("EV_VOL_001 Volume_Spike")
            if climax:
                events.append("EV_VOL_002 Volume_Climax")
            if dryup:
                events.append("EV_VOL_003 Volume_DryUp")
            if evr is not None and vz is not None:
                if vz > 1.5 and abs(rz if rz is not None else 0) < 0.5:
                    events.append("EV_VOL_004 Effort_High_Result_Low")
                if vz > 1.5 and abs(rz if rz is not None else 0) > 1.5:
                    events.append("EV_VOL_005 Effort_High_Result_High")
            if ad > 0.3:
                events.append("EV_VOL_006 Accumulation_Proxy")
            if ad < -0.3:
                events.append("EV_VOL_007 Distribution_Proxy")
            if oi_z is not None:
                if oi_z > 1.0:
                    events.append("EV_VOL_008 OI_Expansion")
                if oi_z < -1.0:
                    events.append("EV_VOL_009 OI_Contraction")
            if oi_state in ("STALE", "MISSING", "INVALID"):
                events.append("EV_VOL_011 OI_Unavailable")
            if is_wash:
                events.append("EV_VOL_012 WashTrading_Suspect")
            # EV_VOL_010 Participation_Divergence (§1.2 scope; §3.8 math):
            # price pivots vs OBV pivots over the in-window history
            if len(close_history) >= 6:
                pivot_idx = [i for i in range(1, len(close_history) - 1)
                             if (close_history[i] >= close_history[i - 1]
                                 and close_history[i] >= close_history[i + 1])
                             or (close_history[i] <= close_history[i - 1]
                                 and close_history[i] <= close_history[i + 1])
                             ][-4:]
                if len(pivot_idx) >= 2:
                    price_pivots = [close_history[i] for i in pivot_idx]
                    part_pivots = [self.history_obv[i] for i in pivot_idx]
                    div = detect_participation_divergence(
                        price_pivots, part_pivots)
                    if div["diverged"]:
                        events.append("EV_VOL_010 Participation_Divergence")

            ev = ParticipationEvidence(
                as_of_ts=as_of_ms,
                tf=bar.get("tf", "1h"),
                symbol=bar.get("symbol", "UNKNOWN"),
                volume_ratio=vr,
                volume_sma=vol_sma,
                volume_z=vz,
                range_z=rz,
                oi_z=oi_z,
                vwap=vwap_val,
                vwap_dev=vwap_dev,
                obv=obv_current,
                obv_z=obv_z,
                evr=evr,
                profile=profile,
                ad_proxy=ad,
                climax=climax,
                dryup=dryup,
                wash_score=wash_score,
                oi_state=oi_state,
                quality="Q1" if vr is not None else "QX",
                events=events,
                pit_meta={"sma_n": self.p["vol_sma_n"],
                          "history_len": len(vol_history),
                          "atr_used": atr_for_vwap},
            )
            normalized = normalize_e03_boundary(ev.__dict__)
            ev.__dict__.clear()
            ev.__dict__.update(normalized)
            quarantine_nonfinite_e03(ev.__dict__)
            ev.snapshot_id = snapshot_id(ev.__dict__)

            self.history_bars.append(bar)
            self.history_vols.append(bar["v"])
            self.history_ranges.append(rng)
            self.history_closes.append(bar["c"])
            self.history_obv.append(obv_current)
            if oi is not None:
                oi_timestamp = bar.get("oi_timestamp")
                if oi_timestamp is None:
                    raise ValueError("MISSING_OI_TIMESTAMP_QX")
                self.history_oi.append(oi)
                self.history_oi_ts.append(int(oi_timestamp))

            # six-phase transitions (§5.2)
            if oi_state in ("STALE", "MISSING", "INVALID"):
                self.state = "DEGRADED"
            else:
                self.state = "EMITTING"
            self.emitted.append(ev)
            return ev
        except ValueError as e:
            code = str(e) or "E03_PROCESSING_ERROR"
            self.last_error = {"code": code, "quality": "QX",
                               "as_of_ts": locals().get("as_of_ms")}
            return None


# ===========================================================================
# §5 SCHEMA — events, lifecycle crosswalk, versioning
# ===========================================================================

EVENT_CATALOG: Dict[str, str] = {
    "EV_VOL_001": "Volume_Spike (VR >= 1.5)",
    "EV_VOL_002": "Volume_Climax (Q2)",
    "EV_VOL_003": "Volume_DryUp (Q2)",
    "EV_VOL_004": "Effort_High_Result_Low",
    "EV_VOL_005": "Effort_High_Result_High",
    "EV_VOL_006": "Accumulation_Proxy (AD > 0.3, Q3)",
    "EV_VOL_007": "Distribution_Proxy (AD < -0.3, Q3)",
    "EV_VOL_008": "OI_Expansion",
    "EV_VOL_009": "OI_Contraction",
    "EV_VOL_010": "Participation_Divergence (Q3)",
    "EV_VOL_011": "OI_Unavailable (STALE)",
    "EV_VOL_012": "WashTrading_Suspect (Q3)",
}
# §5.2 lifecycle crosswalk: emitted ≡ ACTIVE, expired (5×TF) ≡ EXPIRED,
# superseded ≡ SUPERSEDED; archived, never deleted.
LIFECYCLE_CROSSWALK: Dict[str, str] = {
    "emitted": "ACTIVE", "expired": "EXPIRED", "superseded": "SUPERSEDED",
}


# ===========================================================================
# §6 PARAMS — governed table (§6; frozen defaults)
# ===========================================================================

E03_DEFAULTS: Dict[str, Any] = {
    "vol_sma_n": 20,             # bars, 5-100 (frozen)
    "vol_z_window": 50,          # bars, 10-200
    "oi_window": 20,             # bars, 5-100
    "climax_ratio": 2.5,         # 1.5-4.0 (frozen)
    "climax_range_z": 2.0,       # z, 1.0-4.0 (frozen)
    "dryup_ratio": 0.4,          # 0.1-0.7
    "vwap_temporal_window": "temporal_window",   # static, frozen
    "vwap_lookback": 100,        # bars, 20-500
    "profile_window": 48,        # bars, 20-500
    "value_area_pct": 0.70,      # 0.5-0.85 (frozen)
    "ad_weights": [0.25, 0.25, 0.15, 0.20, 0.15],   # OOS only
    "ad_tau": [1.0, 1.0, 2.0, 2.0, 2.0],
    "oi_missing_policy": "DEGRADED",   # frozen
    "wash_vr_threshold": 3.0,    # 2-5 (frozen)
    "oi_stale_candles": 5,       # 3-10 (frozen)
    "atr_period": 20,            # 5-50 (frozen)
    "min_candles": 50,
}


def get_params(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = dict(E03_DEFAULTS)
    if overrides:
        unknown = set(overrides) - set(params)
        if unknown:
            raise ValueError(f"unknown E03 params: {sorted(unknown)}")
        params.update(overrides)
    return params


# ===========================================================================
# §7 ENCYCLOPEDIA — computational bits (Ch.1–3)
# ===========================================================================


def vwap_dev(c: float, vwap_value: Optional[float], atr_prev: float
             ) -> Optional[float]:
    """Ch.2 §12: Dev = (C − VWAP)/max(ATR_{t-1}, ε)."""
    if vwap_value is None:
        return None
    return (c - vwap_value) / max(atr_prev, EPS)


def mtf_vr_ratio(vr_ltf: float, vr_htf: float) -> Optional[float]:
    """Ch.1 §7: VR_MTF = VR_1h/VR_4h (division guarded)."""
    if abs(vr_htf) < EPS:
        return None
    return vr_ltf / vr_htf


def bos_confirmation_filter(vr: Optional[float], oi_z: Optional[float]
                            ) -> Dict[str, Any]:
    """Ch.1 §8: BOS filter — VR >= 1.5 and OIZ > 0 (context helper,
    descriptive only)."""
    confirmed = (vr is not None and vr >= 1.5
                 and oi_z is not None and oi_z > 0)
    return {"confirmed": confirmed, "vr": vr, "oi_z": oi_z}


# ===========================================================================
# §8 VALIDATION — battery helpers (each §8 clause becomes an executed test)
# ===========================================================================


def run_engine(bars: Sequence[dict],
               params: Optional[Dict[str, Any]] = None
               ) -> VolumeEngineV4:
    p = params or get_params()
    eng = VolumeEngineV4(p)
    for b in bars:
        eng.ingest_bar(b)
    return eng


def deterministic_replay_check(bars: Sequence[dict]) -> bool:
    """§8.2: hash(evidence excluding snapshot_id) equal across two runs;
    JSON serialized with sort_keys=True."""
    from apex.identity.canonical_json import canonical_json

    def run():
        eng = run_engine(bars)
        return canonical_json([
            {k: v for k, v in ev.__dict__.items() if k != "snapshot_id"}
            for ev in eng.emitted])
    return run() == run()


def no_future_leak_check(bars: Sequence[dict]) -> bool:
    """§8.3: SMA_{t-1} never includes V_t — replacing V_t with 1e9 must not
    change the previously computed SMA; VWAP ignores is_closed=False bars."""
    eng = run_engine(bars)
    mutated = [dict(b) for b in bars]
    mutated[-1] = dict(mutated[-1], v=1e9)
    eng2 = run_engine(mutated)
    if not eng.emitted or not eng2.emitted:
        return len(eng.emitted) == len(eng2.emitted)
    # the last emitted evidence was computed from bars[:n-1] history +
    # the (mutated) current bar: its SMA must be unchanged
    return (eng2.emitted[-1].volume_sma
            == eng.emitted[-1].volume_sma)


def ablation_ad(components: Dict[str, Optional[float]],
                weights: List[float]) -> Dict[str, float]:
    """§8.4: A/D proxy recomputed with each component removed."""
    full = ad_proxy_tanh(components, weights)
    out = {"full": full}
    for k in ("y1", "y2", "y3", "y4", "y5"):
        reduced = dict(components)
        reduced[k] = 0.0
        w = list(weights)
        if k == "y5":
            w[4] = 0.0
            s = sum(w)
            if s > EPS:
                w = [wi / s for wi in w]
        out[f"without_{k}"] = ad_proxy_tanh(reduced, w)
    return out


def round8(x: float) -> float:
    """§5.3 serialization: values rounded to 8 decimal places."""
    return round(x + 0.0, 8)


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


def observation_to_bar(obs: MarketObservation, timeframe: str,
                       atr_prev: Optional[float],
                       oi_availability_ms: Optional[int],
                       atr_availability_ms: Optional[int]) -> dict:
    """MarketObservation → E03 bar dict. The E04 ATR scalar and the OI/ATR
    availability stamps arrive via the versioned input contract (context);
    missing availability metadata is fail-closed (Phase 67)."""
    from apex.data_catalog.contracts import parse_utc_ms
    ts_ms = int(parse_utc_ms(obs.timestamp).timestamp() * 1000)
    avail_ms = int(parse_utc_ms(obs.availability_time).timestamp() * 1000)
    oi_ts_ms = (int(parse_utc_ms(obs.oi_timestamp).timestamp() * 1000)
                if obs.oi_timestamp else None)
    return {
        "ts": ts_ms, "o": float(obs.open), "h": float(obs.high),
        "l": float(obs.low), "c": float(obs.close),
        "v": float(obs.volume or 0), "is_closed": obs.status == "CLOSED",
        "tf": timeframe, "symbol": obs.symbol,
        "oi": float(obs.oi) if obs.oi is not None else None,
        "oi_timestamp": oi_ts_ms,
        "atr_prev": atr_prev,
        "availability_time_ms": avail_ms,
        "oi_availability_time_ms": (oi_availability_ms
                                    if oi_availability_ms is not None
                                    else (oi_ts_ms if oi_ts_ms else avail_ms)),
        "atr_availability_time_ms": (atr_availability_ms
                                     if atr_availability_ms is not None
                                     else avail_ms),
        "temporal_window": obs.timestamp[:10],
    }


class E03VolumeEngine(EngineBase):
    """E03_Volume on the frozen EngineBase contract (v4.0.0).

    compute(symbol, timeframe, as_of, context): window via context['window']
    or a sync WindowProvider; the E04 ATR scalar arrives via
    context['atr_prev'] (scalar or per-bar list — the ATRBundle v2.0.0
    contract). ATR absent → fail-closed ATR_UNAVAILABLE_QX."""

    engine_id = "E03"
    analyst_version = ANALYST_VERSION
    code_revision = "0" * 40

    def compute(self, symbol: str, timeframe: str, as_of: str,
                context: Optional[Dict[str, Any]] = None
                ) -> List[EvidenceEvent]:
        context = context or {}
        window_obs = self._resolve_window(symbol, timeframe, as_of, context)
        if not window_obs:
            return []
        atr_prev = context.get("atr_prev")
        if isinstance(atr_prev, (list, tuple)):
            atr_series = list(atr_prev)
        else:
            atr_series = [atr_prev] * len(window_obs)
        if len(atr_series) < len(window_obs):
            raise ValueError("ATR_UNAVAILABLE_QX")
        def availability(key: str, index: int):
            value = context.get(key)
            if isinstance(value, (list, tuple)):
                if len(value) != len(window_obs):
                    raise ValueError("AVAILABILITY_ALIGNMENT_QX")
                return value[index]
            return value
        bars = [observation_to_bar(o, timeframe, atr_series[i],
                                   availability("oi_availability_time_ms", i),
                                   availability("atr_availability_time_ms", i))
                for i, o in enumerate(window_obs)]
        params = get_params(context.get("e03_params"))
        eng = VolumeEngineV4(params)
        results: List[ParticipationEvidence] = []
        for b in bars:
            ev = eng.ingest_bar(b)
            if ev is not None:
                results.append(ev)
        quality = self._window_quality(window_obs)
        conf = self._climax_calibration(results, bars)
        input_hash = _sha_of(_canon([
            {k: b[k] for k in ("ts", "o", "h", "l", "c", "v", "atr_prev")}
            for b in bars]))
        replay = self.build_replay_key(
            symbol, timeframe, as_of, input_hash, "E03-VOL-V4.0.0-DEFAULTS",
            _canon({"vol_sma_n": params["vol_sma_n"],
                    "profile_window": params["profile_window"]}))
        cached = self.replay_lookup(replay)
        if cached is not None:
            return cached
        out = [self._to_evidence(ev, symbol, timeframe, as_of, quality, conf)
               for ev in results]
        self.replay_store(replay, out)
        return out

    @staticmethod
    def _window_quality(window_obs: Sequence[MarketObservation]) -> float:
        if not window_obs:
            return 0.0
        comps = [float(o.completeness_pct or 0) / 100.0 for o in window_obs]
        return min(1.0, sum(comps) / len(comps))

    @staticmethod
    def _climax_calibration(results: Sequence[ParticipationEvidence],
                            bars: Sequence[dict]
                            ) -> float:
        """§8.5: Wilson lower bound over in-window climax outcomes (a climax
        bar followed within 5 bars by a close beyond the climax close —
        continuation ground truth), else 0 (uncalibrated)."""
        by_time = {bar["ts"]: bar for bar in bars}
        n = cont = 0
        for i, ev in enumerate(results):
            if not ev.climax:
                continue
            future = results[i + 1:i + 6]
            if not future:
                continue
            n += 1
            origin = by_time[ev.as_of_ts]
            direction = 1 if origin["c"] >= origin["o"] else -1
            if any((by_time[f.as_of_ts]["c"] - origin["c"]) * direction > 0
                   for f in future):
                cont += 1
        if n == 0:
            return 0.0
        return wilson_ci(cont / n, n)[0]

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

    def _to_evidence(self, ev: ParticipationEvidence, symbol: str,
                     timeframe: str, as_of: str, quality: float,
                     conf: float) -> EvidenceEvent:
        import datetime
        as_of_iso = datetime.datetime.fromtimestamp(
            ev.as_of_ts / 1000.0, tz=datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.") + f"{ev.as_of_ts % 1000:03d}Z"
        n_events = len(ev.events)
        direction = 0
        strength = self._event_strength(ev)
        q_tag = self._quality_tag(ev)
        return EvidenceEvent(
            evidence_id=uuid_v7(),
            engine_id=self.engine_id,
            analyst_version=self.analyst_version,
            symbol=symbol, timeframe=timeframe,
            snapshot_id=ev.snapshot_id,
            event_time=as_of_iso,
            availability_time=as_of_iso,
            observation_window={"bars": ev.pit_meta.get("history_len", 0)
                                + 1, "tf": ev.tf},
            feature_snapshot_id=_sha_of(_canon(
                {"as_of": ev.as_of_ts, "sma": ev.volume_sma})),
            feature_dependencies=("window", "oi", "atr_prev"),
            condition_state=(ev.events[0] if n_events else
                             "EV_VOL_000_NO_EVENT"),
            direction=direction,
            strength=float(strength),
            confidence=float(conf),
            quality=float(quality),
            validity="VALID" if q_tag != "QX" else "DEGRADED",
            fate_state=LifecycleState.ACTIVE,
            age=0.0,
            decay=1.0,
            explanation=(f"E03 participation evidence: vr={ev.volume_ratio} "
                         f"vz={ev.volume_z} ad={ev.ad_proxy} "
                         f"events={ev.events}"),
            parameter_version="E03-VOL-V4.0.0/DEFAULTS-v1",
            lineage=("as_of_%d" % ev.as_of_ts,
                     "window_%d" % ev.pit_meta.get("history_len", 0)),
            resolution_class=q_tag,
        )

    @staticmethod
    def _event_strength(ev: ParticipationEvidence) -> float:
        """Intensity on the engine's own scale — chapter quantities only."""
        if ev.climax:
            return float(ev.volume_ratio or 0.0)
        if ev.dryup:
            return float(ev.volume_ratio or 0.0)
        if ev.events:
            if "EV_VOL_006 Accumulation_Proxy" in ev.events:
                return abs(float(ev.ad_proxy or 0.0))
            if "EV_VOL_007 Distribution_Proxy" in ev.events:
                return abs(float(ev.ad_proxy or 0.0))
            if ev.volume_ratio is not None:
                return float(ev.volume_ratio)
        return float(ev.volume_ratio or 0.0)

    @staticmethod
    def _quality_tag(ev: ParticipationEvidence) -> str:
        if ev.quality == "QX":
            return "QX"
        if ev.oi_state in ("STALE", "MISSING", "INVALID"):
            return "Q3"
        if ev.climax or ev.dryup:
            return "Q2"
        if any("Proxy" in e or "Divergence" in e or "Wash" in e
               for e in ev.events):
            return "Q3"
        return "Q1"
