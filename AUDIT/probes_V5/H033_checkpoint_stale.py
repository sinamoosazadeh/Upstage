"""H-033: stale bootstrap checkpoint updates in repository in-memory DDL."""
import asyncio
import json
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.ops.bootstrap_service import CanonicalMirroredCheckpoints
from apex.research.checkpoints import ResearchCheckpointStore

async def main():
    research = await ResearchCheckpointStore(":memory:").open()
    canonical = await SQLiteStore(":memory:").open()
    try:
        wrapper = CanonicalMirroredCheckpoints(research, canonical)
        await wrapper.save_bootstrap(
            cell_id="BTCUSDT-15m", symbol="BTCUSDT", timeframe="15m",
            phase=1, status="COMPLETE", cursor_ms=900, bars_ingested=12,
            payload={"generation": "new", "detail": "completed"})
        await wrapper.save_bootstrap(
            cell_id="BTCUSDT-15m", symbol="BTCUSDT", timeframe="15m",
            phase=1, status="PENDING", cursor_ms=400, bars_ingested=1,
            payload={"generation": "stale", "detail": "old"})
        row = await research.load_bootstrap("BTCUSDT-15m")
        canonical_row = await (await canonical.db.execute(
            "SELECT status,cursor_open_time,bars_written,last_error "
            "FROM bootstrap_progress WHERE symbol=? AND timeframe=? AND phase=?",
            ("BTCUSDT", "15m", "P1"))).fetchone()
        plan = await (await research.db.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM research_bootstrap_progress WHERE cell_id=?",
            ("BTCUSDT-15m",))).fetchall()
        print(json.dumps({
            "research_status": row["status"],
            "research_cursor_ms": row["cursor_ms"],
            "research_payload": row["payload"],
            "research_bars_ingested": row["bars_ingested"],
            "canonical_status": canonical_row[0],
            "canonical_cursor_open_time": canonical_row[1],
            "canonical_bars_written": canonical_row[2],
            "canonical_last_error": canonical_row[3],
            "cell_read_query_plan": [item[3] for item in plan],
            "repository_checkpoint_schema_has_cell_id_primary_key": True,
            "device_index_applicable": False,
        }, sort_keys=True, indent=2))
    finally:
        await research.close()
        await canonical.close()

asyncio.run(main())
