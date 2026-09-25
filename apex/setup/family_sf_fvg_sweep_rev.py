"""APEX_GEN5 — the only Wave-In setup family: ``SF_FVG_SWEEP_REV``.

Blueprint: APEX_GEN5.md Ch.10 §10.1 (instantiated family) + §10.2 AD.8
(``SF_FVG_SWEEP_REV`` / ``EL_SWEEP_RECLAIM_FVG``).

Ch.10 §10.1 is explicit: **"One family is instantiated for implementation:
FVG + sweep reversal, on every symbol and every timeframe. No second family
may be invented in code."** Requesting another family raises ``WaveOutError``
(``extra_setup_families`` on the frozen Wave-Out list).

Family contract (verbatim, §10.2 AD.8)::

    family_id: SF_FVG_SWEEP_REV
    setup_timeframe: ANY of the 14 TFs
    symbol: ANY of Core-10
    required_evidence: E01, E02, E05, E09, E11, E12
    optional_evidence: E06, E10
    forbidden_regimes: [SHOCK]
    horizon_bars: 16 closed bars of THE SETUP TF
    entry_logic_ref: EL_SWEEP_RECLAIM_FVG
    playbook_id: PB_FVG_SWEEP_REV_A

``EL_SWEEP_RECLAIM_FVG`` at setup-TF close ``t`` (§10.2 AD.8):
1. ATR(14) of that TF; UNAVAILABLE ⇒ reject (no substitute ATR).
2. Sweep LONG: lookback 20 bars of that TF;
   ``low[t] < min(low[t-L:t])`` AND ``close[t] >`` that min. SHORT symmetric.
3. Reclaim = that close. Optional finer-TF reclaim if ``L[i-1]`` exists.
4. E05 unfilled FVG of that TF in the last 12 bars.
5. E01 BOS/CHOCH with setup, ``S_struct ≥ 0.55``.
6. ``entry = close[t]``, LIMIT+IOC; 0-fill dies; no chase.

Relative MTF (Ch.10 §10.1, ordered
``L = 1m,3m,5m,15m,30m,1h,2h,4h,6h,8h,12h,1d,1w,1mo``): for a setup at index
``i`` — timing optional ``L[i-1]``; intermediate required = the coarsest
available among ``L[i+2]`` else ``L[i+1]`` if strictly coarser; HTF required =
``L[i+4]`` if it exists else the coarsest above ``T``; if no coarser TF exists
the HTF/intermediate requirement is a documented **vacuous pass**; a *missing*
required coarser bar means **that cell does not emit**.

Universality: ``all_cells()`` is the 10 symbols × 14 timeframes = 140-cell
grid (§9.5-8) — no cell is skipped and no gate is timeframe-specific.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from apex.config import load_params
from apex.data_catalog.contracts import CORE10_SYMBOLS, TIMEFRAMES_14
from apex.errors import wave_out
from apex.fabric.context import q_min_setup, setup_score
from apex.fabric.evidence import EvidenceFabric
from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import sha256_hex
from apex.setup import gates

CONTRACT_VERSION = "4.0.0"

FAMILY_ID = "SF_FVG_SWEEP_REV"
PLAYBOOK_ID = "PB_FVG_SWEEP_REV_A"
ENTRY_LOGIC_REF = "EL_SWEEP_RECLAIM_FVG"
REQUIRED_EVIDENCE: Tuple[str, ...] = ("E01", "E02", "E05", "E09", "E11", "E12")
OPTIONAL_EVIDENCE: Tuple[str, ...] = ("E06", "E10")
# Blueprint line 15552 says SHOCK. SHOCK is not in the nine-class E11 registry.
# D63 defines the forbidden regime as CRISIS.
FORBIDDEN_REGIMES: Tuple[str, ...] = ("CRISIS",)
HORIZON_BARS = 16
SWEEP_LOOKBACK = 20
FVG_LOOKBACK_BARS = 12
S_STRUCT_MIN_KEY = "family_s_struct_min"

# D59 ح۳: s_i and q_i are mandatory. The 1.0/0.9 defaults are deleted.
# A missing family component raises FamilyError("COMPONENT_INPUT_MISSING").

# Ch.10 §10.1 relative-MTF ordering (the 14 frozen TFs).
TF_ORDER: Tuple[str, ...] = TIMEFRAMES_14
# The coarsest usable TF (no coarser TF exists above it ⇒ vacuous pass).
COARSEST_TF = TF_ORDER[-1]


class FamilyError(ValueError):
    """Deterministic family-level rejection (never a silent ``None``)."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}{('::' + detail) if detail else ''}")
        self.reason = reason
        self.detail = detail


