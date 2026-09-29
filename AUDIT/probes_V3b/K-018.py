"""K-018 — the CELL_COMPLETE notification is lost when the run end falls on
a close boundary.

Real BootstrapService / ToobitKlineSource / BootstrapRunner / SQLiteStore with
the repository's own poison-row venue helper. The only variable is `end_ms`:
exactly the last bar's close boundary vs a few seconds later.

Run: python3 -B AUDIT/probes_V3b/K-018.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.config import Config                                        # noqa: E402
from apex.ops import bootstrap_service as BS                          # noqa: E402
from apex.research.bootstrap import DEEP_START_MS                     # noqa: E402

spec = importlib.util.spec_from_file_location(
    "v3b_bs_tests", REPO / "tests" / "unit" / "test_ops_bootstrap_service.py")
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)

OUT = Path(__file__).with_suffix(".out")


async def scenario(label: str, end_offset_ms: int, log) -> None:
    tmp = Path(tempfile.mkdtemp())
    db = str(tmp / "apex.sqlite3")
    venue = T.HygieneVenue(step_ms=T.DAY, retention=50, limit_cap=1000,
                           now_ms=T.POISON_OPEN_B + 5 * T.DAY,
                           rows_by_open=T.POISON_OHLC)
    source, bridge = T.source_for(venue)
    service = BS.BootstrapService(config=Config(), cells=[("BTCUSDT", "1d")],
                                  source=source, db_path=db,
                                  checkpoint_path=db)
    await service.open()
    try:
        close_of_last = BS.close_time_ms(venue.newest_ms, "1d")
        end_ms = close_of_last + end_offset_ms
        result = await service.run(start_ms=DEEP_START_MS, end_ms=end_ms,
                                   announce=False)
        notes = [n for n in service.notifications
                 if n["kind"] == "CELL_COMPLETE"]
        row = await service._checkpoints.load_bootstrap("BTCUSDT:1d")
        log(f"\n{label}")
        log(f"  last bar open={venue.newest_ms} close={close_of_last} "
            f"end_ms={end_ms} (offset {end_offset_ms} ms)")
        log(f"  run status={result['status']} "
            f"invalid_bars_dropped={result.get('invalid_bars_dropped')} "
            f"pages_fetched={result.get('pages_fetched')}")
        log(f"  checkpoint status={row['status']} payload={row.get('payload')}")
        log(f"  CELL_COMPLETE notifications = {len(notes)}")
        for note in notes:
            log(f"    {note.get('text') or note}")
    finally:
        await service.close()
        bridge.close()


async def main() -> None:
    lines = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        lines.append(msg)

    log("# K-018 — completion announcement vs the run-end boundary")
    await scenario("A. end_ms == close boundary of the last closed bar", 0, log)
    await scenario("B. end_ms == close boundary + 5 s", 5_000, log)

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    asyncio.run(main())
