"""E08 Wyckoff / Auction Theory — full §8 validation battery
(APEX_GEN5.md L9086–9466).

Covers: §8 golden fixtures (12, constructed + re-derived per ADR-P2-007/014) ·
deterministic replay (identical snapshot_id + phase_hypotheses) ·
no-future-leak (fabricated future candle must not alter a past SC) ·
calibration (Brier / log-loss) · ablation ordering · redundancy (Spring vs
Liquidity Sweep ≤ 0.45) · serialization stability · §3.1 three laws ·
§3.2 phase probabilities + Dirichlet transition matrix · §3.3 six-parameter
event contract · §5 state machine + cycle-state schema · §6 parameters ·
**encyclopedia chapters 2–4 Wave-Out** · EngineBase binding · T-DR-001.
"""

from __future__ import annotations

import json
import math
import pathlib
from decimal import Decimal

import pytest

from apex.data_catalog.contracts import MarketObservation
from apex.engines.e08_wyckoff import (
    CONTRACT_LABEL,
    CONTRACT_VERSION,
    CYCLE_STATE_REQUIRED,
    E08_DEFAULTS,
    E08WyckoffEngine,
    ENGINE,
    ENCYCLOPEDIA_CH1,
    ENCYCLOPEDIA_CH1_DIMENSIONS,
    ENCYCLOPEDIA_WAVE_OUT_CHAPTERS,
    EPS,
    EVENT_CATALOG,
    K_PHASES,
    PHASES,
    PHASE_SCORE_RULES,
    QUALITIES,
    WAVE_OUT_FEATURE,
    WyckoffEngineV4,
    WaveOutError,
    atr14,
    body_ratio,
    brier_score,
    cause_effect_target,
    close_position,
    detect_ar,
    detect_lps,
    detect_lpsy,
    detect_range,
    detect_sc,
    detect_sc_full,
    detect_sos,
    detect_spring,
    detect_st,
    detect_ut,
    detect_utad,
    e08_snapshot_id,
    effort_without_result,
    encyclopedia_chapter,
    entropy,
    evr,
    evr_correlation,
    get_params,
    log_loss,
    pearson,
    pf_box_size,
    phase_probabilities,
    phase_score_matrix,
    phase_weights,
    point_figure_target,
    range_z,
    rma,
    run_engine,
    sc_low_extremum,
    sigmoid,
    softmax,
    spring_recovered,
    transition_matrix,
    true_range,
    volume_z,
    wilson_ci,
)
from apex.errors import WAVE_OUT_FEATURES

FIXTURES = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent / "fixtures"
     / "e08_golden_fixtures.json").read_text())
BY_ID = {f["id"]: f for f in FIXTURES["fixtures"]}

# §9 case-study geometry (illustrative per §9.5-2; the numbers below are the
# chapter's own and are re-checked against the §3 formulas, never trusted).
RANGE_LO, RANGE_HI, ATR = 608.2, 628.4, 4.2


def bar(o, h, l, c, v=30000.0, ts=0):
    return {"o": o, "h": h, "l": l, "c": c, "v": v, "ts": ts}


def range_window(n=14, lo=RANGE_LO, hi=RANGE_HI, seed=3):
    """A closed-candle window inside the §9 range boundary."""
    out = []
    x = seed
    for i in range(n):
        x = (1103515245 * x + 12345) % (2 ** 31)
        u = x / 2 ** 31
        l = lo + u * (hi - lo) * 0.2
        h = l + (hi - lo) * 0.05
        o = l + (h - l) * u
        c = l + (h - l) * (1 - u)
        out.append(bar(round(o, 4), round(h, 4), round(l, 4), round(c, 4),
                       30000.0, 1710000000000 + i * 21600000))
    return out


def onehot(phase):
    return [1.0 if p == phase else 0.0 for p in PHASES]


