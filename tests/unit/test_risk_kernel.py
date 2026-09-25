"""CP-6 battery — Risk Kernel (Ch.15 §15.1): the fourteen hard vetoes (T_VETO
on boundary samples), the sizing machine's every boundary, the RSK-ERR-506
ratchet, the FROZEN_BOOTSTRAP literals asserted from the params YAML, and the
ADR-P2-004 ``apex_risk_ladder_state`` persistence.
"""

from __future__ import annotations

import math

import pytest

from apex.config import load_params
from apex.risk.kernel import (
    DEFAULT_CONTRACT_ROLLOVER_DAYS,
    DEFAULT_CVAR_CAP_FRACTION,
    DEFAULT_MARGIN_HEALTH_ACTION,
    DEFAULT_MARGIN_HEALTH_LIQUIDATION,
    DEFAULT_MARGIN_HEALTH_WARN,
    EMERGENCY_LADDER,
    HARD_VETO_NUMBERS,
    LADDER_ROW_COLUMNS,
    LADDER_STATE_DDL,
    LADDER_STATE_MIGRATION,
    RATCHET_ALLOWED_DOWNGRADE,
    RATCHET_BLOCKED,
    RISK_LADDER_MULTIPLIER,
    RISK_LADDER_STATES,
    TRADE_PLAN_FIELDS,
    VETO_COUNT,
    VETO_NAMES,
    VETO_REGISTRY,
    RiskError,
    adjudicate,
    aggregate_loss_state,
    append_ladder_revision,
    apply_ladder_state_migration,
    circuit_breaker_reset,
    effective_leverage,
    evaluate_vetoes,
    frozen_risk_params,
    ladder_multiplier,
    ladder_revision,
    ladder_state_for,
    leverage_cap,
    margin_health_state,
    ratchet_allow,
    reduce_to_correlation_cap,
    size,
    veto_definition,
)

# A clean proposal: no veto fires, sizing is well-defined.
CLEAN = {
    "snapshot_id": "a" * 64, "timeframe": "1h", "capital": 10_000.0,
    "q_raw": 0.9, "qx_state": False, "failed_setup_gate": False,
    "pit_violation": False, "availability_time": 1,
    "portfolio_exposure": 100.0, "proposed_notional": 50.0,
    "capital_hard_cap": 1_000_000.0, "circuit_breaker_engaged": False,
    "emergency_state": "NORMAL", "per_symbol_exposure": 100.0,
    "symbol_cap": 1_000.0, "portfolio_cap": 1_000_000.0,
    "conflict_state": "CONSENSUS", "staleness_seconds": 1.0,
    "freshness_sla_seconds": 30.0, "oi_lag_seconds": 5.0,
    "oi_lag_threshold_seconds": 60.0, "is_risk_increase": False,
    "uncertainty_is_rising": False, "realized_daily_loss_fraction": 0.0,
    "realized_weekly_loss_fraction": 0.0, "consecutive_losses": 0,
    "time_to_expiry_days": 40.0, "margin_health_fraction": 0.9,
    "stop_distance": 20.0, "min_quantity": 0.001, "risk_state": "LowRisk",
}


def ri(**over):
    d = dict(CLEAN)
    d.update(over)
    return d


# ---------------------------------------------------------------------------
# The fourteen vetoes (T_VETO): every one exercised on a boundary sample
# ---------------------------------------------------------------------------

