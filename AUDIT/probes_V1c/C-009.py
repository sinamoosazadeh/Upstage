#!/usr/bin/env python3
"""C-009 probe: battery-guard failures in the FROZEN runner + the wiring layer.

(1) bool("UNPLUGGED") / bool("false") parse as charging: real Termux-shaped
    JSON at 4% unplugged => PROCEED in continuous mode (should be PAUSE, W.6).
(2) run_phase1 only handles PAUSE: with preflight = SKIP_NIGHTLY (proper
    booleans, unplugged, 10%) it still FETCHES and returns status COMPLETE.
(3) read_battery never checks returncode (non-zero exit + valid stdout is
    parsed as if the battery API succeeded).

Real repo code only (apex.research.bootstrap is imported as-is). No network.
Termux format evidence: gotermux docs — plugged is a STRING enum
("UNPLUGGED"/"PLUGGED_AC"/...), matching termux-api's BatteryStatus.
"""
import asyncio, json, subprocess, sys, tempfile
from pathlib import Path

ROOT = "/home/user/Upstage"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from apex.research.bootstrap import (
    BootstrapRunner, hardware_preflight, parse_battery_json, DEEP_START_MS)
from apex.research.checkpoints import ResearchCheckpointStore
from apex.ops.bootstrap_service import read_battery

tmp = Path(tempfile.mkdtemp(prefix="c009-"))

print("== (1) parser truthiness on the real Termux shape ==")
termux_unplugged_4pct = json.dumps({
    "health": "GOOD", "percentage": 4, "plugged": "UNPLUGGED",
    "status": "DISCHARGING", "temperature": 250})
parsed = parse_battery_json(termux_unplugged_4pct)
print(f"parse_battery_json(4%, 'UNPLUGGED') -> {parsed}")
parsed_false = parse_battery_json(json.dumps({"percentage": 10, "plugged": "false"}))
print(f"parse_battery_json(10%, 'false')   -> {parsed_false}")
decision = hardware_preflight(free_disk_mb=10_000.0, battery=parsed,
                              continuous=True)
print(f"preflight(continuous, 4% 'UNPLUGGED' parsed) -> action="
      f"{decision['action']} reason={decision['reason']} "
      f"(W.6 wants PAUSE below 5% unplugged)")
bool_ok_pause = hardware_preflight(free_disk_mb=10_000.0,
                                   battery={"percentage": 4, "plugged": False},
                                   continuous=True)
print(f"control with REAL boolean False 4% -> action={bool_ok_pause['action']} "
      f"reason={bool_ok_pause['reason']}")

print()
print("== (2) run_phase1 ignores SKIP_NIGHTLY ==")
fetch_calls = []

def counting_fetcher(symbol, timeframe, start_ms, end_ms, limit):
    fetch_calls.append((symbol, timeframe, start_ms, end_ms))
    if len(fetch_calls) > 1:
        return {"rows": [], "next_cursor_ms": end_ms, "code": None}
    return {"rows": [{"open_time": start_ms}], "next_cursor_ms": start_ms + 1,
            "code": None}

ingested = []

async def sink(rows, symbol, timeframe):
    ingested.extend(rows)

async def scenario():
    runner = BootstrapRunner(
        fetcher=counting_fetcher, ingest=sink,
        store=ResearchCheckpointStore(path=str(tmp / "cp.sqlite3")),
        cells=[("BTCUSDT", "1h")])
    async with runner.store:
        return await runner.run_phase1(
            battery={"percentage": 10, "plugged": False})   # SKIP_NIGHTLY

result = asyncio.run(scenario())
print(f"battery=10%/False (preflight would say SKIP_NIGHTLY):")
chk = hardware_preflight(free_disk_mb=10_000.0,
                         battery={"percentage": 10, "plugged": False},
                         continuous=False)
print(f"  preflight alone -> action={chk['action']} reason={chk['reason']}")
print(f"  run_phase1      -> status={result['status']} pages={result['pages']} "
      f"completed={result['completed_cells']}")
print(f"  fetch_calls={len(fetch_calls)} ingested_rows={len(ingested)} "
      f"(W.6 wants the nightly run SKIPPED: 0 fetches, no COMPLETE)")

print()
print("== (3) read_battery ignores returncode ==")
class FakeCompleted:
    def __init__(self, rc, out):
        self.returncode = rc
        self.stdout = out

def failing_runner(cmd):
    return FakeCompleted(1, json.dumps({"percentage": 3, "plugged": "UNPLUGGED"}))

battery = read_battery(runner=failing_runner)
print(f"termux exits rc=1 but prints valid JSON -> read_battery -> {battery} "
      f"(parsed anyway; returncode never read)")

ok = (parsed == {"percentage": 4, "plugged": True}
      and parsed_false == {"percentage": 10, "plugged": True}
      and decision["action"] == "PROCEED"
      and result["status"] == "COMPLETE"
      and len(fetch_calls) > 0
      and battery == {"percentage": 3, "plugged": True})
print(f"CLAIMS_REPRODUCED={ok}")