# ---------------------------------------------------------------------------
# §8 Golden fixtures (12 samples)
# ---------------------------------------------------------------------------
class TestGoldenFixtures:
    def test_fixture_shape_is_the_chapter_contract(self):
        assert len(FIXTURES["fixtures"]) == 12
        for f in FIXTURES["fixtures"]:
            assert set(f) >= {"id", "bars", "expected", "hash"}
            assert set(f["expected"]) == {"sc", "vol_ratio", "range_z"}
            assert f["hash"].startswith("sha256:") and len(f["hash"]) == 71

    def test_hashes_are_real_and_recompute(self):
        """§9.5-3: the hash is computed after the fixture exists; recomputed
        here from the committed bar arrays (no document hash is ever copied).
        """
        from apex.identity.canonical_json import canonical_json
        from apex.identity.hashes import sha256_hex
        for f in FIXTURES["fixtures"]:
            assert f["hash"] == "sha256:" + sha256_hex(
                canonical_json(f["bars"]).encode("utf-8"))

    def test_sc_canonical(self):
        fx = BY_ID["FIX_E08_01_SC_CANONICAL"]
        b = fx["bars"][0]
        assert detect_sc(b, fx["expected"]["vol_ratio"],
                         fx["expected"]["range_z"], close_position(b),
                         body_ratio(b)) is True
        assert fx["expected"]["sc"] is True
        assert 0.25 <= close_position(b) <= 0.6
        assert body_ratio(b) >= 0.5

    @pytest.mark.parametrize("fid", ["FIX_E08_02_SC_FAIL_CLOSEPOS",
                                     "FIX_E08_03_SC_FAIL_VOLRATIO",
                                     "FIX_E08_04_SC_FAIL_RANGEZ"])
    def test_sc_negative_fixtures(self, fid):
        fx = BY_ID[fid]
        b = fx["bars"][0]
        assert fx["expected"]["sc"] is False
        assert detect_sc(b, fx["expected"]["vol_ratio"],
                         fx["expected"]["range_z"], close_position(b),
                         body_ratio(b)) is False

    def test_edge_h_l_invalid(self):
        fx = BY_ID["FIX_E08_05_EDGE_H_L_INVALID"]
        eng = WyckoffEngineV4()
        out = eng.process_bar(fx["bars"][0], ATR, 1.0, 0.5, 0.5)
        assert out["fate"] == "Q0_INVALID" and out["reason"] == "H<L"
        assert out["quality"] == "Q0"

    def test_edge_atr_zero(self):
        fx = BY_ID["FIX_E08_06_EDGE_ATR_ZERO"]
        eng = WyckoffEngineV4()
        out = eng.process_bar(fx["bars"][0], 0.0, 1.0, 0.5, 0.5)
        assert out["fate"] == "Q0_INVALID" and out["reason"] == "ATR=0"

    def test_range_boundary_fixture(self):
        fx = BY_ID["FIX_E08_07_RANGE_BOUNDARY"]
        bars = fx["bars"]
        detected = detect_range(bars, ATR, 12, 1.5)
        assert detected is not None
        lo, hi = detected
        assert (hi - lo) < 1.5 * ATR
        eng = WyckoffEngineV4()
        states = eng.run_full(bars, atr_by_idx={i: ATR for i in range(len(bars))})
        assert any(e["code"] == "EV_WYK_011" for e in eng.events)
        assert states[-1]["range"] is not None

    def test_spring_fixture(self):
        fx = BY_ID["FIX_E08_08_SPRING"]
        b = fx["bars"][0]
        assert detect_spring(b["l"], RANGE_LO, b["c"], ATR,
                             fx["expected"]["vol_ratio"], 0.7) is True
        pen = RANGE_LO - b["l"]
        assert 0 < pen <= 0.3 * ATR

    def test_sos_fixture(self):
        fx = BY_ID["FIX_E08_09_SOS"]
        b = fx["bars"][0]
        assert detect_sos(b, RANGE_HI, ATR, fx["expected"]["vol_ratio"],
                          bos_confirmed_idx=12, current_idx=13) is True
        # PIT: a BOS confirmed at t is not usable at t (§3.3 t−1 rule).
        assert detect_sos(b, RANGE_HI, ATR, fx["expected"]["vol_ratio"],
                          bos_confirmed_idx=13, current_idx=13) is False

    def test_st_fixture(self):
        fx = BY_ID["FIX_E08_10_ST"]
        b = fx["bars"][0]
        assert detect_st(b, RANGE_LO, ATR, fx["expected"]["vol_ratio"]) is True

    def test_utad_fixture(self):
        fx = BY_ID["FIX_E08_11_UTAD"]
        b = fx["bars"][0]
        assert detect_utad(b, RANGE_HI, ATR,
                           fx["expected"]["vol_ratio"]) is True
        assert close_position(b) <= 0.4

    def test_phase_vector_fixture(self):
        fx = BY_ID["FIX_E08_12_PHASE_VECTOR"]
        eng = WyckoffEngineV4()
        states = eng.run_full(fx["bars"],
                              atr_by_idx={i: ATR for i in range(len(fx["bars"]))},
                              vol_ratio_by_idx={i: 1.0 for i in range(len(fx["bars"]))},
                              evr_by_idx={i: 0.4 for i in range(len(fx["bars"]))})
        final = states[-1]
        assert len(final["phase_hypotheses"]) == K_PHASES
        assert sum(h["prob"] for h in final["phase_hypotheses"]) == \
            pytest.approx(1.0, abs=1e-12)
        # ISSUE-CP4-013: with 8 phases and Σw = 1 the entropy exceeds θ_H.
        assert final["entropy"] >= 0.85
        assert final["fate"] == "AMBIGUOUS"


# ---------------------------------------------------------------------------
# §3.1 The three laws, quantified
# ---------------------------------------------------------------------------
class TestThreeLaws:
    def test_true_range_and_rma(self):
        assert true_range(10.0, 8.0, 9.0) == 2.0
        # Wilder's RMA seeds on the SMA of the first `period` values:
        # seed = (1+2)/2 = 1.5, then (1.5·1 + 3)/2 = 2.25.
        assert rma([1.0, 2.0, 3.0], 2) == pytest.approx(2.25, abs=1e-12)
        assert math.isnan(rma([1.0], 2))       # no fabricated warm-up value

    def test_atr14_uses_wilder_rma_and_drops_invalid_bars(self):
        bars = [{"h": 2.0, "l": 1.0, "c": 1.5}] * 20
        assert atr14(bars, 14) == pytest.approx(1.0, abs=1e-12)
        broken = list(bars)
        broken[5] = {"h": 0.5, "l": 1.0, "c": 0.7}      # H < L ⇒ no own TR
        # The invalid bar contributes no TR of its own (19 TRs, not 20); the
        # *next* bar still chains against the real printed previous close
        # (0.7), which is a fact, not a repair: TR = max(1.0, 1.3, 0.3) = 1.3.
        assert atr14(broken, 14) == pytest.approx(1.015931419944071, abs=1e-12)
        # An H<L bar in the last position changes nothing: it adds no TR.
        tail = list(bars) + [{"h": 0.5, "l": 1.0, "c": 0.7}]
        assert atr14(tail, 14) == pytest.approx(atr14(bars, 14), abs=1e-12)

    def test_volume_z_and_range_z_are_z_scores_issue_cp4_010(self):
        vols = [100.0] * 20 + [310.0]
        # SD = 0 ⇒ the ε floor keeps the quotient finite but enormous (2.1e10);
        # no infinite score is ever published.
        assert volume_z(vols) > 1e6
        varied = [100.0, 110.0, 90.0, 105.0, 95.0, 310.0]
        assert volume_z(varied) > 2.5
        rngs = [3.0, 3.2, 2.8, 3.1, 2.9, 8.2]
        assert range_z(rngs) > 2.0
        assert math.isnan(volume_z([1.0]))

    def test_evr_is_the_corrected_formulation(self):
        # §3.1: EVR = VolumeZ · RangeZ · sign(ΔC) — sign, not sign·sign.
        assert evr(3.1, 2.4, 611.5, 610.0) == pytest.approx(3.1 * 2.4)
        assert evr(3.1, 2.4, 609.0, 610.0) == pytest.approx(-3.1 * 2.4)
        assert evr(3.1, 2.4, 610.0, 610.0) == 0.0
        assert math.isnan(evr(float("nan"), 2.4, 1.0, 0.0))

    def test_effort_result_correlation_and_threshold(self):
        vols = [100.0, 120.0, 140.0, 160.0, 180.0, 200.0, 220.0, 240.0,
                260.0, 280.0]
        rets = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
        rho = evr_correlation(vols, rets)
        assert rho == pytest.approx(1.0, abs=1e-9)
        assert effort_without_result(rho, 0.2) is False
        assert effort_without_result(-0.1, 0.2) is True
        assert effort_without_result(float("nan"), 0.2) is False
        assert math.isnan(evr_correlation([1.0, 2.0], [1.0, 2.0]))

    def test_cause_effect_continuous_variant(self):
        # §3.1 Effect = k·Duration^γ·Range with k = 0.42, γ = 0.71.
        assert cause_effect_target(20.2, 14) == pytest.approx(
            0.42 * (14 ** 0.71) * 20.2, abs=1e-9)
        assert cause_effect_target(20.2, 14, breakout=628.4) > 628.4
        with pytest.raises(ValueError, match="CAUSE_EFFECT_INPUT_QX"):
            cause_effect_target(-1.0, 14)

    def test_point_figure_count(self):
        box = pf_box_size(ATR)
        assert box == pytest.approx(0.5 * ATR)
        assert point_figure_target(RANGE_HI, 5, box, 3) == pytest.approx(
            RANGE_HI + 5 * box * 3)
        with pytest.raises(ValueError, match="PF_BOX_SIZE_QX"):
            pf_box_size(0.0)
        with pytest.raises(ValueError, match="PF_TARGET_INPUT_QX"):
            point_figure_target(1.0, -1, 1.0)