# (veto number, input that sits just INSIDE (no fire), input just OUTSIDE (fire))
BOUNDARY_CASES = [
    (1, {"q_raw": 0.50}, {"q_raw": 0.49}),                       # Q_min(1h)
    (2, {"pit_violation": False}, {"pit_violation": True}),
    (3, {"proposed_notional": 50.0}, {"proposed_notional": 999_901.0}),
    (4, {"circuit_breaker_engaged": False}, {"circuit_breaker_engaged": True}),
    (5, {"per_symbol_exposure": 1000.0}, {"per_symbol_exposure": 1000.1}),
    (6, {"conflict_state": "MATERIAL_CONFLICT"}, {"conflict_state": "HARD_CONFLICT"}),
    (7, {"staleness_seconds": 30.0}, {"staleness_seconds": 30.1}),
    (8, {"oi_lag_seconds": 60.0}, {"oi_lag_seconds": 60.1}),
    (9, {"is_risk_increase": True, "uncertainty_is_rising": False},
     {"is_risk_increase": True, "uncertainty_is_rising": True}),
    (10, {"realized_daily_loss_fraction": 0.03},
     {"realized_daily_loss_fraction": 0.0301}),
    (11, {"realized_weekly_loss_fraction": 0.06},
     {"realized_weekly_loss_fraction": 0.0601}),
    (12, {"consecutive_losses": 4}, {"consecutive_losses": 5}),
    (13, {"time_to_expiry_days": 7.0}, {"time_to_expiry_days": 6.9}),
    (14, {"margin_health_fraction": 0.41}, {"margin_health_fraction": 0.40}),
]


class TestVetoRegistry:
    def test_exactly_fourteen_named_vetoes_in_order(self):
        assert VETO_COUNT == 14
        assert [v[0] for v in VETO_REGISTRY] == list(range(1, 15))
        assert HARD_VETO_NUMBERS == tuple(range(1, 15))
        assert len(set(VETO_NAMES)) == 14
        assert VETO_NAMES[0] == "VETO_INVALID_QUARANTINED_INPUT"
        assert VETO_NAMES[-1] == "VETO_MARGIN_HEALTH"

    def test_error_codes_are_registry_references_only(self):
        # the codes come from the frozen Ch.7 registry (diagnostic only); the
        # alert-policy label of vetoes 10–12 is deliberately NOT an error code
        # (ISSUE-CP6-004) so those rows carry None
        for n, _name, _carrier, code in VETO_REGISTRY:
            d = veto_definition(n)
            assert d["number"] == n
            if code is None:
                assert d["registry"] is None
            else:
                assert code in str(d["registry"])
        assert [veto_definition(n)["error_code"] for n in (10, 11, 12)] == \
            [None, None, None]
        assert veto_definition(4)["error_code"] == "RSK-ERR-506"
        assert veto_definition(2)["error_code"] == "E-PIT-001"
        assert veto_definition(7)["error_code"] == "VETO_FRESHNESS_SLA"
        assert veto_definition(8)["error_code"] == "VETO_OI_LAG"
        assert veto_definition(1)["error_code"] == "QX_INVALID"
        with pytest.raises(RiskError, match="VETO_NUMBER_QX"):
            veto_definition(15)
        with pytest.raises(RiskError, match="VETO_NUMBER_QX"):
            veto_definition(0)

    def test_clean_proposal_fires_nothing(self):
        got = evaluate_vetoes(ri())
        assert got["any"] is False and got["fired"] == []
        assert got["evaluated_in_order"] == list(range(1, 15))
        assert got["veto_count"] == 14

    @pytest.mark.parametrize("n,inside,outside", BOUNDARY_CASES)
    def test_boundary_samples_accept_and_reject(self, n, inside, outside):
        ok = evaluate_vetoes(ri(**inside))
        assert n not in ok["fired_numbers"], (n, ok["fired"])
        bad = evaluate_vetoes(ri(**outside))
        assert n in bad["fired_numbers"]
        assert bad["fired"][0]["number"] == n
        assert bad["fired"][0]["name"] == veto_definition(n)["name"]

    def test_every_veto_is_independently_sufficient_even_at_p_099(self):
        # "even at P = 0.99" — the kernel never sees P; the veto stands alone
        for n, _inside, outside in BOUNDARY_CASES:
            got = adjudicate(ri(EU_p=0.99, **outside))
            assert got["decision"] == "REJECT"
            assert n in got["vetoes_applied"]
            assert got["sized_quantity"] == 0.0
            # and every veto was evaluated before the rejection was decided
            assert got["veto_evaluation_order"] == list(range(1, 15))

    def test_qx_state_fires_veto_one_without_a_q_raw(self):
        assert 1 in evaluate_vetoes(ri(qx_state=True))["fired_numbers"]

    def test_unknown_timeframe_fails_closed(self):
        with pytest.raises(ValueError, match="E-VAL-022"):
            evaluate_vetoes(ri(timeframe="2d"))

    def test_registry_is_complete_by_construction(self):
        # the kernel refuses to report a partial evaluation
        src = open("apex/risk/kernel.py", encoding="utf-8").read()
        assert 'raise RiskError("VETO_REGISTRY_INCOMPLETE"' in src


