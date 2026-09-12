"""APEX_GEN5 snapshot identity and PIT boundary (GLOBAL IDENTITY / PIT
UTILITY CONTRACT v1.0.0, APEX_GEN5.md L4104–4158 + §2.3 + §9.5-5).

- ``snapshot_id = SHA256(canonical_json(canonical_snapshot_payload))`` —
  deterministic 64-hex identity; NO UUID, timestamp-randomness, bar-index
  suffix, or truncated digest enters it.
- A SINGLE canonical snapshot envelope per artifact (Phase 67A rule: no
  engine/contract double-wrapping).
- ``canonical_snapshot_id(engine, contract_version, payload)`` implements
  the frozen reference wrapper exactly (invalid context → ValueError
  INVALID_SNAPSHOT_CONTEXT_QX).
- ``governed_as_of_ms(required_artifacts)`` implements the frozen PIT rule:
  ``as_of = max(availability_time)``; producers MUST NOT substitute candle
  timestamp, local wall-clock time, or a fixed lag. Missing artifacts →
  ValueError MISSING_REQUIRED_ARTIFACTS_QX; missing availability_time →
  ValueError MISSING_AVAILABILITY_TIME_QX (fail-closed).
"""

from __future__ import annotations

import time as _time
from typing import Any, Dict, List, Optional

from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import sha256_hex


# ---------------------------------------------------------------------------
# Frozen global utilities
# ---------------------------------------------------------------------------

def canonical_snapshot_id(engine: str, contract_version: str, payload: dict) -> str:
    """Frozen reference wrapper (L4109): envelope {engine, contract_version,
    payload} → SHA256 over canonical JSON (sorted keys, no whitespace)."""
    if not engine or not contract_version:
        raise ValueError("INVALID_SNAPSHOT_CONTEXT_QX")
    canonical_payload = {
        "engine": engine,
        "contract_version": contract_version,
        "payload": payload,
    }
    return sha256_hex(canonical_json(canonical_payload))


def governed_as_of_ms(required_artifacts: List[Dict[str, Any]]) -> int:
    """Frozen PIT rule: as_of = max(availability_time_ms) over all required
    artifacts. Fail-closed on missing artifacts/availability_time."""
    if not required_artifacts:
        raise ValueError("MISSING_REQUIRED_ARTIFACTS_QX")
    times: List[int] = []
    for artifact in required_artifacts:
        t = artifact.get("availability_time_ms")
        if t is None:
            raise ValueError("MISSING_AVAILABILITY_TIME_QX")
        times.append(int(t))
    return max(times)


# ---------------------------------------------------------------------------
# Snapshot barrier (§2.3 Snapshot binding)
# ---------------------------------------------------------------------------

# Fields of the canonical snapshot payload that produce snapshot_id (§2.3
# algorithm). created_at is operational metadata and is EXCLUDED from the
# deterministic identity (the frozen algorithm omits it from the hash input).
_CANONICAL_SNAPSHOT_FIELDS = (
    "as_of",
    "symbol_scope",
    "timeframe_scope",
    "source_state",
    "manifest_hash",
    "parameter_package_id",
    "code_version",
    "quality_state",
    "observation_windows",
    "mtf_states",
    "overall_mtf",
)


class SnapshotBarrier:
    """Immutable snapshot binding one PIT boundary (§2.3).

    snapshot_id is computed once at construction from the canonical payload
    and never mutated. A new artifact ⇒ a new SnapshotBarrier (OLD →
    CORRECTION EVENT → NEW VERSION → SUPERSEDES) — never an edit.
    """

    def __init__(
        self,
        as_of: str,
        symbol_scope: List[str],
        timeframe_scope: List[str],
        source_state: str,
        manifest_hash: str,
        parameter_package_id: str,
        code_version: str,
        quality_state: Dict[str, Any],
        observation_windows: Dict[str, Any],
        mtf_states: Dict[str, str],
        overall_mtf: str,
        created_at: Optional[float] = None,
    ) -> None:
        if len(symbol_scope) > 10:
            raise ValueError("symbol_scope over 10 → BLOCK (§2.3)")
        if len(timeframe_scope) > 14:
            raise ValueError("timeframe_scope over 14 → BLOCK (§2.3)")
        if not parameter_package_id or not code_version:
            raise ValueError(
                "missing parameter_package_id or code_version → QX INVALID (§2.3)"
            )
        self.as_of = as_of
        self.symbol_scope = list(symbol_scope)
        self.timeframe_scope = list(timeframe_scope)
        self.source_state = source_state
        self.manifest_hash = manifest_hash
        self.parameter_package_id = parameter_package_id
        self.code_version = code_version
        self.quality_state = dict(quality_state)
        self.observation_windows = dict(observation_windows)
        self.mtf_states = dict(mtf_states)
        self.overall_mtf = overall_mtf
        self.created_at = created_at if created_at is not None else _time.time()
        self._snapshot_id = snapshot_id_from_payload(self._canonical_payload())

    def _canonical_payload(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of,
            "symbol_scope": self.symbol_scope,
            "timeframe_scope": self.timeframe_scope,
            "source_state": self.source_state,
            "manifest_hash": self.manifest_hash,
            "parameter_package_id": self.parameter_package_id,
            "code_version": self.code_version,
            "quality_state": self.quality_state,
            "observation_windows": self.observation_windows,
            "mtf_states": self.mtf_states,
            "overall_mtf": self.overall_mtf,
        }

    @property
    def snapshot_id(self) -> str:
        return self._snapshot_id

    def to_dict(self) -> Dict[str, Any]:
        """Full envelope (operational fields included, snapshot_id first)."""
        out = dict(self._canonical_payload())
        out["snapshot_id"] = self._snapshot_id
        out["created_at"] = self.created_at
        return out


def snapshot_id_from_payload(payload: Dict[str, Any]) -> str:
    """snapshot_id = SHA256(canonical_json(canonical_snapshot_payload))
    (§9.5-5). Deterministic; UUIDv7 is never part of the payload."""
    return sha256_hex(canonical_json(payload))


def manifest_hash(manifest: Dict[str, Any]) -> str:
    """Observation/data manifest hash: SHA-256 over canonical JSON, sorted
    keys, no whitespace (§2.3)."""
    return sha256_hex(canonical_json(manifest))
