"""CP-6 battery — the thirteen hard gates, each individually tested on its
±1-unit boundary (Ch.10 §10.1). Mission item: "gates.py — all 13 gates
individually testable with ±1-unit boundaries".

Convention (recorded in params/setup_weights_v1.yaml):
* score gates (1, 2, 3, 4, 7, 12) — the unit is ``gate_score_unit`` = 0.01;
* quality-class gates (8, 9) — one Q-class = one unit;
* enum gates (5, 6) and structural gates (11, 13) have no numeric scale, so
  their boundary is the state/package itself (both sides are still exercised).
"""

from __future__ import annotations

import pytest

from apex.config import load_params
from apex.setup.gates import (
    GATE_COUNT,
    GATE_NAMES,
    GATES,
    QUARANTINE,
    evaluate,
    gate10_forecast_quality,
    gate11_snapshot_lineage,
    gate12_q_forecast,
    gate13_parameter_package,
    gate1_final_score,
    gate2_window_quality,
    gate3_conflict_penalty,
    gate4_redundancy_penalty,
    gate5_mtf_conflicting,
    gate6_mtf_sufficient,
    gate7_regime_quality,
    gate8_temporal_window_quality,
    gate9_volatility_quality,
    gate_thresholds,
    quality_min_class,
    run_all,
    score_unit,
)
from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import sha256_hex

UNIT = 0.01


def approx(v):
    return pytest.approx(v, abs=1e-12)


class TestGateMatrixShape:
    def test_exactly_thirteen_gates(self):
        assert GATE_COUNT == 13
        assert sorted(GATES) == list(range(1, 14))
        assert len(GATE_NAMES) == 13
        assert GATE_NAMES[10] == "SNAPSHOT_LINEAGE_INTEGRITY"

    def test_score_unit_is_the_documented_quantum(self):
        assert score_unit() == UNIT
        assert quality_min_class() == 2
        assert gate_thresholds()["gate1_q_min_setup"] == 0.55
        assert gate_thresholds()["gate3_conflict_penalty_max"] == 0.5
        assert gate_thresholds()["gate4_redundancy_penalty_max"] == 0.3
        assert gate_thresholds()["gate7_entropy_max"] == 0.85
        assert gate_thresholds()["gate12_q_forecast_min"] == 0.5

    def test_unknown_gate_number_fails_closed(self):
        with pytest.raises(ValueError, match="GATE_NUMBER_QX"):
            evaluate(14, 0.9)
        with pytest.raises(ValueError, match="GATE_NUMBER_QX"):
            evaluate(0, 0.9)

    def test_evaluate_dispatches_by_number(self):
        assert evaluate(1, 0.55).passed is True
        assert evaluate(3, 0.51).passed is False


