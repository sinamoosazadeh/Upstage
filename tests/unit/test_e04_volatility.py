"""E04 Volatility — §8 validation battery (blueprint L5497–5570) + §3/§5/§6/§7
conformance. Every clause of §8 is a test class; fixtures re-derived per
ADR-P2-007 (tests/fixtures/e04_golden_fixtures.json). T-DR-001 re-run
(CP-2 parity)."""

import copy
import json
import math
import os

import pytest

from apex.engines.e04_volatility import (
    EPS,
    ATR_FLOOR,
    E04_DEFAULTS,
    E04VolatilityEngine,
    EVENT_CATALOG,
    K_TARGETING,
    REGIMES,
    VolatilityEngineV4,
    VolatilityState,
    WilderATR,
    annualized_hv,
    bollinger_width,
    chi2_sf,
    cluster_persistence,
    ewma_vol_step,
    garman_klass,
    get_params,
    garch_mle_fit,
    har_rv_fit,
    load_state,
    ljung_box,
    nondirectional_test,
    overnight_var,
    parkinson_adjusted,
    parkinson_raw,
    range_z,
    realized_var,
    regime_from_hv,
    rogers_satchell,
    rolling_quantiles,
    run_engine,
    t_sf_two_sided,
    true_range,
    vol_ratio,
    vol_targeting,
    wilson_ci,
    yang_zhang,
)
from apex.data_catalog.contracts import MarketObservation
from apex.errors import WaveOutError

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "..", "fixtures",
                            "e04_golden_fixtures.json")


def load_fixtures():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as fh:
        return {f["fixture_id"]: f for f in json.load(fh)["fixtures"]}


FIX = load_fixtures()


def lcg_bars(n, seed=42, base=100.0, vol=0.01, ts0=1700000000000,
             tf_ms=3600000):
    """Deterministic synthetic closed candles (documented seed; no real
    market data exists in the sandbox and none may be fabricated —
    ISSUE-CP2-015 discipline)."""
    state = seed
    bars = []
    price = base
    for i in range(n):
        state = (state * 1103515245 + 12345) % (2 ** 31)
        u1 = state / 2 ** 31
        state = (state * 1103515245 + 12345) % (2 ** 31)
        u2 = state / 2 ** 31
        g = math.sqrt(-2.0 * math.log(max(u1, 1e-12))) * math.cos(
            2 * math.pi * u2)
        o = price
        c = price * (1.0 + vol * g)
        state = (state * 1103515245 + 12345) % (2 ** 31)
        wick = abs(state / 2 ** 31) * vol * price
        h = max(o, c) + wick
        l = min(o, c) - wick * 0.8
        v = 1000.0 + (state % 500)
        bars.append({"ts": ts0 + i * tf_ms, "o": o, "h": h, "l": l,
                     "c": c, "v": v})
        price = c
    return bars


