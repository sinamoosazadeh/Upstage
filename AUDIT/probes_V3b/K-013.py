"""K-013 — every Catalog.get branch returns snapshot_id=None.

Uses the REAL Catalog, the REAL registry/computers and the REAL SQLiteStore
as window provider on a temporary database built by the repository's own
migrations. Nothing in the repository is modified; data/ is never touched.

Run: python3 -B AUDIT/probes_V3b/K-013.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.data_catalog.catalog import Catalog                      # noqa: E402
from apex.data_catalog.contracts import MarketObservation          # noqa: E402
from apex.data_catalog.store.sqlite_store import SQLiteStore       # noqa: E402

OUT = Path(__file__).with_suffix(".out")
BASE = 1_600_000_000_000


def iso(ms: int) -> str:
    import datetime as dt
    return (dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z")


async def main() -> None:
    lines = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        lines.append(msg)

    path = os.path.join(tempfile.mkdtemp(), "k013.db")
    store = await SQLiteStore(path).open()
    for i in range(120):
        ms = BASE + i * 3_600_000
        await store.ingest_raw(MarketObservation(
            symbol="BTCUSDT", timeframe="1h", open=Decimal("100"),
            high=Decimal("101"), low=Decimal("99"), close=Decimal("100.5"),
            volume=Decimal(str(10 + i)), oi=Decimal("7"), timestamp=iso(ms),
            sequence=i, status="CLOSED", source="TOOBIT",
            availability_time=iso(ms), oi_timestamp=iso(ms)), "AVAILABLE")
    as_of = iso(BASE + 119 * 3_600_000)

    cat = Catalog(provider=store)
    log(f"registry completeness: {cat.verify_completeness()}")

    async def show(feature_id: str, label: str, **kw):
        res = await cat.get(feature_id, "BTCUSDT", "1h", as_of, **kw)
        log(f"  {label:34s} feature={feature_id:22s} status={res.status.value:10s} "
            f"reason={res.reason:22s} value={str(res.value)[:18]:18s} "
            f"snapshot_id={res.snapshot_id!r}")
        return res

    log("\n-- every branch of Catalog.get --")
    await show("body_ratio", "ATOM, OK")
    await show("body_ratio", "ATOM, OK (second call)")
    # a non-ATOM tier feature: first call computes and stores, second hits cache
    for alias in ("sweep", "volatility_regime"):
        await show(alias, f"non-ATOM first call ({alias})")
        await show(alias, f"non-ATOM second call ({alias})")
    await show("no_such_feature", "UNREGISTERED_FEATURE_ID")
    await show("body_ratio", "PIT_FUTURE_AS_OF", lookback=1) if False else None
    res = await cat.get("body_ratio", "BTCUSDT", "1h",
                        iso(BASE + 10_000 * 3_600_000))
    log(f"  {'PIT_FUTURE_AS_OF':34s} status={res.status.value:10s} "
        f"reason={res.reason:22s} snapshot_id={res.snapshot_id!r}")
    res = await Catalog(provider=None).get("body_ratio", "BTCUSDT", "1h", as_of)
    log(f"  {'NO_WINDOW_PROVIDER':34s} status={res.status.value:10s} "
        f"reason={res.reason:22s} snapshot_id={res.snapshot_id!r}")
    res = await cat.get("body_ratio", "BTCUSDT", "1h", "not-a-timestamp")
    log(f"  {'INVALID_AS_OF_FORMAT':34s} status={res.status.value:10s} "
        f"reason={res.reason:22s} snapshot_id={res.snapshot_id!r}")

    log("\n-- source check: literal 'snapshot_id=' occurrences in Catalog.get --")
    src = (REPO / "apex/data_catalog/catalog.py").read_text().splitlines()
    for n, line in enumerate(src, 1):
        if "snapshot_id=" in line:
            log(f"  catalog.py:{n}: {line.strip()}")

    await store.close()
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    asyncio.run(main())
