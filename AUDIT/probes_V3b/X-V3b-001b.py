"""X-V3b-001b — join-rewrite equivalence and unbounded-window cost.

1. Proves the `ON r.event_id = substr(m.observation_id,5)` rewrite returns
   EXACTLY the same rows as `ON m.observation_id='obs-'||r.event_id` on the
   synthetic 200k-row database, and states the one edge case where they
   could differ.
2. Measures the cost of the FULL-HISTORY window that
   `prepare_engine_bundle` requests (`window(symbol, tf, as_of, COUNT(*))`),
   which drives the same join once per cell per cycle.

Usage: python3 -B AUDIT/probes_V3b/X-V3b-001b.py [db_path]
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

DB = sys.argv[1] if len(sys.argv) > 1 else "/tmp/v3b_big.db"
OUT = Path(__file__).with_suffix(".out")
DEVICE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_mo_sym_tf_open "
    "ON market_observation(symbol,timeframe,open_time)",
    "CREATE INDEX IF NOT EXISTS idx_pit_scope_asof "
    "ON snapshot_pit(source_state,symbol_scope,timeframe_scope,as_of)",
]
CURRENT = ("SELECT m.observation_id,m.raw_payload_hash,r.availability_time,"
           "r.oi_timestamp,r.oi_state FROM market_observation m "
           "JOIN raw_observation r ON m.observation_id='obs-'||r.event_id "
           "WHERE m.symbol=? ORDER BY m.observation_id")
REWRITE = ("SELECT m.observation_id,m.raw_payload_hash,r.availability_time,"
           "r.oi_timestamp,r.oi_state FROM market_observation m "
           "JOIN raw_observation r ON r.event_id = substr(m.observation_id, 5) "
           "WHERE m.symbol=? ORDER BY m.observation_id")
WIN_FULL = ("SELECT m.open_time,m.observation_id,m.raw_payload_hash,r.content_hash,"
            "r.availability_time,r.oi_timestamp,r.oi_state FROM market_observation m "
            "JOIN raw_observation r ON m.observation_id='obs-'||r.event_id "
            "WHERE m.symbol=? AND m.timeframe=? AND m.candle_status IN ('CLOSED','CORRECTED') "
            "AND m.open_time>=? AND m.open_time<=? ORDER BY m.open_time")


def set_state(path: str, indexes: bool, analyze: bool) -> None:
    con = sqlite3.connect(path)
    for ix in ("idx_mo_sym_tf_open", "idx_pit_scope_asof"):
        con.execute(f"DROP INDEX IF EXISTS {ix}")
    if indexes:
        for stmt in DEVICE_INDEXES:
            con.execute(stmt)
    if con.execute("SELECT count(*) FROM sqlite_master "
                   "WHERE name='sqlite_stat1'").fetchone()[0]:
        con.execute("DELETE FROM sqlite_stat1")
    con.commit()
    if analyze:
        con.execute("ANALYZE")
    con.commit()
    con.close()


def timed(path: str, sql: str, args, budget: float):
    con = sqlite3.connect(path)
    deadline = time.time() + budget
    con.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 20000)
    t0 = time.time()
    rows = 0
    try:
        for _ in con.execute(sql, args):
            rows += 1
    except sqlite3.OperationalError as exc:
        con.close()
        return rows, time.time() - t0, f"ABORTED-{exc}"
    con.close()
    return rows, time.time() - t0, "complete"


def main() -> None:
    lines = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        lines.append(msg)

    log(f"# X-V3b-001b — sqlite {sqlite3.sqlite_version}, db={DB}")

    # ---- 1. equivalence -------------------------------------------------
    set_state(DB, indexes=False, analyze=True)     # a plan that terminates
    con = sqlite3.connect(DB)
    a = con.execute(CURRENT, ("BTCUSDT",)).fetchall()
    b = con.execute(REWRITE, ("BTCUSDT",)).fetchall()
    log(f"current join rows: {len(a)}; rewrite rows: {len(b)}; identical: {a == b}")
    bad = con.execute("SELECT count(*) FROM market_observation "
                      "WHERE substr(observation_id,1,4)<>'obs-'").fetchone()[0]
    log(f"market_observation rows whose observation_id does not start with "
        f"'obs-': {bad}  (the ONE case where the rewrite could differ)")
    full = con.execute("SELECT count(*) FROM market_observation WHERE symbol=? "
                       "AND timeframe=? AND candle_status IN ('CLOSED','CORRECTED')",
                       ("BTCUSDT", "1h")).fetchone()[0]
    bounds = con.execute("SELECT min(open_time),max(open_time) FROM market_observation "
                         "WHERE symbol=? AND timeframe=?", ("BTCUSDT", "1h")).fetchone()
    con.close()
    log(f"prepare_engine_bundle COUNT(*) for BTCUSDT:1h = {full} bars "
        f"(this is the `bars` argument it passes to window())")

    # ---- 2. cost of the full-history window join ------------------------
    for tag, indexes, analyze in (("A no-index/no-ANALYZE", False, False),
                                  ("C device-index/no-ANALYZE", True, False),
                                  ("D device-index/ANALYZE", True, True)):
        set_state(DB, indexes, analyze)
        rows, secs, status = timed(DB, WIN_FULL,
                                   ("BTCUSDT", "1h", bounds[0], bounds[1]), 120.0)
        log(f"  full-history WIN_META [{tag}]: {rows}/{full} rows in "
            f"{secs:.3f}s [{status}]")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
