"""K-014 — negative/zero volume passes the ingest boundary.

Real code only: `parse_kline_to_observation` (frozen ingest parser),
`_ohlc_violation` (CP-12 hygiene gate of bootstrap_service),
`ingest_observations` -> `SQLiteStore.ingest_raw`, and
`validate_market_observation` (the contract validator that is NOT called).

Run: python3 -B AUDIT/probes_V3b/K-014.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.data_catalog.contracts import validate_market_observation   # noqa: E402
from apex.data_catalog.ingest.toobit_public import (                  # noqa: E402
    parse_kline_to_observation)
from apex.data_catalog.store.sqlite_store import SQLiteStore          # noqa: E402
from apex.ops.bootstrap_service import (                              # noqa: E402
    _ohlc_violation, ingest_observations)

OUT = Path(__file__).with_suffix(".out")
BASE = 1_600_000_000_000


async def main() -> None:
    lines = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        lines.append(msg)

    path = os.path.join(tempfile.mkdtemp(), "k014.db")
    store = await SQLiteStore(path).open()

    cases = {
        "negative volume": [BASE, "100", "101", "99", "100.5", "-1",
                            BASE + 3_599_999],
        "zero volume, CLOSED": [BASE + 3_600_000, "100", "101", "99", "100.5",
                                "0", BASE + 7_199_999],
        "healthy volume": [BASE + 7_200_000, "100", "101", "99", "100.5",
                           "12.5", BASE + 10_799_999],
    }
    parsed = {}
    for label, row in cases.items():
        obs = parse_kline_to_observation("BTCUSDT", "1h", row, 0)
        parsed[label] = obs
        log(f"{label}:")
        log(f"  parser accepted: volume={obs.volume!r} status={obs.status} "
            f"type={type(obs.volume).__name__}")
        log(f"  _ohlc_violation (CP-12 hygiene gate) -> {_ohlc_violation(obs)!r}")
        try:
            validate_market_observation(obs)
            log("  validate_market_observation -> PASSED")
        except Exception as exc:                        # noqa: BLE001
            log(f"  validate_market_observation -> {type(exc).__name__} "
                f"{getattr(exc, 'code', '')}: {exc}")

    result = await ingest_observations(store, list(parsed.values()),
                                       "BTCUSDT", "1h", oi_state="MISSING")
    log(f"\ningest_observations result: {result}")
    rows = await (await store.db.execute(
        "SELECT open_time,volume,candle_status,quality_state FROM "
        "market_observation ORDER BY open_time")).fetchall()
    log("market_observation rows after ingest:")
    for row in rows:
        log(f"  open_time={row[0]} volume={row[1]!r} candle_status={row[2]} "
            f"quality_state={row[3]}")
    raws = await (await store.db.execute(
        "SELECT as_of,volume,status,oi_state FROM raw_observation "
        "ORDER BY as_of")).fetchall()
    log("raw_observation rows after ingest:")
    for row in raws:
        log(f"  as_of={row[0]} volume={row[1]!r} status={row[2]} "
            f"oi_state={row[3]}")

    log("\ngrep: does any ingest path call validate_market_observation?")
    import subprocess
    out = subprocess.run(
        ["grep", "-rn", "validate_market_observation", "--include=*.py",
         "apex"], cwd=REPO, capture_output=True, text=True).stdout
    for line in out.strip().splitlines():
        log("  " + line)

    await store.close()
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    asyncio.run(main())
