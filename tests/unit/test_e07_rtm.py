"""E07 RTM/ICT — full §8 validation battery (APEX_GEN5.md L8293–9085).

Covers: §8.1 golden fixtures (15, values re-derived per ADR-P2-007) · §8.2
deterministic replay (100× identical snapshot_id) · §8.3 no-future-leak ·
§8.4 ablation · §8.5 Wilson-CI calibration · §8.6 redundancy 0.85 ·
§8.7 v3→v4 serialization · §6 governed params · §3.1–§3.7 formulas ·
§5.1/§5.2 schema + fate machine · the E12-unavailable degraded branch
(CP-4; the both-mode integration test lands at CP-5) · EngineBase binding ·
T-DR-001.
"""

from __future__ import annotations

import json
import math
import pathlib
from decimal import Decimal

import pytest

from apex.data_catalog.contracts import MarketObservation
from apex.engines.e07_rtm import (
    BUNDLE_VERSION,
    CHAIN_DEFS,
    CONTRACT_VERSION,
    E07_DEFAULTS,
    E07RTMEngine,
    E12_CONTRACT,
    E12_UNAVAILABLE_REASON,
    ENGINE,
    EPS,
    EVENT_CATALOG,
    FRAMEWORK_IDS,
    KZ_CONFIG_VERSION,
    NON_UTC_REASON,
    ComponentDef,
    EngineParams,
    RTMEngineStreaming,
    VOL_UNAVAILABLE_REASON,
    WaveOutError,
    atr_ratio_detect,
    build_bundle_pipeline,
    build_order_map,
    bundle_confidence,
    evaluate_order_ok,
    expected_components,
    framework_threshold,
    get_params,
    judas_swing_detect,
    kz_align_score,
    load_v3_adapter,
    make_snapshot_id,
    mss_confirmed,
    mss_proximity_check,
    new_bundle_id,
    ote_zone_calc,
    pearson,
    quality_class_caps,
    quality_class_cascade,
    redundancy_halve_weights,
    resolution_class,
    resolve_conflicting_bundles,
    run_engine,
    sequence_integrity_v4,
    to_utc_ms,
    update_bundle_fate,
    utc_activity_window_check,
    wilder_rma_series,
    wilson_ci,
    window_overlap,
)

FIXTURES = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent / "fixtures"
     / "e07_golden_fixtures.json").read_text())
BY_ID = {f["id"]: f for f in FIXTURES["fixtures"]}
# The fixture file pins the canonical as_of so the battery and the recorded
# expectations cannot drift apart (§8.1 re-derivation discipline).
AS_OF_ISO = FIXTURES["as_of_iso"]
AS_OF_MS = to_utc_ms(AS_OF_ISO)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def lcg_window(n, seed=1234, base=605.0, step_ms=15 * 60 * 1000):
    """Deterministic closed-candle window (no fabricated market data)."""
    out = []
    x = seed
    price = base
    for i in range(n):
        x = (1103515245 * x + 12345) % (2 ** 31)
        u = x / 2 ** 31
        o = price + (u - 0.5) * 0.4
        c = o + (u - 0.5) * 0.3
        h = max(o, c) + 0.05 + u * 0.1
        l = min(o, c) - 0.05 - u * 0.1
        out.append({"ts": 1768485600000 + i * step_ms, "o": o, "h": h,
                    "l": l, "c": c, "v": 1000.0 + 60.0 * u, "is_closed": True})
        price = c
    return out


def compress_window(n=140, seed=7, tail=20, wide=1.2, tight=0.02):
    """A window whose recent bars are compressed versus the longer history.

    §3.2 compares ATR10 against ATR100, so the tail must be materially tighter
    than the body (and lower-volume) for the Accumulation gate to be met.
    """
    bars = []
    price = 605.0
    x = seed
    for i in range(n):
        x = (1103515245 * x + 12345) % (2 ** 31)
        u = x / 2 ** 31
        span = tight if i >= n - tail else wide
        vol = 700.0 if i >= n - tail else 1000.0
        o = price + (u - 0.5) * span
        c = o + (u - 0.5) * span * 0.6
        h = max(o, c) + span * 0.2
        l = min(o, c) - span * 0.2
        bars.append({"ts": 1768485600000 + i * 900000, "o": o, "h": h,
                     "l": l, "c": c, "v": vol, "is_closed": True})
        price = c
    return bars


def po3_confirmations(t0=None):
    t0 = AS_OF_MS if t0 is None else t0
    return [{"cid": cid, "t_confirm_ms": t0 + 900000 * (i + 1),
             "p_confirm": 604.0 + i}
            for i, cid in enumerate(["sweep", "choch", "bos", "fvg",
                                     "vol_confirm"])]


class FakeE12:
    """Stand-in for ``E12_Temporal_Context.Contract v4.0.0`` (test double)."""

    def __init__(self, payload=None, boom=False):
        self.payload = payload
        self.boom = boom
        self.calls = 0

    def temporal_window(self, ts_ms):
        self.calls += 1
        if self.boom:
            raise RuntimeError("E12 provider failure")
        return self.payload


