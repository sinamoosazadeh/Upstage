"""CP-8 — Ch.18 W.6/W.8 bootstrap runner: hardware preflight thresholds, the
owner command surface, resume-never-rewind paging with the −1003 backoff,
24-h pause recheck, Phase-2 determinism veto and the Phase-3 hand-off
(MATRIX Part III CP-8 rows C8-BS|1..20)."""

from __future__ import annotations

import asyncio

import pytest

from apex.research import bootstrap as bs
from apex.research.checkpoints import ResearchCheckpointStore


def _run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------
# W.6 — hardware preflight
# --------------------------------------------------------------------------

class TestHardwarePreflight:
    def test_low_disk_pauses_before_anything_else(self):
        out = bs.hardware_preflight(free_disk_mb=100.0,
                                    battery={"percentage": 5, "plugged": True})
        assert out["action"] == "PAUSE"
        assert out["reason"] == "FREE_DISK_BELOW_512MB"

    def test_disk_floor_is_exactly_512(self):
        assert bs.hardware_preflight(free_disk_mb=511.9)["action"] == "PAUSE"
        assert bs.hardware_preflight(free_disk_mb=512.0)["action"] == "PROCEED"

    def test_absent_battery_api_never_skips(self):
        out = bs.hardware_preflight(free_disk_mb=10_000.0, battery=None)
        assert out["action"] == "PROCEED"
        assert out["reason"] == "BATTERY_API_ABSENT_DO_NOT_SKIP"

    def test_unplugged_below_15_pct_skips_a_nightly_run(self):
        out = bs.hardware_preflight(free_disk_mb=10_000.0,
                                    battery={"percentage": 10, "plugged": False})
        assert out["action"] == "SKIP_NIGHTLY"
        assert out["reason"] == "BATTERY_BELOW_15PCT"

    def test_unplugged_above_15_pct_runs(self):
        out = bs.hardware_preflight(free_disk_mb=10_000.0,
                                    battery={"percentage": 20, "plugged": False})
        assert out["action"] == "PROCEED"

    def test_charging_below_15_pct_still_runs(self):
        out = bs.hardware_preflight(free_disk_mb=10_000.0,
                                    battery={"percentage": 3, "plugged": True})
        assert out["action"] == "PROCEED"

    def test_continuous_unplugged_below_5_pct_pauses(self):
        out = bs.hardware_preflight(free_disk_mb=10_000.0,
                                    battery={"percentage": 4, "plugged": False},
                                    continuous=True)
        assert out["action"] == "PAUSE"
        assert out["reason"] == "CONTINUOUS_BATTERY_BELOW_5PCT"

    def test_continuous_unplugged_between_5_and_15_runs(self):
        out = bs.hardware_preflight(free_disk_mb=10_000.0,
                                    battery={"percentage": 8, "plugged": False},
                                    continuous=True)
        assert out["action"] == "PROCEED"

    def test_percentage_given_as_fraction(self):
        out = bs.hardware_preflight(free_disk_mb=10_000.0,
                                    battery={"percentage": 0.10, "plugged": False})
        assert out["action"] == "SKIP_NIGHTLY"

    def test_percentage_absent_never_skips(self):
        out = bs.hardware_preflight(free_disk_mb=10_000.0,
                                    battery={"plugged": False})
        assert out["action"] == "PROCEED"

    def test_parse_battery_json(self):
        assert bs.parse_battery_json('{"percentage": 42, "plugged": "true"}') == \
            {"percentage": 42, "plugged": True}

    @pytest.mark.parametrize("text", [None, "", "not json", "{}", '"x"', "[1]"])
    def test_parse_battery_json_fails_soft_to_none(self, text):
        assert bs.parse_battery_json(text) is None


# --------------------------------------------------------------------------
# W.8-2 — command surface
# --------------------------------------------------------------------------

