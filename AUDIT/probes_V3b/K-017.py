"""K-017 — drop evidence is durable only when the cell reaches COMPLETE.

Uses the repository's own poison-row venue helpers (loaded from
tests/unit/test_ops_bootstrap_service.py by file path, not re-implemented)
with the real BootstrapService / ToobitKlineSource / SQLiteStore /
ResearchCheckpointStore, then closes the service (process exit) and reopens
it OFFLINE to show what an operator sees afterwards.

Run: python3 -B AUDIT/probes_V3b/K-017.py
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


async def main() -> None:
    lines = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        lines.append(msg)

    tmp = Path(tempfile.mkdtemp())
    db = str(tmp / "apex.sqlite3")
    venue = T.HygieneVenue(step_ms=T.DAY, retention=50, limit_cap=1000,
                           now_ms=T.POISON_OPEN_B + 5 * T.DAY,
                           rows_by_open=T.POISON_OHLC)
    source, bridge = T.source_for(venue, max_pages=1)
    service = BS.BootstrapService(config=Config(), cells=[("BTCUSDT", "1d")],
                                  source=source, db_path=db,
                                  checkpoint_path=db)
    await service.open()
    try:
        result = await service.run(start_ms=DEEP_START_MS,
                                   end_ms=venue.newest_ms + 100 * T.DAY,
                                   announce=False)
        log(f"budget stop: status={result['status']} "
            f"resumable={result.get('resumable')} "
            f"invalid_bars_dropped(reported)={result.get('invalid_bars_dropped')}")
        row = await service._checkpoints.load_bootstrap("BTCUSDT:1d")
        log(f"durable checkpoint: status={row['status']} "
            f"payload={row.get('payload')}")
        live = await service.status()
        log(f"in-process status(): invalid_bars_dropped="
            f"{live['invalid_bars_dropped']}")
        log(f"live source evidence: invalid_by_cell="
            f"{dict(source.invalid_by_cell)} reasons="
            f"{ {k: dict(v) for k, v in source.invalid_reasons.items()} }")
    finally:
        await service.close()
        bridge.close()

    # ---- process exit: reopen OFFLINE (what `run_apex.py status` shows) ----
    offline = BS.BootstrapService(config=Config(), cells=[("BTCUSDT", "1d")],
                                  source=None, db_path=db, checkpoint_path=db)
    await offline.open()
    try:
        log(f"\nAFTER EXIT — offline service.source is None: "
            f"{offline.source is None}")
        status = await offline.status()
        log(f"offline status(): invalid_bars_dropped="
            f"{status['invalid_bars_dropped']} "
            f"cells_completed={status['cells_completed']}")
        row = await offline._checkpoints.load_bootstrap("BTCUSDT:1d")
        log(f"offline checkpoint: status={row['status']} "
            f"payload={row.get('payload')}")
    finally:
        await offline.close()

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    asyncio.run(main())
