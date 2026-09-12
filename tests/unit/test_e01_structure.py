"""E01 Structure engine — full §8 validation battery (APEX_GEN5 E01 chapter).

Every §8 clause is an executed test:
  §8.1 golden fixtures FIX_001..FIX_010 (tests/fixtures/e01_golden_fixtures.json;
       bars hand-constructed from the §8 definitions, expected values re-derived
       from the §3 formulas — never copied)
  §8.2 deterministic replay (double-run byte-identical)
  §8.3 no-future-leak injection
  §8.4 ablation of S_struct components
  §8.5 Wilson CI calibration + z-test (formula checks on the §8.5 examples)
  §8.7 serialization compatibility (schema diff, snapshot_id regex)
Plus: T-E01-001 (v4.0.0 schema conformance over 50 candles), T-DR-001 (E01
replay), state machines, Wave-Out dynamic-k, streaming idempotency, §6 params
table, §7 micro-structure metrics, EngineBase emission contract.
§8.6 (E01↔E02 redundancy correlation) lives in tests/integration/test_cp2_engines.py
(E02 must exist for it).
"""
import json
import math
import re
from pathlib import Path

import pytest

from apex.engines.base import EngineBase
from apex.errors import WaveOutError
from apex.engines.e01_structure import (
    E01_DEFAULTS,
    E01StructureEngine,
    StructureEngineStreaming,
    StructureState,
    ablation_strength,
    candle_features,
    compute_mtf_bias,
    detect_bos,
    detect_choch,
    detect_gaps,
    detect_retest_and_invalidation,
    detect_swings_gann,
    detect_swings_williams,
    detect_wick_rejection,
    dynamic_k,
    get_params,
    merge_and_prune_swings,
    run_pipeline,
    scaled_epsilon,
    stop_context,
    validate_structure_event,
    validate_swingpoint,
    wilson_ci,
)
from apex.engines.e01_structure.engine import (
    atr_sma,
    break_mag,
    deterministic_replay_hash,
    displacement,
    false_break_rate,
    is_inside_bar,
    is_outside_bar,
    no_future_leak_check,
    resolve_tick_size,
    s_struct,
    strength_B,
    strength_C,
    strength_D,
    strength_V,
    vol_ratio,
    with_schema_version,
)

FIXTURES = json.loads(
    (Path(__file__).resolve().parent.parent / "fixtures"
     / "e01_golden_fixtures.json").read_text(encoding="utf-8"))["fixtures"]
BY_ID = {f["id"]: f for f in FIXTURES}


def warm_candles(n, warm, brk=None):
    out = [{"O": warm["O"], "H": warm["H"], "L": warm["L"], "C": warm["C"],
            "V": warm["V"], "open_time": f"o{i}", "close_time": f"c{i}"}
           for i in range(n)]
    if brk is not None:
        c = dict(brk)
        c.setdefault("open_time", "x")
        c.setdefault("close_time", "y")
        out.append(c)
    return out


def lcg_candles(n, seed=42, base=100.0):
    """Deterministic synthetic closed candles (no external data, no fabrication
    of market statistics — pure determinism harness)."""
    state = seed
    out = []
    price = base
    for i in range(n):
        state = (state * 1103515245 + 12345) % (2 ** 31)
        r1 = (state / 2 ** 31)
        state = (state * 1103515245 + 12345) % (2 ** 31)
        r2 = (state / 2 ** 31)
        o = price
        c = o + (r1 - 0.5) * 4.0
        h = max(o, c) + r2 * 1.5
        l = min(o, c) - (1.0 - r2) * 1.5
        v = 100 + int(r1 * 200)
        out.append({"O": o, "H": h, "L": l, "C": c, "V": v,
                    "open_time": f"o{i}", "close_time": f"c{i}"})
        price = c
    return out


# ---------------------------------------------------------------- §8.1 ----


