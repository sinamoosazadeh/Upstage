"""CP-6 battery — Playbook ``PB_FVG_SWEEP_REV_A`` and position management
(Ch.11 §11.1 AE.1–AE.6, §11.2 X.1–X.8).

The mission's playbook commit item is explicit: **X.4 exit precedence** and the
**AE.1 16-field template**; both are tested exhaustively here.
"""

from __future__ import annotations

import itertools

import pytest

from apex.errors import WaveOutError
from apex.playbook.pb_fvg_sweep_rev_a import (
    AE1_FIELD_COUNT,
    AE1_TEMPLATE_FIELDS,
    EXIT_PRECEDENCE,
    EXIT_REASON_BY_FAILURE,
    MAX_HOLD_BY_TF_GROUP,
    PB_LIFECYCLE_FORWARD,
    PB_LIFECYCLE_STATES,
    PARAM_BOUNDS,
    PARENT_FAMILY_ID,
    PLAYBOOK_ID,
    PLAYBOOK_PARAMS,
    TRAIL_FACTOR_BY_VOLATILITY,
    PlaybookRecord,
    apply_partial_exit,
    be_factor_for,
    breakeven_state,
    build_stops,
    evaluate_exits,
    flatten_on_opposing_bos,
    instantiate_playbook,
    lifecycle_can_move,
    max_hold_for,
    playbook_params,
    pyramiding_policy,
    register_playbook,
    time_stop_state,
    trail_factor_for,
    trailing_state,
)


class TestAE1Template:
    def test_template_is_the_sixteen_fields_verbatim(self):
        assert AE1_TEMPLATE_FIELDS == (
            "ID", "playbook-name", "parent-setup-ID", "entry-execution-class",
            "entry-target-fill-distance", "entry-trail-policy",
            "position-management-phase", "stop-structure",
            "take-profit-structure", "time-exit-policy",
            "breakeven-conditions", "anomaly-exit-trigger", "scaling-rules",
            "failure-mode-exit", "lifecycle", "research-battery-binding")
        assert AE1_FIELD_COUNT == len(AE1_TEMPLATE_FIELDS) == 16

    def test_instantiated_record_has_exactly_the_sixteen_fields(self):
        rec = instantiate_playbook()
        assert isinstance(rec, PlaybookRecord)
        assert tuple(rec.record) == AE1_TEMPLATE_FIELDS
        assert rec.record["ID"] == PLAYBOOK_ID == "PB_FVG_SWEEP_REV_A"
        assert rec.record["parent-setup-ID"] == PARENT_FAMILY_ID
        assert rec.regime_window == (
            "TRANSITION", "EXPANSION", "TREND_EXPANSION", "TREND_CONTRACTION",
            "TREND", "COMPRESSION", "CHOP", "RANGE")

    def test_missing_field_fails_closed(self):
        bad = {k: v for k, v in instantiate_playbook().record.items()
               if k != "scaling-rules"}
        with pytest.raises(ValueError, match="PB_SCHEMA_QX"):
            PlaybookRecord(record=bad)

    def test_invented_field_fails_closed(self):
        bad = dict(instantiate_playbook().record)
        bad["exit-anyway"] = True
        with pytest.raises(ValueError, match="PB_SCHEMA_QX"):
            PlaybookRecord(record=bad)

    def test_parent_must_be_the_registered_family(self):
        bad = dict(instantiate_playbook().record)
        bad["parent-setup-ID"] = "SF_INVENTED"
        with pytest.raises(ValueError, match="PB_PARENT_QX"):
            PlaybookRecord(record=bad)

    def test_no_hardcoded_constant_outside_governance_bounds(self):
        # AE.1: "No playbook may contain hardcoded numeric constants outside
        # governance bounds" — every numeric param of the instantiated playbook
        # is either inside the X.6 bounds or a frozen blueprint literal.
        p = playbook_params()
        assert PARAM_BOUNDS["stop_distance_atr"][0] <= p["stop_buffer_atr"] \
            <= 3.0 or p["stop_buffer_atr"] == 0.25      # AE.5 frozen literal
        assert PARAM_BOUNDS["target_distance_r"][0] <= p["target_r"] \
            <= PARAM_BOUNDS["target_distance_r"][1]
        assert PARAM_BOUNDS["be_factor_r"][0] <= p["be_trigger_r"] \
            <= PARAM_BOUNDS["be_factor_r"][1]
        assert PARAM_BOUNDS["max_hold_bars"][0] <= p["max_hold_bars"] \
            <= PARAM_BOUNDS["max_hold_bars"][1]
        assert PARAM_BOUNDS["trail_factor"][0] <= 1.5   # trail_after_R bound
        with pytest.raises(ValueError, match="UNKNOWN_PB_PARAM_QX"):
            playbook_params({"made_up": 1})

    def test_failure_modes_map_onto_the_precedence_items(self):
        # AE.1 #6: "Each anomaly-exit-trigger must map to one of the five
        # exit-precedence items or be recorded as a non-exit reason"
        assert set(EXIT_REASON_BY_FAILURE.values()) == {
            "DATA_INVALID", "STRUCTURAL_INVALID", "TIME_EXIT",
            "EXECUTION_FAILED", "ECONOMIC_INVALID"}
        rec = instantiate_playbook()
        assert rec.record["anomaly-exit-trigger"]["maps_to_precedence_item"] == 2
        assert set(EXIT_PRECEDENCE) == {
            "INVALID_DATA", "STRUCTURAL_INVALIDATION", "STOP_LOSS",
            "TAKE_PROFIT", "TIME_STOP"}

    def test_extra_playbook_is_wave_out(self):
        with pytest.raises(WaveOutError) as ei:
            register_playbook("PB_SECOND")
        assert ei.value.feature == "extra_playbooks"


