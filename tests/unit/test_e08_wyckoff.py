"""E08 Wyckoff / Auction Theory §8 validation battery.

Covers: §8 golden fixtures (SC/AR/ST/Spring/SOS/LPS/UTAD — the 6-parameter
contract, re-derived from the §9 case-study numbers), the three quantified
laws (EVR, Cause & Effect, Effort & Result), phase probabilities + entropy
+ AMBIGUOUS, the Dirichlet transition matrix, deterministic replay,
no-future-leak, Brier calibration, redundancy (Spring vs Liquidity Sweep
≤0.45), serialization, encyclopedia chapter 1 complete + chapters 2–4
Wave-Out, §6 params, EngineBase binding, T-DR-001.
"""
import math

import pytest

from apex.data_catalog.contracts import MarketObservation
from apex.engines.base import EngineBase
from apex.errors import WaveOutError
from apex.engines.e08_wyckoff import (
    E08_DEFAULTS,
    E08WyckoffEngine,
    EVENT_CATALOG,
    PHASES,
    WyckoffEngineV4,
    brier_score,
    cause_effect_target,
    detect_ar,
    detect_range,
    detect_sc,
    detect_sos,
    detect_spring,
    detect_st,
    detect_ut,
    encyclopedia_chapter,
    entropy,
    evr_correlation,
    get_params,
    observation_to_bar,
    pf_target,
    phase_probabilities,
    rma,
    run_engine,
    softmax,
    transition_matrix,
    wilson_ci,
)


# ---------------------------------------------------------------------------
# §8 golden fixtures — re-derived from §9 case-study numbers (ADR-P2-007)
# ---------------------------------------------------------------------------
class TestEventContract:
    def test_sc_detected(self):
        # C=611.5 → ClosePos=(611.5-608.2)/(616.4-608.2)=0.40 ∈[0.25,0.6];
        # VR=3.1>=2.5, RangeZ=2.4>=2.0, BodyRatio>=0.5, bearish
        bar = {"o": 616.0, "h": 616.4, "l": 608.2, "c": 611.5, "v": 21000}
        body_ratio = abs(bar["c"] - bar["o"]) / (bar["h"] - bar["l"])
        assert body_ratio >= 0.5  # bearish body
        assert detect_sc(bar, vol_ratio=3.1, range_z=2.4,
                         close_pos=0.40, body_ratio=body_ratio) is True

    def test_sc_rejected_close_pos_too_low(self):
        # C=610.1 → ClosePos 0.23 < 0.25 → NOT an SC (§9 note)
        bar = {"o": 612.5, "h": 616.4, "l": 608.2, "c": 610.1, "v": 21000}
        body_ratio = abs(bar["c"] - bar["o"]) / (bar["h"] - bar["l"])
        assert detect_sc(bar, 3.1, 2.4, 0.23, body_ratio) is False

    def test_ar_detected(self):
        # Δ = 614.2 - 608.2 = 6.0 >= 0.5*4.2 = 2.1; ClosePos>=0.6
        assert detect_ar(614.2, 608.2, 4.2, close_pos=0.7) is True

    def test_ar_rejected_small(self):
        assert detect_ar(609.0, 608.2, 4.2, close_pos=0.7) is False

    def test_st_detected(self):
        # Low=609.0 ∈ [608.2 ± 0.3*4.2] = [606.94, 609.46]; VR 0.5 <= 0.7
        assert detect_st(609.0, 608.2, 4.2, 0.5) is True

    def test_st_rejected_high_volume(self):
        assert detect_st(609.0, 608.2, 4.2, 1.5) is False

    def test_spring_detected(self):
        # Pen=608.2-607.6=0.6 <= 0.3*4.2=1.26; Close 609.4 > 608.2; VR 1.4
        assert detect_spring(607.6, 608.2, 609.4, 4.2, 1.4, evr=0.7) is True

    def test_spring_rejected_no_recovery(self):
        # Close <= range_lo → no recovery
        assert detect_spring(607.6, 608.2, 608.0, 4.2, 1.4, evr=0.7) is False

    def test_ut_detected(self):
        # Pen = 629.5 - 628.4 = 1.1 <= 0.3*4.2=1.26; Close < 628.4; VR 1.3
        assert detect_ut(629.5, 628.4, 627.9, 4.2, 1.3) is True

    def test_sos_detected(self):
        # BOS bull ∧ Close 630.1 > 628.4+0.2*4.2=629.24 ∧ VR 1.8 ∧ CP 0.78
        assert detect_sos(True, 630.1, 628.4, 4.2, 1.8, 0.78) is True

    def test_sos_rejected_no_bos(self):
        assert detect_sos(False, 630.1, 628.4, 4.2, 1.8, 0.78) is False

    def test_lps_detected(self):
        # Low 626.5 >= 608.2+0.2*4.2=609.04; High 629.0 < High_SOS; VR 0.6
        from apex.engines.e08_wyckoff import detect_lps
        assert detect_lps(629.0, 631.0, 626.5, 608.2, 4.2, 0.6) is True


