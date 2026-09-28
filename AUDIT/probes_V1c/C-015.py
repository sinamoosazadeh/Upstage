#!/usr/bin/env python3
"""C-015 probe: a pre-send exception after _take_budget() leaks the cycle slot
(no release on the exception path), so another healthy cell of the SAME cycle
dies with TRADE_BUDGET_REACHED without execute_plan ever being called.

D51 (PHASE2_DECISION_LOG.md:1161): "A submission that does not leave the
process releases the slot." Real code only. No network.
"""
import asyncio, sys, tempfile
from pathlib import Path

ROOT = "/home/user/Upstage"
for p in (ROOT, ROOT + "/tests"):
    if p not in sys.path:
        sys.path.insert(0, p)

from apex.bus import EventBus
from apex.config import Config
from apex.data_catalog.store import sqlite_store as ss
from apex.ledger import store as LS
from apex.ops import paper_loop as PL
from apex.scheduler import clock as C
from tests.integration.test_ops_paper_loop import (
    START, START_MS, HOUR, SYMBOL, TF, FakeAdapter, LedgerClock, plan_mapping,
    seed_bars, seed_setup, _ms_to_iso)

tmp = Path(tempfile.mkdtemp(prefix="c015-"))


class RaisingAdapter(FakeAdapter):
    """submit raises OSError BEFORE any venue round-trip (synthetic pre-send
    failure trigger — same trigger the auditor used)."""
    async def submit_order(self, **kwargs):
        raise OSError("simulated pre-send transport failure (no bytes sent)")


async def main():
    store = ss.SQLiteStore(str(tmp / "apex.sqlite3"))
    await store.open()
    ledger = LS.LedgerWriter(store, clock=LedgerClock())
    await ledger.initialize()
    await ledger.start()
    clock = C.FixtureClock(START)
    adapter = RaisingAdapter()
    bus = EventBus()
    bus.start()
    await seed_setup(store, "setup-0001")
    runtime = PL.PaperRuntime(
        config=Config(), store=store, ledger=ledger, bus=bus,
        adapter=adapter, clock=clock, environment="PAPER",
        cells=[C.BundleCell(SYMBOL, TF)], notifier=None,
        max_trades_per_cycle=1,
        plan_provider=lambda s, t, a: plan_mapping())
    try:
        verdict = await runtime.boot(drift_seconds=0.0)
        print(f"boot_state={verdict['boot_state']} trading_enabled={runtime.trading_enabled}")
        await seed_bars(store, ("100", "105"))

        # --- Cycle 1: cell takes the only budget slot, then OSError pre-send
        cycle1 = await runtime.run_cycle(now_ms=START_MS + HOUR)
        last = runtime.scheduler.runs[-1]
        print(f"cycle1: due={cycle1['cells_due']} halted={cycle1['cells_halted']} "
              f"status={last.status} reason={last.reason}")
        print(f"cycle1 failed-stage detail: {last.stages[-1].detail!r}")
        print(f"budget after cycle1: _budget_taken={runtime._budget_taken} "
              f"(D51 says a not-sent submission releases the slot -> expected 0)")
        plans = await runtime.plans.counts()
        print(f"materialized trade_plan rows after cycle1: {plans}")
        ledger_types = [e.event_type for e in await ledger.read_ledger()]
        print(f"ledger events cycle1: {ledger_types}")

        # --- A SECOND healthy cell of the SAME cycle now competes for the slot
        await seed_setup(store, "setup-0002")
        plan2 = PL.normalize_plan(plan_mapping(
            proposal_id="0199c0de-0000-7000-8000-000000000002",
            setup_id="setup-0002"))
        payload2 = {"cell_id": "ETHUSDT:1h", "symbol": "ETHUSDT",
                    "timeframe": TF, "as_of": _ms_to_iso(START_MS + HOUR),
                    "close_ms": START_MS + HOUR,
                    "context": {"cell_state": {"plan_obj": plan2}}}
        try:
            await runtime._stage_execution(payload2)
            print("cell2 _stage_execution: UNEXPECTEDLY succeeded")
        except PL.CellRefusal as exc:
            print(f"cell2 _stage_execution: CellRefusal reason={exc.reason} "
                  f"detail={exc.detail}")
        print(f"adapter submit calls so far: BTC attempt={adapter.submitted} "
              f"(empty: the venue never saw anything; ETH never tried)")
        cursor = await PL.load_cell_cursor(store.db)
        print(f"cursor after cycle1: {cursor}  (BTC close locked despite HALT)")

        # --- Cycle 2 (next close): D51 resets the budget at cycle start
        fresh = PL.PaperRuntime(
            config=Config(), store=store, ledger=ledger, bus=bus,
            adapter=FakeAdapter(), clock=clock, environment="PAPER",
            cells=[C.BundleCell("ETHUSDT", TF)], notifier=None,
            max_trades_per_cycle=1,
            plan_provider=lambda s, t, a: plan_mapping(
                proposal_id="0199c0de-0000-7000-8000-000000000002",
                setup_id="setup-0002"))
        await fresh.boot(drift_seconds=0.0)
        from decimal import Decimal
        from tests.integration.test_ops_paper_loop import observation
        from dataclasses import replace
        await store.ingest_raw(replace(observation("10", START_MS), symbol="ETHUSDT", oi=Decimal("5")), "AVAILABLE")
        await store.ingest_raw(replace(observation("11", START_MS + HOUR), symbol="ETHUSDT", oi=Decimal("5")), "AVAILABLE")
        cycle2 = await fresh.run_cycle(now_ms=START_MS + 2 * HOUR)
        print(f"cycle2 fresh budget: halt_reasons={cycle2['halt_reasons']} "); print(f"cycle2 fresh budget: complete={cycle2['cells_complete']} "
              f"halted={cycle2['cells_halted']} _budget_taken={fresh._budget_taken}")
        chain = await ledger.verify_chain()
        print(f"ledger chain intact: {chain['intact']}")

        ok = (runtime._budget_taken == 1 and last.status == "HALTED"
              and "OSError" in last.stages[-1].detail
              and adapter.submitted == [])
        print(f"CLAIM_REPRODUCED={ok}")
    finally:
        await bus.stop()
        if not ledger.closed:
            await ledger.stop()
        await store.close()

asyncio.run(main())
