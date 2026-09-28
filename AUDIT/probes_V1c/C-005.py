#!/usr/bin/env python3
"""C-005 probe: the D50 cell_decision_cursor advances even for HALTED cells
(only catch-up / context-preparation failures are exempted), so a halted close
(e.g. BOOT_NOT_READY) is never re-decided until the NEXT TF boundary.

Real code only: apex.ops.paper_loop + apex.scheduler.clock + the frozen
SQLiteStore/LedgerWriter. No network. Fixture clock + FakeAdapter test double.
"""
import asyncio, sys, tempfile
from decimal import Decimal
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
    START, START_MS, HOUR, SYMBOL, TF, FakeAdapter, LedgerClock, observation,
    plan_mapping, seed_bars, seed_setup, _ms_to_iso)

tmp = Path(tempfile.mkdtemp(prefix="c005-"))

async def main():
    store = ss.SQLiteStore(str(tmp / "apex.sqlite3"))
    await store.open()
    ledger = LS.LedgerWriter(store, clock=LedgerClock())
    await ledger.initialize()
    await ledger.start()
    clock = C.FixtureClock(START)
    adapter = FakeAdapter()
    bus = EventBus()
    bus.start()
    await seed_setup(store, "setup-0001")
    runtime = PL.PaperRuntime(
        config=Config(), store=store, ledger=ledger, bus=bus,
        adapter=adapter, clock=clock, environment="PAPER",
        cells=[C.BundleCell(SYMBOL, TF)], notifier=None,
        plan_provider=lambda s, t, a: plan_mapping())

    try:
        # ---- Phase 1: boot NOT READY (drift unmeasurable -> new_trades_allowed False)
        verdict = await runtime.boot(drift_seconds=None)
        print(f"phase1 boot_state={verdict['boot_state']} "
              f"new_trades_allowed={verdict['new_trades_allowed']}")
        await seed_bars(store, ("100", "105"))
        cycle1 = await runtime.run_cycle(now_ms=START_MS + HOUR)
        print(f"phase1 cycle1: due={cycle1['cells_due']} complete={cycle1['cells_complete']} "
              f"halted={cycle1['cells_halted']} halted_reasons={cycle1['halt_reasons']}")
        cursor1 = await PL.load_cell_cursor(store.db)
        print(f"phase1 cursor after HALTED cell: {cursor1} "
              f"(expected close_ms={START_MS + HOUR})")
        print(f"phase1 adapter submissions: {len(adapter.submitted)}")
        print(f"phase1 runtime.trades: {runtime.trades}")

        # ---- Phase 2: re-boot to READY and run the SAME close again
        verdict2 = await runtime.boot(drift_seconds=0.0)
        print(f"phase2 boot_state={verdict2['boot_state']} "
              f"new_trades_allowed={verdict2['new_trades_allowed']}")
        cycle2 = await runtime.run_cycle(now_ms=START_MS + HOUR)
        print(f"phase2 cycle2 SAME close: due={cycle2['cells_due']} "
              f"skipped_already_decided={cycle2['cells_skipped_already_decided']} "
              f"halted={cycle2['cells_halted']} complete={cycle2['cells_complete']}")
        print(f"phase2 adapter submissions: {len(adapter.submitted)} "
              f"(0 == the halted close was never reconsidered)")
        submissions_after_phase2 = len(adapter.submitted)

        # ---- Phase 3: the NEXT close runs normally again
        await seed_bars(store, ("110",), start_ms=START_MS + 2 * HOUR)
        cycle3 = await runtime.run_cycle(now_ms=START_MS + 2 * HOUR)
        print(f"phase3 cycle3 NEXT close: due={cycle3['cells_due']} "
              f"halted_reasons={cycle3['halt_reasons']} complete={cycle3['cells_complete']}")
        cursor3 = await PL.load_cell_cursor(store.db)
        print(f"phase3 cursor: {cursor3}")

        ok = (cycle1['cells_halted'] == 1
              and cursor1.get(f"{SYMBOL}:{TF}") == START_MS + HOUR
              and cycle2['cells_due'] == 0
              and cycle2['cells_skipped_already_decided'] == 1
              and submissions_after_phase2 == 0)
        print(f"CLAIM_REPRODUCED={ok}")
    finally:
        await bus.stop()
        if not ledger.closed:
            await ledger.stop()
        await store.close()

asyncio.run(main())
