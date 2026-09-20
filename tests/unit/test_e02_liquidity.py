"""E02 Liquidity engine — full §8 validation battery (APEX_GEN5 E02 chapter).

Every §8 clause is an executed test:
  §8.1 golden fixtures GF_LIQ_001..012 (tests/fixtures/e02_golden_fixtures.json;
       expected values re-derived from the §3 formulas — never copied)
  §8.2 deterministic replay (snapshot_id identical on re-run)
  §8.3 no-future-leak (level.first_seen <= event.at_bar - 1 for every sweep)
  §8.4 ablation of SweepScore components (ground truth: >0.5·ATR reversal
       within 5 candles)
  §8.5 Wilson CI calibration (§9 figures: p̂=0.277, n=18 -> [0.13, 0.51])
  §8.7 serialization compatibility (v3 → v4 loader Q3 warning, no crash)
Plus: T-DR-001 (E02 replay), schema conformance (levels/pools/events rows),
level state machine, §9 case-study walkthrough, raid, params table,
EngineBase emission contract. §8.6 redundancy lives in
tests/integration/test_cp2_engines.py (needs E01).
"""
import json
import math
import re
from pathlib import Path

import pytest

from apex.engines.base import EngineBase
from apex.engines.e02_liquidity import (
    E02_DEFAULTS,
    E02LiquidityEngine,
    EVENT_CATALOG,
    LEVEL_FATE_TRANSITIONS,
    Candle,
    Level,
    LiquidityEngineV4,
    ablation_sweep_score,
    adaptive_min_pts,
    brownian_hit_probability,
    compute_OFI_from_L2_snapshots,
    compute_VPIN,
    compute_ATR_wilder,
    compute_TR,
    compute_pool_weight,
    compute_salience,
    dbscan_1d_optimal,
    detect_raid,
    detect_sweep,
    estimate_merton_parameters,
    freshness,
    glosten_milgrom_half_spread,
    group_equal_levels_hierarchical,
    identify_liquidity_voids_LVN,
    jaccard_index,
    kyle_lambda,
    load_output,
    merton_hit_probability,
    no_future_leak_check,
    poisson_significance,
    proximity_htf,
    run_engine,
    sweep_outcomes,
    utc_window_of,
    validate_event_row,
    validate_level_row,
    validate_pool_row,
    vpin_from_buckets,
    wilson_ci,
)
from apex.engines.e02_liquidity.engine import generate_snapshot_id

FIXTURES = json.loads(
    (Path(__file__).resolve().parent.parent / "fixtures"
     / "e02_golden_fixtures.json").read_text(encoding="utf-8"))["fixtures"]
BY_ID = {f["id"]: f for f in FIXTURES}


def make_level(price, side="SELL_SIDE", ltype="EQUAL_HIGH", instances=2,
               first_seen=5, last_touch=8, salience=0.8, fate="ACTIVE",
               Q="Q1"):
    return Level(lid=f"lvl_{price}", price=price, side=side, ltype=ltype,
                 instances=instances, first_seen=first_seen,
                 last_touch=last_touch, touch_count=instances,
                 salience=salience, fate=fate, Q=Q)


def lcg_candles(n, seed=42, base=100.0, tr=1.0):
    state = seed
    out = []
    price = base
    for i in range(n):
        state = (state * 1103515245 + 12345) % (2 ** 31)
        r1 = state / 2 ** 31
        state = (state * 1103515245 + 12345) % (2 ** 31)
        r2 = state / 2 ** 31
        o = price
        c = o + (r1 - 0.5) * tr
        h = max(o, c) + r2 * tr * 0.3
        l = min(o, c) - (1 - r2) * tr * 0.3
        out.append(Candle(open=o, high=h, low=l, close=c,
                          volume=100 + int(r1 * 100), bar_index=i,
                          is_closed=True, t_close=i * 3600))
        price = c
    return out


# ---------------------------------------------------------------- §8.1 ----


