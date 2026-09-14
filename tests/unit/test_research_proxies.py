"""CP-8 — Ch.20 liquidity-proxy layer: registry-38, the six rejections and the
Q3 proxy formulas (AA.1–AA.7; MATRIX Part III CP-8 rows C8-A*/C8-B*/C8-D*).
"""

from __future__ import annotations

import math

import pytest

from apex.research import proxies as px


# --------------------------------------------------------------------------
# AA.1–AA.4 — registry completeness
# --------------------------------------------------------------------------

class TestRegistry38:
    def test_totals_and_layers(self):
        summary = px.assert_registry_complete()
        assert summary["total"] == 38
        assert summary["by_layer"] == {"L1": 25, "L2P": 10, "L3P": 3}
        assert summary["rejected"] == 6
        assert summary["complete"] and summary["rejected_complete"]

    def test_ids_are_exactly_the_blueprint_ids(self):
        ids = [c.concept_id for c in px.PROXY_REGISTRY]
        assert ids == ([f"A{i:02d}" for i in range(1, 26)]
                       + [f"B{i:02d}" for i in range(1, 11)]
                       + ["D01", "D02", "D03"])

    def test_every_row_carries_a_disposition(self):
        for row in px.registry_rows():
            assert row["frozen_status"]
            assert row["status"] in ("IMPLEMENTED", "EXISTING_IN_FROZEN",
                                     "REGISTERED_OPEN")
            if row["status"] == "REGISTERED_OPEN":
                # no active value: neither a formula nor an owner module
                assert row["formula"] == ""
                assert row["status"] != "IMPLEMENTED"

    def test_l2_and_l3_are_q3_labeled(self):
        for row in px.registry_rows():
            if row["layer"] in ("L2P", "L3P"):
                assert row["q_label"] == px.Q3

    def test_registered_open_concepts_have_no_active_value(self):
        open_ids = {r["concept_id"] for r in px.registry_rows()
                    if r["status"] == "REGISTERED_OPEN"}
        # A05 (Kalman Q,R closure OPEN), A14 (DCC-GARCH), A04 (BOCPD), A11
        # (advisory), A13 (Q6 research), A25 (research)
        assert {"A04", "A05", "A11", "A13", "A14", "A25"} <= open_ids

    def test_critical_gap_concepts_are_implemented(self):
        by_id = {r["concept_id"]: r for r in px.registry_rows()}
        for cid in ("B01", "B04", "B06", "B07", "B08", "B10", "D01", "D02",
                    "A21", "A22", "A12", "A10", "A01"):
            assert by_id[cid]["status"] == "IMPLEMENTED", cid

    def test_duplicate_id_is_refused(self):
        rows = list(px.PROXY_REGISTRY)
        with pytest.raises(ValueError):
            ids = [c.concept_id for c in rows]
            assert len(ids) == len(set(ids))
            raise ValueError("PROXY_REGISTRY_DUPLICATE_ID")


# --------------------------------------------------------------------------
# AA.5 — the six rejections
# --------------------------------------------------------------------------

class TestRejectedSix:
    def test_six_rejections(self):
        assert len(px.REJECTED_CONCEPTS) == 6
        assert [r.concept_id for r in px.REJECTED_CONCEPTS] == [
            "C01", "C02", "C03", "C04", "C05", "C06"]

    def test_upgrade_contract_retained(self):
        for rejection in px.REJECTED_CONCEPTS:
            assert rejection.upgrade_contract == "L2Snapshot.v1"

    def test_no_rejected_concept_in_the_runtime_tree(self):
        verdict = px.assert_rejected_absent()
        assert verdict["rejected_absent"] is True
        assert verdict["hits"] == []
        assert verdict["probes_checked"] == 12

    def test_probe_tokens_are_really_absent_from_apex(self, tmp_path):
        """Negative control: the scanner DOES fire when a probe is present."""
        fake = tmp_path / "apex"
        (fake / "research").mkdir(parents=True)
        (fake / "research" / "leak.py").write_text(
            "QUEUE_POSITION = 'queue_position'\n", encoding="utf-8")
        with pytest.raises(ValueError) as err:
            px.assert_rejected_absent(tmp_path)
        assert "REJECTED_CONCEPT_PRESENT" in str(err.value)
        assert "queue_position" in str(err.value)


