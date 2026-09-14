"""CP-8 — Ch.18 W.1–W.4/W.8 dual optimizer: disjoint scopes, exhaustive-grid
default with the owner-only random escape, both objectives, the 03:00–05:00 UTC
window with the live-workload halt, per-cell checkpointing and the
suggestion-only output RED LINE (MATRIX Part III CP-8 rows C8-OP|1..18)."""

from __future__ import annotations

import asyncio
import json

import pytest

from apex.research import optimizer as opt
from apex.research.checkpoints import ResearchCheckpointStore
from apex.research.governance import ResearchRedLineError


def _run(coro):
    return asyncio.run(coro)


def _grid():
    return opt.ParameterGrid([
        opt.ParameterRange("atr_mult", 0.5, 2.5, 0.5),
        opt.ParameterRange("lookback", 10, 30, 10)])


# --------------------------------------------------------------------------
# W.1 — scopes
# --------------------------------------------------------------------------

class TestScopes:
    def test_scopes_are_disjoint(self):
        proof = opt.assert_scopes_disjoint()
        assert proof["disjoint"] is True
        assert proof["overlap"] == []

    def test_signal_scope_is_thresholds_only(self):
        assert set(opt.SIGNAL_SCOPE) == {"engine_thresholds",
                                         "setup_scoring_weights",
                                         "gate_thresholds"}

    def test_risk_scope_carries_the_nine_execution_parameters(self):
        assert set(opt.RISK_SCOPE) == {
            "position_size", "effective_leverage", "stop_distance",
            "target_distance", "trailing_distance", "breakeven_distance",
            "time_stop_distance", "cooldown", "staged_tp_ratios"}

    def test_summary_reports_the_contract(self):
        summary = opt.optimizer_summary()
        assert summary["full_grid_threshold"] == 500
        assert summary["default_window"] == ["03:00", "05:00"]
        assert summary["continuous_flag"] == "continuous on"
        assert "params_suggestions" in summary["suggestions_dir"]


# --------------------------------------------------------------------------
# W.3 — grids
# --------------------------------------------------------------------------

class TestGrids:
    def test_full_cartesian_product(self):
        assert _grid().size == 5 * 3
        assert len(_grid().enumerate()) == 15

    def test_step_count_is_inclusive(self):
        assert opt.ParameterRange("x", 0.0, 1.0, 0.25).states() == \
            [0.0, 0.25, 0.5, 0.75, 1.0]

    def test_single_state_range(self):
        assert opt.ParameterRange("x", 1.0, 1.0, 1.0).states() == [1.0]

    def test_inverted_range_refused(self):
        with pytest.raises(opt.OptimizerError) as err:
            opt.ParameterRange("x", 2.0, 1.0, 0.1)
        assert err.value.reason == "RANGE_INVERTED"

    def test_zero_step_refused(self):
        with pytest.raises(opt.OptimizerError) as err:
            opt.ParameterRange("x", 0.0, 1.0, 0.0)
        assert err.value.reason == "STEP_QX"

    def test_empty_grid_refused(self):
        with pytest.raises(opt.OptimizerError) as err:
            opt.ParameterGrid([])
        assert err.value.reason == "EMPTY_GRID"

    def test_duplicate_range_name_refused(self):
        with pytest.raises(opt.OptimizerError) as err:
            opt.ParameterGrid([opt.ParameterRange("x", 0.0, 1.0, 1.0),
                               opt.ParameterRange("x", 2.0, 3.0, 1.0)])
        assert err.value.reason == "DUPLICATE_RANGE"

    def test_default_mode_is_the_full_grid(self):
        combos = _grid().generate()
        assert len(combos) == 15
        assert _grid().to_dict()["mode"] == "FULL_GRID"

    def test_random_search_requires_the_owner_order(self):
        with pytest.raises(opt.OptimizerError) as err:
            _grid().random_search(budget=10, seed=1, owner_authorized=False)
        assert err.value.reason == "OWNER_AUTHORIZATION_REQUIRED_D3"

    def test_random_search_stays_inside_the_states(self):
        pool = set(opt.ParameterRange("atr_mult", 0.5, 2.5, 0.5).states())
        combos = _grid().random_search(budget=50, seed=11,
                                       owner_authorized=True)
        assert len(combos) == 50
        assert all(c["atr_mult"] in pool for c in combos)

    def test_random_search_is_seed_deterministic(self):
        a = _grid().random_search(budget=20, seed=5, owner_authorized=True)
        b = _grid().random_search(budget=20, seed=5, owner_authorized=True)
        assert a == b

    def test_small_domain_never_randomizes_even_with_authorization(self):
        """W.3: below ~500 states the full grid is mandatory."""
        combos = _grid().generate(owner_authorized_random=True, budget=3)
        assert len(combos) == 15

    def test_large_domain_randomizes_only_when_authorized(self):
        big = opt.ParameterGrid([opt.ParameterRange("x", 0.0, 999.0, 1.0),
                                 opt.ParameterRange("y", 0.0, 10.0, 1.0)])
        assert big.size > opt.FULL_GRID_THRESHOLD
        assert len(big.generate(owner_authorized_random=True, budget=25)) == 25
        assert len(big.generate(owner_authorized_random=False)) == big.size


