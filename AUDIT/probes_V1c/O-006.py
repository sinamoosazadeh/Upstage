#!/usr/bin/env python3
"""O-006 probe: fact-check the scope/review row against real code/files.
(1) PaperRuntime ctor default max_trades_per_cycle == 4 and the live budget
    refuses the 5th take and releases a slot (D51 semantics, real instance);
(2) params/setup_weights_v1.yaml lines 4-5 hold exactly one family/playbook
    pair and the parsed mapping carries exactly that pair;
(3) PHASE2_HANDOFF_CP9.md carries the D51 note (Python read, no shell grep).
No network; real code and real files only.
"""
import asyncio, inspect, sys, tempfile
from pathlib import Path

ROOT = "/home/user/Upstage"
for p in (ROOT, ROOT + "/tests"):
    if p not in sys.path:
        sys.path.insert(0, p)

from apex.config import _load_yaml

from apex.bus import EventBus
from apex.config import Config
from apex.data_catalog.store import sqlite_store as ss
from apex.ledger import store as LS
from apex.ops import paper_loop as PL
from apex.ops.paper_loop import PaperRuntime
from apex.scheduler import clock as C
from tests.integration.test_ops_paper_loop import (
    START, SYMBOL, TF, FakeAdapter, LedgerClock)

print("== (1) default budget and D51 semantics on a live instance ==")
tmp = Path(tempfile.mkdtemp(prefix="o006-"))

async def main():
    store = ss.SQLiteStore(str(tmp / "apex.sqlite3"))
    await store.open()
    ledger = LS.LedgerWriter(store, clock=LedgerClock())
    await ledger.initialize()
    await ledger.start()
    bus = EventBus()
    bus.start()
    runtime = PaperRuntime(
        config=Config(), store=store, ledger=ledger, bus=bus,
        adapter=FakeAdapter(), clock=C.FixtureClock(START), environment="PAPER",
        cells=[C.BundleCell(SYMBOL, TF)])

    try:
        sig = inspect.signature(PaperRuntime.__init__)
        default_cap = sig.parameters["max_trades_per_cycle"].default
        print(f"ctor default max_trades_per_cycle = {default_cap}")
        print(f"instance max_trades_per_cycle = {runtime.max_trades_per_cycle}")
        takes = [runtime._take_budget() for _ in range(5)]
        print(f"five consecutive _take_budget(): {takes}")
        runtime._release_budget()
        print(f"after one _release_budget(): next take = {runtime._take_budget()}")
        budget_ok = (default_cap == 4 and runtime.max_trades_per_cycle == 4
                     and takes == [True, True, True, True, False])
    finally:
        await bus.stop()
        if not ledger.closed:
            await ledger.stop()
        await store.close()
    return budget_ok

budget_ok = asyncio.run(main())

print()
print("== (2) single family/playbook pair in params/setup_weights_v1.yaml ==")
yaml_path = Path(ROOT) / "params/setup_weights_v1.yaml"
lines = yaml_path.read_text(encoding="utf-8").splitlines()
print(f"line 4: {lines[3]!r}")
print(f"line 5: {lines[4]!r}")
data = _load_yaml("setup_weights")
print(f"parsed: family_id={data['family_id']} playbook_id={data['playbook_id']}")
pair_ok = (lines[3].strip() == "family_id: SF_FVG_SWEEP_REV"
           and lines[4].strip() == "playbook_id: PB_FVG_SWEEP_REV_A"
           and data["family_id"] == "SF_FVG_SWEEP_REV"
           and data["playbook_id"] == "PB_FVG_SWEEP_REV_A")

print()
print("== (3) D51 note in PHASE2_HANDOFF_CP9.md ==")
handoff = (Path(ROOT) / "PHASE2_HANDOFF_CP9.md").read_text(encoding="utf-8")
anchor = None
for i, line in enumerate(handoff.splitlines(), start=1):
    if line.startswith("- D51:"):
        anchor = (i, line)
        break
print(f"'- D51:' found at line {anchor[0]}")
print(f"text: {anchor[1][:150]}")
d51_ok = anchor is not None and "max_trades_per_cycle" in anchor[1] and anchor[0] in (933, 934, 935)

ok = budget_ok and pair_ok and d51_ok
print(f"CLAIMS_REPRODUCED={ok}")
