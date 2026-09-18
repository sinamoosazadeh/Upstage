"""CP-14 A: actual SQLite sources, not injected engine/bridge contexts."""
import asyncio
from dataclasses import replace
import math

import pytest

from apex.data_catalog.contracts import TIMEFRAMES_14
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.identity.canonical_json import canonical_json
from apex.ops import engine_context as EC
from apex.ops.plan_bridge import BridgeError
from apex.quality.vector import QualityFlags, calc_quality_vector
from tests.integration.test_store_integration import make_obs


async def measured_bar(store, tf="1h", stamp="2026-01-01T00:00:00.000Z", *, index=0,
                       delay_ms=2000, flags=None, publish=True):
    opening = 100 + index*.1 + math.sin(index*.6)
    close = opening + math.cos(index*.6)*.3
    obs = replace(make_obs(timeframe=tf, ts=stamp, o=opening, c=close,
                          h=max(opening,close)+1, l=min(opening,close)-1,
                          v=1000+200*math.sin(index), oi=None), sequence=index,
                  availability_time="1970-01-01T00:00:00.000Z")
    await store.ingest_raw(obs, oi_state="MISSING")
    receipt = EC.close_time_ms(EC._iso_to_ms(stamp), tf)+delay_ms
    metadata = {"source_health": .95, "gap_count": 0,
                "expected_count": 1, "completeness_pct": 100.0}
    if publish:
        await EC.publish_quality_observation(store, obs,
            flags=flags or QualityFlags(True, True, False, True, True),
            measurements=metadata, receipt_time_ms=receipt,
            measured_at=EC._ms_to_iso(receipt), measurement_source="fixture-ingest-measurements-v1")
    return obs, receipt, metadata


def test_quality_store_native_readback_determinism_and_missing_not_healthy(tmp_path):
    async def run():
        store = await SQLiteStore(str(tmp_path/"source.sqlite")).open()
        try:
            obs, receipt, metadata = await measured_bar(store, publish=False)
            source = EC.EngineContextProducer(store, environment="PAPER")
            asof = EC._ms_to_iso(receipt)
            with pytest.raises(BridgeError, match="QUALITY_PROVENANCE_UNAVAILABLE"):
                await source.quality_window(obs.symbol, obs.timeframe, asof)
            identity = await EC.publish_quality_observation(store, obs,
                flags=QualityFlags(True, True, False, True, True), measurements=metadata,
                receipt_time_ms=receipt, measured_at=asof, measurement_source="fixture-measured")
            first = await source.quality_window(obs.symbol, obs.timeframe, asof)
            second = await EC.EngineContextProducer(store, environment="PAPER").quality_window(obs.symbol, obs.timeframe, asof)
            assert canonical_json(first) == canonical_json(second)
            assert first["quality_snapshot_ids"] == [identity]
            assert first["staleness_seconds"] == 2
            assert first["freshness_ok"] is True
            assert first["window"][0].source_health == .95
            assert first["window"][0].availability_time == "1970-01-01T00:00:00.000Z"
            assert first["q_raw"] == calc_quality_vector(first["window"][0], QualityFlags())[0]
            assert first["data_trust"] == first["q_raw"]
            with pytest.raises(BridgeError, match="QUALITY_PROVENANCE_UNAVAILABLE"):
                await source.quality_window(obs.symbol, obs.timeframe, EC._ms_to_iso(receipt-1))
        finally:
            await store.close()
    asyncio.run(run())


@pytest.mark.parametrize("case", ["content", "identity", "receipt", "source", "flags", "measurements", "counts", "delay", "q_raw", "native_veto"])
def test_quality_store_refuses_bad_provenance_or_native_veto(tmp_path, case):
    async def run():
        store = await SQLiteStore(str(tmp_path/"source.sqlite")).open()
        try:
            obs, receipt, _ = await measured_bar(store)
            source = EC.EngineContextProducer(store, environment="PAPER")
            await source.window(obs.symbol, obs.timeframe, EC._ms_to_iso(receipt), 1)
            identity = source._raw_lineage[(obs.symbol,obs.timeframe,obs.timestamp,obs.content_hash())]["observation_id"]
            fact = await EC.read_context_fact(store, "QUALITY_"+identity, obs.symbol, obs.timeframe, EC._ms_to_iso(receipt))
            fact.pop("fact_snapshot_id"); fact.pop("fact_as_of")
            if case == "content": fact["content_hash"] = "wrong"
            elif case == "identity": fact["observation_id"] = "wrong"
            elif case == "receipt": fact["receipt_time_ms"] = receipt+2
            elif case == "source": fact["measurement_source"] = ""
            elif case == "flags": fact["flags"]["schema_valid"] = 1
            elif case == "measurements": fact["measurements"].pop("source_health")
            elif case == "counts": fact["measurements"]["gap_count"] = -1
            elif case == "delay": fact["measurements"]["delay_seconds"] = 0
            elif case == "q_raw": fact["q_raw"] = .1
            elif case == "native_veto": fact["flags"]["schema_valid"] = False
            await EC.append_context_fact(store, "QUALITY_"+identity, obs.symbol, obs.timeframe, EC._ms_to_iso(receipt+1), fact)
            reason = "WINDOW_QUALITY_UNAVAILABLE" if case == "native_veto" else "QUALITY_PROVENANCE_UNAVAILABLE"
            with pytest.raises(BridgeError, match=reason):
                await source.quality_window(obs.symbol, obs.timeframe, EC._ms_to_iso(receipt+1))
        finally:
            await store.close()
    asyncio.run(run())