class TestVetoesBeforeSizing:
    def test_sizing_is_unreachable_when_any_veto_fires(self):
        got = adjudicate(ri(margin_health_fraction=0.1))
        assert got["decision"] == "REJECT" and got["sized_after_all_vetoes"] is False
        assert got["sized_quantity"] == 0.0
        assert got["vetoes_applied"] == [14]

    def test_all_fourteen_are_evaluated_before_the_first_rejection(self):
        # three simultaneous vetoes: the record lists them all, and the order
        # shows sizing could not have run in between
        got = adjudicate(ri(margin_health_fraction=0.1, oi_lag_seconds=99.0,
                           circuit_breaker_engaged=True))
        assert got["vetoes_applied"] == [4, 8, 14]
        assert got["veto_evaluation_order"] == list(range(1, 15))
        assert got["sized_after_all_vetoes"] is False

    def test_the_clean_path_sizes_after_the_full_sweep(self):
        got = adjudicate(ri())
        assert got["decision"] == "ALLOW"
        assert got["sized_after_all_vetoes"] is True
        assert got["vetoes_applied"] == []
        assert set(got) >= set(TRADE_PLAN_FIELDS)

    def test_trade_plan_shape_is_exact(self):
        got = adjudicate(ri())
        for f in TRADE_PLAN_FIELDS:
            assert f in got
        assert got["snapshot_id"] == CLEAN["snapshot_id"]

    def test_missing_mandatory_input_fails_closed(self):
        for key in ("snapshot_id", "timeframe", "capital"):
            bad = {k: v for k, v in ri().items() if k != key}
            with pytest.raises(RiskError, match="RISK_INPUT_QX"):
                adjudicate(bad)