# --------------------------------------------------------------------------
# W.2 — objectives
# --------------------------------------------------------------------------

def _regimes(**overrides):
    base = {name: 0.1 for name in ("LOW", "NORMAL", "HIGH", "EXTREME", "CRISIS")}
    base.update(overrides)
    return base


class TestObjectives:
    def _signal(self, **overrides):
        base = dict(deflated_sharpe=1.2, trades=150, net_return=0.30,
                    btc_buy_and_hold=0.25, calibration_error=0.01,
                    staleness_threshold=0.05)
        base.update(overrides)
        return opt.signal_objective(**base)

    def test_feasible_signal_scores_the_deflated_sharpe(self):
        out = self._signal()
        assert out["feasible"] is True
        assert out["value"] == pytest.approx(1.2)
        assert out["objective"] == "cost_adjusted_deflated_sharpe"

    def test_too_few_trades_is_infeasible(self):
        out = self._signal(trades=99)
        assert out["feasible"] is False
        assert out["value"] == float("-inf")
        assert out["constraints"]["min_trades_per_window"] is False

    def test_not_beating_buy_and_hold_is_infeasible(self):
        out = self._signal(net_return=0.20)
        assert out["constraints"]["beats_buy_and_hold"] is False

    def test_stale_calibration_is_infeasible(self):
        out = self._signal(calibration_error=0.06)
        assert out["constraints"]["calibration_fresh"] is False

    def test_risk_objective_needs_all_five_regimes(self):
        out = opt.risk_objective(expected_net_r=0.4, max_drawdown=0.10,
                                 drawdown_limit=0.15, leverage_adherence=1.0,
                                 per_regime_stability=_regimes())
        assert out["feasible"] is True
        assert out["value"] == pytest.approx(0.4)

    def test_missing_regime_is_infeasible_and_named(self):
        regimes = _regimes()
        regimes.pop("CRISIS")
        out = opt.risk_objective(expected_net_r=0.4, max_drawdown=0.10,
                                 drawdown_limit=0.15, leverage_adherence=1.0,
                                 per_regime_stability=regimes)
        assert out["feasible"] is False
        assert out["missing_regimes"] == ["CRISIS"]

    def test_drawdown_breach_is_infeasible(self):
        out = opt.risk_objective(expected_net_r=0.4, max_drawdown=0.20,
                                 drawdown_limit=0.15, leverage_adherence=1.0,
                                 per_regime_stability=_regimes())
        assert out["constraints"]["drawdown_within_limit"] is False

    def test_partial_leverage_adherence_is_infeasible(self):
        out = opt.risk_objective(expected_net_r=0.4, max_drawdown=0.10,
                                 drawdown_limit=0.15, leverage_adherence=0.99,
                                 per_regime_stability=_regimes())
        assert out["constraints"]["leverage_adherence_full"] is False


# --------------------------------------------------------------------------
# W.4 — schedule
# --------------------------------------------------------------------------

