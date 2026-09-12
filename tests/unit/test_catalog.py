"""CP-1 catalog tests: §3.13 completeness (74/74), registration
enforcement, tier-cache rules, catalog.get contract (T-DC-001..004),
OI policy (T-OM-001..003), deterministic replay (T-DR-001), monotonic
quality (T-MON-001), and §2.2 feature-value correctness."""
from __future__ import annotations

import asyncio
import random
from decimal import Decimal

import pytest

from apex.data_catalog.catalog import (
    AtomTierFailure,
    Catalog,
    build_registry,
)
from apex.data_catalog.contracts import (
    CatalogStatus,
    MarketObservation,
    OIState,
    ValidationError,
    oi_state_for,
    validate_market_observation,
)
from apex.identity.uuid_v7 import uuid_v7

TS_BASE = "2024-01-01T00:00:00.000Z"


def run(coro):
    return asyncio.run(coro)


def make_obs(symbol="BTCUSDT", timeframe="15m", o=100, h=105, l=98, c=102,
             v=10, oi=Decimal("500"), seq=0, status="CLOSED", ts=TS_BASE,
             availability=None, oi_lag=None, delay=0.0, completeness=100.0,
             source_health=1.0):
    return MarketObservation(
        symbol=symbol, timeframe=timeframe, open=Decimal(o),
        high=Decimal(h), low=Decimal(l), close=Decimal(c),
        volume=Decimal(v), oi=oi, timestamp=ts, sequence=seq,
        status=status, source="TOOBIT",
        availability_time=availability or ts,
        oi_lag_seconds=oi_lag, delay_seconds=delay,
        completeness_pct=completeness, source_health=source_health)


def make_window(n, close=None, step=1.0):
    obs = []
    for i in range(n):
        base = 100.0 + (i * step if close is None else 0)
        o = base if close is None else close[i]
        obs.append(make_obs(
            o=o, h=o + 5, l=o - 3, c=o + 2, v=10 + i, seq=i,
            ts=f"2024-01-01T00:{i // 60:02d}:{i % 60:02d}.000Z"))
    return obs


class FakeProvider:
    """In-memory WindowProvider (test double — lawful)."""

    def __init__(self, rows=None, frontier=None):
        self._rows = rows or {}
        self._frontier = frontier

    def add(self, symbol, timeframe, obs):
        self._rows.setdefault((symbol, timeframe), []).append(obs)

    def get_window(self, symbol, timeframe, as_of, bars):
        rows = [o for o in self._rows.get((symbol, timeframe), [])
                if o.status == "CLOSED" and o.timestamp <= as_of]
        return rows[-bars:]

    def max_availability_time(self, symbol, timeframe, as_of):
        if self._frontier:
            return self._frontier
        rows = self._rows.get((symbol, timeframe), [])
        if not rows:
            return None
        return max(o.availability_time for o in rows)


