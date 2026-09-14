"""CP-8 — Ch.18 §18.1/§18.4 backtest engine: PIT safety, exit precedence,
metrics, walk-forward, Monte-Carlo, the seven stress scenarios and the
determinism double-run (MATRIX Part III CP-8 rows C8-BT|1..14)."""

from __future__ import annotations

import math

import pytest

from apex.research import backtest as bt


def _bars(n=60, start=100.0, step=0.0, amp=1.0):
    bars = []
    price = start
    for i in range(n):
        bars.append({"open": price, "high": price + amp,
                     "low": price - amp, "close": price + step,
                     "volume": 1000.0 + i})
        price += step
    return bars


class TestMetrics:
    def test_sharpe_matches_hand_computation(self):
        r = [0.01, 0.02, 0.03, 0.04]
        mean = sum(r) / 4
        sd = math.sqrt(sum((x - mean) ** 2 for x in r) / 3)
        assert bt.sharpe(r) == pytest.approx(mean / sd, rel=1e-12)

    def test_sharpe_zero_variance_fails_closed(self):
        with pytest.raises(bt.BacktestError):
            bt.sharpe([0.01, 0.01, 0.01])

    def test_profit_factor(self):
        assert bt.profit_factor([2.0, -1.0, 3.0, -1.0]) == pytest.approx(2.5)

    def test_profit_factor_infinite_without_losses(self):
        assert bt.profit_factor([1.0, 2.0]) == float("inf")

    def test_profit_factor_no_pnl_fails_closed(self):
        with pytest.raises(bt.BacktestError):
            bt.profit_factor([0.0, 0.0])

    def test_max_drawdown_compounds(self):
        assert bt.max_drawdown([0.10, -0.20]) == pytest.approx(0.20)

    def test_expectancy_is_mean_r(self):
        assert bt.expectancy([1.0, -1.0, 2.0]) == pytest.approx(2.0 / 3.0)

    def test_metrics_from_trades_counts_cost_adjusted_wins(self):
        trades = [_trade(1.5), _trade(-1.0), _trade(0.2), _trade(-0.5)]
        metrics = bt.metrics_from_trades(trades, periods_per_year=252)
        assert metrics["trades"] == 4
        assert metrics["wins"] == 2
        assert metrics["winrate"] == pytest.approx(0.5)
        assert metrics["total_r"] == pytest.approx(0.2)
        assert metrics["sharpe"] is not None

    def test_empty_sample_fails_closed(self):
        with pytest.raises(bt.BacktestError) as err:
            bt.metrics_from_trades([])
        assert "NO_TRADES_QX" in str(err.value)


def _trade(r: float):
    return bt.Trade(symbol="BTCUSDT", timeframe="15m", family_id="SF_X",
                    direction=1, entry_index=1, exit_index=2, entry_price=100.0,
                    exit_price=100.0 + r, stop_price=99.0, target_price=103.0,
                    quantity=1.0, r_multiple=r, costs=0.0004,
                    exit_reason="TARGET", atr=1.0)


class TestDeflatedSharpe:
    def test_dsr_discounts_for_trials(self):
        few = bt.deflated_sharpe_ratio(observed_sharpe=1.5, trials=1,
                                       variance_of_trials=0.02, skew=0.0,
                                       kurtosis=3.0, n_observations=200)
        many = bt.deflated_sharpe_ratio(observed_sharpe=1.5, trials=500,
                                        variance_of_trials=0.02, skew=0.0,
                                        kurtosis=3.0, n_observations=200)
        assert many["expected_max_sharpe"] > few["expected_max_sharpe"]
        assert many["deflated_sharpe"] < few["deflated_sharpe"]

    def test_zero_trial_variance_fails_closed(self):
        with pytest.raises(bt.BacktestError):
            bt.deflated_sharpe_ratio(observed_sharpe=1.0, trials=10,
                                     variance_of_trials=0.0, skew=0.0,
                                     kurtosis=3.0, n_observations=100)

    def test_norm_ppf_round_trip(self):
        for p in (0.01, 0.25, 0.5, 0.75, 0.99):
            assert bt._norm_cdf(bt._norm_ppf(p)) == pytest.approx(p, abs=1e-6)