class TestCommands:
    def _runner(self, tmp_path, **kwargs):
        return bs.BootstrapRunner(
            fetcher=kwargs.pop("fetcher", _no_rows),
            ingest=kwargs.pop("ingest", _sink),
            store=ResearchCheckpointStore(path=str(tmp_path / "r.sqlite3")),
            cells=[("BTCUSDT", "15m")], **kwargs)

    def test_exactly_the_eight_owner_commands(self):
        assert bs.COMMANDS == ("start", "pause", "resume", "stop", "progress",
                               "eta", "continuous on", "continuous off")

    def test_unknown_command_refused(self, tmp_path):
        runner = self._runner(tmp_path)
        with pytest.raises(bs.BootstrapError) as err:
            runner.command("reboot")
        assert err.value.reason == "UNKNOWN_COMMAND"

    def test_start_pause_resume_cycle(self, tmp_path):
        runner = self._runner(tmp_path)
        runner.command("start")
        assert runner.state.started is True
        runner.command("pause")
        assert runner.state.paused is True
        runner.command("resume")
        assert runner.state.paused is False

    def test_resume_before_start_refused(self, tmp_path):
        runner = self._runner(tmp_path)
        with pytest.raises(bs.BootstrapError) as err:
            runner.command("resume")
        assert err.value.reason == "NOT_STARTED"

    def test_stop_is_terminal(self, tmp_path):
        runner = self._runner(tmp_path)
        runner.command("start")
        runner.command("stop")
        assert runner.state.stopped is True
        with pytest.raises(bs.BootstrapError) as err:
            runner.command("start")
        assert err.value.reason == "BOOTSTRAP_STOPPED"

    def test_continuous_mode_toggle(self, tmp_path):
        runner = self._runner(tmp_path)
        assert runner.command("continuous on")["state"]["continuous"] is True
        assert runner.command("continuous off")["state"]["continuous"] is False

    def test_progress_and_eta_answer_without_running(self, tmp_path):
        runner = self._runner(tmp_path)
        assert runner.command("progress")["cells_total"] == 1
        eta = runner.command("eta")
        assert eta["measured"] is False
        assert eta["eta_seconds"] is None

    def test_pause_recheck_flag_after_24_hours(self):
        clock = {"now": 1_000_000.0}
        runner = bs.BootstrapRunner(
            fetcher=_no_rows, ingest=_sink,
            store=ResearchCheckpointStore(path="/tmp/unused.sqlite3"),
            cells=[("BTCUSDT", "15m")], now=lambda: clock["now"])
        runner.command("start")
        runner.command("pause")
        clock["now"] += 23 * 3600
        assert runner.health_recheck_required()["required"] is False
        clock["now"] += 2 * 3600
        assert runner.health_recheck_required()["required"] is True

    def test_no_cells_refused(self):
        with pytest.raises(bs.BootstrapError) as err:
            bs.BootstrapRunner(fetcher=_no_rows, ingest=_sink,
                               store=ResearchCheckpointStore(path="/tmp/x.sqlite3"),
                               cells=[])
        assert err.value.reason == "NO_CELLS"


def _no_rows(symbol, timeframe, start_ms, end_ms, limit):
    return {"rows": [], "next_cursor_ms": end_ms, "code": None}


async def _sink(rows, symbol, timeframe):
    return len(rows)


# --------------------------------------------------------------------------
# W.6/W.8 — Phase 1 paging
# --------------------------------------------------------------------------

class _Fetcher:
    """Per-cell page walker: ``total_pages`` pages of bars, then end-of-data."""

    def __init__(self, *, rate_limit_first: int = 0, bars_per_page: int = 10,
                 total_pages: int = 3):
        self.calls = 0
        self.rate_limit_first = rate_limit_first
        self.bars_per_page = bars_per_page
        self.total_pages = total_pages
        self._pages: dict = {}
        self._limited = 0

    def __call__(self, symbol, timeframe, start_ms, end_ms, limit):
        self.calls += 1
        if self._limited < self.rate_limit_first:
            self._limited += 1
            return {"rows": [], "next_cursor_ms": None, "code": -1003}
        key = (symbol, timeframe)
        page = self._pages.get(key, 0) + 1
        self._pages[key] = page
        if page > self.total_pages:
            return {"rows": [], "next_cursor_ms": end_ms, "code": None}
        rows = [{"ts": start_ms + i} for i in range(self.bars_per_page)]
        return {"rows": rows, "next_cursor_ms": start_ms + 900_000,
                "code": None}


