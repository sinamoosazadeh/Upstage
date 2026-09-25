"""CP-6 battery — Context Fabric, the combiner, and the Conflict policy
package (Ch.8 §8.0/§8.1/§8.2/§8.3; SL-2/SL-7/SL-8/SL-11 per ADR-P2-011).

Includes the mission-required **vacuous-pass** test: the combiner must NOT
report a pass on a deliberately empty evidence set, and the test proves that
the unguarded formula would have (i.e. the assertion has teeth).
"""

from __future__ import annotations

import math

import pytest

from apex.fabric.conflict import (
    CONFLICT_OUTPUTS,
    CONSENSUS,
    GATE3_CONFLICT_THRESHOLD,
    GATE4_REDUNDANCY_THRESHOLD,
    HARD_CONFLICT,
    INSUFFICIENT_EVIDENCE,
    MATERIAL_CONFLICT,
    SEVEN_INVARIANTS,
    SMTRecord,
    CorrelationRecord,
    ConflictRecord,
    DivergenceRecord,
    assert_no_reversion_semantics,
    assert_permission_monotone,
    correlation_exposure,
    disagreement_of,
    gate_thresholds,
    monotone_ok,
    penalties,
    quality_asymmetry_of,
    resolve,
    stale_fraction_of,
)
from apex.fabric.context import (
    COMPONENT_ENGINE,
    CONTEXT_COMPONENTS_12,
    DEFAULT_COMBINER_WEIGHTS,
    MTF_STATE_SCORES,
    REDUNDANCY_HALVE_FACTOR,
    CombinerInputs,
    ContextRecord,
    apply_redundancy,
    band_of,
    build_context,
    conflict_multiplier,
    context_bands,
    context_confidence,
    context_decay_per_bar,
    context_weights,
    data_trust_floor,
    evidence_agreement,
    evidence_decay_per_bar,
    freshness_factor,
    mtf_agreement,
    normalized_context_weights,
    propagation_band,
    propagation_confirmatory_threshold,
    q_min_setup,
    q_min_tf,
    raw_setup_score,
    redundancy_penalty_value,
    redundancy_rho,
    redundancy_rho_threshold,
    setup_score,
    solvency_check,
)
from apex.fabric.evidence import EvidenceFabric, FabricEvidenceRef, expiry_age_bars
from apex.config import load_params

TF = "1h"


def ref(eid, engine, direction=1, quality=0.9, age=0.0):
    return FabricEvidenceRef(
        evidence_id=eid, engine_id=engine, symbol="BTCUSDT", timeframe=TF,
        state="ACTIVE", direction=direction, quality=quality,
        resolution_class="Q3", age_bars=age, as_of=1000,
        snapshot_id="f" * 64, lineage=("obs-" + eid,))


def fabric(*refs, data_trust=0.98):
    return EvidenceFabric.assemble(symbol="BTCUSDT", timeframe=TF, as_of=1000,
                                   evidence=list(refs), data_trust=data_trust)


def ci(**kw):
    base = dict(data_trust=0.9, mtf_state="ALIGNED", evidence_agreement=1.0,
                regime_confidence=1.0, regime_uncertainty=0.0,
                divergence_magnitude=0.0, temporal_window_validity=1.0)
    base.update(kw)
    return CombinerInputs(**base)


# ---------------------------------------------------------------------------
# Frozen numbers (Ch.10 §10.1 L15236–15241) — asserted FROM THE PARAMS YAML
# ---------------------------------------------------------------------------

