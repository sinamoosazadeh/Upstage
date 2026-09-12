"""E10 Momentum — full §8 validation battery (APEX_GEN5.md L10276–11670).

Covers: §8.1 golden fixtures (17 cases, re-derived — doc inconsistencies
logged, formula governs) · §3.1 log-return/Candle validation · §3.2 smoothed
velocity/acceleration + MomentumZ · §3.3 Wilder-RMA RSI (SMA ablation path),
ROC, Stochastic %K/%D, full MACD · §3.4 divergence (OLS β + confirmed
both-pivot) with D_mag, CONVERGENCE, disagreement⇒Q2 · §3.5 symmetric
Impulse/Exhaustion (z-scaled a_z, ISSUE-CP5-001) · §3.6 VR/Vz/MvZ/corr ·
§3.7 invalid-candle discard · §4 streaming idempotency + gap reset +
warmup refusal · §5 state schema + Q-cascade (runtime max Q4) · §6 params
fail-closed · §1.6 momentum_state_projection (E11 consumer) · EV_MOM_001..008 ·
PIT / no-future-leak · deterministic replay (T-DR-001) · EngineBase binding.
"""

from __future__ import annotations

import json
import math
import pathlib
from decimal import Decimal

import pytest

from apex.data_catalog.contracts import MarketObservation
from apex.engines.e10_momentum import (
    CONTRACT_LABEL,
    CONTRACT_VERSION,
    DIVERGENCE_KINDS,
    E10_DEFAULTS,
    E10MomentumEngine,
    ENGINE,
    EVENT_CATALOG,
    INTERVALS,
    KIND_TO_EVENT,
    MOMENTUM_STATE_REQUIRED,
    MomentumEngine,
    Q_TAGS,
    TF_SECONDS,
    calibration_report,
    candle_from_bar,
    catalog_events,
    classify_pivot_pair,
    deterministic_replay_check,
    divergence_mag_ols,
    divergence_mag_pivot,
    divergence_success,
    e10_snapshot_id,
    get_params,
    impulse_exhaustion_flags,
    load_v3_adapter,
    log_return,
    macd_state,
    momentum_state_projection,
    momentum_z,
    no_future_leak_check,
    observation_to_bar,
    ols_slope,
    param_hash,
    pearson_corr,
    redundancy_report,
    roc,
    rsi_series,
    run_engine,
    stochastic_kd,
    validate_state_schema,
    volume_features,
    wilson_ci,
)

FIXTURES = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent / "fixtures"
     / "e10_golden_fixtures.json").read_text())
BY_ID = {f["id"]: f for f in FIXTURES["fixtures"]}

T0 = 1768485600000


def lcg_bars(n, seed=7, base=100.0, drift=0.001, vol=0.004, t0=T0):
    """Deterministic pseudo-random closed 1h bars (LCG — no RNG import)."""
    s = seed
    out = []
    px = base
    for i in range(n):
        s = (1103515245 * s + 12345) % (2 ** 31)
        r = (s / 2 ** 31 - 0.5) * 2 * vol + drift
        o = px
        c = px * math.exp(r)
        h = max(o, c) * (1 + abs(r) / 2 + 0.0005)
        lo = min(o, c) * (1 - abs(r) / 2 - 0.0005)
        v = 1000 * (1 + (s % 100) / 100)
        out.append({"ts": t0 + i * 3600000, "o": o, "h": h, "l": lo, "c": c,
                    "v": v, "is_closed": True})
        px = c
    return out


def zigzag_bars(n=60, amp=0.004, base=100.0, t0=T0):
    """Alternating ±amp log returns (RSI ablation / corr fixtures)."""
    out = []
    px = base
    for i in range(n):
        r = amp if i % 2 == 0 else -amp
        o = px
        c = px * math.exp(r)
        out.append({"ts": t0 + i * 3600000, "o": o,
                    "h": max(o, c) * 1.0004, "l": min(o, c) * 0.9996,
                    "c": c, "v": 1000.0, "is_closed": True})
        px = c
    return out


def stream(bars, params=None):
    eng = MomentumEngine(params)
    st = None
    for b in bars:
        st = eng.update(candle_from_bar(b, "BNBUSDT", "1h"))
    return eng, st


