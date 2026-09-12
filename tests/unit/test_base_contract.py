"""CP-1 engine base contract: versioned interfaces (v4.0.0), lifecycle
(only forward/terminal; T-MON-002 discipline), replay idempotency with
code-revision invalidation, emission → 24-field validation, Wave-Out
plumbing, catalog-only data access, frozen EPS."""
from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from apex.data_catalog.contracts import (
    CatalogResult,
    CatalogStatus,
    EvidenceEvent,
    LifecycleState,
)
from apex.engines.base import (
    CONTRACT_VERSION,
    ENGINE_IDS,
    INTERFACE_VERSION,
    EngineBase,
    EngineStateError,
)
from apex.errors import WaveOutError
from apex.identity.uuid_v7 import uuid_v7


def run(coro):
    return asyncio.run(coro)


class DemoEngine(EngineBase):
    engine_id = "E05"
    analyst_version = "1.2.3+" + "a" * 40
    code_revision = "b" * 40

    def compute(self, symbol, timeframe, as_of, context=None):
        return []


def ev(**overrides):
    base = dict(
        evidence_id=uuid_v7(), engine_id="E05",
        analyst_version="1.2.3+aaa", symbol="BTCUSDT", timeframe="15m",
        snapshot_id="s" * 64, event_time="2024-01-01T00:15:00.000Z",
        availability_time="2024-01-01T00:15:00.000Z",
        observation_window={}, feature_snapshot_id="s",
        feature_dependencies=(), condition_state="FVG", direction=1,
        strength=0.7, confidence=0.8, quality=0.9, validity="VALID",
        fate_state=LifecycleState.ACTIVE, age=None, decay=None,
        explanation="demo", parameter_version="p1", lineage=(),
        resolution_class="Q1")
    base.update(overrides)
    return EvidenceEvent(**base)


class TestVersionedInterfaces:
    def test_contract_version_frozen(self):
        assert CONTRACT_VERSION == "v4.0.0"
        assert INTERFACE_VERSION == "v4.0.0"
        eng = DemoEngine()
        assert eng.contract_version == "v4.0.0"

    def test_engine_ids(self):
        assert ENGINE_IDS == tuple(f"E{i:02d}" for i in range(1, 13))

    def test_invalid_engine_id_rejected(self):
        class Bad(EngineBase):
            engine_id = "E13"
            def compute(self, *a, **k):
                return []
        with pytest.raises(ValueError):
            Bad()


class TestLifecycle:
    def test_forward_transitions(self):
        eng = DemoEngine()
        assert eng.state == LifecycleState.CANDIDATE
        eng.confirm()
        eng.activate()
        assert eng.state == LifecycleState.ACTIVE

    def test_illegal_transitions_raise(self):
        eng = DemoEngine()
        with pytest.raises(EngineStateError):
            eng.activate()  # CANDIDATE → ACTIVE skips CONFIRMED
        eng.confirm()
        with pytest.raises(EngineStateError):
            eng.advance_state(LifecycleState.CANDIDATE)  # never backward

    def test_terminal_never_reverts(self):
        eng = DemoEngine()
        eng.confirm()
        eng.activate()
        eng.advance_state(LifecycleState.INVALIDATED)
        for state in LifecycleState:
            with pytest.raises(EngineStateError):
                eng.advance_state(state)


class TestReplayIdempotency:
    def test_replay_key_cached_and_code_revision_invalidates(self):
        eng = DemoEngine()
        key = eng.build_replay_key(
            "BTCUSDT", "15m", "2024-01-01T00:15:00.000Z",
            input_hash="h", parameter_package_id="pkg",
            canonical_payload='{"x":1}')
        assert len(key) == 64
        assert eng.replay_lookup(key) is None
        eng.replay_store(key, "result-1")
        assert eng.replay_lookup(key) == "result-1"  # cached within TTL
        # code_revision change discards cached results (AI.12)
        eng.code_revision = "c" * 40
        assert eng.replay_lookup(key) is None

    def test_replay_key_input_sensitivity(self):
        eng = DemoEngine()
        k1 = eng.build_replay_key("BTCUSDT", "15m", "2024-01-01T00:15:00.000Z",
                                  "h", "pkg", "{}")
        k2 = eng.build_replay_key("BTCUSDT", "15m", "2024-01-01T00:15:00.000Z",
                                  "h", "pkg2", "{}")
        assert k1 != k2


class TestEmission:
    def test_valid_event_published(self):
        eng = DemoEngine()
        collected = []
        class MiniBus:
            async def publish(self, bus_event):
                collected.append(bus_event)
        run(eng.emit(ev(), bus=MiniBus()))
        assert len(collected) == 1
        assert collected[0].topic == "evidence.E05.FVG"

    def test_invalid_engine_id_rejected(self):
        eng = DemoEngine()
        with pytest.raises(ValueError):
            run(eng.emit(ev(engine_id="E01")))

    def test_invalid_24_field_rejected(self):
        eng = DemoEngine()
        with pytest.raises(ValueError):
            run(eng.emit(ev(direction=2)))          # direction ∉ {-1,0,1}
        with pytest.raises(ValueError):
            run(eng.emit(ev(confidence=float("nan"))))  # non-finite
        with pytest.raises(ValueError):
            run(eng.emit(ev(resolution_class="Q9")))    # not Q0..QX


class TestWaveOut:
    def test_wave_out_plumbing(self):
        eng = DemoEngine()
        err = eng.wave_out("market_profile")
        assert isinstance(err, WaveOutError)
        with pytest.raises(WaveOutError):
            raise eng.wave_out("physical_postgresql")


class TestDataAccessAndEps:
    def test_feature_goes_through_catalog(self):
        eng = DemoEngine()
        class FakeCatalog:
            def __init__(self):
                self.got = None
            def get(self, feature_id, symbol, timeframe, as_of, lookback=1,
                    context=None):
                self.got = (feature_id, symbol, timeframe, as_of)
                return CatalogResult(
                    feature_id=feature_id, symbol=symbol, timeframe=timeframe,
                    as_of=as_of, value=Decimal("0.5"), q_component=1.0,
                    availability_time=as_of, snapshot_id=None,
                    status=CatalogStatus.OK, reason="")
        fake = FakeCatalog()
        eng._catalog = fake
        result = run(eng.feature("body_ratio", "BTCUSDT", "15m", "T"))
        assert result.value == Decimal("0.5")
        assert fake.got == ("body_ratio", "BTCUSDT", "15m", "T")

    def test_frozen_eps(self):
        eng = DemoEngine()
        assert eng.eps == Decimal("1e-8")  # E05 → 1e-8 (§2.2 table)

    def test_e01_scaled_eps(self):
        class E01Engine(DemoEngine):
            engine_id = "E01"
        eng = E01Engine()
        with pytest.raises(ValueError):
            _ = eng.eps  # scaled inputs required → fail-closed
        eng.set_eps_inputs(Decimal("0.1"), [Decimal(100)] * 20)
        assert eng.eps == Decimal("0.05")  # max(0.1*0.5, 100*1e-8, 1e-12)