class TestFrozenNumbers:
    def test_twelve_weights_literal_from_yaml(self):
        assert load_params()["setup_weights"]["weights"] == {
            "w_structure": 0.16, "w_liquidity": 0.12, "w_volume": 0.10,
            "w_volatility": 0.08, "w_fvg": 0.12, "w_orderblock": 0.10,
            "w_rtm": 0.06, "w_wyckoff": 0.06, "w_trend": 0.08,
            "w_momentum": 0.06, "w_regime": 0.04, "w_temporal": 0.02}
        assert len(context_weights()) == 12
        assert set(context_weights()) == {n for n, _ in CONTEXT_COMPONENTS_12}

    def test_twelve_component_names_and_engine_binding(self):
        assert [n for n, _ in CONTEXT_COMPONENTS_12] == [
            "structure", "liquidity", "volume", "volatility", "fvg",
            "orderblock", "rtm", "wyckoff", "trend", "momentum", "regime",
            "temporal"]
        assert COMPONENT_ENGINE == {
            "structure": "E01", "liquidity": "E02", "volume": "E03",
            "volatility": "E04", "fvg": "E05", "orderblock": "E06",
            "rtm": "E07", "wyckoff": "E08", "trend": "E09",
            "momentum": "E10", "regime": "E11", "temporal": "E12"}

    def test_weights_sum_to_one_and_are_not_renormalized_away(self):
        assert math.isclose(sum(context_weights().values()), 1.0)
        assert normalized_context_weights() == context_weights()

    def test_q_min_setup_is_055(self):
        assert q_min_setup() == 0.55

    def test_decay_numbers_005_and_002(self):
        assert context_decay_per_bar() == 0.05
        assert evidence_decay_per_bar() == 0.02
        # The Q-window λ of §2.1 stays 0.1 (the decays do not replace it).
        assert load_params()["quality_weights"]["q_window_lambda"] == 0.1

    def test_band_grid_numbers_070_050_030(self):
        assert context_bands() == (0.70, 0.50, 0.30)
        assert propagation_confirmatory_threshold() == 0.40   # Ch.8 §8.0 table
        assert data_trust_floor() == 0.30

    def test_conflict_multiplier_is_060_and_redundancy_halve_is_050(self):
        assert conflict_multiplier() == pytest.approx(0.6)     # ×0.6 (1−0.4)
        assert REDUNDANCY_HALVE_FACTOR == 0.50                  # ρ>0.85 → 0.50×
        assert redundancy_rho_threshold() == 0.85
        assert redundancy_penalty_value() == 0.3
        assert load_params()["setup_weights"]["conflict_penalty"] == 0.4


# ---------------------------------------------------------------------------
# context_confidence combiner (Ch.8 §8.0)
# ---------------------------------------------------------------------------

