"""The wiring increment — `apex.ops.bootstrap_service` (W.6 Phase-1 long run).

Every venue interaction here goes through an injected double (G9): the tests
never reach the network, and the AsyncBridge → source → runner → raw store path
is exercised for real.

CP-11: `ToobitKlineSource` is venue-adaptive (backward walk + ascending serve)
because Toobit public klines are tail-aligned. `TailAlignedVenue` emulates the
owner-measured venue shape; `FakeVenueClient` remains a simple series generator
used by the service-level wiring tests (full history fits one walk page).
"""
from __future__ import annotations

import asyncio
from typing import Optional

import pytest

from apex.config import Config
from apex.data_catalog.ingest.toobit_public import (
    ToobitPublicError, parse_kline_to_observation)
from apex.data_catalog.store import sqlite_store as ss
from apex.ops import bootstrap_service as BS
from apex.research.bootstrap import BootstrapError, DEEP_START_MS

def run(coro):
    return asyncio.run(coro)


STAMP = "2026-01-01T00:00:00.000Z"
HOUR = 3_600_000
# A fixed "now" for the tail-aligned double (owner-probe era, 2026-09-16).
NOW_MS = 1_726_444_800_000  # 2024-09-16T00:00:00Z-ish fixed anchor


class FakeVenueClient:
    """Async double for `ToobitPublicClient` (klines only).

    Generates a contiguous series of ``bars`` 1h candles starting at the
    requested ``start_ms`` (capped by ``end_ms``), returning at most ``page``
    rows per call. Used by the service-level wiring tests: with the CP-11
    backward walk the first venue page under a deep start collects the series
    head; multi-page runner budgets are covered by the dedicated tail-aligned
    suite below.
    """

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
        step = HOUR
        out = []
        index = 0
        # Prefer the caller's limit when the adaptive source walks with PAGE_LIMIT.
        cap = int(limit) if limit is not None else self.page
        cap = min(cap, self.page) if self.page else cap
        for i in range(self.bars):
            open_ms = int(start_ms) + i * step
            if open_ms >= int(end_ms):
                break
            row = [open_ms, "100", "101", "99", "100.5", "10", open_ms + step - 1]
            out.append(parse_kline_to_observation(symbol, interval, row, index))
            index += 1
            if len(out) >= cap:
                break
        return out


class TailAlignedVenue:
    """Emulates the owner-measured Toobit public klines shape (CP-11).

    Facts reproduced:
    * for any ``[startTime, endTime]`` the venue returns the LAST ``limit`` bars
      at/before ``endTime`` (``startTime`` ignored);
    * a window that does not reach the retained tail returns ``[]``
      (owner probe: 2020→2020+7d → ``[]``; 2020→now → most recent N bars);
    * retention is a rolling window of ``retention`` bars ending at ``now_ms``.
    """

    def __init__(self, *, now_ms: int = NOW_MS, step_ms: int = HOUR,
                 retention: int = 10, limit_cap: int = 1000,
                 rate_limit_times: int = 0,
                 fail_after_walks: Optional[int] = None,
                 fail_message: str = "HTTP 500") -> None:
        self.now_ms = int(now_ms)
        self.step_ms = int(step_ms)
        self.retention = int(retention)
        self.limit_cap = int(limit_cap)
        self.calls: list = []
        self._rate_limit_remaining = int(rate_limit_times)
        self._fail_after = fail_after_walks
        self._fail_message = fail_message
        # Contiguous open times: oldest .. newest (newest = floor_to_step(now)).
        newest = self.now_ms - (self.now_ms % self.step_ms)
        self.series = [
            newest - (self.retention - 1 - i) * self.step_ms
            for i in range(self.retention)
        ]
        self.oldest_ms = self.series[0]
        self.newest_ms = self.series[-1]

    async def get_klines(self, symbol, interval, start_ms, end_ms, limit=None):
        self.calls.append((symbol, interval, int(start_ms), int(end_ms), limit))
        if self._fail_after is not None and len(self.calls) > self._fail_after:
            raise ToobitPublicError("klines", self._fail_message)
        if self._rate_limit_remaining > 0:
            self._rate_limit_remaining -= 1
            raise ToobitPublicError("klines", "code=-1003 Too many requests")
        cap = int(limit) if limit is not None else self.limit_cap
        cap = min(cap, self.limit_cap)
        end = int(end_ms)
        # Bars at/before endTime that the venue still retains.
        eligible = [t for t in self.series if t <= end]
        if not eligible:
            return []
        window = eligible[-cap:]                 # LAST `limit` bars (tail-aligned)
        out = []
        for i, open_ms in enumerate(window):
            row = [open_ms, "100", "101", "99", "100.5", "10",
                   open_ms + self.step_ms - 1]
            out.append(parse_kline_to_observation(symbol, interval, row, i))
        return out


