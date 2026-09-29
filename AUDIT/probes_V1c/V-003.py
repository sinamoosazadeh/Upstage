#!/usr/bin/env python3
"""V-003 probe: verify the audited wiring claims with real code.
A. paper_loop run_cycle calls plan_provider.prepare per due cell OUTSIDE the
   trade budget (paper_loop.py:1008-1027), counts them, and records failures
   per cell via reason code.
B. PaperPlanBridge.prepare is PAPER-only and never builds plans;
   __call__ is PAPER-only + universe-gated + fail-closed without context
   (plan_bridge.py:530-559).
C. REQUIRED_CONTEXT_KEYS == 38 and REQUIRED_RISK_KEYS == 23.
D. bridge._build runs its REAL validation/fabric/conflict/context code and
   invokes the stage authorities (build_forecast, evaluate_cell, adjudicate,
   build_trade_plan) in order. Only the downstream stage bodies are spies
   with canned returns; every bridge validation/fabric/conflict line ahead
   of and between the stages runs for real.
No network; tmp SQLite store; real modules only.
"""
import asyncio, sys, tempfile, types
from pathlib import Path

ROOT = "/home/user/Upstage"
for p in (ROOT, ROOT + "/tests"):
    if p not in sys.path:
        sys.path.insert(0, p)

import apex.ops.plan_bridge as PB
from apex.bus import EventBus
from apex.config import Config
from apex.data_catalog.store import sqlite_store as ss
from apex.ledger import store as LS
from apex.ops import paper_loop as PL
from apex.scheduler import clock as C
from tests.integration.test_ops_paper_loop import (
    HOUR, START, START_MS, SYMBOL, TF, FakeAdapter, LedgerClock, seed_bars,
    seed_setup)

AS_OF = "2025-03-07T21:00:00.000Z"
CALLS = []

def spy(name, ret):
    def _wrapped(*a, **k):
        CALLS.append(name)
        return ret
    return _wrapped

async def open_stack(tmp):
    store = ss.SQLiteStore(str(tmp / "apex.sqlite3"))
    await store.open()
    ledger = LS.LedgerWriter(store, clock=LedgerClock())
    await ledger.initialize()
    await ledger.start()
    bus = EventBus()
    bus.start()
    return store, ledger, bus

async def close_stack(store, ledger, bus):
    await bus.stop()
    if not ledger.closed:
        await ledger.stop()
    await store.close()

async def part_a():
    print("== A: run_cycle calls plan_provider.prepare outside the trade budget ==")
    tmp = Path(tempfile.mkdtemp(prefix="v003-a1-"))
    store, ledger, bus = await open_stack(tmp)
    prepare_calls, provider_calls = [], []

    class SpyProvider:
        async def prepare(self, symbol, timeframe, as_of):
            prepare_calls.append((symbol, timeframe))
        async def __call__(self, symbol, timeframe, as_of):
            provider_calls.append((symbol, timeframe))
            return None  # no plan -> named refusal; budget untouched

    runtime = PL.PaperRuntime(
        config=Config(), store=store, ledger=ledger, bus=bus,
        adapter=FakeAdapter(), clock=C.FixtureClock(START), environment="PAPER",
        cells=[C.BundleCell(SYMBOL, TF)], plan_provider=SpyProvider())
    try:
        await runtime.boot(drift_seconds=0.0)
        await seed_bars(store, ("100", "105"))
        budget_before = runtime._budget_taken
        cycle = await runtime.run_cycle(now_ms=START_MS + HOUR)
        prep = cycle["context_preparation"]
        print(f"prepare_calls={prepare_calls} provider_calls={provider_calls}")
        print(f"context_preparation={prep}")
        print(f"budget taken: before={budget_before} after={runtime._budget_taken}")
        a1 = (prepare_calls and prep["cells_prepared"] == 1
              and prep["cells_checked"] == 1 and not prep["failures"]
              and runtime._budget_taken == 0 and cycle["trades"] == [])
        print(f"A1 (prepare per due cell, budget untouched) PASS={a1}")
    finally:
        await close_stack(store, ledger, bus)

    tmp2 = Path(tempfile.mkdtemp(prefix="v003-a2-"))
    store2, ledger2, bus2 = await open_stack(tmp2)

    class FailProvider:
        async def prepare(self, symbol, timeframe, as_of):
            raise PB.BridgeError("ENGINE_CONTEXT_INVALID", "probe fake failure")
        async def __call__(self, symbol, timeframe, as_of):
            return None

    runtime2 = PL.PaperRuntime(
        config=Config(), store=store2, ledger=ledger2, bus=bus2,
        adapter=FakeAdapter(), clock=C.FixtureClock(START), environment="PAPER",
        cells=[C.BundleCell(SYMBOL, TF)], plan_provider=FailProvider())
    try:
        await runtime2.boot(drift_seconds=0.0)
        await seed_bars(store2, ("100", "105"))
        cycle2 = await runtime2.run_cycle(now_ms=START_MS + HOUR)
        prep2 = cycle2["context_preparation"]
        print(f"failure case: context_preparation={prep2}")
        print(f"runtime._context_preparation_failed="
              f"{runtime2._context_preparation_failed}")
        a2 = (prep2["cells_checked"] == 1 and prep2["cells_prepared"] == 0
              and prep2["failures"]
              and prep2["failures"][0]["reason"] == "ENGINE_CONTEXT_INVALID"
              and prep2["failures"][0]["cell"]
              in runtime2._context_preparation_failed)
        print(f"A2 (prepare failure recorded fail-closed) PASS={a2}")
    finally:
        await close_stack(store2, ledger2, bus2)
    return a1 and a2

