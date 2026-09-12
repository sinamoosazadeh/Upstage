"""APEX_GEN5 — Conflict policy package (Ch.8 §8.1–§8.3, SL-2/SL-7/SL-8/SL-11).

Blueprint: APEX_GEN5.md Ch.8 §8.1 (L14770–14870) + §8.2 (L14871–14900) +
§8.3 (L14901–14913).

"Conflict never creates permission" (Ch.8 heading). The package is the single
producer of the two penalty values the Setup gates project
(``conflict_penalty``, ``redundancy_penalty``); it is *not* a second, parallel
definition (Ch.8 §8.1 "Mapping to frozen anchors").

Terminal mapping (verbatim, L14820–14828)::

    if mtf_conflict == CONFLICTING:               out = HARD_CONFLICT
    elif disagreement >= 0.60:                    out = HARD_CONFLICT
    elif disagreement >= 0.35:                    out = MATERIAL_CONFLICT
    elif data_trust < 0.30 or Q_raw < Q_min(tf):  out = INSUFFICIENT_EVIDENCE
    elif disagreement < 0.35 and no hard flags:   out = CONSENSUS
    else:                                         out = INSUFFICIENT_EVIDENCE

Safe monotonicity (normative): rising disagreement, staleness or uncertainty
can never *grant* permission — a failed check is veto 9 of SL-5.

Seven invariants (complete definition, L14849–14857); any violation is
FAIL_CLOSED, not a warning.
"""

from __future__ import annotations

import dataclasses
import enum
from dataclasses import dataclass
from typing import (
    Any, ClassVar, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple,
)

from apex.config import load_params
from apex.fabric.context import q_min_tf
from apex.fabric.evidence import FabricEvidenceRef, engine_group_of

CONTRACT_VERSION = "4.0.0"

CONSENSUS = "CONSENSUS"
MATERIAL_CONFLICT = "MATERIAL_CONFLICT"
HARD_CONFLICT = "HARD_CONFLICT"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

CONFLICT_OUTPUTS: Tuple[str, ...] = (
    CONSENSUS, MATERIAL_CONFLICT, HARD_CONFLICT, INSUFFICIENT_EVIDENCE,
)

HARD_DISAGREEMENT = 0.60     # ≥ → HARD_CONFLICT (verbatim table)
MATERIAL_DISAGREEMENT = 0.35  # ≥ → MATERIAL_CONFLICT, < → CONSENSUS-eligible

MTF_STATES = ("ALIGNED", "PARTIALLY_ALIGNED", "CONFLICTING", "STALE",
              "UNAVAILABLE", "INSUFFICIENT")

# Gate projections (Ch.8 §8.1 "Mapping to frozen anchors" + Ch.10 §10.1).
GATE3_CONFLICT_THRESHOLD = 0.5
GATE4_REDUNDANCY_THRESHOLD = 0.3


class InvariantViolation(RuntimeError):
    """A violated invariant is FAIL_CLOSED (Ch.8 §8.1) — never a warning."""


SEVEN_INVARIANTS: Dict[str, str] = {
    "I1": "Point-in-time: availability_time <= as_of for every input; "
          "CANDIDATE → ACTIVE transitions use only subsequent CLOSED candles",
    "I2": "Determinism: output is a pure function of input; replay is "
          "byte-identical; no unseeded randomness",
    "I3": "Safe monotonicity: rising conflict/uncertainty never grants "
          "permission or increases risk (permission-monotone downward)",
    "I4": "Reconcile-first: no downstream state reaches RECONCILED before "
          "ledger ↔ exchange agreement (SL-6)",
    "I5": "Immutable ledger: hash-chained ledger; corrections append "
          "revisions, never rewrite (SL-6)",
    "I6": "Fresh and closed inputs: every probability and decision is "
          "computed only on fresh, valid, CLOSED data",
    "I7": "Non-permission by evidence: evidence, quality, and context never "
          "grant permission; they restrict decisions only through vetoes "
          "and caps",
}

# The §8.1 conflict-list ordering: the four structured outputs in increasing
# severity of restriction (used ONLY for the monotonicity check, never as a
# permission ladder).
_OUTPUT_RESTRICTION: Dict[str, int] = {
    CONSENSUS: 0, MATERIAL_CONFLICT: 1,
    INSUFFICIENT_EVIDENCE: 2, HARD_CONFLICT: 3,
}