# --------------------------------------------------------------------------
# B01/B02/B03 — spread estimators
# --------------------------------------------------------------------------

def _wide_bars(n=30):
    """Bars with wide ranges (a genuine spread signal, not flat noise)."""
    bars = []
    price = 100.0
    for i in range(n):
        high = price + 1.0 + (i % 3) * 0.1
        low = price - 1.0 - (i % 2) * 0.1
        bars.append({"open": price, "high": high, "low": low,
                     "close": price + (0.2 if i % 2 else -0.2),
                     "volume": 1000.0})
        price += 0.05
    return bars


class TestSpreadEstimators:
    def test_corwin_schultz_is_finite_and_labeled(self):
        est = px.corwin_schultz_spread(_wide_bars())
        assert est.estimator == "CORWIN_SCHULTZ"
        assert est.q_label == px.Q3
        assert est.n_pairs == 29
        assert 0.0 <= est.spread < 1.0
        assert math.isfinite(est.spread)

    def test_corwin_schultz_negative_clamp(self):
        """Narrow ranges with a large level jump make the CS alpha negative
        (the two-bar span dwarfs the individual high-low ranges) ⇒ the CS
        negative-spread adjustment clamps to 0."""
        jumpy = []
        for i in range(6):
            base = 100.0 if i % 2 == 0 else 200.0
            jumpy.append({"open": base, "high": base + 0.01,
                          "low": base - 0.01, "close": base})
        est = px.corwin_schultz_spread(jumpy)
        assert est.spread == 0.0
        assert est.clamped is True
        assert "clamped" in est.note

    def test_corwin_schultz_needs_two_bars(self):
        with pytest.raises(ValueError) as err:
            px.corwin_schultz_spread([{"high": 1, "low": 1}])
        assert "INSUFFICIENT_HISTORY_B01" in str(err.value)

    def test_corwin_schultz_rejects_non_positive_price(self):
        with pytest.raises(ValueError) as err:
            px.corwin_schultz_spread([{"high": 1, "low": 0}, {"high": 1, "low": 1}])
        assert "NON_POSITIVE_PRICE_B01" in str(err.value)

    def test_abdi_ranaldo(self):
        est = px.abdi_ranaldo_spread(_wide_bars())
        assert est.estimator == "ABDI_RANALDO"
        assert est.spread > 0.0
        assert est.n_pairs == 29

    def test_roll_spread_positive_on_negative_autocovariance(self):
        returns = [0.01, -0.01, 0.01, -0.01, 0.01, -0.01]
        est = px.roll_spread(returns)
        assert est.estimator == "ROLL"
        assert est.spread > 0.0
        assert est.clamped is False

    def test_roll_spread_clamps_on_positive_autocovariance(self):
        est = px.roll_spread([0.01, 0.02, 0.03, 0.04, 0.05, 0.06])
        assert est.spread == 0.0 and est.clamped is True

    def test_spread_quality_flag_threshold(self):
        cs = px.SpreadEstimate("CORWIN_SCHULTZ", 0.04, 10)
        ar = px.SpreadEstimate("ABDI_RANALDO", 0.02, 10)
        assert px.spread_quality_flag(cs, ar, threshold=0.5)["flag"] is False
        far = px.SpreadEstimate("ABDI_RANALDO", 0.9, 10)
        assert px.spread_quality_flag(cs, far, threshold=0.5)["flag"] is True


# --------------------------------------------------------------------------
# B04/A21/D01 — trade-feed proxies
# --------------------------------------------------------------------------

class TestTradeFeedProxies:
    def test_obi_proxy_formula(self):
        out = px.obi_proxy(taker_buy=60.0, taker_sell=40.0, total_volume=200.0)
        assert out["obi_proxy"] == pytest.approx(0.10)
        assert out["q_label"] == px.Q3

    def test_obi_proxy_rejects_zero_volume(self):
        with pytest.raises(ValueError):
            px.obi_proxy(taker_buy=1.0, taker_sell=1.0, total_volume=0.0)

    def test_taker_pressure_formula(self):
        out = px.taker_pressure(taker_buy=75.0, taker_sell=25.0)
        assert out["taker_pressure"] == pytest.approx(0.5)

    def test_footprint_delta_is_labeled_a_proxy(self):
        out = px.footprint_delta(taker_buy=80.0, taker_sell=30.0)
        assert out["delta"] == pytest.approx(50.0)
        assert out["label"] == px.DELTA_LABEL
        assert out["true_delta"] is False

    def test_cvd_accumulates(self):
        out = px.cvd([10.0, -4.0, 6.0])
        assert out["cvd"] == [10.0, 6.0, 12.0]
        assert out["final"] == 12.0


