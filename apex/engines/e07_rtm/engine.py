"""APEX_GEN5 — E07 RTM/ICT: Combined Reading-the-Market Methodology (v4.0.0).

Blueprint: APEX_GEN5.md L8293–9085 (chapter order mirrored below:
§2 vocabulary → §3 formulas → §4 flows → §5 objects/state/events/schema →
§6 parameters → §7 encyclopedic → §8 validation).

E07 is the meta-layer: it builds NO new indicator from raw price. It consumes
versioned evidence from E01/E02/E03/E04/E05/E06 (and, from CP-5 onward,
E12_Temporal_Context) under the APEX-InterMotor-Contract and arranges it into
auditable Conceptual Chains (``RTMBundle``). It never emits a capital
allocation signal (§0; Non-Goals NG2/NG5).

Wave-In discipline (G6/P6): nothing here is a stub. Where the chapter leaves a
gap the code fails closed with a deterministic reason code:
  * ``E12_UNAVAILABLE_DEGRADED_QX`` — the canonical UTC-window authority is
    E12 §3.5. E12 does not exist until CP-5, so at CP-4 build time E07 runs its
    documented DEGRADED branch on the chapter's own *non-authoritative*
    duplicate registry (§6 ``overlap_real_def``: "non-authoritative duplicate;
    E12 registry governs") and marks every bundle degraded. The local windows
    are NEVER labelled E12-canonical (P19 degradation path; ADR-P2-017).
  * ``VOL_UNAVAILABLE_QX`` — §3.2: ``V = 0`` ⇒ VolRatio unavailable ⇒ the range
    decision is NOT authorized from a synthetic neutral value.
  * ``NON_UTC_TIMESTAMP_QX`` — §3.8: non-UTC timestamp input.

Logged contradictions resolved here (PHASE2_DECISION_LOG §B/CP-4):
  ISSUE-CP4-001 (§2 vs §3.2 range condition)   → fail-closed intersection.
  ISSUE-CP4-002 (§4 ``or recent_vol == 0``)    → §3.2 edge case wins.
  ISSUE-CP4-003 (gap reset 3·ATR vs 5·ATR)     → tighter §3.2 threshold.
  ISSUE-CP4-004 (``uuid.uuid4`` for ``bid``)   → in-tree UUIDv7 only.
  ISSUE-CP4-005 (E12 absent)                   → degraded branch, CP-5 re-test.
  ISSUE-CP4-006 (§3.7 bands vs §4 cascade)     → §4 cascade + §3.7 gate caps.
  ISSUE-CP4-007 (retest chain weight)          → equals the FVG term.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
from collections import deque
from dataclasses import dataclass, field, replace
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
from apex.quality.numerical import ATR_FLOOR, eps_for_engine

# ---------------------------------------------------------------------------
# Chapter identity (§0 header)
# ---------------------------------------------------------------------------

ENGINE = "E07_RTM_ICT"
CONTRACT_VERSION = "4.0.0"
INTER_MOTOR_CONTRACT = "APEX-InterMotor-Contract v2.1"
ANALYST_VERSION = "4.0.0+" + "0" * 40
EPS = float(eps_for_engine("E07"))            # 1e-8 — frozen §2.2 Tier-2 row
BUNDLE_VERSION = "E07.v4.0.0"                 # §5.1 ``version`` const
KZ_CONFIG_VERSION = "KZ.v2.1.1"               # §3.6 / §6 versioned registry
E12_CONTRACT = "E12_Temporal_Context.Contract v4.0.0"
E12_UNAVAILABLE_REASON = "E12_UNAVAILABLE_DEGRADED_QX"
VOL_UNAVAILABLE_REASON = "VOL_UNAVAILABLE_QX"
NON_UTC_REASON = "NON_UTC_TIMESTAMP_QX"

# §5.1 JSON schema enums (verbatim).
FRAMEWORK_IDS = (
    "RTM.PO3.v1",
    "RTM.MSS.v1",
    "RTM.CHAIN.v1",
    "RTM.OTE.v1",
    "RTM.JUDAS.v1",
    "RTM.UTC_ACTIVITY_WINDOW.v1",
)
FATES = ("proposed", "active", "completed", "invalidated", "expired",
         "superseded")
TERMINAL_FATES = ("completed", "invalidated", "expired", "superseded")
Q_CLASSES = ("Q0", "Q1", "Q2", "Q3", "Q4", "Q5")
DIRECTIONS = ("UP", "DOWN")

BUNDLE_REQUIRED = (
    "bid", "framework_id", "components_present", "components_missing",
    "integrity", "confidence", "direction", "resolution_class", "as_of_ms",
    "snapshot_id", "version", "fate",
)

# §5.3 event table (EV_RTM_001..011 + §5.3.1).
EVENT_CATALOG: Dict[str, Dict[str, Any]] = {
    "EV_RTM_001": {"name": "Po3_Accumulation_Detected",
                   "trigger": "is_range True, ATR_ratio<0.75, N>=8"},
    "EV_RTM_002": {"name": "Po3_Manipulation_Detected",
                   "trigger": "Sweep event + t within Po3 window"},
    "EV_RTM_003": {"name": "Po3_Distribution_Detected",
                   "trigger": "BOS+FVG+Vol"},
    "EV_RTM_004": {"name": "Bundle_Complete",
                   "trigger": "Integrity>=th, Weight>=th"},
    "EV_RTM_005": {"name": "Bundle_Incomplete", "trigger": "Integrity<th"},
    "EV_RTM_006": {"name": "MSS_Confirmed_With_Liquidity",
                   "trigger": "CHoCH + Sweep <=0.5 ATR"},
    "EV_RTM_007": {"name": "Killzone_Aligned",
                   "trigger": "price in KZ + bundle"},
    "EV_RTM_008": {"name": "OTE_Zone_Active", "trigger": "Valid impulse + OTE"},
    "EV_RTM_009": {"name": "JudasSwing_Suspected",
                   "trigger": "Judas len <=0.25 ATR + rev >=100% in <=3 bars"},
    "EV_RTM_010": {"name": "Bundle_Invalidated", "trigger": "Fate -> invalidated"},
    "EV_RTM_011": {"name": "LiquidityGrabChain_Detected",
                   "trigger": "full hunt chain present in order (§5.3.1)"},
}

# ---------------------------------------------------------------------------
# §6 Parameters — full governed table (defaults literal from the chapter).
# Six-YAML law (ISSUE-CP2-006 pattern): engine §6 tables live as frozen
# in-package defaults; ``get_params`` rejects unknown keys.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EngineParams:
    """E07 governed parameter set (§6 table, defaults verbatim)."""

    po3_bars: int = 8                  # candles, 4–30
    atr_ratio_th: float = 0.75         # statistical, 30th percentile
    po3_vol_th: float = 0.9            # volume compression
    mss_prox_th: float = 0.5           # ×ATR20 proximity
    th_int: float = 0.7                # integrity threshold (max F1)
    th_weight: float = 0.6             # weight coverage threshold
    th_mss: float = 0.65               # minimum MSS chain integrity
    ote_lo: float = 0.62               # ICT + statistical median
    ote_hi: float = 0.79               # sqrt(phi)
    ote_star: float = 0.705            # centre
    judas_max_pen: float = 0.25        # ×ATR Judas depth
    judas_rev_min: float = 1.0         # reversal >= 100% of J_len
    judas_max_bars: int = 3            # candles to reversal
    econ_pause_min: int = 30           # high-impact news pause (±minutes)
    alpha: float = 0.4                 # confidence weights (Σ = 1)
    beta: float = 0.25
    gamma: float = 0.2
    delta: float = 0.15
    bundle_expiry_bars: int = 20       # candles (§5.2 expiry)
    # Range-detection internals (§3.2).
    atr_short_period: int = 10
    atr_long_period: int = 100
    range_hl_max_atr: float = 2.5      # §3.2 Range_HL/ATR_long < 2.5
    range_sigma_max: float = 0.6       # §2 Accumulation: sigma(C)/ATR_l < 0.6
    gap_reset_atr: float = 3.0         # ISSUE-CP4-003 (§3.2, tighter)
    gap_edge_atr: float = 5.0          # §3.8 general edge-case flag
    judas_lookback: int = 10           # §4 recent-window depth
    redundancy_corr_th: float = 0.85   # §8.6 redundancy threshold
    conflict_overlap_ms: int = 20 * 15 * 60 * 1000   # §4 conflict resolver
    conflict_conf_margin: float = 0.1  # §4 supersede margin
    idem_bucket_ms: int = 15 * 60 * 1000             # §4 idempotency bucket
    # Chain weights (ISSUE-CP4-007: ``retest`` = the FVG term).
    w_sweep: float = 1.5
    w_choch: float = 1.0
    w_bos: float = 1.0
    w_fvg: float = 0.8
    w_retest: float = 0.8
    w_vol: float = 0.7
    w_unit: float = 1.0


E07_DEFAULTS: Dict[str, Any] = {f.name: f.default for f in EngineParams.__dataclass_fields__.values()}


def get_params(overrides: Optional[Dict[str, Any]] = None) -> EngineParams:
    """Build a parameter set; unknown keys are rejected (fail-closed)."""
    overrides = dict(overrides or {})
    unknown = sorted(set(overrides) - set(E07_DEFAULTS))
    if unknown:
        raise ValueError(f"UNKNOWN_E07_PARAM_QX: {unknown}")
    return EngineParams(**{**E07_DEFAULTS, **overrides})


# ---------------------------------------------------------------------------
# §2 Vocabulary + §5.3.1 component contract → framework chain definitions.
# ---------------------------------------------------------------------------

# cid -> (weight attr, expected_seq). ``expected_seq`` is the chain order.
CHAIN_DEFS: Dict[str, Tuple[Tuple[str, str], ...]] = {
    # §9 Integrity computation: [sweep 1.5, CHoCH 1.0, BOS 1.0, FVG 0.8, vol 0.7]
    "RTM.PO3.v1": (("sweep", "w_sweep"), ("choch", "w_choch"),
                   ("bos", "w_bos"), ("fvg", "w_fvg"),
                   ("vol_confirm", "w_vol")),
    # §5.3.1 hunt sequence: sweep → CHoCH/BOS → FVG → retest → volume.
    "RTM.CHAIN.v1": (("sweep", "w_sweep"), ("choch", "w_choch"),
                     ("fvg", "w_fvg"), ("retest", "w_retest"),
                     ("vol_confirm", "w_vol")),
    # §3.3 MSS = CHoCH ∧ Sweep ∧ proximity ∧ Integrity >= θ_mss.
    "RTM.MSS.v1": (("sweep", "w_unit"), ("choch", "w_unit")),
    # §3.4 OTE chain: impulse → OTE zone → mitigation.
    "RTM.OTE.v1": (("impulse", "w_unit"), ("ote_zone", "w_unit"),
                   ("mitigation", "w_unit")),
    # §3.5 Judas chain: deceptive move → 180° reversal.
    "RTM.JUDAS.v1": (("judas", "w_unit"), ("reversal", "w_unit")),
    # §3.6 UTC activity-window alignment chain.
    "RTM.UTC_ACTIVITY_WINDOW.v1": (("utc_window", "w_unit"),),
}


def expected_components(framework_id: str,
                        params: Optional[EngineParams] = None
                        ) -> List["ComponentDef"]:
    """Return the reference chain ``[s1..sm]`` of a framework (§3.1)."""
    if framework_id not in CHAIN_DEFS:
        raise ValueError(f"UNKNOWN_FRAMEWORK_QX: {framework_id!r}")
    params = params or EngineParams()
    out: List[ComponentDef] = []
    for seq, (cid, weight_attr) in enumerate(CHAIN_DEFS[framework_id]):
        out.append(ComponentDef(cid=cid, weight=float(getattr(params, weight_attr)),
                                expected_seq=seq, required=True))
    return out


def framework_threshold(framework_id: str,
                        params: Optional[EngineParams] = None) -> float:
    """Minimum integrity for emission: θ_mss for MSS, θ_int otherwise (§6)."""
    params = params or EngineParams()
    return params.th_mss if framework_id == "RTM.MSS.v1" else params.th_int


# ---------------------------------------------------------------------------
# §3.1 order_map / sequence_integrity (0.5 partial penalty)
# ---------------------------------------------------------------------------


@dataclass
class OrderMapEntry:
    """§2 ``order_map`` row: PIT-confirmed timestamp + order verdict."""

    cid: str
    t_confirm_ms: int
    seq_idx: int
    actual_idx: int
    p_confirm: float
    order_ok: bool = False


@dataclass
class ComponentDef:
    """§3.1 reference-chain component: weight + expected order slot."""

    cid: str
    weight: float
    expected_seq: int
    required: bool = True


@dataclass
class RTMBundle:
    """§2 ``Bundle`` / §5.1 RTMBundle v4 (schema-required fields verbatim)."""

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
    version: str = BUNDLE_VERSION
    fate: str = "active"
    utc_window_aligned: bool = False
    mtf_align_score: float = 0.0
    conflict_with: Optional[str] = None
    # Degradation / lineage carriers (additive; §8.7 keeps them optional).
    order_map: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    temporal_authority: str = E12_CONTRACT
    degraded: bool = False
    degraded_reason: Optional[str] = None
    age_bars: int = 0
    created_at_ms: Optional[int] = None

    def to_canonical(self) -> Dict[str, Any]:
        """Canonical snapshot payload (§5.4); ``snapshot_id`` excluded."""
        return {
            "framework_id": self.framework_id,
            "present": list(self.components_present),
            "integrity": self.integrity,
            "as_of_ms": self.as_of_ms,
        }

    def update_snapshot(self) -> "RTMBundle":
        self.snapshot_id = make_snapshot_id(self.to_canonical())
        return self

    def validate_schema(self) -> None:
        """§5.1 RTMBundle v4 JSON-schema conformance (fail-closed)."""
        import re
        for name in BUNDLE_REQUIRED:
            if getattr(self, name, None) in (None, ""):
                raise ValueError(f"BUNDLE_SCHEMA_QX: missing {name}")
        if not re.fullmatch(r"bnd_[a-f0-9]{12}", self.bid):
            raise ValueError(f"BUNDLE_SCHEMA_QX: bid {self.bid!r}")
        if self.framework_id not in FRAMEWORK_IDS:
            raise ValueError(f"BUNDLE_SCHEMA_QX: framework {self.framework_id!r}")
        if not self.components_present:
            raise ValueError("BUNDLE_SCHEMA_QX: components_present minItems=1")
        for name in ("integrity", "weight_coverage", "confidence",
                     "mtf_align_score"):
            v = getattr(self, name)
            if not (0.0 <= v <= 1.0) or not math.isfinite(v):
                raise ValueError(f"BUNDLE_SCHEMA_QX: {name}={v!r} outside [0,1]")
        if self.direction not in DIRECTIONS:
            raise ValueError(f"BUNDLE_SCHEMA_QX: direction {self.direction!r}")
        if self.resolution_class not in Q_CLASSES:
            raise ValueError(f"BUNDLE_SCHEMA_QX: class {self.resolution_class!r}")
        if self.fate not in FATES:
            raise ValueError(f"BUNDLE_SCHEMA_QX: fate {self.fate!r}")
        if not re.fullmatch(r"[0-9a-f]{64}", self.snapshot_id):
            raise ValueError("BUNDLE_SCHEMA_QX: snapshot_id not 64-hex")
        if self.version != BUNDLE_VERSION:
            raise ValueError(f"BUNDLE_SCHEMA_QX: version {self.version!r}")
        if self.as_of_ms < 0:
            raise ValueError("BUNDLE_SCHEMA_QX: as_of_ms < 0")
        if len(self.explanation) > 500:
            raise ValueError("BUNDLE_SCHEMA_QX: explanation maxLength=500")


def make_snapshot_id(payload: Dict[str, Any]) -> str:
    """§5.4 canonical identity: SHA256(canonical_json(payload envelope))."""
    return canonical_snapshot_id(ENGINE, CONTRACT_VERSION, payload)


def short_fingerprint(d: Dict[str, Any]) -> str:
    """§4 non-authoritative local fingerprint; NEVER used as snapshot_id."""
    s = json.dumps(d, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(s).hexdigest()[:16]


def build_order_map(components: Sequence[ComponentDef],
                    confirmations: Sequence[Dict[str, Any]]) -> Dict[str, OrderMapEntry]:
    """Build the PIT ``order_map`` from upstream component confirmations.

    Each confirmation is ``{cid, t_confirm_ms, p_confirm[, seq_idx]}``.
    §3.8 duplicate events → de-duplicated on ``(cid, t_confirm_ms)`` keeping
    the earliest record; ``t_confirm_ms`` is the PIT-safe close time of the
    confirming candle (§2), never a wall-clock substitute.
    """
    seq_by_cid = {c.cid: c.expected_seq for c in components}
    order: Dict[str, OrderMapEntry] = {}
    seen: set = set()
    for rec in sorted(confirmations, key=lambda r: (int(r["t_confirm_ms"]),
                                                    str(r["cid"]))):
        cid = str(rec["cid"])
        t = int(rec["t_confirm_ms"])
        key = (cid, t)
        if key in seen:
            continue                      # §3.8 duplicate-event edge case
        seen.add(key)
        if cid in order:
            continue                      # first PIT confirmation wins
        order[cid] = OrderMapEntry(
            cid=cid, t_confirm_ms=t,
            seq_idx=int(rec.get("seq_idx", seq_by_cid.get(cid, 999))),
            actual_idx=999, p_confirm=float(rec.get("p_confirm", 0.0)),
            order_ok=False)
    return order


def evaluate_order_ok(expected: Sequence[ComponentDef], present: Sequence[str],
                      order_map: Dict[str, OrderMapEntry]) -> None:
    """§3.1/§4: mark ``order_ok`` by comparing PIT-safe ``t_confirm`` values.

    Walks the present components in confirmation-time order; a component whose
    expected slot does not advance the running maximum is out of order.
    """
    exp_seq = {c.cid: c.expected_seq for c in expected}
    present_sorted = sorted((cid for cid in present if cid in order_map),
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


def sequence_integrity_v4(expected: Sequence[ComponentDef], present: Sequence[str],
                          order_map: Dict[str, OrderMapEntry]
                          ) -> Tuple[float, float, List[str]]:
    """§3.1 Integrity with the 0.5 out-of-order partial penalty.

    ``s_i = 1`` present ∧ order_ok, ``0.5`` present ∧ ¬order_ok, ``0`` absent;
    ``Integrity = Σ w_i s_i / (Σ w_i + ε)``; ``sum(w) == 0`` ⇒ Integrity 0.
    """
    total_w = sum(c.weight for c in expected) + EPS
    num = 0.0
    present_w = 0.0
    missing: List[str] = []
    sorted_present = sorted(
        present,
        key=lambda cid: order_map[cid].t_confirm_ms if cid in order_map
        else float("inf"))
    for idx_actual, cid in enumerate(sorted_present):
        if cid in order_map:
            order_map[cid].actual_idx = idx_actual
    for comp in expected:
        cid = comp.cid
        if cid not in present:
            missing.append(cid)
            continue
        present_w += comp.weight
        entry = order_map.get(cid)
        if entry is None:
            num += comp.weight * 0.5      # present but un-timed → partial
        elif entry.order_ok:
            num += comp.weight * 1.0
        else:
            num += comp.weight * 0.5      # §0 design point 7: partial penalty
    raw_w = sum(c.weight for c in expected)
    if raw_w <= 0.0:
        return 0.0, 0.0, missing          # §3.1 edge case
    integrity = num / total_w             # §3.1: denominator Σw + ε
    # §3.1 defines WeightCoverage WITHOUT the ε term (Σ_{i∈O} w_i / Σ_i w_i);
    # §4 reuses the ε-inflated total_w. §3 formula authority applies
    # (ISSUE-CP3-001 precedent) — coverage is the exact ratio.
    weight_coverage = present_w / raw_w
    return integrity, weight_coverage, missing


# ---------------------------------------------------------------------------
# §3.2 Range detection (Accumulation) + §3.8 edge cases
# ---------------------------------------------------------------------------


def wilder_rma_series(values: Sequence[float], period: int) -> float:
    """Wilder RMA (§3.2 "ATR10/ATR100 (Wilder RMA)"; §E09 §3.5 smoothing).

    Seed = SMA of the first ``period`` values, then
    ``RMA_t = (RMA_{t-1}(n-1) + x_t)/n``. Fewer than ``period`` samples ⇒ 0.0
    (no fabrication of a warm-up value).
    """
    if period <= 0 or len(values) < period:
        return 0.0
    rma = sum(values[:period]) / period
    for x in values[period:]:
        rma = (rma * (period - 1) + x) / period
    return rma


def true_range_list(bars: Sequence[Dict[str, Any]]) -> List[float]:
    """TR series skipping §3.8 ``H < L`` invalid bars."""
    trs: List[float] = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["h"], bars[i]["l"], bars[i - 1]["c"]
        if h < l:
            continue                      # §3.2 edge case: invalid bar, skip
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return trs


def atr_ratio_detect(bars: Sequence[Dict[str, Any]],
                     atr_short_period: int = 10,
                     atr_long_period: int = 100,
                     params: Optional[EngineParams] = None
                     ) -> Dict[str, Any]:
    """§3.2 range detection with the §2/§3.8 edge cases applied.

    ``RangeCondition = (N_bars >= 8) ∧ (ATR_s/ATR_l < 0.75) ∧
    (Range_HL/ATR_l < 2.5) ∧ (σ(C)/ATR_l < 0.6) ∧ (VolRatio <= 0.9)``.

    Fail-closed branches (never a synthetic neutral value):
      * ``V = 0`` in the range window ⇒ ``degraded=True``, ``is_range=False``,
        reason ``VOL_UNAVAILABLE_QX`` (ISSUE-CP4-002).
      * ``ATR_long < ε`` ⇒ ratio undefined ⇒ ``is_range=False``.
      * a gap ``> 3·ATR_long`` inside the window ⇒ the range resets
        (ISSUE-CP4-003); ``> 5·ATR`` additionally sets ``gap_edge`` (§3.8).
    """
    p = params or EngineParams()
    n = len(bars)
    out: Dict[str, Any] = {"is_range": False, "ratio": 999.0, "n_bars": n,
                           "hl_range": 0.0, "vol_ratio": None,
                           "sigma_ratio": None, "degraded": False,
                           "reason": None, "gap_reset": False,
                           "gap_edge": False, "atr_short": 0.0,
                           "atr_long": 0.0}
    if n < max(atr_long_period, p.po3_bars) + 1:
        out["reason"] = "INSUFFICIENT_HISTORY_QX"
        return out
    trs = true_range_list(bars)
    atr_s = wilder_rma_series(trs, atr_short_period)
    atr_l = wilder_rma_series(trs, atr_long_period)
    out["atr_short"], out["atr_long"] = atr_s, atr_l
    if atr_l < EPS:
        out["reason"] = "ATR_UNDEFINED_QX"          # §3.2 ATR = 0
        return out
    ratio = atr_s / atr_l
    out["ratio"] = ratio
    window = bars[-p.po3_bars:]
    highs = [b["h"] for b in window if b["h"] >= b["l"]]
    lows = [b["l"] for b in window if b["h"] >= b["l"]]
    closes = [b["c"] for b in window if b["h"] >= b["l"]]
    if not highs or not lows:
        out["reason"] = "NO_VALID_BARS_QX"
        return out
    hl_range = max(highs) - min(lows)
    out["hl_range"] = hl_range
    mean_c = sum(closes) / len(closes)
    var_c = sum((c - mean_c) ** 2 for c in closes) / len(closes)
    sigma_ratio = math.sqrt(var_c) / atr_l
    out["sigma_ratio"] = sigma_ratio
    # Volume compression. V = 0 anywhere in the window ⇒ not authorized.
    vols = [float(b.get("v", 0.0)) for b in window]
    recent_vol = sum(vols) / len(vols)
    lookback = bars[-atr_long_period:-p.po3_bars]
    lookback_vol = (sum(float(b.get("v", 0.0)) for b in lookback) / len(lookback)
                    if lookback else recent_vol)
    if any(v <= 0.0 for v in vols):
        out["degraded"] = True
        out["reason"] = VOL_UNAVAILABLE_REASON      # ISSUE-CP4-002
        out["vol_ratio"] = None
        return out
    vol_ratio = recent_vol / max(lookback_vol, EPS)
    out["vol_ratio"] = vol_ratio
    # Gap scan over the range window (§3.2 reset / §3.8 edge flag).
    for i in range(1, len(window)):
        gap = abs(window[i]["o"] - window[i - 1]["c"])
        if gap > p.gap_reset_atr * atr_l:
            out["gap_reset"] = True
        if gap > p.gap_edge_atr * atr_l:
            out["gap_edge"] = True
    if out["gap_reset"]:
        out["reason"] = "RANGE_RESET_GAP_QX"
        return out
    out["is_range"] = bool(
        n >= p.po3_bars
        and ratio < p.atr_ratio_th
        and hl_range < p.range_hl_max_atr * atr_l
        and sigma_ratio < p.range_sigma_max          # ISSUE-CP4-001
        and vol_ratio <= p.po3_vol_th)
    if not out["is_range"]:
        out["reason"] = "RANGE_CONDITION_UNMET_QX"
    return out


# ---------------------------------------------------------------------------
# §3.3 MSS · §3.4 OTE · §3.5 Judas
# ---------------------------------------------------------------------------


def mss_proximity_check(p_sweep: float, p_choch: float, atr20: float,
                        thresh: float = 0.5) -> bool:
    """§3.3 ``MSS_prox = 1[|p_sweep − p_CHoCH| <= 0.5·ATR20]``."""
    if atr20 < EPS or not math.isfinite(atr20):
        return False
    return abs(p_sweep - p_choch) <= thresh * atr20


def mss_confirmed(p_sweep: float, p_choch: float, atr20: float,
                  chain_integrity: float,
                  params: Optional[EngineParams] = None) -> bool:
    """§3.3 ``MSS = CHoCH ∧ Sweep ∧ MSS_prox ∧ (Integrity >= θ_mss)``."""
    p = params or EngineParams()
    return bool(mss_proximity_check(p_sweep, p_choch, atr20, p.mss_prox_th)
                and chain_integrity >= p.th_mss)


def ote_zone_calc(a: float, b: float, r_lo: float = 0.62, r_hi: float = 0.79,
                  r_star: float = 0.705) -> Optional[Dict[str, float]]:
    """§3.4 ``Zone_OTE = [A+0.62(B−A), A+0.79(B−A)]``, optimal ``A+0.705(B−A)``.

    ``A == B`` ⇒ invalid (None) — the §3.4/§7 Ch.2 "false OTE" failure mode.
    """
    if math.isnan(a) or math.isnan(b) or abs(a - b) < EPS:
        return None
    lo = a + r_lo * (b - a)
    hi = a + r_hi * (b - a)
    return {"lo": min(lo, hi), "hi": max(lo, hi), "star": a + r_star * (b - a),
            "r_lo": r_lo, "r_hi": r_hi, "a": a, "b": b}


def judas_swing_detect(bars: Sequence[Dict[str, Any]], expected_dir: str,
                       atr20: float, max_pen: float = 0.25,
                       params: Optional[EngineParams] = None
                       ) -> Optional[Dict[str, Any]]:
    """§3.5 Judas Swing: deceptive move ``J_len <= k·ATR`` then a ``>= 1.0·J_len``
    reversal within ``<= 3`` candles with ``dir(Rev) = −dir(J)``.
    """
    p = params or EngineParams()
    if expected_dir not in DIRECTIONS:
        raise ValueError(f"JUDAS_DIRECTION_QX: {expected_dir!r}")
    if len(bars) < 5 or atr20 < EPS:
        return None
    recent = list(bars[-p.judas_lookback:])
    start_price = recent[0]["c"]
    judas_dir = "DOWN" if expected_dir == "UP" else "UP"
    judas_end_idx: Optional[int] = None
    max_judas_move = 0.0
    for i, b in enumerate(recent):
        move = b["c"] - start_price
        if judas_dir == "DOWN" and move < 0 and abs(move) > max_judas_move:
            max_judas_move = abs(move)
            judas_end_idx = i
        if judas_dir == "UP" and move > 0 and move > max_judas_move:
            max_judas_move = move
            judas_end_idx = i
    if judas_end_idx is None:
        return None
    j_len = max_judas_move
    if j_len > max_pen * atr20:
        return None                       # too deep to be a Judas swing
    if judas_end_idx + p.judas_max_bars >= len(recent):
        return None                       # no room for the reversal window
    p_judas_end = recent[judas_end_idx]["c"]
    for k in range(judas_end_idx + 1,
                   min(judas_end_idx + 1 + p.judas_max_bars, len(recent))):
        rev_len = recent[k]["c"] - p_judas_end
        if expected_dir == "UP" and rev_len >= j_len * p.judas_rev_min:
            return {"judas_len": j_len, "rev_len": rev_len,
                    "bars_to_rev": k - judas_end_idx,
                    "p_judas_end": p_judas_end, "confirmed": True,
                    "rev_ratio": rev_len / max(j_len, EPS)}
        if expected_dir == "DOWN" and rev_len <= -j_len * p.judas_rev_min:
            return {"judas_len": j_len, "rev_len": abs(rev_len),
                    "bars_to_rev": k - judas_end_idx,
                    "p_judas_end": p_judas_end, "confirmed": True,
                    "rev_ratio": abs(rev_len) / max(j_len, EPS)}
    return None


# ---------------------------------------------------------------------------
# §3.6 UTC activity windows — UTC-fixed, E12-authoritative (degraded at CP-4)
# ---------------------------------------------------------------------------

# The chapter's own registry (KZ.v2.1.1). §6: ``overlap_real_def`` is a
# "non-authoritative duplicate; E12 registry governs" — see the degraded
# branch of utc_activity_window_check().
UTC_WINDOWS: Dict[str, Tuple[float, float]] = {
    "UTC_W0": (0.0, 7.0),
    "UTC_W1": (7.0, 12.5),
    "UTC_W2": (12.5, 21.0),
    "UTC_W3": (21.0, 24.0),
}
UTC_CORE_WINDOWS: Dict[str, Tuple[float, float]] = {
    "UTC_W1_CORE": (7.0, 11.0),
    "UTC_W2_CORE": (12.5, 16.0),
}
UTC_OVERLAP_WINDOW: Tuple[float, float] = (12.5, 16.0)   # 12:30–16:00 UTC


def to_utc_ms(ts: Any) -> int:
    """§3.8 edge case: non-UTC timestamp input is rejected, never converted."""
    if isinstance(ts, (int, float)):
        return int(ts)
    if isinstance(ts, datetime.datetime):
        if ts.tzinfo is None:
            raise ValueError(NON_UTC_REASON)
        offset = ts.utcoffset()
        if offset != datetime.timedelta(0):
            raise ValueError(NON_UTC_REASON)
        return int(ts.timestamp() * 1000)
    if isinstance(ts, str):
        text = ts.strip()
        if text.endswith("Z"):
            dt = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        else:
            dt = datetime.datetime.fromisoformat(text)
            if dt.tzinfo is None or dt.utcoffset() != datetime.timedelta(0):
                raise ValueError(NON_UTC_REASON)
        return int(dt.timestamp() * 1000)
    raise ValueError(NON_UTC_REASON)


def window_overlap(a: Tuple[float, float],
                   b: Tuple[float, float]) -> Optional[Tuple[float, float]]:
    """§3.6 ``Overlap = [max(L_start,N_start), min(L_end,N_end)]``."""
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    return (lo, hi) if lo < hi else None


def utc_activity_window_check(ts: Any,
                              econ_events: Optional[Sequence[Dict[str, Any]]] = None,
                              kz_config_version: str = KZ_CONFIG_VERSION,
                              temporal_provider: Any = None,
                              params: Optional[EngineParams] = None
                              ) -> Dict[str, Any]:
    """§3.6 UTC-fixed activity-window evaluation.

    E12 §3.5 ("Corrected WINDOWS") is the temporal authority. ``temporal_provider``
    is the versioned ``E12_Temporal_Context.Contract v4.0.0`` surface:
    ``temporal_window(ts_ms) -> {"which": [...], "is_overlap": bool,
    "utc_activity_window": str, "config_version": str}``.

    **Degraded branch (ISSUE-CP4-005, P19/ADR-P2-017):** with no provider — or a
    provider that returns nothing — E07 evaluates its own NON-authoritative
    duplicate registry, returns ``degraded=True`` with reason
    ``E12_UNAVAILABLE_DEGRADED_QX``, and never presents the local windows as
    E12-canonical. CP-5 re-tests both modes.
    """
    p = params or EngineParams()
    ts_ms = to_utc_ms(ts)
    econ_events = list(econ_events or [])
    econ_conflict = any(
        abs(int(ev["time_ms"]) - ts_ms) <= p.econ_pause_min * 60 * 1000
        and ev.get("impact") == "HIGH" for ev in econ_events)
    if temporal_provider is not None:
        try:
            canonical = temporal_provider.temporal_window(ts_ms)
        except Exception:                                  # fail closed
            canonical = None
        if canonical:
            return {
                "in_kz": True,
                "which": list(canonical.get("which", [])),
                "utc_activity_window": canonical.get("utc_activity_window", ""),
                "is_overlap": bool(canonical.get("is_overlap", False)),
                "econ_conflict": bool(econ_conflict),
                "rollover_active": False,
                "config_version": canonical.get("config_version",
                                                kz_config_version),
                "source": E12_CONTRACT,
                "degraded": False,
                "degraded_reason": None,
                "as_of_ms": ts_ms,
            }
    # --- degraded branch -------------------------------------------------
    dt = datetime.datetime.fromtimestamp(ts_ms / 1000, tz=datetime.timezone.utc)
    hour = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    which: List[str] = []
    for name, (lo, hi) in UTC_WINDOWS.items():
        if lo <= hour < hi:
            which.append(name)
    core = [name for name, (lo, hi) in UTC_CORE_WINDOWS.items()
            if lo <= hour < hi]
    is_overlap = UTC_OVERLAP_WINDOW[0] <= hour < UTC_OVERLAP_WINDOW[1]
    if is_overlap:
        which.append("UTC_W1_W2_OVERLAP")
    if not which:                                          # defensive
        which = ["UTC_W3"]
    return {
        "in_kz": True,                  # crypto trades continuously (§4 doc)
        "which": which,
        "utc_activity_window": which[0],
        "core_windows": core,
        "is_overlap": bool(is_overlap),
        "econ_conflict": bool(econ_conflict),
        "rollover_active": False,
        "config_version": kz_config_version,
        "source": "E07_LOCAL_NON_AUTHORITATIVE",
        "degraded": True,
        "degraded_reason": E12_UNAVAILABLE_REASON,
        "as_of_ms": ts_ms,
    }


# ---------------------------------------------------------------------------
# §3.7 Confidence + quality classes (with the §3.7 gate caps)
# ---------------------------------------------------------------------------


def bundle_confidence(integrity: float, avg_q: float, mtf_align: float,
                      kz_align: float, alpha: float = 0.4, beta: float = 0.25,
                      gamma: float = 0.2, delta: float = 0.15) -> float:
    """§3.7 ``Conf = min(1, αI + βQ̄ + γMTF + δKZ)``, α+β+γ+δ = 1."""
    return min(1.0, alpha * integrity + beta * avg_q + gamma * mtf_align
               + delta * kz_align)


def kz_align_score(kz_info: Dict[str, Any]) -> float:
    """§4 KZ alignment term: 1.0 in-window, 0.2 otherwise, ×0.7 on econ conflict."""
    score = 1.0 if kz_info.get("in_kz") else 0.2
    if kz_info.get("econ_conflict"):
        score *= 0.7                     # §7 Ch.3 example 3
    return score


def quality_class_cascade(integrity: float, conf: float) -> str:
    """§4 ``build_bundle_pipeline`` classification cascade (executable rule)."""
    if integrity < 0.5:
        return "Q0"
    if integrity < 0.7:
        return "Q1"
    if integrity < 0.8:
        return "Q2"
    if integrity < 0.9:
        return "Q3"
    if integrity <= 1.0 and conf < 0.85:
        return "Q3"
    if integrity >= 0.9 and 0.85 <= conf < 0.95:
        return "Q4"
    return "Q5"


def quality_class_caps(cascade_class: str, conf: float, avg_q: float,
                       mtf_align: float, kz_info: Dict[str, Any],
                       has_conflict: bool = False) -> str:
    """§3.7 conjunctive gates applied as caps (ISSUE-CP4-006).

    §3.7 attaches extra conditions to Q3 (``avgQ >= 0.6``), Q4 (``MTF >= 0.6``)
    and Q5 (Killzone *overlap*, no conflict, economic calendar clear). The §3.7
    Conf ranges are descriptive and do not tile the space, so they are not used
    as hard gates; the conjunctive gates are. A bundle failing a class's gate is
    capped one level down until it satisfies a class's gates (fail-closed).
    """
    idx = Q_CLASSES.index(cascade_class)
    while idx > 0:
        label = Q_CLASSES[idx]
        ok = True
        if label == "Q3":
            ok = avg_q >= 0.6
        elif label == "Q4":
            ok = mtf_align >= 0.6
        elif label == "Q5":
            ok = (bool(kz_info.get("is_overlap")) and mtf_align >= 1.0
                  and not has_conflict and not kz_info.get("econ_conflict")
                  and conf > 0.95)
        if ok:
            return label
        idx -= 1
    return "Q0"


def resolution_class(integrity: float, conf: float, avg_q: float,
                     mtf_align: float, kz_info: Dict[str, Any],
                     has_conflict: bool = False) -> str:
    """Final QX label: §4 cascade capped by the §3.7 conjunctive gates."""
    return quality_class_caps(quality_class_cascade(integrity, conf), conf,
                              avg_q, mtf_align, kz_info, has_conflict)


# ---------------------------------------------------------------------------
# §4 Bundle pipeline · conflict resolver · streaming/idempotency
# ---------------------------------------------------------------------------


def new_bundle_id() -> str:
    """``bid`` = ``bnd_`` + 12 hex chars (§5.1 pattern ``^bnd_[a-f0-9]{12}$``).

    ISSUE-CP4-004: §4 pseudocode uses ``uuid.uuid4()``; the GLOBAL IDENTITY
    contract + P8 permit exactly one in-tree generator (UUIDv7, operational
    identity only). The 12 hex chars are taken from the UUIDv7 *random* field
    (bits 62..111 = 48 random bits), NOT from the leading 48-bit timestamp —
    a timestamp prefix would collide for every bundle created inside the same
    millisecond. The id never enters the canonical snapshot payload.
    """
    return "bnd_" + uuid_v7().replace("-", "")[-12:]


def build_bundle_pipeline(expected: Sequence[ComponentDef], present: Sequence[str],
                          order_map: Dict[str, OrderMapEntry], avg_q: float,
                          mtf_align: float, kz_info: Dict[str, Any],
                          framework_id: str, direction: str, as_of_ms: int,
                          params: Optional[Dict[str, Any]] = None,
                          has_conflict: bool = False) -> Optional[RTMBundle]:
    """§4 ``build_bundle_pipeline`` — evaluate, threshold, classify, snapshot.

    Returns ``None`` when ``Integrity < θ_int`` or ``WeightCoverage < θ_weight``
    (§1 mission 4: emit only above both thresholds).
    """
    p = get_params(params)
    present = list(present)
    order_map = dict(order_map)
    evaluate_order_ok(expected, present, order_map)
    integrity, weight_cov, missing = sequence_integrity_v4(expected, present,
                                                           order_map)
    th_int = framework_threshold(framework_id, p)
    if integrity < th_int or weight_cov < p.th_weight:
        return None
    kz_score = kz_align_score(kz_info)
    conf = bundle_confidence(integrity, avg_q, mtf_align, kz_score,
                             p.alpha, p.beta, p.gamma, p.delta)
    qclass = resolution_class(integrity, conf, avg_q, mtf_align, kz_info,
                              has_conflict)
    payload = {"framework_id": framework_id, "present": present,
               "integrity": integrity, "as_of_ms": as_of_ms}
    bundle = RTMBundle(
        bid=new_bundle_id(), framework_id=framework_id,
        components_present=present, components_missing=missing,
        integrity=integrity, weight_coverage=weight_cov, confidence=conf,
        direction=direction, resolution_class=qclass,
        explanation=",".join(present)[:500], as_of_ms=as_of_ms,
        snapshot_id=make_snapshot_id(payload),
        utc_window_aligned=bool(kz_info.get("in_kz", False)),
        mtf_align_score=mtf_align,
        order_map={cid: {"cid": e.cid, "t_confirm_ms": e.t_confirm_ms,
                         "seq_idx": e.seq_idx, "actual_idx": e.actual_idx,
                         "p_confirm": e.p_confirm, "order_ok": e.order_ok}
                   for cid, e in order_map.items()},
        temporal_authority=str(kz_info.get("source", E12_CONTRACT)),
        degraded=bool(kz_info.get("degraded", False)),
        degraded_reason=kz_info.get("degraded_reason"),
        created_at_ms=as_of_ms)
    bundle.validate_schema()
    return bundle


def resolve_conflicting_bundles(bundles: Sequence[RTMBundle],
                                params: Optional[EngineParams] = None
                                ) -> List[RTMBundle]:
    """§0/§4 conflict resolver: opposite direction + >70% time overlap.

    The newer bundle supersedes the older one only when its confidence exceeds
    the older by ``conflict_conf_margin`` (0.1); otherwise the newer bundle is
    invalidated and the older survives.
    """
    p = params or EngineParams()
    ordered = sorted(bundles, key=lambda b: b.as_of_ms)
    active: List[RTMBundle] = []
    for b in ordered:
        conflict = False
        for a in active:
            if a.fate != "active":
                continue
            time_overlap = abs(b.as_of_ms - a.as_of_ms) < p.conflict_overlap_ms
            opposite = b.direction != a.direction
            if time_overlap and opposite:
                if b.confidence > a.confidence + p.conflict_conf_margin:
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


def update_bundle_fate(bundle: RTMBundle, bars_since: int = 0,
                       opposite_bos: bool = False, opposite_sweep: bool = False,
                       ote_tapped: bool = False, continuation: bool = False,
                       params: Optional[EngineParams] = None) -> RTMBundle:
    """§5.2 fate state machine (forward-only; terminal fates never revert).

    ``proposed →(integrity>=θ_int)→ active →(BOS opposite ∧ sweep opposite)→
    invalidated`` · ``active →(age > expiry=20 bars)→ expired`` ·
    ``active →(conflict ∧ superseded)→ superseded`` ·
    ``active →(OTE tapped ∧ continuation)→ completed``.
    """
    p = params or EngineParams()
    if bundle.fate in TERMINAL_FATES:
        return bundle
    bundle.age_bars = int(bars_since)
    if opposite_bos and opposite_sweep:
        bundle.fate = "invalidated"
    elif ote_tapped and continuation:
        bundle.fate = "completed"
    elif bundle.age_bars > p.bundle_expiry_bars:
        bundle.fate = "expired"
    return bundle


class RTMEngineStreaming:
    """§4 streaming + idempotency wrapper (one bundle set per time bucket)."""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        self.params = get_params(params)
        self.buffer: deque = deque(maxlen=500)
        self.last_bundles: Dict[str, List[RTMBundle]] = {}
        self.emitted_buckets: set = set()

    def on_event(self, event: Dict[str, Any]) -> None:
        """Buffer one upstream evidence event (E01..E06/E12)."""
        if "cid" not in event or "t_confirm_ms" not in event:
            raise ValueError("EVENT_CONTRACT_QX: cid/t_confirm_ms required")
        self.buffer.append(dict(event))

    def confirmations(self, framework_id: str, as_of_ms: int
                      ) -> List[Dict[str, Any]]:
        """PIT-filtered confirmations for a framework (``t' <= t``)."""
        cids = {cid for cid, _ in CHAIN_DEFS[framework_id]}
        return [dict(e) for e in self.buffer
                if e["cid"] in cids and int(e["t_confirm_ms"]) <= as_of_ms]

    def process_at(self, as_of_ms: int, bars: Sequence[Dict[str, Any]],
                   econ: Optional[Sequence[Dict[str, Any]]] = None,
                   framework_id: str = "RTM.PO3.v1", direction: str = "UP",
                   avg_q: float = 0.9, mtf_align: float = 1.0,
                   temporal_provider: Any = None) -> List[RTMBundle]:
        """Idempotent bundle production at a closed-candle boundary.

        ``idem_key = as_of_ms // bucket`` (§4); a repeat call for the same
        bucket returns the already-produced bundles and produces nothing new.
        """
        idem_key = f"{as_of_ms // self.params.idem_bucket_ms}"
        if idem_key in self.emitted_buckets:
            return []
        expected = expected_components(framework_id, self.params)
        conf = self.confirmations(framework_id, as_of_ms)
        order_map = build_order_map(expected, conf)
        present = [c["cid"] for c in conf]
        kz_info = utc_activity_window_check(
            as_of_ms, econ, temporal_provider=temporal_provider,
            params=self.params)
        bundle = build_bundle_pipeline(
            expected, present, order_map, avg_q, mtf_align, kz_info,
            framework_id, direction, as_of_ms,
            params=self.params.__dict__, )
        self.emitted_buckets.add(idem_key)
        out = [bundle] if bundle is not None else []
        self.last_bundles[idem_key] = out
        return out


# ---------------------------------------------------------------------------
# §8.7 Serialization compatibility (v3 → v4)
# ---------------------------------------------------------------------------

_V3_FIELD_MAP = {
    "bundle_id": "bid",
    "framework": "framework_id",
    "present": "components_present",
    "missing": "components_missing",
    "q_class": "resolution_class",
    "as_of": "as_of_ms",
    "snapshot": "snapshot_id",
}


def load_v3_adapter(payload: Dict[str, Any]) -> RTMBundle:
    """§8.7 v3→v4 upcaster: new fields optional with defaults; never fails.

    Read-only migration (ADR-P2-009): no state mutation, no invented values.
    An ambiguous or schema-violating payload is rejected fail-closed.
    """
    if not isinstance(payload, dict):
        raise ValueError("V3_ADAPTER_QX: payload is not an object")
    data: Dict[str, Any] = {}
    for key, value in payload.items():
        data[_V3_FIELD_MAP.get(key, key)] = value
    if "bid" in data and not str(data["bid"]).startswith("bnd_"):
        data["bid"] = "bnd_" + hashlib.sha256(
            str(data["bid"]).encode("utf-8")).hexdigest()[:12]
    required = ("bid", "framework_id", "components_present", "integrity",
                "confidence", "direction", "as_of_ms")
    missing = [k for k in required if k not in data or data[k] in (None, "")]
    if missing:
        raise ValueError(f"V3_ADAPTER_QX: missing {sorted(missing)}")
    bundle = RTMBundle(
        bid=str(data["bid"]), framework_id=str(data["framework_id"]),
        components_present=list(data["components_present"]),
        components_missing=list(data.get("components_missing", [])),
        integrity=float(data["integrity"]),
        weight_coverage=float(data.get("weight_coverage",
                                       data["integrity"])),
        confidence=float(data["confidence"]),
        direction=str(data["direction"]),
        resolution_class=str(data.get("resolution_class", "Q0")),
        explanation=str(data.get("explanation", ""))[:500],
        as_of_ms=int(data["as_of_ms"]),
        snapshot_id=str(data.get("snapshot_id", "")),
        version=BUNDLE_VERSION, fate=str(data.get("fate", "active")),
        utc_window_aligned=bool(data.get("utc_window_aligned", False)),
        mtf_align_score=float(data.get("mtf_align_score", 0.0)),
        conflict_with=data.get("conflict_with"),
        temporal_authority=str(data.get("temporal_authority",
                                        "E07.v3.0.0_LEGACY")),
        degraded=bool(data.get("degraded", True)),
        degraded_reason=data.get("degraded_reason", "LEGACY_V3_PAYLOAD_QX"),
        age_bars=int(data.get("age_bars", 0)))
    if not bundle.snapshot_id:
        bundle.update_snapshot()         # recompute, never copy a doc hash
    return bundle


# ---------------------------------------------------------------------------
# §8.6 Redundancy guard
# ---------------------------------------------------------------------------


def pearson(x: Sequence[float], y: Sequence[float]) -> float:
    """Pearson r (stdlib); < 2 samples or zero variance ⇒ 0.0."""
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


def redundancy_halve_weights(components: Sequence[ComponentDef],
                             series: Dict[str, Sequence[float]],
                             threshold: float = 0.85) -> List[ComponentDef]:
    """§8.6/§7 Ch.3: correlation > 0.85 between components ⇒ weight halved."""
    halved: List[ComponentDef] = []
    flagged: set = set()
    names = [c.cid for c in components if c.cid in series]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if abs(pearson(series[a], series[b])) > threshold:
                flagged.add(b)           # the later component is the duplicate
    for c in components:
        halved.append(replace(c, weight=c.weight * 0.5) if c.cid in flagged
                      else replace(c))
    return halved


# ---------------------------------------------------------------------------
# §8.5 Calibration — Wilson CI (stdlib, z = 1.96)
# ---------------------------------------------------------------------------


def wilson_ci(p_hat: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    """§8.5 Wilson score interval."""
    if n <= 0:
        return (0.0, 0.0)
    denom = 1.0 + z * z / n
    centre = p_hat + z * z / (2 * n)
    spread = z * math.sqrt(max(p_hat * (1 - p_hat) / n + z * z / (4 * n * n), 0.0))
    return ((centre - spread) / denom, (centre + spread) / denom)


# ---------------------------------------------------------------------------
# Batch driver + catalog bridge
# ---------------------------------------------------------------------------


def observation_to_bar(obs: MarketObservation,
                       timeframe: Optional[str] = None) -> Dict[str, Any]:
    """MarketObservation → the ``{ts,o,h,l,c,v,is_closed}`` bar shape."""
    ts_ms = 0
    try:
        dt = datetime.datetime.fromisoformat(str(obs.timestamp).replace("Z", "+00:00"))
        ts_ms = int(dt.timestamp() * 1000)
    except (ValueError, AttributeError):
        ts_ms = 0
    return {"ts": ts_ms, "o": float(obs.open), "h": float(obs.high),
            "l": float(obs.low), "c": float(obs.close),
            "v": float(obs.volume), "is_closed": obs.is_closed,
            "timeframe": timeframe}


def run_engine(bars: Sequence[Dict[str, Any]],
               events: Optional[Sequence[Dict[str, Any]]] = None,
               framework_id: str = "RTM.PO3.v1",
               direction: str = "UP",
               as_of_ms: Optional[int] = None,
               avg_q: float = 0.9,
               mtf_align: float = 1.0,
               econ_events: Optional[Sequence[Dict[str, Any]]] = None,
               temporal_provider: Any = None,
               params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Batch driver over a closed-candle window.

    ``events`` are upstream confirmations ``{cid, t_confirm_ms, p_confirm}``.
    Returns ``{engine, range, kz, bundle, events, integrity, weight_coverage}``.
    The degraded (E12-absent) branch is the CP-4 default — see
    ``utc_activity_window_check``.
    """
    p = get_params(params)
    bars = list(bars)
    if not bars:
        raise ValueError("EMPTY_WINDOW_QX: E07 requires a closed-candle window")
    as_of = int(as_of_ms if as_of_ms is not None else bars[-1]["ts"])
    range_info = atr_ratio_detect(bars, p.atr_short_period, p.atr_long_period, p)
    kz_info = utc_activity_window_check(as_of, econ_events,
                                        temporal_provider=temporal_provider,
                                        params=p)
    expected = expected_components(framework_id, p)
    confs = [dict(e) for e in (events or [])
             if int(e["t_confirm_ms"]) <= as_of]          # PIT filter (§3.1)
    order_map = build_order_map(expected, confs)
    present = sorted({c["cid"] for c in confs})
    evaluate_order_ok(expected, present, order_map)
    integrity, weight_cov, missing = sequence_integrity_v4(expected, present,
                                                           order_map)
    ev_names: List[str] = []
    if range_info["is_range"]:
        ev_names.append("EV_RTM_001")
    bundle = build_bundle_pipeline(
        expected, present, order_map, avg_q, mtf_align, kz_info, framework_id,
        direction, as_of, params=p.__dict__)
    if bundle is not None:
        ev_names.append("EV_RTM_011" if framework_id == "RTM.CHAIN.v1"
                        else "EV_RTM_004")
        if kz_info.get("in_kz"):
            ev_names.append("EV_RTM_007")
    else:
        ev_names.append("EV_RTM_005")
    return {"engine": ENGINE, "contract_version": CONTRACT_VERSION,
            "range": range_info, "kz": kz_info, "bundle": bundle,
            "events": ev_names, "integrity": integrity,
            "weight_coverage": weight_cov, "missing": missing,
            "as_of_ms": as_of,
            "degraded": bool(kz_info.get("degraded")),
            "degraded_reason": kz_info.get("degraded_reason")}


class E07RTMEngine(EngineBase):
    """E07_RTM_ICT on the frozen EngineBase contract (v4.0.0).

    ``compute(symbol, timeframe, as_of, context)``; consumed context keys:
      ``window`` / ``provider``   — closed-candle window (catalog surface)
      ``e07_params``              — §6 overrides (unknown keys rejected)
      ``events``                  — upstream confirmations
                                    ``[{cid, t_confirm_ms, p_confirm}]``
      ``framework_id``            — default ``RTM.PO3.v1``
      ``direction``               — ``UP`` | ``DOWN``
      ``avg_quality``/``mtf_align`` — §3.7 confidence terms
      ``econ_events``             — high-impact calendar rows
      ``temporal_provider``       — ``E12_Temporal_Context.Contract v4.0.0``;
                                    absent ⇒ documented degraded branch
    Emissions: one ``EvidenceEvent`` per produced bundle on
    ``evidence.E07.{condition_state}``; every emission validates the 24-field
    frame. Bundles are context only — never a capital signal (§0, NG2/NG5).
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
        bars = [observation_to_bar(o, timeframe) for o in window_obs]
        result = run_engine(
            bars,
            events=context.get("events"),
            framework_id=context.get("framework_id", "RTM.PO3.v1"),
            direction=context.get("direction", "UP"),
            as_of_ms=context.get("as_of_ms"),
            avg_q=float(context.get("avg_quality", 0.9)),
            mtf_align=float(context.get("mtf_align", 1.0)),
            econ_events=context.get("econ_events"),
            temporal_provider=context.get("temporal_provider"),
            params=context.get("e07_params"))
        bundle = result["bundle"]
        if bundle is None:
            return []
        quality = self._window_quality(window_obs)
        return [self._to_evidence(bundle, symbol, timeframe, quality, result)]

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

    def _to_evidence(self, bundle: RTMBundle, symbol: str, timeframe: str,
                     quality: float, result: Dict[str, Any]) -> EvidenceEvent:
        iso = datetime.datetime.fromtimestamp(
            bundle.as_of_ms / 1000.0, tz=datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.") + f"{bundle.as_of_ms % 1000:03d}Z"
        direction = 1 if bundle.direction == "UP" else -1
        explanation = (f"E07 {bundle.framework_id} {bundle.direction} "
                       f"I={bundle.integrity:.4f} conf={bundle.confidence:.4f} "
                       f"{bundle.resolution_class} fate={bundle.fate}")
        if bundle.degraded:
            explanation += f" degraded={bundle.degraded_reason}"
        return EvidenceEvent(
            evidence_id=uuid_v7(),
            engine_id=self.engine_id,
            analyst_version=self.analyst_version,
            symbol=symbol, timeframe=timeframe,
            snapshot_id=bundle.snapshot_id,
            event_time=iso, availability_time=iso,
            observation_window={"bars": len(bundle.components_present),
                                "tf": timeframe,
                                "framework": bundle.framework_id},
            feature_snapshot_id=bundle.snapshot_id,
            feature_dependencies=("window", "I_Structure_v4", "I_Liquidity_v4",
                                  "I_Volume_v4", "I_FVG_v4",
                                  "I_Temporal_v4(degradable)"),
            condition_state=f"{bundle.framework_id}_{bundle.fate}",
            direction=direction,
            strength=float(min(max(bundle.integrity, 0.0), 1.0)),
            confidence=float(min(max(bundle.confidence, 0.0), 1.0)),
            quality=float(quality),
            validity="DEGRADED" if bundle.degraded else "VALID",
            fate_state=LifecycleState.ACTIVE if bundle.fate == "active"
            else LifecycleState.CONFIRMED,
            age=float(bundle.age_bars),
            decay=math.exp(-bundle.age_bars /
                           max(self.p_default().bundle_expiry_bars, 1)),
            explanation=explanation[:500],
            parameter_version="E07-RTM-V4.0.0/DEFAULTS-v1",
            lineage=(f"framework_{bundle.framework_id}",
                     f"temporal_{bundle.temporal_authority}"),
            resolution_class=bundle.resolution_class,
        )

    @staticmethod
    def p_default() -> EngineParams:
        return EngineParams()


__all__ = [
    "ANALYST_VERSION", "ATR_FLOOR", "BUNDLE_REQUIRED", "BUNDLE_VERSION",
    "CHAIN_DEFS", "CONTRACT_VERSION", "E07_DEFAULTS", "E07RTMEngine", "ENGINE",
    "EPS", "EVENT_CATALOG", "E12_CONTRACT", "E12_UNAVAILABLE_REASON",
    "FRAMEWORK_IDS", "FATES", "KZ_CONFIG_VERSION", "NON_UTC_REASON",
    "OrderMapEntry", "ComponentDef", "EngineParams", "Q_CLASSES", "RTMBundle",
    "RTMEngineStreaming", "TERMINAL_FATES", "UTC_CORE_WINDOWS",
    "UTC_OVERLAP_WINDOW", "UTC_WINDOWS", "VOL_UNAVAILABLE_REASON",
    "WaveOutError", "atr_ratio_detect", "build_bundle_pipeline",
    "build_order_map", "bundle_confidence", "evaluate_order_ok",
    "expected_components", "framework_threshold", "get_params",
    "judas_swing_detect", "kz_align_score", "load_v3_adapter",
    "make_snapshot_id", "mss_confirmed", "mss_proximity_check",
    "new_bundle_id", "observation_to_bar", "ote_zone_calc", "pearson",
    "quality_class_caps", "quality_class_cascade", "redundancy_halve_weights",
    "resolution_class", "resolve_conflicting_bundles", "run_engine",
    "sequence_integrity_v4", "short_fingerprint", "to_utc_ms",
    "true_range_list", "update_bundle_fate", "utc_activity_window_check",
    "wilder_rma_series", "wilson_ci", "window_overlap",
]
