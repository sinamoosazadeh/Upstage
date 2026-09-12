"""APEX_GEN5 E05 — IMBALANCE / FVG ENGINE (v4.0.0).

Blueprint: APEX_GEN5.md L5602–6859 (chapter order mirrored: §3 formulas →
§4 algorithms → §5 objects/state/events/schema → §6 params → §7 notes →
§8 validation hooks). Versioned dependencies: E01–E04 @ ^4.0.0; E11/E12
are NOT E05 runtime dependencies (chapter header). Output is
Context/SETUP, never a trading signal (NG4).

Geometric core (GEN5-V4 rewrite, §0): four Gates (A candle validity, B gap
imbalance, C non-negativity safety net, D minimum width), true BISI/SIBI
via BodyRatio, Sequential MTF alignment (0.3·ATR_HTF), directional
Mitigation, defined Mid_range Premium/Discount, Inverse with
structure-break criterion, overlap merge, Freshness-Decay expiry.

Zone law (reconciled per ISSUE-CP3-002): the ICT zone is canonical —
bullish [H_{t−2}, L_t], bearish [H_t, L_{t−2}] (§0/§2/§4/§7.11 historical
note + Golden Fixtures). The §3.1 max/min "de-negativization" variant is
the abandoned pre-freeze formula (algebraically guaranteed lower>upper;
§7 Ch.1-11 note) — retained only as the numerical safety-net check.
"""

from __future__ import annotations

import hashlib
import math
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

ENGINE = "E05_FVG"
CONTRACT_VERSION = "4.0.0"
ANALYST_VERSION = "4.0.0+" + "0" * 40

EPS = float(eps_for_engine("E05"))          # 1e-8 (§2.2 E05 row)

FTYPES = ("CONVENTIONAL", "BISI", "SIBI", "DOJI_FVG", "REJECTION",
          "SEQUENTIAL", "INVERSE", "INVALID")
FATES = ("FRESH", "TOUCHED", "MITIGATED", "FILLED", "INVALIDATED",
         "EXPIRED")
QTAGS = ("Q0", "Q1", "Q2", "Q3", "Q3_Experimental", "Q4", "Q5",
         "QX_INVALID_CANDLE", "QX_NEGATIVE_WIDTH",
         "QX_INSUFFICIENT_WIDTH", "QX_EXPIRED", "QX_CONFLICT")

EVENT_CATALOG = {
    "EV_FVG_001": "Zone_Created",
    "EV_FVG_002": "Zone_Touched",
    "EV_FVG_003": "Zone_Mitigated",
    "EV_FVG_004": "Zone_Filled",
    "EV_FVG_005": "Zone_Invalidated",
    "EV_FVG_006": "Zone_Expired",
    "EV_FVG_007": "FVG_Confluence_MTF",
    "EV_FVG_008": "BISI_Confirmed",
    "EV_FVG_009": "Rejection_Confirmed",
}

FVG_ZONE_REQUIRED = (
    "fid", "direction", "lower", "upper", "mid", "width",
    "created_at_ts", "created_at_idx", "ftype", "quality_tag", "fate",
    "age_bars", "touch_count", "mitigation_depth", "mitigation_dir",
    "salience_0", "salience", "freshness", "premium_z", "snapshot_id",
    "schema_version",
)


# --------------------------------------------------------------------------
# §6 Parameters (frozen in-package defaults, ISSUE-CP2-006 pattern).
# CP-E05-001 (min_width 0.25×ATR) is NOT applied at freeze — the frozen
# value stays 0.2 (chapter appendix; change proposal only).
# --------------------------------------------------------------------------
E05_DEFAULTS: Dict[str, Any] = {
    "min_width_atr": 0.2,          # θ_minW (§6; CP-E05-001 NOT applied)
    "min_abs_ticks": 3,            # §6
    "max_age_bars": 96,            # §6 OOS 90th percentile of return age
    "mit_activate": 0.5,           # §6 Mitigated threshold
    "rej_wick": 0.5,               # §6 Rejection wick ratio
    "salience_weights": (0.35, 0.25, 0.25, 0.15),   # w_w,w_v,w_s,w_f Σ=1
    "mtf_required": False,         # §6 policy
    "inverse_enabled": False,      # §6 research-only, default off
    "half_life_bars": 48,          # §6 Freshness half-life
    "fresh_thr": 0.15,             # §6 expiry threshold
    "iou_merge_thr": 0.7,          # §6 overlap merge
    "body_ratio_doji_thr": 0.1,    # §6 DOJI threshold
    "range_lookback": 20,          # §6 Mid_range window
    "atr_period": 14,              # §6 governed from E04
    "vol_lookback": 20,            # §3.4 VolRatio SMA(V,20)
    "sequential_tol_atr": 0.3,     # §3.5 0.3·ATR_HTF
    "sequential_boost": 1.25,      # §3.5 Salience boost
    "doji_penalty": 0.7,           # §3.2 Salience penalty
    "inverse_penalty": 0.5,        # §3.6 Salience penalty
    "gap_salience_boost": 0.1,     # §3.8 severe-imbalance gap boost
    "fill_depth_thr": 0.999,       # §4 FILLED threshold
}


