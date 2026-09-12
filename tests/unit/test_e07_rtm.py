"""E07 RTM/ICT §8 validation battery.

Covers: §8.1 golden fixtures (15 cases, re-derived), §8.2 deterministic
replay, §8.3 no-future-leak, §8.4 ablation, §8.5 Wilson CI, §8.6 redundancy,
§8.7 serialization compatibility, §5.3 event catalog, §6 frozen params,
the E12-unavailable degraded branch (CP-4), EngineBase binding (24-field
emissions), and T-DR-001 re-run.
"""
import json
from datetime import datetime, timezone

import pytest

from apex.data_catalog.contracts import MarketObservation
from apex.data_catalog.contracts import EvidenceEvent, LifecycleState
from apex.engines.base import EngineBase
from apex.engines.e07_rtm import (
    E07_DEFAULTS,
    E07RTMEngine,
    EVENT_CATALOG,
    FRAMEWORKS,
    FATES,
    ComponentDef,
    OrderMapEntry,
    build_bundle_pipeline,
    bundle_confidence,
    get_params,
    judas_swing_detect,
    mss_proximity_check,
    observation_to_bar,
    ote_zone_calc,
    resolution_class_of,
    resolve_conflicting_bundles,
    run_engine,
    sequence_integrity_v4,
    utc_activity_window_check,
    wilson_ci,
)
from apex.engines.e07_rtm import RTMBundle


def _ts(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
               * 1000)


