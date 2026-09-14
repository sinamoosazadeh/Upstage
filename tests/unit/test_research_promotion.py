"""CP-8 — Ch.18 W.5 + Z.1–Z.9 promotion gate: family pool, Wilson gate, floor,
Bayesian shrinkage, SPRT halt/rollback, PBO, the re-derived Z.8 worked example
and the thesis registry (MATRIX Part III CP-8 rows C8-PR|1..16)."""

from __future__ import annotations

import math

import pytest

from apex.research import backtest as bt
from apex.research import promotion as pr


def _trade(r: float, *, symbol="BTCUSDT", family="SF_FVG_SWEEP_REV"):
    return bt.Trade(symbol=symbol, timeframe="15m", family_id=family,
                    direction=1, entry_index=1, exit_index=2, entry_price=100.0,
                    exit_price=100.0 + r, stop_price=99.0, target_price=103.0,
                    quantity=1.0, r_multiple=r, costs=0.0004,
                    exit_reason="TARGET", atr=1.0)


def _pool(n_wins: int, n_losses: int) -> pr.FamilyPool:
    pool = pr.FamilyPool(family_id="SF_FVG_SWEEP_REV")
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
               "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT"]
    for i in range(n_wins):
        pool.add(_trade(1.5, symbol=symbols[i % 10]))
    for i in range(n_losses):
        pool.add(_trade(-1.0, symbol=symbols[i % 10]))
    return pool


# --------------------------------------------------------------------------
# A01 — thesis registry
# --------------------------------------------------------------------------

class TestThesisRegistry:
    def test_register_and_read(self):
        registry = pr.ThesisRegistry()
        registry.register(pr.ThesisRecord(
            thesis_id="thesis-abc", hypothesis="sweep reclaim reverses",
            expected_return="+0.4R", holding_period="<= 12 bars",
            invalidation_condition="close beyond the sweep extreme"))
        assert len(registry) == 1
        assert registry.get("thesis-abc").to_dict()["holding_period"] == "<= 12 bars"

    def test_id_prefix_enforced(self):
        with pytest.raises(pr.PromotionError):
            pr.ThesisRecord(thesis_id="abc", hypothesis="h", expected_return="r",
                            holding_period="p", invalidation_condition="c")

    def test_empty_field_enforced(self):
        with pytest.raises(pr.PromotionError):
            pr.ThesisRecord(thesis_id="thesis-a", hypothesis="", expected_return="r",
                            holding_period="p", invalidation_condition="c")

    def test_duplicate_refused(self):
        registry = pr.ThesisRegistry()
        record = pr.ThesisRecord(thesis_id="thesis-a", hypothesis="h",
                                 expected_return="r", holding_period="p",
                                 invalidation_condition="c")
        registry.register(record)
        with pytest.raises(pr.PromotionError):
            registry.register(record)


# --------------------------------------------------------------------------
# Z.2/Z.3/Z.4 — family pool + Wilson gate + floor
# --------------------------------------------------------------------------

class TestFamilyPool:
    def test_pool_counts(self):
        pool = _pool(27, 15)
        assert pool.n == 42
        assert pool.wins == 27
        assert pool.success_rate == pytest.approx(27 / 42)

    def test_atr_normalization_is_structural(self):
        pool = pr.FamilyPool(family_id="SF_FVG_SWEEP_REV")
        bad = bt.Trade(symbol="BTCUSDT", timeframe="15m",
                       family_id="SF_FVG_SWEEP_REV", direction=1, entry_index=1,
                       exit_index=2, entry_price=100.0, exit_price=101.0,
                       stop_price=100.0, target_price=102.0, quantity=1.0,
                       r_multiple=1.0, costs=0.0, exit_reason="TARGET", atr=0.0)
        with pytest.raises(pr.PromotionError) as err:
            pool.add(bad)
        assert "ATR_NORMALIZATION_QX" in str(err.value)

    def test_foreign_family_refused(self):
        pool = pr.FamilyPool(family_id="SF_A")
        with pytest.raises(pr.PromotionError):
            pool.add(_trade(1.0, family="SF_B"))

    def test_per_symbol_breakdown(self):
        pool = _pool(12, 8)
        per_symbol = pool.per_symbol()
        assert sum(row["n"] for row in per_symbol.values()) == 20

    def test_wilson_gate_matches_z8_scenario_a(self):
        gate = pr.wilson_gate(n=42, k=27, p_breakeven=0.48)
        assert gate["wilson_lower"] == pytest.approx(0.49, abs=0.01)
        assert gate["above_breakeven"] is True

    def test_floor_blocks_even_a_high_rate(self):
        pool = _pool(11, 7)              # 18 trades, 61 %
        gate = pr.family_pool_gate(pool)
        assert gate["floor_ok"] is False
        assert gate["eligible"] is False
        assert gate["reason"] == "BELOW_ABSOLUTE_FLOOR_30"

    def test_pool_at_the_floor_promotes(self):
        pool = _pool(31, 17)             # 48 trades, 64.6 %
        gate = pr.family_pool_gate(pool)
        assert gate["floor_ok"] is True
        assert gate["eligible"] is True
        assert gate["reason"] == "PROMOTION_ALLOWED"

    def test_pool_above_floor_but_below_breakeven_is_blocked(self):
        pool = _pool(16, 16)             # 50 %, Wilson lower well under 48 %
        gate = pr.family_pool_gate(pool)
        assert gate["eligible"] is False
        assert gate["reason"] == "WILSON_LOWER_BELOW_BREAKEVEN"

    def test_breakeven_range_enforced(self):
        with pytest.raises(pr.PromotionError):
            pr.wilson_gate(n=40, k=25, p_breakeven=1.5)