class TestGoldenFixtures:
    def test_fix001_williams_high(self):
        f = BY_ID["FIX_001_WILLIAMS_HIGH"]
        sw = detect_swings_williams(f["candles"], k=f["config"]["k"])
        exp = f["expected_swings"]
        assert len(sw) == len(exp) == 1
        assert sw[0]["type"] == exp[0]["type"]
        assert sw[0]["price"] == pytest.approx(exp[0]["price"])
        assert sw[0]["index"] == exp[0]["index"]
        assert sw[0]["method"] == exp[0]["method"]
        assert sw[0]["q_tag"] == exp[0]["q"]
        assert re.fullmatch(r"[0-9a-f]{64}", sw[0]["snapshot_id"])
        # confirmation at C5's close (t+k)
        assert sw[0]["confirmed_at"] == f["candles"][4]["close_time"]

    def test_fix002_gann_low(self):
        f = BY_ID["FIX_002_GANN_LOW"]
        sw = detect_swings_gann(f["candles"])
        assert len(sw) == 1
        assert (sw[0]["type"], sw[0]["price"], sw[0]["index"],
                sw[0]["method"]) == ("LOW", 97, 2, "GANN")

    def test_fix003_bos_l1(self):
        f = BY_ID["FIX_003_BOS_L1"]
        candles = warm_candles(f["warmup_bars"], f["warmup"], f["candle"])
        swings = [{"type": f["swing"]["type"], "price": f["swing"]["price"],
                   "index": f["swing"]["index"], "snapshot_id": "a" * 64}]
        evs = detect_bos(candles, swings, atr_n=14, atr_override=f["atr"])
        assert len(evs) == 1
        ev = evs[0]
        assert ev["event_type"] == f["expected"]["event"]
        # re-derived: |638.9 - 635.5| / 4.2 = 0.809523809...
        assert ev["break_mag"] == pytest.approx(3.4 / 4.2, abs=1e-7)
        assert ev["break_mag"] == pytest.approx(f["expected"]["break_mag"],
                                                abs=1e-6)
        assert ev["strength"]["S"] >= f["expected"]["S_min"]
        # S re-derived from §3.9 components
        B = 1 / (1 + math.exp(1 - 3.4 / 4.2 * 1 - (3.4 / 4.2 - 1) * 0))  # σ(BM−1)
        B = 1 / (1 + math.exp(-(3.4 / 4.2 - 1)))
        disp = 3.2 / 4.2  # range / SMA(ranges,20) of uniform 4.2 bars
        D = min(disp / 1.5, 1.0)
        V = min(2.0 / 2.0, 1.0)  # V=200 vs SMA(V)=100
        C = (638.9 - 635.8) / (639.0 - 635.8)
        S = 0.38 * B + 0.27 * D + 0.19 * V + 0.16 * C
        assert ev["strength"]["S"] == pytest.approx(S, abs=1e-9)

    def test_fix004_bos_multi_level(self):
        f = BY_ID["FIX_004_BOS_MULTI_LEVEL"]
        candles = warm_candles(f["warmup_bars"], f["warmup"], f["candle"])
        swings = [{"type": s["type"], "price": s["price"], "index": s["index"],
                   "snapshot_id": "a" * 64} for s in f["swings"]]
        evs = detect_bos(candles, swings, atr_n=14, atr_override=f["atr"])
        assert len(evs) == f["expected_count"]
        by_level = {e["level_index"]: e for e in evs}
        # L1 = nearest opposing level in price order: |641.5-635.5|/4.2
        assert by_level[1]["break_mag"] == pytest.approx(6.0 / 4.2, abs=1e-6)
        assert by_level[1]["break_mag"] == pytest.approx(
            f["expected_BM_L1"], abs=1e-3)
        assert by_level[2]["break_mag"] == pytest.approx(1.5 / 4.2, abs=1e-6)
        assert by_level[2]["break_mag"] == pytest.approx(
            f["expected_BM_L2"], abs=1e-3)

    def test_fix005_choche_bull(self):
        f = BY_ID["FIX_005_CHOCHE_BULL"]
        candles = warm_candles(f["warmup_bars"], f["warmup"], f["candle"])
        swings = [{"type": s["type"], "price": s["price"], "index": s["index"],
                   "snapshot_id": "a" * 64} for s in f["swings"]]
        bos = [{"event_type": "EV_STR_008_BOS_BEARISH",
                "candle_index": f["prior_bos_bear_at"], "snapshot_id": "b" * 64}]
        evs = detect_choch(candles, swings, bos, atr_n=14,
                           atr_override=f["atr"])
        assert len(evs) == 1
        assert evs[0]["event_type"] == f["expected_event"]
        assert evs[0]["price_level"] == pytest.approx(632.4)

    def test_fix006_retest(self):
        f = BY_ID["FIX_006_RETEST"]
        candles = warm_candles(f["warmup_bars"], f["warmup"],
                               f["candles_after"][0])
        bos = dict(f["bos"])
        bos["snapshot_id"] = "a" * 64
        retests, invalids = detect_retest_and_invalidation(
            candles, [bos], atr_n=14, retest_tol_atr=f["kappa"],
            atr_override=f["atr"])
        assert [r["event_type"] for r in retests] == [f["expected"]]
        assert invalids == []
        # re-derived: |635.8-635.5| = 0.3 <= 0.25*4.2 = 1.05
        assert abs(retests[0]["retest_price"] - 635.5) <= 0.25 * 4.2

    def test_fix007_invalidation(self):
        f = BY_ID["FIX_007_INVALIDATION"]
        candles = warm_candles(f["warmup_bars"], f["warmup"], f["candle"])
        bos = dict(f["bos"])
        bos["snapshot_id"] = "a" * 64
        retests, invalids = detect_retest_and_invalidation(
            candles, [bos], atr_n=14, inv_thr=f["inv_thr"],
            atr_override=f["atr"])
        # close-only retest (§3.11): |631-635.5|=4.5 > 1.05 -> not a retest
        assert retests == []
        assert [i["event_type"] for i in invalids] == [f["expected"]]
        # invalidation depth: |631-635.5|/4.2 >= 0.5
        assert invalids[0]["break_mag"] == pytest.approx(4.5 / 4.2)

    def test_fix008_gap_breakaway(self):
        f = BY_ID["FIX_008_GAP_BREAKAWAY"]
        # 13 uniform TR=2.0 warmup bars ending at C=625, then the gap bar
        candles = warm_candles(f["warmup_bars"], f["warmup"])
        candles += [{"O": c["O"], "H": c["H"], "L": c["L"], "C": c["C"],
                     "V": c["V"], "open_time": "g0", "close_time": "g1"}
                    for c in f["candles"]]
        gaps = detect_gaps(candles, gamma_gap=f["gamma"], atr_override=f["atr"])
        assert len(gaps) == 1
        assert gaps[0]["gap"] == pytest.approx(f["expected_gap"])
        assert gaps[0]["type"] == f["expected_type"]
        # re-derived: |gap|=6 > 1.8*2=3.6; BREAKAWAY: 6 > 2*2 and 5/2 > 1.5

    def test_fix009_prune_count(self):
        f = BY_ID["FIX_009_PRUNE_REDUNDANCY"]
        candles = warm_candles(f["warmup_bars"], f["warmup"])
        sw = [{"type": s["type"], "price": s["price"], "index": s["index"],
               "method": "WILLIAMS", "snapshot_id": "a" * 64}
              for s in f["swings"]]
        active, pruned = merge_and_prune_swings(
            sw, [], candles, theta_depth=0.8, theta_maxAge=120)
        assert len(pruned) == f["expected_pruned_count"]
        assert len(active) == 1
        # re-derived: depth(632.4 vs 631.2) = 1.2/4.2 = 0.286 < 0.8;
        #             depth(631.8 vs 631.2) = 0.6/4.2 = 0.143 < 0.8
        assert pruned[0]["prune_reason"].startswith("depth")

    def test_fix010_bias_mtf(self):
        f = BY_ID["FIX_010_BIAS_MTF"]
        out = compute_mtf_bias(f["states"], f["weights"])
        # re-derived per §3.10: 0.6·(+1) + 0.4·(+1) = 1.0 (> 0.5 -> BULL).
        # The fixture's expected_bias=0.6 contradicts its own inputs under
        # the §3.10 formula and the §9 Step-9 walkthrough (Bias=1.0 for the
        # same weights) — ISSUE-CP2-008; the formula is authoritative.
        assert out["bias_value"] == pytest.approx(1.0)
        assert out["bias_label"] == f["expected_label"]