def family_engines() -> Tuple[str, ...]:
    """D59 ج۷ governed list. Missing or empty ⇒ CONFIGURATION_INVALID."""
    raw = load_params()["setup_weights"].get("family_engines")
    if not isinstance(raw, (list, tuple)) or not raw:
        raise FamilyError("CONFIGURATION_INVALID", "family_engines")
    engines = tuple(str(item) for item in raw)
    from apex.fabric.context import context_weights
    unknown = [name for name in engines if name not in context_weights()]
    if unknown:
        raise FamilyError("CONFIGURATION_INVALID", ",".join(unknown))
    return engines


def family_mass() -> float:
    from apex.fabric.context import context_weights
    weights = context_weights()
    return float(sum(weights[name] for name in family_engines()))


def family_score_inputs(s_i: Optional[Mapping[str, float]],
                        q_i: Optional[Mapping[str, float]]) -> Dict[str, Any]:
    """Mandatory s_i/q_i for every family engine (D59 ح۳). No 1.0/0.9 default."""
    engines = family_engines()
    if not isinstance(s_i, Mapping) or not isinstance(q_i, Mapping):
        raise FamilyError("COMPONENT_INPUT_MISSING", "s_i" if not isinstance(s_i, Mapping) else "q_i")
    from apex.fabric.context import ENGINE_COMPONENT
    required = {ENGINE_COMPONENT[engine] for engine in REQUIRED_EVIDENCE}
    out_s: Dict[str, float] = {}
    out_q: Dict[str, float] = {}
    for name in engines:
        if name not in s_i or name not in q_i:
            # A required engine must be present. An omitted optional engine is
            # proven absence (D33): score 0, never the deleted 1.0/0.9 default.
            if name in required:
                raise FamilyError("COMPONENT_INPUT_MISSING", name)
            out_s[name] = 0.0
            out_q[name] = 0.0
            continue
        out_s[name] = float(s_i[name])
        out_q[name] = float(q_i[name])
    return {"s_i": out_s, "q_i": out_q, "mass": family_mass(), "engines": engines}


def _fabric_penalties(fabric: EvidenceFabric, rho: Optional[float]) -> Dict[str, float]:
    from apex.fabric.conflict import penalties
    return penalties(fabric.conflict_state, redundancy_rho=rho)


def family_params() -> Dict[str, Any]:
    c = load_params()["setup_weights"]
    if c["family_id"] != FAMILY_ID:
        raise FamilyError("FAMILY_ID_MISMATCH", str(c["family_id"]))
    if c["playbook_id"] != PLAYBOOK_ID:
        raise FamilyError("PLAYBOOK_ID_MISMATCH", str(c["playbook_id"]))
    return {
        "family_id": c["family_id"],
        "playbook_id": c["playbook_id"],
        "Q_min_setup": float(c["Q_min_setup"]),
        "s_struct_min": float(c[S_STRUCT_MIN_KEY]),
        "horizon_bars": HORIZON_BARS,
        "required_evidence": REQUIRED_EVIDENCE,
        "optional_evidence": OPTIONAL_EVIDENCE,
        "forbidden_regimes": FORBIDDEN_REGIMES,
        "entry_logic_ref": ENTRY_LOGIC_REF,
    }


def all_cells() -> List[Tuple[str, str]]:
    """The 140 (symbol, timeframe) cells (§9.5-8: 10 × 14)."""
    return [(sym, tf) for sym in CORE10_SYMBOLS for tf in TIMEFRAMES_14]


def register_family(name: str) -> None:
    """Only one family exists until SL-12 (Ch.10 §10.2 AD.8). An empty
    registry row is not an invitation to invent one."""
    raise wave_out("extra_setup_families",
                   f"SETUP_FAMILY_NOT_IN_FREEZE::{name}")


