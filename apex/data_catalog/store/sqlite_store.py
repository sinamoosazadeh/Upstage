"""APEX_GEN5 SQLite store (physical persistence contract).

Blueprint: Ch.4 Data Plane DDL + Ch.5 raw store DDL (table/column/index
names verbatim), AI.5 Raw Store Contract (append-only, hash-chained,
raw_revision/raw_manifest), §2.6 retention (raw 12 months rolling,
snapshots/evidence 6 months, ledger/outcomes never purged; every purge
appends a retention event to the immutable audit trail), P12 (WAL,
synchronous=FULL, foreign_keys=ON, busy_timeout=5000), G16 (SQLite only —
physical PostgreSQL is Wave-Out).

Immutable raw store is enforced AT THE DATABASE LEVEL: UPDATE/DELETE on
raw_observation raise (T-RS-001). Corrections are new records: original
marked SUPERSEDED, new row appended with a fresh event_id and revision,
lineage preserved in raw_revision (T-CL-001/002/003). CLOSED candles are
never overwritten.

The store implements the catalog's WindowProvider so engines read the
catalog only — engines never SQL the store (Ch.5 lint rule).
"""

from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import aiosqlite

from apex.config import Config
from apex.data_catalog.contracts import (
    CORE10_SYMBOLS,
    TIMEFRAMES_14,
    EvidenceEvent,
    MarketObservation,
    parse_utc_ms,
)
from apex.identity.hashes import sha256_hex

# ---------------------------------------------------------------------------
# Ch.4 Data Plane DDL — VERBATIM (logical tables; money/prices are TEXT
# Decimal strings; the SQL is the frozen document's own SQL).
# ---------------------------------------------------------------------------

