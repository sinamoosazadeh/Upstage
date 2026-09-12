"""APEX_GEN5 E07 — RTM/ICT meta-layer engine (v4.0.0).

Blueprint: APEX_GEN5.md L8293–9085 (chapter order mirrored: §3 formulas →
§4 algorithms → §5 objects/state/events/schema → §6 params → §7 notes →
§8 validation hooks). E07 builds NO new indicator from raw price (NG1); it
assembles an auditable Bundle from base-engine evidence under the
APEX-InterMotor-Contract v2.1, arranged into a time-and-concept sequence
(Conceptual Chain).

Versioned dependencies (chapter header): E01 Structure, E02 Liquidity,
E03 Volume, E04 Volatility, E05 FVG, E06 OrderBlock, E12 Temporal_Context
— all v4.x. Output is an ``RTMBundle`` (confidence, sequence_integrity,
resolution_class QX, components_present/missing, fate lifecycle), NEVER a
capital-allocation signal (NG2). Quality labels Q0 Invalid … Q5 Diamond.

E12 degraded branch (CP-4, per §9.5-9 + CP-5 integration note): E12
Temporal_Context is consumed only when present in ``context``. When E12
evidence is ABSENT the engine degrades deterministically to its own
UTC-fixed ``UTCActivityWindowConfig v2`` (KZ.v2.1.1, aligned with the
canonical E12 §3.5 windows) and records ``temporal_source =
"E07_UTC_FIXED_DEGRADED"`` — it NEVER fabricates E12 evidence. The
E07↔E12 integration test (degraded branch resolving when E12 is present)
lands at CP-5, when E12 exists.
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

ENGINE = "E07_RTM_ICT"
CONTRACT_VERSION = "4.0.0"
ANALYST_VERSION = "4.0.0+" + "0" * 40
EPS = float(eps_for_engine("E07"))          # 1e-8 (§2.2 E07 row)

FRAMEWORKS = (
    "RTM.PO3.v1",
    "RTM.MSS.v1",
    "RTM.CHAIN.v1",
    "RTM.OTE.v1",
    "RTM.JUDAS.v1",
    "RTM.UTC_ACTIVITY_WINDOW.v1",
)
FATES = ("proposed", "active", "completed", "invalidated", "expired",
         "superseded")
QCLASSES = ("Q0", "Q1", "Q2", "Q3", "Q4", "Q5")

EVENT_CATALOG = {
    "EV_RTM_001": "Po3_Accumulation_Detected",
    "EV_RTM_002": "Po3_Manipulation_Detected",
    "EV_RTM_003": "Po3_Distribution_Detected",
    "EV_RTM_004": "Bundle_Complete",
    "EV_RTM_005": "Bundle_Incomplete",
    "EV_RTM_006": "MSS_Confirmed_With_Liquidity",
    "EV_RTM_007": "Killzone_Aligned",
    "EV_RTM_008": "OTE_Zone_Active",
    "EV_RTM_009": "JudasSwing_Suspected",
    "EV_RTM_010": "Bundle_Invalidated",
    "EV_RTM_011": "LiquidityGrabChain_Detected",
}

# UTC activity window config (KZ.v2.1.1 — §3.6; aligned with E12 §3.5).
UTC_W0 = (0.0, 7.0)
UTC_W1 = (7.0, 12.5)
UTC_W1_CORE = (7.0, 11.0)
UTC_W2 = (12.5, 21.0)
UTC_W2_CORE = (12.5, 16.0)
UTC_W3 = (21.0, 24.0)
UTC_OVERLAP = (12.5, 16.0)
KZ_CONFIG_VERSION = "KZ.v2.1.1"


# ---------------------------------------------------------------------------
# §6 Parameters (frozen in-package defaults, ISSUE-CP2-006 pattern)
# ---------------------------------------------------------------------------
E07_DEFAULTS: Dict[str, Any] = {
    "po3_bars": 8,              # N>=8 range (§6; default 8)
    "atr_ratio_th": 0.75,       # ATR_short/ATR_long < 0.75
    "po3_vol_th": 0.9,          # VolRatio <= 0.9 volume compression
    "mss_prox_th": 0.5,         # |p_sweep - p_choch| <= 0.5*ATR20
    "th_int": 0.7,              # integrity threshold (emit gate)
    "th_weight": 0.6,           # weight coverage threshold (emit gate)
    "th_mss": 0.65,             # minimum MSS chain integrity
    "ote_lo": 0.62,             # OTE zone lower Fibonacci ratio
    "ote_hi": 0.79,             # OTE zone upper ratio (sqrt(phi))
    "ote_star": 0.705,          # OTE optimal retracement
    "judas_max_pen": 0.25,      # Judas move depth (×ATR)
    "judas_rev_min": 1.0,       # reversal >= 100% of J_len
    "judas_max_bars": 3,        # reversal within <=3 candles
    "econ_pause_min": 30,       # high-impact-news pause (minutes)
    "conf_alpha": 0.4,
    "conf_beta": 0.25,
    "conf_gamma": 0.2,
    "conf_delta": 0.15,
    "bundle_expiry_bars": 20,   # fate expiry (§5.2)
    "range_hl_mult": 2.5,       # Range_HL/ATR_long < 2.5 (§3.2)
    "gap_reset_mult": 3.0,      # Gap > 3*ATR resets range (§3.2)
    "conflict_time_overlap_ms": 20 * 15 * 60 * 1000,  # 20×15m (§4)
    "conflict_win_margin": 0.1,  # supersede only if conf > other + 0.1
}


def get_params(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = dict(E07_DEFAULTS)
    for key, value in (overrides or {}).items():
        if key not in E07_DEFAULTS:
            raise ValueError(f"UNKNOWN_E07_PARAM_QX:{key}")
        params[key] = value
    weights = (params["conf_alpha"], params["conf_beta"],
               params["conf_gamma"], params["conf_delta"])
    if abs(sum(weights) - 1.0) > 1e-9:
        raise ValueError("E07_CONF_WEIGHTS_SUM_QX")
    return params


# ---------------------------------------------------------------------------
# §4 dataclasses
# ---------------------------------------------------------------------------
@dataclass
class OrderMapEntry:
    cid: str
    t_confirm_ms: int
    seq_idx: int
    actual_idx: int
    p_confirm: float
    order_ok: bool = False


@dataclass
class ComponentDef:
    cid: str
    weight: float
    expected_seq: int
    required: bool = True


@dataclass
class RTMBundle:
    bid: str
    framework_id: str
    components_present: List[str]
    components_missing: List[str]
    integrity: float
    weight_coverage: float
    confidence: float
    direction: str
    resolution_class: str
    explanation: str
    as_of_ms: int
    snapshot_id: str
    version: str = "E07.v4.0.0"
    fate: str = "active"
    utc_window_aligned: bool = False
    mtf_align_score: float = 0.0
    conflict_with: Optional[str] = None
    order_map: Optional[Dict[str, OrderMapEntry]] = None
    temporal_source: str = "E12"
    components_present_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Schema-shaped dict (operational fields only; snapshot_id is the
        deterministic identity, never recomputed from a mutated object)."""
        return {
            "bid": self.bid,
            "framework_id": self.framework_id,
            "components_present": self.components_present,
            "components_missing": self.components_missing,
            "integrity": self.integrity,
            "weight_coverage": self.weight_coverage,
            "confidence": self.confidence,
            "direction": self.direction,
            "resolution_class": self.resolution_class,
            "explanation": self.explanation,
            "as_of_ms": self.as_of_ms,
            "snapshot_id": self.snapshot_id,
            "version": self.version,
            "fate": self.fate,
            "utc_window_aligned": self.utc_window_aligned,
            "mtf_align_score": self.mtf_align_score,
            "conflict_with": self.conflict_with,
        }