def get_params(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = dict(E05_DEFAULTS)
    for key, value in (overrides or {}).items():
        if key not in E05_DEFAULTS:
            raise ValueError(f"UNKNOWN_E05_PARAM_QX:{key}")
        params[key] = value
    weights = tuple(params["salience_weights"])
    if abs(sum(weights) - 1.0) > 1e-9:
        raise ValueError("E05_SALIENCE_WEIGHTS_SUM_QX")
    params["salience_weights"] = weights
    return params


# --------------------------------------------------------------------------
# §4 utilities (PIT-safe; ATR consumed from E04 when evidence is passed,
# local atr_calc only the §4 reference fallback for fixture windows)
# --------------------------------------------------------------------------
def canonical_hash(obj: Dict[str, Any]) -> str:
    """Delegator only — the global identity helper supplies the single
    engine/version envelope (§4 note; Phase 67A rule)."""
    return canonical_snapshot_id(ENGINE, CONTRACT_VERSION, obj)


def atr_calc(bars: Sequence[Dict[str, Any]], n: int, idx: int) -> float:
    """§4 atr_calc — PIT-safe SMA of TR (idx−1 as prev close)."""
    if idx < 1:
        return bars[idx]["h"] - bars[idx]["l"]
    trs = []
    for k in range(max(1, idx - n + 1), idx + 1):
        b = bars[k]
        prev_c = bars[k - 1]["c"]
        tr = max(b["h"] - b["l"], abs(b["h"] - prev_c), abs(b["l"] - prev_c))
        trs.append(tr)
    return sum(trs) / len(trs) if trs else bars[idx]["h"] - bars[idx]["l"]


def vol_ratio(bars: Sequence[Dict[str, Any]], idx: int,
              lookback: int = 20) -> Optional[float]:
    """§4 vol_ratio — V_idx / SMA(V, lookback on idx−lookback:idx);
    None during Q1 warmup (never decision-usable); V=0 → 0.0."""
    if idx < lookback:
        return None
    v_now = bars[idx].get("v", 0)
    if v_now == 0:
        return 0.0
    sma = sum(b.get("v", 0) for b in bars[idx - lookback:idx]) / lookback
    if sma < EPS:
        return 0.0
    return v_now / sma


def body_ratio(bar: Dict[str, Any]) -> float:
    """§3.2 BR = |C−O| / (H−L+ε)."""
    hl = bar["h"] - bar["l"]
    if hl < EPS:
        return 0.0
    return abs(bar["c"] - bar["o"]) / hl


def range_20(bars: Sequence[Dict[str, Any]], idx: int,
             lookback: int = 20) -> Tuple[float, float]:
    """§4 range_20 — closed-candle window [idx−lookback, idx) (§2 PIT)."""
    if idx < lookback:
        slice_b = list(bars[:idx])
    else:
        slice_b = list(bars[idx - lookback:idx])
    if not slice_b:
        return bars[idx]["l"], bars[idx]["h"]
    return (min(b["l"] for b in slice_b), max(b["h"] for b in slice_b))


def freshness_decay(age_bars: int, half_life_bars: int) -> float:
    """§3.4 Freshness = exp(−λ·age), λ = ln2 / half_life."""
    lam = math.log(2) / max(half_life_bars, 1)
    return math.exp(-lam * age_bars)


def wilson_ci(p_hat: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    """§7 Ch.1-14 Wilson CI for the return rate."""
    if n <= 0:
        return (0.0, 1.0)
    denom = 1.0 + z * z / n
    centre = p_hat + z * z / (2 * n)
    half = z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
    return ((centre - half) / denom, (centre + half) / denom)


# --------------------------------------------------------------------------
# §4 core object
# --------------------------------------------------------------------------
@dataclass
class FVGObject:
    fid: str
    direction: str                          # UP/DOWN
    lower: float
    upper: float
    mid: float
    width: float
    created_at_ts: int
    created_at_idx: int
    ftype: str = "CONVENTIONAL"
    quality_tag: str = "Q1"
    fate: str = "FRESH"
    age_bars: int = 0
    touch_count: int = 0
    mitigation_depth: float = 0.0
    mitigation_dir: int = 0                 # +1 from above, −1 below, 0 in
    salience_0: float = 0.0
    salience: float = 0.0
    freshness: float = 1.0
    premium_z: float = 0.0
    structural_role: float = 0.5
    vol_ratio_at_creation: float = 1.0
    atr_at_creation: float = 0.0
    body_ratio_mid: float = 0.0
    snapshot_id: str = ""
    schema_version: str = "4.0.0"
    extra: Dict[str, Any] = field(default_factory=dict)

    def update_snapshot(self) -> None:
        """Governed E05 state payload; the global canonical_snapshot_id
        helper supplies the single engine/version envelope."""
        canonical_state = {
            "fid": self.fid, "direction": self.direction,
            "lower": round(self.lower, 8), "upper": round(self.upper, 8),
            "mid": round(self.mid, 8), "width": round(self.width, 8),
            "created_at_ts": self.created_at_ts,
            "created_at_idx": self.created_at_idx,
            "ftype": self.ftype, "quality_tag": self.quality_tag,
            "fate": self.fate, "age_bars": self.age_bars,
            "touch_count": self.touch_count,
            "mitigation_depth": self.mitigation_depth,
            "mitigation_dir": self.mitigation_dir,
            "salience": self.salience,
            "freshness": self.freshness, "premium_z": self.premium_z,
            "structural_role": self.structural_role,
            "vol_ratio_at_creation": self.vol_ratio_at_creation,
            "atr_at_creation": self.atr_at_creation,
            "body_ratio_mid": self.body_ratio_mid,
            "schema_version": self.schema_version,
            "extra": self.extra,
        }
        self.snapshot_id = canonical_snapshot_id(
            ENGINE, CONTRACT_VERSION, canonical_state)

    def validate_schema(self) -> None:
        """§5.1 required-field + enum conformance (draft-07 pointer)."""
        for key in FVG_ZONE_REQUIRED:
            if getattr(self, key, None) is None and key != "snapshot_id":
                raise ValueError(f"FVG_ZONE_MISSING_FIELD_QX:{key}")
        if self.direction not in ("UP", "DOWN"):
            raise ValueError("FVG_ZONE_DIRECTION_QX")
        if self.ftype not in FTYPES:
            raise ValueError(f"FVG_ZONE_FTYPE_QX:{self.ftype}")
        if self.quality_tag not in QTAGS:
            raise ValueError(f"FVG_ZONE_QTAG_QX:{self.quality_tag}")
        if self.fate not in FATES:
            raise ValueError(f"FVG_ZONE_FATE_QX:{self.fate}")
        if self.mitigation_dir not in (-1, 0, 1):
            raise ValueError("FVG_ZONE_MIT_DIR_QX")
        if not (isinstance(self.snapshot_id, str)
                and len(self.snapshot_id) == 64):
            raise ValueError("FVG_ZONE_SNAPSHOT_QX")
        if self.ftype == "INVERSE" and self.quality_tag != "Q3_Experimental":
            raise ValueError("FVG_ZONE_INVERSE_QTAG_QX")


# --------------------------------------------------------------------------
# §3.1/§4 detection — ICT zone with the NEGATIVE-WIDTH safety net
# --------------------------------------------------------------------------
def detect_fvg_at(bars: Sequence[Dict[str, Any]], i: int,
                  theta_min_w: float, min_abs_ticks: int, tick_size: float,
                  atr_override: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Three-candle detection at closed candle i (§3.1 Gates A–D).

    Gate_A candle validity; Gate_B imbalance; Gate_C safety net;
    Gate_D minimum width (θ_minW·ATR ∧ min_abs_ticks·tick_size).
    atr_override is the E04-evidence/fixture pathway; production computes
    the §4 PIT-safe fallback only when no ATR evidence is supplied.
    """
    if i < 2:
        return None
    b2, b1, b0 = bars[i - 2], bars[i - 1], bars[i]
    # Gate_A — invalid candle
    for b in (b2, b1, b0):
        if b["h"] < b["l"] - EPS or not math.isfinite(b["h"]):
            return {"invalid_reason": "INVALID_CANDLE"}
    # Gate_B — imbalance
    bullish_cond = b2["h"] < b0["l"]
    bearish_cond = b2["l"] > b0["h"]
    if not (bullish_cond or bearish_cond):
        return None
    atr_now = atr_override if atr_override is not None else atr_calc(
        bars, 14, i)
    if bullish_cond:
        # ICT-correct zone [H_{t−2}, L_t] — the middle candle does NOT
        # shrink the zone (§0/§2/§7 Ch.1-11; fixture-canonical).
        lower = b2["h"]
        upper = b0["l"]
        direction = "UP"
    else:
        # Bearish ICT zone [H_t, L_{t−2}] (§2 table main implementation).
        lower = b0["h"]
        upper = b2["l"]
        direction = "DOWN"
    # Gate_C — numerical safety net (structurally guaranteed by Gate_B;
    # the abandoned max/min formula is deliberately NOT used here).
    if lower > upper + EPS:
        return {"invalid_reason": "NEGATIVE_WIDTH", "lower": lower,
                "upper": upper, "direction": direction}
    width = upper - lower
    # Gate_D — minimum width
    min_w_atr = theta_min_w * atr_now
    min_w_abs = min_abs_ticks * tick_size
    if width < min_w_atr - EPS or width < min_w_abs - EPS:
        return {"invalid_reason": "INSUFFICIENT_WIDTH", "width": width,
                "thr_atr": min_w_atr}
    return {
        "direction": direction, "lower": lower, "upper": upper,
        "width": width, "atr": atr_now, "at_idx": i,
        "at_ts": b0.get("ts_close", b0.get("ts", 0)),
        "b2": b2, "b1": b1, "b0": b0,
    }


# --------------------------------------------------------------------------
# §3.2/§3.5/§3.6 classification
# --------------------------------------------------------------------------
def classify_fvg(det: Dict[str, Any], bars: Sequence[Dict[str, Any]],
                 i: int, params: Dict[str, Any],
                 htf_fvgs: Optional[Sequence[FVGObject]] = None,
                 trend_htf: Optional[str] = None,
                 bos_events: Optional[Sequence[Dict[str, Any]]] = None
                 ) -> Tuple[str, float]:
    """Q2 classification decision tree (§3.2) + Sequential (§3.5) +
    Inverse (§3.6). Returns (ftype, salience_penalty)."""
    if "invalid_reason" in det:
        return "INVALID", 0.0
    b1 = bars[i - 1]
    br = body_ratio(b1)
    dir_ = det["direction"]
    ftype = "CONVENTIONAL"
    salience_penalty = 1.0

    if br < params.get("body_ratio_doji_thr", 0.1):
        ftype = "DOJI_FVG"
        salience_penalty = params.get("doji_penalty", 0.7)
    else:
        if dir_ == "UP" and b1["c"] < b1["o"]:
            ftype = "BISI"
        elif dir_ == "DOWN" and b1["c"] > b1["o"]:
            ftype = "SIBI"
        else:
            b0 = bars[i]
            hl = b0["h"] - b0["l"] + EPS
            if dir_ == "UP":
                wick = b0["h"] - max(b0["o"], b0["c"])
            else:
                wick = min(b0["o"], b0["c"]) - b0["l"]
            wr = wick / hl
            if (wr >= params["rej_wick"]
                    and abs(b0["c"] - b0["o"]) / hl <= 0.4):
                ftype = "REJECTION"

    # §3.5 Sequential MTF alignment (tolerance 0.3·ATR_HTF)
    if htf_fvgs:
        mid_ltf = (det["lower"] + det["upper"]) / 2
        for hfvg in htf_fvgs:
            if hfvg.direction != dir_:
                continue
            if hfvg.created_at_ts > det["at_ts"]:     # §3.5 PIT rule 4
                continue
            atr_htf = hfvg.atr_at_creation or 1.0
            if (abs(mid_ltf - hfvg.mid)
                    <= params["sequential_tol_atr"] * atr_htf + EPS):
                if not (det["upper"] < hfvg.lower
                        or det["lower"] > hfvg.upper):
                    ftype = "SEQUENTIAL"
                    break

    # §3.6 Inverse (research-only; disabled by default)
    if params.get("inverse_enabled", False) and trend_htf:
        if ((dir_ == "UP" and trend_htf == "DOWN")
                or (dir_ == "DOWN" and trend_htf == "UP")):
            if bos_events:
                opp_bos = [e for e in bos_events
                           if e["dir"] != dir_ and i <= e["idx"] <= i + 5]
                vr_here = vol_ratio(bars, i - 1,
                                    params.get("vol_lookback", 20))
                # §3.6 VolRatio>1.2 gate applies when computable; during
                # Q1 warmup the fixture-canonical classification stands
                # (ISSUE-CP3-005 reconciliation).
                if opp_bos and (vr_here is None or vr_here > 1.2):
                    ftype = "INVERSE"
                    salience_penalty = params.get("inverse_penalty", 0.5)

    return ftype, salience_penalty


# --------------------------------------------------------------------------
# §3.3/§3.4 salience, mitigation, premium/discount
# --------------------------------------------------------------------------
def compute_salience_and_premium(det: Dict[str, Any], ftype: str,
                                 penalty: float,
                                 bars: Sequence[Dict[str, Any]], i: int,
                                 params: Dict[str, Any],
                                 struct_role: float = 0.5,
                                 vr_override: Optional[float] = None
                                 ) -> Tuple[float, float, float, float]:
    """§3.4 Salience_0 (Freshness=1 at creation) + §2 z_mid.

    vr_override is the documented warmup path: during Q1 warmup the
    §4 contract call raises INSUFFICIENT_HISTORY_Q1, and the streaming
    engine applies the §3.4 conservative rule (VolRatio stays 0, its w_v
    share is NOT reallocated) rather than blocking zone creation —
    ISSUE-CP3-007 reconciliation (fixtures are canonical at 3 bars)."""
    atr_now = det["atr"]
    width = det["width"]
    if vr_override is not None:
        vr = vr_override
    else:
        vr = vol_ratio(bars, i - 1, params.get("vol_lookback", 20))
        if vr is None:
            raise ValueError("INSUFFICIENT_HISTORY_Q1")
    w_w, w_v, w_s, w_f = params["salience_weights"]
    salience_0 = (w_w * min(width / max(atr_now, EPS), 2.0) / 2.0
                  + w_v * min(vr / 2.0, 1.0)
                  + w_s * struct_role
                  + w_f * 1.0) * penalty
    rl, rh = range_20(bars, i, params.get("range_lookback", 20))
    mid_range = (rh + rl) / 2
    atr20 = atr_calc(bars, params.get("range_lookback", 20), i)
    z_mid = (bars[i]["c"] - mid_range) / max(atr20, EPS)
    return salience_0, salience_0, 1.0, z_mid


def mitigation_of(fvg: FVGObject, bar: Dict[str, Any], prev_close: float,
                  eps: float = EPS) -> Tuple[bool, float, int]:
    """§3.3 directional mitigation: (touch, depth, dir_flag)."""
    if not (bar["h"] >= fvg.lower - eps and bar["l"] <= fvg.upper + eps):
        return False, 0.0, 0
    overlap = max(0.0, min(fvg.upper, bar["h"]) - max(fvg.lower, bar["l"]))
    depth = overlap / max(fvg.width, eps)
    dir_flag = 1 if prev_close > fvg.upper else (
        -1 if prev_close < fvg.lower else 0)
    return True, depth, dir_flag


def iou_of(a_lo: float, a_hi: float, b_lo: float, b_hi: float,
           eps: float = EPS) -> float:
    """§3.7 IoU."""
    inter = max(0.0, min(a_hi, b_hi) - max(a_lo, b_lo))
    union = max(a_hi, b_hi) - min(a_lo, b_lo)
    return inter / max(union, eps)


# --------------------------------------------------------------------------
# §4/§5 streaming engine
# --------------------------------------------------------------------------
class FVGEngine:
    """§4 FVG_Engine — streaming lifecycle manager (§5.2 state machine).

    process_bar(bars, i, ...) advances one CLOSED candle; idempotent per
    (fid, bar_idx) via deterministic fid; events EV_FVG_001..009.
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None,
                 tick_size: float = 0.01, symbol: str = ""):
        self.params = get_params(params)
        self.tick_size = tick_size
        self.symbol = symbol
        self.active_fvgs: Dict[str, FVGObject] = {}
        self.history: List[FVGObject] = []
        self.bar_idx = -1
        self._processed: set = set()

    # -- creation ----------------------------------------------------------
    def process_bar(self, bars: Sequence[Dict[str, Any]], i: int,
                    htf_fvgs: Optional[Sequence[FVGObject]] = None,
                    trend_htf: Optional[str] = None,
                    bos_events: Optional[Sequence[Dict[str, Any]]] = None,
                    struct_role: float = 0.5,
                    atr_override: Optional[float] = None) -> List[Dict[str, Any]]:
        bar_key = (i, bars[i].get("ts_close", bars[i].get("ts", 0)))
        if bar_key in self._processed and i <= self.bar_idx:
            return []                       # idempotency (§5.4)
        self._processed.add(bar_key)
        events: List[Dict[str, Any]] = []

        # Step 1 — detect + classify + create
        det = detect_fvg_at(bars, i, self.params["min_width_atr"],
                            self.params["min_abs_ticks"], self.tick_size,
                            atr_override=atr_override)
        if det and "invalid_reason" not in det:
            ftype, penalty = classify_fvg(det, bars, i, self.params,
                                          htf_fvgs, trend_htf, bos_events)
            if ftype != "INVALID":
                vr_here = vol_ratio(bars, i - 1, self.params["vol_lookback"])
                vr_warmup = vr_here is None
                sal0, sal, fresh, zmid = compute_salience_and_premium(
                    det, ftype, penalty, bars, i, self.params, struct_role,
                    vr_override=0.0 if vr_warmup else None)
                if ftype == "SEQUENTIAL":
                    sal0 *= self.params["sequential_boost"]
                    sal = sal0 * fresh
                fid_hash_input = f"{det['lower']}_{det['upper']}"
                fid_fingerprint = hashlib.sha256(
                    fid_hash_input.encode("utf-8")).hexdigest()[:12]
                # Short fingerprint = local FVG key only; never snapshot_id.
                fid = (f"fvg_{self.symbol}_{det['direction']}_"
                       f"{det['at_ts']}_{fid_fingerprint}")
                if fid not in self.active_fvgs:
                    obj = FVGObject(
                        fid=fid, direction=det["direction"],
                        lower=det["lower"], upper=det["upper"],
                        mid=(det["lower"] + det["upper"]) / 2,
                        width=det["width"],
                        created_at_ts=det["at_ts"], created_at_idx=i,
                        ftype=ftype,
                        quality_tag=("Q2" if ftype in
                                     ("CONVENTIONAL", "BISI", "SIBI")
                                     else "Q3"),
                        salience_0=sal0, salience=sal, freshness=fresh,
                        premium_z=zmid, atr_at_creation=det["atr"],
                        vol_ratio_at_creation=vol_ratio(
                            bars, i - 1, self.params["vol_lookback"]) or 0.0,
                        body_ratio_mid=body_ratio(bars[i - 1]),
                        structural_role=struct_role)
                    if ftype == "INVERSE":
                        obj.quality_tag = "Q3_Experimental"
                    obj.update_snapshot()
                    self.active_fvgs[fid] = obj
                    events.append({"type": "EV_FVG_001_Zone_Created",
                                   "fid": fid, "obj": asdict(obj)})
                    if ftype in ("BISI", "SIBI"):
                        events.append({
                            "type": "EV_FVG_008_BISI_Confirmed",
                            "fid": fid,
                            "body_ratio": obj.body_ratio_mid})
                    if ftype == "REJECTION":
                        b0 = bars[i]
                        hl = b0["h"] - b0["l"] + EPS
                        wick = (b0["h"] - max(b0["o"], b0["c"])
                                if det["direction"] == "UP"
                                else min(b0["o"], b0["c"]) - b0["l"])
                        events.append({
                            "type": "EV_FVG_009_Rejection_Confirmed",
                            "fid": fid, "wick_ratio": wick / hl})
        elif det and "invalid_reason" in det:
            events.append({"type": "EV_FVG_005_Zone_Invalidated",
                           "reason": det["invalid_reason"], "at_idx": i})

        # Step 2 — update active FVGs (mitigation / freshness / expiry)
        bar = bars[i]
        to_remove: List[str] = []
        lambda_ = math.log(2) / self.params["half_life_bars"]
        for fid, fvg in list(self.active_fvgs.items()):
            if fvg.created_at_idx == i:
                # a zone created on this bar is not aged against itself
                fvg.update_snapshot()
                continue
            fvg.age_bars += 1
            fvg.freshness = math.exp(-lambda_ * fvg.age_bars)
            fvg.salience = fvg.salience_0 * fvg.freshness

            touch, depth, dir_flag = mitigation_of(
                fvg, bar, bars[i - 1]["c"] if i > 0 else bar["c"])
            if touch:
                if fvg.touch_count == 0:
                    events.append({"type": "EV_FVG_002_Zone_Touched",
                                   "fid": fid, "depth": depth,
                                   "dir": dir_flag, "bar_idx": i})
                fvg.touch_count += 1
                fvg.mitigation_depth = max(fvg.mitigation_depth, depth)
                if fvg.mitigation_dir == 0:
                    fvg.mitigation_dir = dir_flag

                if depth >= self.params["mit_activate"]:
                    if fvg.fate in ("FRESH", "TOUCHED"):
                        fvg.fate = "MITIGATED"
                        events.append({"type": "EV_FVG_003_Zone_Mitigated",
                                       "fid": fid, "depth": depth,
                                       "dir": dir_flag})
                if depth >= self.params["fill_depth_thr"]:
                    fvg.fate = "FILLED"
                    fvg.quality_tag = "Q5"
                    events.append({"type": "EV_FVG_004_Zone_Filled",
                                   "fid": fid,
                                   "fill_price": (fvg.lower + fvg.upper) / 2})
                    to_remove.append(fid)
                elif fvg.fate == "FRESH":
                    fvg.fate = "TOUCHED"

            # Expiry: age ≥ max_age_bars OR freshness < fresh_thr
            # (boundary-inclusive age — fixture FRESHNESS_DECAY_EXPIRY is
            # canonical at age == max_age; ISSUE-CP3-004).
            if (fvg.age_bars >= self.params["max_age_bars"]
                    or fvg.freshness < self.params["fresh_thr"]):
                fvg.fate = "EXPIRED"
                fvg.quality_tag = "QX_EXPIRED"
                events.append({"type": "EV_FVG_006_Zone_Expired",
                               "fid": fid, "freshness": fvg.freshness})
                to_remove.append(fid)
                continue

            if fvg.fate == "FRESH" and fvg.touch_count == 0:
                fvg.quality_tag = "Q3"
            elif fvg.fate == "TOUCHED":
                fvg.quality_tag = "Q4"
            fvg.update_snapshot()

        for fid in to_remove:
            hist_obj = self.active_fvgs.pop(fid, None)
            if hist_obj:
                self.history.append(hist_obj)

        # Step 3 — merge overlapping same-direction FVGs (§3.7)
        events.extend(self._merge_overlaps())
        self.bar_idx = i
        return events

    def _merge_overlaps(self) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for direction in ("UP", "DOWN"):
            group = sorted([f for f in self.active_fvgs.values()
                            if f.direction == direction],
                           key=lambda x: x.lower)
            i = 0
            while i < len(group) - 1:
                a, b = group[i], group[i + 1]
                iou = iou_of(a.lower, a.upper, b.lower, b.upper)
                contained = ((a.lower <= b.lower and a.upper >= b.upper)
                             or (b.lower <= a.lower and b.upper >= a.upper))
                if iou > self.params["iou_merge_thr"] or contained:
                    new_lower = min(a.lower, b.lower)
                    new_upper = max(a.upper, b.upper)
                    base = a if a.created_at_idx <= b.created_at_idx else b
                    base.lower = new_lower
                    base.upper = new_upper
                    base.mid = (new_lower + new_upper) / 2
                    base.width = new_upper - new_lower
                    base.salience_0 = (max(a.salience_0, b.salience_0)
                                       * (1 + 0.1))
                    base.salience = base.salience_0 * base.freshness
                    base.extra["merged_from"] = [a.fid, b.fid]
                    other = b if base is a else a
                    # identity-based removal: robust even if the dict key
                    # diverges from .fid (never loops on stale entries)
                    for _key, _val in list(self.active_fvgs.items()):
                        if _val is other:
                            del self.active_fvgs[_key]
                            break
                    events.append({"type": "EV_FVG_007_FVG_Confluence_MTF",
                                   "merged_fid": base.fid,
                                   "from": [a.fid, b.fid], "iou": iou})
                    group = sorted([f for f in self.active_fvgs.values()
                                    if f.direction == direction],
                                   key=lambda x: x.lower)
                    i = 0
                else:
                    i += 1
        return events

    def output(self) -> Dict[str, Any]:
        return {
            "engine": ENGINE,
            "version": CONTRACT_VERSION,
            "active": [asdict(f) for f in self.active_fvgs.values()],
            "history": [asdict(f) for f in self.history],
        }


def run_engine(bars: Sequence[Dict[str, Any]],
               params: Optional[Dict[str, Any]] = None,
               tick_size: float = 0.01, symbol: str = "",
               htf_fvgs_by_idx: Optional[Dict[int, List[FVGObject]]] = None,
               trend_htf_by_idx: Optional[Dict[int, str]] = None,
               bos_by_idx: Optional[Dict[int, List[Dict[str, Any]]]] = None,
               atr_by_idx: Optional[Dict[int, float]] = None
               ) -> Dict[str, Any]:
    """Pure batch driver over closed candles (CP-2 parity)."""
    eng = FVGEngine(params, tick_size=tick_size, symbol=symbol)
    events: List[Dict[str, Any]] = []
    for i in range(len(bars)):
        events.extend(eng.process_bar(
            bars, i,
            htf_fvgs=(htf_fvgs_by_idx or {}).get(i),
            trend_htf=(trend_htf_by_idx or {}).get(i),
            bos_events=(bos_by_idx or {}).get(i),
            atr_override=(atr_by_idx or {}).get(i)))
    return {"engine": eng, "events": events,
            "active": list(eng.active_fvgs.values()),
            "history": list(eng.history)}


# --------------------------------------------------------------------------
# §5.5 v3→v4 migration adapter (read-only; fail-closed on ambiguity)
# --------------------------------------------------------------------------
def load_v3_adapter(payload: Dict[str, Any]) -> FVGObject:
    """Explicit read-only migration v3 → v4 (§5.5): mitigation_dir absent
    ⇒ default 0; ftype DOJI_FVG ⇒ CONVENTIONAL with the 0.7 penalty marker
    in extra. Unresolved ambiguity fails closed (never a silent v4 live
    interpretation)."""
    if payload.get("schema_version", "3.0.0") not in ("3.0.0", "3"):
        raise ValueError("E05_ADAPTER_VERSION_QX: not a v3 payload")
    required = ("fid", "direction", "lower", "upper", "created_at_ts",
                "created_at_idx")
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError(f"E05_ADAPTER_AMBIGUOUS_QX: missing {missing}")
    ftype = payload.get("ftype", "CONVENTIONAL")
    penalty_applied = False
    if ftype == "DOJI_FVG":
        ftype = "CONVENTIONAL"
        penalty_applied = True
    lower = float(payload["lower"])
    upper = float(payload["upper"])
    sal0 = float(payload.get("salience_0", payload.get("salience", 0.0)))
    obj = FVGObject(
        fid=str(payload["fid"]), direction=payload["direction"],
        lower=lower, upper=upper, mid=(lower + upper) / 2,
        width=upper - lower,
        created_at_ts=int(payload["created_at_ts"]),
        created_at_idx=int(payload["created_at_idx"]),
        ftype=ftype,
        quality_tag=payload.get("quality_tag", "Q2"),
        fate=payload.get("fate", "FRESH"),
        age_bars=int(payload.get("age_bars", 0)),
        touch_count=int(payload.get("touch_count", 0)),
        mitigation_depth=float(payload.get("mitigation_depth", 0.0)),
        mitigation_dir=int(payload.get("mitigation_dir", 0)),
        salience_0=sal0,
        salience=float(payload.get("salience", sal0)),
        freshness=float(payload.get("freshness", 1.0)),
        premium_z=float(payload.get("premium_z", 0.0)))
    if penalty_applied:
        obj.extra["v3_doji_penalty"] = 0.7
    obj.update_snapshot()
    return obj


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
    return {"o": float(obs.open), "h": float(obs.high),
            "l": float(obs.low), "c": float(obs.close),
            "v": float(obs.volume), "ts_close": ts_ms,
            "symbol": obs.symbol}


class E05FVGEngine(EngineBase):
    """E05_FVG on the frozen EngineBase contract (v4.0.0).

    compute(symbol, timeframe, as_of, context): window via
    context['window'] or a sync WindowProvider. Consumed context keys:
    window, provider, bars, e05_params, tick_size,
    htf_fvgs (List[FVGObject] — MTF_FVG_HTF@^4.0.0 input contract §1.3),
    trend_htf (UP/DOWN from E09-governed context),
    bos_events (E01_STRUCTURE_BOS@^3.2.0 governed input),
    atr_series (E04_ATR@^2.3.0 governed input — consumed, never
    recomputed for normative decisions). Produces FVG_ZONE@^4.0.0
    evidence on topics evidence.E05.* ."""

    engine_id = "E05"
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
        params = get_params(context.get("e05_params"))
        atr_series = context.get("atr_series")
        atr_by_idx = ({i: float(v) for i, v in enumerate(atr_series)}
                      if atr_series is not None else None)
        result = run_engine(
            bars, params,
            tick_size=float(context.get("tick_size", 0.01)),
            symbol=symbol,
            htf_fvgs_by_idx=context.get("htf_fvgs_by_idx"),
            trend_htf_by_idx=context.get("trend_htf_by_idx"),
            bos_by_idx=context.get("bos_by_idx"),
            atr_by_idx=atr_by_idx)
        quality = self._window_quality(window_obs)
        out: List[EvidenceEvent] = []
        for fvg in result["active"] + result["history"]:
            out.append(self._to_evidence(fvg, symbol, timeframe, quality))
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

    def _to_evidence(self, fvg: FVGObject, symbol: str, timeframe: str,
                     quality: float) -> EvidenceEvent:
        import datetime
        as_of_iso = datetime.datetime.fromtimestamp(
            fvg.created_at_ts / 1000.0, tz=datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.") + f"{fvg.created_at_ts % 1000:03d}Z"
        direction = 1 if fvg.direction == "UP" else -1
        qtag = fvg.quality_tag
        resolution = "QX" if qtag.startswith("QX") else qtag[:2]
        return EvidenceEvent(
            evidence_id=uuid_v7(),
            engine_id=self.engine_id,
            analyst_version=self.analyst_version,
            symbol=symbol, timeframe=timeframe,
            snapshot_id=fvg.snapshot_id,
            event_time=as_of_iso,
            availability_time=as_of_iso,
            observation_window={"bars": fvg.age_bars, "tf": timeframe},
            feature_snapshot_id=fvg.snapshot_id,
            feature_dependencies=("window", "atr_series", "bos_events",
                                  "htf_fvgs"),
            condition_state=f"EV_FVG_ZONE_{fvg.ftype}_{fvg.fate}",
            direction=direction,
            strength=float(min(max(fvg.salience, 0.0), 1.0)),
            confidence=1.0 if qtag in ("Q3", "Q4", "Q5") else 0.5,
            quality=float(quality),
            validity="VALID" if not qtag.startswith("QX") else "DEGRADED",
            fate_state=LifecycleState.ACTIVE,
            age=float(fvg.age_bars),
            decay=float(fvg.freshness),
            explanation=(f"E05 FVG zone {fvg.direction} [{fvg.lower},"
                         f"{fvg.upper}] {fvg.ftype} fate={fvg.fate} "
                         f"S={fvg.salience:.4f}"),
            parameter_version="E05-FVG-V4.0.0/DEFAULTS-v1",
            lineage=(f"idx_{fvg.created_at_idx}",),
            resolution_class=resolution,
        )