class TestShrinkage:
    def test_lambda_formula(self):
        factor = pr.shrinkage_factor(n_cell=5, family_variance=5.0)
        assert factor["lambda"] == pytest.approx(0.5)

    def test_small_cell_is_pulled_to_the_family_rate(self):
        out = pr.shrink_cell_rate(cell_rate=0.60, cell_n=5, family_rate=0.58,
                                  family_variance=5.0)
        assert out["shrunk_rate"] == pytest.approx(0.59)
        assert out["used_in_isolation"] is False

    def test_large_cell_stays_near_its_own_rate(self):
        out = pr.shrink_cell_rate(cell_rate=0.80, cell_n=1000,
                                  family_rate=0.58, family_variance=1.0)
        assert out["shrunk_rate"] > 0.79

    def test_negative_inputs_refused(self):
        with pytest.raises(pr.PromotionError):
            pr.shrinkage_factor(n_cell=-1, family_variance=1.0)


# --------------------------------------------------------------------------
# Z.6 — SPRT
# --------------------------------------------------------------------------

class TestSPRT:
    def test_rates_must_satisfy_the_hypothesis_order(self):
        with pytest.raises(pr.PromotionError):
            pr.SPRTState(p0=0.50, p_min=0.60)

    def test_good_performance_never_halts(self):
        out = pr.sprt_monitor("SF", p0=0.58, outcomes=[True] * 40)
        assert out["action"] == "ACCEPT_PERFORMANCE"
        assert out["state"]["verdict"] == "REJECT_H1"

    def test_bad_performance_halts_and_rolls_back(self):
        out = pr.sprt_monitor("SF", p0=0.58, outcomes=[False] * 40)
        assert out["action"] == "HALT_AND_ROLLBACK"
        assert out["state"]["verdict"] == "ACCEPT_H1"
        assert len(out["rollback_actions"]) == 4
        assert any("halt" in a for a in out["rollback_actions"])
        assert any("close" in a for a in out["rollback_actions"])
        assert any("rollback" in a for a in out["rollback_actions"])
        assert any("log" in a for a in out["rollback_actions"])

    def test_indecisive_sequence_continues(self):
        out = pr.sprt_monitor("SF", p0=0.58, gap=0.05,
                              outcomes=[True, False] * 3)
        assert out["action"] == "CONTINUE"
        assert out["state"]["verdict"] == "CONTINUE"

    def test_likelihood_ratio_moves_in_the_right_direction(self):
        state = pr.SPRTState(p0=0.58, p_min=0.53)
        pr.sprt_step(state, win=True)
        assert state.llr > 0
        state2 = pr.SPRTState(p0=0.58, p_min=0.53)
        pr.sprt_step(state2, win=False)
        assert state2.llr < 0

    def test_thresholds_are_log_alpha_beta(self):
        state = pr.SPRTState(p0=0.58, p_min=0.53)
        assert state.upper == pytest.approx(math.log((1 - 0.05) / 0.05))
        assert state.lower == pytest.approx(math.log(0.05 / (1 - 0.05)))

    def test_live_monitor_halts_and_records(self):
        monitor = pr.LiveFamilyMonitor(
            "SF", pr.SPRTState(p0=0.58, p_min=0.53))
        last = None
        for i in range(40):
            last = monitor.on_trade(win=False, timestamp=f"2026-09-14T00:{i:02d}Z")
            if monitor.halted:
                break
        assert monitor.halted is True
        assert last["action"] == "HALT_AND_ROLLBACK"
        assert monitor.log[-1]["verdict"] == "ACCEPT_H1"
        assert len(monitor.log) < 40          # detected within a few trades