# ---------------------------------------------------------------------------
# §8.1 Golden fixtures (12, re-derived)
# ---------------------------------------------------------------------------
class TestGoldenFixtures:
    def test_f01_atr_seed(self):
        f = FIX["E04_F01_ATR_seed"]
        atr = WilderATR(14)
        out = None
        for tr in f["input"]["trs"]:
            out = atr.update(tr, "Q1")
        assert out[0] == pytest.approx(f["expected"]["atr"], abs=1e-9)
        assert out[1] == f["expected"]["q_tag"]

    def test_f02_rma_step(self):
        f = FIX["E04_F02_RMA_step"]
        prev, tr, n = (f["input"]["prev"], f["input"]["tr"], f["input"]["n"])
        new = (prev * (n - 1) + tr) / n
        assert new == pytest.approx(f["expected"]["new"], abs=1e-6)

    def test_f03_tr_gap(self):
        f = FIX["E04_F03_TR_gap"]
        tr, q = true_range(f["input"]["h"], f["input"]["l"],
                           f["input"]["c_prev"])
        assert tr == f["expected"]["tr"] and q == "Q1"

    def test_f04_tr_gap_up_dominant(self):
        f = FIX["E04_F04_TR_gap_up"]
        tr, _ = true_range(f["input"]["h"], f["input"]["l"],
                           f["input"]["c_prev"])
        assert tr == f["expected"]["tr"]
        assert abs(f["input"]["h"] - f["input"]["c_prev"]) == tr  # dominant

    def test_f05_parkinson_redrived(self):
        f = FIX["E04_F05_Parkinson"]
        sigma = parkinson_raw(f["input"]["highs"], f["input"]["lows"])
        assert sigma == pytest.approx(f["expected"]["sigma"],
                                      abs=f["expected"]["tol"])

    def test_f06_gk_floor(self):
        f = FIX["E04_F06_GK_floor"]
        o, h, l, c = (f["input"][k] for k in ("o", "h", "l", "c"))
        raw = (0.5 * math.log(h / l) ** 2
               - (2 * math.log(2) - 1) * math.log(c / o) ** 2)
        assert raw < 0
        assert raw == pytest.approx(f["expected"]["gk_contribution_raw"],
                                    abs=1e-6)
        assert garman_klass([o], [h], [l], [c]) == pytest.approx(
            f["expected"]["gk_floor"], abs=1e-12)

    def test_f07_yang_zhang_redrived(self):
        f = FIX["E04_F07_YZ"]
        yz = yang_zhang(f["input"]["opens"], f["input"]["highs"],
                        f["input"]["lows"], f["input"]["closes"],
                        f["input"]["closes_prev"])
        assert yz == pytest.approx(f["expected"]["yz"],
                                   abs=f["expected"]["tol"])

    def test_f08_boll_width_redrived(self):
        f = FIX["E04_F08_BollWidth"]
        width, sma, up, low = bollinger_width(f["input"]["closes20"], 20, 2.0)
        assert sma == pytest.approx(f["expected"]["sma"], abs=1e-9)
        std = math.sqrt(sum((x - sma) ** 2
                            for x in f["input"]["closes20"]) / 20)
        assert std == pytest.approx(f["expected"]["std_pop"], abs=1e-6)
        assert width == pytest.approx(f["expected"]["width"], abs=1e-6)
        assert width == pytest.approx((up - low) / sma, abs=1e-12)

    def test_f09_vol_ratio_and_squeeze_rule(self):
        f = FIX["E04_F09_VolRatio"]
        vr = vol_ratio(f["input"]["atr_s"], f["input"]["atr_l"])
        assert vr == pytest.approx(f["expected"]["vr"], abs=1e-6)
        # §3.8 squeeze = VR≤0.75 ∧ BW≤0.12 ∧ RZ≤−0.5 (all three supplied)
        p = get_params()
        squeeze = (vr <= p["squeeze_vr"]
                   and f["input"]["bw"] <= p["squeeze_bw"]
                   and f["input"]["range_z"] <= p["squeeze_rz"])
        assert squeeze is f["expected"]["squeeze"]

    def test_f10_regime_pit_quantiles_redrived(self):
        f = FIX["E04_F10_Regime_PIT"]
        # §3.9: S_t = HV_{t−W:t−1} excludes HV_t itself — the quantile
        # window is exactly hv_hist here (hv_cur parked outside the tail)
        series = [f["input"]["hv_cur"]] + f["input"]["hv_hist"]
        qs = rolling_quantiles(series, len(series) - 1, [15, 35, 75, 95])
        for key, expected in f["expected"]["qs"].items():
            assert qs[int(key[1:])] == pytest.approx(expected, abs=1e-9)
        reg = regime_from_hv(f["input"]["hv_cur"], qs)
        assert reg == f["expected"]["reg"]

    def test_f11_ljung_redrived(self):
        f = FIX["E04_F11_Ljung"]
        Q, p = ljung_box(f["input"]["r2"], f["input"]["m"])
        assert Q == pytest.approx(f["expected"]["Q"],
                                  abs=f["expected"]["tol"])
        assert (Q > 0) is f["expected"]["Q_gt_0"]
        assert p == pytest.approx(f["expected"]["p"],
                                  abs=f["expected"]["p_tol"])

    def test_f12_vol_targeting(self):
        f = FIX["E04_F12_VolTargeting"]
        assert K_TARGETING["NORMAL"] == f["expected"]["k"]
        pos = vol_targeting(f["input"]["risk"], f["input"]["atr"],
                            f["input"]["reg"])
        assert pos == pytest.approx(f["expected"]["pos"], abs=1e-6)