class TestBoundaryOneUnit:
    def test_gate1_final_score(self):
        thr = 0.55
        assert gate1_final_score(thr + UNIT).passed is True
        assert gate1_final_score(thr).passed is True          # `<` fails
        assert gate1_final_score(thr - UNIT).passed is False
        assert gate1_final_score(thr - UNIT).reason == "GATE1_BELOW_Q_MIN_SETUP"
        # the only lawful action of a failing gate is the QUARANTINED block
        d = gate1_final_score(thr - UNIT).to_dict()
        assert d["action"] == QUARANTINE
        assert gate1_final_score(thr).to_dict()["action"] is None

    def test_gate2_window_quality_min_veto(self):
        # one quarantined candle in the window blocks the whole window
        # D59: the 1h governed threshold is 0.5 (same number as the old default).
        # The call must name the timeframe; there is no gate2_q_thr_default.
        ok = gate2_window_quality([(0.60, 0.0), (0.55, 1.0)], q_thr=0.5)
        bad = gate2_window_quality([(0.60, 0.0), (0.49, 1.0)], q_thr=0.5)
        assert ok.passed is True and ok.measured > 0.5
        assert bad.passed is False
        assert bad.reason == "GATE2_INVALID_MIN_Q_THR"
        assert gate2_window_quality([], q_thr=0.5).reason == "GATE2_INVALID_EMPTY"

    def test_gate3_conflict_penalty(self):
        assert gate3_conflict_penalty(0.5 + UNIT).passed is False
        assert gate3_conflict_penalty(0.5).passed is True     # `> 0.5` blocks
        assert gate3_conflict_penalty(0.4).passed is True     # frozen value

    def test_gate4_redundancy_penalty(self):
        assert gate4_redundancy_penalty(0.3 + UNIT).passed is False
        assert gate4_redundancy_penalty(0.3).passed is True   # frozen 0.3
        assert gate4_redundancy_penalty(0.31).passed is False

    def test_gate5_mtf_conflicting_boundary(self):
        assert gate5_mtf_conflicting("CONFLICTING").passed is False
        assert gate5_mtf_conflicting("PARTIALLY_ALIGNED").passed is True
        assert gate5_mtf_conflicting("STALE").passed is True  # evidence, not veto
        with pytest.raises(ValueError, match="GATE_MTF_STATE_QX"):
            gate5_mtf_conflicting("SOMEWHAT_ALIGNED")

    def test_gate6_mtf_insufficient_and_vacuous_pass(self):
        assert gate6_mtf_sufficient("INSUFFICIENT").passed is False
        # Ch.10 §10.1: with NO coarser TF at all the requirement is a
        # documented vacuous pass (the 1mo cell has no coarser timeframe).
        assert gate6_mtf_sufficient("INSUFFICIENT",
                                    has_coarser_bars=False).passed is True
        assert gate6_mtf_sufficient("INSUFFICIENT",
                                    has_coarser_bars=False).reason == \
            "GATE6_VACUOUS_NO_COARSER_TF"
        assert gate6_mtf_sufficient("ALIGNED").passed is True

    def test_gate7_regime_entropy_boundary(self):
        assert gate7_regime_quality(0.85).passed is True       # `> 0.85` fails
        assert gate7_regime_quality(0.85 + UNIT).passed is False
        assert gate7_regime_quality(0.84).passed is True
        assert gate7_regime_quality(0.65).passed is True       # E11 θ_H ≠ gate

    def test_gate8_and_9_quality_class_one_unit_apart(self):
        assert gate8_temporal_window_quality("Q2").passed is True
        assert gate8_temporal_window_quality("Q1").passed is False
        assert gate8_temporal_window_quality("QX").passed is False
        assert gate8_temporal_window_quality(None).passed is False
        assert gate9_volatility_quality("Q5").passed is True
        assert gate9_volatility_quality("Q2").passed is True
        assert gate9_volatility_quality("Q1").passed is False
        with pytest.raises(ValueError, match="GATE_QUALITY_CLASS_QX"):
            gate9_volatility_quality("Q9")

    def test_gate10_forecast_quality(self):
        assert gate10_forecast_quality({"quality": "Q2"}).passed is True
        assert gate10_forecast_quality({"quality": "Q1"}).passed is False
        assert gate10_forecast_quality({}).reason == \
            "GATE10_FORECAST_QUALITY_MISSING"
        # Ch.13 §13.1: the constant-0.5 bootstrap prior runs in RESEARCH/PAPER
        # only; for LIVE capital gate 10 fails until a package exists.
        assert gate10_forecast_quality({"quality": "Q5",
                                        "bootstrap_prior": True},
                                       environment="PAPER").passed is True
        assert gate10_forecast_quality({"quality": "Q5",
                                        "bootstrap_prior": True},
                                       environment="RESEARCH").passed is True
        live = gate10_forecast_quality({"quality": "Q5", "bootstrap_prior": True},
                                       environment="LIVE")
        assert live.passed is False
        assert live.reason == "GATE10_BOOTSTRAP_PRIOR_NOT_LIVE_ELIGIBLE"

    def test_gate12_q_forecast_boundary(self):
        assert gate12_q_forecast(0.5).passed is True
        assert gate12_q_forecast(0.5 - UNIT).passed is False
        assert gate12_q_forecast(0.5 + UNIT).passed is True
        assert gate12_q_forecast(None).passed is False
        assert gate12_q_forecast(None).reason == "GATE12_Q_FORECAST_UNAVAILABLE"
        assert gate12_q_forecast(float("nan")).passed is False

    def test_gate13_parameter_package(self):
        # D59 د۳: metrics are mandatory. A self-declared q_param is ignored.
        good = {"package_version": 7, "parameter_package_id": "pkg-7",
                "rolling_calibration_error": 0.05, "brier": 0.20,
                "log_loss": 0.69}
        assert gate13_parameter_package(good, environment="PAPER").passed is True
        assert gate13_parameter_package(good, environment="PAPER").reason == \
            "PACKAGE_VALID"
        assert gate13_parameter_package(None).passed is False
        assert gate13_parameter_package({}).passed is False
        assert gate13_parameter_package({"package_version": 1}).reason == \
            "GATE13_PACKAGE_UNVERSIONED"
        degraded = dict(good, rolling_calibration_error=1.0, brier=1.0,
                        log_loss=2.0)
        assert gate13_parameter_package(degraded).reason == \
            "GATE13_PACKAGE_DEGRADED"
        declared = {"package_version": 7, "parameter_package_id": "pkg-7",
                    "q_param": 0.4}
        assert gate13_parameter_package(declared).reason == \
            "GATE13_METRICS_MISSING"


