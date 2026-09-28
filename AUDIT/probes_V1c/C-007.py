#!/usr/bin/env python3
"""C-007 probe: a REFUSED submission (nothing leaves the process) completes the
execution stage WITHOUT an exception -> the cell is COMPLETE and shows up in
cycle['trades'] / len(self.trades), although no order was ever submitted or
filled. Also: _serve's exit code reads only boot['boot_state'] (code citation:
scripts/run_apex.py:806), not the unhealthy outcome.

Real code only (PaperRuntime + ExecutionFSM + frozen store/ledger). No network.
The REFUSED AdapterResult shape mirrors apex/execution/toobit_adapter.py:829-835.
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
    START, START_MS, HOUR, SYMBOL, TF, FakeAdapter, LedgerClock,
    adapter_result, plan_mapping, seed_bars, seed_setup)

tmp = Path(tempfile.mkdtemp(prefix="c007-"))


class RefusingAdapter(FakeAdapter):
    """Every entry submission is refused by the adapter's own guard BEFORE the
    exchange sees it (classification=REFUSED, outcome=REJECTED — the shape
    toobit_adapter.py:829-835 produces)."""
    async def submit_order(self, **kwargs):
        return adapter_result(ok=False, outcome="REJECTED",
                              classification="REFUSED",
                              error_code="GUARD_REFUSED_DEMO")


async def main():
    store = ss.SQLiteStore(str(tmp / "apex.sqlite3"))
    await store.open()
    ledger = LS.LedgerWriter(store, clock=LedgerClock())
    await ledger.initialize()
    await ledger.start()
    clock = C.FixtureClock(START)
    adapter = RefusingAdapter()
    bus = EventBus()
    bus.start()
    await seed_setup(store, "setup-0001")
    runtime = PL.PaperRuntime(
        config=Config(), store=store, ledger=ledger, bus=bus,
        adapter=adapter, clock=clock, environment="PAPER",
        cells=[C.BundleCell(SYMBOL, TF)], notifier=None,
        plan_provider=lambda s, t, a: plan_mapping())
    try:
        verdict = await runtime.boot(drift_seconds=0.0)
        await seed_bars(store, ("100", "105"))
        cycle = await runtime.run_cycle(now_ms=START_MS + HOUR)
        print(f"boot_state={verdict['boot_state']}")
        print(f"cycle: due={cycle['cells_due']} complete={cycle['cells_complete']} "
              f"halted={cycle['cells_halted']} halt_reasons={cycle['halt_reasons']}")
        print(f"len(cycle['trades'])={len(cycle['trades'])} "
              f"(these are COMPLETE CellRuns, not fills)")
        trade = runtime.trades[-1] if runtime.trades else None
        print(f"runtime.trades[-1]: submitted={trade['submitted'] if trade else '-'} "
              f"outcome={trade['outcome'] if trade else '-'} "
              f"reason={trade['reason'] if trade else '-'} "
              f"fill={trade['fill'] if trade else '-'} state={trade['state'] if trade else '-'}")
        print(f"refusals recorded: {len(runtime.refusals)}")
        print(f"adapter real round-trips: submitted={adapter.submitted} "
              f"queries={adapter.queries}")

        async def _no_sleep(_: float) -> None:
            return None
        outcome = await runtime.run(cycles=1, interval=0, sleep=_no_sleep)
        print(f"run() outcome: cycles={outcome['cycles']} trades={outcome['trades']} "
              f"refusals={outcome['refusals']} open={outcome['open_intents']} "
              f"boot_state={outcome['boot_state']} chain={outcome['ledger_chain_intact']}")
        print(f"-> outcome['trades']=={outcome['trades']} although 0 orders left the process")
        print(f"serve exit rule (code, run_apex.py:806): EXIT_READY iff "
              f"boot['boot_state']=='READY' -> here {verdict['boot_state']!r} => EXIT_READY "
              f"regardless of refusals={outcome['refusals']}")
        ok = (cycle['cells_complete'] == 1 and cycle['cells_halted'] == 0
              and trade is not None and trade['submitted'] is False
              and adapter.submitted == [] and outcome['trades'] == 1)
        print(f"CLAIM_REPRODUCED={ok}")
    finally:
        await bus.stop()
        if not ledger.closed:
            await ledger.stop()
        await store.close()

asyncio.run(main())
