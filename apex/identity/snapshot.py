"""Canonical snapshot identity (§9.5-5, §2.3, GLOBAL IDENTITY/PIT CONTRACT).

* ONE canonical snapshot envelope per artifact — no engine/contract
  double-wrapping (Phase 67A rule):
      canonical_payload = {"engine": ..., "contract_version": ...,
                           "payload": ...}
      snapshot_id = SHA256(canonical_json(canonical_payload))
* Deterministic identity contains NO UUID, NO timestamp-randomness, NO
  bar-index suffix, NO truncated digest (§2.3 canonical snapshot_id form).
* ``governed_as_of_ms`` — PIT boundary: as_of = max(availability_time) over
  required artifacts; missing availability_time is FAIL-CLOSED (ValueError);
  candle ts / local clock / fixed lag are never substitutes (GLOBAL contract).
"""
from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping

from apex.identity.canonical_json import canonical_json_bytes

__all__ = ["canonical_snapshot_id", "snapshot_envelope", "governed_as_of_ms"]


def snapshot_envelope(engine: str, contract_version: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """The single canonical envelope (do not wrap twice)."""
    if not engine or not contract_version:
        raise ValueError("INVALID_SNAPSHOT_CONTEXT_QX")
    return {"engine": engine, "contract_version": contract_version, "payload": dict(payload)}


def canonical_snapshot_id(engine: str, contract_version: str, payload: Mapping[str, Any]) -> str:
    """SHA-256 snapshot identity of the canonical envelope (64-hex)."""
    envelope = snapshot_envelope(engine, contract_version, payload)
    return hashlib.sha256(canonical_json_bytes(envelope)).hexdigest()


def governed_as_of_ms(required_artifacts: Iterable[Mapping[str, Any]]) -> int:
    """as_of = max(availability_time_ms) over all required artifacts.

    Fail-closed: empty requirement set -> MISSING_REQUIRED_ARTIFACTS_QX;
    any artifact lacking availability_time_ms -> MISSING_AVAILABILITY_TIME_QX
    (candle ts / wall clock / fixed lag are NOT substitutes — GLOBAL rule).
    """
    times: list[int] = []
    for artifact in required_artifacts:
        t = artifact.get("availability_time_ms")
        if t is None:
            raise ValueError("MISSING_AVAILABILITY_TIME_QX")
        times.append(int(t))
    if not times:
        raise ValueError("MISSING_REQUIRED_ARTIFACTS_QX")
    return max(times)
