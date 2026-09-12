"""E06 OrderBlock — §8 validation battery (blueprint L8046–8292) + §1–§6
conformance. §8.1 fixtures re-derived per ADR-P2-007
(tests/fixtures/e06_golden_fixtures.json). Includes the mandated
CONSUMPTION-LINT test: E06 consumes E01–E05 evidence strictly through the
base-catalog interfaces and re-computes ZERO SMA/ATR/Wilder paths
internally. T-DR-001 re-run."""

import ast
import json
import math
import os
import re

import pytest

from apex.engines.e06_orderblock import (
    E06OrderBlockEngine,
    E06_DEFAULTS,
    EVENT_CATALOG,
    OB,
    OrderBlockEngine,
    asymmetric_zone,
    binomial_test_gt_half,
    body_ratio_pit,
    canonical_hash,
    directional_mitigation,
    e06_snapshot_id,
    get_params,
    iou_zones,
    load_v3_adapter,
    promote_q4,
    promote_quality,
    run_engine,
    wilson_ci,
)
from apex.data_catalog.contracts import MarketObservation
from decimal import Decimal

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "..", "fixtures",
                            "e06_golden_fixtures.json")
ENGINE_SOURCE = os.path.join(os.path.dirname(__file__), "..", "..",
                             "apex", "engines", "e06_orderblock",
                             "engine.py")


def load_fixtures():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as fh:
        return {f["fixture_id"]: f
                for f in json.load(fh)["fixtures"]}


FIX = load_fixtures()


def ob_from_fixture(payload, **extra):
    """Build a schema-complete OB from a (possibly partial) fixture."""
    base = dict(
        oid=payload["oid"], direction=payload["direction"],
        zone_lo=float(payload["zone_lo"]), zone_hi=float(payload["zone_hi"]),
        origin_ts=int(payload["origin_ts"]),
        origin_idx=int(payload["origin_idx"]),
        displacement_mag=float(payload.get("displacement_mag", 0.0)),
        displacement_multi=float(payload.get("displacement_multi", 0.0)),
        structural_event=payload.get("structural_event", "NONE"),
        structural_strength=float(payload.get("structural_strength", 0.3)),
        otype=payload.get("otype", "ENTRY"),
        quality=payload.get("quality", "Q2"),
        fate=payload.get("fate", "CANDIDATE"),
        vol_ratio=float(payload.get("vol_ratio", 0.0)),
        width=float(payload["zone_hi"]) - float(payload["zone_lo"]),
    )
    base.update(extra)
    ob = OB(**base)
    ob.snapshot_id = e06_snapshot_id(ob)
    return ob


