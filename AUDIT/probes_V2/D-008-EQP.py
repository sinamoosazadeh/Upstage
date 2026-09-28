#!/usr/bin/env python3
from __future__ import annotations
import asyncio, os, tempfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from apex.data_catalog.store.sqlite_store import SQLiteStore

QUERIES={
 "raw":("SELECT m.observation_id,m.raw_payload_hash,r.availability_time,r.oi_timestamp,r.oi_state FROM market_observation m JOIN raw_observation r ON m.observation_id='obs-'||r.event_id WHERE m.symbol=? AND r.availability_time<=? ORDER BY m.timeframe,m.open_time,m.observation_id",("BTCUSDT","2026-09-28T00:00:00.000Z")),
 "facts":("SELECT snapshot_id FROM snapshot_pit WHERE as_of<=? AND source_state NOT IN ('CP14_BRIDGE_CONTEXT','CP14_UNCERTAINTY','CP14_COMPONENTS','CP14_SL14_ADMISSION') ORDER BY snapshot_id",("2026-09-28T00:00:00.000Z",)),
 "prior":("SELECT snapshot_id FROM snapshot_pit WHERE source_state IN ('CP14_UNCERTAINTY','CP14_COMPONENTS') AND symbol_scope=? AND timeframe_scope=? AND as_of<? ORDER BY snapshot_id",("BTCUSDT","1h","2026-09-27T00:00:00.000Z")),
 "ledger":("SELECT ledger_id,payload_hash FROM ledger WHERE timestamp<=? ORDER BY rowid",("2026-09-28T00:00:00.000Z",)),
}
async def main():
 fd,path=tempfile.mkstemp(prefix="audit-eqp-",suffix=".sqlite3",dir="/tmp"); os.close(fd)
 store=await SQLiteStore(path).open()
 async def plans(label):
  await store.db.execute("PRAGMA automatic_index=OFF")
  result={}
  for name,(sql,args) in QUERIES.items():
   rows=await (await store.db.execute("EXPLAIN QUERY PLAN "+sql,args)).fetchall()
   result[name]=[list(r) for r in rows]
  return result
 without=await plans("without")
 await store.db.execute("CREATE INDEX idx_mo_sym_tf_open ON market_observation(symbol,timeframe,open_time)")
 await store.db.execute("CREATE INDEX idx_pit_scope_asof ON snapshot_pit(symbol_scope,timeframe_scope,as_of)")
 await store.db.commit()
 with_indexes=await plans("with")
 print({"automatic_index":False,"without_device_indexes":without,"with_device_indexes":with_indexes,"required_indexes":["idx_mo_sym_tf_open","idx_pit_scope_asof"],"note":"SCAN entries are reported exactly as SQLite's planner returned them"})
 await store.close(); os.unlink(path)
asyncio.run(main())
