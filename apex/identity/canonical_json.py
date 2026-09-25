"""APEX_GEN5 canonical JSON serialization.

Blueprint: §9.5-5/G11/AI.3 canonical serialization.
- UTF-8 JSON, sorted keys (lexicographic), no unnecessary whitespace
  (separators=(",", ":")), ensure_ascii=False, allow_nan=False.
- Decimal serialized as a QUANTIZED fixed-point JSON string — no
  exponential notation (AI.3); NaN/Inf forbidden.
- datetimes in UTC ISO 8601 with millisecond precision: ``YYYY-MM-DDTHH:MM:SS.fffZ``.
- ``-0`` normalizes to ``0`` (E-NUM-003); NaN/Inf raise ValueError
  (E-NUM-001/E-NUM-002).
This module is the ONLY canonical serializer in the repo; snapshot_id and
content_id hashes depend on its byte output (determinism contract).
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import enum
import json
import math
import uuid as _uuid
from decimal import Decimal
from typing import Any, Mapping, Sequence


class CanonicalJsonError(ValueError):
    """Raised when a payload cannot be canonically serialized (NaN/Inf,
    unsupported type). Never silently coerced (G11/AI.3)."""


def _quantize_decimal(value: Decimal) -> str:
    """Decimal → fixed-point string; no exponent, no NaN/Inf, -0 → '0'."""
    if not value.is_finite():
        raise CanonicalJsonError(
            "Decimal NaN/Inf is forbidden in canonical payloads"
        )
    if value == 0:
        return "0"
    text = format(value, "f")  # fixed-point, full precision, no exponent
    return text


def _canonical_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return _quantize_decimal(obj)
    if isinstance(obj, _dt.datetime):
        if obj.tzinfo is None:
            raise CanonicalJsonError(
                f"naive datetime {obj!r} is forbidden in canonical payloads "
                "(UTC required, AI.3)"
            )
        utc = obj.astimezone(_dt.timezone.utc)
        # ISO 8601 UTC, millisecond precision, 'Z' suffix (AI.3)
        return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"
    if isinstance(obj, _dt.date):
        return obj.isoformat()
    if isinstance(obj, _dt.time):
        return obj.isoformat()
    if isinstance(obj, _uuid.UUID):
        return str(obj)
    if isinstance(obj, enum.Enum):
        return obj.value
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, set) or isinstance(obj, frozenset):
        return sorted(obj)
    if hasattr(obj, "model_dump"):  # pydantic v2 model
        return obj.model_dump()
    raise CanonicalJsonError(
        f"unsupported canonical payload type {type(obj).__name__}"
    )


def _check_nan_inf(obj: Any, _depth: int = 0) -> None:
    if _depth > 100:
        raise CanonicalJsonError("payload nesting depth exceeds 100")
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise CanonicalJsonError("float NaN/Inf is forbidden in canonical payloads")
        return
    if isinstance(obj, Decimal) and not obj.is_finite():
        raise CanonicalJsonError("Decimal NaN/Inf is forbidden in canonical payloads")
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise CanonicalJsonError(
                    f"non-string key {k!r} is forbidden in canonical payloads"
                )
            _check_nan_inf(v, _depth + 1)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for v in obj:
            _check_nan_inf(v, _depth + 1)
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        _check_nan_inf(dataclasses.asdict(obj), _depth + 1)
    elif hasattr(obj, "model_dump"):
        _check_nan_inf(obj.model_dump(), _depth + 1)


def _normalize_neg_zero(obj: Any, _depth: int = 0) -> Any:
    """Float ``-0.0`` serialises as ``0`` (D50 / audit ب۵).

    The Decimal path already maps ``-0`` to ``"0"``. ``json.dumps`` would
    otherwise emit ``-0.0`` for a float, so two equal magnitudes would not
    hash equal. NaN/Inf are rejected by :func:`_check_nan_inf` first.
    """
    if _depth > 100:
        raise CanonicalJsonError("payload nesting depth exceeds 100")
    if isinstance(obj, float):
        if obj == 0.0:
            return 0.0
        return obj
    if isinstance(obj, Mapping):
        return {k: _normalize_neg_zero(v, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, tuple):
        return tuple(_normalize_neg_zero(v, _depth + 1) for v in obj)
    if isinstance(obj, list):
        return [_normalize_neg_zero(v, _depth + 1) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return obj
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _normalize_neg_zero(dataclasses.asdict(obj), _depth + 1)
    if hasattr(obj, "model_dump"):
        return _normalize_neg_zero(obj.model_dump(), _depth + 1)
    return obj


def canonical_json(obj: Any) -> str:
    """Serialize ``obj`` to the canonical byte-stable JSON string.

    sorted keys, no whitespace, ensure_ascii=False, NaN/Inf forbidden,
    Decimal fixed-point strings, datetimes ``...Z``, float ``-0.0`` → ``0``.
    Deterministic: identical Python values ⇒ identical strings.
    """
    _check_nan_inf(obj)
    obj = _normalize_neg_zero(obj)
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_canonical_default,
    )


def canonical_json_bytes(obj: Any) -> bytes:
    return canonical_json(obj).encode("utf-8")