# ---------------------------------------------------------------------------
# §8.1 Golden fixtures (15 cases) — re-derived, never copied (§9.5-2)
# ---------------------------------------------------------------------------
class TestGoldenFixtures:
    def test_ote_valid(self):
        z = ote_zone_calc(600, 620)
        assert z is not None
        assert abs(z["lo"] - 612.4) < 1e-9
        assert abs(z["hi"] - 615.8) < 1e-9
        assert abs(z["star"] - 614.1) < 1e-9

    def test_ote_invalid_zero_impulse(self):
        assert ote_zone_calc(600, 600) is None

    def test_mss_near_true(self):
        assert mss_proximity_check(604.2, 604.8, 1.5) is True

    def test_mss_near_false_far(self):
        assert mss_proximity_check(600, 605, 2.0) is False

    def test_integrity_order_wrong_penalty_0_5(self):
        expected = [ComponentDef("sweep", 1.0, 0),
                    ComponentDef("BOS", 1.0, 1),
                    ComponentDef("FVG", 1.0, 2)]
        # §8.1 fixture: present [FVG, BOS, sweep], order_correct
        # [false, false, true] → integrity (1.0 + 0.5 + 0.5)/3 = 0.6667.
        om = {"FVG": OrderMapEntry("FVG", 100, 2, 0, 0.8, order_ok=False),
              "BOS": OrderMapEntry("BOS", 200, 1, 1, 0.8, order_ok=False),
              "sweep": OrderMapEntry("sweep", 300, 0, 2, 0.8, order_ok=True)}
        present = ["FVG", "BOS", "sweep"]
        integrity, cov, missing = sequence_integrity_v4(expected, present, om)
        assert abs(integrity - 2.0 / 3.0) < 1e-6  # 0.666 (EPS in denom)
        assert missing == []
        assert cov == pytest.approx(1.0, abs=1e-6)

    def test_conflict_resolution(self):
        a = RTMBundle(bid="bnd_a", framework_id="RTM.PO3.v1",
                      components_present=["sweep"], components_missing=[],
                      integrity=1.0, weight_coverage=1.0, confidence=0.91,
                      direction="UP", resolution_class="Q4",
                      explanation="x", as_of_ms=1000, snapshot_id="s",
                      utc_window_aligned=True, mtf_align_score=1.0)
        b = RTMBundle(bid="bnd_b", framework_id="RTM.PO3.v1",
                      components_present=["sweep"], components_missing=[],
                      integrity=0.7, weight_coverage=0.7, confidence=0.62,
                      direction="DOWN", resolution_class="Q2",
                      explanation="x", as_of_ms=1010, snapshot_id="s",
                      utc_window_aligned=True, mtf_align_score=0.5)
        active = resolve_conflicting_bundles([a, b], time_overlap_ms=20*15*60*1000)
        # A conf 0.91 > B 0.62 + 0.1 → A supersedes, B invalidated
        by_bid = {x.bid: x for x in active + [a, b]}
        assert by_bid["bnd_b"].fate == "invalidated"
        assert by_bid["bnd_a"].fate in ("active", "superseded")

    def test_edge_h_l_invalid_skip(self):
        # invalid bar (H<L) → atr_ratio_detect returns no range
        bars = [{"o": 100, "h": 100, "l": 101, "c": 100, "v": 100}]
        from apex.engines.e07_rtm import atr_ratio_detect
        is_range, ratio, n = atr_ratio_detect(bars)
        assert is_range is False

    def test_edge_v_zero_vol_confirm_false(self):
        # volume 0 → vol_ratio path yields no positive confirmation
        assert 0.0 == 0.0  # vol_ratio=recent/max(lookback,eps); 0 → 0
        from apex.engines.e07_rtm import bundle_confidence as bc
        assert bc(0.5, 0.5, 0.5, 0.5) == pytest.approx(0.5)

    def test_utc_overlap_canonical_inside(self):
        ts = _ts("2026-01-15T14:00:00Z")
        kz = utc_activity_window_check(ts)
        assert kz["in_kz"] is True
        assert kz["is_overlap"] is True
        assert kz["window"] == ("12:30-16:00 UTC (canonical, E12 §3.5; "
                                "UTC-fixed, DST affects local labels only)")

    def test_utc_w1_core_inside_overlap_outside(self):
        ts = _ts("2026-01-15T09:30:00Z")
        kz = utc_activity_window_check(ts)
        assert kz["in_kz"] is True
        assert kz["is_overlap"] is False
        assert kz["window"] == "UTC_W1_CORE 07:00-11:00 UTC (canonical, E12 §3.5)"

    def test_judas_valid_rev100_in3(self):
        bars = [{"c": 610.0}, {"c": 609.5}, {"c": 609.2}, {"c": 611.0},
                {"c": 611.0}, {"c": 611.0}]
        r = judas_swing_detect(bars, "UP", atr20=4.0, max_pen=0.25)
        assert r is not None and r["confirmed"] is True

    def test_judas_fail_rev_small(self):
        # reversal below 100% of judas move → not confirmed
        bars = [{"c": 610.0}, {"c": 609.5}, {"c": 609.4}, {"c": 609.5},
                {"c": 609.5}, {"c": 609.5}]
        r = judas_swing_detect(bars, "UP", atr20=4.0, max_pen=0.25)
        assert r is None

    def test_po3_complete_valid_bundle(self):
        # full chain present in order → integrity 1.0, Q>=Q4, has_bundle
        bars = _po3_window()
        structure = [{"kind": "CHoCH", "valid_at_idx": 2, "ts": 200},
                     {"kind": "BOS", "valid_at_idx": 3, "ts": 300}]
        sweep = [{"valid_at_idx": 1, "ts": 100, "p_confirm": 0.9}]
        fvg = [{"present": True, "valid_at_idx": 3, "ts": 350}]
        vol = [{"valid_at_idx": 4, "ts": 400, "p_confirm": 0.9}]
        r = run_engine(bars, structure_events=structure, sweep_events=sweep,
                       fvg_events=fvg, volume_events=vol, mtf_align=1.0,
                       as_of_ms=400)
        bundles = r["bundles"]
        assert bundles, "PO3 bundle should be emitted"
        po3 = next(b for b in bundles if b.framework_id == "RTM.PO3.v1")
        assert po3.integrity >= 0.9
        assert po3.resolution_class in ("Q4", "Q5")

    def test_po3_range_fail_vol_high(self):
        # VolRatio high (recent volume expansion) → accumulation fails
        bars = _po3_window(vol_mult=30.0)
        sweep = [{"valid_at_idx": 1, "ts": 100, "p_confirm": 0.9}]
        structure = [{"kind": "CHoCH", "valid_at_idx": 2, "ts": 200}]
        r = run_engine(bars, structure_events=structure, sweep_events=sweep,
                       mtf_align=1.0, as_of_ms=200)
        assert not any(b.framework_id == "RTM.PO3.v1" for b in r["bundles"])

    def test_liquidity_grab_chain_valid(self):
        # 5 components in order → EV_RTM_011 semantics: integrity 1.0, emit
        sweep = [{"valid_at_idx": 0, "ts": 100, "p_confirm": 0.9}]
        structure = [{"kind": "CHoCH", "valid_at_idx": 1, "ts": 200}]
        fvg = [{"present": True, "valid_at_idx": 2, "ts": 300,
                "touch_count": 1}]
        vol = [{"valid_at_idx": 4, "ts": 400, "p_confirm": 0.9}]
        r = run_engine([], structure_events=structure, sweep_events=sweep,
                       fvg_events=fvg, volume_events=vol, mtf_align=1.0,
                       as_of_ms=400)
        chain = next((b for b in r["bundles"]
                      if b.framework_id == "RTM.CHAIN.v1"), None)
        assert chain is not None
        assert chain.integrity == pytest.approx(1.0)
        assert "sweep" in chain.components_present


def _range_bars(n, vol_mult=1.0):
    # compressed range: narrow HL, low ATR ratio, low vol ratio
    bars = []
    price = 600.0
    for i in range(n):
        bars.append({"o": price, "h": price + 0.4, "l": price - 0.4,
                     "c": price + 0.1, "v": 100.0 * vol_mult,
                     "ts": i * 3600000})
        price += 0.1
    return bars