class TestCombiner:
    def test_l1_default_weights_are_the_documented_ones(self):
        assert DEFAULT_COMBINER_WEIGHTS == {
            "data_trust": 0.35, "mtf_agreement": 0.20,
            "evidence_agreement": 0.15, "regime_confidence": 0.15,
            "one_minus_regime_uncertainty": 0.10,
            "one_minus_divergence_magnitude": 0.05,
            "temporal_window_validity": 0.0}
        # Σ of the six documented governed weights is 1.0 exactly.
        assert math.isclose(sum(v for k, v in DEFAULT_COMBINER_WEIGHTS.items()
                                if k != "temporal_window_validity"), 1.0)

    def test_sigmoid_of_weighted_sum(self):
        inp = ci(data_trust=1.0, evidence_agreement=1.0, regime_confidence=1.0)
        res = context_confidence(inp, timeframe=TF, q_raw=1.0)
        z = 0.35 + 0.20 + 0.15 + 0.15 + 0.10 + 0.05
        assert math.isclose(res["z"], z)
        from apex.decision.pipeline import load_decision_v1
        gain = load_decision_v1()["context_confidence_gain"]
        assert math.isclose(res["context_confidence"],
                            1 / (1 + math.exp(-gain * (z - 0.5))))

    def test_bounds_never_exceed_half_to_one(self):
        hi = context_confidence(ci(), timeframe=TF, q_raw=1.0)
        lo = context_confidence(ci(data_trust=0.3, mtf_state="STALE",
                                   evidence_agreement=0.0,
                                   regime_confidence=0.0, regime_uncertainty=1.0,
                                   divergence_magnitude=1.0,
                                   temporal_window_validity=0.0),
                               timeframe=TF, q_raw=1.0)
        # D59 ج۴: the low end is no longer trapped above 0.5, so the band grid
        # is reachable. Order is preserved.
        assert 0.0 < lo["context_confidence"] < hi["context_confidence"] < 1.0
        assert lo["context_confidence"] < 0.5 < hi["context_confidence"]

    def test_mtf_agreement_table_verbatim(self):
        assert MTF_STATE_SCORES == {
            "ALIGNED": 1.0, "PARTIALLY_ALIGNED": 0.6, "STALE": 0.3,
            "CONFLICTING": 0.0, "UNAVAILABLE": 0.0, "INSUFFICIENT": 0.0}
        for state, val in MTF_STATE_SCORES.items():
            assert mtf_agreement(state) == val
        with pytest.raises(ValueError, match="MTF_STATE_QX"):
            mtf_agreement("MOSTLY_ALIGNED")

    def test_solvency_rule_collapses_to_zero_data_trust(self):
        ok, reason = solvency_check(data_trust=0.2999, q_raw=1.0, timeframe=TF)
        assert (ok, reason) == (False, "SOLVENCY_DATA_TRUST")
        r = context_confidence(ci(data_trust=0.2999), timeframe=TF)
        assert r["context_confidence"] == 0.0
        assert r["band"] == "COLLAPSED"

    def test_solvency_rule_data_trust_boundary_inclusive(self):
        ok, _ = solvency_check(data_trust=0.30, q_raw=1.0, timeframe=TF)
        assert ok is True          # rule is `data_trust < 0.30`

    def test_solvency_rule_q_min_per_timeframe_boundaries(self):
        # Q_min(1h) = 0.50 (frozen §2.1 table); < ⇒ collapse, == ⇒ fine.
        assert q_min_tf("1h") == 0.50
        assert solvency_check(data_trust=1.0, q_raw=0.49, timeframe="1h")[0] is False
        assert solvency_check(data_trust=1.0, q_raw=0.50, timeframe="1h")[0] is True
        # every frozen TF has its own Q_min (140-cell universality)
        for tf, qmin in load_params()["quality_weights"]["q_min_by_tf"].items():
            assert solvency_check(data_trust=1.0, q_raw=qmin - 0.01,
                                  timeframe=tf)[0] is False
            assert solvency_check(data_trust=1.0, q_raw=qmin,
                                  timeframe=tf)[0] is True
        with pytest.raises(ValueError, match="E-VAL-022"):
            q_min_tf("2d")

    def test_q_raw_absent_is_not_zero_substituted(self):
        # SL-14: QX is never replaced by zero or a guess. An absent Q_raw does
        # not silently fail the solvency floor either — there is no value to
        # compare, so no collapse is *fabricated* and no credit is given.
        ok, reason = solvency_check(data_trust=0.9, q_raw=None, timeframe=TF)
        assert (ok, reason) == (True, "OK")
        r = context_confidence(ci(data_trust=0.9), timeframe=TF, q_raw=None)
        assert 0.0 < r["context_confidence"] < 1.0     # not zero-substituted
        # and an empty evidence set never fabricates the solvency value:
        assert solvency_check(data_trust=0.0, q_raw=None, timeframe=TF)[0] is False

    def test_propagation_thresholds(self):
        # the low-data_trust arm of the third row is unconditional
        assert propagation_band(0.9, 0.299) == "COLLAPSED_DATA_TRUST"
        assert propagation_band(0.70, 0.9) == "ADMISSIBLE_TO_FORECAST_DECISION"
        assert propagation_band(0.699, 0.9) == "CONFIRMATORY_ONLY"
        assert propagation_band(0.40, 0.9) == "CONFIRMATORY_ONLY"
        assert propagation_band(0.399, 0.9) == "COLLAPSED"

    def test_band_grid_classification_boundaries_inclusive(self):
        assert band_of(0.70) == "ADMISSIBLE"
        assert band_of(0.699) == "CONFIRMATORY"
        assert band_of(0.50) == "CONFIRMATORY"
        assert band_of(0.499) == "WEAK"
        assert band_of(0.30) == "WEAK"
        assert band_of(0.299) == "COLLAPSED"
        with pytest.raises(ValueError, match="CONTEXT_BAND_INPUT_QX"):
            band_of(1.5)

    def test_unknown_weight_name_fails_closed(self):
        with pytest.raises(ValueError, match="COMBINER_WEIGHT_KEY_QX"):
            ci(weights={**DEFAULT_COMBINER_WEIGHTS, "vibes": 0.5})

    def test_out_of_range_input_fails_closed(self):
        with pytest.raises(ValueError, match="COMBINER_INPUT_QX"):
            ci(divergence_magnitude=1.4)


