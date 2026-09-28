#!/usr/bin/env python3
"""C-014 probe: after a >24h pause, `resume` only returns a flag and clears
paused_at immediately; nothing persists the recheck requirement and
run_phase1 has no health gate before fetching.

Contract: APEX_GEN5.md:17316 (W.8-3): "After pause duration exceeds 24 hours,
before resume, re-run health check on downloaded data (detect stale feeds,
re-sync as needed)."
Real code only. No network.
"""
import asyncio, sys, tempfile
from pathlib import Path

ROOT = "/home/user/Upstage"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from apex.research.bootstrap import BootstrapRunner
from apex.research.checkpoints import ResearchCheckpointStore

tmp = Path(tempfile.mkdtemp(prefix="c014-"))
clock = {"now": 1767225600.0}  # 2026-01-01T00:00:00Z (realistic epoch > DEEP_START)
fetch_calls = []

def counting_fetcher(symbol, timeframe, start_ms, end_ms, limit):
    fetch_calls.append(start_ms)
    if len(fetch_calls) > 1:
        return {"rows": [], "next_cursor_ms": end_ms, "code": None}
    return {"rows": [{"open_time": start_ms}], "next_cursor_ms": start_ms + 1,
            "code": None}

async def sink(rows, symbol, timeframe):
    return None

async def main():
    runner = BootstrapRunner(
        fetcher=counting_fetcher, ingest=sink,
        store=ResearchCheckpointStore(path=str(tmp / "cp.sqlite3")),
        cells=[("BTCUSDT", "1h")], now=lambda: clock["now"])
    runner.command("start")
    runner.command("pause")
    print(f"paused_at recorded at now={clock['now']}")
    clock["now"] += 25 * 3600          # 25 hours later (> 24 h threshold)

    print(f"health_recheck_required() BEFORE resume: "
          f"{runner.health_recheck_required()}")
    verdict = runner.command("resume")
    print(f"command('resume') -> accepted={verdict['accepted']} "
          f"health_recheck={verdict['health_recheck']}")
    print(f"health_recheck_required() AFTER resume: "
          f"{runner.health_recheck_required()}  (paused_at was cleared)")
    print(f"state.paused={runner.state.paused} state.paused_at={runner.state.paused_at}")

    async with runner.store:
        result = await runner.run_phase1()
    print(f"run_phase1 right after resume (no recheck executed anywhere): "
          f"status={result['status']} completed={result['completed_cells']} "
          f"fetch_calls={len(fetch_calls)}")
    print(f"grep check: 'health' appears nowhere inside run_phase1 "
          f"(W.8-3 wants the re-check BEFORE resuming the walk)")
    ok = (verdict["health_recheck"]["required"] is True
          and runner.health_recheck_required()["reason"] == "NO_PAUSE_RECORDED"
          and result["status"] == "COMPLETE" and len(fetch_calls) > 0)
    print(f"CLAIM_REPRODUCED={ok}")

asyncio.run(main())
