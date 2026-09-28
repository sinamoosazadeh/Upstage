"""I-004: EXPLAIN the producer's bounded per-cell/bar lineage query in memory."""
import json
import sqlite3
from apex.data_catalog.store.sqlite_store import CH4_DDL, CH5_DDL

query = (
    "SELECT m.open_time,m.observation_id,m.raw_payload_hash,r.content_hash,"
    "r.availability_time,r.oi_timestamp,r.oi_state FROM market_observation m "
    "JOIN raw_observation r ON m.observation_id='obs-'||r.event_id "
    "WHERE m.symbol=? AND m.timeframe=? AND m.candle_status IN ('CLOSED','CORRECTED') "
    "AND m.open_time>=? AND m.open_time<=? ORDER BY m.open_time"
)
conn = sqlite3.connect(":memory:")
conn.executescript(CH4_DDL + CH5_DDL)
def plan():
    return [row[3] for row in conn.execute(
        "EXPLAIN QUERY PLAN " + query,
        ("BTCUSDT", "1h", "2026-01-01", "2026-01-02"))]
without = plan()
base_indexes = [row[1] for row in conn.execute("PRAGMA index_list(market_observation)")]
# Hypothetical device-side lookup index, created only in this in-memory DB.
conn.execute("CREATE INDEX device_market_window ON market_observation "
             "(symbol,timeframe,candle_status,open_time)")
with_device_style = plan()
print(json.dumps({"repository_ddl_without_extra_index": without,
                  "with_hypothetical_device_style_index": with_device_style,
                  "repository_market_indexes_before_hypothetical": base_indexes,
                  "database": ":memory:"}, sort_keys=True, indent=2))
conn.close()