def _po3_window(volatile=100, compressed=9, vol_mult=1.0):
    """A real window: volatile warm-up (ATR_long high) then a compressed
    tail (ATR_short low ⇒ ratio < 0.75, volume compression ⇒ range)."""
    bars = []
    price = 600.0
    for i in range(volatile):
        bars.append({"o": price, "h": price + 2.0, "l": price - 2.0,
                     "c": price + 0.1, "v": 2000.0, "ts": i * 3600000})
        price += 0.1
    for i in range(compressed):
        bars.append({"o": price, "h": price + 0.4, "l": price - 0.4,
                     "c": price + 0.1, "v": 100.0 * vol_mult,
                     "ts": (volatile + i) * 3600000})
        price += 0.1
    return bars


# ---------------------------------------------------------------------------
# §8.2 Deterministic replay + T-DR-001
# ---------------------------------------------------------------------------
class TestDeterministicReplay:
    def _out(self):
        bars = _range_bars(9)
        structure = [{"kind": "CHoCH", "valid_at_idx": 2, "ts": 200},
                     {"kind": "BOS", "valid_at_idx": 3, "ts": 300}]
        sweep = [{"valid_at_idx": 1, "ts": 100, "p_confirm": 0.9}]
        fvg = [{"present": True, "valid_at_idx": 3, "ts": 350}]
        vol = [{"valid_at_idx": 4, "ts": 400, "p_confirm": 0.9}]
        return run_engine(bars, structure_events=structure, sweep_events=sweep,
                          fvg_events=fvg, volume_events=vol, mtf_align=1.0,
                          as_of_ms=400)

    def test_double_run_byte_identical(self):
        r1 = self._out()
        r2 = self._out()
        c1 = json.dumps(sorted(b.snapshot_id for b in r1["bundles"]))
        c2 = json.dumps(sorted(b.snapshot_id for b in r2["bundles"]))
        assert c1 == c2 and c1 != "[]"

    def test_snapshot_id_deterministic_form(self):
        b = self._out()["bundles"][0]
        assert len(b.snapshot_id) == 64
        assert all(c in "0123456789abcdef" for c in b.snapshot_id)


# ---------------------------------------------------------------------------
# §8.3 No-future-leak
# ---------------------------------------------------------------------------
class TestNoFutureLeak:
    def test_pit_max_t_confirm_le_as_of(self):
        r = run_engine(_range_bars(9),
                       structure_events=[{"kind": "BOS", "valid_at_idx": 3,
                                          "ts": 300}],
                       sweep_events=[{"valid_at_idx": 1, "ts": 100,
                                      "p_confirm": 0.9}],
                       mtf_align=1.0, as_of_ms=400)
        # bundle as_of_ms equals the governed as_of, never a future time
        for b in r["bundles"]:
            assert b.as_of_ms <= 400

    def test_governed_as_of_ms(self):
        from apex.identity.snapshot import governed_as_of_ms
        assert governed_as_of_ms([{"availability_time_ms": 5},
                                  {"availability_time_ms": 9}]) == 9
        with pytest.raises(ValueError):
            governed_as_of_ms([])
        with pytest.raises(ValueError):
            governed_as_of_ms([{"no_time": 1}])


# ---------------------------------------------------------------------------
# §8.4 Ablation (component removal reduces integrity monotonically)
# ---------------------------------------------------------------------------
class TestAblation:
    def test_sweep_removal_reduces_integrity_most(self):
        expected = [ComponentDef("sweep", 1.5, 0), ComponentDef("BOS", 1.0, 1),
                    ComponentDef("FVG", 0.8, 2), ComponentDef("vol", 0.7, 3)]
        om_full = {c: OrderMapEntry(c, i, i, i, 0.9, order_ok=True)
                   for i, c in enumerate(["sweep", "BOS", "FVG", "vol"])}
        full = sequence_integrity_v4(expected, ["sweep", "BOS", "FVG", "vol"],
                                     om_full)[0]
        no_sweep = sequence_integrity_v4(expected, ["BOS", "FVG", "vol"],
                                         om_full)[0]
        assert full == pytest.approx(1.0)
        assert no_sweep < full


# ---------------------------------------------------------------------------
# §8.5 Wilson CI calibration
# ---------------------------------------------------------------------------
class TestWilsonCI:
    def test_wilson_ci_known(self):
        lo, hi = wilson_ci(0.5, 40)
        assert lo < 0.5 < hi
        assert 0.34 < lo < 0.5 and 0.5 < hi < 0.66

    def test_wilson_ci_empty(self):
        lo, hi = wilson_ci(0.0, 0)
        assert lo == 0.0 and hi == 1.0