@dataclass(frozen=True)
class ConflictRecord:
    """The §8.1 structured record (exactly these fields, in order)."""

    conflict_id: str
    disagreement: float
    quality_asymmetry: float
    redundancy: float
    uncertainty: float
    mtf_conflict: str
    stale_fraction: float
    regime_state: str
    action_policy: str
    package_id: str
    snapshot_id: str
    lineage: Tuple[str, ...]

    REQUIRED_FLOATS: ClassVar[Tuple[str, ...]] = (
        "disagreement", "quality_asymmetry", "redundancy", "uncertainty",
        "stale_fraction",
    )

    def __post_init__(self) -> None:
        for name in self.REQUIRED_FLOATS:
            v = getattr(self, name)
            if not (0.0 <= v <= 1.0) or v != v:
                raise ValueError(
                    f"CONFLICT_COMPONENT_QX: {name} must be finite in [0,1], "
                    f"got {v!r}"
                )
        if self.mtf_conflict not in MTF_STATES:
            raise ValueError(
                f"MTF_STATE_QX: {self.mtf_conflict!r} not in {MTF_STATES}"
            )
        if not self.snapshot_id or not self.package_id:
            raise ValueError("CONFLICT_IDENTITY_QX: snapshot_id/package_id mandatory")
        if not self.lineage:
            raise ValueError("CONFLICT_LINEAGE_QX: lineage is mandatory")


def disagreement_of(members: Iterable[FabricEvidenceRef]) -> float:
    """Direction/class disagreement between engines of the same dependency
    group (§8.1 component table), on the same group law as
    ``apex.fabric.context.evidence_agreement`` (one law, not two: 1 − this).
    """
    from apex.fabric.context import evidence_agreement
    ms = list(members)
    if not ms:
        return 1.0           # disagreement with nothing is total: fail-closed
    return max(0.0, 1.0 - evidence_agreement(ms))


def quality_asymmetry_of(members: Sequence[float]) -> float:
    """Quality gap between the strongest and the weakest evidence (§8.1)."""
    vals = [v for v in members]
    if not vals:
        raise ValueError("CONFLICT_EMPTY_QUALITY_QX: no evidence to compare")
    return max(vals) - min(vals)


def stale_fraction_of(ages_bars: Sequence[float], expiry_age_bars: float) -> float:
    """Fraction of stale evidence (age/decay, §8.1); stale = age ≥ the 5×TF
    expiry horizon of the SL-14 ladder (apex.fabric.evidence.expiry_age_bars).
    """
    if expiry_age_bars <= 0:
        raise ValueError("STALE_EXPIRY_QX: expiry horizon must be > 0")
    if not ages_bars:
        return 0.0
    stale = sum(1 for a in ages_bars if a * (expiry_age_bars / 5.0) >= expiry_age_bars)
    return stale / len(ages_bars)


def penalties(conflict_state: str, *, redundancy_rho: Optional[float] = None
               ) -> Dict[str, float]:
    """The two operational penalty values consumed by Setup Gates 3/4.

    They are *produced* here (single authority) and *projected* by the gates;
    the numbers themselves are the frozen values of the Cross-Domain row
    (``conflict_penalty`` / ``redundancy_penalty`` in
    ``params/setup_weights_v1.yaml``) — never re-interpolated. A conflict of
    state MATERIAL/HARD carries the frozen conflict penalty; the redundancy
    penalty applies only when a measured |ρ| exceeds the frozen threshold.
    """
    s = load_params()["setup_weights"]
    conflict_penalty = (float(s["conflict_penalty"])
                        if conflict_state in (MATERIAL_CONFLICT, HARD_CONFLICT)
                        else 0.0)
    red_active = (redundancy_rho is not None
                  and abs(redundancy_rho) > float(s["redundancy_rho_threshold"]))
    return {"conflict_penalty": conflict_penalty,
            "redundancy_penalty": float(s["redundancy_penalty"]) if red_active else 0.0}