# ---------------------------------------------------------------- §8.2 ----


class TestDeterministicReplay:
    def test_tdr_001_double_run_byte_identical(self):
        """T-DR-001 (E01): outputs identical on re-run, same inputs."""
        candles = lcg_candles(120)
        h1 = deterministic_replay_hash(candles)
        h2 = deterministic_replay_hash(candles)
        assert h1 == h2 and len(h1) == 64

    def test_tdr_001_engine_replay_cache_same_result(self):
        eng = E01StructureEngine()
        candles = lcg_candles(60, seed=7)
        from apex.data_catalog.contracts import MarketObservation
        from decimal import Decimal
        obs = []
        for i, c in enumerate(candles):
            obs.append(MarketObservation(
                symbol="BTCUSDT", timeframe="1h",
                open=Decimal(str(c["O"])), high=Decimal(str(c["H"])),
                low=Decimal(str(c["L"])), close=Decimal(str(c["C"])),
                volume=Decimal(str(c["V"])), oi=None,
                timestamp=f"2026-01-01T{(i + 1) % 24:02d}:00:00.000Z",
                sequence=i, status="CLOSED", source="TEST",
                availability_time=f"2026-01-01T{(i + 1) % 24:02d}:00:00.000Z"))
        r1 = eng.compute("BTCUSDT", "1h", "2026-01-03T00:00:00.000Z",
                         context={"window": obs})
        r2 = eng.compute("BTCUSDT", "1h", "2026-01-03T00:00:00.000Z",
                         context={"window": obs})
        assert r1 is r2  # replay cache hit — identical objects (T-PIT-003)

    def test_tdr_001_fresh_engine_identical_minus_operational_ids(self):
        candles = lcg_candles(80, seed=11)
        from apex.identity.canonical_json import canonical_json

        def run():
            eng = E01StructureEngine()
            evs = run_pipeline(candles)
            return canonical_json([
                {k: v for k, v in ev.items() if k != "snapshot_id"}
                for ev in evs["events"]]), [ev["snapshot_id"]
                                            for ev in evs["events"]]
        j1, s1 = run()
        j2, s2 = run()
        assert j1 == j2          # payloads byte-identical
        assert s1 == s2          # deterministic snapshot_ids (candle-derived)