class TestSizingMachine:
    def test_r_allowed_and_quantity_formula(self):
        r = frozen_risk_params()
        got = size(capital=10_000.0, stop_distance=20.0, min_quantity=0.001,
                  risk_state="LowRisk")
        r_allowed = r["budget_per_trade"] * 10_000.0 * 1.0        # 0.005·10000
        assert got["R_allowed"] == pytest.approx(r_allowed)       # 50.0
        assert got["q_risk_bound"] == pytest.approx(r_allowed / 20.0)
        assert got["sized_quantity"] == pytest.approx(2.5)
        assert got["decision"] == "ALLOW"

    def test_ladder_multipliers_are_the_frozen_values(self):
        assert RISK_LADDER_MULTIPLIER == {"NoRisk": 1.0, "LowRisk": 1.0,
                                         "MediumRisk": 0.75, "HighRisk": 0.50,
                                         "CriticalRisk": 0.0}
        for st, m in RISK_LADDER_MULTIPLIER.items():
            assert ladder_multiplier(st) == m
        with pytest.raises(RiskError, match="LADDER_STATE_QX"):
            ladder_multiplier("ExtremeRisk")

    def test_attention_cap_is_the_second_bound(self):
        got = size(capital=10_000.0, stop_distance=0.5, min_quantity=0.001,
                  risk_state="LowRisk", atr_cap=0.0001)
        k = frozen_risk_params()["k_attn"]
        assert got["q_attention_bound"] == pytest.approx(k * 0.0001 * 10_000.0)
        assert got["sized_quantity"] == pytest.approx(
            min(50.0 / 0.5, k * 0.0001 * 10_000.0))

    def test_zero_quantity_rejects_with_portfolio_capacity(self):
        got = size(capital=100.0, stop_distance=1_000.0, min_quantity=0.001)
        assert got["decision"] == "REJECT"
        assert got["reason"] == "PORTFOLIO_CAPACITY"
        assert got["sized_quantity"] == 0.0

    def test_min_quantity_floor_is_applied(self):
        got = size(capital=10_000.0, stop_distance=20.0, min_quantity=1.0)
        # R_allowed = 50 → 2.5 → floor(2.5/1)·1 = 2.0
        assert got["sized_quantity"] == 2.0
        got2 = size(capital=10_000.0, stop_distance=20.0, min_quantity=3.0)
        assert got2["decision"] == "REJECT"
        assert got2["reason"] == "PORTFOLIO_CAPACITY"
        with pytest.raises(RiskError, match="MIN_QUANTITY_QX"):
            size(capital=10_000.0, stop_distance=20.0, min_quantity=0.0)

    def test_stop_distance_and_capital_guards(self):
        zero = size(capital=10_000.0, stop_distance=0.0, min_quantity=0.001)
        assert zero["decision"] == "REJECT"
        assert zero["reason"] == "STOP_DISTANCE_INVALID"
        neg = size(capital=10_000.0, stop_distance=-5.0, min_quantity=0.001)
        assert neg["reason"] == "STOP_DISTANCE_INVALID"
        nocap = size(capital=0.0, stop_distance=20.0, min_quantity=0.001)
        assert nocap["reason"] == "CAPITAL_NON_POSITIVE"
        assert nocap["decision"] == "REJECT"
        # Capital ≤ 0 is rejected BEFORE any leverage/quantity evaluation
        assert "multiplier" not in nocap
        bad = size(capital=10_000.0, stop_distance=20.0, min_quantity=0.001,
                  contract_multiplier=0.0)
        assert bad["reason"] == "CONTRACT_MULTIPLIER_INVALID"

    def test_critical_risk_sizes_to_zero_and_rejects(self):
        got = size(capital=10_000.0, stop_distance=20.0, min_quantity=0.001,
                  risk_state="CriticalRisk")
        assert got["decision"] == "REJECT"
        assert got["R_allowed"] == 0.0

    def test_ladder_band_projection_boundaries(self):
        assert ladder_state_for(0.0) == "NoRisk"
        assert ladder_state_for(0.2499) == "LowRisk"
        assert ladder_state_for(0.25) == "MediumRisk"        # 25 % boundary
        assert ladder_state_for(0.50) == "HighRisk"
        assert ladder_state_for(0.75) == "CriticalRisk"
        assert ladder_state_for(1.0) == "CriticalRisk"
        for bad in (-0.01, 1.01, float("nan")):
            with pytest.raises(RiskError, match="BUDGET_FRACTION_QX"):
                ladder_state_for(bad)

    def test_declared_state_is_a_floor_never_a_softener(self):
        # a caller cannot downgrade the ladder: capacity escalates it
        got = adjudicate(ri(portfolio_exposure=8_000.0, capital=10_000.0,
                           symbol_cap=1e12, portfolio_cap=1e12,
                           capital_hard_cap=1e12, per_symbol_exposure=8_000.0,
                           risk_state="LowRisk"))
        assert got["sizing"]["risk_state"] == "CriticalRisk"
        assert got["decision"] == "REJECT"
        # and a stricter declared state is kept
        got2 = adjudicate(ri(portfolio_exposure=0.0, capital=10_000.0,
                            symbol_cap=1e12, portfolio_cap=1e12,
                            capital_hard_cap=1e12, per_symbol_exposure=0.0,
                            risk_state="HighRisk"))
        assert got2["sizing"]["risk_state"] == "HighRisk"

    def test_adjudicate_rejects_at_critical_capacity(self):
        got = adjudicate(ri(portfolio_exposure=8_000.0, capital=10_000.0,
                           symbol_cap=1e12, portfolio_cap=1e12,
                           capital_hard_cap=1e12, per_symbol_exposure=8_000.0))
        assert got["reason"] == "PORTFOLIO_CAPACITY"
        assert got["sized_after_all_vetoes"] is True   # sized only after 14
        assert got["decision"] == "REJECT"
        assert got["sized_quantity"] == 0.0
        assert got["sizing"]["override_reason"] == "LADDER_CRITICAL_RISK"

    def test_correlation_reduce_path(self):
        got = size(capital=10_000.0, stop_distance=20.0, min_quantity=0.001,
                  correlation={"rho": 0.95, "open_notional": [2000.0],
                               "cap": 0.70})
        assert got["decision"] in ("REDUCE", "REJECT")
        if got["decision"] == "REDUCE":
            assert "CORRELATION_REDUCE_PATH" in got["notes"]
            assert got["sized_quantity"] < 2.5

    def test_cvar_advisory_downgrade_reaches_sizing(self):
        plain = size(capital=10_000.0, stop_distance=20.0, min_quantity=0.001,
                    risk_state="MediumRisk")
        hitl = size(capital=10_000.0, stop_distance=20.0, min_quantity=0.001,
                   risk_state="MediumRisk", cvar_fraction=0.05)
        assert hitl["risk_state"] == "HighRisk"
        assert hitl["sized_quantity"] < plain["sized_quantity"]
        assert hitl["multiplier"] == 0.5