class TestPhase1:
    def _runner(self, tmp_path, fetcher, verifier=None, ingested=None):
        async def ingest(rows, symbol, timeframe):
            if ingested is not None:
                ingested.extend(rows)
            return len(rows)

        return bs.BootstrapRunner(
            fetcher=fetcher, ingest=ingest,
            store=ResearchCheckpointStore(path=str(tmp_path / "r.sqlite3")),
            cells=[("BTCUSDT", "15m"), ("ETHUSDT", "15m")],
            phase1_verifier=verifier)

    def test_phase1_walks_every_cell_and_completes(self, tmp_path):
        ingested = []
        runner = self._runner(tmp_path, _Fetcher(), ingested=ingested)

        async def _flow():
            async with runner.store as store:
                return await runner.run_phase1(
                    start_ms=1_000_000, end_ms=1_000_000 + 3 * 900_000)
        result = _run(_flow())
        assert result["status"] == "COMPLETE"
        assert result["completed_cells"] == ["BTCUSDT:15m", "ETHUSDT:15m"]
        assert result["pending_cells"] == []
        assert len(ingested) == 2 * 3 * 10

    def test_rate_limit_backs_off_and_never_skips(self, tmp_path):
        runner = self._runner(tmp_path, _Fetcher(rate_limit_first=3))

        async def _flow():
            async with runner.store as store:
                return await runner.run_phase1(
                    start_ms=1_000_000, end_ms=1_000_000 + 900_000)
        result = _run(_flow())
        assert result["backoffs"] == 3
        assert result["status"] == "COMPLETE"

    def test_cursor_never_rewinds_on_rerun(self, tmp_path):
        fetcher = _Fetcher(total_pages=100)
        runner = self._runner(tmp_path, fetcher)

        async def _first():
            async with runner.store as store:
                await runner.run_phase1(start_ms=1_000_000,
                                        end_ms=1_000_000 + 3 * 900_000)
                return await store.load_bootstrap("BTCUSDT:15m")

        first = _run(_first())
        progress_before = runner.state.bars_ingested

        async def _second():
            async with runner.store as store:
                await runner.run_phase1(start_ms=0,   # a hostile earlier start
                                        end_ms=1_000_000 + 3 * 900_000)
                return await store.load_bootstrap("BTCUSDT:15m")
        second = _run(_second())
        assert second["cursor_ms"] >= first["cursor_ms"]
        assert runner.state.bars_ingested >= progress_before

    def test_pause_stops_after_the_current_page_and_keeps_sqlite(self, tmp_path):
        runner = self._runner(tmp_path, _Fetcher())
        runner.command("start")

        async def _flow():
            async with runner.store as store:
                runner.command("pause")
                return await runner.run_phase1(start_ms=1_000_000,
                                               end_ms=1_000_000 + 3 * 900_000)
        result = _run(_flow())
        assert result["status"] == "PAUSED"
        assert "BTCUSDT:15m" in result["pending_cells"]

    def test_failed_verification_marks_the_cell_skipped(self, tmp_path):
        runner = self._runner(
            tmp_path, _Fetcher(),
            verifier=lambda info: {"verified": False, "reason": "GAP"})

        async def _flow():
            async with runner.store as store:
                return await runner.run_phase1(start_ms=1_000_000,
                                               end_ms=1_000_000 + 900_000)
        result = _run(_flow())
        assert result["skipped_cells"] == ["BTCUSDT:15m", "ETHUSDT:15m"]
        assert result["completed_cells"] == []

    def test_disk_pause_is_honoured_before_paging(self, tmp_path):
        fetcher = _Fetcher()
        runner = self._runner(tmp_path, fetcher)

        async def _flow():
            async with runner.store as store:
                return await runner.run_phase1(free_disk_mb=10.0)
        result = _run(_flow())
        assert result["status"] == "PAUSED"
        assert fetcher.calls == 0

    def test_battery_skip_is_honoured(self, tmp_path):
        fetcher = _Fetcher()
        runner = self._runner(tmp_path, fetcher)

        async def _flow():
            async with runner.store as store:
                return await runner.run_phase1(
                    battery={"percentage": 10, "plugged": False})
        # W.6: below 15 % unplugged the nightly run is skipped, not paused
        result = _run(_flow())
        assert result["status"] == "COMPLETE"

    def test_non_advancing_cursor_is_a_failure_not_a_loop(self, tmp_path):
        def stuck(symbol, timeframe, start_ms, end_ms, limit):
            return {"rows": [], "next_cursor_ms": start_ms, "code": None}

        runner = self._runner(tmp_path, stuck)

        async def _flow():
            async with runner.store as store:
                return await runner.run_phase1(start_ms=1_000_000,
                                               end_ms=1_000_000 + 900_000)
        with pytest.raises(bs.BootstrapError) as err:
            _run(_flow())
        assert err.value.reason == "CURSOR_NOT_ADVANCING"

    def test_timeframe_table_has_the_fourteen_frozen_timeframes(self):
        assert len(bs.BootstrapRunner._ms_per_bar.__doc__ or "") >= 0
        table = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h",
                 "12h", "1d", "1w", "1mo"}
        for timeframe in table:
            assert bs.BootstrapRunner._ms_per_bar(timeframe) > 0
        with pytest.raises(bs.BootstrapError) as err:
            bs.BootstrapRunner._ms_per_bar("7m")
        assert err.value.reason == "TIMEFRAME_QX"

    def test_deep_start_is_2020_01_01(self):
        assert bs.DEEP_START_ISO == "2020-01-01T00:00:00Z"
        assert bs.DEEP_START_MS == 1577836800000
        assert bs.PAGE_LIMIT == 1000