class TestSchedule:
    def test_window_bounds(self):
        schedule = opt.OptimizerSchedule("03:00", "05:00")
        assert schedule.in_window(utc_hhmm="03:00") is True
        assert schedule.in_window(utc_hhmm="04:59") is True
        assert schedule.in_window(utc_hhmm="05:00") is False
        assert schedule.in_window(utc_hhmm="02:59") is False

    def test_window_wrapping_midnight(self):
        schedule = opt.OptimizerSchedule("23:00", "01:00")
        assert schedule.in_window(utc_hhmm="23:30") is True
        assert schedule.in_window(utc_hhmm="00:30") is True
        assert schedule.in_window(utc_hhmm="12:00") is False

    def test_default_window_comes_from_the_frozen_yaml(self):
        assert opt.nightly_window() == ("03:00", "05:00")

    def test_live_workload_halts_even_inside_the_window(self):
        decision = opt.OptimizerSchedule("03:00", "05:00").may_run(
            utc_hhmm="03:30", live_workload=True)
        assert decision == {"run": False, "reason": "LIVE_WORKLOAD_HALT",
                            "window": ["03:00", "05:00"], "continuous": False}

    def test_outside_window_does_not_run(self):
        decision = opt.OptimizerSchedule("03:00", "05:00").may_run(
            utc_hhmm="13:30", live_workload=False)
        assert decision["reason"] == "OUTSIDE_WINDOW"

    def test_continuous_mode_needs_the_owner_command(self):
        schedule = opt.OptimizerSchedule("03:00", "05:00")
        with pytest.raises(opt.OptimizerError) as err:
            schedule.set_continuous(True, owner_command="go")
        assert err.value.reason == "CONTINUOUS_MODE_REQUIRES_OWNER"
        assert schedule.set_continuous(True, owner_command="continuous on")[
            "continuous"] is True
        assert schedule.in_window(utc_hhmm="13:30") is True

    def test_bad_window_refused(self):
        with pytest.raises(opt.OptimizerError) as err:
            opt.OptimizerSchedule("25:00", "05:00")
        assert err.value.reason == "WINDOW_QX"


# --------------------------------------------------------------------------
# The run loop
# --------------------------------------------------------------------------

class TestDualOptimizerRun:
    def _evaluate(self, kind, params, cell_id):
        value = float(params["atr_mult"]) + (0.001 if kind == "RISK" else 0.0)
        return {"feasible": params["atr_mult"] >= 1.0, "value": value}

    def test_run_completes_every_cell_and_records_the_best(self):
        optimizer = opt.DualOptimizer()
        result = _run(optimizer.run_run(
            run_id="run-1", cells=["BTCUSDT-15m", "ETHUSDT-15m"],
            grids={"BTCUSDT-15m": _grid(), "ETHUSDT-15m": _grid()},
            evaluate=self._evaluate, utc_hhmm="03:30"))
        assert result["status"] == "COMPLETE"
        assert result["completed_cells"] == ["BTCUSDT-15m", "ETHUSDT-15m"]
        assert all(r["combinations_evaluated"] == 15 for r in result["results"])
        assert result["results"][0]["best_params"]["atr_mult"] == 2.5

    def test_cell_without_a_grid_is_left_pending(self):
        result = _run(opt.DualOptimizer().run_run(
            run_id="run-1", cells=["A", "B"], grids={"A": _grid()},
            evaluate=self._evaluate, utc_hhmm="03:30"))
        assert result["completed_cells"] == ["A"]
        assert result["pending_cells"] == ["B"]

    def test_sru_hash_is_the_canonical_run_identity(self):
        optimizer = opt.DualOptimizer()
        _run(optimizer.run_run(run_id="run-1", cells=["A"],
                               grids={"A": _grid()}, evaluate=self._evaluate,
                               utc_hhmm="03:30"))
        second = opt.DualOptimizer()
        _run(second.run_run(run_id="run-1", cells=["A"], grids={"A": _grid()},
                            evaluate=self._evaluate, utc_hhmm="03:30"))
        assert optimizer.results[0].sru_hash == second.results[0].sru_hash

    def test_live_workload_records_halt_and_runs_nothing(self):
        calls = []

        def evaluate(kind, params, cell_id):
            calls.append(cell_id)
            return {"feasible": True, "value": 1.0}

        result = _run(opt.DualOptimizer().run_run(
            run_id="run-1", cells=["A"], grids={"A": _grid()},
            evaluate=evaluate, utc_hhmm="03:30", live_workload=True))
        assert result["status"] == "LIVE_WORKLOAD_HALT"
        assert calls == []
        assert result["pending_cells"] == ["A"]

    def test_outside_the_window_the_run_pauses(self):
        result = _run(opt.DualOptimizer().run_run(
            run_id="run-1", cells=["A"], grids={"A": _grid()},
            evaluate=self._evaluate, utc_hhmm="15:00"))
        assert result["status"] == "OUTSIDE_WINDOW"

    def test_bad_optimizer_refused(self):
        with pytest.raises(opt.OptimizerError) as err:
            _run(opt.DualOptimizer().run_run(
                run_id="r", cells=["A"], grids={"A": _grid()},
                evaluate=self._evaluate, optimizer="BOTH"))
        assert err.value.reason == "OPTIMIZER_QX"


