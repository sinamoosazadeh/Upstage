"""Canonical serialization (§9.5, AI.3, GLOBAL IDENTITY/PIT UTILITY CONTRACT).

`canonical_json`: sorted keys, no whitespace, Decimal as quantized fixed
decimal string, datetimes as ISO-8601 UTC `...Z` with millisecond precision,
NaN/Inf forbidden, no exponential notation, UTF-8.

There is exactly ONE canonical serializer in the repository (G11/P8).
"""
from __future__ import annotations

import datetime as _dt
import json
import math
from decimal import Decimal
from typing import Any

__all__ = ["canonical_json", "canonical_json_bytes", "CanonicalJsonError"]


class CanonicalJsonError(ValueError):
    """Raised for non-canonicalizable values (NaN/Inf, unsupported types)."""


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                raise CanonicalJsonError("NaN/Inf forbidden in canonical JSON")
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise CanonicalJsonError("NaN/Inf forbidden in canonical JSON")
        # floats must not enter canonical payloads silently; render exactly
        return value
    if isinstance(value, Decimal):
        if value.is_nan() or value.is_infinite():
            raise CanonicalJsonError("NaN/Inf Decimal forbidden in canonical JSON")
        # quantized JSON string, fixed notation (never exponential)
        return format(value, "f")
    if isinstance(value, _dt.datetime):
        if value.tzinfo is None:
            raise CanonicalJsonError("naive datetime forbidden; UTC required")
        utc = value.astimezone(_dt.timezone.utc)
        # ISO-8601 with millisecond precision: YYYY-MM-DDTHH:MM:SS.fffZ
        return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise CanonicalJsonError(f"non-string key forbidden: {k!r}")
            out[k] = _normalize(v)
        return out
    raise CanonicalJsonError(f"unsupported canonical type: {type(value).__name__}")


def canonical_json(payload: Any) -> str:
    """Deterministic canonical JSON string (sorted keys, no whitespace)."""
    normalized = _normalize(payload)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_json_bytes(payload: Any) -> bytes:
    return canonical_json(payload).encode("utf-8")