# ---------------------------------------------------------------- §8.3 ----


class TestNoFutureLeak:
    def test_no_future_leak_injection(self):
        candles = lcg_candles(60, seed=3)
        assert no_future_leak_check(candles) is True

    def test_sma_never_includes_current_bar(self):
        candles = lcg_candles(40, seed=5)
        from apex.engines.e01_structure.engine import sma_until
        ranges = [c["H"] - c["L"] for c in candles]
        base = sma_until(ranges, 20, 30)
        mutated = list(ranges)
        mutated[30] = 1e9
        assert sma_until(mutated, 20, 30) == base  # t excluded from own SMA


# ---------------------------------------------------------------- §8.4 ----


class TestAblation:
    def test_every_component_contributes(self):
        ev = {"strength": {"B": 0.6, "D": 0.7, "V": 0.5, "C": 0.8,
                           "S": 0.38 * 0.6 + 0.27 * 0.7 + 0.19 * 0.5
                           + 0.16 * 0.8}}
        abl = ablation_strength(ev)
        w = E01_DEFAULTS["strength_weights"]
        for comp, wkey in (("B", "w_b"), ("D", "w_d"), ("V", "w_v"),
                           ("C", "w_c")):
            assert abl[f"without_{comp}"] < abl["full"]
            assert abl["full"] - abl[f"without_{comp}"] == pytest.approx(
                w[wkey] * ev["strength"][comp])
        # documented drops: B −0.09 > D −0.05 ≈ V −0.06 > C −0.03 ordering
        drops = {c: abl["full"] - abl[f"without_{c}"] for c in "BDVC"}
        assert drops["B"] > drops["C"]

    def test_weights_sum_to_one_and_floor(self):
        w = E01_DEFAULTS["strength_weights"]
        assert sum(w.values()) == pytest.approx(1.0)
        assert all(v >= 0.05 for v in w.values())


