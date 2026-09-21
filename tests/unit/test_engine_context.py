"""CP-14 artifact, D21 labels, D14 freshness and PAPER accounting contracts."""
from __future__ import annotations

import asyncio
import copy
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from apex.config import Config, load_params
from apex.ops import engine_context as EC
from apex.ops.plan_bridge import BridgeError, _validate_e11_context
from apex.telegram.control_plane import ControlPlane, ENVS, EXPORT_ENVIRONMENTS
from tests.integration.test_store_integration import make_obs

FIXTURE = Path(__file__).parents[1] / "fixtures" / "e11_classifier_v1.yaml"


def test_classifier_loader_and_real_bridge_tensor_validation():
    artifact = EC.load_classifier(FIXTURE)
    _validate_e11_context({"classifier_W": artifact["W"], "classifier_b": artifact["b"],
                          "ic_inputs": {"test": 1}, "history_windows": {},
                          "regime_state": "TRANSITION"})
    assert artifact["artifact_sha256"] == EC.classifier_hash(
        artifact["W"], artifact["b"], artifact["seed"])


@pytest.mark.parametrize("change", ["W", "b", "K", "hash", "seed", "NaN", "delay", "window"])
def test_artifact_invalid_fails_closed(change):
    artifact = copy.deepcopy(EC.load_classifier(FIXTURE))
    if change == "W":
        artifact["W"].pop()
    elif change == "b":
        artifact["b"].pop()
    elif change == "K":
        artifact["K"] = 8
    elif change == "hash":
        artifact["artifact_sha256"] = "0" * 64
    elif change == "seed":
        artifact["seed"] = True
    elif change == "NaN":
        artifact["W"][0][0] = float("nan")
    elif change == "delay":
        artifact["label_delay_candles"] = 47
    else:
        artifact["training_window"]["end"] = "2020-01-01T00:00:00.000Z"
    with pytest.raises(BridgeError, match="CONFIGURATION_INVALID"):
        EC.validate_classifier(artifact)


def test_artifact_missing_is_lazy_and_has_no_fixture_fallback(tmp_path):
    assert Config().sqlite_path
    assert load_params()["paper_account"]["capital_usdt"] == 10000.0
    with pytest.raises(BridgeError, match="CONFIGURATION_INVALID"):
        EC.load_classifier(tmp_path / "missing.yaml")


@pytest.mark.parametrize("offset,expected", [(-1, True), (0, True), (30, True), (30.001, False)])
def test_freshness_exact_boundary_without_availability_rewrite(offset, expected):
    bar = replace(make_obs(timeframe="1h", ts="2026-01-01T00:00:00.000Z"),
                  availability_time="1970-01-01T00:00:00.000Z")
    measured = EC.freshness([bar], "1h", receipt_time=1767229200 + offset)
    assert measured["freshness_ok"] is expected
    assert measured["staleness_seconds"] == pytest.approx(max(0, offset))
    assert bar.availability_time == "1970-01-01T00:00:00.000Z"


def test_empty_window_is_explicit_not_a_truthiness_fallback():
    with pytest.raises(BridgeError, match="NO_MARKET_DATA"):
        EC.freshness([], "1h", receipt_time=0)


def test_paper_yaml_has_only_p7_keys():
    account = EC.load_paper_account()
    assert account == {"capital_usdt": 10000.0, "simulated_margin": {
        "warning_fraction": 0.60, "action_fraction": 0.40,
        "liquidation_approach_fraction": 0.20}}


def test_paper_ledger_balance_excludes_live_outcomes():
    class Ledger:
        async def read_ledger(self):
            return [SimpleNamespace(event_type="OUTCOME", raw={"pnl": amount,
                    "payload": {"outcome": {"context": {"environment": env}}}})
                    for env, amount in (("PAPER", "2.5"), ("PAPER", "-1"), ("LIVE", "999"))]
    assert asyncio.run(EC.paper_balance(Ledger())) == Decimal("10001.5")


def test_live_report_never_displays_injected_paper_balance():
    live = ControlPlane(environment="LIVE", paper_balance="12345.67")
    paper = ControlPlane(environment="PAPER", paper_balance="12345.67")
    assert "12,345.67" not in live.screen_main_menu()["title"]
    assert "UNAVAILABLE" in live.screen_main_menu()["title"]
    assert "12,345.67" in paper.screen_main_menu()["title"]
    assert "PAPER" in ENVS and "LIVE" in ENVS
    assert EXPORT_ENVIRONMENTS == ("PAPER", "LIVE")


def test_d21_tail_and_confirmation_boundaries():
    rule0 = ["TREND"] * 100
    confirmation = [False] * 100
    confirmation[48] = True
    result = EC.delayed_training_labels(rule0, confirmation)
    assert len(result) == 52
    assert result[0] == "TREND"  # confirmation at exactly t+48 is included
    assert result[47] == "TREND"
    assert result[48] == "TRANSITION"  # at t itself is not future confirmation
    assert result[-1] == "TRANSITION"


def test_d21_rule_has_no_entropy_dependency():
    v = {"trendiness": 0.1, "volatility": 0.5, "compression": 0.5,
         "expansion": 0.1, "participation": 0.5, "liquidity_stability": 0.5}
    assert EC.training_rule0(v, turbulence=15.499) == "RANGE"
    assert EC.training_rule0(v, turbulence=15.5) == "CRISIS"


class _StoredKlineResponder:
    """Public-client adapter over the required fake Toobit transport."""
    def __init__(self, rows):
        from tests.fake_toobit_responder import FakeToobitResponder

        class Venue(FakeToobitResponder):
            def _klines(self, params):
                data = rows.get((params["symbol"], params["interval"]), [])
                return [row for row in data if row[0] <= int(params["endTime"])][-int(params["limit"]):]

        self.responder = Venue()

    async def get_klines(self, symbol, interval, start_ms, end_ms, limit):
        from urllib.parse import urlencode
        from apex.execution.toobit_map import BASE_URL
        from apex.data_catalog.ingest.toobit_public import (
            parse_kline_to_observation, unwrap_toobit_response)
        response = await self.responder("GET", BASE_URL + "/api/v1/futures/klines",
            urlencode({"symbol": symbol, "interval": interval, "startTime": start_ms,
                       "endTime": end_ms, "limit": limit}), {})
        data = unwrap_toobit_response(response["body"], "klines")
        return [parse_kline_to_observation(symbol, interval, row, i)
                for i, row in enumerate(data)]


def _row(open_ms):
    return [open_ms, "100", "102", "99", "101", "10", 0]


def test_catch_up_frontier_boundary_and_failure_retry(tmp_path):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    from apex.ops import bootstrap_service as BS

    async def scenario():
        start = 1767225600000
        rows = {(symbol, tf): [_row(start), _row(start + 3600_000)]
                for symbol in ("BTCUSDT", "ETHUSDT") for tf in ("1h",)}
        client = _StoredKlineResponder(rows)
        bridge = BS.AsyncBridge().start()
        store = await SQLiteStore(str(tmp_path / "market.sqlite3")).open()
        source = BS.ToobitKlineSource(client=client, bridge=bridge)
        service = BS.BootstrapService(store=store, source=source,
            checkpoint_path=str(tmp_path / "progress.sqlite3"), cells=list(rows))
        await service.open()
        try:
            first = await service.catch_up(start + 3600_000)
            assert first == {"cells_checked": 2, "cells_updated": 2,
                             "bars_ingested": 2, "failures": []}
            assert await service.catch_up(start + 3600_001) == {
                "cells_checked": 0, "cells_updated": 0, "bars_ingested": 0, "failures": []}
            client.responder.fail_next(-1120)
            failed = await service.catch_up(start + 7200_000)
            assert failed["cells_checked"] == 2
            assert failed["bars_ingested"] == 1
            assert len(failed["failures"]) == 1
            assert failed["failures"][0]["cell"] == "BTCUSDT:1h"
            assert failed["failures"][0]["frontier"] == start
            assert failed["failures"][0]["error_code"] == "FETCH_FAILED"
            retry = await service.catch_up(start + 7200_001)
            assert retry["cells_checked"] == 2
            assert retry["bars_ingested"] == 1
            assert retry["failures"] == []
            assert (await store.get_window("BTCUSDT", "1h", "2026-01-02T00:00:00.000Z", 10))[-1].timestamp == "2026-01-01T01:00:00.000Z"
            # Four bars total: same frontier twice never duplicates a row.
            row = await (await store.db.execute("SELECT count(*) FROM raw_observation")).fetchone()
            assert row[0] == 4
        finally:
            await service.close()
            await store.close()
            bridge.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("tf,stamp,expected", [
    ("1h", "2026-01-01T01:00:00.000Z", "2026-01-01T01:00:00.000Z"),
    ("1w", "2026-09-17T10:00:00.000Z", "2026-09-14T00:00:00.000Z"),
    ("1mo", "2026-03-01T00:00:00.000Z", "2026-03-01T00:00:00.000Z"),
    ("1mo", "2026-02-28T23:59:59.999Z", "2026-02-01T00:00:00.000Z"),
])
def test_catch_up_calendar_boundaries(tf, stamp, expected):
    from apex.ops.bootstrap_service import latest_close_boundary, _iso_to_ms
    assert latest_close_boundary(_iso_to_ms(stamp), tf) == _iso_to_ms(expected)


def test_catch_up_failure_with_fresh_data_blocks_plan_only(tmp_path):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    from apex.ledger.store import LedgerWriter
    from apex.ops import bootstrap_service as BS, paper_loop as PL
    from apex.scheduler.clock import BundleCell, FixtureClock

    async def scenario():
        stamp = "2026-01-01T00:00:00.000Z"
        clock = FixtureClock("2026-01-01T01:00:00.000Z")
        store = await SQLiteStore(str(tmp_path / "store.sqlite3")).open()
        await store.ingest_raw(make_obs(timeframe="1h", ts=stamp), "AVAILABLE")
        # Only stage admission is exercised; no ledger/execution call occurs.
        class Ledger:
            async def read_ledger(self):
                return []
        calls = []
        async def provider(*args):
            calls.append(args)
        async def catch_up(now_ms):
            return {"cells_checked": 1, "cells_updated": 0, "bars_ingested": 0,
                    "failures": [{"cell": "BTCUSDT:1h", "error_code": "FETCH_FAILED",
                                  "frontier": 1767225600000}]}
        driver = PL.PaperRuntime(store=store, ledger=Ledger(), clock=clock,
            cells=[BundleCell("BTCUSDT", "1h")], plan_provider=provider, catch_up=catch_up)
        try:
            window = await store.get_window("BTCUSDT", "1h", clock.utc_now(), 10)
            assert EC.freshness(window, "1h", receipt_time=clock.now_ms()/1000)["freshness_ok"]
            cycle = await driver.run_cycle()
            assert calls == []
            assert cycle["halt_reasons"] == {"CATCH_UP_FAILED": 1}
            assert cycle["cell_runs"][0]["stages"][-1]["stage"] == "setup"
            assert cycle["catch_up"]["failures"][0]["frontier"] == 1767225600000
            assert "BTCUSDT:1h" not in driver._last_close
        finally:
            await store.close()
    asyncio.run(scenario())


def test_first_catch_up_checks_all_140_cells_then_only_due_timeframe(tmp_path):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    from apex.ops import bootstrap_service as BS

    async def scenario():
        client = _StoredKlineResponder({})
        bridge = BS.AsyncBridge().start()
        store = await SQLiteStore(str(tmp_path / "store.sqlite3")).open()
        service = BS.BootstrapService(store=store,
            source=BS.ToobitKlineSource(client=client, bridge=bridge),
            checkpoint_path=str(tmp_path / "progress.sqlite3"))
        await service.open()
        try:
            first = await service.catch_up(1767225600000)
            assert first["cells_checked"] == 140
            assert first["failures"] == []
            same = await service.catch_up(1767225601000)
            assert same["cells_checked"] == 0
            minute = await service.catch_up(1767225660000)
            assert minute["cells_checked"] == 10
            calls = client.responder.calls
            assert len(calls) == 150
            assert all(call.params["interval"] == "1m" for call in calls[-10:])
            assert all(not call.api_key_present for call in calls)
        finally:
            await service.close()
            await store.close()
            bridge.close()
    asyncio.run(scenario())


def test_catch_up_ingest_failure_resets_served_frontier(tmp_path, monkeypatch):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    from apex.ops import bootstrap_service as BS

    async def scenario():
        start = 1767225600000
        client = _StoredKlineResponder({("BTCUSDT", "1h"): [
            _row(start), _row(start + 3600_000)]})
        bridge = BS.AsyncBridge().start()
        store = await SQLiteStore(str(tmp_path / "store.sqlite3")).open()
        original = store.ingest_raw
        count = 0
        async def fail_second(*args):
            nonlocal count
            count += 1
            if count == 2:
                raise RuntimeError("injected ingestion failure")
            return await original(*args)
        monkeypatch.setattr(store, "ingest_raw", fail_second)
        service = BS.BootstrapService(store=store,
            source=BS.ToobitKlineSource(client=client, bridge=bridge),
            checkpoint_path=str(tmp_path / "progress.sqlite3"), cells=[("BTCUSDT", "1h")])
        await service.open()
        try:
            failed = await service.catch_up(start + 7200_000)
            assert failed["bars_ingested"] == 1
            assert len(failed["failures"]) == 1
            retry = await service.catch_up(start + 7200_000)
            assert retry["bars_ingested"] == 1
            assert retry["failures"] == []
        finally:
            await service.close()
            await store.close()
            bridge.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("oi_state", ["MISSING", "STALE", "INVALID", "DEGRADED", "AVAILABLE"])
def test_d23_formula_marker_and_only_q5_cap(oi_state):
    import math
    import numpy as np
    from tests.unit.test_e11_regime import ic, candle, seed_windows
    part = EC.participation_input(1.2, 2.0 if oi_state == "AVAILABLE" else None, oi_state)
    expected_raw = 1.52 if oi_state == "AVAILABLE" else 1.2
    assert part["participation_raw"] == pytest.approx(expected_raw)
    assert part["oi_state"] == oi_state
    assert part["contributing_features"]["participation"] == (
        "COMPLETE" if oi_state == "AVAILABLE" else "PARTIAL")
    inputs = {**ic(), **part}
    history = seed_windows()
    vector, _ = EC.E11.compute_state_vector(inputs, history, 0.5)
    assert vector["participation"] == pytest.approx(1 / (1 + math.exp(-expected_raw)))
    b = [0.0] * 9
    b[8] = 30.0
    result = EC.E11.run_engine([candle(0, inputs)], W=np.zeros((9, 8)), b=b,
                              history=history, mu0=EC.E11.vector_to_array(vector))
    EC.E11.validate_state_schema(result["regime_state"])
    assert result["regime_state"]["Q"] == ("Q5" if oi_state == "AVAILABLE" else "Q4")
    assert result["dependency_state"] == {"oi_state": oi_state,
                                          "contributing_features": part["contributing_features"]}
    # An already-lower quality is unchanged, not forced to Q4.
    noisy = EC.E11.run_engine([candle(0, inputs)], W=np.zeros((9, 8)), b=np.zeros(9),
                             history=history, mu0=EC.E11.vector_to_array(vector))
    assert noisy["regime_state"]["Q"] == "Q2"
    engine = EC.E11.E11RegimeEngine()
    events = engine.compute("BNBUSDT", "1h", "2026-01-15T14:00:00.000Z", {
        "candles": [candle(0, inputs)], "W": np.zeros((9, 8)), "b": b,
        "history": history, "mu0": EC.E11.vector_to_array(vector)})
    assert events
    assert all(e.observation_window["oi_state"] == oi_state for e in events)


def test_artifact_identity_reaches_canonical_e11_snapshot():
    from tests.unit.test_e11_regime import ic, candle, seed_windows
    engine = EC.E11.E11RegimeEngine()
    artifact = EC.load_classifier(FIXTURE)
    context = {"candles": [candle(0, ic())], "history": seed_windows(),
               "W": artifact["W"], "b": artifact["b"],
               "classifier_artifact_sha256": artifact["artifact_sha256"]}
    events = engine.compute("BNBUSDT", "1h", "2026-01-15T14:00:00.000Z", context)
    assert events
    original = events[0].snapshot_id
    context["classifier_artifact_sha256"] = "1" * 64
    changed = engine.compute("BNBUSDT", "1h", "2026-01-15T14:00:00.000Z", context)
    assert changed[0].snapshot_id != original


def test_d25_all_cells_strictest_anchor_and_cap():
    from apex.data_catalog.contracts import TIMEFRAMES_14
    policy = EC.load_decision_runtime()
    assert set(policy["p_min_tf"]) == set(TIMEFRAMES_14)
    assert policy["p_min_tf"]["1m"] == 0.52
    assert policy["p_min_tf"]["1h"] == 0.55
    assert policy["p_min_tf"]["1d"] == 0.50
    for tf in set(TIMEFRAMES_14) - {"1m", "1h", "1d"}:
        assert policy["p_min_tf"][tf] == 0.55
    assert policy["capital_hard_cap_fraction"] * EC.load_paper_account()["capital_usdt"] == 6000.0
    assert policy["c_min"] == 0.5


@pytest.mark.parametrize("bad", ["missing", "tf", "cap", "c_min", "extra"])
def test_d25_missing_or_invalid_policy_fails_closed(monkeypatch, bad):
    policy = copy.deepcopy(EC.load_decision_runtime())
    if bad == "tf":
        policy["p_min_tf"].pop("3m")
    elif bad == "cap":
        policy["capital_hard_cap_fraction"] = 0.7
    elif bad == "c_min":
        policy["c_min"] = None
    elif bad == "extra":
        policy["portfolio_exposure_cap"] = 0.6
    class Params:
        def __getitem__(self, key):
            if bad == "missing":
                raise FileNotFoundError("test-only missing file")
            return policy
    monkeypatch.setattr(EC, "load_params", Params)
    with pytest.raises(BridgeError, match="CONFIGURATION_INVALID"):
        EC.load_decision_runtime()