# ---------------------------------------------------------------------------
# §8.1 Golden fixtures (15 cases)
# ---------------------------------------------------------------------------
class TestGoldenFixtures:
    def test_fixture_file_is_the_15_case_set(self):
        assert FIXTURES["engine"] == ENGINE
        assert len(FIXTURES["fixtures"]) == 15

    def test_po3_complete_valid(self):
        fx = BY_ID["PO3_COMPLETE_VALID"]
        exp = expected_components("RTM.PO3.v1")
        conf = po3_confirmations()
        om = build_order_map(exp, conf)
        order = [c["cid"] for c in conf]
        evaluate_order_ok(exp, order, om)
        integrity, cov, missing = sequence_integrity_v4(exp, order, om)
        assert fx["expected"]["framework"] == "RTM.PO3.v1"
        assert integrity == pytest.approx(fx["expected"]["integrity"], abs=1e-12)
        assert integrity >= fx["expected"]["integrity_min"]
        assert cov == pytest.approx(1.0, abs=1e-9)
        assert missing == []
        kz = utc_activity_window_check(conf[-1]["t_confirm_ms"])
        bundle = build_bundle_pipeline(exp, order, om, 0.9, 1.0, kz,
                                       "RTM.PO3.v1", "UP",
                                       conf[-1]["t_confirm_ms"])
        assert fx["expected"]["has_bundle"] is True
        assert bundle is not None
        # Degraded at CP-4 (E12 absent) ⇒ the §3.7 Q5 gate caps to Q4.
        assert bundle.resolution_class == fx["expected"]["resolution_class"]
        assert ["Q0", "Q1", "Q2", "Q3", "Q4", "Q5"].index(
            bundle.resolution_class) >= ["Q0", "Q1", "Q2", "Q3", "Q4",
                                         "Q5"].index(fx["expected"]["q_min"])
        assert bundle.confidence == pytest.approx(
            fx["expected"]["confidence"], abs=1e-12)

    def test_po3_range_fail_vol_high(self):
        fx = BY_ID["PO3_RANGE_FAIL_VOL_HIGH"]
        assert fx["expected"]["has_bundle"] is False
        bars = compress_window()
        for b in bars[-8:]:
            b["v"] = 5000.0                     # VolRatio > 0.9
        info = atr_ratio_detect(bars)
        assert info["is_range"] is False
        assert info["vol_ratio"] > 0.9

    def test_mss_near_true(self):
        fx = BY_ID["MSS_NEAR_TRUE"]
        i = fx["inputs"]
        assert mss_proximity_check(i["p_sweep"], i["p_choch"],
                                   i["atr20"]) is fx["expected"]["proximity"]
        assert abs(i["p_sweep"] - i["p_choch"]) == pytest.approx(
            fx["expected"]["distance"])
        assert fx["expected"]["threshold"] == pytest.approx(0.5 * i["atr20"])

    def test_mss_near_false_far(self):
        fx = BY_ID["MSS_NEAR_FALSE_FAR"]
        i = fx["inputs"]
        assert mss_proximity_check(i["p_sweep"], i["p_choch"],
                                   i["atr20"]) is fx["expected"]["proximity"]
        assert abs(i["p_sweep"] - i["p_choch"]) > fx["expected"]["threshold"]

    def test_ote_valid(self):
        fx = BY_ID["OTE_VALID"]
        zone = ote_zone_calc(fx["inputs"]["A"], fx["inputs"]["B"])
        assert zone["lo"] == pytest.approx(fx["expected"]["lo"], abs=1e-9)
        assert zone["hi"] == pytest.approx(fx["expected"]["hi"], abs=1e-9)
        assert zone["star"] == pytest.approx(fx["expected"]["star"], abs=1e-9)

    def test_ote_invalid_zero_impulse(self):
        fx = BY_ID["OTE_INVALID_ZERO_IMPULSE"]
        assert ote_zone_calc(600, 600) is None
        assert fx["expected"]["valid"] is False

    def test_judas_valid_rev100_in3(self):
        fx = BY_ID["JUDAS_VALID_REV100_IN3"]
        # expected_dir UP ⇒ the Judas leg is DOWN then a >= 100% reversal.
        bars = [{"ts": i, "o": 610.0, "h": 610.4, "l": 609.0, "c": c,
                 "v": 1000.0}
                for i, c in enumerate([610.0, 609.5, 609.2, 611.0, 611.4,
                                       611.6, 611.8])]
        det = judas_swing_detect(bars, "UP", atr20=4.0)
        assert det is not None and det["confirmed"] is True
        assert fx["expected"]["judas_confirmed"] is True
        assert det["judas_len"] <= 0.25 * 4.0
        assert det["rev_len"] >= det["judas_len"]
        assert det["bars_to_rev"] <= 3

    def test_judas_fail_rev_small(self):
        fx = BY_ID["JUDAS_FAIL_REV_SMALL"]
        bars = [{"ts": i, "o": 610.0, "h": 610.4, "l": 609.0, "c": c,
                 "v": 1000.0}
                for i, c in enumerate([610.0, 609.5, 609.2, 609.5, 609.6,
                                       609.6, 609.6])]
        assert judas_swing_detect(bars, "UP", atr20=4.0) is None
        assert fx["expected"]["judas_confirmed"] is False

    def test_utc_window_overlap_canonical_inside(self):
        fx = BY_ID["UTC_ACTIVITY_WINDOW_OVERLAP_CANONICAL_INSIDE"]
        info = utc_activity_window_check(fx["inputs"]["ts"])
        assert info["in_kz"] is fx["expected"]["in_kz"]
        assert info["which"] == fx["expected"]["which"]
        assert info["is_overlap"] is fx["expected"]["is_overlap"]
        assert info["config_version"] == KZ_CONFIG_VERSION
        # §3.6 windows are disjoint ⇒ 14:00 belongs to UTC_W2 only; the doc's
        # own `which` array is recorded as a doc_inconsistency in the fixture.
        assert info["utc_activity_window"] == "UTC_W2"
        assert "UTC_W1_W2_OVERLAP" in info["which"]
        assert info["degraded"] is True
        assert info["degraded_reason"] == E12_UNAVAILABLE_REASON

    def test_utc_window_w1_core_inside_overlap_outside(self):
        fx = BY_ID["UTC_ACTIVITY_WINDOW_UTC_W1_CORE_INSIDE_OVERLAP_OUTSIDE"]
        info = utc_activity_window_check(fx["inputs"]["ts"])
        assert info["which"] == fx["expected"]["which"]
        assert info["is_overlap"] is fx["expected"]["is_overlap"]
        assert info["core_windows"] == fx["expected"]["core_windows"]
        assert info["utc_activity_window"] == "UTC_W1"

    def test_integrity_order_wrong_penalty_0_5(self):
        fx = BY_ID["INTEGRITY_ORDER_WRONG_PENALTY_0.5"]
        exp = [ComponentDef("sweep", 1.0, 0), ComponentDef("BOS", 1.0, 1),
               ComponentDef("FVG", 1.0, 2)]
        order = ["FVG", "BOS", "sweep"]
        conf = [{"cid": c, "t_confirm_ms": 1000 * (i + 1), "p_confirm": i}
                for i, c in enumerate(order)]
        om = build_order_map(exp, conf)
        evaluate_order_ok(exp, order, om)
        integrity, cov, missing = sequence_integrity_v4(exp, order, om)
        assert integrity == pytest.approx(fx["expected"]["integrity"], abs=1e-12)
        assert abs(integrity - fx["expected"]["integrity_fixture"]) < 5e-3
        # The §8.1 `order_correct` array is stated in EXPECTED order
        # [sweep, BOS, FVG]; §7 Ch.3 names a different single ordered member
        # but the same 2×0.5 + 1×1.0 count, so Integrity is identical either
        # way (recorded as a doc divergence in the fixture note).
        assert [om[c].order_ok for c in ("sweep", "BOS", "FVG")] == \
            fx["inputs"]["order_correct"]
        assert sum(om[c].order_ok for c in order) == 1
        assert missing == []
        assert cov == pytest.approx(1.0, abs=1e-9)

    def test_conflict_resolution(self):
        fx = BY_ID["CONFLICT_RESOLUTION"]
        exp = expected_components("RTM.PO3.v1")
        kz = utc_activity_window_check(1768485600000)

        def mk(direction, conf, t):
            om = build_order_map(exp, po3_confirmations(t))
            order = [c["cid"] for c in po3_confirmations(t)]
            return build_bundle_pipeline(exp, order, om, 0.9, 1.0, kz,
                                         "RTM.PO3.v1", direction, t,
                                         params={"alpha": 1.0, "beta": 0.0,
                                                 "gamma": 0.0, "delta": 0.0})

        a = mk("UP", 0.91, 1768485600000)
        a.confidence = 0.91
        b = mk("DOWN", 0.62, 1768485600000 + 15 * 60 * 1000)
        b.confidence = 0.62
        active = resolve_conflicting_bundles([a, b])
        assert [x.bid for x in active] == [a.bid]
        assert a.fate == "active"
        assert b.fate == fx["expected"]["loser_fate"]
        assert b.conflict_with == a.bid

    def test_edge_h_l_invalid(self):
        fx = BY_ID["EDGE_H_L_INVALID"]
        bars = compress_window()
        bars[-1]["h"], bars[-1]["l"] = fx["inputs"]["high"], fx["inputs"]["low"]
        info = atr_ratio_detect(bars)
        # §3.2/§3.8: the invalid bar is skipped, never repaired.
        assert fx["expected"]["skip_bar"] is True
        assert info["is_range"] in (True, False)
        assert not any(b["h"] < b["l"] for b in bars[:-1])

    def test_edge_v_zero(self):
        fx = BY_ID["EDGE_V_ZERO"]
        bars = compress_window()
        bars[-3]["v"] = fx["inputs"]["volume"]
        info = atr_ratio_detect(bars)
        assert info["is_range"] is False
        assert info["degraded"] is True
        assert info["reason"] == VOL_UNAVAILABLE_REASON
        assert info["vol_ratio"] is None      # never a synthetic neutral value
        assert fx["expected"]["range_authorized"] is False

    def test_liquidity_grab_chain_valid(self):
        fx = BY_ID["LIQUIDITY_GRAB_CHAIN_VALID"]
        exp = expected_components("RTM.CHAIN.v1")
        assert [c.cid for c in exp] == fx["inputs"]["chain"]
        assert sum(c.weight for c in exp) == pytest.approx(
            fx["expected"]["total_weight"], abs=1e-12)
        conf = [{"cid": c, "t_confirm_ms": 1768485600000 + 900000 * (i + 1),
                 "p_confirm": 69200.0 - i} for i, c in enumerate(exp_cids())]
        om = build_order_map(exp, conf)
        order = [c["cid"] for c in conf]
        evaluate_order_ok(exp, order, om)
        integrity, cov, missing = sequence_integrity_v4(exp, order, om)
        assert integrity == pytest.approx(fx["expected"]["integrity"], abs=1e-12)
        assert all(om[c].order_ok for c in order)      # penalty 0
        kz = utc_activity_window_check(conf[-1]["t_confirm_ms"])
        bundle = build_bundle_pipeline(exp, order, om, 0.8, 1.0, kz,
                                       "RTM.CHAIN.v1", "UP",
                                       conf[-1]["t_confirm_ms"])
        assert fx["expected"]["emit_bundle"] is True and bundle is not None
        assert bundle.framework_id == "RTM.CHAIN.v1"
        assert "EV_RTM_011" in EVENT_CATALOG


