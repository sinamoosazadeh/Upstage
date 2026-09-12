"""E09 Trend — full §8 validation battery (APEX_GEN5.md L9467–10275).

Covers: §8.1 golden fixtures (11 cases, re-derived) · §3.1 position/sequence/
direction-strength/quality · §3.2 Mann–Kendall with tie correction ·
§3.3 Newey–West OLS · §3.4 Hurst R/S (Anis–Lloyd corrected) · §3.5 Wilder ADX
**AD-line** (DI+/DI−/DX/ADX, NaN-before-2n warm-up) · §3.6 divergence and
exhaustion · §3.7 **multi-TF** stack (bias, alignment, quality aggregate) ·
§4 continuity · §5 state machine + schema · §6 parameters · EV_TRD_001..008 ·
PIT violation · deterministic replay (T-DR-001) · EngineBase binding.
"""

from __future__ import annotations

import json
import math
import pathlib
from decimal import Decimal

import pytest

from apex.data_catalog.contracts import MarketObservation
from apex.engines.e09_trend import (
    ALIGNMENTS,
    CONTRACT_LABEL,
    CONTRACT_VERSION,
    E09_DEFAULTS,
    E09TrendEngine,
    ENGINE,
    EVENT_CATALOG,
    MOMENTUM_UNAVAILABLE_REASON,
    OI_MISSING_REASON,
    OI_STATES,
    PIT_LAG,
    QUALITY_LABELS,
    SCALES,
    SCALE_STATES,
    SWINGS_UNAVAILABLE_REASON,
    TREND_SCALE_REQUIRED,
    TREND_STACK_REQUIRED,
    W_STACK_CORRECTED,
    TrendEngine,
    TrendScale,
    anis_lloyd_expected_rs,
    compute_adx_wilder,
    compute_pos_scale,
    compute_seq_score,
    compute_trend_quality,
    continuity_break,
    dedup_swings,
    directional_movement,
    divergence_exhaustion_check,
    e09_snapshot_id,
    exhaustion_score,
    get_params,
    hurst_rs_anis_lloyd_corrected,
    mann_kendall_with_tie_correction,
    newey_west_lag,
    ols_slope_newey_west,
    pearson,
    quality_aggregate,
    quality_label,
    run_engine,
    scale_state,
    scale_windows,
    stack_alignment,
    stack_bias,
    trend_direction_and_strength,
    validate_bar,
    wilder_rma,
    wilson_ci,
)

FIXTURES = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent / "fixtures"
     / "e09_golden_fixtures.json").read_text())
BY_ID = {f["id"]: f for f in FIXTURES["fixtures"]}


def bar(o, h, l, c, ts=0, v=1000.0):
    return {"o": o, "h": h, "l": l, "c": c, "ts": ts, "v": v}


def ramp(n, start=2000.0, step=1.0):
    """A strictly rising synthetic series of closed bars."""
    out = []
    for i in range(n):
        c = start + step * i
        out.append(bar(c - 0.4, c + 0.5, c - 0.5, c, 1768485600000 + i * 3600000))
    return out