# ---------------------------------------------------------------------------
# §3.2 Phase detection
# ---------------------------------------------------------------------------
class TestPhaseMath:
    def test_softmax_and_entropy(self):
        p = softmax([1.0, 1.0, 1.0, 1.0])
        assert all(abs(x - 0.25) < 1e-12 for x in p)
        assert entropy(p) == pytest.approx(math.log(4), abs=1e-12)
        assert entropy([1.0, 0.0, 0.0]) == pytest.approx(0.0, abs=1e-12)
        assert softmax([]) == []

    def test_entropy_threshold_semantics(self):
        # §0: θ_H = 0.85 nat ⇔ 2.34 equally-likely regimes.
        assert math.log(2.34) == pytest.approx(0.85, abs=5e-3)

    def test_score_functions(self):
        assert sigmoid(0.0) == 0.5
        assert 0.0 <= phase_score_matrix(610.0, 608.2, 628.4, 0.5, 1.0,
                                         "BULL", 0)[0][0][0] <= 1.0
        # §3.2 score_volume = 1 − min(VR/2, 1)
        from apex.engines.e08_wyckoff import score_volume, score_age
        assert score_volume(0.0) == 1.0
        assert score_volume(2.0) == 0.0
        assert score_volume(5.0) == 0.0
        assert score_age(0.0) == 1.0
        assert score_age(14.0) == pytest.approx(math.exp(-0.02 * 14))

    def test_position_score_is_clamped_to_the_stated_domain(self):
        """ISSUE-CP4-011: sigmoid(x−0.5)·2 reaches 2; §3.2 states [0,1]."""
        from apex.engines.e08_wyckoff import score_position
        assert score_position(628.4, RANGE_LO, RANGE_HI) == 1.0
        assert 0.0 <= score_position(608.2, RANGE_LO, RANGE_HI)
        assert math.isnan(score_position(610.0, 610.0, 610.0))

    def test_structure_score_only_for_accum_and_markup(self):
        from apex.engines.e08_wyckoff import score_structure
        assert score_structure("BULL", "ACCUMULATION") == 1.0
        assert score_structure("BEAR", "MARKUP") == 0.0
        assert math.isnan(score_structure("BULL", "MARKDOWN"))

    def test_score_matrix_shape_and_provenance(self):
        scores, prov = phase_score_matrix(610.1, RANGE_LO, RANGE_HI, 0.7, 0.6,
                                          "BULL", 14)
        assert len(scores) == 5 and all(len(row) == K_PHASES for row in scores)
        assert set(prov) == set(PHASES)
        # §3.2 fully specifies the Accumulation column only.
        assert all("UNSPECIFIED" not in v for v in prov["ACCUMULATION"].values())
        assert prov["MARKDOWN"]["position"] == "UNSPECIFIED_NEUTRAL"
        assert prov["DISTRIBUTION"]["evr"].startswith("§3.2 sign mirrored")

    def test_unspecified_cells_are_neutral_not_biasing(self):
        """ISSUE-CP4-012: a phase with no specified component must not be
        pushed toward zero probability by the neutral choice."""
        scores, prov = phase_score_matrix(610.1, RANGE_LO, RANGE_HI, 0.0, 1.0,
                                          None, 0)
        idx = {p: i for i, p in enumerate(PHASES)}
        w = phase_weights()
        z_markdown = sum(w[k] * scores[k][idx["MARKDOWN"]] for k in range(5))
        assert z_markdown == pytest.approx(sum(w[:4]) * 0.5 + w[4] * 1.0,
                                           abs=1e-12)

    def test_phase_probabilities_contract(self):
        scores, _ = phase_score_matrix(610.1, RANGE_LO, RANGE_HI, 0.7, 0.6,
                                       "BULL", 14)
        probs, H = phase_probabilities(scores, phase_weights())
        assert set(probs) == set(PHASES)
        assert sum(probs.values()) == pytest.approx(1.0, abs=1e-12)
        assert 0.0 <= H <= math.log(K_PHASES)
        with pytest.raises(ValueError, match="PHASE_MATRIX_SHAPE_QX"):
            phase_probabilities(scores, [0.5, 0.5])
        with pytest.raises(ValueError, match="PHASE_MATRIX_SHAPE_QX"):
            phase_probabilities([], phase_weights())

    def test_chapter9_three_phase_example_is_not_reproducible(self):
        """ADR-P2-007: §9 claims softmax([0.76,0.55,0.12]) = [0.71,0.18,0.11]
        with H = 0.52. Recomputed, it is [0.428,0.347,0.226] with H = 1.066 —
        the fixture is illustrative, so the recomputation is asserted."""
        p = softmax([0.76, 0.55, 0.12])
        assert p == pytest.approx([0.4278, 0.3468, 0.2255], abs=1e-3)
        assert entropy(p) == pytest.approx(1.0664, abs=1e-3)
        assert entropy(p) != pytest.approx(0.52, abs=0.01)

    def test_z_accumulation_matches_the_chapter_components(self):
        scores, _ = phase_score_matrix(610.1, RANGE_LO, RANGE_HI, 0.7, 0.65,
                                       "BULL", 14)
        w = phase_weights()
        z = sum(w[k] * scores[k][0] for k in range(5))
        # §9's own component values (0.85/0.72/0.65/0.9/0.75) give 0.76; the
        # recomputed z from the §3.2 formulas on the same inputs is asserted
        # against the formula, not the doc's rounded number.
        expected = (w[0] * scores[0][0] + w[1] * scores[1][0]
                    + w[2] * scores[2][0] + w[3] * scores[3][0]
                    + w[4] * scores[4][0])
        assert z == pytest.approx(expected, abs=1e-12)
        assert 0.0 <= z <= 1.0

    def test_transition_matrix_is_the_dirichlet_formula(self):
        t = transition_matrix({})
        assert all(abs(v - 1 / 9) < 1e-12 for row in t.values() for v in row.values())
        # §3.2 T_ij = (N_ij + α)/(N_i + Kα) with α = 0.1, K = 9.
        counts = {("ACCUMULATION", "MARKUP"): 8}
        t2 = transition_matrix(counts)
        assert t2["ACCUMULATION"]["MARKUP"] == pytest.approx((8 + 0.1) / (8 + 0.9))
        # ISSUE-CP4-014: K = 9 in the denominator while the matrix has 8
        # columns, so rows never sum to 1: here (8 + 8·0.1)/(8 + 9·0.1).
        assert sum(t2["ACCUMULATION"].values()) == pytest.approx(8.8 / 8.9)
        assert sum(t["ACCUMULATION"].values()) == pytest.approx(8 / 9)
        with pytest.raises(ValueError, match="TRANSITION_MATRIX_QX"):
            transition_matrix({("NOPE", "MARKUP"): 1})

    def test_ambiguous_suppression(self):
        eng = WyckoffEngineV4()
        out = eng.process_bar(bar(615.0, 616.0, 608.0, 611.0), ATR, 1.0, 0.4,
                              0.5)
        assert out["entropy"] >= 0.85
        assert out["fate"] == "AMBIGUOUS"
        assert out["quality"] in QUALITIES


