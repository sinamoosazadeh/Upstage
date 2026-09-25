"""CP-14.6 — D49 values, D50 identity, D51 budget, D52 publishers,
D53 venue calendar, D59 hygiene. D54–D58 are not exercised here.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
from decimal import Decimal

import pytest

from apex.config import load_params
from apex.data_catalog.contracts import CORE10_SYMBOLS
from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import content_id, replay_key, sha256_hex
from apex.ops import engine_context as EC
from apex.scheduler import clock as C

@pytest.fixture()
def harness(tmp_path):
    """Local fixture. Does not load the integration plugin or its autouse env."""
    async def build(**runtime_kwargs):
        from tests.integration.paper_harness import build_harness
        return await build_harness(tmp_path, **runtime_kwargs)

    yield build

HANDOFF_CP145_PROTOCOL_HASH = (
    "d9024bb68fb485e3e0f40059becd3325eac3f228b1b1d6a49482bc52a5773582")


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# T1–T5 (part 13)
# ---------------------------------------------------------------------------

def test_t1_negative_zero_hashes_as_zero():
    """D50 ب۵: float -0.0 and 0.0 are one canonical magnitude."""
    assert canonical_json(-0.0) == canonical_json(0.0) == "0.0"
    assert "-0" not in canonical_json({"x": -0.0, "y": [-0.0]})
    assert content_id({"x": -0.0}) == content_id({"x": 0.0})


def test_t2_replay_key_is_a_named_object_not_a_concatenation():
    """D50 ب۶: a field shift must not collide."""
    common = dict(symbol="BTCUSDT", timeframe="1h",
                  as_of_timestamp="2026-01-01T00:00:00.000Z",
                  input_hash="h", parameter_package_id="pkg",
                  code_revision="rev", canonical_payload="{}")
    shifted = replay_key(engine_version="AB", contract_version="C", **common)
    other = replay_key(engine_version="A", contract_version="BC", **common)
    assert shifted != other
    expected = sha256_hex(canonical_json({
        "engine_version": "AB", "contract_version": "C", **common}))
    assert shifted == expected
    assert len(shifted) == 64


def test_t3_fabric_id_is_content_derived():
    """D50: identical members share fabric_id; evidence_id is not hashed."""
    from apex.fabric.evidence import EvidenceFabric, FabricEvidenceRef, make_fabric_id
    def ref(evidence_id):
        return FabricEvidenceRef(
            evidence_id=evidence_id, engine_id="E01", symbol="BTCUSDT",
            timeframe="1h", state="ACTIVE", direction=1, quality=0.9,
            resolution_class="Q3", age_bars=0.0, as_of=1_700_000_000_000,
            snapshot_id="sn-1", lineage=("obs-1",), parent_ids=())
    a = EvidenceFabric.assemble(
        symbol="BTCUSDT", timeframe="1h", as_of=1_700_000_000_000,
        evidence=[ref("0199c0de-0000-7000-8000-000000000001")],
        data_trust=0.9, raw_observation_ids=["obs-1"])
    b = EvidenceFabric.assemble(
        symbol="BTCUSDT", timeframe="1h", as_of=1_700_000_000_000,
        evidence=[ref("0199c0de-0000-7000-8000-000000000099")],
        data_trust=0.9, raw_observation_ids=["obs-1"])
    assert a.hash == b.hash
    assert a.fabric_id == b.fabric_id == make_fabric_id(a.hash)
    assert a.fabric_id.startswith("fab_") and "-" not in a.fabric_id


def test_t4_bounded_model_quality_admits_a_well_calibrated_triple():
    """D59 ج۲: the additive form blocked a well-calibrated model; the bounded form does not."""
    from apex.quality.vector import bounded_model_quality, q_forecast
    # additive 1 - 0.05 - 0.20 - 0.69 = 0.06 would be degraded.
    score = bounded_model_quality(0.05, 0.20, 0.69)
    assert score >= 0.5
    value, blocked = q_forecast(0.05, 0.20, 0.69)
    assert value == pytest.approx(score)
    assert blocked is False
    bad, blocked_bad = q_forecast(1.0, 1.0, 2.0)
    assert bad < 0.5 and blocked_bad is True


def test_t5_rr_below_min_is_a_named_refusal():
    """D59 و۳: RR is never floored into eligibility."""
    from apex.decision.pipeline import DecisionError, min_rr, units_of_r
    assert min_rr() == pytest.approx(0.5)
    ok = units_of_r(entry=100.0, stop=95.0, target=110.0)
    assert ok["RR"] == pytest.approx(2.0)
    with pytest.raises(DecisionError) as exc:
        units_of_r(entry=100.0, stop=95.0, target=101.0)  # RR = 0.2
    assert exc.value.reason == "DECISION_NO_TRADE"
    assert exc.value.detail == "RR_BELOW_MIN"


# ---------------------------------------------------------------------------
# D49 / D50 / training path
# ---------------------------------------------------------------------------

def test_d49_yaml_values_are_the_pass_artifact_percentiles():
    e = load_params()["e11_params"]
    assert e["theta_H"] == pytest.approx(1.105878)
    assert e["quality_H_Q2"] == pytest.approx(1.229880)
    assert e["quality_H_Q5"] == pytest.approx(0.564415)
    assert e["quality_H_Q5"] < e["theta_H"] < e["quality_H_Q2"]
    assert e["K"] == 9 and e["lambda_ewma"] == pytest.approx(0.94)


def test_d50_intent_id_is_a_content_hash_not_a_proposal_tail():
    from apex.execution.fsm import TradePlan
    from apex.ops.paper_loop import intent_id_for
    plan = TradePlan(
        proposal_id="0199c0de-0000-7000-8000-0000000000ab",
        setup_id="setup-1", symbol="BTCUSDT", timeframe="1h",
        direction="LONG", entry_ref="E", stop_price=1.0, target_price=2.0,
        sized_quantity=0.1, risk_amount=1.0, contract_multiplier=1.0,
        decision="ALLOW", vetoes_applied=(), risk_state="NoRisk",
        package_version="v1", snapshot_id="sn", as_of="2026-01-01T00:00:00.000Z",
        created_utc="2026-01-01T00:00:00.000Z", lineage="l", payload_hash="h",
        environment="PAPER")
    close_ms = 1_767_225_600_000
    intent = intent_id_for(plan, close_ms)
    assert intent.startswith("i-") and len(intent) == 26
    assert not intent.endswith("0000000000ab")
    assert intent == intent_id_for(plan, close_ms)
    assert intent != intent_id_for(plan, close_ms + 1)


def test_d50_cell_cursor_survives_a_new_reader(tmp_path):
    from apex.data_catalog.store import sqlite_store as ss
    from apex.ops.paper_loop import load_cell_cursor, upsert_cell_cursor

    async def scenario():
        store = ss.SQLiteStore(str(tmp_path / "apex.sqlite3"))
        await store.open()
        try:
            await upsert_cell_cursor(
                store.db, "BTCUSDT:1h", 1_700_000_000_000,
                decided_at="2026-01-01T01:00:00.000Z", proposal_id="p-1")
            # An older close must not rewind the lock.
            await upsert_cell_cursor(
                store.db, "BTCUSDT:1h", 1_600_000_000_000,
                decided_at="2026-01-01T00:00:00.000Z", proposal_id="older")
            seen = await load_cell_cursor(store.db)
            assert seen["BTCUSDT:1h"] == 1_700_000_000_000
        finally:
            await store.close()

    run(scenario())


def test_training_path_matches_handoff_cp145():
    """HARD CONSTRAINT: the 720-bar phone cache key is unchanged."""
    assert EC.E11_TRAIN_CACHE_FORMAT == "e11-train-cache-v1"
    digest = EC.training_protocol_hash(("1h", "4h"), tuple(CORE10_SYMBOLS), 720)
    assert digest == HANDOFF_CP145_PROTOCOL_HASH
    assert len(CORE10_SYMBOLS) == 10
    # The query object itself is the CP-14.5 bytes (sorted canonical JSON).
    assert hashlib.sha256(EC.TRAINING_QUERY.encode()).hexdigest() == sha256_hex(
        EC.TRAINING_QUERY)


def test_paper_package_is_named_uncalibrated_and_not_zero_metrics():
    package = EC.paper_package_binding(environment="PAPER")
    assert package["calibration"] == "BOOTSTRAP_UNCALIBRATED"
    assert "rolling_calibration_error" not in package
    assert "brier" not in package
    assert "log_loss" not in package
    documents = {name: EC._YamlSubsetParser(
        (EC.PARAMS_DIR / name).read_text(encoding="utf-8")).parse()
        for name in package["parameter_files"]}
    digest = hashlib.sha256(canonical_json(documents).encode()).hexdigest()
    assert package["parameter_sha256"] == digest
    assert "rolling_calibration_error" not in documents
    from apex.setup.gates import gate13_parameter_package
    paper = gate13_parameter_package(package, environment="PAPER")
    assert paper.passed is True
    assert paper.reason == "PACKAGE_BOOTSTRAP_UNCALIBRATED"
    live = gate13_parameter_package(package, environment="LIVE")
    assert live.passed is False
    assert live.reason == "GATE13_BOOTSTRAP_NOT_LIVE"
    missing = gate13_parameter_package(package)
    assert missing.reason == "CONFIGURATION_INVALID"
    measured = {"package_version": 1, "parameter_package_id": "pkg-real",
                "rolling_calibration_error": 0.05, "brier": 0.20,
                "log_loss": 0.69}
    bounded = gate13_parameter_package(measured, environment="LIVE")
    assert bounded.passed is True
    assert bounded.reason == "PACKAGE_VALID"
    bare = {k: package[k] for k in ("package_version", "parameter_package_id")}
    refused = gate13_parameter_package(bare, environment="PAPER")
    assert refused.passed is False
    assert refused.reason == "GATE13_METRICS_MISSING"


# ---------------------------------------------------------------------------
# D53 — 400-day venue parity
# ---------------------------------------------------------------------------

def test_d53_week_and_month_boundaries_match_the_calendar_for_400_days():
    start = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    end = start + dt.timedelta(days=400)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    weeks = C.tf_close_times("1w", start_ms=start_ms, end_ms=end_ms)
    months = C.tf_close_times("1mo", start_ms=start_ms, end_ms=end_ms)
    assert weeks and months
    for ms in weeks:
        moment = dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc)
        assert moment.weekday() == 0
        assert (moment.hour, moment.minute, moment.second, moment.microsecond) == (0, 0, 0, 0)
        assert start_ms <= ms < end_ms
    for ms in months:
        moment = dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc)
        assert moment.day == 1
        assert (moment.hour, moment.minute) == (0, 0)
        assert start_ms <= ms < end_ms
    # Independent calendar enumeration.
    cursor = start
    while cursor.weekday() != 0:
        cursor += dt.timedelta(days=1)
    expected_weeks = []
    while cursor < end:
        expected_weeks.append(int(cursor.timestamp() * 1000))
        cursor += dt.timedelta(days=7)
    assert weeks == expected_weeks
    expected_months = []
    year, month = 2024, 1
    while True:
        moment = dt.datetime(year, month, 1, tzinfo=dt.timezone.utc)
        if moment >= end:
            break
        if moment >= start:
            expected_months.append(int(moment.timestamp() * 1000))
        month += 1
        if month == 13:
            month, year = 1, year + 1
    assert months == expected_months
    # The epoch floor (Thursday weeks, 30-day months) is not the venue.
    week_ms = 7 * 86_400_000
    epoch_weeks = list(range(((start_ms + week_ms - 1) // week_ms) * week_ms,
                             end_ms, week_ms))
    assert epoch_weeks != weeks
    from apex.ops.bootstrap_service import latest_close_boundary as boot_boundary
    sample = int(dt.datetime(2024, 6, 15, 12, tzinfo=dt.timezone.utc).timestamp() * 1000)
    assert boot_boundary(sample, "1w") == C.latest_close_boundary(sample, "1w")
    assert boot_boundary(sample, "1mo") == C.latest_close_boundary(sample, "1mo")
    monday = dt.datetime.fromtimestamp(
        C.latest_close_boundary(sample, "1w") / 1000, dt.timezone.utc)
    assert monday.weekday() == 0 and monday.day != 15


# ---------------------------------------------------------------------------
# D59 scalars and family mass
# ---------------------------------------------------------------------------

def test_d59_decision_scalars_and_family_mass():
    from apex.decision.pipeline import load_decision_v1
    from apex.setup.family_sf_fvg_sweep_rev import family_engines, family_mass
    from apex.setup.gates import q_thr_for, require_q_thr_complete
    decision = load_decision_v1()
    assert decision["min_rr"] == pytest.approx(0.5)
    assert decision["direction_conflict_threshold"] == pytest.approx(0.15)
    assert decision["context_confidence_gain"] == pytest.approx(8.0)
    assert decision["q_forecast_threshold"] == pytest.approx(0.5)
    assert family_engines() == (
        "structure", "liquidity", "fvg", "trend", "regime", "temporal",
        "orderblock", "momentum")
    assert family_mass() == pytest.approx(0.70)
    assert q_thr_for("1h") == pytest.approx(0.5)
    assert q_thr_for("5m") == pytest.approx(0.56)
    complete = require_q_thr_complete()
    assert len(complete) == 14
    assert complete["5m"] == pytest.approx(0.56)


def test_d59_live_without_a_package_does_not_bootstrap():
    from apex.forecast.logistic import ForecastError, ForecastEvent, X_FEATURES, build_forecast
    event = ForecastEvent(
        target_condition="T", stop_condition="S", horizon=4, entry_ref="E",
        symbol="BTCUSDT", timeframe="1h", timestamp=0)
    x = {key: 0.0 for key in X_FEATURES}
    with pytest.raises(ForecastError) as exc:
        build_forecast(event, x=x, environment="LIVE",
                       uncertainty={"calibration": 0.2, "data_quality": 0.2,
                                    "disagreement": 0.2})
    assert exc.value.reason == "FORECAST_BOOTSTRAP_NOT_LIVE_ELIGIBLE"
    paper = build_forecast(
        event, x=x, environment="PAPER",
        uncertainty={"calibration": 0.2, "data_quality": 0.2, "disagreement": 0.2})
    assert paper.bootstrap_prior is True
    assert paper.p_hat == pytest.approx(0.5)


def test_d59_l2_label_is_disable_new():
    from apex.risk.kernel import EMERGENCY_LADDER, RATCHET_BLOCKED
    assert "L2_DISABLE_NEW" in EMERGENCY_LADDER
    assert "L2_LIMIT_RISK" not in EMERGENCY_LADDER
    assert ("L2_DISABLE_NEW", "L1_PAUSE") in RATCHET_BLOCKED


# ---------------------------------------------------------------------------
# D52 — raw-only refuses; PAPER backfill labels what it writes
# ---------------------------------------------------------------------------

def test_d52_raw_only_then_paper_backfill(tmp_path):
    from apex.data_catalog.contracts import MarketObservation
    from apex.data_catalog.store import sqlite_store as ss
    from apex.ops.plan_bridge import BridgeError

    stamp = "2026-01-01T00:00:00.000Z"
    obs = MarketObservation(
        symbol="BTCUSDT", timeframe="1h", open=Decimal("100"),
        high=Decimal("101"), low=Decimal("99"), close=Decimal("100.5"),
        volume=Decimal("10"), oi=Decimal("5"), timestamp=stamp, sequence=0,
        status="CLOSED", source="TOOBIT", availability_time=stamp)

    async def scenario():
        store = ss.SQLiteStore(str(tmp_path / "apex.sqlite3"))
        await store.open()
        try:
            await store.ingest_raw(obs, "AVAILABLE")
            producer = EC.EngineContextProducer(store, environment="PAPER")
            # The bar is closed only at the next hour. Raw rows alone still
            # have no quality fact.
            closed = "2026-01-01T01:00:00.000Z"
            with pytest.raises(BridgeError) as missing:
                await producer.quality_window("BTCUSDT", "1h", closed, bars=5)
            assert missing.value.reason == "QUALITY_PROVENANCE_UNAVAILABLE"
            with pytest.raises(BridgeError) as live:
                await EC.publish_quality_backfill(store, environment="LIVE")
            assert live.value.reason == "BACKFILL_PAPER_ONLY"
            report = await EC.publish_quality_backfill(
                store, environment="PAPER", symbol="BTCUSDT", timeframe="1h")
            assert report["written"] == 1
            assert report["cells"]["BTCUSDT:1h"]["written"] == 1
            again = await EC.publish_quality_backfill(
                store, environment="PAPER", symbol="BTCUSDT", timeframe="1h")
            assert again["written"] == 0
            assert again["already_present"] == 1
            remaining = await EC.backfill_facts_in_window(
                store, "BTCUSDT", "1h", "2026-12-31T00:00:00.000Z")
            assert remaining == 1
        finally:
            await store.close()

    run(scenario())


def test_d52_backfill_lists_a_receipt_before_close_and_does_not_fake_it(tmp_path, monkeypatch):
    from apex.data_catalog.contracts import MarketObservation
    from apex.data_catalog.store import sqlite_store as ss
    import apex.data_catalog.store.sqlite_store as store_mod

    stamp = "2026-01-01T00:00:00.000Z"
    obs = MarketObservation(
        symbol="ETHUSDT", timeframe="1h", open=Decimal("10"), high=Decimal("10"),
        low=Decimal("10"), close=Decimal("10"), volume=Decimal("1"),
        oi=Decimal("1"), timestamp=stamp, sequence=0, status="CLOSED",
        source="TOOBIT", availability_time=stamp)
    # raw_observation is immutable, so the early receipt is the ingest clock.
    monkeypatch.setattr(store_mod, "_utc_now_ms_iso",
                        lambda: "2020-01-01T00:00:00.000Z")

    async def scenario():
        store = ss.SQLiteStore(str(tmp_path / "apex.sqlite3"))
        await store.open()
        try:
            await store.ingest_raw(obs, "AVAILABLE")
            report = await EC.publish_quality_backfill(
                store, environment="PAPER", symbol="ETHUSDT", timeframe="1h")
            assert report["written"] == 0
            assert len(report["skipped_receipt_before_close"]) == 1
            skipped = report["skipped_receipt_before_close"][0]
            assert skipped["symbol"] == "ETHUSDT"
            assert skipped["created_at"] == "2020-01-01T00:00:00.000Z"
        finally:
            await store.close()

    run(scenario())


# ---------------------------------------------------------------------------
# D51 — six cycles, one admission each, budget resets
# ---------------------------------------------------------------------------

def test_d51_six_cycles_each_admit_one_trade(harness):
    from tests.integration.test_ops_paper_loop import (
        HOUR, START_MS, plan_mapping, seed_bars, shutdown)  # functions, not a plugin

    async def scenario():
        plans = {}
        for index in range(6):
            plans[index] = plan_mapping(
                proposal_id=f"0199c0de-0000-7000-8000-00000000000{index}")

        async def provider(symbol, timeframe, as_of):
            # One plan per close. A repeated close returns None.
            hour = int((C.FixtureClock(as_of).now_ms() - START_MS) / HOUR)
            return plans.pop(hour - 1, None)

        h = await harness(
            plan_provider=provider, max_trades_per_cycle=1,
            cells=[C.BundleCell("BTCUSDT", "1h")])

        async def quiet(due):
            return {"quality_facts_written": 0, "funding_refreshed": 0,
                    "venue_refreshed": 0, "ladder_initialised": False,
                    "failures": [], "backfill_facts_in_window": {}}

        h.runtime._refresh_publishers = quiet
        try:
            await seed_bars(h.store, tuple("100" for _ in range(8)))
            admitted = []
            for index in range(6):
                cycle = await h.runtime.run_cycle(now_ms=START_MS + (index + 1) * HOUR)
                assert cycle["budget_limit"] == 1
                assert h.runtime._budget_taken <= 1
                admitted.append(cycle["cells_complete"])
                # The next cycle must see a reset reservation, not a leftover slot.
                assert h.runtime._budget_taken in (0, 1)
            assert admitted == [1, 1, 1, 1, 1, 1]
            assert len(h.adapter.submitted) >= 6
            # Same close is not decided twice.
            replay = await h.runtime.run_cycle(now_ms=START_MS + 6 * HOUR)
            assert replay["cells_skipped_already_decided"] == 1
            assert replay["cells_due"] == 0
            cursor = await __import__(
                "apex.ops.paper_loop", fromlist=["load_cell_cursor"]
            ).load_cell_cursor(h.store.db)
            assert cursor["BTCUSDT:1h"] == C.latest_close_boundary(
                START_MS + 6 * HOUR, "1h")
        finally:
            await shutdown(h)

    run(scenario())


def test_publisher_timeout_is_named_in_the_same_cycle(monkeypatch):
    import time
    from apex.data_catalog.ingest import toobit_public as tp

    async def scenario():
        async def handle(reader, writer):
            await asyncio.sleep(12)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as exc:
                raise AssertionError(type(exc).__name__)

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        real_init = tp.ToobitPublicClient.__init__

        def init(self, session=None):
            real_init(self, session=session)
            self.base_url = f"http://127.0.0.1:{port}"
            self._attempts = 1

        monkeypatch.setattr(tp.ToobitPublicClient, "__init__", init)
        started = time.monotonic()
        from apex.ops.engine_context import collect_public_funding_schedule
        from apex.ops.paper_loop import _publisher_failure
        with pytest.raises(TimeoutError, match="PUBLISHER_TIMEOUT"):
            await collect_public_funding_schedule("BTCUSDT")
        elapsed = time.monotonic() - started
        assert elapsed < 15
        reason, down = _publisher_failure(TimeoutError("PUBLISHER_TIMEOUT"))
        assert reason == "PUBLISHER_TIMEOUT" and down is True
        other, other_down = _publisher_failure(ValueError("schema"))
        assert other == "ValueError" and other_down is False
        server.close()
        await server.wait_closed()

    run(scenario())


def test_cycle_publishers_reflect_quality_publish(harness):
    from tests.integration.test_ops_paper_loop import START_MS, shutdown

    async def scenario():
        h = await harness(plan_provider=lambda *_: None)

        async def catch_up(moment):
            return {"cells_checked": 0, "cells_updated": 0, "bars_ingested": 0,
                    "failures": [],
                    "quality_publish": {
                        "written": 2, "skipped": 1,
                        "failures": [{"symbol": "BTCUSDT", "timeframe": "1h",
                                      "reason": "QUALITY_PUBLISH_REFUSED"}]}}

        async def refresh(due):
            return {"quality_facts_written": 1, "funding_refreshed": 0,
                    "venue_refreshed": 0, "ladder_initialised": False,
                    "failures": [{"symbol": "ETHUSDT", "reason": "VENUE_FACTS_UNAVAILABLE"}],
                    "backfill_facts_in_window": {}}

        h.runtime.catch_up = catch_up
        h.runtime._refresh_publishers = refresh
        try:
            cycle = await h.runtime.run_cycle(now_ms=START_MS)
            assert cycle["publishers"]["quality_facts_written"] == 3
            assert cycle["publishers"]["failures"][-1]["reason"] == \
                "QUALITY_PUBLISH_REFUSED"
        finally:
            await shutdown(h)

    run(scenario())


def test_crisis_regime_is_bridge_regime_window(monkeypatch, harness):
    from apex.ops.plan_bridge import BridgeError, build_paper_plan
    from tests.integration.test_ops_paper_loop import (
        HOUR, START_MS, _ms_to_iso, bridge_context, seed_bridge_sweep, shutdown,
    )
    import apex.ops.plan_bridge as bridge_mod

    real = bridge_mod.evaluate_cell

    def emit(**kwargs):
        kwargs["regime_state"] = "TREND"
        return real(**kwargs)

    monkeypatch.setattr(bridge_mod, "evaluate_cell", emit)

    async def scenario():
        h = await harness()
        try:
            await seed_bridge_sweep(h.store)

            async def source(symbol, timeframe, as_of):
                context = await bridge_context(h.store, symbol, timeframe, as_of)
                context["regime_state"] = "CRISIS"
                context["e11_context"]["regime_state"] = "CRISIS"
                return context

            as_of = _ms_to_iso(START_MS + 24 * HOUR)
            with pytest.raises(BridgeError) as err:
                await build_paper_plan(
                    store=h.store, context=await source("BTCUSDT", "1h", as_of),
                    symbol="BTCUSDT", timeframe="1h", as_of=as_of)
            assert err.value.reason == "DECISION_NO_TRADE"
            assert err.value.detail == "REGIME_WINDOW"
        finally:
            await shutdown(h)

    run(scenario())


def test_q_thr_matches_q_min_for_every_timeframe():
    from apex.data_catalog.contracts import TIMEFRAMES_14
    from apex.setup.gates import gate2_window_quality, q_thr_for
    q_min = load_params()["quality_weights"]["q_min_by_tf"]
    q_thr = load_params()["quality_weights"]["q_thr_by_tf"]
    assert list(q_thr) == list(q_min)
    for tf in TIMEFRAMES_14:
        assert q_thr_for(tf) == q_min[tf]
        result = gate2_window_quality([(1.0, 0.0)], timeframe=tf)
        assert result.reason != "CONFIGURATION_INVALID"


def test_regime_window_admits_range_and_trend_and_refuses_crisis():
    from apex.decision.pipeline import arbitrate, generate_candidates
    from apex.playbook.pb_fvg_sweep_rev_a import instantiate_playbook
    playbook = instantiate_playbook()
    window = playbook.regime_window
    assert "CRISIS" not in window
    assert "RANGE" in window and "TREND" in window
    setup = {"setup_id": "s", "entry": 100.0, "stop": 99.0, "target": 103.0,
             "P": 0.6, "C": 0.6, "U_sum": 0.2, "cost_unit": 0.05,
             "r_penalty": 0.0, "is_risk_increase": False,
             "uncertainty_is_rising": False}
    candidates = generate_candidates([setup])
    assert candidates
    weights = {"quality": 0.4, "alignment": 0.3, "recency": 0.3}
    candidate = {"playbook_id": "PB_FVG_SWEEP_REV_A",
                 "family_id": "SF_FVG_SWEEP_REV", "direction": "LONG",
                 "regime_window": window, "composite_weights": weights,
                 "quality": 0.9, "alignment": 0.5, "recency": 0.5}
    for regime in ("RANGE", "TREND"):
        got = arbitrate([candidate], regime=regime,
                        family_statuses={"SF_FVG_SWEEP_REV": "ACTIVE"})
        assert got["proposal"] is not None
    crisis = arbitrate([candidate], regime="CRISIS",
                       family_statuses={"SF_FVG_SWEEP_REV": "ACTIVE"})
    assert crisis["proposal"] is None
    assert crisis["reason"]["excluded"]["regime_window"] == 1


def test_missing_regime_window_is_configuration_invalid(monkeypatch):
    from apex.playbook import pb_fvg_sweep_rev_a as pb
    real = pb.load_params()

    def missing():
        class View(dict):
            def __getitem__(self, key):
                if key == "setup_weights":
                    data = dict(real["setup_weights"])
                    data.pop("regime_window", None)
                    return data
                return real[key]
        return View()

    monkeypatch.setattr(pb, "load_params", missing)
    with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
        pb.instantiate_playbook()


def test_l2_migration_is_one_transaction_and_second_call_is_noop(tmp_path):
    import aiosqlite
    from apex.risk.kernel import (
        LADDER_STATE_RENAME_MIGRATION, apply_l2_disable_new_migration,
    )

    async def scenario():
        db = await aiosqlite.connect(str(tmp_path / "ladder.sqlite3"))
        await db.execute(
            "CREATE TABLE apex_risk_ladder_state ("
            "revision_id TEXT PRIMARY KEY, applied_at TEXT NOT NULL, "
            "state TEXT NOT NULL, emergency_state TEXT NOT NULL, "
            "consumed_budget REAL NOT NULL, multiplier REAL NOT NULL, "
            "reason TEXT NOT NULL, snapshot_id TEXT NOT NULL, "
            "parent_revision_id TEXT)")
        await db.execute(
            "INSERT INTO apex_risk_ladder_state VALUES "
            "(?,?,?,?,?,?,?,?,?)",
            ("rev-1", "2026-01-01T00:00:00.000Z", "LowRisk", "L2_LIMIT_RISK",
             0.0, 1.0, "old", "a" * 64, None))
        await db.commit()
        first = await apply_l2_disable_new_migration(db)
        assert first["noop"] is False
        assert first["rebuilt"] is True
        row = await (await db.execute(
            "SELECT emergency_state FROM apex_risk_ladder_state")).fetchone()
        assert row[0] == "L2_DISABLE_NEW"
        seen = await (await db.execute(
            "SELECT migration_name FROM schema_migrations WHERE migration_name=?",
            (LADDER_STATE_RENAME_MIGRATION,))).fetchone()
        assert seen[0] == LADDER_STATE_RENAME_MIGRATION
        with pytest.raises(Exception, match="LADDER_STATE_APPEND_ONLY"):
            await db.execute(
                "UPDATE apex_risk_ladder_state SET reason='mutated'")
            await db.commit()
        with pytest.raises(Exception, match="LADDER_STATE_APPEND_ONLY"):
            await db.execute("DELETE FROM apex_risk_ladder_state")
            await db.commit()
        second = await apply_l2_disable_new_migration(db)
        assert second["noop"] is True
        await db.close()

    run(scenario())
