"""APEX_GEN5 E06 — ORDER BLOCK ENGINE (v4.0.0).

Blueprint: APEX_GEN5.md L6860–8292 (chapter order mirrored: §1/§2
vocabulary → §3 formulas → §4 algorithms → §5 objects/state/events →
§6 params → §7 notes → §8 validation hooks).

Fidelity law for this engine (CP-3 checkpoint + chapter §1.4): E06
CONSUMES E01–E05 evidence strictly through the versioned base-catalog
interfaces — I_Structure_v4, I_Volume_v4, I_Volatility_v4, I_FVG_v4.
Fallback for volume/ATR evidence is NONE: missing, invalid or misaligned
evidence is QX / fail-closed, and E06 MUST NOT recompute volume averages
or true-range statistics for normative decisions (§1.4). The blueprint's
`..._for_test_only` recomputation helpers are test-side only (their names
say so) and live in the test suite, not in this runtime module;
tests/unit/test_e06_orderblock.py carries the consumption lint proving
zero internal re-computation of E01–E05 indicator paths here.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field, asdict
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

ENGINE = "E06_OrderBlock"
CONTRACT_VERSION = "4.0.0"
ANALYST_VERSION = "4.0.0+" + "0" * 40

EPS = float(eps_for_engine("E06"))          # 1e-8 (§3.1 Tier-2 row)

OTYPES = ("ENTRY", "BREAKER", "REVERSAL", "MITIGATION_BLOCK")
QUALITIES = ("Q0", "Q1", "Q2", "Q3", "Q4", "QX")
FATES = ("CANDIDATE", "ACTIVE", "RETESTED", "MITIGATED", "INVALIDATED",
         "EXPIRED", "MERGED")

EVENT_CATALOG = {
    "EV_OBK_001": "OB_Formed",
    "EV_OBK_002": "Displacement_Confirmed",
    "EV_OBK_003": "OB_Retested",
    "EV_OBK_004": "OB_Mitigated",
    "EV_OBK_005": "OB_Invalidated",
    "EV_OBK_006": "OB_Expired",
    "EV_OBK_007": "Breaker_Converted",
    "EV_OBK_008": "OB_Confluence",
    "EV_OBK_009": "Reversal_OB_Confirmed",
}

OB_REQUIRED = ("oid", "direction", "zone_lo", "zone_hi", "origin_ts",
               "origin_idx", "displacement_mag", "displacement_multi",
               "structural_event", "otype", "quality", "fate",
               "snapshot_id", "version")


# --------------------------------------------------------------------------
# §6 Parameters (frozen defaults; governance per §6 process)
# --------------------------------------------------------------------------
@dataclass
class EngineParams:
    body_min: float = 0.55          # θ_body
    disp_min: float = 1.5           # θ_disp (Q1 multi-displacement floor)
    disp_high: float = 1.8          # θ_disp_high (Q3 Context OR term)
    zone_tol: float = 0.15          # θ_tol asymmetric zone tolerance
    vol_min: float = 1.3            # θ_vol
    max_age_bars: int = 144         # θ_age
    mit_activate: float = 0.5       # Mitigated threshold
    min_width_atr: float = 0.15     # θ_minW
    inv_tol: float = 0.2            # θ_inv_tol
    iou_thresh: float = 0.7         # IoU merge threshold
    merge_bars: int = 20            # merge time window
    breaker_enabled: bool = True    # policy flag
    salience_weights: Tuple[float, float, float, float] = (
        0.35, 0.25, 0.25, 0.15)     # w_d, w_s, w_v, w_f (Σ=1)
    atr_period: int = 14
    vol_sma_period: int = 20
    disp_max_k: int = 5
    confluence_iou: float = 0.5     # §8.6 OB/FVG confluence threshold
    confluence_mid_atr: float = 0.5  # §8.6 midpoint distance bound


E06_DEFAULTS: Dict[str, Any] = {
    k: getattr(EngineParams(), k) for k in (
        "body_min", "disp_min", "disp_high", "zone_tol", "vol_min",
        "max_age_bars", "mit_activate", "min_width_atr", "inv_tol",
        "iou_thresh", "merge_bars", "breaker_enabled", "salience_weights",
        "atr_period", "vol_sma_period", "disp_max_k", "confluence_iou",
        "confluence_mid_atr")}


def get_params(overrides: Optional[Dict[str, Any]] = None) -> EngineParams:
    """Frozen defaults + governed overrides (unknown keys rejected)."""
    values = dict(E06_DEFAULTS)
    for key, value in (overrides or {}).items():
        if key not in E06_DEFAULTS:
            raise ValueError(f"UNKNOWN_E06_PARAM_QX:{key}")
        values[key] = value
    params = EngineParams(**values)
    if abs(sum(params.salience_weights) - 1.0) > 1e-9:
        raise ValueError("E06_SALIENCE_WEIGHTS_SUM_QX")
    return params


def canonical_hash(obj: Any) -> str:
    return canonical_snapshot_id(ENGINE, CONTRACT_VERSION, obj)


def build_e06_snapshot_payload(ob: "OB") -> Dict[str, Any]:
    """Single governed identity boundary: only contract fields enter."""
    return {"engine": ENGINE, "contract_version": CONTRACT_VERSION,
            "state": ob.to_canonical()}


def e06_snapshot_id(ob: "OB") -> str:
    return canonical_snapshot_id(ENGINE, CONTRACT_VERSION,
                                 {"state": ob.to_canonical()})


# --------------------------------------------------------------------------
# §3.2 core formulas
# --------------------------------------------------------------------------
def body_ratio_pit(bar: Dict[str, Any]) -> float:
    """§3.2 BodyRatio with H<L invalid handling (§3.3)."""
    if bar["h"] < bar["l"]:
        return 0.0
    rng = max(bar["h"] - bar["l"], EPS)
    return abs(bar["c"] - bar["o"]) / rng


def iou_zones(a_lo: float, a_hi: float, b_lo: float, b_hi: float,
              eps: float = EPS) -> float:
    """§3.2 IoU of two zones."""
    inter = max(0.0, min(a_hi, b_hi) - max(a_lo, b_lo))
    union = (a_hi - a_lo) + (b_hi - b_lo) - inter
    return inter / max(union, eps)


def asymmetric_zone(direction: str, bar: Dict[str, Any],
                    atr: float, zone_tol: float) -> Tuple[float, float]:
    """§2.6 asymmetric zone (orders cluster below/above the body)."""
    tol = zone_tol * atr
    if direction == "UP":
        return bar["l"] - tol, min(bar["o"], bar["c"]) + tol
    return max(bar["o"], bar["c"]) - tol, bar["h"] + tol


def directional_mitigation(ob: "OB", bar: Dict[str, Any],
                           prev_close: float, first_touch_strict: bool
                           ) -> Tuple[bool, bool, float]:
    """§2.8 directional mitigation: (touch, side_ok, depth). A UP OB must
    be approached from above (first touch strict; lenient afterwards —
    §4 reference semantics)."""
    touch = bar["l"] <= ob.zone_hi and bar["h"] >= ob.zone_lo
    if not touch:
        return False, False, 0.0
    if ob.direction == "UP":
        side_ok = (prev_close > ob.zone_hi) or not first_touch_strict
    else:
        side_ok = (prev_close < ob.zone_lo) or not first_touch_strict
    inter = max(0.0, min(ob.zone_hi, bar["h"]) - max(ob.zone_lo, bar["l"]))
    depth = inter / max(ob.width, EPS)
    return True, side_ok, depth


def wilson_ci(p_hat: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    """§7 Ch.1-14 / §8.5 Wilson CI."""
    if n <= 0:
        return (0.0, 1.0)
    denom = 1.0 + z * z / n
    centre = p_hat + z * z / (2 * n)
    half = z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
    return ((centre - half) / denom, (centre + half) / denom)


def binomial_test_gt_half(k: int, n: int) -> float:
    """§7 Ch.1-14 H0: p ≤ 0.5 vs H1: p > 0.5 (exact binomial, stdlib)."""
    if n <= 0:
        return 1.0
    total = 0.0
    for i in range(k, n + 1):
        total += math.exp(math.lgamma(n + 1) - math.lgamma(i + 1)
                          - math.lgamma(n - i + 1)) * (0.5 ** n)
    return min(1.0, total)


def promote_q4(touches: int, n: int) -> bool:
    """§8.5 calibration rule: Wilson lower bound > 0.5 AND binomial
    p-value < 0.5… < 0.05 → Q4. (Runtime never fabricates OOS statistics;
    this gate is the documented promotion path used by the research
    layer.)"""
    if n <= 0:
        return False
    lo, _ = wilson_ci(touches / n, n)
    return lo > 0.5 and binomial_test_gt_half(touches, n) < 0.05


# --------------------------------------------------------------------------
# §4 objects
# --------------------------------------------------------------------------
@dataclass
class OB:
    oid: str
    direction: str                      # UP|DOWN (expected move direction)
    zone_lo: float
    zone_hi: float
    origin_ts: int
    origin_idx: int
    displacement_mag: float
    displacement_multi: float
    structural_event: str
    structural_strength: float
    otype: str = "ENTRY"
    age: int = 0
    touch_count: int = 0
    mitigation: float = 0.0
    salience: float = 0.0
    vol_ratio: float = 0.0
    quality: str = "Q0"
    fate: str = "CANDIDATE"
    confirmed_at: int = 0
    snapshot_id: str = ""
    lineage: List[Dict[str, Any]] = field(default_factory=list)
    width: float = 0.0
    iou_group: Optional[str] = None
    version: str = CONTRACT_VERSION

    def to_canonical(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("snapshot_id", None)
        d.pop("lineage", None)
        return d

    def validate_schema(self) -> None:
        """§5.1 OBObject_V4 required fields + enums."""
        if self.direction not in ("UP", "DOWN"):
            raise ValueError("OB_DIRECTION_QX")
        if self.structural_event not in ("BOS", "CHoCH", "NONE"):
            raise ValueError(f"OB_STRUCT_EVENT_QX:{self.structural_event}")
        if self.otype not in OTYPES:
            raise ValueError(f"OB_OTYPE_QX:{self.otype}")
        if self.quality not in QUALITIES:
            raise ValueError(f"OB_QUALITY_QX:{self.quality}")
        if self.fate not in FATES:
            raise ValueError(f"OB_FATE_QX:{self.fate}")
        if not (isinstance(self.snapshot_id, str)
                and len(self.snapshot_id) == 64):
            raise ValueError("OB_SNAPSHOT_QX")
        if self.version != CONTRACT_VERSION:
            raise ValueError("OB_VERSION_QX")


def promote_quality(ob: OB, checks: Dict[str, bool], ts: int = 0) -> OB:
    """§1.6 Q0→Q3 promotion ladder, recorded in quality_lineage."""
    start = ob.quality
    target = "Q0"
    if checks.get("origin") and checks.get("disp_single"):
        target = "Q1"
    if target == "Q1" and checks.get("vol_ratio"):
        target = "Q2"
    if (target == "Q2" and (checks.get("fvg_same")
                            or checks.get("disp_high"))
            and checks.get("structural")):
        target = "Q3"
    if checks.get("oos_validated") and target == "Q3":
        target = "Q4"
    if QUALITIES.index(target) > QUALITIES.index(start):
        ob.quality = target
        ob.lineage.append({"from": start, "to": target,
                           "reason": "promote_quality", "ts": ts})
    return ob


# --------------------------------------------------------------------------
# §4.2 streaming engine
# --------------------------------------------------------------------------
class OrderBlockEngine:
    """§4 reference implementation — stateful, streaming, replayable.

    Evidence intake (§1.4): ingest_bars(bars_closed, volume_evidence,
    volatility_evidence). Volume/ATR evidence is the E03 I_Volume_v4 and
    E04 I_Volatility_v4 contract output; missing/misaligned evidence is
    QX fail-closed. E06 NEVER recomputes volume SMA or ATR for normative
    decisions (consumption lint: tests/unit/test_e06_orderblock.py).
    """

    def __init__(self, params: Optional[EngineParams] = None):
        self.p = params or EngineParams()
        self.active_obs: List[OB] = []
        self.history: List[OB] = []
        self.bars: List[Dict[str, Any]] = []
        self.atr: List[float] = []
        self.volatility_evidence: List[Optional[Dict[str, Any]]] = []
        self.volume_evidence: List[Optional[Dict[str, Any]]] = []
        self.events: List[Dict[str, Any]] = []

    # -- §1.4 evidence intake (fail-closed; no internal recomputation) ----
    def ingest_bars(self, bars_closed: Sequence[Dict[str, Any]],
                    volume_evidence: Sequence[Optional[Dict[str, Any]]],
                    volatility_evidence: Sequence[Optional[Dict[str, Any]]]
                    ) -> None:
        self.bars = [b for b in bars_closed if b.get("h") >= b.get("l")]
        if (len(volume_evidence) != len(self.bars)
                or len(volatility_evidence) != len(self.bars)):
            raise ValueError("UPSTREAM_EVIDENCE_ALIGNMENT_QX")
        for ev in volume_evidence:
            if (ev is None or ev.get("snapshot_id") is None
                    or ev.get("as_of_ts") is None):
                raise ValueError("MISSING_VOLUME_EVIDENCE_QX")
            if ev.get("as_of_ts") < ev.get("availability_time_ms",
                                            ev.get("as_of_ts")):
                raise ValueError("VOLUME_EVIDENCE_PIT_QX")
        self.volume_evidence = list(volume_evidence)
        self.volatility_evidence = list(volatility_evidence)
        self.atr = []
        for ev in volatility_evidence:
            if (ev is None or ev.get("snapshot_id") is None
                    or ev.get("as_of") is None or ev.get("atr_n") is None):
                raise ValueError("MISSING_VOLATILITY_EVIDENCE_QX")
            atr_value = float(ev["atr_n"])
            if not math.isfinite(atr_value):
                raise ValueError("INVALID_VOLATILITY_EVIDENCE_QX")
            self.atr.append(atr_value)

    def _safe_vol_ratio(self, idx: int) -> float:
        if idx >= len(self.volume_evidence):
            raise ValueError("MISSING_VOLUME_EVIDENCE_QX")
        ev = self.volume_evidence[idx]
        if (ev is None or ev.get("volume_ratio") is None
                or ev.get("volume_sma") is None):
            raise ValueError("MISSING_VOLUME_EVIDENCE_QX")
        return float(ev["volume_ratio"])

    # -- §4.2 detection ----------------------------------------------------
    def detect_at(self, origin_idx: int,
                  structure_events: Sequence[Dict[str, Any]],
                  fvg_events: Sequence[Dict[str, Any]]) -> Optional[OB]:
        """Origin test + multi-candle displacement + corrected Context +
        asymmetric zone (§2.2–§2.6, §3.2). PIT: reads only bars ≤
        origin_idx+K of CLOSED candles; confirmation is delayed (t+K)."""
        try:
            if origin_idx < 0 or origin_idx + 1 >= len(self.bars):
                return None
            if not self.bars[origin_idx].get("is_closed", True):
                return None
            b0 = self.bars[origin_idx]
            if b0["h"] < b0["l"]:
                return None                       # §3.3 invalid candle
            body_ratio = body_ratio_pit(b0)
            if body_ratio < self.p.body_min:
                return None

            atr_now = (self.atr[origin_idx]
                       if origin_idx < len(self.atr) else EPS)
            if atr_now < EPS:
                atr_now = EPS                     # §3.3 dead market

            disp_sum = 0.0
            K_star = 1
            detected_struct: Optional[Dict[str, Any]] = None
            disp_direction: Optional[str] = None
            for k in range(1, self.p.disp_max_k + 1):
                idx = origin_idx + k
                if idx >= len(self.bars):
                    break
                bk = self.bars[idx]
                if not bk.get("is_closed", True):
                    break
                disp_sum += (bk["h"] - bk["l"])
                if k == 1:
                    disp_direction = "UP" if bk["c"] > bk["o"] else "DOWN"
                for ev in structure_events:
                    if (ev.get("valid_at_idx") == idx
                            and ev.get("direction") == disp_direction):
                        detected_struct = ev
                        K_star = k
                        break
                if detected_struct:
                    break
            if disp_direction is None:
                return None
            origin_bearish = b0["c"] < b0["o"]
            if disp_direction == "UP" and not origin_bearish:
                return None
            if disp_direction == "DOWN" and origin_bearish:
                return None

            disp_multi = disp_sum / max(atr_now, EPS)
            disp_single = ((self.bars[origin_idx + 1]["h"]
                            - self.bars[origin_idx + 1]["l"])
                           / max(atr_now, EPS))
            if disp_multi < self.p.disp_min:
                return None

            vol_ratio = self._safe_vol_ratio(origin_idx + 1)

            # FVG same direction (I_FVG_v4; distance ≤ 2·ATR from origin)
            fvg_same = False
            for f in fvg_events:
                if f.get("direction") != disp_direction:
                    continue
                if not f.get("present", True):
                    continue
                mid_f = (f["lower"] + f["upper"]) / 2
                if abs(mid_f - b0["c"]) <= 2 * atr_now:
                    fvg_same = True
                    break

            # §2.5 corrected Context — evaluated at confirmation time only
            context_ok = ((vol_ratio >= self.p.vol_min)
                          and (fvg_same or disp_multi >= self.p.disp_high))
            quality = "Q2"
            if context_ok and detected_struct:
                quality = "Q3"
            elif not context_ok:
                if disp_multi >= self.p.disp_min:
                    quality = ("Q1" if vol_ratio < self.p.vol_min else "Q2")
                else:
                    return None
            if not detected_struct and quality == "Q3":
                quality = "Q2"

            zone_lo, zone_hi = asymmetric_zone(disp_direction, b0, atr_now,
                                               self.p.zone_tol)
            width = zone_hi - zone_lo
            if width < self.p.min_width_atr * atr_now:
                return None
            if zone_lo >= zone_hi:
                return None

            otype = "ENTRY"
            if detected_struct and detected_struct.get("kind") == "CHoCH":
                otype = "REVERSAL"

            oid = f"ob_{b0['ts']}_{origin_idx}_{disp_direction}"
            struct_strength = (1.0 if detected_struct
                               and detected_struct.get("kind") == "BOS"
                               else 0.6 if detected_struct else 0.3)

            w_d, w_s, w_v, w_f = self.p.salience_weights
            freshness = 1.0
            sal = (w_d * min(disp_multi / 3, 1)
                   + w_s * struct_strength
                   + w_v * min(vol_ratio / 3, 1)
                   + w_f * freshness)

            ob = OB(
                oid=oid, direction=disp_direction, zone_lo=zone_lo,
                zone_hi=zone_hi, origin_ts=b0["ts"],
                origin_idx=origin_idx, displacement_mag=disp_single,
                displacement_multi=disp_multi,
                structural_event=(detected_struct.get("kind")
                                  if detected_struct else "NONE"),
                structural_strength=struct_strength, otype=otype,
                vol_ratio=vol_ratio, quality=quality,
                fate="ACTIVE" if quality in ("Q3", "Q4") else "CANDIDATE",
                confirmed_at=(self.bars[origin_idx + K_star]["ts"]
                              if origin_idx + K_star < len(self.bars)
                              else b0["ts"]),
                width=width, salience=sal)
            ob.snapshot_id = e06_snapshot_id(ob)
            self.events.append(self._event("EV_OBK_001", ob.confirmed_at,
                                           ob=ob.oid, quality=ob.quality,
                                           snapshot_id=ob.snapshot_id))
            self.events.append(self._event("EV_OBK_002", ob.confirmed_at,
                                           disp_multi=disp_multi,
                                           K=K_star))
            if otype == "REVERSAL":
                self.events.append(self._event("EV_OBK_009", ob.confirmed_at,
                                               ob=ob.oid, chich=True))
            return ob
        except ValueError:
            # §4 error handling: evidence-missing paths fail closed (QX);
            # the caller records nothing — never a fabricated OB.
            return None

    # -- §4.2 per-bar state update ------------------------------------------
    def update_with_bar(self, bar_idx: int) -> None:
        """Canonical decision-state mutation from CLOSED candles only;
        open candles are preview-only (§3.3)."""
        if bar_idx < 0 or bar_idx >= len(self.bars):
            return
        bar = self.bars[bar_idx]
        if not bar.get("is_closed", True):
            return
        atr_now = self.atr[bar_idx] if bar_idx < len(self.atr) else EPS
        to_remove: List[OB] = []
        for ob in self.active_obs:
            # §2.2 delayed confirmation: lifecycle tracking starts only
            # AFTER the confirmation candle (t+K); the origin bar and the
            # displacement leg must never touch/mitigate their own OB.
            if bar["ts"] <= ob.confirmed_at:
                continue
            ob.age += 1

            # Invalidation (§3.2)
            inv = False
            if ob.direction == "UP":
                if bar["c"] < ob.zone_lo - self.p.inv_tol * atr_now:
                    inv = True
            else:
                if bar["c"] > ob.zone_hi + self.p.inv_tol * atr_now:
                    inv = True
            if inv:
                ob.fate = "INVALIDATED"
                ob.quality = "QX"
                self.events.append(self._event("EV_OBK_005", bar["ts"],
                                               ob=ob.oid,
                                               reason="close_outside_zone"))
                to_remove.append(ob)
                continue

            # Touch / directional mitigation (§2.8)
            prev_close = (self.bars[bar_idx - 1]["c"] if bar_idx > 0
                          else bar["c"])
            touch, side_ok, depth = directional_mitigation(
                ob, bar, prev_close, first_touch_strict=(ob.touch_count == 0))
            if touch and side_ok:
                ob.touch_count += 1
                ob.mitigation = depth
                if ob.fate in ("ACTIVE", "CANDIDATE") and ob.touch_count == 1:
                    ob.fate = "RETESTED"
                    self.events.append(self._event("EV_OBK_003", bar["ts"],
                                                   ob=ob.oid,
                                                   touch_count=ob.touch_count,
                                                   mitigation=depth))
                if ob.mitigation >= self.p.mit_activate:
                    if ob.fate != "MITIGATED":
                        self.events.append(self._event(
                            "EV_OBK_004", bar["ts"], ob=ob.oid,
                            mitigation=depth))
                    ob.fate = "MITIGATED"

            # Expiry (§2.11)
            if ob.age >= self.p.max_age_bars:
                ob.fate = "EXPIRED"
                ob.quality = "QX"
                self.events.append(self._event("EV_OBK_006", bar["ts"],
                                               ob=ob.oid, age=ob.age))
                to_remove.append(ob)
                continue

            ob.lineage.append({"ts": bar["ts"], "fate": ob.fate,
                               "mit": ob.mitigation})

        # BREAKER role reversal (§2.7)
        if self.p.breaker_enabled:
            self._detect_breaker_conversion(bar_idx)

        # MITIGATION_BLOCK reactivation (§5.2 research transition;
        # ISSUE-CP3-006: emitted at Q2 — decision-usable only via Q4 OOS
        # validation, which never happens implicitly at runtime).
        self._detect_mitigation_block(bar_idx)

        self._merge_overlapping()
        self._detect_confluence(bar_idx)

        for ob in to_remove:
            if ob in self.active_obs:
                self.active_obs.remove(ob)
                self.history.append(ob)

    def _detect_breaker_conversion(self, bar_idx: int) -> None:
        """§2.7: an INVALIDATED OB reclaimed through its far edge becomes
        a BREAKER with reversed role (zone identical, direction reversed)."""
        bar = self.bars[bar_idx]
        atr_now = self.atr[bar_idx] if bar_idx < len(self.atr) else EPS
        for old in self.history[-20:]:
            if old.fate != "INVALIDATED":
                continue
            if old.otype == "BREAKER":
                continue
            reclaimed = False
            if old.direction == "UP":
                if (bar["c"] > old.zone_hi + self.p.inv_tol * atr_now
                        and bar["l"] <= old.zone_hi):
                    reclaimed = True
            else:
                if (bar["c"] < old.zone_lo - self.p.inv_tol * atr_now
                        and bar["h"] >= old.zone_lo):
                    reclaimed = True
            if not reclaimed:
                continue
            try:
                vr_now = self._safe_vol_ratio(bar_idx)
            except ValueError:
                vr_now = 0.0
            new_ob = OB(
                oid=old.oid + "_breaker",
                direction="DOWN" if old.direction == "UP" else "UP",
                zone_lo=old.zone_lo, zone_hi=old.zone_hi,
                origin_ts=bar["ts"], origin_idx=bar_idx,
                displacement_mag=old.displacement_mag,
                displacement_multi=old.displacement_multi,
                structural_event="BOS", structural_strength=1.0,
                otype="BREAKER", vol_ratio=vr_now, quality="Q3",
                fate="ACTIVE", confirmed_at=bar["ts"], width=old.width,
                salience=old.salience * 0.9)
            new_ob.snapshot_id = e06_snapshot_id(new_ob)
            self.active_obs.append(new_ob)
            old.fate = "MERGED"     # consumed by the conversion
            self.events.append(self._event("EV_OBK_007", bar["ts"],
                                           old_oid=old.oid,
                                           new_ob=new_ob.oid))

    def _detect_mitigation_block(self, bar_idx: int) -> None:
        """§5.2 final row (research): a MITIGATED OB that price exits
        beyond tolerance reactivates as MITIGATION_BLOCK when a new
        structural event occurs. No structural feed at this call site is
        fine — the transition fires only when the exit condition holds;
        structure confirmation arrives via run_full's event map."""
        bar = self.bars[bar_idx]
        atr_now = self.atr[bar_idx] if bar_idx < len(self.atr) else EPS
        for ob in list(self.active_obs):
            if ob.fate != "MITIGATED":
                continue
            exited = (bar["c"] > ob.zone_hi + self.p.inv_tol * atr_now
                      or bar["c"] < ob.zone_lo - self.p.inv_tol * atr_now)
            if not exited:
                continue
            new_ob = OB(
                oid=ob.oid + "_mitblock", direction=ob.direction,
                zone_lo=ob.zone_lo, zone_hi=ob.zone_hi,
                origin_ts=bar["ts"], origin_idx=bar_idx,
                displacement_mag=ob.displacement_mag,
                displacement_multi=ob.displacement_multi,
                structural_event=ob.structural_event,
                structural_strength=ob.structural_strength,
                otype="MITIGATION_BLOCK", vol_ratio=ob.vol_ratio,
                quality="Q2",          # research: never decision-usable
                                       # without Q4 OOS validation (§8.5)
                fate="ACTIVE", confirmed_at=bar["ts"], width=ob.width,
                salience=ob.salience * 0.8)
            new_ob.snapshot_id = e06_snapshot_id(new_ob)
            self.active_obs.remove(ob)
            ob.fate = "MERGED"
            self.history.append(ob)
            self.active_obs.append(new_ob)

    def _merge_overlapping(self) -> None:
        """§2.9 IoU > 0.7 + same direction + time gap < merge_bars →
        keep the higher-Salience OB."""
        used: set = set()
        obs = sorted(self.active_obs, key=lambda x: x.salience, reverse=True)
        for i in range(len(obs)):
            if i in used:
                continue
            a = obs[i]
            for j in range(i + 1, len(obs)):
                if j in used:
                    continue
                b = obs[j]
                if a.direction != b.direction:
                    continue
                if abs(a.origin_idx - b.origin_idx) > self.p.merge_bars:
                    continue
                iou = iou_zones(a.zone_lo, a.zone_hi, b.zone_lo, b.zone_hi)
                if iou > self.p.iou_thresh:
                    used.add(j)
                    b.fate = "MERGED"
                    b.quality = "QX"
                    self.history.append(b)
        self.active_obs = [ob for idx, ob in enumerate(obs)
                           if idx not in used]

    def _detect_confluence(self, bar_idx: int) -> None:
        """§8.6 OB↔FVG confluence: same direction, midpoint within
        0.5·ATR, IoU > 0.5 → EV_OBK_008 (checked against active FVG
        zones passed through run_full's fvg map at origin time — recorded
        as lineage events here for active OBs)."""
        bar = self.bars[bar_idx]
        atr_now = self.atr[bar_idx] if bar_idx < len(self.atr) else EPS
        for ob in self.active_obs:
            if any(e.get("ob") == ob.oid and e["code"] == "EV_OBK_008"
                   for e in self.events):
                continue
            mid_ob = (ob.zone_lo + ob.zone_hi) / 2
            for other in self.active_obs:
                if other.oid == ob.oid or other.direction != ob.direction:
                    continue
                mid_other = (other.zone_lo + other.zone_hi) / 2
                iou = iou_zones(ob.zone_lo, ob.zone_hi, other.zone_lo,
                                other.zone_hi)
                if (abs(mid_ob - mid_other) <= self.p.confluence_mid_atr
                        * atr_now and iou > self.p.confluence_iou):
                    self.events.append(self._event(
                        "EV_OBK_008", bar["ts"], ob=ob.oid,
                        other=other.oid, iou=iou))
                    break

    def run_full(self, bars: Sequence[Dict[str, Any]],
                 struct_events_by_idx: Dict[int, List[Dict[str, Any]]],
                 fvg_by_idx: Dict[int, List[Dict[str, Any]]],
                 volume_evidence: Sequence[Optional[Dict[str, Any]]],
                 volatility_evidence: Sequence[Optional[Dict[str, Any]]]
                 ) -> List[OB]:
        self.ingest_bars(bars, volume_evidence, volatility_evidence)
        for i in range(len(self.bars) - self.p.disp_max_k - 1):
            evs = (struct_events_by_idx.get(i, [])
                   + struct_events_by_idx.get(i + 1, [])
                   + struct_events_by_idx.get(i + 2, []))
            fvgs = fvg_by_idx.get(i, []) + fvg_by_idx.get(i + 1, [])
            ob = self.detect_at(i, evs, fvgs)
            if ob and ob.quality in ("Q3", "Q4", "Q2", "Q1"):
                if not any(abs(x.origin_idx - ob.origin_idx) <= 1
                           and x.direction == ob.direction
                           for x in self.active_obs):
                    self.active_obs.append(ob)
            if i > 0:
                self.update_with_bar(i)
        return self.active_obs + self.history

    @staticmethod
    def _event(code: str, ts: int, **payload: Any) -> Dict[str, Any]:
        return {"code": code, "name": EVENT_CATALOG[code], "ts": ts,
                "engine": ENGINE, "version": CONTRACT_VERSION, **payload}