async def part_b(store):
    print()
    print("== B: bridge guard layers (prepare PAPER-only, no plan build) ==")
    orig = PB.build_trade_plan
    PB.build_trade_plan = spy("build_trade_plan", None)
    try:
        bridge = PB.PaperPlanBridge(
            store=store, environment="PAPER",
            context_preparer=lambda s, t, a: CALLS.append("context_preparer"))
        await bridge.prepare(SYMBOL, TF, AS_OF)
        b1 = CALLS.count("context_preparer") == 1
        print(f"prepare() delegated to producer preparer; "
              f"build_trade_plan calls={CALLS.count('build_trade_plan')}")
        try:
            live = PB.PaperPlanBridge(store=store, environment="LIVE",
                                      context_preparer=lambda s, t, a: None)
            await live.prepare(SYMBOL, TF, AS_OF)
            b2 = False
            print("LIVE prepare accepted unexpectedly")
        except PB.BridgeError as exc:
            print(f"LIVE prepare refused with reason={exc.reason}")
            b2 = exc.reason == "PAPER_ONLY_EXECUTION"
        ret3 = await bridge("NOPE", TF, AS_OF)
        refusal3 = bridge.refusals.get("NOPE:1h") or bridge.refusals.get("NOPE:" + TF)
        print(f"out-of-universe call -> return={ret3} refusal={refusal3}")
        b3 = (ret3 is None and isinstance(refusal3, dict)
              and refusal3["reason"] == "CELL_OUT_OF_UNIVERSE")
        lonely = PB.PaperPlanBridge(store=store, environment="PAPER")
        ret4 = await lonely(SYMBOL, TF, AS_OF)
        refusal4 = lonely.refusals.get(f"{SYMBOL}:{TF}")
        print(f"context-less call -> return={ret4} refusal={refusal4}")
        b4 = (ret4 is None and isinstance(refusal4, dict)
              and refusal4["reason"] == "ENGINE_CONTEXT_UNAVAILABLE")
        b5 = CALLS.count("build_trade_plan") == 0
        ok = b1 and b2 and b3 and b4 and b5
        print(f"B PASS={ok} (delegation={b1} LIVE-refusal={b2} universe={b3} "
              f"fail-closed={b4} plan-free-prepare={b5})")
        return ok
    finally:
        PB.build_trade_plan = orig

def make_context():
    components = ("structure", "liquidity", "fvg", "trend", "regime",
                  "temporal")
    return {
        "events": [{"evidence_id": "ev1", "engine_id": "E01", "direction": 1,
                    "quality": 0.95, "resolution_class": "Q2",
                    "snapshot_id": "snap1", "lineage": ["o-raw-1"],
                    "state": "ACTIVE", "age": 0.0,
                    "availability_time": "2025-03-07T20:55:00.000Z"}],
        "raw_observation_ids": ["o-raw-1"],
        "data_trust": 0.9, "q_raw": 0.9,
        "market_regime": "TREND", "mtf_state": "ALIGNED",
        "utc_window_state": "UTC_W2", "is_overlap": True,
        "volatility_state": "NORMAL", "structure_state": "BOS_UP",
        "regime_confidence": 0.7, "regime_uncertainty": 0.2,
        "divergence_magnitude": 0.1, "temporal_window_validity": 0.9,
        "atr": 5.0,
        "fvg_zones": [{"low": 98.0, "high": 99.5, "filled": False}],
        "bos": {"s_struct": 0.6, "direction": 1},
        "regime_state": "TREND",
        "e11_context": {"ic_inputs": {"trendiness_raw": 0.7},
                        "history_windows": {"trend": [0.5]},
                        "classifier_W": [[0.0] * 8 for _ in range(9)],
                        "classifier_b": [0.0] * 9,
                        "regime_state": "TREND"},
        "direction": 1, "pattern_id": "PAT-WYC-001",
        "x": {"s_struct": 0.5}, "forecast_quality": "Q3",
        "forecast_rr": 3.0, "forecast_cost_r": 0.05,
        "forecast_uncertainty": {"calibration": 0.2, "data_quality": 0.2,
                                 "disagreement": 0.2},
        "window_qualities": [(1.0, 0.0)],
        "temporal_quality": "Q2", "volatility_quality": "Q2",
        "s_i": {key: 1.0 for key in components},
        "q_i": {key: 0.9 for key in components},
        "package": {"package_version": 1, "parameter_package_id": "pkg-1",
                    "calibration": "BOOTSTRAP_UNCALIBRATED"},
        "p_min_tf": 0.5, "c_min": 0.5, "freshness_ok": True,
        "risk": {k: (False if k in ("circuit_breaker_engaged", "emergency_state",
                                    "is_risk_increase", "uncertainty_is_rising")
                     else "LowRisk" if k == "risk_state" else 1.0)
                 for k in PB.REQUIRED_RISK_KEYS},
        "risk_state": "LowRisk", "h_norm": 0.4,
        "family_status": "ACTIVE",
        "arbitration": {"composite_weights": {"alignment": 0.5, "recency": 0.5},
                        "quality": 0.9, "alignment": 0.9, "recency": 0.9},
        "risk_transport": {},
        "bars": [{"timestamp": "2025-03-07T20:00:00.000Z",
                  "open": 99.0, "high": 100.5, "low": 98.5,
                  "close": 100.0, "volume": 5.0, "status": "CLOSED"}],
    }

