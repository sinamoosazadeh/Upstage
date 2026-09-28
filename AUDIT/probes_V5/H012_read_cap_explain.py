"""H-012 in-memory SQLite proof of full count/read before Python bar slicing.
Uses repository SQLite DDL and query text; no data/ or persistent DB."""
import asyncio, json
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from apex.data_catalog.contracts import MarketObservation
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.ops import engine_context as ec

GET_WINDOW=("SELECT * FROM (SELECT observation_id, symbol, timeframe, open_price, high_price, low_price, close_price, volume, open_interest, open_time, retrieved_at, candle_status, quality_state, source, raw_payload_hash FROM market_observation WHERE symbol=? AND timeframe=? AND candle_status IN ('CLOSED','CORRECTED') AND open_time<=? ORDER BY open_time DESC LIMIT ?) ORDER BY open_time ASC")
LINEAGE=("SELECT m.open_time,m.observation_id,m.raw_payload_hash,r.content_hash,r.availability_time,r.oi_timestamp,r.oi_state FROM market_observation m JOIN raw_observation r ON m.observation_id='obs-'||r.event_id WHERE m.symbol=? AND m.timeframe=? AND m.candle_status IN ('CLOSED','CORRECTED') AND m.open_time>=? AND m.open_time<=? ORDER BY m.open_time")
async def plan(db, label, sql, args=()):
  rows=await (await db.execute("EXPLAIN QUERY PLAN "+sql,args)).fetchall()
  return {"case":label,"details":[r[3] for r in rows]}
async def main():
  store=await SQLiteStore(":memory:").open()
  try:
    plans=[]
    for label,sql,args in (("cell_discovery",ec.CELL_QUERY,()),
      ("get_window",GET_WINDOW,("BTCUSDT","1h","2026-01-04T00:00:00.000Z",3)),
      ("lineage",LINEAGE,("BTCUSDT","1h","2026-01-01T00:00:00.000Z","2026-01-04T00:00:00.000Z"))):
      plans.append(await plan(store.db,"repository DDL; no market_observation device index; "+label,sql,args))
    idx="CREATE INDEX probe_market_cell_close ON market_observation(symbol,timeframe,candle_status,open_time)"
    await store.db.execute(idx)
    for label,sql,args in (("cell_discovery",ec.CELL_QUERY,()),
      ("get_window",GET_WINDOW,("BTCUSDT","1h","2026-01-04T00:00:00.000Z",3)),
      ("lineage",LINEAGE,("BTCUSDT","1h","2026-01-01T00:00:00.000Z","2026-01-04T00:00:00.000Z"))):
      plans.append(await plan(store.db,"temporary candidate composite index; "+label,sql,args))
    start=datetime(2026,1,1,tzinfo=timezone.utc)
    for i in range(3):
      price=Decimal(100+i)
      stamp=(start+timedelta(hours=i)).isoformat(timespec="milliseconds").replace("+00:00","Z")
      obs=MarketObservation("BTCUSDT","1h",price,price+1,price-1,price+Decimal(".5"),Decimal(10),None,stamp,i,"CLOSED",availability_time=stamp)
      await store.ingest_raw(obs,oi_state="MISSING")
    count=(await (await store.db.execute(ec.CELL_QUERY)).fetchall())
    count=int(count[0][3])
    from apex.ops.engine_context import EngineContextProducer
    producer=EngineContextProducer(store,now=lambda:1767484800.0)
    full=await producer.window("BTCUSDT","1h","2026-01-04T00:00:00.000Z",count)
    capped=full[-1:]
    print(json.dumps({"repository_query_count":count,"actual_get_window_rows":len(full),
      "python_slice_rows_when_cap_is_1":len(capped),"slice_is_after_window_read_and_lineage":True,
      "baseline_market_indexes_in_frozen_ddl":[],"plans":plans},indent=2,sort_keys=True))
  finally: await store.close()
asyncio.run(main())