class TestAgreement:
    def test_empty_membership_is_not_agreement(self):
        assert evidence_agreement([]) == 0.0

    def test_single_engine_full_agreement(self):
        assert evidence_agreement([ref("a", "E01")]) == 1.0

    def test_opposing_group_member_reduces_agreement_by_weight_share(self):
        alone = evidence_agreement([ref("a", "E01")])
        with_opposition = evidence_agreement([ref("a", "E01", 1),
                                             ref("b", "E09", -1)])
        assert with_opposition < alone
        # E01(0.16) vs E09(0.08) same group: dominant = E01; disagreement
        # share = 0.08/(0.16+0.08) = 1/3 ⇒ agreement = 2/3.
        assert math.isclose(with_opposition, 1 - 0.08 / 0.24, rel_tol=1e-12)

    def test_direction_zero_never_opposes(self):
        v = evidence_agreement([ref("a", "E01", 1), ref("b", "E09", 0)])
        assert math.isclose(v, 1.0)

    def test_cross_group_opposition_is_not_group_disagreement(self):
        # E01 (structure) vs E02 (liquidity): different dependency groups ⇒
        # no intra-group disagreement; the two are both dominant in their own
        # group (single member) so each agrees with itself.
        assert math.isclose(evidence_agreement([ref("a", "E01", 1),
                                                ref("b", "E02", -1)]), 1.0)


# ---------------------------------------------------------------------------
# Context Fabric record
# ---------------------------------------------------------------------------

class TestContextRecord:
    def test_schema_keys_are_exactly_the_frozen_json(self):
        assert set(ContextRecord.keys()) == {
            "market_regime", "mtf_state", "utc_window_state", "is_overlap",
            "correlation_state", "divergence_state", "liquidity_state",
            "volatility_state", "structure_state", "portfolio_context",
            "data_trust", "conflict_state", "context_confidence", "as_of"}

    def test_build_context_recomputes_and_round_trips(self):
        fab = fabric(ref("a", "E01"), ref("b", "E05"))
        out = build_context(fab, market_regime="TREND_EXPANSION",
                            mtf_state="ALIGNED", utc_window_state="UTC_W2",
                            is_overlap=True, volatility_state="ELEVATED",
                            structure_state="BULL", regime_confidence=0.8,
                            regime_uncertainty=0.2, divergence_magnitude=0.1,
                            temporal_window_validity=1.0, q_raw=0.9)
        rec = ContextRecord.from_dict(out["context"])
        assert rec.conflict_state == "NONE"
        assert rec.context_confidence == out["context_confidence"]
        # a caller cannot inject a confidence: it is always recomputed
        assert rec.context_confidence != 0.0
        with pytest.raises(ValueError, match="CONTEXT_SCHEMA_QX"):
            ContextRecord.from_dict({"market_regime": "X"})

    def test_determinism_same_input_same_hash_and_confidence(self):
        kw = dict(market_regime="TREND_EXPANSION", mtf_state="ALIGNED",
                  utc_window_state="UTC_W1", is_overlap=False,
                  volatility_state="NORMAL", structure_state="BULL",
                  regime_confidence=0.7, regime_uncertainty=0.3,
                  divergence_magnitude=0.0, temporal_window_validity=1.0,
                  q_raw=0.8)
        a = build_context(fabric(ref("a", "E01")), **kw)
        b = build_context(fabric(ref("a", "E01")), **kw)
        assert a["context"] == b["context"]
        assert a["context_confidence"] == b["context_confidence"]
        assert a["weights_normalized"] == b["weights_normalized"]


# ---------------------------------------------------------------------------
# Setup-score combiner + the vacuous-pass guard
# ---------------------------------------------------------------------------

