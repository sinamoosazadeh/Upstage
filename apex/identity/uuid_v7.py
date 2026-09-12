"""UUIDv7 (RFC 9562) — the SINGLE implementation in this repository.

GLOBAL IDENTITY/PIT UTILITY CONTRACT (normative): UUIDv7 is OPERATIONAL
identity only (event_id / object_id for sequencing, ledger, audit). It MUST
NOT enter canonical snapshot payloads and is never part of `snapshot_id`.
Local variants are forbidden (G11/P8); every module imports from here.

Shape: 48-bit Unix-ms timestamp + version 7 + 12-bit rand_a + RFC-variant
+ 62-bit rand_b.
"""
from __future__ import annotations

import secrets
import time

__all__ = ["uuid_v7", "parse_uuid_v7_timestamp_ms"]


def uuid_v7() -> str:
    """Generate a fresh RFC-9562 UUIDv7 string (operational identity)."""
    ts = int(time.time_ns() // 1_000_000) & ((1 << 48) - 1)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (ts << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    h = f"{value:032x}"
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def parse_uuid_v7_timestamp_ms(value: str) -> int:
    """Extract the embedded 48-bit Unix-ms timestamp (sequencing support)."""
    hexstr = value.replace("-", "")
    if len(hexstr) != 32:
        raise ValueError("INVALID_UUID_V7_SHAPE")
    version = int(hexstr[12], 16)
    if version != 7:
        raise ValueError("INVALID_UUID_V7_VERSION")
    return int(hexstr[0:12], 16)