class TestFrozenBootstrapLiterals:
    """§9.5-11: every literal is asserted FROM the params YAML (no re-tuning,
    no hardcoding)."""

    def test_risk_defaults_yaml_literals(self):
        y = load_params()["risk_defaults"]
        f = frozen_risk_params()
        assert y["budget_per_trade"] == 0.005 and f["budget_per_trade"] == 0.005
        assert y["k_attn"] == 0.25 and f["k_attn"] == 0.25
        assert y["daily_loss_cap"] == 0.03
        assert y["weekly_loss_cap"] == 0.06
        assert y["consecutive_loss_halt"] == 4
        assert y["cost_R_floor"] == 0.05
        assert y["R_penalty_medium"] == 0.10 and y["R_penalty_high"] == 0.25
        assert y["max_candidates"] == 3
        assert y["correlation_cap"] == 0.70
        assert y["margin_mode"] == "ISOLATED"
        assert y["position_mode"] == "ONE_WAY"

    def test_y2_leverage_table_by_timeframe(self):
        caps = frozen_risk_params()["system_leverage_cap_by_tf"]
        assert caps == {"1m": 2, "3m": 2, "5m": 2, "15m": 3, "30m": 3,
                        "1h": 4, "2h": 4, "4h": 4, "6h": 5, "8h": 5, "12h": 5,
                        "1d": 5, "1w": 5, "1mo": 5}
        for tf, v in caps.items():
            assert leverage_cap(tf) == v
        with pytest.raises(RiskError, match="E-VAL-022"):
            leverage_cap("2d")

    def test_effective_leverage_is_a_ceiling_not_a_target(self):
        ok = effective_leverage(notional=400.0, capital_allocated=100.0,
                               timeframe="1h")
        assert ok["cap"] == 4 and ok["within_cap"] is True
        over = effective_leverage(notional=500.0, capital_allocated=100.0,
                                 timeframe="1h")
        assert over["within_cap"] is False
        assert over["reduced_notional"] == pytest.approx(400.0)
        owner = effective_leverage(notional=400.0, capital_allocated=100.0,
                                   timeframe="1h", owner_cap=2.0)
        assert owner["cap"] == 2.0
        assert owner["within_cap"] is False          # min(exchange, owner) wins
        assert owner["reduced_notional"] == pytest.approx(200.0)
        edge = effective_leverage(notional=200.0, capital_allocated=100.0,
                                 timeframe="1h", owner_cap=2.0)
        assert edge["within_cap"] is True            # exactly at the ceiling
        with pytest.raises(RiskError, match="CAPITAL_NON_POSITIVE"):
            effective_leverage(notional=1.0, capital_allocated=0.0,
                              timeframe="1h")

    def test_governed_defaults_are_the_documented_numbers(self):
        assert DEFAULT_CONTRACT_ROLLOVER_DAYS == 7
        assert (DEFAULT_MARGIN_HEALTH_WARN, DEFAULT_MARGIN_HEALTH_ACTION,
                DEFAULT_MARGIN_HEALTH_LIQUIDATION) == (0.60, 0.40, 0.20)
        assert DEFAULT_CVAR_CAP_FRACTION == 0.04