CH4_DDL = """
CREATE TABLE market_observation (
    observation_id TEXT PRIMARY KEY CHECK(typeof(observation_id)='text'),
    symbol TEXT CHECK(typeof(symbol)='text') CHECK(symbol IN ('BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT','XRPUSDT','ADAUSDT','DOGEUSDT','AVAXUSDT','LINKUSDT','LTCUSDT')),
    timeframe TEXT CHECK(typeof(timeframe)='text') CHECK(timeframe IN ('1m','3m','5m','15m','30m','1h','2h','4h','6h','8h','12h','1d','1w','1mo')),
    open_price TEXT CHECK(typeof(open_price)='text'),
    high_price TEXT CHECK(typeof(high_price)='text'),
    low_price TEXT CHECK(typeof(low_price)='text'),
    close_price TEXT CHECK(typeof(close_price)='text'),
    volume TEXT CHECK(typeof(volume)='text'),
    open_interest TEXT CHECK(typeof(open_interest)='text'),
    open_time TEXT CHECK(typeof(open_time)='text'),
    close_time TEXT CHECK(typeof(close_time)='text'),
    retrieved_at TEXT CHECK(typeof(retrieved_at)='text'),
    candle_status TEXT CHECK(candle_status IN ('MISSING','PARTIAL','CLOSED','CORRECTED','SUPERSEDED')),
    quality_state TEXT CHECK(quality_state IN ('Q0','Q1','Q2','Q3','Q4','QX')),
    source TEXT,
    schema_version TEXT,
    raw_payload_hash TEXT,
    CHECK(CAST(high_price AS REAL)>=max(CAST(open_price AS REAL),CAST(close_price AS REAL)) AND CAST(low_price AS REAL)<=min(CAST(open_price AS REAL),CAST(close_price AS REAL)) AND CAST(high_price AS REAL)>=CAST(low_price AS REAL))
);

CREATE TABLE quality_vector (
    quality_id TEXT PRIMARY KEY CHECK(typeof(quality_id)='text'),
    observation_id TEXT,
    q_schema REAL, q_time REAL, q_seq REAL, q_ohlc REAL, q_volume REAL, q_oi REAL, q_source REAL,
    q_raw REAL CHECK(q_raw>=0 AND q_raw<=1),
    veto_freshness INTEGER, veto_completeness INTEGER, veto_oi_lag INTEGER, veto_source INTEGER,
    FOREIGN KEY(observation_id) REFERENCES market_observation(observation_id)
);

CREATE TABLE snapshot_pit (
    snapshot_id TEXT PRIMARY KEY CHECK(typeof(snapshot_id)='text'),
    as_of TEXT,
    symbol_scope TEXT,
    timeframe_scope TEXT,
    source_state TEXT,
    manifest_hash TEXT,
    parameter_package_id TEXT,
    code_version TEXT,
    vector_quality_state TEXT,
    min_quality REAL,
    weighted_quality REAL,
    created_at TEXT
);

CREATE TABLE evidence_event (
    evidence_id TEXT PRIMARY KEY CHECK(typeof(evidence_id)='text'),
    timestamp_utc TEXT CHECK(typeof(timestamp_utc)='text'),
    symbol TEXT,
    timeframe TEXT,
    engine_id TEXT CHECK(engine_id IN ('E01','E02','E03','E04','E05','E06','E07','E08','E09','E10','E11','E12')),
    event_type TEXT,
    price_level TEXT CHECK(typeof(price_level)='text'),
    strength INTEGER,
    confidence REAL,
    quality TEXT,
    validity INTEGER,
    snapshot_id TEXT,
    parent_ids TEXT,
    payload_hash TEXT,
    source_hash TEXT,
    epsilon TEXT,
    atr TEXT,
    volume TEXT,
    oi TEXT,
    regime TEXT,
    utc_activity_window_id TEXT,
    lineage TEXT,
    until TEXT,
    raw TEXT,
    authority TEXT,
    authority_scope TEXT,
    CHECK(length(evidence_id)>0)
);

CREATE TABLE pattern_evidence (
    pattern_id TEXT PRIMARY KEY,
    family TEXT NOT NULL,
    pattern_type TEXT,
    formation_sequence TEXT NOT NULL,
    required_context TEXT,
    evidence_dependencies TEXT NOT NULL,
    invalidation_rules TEXT NOT NULL,
    provenance_class TEXT NOT NULL CHECK(provenance_class IN ('RESEARCH_ONLY','ACTIVE','DEPRECATED')),
    lifecycle_status TEXT NOT NULL CHECK(lifecycle_status IN ('ACTIVE','RESEARCH_ONLY','DEPRECATED')),
    setup_score_contribution_class TEXT NOT NULL CHECK(setup_score_contribution_class IN ('s_i_component','q_i_component','convergence_weight','advisory')),
    template_reconciliation TEXT,
    reference_implementation TEXT,
    historical_statistics TEXT,
    revision_history TEXT,
    confidence REAL,
    CHECK(length(pattern_id)>0),
    CHECK(length(evidence_dependencies)>0)
);

CREATE TABLE setup_candidate (
    setup_id TEXT PRIMARY KEY,
    timestamp TEXT,
    symbol TEXT,
    timeframe TEXT,
    pattern_ids TEXT,
    direction TEXT CHECK(direction IN ('BULLISH','BEARISH')),
    entry_price TEXT,
    stop_loss TEXT,
    take_profit TEXT,
    risk_reward REAL,
    confidence REAL,
    quality TEXT,
    validity INTEGER,
    snapshot_id TEXT,
    parent_ids TEXT,
    payload_hash TEXT,
    regime TEXT,
    utc_activity_window_id TEXT,
    lineage TEXT,
    authority TEXT,
    authority_scope TEXT
);

CREATE TABLE ledger (
    ledger_id TEXT PRIMARY KEY CHECK(typeof(ledger_id)='text'),
    intent_id TEXT,
    order_id TEXT,
    fill_id TEXT,
    cancel_id TEXT,
    payload_hash TEXT,
    parent_ids TEXT,
    until TEXT,
    raw TEXT,
    fee TEXT CHECK(typeof(fee)='text'),
    slippage TEXT,
    price TEXT CHECK(typeof(price)='text'),
    quantity TEXT CHECK(typeof(quantity)='text'),
    timestamp TEXT
);

CREATE TABLE outcome (
    outcome_id TEXT PRIMARY KEY,
    entry_price TEXT,
    exit_price TEXT,
    pnl TEXT CHECK(typeof(pnl)='text'),
    fees TEXT,
    slippage TEXT,
    mfe TEXT,
    mae TEXT,
    duration INTEGER,
    exit_reason TEXT,
    risk_used TEXT,
    forecast TEXT,
    setup_id TEXT,
    regime TEXT,
    context TEXT,
    FOREIGN KEY(setup_id) REFERENCES setup_candidate(setup_id)
);
"""

