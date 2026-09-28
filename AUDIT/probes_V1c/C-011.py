#!/usr/bin/env python3
"""C-011 probe: _percent says 100% on a FRESH runner (current_cell=None), and
the cells*8 denominator caps out at 100% after cells*8 pages while many cells
are still pending. ETA needs command('start') to get a clock. Real code only.
"""
import asyncio, sys, tempfile
from pathlib import Path

ROOT = "/home/user/Upstage"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from apex.data_catalog.contracts import CORE10_SYMBOLS, TIMEFRAMES_14
from apex.research.bootstrap import BootstrapRunner, DEEP_START_MS
from apex.research.checkpoints import ResearchCheckpointStore

tmp = Path(tempfile.mkdtemp(prefix="c011-"))
CELLS = [(s, t) for s in CORE10_SYMBOLS for t in TIMEFRAMES_14]   # the 140

def no_fetch(s, t, a, b, l):
    return {"rows": [], "next_cursor_ms": b, "code": None}

async def sink(rows, symbol, timeframe):
    return None

print("== (a) fresh runner, zero pages, zero checkpoints ==")
store = ResearchCheckpointStore(path=str(tmp / "cp.sqlite3"))
runner = BootstrapRunner(fetcher=no_fetch, ingest=sink, store=store, cells=CELLS)
p = runner.progress()
print(f"current_cell={p['current_cell']} pages_fetched={p['pages_fetched']} "
      f"percent_complete={p['percent_complete']}  <- fresh run reports 100%")

print()
print("== (b) mid-run: pages_fetched=1120 (=140*8), cells barely started ==")
runner.state.started = True
runner.state.current_cell = "BTCUSDT:1h"
runner.state.pages_fetched = 1120
p2 = runner.progress()
print(f"pages_fetched=1120 cells=140 -> percent_complete={p2['percent_complete']}")

async def pendings():
    async with store:
        return await runner.pending_cells()
pending = asyncio.run(pendings())
print(f"pending_cells at that moment: {len(pending)} of 140")
runner.state.pages_fetched = 560
print(f"pages=560 (50% of the guess) -> percent_complete={runner.progress()['percent_complete']}")

print()
print("== (c) ETA basis ==")
eta_fresh = runner.eta()
print(f"eta() before any command('start'): basis={eta_fresh['basis']} "
      f"measured={eta_fresh['measured']} eta_seconds={eta_fresh['eta_seconds']}")
runner.state.pages_fetched = 10        # pages exist, but no start command yet
eta_no_start = runner.eta()
print(f"eta() with 10 pages but started_at=None: basis={eta_no_start['basis']} "
      f"measured={eta_no_start['measured']}")
runner.command("start")
runner.state.pages_fetched = 20
eta_after = runner.eta()
print(f"eta() after command('start'): measured={eta_after['measured']} "
      f"seconds_per_page={eta_after['seconds_per_page']:.4f}")

ok = (p["percent_complete"] == 100.0
      and p2["percent_complete"] == 100.0
      and len(pending) == 140
      and eta_fresh["measured"] is False
      and eta_no_start["measured"] is False)
print(f"CLAIM_REPRODUCED={ok}")