def relative_mtf(timeframe: str) -> Dict[str, Any]:
    """The relative-MTF selection law (Ch.10 §10.1)."""
    if timeframe not in TF_ORDER:
        raise FamilyError("TIMEFRAME_NOT_FROZEN", str(timeframe))
    i = TF_ORDER.index(timeframe)
    timing = TF_ORDER[i - 1] if i - 1 >= 0 else None
    finer_available = timing is not None
    intermediate = None
    for cand in (i + 2, i + 1):
        if cand < len(TF_ORDER):
            intermediate = TF_ORDER[cand]
            break
    htf = TF_ORDER[i + 4] if i + 4 < len(TF_ORDER) else (
        COARSEST_TF if intermediate is not None else None)
    vacuous = intermediate is None and htf is None
    return {"setup": timeframe, "timing": timing,
            "timing_available": finer_available,
            "intermediate": intermediate, "htf": htf,
            "vacuous": vacuous,
            "note": "missing required coarser bar ⇒ the cell does not emit; "
                    "no coarser TF at all ⇒ documented vacuous pass"}


def s_struct_min() -> float:
    return family_params()["s_struct_min"]


# ---------------------------------------------------------------------------
# Entry logic EL_SWEEP_RECLAIM_FVG (each clause individually testable)
# ---------------------------------------------------------------------------

def sweep_and_reclaim(bars: Sequence[Mapping[str, float]], *, direction: int,
                      lookback: int = SWEEP_LOOKBACK) -> Dict[str, Any]:
    """Steps 2–3: sweep of the prior ``lookback`` extremes + reclaim at the
    confirming close. LONG: ``low[t] < min(low[t-L:t])`` ∧ ``close[t] >`` that
    min. SHORT symmetric on highs."""
    if direction not in (-1, 0, 1) or direction == 0:
        raise FamilyError("DIRECTION_QX", str(direction))
    if len(bars) < 2:
        return {"ok": False, "reason": "INSUFFICIENT_BARS"}
    t = len(bars) - 1
    start = max(0, t - lookback)
    window = bars[start:t]
    if not window:
        return {"ok": False, "reason": "INSUFFICIENT_LOOKBACK"}
    if direction > 0:
        extreme = min(float(b["l"]) for b in window)
        swept = float(bars[t]["l"]) < extreme - 1e-12
        reclaim = float(bars[t]["c"]) > extreme + 1e-12
    else:
        extreme = max(float(b["h"]) for b in window)
        swept = float(bars[t]["h"]) > extreme + 1e-12
        reclaim = float(bars[t]["c"]) < extreme - 1e-12
    if not swept:
        return {"ok": False, "reason": "NO_SWEEP", "extreme": extreme}
    if not reclaim:
        return {"ok": False, "reason": "NO_RECLAIM", "extreme": extreme}
    return {"ok": True, "reason": "SWEEP_RECLAIMED", "extreme": extreme,
            "reclaim_level": float(bars[t]["c"]), "sweep_bar": t,
            "lookback_used": t - start}


def atr_gate(atr: Optional[float]) -> Dict[str, Any]:
    """Step 1: ATR(14) of that TF; UNAVAILABLE ⇒ reject (never substituted)."""
    if atr is None or atr != atr or atr <= 0:
        return {"ok": False, "reason": "ATR_UNAVAILABLE"}
    return {"ok": True, "reason": "ATR_GOVERNED", "atr": float(atr)}


def fvg_gate(zones: Sequence[Mapping[str, Any]], *, last_bars: int = FVG_LOOKBACK_BARS,
             current_index: Optional[int] = None) -> Dict[str, Any]:
    """Step 4: an E05 unfilled FVG of that TF within the last 12 bars.

    ``zones`` are E05 FVG records ``{index, filled: bool}`` — the family only
    consumes them (E05 owns creation/mitigation; no re-derivation here).
    """
    if not zones:
        return {"ok": False, "reason": "NO_FVG_EVIDENCE"}
    cur = len(zones) - 1 if current_index is None else int(current_index)
    for z in reversed(list(zones)):
        idx = int(z.get("index", cur))
        if idx > cur:
            raise FamilyError("FVG_PIT_VIOLATION", f"zone index {idx} > {cur}")
        if cur - idx > last_bars:
            break
        if not bool(z.get("filled", False)):
            return {"ok": True, "reason": "UNFILLED_FVG_IN_WINDOW",
                    "fvg_index": idx, "zone": dict(z)}
    return {"ok": False, "reason": "NO_UNFILLED_FVG_IN_WINDOW"}