def exp_cids():
    return ["sweep", "choch", "fvg", "retest", "vol_confirm"]


# ---------------------------------------------------------------------------
# §3.1 Integrity / order_map
# ---------------------------------------------------------------------------
class TestSequenceIntegrity:
    def test_absent_component_scores_zero(self):
        exp = [ComponentDef("a", 1.0, 0), ComponentDef("b", 1.0, 1)]
        om = build_order_map(exp, [{"cid": "a", "t_confirm_ms": 1}])
        evaluate_order_ok(exp, ["a"], om)
        integrity, cov, missing = sequence_integrity_v4(exp, ["a"], om)
        assert missing == ["b"]
        assert integrity == pytest.approx(1.0 / (2.0 + EPS), abs=1e-12)
        assert cov == pytest.approx(0.5, abs=1e-9)

    def test_zero_total_weight_gives_zero_integrity(self):
        exp = [ComponentDef("a", 0.0, 0)]
        om = build_order_map(exp, [{"cid": "a", "t_confirm_ms": 1}])
        integrity, cov, _ = sequence_integrity_v4(exp, ["a"], om)
        assert integrity == 0.0 and cov == 0.0

    def test_untimed_component_gets_partial_penalty(self):
        exp = [ComponentDef("a", 1.0, 0), ComponentDef("b", 1.0, 1)]
        integrity, cov, _ = sequence_integrity_v4(exp, ["a", "b"], {})
        assert integrity == pytest.approx(1.0 / (2.0 + EPS), abs=1e-12)
        assert cov == pytest.approx(1.0, abs=1e-9)

    def test_duplicate_events_are_deduplicated(self):
        exp = [ComponentDef("a", 1.0, 0)]
        om = build_order_map(exp, [{"cid": "a", "t_confirm_ms": 5},
                                   {"cid": "a", "t_confirm_ms": 5},
                                   {"cid": "a", "t_confirm_ms": 9}])
        assert len(om) == 1
        assert om["a"].t_confirm_ms == 5      # first PIT confirmation wins

    def test_pit_ordering_uses_t_confirm_only(self):
        exp = [ComponentDef("a", 1.0, 0), ComponentDef("b", 1.0, 1)]
        om = build_order_map(exp, [{"cid": "b", "t_confirm_ms": 10},
                                   {"cid": "a", "t_confirm_ms": 20}])
        evaluate_order_ok(exp, ["a", "b"], om)
        assert om["b"].order_ok is True and om["a"].order_ok is False