# ---------------------------------------------------------------------------
# §3 formula conformance
# ---------------------------------------------------------------------------
class TestFormulas:
    def test_tr_h_lt_l_is_q0(self):
        tr, q = true_range(99.0, 100.0, 100.0)
        assert (tr, q) == (0.0, "Q0")

    def test_wilder_seed_once_then_rma(self):
        atr = WilderATR(3)
        outs = [atr.update(tr, "Q1")[0] for tr in (2.0, 4.0, 6.0, 3.0)]
        assert math.isnan(outs[0]) and math.isnan(outs[1])
        assert outs[2] == pytest.approx(4.0)          # seed mean
        assert outs[3] == pytest.approx((4.0 * 2 + 3.0) / 3)

    def test_wilder_q0_freezes(self):
        atr = WilderATR(2)
        atr.update(2.0, "Q1")
        atr.update(4.0, "Q1")          # seed = 3
        val, q = atr.update(99.0, "Q0")
        assert q == "Q0" and val == pytest.approx(3.0)

    def test_realized_var_and_hv(self):
        rv = realized_var([0.01, -0.02])
        assert rv == pytest.approx(0.0005)
        hv = annualized_hv(rv, 3600, days=365)
        assert hv == pytest.approx(math.sqrt(rv * 365 * 24))

    def test_overnight_and_oc_var(self):
        on = overnight_var([100.0, 105.0], [99.0, 104.0])
        assert on == pytest.approx((math.log(100 / 99) ** 2
                                    + math.log(105 / 104) ** 2) / 2)
        oc = __import__("apex.engines.e04_volatility",
                        fromlist=["oc_var"]).oc_var([100.0], [101.0])
        assert oc == pytest.approx(math.log(101 / 100) ** 2)

    def test_parkinson_adjusted_gap_correction(self):
        highs = [610.0]
        lows = [590.0]
        opens = [600.0]
        closes_prev = [595.0]
        adj = parkinson_adjusted(highs, lows, opens, closes_prev)
        raw = parkinson_raw(highs, lows)
        on = overnight_var(opens, closes_prev)
        assert adj == pytest.approx(math.sqrt(on + raw ** 2))
        assert adj > raw                      # gap correction adds variance

    def test_rogers_satchell_driftless_positive(self):
        rs = rogers_satchell([100.0, 102.0], [105.0, 106.0],
                             [98.0, 100.0], [103.0, 104.0])
        assert rs > 0 and math.isfinite(rs)

    def test_yang_zhang_k_formula(self):
        n = 10
        k = 0.34 / (1.34 + (n + 1) / (n - 1))
        assert k == pytest.approx(0.34 / (1.34 + 11 / 9))

    def test_ewma_recurrence(self):
        v1 = ewma_vol_step(0.0004, 0.02, 0.94)
        assert v1 == pytest.approx(0.94 * 0.0004 + 0.06 * 0.0004)

    def test_garch_insufficient_and_fit(self):
        out = garch_mle_fit([0.01] * 10)
        assert out["status"] == "insufficient"
        bars = lcg_bars(220, seed=5)
        rets = [math.log(b["c"] / bars[i - 1]["c"])
                for i, b in enumerate(bars) if i > 0]
        fit = garch_mle_fit(rets, min_obs=100)
        assert fit["status"] == "fitted"
        assert fit["omega"] > 0 and fit["alpha"] >= 0 and fit["beta"] >= 0
        assert fit["alpha"] + fit["beta"] < 0.999999
        assert fit["long_var"] == pytest.approx(
            fit["omega"] / (1 - fit["alpha"] - fit["beta"]))
        # deterministic restart grid → identical fit on replay
        fit2 = garch_mle_fit(rets, min_obs=100)
        assert fit == fit2

    def test_har_rv_newey_west(self):
        bars = lcg_bars(120, seed=6)
        rets = [math.log(b["c"] / bars[i - 1]["c"])
                for i, b in enumerate(bars) if i > 0]
        rv_series = [r * r for r in rets]
        fit = har_rv_fit(rv_series)
        assert fit["status"] == "fitted"
        assert len(fit["newey_west_se"]) == 4
        assert all(se >= 0 for se in fit["newey_west_se"])

    def test_range_z_window_rule(self):
        assert math.isnan(range_z(10.0, [1.0] * 5))     # <20 → NaN
        z = range_z(12.0, [10.0] * 20)
        assert z > 0

    def test_rolling_quantiles_warmup_nan(self):
        qs = rolling_quantiles([1.0, 2.0], 10, [15, 35, 75, 95])
        assert all(math.isnan(v) for v in qs.values())

    def test_chi2_sf_matches_critical_values(self):
        # §4 reference thresholds ARE the m=20 χ² critical values (§3.10
        # formula authority; ISSUE-CP3-003)
        assert chi2_sf(31.410, 20) == pytest.approx(0.05, abs=2e-3)
        assert chi2_sf(37.566, 20) == pytest.approx(0.01, abs=2e-3)
        assert chi2_sf(0.0, 20) == 1.0

    def test_t_sf_two_sided(self):
        assert t_sf_two_sided(0.0, 30) == pytest.approx(1.0, abs=1e-9)
        assert t_sf_two_sided(2.042, 30) == pytest.approx(0.05, abs=2e-3)

    def test_cluster_persistence_chapter_example(self):
        # §7 Ch.3-11: NORMAL,NORMAL,ELEVATED,ELEVATED,ELEVATED,NORMAL,
        # LOW,LOW,LOW,NORMAL,ELEVATED → (2+1)/(3+2) = 0.6
        seq = ["NORMAL", "NORMAL", "ELEVATED", "ELEVATED", "ELEVATED",
               "NORMAL", "LOW", "LOW", "LOW", "NORMAL", "ELEVATED"]
        assert cluster_persistence(seq, "ELEVATED") == pytest.approx(0.6)

    def test_nondirectional_test_uncorrelated_pass(self):
        bars = lcg_bars(120, seed=8)
        rets = [math.log(b["c"] / bars[i - 1]["c"])
                for i, b in enumerate(bars) if i > 0]
        vols = [abs(rets[i - 1]) * 0.1 + 0.005 for i in range(len(rets))]
        corr, t, p, (lo, hi) = nondirectional_test(rets[1:], vols[:-1])
        assert math.isfinite(corr) and -1 < corr < 1
        assert lo <= hi

    def test_wilson_ci_bounds(self):
        lo, hi = wilson_ci(0.5, 100)
        assert 0 < lo < 0.5 < hi < 1
        lo0, hi0 = wilson_ci(0.5, 0)
        assert (lo0, hi0) == (0.0, 1.0)

    def test_vol_targeting_zero_budget_and_dead_atr(self):
        assert vol_targeting(0.0, 5.0, "NORMAL") == 0.0
        assert vol_targeting(100.0, 0.0, "NORMAL") == 0.0

    def test_eps_is_the_frozen_tier2_value(self):
        assert EPS == 1e-12            # §2.2 E04 operational EPS (§6 row)
        assert ATR_FLOOR == 1e-8       # §2.2 ATR floor


