"""APEX_GEN5 UUIDv7 — the ONLY UUIDv7 implementation in the repository
(G11/P8: "exactly one implementation (apex/identity/uuid_v7.py); local
variants forbidden").

Shape (GLOBAL IDENTITY/PIT UTILITY CONTRACT v1.0.0, APEX_GEN5.md L4104):
RFC 9562 UUIDv7 — 48-bit Unix-ms timestamp | version 7 | 12-bit rand_a |
RFC-variant bits (0b10) | 62-bit rand_b.

Operational identity only: UUIDv7 MUST NOT enter canonical snapshot
payloads or snapshot_id (deterministic identity separation rule).
"""

from __future__ import annotations

import secrets
import time


def uuid_v7() -> str:
    """Generate a UUIDv7 string (lowercase, hyphenated, RFC 9562 shape).

    Exact reference from the frozen GLOBAL IDENTITY contract:
        48-bit Unix-ms timestamp + version 7 + 12-bit rand_a +
        RFC-variant + 62-bit rand_b.
    """
    ts = int(time.time_ns() // 1_000_000) & ((1 << 48) - 1)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (ts << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    h = f"{value:032x}"
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def uuid_v7_timestamp_ms(uuid_str: str) -> int:
    """Extract the 48-bit Unix-ms timestamp from a UUIDv7 string
    (operational ordering check; strictly increasing under RFC 9562)."""
    h = uuid_str.replace("-", "")
    return int(h[0:12], 16)
