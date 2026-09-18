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


def test_train_cli_empty_store_refuses_all_nine_without_artifact_write(tmp_path):
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
                         "symbols": list(CORE10_SYMBOLS), "default_timeframes": list(DEFAULT_TRAINING_TIMEFRAMES), "default_symbols": list(CORE10_SYMBOLS)},
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
        outer = self
        class Venue(FakeToobitResponder):
            def _route(self, call, method, path, params):
                call.responded = True
                if method == "GET" and path == "/api/v1/exchangeInfo":
                    return {"http_status": 200, "body": {"symbols": [copy.deepcopy(outer.record)]}}
                if method == "GET" and path == "/api/v1/futures/fundingRate":
                    return {"http_status": 200, "body": {"fundingRate": outer.funding}}
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
    assert json.loads(result.stdout) == {"status": "REFUSED", "reason": "TRAINING_TIME_LIMIT", "artifact_written": False}
    assert not list(tmp_path.glob(".e11-*"))
    assert target.read_text() == "do not replace this artifact\n" if existing else not target.exists()


@pytest.mark.parametrize("timeframes,symbols", [("15m", "BTCUSDT"), ("1h,1h", "BTCUSDT"), ("", "BTCUSDT"), ("1h", "UNKNOWN")])
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
        result = subprocess.run([sys.executable, "scripts/run_apex.py", "train-e11", "--sqlite", str(path),
            "--out", str(target), "--seed", "20260917", "--max-minutes", "6", "--json"],
            capture_output=True, text=True, timeout=370)
        assert result.returncode == 0, result.stdout + result.stderr
        report = json.loads(result.stdout)
        assert report["status"] == "TRAINED"
        assert set(report["per_class_counts"]) == set(EC.E11.REGIMES)
        assert all(n > 0 for n in report["per_class_counts"].values())
        assert len([line for line in result.stderr.splitlines() if line.startswith("TRAIN_CELL ")]) == 20
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
            # Explicit E07 contract inputs: this test proves native assembly,
            # not the still-unfinished 38-context/23-risk source projection.
            bundle = await producer.prepare_engine_bundle("ETHUSDT", "1h", "2026-01-04T18:00:00.000Z",
                rtm_context={"avg_quality": .9, "mtf_align": .5})
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
                rtm_context={"avg_quality": .9, "mtf_align": .5})
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
