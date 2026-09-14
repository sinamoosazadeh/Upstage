"""CP-8 — AI.7 / Ch.17 safeguards: 15-minute backup cadence, online SQLite
backup + integrity check, storage floor/alert arithmetic, the ≤ 30 min RTO
restore and the T-RESTORE-001 / G-RESTORE-001 drill executed end-to-end in a
tempdir (MATRIX Part III CP-8 rows C8-BK|1..14)."""

from __future__ import annotations

import asyncio
import sqlite3

import pytest

from apex.ops import backup as bk


def _run(coro):
    return asyncio.run(coro)


class TestConstants:
    def test_cadence_and_targets(self):
        assert bk.BACKUP_INTERVAL_MINUTES == 15
        assert bk.RESTORE_DRILL_PERIOD_DAYS == 90
        assert bk.RTO_SECONDS == 1800
        assert bk.RPO_SECONDS == 300

    def test_storage_thresholds(self):
        assert bk.STORAGE_FLOOR_FRACTION == pytest.approx(0.15)
        assert bk.STORAGE_ALERT_FRACTION == pytest.approx(0.80)

    def test_encryption_is_not_claimed(self):
        assert bk.DRILL_MISMATCH_TOLERANCE == 0
        summary = bk.backup_summary()
        assert "fails closed" in summary["encryption"]


class TestStorageGuard:
    def test_floor_pause(self):
        out = bk.storage_guard(free_fraction=0.10)
        assert out["pause_below_floor"] is True
        assert out["action"] == "PAUSE"

    def test_floor_boundary(self):
        assert bk.storage_guard(free_fraction=0.15)["pause_below_floor"] is False

    def test_storage_alert_above_80_pct_used(self):
        out = bk.storage_guard(free_fraction=0.10, used_fraction=0.85)
        assert out["storage_alert"] is True
        assert out["alert_name"] == "STORAGE"
        # both rules fire: the floor wins the action, the alert still exists
        assert out["action"] == "PAUSE"

    def test_used_fraction_derived_when_absent(self):
        out = bk.storage_guard(free_fraction=0.05)
        assert out["used_fraction"] == pytest.approx(0.95)

    def test_healthy_device_proceeds_quietly(self):
        out = bk.storage_guard(free_fraction=0.50)
        assert out["action"] == "PROCEED"
        assert out["alert_name"] is None


@pytest.fixture()
def live_db(tmp_path):
    """A small but real SQLite database with a WAL-mode table."""
    path = tmp_path / "apex.sqlite3"
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, kind TEXT)")
    conn.executemany("INSERT INTO events (kind) VALUES (?)",
                     [("A",), ("B",), ("C",)])
    conn.commit()
    conn.close()
    return path


class TestBackup:
    def test_online_backup_is_byte_identical_and_verified(self, live_db, tmp_path):
        manager = bk.SQLiteBackupManager(db_path=str(live_db),
                                        backup_dir=str(tmp_path / "b"))
        result = manager.backup(label="nightly")
        assert result.integrity_ok is True
        assert result.bytes > 0
        assert result.sha256 == bk.sha256_file(tmp_path / "b" / result.backup_path
                                               .split("/")[-1])
        assert "nightly" in result.backup_path

    def test_backup_survives_an_open_wal_connection(self, live_db, tmp_path):
        writer = sqlite3.connect(str(live_db))
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("INSERT INTO events (kind) VALUES ('D')")   # not committed
        manager = bk.SQLiteBackupManager(db_path=str(live_db),
                                        backup_dir=str(tmp_path / "b"))
        result = manager.backup(label="hot")
        assert result.integrity_ok is True
        writer.close()

    def test_absent_source_fails_closed(self, tmp_path):
        manager = bk.SQLiteBackupManager(db_path=str(tmp_path / "nope.sqlite3"),
                                        backup_dir=str(tmp_path / "b"))
        with pytest.raises(bk.BackupError) as err:
            manager.backup()
        assert err.value.reason == "SOURCE_DB_ABSENT"

    def test_encryption_request_fails_closed_without_mislabelling(self, live_db,
                                                                 tmp_path):
        manager = bk.SQLiteBackupManager(db_path=str(live_db),
                                         backup_dir=str(tmp_path / "b"))
        with pytest.raises(bk.BackupError) as err:
            manager.backup(encrypt=True)
        assert err.value.reason == "ENCRYPTION_UNAVAILABLE_IN_SBOM"

    def test_integrity_check_detects_a_corrupt_file(self, tmp_path):
        bad = tmp_path / "corrupt.sqlite3"
        bad.write_bytes(b"this is not a database")
        assert bk.SQLiteBackupManager.integrity_check(bad) is False

    def test_duration_is_measured_not_estimated(self, live_db, tmp_path):
        # call order: file stamp, started, finished
        ticks = iter([100.0, 200.0, 212.5])
        manager = bk.SQLiteBackupManager(db_path=str(live_db),
                                         backup_dir=str(tmp_path / "b"),
                                         now=lambda: next(ticks))
        result = manager.backup()
        assert result.duration_seconds == pytest.approx(12.5)

    def test_result_reports_the_frozen_interval(self, live_db, tmp_path):
        manager = bk.SQLiteBackupManager(db_path=str(live_db),
                                         backup_dir=str(tmp_path / "b"))
        assert manager.backup().to_dict()["interval_minutes"] == 15