# ---------------------------------------------------------------------------
# §8.1 Golden fixtures
# ---------------------------------------------------------------------------
class TestGoldenFixtures:
    def test_eleven_cases_present_with_hashes(self):
        assert len(FIXTURES["fixtures"]) == 11
        from apex.identity.canonical_json import canonical_json
        from apex.identity.hashes import sha256_hex
        for f in FIXTURES["fixtures"]:
            # §9.5-3: computed after the fixture was written; recomputed here
            # over the committed body (no document hash is ever copied).
            body = {k: v for k, v in f.items() if k not in ("hash", "note")}
            assert f["hash"] == "sha256:" + sha256_hex(
                canonical_json(body).encode("utf-8"))

    def test_fix01_uptrend_strong(self):
        fx = BY_ID["FIX_01_UPTREND_STRONG"]
        p = get_params()
        seq, ev = compute_seq_score(fx["swings"], p.window_micro,
                                    len(fx["bars"]) - 1)
        assert seq == pytest.approx(fx["expected"]["seq_score"])
        assert ev == fx["expected"]["evidence_count"]
        pos = compute_pos_scale(fx["bars"], p.window_micro, fx["atr"])
        assert pos == pytest.approx(1.0)
        # §3.2 runs the regression on LOG closes.
        closes = [math.log(b["c"]) for b in fx["bars"][-p.window_micro:]]
        beta, se, r2 = ols_slope_newey_west(
            [float(i) for i in range(len(closes))], closes)
        assert r2 == pytest.approx(fx["expected"]["r2"], abs=1e-9)
        slope_z = beta / se                      # §3.2 t-statistic
        assert slope_z == pytest.approx(fx["expected"]["slope_z"], rel=1e-9)
        assert slope_z >= fx["expected"]["slope_z_min"]
        direction, strength, raw = trend_direction_and_strength(
            seq, slope_z, pos)
        assert direction == fx["expected"]["MICRO_dir"] == 1
        assert strength == pytest.approx(1.0)
        # §3.1: Q = R²·min(ADX/100,1)·clip(H,0,1.2)/1.2 — but ADX is in warm-up
        # on a 5-bar window, so the re-derived label is Q0 (ISSUE-CP4-020).
        adx_res = compute_adx_wilder(fx["bars"], p.adx_n)
        assert adx_res["warmup_2n"] is True
        assert quality_label(0.0, fx["expected"]["r2"], 0.0, 0.5) == "Q0"
        assert fx["expected"]["Q_rederived"] == "Q0"

    def test_fix02_downtrend(self):
        fx = BY_ID["FIX_02_DOWNTREND"]
        p = get_params()
        seq, _ev = compute_seq_score(fx["swings"], p.window_micro,
                                     len(fx["bars"]) - 1)
        assert seq == pytest.approx(fx["expected"]["seq_score"])
        assert seq <= fx["expected"]["seq_score_max"]
        closes = [math.log(b["c"]) for b in fx["bars"][-p.window_micro:]]
        beta, se, _r2 = ols_slope_newey_west(
            [float(i) for i in range(len(closes))], closes)
        direction, strength, _raw = trend_direction_and_strength(
            seq, beta / se, 0.0)
        assert direction == fx["expected"]["MICRO_dir"] == -1
        assert beta < 0

    def test_fix03_sideways_direction_divergence(self):
        """ISSUE-CP4-019: §8.1 expects MICRO_dir = 0; §3.2/§4 on the same
        table give slope_z = +0.38 > the 0.05 deadband ⇒ +1. The sideways
        diagnosis is carried by EV_TRD_007, which does fire."""
        fx = BY_ID["FIX_03_SIDEWAYS"]
        p = get_params()
        closes = [math.log(b["c"]) for b in fx["bars"][-p.window_micro:]]
        beta, se, _r2 = ols_slope_newey_west(
            [float(i) for i in range(len(closes))], closes)
        slope_z = beta / se
        direction, _strength, raw_z = trend_direction_and_strength(
            0.0, slope_z, 0.0267)
        assert direction == fx["expected"]["MICRO_dir_rederived"] == 1
        assert fx["expected"]["MICRO_dir"] == 0        # the doc's expectation
        assert direction != fx["expected"]["MICRO_dir"]
        assert raw_z == pytest.approx(0.3827, abs=1e-3)  # > the 0.05 deadband
        res = run_engine(fx["bars"], swings=fx["swings"], atr=fx["atr"])
        assert any(e["code"] == fx["expected"]["sideways_event"]
                   for e in res["events"])
        micro = res["scales"]["MICRO"]
        assert micro["adx"] < fx["expected"]["adx_max"]
        assert micro["r2"] < p.r2_sideways_max
        assert abs(micro["hurst"] - 0.5) < p.hurst_sideways_band

    def test_fix04_adx_known_values(self):
        """The **AD-line**: DI+, DI−, DX and ADX from Wilder's recursion."""
        fx = BY_ID["FIX_04_ADX_KNOWN"]
        res = compute_adx_wilder(fx["bars"], 14)
        assert res["adx"] == pytest.approx(fx["expected"]["adx"], abs=1e-9)
        assert res["adx"] >= fx["expected"]["adx_min"]
        assert res["di_plus"] == pytest.approx(fx["expected"]["di_plus"],
                                               abs=1e-9)
        assert res["di_minus"] == pytest.approx(fx["expected"]["di_minus"],
                                                abs=1e-12)
        assert res["dx"] == pytest.approx(fx["expected"]["dx"], abs=1e-9)
        assert res["di_plus"] > res["di_minus"]
        assert res["warmup"] is fx["expected"]["warmup"]
        # §3.5: "ADX is NaN until t ≥ 2n" — 15 bars < 2·14 (ISSUE-CP4-018).
        assert res["warmup_2n"] is fx["expected"]["warmup_2n"] is True

    def test_fix05_mann_kendall_tie_correction(self):
        fx = BY_ID["FIX_05_MK_TIE"]
        S, var_s, z = mann_kendall_with_tie_correction(fx["bars_log"])
        assert S == pytest.approx(fx["expected"]["S"])
        assert var_s == pytest.approx(fx["expected"]["var_s"], abs=1e-9)
        assert z == pytest.approx(fx["expected"]["z_mk"], abs=1e-9)
        # Var(S) = [n(n−1)(2n+5) − Σ t(t−1)(2t+5)] / 18 with n = 15.
        n = len(fx["bars_log"])
        assert fx["expected"]["untied_var"] == pytest.approx(
            n * (n - 1) * (2 * n + 5) / 18, abs=1e-9)
        assert fx["expected"]["untied_var"] - fx["expected"]["var_s"] == \
            pytest.approx(fx["expected"]["correction"], abs=1e-9)
        assert fx["expected"]["mk_var_correction_nonzero"] is True

    def test_fix06_hurst_trending(self):
        fx = BY_ID["FIX_06_HURST_TRENDING"]
        assert fx["series"] == [60000.0 + 7.0 * i for i in range(128)]
        h, r2 = hurst_rs_anis_lloyd_corrected(fx["series"])
        assert h == pytest.approx(fx["expected"]["hurst"], abs=1e-9)
        assert h >= fx["expected"]["hurst_min"]
        assert r2 == pytest.approx(fx["expected"]["rsq"], abs=1e-9)

    def test_fix07_hurst_mean_reverting(self):
        fx = BY_ID["FIX_07_HURST_MEANREV"]
        assert len(fx["series"]) == 128
        assert set(fx["series"]) == {59995.0, 60005.0}
        h, r2 = hurst_rs_anis_lloyd_corrected(fx["series"])
        assert h == pytest.approx(fx["expected"]["hurst"], abs=1e-9)
        assert h <= fx["expected"]["hurst_max"]
        assert r2 == pytest.approx(fx["expected"]["rsq"], abs=1e-9)

    def test_fix08_exhaustion_divergence(self):
        fx = BY_ID["FIX_08_EXHAUSTION_DIV"]
        p = get_params()
        # At the governed lookback = 20 a 5-point momentum series cannot be
        # evaluated — the branch degrades instead of guessing.
        at_default = divergence_exhaustion_check(
            fx["price_swings"], fx["mom_series"], len(fx["price_swings"]) - 1,
            lookback=p.divergence_lookback)
        recorded = fx["expected"]["at_default_lookback_20"]
        assert at_default["is_exhaustion"] is recorded["is_exhaustion"] is False
        assert at_default["degraded"] is recorded["degraded"] is False
        assert at_default["degraded_reason"] == recorded["degraded_reason"]
        # Exercised explicitly at lookback = 5 (recorded in the fixture).
        res = divergence_exhaustion_check(
            fx["price_swings"], fx["mom_series"], len(fx["price_swings"]) - 1,
            lookback=fx["expected"]["lookback_used"])
        assert res["is_exhaustion"] is fx["expected"]["exhaustion"] is True
        assert res["type"] == fx["expected"]["type"]
        assert res["score"] == pytest.approx(fx["expected"]["score"])

    def test_fix09_stack_aligned(self):
        fx = BY_ID["FIX_09_STACK_ALIGNED"]
        dirs = {s: 1 for s in SCALES}
        bias = stack_bias(dirs)
        assert bias == pytest.approx(fx["expected"]["bias"])
        assert stack_alignment(bias, dirs) == fx["expected"]["alignment"]
        assert quality_aggregate({s: 1.0 for s in SCALES}) == pytest.approx(
            fx["expected"]["quality_agg_all_ones"])

    def test_fix10_quality_formula(self):
        fx = BY_ID["FIX_10_QUALITY_FORMULA"]
        q = compute_trend_quality(fx["r2"], fx["adx"], fx["hurst"])
        assert q == pytest.approx(fx["expected"]["Q"])
        assert q == pytest.approx(0.8 * 0.3 * 0.65)     # fx["expected"]["calc"]
        assert quality_label(q, fx["r2"], fx["adx"],
                             fx["hurst"]) == fx["expected"]["quality_label"]

    def test_fix11_edge_h_l_invalid(self):
        fx = BY_ID["FIX_11_EDGE_H_L_INVALID"]
        assert validate_bar(fx["bars"][0]) is False
        assert fx["expected"]["invalid"] is True
        for b in ramp(5):
            assert validate_bar(b) is True