def source_for(client, *, max_pages=None, walk_backoff_seconds=(0.0, 0.0, 0.0)):
    """Build a source; walk backoff is zeroed so unit tests stay fast."""
    bridge = BS.AsyncBridge().start()
    return BS.ToobitKlineSource(
        client=client, bridge=bridge, max_pages=max_pages,
        walk_backoff_seconds=walk_backoff_seconds), bridge


# ---------------------------------------------------------------------------
# source / bridge
# ---------------------------------------------------------------------------

class TestKlineSource:
    def test_page_contract_and_cursor(self, tmp_path):
        client = FakeVenueClient(bars=5, page=2)
        source, bridge = source_for(client)
        try:
            page = source("BTCUSDT", "1h", DEEP_START_MS, DEEP_START_MS + 10 * HOUR)
            assert page["code"] is None
            assert len(page["rows"]) == 2
            assert page["oi_available"] is False       # OI is never invented
            last_open = BS._iso_to_ms(page["rows"][-1].timestamp)
            assert page["next_cursor_ms"] == last_open + HOUR
        finally:
            run(source.aclose())
            bridge.close()

    def test_rate_limit_is_a_backoff_never_a_skip(self):
        # rate_limit_times exhausts the walk-internal retries → surface −1003
        # to the frozen runner (never a skip, never a fabricated page).
        client = FakeVenueClient(rate_limit_once=True)
        source, bridge = source_for(client, walk_backoff_seconds=(0.0,))
        try:
            first = source("BTCUSDT", "1h", DEEP_START_MS, DEEP_START_MS + HOUR)
            # One walk-internal retry (backoff tuple length 1 ⇒ 2 attempts);
            # FakeVenueClient only rate-limits once, so the walk succeeds and
            # the first runner-facing page carries real rows.
            assert first["code"] is None and first["rows"]
            assert source.rate_limited == 1
        finally:
            run(source.aclose())
            bridge.close()

    def test_rate_limit_surfaces_when_walk_retries_exhaust(self):
        class AlwaysLimited:
            async def get_klines(self, *a, **kw):
                raise ToobitPublicError("klines", "code=-1003 rate limit")

        source, bridge = source_for(AlwaysLimited(), walk_backoff_seconds=(0.0, 0.0))
        try:
            page = source("BTCUSDT", "1h", DEEP_START_MS, DEEP_START_MS + HOUR)
            assert page["code"] == -1003
            assert page["rows"] == []
            assert page["next_cursor_ms"] is None
            assert source.rate_limited >= 1
            # A subsequent call retries the walk (history not cached on failure).
            page2 = source("BTCUSDT", "1h", DEEP_START_MS, DEEP_START_MS + HOUR)
            assert page2["code"] == -1003
        finally:
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
            source("BTCUSDT", "1h", DEEP_START_MS, DEEP_START_MS + 5 * HOUR)
            with pytest.raises(BootstrapError) as excinfo:
                source("BTCUSDT", "1h", DEEP_START_MS, DEEP_START_MS + 5 * HOUR)
            assert excinfo.value.reason == "PAGE_BUDGET_REACHED"
        finally:
            bridge.close()

    def test_empty_page_finishes_the_cell(self):
        class Empty:
            async def get_klines(self, *a, **kw):
                return []

        source, bridge = source_for(Empty())
        try:
            page = source("ETHUSDT", "1h", DEEP_START_MS, DEEP_START_MS + HOUR)
            assert page["rows"] == [] and page["next_cursor_ms"] == DEEP_START_MS + HOUR
        finally:
            bridge.close()


