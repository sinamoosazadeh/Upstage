"""APEX_GEN5 hash helpers (AI.3 deterministic identity; §9.5-5).

- ``content_id = SHA256(canonical_json(payload))`` — dedup/cache key.
- ``replay_key = SHA256(engine_version || contract_version || symbol ||
  timeframe || as_of_timestamp || input_hash || parameter_package_id ||
  code_revision || canonical_payload)`` — idempotency/retry gate; stable
  across identical inputs and code (AI.3).
All digests are full 64-hex-character SHA-256 (never truncated, G11).
"""

from __future__ import annotations

import hashlib
from typing import Any

from apex.identity.canonical_json import canonical_json


def sha256_hex(data: bytes | str) -> str:
    """SHA-256 over bytes (str inputs are UTF-8 encoded). 64-hex output."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def content_id(payload: Any) -> str:
    """Deterministic content identity: SHA256(canonical_json(payload))."""
    return sha256_hex(canonical_json(payload))


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
    """Deterministic replay key (AI.3). Fields concatenated in the frozen
    order with ``||`` semantics (plain concatenation, as specified)."""
    joined = "".join([
        engine_version,
        contract_version,
        symbol,
        timeframe,
        as_of_timestamp,
        input_hash,
        parameter_package_id,
        code_revision,
        canonical_payload,
    ])
    return sha256_hex(joined)
