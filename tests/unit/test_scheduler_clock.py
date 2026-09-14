"""CP-7 scheduler + clock tests — §9.5-14 (APEX_GEN5.md L20246: on each TF
close run ingest→quality→features→engines→setup→gates→risk→decision→execution
for THAT (symbol,TF), semaphore 4, HTF consumed last-closed only), §9.5-8
universality (140 cells), Ch.23 L18253–18266 (single event loop, bounded worker
pool, contention serialized by the ledger queue), AI.7 L18722–18725 (clock
drift) and Y.2/Ch.16 L16900 leverage = min over ALL caps (T_MONOTONE).
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import pytest

from apex.bus import EventBus, Priority
from apex.data_catalog.contracts import CORE10_SYMBOLS, TIMEFRAMES_14
from apex.execution.toobit_map import LEVERAGE_CAP_BY_TF
from apex.quality.pit import TF_DURATION_SECONDS
from apex.scheduler import clock as C


def run(coro):
    return asyncio.run(coro)


def make_handler(log: List[str], label: str, *, fail: bool = False,
                 hold: float = 0.0):
    """One stage handler double: records the (stage, cell) it ran for."""

    async def handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        log.append(f"{label}:{payload['cell_id']}")
        if hold:
            await asyncio.sleep(hold)
        if fail:
            raise RuntimeError(f"{label} exploded")
        return {"detail": f"{label} ok"}

    return handler


def handlers(log: List[str], *, hold: float = 0.0, fail_at: str = "") -> Dict:
    return {stage: make_handler(log, stage, hold=hold, fail=(stage == fail_at))
            for stage in C.PIPELINE_STAGES}


# ---------------------------------------------------------------------------
# Universality: 140 cells
# ---------------------------------------------------------------------------

class TestUniverse:
    def test_the_grid_is_exactly_140_cells(self):
        cells = C.universe_cells()
        assert len(cells) == 140
        assert C.UNIVERSE_CELLS == 140 == len(CORE10_SYMBOLS) * len(TIMEFRAMES_14)

    def test_every_core10_symbol_appears_with_all_fourteen_timeframes(self):
        cells = C.universe_cells()
        for symbol in CORE10_SYMBOLS:
            tfs = sorted(c.timeframe for c in cells if c.symbol == symbol)
            assert tfs == sorted(TIMEFRAMES_14)

    def test_cell_ids_are_symbol_colon_timeframe(self):
        cell = C.BundleCell(symbol="BTCUSDT", timeframe="1mo")
        assert cell.cell_id == "BTCUSDT:1mo"
        assert cell.tf_seconds == TF_DURATION_SECONDS["1mo"]

    def test_3d_is_not_in_the_grid(self):
        assert all(c.timeframe != "3d" for c in C.universe_cells())

    def test_a_disabled_cell_is_removed_from_the_grid_only(self):
        """Ch.16 L16877: −1120 disables that TF for that symbol ONLY."""
        cells = C.universe_cells(disabled={"BTCUSDT": ["1mo"]})
        assert len(cells) == 139
        assert C.BundleCell("BTCUSDT", "1mo") not in cells
        assert C.BundleCell("BTCUSDT", "1h") in cells
        assert C.BundleCell("ETHUSDT", "1mo") in cells

    def test_tf_durations_come_from_the_frozen_pit_table(self):
        for tf in TIMEFRAMES_14:
            assert C.tf_seconds(tf) == TF_DURATION_SECONDS[tf]

    def test_an_unknown_timeframe_fails_closed(self):
        with pytest.raises(C.SchedulerError) as exc:
            C.tf_seconds("3d")
        assert exc.value.reason == "E-VAL-022"


class TestCloseBoundaries:
    def test_next_close_is_the_next_boundary(self):
        clock = C.FixtureClock("2026-01-01T00:00:00.000Z")
        assert clock.advance_to_next_close("1h") == "2026-01-01T01:00:00.000Z"
        assert clock.advance_to_next_close("15m") == "2026-01-01T01:15:00.000Z"
        assert clock.advance_to_next_close("1d") == "2026-01-02T00:00:00.000Z"

    def test_close_times_enumerate_every_boundary(self):
        start = C.FixtureClock("2026-01-01T00:00:00.000Z").now_ms()
        end = C.FixtureClock("2026-01-01T01:00:00.000Z").now_ms()
        closes = C.tf_close_times("15m", start_ms=start, end_ms=end)
        assert len(closes) == 4
        assert closes == sorted(closes)

    def test_next_close_matches_the_enumeration(self):
        now = C.FixtureClock("2026-01-01T00:07:00.000Z").now_ms()
        assert C.next_close("15m", now_ms=now) == \
            C.FixtureClock("2026-01-01T00:15:00.000Z").now_ms()


# ---------------------------------------------------------------------------
# Fixture clock determinism
# ---------------------------------------------------------------------------

class TestFixtureClock:
    def test_time_moves_only_when_the_test_moves_it(self):
        clock = C.FixtureClock("2026-01-01T00:00:00.000Z")
        assert clock.now_ms() == clock.now_ms()
        assert clock.utc_now() == "2026-01-01T00:00:00.000Z"
        clock.advance(1.5)
        assert clock.utc_now() == "2026-01-01T00:00:01.500Z"
        assert clock.elapsed_seconds == 1.5
        assert clock.monotonic() == 1.5

    def test_the_fixture_clock_never_runs_backward(self):
        clock = C.FixtureClock()
        with pytest.raises(C.SchedulerError) as exc:
            clock.advance(-1)
        assert exc.value.reason == "FIXTURE_CLOCK_BACKWARD"
        with pytest.raises(C.SchedulerError):
            clock.advance_to("2020-01-01T00:00:00.000Z")

    def test_iso_round_trip_is_millisecond_exact(self):
        stamp = "2026-03-04T05:06:07.890Z"
        clock = C.FixtureClock(stamp)
        assert clock.utc_now() == stamp

    def test_the_system_clock_reports_utc_with_milliseconds(self):
        stamp = C.SystemClock().utc_now()
        assert stamp.endswith("Z")
        assert len(stamp) == 24
        assert C.SystemClock().now_ms() > 0


# ---------------------------------------------------------------------------
# Drift gates (Ch.23 L18244 + AI.7 L18722–18725)
# ---------------------------------------------------------------------------

class TestDrift:
    def test_governed_literals(self):
        assert C.CLOCK_DRIFT_TOLERANCE_SECONDS == 5.0
        assert C.E12_DRIFT_DEGRADED_SECONDS == 0.5
        assert C.NTP_SYNC_TARGET_SECONDS == 0.1

    @pytest.mark.parametrize("drift,state,blocks,e12", [
        (0.0, "SYNCED", False, False),
        (0.05, "SYNCED", False, False),
        (0.1, "SYNCED", False, False),
        (0.6, "DEGRADED", True, True),
        (5.0, "DEGRADED", True, True),
        (5.1, "BLOCKED", True, True),
        (-9.0, "BLOCKED", True, True)])
    def test_drift_verdict(self, drift, state, blocks, e12):
        verdict = C.drift_verdict(drift)
        assert verdict["state"] == state
        assert verdict["blocks_new_trades"] is blocks
        assert verdict["e12_degraded"] is e12

    def test_a_negative_drift_is_treated_by_magnitude(self):
        assert C.drift_verdict(-0.6)["state"] == "DEGRADED"

    def test_an_unmeasurable_clock_never_assumes_sync(self):
        async def broken():
            raise RuntimeError("no route to host")

        verdict = run(C.measure_drift(broken, C.FixtureClock()))
        assert verdict["state"] == "UNAVAILABLE"
        assert verdict["blocks_new_trades"] is True
        assert verdict["drift_seconds"] is None

    def test_a_missing_server_time_field_fails_closed(self):
        async def empty():
            return {"code": 0, "data": {}}

        verdict = run(C.measure_drift(empty, C.FixtureClock()))
        assert verdict["state"] == "UNAVAILABLE"
        assert verdict["reason"] == "SERVER_TIME_FIELD_MISSING"

    def test_drift_is_measured_against_the_exchange_server_time(self):
        clock = C.FixtureClock("2026-01-01T00:00:00.000Z")

        async def server_time():
            return {"code": 0, "msg": "success",
                    "data": {"serverTime": clock.now_ms() - 7000}}

        verdict = run(C.measure_drift(server_time, clock))
        assert verdict["drift_seconds"] == pytest.approx(7.0)
        assert verdict["state"] == "BLOCKED"
        assert verdict["blocks_new_trades"] is True


# ---------------------------------------------------------------------------
# T_MONOTONE — leverage = min over ALL caps, never last-writer
# ---------------------------------------------------------------------------

class TestTMonotone:
    def test_the_cap_set_is_evaluated_together(self):
        resolved = C.monotone_leverage("1mo", symbol="BTCUSDT", owner_cap=3,
                                       extra_caps=(7.0,))
        assert resolved["leverage"] == 3.0
        assert set(resolved["caps"]) == {"y2_tf_cap", "exchange_max",
                                         "owner_cap", "extra_cap_0"}
        assert resolved["order_independent"] is True
        assert resolved["binding_cap"] == "owner_cap"
        assert resolved["never_send_125x"] is True

    def test_a_last_writer_policy_would_give_the_wrong_answer(self):
        """A sequential "last writer wins" override would end at the LAST cap
        supplied (here an owner cap of 7 on a 1m cell whose Y.2 cap is 2);
        min over ALL caps must return 2."""
        resolved = C.monotone_leverage("1m", symbol="BTCUSDT", owner_cap=7)
        assert resolved["last_writer_value"] == 7.0
        assert resolved["leverage"] == 2.0
        assert resolved["differs_from_last_writer"] is True
        assert resolved["binding_cap"] == "y2_tf_cap"

    def test_the_running_minimum_never_increases(self):
        resolved = C.monotone_leverage("1h", symbol="BTCUSDT", owner_cap=3)
        assert resolved["running_min_non_increasing"] is True

    def test_tightening_a_cap_can_only_lower_the_result(self):
        base = C.monotone_leverage("1h", symbol="BTCUSDT")["leverage"]
        for cap in (10, 4, 3, 2, 1):
            tighter = C.monotone_leverage("1h", symbol="BTCUSDT",
                                          owner_cap=cap)["leverage"]
            assert tighter <= base
            base = tighter

    def test_the_cap_order_is_irrelevant(self):
        forward = C.monotone_leverage("4h", symbol="ETHUSDT", owner_cap=3,
                                      extra_caps=(2.5, 9.0))["leverage"]
        backward = C.monotone_leverage("4h", symbol="ETHUSDT", owner_cap=9.0,
                                       extra_caps=(2.5, 3.0))["leverage"]
        assert forward == backward == 2.5

    def test_monotone_check_permutation_invariance(self):
        verdict = C.monotone_check([5, 3, 4, 2])
        assert verdict["minimum"] == 2
        assert verdict["running_min"] == [5, 3, 3, 2]
        assert verdict["non_increasing"] is True
        assert verdict["permutation_invariant"] is True

    def test_an_empty_cap_set_is_refused(self):
        with pytest.raises(C.SchedulerError) as exc:
            C.monotone_check([])
        assert exc.value.reason == "CAP_SET_EMPTY"

    @pytest.mark.parametrize("tf", TIMEFRAMES_14)
    def test_no_cell_can_exceed_its_tf_cap(self, tf):
        for symbol in CORE10_SYMBOLS:
            resolved = C.monotone_leverage(tf, symbol=symbol)
            assert resolved["leverage"] <= LEVERAGE_CAP_BY_TF[tf]
            assert resolved["leverage"] < 125


# ---------------------------------------------------------------------------
# HTF last-closed only (§9.5-14 / SL-8 PIT law)
# ---------------------------------------------------------------------------

class TestHtfLastClosed:
    def test_the_policy_constant(self):
        assert C.HTF_POLICY == "LAST_CLOSED_ONLY"

    def test_a_last_closed_htf_candle_is_allowed(self):
        verdict = C.htf_last_closed_guard(htf_close_ms=1000,
                                          current_close_ms=2000)
        assert verdict["allowed"] is True
        assert verdict["reason"] is None

    def test_a_future_htf_candle_is_a_future_leak(self):
        verdict = C.htf_last_closed_guard(htf_close_ms=3000,
                                          current_close_ms=2000)
        assert verdict["allowed"] is False
        assert verdict["reason"] == "E-PIT-001"

    def test_an_htf_candle_closing_exactly_now_is_allowed(self):
        assert C.htf_last_closed_guard(htf_close_ms=2000,
                                       current_close_ms=2000)["allowed"] is True


# ---------------------------------------------------------------------------
# The scheduler itself
# ---------------------------------------------------------------------------

class TestPipelineOrder:
    def test_the_nine_stages_are_exactly_the_contract_order(self):
        assert C.PIPELINE_STAGES == ("ingest", "quality", "features", "engines",
                                     "setup", "gates", "risk", "decision",
                                     "execution")
        assert len(C.PIPELINE_STAGES) == 9

    def test_a_cell_runs_the_stages_in_order(self):
        log: List[str] = []

        async def body():
            scheduler = C.Scheduler(clock=C.FixtureClock(),
                                    handlers=handlers(log))
            run_result = await scheduler.run_cell(C.BundleCell("BTCUSDT", "1h"))
            return run_result

        result = run(body())
        assert result.status == "COMPLETE"
        assert [s.stage for s in result.stages] == list(C.PIPELINE_STAGES)
        assert log == [f"{stage}:BTCUSDT:1h" for stage in C.PIPELINE_STAGES]
        assert all(s.status == "PASS" for s in result.stages)

    def test_a_missing_stage_halts_the_cell_and_is_never_skipped(self):
        log: List[str] = []

        async def body():
            partial = {stage: handler for stage, handler
                       in handlers(log).items() if stage != "gates"}
            scheduler = C.Scheduler(clock=C.FixtureClock(), handlers=partial)
            return await scheduler.run_cell(C.BundleCell("BTCUSDT", "1h"))

        result = run(body())
        assert result.status == "HALTED"
        assert result.reason == "STAGE_UNAVAILABLE:gates"
        assert [s.stage for s in result.stages] == list(C.PIPELINE_STAGES)[:6]
        assert result.stages[-1].status == "UNAVAILABLE"
        assert "decision:BTCUSDT:1h" not in log     # nothing after the gap ran

    def test_a_failing_stage_halts_the_cell(self):
        log: List[str] = []

        async def body():
            scheduler = C.Scheduler(clock=C.FixtureClock(),
                                    handlers=handlers(log, fail_at="risk"))
            return await scheduler.run_cell(C.BundleCell("ETHUSDT", "15m"))

        result = run(body())
        assert result.status == "HALTED"
        assert result.reason == "STAGE_FAILED:risk"
        assert [s.stage for s in result.stages][-1] == "risk"
        assert "decision:ETHUSDT:15m" not in log

    def test_an_unregistered_stage_name_is_refused(self):
        scheduler = C.Scheduler(clock=C.FixtureClock())
        with pytest.raises(C.SchedulerError) as exc:
            scheduler.register("liquidation", None)
        assert exc.value.reason == "STAGE_UNKNOWN"

    def test_each_cell_only_sees_its_own_symbol_and_timeframe(self):
        seen: List[Dict[str, Any]] = []

        async def body():
            async def handler(payload):
                seen.append({"cell": payload["cell_id"],
                             "symbol": payload["symbol"],
                             "timeframe": payload["timeframe"],
                             "close_ms": payload["close_ms"],
                             "htf_policy": payload["htf_policy"]})
                return {"detail": "ok"}

            scheduler = C.Scheduler(clock=C.FixtureClock(),
                                    handlers={s: handler
                                              for s in C.PIPELINE_STAGES})
            await scheduler.run_cell(C.BundleCell("BTCUSDT", "1h"))
            await scheduler.run_cell(C.BundleCell("ETHUSDT", "15m"))
            return seen

        rows = run(body())
        assert {r["cell"] for r in rows} == {"BTCUSDT:1h", "ETHUSDT:15m"}
        assert all(r["htf_policy"] == "LAST_CLOSED_ONLY" for r in rows)
        assert len({r["symbol"] for r in rows if r["cell"] == "BTCUSDT:1h"}) == 1


class TestSemaphore:
    def test_the_governed_bound_is_four(self):
        assert C.SCHEDULER_SEMAPHORE == 4

    def test_a_full_burst_never_exceeds_four_concurrent_cells(self):
        async def body():
            scheduler = C.Scheduler(clock=C.FixtureClock(),
                                    handlers=handlers([], hold=0.001))
            cells = C.universe_cells()
            runs = await scheduler.run_burst(cells)
            return scheduler.concurrent_peak, len(runs), \
                scheduler.semaphore_value

        peak, count, bound = run(body())
        assert bound == 4
        assert count == 140
        assert 1 < peak <= 4

    def test_a_non_positive_semaphore_is_refused(self):
        with pytest.raises(C.SchedulerError) as exc:
            C.Scheduler(clock=C.FixtureClock(), semaphore=0)
        assert exc.value.reason == "SEMAPHORE_NON_POSITIVE"


class TestPriorityLanes:
    def test_priority_order_is_p0_to_p3(self):
        assert C.PRIORITY_ORDER == (Priority.P0, Priority.P1, Priority.P2,
                                    Priority.P3)
        assert [int(p) for p in C.PRIORITY_ORDER] == [0, 1, 2, 3]

    def test_a_p0_cell_runs_before_an_earlier_p2_cell(self):
        order: List[str] = []

        async def body():
            async def handler(payload):
                if payload["stage"] == "ingest":
                    order.append(f"{payload['cell_id']}:{payload['priority']}")
                return {"detail": "ok"}

            cells = (C.BundleCell("BTCUSDT", "1h"),
                     C.BundleCell("ETHUSDT", "1h"))
            scheduler = C.Scheduler(clock=C.FixtureClock(), cells=cells,
                                    handlers={s: handler
                                              for s in C.PIPELINE_STAGES},
                                    semaphore=1)
            await scheduler.run_due(priority_map={"ETHUSDT:1h": int(Priority.P0),
                                                  "BTCUSDT:1h": int(Priority.P2)})
            return order

        first = run(body())
        assert first[0] == "ETHUSDT:1h:0"      # P0 wins over the earlier close
        assert first[1] == "BTCUSDT:1h:2"

    def test_due_cells_are_ordered_by_close_then_symbol_then_timeframe(self):
        clock = C.FixtureClock("2026-01-01T01:00:00.000Z")
        scheduler = C.Scheduler(clock=clock)
        due = scheduler.due_cells()
        assert len(due) == 140
        keys = [(close, cell.symbol, cell.timeframe) for cell, close in due]
        assert keys == sorted(keys)

    def test_a_cell_run_is_published_on_the_bus(self):
        async def body():
            bus = EventBus()
            events: List[Any] = []

            async def collector(event):
                events.append(event)

            bus.subscribe("scheduler.cell", collector)
            task = bus.start()
            try:
                scheduler = C.Scheduler(clock=C.FixtureClock(), bus=bus,
                                        handlers=handlers([]))
                await scheduler.run_cell(C.BundleCell("BTCUSDT", "1h"))
                for _ in range(10):
                    await asyncio.sleep(0)
            finally:
                await bus.stop()
            return events

        events = run(body())
        assert len(events) == 1
        assert events[0].payload["cell_id"] == "BTCUSDT:1h"
        assert events[0].payload["status"] == "COMPLETE"
        assert events[0].payload["leverage"] == 4.0     # 1h cap


class TestDriftBlock:
    def test_drift_beyond_tolerance_blocks_every_cell(self):
        log: List[str] = []

        async def body():
            cells = tuple(C.universe_cells()[:5])
            scheduler = C.Scheduler(clock=C.FixtureClock(), cells=cells,
                                    handlers=handlers(log), drift_seconds=6.0)
            runs = await scheduler.run_due(limit=5)
            return runs

        runs = run(body())
        assert len(runs) == 5
        assert all(r.status == "BLOCKED" for r in runs)
        assert all(r.reason == "CLOCK_DRIFT_BEYOND_TOLERANCE" for r in runs)
        assert all(r.stages == () for r in runs)
        assert log == []                       # no stage ran at all

    def test_e12_drift_also_blocks_new_trades(self):
        log: List[str] = []

        async def body():
            scheduler = C.Scheduler(clock=C.FixtureClock(),
                                    handlers=handlers(log), drift_seconds=0.6)
            return (await scheduler.run_cell(C.BundleCell("BTCUSDT", "1h")))

        result = run(body())
        assert result.status == "BLOCKED"
        assert result.reason == "E12_CLOCK_DRIFT_DEGRADED"
        assert result.stages == ()
        assert log == []

    def test_a_synced_clock_runs_normally(self):
        async def body():
            scheduler = C.Scheduler(clock=C.FixtureClock(),
                                    handlers=handlers([]), drift_seconds=0.01)
            return (await scheduler.run_cell(C.BundleCell("BTCUSDT", "1h"))).status

        assert run(body()) == "COMPLETE"


class TestContentionSerialization:
    def test_known_contention_points_are_serialized(self):
        """Ch.23 L18256–18260: a concurrent fill and quality update on the same
        position, reconciliation overlapping a submission, a backup during a
        candle-close burst — all serialized by the ledger queue."""
        active = {"now": 0, "peak": 0}

        async def body():
            async def work(name):
                async def item():
                    active["now"] += 1
                    active["peak"] = max(active["peak"], active["now"])
                    await asyncio.sleep(0.001)
                    active["now"] -= 1
                    return name

                return item

            scheduler = C.Scheduler(clock=C.FixtureClock())
            items = [await work(n) for n in ("fill", "quality", "reconcile",
                                             "submit", "backup")]
            return await scheduler.serialized(items)

        results = run(body())
        assert results == ["fill", "quality", "reconcile", "submit", "backup"]
        assert active["peak"] == 1              # never two writers at once


class TestCellLeverage:
    def test_each_cell_carries_its_own_min_cap_leverage(self):
        async def body():
            seen = {}

            async def handler(payload):
                if payload["stage"] == "risk":
                    seen[payload["cell_id"]] = payload["leverage"]
                return {"detail": "ok"}

            scheduler = C.Scheduler(clock=C.FixtureClock(),
                                    handlers={s: handler
                                              for s in C.PIPELINE_STAGES},
                                    owner_leverage_cap=None)
            for cell in (C.BundleCell("BTCUSDT", "1m"),
                         C.BundleCell("BTCUSDT", "1mo"),
                         C.BundleCell("ETHUSDT", "1h")):
                await scheduler.run_cell(cell)
            return seen

        seen = run(body())
        assert seen == {"BTCUSDT:1m": 2.0, "BTCUSDT:1mo": 5.0,
                        "ETHUSDT:1h": 4.0}

    def test_an_owner_cap_lowers_every_cell(self):
        async def body():
            scheduler = C.Scheduler(clock=C.FixtureClock(),
                                    handlers=handlers([]),
                                    owner_leverage_cap=1.5)
            runs = [await scheduler.run_cell(C.BundleCell(s, tf))
                    for s, tf in (("BTCUSDT", "1mo"), ("ETHUSDT", "1h"))]
            return [r.leverage for r in runs]

        assert run(body()) == [1.5, 1.5]


class TestCellLookup:
    def test_a_cell_outside_the_universe_is_refused(self):
        scheduler = C.Scheduler(clock=C.FixtureClock())
        with pytest.raises(C.SchedulerError) as exc:
            scheduler.cell("DOGEUSD", "1h")
        assert exc.value.reason == "CELL_NOT_IN_UNIVERSE"

    def test_the_scheduler_defaults_to_the_full_grid(self):
        scheduler = C.Scheduler(clock=C.FixtureClock())
        assert len(scheduler.cells) == 140
        assert scheduler.cell("BTCUSDT", "1mo").cell_id == "BTCUSDT:1mo"

    def test_runs_are_an_immutable_view(self):
        async def body():
            scheduler = C.Scheduler(clock=C.FixtureClock(), handlers=handlers([]))
            await scheduler.run_cell(C.BundleCell("BTCUSDT", "1h"))
            runs = scheduler.runs
            with pytest.raises(TypeError):
                runs[0] = None
            return len(runs)

        assert run(body()) == 1
