"""APEX_GEN5 — Evidence Fabric + unified evidence lifecycle (SL-1/SL-14).

Blueprint: APEX_GEN5.md Ch.8 §8.0 (L14672–14768) — "Evidence Fabric: the
normalized set of all ACTIVE evidence at time ``t`` for one
``(symbol, timeframe)``" — plus the lifecycle crosswalk recorded at L4681 and
the SL-14 resolution ladder (ADR-P2-011: SL-14 content lives in Ch.8 §8.0 +
Ch.2 §2.1).

Normative rules implemented here
--------------------------------
* Ch.8 §8.0: "evidence enters/leaves a fabric **only** through the lifecycle
  state machine (SL-14); every input carries full lineage down to raw
  ``observation_id`` (the Data Plane ``market_observation``); fabrics are
  read-only for engines — engines publish events, they never mutate a fabric
  in place."
* L4681 crosswalk (E05 engine lifecycle → SL-14 unified lifecycle):
  ``created → emitted → consumed → expired (5×TF) → superseded`` maps into
  ``CANDIDATE → CONFIRMED → ACTIVE → {MITIGATED, INVALIDATED, EXPIRED,
  SUPERSEDED}`` with the frozen equivalences ``emitted ≡ ACTIVE``,
  ``expired ≡ EXPIRED``, ``superseded ≡ SUPERSEDED``; "archived, never
  deleted".
* Expiry age = 5 × TF duration (L4681 "expired (5×TF)"); TF durations are the
  frozen §2.3 minute-multiples of ``apex.quality.pit.TF_DURATION_SECONDS``
  (ISSUE-CP1-007), never a locally re-invented table.
* Solvency (Ch.8 §8.0): low data quality removes the affected evidence —
  it is never replaced by zero or a guess (SL-14: "QX is never replaced by
  zero or guess").

The fabric is a pure, deterministic, hash-bound read-only view: the fabric
``hash`` is ``sha256(canonical_json(serialization))`` computed over the
canonical serialization of the fabric members (Ch.8 §8.0 fabric JSON).
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import sha256_hex
from apex.identity.uuid_v7 import uuid_v7
from apex.quality.pit import TF_DURATION_SECONDS

CONTRACT_VERSION = "4.0.0"

# ---------------------------------------------------------------------------
# SL-14 unified evidence lifecycle (Ch.2 §2.1 state machine + AI.4/AI.9):
# CANDIDATE → CONFIRMED → ACTIVE → {MITIGATED, INVALIDATED, EXPIRED,
# SUPERSEDED}. Terminal states never revert.
# ---------------------------------------------------------------------------

EVIDENCE_LIFECYCLE_STATES: Tuple[str, ...] = (
    "CANDIDATE", "CONFIRMED", "ACTIVE", "MITIGATED",
    "INVALIDATED", "EXPIRED", "SUPERSEDED",
)

# The engine-local naming of the same machine (L4681, verbatim order).
ENGINE_LIFECYCLE_STATES: Tuple[str, ...] = (
    "created", "emitted", "consumed", "expired", "superseded",
)

# SL-14 crosswalk (L4681). The three equivalences the blueprint states
# verbatim are ACTIVE / EXPIRED / SUPERSEDED; the remaining engine-local
# labels are pre-ACTIVE stages of the same ladder and crosswalk to their
# forward neighbour so no engine name becomes a second lifecycle.
SL14_CROSSWALK: Dict[str, str] = {
    "created": "CANDIDATE",
    "emitted": "ACTIVE",          # emitted ≡ ACTIVE (verbatim, L4681)
    "consumed": "ACTIVE",         # consumed does not leave the ACTIVE set
    "expired": "EXPIRED",         # expired ≡ EXPIRED (verbatim)
    "superseded": "SUPERSEDED",   # superseded ≡ SUPERSEDED (verbatim)
}

_FORWARD: Dict[str, Tuple[str, ...]] = {
    "CANDIDATE": ("CONFIRMED",),
    "CONFIRMED": ("ACTIVE",),
    "ACTIVE": ("MITIGATED", "INVALIDATED", "EXPIRED", "SUPERSEDED"),
    "MITIGATED": ("INVALIDATED", "EXPIRED", "SUPERSEDED"),
    "INVALIDATED": (),
    "EXPIRED": (),
    "SUPERSEDED": (),
}

TERMINAL_STATES: Tuple[str, ...] = ("INVALIDATED", "EXPIRED", "SUPERSEDED")

# Ch.8 §8.0: "the normalized set of all ACTIVE evidence".
FABRIC_ADMIT_STATE = "ACTIVE"

# Expiry rule of the engine-local ladder: "expired (5×TF)" (L4681).
EXPIRY_TF_MULTIPLE = 5


def lifecycle_of(engine_state: str) -> str:
    """Map an engine-local lifecycle label onto SL-14 (L4681 crosswalk).

    Unknown labels fail closed — the unified machine has exactly the seven
    states, an eighth is never invented (G6/P6).
    """
    try:
        return SL14_CROSSWALK[engine_state]
    except KeyError:
        raise ValueError(
            f"UNRECOGNISED_EVIDENCE_LIFECYCLE_QX: {engine_state!r} is not an "
            f"engine-local SL-14 label {sorted(SL14_CROSSWALK)}"
        ) from None


def is_forward(src: str, dst: str) -> bool:
    """SL-14 legal transition test (terminal states never revert)."""
    return dst in _FORWARD.get(src, ())


def advance_lifecycle(src: str, dst: str) -> str:
    """The ONLY lawful way to move evidence inside/outside a fabric.

    Illegal transitions raise (fail-closed, T-MON-002 semantics reused from
    the frozen base contract; the fabric never re-labels evidence quietly).
    """
    if src not in EVIDENCE_LIFECYCLE_STATES or dst not in EVIDENCE_LIFECYCLE_STATES:
        raise ValueError(
            f"UNKNOWN_SL14_STATE_QX: {src!r}/{dst!r} not in "
            f"{EVIDENCE_LIFECYCLE_STATES}"
        )
    if not is_forward(src, dst):
        raise ValueError(
            f"ILLEGAL_SL14_TRANSITION_QX: {src} → {dst} "
            "(evidence enters/leaves a fabric only through the lifecycle "
            "state machine, Ch.8 §8.0)"
        )
    return dst


def expiry_age_bars(timeframe: str) -> int:
    """Expiry horizon in seconds of the engine-local ladder: 5×TF (L4681).

    The TF duration is read from the frozen §2.3 table (ISSUE-CP1-007);
    an unknown timeframe fails closed (E-VAL-022 linter semantics).
    """
    try:
        return EXPIRY_TF_MULTIPLE * TF_DURATION_SECONDS[timeframe]
    except KeyError:
        raise ValueError(
            f"E-VAL-022: timeframe {timeframe!r} is not one of the frozen 14"
        ) from None


def evidence_freshness(age_bars: float, lam: float, *, what: str = "evidence") -> float:
    """Freshness factor ``exp(−λ·age)`` for the given decay law.

    ``lam`` is always supplied by the caller from the governed parameters —
    the fabric never hardcodes a decay rate (§9.5-10: values live in the
    params YAMLs, code loads).
    """
    if lam < 0 or age_bars < 0:
        raise ValueError(
            f"NEGATIVE_DECAY_INPUT_QX: {what} requires age_bars ≥ 0 and "
            f"λ ≥ 0 (got age={age_bars}, λ={lam})"
        )
    return math.exp(-lam * age_bars)


# ---------------------------------------------------------------------------
# Dependency groups (Ch.8 §8.1: "disagreement between engines of the same
# dependency group"). The grouping is the frozen SL-9 semantic ladder
# (Feature → … → Strategy) applied to the twelve engines, in engine order:
# it assigns every engine to exactly one group and is used ONLY to compute
# `disagreement`; it grants nothing and vetoes nothing.
# ---------------------------------------------------------------------------

ENGINE_GROUPS: Dict[str, Tuple[str, ...]] = {
    "structure": ("E01", "E09"),          # market structure / trend
    "liquidity": ("E02", "E07"),           # liquidity / smart-money behaviour
    "volume": ("E03",),                    # participation
    "volatility": ("E04",),               # volatility regime
    "zones": ("E05", "E06", "E08"),       # zone/block/cycle objects
    "momentum": ("E10",),                  # momentum
    "context": ("E11", "E12"),             # regime / temporal context
}

_GROUP_OF_ENGINE: Dict[str, str] = {
    eng: grp for grp, engines in ENGINE_GROUPS.items() for eng in engines
}


def engine_group_of(engine_id: str) -> str:
    """Dependency group of an engine (fail-closed on unknown ids)."""
    try:
        return _GROUP_OF_ENGINE[engine_id]
    except KeyError:
        raise ValueError(
            f"UNKNOWN_ENGINE_ID_QX: {engine_id!r} is not E01..E12"
        ) from None


# ---------------------------------------------------------------------------
# Fabric records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FabricEvidenceRef:
    """One normalized member of the Evidence Fabric.

    Carries the fields Ch.8 §8.0 requires of a fabric input: identity, the
    SL-14 lifecycle state, full lineage down to the raw ``observation_id``,
    the direction vote (``direction ∈ {−1,0,+1}``, Ch.10 §10.1) and the
    quality/resolution class used by the solvency rule.
    """

    evidence_id: str
    engine_id: str
    symbol: str
    timeframe: str
    state: str                       # SL-14 label
    direction: int                   # -1 / 0 / +1
    quality: float                   # Q_evidence-style scalar in [0,1]
    resolution_class: str            # Q0..Q5 / QX
    age_bars: float
    as_of: int                       # epoch ms (governed as_of)
    snapshot_id: str
    lineage: Tuple[str, ...]         # down to raw observation_id
    parent_ids: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raise ValueError("FABRIC_MEMBER_ID_EMPTY_QX")
        if self.direction not in (-1, 0, 1):
            raise ValueError(
                f"FABRIC_DIRECTION_QX: {self.direction!r} not in {{-1,0,+1}}"
            )
        if self.state not in EVIDENCE_LIFECYCLE_STATES:
            raise ValueError(
                f"FABRIC_STATE_QX: {self.state!r} not in {EVIDENCE_LIFECYCLE_STATES}"
            )
        if not (0.0 <= self.quality <= 1.0) or self.quality != self.quality:
            raise ValueError(
                f"FABRIC_QUALITY_QX: quality must be finite in [0,1], got "
                f"{self.quality!r}"
            )
        if self.age_bars < 0:
            raise ValueError("FABRIC_AGE_QX: age_bars must be ≥ 0")
        if not self.lineage:
            # Ch.8 §8.0: "every input carries full lineage down to raw
            # observation_id" — a member without lineage is not admissible.
            raise ValueError(
                "FABRIC_LINEAGE_QX: evidence without lineage down to raw "
                "observation_id cannot enter a fabric (Ch.8 §8.0)"
            )
        if not self.snapshot_id:
            raise ValueError("FABRIC_SNAPSHOT_QX: snapshot_id is mandatory")

    @property
    def is_active(self) -> bool:
        return self.state == FABRIC_ADMIT_STATE

    def to_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        d["engine_group"] = engine_group_of(self.engine_id)
        d["expiry_age_seconds"] = expiry_age_bars(self.timeframe)
        return d


def make_fabric_id() -> str:
    """``fab_<uuid>`` — operational identity only (P8: UUIDv7 never enters
    canonical payloads)."""
    return "fab_" + uuid_v7()


def make_hash(payload: Any) -> str:
    """Fabric hash: SHA-256 of the canonical serialization (Ch.8 §8.0)."""
    return sha256_hex(canonical_json(payload))


def _lineage_ok(ref: FabricEvidenceRef, raw_observation_ids: Iterable[str]) -> bool:
    allowed = set(raw_observation_ids)
    return any(tok in allowed for tok in ref.lineage)


@dataclass(frozen=True)
class EvidenceFabric:
    """Ch.8 §8.0 Evidence Fabric JSON, read-only for engines.

    ``members`` are the normalized ACTIVE inputs (the fabric is by definition
    "the normalized set of all ACTIVE evidence at time t"). Inadmissible
    inputs are reported in ``excluded`` with a deterministic reason code —
    the fabric never silently drops them and never substitutes a value.
    """

    fabric_id: str
    as_of: int
    symbol: str
    timeframe: str
    members: Tuple[FabricEvidenceRef, ...]
    data_trust: float
    conflict_state: str
    redundancy_state: Dict[str, float]
    hash: str
    excluded: Tuple[Tuple[str, str], ...] = ()   # (evidence_id, reason)

    # -- construction -------------------------------------------------------
    @classmethod
    def assemble(cls,
                 *,
                 symbol: str,
                 timeframe: str,
                 as_of: int,
                 evidence: Sequence[FabricEvidenceRef],
                 data_trust: float,
                 conflict_state: str = "NONE",
                 redundancy_state: Optional[Dict[str, float]] = None,
                 raw_observation_ids: Optional[Iterable[str]] = None) -> "EvidenceFabric":
        """Build the fabric for one ``(symbol, timeframe)`` at ``as_of``.

        Admission = SL-14 ACTIVE ∧ lineage present ∧ (when a raw-observation
        set is supplied) lineage resolvable to it ∧ PIT (no member with
        ``as_of`` beyond the fabric as_of) ∧ freshness below the 5×TF expiry.
        Anything else is excluded with a reason, never repaired.
        """
        if symbol == "" or timeframe == "":
            raise ValueError("FABRIC_KEY_QX: symbol and timeframe are mandatory")
        if not (0.0 <= data_trust <= 1.0) or data_trust != data_trust:
            raise ValueError("FABRIC_DATA_TRUST_QX: data_trust must be in [0,1]")
        expiry = expiry_age_bars(timeframe)
        raw_ids = None if raw_observation_ids is None else set(raw_observation_ids)
        members: List[FabricEvidenceRef] = []
        excluded: List[Tuple[str, str]] = []
        for ref in evidence:
            if ref.symbol != symbol or ref.timeframe != timeframe:
                excluded.append((ref.evidence_id, "FABRIC_SCOPE_MISMATCH_QX"))
                continue
            if ref.state != FABRIC_ADMIT_STATE:
                # SL-14 is the only gate in/out of a fabric.
                excluded.append((ref.evidence_id, "NOT_ACTIVE_SL14"))
                continue
            if ref.as_of > as_of:
                # Invariant I1 (point-in-time).
                excluded.append((ref.evidence_id, "E-PIT-001"))
                continue
            if raw_ids is not None and not _lineage_ok(ref, raw_ids):
                excluded.append((ref.evidence_id, "LINEAGE_UNRESOLVED_QX"))
                continue
            if ref.age_bars * TF_DURATION_SECONDS[timeframe] > expiry:
                excluded.append((ref.evidence_id, "EXPIRED_5TF"))
                continue
            members.append(ref)
        members.sort(key=lambda r: r.evidence_id)
        body: Dict[str, Any] = {
            "as_of": as_of,
            "symbol": symbol,
            "timeframe": timeframe,
            "evidence": [r.evidence_id for r in members],
            "data_trust": data_trust,
            "conflict_state": conflict_state,
            "redundancy_state": dict(sorted((redundancy_state or {}).items())),
        }
        return cls(
            fabric_id=make_fabric_id(),
            as_of=as_of,
            symbol=symbol,
            timeframe=timeframe,
            members=tuple(members),
            data_trust=data_trust,
            conflict_state=conflict_state,
            redundancy_state=dict(sorted((redundancy_state or {}).items())),
            hash=make_hash(body),
            excluded=tuple(excluded),
        )

    # -- read-only views ----------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """The Ch.8 §8.0 fabric JSON (``evidence`` = member ids)."""
        return {
            "fabric_id": self.fabric_id,
            "as_of": self.as_of,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "evidence": [r.evidence_id for r in self.members],
            "data_trust": self.data_trust,
            "conflict_state": self.conflict_state,
            "redundancy_state": dict(self.redundancy_state),
            "hash": self.hash,
        }

    def members_by_group(self) -> Dict[str, List[FabricEvidenceRef]]:
        out: Dict[str, List[FabricEvidenceRef]] = {g: [] for g in ENGINE_GROUPS}
        for ref in self.members:
            out[engine_group_of(ref.engine_id)].append(ref)
        return out

    def is_empty(self) -> bool:
        return not self.members


def fabric_from_events(events: Sequence[Any], *, symbol: str, timeframe: str,
                       as_of: int, data_trust: float,
                       conflict_state: str = "NONE",
                       redundancy_state: Optional[Dict[str, float]] = None,
                       raw_observation_ids: Optional[Iterable[str]] = None,
                       state_key: str = "fate_state") -> EvidenceFabric:
    """Adapt frozen 24-field ``EvidenceEvent`` objects into a fabric.

    The event's SL-14 ``fate_state`` (or an explicit ``engine_state`` key for
    engine-local ladders) is crosswalked through :func:`lifecycle_of`;
    engines are never re-computed here (fabric is a read-only view, and the
    E06-style consumption lint of CP-3 stays intact).
    """
    refs: List[FabricEvidenceRef] = []
    for ev in events:
        raw_state = getattr(ev, state_key, None)
        if raw_state is None:
            raise ValueError(
                "FABRIC_STATE_QX: evidence carries no SL-14 lifecycle field"
            )
        state = str(getattr(raw_state, "value", raw_state))
        if state in SL14_CROSSWALK:
            state = lifecycle_of(state)
        refs.append(FabricEvidenceRef(
            evidence_id=ev.evidence_id,
            engine_id=ev.engine_id,
            symbol=ev.symbol,
            timeframe=ev.timeframe,
            state=state,
            direction=int(ev.direction),
            quality=float(ev.quality),
            resolution_class=str(ev.resolution_class),
            age_bars=float(ev.age if ev.age is not None else 0.0),
            as_of=as_of,
            snapshot_id=ev.snapshot_id,
            lineage=tuple(ev.lineage) if ev.lineage else (ev.evidence_id,),
            parent_ids=tuple(ev.feature_dependencies),
        ))
    return EvidenceFabric.assemble(
        symbol=symbol, timeframe=timeframe, as_of=as_of, evidence=refs,
        data_trust=data_trust, conflict_state=conflict_state,
        redundancy_state=redundancy_state,
        raw_observation_ids=raw_observation_ids)