def _obs_window(bars, tf="1h"):
    obs = []
    for i, b in enumerate(bars):
        ts = "2026-01-%02dT%02d:00:00.000Z" % (1 + i // 24, i % 24)
        obs.append(MarketObservation(
            symbol="BNBUSDT", timeframe=tf,
            open=Decimal(str(b["o"])), high=Decimal(str(b["h"])),
            low=Decimal(str(b["l"])), close=Decimal(str(b["c"])),
            volume=Decimal(str(b.get("v", 1000.0))), oi=None,
            timestamp=ts, sequence=i, status="CLOSED"))
    return obs


# ---------------------------------------------------------------------------
# §8.1 Golden fixtures (17 cases; expected values re-derived, ADR-P2-007)
# ---------------------------------------------------------------------------
class TestGoldenFixtures:
    def test_seventeen_cases_present_with_hashes(self):
        assert len(FIXTURES["fixtures"]) == 17
        from apex.identity.canonical_json import canonical_json
        from apex.identity.hashes import sha256_hex
        for f in FIXTURES["fixtures"]:
            # §9.5-3: hash computed after the fixture was written; recomputed
            # here over the committed body (no document hash is ever copied).
            body = {k: v for k, v in f.items() if k not in ("hash", "note")}
            assert f["hash"] == "sha256:" + sha256_hex(
                canonical_json(body).encode("utf-8"))

    def test_gf01_rsi_wilder_rma(self):
        fx = BY_ID["GF01_RSI_Wilder"]
        got = rsi_series([float(c) for c in fx["closes"]], 14, "RMA")[-1]
        assert got == pytest.approx(
            fx["expected"]["rsi_wilder_14"], abs=1e-9)
        # doc_inconsistency: §8.1's 78.2 is not reproducible from the given
        # closes (gains Σ13.0, losses Σ2.0 ⇒ RS=6.5 ⇒ 86.6667). The RMA
        # formula governs; the doc value is logged, never used.
        assert got != pytest.approx(78.2, abs=0.5)

    def test_gf02_stochastic_hh_ll(self):
        fx = BY_ID["GF02_Stoch_HH_LL"]
        cs = fx["candles"]
        k, _d = stochastic_kd([c["h"] for c in cs], [c["l"] for c in cs],
                              [c["c"] for c in cs], 14)
        assert k == pytest.approx(fx["expected"]["stoch_k"], abs=1e-9)
        # HH/LL over the given candles: h=10+i (i=1..14) ⇒ HH=24,
        # l=5+i ⇒ LL=6, last c=23 ⇒ %K = 100·(23−6)/(24−6) = 94.4444.
        assert fx["expected"]["hh"] == 24 and fx["expected"]["ll"] == 6
        assert k == pytest.approx(100.0 * (23 - 6) / (24 - 6), abs=1e-9)

    def test_gf03_macd_full(self):
        fx = BY_ID["GF03_MACD"]
        m = macd_state([float(c) for c in fx["closes"]])
        e = fx["expected"]
        assert m["ema_fast"] == pytest.approx(e["ema12"], abs=1e-9)
        assert m["ema_slow"] == pytest.approx(e["ema26"], abs=1e-9)
        assert m["line"] == pytest.approx(e["macd_line"], abs=1e-9)
        assert m["signal"] == pytest.approx(e["signal"], abs=1e-9)
        assert m["hist"] == pytest.approx(e["hist"], abs=1e-9)
        assert m["hist"] == pytest.approx(m["line"] - m["signal"], abs=1e-12)

    def test_gf04_impulse_bull(self):
        fx = BY_ID["GF04_MomentumZ_Impulse_Bull"]
        res = run_engine(fx["candles"], symbol="BNBUSDT", interval="1h")
        st = res["state"]
        ev = st["events"]
        assert ev["impulse_bull"] is True
        assert ev["impulse_bear"] is False
        assert st["momentum"]["momentum_z"] >= fx["expected"]["mz_min"]
        assert st["momentum"]["acceleration_z"] >= fx["expected"]["a_z_min"]
        assert st["volume_context"]["mvz"] > 0
        assert st["momentum"]["momentum_z"] == pytest.approx(
            fx["derived"]["mz"], abs=1e-6)
        assert "EV_MOM_001" in [e["code"] for e in res["events"]]

    @pytest.mark.parametrize("fid", ["GF05_Exhaustion_Sym_Bull",
                                     "GF06_Exhaustion_Sym_Bear"])
    def test_gf05_gf06_exhaustion_symmetric(self, fid):
        fx = BY_ID[fid]
        s = fx["state"]
        fl = impulse_exhaustion_flags(s["mz"], s["a_z"], s["th_imp"],
                                      s["th_acc"])
        assert fl["exhaustion_bull"] == fx["expected"]["exhaustion_bull"]
        assert fl["exhaustion_bear"] == fx["expected"]["exhaustion_bear"]
        assert fl["impulse_bull"] is False and fl["impulse_bear"] is False

    @pytest.mark.parametrize("fid,side", [
        ("GF07_Div_Regular_Bearish_Pivot", "HIGH"),
        ("GF08_Div_Regular_Bullish_Pivot", "LOW"),
        ("GF09_Div_Hidden_Bullish", "LOW"),
        ("GF10_Div_Hidden_Bearish", "HIGH")])
    def test_gf07_gf10_pivot_divergence_kinds(self, fid, side):
        fx = BY_ID[fid]
        p1, p2 = fx["price_pivots"]
        m1, m2 = fx["mom_pivots"]
        kind, proof = classify_pivot_pair(
            p1["price"], p2["price"], m1["value"], m2["value"], side)
        assert kind == fx["expected"]["kind"]
        assert proof                             # pit_proof flags recorded
        dm = divergence_mag_pivot(p1["price"], p2["price"],
                                  m1["value"], m2["value"])
        assert dm == pytest.approx(fx["expected"]["D_mag"], abs=1e-9)
        assert 0.0 <= dm <= 1.0

    def test_gf11_ols_slope(self):
        fx = BY_ID["GF11_OLS_Slope"]
        e = fx["expected"]
        bp, _ = ols_slope(fx["price_series"])
        bm, _ = ols_slope(fx["mom_series"])
        assert bp == pytest.approx(e["beta_price"], abs=1e-12)
        assert bm == pytest.approx(e["beta_mom"], abs=1e-12)
        assert (bp > 0) != (bm > 0)              # opposite signs
        assert divergence_mag_ols(bp, bm) == pytest.approx(
            e["D_mag"], abs=1e-12) == pytest.approx(1.0)
        # doc_inconsistency: §8.1's D_mag=0.8 is not reproducible from the
        # §3.4 formula |βX−βY|/max(|βX|+|βY|,ε) ⇒ exactly 1.0 here.

    def test_gf12_mvz_corr(self):
        fx = BY_ID["GF12_MvZ_Corr"]
        c = pearson_corr(fx["mz_series"], fx["vz_series"])
        assert c == pytest.approx(fx["expected"]["corr"], abs=1e-9)
        mvz = 2.2 * min(fx["vr"] / 2.0, 1.0) * abs(c)
        assert mvz == pytest.approx(fx["expected"]["mvz"], abs=1e-9)
        assert fx["expected"]["mvz_positive"] is True

    def test_gf13_warmup_refusal(self):
        fx = BY_ID["GF13_Warmup_Refusal"]
        res = run_engine(fx["candles"], symbol="BNBUSDT", interval="1h")
        assert res["state"]["quality"] == fx["expected"]["quality"]
        assert res["state"]["reason"] == fx["expected"]["reason"]
        assert res["events"] == []               # nothing fabricated
        assert "snapshot_id" not in res["state"]

    def test_gf14_idempotency(self):
        fx = BY_ID["GF14_Idempotency"]
        eng, st = stream(fx["candles"])
        n_before = eng.bar_index
        dup = eng.update(candle_from_bar(fx["candles"][-1], "BNBUSDT", "1h"))
        assert dup["pit"]["duplicate"] is True
        assert dup["snapshot_id"] == st["snapshot_id"]
        assert eng.bar_index == n_before         # buffers untouched

    def test_gf15_convergence(self):
        fx = BY_ID["GF15_Convergence"]
        res = run_engine(fx["candles"], symbol="BNBUSDT", interval="1h")
        dv = res["state"]["events"]["divergence"]
        assert dv["kind"] == "CONVERGENCE"
        assert dv["method"] == "OLS"
        assert dv["pit_proof"]["same_sign"] is True
        assert dv["D_mag"] < fx["expected"]["D_mag_lt"]
        der = fx["derived"]
        assert dv["beta_price"] == pytest.approx(der["beta_price"], abs=1e-9)
        assert dv["beta_mom"] == pytest.approx(der["beta_mom"], abs=1e-9)
        assert dv["D_mag"] == pytest.approx(der["D_mag"], abs=1e-9)
        assert "EV_MOM_007" in [e["code"] for e in res["events"]]

    def test_gf16_divergence_none(self):
        fx = BY_ID["GF16_Divergence_None"]
        res = run_engine(fx["candles"], symbol="BNBUSDT", interval="1h")
        dv = res["state"]["events"]["divergence"]
        assert dv["kind"] == "NONE" and dv["method"] == "NONE"
        assert dv["present"] is False
        # constant series ⇒ RSI edge AG=AL=0 ⇒ 50 (§3.3)
        assert res["state"]["indicators"]["rsi_wilder_rma14"] == \
            pytest.approx(50.0)

    def test_gf17_zero_volume_edge(self):
        fx = BY_ID["GF17_Zero_Volume_Edge"]
        res = run_engine(fx["candles"], symbol="BNBUSDT", interval="1h")
        st = res["state"]
        assert st["volume_context"]["mvz"] == 0.0
        assert st["volume_context"]["volume_ratio"] == 0.0
        assert st["q_tag"] == "Q2"               # §5.2 Q3→Q2 on V=0
        validate_state_schema(st)


# ---------------------------------------------------------------------------
# §3.1–§3.3 formulas
# ---------------------------------------------------------------------------
class TestFormulas:
    def test_log_return_edges(self):
        assert log_return(110.0, None) is None       # first bar
        assert log_return(110.0, 100.0) == pytest.approx(math.log(1.1))
        assert log_return(110.0, 0.0) is None        # non-positive prev
        assert log_return(-1.0, 100.0) is None       # non-positive price

    def test_momentum_z_window_and_sigma(self):
        assert momentum_z([0.1], 50) == (None, None, None)
        flat = [0.001] * 10
        mz, mu, sd = momentum_z(flat, 50)
        assert mz == 0.0                             # σ<ε ⇒ Mz=0 (no div/0)
        assert mu == pytest.approx(0.001)
        # window slicing: only the last z_window entries count
        seq = [0.0] * 60 + [1.0]
        mz2, mu2, _ = momentum_z(seq, 10)
        assert mu2 == pytest.approx(0.1) and mz2 > 2.0

    def test_rsi_rma_vs_sma_ablation(self):
        # §8.4: the SMA variant exists ONLY as the ablation path — it must
        # differ from the governing RMA recursion on a trending series.
        closes = [float(b["c"]) for b in lcg_bars(80)]
        rma = rsi_series(closes, 14, "RMA")
        sma = rsi_series(closes, 14, "SMA")
        assert all(0.0 <= v <= 100.0 for v in rma if v is not None)
        assert any(abs(a - b) > 1e-9 for a, b in zip(rma, sma)
                   if a is not None and b is not None)
        assert rma[:14] == [None] * 14               # NaN-before-warm-up
        with pytest.raises(ValueError, match="UNKNOWN_E10_PARAM_QX"):
            rsi_series(closes, 14, "EMA")

    def test_rsi_edges_all_gain_and_flat(self):
        rising = [100.0 + i for i in range(20)]
        assert rsi_series(rising, 14)[-1] == pytest.approx(100.0)
        flat = [100.0] * 20
        assert rsi_series(flat, 14)[-1] == pytest.approx(50.0)

    def test_roc_index_is_t_minus_n(self):
        closes = [float(i) for i in range(1, 13)]    # C_t=12, C_{t−10}=2
        assert roc(closes, 10) == pytest.approx((12 - 2) / 2 * 100.0)
        assert roc(closes[:10], 10) is None          # needs n+1 samples
        assert roc([1.0] * 9 + [0.0, 5.0], 1) is None  # C_{t−n} ≤ 0 edge

    def test_stochastic_flat_is_50(self):
        hs = [100.0] * 14
        k, d = stochastic_kd(hs, hs, hs, 14)
        assert k == 50.0 and d is None               # HH−LL<ε edge
        assert stochastic_kd(hs[:5], hs[:5], hs[:5], 14) == (None, None)

    def test_macd_matches_independent_ema_recursion(self):
        closes = [20.0 + i for i in range(40)]
        m = macd_state(closes)

        def ema(vals, n):
            a = 2.0 / (n + 1)
            v = sum(vals[:n]) / n
            for x in vals[n:]:
                v = a * x + (1 - a) * v
            return v
        e12 = ema(closes, 12)
        e26 = ema(closes, 26)
        line_last = ema(closes[:40], 12) - ema(closes[:40], 26)
        assert m["ema_fast"] == pytest.approx(e12, abs=1e-9)
        assert m["ema_slow"] == pytest.approx(e26, abs=1e-9)
        assert m["line"] == pytest.approx(line_last, abs=1e-9)
        assert m["line"] == pytest.approx(e12 - e26, abs=1e-9)
        short = macd_state(closes[:20])
        assert short["line"] is None and short["signal"] is None

    def test_wilson_ci_bounds(self):
        lo, hi = wilson_ci(0.8, 40)
        assert 0.0 <= lo < 0.8 < hi <= 1.0
        assert wilson_ci(0.5, 0) == (0.0, 0.0)
        lo2, hi2 = wilson_ci(0.6, 30)
        assert hi2 - lo2 < 0.4                       # width shrinks with n


# ---------------------------------------------------------------------------
# §3.5–§3.6 statistics, volume context, flags
# ---------------------------------------------------------------------------
class TestStatistics:
    def test_pearson_degenerate_is_zero(self):
        assert pearson_corr([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == \
            pytest.approx(1.0)
        assert pearson_corr([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) == 0.0
        assert pearson_corr([1.0, 2.0], [1.0, 2.0]) == 0.0   # <3 pairs
        assert pearson_corr([1.0, None, 3.0], [1.0, 2.0, 3.0]) == 0.0

    def test_volume_features_vr_vz(self):
        vols = [1000.0] * 19 + [2000.0]
        vr, vz, mu = volume_features(vols, 20)
        assert mu == pytest.approx(1050.0)
        assert vr == pytest.approx(2000.0 / 1050.0)
        assert vz > 0
        assert volume_features([100.0], 20) == (None, None, None)

    def test_impulse_mvz_clause(self):
        # core condition alone (no MvZ context — ISSUE-CP5-002)
        assert impulse_exhaustion_flags(2.5, 0.6, 2.0, 0.5)["impulse_bull"]
        # MvZ ≤ 0 blocks the bullish impulse (§3.5 participation clause)
        assert not impulse_exhaustion_flags(
            2.5, 0.6, 2.0, 0.5, mvz=-0.1)["impulse_bull"]
        # symmetric bearish
        assert impulse_exhaustion_flags(-2.5, -0.6, 2.0, 0.5,
                                        mvz=-0.4)["impulse_bear"]
        # None inputs ⇒ all False (never a guess)
        fl = impulse_exhaustion_flags(None, None, 2.0, 0.5)
        assert not any(fl.values())

    def test_exhaustion_requires_fading_participation(self):
        # with context: exhaustion_bull needs MvZ falling AND VR declining
        assert impulse_exhaustion_flags(
            2.5, -0.7, 2.0, 0.5, mvz=0.1, mvz_prev=0.9,
            vr=0.8, vr_prev=1.2)["exhaustion_bull"]
        assert not impulse_exhaustion_flags(
            2.5, -0.7, 2.0, 0.5, mvz=1.2, mvz_prev=0.9,
            vr=1.5, vr_prev=1.2)["exhaustion_bull"]

    def test_divergence_mag_bounds(self):
        assert divergence_mag_ols(1.0, 1.0) == 0.0
        assert divergence_mag_ols(1.0, -1.0) == pytest.approx(1.0)
        assert divergence_mag_pivot(0.0, 5.0, 1.0, 2.0) == 0.0  # P1=0 edge
        d = divergence_mag_pivot(100.0, 101.0, 50.0, 40.0)
        assert 0.0 <= d <= 1.0

    def test_classify_pivot_pair_thresholds_and_fail_closed(self):
        # below thresholds ⇒ no divergence (δ_p=0.1%, δ_m=0.5)
        assert classify_pivot_pair(100.0, 100.05, 60.0, 59.8,
                                   "HIGH")[0] is None
        # price leg passes δ_p but momentum leg misses δ_m ⇒ still None
        assert classify_pivot_pair(100.0, 101.0, 60.0, 59.8,
                                   "HIGH")[0] is None
        assert classify_pivot_pair(100.0, 101.0, 60.0, 59.0,
                                   "HIGH")[0] == "REGULAR_BEARISH"
        with pytest.raises(ValueError, match="UNKNOWN_E10_PARAM_QX"):
            classify_pivot_pair(1.0, 2.0, 3.0, 4.0, "MIDDLE")


# ---------------------------------------------------------------------------
# §3.7 / §4 streaming semantics
# ---------------------------------------------------------------------------
class TestStreamingAndState:
    def test_invalid_candle_discarded_q0(self):
        eng, st = stream(lcg_bars(60))
        n_before = eng.bar_index
        bad = candle_from_bar({"ts": T0 + 60 * 3600000, "o": 100.0,
                               "h": 90.0, "l": 95.0, "c": 96.0, "v": 10.0,
                               "is_closed": True}, "BNBUSDT", "1h")
        out = eng.update(bad)
        assert out["quality"] == "Q0" and out["reason"] == "H_LT_L"
        assert eng.bar_index == n_before           # buffers untouched
        open_c = candle_from_bar({"ts": T0 + 60 * 3600000, "o": 100.0,
                                  "h": 101.0, "l": 99.0, "c": 100.5,
                                  "v": 10.0, "is_closed": False},
                                 "BNBUSDT", "1h")
        assert eng.update(open_c)["reason"] == "OPEN_CANDLE"

    def test_unknown_interval_fails_closed(self):
        bars = [dict(b, interval="9m") for b in lcg_bars(60)]
        res = run_engine(bars, symbol="BNBUSDT", interval="9m")
        assert res["state"]["quality"] == "Q0"
        assert res["state"]["reason"] == "UNKNOWN_INTERVAL_QX"
        assert res["events"] == []

    def test_gap_break_resets_smothers(self):
        bars = lcg_bars(60)
        gap = dict(bars[-1])
        gap["ts"] = bars[-1]["ts"] + 4 * 3600000    # >1.5× interval
        gap["o"] = gap["c"] * 0.99
        eng = MomentumEngine(get_params())
        for b in bars:
            eng.update(candle_from_bar(b, "BNBUSDT", "1h"))
        assert eng.ema_vel.value is not None
        eng.update(candle_from_bar(gap, "BNBUSDT", "1h"))
        assert eng.ema_vel.value is None            # reset to SMA seed
        assert eng.rma_gain.value is None
        # re-seeds after enough contiguous bars post-gap
        for b in lcg_bars(20, seed=11, t0=gap["ts"] + 3600000):
            eng.update(candle_from_bar(b, "BNBUSDT", "1h"))
        assert eng.ema_vel.value is not None

    def test_warmup_refusal_then_state(self):
        eng = MomentumEngine(get_params())
        for b in lcg_bars(49):
            out = eng.update(candle_from_bar(b, "BNBUSDT", "1h"))
        assert out["quality"] == "QX"
        assert out["reason"] == "INSUFFICIENT_HISTORY_Q1"
        out = eng.update(candle_from_bar(lcg_bars(50)[-1], "BNBUSDT", "1h"))
        assert "snapshot_id" in out                 # 50th bar ⇒ full state
        validate_state_schema(out)

    def test_runtime_quality_capped_at_q4(self):
        # Q5 requires the offline replay+leak+calibration gates (§5.2) —
        # the streaming path must never emit it.
        for bars in (lcg_bars(150), zigzag_bars(150, amp=0.002)):
            _eng, st = stream(bars)
            assert st["q_tag"] in ("Q1", "Q2", "Q3", "Q4")
            assert st["q_tag"] != "Q5"

    def test_disagreement_downgrades_to_q2(self):
        # deterministic LCG(120): PIVOT fires HIDDEN_BULLISH while OLS
        # disagrees ⇒ §3.4 disagreement rule ⇒ Q2 (never silent pick).
        _eng, st = stream(lcg_bars(120))
        dv = st["events"]["divergence"]
        assert dv["ols_disagrees"] is True
        assert st["q_tag"] == "Q2"

    def test_state_schema_fail_closed(self):
        _eng, st = stream(lcg_bars(80))
        validate_state_schema(st)
        broken = dict(st)
        del broken["q_tag"]
        with pytest.raises(ValueError, match="E10_STATE_SCHEMA_QX"):
            validate_state_schema(broken)
        bad = dict(st, contract_version="E10_Momentum/4.0")
        with pytest.raises(ValueError, match="contract_version pattern"):
            validate_state_schema(bad)
        bad2 = dict(st, q_tag="Q9")
        with pytest.raises(ValueError, match="q_tag enum"):
            validate_state_schema(bad2)

    def test_trend_context_downgrade_matrix(self):
        bars = lcg_bars(100)
        res_a = run_engine(bars, symbol="BNBUSDT", interval="1h")
        res_b = run_engine(bars, symbol="BNBUSDT", interval="1h",
                           trend_context={"contract_version":
                                          "E09_Trend/3.9.0"})
        res_c = run_engine(bars, symbol="BNBUSDT", interval="1h",
                           trend_context={"contract_version": "garbage"})
        order = ["Q0", "Q1", "Q2", "Q3", "Q4"]
        qa = res_a["state"]["q_tag"]
        assert res_b["state"]["q_tag"] == order[order.index(qa) - 1]
        # unparseable version ⇒ treated as incompatible (fail-closed)
        assert res_c["state"]["q_tag"] == res_b["state"]["q_tag"]
        # compatible v4 ⇒ no downgrade
        res_d = run_engine(bars, symbol="BNBUSDT", interval="1h",
                           trend_context={"contract_version":
                                          "E09_Trend/4.0.0"})
        assert res_d["state"]["q_tag"] == qa

    def test_pit_pivots_confirm_lag_and_no_leak(self):
        bars = lcg_bars(120)
        eng, st = stream(bars)
        assert no_future_leak_check(eng, st, "1h") is True
        assert st["pit"]["is_pit_safe"] is True
        for plist in (eng.price_high_pivots, eng.price_low_pivots,
                      eng.mom_high_pivots, eng.mom_low_pivots):
            for piv in plist:
                k = int(eng.p.pivot_min_bars)
                assert piv.confirmed_at == piv.index + k
                assert piv.time + k * 3600000 <= st["as_of"]

    def test_deterministic_replay_check(self):
        candles = [candle_from_bar(b, "BNBUSDT", "1h") for b in lcg_bars(70)]
        assert deterministic_replay_check(candles) is True

    def test_replay_is_byte_identical(self):
        bars = lcg_bars(90)
        a = run_engine(bars, symbol="BNBUSDT", interval="1h")
        b = run_engine(bars, symbol="BNBUSDT", interval="1h")
        assert json.dumps(a, sort_keys=True, default=str) == json.dumps(
            b, sort_keys=True, default=str)


# ---------------------------------------------------------------------------
# §5.3 / §6 parameters, catalog, identity
# ---------------------------------------------------------------------------
class TestParamsAndEvents:
    def test_defaults_are_the_frozen_six_surface(self):
        assert len(E10_DEFAULTS) == 20             # §6 19 + 1 derived
        for key in ("mom_window", "z_window", "ema_vel", "ema_acc",
                    "impulse_z", "accel_threshold", "rsi_period",
                    "roc_window", "stoch_period", "macd_fast", "macd_slow",
                    "macd_signal", "pivot_min_bars", "divergence_window",
                    "price_delta_pct", "mom_delta", "reference_mode",
                    "corr_window", "beta_min", "convergence_dmag_max"):
            assert key in E10_DEFAULTS
        assert E10_DEFAULTS["impulse_z"] == 2.0
        assert E10_DEFAULTS["accel_threshold"] == 0.5
        assert E10_DEFAULTS["reference_mode"] == "RSI"

    def test_unknown_params_rejected_fail_closed(self):
        with pytest.raises(ValueError, match="UNKNOWN_E10_PARAM_QX"):
            get_params({"nope": 1})
        with pytest.raises(ValueError, match="UNKNOWN_E10_PARAM_QX"):
            run_engine(lcg_bars(60), params={"theta": 3})

    def test_param_hash_stable_12_hex(self):
        h = param_hash(get_params())
        assert len(h) == 12 and all(c in "0123456789abcdef" for c in h)
        assert h == param_hash(get_params())
        assert h != param_hash(get_params({"z_window": 60}))

    def test_event_catalog_and_kind_mapping(self):
        assert set(EVENT_CATALOG) == {
            "EV_MOM_001", "EV_MOM_001b", "EV_MOM_002", "EV_MOM_002b",
            "EV_MOM_003", "EV_MOM_004", "EV_MOM_005", "EV_MOM_006",
            "EV_MOM_007", "EV_MOM_008"}
        assert set(KIND_TO_EVENT.values()) <= set(EVENT_CATALOG)
        assert set(KIND_TO_EVENT) == set(DIVERGENCE_KINDS) - {"NONE"}
        assert CONTRACT_LABEL == "E10_Momentum/4.0.0"
        assert CONTRACT_VERSION == "4.0.0" and ENGINE == "E10_Momentum"

    def test_interval_universe_is_the_frozen_14tf(self):
        assert set(INTERVALS) == set(TF_SECONDS) == {
            "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h",
            "12h", "1d", "1w", "1mo"}

    def test_catalog_events_empty_for_refusal(self):
        assert catalog_events({"quality": "QX"}) == []
        assert catalog_events({}) == []

    def test_snapshot_id_content_bound(self):
        a = {"momentum": {"momentum_z": 1.0}}
        b = {"momentum": {"momentum_z": 1.0}}
        c = {"momentum": {"momentum_z": 1.1}}
        assert e10_snapshot_id(a) == e10_snapshot_id(b)
        assert e10_snapshot_id(a) != e10_snapshot_id(c)
        assert len(e10_snapshot_id(a)) == 64


# ---------------------------------------------------------------------------
# §8.5–§8.7 battery helpers
# ---------------------------------------------------------------------------
class TestBatteryHelpers:
    def test_divergence_success_definitions(self):
        after = [{"h": 101.0, "l": 90.0, "c": 95.0}] * 10
        assert divergence_success("REGULAR_BEARISH", after, atr=5.0) is True
        down = [{"h": 94.0, "l": 90.0, "c": 91.0}] * 10
        assert divergence_success("REGULAR_BULLISH", down, atr=5.0) is False
        up = [{"h": 110.0, "l": 100.0, "c": 105.0}] * 10
        assert divergence_success("REGULAR_BULLISH", up, atr=5.0) is True
        rising = [{"h": 104.0 + i, "l": 100.0 + i, "c": 102.0 + i}
                  for i in range(10)]
        assert divergence_success("HIDDEN_BULLISH", rising, atr=5.0) is True
        falling = [{"h": 110.0 - i, "l": 100.0 - i, "c": 105.0 - i}
                   for i in range(10)]
        assert divergence_success("HIDDEN_BEARISH", falling, atr=5.0) is True
        assert divergence_success("NONE", up, atr=5.0) is None
        assert divergence_success("REGULAR_BEARISH", [], atr=5.0) is None

    def test_calibration_report(self):
        outcomes = [("REGULAR_BEARISH", True)] * 6 + \
                   [("REGULAR_BEARISH", False)] * 4 + \
                   [("HIDDEN_BULLISH", True)] * 2
        rep = calibration_report(outcomes)
        rb = rep["REGULAR_BEARISH"]
        assert rb["n"] == 10 and rb["k"] == 6 and rb["p"] == \
            pytest.approx(0.6)
        lo, hi = rb["wilson_ci"]
        assert lo < 0.6 < hi
        assert rep["REGULAR_BULLISH"]["n"] == 0
        assert rep["REGULAR_BULLISH"]["p"] is None

    def test_redundancy_report_thresholds(self):
        mz = [float(i) for i in range(30)]
        dup = [2.0 * x + 1.0 for x in mz]
        rep = redundancy_report(mz, trend_series=dup)
        assert rep["rho_trend"] == pytest.approx(1.0)
        assert rep["redundancy_warning"] is True
        assert rep["quality_downgrade"] is True
        indep = [(1.0 if i % 2 else -1.0) for i in range(30)]
        rep2 = redundancy_report(mz, trend_series=indep, volz_series=indep)
        assert rep2["rho_trend"] < 0.75
        assert rep2["redundancy_warning"] is False
        assert rep2["volz_ok"] is True

    def test_load_v3_adapter_fail_closed(self):
        with pytest.raises(ValueError, match="E10_V3_ADAPTER_QX"):
            load_v3_adapter({"version": "4.0.0"})
        with pytest.raises(ValueError, match="E10_V3_ADAPTER_QX"):
            load_v3_adapter({"version": "3.2.0", "momentum": {}})
        out = load_v3_adapter({"version": "3.2.0", "as_of": 5,
                               "momentum": {"momentum_z": 1.5}})
        assert out["q_tag"] == "Q1"                # migration ⇒ Q1
        assert out["contract_version"] == CONTRACT_LABEL
        assert out["migrated_from"] == "3.2.0"

    def test_momentum_state_projection_for_e11(self):
        _eng, st = stream(BY_ID["GF04_MomentumZ_Impulse_Bull"]["candles"])
        proj = momentum_state_projection(st)
        assert set(proj) == {"momentum_state_raw", "impulse_score", "as_of",
                             "contract_version"}
        assert proj["momentum_state_raw"] == "IMPULSIVE"
        assert 0.0 < proj["impulse_score"] <= 1.0
        assert proj["contract_version"] == CONTRACT_LABEL
        # EXHAUSTED wins over IMPULSIVE; neutral default
        ex = {"events": {"exhaustion_bull": True, "impulse_bull": True},
              "momentum": {"momentum_z": 2.5}, "as_of": 1}
        assert momentum_state_projection(ex)["momentum_state_raw"] == \
            "EXHAUSTED"
        neutral = {"events": {}, "momentum": {"momentum_z": 0.1}, "as_of": 1}
        p2 = momentum_state_projection(neutral)
        assert p2["momentum_state_raw"] == "NEUTRAL"
        assert p2["impulse_score"] == 0.0


# ---------------------------------------------------------------------------
# EngineBase binding (frozen contract — consumed, never patched)
# ---------------------------------------------------------------------------
class TestDeterminismAndBinding:
    def test_missing_window_fails_closed(self):
        with pytest.raises(ValueError, match="MISSING_WINDOW_CONTEXT_QX"):
            E10MomentumEngine().compute("BNBUSDT", "1h",
                                        "2026-01-15T00:00:00Z", {})

    def test_empty_window_emits_nothing(self):
        assert E10MomentumEngine().compute("BNBUSDT", "1h",
                                           "2026-01-15T00:00:00Z",
                                           {"window": []}) == []

    def test_compute_emits_context_only_events(self):
        fx = BY_ID["GF04_MomentumZ_Impulse_Bull"]
        evs = E10MomentumEngine().compute(
            "BNBUSDT", "1h", "2026-01-15T00:00:00Z",
            {"window": _obs_window(fx["candles"])})
        assert evs                                   # EV_MOM_001 fired
        for ev in evs:
            ev.validate_24_fields()
            assert ev.engine_id == "E10"
            assert ev.direction == 0                 # NG1 context engine
            assert ev.resolution_class in Q_TAGS
            assert ev.parameter_version == "E10-MOM-V4.0.0/DEFAULTS-v1"
            assert ev.condition_state.startswith("EV_MOM_")
            assert ev.validity in ("VALID", "DEGRADED")
            assert 0.0 <= ev.strength <= 1.0
            assert 0.0 <= ev.confidence <= 1.0

    def test_compute_warmup_window_emits_nothing(self):
        fx = BY_ID["GF13_Warmup_Refusal"]
        assert E10MomentumEngine().compute(
            "BNBUSDT", "1h", "2026-01-15T00:00:00Z",
            {"window": _obs_window(fx["candles"])}) == []

    def test_compute_rejects_unknown_params(self):
        fx = BY_ID["GF14_Idempotency"]
        with pytest.raises(ValueError, match="UNKNOWN_E10_PARAM_QX"):
            E10MomentumEngine().compute(
                "BNBUSDT", "1h", "2026-01-15T00:00:00Z",
                {"window": _obs_window(fx["candles"]),
                 "e10_params": {"nope": 1}})

    def test_observation_to_bar_shape(self):
        obs = _obs_window(lcg_bars(2))[0]
        b = observation_to_bar(obs, "1h")
        assert set(b) >= {"ts", "o", "h", "l", "c", "v", "is_closed"}
        assert b["is_closed"] is True and b["ts"] > 0

    def test_t_dr_001_deterministic_replay(self):
        """T-DR-001: identical emissions on re-run over identical inputs."""
        fx = BY_ID["GF04_MomentumZ_Impulse_Bull"]
        ctx = {"window": _obs_window(fx["candles"])}
        a = E10MomentumEngine().compute("BNBUSDT", "1h",
                                        "2026-01-15T00:00:00Z", ctx)
        b = E10MomentumEngine().compute("BNBUSDT", "1h",
                                        "2026-01-15T00:00:00Z", ctx)
        assert [e.snapshot_id for e in a] == [e.snapshot_id for e in b]
        assert [e.condition_state for e in a] == \
            [e.condition_state for e in b]
        assert [e.direction for e in a] == [e.direction for e in b]
        assert [e.strength for e in a] == [e.strength for e in b]

    def test_state_required_keys_and_q_enum(self):
        _eng, st = stream(lcg_bars(80))
        for key in MOMENTUM_STATE_REQUIRED:
            assert key in st
        assert st["q_tag"] in Q_TAGS
        assert st["engine_code"] == ENGINE
        assert st["contract_version"] == CONTRACT_LABEL