def resolve(*, disagreement: float, data_trust: float, q_raw: Optional[float],
            timeframe: str, mtf_conflict: str = "ALIGNED",
            hard_flags: Sequence[str] = (),
            uncertainty: float = 0.0, stale_fraction: float = 0.0,
            redundancy: float = 0.0, quality_asymmetry: float = 0.0,
            redundancy_rho: Optional[float] = None,
            regime_state: str = "RANGE",
            conflict_id: str = "cfl_conflict", package_id: str = "pkg_0",
            snapshot_id: str = "snap_0",
            lineage: Sequence[str] = ("lineage_root",)) -> Dict[str, Any]:
    """Terminal mapping (§8.1) + the ConflictRecord. Exactly one output.

    Fail-closed guards before any classification: unknown MTF state, unknown
    timeframe (no Q_min) and out-of-range components raise — the policy never
    adjudicates on inputs it cannot interpret.
    """
    if mtf_conflict not in MTF_STATES:
        raise ValueError(f"MTF_STATE_QX: {mtf_conflict!r} not in {MTF_STATES}")
    q_min = q_min_tf(timeframe)              # raises for a TF outside the 14
    rec = ConflictRecord(
        conflict_id=conflict_id, disagreement=disagreement,
        quality_asymmetry=quality_asymmetry, redundancy=redundancy,
        uncertainty=uncertainty, mtf_conflict=mtf_conflict,
        stale_fraction=stale_fraction, regime_state=regime_state,
        action_policy="NONE", package_id=package_id, snapshot_id=snapshot_id,
        lineage=tuple(lineage),
    )
    hard = bool(hard_flags)
    if mtf_conflict == "CONFLICTING":
        out = HARD_CONFLICT
    elif disagreement >= HARD_DISAGREEMENT:
        out = HARD_CONFLICT
    elif disagreement >= MATERIAL_DISAGREEMENT:
        out = MATERIAL_CONFLICT
    elif data_trust < 0.30 or q_raw is None or q_raw < q_min:
        out = INSUFFICIENT_EVIDENCE
    elif disagreement < MATERIAL_DISAGREEMENT and not hard:
        out = CONSENSUS
    else:
        out = INSUFFICIENT_EVIDENCE
    # `redundancy` (the [0,1] semantic-overlap component of the record) and
    # the measured |ρ| of the two s_i series are distinct inputs: the Gate-4
    # penalty is produced from the ρ measurement (Ch.10 §10.1), never from the
    # component field.
    pen = penalties(out, redundancy_rho=redundancy_rho)
    return {
        "output": out,
        "record": rec,
        "conflict_penalty": pen["conflict_penalty"],
        "redundancy_penalty": pen["redundancy_penalty"],
        "gate_projection": {
            "gate3_block": pen["conflict_penalty"] > GATE3_CONFLICT_THRESHOLD,
            "gate4_block": pen["redundancy_penalty"] > GATE4_REDUNDANCY_THRESHOLD,
        },
        "contract_version": CONTRACT_VERSION,
    }


def monotone_ok(*, is_risk_increase: bool, uncertainty_is_rising: bool) -> bool:
    """Executable safe-monotonicity check (§8.1).

    A failed check is the anti-monotonicity veto (veto 9 of SL-5) — the Risk
    Kernel owns the veto; this function only reports the condition.
    """
    return not (is_risk_increase and uncertainty_is_rising)


def assert_permission_monotone(before: Mapping[str, Any], after: Mapping[str, Any]
                               ) -> None:
    """T_CONFLICT property: raising any uncertainty input can never move the
    output toward CONSENSUS (i.e. toward *less* restriction). Raises the
    fail-closed violation (I3) instead of warning.
    """
    a = _OUTPUT_RESTRICTION[before["output"]]
    b = _OUTPUT_RESTRICTION[after["output"]]
    if b < a:
        raise InvariantViolation(
            f"I3 VIOLATION: conflict output moved from {before['output']} to "
            f"{after['output']} while uncertainty rose — permission was "
            f"granted by rising conflict"
        )