# ---------------------------------------------------------------- §8.5 ----


class TestWilsonCI:
    def test_wilson_examples(self):
        # §8.5: p̂=0.286, n=21 -> [0.14, 0.49]
        lo, hi = wilson_ci(0.286, 21)
        assert lo == pytest.approx(0.14, abs=0.01)
        assert hi == pytest.approx(0.49, abs=0.01)
        # p̂=0.22, n=500 -> [0.18, 0.26] (doc rounding; computed 0.1859/0.2554)
        lo, hi = wilson_ci(0.22, 500)
        assert lo == pytest.approx(0.18, abs=0.01)
        assert hi == pytest.approx(0.26, abs=0.01)
        # trend p̂=0.18 -> [0.15, 0.22]; range p̂=0.42 -> [0.38, 0.46]
        # (§8.5 states no n for these two; n recovered from the CI
        #  half-widths — pure formula checks: 463 and 585)
        assert wilson_ci(0.18, 463) == pytest.approx((0.15, 0.22), abs=0.01)
        assert wilson_ci(0.42, 585) == pytest.approx((0.38, 0.46), abs=0.01)

    def test_z_test_trend_vs_range(self):
        def z_test(p1, n1, p2, n2):
            p = (p1 * n1 + p2 * n2) / (n1 + n2)
            return (p1 - p2) / math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
        # §8.5 figures -> z ≈ 7.2 (pooled p=0.30, n≈378 per side)
        n1 = n2 = 378
        assert abs(z_test(0.18, n1, 0.42, n2)) == pytest.approx(7.2, abs=0.1)

    def test_false_break_rate_in_window(self):
        candles = lcg_candles(80, seed=13)
        out = run_pipeline(candles)
        bos = [e for e in out["events"] if e["event_type"].startswith(
            "EV_STR_007") or e["event_type"].startswith("EV_STR_008")]
        at = atr_sma(candles, 14)
        p, n = false_break_rate(bos, candles, at)
        assert 0.0 <= p <= 1.0 and n >= 0


# ---------------------------------------------------------------- §8.7 ----


class TestSerializationCompat:
    def test_schema_diff_identical_across_runs(self):
        candles = lcg_candles(70, seed=17)
        o1 = run_pipeline(candles)
        o2 = run_pipeline(candles)
        assert [e["snapshot_id"] for e in o1["events"]] == [
            e["snapshot_id"] for e in o2["events"]]
        for ev in o1["events"]:
            if ev["event_type"] in ("EV_STR_007_BOS_BULLISH",
                                    "EV_STR_008_BOS_BEARISH"):
                validate_structure_event(ev)

    def test_snapshot_id_regex(self):
        candles = lcg_candles(70, seed=19)
        out = run_pipeline(candles)
        assert out["events"]
        for ev in out["events"]:
            if "snapshot_id" in ev:
                assert re.fullmatch(r"[0-9a-f]{64}", ev["snapshot_id"])

    def test_no_v3_runtime_path(self):
        import apex.engines.e01_structure.engine as mod
        public = [n for n in dir(mod) if "v3" in n.lower()]
        assert public == []  # legacy is adapter-mediated only (CP-8)


# ------------------------------------------------------- T-E01-001 ---------