class TestWalkForward:
    def test_split_is_70_30(self):
        split = bt.walk_forward(1000)
        assert split["train"] == [0, 700]
        assert split["test"] == [700, 1000]
        assert split["train_fraction"] == 0.70

    def test_oos_window_carved_out(self):
        split = bt.walk_forward(1000, oos_fraction=0.10)
        assert split["train"] == [0, 700]
        assert split["test"] == [700, 900]
        assert split["oos"] == [900, 1000]

    def test_invalid_fraction_refused(self):
        with pytest.raises(bt.BacktestError):
            bt.walk_forward(100, train_fraction=1.5)

    def test_too_short_sample_refused(self):
        with pytest.raises(bt.BacktestError):
            bt.walk_forward(5)

    def test_promotion_requires_all_three_criteria(self):
        good = {"sharpe": 1.5, "profit_factor": 1.4, "max_drawdown": 0.10}
        assert bt.evaluate_wfo(train={}, test=good)["decision"] == "PROMOTED"
        for bad in ({"sharpe": 0.9, "profit_factor": 1.4, "max_drawdown": 0.10},
                    {"sharpe": 1.5, "profit_factor": 1.1, "max_drawdown": 0.10},
                    {"sharpe": 1.5, "profit_factor": 1.4, "max_drawdown": 0.16}):
            assert bt.evaluate_wfo(train={}, test=bad)["decision"] == "NOT_PROMOTED"

    def test_missing_sharpe_fails_closed(self):
        verdict = bt.evaluate_wfo(train={}, test={"profit_factor": 2.0,
                                                  "max_drawdown": 0.05})
        assert verdict["decision"] == "NOT_PROMOTED"
        assert verdict["checks"]["oos_sharpe_gt_1_0"] is False


class TestMonteCarlo:
    def test_deterministic_for_a_seed(self):
        trades = [_trade(x) for x in (1.0, -1.0, 0.5, 2.0, -0.5)]
        a = bt.monte_carlo(trades, paths=200, seed=42)
        b = bt.monte_carlo(trades, paths=200, seed=42)
        assert bt.canonical_json(a) == bt.canonical_json(b)

    def test_seed_changes_the_result(self):
        trades = [_trade(x) for x in (1.0, -1.0, 0.5, 2.0, -0.5)]
        a = bt.monte_carlo(trades, paths=200, seed=1)
        b = bt.monte_carlo(trades, paths=200, seed=2)
        assert a["mean"] != b["mean"]

    def test_percentile_ordering(self):
        trades = [_trade(x) for x in (3.0, -1.0, 0.5, 2.0, -0.5, 1.0)]
        mc = bt.monte_carlo(trades, paths=500, seed=7)
        assert mc["min"] <= mc["p5"] <= mc["median"] <= mc["p95"] <= mc["max"]

    def test_cvar_is_the_left_tail(self):
        out = bt.cvar_bootstrap([0.01, -0.02, 0.03, -0.01, 0.02], paths=300,
                                seed=5)
        assert out["cvar"] <= 0.0
        assert out["paths"] == 300


class TestStressBattery:
    def test_seven_scenarios_execute(self):
        battery = bt.stress_battery([0.01, -0.02, 0.015, -0.005, 0.02])
        assert battery["count"] == 7
        assert set(battery["scenarios"]) == set(bt.STRESS_SCENARIO_NAMES)
        assert battery["crisis_factor"] == 0.5

    def test_crash_scenario_is_a_real_transform(self):
        out = bt.apply_stress("Crash", [0.0, 0.01])
        assert out["returns"][0] <= -0.5
        assert out["metrics"]["max_drawdown"] > 0.0

    def test_volume_scenario_scales_by_a_tenth(self):
        out = bt.apply_stress("Volume", [0.02, -0.01])
        assert out["returns"] == pytest.approx([0.002, -0.001])

    def test_unknown_scenario_refused(self):
        with pytest.raises(bt.BacktestError):
            bt.apply_stress("Meltdown", [0.01])


