"""EXPLAIN repository get_window SQL on in-memory SQLite, no device DB."""
import asyncio
import sqlite3
from apex.data_catalog.store.sqlite_store import SQLiteStore

SQL = ("SELECT * FROM (SELECT observation_id, symbol, timeframe, "
       " open_price, high_price, low_price, close_price, volume, "
       " open_interest, open_time, retrieved_at, candle_status, "
       " quality_state, source, raw_payload_hash "
       " FROM market_observation WHERE symbol=? AND timeframe=? "
       " AND candle_status IN ('CLOSED','CORRECTED') "
       " AND open_time<=? ORDER BY open_time DESC LIMIT ?) "
       "ORDER BY open_time ASC")
ARGS = ("BTCUSDT", "1h", "2026-01-15T14:00:00.000Z", 300)

async def main():
    store = SQLiteStore(path=":memory:")
    await store.open()
    try:
        print(f"SQLite {sqlite3.sqlite_version}; repository CH4_DDL; :memory: only")
        indexes = await (await store.db.execute("PRAGMA index_list('market_observation')")).fetchall()
        print(f"repository secondary indexes on market_observation before probe index: {indexes}")
        rows = await (await store.db.execute("EXPLAIN QUERY PLAN " + SQL, ARGS)).fetchall()
        print("without hypothetical device index:")
        for row in rows:
            print(tuple(row))
        await store.db.execute(
            "CREATE INDEX idx_market_device_pit_window "
            "ON market_observation(symbol,timeframe,candle_status,open_time)")
        rows = await (await store.db.execute("EXPLAIN QUERY PLAN " + SQL, ARGS)).fetchall()
        print("with temporary in-memory hypothetical composite index:")
        for row in rows:
            print(tuple(row))
    finally:
        await store.close()

asyncio.run(main())