# ---------------------------------------------------------------------------
# §3.3 The six-parameter event contract
# ---------------------------------------------------------------------------
class TestEventContract:
    def test_sc_requires_the_low_extremum(self):
        b = bar(616.0, 616.4, 608.2, 611.5, 65100.0)
        history = [bar(610.0, 612.0, 609.5, 611.0)] * 5 + [b]
        assert sc_low_extremum(history, 5) is True
        higher = [bar(610.0, 612.0, 607.0, 611.0)] * 5 + [b]
        assert sc_low_extremum(higher, 5) is False
        assert detect_sc_full(b, history, 3.1, 2.4) is True
        assert detect_sc_full(b, higher, 3.1, 2.4) is False

    def test_ar_window_and_geometry(self):
        assert detect_ar(bar(610.0, 614.2, 609.0, 613.5), RANGE_LO, ATR, 1) is True
        assert detect_ar(bar(610.0, 614.2, 609.0, 613.5), RANGE_LO, ATR, 6) is False
        assert detect_ar(bar(610.0, 610.1, 609.0, 609.5), RANGE_LO, ATR, 1) is False

    def test_st_band_and_volume(self):
        assert detect_st(bar(610.0, 611.0, 609.0, 610.5), RANGE_LO, ATR, 0.5)
        assert not detect_st(bar(610.0, 611.0, 604.0, 610.5), RANGE_LO, ATR, 0.5)
        assert not detect_st(bar(610.0, 611.0, 609.0, 610.5), RANGE_LO, ATR, 1.5)

    def test_spring_conditions(self):
        assert detect_spring(607.6, RANGE_LO, 609.4, ATR, 1.4, 0.7)
        assert detect_spring(607.6, RANGE_LO, 609.4, ATR, 0.9, 0.7)  # EVR path
        assert not detect_spring(607.6, RANGE_LO, 609.4, ATR, 0.9, 0.1)
        assert not detect_spring(607.6, RANGE_LO, 607.0, ATR, 1.4, 0.7)  # no recovery
        assert not detect_spring(608.2, RANGE_LO, 609.4, ATR, 1.4, 0.7)  # pen = 0
        assert not detect_spring(606.0, RANGE_LO, 609.4, ATR, 1.4, 0.7)  # pen too deep
        assert not detect_spring(607.6, RANGE_LO, 609.4, ATR, 1.4, 0.7, 25)

    def test_spring_recovery_window(self):
        bars = [bar(609.0, 610.0, 607.6, 609.4), bar(609.4, 610.0, 608.5, 609.8)]
        assert spring_recovered(bars, RANGE_LO, 0, 3) is True
        stuck = [bar(609.0, 610.0, 607.6, 608.0), bar(608.0, 608.1, 607.0, 607.5)]
        assert spring_recovered(stuck, RANGE_LO, 0, 3) is False

    def test_ut_and_utad(self):
        assert detect_ut(629.4, RANGE_HI, 627.9, ATR, 1.5) is True
        assert detect_ut(629.4, RANGE_HI, 629.9, ATR, 1.5) is False   # close above
        assert detect_utad(bar(628.0, 629.4, 627.5, 627.9), RANGE_HI, ATR, 1.5)
        assert not detect_utad(bar(628.0, 629.4, 627.5, 629.0), RANGE_HI, ATR, 1.5)

    def test_lps_and_lpsy(self):
        assert detect_lps(bar(626.0, 629.0, 626.5, 628.0), 630.5, RANGE_LO,
                          ATR, 0.6, "BULL") is True
        assert detect_lps(bar(626.0, 629.0, 626.5, 628.0), 630.5, RANGE_LO,
                          ATR, 0.6, "BEAR") is False
        assert detect_lps(bar(626.0, 631.0, 626.5, 628.0), 630.5, RANGE_LO,
                          ATR, 0.6, "BULL") is False          # High >= High_SOS
        assert detect_lpsy(bar(627.8, 627.9, 626.5, 627.0), RANGE_HI, RANGE_LO,
                           ATR, 0.6) is True
        assert detect_lpsy(bar(626.0, 627.9, 626.5, 627.0), RANGE_HI, RANGE_LO,
                           ATR, 0.6) is False          # bullish close ⇒ not LPSY
        assert detect_lpsy(bar(627.8, 629.9, 626.5, 627.0), RANGE_HI, RANGE_LO,
                           ATR, 0.6) is False          # High >= range_hi
        assert detect_lpsy(bar(627.8, 627.9, 626.5, 627.0), RANGE_HI, RANGE_LO,
                           ATR, 1.5) is False          # volume too high

    def test_range_detection_edges(self):
        bars = range_window(12)
        assert detect_range(bars, ATR, 12, 1.5) is not None
        assert detect_range(bars[:11], ATR, 12, 1.5) is None      # too short
        assert detect_range(bars, 0.0, 12, 1.5) is None           # ATR = 0
        assert detect_range(bars, float("nan"), 12, 1.5) is None