async def part_d(store):
    print()
    print("== D: _build invokes stage authorities in order (real validation) ==")
    CALLS.clear()
    forecast_obj = types.SimpleNamespace(
        bootstrap_prior=True, q_forecast=0.7, p_hat=0.6, c=0.8, u=0.1,
        cost_r=0.01, r_penalty=0.0, to_dict=lambda: {"p_hat": 0.6})
    eval_obj = types.SimpleNamespace(
        status=PB.EMITTED, reason="ALL_GATES_PASS",
        gate_block={"all_pass": True, "results": {10: {"passed": True}}},
        entry_logic_steps={"2_3_sweep_reclaim": {"extreme": 95.0}},
        entry=100.0, final_score=0.8, q_min_setup=0.55,
        fabric_hash="fab_deadbeef",
        to_setup_event=lambda: {"setup_id": "su_probe", "payload": {}})
    stage_fakes = {
        "build_forecast": forecast_obj,
        "evaluate_cell": eval_obj,
        "instantiate_playbook": types.SimpleNamespace(
            regime_window=("TREND",), to_dict=lambda: {"playbook": "fake"}),
        "build_stops": {"stop": 97.0, "target": 109.0, "R": 3.0},
        "eligibility": {"eligible": True, "failed": []},
        "generate_candidates": [{"side": "LONG"}],
        "rank": [{"side": "LONG"}],
        "select": {"side": "LONG"},
        "arbitrate": {"proposal": {"x": 1}, "reason": {"decision": "TRADE"}},
        "build_proposal": {"proposal_id": "pr_probe"},
        "adjudicate": {"sizing": {"risk_state": "NORMAL"}},
        "build_trade_plan": types.SimpleNamespace(
            to_dict=lambda: {"plan_id": "plan_probe"}),
    }
    originals = {name: getattr(PB, name) for name in stage_fakes}
    for name, fake in stage_fakes.items():
        setattr(PB, name, spy(name, fake))

    materialized = []
    orig_mat = PB.PaperPlanBridge._materialize_setup
    async def mat_spy(self, event, *, pattern_id, regime):
        materialized.append((pattern_id, regime))
    PB.PaperPlanBridge._materialize_setup = mat_spy
    try:
        bridge = PB.PaperPlanBridge(store=store, environment="PAPER")
        result = await bridge._build(make_context(), symbol=SYMBOL,
                                     timeframe=TF, as_of=AS_OF)
    except PB.BridgeError as exc:
        print(f"_build refused (real validation) before stages: "
              f"{exc.reason}: {exc.detail}")
        print(f"stage calls so far: {CALLS}")
        raise
    finally:
        for name, fn in originals.items():
            setattr(PB, name, fn)
        PB.PaperPlanBridge._materialize_setup = orig_mat
    print(f"stage call order: {CALLS}")
    print(f"plan returned: {result}")
    print(f"traces recorded: {list(bridge.traces)} "
          f"materialize_setup calls: {materialized}")
    seq = ["build_forecast", "evaluate_cell", "instantiate_playbook",
           "build_stops", "eligibility", "generate_candidates", "rank",
           "select", "arbitrate", "build_proposal", "adjudicate",
           "build_trade_plan"]
    ok = CALLS == seq and len(materialized) == 1
    print(f"D PASS={ok}")
    return ok

async def main():
    a = await part_a()
    print()
    print("== C: context/risk key counts ==")
    c_ok = (len(PB.REQUIRED_CONTEXT_KEYS) == 38
            and len(PB.REQUIRED_RISK_KEYS) == 23)
    print(f"REQUIRED_CONTEXT_KEYS={len(PB.REQUIRED_CONTEXT_KEYS)} "
          f"REQUIRED_RISK_KEYS={len(PB.REQUIRED_RISK_KEYS)} -> PASS={c_ok}")
    tmp3 = Path(tempfile.mkdtemp(prefix="v003-bd-"))
    store, ledger, bus = await open_stack(tmp3)
    try:
        b = await part_b(store)
        d = await part_d(store)
    finally:
        await close_stack(store, ledger, bus)
    ok = a and b and c_ok and d
    print(f"CLAIMS_REPRODUCED={ok}")

asyncio.run(main())