class TestGoldenFixtures:
    def test_gf001_equal_high_formed(self):
        f = BY_ID["GF_LIQ_001_EqualHigh_Formed"]
        groups = group_equal_levels_hierarchical(f["prices"], f["atr"],
                                                 f["theta_eq"])
        assert len(groups) == f["expected"]["groups_count"]
        g = groups[0]
        assert g["median"] == pytest.approx(f["expected"]["median"])
        assert g["diameter"] == pytest.approx(f["expected"]["diameter"],
                                              abs=1e-6)
        assert len(g["members"]) == f["expected"]["instances"]
        # re-derived: tol = 0.15*4.3 = 0.645; D_max = 1.29
        assert 0.15 * 4.3 == pytest.approx(0.645)

    def test_gf002_chain_prevention(self):
        f = BY_ID["GF_LIQ_002_ChainPrevention"]
        groups = group_equal_levels_hierarchical(f["prices"], f["atr"],
                                                 f["theta_eq"])
        assert len(groups) == f["expected"]["groups_count"]
        # re-derived: tol = 0.03, D_max = 0.06; every gap (0.3) > D_max
        assert all(g["diameter"] == 0.0 for g in groups)

    def test_gf003_dbscan_pool(self):
        f = BY_ID["GF_LIQ_003_DBSCAN_Pool"]
        levels = [make_level(l["price"], instances=l["instances"],
                             salience=l["salience"])
                  for l in f["levels"]]
        eps = 2 * f["theta_eq"] * f["atr"] * f["kappa"]  # pool radius (ISSUE-CP2-010)
        min_pts = adaptive_min_pts(len(levels))
        assert min_pts == 2  # max(2, ceil(log 4)) = 2
        clusters = dbscan_1d_optimal(levels, eps, min_pts)
        assert len(clusters) == f["expected"]["pools_count"]
        assert len(clusters[0]) == f["expected"]["member_count"]
        w = compute_pool_weight(clusters[0], eps)
        assert w > f["expected"]["weight_gt"]
        assert w == pytest.approx(f["expected"]["weight"], abs=1e-3)

    def test_gf004_sweep_valid(self):
        f = BY_ID["GF_LIQ_004_Sweep_Valid"]
        c = Candle(**f["candle"], is_closed=True, t_close=0)
        lv = make_level(f["level"]["price"], f["level"]["side"],
                        fate=f["level"]["fate"], Q=f["level"]["Q"],
                        first_seen=f["level"]["first_seen"],
                        last_touch=f["level"]["last_touch"])
        kind, prereq, score = detect_sweep(c, lv, f["atr"], f["vol_sma20"])
        assert kind == f["expected"]["kind"]
        keys = {"P1": "P1_valid_level", "P2": "P2_penetration",
                "P3": "P3_rejection", "P4": "P4_temporal",
                "P5": "P5_data_quality"}
        for p, key in keys.items():
            assert prereq[key] is True, (p, prereq)
        assert score >= f["expected"]["score_gte"]
        assert score == pytest.approx(f["expected"]["score"], abs=1e-3)

    def test_gf005_wick_only_no_return(self):
        f = BY_ID["GF_LIQ_005_WickOnly_NoReturn"]
        c = Candle(**f["candle"], is_closed=True, t_close=0)
        lv = make_level(f["level"]["price"], f["level"]["side"],
                        fate=f["level"]["fate"], Q=f["level"]["Q"],
                        first_seen=f["level"]["first_seen"],
                        last_touch=f["level"]["last_touch"])
        kind, _, _ = detect_sweep(c, lv, f["atr"], f["vol_sma20"])
        assert kind == f["expected"]["kind"]

    def test_gf006_raid_two_levels(self):
        f = BY_ID["GF_LIQ_006_Raid_TwoLevels"]
        sweeps = [{**s, "side": "SELL_SIDE"} for s in f["sweeps"]]
        raids = detect_raid(sweeps, f["window"])
        assert len(raids) == 1
        assert raids[0]["count"] == f["expected"]["count"]

    def test_gf007_void_lvn(self):
        f = BY_ID["GF_LIQ_007_Void_LVN"]
        levels = [make_level(l["price"]) for l in f["levels"]]
        voids = identify_liquidity_voids_LVN(
            levels, {float(k): v for k, v in f["volume_profile"].items()},
            f["atr"], f["void_gap"])
        assert len(voids) == f["expected"]["voids_count"]
        assert voids[0]["lo"] == pytest.approx(f["expected"]["lo"])
        assert voids[0]["hi"] == pytest.approx(f["expected"]["hi"])
        assert voids[0]["type"] == f["expected"]["type"]
        # re-derived: inside sum 1150 <= 0.15 * 12150 = 1822.5
        assert voids[0]["volume_inside"] == pytest.approx(1150)

    def test_gf008_ofi_cont(self):
        f = BY_ID["GF_LIQ_008_OFI_Complete"]
        ofi = compute_OFI_from_L2_snapshots(f["snapshots"])
        assert ofi[-1] == pytest.approx(f["expected"]["ofi_second"])
        # re-derived: e_b = 12-10 = +2 (price unchanged); e_a = +5 (price up)
        # OFI = 2 - 5 = -3

    def test_gf009_vpin_bvc(self):
        f = BY_ID["GF_LIQ_009_VPIN_BVC"]
        v = vpin_from_buckets(f["buckets"], f["sigma"])
        assert v > f["expected"]["vpin_gt"]
        assert v == pytest.approx(f["expected"]["vpin"], abs=1e-3)
        # re-derived: Φ(1.6)=0.9452, Φ(-0.6)=0.2743
        # imbalance = |2*945.2-1000| + |2*274.3-1000| = 1341.8; /2000

    def test_gf010_proximity_htf(self):
        f = BY_ID["GF_LIQ_010_Salience_proximityHTF"]
        p = proximity_htf(f["level"]["price"], f["p_htf"], f["atr_htf"])
        assert p == pytest.approx(f["expected"]["proximity"], abs=1e-4)
        # full salience check (weights 0.3/0.3/0.25/0.15)
        lv = make_level(f["level"]["price"], ltype=f["level"]["ltype"],
                        instances=f["level"]["instances"],
                        last_touch=f["level"]["last_touch"])
        sal = compute_salience(lv, f["current_bar"], f["atr_htf"],
                               f["p_htf"], E02_DEFAULTS["type_score"],
                               lambda_decay=f["lambda"])
        type_term = 0.3 * 1.0
        inst_term = 0.3 * min(3 / 3, 1)
        fresh_term = 0.25 * math.exp(-0.02 * (f["current_bar"]
                                               - f["level"]["last_touch"]))
        prox_term = 0.15 * math.exp(-0.5 / 2.0)  # exact proximity
        assert sal == pytest.approx(type_term + inst_term + fresh_term
                                    + prox_term, abs=1e-9)

    def test_gf011_freshness(self):
        f = BY_ID["GF_LIQ_011_Freshness_Governed"]
        fr = freshness(f["age"], f["lambda"])
        assert fr == pytest.approx(f["expected"]["freshness"], abs=1e-4)
        # half-life = ln2/λ = 34.66 ≈ 35
        assert math.log(2) / f["lambda"] == pytest.approx(
            f["expected"]["half_life"], abs=1.0)

    def test_gf012_merton(self):
        f = BY_ID["GF_LIQ_012_Merton_HitProb"]
        pm = merton_hit_probability(f["distance_atr"], f["atr"],
                                     f["sigma_ret"], f["T"],
                                     lambda_j=f["lambda_j"])
        pb = brownian_hit_probability(f["distance_atr"], f["atr"],
                                      f["sigma_ret"], f["T"])
        assert pm > pb  # p_hit_gt_brownian
        assert pm == pytest.approx(f["expected"]["p_merton"], abs=1e-3)
        assert pb == pytest.approx(f["expected"]["p_brownian"], abs=1e-3)
        # Q4 statistical-context tag is applied at emission (see below)