class TestCheckpointedRun:
    def _evaluate(self, kind, params, cell_id):
        if cell_id == "B":
            raise RuntimeError("simulated process kill")
        return {"feasible": True, "value": float(params["atr_mult"])}

    def test_resume_never_rewinds_w8_1(self, tmp_path):
        path = str(tmp_path / "research.sqlite3")
        store = ResearchCheckpointStore(path=path)

        async def _phase_one():
            async with store as opened:
                optimizer = opt.DualOptimizer(checkpoint_store=opened)
                try:
                    await optimizer.run_run(
                        run_id="run-1", cells=["A", "B"], grids={"A": _grid(),
                                                                 "B": _grid()},
                        evaluate=self._evaluate, utc_hhmm="03:30")
                except RuntimeError:
                    pass
                return await opened.optimizer_rows("run-1")

        rows = _run(_phase_one())
        assert [r["cell_id"] for r in rows] == ["A"]
        assert rows[0]["status"] == "COMPLETE"
        assert rows[0]["combination_index"] == 15

        # phase two: a fresh process resumes; A is skipped, B is evaluated
        evaluated_cells = []

        def resumed_evaluate(kind, params, cell_id):
            evaluated_cells.append(cell_id)
            return {"feasible": True, "value": 1.0}

        async def _phase_two():
            async with ResearchCheckpointStore(path=path) as opened:
                rerun = opt.DualOptimizer(checkpoint_store=opened)
                result = await rerun.run_run(
                    run_id="run-1", cells=["A", "B"],
                    grids={"A": _grid(), "B": _grid()},
                    evaluate=resumed_evaluate, utc_hhmm="03:30")
                return result, rerun

        result, rerun = _run(_phase_two())
        assert result["completed_cells"] == ["A", "B"]
        assert evaluated_cells == ["B"] * 15
        assert len(rerun.results) == 1          # A was not re-evaluated

    def test_halted_cells_are_recorded_as_paused(self, tmp_path):
        async def _phase():
            async with ResearchCheckpointStore(
                    path=str(tmp_path / "r.sqlite3")) as opened:
                optimizer = opt.DualOptimizer(checkpoint_store=opened)
                await optimizer.run_run(run_id="run-2", cells=["A"],
                                        grids={"A": _grid()},
                                        evaluate=self._evaluate,
                                        utc_hhmm="13:00")
                return await opened.load_optimizer("run-2", "A", "SIGNAL")
        row = _run(_phase())
        assert row["status"] == "PAUSED"


class TestSuggestionOutput:
    def test_suggestion_lands_under_the_research_dir(self, tmp_path):
        optimizer = opt.DualOptimizer(suggestions_dir=tmp_path / "suggestions")
        out = optimizer.write_suggestion(
            run_id="run-1", cell_id="BTCUSDT-15m", optimizer="SIGNAL",
            params={"atr_mult": 1.5}, reason="nightly grid winner")
        path = tmp_path / "suggestions" / "run-1" / "BTCUSDT-15m-signal.json"
        assert out["written"] == str(path)
        assert path.exists()
        payload = json.loads(path.read_text())
        assert payload["params"] == {"atr_mult": 1.5}
        assert "SUGGESTION ONLY" in payload["note"]

    def test_writing_into_live_params_is_refused(self):
        optimizer = opt.DualOptimizer()
        optimizer.suggestions_dir = opt.LIVE_PARAMS_DIR
        with pytest.raises(ResearchRedLineError) as err:
            optimizer.write_suggestion(
                run_id="run-1", cell_id="c", optimizer="SIGNAL", params={},
                reason="boom")
        assert err.value.reason == "LIVE_PARAMS_WRITE_FORBIDDEN"

    def test_suggestion_hash_is_deterministic(self, tmp_path):
        out1 = opt.DualOptimizer(suggestions_dir=tmp_path / "a").write_suggestion(
            run_id="r", cell_id="c", optimizer="RISK", params={"stop_distance": 2.0},
            reason="x")
        out2 = opt.DualOptimizer(suggestions_dir=tmp_path / "b").write_suggestion(
            run_id="r", cell_id="c", optimizer="RISK", params={"stop_distance": 2.0},
            reason="x")
        assert out1["suggestion_hash"] == out2["suggestion_hash"]
