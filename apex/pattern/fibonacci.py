"""APEX_GEN5 — Fibonacci levels, in-repo (Ch.9 §9.0 Pattern contract + §9.5-15).

Blueprint: ``Level(r) = A + r·(B − A)`` (Ch.9 §9.0, L15021) and §9.5-15:
"**Identity:** ``intent_id`` = UUIDv7. Fibonacci is
``apex/pattern/fibonacci.py`` (not a network service)."

This module is therefore a pure, dependency-free computation. It never opens
a socket, never imports a transport library, and never reads the environment:
the "no network" rule is enforced by a source-level test (T_PATTERN seam).

Ratio sets are in-code governed defaults following the engine precedent
(ISSUE-CP2-006: frozen defaults + ``get_params()``, no seventh YAML file).
The harmonic families that *use* these levels (Three Drives / Gartley / Bat)
remain research-only (Ch.9 §9.1 round-2 demotion) — levels are computed for
them, but no scoring admission follows from that (§9.0: "harmonic families
remain research-only until promoted through the family registry").
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

CONTRACT_VERSION = "4.0.0"

GOLDEN_RATIO = 1.6180339887498949   # φ
GOLDEN_CONJUGATE = 0.6180339887498949  # φ − 1

# Ch.9 §9.0 retracement / extension / projection / expansion / confluence.
RETRACE_RATIOS: Tuple[float, ...] = (0.236, 0.382, 0.5, 0.618, 0.786)
EXTENSION_RATIOS: Tuple[float, ...] = (1.0, 1.272, 1.618, 2.0, 2.618)
PROJECTION_RATIOS: Tuple[float, ...] = (0.618, 1.0, 1.618)
EXPANSION_RATIOS: Tuple[float, ...] = (0.618, 1.0, 1.272, 1.618)

# §9.1 (Gartley/Bat rows) — recorded for the research-only harmonic contract.
HARMONIC_RATIOS: Dict[str, float] = {"gartley_ab": 0.618, "bat_ab_low": 0.382,
                                     "bat_ab_high": 0.5, "bat_prz": 0.886}

FIB_PARAMS: Dict[str, Any] = {
    "retrace": RETRACE_RATIOS,
    "extension": EXTENSION_RATIOS,
    "projection": PROJECTION_RATIOS,
    "expansion": EXPANSION_RATIOS,
    "confluence_atr_mult": 0.15,     # level-cluster tolerance = the θ_eq row
    "ote_low": 0.62,                 # E07 OTE band, registered verbatim (§7)
    "ote_high": 0.79,
    "ote_star": 0.705,
    "eps": 1e-8,
}


def get_params(overrides: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """In-code governed defaults; unknown keys fail closed (engine precedent)."""
    ov = dict(overrides or {})
    unknown = sorted(set(ov) - set(FIB_PARAMS))
    if unknown:
        raise ValueError(f"UNKNOWN_FIB_PARAM_QX: {unknown}")
    return {**FIB_PARAMS, **ov}


def level(a: float, b: float, r: float) -> float:
    """The frozen formula, verbatim: ``Level(r) = A + r·(B − A)``."""
    if r != r or a != a or b != b:
        raise ValueError("FIB_NAN_QX: non-finite input")
    return a + r * (b - a)


def _validate_segment(a: float, b: float) -> None:
    for name, v in (("A", a), ("B", b)):
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError(f"FIB_SEGMENT_QX: {name} must be finite")
    if abs(b - a) < 1e-12:
        raise ValueError(
            f"FIB_DEGENERATE_LEG_QX: A == B ({a}) has no direction to "
            f"measure — never a zero-length level set"
        )


def retracements(a: float, b: float, *, ratios: Optional[Sequence[float]] = None,
                 params: Optional[Mapping[str, Any]] = None) -> Dict[float, float]:
    """Retracement ladder of the leg A→B (``r`` measured from B back toward A:
    ``Level(r) = B + r·(A − B)`` is the same law with the leg reversed — the
    frozen ``Level(r) = A + r·(B − A)`` is used for the *projection* family).
    """
    _validate_segment(a, b)
    p = get_params(params)
    rs = tuple(ratios) if ratios is not None else p["retrace"]
    return {r: b + r * (a - b) for r in rs}


def projections(a: float, b: float, *, ratios: Optional[Sequence[float]] = None,
                params: Optional[Mapping[str, Any]] = None) -> Dict[float, float]:
    """``Level(r) = A + r·(B − A)`` — the frozen formula itself."""
    _validate_segment(a, b)
    p = get_params(params)
    rs = tuple(ratios) if ratios is not None else p["projection"]
    return {r: level(a, b, r) for r in rs}


def extensions(a: float, b: float, *, ratios: Optional[Sequence[float]] = None,
               params: Optional[Mapping[str, Any]] = None) -> Dict[float, float]:
    """Extension ladder beyond B along the A→B direction (r > 1)."""
    _validate_segment(a, b)
    p = get_params(params)
    rs = tuple(ratios) if ratios is not None else p["extension"]
    bad = [r for r in rs if r < 1.0]
    if bad:
        raise ValueError(f"FIB_EXTENSION_RATIO_QX: {bad} < 1.0 is not an extension")
    return {r: level(a, b, r) for r in rs}


def expansion(a: float, b: float, c: float, *,
              ratios: Optional[Sequence[float]] = None,
              params: Optional[Mapping[str, Any]] = None) -> Dict[float, float]:
    """AB=CD expansion: the CD leg is measured as ``C + r·(B − A)`` (the
    XABCD convention, Ch.9 §9.0 harmonic family definition)."""
    _validate_segment(a, b)
    if c != c or c in (float("inf"), float("-inf")):
        raise ValueError("FIB_SEGMENT_QX: C must be finite")
    p = get_params(params)
    rs = tuple(ratios) if ratios is not None else p["expansion"]
    delta = b - a
    return {r: c + r * delta for r in rs}


def harmonic_prz(x: float, a: float, b: float, *, pattern: str,
                 tolerance_atr: Optional[float] = None) -> Dict[str, Any]:
    """XABCD potential-reversal zone for the two registered harmonic ratios
    (Gartley AB = 0.618 of XA; Bat AB = 0.382–0.5 of XA with PRZ at 0.886).

    "Harmonic (record tolerance — never assume perfection)" (Ch.9 §9.0): a
    mismatch returns the measured deviation instead of a forced fit, and the
    pattern stays research-only regardless of the outcome.
    """
    xa = a - x
    if abs(xa) < 1e-12:
        raise ValueError("FIB_HARMONIC_LEG_QX: XA is degenerate")
    ab_ratio = (a - b) / xa if xa else float("nan")
    spec = {"GARTLEY": (HARMONIC_RATIOS["gartley_ab"], HARMONIC_RATIOS["gartley_ab"]),
            "BAT": (HARMONIC_RATIOS["bat_ab_low"], HARMONIC_RATIOS["bat_ab_high"])}
    if pattern not in spec:
        raise ValueError(f"FIB_HARMONIC_PATTERN_QX: {pattern!r} not in {sorted(spec)}")
    lo, hi = spec[pattern]
    tol = (abs(ab_ratio - lo) if ab_ratio < lo
           else (ab_ratio - hi) if ab_ratio > hi else 0.0)
    # CD completion (record tolerance only, never a forced fit):
    #   GARTLEY — AB = CD ⇒ D = 2B − A  (CD mirrors BA in size and direction)
    #   BAT     — PRZ at 0.886 of XA ⇒ D = X + 0.886·(A − X)
    prz = ((x + HARMONIC_RATIOS["bat_prz"] * xa) if pattern == "BAT"
           else (2.0 * b - a))
    return {"pattern": pattern, "ab_ratio": ab_ratio, "in_band": tol == 0.0,
            "deviation": tol, "prz": prz,
            "lifecycle_status": "RESEARCH_ONLY",
            "note": "record tolerance — never assume perfection (Ch.9 §9.0); "
                    "the row is RESEARCH_ONLY and produces no setup-scoring "
                    "evidence (§9.1 round-2 demotion)"}


def confluence(levels: Mapping[str, Sequence[float]], *, atr: float,
               params: Optional[Mapping[str, Any]] = None) -> List[Dict[str, Any]]:
    """Cluster levels from independent constructions; a cluster is a set of
    levels within ``confluence_atr_mult · ATR`` (the θ_eq tolerance family).

    Each cluster lists its members — a confluence is *recorded*, never
    silently averaged away.
    """
    p = get_params(params)
    if atr is None or atr <= 0 or atr != atr:
        raise ValueError("FIB_ATR_QX: a positive governed ATR is required")
    tol = p["confluence_atr_mult"] * atr
    flat: List[Tuple[float, str]] = []
    for src, vals in levels.items():
        for v in vals:
            if v != v:
                raise ValueError(f"FIB_NAN_QX: {src} carries a NaN level")
            flat.append((float(v), src))
    flat.sort()
    clusters: List[Dict[str, Any]] = []
    cur: List[Tuple[float, str]] = []
    for v, src in flat:
        if cur and v - cur[-1][0] > tol:
            clusters.append(cur)
            cur = []
        cur.append((v, src))
    if cur:
        clusters.append(cur)
    out = []
    for c in clusters:
        if len(c) < 2:
            continue
        vals = [v for v, _ in c]
        out.append({"centre": sum(vals) / len(vals), "spread": max(vals) - min(vals),
                    "members": [{"level": v, "source": s} for v, s in c],
                    "count": len(c)})
    return out


def ote_zone(a: float, b: float, *, params: Optional[Mapping[str, Any]] = None
              ) -> Dict[str, float]:
    """Optimal Trade Entry band of the leg — the frozen E07 values 0.62–0.79
    with the star at 0.705, re-expressed on the Fibonacci ladder (Ch.9 §9.0
    retracement family; E07 owns the RTM usage, this is the level math)."""
    _validate_segment(a, b)
    p = get_params(params)
    lo = level(b, a, p["ote_low"])
    hi = level(b, a, p["ote_high"])
    star = level(b, a, p["ote_star"])
    return {"lo": min(lo, hi), "hi": max(lo, hi), "star": star,
            "band": (p["ote_low"], p["ote_high"])}


@dataclass(frozen=True)
class FibLevel:
    ratio: float
    price: float
    kind: str
    source_leg: Tuple[float, float]

    def to_dict(self) -> Dict[str, Any]:
        return {"ratio": self.ratio, "price": self.price, "kind": self.kind,
                "source_leg": list(self.source_leg),
                "contract_version": CONTRACT_VERSION}


def ladder(a: float, b: float, *, kinds: Sequence[str] = ("retrace", "extension"),
           params: Optional[Mapping[str, Any]] = None) -> List[FibLevel]:
    """The full level set as records (never a bare list of floats)."""
    p = get_params(params)
    out: List[FibLevel] = []
    for kind in kinds:
        if kind not in ("retrace", "extension", "projection", "expansion"):
            raise ValueError(f"FIB_KIND_QX: {kind!r} unknown")
        if kind == "retrace":
            for r, v in retracements(a, b, params=p).items():
                out.append(FibLevel(r, v, kind, (a, b)))
        elif kind == "extension":
            for r, v in extensions(a, b, params=p).items():
                out.append(FibLevel(r, v, kind, (a, b)))
        elif kind == "projection":
            for r, v in projections(a, b, params=p).items():
                out.append(FibLevel(r, v, kind, (a, b)))
        else:
            raise ValueError(
                "FIB_KIND_QX: expansion needs a third pivot — call expansion()")
    return out


def golden_identities() -> Dict[str, float]:
    """The identities the frozen text relies on: 0.618 = φ−1 and
    0.786 = √0.618 (L8309). Exposed for the conformance test, never used to
    re-derive a governed ratio set."""
    return {
        "phi": GOLDEN_RATIO,
        "phi_conjugate": GOLDEN_CONJUGATE,
        "sqrt_0618": math.sqrt(0.618),
        "one_over_phi": 1.0 / GOLDEN_RATIO,
    }


__all__ = ["CONTRACT_VERSION", "EXTENSION_RATIOS", "EXPANSION_RATIOS",
           "FibLevel", "GOLDEN_CONJUGATE", "GOLDEN_RATIO", "HARMONIC_RATIOS",
           "PROJECTION_RATIOS", "RETRACE_RATIOS", "confluence",
           "extensions", "expansion", "get_params", "golden_identities",
           "harmonic_prz", "level", "ladder", "ote_zone", "projections",
           "retracements"]