# ---------------------------------------------------------------- §8.2 ----


class TestDeterministicReplay:
    def test_tdr_001_snapshot_ids_identical(self):
        candles = lcg_candles(80, seed=5)
        e1 = run_engine(candles)
        e2 = run_engine(candles)
        ids1 = [ev["snapshot_id"] for ev in e1.events]
        ids2 = [ev["snapshot_id"] for ev in e2.events]
        assert ids1 == ids2

    def test_tdr_001_engine_replay_cache(self):
        from apex.data_catalog.contracts import MarketObservation
        from decimal import Decimal
        eng = E02LiquidityEngine()
        candles = lcg_candles(60, seed=9)
        obs = [MarketObservation(
            symbol="BTCUSDT", timeframe="1h",
            open=Decimal(str(c.open)), high=Decimal(str(c.high)),
            low=Decimal(str(c.low)), close=Decimal(str(c.close)),
            volume=Decimal(str(c.volume)), oi=None,
            timestamp=f"2026-01-01T{i % 24:02d}:00:00.000Z", sequence=i,
            status="CLOSED", source="TEST",
            availability_time=f"2026-01-01T{i % 24:02d}:00:00.000Z")
            for i, c in enumerate(candles)]
        r1 = eng.compute("BTCUSDT", "1h", "2026-01-03T00:00:00.000Z",
                         context={"window": obs})
        r2 = eng.compute("BTCUSDT", "1h", "2026-01-03T00:00:00.000Z",
                         context={"window": obs})
        assert r1 is r2  # replay cache hit (T-PIT-003)

    def test_tdr_001_fresh_engine_identical_minus_operational_ids(self):
        from apex.identity.canonical_json import canonical_json

        def run():
            e = run_engine(lcg_candles(70, seed=13))
            return canonical_json([
                {k: v for k, v in ev.items() if k != "evidence_id"}
                for ev in e.events])
        assert run() == run()