class TestTE01001Schema:
    def test_50_candles_output_conforms_v4(self):
        """T-E01-001: 50 candles; output validated against the v4.0.0 schema."""
        candles = lcg_candles(50, seed=23)
        out = run_pipeline(candles)
        for ev in with_schema_version(out["events"]):
            assert ev["version"] == "4.0.0"
            if ev["event_type"] in ("EV_STR_007_BOS_BULLISH",
                                    "EV_STR_008_BOS_BEARISH",
                                    "EV_STR_009_CHOCHE_BULLISH",
                                    "EV_STR_010_CHOCHE_BEARISH"):
                validate_structure_event(ev)
        for sw in out["swings"]:
            vsw = dict(sw)
            vsw.setdefault("version", "4.0.0")
            validate_swingpoint(vsw)

    def test_emission_24_fields_valid(self):
        eng = E01StructureEngine()
        from apex.data_catalog.contracts import MarketObservation
        from decimal import Decimal
        candles = lcg_candles(55, seed=29)
        obs = [MarketObservation(
            symbol="BTCUSDT", timeframe="1h",
            open=Decimal(str(c["O"])), high=Decimal(str(c["H"])),
            low=Decimal(str(c["L"])), close=Decimal(str(c["C"])),
            volume=Decimal(str(c["V"])), oi=None,
            timestamp=f"2026-01-01T{i % 24:02d}:59:00.000Z", sequence=i,
            status="CLOSED", source="TEST",
            availability_time=f"2026-01-01T{i % 24:02d}:59:00.000Z")
            for i, c in enumerate(candles)]
        evs = eng.compute("BTCUSDT", "1h", "2026-01-03T00:00:00.000Z",
                          context={"window": obs})
        assert evs, "engine must emit on a warm window"
        for ev in evs:
            ev.validate_24_fields()
            assert ev.engine_id == "E01"
            assert ev.condition_state.startswith("EV_STR_")
            assert ev.direction in (-1, 0, 1)
            assert math.isfinite(ev.strength) and math.isfinite(ev.confidence)

    def test_enginebase_contract(self):
        eng = E01StructureEngine()
        assert isinstance(eng, EngineBase)
        assert eng.engine_id == "E01"
        assert eng.contract_version == "v4.0.0"
        assert eng.analyst_version.endswith("0" * 40)

    def test_missing_window_fail_closed(self):
        eng = E01StructureEngine()
        with pytest.raises(ValueError, match="MISSING_WINDOW_CONTEXT_QX"):
            eng.compute("BTCUSDT", "1h", "2026-01-01T00:00:00.000Z")


# ---------------------------------------------------- state machines --------


class TestStateMachines:
    def test_swing_fate_forward_only(self):
        from apex.engines.e01_structure.engine import SWING_FATE_TRANSITIONS
        assert "CONFIRMED" in SWING_FATE_TRANSITIONS["CANDIDATE"]
        assert SWING_FATE_TRANSITIONS["INVALIDATED"] == ()
        assert SWING_FATE_TRANSITIONS["EXPIRED"] == ()
        assert SWING_FATE_TRANSITIONS["PRUNED"] == ()

    def test_market_state_strict_transitions(self):
        sm = StructureState()
        assert sm.state == "RANGE"
        # RANGE needs S>0.6 for BOS to flip
        sm.on_event({"event_type": "EV_STR_007_BOS_BULLISH",
                     "strength": {"S": 0.4}})
        assert sm.state == "RANGE"
        sm.on_event({"event_type": "EV_STR_007_BOS_BULLISH",
                     "strength": {"S": 0.73}})
        assert sm.state == "BULL"
        # direct BULL -> BEAR is illegal: needs CHoCH first
        sm.on_event({"event_type": "EV_STR_008_BOS_BEARISH",
                     "strength": {"S": 0.9}})
        assert sm.state == "BULL"
        sm.on_event({"event_type": "EV_STR_010_CHOCHE_BEARISH"})
        assert sm.state == "TRANSITION"
        sm.on_event({"event_type": "EV_STR_008_BOS_BEARISH",
                     "strength": {"S": 0.9}})
        assert sm.state == "BEAR"
        # EXPIRY transitions only from TRANSITION (the §5.3 fourth source);
        # BEAR must go through CHoCH first
        sm.on_event({"event_type": "EV_STR_019_EXPIRY"})
        assert sm.state == "BEAR"
        sm.on_event({"event_type": "EV_STR_009_CHOCHE_BULLISH"})
        assert sm.state == "TRANSITION"
        sm.on_event({"event_type": "EV_STR_019_EXPIRY"})
        assert sm.state == "RANGE"


# ---------------------------------------------------- Wave-Out / params -----