class TestSetupScoreAndVacuousPass:
    def test_formula_is_weight_times_s_times_q_times_f(self):
        fab = fabric(ref("a", "E01"), ref("b", "E05"))
        r = setup_score(fab, s_i={"structure": 1.0, "fvg": 1.0},
                        q_i={"structure": 0.9, "fvg": 0.5},
                        f_i={"structure": 1.0, "fvg": 1.0})
        assert math.isclose(r["final"], 0.16 * 0.9 + 0.12 * 0.5)

    def test_absent_components_contribute_nothing(self):
        fab = fabric(ref("a", "E01"))
        r = setup_score(fab, s_i={"structure": 1.0}, q_i={"structure": 1.0})
        assert math.isclose(r["raw"], 0.16)
        assert r["final"] < q_min_setup()      # one engine ≠ a setup

    def test_unscored_engine_in_fabric_contributes_nothing(self):
        """CP-6 integration regression: real E08 (wyckoff) evidence may sit
        in the fabric while the setup layer scores no wyckoff term. That
        component contributes NOTHING — it never raises KeyError and never
        gains a fabricated zero-weighted term (the raw_setup_score law)."""
        fab = fabric(ref("a", "E01"), ref("b", "E08"))
        r = setup_score(fab, s_i={"structure": 1.0}, q_i={"structure": 1.0})
        assert math.isclose(r["raw"], 0.16)
        assert "wyckoff" not in r["terms"]
        assert r["vacuous"] is False and r["reason"] == "OK"
        with_s_i = setup_score(fab, s_i={"structure": 1.0, "wyckoff": 1.0},
                                q_i={"structure": 1.0, "wyckoff": 1.0})
        assert math.isclose(with_s_i["raw"], 0.16 + with_s_i["terms"]["wyckoff"])

    def test_vacuous_pass_EMPTY_EVIDENCE_FAILS(self):
        """Mission item: a deliberately empty evidence set must NOT pass.

        The fail-closed reading of "final score < Q_min ⇒ QUARANTINED BLOCK"
        (Gate 1) plus the solvency/monotonicity law: an empty set scores 0.0,
        reports zero agreement, and the conflict package reads it as total
        disagreement (HARD_CONFLICT) — never as consensus.
        """
        empty = fabric()
        assert empty.is_empty()
        r = setup_score(empty, s_i={}, q_i={})
        assert r["raw"] == 0.0 and r["final"] == 0.0
        assert r["vacuous"] is True
        assert r["reason"] == "VACUOUS_NO_EVIDENCE"
        assert r["final"] < q_min_setup()          # ⇒ Gate 1 quarantines
        assert evidence_agreement([]) == 0.0        # no phantom agreement
        assert disagreement_of([]) == 1.0           # total disagreement, not 0
        out = resolve(disagreement=disagreement_of([]), data_trust=0.9,
                      q_raw=0.9, timeframe=TF)
        assert out["output"] == HARD_CONFLICT       # nothing to agree with

    def test_the_guard_is_what_makes_it_fail(self):
        """The assertion has teeth: the unguarded Σ over the full weight set
        (i.e. treating "no evidence" as "every component present") would score
        1.0 and pass Gate 1 — the guard is what prevents that."""
        unguarded = sum(context_weights().values())     # Σ w_i·1·1·1
        assert unguarded == pytest.approx(1.0)
        assert unguarded >= q_min_setup()                # would have passed
        guarded = setup_score(fabric(), s_i={}, q_i={})["final"]
        assert guarded < q_min_setup()                   # actually quarantined

    def test_components_are_only_the_twelve(self):
        fab = fabric(ref("a", "E01"))
        with pytest.raises(ValueError, match="SETUP_COMPONENT_QX"):
            raw_setup_score({"sentiment": 1.0}, q_i={"sentiment": 1.0})

    def test_missing_quality_fails_closed(self):
        with pytest.raises(ValueError, match="SETUP_FACTOR_QX"):
            raw_setup_score({"structure": 1.0}, q_i={})

    def test_factor_domain_is_zero_one(self):
        with pytest.raises(ValueError, match="SETUP_FACTOR_QX"):
            raw_setup_score({"structure": 1.7}, q_i={"structure": 1.0})

    def test_required_conflict_multiplies_by_06(self):
        fab = fabric(ref("a", "E01"), ref("b", "E05"))
        plain = setup_score(fab, s_i={"structure": 1.0, "fvg": 1.0},
                            q_i={"structure": 1.0, "fvg": 1.0})
        conflicted = setup_score(fab, s_i={"structure": 1.0, "fvg": 1.0},
                                 q_i={"structure": 1.0, "fvg": 1.0},
                                 required_conflict=True)
        assert math.isclose(conflicted["final"], plain["final"] * 0.6)

    def test_optional_conflict_only_adds_a_penalty(self):
        fab = fabric(ref("a", "E01"))
        base = setup_score(fab, s_i={"structure": 1.0}, q_i={"structure": 1.0})
        opt = setup_score(fab, s_i={"structure": 1.0}, q_i={"structure": 1.0},
                          optional_conflict_penalty=0.05)
        assert base["conflict_multiplier"] == 1.0
        assert math.isclose(opt["final"], base["final"] - 0.05)

    def test_redundancy_window_is_48_points(self):
        a = [float(i % 7) for i in range(60)]
        b = [x * 2.0 + 1.0 for x in a]
        r = redundancy_rho(a, b)
        assert r["points"] == 48 and math.isclose(r["rho"], 1.0)

    def test_redundancy_below_20_points_skips(self):
        r = redundancy_rho([1.0, 2.0, 3.0], [2.0, 4.0, 6.0])
        assert r["skipped"] is True and r["rho"] is None
        assert r["reason"] == "REDUNDANCY_INSUFFICIENT_POINTS"

    def test_redundancy_boundary_085_is_strictly_above(self):
        assert redundancy_rho_threshold() == 0.85
        terms = {"structure": 0.16, "fvg": 0.12}
        qual = {"structure": 0.9, "fvg": 0.5}
        assert apply_redundancy(terms, qual, 0.85)["victim"] is None
        halved = apply_redundancy(terms, qual, 0.851)
        assert halved["victim"] == "fvg"                    # lower Q dropped
        assert math.isclose(halved["terms"]["fvg"], 0.12 * 0.50)
        assert math.isclose(halved["terms"]["structure"], 0.16)

    def test_redundancy_tie_keeps_the_higher_engine_id(self):
        terms = {"structure": 0.16, "liquidity": 0.12}
        qual = {"structure": 0.7, "liquidity": 0.7}      # E01 vs E02, tie
        res = apply_redundancy(terms, qual, 0.99)
        assert res["victim"] == "structure"               # E01 dropped (E02 kept)

    def test_freshness_factor_uses_the_governed_evidence_decay(self):
        assert freshness_factor(0.0) == 1.0
        assert math.isclose(freshness_factor(50.0), math.exp(-0.02 * 50))