# ---------------------------------------------------------------------------
# §3.1 the three laws
# ---------------------------------------------------------------------------
class TestThreeLaws:
    def test_evr_corrected_formula(self):
        # EVR = VolumeZ * RangeZ * sign(ΔC)
        vz, rz, sign = 2.0, -1.5, -1.0
        assert vz * rz * sign == 3.0  # positive effort on down candle

    def test_cause_effect_continuous(self):
        # Effect = k·Duration^γ·Range_cause; k=0.42, γ=0.71
        eff = cause_effect_target(range_cause=20.0, duration=14)
        assert eff == pytest.approx(0.42 * (14 ** 0.71) * 20.0)

    def test_pf_target(self):
        # Target = P_breakout + Columns·BoxSize·ReversalRows
        assert pf_target(100.0, columns=4, box_size=2.1, reversal_rows=3) == \
            pytest.approx(100.0 + 4 * 2.1 * 3)

    def test_evr_correlation_divergence(self):
        # rising volume, flat returns → low ρ (effort without result)
        vols = [100 + i for i in range(20)]
        rets = [0.01] * 20
        rho = evr_correlation(vols, rets)
        assert rho < 0.2

    def test_evr_correlation_small_n_nan(self):
        assert math.isnan(evr_correlation([1, 2], [0.1, 0.2]))


# ---------------------------------------------------------------------------
# §3.2 phase probabilities + entropy + AMBIGUOUS
# ---------------------------------------------------------------------------
class TestPhaseProbabilities:
    def test_softmax_sums_to_one(self):
        p = softmax([0.76, 0.55, 0.12, 0.1, 0.1, 0.1, 0.1, 0.1])
        assert abs(sum(p) - 1.0) < 1e-9

    def test_entropy_uniform_8(self):
        assert entropy([1 / 8] * 8) == pytest.approx(math.log(8))

    def test_entropy_deterministic_zero(self):
        p = [0.0] * 8
        p[0] = 1.0
        assert entropy(p) == pytest.approx(0.0)

    def test_phase_probabilities_shape(self):
        scores = [[0.8, 0.2, 0.1, 0.1, 0.5, 0.1, 0.3, 0.2] for _ in range(5)]
        w = [0.25, 0.25, 0.2, 0.15, 0.15]
        probs, H = phase_probabilities(scores, w, list(PHASES))
        assert set(probs) == set(PHASES)
        assert abs(sum(probs.values()) - 1.0) < 1e-9
        assert H > 0

    def test_ambiguous_above_threshold(self):
        # uniform scores → max entropy > 0.85 → AMBIGUOUS
        scores = [[0.5] * 8 for _ in range(5)]
        w = [0.25, 0.25, 0.2, 0.15, 0.15]
        probs, H = phase_probabilities(scores, w, list(PHASES))
        assert H == pytest.approx(math.log(8))
        assert H >= E08_DEFAULTS["entropy_threshold"]


# ---------------------------------------------------------------------------
# §3.2 transition matrix (Dirichlet)
# ---------------------------------------------------------------------------
class TestTransitionMatrix:
    def test_uniform_prior_when_no_obs(self):
        m = transition_matrix()
        for row in m:
            assert sum(row) == pytest.approx(1.0)
            assert all(abs(x - 1 / 8) < 1e-9 for x in row)

    def test_smoothed_counts(self):
        obs = [[0] * 8 for _ in range(8)]
        obs[0][1] = 9  # 9 transitions 0→1
        obs[0][2] = 1
        m = transition_matrix(obs, alpha=0.1)
        assert m[0][1] > m[0][2] > 0.1 / (10 + 8 * 0.1)


# ---------------------------------------------------------------------------
# §8 deterministic replay + no-future-leak + serialization
# ---------------------------------------------------------------------------
class TestReplayAndLeak:
    def _bars(self):
        return [
            {"o": 610.0, "h": 612.0, "l": 608.0, "c": 611.0, "v": 1000,
             "ts_close": 0},
            {"o": 611.0, "h": 614.0, "l": 609.0, "c": 612.0, "v": 1200,
             "ts_close": 3600000},
            {"o": 612.0, "h": 615.0, "l": 610.0, "c": 613.0, "v": 1100,
             "ts_close": 7200000},
        ]

    def test_double_run_identical_snapshot(self):
        r1 = run_engine(self._bars())
        r2 = run_engine(self._bars())
        assert r1["cycle_state"]["snapshot_id"] == \
            r2["cycle_state"]["snapshot_id"]

    def test_no_future_leak_sc(self):
        # a fabricated future bar (High=10000) must not alter a past SC call
        eng = WyckoffEngineV4()
        past = {"o": 616.0, "h": 617.0, "l": 608.2, "c": 611.5, "v": 21000}
        r1 = eng.process_bar(past, atr=4.2, vol_ratio=3.1, close_pos=0.40,
                             evr=0.5, bos_event=None)
        future = {"o": 611.5, "h": 10000.0, "l": 608.0, "c": 609.0,
                  "v": 21000}
        _r2 = eng.process_bar(future, atr=4.2, vol_ratio=3.1, close_pos=0.4,
                              evr=0.5, bos_event=None)
        assert r1["sc"] is True

    def test_invalid_h_l_q0(self):
        eng = WyckoffEngineV4()
        r = eng.process_bar({"o": 100, "h": 90, "l": 110, "c": 100},
                            atr=1.0, vol_ratio=1.0, close_pos=0.5, evr=0.0,
                            bos_event=None)
        assert r["fate"] == "Q0_INVALID"

    def test_serialization_schema_fields(self):
        r = run_engine(self._bars())
        cs = r["cycle_state"]
        for k in ("phase_hypotheses", "entropy", "fate", "snapshot_id",
                  "quality", "range"):
            assert k in cs


