"""Deterministic content identity (AI.3).

* ``content_id  = SHA256(canonical_json(payload))`` — dedup, cache keys.
* ``replay_key`` — deterministic retry/idempotency key:
  SHA256(engine_version || contract_version || symbol || timeframe ||
  as_of_timestamp || input_hash || parameter_package_id || code_revision ||
  canonical_payload). Stable across identical inputs+code; cached results
  are discarded on code_version change (AI.12 Phase 7).
* ``sha256_hex`` — raw byte hashing (source/payload hashes for lineage §2.4).

Runtime UUIDv7 (apex.identity.uuid_v7) is separate: operational identity
only, never part of deterministic identity.
"""
from __future__ import annotations

import hashlib
from typing import Any

from apex.identity.canonical_json import canonical_json_bytes

__all__ = ["sha256_hex", "content_id", "replay_key"]


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def content_id(payload: Any) -> str:
    """SHA-256 over the canonical JSON payload (64-hex deterministic id)."""
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def replay_key(
    engine_version: str,
    contract_version: str,
    symbol: str,
    timeframe: str,
    as_of_timestamp: str,
    input_hash: str,
    parameter_package_id: str,
    code_revision: str,
    canonical_payload: str,
) -> str:
    """AI.3 deterministic replay key (idempotency / retry deduplication)."""
    joined = "||".join(
        (
            engine_version,
            contract_version,
            symbol,
            timeframe,
            as_of_timestamp,
            input_hash,
            parameter_package_id,
            code_revision,
            canonical_payload,
        )
    )
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