# ---------------------------------------------------------------------------
# Conflict policy package (Ch.8 §8.1) — T_CONFLICT
# ---------------------------------------------------------------------------

class TestConflictResolution:
    def test_exactly_four_structured_outputs(self):
        assert CONFLICT_OUTPUTS == ("CONSENSUS", "MATERIAL_CONFLICT",
                                    "HARD_CONFLICT", "INSUFFICIENT_EVIDENCE")
        assert len(set(CONFLICT_OUTPUTS)) == 4

    def test_terminal_mapping_boundaries(self):
        # disagreement ≥ 0.60 → HARD (inclusive), 0.35 ≤ d < 0.60 → MATERIAL
        assert resolve(disagreement=0.60, data_trust=0.9, q_raw=0.9,
                       timeframe=TF)["output"] == HARD_CONFLICT
        assert resolve(disagreement=0.599, data_trust=0.9, q_raw=0.9,
                       timeframe=TF)["output"] == MATERIAL_CONFLICT
        assert resolve(disagreement=0.35, data_trust=0.9, q_raw=0.9,
                       timeframe=TF)["output"] == MATERIAL_CONFLICT
        assert resolve(disagreement=0.349, data_trust=0.9, q_raw=0.9,
                       timeframe=TF)["output"] == CONSENSUS
        # mtf CONFLICTING wins the first branch even at zero disagreement
        assert resolve(disagreement=0.0, data_trust=0.9, q_raw=0.9,
                       timeframe=TF,
                       mtf_conflict="CONFLICTING")["output"] == HARD_CONFLICT
        # low data trust / low Q_raw → INSUFFICIENT (before the CONSENSUS arm)
        assert resolve(disagreement=0.1, data_trust=0.29, q_raw=0.9,
                       timeframe=TF)["output"] == INSUFFICIENT_EVIDENCE
        assert resolve(disagreement=0.1, data_trust=0.9, q_raw=0.49,
                       timeframe=TF)["output"] == INSUFFICIENT_EVIDENCE

    def test_gate_projection_thresholds(self):
        assert GATE3_CONFLICT_THRESHOLD == 0.5      # conflict_penalty > 0.5
        assert GATE4_REDUNDANCY_THRESHOLD == 0.3    # redundancy_penalty > 0.3
        assert gate_thresholds() == {
            "gate3_conflict_penalty_max": 0.5,
            "gate4_redundancy_penalty_max": 0.3}
        r = resolve(disagreement=0.5, data_trust=0.9, q_raw=0.9, timeframe=TF)
        assert r["conflict_penalty"] == 0.4
        assert r["gate_projection"]["gate3_block"] is False   # 0.4 ≤ 0.5
        # the redundancy penalty is exactly 0.3 → `> 0.3` is False at the
        # frozen value (Gate 4 blocks only a strictly larger penalty).
        r2 = resolve(disagreement=0.5, data_trust=0.9, q_raw=0.9,
                     timeframe=TF, redundancy_rho=0.9)
        assert r2["redundancy_penalty"] == 0.3
        assert r2["gate_projection"]["gate4_block"] is False

    def test_penalties_are_produced_here_not_redefined(self):
        p = penalties(MATERIAL_CONFLICT, redundancy_rho=0.9)
        assert p == {"conflict_penalty": 0.4, "redundancy_penalty": 0.3}
        assert penalties(CONSENSUS, redundancy_rho=0.1) == {
            "conflict_penalty": 0.0, "redundancy_penalty": 0.0}

    def test_record_fields_are_exactly_the_frozen_list(self):
        out = resolve(disagreement=0.2, data_trust=0.9, q_raw=0.9, timeframe=TF)
        rec = out["record"]
        assert isinstance(rec, ConflictRecord)
        import dataclasses as _dc
        assert [f.name for f in _dc.fields(ConflictRecord)] == [
            "conflict_id", "disagreement", "quality_asymmetry", "redundancy",
            "uncertainty", "mtf_conflict", "stale_fraction", "regime_state",
            "action_policy", "package_id", "snapshot_id", "lineage"]

    def test_component_domain_fail_closed(self):
        with pytest.raises(ValueError, match="CONFLICT_COMPONENT_QX"):
            resolve(disagreement=1.2, data_trust=0.9, q_raw=0.9, timeframe=TF)
        with pytest.raises(ValueError, match="MTF_STATE_QX"):
            resolve(disagreement=0.1, data_trust=0.9, q_raw=0.9, timeframe=TF,
                    mtf_conflict="MAYBE")
        with pytest.raises(ValueError, match="E-VAL-022"):
            resolve(disagreement=0.1, data_trust=0.9, q_raw=0.9, timeframe="5s")

    def test_quality_asymmetry_and_stale_fraction(self):
        assert quality_asymmetry_of([0.9, 0.4, 0.7]) == pytest.approx(0.5)
        with pytest.raises(ValueError, match="CONFLICT_EMPTY_QUALITY_QX"):
            quality_asymmetry_of([])
        # stale = age ≥ expiry (5×TF bars for the member's own TF)
        assert stale_fraction_of([4.99, 5.0, 6.0], expiry_age_bars(TF)) \
            == pytest.approx(2 / 3)
        assert stale_fraction_of([], 3600.0) == 0.0


