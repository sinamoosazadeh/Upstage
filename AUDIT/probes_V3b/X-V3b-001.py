"""X-V3b-001 — EngineContextProducer._input_fingerprint / window() cost probe.

READ-ONLY with respect to the repository: this script only imports repository
code and writes a synthetic SQLite database into a temporary directory
(default /tmp). It never touches data/, .env, the network or the device DB.

What it does
------------
1. Builds a synthetic store with the REAL `SQLiteStore.open()` migrations and
   the REAL `SQLiteStore.ingest_raw` / `insert_snapshot` methods (commit is
   deferred in bulk mode only, to make 200k rows loadable; every INSERT
   statement executed is the repository's own).
2. Runs EXPLAIN QUERY PLAN for the two market_observation<->raw_observation
   joins used by `_input_fingerprint` and by `window()`, plus the snapshot_pit
   and ledger reads of `_input_fingerprint`, in four index states
   (none / device indexes, before / after ANALYZE) and for the
   `substr(m.observation_id,5)` rewrite.
3. Measures wall time of the fingerprint queries and of the real
   `EngineContextProducer.window()`.

Usage: python3 -B AUDIT/probes_V3b/X-V3b-001.py [db_path]
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import time
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.data_catalog.contracts import MarketObservation          # noqa: E402
from apex.data_catalog.store.sqlite_store import SQLiteStore       # noqa: E402

DB = sys.argv[1] if len(sys.argv) > 1 else "/tmp/v3b_big.db"
SYMBOLS = ["BTCUSDT", "ETHUSDT"]
TFS = ["1m", "5m", "15m", "1h", "4h"]
PER_CELL = 20_000                      # 2 * 5 * 20000 = 200_000 market rows
SNAPSHOTS = 300_000
LEDGER_ROWS = 2_000
DEVICE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_mo_sym_tf_open "
    "ON market_observation(symbol,timeframe,open_time)",
    "CREATE INDEX IF NOT EXISTS idx_pit_scope_asof "
    "ON snapshot_pit(source_state,symbol_scope,timeframe_scope,as_of)",
]

FP_RAW = ("SELECT m.observation_id,m.raw_payload_hash,r.availability_time,"
          "r.oi_timestamp,r.oi_state "
          "FROM market_observation m JOIN raw_observation r "
          "ON m.observation_id='obs-'||r.event_id "
          "WHERE m.symbol=? AND r.availability_time<=? "
          "ORDER BY m.timeframe,m.open_time,m.observation_id")
FP_RAW_REWRITE = ("SELECT m.observation_id,m.raw_payload_hash,r.availability_time,"
                  "r.oi_timestamp,r.oi_state "
                  "FROM market_observation m JOIN raw_observation r "
                  "ON r.event_id = substr(m.observation_id, 5) "
                  "WHERE m.symbol=? AND r.availability_time<=? "
                  "ORDER BY m.timeframe,m.open_time,m.observation_id")
FP_FACTS = ("SELECT snapshot_id FROM snapshot_pit WHERE as_of<=? AND "
            "source_state NOT IN ('CP14_BRIDGE_CONTEXT','CP14_UNCERTAINTY',"
            "'CP14_COMPONENTS','CP14_SL14_ADMISSION') ORDER BY snapshot_id")
FP_PRIOR = ("SELECT snapshot_id FROM snapshot_pit WHERE source_state IN "
            "('CP14_UNCERTAINTY','CP14_COMPONENTS') AND symbol_scope=? AND "
            "timeframe_scope=? AND as_of<? ORDER BY snapshot_id")
FP_LEDGER = "SELECT ledger_id,payload_hash FROM ledger WHERE timestamp<=? ORDER BY rowid"
WIN_META = ("SELECT m.open_time,m.observation_id,m.raw_payload_hash,r.content_hash,"
            "r.availability_time,r.oi_timestamp,r.oi_state FROM market_observation m "
            "JOIN raw_observation r ON m.observation_id='obs-'||r.event_id "
            "WHERE m.symbol=? AND m.timeframe=? AND m.candle_status IN ('CLOSED','CORRECTED') "
            "AND m.open_time>=? AND m.open_time<=? ORDER BY m.open_time")
WIN_META_REWRITE = WIN_META.replace(
    "ON m.observation_id='obs-'||r.event_id",
    "ON r.event_id = substr(m.observation_id, 5)")
HISTORY = ("SELECT vector_quality_state FROM snapshot_pit WHERE "
           "source_state='CP14_COMPONENTS' AND symbol_scope=? AND timeframe_scope=? "
           "AND as_of<? ORDER BY as_of DESC,rowid DESC LIMIT 48")

TF_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000,
         "1h": 3_600_000, "4h": 14_400_000}
BASE_MS = 1_600_000_000_000


def iso(ms: int) -> str:
    import datetime as dt
    return (dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z")


async def build(path: str, log) -> None:
    store = await SQLiteStore(path).open()
    real_commit = store.db.commit

    async def deferred():
        return None

    store.db.commit = deferred                     # bulk load only
    t0 = time.time()
    n = 0
    for symbol in SYMBOLS:
        for tf in TFS:
            step = TF_MS[tf]
            for i in range(PER_CELL):
                ms = BASE_MS + i * step
                stamp = iso(ms)
                obs = MarketObservation(
                    symbol=symbol, timeframe=tf,
                    open=Decimal("100"), high=Decimal("101"),
                    low=Decimal("99"), close=Decimal("100.5"),
                    volume=Decimal(str(10 + i)), oi=Decimal(str(1000 + i)),
                    timestamp=stamp, sequence=i, status="CLOSED",
                    source="TOOBIT", availability_time=stamp,
                    oi_timestamp=stamp)
                await store.ingest_raw(obs, "AVAILABLE")
                n += 1
            await real_commit()
    log(f"market_observation+raw_observation rows ingested: {n} "
        f"in {time.time() - t0:.1f}s (real SQLiteStore.ingest_raw)")

    t0 = time.time()
    states = ["PUBLIC_VENUE_FACTS", "CP14_COMPONENTS", "CP14_UNCERTAINTY",
              "CP14_BRIDGE_CONTEXT", "QUALITY_obs", "CP14_SL14_ADMISSION"]
    for i in range(SNAPSHOTS):
        state = states[i % len(states)]
        sym = SYMBOLS[i % len(SYMBOLS)]
        tf = TFS[i % len(TFS)]
        await store.insert_snapshot({
            "snapshot_id": f"snap-{i:08d}", "as_of": iso(BASE_MS + i * 1000),
            "symbol_scope": [sym], "timeframe_scope": [tf],
            "source_state": state, "manifest_hash": "m" * 8,
            "parameter_package_id": "pkg-1", "code_version": "v1",
            "quality_state": {"min_q": 0.9, "weighted_q": 0.9,
                              "data": {"s_i": {}, "parameter_version": "pkg-1",
                                       "classifier_version": "c"}}})
        if i % 20_000 == 0:
            await real_commit()
    await real_commit()
    log(f"snapshot_pit rows ingested: {SNAPSHOTS} in {time.time() - t0:.1f}s "
        f"(real SQLiteStore.insert_snapshot)")

    store.db.commit = real_commit
    from apex.ledger.store import LedgerWriter
    writer = LedgerWriter(store)
    await writer.initialize()
    async with writer:
        for i in range(LEDGER_ROWS):
            await writer.append(event_type="PROBE", intent_id=f"i-{i}",
                                result="OK", sequence=i)
    log(f"ledger rows appended via real LedgerWriter.append: {LEDGER_ROWS}")
    await store.close()


def eqp(con: sqlite3.Connection, sql: str, args) -> list[str]:
    return [" ".join(str(c) for c in row[3:])
            for row in con.execute("EXPLAIN QUERY PLAN " + sql, args).fetchall()]


STATES = (("A", "no device indexes, no ANALYZE", False, False),
          ("B", "no device indexes, after ANALYZE", False, True),
          ("C", "device indexes, no ANALYZE", True, False),
          ("D", "device indexes, after ANALYZE", True, True))


def set_state(con: sqlite3.Connection, indexes: bool, analyze: bool) -> None:
    """Deterministic index/statistics state (sqlite_stat1 is persistent)."""
    for ix in ("idx_mo_sym_tf_open", "idx_pit_scope_asof"):
        con.execute(f"DROP INDEX IF EXISTS {ix}")
    if indexes:
        for stmt in DEVICE_INDEXES:
            con.execute(stmt)
    has_stat = con.execute(
        "SELECT count(*) FROM sqlite_master WHERE name='sqlite_stat1'").fetchone()[0]
    if has_stat:
        con.execute("DELETE FROM sqlite_stat1")
    con.commit()
    if analyze:
        con.execute("ANALYZE")
    con.commit()
    con.close()                      # force a fresh schema/stat load


def queryset(as_of: str):
    return [
        ("FP_RAW (fingerprint join, current)", FP_RAW, ("BTCUSDT", as_of)),
        ("FP_RAW (rewrite substr)", FP_RAW_REWRITE, ("BTCUSDT", as_of)),
        ("FP_FACTS", FP_FACTS, (as_of,)),
        ("FP_PRIOR", FP_PRIOR, ("BTCUSDT", "1h", as_of)),
        ("FP_LEDGER", FP_LEDGER, (as_of,)),
        ("WIN_META (window join, current)", WIN_META,
         ("BTCUSDT", "1h", iso(BASE_MS), as_of)),
        ("WIN_META (rewrite substr)", WIN_META_REWRITE,
         ("BTCUSDT", "1h", iso(BASE_MS), as_of)),
        ("HISTORY (compose_bridge_context)", HISTORY, ("BTCUSDT", "1h", as_of)),
    ]


def plans(path: str, log) -> None:
    as_of = iso(BASE_MS + PER_CELL * TF_MS["1m"])
    for tag, label, indexes, analyze in STATES:
        set_state(sqlite3.connect(path), indexes, analyze)
        con = sqlite3.connect(path)
        log(f"\n--- EXPLAIN QUERY PLAN — state {tag}. {label} ---")
        for name, sql, args in queryset(as_of):
            for line in eqp(con, sql, args):
                log(f"  [{name}] {line}")
        con.close()


def timed_fetch(path: str, sql: str, args, budget: float):
    """Run one query, streaming rows, aborting after `budget` seconds."""
    con = sqlite3.connect(path)
    deadline = time.time() + budget
    aborted = {"v": False}

    def handler():
        if time.time() > deadline:
            aborted["v"] = True
            return 1
        return 0

    con.set_progress_handler(handler, 20000)
    t0 = time.time()
    rows = 0
    try:
        cur = con.execute(sql, args)
        for _ in cur:
            rows += 1
    except sqlite3.OperationalError as exc:
        con.close()
        return rows, time.time() - t0, f"ABORTED-{exc}"
    con.close()
    return rows, time.time() - t0, "complete"


def timings_sql(path: str, log, budget: float) -> None:
    as_of = iso(BASE_MS + PER_CELL * TF_MS["1m"])
    for tag, label, indexes, analyze in STATES:
        set_state(sqlite3.connect(path), indexes, analyze)
        log(f"\n--- wall time (budget {budget:.0f}s/query) — state {tag}. {label} ---")
        for name, sql, args in queryset(as_of):
            rows, secs, status = timed_fetch(path, sql, args, budget)
            log(f"  {name}: {rows} rows in {secs:.3f}s [{status}]")


async def timings_producer(path: str, log) -> None:
    from apex.ops.engine_context import EngineContextProducer
    as_of = iso(BASE_MS + PER_CELL * TF_MS["1m"])
    classifier = REPO / "tests" / "fixtures" / "e11_classifier_v1.yaml"
    for tag, label, indexes, analyze in STATES:
        set_state(sqlite3.connect(path), indexes, analyze)
        store = await SQLiteStore(path).open()
        producer = EngineContextProducer(store, classifier_path=classifier,
                                         environment="PAPER")
        log(f"\n--- real producer calls — state {tag}. {label} ---")
        for bars in (300,):
            t0 = time.time()
            try:
                win = await producer.window("BTCUSDT", "1h", as_of, bars)
                log(f"  producer.window(BTCUSDT,1h,bars={bars}): {len(win)} obs "
                    f"in {time.time() - t0:.3f}s")
            except Exception as exc:                      # noqa: BLE001
                log(f"  producer.window(bars={bars}) raised {type(exc).__name__}: "
                    f"{exc} after {time.time() - t0:.3f}s")
        if tag == "C":
            log("  producer._input_fingerprint: SKIPPED in state C — the same "
                "FP_RAW plan did not finish within 1690s in an earlier run")
        else:
            t0 = time.time()
            try:
                fp = await producer._input_fingerprint("BTCUSDT", "1h", as_of)
                log(f"  producer._input_fingerprint: {fp[:16]}… in "
                    f"{time.time() - t0:.3f}s")
            except Exception as exc:                      # noqa: BLE001
                log(f"  producer._input_fingerprint raised {type(exc).__name__}: "
                    f"{exc} after {time.time() - t0:.3f}s")
        await store.close()


def counts(path: str, log) -> None:
    con = sqlite3.connect(path)
    for table in ("market_observation", "raw_observation", "snapshot_pit", "ledger"):
        log(f"  {table}: {con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]} rows")
    log(f"  db size: {os.path.getsize(path) / 1e6:.1f} MB")
    log("  indexes present: " + json.dumps(
        [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")]))
    con.close()


def main() -> None:
    phase = sys.argv[2] if len(sys.argv) > 2 else "all"
    dest = Path(__file__).with_suffix(".out")
    handle = dest.open("a", encoding="utf-8")

    def log(msg: str) -> None:
        print(msg, flush=True)
        handle.write(msg + "\n")
        handle.flush()

    log(f"# X-V3b-001 probe — sqlite {sqlite3.sqlite_version}, db={DB}, phase={phase}")
    if phase in ("all", "build"):
        if not os.path.exists(DB):
            asyncio.run(build(DB, log))
        else:
            log("(reusing previously built synthetic db)")
        counts(DB, log)
    if phase in ("all", "plans"):
        plans(DB, log)
    if phase in ("all", "timings"):
        timings_sql(DB, log, float(os.environ.get("BUDGET", "120")))
    if phase in ("all", "producer"):
        asyncio.run(timings_producer(DB, log))
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