class TestBacktestEngine:
    def test_pit_window_never_exposes_the_future(self):
        seen = []

        def signal_fn(window, index):
            assert len(window) == index + 1
            assert window[-1] is bars[index]
            seen.append(len(window))
            return None

        bars = _bars(30)
        engine = bt.BacktestEngine(symbol="BTCUSDT", timeframe="15m")
        engine.run(bars, signal_fn)
        # start_index defaults to 1: the first signal may use bars 0..1
        assert seen == list(range(2, 30))

    def test_entry_fills_at_next_bar_open(self):
        bars = _bars(10)
        bars[4]["open"] = 111.0       # the signal bar's next bar
        engine = bt.BacktestEngine(symbol="BTCUSDT", timeframe="15m")

        def signal_fn(window, index):
            if index == 3:
                return bt.SignalProposal(direction=1, stop_price=95.0,
                                         target_price=200.0, stop_distance=5.0)
            return None

        result = engine.run(bars, signal_fn)
        assert result["trades"][0].entry_index == 4
        assert result["trades"][0].entry_price == pytest.approx(111.0)

    def test_exit_precedence_stop_wins_over_target(self):
        bars = _bars(6)
        bars[3]["low"] = 90.0
        bars[3]["high"] = 300.0
        engine = bt.BacktestEngine(symbol="BTCUSDT", timeframe="15m")

        def signal_fn(window, index):
            if index == 1:
                return bt.SignalProposal(direction=1, stop_price=95.0,
                                         target_price=200.0, stop_distance=5.0)
            return None

        result = engine.run(bars, signal_fn)
        assert result["trades"][0].exit_reason == "STOP"
        assert result["trades"][0].exit_price == pytest.approx(95.0)

    def test_time_stop_closes_at_the_horizon(self):
        bars = _bars(40, step=0.01, amp=0.05)
        engine = bt.BacktestEngine(symbol="BTCUSDT", timeframe="15m",
                                   max_hold=3)

        def signal_fn(window, index):
            if index == 1:
                return bt.SignalProposal(direction=1, stop_price=1.0,
                                         target_price=10000.0, stop_distance=99.0)
            return None

        result = engine.run(bars, signal_fn)
        trade = result["trades"][0]
        assert trade.exit_reason == "TIME_STOP"
        assert trade.exit_index - trade.entry_index == 3

    def test_costs_reduce_the_r_multiple(self):
        bars = _bars(20, step=0.5, amp=1.0)
        engine = bt.BacktestEngine(symbol="BTCUSDT", timeframe="15m", fee=0.0,
                                   alpha_spread=0.0)

        def signal_fn(window, index):
            if index == 1:
                return bt.SignalProposal(direction=1, stop_price=bars[2]["open"] - 1.0,
                                         target_price=bars[2]["open"] + 1.0,
                                         stop_distance=1.0)
            return None

        free = engine.run(bars, signal_fn)["trades"][0]
        costly_engine = bt.BacktestEngine(symbol="BTCUSDT", timeframe="15m",
                                          fee=0.0002, alpha_spread=0.25)
        costly = costly_engine.run(bars, signal_fn)["trades"][0]
        assert costly.r_multiple < free.r_multiple
        assert costly.costs > 0.0

    def test_slippage_fn_is_injected(self):
        bars = _bars(20, step=0.5)
        engine = bt.BacktestEngine(symbol="BTCUSDT", timeframe="15m",
                                   slippage_fn=lambda index: 0.001)

        def signal_fn(window, index):
            if index == 1:
                return bt.SignalProposal(direction=1, stop_price=bars[2]["open"] - 1.0,
                                         target_price=bars[2]["open"] + 1.0,
                                         stop_distance=1.0)
            return None

        trade = engine.run(bars, signal_fn)["trades"][0]
        assert trade.costs == pytest.approx(2 * bt.FEE_FRACTION + 0.001)

    def test_invalid_direction_refused(self):
        with pytest.raises(bt.BacktestError):
            bt.SignalProposal(direction=0, stop_price=1.0, target_price=2.0,
                              stop_distance=1.0)

    def test_short_direction_is_supported(self):
        bars = _bars(20, step=-0.5, amp=0.2)
        engine = bt.BacktestEngine(symbol="BTCUSDT", timeframe="15m", fee=0.0,
                                   alpha_spread=0.0)

        def signal_fn(window, index):
            if index == 1:
                return bt.SignalProposal(direction=-1, stop_price=1e9,
                                         target_price=bars[2]["open"] - 2.0,
                                         stop_distance=2.0)
            return None

        trade = engine.run(bars, signal_fn)["trades"][0]
        assert trade.r_multiple > 0.0

    def test_run_with_metrics_attaches_the_metric_block(self):
        bars = _bars(30, step=0.5)
        engine = bt.BacktestEngine(symbol="BTCUSDT", timeframe="15m")

        def signal_fn(window, index):
            if index % 7 == 1:
                return bt.SignalProposal(direction=1, stop_price=bars[index + 1]["open"] - 1.0,
                                         target_price=bars[index + 1]["open"] + 2.0,
                                         stop_distance=1.0)
            return None

        result = engine.run_with_metrics(bars, signal_fn)
        assert result["metrics"]["trades"] >= 1
        assert "expectancy_r" in result["metrics"]


class TestBenchmark:
    def test_buy_and_hold_net_of_fees(self):
        bars = _bars(10, start=100.0, step=1.0)
        out = bt.buy_and_hold(bars)
        gross = (float(bars[-1]["close"]) - float(bars[0]["open"])) / 100.0
        assert out["gross"] == pytest.approx(gross)
        assert out["buy_and_hold"] == pytest.approx(gross - 2 * bt.FEE_FRACTION)

    def test_outperformance_requires_significance(self):
        strong = bt.benchmark_outperformance(
            strategy_returns=[0.02, 0.021, 0.019, 0.022, 0.02],
            benchmark_returns=[0.0] * 5)
        assert strong["outperforms"] is True
        weak = bt.benchmark_outperformance(
            strategy_returns=[0.02, -0.02, 0.02, -0.02, 0.02],
            benchmark_returns=[0.0] * 5)
        assert weak["outperforms"] is False


class TestDeterminism:
    def test_double_run_is_byte_identical(self):
        payload = {"b": [1, 2, 3], "a": {"z": "1.0"}}
        out = bt.deterministic_double_run(lambda: payload)
        assert out["identical"] is True
        assert out["first_hash"] == out["second_hash"]

    def test_double_run_flags_nondeterminism(self):
        state = {"n": 0}

        def flaky():
            state["n"] += 1
            return {"n": state["n"]}

        out = bt.deterministic_double_run(flaky)
        assert out["identical"] is False