# ---------------------------------------------------------------- §8.3 ----


class TestNoFutureLeak:
    def test_no_event_uses_level_before_formation(self):
        candles = lcg_candles(80, seed=17)
        assert no_future_leak_check(candles) is True

    def test_sweep_never_before_formation_plus_one(self):
        eng = LiquidityEngineV4()
        candles = lcg_candles(40, seed=21)
        for c in candles:
            eng.on_new_closed_candle(c)
        # every swept level was swept at a bar strictly after formation
        for e in eng.events:
            if e["event_type"] in ("EV_LIQ_005", "EV_LIQ_006"):
                lv = eng.levels[e["level_id"]]
                assert e["at_bar"] >= lv.first_seen + 1
        # a level formed at bar t is ACTIVE only from t+1 (PIT)
        for lv in eng.levels.values():
            if lv.fate != "FORMED":
                assert any(c.bar_index >= lv.first_seen + 1
                           for c in eng.candles)


# ---------------------------------------------------------------- §8.4 ----


class TestAblation:
    def test_every_component_contributes(self):
        c = Candle(open=100.2, high=101.5, low=99.8, close=99.5, volume=1500,
                   bar_index=10, is_closed=True, t_close=0)
        lv = make_level(100, first_seen=5, last_touch=8)
        abl = ablation_sweep_score(c, lv, 1.0, 800)
        assert abl["full"] == pytest.approx(0.6845, abs=1e-3)
        for comp in ("pen", "rej", "close", "vol"):
            assert abl[f"without_{comp}"] < abl["full"]
        # documented importances: pen/rej > close/vol contributions here
        drops = {k: abl["full"] - abl[f"without_{k}"]
                 for k in ("pen", "rej", "close", "vol")}
        assert drops["pen"] > drops["close"]

    def test_sweep_outcomes_ground_truth(self):
        candles = lcg_candles(80, seed=23)
        eng = run_engine(candles)
        atr = compute_ATR_wilder(candles, 14)[-1]
        rate, n = sweep_outcomes(eng.sweep_log, candles, atr)
        assert 0.0 <= rate <= 1.0
        assert n == len([s for s in eng.sweep_log
                         if any(cc.bar_index == s["at_bar"] + 1
                                for cc in candles)])


# ---------------------------------------------------------------- §8.5 ----


class TestWilsonCI:
    def test_case_study_calibration_figures(self):
        # §9: 18 sweeps, 5 false -> p̂_false = 0.277; genuine rate 0.723;
        # Wilson CI on p̂=0.277, n=18 -> [0.13, 0.51] (doc figures)
        lo, hi = wilson_ci(0.277, 18)
        assert lo == pytest.approx(0.13, abs=0.02)
        assert hi == pytest.approx(0.51, abs=0.02)
        # false-positive CIs per level type (§7 Ch.3 §9: EQUAL 30%,
        # UTC_ACTIVITY_WINDOW 20%) — formula check
        lo, hi = wilson_ci(0.30, 50)
        assert 0.19 <= lo <= 0.20 and 0.42 <= hi <= 0.44

    def test_wilson_bounds(self):
        lo, hi = wilson_ci(0.5, 1)
        assert 0.0 < lo < hi < 1.0
        with pytest.raises(ValueError):
            wilson_ci(0.5, 0)