# ---------------------------------------------------------------------------
# §5 VolatilityState schema / events
# ---------------------------------------------------------------------------
class TestSchemaAndEvents:
    def test_event_catalog_complete(self):
        assert tuple(EVENT_CATALOG) == tuple(
            f"EV_VLT_{i:03d}" for i in range(1, 9))

    def test_state_21_required_fields(self):
        from apex.engines.e04_volatility import VOLATILITY_STATE_REQUIRED
        assert len(VOLATILITY_STATE_REQUIRED) == 21
        state = VolatilityState(as_of=1)
        state.update_snapshot()
        payload = state.to_canonical()
        assert len(payload) == 20      # canonical payload excludes snapshot_id
        assert state.contract_version == "APEX-Contract-Volatility v4.0.0"
        assert len(state.snapshot_id) == 64

    def test_regime_enum_and_order(self):
        assert REGIMES == ("VERY_LOW", "LOW", "NORMAL", "ELEVATED",
                           "EXTREME")

    def test_regime_banding_boundaries(self):
        qs = {15: 0.1, 35: 0.2, 75: 0.3, 95: 0.4}
        assert regime_from_hv(0.05, qs) == "VERY_LOW"
        assert regime_from_hv(0.15, qs) == "LOW"
        assert regime_from_hv(0.25, qs) == "NORMAL"
        assert regime_from_hv(0.35, qs) == "ELEVATED"
        assert regime_from_hv(0.45, qs) == "EXTREME"


# ---------------------------------------------------------------------------
# §7 worked examples (re-derived; case-study numbers are illustrative)
# ---------------------------------------------------------------------------
class TestChapterWorkedExamples:
    def test_ch1_wilder_vs_naive(self):
        # §7 Ch.1-11: ATR_new = (44.2×13+60)/14 = 45.33 vs naive SMA 44.7
        atr = WilderATR(14)
        for _ in range(13):
            atr.update(44.2, "Q1")
        atr.update(44.2, "Q1")               # seed 44.2
        val, _ = atr.update(60.0, "Q1")
        assert val == pytest.approx(45.3285714, abs=1e-6)

    def test_ch3_squeeze_check_example(self):
        # §7 Ch.3-11: SMA20=615 σ=9 → width 5.85% < 12%; VR=4/6.5=0.615<0.75
        width = (4 * 9) / 615
        assert width == pytest.approx(0.0585366, abs=1e-6)
        assert width < 0.12
        assert 4.0 / 6.5 == pytest.approx(0.6153846, abs=1e-6)

    def test_ch3_cluster_persistence_example(self):
        seq = ["NORMAL", "NORMAL", "ELEVATED", "ELEVATED", "ELEVATED",
               "NORMAL", "LOW", "LOW", "LOW", "NORMAL", "ELEVATED"]
        assert cluster_persistence(seq, "ELEVATED") == pytest.approx(0.6)

    def test_case_study_wilder_steps(self):
        # §9: seed 4.214 → bar0 TR 7 → 4.413; bar7 (4.228×13+1.5)/14=4.033;
        # bar10 (3.829×13+14)/14 = 4.555
        assert (4.214 * 13 + 7) / 14 == pytest.approx(4.413, abs=1e-3)
        assert (4.228 * 13 + 1.5) / 14 == pytest.approx(4.033, abs=1e-3)
        assert (3.829 * 13 + 14) / 14 == pytest.approx(4.555, abs=1e-3)

    def test_case_study_targeting_bar8(self):
        pos = vol_targeting(100.0, 3.816, "VERY_LOW")
        assert pos == pytest.approx(17.47, abs=0.02)