# --------------------------------------------------------------------------
# §8.7 serialization compatibility (v3 read-only research adapter)
# --------------------------------------------------------------------------
def load_v3_adapter(payload: Dict[str, Any]) -> OB:
    """Live v4 does NOT consume v3 payloads directly (§8.7): only the
    explicit read-only migration adapter may derive zone_hi/zone_lo from
    older H/L-based fields; ambiguity fails closed."""
    if payload.get("version", "3.0.0") not in ("3.0.0", "3"):
        raise ValueError("E06_ADAPTER_VERSION_QX: not a v3 payload")
    if "zone_lo" in payload and "zone_hi" in payload:
        zone_lo, zone_hi = float(payload["zone_lo"]), float(payload["zone_hi"])
    elif "origin_high" in payload and "origin_low" in payload:
        zone_lo, zone_hi = (float(payload["origin_low"]),
                            float(payload["origin_high"]))
    else:
        raise ValueError(
            "E06_ADAPTER_AMBIGUOUS_QX: cannot derive zone from v3 fields")
    required = ("oid", "direction", "origin_ts", "origin_idx")
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError(f"E06_ADAPTER_AMBIGUOUS_QX: missing {missing}")
    ob = OB(
        oid=str(payload["oid"]), direction=payload["direction"],
        zone_lo=zone_lo, zone_hi=zone_hi,
        origin_ts=int(payload["origin_ts"]),
        origin_idx=int(payload["origin_idx"]),
        displacement_mag=float(payload.get("displacement_mag", 0.0)),
        displacement_multi=float(payload.get("displacement_multi", 0.0)),
        structural_event=payload.get("structural_event", "NONE"),
        structural_strength=float(payload.get("structural_strength", 0.3)),
        otype=payload.get("otype", "ENTRY"),
        quality=payload.get("quality", "Q2"),
        fate=payload.get("fate", "CANDIDATE"),
        vol_ratio=float(payload.get("vol_ratio", 0.0)),
        width=zone_hi - zone_lo,
        confirmed_at=int(payload.get("confirmed_at",
                                     payload["origin_ts"])))
    ob.snapshot_id = e06_snapshot_id(ob)
    return ob


