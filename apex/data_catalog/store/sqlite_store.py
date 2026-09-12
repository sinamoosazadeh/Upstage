"""APEX_GEN5 physical store — SQLite WAL at ``APEX_SQLITE_PATH`` (Ch.4/Ch.5).

Binding rules implemented:
* Ch.4 Data Plane DDL and Ch.5 Trading Universe DDL are executed VERBATIM
  (every table/index/constraint name preserved — the DDL constants below are
  copy-exact and are asserted against APEX_GEN5.md in tests).
* Physical store: SQLite WAL, synchronous=FULL, foreign_keys=ON,
  busy_timeout=5000 (Ch.5). PostgreSQL is Wave-Out (§9.5-9).
* Money/prices are TEXT Decimal strings at the store boundary (P12).
* Ledgers and raw stores are append-only and hash-chained; corrections
  append revisions, never rewrite (P12, AI.5). Append-only is enforced AT
  THE DB LEVEL via triggers (T-RS-001). The ONLY governed deletion path is
  retention (§2.6), which runs under an explicit lease and appends an
  immutable audit event (§2.6: "all purging appends a retention event").
* Retention (governed): raw observations 12 months rolling; snapshots and
  evidence 6 months; ledger and outcomes immutable, never purged (§2.6/AI.5).
* AI.5 lineage tables (raw_revision, raw_manifest) + audit_event are additive
  tables required by the blueprint chapter (ADR-P2-003), adapted to the
  SQLite TEXT-decimal physical convention (the AI.5 PostgreSQL outline is
  explicitly "not a SQLite executable fixture").
"""
from __future__ import annotations

import pathlib
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import sha256_hex
from apex.identity.uuid_v7 import uuid_v7

__all__ = [
    "CH4_DDL",
    "CH5_DDL",
    "MIGRATIONS",
    "RAW_RETENTION_DAYS",
    "SNAPSHOT_EVIDENCE_RETENTION_DAYS",
    "StoreError",
    "AppendOnlyViolation",
    "SqliteStore",
    "utc_now_iso",
]

RAW_RETENTION_DAYS = 365            # §2.6 raw observations 12 months rolling
SNAPSHOT_EVIDENCE_RETENTION_DAYS = 180  # §2.6 snapshots and evidence 6 months


class StoreError(RuntimeError):
    """Store-level fail-closed error."""


class AppendOnlyViolation(StoreError):
    """Attempted mutation of an append-only table (blocked by DB trigger)."""


def utc_now_iso() -> str:
    """AI.3 canonical timestamp: ISO-8601 UTC, millisecond precision, Z."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


# ---------------------------------------------------------------------------
# Ch.4 Data Plane DDL — VERBATIM (APEX_GEN5.md L14389-L14539)
# ---------------------------------------------------------------------------
CH4_DDL = """CREATE TABLE market_observation (
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
);"""

# ---------------------------------------------------------------------------
# Ch.5 Trading Universe DDL — VERBATIM (APEX_GEN5.md L14549-L14580)
# ---------------------------------------------------------------------------
CH5_DDL = """PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;

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
);"""

# ---------------------------------------------------------------------------
# Additive migrations (blueprint-required: AI.5 lineage + §2.6 retention
# audit + append-only triggers; ADR-P2-003 logged).
# ---------------------------------------------------------------------------
_AI5_LINEAGE_DDL = """CREATE TABLE IF NOT EXISTS raw_revision (
  revision_id TEXT PRIMARY KEY,
  original_event_id TEXT NOT NULL REFERENCES raw_observation(event_id),
  new_event_id TEXT NOT NULL REFERENCES raw_observation(event_id),
  correction_reason TEXT NOT NULL,
  correction_timestamp TEXT NOT NULL,
  actor TEXT,
  parent_lineage TEXT
);
CREATE INDEX IF NOT EXISTS idx_raw_revision_original ON raw_revision(original_event_id);

