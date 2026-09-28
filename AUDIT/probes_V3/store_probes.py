#!/usr/bin/env python3
"""Read-only SESSION V3 probes over isolated SQLite databases using repo DDL/code.

Run from the repository root with PYTHONDONTWRITEBYTECODE=1 and python3 -B.
Temporary databases are created under TemporaryDirectory and removed at exit.
No network, data/, credentials, or device database is used.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apex.data_catalog.contracts import MarketObservation
from apex.data_catalog.store.sqlite_store import SQLiteStore


def observation(*, high: str = "105", low: str = "95", close: str = "101",
                oi: Decimal | None = None, timestamp: str = "2026-09-27T00:00:00.000Z",
                sequence: int = 1, volume: str = "10", status: str = "CLOSED") -> MarketObservation:
    return MarketObservation(
        symbol="BTCUSDT", timeframe="1h", open=Decimal("100"),
        high=Decimal(high), low=Decimal(low), close=Decimal(close),
        volume=Decimal(volume), oi=oi, timestamp=timestamp, sequence=sequence,
        status=status, source="TOOBIT", availability_time="2026-09-27T01:00:00.000Z",
        oi_timestamp=None,
    )


async def k001() -> dict:
    with tempfile.TemporaryDirectory(prefix="v3-k001-") as td:
        store = await SQLiteStore(str(Path(td) / "probe.sqlite")).open()
        try:
            original = observation()
            correction = observation(high="107")
            original_id = await store.ingest_raw(original, "MISSING")
            corrected_id = await store.correct_raw(
                original_id, correction, "MISSING", "high-only correction", "V3-PROBE")
            raw = await (await store.db.execute(
                "SELECT event_id,high,content_hash FROM raw_observation ORDER BY rowid")).fetchall()
            market = await (await store.db.execute(
                "SELECT observation_id,high_price,candle_status,raw_payload_hash "
                "FROM market_observation ORDER BY rowid")).fetchall()
            revisions = await (await store.db.execute(
                "SELECT original_event_id,new_event_id FROM raw_revision ORDER BY rowid")).fetchall()
            window = await store.get_window("BTCUSDT", "1h", "2026-09-28T00:00:00.000Z", 5)
            return {
                "hash_equal_for_high_only_change": original.content_hash() == correction.content_hash(),
                "original_event_id": original_id,
                "correct_raw_returned_event_id": corrected_id,
                "raw_rows": [list(r) for r in raw],
                "market_rows": [list(r) for r in market],
                "revision_rows": [list(r) for r in revisions],
                "stored_window_highs": [str(o.high) for o in window],
            }
        finally:
            await store.close()


async def k002() -> dict:
    from apex.data_catalog.ingest.toobit_public import parse_kline_to_observation
    from apex.ops.engine_context import EngineContextProducer
    from datetime import datetime, timezone

    with tempfile.TemporaryDirectory(prefix="v3-k002-") as td:
        store = await SQLiteStore(str(Path(td) / "probe.sqlite")).open()
        try:
            open_ms = int(datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
            close_ms = open_ms + 3_600_000
            as_of = "2026-01-10T01:05:00.000Z"
            original = parse_kline_to_observation(
                "BTCUSDT", "1h", [open_ms, "100", "105", "95", "101", "10", close_ms], 1)
            original_id = await store.ingest_raw(original, "MISSING")
            producer = EngineContextProducer(store, environment="PAPER")
            before = await producer.window("BTCUSDT", "1h", as_of, 5)
            corrected = parse_kline_to_observation(
                "BTCUSDT", "1h", [open_ms, "100", "105", "95", "102", "10", close_ms], 1)
            new_id = await store.correct_raw(original_id, corrected, "MISSING", "late correction", "V3-PROBE")
            after = await producer.window("BTCUSDT", "1h", as_of, 5)
            revision = await (await store.db.execute(
                "SELECT original_event_id,new_event_id,correction_timestamp FROM raw_revision")).fetchone()
            raw = await (await store.db.execute(
                "SELECT event_id,close,availability_time FROM raw_observation ORDER BY rowid")).fetchall()
            return {
                "historical_as_of": as_of,
                "parser_availability_for_both_versions": [original.availability_time, corrected.availability_time],
                "before_correction": [str(o.close) for o in before],
                "correction_record": list(revision) if revision else None,
                "returned_new_event_id": new_id,
                "raw_rows": [list(r) for r in raw],
                "after_correction_same_historical_as_of": [str(o.close) for o in after],
            }
        finally:
            await store.close()


async def main(row: str) -> dict:
    probes = {"K-001": k001, "K-002": k002}
    if row not in probes:
        raise SystemExit(f"probe not yet implemented: {row}")
    return {"id": row, "probe": probes[row].__name__, "result": await probes[row]()}


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("usage: python store_probes.py K-001")
    print(json.dumps(asyncio.run(main(sys.argv[1])), sort_keys=True, indent=2))