def test_closed_projection_preserves_raw_availability_and_rebases_sequence():
    raw = replace(make_obs(timeframe="1h", ts="2026-01-01T00:00:00.000Z"),
                  sequence=700, status="CORRECTED", availability_time="1970-01-01T00:00:00.000Z")
    projected, = EC.closed_engine_window([raw], "1h")
    assert projected.timestamp == "2026-01-01T01:00:00.000Z"
    assert projected.status == "CLOSED" and projected.sequence == 0
    assert projected.availability_time == raw.availability_time
    assert raw.sequence == 700 and raw.status == "CORRECTED"
    assert raw.timestamp == "2026-01-01T00:00:00.000Z"


def test_d26a_atr14_known_series_uses_method_b_reference_and_explicit_epsilon():
    import math
    prior = [float(i) for i in range(1, 21)]
    state = SimpleNamespace(atr14_wilder=25.0, atr20=999999.0)
    mean = sum(prior) / len(prior)
    sigma = math.sqrt(sum((x - mean) ** 2 for x in prior) / len(prior) + EC.E11.EPS)
    expected = (25.0 - mean) / (sigma + EC.E11.EPS)
    assert EC.atr_z_input(state, prior) == expected
    assert prior == [float(i) for i in range(1, 21)]
    # No sigmoid or ±10 cap is applied to the ATR z-score.
    assert EC.atr_z_input(SimpleNamespace(atr14_wilder=1000.0), prior) > 10.0


@pytest.mark.parametrize("prior", [[], [1.0], [float(i) for i in range(19)], [1.0] * 20])
def test_d26a_short_or_degenerate_history_uses_existing_failure(prior):
    state = SimpleNamespace(atr14_wilder=5.0)
    with pytest.raises(ValueError, match="INVALID_E11_HISTORY") as reference_error:
        EC.E11.rolling_sigmoid_norm(state.atr14_wilder, prior)
    with pytest.raises(ValueError, match="INVALID_E11_HISTORY") as projection_error:
        EC.atr_z_input(state, prior)
    assert str(projection_error.value) == str(reference_error.value)


def test_d26a_window_cap_reuses_existing_e11_constant_and_shared_helper(monkeypatch):
    cap = EC.E11.W_180D_H1
    prior = [float(i % 17) for i in range(cap)]
    state = SimpleNamespace(atr14_wilder=15.0)
    expected = EC.atr_z_input(state, prior)
    observed = []
    original = EC.E11.rolling_method_b_reference
    def reference(current, window):
        observed.append((current, list(window)))
        return original(current, window)
    monkeypatch.setattr(EC.E11, "rolling_method_b_reference", reference)
    assert EC.atr_z_input(state, [999999.0] * 30 + prior) == expected
    assert observed == [(15.0, prior)]
    EC.E11.rolling_sigmoid_norm(15.0, prior)
    assert observed[-1] == (15.0, prior) and len(observed) == 2


def test_d26a_refactor_preserves_existing_method_b_sigmoid_values():
    import math
    import numpy as np
    prior = [float(i) for i in range(20)]
    mean = float(np.mean(prior))
    sigma = math.sqrt(float(np.mean([(v - mean) ** 2 for v in prior])) + EC.E11.EPS)
    for current in (-1000.0, 1.25, 20.0, 1000.0):
        z = max(-10.0, min(10.0, (current - mean) / sigma))
        assert EC.E11.rolling_sigmoid_norm(current, prior) == 1.0 / (1.0 + math.exp(-z))


def test_e03_aligned_availability_arrays_and_misalignment():
    window = [make_obs(timeframe="1h", ts="2026-01-01T00:00:00.000Z")]
    engine = EC.E03.E03VolumeEngine()
    context = {"window": window, "atr_prev": [1.0], "atr_availability_time_ms": [1767225600000]}
    assert engine.compute("BTCUSDT", "1h", window[-1].timestamp, context) == []
    context["atr_availability_time_ms"] = [1, 2]
    with pytest.raises(ValueError, match="AVAILABILITY_ALIGNMENT_QX"):
        engine.compute("BTCUSDT", "1h", window[-1].timestamp, context)


def complete_event():
    from apex.data_catalog.contracts import EvidenceEvent, LifecycleState
    return EvidenceEvent(
        evidence_id="cp14-round-trip", engine_id="E01", analyst_version="4.0.0",
        symbol="BTCUSDT", timeframe="1h", snapshot_id="snapshot",
        event_time="2026-01-01T01:00:00.000Z", availability_time="2026-01-01T01:00:00.123Z",
        observation_window={"start": "2025-12-31T23:00:00.000Z", "bars": 2},
        feature_snapshot_id="feature-snapshot", feature_dependencies=("a", "b"),
        condition_state="EV_STR_007_BOS", direction=1, strength=0.75, confidence=0.8,
        quality=0.9, validity="VALID", fate_state=LifecycleState.ACTIVE,
        age=2.0, decay=0.95, explanation="original explanation", parameter_version="v4",
        lineage=("root", "branch"), resolution_class="Q4")


def test_complete_evidence_public_store_roundtrip_idempotence_and_collision(tmp_path):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    async def exercise():
        store = await SQLiteStore(str(tmp_path / "events.sqlite")).open()
        event = complete_event()
        try:
            assert await EC.persist_complete_evidence(store, [event]) == [event]
            assert await EC.persist_complete_evidence(store, [event]) == [event]
            assert event.explanation == "original explanation"
            with pytest.raises(BridgeError, match="identity collision"):
                await EC.persist_complete_evidence(store, [replace(event, age=3)])
            with pytest.raises(BridgeError, match="persisted event missing"):
                await EC.read_complete_evidence(store, ["absent"])
            await store.insert_evidence(replace(event, evidence_id="legacy-reduced"))
            with pytest.raises(BridgeError, match="EVIDENCE_CONTEXT_INVALID"):
                await EC.read_complete_evidence(store, ["legacy-reduced"])
        finally:
            await store.close()
    asyncio.run(exercise())


def test_complete_evidence_hash_and_schema_reject_corruption():
    import json
    stored = EC.evidence_storage_copy(complete_event())
    envelope = json.loads(stored.explanation)
    envelope["event"]["availability_time"] = "2026-01-02T01:00:00.123Z"
    with pytest.raises(BridgeError, match="EVIDENCE_CONTEXT_INVALID"):
        EC.evidence_from_raw(json.dumps(envelope))
    envelope["event"].pop("age")
    with pytest.raises(BridgeError, match="EVIDENCE_CONTEXT_INVALID"):
        EC.evidence_from_raw(json.dumps(envelope))


def test_train_cli_empty_store_refuses_first_required_class_without_artifact_write(tmp_path):
    """D36: an empty store refuses on the FIRST of the eight rule-tree
    classes (CRISIS precedes the derived TRANSITION in E11.REGIMES order)."""
    import json
    import subprocess
    import sys
    target = tmp_path / "existing.yaml"
    target.write_text("unchanged existing artifact\n")
    result = subprocess.run([sys.executable, "scripts/run_apex.py", "train-e11",
                             "--sqlite", str(tmp_path / "empty.sqlite"),
                             "--out", str(target), "--json"], capture_output=True, text=True)
    assert result.returncode == 2, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "REFUSED" and report["sample_count"] == 0
    assert report["per_class_counts"] == {key: 0 for key in EC.E11.REGIMES}
    assert report["reason"] == "EMPTY_CLASS:CRISIS"
    assert report["refusing_class"] == "CRISIS" and not report["artifact_written"]
    assert target.read_text() == "unchanged existing artifact\n"