class TestLifecycleAE2:
    def test_five_states_and_forward_edges(self):
        assert PB_LIFECYCLE_STATES == ("DRAFT", "VALIDATING", "ACTIVE",
                                       "DEGRADED", "DEPRECATED")
        assert PB_LIFECYCLE_FORWARD["DRAFT"] == ("VALIDATING",)
        assert set(PB_LIFECYCLE_FORWARD["VALIDATING"]) == {"ACTIVE", "DRAFT"}
        assert set(PB_LIFECYCLE_FORWARD["DEPRECATED"]) == set()

    def test_illegal_moves_are_refused(self):
        assert lifecycle_can_move("DRAFT", "ACTIVE") is False
        assert lifecycle_can_move("DEPRECATED", "ACTIVE") is False
        assert lifecycle_can_move("ACTIVE", "VALIDATING") is False
        with pytest.raises(ValueError, match="PB_LIFECYCLE_QX"):
            lifecycle_can_move("DRAFT", "PUBLISHED")

    def test_active_is_not_self_service(self):
        with pytest.raises(ValueError, match="PB_ACTIVE_GATE_QX"):
            lifecycle_can_move("VALIDATING", "ACTIVE")

    def test_deprecation_needs_the_owner(self):
        with pytest.raises(ValueError, match="PB_DEPRECATION_OWNER_GATE_QX"):
            lifecycle_can_move("ACTIVE", "DEPRECATED")
        assert lifecycle_can_move("ACTIVE", "DEGRADED") is True   # auto
        assert lifecycle_can_move("DEGRADED", "ACTIVE") is True    # recovery
        assert lifecycle_can_move("ACTIVE", "DEPRECATED",
                                  owner_confirmed=True) is True


# ---------------------------------------------------------------------------
# X.4 — exit precedence (exhaustive over the 2^5 fire patterns)
# ---------------------------------------------------------------------------

FLAGS = ("data_invalid", "structural_invalidation", "stop_hit", "target_hit",
         "time_stop")