# ---------------------------------------------------------------------------
# §4 core formula functions (PIT-safe; deterministic)
# ---------------------------------------------------------------------------
def make_snapshot_id(payload: dict) -> str:
    """§4 make_snapshot_id — canonical E07_RTM_ICT/4.0.0 envelope."""
    return canonical_snapshot_id("E07_RTM_ICT", "4.0.0", payload)


def sequence_integrity_v4(
        expected: Sequence[ComponentDef],
        present: Sequence[str],
        order_map: Dict[str, OrderMapEntry],
) -> Tuple[float, float, List[str]]:
    """§3.1 sequence integrity with 0.5 out-of-order penalty.

    Integrity = sum(w_i * s_i) / (sum(w_i) + eps), s_i ∈ {1, 0.5, 0}.
    Returns (integrity, weight_coverage, missing).
    """
    total_w = sum(c.weight for c in expected) + EPS
    num = 0.0
    present_w = 0.0
    missing: List[str] = []
    present_set = set(present)
    for comp in expected:
        cid = comp.cid
        if cid not in present_set:
            missing.append(cid)
            continue
        present_w += comp.weight
        entry = order_map.get(cid)
        if entry is None:
            num += comp.weight * 0.5
        elif entry.order_ok:
            num += comp.weight * 1.0
        else:
            num += comp.weight * 0.5
    integrity = num / total_w
    weight_coverage = present_w / total_w
    return integrity, weight_coverage, missing