def correlation_exposure(*, rho: float, open_notional: Sequence[float],
                         proposed_notional: float,
                         cap: Optional[float] = None) -> Dict[str, Any]:
    """The §8.2 exposure rule, implemented in its verbatim form::

        rho = weighted-average correlation over the shared risk-factor window
        if rho > correlation_cap:            # governed default 0.70 (SL-12)
            return REDUCE(proposal, to_correlation_cap)     # SL-5 REDUCE path

    ``rho`` is the weighted-average correlation of the in-window
    CorrelationRecord estimates (never re-consumed outside its window/scope).
    The bound is strict (``> cap``): at ``rho == cap`` nothing is reduced.
    ``REDUCE(proposal, to_correlation_cap)`` scales the *proposal* so that
    ``rho · combined`` lands exactly on the cap (the Ch.15 REDUCE path —
    never a silent rejection, never an override of a veto).
    """
    if not (-1.0 <= rho <= 1.0) or rho != rho:
        raise ValueError("CORRELATION_RHO_QX: rho must be finite in [-1,1]")
    if proposed_notional < 0:
        raise ValueError("CORRELATION_PROPOSAL_QX: notional must be ≥ 0")
    if cap is None:
        cap = float(load_params()["risk_defaults"]["correlation_cap"])
    open_total = float(sum(open_notional))
    combined = open_total + float(proposed_notional)
    if rho <= cap:
        return {"action": "NONE", "rho": rho, "combined_notional": combined,
                "cap": cap, "reduced_combined_notional": None,
                "reduced_proposal": None}
    target_combined = cap / rho if rho > 0 else 0.0
    reduced = max(0.0, min(float(proposed_notional),
                           target_combined - open_total))
    return {"action": "REDUCE", "rho": rho, "combined_notional": combined,
            "cap": cap, "reduced_combined_notional": open_total + reduced,
            "reduced_proposal": reduced}


@dataclass(frozen=True)
class CorrelationRecord:
    """§8.2 CorrelationRecord — a portfolio constraint, never a directional
    signal (Ch.8 preamble: "Correlation between symbols is a portfolio
    constraint, not a directional signal")."""

    symbol_pair: Tuple[str, str]
    window: str
    sample_count: int
    estimate: float              # Pearson ρ
    confidence_interval: Tuple[float, float]
    regime_scope: str
    last_update: int
    quality: float
    spearman: Optional[float] = None

    def __post_init__(self) -> None:
        if self.sample_count <= 0:
            raise ValueError("CORRELATION_SAMPLE_QX: sample_count must be > 0")
        if self.regime_scope == "":
            raise ValueError("CORRELATION_SCOPE_QX: regime_scope is mandatory")
        if not (-1.0 <= self.estimate <= 1.0):
            raise ValueError("CORRELATION_ESTIMATE_QX: ρ must be in [-1,1]")


@dataclass(frozen=True)
class DivergenceRecord:
    """§8.2 DivergenceRecord — BOTH pivots are stored, never only a boolean."""

    pivot_a: Mapping[str, Any]
    pivot_b: Mapping[str, Any]
    relation: str

    def __post_init__(self) -> None:
        if not self.pivot_a or not self.pivot_b:
            raise ValueError(
                "DIVERGENCE_PIVOT_QX: both pivots are stored (§8.2); a boolean "
                "alone is not a divergence record"
            )


@dataclass(frozen=True)
class SMTRecord:
    """§8.2 SMTRecord — Context-only; no "must revert" assumption is ever
    encoded."""

    asset_a_structure: Mapping[str, Any]
    asset_b_structure: Mapping[str, Any]
    relative_structure_divergence: float

    FORBIDDEN_FIELDS: Tuple[str, ...] = ("must_revert", "reversion_target")

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def assert_no_reversion_semantics(record: SMTRecord) -> None:
    """T_XSYM: an SMT record must never carry reversion language."""
    keys = {k.lower() for k in record.to_dict()}
    if keys & set(SMTRecord.FORBIDDEN_FIELDS):
        raise InvariantViolation(
            "SMT_REVERSION_QX: an SMT record encodes a structural "
            "disagreement, never a reversion assumption"
        )


def gate_thresholds() -> Dict[str, float]:
    """The two hard-gate projections named by §8.1 (read by the Setup gates so
    the threshold is defined exactly once)."""
    return {"gate3_conflict_penalty_max": GATE3_CONFLICT_THRESHOLD,
            "gate4_redundancy_penalty_max": GATE4_REDUNDANCY_THRESHOLD}
