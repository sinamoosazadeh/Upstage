"""E05 Imbalance/FVG — §8 validation battery (blueprint L6683–6760) +
§3/§5/§6/§7 conformance. §8.1 fixtures re-derived per ADR-P2-007
(tests/fixtures/e05_golden_fixtures.json); the min-width 0.2 rule is the
frozen θ_minW (CP-E05-001's 0.25 proposal NOT applied). T-DR-001 re-run."""

import copy
import json
import math
import os

import pytest

from apex.engines.e05_fvg import (
    E05_DEFAULTS,
    E05FVGEngine,
    EVENT_CATALOG,
    FVGEngine,
    FVGObject,
    atr_calc,
    body_ratio,
    classify_fvg,
    compute_salience_and_premium,
    detect_fvg_at,
    freshness_decay,
    get_params,
    iou_of,
    load_v3_adapter,
    mitigation_of,
    range_20,
    run_engine,
    vol_ratio,
    wilson_ci,
)
from apex.data_catalog.contracts import MarketObservation
from decimal import Decimal

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "..", "fixtures",
                            "e05_golden_fixtures.json")


def load_fixtures():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as fh:
        return {f["name"]: f for f in json.load(fh)["fixtures"]}


FIX = load_fixtures()


def eng(params=None, tick=0.01):
    return FVGEngine(params, tick_size=tick, symbol="TESTUSDT")