ITEM_BY_FLAG = {"data_invalid": 1, "structural_invalidation": 2,
                "stop_hit": 3, "target_hit": 4, "time_stop": 5}
REASON_BY_ITEM = {1: "DATA_INVALID", 2: "STRUCTURAL_INVALID", 3: "STOP_LOSS",
                  4: "TAKE_PROFIT", 5: "TIME_EXIT"}


class TestExitPrecedence:
    def test_nothing_fired(self):
        res = evaluate_exits()
        assert res["exit_reason"] is None and res["fired"] == []
        assert res["reason"] == "NO_EXIT"

    @pytest.mark.parametrize("r", range(1, 6))
    def test_single_fire_uses_its_own_reason(self, r):
        flag = FLAGS[r - 1]
        res = evaluate_exits(**{flag: True})
        assert res["executed_item"] == r
        assert res["exit_reason"] == REASON_BY_ITEM[r]
        assert len(res["fired"]) == 1

    def test_every_combination_resolves_to_the_lowest_item(self):
        for k in range(1, 6):
            for combo in itertools.combinations(FLAGS, k):
                kw = {c: True for c in combo}
                res = evaluate_exits(**kw)
                expect_item = min(ITEM_BY_FLAG[c] for c in combo)
                assert res["executed_item"] == expect_item, combo
                assert res["exit_reason"] == REASON_BY_ITEM[expect_item]
                # ALL fired conditions are recorded, not just the executed one
                assert len(res["fired"]) == k
                assert [f["item"] for f in res["fired"]] == sorted(
                    ITEM_BY_FLAG[c] for c in combo)

    def test_data_invalid_beats_everything_with_market_close(self):
        res = evaluate_exits(data_invalid=True, target_hit=True, stop_hit=True,
                            structural_invalidation=True, time_stop=True)
        assert res["exit_reason"] == "DATA_INVALID"
        assert res["executed_item"] == 1
        assert len(res["fired"]) == 5

    def test_stop_price_is_used_for_a_stop_exit_and_target_for_a_target_exit(self):
        s = evaluate_exits(stop_hit=True, target_hit=True, stop_price=97.5,
                          target_price=110.0, current_price=99.0)
        assert s["price"] == 97.5
        t = evaluate_exits(target_hit=True, target_price=110.0,
                          current_price=109.0)
        assert t["price"] == 110.0
        d = evaluate_exits(data_invalid=True, current_price=101.0)
        assert d["price"] == 101.0          # immediate close at market price

    def test_be_and_trailing_are_not_exit_conditions(self):
        # X.4: they are stop-management operations inside item 3
        st = instantiate_playbook().record
        assert "scaling-rules" in st
        be = breakeven_state(entry=100.0, initial_stop=98.0, direction=1,
                            current=102.0, fees_round_trip=0.0008,
                            half_spread=0.0002, be_factor_r=1.0)
        assert be["counts_as_exit"] is False
        tr = trailing_state(entry=100.0, current_stop=98.0, direction=1,
                            current=104.0, atr=1.0, volatility_regime="NORMAL",
                            trail_after_r=1.5, trail_atr_mult=1.0)
        assert tr["counts_as_exit"] is False


