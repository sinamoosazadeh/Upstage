"""K-016 — page delivery high-water mark survives a failed ingest.

Real `ToobitKlineSource` (with the real `set_frontiers` handoff the service
performs), real `BootstrapRunner.run_phase1`, real `ResearchCheckpointStore`
and real `SQLiteStore.ingest_raw`. The only injected fault is an ingest that
raises on the third row of the page — modelling any per-row failure of the
per-row-committing `ingest_observations` loop.

Run: python3 -B AUDIT/probes_V3b/K-016.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.data_catalog.ingest.toobit_public import (                  # noqa: E402
    parse_kline_to_observation)
from apex.data_catalog.store.sqlite_store import SQLiteStore          # noqa: E402
from apex.ops import bootstrap_service as BS                          # noqa: E402
from apex.research.bootstrap import BootstrapRunner, DEEP_START_MS    # noqa: E402
from apex.research.checkpoints import ResearchCheckpointStore         # noqa: E402

OUT = Path(__file__).with_suffix(".out")
HOUR = 3_600_000
NOW_MS = 1_726_444_800_000
SERIES = [NOW_MS - 2 * HOUR, NOW_MS - HOUR, NOW_MS]


class Venue:
    """Three retained closed bars, endTime honoured."""

    async def get_klines(self, symbol, interval, start_ms, end_ms, limit=None):
        out = []
        for i, open_ms in enumerate([ms for ms in SERIES if ms <= int(end_ms)]):
            row = [open_ms, "1", "1", "1", "1", "1", open_ms + HOUR - 1]
            out.append(parse_kline_to_observation(symbol, interval, row, i))
        return out


async def main() -> None:
    lines = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        lines.append(msg)

    tmp = tempfile.mkdtemp()
    store = await SQLiteStore(os.path.join(tmp, "raw.db")).open()
    checkpoints = await ResearchCheckpointStore(
        os.path.join(tmp, "ck.db")).open()
    bridge = BS.AsyncBridge().start()
    source = BS.ToobitKlineSource(client=Venue(), bridge=bridge,
                                  walk_backoff_seconds=(0.0, 0.0, 0.0))

    fail_on_third = {"armed": True}

    async def ingest(rows, symbol, timeframe):
        for n, obs in enumerate(rows, 1):
            if fail_on_third["armed"] and n == 3:
                raise RuntimeError("INJECTED_INGEST_FAILURE on row 3")
            await store.ingest_raw(obs, "MISSING")

    runner = BootstrapRunner(fetcher=source, ingest=ingest,
                             store=checkpoints, cells=[("BTCUSDT", "1h")])

    async def frontiers():
        row = await (await store.db.execute(
            "SELECT MAX(as_of) FROM raw_observation WHERE symbol=? AND "
            "timeframe=?", ("BTCUSDT", "1h"))).fetchone()
        value = row[0] if row else None
        return {("BTCUSDT", "1h"): None if value is None
                else BS._iso_to_ms(str(value))}

    async def stored():
        rows = await (await store.db.execute(
            "SELECT as_of FROM raw_observation ORDER BY as_of")).fetchall()
        return [BS._iso_to_ms(r[0]) for r in rows]

    log(f"venue retains {len(SERIES)} closed bars: {SERIES}")

    # ---- run 1: the service hands the frontier over, then pages -----------
    source.set_frontiers(await frontiers())
    log(f"\nrun 1: frontiers handed to source = {await frontiers()}")
    try:
        await runner.run_phase1(start_ms=DEEP_START_MS, end_ms=NOW_MS + HOUR)
        log("run 1: run_phase1 returned without raising (unexpected)")
    except Exception as exc:                        # noqa: BLE001
        log(f"run 1: run_phase1 raised {type(exc).__name__}: {exc}")
    log(f"run 1: rows durably stored  = {await stored()}")
    log(f"run 1: source._served_upto  = {dict(source._served_upto)}")
    log(f"run 1: store frontier now   = {await frontiers()}")

    # ---- run 2: same process, fault cleared, service.run() repeats --------
    fail_on_third["armed"] = False
    source.set_frontiers(await frontiers())   # exactly what service.run() does
    log("\nrun 2 (same process, ingest healthy, service re-reads frontiers):")
    log(f"  set_frontiers({await frontiers()}) — _served_upto after handoff = "
        f"{dict(source._served_upto)}")
    result = await runner.run_phase1(start_ms=DEEP_START_MS,
                                     end_ms=NOW_MS + HOUR)
    log(f"  run_phase1 status={result.get('status')} "
        f"completed={result.get('completed')} skipped={result.get('skipped')}")
    final = await stored()
    log(f"  rows durably stored = {final}")
    log(f"  MISSING FOR EVER    = {sorted(set(SERIES) - set(final))}")
    row = await checkpoints.load_bootstrap("BTCUSDT:1h")
    log(f"  checkpoint          = status={row and row.get('status')} "
        f"cursor_ms={row and row.get('cursor_ms')} "
        f"bars={row and row.get('bars_ingested')}")

    # ---- run 3: the catch-up path, which DOES reset the high-water mark ---
    source.begin_catch_up("BTCUSDT", "1h", (await frontiers())[("BTCUSDT", "1h")])
    log("\nrun 3 (same process, after begin_catch_up reset):")
    log(f"  _served_upto after begin_catch_up = {dict(source._served_upto)}")
    await runner.run_phase1(start_ms=DEEP_START_MS, end_ms=NOW_MS + HOUR)
    final = await stored()
    log(f"  rows durably stored = {final}")
    log(f"  missing             = {sorted(set(SERIES) - set(final))}")

    await store.close()
    await checkpoints.close()
    bridge.close()
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    asyncio.run(main())