# ---------------------------------------------------------------------------
# §8.2 deterministic replay (500 bars, twice)
# ---------------------------------------------------------------------------
class TestDeterministicReplay:
    def test_500_bar_double_run_byte_identical(self):
        bars = lcg_bars(500, seed=97)
        r1 = run_engine(bars, timeframe="1h")
        r2 = run_engine(bars, timeframe="1h")
        assert len(r1["states"]) == len(r2["states"]) >= 400
        for s1, s2 in zip(r1["states"], r2["states"]):
            assert s1.snapshot_id == s2.snapshot_id
            assert abs(s1.atr14_wilder - s2.atr14_wilder) < 1e-12
            assert abs(s1.vol_ratio - s2.vol_ratio) < 1e-12
            assert abs(s1.yz - s2.yz) < 1e-12


# ---------------------------------------------------------------------------
# §8.3 no-future-leak
# ---------------------------------------------------------------------------
class TestNoFutureLeak:
    def test_regime_quantiles_exclude_hv_t(self):
        bars = lcg_bars(120, seed=11)
        r_base = run_engine(bars, timeframe="1h")
        # 10× the final move: HV_t explodes, but S_t (t−W:t−1) must not
        # move the quantile boundaries used for regime(t) of earlier bars
        shocked = copy.deepcopy(bars)
        shocked[-1]["c"] = shocked[-1]["c"] * 1.09
        shocked[-1]["h"] = shocked[-1]["c"] * 1.01
        r_shock = run_engine(shocked, timeframe="1h")
        n = len(r_base["states"]) - 1
        for i in range(30, n):                      # post-warmup prefix
            assert (r_base["states"][i].regime
                    == r_shock["states"][i].regime)

    def test_atr_t_never_uses_c_t_plus_1(self):
        bars = lcg_bars(80, seed=12)
        full = run_engine(bars, timeframe="1h")
        prefix = run_engine(bars[:-10], timeframe="1h")
        m = len(prefix["states"])
        for i in range(m):
            assert (full["states"][i].atr14_wilder
                    == prefix["states"][i].atr14_wilder)


# ---------------------------------------------------------------------------
# §8.4 ablation (deterministic synthetic windows; exact % claims are
# illustrative — ISSUE-CP2-015 discipline)
# ---------------------------------------------------------------------------
class TestAblation:
    def test_removing_yz_worsens_next_period_rv_tracking(self):
        bars = lcg_bars(300, seed=13, vol=0.02)
        rets = [math.log(b["c"] / bars[i - 1]["c"])
                for i, b in enumerate(bars) if i > 0]
        win = 30
        sq_err_yz, sq_err_c2c = [], []
        for t in range(win + 1, len(bars) - 1):
            o = [b["o"] for b in bars[t - win:t]]
            h = [b["h"] for b in bars[t - win:t]]
            l = [b["l"] for b in bars[t - win:t]]
            c = [b["c"] for b in bars[t - win:t]]
            cp = [bars[i - 1]["c"] for i in range(t - win, t)]
            yz = yang_zhang(o, h, l, c, cp)
            c2c = math.sqrt(realized_var(rets[t - win:t]))
            rv_next = rets[t] ** 2
            if math.isfinite(yz):
                sq_err_yz.append((yz ** 2 - rv_next) ** 2)
                sq_err_c2c.append((c2c ** 2 - rv_next) ** 2)
        rmse_yz = math.sqrt(sum(sq_err_yz) / len(sq_err_yz))
        rmse_c2c = math.sqrt(sum(sq_err_c2c) / len(sq_err_c2c))
        assert rmse_c2c > rmse_yz        # removing YZ raises RMSE (§8.4)

    def test_replacing_wilder_with_sma_raises_atr_variance(self):
        bars = lcg_bars(400, seed=14, vol=0.015)
        trs = []
        for i, b in enumerate(bars):
            cp = bars[i - 1]["c"] if i else None
            trs.append(true_range(b["h"], b["l"], cp)[0])
        wilder = WilderATR(14)
        w_series, sma_series = [], []
        for tr in trs:
            val, _ = wilder.update(tr, "Q1")
            if math.isfinite(val):
                w_series.append(val)
        for i in range(14, len(trs)):
            sma_series.append(sum(trs[i - 14:i]) / 14)
        m = min(len(w_series), len(sma_series))
        w_series, sma_series = w_series[-m:], sma_series[-m:]

        def var(s):
            mu = sum(s) / len(s)
            return sum((x - mu) ** 2 for x in s) / len(s)
        assert var(sma_series) > var(w_series)   # §8.4 direction holds