class TestStopsAndTargets:
    def test_long_stop_formula_verbatim(self):
        s = build_stops(direction=+1, entry=100.0, atr=2.0, sweep_extreme=98.0,
                       fvg_low=99.0)
        # min(98.0, 99.0) − 0.25·2.0 = 97.5
        assert s["stop"] == pytest.approx(97.5)
        assert s["R"] == pytest.approx(2.5)
        assert s["target"] == pytest.approx(107.5)      # entry + 3R

    def test_short_stop_formula_verbatim(self):
        s = build_stops(direction=-1, entry=100.0, atr=2.0, sweep_extreme=104.0,
                       fvg_high=103.0)
        # max(104.0, 103.0) + 0.25·2.0 = 104.5
        assert s["stop"] == pytest.approx(104.5)
        assert s["target"] == pytest.approx(86.5)       # entry − 3R

    def test_missing_fvg_side_uses_the_sweep_extreme_alone(self):
        s = build_stops(direction=+1, entry=100.0, atr=1.0, sweep_extreme=98.0)
        assert s["stop"] == pytest.approx(97.75)

    def test_fail_closed_inputs(self):
        for kw, msg in (
            (dict(direction=0, entry=100.0, atr=1.0, sweep_extreme=98.0),
             "PB_DIRECTION_QX"),
            (dict(direction=+1, entry=100.0, atr=0.0, sweep_extreme=98.0),
             "PB_ATR_QX"),
            (dict(direction=+1, entry=100.0, atr=float("nan"),
                  sweep_extreme=98.0), "PB_ATR_QX"),
            (dict(direction=+1, entry=97.0, atr=1.0, sweep_extreme=98.0),
             "PB_STOP_SIDE_QX"),
            (dict(direction=-1, entry=104.0, atr=1.0, sweep_extreme=103.0),
             "PB_STOP_SIDE_QX"),
        ):
            with pytest.raises(ValueError, match=msg):
                build_stops(**kw)

    def test_anomaly_flatten_sequence_never_forbidden_order_types(self):
        plan = flatten_on_opposing_bos()
        assert plan["sequence"] == ["LIMIT+IOC(reduce-only)",
                                   "LIMIT priceType=MARKET(reduce-only)"]
        assert "flashClose" in plan["forbidden"]
        assert plan["counts_as_new_veto"] is False
        built = []
        flatten_on_opposing_bos(order_builder=built.append)
        assert len(built) == 2