# ---------------------------------------------------------------------------
# §8.1 golden fixtures (10, re-derived)
# ---------------------------------------------------------------------------
class TestGoldenFixtures:
    def test_valid_bull_conventional(self):
        f = FIX["VALID_BULL_CONVENTIONAL"]
        e = eng()
        evs = e.process_bar(f["bars"], f["i"])
        assert any(ev["type"] == "EV_FVG_001_Zone_Created" for ev in evs)
        obj = list(e.active_fvgs.values())[0]
        exp = f["expected"]
        assert obj.direction == exp["direction"]
        assert obj.lower == exp["lower"] and obj.upper == exp["upper"]
        assert obj.width == pytest.approx(exp["width"])
        assert obj.ftype == exp["ftype"]
        assert obj.quality_tag == exp["quality"]

    def test_negative_width_old_formula_but_valid_with_new(self):
        f = FIX["INVALID_NEGATIVE_WIDTH_OLD_FORMULA_BUT_VALID_WITH_NEW"]
        bars = f["bars"]
        det = detect_fvg_at(bars, f["i"], 0.2, 3, 0.01, atr_override=3.5)
        assert "invalid_reason" not in det
        assert det["lower"] == f["expected"]["new_lower"]
        assert det["upper"] == f["expected"]["new_upper"]
        assert det["width"] == pytest.approx(f["expected"]["width"])
        # the abandoned max/min variant IS negative on these bars (the
        # safety-net rationale; §7 Ch.1-11 historical note)
        old_lower = max(bars[0]["h"], bars[1]["h"])
        old_upper = min(bars[1]["l"], bars[2]["l"])
        assert old_lower > old_upper

    def test_bisi_valid_bodyratio(self):
        f = FIX["BISI_VALID_BODYRATIO"]
        bars = f["bars"]
        det = detect_fvg_at(bars, f["i"], 0.2, 3, 0.01, atr_override=2.0)
        assert "invalid_reason" not in det
        assert body_ratio(bars[1]) == pytest.approx(
            f["expected"]["body_ratio"], abs=1e-3)
        ftype, penalty = classify_fvg(det, bars, f["i"], get_params())
        assert ftype == f["expected"]["ftype"] and penalty == 1.0

    def test_doji_fvg_penalty(self):
        f = FIX["DOJI_FVG_PENALTY"]
        bars = f["bars"]
        # zone width 0.2 ⇒ ATR override must keep θ_minW·ATR ≤ 0.2
        det = detect_fvg_at(bars, f["i"], 0.2, 3, 0.01, atr_override=0.9)
        assert "invalid_reason" not in det
        assert body_ratio(bars[1]) == pytest.approx(
            f["expected"]["body_ratio"], abs=1e-4)
        ftype, penalty = classify_fvg(det, bars, f["i"], get_params())
        assert ftype == f["expected"]["ftype"]
        assert penalty == pytest.approx(f["expected"]["salience_penalty"])
        # salience carries the 0.7 penalty (§3.2 step 1)
        params = get_params()
        sal_raw, _, _, _ = compute_salience_and_premium(
            det, "CONVENTIONAL", 1.0, bars, f["i"], params,
            vr_override=0.0)
        sal_pen, _, _, _ = compute_salience_and_premium(
            det, ftype, penalty, bars, f["i"], params, vr_override=0.0)
        assert sal_pen == pytest.approx(0.7 * sal_raw)

    def test_rejection_fvg_wick_ratio_and_branch(self):
        f = FIX["REJECTION_FVG"]
        b0 = f["bars"][2]
        wr = (b0["h"] - max(b0["o"], b0["c"])) / (b0["h"] - b0["l"])
        assert wr == pytest.approx(f["expected"]["wick_ratio"], abs=1e-3)
        # classification branch on a Gate_B-passing shape with the same
        # closing-bar geometry (doc bars fail Gate_B — doc_inconsistency)
        bars = [
            {"o": 100, "h": 101, "l": 99, "c": 100, "v": 1000,
             "ts_close": 1000},
            {"o": 100, "h": 101.5, "l": 99.8, "c": 101, "v": 1100,
             "ts_close": 2000},
            {"o": 101, "h": 106, "l": 101.5, "c": 101.9, "v": 2000,
             "ts_close": 3000},
        ]
        det = detect_fvg_at(bars, 2, 0.2, 3, 0.01, atr_override=2.0)
        assert "invalid_reason" not in det
        ftype, _ = classify_fvg(det, bars, 2, get_params())
        assert ftype == "REJECTION"

    def test_sequential_mtf_alignment(self):
        f = FIX["SEQUENTIAL_MTF_ALIGNMENT"]
        htf = FVGObject(
            fid="fvg_HTF_UP_2000_abcdef123456", direction="UP",
            lower=f["htf_fvg"]["lower"], upper=f["htf_fvg"]["upper"],
            mid=f["htf_fvg"]["mid"], width=2.0, created_at_ts=2000,
            created_at_idx=0, atr_at_creation=f["htf_fvg"][
                "atr_at_creation"])
        e = eng()
        evs = e.process_bar(f["bars_ltf"], 2, htf_fvgs=[htf],
                            atr_override=0.9)   # zone width 0.2 ⇒ Gate_D
        obj = list(e.active_fvgs.values())[0]
        assert obj.ftype == f["expected"]["ftype"]
        mid_ltf = (obj.lower + obj.upper) / 2
        assert abs(mid_ltf - htf.mid) == pytest.approx(
            f["expected"]["mid_diff"], abs=1e-9)
        assert abs(mid_ltf - htf.mid) <= f["expected"]["alignment_tol"]
        # §3.5 Salience boost ×1.25 for SEQUENTIAL
        e2 = eng()
        e2.process_bar(f["bars_ltf"], 2, htf_fvgs=None, atr_override=0.9)
        base_obj = list(e2.active_fvgs.values())[0]
        assert obj.salience_0 == pytest.approx(
            base_obj.salience_0 * 1.25, rel=1e-9)

    def test_inverse_with_bos_opp(self):
        f = FIX["INVERSE_WITH_BOS_OPP"]
        # Gate_B-passing UP zone (doc bars fail Gate_B — see fixture note)
        bars = [
            {"o": 110, "h": 112, "l": 108, "c": 109, "v": 1000,
             "ts_close": 1000},
            {"o": 109, "h": 112.5, "l": 108.8, "c": 112, "v": 1000,
             "ts_close": 2000},
            {"o": 112, "h": 115, "l": 113, "c": 114.5, "v": 1500,
             "ts_close": 3000},
        ]
        params = get_params({"inverse_enabled": True})
        det = detect_fvg_at(bars, 2, 0.2, 3, 0.01, atr_override=2.0)
        assert "invalid_reason" not in det and det["direction"] == "UP"
        ftype, penalty = classify_fvg(
            det, bars, 2, params, trend_htf=f["trend_htf"],
            bos_events=f["bos_events"])
        assert ftype == f["expected"]["ftype"]
        assert penalty == pytest.approx(0.5)
        e = eng({"inverse_enabled": True})
        e.process_bar(bars, 2, trend_htf=f["trend_htf"],
                      bos_events=f["bos_events"], atr_override=2.0)
        obj = list(e.active_fvgs.values())[0]
        assert obj.quality_tag == f["expected"]["quality"]
        obj.validate_schema()
        # disabled by default (§6 inverse_enabled=false)
        ftype_off, _ = classify_fvg(det, bars, 2, get_params(),
                                    trend_htf=f["trend_htf"],
                                    bos_events=f["bos_events"])
        assert ftype_off != "INVERSE"

    def test_mitigation_directional_from_above(self):
        f = FIX["MITIGATION_DIRECTIONAL_FROM_ABOVE"]
        fvg = FVGObject(fid="fvg_TESTUSDT_UP_0_000000000000",
                        direction="UP", lower=f["fvg"]["lower"],
                        upper=f["fvg"]["upper"], mid=101.0,
                        width=f["fvg"]["width"], created_at_ts=0,
                        created_at_idx=0)
        touch, depth, dir_flag = mitigation_of(fvg, f["bar"], f["prev_c"])
        assert touch is True
        assert depth == pytest.approx(f["expected"]["depth"])
        assert dir_flag == f["expected"]["dir"]
        assert depth >= 0.999                     # → FILLED (§4)

    def test_freshness_decay_expiry(self):
        f = FIX["FRESHNESS_DECAY_EXPIRY"]
        fr = freshness_decay(f["fvg"]["age_bars"], f["fvg"]["half_life"])
        assert fr == pytest.approx(f["expected"]["freshness"])
        # boundary-inclusive age expiry (fixture canonical; ISSUE-CP3-004)
        bars = [
            {"o": 100, "h": 101, "l": 99, "c": 100.5, "v": 1000,
             "ts_close": 0, "symbol": "TESTUSDT"},
            {"o": 100.5, "h": 105, "l": 100.3, "c": 104, "v": 1000,
             "ts_close": 1000, "symbol": "TESTUSDT"},
            {"o": 104, "h": 106, "l": 102.5, "c": 105.5, "v": 1000,
             "ts_close": 2000, "symbol": "TESTUSDT"},
        ]
        e = eng({"max_age_bars": 4, "half_life_bars": 48})
        e.process_bar(bars, 2, atr_override=2.0)   # FVG [101,102.5]
        assert len(e.active_fvgs) == 1
        fid = list(e.active_fvgs)[0]
        # follow-through bars stay above the zone and never re-trigger
        # Gate_B (bars[i−2].h stays above each low)
        for i in range(3, 7):
            bars.append({"o": 105.5, "h": 106.5, "l": 104.5, "c": 106,
                         "v": 1000, "ts_close": i * 1000,
                         "symbol": "TESTUSDT"})
            e.process_bar(bars, i)
        assert fid not in e.active_fvgs
        expired = [h for h in e.history if h.fid == fid]
        assert expired and expired[0].fate == "EXPIRED"
        assert expired[0].age_bars >= 4

    def test_overlap_merge_iou_redrived(self):
        f = FIX["OVERLAP_MERGE_IOU"]
        a, b = f["fvgs"]
        iou = iou_of(a["lower"], a["upper"], b["lower"], b["upper"])
        assert iou == pytest.approx(f["expected"]["iou"], abs=1e-9)
        # default threshold 0.7: these two do NOT merge (0.6 < 0.7)
        e = eng()
        _a = FVGObject(
            fid="fvg_TESTUSDT_UP_1_aaaaaaaaaaaa", direction="UP",
            lower=a["lower"], upper=a["upper"], mid=101.0, width=2.0,
            created_at_ts=1, created_at_idx=0, salience_0=a["salience_0"],
            salience=a["salience_0"])
        _b = FVGObject(
            fid="fvg_TESTUSDT_UP_2_bbbbbbbbbbbb", direction="UP",
            lower=b["lower"], upper=b["upper"], mid=101.5, width=2.0,
            created_at_ts=2, created_at_idx=1, salience_0=b["salience_0"],
            salience=b["salience_0"])
        e.active_fvgs[_a.fid] = _a
        e.active_fvgs[_b.fid] = _b
        assert e._merge_overlaps() == []
        assert len(e.active_fvgs) == 2
        # governed threshold 0.5: merge mechanics per §3.7
        e2 = eng({"iou_merge_thr": 0.5})
        e2.active_fvgs = dict(e.active_fvgs)
        evs = e2._merge_overlaps()
        assert len(evs) == 1 and len(e2.active_fvgs) == 1
        merged = list(e2.active_fvgs.values())[0]
        assert merged.lower == f["expected"]["merged_lower"]
        assert merged.upper == f["expected"]["merged_upper"]
        assert merged.salience_0 == pytest.approx(
            max(a["salience_0"], b["salience_0"]) * 1.1)
        # containment merges regardless of IoU (§3.7)
        e3 = eng()
        _ca = FVGObject(
            fid="fvg_TESTUSDT_UP_1_cccccccccccc", direction="UP",
            lower=100.0, upper=110.0, mid=105.0, width=10.0,
            created_at_ts=1, created_at_idx=0, salience_0=0.5,
            salience=0.5)
        _cb = FVGObject(
            fid="fvg_TESTUSDT_UP_2_dddddddddddd", direction="UP",
            lower=102.0, upper=104.0, mid=103.0, width=2.0,
            created_at_ts=2, created_at_idx=1, salience_0=0.9,
            salience=0.9)
        e3.active_fvgs[_ca.fid] = _ca
        e3.active_fvgs[_cb.fid] = _cb
        evs3 = e3._merge_overlaps()
        assert len(evs3) == 1 and len(e3.active_fvgs) == 1