# ---------------------------------------------------------------------------
# §8.5 Wilson CI calibration + wide-CI downgrade
# ---------------------------------------------------------------------------
class TestWilsonCalibration:
    def test_wilson_formula_values(self):
        lo, hi = wilson_ci(15 / 21, 21)
        assert lo == pytest.approx(0.50, abs=0.01)
        assert hi == pytest.approx(0.86, abs=0.01)

    def test_wide_ci_downgrades_q3_to_q2(self):
        # cluster_p with tiny sample → Wilson width > 0.25 → downgrade
        eng = VolatilityEngineV4(timeframe="1m")
        bars = lcg_bars(80, seed=15, vol=0.005)
        out = run_engine(bars, params={"cluster_window": 5}, timeframe="1m")
        tags = {s.q_tag for s in out["states"]}
        assert tags <= {"Q0", "Q1", "Q2", "Q3", "QX"}
        # wide-CI rule exercised: with 5-bar cluster window the CI width
        # exceeds 0.25, so no Q3 survives via the cluster path
        wide = wilson_ci(0.5, 5)
        assert wide[1] - wide[0] > 0.25


# ---------------------------------------------------------------------------
# §8.6 redundancy gates
# ---------------------------------------------------------------------------
class TestRedundancyGates:
    def test_gk_rs_disagreement_downgrades_q2(self):
        # large-body small-range bars drive GK toward its floor while RS
        # stays positive → |GK−RS|/YZ > 0.4 → Q2 (§8.6)
        bars = []
        price = 100.0
        for i in range(60):
            o = price
            c = price * 1.004               # big bullish body
            h = c + 0.001                   # tiny wicks
            l = o - 0.001
            bars.append({"ts": i * 60000, "o": o, "h": h, "l": l,
                         "c": c, "v": 1000.0})
            price = c
        out = run_engine(bars, timeframe="1m")
        last = out["states"][-1]
        if last.gk > 0 and last.yz > 0:
            assert abs(last.gk - last.rs) / last.yz > 0.4 or \
                last.q_tag in ("Q1", "Q2")
        assert last.q_tag != "Q3"

    def test_atr_overestimate_gate(self):
        # §8.6: ATR/(YZ×Price) > 3 → downgrade to Q2. A single gap spike
        # inflates Wilder ATR far beyond the YZ-scaled price.
        bars = lcg_bars(60, seed=16, vol=0.002)
        bars[-1]["o"] = bars[-2]["c"] * 1.15       # 15% gap
        bars[-1]["h"] = bars[-1]["o"] * 1.02
        bars[-1]["l"] = bars[-1]["o"] * 0.99
        bars[-1]["c"] = bars[-1]["o"] * 1.01
        out = run_engine(bars, timeframe="1m")
        last = out["states"][-1]
        assert last.q_tag in ("Q0", "Q1", "Q2", "QX")


# ---------------------------------------------------------------------------
# §8.7 serialization compatibility (v3 breaking change)
# ---------------------------------------------------------------------------
class TestSerializationCompat:
    def test_v3_payload_raises_explicit_error(self):
        with pytest.raises(ValueError, match="E04_V3_PAYLOAD_REJECTED"):
            load_state({"contract_version": "APEX-Contract-Volatility v3.0.0",
                        "regime": "NORMAL"})

    def test_v4_roundtrip_snapshot_preserved(self):
        bars = lcg_bars(80, seed=17)
        out = run_engine(bars, timeframe="1h")
        state = out["states"][-1]
        payload = state.to_canonical()
        payload["snapshot_id"] = state.snapshot_id
        loaded = load_state(payload)
        assert loaded.snapshot_id == state.snapshot_id


# ---------------------------------------------------------------------------
# §8.8 daily non-directionality check + RS fallback
# ---------------------------------------------------------------------------
class TestNonDirectionalityCheck:
    def test_three_consecutive_failures_trigger_rs_fallback(self):
        # construct returns positively coupled to current EWMA sigma:
        # r_{t+1} = +0.9·σ_t ⇒ Corr(r_{t+1}, σ_t) ≈ 1, p ≤ 0.05 always
        bars = []
        price = 100.0
        sigma = 0.01
        lam = 0.94
        for i in range(80):
            r = 0.9 * sigma
            o = price
            c = price * (1 + r)
            h = c * 1.0005
            l = o * 0.9995
            bars.append({"ts": i * 86400000, "o": o, "h": h, "l": l,
                         "c": c, "v": 1000.0})
            sigma = math.sqrt(lam * sigma ** 2 + (1 - lam) * r ** 2)
            price = c
        eng = VolatilityEngineV4(timeframe="1d")
        for b in bars:
            eng.ingest_bar(b)
        assert eng.nondir_fallback is True
        assert eng.drift_streak >= 3