# --------------------------------------------------------------------------
# Phases 2 and 3
# --------------------------------------------------------------------------

class TestPhase2Phase3:
    def _runner(self, tmp_path):
        return bs.BootstrapRunner(
            fetcher=_no_rows, ingest=_sink,
            store=ResearchCheckpointStore(path=str(tmp_path / "r.sqlite3")),
            cells=[("BTCUSDT", "15m")])

    def test_deterministic_replay_activates_defaults(self, tmp_path):
        runner = self._runner(tmp_path)

        async def _flow():
            async with runner.store:
                return await runner.run_phase2(replay=lambda: {"pnl": 1.5})
        result = _run(_flow())
        assert result["deterministic"] is True
        assert result["defaults_active"] is True

    def test_non_deterministic_replay_is_a_critical_failure(self, tmp_path):
        runner = self._runner(tmp_path)
        state = {"n": 0}

        def flaky():
            state["n"] += 1
            return {"pnl": state["n"]}

        async def _flow():
            async with runner.store:
                return await runner.run_phase2(replay=flaky)
        result = _run(_flow())
        assert result["defaults_active"] is False
        assert result["status"] == "CRITICAL_FAILURE"
        assert result["critical_failures"] == ["NON_DETERMINISTIC_REPLAY"]

    def test_replay_is_mandatory(self, tmp_path):
        runner = self._runner(tmp_path)

        async def _flow():
            async with runner.store:
                return await runner.run_phase2()
        with pytest.raises(bs.BootstrapError) as err:
            _run(_flow())
        assert err.value.reason == "PHASE2_REPLAY_REQUIRED"

    def test_phase3_hands_off_to_the_optimizer(self, tmp_path):
        plan = self._runner(tmp_path).phase3_plan()
        assert plan["phase"] == 3
        assert plan["cells"] == ["BTCUSDT:15m"]
        assert "DualOptimizer" in plan["requires"]
        assert plan["default_window"] == "03:00-05:00 UTC (W.4)"

    def test_progress_counts_completed_cells_from_the_store(self, tmp_path):
        runner = self._runner(tmp_path)

        async def _flow():
            async with runner.store as store:
                await store.save_bootstrap(cell_id="BTCUSDT:15m",
                                           symbol="BTCUSDT", timeframe="15m",
                                           phase=1, status="COMPLETE",
                                           cursor_ms=1)
                return await runner.progress_async()
        out = _run(_flow())
        assert out["cells_completed"] == 1
        assert out["cells_remaining"] == 0

    def test_eta_needs_a_measurement(self, tmp_path):
        runner = self._runner(tmp_path)
        assert runner.eta()["measured"] is False