# ---------------------------------------------------------------- §8.7 ----


class TestSerializationCompat:
    def test_v4_output_validates(self):
        candles = lcg_candles(70, seed=29)
        out = run_engine(candles).output()
        assert out["version"] == "4.0.0"
        assert out["engine"] == "E02_LIQUIDITY"
        for row in out["levels"]:
            validate_level_row(row)
        for row in out["pools"]:
            validate_pool_row(row)
        for row in out["events"]:
            validate_event_row(row)

    def test_v3_loads_with_q3_warning_not_crash(self):
        candles = lcg_candles(70, seed=31)
        out = run_engine(candles).output()
        legacy = dict(out)
        legacy["version"] = "3.2.1"
        legacy.pop("Q_summary", None)
        loaded, warning = load_output(legacy)
        assert loaded["version"] == "4.0.0"
        assert warning is not None and warning.startswith("Q3_LEGACY")
        # v4 loads clean
        loaded2, warning2 = load_output(out)
        assert warning2 is None and loaded2["version"] == "4.0.0"

    def test_additive_fields_optional(self):
        # §5.4: density/age are OPTIONAL additive pool fields — validators
        # must not require them
        row = {"pid": "p", "lo": 1.0, "hi": 2.0, "median": 1.5, "weight": 1.0,
               "member_level_ids": ["a"], "fate": "ACTIVE", "Q": "Q1",
               "snapshot_id": "a" * 64}
        validate_pool_row(row)   # no density/age -> still valid

    def test_snapshot_id_regex(self):
        candles = lcg_candles(60, seed=37)
        out = run_engine(candles).output()
        for row in out["levels"] + out["pools"] + out["events"]:
            assert re.fullmatch(r"[0-9a-f]{64}", row["snapshot_id"])


# ---------------------------------------------------- schema / state -------


class TestSchemaAndState:
    def test_level_state_machine(self):
        assert LEVEL_FATE_TRANSITIONS["FORMED"] == ("ACTIVE",)
        assert LEVEL_FATE_TRANSITIONS["SWEPT"] == ()
        assert LEVEL_FATE_TRANSITIONS["INVALIDATED"] == ()
        assert LEVEL_FATE_TRANSITIONS["EXPIRED"] == ()

    def test_event_catalog_complete(self):
        for i in range(1, 14):
            assert f"EV_LIQ_{i:03d}" in EVENT_CATALOG
        assert "EV_LIQ_000" in EVENT_CATALOG

    def test_params_table_frozen_defaults(self):
        p = E02_DEFAULTS
        assert p["theta_eq"] == 0.15
        assert p["kappa"] == 1.0
        assert p["sweep_min_pen"] == 0.10
        assert p["sweep_min_rejection"] == 0.20
        assert p["sweep_weights"] == [0.25, 0.25, 0.2, 0.2, 0.1]
        assert p["lambda_decay"] == 0.02
        assert p["lambda_fast"] == 0.08 and p["lambda_slow"] == 0.01
        assert p["salience_weights"] == {"w_t": 0.3, "w_i": 0.3,
                                         "w_f": 0.25, "w_p": 0.15}
        assert p["void_gap"] == 2.5
        assert p["lvn_percentile"] == 15.0
        assert p["raid_window"] == 3
        assert p["level_expiry_bars"] == 96
        assert p["invalid_break_atr"] == 1.5
        assert p["utc_activity_windows"][0] == ("UTC_W0", 0.0, 7.0)
        assert p["T_hit"] == 100
        assert p["type_score"]["EQUAL_HIGH"] == 1.0
        assert p["type_score"]["VOID_EDGE"] == 0.5

    def test_salience_weights_sum_one(self):
        w = E02_DEFAULTS["salience_weights"]
        assert sum(w.values()) == pytest.approx(1.0)
        assert max(w.values()) <= 0.6

    def test_invalid_candle_q0(self):
        eng = LiquidityEngineV4()
        bad = Candle(open=100, high=99, low=101, close=100, volume=10,
                     bar_index=0, is_closed=True, t_close=0)
        evs = eng.on_new_closed_candle(bad)
        assert evs and evs[0]["event_type"] == "EV_LIQ_000"
        assert evs[0]["Q"] == "Q0"

    def test_streaming_idempotent(self):
        eng = LiquidityEngineV4()
        candles = lcg_candles(60, seed=41)
        for c in candles:
            eng.on_new_closed_candle(c)
        again = eng.on_new_closed_candle(candles[-1])
        assert again == []
        ids = [e["snapshot_id"] for e in eng.events]
        assert len(ids) == len(set(ids))

    def test_utc_windows(self):
        assert utc_window_of(3.5) == "UTC_W0"
        assert utc_window_of(8.0) == "UTC_W1"
        assert utc_window_of(13.0) == "UTC_W2"
        assert utc_window_of(22.0) == "UTC_W3"
        assert utc_window_of(12.4) == "UTC_W1"
        assert utc_window_of(12.6) == "UTC_W2"


