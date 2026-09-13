"""APEX_GEN5 — the thirteen hard gates of the Setup Engine (Ch.10 §10.1).

Blueprint: APEX_GEN5.md Ch.10 §10.1 (L15204–15250) — the gate table verbatim:

| Gate | Condition | Action |
|------|-----------|--------|
| 1 | final score < Q_min | QUARANTINED BLOCK |
| 2 | Q_window min < threshold | QUARANTINED BLOCK |
| 3 | conflict_penalty > 0.5 | QUARANTINED BLOCK |
| 4 | redundancy_penalty > 0.3 | QUARANTINED BLOCK |
| 5 | MTF CONFLICTING | QUARANTINED BLOCK |
| 6 | MTF INSUFFICIENT | QUARANTINED BLOCK |
| 7 | regime quality fail | QUARANTINED BLOCK |
| 8 | temporal_window quality fail | QUARANTINED BLOCK |
| 9 | volatility quality fail | QUARANTINED BLOCK |
| 10 | forecast quality fail | QUARANTINED BLOCK |
| 11 | lineage / snapshot integrity fail (AJ.10 / GC-D8; NOT "any of the 13
       gates") | QUARANTINED BLOCK |
| 12 | Q_forecast < threshold | QUARANTINED BLOCK |
| 13 | ParameterPackage invalid | QUARANTINED BLOCK |

All thirteen trigger a QUARANTINED block on failure; they apply to **every
Core-10 symbol and every one of the 14 TFs** (no gate is 15m-only).

Gate design (auditable, one gate = one function, individually testable)
------------------------------------------------------------------------
* Score gates (1, 3, 4, 7, 12) compare a frozen quantized value against a
  governed threshold; the unit of the scale is ``gate_score_unit`` = 0.01, so
  the boundary pair of every score gate is exactly one unit apart.
* Quality-class gates (8, 9) compare the integer of the input's Q-label
  (Q0..Q5) against ``gate_quality_min_class``; one Q-class = one unit.
* Enum gates (5, 6) fire on the state itself (the MTF state is *consumed*,
  never re-derived — Ch.8 §8.3: "the gate operates on the state, it does not
  re-derive it").
* Gate 11 is **snapshot/lineage integrity only** (AJ.10 / GC-D8): the payload
  hash must recompute and every lineage token must be a real identity — it is
  *not* a catch-all for "any of the 13 gates" (§10.1 parenthetical).
* Gate 13 is ParameterPackage validity: a missing package, a non-mapping
  package, or a Q_param-degraded package is invalid.

Every gate returns ``GateResult``; nothing here quarantines, permits or sizes
— it only judges.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from apex.config import load_params
from apex.fabric.context import q_min_tf
from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import sha256_hex
from apex.quality.vector import calc_window_quality, q_param

CONTRACT_VERSION = "4.0.0"
QUARANTINE = "QUARANTINED"

GATE_NAMES: Tuple[str, ...] = (
    "FINAL_SCORE_MIN", "Q_WINDOW_MIN", "CONFLICT_PENALTY_MAX",
    "REDUNDANCY_PENALTY_MAX", "MTF_CONFLICTING", "MTF_INSUFFICIENT",
    "REGIME_QUALITY", "TEMPORAL_WINDOW_QUALITY", "VOLATILITY_QUALITY",
    "FORECAST_QUALITY", "SNAPSHOT_LINEAGE_INTEGRITY", "Q_FORECAST_MIN",
    "PARAMETER_PACKAGE_VALID",
)
GATE_COUNT = 13
MTF_BLOCKING_STATES: Dict[int, str] = {5: "CONFLICTING", 6: "INSUFFICIENT"}
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ID_TOKEN = re.compile(r"^(obs-[A-Za-z0-9_-]+|ev_[A-Za-z0-9_-]+|"
                       r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
                       r"[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{64})$")


def _cfg() -> Dict[str, Any]:
    return load_params()["setup_weights"]


def score_unit() -> float:
    return float(_cfg()["gate_score_unit"])


def quality_min_class() -> int:
    return int(_cfg()["gate_quality_min_class"])


def q_forecast_min() -> float:
    return float(_cfg()["gate_forecast_q_min"])


def gate_thresholds() -> Dict[str, float]:
    """The governed threshold set of the score gates (single source)."""
    c = _cfg()
    return {
        "gate1_q_min_setup": float(c["Q_min_setup"]),
        "gate2_q_thr_default": 0.5,               # §2.1 algorithm default
        "gate3_conflict_penalty_max": 0.5,
        "gate4_redundancy_penalty_max": 0.3,
        "gate7_entropy_max": float(c["gate7_entropy_threshold"]),
        "gate12_q_forecast_min": float(c["gate_forecast_q_min"]),
        "gate_score_unit": float(c["gate_score_unit"]),
    }


def _q_class_int(value: Any) -> int:
    """Q0..Q5 → 0..5; QX / UNAVAILABLE → −1 (fail closed, never a guess)."""
    if value is None:
        return -1
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    s = str(value).strip().upper()
    if s in ("QX", "UNAVAILABLE", "MISSING", ""):
        return -1
    m = re.match(r"^Q([0-5])$", s)
    if not m:
        raise ValueError(f"GATE_QUALITY_CLASS_QX: {value!r} is not Q0..Q5/QX")
    return int(m.group(1))


@dataclass(frozen=True)
class GateResult:
    number: int
    name: str
    passed: bool
    measured: Any
    threshold: Any
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {"gate": self.number, "name": self.name, "passed": self.passed,
                "measured": self.measured, "threshold": self.threshold,
                "reason": self.reason, "action": (None if self.passed
                                                  else QUARANTINE)}


def _res(number: int, passed: bool, measured: Any, threshold: Any,
         reason_pass: str, reason_fail: str) -> GateResult:
    return GateResult(number, GATE_NAMES[number - 1], bool(passed), measured,
                      threshold, reason_pass if passed else reason_fail)


# ---------------------------------------------------------------------------
# The thirteen gates, each individually callable
# ---------------------------------------------------------------------------

def gate1_final_score(final_score: float) -> GateResult:
    """``final score < Q_min`` ⇒ block (Q_min_setup = 0.55, frozen)."""
    thr = gate_thresholds()["gate1_q_min_setup"]
    return _res(1, final_score >= thr, final_score, thr,
                "SCORE_ABOVE_Q_MIN", "GATE1_BELOW_Q_MIN_SETUP")


def gate2_window_quality(qualities: Sequence[Tuple[float, float]], *,
                         q_thr: Optional[float] = None) -> GateResult:
    """``Q_window min < threshold`` ⇒ block. Delegates to the frozen §2.1
    ``calc_window_quality`` (minimum-veto + exponential-decay average)."""
    q_thr = gate_thresholds()["gate2_q_thr_default"] if q_thr is None else q_thr
    value, state, _cls = calc_window_quality(qualities, q_thr=q_thr)
    passed = state == "VALID"
    return _res(2, passed, value if value is not None else state, q_thr,
                 "WINDOW_QUALITY_VALID", "GATE2_" + str(state))


def gate3_conflict_penalty(conflict_penalty: float) -> GateResult:
    """``conflict_penalty > 0.5`` ⇒ block (Ch.8 §8.1 projection)."""
    thr = gate_thresholds()["gate3_conflict_penalty_max"]
    return _res(3, conflict_penalty <= thr, conflict_penalty, thr,
                 "CONFLICT_PENALTY_IN_BOUNDS", "GATE3_CONFLICT_PENALTY_EXCEEDED")


def gate4_redundancy_penalty(redundancy_penalty: float) -> GateResult:
    """``redundancy_penalty > 0.3`` ⇒ block."""
    thr = gate_thresholds()["gate4_redundancy_penalty_max"]
    return _res(4, redundancy_penalty <= thr, redundancy_penalty, thr,
                "REDUNDANCY_PENALTY_IN_BOUNDS",
                "GATE4_REDUNDANCY_PENALTY_EXCEEDED")


def gate5_mtf_conflicting(mtf_state: str) -> GateResult:
    """``MTF CONFLICTING`` ⇒ block. The state is consumed (Ch.8 §8.3); an
    unknown state fails closed rather than passing."""
    if mtf_state not in ("ALIGNED", "PARTIALLY_ALIGNED", "CONFLICTING",
                        "STALE", "UNAVAILABLE", "INSUFFICIENT"):
        raise ValueError(f"GATE_MTF_STATE_QX: {mtf_state!r} is not an MTF state")
    return _res(5, mtf_state != "CONFLICTING", mtf_state, "CONFLICTING",
                 "MTF_NOT_CONFLICTING", "GATE5_MTF_CONFLICTING")


def gate6_mtf_sufficient(mtf_state: str, *, has_coarser_bars: bool = True) -> GateResult:
    """``MTF INSUFFICIENT`` ⇒ block. When no coarser timeframe exists at all,
    the HTF/intermediate requirement is a documented **vacuous pass**
    (Ch.10 §10.1); a *missing required coarser bar* is not vacuous — it blocks
    (that cell does not emit)."""
    if mtf_state not in ("ALIGNED", "PARTIALLY_ALIGNED", "CONFLICTING",
                        "STALE", "UNAVAILABLE", "INSUFFICIENT"):
        raise ValueError(f"GATE_MTF_STATE_QX: {mtf_state!r} is not an MTF state")
    passed = (mtf_state != "INSUFFICIENT") or (not has_coarser_bars)
    return _res(6, passed, mtf_state, "INSUFFICIENT",
                 "MTF_SUFFICIENT" if mtf_state != "INSUFFICIENT"
                 else "GATE6_VACUOUS_NO_COARSER_TF",
                 "GATE6_MTF_INSUFFICIENT")


def gate7_regime_quality(h_norm: float) -> GateResult:
    """Regime quality fail ⇒ block; ``H/ln(9) > 0.85`` is the fail condition
    (Ch.10 §10.1 — distinct from E11's ``θ_H = 0.65``, which only forces
    TRANSITION inside E11)."""
    thr = gate_thresholds()["gate7_entropy_max"]
    return _res(7, h_norm <= thr, h_norm, thr, "REGIME_ENTROPY_IN_BOUNDS",
                 "GATE7_REGIME_QUALITY_FAIL")


def gate8_temporal_window_quality(quality_class: Any) -> GateResult:
    """temporal_window quality fail ⇒ block (E12 Q-class consumed as-is)."""
    minimum = quality_min_class()
    v = _q_class_int(quality_class)
    return _res(8, v >= minimum, quality_class, f"Q{minimum}",
                 "TEMPORAL_WINDOW_QUALITY_OK", "GATE8_TEMPORAL_WINDOW_QUALITY_FAIL")


def gate9_volatility_quality(quality_class: Any) -> GateResult:
    """volatility quality fail ⇒ block (E04 governed ATR / regime Q-class)."""
    minimum = quality_min_class()
    v = _q_class_int(quality_class)
    return _res(9, v >= minimum, quality_class, f"Q{minimum}",
                 "VOLATILITY_QUALITY_OK", "GATE9_VOLATILITY_QUALITY_FAIL")


def gate10_forecast_quality(forecast: Mapping[str, Any], *,
                            environment: str = "PAPER") -> GateResult:
    """Forecast quality fail ⇒ block.

    Two fail-closed conditions from Ch.13 §13.1:
    * the forecast record must carry the full P/U/C contract; a missing
      quality view is a fail, never an assumed pass;
    * the constant-0.5 bootstrap prior is eligible for RESEARCH/PAPER **only**
      — "LIVE capital: Setup Gates 10/12 fail until a calibrated package
      exists".
    """
    if "q_forecast" not in forecast and "quality" not in forecast:
        return _res(10, False, "MISSING_FORECAST_QUALITY", "Q1",
                    "", "GATE10_FORECAST_QUALITY_MISSING")
    bootstrap = bool(forecast.get("bootstrap_prior", False))
    if bootstrap and environment not in ("RESEARCH", "PAPER", "BACKTEST"):
        return _res(10, False, f"bootstrap p=0.5 in {environment}",
                    "RESEARCH|PAPER only", "",
                    "GATE10_BOOTSTRAP_PRIOR_NOT_LIVE_ELIGIBLE")
    cls = forecast.get("quality", forecast.get("q_forecast"))
    v = _q_class_int(cls) if not isinstance(cls, (int, float)) else int(cls)
    minimum = quality_min_class()
    return _res(10, v >= minimum, cls, f"Q{minimum}",
                 "FORECAST_QUALITY_OK", "GATE10_FORECAST_QUALITY_FAIL")


def gate11_snapshot_lineage(snapshot_id: str, payload: Any,
                            lineage: Sequence[str], *,
                            fabric_hash: Optional[str] = None) -> GateResult:
    """**Snapshot / lineage integrity only** (AJ.10 / GC-D8).

    (a) ``snapshot_id`` must be ``sha256(canonical_json(payload))`` —
        recomputed here, never trusted; (b) every lineage token must be a
        well-formed identity down to the raw ``observation_id``; (c) the
        payload must be canonically serializable at all (NaN/Inf ⇒ fail);
        (d) when an Evidence Fabric hash is supplied it must also recompute.
    A failure is ``QUARANTINED`` — the setup is not repaired and not deleted.
    This gate judges integrity ONLY — it is *not* "any of the 13 gates"
    (Ch.10 §10.1).
    """
    try:
        expected = sha256_hex(canonical_json(payload))
    except Exception as exc:
        return _res(11, False, f"CANONICALIZATION_FAILED::{type(exc).__name__}",
                    "sha256(canonical_json(payload))", "",
                    "GATE11_SNAPSHOT_UNHASHABLE")
    if not isinstance(snapshot_id, str) or not _HEX64.match(snapshot_id or ""):
        return _res(11, False, snapshot_id, "64-hex", "",
                    "GATE11_SNAPSHOT_ID_MALFORMED")
    if snapshot_id != expected:
        return _res(11, False, snapshot_id, expected, "",
                    "GATE11_SNAPSHOT_HASH_MISMATCH")
    if not lineage:
        return _res(11, False, "EMPTY_LINEAGE", "lineage → raw observation_id",
                    "", "GATE11_LINEAGE_EMPTY")
    bad = [tok for tok in lineage if not _ID_TOKEN.match(str(tok))]
    if bad:
        return _res(11, False, bad, "well-formed ids", "",
                    "GATE11_LINEAGE_UNRESOLVED")
    if fabric_hash is not None and fabric_hash != expected:
        return _res(11, False, fabric_hash, expected, "",
                    "GATE11_FABRIC_HASH_MISMATCH")
    return _res(11, True, snapshot_id, "matches recomputed hash",
                "SNAPSHOT_LINEAGE_INTACT", "")


def gate12_q_forecast(q_forecast: Optional[float]) -> GateResult:
    """``Q_forecast < threshold`` ⇒ block (threshold = 0.5; §2.1
    "Q_forecast < 0.5 → Forecast BLOCK"). An absent value is not zero — it is
    an unavailable measurement, which fails closed."""
    thr = q_forecast_min()
    if q_forecast is None or q_forecast != q_forecast:
        return _res(12, False, q_forecast, thr, "",
                    "GATE12_Q_FORECAST_UNAVAILABLE")
    return _res(12, q_forecast >= thr, q_forecast, thr, "Q_FORECAST_ABOVE_MIN",
                "GATE12_Q_FORECAST_BELOW_THRESHOLD")


def gate13_parameter_package(package: Optional[Mapping[str, Any]]) -> GateResult:
    """ParameterPackage invalid ⇒ block. Valid means: a non-empty mapping, a
    versioned id, and a package quality that is not Q_param-degraded
    (``Q_param < 0.5``)."""
    if package is None or not isinstance(package, Mapping) or not package:
        return _res(13, False, package, "versioned non-empty mapping", "",
                    "GATE13_PACKAGE_MISSING")
    if not package.get("package_version") or not package.get("parameter_package_id"):
        return _res(13, False, sorted(package), "package_version + "
                    "parameter_package_id", "", "GATE13_PACKAGE_UNVERSIONED")
    needed = ("rolling_calibration_error", "brier", "log_loss")
    if all(k in package for k in needed):
        value, degraded = q_param(float(package["rolling_calibration_error"]),
                                 float(package["brier"]),
                                 float(package["log_loss"]))
        if degraded:
            return _res(13, False, value, "Q_param ≥ 0.5", "",
                        "GATE13_PACKAGE_DEGRADED")
        return _res(13, True, package.get("parameter_package_id"), "valid",
                    "PACKAGE_VALID", "")
    if package.get("q_param") is not None:
        if float(package["q_param"]) < 0.5:
            return _res(13, False, package["q_param"], "Q_param ≥ 0.5", "",
                        "GATE13_PACKAGE_DEGRADED")
    return _res(13, True, package.get("parameter_package_id"), "valid",
                 "PACKAGE_VALID", "")


GATES: Dict[int, Callable[..., GateResult]] = {
    1: gate1_final_score, 2: gate2_window_quality, 3: gate3_conflict_penalty,
    4: gate4_redundancy_penalty, 5: gate5_mtf_conflicting,
    6: gate6_mtf_sufficient, 7: gate7_regime_quality,
    8: gate8_temporal_window_quality, 9: gate9_volatility_quality,
    10: gate10_forecast_quality, 11: gate11_snapshot_lineage,
    12: gate12_q_forecast, 13: gate13_parameter_package,
}


def evaluate(gate: int, *args, **kwargs) -> GateResult:
    """Address a single gate by number — the seam the ±1-unit matrix tests.
    An unknown gate number fails closed: the set is frozen at thirteen."""
    try:
        fn = GATES[gate]
    except KeyError:
        raise ValueError(
            f"GATE_NUMBER_QX: {gate!r} is not one of the thirteen hard gates "
            f"{sorted(GATES)} (no gate may be invented — G12)"
        ) from None
    return fn(*args, **kwargs)


def run_all(context: Mapping[str, Any]) -> Dict[str, Any]:
    """Evaluate all thirteen gates for one ``(symbol, timeframe)`` cell.

    ``context`` keys (all consumed, never recomputed): ``final_score``,
    ``window_qualities``, ``conflict_penalty``, ``redundancy_penalty``,
    ``mtf_state``, ``has_coarser_bars``, ``h_norm``, ``temporal_quality``,
    ``volatility_quality``, ``forecast``, ``snapshot_id``, ``payload``,
    ``lineage``, ``q_forecast``, ``package``, ``environment``.
    """
    results: List[GateResult] = [
        gate1_final_score(context["final_score"]),
        gate2_window_quality(context["window_qualities"]),
        gate3_conflict_penalty(context["conflict_penalty"]),
        gate4_redundancy_penalty(context["redundancy_penalty"]),
        gate5_mtf_conflicting(context["mtf_state"]),
        gate6_mtf_sufficient(context["mtf_state"],
                            has_coarser_bars=context.get("has_coarser_bars",
                                                         True)),
        gate7_regime_quality(context["h_norm"]),
        gate8_temporal_window_quality(context["temporal_quality"]),
        gate9_volatility_quality(context["volatility_quality"]),
        gate10_forecast_quality(context["forecast"],
                                environment=context.get("environment", "PAPER")),
        gate11_snapshot_lineage(context["snapshot_id"], context["payload"],
                               context["lineage"],
                               fabric_hash=context.get("fabric_hash")),
        gate12_q_forecast(context["q_forecast"]),
        gate13_parameter_package(context.get("package")),
    ]
    assert len(results) == GATE_COUNT
    failures = [r for r in results if not r.passed]
    return {
        "results": {r.number: r.to_dict() for r in results},
        "all_pass": not failures,
        "blocked_by": [r.number for r in failures],
        "reasons": [r.reason for r in failures],
        "action": QUARANTINE if failures else "ELIGIBLE",
        "q_min_tf": q_min_tf(context["timeframe"])
        if "timeframe" in context else None,
        "contract_version": CONTRACT_VERSION,
    }