# ---------------------------------------------------------------------------
# Consumption lint (mandated CP-3 deliverable): zero internal
# re-computation of E01–E05 evidence paths (SMA / ATR / Wilder / EWMA)
# ---------------------------------------------------------------------------
class TestConsumptionLint:
    def test_source_has_no_recomputation_internals(self):
        with open(ENGINE_SOURCE, "r", encoding="utf-8") as fh:
            src = fh.read()
        lowered = src.lower()
        # no Wilder/EMA smoothing implementations
        assert "wilder" not in lowered
        assert not re.search(r"\bdef\s+(ewma|rma|ema|sma|atr_calc|"
                             r"true_range|vol_sma|rolling_mean)\w*\s*\(",
                             lowered)
        # no smoothing-factor construction
        assert not re.search(r"alpha\s*=\s*1\s*/", lowered)
        # AST: no function definitions recomputing indicator internals
        tree = ast.parse(src)
        bad_names = re.compile(r"(?:^|_)(atr|sma|ema|ewma|rma|wilder|"
                               r"true_range|vol_sma|rolling_mean|"
                               r"atr_calc|volatility)$")
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert not bad_names.search(node.name.lower()), node.name
            # no imports from sibling engine packages (E01..E05)
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not re.match(r"apex\.engines\.e0[1-5]\b", mod), mod
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not re.match(r"apex\.engines\.e0[1-5]\b",
                                        alias.name), alias.name

    def test_run_engine_requires_both_evidence_streams(self):
        with pytest.raises(ValueError, match="MISSING_EVIDENCE_QX"):
            run_engine([{"o": 1, "h": 1, "l": 1, "c": 1, "v": 1,
                         "ts": 0}], volume_evidence=None,
                       volatility_evidence=None)

    def test_misaligned_evidence_fails_closed(self):
        eng = OrderBlockEngine()
        bars = [{"o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10, "ts": i}
                for i in range(3)]
        with pytest.raises(ValueError,
                           match="UPSTREAM_EVIDENCE_ALIGNMENT_QX"):
            eng.ingest_bars(bars, [None], [None])

    def test_missing_volume_evidence_entry_fails_closed(self):
        eng = OrderBlockEngine()
        bars = [{"o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10, "ts": i}
                for i in range(2)]
        with pytest.raises(ValueError, match="MISSING_VOLUME_EVIDENCE_QX"):
            eng.ingest_bars(bars, [None, None],
                            [{"snapshot_id": "s", "as_of": i,
                              "atr_n": 1.0} for i in range(2)])

    def test_missing_volatility_evidence_entry_fails_closed(self):
        eng = OrderBlockEngine()
        bars = [{"o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10, "ts": i}
                for i in range(2)]
        with pytest.raises(ValueError,
                           match="MISSING_VOLATILITY_EVIDENCE_QX"):
            eng.ingest_bars(bars,
                            [{"snapshot_id": "s", "as_of_ts": i,
                              "volume_sma": 1.0, "volume_ratio": 1.0}
                             for i in range(2)],
                            [None, None])

    def test_volume_pit_violation_fails_closed(self):
        eng = OrderBlockEngine()
        bars = [{"o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10, "ts": i}
                for i in range(1)]
        vol = [{"snapshot_id": "s", "as_of_ts": 5,
                "availability_time_ms": 9, "volume_sma": 1.0,
                "volume_ratio": 1.0}]
        vola = [{"snapshot_id": "s", "as_of": 0, "atr_n": 1.0}]
        with pytest.raises(ValueError, match="VOLUME_EVIDENCE_PIT_QX"):
            eng.ingest_bars(bars, vol, vola)

    def test_nonfinite_atr_fails_closed(self):
        eng = OrderBlockEngine()
        bars = [{"o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10, "ts": 0}]
        vol = [{"snapshot_id": "s", "as_of_ts": 0, "volume_sma": 1.0,
                "volume_ratio": 1.0}]
        with pytest.raises(ValueError,
                           match="INVALID_VOLATILITY_EVIDENCE_QX"):
            eng.ingest_bars(bars, vol,
                            [{"snapshot_id": "s", "as_of": 0,
                              "atr_n": float("nan")}])


# ---------------------------------------------------------------------------
# §8.1 golden fixtures (12, re-derived semantics)
# ---------------------------------------------------------------------------
class TestGoldenFixtures:
    def test_f01_up_q3_schema_and_salience(self):
        f = FIX["E06_F01_UP_Q3"]["ob"]
        ob = ob_from_fixture(f)
        ob.validate_schema()
        assert ob.quality == "Q3" and ob.fate == "ACTIVE"
        # §2.7 Salience re-derivation (matches §9 case study 0.916):
        w_d, w_s, w_v, w_f = get_params().salience_weights
        sal = (w_d * min(3.5 / 3, 1) + w_s * 1.0
               + w_v * min(2.0 / 3, 1) + w_f * 1.0)
        assert sal == pytest.approx(0.9166667, abs=1e-6)
        # Q3 contract re-derivation: Context ∧ StructuralEvent
        p = get_params()
        context = ((2.0 >= p.vol_min)
                   and (False or 3.5 >= p.disp_high))
        assert context and f["structural_event"] in ("BOS", "CHoCH")

    def test_f02_down_q2_ladder_redrivation(self):
        f = FIX["E06_F02_DOWN_Q2_low_volume"]
        ob = ob_from_fixture(f["ob"])
        ob.validate_schema()              # valid v4 record as stored
        # §1.6 ladder re-derivation: VolRatio 1.1 < 1.3 ⇒ the Q2 volume
        # check FAILS ⇒ normative quality is Q1 (doc's Q2 label is the
        # recorded inconsistency — fixture doc_inconsistency,
        # ISSUE-CP3-012)
        p = get_params()
        assert f["ob"]["vol_ratio"] < p.vol_min
        checks = {"origin": True, "disp_single": True, "vol_ratio": False,
                  "structural": True}
        probe = OB(oid="probe", direction="DOWN", zone_lo=0, zone_hi=1,
                   origin_ts=0, origin_idx=0, displacement_mag=0,
                   displacement_multi=0, structural_event="NONE",
                   structural_strength=0.0, snapshot_id="0" * 64)
        promote_quality(probe, checks)
        assert probe.quality == "Q1"
        assert "ISSUE-CP3-012" in f["doc_inconsistency"]

    def test_f03_breaker_role_reversal(self):
        f = FIX["E06_F03_BREAKER"]["ob"]
        ob = ob_from_fixture(f)
        ob.validate_schema()
        assert ob.otype == "BREAKER" and ob.direction == "DOWN"
        assert ob.oid.endswith("_breaker")
        assert ob.quality == "Q3" and ob.fate == "ACTIVE"
        assert len(ob.snapshot_id) == 64

    def test_f04_reversal_chich(self):
        f = FIX["E06_F04_REVERSAL_CHoCH"]["ob"]
        ob = ob_from_fixture(f)
        ob.validate_schema()
        assert ob.structural_event == "CHoCH"
        assert ob.otype == "REVERSAL"
        assert ob.structural_strength == pytest.approx(0.6)
        # CHoCH Q3 Context via Disp_high (2.1 >= 1.8, no FVG needed)
        p = get_params()
        assert (1.4 >= p.vol_min) and (2.1 >= p.disp_high)

    def test_f05_invalidated_terminal(self):
        f = FIX["E06_F05_INVALIDATED"]["ob"]
        ob = ob_from_fixture(f)
        ob.validate_schema()
        assert ob.fate == "INVALIDATED" and ob.quality == "QX"

    def test_f06_mitigated_with_touches(self):
        f = FIX["E06_F06_MITIGATED"]["ob"]
        ob = ob_from_fixture(f, touch_count=f.get("touch_count", 2),
                             mitigation=f.get("mitigation", 0.65))
        ob.validate_schema()
        assert ob.mitigation >= get_params().mit_activate
        assert ob.touch_count == 2

    def test_f07_h_eq_l_rejected(self):
        bar = FIX["E06_F07_H_EQ_L_rejected"]["bar"]
        assert body_ratio_pit(bar) == 0.0
        # H<L invalid candle variant also → 0 (§3.3)
        assert body_ratio_pit({"o": 1, "h": 0.5, "l": 1.5, "c": 1}) == 0.0

    def test_f08_v_zero_vol_ratio_and_q1_cap(self):
        f = FIX["E06_F08_V_zero"]
        # V=0 ⇒ VolRatio=0 (never infinity — §2.1/§3.3); consumed via
        # evidence, asserted here as the contract outcome
        assert f["expected_vol_ratio"] == 0.0
        p = get_params()
        assert not (0.0 >= p.vol_min)         # Context AND term fails
        checks = {"origin": True, "disp_single": True, "vol_ratio": False,
                  "structural": True}
        probe = OB(oid="probe", direction="UP", zone_lo=0, zone_hi=1,
                   origin_ts=0, origin_idx=0, displacement_mag=0,
                   displacement_multi=0, structural_event="NONE",
                   structural_strength=0.0, snapshot_id="0" * 64)
        promote_quality(probe, checks)
        assert probe.quality == f["expected_quality_cap"]  # "Q1"

    def test_f09_iou_merge_redrived(self):
        f = FIX["E06_F09_IoU_merge"]
        a, b = f["ob_a"], f["ob_b"]
        iou = iou_zones(a["zone_lo"], a["zone_hi"], b["zone_lo"],
                        b["zone_hi"])
        assert iou == pytest.approx(f["expected_iou"], abs=1e-6)
        assert (iou > get_params().iou_thresh) == f["should_merge"]
        # engine merge keeps the higher-Salience OB
        eng = OrderBlockEngine()
        ob_a = ob_from_fixture({"oid": "ob_a", "direction": "UP",
                                "zone_lo": a["zone_lo"],
                                "zone_hi": a["zone_hi"],
                                "origin_ts": 0, "origin_idx": 10},
                               salience=0.9)
        ob_b = ob_from_fixture({"oid": "ob_b", "direction": "UP",
                                "zone_lo": b["zone_lo"],
                                "zone_hi": b["zone_hi"],
                                "origin_ts": 0, "origin_idx": 12},
                               salience=0.5)
        eng.active_obs = [ob_b, ob_a]
        eng._merge_overlapping()
        assert len(eng.active_obs) == 1
        assert eng.active_obs[0].oid == "ob_a"      # higher Salience kept
        merged = [o for o in eng.history if o.oid == "ob_b"][0]
        assert merged.fate == "MERGED" and merged.quality == "QX"

    def test_f10_directional_wrong_side(self):
        f = FIX["E06_F10_directional_wrong_side"]
        ob = OB(oid="ob_x", direction=f["ob"]["direction"],
                zone_lo=f["ob"]["zone_lo"], zone_hi=f["ob"]["zone_hi"],
                origin_ts=0, origin_idx=0, displacement_mag=0.0,
                displacement_multi=0.0, structural_event="NONE",
                structural_strength=0.0, width=2.0, snapshot_id="0" * 64)
        touch, side_ok, depth = directional_mitigation(
            ob, f["bar"], f["prev_close"], first_touch_strict=True)
        assert touch is True                      # geometric overlap exists
        assert side_ok == f["expected_side_ok"]
        # §2.8 effective-touch semantics: wrong-side penetration MUST NOT
        # count (ISSUE-CP3-011) — no state change may result
        assert (touch and side_ok) == f["expected_effective_touch"]
        assert depth > 0.0

    def test_f11_context_via_disp_high(self):
        f = FIX["E06_F11_context_via_disp_high"]["input"]
        p = get_params()
        context = ((f["vol_ratio"] >= p.vol_min)
                   and (f["fvg_same"]
                        or f["disp_multi"] >= p.disp_high))
        assert context is True

    def test_f12_context_fails_low_volume(self):
        f = FIX["E06_F12_context_fails_low_volume"]["input"]
        p = get_params()
        context = ((f["vol_ratio"] >= p.vol_min)
                   and (f["fvg_same"]
                        or f["disp_multi"] >= p.disp_high))
        assert context is False


# ---------------------------------------------------------------------------
# §3 formula + §2 semantics units
# ---------------------------------------------------------------------------
class TestFormulas:
    def test_asymmetric_zone_up_and_down(self):
        bar = {"o": 100.5, "h": 103, "l": 98.5, "c": 98.8}
        lo, hi = asymmetric_zone("UP", bar, atr=2.0, zone_tol=0.15)
        assert lo == pytest.approx(98.5 - 0.3)
        assert hi == pytest.approx(98.8 + 0.3)
        lo_d, hi_d = asymmetric_zone("DOWN", bar, atr=2.0, zone_tol=0.15)
        assert lo_d == pytest.approx(100.5 - 0.3)
        assert hi_d == pytest.approx(103 + 0.3)

    def test_iou_formula(self):
        assert iou_zones(100, 104, 100.5, 104.5) == pytest.approx(
            3.5 / 4.5, abs=1e-9)
        assert iou_zones(100, 101, 200, 201) == 0.0

    def test_promote_ladder_ratchet(self):
        probe = OB(oid="p", direction="UP", zone_lo=0, zone_hi=1,
                   origin_ts=0, origin_idx=0, displacement_mag=0,
                   displacement_multi=0, structural_event="NONE",
                   structural_strength=0.0, snapshot_id="0" * 64)
        promote_quality(probe, {"origin": True, "disp_single": True})
        assert probe.quality == "Q1"
        promote_quality(probe, {"origin": True, "disp_single": True,
                                "vol_ratio": True})
        assert probe.quality == "Q2"
        promote_quality(probe, {"origin": True, "disp_single": True,
                                "vol_ratio": True, "disp_high": True,
                                "structural": True})
        assert probe.quality == "Q3"
        promote_quality(probe, {"origin": True, "disp_single": True,
                                "vol_ratio": True, "disp_high": True,
                                "structural": True, "oos_validated": True})
        assert probe.quality == "Q4"
        # ratchet: a weaker checks set never downgrades
        promote_quality(probe, {"origin": True})
        assert probe.quality == "Q4"
        assert probe.lineage[-1]["to"] == "Q4"

    def test_wilson_and_binomial(self):
        lo, hi = wilson_ci(0.65, 20)
        assert 0 < lo < 0.65 < hi < 1
        # §7 Ch.1-14 exact binomial: k=9 of 11 → p≈0.0327
        p = binomial_test_gt_half(9, 11)
        assert p == pytest.approx((55 + 11 + 1) / 2048, abs=1e-9)
        assert promote_q4(9, 11) is True
        assert promote_q4(6, 10) is False
        assert promote_q4(0, 0) is False

    def test_schema_enum_fail_closed(self):
        ob = ob_from_fixture(FIX["E06_F01_UP_Q3"]["ob"])
        ob.direction = "SIDEWAYS"
        with pytest.raises(ValueError, match="OB_DIRECTION_QX"):
            ob.validate_schema()
        ob2 = ob_from_fixture(FIX["E06_F01_UP_Q3"]["ob"])
        ob2.fate = "EXPLODED"
        with pytest.raises(ValueError, match="OB_FATE_QX"):
            ob2.validate_schema()
        ob3 = ob_from_fixture(FIX["E06_F01_UP_Q3"]["ob"])
        ob3.snapshot_id = "short"
        with pytest.raises(ValueError, match="OB_SNAPSHOT_QX"):
            ob3.validate_schema()


# ---------------------------------------------------------------------------
# Bar-driven lifecycle scenario (detection → retest → mitigation →
# invalidation → breaker reclaim) with fully-consumed evidence
# ---------------------------------------------------------------------------
def _scenario_bars():
    bars = []
    # 0..4 gentle noise
    for i in range(5):
        bars.append({"o": 100.0, "h": 100.2, "l": 99.8, "c": 100.1,
                     "v": 1000, "ts": i * 3600000})
    # 5: bearish origin (BR 0.68)
    bars.append({"o": 100.5, "h": 101.0, "l": 98.5, "c": 98.8, "v": 1500,
                 "ts": 5 * 3600000})
    # 6: displacement UP
    bars.append({"o": 98.8, "h": 103.5, "l": 98.7, "c": 103.2, "v": 3000,
                 "ts": 6 * 3600000})
    # 7: continuation
    bars.append({"o": 103.2, "h": 104.6, "l": 103.0, "c": 104.4, "v": 2000,
                 "ts": 7 * 3600000})
    # 8..11 drift up (no zone touch)
    for j, c in enumerate((105.2, 106.0, 106.8, 107.4)):
        bars.append({"o": c - 0.4, "h": c + 0.3, "l": c - 0.6, "c": c,
                     "v": 1200, "ts": (8 + j) * 3600000})
    # 12: retest from above (shallow)
    bars.append({"o": 107.0, "h": 100.5, "l": 98.9, "c": 100.2, "v": 1500,
                 "ts": 12 * 3600000})
    # 13: deep penetration → mitigated
    bars.append({"o": 100.2, "h": 100.8, "l": 98.3, "c": 98.6, "v": 1400,
                 "ts": 13 * 3600000})
    # 14: close below zone_lo − 0.2·ATR → invalidated
    bars.append({"o": 98.6, "h": 100.0, "l": 97.3, "c": 97.5, "v": 1300,
                 "ts": 14 * 3600000})
    # 15: reclaim through the far edge → breaker
    bars.append({"o": 97.5, "h": 100.2, "l": 99.0, "c": 99.9, "v": 2500,
                 "ts": 15 * 3600000})
    # 16..21 flat inside breaker-safe band (no touch, no invalidation)
    for j in range(6):
        bars.append({"o": 99.3, "h": 99.5, "l": 99.2, "c": 99.4,
                     "v": 900, "ts": (16 + j) * 3600000})
    return bars


def _evidence(n, atr=2.0, vr_default=1.0, vr_at=None):
    vol, vola = [], []
    for i in range(n):
        vr = vr_default if vr_at is None else vr_at.get(i, vr_default)
        vol.append({"snapshot_id": "s" + str(i), "as_of_ts": i * 3600000,
                    "availability_time_ms": i * 3600000,
                    "volume_sma": 1000.0, "volume_ratio": vr})
        vola.append({"snapshot_id": "v" + str(i), "as_of": i * 3600000,
                     "atr_n": atr, "tr_method": "Wilder-free-evidence"})
    return vol, vola


def _run_scenario(vr_override=None, atr=2.0, struct=True):
    bars = _scenario_bars()
    vol, vola = _evidence(len(bars), atr=atr, vr_at=vr_override)
    struct_by_idx = ({5: [{"kind": "BOS", "direction": "UP",
                           "valid_at_idx": 6, "level": 101.0,
                           "ts": 6 * 3600000}]} if struct else {})
    res = run_engine(bars, struct_events_by_idx=struct_by_idx,
                     fvg_by_idx={}, volume_evidence=vol,
                     volatility_evidence=vola)
    return res, bars


class TestLifecycleScenario:
    def test_up_ob_q3_detected_with_consumed_evidence(self):
        res, bars = _run_scenario(vr_override={6: 2.0})
        obs = res["obs"]
        created = [o for o in obs if o.oid == "ob_18000000_5_UP"]
        assert created, [o.oid for o in obs]
        ob = created[0]
        assert ob.direction == "UP" and ob.otype == "ENTRY"
        assert ob.zone_lo == pytest.approx(98.2)     # 98.5 − 0.15·2
        assert ob.zone_hi == pytest.approx(99.1)     # 98.8 + 0.15·2
        assert ob.displacement_multi == pytest.approx(4.8 / 2.0)
        assert ob.vol_ratio == pytest.approx(2.0)
        # creation-time quality (the scenario later walks the OB through
        # RETESTED → MITIGATED → INVALIDATED, ending at QX)
        formed = [e for e in res["events"] if e["code"] == "EV_OBK_001"
                  and e.get("ob") == ob.oid]
        assert formed and formed[0]["quality"] == "Q3"   # Context ∧ BOS
        codes = [e["code"] for e in res["events"]]
        assert "EV_OBK_001" in codes and "EV_OBK_002" in codes

    def test_retest_mitigated_invalidated_breaker_chain(self):
        res, bars = _run_scenario(vr_override={6: 2.0})
        codes = [e["code"] for e in res["events"]]
        assert "EV_OBK_003" in codes     # RETESTED at bar 12
        assert "EV_OBK_004" in codes     # MITIGATED at bar 13
        assert "EV_OBK_005" in codes     # INVALIDATED at bar 14
        assert "EV_OBK_007" in codes     # BREAKER reclaim at bar 15
        breaker = [o for o in res["obs"] if o.otype == "BREAKER"]
        assert breaker and breaker[0].direction == "DOWN"
        assert breaker[0].zone_lo == pytest.approx(98.2)
        assert breaker[0].zone_hi == pytest.approx(99.1)
        assert breaker[0].quality == "Q3"
        original = [o for o in res["obs"]
                    if o.oid == "ob_18000000_5_UP"][0]
        assert breaker[0].salience == pytest.approx(
            original.salience * 0.9)
        # fate ladder walked in order on the original OB
        retested = [e for e in res["events"] if e["code"] == "EV_OBK_003"]
        assert retested[0]["ob"] == "ob_18000000_5_UP"

    def test_no_structure_caps_below_q3(self):
        res, _ = _run_scenario(vr_override={6: 2.0}, struct=False)
        obs = [o for o in res["obs"] if o.origin_idx == 5]
        assert obs and obs[0].quality != "Q3"
        assert obs[0].structural_event == "NONE"

    def test_low_volume_caps_at_q1(self):
        # VR 1.1 < θ_vol ⇒ Q1 per §1.6 (fixture F02 re-derivation);
        # asserted at creation time via the EV_OBK_001 payload
        res, _ = _run_scenario(vr_override={6: 1.1})
        formed = [e for e in res["events"]
                  if e["code"] == "EV_OBK_001"
                  and e.get("ob") == "ob_18000000_5_UP"]
        assert formed and formed[0]["quality"] == "Q1"

    def test_v_zero_caps_at_q1(self):
        res, _ = _run_scenario(vr_override={6: 0.0})
        formed = [e for e in res["events"]
                  if e["code"] == "EV_OBK_001"
                  and e.get("ob") == "ob_18000000_5_UP"]
        assert formed and formed[0]["quality"] == "Q1"

    def test_expiry_at_max_age(self):
        p = get_params({"max_age_bars": 3})
        bars = _scenario_bars()
        vol, vola = _evidence(len(bars), vr_at={6: 2.0})
        eng = OrderBlockEngine(p)
        eng.run_full(bars, {5: [{"kind": "BOS", "direction": "UP",
                                 "valid_at_idx": 6}]}, {}, vol, vola)
        expired = [o for o in eng.history if o.fate == "EXPIRED"]
        assert expired and expired[0].quality == "QX"
        assert any(e["code"] == "EV_OBK_006" for e in eng.events)

    def test_flat_h_eq_l_origin_rejected(self):
        bars = _scenario_bars()
        bars[5] = {"o": 100, "h": 100, "l": 100, "c": 100, "v": 0,
                   "ts": 5 * 3600000}          # fixture F07 shape
        vol, vola = _evidence(len(bars), vr_at={6: 2.0})
        eng = OrderBlockEngine()
        eng.run_full(bars, {5: [{"kind": "BOS", "direction": "UP",
                                 "valid_at_idx": 6}]}, {}, vol, vola)
        assert not [o for o in eng.active_obs + eng.history
                    if o.origin_idx == 5]

    def test_width_floor_property_of_asymmetric_zone(self):
        # §2.6 zone width = body-excess + 2·θ_tol·ATR ≥ 0.3·ATR, hence
        # the θ_minW=0.15 floor can never reject a well-formed zone —
        # asserted as the documented geometric property (§3.2)
        p = get_params()
        for o, h, l, c in ((100.5, 103, 98.5, 98.8),
                           (620.0, 625, 619.5, 624.5),
                           (50, 50.4, 49.9, 50.1)):
            bar = {"o": o, "h": h, "l": l, "c": c}
            for atr in (0.5, 2.0, 100.0):
                lo, hi = asymmetric_zone("UP", bar, atr, p.zone_tol)
                assert hi - lo >= p.min_width_atr * atr
                lo_d, hi_d = asymmetric_zone("DOWN", bar, atr, p.zone_tol)
                assert hi_d - lo_d >= p.min_width_atr * atr


# ---------------------------------------------------------------------------
# §2.8 wrong-side approach never counts (engine level)
# ---------------------------------------------------------------------------
class TestWrongSideNoStateChange:
    def test_approach_from_below_up_zone_ignored(self):
        eng = OrderBlockEngine()
        ob = ob_from_fixture({"oid": "ob_ws", "direction": "UP",
                              "zone_lo": 100.0, "zone_hi": 102.0,
                              "origin_ts": 0, "origin_idx": 0})
        ob.fate = "ACTIVE"
        eng.active_obs = [ob]
        eng.bars = [{"ts": 0, "o": 98, "h": 99, "l": 97, "c": 98},
                    {"ts": 1, "o": 98, "h": 101, "l": 99, "c": 100}]
        eng.atr = [1.0, 1.0]
        eng.volume_evidence = [None, None]
        eng.update_with_bar(1)
        assert ob.touch_count == 0               # no effective touch
        assert ob.fate == "ACTIVE"
        assert not any(e["code"] == "EV_OBK_003" for e in eng.events)


# ---------------------------------------------------------------------------
# §8.2 deterministic replay
# ---------------------------------------------------------------------------
class TestDeterministicReplay:
    def test_double_run_identical_canonical_hash(self):
        bars = _scenario_bars()
        vol, vola = _evidence(len(bars), vr_at={6: 2.0})
        struct = {5: [{"kind": "BOS", "direction": "UP",
                       "valid_at_idx": 6}]}

        def once():
            eng = OrderBlockEngine()
            return eng.run_full(bars, struct, {}, vol, vola), eng

        obs1, eng1 = once()
        obs2, eng2 = once()
        h1 = canonical_hash([o.to_canonical() for o in obs1])
        h2 = canonical_hash([o.to_canonical() for o in obs2])
        assert h1 == h2 and obs1
        ids1 = sorted(o.snapshot_id for o in obs1)
        ids2 = sorted(o.snapshot_id for o in obs2)
        assert ids1 == ids2
        assert all(len(s) == 64 for s in ids1)


# ---------------------------------------------------------------------------
# §8.3 no-future-leak
# ---------------------------------------------------------------------------
class GuardedList(list):
    """Raises if any index beyond max_idx is read."""

    def __init__(self, iterable, max_idx):
        super().__init__(iterable)
        self.max_idx = max_idx

    def __getitem__(self, idx):
        if isinstance(idx, int) and idx > self.max_idx:
            raise AssertionError(f"future read at idx={idx}")
        return super().__getitem__(idx)


class TestNoFutureLeak:
    def test_detect_at_reads_only_up_to_origin_plus_k(self):
        bars = _scenario_bars()
        vol, vola = _evidence(len(bars), vr_at={6: 2.0})
        eng = OrderBlockEngine()
        eng.ingest_bars(bars, vol, vola)
        origin = 5
        eng.bars = GuardedList(bars, origin + eng.p.disp_max_k)
        struct = [{"kind": "BOS", "direction": "UP", "valid_at_idx": 6}]
        ob = eng.detect_at(origin, struct, [])
        assert ob is not None
        # confirmation delayed to t+K (§2.2)
        assert ob.confirmed_at == bars[6]["ts"]
        assert ob.confirmed_at >= ob.origin_ts

    def test_truncated_future_changes_nothing_before_confirmation(self):
        bars = _scenario_bars()
        vol, vola = _evidence(len(bars), vr_at={6: 2.0})
        eng_full = OrderBlockEngine()
        eng_full.ingest_bars(bars, vol, vola)
        ob_full = eng_full.detect_at(
            5, [{"kind": "BOS", "direction": "UP", "valid_at_idx": 6}], [])
        eng_trunc = OrderBlockEngine()
        eng_trunc.ingest_bars(bars[:8], vol[:8], vola[:8])
        ob_trunc = eng_trunc.detect_at(
            5, [{"kind": "BOS", "direction": "UP", "valid_at_idx": 6}], [])
        assert ob_full.snapshot_id == ob_trunc.snapshot_id


# ---------------------------------------------------------------------------
# §8.4 ablation (mechanism-level; the doc's precision numbers are OOS
# research results and are never fabricated at runtime)
# ---------------------------------------------------------------------------
class TestAblation:
    def test_removing_each_check_lowers_or_caps_quality(self):
        full = {"origin": True, "disp_single": True, "vol_ratio": True,
                "disp_high": True, "structural": True}

        def reach(checks):
            probe = OB(oid="p", direction="UP", zone_lo=0, zone_hi=1,
                       origin_ts=0, origin_idx=0, displacement_mag=0,
                       displacement_multi=0, structural_event="NONE",
                       structural_strength=0.0, snapshot_id="0" * 64)
            return promote_quality(probe, checks).quality

        assert reach(full) == "Q3"
        no_vol = dict(full, vol_ratio=False)
        assert reach(no_vol) == "Q1"              # −VolRatio
        no_struct = dict(full, structural=False)
        assert reach(no_struct) == "Q2"           # −StructuralEvent
        no_or = dict(full, disp_high=False, fvg_same=False)
        assert reach(no_or) == "Q2"               # −FVG_OR_DispHigh
        no_origin = dict(full, origin=False, disp_single=False)
        assert reach(no_origin) == "Q0"           # −BodyRatio/Origin

    def test_asymmetric_zone_tighter_than_full_range(self):
        bar = {"o": 100.5, "h": 103, "l": 98.5, "c": 98.8}
        lo, hi = asymmetric_zone("UP", bar, atr=2.0, zone_tol=0.15)
        assert hi - lo < bar["h"] - bar["l"]      # tighter than the range


# ---------------------------------------------------------------------------
# §8.5 calibration
# ---------------------------------------------------------------------------
class TestCalibration:
    def test_promote_q4_requires_both_statistics(self):
        assert promote_q4(9, 11) is True
        # k=6 of 10: Wilson lower bound ≤ 0.5 AND binomial p = 0.377 >
        # 0.05 — neither gate passes, so no promotion
        assert promote_q4(6, 10) is False
        lo, _ = wilson_ci(6 / 10, 10)
        assert lo <= 0.5
        assert binomial_test_gt_half(6, 10) > 0.05
        # the exact binomial is the stdlib lgamma expansion
        assert binomial_test_gt_half(9, 11) == pytest.approx(
            (55 + 11 + 1) / 2048, abs=1e-12)

    def test_wilson_small_sample_contains_half(self):
        lo, hi = wilson_ci(3 / 5, 5)
        assert lo <= 0.5 <= hi   # no superiority claim on thin samples


# ---------------------------------------------------------------------------
# §8.6 redundancy / confluence
# ---------------------------------------------------------------------------
class TestRedundancyAndConfluence:
    def test_confluence_event_for_nearby_same_direction_obs(self):
        eng = OrderBlockEngine()
        ob_a = ob_from_fixture({"oid": "ob_ca", "direction": "UP",
                                "zone_lo": 100.0, "zone_hi": 104.0,
                                "origin_ts": 0, "origin_idx": 10})
        ob_b = ob_from_fixture({"oid": "ob_cb", "direction": "UP",
                                "zone_lo": 100.8, "zone_hi": 104.8,
                                "origin_ts": 0, "origin_idx": 11})
        eng.active_obs = [ob_a, ob_b]
        eng.bars = [{"ts": 0, "o": 1, "h": 1, "l": 1, "c": 1}]
        eng.atr = [2.0]
        eng.volume_evidence = [None]
        eng._detect_confluence(0)
        conf = [e for e in eng.events if e["code"] == "EV_OBK_008"]
        assert conf and conf[0]["iou"] > get_params().confluence_iou

    def test_merge_time_window_respected(self):
        eng = OrderBlockEngine()
        ob_a = ob_from_fixture({"oid": "ob_ta", "direction": "UP",
                                "zone_lo": 100.0, "zone_hi": 104.0,
                                "origin_ts": 0, "origin_idx": 0})
        ob_b = ob_from_fixture({"oid": "ob_tb", "direction": "UP",
                                "zone_lo": 100.0, "zone_hi": 104.0,
                                "origin_ts": 0, "origin_idx": 25})
        eng.active_obs = [ob_a, ob_b]
        eng._merge_overlapping()
        assert len(eng.active_obs) == 2   # |Δidx|=25 > merge_bars=20


# ---------------------------------------------------------------------------
# §8.7 serialization compatibility (v3 read-only adapter)
# ---------------------------------------------------------------------------
class TestSerializationCompat:
    def test_v3_hl_fields_derive_zone(self):
        payload = {"oid": "ob_v3", "direction": "UP", "origin_ts": 5,
                   "origin_idx": 1, "origin_high": 102.0,
                   "origin_low": 100.0}
        ob = load_v3_adapter(payload)
        assert ob.zone_lo == 100.0 and ob.zone_hi == 102.0
        assert len(ob.snapshot_id) == 64

    def test_v3_zone_fields_direct(self):
        payload = {"oid": "ob_v3b", "direction": "DOWN", "origin_ts": 5,
                   "origin_idx": 1, "zone_lo": 10.0, "zone_hi": 12.0}
        ob = load_v3_adapter(payload)
        assert ob.zone_lo == 10.0 and ob.zone_hi == 12.0

    def test_v3_ambiguity_fails_closed(self):
        with pytest.raises(ValueError, match="E06_ADAPTER_AMBIGUOUS_QX"):
            load_v3_adapter({"oid": "x", "direction": "UP",
                             "origin_ts": 0, "origin_idx": 0})
        with pytest.raises(ValueError, match="E06_ADAPTER_AMBIGUOUS_QX"):
            load_v3_adapter({"direction": "UP", "zone_lo": 1,
                             "zone_hi": 2})

    def test_v4_payload_rejected_by_v3_adapter(self):
        with pytest.raises(ValueError, match="E06_ADAPTER_VERSION_QX"):
            load_v3_adapter({"version": "4.0.0", "oid": "x",
                             "direction": "UP", "origin_ts": 0,
                             "origin_idx": 0, "zone_lo": 1, "zone_hi": 2})


# ---------------------------------------------------------------------------
# §6 parameters (frozen literals)
# ---------------------------------------------------------------------------
class TestParameters:
    def test_frozen_defaults_match_chapter_6(self):
        assert E06_DEFAULTS["body_min"] == 0.55
        assert E06_DEFAULTS["disp_min"] == 1.5
        assert E06_DEFAULTS["disp_high"] == 1.8
        assert E06_DEFAULTS["zone_tol"] == 0.15
        assert E06_DEFAULTS["vol_min"] == 1.3
        assert E06_DEFAULTS["max_age_bars"] == 144
        assert E06_DEFAULTS["mit_activate"] == 0.5
        assert E06_DEFAULTS["min_width_atr"] == 0.15
        assert E06_DEFAULTS["inv_tol"] == 0.2
        assert E06_DEFAULTS["iou_thresh"] == 0.7
        assert E06_DEFAULTS["merge_bars"] == 20
        assert E06_DEFAULTS["disp_max_k"] == 5
        assert E06_DEFAULTS["atr_period"] == 14
        assert E06_DEFAULTS["vol_sma_period"] == 20
        assert E06_DEFAULTS["salience_weights"] == (0.35, 0.25, 0.25, 0.15)
        assert tuple(EVENT_CATALOG) == tuple(
            f"EV_OBK_{i:03d}" for i in range(1, 10))

    def test_unknown_param_and_weight_sum_rejected(self):
        with pytest.raises(ValueError, match="UNKNOWN_E06_PARAM_QX"):
            get_params({"body_min2": 0.5})
        with pytest.raises(ValueError, match="E06_SALIENCE_WEIGHTS_SUM_QX"):
            get_params({"salience_weights": (0.5, 0.5, 0.5, 0.5)})


# ---------------------------------------------------------------------------
# EngineBase binding
# ---------------------------------------------------------------------------
def _obs_window(bars):
    obs = []
    for i, b in enumerate(bars):
        ts = "2026-01-01T%02d:%02d:00.000Z" % ((i // 60) % 24, i % 60)
        obs.append(MarketObservation(
            symbol="BTCUSDT", timeframe="1h",
            open=Decimal(str(b["o"])), high=Decimal(str(b["h"])),
            low=Decimal(str(b["l"])), close=Decimal(str(b["c"])),
            volume=Decimal(str(b["v"])), oi=None, timestamp=ts,
            sequence=i, status="CLOSED"))
    return obs


class TestEngineBaseBinding:
    def test_missing_window_fails_closed(self):
        with pytest.raises(ValueError, match="MISSING_WINDOW_CONTEXT_QX"):
            E06OrderBlockEngine().compute("BTCUSDT", "1h",
                                          "2026-01-01T00:00:00Z", {})

    def test_missing_evidence_fails_closed(self):
        bars = _scenario_bars()
        with pytest.raises(ValueError, match="MISSING_EVIDENCE_QX"):
            E06OrderBlockEngine().compute(
                "BTCUSDT", "1h", "2026-01-02T00:00:00Z",
                {"window": _obs_window(bars)})

    def test_compute_emits_valid_evidence(self):
        bars = _scenario_bars()
        vol, vola = _evidence(len(bars), vr_at={6: 2.0})
        evs = E06OrderBlockEngine().compute(
            "BTCUSDT", "1h", "2026-01-02T00:00:00Z",
            {"window": _obs_window(bars),
             "struct_events_by_idx": {5: [{"kind": "BOS",
                                           "direction": "UP",
                                           "valid_at_idx": 6}]},
             "volume_evidence": vol, "volatility_evidence": vola})
        assert evs
        for ev in evs:
            ev.validate_24_fields()
            assert ev.engine_id == "E06"
            assert len(ev.snapshot_id) == 64
        up = [ev for ev in evs if ev.direction == 1]
        assert up


# ---------------------------------------------------------------------------
# T-DR-001 (E06 re-run)
# ---------------------------------------------------------------------------
class TestTDR001:
    def test_double_run_canonical_byte_identical(self):
        def run():
            bars = _scenario_bars()
            vol, vola = _evidence(len(bars), vr_at={6: 2.0})
            return run_engine(bars,
                              struct_events_by_idx={5: [{"kind": "BOS",
                                                         "direction": "UP",
                                                         "valid_at_idx": 6}]},
                              fvg_by_idx={}, volume_evidence=vol,
                              volatility_evidence=vola)

        r1, r2 = run(), run()
        c1 = canonical_hash([o.to_canonical() for o in r1["obs"]])
        c2 = canonical_hash([o.to_canonical() for o in r2["obs"]])
        assert c1 == c2 and r1["obs"]

    def test_pit_availability_boundary(self):
        from apex.identity.snapshot import governed_as_of_ms
        assert governed_as_of_ms([{"availability_time_ms": 5},
                                  {"availability_time_ms": 9}]) == 9
        with pytest.raises(ValueError):
            governed_as_of_ms([])