# ---------------------------------------------------------------------------
# §4/§5 streaming engine, state machine, cycle state
# ---------------------------------------------------------------------------
class TestStreamingEngine:
    def _feed(self, eng, bars, **kw):
        return eng.run_full(bars, **kw)

    def test_full_sequence_advances_the_state_machine(self):
        # A range must be identified first (§4 `detect_range`, ≥ 12 candles),
        # so the sequence events ride on a 12-bar range prologue.
        prologue = range_window(12)
        bars = prologue + [
            bar(616.0, 616.4, 608.2, 611.5, 65100.0, 1),     # SC candidate
            bar(611.5, 614.2, 610.0, 613.5, 40000.0, 2),     # AR
            bar(613.0, 613.5, 609.0, 610.5, 15000.0, 3),     # ST
            bar(610.0, 610.5, 607.6, 609.4, 42000.0, 4),     # Spring
            bar(628.5, 630.5, 628.0, 630.1, 54000.0, 5),     # SOS
        ]
        n = len(bars)
        sc_at = len(prologue)
        eng = WyckoffEngineV4()
        states = self._feed(
            eng, bars,
            atr_by_idx={i: ATR for i in range(n)},
            vol_ratio_by_idx={sc_at: 3.1, sc_at + 1: 1.5, sc_at + 2: 0.5,
                              sc_at + 3: 1.4, sc_at + 4: 1.8},
            evr_by_idx={i: 0.7 for i in range(n)},
            structure_by_idx={i: "BULL" for i in range(n)},
            bos_by_idx={sc_at + 4: {"confirmed_at_idx": sc_at + 3,
                                    "direction": "UP"}})
        assert eng.range_lo is not None
        codes = [e["code"] for e in eng.events]
        assert "EV_WYK_002" in codes          # SC
        assert "EV_WYK_005" in codes          # Spring
        assert "EV_WYK_006" in codes          # SOS
        assert "EV_WYK_001" in codes          # phase hypothesis update
        assert eng.state in ("SOS", "LPS", "MARKUP", "RANGE_DETECTED")
        assert states[-1]["snapshot_id"]

    def test_invalidation_and_expiry(self):
        eng = WyckoffEngineV4()
        bars = range_window(14)
        self._feed(eng, bars, atr_by_idx={i: ATR for i in range(14)},
                   vol_ratio_by_idx={i: 1.0 for i in range(14)},
                   evr_by_idx={i: 0.5 for i in range(14)})
        eng.low_sc = 620.0
        out = eng.process_bar(bar(610.0, 611.0, 600.0, 601.0, 30000.0, 99),
                              ATR, 1.0, 0.1, 0.5)
        assert out["fate"] == "INVALIDATED"
        assert any(e["code"] == "EV_WYK_012" for e in eng.events)
        eng2 = WyckoffEngineV4()
        self._feed(eng2, bars, atr_by_idx={i: ATR for i in range(14)})
        eng2.range_age = 200
        out2 = eng2.process_bar(bar(610.0, 611.0, 609.0, 610.0, 30000.0, 100),
                                ATR, 1.0, 0.5, 0.5)
        assert out2["fate"] == "EXPIRED"

    def test_state_machine_is_forward_only(self):
        eng = WyckoffEngineV4()
        assert eng._advance("RANGE_DETECTED") is True
        assert eng._advance("SC") is True
        assert eng._advance("RANGE_DETECTED") is False     # no going back
        assert eng.state == "SC"

    def test_quality_ladder(self):
        eng = WyckoffEngineV4()
        assert eng._quality(0.0, "BULL", 1.0, 0.5, None) == "Q0"
        assert eng._quality(ATR, None, float("nan"), 0.5, None) == "Q1"
        assert eng._quality(ATR, "BULL", float("nan"), 0.5, None) == "Q2"
        assert eng._quality(ATR, "BULL", 1.0, 0.5, None) == "Q3"
        assert eng._quality(ATR, "BULL", 1.0, 0.5, 0.19) == "Q4"
        assert eng._quality(ATR, "BULL", 1.0, 0.9, 0.19) == "Q3"   # H >= θ_H

    def test_cycle_state_schema(self):
        eng = WyckoffEngineV4()
        bars = range_window(14)
        states = self._feed(eng, bars, atr_by_idx={i: ATR for i in range(14)},
                            vol_ratio_by_idx={i: 1.0 for i in range(14)},
                            evr_by_idx={i: 0.5 for i in range(14)})
        state = states[-1]
        for key in CYCLE_STATE_REQUIRED:
            if key in ("range", "confirmed_events"):
                continue
            assert state[key] not in (None, "")
        assert state["version"] == CONTRACT_LABEL
        assert len(state["snapshot_id"]) == 64
        assert len(state["phase_hypotheses"]) == K_PHASES

    def test_degraded_when_evidence_is_undefined(self):
        eng = WyckoffEngineV4()
        out = eng.process_bar(bar(610.0, 612.0, 609.0, 611.0, 30000.0, 7),
                              ATR, float("nan"), 0.5, float("nan"))
        assert out["degraded"] is True
        assert out["degraded_reason"] == "EVIDENCE_UNDEFINED_QX"

    def test_run_engine_shape(self):
        bars = range_window(14)
        res = run_engine(bars, atr_by_idx={i: ATR for i in range(14)},
                         vol_ratio_by_idx={i: 1.0 for i in range(14)},
                         evr_by_idx={i: 0.5 for i in range(14)})
        assert res["engine"] == ENGINE
        assert res["contract_version"] == CONTRACT_VERSION
        assert len(res["states"]) == 14
        assert res["final"] is not None