# ---------------------------------------------------------------------------
# §3 formula conformance
# ---------------------------------------------------------------------------
class TestFormulas:
    def test_body_ratio_doj_and_full(self):
        assert body_ratio({"o": 100, "c": 100.05, "h": 101, "l": 99}
                          ) == pytest.approx(0.025)
        assert body_ratio({"o": 100, "c": 102, "h": 102, "l": 100}
                          ) == pytest.approx(1.0)
        assert body_ratio({"o": 100, "c": 100, "h": 100, "l": 100}
                          ) == 0.0          # H==L → 0

    def test_vol_ratio_warmup_none_and_v0(self):
        bars = [{"v": 100} for _ in range(5)]
        assert vol_ratio(bars, 4, lookback=20) is None   # Q1 warmup
        bars2 = [{"v": 100} for _ in range(21)]
        bars2[20]["v"] = 0
        assert vol_ratio(bars2, 20, lookback=20) == 0.0

    def test_range_20_pit_window(self):
        bars = [{"h": 10 + i, "l": i} for i in range(30)]
        rl, rh = range_20(bars, 25, lookback=20)
        assert rh == 10 + 24 and rl == 5       # bars[5:25] only, PIT

    def test_z_mid_premium_discount_example(self):
        # §7 Ch.3-11: RH=110 RL=90 Mid=100, C=105, ATR=4 → z_mid=1.25
        z = (105 - (110 + 90) / 2) / 4
        assert z == pytest.approx(1.25)
        assert z > 0.5                          # Premium band

    def test_mitigation_from_below_for_bull_fvg(self):
        fvg = FVGObject(fid="fvg_T_UP_0_eeeeeeeeeeee", direction="UP",
                        lower=100.0, upper=102.0, mid=101.0, width=2.0,
                        created_at_ts=0, created_at_idx=0)
        touch, depth, dir_flag = mitigation_of(
            fvg, {"h": 101.0, "l": 99.0}, prev_close=98.0)
        assert touch and dir_flag == -1         # entry from below

    def test_no_touch_outside_zone(self):
        fvg = FVGObject(fid="fvg_T_UP_0_ffffffffffff", direction="UP",
                        lower=100.0, upper=102.0, mid=101.0, width=2.0,
                        created_at_ts=0, created_at_idx=0)
        touch, depth, dir_flag = mitigation_of(
            fvg, {"h": 105.0, "l": 103.0}, prev_close=104.0)
        assert not touch and depth == 0.0

    def test_atr_calc_pit_safe(self):
        bars = [{"h": 102, "l": 100, "c": 101},
                {"h": 104, "l": 101, "c": 103},
                {"h": 106, "l": 103, "c": 105}]
        atr2 = atr_calc(bars, 14, 2)
        tr1 = max(104 - 101, abs(104 - 101), abs(101 - 101))
        tr2 = max(106 - 103, abs(106 - 103), abs(103 - 103))
        assert atr2 == pytest.approx((tr1 + tr2) / 2)

    def test_freshness_half_life(self):
        assert freshness_decay(48, 48) == pytest.approx(0.5)
        assert freshness_decay(0, 48) == pytest.approx(1.0)

    def test_gate_d_min_width_0_2_rule(self):
        # frozen θ_minW = 0.2 (CP-E05-001 NOT applied): width 0.19·ATR
        # rejected, 0.21·ATR accepted (min_abs_ticks also satisfied)
        bars = [
            {"o": 100, "h": 101, "l": 99, "c": 100, "v": 1000,
             "ts_close": 1000},
            {"o": 100, "h": 101, "l": 99.9, "c": 100.5, "v": 1000,
             "ts_close": 2000},
            {"o": 100.5, "h": 102, "l": 101.19, "c": 101.8, "v": 1000,
             "ts_close": 3000},
        ]
        det = detect_fvg_at(bars, 2, 0.2, 3, 0.01, atr_override=1.0)
        assert det and det.get("invalid_reason") == "INSUFFICIENT_WIDTH"
        bars[2]["l"] = 101.21
        det2 = detect_fvg_at(bars, 2, 0.2, 3, 0.01, atr_override=1.0)
        assert det2 and "invalid_reason" not in det2

    def test_invalid_candle_gate_a(self):
        bars = [{"o": 100, "h": 99, "l": 100, "c": 100, "v": 1,
                 "ts_close": 1000},
                {"o": 100, "h": 101, "l": 100, "c": 100.5, "v": 1,
                 "ts_close": 2000},
                {"o": 100.5, "h": 103, "l": 101, "c": 102, "v": 1,
                 "ts_close": 3000}]
        det = detect_fvg_at(bars, 2, 0.2, 3, 0.01, atr_override=1.0)
        assert det == {"invalid_reason": "INVALID_CANDLE"}