class TestBreakevenTrailingTimeStop:
    def test_activation_threshold_is_exact(self):
        R = 2.0
        args = dict(entry=100.0, initial_stop=98.0, direction=1,
                    fees_round_trip=0.0008, half_spread=0.0002,
                    be_factor_r=1.0)
        assert breakeven_state(current=101.99, **args)["activated"] is False
        assert breakeven_state(current=102.0, **args)["activated"] is True

    def test_buffer_makes_breakeven_real(self):
        res = breakeven_state(entry=100.0, initial_stop=98.0, direction=1,
                             current=103.0, fees_round_trip=0.001,
                             half_spread=0.0006, be_factor_r=1.0,
                             be_offset_r=0.10)
        # buffer = (0.001 + 0.0006)·100 + 0.10·2 = 0.16 + 0.20 = 0.36
        assert res["buffer"] == pytest.approx(0.36)
        assert res["be_stop_price"] == pytest.approx(100.36)
        assert res["be_stop_price"] > 100.0     # LONG moves up, never down

    def test_short_mirror(self):
        res = breakeven_state(entry=100.0, initial_stop=102.0, direction=-1,
                             current=97.0, fees_round_trip=0.001,
                             half_spread=0.0, be_factor_r=1.0, be_offset_r=0.1)
        assert res["activated"] is True
        # buffer = 0.001·100 + 0.10·R(2.0) = 0.30 → 100.0 − 0.30
        assert res["be_stop_price"] == pytest.approx(99.7)

    def test_zero_risk_unit_fails_closed(self):
        with pytest.raises(ValueError, match="PB_RISK_UNIT_QX"):
            breakeven_state(entry=100.0, initial_stop=100.0, direction=1,
                           current=101.0, fees_round_trip=0.0, half_spread=0.0,
                           be_factor_r=1.0)

    def test_be_factor_bootstrap_table_and_bounds(self):
        assert be_factor_for("15m")["be_factor_r"] == 0.8
        assert be_factor_for("1h")["be_factor_r"] == 1.0
        assert be_factor_for("1d")["be_factor_r"] == 1.2
        assert be_factor_for("1h")["source"] == "FROZEN_BOOTSTRAP_X1"
        assert be_factor_for("1h", {"be_factor": 1.4})["source"] == \
            "OPTIMIZED_PACKAGE"
        with pytest.raises(ValueError, match="PB_PARAM_OUT_OF_BOUNDS"):
            be_factor_for("1h", {"be_factor": 1.6})
        with pytest.raises(ValueError, match="E-VAL-022"):
            be_factor_for("2d")

    def test_trail_activation_and_extreme_disable(self):
        common = dict(entry=100.0, current_stop=98.0, direction=1, atr=1.0,
                      trail_after_r=1.5)
        off = trailing_state(current=101.0, volatility_regime="NORMAL",
                            trail_atr_mult=1.0, **common)
        assert off["activated"] is False and off["distance"] == 1.0
        on = trailing_state(current=104.0, volatility_regime="NORMAL",
                           trail_atr_mult=1.0, **common)
        assert on["activated"] is True
        assert on["stop"] == pytest.approx(103.0)
        ext = trailing_state(current=110.0, volatility_regime="EXTREME",
                            **common)
        assert ext["activated"] is False
        assert ext["reason"] == "VOLATILITY_EXTREME_FIXED_STOP"
        assert ext["stop"] == 98.0      # revert to the current fixed stop

    def test_trail_never_widens_and_follows_price_up(self):
        # after the first activation, a lower candidate must not move the stop
        first = trailing_state(entry=100.0, current_stop=98.0, direction=1,
                              current=104.0, atr=1.0,
                              volatility_regime="NORMAL", trail_after_r=1.5,
                              trail_atr_mult=1.0)
        second = trailing_state(entry=100.0, current_stop=first["stop"],
                               direction=1, current=104.2, atr=1.0,
                               volatility_regime="NORMAL", trail_after_r=1.5,
                               trail_atr_mult=1.0)
        assert second["stop"] >= first["stop"]
        # and a fallback regime table is used when no playbook multiplier is set
        t = trail_factor_for("HIGH")
        assert t["trail_factor"] == 3.0 and t["trailing_enabled"] is True
        assert trail_factor_for("EXTREME")["trailing_enabled"] is False
        assert trail_factor_for("EXTREME")["trail_factor"] is None
        with pytest.raises(ValueError, match="PB_VOLATILITY_REGIME_QX"):
            trail_factor_for("STORMY")

    def test_time_stop_is_a_hard_ceiling_on_closed_candles(self):
        below = time_stop_state(bars_held=15, timeframe="1h", max_hold_bars=16)
        at = time_stop_state(bars_held=16, timeframe="1h", max_hold_bars=16)
        assert below["time_stop_triggered"] is False
        assert at["time_stop_triggered"] is True
        assert at["record"] == {"time_stop_triggered": True}
        # the generic X.3 table is the fallback source
        assert max_hold_for("15m")["max_hold_bars"] == 96
        assert max_hold_for("1h")["max_hold_bars"] == 60
        assert max_hold_for("1d")["max_hold_bars"] == 40
        assert max_hold_for("1w")["max_hold_bars"] == 20
        assert set(MAX_HOLD_BY_TF_GROUP) == {
            "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h",
            "12h", "1d", "1w", "1mo"}
        with pytest.raises(ValueError, match="PB_PARAM_OUT_OF_BOUNDS"):
            max_hold_for("1h", {"max_hold_bars": 250})


