"""CP-6 battery — Forecast (Ch.13 §13.1) + the AG registry (§13.2).

T-DR-003 (SL-3 forecast replay) is exercised by ``test_replay_is_byte_identical``.
"""

from __future__ import annotations

import math

import pytest

from apex.errors import WaveOutError
from apex.forecast.logistic import (
    BOOTSTRAP_P,
    BOOTSTRAP_Q_FORECAST,
    CALIBRATION_THRESHOLDS,
    DECAY_LAMBDA_PER_BAR,
    HORIZON_MULTIPLE,
    INVALIDATION_REASONS,
    MIN_OBS_DEFAULT,
    UNCERTAINTY_COMPONENTS,
    X_FEATURES,
    X_FEATURE_COUNT,
    ForecastError,
    ForecastEvent,
    build_forecast,
    composite_estimate,
    cost_r_floor,
    decay,
    economic_utility,
    h_max_tf,
    horizon_bars,
    logistic_bootstrap_p,
    platt_or_isotonic_oos,
    require_calibrated_package,
    r_penalty_for,
    uncertainty_from,
)
from apex.forecast.registry import (
    AG2_FIELDS,
    AG_MODEL_REGISTRY,
    AG_REGISTRY_SUMMARY,
    AGModel,
    RED_LINE,
    ag_models_bound_to_q_i,
    research_only_models,
)

X0 = {k: 0.0 for k in X_FEATURES}


def ev(**over):
    kw = dict(target_condition="touch(110)", stop_condition="touch(95)",
              horizon=16, entry_ref="setup-1", symbol="BTCUSDT",
              timeframe="1h", timestamp=1)
    kw.update(over)
    return ForecastEvent(**kw)


class TestFrozenContract:
    def test_event_shape_is_the_exact_seven_fields(self):
        d = ev().to_dict()
        assert set(d) == {"target_condition", "stop_condition", "horizon",
                          "entry_ref", "symbol", "timeframe", "timestamp"}

    def test_event_validation_fails_closed(self):
        with pytest.raises(ForecastError, match="HORIZON_QX"):
            ev(horizon=0)
        with pytest.raises(ForecastError, match="EVENT_CONDITIONS_QX"):
            ev(stop_condition="")
        with pytest.raises(ForecastError, match="EVENT_KEY_QX"):
            ev(symbol="")

    def test_feature_vector_is_the_frozen_twelve(self):
        assert X_FEATURES == ("s_struct", "s_liq", "s_vol", "s_fvg", "s_ob",
                             "trend_stack", "momentum_z", "regime_entropy",
                             "vol_quantile", "temporal_core_flag", "log_rr",
                             "log_cost_R")
        assert X_FEATURE_COUNT == 12 == len(X_FEATURES)

    def test_bootstrap_is_exactly_half(self):
        assert logistic_bootstrap_p(X0) == BOOTSTRAP_P == 0.5
        # β=0 ⇒ the vector cannot move p: an uninformative prior is honest
        assert logistic_bootstrap_p({k: 7.5 for k in X_FEATURES}) == 0.5

    def test_missing_or_unknown_feature_fails_closed(self):
        with pytest.raises(ForecastError, match="FORECAST_FEATURE_VECTOR_QX"):
            logistic_bootstrap_p({k: 0.0 for k in X_FEATURES[1:]})
        with pytest.raises(ForecastError, match="FORECAST_FEATURE_VECTOR_QX"):
            logistic_bootstrap_p({**X0, "sentiment": 1.0})
        with pytest.raises(ForecastError, match="FORECAST_FEATURE_NONFINITE_QX"):
            logistic_bootstrap_p({**X0, "log_rr": float("nan")})

    def test_q_forecast_default_is_the_bootstrap_value(self):
        rec = build_forecast(ev(), x=X0, environment="PAPER")
        assert rec.q_forecast == BOOTSTRAP_Q_FORECAST == 0.5

    def test_seven_invalidation_reasons_in_order(self):
        assert INVALIDATION_REASONS == (
            "TARGET_REACHED", "INVALIDATION", "HORIZON_EXPIRED", "REGIME_SHIFT",
            "QUALITY_DEGRADED", "PACKAGE_INVALIDATED", "SOURCE_STALE")
        assert len(set(INVALIDATION_REASONS)) == 7