class TestGate11IntegrityOnly:
    """Gate 11 = snapshot/lineage integrity ONLY (AJ.10 / GC-D8): it is not a
    catch-all for the other twelve, and nothing else may hide behind it."""

    def test_matching_snapshot_passes(self):
        payload = {"a": 1, "b": [1, 2, 3]}
        snap = sha256_hex(canonical_json(payload))
        res = gate11_snapshot_lineage(snap, payload, ["obs-1", "obs-2"])
        assert res.passed is True
        assert res.reason == "SNAPSHOT_LINEAGE_INTACT"

    def test_tampered_snapshot_fails(self):
        payload = {"a": 1, "b": [1, 2, 3]}
        res = gate11_snapshot_lineage("0" * 64, payload, ["obs-1"])
        assert res.passed is False
        assert res.reason == "GATE11_SNAPSHOT_HASH_MISMATCH"

    def test_malformed_snapshot_id_fails(self):
        res = gate11_snapshot_lineage("not-a-hash", {"a": 1}, ["obs-1"])
        assert res.reason == "GATE11_SNAPSHOT_ID_MALFORMED"

    def test_empty_lineage_fails(self):
        payload = {"a": 1}
        res = gate11_snapshot_lineage(sha256_hex(canonical_json(payload)),
                                      payload, [])
        assert res.reason == "GATE11_LINEAGE_EMPTY"

    def test_unresolvable_lineage_token_fails(self):
        payload = {"a": 1}
        res = gate11_snapshot_lineage(sha256_hex(canonical_json(payload)),
                                      payload, ["made-up-identifier"])
        assert res.reason == "GATE11_LINEAGE_UNRESOLVED"

    def test_non_canonicalizable_payload_fails_closed(self):
        res = gate11_snapshot_lineage("0" * 64, {"a": float("nan")}, ["obs-1"])
        assert res.passed is False
        assert res.reason.startswith("GATE11_SNAPSHOT_UNHASHABLE")

    def test_fabric_hash_mismatch_fails(self):
        payload = {"a": 1}
        res = gate11_snapshot_lineage(sha256_hex(canonical_json(payload)),
                                      payload, ["obs-1"], fabric_hash="f" * 64)
        assert res.reason == "GATE11_FABRIC_HASH_MISMATCH"

    def test_gate11_is_not_a_proxy_for_the_other_twelve(self):
        # a perfect-integrity snapshot still fails its own gate when the score
        # is low: integrity never rescues a blocked setup, and a bad snapshot
        # is never excused by a good score.
        payload = {"a": 1}
        snap = sha256_hex(canonical_json(payload))
        assert gate11_snapshot_lineage(snap, payload, ["obs-1"]).passed is True
        assert gate1_final_score(0.10).passed is False
        assert gate1_final_score(0.90).passed is True
        assert gate11_snapshot_lineage("e" * 64, payload, ["obs-1"]).passed is False


class TestRunAll:
    def ctx(self, **over):
        base = {
            "final_score": 0.60,
            "window_qualities": [(0.9, 0.0), (0.8, 1.0)],
            "conflict_penalty": 0.0, "redundancy_penalty": 0.0,
            "mtf_state": "ALIGNED", "has_coarser_bars": True, "h_norm": 0.4,
            "temporal_quality": "Q3", "volatility_quality": "Q2",
            "forecast": {"quality": "Q3"},
            "snapshot_id": "0" * 64, "payload": None, "lineage": ["obs-1"],
            "q_forecast": 0.6, "package": {
                "package_version": 1, "parameter_package_id": "p1",
                "calibration": "BOOTSTRAP_UNCALIBRATED"},
            "timeframe": "1h", "environment": "PAPER",
        }
        base.update(over)
        if base["payload"] is None:
            payload = {"x": 1}
            base["payload"] = payload
            base["snapshot_id"] = sha256_hex(canonical_json(payload))
        return base

    def test_all_thirteen_pass_emits_eligible(self):
        res = run_all(self.ctx())
        assert res["all_pass"] is True and res["blocked_by"] == []
        assert res["action"] == "ELIGIBLE"
        assert set(res["results"]) == set(range(1, 14))

    def test_single_gate_failure_blocks_and_names_it(self):
        res = run_all(self.ctx(final_score=0.54))
        assert res["all_pass"] is False
        assert res["blocked_by"] == [1]
        assert res["action"] == QUARANTINE

    def test_multiple_failures_are_all_reported(self):
        res = run_all(self.ctx(final_score=0.1, mtf_state="CONFLICTING",
                              q_forecast=0.2, temporal_quality="Q0"))
        assert res["blocked_by"] == [1, 5, 8, 12]
        assert len(res["reasons"]) == 4

    def test_gates_never_modify_the_inputs(self):
        ctx = self.ctx()
        before = {k: (dict(v) if isinstance(v, dict) else v)
                  for k, v in ctx.items()}
        run_all(ctx)
        assert {k: ctx[k] for k in before} == before

    def test_q_min_tf_is_reported_for_the_cell(self):
        res = run_all(self.ctx(timeframe="15m"))
        assert res["q_min_tf"] == load_params()["quality_weights"] \
            ["q_min_by_tf"]["15m"]

    def test_every_gate_is_reachable_through_the_registry(self):
        # the matrix requires one call path per gate (11 and 13 need arity)
        res = run_all(self.ctx())
        for n in range(1, GATE_COUNT + 1):
            assert res["results"][n]["gate"] == n
            assert res["results"][n]["name"] == GATE_NAMES[n - 1]
