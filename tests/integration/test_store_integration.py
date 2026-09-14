"""CP-1 store integration: Ch.4/Ch.5 DDL verbatim-equivalence, WAL pragmas,
immutability (T-RS-001), hash-chain manifests (T-RS-002), retention
(T-RS-003), correction lifecycle (T-CL-001..003), ingest dedup, evidence
24-field validation, catalog-over-store."""
from __future__ import annotations

import asyncio
import re
from decimal import Decimal
from pathlib import Path

import pytest

from apex.data_catalog.catalog import Catalog, CatalogStatus
from apex.data_catalog.contracts import EvidenceEvent, MarketObservation
from apex.data_catalog.store import sqlite_store as ss
from apex.identity.uuid_v7 import uuid_v7


def make_obs(symbol="BTCUSDT", timeframe="15m", o=100, h=105, l=98, c=102,
             v=10, oi=Decimal("500"), ts="2024-01-01T00:15:00.000Z",
             status="CLOSED"):
    return MarketObservation(
        symbol=symbol, timeframe=timeframe, open=Decimal(o),
        high=Decimal(h), low=Decimal(l), close=Decimal(c), volume=Decimal(v),
        oi=oi, timestamp=ts, sequence=0, status=status, source="TOOBIT",
        availability_time=ts, oi_lag_seconds=0.0, delay_seconds=1.0,
        completeness_pct=100.0, source_health=1.0)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def store(tmp_path):
    s = ss.SQLiteStore(str(tmp_path / "apex.sqlite3"))
    run(s.open())
    yield s
    run(s.close())


