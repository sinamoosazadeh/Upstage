#!/usr/bin/env python3
"""Broader repository-query EQP comparison for the audit.

The temporary database is opened through SQLiteStore, so its schema is the
repository DDL/migrations. No data/ or production database is read. The two
requested device indexes are compared for every representative per-cell,
bar, context, ledger, and bridge query used by the read paths traced in the
mandatory source files.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import ast
import sqlite3


def literal_assignment(path: Path, name: str):
    """Read a DDL string literal without importing optional runtime packages."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError(f"DDL assignment not found: {path}:{name}")


ARGS = {
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "as_of": "2026-09-28T00:00:00.000Z",
    "prior_as_of": "2026-09-27T00:00:00.000Z",
    "open_time": "2026-09-27T00:00:00.000Z",
    "snapshot": "s-audit",
    "proposal": "p-audit",
    "setup": "su-audit",
    "intent": "i-audit",
    "outcome": "o-audit",
}

QUERIES = {
    # SQLiteStore.get_window: newest N rows then restore ascending order.
    "store_get_window": (
        "SELECT * FROM (SELECT observation_id, symbol, timeframe, "
        "open_price, high_price, low_price, close_price, volume, open_interest, "
        "open_time, retrieved_at, candle_status, quality_state, source, raw_payload_hash "
        "FROM market_observation WHERE symbol=? AND timeframe=? "
        "AND candle_status IN ('CLOSED','CORRECTED') AND open_time<=? "
        "ORDER BY open_time DESC LIMIT ?) ORDER BY open_time ASC",
        (ARGS["symbol"], ARGS["timeframe"], ARGS["as_of"], 300)),
    # EngineContextProducer.window metadata join.
    "window_raw_metadata": (
        "SELECT m.open_time,m.observation_id,m.raw_payload_hash,r.content_hash,"
        "r.availability_time,r.oi_timestamp,r.oi_state FROM market_observation m "
        "JOIN raw_observation r ON m.observation_id='obs-'||r.event_id "
        "WHERE m.symbol=? AND m.timeframe=? AND m.candle_status IN ('CLOSED','CORRECTED') "
        "AND m.open_time>=? AND m.open_time<=? ORDER BY m.open_time",
        (ARGS["symbol"], ARGS["timeframe"], ARGS["open_time"], ARGS["as_of"])),
    "engine_input_raw": (
        "SELECT m.observation_id,m.raw_payload_hash,r.availability_time,r.oi_timestamp,r.oi_state "
        "FROM market_observation m JOIN raw_observation r "
        "ON m.observation_id='obs-'||r.event_id "
        "WHERE m.symbol=? AND r.availability_time<=? "
        "ORDER BY m.timeframe,m.open_time,m.observation_id",
        (ARGS["symbol"], ARGS["as_of"])),
    "engine_input_facts": (
        "SELECT snapshot_id FROM snapshot_pit WHERE as_of<=? "
        "AND source_state NOT IN ('CP14_BRIDGE_CONTEXT','CP14_UNCERTAINTY'," 
        "'CP14_COMPONENTS','CP14_SL14_ADMISSION') ORDER BY snapshot_id",
        (ARGS["as_of"],)),
    "engine_input_prior": (
        "SELECT snapshot_id FROM snapshot_pit WHERE source_state IN "
        "('CP14_UNCERTAINTY','CP14_COMPONENTS') AND symbol_scope=? "
        "AND timeframe_scope=? AND as_of<? ORDER BY snapshot_id",
        (ARGS["symbol"], ARGS["timeframe"], ARGS["prior_as_of"])),
    "engine_input_ledger": (
        "SELECT ledger_id,payload_hash FROM ledger WHERE timestamp<=? ORDER BY rowid",
        (ARGS["as_of"],)),
    "paper_plan_queue": (
        "SELECT proposal_id,setup_id,symbol,timeframe,direction,entry_ref,stop_price,"
        "target_price,sized_quantity,risk_amount,contract_multiplier,decision,"
        "vetoes_applied,risk_state,package_version,snapshot_id,as_of,created_utc,"
        "lineage,payload_hash,environment FROM trade_plan WHERE environment=? "
        "ORDER BY created_utc,proposal_id",
        ("PAPER",)),
    "paper_setup_exists": (
        "SELECT 1 FROM setup_candidate WHERE setup_id=? LIMIT 1",
        (ARGS["setup"],)),
    "paper_evidence_count": (
        "SELECT COUNT(*) FROM evidence_event WHERE symbol=? AND timeframe=?",
        (ARGS["symbol"], ARGS["timeframe"])),
    "paper_outcome_lookup": (
        "SELECT pnl,setup_id,exit_reason,context FROM outcome WHERE outcome_id=?",
        (ARGS["outcome"],)),
    "paper_ladder_pit": (
        "SELECT revision_id,parent_revision_id,state,emergency_state,multiplier,"
        "consumed_budget,reason,snapshot_id,applied_at FROM apex_risk_ladder_state "
        "WHERE applied_at<=? ORDER BY applied_at DESC,rowid DESC LIMIT 2",
        (ARGS["as_of"],)),
    "context_fact_exact": (
        "SELECT snapshot_id,vector_quality_state,as_of FROM snapshot_pit "
        "WHERE source_state=? AND symbol_scope=? AND timeframe_scope=? AND as_of=? "
        "ORDER BY as_of DESC,rowid DESC LIMIT 1",
        ("CP14_BRIDGE_CONTEXT", ARGS["symbol"], ARGS["timeframe"], ARGS["as_of"])),
    "quality_fact_read": (
        "SELECT snapshot_id,vector_quality_state,as_of FROM snapshot_pit "
        "WHERE source_state=? AND symbol_scope=? AND timeframe_scope=? AND as_of<=? "
        "ORDER BY as_of DESC,rowid DESC LIMIT 1",
        ("CP14_QUALITY_obs-audit", ARGS["symbol"], ARGS["timeframe"], ARGS["as_of"])),
    "funding_fact_read": (
        "SELECT snapshot_id,vector_quality_state,as_of FROM snapshot_pit "
        "WHERE source_state=? AND symbol_scope=? AND timeframe_scope=? AND as_of<=? "
        "ORDER BY as_of DESC,rowid DESC LIMIT 1",
        ("CP14_PUBLIC_FUNDING_SCHEDULE", ARGS["symbol"], "", ARGS["as_of"])),
}