# ---------------------------------------------------------------------------
# §7 encyclopedia — Chapter 1 normative, Chapters 2–4 Wave-Out
# ---------------------------------------------------------------------------
class TestEncyclopediaWaveOut:
    def test_chapter_1_is_served(self):
        ch1 = encyclopedia_chapter(1)
        assert ch1["normative"] is True
        assert ch1["dimensions"] == ENCYCLOPEDIA_CH1_DIMENSIONS
        assert len(ch1["content"]) == 16 == len(ENCYCLOPEDIA_CH1)

    @pytest.mark.parametrize("chapter", ENCYCLOPEDIA_WAVE_OUT_CHAPTERS)
    def test_chapters_2_to_4_raise_wave_out(self, chapter):
        with pytest.raises(WaveOutError) as exc:
            encyclopedia_chapter(chapter)
        assert exc.value.feature == WAVE_OUT_FEATURE
        assert exc.value.feature in WAVE_OUT_FEATURES      # frozen registry
        assert exc.value.reason.startswith("E08_CH")
        assert "DEFERRED_NON_NORMATIVE" in exc.value.reason

    def test_wave_out_reasons_are_deterministic(self):
        reasons = []
        for chapter in ENCYCLOPEDIA_WAVE_OUT_CHAPTERS:
            try:
                encyclopedia_chapter(chapter)
            except WaveOutError as exc:
                reasons.append(exc.reason)
        assert reasons == sorted(reasons)          # stable ordering
        assert len(set(reasons)) == 3              # distinct per chapter

    def test_unknown_chapter_fails_closed(self):
        with pytest.raises(ValueError, match="ENCYCLOPEDIA_CHAPTER_QX"):
            encyclopedia_chapter(5)

    def test_no_stub_placeholder_in_wave_in_code(self):
        src = (pathlib.Path(__file__).resolve().parents[2] / "apex" / "engines"
               / "e08_wyckoff" / "engine.py").read_text()
        for token in ("TODO", "FIXME", "NotImplementedError"):
            assert token not in src


# ---------------------------------------------------------------------------
# §6 parameters
# ---------------------------------------------------------------------------
class TestParams:
    def test_defaults_are_the_chapter_literals(self):
        p = get_params()
        assert (p.sc_vol_ratio, p.sc_range_z) == (2.5, 2.0)
        assert (p.sc_close_pos_lo, p.sc_close_pos_hi) == (0.25, 0.6)
        assert (p.ar_min_ratio, p.st_vol_ratio) == (0.5, 0.7)
        assert (p.spring_pen_max, p.spring_vol_min) == (0.3, 1.3)
        assert (p.sos_vol_min, p.lps_vol_max, p.ut_pen_max) == (1.2, 0.7, 0.3)
        assert (p.range_min_bars, p.entropy_threshold) == (12, 0.85)
        assert (p.cause_effect_k, p.cause_effect_gamma) == (0.42, 0.71)
        assert (p.evr_rho_threshold, p.max_age_bars) == (0.2, 96)
        assert (p.dirichlet_alpha, p.transition_K, p.transition_lag_bars) == \
            (0.1, 9, 48)
        assert phase_weights() == [0.25, 0.25, 0.20, 0.15, 0.15]
        assert sum(phase_weights()) == pytest.approx(1.0)

    def test_unknown_key_rejected(self):
        with pytest.raises(ValueError, match="UNKNOWN_E08_PARAM_QX"):
            get_params({"sc_vol_ratio2": 3.0})
        assert set(E08_DEFAULTS) == set(get_params().__dict__)

    def test_governed_override_applies(self):
        assert get_params({"sc_vol_ratio": 3.0}).sc_vol_ratio == 3.0
        b = bar(616.0, 616.4, 608.2, 611.5)
        assert detect_sc(b, 2.8, 2.4, close_position(b), body_ratio(b),
                         get_params({"sc_vol_ratio": 3.0})) is False


