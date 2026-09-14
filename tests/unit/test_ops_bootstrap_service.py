"""The wiring increment — `apex.ops.bootstrap_service` (W.6 Phase-1 long run).

Every venue interaction here goes through an injected double (G9): the tests
never reach the network, and the AsyncBridge → source → runner → raw store path
is exercised for real.
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path

import pytest

from apex.config import Config
from apex.data_catalog.contracts import MarketObservation
from apex.data_catalog.ingest.toobit_public import (
    ToobitPublicError, parse_kline_to_observation)
from apex.data_catalog.store import sqlite_store as ss
from apex.ops import bootstrap_service as BS
from apex.research.bootstrap import BootstrapError, DEEP_START_MS


def run(coro):
    return asyncio.run(coro)


STAMP = "2026-01-01T00:00:00.000Z"


class FakeVenueClient:
    """Async double for `ToobitPublicClient` (klines only)."""

    def __init__(self, *, bars: int = 5, page: int = 2, rate_limit_once: bool = False):
        self.bars = bars
        self.page = page
        self.calls = []
        self._rate_limited = False
        self._rate_limit_once = rate_limit_once

    async def get_klines(self, symbol, interval, start_ms, end_ms, limit=None):
        self.calls.append((symbol, interval, int(start_ms), int(end_ms), limit))
        if self._rate_limit_once and not self._rate_limited:
            self._rate_limited = True
            raise ToobitPublicError("klines", "code=-1003 rate limit")
        step = 3_600_000                       # every test cell is 1h
        out = []
        index = 0
        for i in range(self.bars):
            open_ms = int(start_ms) + i * step
            if open_ms >= int(end_ms):
                break
            row = [open_ms, "100", "101", "99", "100.5", "10", open_ms + step - 1]
            out.append(parse_kline_to_observation(symbol, interval, row, index))
            index += 1
        return out[: self.page]


def source_for(client, *, max_pages=None):
    bridge = BS.AsyncBridge().start()
    return BS.ToobitKlineSource(client=client, bridge=bridge, max_pages=max_pages), bridge


# ---------------------------------------------------------------------------
# source / bridge
# ---------------------------------------------------------------------------

class TestKlineSource:
    def test_page_contract_and_cursor(self, tmp_path):
        client = FakeVenueClient(bars=5, page=2)
        source, bridge = source_for(client)
        try:
            page = source("BTCUSDT", "1h", DEEP_START_MS, DEEP_START_MS + 10 * 3_600_000)
            assert page["code"] is None
            assert len(page["rows"]) == 2
            assert page["oi_available"] is False       # OI is never invented
            last_open = BS._iso_to_ms(page["rows"][-1].timestamp)
            assert page["next_cursor_ms"] == last_open + 3_600_000
        finally:
            run(source.aclose())
            bridge.close()

    def test_rate_limit_is_a_backoff_never_a_skip(self):
        client = FakeVenueClient(rate_limit_once=True)
        source, bridge = source_for(client)
        try:
            first = source("BTCUSDT", "1h", DEEP_START_MS, DEEP_START_MS + 3_600_000)
            assert first["code"] == -1003
            assert first["rows"] == []
            assert source.rate_limited == 1
            second = source("BTCUSDT", "1h", DEEP_START_MS, DEEP_START_MS + 3_600_000)
            assert second["code"] is None and second["rows"]
        finally:
            run(source.aclose())
            bridge.close()

    def test_non_rate_limit_failure_stops_with_a_named_reason(self):
        class Broken:
            async def get_klines(self, *a, **kw):
                raise ToobitPublicError("klines", "HTTP 500")

        source, bridge = source_for(Broken())
        try:
            with pytest.raises(BootstrapError) as excinfo:
                source("BTCUSDT", "1h", DEEP_START_MS, DEEP_START_MS + 1)
            assert excinfo.value.reason == "FETCH_FAILED"
        finally:
            bridge.close()

    def test_page_budget_stops_cleanly_and_resumably(self):
        client = FakeVenueClient(bars=5, page=1)
        source, bridge = source_for(client, max_pages=1)
        try:
            source("BTCUSDT", "1h", DEEP_START_MS, DEEP_START_MS + 5 * 3_600_000)
            with pytest.raises(BootstrapError) as excinfo:
                source("BTCUSDT", "1h", DEEP_START_MS, DEEP_START_MS + 5 * 3_600_000)
            assert excinfo.value.reason == "PAGE_BUDGET_REACHED"
        finally:
            bridge.close()

    def test_empty_page_finishes_the_cell(self):
        class Empty:
            async def get_klines(self, *a, **kw):
                return []

        source, bridge = source_for(Empty())
        try:
            page = source("ETHUSDT", "1h", DEEP_START_MS, DEEP_START_MS + 3_600_000)
            assert page["rows"] == [] and page["next_cursor_ms"] == DEEP_START_MS + 3_600_000
        finally:
            bridge.close()


class TestBridge:
    def test_bridge_reports_missing_start(self):
        async def pending():
            return None

        coro = pending()
        try:
            with pytest.raises(BS.BootstrapServiceError) as excinfo:
                BS.AsyncBridge().call(coro)
            assert excinfo.value.reason == "BRIDGE_NOT_STARTED"
        finally:
            coro.close()

    def test_bridge_round_trip_and_close(self):
        async def answer():
            return 42

        bridge = BS.AsyncBridge().start()
        assert bridge.call(answer()) == 42
        bridge.close()
        assert bridge._loop is None


# ---------------------------------------------------------------------------
# ingest into the raw store (append-only, idempotent)
# ---------------------------------------------------------------------------

class TestIngest:
    def test_rows_are_appended_and_repeats_are_deduped(self, tmp_path):
        async def scenario():
            store = ss.SQLiteStore(str(tmp_path / "apex.sqlite3"))
            await store.open()
            try:
                row = [DEEP_START_MS, "100", "101", "99", "100.5", "10",
                       DEEP_START_MS + 3_599_999]
                obs = parse_kline_to_observation("BTCUSDT", "1h", row, 0)
                first = await BS.ingest_observations(store, [obs], "BTCUSDT", "1h")
                second = await BS.ingest_observations(store, [obs], "BTCUSDT", "1h")
                assert first["inserted"] == 1 and first["duplicates"] == 0
                assert second["inserted"] == 0 and second["duplicates"] == 1
                assert first["oi_state"] == "MISSING"
                cursor = await store.db.execute(
                    "SELECT COUNT(*) FROM raw_observation WHERE symbol='BTCUSDT'")
                assert (await cursor.fetchone())[0] == 1
            finally:
                await store.close()

        run(scenario())

    def test_row_cell_mismatch_is_refused(self, tmp_path):
        async def scenario():
            store = ss.SQLiteStore(str(tmp_path / "apex.sqlite3"))
            await store.open()
            try:
                row = [DEEP_START_MS, "1", "1", "1", "1", "1", DEEP_START_MS]
                obs = parse_kline_to_observation("ETHUSDT", "1h", row, 0)
                with pytest.raises(BS.BootstrapServiceError) as excinfo:
                    await BS.ingest_observations(store, [obs], "BTCUSDT", "1h")
                assert excinfo.value.reason == "ROW_CELL_MISMATCH"
            finally:
                await store.close()

        run(scenario())


# ---------------------------------------------------------------------------
# device probes (W.6: an absent battery API never skips)
# ---------------------------------------------------------------------------

class TestProbes:
    def test_free_disk_is_measured(self):
        assert BS.free_disk_mb(".") > 0

    def test_absent_battery_binary_never_skips(self):
        def runner(cmd):
            raise OSError("termux-battery-status: not found")

        assert BS.read_battery(runner) is None

    def test_battery_json_is_parsed(self):
        class Completed:
            stdout = '{"percentage": 12, "plugged": false}'

        assert BS.read_battery(lambda cmd: Completed()) == {
            "percentage": 12, "plugged": False}

    def test_malformed_battery_output_is_none(self):
        class Completed:
            stdout = "not-json"

        assert BS.read_battery(lambda cmd: Completed()) is None


# ---------------------------------------------------------------------------
# the service
# ---------------------------------------------------------------------------

class TestService:
    def _service(self, tmp_path, client, **kwargs):
        return BS.BootstrapService(
            config=Config(), cells=[("BTCUSDT", "1h")],
            source=source_for(client)[0], db_path=str(tmp_path / "apex.sqlite3"),
            checkpoint_path=str(tmp_path / "apex.sqlite3"), **kwargs)

    def test_status_works_offline_without_a_venue(self, tmp_path):
        async def scenario():
            service = BS.BootstrapService(
                config=Config(), cells=[("BTCUSDT", "1h")],
                db_path=str(tmp_path / "apex.sqlite3"),
                checkpoint_path=str(tmp_path / "apex.sqlite3"))
            await service.open()
            try:
                status = await service.status()
                assert status["cells_total"] == 1
                assert status["cells_remaining"] == 1
                assert status["state"]["started"] is False
                assert service.source is None       # lazy: no venue, no bridge
            finally:
                await service.close()

        run(scenario())

    def test_command_surface_and_reporting(self, tmp_path):
        async def scenario():
            sent = []

            async def notifier(text):
                sent.append(text)
                return {"sent": True}

            service = self._service(tmp_path, FakeVenueClient(), notifier=notifier)
            await service.open()
            try:
                denied = await service.command("nonsense")
                assert denied["accepted"] is False
                assert denied["reason"] == "UNKNOWN_COMMAND"
                assert sent and "REFUSED" in sent[-1]
                started = await service.command("pause")
                assert started["accepted"] is True
                progress = await service.command("progress")
                assert progress["command"] == "progress"
                continuous = await service.command("continuous on")
                assert continuous["state"]["continuous"] is True
            finally:
                await service.close()

        run(scenario())

    def test_report_without_a_notifier_is_a_reported_refusal(self, tmp_path):
        async def scenario():
            service = self._service(tmp_path, FakeVenueClient())
            await service.open()
            try:
                record = await service.report("hello")
                assert record["delivered"] is False
                assert record["reason"] == "NO_NOTIFIER"
            finally:
                await service.close()

        run(scenario())

    def test_bounded_run_is_resumable_and_idempotent(self, tmp_path):
        async def scenario():
            client = FakeVenueClient(bars=6, page=3)
            source, bridge = source_for(client, max_pages=2)
            service = BS.BootstrapService(
                config=Config(), cells=[("BTCUSDT", "1h")], source=source,
                db_path=str(tmp_path / "apex.sqlite3"),
                checkpoint_path=str(tmp_path / "apex.sqlite3"))
            await service.open()
            try:
                first = await service.run(announce=False)
                assert first["status"] == "BUDGET_REACHED"
                assert first["resumable"] is True
                assert first["pages_fetched"] == 2
                assert first["bars_ingested"] == 6
                # the durable cursor is the resume point
                cursor = await service._checkpoints.db.execute(
                    "SELECT cursor_ms, status FROM "
                    "research_bootstrap_progress "
                    "WHERE cell_id='BTCUSDT:1h'")
                row = await cursor.fetchone()
                assert row is not None and row[0] > DEEP_START_MS
                status = await service.status()
                assert status["pages_fetched"] == 2
            finally:
                await service.close()
                bridge.close()

        run(scenario())

    def test_complete_run_marks_the_cell(self, tmp_path):
        async def scenario():
            client = FakeVenueClient(bars=3, page=3)
            source, bridge = source_for(client)
            service = BS.BootstrapService(
                config=Config(), cells=[("BTCUSDT", "1h")], source=source,
                db_path=str(tmp_path / "apex.sqlite3"),
                checkpoint_path=str(tmp_path / "apex.sqlite3"))
            await service.open()
            try:
                result = await service.run(
                    end_ms=DEEP_START_MS + 3 * 3_600_000, announce=False)
                assert result["status"] == "COMPLETE"
                assert result["completed_cells"] == ["BTCUSDT:1h"]
                assert result["pending_cells"] == []
                assert result["oi_policy"].startswith("oi_state=MISSING")
            finally:
                await service.close()
                bridge.close()

        run(scenario())

    # Canonical mirror — ISSUE-CP9-002 + W.6: research checkpoint is mirrored to Ch.5 bootstrap_progress
    def test_complete_run_mirrors_canonical_done_and_cursor(self, tmp_path):
        """Complete run → canonical row phase='P1' status='DONE' bars_written≥3 and ISO cursor matches research."""
        async def scenario():
            client = FakeVenueClient(bars=3, page=3)
            source, bridge = source_for(client)
            service = BS.BootstrapService(
                config=Config(), cells=[("BTCUSDT", "1h")], source=source,
                db_path=str(tmp_path / "apex.sqlite3"),
                checkpoint_path=str(tmp_path / "apex.sqlite3"))
            await service.open()
            try:
                result = await service.run(
                    end_ms=DEEP_START_MS + 3 * 3_600_000, announce=False)
                assert result["status"] == "COMPLETE"
                cur = await service._checkpoints.db.execute(
                    "SELECT cursor_ms FROM research_bootstrap_progress WHERE cell_id='BTCUSDT:1h'")
                rrow = await cur.fetchone()
                assert rrow is not None
                research_cursor = int(rrow[0])
                cur2 = await service._store.db.execute(
                    "SELECT phase, status, bars_written, cursor_open_time FROM bootstrap_progress "
                    "WHERE symbol='BTCUSDT' AND timeframe='1h' AND phase='P1'")
                prow = await cur2.fetchone()
                assert prow is not None, "canonical bootstrap_progress row missing"
                assert prow[0] == "P1"
                assert prow[1] == "DONE"
                assert int(prow[2]) >= 3
                assert BS._iso_to_ms(prow[3]) == research_cursor
            finally:
                await service.close()
                bridge.close()

        run(scenario())

    def test_budget_paused_mirrors_canonical_running_and_cursor(self, tmp_path):
        """Budget-paused run → canonical status RUNNING|PAUSED and cursor advanced (= research)."""
        async def scenario():
            client = FakeVenueClient(bars=6, page=3)
            source, bridge = source_for(client, max_pages=2)
            service = BS.BootstrapService(
                config=Config(), cells=[("BTCUSDT", "1h")], source=source,
                db_path=str(tmp_path / "apex.sqlite3"),
                checkpoint_path=str(tmp_path / "apex.sqlite3"))
            await service.open()
            try:
                first = await service.run(announce=False)
                assert first["status"] == "BUDGET_REACHED"
                cur = await service._checkpoints.db.execute(
                    "SELECT cursor_ms FROM research_bootstrap_progress WHERE cell_id='BTCUSDT:1h'")
                rrow = await cur.fetchone()
                assert rrow is not None
                research_cursor = int(rrow[0])
                assert research_cursor > DEEP_START_MS
                cur2 = await service._store.db.execute(
                    "SELECT status, cursor_open_time, bars_written FROM bootstrap_progress "
                    "WHERE symbol='BTCUSDT' AND timeframe='1h' AND phase='P1'")
                prow = await cur2.fetchone()
                assert prow is not None
                assert prow[0] in ("RUNNING", "PAUSED")
                assert BS._iso_to_ms(prow[1]) == research_cursor
                assert BS._iso_to_ms(prow[1]) > DEEP_START_MS
            finally:
                await service.close()
                bridge.close()

        run(scenario())
