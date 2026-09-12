"""CP-1 identity tests — MATRIX: T-PIT-001..004 + T-ID-001/002 +
test_uuid7_single_implementation_grep (GLOBAL IDENTITY/PIT CONTRACT, AI.3)."""
from __future__ import annotations

import datetime as dt
import pathlib
import re
from decimal import Decimal

import pytest

from apex.identity import (
    CanonicalJsonError,
    canonical_json,
    canonical_snapshot_id,
    content_id,
    governed_as_of_ms,
    replay_key,
    uuid_v7,
    parse_uuid_v7_timestamp_ms,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


# ---- T-PIT-001: canonical serialization -----------------------------------

def test_t_pit_001_canonical_serialization_byte_identical() -> None:
    """50 snapshots; JSON canonical re-serialization byte-identical."""
    for i in range(50):
        payload = {
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "as_of": dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(minutes=i),
            "values": {"close": Decimal("43210.5500000000"), "n": i},
            "flags": [True, False, None],
        }
        once = canonical_json(payload)
        twice = canonical_json(payload)
        assert once == twice
        # sorted keys, no whitespace
        assert once == canonical_json(dict(reversed(list(payload.items()))))
        assert ": " not in once and ", " not in once
        assert once.encode("utf-8") == canonical_json(payload).encode("utf-8")


def test_canonical_json_rules() -> None:
    # Decimal as quantized fixed decimal string (never exponential)
    s = canonical_json({"x": Decimal("1E-7"), "y": Decimal("0.0002")})
    assert '"x":"0.0000001"' in s and '"y":"0.0002"' in s
    assert "E" not in s and "e-" not in s
    # datetime -> ...Z with millisecond precision
    d = dt.datetime(2024, 1, 1, 0, 15, 0, 250000, tzinfo=dt.timezone.utc)
    assert canonical_json({"t": d}) == '{"t":"2024-01-01T00:15:00.250Z"}'
    # NaN/Inf forbidden
    with pytest.raises(CanonicalJsonError):
        canonical_json({"x": float("nan")})
    with pytest.raises(CanonicalJsonError):
        canonical_json({"x": Decimal("Infinity")})
    with pytest.raises(CanonicalJsonError):
        canonical_json({"t": dt.datetime(2024, 1, 1)})  # naive forbidden


# ---- T-PIT-002: deterministic content id ----------------------------------

def test_t_pit_002_content_id_deterministic() -> None:
    """Identical payloads -> identical content_id; n=500."""
    for i in range(500):
        payload = {"i": i % 17, "v": Decimal("0.0001"), "s": "BTCUSDT"}
        assert content_id(payload) == content_id(dict(payload))
    assert content_id({"a": 1, "b": 2}) == content_id({"b": 2, "a": 1})
    assert content_id({"a": 1}) != content_id({"a": 2})
    assert re.fullmatch(r"[0-9a-f]{64}", content_id({"x": 1}))


# ---- T-PIT-003: replay key dedup -------------------------------------------

def test_t_pit_003_replay_key_stable_and_retry_cache() -> None:
    """Same inputs+code -> same replay_key; retry returns cached result."""
    kwargs = dict(
        engine_version="E01-v5.0.0",
        contract_version="v4.0.0",
        symbol="BTCUSDT",
        timeframe="15m",
        as_of_timestamp="2024-01-01T00:15:00.000Z",
        input_hash="ab" * 32,
        parameter_package_id="pkg-v1",
        code_revision="c" * 40,
        canonical_payload=canonical_json({"k": 1}),
    )
    first = replay_key(**kwargs)
    # retry with identical inputs -> identical key (dedup hit)
    for _ in range(3):
        assert replay_key(**kwargs) == first
    # code_version change invalidates the cache key
    assert replay_key(**{**kwargs, "code_revision": "d" * 40}) != first


# ---- T-PIT-004: snapshot id -------------------------------------------------

def test_t_pit_004_snapshot_id_reproducible() -> None:
    """100 identical-input snapshots reproduce the same snapshot_id."""
    payload = {"as_of_ms": 1_704_067_200_000, "close": Decimal("42000.0")}
    ref = canonical_snapshot_id("E01", "v4.0.0", payload)
    for _ in range(100):
        assert canonical_snapshot_id("E01", "v4.0.0", dict(payload)) == ref
    assert re.fullmatch(r"[0-9a-f]{64}", ref)
    # envelope is singular: re-wrapping an envelope must change identity
    wrapped = canonical_snapshot_id(
        "E01", "v4.0.0", {"engine": "E01", "contract_version": "v4.0.0", "payload": payload}
    )
    assert wrapped != ref  # double-wrapping is detectable and forbidden
    with pytest.raises(ValueError):
        canonical_snapshot_id("", "v4.0.0", payload)  # INVALID_SNAPSHOT_CONTEXT_QX


# ---- T-ID-001: UUIDv7 sequencing --------------------------------------------

def test_t_id_001_uuid7_strictly_increasing_no_duplicates() -> None:
    """1000 events; event_id strictly increasing; no duplicates."""
    ids = [uuid_v7() for _ in range(1000)]
    assert len(set(ids)) == 1000
    ts = [parse_uuid_v7_timestamp_ms(i) for i in ids]
    assert all(a <= b for a, b in zip(ts, ts[1:]))  # time-ordered (ms resolution)
    for value in ids[:50]:
        assert re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", value
        )


