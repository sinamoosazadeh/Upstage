"""CP-8 — Ch.18 W.4/W.6/W.8 research checkpoints: the additive M201–M203
migration set, WAL journal mode, resume-never-rewind cursor arithmetic and the
durable monitor log (MATRIX Part III CP-8 rows C8-CK|1..10)."""

from __future__ import annotations

import asyncio
import sqlite3

import pytest

from apex.research.checkpoints import (
    BOOTSTRAP_PHASES, RESEARCH_MIGRATIONS, CheckpointError,
    ResearchCheckpointStore)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def store(tmp_path):
    return ResearchCheckpointStore(path=str(tmp_path / "research.sqlite3"))


class TestSchema:
    def test_three_additive_migrations(self):
        assert [name for name, _ in RESEARCH_MIGRATIONS] == [
            "M201_bootstrap_progress", "M202_optimizer_checkpoint",
            "M203_research_monitor_log"]

    def test_tables_exist_after_open(self, store, tmp_path):
        async def _check():
            async with store as opened:
                cur = await opened.db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")
                return sorted(r[0] for r in await cur.fetchall())
        names = _run(_check())
        assert {"bootstrap_progress", "optimizer_checkpoint",
                "research_monitor_log"} <= set(names)

    def test_wal_journal_mode(self, store):
        async def _check():
            async with store as opened:
                cur = await opened.db.execute("PRAGMA journal_mode")
                row = await cur.fetchone()
                return row[0]
        assert _run(_check()).lower() == "wal"

    def test_applied_migrations_are_reported(self, store):
        async def _check():
            async with store as opened:
                return await opened.applied_migrations()
        assert len(_run(_check())) == 3

    def test_phase_check_constraint_is_in_the_ddl(self):
        ddl = dict(RESEARCH_MIGRATIONS)["M201_bootstrap_progress"]
        assert "CHECK(phase IN (1, 2, 3))" in ddl
        assert BOOTSTRAP_PHASES == (1, 2, 3)

    def test_status_check_constraint_is_in_the_ddl(self):
        ddl = dict(RESEARCH_MIGRATIONS)["M202_optimizer_checkpoint"]
        assert "CHECK(optimizer IN ('SIGNAL', 'RISK'))" in ddl

    def test_use_before_open_fails_closed(self, store):
        with pytest.raises(CheckpointError) as err:
            _ = store.db
        assert err.value.reason == "STORE_NOT_OPEN"

    def test_bad_phase_refused(self, store):
        async def _write():
            async with store as opened:
                await opened.save_bootstrap(
                    cell_id="c1", symbol="BTCUSDT", timeframe="15m", phase=9,
                    status="IN_PROGRESS", cursor_ms=0)
        with pytest.raises(CheckpointError) as err:
            _run(_write())
        assert err.value.reason == "PHASE_QX"

    def test_bad_optimizer_refused(self, store):
        async def _write():
            async with store as opened:
                await opened.save_optimizer(
                    run_id="r1", cell_id="c1", optimizer="COMBINED",
                    status="IN_PROGRESS", combination_index=0)
        with pytest.raises(CheckpointError) as err:
            _run(_write())
        assert err.value.reason == "OPTIMIZER_QX"


class TestBootstrapCursor:
    def test_round_trip(self, store):
        async def _flow():
            async with store as opened:
                await opened.save_bootstrap(
                    cell_id="BTCUSDT-15m", symbol="BTCUSDT", timeframe="15m",
                    phase=1, status="IN_PROGRESS", cursor_ms=1_700_000_000_000,
                    bars_ingested=1000, oi_available=True,
                    payload={"source": "klines"})
                return await opened.load_bootstrap("BTCUSDT-15m")
        row = _run(_flow())
        assert row["cursor_ms"] == 1_700_000_000_000
        assert row["bars_ingested"] == 1000
        assert row["oi_available"] is True
        assert row["payload"] == {"source": "klines"}

    def test_missing_cell_returns_none(self, store):
        async def _flow():
            async with store as opened:
                return await opened.load_bootstrap("nope")
        assert _run(_flow()) is None

    def test_resume_never_rewinds_the_cursor(self, store):
        """W.8-1: a late, stale checkpoint can never move the cursor back."""
        async def _flow():
            async with store as opened:
                await opened.save_bootstrap(
                    cell_id="c1", symbol="BTCUSDT", timeframe="15m", phase=2,
                    status="IN_PROGRESS", cursor_ms=900, bars_ingested=10)
                await opened.save_bootstrap(
                    cell_id="c1", symbol="BTCUSDT", timeframe="15m", phase=2,
                    status="IN_PROGRESS", cursor_ms=400, bars_ingested=5)
                return await opened.load_bootstrap("c1")
        row = _run(_flow())
        assert row["cursor_ms"] == 900
        assert row["bars_ingested"] == 15      # bars are additive, never reset

    def test_incomplete_cells_exclude_complete_and_skipped(self, store):
        async def _flow():
            async with store as opened:
                for cell, status in (("a", "IN_PROGRESS"), ("b", "COMPLETE"),
                                     ("c", "SKIPPED"), ("d", "PAUSED")):
                    await opened.save_bootstrap(
                        cell_id=cell, symbol="BTCUSDT", timeframe="15m",
                        phase=1, status=status, cursor_ms=1)
                return await opened.incomplete_bootstrap_cells()
        assert _run(_flow()) == ["a", "d"]

    def test_rows_are_ordered_by_cell(self, store):
        async def _flow():
            async with store as opened:
                for cell in ("z", "a", "m"):
                    await opened.save_bootstrap(
                        cell_id=cell, symbol="BTCUSDT", timeframe="15m",
                        phase=1, status="PENDING", cursor_ms=0)
                return [r["cell_id"] for r in await opened.bootstrap_rows()]
        assert _run(_flow()) == ["a", "m", "z"]


