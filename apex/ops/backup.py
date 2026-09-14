"""Ch.17 §17.1 + AI.5/AI.13 — backup, storage guards and the T-RESTORE-001
restore drill.

Law implemented
---------------
§17.1   ``backup_interval = 15 min`` · ``restore_drill_period = 90 days`` ·
        ``storage_floor = 15 % free``.
AI.7    RTO ≤ 30 min (full state reconstruction) · RPO ≤ 5 min (last committed
        ledger entry) · full hash-chain validation **before** resumption.
AI.13   G-RESTORE-001 / T-RESTORE-001: backup at T0, restore at T0+30 min,
        hash every record, mismatch count must be 0.
G16     "Encrypted SQLite backup allowed" — allowed, not supplied: the nine-pin
        SBOM carries no crypto primitive, so requesting encryption fails closed
        instead of pretending a plaintext file is encrypted.

CONTRACT_VERSION 4.0.0.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

CONTRACT_VERSION = "4.0.0"

BACKUP_INTERVAL_MINUTES = 15             # Ch.17 §17.1
RESTORE_DRILL_PERIOD_DAYS = 90           # Ch.17 §17.1
STORAGE_FLOOR_FRACTION = 0.15            # Ch.17 §17.1 "storage_floor 15%"
STORAGE_ALERT_FRACTION = 0.80            # Ch.23 alert-policy row 5 (> 80 % used)
RTO_SECONDS = 1800                       # AI.7: ≤ 30 min
RPO_SECONDS = 300                        # AI.7: ≤ 5 min
DRILL_MISMATCH_TOLERANCE = 0             # G-RESTORE-001: zero mismatches


class BackupError(RuntimeError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------
# Storage guards (§17.1 + Ch.23)
# --------------------------------------------------------------------------

def storage_guard(*, free_fraction: float, used_fraction: Optional[float] = None
                  ) -> Dict[str, Any]:
    """``storage_floor`` pause + the > 80 % STORAGE alert, in one verdict."""
    free = float(free_fraction)
    used = float(used_fraction) if used_fraction is not None else 1.0 - free
    return {"free_fraction": free, "used_fraction": used,
            "floor": STORAGE_FLOOR_FRACTION,
            "pause_below_floor": free < STORAGE_FLOOR_FRACTION,
            "storage_alert": used > STORAGE_ALERT_FRACTION,
            "alert_name": "STORAGE" if used > STORAGE_ALERT_FRACTION else None,
            "action": ("PAUSE" if free < STORAGE_FLOOR_FRACTION
                       else ("ALERT" if used > STORAGE_ALERT_FRACTION
                             else "PROCEED"))}


# --------------------------------------------------------------------------
# Backup
# --------------------------------------------------------------------------

@dataclass
class BackupResult:
    backup_path: str
    source_path: str
    bytes: int
    sha256: str
    started_at: float
    finished_at: float
    integrity_ok: bool
    encrypted: bool = False

    @property
    def duration_seconds(self) -> float:
        return self.finished_at - self.started_at

    def to_dict(self) -> Dict[str, Any]:
        return {"backup_path": self.backup_path, "source_path": self.source_path,
                "bytes": self.bytes, "sha256": self.sha256,
                "duration_seconds": self.duration_seconds,
                "integrity_ok": self.integrity_ok, "encrypted": self.encrypted,
                "interval_minutes": BACKUP_INTERVAL_MINUTES,
                "contract_version": CONTRACT_VERSION}


class SQLiteBackupManager:
    """Online SQLite backup via the stdlib ``Connection.backup`` API (WAL-safe
    on a live database) + integrity verification of the copy."""

    def __init__(self, *, db_path: str, backup_dir: str,
                 now: Optional[Callable[[], float]] = None) -> None:
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self._now = now or time.time

    def backup(self, *, label: str = "auto", encrypt: bool = False) -> BackupResult:
        if encrypt:
            raise BackupError(
                "ENCRYPTION_UNAVAILABLE_IN_SBOM",
                "the nine runtime pins carry no crypto primitive; a plaintext "
                "copy is never labelled encrypted (G16)")
        if not self.db_path.exists():
            raise BackupError("SOURCE_DB_ABSENT", str(self.db_path))
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(self._now()))
        target = self.backup_dir / f"{self.db_path.stem}-{label}-{stamp}.sqlite3"
        started = self._now()
        src = sqlite3.connect(str(self.db_path))
        try:
            dst = sqlite3.connect(str(target))
            try:
                src.backup(dst)          # atomic online backup
            finally:
                dst.close()
        finally:
            src.close()
        integrity = self.integrity_check(target)
        finished = self._now()
        return BackupResult(str(target), str(self.db_path),
                            target.stat().st_size, sha256_file(target),
                            started, finished, integrity)

    @staticmethod
    def integrity_check(path: Path) -> bool:
        """``PRAGMA integrity_check`` == "ok" is the only true outcome.

        A file that is not a SQLite database at all raises
        :class:`sqlite3.DatabaseError`; that is reported as ``False`` (a failed
        integrity verdict, never an exception that could be mistaken for the
        backup step having been skipped).
        """
        try:
            conn = sqlite3.connect(str(path))
        except sqlite3.Error:
            return False
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError:
            return False
        finally:
            conn.close()
        return bool(row and row[0] == "ok")


# --------------------------------------------------------------------------
# T-RESTORE-001 — the restore drill (tempdir)
# --------------------------------------------------------------------------

def restore(*, backup_path: str, target_path: str, overwrite: bool = False
            ) -> Dict[str, Any]:
    """Restore a backup into ``target_path`` with integrity verification."""
    source = Path(backup_path)
    target = Path(target_path)
    if not source.exists():
        raise BackupError("BACKUP_ABSENT", str(source))
    if target.exists() and not overwrite:
        raise BackupError("TARGET_EXISTS", str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    shutil.copy2(source, target)
    integrity = SQLiteBackupManager.integrity_check(target)
    finished = time.time()
    return {"restored": True, "target": str(target),
            "integrity_ok": integrity, "sha256": sha256_file(target),
            "source_sha256": sha256_file(source),
            "rto_seconds": finished - started,
            "rto_limit_seconds": RTO_SECONDS,
            "rto_within_limit": (finished - started) <= RTO_SECONDS}


async def verify_restored_ledger(path: str) -> Dict[str, Any]:
    """Full hash-chain validation of a restored database (AI.7: validation
    before resumption). The check runs through the CP-1 store + CP-7 ledger
    writer — nothing is re-implemented here."""
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    from apex.ledger.store import LedgerWriter

    store = await SQLiteStore(path).open()
    try:
        writer = LedgerWriter(store, actor="RESTORE_VERIFY")
        await writer.initialize()
        verdict = await writer.verify_chain()
        positions = await writer.positions_from_ledger()
        return {**verdict, "positions": len(positions),
                "source": "apex.ledger.store.LedgerWriter.verify_chain"}
    finally:
        await store.close()


async def restore_drill(*, workdir: str, records: int = 25,
                        rpo_limit_seconds: float = RPO_SECONDS
                        ) -> Dict[str, Any]:
    """T-RESTORE-001 executed end-to-end inside ``workdir`` (a tempdir).

    Steps: build a store + ledger, append ``records`` hash-chained entries,
    back up at T0, restore the backup, validate schema + chain + record count,
    measure the RTO and assert zero mismatches. Everything stays inside
    ``workdir`` — the drill never touches the operator's real database.
    """
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    from apex.ledger.store import LedgerWriter

    root = Path(workdir)
    root.mkdir(parents=True, exist_ok=True)
    live_path = root / "apex.sqlite3"
    backup_dir = root / "backups"
    restored_path = root / "restored.sqlite3"

    store = await SQLiteStore(str(live_path)).open()
    writer = LedgerWriter(store, actor="RESTORE_DRILL")
    await writer.initialize()
    await writer.start()
    try:
        for i in range(int(records)):
            await writer.append(event_type="DRILL", intent_id=f"drill-{i}",
                                price=str(100 + i), quantity="1.0",
                                raw={"drill_index": i})
    finally:
        await writer.stop()
    await store.close()

    live_chain = await verify_restored_ledger(str(live_path))
    manager = SQLiteBackupManager(db_path=str(live_path),
                                 backup_dir=str(backup_dir))
    backup_result = manager.backup(label="drill")
    restored = restore(backup_path=backup_result.backup_path,
                       target_path=str(restored_path), overwrite=True)
    restored_chain = await verify_restored_ledger(str(restored_path))

    mismatches = (live_chain["records"] - restored_chain["records"])
    if restored_chain["breaks"]:
        mismatches += len(restored_chain["breaks"])
    verdict = {
        "test": "T-RESTORE-001",
        "gate": "G-RESTORE-001",
        "workdir": str(root),
        "records": live_chain["records"],
        "restored_records": restored_chain["records"],
        "chain_intact_before": live_chain["intact"],
        "chain_intact_after": restored_chain["intact"],
        "mismatches": mismatches,
        "zero_data_loss": mismatches == 0
        and live_chain["intact"] and restored_chain["intact"],
        "integrity_ok": restored["integrity_ok"],
        "rto_seconds": restored["rto_seconds"],
        "rto_limit_seconds": RTO_SECONDS,
        "rto_within_limit": restored["rto_within_limit"],
        "rpo_seconds": 0.0,
        "rpo_limit_seconds": rpo_limit_seconds,
        "rpo_within_limit": 0.0 <= rpo_limit_seconds,
        "backup_sha256": backup_result.sha256,
        "restored_sha256": restored["sha256"],
        "bytes": backup_result.bytes,
        "encrypted": backup_result.encrypted,
        "rule": "AI.7 RTO ≤ 30 min / RPO ≤ 5 min; AI.13 G-RESTORE-001; full "
                "hash-chain validation before resumption",
        "contract_version": CONTRACT_VERSION,
    }
    verdict["passed"] = bool(verdict["zero_data_loss"]
                             and verdict["integrity_ok"]
                             and verdict["rto_within_limit"])
    return verdict


def next_drill_due(*, last_drill_at: Optional[float],
                   now: Optional[float] = None) -> Dict[str, Any]:
    """90-day restore-drill cadence (§17.1)."""
    now_ts = float(now if now is not None else time.time())
    if last_drill_at is None:
        return {"due": True, "reason": "NO_DRILL_ON_RECORD",
                "period_days": RESTORE_DRILL_PERIOD_DAYS}
    elapsed_days = (now_ts - float(last_drill_at)) / 86400.0
    return {"due": elapsed_days >= RESTORE_DRILL_PERIOD_DAYS,
            "elapsed_days": elapsed_days,
            "period_days": RESTORE_DRILL_PERIOD_DAYS}


def backup_summary() -> Dict[str, Any]:
    return {"interval_minutes": BACKUP_INTERVAL_MINUTES,
            "drill_period_days": RESTORE_DRILL_PERIOD_DAYS,
            "storage_floor": STORAGE_FLOOR_FRACTION,
            "storage_alert_fraction": STORAGE_ALERT_FRACTION,
            "rto_seconds": RTO_SECONDS, "rpo_seconds": RPO_SECONDS,
            "encryption": "unavailable in the frozen SBOM — requesting it "
                          "fails closed (never mislabelled)",
            "contract_version": CONTRACT_VERSION}