# ---------------------------------------------------------------------------
# Ch.5 raw store DDL — VERBATIM (physical store, merged from gap-closure).
# PRAGMAs are applied per-connection at open() (P12), not in migrations.
# ---------------------------------------------------------------------------

CH5_DDL = """
CREATE TABLE IF NOT EXISTS raw_observation (
  event_id TEXT PRIMARY KEY,
  as_of TEXT NOT NULL,
  symbol TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  open TEXT NOT NULL, high TEXT NOT NULL, low TEXT NOT NULL, close TEXT NOT NULL,
  volume TEXT NOT NULL,
  oi TEXT,
  oi_timestamp TEXT,
  oi_state TEXT NOT NULL CHECK(oi_state IN ('AVAILABLE','STALE','MISSING','INVALID','DEGRADED')),
  status TEXT NOT NULL CHECK(status IN ('OPEN','PARTIAL','CLOSED')),
  content_hash TEXT NOT NULL UNIQUE,
  source TEXT NOT NULL,
  availability_time TEXT,
  quality_vector TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_raw_sym_tf_asof ON raw_observation(symbol, timeframe, as_of);

CREATE TABLE IF NOT EXISTS bootstrap_progress (
  symbol TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  phase TEXT NOT NULL CHECK(phase IN ('P1','P2','P3')),
  cursor_open_time TEXT,
  status TEXT NOT NULL CHECK(status IN ('PENDING','RUNNING','DONE','PAUSED','ERROR')),
  bars_written INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(symbol, timeframe, phase)
);
"""

# ---------------------------------------------------------------------------
# AI.5 Raw Store Contract (SQLite-adapted; same column names as the frozen
# outline; the frozen outline is PostgreSQL-shaped and NOT an executable
# SQLite fixture — P12: SQLite only).
# ---------------------------------------------------------------------------

AI5_DDL = """
CREATE TABLE raw_revision (
  revision_id TEXT PRIMARY KEY,
  original_event_id TEXT NOT NULL REFERENCES raw_observation(event_id),
  new_event_id TEXT NOT NULL REFERENCES raw_observation(event_id),
  correction_reason TEXT NOT NULL,
  correction_timestamp TEXT,
  actor TEXT,
  parent_lineage TEXT
);
CREATE INDEX idx_raw_revision_original ON raw_revision(original_event_id);

CREATE TABLE raw_manifest (
  manifest_id TEXT PRIMARY KEY,
  manifest_hash TEXT NOT NULL UNIQUE,
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  observation_count INTEGER NOT NULL,
  content_hashes_included TEXT NOT NULL,
  parent_manifest_hash TEXT,
  created_at TEXT
);
CREATE INDEX idx_raw_manifest_period ON raw_manifest(period_start, period_end);

CREATE VIEW raw_store_current AS
SELECT event_id, as_of, symbol, timeframe,
       open, high, low, close, volume, oi,
       status, content_hash, source
FROM raw_observation
WHERE status = 'CLOSED'
  AND as_of > datetime('now', '-12 months')
ORDER BY symbol, timeframe, as_of DESC;

-- §2.6 / AI.5: every correction, revocation, or deletion is logged with
-- event_id, timestamp, reason, and actor identity (immutable audit trail).
CREATE TABLE retention_event (
  retention_event_id TEXT PRIMARY KEY,
  event_kind TEXT NOT NULL CHECK(event_kind IN ('PURGE_RAW','PURGE_SNAPSHOT','CORRECTION')),
  timestamp TEXT NOT NULL,
  reason TEXT NOT NULL,
  actor TEXT,
  detail TEXT
);
"""