CREATE TABLE IF NOT EXISTS raw_manifest (
  manifest_id TEXT PRIMARY KEY,
  seq INTEGER NOT NULL UNIQUE,
  symbol TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  event_id TEXT NOT NULL REFERENCES raw_observation(event_id),
  content_hash TEXT NOT NULL,
  chain_hash TEXT NOT NULL,
  prev_chain_hash TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_event (
  audit_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  target_table TEXT NOT NULL,
  target_id TEXT,
  reason TEXT NOT NULL,
  actor TEXT,
  detail TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS _retention_lease (
  lease TEXT PRIMARY KEY CHECK(lease='RETENTION_ACTIVE'),
  started_at TEXT NOT NULL
);"""

# Append-only enforcement at the DB level (AI.5/P12/T-RS-001). raw_observation
# DELETE is permitted ONLY while the governed retention lease is held (§2.6);
# every other mutation is always rejected.
_APPEND_ONLY_TRIGGERS = """CREATE TRIGGER raw_observation_no_update BEFORE UPDATE ON raw_observation
BEGIN
  SELECT RAISE(ABORT, 'append-only: raw_observation UPDATE forbidden');
END;
CREATE TRIGGER raw_observation_no_delete BEFORE DELETE ON raw_observation
WHEN NOT EXISTS (SELECT 1 FROM _retention_lease WHERE lease='RETENTION_ACTIVE')
BEGIN
  SELECT RAISE(ABORT, 'append-only: raw_observation DELETE forbidden');
END;
CREATE TRIGGER ledger_no_update BEFORE UPDATE ON ledger
BEGIN
  SELECT RAISE(ABORT, 'append-only: ledger UPDATE forbidden');
END;
CREATE TRIGGER ledger_no_delete BEFORE DELETE ON ledger
BEGIN
  SELECT RAISE(ABORT, 'append-only: ledger DELETE forbidden');
END;
CREATE TRIGGER outcome_no_update BEFORE UPDATE ON outcome
BEGIN
  SELECT RAISE(ABORT, 'append-only: outcome UPDATE forbidden');
END;
CREATE TRIGGER outcome_no_delete BEFORE DELETE ON outcome
BEGIN
  SELECT RAISE(ABORT, 'append-only: outcome DELETE forbidden');
END;
CREATE TRIGGER audit_event_no_update BEFORE UPDATE ON audit_event
BEGIN
  SELECT RAISE(ABORT, 'append-only: audit_event UPDATE forbidden');
END;
CREATE TRIGGER audit_event_no_delete BEFORE DELETE ON audit_event
BEGIN
  SELECT RAISE(ABORT, 'append-only: audit_event DELETE forbidden');
END;
CREATE TRIGGER raw_manifest_no_update BEFORE UPDATE ON raw_manifest
BEGIN
  SELECT RAISE(ABORT, 'append-only: raw_manifest UPDATE forbidden');
END;
CREATE TRIGGER raw_manifest_no_delete BEFORE DELETE ON raw_manifest
BEGIN
  SELECT RAISE(ABORT, 'append-only: raw_manifest DELETE forbidden');
END;"""

MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("0001_ch4_data_plane", CH4_DDL),
    ("0002_ch5_universe", CH5_DDL),
    ("0003_ai5_lineage", _AI5_LINEAGE_DDL),
    ("0004_append_only_triggers", _APPEND_ONLY_TRIGGERS),
)


class SqliteStore:
    """The one physical store (Ch.4: "All runtime state that must survive a
    process death lives in one SQLite database on the device")."""

    def __init__(self, path: str | pathlib.Path) -> None:
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._configure()

    def _configure(self) -> None:
        # Ch.5 pragmas (also executed by migration 0002 for fresh files)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")

    # -- lifecycle -----------------------------------------------------------

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SqliteStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    # -- migrations -----------------------------------------------------------

    def apply_migrations(self) -> list[str]:
        """Apply pending migrations in order; record each in schema_migrations.
        Returns names applied in this call (idempotent)."""
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        applied_now: list[str] = []
        for name, sql in MIGRATIONS:
            row = self._conn.execute(
                "SELECT 1 FROM schema_migrations WHERE name=?", (name,)
            ).fetchone()
            if row:
                continue
            self._conn.executescript(sql)
            self._conn.execute(
                "INSERT INTO schema_migrations(name, applied_at) VALUES(?, ?)",
                (name, utc_now_iso()),
            )
            applied_now.append(name)
        self._conn.commit()
        return applied_now

    # -- market observations (Ch.4) ---------------------------------------------

    def insert_market_observation(self, row: Mapping[str, Any]) -> str:
        observation_id = row.get("observation_id") or uuid_v7()
        if not isinstance(row.get("open_interest"), str):
            # DDL boundary: open_interest is REQUIRED TEXT. Missing OI is a
            # raw-store state (raw_observation.oi_state='MISSING'); it is
            # never coerced to 0 or NULL here (T-DC-004 / AI.6). Fail closed.
            raise StoreError(
                "FAIL_CLOSED: market_observation.open_interest must be a TEXT value; "
                "missing OI belongs to raw_observation.oi_state, never to a silent default"
            )
        self._conn.execute(
            """INSERT INTO market_observation
               (observation_id, symbol, timeframe, open_price, high_price,
                low_price, close_price, volume, open_interest, open_time,
                close_time, retrieved_at, candle_status, quality_state,
                source, schema_version, raw_payload_hash)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                observation_id,
                row["symbol"],
                row["timeframe"],
                row["open_price"],
                row["high_price"],
                row["low_price"],
                row["close_price"],
                row["volume"],
                row.get("open_interest"),
                row["open_time"],
                row["close_time"],
                row.get("retrieved_at", utc_now_iso()),
                row.get("candle_status", "CLOSED"),
                row.get("quality_state", "Q0"),
                row.get("source", "toobit"),
                row.get("schema_version", "v4.0.0"),
                row.get("raw_payload_hash"),
            ),
        )
        self._conn.commit()
        return observation_id

    def supersede_observation(
        self,
        original_observation_id: str,
        correction: Mapping[str, Any],
        reason: str,
        actor: str = "system",
    ) -> str:
        """T-CL-001 correction lifecycle: the correction is logged as a NEW
        record (status CORRECTED); the original is marked SUPERSEDED (its row
        is never rewritten — only its governed status column transitions);
        lineage is preserved in raw_revision + audit_event."""
        original = self._conn.execute(
            "SELECT * FROM market_observation WHERE observation_id=?",
            (original_observation_id,),
        ).fetchone()
        if original is None:
            raise StoreError(f"unknown observation: {original_observation_id}")
        new_row = dict(correction)
        new_row.setdefault("symbol", original["symbol"])
        new_row.setdefault("timeframe", original["timeframe"])
        new_row.setdefault("open_price", original["open_price"])
        new_row.setdefault("high_price", original["high_price"])
        new_row.setdefault("low_price", original["low_price"])
        new_row.setdefault("close_price", original["close_price"])
        new_row.setdefault("volume", original["volume"])
        new_row.setdefault("open_interest", original["open_interest"])
        new_row.setdefault("open_time", original["open_time"])
        new_row.setdefault("close_time", original["close_time"])
        new_row["candle_status"] = "CORRECTED"
        new_id = self.insert_market_observation(new_row)
        self._conn.execute(
            "UPDATE market_observation SET candle_status='SUPERSEDED' WHERE observation_id=?",
            (original_observation_id,),
        )
        self._append_audit(
            "CORRECTION",
            "market_observation",
            original_observation_id,
            reason,
            actor,
            detail=canonical_json(
                {"original_observation_id": original_observation_id, "new_observation_id": new_id}
            ),
        )
        self._conn.commit()
        return new_id

    def insert_raw_revision(
        self, original_event_id: str, new_event_id: str, reason: str, actor: str = "system"
    ) -> str:
        """AI.5 raw-store revision lineage (both events live in raw_observation:
        corrections are new records, never rewrites)."""
        revision_id = uuid_v7()
        self._conn.execute(
            """INSERT INTO raw_revision
               (revision_id, original_event_id, new_event_id, correction_reason,
                correction_timestamp, actor, parent_lineage)
               VALUES (?,?,?,?,?,?,?)""",
            (
                revision_id,
                original_event_id,
                new_event_id,
                reason,
                utc_now_iso(),
                actor,
                canonical_json({"parent": original_event_id}),
            ),
        )
        self._append_audit("RAW_REVISION", "raw_observation", original_event_id, reason, actor)
        self._conn.commit()
        return revision_id

    # -- raw store (Ch.5 + AI.5) -------------------------------------------------

    def insert_raw_observation(self, row: Mapping[str, Any]) -> str:
        event_id = row.get("event_id") or uuid_v7()
        payload_for_hash = {
            "as_of": row["as_of"],
            "symbol": row["symbol"],
            "timeframe": row["timeframe"],
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row["volume"],
            "oi": row.get("oi"),
        }
        content_hash = row.get("content_hash") or sha256_hex(canonical_json(payload_for_hash))
        self._conn.execute(
            """INSERT INTO raw_observation
               (event_id, as_of, symbol, timeframe, open, high, low, close,
                volume, oi, oi_timestamp, oi_state, status, content_hash,
                source, availability_time, quality_vector, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event_id,
                row["as_of"],
                row["symbol"],
                row["timeframe"],
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row["volume"],
                row.get("oi"),
                row.get("oi_timestamp"),
                row.get("oi_state", "MISSING"),
                row.get("status", "CLOSED"),
                content_hash,
                row.get("source", "toobit"),
                row.get("availability_time"),
                row.get("quality_vector"),
                row.get("created_at", utc_now_iso()),
            ),
        )
        self._conn.commit()
        return event_id

    def append_raw_manifest(self, event_id: str, symbol: str, timeframe: str) -> str:
        """Hash-chained manifest (T-RS-002): chain_hash =
        SHA256(canonical_json({seq, event_id, content_hash, prev_chain_hash}))."""
        row = self._conn.execute(
            "SELECT content_hash FROM raw_observation WHERE event_id=?", (event_id,)
        ).fetchone()
        if row is None:
            raise StoreError(f"manifest for unknown event: {event_id}")
        last = self._conn.execute(
            "SELECT seq, chain_hash FROM raw_manifest ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        seq = 0 if last is None else last["seq"] + 1
        prev = None if last is None else last["chain_hash"]
        chain_hash = sha256_hex(
            canonical_json(
                {"seq": seq, "event_id": event_id, "content_hash": row["content_hash"], "prev_chain_hash": prev}
            )
        )
        manifest_id = uuid_v7()
        self._conn.execute(
            """INSERT INTO raw_manifest
               (manifest_id, seq, symbol, timeframe, event_id, content_hash,
                chain_hash, prev_chain_hash, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (manifest_id, seq, symbol, timeframe, event_id, row["content_hash"], chain_hash, prev, utc_now_iso()),
        )
        self._conn.commit()
        return manifest_id

    def verify_hash_chain(self) -> bool:
        """Recompute every manifest hash; any mismatch breaks integrity."""
        rows = self._conn.execute(
            "SELECT seq, event_id, content_hash, chain_hash, prev_chain_hash "
            "FROM raw_manifest ORDER BY seq ASC"
        ).fetchall()
        prev = None
        for i, r in enumerate(rows):
            expected = sha256_hex(
                canonical_json(
                    {"seq": r["seq"], "event_id": r["event_id"], "content_hash": r["content_hash"], "prev_chain_hash": r["prev_chain_hash"]}
                )
            )
            if expected != r["chain_hash"] or r["prev_chain_hash"] != prev or r["seq"] != i:
                return False
            prev = r["chain_hash"]
        return True

    # -- audit ------------------------------------------------------------------

    def _append_audit(
        self, event_type: str, target_table: str, target_id: str | None, reason: str, actor: str, detail: str | None = None
    ) -> str:
        audit_id = uuid_v7()
        self._conn.execute(
            """INSERT INTO audit_event
               (audit_id, event_type, target_table, target_id, reason, actor, detail, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (audit_id, event_type, target_table, target_id, reason, actor, detail, utc_now_iso()),
        )
        return audit_id

    # -- retention (§2.6, AI.5) ----------------------------------------------------

    def enforce_retention(self, now_iso: str, actor: str = "retention") -> dict[str, int]:
        """12-month rolling raw observations; 6-month snapshots/evidence;
        ledger and outcomes NEVER purged. Every purge appends an immutable
        retention audit event (§2.6). Runs under the retention lease — the
        only governed deletion path."""
        from datetime import timedelta

        now = datetime.strptime(now_iso, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=None)

        def cutoff(days: int) -> str:
            c = now - timedelta(days=days)
            return c.strftime("%Y-%m-%dT%H:%M:%S.") + f"{c.microsecond // 1000:03d}Z"

        raw_cut = cutoff(RAW_RETENTION_DAYS)
        se_cut = cutoff(SNAPSHOT_EVIDENCE_RETENTION_DAYS)
        purged: dict[str, int] = {}
        self._conn.execute(
            "INSERT INTO _retention_lease(lease, started_at) VALUES('RETENTION_ACTIVE', ?)",
            (utc_now_iso(),),
        )
        try:
            # manifests referencing expiring raw rows go with them (both are
            # raw-store lineage; ledger/outcome stay permanent) — inside lease
            self._conn.execute(
                "DELETE FROM raw_manifest WHERE event_id IN "
                "(SELECT event_id FROM raw_observation WHERE created_at < ?)",
                (raw_cut,),
            )
            cur = self._conn.execute("DELETE FROM raw_observation WHERE created_at < ?", (raw_cut,))
            purged["raw_observation"] = cur.rowcount
            cur = self._conn.execute("DELETE FROM snapshot_pit WHERE created_at < ?", (se_cut,))
            purged["snapshot_pit"] = cur.rowcount
            cur = self._conn.execute("DELETE FROM evidence_event WHERE timestamp_utc < ?", (se_cut,))
            purged["evidence_event"] = cur.rowcount
            for table, count in purged.items():
                if count:
                    self._append_audit(
                        "RETENTION_PURGE",
                        table,
                        None,
                        f"governed retention purged {count} rows older than policy cutoff",
                        actor,
                        detail=canonical_json({"cutoff": raw_cut if table == "raw_observation" else se_cut}),
                    )
        finally:
            self._conn.execute("DELETE FROM _retention_lease WHERE lease='RETENTION_ACTIVE'")
        self._conn.commit()
        return purged

    # -- ledger (append-only, hash-chained; P12) ------------------------------------

    def append_ledger_entry(self, row: Mapping[str, Any]) -> str:
        ledger_id = row.get("ledger_id") or uuid_v7()
        for required in ("fee", "price", "quantity"):
            if not isinstance(row.get(required), str):
                # DDL boundary: ledger money fields are REQUIRED TEXT decimals.
                # Never coerce/invent a fee (Ch.16: "store; do not invent a fee").
                raise StoreError(
                    f"FAIL_CLOSED: ledger.{required} must be a TEXT decimal string"
                )
        last = self._conn.execute(
            "SELECT payload_hash FROM ledger ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        parent = last["payload_hash"] if last else None
        payload_hash = sha256_hex(
            canonical_json(
                {
                    "intent_id": row.get("intent_id"),
                    "order_id": row.get("order_id"),
                    "fill_id": row.get("fill_id"),
                    "price": row.get("price"),
                    "quantity": row.get("quantity"),
                    "parent": parent,
                }
            )
        )
        self._conn.execute(
            """INSERT INTO ledger
               (ledger_id, intent_id, order_id, fill_id, cancel_id, payload_hash,
                parent_ids, until, raw, fee, slippage, price, quantity, timestamp)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ledger_id,
                row.get("intent_id"),
                row.get("order_id"),
                row.get("fill_id"),
                row.get("cancel_id"),
                payload_hash,
                canonical_json([parent] if parent else []),
                row.get("until"),
                row.get("raw"),
                row.get("fee"),
                row.get("slippage"),
                row.get("price"),
                row.get("quantity"),
                row.get("timestamp", utc_now_iso()),
            ),
        )
        self._conn.commit()
        return ledger_id

    # -- generic inserts for remaining Ch.4 tables ----------------------------------

    def insert_evidence_event(self, row: Mapping[str, str | int | float | None]) -> str:
        evidence_id = row.get("evidence_id") or uuid_v7()
        cols = (
            "evidence_id", "timestamp_utc", "symbol", "timeframe", "engine_id",
            "event_type", "price_level", "strength", "confidence", "quality",
            "validity", "snapshot_id", "parent_ids", "payload_hash", "source_hash",
            "epsilon", "atr", "volume", "oi", "regime", "utc_activity_window_id",
            "lineage", "until", "raw", "authority", "authority_scope",
        )
        values = [evidence_id] + [row.get(c) for c in cols[1:]]
        placeholders = ",".join("?" * len(cols))
        self._conn.execute(
            f"INSERT INTO evidence_event ({','.join(cols)}) VALUES ({placeholders})", values
        )
        self._conn.commit()
        return evidence_id

    def insert_quality_vector(self, row: Mapping[str, Any]) -> str:
        quality_id = row.get("quality_id") or uuid_v7()
        self._conn.execute(
            """INSERT INTO quality_vector
               (quality_id, observation_id, q_schema, q_time, q_seq, q_ohlc,
                q_volume, q_oi, q_source, q_raw, veto_freshness, veto_completeness,
                veto_oi_lag, veto_source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                quality_id,
                row["observation_id"],
                row["q_schema"],
                row["q_time"],
                row["q_seq"],
                row["q_ohlc"],
                row["q_volume"],
                row["q_oi"],
                row["q_source"],
                row["q_raw"],
                row.get("veto_freshness", 0),
                row.get("veto_completeness", 0),
                row.get("veto_oi_lag", 0),
                row.get("veto_source", 0),
            ),
        )
        self._conn.commit()
        return quality_id

    def insert_snapshot_pit(self, row: Mapping[str, Any]) -> str:
        cols = (
            "snapshot_id", "as_of", "symbol_scope", "timeframe_scope", "source_state",
            "manifest_hash", "parameter_package_id", "code_version",
            "vector_quality_state", "min_quality", "weighted_quality", "created_at",
        )
        values = [row.get(c) for c in cols]
        self._conn.execute(
            f"INSERT INTO snapshot_pit ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            values,
        )
        self._conn.commit()
        return row["snapshot_id"]

    def upsert_bootstrap_progress(self, symbol: str, timeframe: str, phase: str, status: str, bars_written: int = 0, last_error: str | None = None, cursor_open_time: str | None = None) -> None:
        self._conn.execute(
            """INSERT INTO bootstrap_progress
               (symbol, timeframe, phase, cursor_open_time, status, bars_written, last_error, updated_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(symbol, timeframe, phase) DO UPDATE SET
                 cursor_open_time=excluded.cursor_open_time,
                 status=excluded.status,
                 bars_written=excluded.bars_written,
                 last_error=excluded.last_error,
                 updated_at=excluded.updated_at""",
            (symbol, timeframe, phase, cursor_open_time, status, bars_written, last_error, utc_now_iso()),
        )
        self._conn.commit()

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        return self._conn.execute(sql, params).fetchall()
