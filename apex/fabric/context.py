"""APEX_GEN5 — Context Fabric + context_confidence combiner (Ch.8 §8.0).

Blueprint: APEX_GEN5.md Ch.8 §8.0 (L14690–14768) and the frozen
FROZEN_BOOTSTRAP setup weights of Ch.10 §10.1 (L15236–15241). Every numeric
used here is read from ``params/setup_weights_v1.yaml`` /
``params/quality_weights_v1.yaml`` — never hardcoded (§9.5-10).

Normative content
-----------------
* Context Fabric JSON (Ch.8 §8.0): the aggregated situational state consumed
  read-only by Setup/Forecast/Decision. **"Context is never an order and never
  a permission."**
* ``context_confidence = sigmoid(Σ_k w_c[k]·x[k])`` with ``Σ_k w_c[k] = 1``
  over the seven documented ``x[k]`` slots (six governed names + the
  ``1 − divergence_magnitude`` slot) and the L1 default weights
  ``data_trust 0.35 · mtf_agreement 0.20 · evidence_agreement 0.15 ·
  regime_confidence 0.15 · (1 − regime_uncertainty) 0.10 ·
  (1 − divergence_magnitude) 0.05``; the temporal-window-validity slot is
  documented without a weight → it is admitted at weight 0.00 and reported
  (an unweighted input, never a dropped one).
* ``mtf_agreement``: ``ALIGNED 1.0 · PARTIALLY_ALIGNED 0.6 · STALE 0.3 ·
  CONFLICTING/UNAVAILABLE/INSUFFICIENT 0.0`` (verbatim table).
* **Solvency rule**: ``data_trust < 0.30`` or ``Q_raw < Q_min(tf)`` ⇒
  ``context_confidence = 0`` — full removal of the affected evidence, never
  zero-substitution.
* Propagation thresholds: ``≥ 0.70`` admissible · ``[0.40, 0.70)``
  confirmatory only · ``< 0.40`` (or ``data_trust < 0.30``) collapsed.
* Setup-score combiner (Global Contracts formula, cited by Ch.9 §9.0 and
  Ch.10 §10.1): ``raw_setup_score = Σ(w_i·s_i·q_i·f_i)``, then
  ``raw ×= (1 − conflict_penalty)`` — the **×0.6** multiplier of the frozen
  0.4 penalty — and ``×= (1 − redundancy_penalty)`` for an |ρ|>0.85 pair,
  whose primary effect is the **0.50× weight reduction** of the lower-quality
  engine (Ch.10 §10.1 / Ch.7 §14 precedent).
* **Vacuous-pass guard**: composition over an empty evidence set is *not* a
  pass. ``raw_setup_score`` of zero inputs is 0.0 with reason
  ``VACUOUS_NO_EVIDENCE`` — the frozen formula sums to 0 over no inputs, and
  silently granting a "full score" to nothing would turn an empty fabric into
  a permission.

Context freshness decays (``context_decay_per_bar = 0.05``,
``evidence_decay_per_bar = 0.02``) are governed parameters (ISSUE-CP6-002
discloses their mission-prompt provenance); the Q-ladder λ stays the frozen
``q_window_lambda = 0.1`` of §2.1, and the forecast decay stays ``0.1``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from apex.config import load_params
from apex.fabric.evidence import EvidenceFabric, FabricEvidenceRef, engine_group_of

CONTRACT_VERSION = "4.0.0"

# Ch.8 §8.0 verbatim: mtf_agreement mapping.
MTF_STATE_SCORES: Dict[str, float] = {
    "ALIGNED": 1.0,
    "PARTIALLY_ALIGNED": 0.6,
    "STALE": 0.3,
    "CONFLICTING": 0.0,
    "UNAVAILABLE": 0.0,
    "INSUFFICIENT": 0.0,
}

# Ch.8 §8.0 propagation thresholds (normative adjudication) + the governed
# band grid (0.70 / 0.50 / 0.30) used as the operational classification of
# the same scalar; both are READ from params/setup_weights_v1.yaml (§9.5-10)
# — the literals below are only the documented fallbacks asserted by the
# params test against the YAML (single source: the YAML).
BAND_ADMISSIBLE = 0.70
BAND_CONFIRMATORY = 0.40
CONTEXT_BAND_GRID: Tuple[float, ...] = (0.70, 0.50, 0.30)
SOLVENCY_DATA_TRUST_FLOOR = 0.30


def context_bands() -> Tuple[float, float, float]:
    """Governed band grid (admissible / confirmatory / collapsed)."""
    b = _setup_cfg()["context_bands"]
    return (float(b["admissible"]), float(b["confirmatory"]),
            float(b["collapsed"]))


def propagation_confirmatory_threshold() -> float:
    return float(_setup_cfg()["propagation_confirmatory_threshold"])


def data_trust_floor() -> float:
    return float(_setup_cfg()["data_trust_floor"])

# The twelve frozen FROZEN_BOOTSTRAP context/setup weights (Ch.10 §10.1).
CONTEXT_COMPONENTS_12: Tuple[Tuple[str, str], ...] = (
    ("structure", "w_structure"), ("liquidity", "w_liquidity"),
    ("volume", "w_volume"), ("volatility", "w_volatility"),
    ("fvg", "w_fvg"), ("orderblock", "w_orderblock"),
    ("rtm", "w_rtm"), ("wyckoff", "w_wyckoff"),
    ("trend", "w_trend"), ("momentum", "w_momentum"),
    ("regime", "w_regime"), ("temporal", "w_temporal"),
)

# Component → producing engine (Ch.10 §10.1 family evidence mapping; binds an
# engine's contribution to its component weight).
COMPONENT_ENGINE: Dict[str, str] = {
    "structure": "E01", "liquidity": "E02", "volume": "E03",
    "volatility": "E04", "fvg": "E05", "orderblock": "E06",
    "rtm": "E07", "wyckoff": "E08", "trend": "E09",
    "momentum": "E10", "regime": "E11", "temporal": "E12",
}

ENGINE_COMPONENT: Dict[str, str] = {e: c for c, e in COMPONENT_ENGINE.items()}

# Ch.8 §8.0 governed L1 default weights of the context combiner.
DEFAULT_COMBINER_WEIGHTS: Dict[str, float] = {
    "data_trust": 0.35,
    "mtf_agreement": 0.20,
    "evidence_agreement": 0.15,
    "regime_confidence": 0.15,
    "one_minus_regime_uncertainty": 0.10,
    "one_minus_divergence_magnitude": 0.05,
    "temporal_window_validity": 0.0,   # documented input, no documented weight
}

REDUNDANCY_HALVE_FACTOR = 0.50   # ρ > 0.85 ⇒ 0.50× the correlated component


def _setup_cfg() -> Dict[str, Any]:
    return load_params()["setup_weights"]


def raw_weight_map() -> Dict[str, float]:
    """The frozen weight map exactly as written in the YAML (``w_*`` keys)."""
    return dict(_setup_cfg()["weights"])


def context_weights() -> Dict[str, float]:
    """The frozen 12 context/setup weights, keyed by component name (the
    ``w_`` prefix of the YAML key stripped — a naming projection only, values
    verbatim, never re-scaled)."""
    return {k[2:] if k.startswith("w_") else k: float(v)
            for k, v in raw_weight_map().items()}


def normalized_context_weights() -> Dict[str, float]:
    """The active weights, normalized to sum to 1 (Ch.8 §8.0: "the active
    weights are normalized to sum to 1"). A set that does not sum to 1 is
    rescaled, never silently re-tuned; a negative weight fails closed."""
    w = context_weights()
    if any(v < 0 for v in w.values()):
        raise ValueError("CONTEXT_WEIGHT_NEGATIVE_QX: weights must be ≥ 0")
    total = sum(w.values())
    if total <= 0:
        raise ValueError("CONTEXT_WEIGHTS_EMPTY_QX: Σw must be > 0")
    return {k: v / total for k, v in w.items()}


def context_decay_per_bar() -> float:
    return float(_setup_cfg()["context_decay_per_bar"])


def evidence_decay_per_bar() -> float:
    return float(_setup_cfg()["evidence_decay_per_bar"])


def q_min_setup() -> float:
    return float(_setup_cfg()["Q_min_setup"])


def q_min_tf(timeframe: str) -> float:
    """Q_min(tf) of §2.1 (frozen table, read from the params YAML)."""
    table = load_params()["quality_weights"]["q_min_by_tf"]
    try:
        return float(table[timeframe])
    except KeyError:
        raise ValueError(
            f"E-VAL-022: no Q_min for timeframe {timeframe!r} (the frozen 14 "
            f"only)"
        ) from None


def solvency_check(*, data_trust: float, q_raw: Optional[float],
                   timeframe: str) -> Tuple[bool, str]:
    """Ch.8 §8.0 solvency rule. Returns ``(ok, reason)``."""
    if data_trust < data_trust_floor():
        return False, "SOLVENCY_DATA_TRUST"
    if q_raw is not None and q_raw < q_min_tf(timeframe):
        return False, "SOLVENCY_Q_MIN_TF"
    return True, "OK"


def band_of(confidence: float, bands: Optional[Sequence[float]] = None) -> str:
    """Operational band label on the governed band grid (0.70/0.50/0.30).

    This is a *classification* of the same bounded scalar; it grants nothing
    (Ch.8 §8.0: context is never an order and never a permission). Boundaries
    are inclusive at the band's own value.
    """
    if not (0.0 <= confidence <= 1.0) or confidence != confidence:
        raise ValueError("CONTEXT_BAND_INPUT_QX: confidence must be in [0,1]")
    hi, mid, lo = tuple(bands) if bands is not None else context_bands()
    if confidence >= hi:
        return "ADMISSIBLE"
    if confidence >= mid:
        return "CONFIRMATORY"
    if confidence >= lo:
        return "WEAK"
    return "COLLAPSED"


def propagation_band(confidence: float, data_trust: float) -> str:
    """Ch.8 §8.0 propagation thresholds — the normative adjudication.

    The third row ("``context_confidence < 0.40`` **or** ``data_trust < 0.30``
    ⇒ collapsed") is unconditional, so the data-trust arm is evaluated first.
    """
    if data_trust < data_trust_floor():
        return "COLLAPSED_DATA_TRUST"
    if confidence >= BAND_ADMISSIBLE:
        return "ADMISSIBLE_TO_FORECAST_DECISION"
    if confidence >= propagation_confirmatory_threshold():
        return "CONFIRMATORY_ONLY"
    return "COLLAPSED"


def evidence_agreement(members: Iterable[FabricEvidenceRef]) -> float:
    """``1 − normalized_disagreement`` (SL-2), weighted by the frozen twelve
    context weights of the producing engines.

    Disagreement within a dependency group is the weight share of the engines
    opposing the group's weighted-dominant direction, normalized by the total
    weight present. **No evidence present ⇒ 0.0** — agreement with nothing is
    not agreement with something (fail-closed, never a vacuous 1.0).
    """
    w = normalized_context_weights()
    by_engine: Dict[str, List[FabricEvidenceRef]] = {}
    for m in members:
        by_engine.setdefault(m.engine_id, []).append(m)
    if not by_engine:
        return 0.0
    weight_of = {eng: w[ENGINE_COMPONENT[eng]] for eng in by_engine}
    total = sum(weight_of.values())
    if total <= 0:
        return 0.0
    groups: Dict[str, List[str]] = {}
    for eng in by_engine:
        groups.setdefault(engine_group_of(eng), []).append(eng)
    disagreement = 0.0
    for _grp, engines in groups.items():
        s = sum(sum(m.direction * weight_of[e] / len(by_engine[e])
                    for m in by_engine[e]) for e in engines)
        dom = 0 if abs(s) < 1e-12 else (1 if s > 0 else -1)
        if dom == 0:
            continue
        for e in engines:
            for m in by_engine[e]:
                if m.direction * dom == -1:
                    disagreement += weight_of[e] / len(by_engine[e])
    normalized = min(1.0, disagreement / total)
    return max(0.0, 1.0 - normalized)


@dataclass(frozen=True)
class CombinerInputs:
    """The seven documented ``x[k]`` slots of the context_confidence combiner."""

    data_trust: float
    mtf_state: str
    evidence_agreement: float
    regime_confidence: float
    regime_uncertainty: float
    divergence_magnitude: float
    temporal_window_validity: float
    weights: Mapping[str, float] = field(
        default_factory=lambda: dict(DEFAULT_COMBINER_WEIGHTS))

    def __post_init__(self) -> None:
        for name in ("data_trust", "evidence_agreement", "regime_confidence",
                     "regime_uncertainty", "divergence_magnitude",
                     "temporal_window_validity"):
            v = getattr(self, name)
            if not (0.0 <= v <= 1.0) or v != v:
                raise ValueError(
                    f"COMBINER_INPUT_QX: {name} must be finite in [0,1], got {v!r}"
                )
        if self.mtf_state not in MTF_STATE_SCORES:
            raise ValueError(
                f"MTF_STATE_QX: {self.mtf_state!r} not in {sorted(MTF_STATE_SCORES)}"
            )
        w = dict(self.weights)
        if any(v < 0 for v in w.values()):
            raise ValueError("COMBINER_WEIGHT_NEGATIVE_QX")
        if sum(w.values()) <= 0:
            raise ValueError("COMBINER_WEIGHTS_EMPTY_QX")
        unknown = sorted(set(w) - set(DEFAULT_COMBINER_WEIGHTS))
        if unknown:
            raise ValueError(
                f"COMBINER_WEIGHT_KEY_QX: unknown weight names {unknown} — the "
                f"combiner has exactly the documented slots"
            )


def context_confidence(inp: CombinerInputs, *, timeframe: str,
                       q_raw: Optional[float] = None) -> Dict[str, Any]:
    """Bounded, versioned, calibrated context_confidence (Ch.8 §8.0)."""
    ok, reason = solvency_check(data_trust=inp.data_trust, q_raw=q_raw,
                                timeframe=timeframe)
    if not ok:
        # Solvency rule: confidence collapses to zero — full removal of the
        # affected evidence, never a zero-substituted continuation.
        return {
            "context_confidence": 0.0,
            "band": "COLLAPSED",
            "propagation": "COLLAPSED_" + reason,
            "solvency": {"ok": False, "reason": reason},
            "weights_normalized": {},
            "contract_version": CONTRACT_VERSION,
        }
    w = dict(inp.weights)
    total = sum(w.values())
    wn = {k: v / total for k, v in w.items()}
    z = (wn["data_trust"] * inp.data_trust
         + wn["mtf_agreement"] * mtf_agreement(inp.mtf_state)
         + wn["evidence_agreement"] * inp.evidence_agreement
         + wn["regime_confidence"] * inp.regime_confidence
         + wn["one_minus_regime_uncertainty"] * (1.0 - inp.regime_uncertainty)
         + wn["one_minus_divergence_magnitude"] * (1.0 - inp.divergence_magnitude)
         + wn["temporal_window_validity"] * inp.temporal_window_validity)
    # D59 ج۴: sigmoid(z) with z in [0, 1] is confined to about [0.526, 0.731],
    # so the band grid was unreachable. Gain is governed (decision_v1.yaml).
    from apex.decision.pipeline import load_decision_v1
    gain = float(load_decision_v1()["context_confidence_gain"])
    conf = 1.0 / (1.0 + math.exp(-gain * (z - 0.5)))
    return {
        "context_confidence": conf,
        "band": band_of(conf),
        "propagation": propagation_band(conf, inp.data_trust),
        "solvency": {"ok": True, "reason": "OK"},
        "weights_normalized": wn,
        "z": z,
        "contract_version": CONTRACT_VERSION,
    }


def mtf_agreement(mtf_state: str) -> float:
    try:
        return MTF_STATE_SCORES[mtf_state]
    except KeyError:
        raise ValueError(
            f"MTF_STATE_QX: {mtf_state!r} not in {sorted(MTF_STATE_SCORES)}"
        ) from None


@dataclass(frozen=True)
class ContextRecord:
    """The Ch.8 §8.0 Context Fabric JSON consumed read-only downstream."""

    market_regime: str
    mtf_state: str
    utc_window_state: str
    is_overlap: bool
    correlation_state: Dict[str, Any]
    divergence_state: Dict[str, Any]
    liquidity_state: Dict[str, Any]
    volatility_state: str
    structure_state: str
    portfolio_context: Dict[str, Any]
    data_trust: float
    conflict_state: str
    context_confidence: float
    as_of: int

    def to_dict(self) -> Dict[str, Any]:
        keys = ("market_regime", "mtf_state", "utc_window_state", "is_overlap",
                "correlation_state", "divergence_state", "liquidity_state",
                "volatility_state", "structure_state", "portfolio_context",
                "data_trust", "conflict_state", "context_confidence", "as_of")
        return {k: getattr(self, k) for k in keys}

    @classmethod
    def keys(cls) -> Tuple[str, ...]:
        return ("market_regime", "mtf_state", "utc_window_state", "is_overlap",
                "correlation_state", "divergence_state", "liquidity_state",
                "volatility_state", "structure_state", "portfolio_context",
                "data_trust", "conflict_state", "context_confidence", "as_of")

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ContextRecord":
        missing = [k for k in cls.keys() if k not in d]
        if missing:
            raise ValueError(
                f"CONTEXT_SCHEMA_QX: missing keys {missing} (Ch.8 §8.0 schema "
                f"is the producer-side contract, no key is optional)"
            )
        return cls(**{k: d[k] for k in cls.keys()})


def build_context(fabric: EvidenceFabric, *, market_regime: str,
                  mtf_state: str, utc_window_state: str, is_overlap: bool,
                  volatility_state: str, structure_state: str,
                  regime_confidence: float, regime_uncertainty: float,
                  divergence_magnitude: float, temporal_window_validity: float,
                  q_raw: Optional[float] = None,
                  correlation_state: Optional[Dict[str, Any]] = None,
                  divergence_state: Optional[Dict[str, Any]] = None,
                  liquidity_state: Optional[Dict[str, Any]] = None,
                  portfolio_context: Optional[Dict[str, Any]] = None,
                  weights: Optional[Mapping[str, float]] = None) -> Dict[str, Any]:
    """Assemble the Context Fabric JSON from an Evidence Fabric + the versioned
    context inputs. The confidence is always recomputed here — a caller cannot
    inject a number (context is produced, not declared)."""
    inp = CombinerInputs(
        data_trust=fabric.data_trust, mtf_state=mtf_state,
        evidence_agreement=evidence_agreement(fabric.members),
        regime_confidence=regime_confidence,
        regime_uncertainty=regime_uncertainty,
        divergence_magnitude=divergence_magnitude,
        temporal_window_validity=temporal_window_validity,
        weights=dict(weights) if weights else dict(DEFAULT_COMBINER_WEIGHTS),
    )
    res = context_confidence(inp, timeframe=fabric.timeframe, q_raw=q_raw)
    rec = ContextRecord(
        market_regime=market_regime, mtf_state=mtf_state,
        utc_window_state=utc_window_state, is_overlap=bool(is_overlap),
        correlation_state=dict(correlation_state or {}),
        divergence_state=dict(divergence_state or {}),
        liquidity_state=dict(liquidity_state or {}),
        volatility_state=volatility_state, structure_state=structure_state,
        portfolio_context=dict(portfolio_context or {}),
        data_trust=fabric.data_trust, conflict_state=fabric.conflict_state,
        context_confidence=res["context_confidence"], as_of=fabric.as_of,
    )
    out = dict(res)
    out["context"] = rec.to_dict()
    return out


# ---------------------------------------------------------------------------
# Setup-score combiner (Global Contracts formula, cited by Ch.9 §9.0 and
# Ch.10 §10.1). Kept here so Setup, Forecast and Decision share ONE scoring
# authority ("this formula is not restated here", Ch.9 §9.0).
# ---------------------------------------------------------------------------

def freshness_factor(age_bars: float) -> float:
    """f_i — evidence freshness on the governed evidence decay λ (0.02/bar)."""
    from apex.fabric.evidence import evidence_freshness
    return evidence_freshness(age_bars, evidence_decay_per_bar(),
                              what="evidence")


def raw_setup_score(s_i: Mapping[str, float], *,
                    q_i: Mapping[str, float],
                    f_i: Optional[Mapping[str, float]] = None) -> Dict[str, Any]:
    """``raw_setup_score = Σ(w_i·s_i·q_i·f_i)`` over the twelve frozen weights.

    **Vacuous-pass guard**: an empty ``s_i`` set returns 0.0 with
    ``VACUOUS_NO_EVIDENCE`` — an empty evidence set never scores, and a 0.0
    score makes Gate 1 (final score < Q_min_setup) quarantine the setup.
    """
    w = context_weights()
    unknown = sorted(set(s_i) - set(w))
    if unknown:
        raise ValueError(
            f"SETUP_COMPONENT_QX: {unknown} are not the twelve frozen "
            f"components {sorted(w)}"
        )
    if not s_i:
        return {"raw": 0.0, "reason": "VACUOUS_NO_EVIDENCE", "admitted": False,
                "terms": {}}
    missing_q = sorted(set(s_i) - set(q_i))
    if missing_q:
        raise ValueError(
            f"SETUP_FACTOR_QX: q_i missing for components {missing_q} — "
            f"quality is a mandatory factor of the frozen formula"
        )
    terms: Dict[str, float] = {}
    raw = 0.0
    for name in s_i:
        s = float(s_i[name])
        q = float(q_i[name])
        f = 1.0 if f_i is None else float(f_i.get(name, 1.0))
        for label, v in (("s_i", s), ("q_i", q), ("f_i", f)):
            if not (0.0 <= v <= 1.0) or v != v:
                raise ValueError(
                    f"SETUP_FACTOR_QX: {label}[{name}] must be finite in [0,1]"
                )
        t = w[name] * s * q * f
        terms[name] = t
        raw += t
    return {"raw": raw, "reason": "OK", "admitted": True, "terms": terms}


def conflict_multiplier(conflict_penalty: Optional[float] = None) -> float:
    """``raw *= (1 − conflict_penalty)`` with the frozen 0.4 ⇒ **×0.6**
    (Ch.10 §10.1: "required evidences with direction_i·direction_j = −1 ⇒
    raw *= (1−0.4)")."""
    if conflict_penalty is None:
        conflict_penalty = float(_setup_cfg()["conflict_penalty"])
    if not (0.0 <= conflict_penalty <= 1.0):
        raise ValueError("CONFLICT_PENALTY_QX: penalty must be in [0,1]")
    return 1.0 - conflict_penalty


def redundancy_rho_threshold() -> float:
    return float(_setup_cfg()["redundancy_rho_threshold"])


def redundancy_penalty_value() -> float:
    return float(_setup_cfg()["redundancy_penalty"])


def redundancy_rho(s_a: Sequence[float], s_b: Sequence[float], *,
                   n: Optional[int] = None, min_points: int = 20) -> Dict[str, Any]:
    """Ch.10 §10.1 redundancy law: Pearson ρ on the last ``n=48`` OK points of
    the two ``s_i`` series (same symbol+TF). Fewer than 20 OK points ⇒ skip
    (no penalty is invented; the skip reason is carried so nothing is silently
    dropped either).
    """
    n = int(_setup_cfg()["redundancy_window_n"]) if n is None else n
    a = [v for v in list(s_a)[-n:] if v == v]
    b = [v for v in list(s_b)[-n:] if v == v]
    k = min(len(a), len(b))
    a, b = a[-k:], b[-k:]
    if k < min_points:
        return {"rho": None, "points": k, "skipped": True,
                "reason": "REDUNDANCY_INSUFFICIENT_POINTS"}
    ma, mb = sum(a) / k, sum(b) / k
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / k
    va = sum((x - ma) ** 2 for x in a) / k
    vb = sum((y - mb) ** 2 for y in b) / k
    denom = math.sqrt(va * vb)
    rho = cov / denom if denom > 1e-12 else 0.0
    return {"rho": rho, "points": k, "skipped": False, "reason": "OK"}


def _pair_victim(a: str, b: str, qualities: Mapping[str, float]) -> str:
    qa, qb = float(qualities.get(a, 0.0)), float(qualities.get(b, 0.0))
    if qa < qb:
        return a
    if qb < qa:
        return b
    # quality tie: the lower engine id is the victim (higher id is kept)
    return a if COMPONENT_ENGINE[a] <= COMPONENT_ENGINE[b] else b


def apply_redundancy(terms: Mapping[str, float], qualities: Mapping[str, float],
                     rho: Optional[float], *,
                     halve_factor: float = REDUNDANCY_HALVE_FACTOR,
                     pairs: Optional[Sequence[Tuple[str, str, Optional[float]]]] = None
                     ) -> Dict[str, Any]:
    """``|ρ| > 0.85`` ⇒ drop the lower-Q engine; tie ⇒ the higher engine id
    (Ch.10 §10.1). The drop is executed as the **0.50× weight reduction** of
    the victim's contribution ("Redundancy threshold 0.85 halves the weight of
    correlated components", Ch.7 §14 as applied by the Setup combiner) and is
    always recorded — never silent.
    """
    # D59 ج۶: each correlated pair halves its own lower-quality member.
    # A single scalar rho is the legacy one-pair call. A pairs list never
    # blankets an uncorrelated component.
    if pairs is not None:
        out = dict(terms)
        victims: List[str] = []
        thr = redundancy_rho_threshold()
        for a, b, pair_rho in pairs:
            if pair_rho is None or abs(float(pair_rho)) <= thr:
                continue
            if a not in out or b not in out:
                continue
            victim = _pair_victim(a, b, qualities)
            out[victim] = out[victim] * halve_factor
            victims.append(victim)
        if not victims:
            return {"terms": out, "victim": None, "victims": [],
                    "halve_factor": 1.0, "reason": "NO_REDUNDANCY"}
        return {"terms": out, "victim": victims[0], "victims": victims,
                "halve_factor": halve_factor, "reason": "REDUNDANCY_HALVED"}
    if rho is None or abs(rho) <= redundancy_rho_threshold():
        return {"terms": dict(terms), "victim": None, "halve_factor": 1.0,
                "reason": "NO_REDUNDANCY"}
    if not terms:
        return {"terms": {}, "victim": None, "halve_factor": 1.0,
                "reason": "NO_REDUNDANCY_NO_TERMS"}
    # keep the best, drop the worst: sort by (quality, engine id) ascending —
    # the first element is the victim; on a quality tie the LOWER engine id
    # sorts first, so the higher engine id is the one kept.
    order = sorted(terms, key=lambda k: (qualities.get(k, 0.0),
                                         COMPONENT_ENGINE[k]))
    victim = order[0]
    out = dict(terms)
    out[victim] = out[victim] * halve_factor
    return {"terms": out, "victim": victim, "halve_factor": halve_factor,
            "reason": "REDUNDANCY_HALVED"}


def setup_score(fabric: EvidenceFabric, *, s_i: Mapping[str, float],
                q_i: Mapping[str, float],
                f_i: Optional[Mapping[str, float]] = None,
                required_conflict: bool = False,
                optional_conflict_penalty: float = 0.0,
                redundancy_rho: Optional[float] = None,
                redundancy_pairs: Optional[Sequence[Tuple[str, str, Optional[float]]]] = None,
                component_terms: Optional[Mapping[str, float]] = None,
                ) -> Dict[str, Any]:
    """The one scored composition: raw → redundancy halve → conflict ×0.6 →
    redundancy penalty (Global Contracts), with the Ch.10 §10.1 specifics:
    conflict multiplies the raw score only for **required** evidences
    ("optional conflict adds penalty only")."""
    if component_terms is not None:
        raw_res = {"raw": float(sum(component_terms.values())), "reason": "OK",
                   "admitted": True, "terms": dict(component_terms)}
    elif fabric.is_empty():
        raw_res = {"raw": 0.0, "reason": "VACUOUS_NO_EVIDENCE",
                   "admitted": False, "terms": {}}
    else:
        present = {name for name, eng in COMPONENT_ENGINE.items()
                   if any(m.engine_id == eng for m in fabric.members)}
        # "absent components contribute nothing" (raw_setup_score law): an
        # engine may sit in the fabric while the setup layer scores no term
        # for its component — that component is UNSCORABLE input, never a
        # KeyError and never a zero-substituted term.
        present &= set(s_i)
        if not present:
            raw_res = {"raw": 0.0, "reason": "VACUOUS_NO_EVIDENCE",
                       "admitted": False, "terms": {}}
        else:
            raw_res = raw_setup_score(
                {k: s_i[k] for k in present},
                q_i={k: q_i[k] for k in present},
                f_i=None if f_i is None else {k: f_i[k] for k in present
                                              if k in f_i},
            )
    conf_mult = conflict_multiplier() if required_conflict else 1.0
    red = apply_redundancy(raw_res["terms"],
                           {k: q_i.get(k, 0.0) for k in raw_res["terms"]},
                           redundancy_rho, pairs=redundancy_pairs)
    red_mult = 1.0 - redundancy_penalty_value() if red["victim"] else 1.0
    final = sum(red["terms"].values()) * conf_mult * red_mult \
        - float(optional_conflict_penalty or 0.0)
    return {
        "raw": raw_res["raw"],
        "final": final,
        "conflict_multiplier": conf_mult,
        "redundancy_multiplier": red_mult,
        "redundancy": red,
        "vacuous": not raw_res["admitted"],
        "reason": raw_res["reason"],
        "terms": red["terms"],
        "contract_version": CONTRACT_VERSION,
    }