# ---------------------------------------------------------------------------
# §3.1 the four formulas
# ---------------------------------------------------------------------------
class TestFormulas:
    def test_pos_scale_is_the_atr_normalised_distance(self):
        p = get_params()
        bars = ramp(5, start=100.0, step=1.0)
        sma = sum(b["c"] for b in bars) / 5
        pos = compute_pos_scale(bars, p.window_micro, 2.0)
        # §2 pos_s = (C_t − SMA_window)/max(ATR, ε) — an unbounded z, not a
        # bounded ratio.
        assert pos == pytest.approx((bars[-1]["c"] - sma) / 2.0, abs=1e-12)
        # No governed ATR ⇒ the ε floor keeps the quotient finite (degraded,
        # never a recomputed ATR).
        assert math.isfinite(compute_pos_scale(bars, p.window_micro, 0.0))
        assert compute_pos_scale([], p.window_micro, 1.0) == 0.0

    def test_seq_score_counts_only_confirmed_swings(self):
        swings = [
            {"type": "HH", "idx": 1, "confirmed_at_idx": 2},
            {"type": "HL", "idx": 3, "confirmed_at_idx": 4},
            {"type": "HH", "idx": 5, "confirmed_at_idx": 6},
        ]
        score, ev = compute_seq_score(swings, 10, 9)
        assert score == pytest.approx(1.0) and ev == 3
        down = [{"type": t, "idx": i, "confirmed_at_idx": i + 1}
                for i, t in enumerate(["LL", "LH", "LL"])]
        assert compute_seq_score(down, 10, 9)[0] == pytest.approx(-1.0)
        assert compute_seq_score([], 10, 9) == (0.0, 0)

    def test_pit_violation_raises(self):
        """§3.1/PIT: a swing confirmed after the evaluated bar is a leak."""
        # A swing confirmed AFTER the bar being evaluated is a look-ahead leak.
        swings = [{"type": "HH", "idx": 4, "confirmed_at_idx": 10}]
        with pytest.raises(ValueError, match="PIT_SWING_VIOLATION_QX"):
            compute_seq_score(swings, 10, 9, strict_pit=True)
        # Non-strict mode ignores the impossible confirmation instead.
        assert compute_seq_score(swings, 10, 9, strict_pit=False)[1] == 0
        assert PIT_LAG == 1

    def test_dedup_swings(self):
        swings = [{"type": "HH", "idx": 1, "confirmed_at_idx": 2},
                  {"type": "HH", "idx": 2, "confirmed_at_idx": 3},
                  {"type": "HL", "idx": 9, "confirmed_at_idx": 10}]
        assert len(dedup_swings(swings, 2)) == 2

    def test_direction_and_strength(self):
        p = get_params()
        d, strength, raw = trend_direction_and_strength(
            1.0, 3.0, 1.0, (p.w_a, p.w_b, p.w_c), p.strength_threshold,
            p.direction_deadband)
        assert d == 1
        assert raw == pytest.approx(0.4 + 0.35 * 3.0 + 0.25)
        assert strength == pytest.approx(1.0)          # clamped at 1
        d, strength, raw = trend_direction_and_strength(
            0.0, 0.0, 0.0, (0.4, 0.35, 0.25), 0.5, 0.05)
        assert d == 0 and strength == pytest.approx(0.0)
        # Deadband: a raw score inside ±0.05 must not create a direction.
        d2, _s2, raw2 = trend_direction_and_strength(
            0.0, 0.04, 0.0, (0.4, 0.35, 0.25), 0.5, 0.05)
        assert abs(raw2) < 0.05 and d2 == 0
        # Strength is clamped to [0, 1].
        _d, strength_hi, _r = trend_direction_and_strength(
            1.0, 50.0, 1.0, (0.4, 0.35, 0.25), 0.5, 0.05)
        assert 0.0 <= strength_hi <= 1.0

    def test_quality_formula_and_clip(self):
        # Q = R² · min(ADX/100, 1) · clip(H, 0, 1.2)/1.2
        # H ≤ 1.2 keeps its own value; H > 1.2 clips to 1.0 (§4 form,
        # ISSUE-CP4-016); the product is then clipped to [0, 1.5].
        assert compute_trend_quality(1.0, 100.0, 1.2) == pytest.approx(1.2)
        assert compute_trend_quality(1.0, 100.0, 2.0) == pytest.approx(1.0)
        assert compute_trend_quality(1.0, 100.0, -0.5) == pytest.approx(0.0)
        assert compute_trend_quality(1.5, 100.0, 1.2) <= 1.5
        assert compute_trend_quality(1.0, 50.0, 0.6) == pytest.approx(0.3)
        assert compute_trend_quality(0.0, 100.0, 1.0) == pytest.approx(0.0)

    def test_quality_ladder(self):
        p = get_params()
        assert quality_label(0.9, 0.5, 40.0, 0.8) == "Q4"
        assert quality_label(0.0, 0.5, 40.0, 0.8) == "Q0"
        assert quality_label(0.5, 0.1, 40.0, 0.8) in QUALITY_LABELS
        assert quality_label(0.5, 0.5, 5.0, 0.8) in QUALITY_LABELS