def structure_gate(bos: Optional[Mapping[str, Any]], *, s_min: Optional[float] = None
                   ) -> Dict[str, Any]:
    """Step 5: E01 BOS/CHOCH with the setup and ``S_struct ≥ 0.55``."""
    thr = s_struct_min() if s_min is None else float(s_min)
    if not bos:
        return {"ok": False, "reason": "NO_BOS_EVIDENCE", "s_struct": None,
                "threshold": thr}
    s = float(bos.get("s_struct", float("nan")))
    if s != s:
        return {"ok": False, "reason": "S_STRUCT_UNAVAILABLE", "s_struct": None,
                "threshold": thr}
    direction_match = int(bos.get("direction", 0)) != 0
    if not direction_match:
        return {"ok": False, "reason": "BOS_DIRECTION_MISSING", "s_struct": s,
                "threshold": thr}
    if s < thr:
        return {"ok": False, "reason": "S_STRUCT_BELOW_MIN", "s_struct": s,
                "threshold": thr}
    return {"ok": True, "reason": "BOS_ALIGNED", "s_struct": s, "threshold": thr}


def regime_gate(regime_state: Optional[str]) -> Dict[str, Any]:
    """Forbidden regime blocks the setup. D63 names CRISIS, not the blueprint
    token SHOCK, which is not in the nine-class E11 registry."""
    if regime_state is None:
        return {"ok": False, "reason": "REGIME_UNAVAILABLE"}
    if str(regime_state).upper() in FORBIDDEN_REGIMES:
        return {"ok": False, "reason": "FORBIDDEN_REGIME",
                "regime": str(regime_state).upper()}
    return {"ok": True, "reason": "REGIME_PERMITTED", "regime": str(regime_state)}


def mtf_gate(timeframe: str, available_closes: Mapping[str, Any]) -> Dict[str, Any]:
    """Relative-MTF requirement + the "cell does not emit" law."""
    rel = relative_mtf(timeframe)
    missing_required = [k for k in ("intermediate", "htf")
                        if rel[k] is not None and available_closes.get(rel[k]) is None]
    if missing_required and not rel["vacuous"]:
        return {"ok": False, "reason": "MISSING_REQUIRED_COARSER_BAR",
                "missing": [rel[k] for k in missing_required], "selection": rel}
    if rel["vacuous"]:
        return {"ok": True, "reason": "VACUOUS_NO_COARSER_TF", "selection": rel}
    return {"ok": True, "reason": "MTF_BARS_PRESENT", "selection": rel,
            "timing_present": available_closes.get(rel["timing"]) is not None
            if rel["timing"] else False}


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SetupEvaluation:
    """The family's output: a scored, gated setup candidate for one cell."""

    symbol: str
    timeframe: str
    as_of: int
    direction: int
    status: str                       # EMITTED | QUARANTINED | NOT_EMITTED
    raw: float
    final_score: float
    q_min_setup: float
    entry: Optional[float] = None
    risk_reference: Optional[float] = None
    gate_block: Dict[str, Any] = field(default_factory=dict)
    entry_logic_steps: Dict[str, Any] = field(default_factory=dict)
    fabric_hash: str = ""
    context_confidence: Optional[float] = None
    horizon_bars: int = HORIZON_BARS
    family_id: str = FAMILY_ID
    playbook_id: str = PLAYBOOK_ID
    entry_logic_ref: str = ENTRY_LOGIC_REF
    reason: str = ""

    def to_setup_event(self) -> Dict[str, Any]:
        """SetupEvent materialization: the Data Plane ``setup_candidate``
        columns plus the additive AD.1 field 22 ``family_id``.

        ``family_id != NULL`` ⇒ pooled/eligible; a setup without family
        membership stays UNPOOLED (research-only, never promotable) — which
        this family never produces, since family_id is always set here.
        """
        return {
            "setup_id": "setup-" + sha256_hex(canonical_json({
                "symbol": self.symbol, "timeframe": self.timeframe,
                "as_of": self.as_of, "direction": self.direction,
                "fabric_hash": self.fabric_hash}))[:32],
            "timestamp": self.as_of,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "pattern_ids": "",
            "direction": "BULLISH" if self.direction > 0 else "BEARISH",
            "entry_price": None if self.entry is None else repr(self.entry),
            "stop_loss": (None if self.risk_reference is None
                          else repr(self.risk_reference)),
            "take_profit": None,
            "risk_reward": None,
            "confidence": self.context_confidence,
            "quality": "Q1" if self.status == "EMITTED" else "QX",
            "validity": 1 if self.status == "EMITTED" else 0,
            "snapshot_id": self.fabric_hash,
            "parent_ids": "",
            "payload_hash": self.fabric_hash,
            "regime": None,
            "utc_activity_window_id": None,
            "lineage": self.fabric_hash,
            "authority": "SETUP_ENGINE",
            "authority_scope": "SIGNAL",
            # AD.1 SetupEvent contract amendment (additive, field 22):
            "family_id": self.family_id,
            # CP-6 operational extras (never part of the frozen DDL):
            "status": self.status,
            "score": {"raw": self.raw, "final": self.final_score,
                      "q_min_setup": self.q_min_setup},
            "gates": self.gate_block,
            "entry_logic_ref": self.entry_logic_ref,
            "entry_logic_steps": self.entry_logic_steps,
            "playbook_id": self.playbook_id,
            "horizon_bars": self.horizon_bars,
            "reason": self.reason,
            "contract_version": CONTRACT_VERSION,
        }