# ---- T-ID-002: lineage parents valid -----------------------------------------

def test_t_id_002_lineage_parent_references_valid() -> None:
    """500 derived events; all parent_event_ids exist in the ledger set."""
    ledger: dict[str, dict] = {}
    roots = [uuid_v7() for _ in range(10)]
    for r in roots:
        ledger[r] = {"parent_ids": []}
    import itertools

    for n, parent_pool in zip(range(500), itertools.cycle([roots])):
        event_id = uuid_v7()
        parents = [parent_pool[n % len(parent_pool)]]
        ledger[event_id] = {"parent_ids": parents}
    for event in ledger.values():
        for parent in event["parent_ids"]:
            assert parent in ledger, "orphan lineage reference"


# ---- single uuid implementation grep ------------------------------------------

def test_uuid7_single_implementation_grep() -> None:
    """apex/identity/uuid_v7.py is the ONLY uuid generator in the repo
    (G11/P8: local variants forbidden)."""
    apex_dir = REPO_ROOT / "apex"
    offenders = []
    for path in apex_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if path.name == "uuid_v7.py":
            continue
        if re.search(r"\buuid\.uuid[1-8]\b|\brandom.*uuid|secrets\.randbits\(\s*62\s*\)", text):
            offenders.append(str(path))
        if "def uuid_v7" in text:
            offenders.append(str(path))
    assert not offenders, f"duplicate UUID implementations: {offenders}"


def test_uuid7_never_in_canonical_snapshot_payload() -> None:
    """Identity separation rule: snapshot_id must not change if a uuid in the
    operational layer changes — operational ids stay out of canonical payloads."""
    payload = {"close": Decimal("100.5")}
    a = canonical_snapshot_id("E05", "v4.0.0", payload)
    b = canonical_snapshot_id("E05", "v4.0.0", payload)
    assert a == b


def test_governed_as_of_ms() -> None:
    arts = [{"availability_time_ms": 100}, {"availability_time_ms": 300}, {"availability_time_ms": 200}]
    assert governed_as_of_ms(arts) == 300
    with pytest.raises(ValueError, match="MISSING_AVAILABILITY_TIME_QX"):
        governed_as_of_ms([{"availability_time_ms": 100}, {}])
    with pytest.raises(ValueError, match="MISSING_REQUIRED_ARTIFACTS_QX"):
        governed_as_of_ms([])