class TestRegistryCompleteness:
    def test_section_313_74_slots(self):
        """§3.13: registry count == catalogue count (74); every tier
        carries registered features."""
        catalog = Catalog()
        check = catalog.verify_completeness()
        assert check["count"] == 74
        assert check["tiers"] == {"ATOM": 44, "MOLE": 1, "ORGN": 29}

    def test_f74_full_template_and_f73_complete(self):
        catalog = Catalog()
        f74 = catalog.registry.lookup("sweep")
        assert f74 is not None
        assert f74.id.full_id == "APEX.L00.MOLE.LIQ.SWEEP.STRENGTH.V1"
        assert f74.lookback == 5 and f74.warmup == 20
        assert f74.validity.decay_formula == "exp(-0.02*age)"
        assert f74.confidence_equation == "0.9*Q_formula_valid*min(1,VolumeZ/2)"
        f73 = catalog.registry.lookup("volatility_regime")
        assert f73 is not None
        assert f73.id.full_id == "APEX.L00.ORGN.CTXT.VOLATILITY_R.SCORE.V1"
        assert f73.lookback == 50 and f73.warmup == 49
        assert f73.dependencies and f73.validity and f73.confidence_equation

    def test_f49_registered_removed_absent_by_design(self):
        catalog = Catalog()
        f49 = catalog.registry.lookup("funding_rate")
        assert f49 is not None  # slot registered
        assert "REMOVED" in f49.description

    def test_f56_market_profile_always_unavailable(self):
        catalog = Catalog()
        provider = FakeProvider()
        provider.add("BTCUSDT", "15m", make_obs())
        catalog.set_provider(provider)
        result = run(catalog.get("market_profile", "BTCUSDT", "15m", TS_BASE))
        assert result.status == CatalogStatus.UNAVAILABLE
        assert "WAVE_OUT" in result.reason

    def test_exact_feature_ids(self):
        catalog = Catalog()
        assert catalog.registry.lookup(
            "APEX.L00.ATOM.CNDL.BODY_RATIO.RATIO.V1").id.alias == "body_ratio"
        assert catalog.registry.lookup(
            "APEX.L00.ORGN.CTXT.UTC_ACTIVITY_WINDOW_HIGH.SCORE.V1"
        ).id.alias == "temporal_window_high"


class TestCatalogGetContract:
    def test_unregistered_feature_invalid(self):
        catalog = Catalog()
        result = run(catalog.get("not_a_feature", "BTCUSDT", "15m", TS_BASE))
        assert result.status == CatalogStatus.INVALID
        assert result.reason == "UNREGISTERED_FEATURE_ID"

    def test_future_as_of_invalid(self):
        catalog = Catalog()
        provider = FakeProvider(frontier="2024-01-01T00:00:00.000Z")
        catalog.set_provider(provider)
        result = run(catalog.get("body_ratio", "BTCUSDT", "15m",
                                 "2024-01-02T00:00:00.000Z"))
        assert result.status == CatalogStatus.INVALID
        assert result.reason == "PIT_FUTURE_AS_OF"

    def test_result_shape(self):
        catalog = Catalog()
        provider = FakeProvider()
        provider.add("BTCUSDT", "15m", make_obs(o=100, h=110, l=98, c=105))
        catalog.set_provider(provider)
        result = run(catalog.get("body_ratio", "BTCUSDT", "15m", TS_BASE))
        assert result.feature_id == "body_ratio"
        assert result.symbol == "BTCUSDT"
        assert result.timeframe == "15m"
        assert result.as_of == TS_BASE
        assert result.status == CatalogStatus.OK
        assert result.value == Decimal("0.416667")  # |105−100|/12, 6 digits
        assert result.q_component == 1.0
        assert result.availability_time == TS_BASE

    def test_no_provider_missing(self):
        catalog = Catalog()
        result = run(catalog.get("body_ratio", "BTCUSDT", "15m", TS_BASE))
        assert result.status == CatalogStatus.MISSING
        assert result.reason == "NO_WINDOW_PROVIDER"


class TestTierCacheRules:
    def test_atom_never_cached(self):
        catalog = Catalog()
        provider = FakeProvider()
        obs = make_obs()
        provider.add("BTCUSDT", "15m", obs)
        catalog.set_provider(provider)
        calls = []
        orig = catalog._computers["body_ratio"]
        def counting(window, params, context):
            calls.append(1)
            return orig(window, params, context)
        catalog._computers["body_ratio"] = counting
        run(catalog.get("body_ratio", "BTCUSDT", "15m", TS_BASE))
        run(catalog.get("body_ratio", "BTCUSDT", "15m", TS_BASE))
        assert len(calls) == 2  # ATOM recomputed every call

    def test_molecular_cached_5_candles(self):
        catalog = Catalog()
        provider = FakeProvider()
        for i in range(30):
            provider.add("BTCUSDT", "15m", make_obs(
                seq=i, v=10 + (i % 3), ts=f"2024-01-01T00:{i:02d}:00.000Z"))
        catalog.set_provider(provider)
        calls = []
        orig = catalog._computers["sweep"]
        def counting(window, params, context):
            calls.append(1)
            return orig(window, params, context)
        catalog._computers["sweep"] = counting
        as_of = "2024-01-01T00:29:00.000Z"
        run(catalog.get("sweep", "BTCUSDT", "15m", as_of))
        run(catalog.get("sweep", "BTCUSDT", "15m", as_of))
        assert len(calls) == 1  # cached within 5 candles

    def test_orgn_lru_100(self):
        from apex.data_catalog.performance import LRUCache
        cache = LRUCache(capacity=100)
        for i in range(150):
            cache.put(i, i)
        assert len(cache) == 100
        assert cache.get(0) is None  # evicted (oldest)
        assert cache.get(149) == 149