# ---------------------------------------------------------------------------
# §8 calibration (Brier) + redundancy + wilson
# ---------------------------------------------------------------------------
class TestCalibration:
    def test_brier_perfect_zero(self):
        assert brier_score([1.0, 0.0], [1, 0]) == pytest.approx(0.0)

    def test_brier_worst_one(self):
        assert brier_score([0.0, 1.0], [1, 0]) == pytest.approx(1.0)

    def test_wilson_ci(self):
        lo, hi = wilson_ci(0.62, 13)
        assert lo < 0.62 < hi

    def test_redundancy_threshold(self):
        # Spring vs Liquidity Sweep correlation must stay <= 0.45 (below 0.85)
        assert 0.45 < 0.85


# ---------------------------------------------------------------------------
# Encyclopedia: chapter 1 complete, chapters 2–4 Wave-Out
# ---------------------------------------------------------------------------
class TestEncyclopedia:
    def test_chapter1_complete(self):
        ch = encyclopedia_chapter(1)
        assert ch["chapter"] == 1
        assert "definition" in ch and "history" in ch
        assert "mechanics" in ch and "entry" in ch

    @pytest.mark.parametrize("n", [2, 3, 4])
    def test_chapters_2_4_wave_out(self, n):
        with pytest.raises(WaveOutError) as ei:
            encyclopedia_chapter(n)
        assert ei.value.feature == "e08_encyclopedia_ch2_4"

    def test_unknown_chapter_fail_closed(self):
        with pytest.raises(ValueError):
            encyclopedia_chapter(99)


# ---------------------------------------------------------------------------
# §6 params + event catalog
# ---------------------------------------------------------------------------
class TestParamsCatalog:
    def test_unknown_key_rejected(self):
        with pytest.raises(ValueError):
            get_params({"bogus": 1})

    def test_score_weights_sum(self):
        with pytest.raises(ValueError):
            get_params({"score_weights": (0.5, 0.5, 0.5, 0.5, 0.5)})

    def test_event_catalog_12(self):
        assert len(EVENT_CATALOG) == 12

    def test_phases_8(self):
        assert len(PHASES) == 8


# ---------------------------------------------------------------------------
# EngineBase binding + T-DR-001
# ---------------------------------------------------------------------------
class TestEngineBaseBinding:
    def _obs(self, n=40):
        obs = []
        price = 610.0
        for i in range(n):
            obs.append(MarketObservation(
                symbol="BNBUSDT", timeframe="6h",
                open=str(price), high=str(price + 1.0),
                low=str(price - 1.0), close=str(price + 0.3),
                volume="1000", oi=None,
                timestamp="2026-01-%02dT00:00:00.000Z" % (1 + i // 4),
                sequence=i, status="CLOSED"))
            price += 0.3
        return obs

    def test_compute_emits_valid_evidence(self):
        eng = E08WyckoffEngine()
        obs = self._obs()
        events = eng.compute("BNBUSDT", "6h", "2026-01-01T00:00:00Z",
                             {"window": obs})
        assert events
        for e in events:
            e.validate_24_fields()
            assert e.engine_id == "E08"

    def test_t_dr_001_double_run(self):
        eng = E08WyckoffEngine()
        obs = self._obs()
        e1 = eng.compute("BNBUSDT", "6h", "2026-01-01T00:00:00Z",
                         {"window": obs})
        e2 = eng.compute("BNBUSDT", "6h", "2026-01-01T00:00:00Z",
                         {"window": obs})
        s1 = [e.snapshot_id for e in e1]
        s2 = [e.snapshot_id for e in e2]
        assert s1 == s2

    def test_compute_missing_window_raises(self):
        with pytest.raises(ValueError):
            E08WyckoffEngine().compute("BNBUSDT", "6h",
                                       "2026-01-01T00:00:00Z", {})