class TestOptimizerCheckpoint:
    def test_two_optimizers_are_kept_apart(self, store):
        async def _flow():
            async with store as opened:
                await opened.save_optimizer(
                    run_id="run-1", cell_id="c1", optimizer="SIGNAL",
                    status="COMPLETE", combination_index=9, best_value=1.4,
                    best_params={"atr_mult": 1.5}, sru_hash="a" * 64)
                await opened.save_optimizer(
                    run_id="run-1", cell_id="c1", optimizer="RISK",
                    status="IN_PROGRESS", combination_index=3)
                return (await opened.load_optimizer("run-1", "c1", "SIGNAL"),
                        await opened.load_optimizer("run-1", "c1", "RISK"))
        signal, risk = _run(_flow())
        assert signal["status"] == "COMPLETE"
        assert signal["best_params"] == {"atr_mult": 1.5}
        assert signal["sru_hash"] == "a" * 64
        assert risk["status"] == "IN_PROGRESS"

    def test_same_pair_upserts(self, store):
        async def _flow():
            async with store as opened:
                await opened.save_optimizer(
                    run_id="r", cell_id="c", optimizer="SIGNAL",
                    status="IN_PROGRESS", combination_index=1)
                await opened.save_optimizer(
                    run_id="r", cell_id="c", optimizer="SIGNAL",
                    status="COMPLETE", combination_index=5, best_value=2.0)
                rows = await opened.optimizer_rows("r")
                return rows
        rows = _run(_flow())
        assert len(rows) == 1
        assert rows[0]["combination_index"] == 5
        assert rows[0]["status"] == "COMPLETE"

    def test_run_filter(self, store):
        async def _flow():
            async with store as opened:
                for run in ("r1", "r2"):
                    await opened.save_optimizer(
                        run_id=run, cell_id="c", optimizer="SIGNAL",
                        status="PENDING", combination_index=0)
                return await opened.optimizer_rows("r2")
        rows = _run(_flow())
        assert len(rows) == 1 and rows[0]["run_id"] == "r2"

    def test_live_workload_halt_is_a_legal_state(self, store):
        async def _flow():
            async with store as opened:
                await opened.save_optimizer(
                    run_id="r", cell_id="c", optimizer="RISK",
                    status="LIVE_WORKLOAD_HALT", combination_index=0)
                return await opened.load_optimizer("r", "c", "RISK")
        assert _run(_flow())["status"] == "LIVE_WORKLOAD_HALT"


class TestMonitorLog:
    def test_verdict_is_durable_and_hashed_on_disk(self, store, tmp_path):
        async def _flow():
            async with store as opened:
                await opened.log_monitor(
                    log_id="sprt-SF-1", family_id="SF_FVG_SWEEP_REV",
                    kind="SPRT", verdict="ACCEPT_H1",
                    stats={"llr": -3.2, "trades": 12})
                return await opened.monitor_rows()
        rows = _run(_flow())
        assert rows[0]["verdict"] == "ACCEPT_H1"
        assert "llr" in rows[0]["stats_json"]
        # raw sqlite3 (no aiosqlite) sees the committed row
        raw = sqlite3.connect(str(tmp_path / "research.sqlite3"))
        try:
            count = raw.execute(
                "SELECT COUNT(*) FROM research_monitor_log").fetchone()[0]
        finally:
            raw.close()
        assert count == 1

    def test_reopening_the_store_sees_the_rows(self, tmp_path):
        path = str(tmp_path / "research.sqlite3")

        async def _write():
            async with ResearchCheckpointStore(path=path) as opened:
                await opened.log_monitor(log_id="l1", family_id="SF",
                                         kind="SPRT", verdict="CONTINUE",
                                         stats={})

        async def _read():
            async with ResearchCheckpointStore(path=path) as opened:
                return await opened.monitor_rows()

        _run(_write())
        assert len(_run(_read())) == 1