class TestAggregateLossBreakers:
    def test_thresholds_and_precedence(self):
        st = aggregate_loss_state(realized_daily=0.031, realized_weekly=0.0,
                                 consecutive_losses=0)
        assert st["daily_blocked"] is True
        assert st["weekly_blocked"] is False
        assert st["thresholds"] == {"daily": 0.03, "weekly": 0.06,
                                   "consecutive": 4}
        assert "precedence over every ALLOW" in st["precedence"]

    def test_boundary_is_strictly_greater(self):
        at = aggregate_loss_state(realized_daily=0.03, realized_weekly=0.06,
                                 consecutive_losses=4)
        assert at["daily_blocked"] is False
        assert at["weekly_blocked"] is False
        assert at["consecutive_blocked"] is False   # "> governed threshold"

    def test_reset_is_time_or_owner_only(self):
        assert circuit_breaker_reset("DAILY_LOSS_LIMIT")["reset"] is False
        assert circuit_breaker_reset("DAILY_LOSS_LIMIT",
                                    utc_rollover=True)["reset"] is True
        assert circuit_breaker_reset("WEEKLY_LOSS_LIMIT",
                                    utc_rollover=True)["owner_review_required"] \
            is True
        assert circuit_breaker_reset("CONSECUTIVE_LOSSES",
                                    owner_reviewed=True)["mechanism"] == \
            "OWNER_REVIEW"
        assert circuit_breaker_reset("CONSECUTIVE_LOSSES",
                                    utc_rollover=True)["reset"] is False
        with pytest.raises(RiskError, match="CIRCUIT_BREAKER_KIND_QX"):
            circuit_breaker_reset("NEW_YEAR")


class TestMarginAndTail:
    @pytest.mark.parametrize("value,level,veto", [
        (0.61, "OK", None), (0.60, "WARNING", None), (0.45, "WARNING", None),
        (0.40, "ACTION", 14), (0.39, "ACTION", 14), (0.21, "ACTION", 14),
        (0.20, "LIQUIDATION_APPROACH", 14), (0.05, "LIQUIDATION_APPROACH", 14)])
    def test_bands(self, value, level, veto):
        got = margin_health_state(value)
        assert got["level"] == level
        assert got["veto"] == veto

    def test_actions_are_exact(self):
        assert margin_health_state(0.40)["action"] == "BLOCK_NEW_ENTRIES"
        assert margin_health_state(0.20)["action"] == "EMERGENCY_L3_CANCEL_ALL"
        with pytest.raises(RiskError, match="MARGIN_HEALTH_QX"):
            margin_health_state(1.2)

    def test_cvar_is_advisory_only(self):
        from apex.risk.kernel import cvar_advisory
        ok = cvar_advisory(cvar_fraction=0.04, risk_state="LowRisk")
        assert ok["downgraded"] is False
        bad = cvar_advisory(cvar_fraction=0.041, risk_state="LowRisk")
        assert bad["downgraded"] is True and bad["risk_state"] == "MediumRisk"
        top = cvar_advisory(cvar_fraction=1.0, risk_state="CriticalRisk")
        assert top["risk_state"] == "CriticalRisk"      # never past the ceiling
        assert "never replacement of, the hard vetoes" in top["note"]


# ---------------------------------------------------------------------------
# RSK-ERR-506 ratchet
# ---------------------------------------------------------------------------