def test_quality_native_min_veto_cannot_be_hidden_by_healthy_latest(tmp_path):
    async def run():
        store = await SQLiteStore(str(tmp_path/"source.sqlite")).open()
        try:
            await measured_bar(store, flags=QualityFlags(True,False,False,True,True))
            obs, receipt, _ = await measured_bar(store, stamp="2026-01-01T01:00:00.000Z", index=1)
            with pytest.raises(BridgeError, match="WINDOW_QUALITY_UNAVAILABLE: QUARANTINED_ORDERING"):
                await EC.EngineContextProducer(store).quality_window(obs.symbol, obs.timeframe, EC._ms_to_iso(receipt))
        finally:
            await store.close()
    asyncio.run(run())


def test_quality_store_excludes_raw_available_after_asof(tmp_path):
    async def run():
        store = await SQLiteStore(str(tmp_path/"source.sqlite")).open()
        try:
            obs, receipt, _ = await measured_bar(store)
            future = replace(obs, timestamp="2026-01-01T01:00:00.000Z", sequence=1,
                             availability_time="2026-01-01T03:00:00.000Z")
            await store.ingest_raw(future, oi_state="MISSING")
            result = await EC.EngineContextProducer(store).quality_window(obs.symbol, obs.timeframe, "2026-01-01T02:00:00.000Z")
            assert [o.timestamp for o in result["window"]] == [obs.timestamp]
        finally:
            await store.close()
    asyncio.run(run())


def test_mtf_source_actual_coarser_e09_and_quality_receipts(tmp_path):
    async def run():
        store = await SQLiteStore(str(tmp_path/"source.sqlite")).open()
        try:
            end = EC._iso_to_ms("2026-01-08T00:00:00.000Z")
            source = EC.EngineContextProducer(store, environment="PAPER")
            with pytest.raises(BridgeError, match="MTF_INSUFFICIENT"):
                await source.mtf_inputs("BTCUSDT", "1h", EC._ms_to_iso(end+2000))
            for tf, step in (("1h",3600000),("4h",14400000),("8h",28800000)):
                for i in range(70):
                    await measured_bar(store, tf, EC._ms_to_iso(end-(70-i)*step), index=i)
            result = await source.mtf_inputs("BTCUSDT", "1h", EC._ms_to_iso(end+2000))
            assert set(result["states"]) == {"1h","4h","8h"}
            for tf, state in result["states"].items():
                assert state["bias"] == result["frames"][tf]["trend"]["bias"]
                assert state["closed"] is True and state["freshness_ok"] is True
                assert state["as_of"] == end and state["receipt_time_ms"] == end+2000
                assert len(state["quality_snapshot_ids"]) == 70
            projection = EC.mtf_projection("BTCUSDT","1h",end+2000,result["states"])
            assert result["mtf_align"] == projection["mtf_align"]
            assert result["mtf_state"] == projection["mtf_state"]
        finally:
            await store.close()
    asyncio.run(run())


@pytest.mark.parametrize("tf", TIMEFRAMES_14)
def test_governed_holding_uses_sl12_known_bound_or_strictest(tf):
    start = EC._iso_to_ms("2026-01-01T00:00:00.000Z")
    expected = start
    for _ in range(24 if tf == "1h" else 12):
        expected = EC.close_time_ms(expected, tf)
    assert EC.governed_holding_end(start, tf) == expected