class TestTDC:
    def test_tdc_001_schema_fields(self):
        """T-DC-001: all 10 fields present; types match; required non-null."""
        obs = make_obs()
        validate_market_observation(obs)
        with pytest.raises(ValidationError) as ei:
            validate_market_observation(
                MarketObservation(symbol="", timeframe="15m",
                                  open=Decimal(1), high=Decimal(2),
                                  low=Decimal(0.5), close=Decimal(1.5),
                                  volume=Decimal(1), oi=None,
                                  timestamp=TS_BASE, sequence=0,
                                  status="CLOSED"))
        assert "E-Q-001" in str(ei.value)

    def test_tdc_002_validation_order_fail_fast(self):
        """T-DC-002: validation order respected; fail-fast on first error."""
        bad = MarketObservation(symbol="BTCUSDT", timeframe="15m",
                                open="not-decimal", high=Decimal(1),
                                low=Decimal(2), close=Decimal(3),
                                volume=Decimal(4), oi=None, timestamp="x",
                                sequence=0, status="CLOSED")
        with pytest.raises(ValidationError) as ei:
            validate_market_observation(bad)
        assert ei.value.code == "E-Q-001"  # schema first, not OHLC/QX

    def test_tdc_003_random_ohlc_no_false_rejects(self):
        """T-DC-003: 1000 random OHLC tuples; none rejected incorrectly."""
        rng = random.Random(42)
        for _ in range(1000):
            o = rng.uniform(1, 100000)
            c = rng.uniform(1, 100000)
            h = max(o, c) + rng.uniform(0, 100)
            l = min(o, c) - rng.uniform(0, min(o, c))
            if l < 0:
                l = 0
            obs = make_obs(o=o, h=h, l=l, c=c)
            validate_market_observation(obs)

    def test_tdc_003_invalid_rejected(self):
        for o, h, l, c in [(100, 99, 98, 101),  # H < max(O,C)
                           (100, 105, 101, 102),  # L > min(O,C)
                           (100, 99, 100, 100)]:  # H < L
            obs = make_obs(o=o, h=h, l=l, c=c)
            with pytest.raises(ValidationError):
                validate_market_observation(obs)

    def test_tdc_004_missing_oi_never_zero(self):
        """T-DC-004: 100 candles with missing OI; all MISSING, not 0."""
        for _ in range(100):
            state, q = oi_state_for(None, None, 60)
            assert state.value == "MISSING" and q == 0.0