async def explain(db, sql, args):
    rows = await (await db.execute("EXPLAIN QUERY PLAN " + sql, args)).fetchall()
    return [list(row) for row in rows]

async def main():
    fd, path = tempfile.mkstemp(prefix="audit-eqp-broad-", suffix=".sqlite3", dir="/tmp")
    os.close(fd)
    db = sqlite3.connect(path)
    try:
        # Apply the exact repository DDL strings, without importing aiosqlite.
        store_file = ROOT / "apex/data_catalog/store/sqlite_store.py"
        ledger_file = ROOT / "apex/ledger/store.py"
        risk_file = ROOT / "apex/risk/kernel.py"
        loop_file = ROOT / "apex/ops/paper_loop.py"
        db.executescript("CREATE TABLE IF NOT EXISTS schema_migrations "
                         "(migration_name TEXT PRIMARY KEY, applied_at TEXT NOT NULL);")
        for source, names in ((store_file, ("CH4_DDL", "CH5_DDL", "AI5_DDL", "IMMUTABILITY_TRIGGERS")),
                              (ledger_file, ("TRADE_PLAN_DDL", "AUDIT_DDL")),
                              (risk_file, ("LADDER_STATE_DDL",)),
                              (loop_file, ("CELL_CURSOR_DDL",))):
            for name in names:
                db.executescript(literal_assignment(source, name))
        db.commit()
        db.execute("PRAGMA automatic_index=OFF")
        def explain_sync(sql, args):
            return [list(row) for row in db.execute("EXPLAIN QUERY PLAN " + sql, args)]
        before = {name: explain_sync(sql, args)
                  for name, (sql, args) in QUERIES.items()}
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_mo_sym_tf_open "
            "ON market_observation(symbol,timeframe,open_time)")
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_pit_scope_asof "
            "ON snapshot_pit(symbol_scope,timeframe_scope,as_of)")
        db.commit()
        after = {name: explain_sync(sql, args)
                 for name, (sql, args) in QUERIES.items()}
        scans = lambda plans: {
            name: [row[3] for row in plan if "SCAN" in str(row[3]).upper()]
            for name, plan in plans.items()
            if any("SCAN" in str(row[3]).upper() for row in plan)
        }
        print({
            "automatic_index": False,
            "query_count": len(QUERIES),
            "without_device_indexes": before,
            "with_device_indexes": after,
            "scan_summary_without": scans(before),
            "scan_summary_with": scans(after),
            "required_indexes": ["idx_mo_sym_tf_open", "idx_pit_scope_asof"],
            "schema_source": "literal CH4_DDL/CH5_DDL/AI5_DDL/IMMUTABILITY_TRIGGERS/TRADE_PLAN_DDL/AUDIT_DDL/LADDER_STATE_DDL/CELL_CURSOR_DDL from repository",
            "temporary_path": path,
        })
    finally:
        db.close()
        os.unlink(path)

asyncio.run(main())