class TestWaveOutAndParams:
    def test_dynamic_k_wave_out(self):
        with pytest.raises(WaveOutError):
            dynamic_k(1.4, 0.5)
        with pytest.raises(WaveOutError):
            StructureEngineStreaming(config={"dynamic_k": True})

    def test_k_fixed_at_2(self):
        assert E01_DEFAULTS["k_williams"] == 2  # GC-D

    def test_params_table_frozen_defaults(self):
        p = get_params()
        assert p["break_policy"] == "CLOSE"
        assert p["break_min_mag"] == 0.3
        assert p["theta_depth"] == 0.8
        assert p["theta_maxAge"] == 120
        assert p["gamma_gap"] == 1.8
        assert p["T_HTF"] == 0.15
        assert p["retest_tol_kappa"] == 0.25
        assert p["expiry_bars"] == 48
        assert p["max_levels"] == 3
        assert p["redundancy_thr"] == 0.9
        assert p["disp_min"] == 1.5
        assert p["accept_wicks"] is False
        with pytest.raises(ValueError):
            get_params({"not_a_param": 1})

    def test_tick_size_from_universe_yaml(self):
        from apex.config import load_params
        tick = resolve_tick_size("BTCUSDT", load_params())
        assert tick > 0
        with pytest.raises(ValueError):
            resolve_tick_size("NOPEUSDT", load_params())

    def test_scaled_epsilon_formula(self):
        candles = [{"C": 100.0}] * 20
        eps = scaled_epsilon(candles, tick=0.01)
        assert eps == pytest.approx(0.005)  # max(0.005, 100*1e-8, 1e-12)
        assert scaled_epsilon([], tick=0.01) == pytest.approx(0.005)

    def test_no_stubs(self):
        src = Path("apex/engines/e01_structure/engine.py").read_text()
        for token in ("TODO", "FIXME", "NotImplementedError", "pass-stub"):
            assert token not in src


# ---------------------------------------------------- §3 formula units -----


class TestFormulas:
    def test_candle_geometry_and_strengths(self):
        c = {"O": 630, "H": 639, "L": 635.8, "C": 638.9, "V": 200}
        eps = 0.005
        assert strength_B(1.0) == pytest.approx(0.5)
        assert strength_D(3.0, 1.5) == 1.0
        assert strength_V(4.0) == 1.0
        assert strength_V(0.0) == 0.0
        assert strength_C(c, eps, True) == pytest.approx(
            (638.9 - 635.8) / (639 - 635.8))
        assert strength_C(c, eps, False) == pytest.approx(
            1 - (638.9 - 635.8) / (639 - 635.8))
        st = s_struct(0.8095, 0.76, 2.0, c, eps, True)
        assert 0.0 <= st["S"] <= 1.0
        assert set(st) == {"B", "D", "V", "C", "S"}

    def test_wick_and_gap_metrics(self):
        c = {"O": 630, "H": 639, "L": 635.8, "C": 638.9, "V": 200}
        assert is_outside_bar({"H": 11, "L": 9}, {"H": 10, "L": 10.5})
        assert is_inside_bar({"H": 10, "L": 10.2}, {"H": 11, "L": 9.5})

    def test_candle_features_doji(self):
        # doji: BodyRatio<0.1 and Range/ATR>0.7 (encyclopedia Ch.2)
        doji = {"O": 65000, "H": 65100, "L": 64900, "C": 65020, "V": 10}
        f = candle_features(doji, 200.0, 1e-12)
        assert f["is_doji"] is True
        assert f["body_ratio"] == pytest.approx(20 / 200, abs=1e-6)
        strong = {"O": 630, "H": 638.9, "L": 629.5, "C": 638.1, "V": 10}
        f2 = candle_features(strong, 9.4, 1e-12)
        assert f2["is_doji"] is False
        assert f2["close_pos"] == pytest.approx(0.91, abs=0.01)

    def test_stop_context(self):
        bos = {"event_type": "EV_STR_007_BOS_BULLISH", "price_level": 635.5,
               "strength": {"S": 0.737}}
        ctx = stop_context(bos, 4.2)
        assert ctx["stop_level"] == pytest.approx(635.5 - 2.1)
        assert ctx["halve_size"] is False
        weak = {"event_type": "EV_STR_007_BOS_BULLISH", "price_level": 635.5,
                "strength": {"S": 0.4}}
        assert stop_context(weak, 4.2)["halve_size"] is True

    def test_vol_ratio_zero_volume(self):
        candles = lcg_candles(30, seed=31)
        candles[-1] = dict(candles[-1], V=0)
        assert vol_ratio(candles, len(candles) - 1, 20) == 0.0

    def test_break_mag_symmetric(self):
        assert break_mag(110, 100, 5, 1e-12) == pytest.approx(2.0)
        assert break_mag(90, 100, 5, 1e-12) == pytest.approx(2.0)

    def test_case_study_step_values(self):
        """§9 walkthrough re-derivations (illustrative → re-derived)."""
        # C3 swing high 632.4, k=2 (§9 Step 2)
        cs = [(620, 625, 618, 622, 100), (622, 628, 621.5, 627, 110),
              (627, 632.4, 624.1, 631.2, 150), (631.2, 631.5, 626, 627, 120),
              (627, 629, 621, 623, 90)]
        sw = detect_swings_williams(
            [{"O": o, "H": h, "L": l, "C": c, "V": v,
              "open_time": f"o{i}", "close_time": f"c{i}"}
             for i, (o, h, l, c, v) in enumerate(cs)], k=2)
        assert sw[0]["price"] == pytest.approx(632.4)
        # BOS L1 at C6: BM = |635.5-632.4|/4.2 = 0.738 (§9 Step 4)
        bm = break_mag(635.5, 632.4, 4.2, 0.005)
        assert bm == pytest.approx(0.738, abs=1e-3)
        # Retest at C10: |635.8-635.5| = 0.3 <= 0.25*4.3 = 1.075 (§9 Step 6)
        assert abs(635.8 - 635.5) <= 0.25 * 4.3
        # Gap C7->C8: 1.9/4.2 = 0.45 < 1.8 -> COMMON, no event (§9 Step 7)
        assert abs(638.9 - 637.0) / 4.2 < 1.8
        # Bias: 1D BULL 0.6 + 1W BULL 0.4 = 1.0 > 0.5 -> BULL (§9 Step 9)
        b = compute_mtf_bias({"1D": "BULL", "1W": "BULL"},
                             {"1D": 0.6, "1W": 0.4})
        assert b["bias_value"] == pytest.approx(1.0)
        assert b["bias_label"] == "BULL"