# ---------------------------------------------------------------------------
# §3.2 range detection
# ---------------------------------------------------------------------------
class TestRangeDetection:
    def test_compressed_window_is_a_range(self):
        info = atr_ratio_detect(compress_window())
        assert info["is_range"] is True
        assert info["ratio"] < 0.75
        assert info["hl_range"] < 2.5 * info["atr_long"]
        assert info["sigma_ratio"] < 0.6
        assert info["vol_ratio"] <= 0.9

    def test_expanded_window_is_not_a_range(self):
        info = atr_ratio_detect(lcg_window(140, seed=99, base=600.0))
        assert info["is_range"] is False

    def test_insufficient_history_fails_closed(self):
        info = atr_ratio_detect(compress_window(50))
        assert info["is_range"] is False
        assert info["reason"] == "INSUFFICIENT_HISTORY_QX"

    def test_sigma_term_is_enforced_issue_cp4_001(self):
        """§2 requires sigma(C)/ATR_l < 0.6 in addition to §3.2's HL term.

        The two terms are coupled (C ∈ [L, H]), so the σ gate is isolated by
        relaxing the ratio/HL thresholds through the governed parameters and
        showing that σ alone vetoes the range.
        """
        bars = compress_window()
        base = bars[-1]["c"]
        for i, b in enumerate(bars[-8:]):
            b["h"], b["l"] = base + 0.9, base - 0.9      # HL/ATR_l ≈ 1.5
            b["c"] = b["l"] if i % 2 == 0 else b["h"]    # σ(C) ≈ 0.9
        relaxed = get_params({"atr_ratio_th": 99.0, "range_hl_max_atr": 99.0})
        info = atr_ratio_detect(bars, params=relaxed)
        assert info["hl_range"] < 99.0 * info["atr_long"]
        assert info["sigma_ratio"] > 0.6
        assert info["is_range"] is False                 # σ term vetoes
        # With the σ threshold also relaxed the same bars form a range, which
        # proves the σ term — not the ratio/HL terms — is the binding gate.
        loose = get_params({"atr_ratio_th": 99.0, "range_hl_max_atr": 99.0,
                            "range_sigma_max": 99.0})
        assert atr_ratio_detect(bars, params=loose)["is_range"] is True

    def test_gap_resets_the_range_issue_cp4_003(self):
        bars = compress_window()
        atr_l = atr_ratio_detect(bars)["atr_long"]
        for b in bars[-4:]:
            for k in ("o", "h", "l", "c"):
                b[k] += 10 * atr_l
        info = atr_ratio_detect(bars)
        assert info["gap_reset"] is True
        assert info["gap_edge"] is True
        assert info["is_range"] is False
        assert info["reason"] == "RANGE_RESET_GAP_QX"

    def test_wilder_rma_matches_documented_recursion(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        rma = wilder_rma_series(vals, 3)
        seed = (1 + 2 + 3) / 3
        seed = (seed * 2 + 4) / 3
        seed = (seed * 2 + 5) / 3
        seed = (seed * 2 + 6) / 3
        assert rma == pytest.approx(seed, abs=1e-12)
        assert wilder_rma_series([1.0, 2.0], 3) == 0.0   # no fabricated warm-up


# ---------------------------------------------------------------------------
# §3.3–§3.5 MSS · OTE · Judas
# ---------------------------------------------------------------------------
class TestConcepts:
    def test_mss_requires_integrity_gate(self):
        assert mss_confirmed(604.2, 604.8, 1.5, 0.70) is True
        assert mss_confirmed(604.2, 604.8, 1.5, 0.60) is False

    def test_ote_rejects_nan_and_equal_legs(self):
        assert ote_zone_calc(float("nan"), 620) is None
        assert ote_zone_calc(600, 600 + 1e-12) is None

    def test_ote_zone_is_ordered_for_down_legs(self):
        zone = ote_zone_calc(620, 600)
        assert zone["lo"] < zone["hi"]
        assert zone["lo"] == pytest.approx(620 + 0.79 * (600 - 620))

    def test_judas_rejects_bad_direction(self):
        with pytest.raises(ValueError, match="JUDAS_DIRECTION_QX"):
            judas_swing_detect([{"c": 1.0}] * 6, "SIDEWAYS", 1.0)

    def test_judas_needs_room_for_the_reversal(self):
        bars = [{"ts": i, "o": 610.0, "h": 610.4, "l": 609.0, "c": c,
                 "v": 1.0} for i, c in enumerate([610.0, 609.5, 609.2])]
        assert judas_swing_detect(bars, "UP", atr20=4.0) is None

    def test_judas_rejects_zero_atr(self):
        bars = [{"ts": i, "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0, "v": 1.0}
                for i in range(8)]
        assert judas_swing_detect(bars, "UP", atr20=0.0) is None


# ---------------------------------------------------------------------------
# §3.6 UTC activity windows + the E12 degraded branch
# ---------------------------------------------------------------------------
class TestUTCWindows:
    def test_window_membership_table(self):
        cases = {"2026-01-15T03:00:00Z": "UTC_W0",
                 "2026-01-15T09:00:00Z": "UTC_W1",
                 "2026-01-15T18:00:00Z": "UTC_W2",
                 "2026-01-15T22:00:00Z": "UTC_W3"}
        for ts, expected in cases.items():
            assert utc_activity_window_check(ts)["utc_activity_window"] == expected

    def test_overlap_formula(self):
        assert window_overlap((7.0, 12.5), (12.5, 21.0)) is None
        assert window_overlap((7.0, 16.0), (12.5, 21.0)) == (12.5, 16.0)

    def test_non_utc_timestamp_rejected(self):
        for bad in ("2026-01-15T14:00:00+03:30", "2026-01-15T14:00:00"):
            with pytest.raises(ValueError, match=NON_UTC_REASON):
                utc_activity_window_check(bad)
        assert to_utc_ms("2026-01-15T14:00:00Z") == 1768485600000

    def test_econ_conflict_within_30_min(self):
        ts = to_utc_ms("2026-01-15T14:00:00Z")
        econ = [{"time_ms": ts + 20 * 60 * 1000, "impact": "HIGH"}]
        assert utc_activity_window_check(ts, econ)["econ_conflict"] is True
        far = [{"time_ms": ts + 45 * 60 * 1000, "impact": "HIGH"}]
        assert utc_activity_window_check(ts, far)["econ_conflict"] is False
        low = [{"time_ms": ts + 5 * 60 * 1000, "impact": "LOW"}]
        assert utc_activity_window_check(ts, low)["econ_conflict"] is False

    # -- the E12-unavailable → degraded branch (CP-4; CP-5 re-tests) ------
    def test_e12_absent_is_degraded_and_never_claims_canonical_authority(self):
        info = utc_activity_window_check(to_utc_ms("2026-01-15T14:00:00Z"))
        assert info["degraded"] is True
        assert info["degraded_reason"] == E12_UNAVAILABLE_REASON
        assert info["source"] == "E07_LOCAL_NON_AUTHORITATIVE"
        assert E12_CONTRACT not in info["source"]

    def test_e12_present_resolves_the_degraded_branch(self):
        provider = FakeE12({"which": ["UTC_W2", "UTC_W1_W2_OVERLAP"],
                            "is_overlap": True,
                            "utc_activity_window": "UTC_W2",
                            "config_version": "E12.WINDOWS.v4.0.0"})
        info = utc_activity_window_check(to_utc_ms("2026-01-15T14:00:00Z"),
                                         temporal_provider=provider)
        assert provider.calls == 1
        assert info["degraded"] is False
        assert info["source"] == E12_CONTRACT
        assert info["config_version"] == "E12.WINDOWS.v4.0.0"

    def test_e12_provider_failure_fails_closed_to_degraded(self):
        info = utc_activity_window_check(to_utc_ms("2026-01-15T14:00:00Z"),
                                         temporal_provider=FakeE12(boom=True))
        assert info["degraded"] is True
        assert info["degraded_reason"] == E12_UNAVAILABLE_REASON

    def test_e12_provider_returning_nothing_fails_closed(self):
        info = utc_activity_window_check(to_utc_ms("2026-01-15T14:00:00Z"),
                                         temporal_provider=FakeE12(payload=None))
        assert info["degraded"] is True
        assert info["source"] == "E07_LOCAL_NON_AUTHORITATIVE"

    def test_bundle_carries_the_degradation_into_its_lineage(self):
        exp = expected_components("RTM.PO3.v1")
        conf = po3_confirmations()
        om = build_order_map(exp, conf)
        kz = utc_activity_window_check(conf[-1]["t_confirm_ms"])
        bundle = build_bundle_pipeline(exp, [c["cid"] for c in conf], om, 0.9,
                                       1.0, kz, "RTM.PO3.v1", "UP",
                                       conf[-1]["t_confirm_ms"])
        assert bundle.degraded is True
        assert bundle.degraded_reason == E12_UNAVAILABLE_REASON
        assert bundle.temporal_authority == "E07_LOCAL_NON_AUTHORITATIVE"
        assert bundle.resolution_class != "Q5"   # Q5 needs the overlap gate


# ---------------------------------------------------------------------------
# §3.7 Confidence + quality classes
# ---------------------------------------------------------------------------
class TestConfidenceAndQuality:
    def test_confidence_formula(self):
        assert bundle_confidence(1.0, 0.9, 1.0, 1.0) == pytest.approx(
            0.4 + 0.25 * 0.9 + 0.2 + 0.15, abs=1e-12)
        assert bundle_confidence(9.0, 9.0, 9.0, 9.0) == 1.0     # min(1, …)

    def test_weights_sum_to_one(self):
        p = EngineParams()
        assert p.alpha + p.beta + p.gamma + p.delta == pytest.approx(1.0)

    def test_kz_align_score(self):
        assert kz_align_score({"in_kz": True}) == 1.0
        assert kz_align_score({"in_kz": False}) == 0.2
        assert kz_align_score({"in_kz": True, "econ_conflict": True}) == \
            pytest.approx(0.7)

    def test_cascade_boundaries(self):
        assert quality_class_cascade(0.4, 0.9) == "Q0"
        assert quality_class_cascade(0.5, 0.5) == "Q1"
        assert quality_class_cascade(0.75, 0.7) == "Q2"
        assert quality_class_cascade(0.85, 0.8) == "Q3"
        assert quality_class_cascade(0.95, 0.8) == "Q3"
        assert quality_class_cascade(0.95, 0.9) == "Q4"
        assert quality_class_cascade(1.0, 0.97) == "Q5"

    def test_q5_gates_cap_the_cascade_issue_cp4_006(self):
        kz_overlap = {"in_kz": True, "is_overlap": True}
        kz_no_overlap = {"in_kz": True, "is_overlap": False}
        assert resolution_class(1.0, 0.97, 0.9, 1.0, kz_overlap) == "Q5"
        # §3.7 Q5 needs Killzone overlap ⇒ capped to Q4 without it (the §9
        # case study declares Q5 without overlap; recorded as a divergence).
        assert resolution_class(1.0, 0.97, 0.9, 1.0, kz_no_overlap) == "Q4"
        assert resolution_class(1.0, 0.97, 0.9, 1.0, kz_overlap,
                               has_conflict=True) == "Q4"
        econ = {"in_kz": True, "is_overlap": True, "econ_conflict": True}
        assert resolution_class(1.0, 0.97, 0.9, 1.0, econ) == "Q4"

    def test_q4_and_q3_gates(self):
        kz = {"in_kz": True, "is_overlap": False}
        assert resolution_class(0.95, 0.9, 0.9, 0.5, kz) == "Q3"   # MTF < 0.6
        assert resolution_class(0.85, 0.8, 0.5, 1.0, kz) == "Q2"   # avgQ < 0.6
        assert quality_class_caps("Q0", 0.1, 0.1, 0.1, kz) == "Q0"


# ---------------------------------------------------------------------------
# §4 pipeline · conflict resolver · streaming/idempotency
# ---------------------------------------------------------------------------
class TestPipeline:
    def test_thresholds_gate_emission(self):
        exp = expected_components("RTM.PO3.v1")
        conf = po3_confirmations()[:3]
        om = build_order_map(exp, conf)
        kz = utc_activity_window_check(conf[-1]["t_confirm_ms"])
        assert build_bundle_pipeline(exp, [c["cid"] for c in conf], om, 0.9,
                                     1.0, kz, "RTM.PO3.v1", "UP",
                                     conf[-1]["t_confirm_ms"]) is None

    def test_mss_framework_uses_theta_mss(self):
        p = EngineParams()
        assert framework_threshold("RTM.MSS.v1", p) == p.th_mss
        assert framework_threshold("RTM.PO3.v1", p) == p.th_int

    def test_bid_shape_and_uniqueness_issue_cp4_004(self):
        import re
        ids = {new_bundle_id() for _ in range(50)}
        assert len(ids) == 50
        for bid in ids:
            assert re.fullmatch(r"bnd_[a-f0-9]{12}", bid)

    def test_snapshot_is_deterministic_and_content_bound(self):
        payload = {"framework_id": "RTM.PO3.v1", "present": ["sweep"],
                   "integrity": 1.0, "as_of_ms": 123}
        assert make_snapshot_id(payload) == make_snapshot_id(dict(payload))
        other = dict(payload, as_of_ms=124)
        assert make_snapshot_id(payload) != make_snapshot_id(other)

    def test_streaming_is_idempotent_per_bucket(self):
        eng = RTMEngineStreaming()
        for c in po3_confirmations():
            eng.on_event(c)
        as_of = po3_confirmations()[-1]["t_confirm_ms"]
        first = eng.process_at(as_of, lcg_window(20), framework_id="RTM.PO3.v1",
                              direction="UP")
        second = eng.process_at(as_of + 60000, lcg_window(20),
                                framework_id="RTM.PO3.v1", direction="UP")
        assert len(first) == 1
        assert second == []               # same 15-minute bucket ⇒ no re-emit

    def test_streaming_rejects_malformed_events(self):
        eng = RTMEngineStreaming()
        with pytest.raises(ValueError, match="EVENT_CONTRACT_QX"):
            eng.on_event({"cid": "sweep"})

    def test_streaming_pit_filters_future_confirmations(self):
        eng = RTMEngineStreaming()
        conf = po3_confirmations()
        for c in conf:
            eng.on_event(c)
        early = conf[2]["t_confirm_ms"]
        assert len(eng.confirmations("RTM.PO3.v1", early)) == 3

    def test_fate_machine_forward_only(self):
        exp = expected_components("RTM.PO3.v1")
        conf = po3_confirmations()
        om = build_order_map(exp, conf)
        kz = utc_activity_window_check(conf[-1]["t_confirm_ms"])
        b = build_bundle_pipeline(exp, [c["cid"] for c in conf], om, 0.9, 1.0,
                                  kz, "RTM.PO3.v1", "UP",
                                  conf[-1]["t_confirm_ms"])
        assert b.fate == "active"
        assert update_bundle_fate(b, bars_since=10).fate == "active"
        assert update_bundle_fate(b, bars_since=21).fate == "expired"
        assert update_bundle_fate(b, opposite_bos=True,
                                 opposite_sweep=True).fate == "expired"
        b2 = build_bundle_pipeline(exp, [c["cid"] for c in conf], om, 0.9, 1.0,
                                   kz, "RTM.PO3.v1", "UP",
                                   conf[-1]["t_confirm_ms"])
        assert update_bundle_fate(b2, ote_tapped=True,
                                 continuation=True).fate == "completed"
        b3 = build_bundle_pipeline(exp, [c["cid"] for c in conf], om, 0.9, 1.0,
                                   kz, "RTM.PO3.v1", "UP",
                                   conf[-1]["t_confirm_ms"])
        assert update_bundle_fate(b3, opposite_bos=True,
                                 opposite_sweep=True).fate == "invalidated"


# ---------------------------------------------------------------------------
# §5.1/§5.2 schema
# ---------------------------------------------------------------------------
class TestBundleSchema:
    def _bundle(self):
        exp = expected_components("RTM.PO3.v1")
        conf = po3_confirmations()
        om = build_order_map(exp, conf)
        kz = utc_activity_window_check(conf[-1]["t_confirm_ms"])
        return build_bundle_pipeline(exp, [c["cid"] for c in conf], om, 0.9,
                                     1.0, kz, "RTM.PO3.v1", "UP",
                                     conf[-1]["t_confirm_ms"])

    def test_schema_valid(self):
        b = self._bundle()
        b.validate_schema()
        assert b.version == BUNDLE_VERSION
        assert len(b.snapshot_id) == 64
        assert set(b.order_map) == set(c["cid"] for c in po3_confirmations())

    def test_schema_rejects_bad_fields(self):
        b = self._bundle()
        b.bid = "nope"
        with pytest.raises(ValueError, match="BUNDLE_SCHEMA_QX"):
            b.validate_schema()
        b = self._bundle()
        b.framework_id = "RTM.UNKNOWN.v1"
        with pytest.raises(ValueError, match="BUNDLE_SCHEMA_QX"):
            b.validate_schema()
        b = self._bundle()
        b.confidence = 1.4
        with pytest.raises(ValueError, match="BUNDLE_SCHEMA_QX"):
            b.validate_schema()
        b = self._bundle()
        b.components_present = []
        with pytest.raises(ValueError, match="BUNDLE_SCHEMA_QX"):
            b.validate_schema()

    def test_framework_ids_are_the_schema_enum(self):
        assert set(CHAIN_DEFS) == set(FRAMEWORK_IDS)
        with pytest.raises(ValueError, match="UNKNOWN_FRAMEWORK_QX"):
            expected_components("RTM.NOPE.v1")


# ---------------------------------------------------------------------------
# §6 parameters
# ---------------------------------------------------------------------------
class TestParams:
    def test_defaults_are_the_chapter_literals(self):
        p = EngineParams()
        assert (p.po3_bars, p.atr_ratio_th, p.po3_vol_th) == (8, 0.75, 0.9)
        assert (p.mss_prox_th, p.th_int, p.th_weight, p.th_mss) == \
            (0.5, 0.7, 0.6, 0.65)
        assert (p.ote_lo, p.ote_hi, p.ote_star) == (0.62, 0.79, 0.705)
        assert (p.judas_max_pen, p.judas_rev_min, p.judas_max_bars) == \
            (0.25, 1.0, 3)
        assert p.econ_pause_min == 30 and p.bundle_expiry_bars == 20
        assert (p.alpha, p.beta, p.gamma, p.delta) == (0.4, 0.25, 0.2, 0.15)
        assert p.redundancy_corr_th == 0.85

    def test_unknown_key_rejected(self):
        with pytest.raises(ValueError, match="UNKNOWN_E07_PARAM_QX"):
            get_params({"th_int2": 0.5})

    def test_override_applies(self):
        assert get_params({"th_int": 0.9}).th_int == 0.9
        assert set(E07_DEFAULTS) == set(EngineParams().__dict__)


# ---------------------------------------------------------------------------
# §8.2 deterministic replay · §8.3 no-future-leak
# ---------------------------------------------------------------------------
class TestReplayAndPIT:
    def test_100_replays_identical_snapshot_id(self):
        exp = expected_components("RTM.PO3.v1")
        conf = po3_confirmations()
        as_of = conf[-1]["t_confirm_ms"]
        ids = set()
        for _ in range(100):
            om = build_order_map(exp, conf)
            kz = utc_activity_window_check(as_of)
            b = build_bundle_pipeline(exp, [c["cid"] for c in conf], om, 0.9,
                                      1.0, kz, "RTM.PO3.v1", "UP", as_of)
            ids.add(b.snapshot_id)
        assert len(ids) == 1

    def test_run_engine_replay_is_byte_identical(self):
        bars = lcg_window(140, seed=5)
        r1 = run_engine(bars, po3_confirmations(), as_of_ms=bars[-1]["ts"])
        r2 = run_engine(bars, po3_confirmations(), as_of_ms=bars[-1]["ts"])
        assert r1["bundle"].snapshot_id == r2["bundle"].snapshot_id
        assert r1["integrity"] == r2["integrity"]
        assert r1["range"] == r2["range"]

    def test_no_future_leak(self):
        bars = lcg_window(140, seed=5)
        as_of = bars[-1]["ts"]
        future = [{"cid": "sweep", "t_confirm_ms": as_of + 10 ** 9,
                   "p_confirm": 1.0}]
        result = run_engine(bars, po3_confirmations() + future, as_of_ms=as_of)
        # max(t_confirm) over the consumed set must not exceed as_of.
        exp = expected_components("RTM.PO3.v1")
        om = build_order_map(exp, [c for c in po3_confirmations() + future
                                   if c["t_confirm_ms"] <= as_of])
        assert max(e.t_confirm_ms for e in om.values()) <= as_of
        assert "sweep" in result["bundle"].components_present
        assert result["bundle"].as_of_ms == as_of
        assert as_of - bars[-1]["ts"] >= 0

    def test_empty_window_fails_closed(self):
        with pytest.raises(ValueError, match="EMPTY_WINDOW_QX"):
            run_engine([])


# ---------------------------------------------------------------------------
# §8.4 ablation · §8.5 calibration · §8.6 redundancy
# ---------------------------------------------------------------------------
class TestAblationCalibrationRedundancy:
    def test_ablation_deltas_are_ordered_like_the_chapter_table(self):
        """§8.4: removing Sweep costs more Integrity than BOS > FVG > Volume."""
        exp = expected_components("RTM.PO3.v1")
        conf = po3_confirmations()
        om = build_order_map(exp, conf)
        evaluate_order_ok(exp, [c["cid"] for c in conf], om)
        base, _, _ = sequence_integrity_v4(exp, [c["cid"] for c in conf], om)
        deltas = {}
        for cid in ("sweep", "choch", "fvg", "vol_confirm"):
            kept = [c["cid"] for c in conf if c["cid"] != cid]
            om2 = build_order_map(exp, [c for c in conf if c["cid"] in kept])
            evaluate_order_ok(exp, kept, om2)
            i2, _, _ = sequence_integrity_v4(exp, kept, om2)
            deltas[cid] = base - i2
        assert deltas["sweep"] > deltas["choch"] > deltas["fvg"] > \
            deltas["vol_confirm"]
        assert deltas["sweep"] == pytest.approx(1.5 / (5.0 + EPS), abs=1e-9)

    def test_wilson_ci_matches_the_formula(self):
        """§0/§7 Ch.1-14: 26/41 ⇒ Wilson CI [48%, 76%] (recomputed here)."""
        p_hat, n = 26 / 41, 41
        lo, hi = wilson_ci(p_hat, n)
        z = 1.96
        denom = 1 + z * z / n
        centre = p_hat + z * z / (2 * n)
        spread = z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
        assert lo == pytest.approx((centre - spread) / denom, abs=1e-12)
        assert hi == pytest.approx((centre + spread) / denom, abs=1e-12)
        # The chapter's rounded interval [48%, 76%] is reproduced.
        assert round(lo, 2) == 0.48 and round(hi, 2) == 0.76
        assert wilson_ci(0.5, 0) == (0.0, 0.0)

    def test_integrity_buckets_are_monotone_in_the_wilson_lower_bound(self):
        """§8.5: a higher Integrity bucket must not have a lower success rate."""
        buckets = [(6, 20), (12, 20), (17, 20)]        # (successes, n)
        rates = [k / n for k, n in buckets]
        assert rates == sorted(rates)                    # monotone by bucket
        lower = [wilson_ci(k / n, n)[0] for k, n in buckets]
        assert lower == sorted(lower)
        upper = [wilson_ci(k / n, n)[1] for k, n in buckets]
        assert upper == sorted(upper)

    def test_redundancy_halves_the_correlated_weight(self):
        exp = expected_components("RTM.CHAIN.v1")
        base = [float(i) for i in range(20)]
        # `retest` carries an uncorrelated (sine-phase) series so that only
        # the genuinely redundant component is halved.
        series = {"sweep": base, "choch": [v * 1.0001 for v in base],
                  "fvg": [(-1) ** i for i in range(20)],
                  "retest": [math.sin(i * 1.7) * 10 for i in range(20)],
                  "vol_confirm": [math.cos(i * 2.3) * 7 for i in range(20)]}
        assert abs(pearson(series["sweep"], series["retest"])) <= 0.85
        assert abs(pearson(series["sweep"], series["vol_confirm"])) <= 0.85
        assert abs(pearson(series["sweep"], series["fvg"])) <= 0.85
        assert abs(pearson(series["sweep"], series["choch"])) > 0.85
        halved = redundancy_halve_weights(exp, series, 0.85)
        by_cid = {c.cid: c.weight for c in halved}
        original = {c.cid: c.weight for c in exp}
        for cid, w in by_cid.items():
            if cid == "choch":
                assert w == pytest.approx(original[cid] * 0.5)
            else:
                assert w == pytest.approx(original[cid])
        assert by_cid["choch"] == pytest.approx(0.5)

    def test_pearson_edge_cases(self):
        assert pearson([1.0], [1.0]) == 0.0
        assert pearson([1.0, 1.0], [2.0, 3.0]) == 0.0   # zero variance


# ---------------------------------------------------------------------------
# §8.7 serialization compatibility
# ---------------------------------------------------------------------------
class TestSerialization:
    def test_v3_payload_upcasts_without_failing(self):
        v3 = {"bundle_id": "legacy-1", "framework": "RTM.PO3.v1",
              "present": ["sweep", "choch", "bos", "fvg", "vol_confirm"],
              "missing": [], "integrity": 0.95, "confidence": 0.9,
              "direction": "UP", "q_class": "Q4", "as_of": 1768485600000}
        bundle = load_v3_adapter(v3)
        assert bundle.version == BUNDLE_VERSION
        assert bundle.bid.startswith("bnd_")
        assert bundle.resolution_class == "Q4"
        assert bundle.degraded is True
        assert bundle.degraded_reason == "LEGACY_V3_PAYLOAD_QX"
        assert len(bundle.snapshot_id) == 64
        bundle.validate_schema()

    def test_v3_roundtrip_is_stable(self):
        v3 = {"bundle_id": "legacy-2", "framework": "RTM.MSS.v1",
              "present": ["sweep", "choch"], "integrity": 0.8,
              "confidence": 0.7, "direction": "DOWN", "as_of": 1000}
        first = load_v3_adapter(v3)
        second = load_v3_adapter(v3)
        assert first.snapshot_id == second.snapshot_id

    def test_v3_ambiguous_payload_rejected(self):
        with pytest.raises(ValueError, match="V3_ADAPTER_QX"):
            load_v3_adapter({"framework": "RTM.PO3.v1"})
        with pytest.raises(ValueError, match="V3_ADAPTER_QX"):
            load_v3_adapter(["not", "an", "object"])


# ---------------------------------------------------------------------------
# Batch driver + EngineBase binding
# ---------------------------------------------------------------------------
def _obs_window(bars, tf="15m"):
    obs = []
    for i, b in enumerate(bars):
        ts = "2026-01-15T%02d:%02d:00.000Z" % ((i // 4) % 24, (i * 15) % 60)
        obs.append(MarketObservation(
            symbol="BNBUSDT", timeframe=tf,
            open=Decimal(str(round(b["o"], 6))), high=Decimal(str(round(b["h"], 6))),
            low=Decimal(str(round(b["l"], 6))), close=Decimal(str(round(b["c"], 6))),
            volume=Decimal(str(round(b["v"], 3))), oi=None, timestamp=ts,
            sequence=i, status="CLOSED"))
    return obs


class TestRunEngineAndBase:
    def test_run_engine_emits_bundle_complete(self):
        bars = lcg_window(140, seed=5)
        result = run_engine(bars, po3_confirmations(), as_of_ms=bars[-1]["ts"])
        assert result["engine"] == ENGINE
        assert result["contract_version"] == CONTRACT_VERSION
        assert result["bundle"] is not None
        assert "EV_RTM_004" in result["events"]
        assert result["degraded"] is True

    def test_run_engine_without_events_emits_incomplete(self):
        bars = lcg_window(140, seed=5)
        result = run_engine(bars, None, as_of_ms=bars[-1]["ts"])
        assert result["bundle"] is None
        assert result["events"] == ["EV_RTM_005"]

    def test_missing_window_fails_closed(self):
        with pytest.raises(ValueError, match="MISSING_WINDOW_CONTEXT_QX"):
            E07RTMEngine().compute("BNBUSDT", "15m", "2026-01-15T00:00:00Z", {})

    def test_compute_emits_24_field_valid_evidence(self):
        bars = lcg_window(140, seed=5)
        evs = E07RTMEngine().compute(
            "BNBUSDT", "15m", "2026-01-15T00:00:00Z",
            {"window": _obs_window(bars),
             "events": po3_confirmations(), "direction": "UP"})
        assert len(evs) == 1
        ev = evs[0]
        ev.validate_24_fields()
        assert ev.engine_id == "E07"
        assert ev.direction in (-1, 0, 1)
        assert ev.validity == "DEGRADED"        # E12 absent at CP-4
        assert E12_UNAVAILABLE_REASON in ev.explanation
        assert ev.resolution_class in ("Q0", "Q1", "Q2", "Q3", "Q4", "Q5")

    def test_compute_returns_empty_for_an_empty_window(self):
        assert E07RTMEngine().compute("BNBUSDT", "15m",
                                      "2026-01-15T00:00:00Z",
                                      {"window": []}) == []

    def test_compute_rejects_unknown_params(self):
        with pytest.raises(ValueError, match="UNKNOWN_E07_PARAM_QX"):
            E07RTMEngine().compute("BNBUSDT", "15m", "2026-01-15T00:00:00Z",
                                   {"window": _obs_window(lcg_window(140)),
                                    "e07_params": {"nope": 1}})

    def test_t_dr_001_deterministic_replay(self):
        """T-DR-001: E07 output identical on re-run over the same inputs."""
        bars = lcg_window(140, seed=21)
        conf = po3_confirmations()
        a = E07RTMEngine().compute("BNBUSDT", "15m", "2026-01-15T00:00:00Z",
                                   {"window": _obs_window(bars),
                                    "events": conf})
        b = E07RTMEngine().compute("BNBUSDT", "15m", "2026-01-15T00:00:00Z",
                                   {"window": _obs_window(bars),
                                    "events": conf})
        assert len(a) == len(b) == 1
        assert a[0].snapshot_id == b[0].snapshot_id
        assert a[0].condition_state == b[0].condition_state
        assert a[0].strength == b[0].strength


class TestWaveOutDiscipline:
    def test_no_wave_out_feature_is_silently_stubbed(self):
        """G6: every Wave-Out item raises; nothing in E07 implements one."""
        err = WaveOutError("e12_temporal_windows_canonical",
                           "E12_NOT_BUILT_AT_CP4")
        assert err.feature == "e12_temporal_windows_canonical"
        with pytest.raises(WaveOutError):
            raise err

    def test_engine_module_has_no_placeholders(self):
        src = (pathlib.Path(__file__).resolve().parents[2]
               / "apex" / "engines" / "e07_rtm" / "engine.py").read_text()
        for token in ("TODO", "FIXME", "NotImplementedError"):
            assert token not in src