class TestTConflictMonotonicity:
    """T_CONFLICT: the four canonical scenarios + the monotonicity property —
    raising any uncertainty input never moves the output toward CONSENSUS."""

    @pytest.mark.parametrize("field,value,base_kw", [
        ("disagreement", 0.9, {"disagreement": 0.0}),
        ("stale_fraction", 1.0, {"disagreement": 0.4}),
        ("uncertainty", 1.0, {"disagreement": 0.4}),
        ("redundancy", 1.0, {"disagreement": 0.4}),
        ("quality_asymmetry", 1.0, {"disagreement": 0.4}),
    ])
    def test_raising_uncertainty_never_grants_consensus(self, field, value, base_kw):
        base = resolve(data_trust=0.9, q_raw=0.9, timeframe=TF,
                       **{**base_kw, field: 0.0})
        worse = resolve(data_trust=0.9, q_raw=0.9, timeframe=TF,
                        **{**base_kw, field: value})
        order = {CONSENSUS: 0, MATERIAL_CONFLICT: 1,
                 INSUFFICIENT_EVIDENCE: 2, HARD_CONFLICT: 3}
        assert order[worse["output"]] >= order[base["output"]]
        assert_permission_monotone(base, worse)
        if field == "disagreement":
            assert base["output"] == CONSENSUS and worse["output"] == HARD_CONFLICT
        else:
            assert base["output"] == MATERIAL_CONFLICT

    def test_monotonicity_assertion_catches_a_violation(self):
        with pytest.raises(Exception, match="I3 VIOLATION"):
            assert_permission_monotone({"output": HARD_CONFLICT},
                                       {"output": CONSENSUS})

    def test_monotone_ok_is_the_veto_nine_condition(self):
        assert monotone_ok(is_risk_increase=True, uncertainty_is_rising=False)
        assert monotone_ok(is_risk_increase=False, uncertainty_is_rising=True)
        assert not monotone_ok(is_risk_increase=True, uncertainty_is_rising=True)