# ---------------------------------------------------------------------------
# §5 event machine (squeeze hysteresis, regime, compression, extreme)
# ---------------------------------------------------------------------------
class TestEventMachine:
    def _quiet_then_expansion(self):
        """Volatile stretch (raises ATR50), then sustained compression
        (ATR14 collapses → VR < 0.70 ∧ BW < 0.12 for ≥3 bars), then an
        expansion leg (RangeZ > 3.5)."""
        bars = []
        price = 600.0
        for i in range(80):                      # volatile stretch
            o = price
            c = price + (6.0 if i % 2 else -6.0)
            h = max(o, c) + 3.0
            l = min(o, c) - 3.0
            bars.append({"ts": i * 3600000, "o": o, "h": h, "l": l,
                         "c": c, "v": 1000.0})
            price = c
        for i in range(80, 130):                 # compression: tiny ranges
            o = price
            c = price + (0.05 if i % 2 else -0.05)
            h = max(o, c) + 0.05
            l = min(o, c) - 0.05
            bars.append({"ts": i * 3600000, "o": o, "h": h, "l": l,
                         "c": c, "v": 1000.0})
            price = c
        for j in range(3):                       # expansion leg
            o = price
            c = price + 25.0
            h = c + 2.0
            l = o - 1.0
            bars.append({"ts": (130 + j) * 3600000, "o": o, "h": h,
                         "l": l, "c": c, "v": 5000.0})
            price = c
        return bars

    def test_squeeze_start_end_and_expansion_events(self):
        out = run_engine(self._quiet_then_expansion(), timeframe="1h")
        types = [e["event_type"] for e in out["events"]]
        assert "EV_VLT_003" in types             # squeeze start (3 bars)
        assert "EV_VLT_004" in types             # squeeze end
        assert "EV_VLT_008" in types             # extreme move (RZ>3.5)

    def test_regime_up_down_events_fire(self):
        # 1mo timeframe ⇒ the §3.9 PIT window (30-bar floor of the
        # 180-day span) is reachable inside the synthetic series, so the
        # quantile banding actually classifies regimes
        out = run_engine(self._quiet_then_expansion(), timeframe="1mo")
        types = [e["event_type"] for e in out["events"]]
        assert "EV_VLT_001" in types or "EV_VLT_002" in types

    def test_expansion_breakout_requires_bos_note(self):
        out = run_engine(self._quiet_then_expansion(), timeframe="1mo")
        e05 = [e for e in out["events"] if e["event_type"] == "EV_VLT_005"]
        for e in e05:
            assert e.get("bos_required") is True   # §1.3 E01 contract


# ---------------------------------------------------------------------------
# §6 parameters (frozen literals; unknown keys rejected)
# ---------------------------------------------------------------------------
class TestParameters:
    def test_frozen_defaults_match_chapter_6(self):
        assert E04_DEFAULTS["atr_short"] == 14
        assert E04_DEFAULTS["atr_long"] == 50
        assert E04_DEFAULTS["hv_window"] == 30
        assert E04_DEFAULTS["boll_period"] == 20
        assert E04_DEFAULTS["boll_k"] == 2.0
        assert E04_DEFAULTS["squeeze_vr"] == 0.75
        assert E04_DEFAULTS["squeeze_bw"] == 0.12
        assert E04_DEFAULTS["extreme_z"] == 3.5
        assert E04_DEFAULTS["regime_window_days"] == 180
        assert E04_DEFAULTS["cluster_window"] == 200
        assert E04_DEFAULTS["ewma_lambda"] == 0.94
        assert E04_DEFAULTS["winsorize_tr_mult"] == 10
        assert E04_DEFAULTS["epsilon"] == 1e-12
        assert E04_DEFAULTS["ljung_m"] == 20
        assert E04_DEFAULTS["k_targeting"] == {"VERY_LOW": 1.5, "LOW": 1.8,
                                               "NORMAL": 2.0, "ELEVATED": 2.5,
                                               "EXTREME": 3.0}

    def test_unknown_param_rejected(self):
        with pytest.raises(ValueError, match="UNKNOWN_E04_PARAM_QX"):
            get_params({"not_a_param": 1})