def test_fitter_writer_two_process_determinism_not_a_store_training_claim(tmp_path):
    import subprocess
    import sys
    # Deliberately test only fitting/serialization on a labelled numerical
    # matrix. This is NOT the required successful harvested-store fixture.
    script = '''
import sys
from apex.ops.engine_context import *
X = [[float(i == j) for j in range(8)] for i in range(9)] * 3
W,b = fit_multinomial(X, list(E11.REGIMES) * 3, 123)
a = {"W": W, "b": b, "K": 9, "label_delay_candles": 48, "seed": 123,
     "training_window": {"start": "2026-01-01T00:00:00.000Z", "end": "2026-01-02T00:00:00.000Z", "timeframes": list(DEFAULT_TRAINING_TIMEFRAMES),
                         "symbols": list(CORE10_SYMBOLS), "default_timeframes": list(DEFAULT_TRAINING_TIMEFRAMES), "default_symbols": list(CORE10_SYMBOLS),
                         "max_bars_per_cell": None},
     "sample_count": 27, "training_query_sha256": "0" * 64, "artifact_sha256": classifier_hash(W,b,123)}
write_classifier(a, sys.argv[1])
assert load_classifier(sys.argv[1]) == a
'''
    paths = [tmp_path / f"process-{n}.yaml" for n in range(2)]
    for path in paths:
        result = subprocess.run([sys.executable, "-c", script, str(path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    assert paths[0].read_bytes() == paths[1].read_bytes()


def test_actual_first_seven_engines_use_d26_projections_and_refuse_short_history():
    import random
    from datetime import datetime, timedelta, timezone
    rng = random.Random(2)
    begin = datetime(2026, 1, 1, tzinfo=timezone.utc)
    window = []
    close = 100.0
    for i in range(90):
        opening = close
        close += rng.uniform(-2.0, 2.0)
        high, low = max(opening, close) + rng.random(), min(opening, close) - rng.random()
        window.append(replace(make_obs(timeframe="1h", ts=(begin + timedelta(hours=i)).isoformat(timespec="milliseconds").replace("+00:00", "Z")),
                              open=Decimal(str(opening)), close=Decimal(str(close)),
                              high=Decimal(str(high)), low=Decimal(str(low)),
                              volume=Decimal(str(rng.uniform(500, 2000))), oi=None, sequence=i + 600))
    frame = EC.upstream_frame(window, "BTCUSDT", "1h", emit=True)
    assert frame["engine_order"] == list(EC.ENGINE_ORDER[:7])
    assert frame["events"]
    assert frame["ic"]["oi_state"] == "MISSING"
    assert frame["ic"]["contributing_features"]["participation"] == "PARTIAL"
    assert frame["ic"]["liquidity_raw"] == EC.liquidity_inputs(frame["liquidity"])["liquidity_raw"]
    assert frame["projection_refusals"] == []
    states = frame["volatility"]["states"]
    prior = [state.atr14_wilder for state in states[:-1]]
    assert frame["ic"]["atr_z"] == EC.atr_z_input(states[-1], prior)
    assert "atr20" not in frame and not hasattr(EC.E04, "atr20_series")
    atr_by_close = {state.as_of: state.atr14_wilder for state in states}
    for i, bar in enumerate(frame["volume_bars"]):
        expected = None if i == 0 else atr_by_close.get(EC._iso_to_ms(frame["window"][i-1].timestamp))
        assert bar["atr_prev"] == expected
    short = EC.upstream_frame(window, "BTCUSDT", "1h", atr14_history=[])
    assert short["ic"]["atr_z"] is None
    assert "INVALID_E11_HISTORY" in short["projection_refusals"]
    assert frame["window"][0].sequence == 0
    assert window[0].sequence == 600
    assert all(a.availability_time == b.availability_time for a, b in zip(frame["window"], window))


def test_producer_window_uses_public_store_and_derived_closed_boundary(tmp_path):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    async def exercise():
        store = await SQLiteStore(str(tmp_path / "closed.sqlite")).open()
        try:
            for hour in range(3):
                await store.ingest_raw(make_obs(timeframe="1h", ts=f"2026-01-01T0{hour}:00:00.000Z"), oi_state="AVAILABLE")
            producer = EC.EngineContextProducer(store)
            window = await producer.window("BTCUSDT", "1h", "2026-01-01T02:00:00.000Z", 10)
            assert [o.timestamp for o in window] == ["2026-01-01T00:00:00.000Z", "2026-01-01T01:00:00.000Z"]
        finally:
            await store.close()
    asyncio.run(exercise())


def test_d26a_shared_timeline_advances_prior_same_cell_history_after_projection(monkeypatch):
    from datetime import datetime, timedelta, timezone
    calls = []
    initial = [SimpleNamespace(atr14_wilder=float(i)) for i in range(1, 21)]
    def upstream(window, symbol, timeframe, *, atr14_history, **kwargs):
        calls.append((symbol, timeframe, None if atr14_history is None else list(atr14_history)))
        states = initial if atr14_history is None else [SimpleNamespace(atr14_wilder=100.0)]
        return {"confirmation": False, "volatility": {"states": states}, "vlt": states[-1],
                "projection_refusals": ["E11_LIQUIDITY_PROJECTION_UNCONFIGURED"]}
    monkeypatch.setattr(EC, "upstream_frame", upstream)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    window = [make_obs(timeframe="1h", ts=(start + timedelta(hours=i)).isoformat(timespec="milliseconds").replace("+00:00", "Z"))
              for i in range(53)]
    async def exercise():
        producer = EC.EngineContextProducer(None)
        first = [row async for row in producer.feature_timeline("BTCUSDT", "1h", window)]
        assert len(first) == 53
        assert first[-1]["reason"] == "E11_PROJECTION_UNCONFIGURED"
        # Another cell has independent initial history; no BTC -> ETH leak.
        _ = [row async for row in producer.feature_timeline("ETHUSDT", "1h", window)]
    asyncio.run(exercise())
    assert calls[:3] == [("BTCUSDT", "1h", None),
                         ("BTCUSDT", "1h", [float(i) for i in range(1, 21)]),
                         ("BTCUSDT", "1h", [float(i) for i in range(1, 21)] + [100.0])]
    assert calls[3] == ("ETHUSDT", "1h", None)


def _copy_governed_params(tmp_path):
    import shutil
    destination = tmp_path / "params"
    destination.mkdir()
    for name in EC.PARAMS_FILES.values():
        source = EC.PARAMS_DIR / name
        if source.exists():
            shutil.copyfile(source, destination / name)
    return destination


def test_d27_probability_complement_is_accepted_by_unchanged_combiner():
    import math
    from apex.fabric.context import CombinerInputs, context_confidence, DEFAULT_COMBINER_WEIGHTS
    state = {"probs": [.4] + [.075] * 8, "entropy": -(.4 * math.log(.4) + 8 * .075 * math.log(.075))}
    before = copy.deepcopy(state)
    produced = {"data_trust": 1., "mtf_state": "ALIGNED", "evidence_agreement": 1.,
                "regime_confidence": max(state["probs"]), "regime_uncertainty": EC.regime_uncertainty_input(state),
                "divergence_magnitude": 0., "temporal_window_validity": 1.}
    assert produced["regime_uncertainty"] == pytest.approx(.6)
    combined = context_confidence(CombinerInputs(**produced), timeframe="1h", q_raw=1.)
    assert 0 < combined["context_confidence"] <= 1
    assert CombinerInputs(**produced).weights == DEFAULT_COMBINER_WEIGHTS
    assert state == before
    assert EC.E11.entropy_normalized(state["entropy"]) == pytest.approx(state["entropy"] / math.log(9))


@pytest.mark.parametrize("probs", [None, [], [.4] * 9, [float("nan")] * 9, [-1.] + [.25] * 8])
def test_d27_invalid_probabilities_do_not_become_permission(probs):
    with pytest.raises(BridgeError, match="CONFIGURATION_INVALID"):
        EC.regime_uncertainty_input({"probs": probs})


def test_d28_package_hash_covers_canonical_governed_values_and_optional_classifier(tmp_path):
    import hashlib
    from apex.identity.canonical_json import canonical_json
    folder = _copy_governed_params(tmp_path)
    first = EC.paper_package_binding(environment="PAPER", params_dir=folder)
    expected = {name: EC._YamlSubsetParser((folder / name).read_text()).parse()
                for name in first["parameter_files"]}
    digest = hashlib.sha256(canonical_json(expected).encode("utf-8")).hexdigest()
    assert first["parameter_package_id"] == "cp14_paper_bootstrap-v1.0.0-" + digest[:12]
    assert first["parameter_sha256"] == digest
    # Formatting/comments are not governed value changes.
    path = folder / "decision_runtime_v1.yaml"
    path.write_text(path.read_text() + "\n# test-only formatting change\n")
    assert EC.paper_package_binding(environment="PAPER", params_dir=folder) == first
    # An actual governed change (only in the temporary test copy) changes ID.
    path.write_text(path.read_text().replace("quality: 1.0, alignment: 0.0", "quality: 0.8, alignment: 0.2"))
    second = EC.paper_package_binding(environment="PAPER", params_dir=folder)
    assert second["parameter_package_id"] != first["parameter_package_id"]
    (folder / "e11_classifier_v1.yaml").write_bytes(FIXTURE.read_bytes())
    third = EC.paper_package_binding(environment="PAPER", params_dir=folder)
    assert third["parameter_package_id"] != second["parameter_package_id"]
    assert third["parameter_files"].count("e11_classifier_v1.yaml") == 1
    artifact = EC.load_classifier(folder / "e11_classifier_v1.yaml")
    artifact["b"][0] += .01
    artifact["artifact_sha256"] = EC.classifier_hash(artifact["W"], artifact["b"], artifact["seed"])
    EC.write_classifier(artifact, folder / "e11_classifier_v1.yaml")
    assert EC.paper_package_binding(environment="PAPER", params_dir=folder)["parameter_package_id"] != third["parameter_package_id"]
    # A non-governed stray file is never adopted as an active parameter source.
    current = EC.paper_package_binding(environment="PAPER", params_dir=folder)
    (folder / "not_governed.yaml").write_text("quality: 999\n")
    assert EC.paper_package_binding(environment="PAPER", params_dir=folder) == current


def test_d28_package_id_reproducible_in_two_processes(tmp_path):
    import subprocess
    import sys
    folder = _copy_governed_params(tmp_path)
    code = ("from apex.ops.engine_context import paper_package_binding; "
            "from apex.identity.canonical_json import canonical_json; "
            f"print(canonical_json(paper_package_binding(environment='PAPER', params_dir={str(folder)!r})))")
    assert subprocess.check_output([sys.executable, "-c", code]) == subprocess.check_output([sys.executable, "-c", code])


def test_d28_missing_governed_file_refuses_and_live_reads_nothing(tmp_path, monkeypatch):
    folder = _copy_governed_params(tmp_path)
    (folder / "setup_weights_v1.yaml").unlink()
    with pytest.raises(BridgeError, match="CONFIGURATION_INVALID"):
        EC.paper_package_binding(environment="PAPER", params_dir=folder)
    monkeypatch.setenv("APEX_ENV", "LIVE")
    live = Config(env_path=None).apex_env
    monkeypatch.setattr(Path, "read_text", lambda *a, **kw: pytest.fail("LIVE bootstrap read"))
    assert EC.paper_package_binding(environment=live, params_dir=folder) is None
    assert EC.EngineContextProducer(None).environment == "LIVE"
    assert EC.paper_bootstrap_inputs(environment=live, family_record=None, params_dir=folder) is None
    with pytest.raises(BridgeError, match="LIVE_GOVERNANCE_UNAVAILABLE"):
        asyncio.run(EC.EngineContextProducer(None, environment=live).decision_inputs("BTCUSDT", "1h", "2026-01-01T00:00:00.000Z"))


def test_d28_live_policy_ignores_even_invalid_bootstrap_section(monkeypatch):
    params = {"decision_runtime": copy.deepcopy(EC.load_decision_runtime())}
    params["decision_runtime"]["paper_bootstrap"] = {"invalid": "must not be validated for LIVE"}
    monkeypatch.setattr(EC, "load_params", lambda: params)
    assert "paper_bootstrap" not in EC.load_decision_runtime(environment="LIVE")
    assert EC.load_decision_runtime(environment="LIVE")["capital_hard_cap_fraction"] == .60
    with pytest.raises(BridgeError, match="CONFIGURATION_INVALID"):
        EC.load_decision_runtime(environment="PAPER")


@pytest.mark.parametrize("status", ["ACCUMULATING", "PROMOTED", "DEGRADING", "DEMOTED"])
def test_d28_existing_family_status_is_never_overwritten(status):
    record = {"status": status, "actor": "OWNER"}
    result = EC.paper_bootstrap_inputs(environment="PAPER", family_record=record)
    assert result["family_status"] == status and record == {"status": status, "actor": "OWNER"}
    assert result["family_status_source"] == "SETUP_FAMILY_REGISTRY"
    assert result["arbitration"] == {"composite_weights": {"quality": 1., "alignment": 0., "recency": 0.},
                                     "alignment": "UNAVAILABLE", "recency": "UNAVAILABLE"}


def test_d28_absence_is_not_invalid_record():
    assert EC.paper_bootstrap_inputs(environment="PAPER", family_record=None)["family_status"] == "ACCUMULATING"
    with pytest.raises(BridgeError, match="FAMILY_REGISTRY_INVALID"):
        EC.paper_bootstrap_inputs(environment="PAPER", family_record={})


def test_d28_family_snapshot_pit_read_does_not_create_or_overwrite_records(tmp_path):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    async def exercise():
        store = await SQLiteStore(str(tmp_path / "family.sqlite")).open()
        try:
            assert await EC.read_family_record(store, "family", "2026-01-01T00:00:00.000Z") is None
            await store.insert_snapshot({"snapshot_id": "owner-demotion", "as_of": "2026-01-01T01:00:00.000Z",
                "source_state": "SETUP_FAMILY_REGISTRY", "quality_state": {"family_registry": {"family": {"status": "DEMOTED"}}}})
            await store.insert_snapshot({"snapshot_id": "other-family", "as_of": "2026-01-01T02:00:00.000Z",
                "source_state": "SETUP_FAMILY_REGISTRY", "quality_state": {"family_registry": {}}})
            before = await (await store.db.execute("SELECT * FROM snapshot_pit")).fetchall()
            assert await EC.read_family_record(store, "family", "2026-01-01T00:59:59.999Z") is None
            record = await EC.read_family_record(store, "family", "2026-01-01T03:00:00.000Z")
            assert EC.paper_bootstrap_inputs(environment="PAPER", family_record=record)["family_status"] == "DEMOTED"
            assert record["registry_snapshot_id"] == "owner-demotion"
            assert await (await store.db.execute("SELECT * FROM snapshot_pit")).fetchall() == before
        finally:
            await store.close()
    asyncio.run(exercise())


class _PublicFactsFixture:
    """Actual public client + required fake transport, no production fixtures."""
    def __init__(self):
        from tests.fake_toobit_responder import FakeToobitResponder
        from apex.data_catalog.ingest.toobit_public import ToobitPublicClient
        from urllib.parse import urlencode
        self.record = {"symbol": "BTC-SWAP-USDT", "commissionRate": {"takerCommissionRate": "0.0005"},
                       "contractMultiplier": "1", "contractType": "PERPETUAL", "deliveryDate": 0}
        self.funding = "0.0001"
        self.funding_schedule = {}
        outer = self
        class Venue(FakeToobitResponder):
            def _route(self, call, method, path, params):
                call.responded = True
                if method == "GET" and path == "/api/v1/exchangeInfo":
                    return {"http_status": 200, "body": {"symbols": [copy.deepcopy(outer.record)]}}
                if method == "GET" and path == "/api/v1/futures/fundingRate":
                    return {"http_status": 200, "body": {"fundingRate": outer.funding, **outer.funding_schedule}}
                return super()._route(call, method, path, params)
        self.venue = Venue()
        class Response:
            async def __aenter__(self):
                self.result = await outer.venue("GET", self.url, urlencode(self.params or {}), self.headers or {})
                self.status = self.result["http_status"]
                return self
            async def __aexit__(self, *args): return False
            async def json(self, **kwargs): return self.result["body"]
        class Session:
            def get(self, url, params=None, headers=None, timeout=None):
                r = Response(); r.url = url; r.params = params; r.headers = headers
                return r
        self.client = ToobitPublicClient(session=Session())


def test_d28_public_facts_real_client_no_keys_and_pit_roundtrip(tmp_path, monkeypatch):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    from apex.setup.family_sf_fvg_sweep_rev import FAMILY_ID
    monkeypatch.delenv("TOOBIT_API_KEY", raising=False)
    monkeypatch.delenv("TOOBIT_API_SECRET", raising=False)
    fixture = _PublicFactsFixture()
    async def exercise():
        stamp = "2026-01-01T00:00:00.000Z"
        store = await SQLiteStore(str(tmp_path / "facts.sqlite")).open()
        try:
            now = lambda: EC._iso_to_ms(stamp) / 1000
            facts = await EC.persist_public_venue_facts(store, "BTCUSDT", environment="PAPER", client=fixture.client, now=now)
            assert facts["commission_rate"] == Decimal(".0005")
            assert facts["funding_rate"] == Decimal(".0001")
            assert facts["contract_multiplier"] == 1 and facts["expiry_time"] is None
            with pytest.raises(BridgeError, match="VENUE_FACTS_UNAVAILABLE"):
                await EC.read_public_venue_facts(store, "BTCUSDT", "2025-12-31T23:59:59.999Z")
            restored = await EC.read_public_venue_facts(store, "BTCUSDT", stamp)
            assert EC.canonical_json(restored) == EC.canonical_json(facts)
            await EC.persist_public_venue_facts(store, "BTCUSDT", environment="PAPER", client=fixture.client, now=now)
            row = await (await store.db.execute("SELECT count(*) FROM snapshot_pit")).fetchone()
            assert row[0] == 1
            producer = EC.EngineContextProducer(store, environment="PAPER")
            inputs = await producer.decision_inputs("BTCUSDT", "1h", stamp)
            assert inputs["family_status"] == "ACCUMULATING"
            assert inputs["arbitration"]["alignment"] == "UNAVAILABLE"
            assert inputs["venue_provenance"]["source_sha256"] == facts["source_sha256"]
            await store.insert_snapshot({"snapshot_id": "family-demoted", "as_of": stamp,
                "source_state": "SETUP_FAMILY_REGISTRY", "quality_state": {"family_registry": {FAMILY_ID: {"status": "DEMOTED"}}}})
            assert (await producer.decision_inputs("BTCUSDT", "1h", stamp))["family_status"] == "DEMOTED"
            calls = fixture.venue.calls
            assert all(c.method == "GET" and not c.api_key_present and "signature" not in c.params for c in calls)
            assert {c.path for c in calls} == {"/api/v1/exchangeInfo", "/api/v1/futures/fundingRate"}
        finally:
            await store.close()
    asyncio.run(exercise())


@pytest.mark.parametrize("field,reason", [("commissionRate", "COMMISSION_RATE"), ("contractMultiplier", "CONTRACT_MULTIPLIER"),
                                            ("contractType", "CONTRACT_TYPE"), ("funding", "FUNDING_RATE")])
def test_d28_missing_public_fact_is_named_and_never_uses_a_fee_default(field, reason):
    fixture = _PublicFactsFixture()
    if field == "funding":
        fixture.funding = None
    else:
        fixture.record.pop(field)
    with pytest.raises(BridgeError, match="VENUE_" + reason + "_UNAVAILABLE"):
        asyncio.run(EC.collect_public_venue_facts("BTCUSDT", client=fixture.client))
    assert all(not c.api_key_present and c.method == "GET" for c in fixture.venue.calls)


def test_d28_expiring_contract_requires_explicit_expiry_and_perpetual_cannot_conflict():
    fixture = _PublicFactsFixture()
    fixture.record["contractType"] = "DELIVERY"
    with pytest.raises(BridgeError, match="VENUE_EXPIRY_UNAVAILABLE"):
        asyncio.run(EC.collect_public_venue_facts("BTCUSDT", client=fixture.client))
    fixture.record["deliveryDate"] = EC._iso_to_ms("2026-12-31T00:00:00.000Z")
    assert asyncio.run(EC.collect_public_venue_facts("BTCUSDT", client=fixture.client))["expiry_time"] == "2026-12-31T00:00:00.000Z"
    fixture.record["contractType"] = "PERPETUAL"
    with pytest.raises(BridgeError, match="VENUE_EXPIRY_UNAVAILABLE"):
        asyncio.run(EC.collect_public_venue_facts("BTCUSDT", client=fixture.client))


def test_d28_failed_refresh_does_not_resurrect_old_facts_or_poison_other_symbol(tmp_path):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    fixture = _PublicFactsFixture()
    async def exercise():
        store = await SQLiteStore(str(tmp_path / "refresh.sqlite")).open()
        t0 = EC._iso_to_ms("2026-01-01T00:00:00.000Z") / 1000
        try:
            await EC.persist_public_venue_facts(store, "BTCUSDT", environment="PAPER", client=fixture.client, now=lambda: t0)
            fixture.record["symbol"] = "ETH-SWAP-USDT"
            await EC.persist_public_venue_facts(store, "ETHUSDT", environment="PAPER", client=fixture.client, now=lambda: t0)
            fixture.record["symbol"] = "BTC-SWAP-USDT"
            fixture.record.pop("commissionRate")
            with pytest.raises(BridgeError, match="VENUE_COMMISSION_RATE_UNAVAILABLE"):
                await EC.persist_public_venue_facts(store, "BTCUSDT", environment="PAPER", client=fixture.client, now=lambda: t0 + 1)
            with pytest.raises(BridgeError, match="VENUE_COMMISSION_RATE_UNAVAILABLE"):
                await EC.read_public_venue_facts(store, "BTCUSDT", "2026-01-01T00:00:01.000Z")
            assert (await EC.read_public_venue_facts(store, "BTCUSDT", "2026-01-01T00:00:00.000Z"))["commission_rate"] == "0.0005"
            assert (await EC.read_public_venue_facts(store, "ETHUSDT", "2026-01-01T00:00:01.000Z"))["symbol"] == "ETHUSDT"
            assert (await (await store.db.execute("SELECT count(*) FROM snapshot_pit")).fetchone())[0] == 3
        finally:
            await store.close()
    asyncio.run(exercise())


@pytest.mark.parametrize("reserved,level", [(0, "OK"), (5000, "WARNING"), (6500, "ACTION"), (8100, "LIQUIDATION_APPROACH")])
def test_d29_paper_proxy_requested_examples_and_real_veto(reserved, level):
    from apex.risk import kernel
    positions = [] if not reserved else [{"quantity": reserved, "mark_price": 1, "contract_multiplier": 1}]
    result = EC.paper_reservation_proxy(capital=10000, positions=positions, orders=[], environment="PAPER")
    assert result["margin_health_fraction"] == (Decimal(10000) - reserved) / 10000
    assert result["margin_status"]["level"] == level
    veto = kernel.evaluate_vetoes({**result, "timeframe": "1h", "q_raw": 1.0})
    assert (14 in veto["fired_numbers"]) == (reserved > 6000)
    if level == "LIQUIDATION_APPROACH":
        assert result["margin_status"]["action"] == "EMERGENCY_L3_CANCEL_ALL"


@pytest.mark.parametrize("fraction,paper,live", [(.6, "OK", "WARNING"), (.4, "WARNING", "ACTION"), (.2, "ACTION", "LIQUIDATION_APPROACH")])
def test_d29_strict_boundaries_do_not_change_live(fraction, paper, live):
    from apex.risk import kernel
    assert kernel.margin_health_state(fraction, environment="PAPER")["level"] == paper
    assert kernel.margin_health_state(fraction)["level"] == live
    if fraction == .4:
        base = {"timeframe": "1h", "q_raw": 1., "margin_health_fraction": fraction,
                "margin_model": "PAPER_RESERVATION_PROXY_D29"}
        assert 14 not in kernel.evaluate_vetoes({**base, "environment": "PAPER"})["fired_numbers"]
        assert 14 in kernel.evaluate_vetoes({**base, "environment": "LIVE"})["fired_numbers"]


@pytest.mark.parametrize("capital", [0, -1, None, "NaN", "Infinity"])
def test_d29_invalid_capital_refuses(capital):
    with pytest.raises(BridgeError, match="PAPER_MARGIN_INPUT_INVALID"):
        EC.paper_reservation_proxy(capital=capital, positions=[], orders=[], environment="PAPER")


def test_d29_pending_partial_reduce_only_cancelled_and_missing_facts():
    position = {"quantity": 4, "mark_price": 125, "contract_multiplier": 1}
    order = {"state": "PARTIAL", "quantity": 10, "filled_quantity": 4, "reference_price": 100,
             "contract_multiplier": 1, "reduce_only": False, "is_risk_increase": True}
    def calc(positions, orders):
        return EC.paper_reservation_proxy(capital=10000, positions=positions, orders=orders, environment="PAPER")
    result = calc([position], [order])
    assert result["open_notional"] == 500 and result["pending_notional"] == 600
    assert result["margin_health_fraction"] == Decimal(".89")
    assert calc([position], [{**order, "state": "CANCELLED"}])["pending_notional"] == 0
    assert calc([position], [{**order, "reduce_only": True}])["pending_notional"] == 0
    with pytest.raises(BridgeError, match="PAPER_MARGIN_INPUT_INVALID"):
        calc([{**position, "mark_price": None}], [])
    with pytest.raises(BridgeError, match="PAPER_ORDER_STATE_UNAVAILABLE"):
        calc([], [{**order, "state": None}])
    with pytest.raises(BridgeError, match="PAPER_ORDER_STATE_UNAVAILABLE"):
        calc([], [{**order, "state": "FILLED"}])
    with pytest.raises(BridgeError, match="PAPER_MARGIN_OUT_OF_RANGE"):
        calc([{**position, "quantity": 1000}], [])
    with pytest.raises(BridgeError, match="PAPER_ACCOUNT_NOT_LIVE"):
        EC.paper_reservation_proxy(capital=10000, positions=[], orders=[], environment="LIVE")


def test_d29_real_ledger_partial_order_pnl_environment_isolation_and_cancel(tmp_path):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    from apex.ledger.store import LedgerWriter
    async def exercise():
        store = await SQLiteStore(str(tmp_path / "reservation.sqlite")).open()
        ledger = LedgerWriter(store, clock=lambda: "2026-01-01T00:00:00.000Z")
        await ledger.initialize(); await ledger.start()
        try:
            for env, suffix in (("PAPER", "000000000001"), ("LIVE", "000000000002")):
                pid, intent, setup = "plan-" + suffix, "i-" + suffix, "setup-" + suffix
                await ledger.append_trade_plan({"proposal_id": pid, "setup_id": setup, "symbol": "BTCUSDT", "timeframe": "1h",
                    "direction": "LONG", "sized_quantity": 10, "decision": "ALLOW", "environment": env, "contract_multiplier": 1})
                await ledger.append_fsm_transition(intent_id=intent, from_state="READY", to_state="SUBMITTING", reason="test",
                    trigger="SUBMIT_ORDER", environment=env, evidence={"symbol": "BTCUSDT", "quantity": "10", "price": "100"})
                await ledger.append_fsm_transition(intent_id=intent, from_state="SUBMITTING", to_state="PARTIAL", reason="test",
                    trigger="PARTIAL_FILL", environment=env)
                await ledger.append_fill(intent_id=intent, fill_id="fill-" + suffix, price="100", quantity="4", symbol="BTCUSDT", side="BUY_OPEN")
                await store.db.execute("INSERT INTO setup_candidate (setup_id) VALUES (?)", (setup,))
                await store.db.commit()
                await ledger.append_outcome({"outcome_id": "outcome-" + suffix, "setup_id": setup, "pnl": "25", "context": {"environment": env}})
            kwargs = {"marks": {"BTCUSDT": 125}, "contract_specs": {"BTCUSDT": {"contract_multiplier": 1}}, "environment": "PAPER"}
            got = await EC.paper_account_state(ledger, **kwargs)
            assert got["capital"] == Decimal("10025") == await EC.paper_balance(ledger)
            assert got["open_notional"] == 500 and got["pending_notional"] == 600
            assert got["margin_health_fraction"] == Decimal(8925) / Decimal(10025)
            await ledger.append_fsm_transition(intent_id="i-000000000001", from_state="PARTIAL", to_state="CANCELLED", reason="test",
                trigger="CANCEL_CONFIRMED", environment="PAPER")
            cancelled = await EC.paper_account_state(ledger, **kwargs)
            assert cancelled["open_notional"] == 500 and cancelled["pending_notional"] == 0
            await ledger.append_trade_plan({"proposal_id": "missing-state", "setup_id": "setup", "symbol": "BTCUSDT", "timeframe": "1h",
                "direction": "LONG", "sized_quantity": 1, "decision": "ALLOW", "environment": "PAPER", "contract_multiplier": 1})
            with pytest.raises(BridgeError, match="PAPER_ORDER_STATE_UNAVAILABLE"):
                await EC.paper_account_state(ledger, **kwargs)
            assert (await ledger.verify_chain())["intact"]
        finally:
            await ledger.stop(); await store.close()
    asyncio.run(exercise())


def test_d26b_live_density_max_age_and_five_prerequisite_sweeps():
    engine = EC.E02.LiquidityEngineV4()
    engine.candles = [EC.E02.Candle(100, 105, 95, 101, 50, i, True, i) for i in range(120)]
    def level(price, touch, fate="ACTIVE"):
        return SimpleNamespace(price=price, last_touch=touch, fate=fate)
    engine.levels = {"a": level(100, 115), "b": level(110, 100, "STRENGTHENED"),
                     "c": level(130, 118), "dead": level(1000, 0, "EXPIRED")}
    prereq = dict.fromkeys(EC.SWEEP_PREREQUISITES, True)
    def event(kind, index, checks=prereq):
        return {"event_type": kind, "at_bar": index, "payload": {"prereq": checks}}
    engine.events = [event("EV_LIQ_005", 110), event("EV_LIQ_006", 111), event("EV_LIQ_005", 0),
                     event("EV_LIQ_007", 112), event("EV_LIQ_005", 113, {**prereq, "P3_rejection": False})]
    got = EC.liquidity_inputs(engine)
    assert got["level_density"] == 3 / 30
    assert got["age_score"] == 19  # maximum age, NOT average/sum
    assert got["sweep_rate"] == 2 / EC.E02.E02_DEFAULTS["volume_profile_bars"]
    assert got["liquidity_raw"] == (3 / 30) * 19 / 1.02
    engine.levels = {"a": engine.levels["a"]}
    one = EC.liquidity_inputs(engine)
    assert one["level_density"] == one["age_score"] == one["liquidity_raw"] == 0
    assert one["sweep_rate"] == .02
    assert EC.E11.projected_liquidity_norm(one["liquidity_raw"], [0.] * 20) == .5
    engine.events = [event("EV_LIQ_007", 112)]
    assert EC.liquidity_inputs(engine)["sweep_rate"] == 0


def test_d26b_classifier_normalizes_projected_raw_not_density():
    ic = {"trendiness_raw": .4, "vol_ratio": .4, "expansion_raw": .4,
          "level_density": .1, "liquidity_raw": 1.9, "participation_raw": .4,
          "structure_score": .4, "momentum_state_raw": "NEUTRAL", "atr_z": 0,
          "bias_per_TF": {"H4": 0, "H1": 0, "M15": 0}}
    history = {key: [0., 1., 2.] * 10 for key in EC.HISTORY_KEYS}
    vector, _ = EC.E11.compute_state_vector(ic, history, .5)
    assert vector["liquidity_stability"] == EC.E11.rolling_minmax_norm(1.9, history["liq"])
    engine = EC.E11.RegimeEngine()
    engine._append_history(ic, vector)
    assert engine.history_windows["liq"][-1] == 1.9


def test_raw_availability_and_oi_lineage_survive_public_store_projection(tmp_path):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    async def exercise():
        store = await SQLiteStore(str(tmp_path / "lineage.sqlite")).open()
        try:
            original = replace(make_obs(timeframe="1h", ts="2026-01-01T00:00:00.000Z"),
                availability_time="1970-01-01T00:00:00.000Z", oi_timestamp="2026-01-01T00:59:00.000Z")
            await store.ingest_raw(original, oi_state="AVAILABLE")
            legacy = (await store.get_window("BTCUSDT", "1h", "2026-01-01T01:00:00.000Z", 10))[0]
            assert legacy.availability_time != original.availability_time and legacy.oi_timestamp is None
            producer = EC.EngineContextProducer(store)
            recovered = (await producer.window("BTCUSDT", "1h", "2026-01-01T01:00:00.000Z", 10))[0]
            assert recovered.availability_time == original.availability_time
            assert recovered.oi_timestamp == original.oi_timestamp and recovered.oi_lag_seconds == 60
            late = replace(make_obs(timeframe="1h", ts="2026-01-01T01:00:00.000Z"), availability_time="2026-01-01T03:00:00.000Z")
            await store.ingest_raw(late, oi_state="AVAILABLE")
            assert len(await producer.window("BTCUSDT", "1h", "2026-01-01T02:00:00.000Z", 10)) == 1
            assert len(await producer.window("BTCUSDT", "1h", "2026-01-01T03:00:00.000Z", 10)) == 2
            row = await (await store.db.execute("SELECT availability_time FROM raw_observation WHERE as_of=?", (original.timestamp,))).fetchone()
            assert row[0] == original.availability_time
        finally:
            await store.close()
    asyncio.run(exercise())


def test_label_horizon_requires_contiguous_calendar_closes():
    from datetime import datetime, timedelta, timezone
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    window = [make_obs(timeframe="1h", ts=(start + timedelta(hours=i)).isoformat(timespec="milliseconds").replace("+00:00", "Z")) for i in range(51)]
    assert EC.contiguous_label_horizon(window, 0, "1h")
    assert not EC.contiguous_label_horizon(window[:48], 0, "1h")
    assert not EC.contiguous_label_horizon(window[:20] + window[21:], 0, "1h")


def test_future_confirmation_survives_unavailable_e11_features(monkeypatch):
    from datetime import datetime, timedelta, timezone
    def failed(*a, **kw):
        raise BridgeError("INVALID_E11_HISTORY", "normalizer unavailable")
    monkeypatch.setattr(EC, "upstream_frame", failed)
    monkeypatch.setattr(EC, "structural_confirmation", lambda *a, **kw: True)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    window = [make_obs(timeframe="1h", ts=(start + timedelta(hours=i)).isoformat(timespec="milliseconds").replace("+00:00", "Z")) for i in range(52)]
    async def exercise():
        rows = [r async for r in EC.EngineContextProducer(None).feature_timeline("BTCUSDT", "1h", window)]
        assert rows[-1]["confirmation"] is True and rows[-1]["reason"] == "INVALID_E11_HISTORY"
    asyncio.run(exercise())


def test_native_e04_stream_matches_full_prefix_batch_without_future_inputs():
    import random
    from datetime import datetime, timedelta, timezone
    rng = random.Random(47)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    raw = []
    price = 100.
    for i in range(82):
        opening = price; price += rng.uniform(-1, 1)
        raw.append(replace(make_obs(timeframe="1h", oi=None,
            ts=(start + timedelta(hours=i)).isoformat(timespec="milliseconds").replace("+00:00", "Z")),
            open=Decimal(str(opening)), close=Decimal(str(price)), high=Decimal(str(max(opening, price) + 1)),
            low=Decimal(str(min(opening, price) - 1)), volume=Decimal(str(rng.uniform(300, 1000)))))
    bars = [EC.E04.observation_to_bar(o, "1h") for o in EC.closed_engine_window(raw, "1h")]
    stream = {"engine": EC.E04.VolatilityEngineV4(timeframe="1h"), "pending": bars[:80], "evidence": []}
    for end in (80, 81, 82):
        if end > 80:
            stream["pending"].append(bars[end - 1])
        projection_raw = raw[:end] if end == 80 else raw[end - 51:end]
        frame = EC.upstream_frame(projection_raw, "BTCUSDT", "1h", volatility_stream=stream)
        expected = EC.E04.run_engine(bars[:end], timeframe="1h")
        start_ms = EC._iso_to_ms(frame["window"][0].timestamp)
        assert [s.to_canonical() for s in frame["volatility"]["states"]] == [s.to_canonical() for s in expected["states"] if s.as_of >= start_ms]
        assert len(stream["engine"].bars) == end
        assert max(s.as_of for s in frame["volatility"]["states"]) == bars[end - 1]["ts"]


def test_e01_local_atr_memoization_preserves_complete_native_pipeline(monkeypatch):
    import random
    rng = random.Random(12)
    candles = []
    price = 100.
    for i in range(130):
        opening = price; price += rng.uniform(-2, 2)
        candles.append({"O": opening, "H": max(opening, price) + rng.random(),
                        "L": min(opening, price) - rng.random(), "C": price,
                        "V": rng.uniform(10, 100), "is_closed": True, "close_time": i})
    memoized = EC.E01.run_pipeline(candles)
    original = EC.E01.atr_sma
    monkeypatch.setattr(EC.E01, "atr_sma", lambda candles, n=14, idx=-1: original(list(candles), n, idx))
    reference = EC.E01.run_pipeline(candles)
    assert EC.canonical_json(memoized) == EC.canonical_json(reference)


def test_d30_default_scope_and_progress_are_exactly_twenty_base_cells(tmp_path):
    import json
    import subprocess
    import sys
    from apex.data_catalog.contracts import CORE10_SYMBOLS
    result = subprocess.run([sys.executable, "scripts/run_apex.py", "train-e11", "--sqlite", str(tmp_path / "empty.sqlite"),
                             "--out", str(tmp_path / "absent.yaml"), "--json"], capture_output=True, text=True, timeout=15)
    assert result.returncode == 2, result.stdout + result.stderr
    report = json.loads(result.stdout)
    lines = [line for line in result.stderr.splitlines() if line.startswith("TRAIN_CELL ")]
    assert len(lines) == 20
    assert {line.split()[1] for line in lines} == {f"cell={symbol}:{tf}" for symbol in CORE10_SYMBOLS for tf in ("1h", "4h")}
    assert all("closed_bars=0 eligible_samples=0 elapsed_seconds=" in line for line in lines)
    assert report["training_window"]["timeframes"] == ["1h", "4h"]
    assert report["training_window"]["symbols"] == list(CORE10_SYMBOLS)
    assert report["training_window"]["default_timeframes"] == ["1h", "4h"]
    assert report["training_window"]["default_symbols"] == list(CORE10_SYMBOLS)
    assert report["per_class_counts"] == dict.fromkeys(EC.E11.REGIMES, 0)
    assert not (tmp_path / "absent.yaml").exists()


@pytest.mark.parametrize("existing", [False, True])
def test_d30_hard_cli_deadline_never_writes_artifact(tmp_path, existing):
    import json
    import subprocess
    import sys
    import time
    target = tmp_path / "output.yaml"
    if existing:
        target.write_text("do not replace this artifact\n")
    started = time.monotonic()
    result = subprocess.run([sys.executable, "scripts/run_apex.py", "train-e11", "--sqlite", str(tmp_path / "empty.sqlite"),
                             "--out", str(target), "--json", "--max-minutes", "0.0001"], capture_output=True, text=True, timeout=10)
    assert time.monotonic() - started < 5
    assert result.returncode == 2, result.stdout + result.stderr
    from apex.data_catalog.contracts import CORE10_SYMBOLS as _CORE10
    assert json.loads(result.stdout) == {
        "status": "REFUSED", "reason": "TRAINING_TIME_LIMIT", "artifact_written": False,
        "cells_completed": [],
        "cells_remaining": [f"{symbol}:{tf}" for symbol in _CORE10 for tf in ("1h", "4h")],
        "next_cell": "BTCUSDT:1h"}
    assert not list(tmp_path.glob(".e11-*"))
    assert target.read_text() == "do not replace this artifact\n" if existing else not target.exists()


@pytest.mark.parametrize("timeframes,symbols", [("8h", "BTCUSDT"), ("1h,1h", "BTCUSDT"), ("", "BTCUSDT"), ("1h", "UNKNOWN")])
def test_d30_scope_rejects_nonbase_or_ambiguous_selection(timeframes, symbols):
    with pytest.raises(BridgeError, match="TRAINING_SCOPE_INVALID"):
        EC.training_scope(timeframes, symbols)


def test_d30_subset_is_canonical_and_excludes_other_training_cells(tmp_path):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    assert EC.training_scope("4h,1h", "ETHUSDT,BTCUSDT") == (("1h", "4h"), ("BTCUSDT", "ETHUSDT"))
    async def exercise():
        store = await SQLiteStore(str(tmp_path / "scope.sqlite")).open()
        progress = []
        try:
            for symbol, tf in (("BTCUSDT", "15m"), ("BTCUSDT", "1h"), ("ETHUSDT", "4h")):
                await store.ingest_raw(make_obs(symbol=symbol, timeframe=tf), oi_state="AVAILABLE")
            with pytest.raises(EC.DegenerateTraining) as exc:
                await EC.train_classifier(store, symbols="BTCUSDT", timeframes="1h", progress=progress.append)
            cells = [row for row in progress if row["kind"] == "cell"]
            assert len(cells) == 1 and cells[0]["cell"] == "BTCUSDT:1h" and cells[0]["closed_bars"] == 1
            assert exc.value.training_window["symbols"] == ["BTCUSDT"]
            assert exc.value.training_window["timeframes"] == ["1h"]
        finally:
            await store.close()
    asyncio.run(exercise())


def test_d23_vocabulary_table_stays_contiguous_with_note_below():
    text = (Path(__file__).parents[2] / "APEX_GEN5.md").read_text()
    note_start = text.index("Session-CP-14 (2026-09-17; D23):")
    start = text.rfind("## 2. Complete Vocabulary with Mathematical Definitions", 0, note_start)
    section = text[start:note_start]
    rows = [i for i, line in enumerate(section.splitlines()) if line.startswith("|")]
    assert rows == list(range(rows[0], rows[-1] + 1))
    assert section.count("| Term | Symbol |") == 1
    assert "| participation |" in section and "| structure_quality |" in section and "| PIT |" in section


async def _seed_full_training_fixture(store, symbols=("BTCUSDT", "ETHUSDT")):
    """Unlabelled OHLCV only: native D21 supplies every class member.

    BTC varies throughout; ETH has expanding oscillations then a mid-range
    quiet segment. Past-only M15/H4 data supplies canonical HTF dependencies.
    """
    import math
    import random
    from datetime import datetime, timedelta, timezone
    from apex.data_catalog.contracts import MarketObservation
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for symbol in symbols:
        target_count = 700 if symbol == "BTCUSDT" else 180
        for tf, hours, count, start in (("15m", .25, 65, -16.25), ("4h", 4, 65, -260), ("1h", 1, target_count, 0)):
            rng, price = random.Random(2), 100.
            for i in range(count):
                opening = price
                if tf != "1h":
                    price += .15 + math.sin(i) * .5
                elif symbol == "BTCUSDT":
                    price *= math.exp(rng.gauss(0, .013) + .005 * math.sin(i / 45))
                else:
                    price = 100 + (2 + .05 * i) * math.sin(2 * math.pi * i / 10) if i < 80 else 100.
                wick = .1 if symbol == "ETHUSDT" and tf == "1h" else None
                high = max(opening, price) + (rng.uniform(.1, 2) if wick is None else wick)
                low = min(opening, price) - (rng.uniform(.1, 2) if wick is None else wick)
                stamp = (base + timedelta(hours=start + i * hours)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                obs = MarketObservation(symbol, tf, *[Decimal(str(v)) for v in
                    (opening, high, low, price, rng.uniform(500, 2000))], None, stamp, i, "CLOSED",
                    availability_time="1970-01-01T00:00:00.000Z")
                await store.ingest_raw(obs, oi_state="MISSING")


def test_g2_actual_store_training_in_two_processes_is_byte_identical(tmp_path):
    import json
    import subprocess
    import sys
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    path = tmp_path / "training.sqlite"
    async def seed():
        store = await SQLiteStore(str(path)).open()
        try:
            await _seed_full_training_fixture(store)
        finally:
            await store.close()
    asyncio.run(seed())
    targets = [tmp_path / f"trained-{i}.yaml" for i in range(2)]
    reports = []
    for target in targets:
        # Each CLI launches its own isolated native-engine training worker.
        # No monkeypatch, pre-labelled matrix or existing classifier is used.
        # D35(f): every proof run starts cold-cache; warm-cache byte-equality
        # is proven separately by test_d35_warm_cache_resume_is_byte_identical.
        import shutil
        shutil.rmtree(EC.E11_TRAIN_CACHE_ROOT, ignore_errors=True)
        result = subprocess.run([sys.executable, "scripts/run_apex.py", "train-e11", "--sqlite", str(path),
            "--out", str(target), "--seed", "20260917", "--max-minutes", "6", "--json", "--profile"],
            capture_output=True, text=True, timeout=370)
        assert result.returncode == 0, result.stdout + result.stderr
        report = json.loads(result.stdout)
        assert report["status"] == "TRAINED"
        assert set(report["per_class_counts"]) == set(EC.E11.REGIMES)
        assert all(n > 0 for n in report["per_class_counts"].values())
        assert len([line for line in result.stderr.splitlines() if line.startswith("TRAIN_CELL ")]) == 20
        # D35(c): --profile is stderr-only so the byte-identity proof is
        # unaffected; one per-cell line plus the single fit line on TRAINED.
        assert len([line for line in result.stderr.splitlines() if line.startswith("TRAIN_PROFILE ")]) == 20
        assert len([line for line in result.stderr.splitlines() if line.startswith("TRAIN_PROFILE_FIT ")]) == 1
        reports.append(report)
    assert targets[0].read_bytes() == targets[1].read_bytes()
    assert reports[0]["artifact_sha256"] == reports[1]["artifact_sha256"]
    artifact = EC.load_classifier(targets[0])
    assert artifact["sample_count"] == sum(reports[0]["per_class_counts"].values())
    assert artifact["training_window"]["timeframes"] == ["1h", "4h"]
    print("G2 actual-store proof:", json.dumps({k: reports[0][k] for k in
        ("sample_count", "per_class_counts", "training_window", "artifact_sha256")}, sort_keys=True))


def test_e01_atr_prefix_cache_uses_absolute_boundary_without_changing_failures():
    bars = [{"O": 100 + i, "C": 101 + i, "H": 103 + i, "L": 98 + i} for i in range(80)]
    window = EC.E01._ATRWindow(bars)
    for end in (30, 50, 80):
        expected = EC.E01.atr_sma(bars[:end])
        assert EC.E01.atr_sma(window, idx=end - 1) == expected
        assert EC.E01.atr_sma(window[:end]) == expected
        assert window[:end]._atr_sma_cache is window._atr_sma_cache
    assert len(window._atr_sma_cache) == 3
    assert not isinstance(window[1:], EC.E01._ATRWindow)
    with pytest.raises(IndexError):
        EC.E01.atr_sma(window[:20], idx=49)
    with pytest.raises(ValueError, match="INSUFFICIENT_HISTORY"):
        EC.E01.atr_sma(window[:5])


def test_native_twelve_engine_bundle_persists_full_evidence(tmp_path):
    from pathlib import Path
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    async def exercise():
        store = await SQLiteStore(str(tmp_path / "native.sqlite")).open()
        try:
            await _seed_full_training_fixture(store, symbols=("ETHUSDT",))
            classifier = Path(__file__).parents[1] / "fixtures" / "e11_classifier_v1.yaml"
            producer = EC.EngineContextProducer(store, classifier_path=classifier, environment="PAPER")
            # Native contributor quality now replaces the old injected .9.
            # MTF remains explicit here; this is not the full 38+23 proof.
            bundle = await producer.prepare_engine_bundle("ETHUSDT", "1h", "2026-01-04T18:00:00.000Z",
                rtm_context={"derive_avg_quality": True, "mtf_align": .5})
            contributors = bundle["rtm_quality_contributors"]
            assert contributors
            by_id = {event.evidence_id: event for event in bundle["events"]}
            assert all(row["quality"] == by_id[row["evidence_id"]].quality for row in contributors)
            assert bundle["rtm_avg_quality"] == pytest.approx(sum(row["quality"] for row in contributors)/len(contributors))
            assert tuple(bundle["engine_order"]) == EC.ENGINE_ORDER
            assert bundle["events"]
            assert bundle["classifier_artifact_sha256"] == EC.load_classifier(classifier)["artifact_sha256"]
            assert bundle["regime_state"]["vector"] == bundle["feature_vector"]
            restored = await EC.read_complete_evidence(store, [event.evidence_id for event in bundle["events"]])
            assert EC.canonical_json(restored) == EC.canonical_json(bundle["events"])
            for event in restored:
                event.validate_24_fields()
                assert set(bundle["raw_observation_ids"]).issubset(event.lineage)
                assert EC._iso_to_ms(event.availability_time) <= EC._iso_to_ms("2026-01-04T18:00:00.000Z")
            assert bundle["regime_state"]["snapshot_id"]
            from apex.ops.plan_bridge import _regime_label
            assert _regime_label(bundle["regime_state"]) == bundle["regime_state"]["state"]
            # D31: terminal QX must remain intact, including the native
            # expiry meaning and every other field, not dropped/relabelled.
            later = await producer.prepare_engine_bundle("ETHUSDT", "1h", "2026-01-08T12:00:00.000Z",
                rtm_context={"derive_avg_quality": True, "mtf_align": .5})
            expired = [event for event in later["events"] if event.engine_id == "E05"
                       and event.condition_state.endswith("_EXPIRED")]
            assert expired and all(event.resolution_class == "QX" for event in expired)
            assert await EC.read_complete_evidence(store, [event.evidence_id for event in later["events"]]) == later["events"]
        finally:
            await store.close()
    asyncio.run(exercise())


@pytest.mark.parametrize("context", [{}, {"avg_quality": .9}, {"avg_quality": .9, "mtf_align": None},
                                    {"avg_quality": 1.1, "mtf_align": .5}, {"avg_quality": .9, "mtf_align": float("nan")}])
def test_native_bundle_never_uses_e07_default_quality_or_alignment(context):
    from pathlib import Path
    artifact = EC.load_classifier(Path(__file__).parents[1] / "fixtures" / "e11_classifier_v1.yaml")
    with pytest.raises(BridgeError, match="E07_CONTEXT_UNAVAILABLE"):
        EC.complete_engine_bundle({}, "BTCUSDT", "1h", artifact, rtm_context=context)


def _d31_terminal_e05_event():
    zone = EC.E05.FVGObject(
        fid="d31-terminal-zone", direction="UP", lower=99., upper=101., mid=100., width=2.,
        created_at_ts=1767229200000, created_at_idx=20, quality_tag="QX_EXPIRED",
        fate="EXPIRED", age_bars=96, freshness=.1, salience=.2)
    zone.update_snapshot()
    return EC.E05.E05FVGEngine()._to_evidence(zone, "BTCUSDT", "1h", .9)


def test_d31_terminal_e05_qx_public_insert_full_roundtrip(tmp_path):
    import hashlib
    from dataclasses import asdict, replace
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    async def exercise():
        event = _d31_terminal_e05_event()
        assert event.resolution_class == "QX"
        assert event.condition_state.endswith("_EXPIRED")
        assert event.validity == "DEGRADED"
        payload = asdict(event)
        # Construct the transport envelope independently so the pre-fix
        # failure comes from public insert_evidence's frozen validator.
        raw = EC.canonical_json({"schema": EC.EVIDENCE_ENVELOPE, "event": payload,
            "payload_sha256": hashlib.sha256(EC.canonical_json(payload).encode()).hexdigest()})
        store = await SQLiteStore(str(tmp_path / "terminal.sqlite")).open()
        try:
            await store.insert_evidence(replace(event, explanation=raw))
            assert await EC.read_complete_evidence(store, [event.evidence_id]) == [event]
            assert await EC.persist_complete_evidence(store, [event]) == [event]
            restored_raw = (await (await store.db.execute(
                "SELECT raw FROM evidence_event WHERE evidence_id=?", (event.evidence_id,))).fetchone())[0]
            assert restored_raw == raw
            assert EC.canonical_json(EC.evidence_from_raw(restored_raw)) == EC.canonical_json(event)
        finally:
            await store.close()
    asyncio.run(exercise())


@pytest.mark.parametrize("invalid", ["Q6", "QX_EXPIRED", "", None])
def test_d31_public_insert_still_rejects_invalid_resolution_tags(tmp_path, invalid):
    from dataclasses import replace
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    async def exercise():
        store = await SQLiteStore(str(tmp_path / "invalid.sqlite")).open()
        try:
            with pytest.raises(ValueError, match="resolution_class"):
                await store.insert_evidence(replace(_d31_terminal_e05_event(), resolution_class=invalid))
            assert (await (await store.db.execute("SELECT COUNT(*) FROM evidence_event")).fetchone())[0] == 0
        finally:
            await store.close()
    asyncio.run(exercise())


@pytest.mark.parametrize("values,current,expected", [
    ([1.] * 25 + [2.] * 25, 2., .75),
    ([3.] * 50, 3., .5),
    ([1.] * 50, 2., 1.),
    ([3.] * 50, 2., 0.),
])
def test_d32_native_hv_midrank(values, current, expected):
    states = [SimpleNamespace(hv30=v, as_of=i) for i, v in enumerate(values)]
    assert EC.forecast_vol_quantile(states, SimpleNamespace(hv30=current, as_of=100), timeframe="1h") == expected


def test_d32_49_refuses_50_passes_and_nonfinite_refuses():
    states = [SimpleNamespace(hv30=1., as_of=i) for i in range(50)]
    current = SimpleNamespace(hv30=1., as_of=100)
    with pytest.raises(BridgeError, match="VOL_QUANTILE_UNAVAILABLE"):
        EC.forecast_vol_quantile(states[:49], current, timeframe="1h")
    assert EC.forecast_vol_quantile(states, current, timeframe="1h") == .5
    with pytest.raises(BridgeError, match="VOL_QUANTILE_UNAVAILABLE"):
        EC.forecast_vol_quantile(states, SimpleNamespace(hv30=float("nan"), as_of=100), timeframe="1h")
    states[0].hv30 = float("inf")
    with pytest.raises(BridgeError, match="VOL_QUANTILE_UNAVAILABLE"):
        EC.forecast_vol_quantile(states, current, timeframe="1h")


def test_d32_native_window_cap_and_strict_pit():
    # Native 1d regime window is 180 bars, not all retained native states.
    states = [SimpleNamespace(hv30=0. if i < 20 else 5., as_of=i) for i in range(200)]
    current = SimpleNamespace(hv30=5., as_of=200)
    states += [current, SimpleNamespace(hv30=0., as_of=201)]
    assert EC.forecast_vol_quantile(states, current, timeframe="1d") == .5
    assert EC.forecast_vol_quantile(list(reversed(states)), current, timeframe="1d") == .5
    # Native 1h cap (4320) must not be confused with min_bars (50).
    assert EC.forecast_vol_quantile(states, current, timeframe="1h") == .55


def test_d33_gate10_native_normalized_half_before_after():
    from apex.setup.gates import gate10_forecast_quality
    assert gate10_forecast_quality({"q_forecast": .5, "bootstrap_prior": True}, environment="PAPER").passed


@pytest.mark.parametrize("quality,passed", [(.5, True), (.49, False), (0., False), (1., True), (float("nan"), False), (float("inf"), False)])
def test_d33_gate10_normalized_boundaries(quality, passed):
    from apex.setup.gates import gate10_forecast_quality
    assert gate10_forecast_quality({"q_forecast": quality}).passed is passed


def test_d33_gate10_categorical_and_live_bootstrap():
    from apex.setup.gates import gate10_forecast_quality as gate
    assert gate({"quality": "Q2"}).passed
    assert not gate({"quality": "Q1"}).passed
    assert not gate({"q_forecast": .5, "bootstrap_prior": True}, environment="LIVE").passed


def test_d34_versioned_bootstrap_uncertainty_is_same_e11_snapshot():
    from tests.unit.test_forecast_logistic import ev, X0
    from apex.forecast.logistic import build_forecast, ForecastError
    state = {"snapshot_id": "a"*64, "probs": [.8]+[.025]*8}
    model = EC.paper_bootstrap_uncertainty(state, environment="PAPER")
    rec = build_forecast(ev(), x=X0, uncertainty=model)
    assert rec.u == pytest.approx(.44)
    assert rec.c == pytest.approx(.56)
    assert rec.components["e11_snapshot_id"] == state["snapshot_id"]
    assert rec.components["uncertainty_model"] == "cp14_paper_bootstrap_uncertainty-v1"
    assert rec.uncertainty["tail_risk"] == {"state": "UNAVAILABLE"}
    assert rec.uncertainty["data_quality"] == {"state": "UNAVAILABLE"}
    with pytest.raises(BridgeError, match="PAPER_UNCERTAINTY_NOT_LIVE"):
        EC.paper_bootstrap_uncertainty(state, environment="LIVE")
    with pytest.raises(ForecastError, match="FORECAST_UNCERTAINTY_UNAVAILABLE"):
        build_forecast(ev(), x=X0)
    with pytest.raises(ForecastError, match="UNCERTAINTY_COMPONENT_QX"):
        build_forecast(ev(), x=X0, uncertainty={**model, "tail_risk": 0.})
    with pytest.raises(ForecastError, match="FORECAST_BOOTSTRAP_NOT_LIVE_ELIGIBLE"):
        build_forecast(ev(), x=X0, uncertainty=model, environment="LIVE")
    with pytest.raises(BridgeError, match="FORECAST_UNCERTAINTY_UNAVAILABLE"):
        EC.paper_bootstrap_uncertainty({**state, "probs": [float("nan")]*9}, environment="PAPER")


def test_d33_quality_uses_native_window_not_current_bar():
    from apex.quality.vector import calc_window_quality
    pairs = [(.6, 1), (.9, 0)]
    projected = EC.window_quality_projection(pairs)
    assert projected["q_raw"] == projected["data_trust"] == calc_window_quality(pairs)[0]
    assert projected["q_raw"] != .9
    with pytest.raises(BridgeError, match="WINDOW_QUALITY_UNAVAILABLE"):
        EC.window_quality_projection([(.49, 1), (.99, 0)])
    for bad in (None, float("nan"), 1.1):
        with pytest.raises(BridgeError, match="QUALITY_PROVENANCE_UNAVAILABLE"):
            EC.window_quality_projection([(bad, 0)])


def _d33_mtf_states(tf="1h"):
    scope = __import__("apex.setup.family_sf_fvg_sweep_rev", fromlist=["relative_mtf"]).relative_mtf(tf)
    return {t: {"symbol": "BTCUSDT", "timeframe": t, "as_of": 100,
                "closed": True, "freshness_ok": True, "bias": .5}
            for t in (tf, scope["intermediate"], scope["htf"]) if t}


@pytest.mark.parametrize("bias,label,score", [(.5, "ALIGNED", 1.), (0., "PARTIALLY_ALIGNED", .6), (-.5, "CONFLICTING", 0.)])
def test_d33_mtf_native_directions(bias, label, score):
    states = _d33_mtf_states()
    states["1h"]["bias"] = bias
    result = EC.mtf_projection("BTCUSDT", "1h", 100, states)
    assert (result["mtf_state"], result["mtf_align"]) == (label, score)


@pytest.mark.parametrize("key,value", [("closed", False), ("as_of", 101), ("freshness_ok", False), ("bias", None), ("symbol", "ETHUSDT")])
def test_d33_mtf_missing_stale_future_scope_refuse(key, value):
    states = _d33_mtf_states()
    states["1h"][key] = value
    with pytest.raises(BridgeError, match="MTF_"):
        EC.mtf_projection("BTCUSDT", "1h", 100, states)


def test_d33_mtf_top_vacuity_and_missing_required():
    states = _d33_mtf_states("1mo")
    states["1mo"]["bias"] = 0.
    assert EC.mtf_projection("BTCUSDT", "1mo", 100, states)["mtf_state"] == "ALIGNED"
    states = _d33_mtf_states()
    states.pop(next(t for t in states if t != "1h"))
    with pytest.raises(BridgeError, match="MTF_INSUFFICIENT"):
        EC.mtf_projection("BTCUSDT", "1h", 100, states)


def test_d33_component_quality_opposition_absence_and_features():
    from apex.setup.family_sf_fvg_sweep_rev import REQUIRED_EVIDENCE
    refs = [SimpleNamespace(engine_id=e, state="ACTIVE", direction=1, quality=.8) for e in REQUIRED_EVIDENCE]
    refs += [SimpleNamespace(engine_id="E01", state="ACTIVE", direction=-1, quality=.6),
             SimpleNamespace(engine_id="E04", state="ACTIVE", direction=0, quality=.7)]
    projection = EC.component_projection(refs, 1)
    assert projection["q_i"]["structure"] == .6
    assert projection["s_i"]["structure"] == 1
    assert "volume" not in projection["s_i"]
    assert len(refs) == 8  # no opposing evidence deletion
    x = EC.forecast_features(scores=projection["s_i"], trend_bias=-.4, momentum_z=-2,
        regime_entropy=.8, vol_quantile=.5, temporal_core=False, rr=3., cost_r=.05)
    assert x["s_vol"] == 0.  # E04 presence is not E03 volume presence
    assert x["s_struct"] == 1.  # not multiplied by .6
    assert x["trend_stack"] == -.4
    assert x["temporal_core_flag"] == 0.
    refs[0].quality = None
    with pytest.raises(BridgeError, match="COMPONENT_QUALITY_UNAVAILABLE"):
        EC.component_projection(refs, 1)
    with pytest.raises(BridgeError, match="REQUIRED_EVIDENCE_MISSING"):
        EC.component_projection([], 1)


def test_d33_e07_actual_contributor_mean_not_default():
    contributors = [{"engine_id": "E01", "evidence_id": "ev1", "quality": .4},
                    {"engine_id": "E05", "evidence_id": "ev2", "quality": .8}]
    assert EC.confirmation_quality(contributors) == pytest.approx(.6)
    for bad in ([], [{"engine_id": "E07", "evidence_id": "circular", "quality": .9}],
                [{"engine_id": "E01", "evidence_id": "ev", "quality": None}]):
        with pytest.raises(BridgeError, match="E07_CONFIRMATION_QUALITY_UNAVAILABLE"):
            EC.confirmation_quality(bad)


def test_d33_pattern_hybrid_ranking_opposition_and_invalidation():
    from apex.pattern.detect import PatternHit, CATALOGUE, entity_for
    ids = ["PAT-STR-001", "PAT-STR-002"]
    entities = {i: entity_for(next(r for r in CATALOGUE if r.pattern_id == i)) for i in ids}
    a = PatternHit(ids[0], "test", 1, 0, 5., "DOWN", strength=.8)
    b = PatternHit(ids[1], "test", 1, 1, 5., "DOWN", strength=.5)
    bars = [{"c": 10.}, {"c": 10.}]
    assert EC.select_native_pattern([a, b], entities, bars) == b
    b = replace(b, index=0, strength=.9)
    assert EC.select_native_pattern([a, b], entities, bars) == b
    b = replace(b, strength=.8)
    assert EC.select_native_pattern([b, a], entities, bars) == a
    with pytest.raises(BridgeError, match="PATTERN_SELECTION_AMBIGUOUS"):
        EC.select_native_pattern([a, replace(b, direction=-1)], entities, bars)
    with pytest.raises(BridgeError, match="PATTERN_NOT_DETECTED"):
        EC.select_native_pattern([a], entities, [{"c": 10.}, {"c": 4.}])
    with pytest.raises(BridgeError, match="PATTERN_NOT_DETECTED"):
        EC.select_native_pattern([a], {}, bars)


@pytest.mark.parametrize("state,value", [("VALID", 1.), ("DEGRADED", 0.), ("INVALID", 0.)])
def test_d33_temporal_validity_categories(state, value):
    assert EC.temporal_validity_projection(state) == value


@pytest.mark.parametrize("state", [None, "Q3", "CORE", "UNKNOWN"])
def test_d33_temporal_missing_not_core_flag(state):
    with pytest.raises(BridgeError, match="TEMPORAL_VALIDITY_UNAVAILABLE"):
        EC.temporal_validity_projection(state)


def test_d34_size_request_native_attention_multiplier_and_no_permission():
    kw = dict(capital=10000., exposure=0., risk_state="NoRisk", atr=1000.,
              stop_distance=1., entry=100., contract_multiplier=2., quantity_step=.1)
    result = EC.native_size_request(**kw)
    assert result["atr_cap"] == .001
    assert result["sized_quantity"] == pytest.approx(1.2)  # native float attention 1.25 rounded down to step
    assert result["proposed_notional"] == pytest.approx(240.)
    assert result["request_only"] and result["is_risk_increase"]
    assert EC.native_size_request(**{**kw, "exposure": 5500.})["risk_state"] == "HighRisk"
    for value in (0., None, EC.E04.EPS, float("nan")):
        with pytest.raises(BridgeError, match="SIZE_INPUT_UNAVAILABLE"):
            EC.native_size_request(**{**kw, "atr": value})


def test_d34_shared_paper_close_marks_and_stale_future_refusal():
    opening = EC._iso_to_ms("2026-01-01T00:00:00.000Z")
    row = dict(symbol="BTCUSDT", timeframe="1m", status="CLOSED", open_time_ms=opening,
               availability_ms=opening+60000, receipt_ms=opening+61000, close_price=100.)
    result = EC.paper_close_marks(["BTCUSDT"], {"BTCUSDT": row}, as_of_ms=opening+62000)
    assert result["marks"] == {"BTCUSDT": 100.}
    assert result["mark_model"] == "PAPER_CLOSE_MARK"
    assert EC.paper_close_marks([], {}, as_of_ms=opening)["marks"] == {}
    for over in ({"timeframe": "1h"}, {"receipt_ms": opening+65000}, {"status": "PARTIAL"}, {"close_price": None}):
        with pytest.raises(BridgeError, match="PAPER_MARK_UNAVAILABLE"):
            EC.paper_close_marks(["BTCUSDT"], {"BTCUSDT": {**row, **over}}, as_of_ms=opening+62000)
    with pytest.raises(BridgeError, match="PAPER_MARK_UNAVAILABLE"):
        EC.paper_close_marks(["BTCUSDT"], {"BTCUSDT": row}, as_of_ms=opening+3600000)


def _d34_comparison():
    prev = dict(symbol="BTCUSDT", timeframe="1h", parameter_version="p1", classifier_version="c1",
                close_ms=EC._iso_to_ms("2026-01-01T00:00:00.000Z"), closed=True,
                entropy=.5, conflict_state="CONSENSUS")
    return prev, {**prev, "close_ms": prev["close_ms"]+3600000}


def test_d34_uncertainty_trend_strict_entropy_or_native_conflict_rank():
    prev, current = _d34_comparison()
    assert not EC.uncertainty_trend(current, prev, is_risk_increase=True)
    assert EC.uncertainty_trend({**current, "entropy": .6}, prev, is_risk_increase=True)
    assert EC.uncertainty_trend({**current, "entropy": .4, "conflict_state": "MATERIAL_CONFLICT"}, prev, is_risk_increase=True)
    assert not EC.uncertainty_trend(current, None, is_risk_increase=False)
    for bad in (None, {**prev, "classifier_version": "old"}, {**prev, "symbol": "ETHUSDT"},
                {**prev, "close_ms": current["close_ms"]}, {**prev, "closed": False}):
        with pytest.raises(BridgeError, match="UNCERTAINTY_TREND_UNAVAILABLE"):
            EC.uncertainty_trend(current, bad, is_risk_increase=True)


def _d34_adv_bars():
    end = EC._iso_to_ms("2026-02-01T00:00:00.000Z")
    return end, [dict(open_time_ms=t, timeframe="1h", status="CLOSED", availability_ms=t+3600000, volume=10.)
                 for t in range(end-30*86400000, end, 3600000)]


def test_d34_adv_complete_utc_days_units_and_pit():
    end, bars = _d34_adv_bars()
    assert EC.adv_base_volume(bars, as_of_ms=end+3600000, volume_unit="BASE") == 240.
    assert EC.adv_base_volume(bars, as_of_ms=end, volume_unit="CONTRACT", contract_multiplier=2.) == 480.
    assert EC.adv_base_volume(bars+[dict(open_time_ms=end, volume=1e10)], as_of_ms=end+3600000, volume_unit="BASE") == 240.
    for bad in (bars[1:], bars+[bars[-1]], [*bars[:-1], {**bars[-1], "availability_ms": end+1}]):
        with pytest.raises(BridgeError, match="ADV_UNAVAILABLE"):
            EC.adv_base_volume(bad, as_of_ms=end, volume_unit="BASE")
    with pytest.raises(BridgeError, match="ADV_UNAVAILABLE"):
        EC.adv_base_volume(bars, as_of_ms=end, volume_unit="UNKNOWN")


def test_d34_cost_actual_fee_schedule_side_units_and_floor():
    funding = dict(rate=.001, interval_ms=3600000, next_settlement_ms=3600000, observed_at_ms=0, source="public-test-record")
    kw = dict(quantity=2., entry=100., stop_distance=10., contract_multiplier=3., adv=600.,
              commission_rate=.0005, funding=funding, direction=1, start_ms=0, end_ms=7200000, spread_available=True)
    long = EC.forecast_cost_projection(**kw)
    assert long["funding_settlements"] == 2
    assert long["forecast_cost_r"] == pytest.approx((.001 + .25*.01 + .002)*10)
    assert EC.forecast_cost_projection(**{**kw, "direction": -1})["funding_fraction"] == 0.
    assert EC.forecast_cost_projection(**{**kw, "adv": None, "direction": -1})["forecast_cost_r"] == .05
    for bad in ({}, {**funding, "interval_ms": None}, {**funding, "observed_at_ms": 1}):
        with pytest.raises(BridgeError, match="FUNDING_UNAVAILABLE"):
            EC.forecast_cost_projection(**{**kw, "funding": bad})


def test_d34_public_funding_schedule_real_client_fake_responder():
    fixture = _PublicFactsFixture()
    fixture.funding_schedule = {"fundingIntervalHours": "4", "nextFundingTime": "1767240000000"}
    result = asyncio.run(EC.collect_public_funding_schedule("BTCUSDT", client=fixture.client, now=lambda: 1767225600))
    assert result["interval_ms"] == 4*3600000  # not a guessed eight hours
    assert result["rate"] == Decimal("0.0001")
    fixture.funding_schedule = {}
    with pytest.raises(BridgeError, match="FUNDING_UNAVAILABLE"):
        asyncio.run(EC.collect_public_funding_schedule("BTCUSDT", client=fixture.client))
    fixture.funding_schedule = {"fundingIntervalHours": "4", "nextFundingTime": "1767240000000"}
    assert asyncio.run(EC.collect_public_funding_schedule("BTCUSDT", client=fixture.client))["interval_ms"] == 14400000


def _d34_outcome(i, pnl, stamp="2026-01-01T12:00:00.000Z"):
    return dict(outcome_id=str(i), environment="PAPER", completed=True,
                timestamp_ms=EC._iso_to_ms(stamp), pnl=pnl)


def test_d34_net_losses_current_capital_streak_and_persistent_breach():
    at = EC._iso_to_ms("2026-01-01T13:00:00.000Z")
    rows = [_d34_outcome(1, -300), _d34_outcome(2, 300)]
    result = EC.realized_loss_projection(rows, capital=10000, as_of_ms=at)
    assert result["realized_daily_loss_fraction"] == 0.
    assert result["consecutive_losses"] == 0
    assert "DAILY_LOSS_LIMIT" in result["loss_latches"]  # 300/9700 crossed before recovery
    result = EC.realized_loss_projection(rows[:1], capital=9700, as_of_ms=at)
    assert result["realized_daily_loss_fraction"] == pytest.approx(300/9700)
    streak = [_d34_outcome(i, -1) for i in range(5)] + [_d34_outcome(6, 0)]
    result = EC.realized_loss_projection(streak, capital=9995, as_of_ms=at)
    assert result["consecutive_losses"] == 0
    assert "CONSECUTIVE_LOSSES" in result["loss_latches"]
    review = dict(kind="CONSECUTIVE_LOSSES", actor="OWNER", timestamp_ms=at-1)
    assert not EC.realized_loss_projection(streak, capital=9995, as_of_ms=at, owner_reviews=[review])["loss_latches"]


def test_d34_losses_utc_week_reset_requires_review_pit_and_integrity():
    rows = [_d34_outcome(1, -700, "2026-01-04T12:00:00.000Z")]
    at = EC._iso_to_ms("2026-01-05T00:00:00.000Z")  # Monday
    result = EC.realized_loss_projection(rows, capital=9300, as_of_ms=at)
    assert result["realized_weekly_loss_fraction"] == 0
    assert result["loss_latches"] == ["WEEKLY_LOSS_LIMIT"]
    review = dict(kind="WEEKLY_LOSS_LIMIT", actor="OWNER", timestamp_ms=at)
    assert not EC.realized_loss_projection(rows, capital=9300, as_of_ms=at, owner_reviews=[review])["loss_latches"]
    assert EC.realized_loss_projection([_d34_outcome(2, -100)], capital=10000, as_of_ms=0)["consecutive_losses"] == 0
    for bad in (rows*2, [{**rows[0], "completed": False}], [{**rows[0], "environment": None}]):
        with pytest.raises(BridgeError, match="PAPER_LOSS_UNAVAILABLE"):
            EC.realized_loss_projection(bad, capital=9300, as_of_ms=at)


def test_closeout_phone_fallback_does_not_change_training_defaults():
    assert EC.DEFAULT_TRAINING_TIMEFRAMES == ("1h","4h")
    assert EC.DEFAULT_TRAINING_MAX_MINUTES == 20.
    assert EC.training_scope("15m,30m,1h,2h,4h","BTCUSDT")[0] == ("15m","30m","1h","2h","4h")
    assert EC.training_time_limit(90) == 5400.
    assert EC.DEFAULT_MAX_BARS_PER_CELL is None


# ---------------------------------------------------------------------------
# CP-14.1 / D35: resumable bar-capped training with profiling.


async def _seed_d35_small_store(store, n_1h=120, symbols=("BTCUSDT",)):
    """Small training store with static adequate HTF (the G2 pattern).

    Unlabelled OHLCV only; the native D21 rule supplies every label. The
    15m/4h legs end exactly where the 1h leg starts, so every 1h bar sees
    full 65-bar dependency windows.
    """
    import math
    import random
    from datetime import datetime, timedelta, timezone
    from apex.data_catalog.contracts import MarketObservation
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for symbol in symbols:
        for tf, hours, count, start in (("15m", .25, 65, -16.25), ("4h", 4, 65, -260),
                                        ("1h", 1, n_1h, 0)):
            rng, price = random.Random(11), 100.
            for i in range(count):
                opening = price
                if tf != "1h":
                    price += .15 + math.sin(i) * .5
                else:
                    price *= math.exp(rng.gauss(0, .013) + .005 * math.sin(i / 45))
                high = max(opening, price) + rng.uniform(.1, 2)
                low = min(opening, price) - rng.uniform(.1, 2)
                stamp = (base + timedelta(hours=start + i * hours)).isoformat(
                    timespec="milliseconds").replace("+00:00", "Z")
                obs = MarketObservation(symbol, tf, *[Decimal(str(v)) for v in
                    (opening, high, low, price, rng.uniform(500, 2000))], None, stamp, i, "CLOSED",
                    availability_time="1970-01-01T00:00:00.000Z")
                await store.ingest_raw(obs, oi_state="MISSING")


async def _train_outcome(store, **kwargs):
    """Run train_classifier; normalize TRAINED/degenerate into one shape."""
    progress = []
    try:
        artifact, report = await EC.train_classifier(store, progress=progress.append, **kwargs)
        return ("trained", artifact["sample_count"], report["per_class_counts"],
                report["excluded"], progress)
    except EC.DegenerateTraining as exc:
        return ("refused", exc.reason, exc.histogram, exc.excluded, progress)


def test_d35_bar_cap_validation():
    assert EC.training_bar_cap(None) is None
    assert EC.training_bar_cap(1000) == 1000
    for bad in (0, -3, True, "100", 2.5):
        with pytest.raises(BridgeError, match="TRAINING_BARS_INVALID"):
            EC.training_bar_cap(bad)


def test_d35_protocol_hash_separates_namespaces():
    from apex.data_catalog.contracts import CORE10_SYMBOLS
    base = EC.training_protocol_hash(("1h", "4h"), tuple(CORE10_SYMBOLS), None)
    assert len(base) == 64 and all(c in "0123456789abcdef" for c in base)
    assert EC.training_protocol_hash(("1h", "4h"), tuple(CORE10_SYMBOLS), 1000) != base
    assert EC.training_protocol_hash(("1h",), tuple(CORE10_SYMBOLS), None) != base
    assert EC.training_protocol_hash(("1h", "4h"), ("BTCUSDT",), None) != base


def test_d35_cache_roundtrip_and_invalidation(tmp_path):
    proto = EC.training_protocol_hash(("1h",), ("BTCUSDT",), None)
    path = tmp_path / "cache" / proto / "BTCUSDT_1h.json"
    assert EC.read_cell_cache(path, cell="BTCUSDT:1h", protocol_hash=proto, input_hash="abc") is None
    payload = {"format": EC.E11_TRAIN_CACHE_FORMAT, "cell": "BTCUSDT:1h",
               "training_query_sha256": proto, "input_hash": "abc", "closed_bars": 60,
               "max_bars_per_cell": None, "vector_keys": list(EC.E11.VECTOR_KEYS),
               "samples": [{"as_of": "2026-01-02T00:00:00.000Z", "label": "RANGE",
                            "vector": [float(i) for i in range(8)]}],
               "excluded": {"UPSTREAM_WARMUP": 50}, "window_start": "s", "window_end": "e"}
    EC.write_cell_cache(path, payload)
    assert EC.read_cell_cache(path, cell="BTCUSDT:1h", protocol_hash=proto,
                              input_hash="abc")["samples"] == payload["samples"]
    assert EC.read_cell_cache(path, cell="BTCUSDT:1h", protocol_hash=proto,
                              input_hash="other") is None
    assert EC.read_cell_cache(path, cell="BTCUSDT:1h", protocol_hash="0" * 64,
                              input_hash="abc") is None
    path.write_text("{not json")
    assert EC.read_cell_cache(path, cell="BTCUSDT:1h", protocol_hash=proto,
                              input_hash="abc") is None
    EC.write_cell_cache(path, dict(payload, samples=[{"as_of": "x", "label": "RANGE",
                                                      "vector": [1.0] * 7}]))
    assert EC.read_cell_cache(path, cell="BTCUSDT:1h", protocol_hash=proto,
                              input_hash="abc") is None
    EC.write_cell_cache(path, dict(payload, samples=[{"as_of": "x", "label": "RANGE",
                                                      "vector": [float("nan")] * 8}]))
    assert EC.read_cell_cache(path, cell="BTCUSDT:1h", protocol_hash=proto,
                              input_hash="abc") is None


def test_d35_small_store_cache_resume_reproduces_samples(tmp_path):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    async def exercise():
        store = await SQLiteStore(str(tmp_path / "small.sqlite")).open()
        try:
            await _seed_d35_small_store(store)
            cache = tmp_path / "cache"
            cold = await _train_outcome(store, symbols="BTCUSDT", timeframes="1h", cache_dir=cache)
            proto = EC.training_protocol_hash(("1h",), ("BTCUSDT",), None)
            assert [f.name for f in (cache / proto).glob("*.json")] == ["BTCUSDT_1h.json"]
            cold_cells = [row for row in cold[-1] if row["kind"] == "cell"]
            assert len(cold_cells) == 1 and cold_cells[0]["cache"] == "miss"
            assert cold_cells[0]["eligible_samples"] > 0  # real samples, not an empty set
            warm = await _train_outcome(store, symbols="BTCUSDT", timeframes="1h", cache_dir=cache)
            assert warm[:4] == cold[:4]
            warm_cells = [row for row in warm[-1] if row["kind"] == "cell"]
            assert len(warm_cells) == 1 and warm_cells[0]["cache"] == "hit"
            assert warm_cells[0]["eligible_samples"] == cold_cells[0]["eligible_samples"]
        finally:
            await store.close()
    asyncio.run(exercise())


def test_d35_bar_cap_caps_window_and_namespace(tmp_path):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    async def exercise():
        store = await SQLiteStore(str(tmp_path / "capped.sqlite")).open()
        try:
            await _seed_d35_small_store(store)
            cache = tmp_path / "cache"
            capped = await _train_outcome(store, symbols="BTCUSDT", timeframes="1h",
                                          max_bars_per_cell=100, cache_dir=cache)
            cells = [row for row in capped[-1] if row["kind"] == "cell"]
            assert len(cells) == 1 and cells[0]["closed_bars"] == 100
            capped_proto = EC.training_protocol_hash(("1h",), ("BTCUSDT",), 100)
            assert (cache / capped_proto / "BTCUSDT_1h.json").exists()
            assert not (cache / EC.training_protocol_hash(("1h",), ("BTCUSDT",), None)).exists()
            full = await _train_outcome(store, symbols="BTCUSDT", timeframes="1h", cache_dir=cache)
            full_cells = [row for row in full[-1] if row["kind"] == "cell"]
            assert len(full_cells) == 1 and full_cells[0]["closed_bars"] == 120
            assert full_cells[0]["cache"] == "miss"  # capped run did not populate this namespace
        finally:
            await store.close()
    asyncio.run(exercise())


def test_d35_liveness_tick_every_250_bars(tmp_path):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    async def exercise():
        store = await SQLiteStore(str(tmp_path / "live.sqlite")).open()
        try:
            await _seed_d35_small_store(store, n_1h=300)
            outcome = await _train_outcome(store, symbols="BTCUSDT", timeframes="1h",
                                           cache_dir=tmp_path / "cache")
            ticks = [row for row in outcome[-1] if row["kind"] == "tick"]
            assert len(ticks) == 1
            assert ticks[0]["cell"] == "BTCUSDT:1h"
            assert ticks[0]["bars_done"] == 250 and ticks[0]["bars_total"] == 300
        finally:
            await store.close()
    asyncio.run(exercise())


def test_d35_slice_training_window_equals_live_window(tmp_path):
    from datetime import datetime, timedelta, timezone
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    from apex.identity.canonical_json import canonical_json
    async def exercise():
        store = await SQLiteStore(str(tmp_path / "slice.sqlite")).open()
        try:
            await _seed_d35_small_store(store, n_1h=60)
            producer = EC.EngineContextProducer(store)
            base = datetime(2026, 1, 1, tzinfo=timezone.utc)
            stamps = [(base + timedelta(hours=h)).isoformat(timespec="milliseconds").replace(
                "+00:00", "Z") for h in (1, 30, 60, 200)]
            for tf in ("15m", "4h"):
                rows = await producer.training_dep_window(
                    "BTCUSDT", tf, close_to_ms=int((base + timedelta(hours=200)).timestamp() * 1000),
                    count=1000)
                assert len(rows) == 65
                for as_of in stamps:
                    as_of_ms = int(datetime.fromisoformat(as_of.replace("Z", "+00:00")).timestamp() * 1000)
                    live = await producer.window("BTCUSDT", tf, as_of, 301)
                    sliced = EC.slice_training_window(rows, as_of_ms, tf, 301)
                    assert canonical_json([o.to_dict() for o in sliced]) == canonical_json(
                        [o.to_dict() for o in live])
        finally:
            await store.close()
    asyncio.run(exercise())


def test_d35_optimized_matches_unoptimized_reference_bytes(tmp_path):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    async def exercise():
        store = await SQLiteStore(str(tmp_path / "parity.sqlite")).open()
        try:
            await _seed_d35_small_store(store)
            proto = EC.training_protocol_hash(("1h",), ("BTCUSDT",), None)
            first = await _train_outcome(store, symbols="BTCUSDT", timeframes="1h",
                                         cache_dir=tmp_path / "opt", optimize=True)
            second = await _train_outcome(store, symbols="BTCUSDT", timeframes="1h",
                                          cache_dir=tmp_path / "ref", optimize=False)
            assert second[:4] == first[:4]
            assert (tmp_path / "ref" / proto / "BTCUSDT_1h.json").read_bytes() == (
                tmp_path / "opt" / proto / "BTCUSDT_1h.json").read_bytes()
        finally:
            await store.close()
    asyncio.run(exercise())


def test_d35_timeout_keeps_completed_cells_and_resumes(tmp_path):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    class _StepClock:
        def __init__(self, steps):
            self.calls, self.steps = 0, steps
        def __call__(self):
            self.calls += 1
            return 0.0 if self.calls <= self.steps else 1e9
    async def exercise():
        store = await SQLiteStore(str(tmp_path / "resume.sqlite")).open()
        try:
            await _seed_d35_small_store(store, symbols=("BTCUSDT", "ETHUSDT"))
            cache = tmp_path / "cache"
            proto = EC.training_protocol_hash(("1h",), ("BTCUSDT", "ETHUSDT"), None)
            partial = []
            with pytest.raises(BridgeError, match="TRAINING_TIME_LIMIT"):
                await EC.train_classifier(store, symbols="BTCUSDT,ETHUSDT", timeframes="1h",
                                          cache_dir=cache, progress=partial.append,
                                          monotonic=_StepClock(150))
            assert (cache / proto / "BTCUSDT_1h.json").exists()
            assert not (cache / proto / "ETHUSDT_1h.json").exists()
            assert [row["cell"] for row in partial if row["kind"] == "cell"] == ["BTCUSDT:1h"]
            resumed = await _train_outcome(store, symbols="BTCUSDT,ETHUSDT", timeframes="1h",
                                           cache_dir=cache)
            assert resumed[0] in ("trained", "refused")
            cells = {row["cell"]: row for row in resumed[-1] if row["kind"] == "cell"}
            assert cells["BTCUSDT:1h"]["cache"] == "hit"
            assert cells["ETHUSDT:1h"]["cache"] == "miss"
            assert (cache / proto / "ETHUSDT_1h.json").exists()
        finally:
            await store.close()
    asyncio.run(exercise())


def test_d35_warm_cache_resume_is_byte_identical(tmp_path):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    path = tmp_path / "warm.sqlite"
    async def seed():
        store = await SQLiteStore(str(path)).open()
        try:
            await _seed_full_training_fixture(store)
        finally:
            await store.close()
    asyncio.run(seed())
    async def exercise(cache_dir, target):
        store = await SQLiteStore(str(path)).open()
        try:
            progress = []
            artifact, report = await EC.train_classifier(
                store, cache_dir=cache_dir, max_minutes=6, progress=progress.append)
            EC.write_classifier(artifact, target)
            return artifact, report, progress
        finally:
            await store.close()
    cache = tmp_path / "cache"
    cold_artifact, cold_report, cold_progress = asyncio.run(exercise(cache, tmp_path / "cold.yaml"))
    assert all(n > 0 for n in cold_report["per_class_counts"].values())
    assert sorted(f.name for f in (cache / cold_artifact["training_query_sha256"]).glob("*.json")) == [
        "BTCUSDT_1h.json", "BTCUSDT_4h.json", "ETHUSDT_1h.json", "ETHUSDT_4h.json"]
    warm_artifact, warm_report, warm_progress = asyncio.run(exercise(cache, tmp_path / "warm.yaml"))
    assert (tmp_path / "warm.yaml").read_bytes() == (tmp_path / "cold.yaml").read_bytes()
    assert warm_artifact["artifact_sha256"] == cold_artifact["artifact_sha256"]
    assert warm_report["per_class_counts"] == cold_report["per_class_counts"]
    for row in warm_progress:
        if row["kind"] != "cell":
            continue
        assert row["cache"] == ("hit" if row["closed_bars"] else "miss")


def test_d35_cli_profile_lines_on_empty_store(tmp_path):
    import json
    import subprocess
    import sys
    result = subprocess.run([sys.executable, "scripts/run_apex.py", "train-e11",
                             "--sqlite", str(tmp_path / "empty.sqlite"),
                             "--out", str(tmp_path / "o.yaml"), "--profile", "--json"],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 2, result.stdout + result.stderr
    assert json.loads(result.stdout)["reason"] == "EMPTY_CLASS:CRISIS"
    lines = result.stderr.splitlines()
    assert len([line for line in lines if line.startswith("TRAIN_CELL ")]) == 20
    profiles = [line for line in lines if line.startswith("TRAIN_PROFILE ")]
    assert len(profiles) == 20
    assert all("cache=miss" in line and "engines=E01:0.000" in line for line in profiles)
    assert all("excluded=EMPTY_CLOSED_WINDOW:1" in line for line in profiles)
    assert all("stages=window_read:" in line and "label_confirmation:" in line for line in profiles)
    assert not [line for line in lines if line.startswith("TRAIN_PROGRESS ")]
    assert not [line for line in lines if line.startswith("TRAIN_PROFILE_FIT ")]


def test_d35_cli_timeout_zero_reports_cells_and_writes_nothing(tmp_path):
    import json
    import shutil
    import subprocess
    import sys
    from apex.data_catalog.contracts import CORE10_SYMBOLS
    target = tmp_path / "o.yaml"
    proto = EC.training_protocol_hash(("1h", "4h"), tuple(CORE10_SYMBOLS), None)
    # G2's default-scope run leaves its own cell files behind; clear them so
    # the writes-nothing assertion below tests THIS run only (order-safe).
    shutil.rmtree(EC.E11_TRAIN_CACHE_ROOT / proto, ignore_errors=True)
    try:
        result = subprocess.run([sys.executable, "scripts/run_apex.py", "train-e11",
                                 "--sqlite", str(tmp_path / "empty.sqlite"),
                                 "--out", str(target), "--json", "--max-minutes", "0"],
                                capture_output=True, text=True, timeout=60)
        assert result.returncode == 2, result.stdout + result.stderr
        assert json.loads(result.stdout) == {
            "status": "REFUSED", "reason": "TRAINING_TIME_LIMIT", "artifact_written": False,
            "cells_completed": [],
            "cells_remaining": [f"{symbol}:{tf}" for symbol in CORE10_SYMBOLS for tf in ("1h", "4h")],
            "next_cell": "BTCUSDT:1h"}
        assert not target.exists()
        assert not list((EC.E11_TRAIN_CACHE_ROOT / proto).glob("*.json"))
    finally:
        shutil.rmtree(EC.E11_TRAIN_CACHE_ROOT / proto, ignore_errors=True)


def test_d35_cli_bar_cap_records_window_and_rejects_invalid(tmp_path):
    import json
    import shutil
    import subprocess
    import sys
    from apex.data_catalog.contracts import CORE10_SYMBOLS
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    from datetime import datetime, timedelta, timezone
    async def seed():
        store = await SQLiteStore(str(tmp_path / "bars.sqlite")).open()
        try:
            base = datetime(2026, 1, 1, tzinfo=timezone.utc)
            for i in range(5):
                stamp = (base + timedelta(hours=i)).isoformat(timespec="milliseconds").replace(
                    "+00:00", "Z")
                await store.ingest_raw(make_obs(symbol="BTCUSDT", timeframe="1h", ts=stamp),
                                       oi_state="AVAILABLE")
        finally:
            await store.close()
    asyncio.run(seed())
    try:
        result = subprocess.run([sys.executable, "scripts/run_apex.py", "train-e11",
                                 "--sqlite", str(tmp_path / "bars.sqlite"),
                                 "--out", str(tmp_path / "capped.yaml"), "--json",
                                 "--symbols", "BTCUSDT", "--timeframes", "1h",
                                 "--max-bars-per-cell", "3"],
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 2, result.stdout + result.stderr
        report = json.loads(result.stdout)
        assert report["training_window"]["max_bars_per_cell"] == 3
        assert "cell=BTCUSDT:1h closed_bars=3 " in result.stderr
        uncapped = subprocess.run([sys.executable, "scripts/run_apex.py", "train-e11",
                                   "--sqlite", str(tmp_path / "bars.sqlite"),
                                   "--out", str(tmp_path / "full.yaml"), "--json",
                                   "--symbols", "BTCUSDT", "--timeframes", "1h"],
                                  capture_output=True, text=True, timeout=120)
        assert uncapped.returncode == 2, uncapped.stdout + uncapped.stderr
        assert json.loads(uncapped.stdout)["training_window"]["max_bars_per_cell"] is None
        assert "cell=BTCUSDT:1h closed_bars=5 " in uncapped.stderr
        invalid = subprocess.run([sys.executable, "scripts/run_apex.py", "train-e11",
                                  "--sqlite", str(tmp_path / "bars.sqlite"),
                                  "--out", str(tmp_path / "bad.yaml"), "--json",
                                  "--max-bars-per-cell", "0"],
                                 capture_output=True, text=True, timeout=60)
        assert invalid.returncode == 2, invalid.stdout + invalid.stderr
        assert json.loads(invalid.stdout) == {"status": "REFUSED", "reason": "TRAINING_BARS_INVALID",
                                              "artifact_written": False}
        assert not (tmp_path / "bad.yaml").exists()
    finally:
        for proto in (EC.training_protocol_hash(("1h",), ("BTCUSDT",), 3),
                      EC.training_protocol_hash(("1h",), ("BTCUSDT",), None)):
            shutil.rmtree(EC.E11_TRAIN_CACHE_ROOT / proto, ignore_errors=True)


def _strip_evidence_ids(node):
    if isinstance(node, dict):
        return {k: _strip_evidence_ids(v) for k, v in node.items() if k != "evidence_id"}
    if isinstance(node, (list, tuple)):
        return [_strip_evidence_ids(v) for v in node]
    return node


def test_d35e_p0_threaded_frame_matches_fresh_frame():
    """D35(e) P0: the threaded-structure path equals the fresh path."""
    import random
    from dataclasses import replace
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal
    rng = random.Random(20260919)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    raw = []
    price = 100.
    for i in range(80):
        opening = price; price += rng.uniform(-1, 1)
        raw.append(replace(make_obs(timeframe="1h", oi=None,
            ts=(start + timedelta(hours=i)).isoformat(timespec="milliseconds").replace("+00:00", "Z")),
            open=Decimal(str(opening)), close=Decimal(str(price)),
            high=Decimal(str(max(opening, price) + 1)),
            low=Decimal(str(min(opening, price) - 1)),
            volume=Decimal(str(rng.uniform(300, 1000)))))
    window = EC.closed_engine_window(raw, "1h")
    bars = [EC.E04.observation_to_bar(o, "1h") for o in window]

    def fresh_stream():
        return {"engine": EC.E04.VolatilityEngineV4(timeframe="1h"),
                "pending": list(bars), "evidence": []}

    def observable(frame):
        return EC.canonical_json(_strip_evidence_ids({
            "structure": frame["structure"], "ic": frame["ic"],
            "atr14": frame["atr14"], "trend_stack": frame["trend"]["stack"],
            "trend_bias": frame["trend"]["bias"],
            "confirmation": frame["confirmation"],
            "engine_order": frame["engine_order"],
            "projection_refusals": frame["projection_refusals"],
            "structural": [(e["event_type"], e["candle_index"])
                           for e in frame["structural_events"]],
            "e04": [s.to_canonical() for s in frame["volatility"]["states"]],
        }))

    structure = EC.structure_projection(window, "BTCUSDT", "1h")
    threaded = EC.upstream_frame(window, "BTCUSDT", "1h",
                                 structure_result=structure,
                                 volatility_stream=fresh_stream())
    fresh = EC.upstream_frame(window, "BTCUSDT", "1h",
                              volatility_stream=fresh_stream())
    assert observable(threaded) == observable(fresh)


def test_d35e_p0_e01_conversion_runs_once_per_own_bar(tmp_path, monkeypatch):
    """D35(e) P0: upstream_frame no longer re-parses threaded windows."""
    import asyncio
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    async def exercise():
        store = await SQLiteStore(str(tmp_path / "once.sqlite")).open()
        try:
            await _seed_d35_small_store(store, n_1h=120)
            calls = {"h1": 0, "htf": 0}
            original = EC.E01.observation_to_candle
            def counting(obs, timeframe, duration):
                calls["h1" if obs.timeframe == "1h" else "htf"] += 1
                return original(obs, timeframe, duration)
            monkeypatch.setattr(EC.E01, "observation_to_candle", counting)
            await _train_outcome(store, symbols="BTCUSDT", timeframes="1h",
                                 cache_dir=tmp_path / "once")
            # bars 50..119 convert their own 51..120-bar windows exactly once
            assert calls["h1"] == sum(range(51, 121))
            # one 65-bar computation per static HTF leg, then memoized
            assert calls["htf"] == 130
        finally:
            await store.close()
    asyncio.run(exercise())


def test_d35e_p4_bisect_slice_matches_linear_scan():
    """D35(e) P4: the bisect evidence slice equals the inclusive scan."""
    import random
    from types import SimpleNamespace
    rng = random.Random(20260919)
    for _ in range(50):
        count = rng.choice((0, 1, 2, 5, 40, 150, 400))
        stamps = sorted(rng.randint(0, 10) for _ in range(count))
        evidence = [SimpleNamespace(state=SimpleNamespace(as_of=t))
                    for t in stamps]
        start, end = sorted((rng.randint(-2, 12), rng.randint(-2, 12)))
        expected = [e for e in evidence if start <= e.state.as_of <= end]
        assert EC._retained_e04_evidence(evidence, start, end) == expected


def test_d35e_p4_drain_appends_chronological_evidence():
    """D35(e) P4 precondition: drained evidence as_of is sorted ascending."""
    import random
    from dataclasses import replace
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal
    rng = random.Random(20260919)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    raw = []
    price = 100.
    for i in range(60):
        opening = price; price += rng.uniform(-1, 1)
        raw.append(replace(make_obs(timeframe="1h", oi=None,
            ts=(start + timedelta(hours=i)).isoformat(timespec="milliseconds").replace("+00:00", "Z")),
            open=Decimal(str(opening)), close=Decimal(str(price)),
            high=Decimal(str(max(opening, price) + 1)),
            low=Decimal(str(min(opening, price) - 1)),
            volume=Decimal(str(rng.uniform(300, 1000)))))
    bars = [EC.E04.observation_to_bar(o, "1h") for o in EC.closed_engine_window(raw, "1h")]
    engine = EC.E04.VolatilityEngineV4(timeframe="1h")
    evidence = [ev for bar in bars if (ev := engine.ingest_bar(bar)) is not None]
    stamps = [e.state.as_of for e in evidence]
    assert stamps == sorted(stamps) and len(stamps) >= 5


def test_d35_cli_profile_lines_on_small_store(tmp_path):
    """D35(c): --profile prints real engine/stage data on a small store."""
    import asyncio
    import json
    import shutil
    import subprocess
    import sys
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    async def exercise():
        store = await SQLiteStore(str(tmp_path / "prof55.sqlite")).open()
        try:
            await _seed_d35_small_store(store, n_1h=55)
        finally:
            await store.close()
    asyncio.run(exercise())
    try:
        result = subprocess.run(
            [sys.executable, "scripts/run_apex.py", "train-e11",
             "--sqlite", str(tmp_path / "prof55.sqlite"),
             "--out", str(tmp_path / "prof55.yaml"), "--json", "--profile",
             "--symbols", "BTCUSDT", "--timeframes", "1h"],
            capture_output=True, text=True, timeout=600)
        assert result.returncode == 2, result.stdout + result.stderr
        assert json.loads(result.stdout)["status"] == "REFUSED"
        cells = [line for line in result.stderr.splitlines()
                 if line.startswith("TRAIN_CELL ")]
        assert len(cells) == 1 and "cell=BTCUSDT:1h closed_bars=55 " in cells[0]
        profiles = [line for line in result.stderr.splitlines()
                    if line.startswith("TRAIN_PROFILE ")]
        assert len(profiles) == 1
        assert "engines=E01:" in profiles[0] and "stages=window_read:" in profiles[0]
        assert "excluded=" in profiles[0] and "cache=miss" in profiles[0]
        assert "TRAIN_PROFILE_FIT " not in result.stderr
        assert not (tmp_path / "prof55.yaml").exists()
    finally:
        shutil.rmtree(EC.E11_TRAIN_CACHE_ROOT / EC.training_protocol_hash(
            ("1h",), ("BTCUSDT",), None), ignore_errors=True)


# ---------------------------------------------------------------------------
# CP-14.2 / D36: eight-class E11 fit (TRANSITION is a derived state) with a
# mandatory post-fit entropy/confidence validation report (ADR-CP14-023).


def _d36_matrix(n_rows):
    """Deterministic 8-column training matrix for D36 fit tests."""
    return [[((i * 7 + j * 13 + (i * j) % 5) % 17) / 17.0 - 0.5 for j in range(8)]
            for i in range(n_rows)]


# Golden W/b: produced by the pre-D36 fit_multinomial of main@c5f0261 (the
# commit this branch starts from, before any CP-14.2 edit) on
# _d36_matrix(72) with labels list(E11.REGIMES) * 8 and seed 123. The
# nine-class optimizer protocol is unchanged by D36, so bit-identical
# equality is the regression proof. Provenance is recorded in the CP-14.2 PR.
D36_GOLDEN_W = [
    [0.3430084931737144, -0.6860462797100152, -0.09729552026286134, 0.41951968877902, -1.03414255640865, 1.518643697947403, -1.0987983597920628, 1.0804921356068895],
    [0.5697348243350109, 1.0088792825111683, -2.9421346137068616, 0.770379031485021, 1.2785242009097715, 0.5756028377800233, 1.9641703669316548, 1.7982597958987756],
    [0.09683633795593784, -0.35524153890922544, -0.23120010867059726, -1.974526852383974, -0.2262639591514165, -0.6448110381943286, 0.1967635621244828, -0.2217434342486466],
    [0.8385782176106714, -2.0204134105089233, 2.2117073637457376, 0.5286929171950618, 1.4579139525123663, -0.12002021404265313, 0.7725373217844255, -1.531468917298119],
    [0.3940459209709419, 1.085473625955572, 1.2373488432029847, 0.90021285871624, -0.6583180139205898, -0.3254618724450695, -2.2438742342725786, -0.37671252715552406],
    [-0.7927048096034512, 1.0561817586376785, -1.3022842702731086, -1.156281337142635, -0.07410845750148587, -0.33419248282874364, 0.6714184120422343, 2.274742954927828],
    [-0.9869984960803541, 2.5351021224911388, -1.9283458734404284, -0.5103171378602085, -0.1759244306787494, -1.901896992395156, -0.5194356681587742, 0.5582953876622907],
    [-0.39834719963120785, -1.5145671782784262, 0.7674937159375179, -0.5539919371918484, 1.0655554268009477, 0.8901829433126912, 1.1000630605197292, -2.1551405427729797],
    [-0.03488406403770553, -1.1670785322613098, 2.325739519419704, 1.580197565654057, -1.6305758772820813, 0.3511523664342732, -0.8281849749464859, -1.4346202707880533],
]
D36_GOLDEN_B = [0.12529475523635025, 0.03429430115365462, 0.03384038199144579,
                0.04214814242739484, 0.02648333856057313, 0.03543476959000789,
                -0.1319648679420332, -0.03035999014336817, -0.13517083087402532]


def test_d36_nine_class_fit_bit_identical_to_main_golden():
    """D36(a): all nine classes present -> W/b bit-identical to main@c5f0261."""
    W, b = EC.fit_multinomial(_d36_matrix(72), list(EC.E11.REGIMES) * 8, 123)
    assert W == D36_GOLDEN_W
    assert b == D36_GOLDEN_B


def test_d36_nine_minus_transition_fits_nine_by_eight_finite():
    """D36(b): TRANSITION absent -> fit succeeds, W (9,8), b (9,), finite."""
    required = [name for name in EC.E11.REGIMES if name != "TRANSITION"]
    W, b = EC.fit_multinomial(_d36_matrix(64), required * 8, 123)
    import numpy as np
    W_arr, b_arr = np.asarray(W, dtype=float), np.asarray(b, dtype=float)
    assert W_arr.shape == (9, 8) and b_arr.shape == (9,)
    assert np.isfinite(W_arr).all() and np.isfinite(b_arr).all()


@pytest.mark.parametrize("missing", [name for name in EC.E11.REGIMES if name != "TRANSITION"])
def test_d36_single_missing_required_class_refuses(missing):
    """D36(c): any other single missing class refuses CONFIGURATION_INVALID."""
    labels = [name for name in EC.E11.REGIMES * 8 if name != missing]
    with pytest.raises(BridgeError, match="eight rule-tree classes required for fitting"):
        EC.fit_multinomial(_d36_matrix(64), labels, 123)


def _d36_fake_feature_timeline(rule0_cycle):
    """Store-driven samples whose D21 labels are exactly the rule0 cycle.

    Every candidate is structurally confirmed, so the label is always the
    rule0 value and the derived TRANSITION label never occurs.
    """
    def fake(self, symbol, timeframe, window, *, dep_rows=None,
             engine_profile=None, incremental=False):
        async def generate():
            for index, obs in enumerate(window):
                yield {"index": index, "as_of": obs.timestamp, "confirmation": True,
                       "vector": {key: float((index * 7 + j) % 11) / 11.0 - 0.4
                                  for j, key in enumerate(EC.E11.VECTOR_KEYS)},
                       "rule0": rule0_cycle[index % len(rule0_cycle)]}
        return generate()
    return fake


def test_d36_train_classifier_zero_transition_fits_and_validates(tmp_path, monkeypatch):
    """D36(d): TRANSITION count 0 -> artifact written + validation report."""
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    required = [name for name in EC.E11.REGIMES if name != "TRANSITION"]
    monkeypatch.setattr(EC.EngineContextProducer, "feature_timeline",
                        _d36_fake_feature_timeline(required))

    async def exercise():
        store = await SQLiteStore(str(tmp_path / "zero-trans.sqlite")).open()
        try:
            await _seed_d35_small_store(store)
            return await EC.train_classifier(store, symbols="BTCUSDT",
                                             timeframes="1h",
                                             cache_dir=tmp_path / "cache")
        finally:
            await store.close()

    artifact, report = asyncio.run(exercise())
    assert artifact["K"] == 9 and artifact["sample_count"] == 72
    assert report["per_class_counts"]["TRANSITION"] == 0
    assert all(report["per_class_counts"][name] == 9 for name in required)
    assert EC.validate_classifier(artifact) == artifact  # schema unchanged
    validation = report["validation"]
    assert validation["samples"] == 72
    assert validation["theta_H"] == EC.E11.THETA_H
    assert validation["verdict"] in ("PASS", "WARN")
    assert validation["per_class"]["TRANSITION"]["n"] == 0
    assert all(validation["per_class"][name]["n"] == 9 for name in required)


def test_d36_train_classifier_missing_other_class_refuses_named(tmp_path, monkeypatch):
    """D36(e): another class at 0 -> DegenerateTraining EMPTY_CLASS:<name>."""
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    required = [name for name in EC.E11.REGIMES if name != "TRANSITION"]
    cycle = [name for name in required if name != "CHOP"]
    monkeypatch.setattr(EC.EngineContextProducer, "feature_timeline",
                        _d36_fake_feature_timeline(cycle))

    async def exercise():
        store = await SQLiteStore(str(tmp_path / "missing-choch.sqlite")).open()
        try:
            await _seed_d35_small_store(store)
            with pytest.raises(EC.DegenerateTraining) as exc:
                await EC.train_classifier(store, symbols="BTCUSDT",
                                          timeframes="1h",
                                          cache_dir=tmp_path / "cache")
            return exc
        finally:
            await store.close()

    exc = asyncio.run(exercise())
    assert exc.value.reason == "EMPTY_CLASS:CHOP"
    assert exc.value.refusing_class == "CHOP"
    assert exc.value.histogram["CHOP"] == 0
    assert exc.value.histogram["TRANSITION"] == 0


def test_d36_training_validation_shares_verdicts_and_native_entropy():
    """D36(f): shares + verdict on hand-built W/b; H == E11.compute_logits_softmax."""
    import math
    import numpy as np
    required = [name for name in EC.E11.REGIMES if name != "TRANSITION"]
    # PASS: 16 confident samples (one-hot x, row-100 logits) + 4 uniform.
    W_pass = [[100.0 if i == j else 0.0 for j in range(8)] for i in range(9)]
    X_pass = []
    for i in range(16):
        row = [0.0] * 8
        row[i % 8] = 1.0
        X_pass.append(row)
    X_pass += [[0.0] * 8 for _ in range(4)]
    labels_pass = [required[i % 8] for i in range(20)]
    report = EC.training_validation(X_pass, labels_pass, W_pass, [0.0] * 9)
    assert report["verdict"] == "PASS"
    assert report["samples"] == 20
    assert report["theta_H"] == EC.E11.THETA_H
    assert report["share_H_ge_theta"] == 0.2
    assert report["share_H_ge_0_80"] == 0.2
    assert report["share_H_lt_0_40"] == 0.8
    assert report["share_pmax_ge_0_50"] == 0.8
    assert report["H_max"] == pytest.approx(math.log(9))
    assert report["pmax_median"] == pytest.approx(1.0)
    # The report's H is the runtime function's H, sample for sample.
    hs = [EC.E11.compute_logits_softmax(dict(zip(EC.E11.VECTOR_KEYS, row)),
                                        W_pass, [0.0] * 9)[2] for row in X_pass]
    assert report["H_min"] == min(hs)
    assert report["H_max"] == max(hs)
    assert report["H_median"] == float(np.median(hs))
    for name in EC.E11.REGIMES:
        idxs = [i for i in range(20) if labels_pass[i] == name]
        n = len(idxs)
        assert report["per_class"][name]["n"] == n
        if n:
            # i=0..15 are confident (H < theta_H, pmax ~ 1); i=16..19 uniform.
            expected_h = sum(1 for i in idxs if i >= 16) / n
            expected_p = sum(1 for i in idxs if i < 16) / n
            assert report["per_class"][name]["share_H_ge_theta"] == pytest.approx(expected_h)
            assert report["per_class"][name]["share_pmax_ge_0_50"] == pytest.approx(expected_p)
    # WARN: zero weights/biases -> uniform 1/9 everywhere (H = ln 9, pmax < 0.5).
    W_zero = [[0.0] * 8 for _ in range(9)]
    X_warn = [[(i % 8) / 8.0] * 8 for i in range(10)]
    warn = EC.training_validation(X_warn, ["RANGE"] * 10, W_zero, [0.0] * 9)
    assert warn["verdict"] == "WARN"
    assert warn["share_H_ge_theta"] == 1.0
    assert warn["share_pmax_ge_0_50"] == 0.0
    assert warn["H_min"] == warn["H_max"] == pytest.approx(math.log(9))
    assert warn["per_class"]["RANGE"]["n"] == 10


def test_d36_cache_hashes_equal_main_constants_reuse_phone_namespaces():
    """D36(g): protocol/cell hashes equal main@c5f0261 constants (cache reuse)."""
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal
    from apex.data_catalog.contracts import CORE10_SYMBOLS, MarketObservation
    # Phone-acceptance namespace: (1h,4h) x Core-10 with the 168-bar cap.
    assert EC.training_protocol_hash(("1h", "4h"), tuple(CORE10_SYMBOLS), 168) == (
        "3a8efe2d6e9d436276f9b89be140cbda8d9a3ddda964ec12059b9549c9c1113d")
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def fixed_obs(symbol, timeframe, index):
        stamp = (base + timedelta(hours=index)).isoformat(
            timespec="milliseconds").replace("+00:00", "Z")
        return MarketObservation(
            symbol=symbol, timeframe=timeframe, open=Decimal(100),
            high=Decimal(105), low=Decimal(98), close=Decimal(102),
            volume=Decimal(10), oi=Decimal("500"), timestamp=stamp, sequence=0,
            status="CLOSED", source="TOOBIT", availability_time=stamp,
            oi_lag_seconds=0.0, delay_seconds=1.0, completeness_pct=100.0,
            source_health=1.0)
    window = [fixed_obs("BTCUSDT", "1h", i) for i in range(4)]
    dep_rows = {"4h": [fixed_obs("BTCUSDT", "4h", i) for i in range(2)],
                "15m": [fixed_obs("BTCUSDT", "15m", i) for i in range(3)]}
    assert EC.cell_input_hash(window, dep_rows, 168) == (
        "1eabb6da42bcae88ede90354230b9d9257470c56cc02ce6b5e14606e6f929f01")


def test_d36_cli_trained_prints_train_validation_and_writes_report(tmp_path):
    """D36(h): a cache-hit TRAINED run prints TRAIN_VALIDATION + writes the report."""
    import json
    import shutil
    import subprocess
    import sys
    import time
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    db_path = tmp_path / "d36-cli.sqlite"
    required = [name for name in EC.E11.REGIMES if name != "TRANSITION"]
    protocol = EC.training_protocol_hash(("1h",), ("BTCUSDT",), None)
    cache_dir = EC.E11_TRAIN_CACHE_ROOT / protocol
    data_dir = EC.REPO_ROOT / "data"
    try:
        async def seed_and_prime_cache():
            store = await SQLiteStore(str(db_path)).open()
            try:
                await _seed_d35_small_store(store)
                producer = EC.EngineContextProducer(store)
                now_ms = int(time.time() * 1000)
                window = await producer.window("BTCUSDT", "1h", EC._ms_to_iso(now_ms), 120)
                close_to = EC.close_time_ms(EC._iso_to_ms(window[-1].timestamp), "1h")
                dep_rows = {}
                for tf in ("4h", "15m"):
                    count = (await (await store.db.execute(
                        "SELECT COUNT(*) FROM market_observation WHERE symbol=? AND "
                        "timeframe=? AND candle_status IN ('CLOSED','CORRECTED')",
                        ("BTCUSDT", tf))).fetchone())[0]
                    dep_rows[tf] = await producer.training_dep_window(
                        "BTCUSDT", tf, close_to_ms=close_to, count=int(count))
                input_hash = EC.cell_input_hash(window, dep_rows, None)
                samples = []
                for i in range(56):
                    samples.append({"as_of": f"2026-01-02T{i % 24:02d}:00:00.000Z",
                                    "label": required[i % 8],
                                    "vector": [float((i * 7 + j * 3) % 11) / 11.0 - 0.4
                                               for j in range(8)]})
                EC.write_cell_cache(cache_dir / "BTCUSDT_1h.json", {
                    "format": EC.E11_TRAIN_CACHE_FORMAT, "cell": "BTCUSDT:1h",
                    "training_query_sha256": protocol, "input_hash": input_hash,
                    "closed_bars": len(window), "max_bars_per_cell": None,
                    "vector_keys": list(EC.E11.VECTOR_KEYS), "samples": samples,
                    "excluded": {"UNFINALIZED_TAIL": 48},
                    "window_start": window[0].timestamp,
                    "window_end": window[-1].timestamp})
            finally:
                await store.close()
        asyncio.run(seed_and_prime_cache())
        base = [sys.executable, "scripts/run_apex.py", "train-e11",
                "--sqlite", str(db_path), "--symbols", "BTCUSDT",
                "--timeframes", "1h"]
        json_run = subprocess.run(
            base + ["--out", str(tmp_path / "d36.yaml"), "--json"],
            capture_output=True, text=True, timeout=300)
        assert json_run.returncode == 0, json_run.stdout + json_run.stderr
        report = json.loads(json_run.stdout)
        assert report["status"] == "TRAINED"
        assert report["per_class_counts"]["TRANSITION"] == 0
        assert all(report["per_class_counts"][name] == 7 for name in required)
        assert report["validation"]["samples"] == 56
        assert report["validation"]["verdict"] in ("PASS", "WARN")
        lines = [line for line in json_run.stderr.splitlines()
                 if line.startswith("TRAIN_VALIDATION ")]
        assert len(lines) == 1
        assert lines[0].startswith("TRAIN_VALIDATION verdict=")
        for field in ("share_H_ge_theta=", "share_pmax_ge_0_50=", " samples="):
            assert field in lines[0]
        reports = sorted(data_dir.glob("e11_train_report_*.json"))
        assert reports, "no D36 validation report written"
        assert json.loads(reports[-1].read_text()) == report["validation"]
        text_run = subprocess.run(
            base + ["--out", str(tmp_path / "d36b.yaml")],
            capture_output=True, text=True, timeout=300)
        assert text_run.returncode == 0, text_run.stdout + text_run.stderr
        assert "TRAINED 56 samples" in text_run.stdout
        assert "validation verdict=" in text_run.stdout
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)
        for report_file in data_dir.glob("e11_train_report_*.json"):
            report_file.unlink()