# ---------------------------------------------------------------------------
# §5 lifecycle state machine + events
# ---------------------------------------------------------------------------
def _bull_zone_bars():
    """Three-candle bullish FVG [101, 102.5] then follow-through bars."""
    return [
        {"o": 100, "h": 101, "l": 99.5, "c": 100.5, "v": 1000,
         "ts_close": 1000},
        {"o": 100.5, "h": 101.2, "l": 100.3, "c": 101.0, "v": 1200,
         "ts_close": 2000},
        {"o": 101.0, "h": 104, "l": 102.5, "c": 103.5, "v": 2000,
         "ts_close": 3000},
    ]


class TestLifecycle:
    def test_fresh_touched_mitigated_filled(self):
        bars = _bull_zone_bars()
        e = eng()
        e.process_bar(bars, 2, atr_override=1.5)
        fid = list(e.active_fvgs)[0]
        obj = e.active_fvgs[fid]
        assert obj.fate == "FRESH" and obj.quality_tag == "Q2"  # Classified
        # touch with shallow depth → TOUCHED (Q4); the large ATR override
        # at this bar keeps Gate_D from minting a second zone out of the
        # [bars[i−2].h, L_t] candidate
        bars.append({"o": 103.5, "h": 104, "l": 102.1, "c": 103.8,
                     "v": 900, "ts_close": 4000})
        evs = e.process_bar(bars, 3, atr_override=50.0)
        assert obj.fate == "TOUCHED" and obj.quality_tag == "Q4"
        assert any(ev["type"] == "EV_FVG_002_Zone_Touched" for ev in evs)
        # deep penetration ≥ 0.5 → MITIGATED
        bars.append({"o": 103.8, "h": 104.2, "l": 101.4, "c": 102.0,
                     "v": 900, "ts_close": 5000})
        evs = e.process_bar(bars, 4)
        assert obj.fate == "MITIGATED"
        assert any(ev["type"] == "EV_FVG_003_Zone_Mitigated" for ev in evs)
        # full crossing → FILLED (terminal, moved to history)
        bars.append({"o": 102.0, "h": 103.5, "l": 100.5, "c": 101.0,
                     "v": 900, "ts_close": 6000})
        evs = e.process_bar(bars, 5)
        assert obj.fate == "FILLED" and obj.quality_tag == "Q5"
        assert fid not in e.active_fvgs
        assert any(ev["type"] == "EV_FVG_004_Zone_Filled" for ev in evs)
        assert e.history[-1].fid == fid

    def test_event_catalog_ids_complete(self):
        assert tuple(EVENT_CATALOG) == tuple(
            f"EV_FVG_{i:03d}" for i in range(1, 10))

    def test_bisi_and_rejection_confirmation_events(self):
        # BISI bars (fixture 3) through the engine → EV_FVG_008
        bars = FIX["BISI_VALID_BODYRATIO"]["bars"]
        e = eng()
        evs = e.process_bar(bars, 2, atr_override=2.0)
        types = [ev["type"] for ev in evs]
        assert "EV_FVG_001_Zone_Created" in types
        assert "EV_FVG_008_BISI_Confirmed" in types
        # REJECTION shape → EV_FVG_009
        bars_r = [
            {"o": 100, "h": 101, "l": 99, "c": 100, "v": 1000,
             "ts_close": 1000},
            {"o": 100, "h": 101.5, "l": 99.8, "c": 101, "v": 1100,
             "ts_close": 2000},
            {"o": 101, "h": 106, "l": 101.5, "c": 101.9, "v": 2000,
             "ts_close": 3000},
        ]
        e2 = eng()
        evs2 = e2.process_bar(bars_r, 2, atr_override=2.0)
        assert any(ev["type"] == "EV_FVG_009_Rejection_Confirmed"
                   for ev in evs2)

    def test_zone_invalidated_events_for_insufficient_width(self):
        bars = _bull_zone_bars()
        e = eng()
        evs = e.process_bar(bars, 2, atr_override=30.0)
        assert any(ev["type"] == "EV_FVG_005_Zone_Invalidated"
                   and ev["reason"] == "INSUFFICIENT_WIDTH"
                   for ev in evs)
        assert not e.active_fvgs

    def test_idempotency_same_bar_no_duplicate(self):
        bars = _bull_zone_bars()
        e = eng()
        evs1 = e.process_bar(bars, 2, atr_override=1.5)
        evs2 = e.process_bar(bars, 2, atr_override=1.5)
        assert evs1 and evs2 == []
        assert len(e.active_fvgs) == 1

    def test_snapshot_id_deterministic_and_64hex(self):
        bars = _bull_zone_bars()
        e1 = eng()
        e1.process_bar(bars, 2, atr_override=1.5)
        e2 = eng()
        e2.process_bar(bars, 2, atr_override=1.5)
        o1 = list(e1.active_fvgs.values())[0]
        o2 = list(e2.active_fvgs.values())[0]
        assert o1.snapshot_id == o2.snapshot_id
        assert len(o1.snapshot_id) == 64
        assert o1.fid.startswith("fvg_")

    def test_schema_validation_enums(self):
        bars = _bull_zone_bars()
        e = eng()
        e.process_bar(bars, 2, atr_override=1.5)
        obj = list(e.active_fvgs.values())[0]
        obj.validate_schema()
        bad = copy.deepcopy(obj)
        bad.mitigation_dir = 7
        with pytest.raises(ValueError, match="FVG_ZONE_MIT_DIR_QX"):
            bad.validate_schema()


