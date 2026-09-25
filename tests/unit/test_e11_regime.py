"""E11 Regime — full §8 validation battery (APEX_GEN5.md L11671–12732)
+ AI.10 T-E11-K9 dimensionality proof (L18932) + params re-assertion
(params/e11_params_v4.yaml vs §9.5/§6, ADR-P2-008) + live-regime-gate
default-OFF (AI.2 L19046–19048).

Covers: §8.1 golden fixtures (18 cases, re-derived — doc inconsistencies
ISSUE-CP5-015/016/018 logged) · §3.1 norms A/B/C + bias · §3.2 rule tree
priority (K=9) · §3.3 softmax fail-closed (no probabilistic fallback) ·
§3.4 delayed labels + Dirichlet T · §3.5 global Gaussian emission · §3.6
EWMA μ/Σ λ=0.94 · §3.7 Mahalanobis turbulence + χ² thresholds · §3.8 edges
(H<L, V=0, gap, time offset, non-finite) · §3.9 BaseRate Wilson · §4
streaming idempotency + PIT · §5.1 schema (additionalProperties:false) ·
§6 params · EV_RGM_001..007 · hysteresis (ISSUE-CP5-019) · deterministic
replay (T-DR-001) · Wave-Out · EngineBase binding.
"""

from __future__ import annotations

import json
import math
import pathlib

import numpy as np
import pytest

from apex.errors import WaveOutError
from apex.engines.e11_regime import (
    CONTRACT_LABEL,
    D,
    DELAY_BARS,
    E11_DEFAULTS,
    E11RegimeEngine,
    ENGINE,
    EVENT_CATALOG,
    EngineParams,
    K,
    LIVE_GATE_OFF_REASON,
    REGIMES,
    REGIME_STATE_ALLOWED,
    REGIME_STATE_REQUIRED,
    STATE_ENUM,
    TH_TURB_95,
    VECTOR_KEYS,
    apply_delayed_labels,
    apply_quality_caps,
    base_rates_report,
    calibration_report,
    catalog_events,
    compute_bias,
    compute_logits_softmax,
    compute_state_vector,
    deterministic_replay_check,
    e11_snapshot_id,
    entropy_normalized,
    estimate_T_dirichlet,
    ewma_update,
    forecast_next_regime,
    gaussian_log_emission,
    get_params,
    hamilton_filter_step,
    hysteresis_manager,
    load_v3_adapter,
    mahalanobis_turbulence,
    map_momentum_state,
    no_future_leak_check,
    param_hash,
    quality_score,
    redundancy_report,
    rolling_minmax_norm,
    rolling_sigmoid_norm,
    rule_tree_priority,
    run_engine,
    serialize_state,
    validate_state_schema,
    wilson_ci,
)

FIXTURES = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent / "fixtures"
     / "e11_golden_fixtures.json").read_text())
BY_ID = {f["id"]: f for f in FIXTURES["fixtures"]}

T0 = 1768485600000


def ic(trd=0.4, vol=1.0, exp=1.0, liq=0.5, part=0.3, sq=0.5, mom="NEUTRAL",
       bias=(0.1, 0.1, 0.1), atr_z=0.0):
    return {"trendiness_raw": trd, "vol_ratio": vol, "expansion_raw": exp,
            "level_density": liq, "participation_raw": part,
            "structure_score": sq, "momentum_state_raw": mom,
            "bias_per_TF": {"H4": bias[0], "H1": bias[1], "M15": bias[2]},
            "atr_z": atr_z}


def candle(i, inputs, v=1000.0, **flags):
    c = {"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.5, "v": v,
         "ts": T0 + i * 3600000, "as_of": T0 + i * 3600000,
         "symbol": "BNBUSDT", "timeframe": "1h", "ic_inputs": inputs}
    c.update(flags)
    return c


def peaked(idx, scale=6.0):
    W = np.zeros((K, D))
    W[idx] = scale
    return W, np.zeros(K)


def seed_windows():
    return {"trend": [0.25, 0.65] * 20,
            "vol": [0.4, 1.8, 1.1, 0.9] * 10,
            "exp": [0.2, 2.2] * 20,
            "liq": [0.0, 1.0, 0.5, 0.25] * 10,
            "part": [-0.6, 0.6] * 20,
            "sq": [0.18, 0.82] * 20}


def run_fixture_single(fx, **kw):
    candles = [candle(0, fx["inputs"], **(fx.get("candle_flags") or {}))]
    return run_engine(candles, W=np.array(fx["W"]), b=np.array(fx["b"]),
                      history=fx["history"], Sigma0=np.array(fx["Sigma0"]),
                      prev_mom=fx["prev_mom"], symbol="BNBUSDT",
                      timeframe="1h", base_rates=fx.get("base_rates"), **kw)