class TestPUCSemantics:
    def test_uncertainty_combination_is_the_frozen_formula(self):
        assert uncertainty_from(1.0, 1.0, 1.0) == 1.0
        assert uncertainty_from(0.0, 0.0, 0.0) == 0.0
        assert uncertainty_from(0.6, 0.4, 0.2) == pytest.approx(0.46)  # 0.5·0.6 + 0.3·0.4 + 0.2·0.2
        # an out-of-range component fails closed; the clip applies to the
        # weighted sum (all-ones is the maximum legitimate value)
        for bad in ((2.0, 0.0, 0.0), (-0.1, 0.0, 0.0), (0.0, float("nan"), 0.0)):
            with pytest.raises(ForecastError, match="UNCERTAINTY_INPUT_QX"):
                uncertainty_from(*bad)

    def test_named_components_are_the_six(self):
        assert UNCERTAINTY_COMPONENTS == ("disagreement", "sampling",
                                         "calibration", "data_quality",
                                         "regime_shift", "tail_risk")
        rec = build_forecast(ev(), x=X0, uncertainty={
            "disagreement": 0.4, "sampling": 0.2, "calibration": 0.1,
            "data_quality": 0.3, "regime_shift": 0.5, "tail_risk": 0.6},
            environment="PAPER")
        assert set(rec.uncertainty) == set(UNCERTAINTY_COMPONENTS)
        # C = 1 − max(U) (the §13.1 binding), bounded and reported
        assert rec.c == pytest.approx(1.0 - 0.6)
        assert rec.components["u_structured"] == pytest.approx(rec.u)
        assert rec.components["c_from_max_u"] == pytest.approx(rec.c)

    def test_out_of_range_component_fails_closed(self):
        with pytest.raises(ForecastError, match="UNCERTAINTY_COMPONENT_QX"):
            build_forecast(ev(), x=X0, uncertainty={"tail_risk": 1.4},
                          environment="PAPER")


class TestEconomicUtilityAndDecay:
    def test_eu_formula_and_bootstrap_value(self):
        got = economic_utility(0.5, 3.0, 0.02, 0.0)
        assert got["EU"] == pytest.approx(0.5 * 3.0 - 0.5 - 0.02)   # 0.98
        assert got["P"] == 0.5 and got["RR"] == 3.0
        assert economic_utility(0.5, 1.0, 0.0, 0.0)["EU"] == 0.0

    def test_r_penalty_ladder_values(self):
        assert r_penalty_for("NoRisk") == 0.0
        assert r_penalty_for("LowRisk") == 0.0
        assert r_penalty_for("MediumRisk") == 0.10
        assert r_penalty_for("HighRisk") == 0.25
        assert r_penalty_for("CriticalRisk") == math.inf
        with pytest.raises(ForecastError, match="RISK_STATE_QX"):
            r_penalty_for("NoRiskNoRisk")

    def test_unavailable_spread_enforces_the_cost_floor(self):
        floor = cost_r_floor()
        assert floor == 0.05
        got = economic_utility(0.6, 2.0, 0.0, 0.0, spread_available=False)
        assert got["cost_R"] == floor
        assert got["EU"] == pytest.approx(1.2 - 0.4 - floor)
        better = economic_utility(0.6, 2.0, 0.09, 0.0, spread_available=False)
        assert better["cost_R"] == pytest.approx(0.09)   # never reduced
        with pytest.raises(ForecastError, match="P_HAT_QX"):
            economic_utility(1.2, 2.0, 0.0, 0.0)

    def test_horizon_and_decay(self):
        got = horizon_bars(10, "1h")
        assert got["horizon"] == HORIZON_MULTIPLE * 10
        assert got["h_max"] is None                    # governed: not defined
        assert got["reason"] == "H_MAX_UNAVAILABLE_GOVERNED"
        assert h_max_tf("1h") is None
        assert decay(0.0) == 1.0
        assert decay(1.0) == pytest.approx(math.exp(-DECAY_LAMBDA_PER_BAR))
        assert decay(3.0) < decay(2.0) < decay(1.0)
        with pytest.raises(ForecastError, match="DECAY_INPUT_QX"):
            decay(-1.0)
        with pytest.raises(ForecastError, match="HORIZON_INPUT_QX"):
            horizon_bars(0, "1h")

    def test_calibration_thresholds_are_the_documented_numbers(self):
        assert CALIBRATION_THRESHOLDS == {
            "brier_desirable": 0.25, "log_loss_desirable": 0.70,
            "rolling_calibration_error_rollback": 0.10}


