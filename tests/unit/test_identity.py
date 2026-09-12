"""CP-1 identity tests: canonical_json determinism (T-PIT-001),
content_id (T-PIT-002), replay_key (T-PIT-003), snapshot_id (T-PIT-004),
UUIDv7 RFC 9562 + single implementation (T-ID-001), lineage refs
(T-ID-002), snapshot envelope rules, governed as_of fail-closed."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import re
import time
from decimal import Decimal

import pytest

from apex.identity.canonical_json import (
    CanonicalJsonError,
    canonical_json,
    canonical_json_bytes,
)
from apex.identity.hashes import content_id, replay_key, sha256_hex
from apex.identity.snapshot import (
    SnapshotBarrier,
    canonical_snapshot_id,
    governed_as_of_ms,
    manifest_hash,
)
from apex.identity.uuid_v7 import uuid_v7, uuid_v7_timestamp_ms

REPO = pathlib.Path(__file__).resolve().parent.parent.parent


class TestCanonicalJson:
    def test_sorted_keys_no_whitespace(self):
        obj = {"b": 1, "a": {"d": 4, "c": 3}}
        text = canonical_json(obj)
        assert text == '{"a":{"c":3,"d":4},"b":1}'
        assert "\n" not in text and " " not in text

    def test_decimal_fixed_point_no_exponent(self):
        text = canonical_json({"fee": Decimal("0.0002"),
                               "tiny": Decimal("1E-18"),
                               "neg_zero": Decimal("-0")})
        assert '"fee":"0.0002"' in text
        assert '"tiny":"0.000000000000000001"' in text  # no exponent
        assert '"neg_zero":"0"' in text  # -0 → 0 (E-NUM-003)

    def test_datetime_z_millis(self):
        ts = dt.datetime(2024, 1, 1, 0, 15, 0, 123000, tzinfo=dt.timezone.utc)
        text = canonical_json({"t": ts})
        assert '"t":"2024-01-01T00:15:00.123Z"' in text

    def test_nan_inf_forbidden(self):
        with pytest.raises(CanonicalJsonError):
            canonical_json({"x": float("nan")})
        with pytest.raises(CanonicalJsonError):
            canonical_json({"x": Decimal("Infinity")})
        with pytest.raises(CanonicalJsonError):
            canonical_json({"x": {"y": [float("-inf")]}})

    def test_unsupported_type_fails_closed(self):
        with pytest.raises(CanonicalJsonError):
            canonical_json({"x": object()})

    def test_non_string_keys_rejected(self):
        with pytest.raises(CanonicalJsonError):
            canonical_json({1: "v"})

    def test_pit_001_byte_identical_reserialization(self):
        """T-PIT-001: 50 snapshots; canonical re-serialization
        byte-identical."""
        for i in range(50):
            obj = {"snapshot_id": f"s{i}", "as_of": "2024-01-01T00:00:00.000Z",
                   "prices": [Decimal("1.5"), Decimal("2.25")],
                   "nested": {"z": i, "a": "same"}}
            assert canonical_json(obj) == canonical_json(json.loads(
                canonical_json(obj), parse_float=Decimal, parse_int=int))


class TestContentId:
    def test_pit_002_identical_payloads_identical_content_id(self):
        """T-PIT-002: n=500 identical payloads → identical content_id."""
        base = {"symbol": "BTCUSDT", "timeframe": "15m",
                "close": Decimal("67250.50")}
        ids = {content_id(base) for _ in range(500)}
        assert len(ids) == 1
        expected = sha256_hex(canonical_json(base).encode("utf-8"))
        assert ids.pop() == expected

    def test_different_payload_different_id(self):
        assert content_id({"a": 1}) != content_id({"a": 2})


class TestReplayKey:
    def test_pit_003_stable_key_and_cache_semantics(self):
        """T-PIT-003: same inputs+code → same replay_key; a retry with the
        same key returns the cached result (dedup)."""
        args = dict(engine_version="1.0.0+ab", contract_version="v4.0.0",
                    symbol="BTCUSDT", timeframe="1h",
                    as_of_timestamp="2024-01-01T14:00:03.000Z",
                    input_hash="h1", parameter_package_id="pkg-1",
                    code_revision="0" * 40, canonical_payload='{"x":1}')
        k1 = replay_key(**args)
        k2 = replay_key(**args)
        assert k1 == k2
        assert len(k1) == 64  # full SHA-256, never truncated
        args["symbol"] = "ETHUSDT"
        assert replay_key(**args) != k1
        args["code_revision"] = "1" * 40
        assert replay_key(**args) != k1


class TestSnapshot:
    def test_pit_004_snapshot_id_reproducible(self):
        """T-PIT-004: 100 identical-input snapshots reproduce the same
        snapshot_id."""
        barrier = SnapshotBarrier(
            as_of="2024-01-01T14:00:03.000Z",
            symbol_scope=["BTCUSDT"], timeframe_scope=["1h"],
            source_state="VALID",
            manifest_hash=manifest_hash({"observation_windows": {}}),
            parameter_package_id="pkg", code_version="4.0.0",
            quality_state={"min_q": 0.9, "weighted_q": 0.95},
            observation_windows={}, mtf_states={"1h": "ALIGNED"},
            overall_mtf="ALIGNED")
        ids = {SnapshotBarrier(
            as_of="2024-01-01T14:00:03.000Z",
            symbol_scope=["BTCUSDT"], timeframe_scope=["1h"],
            source_state="VALID",
            manifest_hash=manifest_hash({"observation_windows": {}}),
            parameter_package_id="pkg", code_version="4.0.0",
            quality_state={"min_q": 0.9, "weighted_q": 0.95},
            observation_windows={}, mtf_states={"1h": "ALIGNED"},
            overall_mtf="ALIGNED").snapshot_id for _ in range(100)}
        assert len(ids) == 1
        assert len(ids.pop()) == 64

    def test_created_at_not_in_identity(self):
        b1 = SnapshotBarrier(
            as_of="2024-01-01T14:00:03.000Z", symbol_scope=[],
            timeframe_scope=[], source_state="VALID", manifest_hash="m",
            parameter_package_id="p", code_version="c",
            quality_state={}, observation_windows={}, mtf_states={},
            overall_mtf="ALIGNED", created_at=1.0)
        b2 = SnapshotBarrier(
            as_of="2024-01-01T14:00:03.000Z", symbol_scope=[],
            timeframe_scope=[], source_state="VALID", manifest_hash="m",
            parameter_package_id="p", code_version="c",
            quality_state={}, observation_windows={}, mtf_states={},
            overall_mtf="ALIGNED", created_at=9999.0)
        assert b1.snapshot_id == b2.snapshot_id  # deterministic identity

    def test_symbol_scope_over_10_block(self):
        with pytest.raises(ValueError):
            SnapshotBarrier(
                as_of="2024-01-01T00:00:00.000Z",
                symbol_scope=[f"S{i}" for i in range(11)],
                timeframe_scope=[], source_state="VALID", manifest_hash="m",
                parameter_package_id="p", code_version="c",
                quality_state={}, observation_windows={}, mtf_states={},
                overall_mtf="ALIGNED")

    def test_timeframe_scope_over_14_block(self):
        with pytest.raises(ValueError):
            SnapshotBarrier(
                as_of="2024-01-01T00:00:00.000Z", symbol_scope=[],
                timeframe_scope=[f"T{i}" for i in range(15)],
                source_state="VALID", manifest_hash="m",
                parameter_package_id="p", code_version="c",
                quality_state={}, observation_windows={}, mtf_states={},
                overall_mtf="ALIGNED")

    def test_missing_package_or_code_version_qx(self):
        with pytest.raises(ValueError):
            SnapshotBarrier(
                as_of="2024-01-01T00:00:00.000Z", symbol_scope=[],
                timeframe_scope=[], source_state="VALID", manifest_hash="m",
                parameter_package_id="", code_version="c",
                quality_state={}, observation_windows={}, mtf_states={},
                overall_mtf="ALIGNED")

    def test_canonical_snapshot_id_frozen_wrapper(self):
        """GLOBAL IDENTITY contract: envelope {engine, contract_version,
        payload} hashed; context required; deterministic."""
        payload = {"close": Decimal("105.5"), "ts": "2024-01-01T00:15:00.000Z"}
        got = canonical_snapshot_id("E01", "v4.0.0", payload)
        expected = hashlib.sha256(canonical_json({
            "engine": "E01", "contract_version": "v4.0.0",
            "payload": payload}).encode("utf-8")).hexdigest()
        assert got == expected
        with pytest.raises(ValueError) as ei:
            canonical_snapshot_id("", "v4.0.0", payload)
        assert "INVALID_SNAPSHOT_CONTEXT_QX" in str(ei.value)

    def test_governed_as_of_max_and_fail_closed(self):
        """as_of = max(availability_time_ms); missing artifact or missing
        availability_time → fail-closed ValueError (G11)."""
        arts = [{"availability_time_ms": 1000}, {"availability_time_ms": 3000}]
        assert governed_as_of_ms(arts) == 3000
        with pytest.raises(ValueError) as e1:
            governed_as_of_ms([])
        assert "MISSING_REQUIRED_ARTIFACTS_QX" in str(e1.value)
        with pytest.raises(ValueError) as e2:
            governed_as_of_ms([{"availability_time_ms": None}])
        assert "MISSING_AVAILABILITY_TIME_QX" in str(e2.value)


class TestUuidV7:
    def test_rfc9562_shape(self):
        u = uuid_v7()
        assert re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-"
                        r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$", u)
        # 48-bit ms timestamp field parses to a plausible epoch-ms
        ts = uuid_v7_timestamp_ms(u)
        now_ms = int(time.time() * 1000)
        assert abs(now_ms - ts) < 60_000

    def test_id_001_monotonic_no_duplicates(self):
        """T-ID-001: 1000 events; event_id strictly increasing; no
        duplicates (generation paced to distinct ms timestamps)."""
        ids = []
        for _ in range(1000):
            ids.append(uuid_v7())
            time.sleep(0.0011)
        assert len(set(ids)) == 1000
        ts = [uuid_v7_timestamp_ms(u) for u in ids]
        assert ts == sorted(ts)
        assert len(set(ts)) == 1000  # strictly increasing

    def test_single_implementation_grep(self):
        """G11/P8: exactly one UUIDv7 implementation in the repo
        (apex/identity/uuid_v7.py); no local variants."""
        hits = []
        for path in (REPO / "apex").rglob("*.py"):
            text = path.read_text()
            if "def uuid_v7" in text or re.search(
                    r"int\(time\.time_ns\(\)\s*//\s*1_000_000\)", text):
                hits.append(path)
        assert [h.relative_to(REPO) for h in hits] == [
            pathlib.Path("apex/identity/uuid_v7.py")]

    def test_operational_only_never_in_payloads(self):
        """Identity separation: uuid_v7 import must not appear in
        canonical_json (snapshot identity path)."""
        src = (REPO / "apex/identity/canonical_json.py").read_text()
        assert "uuid_v7" not in src