def evaluate_order_ok(
        expected: Sequence[ComponentDef],
        present: Sequence[str],
        order_map: Dict[str, OrderMapEntry],
) -> None:
    """§4 — mark each present component order_ok by PIT t_confirm order."""
    exp_seq = {c.cid: c.expected_seq for c in expected}
    present_sorted = sorted(
        [cid for cid in present if cid in order_map],
        key=lambda x: order_map[x].t_confirm_ms)
    last_seq = -1
    for cid in present_sorted:
        curr_seq = exp_seq.get(cid, 999)
        entry = order_map[cid]
        if curr_seq >= last_seq:
            entry.order_ok = True
            last_seq = curr_seq
        else:
            entry.order_ok = False


def _wilder_rma(period: int, trs: List[float]) -> float:
    if not trs:
        return 0.0
    alpha = 1.0 / period
    ema = trs[0]
    for v in trs[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return ema


def atr_ratio_detect(
        bars: Sequence[Dict[str, Any]],
        atr_short_period: int = 10,
        atr_long_period: int = 100,
        params: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, float, int]:
    """§3.2 range detection — ATR_ratio < th ∧ N>=8 ∧ HL compressed ∧ vol
    compression. Returns (is_range, atr_ratio, n_bars)."""
    p = params or E07_DEFAULTS
    if len(bars) < max(atr_long_period, 8) + 1:
        return False, 999.0, len(bars)

    def atr(period: int, data: Sequence[Dict[str, Any]]) -> float:
        trs: List[float] = []
        for i in range(1, len(data)):
            h, l, pc = data[i]["h"], data[i]["l"], data[i - 1]["c"]
            if h < l:
                continue
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        if not trs:
            return 0.0
        return _wilder_rma(period, trs)

    atr_s = atr(atr_short_period, bars)
    atr_l = atr(atr_long_period, bars)
    if atr_l < EPS:
        return False, 999.0, len(bars)
    ratio = atr_s / atr_l
    n_bars = len(bars)
    highs = [b["h"] for b in bars[-8:]]
    lows = [b["l"] for b in bars[-8:] if b["h"] >= b["l"]]
    if not lows:
        return False, ratio, n_bars
    hl_range = max(highs) - min(lows)
    range_compressed = hl_range < p["range_hl_mult"] * atr_l
    recent_vol = sum(b.get("v", 0) for b in bars[-8:]) / 8.0
    if len(bars) > 100:
        lookback_vol = sum(b.get("v", 0) for b in bars[-100:-8]) / 92.0
    else:
        lookback_vol = recent_vol
    vol_ratio = recent_vol / max(lookback_vol, EPS)
    is_range = (n_bars >= 8) and (ratio < p["atr_ratio_th"]) and \
        range_compressed and (vol_ratio <= p["po3_vol_th"] or recent_vol == 0)
    return is_range, ratio, n_bars


def mss_proximity_check(p_sweep: float, p_choch: float, atr20: float,
                        thresh: float = 0.5) -> bool:
    """§3.3 MSS proximity |p_sweep - p_choch| <= 0.5*ATR20."""
    if atr20 < EPS:
        return False
    return abs(p_sweep - p_choch) <= thresh * atr20


def ote_zone_calc(a: float, b: float, r_lo: float = 0.62,
                  r_hi: float = 0.79,
                  r_star: float = 0.705) -> Optional[Dict[str, float]]:
    """§3.4 OTE zone [A+0.62(B-A), A+0.79(B-A)], star A+0.705(B-A).
    A == B → invalid (None)."""
    if math.isnan(a) or math.isnan(b) or abs(a - b) < EPS:
        return None
    lo = a + r_lo * (b - a)
    hi = a + r_hi * (b - a)
    star = a + r_star * (b - a)
    return {"lo": min(lo, hi), "hi": max(lo, hi), "star": star,
            "r_lo": r_lo, "r_hi": r_hi}


def judas_swing_detect(bars: Sequence[Dict[str, Any]], expected_dir: str,
                       atr20: float,
                       max_pen: float = 0.25,
                       rev_min: float = 1.0,
                       max_bars: int = 3) -> Optional[Dict[str, Any]]:
    """§3.5 Judas swing — J_len <= max_pen*ATR then reversal >= rev_min*J_len
    within <= max_bars candles with directional flip."""
    if len(bars) < 5 or atr20 < EPS:
        return None
    recent = bars[-10:]
    start_price = recent[0]["c"]
    judas_dir = "DOWN" if expected_dir == "UP" else "UP"
    judas_end_idx: Optional[int] = None
    max_judas_move = 0.0
    for i, b in enumerate(recent):
        move = b["c"] - start_price
        if judas_dir == "DOWN" and move < 0:
            if abs(move) > max_judas_move:
                max_judas_move = abs(move)
                judas_end_idx = i
        if judas_dir == "UP" and move > 0:
            if move > max_judas_move:
                max_judas_move = move
                judas_end_idx = i
    if judas_end_idx is None:
        return None
    j_len = max_judas_move
    if j_len > max_pen * atr20:
        return None
    if judas_end_idx + max_bars >= len(recent):
        return None
    p_judas_end = recent[judas_end_idx]["c"]
    for k in range(judas_end_idx + 1,
                   min(judas_end_idx + max_bars + 1, len(recent))):
        rev_len = recent[k]["c"] - p_judas_end
        if expected_dir == "UP" and rev_len >= j_len * rev_min:
            return {"judas_len": j_len, "rev_len": rev_len,
                    "bars_to_rev": k - judas_end_idx,
                    "p_judas_end": p_judas_end, "confirmed": True}
        if expected_dir == "DOWN" and rev_len <= -j_len * rev_min:
            return {"judas_len": j_len, "rev_len": abs(rev_len),
                    "bars_to_rev": k - judas_end_idx,
                    "p_judas_end": p_judas_end, "confirmed": True}
    return None


def _hour_of(ts_ms: int) -> float:
    dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    return dt.hour + dt.minute / 60.0 + dt.second / 3600.0


def window_description(hour: float) -> str:
    """Canonical UTC window description string (§3.6 + §8.1 fixtures)."""
    if UTC_OVERLAP[0] <= hour < UTC_OVERLAP[1]:
        return ("12:30-16:00 UTC (canonical, E12 §3.5; UTC-fixed, DST "
                "affects local labels only)")
    if UTC_W1_CORE[0] <= hour < UTC_W1_CORE[1]:
        return "UTC_W1_CORE 07:00-11:00 UTC (canonical, E12 §3.5)"
    return "UTC activity window (canonical, E12 §3.5)"


def utc_activity_window_check(
        ts_ms: int,
        econ_events: Optional[List[Dict[str, Any]]] = None,
        kz_config_version: str = KZ_CONFIG_VERSION,
        econ_pause_min: int = 30,
) -> Dict[str, Any]:
    """§3.6/§4 — evaluate fixed UTC activity windows. The market is
    continuously tradable, so ``in_kz`` is True; the window/overlap flags
    record WHICH canonical window the timestamp falls in (E12 §3.5)."""
    hour = _hour_of(ts_ms)
    utc_w0_in = UTC_W0[0] <= hour < UTC_W0[1]
    utc_w1_in = UTC_W1[0] <= hour < UTC_W1[1]
    utc_w2_in = UTC_W2[0] <= hour < UTC_W2[1]
    overlap_in = UTC_OVERLAP[0] <= hour < UTC_OVERLAP[1]
    which: List[str] = []
    if utc_w0_in:
        which.append("UTC_W0")
    elif utc_w1_in:
        which.append("UTC_W1")
    elif utc_w2_in:
        which.append("UTC_W2")
    else:
        which.append("UTC_W3")
    econ_conflict = False
    for ev in (econ_events or []):
        if abs(ev["time_ms"] - ts_ms) <= econ_pause_min * 60 * 1000 and \
                ev.get("impact") == "HIGH":
            econ_conflict = True
            break
    return {
        "in_kz": True,
        "which": which,
        "utc_activity_window": which[0],
        "is_overlap": overlap_in,
        "econ_conflict": econ_conflict,
        "rollover_active": False,
        "config_version": kz_config_version,
        "window": window_description(hour),
    }


def bundle_confidence(integrity: float, avg_q: float, mtf_align: float,
                      kz_align: float, alpha: float = 0.4, beta: float = 0.25,
                      gamma: float = 0.2, delta: float = 0.15) -> float:
    """§3.7 confidence = min(1, αI + βQ̄ + γMTF + δKZ)."""
    return min(1.0, alpha * integrity + beta * avg_q + gamma * mtf_align +
               delta * kz_align)


def resolution_class_of(integrity: float, confidence: float,
                        in_kz: bool, mtf_align: float) -> str:
    """§4 pseudocode qclass derivation (executable reference; §3.7 is the
    conceptual summary). Q5 additionally requires killzone overlap + MTF."""
    if integrity < 0.5:
        return "Q0"
    if integrity < 0.7:
        return "Q1"
    if integrity < 0.8:
        return "Q2"
    if integrity < 0.9:
        return "Q3"
    if integrity <= 1.0 and confidence < 0.85:
        return "Q3"
    if integrity >= 0.9 and 0.85 <= confidence < 0.95:
        return "Q4"
    return "Q5" if (in_kz and mtf_align >= 0.9) else "Q4"


def resolve_conflicting_bundles(
        bundles: Sequence[RTMBundle],
        time_overlap_ms: int = 20 * 15 * 60 * 1000,
        win_margin: float = 0.1,
) -> List[RTMBundle]:
    """§4/§5.2 — conflicting opposite-direction bundles with overlapping
    time: older/weaker invalidated, newer/stronger supersedes."""
    bundles_sorted = sorted(bundles, key=lambda b: b.as_of_ms)
    active: List[RTMBundle] = []
    for b in bundles_sorted:
        conflict = False
        for a in active:
            if a.fate != "active":
                continue
            time_overlap = abs(b.as_of_ms - a.as_of_ms) < time_overlap_ms
            opposite = b.direction != a.direction
            if time_overlap and opposite:
                if b.confidence > a.confidence + win_margin:
                    a.fate = "superseded"
                    a.conflict_with = b.bid
                    active.append(b)
                else:
                    b.fate = "invalidated"
                    b.conflict_with = a.bid
                conflict = True
                break
        if not conflict and b.fate == "active":
            active.append(b)
    return active


def build_bundle_pipeline(
        expected: Sequence[ComponentDef],
        present: Sequence[str],
        order_map: Dict[str, OrderMapEntry],
        avg_q: float,
        mtf_align: float,
        kz_info: Dict[str, Any],
        framework_id: str,
        direction: str,
        as_of_ms: int,
        params: Dict[str, Any],
        temporal_source: str = "E12",
        components_present_ids: Optional[List[str]] = None,
) -> Optional[RTMBundle]:
    """§4 build_bundle_pipeline — integrity gate → confidence → qclass →
    snapshot_id → RTMBundle (or None when the emit gates fail)."""
    evaluate_order_ok(expected, present, order_map)
    integrity, weight_cov, missing = sequence_integrity_v4(
        expected, present, order_map)
    th_int = params.get("th_int", 0.7)
    th_w = params.get("th_weight", 0.6)
    if integrity < th_int or weight_cov < th_w:
        return None
    kz_align_score = 1.0 if kz_info.get("in_kz") else 0.2
    if kz_info.get("econ_conflict"):
        kz_align_score *= 0.7
    conf = bundle_confidence(
        integrity, avg_q, mtf_align, kz_align_score,
        params.get("conf_alpha", 0.4), params.get("conf_beta", 0.25),
        params.get("conf_gamma", 0.2), params.get("conf_delta", 0.15))
    qclass = resolution_class_of(integrity, conf, kz_info.get("in_kz", False),
                                 mtf_align)
    snap_payload = {"framework_id": framework_id, "present": list(present),
                    "integrity": integrity, "as_of_ms": as_of_ms}
    snap_id = make_snapshot_id(snap_payload)
    bid = "bnd_" + uuid_v7().replace("-", "")[:12]
    return RTMBundle(
        bid=bid, framework_id=framework_id,
        components_present=list(present), components_missing=missing,
        integrity=integrity, weight_coverage=weight_cov, confidence=conf,
        direction=direction, resolution_class=qclass,
        explanation=",".join(present), as_of_ms=as_of_ms,
        snapshot_id=snap_id,
        utc_window_aligned=bool(kz_info.get("in_kz", False)),
        mtf_align_score=mtf_align,
        temporal_source=temporal_source,
        components_present_ids=list(components_present_ids or []),
    )


def wilson_ci(p_hat: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    """§8.5 Wilson interval."""
    if n <= 0:
        return 0.0, 1.0
    denom = 1 + z * z / n
    centre = (p_hat + z * z / (2 * n)) / denom
    half = z * math.sqrt((p_hat * (1 - p_hat) / n + z * z / (4 * n * n))) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


# --------------------------------------------------------------------------
# §4 streaming engine (buffer + idempotency)
# --------------------------------------------------------------------------
class RTMEngineStreaming:
    """§4 streaming container: event buffer + per-window idempotency."""

    def __init__(self, params: Dict[str, Any]) -> None:
        self.params = params
        self.buffer: List[Dict[str, Any]] = []
        self.last_bundles: Dict[str, RTMBundle] = {}

    def on_event(self, event: Dict[str, Any]) -> None:
        self.buffer.append(event)

    def process_at(self, as_of_ms: int, bars: List[Dict[str, Any]],
                   econ: List[Dict[str, Any]]) -> List[RTMBundle]:
        idem_key = f"{as_of_ms // (15 * 60 * 1000)}"
        if idem_key in self.last_bundles:
            return []
        return []


# --------------------------------------------------------------------------
# Evidence assembly (APEX-InterMotor-Contract v2.1 — cross-engine shapes)
# --------------------------------------------------------------------------
def _idx_of(event: Dict[str, Any]) -> int:
    return int(event.get("valid_at_idx", event.get("idx", 0)))


def _ts_ms_of(event: Dict[str, Any]) -> int:
    return int(event.get("t_confirm_ms", event.get("ts", event.get(
        "as_of_ms", 0))))


def assemble_po3(
        bars: Sequence[Dict[str, Any]],
        structure_events: Sequence[Dict[str, Any]],
        sweep_events: Sequence[Dict[str, Any]],
        volume_events: Sequence[Dict[str, Any]],
        fvg_events: Sequence[Dict[str, Any]],
        atr_series: Optional[Sequence[float]],
        kz_info: Dict[str, Any],
        mtf_align: float,
        as_of_ms: int,
        params: Dict[str, Any],
        temporal_source: str,
) -> Optional[RTMBundle]:
    """Assemble the RTM.PO3.v1 bundle (§5.3 / §9).

    Components (weighted, §9): sweep 1.5, CHoCH 1.0, BOS 1.0, FVG 0.8,
    volume 0.7 (total 5.0). Accumulation (range detection) is the
    EV_RTM_001 precondition, not a weighted chain component."""
    is_range, _ratio, _n = atr_ratio_detect(bars, params=params)
    if not is_range:
        return None
    present: List[str] = []
    present_ids: List[str] = []
    order_map: Dict[str, OrderMapEntry] = {}

    def add(cid: str, seq: int, t_ms: int, p_conf: float, eid: str) -> None:
        present.append(cid)
        present_ids.append(eid)
        order_map[cid] = OrderMapEntry(cid, t_ms, seq, seq, p_conf,
                                       order_ok=False)

    if sweep_events:
        s = sweep_events[0]
        add("sweep", 0, _ts_ms_of(s), float(s.get("p_confirm", 0.8)), "sweep")
    for e in structure_events:
        if e.get("kind") == "CHoCH" and "CHoCH" not in present:
            add("CHoCH", 1, _ts_ms_of(e), float(e.get("p_confirm", 0.8)),
                "choch")
        elif e.get("kind") == "BOS" and "BOS" not in present:
            add("BOS", 2, _ts_ms_of(e), float(e.get("p_confirm", 0.8)),
                "bos")
    if fvg_events and fvg_events[0].get("present"):
        add("FVG", 3, _ts_ms_of(fvg_events[0]), 0.8, "fvg")
    if volume_events:
        add("volume", 4, _ts_ms_of(volume_events[0]),
            float(volume_events[0].get("p_confirm", 0.8)), "vol")
    expected = [
        ComponentDef("sweep", 1.5, 0),
        ComponentDef("CHoCH", 1.0, 1),
        ComponentDef("BOS", 1.0, 2),
        ComponentDef("FVG", 0.8, 3),
        ComponentDef("volume", 0.7, 4),
    ]
    direction = "UP" if mtf_align >= 0 else "DOWN"
    return build_bundle_pipeline(expected, present, order_map,
                                 avg_q=0.9, mtf_align=mtf_align,
                                 kz_info=kz_info, framework_id="RTM.PO3.v1",
                                 direction=direction, as_of_ms=as_of_ms,
                                 params=params,
                                 temporal_source=temporal_source,
                                 components_present_ids=present_ids)


def assemble_liquidity_grab_chain(
        sweep_events: Sequence[Dict[str, Any]],
        structure_events: Sequence[Dict[str, Any]],
        fvg_events: Sequence[Dict[str, Any]],
        volume_events: Sequence[Dict[str, Any]],
        kz_info: Dict[str, Any],
        mtf_align: float,
        as_of_ms: int,
        params: Dict[str, Any],
        temporal_source: str,
) -> Optional[RTMBundle]:
    """§5.3.1 Liquidity Grab Chain: sweep → CHoCH/BOS → FVG → retest →
    volume confirmation (RTM.CHAIN.v1). Retest = price returns into the FVG
    zone (recorded via a retest event or FVG touch)."""
    present: List[str] = []
    present_ids: List[str] = []
    order_map: Dict[str, OrderMapEntry] = {}

    def add(cid: str, seq: int, t_ms: int, p_conf: float, eid: str) -> None:
        present.append(cid)
        present_ids.append(eid)
        order_map[cid] = OrderMapEntry(cid, t_ms, seq, seq, p_conf,
                                       order_ok=False)

    if sweep_events:
        s = sweep_events[0]
        add("sweep", 0, _ts_ms_of(s), float(s.get("p_confirm", 0.8)), "sweep")
    for e in structure_events:
        if e.get("kind") in ("BOS", "CHoCH") and "structure" not in present:
            add("structure", 1, _ts_ms_of(e), float(e.get("p_confirm", 0.8)),
                e.get("kind", "structure"))
    fvg = next((f for f in fvg_events if f.get("present")), None)
    if fvg is not None:
        add("FVG", 2, _ts_ms_of(fvg), 0.8, "fvg")
        # retest: price returned into the zone after formation
        if fvg.get("touch_count", 0) >= 1 or fvg.get("retested", False):
            add("retest", 3, _ts_ms_of(fvg) + 1, 0.8, "retest")
    if volume_events:
        add("volume", 4, _ts_ms_of(volume_events[0]),
            float(volume_events[0].get("p_confirm", 0.8)), "vol")
    expected = [
        ComponentDef("sweep", 1.5, 0),
        ComponentDef("structure", 1.0, 1),
        ComponentDef("FVG", 0.8, 2),
        ComponentDef("retest", 0.8, 3),
        ComponentDef("volume", 0.7, 4),
    ]
    direction = "UP" if mtf_align >= 0 else "DOWN"
    return build_bundle_pipeline(expected, present, order_map,
                                 avg_q=0.8, mtf_align=mtf_align,
                                 kz_info=kz_info, framework_id="RTM.CHAIN.v1",
                                 direction=direction, as_of_ms=as_of_ms,
                                 params=params,
                                 temporal_source=temporal_source,
                                 components_present_ids=present_ids)


def assemble_mss(
        sweep_events: Sequence[Dict[str, Any]],
        structure_events: Sequence[Dict[str, Any]],
        atr20: float,
        kz_info: Dict[str, Any],
        mtf_align: float,
        as_of_ms: int,
        params: Dict[str, Any],
        temporal_source: str,
) -> Optional[RTMBundle]:
    """§3.3 MSS chain: CHoCH + sweep within 0.5·ATR20 proximity."""
    sweep = sweep_events[0] if sweep_events else None
    choch = next((e for e in structure_events if e.get("kind") == "CHoCH"),
                 None)
    if sweep is None or choch is None:
        return None
    p_sweep = float(sweep.get("price", sweep.get("p_confirm", 0.0)))
    p_choch = float(choch.get("price", choch.get("p_confirm", 0.0)))
    if not mss_proximity_check(p_sweep, p_choch, atr20, params["mss_prox_th"]):
        return None
    expected = [ComponentDef("sweep", 1.0, 0), ComponentDef("CHoCH", 1.0, 1)]
    order_map = {
        "sweep": OrderMapEntry("sweep", _ts_ms_of(sweep), 0, 0, 0.8),
        "CHoCH": OrderMapEntry("CHoCH", _ts_ms_of(choch), 1, 1, 0.8),
    }
    present = ["sweep", "CHoCH"]
    return build_bundle_pipeline(expected, present, order_map,
                                 avg_q=0.8, mtf_align=mtf_align,
                                 kz_info=kz_info, framework_id="RTM.MSS.v1",
                                 direction="UP", as_of_ms=as_of_ms,
                                 params=params,
                                 temporal_source=temporal_source,
                                 components_present_ids=["sweep", "choch"])


def run_engine(
        bars: Sequence[Dict[str, Any]],
        params: Optional[Dict[str, Any]] = None,
        symbol: str = "",
        timeframe: str = "1h",
        structure_events: Optional[Sequence[Dict[str, Any]]] = None,
        sweep_events: Optional[Sequence[Dict[str, Any]]] = None,
        volume_events: Optional[Sequence[Dict[str, Any]]] = None,
        fvg_events: Optional[Sequence[Dict[str, Any]]] = None,
        ob_events: Optional[Sequence[Dict[str, Any]]] = None,
        atr_series: Optional[Sequence[float]] = None,
        temporal_windows: Optional[Sequence[Dict[str, Any]]] = None,
        econ_events: Optional[Sequence[Dict[str, Any]]] = None,
        mtf_align: float = 0.0,
        as_of_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """Batch driver: assemble the supported framework bundles from
    evidence. E12 temporal windows are optional — when absent the engine
    degrades to its UTC-fixed config (temporal_source DEGRADED)."""
    p = get_params(params)
    struct = list(structure_events or [])
    sweep = list(sweep_events or [])
    vol = list(volume_events or [])
    fvg = list(fvg_events or [])
    if as_of_ms is None:
        as_of_ms = _ts_ms_of(bars[-1]) if bars else 0
    # E12 availability → degraded branch (CP-4; integration test at CP-5)
    temporal_source = "E12"
    if temporal_windows:
        kz_info = {
            "in_kz": bool(temporal_windows[0].get("in_kz", True)),
            "econ_conflict": bool(temporal_windows[0].get("econ_conflict",
                                                          False)),
            "config_version": temporal_windows[0].get(
                "config_version", KZ_CONFIG_VERSION),
            "window": temporal_windows[0].get("window", ""),
        }
    else:
        kz_info = utc_activity_window_check(
            as_of_ms, econ_events=list(econ_events or []),
            econ_pause_min=p["econ_pause_min"])
        temporal_source = "E07_UTC_FIXED_DEGRADED"

    bundles: List[RTMBundle] = []
    po3 = assemble_po3(bars, struct, sweep, vol, fvg, atr_series, kz_info,
                       mtf_align, as_of_ms, p, temporal_source)
    if po3 is not None:
        bundles.append(po3)
    chain = assemble_liquidity_grab_chain(sweep, struct, fvg, vol, kz_info,
                                          mtf_align, as_of_ms, p,
                                          temporal_source)
    if chain is not None:
        bundles.append(chain)
    mss = assemble_mss(sweep, struct, float(atr_series[-1]) if atr_series
                       else 0.0, kz_info, mtf_align, as_of_ms, p,
                       temporal_source)
    if mss is not None:
        bundles.append(mss)
    return {
        "engine": ENGINE,
        "bundles": bundles,
        "kz_info": kz_info,
        "temporal_source": temporal_source,
        "as_of_ms": as_of_ms,
    }


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


class E07RTMEngine(EngineBase):
    """E07_RTM_ICT on the frozen EngineBase contract (v4.0.0).

    compute(symbol, timeframe, as_of, context): window via context['window']
    or a sync WindowProvider. Consumed context keys: window, provider, bars,
    e07_params, structure_events, sweep_events, volume_events, fvg_events,
    ob_events, atr_series, temporal_windows (E12 — optional), econ_events,
    mtf_align, trend_htf. Produces RTMBundle evidence on topics
    evidence.E07.* . When temporal_windows is absent the engine degrades to
    its UTC-fixed config and records temporal_source=E07_UTC_FIXED_DEGRADED.
    """

    engine_id = "E07"
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
        params = get_params(context.get("e07_params"))
        result = run_engine(
            bars, params, symbol=symbol, timeframe=timeframe,
            structure_events=context.get("structure_events"),
            sweep_events=context.get("sweep_events"),
            volume_events=context.get("volume_events"),
            fvg_events=context.get("fvg_events"),
            ob_events=context.get("ob_events"),
            atr_series=context.get("atr_series"),
            temporal_windows=context.get("temporal_windows"),
            econ_events=context.get("econ_events"),
            mtf_align=float(context.get("mtf_align", 0.0)),
        )
        quality = self._window_quality(window_obs)
        out: List[EvidenceEvent] = []
        for b in result["bundles"]:
            out.append(self._to_evidence(b, symbol, timeframe, quality))
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

    def _to_evidence(self, b: RTMBundle, symbol: str, timeframe: str,
                     quality: float) -> EvidenceEvent:
        as_of_iso = datetime.fromtimestamp(
            b.as_of_ms / 1000.0, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.") + f"{b.as_of_ms % 1000:03d}Z"
        direction = 1 if b.direction == "UP" else -1
        return EvidenceEvent(
            evidence_id=uuid_v7(),
            engine_id=self.engine_id,
            analyst_version=self.analyst_version,
            symbol=symbol, timeframe=timeframe,
            snapshot_id=b.snapshot_id,
            event_time=as_of_iso,
            availability_time=as_of_iso,
            observation_window={"bundles": 1, "tf": timeframe},
            feature_snapshot_id=b.snapshot_id,
            feature_dependencies=("structure_events", "sweep_events",
                                  "volume_events", "fvg_events",
                                  "atr_series", "temporal_windows"),
            condition_state=f"EV_RTM_BUNDLE_{b.framework_id.replace('.', '_')}",
            direction=direction,
            strength=float(min(max(b.integrity, 0.0), 1.0)),
            confidence=float(b.confidence),
            quality=float(quality),
            validity="VALID" if b.resolution_class != "Q0" else "DEGRADED",
            fate_state=LifecycleState.ACTIVE,
            age=None,
            decay=None,
            explanation=(f"E07 {b.framework_id} {b.direction} "
                         f"I={b.integrity:.4f} conf={b.confidence:.4f} "
                         f"{b.resolution_class} "
                         f"temporal={b.temporal_source} "
                         f"present={','.join(b.components_present)}"),
            parameter_version="E07-RTM-V4.0.0/DEFAULTS-v1",
            lineage=tuple(b.components_present_ids),
            resolution_class=b.resolution_class,
        )