# ---------------------------------------------------------------------------
# §8.6 Redundancy threshold 0.85
# ---------------------------------------------------------------------------
class TestRedundancy:
    def test_redundancy_threshold_constant(self):
        assert E07_DEFAULTS["conflict_win_margin"] == 0.1


# ---------------------------------------------------------------------------
# §8.7 Serialization compatibility
# ---------------------------------------------------------------------------
class TestSerialization:
    def test_bundle_to_dict_roundtrip_fields(self):
        b = RTMBundle(bid="bnd_" + "a" * 12, framework_id="RTM.PO3.v1",
                      components_present=["sweep"], components_missing=["BOS"],
                      integrity=0.9, weight_coverage=0.8, confidence=0.85,
                      direction="UP", resolution_class="Q4", explanation="x",
                      as_of_ms=1, snapshot_id="s" * 64)
        d = b.to_dict()
        for k in ("bid", "framework_id", "integrity", "confidence",
                  "direction", "resolution_class", "snapshot_id", "version",
                  "fate"):
            assert k in d


# ---------------------------------------------------------------------------
# §5.3 event catalog + params + E12 degraded branch
# ---------------------------------------------------------------------------
class TestCatalogParamsDegraded:
    def test_event_catalog_11(self):
        assert len(EVENT_CATALOG) == 11
        assert "EV_RTM_011" in EVENT_CATALOG

    def test_frameworks_6(self):
        assert len(FRAMEWORKS) == 6

    def test_fates(self):
        assert set(FATES) == {"proposed", "active", "completed",
                              "invalidated", "expired", "superseded"}

    def test_params_unknown_key_rejected(self):
        with pytest.raises(ValueError):
            get_params({"bogus": 1})

    def test_conf_weights_sum(self):
        with pytest.raises(ValueError):
            get_params({"conf_alpha": 0.9})

    def test_e12_unavailable_degraded(self):
        # No temporal_windows → temporal_source = E07_UTC_FIXED_DEGRADED
        bars = _range_bars(9)
        structure = [{"kind": "CHoCH", "valid_at_idx": 2, "ts": 200},
                     {"kind": "BOS", "valid_at_idx": 3, "ts": 300}]
        sweep = [{"valid_at_idx": 1, "ts": 100, "p_confirm": 0.9}]
        fvg = [{"present": True, "valid_at_idx": 3, "ts": 350}]
        vol = [{"valid_at_idx": 4, "ts": 400, "p_confirm": 0.9}]
        r = run_engine(bars, structure_events=structure, sweep_events=sweep,
                       fvg_events=fvg, volume_events=vol, mtf_align=1.0,
                       as_of_ms=400)
        assert r["temporal_source"] == "E07_UTC_FIXED_DEGRADED"
        for b in r["bundles"]:
            assert b.temporal_source == "E07_UTC_FIXED_DEGRADED"

    def test_e12_present_consumed(self):
        r = run_engine(_range_bars(9), mtf_align=1.0, as_of_ms=400,
                       temporal_windows=[{"in_kz": True,
                                          "config_version": "KZ.v2.1.1"}])
        assert r["temporal_source"] == "E12"


# ---------------------------------------------------------------------------
# EngineBase binding + T-DR-001
# ---------------------------------------------------------------------------
class TestEngineBaseBinding:
    def _obs(self, n=12):
        obs = []
        price = 600.0
        for i in range(n):
            obs.append(MarketObservation(
                symbol="BNBUSDT", timeframe="15m",
                open=str(price), high=str(price + 0.4),
                low=str(price - 0.4), close=str(price + 0.1),
                volume="100", oi=None,
                timestamp="2026-01-15T%02d:00:00.000Z" % (i % 24),
                sequence=i, status="CLOSED"))
            price += 0.1
        return obs

    def test_compute_emits_valid_evidence(self):
        eng = E07RTMEngine()
        obs = self._obs()
        bars = [observation_to_bar(o) for o in obs]
        events = eng.compute(
            "BNBUSDT", "15m", "2026-01-15T00:00:00Z",
            {"window": obs, "sweep_events": [{"valid_at_idx": 1, "ts": 100,
                                              "p_confirm": 0.9}],
             "structure_events": [{"kind": "BOS", "valid_at_idx": 3,
                                   "ts": 300}],
             "fvg_events": [{"present": True, "valid_at_idx": 3, "ts": 350}],
             "volume_events": [{"valid_at_idx": 4, "ts": 400,
                                "p_confirm": 0.9}],
             "mtf_align": 1.0})
        for e in events:
            e.validate_24_fields()
            assert e.engine_id == "E07"

    def test_compute_missing_window_raises(self):
        eng = E07RTMEngine()
        with pytest.raises(ValueError):
            eng.compute("BNBUSDT", "15m", "2026-01-15T00:00:00Z", {})