class TestSevenInvariants:
    def test_all_seven_defined_and_quoted(self):
        assert list(SEVEN_INVARIANTS) == [f"I{i}" for i in range(1, 8)]
        assert "Non-permission by evidence" in SEVEN_INVARIANTS["I7"]
        assert "rising conflict/uncertainty never grants permission" in (
            SEVEN_INVARIANTS["I3"])   # verbatim table wording
        assert "byte-identical" in SEVEN_INVARIANTS["I2"]

    def test_i1_pit_is_enforced_by_the_fabric(self):
        # an input with as_of beyond the fabric as_of is excluded (see
        # test_fabric_evidence), i.e. I1 is executable, not decorative.
        fab = EvidenceFabric.assemble(symbol="BTCUSDT", timeframe=TF, as_of=5,
                                      evidence=[ref("a", "E01")],
                                      data_trust=0.9)
        assert fab.excluded and fab.excluded[0][1] == "E-PIT-001"

    def test_i7_conflict_never_grants_permission(self):
        out = resolve(disagreement=0.0, data_trust=1.0, q_raw=1.0,
                      timeframe=TF, redundancy_rho=0.9)
        # CONSENSUS is an evidence state, not an authorization: no permission
        # field exists on the record at all.
        assert out["output"] == CONSENSUS
        assert not any("permission" in f.name or "allow" in f.name
                       for f in __import__("dataclasses").fields(ConflictRecord))
        # redundancy is a *penalty*, produced here and projected by Gate 4 —
        # resolve() itself returns no authorization of any kind.
        assert out["redundancy_penalty"] == 0.3


class TestCrossSymbolLayer:
    def test_correlation_record_scope_enforced(self):
        rec = CorrelationRecord(symbol_pair=("BTCUSDT", "ETHUSDT"),
                                window="1h:100", sample_count=100,
                                estimate=0.42, confidence_interval=(0.2, 0.6),
                                regime_scope="TREND", last_update=1, quality=0.9)
        assert rec.estimate == 0.42
        with pytest.raises(ValueError, match="CORRELATION_SAMPLE_QX"):
            CorrelationRecord(symbol_pair=("A", "B"), window="w",
                              sample_count=0, estimate=0.1,
                              confidence_interval=(0.0, 0.2),
                              regime_scope="TREND", last_update=1, quality=0.5)
        with pytest.raises(ValueError, match="CORRELATION_SCOPE_QX"):
            CorrelationRecord(symbol_pair=("A", "B"), window="w",
                              sample_count=5, estimate=0.1,
                              confidence_interval=(0.0, 0.2),
                              regime_scope="", last_update=1, quality=0.5)
        with pytest.raises(ValueError, match="CORRELATION_ESTIMATE_QX"):
            CorrelationRecord(symbol_pair=("A", "B"), window="w",
                              sample_count=5, estimate=1.5,
                              confidence_interval=(0.0, 0.2),
                              regime_scope="TREND", last_update=1, quality=0.5)

    def test_divergence_record_stores_both_pivots(self):
        DivergenceRecord(pivot_a={"t": 1, "p": 100.0},
                         pivot_b={"t": 2, "p": 101.0}, relation="BEARISH")
        with pytest.raises(ValueError, match="DIVERGENCE_PIVOT_QX"):
            DivergenceRecord(pivot_a={"t": 1}, pivot_b={}, relation="X")

    def test_smt_record_has_no_reversion_semantics(self):
        rec = SMTRecord(asset_a_structure={"bos": "BULL"},
                        asset_b_structure={"bos": "BEAR"},
                        relative_structure_divergence=0.3)
        assert_no_reversion_semantics(rec)
        assert "must_revert" not in rec.to_dict()

    def test_correlation_exposure_cap_boundary(self):
        # cap 0.70 (governed): combined 100 · ρ 0.69 = 69 ≤ 70 ⇒ NONE
        ok = correlation_exposure(rho=0.69, open_notional=[50.0],
                                  proposed_notional=50.0)
        assert ok["action"] == "NONE"
        hit = correlation_exposure(rho=0.7, open_notional=[50.0],
                                   proposed_notional=50.0)
        assert hit["action"] == "NONE"          # exactly at the cap ⇒ allowed
        over = correlation_exposure(rho=0.71, open_notional=[50.0],
                                    proposed_notional=50.0)
        assert over["action"] == "REDUCE"
        assert over["reduced_combined_notional"] < 100.0
        with pytest.raises(ValueError, match="CORRELATION_RHO_QX"):
            correlation_exposure(rho=1.1, open_notional=[1.0],
                                 proposed_notional=1.0)