def _evidence_directions(fabric: EvidenceFabric) -> Tuple[Dict[int, List[str]],
                                                           Dict[str, int]]:
    by_dir: Dict[int, List[str]] = {-1: [], 0: [], +1: []}
    per_engine: Dict[str, int] = {}
    for m in fabric.members:
        by_dir[m.direction].append(m.engine_id)
        per_engine[m.engine_id] = m.direction
    return by_dir, per_engine


def evaluate_cell(*, symbol: str, timeframe: str, as_of: int,
                  fabric: EvidenceFabric,
                  bars: Sequence[Mapping[str, float]],
                  atr: Optional[float],
                  direction: int,
                  fvg_zones: Sequence[Mapping[str, Any]] = (),
                  bos: Optional[Mapping[str, Any]] = None,
                  regime_state: Optional[str] = None,
                  mtf_state: str = "ALIGNED",
                  available_closes: Optional[Mapping[str, Any]] = None,
                  window_qualities: Optional[Sequence[Tuple[float, float]]] = None,
                  temporal_quality: Any = "Q2",
                  volatility_quality: Any = "Q2",
                  forecast: Optional[Mapping[str, Any]] = None,
                  q_forecast: Optional[float] = None,
                  package: Optional[Mapping[str, Any]] = None,
                  payload: Optional[Mapping[str, Any]] = None,
                  lineage: Optional[Sequence[str]] = None,
                  context_confidence: Optional[float] = None,
                  component_series: Optional[Mapping[str, Sequence[float]]] = None,
                  s_i: Optional[Mapping[str, float]] = None,
                  q_i: Optional[Mapping[str, float]] = None,
                  environment: str = "PAPER") -> SetupEvaluation:
    """Evaluate one ``(symbol, timeframe)`` cell through the family.

    Order is normative: entry-logic conditions → scoring → the thirteen hard
    gates → emission. A cell that cannot satisfy a *required* condition does
    not emit; nothing is fabricated to keep it alive.
    """
    if symbol not in CORE10_SYMBOLS:
        raise FamilyError("E-VAL-021", str(symbol))
    if timeframe not in TIMEFRAMES_14:
        raise FamilyError("E-VAL-022", str(timeframe))
    p = family_params()
    steps: Dict[str, Any] = {}
    # The cell's own canonical snapshot identity (GC-D8): snapshot_id =
    # sha256(canonical_json(payload)) over the fabric body — recomputed here
    # so Gate 11 always has something to verify against.
    snap_payload = {
        "as_of": as_of, "symbol": symbol, "timeframe": timeframe,
        "evidence": [m.content_id for m in fabric.members],
        "data_trust": fabric.data_trust, "conflict_state": fabric.conflict_state,
        "redundancy_state": dict(fabric.redundancy_state),
    }
    snap_id = sha256_hex(canonical_json(dict(payload) if payload is not None
                                           else snap_payload))
    # Fabric self-integrity (GC-D8): the fabric hash must recompute from its
    # own canonical body, or the cell does not emit (integrity, not a score).
    fabric_body = {
        "as_of": fabric.as_of, "symbol": fabric.symbol,
        "timeframe": fabric.timeframe,
        "evidence": [m.content_id for m in fabric.members],
        "data_trust": fabric.data_trust,
        "conflict_state": fabric.conflict_state,
        "redundancy_state": dict(fabric.redundancy_state),
    }
    if payload is None and fabric.hash != sha256_hex(canonical_json(fabric_body)):
        return _reject(symbol, timeframe, as_of, direction, fabric, steps,
                       reason="FABRIC_HASH_MISMATCH", p=p, snap_id=snap_id,
                       context_confidence=context_confidence)

    steps["1_atr"] = atr_gate(atr)
    if not steps["1_atr"]["ok"]:
        return _reject(symbol, timeframe, as_of, direction, fabric, steps,
                       reason=steps["1_atr"]["reason"], p=p, snap_id=snap_id,
                       context_confidence=context_confidence)
    steps["2_3_sweep_reclaim"] = sweep_and_reclaim(bars, direction=direction)
    if not steps["2_3_sweep_reclaim"]["ok"]:
        return _reject(symbol, timeframe, as_of, direction, fabric, steps,
                       reason=steps["2_3_sweep_reclaim"]["reason"], p=p, snap_id=snap_id,
                       context_confidence=context_confidence)
    steps["4_fvg"] = fvg_gate(fvg_zones, current_index=len(bars) - 1)
    if not steps["4_fvg"]["ok"]:
        return _reject(symbol, timeframe, as_of, direction, fabric, steps,
                       reason=steps["4_fvg"]["reason"], p=p, snap_id=snap_id,
                       context_confidence=context_confidence)
    steps["5_structure"] = structure_gate(bos)
    if not steps["5_structure"]["ok"]:
        return _reject(symbol, timeframe, as_of, direction, fabric, steps,
                       reason=steps["5_structure"]["reason"], p=p, snap_id=snap_id,
                       context_confidence=context_confidence)
    steps["regime"] = regime_gate(regime_state)
    if not steps["regime"]["ok"]:
        return _reject(symbol, timeframe, as_of, direction, fabric, steps,
                       reason=steps["regime"]["reason"], p=p, snap_id=snap_id,
                       context_confidence=context_confidence)
    steps["6_entry"] = {
        "ok": True, "reason": "LIMIT_IOC_AT_CLOSE",
        "entry": float(bars[-1]["c"]),
        "risk_reference": steps["2_3_sweep_reclaim"]["extreme"],
        "fill_policy": "0-fill dies; no chase (never a MARKET order)",
    }

    # required evidence must be present in the fabric (family contract)
    _by_dir, per_engine = _evidence_directions(fabric)
    missing = [e for e in REQUIRED_EVIDENCE if e not in per_engine]
    steps["required_evidence"] = {
        "ok": not missing, "missing": missing,
        "required": list(REQUIRED_EVIDENCE), "optional": list(OPTIONAL_EVIDENCE),
        "present": sorted(per_engine),
    }
    if missing:
        return _reject(symbol, timeframe, as_of, direction, fabric, steps,
                       reason="REQUIRED_EVIDENCE_MISSING", p=p,
                       snap_id=snap_id,
                       context_confidence=context_confidence,
                       detail=",".join(missing))

    # required-evidence direction conflict (Ch.10 §10.1): direction_i ·
    # direction_j = −1 among the REQUIRED evidences.
    dirs = [per_engine[e] for e in REQUIRED_EVIDENCE if e in per_engine]
    required_conflict = any(a * b == -1 for a in dirs for b in dirs)
    # redundancy: Pearson ρ on the s_i series (Ch.10 §10.1) — measured, never
    # assumed. Without supplied series the measurement is skipped and no
    # penalty is invented.
    family = family_score_inputs(s_i, q_i)
    rho = None
    pairs = []
    if component_series:
        from apex.fabric.context import redundancy_rho as _rho_fn
        names = sorted(component_series)
        best = 0.0
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                r = _rho_fn(component_series[names[i]], component_series[names[j]])
                pairs.append((names[i], names[j], r["rho"]))
                if r["rho"] is not None and abs(r["rho"]) > abs(best):
                    best = r["rho"]
        if abs(best) > 0.0:
            rho = best
    score = setup_score(fabric,
                        s_i=family["s_i"],
                        q_i=family["q_i"],
                        required_conflict=required_conflict,
                        redundancy_rho=rho,
                        redundancy_pairs=pairs)
    # D59 ج۷: normalise over the family weight mass (0.70), not the twelve-weight sum.
    mass = family["mass"]
    if mass > 0 and score["reason"] == "OK":
        score = dict(score)
        score["raw"] = score["raw"] / mass
        score["final"] = score["final"] / mass
        score["family_mass"] = mass
    steps["conflict"] = {"required_conflict": required_conflict,
                         "multiplier": score["conflict_multiplier"],
                         "reason": ("REQUIRED_DIRECTION_CONFLICT"
                                   if required_conflict else "NONE")}
    steps["redundancy"] = {"rho": rho, "dropped": score["redundancy"]["victim"],
                           "penalty_multiplier": score["redundancy_multiplier"],
                           "reason": score["redundancy"]["reason"]}

    gate_ctx = {
        "final_score": score["final"],
        "window_qualities": list(window_qualities or
                                 [(1.0, 0.0)] * len(bars)),
        "conflict_penalty": _fabric_penalties(fabric, rho)["conflict_penalty"],
        "redundancy_penalty": _fabric_penalties(fabric, rho)["redundancy_penalty"],
        "mtf_state": mtf_state,
        "has_coarser_bars": not relative_mtf(timeframe)["vacuous"],
        "h_norm": float(forecast.get("h_norm", 0.0)) if forecast else 0.0,
        "temporal_quality": temporal_quality,
        "volatility_quality": volatility_quality,
        "forecast": dict(forecast or {}),
        "snapshot_id": snap_id,
        "payload": dict(payload) if payload is not None else snap_payload,
        "lineage": list(lineage if lineage is not None
                        else [m for mem in fabric.members for m in mem.lineage]
                        or [f"obs-{fabric.hash[:8]}"]),
        "q_forecast": q_forecast,
        "package": package,
        "timeframe": timeframe,
        "environment": environment,
    }
    block = gates.run_all(gate_ctx)
    if not block["all_pass"] or score["vacuous"]:
        ev = SetupEvaluation(
            symbol=symbol, timeframe=timeframe, as_of=as_of,
            direction=direction, status=QUARANTINED,
            raw=score["raw"], final_score=score["final"],
            q_min_setup=q_min_setup(),
            entry=steps["6_entry"]["entry"],
            risk_reference=steps["6_entry"]["risk_reference"],
            gate_block=block, entry_logic_steps=steps,
            fabric_hash=snap_id, context_confidence=context_confidence,
            horizon_bars=p["horizon_bars"], family_id=p["family_id"],
            playbook_id=p["playbook_id"], entry_logic_ref=p["entry_logic_ref"],
            reason=("VACUOUS_NO_EVIDENCE" if score["vacuous"]
                    else "GATES_BLOCK::" + ",".join(block["reasons"])))
        return ev
    return SetupEvaluation(
        symbol=symbol, timeframe=timeframe, as_of=as_of, direction=direction,
        status=EMITTED, raw=score["raw"], final_score=score["final"],
        q_min_setup=q_min_setup(), entry=steps["6_entry"]["entry"],
        risk_reference=steps["6_entry"]["risk_reference"], gate_block=block,
        entry_logic_steps=steps, fabric_hash=snap_id,
        context_confidence=context_confidence, horizon_bars=p["horizon_bars"],
        family_id=p["family_id"], playbook_id=p["playbook_id"],
        entry_logic_ref=p["entry_logic_ref"], reason="ALL_GATES_PASS",
    )