def test_native_bundle_without_injected_quality_or_mtf(tmp_path, monkeypatch):
    from tests.unit.test_engine_context import _seed_full_training_fixture, FIXTURE
    from apex.ops.bootstrap_service import latest_close_boundary
    actual_calls, outputs, phase = [], {}, {"active": False}
    native_complete = EC.complete_engine_bundle
    def tracked_complete(*args, **kwargs):
        phase["active"] = True
        try:
            return native_complete(*args, **kwargs)
        finally:
            phase["active"] = False
    monkeypatch.setattr(EC, "complete_engine_bundle", tracked_complete)
    for code, cls in (("E01",EC.E01.E01StructureEngine),("E02",EC.E02.E02LiquidityEngine),
        ("E12",EC.E12.E12TemporalEngine),("E03",EC.E03.E03VolumeEngine),
        ("E09",EC.E09.E09TrendEngine),("E05",EC.E05.E05FVGEngine),
        ("E06",EC.E06.E06OrderBlockEngine),("E11",EC.E11.E11RegimeEngine),
        ("E07",EC.E07.E07RTMEngine),("E08",EC.E08.E08WyckoffEngine)):
        original = cls.compute
        def tracked(self, *args, _code=code, _original=original, **kwargs):
            if phase["active"]: actual_calls.append(_code)
            result = _original(self,*args,**kwargs)
            if phase["active"]: outputs[_code] = list(result)
            return result
        monkeypatch.setattr(cls,"compute",tracked)
    native_fvg = EC.E05.run_engine
    def tracked_fvg(*args, **kwargs):
        if phase["active"]: actual_calls.append("E05")
        return native_fvg(*args, **kwargs)
    monkeypatch.setattr(EC.E05, "run_engine", tracked_fvg)
    # E04/E10 consume their native streams and materialize directly (rather
    # than replaying their generic open/close-incompatible compute wrappers).
    for code, cls in (("E04",EC.E04.E04VolatilityEngine),("E10",EC.E10.E10MomentumEngine)):
        original = cls._window_quality
        def tracked(window, _code=code, _original=original):
            if phase["active"]: actual_calls.append(_code)
            return _original(window)
        monkeypatch.setattr(cls,"_window_quality",staticmethod(tracked))
    async def run():
        store = await SQLiteStore(str(tmp_path/"native.sqlite")).open()
        try:
            await _seed_full_training_fixture(store, symbols=("ETHUSDT",))
            asof = "2026-01-08T12:00:00.000Z"
            end = EC._iso_to_ms(asof)
            source = EC.EngineContextProducer(store, environment="PAPER", classifier_path=FIXTURE)
            # Extend the actual fixture's coarser CLOSED frontier. These are
            # raw OHLCV, not E09 states or an injected alignment score.
            base = EC._iso_to_ms("2026-01-01T00:00:00.000Z")
            for tf, step in (("4h",14400000), ("8h",28800000)):
                stop = latest_close_boundary(end,tf)
                start = base if tf == "4h" else stop-70*step
                for index, stamp in enumerate(range(start,stop,step)):
                    p = 110+index*.1+math.sin(index)
                    obs = replace(make_obs(symbol="ETHUSDT", timeframe=tf,
                        ts=EC._ms_to_iso(stamp), o=p, c=p+.2,h=p+1,l=p-1,v=1000,oi=None),
                        sequence=1000+index, availability_time="1970-01-01T00:00:00.000Z")
                    await store.ingest_raw(obs,oi_state="MISSING")
            for tf in ("1h","4h","8h"):
                for obs in await source.window("ETHUSDT",tf,asof,300):
                    receipt = EC.close_time_ms(EC._iso_to_ms(obs.timestamp),tf)
                    await EC.publish_quality_observation(store,obs,
                        flags=QualityFlags(True,True,False,True,True),
                        measurements={"source_health":.95,"gap_count":0,"expected_count":1,"completeness_pct":100.},
                        receipt_time_ms=receipt, measured_at=EC._ms_to_iso(receipt),
                        measurement_source="native-fixture-measured-ingestion")
            # No rtm_context argument: runtime derives both inputs from stores
            # and native confirmations, with the existing classifier loader.
            bundle = await source.prepare_engine_bundle("ETHUSDT","1h",asof)
            assert tuple(bundle["engine_order"]) == EC.ENGINE_ORDER
            assert set(bundle["measured_mtf"]["states"]) == {"1h","4h","8h"}
            assert bundle["measured_quality"]["window"][0].source_health == .95
            assert bundle["rtm_quality_contributors"]
            assert bundle["rtm_avg_quality"] == EC.confirmation_quality(bundle["rtm_quality_contributors"])
            events = bundle["events"]
            assert tuple(actual_calls) == EC.ENGINE_ORDER
            assert set(e.engine_id for e in events).issubset(EC.ENGINE_ORDER)
            for code, emitted in outputs.items():
                assert {e.evidence_id for e in emitted} == {e.evidence_id for e in events if e.engine_id == code}
            for event in events:
                event.validate_24_fields()
            restored = await EC.read_complete_evidence(store,[e.evidence_id for e in events])
            assert restored == events
            assert EC.forecast_vol_quantile(bundle["volatility_history"], bundle["vlt"], timeframe="1h") >= 0
            assert any(e.engine_id == "E05" and e.resolution_class == "QX" for e in restored)
        finally:
            await store.close()
    asyncio.run(run())