# ---------------------------------------------------------------------------
# §3.2 Mann–Kendall · §3.3 Newey–West · §3.4 Hurst
# ---------------------------------------------------------------------------
class TestStatistics:
    def test_mann_kendall_monotone_and_flat(self):
        S, var_s, z = mann_kendall_with_tie_correction(
            [float(i) for i in range(15)])
        assert S == 105.0                      # n(n−1)/2 for n = 15
        assert z > get_params().mk_crit_z
        flat = mann_kendall_with_tie_correction([1.0] * 15)
        assert flat[0] == 0.0 and flat[2] == pytest.approx(0.0)

    def test_mann_kendall_all_ties_var_is_zero(self):
        S, var_s, z = mann_kendall_with_tie_correction([5.0] * 10)
        assert S == 0.0 and var_s == pytest.approx(0.0)
        assert z == pytest.approx(0.0)

    def test_newey_west_lag_rule(self):
        # L = floor(4·(n/100)^(2/9))
        assert newey_west_lag(10) == 2
        assert newey_west_lag(100) == 4
        assert newey_west_lag(240) == 4
        assert newey_west_lag(1) == 1          # max(1, ·) floors the lag

    def test_ols_newey_west_recovers_the_slope(self):
        ts = [float(i) for i in range(50)]
        ys = [1.0 + 0.5 * t for t in ts]
        beta, se, r2 = ols_slope_newey_west(ts, ys)
        assert beta == pytest.approx(0.5, abs=1e-9)
        assert se >= 0.0 and r2 == pytest.approx(1.0, abs=1e-9)

    def test_ols_newey_west_inflates_se_under_autocorrelation(self):
        ts = [float(i) for i in range(60)]
        noise_free = [math.sin(i / 3.0) for i in range(60)]
        _b1, se_nw, _r1 = ols_slope_newey_west(ts, noise_free, lag_auto=True)
        _b2, se_ols, _r2 = ols_slope_newey_west(ts, noise_free, lag_auto=False)
        assert se_nw >= se_ols - 1e-12

    def test_ols_degenerate_inputs(self):
        # n < 3 or a length mismatch ⇒ (0, inf, 0): no slope is fabricated.
        beta, se, r2 = ols_slope_newey_west([1.0, 2.0], [1.0])
        assert beta == 0.0 and se == float("inf") and r2 == 0.0
        beta, se, r2 = ols_slope_newey_west([0.0], [1.0])
        assert beta == 0.0 and se == float("inf") and r2 == 0.0
        # Zero regressor variance is equally non-informative.
        beta, se, r2 = ols_slope_newey_west([2.0, 2.0, 2.0], [1.0, 2.0, 3.0])
        assert beta == 0.0 and se == float("inf")

    def test_hurst_needs_enough_points(self):
        p = get_params()
        h, r2 = hurst_rs_anis_lloyd_corrected([1.0, 2.0, 3.0, 4.0, 5.0],
                                              min_len=p.hurst_min_len)
        assert h == pytest.approx(0.5) and r2 == pytest.approx(0.0)

    def test_hurst_expected_rs_table(self):
        # E[R/S] = [Γ((n−1)/2)·(n−1)!] / [Γ(n/2)·(n−2)!·√(π/2)·(n−1)^1.5]·…
        # asserted against the chapter's own worked value.
        assert anis_lloyd_expected_rs(341) == pytest.approx(23.1439, abs=5e-3)
        assert anis_lloyd_expected_rs(128) < anis_lloyd_expected_rs(341)


