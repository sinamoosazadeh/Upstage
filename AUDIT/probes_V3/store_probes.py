#!/usr/bin/env python3
"""Read-only SESSION V3 probes over isolated SQLite databases using repo DDL/code.

Run from the repository root with PYTHONDONTWRITEBYTECODE=1 and python3 -B.
Temporary databases are created under TemporaryDirectory and removed at exit.
No network, data/, credentials, or device database is used.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apex.data_catalog.contracts import MarketObservation
from apex.data_catalog.store.sqlite_store import SQLiteStore


def observation(*, high: str = "105", low: str = "95", close: str = "101",
                oi: Decimal | None = None, timestamp: str = "2026-09-27T00:00:00.000Z",
                sequence: int = 1, volume: str = "10", status: str = "CLOSED") -> MarketObservation:
    return MarketObservation(
        symbol="BTCUSDT", timeframe="1h", open=Decimal("100"),
        high=Decimal(high), low=Decimal(low), close=Decimal(close),
        volume=Decimal(volume), oi=oi, timestamp=timestamp, sequence=sequence,
        status=status, source="TOOBIT", availability_time="2026-09-27T01:00:00.000Z",
        oi_timestamp=None,
    )


async def k001() -> dict:
    with tempfile.TemporaryDirectory(prefix="v3-k001-") as td:
        store = await SQLiteStore(str(Path(td) / "probe.sqlite")).open()
        try:
            original = observation()
            correction = observation(high="107")
            original_id = await store.ingest_raw(original, "MISSING")
            corrected_id = await store.correct_raw(
                original_id, correction, "MISSING", "high-only correction", "V3-PROBE")
            raw = await (await store.db.execute(
                "SELECT event_id,high,content_hash FROM raw_observation ORDER BY rowid")).fetchall()
            market = await (await store.db.execute(
                "SELECT observation_id,high_price,candle_status,raw_payload_hash "
                "FROM market_observation ORDER BY rowid")).fetchall()
            revisions = await (await store.db.execute(
                "SELECT original_event_id,new_event_id FROM raw_revision ORDER BY rowid")).fetchall()
            window = await store.get_window("BTCUSDT", "1h", "2026-09-28T00:00:00.000Z", 5)
            return {
                "hash_equal_for_high_only_change": original.content_hash() == correction.content_hash(),
                "original_event_id": original_id,
                "correct_raw_returned_event_id": corrected_id,
                "raw_rows": [list(r) for r in raw],
                "market_rows": [list(r) for r in market],
                "revision_rows": [list(r) for r in revisions],
                "stored_window_highs": [str(o.high) for o in window],
            }
        finally:
            await store.close()


async def k002() -> dict:
    from apex.data_catalog.ingest.toobit_public import parse_kline_to_observation
    from apex.ops.engine_context import EngineContextProducer
    from datetime import datetime, timezone

    with tempfile.TemporaryDirectory(prefix="v3-k002-") as td:
        store = await SQLiteStore(str(Path(td) / "probe.sqlite")).open()
        try:
            open_ms = int(datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
            close_ms = open_ms + 3_600_000
            as_of = "2026-01-10T01:05:00.000Z"
            original = parse_kline_to_observation(
                "BTCUSDT", "1h", [open_ms, "100", "105", "95", "101", "10", close_ms], 1)
            original_id = await store.ingest_raw(original, "MISSING")
            producer = EngineContextProducer(store, environment="PAPER")
            before = await producer.window("BTCUSDT", "1h", as_of, 5)
            corrected = parse_kline_to_observation(
                "BTCUSDT", "1h", [open_ms, "100", "105", "95", "102", "10", close_ms], 1)
            new_id = await store.correct_raw(original_id, corrected, "MISSING", "late correction", "V3-PROBE")
            after = await producer.window("BTCUSDT", "1h", as_of, 5)
            revision = await (await store.db.execute(
                "SELECT original_event_id,new_event_id,correction_timestamp FROM raw_revision")).fetchone()
            raw = await (await store.db.execute(
                "SELECT event_id,close,availability_time FROM raw_observation ORDER BY rowid")).fetchall()
            return {
                "historical_as_of": as_of,
                "parser_availability_for_both_versions": [original.availability_time, corrected.availability_time],
                "before_correction": [str(o.close) for o in before],
                "correction_record": list(revision) if revision else None,
                "returned_new_event_id": new_id,
                "raw_rows": [list(r) for r in raw],
                "after_correction_same_historical_as_of": [str(o.close) for o in after],
            }
        finally:
            await store.close()


def synthetic_classifier():
    import hashlib
    import apex.ops.engine_context as ec
    timeframes, symbols = ec.training_scope()
    artifact = {
        "W": [[0.0] * 8 for _ in range(9)], "b": [0.0] * 9,
        "K": 9, "label_delay_candles": 48, "seed": 7,
        "fit_protocol": {"iterations": 1, "learning_rate": 0.1, "l2": 0.0, "class_weights": False},
        "training_window": {"start": "2020-01-01T00:00:00.000Z", "end": "2026-09-28T00:00:00.000Z",
            "timeframes": list(timeframes), "symbols": list(symbols),
            "default_timeframes": list(ec.DEFAULT_TRAINING_TIMEFRAMES),
            "default_symbols": list(ec.CORE10_SYMBOLS), "max_bars_per_cell": 1},
        "sample_count": 1, "training_query_sha256": "0" * 64,
    }
    artifact["artifact_sha256"] = ec.classifier_hash(artifact["W"], artifact["b"], artifact["seed"], artifact["fit_protocol"])
    return ec.validate_classifier(artifact)


def synthetic_context(event):
    import apex.ops.engine_context as ec
    from apex.fabric.context import COMPONENT_ENGINE
    from apex.ops.plan_bridge import REQUIRED_RISK_KEYS
    from apex.risk.kernel import RISK_LADDER_STATES, EMERGENCY_LADDER

    state = "NoRisk" if "NoRisk" in RISK_LADDER_STATES else sorted(RISK_LADDER_STATES)[0]
    emergency = "NORMAL" if "NORMAL" in EMERGENCY_LADDER else sorted(EMERGENCY_LADDER)[0]
    weights = [[0.0] * 8 for _ in range(9)]
    risk = {
        "capital": 10000.0, "portfolio_exposure": 0.0, "proposed_notional": 1.0,
        "capital_hard_cap": 10000.0, "circuit_breaker_engaged": False,
        "emergency_state": emergency, "per_symbol_exposure": 0.0,
        "symbol_cap": 10000.0, "portfolio_cap": 10000.0,
        "staleness_seconds": 0.0, "freshness_sla_seconds": 3600.0,
        "oi_lag_seconds": 0.0, "oi_lag_threshold_seconds": 3600.0,
        "is_risk_increase": False, "uncertainty_is_rising": False,
        "realized_daily_loss_fraction": 0.0, "realized_weekly_loss_fraction": 0.0,
        "consecutive_losses": 0, "time_to_expiry_days": {"applicable": False, "contract_type": "PERPETUAL"},
        "margin_health_fraction": 1.0, "min_quantity": 0.01,
        "contract_multiplier": 1.0, "risk_state": state,
    }
    assert set(risk) == set(REQUIRED_RISK_KEYS)
    return {
        "events": [event], "data_trust": 0.5, "q_raw": 0.5,
        "market_regime": "RANGE", "mtf_state": "ALIGNED", "utc_window_state": "ACTIVE",
        "is_overlap": False, "volatility_state": "NORMAL", "structure_state": "BULLISH",
        "regime_confidence": 0.5, "regime_uncertainty": 0.5, "divergence_magnitude": 0.0,
        "temporal_window_validity": 1.0, "atr": 1.0, "fvg_zones": [],
        "bos": {"strength": 0.5}, "regime_state": {"state": "RANGE"},
        "e11_context": {"ic_inputs": {"x": 0.0}, "history_windows": {},
            "classifier_W": weights, "classifier_b": [0.0] * 9, "regime_state": {"state": "RANGE"},
            "bridge_inputs": {"bars": [{"c": "101"}]}},
        "direction": 1, "pattern_id": "synthetic-pattern", "x": {"x": 0.0},
        "forecast_quality": 0.5, "forecast_rr": 1.0, "forecast_cost_r": 0.1,
        "window_qualities": [(0.5, 0.0)], "temporal_quality": "Q2", "volatility_quality": "Q2",
        "s_i": {name: 1.0 for name in COMPONENT_ENGINE},
        "q_i": {name: 0.5 for name in COMPONENT_ENGINE},
        "package": {"parameter_package_id": "synthetic-v3"}, "p_min_tf": 0.5,
        "p_min_source": ec.P_MIN_SOURCES[0], "c_min": 0.5, "freshness_ok": True,
        "risk": risk, "risk_state": state, "h_norm": 0.5,
        "family_status": "ACTIVE", "arbitration": {"decision": "PASS"},
    }


async def k003() -> dict:
    from dataclasses import replace
    from apex.data_catalog.contracts import LifecycleState, EvidenceEvent
    import apex.ops.engine_context as ec

    with tempfile.TemporaryDirectory(prefix="v3-k003-") as td:
        store = await SQLiteStore(str(Path(td) / "probe.sqlite")).open()
        original_loader = ec.load_classifier
        try:
            artifact = synthetic_classifier()
            ec.load_classifier = lambda path=None: artifact
            open_time = "2026-01-10T00:00:00.000Z"
            original = observation(timestamp=open_time, high="105", low="95", close="101")
            original = replace(original, availability_time="2026-01-10T01:00:00.000Z")
            original_id = await store.ingest_raw(original, "MISSING")
            producer = ec.EngineContextProducer(store, environment="PAPER")
            as_of = "2026-01-10T01:05:00.000Z"
            fp_before = await producer._input_fingerprint("BTCUSDT", "1h", as_of)
            event = EvidenceEvent(
                evidence_id="v3-k003-event", engine_id="E01", analyst_version="v3-probe",
                symbol="BTCUSDT", timeframe="1h", snapshot_id="v3-k003-snapshot",
                event_time=open_time, availability_time="2026-01-10T01:00:00.000Z",
                observation_window={}, feature_snapshot_id="v3-k003-feature",
                feature_dependencies=(), condition_state="BULLISH", direction=1,
                strength=0.5, confidence=0.5, quality=0.5, validity="VALID",
                fate_state=LifecycleState.ACTIVE, age=0.0, decay=0.0, explanation="synthetic prior context",
                parameter_version="synthetic-v3", lineage=(original_id,), resolution_class="Q2")
            await ec.persist_complete_evidence(store, [event])
            context = synthetic_context(event)
            await ec.append_context_fact(store, "BRIDGE_CONTEXT", "BTCUSDT", "1h", as_of,
                {"input_fingerprint": fp_before,
                 "context": {**context, "events": [event.evidence_id]}})
            corrected = observation(timestamp=open_time, high="106", low="95", close="102")
            corrected = replace(corrected, availability_time="2026-02-01T00:00:00.000Z")
            corrected_id = await store.correct_raw(original_id, corrected, "MISSING", "late availability", "V3-PROBE")
            fp_after = await producer._input_fingerprint("BTCUSDT", "1h", as_of)
            store_window = await store.get_window("BTCUSDT", "1h", as_of, 5)
            producer_window = await producer.window("BTCUSDT", "1h", as_of, 5)
            await producer.prepare("BTCUSDT", "1h", as_of)
            reused = await producer.get_bridge_context("BTCUSDT", "1h", as_of)
            return {
                "classifier_dependency": "synthetic in-memory artifact; passed repository validate_classifier; default model artifact absent",
                "fingerprint_before": fp_before, "fingerprint_after": fp_after,
                "fingerprint_unchanged": fp_before == fp_after,
                "original_event_id": original_id, "corrected_event_id": corrected_id,
                "store_get_window_closes": [str(o.close) for o in store_window],
                "producer_window_closes": [str(o.close) for o in producer_window],
                "prepare_reused_bridge_fact": reused["e11_context"]["bridge_inputs"]["bars"][0]["c"] == "101",
                "reused_prior_context_bar_close": reused["e11_context"]["bridge_inputs"]["bars"][0]["c"],
                "real_compose_called": False,
                "scope_note": "prepare cache-hit path, raw join, and window are real; prior context/evidence are schema-valid synthetic placeholders; no native setup/plan is claimed",
            }
        finally:
            ec.load_classifier = original_loader
            await store.close()


async def k004() -> dict:
    with tempfile.TemporaryDirectory(prefix="v3-k004-") as td:
        store = await SQLiteStore(str(Path(td) / "probe.sqlite")).open()
        try:
            original = observation()
            original_id = await store.ingest_raw(original, "MISSING")
            replacement = MarketObservation(
                symbol="ETHUSDT", timeframe="1h", open=Decimal("200"), high=Decimal("207"),
                low=Decimal("195"), close=Decimal("202"), volume=Decimal("12"), oi=None,
                timestamp=original.timestamp, sequence=2, status="CLOSED", source="TOOBIT",
                availability_time=original.availability_time)
            replacement_id = await store.correct_raw(
                original_id, replacement, "MISSING", "cross-cell API probe", "V3-PROBE")
            market = await (await store.db.execute(
                "SELECT symbol,timeframe,open_time,close_price,candle_status,observation_id "
                "FROM market_observation ORDER BY rowid")).fetchall()
            revision = await (await store.db.execute(
                "SELECT original_event_id,new_event_id FROM raw_revision")).fetchone()
            return {"original_event_id": original_id, "returned_new_event_id": replacement_id,
                "revision": list(revision) if revision else None,
                "market_rows": [list(r) for r in market]}
        finally:
            await store.close()


async def k005() -> dict:
    import sqlite3
    with tempfile.TemporaryDirectory(prefix="v3-k005-") as td:
        store = await SQLiteStore(str(Path(td) / "probe.sqlite")).open()
        try:
            original = observation()
            original_id = await store.ingest_raw(original, "MISSING")
            await store.db.execute("CREATE TRIGGER v3_fail_revision BEFORE INSERT ON raw_revision "
                "BEGIN SELECT RAISE(ABORT,'V3_INJECTED_REVISION_FAILURE'); END")
            await store.db.commit()
            corrected = observation(high="107", close="102")
            caught = None
            try:
                await store.correct_raw(original_id, corrected, "MISSING", "fault probe", "V3-PROBE")
            except sqlite3.IntegrityError as exc:
                caught = f"{type(exc).__name__}: {exc}"
                await store.db.rollback()
            raw = await (await store.db.execute(
                "SELECT event_id,high,close FROM raw_observation ORDER BY rowid")).fetchall()
            market = await (await store.db.execute(
                "SELECT symbol,high_price,close_price,candle_status FROM market_observation ORDER BY rowid")).fetchall()
            revision_count = await (await store.db.execute("SELECT COUNT(*) FROM raw_revision")).fetchone()
            retention_count = await (await store.db.execute(
                "SELECT COUNT(*) FROM retention_event WHERE event_kind='CORRECTION'")).fetchone()
            return {"injected_error": caught, "raw_rows": [list(r) for r in raw],
                "market_rows_after_rollback": [list(r) for r in market],
                "revision_count": revision_count[0], "correction_retention_event_count": retention_count[0]}
        finally:
            await store.close()


async def k006() -> dict:
    import hashlib
    import datetime as dt
    from apex.data_catalog.catalog import Catalog
    from apex.identity.canonical_json import canonical_json
    from apex.ops.engine_context import EngineContextProducer, closed_engine_window, adv_base_volume, BridgeError
    from apex.ops.paper_loop import PaperRuntime, CellRefusal
    from apex.ops.plan_bridge import PaperPlanBridge

    with tempfile.TemporaryDirectory(prefix="v3-k006-") as td:
        store = await SQLiteStore(str(Path(td) / "probe.sqlite")).open()
        try:
            start = dt.datetime(2026, 8, 29, tzinfo=dt.timezone.utc)
            as_of_dt = dt.datetime(2026, 9, 28, 1, tzinfo=dt.timezone.utc)
            as_of = as_of_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            original_id = None
            original_last = None
            for i in range(720):
                opening = start + dt.timedelta(hours=i)
                closing = opening + dt.timedelta(hours=1)
                stamp = opening.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                available = closing.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                obs = MarketObservation(symbol="BTCUSDT", timeframe="1h", open=Decimal("100"),
                    high=Decimal("101"), low=Decimal("99"), close=Decimal("100"), volume=Decimal("1"),
                    oi=None, timestamp=stamp, sequence=i+1, status="CLOSED", source="V3-SYNTHETIC",
                    availability_time=available, oi_timestamp=None)
                original_id = await store.ingest_raw(obs, "MISSING")
                if i == 719:
                    original_last = obs
            corrected = MarketObservation(symbol="BTCUSDT", timeframe="1h", open=Decimal("100"),
                high=Decimal("101"), low=Decimal("99"), close=Decimal("100.5"), volume=Decimal("1"),
                oi=None, timestamp=original_last.timestamp, sequence=721, status="CLOSED", source="V3-SYNTHETIC",
                availability_time=as_of, oi_timestamp=None)
            corrected_id = await store.correct_raw(original_id, corrected, "MISSING", "K-006 probe", "V3-PROBE")
            raw_window = await store.get_window("BTCUSDT", "1h", as_of, 300)
            producer = EngineContextProducer(store, environment="PAPER")
            normalized = closed_engine_window(raw_window, "1h")

            runtime = object.__new__(PaperRuntime)
            runtime.store = store
            payload = {"symbol": "BTCUSDT", "timeframe": "1h", "cell_id": "BTCUSDT:1h",
                "as_of": as_of, "context": {"cell_state": {}}}
            await runtime._stage_ingest(payload)
            paper_quality_error = None
            try:
                await runtime._stage_quality(payload)
            except CellRefusal as exc:
                paper_quality_error = {"reason": exc.reason, "detail": exc.detail}

            bridge = PaperPlanBridge(store=store, environment="PAPER")
            bridge_raw_error = None
            try:
                await bridge._window({}, symbol="BTCUSDT", timeframe="1h", as_of=as_of)
            except BridgeError as exc:
                bridge_raw_error = {"reason": exc.reason, "detail": exc.detail}
            normalized_bridge_bars = await bridge._window({"bars": normalized},
                symbol="BTCUSDT", timeframe="1h", as_of=as_of)

            catalog = Catalog(provider=store)
            catalog_error = None
            catalog_result = None
            try:
                result = await catalog.get("body_ratio", "BTCUSDT", "1h", as_of, lookback=1)
                catalog_result = {"status": result.status.value, "reason": result.reason, "value": str(result.value)}
            except ValueError as exc:
                catalog_error = f"{type(exc).__name__}: {exc}"

            venue_sources = {
                "exchange_info": {"endpoint": "/synthetic/exchangeInfo", "record": {
                    "symbol": "BTCUSDT", "volumeUnit": "BASE", "contractType": "PERPETUAL",
                    "contractMultiplier": "1", "takerCommissionRate": "0.001"}},
                "funding": {"endpoint": "/synthetic/fundingRate", "rate": "0"},
            }
            facts = {"symbol": "BTCUSDT", "observed_at": as_of, "commission_rate": "0.001",
                "funding_rate": "0", "contract_multiplier": "1", "contract_type": "PERPETUAL",
                "expiry_time": None, "commission_field": "takerCommissionRate", "sources": venue_sources,
                "source_sha256": hashlib.sha256(canonical_json(venue_sources).encode()).hexdigest()}
            payload_facts = {"venue_facts": facts}
            package_id = "V3-SYNTHETIC-PUBLIC-FACTS"
            bound = {"source_state": "PUBLIC_VENUE_FACTS", **payload_facts, "parameter_package_id": package_id}
            snapshot_id = hashlib.sha256(canonical_json(bound).encode()).hexdigest()
            await store.insert_snapshot({"snapshot_id": snapshot_id, "as_of": as_of,
                "symbol_scope": ["BTCUSDT"], "source_state": "PUBLIC_VENUE_FACTS",
                "parameter_package_id": package_id, "code_version": "V3-PROBE", "quality_state": payload_facts})
            adv_error = None
            adv_result = None
            try:
                adv_result = await producer.adv_input("BTCUSDT", as_of)
            except BridgeError as exc:
                adv_error = {"reason": exc.reason, "detail": exc.detail}
            all_closed = [{"open_time_ms": int((start + dt.timedelta(hours=i)).timestamp()*1000),
                "timeframe": "1h", "status": "CLOSED", "availability_ms": int(((start + dt.timedelta(hours=i+1)).timestamp())*1000),
                "volume": 1.0} for i in range(720)]
            adv_closed_control = adv_base_volume(all_closed, as_of_ms=int(as_of_dt.timestamp()*1000), volume_unit="BASE")
            return {
                "original_event_id": original_id, "corrected_event_id": corrected_id,
                "corrected_status_from_store": raw_window[-1].status,
                "closed_engine_window_status": normalized[-1].status,
                "paper_runtime_ingest_rows": len(payload["context"]["cell_state"]["window"]),
                "paper_runtime_quality_refusal": paper_quality_error,
                "plan_bridge_raw_store_window_refusal": bridge_raw_error,
                "plan_bridge_normalized_producer_window_accepted": len(normalized_bridge_bars) == len(normalized),
                "catalog_body_ratio_result": catalog_result,
                "catalog_body_ratio_exception": catalog_error,
                "producer_adv_result": adv_result, "producer_adv_refusal": adv_error,
                "adv_all_closed_control_value": adv_closed_control,
                "scope_note": "720 market rows and synthetic public facts are isolated SQLite inputs; producer/loop/bridge/catalog code is real; no network, device data, trade, or native engine bundle was used",
            }
        finally:
            await store.close()


async def k007() -> dict:
    import sqlite3
    old_open = "2024-01-15T00:00:00.000Z"
    old_availability = "2024-01-15T01:00:00.000Z"
    with tempfile.TemporaryDirectory(prefix="v3-k007-") as td:
        store = await SQLiteStore(str(Path(td) / "probe.sqlite")).open()
        try:
            original = MarketObservation(symbol="BTCUSDT", timeframe="1h", open=Decimal("100"),
                high=Decimal("105"), low=Decimal("95"), close=Decimal("101"), volume=Decimal("10"),
                oi=None, timestamp=old_open, sequence=1, status="CLOSED", source="V3-PROBE",
                availability_time=old_availability, oi_timestamp=None)
            original_id = await store.ingest_raw(original, "MISSING")
            corrected = MarketObservation(symbol="BTCUSDT", timeframe="1h", open=Decimal("100"),
                high=Decimal("106"), low=Decimal("95"), close=Decimal("102"), volume=Decimal("10"),
                oi=None, timestamp=old_open, sequence=2, status="CLOSED", source="V3-PROBE",
                availability_time=old_availability, oi_timestamp=None)
            corrected_id = await store.correct_raw(original_id, corrected, "MISSING", "old corrected row", "V3-PROBE")
            fk_enabled = (await (await store.db.execute("PRAGMA foreign_keys")).fetchone())[0]
            purge_error = None
            try:
                await store.retention_purge(actor="V3-PROBE")
            except sqlite3.IntegrityError as exc:
                purge_error = f"{type(exc).__name__}: {exc}"
            raw = await (await store.db.execute(
                "SELECT event_id,as_of FROM raw_observation ORDER BY rowid")).fetchall()
            market = await (await store.db.execute(
                "SELECT candle_status FROM market_observation ORDER BY rowid")).fetchall()
            revisions = await (await store.db.execute(
                "SELECT original_event_id,new_event_id FROM raw_revision")).fetchall()
            retention = await (await store.db.execute(
                "SELECT event_kind,detail FROM retention_event ORDER BY rowid")).fetchall()
            purge_flag = await (await store.db.execute("SELECT COUNT(*) FROM purge_allow")).fetchone()
            return {"original_event_id": original_id, "corrected_event_id": corrected_id,
                "foreign_keys_enabled": fk_enabled, "injected_failure": False,
                "retention_purge_error": purge_error, "raw_rows_after_attempt": [list(r) for r in raw],
                "market_statuses_after_attempt": [r[0] for r in market],
                "revision_rows_after_attempt": [list(r) for r in revisions],
                "retention_events_after_attempt": [list(r) for r in retention],
                "purge_allow_rows_after_attempt": purge_flag[0]}
        finally:
            await store.close()


async def k008() -> dict:
    from apex.ops.engine_context import EngineContextProducer, CELL_QUERY, BridgeError
    old_open = "2024-01-15T00:00:00.000Z"
    old_availability = "2024-01-15T01:00:00.000Z"
    with tempfile.TemporaryDirectory(prefix="v3-k008-") as td:
        store = await SQLiteStore(str(Path(td) / "probe.sqlite")).open()
        try:
            obs = MarketObservation(symbol="BTCUSDT", timeframe="1h", open=Decimal("100"),
                high=Decimal("105"), low=Decimal("95"), close=Decimal("101"), volume=Decimal("10"),
                oi=None, timestamp=old_open, sequence=1, status="CLOSED", source="V3-PROBE",
                availability_time=old_availability, oi_timestamp=None)
            event_id = await store.ingest_raw(obs, "MISSING")
            purged = await store.retention_purge(actor="V3-PROBE")
            raw_count = (await (await store.db.execute("SELECT COUNT(*) FROM raw_observation")).fetchone())[0]
            market_count = (await (await store.db.execute("SELECT COUNT(*) FROM market_observation")).fetchone())[0]
            window = await store.get_window("BTCUSDT", "1h", "2026-09-28T01:00:00.000Z", 10)
            cell_discovery = [list(r) for r in await (await store.db.execute(CELL_QUERY)).fetchall()]
            producer = EngineContextProducer(store, environment="PAPER")
            producer_error = None
            try:
                await producer.window("BTCUSDT", "1h", "2026-09-28T01:00:00.000Z", 10)
            except BridgeError as exc:
                producer_error = {"reason": exc.reason, "detail": exc.detail}
            purge_events = [list(r) for r in await (await store.db.execute(
                "SELECT event_kind,detail FROM retention_event WHERE event_kind='PURGE_RAW'")).fetchall()]
            return {"purged_event_ids": purged, "original_event_id": event_id,
                "raw_count_after_purge": raw_count, "market_count_after_purge": market_count,
                "legacy_get_window_rows": len(window), "legacy_get_window_status": window[0].status if window else None,
                "producer_window_refusal": producer_error, "training_cell_discovery": cell_discovery,
                "purge_events": purge_events}
        finally:
            await store.close()


async def k009() -> dict:
    import datetime as dt
    from types import SimpleNamespace
    import apex.ops.engine_context as ec

    original_functions = {"upstream_frame": ec.upstream_frame,
        "structure_projection": ec.structure_projection,
        "structural_confirmation": ec.structural_confirmation,
        "training_rule0": ec.training_rule0,
        "compute_state_vector": ec.E11.compute_state_vector,
        "vector_to_array": ec.E11.vector_to_array,
        "mahalanobis_turbulence": ec.E11.mahalanobis_turbulence,
        "ewma_update": ec.E11.ewma_update}
    stack = {name: 1.0 for name in ec.E09.W_STACK_CORRECTED}
    history_sources = tuple(ec.HISTORY_KEYS.values())
    def synthetic_frame(raw_window, symbol, timeframe, **kwargs):
        latest = raw_window[-1]
        bias = float(latest.close) - 100.0 if timeframe == "4h" else (0.1 if timeframe == "1h" else 0.2)
        return {"projection_refusals": [],
            "volatility": {"states": [SimpleNamespace(atr14_wilder=1.0)]},
            "vlt": SimpleNamespace(atr14_wilder=1.0, regime="NORMAL"),
            "trend": {"bias": bias, "stack": dict(stack)},
            "ic": {key: 0.1 for key in history_sources}}
    def fake_state_vector(ic, history, previous_momentum):
        return ({"momentum_state": 0.0}, 0.0)

    ec.upstream_frame = synthetic_frame
    ec.structure_projection = lambda *args, **kwargs: {"synthetic": True}
    ec.structural_confirmation = lambda *args, **kwargs: True
    ec.training_rule0 = lambda vector, *, turbulence: "RANGE"
    ec.E11.compute_state_vector = fake_state_vector
    ec.E11.vector_to_array = lambda vector: [0.0] * 8
    ec.E11.mahalanobis_turbulence = lambda x, mu, sigma: 0.0
    ec.E11.ewma_update = lambda mu, sigma, x: (mu, sigma)

    def iso(value):
        return value.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    async def collect(generator):
        return [item async for item in generator]
    with tempfile.TemporaryDirectory(prefix="v3-k009-") as td:
        store = await SQLiteStore(str(Path(td) / "probe.sqlite")).open()
        try:
            as_of_dt = dt.datetime(2026, 1, 12, 3, tzinfo=dt.timezone.utc)
            as_of = iso(as_of_dt)
            async def insert_series(timeframe, start, count, minutes, close_override=None):
                ids = {}
                for i in range(count):
                    opening = start + dt.timedelta(minutes=i*minutes)
                    closing = opening + dt.timedelta(minutes=minutes)
                    close = Decimal(str((close_override or {}).get(i, "100.1")))
                    obs = MarketObservation(symbol="BTCUSDT", timeframe=timeframe, open=Decimal("100"),
                        high=Decimal("101"), low=Decimal("99"), close=close, volume=Decimal("10"), oi=None,
                        timestamp=iso(opening), sequence=i+1, status="CLOSED", source="V3-SYNTHETIC",
                        availability_time=iso(closing), oi_timestamp=None)
                    ids[i] = await store.ingest_raw(obs, "MISSING")
                return ids

            h4_start = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
            h4_target_open = dt.datetime(2026, 1, 11, 20, tzinfo=dt.timezone.utc)
            target_index = int((h4_target_open-h4_start).total_seconds() // (4*3600))
            h4_ids = await insert_series("4h", h4_start, 80, 240,
                {target_index: "100.25"})
            await insert_series("15m", dt.datetime(2026, 1, 11, 12, tzinfo=dt.timezone.utc), 60, 15)
            await insert_series("1h", dt.datetime(2026, 1, 10, tzinfo=dt.timezone.utc), 51, 60)

            producer = ec.EngineContextProducer(store, environment="PAPER")
            base_window = await producer.window("BTCUSDT", "1h", as_of, 301)
            initial = await collect(producer.feature_timeline(
                "BTCUSDT", "1h", base_window, incremental=True))
            before = initial[-1]["ic"]["bias_per_TF"]["H4"]
            before_trendiness = initial[-1]["ic"]["trendiness_raw"]
            target_original = MarketObservation(symbol="BTCUSDT", timeframe="4h", open=Decimal("100"),
                high=Decimal("101"), low=Decimal("99"), close=Decimal("99.15"), volume=Decimal("10"),
                oi=None, timestamp=iso(h4_target_open), sequence=target_index+100,
                status="CLOSED", source="V3-SYNTHETIC", availability_time=as_of, oi_timestamp=None)
            corrected_id = await store.correct_raw(h4_ids[target_index], target_original,
                "MISSING", "synthetic HTF correction", "V3-PROBE")
            base_after = await producer.window("BTCUSDT", "1h", as_of, 301)
            base_signatures_unchanged = [o.content_hash() for o in base_window] == [o.content_hash() for o in base_after]
            warm = await collect(producer.feature_timeline(
                "BTCUSDT", "1h", base_after, incremental=True))
            cold_producer = ec.EngineContextProducer(store, environment="PAPER")
            cold = await collect(cold_producer.feature_timeline(
                "BTCUSDT", "1h", base_after, incremental=False))
            current_h4 = await producer.window("BTCUSDT", "4h", as_of, 301)
            return {"base_window_bars": len(base_window), "h4_window_bars": len(current_h4),
                "h4_corrected_status": current_h4[-1].status,
                "h4_target_open_time": iso(h4_target_open), "corrected_event_id": corrected_id,
                "base_signatures_unchanged": base_signatures_unchanged,
                "initial_h4_bias": before, "initial_trendiness_raw": before_trendiness,
                "warm_timeline_h4_bias": warm[-1]["ic"]["bias_per_TF"]["H4"],
                "warm_timeline_trendiness_raw": warm[-1]["ic"]["trendiness_raw"],
                "warm_reused_same_last_item": warm[-1] is initial[-1],
                "cold_timeline_h4_bias": cold[-1]["ic"]["bias_per_TF"]["H4"],
                "cold_timeline_trendiness_raw": cold[-1]["ic"]["trendiness_raw"],
                "scope_note": "real feature_timeline/cache, SQLiteStore windows, raw lineage and correct_raw were run; synthetic upstream_frame/E11 projection helpers isolate cache behavior; this is not a native engine result or device data"}
        finally:
            await store.close()
            ec.upstream_frame = original_functions["upstream_frame"]
            ec.structure_projection = original_functions["structure_projection"]
            ec.structural_confirmation = original_functions["structural_confirmation"]
            ec.training_rule0 = original_functions["training_rule0"]
            ec.E11.compute_state_vector = original_functions["compute_state_vector"]
            ec.E11.vector_to_array = original_functions["vector_to_array"]
            ec.E11.mahalanobis_turbulence = original_functions["mahalanobis_turbulence"]
            ec.E11.ewma_update = original_functions["ewma_update"]


async def k010() -> dict:
    import datetime as dt
    from apex.ops.engine_context import page_quality_measurements, publish_quality_backfill, read_context_fact

    def iso(value):
        return value.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    monthly_starts = [dt.datetime(2026,1,1,tzinfo=dt.timezone.utc),
        dt.datetime(2026,2,1,tzinfo=dt.timezone.utc),
        dt.datetime(2026,4,1,tzinfo=dt.timezone.utc),
        dt.datetime(2026,5,1,tzinfo=dt.timezone.utc)]
    monthly_rows = []
    for i, opening in enumerate(monthly_starts):
        if opening.month == 12:
            closing = dt.datetime(opening.year+1,1,1,tzinfo=dt.timezone.utc)
        else:
            closing = dt.datetime(opening.year,opening.month+1,1,tzinfo=dt.timezone.utc)
        monthly_rows.append(MarketObservation(symbol="BTCUSDT", timeframe="1mo", open=Decimal("100"),
            high=Decimal("105"), low=Decimal("95"), close=Decimal("101"), volume=Decimal("10"), oi=None,
            timestamp=iso(opening), sequence=i+1, status="CLOSED", source="V3-PROBE",
            availability_time=iso(closing), oi_timestamp=None))
    monthly_page = page_quality_measurements(monthly_rows, "1mo", http_status=200)
    hourly_starts = [dt.datetime(2026,1,1,tzinfo=dt.timezone.utc)+dt.timedelta(hours=i)
        for i in (0,1,3,4)]
    hourly_rows = [MarketObservation(symbol="BTCUSDT", timeframe="1h", open=Decimal("100"),
        high=Decimal("105"), low=Decimal("95"), close=Decimal("101"), volume=Decimal("10"), oi=None,
        timestamp=iso(opening), sequence=i+1, status="CLOSED", source="V3-PROBE",
        availability_time=iso(opening+dt.timedelta(hours=1)), oi_timestamp=None)
        for i, opening in enumerate(hourly_starts)]
    hourly_page = page_quality_measurements(hourly_rows, "1h", http_status=200)

    with tempfile.TemporaryDirectory(prefix="v3-k010-") as td:
        store = await SQLiteStore(str(Path(td) / "probe.sqlite")).open()
        try:
            for row in monthly_rows:
                await store.ingest_raw(row, "MISSING")
            backfill_result = await publish_quality_backfill(
                store, environment="PAPER", symbol="BTCUSDT", timeframe="1mo")
            target_open = iso(monthly_starts[-1])
            identity = await (await store.db.execute(
                "SELECT observation_id FROM market_observation WHERE symbol='BTCUSDT' "
                "AND timeframe='1mo' AND open_time=?", (target_open,))).fetchone()
            fact = await read_context_fact(store, "QUALITY_"+identity[0], "BTCUSDT", "1mo",
                iso(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=1)))
            return {"monthly_page_measurements": monthly_page,
                "hourly_one_gap_control": hourly_page,
                "backfill_report_counts": {k:backfill_result[k] for k in ("written","already_present","skipped")},
                "may_backfill_measurements": fact["measurements"],
                "may_backfill_quality_state": fact["quality_state"],
                "scope_note": "real page_quality_measurements and publish_quality_backfill ran; monthly/hourly rows are synthetic and stored only in temporary repository SQLite; no owner data or network was used"}
        finally:
            await store.close()


async def main(row: str) -> dict:
    probes = {"K-001": k001, "K-002": k002, "K-003": k003, "K-004": k004, "K-005": k005, "K-006": k006, "K-007": k007, "K-008": k008, "K-009": k009, "K-010": k010}
    if row not in probes:
        raise SystemExit(f"probe not yet implemented: {row}")
    return {"id": row, "probe": probes[row].__name__, "result": await probes[row]()}


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("usage: python store_probes.py K-001")
    print(json.dumps(asyncio.run(main(sys.argv[1])), sort_keys=True, indent=2))