class TestDDLVerbatim:
    def test_ch4_tables_and_columns(self, store):
        """Ch.4 table/column names verbatim."""
        expect = {
            "market_observation": {"observation_id", "symbol", "timeframe",
                                   "open_price", "high_price", "low_price",
                                   "close_price", "volume", "open_interest",
                                   "open_time", "close_time", "retrieved_at",
                                   "candle_status", "quality_state", "source",
                                   "schema_version", "raw_payload_hash"},
            "quality_vector": {"quality_id", "observation_id", "q_schema",
                               "q_time", "q_seq", "q_ohlc", "q_volume",
                               "q_oi", "q_source", "q_raw",
                               "veto_freshness", "veto_completeness",
                               "veto_oi_lag", "veto_source"},
            "snapshot_pit": {"snapshot_id", "as_of", "symbol_scope",
                             "timeframe_scope", "source_state",
                             "manifest_hash", "parameter_package_id",
                             "code_version", "vector_quality_state",
                             "min_quality", "weighted_quality", "created_at"},
            "evidence_event": {"evidence_id", "timestamp_utc", "symbol",
                               "timeframe", "engine_id", "event_type",
                               "price_level", "strength", "confidence",
                               "quality", "validity", "snapshot_id",
                               "parent_ids", "payload_hash", "source_hash",
                               "epsilon", "atr", "volume", "oi", "regime",
                               "utc_activity_window_id", "lineage", "until",
                               "raw", "authority", "authority_scope"},
            "pattern_evidence": {"pattern_id", "family", "pattern_type",
                                 "formation_sequence", "required_context",
                                 "evidence_dependencies", "invalidation_rules",
                                 "provenance_class", "lifecycle_status",
                                 "setup_score_contribution_class",
                                 "template_reconciliation",
                                 "reference_implementation",
                                 "historical_statistics", "revision_history",
                                 "confidence"},
            "setup_candidate": {"setup_id", "timestamp", "symbol", "timeframe",
                                "pattern_ids", "direction", "entry_price",
                                "stop_loss", "take_profit", "risk_reward",
                                "confidence", "quality", "validity",
                                "snapshot_id", "parent_ids", "payload_hash",
                                "regime", "utc_activity_window_id",
                                "lineage", "authority", "authority_scope"},
            "ledger": {"ledger_id", "intent_id", "order_id", "fill_id",
                       "cancel_id", "payload_hash", "parent_ids", "until",
                       "raw", "fee", "slippage", "price", "quantity",
                       "timestamp"},
            "outcome": {"outcome_id", "entry_price", "exit_price", "pnl",
                        "fees", "slippage", "mfe", "mae", "duration",
                        "exit_reason", "risk_used", "forecast", "setup_id",
                        "regime", "context"},
        }
        cur = run(store.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"))
        tables = {r[0] for r in run(cur.fetchall())}
        for table, cols in expect.items():
            assert table in tables, f"missing Ch.4 table {table}"
            cur = run(store.db.execute(f"PRAGMA table_info({table})"))
            got = {r[1] for r in run(cur.fetchall())}
            assert cols <= got, f"{table}: missing columns {cols - got}"

    def test_ch5_raw_store_tables_and_indexes(self, store):
        cur = run(store.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"))
        tables = {r[0] for r in run(cur.fetchall())}
        assert "raw_observation" in tables
        assert "bootstrap_progress" in tables
        assert "raw_revision" in tables   # AI.5
        assert "raw_manifest" in tables   # AI.5
        cur = run(store.db.execute("PRAGMA table_info(raw_observation)"))
        cols = {r[1] for r in run(cur.fetchall())}
        assert {"event_id", "as_of", "symbol", "timeframe", "open", "high",
                "low", "close", "volume", "oi", "oi_timestamp", "oi_state",
                "status", "content_hash", "source", "availability_time",
                "quality_vector", "created_at"} <= cols
        cur = run(store.db.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"))
        indexes = {r[0] for r in run(cur.fetchall())}
        assert "idx_raw_sym_tf_asof" in indexes

    def test_wal_pragmas(self, store):
        cur = run(store.db.execute("PRAGMA journal_mode"))
        assert run(cur.fetchone())[0].lower() == "wal"
        cur = run(store.db.execute("PRAGMA synchronous"))
        assert run(cur.fetchone())[0] == 2  # FULL
        cur = run(store.db.execute("PRAGMA foreign_keys"))
        assert run(cur.fetchone())[0] == 1
        cur = run(store.db.execute("PRAGMA busy_timeout"))
        assert run(cur.fetchone())[0] == 5000

    def test_migrations_recorded(self, store):
        cur = run(store.db.execute(
            "SELECT migration_name FROM schema_migrations ORDER BY 1"))
        names = [r[0] for r in run(cur.fetchall())]
        assert names == ["M001_ch4_data_plane_ddl", "M002_ch5_raw_store_ddl",
                         "M003_ai5_raw_revision_manifest",
                         "M004_immutability_triggers"]


class TestRawStore:
    def test_rs_001_immutability_at_db_level(self, store):
        """T-RS-001: UPDATE/DELETE on raw_observation fail; INSERT works."""
        event_id = run(store.ingest_raw(make_obs(), "AVAILABLE"))
        assert event_id
        with pytest.raises(Exception):
            run(store.db.execute(
                "UPDATE raw_observation SET volume='1' WHERE event_id=?",
                (event_id,)))
        with pytest.raises(Exception):
            run(store.db.execute(
                "DELETE FROM raw_observation WHERE event_id=?", (event_id,)))
        cur = run(store.db.execute(
            "SELECT COUNT(*) FROM raw_observation WHERE event_id=?",
            (event_id,)))
        assert run(cur.fetchone())[0] == 1  # intact

    def test_rs_002_manifest_hash_chain(self, store):
        """T-RS-002: manifest hashes recompute and chain via parent."""
        h1 = run(store.write_manifest("2024-01-01T00:00:00.000Z",
                                      "2024-01-02T00:00:00.000Z",
                                      ["aaa", "bbb"]))
        h2 = run(store.write_manifest("2024-01-02T00:00:00.000Z",
                                      "2024-01-03T00:00:00.000Z",
                                      ["ccc"], parent_manifest_hash=h1))
        assert len(h1) == len(h2) == 64
        cur = run(store.db.execute(
            "SELECT parent_manifest_hash, observation_count "
            "FROM raw_manifest WHERE manifest_hash=?", (h2,)))
        row = run(cur.fetchone())
        assert row == (h1, 1)

    def test_rs_003_retention(self, store):
        """T-RS-003: >12-month-old raw rows purged; younger kept; retention
        events logged to the audit trail."""
        import datetime as dt
        now = dt.datetime.now(dt.timezone.utc)
        def ts(delta_days):
            t = now - dt.timedelta(days=delta_days)
            return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"
        old = make_obs(ts=ts(400))
        fresh = make_obs(ts=ts(1))
        run(store.ingest_raw(old, "AVAILABLE"))
        run(store.ingest_raw(fresh, "AVAILABLE"))
        purged = run(store.retention_purge())
        assert purged  # old row purged
        cur = run(store.db.execute("SELECT COUNT(*) FROM raw_observation"))
        assert run(cur.fetchone())[0] == 1  # fresh row remains
        cur = run(store.db.execute(
            "SELECT event_kind FROM retention_event WHERE event_kind='PURGE_RAW'"))
        assert run(cur.fetchall())

    def test_cl_001_correction_supersedes_and_preserves(self, store):
        """T-CL-001/002: correction appends a new record; the original
        CLOSED row is marked SUPERSEDED, never overwritten."""
        ts = _now_ms()
        event_id = run(store.ingest_raw(make_obs(c=102, ts=ts), "AVAILABLE"))
        corrected = make_obs(c=103, ts=ts)
        new_id = run(store.correct_raw(event_id, corrected, "AVAILABLE",
                                       reason="provider correction"))
        assert new_id != event_id
        cur = run(store.db.execute(
            "SELECT COUNT(*) FROM raw_observation")
        )
        assert run(cur.fetchone())[0] == 2  # history retained
        cur = run(store.db.execute(
            "SELECT candle_status FROM market_observation "
            "WHERE raw_payload_hash IN (SELECT raw_payload_hash FROM "
            "market_observation) ORDER BY retrieved_at")
        )
        statuses = [r[0] for r in run(cur.fetchall())]
        assert "SUPERSEDED" in statuses and "CORRECTED" in statuses
        cur = run(store.db.execute("SELECT correction_reason, original_event_id "
                                   "FROM raw_revision"))
        rev = run(cur.fetchone())
        assert rev == ("provider correction", event_id)

    def test_cl_003_cascade_marker(self, store):
        """T-CL-003: the correction propagates lineage; history is never
        rewritten (original + corrected raw rows both retained); the
        corrected value is the newest CLOSED row."""
        ts = _now_ms()
        event_id = run(store.ingest_raw(make_obs(c=102, ts=ts), "AVAILABLE"))
        run(store.correct_raw(event_id, make_obs(c=104, ts=ts), "AVAILABLE",
                              reason="correction"))
        cur = run(store.db.execute(
            "SELECT COUNT(*) FROM raw_observation WHERE close IN ('102','104')"))
        assert run(cur.fetchone())[0] == 2  # history retained, never rewritten
        cur = run(store.db.execute(
            "SELECT close FROM raw_observation WHERE close='104'"))
        assert run(cur.fetchone())[0] == "104"
        cur = run(store.db.execute(
            "SELECT correction_reason, original_event_id FROM raw_revision"))
        assert run(cur.fetchone()) == ("correction", event_id)


def _now_ms():
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


class TestIngestDedupAndValidation:
    def test_duplicate_content_hash_deduplicated(self, store):
        obs = make_obs()
        first = run(store.ingest_raw(obs, "AVAILABLE"))
        second = run(store.ingest_raw(obs, "AVAILABLE"))
        assert second == first  # exact duplicate → same event_id
        cur = run(store.db.execute("SELECT COUNT(*) FROM raw_observation"))
        assert run(cur.fetchone())[0] == 1

    def test_invalid_symbol_timeframe_rejected(self, store):
        with pytest.raises(ValueError) as e1:
            run(store.ingest_raw(make_obs(symbol="DOTUSDT"), "AVAILABLE"))
        assert "E-VAL-021" in str(e1.value)
        with pytest.raises(ValueError) as e2:
            run(store.ingest_raw(make_obs(timeframe="3d"), "AVAILABLE"))
        assert "E-VAL-022" in str(e2.value)


class TestEvidenceContract:
    def test_evidence_24_field_validation_on_insert(self, store):
        good = EvidenceEvent(
            evidence_id=uuid_v7(), engine_id="E01",
            analyst_version="1.0.0+ab", symbol="BTCUSDT", timeframe="15m",
            snapshot_id="s", event_time="2024-01-01T00:15:00.000Z",
            availability_time="2024-01-01T00:15:00.000Z",
            observation_window={}, feature_snapshot_id="s",
            feature_dependencies=(), condition_state="BOS", direction=1,
            strength=0.7, confidence=0.8, quality=0.9, validity="VALID",
            fate_state=__import__("apex.data_catalog.contracts",
                                  fromlist=["LifecycleState"]).LifecycleState.ACTIVE,
            age=None, decay=None, explanation="ok", parameter_version="p1",
            lineage=(), resolution_class="Q1")
        run(store.insert_evidence(good))
        bad = EvidenceEvent(
            evidence_id=uuid_v7(), engine_id="E13",  # not E01..E12
            analyst_version="1.0.0", symbol="BTCUSDT", timeframe="15m",
            snapshot_id="s", event_time="2024-01-01T00:15:00.000Z",
            availability_time="2024-01-01T00:15:00.000Z",
            observation_window={}, feature_snapshot_id="s",
            feature_dependencies=(), condition_state="BOS", direction=1,
            strength=0.7, confidence=0.8, quality=0.9, validity="VALID",
            fate_state=__import__("apex.data_catalog.contracts",
                                  fromlist=["LifecycleState"]).LifecycleState.ACTIVE,
            age=None, decay=None, explanation="ok", parameter_version="p1",
            lineage=(), resolution_class="Q1")
        with pytest.raises(ValueError):
            run(store.insert_evidence(bad))


class TestCatalogOverStore:
    def test_catalog_get_via_store(self, store):
        """Engines read the catalog only: catalog over the store returns
        real feature values."""
        run(store.ingest_raw(make_obs(o=100, h=110, l=98, c=105), "AVAILABLE"))
        catalog = Catalog()
        catalog.set_provider(store)
        result = run(catalog.get("body_ratio", "BTCUSDT", "15m",
                                 "2024-01-01T00:15:00.000Z"))
        assert result.status == CatalogStatus.OK
        assert result.value == Decimal("0.416667")  # |105−100|/(110−98)

    def test_future_as_of_invalid_via_store(self, store):
        run(store.ingest_raw(make_obs(), "AVAILABLE"))
        catalog = Catalog()
        catalog.set_provider(store)
        result = run(catalog.get("body_ratio", "BTCUSDT", "15m",
                                 "2025-01-01T00:00:00.000Z"))
        assert result.status == CatalogStatus.INVALID
        assert result.reason == "PIT_FUTURE_AS_OF"


class TestMissingOiIngest:
    """The OI-less ingest path (wiring increment, T-DC-004 + Ch.4 DDL L14397).

    Phase 1 pages klines only: those rows carry no OI series, so `oi_state` is
    MISSING and `open_interest` cannot be a number. The frozen DDL declares the
    column TEXT, so the canonical label is stored (never 0) and reads back as
    `oi=None` — the same value `Catalog`/engines see for a missing series.
    """

    def test_missing_oi_row_ingests_and_reads_back_as_none(self, store):
        obs = make_obs(oi=None)
        event_id = run(store.ingest_raw(obs, "MISSING"))
        assert event_id
        cur = run(store.db.execute(
            "SELECT oi, oi_state FROM raw_observation WHERE event_id=?",
            (event_id,)))
        assert run(cur.fetchone()) == (None, "MISSING")   # nullable canonical pair
        cur = run(store.db.execute(
            "SELECT open_interest FROM market_observation "
            "WHERE raw_payload_hash=?", (ss.sha256_hex(obs.content_hash()),)))
        assert run(cur.fetchone())[0] == "MISSING"        # never 0
        window = run(store.get_window("BTCUSDT", "15m",
                                      "2024-01-01T01:00:00.000Z", 5))
        assert len(window) == 1 and window[0].oi is None

    def test_missing_oi_row_is_still_deduplicated(self, store):
        first = run(store.ingest_raw(make_obs(oi=None), "MISSING"))
        second = run(store.ingest_raw(make_obs(oi=None), "MISSING"))
        assert first == second
        cur = run(store.db.execute(
            "SELECT COUNT(*) FROM raw_observation WHERE symbol='BTCUSDT'"))
        assert run(cur.fetchone())[0] == 1

    def test_value_state_without_a_value_is_refused(self, store):
        with pytest.raises(ValueError) as excinfo:
            run(store.ingest_raw(make_obs(oi=None), "AVAILABLE"))
        assert "OI_STATE_WITHOUT_VALUE" in str(excinfo.value)

    def test_available_oi_is_unchanged(self, store):
        run(store.ingest_raw(make_obs(oi=Decimal("500")), "AVAILABLE"))
        window = run(store.get_window("BTCUSDT", "15m",
                                      "2024-01-01T01:00:00.000Z", 5))
        assert window[0].oi == Decimal("500")


class TestWindowIsTheLatestBars:
    """ISSUE-CP9-001: ``get_window`` must return the LAST `bars` rows at or
    before ``as_of`` (the docstring always said so; the SQL returned the
    oldest ones, which would starve every engine of its recent window)."""

    def _seed(self, store, closes):
        for index, close in enumerate(closes):
            stamp = f"2024-01-01T{index:02d}:15:00.000Z"
            run(store.ingest_raw(make_obs(c=close, ts=stamp, o=close,
                                          h=close + 1, l=close - 1),
                                 "AVAILABLE"))

    def test_last_bars_are_returned_in_ascending_order(self, store):
        self._seed(store, [100, 101, 102, 103, 104])
        window = run(store.get_window("BTCUSDT", "15m",
                                      "2024-01-01T04:15:00.000Z", 3))
        assert [str(o.close) for o in window] == ["102", "103", "104"]
        assert [o.timestamp for o in window] == [
            "2024-01-01T02:15:00.000Z", "2024-01-01T03:15:00.000Z",
            "2024-01-01T04:15:00.000Z"]

    def test_the_as_of_boundary_is_still_respected(self, store):
        self._seed(store, [100, 101, 102])
        window = run(store.get_window("BTCUSDT", "15m",
                                      "2024-01-01T01:15:00.000Z", 5))
        assert [str(o.close) for o in window] == ["100", "101"]

    def test_a_short_history_returns_what_exists(self, store):
        self._seed(store, [100])
        window = run(store.get_window("BTCUSDT", "15m",
                                      "2024-01-01T00:15:00.000Z", 10))
        assert [str(o.close) for o in window] == ["100"]