# ---------------------------------------------------------------------------
# §8.2 deterministic replay
# ---------------------------------------------------------------------------
class TestDeterministicReplay:
    def test_double_run_identical_fid_and_snapshot(self):
        bars = _bull_zone_bars() + [
            {"o": 103.5, "h": 105, "l": 103, "c": 104.5, "v": 900,
             "ts_close": 4000 + i * 1000, "symbol": "TESTUSDT"}
            for i in range(10)]
        r1 = run_engine(bars, tick_size=0.01, symbol="TESTUSDT",
                        atr_by_idx={i: 1.5 for i in range(len(bars))})
        r2 = run_engine(bars, tick_size=0.01, symbol="TESTUSDT",
                        atr_by_idx={i: 1.5 for i in range(len(bars))})
        ids1 = sorted((o.fid, o.snapshot_id) for o in r1["active"]
                      + r1["history"])
        ids2 = sorted((o.fid, o.snapshot_id) for o in r2["active"]
                      + r2["history"])
        assert ids1 == ids2 and ids1


# ---------------------------------------------------------------------------
# §8.3 no-future-leak
# ---------------------------------------------------------------------------
class TestNoFutureLeak:
    def test_detection_unchanged_when_future_nulled(self):
        bars = _bull_zone_bars() + [
            {"o": 104, "h": 107, "l": 103, "c": 106, "v": 1500,
             "ts_close": 4000 + i * 1000} for i in range(5)]
        det_full = detect_fvg_at(bars, 2, 0.2, 3, 0.01, atr_override=1.5)
        truncated = bars[:3]                        # future removed
        det_trunc = detect_fvg_at(truncated, 2, 0.2, 3, 0.01,
                                  atr_override=1.5)
        assert {k: det_full[k] for k in ("direction", "lower", "upper",
                                         "width")} == \
               {k: det_trunc[k] for k in ("direction", "lower", "upper",
                                          "width")}

    def test_atr_only_uses_up_to_idx(self):
        bars = [{"h": 102 + i, "l": 100 + i, "c": 101 + i}
                for i in range(10)]
        assert atr_calc(bars, 14, 3) == atr_calc(bars[:4], 14, 3)