class TestRatchet:
    def test_ladder_states_are_the_frozen_six(self):
        assert EMERGENCY_LADDER == ("NORMAL", "L1_PAUSE", "L2_DISABLE_NEW",
                                   "L3_CANCEL_ALL", "L4_CLOSE_ALL",
                                   "L5_SAFE_MODE")
        assert RATCHET_ALLOWED_DOWNGRADE == (("L1_PAUSE", "NORMAL"),)

    @pytest.mark.parametrize("src,dst", RATCHET_BLOCKED)
    def test_the_four_blocked_downgrades(self, src, dst):
        got = ratchet_allow(src, dst)
        assert got["allowed"] is False
        assert got["error_code"] == "RSK-ERR-506"
        assert "blocked" in got["note"]

    @pytest.mark.parametrize("src,dst", [
        ("NORMAL", "L1_PAUSE"), ("L1_PAUSE", "L2_DISABLE_NEW"),
        ("L2_DISABLE_NEW", "L3_CANCEL_ALL"), ("L3_CANCEL_ALL", "L4_CLOSE_ALL"),
        ("L4_CLOSE_ALL", "L5_SAFE_MODE"), ("NORMAL", "L5_SAFE_MODE"),
    ])
    def test_every_escalation_is_allowed(self, src, dst):
        assert ratchet_allow(src, dst)["allowed"] is True
        assert ratchet_allow(src, dst)["kind"] == "ESCALATION"

    def test_l1_pause_to_normal_needs_the_owner(self):
        with pytest.raises(RiskError, match="RSK-ERR-506::OWNER_RESUME_REQUIRED"):
            ratchet_allow("L1_PAUSE", "NORMAL")
        assert ratchet_allow("L1_PAUSE", "NORMAL",
                            owner_confirmed=True)["kind"] == "OWNER_RESUME"

    def test_deeper_emergency_states_have_no_resume_path(self):
        for deeper in ("L2_DISABLE_NEW", "L3_CANCEL_ALL", "L4_CLOSE_ALL",
                      "L5_SAFE_MODE"):
            with pytest.raises(RiskError, match="RSK-ERR-506"):
                ladder_revision(revision_id="r1", applied_at="t", state="NoRisk",
                                emergency_state="NORMAL", consumed_budget=0.0,
                                reason="x", snapshot_id="s" * 64,
                                previous_state=deeper)

    def test_idempotent_repeat_is_not_a_downgrade(self):
        assert ratchet_allow("L3_CANCEL_ALL", "L3_CANCEL_ALL")["kind"] == "NOOP"

    def test_unknown_state_fails_closed(self):
        with pytest.raises(RiskError, match="EMERGENCY_STATE_QX"):
            ratchet_allow("NORMAL", "L6_PANIC")


