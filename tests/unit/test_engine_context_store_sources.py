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


def test_ladder_source_reads_native_revision_pit_and_never_defaults(tmp_path):
    from apex.risk.kernel import apply_ladder_state_migration, append_ladder_revision, ladder_revision
    async def run():
        store = await SQLiteStore(str(tmp_path/"ladder.sqlite")).open()
        try:
            source = EC.EngineContextProducer(store,environment="PAPER")
            asof = "2026-01-01T00:00:00.000Z"
            with pytest.raises(BridgeError,match="RISK_LADDER_UNAVAILABLE"):
                await source.ladder_input(asof)
            await apply_ladder_state_migration(store.db)
            with pytest.raises(BridgeError,match="RISK_LADDER_UNAVAILABLE"):
                await source.ladder_input(asof)
            native = ladder_revision(revision_id="fixture-native-revision",applied_at=asof,
                state="HighRisk",emergency_state="L1_PAUSE",consumed_budget=.5,
                reason="measured fixture exposure",snapshot_id="fixture-exposure")
            await append_ladder_revision(store.db,native)
            got = await source.ladder_input(asof)
            assert got["state"] == native.state
            assert got["emergency_state"] == native.emergency_state
            assert got["multiplier"] == native.multiplier
            with pytest.raises(BridgeError,match="RISK_LADDER_UNAVAILABLE"):
                await source.ladder_input("2025-12-31T23:59:59.999Z")
        finally: await store.close()
    asyncio.run(run())


def test_adv_store_reads_720_actual_bars_with_verified_units_and_pit(tmp_path):
    from tests.unit.test_engine_context import _PublicFactsFixture
    async def run():
        store = await SQLiteStore(str(tmp_path/"adv.sqlite")).open()
        try:
            fixture = _PublicFactsFixture()
            asof = "2026-02-01T12:00:00.000Z"
            midnight = EC._iso_to_ms("2026-02-01T00:00:00.000Z")
            source = EC.EngineContextProducer(store,environment="PAPER")
            await EC.persist_public_venue_facts(store,"BTCUSDT",environment="PAPER",
                client=fixture.client,now=lambda:(midnight-1)/1000)
            with pytest.raises(BridgeError,match="ADV_UNAVAILABLE"):
                await source.adv_input("BTCUSDT",asof)
            fixture.record["volumeUnit"] = "BASE"
            await EC.persist_public_venue_facts(store,"BTCUSDT",environment="PAPER",
                client=fixture.client,now=lambda:midnight/1000)
            with pytest.raises(BridgeError,match="ADV_UNAVAILABLE"):
                await source.adv_input("BTCUSDT",asof)
            volumes = []
            for i in range(720):
                obs,_,_ = await measured_bar(store,stamp=EC._ms_to_iso(midnight-(720-i)*3600000),index=i,publish=False)
                volumes.append(float(obs.volume))
            result = await source.adv_input("BTCUSDT",asof)
            assert result["adv"] == pytest.approx(sum(volumes)/30)
            assert len(result["observation_ids"]) == 720
            # Today's volume cannot leak into the previous-complete-days ADV.
            await measured_bar(store,stamp=EC._ms_to_iso(midnight),index=721,publish=False)
            assert canonical_json(await source.adv_input("BTCUSDT",asof)) == canonical_json(result)
            assert fixture.venue.calls and all(not c.api_key_present and "signature" not in c.params for c in fixture.venue.calls)
        finally: await store.close()
    asyncio.run(run())