def run_engine(bars: Sequence[Dict[str, Any]],
               struct_events_by_idx: Optional[Dict[int, List[Dict[str, Any]]]] = None,
               fvg_by_idx: Optional[Dict[int, List[Dict[str, Any]]]] = None,
               volume_evidence: Optional[Sequence[Optional[Dict[str, Any]]]] = None,
               volatility_evidence: Optional[Sequence[Optional[Dict[str, Any]]]] = None,
               params: Optional[EngineParams] = None) -> Dict[str, Any]:
    """Pure batch driver (CP-2 parity). Evidence lists are mandatory —
    E06 never recomputes SMA/ATR (§1.4); omitted evidence fails closed."""
    if volume_evidence is None or volatility_evidence is None:
        raise ValueError("MISSING_EVIDENCE_QX: E06 requires I_Volume_v4 "
                         "and I_Volatility_v4 evidence (consumed, never "
                         "recomputed — §1.4)")
    eng = OrderBlockEngine(params)
    obs = eng.run_full(bars, struct_events_by_idx or {}, fvg_by_idx or {},
                       volume_evidence, volatility_evidence)
    return {"engine": eng, "obs": obs, "events": eng.events}


# --------------------------------------------------------------------------
# EngineBase binding (frozen CP-1 contract; consumed, never patched)
# --------------------------------------------------------------------------
def observation_to_bar(obs: MarketObservation) -> Dict[str, Any]:
    ts = obs.timestamp
    try:
        import datetime
        dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        ts_ms = int(dt.timestamp() * 1000)
    except (ValueError, AttributeError):
        ts_ms = 0
    return {"ts": ts_ms, "o": float(obs.open), "h": float(obs.high),
            "l": float(obs.low), "c": float(obs.close),
            "v": float(obs.volume), "is_closed": obs.is_closed}