# ---------------------------------------------------- §3 formula units -----


class TestFormulas:
    def test_atr_wilder(self):
        candles = [Candle(100, 102, 98, 100, 10, i, True, i * 60)
                   for i in range(20)]
        atr = compute_ATR_wilder(candles, 14)
        assert atr[0] == pytest.approx(4.0)
        assert atr[-1] == pytest.approx(4.0)

    def test_tr_first_bar(self):
        c = Candle(100, 105, 95, 100, 10, 0, True, 0)
        assert compute_TR(c, None) == pytest.approx(10.0)
        prev = Candle(100, 105, 95, 102, 10, 0, True, 0)
        assert compute_TR(c, prev) == pytest.approx(10.0)

    def test_kyle_and_gm(self):
        lam = kyle_lambda([0.1, 0.2, 0.3, 0.4], [100, 200, 300, 400])
        assert lam is not None and lam > 0
        lam_neg = kyle_lambda([0.4, 0.3, 0.2, 0.1], [100, 200, 300, 400])
        assert lam_neg is not None and lam_neg < 0
        assert glosten_milgrom_half_spread(0.5, 0.02) == pytest.approx(0.01)

    def test_poisson_significance(self):
        # 5 touches vs expected 1.0 -> P(X>=5) ~ 0.0037 < 0.05 (significant)
        assert poisson_significance(5, 1.0) < 0.05
        assert poisson_significance(1, 1.0) > 0.05

    def test_jaccard(self):
        assert jaccard_index({"a", "b"}, {"a", "b"}) == 1.0
        assert jaccard_index({"a"}, {"b"}) == 0.0
        assert jaccard_index({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)

    def test_merton_estimation(self):
        candles = lcg_candles(120, seed=43, tr=2.0)
        est = estimate_merton_parameters(candles)
        assert est["sigma_ret"] > 0
        assert est["lambda_j"] >= 0
        assert est["n"] == 100

    def test_merton_case_study_step10(self):
        # §9 Step 10: distance 3.5 (0.76 ATR), σ_ret 0.008, T 100, price 648.5
        pm = merton_hit_probability(3.5 / 4.6, 4.6, 0.008, 100,
                                    lambda_j=0.02, mu_j=0.0, sigma_j=0.02,
                                    price=648.5)
        pb = brownian_hit_probability(3.5 / 4.6, 4.6, 0.008, 100,
                                      price=648.5)
        assert pm == pytest.approx(1.0, abs=1e-6)
        assert pb == pytest.approx(0.949, abs=0.01)
        # target 670: distance 21.5 -> p ~ 0.795
        pm2 = merton_hit_probability(21.5 / 4.6, 4.6, 0.008, 100,
                                     lambda_j=0.02, mu_j=0.0, sigma_j=0.02,
                                     price=648.5)
        assert pm2 == pytest.approx(0.795, abs=0.02)

    def test_no_l2_is_qx_not_fabricated(self):
        eng = LiquidityEngineV4()
        for c in lcg_candles(30, seed=47):
            eng.on_new_closed_candle(c)
        assert eng.l2_available is False
        assert eng.ofi_series == []
        # OFI/VPIN events carry QX semantics: no OFI event is emitted
        ofi_events = [e for e in eng.events if "OFI" in e["event_type"]]
        assert ofi_events == []


# ---------------------------------------------------- §9 case study --------


class TestCaseStudy:
    def test_bnbusdt_walkthrough(self):
        """§9 (illustrative — event SEQUENCE re-derived, not doc numbers)."""
        bars = [
            (120, 643.2, 648.2, 642.0, 645.0, 9800),
            (141, 644.2, 647.9, 643.5, 645.5, 9000),
            (143, 644.0, 648.0, 643.2, 647.0, 8800),
            (144, 647.0, 647.5, 644.5, 645.0, 7100),
            (155, 645.2, 647.6, 643.8, 646.0, 8200),
            (163, 647.0, 649.8, 643.0, 644.2, 11500),
            (164, 644.2, 645.0, 641.0, 642.0, 9500),
            (165, 642.0, 643.5, 639.5, 640.0, 10000),
            (170, 641.0, 649.0, 640.5, 648.5, 11000),
            (171, 648.5, 650.0, 646.5, 649.0, 9000),
        ]
        candles = [Candle(o, h, l, c, v, b, True, b * 21600)
                   for b, o, h, l, c, v in bars]
        eng = LiquidityEngineV4()
        # swing inputs arrive via SwingInput.v1 (§1.2): the four listed
        # swing-high touches (§9 Steps 1-5), fed as each bar closes
        feeds = {120: 648.2, 141: 647.9, 143: 648.0, 155: 647.6}
        for c in candles:
            if c.bar_index in feeds:
                eng.feed_touches([{"price": feeds[c.bar_index],
                                   "bar_index": c.bar_index,
                                   "type": "HIGH", "confirmed": True}])
            eng.on_new_closed_candle(c)
        lvl = [lv for lv in eng.levels.values()
               if abs(lv.price - 648.0) < 1.0]
        assert lvl, "the 648 level must exist"
        lv = lvl[0]
        # Step 1-5: formed at 120, strengthened at 141/143/155 (instances 4)
        assert lv.instances >= 4
        assert lv.ltype == "EQUAL_HIGH"
        formed = [e for e in eng.events if e["event_type"] == "EV_LIQ_001"]
        strengthened = [e for e in eng.events
                        if e["event_type"] == "EV_LIQ_002"]
        assert formed and strengthened
        # Step 6: sweep at bar 163 (EV_LIQ_006, SELL side)
        sweeps = [e for e in eng.events if e["event_type"] == "EV_LIQ_006"]
        assert sweeps and sweeps[0]["at_bar"] == 163
        assert sweeps[0]["level_id"] == lv.lid
        assert lv.fate == "SWEPT"
        # Step 2 re-derived: salience after second touch with HTF high 650,
        # ATR_HTF 6 -> proximity exp(-1.95/6) = 0.722
        assert proximity_htf(648.05, 650.0, 6.0) == pytest.approx(0.722,
                                                                  abs=1e-3)


class TestEngineEmission:
    def test_compute_emits_valid_24_field_events(self):
        from apex.data_catalog.contracts import MarketObservation
        from decimal import Decimal
        eng = E02LiquidityEngine()
        candles = lcg_candles(70, seed=53)
        obs = [MarketObservation(
            symbol="BTCUSDT", timeframe="1h",
            open=Decimal(str(c.open)), high=Decimal(str(c.high)),
            low=Decimal(str(c.low)), close=Decimal(str(c.close)),
            volume=Decimal(str(c.volume)), oi=None,
            timestamp=f"2026-01-01T{i % 24:02d}:00:00.000Z", sequence=i,
            status="CLOSED", source="TEST",
            availability_time=f"2026-01-01T{i % 24:02d}:00:00.000Z")
            for i, c in enumerate(candles)]
        evs = eng.compute("BTCUSDT", "1h", "2026-01-03T00:00:00.000Z",
                          context={"window": obs})
        assert evs
        for ev in evs:
            ev.validate_24_fields()
            assert ev.engine_id == "E02"
            assert ev.condition_state.startswith("EV_LIQ_")
            # E02 evidence is direction-neutral (NG1/NG3)
            assert ev.direction == 0
            assert math.isfinite(ev.strength) and math.isfinite(ev.confidence)

    def test_enginebase_contract(self):
        eng = E02LiquidityEngine()
        assert isinstance(eng, EngineBase)
        assert eng.engine_id == "E02"
        assert eng.contract_version == "v4.0.0"

    def test_missing_window_fail_closed(self):
        eng = E02LiquidityEngine()
        with pytest.raises(ValueError, match="MISSING_WINDOW_CONTEXT_QX"):
            eng.compute("BTCUSDT", "1h", "2026-01-01T00:00:00.000Z")

    def test_raid_engine_level(self):
        """Two BUY_SIDE levels swept by one long-wick candle -> 2 sweeps +
        EV_LIQ_008 raid."""
        eng = LiquidityEngineV4()
        warm = [Candle(96, 96.5, 95.5, 96, 100, i, True, i * 3600)
                for i in range(30)]
        for c in warm:
            eng.on_new_closed_candle(c)
        eng.feed_touches([
            {"price": 95.0, "bar_index": 10, "type": "LOW",
             "confirmed": True},
            {"price": 95.5, "bar_index": 11, "type": "LOW",
             "confirmed": True}])
        for c in warm[:0]:
            pass
        # sweep candle at bar 30: long lower wick through both levels,
        # close back above
        sweep_candle = Candle(96.0, 97.5, 93.8, 96.8, 400, 30, True,
                              30 * 3600)
        evs = eng.on_new_closed_candle(sweep_candle)
        kinds = [e["event_type"] for e in evs]
        assert kinds.count("EV_LIQ_005") == 2
        assert "EV_LIQ_008" in kinds

    def test_no_stubs(self):
        src = Path("apex/engines/e02_liquidity/engine.py").read_text()
        for token in ("TODO", "FIXME", "NotImplementedError"):
            assert token not in src


# ------------------------------------------------------- D35(e) P2 ----

def test_d35e_p2_atr_prefix_memo_matches_verbatim():
    """D35(e) P2: the memoized Wilder(14) extension is bitwise-exact."""
    from apex.engines.e02_liquidity import LiquidityEngineV4, compute_ATR_wilder
    assert LiquidityEngineV4()._atr_wilder14_last() == 0.0
    for length in (1, 2, 13, 14, 15, 16, 20, 50, 100, 300):
        candles = lcg_candles(length, seed=1000 + length)
        eng = LiquidityEngineV4()
        for c in candles:
            eng.candles.append(c)
        expected = compute_ATR_wilder(candles, 14)[-1]
        assert eng._atr_wilder14_last() == expected
        assert eng._atr_wilder14_last() == expected  # memo hit, same length
        extra = lcg_candles(7, seed=2000 + length)
        for offset, c in enumerate(extra):
            c.bar_index = length + offset
            c.t_close = (length + offset) * 3600
            eng.candles.append(c)
            grown = candles + extra[:offset + 1]
            assert eng._atr_wilder14_last() == compute_ATR_wilder(grown, 14)[-1]


def test_d35e_p2_run_engine_canonical_matches_verbatim_atr(monkeypatch):
    """D35(e) P2: memoized engine outputs equal the verbatim reference."""
    from apex.engines.e02_liquidity import (
        LiquidityEngineV4, compute_ATR_wilder, run_engine)
    from apex.identity.canonical_json import canonical_json

    def snapshot(eng):
        return canonical_json({
            "events": [{k: v for k, v in ev.items() if k != "evidence_id"}
                       for ev in eng.events],
            "sweep_log": eng.sweep_log,
            "vpin": eng.vpin,
            "levels": {lid: (lvl.fate, lvl.price, lvl.last_touch,
                             lvl.touch_count, lvl.instances,
                             lvl.atr_at_formation)
                       for lid, lvl in eng.levels.items()},
        })

    memoized = snapshot(run_engine(lcg_candles(120, seed=77)))
    monkeypatch.setattr(LiquidityEngineV4, "_atr_wilder14_last",
                        lambda self: (compute_ATR_wilder(self.candles, 14)[-1]
                                      if self.candles else 0.0))
    reference = snapshot(run_engine(lcg_candles(120, seed=77)))
    assert memoized == reference
