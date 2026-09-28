from __future__ import annotations

import sqlite3

from apex.data_catalog.store.sqlite_store import CH4_DDL, CH5_DDL

WINDOW_SQL = (
    "SELECT * FROM (SELECT observation_id, symbol, timeframe, open_price, high_price, "
    "low_price, close_price, volume, open_interest, open_time, retrieved_at, candle_status, "
    "quality_state, source, raw_payload_hash FROM market_observation "
    "WHERE symbol=? AND timeframe=? AND candle_status IN ('CLOSED','CORRECTED') "
    "AND open_time<=? ORDER BY open_time DESC LIMIT ?) ORDER BY open_time ASC"
)
LINEAGE_SQL = (
    "SELECT m.open_time,m.observation_id,m.raw_payload_hash,r.content_hash,r.availability_time,"
    "r.oi_timestamp,r.oi_state FROM market_observation m JOIN raw_observation r "
    "ON m.observation_id='obs-'||r.event_id WHERE m.symbol=? AND m.timeframe=? "
    "AND m.candle_status IN ('CLOSED','CORRECTED') AND m.open_time>=? AND m.open_time<=? "
    "ORDER BY m.open_time"
)
COUNT_SQL = (
    "SELECT COUNT(*) FROM market_observation WHERE symbol=? AND timeframe=? "
    "AND candle_status IN ('CLOSED','CORRECTED') AND open_time<=?"
)
FINGERPRINT_SQL = (
    "SELECT m.observation_id,m.raw_payload_hash,r.availability_time,r.oi_timestamp,r.oi_state "
    "FROM market_observation m JOIN raw_observation r ON m.observation_id='obs-'||r.event_id "
    "WHERE m.symbol=? AND r.availability_time<=? "
    "ORDER BY m.timeframe,m.open_time,m.observation_id"
)


def plans(db: sqlite3.Connection, label: str) -> None:
    print(f"\n{label}")
    for name, sql, params in (
        ("SQLiteStore.get_window", WINDOW_SQL, ("BTCUSDT", "1h", "2026-01-01T00:00:00.000Z", 300)),
        ("EngineContextProducer.window lineage", LINEAGE_SQL, ("BTCUSDT", "1h", "2025-01-01T00:00:00.000Z", "2026-01-01T00:00:00.000Z")),
        ("prepare_engine_bundle row count", COUNT_SQL, ("BTCUSDT", "1h", "2026-01-01T00:00:00.000Z")),
        ("EngineContextProducer._input_fingerprint", FINGERPRINT_SQL, ("BTCUSDT", "2026-01-01T00:00:00.000Z")),
    ):
        rows = db.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
        print(name + ":")
        for row in rows:
            print(" ", tuple(row))


# Repository DDL only; disposable in-memory database; no data/ access.
db = sqlite3.connect(":memory:")
db.executescript(CH4_DDL)
db.executescript(CH5_DDL)
plans(db, "Repository DDL and indexes as declared")
db.execute("DROP INDEX idx_raw_sym_tf_asof")
plans(db, "Repository DDL with the one declared secondary raw index removed")
print("\nNote: repository DDL declares no market_observation composite window index; no device-specific indexes/data exist in this probe.")