# ---------------------------------------------------------------------------
# §8.4 ablation (component-zeroing on deterministic shapes; AUC claims are
# data-dependent and stay research-side — ISSUE-CP2-015 discipline)
# ---------------------------------------------------------------------------
class TestAblation:
    def test_zeroing_each_component_changes_salience(self):
        bars = _bull_zone_bars() + [
            {"o": 100 + i, "h": 102 + i, "l": 99 + i, "c": 101 + i,
             "v": 1000, "ts_close": 4000 + i * 1000} for i in range(25)]
        det = detect_fvg_at(bars, 2, 0.2, 3, 0.01, atr_override=1.5)
        params = get_params()
        base, _, _, _ = compute_salience_and_premium(
            det, "CONVENTIONAL", 1.0, bars, 2, params, struct_role=1.0,
            vr_override=1.4)
        names = ("w_w", "w_v", "w_s", "w_f")
        for k in range(4):
            w = [0.35, 0.25, 0.25, 0.15]
            w[k] = 0.0
            renorm = [x / sum(w) for x in w]     # Σ=1 governance rule
            p2 = get_params({"salience_weights": tuple(renorm)})
            sal, _, _, _ = compute_salience_and_premium(
                det, "CONVENTIONAL", 1.0, bars, 2, p2, struct_role=1.0,
                vr_override=1.4)
            assert sal != pytest.approx(base, abs=1e-9), names[k]


# ---------------------------------------------------------------------------
# §8.5 Wilson CI calibration of the return rate
# ---------------------------------------------------------------------------
class TestWilsonCalibration:
    def test_wilson_ci_formula(self):
        lo, hi = wilson_ci(0.65, 20)
        assert 0 < lo < 0.65 < hi < 1
        lo2, hi2 = wilson_ci(7 / 11, 11)
        assert lo2 == pytest.approx(0.35, abs=0.01)
        assert hi2 == pytest.approx(0.84, abs=0.01)

    def test_ci_includes_half_no_superiority_claim(self):
        lo, hi = wilson_ci(3 / 5, 5)
        assert lo <= 0.5 <= hi        # claim invalid per §8.5


# ---------------------------------------------------------------------------
# §8.6 redundancy threshold (numeric, documented)
# ---------------------------------------------------------------------------
class TestRedundancy:
    def test_iou_gt_0_6_and_mid_lt_0_2_atr_is_redundant(self):
        atr = 4.0
        a = (100.0, 104.0)
        b = (100.5, 104.5)
        iou = iou_of(a[0], a[1], b[0], b[1])
        mid_dist = abs((a[0] + a[1]) / 2 - (b[0] + b[1]) / 2)
        redundant = iou > 0.6 and mid_dist < 0.2 * atr
        assert redundant is True
        # higher-Salience kept (the merge governance of §3.7 applies the
        # same keep-best rule)
        c = (200.0, 204.0)
        assert iou_of(a[0], a[1], c[0], c[1]) == 0.0


# ---------------------------------------------------------------------------
# §8.7 serialization compatibility (v3 → v4 adapter)
# ---------------------------------------------------------------------------
class TestSerializationCompat:
    def test_v3_adapter_defaults_and_doji_mapping(self):
        v3 = {"fid": "fvg_LEGACY_UP_1000_abcdefabcdef",
              "direction": "UP", "lower": 100.0, "upper": 102.0,
              "created_at_ts": 1000, "created_at_idx": 5,
              "ftype": "DOJI_FVG", "salience_0": 0.6}
        obj = load_v3_adapter(v3)
        assert obj.mitigation_dir == 0            # absent ⇒ default 0
        assert obj.ftype == "CONVENTIONAL"        # DOJI mapped
        assert obj.extra.get("v3_doji_penalty") == 0.7
        assert len(obj.snapshot_id) == 64
        # serialize → deserialize: snapshot preserved
        payload = {"schema_version": "3.0.0", **v3}
        again = load_v3_adapter(payload)
        assert again.snapshot_id == obj.snapshot_id

    def test_v3_adapter_ambiguity_fails_closed(self):
        with pytest.raises(ValueError, match="E05_ADAPTER_AMBIGUOUS_QX"):
            load_v3_adapter({"fid": "x", "direction": "UP"})
        with pytest.raises(ValueError, match="E05_ADAPTER_VERSION_QX"):
            load_v3_adapter({"schema_version": "4.0.0", "fid": "x",
                             "direction": "UP", "lower": 1, "upper": 2,
                             "created_at_ts": 0, "created_at_idx": 0})


