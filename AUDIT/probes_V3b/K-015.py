"""K-015 — a venue stuck on its retained tail completes the cell silently.

Real `ToobitKlineSource` (apex/ops/bootstrap_service.py) + real
`BootstrapRunner` phase-1 loop (apex/research/bootstrap.py) + real
`SQLiteStore`. The venue double is the same "StickyTail" shape the existing
repository test uses (tests/unit/test_ops_bootstrap_service.py:372-405).

Run: python3 -B AUDIT/probes_V3b/K-015.py
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
from apex.ops.bootstrap_service import ingest_observations            # noqa: E402
from apex.research.bootstrap import DEEP_START_MS                     # noqa: E402

OUT = Path(__file__).with_suffix(".out")
HOUR = 3_600_000
NOW_MS = 1_726_444_800_000


class StickyTail:
    """Venue with 4 retained bars that always answers with the newest 2."""

    def __init__(self):
        self.calls = []
        self.series = [NOW_MS - 3 * HOUR, NOW_MS - 2 * HOUR,
                       NOW_MS - HOUR, NOW_MS]

    async def get_klines(self, symbol, interval, start_ms, end_ms, limit=None):
        self.calls.append(int(end_ms))
        out = []
        for i, open_ms in enumerate(self.series[-2:]):
            row = [open_ms, "1", "1", "1", "1", "1", open_ms + HOUR - 1]
            out.append(parse_kline_to_observation(symbol, interval, row, i))
        return out


class HonestVenue(StickyTail):
    """Same 4 bars, but endTime is honoured (a genuinely exhausted window)."""

    async def get_klines(self, symbol, interval, start_ms, end_ms, limit=None):
        self.calls.append(int(end_ms))
        window = [ms for ms in self.series if ms <= int(end_ms)][-2:]
        out = []
        for i, open_ms in enumerate(window):
            row = [open_ms, "1", "1", "1", "1", "1", open_ms + HOUR - 1]
            out.append(parse_kline_to_observation(symbol, interval, row, i))
        return out


async def drive(venue, label, log) -> None:
    bridge = BS.AsyncBridge().start()
    source = BS.ToobitKlineSource(client=venue, bridge=bridge,
                                  walk_backoff_seconds=(0.0, 0.0, 0.0))
    path = os.path.join(tempfile.mkdtemp(), "k015.db")
    store = await SQLiteStore(path).open()
    try:
        cursor, end = DEEP_START_MS, NOW_MS + HOUR
        pages, served = 0, []
        while pages < 10:
            page = source("BTCUSDT", "1h", cursor, end, 500)
            pages += 1
            rows = list(page.get("rows") or ())
            served.extend(BS._iso_to_ms(r.timestamp) for r in rows)
            if rows:
                await ingest_observations(store, rows, "BTCUSDT", "1h",
                                          oi_state="MISSING")
            if not rows:
                log(f"  [{label}] page {pages}: EMPTY page returned "
                    f"(code={page.get('code')!r}) -> this is the only "
                    f"completion signal the runner gets")
                break
            nxt = page.get("next_cursor_ms")
            if nxt is None or int(nxt) <= cursor:
                break
            cursor = int(nxt)
        stored = await (await store.db.execute(
            "SELECT count(*) FROM market_observation")).fetchone()
        log(f"  [{label}] venue retains {len(venue.series)} bars "
            f"{venue.series}")
        log(f"  [{label}] bars served to the runner: {sorted(set(served))}")
        log(f"  [{label}] bars durably stored: {stored[0]}")
        log(f"  [{label}] missing bars: "
            f"{sorted(set(venue.series) - set(served))}")
        log(f"  [{label}] source reported an error/refusal at any point: "
            f"{'no' if page.get('code') is None else page.get('code')}")
    finally:
        await store.close()
        bridge.close()


async def main() -> None:
    lines = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        lines.append(msg)

    log("# K-015 — repeated-window venue vs genuinely exhausted venue")
    log("\nA. StickyTail (venue ignores endTime and repeats its tail):")
    await drive(StickyTail(), "sticky", log)
    log("\nB. HonestVenue (same 4 bars, endTime honoured):")
    await drive(HonestVenue(), "honest", log)

    log("\n-- the completion signal in source code --")
    src = (REPO / "apex/ops/bootstrap_service.py").read_text().splitlines()
    for n in range(620, 634):
        log(f"  bootstrap_service.py:{n}: {src[n-1]}")
    log("\n-- default phase-1 verification in the runner --")
    src2 = (REPO / "apex/research/bootstrap.py").read_text().splitlines()
    for n in range(307, 315):
        log(f"  research/bootstrap.py:{n}: {src2[n-1]}")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    asyncio.run(main())