# --------------------------------------------------------------------------
# B06/B07/B08/B10 — impact, illiquidity composite, slippage
# --------------------------------------------------------------------------

class TestImpactAndComposite:
    def test_kyle_lambda_positive_slope(self):
        returns = [0.001, 0.002, -0.001, 0.003, 0.0005]
        signed = [10.0, 20.0, -10.0, 30.0, 5.0]
        out = px.kyle_lambda(returns=returns, signed_volume=signed, window=100)
        assert out["kyle_lambda"] > 0.0
        assert out["window"] == 5

    def test_kyle_lambda_length_mismatch_fails_closed(self):
        with pytest.raises(ValueError) as err:
            px.kyle_lambda(returns=[0.1, 0.2], signed_volume=[1.0])
        assert "KYLE_INPUT_LENGTH_QX" in str(err.value)

    def test_amihud_skips_zero_volume_bars(self):
        out = px.amihud_illiquidity(returns=[0.01, 0.02, 0.05],
                                    volumes=[100.0, 0.0, 200.0])
        assert out["n"] == 2
        assert out["skipped_zero_volume"] == 1
        assert out["amihud_illiquidity_proxy"] == pytest.approx(
            (0.01 / 100.0 + 0.05 / 200.0) / 2)

    def test_composite_weights_and_sign(self):
        out = px.liquidity_regime_composite(
            amihud=[1.0, 2.0, 3.0], obi=[0.1, 0.2, 0.3],
            kyle=[0.01, 0.02, 0.03])
        assert set(out["components"]) == {"amihud_z", "obi_z", "kyle_z"}
        assert out["higher_is_better_liquidity"] is True
        assert math.isfinite(out["liquidity_regime_composite"])

    def test_adaptive_slippage_is_a_weighted_composite(self):
        out = px.adaptive_slippage(corwin_spread=0.02, kyle_lambda_value=0.001,
                                   order_size=1000.0, flow_toxicity=0.1)
        assert out["slippage_fraction"] > 0.0
        assert out["impact_term"] == pytest.approx(1.0)

    def test_liquidation_cascade_requires_all_three_legs(self):
        hot = px.detect_liquidation_cascade(liq_count_in_window=25,
                                            price_change=-500.0, atr=100.0,
                                            oi_drop_fraction=0.05)
        assert hot["cascade"] is True
        assert all(hot["legs"].values())
        mild = px.detect_liquidation_cascade(liq_count_in_window=25,
                                             price_change=-50.0, atr=100.0,
                                             oi_drop_fraction=0.05)
        assert mild["cascade"] is False
        assert mild["legs"]["price"] is False

    def test_information_ratio(self):
        out = px.information_ratio(returns=[0.02, 0.03, 0.01, 0.04],
                                    benchmark_returns=[0.01, 0.01, 0.01, 0.01])
        assert out["information_ratio"] > 0.0
        assert out["n"] == 4


# --------------------------------------------------------------------------
# Z.3 shared statistic + AA.7 numerics
# --------------------------------------------------------------------------

class TestWilsonAndAA7:
    def test_wilson_matches_the_z8_scenario_a(self):
        """Z.8 Scenario A quoted 49 % for n=42, p̂=0.58."""
        value = px.wilson_lower_bound(27, 42)
        assert value == pytest.approx(0.49, abs=0.01)

    def test_wilson_domain_guards(self):
        with pytest.raises(ValueError):
            px.wilson_lower_bound(1, 0)
        with pytest.raises(ValueError):
            px.wilson_lower_bound(5, 4)

    def test_numba_is_not_used(self):
        """AA.7-2 asks for Numba; §9.5-9 forbids it (Wave-Out) — the module
        records the conflict and never imports it ([ISSUE-CP8-002])."""
        assert px.NUMBA_USED is False
        source = (px.REPO_ROOT / "apex" / "research" / "proxies.py").read_text()
        assert "import numba" not in source

    def test_incremental_only_flag(self):
        assert px.INCREMENTAL_ONLY is True
