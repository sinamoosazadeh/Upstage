"""The 24/7 PAPER runtime (`apex.ops.paper_loop`).

One composition root on a fixture clock: the frozen store + single ledger
writer + the 140-cell scheduler + the execution FSM + a venue double (G9).
Nothing here reaches a network. The plan seam is exercised with an injected
provider — the whole chain runs: plan → gates → FSM.submit → venue query →
fill recorded → protection placed → management → exit → outcome → reconcile.

Also asserted: no provider ⇒ every cell halts with NO_PLAN_PROVIDER (never a
fabricated plan); a plan is never sent twice (the durable ``trade_plan`` row is
the guard); a DEGRADED boot refuses to trade; a malformed plan is refused by
name; the loop honours the control plane's pause; the ledger chain verifies.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import pytest

from apex.bus import EventBus
from apex.config import Config
from apex.data_catalog.contracts import MarketObservation, parse_utc_ms
from apex.data_catalog.store import sqlite_store as ss
from apex.execution.toobit_adapter import AdapterResult, AttemptRecord
from apex.fabric.evidence import FabricEvidenceRef
from apex.forecast.logistic import X_FEATURES
from apex.ledger import store as LS
from apex.ops import paper_loop as PL
from apex.ops.plan_bridge import PaperPlanBridge
from apex.scheduler import clock as C
from tests.integration.test_context_to_trade_paper import (
    gf_bars, real_active_refs, synth_refs, sweep_bars)

START = "2026-01-01T00:00:00.000Z"
START_MS = 1767225600000            # 2026-01-01T00:00:00Z
HOUR = 3_600_000
SYMBOL, TF = "BTCUSDT", "1h"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def signed_env(monkeypatch):
    monkeypatch.setenv("APEX_ENV", "PAPER")
    monkeypatch.setenv("APEX_ALLOW_SIGNED", "1")
    monkeypatch.setenv("TOOBIT_API_KEY", "TEST_KEY_WIRING")
    monkeypatch.setenv("TOOBIT_API_SECRET", "TEST_SECRET_WIRING")


class LedgerClock:
    """Frozen ledger timestamps (deterministic chain hashes)."""

    def __init__(self, stamp: str = START) -> None:
        self.stamp = stamp

    def __call__(self) -> str:
        return self.stamp


def observation(close: str, open_ms: int, *, oi: Optional[Decimal] = None,
                status: str = "CLOSED") -> MarketObservation:
    stamp = _ms_to_iso(open_ms)
    return MarketObservation(
        symbol=SYMBOL, timeframe=TF, open=Decimal(close), high=Decimal(close),
        low=Decimal(close), close=Decimal(close), volume=Decimal("10"), oi=oi,
        timestamp=stamp, sequence=0, status=status, source="TOOBIT",
        availability_time=stamp, oi_lag_seconds=None, delay_seconds=1.0,
        completeness_pct=100.0, source_health=1.0)


def _ms_to_iso(ms: int) -> str:
    import datetime as dt
    moment = dt.datetime.fromtimestamp(ms / 1000.0, dt.timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z"


def adapter_result(*, operation: str = "submit_order", ok: bool = True,
                   outcome: str = "ACKNOWLEDGED", data: Optional[Mapping[str, Any]] = None,
                   order_id: Optional[str] = None, error_code: Optional[str] = None,
                   classification: str = "OK") -> AdapterResult:
    return AdapterResult(
        operation=operation, endpoint="/api/v1/futures/order", ok=ok,
        classification=classification, outcome=outcome, business_code=None,
        http_status=200 if ok else 400, data=dict(data or {}),
        client_order_id=None, order_id=order_id,
        idempotency_key=f"{operation}-{outcome}", reconcile_required=False,
        resubmitted=False, cached=False, interval_disabled=None,
        attempts=(AttemptRecord(
            attempt_no=1, operation=operation, endpoint="/api/v1/futures/order",
            idempotency_key=f"{operation}-{outcome}", timestamp_utc=START,
            classification=classification, business_code=None,
            http_status=200 if ok else 400, result_source="TRANSPORT",
            actor="TEST", outcome=outcome),),
        error_code=error_code, rule="test double")


class FakeAdapter:
    """The venue double: five operations, deterministic responses."""

    def __init__(self, *, entry_price: str = "100", exit_price: str = "111",
                 fill_entry: bool = True, exit_fills: bool = True,
                 disabled: Tuple[Tuple[str, str], ...] = ()) -> None:
        self.entry_price = entry_price
        self.exit_price = exit_price
        self.fill_entry = fill_entry
        self.exit_fills = exit_fills
        self.disabled = set(disabled)
        self.submitted: List[Dict[str, Any]] = []
        self.queries: List[Dict[str, Any]] = []
        self.position_quantity = "0"

    def is_interval_disabled(self, symbol: str, timeframe: str) -> bool:
        return (symbol, timeframe) in self.disabled

    async def submit_order(self, *, intent_id: str, symbol: str, timeframe: str,
                           direction: str, quantity: Any, price: Any,
                           phase: str = "entry", kind: str = "entry",
                           reduce_only: bool = False,
                           timestamp_utc: Optional[str] = None,
                           extra_params: Optional[Mapping[str, Any]] = None,
                           **kwargs: Any) -> AdapterResult:
        self.submitted.append({"intent_id": intent_id, "phase": phase,
                               "kind": kind, "price": str(price),
                               "quantity": str(quantity),
                               "reduce_only": reduce_only,
                               "extra_params": dict(extra_params or {})})
        if kind == "entry" and not self.fill_entry:
            return adapter_result(outcome="ACKNOWLEDGED", order_id=f"o-{intent_id}")
        if kind == "entry":
            return adapter_result(
                outcome="FILLED", order_id=f"o-{intent_id}",
                data={"data": {"avgPrice": self.entry_price,
                               "executedQty": str(quantity),
                               "tradeId": f"t-{intent_id}"}})
        if kind == "exit":
            if not self.exit_fills:
                return adapter_result(outcome="ACKNOWLEDGED",
                                      order_id=f"o-{intent_id}")
            self.position_quantity = "0"
            return adapter_result(
                outcome="FILLED", order_id=f"o-{intent_id}",
                data={"data": {"avgPrice": self.exit_price,
                               "executedQty": str(quantity),
                               "tradeId": f"t-{intent_id}"}})
        return adapter_result(outcome="ACKNOWLEDGED", order_id=f"o-{intent_id}")

    async def query_order_state(self, *, symbol: Optional[str] = None,
                                client_order_id: Optional[str] = None,
                                order_id: Optional[str] = None,
                                scope: str = "single",
                                **kwargs: Any) -> AdapterResult:
        self.queries.append({"scope": scope, "symbol": symbol,
                             "client_order_id": client_order_id})
        if scope == "single":
            if not self.fill_entry:
                return adapter_result(operation="query_order_state",
                                      outcome="ACKNOWLEDGED",
                                      order_id=f"o-{client_order_id}")
            return adapter_result(
                operation="query_order_state", outcome="FILLED",
                order_id=f"o-{client_order_id}",
                data={"data": {"avgPrice": self.entry_price,
                               "executedQty": "0.1",
                               "tradeId": f"t-{client_order_id}"}})
        return adapter_result(operation="query_order_state", outcome="FILLED",
                              data={"data": []})

    async def query_open_positions(self, *, symbol: Optional[str] = None,
                                   **kwargs: Any) -> AdapterResult:
        rows = ([] if Decimal(self.position_quantity) == 0 else
                [{"symbol": symbol or SYMBOL,
                  "quantity": self.position_quantity}])
        return adapter_result(operation="query_open_positions", outcome="FILLED",
                              data={"data": rows})

    async def cancel_order(self, *, symbol: Optional[str] = None,
                           client_order_id: Optional[str] = None,
                           scope: str = "single", **kwargs: Any) -> AdapterResult:
        return adapter_result(operation="cancel_order", outcome="CANCELLED")


async def shutdown(harn: "Harness") -> None:
    """One deterministic teardown: bus → ledger → store (writer task first)."""
    await harn.bus.stop()
    if not harn.ledger.closed:
        await harn.ledger.stop()
    await harn.store.close()


@dataclass
class Harness:
    store: Any
    ledger: LS.LedgerWriter
    bus: EventBus
    clock: C.FixtureClock
    adapter: FakeAdapter
    runtime: PL.PaperRuntime
    notifications: List[str]


@pytest.fixture()
def harness(tmp_path):
    async def build(**runtime_kwargs) -> Harness:
        store = ss.SQLiteStore(str(tmp_path / "apex.sqlite3"))
        await store.open()
        ledger = LS.LedgerWriter(store, clock=LedgerClock())
        await ledger.initialize()
        await ledger.start()
        clock = C.FixtureClock(START)
        adapter = FakeAdapter()
        bus = EventBus()
        bus.start()                      # background dispatcher (a Task)
        notifications: List[str] = []

        async def notifier(text: str) -> Dict[str, Any]:
            notifications.append(text)
            return {"sent": True}

        await seed_setup(store, "setup-0001")
        runtime_kwargs.setdefault("cells", [C.BundleCell(SYMBOL, TF)])
        runtime_kwargs["notifier"] = notifier
        runtime = PL.PaperRuntime(
            config=Config(), store=store, ledger=ledger, bus=bus,
            adapter=adapter, clock=clock, environment="PAPER",
            **runtime_kwargs)
        await runtime.boot(drift_seconds=0.0)
        return Harness(store, ledger, bus, clock, adapter, runtime,
                       notifications)

    yield build


def plan_mapping(**overrides: Any) -> Dict[str, Any]:
    base = {
        "proposal_id": "0199c0de-0000-7000-8000-000000000001",
        "setup_id": "setup-0001", "symbol": SYMBOL, "timeframe": TF,
        "direction": "LONG", "entry_ref": "E-01/BOS",
        "stop_price": 95.0, "target_price": 110.0, "sized_quantity": 0.1,
        "risk_amount": 0.5, "contract_multiplier": 1.0, "decision": "ALLOW",
        "vetoes_applied": [], "risk_state": "LowRisk", "package_version": "v1",
        "snapshot_id": "sn-0001", "as_of": START, "created_utc": START,
        "lineage": "test", "payload_hash": "hash-0001", "environment": "PAPER"}
    base.update(overrides)
    return base


async def seed_setup(store: Any, setup_id: str) -> None:
    """A governed plan implies its `setup_candidate` row exists (the outcome
    table's FK keys on it) — the harness seeds it, as the pipeline would."""
    await store.db.execute(
        "INSERT OR IGNORE INTO setup_candidate (setup_id, timestamp, symbol, "
        "timeframe, pattern_ids, direction, entry_price, stop_loss, "
        "take_profit, risk_reward, confidence, quality, validity, snapshot_id, "
        "parent_ids, payload_hash, regime, utc_activity_window_id, lineage, "
        "authority, authority_scope) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,"
        "?,?,?,?,?)",
        (setup_id, START, SYMBOL, TF, "[]", "BULLISH", "100", "95", "110",
         2.0, 0.6, "Q3", 1, "sn-0001", "[]", "h", "TREND_UP", "aw-1", "[]",
         "SETUP_ENGINE", "cell"))
    await store.db.commit()


async def seed_bars(store, closes: Tuple[str, ...], *, start_ms: int = START_MS):
    for index, close in enumerate(closes):
        await store.ingest_raw(observation(close, start_ms + index * HOUR,
                                           oi=Decimal("500")), "AVAILABLE")


async def seed_bridge_sweep(store, *, start_ms: int = START_MS) -> None:
    """Ingest the real GF-shaped PAPER window used by the bridge provider."""
    for index, bar in enumerate(sweep_bars()):
        ts = start_ms + index * HOUR
        stamp = _ms_to_iso(ts)
        obs = MarketObservation(
            symbol=SYMBOL, timeframe=TF, open=Decimal(repr(bar["o"])),
            high=Decimal(repr(bar["h"])), low=Decimal(repr(bar["l"])),
            close=Decimal(repr(bar["c"])), volume=Decimal(repr(bar["v"])),
            oi=Decimal("500"), timestamp=stamp, sequence=index,
            status="CLOSED", availability_time=stamp)
        await store.ingest_raw(obs, "AVAILABLE")


async def bridge_context(store: Any, symbol: str, timeframe: str,
                         as_of: str) -> Dict[str, Any]:
    """Return complete persisted-style engine context for one real store cell.

    The candles are read by ``PaperPlanBridge`` through ``get_window``. The
    source supplies the non-raw E01/E02/E05/E09/E11/E12 context and complete
    ACTIVE evidence refs, including the actual observation lineage ids. This
    is intentionally a store-double seam: no plan price, score, or risk
    decision is hard-coded in the provider itself.
    """
    cursor = await store.db.execute(
        "SELECT observation_id FROM market_observation WHERE symbol=? AND "
        "timeframe=? ORDER BY open_time", (symbol, timeframe))
    rows = await cursor.fetchall()
    raw_ids = [str(row[0]) for row in rows]
    assert raw_ids, "the bootstrap-style store double must contain raw bars"
    base_refs = getattr(store, "_bridge_engine_refs", None)
    if base_refs is None:
        _, engine_bars = gf_bars()
        base_refs = tuple(real_active_refs(engine_bars) + synth_refs())
        store._bridge_engine_refs = base_refs
    as_of_ms = int(parse_utc_ms(as_of).timestamp() * 1000)
    refs = []
    for ref in base_refs:
        refs.append(FabricEvidenceRef(
            evidence_id=ref.evidence_id, engine_id=ref.engine_id,
            symbol=symbol, timeframe=timeframe, state=ref.state,
            direction=ref.direction, quality=ref.quality,
            resolution_class=ref.resolution_class, age_bars=0.0,
            as_of=as_of_ms, snapshot_id=ref.snapshot_id,
            lineage=(raw_ids[-1],), parent_ids=ref.parent_ids))
    components = ("structure", "liquidity", "fvg", "trend", "regime",
                  "temporal", "orderblock", "momentum")
    return {
        "events": refs, "raw_observation_ids": raw_ids,
        "data_trust": 0.9, "q_raw": 0.9,
        "market_regime": "TREND", "mtf_state": "ALIGNED",
        "utc_window_state": "UTC_W2", "is_overlap": True,
        "volatility_state": "NORMAL", "structure_state": "BOS_UP",
        "regime_confidence": 0.7, "regime_uncertainty": 0.2,
        "divergence_magnitude": 0.1, "temporal_window_validity": 0.9,
        "atr": 1.0,
        "fvg_zones": [{"index": 24, "filled": False,
                        "low": 99.0, "high": 100.0}],
        "bos": {"s_struct": 0.6, "direction": 1},
        "regime_state": "TREND",
        "e11_context": {
            "ic_inputs": {"trendiness_raw": 0.7, "vol_ratio": 1.0,
                          "expansion_raw": 0.5, "level_density": 0.5,
                          "participation_raw": 0.6, "structure_score": 0.6,
                          "momentum_state_raw": "NEUTRAL", "bias_per_TF":
                          {"H4": 0.5, "H1": 0.5, "M15": 0.5}, "atr_z": 0.0},
            "history_windows": {"trend": [0.5], "vol": [0.5],
                                "exp": [0.5], "liq": [0.5], "part": [0.5],
                                "sq": [0.5]},
            "classifier_W": [[0.0] * 8 for _ in range(9)],
            "classifier_b": [0.0] * 9, "regime_state": "TREND",
        },
        "direction": 1,
        "pattern_id": "PAT-WYC-001",
        "x": {key: 0.5 for key in X_FEATURES},
        "forecast_quality": "Q3", "forecast_rr": 3.0,
        "forecast_cost_r": 0.05, "h_norm": 0.4,
        "window_qualities": [(1.0, 0.0)] * 25,
        "temporal_quality": "Q2", "volatility_quality": "Q2",
        "s_i": {key: 1.0 for key in components},
        "q_i": {key: 0.9 for key in components},
        "package": {"package_version": 1, "parameter_package_id": "pkg-1"},
        "p_min_tf": 0.5, "c_min": 0.5, "freshness_ok": True,
        "risk_state": "LowRisk", "family_status": "ACTIVE",
        "arbitration": {
            "composite_weights": {"quality": 0.4, "alignment": 0.3,
                                   "recency": 0.3},
            "regime_window": ["TREND", "TREND_EXPANSION"],
            "alignment": 0.5, "recency": 0.5,
        },
        "risk": {
            "capital": 10000.0, "portfolio_exposure": 100.0,
            "proposed_notional": 50.0, "capital_hard_cap": 1_000_000.0,
            "circuit_breaker_engaged": False, "emergency_state": "NORMAL",
            "per_symbol_exposure": 100.0, "symbol_cap": 1000.0,
            "portfolio_cap": 1_000_000.0, "staleness_seconds": 1.0,
            "freshness_sla_seconds": 30.0, "oi_lag_seconds": 5.0,
            "oi_lag_threshold_seconds": 60.0, "is_risk_increase": False,
            "uncertainty_is_rising": False,
            "realized_daily_loss_fraction": 0.0,
            "realized_weekly_loss_fraction": 0.0, "consecutive_losses": 0,
            "time_to_expiry_days": 40.0, "margin_health_fraction": 0.9,
            "min_quantity": 0.001, "contract_multiplier": 1.0,
            "risk_state": "LowRisk",
        },
    }


# ---------------------------------------------------------------------------
# the plan seam
# ---------------------------------------------------------------------------

def test_no_provider_halts_every_cell_with_a_named_reason(harness):
    async def scenario():
        h = await harness(plan_provider=None)
        try:
            assert h.runtime.trading_enabled is True
            await seed_bars(h.store, ("100", "105"))
            cycle = await h.runtime.run_cycle(now_ms=START_MS + HOUR)
            assert cycle["cells_due"] == 1
            assert cycle["cells_halted"] == 1
            assert cycle["halt_reasons"] == {"NO_PLAN_PROVIDER": 1}
            assert cycle["halt_stages"] == {"setup": 1}
            assert h.runtime.trades == []
            last = h.runtime.scheduler.runs[-1]
            assert last.status == "HALTED" and last.reason == "STAGE_FAILED:setup"
            assert "NO_PLAN_PROVIDER" in last.stages[-1].detail
        finally:
            await shutdown(h)

    run(scenario())


def test_provider_none_for_the_cell_is_a_named_refusal(harness):
    async def scenario():
        h = await harness(plan_provider=lambda symbol, timeframe, as_of: None)
        try:
            await seed_bars(h.store, ("100", "105"))
            cycle = await h.runtime.run_cycle(now_ms=START_MS + HOUR)
            assert cycle["halt_reasons"] == {"NO_PLAN_FOR_CELL": 1}
            last = h.runtime.scheduler.runs[-1]
            assert "NO_PLAN_FOR_CELL" in last.stages[-1].detail
        finally:
            await shutdown(h)

    run(scenario())


def test_engine_bridge_source_is_declared_pending(harness):
    async def scenario():
        h = await harness(signal_source=PL.SIGNAL_SOURCE_ENGINE_BRIDGE)
        try:
            await seed_bars(h.store, ("100", "105"))
            cycle = await h.runtime.run_cycle(now_ms=START_MS + HOUR)
            assert cycle["halt_reasons"] == {"ENGINE_BRIDGE_PENDING": 1}
            assert "ENGINE_BRIDGE_PENDING" in \
                h.runtime.scheduler.runs[-1].stages[-1].detail
        finally:
            await shutdown(h)

    run(scenario())


# ---------------------------------------------------------------------------
# the whole chain
# ---------------------------------------------------------------------------

def test_plan_runs_submit_fill_protect_manage_and_exit(harness):
    async def scenario():
        planned = plan_mapping()
        h = await harness(
            plan_provider=lambda symbol, timeframe, as_of: dict(planned))
        try:
            await seed_bars(h.store, ("100", "105"))
            # the bar the cell runs on (close 105) is the one the fixture clock
            # is aligned to: close_ms = 01:00, so as_of = 01:00.
            cycle = await h.runtime.run_cycle(now_ms=START_MS + HOUR)
            assert cycle["cells_due"] == 1, cycle["halt_reasons"]
            assert cycle["cells_complete"] == 1, cycle["halt_reasons"]
            trade = h.runtime.trades[-1]
            assert trade["submitted"] is True and trade["protected"] is True
            assert trade["state"] == "MANAGED"
            assert trade["fill"]["filled"] is True
            assert h.runtime.working  # one managed position

            # the fill came from the SUBMISSION answer itself (no re-query:
            # the frozen FSM matrix has no second transition from FILLED)
            assert trade["fill"]["source"] == "SUBMIT_RESULT"
            assert trade["fill"]["price"] == "100"
            # the durable record exists: the trade_plan row + the ledger chain
            counts = await h.runtime.plans.counts()
            assert counts == {"materialized": 1, "sent": 1}
            chain = await h.ledger.verify_chain()
            assert chain["intact"] is True
            events = {e.event_type for e in await h.ledger.read_ledger()}
            assert {"TRADE_PLAN", "FILL"} <= events

            # a later close, the SAME plan: the cell runs again and refuses to
            # double-materialize (the dedupe guard, not the per-close filter)
            again = await h.runtime.run_cycle(now_ms=START_MS + 2 * HOUR)
            assert again["halt_reasons"] == {"PLAN_ALREADY_MATERIALIZED": 1}
            assert "PLAN_ALREADY_MATERIALIZED" in \
                h.runtime.scheduler.runs[-1].stages[-1].detail
            assert len(h.adapter.submitted) == 3   # entry + stop + target, once

            # a bar above the target closes the position through the venue
            await seed_bars(h.store, ("111",), start_ms=START_MS + 2 * HOUR)
            actions = await h.runtime.manage_positions(
                as_of=_ms_to_iso(START_MS + 2 * HOUR))
            assert len(actions) == 1
            assert actions[0]["exit_reason"] == "TARGET_1"
            assert actions[0]["filled"] is True
            assert actions[0]["reconciled"] is True
            assert h.runtime.working == {}
            assert any(order["kind"] == "exit"
                       for order in h.adapter.submitted)
            outcomes = [e for e in await h.ledger.read_ledger()
                        if e.event_type == "OUTCOME"]
            assert outcomes and outcomes[-1].result == "TARGET_1"
            assert (await h.ledger.verify_chain())["intact"] is True
        finally:
            await shutdown(h)

    run(scenario())


def test_an_unfilled_entry_stays_working_and_records_nothing(harness):
    async def scenario():
        planned = plan_mapping()
        h = await harness(
            plan_provider=lambda symbol, timeframe, as_of: dict(planned))
        h.adapter.fill_entry = False
        try:
            await seed_bars(h.store, ("100", "105"))
            cycle = await h.runtime.run_cycle(now_ms=START_MS + HOUR)
            assert cycle["cells_complete"] == 1
            trade = h.runtime.trades[-1]
            assert trade["submitted"] is True and trade["fill"]["filled"] is False
            # an ACKNOWLEDGED entry IS polled through the keyed Ch.16 query
            assert any(q["scope"] == "single" for q in h.adapter.queries)
            assert trade["fill"]["reason"] == "FILL_NOT_OBSERVED_YET"
            assert trade["protected"] is False
            assert h.runtime.working == {}
            fills = [e for e in await h.ledger.read_ledger()
                     if e.event_type == "FILL"]
            assert fills == []                    # never a fabricated fill
            assert h.runtime.trades[-1]["state"] == "ACKNOWLEDGED"
        finally:
            await shutdown(h)

    run(scenario())


def test_no_market_data_is_refused_before_any_plan_is_read(harness):
    async def scenario():
        called: List[str] = []

        def provider(symbol, timeframe, as_of):
            called.append(symbol)
            return plan_mapping()

        h = await harness(plan_provider=provider)
        try:
            cycle = await h.runtime.run_cycle(now_ms=START_MS + HOUR)
            assert cycle["halt_reasons"] == {"NO_MARKET_DATA": 1}
            assert called == []                   # nothing to plan against
            assert h.runtime.trades == []
        finally:
            await shutdown(h)

    run(scenario())


def test_malformed_plan_is_refused_by_name(harness):
    async def scenario():
        h = await harness(plan_provider=lambda s, t, a: plan_mapping(
            decision="MAYBE"))
        try:
            await seed_bars(h.store, ("100", "105"))
            cycle = await h.runtime.run_cycle(now_ms=START_MS + HOUR)
            assert cycle["halt_reasons"] == {"PLAN_MALFORMED": 1}
            assert "PLAN_MALFORMED" in h.runtime.scheduler.runs[-1].stages[-1].detail
            assert h.adapter.submitted == []
        finally:
            await shutdown(h)

    run(scenario())


def test_risk_reject_and_zero_quantity_never_reach_the_venue(harness):
    async def scenario():
        h = await harness(plan_provider=lambda s, t, a: plan_mapping(
            decision="REJECT"))
        try:
            await seed_bars(h.store, ("100", "105"))
            cycle = await h.runtime.run_cycle(now_ms=START_MS + HOUR)
            assert cycle["halt_reasons"] == {"PLAN_REJECTED_BY_RISK": 1}
            assert "PLAN_REJECTED_BY_RISK" in \
                h.runtime.scheduler.runs[-1].stages[-1].detail
            assert h.adapter.submitted == []
        finally:
            await shutdown(h)

    run(scenario())


def test_disabled_interval_never_reaches_the_venue(harness):
    async def scenario():
        h = await harness(plan_provider=lambda s, t, a: plan_mapping())
        h.adapter.disabled = {(SYMBOL, TF)}
        try:
            await seed_bars(h.store, ("100", "105"))
            cycle = await h.runtime.run_cycle(now_ms=START_MS + HOUR)
            assert cycle["halt_reasons"] == {"INTERVAL_DISABLED_FOR_CELL": 1}
            assert "INTERVAL_DISABLED_FOR_CELL" in \
                h.runtime.scheduler.runs[-1].stages[-1].detail
            assert h.adapter.submitted == []
        finally:
            await shutdown(h)

    run(scenario())


def test_environment_mismatch_is_refused(harness):
    async def scenario():
        h = await harness(plan_provider=lambda s, t, a: plan_mapping(
            environment="RESEARCH"))
        try:
            await seed_bars(h.store, ("100", "105"))
            cycle = await h.runtime.run_cycle(now_ms=START_MS + HOUR)
            assert cycle["halt_reasons"] == {"PLAN_ENVIRONMENT_MISMATCH": 1}
            assert "PLAN_ENVIRONMENT_MISMATCH" in \
                h.runtime.scheduler.runs[-1].stages[-1].detail
        finally:
            await shutdown(h)

    run(scenario())


# ---------------------------------------------------------------------------
# boot gate, budget, supervision, loop
# ---------------------------------------------------------------------------

def test_a_plan_without_its_setup_row_is_refused(harness):
    """ISSUE-CP9-004: `outcome.setup_id` is a FK to `setup_candidate`, so a
    plan whose setup row is missing could never be closed and booked — the
    runtime refuses it by name instead of dying at outcome time."""
    async def scenario():
        h = await harness(plan_provider=lambda s, t, a: plan_mapping(
            setup_id="setup-does-not-exist"))
        try:
            await seed_bars(h.store, ("100", "105"))
            cycle = await h.runtime.run_cycle(now_ms=START_MS + HOUR)
            assert cycle["halt_reasons"] == {"NO_SETUP_ROW_FOR_PLAN": 1}
            assert "NO_SETUP_ROW_FOR_PLAN" in \
                h.runtime.scheduler.runs[-1].stages[-1].detail
            assert h.adapter.submitted == []          # never reached a venue
            assert h.runtime.trades == []
        finally:
            await shutdown(h)

    run(scenario())


def test_a_degraded_boot_refuses_to_trade(harness):
    async def scenario():
        planned = plan_mapping()
        h = await harness(plan_provider=lambda s, t, a: dict(planned))
        try:
            await seed_bars(h.store, ("100", "105"))
            unmeasurable = await h.runtime.boot(drift_seconds=None)
            assert unmeasurable["new_trades_allowed"] is False
            cycle = await h.runtime.run_cycle(now_ms=START_MS + HOUR)
            assert cycle["halt_reasons"] == {"BOOT_NOT_READY": 1}
            assert "BOOT_NOT_READY" in h.runtime.scheduler.runs[-1].stages[-1].detail
            assert h.adapter.submitted == []
            assert h.runtime.cycles[-1]["trading_enabled"] is False
        finally:
            await shutdown(h)

    run(scenario())


def test_trade_budget_stops_the_cycle(harness):
    async def scenario():
        plans = {"BTCUSDT|1h": plan_mapping()}
        h = await harness(
            plan_provider=lambda s, t, a: plans.pop(f"{s}|{t}", None),
            max_trades_per_cycle=1, cells=[C.BundleCell("BTCUSDT", "1h"),
                                           C.BundleCell("ETHUSDT", "1h")])
        try:
            await seed_bars(h.store, ("100", "105"))
            await h.store.ingest_raw(MarketObservation(
                symbol="ETHUSDT", timeframe=TF, open=Decimal("10"),
                high=Decimal("10"), low=Decimal("10"), close=Decimal("10"),
                volume=Decimal("1"), oi=Decimal("5"),
                timestamp=_ms_to_iso(START_MS), sequence=0, status="CLOSED",
                source="TOOBIT", availability_time=_ms_to_iso(START_MS),
                oi_lag_seconds=0.0, delay_seconds=1.0, completeness_pct=100.0,
                source_health=1.0), "AVAILABLE")
            cycle = await h.runtime.run_cycle(now_ms=START_MS + HOUR)
            assert cycle["cells_due"] == 2
            assert cycle["cells_complete"] == 1          # budget honoured
            assert cycle["halt_reasons"] == {"TRADE_BUDGET_REACHED": 1}
            details = [st.detail for r in h.runtime.scheduler.runs
                       for st in r.stages if st.status == "FAIL"]
            assert any("TRADE_BUDGET_REACHED" in d for d in details)
        finally:
            await shutdown(h)

    run(scenario())


def test_control_pause_and_gateway_are_honoured_in_the_loop(harness):
    async def scenario():
        h = await harness()
        try:
            class Control:
                paused = True
                new_positions_disabled = False

            h.runtime.control = Control()
            outcome = await h.runtime.run(cycles=1, interval=0, sleep=_no_sleep)
            assert outcome["cycles"] == 1
            assert h.runtime.cycles == []                # nothing ran while paused
            assert outcome["ledger_chain_intact"] is True
        finally:
            await shutdown(h)

    run(scenario())


def test_run_loop_is_bounded_and_the_chain_verifies(harness):
    async def scenario():
        h = await harness()
        try:
            await seed_bars(h.store, ("100", "105"))
            outcome = await h.runtime.run(cycles=2, interval=0, sleep=_no_sleep)
            assert outcome["cycles"] == 2
            assert len(h.runtime.cycles) == 2
            assert outcome["ledger_chain_intact"] is True
            assert h.runtime.scheduler.concurrent_peak <= 4
        finally:
            await shutdown(h)

    run(scenario())


def test_notifier_receives_one_line_per_cycle(harness):
    async def scenario():
        h = await harness()
        try:
            await seed_bars(h.store, ("100", "105"))
            await h.runtime.run_cycle(now_ms=START_MS + HOUR)
            assert h.notifications and "cycle 1" in h.notifications[-1]
            assert "cells=" in h.notifications[-1]
        finally:
            await shutdown(h)

    run(scenario())


async def _no_sleep(seconds: float) -> None:
    return None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_normalize_plan_accepts_the_frozen_shapes(self):
        plan = PL.normalize_plan(plan_mapping())
        assert plan.proposal_id == "0199c0de-0000-7000-8000-000000000001"
        assert plan.sized_quantity == 0.1 and plan.environment == "PAPER"
        row = dict(plan_mapping(), vetoes_applied="[3]")
        assert PL.normalize_plan(row).vetoes_applied == (3,)
        with pytest.raises(PL.CellRefusal) as excinfo:
            PL.normalize_plan(plan_mapping(proposal_id=""))
        assert excinfo.value.reason == "PLAN_MALFORMED"

    def test_fill_from_result_never_invents_numbers(self):
        plan = PL.normalize_plan(plan_mapping())
        assert PL.fill_from_result(adapter_result(outcome="ACKNOWLEDGED"), plan) is None
        assert PL.fill_from_result(adapter_result(outcome="FILLED", data={}), plan) is None
        filled = PL.fill_from_result(adapter_result(
            outcome="FILLED", data={"data": {"avgPrice": "101.5",
                                             "executedQty": "0.1"}}), plan)
        assert filled["price"] == "101.5" and filled["quantity"] == "0.1"


def test_last_closed_price_is_pit_safe(harness):
    async def scenario():
        h = await harness()
        try:
            await seed_bars(h.store, ("100", "105"))
            price = await PL.last_closed_price(h.store, SYMBOL, TF,
                                               _ms_to_iso(START_MS + 30 * 60 * 1000))
            assert price == "100"          # the 01:00 bar is not closed yet
            price = await PL.last_closed_price(h.store, SYMBOL, TF,
                                               _ms_to_iso(START_MS + HOUR))
            assert price == "105"
            assert await PL.last_closed_price(h.store, "ETHUSDT", TF, START) is None
        finally:
            await shutdown(h)

    run(scenario())


def test_governed_bridge_drives_fixture_paper_lifecycle(harness):
    """ISSUE-CP9-006: the provider is real, not an injected plan mapping.

    Raw bars are ingested into the same SQLite store the runtime reads. The
    context source is a bootstrap-style store double carrying complete ACTIVE
    evidence and engine-owned derived inputs; every downstream authority then
    runs before the existing FSM/venue double owns execution.
    """
    async def scenario():
        h = await harness()
        try:
            await seed_bridge_sweep(h.store)

            async def source(symbol, timeframe, as_of):
                return await bridge_context(h.store, symbol, timeframe, as_of)

            bridge = PaperPlanBridge(store=h.store, context_source=source)
            h.runtime.plan_provider = bridge
            first = await h.runtime.run_cycle(now_ms=START_MS + 24 * HOUR)

            assert first["cells_complete"] == 1
            assert first["cells_halted"] == 0
            assert not bridge.refusals
            plan = bridge.plans[f"{SYMBOL}:{TF}"]
            assert plan["decision"] == "ALLOW"
            assert plan["environment"] == "PAPER"
            assert plan["direction"] == "LONG"
            assert bridge.traces[f"{SYMBOL}:{TF}"]["evaluation"].status == "EMITTED"
            assert all(result["passed"] for result in
                       bridge.traces[f"{SYMBOL}:{TF}"]["evaluation"].gate_block["results"].values())
            assert bridge.traces[f"{SYMBOL}:{TF}"]["risk"]["veto_evaluation_order"] == list(range(1, 15))
            replay = await bridge(SYMBOL, TF, _ms_to_iso(START_MS + 24 * HOUR))
            assert replay == plan              # T-DR bridge plan bytes are stable

            trade = h.runtime.trades[-1]
            assert trade["submitted"] is True
            assert trade["fill"]["filled"] is True
            assert trade["protected"] is True
            assert h.runtime.working

            setup = await h.store.db.execute(
                "SELECT setup_id, symbol, timeframe, direction, pattern_ids, "
                "validity, authority FROM setup_candidate WHERE setup_id=?",
                (plan["setup_id"],))
            setup_row = await setup.fetchone()
            assert setup_row is not None
            assert tuple(setup_row)[1:] == (
                SYMBOL, TF, "BULLISH", "PAT-WYC-001", 1, "SETUP_ENGINE")

            # A later ingested close crosses the governed target. Calling the
            # runtime manager directly avoids asking a later close to create a
            # second setup while the first position is being flattened.
            await seed_bars(h.store, ("111",), start_ms=START_MS + 25 * HOUR)
            actions = await h.runtime.manage_positions(
                as_of=_ms_to_iso(START_MS + 25 * HOUR))
            assert len(actions) == 1
            assert actions[0]["exit_reason"] == "TARGET_1"
            assert actions[0]["filled"] is True
            assert actions[0]["reconciled"] is True
            assert h.runtime.working == {}
            events = {event.event_type for event in await h.ledger.read_ledger()}
            assert {"TRADE_PLAN", "FILL", "OUTCOME"} <= events
            assert {order["kind"] for order in h.adapter.submitted} >= {
                "entry", "stop", "target", "exit"}
            assert (await h.ledger.verify_chain())["intact"] is True
        finally:
            await shutdown(h)

    run(scenario())


def test_d28_paper_bootstrap_unavailable_components_reach_real_bridge(harness):
    """Only governance is D28-produced; engine/risk values remain test fixtures."""
    from apex.ops import engine_context as EC
    async def scenario():
        h = await harness()
        try:
            await seed_bridge_sweep(h.store)
            bootstrap = EC.paper_bootstrap_inputs(environment="PAPER", family_record=None)
            async def source(symbol, timeframe, as_of):
                context = await bridge_context(h.store, symbol, timeframe, as_of)
                context.update(bootstrap)
                # D27: produced uncertainty, rather than a fixture's old value.
                context["regime_uncertainty"] = EC.regime_uncertainty_input({"probs": [.7] + [.0375] * 8})
                return context
            bridge = PaperPlanBridge(store=h.store, context_source=source)
            plan = await bridge(SYMBOL, TF, _ms_to_iso(START_MS + 24 * HOUR))
            assert plan is not None and not bridge.refusals
            assert plan["environment"] == "PAPER" and plan["package_version"] == "v1.0.0"
            arbitration = bridge.traces[f"{SYMBOL}:{TF}"]["arbitration"]
            candidate = arbitration["ranked"][0]
            assert candidate["family_status"] == "ACCUMULATING"
            assert candidate["composite"]["component_status"]["alignment"] == "UNAVAILABLE"
            assert candidate["composite"]["component_status"]["recency"] == "UNAVAILABLE"
        finally:
            await shutdown(h)
    run(scenario())