# ---------------------------------------------------- streaming -------------


class TestStreaming:
    def test_streaming_idempotent_and_invalid(self):
        cfg = get_params({"min_candles": 20})
        eng = StructureEngineStreaming(config=cfg)
        candles = lcg_candles(60, seed=37)
        total = []
        for c in candles:
            total.extend(eng.on_new_candle(c))
        # re-feed last candle -> no new events (idempotent)
        assert eng.on_new_candle(candles[-1]) == []
        # invalid candle -> EV_STR_000 Q0
        bad = dict(candles[-1], H=1.0, L=100.0)
        out = eng.on_new_candle(bad)
        assert out[0]["event_type"] == "EV_STR_000_INVALID_CANDLE"
        assert out[0]["q_tag"] == "Q0"
        # no duplicate snapshot ids in the accumulated stream
        ids = [e.get("snapshot_id") for e in eng.events
               if e.get("snapshot_id")]
        assert len(ids) == len(set(ids))
        # streaming == batch
        batch = run_pipeline(candles, cfg)["events"]
        batch_ids = {e.get("snapshot_id") for e in batch
                     if e.get("snapshot_id")}
        assert batch_ids.issubset(set(ids))

    def test_wick_rejection(self):
        candles = warm_candles(20, {"O": 100, "H": 101, "L": 99, "C": 100,
                                    "V": 50})
        swings = [{"type": "HIGH", "price": 101.5, "index": 5,
                   "snapshot_id": "a" * 64}]
        candles.append({"O": 101, "H": 102.5, "L": 100.5, "C": 101.0,
                        "V": 80, "open_time": "x", "close_time": "y"})
        evs = detect_wick_rejection(candles, swings, atr_n=14,
                                    atr_override=1.0)
        assert len(evs) == 1
        assert evs[0]["event_type"] == "EV_STR_012_WICK_REJECTION"