class TestCompositeEstimator:
    def test_weighted_mean_and_normalization(self):
        comps = {"f": {"p": 0.7, "n_obs": 100}, "b": {"p": 0.5, "n_obs": 100},
                 "r": {"p": 0.6, "n_obs": 100}, "e": {"p": 0.65, "n_obs": 100}}
        got = composite_estimate(comps)
        assert got["reason"] == "COMPOSITE_OK"
        assert sum(got["weights"].values()) == pytest.approx(1.0)
        expect = (0.30 * 0.7 + 0.30 * 0.5 + 0.30 * 0.6 + 0.10 * 0.65)
        assert got["p_hat"] == pytest.approx(expect)

    def test_small_sample_shrinkage_shifts_weight_to_bayesian(self):
        comps = {"f": {"p": 0.9, "n_obs": MIN_OBS_DEFAULT - 1},
                 "b": {"p": 0.5, "n_obs": 500},
                 "r": {"p": 0.9, "n_obs": 500}}
        got = composite_estimate(comps)
        assert "f" in got["shrinkage"]
        # weight moved toward b, and nothing was zeroed
        assert got["weights"]["b"] > got["weights"]["f"]
        assert got["weights"]["f"] > 0.0
        assert set(got["weights"]) == {"f", "b", "r"}

    def test_ensemble_absence_redistributes_never_zero_substitutes(self):
        with_e = composite_estimate({"f": {"p": 0.6, "n_obs": 100},
                                     "b": {"p": 0.6, "n_obs": 100},
                                     "r": {"p": 0.6, "n_obs": 100},
                                     "e": {"p": 0.6, "n_obs": 100}})
        without = composite_estimate({"f": {"p": 0.6, "n_obs": 100},
                                      "b": {"p": 0.6, "n_obs": 100},
                                      "r": {"p": 0.6, "n_obs": 100}})
        assert "e" in without["dropped"]
        assert without["p_hat"] == pytest.approx(0.6)
        assert with_e["p_hat"] == pytest.approx(0.6)
        assert "e" not in without["weights"]
        assert sum(without["weights"].values()) == pytest.approx(1.0)

    def test_no_components_is_a_vacuous_refusal(self):
        got = composite_estimate({})
        assert got["p_hat"] is None and got["state"] == "UNAVAILABLE"
        assert got["reason"] == "FORECAST_NO_COMPONENTS"
        assert got["eligible_environments"] == ()
        got2 = composite_estimate({"f": {"n_obs": 5}, "b": {"n_obs": 5}})
        assert got2["reason"] == "FORECAST_NO_COMPONENTS"

    def test_unknown_weight_key_fails_closed(self):
        with pytest.raises(ForecastError, match="COMPOSITE_WEIGHT_QX"):
            composite_estimate({"f": {"p": 0.5, "n_obs": 10}},
                              weights={"w_f": 1.0, "w_magic": 0.0})


class TestPaperOnlyPrior:
    def test_bootstrap_prior_eligible_in_research_and_paper(self):
        for env in ("RESEARCH", "PAPER", "BACKTEST"):
            rec = build_forecast(ev(), x=X0, environment=env)
            assert rec.bootstrap_prior is True
            assert rec.is_admissible(env) is True

    def test_live_capital_is_refused_not_degraded(self):
        with pytest.raises(ForecastError,
                          match="FORECAST_BOOTSTRAP_NOT_LIVE_ELIGIBLE"):
            build_forecast(ev(), x=X0, environment="LIVE")

    def test_calibrated_package_unlocks_live(self):
        pkg = {"p_hat": 0.62, "q_forecast": 0.71}
        rec = build_forecast(ev(), x=X0, package=pkg, environment="LIVE")
        assert rec.bootstrap_prior is False
        assert "LIVE" in rec.eligible_environments
        assert rec.p_hat == pytest.approx(0.62)

    def test_asking_for_the_missing_package_or_calibration_raises_wave_out(self):
        with pytest.raises(WaveOutError) as ei:
            require_calibrated_package(None)
        assert ei.value.feature == "optimizer_live_yaml_write"
        with pytest.raises(WaveOutError):
            platt_or_isotonic_oos()
        assert require_calibrated_package({"p_hat": 0.6}) == {"p_hat": 0.6}


class TestInvalidation:
    def test_seven_reasons_unique_traceable_immutable(self):
        rec = build_forecast(ev(), x=X0, environment="PAPER")
        assert rec.invalidation is None and rec.state == "ACTIVE"
        rec.invalidate("REGIME_SHIFT", at=5,
                      trigger_observation_id="obs-77")
        assert rec.state == "INVALIDATED"
        assert rec.invalidation == {"state": "INVALIDATED",
                                   "reason": "REGIME_SHIFT", "at": 5,
                                   "trigger_observation_id": "obs-77"}
        assert rec.is_admissible("PAPER") is False        # never silently usable
        # the record is never deleted and never re-labelled
        with pytest.raises(ForecastError, match="FORECAST_INVALIDATION_IMMUTABLE"):
            rec.invalidate("HORIZON_EXPIRED", at=6,
                          trigger_observation_id="obs-78")
        assert rec.invalidation["reason"] == "REGIME_SHIFT"

    @pytest.mark.parametrize("reason", INVALIDATION_REASONS)
    def test_every_reason_is_accepted(self, reason):
        rec = build_forecast(ev(), x=X0, environment="PAPER")
        rec.invalidate(reason, at=1, trigger_observation_id="obs-1")
        assert rec.invalidation["reason"] == reason

    def test_unknown_reason_and_missing_trigger_fail_closed(self):
        rec = build_forecast(ev(), x=X0, environment="PAPER")
        with pytest.raises(ForecastError,
                          match="FORECAST_INVALIDATION_REASON_QX"):
            rec.invalidate("PRICE_MOVED", at=1, trigger_observation_id="obs-1")
        with pytest.raises(ForecastError,
                          match="FORECAST_INVALIDATION_LINEAGE_QX"):
            rec.invalidate("REGIME_SHIFT", at=1, trigger_observation_id="")