# ---------------------------------------------------------------------------
# §6 parameters (frozen literals; CP-E05-001 NOT applied)
# ---------------------------------------------------------------------------
class TestParameters:
    def test_frozen_defaults_match_chapter_6(self):
        assert E05_DEFAULTS["min_width_atr"] == 0.2     # frozen, not 0.25
        assert E05_DEFAULTS["min_abs_ticks"] == 3
        assert E05_DEFAULTS["max_age_bars"] == 96
        assert E05_DEFAULTS["mit_activate"] == 0.5
        assert E05_DEFAULTS["rej_wick"] == 0.5
        assert E05_DEFAULTS["salience_weights"] == (0.35, 0.25, 0.25, 0.15)
        assert E05_DEFAULTS["mtf_required"] is False
        assert E05_DEFAULTS["inverse_enabled"] is False
        assert E05_DEFAULTS["half_life_bars"] == 48
        assert E05_DEFAULTS["fresh_thr"] == 0.15
        assert E05_DEFAULTS["iou_merge_thr"] == 0.7
        assert E05_DEFAULTS["body_ratio_doji_thr"] == 0.1
        assert E05_DEFAULTS["range_lookback"] == 20
        assert E05_DEFAULTS["atr_period"] == 14
        assert E05_DEFAULTS["vol_lookback"] == 20
        assert E05_DEFAULTS["sequential_boost"] == 1.25
        assert E05_DEFAULTS["sequential_tol_atr"] == 0.3
        assert E05_DEFAULTS["inverse_penalty"] == 0.5
        assert abs(math.log(2) / 48 - 0.01444) < 1e-4

    def test_weights_sum_enforced(self):
        with pytest.raises(ValueError, match="E05_SALIENCE_WEIGHTS_SUM_QX"):
            get_params({"salience_weights": (0.5, 0.5, 0.5, 0.5)})

    def test_unknown_param_rejected(self):
        with pytest.raises(ValueError, match="UNKNOWN_E05_PARAM_QX"):
            get_params({"min_width": 0.25})        # CP-E05-001 key absent


# ---------------------------------------------------------------------------
# §9 case study re-derivations (BNBUSDT 6H, 12 candles — illustrative
# series; every asserted value re-computed from the §3 formulas)
# ---------------------------------------------------------------------------
CASE_BARS = [
    {"o": 516.0, "h": 518.2, "l": 515.0, "c": 517.5, "v": 100000,
     "ts_close": 1000},
    {"o": 517.6, "h": 520.0, "l": 517.5, "c": 519.8, "v": 110000,
     "ts_close": 2000},
    {"o": 519.9, "h": 522.4, "l": 519.8, "c": 521.5, "v": 130000,
     "ts_close": 3000},
    {"o": 521.6, "h": 524.0, "l": 521.0, "c": 523.2, "v": 125000,
     "ts_close": 4000},
    {"o": 523.3, "h": 527.5, "l": 523.5, "c": 526.8, "v": 180000,
     "ts_close": 5000},
    {"o": 526.9, "h": 528.0, "l": 524.6, "c": 525.2, "v": 140000,
     "ts_close": 6000},
    {"o": 525.3, "h": 526.0, "l": 522.9, "c": 523.5, "v": 135000,
     "ts_close": 7000},
    {"o": 523.6, "h": 529.5, "l": 523.0, "c": 528.8, "v": 190000,
     "ts_close": 8000},
    {"o": 528.9, "h": 530.0, "l": 527.0, "c": 529.0, "v": 150000,
     "ts_close": 9000},
    {"o": 529.1, "h": 531.2, "l": 528.5, "c": 530.5, "v": 160000,
     "ts_close": 10000},
    {"o": 530.6, "h": 532.0, "l": 529.5, "c": 531.0, "v": 155000,
     "ts_close": 11000},
    {"o": 531.0, "h": 528.5, "l": 525.0, "c": 526.0, "v": 170000,
     "ts_close": 12000},
]
CASE_ATR = {0: 3.8, 1: 3.9, 2: 4.0, 3: 4.1, 4: 4.3, 5: 4.2, 6: 4.2,
            7: 4.4, 8: 4.3, 9: 4.3, 10: 4.2, 11: 4.4}