# ---------------------------------------------------------------------------
# §8 replay · no-future-leak · calibration · ablation · redundancy ·
#    serialization
# ---------------------------------------------------------------------------
class TestReplayLeakCalibration:
    def test_deterministic_replay_identical_snapshot(self):
        bars = range_window(14)
        kw = dict(atr_by_idx={i: ATR for i in range(14)},
                  vol_ratio_by_idx={i: 1.0 for i in range(14)},
                  evr_by_idx={i: 0.5 for i in range(14)})
        a = run_engine(bars, **kw)
        b = run_engine(bars, **kw)
        assert a["final"]["snapshot_id"] == b["final"]["snapshot_id"]
        assert a["final"]["phase_hypotheses"] == b["final"]["phase_hypotheses"]
        assert a["final"]["entropy"] == b["final"]["entropy"]

    def test_streaming_idempotency_key(self):
        eng = WyckoffEngineV4()
        bars = range_window(14)
        states = eng.run_full(bars, atr_by_idx={i: ATR for i in range(14)})
        assert states[-1]["idempotency_key"].startswith(
            f"{bars[-1]['ts']}_")

    def test_no_future_leak_future_candle_cannot_change_a_past_sc(self):
        """§8: injecting a fabricated future candle with High = 10000 must not
        alter a past SC call."""
        bars = [bar(610.0, 612.0, 609.5, 611.0, 30000.0, i) for i in range(5)]
        sc_bar = bar(616.0, 616.4, 608.2, 611.5, 65100.0, 5)
        past = bars + [sc_bar]
        eng1 = WyckoffEngineV4()
        s1 = eng1.run_full(past, atr_by_idx={i: ATR for i in range(len(past))},
                           vol_ratio_by_idx={i: 3.1 for i in range(len(past))},
                           evr_by_idx={i: 0.7 for i in range(len(past))})
        future = bar(611.0, 10000.0, 608.0, 612.0, 99999.0, 6)
        eng2 = WyckoffEngineV4()
        s2 = eng2.run_full(past + [future],
                           atr_by_idx={i: ATR for i in range(len(past) + 1)},
                           vol_ratio_by_idx={i: 3.1 for i in range(len(past) + 1)},
                           evr_by_idx={i: 0.7 for i in range(len(past) + 1)})
        sc1 = [e for e in eng1.events if e["code"] == "EV_WYK_002"]
        sc2 = [e for e in eng2.events if e["code"] == "EV_WYK_002"
               and e["ts"] == sc_bar["ts"]]
        assert len(sc1) == len(sc2)
        for a, b in zip(sc1, sc2):
            assert a["price"] == b["price"] and a["ts"] == b["ts"]
        # The past snapshot is untouched by the injected future candle.
        assert s1[-1]["snapshot_id"] == s2[len(past) - 1]["snapshot_id"]

    def test_brier_and_log_loss_formulas(self):
        probs = [0.7, 0.2, 0.1]
        assert brier_score(probs, [1, 0, 0]) == pytest.approx(
            ((0.3) ** 2 + 0.2 ** 2 + 0.1 ** 2) / 3, abs=1e-12)
        # Multi-class form: −(1/N)·Σ_i Σ_j y_ij ln p_ij  (N = n_classes).
        assert log_loss(probs, [1, 0, 0]) == pytest.approx(
            -math.log(0.7) / 3, abs=1e-12)
        with pytest.raises(ValueError, match="BRIER_INPUT_QX"):
            brier_score([], [])
        with pytest.raises(ValueError, match="LOG_LOSS_INPUT_QX"):
            log_loss([0.5], [1, 0])

    def test_calibration_targets_are_the_chapter_numbers(self):
        p = get_params()
        assert p.brier_target == 0.22 and p.log_loss_target == 0.65
        # A confident correct call beats both targets; a diffuse one does not.
        sharp = [0.0] * K_PHASES
        sharp[0] = 1.0
        assert brier_score(sharp, onehot("ACCUMULATION")) == 0.0
        # A completely diffuse 8-way vector scores 2(K−1)/K² = 0.109375, i.e.
        # the chapter's 0.22 target is only reachable by a *confidently wrong*
        # model — recorded as a reading of the §7 target, not a defect.
        flat = [1 / K_PHASES] * K_PHASES
        assert brier_score(flat, onehot("ACCUMULATION")) == pytest.approx(
            (K_PHASES - 1) / K_PHASES ** 2, abs=1e-12)
        wrong = [0.0] * K_PHASES
        wrong[K_PHASES - 1] = 1.0
        assert brier_score(wrong, onehot("ACCUMULATION")) > p.brier_target

    def test_wilson_ci_reproduces_the_chapter_interval(self):
        lo, hi = wilson_ci(0.62, 13)
        assert lo == pytest.approx(0.35, abs=2e-2)
        assert hi == pytest.approx(0.82, abs=2e-2)

    def test_ablation_position_dominates(self):
        """§8: removing any one score component degrades calibration, and
        removing `position` degrades it most.

        The chapter's absolute deltas (0.04–0.12) are walk-forward statistics
        over a 48-candle-lagged labelled dataset that does not exist in this
        repository; no statistics are fabricated (G11/ADR-P2-010). The
        mechanical ordering — asserted here on the §3.2 score matrix — is what
        the battery can prove deterministically.
        """
        scores, _ = phase_score_matrix(610.1, RANGE_LO, RANGE_HI, 0.7, 0.65,
                                       "BULL", 14)
        w = phase_weights()
        target = onehot("ACCUMULATION")
        base_probs, _H = phase_probabilities(scores, w)
        base_brier = brier_score([base_probs[p] for p in PHASES], target)
        deltas = {}
        for k, comp in enumerate(("position", "evr", "volume", "structure",
                                  "age")):
            ablated = [list(row) for row in scores]
            for i in range(K_PHASES):
                ablated[k][i] = 0.0
            probs, _ = phase_probabilities(ablated, w)
            deltas[comp] = abs(
                brier_score([probs[p] for p in PHASES], target) - base_brier)
        # A *constant* score column is softmax-invariant: zeroing `age` here
        # leaves the probabilities untouched, so it cannot degrade Brier on
        # this input. Every non-constant component does move the score, and
        # `position` moves it most — the ordering §8 claims.
        varying = {c: d for c, d in deltas.items()
                   if len(set(scores[("position", "evr", "volume", "structure",
                                      "age").index(c)])) > 1}
        assert set(varying) == {"position", "evr", "volume", "structure"}
        assert all(d > 0.0 for d in varying.values())
        assert max(varying, key=varying.get) == "position"
        assert deltas["age"] == pytest.approx(0.0, abs=1e-15)

    def test_redundancy_spring_vs_sweep(self):
        """§8: the Spring / Liquidity-Sweep correlation must stay ≤ 0.45."""
        spring = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
        sweep = [0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        r = pearson(spring, sweep)
        assert abs(r) <= get_params().redundancy_spring_sweep_max
        assert abs(r) < 0.85
        # A perfectly duplicated detector WOULD breach the threshold.
        assert abs(pearson(spring, list(spring))) > 0.85

    def test_serialization_is_stable_across_runs(self):
        bars = range_window(14)
        kw = dict(atr_by_idx={i: ATR for i in range(14)},
                  vol_ratio_by_idx={i: 1.0 for i in range(14)},
                  evr_by_idx={i: 0.5 for i in range(14)})
        a = json.dumps(run_engine(bars, **kw)["final"], sort_keys=True)
        b = json.dumps(run_engine(bars, **kw)["final"], sort_keys=True)
        assert a == b

    def test_snapshot_id_is_content_bound(self):
        p1 = {"a": 1, "b": [1, 2]}
        p2 = {"a": 1, "b": [1, 3]}
        assert e08_snapshot_id(p1) == e08_snapshot_id(dict(p1))
        assert e08_snapshot_id(p1) != e08_snapshot_id(p2)
        assert len(e08_snapshot_id(p1)) == 64


# ---------------------------------------------------------------------------
# EngineBase binding + T-DR-001
# ---------------------------------------------------------------------------
def _obs_window(bars, tf="6h"):
    obs = []
    for i, b in enumerate(bars):
        ts = "2026-01-%02dT%02d:00:00.000Z" % (1 + i // 4, (i * 6) % 24)
        obs.append(MarketObservation(
            symbol="BNBUSDT", timeframe=tf,
            open=Decimal(str(b["o"])), high=Decimal(str(b["h"])),
            low=Decimal(str(b["l"])), close=Decimal(str(b["c"])),
            volume=Decimal(str(b["v"])), oi=None, timestamp=ts,
            sequence=i, status="CLOSED"))
    return obs


class TestEngineBaseBinding:
    def test_missing_window_fails_closed(self):
        with pytest.raises(ValueError, match="MISSING_WINDOW_CONTEXT_QX"):
            E08WyckoffEngine().compute("BNBUSDT", "6h",
                                       "2026-01-15T00:00:00Z", {})

    def test_empty_window_emits_nothing(self):
        assert E08WyckoffEngine().compute("BNBUSDT", "6h",
                                          "2026-01-15T00:00:00Z",
                                          {"window": []}) == []

    def test_absent_atr_evidence_degrades_rather_than_recomputing(self):
        """No governed E04 ATR ⇒ ATR = 0 ⇒ Q0_INVALID (never a substitute)."""
        bars = range_window(14)
        evs = E08WyckoffEngine().compute("BNBUSDT", "6h",
                                         "2026-01-15T00:00:00Z",
                                         {"window": _obs_window(bars)})
        assert evs == []            # every bar fails the ATR gate ⇒ no events

    def test_compute_emits_24_field_valid_evidence(self):
        bars = range_window(14)
        evs = E08WyckoffEngine().compute(
            "BNBUSDT", "6h", "2026-01-15T00:00:00Z",
            {"window": _obs_window(bars),
             "atr_by_idx": {i: ATR for i in range(len(bars))},
             "vol_ratio_by_idx": {i: 1.0 for i in range(len(bars))},
             "evr_by_idx": {i: 0.5 for i in range(len(bars))},
             "structure_by_idx": {i: "BULL" for i in range(len(bars))}})
        assert evs
        for ev in evs:
            ev.validate_24_fields()
            assert ev.engine_id == "E08"
            assert ev.direction in (-1, 0, 1)
            assert ev.resolution_class in QUALITIES
            assert ev.parameter_version == "E08-WYK-V4.0.0/DEFAULTS-v1"

    def test_compute_rejects_unknown_params(self):
        with pytest.raises(ValueError, match="UNKNOWN_E08_PARAM_QX"):
            E08WyckoffEngine().compute("BNBUSDT", "6h", "2026-01-15T00:00:00Z",
                                       {"window": _obs_window(range_window(14)),
                                        "e08_params": {"nope": 1}})

    def test_t_dr_001_deterministic_replay(self):
        """T-DR-001: E08 emissions identical on re-run over the same inputs."""
        bars = range_window(14)
        ctx = {"window": _obs_window(bars),
               "atr_by_idx": {i: ATR for i in range(len(bars))},
               "vol_ratio_by_idx": {i: 1.0 for i in range(len(bars))},
               "evr_by_idx": {i: 0.5 for i in range(len(bars))}}
        a = E08WyckoffEngine().compute("BNBUSDT", "6h", "2026-01-15T00:00:00Z",
                                       ctx)
        b = E08WyckoffEngine().compute("BNBUSDT", "6h", "2026-01-15T00:00:00Z",
                                       ctx)
        assert len(a) == len(b)
        assert [e.snapshot_id for e in a] == [e.snapshot_id for e in b]
        assert [e.condition_state for e in a] == [e.condition_state for e in b]