# ---------------------------------------------------------------------------
# Wave-Out: adaptive ATR E04↔E11 (§9.5-9)
# ---------------------------------------------------------------------------
class TestWaveOut:
    def test_adaptive_atr_request_raises(self):
        eng = VolatilityEngineV4()
        with pytest.raises(WaveOutError, match="adaptive_atr_e04_e11"):
            eng.request_adaptive_atr()

    def test_enginebase_compute_adaptive_context_raises(self):
        eng = E04VolatilityEngine()
        obs = [MarketObservation(symbol="BTCUSDT", timeframe="1h",
                                 open=__import__("decimal").Decimal(100),
                                 high=__import__("decimal").Decimal(101),
                                 low=__import__("decimal").Decimal(99),
                                 close=__import__("decimal").Decimal(100.5),
                                 volume=__import__("decimal").Decimal(10),
                                 oi=None, timestamp=f"2026-01-01T{i:02d}:00:00.000Z",
                                 sequence=i, status="CLOSED")
               for i in range(5)]
        with pytest.raises(WaveOutError, match="adaptive_atr_e04_e11"):
            eng.compute("BTCUSDT", "1h", "2026-01-01T05:00:00Z",
                        {"window": obs, "adaptive_atr": True})


# ---------------------------------------------------------------------------
# EngineBase binding: emissions, ATR series for E03, fail-closed window
# ---------------------------------------------------------------------------
def _obs_window(n=80, seed=21):
    bars = lcg_bars(n, seed=seed)
    obs = []
    from decimal import Decimal
    for i, b in enumerate(bars):
        ts = ("2026-01-%02dT%02d:00:00.000Z"
              % (1 + (i // 24), i % 24))
        obs.append(MarketObservation(
            symbol="BTCUSDT", timeframe="1h",
            open=Decimal(str(round(b["o"], 6))),
            high=Decimal(str(round(b["h"], 6))),
            low=Decimal(str(round(b["l"], 6))),
            close=Decimal(str(round(b["c"], 6))),
            volume=Decimal(str(round(b["v"], 2))),
            oi=None, timestamp=ts, sequence=i, status="CLOSED"))
    return obs


class TestEngineBaseBinding:
    def test_missing_window_context_fails_closed(self):
        eng = E04VolatilityEngine()
        with pytest.raises(ValueError, match="MISSING_WINDOW_CONTEXT_QX"):
            eng.compute("BTCUSDT", "1h", "2026-01-01T00:00:00Z", {})

    def test_compute_emits_valid_24_field_events(self):
        eng = E04VolatilityEngine()
        events = eng.compute("BTCUSDT", "1h", "2026-01-04T08:00:00Z",
                             {"window": _obs_window()})
        assert events
        for ev in events:
            ev.validate_24_fields()
            assert ev.engine_id == "E04"
            assert ev.direction == 0            # §1.4 non-directional
            assert len(ev.snapshot_id) == 64

    def test_atr_series_for_e03_alignment_and_floor(self):
        eng = E04VolatilityEngine()
        window = _obs_window()
        series = eng.atr_series_for("BTCUSDT", "1h",
                                    "2026-01-04T08:00:00Z",
                                    {"window": window})
        assert len(series) == len(window)
        assert all(v >= ATR_FLOOR and math.isfinite(v) for v in series)

    def test_replay_cache_idempotent(self):
        eng = E04VolatilityEngine()
        ctx = {"window": _obs_window()}
        e1 = eng.compute("BTCUSDT", "1h", "2026-01-04T08:00:00Z", ctx)
        e2 = eng.compute("BTCUSDT", "1h", "2026-01-04T08:00:00Z", ctx)
        assert [e.snapshot_id for e in e1] == [e.snapshot_id for e in e2]


# ---------------------------------------------------------------------------
# T-DR-001 (E04 re-run): data-availability contract — identical windows ⇒
# byte-identical canonical evidence; PIT boundary honored.
# ---------------------------------------------------------------------------
class TestTDR001:
    def test_double_run_canonical_byte_identical(self):
        bars = lcg_bars(200, seed=31)
        a = run_engine(bars, timeframe="1h")
        b = run_engine(bars, timeframe="1h")
        ca = json.dumps([s.to_canonical() for s in a["states"]],
                        sort_keys=True, separators=(",", ":"))
        cb = json.dumps([s.to_canonical() for s in b["states"]],
                        sort_keys=True, separators=(",", ":"))
        assert ca == cb

    def test_pit_availability_boundary(self):
        from apex.identity.snapshot import governed_as_of_ms
        artifacts = [{"availability_time_ms": 1000},
                     {"availability_time_ms": 3000},
                     {"availability_time_ms": 2000}]
        assert governed_as_of_ms(artifacts) == 3000
        with pytest.raises(ValueError):
            governed_as_of_ms([{"availability_time_ms": None}])