# --------------------------------------------------------------------------
# Z.9-3 — PBO
# --------------------------------------------------------------------------

class TestPBO:
    def test_persistent_winner_has_low_pbo(self):
        matrix = [[5.0, 1.0, 2.0],
                  [4.5, 1.2, 2.1],
                  [4.8, 0.9, 2.2]]
        out = pr.probability_of_backtest_overfitting(matrix)
        assert out["pbo"] < 0.5
        assert out["flagged_high"] is False

    def test_in_sample_only_winner_has_high_pbo(self):
        """Winner's curse: combination c is best on exactly fold c and ranks
        bottom-half on every other fold ⇒ PBO = 0.667 > 0.5 ⇒ flagged."""
        matrix = [[4.0, 1.0, 2.0, 3.0],
                  [1.0, 4.0, 2.0, 3.0],
                  [1.0, 2.0, 4.0, 3.0],
                  [1.0, 2.0, 3.0, 4.0]]
        out = pr.probability_of_backtest_overfitting(matrix)
        assert out["pbo"] == pytest.approx(2.0 / 3.0)
        assert out["flagged_high"] is True
        assert out["pairs"] == 12

    def test_requires_multiple_combinations(self):
        with pytest.raises(pr.PromotionError):
            pr.probability_of_backtest_overfitting([[1.0], [2.0]])

    def test_ragged_matrix_refused(self):
        with pytest.raises(pr.PromotionError):
            pr.probability_of_backtest_overfitting([[1.0, 2.0], [1.0]])


# --------------------------------------------------------------------------
# Z.9-2 — deflated Sharpe gate
# --------------------------------------------------------------------------

class TestDeflatedSharpeGate:
    def test_passes_above_threshold(self):
        out = pr.deflated_sharpe_gate(observed_sharpe=1.5, trials=50,
                                      variance_of_trials=0.02, skew=0.0,
                                      kurtosis=3.0, n_observations=250,
                                      threshold=0.5)
        assert out["passes"] is True
        assert out["threshold_band"] == [0.5, 1.0]

    def test_fails_below_threshold(self):
        out = pr.deflated_sharpe_gate(observed_sharpe=0.6, trials=5000,
                                      variance_of_trials=0.5, skew=0.0,
                                      kurtosis=3.0, n_observations=250,
                                      threshold=1.0)
        assert out["passes"] is False

    def test_threshold_outside_the_owner_band_refused(self):
        with pytest.raises(pr.PromotionError):
            pr.deflated_sharpe_gate(observed_sharpe=1.0, trials=10,
                                    variance_of_trials=0.02, skew=0.0,
                                    kurtosis=3.0, n_observations=100,
                                    threshold=0.1)


# --------------------------------------------------------------------------
# Z.8 — worked example re-derived
# --------------------------------------------------------------------------

class TestZ8ReDerivation:
    def test_all_bounds_and_decisions_reproduce(self):
        out = pr.z8_scenarios()
        assert out["all_lower_bounds_consistent"] is True
        assert out["all_decisions_consistent"] is True

    def test_scenario_a_numbers(self):
        scenario = pr.z8_scenarios()["scenarios"]["A"]
        assert scenario["recomputed_lower"] == pytest.approx(0.49, abs=0.01)
        assert scenario["recomputed_decision"] == "PROMOTION_ALLOWED"

    def test_scenario_b_accumulates_then_promotes(self):
        scenarios = pr.z8_scenarios()["scenarios"]
        assert scenarios["B_initial"]["recomputed_lower"] == pytest.approx(
            0.39, abs=0.01)
        assert scenarios["B_initial"]["recomputed_decision"] == \
            "NO_PROMOTION_BELOW_FLOOR"
        assert scenarios["B_3months"]["recomputed_decision"] == "STILL_BLOCKED"
        assert scenarios["B_6months"]["recomputed_lower"] == pytest.approx(
            0.50, abs=0.01)
        assert scenarios["B_6months"]["recomputed_decision"] == \
            "PROMOTION_ALLOWED"

    def test_the_two_doc_wordings_are_one_state(self):
        assert pr.canonical_decision("PROMOTION_GRANTED") == \
            pr.canonical_decision("PROMOTION_ALLOWED")