class TestLadderStatePersistence:
    def test_ddl_declares_append_only_and_ratchet_bounds(self):
        assert "apex_risk_ladder_state" in LADDER_STATE_DDL
        assert "LADDER_STATE_APPEND_ONLY" in LADDER_STATE_DDL
        assert LADDER_STATE_DDL.count("BEFORE UPDATE") == 1
        assert LADDER_STATE_DDL.count("BEFORE DELETE") == 1
        assert LADDER_STATE_MIGRATION == "M100_cp6_risk_ladder_state"

    def test_revision_validation(self):
        rev = ladder_revision(revision_id="rev-1", applied_at="2026-01-01T00:00:00.000Z",
                             state="MediumRisk", emergency_state="L1_PAUSE",
                             consumed_budget=0.3, reason="budget",
                             snapshot_id="b" * 64)
        assert rev.multiplier == 0.75
        assert rev.to_row()[0] == "rev-1"
        assert len(LADDER_ROW_COLUMNS) == len(rev.to_row()) == 9
        with pytest.raises(RiskError, match="LADDER_STATE_QX"):
            ladder_revision(revision_id="r", applied_at="t", state="Extreme",
                           emergency_state="NORMAL", consumed_budget=0.0,
                           reason="x", snapshot_id="s")

    def test_ladder_table_is_append_only_in_sqlite(self):
        """Schema-level proof (the async migration path is exercised in the
        integration suite against the real store)."""
        import sqlite3
        db = sqlite3.connect(":memory:")
        db.executescript(LADDER_STATE_DDL)
        rev = ladder_revision(revision_id="rev-1",
                             applied_at="2026-01-01T00:00:00.000Z",
                             state="LowRisk", emergency_state="NORMAL",
                             consumed_budget=0.1, reason="seed",
                             snapshot_id="c" * 64)
        db.execute("INSERT INTO apex_risk_ladder_state (" + ",".join(
            LADDER_ROW_COLUMNS) + ") VALUES (" + ",".join(
            "?" * len(LADDER_ROW_COLUMNS)) + ")", rev.to_row())
        db.commit()
        assert db.execute("SELECT COUNT(*) FROM apex_risk_ladder_state"
                          ).fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE apex_risk_ladder_state SET state='NoRisk'")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM apex_risk_ladder_state")
        with pytest.raises(sqlite3.IntegrityError):      # state enum
            db.execute("INSERT INTO apex_risk_ladder_state VALUES "
                       "('rev-9','t','Extreme','NORMAL',0.0,1.0,'x',?,NULL)",
                       ("d" * 64,))
        with pytest.raises(sqlite3.IntegrityError):      # emergency enum
            db.execute("INSERT INTO apex_risk_ladder_state VALUES "
                       "('rev-8','t','NoRisk','L9_TEAPOT',0.0,1.0,'x',?,NULL)",
                       ("d" * 64,))
        with pytest.raises(sqlite3.IntegrityError):      # multiplier bounds
            db.execute("INSERT INTO apex_risk_ladder_state VALUES "
                       "('rev-7','t','NoRisk','NORMAL',0.0,1.5,'x',?,NULL)",
                       ("d" * 64,))
        with pytest.raises(sqlite3.IntegrityError):      # primary key: no rewrite
            db.execute("INSERT INTO apex_risk_ladder_state VALUES "
                       "('rev-1','t','NoRisk','NORMAL',0.0,1.0,'x',?,NULL)",
                       ("d" * 64,))
        db.close()

    def test_migration_is_idempotent_and_registers_once(self):
        import asyncio

        async def scenario():
            import aiosqlite
            async with aiosqlite.connect(":memory:") as db:
                first = await apply_ladder_state_migration(db)
                second = await apply_ladder_state_migration(db)
                cur = await db.execute(
                    "SELECT COUNT(*) FROM schema_migrations WHERE "
                    "migration_name=?", (LADDER_STATE_MIGRATION,))
                n = (await cur.fetchone())[0]
                cur2 = await db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND "
                    "name='apex_risk_ladder_state'")
                table = await cur2.fetchone()
                rev = ladder_revision(
                    revision_id="rev-async", applied_at="t", state="HighRisk",
                    emergency_state="L2_DISABLE_NEW", consumed_budget=0.6,
                    reason="escalation", snapshot_id="e" * 64,
                    previous_state="L1_PAUSE")
                await append_ladder_revision(db, rev)
                cur3 = await db.execute("SELECT COUNT(*) FROM "
                                       "apex_risk_ladder_state")
                rows = (await cur3.fetchone())[0]
                with pytest.raises(Exception):
                    await db.execute(
                        "UPDATE apex_risk_ladder_state SET state='NoRisk'")
                    await db.commit()
            return first["applied"], second["applied"], n, table[0], rows

        applied1, applied2, count, table_name, rows = asyncio.run(scenario())
        assert (applied1, applied2, count) == (True, False, 1)
        assert table_name == "apex_risk_ladder_state"
        assert rows == 1


class TestAuthorityAndIndependence:
    def test_kernel_never_imports_execution_or_ui(self):
        import ast
        import pathlib
        src = pathlib.Path("apex/risk/kernel.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module)
        forbidden = [m for m in mods if m.startswith(("apex.execution",
                                                     "apex.telegram",
                                                     "apex.ui", "apex.ledger",
                                                     "telegram", "aiohttp",
                                                     "http", "socket"))]
        assert forbidden == []
        assert any(m.startswith("apex.") for m in mods)   # internal seams only

    def test_no_ladder_state_outside_the_frozen_set(self):
        assert RISK_LADDER_STATES == ("NoRisk", "LowRisk", "MediumRisk",
                                     "HighRisk", "CriticalRisk")
        assert len(RISK_LADDER_STATES) == 5   # no new operational states


@pytest.mark.parametrize('applicable',[0,1,True,None,'false'])
def test_cp14_perpetual_descriptor_is_strictly_typed(applicable):
    with pytest.raises(RiskError,match='CONTRACT_APPLICABILITY_QX'):
        evaluate_vetoes(ri(environment='PAPER',time_to_expiry_days={
            'applicable':applicable,'contract_type':'PERPETUAL'}))


def test_cp14_perpetual_applicability_preserves_fourteen_vetoes():
    result=evaluate_vetoes(ri(environment='PAPER',time_to_expiry_days={
        'applicable':False,'contract_type':'PERPETUAL'}))
    assert result['evaluated_in_order']==list(range(1,15))
    assert 13 not in result['fired_numbers']