# ---------------------------------------------------------------------------
# §3.5 ADX (the AD-line)
# ---------------------------------------------------------------------------
class TestADX:
    def test_wilder_rma_step(self):
        assert wilder_rma(10.0, 20.0, 10) == pytest.approx(11.0)
        assert wilder_rma(0.0, 0.0, 14) == pytest.approx(0.0)

    def test_directional_movement(self):
        up, down = directional_movement(12.0, 9.0, 10.0, 8.0)
        assert up == pytest.approx(2.0) and down == pytest.approx(0.0)
        up, down = directional_movement(9.0, 6.0, 10.0, 8.0)
        assert up == pytest.approx(0.0) and down == pytest.approx(2.0)
        up, down = directional_movement(11.0, 7.0, 10.0, 8.0)
        assert (up, down) == (1.0, 1.0) or (up, down) == (0.0, 0.0)

    def test_adx_warmup_flags(self):
        p = get_params()
        short = compute_adx_wilder(ramp(5), p.adx_n)
        assert short["warmup"] is True and short["warmup_2n"] is True
        warm = compute_adx_wilder(ramp(40), p.adx_n)
        assert warm["warmup"] is False and warm["warmup_2n"] is False
        assert 0.0 <= warm["adx"] <= 100.0

    def test_adx_empty_and_invalid_bars(self):
        res = compute_adx_wilder([], 14)
        assert res["adx"] == pytest.approx(0.0) and res["warmup"] is True
        broken = [b for b in ramp(20)]
        broken[5] = bar(1.0, 0.5, 2.0, 1.0, ts=broken[5]["ts"])   # H < L
        res2 = compute_adx_wilder(broken, 14)
        assert 0.0 <= res2["adx"] <= 100.0
        assert res2["warmup_2n"] is True

    def test_adx_scales_with_trend_purity(self):
        p = get_params()
        trending = compute_adx_wilder(ramp(60, step=1.0), p.adx_n)["adx"]
        choppy = ramp(60, step=1.0)
        for i in range(30, 60):
            choppy[i] = bar(2000.0 + (i % 2) * 1.0, 2002.0, 1998.0,
                            2000.0 + (i % 2), ts=choppy[i]["ts"])
        chop = compute_adx_wilder(choppy, p.adx_n)["adx"]
        assert trending > chop