# --------------------------------------------------------------------------
# W.5 — the promotion decision + package drafting
# --------------------------------------------------------------------------

def _candidate(**overrides):
    pool = overrides.pop("pool", _pool(31, 17))
    base = dict(
        family_id="SF_FVG_SWEEP_REV", pool=pool,
        wfo={"decision": "PROMOTED"},
        pbo={"flagged_high": False, "pbo": 0.1},
        deflated_sharpe={"passes": True, "deflated_sharpe": 0.8},
        benchmark={"outperforms": True, "z": 3.0})
    base.update(overrides)
    return pr.PromotionCandidate(**base)


class TestPromotionDecision:
    def test_all_gates_pass(self):
        verdict = pr.evaluate_promotion(_candidate())
        assert verdict["decision"] == "PROMOTE"
        assert verdict["failed"] == []
        assert verdict["paper_trial_required"] is True

    @pytest.mark.parametrize("gate,value", [
        ("wfo", {"decision": "NOT_PROMOTED"}),
        ("pbo", {"flagged_high": True}),
        ("deflated_sharpe", {"passes": False}),
        ("benchmark", {"outperforms": False}),
    ])
    def test_each_gate_can_block(self, gate, value):
        verdict = pr.evaluate_promotion(_candidate(**{gate: value}))
        assert verdict["decision"] == "BLOCK"
        assert gate in verdict["failed"]
        assert verdict["paper_trial_required"] is False

    def test_missing_benchmark_blocks_z9_1(self):
        verdict = pr.evaluate_promotion(_candidate(benchmark=None))
        assert verdict["decision"] == "BLOCK"
        assert "benchmark" in verdict["failed"]

    def test_family_pool_gate_blocks_a_thin_sample(self):
        verdict = pr.evaluate_promotion(_candidate(pool=_pool(11, 7)))
        assert verdict["decision"] == "BLOCK"
        assert "family_pool" in verdict["failed"]


class TestDraftPackage:
    def _proposal(self):
        return {"reason": "promoted", "pit_backtest_180d": 200,
                "forward_observation_30d": 30,
                "out_of_sample_evaluation": "OOS-2026-09",
                "parameter_board_approval": "board-1"}

    def test_blocked_candidate_is_refused(self):
        out = pr.draft_package(candidate=_candidate(wfo={"decision": "NOT_PROMOTED"}),
                               values={"correlation_cap": 0.6}, version="1.0.0",
                               code_revision="b" * 40, feature_version="4.0.0",
                               model_version="4.0.0", seed=1,
                               reason="test", proposals={})
        assert out["decision"] == "REFUSED"
        assert out["reason"] == "PROMOTION_GATE_BLOCKED"

    def test_promoted_candidate_drafts_a_package(self):
        out = pr.draft_package(candidate=_candidate(),
                               values={"correlation_cap": 0.6}, version="1.0.0",
                               code_revision="b" * 40, feature_version="4.0.0",
                               model_version="4.0.0", seed=1, reason="test",
                               proposals={"correlation_cap": self._proposal()})
        assert out["decision"] == "DRAFTED"
        assert out["package"].package_id == "pkg-SF_FVG_SWEEP_REV-1.0.0"
        assert out["validation"]["red_line_clean"] is True

    def test_drafted_package_cannot_touch_a_veto(self):
        out = pr.draft_package(candidate=_candidate(),
                               values={"VETO_STALE_DATA": 1}, version="1.0.0",
                               code_revision="b" * 40, feature_version="4.0.0",
                               model_version="4.0.0", seed=1, reason="test",
                               proposals={})
        assert out["decision"] == "REFUSED"
        assert out["reason"] == "PACKAGE_VALIDATION_FAILED"

    def test_red_line_names_are_the_fourteen_registry_names(self):
        from apex.risk.kernel import veto_definition
        names = [veto_definition(n)["name"] for n in range(1, 15)]
        assert len(names) == 14
        from apex.research.governance import FORBIDDEN_FIELDS
        assert set(names) <= set(FORBIDDEN_FIELDS)