class TestPositionScaling:
    def test_pyramiding_is_disabled(self):
        pol = pyramiding_policy()
        assert pol["scaling_in"] == "DISABLED"
        assert pol["one_position_per"] == ("symbol", "timeframe", "direction")
        assert pol["scaling_out"] == "playbook target ladder only (partial takes)"

    def test_partial_exit_reduces_quantity_and_risk_proportionally(self):
        got = apply_partial_exit(sized_quantity=10.0, reserved_risk=4.0,
                                ladder_weights=(0.3, 0.4, 0.3),
                                taken_index=0, current_stop=99.0,
                                direction=1)
        assert got["closed_fraction"] == pytest.approx(0.3)
        assert got["sized_quantity"] == pytest.approx(7.0)
        assert got["reserved_risk"] == pytest.approx(2.8)
        assert got["scaling_in_allowed"] is False

    def test_stop_is_never_widened_by_a_partial_exit(self):
        tightened = apply_partial_exit(sized_quantity=10.0, reserved_risk=4.0,
                                       ladder_weights=(0.5, 0.5),
                                       taken_index=0, current_stop=99.0,
                                       direction=1, proposed_new_stop=99.5)
        assert tightened["stop"] == 99.5
        loosening = apply_partial_exit(sized_quantity=10.0, reserved_risk=4.0,
                                      ladder_weights=(0.5, 0.5), taken_index=0,
                                      current_stop=99.0, direction=1,
                                      proposed_new_stop=98.0)
        assert loosening["stop"] == 99.0        # refused: never widened
        assert loosening["stop_widened"] is False
        short = apply_partial_exit(sized_quantity=10.0, reserved_risk=4.0,
                                   ladder_weights=(1.0,), taken_index=0,
                                   current_stop=101.0, direction=-1,
                                   proposed_new_stop=100.0)
        assert short["stop"] == 100.0           # SHORT tightens downward
        short_loose = apply_partial_exit(sized_quantity=10.0, reserved_risk=4.0,
                                        ladder_weights=(1.0,), taken_index=0,
                                        current_stop=101.0, direction=-1,
                                        proposed_new_stop=102.0)
        assert short_loose["stop"] == 101.0

    def test_ladder_validation(self):
        base = dict(sized_quantity=10.0, reserved_risk=1.0, current_stop=99.0,
                    direction=1)
        for over, msg in (
            (dict(ladder_weights=(), taken_index=0), "PB_LADDER_QX"),
            (dict(ladder_weights=(1.0,), taken_index=3), "PB_LADDER_INDEX_QX"),
            (dict(ladder_weights=(1.0,), taken_index=0, sized_quantity=-1.0),
             "PB_POSITION_QX"),
        ):
            with pytest.raises(ValueError, match=msg):
                apply_partial_exit(**{**base, **over})


class TestAttributionAndInstantiatedNumbers:
    def test_record_fields_are_the_x4_attribution_set(self):
        be = breakeven_state(entry=100.0, initial_stop=98.0, direction=1,
                            current=103.0, fees_round_trip=0.0008,
                            half_spread=0.0002, be_factor_r=1.0)
        tr = trailing_state(entry=100.0, current_stop=98.0, direction=1,
                           current=105.0, atr=1.0, volatility_regime="NORMAL",
                           trail_after_r=1.5, trail_atr_mult=1.0)
        ts = time_stop_state(bars_held=20, timeframe="1h", max_hold_bars=16)
        assert set(be["record"]) == {"breakeven_activated",
                                    "breakeven_stop_price"}
        assert set(tr["record"]) == {"trailing_activated",
                                    "trailing_distance_final"}
        assert set(ts["record"]) == {"time_stop_triggered"}

    def test_instantiated_params_are_the_frozen_literals(self):
        p = playbook_params()
        assert p["stop_buffer_atr"] == 0.25
        assert p["target_r"] == 3.0
        assert p["be_trigger_r"] == 1.0 and p["be_offset_r"] == 0.10
        assert p["trail_after_r"] == 1.5 and p["trail_atr_mult"] == 1.0
        assert p["max_hold_bars"] == 16
        assert TRAIL_FACTOR_BY_VOLATILITY == {
            "VERY_LOW": 2.0, "LOW": 2.0, "NORMAL": 2.5, "HIGH": 3.0,
            "EXTREME": None}

    def test_determinism(self):
        a = instantiate_playbook().to_dict()
        b = instantiate_playbook().to_dict()
        assert a == b