# ---------------------------------------------------------------------------
# §3.6 divergence / exhaustion · §3.7 multi-TF stack
# ---------------------------------------------------------------------------
class TestDivergenceAndStack:
    def test_exhaustion_score_formula(self):
        # §3.7 ExhaustionScore = Div_binary · (1 − strength) · (1 − ADX/100).
        assert exhaustion_score(1.0, 0.85, 45.0) == pytest.approx(
            1.0 * 0.15 * 0.55, abs=1e-12)
        assert exhaustion_score(1.0, 0.85, 45.0) == pytest.approx(0.0825,
                                                                  abs=1e-9)
        assert exhaustion_score(0.0, 0.1, 5.0) == pytest.approx(0.0)
        assert exhaustion_score(1.0, 1.0, 100.0) == pytest.approx(0.0)

    def test_divergence_degrades_without_momentum(self):
        res = divergence_exhaustion_check(
            [{"type": "HH", "idx": 3, "confirmed_at_idx": 4, "price": 100.0}],
            None, 4)
        assert res["degraded"] is True
        assert res["degraded_reason"] == MOMENTUM_UNAVAILABLE_REASON
        assert res["is_exhaustion"] is False

    def test_bearish_divergence_detected(self):
        price_swings = [
            {"type": "HH", "idx": 2, "confirmed_at_idx": 3, "price": 100.0},
            {"type": "HH", "idx": 8, "confirmed_at_idx": 9, "price": 105.0},
        ]
        mom = [10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
        res = divergence_exhaustion_check(price_swings, mom, 9, lookback=10)
        assert res["is_exhaustion"] is True
        assert res["type"] == "BEARISH_DIVERGENCE"

    def test_no_divergence_when_momentum_confirms(self):
        price_swings = [
            {"type": "HH", "idx": 2, "confirmed_at_idx": 3, "price": 100.0},
            {"type": "HH", "idx": 8, "confirmed_at_idx": 9, "price": 105.0},
        ]
        mom = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        res = divergence_exhaustion_check(price_swings, mom, 9, lookback=10)
        assert res["is_exhaustion"] is False and res["degraded"] is False

    def test_stack_weights_sum_to_one(self):
        assert W_STACK_CORRECTED == {"MICRO": 0.1, "SHORT": 0.2,
                                     "INTER": 0.3, "MACRO": 0.4}
        assert sum(W_STACK_CORRECTED.values()) == pytest.approx(1.0)
        assert sum(scale_windows().values()) > 0

    def test_stack_bias_is_the_weighted_mean(self):
        dirs = {"MICRO": 1, "SHORT": 1, "INTER": -1, "MACRO": 1}
        expected = (0.1 + 0.2 - 0.3 + 0.4)
        assert stack_bias(dirs) == pytest.approx(expected)
        assert stack_bias({s: -1 for s in SCALES}) == pytest.approx(-1.0)
        assert stack_bias({s: 0 for s in SCALES}) == pytest.approx(0.0)
        with pytest.raises(ValueError, match="TREND_STACK_QX"):
            stack_bias({"MICRO": 1})                    # partial scale map
        with pytest.raises(ValueError, match="TREND_STACK_QX"):
            stack_bias({s: 1 for s in SCALES}, {"MICRO": 1.0})

    @pytest.mark.parametrize("dirs,expected", [
        ({"MICRO": 1, "SHORT": 1, "INTER": 1, "MACRO": 1}, "ALIGNED_BULL"),
        ({"MICRO": -1, "SHORT": -1, "INTER": -1, "MACRO": -1}, "ALIGNED_BEAR"),
        ({"MICRO": 1, "SHORT": -1, "INTER": 1, "MACRO": -1}, "CONFLICTING"),
        ({"MICRO": 0, "SHORT": 0, "INTER": 0, "MACRO": 0}, "SIDEWAYS"),
    ])
    def test_alignment_classes(self, dirs, expected):
        assert stack_alignment(stack_bias(dirs), dirs) == expected
        assert expected in ALIGNMENTS

    def test_alignment_bands_are_disjoint(self):
        p = get_params()
        # Bias = 0.1+0.2−0.3+0.4 = 0.4 sits between the SIDEWAYS band (≤ 0.3)
        # and the ALIGNED bands (> 0.5) ⇒ TRANSITIONING.
        dirs = {"MICRO": 1, "SHORT": 1, "INTER": -1, "MACRO": 1}
        bias = stack_bias(dirs)
        assert bias == pytest.approx(0.4)
        assert p.bias_sideways < bias <= p.bias_bull
        assert stack_alignment(bias, dirs) == "TRANSITIONING"
        # |Bias| ≤ 0.3 with a scale opposing MACRO ⇒ CONFLICTING, else SIDEWAYS
        opposed = {"MICRO": 1, "SHORT": 1, "INTER": 1, "MACRO": -1}
        assert stack_alignment(stack_bias(opposed), opposed) == "CONFLICTING"
        flat = {s: 0 for s in SCALES}
        assert stack_alignment(stack_bias(flat), flat) == "SIDEWAYS"

    def test_quality_aggregate_is_weighted(self):
        q = {"MICRO": 1.0, "SHORT": 0.0, "INTER": 0.0, "MACRO": 0.0}
        assert quality_aggregate(q) == pytest.approx(0.1)
        with pytest.raises(ValueError, match="TREND_STACK_QX"):
            quality_aggregate({"MICRO": 1.0})           # partial scale map
        with pytest.raises(ValueError, match="TREND_STACK_QX"):
            quality_aggregate(q, {"MICRO": 0.5, "SHORT": 0.5})


# ---------------------------------------------------------------------------
# §4 continuity · §5 state machine and schema
# ---------------------------------------------------------------------------
class TestContinuityAndState:
    def test_continuity_break_on_a_time_gap(self):
        bars = ramp(6)
        bars[-1] = dict(bars[-1])
        bars[-1]["ts"] = bars[-2]["ts"] + 10 * 3600000        # 10 h gap
        assert continuity_break(bars, 3600, 2.0) is True
        assert continuity_break(ramp(6), 3600, 2.0) is False

    def test_scale_state_matrix(self):
        # §5.3 UNKNOWN → CALCULATING → VALID → DEGRADED → INVALID.
        assert scale_state("Q4", 3, 40.0, 0.9, False, True) == "VALID"
        assert scale_state("Q0", 3, 40.0, 0.9, False, True) == "DEGRADED"
        assert scale_state("Q4", 3, 40.0, 0.9, True, True) == "DEGRADED"
        assert scale_state("Q4", 3, 0.0, 0.1, False, True) == "DEGRADED"
        assert scale_state("Q4", 3, 40.0, 0.9, False, False) == "INVALID"
        # Enough evidence and ADX, but below the evidence floor ⇒ CALCULATING.
        assert scale_state("Q2", 1, 40.0, 0.9, False, True) == "CALCULATING"
        for state in ("VALID", "DEGRADED", "INVALID", "CALCULATING"):
            assert state in SCALE_STATES

    def test_trend_scale_schema_validation(self):
        p = get_params()
        eng = TrendEngine()
        obj = eng._scale_state(ramp(20), None, 1.0, p.window_micro, "MICRO",
                               3600)
        obj.validate_schema()
        record = obj.to_dict()
        # Every §5.1 required key is published, not just the stack subset.
        missing = [k for k in TREND_SCALE_REQUIRED if k not in record]
        assert missing == []
        assert record["scale"] == "MICRO"
        assert record["contract_version"] == CONTRACT_VERSION
        assert len(record["snapshot_id"]) == 64

    def test_schema_rejects_an_invalid_direction(self):
        obj = TrendScale(scale="MICRO", direction=2, strength=0.5, quality=0.5,
                         quality_label="Q2", seq_score=0.0, slope_z=0.0,
                         pos=0.0, r2=0.0, adx=0.0, di_plus=0.0, di_minus=0.0,
                         hurst=0.5, mk_z=0.0, evidence_count=1, as_of=0,
                         snapshot_id="")
        with pytest.raises(ValueError, match="TREND_SCALE_QX"):
            obj.validate_schema()

    def test_stack_payload_shape(self):
        res = run_engine(ramp(20), atr=1.0)
        # §5.2 TrendStack: every TREND_STACK_REQUIRED key is published.
        missing = [k for k in TREND_STACK_REQUIRED if k not in res]
        assert missing == []
        assert set(res["stack"]) == set(SCALES)
        assert set(res["stack_snapshot"]) == set(SCALES)
        assert res["alignment"] in ALIGNMENTS
        assert -1.0 <= res["bias"] <= 1.0
        assert len(res["snapshot_id"]) == 64
        assert res["contract_version"] == CONTRACT_VERSION
        assert res["engine"] == ENGINE


# ---------------------------------------------------------------------------
# §6 parameters · §7 events · honest-label degradation
# ---------------------------------------------------------------------------
class TestParamsAndEvents:
    def test_defaults_are_the_chapter_literals(self):
        p = get_params()
        assert (p.window_micro, p.window_short, p.window_inter,
                p.window_macro) == (5, 20, 60, 240)
        assert (p.w_a, p.w_b, p.w_c) == (0.4, 0.35, 0.25)
        assert (p.slope_z_threshold, p.pos_threshold) == (1.5, 0.3)
        assert (p.adx_n, p.mk_crit_z, p.hurst_window) == (14, 1.96, 128)
        assert (p.divergence_lookback, p.divergence_score) == (20, 0.8)
        assert p.hurst_clip_max == 1.2
        assert set(E09_DEFAULTS) == set(p.__dict__)

    def test_unknown_param_rejected(self):
        with pytest.raises(ValueError, match="UNKNOWN_E09_PARAM_QX"):
            get_params({"window_micro_typo": 5})
        assert get_params({"window_micro": 7}).window_micro == 7

    def test_event_catalog_is_complete(self):
        assert set(EVENT_CATALOG) == {f"EV_TRD_{i:03d}" for i in range(1, 9)}

    def test_stack_aligned_event_emitted(self):
        res = run_engine(ramp(60, step=2.0), atr=1.0)
        codes = [e["code"] for e in res["events"]]
        assert "EV_TRD_005" in codes
        assert res["alignment"] == "ALIGNED_BULL"

    def test_oi_missing_is_labelled_not_fabricated(self):
        res = run_engine(ramp(20), atr=1.0, oi_state="MISSING")
        assert res["oi_state"] == "MISSING"
        deg = [e for e in res["events"] if e["code"] == "EV_TRD_008"]
        assert deg and deg[0]["reason"] == OI_MISSING_REASON
        with pytest.raises(ValueError, match="OI_STATE_QX"):
            run_engine(ramp(20), atr=1.0, oi_state="NOPE")

    def test_swings_absent_degrades_the_sequence_term(self):
        p = get_params()
        eng = TrendEngine()
        obj = eng._scale_state(ramp(20), None, 1.0, p.window_micro, "MICRO",
                               3600)
        assert obj.seq_score == pytest.approx(0.0)
        assert obj.degraded_reason == SWINGS_UNAVAILABLE_REASON

    def test_no_stub_placeholders_in_wave_in_code(self):
        src = (pathlib.Path(__file__).resolve().parents[2] / "apex" / "engines"
               / "e09_trend" / "engine.py").read_text()
        for token in ("TODO", "FIXME", "NotImplementedError"):
            assert token not in src


# ---------------------------------------------------------------------------
# Determinism · EngineBase binding · T-DR-001
# ---------------------------------------------------------------------------
def _obs_window(bars, tf="1h"):
    obs = []
    for i, b in enumerate(bars):
        ts = "2026-01-%02dT%02d:00:00.000Z" % (1 + (i * 1) // 24, i % 24)
        obs.append(MarketObservation(
            symbol="BTCUSDT", timeframe=tf,
            open=Decimal(str(b["o"])), high=Decimal(str(b["h"])),
            low=Decimal(str(b["l"])), close=Decimal(str(b["c"])),
            volume=Decimal(str(b.get("v", 1000.0))), oi=None,
            timestamp=ts, sequence=i, status="CLOSED"))
    return obs


class TestDeterminismAndBinding:
    def test_snapshot_is_content_bound(self):
        a = {"bias": 1.0, "alignment": "ALIGNED_BULL"}
        b = {"bias": 1.0, "alignment": "ALIGNED_BULL"}
        c = {"bias": 0.9, "alignment": "ALIGNED_BULL"}
        assert e09_snapshot_id(a) == e09_snapshot_id(b)
        assert e09_snapshot_id(a) != e09_snapshot_id(c)
        assert len(e09_snapshot_id(a)) == 64

    def test_replay_is_byte_identical(self):
        bars = ramp(60, step=2.0)
        swings = [{"type": "HH", "idx": 10, "confirmed_at_idx": 11},
                  {"type": "HL", "idx": 20, "confirmed_at_idx": 21},
                  {"type": "HH", "idx": 30, "confirmed_at_idx": 31}]
        a = run_engine(bars, swings=swings, atr=1.0)
        b = run_engine(bars, swings=swings, atr=1.0)
        assert json.dumps(a, sort_keys=True, default=str) == json.dumps(
            b, sort_keys=True, default=str)

    def test_pearson_helper(self):
        # §8.6 redundancy statistic: |r| > 0.85 ⇒ components are redundant.
        assert pearson([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == pytest.approx(1.0)
        assert pearson([1.0, 2.0, 3.0], [6.0, 4.0, 2.0]) == pytest.approx(-1.0)
        # Zero variance or a length mismatch ⇒ 0.0 (not NaN, not a guess).
        assert pearson([1.0, 1.0], [1.0, 2.0]) == 0.0
        assert pearson([1.0], [1.0]) == 0.0
        assert abs(pearson([1.0, 2.0, 3.0, 4.0], [1.1, 1.9, 3.2, 3.8])) > 0.85

    def test_wilson_ci_bounds(self):
        lo, hi = wilson_ci(0.8, 40)
        assert 0.0 <= lo < 0.8 < hi <= 1.0
        assert wilson_ci(0.5, 0) == (0.0, 0.0)

    def test_missing_window_fails_closed(self):
        with pytest.raises(ValueError, match="MISSING_WINDOW_CONTEXT_QX"):
            E09TrendEngine().compute("BTCUSDT", "1h", "2026-01-15T00:00:00Z",
                                     {})

    def test_empty_window_emits_nothing(self):
        assert E09TrendEngine().compute("BTCUSDT", "1h",
                                        "2026-01-15T00:00:00Z",
                                        {"window": []}) == []

    def test_compute_emits_one_event_per_scale(self):
        bars = ramp(30, step=1.5)
        evs = E09TrendEngine().compute(
            "BTCUSDT", "1h", "2026-01-15T00:00:00Z",
            {"window": _obs_window(bars), "atr": 1.0,
             "swings": [{"type": "HH", "idx": 5, "confirmed_at_idx": 6},
                        {"type": "HL", "idx": 10, "confirmed_at_idx": 11}]})
        assert len(evs) == len(SCALES)
        for ev in evs:
            ev.validate_24_fields()
            assert ev.engine_id == "E09"
            assert ev.direction in (-1, 0, 1)
            assert ev.resolution_class in QUALITY_LABELS
            assert ev.parameter_version == "E09-TRD-V4.0.0/DEFAULTS-v1"
            assert ev.condition_state.startswith("TREND_")

    def test_compute_rejects_unknown_params(self):
        with pytest.raises(ValueError, match="UNKNOWN_E09_PARAM_QX"):
            E09TrendEngine().compute("BTCUSDT", "1h", "2026-01-15T00:00:00Z",
                                     {"window": _obs_window(ramp(20)),
                                      "e09_params": {"nope": 1}})

    def test_t_dr_001_deterministic_replay(self):
        """T-DR-001: identical emissions on re-run over identical inputs."""
        bars = ramp(40, step=1.2)
        ctx = {"window": _obs_window(bars), "atr": 1.0}
        a = E09TrendEngine().compute("BTCUSDT", "1h", "2026-01-15T00:00:00Z",
                                     ctx)
        b = E09TrendEngine().compute("BTCUSDT", "1h", "2026-01-15T00:00:00Z",
                                     ctx)
        assert [e.snapshot_id for e in a] == [e.snapshot_id for e in b]
        assert [e.condition_state for e in a] == [e.condition_state for e in b]
        assert [e.direction for e in a] == [e.direction for e in b]
        assert [e.strength for e in a] == [e.strength for e in b]