class TestTailAlignedSource:
    """CP-11 — venue-adaptive backfill against a tail-aligned fake session."""

    def test_full_walk_cell_completes_with_all_bars_ascending(self):
        """Backward walk collects the full retained series; ascending serve
        delivers every bar exactly once in open_time order."""
        venue = TailAlignedVenue(retention=7, limit_cap=3)
        source, bridge = source_for(venue)
        try:
            collected = []
            cursor = DEEP_START_MS
            end = venue.now_ms + HOUR
            pages = 0
            while cursor < end:
                page = source("BTCUSDT", "1h", cursor, end, limit=3)
                pages += 1
                if not page["rows"]:
                    assert page["next_cursor_ms"] == end
                    break
                opens = [BS._iso_to_ms(r.timestamp) for r in page["rows"]]
                assert opens == sorted(opens)          # ascending chunk
                collected.extend(opens)
                next_c = page["next_cursor_ms"]
                assert next_c > cursor
                cursor = next_c
            assert collected == venue.series
            assert pages >= 2                          # more than one facing page
            # Walk used multiple venue calls (limit_cap=3, retention=7).
            assert len(venue.calls) >= 3
            assert source.walk_pages >= 3
            # Runner-facing page counter is independent of walk traffic.
            assert source.pages_served == pages
        finally:
            bridge.close()

    def test_empty_first_page_no_longer_completes_at_zero_bars(self):
        """The pilot regression: a head-aligned first page from DEEP_START
        against a tail-aligned venue returned ``[]`` and COMPLETE'd at 0 bars.
        The adaptive walk must instead recover the retained tail."""
        venue = TailAlignedVenue(retention=5, limit_cap=1000)
        source, bridge = source_for(venue)
        try:
            # First runner page from DEEP_START — the dead-window case.
            page = source("BTCUSDT", "1h", DEEP_START_MS, venue.now_ms + HOUR)
            assert page["code"] is None
            assert len(page["rows"]) == 5               # NOT zero
            opens = [BS._iso_to_ms(r.timestamp) for r in page["rows"]]
            assert opens == venue.series
            assert opens[0] == venue.oldest_ms
            # Owner probe shape: a short historical window (2020→2020+7d)
            # returns [] from the venue itself during the walk's deep steps,
            # but the walk continues from `now` and still finds the tail.
            assert any(c[3] >= venue.oldest_ms for c in venue.calls)
        finally:
            bridge.close()

    def test_budget_counts_runner_facing_pages_only(self):
        """``--max-pages`` counts runner-facing pages; walk traffic is free."""
        venue = TailAlignedVenue(retention=9, limit_cap=2)
        source, bridge = source_for(venue, max_pages=2)
        try:
            end = venue.now_ms + HOUR
            p1 = source("BTCUSDT", "1h", DEEP_START_MS, end, limit=2)
            assert len(p1["rows"]) == 2
            assert source.pages_served == 1
            assert source.walk_pages >= 4               # walk >> facing
            p2 = source("BTCUSDT", "1h", p1["next_cursor_ms"], end, limit=2)
            assert len(p2["rows"]) == 2
            assert source.pages_served == 2
            with pytest.raises(BootstrapError) as excinfo:
                source("BTCUSDT", "1h", p2["next_cursor_ms"], end, limit=2)
            assert excinfo.value.reason == "PAGE_BUDGET_REACHED"
        finally:
            bridge.close()

    def test_backoff_inside_the_walk(self):
        """−1003 during the walk retries with bounded backoff; never skips."""
        venue = TailAlignedVenue(retention=4, limit_cap=2, rate_limit_times=2)
        source, bridge = source_for(venue, walk_backoff_seconds=(0.0, 0.0, 0.0))
        try:
            page = source("BTCUSDT", "1h", DEEP_START_MS, venue.now_ms + HOUR)
            assert page["code"] is None
            assert len(page["rows"]) == 4
            assert source.rate_limited == 2
            # Walk still completed — no fabricated empty completion.
            assert BS._iso_to_ms(page["rows"][0].timestamp) == venue.oldest_ms
        finally:
            bridge.close()

    def test_dedup_stop_on_repeated_first_row(self):
        """A page that re-returns its own first row ends the walk (no spin)."""
        class StickyTail:
            """Always returns the same two newest bars regardless of endTime
            once the endTime is at/above the series — emulates a venue stuck
            on the retained tail window."""

            def __init__(self):
                self.calls = []
                self.series = [NOW_MS - 3 * HOUR, NOW_MS - 2 * HOUR,
                               NOW_MS - HOUR, NOW_MS]

            async def get_klines(self, symbol, interval, start_ms, end_ms, limit=None):
                self.calls.append(int(end_ms))
                # Always the same last-2 window (ignores endTime once past tail).
                window = self.series[-2:]
                out = []
                for i, open_ms in enumerate(window):
                    row = [open_ms, "1", "1", "1", "1", "1", open_ms + HOUR - 1]
                    out.append(parse_kline_to_observation(symbol, interval, row, i))
                return out

        sticky = StickyTail()
        source, bridge = source_for(sticky)
        try:
            page = source("BTCUSDT", "1h", DEEP_START_MS, NOW_MS + HOUR)
            assert page["code"] is None
            opens = [BS._iso_to_ms(r.timestamp) for r in page["rows"]]
            # Only the sticky window was collected (dedup-stop prevented spin).
            assert opens == sticky.series[-2:]
            # Walk must have stopped after seeing the repeated first row —
            # not unbounded calls.
            assert 2 <= len(sticky.calls) <= 5
        finally:
            bridge.close()

    def test_resume_with_forward_cursor_filters_already_collected(self):
        """After a restart with a forward cursor, already-collected bars are
        not re-served; ascending order is preserved."""
        venue = TailAlignedVenue(retention=8, limit_cap=3)
        source, bridge = source_for(venue)
        try:
            end = venue.now_ms + HOUR
            first = source("BTCUSDT", "1h", DEEP_START_MS, end, limit=3)
            assert len(first["rows"]) == 3
            cursor = first["next_cursor_ms"]
            # Simulate resume: new source instance (process restart) OR same
            # source with the advanced cursor — cursor filter is the speed net.
            resumed = source("BTCUSDT", "1h", cursor, end, limit=3)
            assert resumed["code"] is None
            assert resumed["rows"]
            first_opens = [BS._iso_to_ms(r.timestamp) for r in first["rows"]]
            next_opens = [BS._iso_to_ms(r.timestamp) for r in resumed["rows"]]
            # No overlap with the already-served page.
            assert not set(first_opens) & set(next_opens)
            assert next_opens == sorted(next_opens)
            assert next_opens[0] >= cursor
            # Full concatenation is the retained series head.
            assert first_opens + next_opens == venue.series[:6]
        finally:
            bridge.close()

    def test_resume_across_source_restart_rewalks_but_filters(self):
        """A brand-new source after restart re-walks the venue, but the
        durable forward cursor still drops already-ingested bars."""
        venue = TailAlignedVenue(retention=6, limit_cap=1000)
        source1, bridge1 = source_for(venue)
        try:
            end = venue.now_ms + HOUR
            first = source1("BTCUSDT", "1h", DEEP_START_MS, end, limit=2)
            cursor = first["next_cursor_ms"]
            first_opens = [BS._iso_to_ms(r.timestamp) for r in first["rows"]]
        finally:
            bridge1.close()

        source2, bridge2 = source_for(venue)
        try:
            second = source2("BTCUSDT", "1h", cursor, end, limit=1000)
            second_opens = [BS._iso_to_ms(r.timestamp) for r in second["rows"]]
            assert not set(first_opens) & set(second_opens)
            assert first_opens + second_opens == venue.series
        finally:
            bridge2.close()

    def test_non_rate_limit_during_walk_is_named_fail_closed(self):
        venue = TailAlignedVenue(retention=5, limit_cap=2,
                                 fail_after_walks=1, fail_message="code=-1120 bad")
        source, bridge = source_for(venue)
        try:
            with pytest.raises(BootstrapError) as excinfo:
                source("BTCUSDT", "1h", DEEP_START_MS, venue.now_ms + HOUR)
            assert excinfo.value.reason == "FETCH_FAILED"
            # History was not cached — durable cursor stays at the caller's value.
            assert ("BTCUSDT", "1h") not in source._history
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
            # Runner always requests PAGE_LIMIT=1000, so a 6-bar series fits
            # one facing page. end_ms is set far past the series so the runner
            # still needs an empty completion page; max_pages=1 stops before
            # that page — durable cursor stays the resume point.
            venue = TailAlignedVenue(retention=6, limit_cap=1000)
            source, bridge = source_for(venue, max_pages=1)
            far_end = venue.newest_ms + 100 * HOUR
            service = BS.BootstrapService(
                config=Config(), cells=[("BTCUSDT", "1h")], source=source,
                db_path=str(tmp_path / "apex.sqlite3"),
                checkpoint_path=str(tmp_path / "apex.sqlite3"))
            await service.open()
            try:
                first = await service.run(end_ms=far_end, announce=False)
                assert first["status"] == "BUDGET_REACHED"
                assert first["resumable"] is True
                assert first["pages_fetched"] == 1
                assert first["bars_ingested"] == 6
                # the durable cursor is the resume point
                cursor = await service._checkpoints.db.execute(
                    "SELECT cursor_ms, status FROM "
                    "research_bootstrap_progress "
                    "WHERE cell_id='BTCUSDT:1h'")
                row = await cursor.fetchone()
                assert row is not None and row[0] > DEEP_START_MS
                status = await service.status()
                assert status["pages_fetched"] == 1
            finally:
                await service.close()
                bridge.close()

        run(scenario())

    def test_complete_run_marks_the_cell(self, tmp_path):
        async def scenario():
            venue = TailAlignedVenue(retention=3, limit_cap=1000)
            source, bridge = source_for(venue)
            service = BS.BootstrapService(
                config=Config(), cells=[("BTCUSDT", "1h")], source=source,
                db_path=str(tmp_path / "apex.sqlite3"),
                checkpoint_path=str(tmp_path / "apex.sqlite3"))
            await service.open()
            try:
                result = await service.run(
                    end_ms=venue.now_ms + HOUR, announce=False)
                assert result["status"] == "COMPLETE"
                assert result["completed_cells"] == ["BTCUSDT:1h"]
                assert result["pending_cells"] == []
                assert result["bars_ingested"] == 3
                assert result["oi_policy"].startswith("oi_state=MISSING")
            finally:
                await service.close()
                bridge.close()

        run(scenario())

    def test_tail_aligned_pilot_regression_completes_with_bars(self, tmp_path):
        """Owner pilot: completed=1 pages=0 bars=0 against tail-aligned Toobit.
        With CP-11 the cell completes with the retained bars, not zero."""
        async def scenario():
            venue = TailAlignedVenue(retention=4, limit_cap=1000)
            source, bridge = source_for(venue)
            service = BS.BootstrapService(
                config=Config(), cells=[("BTCUSDT", "1h")], source=source,
                db_path=str(tmp_path / "apex.sqlite3"),
                checkpoint_path=str(tmp_path / "apex.sqlite3"))
            await service.open()
            try:
                result = await service.run(
                    start_ms=DEEP_START_MS,
                    end_ms=venue.now_ms + HOUR, announce=False)
                assert result["status"] == "COMPLETE"
                assert result["completed_cells"] == ["BTCUSDT:1h"]
                assert result["bars_ingested"] == 4
                assert result["pages"] >= 1
            finally:
                await service.close()
                bridge.close()

        run(scenario())

    # Canonical mirror — ISSUE-CP9-002 + W.6: research checkpoint is mirrored to Ch.5 bootstrap_progress
    def test_complete_run_mirrors_canonical_done_and_cursor(self, tmp_path):
        """Complete run → canonical row phase='P1' status='DONE' bars_written≥3 and ISO cursor matches research."""
        async def scenario():
            venue = TailAlignedVenue(retention=3, limit_cap=1000)
            source, bridge = source_for(venue)
            service = BS.BootstrapService(
                config=Config(), cells=[("BTCUSDT", "1h")], source=source,
                db_path=str(tmp_path / "apex.sqlite3"),
                checkpoint_path=str(tmp_path / "apex.sqlite3"))
            await service.open()
            try:
                result = await service.run(
                    end_ms=venue.now_ms + HOUR, announce=False)
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
            venue = TailAlignedVenue(retention=6, limit_cap=1000)
            source, bridge = source_for(venue, max_pages=1)
            far_end = venue.newest_ms + 100 * HOUR
            service = BS.BootstrapService(
                config=Config(), cells=[("BTCUSDT", "1h")], source=source,
                db_path=str(tmp_path / "apex.sqlite3"),
                checkpoint_path=str(tmp_path / "apex.sqlite3"))
            await service.open()
            try:
                first = await service.run(end_ms=far_end, announce=False)
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
