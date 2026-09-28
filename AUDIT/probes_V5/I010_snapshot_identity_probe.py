"""Separate evidence_id uniqueness from snapshot_id uniqueness using repo DDL."""
import asyncio
import runpy
from dataclasses import replace
from pathlib import Path
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.identity.uuid_v7 import uuid_v7

ROOT=Path(__file__).resolve().parents[2]
ns=runpy.run_path(str(ROOT/"tests"/"integration"/"test_cp4_engines.py"))
event=ns["TestCP4EmissionsInsertIntoStore"]()._events()[0]

async def main():
    store=SQLiteStore(path=":memory:")
    await store.open()
    try:
        for table in ("evidence_event","snapshot_pit"):
            rows=await (await store.db.execute(f"PRAGMA index_list('{table}')")).fetchall()
            print(f"{table} indexes={[(r[1],r[2],r[3]) for r in rows]}")
        rows=await (await store.db.execute(
            "EXPLAIN QUERY PLAN SELECT COUNT(*) FROM evidence_event WHERE snapshot_id=?",
            (event.snapshot_id,))).fetchall()
        print(f"evidence_event snapshot lookup without secondary index plan={[tuple(r) for r in rows]}")
        await store.db.execute("CREATE INDEX probe_snapshot_idx ON evidence_event(snapshot_id)")
        rows=await (await store.db.execute(
            "EXPLAIN QUERY PLAN SELECT COUNT(*) FROM evidence_event WHERE snapshot_id=?",
            (event.snapshot_id,))).fetchall()
        print(f"evidence_event snapshot lookup with temporary in-memory index plan={[tuple(r) for r in rows]}")
        rows=await (await store.db.execute(
            "EXPLAIN QUERY PLAN SELECT snapshot_id FROM snapshot_pit WHERE snapshot_id=?",
            (event.snapshot_id,))).fetchall()
        print(f"snapshot_pit identity lookup using repository PK plan={[tuple(r) for r in rows]}")
        await store.insert_evidence(event)
        distinct_id=replace(event,evidence_id=uuid_v7())
        assert distinct_id.snapshot_id==event.snapshot_id and distinct_id.evidence_id!=event.evidence_id
        await store.insert_evidence(distinct_id)
        same_snapshot_count=(await (await store.db.execute(
            "SELECT COUNT(*) FROM evidence_event WHERE snapshot_id=?",(event.snapshot_id,))).fetchone())[0]
        print(f"same snapshot_id with two distinct evidence_ids inserted: rows={same_snapshot_count}")
        try:
            await store.insert_evidence(event)
        except Exception as exc:
            print(f"same evidence_id duplicate rejected: {type(exc).__name__}: {exc}")
        else:
            raise AssertionError("same evidence_id unexpectedly inserted twice")
        snap={"snapshot_id":event.snapshot_id,"as_of":"2026-01-15T14:00:00.000Z",
              "symbol_scope":["BTCUSDT"],"timeframe_scope":["1h"],
              "quality_state":{"min_q":0.8,"weighted_q":0.9}}
        await store.insert_snapshot(snap)
        try:
            await store.insert_snapshot(snap)
        except Exception as exc:
            print(f"same snapshot_id duplicate in snapshot_pit rejected: {type(exc).__name__}: {exc}")
        else:
            raise AssertionError("same snapshot_id unexpectedly inserted twice")
        print("probe=PASS; SQLiteStore :memory: and repository DDL only")
    finally:
        await store.close()

asyncio.run(main())