EMITTED = "EMITTED"
QUARANTINED = "QUARANTINED"
NOT_EMITTED = "NOT_EMITTED"


def _reject(symbol: str, timeframe: str, as_of: int, direction: int,
            fabric: EvidenceFabric, steps: Dict[str, Any], *, reason: str,
            p: Dict[str, Any], context_confidence: Optional[float],
            detail: str = "", snap_id: str = "") -> SetupEvaluation:
    """A cell that cannot satisfy a required condition: no emission, and no
    fabricated score (``final_score`` 0.0 is *reported*, never *assumed*)."""
    return SetupEvaluation(
        symbol=symbol, timeframe=timeframe, as_of=as_of, direction=direction,
        status=NOT_EMITTED, raw=0.0, final_score=0.0,
        q_min_setup=p["Q_min_setup"], entry=None, risk_reference=None,
        gate_block={"results": {}, "all_pass": False, "blocked_by": [],
                    "reasons": [reason], "action": "DO_NOT_EMIT"},
        entry_logic_steps=steps,
        fabric_hash=snap_id or fabric.hash,
        context_confidence=context_confidence, horizon_bars=p["horizon_bars"],
        family_id=p["family_id"], playbook_id=p["playbook_id"],
        entry_logic_ref=p["entry_logic_ref"],
        reason=reason + (f"::{detail}" if detail else ""))