def test_account_source_durable_pit_marks_pending_fills_and_losses(tmp_path):
    from decimal import Decimal
    from apex.ledger.store import LedgerWriter
    from tests.unit.test_engine_context import _PublicFactsFixture
    async def run():
        store = await SQLiteStore(str(tmp_path/"account.sqlite")).open()
        clock = {"now":"2026-01-01T01:00:00.000Z"}
        ledger = LedgerWriter(store,clock=lambda:clock["now"])
        await ledger.initialize(); await ledger.start()
        try:
            source = EC.EngineContextProducer(store,ledger=ledger,environment="PAPER")
            asof = "2026-01-01T01:00:02.000Z"
            empty = await source.paper_account_inputs(asof)
            assert empty["capital"] == 10000 and empty["reserved_notional"] == 0
            assert empty["margin_health_fraction"] == 1 and empty["consecutive_losses"] == 0
            assert empty["mark_set"]["mark_model"] == "PAPER_CLOSE_MARK"
            fixture = _PublicFactsFixture()
            await EC.persist_public_venue_facts(store,"BTCUSDT",environment="PAPER",
                client=fixture.client,now=lambda:EC._iso_to_ms(clock["now"])/1000)
            plan = {"proposal_id":"plan-000000000001","setup_id":"setup-source","symbol":"BTCUSDT","timeframe":"1h",
                "direction":"LONG","sized_quantity":10,"decision":"ALLOW","environment":"PAPER","contract_multiplier":1,
                "as_of":clock["now"],"created_utc":clock["now"]}
            await ledger.append_trade_plan(plan)
            await ledger.append_fsm_transition(intent_id="i-000000000001",from_state="READY",to_state="SUBMITTING",
                reason="fixture",trigger="SUBMIT_ORDER",environment="PAPER",
                evidence={"symbol":"BTCUSDT","quantity":"10","price":"100"})
            await ledger.append_fsm_transition(intent_id="i-000000000001",from_state="SUBMITTING",to_state="PARTIAL",
                reason="fixture",trigger="PARTIAL_FILL",environment="PAPER")
            await ledger.append_fill(intent_id="i-000000000001",fill_id="actual-fill",price="100",quantity="4",
                symbol="BTCUSDT",side="BUY_OPEN")
            with pytest.raises(BridgeError,match="PAPER_MARK_UNAVAILABLE"):
                await source.paper_account_inputs(asof)
            obs,_,_ = await measured_bar(store,"1m","2026-01-01T00:59:00.000Z")
            await store.db.execute("INSERT INTO setup_candidate (setup_id) VALUES (?)",("setup-source",))
            await store.db.commit()
            outcome = {"outcome_id":"closed-source","setup_id":"setup-source","pnl":"-25",
                       "exit_reason":"STOP_LOSS","context":{"environment":"PAPER"}}
            await ledger.append_outcome(outcome)
            actual = await source.paper_account_inputs(asof)
            assert actual["capital"] == 9975
            assert actual["open_notional"] == 4*obs.close
            assert actual["pending_notional"] == 600
            assert actual["margin_health_fraction"] == (Decimal(9975)-4*obs.close-600)/Decimal(9975)
            assert actual["realized_daily_loss_fraction"] == pytest.approx(25/9975)
            assert actual["consecutive_losses"] == 1
            assert actual["mark_set"]["mark_provenance"]["BTCUSDT"]["model"] == "PAPER_CLOSE_MARK"
            clock["now"] = "2026-01-02T01:00:00.000Z"
            await ledger.append(event_type="OWNER_REVIEW",actor="OWNER",kind="CONSECUTIVE_LOSSES")
            assert canonical_json(await source.paper_account_inputs(asof)) == canonical_json(actual)
            with pytest.raises(BridgeError,match="CIRCUIT_RESET_UNAVAILABLE"):
                await source.paper_account_inputs(clock["now"])
            assert (await ledger.verify_chain())["intact"]
        finally:
            await ledger.stop(); await store.close()
    asyncio.run(run())


@pytest.mark.parametrize("case",["correction","incomplete_outcome","orphan_fill","missing_plan_time","forged_review"])
def test_account_source_reachable_named_refusals(tmp_path,case):
    from apex.ledger.store import LedgerWriter
    async def run():
        store = await SQLiteStore(str(tmp_path/"refusals.sqlite")).open()
        stamp = "2026-01-01T00:00:00.000Z"
        ledger = LedgerWriter(store,clock=lambda:stamp)
        await ledger.initialize(); await ledger.start()
        try:
            source = EC.EngineContextProducer(store,ledger=ledger,environment="PAPER")
            if case == "correction":
                await ledger.append_correction(supersedes="unresolved-event",reason="fixture",delta={"pnl":"1"})
                reason = "PAPER_CORRECTION_UNAVAILABLE"
            elif case == "incomplete_outcome":
                await ledger.append(event_type="OUTCOME",outcome={"context":{"environment":"PAPER"}},pnl="1")
                reason = "PAPER_LOSS_UNAVAILABLE"
            elif case == "orphan_fill":
                await ledger.append_fill(intent_id="unknown",fill_id="f",price="10",quantity="1",symbol="BTCUSDT",side="BUY_OPEN")
                reason = "PAPER_ORDER_STATE_UNAVAILABLE"
            elif case == "missing_plan_time":
                await ledger.append_trade_plan({"proposal_id":"p","setup_id":"s","direction":"LONG",
                    "sized_quantity":1,"decision":"ALLOW","environment":"PAPER"})
                reason = "PAPER_ORDER_STATE_UNAVAILABLE"
            else:
                await ledger.append(event_type="CIRCUIT_RESET",actor="OWNER",environment="PAPER",kind="CONSECUTIVE_LOSSES")
                reason = "CIRCUIT_RESET_UNAVAILABLE"
            with pytest.raises(BridgeError,match=reason): await source.paper_account_inputs(stamp)
        finally: await ledger.stop(); await store.close()
    asyncio.run(run())