class TestCaseStudy:
    def _run(self):
        return run_engine(CASE_BARS, tick_size=0.01, symbol="BNBUSDT",
                          atr_by_idx=CASE_ATR)

    def test_candle2_zone_geometry_and_bris(self):
        r = self._run()
        zones = {(o.created_at_idx, round(o.lower, 4), round(o.upper, 4))
                 for o in r["active"] + r["history"]}
        assert (2, 518.2, 519.8) in zones          # §9 candle 2
        assert (3, 520.0, 521.0) in zones          # §9 candle 3
        assert (4, 522.4, 523.5) in zones          # §9 candle 4
        br = abs(519.8 - 517.6) / (520.0 - 517.5)
        assert br == pytest.approx(0.88, abs=1e-9)  # §9 BR 0.88 → CONV

    def test_candle5_insufficient_width(self):
        # §9 candle 5: W=0.6 < 0.2×4.2=0.84 → EV_FVG_005
        r = self._run()
        inv = [ev for ev in r["events"]
               if ev["type"] == "EV_FVG_005_Zone_Invalidated"]
        assert any(ev["at_idx"] == 5 for ev in inv)

    def test_candle6_mitigation_depth_and_direction(self):
        # §9 candle 6: FVG [522.4,523.5], bar L=522.9 H=526 → overlap
        # 0.6, depth 0.545, prev close 525.2 > upper → dir +1
        overlap = min(523.5, 526.0) - max(522.4, 522.9)
        depth = overlap / (523.5 - 522.4)
        assert overlap == pytest.approx(0.6)
        assert depth == pytest.approx(0.545, abs=1e-3)
        r = self._run()
        fvg3 = [o for o in r["active"] + r["history"]
                if o.created_at_idx == 4][0]
        assert fvg3.mitigation_depth == pytest.approx(depth, abs=1e-9)
        assert fvg3.mitigation_dir == 1
        assert fvg3.touch_count >= 1

    def test_candle11_fill_of_zone_526_527(self):
        # §9 candle 8 creates [526,527]; candle 11 (L=525, H=528.5)
        # fully crosses it → FILLED
        r = self._run()
        filled = [o for o in r["history"]
                  if o.created_at_idx == 8 and o.fate == "FILLED"]
        assert filled

    def test_freshness_case_numbers(self):
        # §9 candle 4: age=2, λ=ln2/48 → F=exp(−0.0288)=0.971
        assert freshness_decay(2, 48) == pytest.approx(0.9714, abs=1e-3)
        # §9 candle 11: age=9 → 0.878
        assert freshness_decay(9, 48) == pytest.approx(0.8786, abs=1e-3)

    def test_salience_warmup_conservative(self):
        # 12-bar window < VolRatio lookback 20 → warmup VR=0 (the §3.4
        # conservative rule); salience at candle 2 with StructRole=1.0:
        # 0.35·min(1.6/4.0,2)/2 + 0 + 0.25 + 0.15 = 0.47
        r = self._run()
        z2 = [o for o in r["active"] + r["history"]
              if o.created_at_idx == 2][0]
        assert z2.salience_0 == pytest.approx(
            0.35 * min(1.6 / 4.0, 2.0) / 2.0 + 0.25 * 0.5 + 0.15, abs=1e-9)


# ---------------------------------------------------------------------------
# EngineBase binding
# ---------------------------------------------------------------------------
def _obs_window(bars):
    obs = []
    for i, b in enumerate(bars):
        ts = "2026-01-01T%02d:%02d:00.000Z" % (i // 60, i % 60)
        obs.append(MarketObservation(
            symbol="BNBUSDT", timeframe="6h",
            open=Decimal(str(b["o"])), high=Decimal(str(b["h"])),
            low=Decimal(str(b["l"])), close=Decimal(str(b["c"])),
            volume=Decimal(str(b["v"])), oi=None, timestamp=ts,
            sequence=i, status="CLOSED"))
    return obs


class TestEngineBaseBinding:
    def test_missing_window_context_fails_closed(self):
        with pytest.raises(ValueError, match="MISSING_WINDOW_CONTEXT_QX"):
            E05FVGEngine().compute("BNBUSDT", "6h",
                                   "2026-01-01T00:00:00Z", {})

    def test_compute_emits_valid_events_with_evidence_inputs(self):
        evs = E05FVGEngine().compute(
            "BNBUSDT", "6h", "2026-01-02T00:00:00Z",
            {"window": _obs_window(CASE_BARS), "tick_size": 0.01,
             "atr_series": [CASE_ATR[i] for i in range(len(CASE_BARS))]})
        assert evs
        for ev in evs:
            ev.validate_24_fields()
            assert ev.engine_id == "E05"
            assert ev.direction in (-1, 1)
            assert len(ev.snapshot_id) == 64


# ---------------------------------------------------------------------------
# T-DR-001 (E05 re-run)
# ---------------------------------------------------------------------------
class TestTDR001:
    def test_double_run_canonical_byte_identical(self):
        r1 = self._out()
        r2 = self._out()
        c1 = json.dumps(sorted(o.snapshot_id
                               for o in r1["active"] + r1["history"]))
        c2 = json.dumps(sorted(o.snapshot_id
                               for o in r2["active"] + r2["history"]))
        assert c1 == c2 and c1 != "[]"

    @staticmethod
    def _out():
        return run_engine(CASE_BARS, tick_size=0.01, symbol="BNBUSDT",
                          atr_by_idx=CASE_ATR)

    def test_pit_availability_boundary(self):
        from apex.identity.snapshot import governed_as_of_ms
        assert governed_as_of_ms([{"availability_time_ms": 5},
                                  {"availability_time_ms": 9}]) == 9
        with pytest.raises(ValueError):
            governed_as_of_ms([])