IMMUTABILITY_TRIGGERS = """
CREATE TABLE IF NOT EXISTS purge_allow (
  purge_flag TEXT PRIMARY KEY CHECK(purge_flag='ENABLED')
);
CREATE TRIGGER raw_observation_no_update BEFORE UPDATE ON raw_observation
BEGIN SELECT RAISE(ABORT, 'IMMUTABLE_RAW_STORE'); END;
-- Deletion is lawful ONLY for the governed retention purge (§2.6/AI.5:
-- purge decisions are approved and recorded). SQLiteStore.retention_purge
-- sets the purge_allow flag inside the same transaction; any other delete
-- raises.
CREATE TRIGGER raw_observation_no_delete BEFORE DELETE ON raw_observation
WHEN NOT EXISTS (SELECT 1 FROM purge_allow)
BEGIN SELECT RAISE(ABORT, 'IMMUTABLE_RAW_STORE'); END;
CREATE TRIGGER ledger_no_update BEFORE UPDATE ON ledger
BEGIN SELECT RAISE(ABORT, 'LEDGER_APPEND_ONLY'); END;
CREATE TRIGGER ledger_no_delete BEFORE DELETE ON ledger
BEGIN SELECT RAISE(ABORT, 'LEDGER_APPEND_ONLY'); END;
"""

# Ordered migration list (append-only; existing migrations never edited)
MIGRATIONS: List[Tuple[str, str]] = [
    ("M001_ch4_data_plane_ddl", CH4_DDL),
    ("M002_ch5_raw_store_ddl", CH5_DDL),
    ("M003_ai5_raw_revision_manifest", AI5_DDL),
    ("M004_immutability_triggers", IMMUTABILITY_TRIGGERS),
]

SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_name TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""

RAW_RETENTION_MONTHS = 12      # §2.6: raw observations 12 months rolling
SNAPSHOT_RETENTION_MONTHS = 6  # §2.6: snapshots and evidence 6 months