class TestTOM:
    def test_tom_001_oi_states_all_triggered(self):
        """T-OM-001: 200 data points; all five states triggered; labels
        match semantics (AVAILABLE/STALE/MISSING/INVALID/DEGRADED)."""
        seen = set()
        for lag in [0, 10, 100, 1000, None]:
            for _ in range(40):
                state, _ = oi_state_for(Decimal("100"), lag, 60)
                seen.add(state)
        seen.add(oi_state_for(None, None, 60)[0])
        seen.add(oi_state_for(Decimal("-5"), 0, 60)[0])
        assert seen == {OIState.AVAILABLE, OIState.STALE, OIState.MISSING,
                        OIState.INVALID, OIState.DEGRADED}
        assert oi_state_for(Decimal("100"), 10, 60)[1] == 1.0   # AVAILABLE
        assert oi_state_for(Decimal("100"), 100, 60)[1] == 0.5  # STALE=0.5
        assert oi_state_for(Decimal("100"), 1000, 60)[1] == 0.2  # DEGRADED
        assert oi_state_for(None, None, 60)[1] == 0.0           # MISSING

    def test_tom_002_oi_dependent_feature_unavailable(self):
        """T-OM-002: OI-dependent feature unavailable when OI missing."""
        catalog = Catalog()
        provider = FakeProvider()
        provider.add("BTCUSDT", "15m", make_obs(oi=None))
        catalog.set_provider(provider)
        result = run(catalog.get("OI_z", "BTCUSDT", "15m", TS_BASE))
        assert result.status == CatalogStatus.MISSING
        assert result.reason == "OI_MISSING_QX"

    def test_tom_003_missing_data_blocks_dependent_path(self):
        """T-OM-003: rule requires OI; OI MISSING → rule does not fire."""
        catalog = Catalog()
        provider = FakeProvider()
        provider.add("BTCUSDT", "15m", make_obs(oi=None))
        catalog.set_provider(provider)
        result = run(catalog.get("open_interest_delta", "BTCUSDT", "15m",
                                 TS_BASE))
        # dependent rule cannot fire: MISSING (gate stays open, AI.6)
        assert result.status in (CatalogStatus.MISSING, CatalogStatus.UNAVAILABLE)


class TestReplayAndMonotonic:
    def test_tdr_001_feature_replay_byte_identical(self):
        """T-DR-001 (feature tier): identical inputs → byte-identical
        feature values (re-run produces identical results)."""
        window = make_window(30, close=[100.0 + i for i in range(30)])
        catalog = Catalog()
        provider = FakeProvider()
        for o in window:
            provider.add("BTCUSDT", "15m", o)
        catalog.set_provider(provider)
        as_of = window[-1].timestamp
        r1 = run(catalog.get("body_ratio", "BTCUSDT", "15m", as_of))
        r2 = run(catalog.get("body_ratio", "BTCUSDT", "15m", as_of))
        assert str(r1.value) == str(r2.value)
        r3 = run(catalog.get("volume_ratio", "BTCUSDT", "15m", as_of))
        r4 = run(catalog.get("volume_ratio", "BTCUSDT", "15m", as_of))
        assert str(r3.value) == str(r4.value)

    def test_tmon_001_quality_never_improves_with_fewer_inputs(self):
        """T-MON-001: feature quality at bar 50 ≥ bar 10 (more inputs
        never degrade availability)."""
        catalog = Catalog()
        provider = FakeProvider()
        for i in range(60):
            provider.add("BTCUSDT", "15m", make_obs(
                seq=i, ts=f"2024-01-01T00:{i:02d}:00.000Z"))
        catalog.set_provider(provider)
        early = run(catalog.get("ATR", "BTCUSDT", "15m",
                                "2024-01-01T00:09:00.000Z", lookback=15))
        late = run(catalog.get("ATR", "BTCUSDT", "15m",
                               "2024-01-01T00:59:00.000Z", lookback=15))
        assert early.status == CatalogStatus.UNAVAILABLE  # warmup: no bars
        assert late.status == CatalogStatus.OK              # 15 bars ⇒ ATR
        assert late.q_component >= early.q_component


class TestAtomFailureHaltsPipeline:
    def test_atom_failure_raises(self):
        """§3.12: a failure at the ATOM tier stops the whole pipeline."""
        catalog = Catalog()
        provider = FakeProvider()
        provider.add("BTCUSDT", "15m",
                     make_obs(o=100, h=98, l=99, c=98.5))  # H < L → INVALID
        catalog.set_provider(provider)
        with pytest.raises(AtomTierFailure):
            run(catalog.get("body_ratio", "BTCUSDT", "15m", TS_BASE))