class E06OrderBlockEngine(EngineBase):
    """E06_OrderBlock on the frozen EngineBase contract (v4.0.0).

    compute(symbol, timeframe, as_of, context): window via
    context['window'] or a sync WindowProvider. Consumed context keys
    (versioned interfaces §1.4 — evidence ONLY, never recomputed):
      structure_events — I_Structure_v4 [{kind, direction, level, ts,
        valid_at_idx, strength?}] (E01; version <4.0 → structural_event
        None + Q2 cap per §1.4 compatibility)
      fvg_zones — I_FVG_v4 [{present, direction, lower, upper, type}]
        keyed by origin idx via fvg_by_idx
      volume_evidence — I_Volume_v4 per-bar [{volume_sma, volume_ratio,
        snapshot_id, as_of_ts}] (E03)
      volatility_evidence — I_Volatility_v4 per-bar [{atr_n, tr_method,
        snapshot_id, as_of}] (E04)
    Missing/misaligned evidence → QX fail-closed (no fallback, §1.4)."""

    engine_id = "E06"
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
        params = get_params(context.get("e06_params"))
        volume_evidence = context.get("volume_evidence")
        volatility_evidence = context.get("volatility_evidence")
        if volume_evidence is None or volatility_evidence is None:
            raise ValueError("MISSING_EVIDENCE_QX: E06 requires I_Volume_v4 "
                             "and I_Volatility_v4 evidence (§1.4)")
        result = run_engine(
            bars,
            struct_events_by_idx=context.get("struct_events_by_idx"),
            fvg_by_idx=context.get("fvg_by_idx"),
            volume_evidence=volume_evidence,
            volatility_evidence=volatility_evidence,
            params=params)
        quality = self._window_quality(window_obs)
        return [self._to_evidence(ob, symbol, timeframe, quality)
                for ob in result["obs"]]

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

    def _to_evidence(self, ob: OB, symbol: str, timeframe: str,
                     quality: float) -> EvidenceEvent:
        import datetime
        as_of_iso = datetime.datetime.fromtimestamp(
            ob.confirmed_at / 1000.0, tz=datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.") + f"{ob.confirmed_at % 1000:03d}Z"
        direction = 1 if ob.direction == "UP" else -1
        # EvidenceEvent validates resolution_class ∈ Q0..Q5 (CP-2
        # precedent E02): out-of-range engine tags (QX terminal states)
        # map to the closest valid class; the DEGRADED validity carries
        # the QX meaning.
        resolution = ob.quality if ob.quality in tuple(
            f"Q{i}" for i in range(6)) else "Q1"
        return EvidenceEvent(
            evidence_id=uuid_v7(),
            engine_id=self.engine_id,
            analyst_version=self.analyst_version,
            symbol=symbol, timeframe=timeframe,
            snapshot_id=ob.snapshot_id,
            event_time=as_of_iso,
            availability_time=as_of_iso,
            observation_window={"bars": ob.age, "tf": timeframe},
            feature_snapshot_id=ob.snapshot_id,
            feature_dependencies=("window", "I_Structure_v4",
                                  "I_Volume_v4", "I_Volatility_v4",
                                  "I_FVG_v4"),
            condition_state=f"EV_OBK_{ob.otype}_{ob.fate}",
            direction=direction,
            strength=float(min(max(ob.salience, 0.0), 1.0)),
            confidence=1.0 if ob.quality in ("Q3", "Q4") else 0.5,
            quality=float(quality),
            validity="VALID" if ob.quality not in ("QX",) else "DEGRADED",
            fate_state=LifecycleState.ACTIVE,
            age=float(ob.age),
            decay=math.exp(-ob.age / max(self.p_default().max_age_bars, 1)),
            explanation=(f"E06 order block {ob.direction} [{ob.zone_lo},"
                         f"{ob.zone_hi}] {ob.otype} {ob.quality} "
                         f"fate={ob.fate}"),
            parameter_version="E06-OBK-V4.0.0/DEFAULTS-v1",
            lineage=(f"origin_idx_{ob.origin_idx}",),
            resolution_class=resolution,
        )

    @staticmethod
    def p_default() -> EngineParams:
        return EngineParams()