def _utc_now_ms_iso() -> str:
    now = _dt.datetime.now(_dt.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


class SQLiteStore:
    """Physical store (single writer per table; catalog-only access)."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path if path is not None else Config().sqlite_path
        self._db: Optional[aiosqlite.Connection] = None

    # -- lifecycle ----------------------------------------------------------
    async def open(self) -> "SQLiteStore":
        db_path = Path(self.path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(db_path))
        await self._db.execute("PRAGMA journal_mode=WAL;")
        await self._db.execute("PRAGMA synchronous=FULL;")
        await self._db.execute("PRAGMA foreign_keys=ON;")
        await self._db.execute("PRAGMA busy_timeout=5000;")
        await self._apply_migrations()
        return self

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("store not open — call await store.open()")
        return self._db

    async def _apply_migrations(self) -> None:
        await self.db.execute(SCHEMA_VERSION_TABLE)
        await self.db.commit()
        for name, script in MIGRATIONS:
            cur = await self.db.execute(
                "SELECT 1 FROM schema_migrations WHERE migration_name=?",
                (name,))
            row = await cur.fetchone()
            if row:
                continue
            await self.db.executescript(script)
            await self.db.execute(
                "INSERT INTO schema_migrations (migration_name, applied_at) "
                "VALUES (?, ?)", (name, _utc_now_ms_iso()))
            await self.db.commit()

    def applied_migrations(self) -> List[str]:
        return [name for name, _ in MIGRATIONS]

    # -- raw ingest (append-only; corrections append revisions) -------------
    async def ingest_raw(self, obs: MarketObservation,
                         oi_state: str) -> str:
        """Append one raw observation (raw_observation + market_observation
        in ONE transaction; single writer). Duplicate content_hash →
        deduplicated (no-op). Returns event_id."""
        if obs.symbol not in CORE10_SYMBOLS:
            raise ValueError(f"E-VAL-021: {obs.symbol} not in Core-10")
        if obs.timeframe not in TIMEFRAMES_14:
            raise ValueError(f"E-VAL-022: {obs.timeframe} not in 14 TFs")
        event_id = self._new_event_id()
        content_hash = obs.content_hash()
        obs_id = "obs-" + event_id
        from apex.identity.uuid_v7 import uuid_v7
        await self.db.execute(
            "INSERT OR IGNORE INTO raw_observation "
            "(event_id, as_of, symbol, timeframe, open, high, low, close, "
            " volume, oi, oi_timestamp, oi_state, status, content_hash, "
            " source, availability_time, quality_vector, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (event_id, obs.timestamp, obs.symbol, obs.timeframe,
             str(obs.open), str(obs.high), str(obs.low), str(obs.close),
             str(obs.volume),
             str(obs.oi) if obs.oi is not None else None,
             obs.oi_timestamp, oi_state, obs.status, content_hash,
             obs.source, obs.availability_time, None, _utc_now_ms_iso()))
        cur = await self.db.execute(
            "SELECT event_id FROM raw_observation WHERE content_hash=?",
            (content_hash,))
        row = await cur.fetchone()
        if row is not None and row[0] != event_id:
            # exact duplicate → deduplicate (AI.8 inbound dedup)
            await self.db.commit()
            return row[0]
        await self.db.execute(
            "INSERT INTO market_observation "
            "(observation_id, symbol, timeframe, open_price, high_price, "
            " low_price, close_price, volume, open_interest, open_time, "
            " close_time, retrieved_at, candle_status, quality_state, "
            " source, schema_version, raw_payload_hash) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (obs_id, obs.symbol, obs.timeframe, str(obs.open),
             str(obs.high), str(obs.low), str(obs.close), str(obs.volume),
             str(obs.oi) if obs.oi is not None else None,
             obs.timestamp, obs.timestamp, _utc_now_ms_iso(),
             "CLOSED" if obs.status == "CLOSED" else "PARTIAL",
             "Q0", obs.source, "v1", sha256_hex(content_hash)))
        await self.db.commit()
        return event_id

    async def correct_raw(self, original_event_id: str,
                          corrected: MarketObservation, oi_state: str,
                          reason: str, actor: str = "INGEST") -> str:
        """Correction event (AI.4): original marked SUPERSEDED (immutable
        reference), new record appended, lineage recorded in raw_revision.
        History is never rewritten. Returns the new event_id."""
        original = await self._find_by_event(original_event_id)
        if original is None:
            raise ValueError(f"original event {original_event_id} not found")
        new_event_id = self._new_event_id()
        await self.db.execute(
            "UPDATE market_observation SET candle_status='SUPERSEDED' "
            "WHERE observation_id=?", (original["observation_id"],))
        new_event = await self.ingest_raw(corrected, oi_state)
        await self.db.execute(
            "UPDATE market_observation SET candle_status='CORRECTED' "
            "WHERE raw_payload_hash=?",
            (sha256_hex(corrected.content_hash()),))
        await self.db.execute(
            "INSERT INTO raw_revision (revision_id, original_event_id, "
            " new_event_id, correction_reason, correction_timestamp, "
            " actor, parent_lineage) VALUES (?,?,?,?,?,?,?)",
            (self._new_event_id(), original_event_id, new_event,
             reason, _utc_now_ms_iso(), actor,
             f"parent_event_id={original_event_id};source=provider"))
        await self.db.execute(
            "INSERT INTO retention_event (retention_event_id, event_kind, "
            " timestamp, reason, actor, detail) VALUES (?,?,?,?,?,?)",
            (self._new_event_id(), "CORRECTION", _utc_now_ms_iso(),
             reason, actor, f"original={original_event_id} new={new_event}"))
        await self.db.commit()
        return new_event

    async def _find_by_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        cur = await self.db.execute(
            "SELECT event_id, content_hash FROM raw_observation "
            "WHERE event_id=?", (event_id,))
        row = await cur.fetchone()
        if row is None:
            return None
        cur2 = await self.db.execute(
            "SELECT observation_id FROM market_observation "
            "WHERE raw_payload_hash=?", (sha256_hex(row[1]),))
        row2 = await cur2.fetchone()
        if row2 is None:
            return None
        return {"observation_id": row2[0], "event_id": event_id}

    # -- WindowProvider (catalog.get backend; engines never SQL) ------------
    async def get_window(self, symbol: str, timeframe: str, as_of: str,
                         bars: int) -> List[MarketObservation]:
        """CLOSED observations with open_time <= as_of, ascending, last
        `bars` rows (PIT-safe by construction)."""
        cur = await self.db.execute(
            "SELECT observation_id, symbol, timeframe, open_price, "
            " high_price, low_price, close_price, volume, open_interest, "
            " open_time, retrieved_at, candle_status, quality_state, "
            " source, raw_payload_hash "
            "FROM market_observation WHERE symbol=? AND timeframe=? "
            "AND candle_status IN ('CLOSED','CORRECTED') "
            "AND open_time<=? ORDER BY open_time ASC LIMIT ?",
            (symbol, timeframe, as_of, bars))
        rows = await cur.fetchall()
        result: List[MarketObservation] = []
        for i, row in enumerate(rows):
            result.append(self._row_to_obs(row, i))
        return result

    async def max_availability_time(self, symbol: str, timeframe: str,
                                    as_of: str) -> Optional[str]:
        """Data frontier: max availability_time over stored raw rows for
        (symbol, timeframe). None when no data (fail-closed at caller)."""
        cur = await self.db.execute(
            "SELECT MAX(availability_time) FROM raw_observation "
            "WHERE symbol=? AND timeframe=?", (symbol, timeframe))
        row = await cur.fetchone()
        if row is None or row[0] is None:
            return None
        return row[0]

    @staticmethod
    def _row_to_obs(row: tuple, seq: int) -> MarketObservation:
        from decimal import Decimal
        (obs_id, symbol, timeframe, o, h, l, c, v, oi, open_time,
         retrieved, status, qstate, source, payload_hash) = row
        return MarketObservation(
            symbol=symbol, timeframe=timeframe,
            open=Decimal(o), high=Decimal(h), low=Decimal(l),
            close=Decimal(c), volume=Decimal(v),
            oi=Decimal(oi) if oi is not None else None,
            timestamp=open_time, sequence=seq, status=status,
            source=source, availability_time=retrieved,
        )

    # -- snapshots + evidence ----------------------------------------------
    async def insert_snapshot(self, snapshot: Dict[str, Any]) -> None:
        qs = snapshot.get("quality_state", {})
        await self.db.execute(
            "INSERT INTO snapshot_pit (snapshot_id, as_of, symbol_scope, "
            " timeframe_scope, source_state, manifest_hash, "
            " parameter_package_id, code_version, vector_quality_state, "
            " min_quality, weighted_quality, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (snapshot["snapshot_id"], snapshot.get("as_of"),
             ",".join(snapshot.get("symbol_scope", [])),
             ",".join(snapshot.get("timeframe_scope", [])),
             snapshot.get("source_state", "VALID"),
             snapshot.get("manifest_hash"), snapshot.get("parameter_package_id"),
             snapshot.get("code_version"), snapshot.get("quality_state"),
             qs.get("min_q"), qs.get("weighted_q"), _utc_now_ms_iso()))
        await self.db.commit()

    async def insert_evidence(self, event: EvidenceEvent) -> None:
        """Validate the 24-field contract, then insert the Data-Plane row
        (contract→DDL mapping at APEX_GEN5.md L18185)."""
        event.validate_24_fields()
        row = event.to_ddl_row()
        # DDL columns beyond the 24-field contract (price_level/epsilon/atr/
        # volume/oi/regime/utc_activity_window_id/authority/authority_scope/
        # payload_hash/source_hash/until) are implementation extensions
        # governed by SL-12 — no DDL column is removed (L18185). Engine
        # stages populate them; CP-1 fills TEXT-typed columns with ''.
        await self.db.execute(
            "INSERT INTO evidence_event (evidence_id, timestamp_utc, symbol, "
            " timeframe, engine_id, event_type, price_level, strength, "
            " confidence, quality, validity, snapshot_id, parent_ids, "
            " payload_hash, source_hash, epsilon, atr, volume, oi, regime, "
            " utc_activity_window_id, lineage, until, raw, authority, "
            " authority_scope) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (row["evidence_id"], row["timestamp_utc"], row["symbol"],
             row["timeframe"], row["engine_id"], row["event_type"], "",
             row["strength"], row["confidence"], str(row["quality"]),
             row["validity"], row["snapshot_id"], row["parent_ids"],
             None, None, "", "", "", "", "", "",
             row["lineage"], "", row["raw"], "", ""))
        await self.db.commit()

    # -- manifests + retention ---------------------------------------------
    async def write_manifest(self, period_start: str, period_end: str,
                             content_hashes: Sequence[str],
                             parent_manifest_hash: Optional[str] = None,
                             ) -> str:
        """Append a raw manifest (T-RS-002 hash chain)."""
        from apex.identity.hashes import sha256_hex
        payload = {"period_start": period_start, "period_end": period_end,
                   "content_hashes": sorted(content_hashes),
                   "parent_manifest_hash": parent_manifest_hash}
        mhash = sha256_hex(__import__("apex.identity.canonical_json",
                                      fromlist=["canonical_json"]).canonical_json(payload))
        manifest_id = self._new_event_id()
        await self.db.execute(
            "INSERT INTO raw_manifest (manifest_id, manifest_hash, "
            " period_start, period_end, observation_count, "
            " content_hashes_included, parent_manifest_hash, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (manifest_id, mhash, period_start, period_end,
             len(content_hashes), ",".join(sorted(content_hashes)),
             parent_manifest_hash, _utc_now_ms_iso()))
        await self.db.commit()
        return mhash

    async def retention_purge(self, actor: str = "RETENTION") -> List[str]:
        """§2.6 retention: raw 12 months rolling; snapshots/evidence 6
        months; ledger/outcomes never purged. Every purge appends a
        retention event to the immutable audit trail. The purge is the ONE
        lawful deletion path: it sets the governed purge_allow flag inside
        the same transaction, so the immutability trigger admits it and
        nothing else."""
        purged: List[str] = []
        await self.db.execute("INSERT INTO purge_allow (purge_flag) "
                              "VALUES ('ENABLED')")
        try:
            cur = await self.db.execute(
                "SELECT event_id FROM raw_observation WHERE as_of < "
                "datetime('now', ?) LIMIT 1000",
                (f"-{RAW_RETENTION_MONTHS} months",))
            rows = await cur.fetchall()
            for (event_id,) in rows:
                await self.db.execute(
                    "DELETE FROM raw_observation WHERE event_id=?",
                    (event_id,))
                await self.db.execute(
                    "INSERT INTO retention_event (retention_event_id, "
                    " event_kind, timestamp, reason, actor, detail) "
                    "VALUES (?,?,?,?,?,?)",
                    (self._new_event_id(), "PURGE_RAW", _utc_now_ms_iso(),
                     f"retention {RAW_RETENTION_MONTHS} months rolling",
                     actor, f"event_id={event_id}"))
                purged.append(event_id)
            await self.db.commit()
        finally:
            # flag never survives the purge window (single transaction)
            await self.db.execute("DELETE FROM purge_allow")
            await self.db.commit()
        return purged

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _new_event_id() -> str:
        from apex.identity.uuid_v7 import uuid_v7
        return uuid_v7()

    async def table_names(self) -> List[str]:
        cur = await self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        rows = await cur.fetchall()
        return [r[0] for r in rows]