# ---------------------------------------------------------------------------
# §8.1 Golden fixtures (18 cases; expected values re-derived, ADR-P2-007)
# ---------------------------------------------------------------------------
class TestGoldenFixtures:
    def test_eighteen_cases_present_with_hashes(self):
        assert len(FIXTURES["fixtures"]) == 18
        from apex.identity.canonical_json import canonical_json
        from apex.identity.hashes import sha256_hex
        for f in FIXTURES["fixtures"]:
            body = {k: v for k, v in f.items() if k not in ("hash", "note")}
            assert f["hash"] == "sha256:" + sha256_hex(
                canonical_json(body).encode("utf-8"))

    @pytest.mark.parametrize("fid", [
        "GF_01_TREND_EXPANSION", "GF_02_CRISIS_TURBULENCE",
        "GF_03_COMPRESSION_SQUEEZE", "GF_04_RANGE", "GF_05_CHOP_LOW_PART",
        "GF_06_TRANSITION_HIGH_ENTROPY", "GF_07_EXPANSION",
        "GF_08_TREND_CONTRACTION", "GF_09_GAP_EDGE"])
    def test_regime_fixture_full_state(self, fid):
        fx = BY_ID[fid]
        res = run_fixture_single(fx)
        st = res["regime_state"]
        exp = fx["expected"]
        validate_state_schema(st)
        assert st["state"] == exp["state"]
        assert st["state_raw"] == exp.get("state_raw", exp["state"])
        assert st["Q"] == exp["Q"]
        for key, val in exp["vector"].items():
            assert st["vector"][key] == pytest.approx(val, abs=1e-9), key
        if "bias" in exp:
            assert st["bias"] == pytest.approx(exp["bias"], abs=1e-9)
        if "entropy" in exp:
            assert st["entropy"] == pytest.approx(exp["entropy"], abs=1e-9)
        if "entropy_lt" in exp:
            assert st["entropy"] < exp["entropy_lt"]
        if "entropy_gte" in exp:
            assert st["entropy"] >= exp["entropy_gte"]
        if "turbulence" in exp:
            assert st["turbulence"] == pytest.approx(
                exp["turbulence"], abs=1e-6)
        if "turbulence_gte" in exp:
            assert st["turbulence"] >= exp["turbulence_gte"]
        if "turbulence_lt" in exp:
            assert st["turbulence"] < exp["turbulence_lt"]
        if "compression_gte" in exp:
            assert st["vector"]["compression"] >= exp["compression_gte"]
        if "probs_uniform" in exp:
            for p, u in zip(st["probs"], exp["probs_uniform"]):
                assert p == pytest.approx(u, abs=1e-12)
        if "probs_max_index" in exp:
            assert int(np.argmax(st["probs"])) == exp["probs_max_index"]
        if "events_include" in exp:
            codes = [e.get("type") for e in res["events"]]
            for code in exp["events_include"]:
                assert code in codes
        # every accepted candle fires EV_RGM_001
        assert "EV_RGM_001" in [e.get("type") for e in res["events"]]

    def test_gf09_gap_adjustment_applied(self):
        st = run_fixture_single(BY_ID["GF_09_GAP_EDGE"])["regime_state"]
        assert st["vector"]["expansion"] == 1.0
        # structure_quality = sigmoid((0.3−0.5)/σ) × 0.7, σ = √(0.32²+ε)
        sigma = math.sqrt(0.1024 + 1e-8)
        base = 1.0 / (1.0 + math.exp(0.2 / sigma))
        assert st["vector"]["structure_quality"] == pytest.approx(
            base * 0.7, abs=1e-9)

    def test_gf10_missing_input_fail_closed(self):
        fx = BY_ID["GF_10_MISSING_INPUT_FAIL_CLOSED"]
        res = run_engine([candle(0, fx["inputs"])],
                         W=np.array(fx["W"]), b=np.array(fx["b"]),
                         history=fx["history"],
                         Sigma0=np.array(fx["Sigma0"]))
        st = res["regime_state"]
        exp = fx["expected"]
        assert st["Q"] == exp["Q"] == "Q0"
        assert st["state"] == exp["state"] == "AMBIGUOUS"
        assert st["event"] == exp["event"] == "EV_RGM_006"
        assert st["error"].startswith(exp["error_prefix"])
        assert "snapshot_id" not in st       # nothing canonical fabricated

    def test_gf11_hysteresis_sequence(self):
        fx = BY_ID["GF_11_HYSTERESIS_SEQUENCE"]
        res = run_engine(fx["candles"], W=np.array(fx["W"]),
                         b=np.array(fx["b"]), history=fx["history"],
                         Sigma0=np.array(fx["Sigma0"]),
                         prev_mom=fx["prev_mom"])
        st = res["regime_state"]
        exp = fx["expected"]
        assert st["state"] == exp["final_state"] == "TREND"
        ev = [(e.get("type"), (e.get("as_of", 0) - T0) // 3600000)
              for e in res["events"]]
        assert [h for t, h in ev if t == "EV_RGM_002"] == exp["ev002_at"]
        assert [h for t, h in ev if t == "EV_RGM_003"] == exp["ev003_at"]
        e3 = [e for e in res["events"] if e.get("type") == "EV_RGM_003"][0]
        assert e3["from"] == exp["ev003_from"]
        assert e3["to"] == exp["ev003_to"]

    def test_gf12_t_dirichlet_exact(self):
        fx = BY_ID["GF_12_T_DIRICHLET"]
        out = estimate_T_dirichlet([tuple(s) for s in fx["sequences"]],
                                   fx["alpha"])
        exp = fx["expected"]
        assert len(out["T"]) == 9 and all(len(r) == 9 for r in out["T"])
        for i, row in enumerate(out["T"]):
            for j, val in enumerate(row):
                assert val == pytest.approx(exp["T"][i][j], abs=1e-9)
            assert sum(row) == pytest.approx(1.0, abs=1e-12)
        assert out["T"][5][5] == pytest.approx(exp["T_TREND_TREND"], abs=1e-12)
        assert out["T"][5][3] == pytest.approx(exp["T_TREND_TEXP"], abs=1e-12)
        # RANGE is registry index 8, CHOP index 7
        assert out["T"][8][7] == pytest.approx(exp["T_RANGE_CHOP"], abs=1e-12)
        # empty history ⇒ uniform Dirichlet prior rows (α/Kα = 1/9)
        t0 = estimate_T_dirichlet([])
        assert all(val == pytest.approx(1.0 / 9.0)
                   for row in t0["T"] for val in row)
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            estimate_T_dirichlet([("TREND", "NOT_A_REGIME")])

    def test_gf13_hamilton_filter_simplex(self):
        fx = BY_ID["GF_13_HAMILTON_FILTER"]
        pred, filt = hamilton_filter_step(np.array(fx["xi0"]),
                                          np.array(fx["T"]),
                                          np.array(fx["eta"]))
        for got, want in ((pred, fx["expected"]["xi_pred"]),
                          (filt, fx["expected"]["xi_filt"])):
            for g, w in zip(got, want):
                assert g == pytest.approx(w, abs=1e-9)
        assert float(np.sum(filt)) == pytest.approx(
            fx["expected"]["xi_filt_sum"], abs=1e-9)
        assert float(np.sum(filt)) == pytest.approx(1.0, abs=1e-7)

    def test_gf14_ewma_update_exact(self):
        fx = BY_ID["GF_14_EWMA_UPDATE"]
        mu1, S1 = ewma_update(np.array(fx["mu0"]),
                              fx["Sigma0_diag"] * np.eye(8),
                              np.array(fx["X"]), fx["lambda"])
        for g, w in zip(mu1, fx["expected"]["mu1"]):
            assert g == pytest.approx(w, abs=1e-12)
        for i in range(8):
            assert S1[i][i] == pytest.approx(
                fx["expected"]["Sigma1_diag"][i], abs=1e-12)
        assert S1[0][1] == pytest.approx(
            fx["expected"]["Sigma1_off_0_1"], abs=1e-12)

    def test_gf15_w_shape_fail_closed_no_fallback(self):
        fx = BY_ID["GF_15_W_SHAPE_FAIL_CLOSED"]
        res = run_engine([candle(0, fx["inputs"])], W=np.array(fx["W"]),
                         b=np.array(fx["b"]), history=fx["history"],
                         Sigma0=np.array(fx["Sigma0"]))
        st = res["regime_state"]
        assert st["Q"] == "Q0" and st["state"] == "FAIL_CLOSED"
        assert st["event"] == "EV_RGM_007"
        assert st["error"].startswith("CONFIGURATION_INVALID")
        assert "probs" not in st               # no uniform fallback exists

    def test_gf16_v_zero(self):
        fx = BY_ID["GF_16_V_ZERO"]
        res = run_engine(fx["candles"], W=np.array(fx["W"]),
                         b=np.array(fx["b"]), history=fx["history"],
                         Sigma0=np.array(fx["Sigma0"]))
        st = res["regime_state"]
        validate_state_schema(st)
        assert st["state"] == "RANGE"
        assert st["Q"] == "Q1"                 # §3.8 cap
        e6 = [e for e in res["events"] if e.get("type") == "EV_RGM_006"]
        assert e6 and e6[0]["error_code"] == "V_ZERO"

    def test_gf17_live_gate_default_off(self):
        fx = BY_ID["GF_17_LIVE_GATE_DEFAULT_OFF"]
        res = run_fixture_single(fx)
        assert res["live_regime_gate"]["enabled"] is False
        assert res["live_regime_gate"]["reason"] == LIVE_GATE_OFF_REASON
        # §5.1 additionalProperties:false ⇒ the gate never lives inside
        assert "live_regime_gate" not in res["regime_state"]
        validate_state_schema(res["regime_state"])
        res2 = run_fixture_single(fx, live_regime_gate=True)
        assert res2["live_regime_gate"]["enabled"] is True
        assert "Phase-7" in res2["live_regime_gate"]["reason"]

    def test_gf18_base_rate_cap_q3(self):
        fx = BY_ID["GF_18_BASE_RATE_CAP"]
        res = run_fixture_single(fx)
        st = res["regime_state"]
        assert st["state"] == "RANGE"
        assert st["Q"] == "Q3"                 # n_r=10 < 30 ⇒ capped


# ---------------------------------------------------------------------------
# AI.10 T-E11-K9 — dimensionality proof (K=9 exactly, everywhere)
# ---------------------------------------------------------------------------
class TestTE11K9:
    def test_registry_is_exactly_9(self):
        assert K == 9
        assert len(REGIMES) == 9
        assert len(set(REGIMES)) == 9
        assert E11_DEFAULTS["K"] == 9

    def test_state_enum_is_9_plus_ambiguous(self):
        assert set(STATE_ENUM) == set(REGIMES) | {"AMBIGUOUS"}

    @pytest.mark.parametrize("fid", [
        "GF_01_TREND_EXPANSION", "GF_02_CRISIS_TURBULENCE",
        "GF_04_RANGE", "GF_06_TRANSITION_HIGH_ENTROPY",
        "GF_07_EXPANSION", "GF_09_GAP_EDGE"])
    def test_probs_and_logits_always_9(self, fid):
        st = run_fixture_single(BY_ID[fid])["regime_state"]
        assert len(st["probs"]) == 9 and len(st["logits"]) == 9
        assert sum(st["probs"]) == pytest.approx(1.0, abs=1e-12)
        assert st["state"] in REGIMES

    def test_T_always_9x9_even_from_sparse_data(self):
        for seqs in ([], [("CRISIS", "CRISIS")],
                     [(r, r) for r in REGIMES]):
            out = estimate_T_dirichlet(seqs)
            assert len(out["T"]) == 9
            assert all(len(row) == 9 for row in out["T"])
            assert out["regimes"] == list(REGIMES)

    def test_K_deviation_fails_closed(self):
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            EngineParams({"K": 8})
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            get_params({"K": 10}, use_yaml=False)

    def test_vector_is_exactly_8_dimensional(self):
        vec, _ = compute_state_vector(ic(), seed_windows(), 0.5)
        assert set(vec) == set(VECTOR_KEYS) and len(VECTOR_KEYS) == 8
        W, b = peaked(5)
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            compute_logits_softmax(vec, np.zeros((9, 7)), b)   # d≠8
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            compute_logits_softmax(vec, W, np.zeros(8))        # K≠9

    def test_covariance_is_8x8_cholesky_guarded(self):
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            mahalanobis_turbulence(np.zeros(8), np.zeros(8), np.zeros((7, 7)))
        bad = np.eye(8)
        bad[0, 0] = -1.0                       # not positive definite
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            mahalanobis_turbulence(np.zeros(8), np.zeros(8), bad)


# ---------------------------------------------------------------------------
# §3.1 normalization methods
# ---------------------------------------------------------------------------
class TestNorms:
    def test_method_a_minmax(self):
        win = [0.4, 1.8, 1.1, 0.9] * 10
        assert rolling_minmax_norm(1.1, win) == pytest.approx(0.5)
        assert rolling_minmax_norm(2.8, win) == 1.0    # clipped above
        assert rolling_minmax_norm(0.1, win) == 0.0    # clipped below
        with pytest.raises(ValueError, match="INVALID_E11_HISTORY"):
            rolling_minmax_norm(1.0, [0.5] * 9)        # <10 samples
        with pytest.raises(ValueError, match="INVALID_E11_HISTORY"):
            rolling_minmax_norm(1.0, [0.5] * 20)       # degenerate mx==mn
        with pytest.raises(ValueError, match="INVALID_E11_HISTORY"):
            rolling_minmax_norm(float("nan"), win)

    def test_method_b_sigmoid(self):
        win = [0.25, 0.65] * 20                      # μ=0.45 σ≈0.2
        got = rolling_sigmoid_norm(0.78, win)
        assert got == pytest.approx(1 / (1 + math.exp(-(0.78 - 0.45) /
                                                        math.sqrt(0.04 + 1e-8))),
                                    abs=1e-12)
        assert 0.0 < got < 1.0
        huge = rolling_sigmoid_norm(1e6, win)          # z clipped to +10
        assert huge < 1.0 and huge > 0.9999
        with pytest.raises(ValueError, match="INVALID_E11_HISTORY"):
            rolling_sigmoid_norm(0.5, [0.4] * 19)      # <20 samples
        with pytest.raises(ValueError, match="INVALID_E11_HISTORY"):
            rolling_sigmoid_norm(0.5, [0.4] * 30)      # σ degenerate

    def test_method_c_momentum(self):
        assert map_momentum_state("IMPULSIVE", 0.5) == pytest.approx(
            0.94 * 0.5 + 0.06 * 1.0)
        assert map_momentum_state("NEUTRAL", 0.5) == pytest.approx(0.5)
        assert map_momentum_state("EXHAUSTED", 0.5) == pytest.approx(
            0.94 * 0.5 + 0.06 * 0.0)
        with pytest.raises(ValueError, match="INVALID_E11_FEATURE"):
            map_momentum_state("SIDEWAYS", 0.5)
        with pytest.raises(ValueError, match="INVALID_E11_FEATURE"):
            map_momentum_state("NEUTRAL", 1.5)

    def test_bias_weights_and_fail_closed(self):
        assert compute_bias({"H4": 0.8, "H1": 0.7, "M15": 0.6}) == \
            pytest.approx(0.73)
        assert compute_bias({"H4": 5.0, "H1": -5.0, "M15": 0.0}) == \
            pytest.approx(0.5 * 1.0 + 0.3 * (-1.0))    # clipped to ±1
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            compute_bias({"H4": 0.1, "M15": 0.2})       # missing H1
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            compute_bias({"H4": float("nan"), "H1": 0.0, "M15": 0.0})

    def test_compression_atr_boost(self):
        wins = seed_windows()
        vec, _ = compute_state_vector(ic(vol=0.55, atr_z=-1.5), wins, 0.5)
        vec2, _ = compute_state_vector(ic(vol=0.55, atr_z=0.0), wins, 0.5)
        assert vec["compression"] == pytest.approx(
            min(1.0, vec2["compression"] + 0.15), abs=1e-12)

    def test_nonfinite_inputs_fail_closed(self):
        with pytest.raises(ValueError, match="INVALID_E11_FEATURE"):
            compute_state_vector(ic(trd=float("inf")), seed_windows(), 0.5)
        with pytest.raises(ValueError,
                           match="CONFIGURATION_INVALID: missing required"):
            compute_state_vector(ic(part=None), seed_windows(), 0.5)


# ---------------------------------------------------------------------------
# §3.2/§3.3 rule tree + softmax
# ---------------------------------------------------------------------------
class TestSoftmaxRuleTree:
    def test_softmax_uniform_entropy_is_ln9(self):
        vec = {k: 0.5 for k in VECTOR_KEYS}
        logits, probs, H = compute_logits_softmax(
            vec, np.zeros((9, 8)), np.zeros(9))
        assert all(p == pytest.approx(1 / 9, abs=1e-15) for p in probs)
        assert H == pytest.approx(math.log(9), abs=1e-12)
        assert entropy_normalized(H) == pytest.approx(1.0, abs=1e-12)

    def test_softmax_peaked_entropy_near_zero(self):
        vec = {k: 0.5 for k in VECTOR_KEYS}
        W, b = peaked(3, scale=12.0)
        _l, probs, H = compute_logits_softmax(vec, W, b)
        assert probs[3] > 0.999
        assert H < 0.05
        assert sum(probs) == pytest.approx(1.0, abs=1e-12)

    def test_softmax_fail_closed(self):
        vec = {k: 0.5 for k in VECTOR_KEYS}
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            compute_logits_softmax(vec, np.zeros((8, 8)), np.zeros(8))
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            W, b = peaked(0)
            W[0, 0] = float("nan")
            compute_logits_softmax(vec, W, b)

    @staticmethod
    def _v(**kw):
        base = {k: 0.3 for k in VECTOR_KEYS}
        base.update(kw)
        return base

    def test_rule_tree_priority_order(self):
        p = EngineParams()
        # CRISIS beats everything (vol ≥ 0.85)
        out = rule_tree_priority(self._v(volatility=0.9, trendiness=0.9),
                                 0.0, 2.0, 30.0, [1 / 9] * 9, p)
        assert out["state"] == "CRISIS"
        # TRANSITION beats trend states (H ≥ θ_H raw nats — ISSUE-CP5-010)
        out = rule_tree_priority(self._v(trendiness=0.9), 0.0, 0.7, 1.0,
                                 [1 / 9] * 9, p)
        assert out["state"] == "TRANSITION"
        # EXPANSION beats TREND_EXPANSION
        out = rule_tree_priority(
            self._v(trendiness=0.9, expansion=0.7, participation=0.5),
            0.0, 0.1, 1.0, [1 / 9] * 9, p)
        assert out["state"] == "EXPANSION"
        out = rule_tree_priority(
            self._v(trendiness=0.9, expansion=0.55, participation=0.5),
            0.0, 0.1, 1.0, [1 / 9] * 9, p)
        assert out["state"] == "TREND_EXPANSION"
        out = rule_tree_priority(
            self._v(trendiness=0.9, expansion=0.2, compression=0.7),
            0.0, 0.1, 1.0, [1 / 9] * 9, p)
        assert out["state"] == "TREND_CONTRACTION"
        out = rule_tree_priority(
            self._v(trendiness=0.9, expansion=0.2, compression=0.2),
            0.0, 0.1, 1.0, [1 / 9] * 9, p)
        assert out["state"] == "TREND"
        out = rule_tree_priority(
            self._v(trendiness=0.2, compression=0.7, volatility=0.25),
            0.0, 0.1, 1.0, [1 / 9] * 9, p)
        assert out["state"] == "COMPRESSION"
        out = rule_tree_priority(
            self._v(trendiness=0.2, compression=0.2, participation=0.2,
                    liquidity_stability=0.2),
            0.0, 0.1, 1.0, [1 / 9] * 9, p)
        assert out["state"] == "CHOP"
        out = rule_tree_priority(self._v(trendiness=0.2), 0.05, 0.1, 1.0,
                                 [1 / 9] * 9, p)
        assert out["state"] == "RANGE"
        assert "bias" in out["reason"]               # neutral-band branch

    def test_quality_cascade(self):
        vec = self._v()
        assert quality_score(vec, 0.9, 1.0, True, True) == "Q2"
        assert quality_score(vec, 0.1, 25.0, True, True) == "Q2"
        assert quality_score(vec, 0.7, 1.0, True, True) == "Q3"
        assert quality_score(vec, 0.1, 16.0, True, True) == "Q3"
        assert quality_score(vec, 0.1, 1.0, True, True) == "Q5"
        assert quality_score(vec, 0.5, 9.0, True, True) == "Q4"
        assert quality_score(vec, 0.1, 1.0, False, True) == "Q0"
        assert quality_score(vec, 0.1, 1.0, True, False) == "Q1"

    def test_apply_quality_caps_worst_of(self):
        assert apply_quality_caps("Q4", ["Q1", "Q3"]) == "Q1"
        assert apply_quality_caps("Q5", [None, "Q3"]) == "Q3"
        assert apply_quality_caps("Q2", []) == "Q2"


# ---------------------------------------------------------------------------
# §4 streaming semantics
# ---------------------------------------------------------------------------
class TestStreamingState:
    def _res(self, candles, **kw):
        W, b = peaked(5)
        return run_engine(candles, W=W, b=b, history=seed_windows(),
                          Sigma0=0.05 * np.eye(8), symbol="BNBUSDT",
                          timeframe="1h", **kw)

    def test_duplicate_as_of_is_idempotent(self):
        from apex.engines.e11_regime import RegimeEngine
        W, b = peaked(5)
        eng = RegimeEngine(EngineParams(), W=W, b=b,
                           history=seed_windows(), Sigma0=0.05 * np.eye(8))
        c = candle(0, ic())
        out1 = eng.update(c)
        n = eng.bar_index
        out2 = eng.update(dict(c))
        assert out2 is out1                        # cached object returned
        assert eng.bar_index == n                  # state untouched

    def test_h_lt_l_q0_degraded(self):
        bad = candle(0, ic(), h=98.0)              # h < l=99
        bad["h"] = 98.0
        res = self._res([bad])
        st = res["regime_state"]
        assert st["Q"] == "Q0" and st["state"] == "AMBIGUOUS"
        assert st["event"] == "EV_RGM_006" and st["error"] == "H<L"

    def test_time_offset_degraded(self):
        c0 = candle(0, ic())
        c1 = candle(1, ic())
        c1["as_of"] = T0 + 4 * 3600000             # > 2× timeframe offset
        c1["ts"] = T0 + 4 * 3600000
        res = self._res([c0, c1])
        codes = [e.get("type") for e in res["events"]]
        assert "EV_RGM_006" in codes
        e6 = [e for e in res["events"] if e.get("type") == "EV_RGM_006"][-1]
        assert e6["error_code"] == "TIME_OFFSET"
        assert res["regime_state"]["Q"] == "Q1"

    def test_contract_mismatch_caps_q1(self):
        inputs = ic()
        inputs["e09_version"] = "E09_Trend/3.9.0"
        res = self._res([candle(0, inputs)])
        assert res["regime_state"]["Q"] == "Q1"
        e6 = [e for e in res["events"] if e.get("type") == "EV_RGM_006"]
        assert e6 and e6[0]["error_code"] == "CONTRACT_MISMATCH"
        inputs2 = ic()
        inputs2["e10_version"] = "garbage"         # unparseable ⇒ mismatch
        assert self._res([candle(0, inputs2)])["regime_state"]["Q"] == "Q1"
        inputs3 = ic()
        inputs3["e04_version"] = "E04_Volatility/4.0.0"
        assert self._res([candle(0, inputs3)])["regime_state"]["Q"] != "Q1"

    def test_warmup_refusal_until_windows_filled(self):
        W, b = peaked(5)
        candles = [candle(i, ic()) for i in range(5)]
        res = run_engine(candles, W=W, b=b, symbol="X", timeframe="1h")
        st = res["regime_state"]
        assert st["quality"] == "QX"
        assert st["reason"] == "INSUFFICIENT_HISTORY_Q1"
        assert res["events"] == []
        assert "snapshot_id" not in st

    def test_missing_prev_mom_fails_closed(self):
        from apex.engines.e11_regime import RegimeEngine
        W, b = peaked(5)
        eng = RegimeEngine(EngineParams(), W=W, b=b,
                           history=seed_windows(), Sigma0=0.05 * np.eye(8),
                           prev_mom=None)
        out = eng.update(candle(0, ic()))
        assert out["event"] == "EV_RGM_007" and out["Q"] == "Q0"
        assert out["state"] == "FAIL_CLOSED"

    def test_pit_no_future_leak(self):
        W, b = peaked(5)

        def make():
            from apex.engines.e11_regime import RegimeEngine
            return RegimeEngine(EngineParams(), W=W, b=b,
                                history=seed_windows(),
                                Sigma0=0.05 * np.eye(8))
        candles = [candle(i, ic(trd=0.4 + 0.01 * i)) for i in range(3)]
        alt = [ic(trd=9.9, vol=99.0, exp=9.9, liq=0.01, part=9.9, sq=9.9,
                  mom="IMPULSIVE", bias=(1.0, 1.0, 1.0), atr_z=9.0)]
        assert no_future_leak_check(make, candles, 1, alt) is True

    def test_deterministic_replay_byte_identical(self):
        W, b = peaked(5)
        candles = [candle(i, ic(trd=0.4 + 0.01 * i)) for i in range(4)]
        from apex.engines.e11_regime import RegimeEngine
        assert deterministic_replay_check(
            candles,
            lambda: RegimeEngine(EngineParams(), W=W, b=b,
                                 history=seed_windows(),
                                 Sigma0=0.05 * np.eye(8))) is True
        a = self._res(candles)
        c = self._res(candles)
        assert json.dumps(a, sort_keys=True, default=str) == json.dumps(
            c, sort_keys=True, default=str)

    def test_gaussian_emission_log_form(self):
        mu = np.full(8, 0.5)
        Sig = 0.05 * np.eye(8)
        x = np.full(8, 0.5)
        ln_eta = gaussian_log_emission(x, mu, Sig)
        # at the mean: ln η = −½(d·ln2π + ln|Σ|), ln|Σ| = 8·ln(0.05)
        expect = -0.5 * (8 * math.log(2 * math.pi) + 8 * math.log(0.05))
        assert ln_eta == pytest.approx(expect, abs=1e-9)
        assert ln_eta > gaussian_log_emission(np.full(8, 5.0), mu, Sig)

    def test_state_schema_fail_closed(self):
        st = run_fixture_single(BY_ID["GF_01_TREND_EXPANSION"])["regime_state"]
        validate_state_schema(st)
        broken = dict(st)
        del broken["turbulence"]
        with pytest.raises(ValueError, match="missing turbulence"):
            validate_state_schema(broken)
        extra = dict(st, live_regime_gate=False)
        with pytest.raises(ValueError, match="additionalProperties"):
            validate_state_schema(extra)
        bad_vec = dict(st, vector=dict(st["vector"], extra_dim=0.5))
        with pytest.raises(ValueError, match="8 canonical components"):
            validate_state_schema(bad_vec)
        bad_probs = dict(st, probs=[1 / 9] * 8)
        with pytest.raises(ValueError, match="exactly\\s*9|9 items"):
            validate_state_schema(bad_probs)
        bad_state = dict(st, state="BULL_RUN")
        with pytest.raises(ValueError, match="state enum"):
            validate_state_schema(bad_state)
        assert set(REGIME_STATE_REQUIRED) <= set(REGIME_STATE_ALLOWED)


# ---------------------------------------------------------------------------
# §6 parameters + ADR-P2-008 YAML re-assertion
# ---------------------------------------------------------------------------
class TestParams:
    def test_yaml_reasserted_against_chapter_defaults(self):
        p = get_params()
        assert p.as_dict()["K"] == 9
        # D49: shipped YAML H p80, not the chapter default 0.65.
        assert p.entropy_threshold == pytest.approx(1.105878)
        assert p.ewma_lambda == 0.94
        assert p.transition_confirm_bars == 3
        assert p.dirichlet_alpha == 0.1
        assert p.delayed_label_bars == 48
        assert p.rolling_window_days == 180
        # §9.5-canonical YAML agrees with the chapter §6 table ⇒ no
        # override assertions are recorded (re-assertion passed).
        # D49 values disagree with the chapter defaults on purpose; the three
        # overrides are recorded and every other YAML key still agrees.
        assert len(p.yaml_assertions) == 3
        joined = " ".join(p.yaml_assertions)
        assert "theta_H" in joined and "quality_H_Q2" in joined
        assert "quality_H_Q5" in joined

    def test_temp_yaml_theta_h_reaches_get_params(self, tmp_path, monkeypatch):
        import apex.config as config
        source = config.PARAMS_DIR / "e11_params_v4.yaml"
        text = source.read_text(encoding="utf-8").replace(
            "theta_H: 1.105878", "theta_H: 1.2", 1)
        assert "theta_H: 1.2" in text
        (tmp_path / "e11_params_v4.yaml").write_text(text, encoding="utf-8")
        monkeypatch.setattr(config, "PARAMS_DIR", tmp_path)
        got = get_params()
        assert got.entropy_threshold == pytest.approx(1.2)

    def test_runtime_override_wins(self):
        p = get_params({"entropy_threshold": 0.7}, use_yaml=False)
        assert p.entropy_threshold == 0.7

    def test_unknown_params_rejected(self):
        with pytest.raises(ValueError, match="UNKNOWN_E11_PARAM_QX"):
            get_params({"nope": 1}, use_yaml=False)
        with pytest.raises(ValueError, match="UNKNOWN_E11_PARAM_QX"):
            run_engine([candle(0, ic())], params={"theta": 1})

    def test_param_hash_stable_12_hex(self):
        h = param_hash(EngineParams())
        assert len(h) == 12 and all(c in "0123456789abcdef" for c in h)
        assert h == param_hash(EngineParams())
        assert h != param_hash(EngineParams({"entropy_threshold": 0.7}))

    def test_defaults_cover_chapter_table(self):
        for key in ("entropy_threshold", "trend_threshold",
                    "expansion_threshold", "compression_threshold",
                    "participation_low", "liquidity_low",
                    "volatility_crisis", "turbulence_threshold",
                    "transition_confirm_bars", "ewma_lambda",
                    "dirichlet_alpha", "delayed_label_bars",
                    "rolling_window_days", "bias_neutral_band",
                    "shock_gap_atr_mult", "quality_H_Q2", "quality_Tur_Q3"):
            assert key in E11_DEFAULTS
        assert E11_DEFAULTS["turbulence_threshold"] == TH_TURB_95 == 15.5073
        assert E11_DEFAULTS["ewma_lambda"] == 0.94

    def test_event_catalog_complete(self):
        assert set(EVENT_CATALOG) == {f"EV_RGM_{i:03d}" for i in range(1, 8)}
        assert CONTRACT_LABEL == "E11_Regime/4.0.0"
        assert ENGINE == "E11_Regime"
        assert DELAY_BARS == 48


# ---------------------------------------------------------------------------
# §3.4/§3.9/§8.5–8.7 battery helpers
# ---------------------------------------------------------------------------
class TestBatteryHelpers:
    def test_delayed_labels(self):
        labels = ["TREND"] * 60
        conf = [True] * 60
        out = apply_delayed_labels(labels, conf, delay=48)
        assert out[:12] == ["TREND"] * 12          # t+48 < 60 ⇒ final
        assert out[12:] == ["AMBIGUOUS"] * 48      # unconfirmed horizon
        out2 = apply_delayed_labels(labels, [False] * 60, delay=48)
        assert out2 == ["AMBIGUOUS"] * 60

    def test_wilson_and_base_rates(self):
        lo, hi = wilson_ci(0.61, 320)
        assert lo == pytest.approx(0.555, abs=0.01)
        assert hi == pytest.approx(0.663, abs=0.01)
        assert wilson_ci(None, 0) == (0.0, 0.0)
        rep = base_rates_report([("TREND", True)] * 6 + [("TREND", False)] * 4)
        assert rep["TREND"]["n"] == 10 and rep["TREND"]["k"] == 6
        assert rep["TREND"]["p"] == pytest.approx(0.6)
        assert rep["CRISIS"]["n"] == 0 and rep["CRISIS"]["p"] is None

    def test_calibration_q3_caps(self):
        rep = base_rates_report([("TREND", True)] * 10)
        cal = calibration_report(rep)
        assert "TREND" in cal["q3_caps"]           # n=10 < 30
        cal2 = calibration_report(rep, bins=[(0.9, True)] * 9 + [(0.9, False)])
        assert cal2["ece"] == pytest.approx(0.18, abs=1e-9)

    def test_redundancy_compression_vs_volatility(self):
        # x_comp = 1 − x_vol (no atr_z adjustment) ⇒ |corr| = 1 ⇒ alert
        vol = [0.2, 0.5, 0.3, 0.7, 0.45, 0.6, 0.35, 0.55, 0.25, 0.65,
               0.4, 0.5]
        comp = [1 - v for v in vol]
        rep = redundancy_report(comp, vol)
        assert rep["corr"] == pytest.approx(-1.0, abs=1e-12)
        assert rep["redundancy_alert"] is True
        # the §3.1 atr_z adjustment breaks the exact anti-correlation
        # (§8.6: −0.92 → below the 0.85 alert threshold)
        pert = [1.75, -0.25, 1.25, -0.75, 1.5, -1.25, 0.75, -1.5, 1.4,
                -0.5, 1.0, -1.4]
        comp_adj = [c + p for c, p in zip(comp, pert)]
        rep2 = redundancy_report(comp_adj, vol)
        assert abs(rep2["corr"]) < 0.85
        assert rep2["redundancy_alert"] is False

    def test_serialize_state_six_decimals(self):
        st = run_fixture_single(BY_ID["GF_01_TREND_EXPANSION"])["regime_state"]
        wire = serialize_state(st)
        assert wire["snapshot_id"] == st["snapshot_id"]
        for key in VECTOR_KEYS:
            s = repr(wire["vector"][key])
            assert len(s.split(".")[-1]) <= 6 if "." in s else True

    def test_load_v3_adapter_fail_closed(self):
        with pytest.raises(ValueError, match="E11_V3_ADAPTER_QX"):
            load_v3_adapter({"version": "4.0.0", "state": {"state": "TREND"}})
        with pytest.raises(ValueError, match="E11_V3_ADAPTER_QX"):
            load_v3_adapter({"version": "3.1.0"})
        out = load_v3_adapter({"version": "3.1.0",
                               "regime_state": {"state": "TREND",
                                                "as_of": 7}})
        assert out["Q"] == "Q1"                    # migration emits Q1
        assert out["contract_version"] == CONTRACT_LABEL
        assert out["state"] == "TREND" and out["as_of"] == 7

    def test_hysteresis_manager_direct(self):
        # first candle adopts its label
        assert hysteresis_manager([], "TREND") == ("TREND", "CONFIRMED")
        # continuation of the confirmed label is stable
        assert hysteresis_manager(["TREND"], "TREND", 3,
                                  confirmed_prev="TREND") == \
            ("TREND", "CONFIRMED")
        # a proposed change with 1/3 repeats stays SUSPECTED
        assert hysteresis_manager(["TREND", "TREND"], "CRISIS", 3,
                                  confirmed_prev="TREND") == \
            ("TREND", "SUSPECTED")
        # 3 consecutive new labels confirm the change
        assert hysteresis_manager(["TREND", "CRISIS", "CRISIS"], "CRISIS", 3,
                                  confirmed_prev="TREND") == \
            ("CRISIS", "CONFIRMED")


# ---------------------------------------------------------------------------
# Wave-Out + EngineBase binding (frozen contract — consumed, never patched)
# ---------------------------------------------------------------------------
class TestWaveOutAndBinding:
    def test_forecast_next_regime_is_wave_out(self):
        with pytest.raises(WaveOutError):
            forecast_next_regime()

    def test_compute_forecast_context_raises_wave_out(self):
        with pytest.raises(WaveOutError):
            E11RegimeEngine().compute("BNBUSDT", "1h",
                                      "2026-01-15T00:00:00Z",
                                      {"candles": [], "forecast": True})

    def test_compute_adaptive_atr_raises_wave_out(self):
        with pytest.raises(WaveOutError):
            E11RegimeEngine().compute("BNBUSDT", "1h",
                                      "2026-01-15T00:00:00Z",
                                      {"candles": [], "adaptive_atr": True})

    def test_missing_window_fails_closed(self):
        with pytest.raises(ValueError, match="MISSING_WINDOW_CONTEXT_QX"):
            E11RegimeEngine().compute("BNBUSDT", "1h",
                                      "2026-01-15T00:00:00Z", {})

    def test_empty_candles_emit_nothing(self):
        assert E11RegimeEngine().compute("BNBUSDT", "1h",
                                         "2026-01-15T00:00:00Z",
                                         {"candles": []}) == []

    def test_compute_emits_context_only_events(self):
        fx = BY_ID["GF_01_TREND_EXPANSION"]
        evs = E11RegimeEngine().compute(
            "BNBUSDT", "1h", "2026-01-15T00:00:00Z",
            {"candles": [candle(0, fx["inputs"])],
             "W": fx["W"], "b": fx["b"], "history": fx["history"],
             "Sigma0": fx["Sigma0"], "prev_mom": fx["prev_mom"]})
        assert evs
        for ev in evs:
            ev.validate_24_fields()
            assert ev.engine_id == "E11"
            assert ev.direction == 0                # NG1 context/veto engine
            assert ev.resolution_class in ("Q0", "Q1", "Q2", "Q3", "Q4", "Q5")
            assert ev.parameter_version == "E11-RGM-V4.0.0/e11_params_v4"
            assert ev.condition_state.startswith("EV_RGM_")
            assert 0.0 <= ev.strength <= 1.0
            assert 0.0 <= ev.confidence <= 1.0
        states = [ev.condition_state for ev in evs]
        assert "EV_RGM_001_TREND_EXPANSION" in states
        for ev in evs:
            if ev.resolution_class in ("Q3", "Q4", "Q5"):
                assert ev.validity == "VALID"

    def test_compute_refusal_emits_nothing(self):
        fx = BY_ID["GF_10_MISSING_INPUT_FAIL_CLOSED"]
        assert E11RegimeEngine().compute(
            "BNBUSDT", "1h", "2026-01-15T00:00:00Z",
            {"candles": [candle(0, fx["inputs"])], "W": fx["W"],
             "b": fx["b"], "history": fx["history"],
             "Sigma0": fx["Sigma0"]}) == []

    def test_compute_rejects_unknown_params(self):
        fx = BY_ID["GF_01_TREND_EXPANSION"]
        with pytest.raises(ValueError, match="UNKNOWN_E11_PARAM_QX"):
            E11RegimeEngine().compute(
                "BNBUSDT", "1h", "2026-01-15T00:00:00Z",
                {"candles": [candle(0, fx["inputs"])], "W": fx["W"],
                 "b": fx["b"], "history": fx["history"],
                 "e11_params": {"nope": 1}})

    def test_t_dr_001_deterministic_replay(self):
        """T-DR-001: identical emissions on re-run over identical inputs."""
        fx = BY_ID["GF_01_TREND_EXPANSION"]
        ctx = {"candles": [candle(0, fx["inputs"])], "W": fx["W"],
               "b": fx["b"], "history": fx["history"],
               "Sigma0": fx["Sigma0"], "prev_mom": fx["prev_mom"]}
        a = E11RegimeEngine().compute("BNBUSDT", "1h",
                                      "2026-01-15T00:00:00Z", ctx)
        b = E11RegimeEngine().compute("BNBUSDT", "1h",
                                      "2026-01-15T00:00:00Z", ctx)
        assert [e.snapshot_id for e in a] == [e.snapshot_id for e in b]
        assert [e.condition_state for e in a] == [e.condition_state for e in b]
        assert [e.strength for e in a] == [e.strength for e in b]

    def test_catalog_events(self):
        assert catalog_events({"quality": "QX"}) == []
        st = run_fixture_single(BY_ID["GF_06_TRANSITION_HIGH_ENTROPY"]
                                )["regime_state"]
        codes = [e["code"] for e in catalog_events(st)]
        assert "EV_RGM_001" in codes and "EV_RGM_004" in codes
        st2 = run_fixture_single(BY_ID["GF_02_CRISIS_TURBULENCE"]
                                 )["regime_state"]
        codes2 = [e["code"] for e in catalog_events(st2)]
        assert "EV_RGM_005" in codes2

    def test_snapshot_id_content_bound(self):
        a = {"state": "TREND", "Q": "Q4"}
        b = {"state": "TREND", "Q": "Q4"}
        c = {"state": "TREND", "Q": "Q3"}
        assert e11_snapshot_id(a) == e11_snapshot_id(b)
        assert e11_snapshot_id(a) != e11_snapshot_id(c)
        assert len(e11_snapshot_id(a)) == 64