class TestRestore:
    def test_restore_round_trip(self, live_db, tmp_path):
        manager = bk.SQLiteBackupManager(db_path=str(live_db),
                                         backup_dir=str(tmp_path / "b"))
        result = manager.backup()
        restored = bk.restore(backup_path=result.backup_path,
                              target_path=str(tmp_path / "restored.sqlite3"))
        assert restored["integrity_ok"] is True
        assert restored["sha256"] == restored["source_sha256"]
        assert restored["rto_seconds"] <= bk.RTO_SECONDS
        assert restored["rto_within_limit"] is True
        conn = sqlite3.connect(restored["target"])
        try:
            assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 3
        finally:
            conn.close()

    def test_existing_target_refused_unless_overwritten(self, live_db, tmp_path):
        manager = bk.SQLiteBackupManager(db_path=str(live_db),
                                         backup_dir=str(tmp_path / "b"))
        result = manager.backup()
        target = str(tmp_path / "restored.sqlite3")
        bk.restore(backup_path=result.backup_path, target_path=target)
        with pytest.raises(bk.BackupError) as err:
            bk.restore(backup_path=result.backup_path, target_path=target)
        assert err.value.reason == "TARGET_EXISTS"
        assert bk.restore(backup_path=result.backup_path, target_path=target,
                          overwrite=True)["restored"] is True

    def test_missing_backup_refused(self, tmp_path):
        with pytest.raises(bk.BackupError) as err:
            bk.restore(backup_path=str(tmp_path / "gone.sqlite3"),
                       target_path=str(tmp_path / "x.sqlite3"))
        assert err.value.reason == "BACKUP_ABSENT"

    def test_drill_due_every_90_days(self):
        assert bk.next_drill_due(last_drill_at=None)["due"] is True
        assert bk.next_drill_due(last_drill_at=1_000.0, now=1_000.0)["due"] is False
        eighty_nine = 89 * 86400.0
        assert bk.next_drill_due(last_drill_at=1_000.0,
                                 now=1_000.0 + eighty_nine)["due"] is False
        ninety = 90 * 86400.0
        assert bk.next_drill_due(last_drill_at=1_000.0,
                                 now=1_000.0 + ninety)["due"] is True


class TestRestoreDrillT001:
    def test_drill_passes_end_to_end_in_a_tempdir(self, tmp_path):
        verdict = _run(bk.restore_drill(workdir=str(tmp_path / "drill"),
                                        records=25))
        assert verdict["test"] == "T-RESTORE-001"
        assert verdict["gate"] == "G-RESTORE-001"
        assert verdict["records"] == 25
        assert verdict["restored_records"] == 25
        assert verdict["chain_intact_before"] is True
        assert verdict["chain_intact_after"] is True
        assert verdict["mismatches"] == 0
        assert verdict["zero_data_loss"] is True
        assert verdict["integrity_ok"] is True
        assert verdict["rto_within_limit"] is True
        assert verdict["encrypted"] is False
        assert verdict["passed"] is True

    def test_drill_leaves_nothing_outside_its_workdir(self, tmp_path):
        workdir = tmp_path / "drill"
        _run(bk.restore_drill(workdir=str(workdir), records=5))
        assert (workdir / "apex.sqlite3").exists()
        assert (workdir / "restored.sqlite3").exists()
        assert (workdir / "backups").exists()
        assert sorted(p.name for p in tmp_path.iterdir()) == ["drill"]

    def test_drill_record_count_is_exact(self, tmp_path):
        verdict = _run(bk.restore_drill(workdir=str(tmp_path / "d2"), records=3))
        assert verdict["records"] == 3
        assert verdict["zero_data_loss"] is True

    def test_verify_restored_ledger_reads_the_chain(self, tmp_path):
        path = tmp_path / "apex.sqlite3"

        async def _make():
            from apex.data_catalog.store.sqlite_store import SQLiteStore
            from apex.ledger.store import LedgerWriter
            store = await SQLiteStore(str(path)).open()
            writer = LedgerWriter(store, actor="UNIT")
            await writer.initialize()
            await writer.start()
            for i in range(4):
                await writer.append(event_type="DRILL", intent_id=f"i{i}",
                                    price="100", quantity="1.0")
            await writer.stop()
            await store.close()

        _run(_make())
        verdict = _run(bk.verify_restored_ledger(str(path)))
        assert verdict["records"] == 4
        assert verdict["intact"] is True
        assert "apex.ledger.store" in verdict["source"]