class TestTDR003Replay:
    def test_replay_is_byte_identical(self):
        from apex.identity.canonical_json import canonical_json
        a = build_forecast(ev(), x=X0, uncertainty={"calibration": 0.2},
                          rr=3.0, cost_r=0.02, risk_state="MediumRisk",
                          environment="PAPER")
        b = build_forecast(ev(), x=X0, uncertainty={"calibration": 0.2},
                          rr=3.0, cost_r=0.02, risk_state="MediumRisk",
                          environment="PAPER")
        assert canonical_json(a.to_dict()) == canonical_json(b.to_dict())
        # a different as_of changes the record (no cross-scenario leakage)
        c = build_forecast(ev(timestamp=2), x=X0, environment="PAPER")
        assert canonical_json(c.to_dict()) != canonical_json(a.to_dict())


class TestAGRegistry:
    def test_twelve_entries_with_seven_fields_each(self):
        assert len(AG_MODEL_REGISTRY) == 12
        for m in AG_MODEL_REGISTRY.values():
            assert set(m.to_dict()) - {"engine", "key", "gate_enrichment",
                                      "contract_version"} == set(AG2_FIELDS)

    def test_every_model_binds_to_q_i_or_nothing(self):
        for m in AG_MODEL_REGISTRY.values():
            assert m.output_binding in ("q_i", "none")
        assert "s_i" not in {m.output_binding
                            for m in AG_MODEL_REGISTRY.values()}
        assert len(ag_models_bound_to_q_i()) == 10

    def test_e08_has_no_model_and_e11_is_research_without_consumer(self):
        assert AG_MODEL_REGISTRY["E08"].status == "VERIFIED-EXISTING"
        assert AG_MODEL_REGISTRY["E08"].output_binding == "none"
        assert research_only_models() == ("E11-AG",)
        assert AG_MODEL_REGISTRY["E11-AG"].output_binding == "none"

    def test_gate_enrichment_is_limited_to_gates_7_to_10(self):
        enrich = {m.key: m.gate_enrichment for m in AG_MODEL_REGISTRY.values()
                  if m.gate_enrichment}
        assert enrich == {"E04-AG": (9,), "E12-AG": (8,)}
        with pytest.raises(ValueError, match="AG_GATE_QX"):
            m = AG_MODEL_REGISTRY["E04-AG"]
            object.__setattr__(m, "gate_enrichment", (11,))
            m.__post_init__()

    def test_no_new_gate_or_veto_is_created(self):
        from apex.setup.gates import GATE_COUNT
        from apex.risk.kernel import VETO_COUNT
        assert GATE_COUNT == 13 and VETO_COUNT == 14
        assert "14 hard vetoes" in RED_LINE and "exit precedence" in RED_LINE

    def test_incomplete_or_illegal_model_fails_closed(self):
        with pytest.raises(ValueError, match="AG_BINDING_QX"):
            AGModel(key="X-AG", engine="E01", definition="d",
                    formula_sketch="f", input_features=("i",),
                    output_binding="s_i", parameter_governance="g",
                    status="OBLIGATION", verification_battery="v")
        with pytest.raises(ValueError, match="AG_MODEL_INCOMPLETE_QX"):
            AGModel(key="X-AG", engine="E01", definition="",
                    formula_sketch="f", input_features=("i",),
                    output_binding="q_i", parameter_governance="g",
                    status="OBLIGATION", verification_battery="v")
        with pytest.raises(ValueError, match="AG_STATUS_QX"):
            AGModel(key="X-AG", engine="E01", definition="d",
                    formula_sketch="f", input_features=("i",),
                    output_binding="q_i", parameter_governance="g",
                    status="SHIPPED", verification_battery="v")

    def test_registry_summary_matches_the_registry(self):
        assert len(AG_REGISTRY_SUMMARY) == len(AG_MODEL_REGISTRY) == 12
        by_key = {k: m for k, m in AG_MODEL_REGISTRY.items()}
        for key, _binding, status in AG_REGISTRY_SUMMARY:
            assert key in by_key
            assert status.startswith(by_key[key].status.split(" ")[0])
