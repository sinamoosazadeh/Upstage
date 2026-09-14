"""Ch.18 W.4/W.6/W.8 — persistent checkpoints for the research plane.

W.8-1 (normative): the state of every bundle-cell lives in the local SQLite
database; on process kill, device reboot or network failure the run resumes at
the start of the next uncompleted cell and is **never** restarted from the
beginning. W.6 Phase-1 checkpoints the ``bootstrap_progress`` cursor per cell
and resumes from it without rewinding.

The tables created here are research-plane tables (ADR-P2-003 additive rule,
logged in the CP-8 handoff DATA-CHANGES). They are created by this module's own
migration list; the frozen CP-1 migration list is never touched.

CONTRACT_VERSION 4.0.0.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import aiosqlite

from apex.config import Config
from apex.research.proxies import REPO_ROOT

CONTRACT_VERSION = "4.0.0"

M201_bootstrap_progress = """
CREATE TABLE IF NOT EXISTS bootstrap_progress (
  cell_id           TEXT PRIMARY KEY,
  symbol            TEXT NOT NULL,
  timeframe         TEXT NOT NULL,
  phase             INTEGER NOT NULL,
  status            TEXT NOT NULL,
  cursor_ms         INTEGER NOT NULL,
  bars_ingested     INTEGER NOT NULL DEFAULT 0,
  oi_available      INTEGER NOT NULL DEFAULT 0,
  updated_at        TEXT NOT NULL,
  payload_json      TEXT NOT NULL DEFAULT '{}',
  CHECK(phase IN (1, 2, 3)),
  CHECK(status IN ('PENDING', 'IN_PROGRESS', 'PAUSED', 'COMPLETE',
                   'SKIPPED')),
  CHECK(cursor_ms >= 0)
);
"""

M202_optimizer_checkpoint = """
CREATE TABLE IF NOT EXISTS optimizer_checkpoint (
  run_id            TEXT NOT NULL,
  cell_id           TEXT NOT NULL,
  optimizer         TEXT NOT NULL,
  status            TEXT NOT NULL,
  combination_index INTEGER NOT NULL DEFAULT 0,
  best_value        REAL,
  best_params_json  TEXT NOT NULL DEFAULT '{}',
  sru_hash          TEXT NOT NULL DEFAULT '',
  updated_at        TEXT NOT NULL,
  PRIMARY KEY (run_id, cell_id, optimizer),
  CHECK(optimizer IN ('SIGNAL', 'RISK')),
  CHECK(status IN ('PENDING', 'IN_PROGRESS', 'PAUSED', 'COMPLETE',
                   'LIVE_WORKLOAD_HALT')),
  CHECK(combination_index >= 0)
);
"""

M203_research_monitor_log = """
CREATE TABLE IF NOT EXISTS research_monitor_log (
  log_id            TEXT PRIMARY KEY,
  family_id         TEXT NOT NULL,
  kind              TEXT NOT NULL,
  verdict           TEXT NOT NULL,
  stats_json        TEXT NOT NULL,
  created_at        TEXT NOT NULL
);
"""

RESEARCH_MIGRATIONS: Tuple[Tuple[str, str], ...] = (
    ("M201_bootstrap_progress", M201_bootstrap_progress),
    ("M202_optimizer_checkpoint", M202_optimizer_checkpoint),
    ("M203_research_monitor_log", M203_research_monitor_log),
)

BOOTSTRAP_PHASES: Tuple[int, ...] = (1, 2, 3)


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


class CheckpointError(RuntimeError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class ResearchCheckpointStore:
    """SQLite-backed checkpoint store for bootstrap + optimizer runs."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or Config().sqlite_path
        self._db: Optional[aiosqlite.Connection] = None

    async def open(self) -> "ResearchCheckpointStore":
        db_path = Path(self.path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA synchronous=FULL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.execute("PRAGMA busy_timeout=5000")
        for _name, ddl in RESEARCH_MIGRATIONS:
            await self._db.execute(ddl)
        await self._db.commit()
        return self

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def __aenter__(self) -> "ResearchCheckpointStore":
        return await self.open()

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise CheckpointError("STORE_NOT_OPEN")
        return self._db

    async def applied_migrations(self) -> Tuple[str, ...]:
        return tuple(name for name, _ in RESEARCH_MIGRATIONS)

    # -- bootstrap progress (Phase 1, W.6) -------------------------------
    async def save_bootstrap(self, *, cell_id: str, symbol: str,
                             timeframe: str, phase: int, status: str,
                             cursor_ms: int, bars_ingested: int = 0,
                             oi_available: bool = False,
                             payload: Optional[Mapping[str, Any]] = None
                             ) -> None:
        if int(phase) not in BOOTSTRAP_PHASES:
            raise CheckpointError("PHASE_QX", str(phase))
        await self.db.execute(
            "INSERT INTO bootstrap_progress (cell_id, symbol, timeframe, phase,"
            " status, cursor_ms, bars_ingested, oi_available, updated_at,"
            " payload_json) VALUES (?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(cell_id) DO UPDATE SET phase=excluded.phase,"
            " status=excluded.status,"
            " cursor_ms=MAX(bootstrap_progress.cursor_ms, excluded.cursor_ms),"
            " bars_ingested=bootstrap_progress.bars_ingested + excluded.bars_ingested,"
            " oi_available=excluded.oi_available,"
            " updated_at=excluded.updated_at, payload_json=excluded.payload_json",
            (cell_id, symbol, timeframe, int(phase), status, int(cursor_ms),
             int(bars_ingested), 1 if oi_available else 0, utc_now(),
             json.dumps(dict(payload or {}), sort_keys=True)))
        await self.db.commit()

    async def load_bootstrap(self, cell_id: str) -> Optional[Dict[str, Any]]:
        cur = await self.db.execute(
            "SELECT * FROM bootstrap_progress WHERE cell_id=?", (cell_id,))
        row = await cur.fetchone()
        await cur.close()
        if row is None:
            return None
        out = dict(row)
        out["payload"] = json.loads(out.pop("payload_json") or "{}")
        out["oi_available"] = bool(out["oi_available"])
        return out

    async def bootstrap_rows(self) -> List[Dict[str, Any]]:
        cur = await self.db.execute(
            "SELECT * FROM bootstrap_progress ORDER BY cell_id")
        rows = [dict(r) for r in await cur.fetchall()]
        await cur.close()
        return rows

    async def incomplete_bootstrap_cells(self) -> List[str]:
        cur = await self.db.execute(
            "SELECT cell_id FROM bootstrap_progress WHERE status NOT IN"
            " ('COMPLETE','SKIPPED') ORDER BY cell_id")
        rows = [r[0] for r in await cur.fetchall()]
        await cur.close()
        return rows

    # -- optimizer checkpoints (W.4/W.8) ---------------------------------
    async def save_optimizer(self, *, run_id: str, cell_id: str,
                             optimizer: str, status: str,
                             combination_index: int,
                             best_value: Optional[float] = None,
                             best_params: Optional[Mapping[str, Any]] = None,
                             sru_hash: str = "") -> None:
        if optimizer not in ("SIGNAL", "RISK"):
            raise CheckpointError("OPTIMIZER_QX", optimizer)
        await self.db.execute(
            "INSERT INTO optimizer_checkpoint (run_id, cell_id, optimizer,"
            " status, combination_index, best_value, best_params_json,"
            " sru_hash, updated_at) VALUES (?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(run_id, cell_id, optimizer) DO UPDATE SET"
            " status=excluded.status,"
            " combination_index=excluded.combination_index,"
            " best_value=excluded.best_value,"
            " best_params_json=excluded.best_params_json,"
            " sru_hash=excluded.sru_hash, updated_at=excluded.updated_at",
            (run_id, cell_id, optimizer, status, int(combination_index),
             None if best_value is None else float(best_value),
             json.dumps(dict(best_params or {}), sort_keys=True), sru_hash,
             utc_now()))
        await self.db.commit()

    async def load_optimizer(self, run_id: str, cell_id: str,
                             optimizer: str) -> Optional[Dict[str, Any]]:
        cur = await self.db.execute(
            "SELECT * FROM optimizer_checkpoint WHERE run_id=? AND cell_id=?"
            " AND optimizer=?", (run_id, cell_id, optimizer))
        row = await cur.fetchone()
        await cur.close()
        if row is None:
            return None
        out = dict(row)
        out["best_params"] = json.loads(out.pop("best_params_json") or "{}")
        return out

    async def optimizer_rows(self, run_id: Optional[str] = None
                             ) -> List[Dict[str, Any]]:
        if run_id:
            cur = await self.db.execute(
                "SELECT * FROM optimizer_checkpoint WHERE run_id=?"
                " ORDER BY cell_id, optimizer", (run_id,))
        else:
            cur = await self.db.execute(
                "SELECT * FROM optimizer_checkpoint ORDER BY run_id, cell_id,"
                " optimizer")
        rows = [dict(r) for r in await cur.fetchall()]
        await cur.close()
        return rows

    # -- research monitor log (SPRT verdicts) ----------------------------
    async def log_monitor(self, *, log_id: str, family_id: str, kind: str,
                          verdict: str, stats: Mapping[str, Any]) -> None:
        await self.db.execute(
            "INSERT INTO research_monitor_log (log_id, family_id, kind,"
            " verdict, stats_json, created_at) VALUES (?,?,?,?,?,?)",
            (log_id, family_id, kind, verdict,
             json.dumps(dict(stats), sort_keys=True), utc_now()))
        await self.db.commit()

    async def monitor_rows(self) -> List[Dict[str, Any]]:
        cur = await self.db.execute(
            "SELECT * FROM research_monitor_log ORDER BY created_at, log_id")
        rows = [dict(r) for r in await cur.fetchall()]
        await cur.close()
        return rows
