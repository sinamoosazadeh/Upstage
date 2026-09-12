"""CP-1 quality tests: §2.1 seven hard gates + four vetoes + Q_raw/Q_min
(copy-exact tables loaded from params), Q_window minimum-veto +
exponential ranking, derived measures; §2.2 two-tier epsilon, quantize,
division guards, core formulas, NaN/Inf/-0; §2.3 as_of/MTF/PIT rules."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal, ROUND_HALF_UP

import pytest

from apex.config import load_params
from apex.data_catalog.contracts import MarketObservation
from apex.quality.numerical import (
    ATR_FLOOR,
    ENGINE_EPS,
    EPS_TIER1,
    EPS_TIER2,
    PRECISION,
    calc_numerical_contract,
    eps_for_engine,
    formula_body_ratio,
    formula_normalized_range,
    formula_return_k,
    formula_volume_ratio,
    guarded_div,
    quantize,
    quantize_field,
)
from apex.quality.pit import (
    TF_DURATION_SECONDS,
    calc_snapshot_pit_window,
)
from apex.quality.vector import (
    QualityFlags,
    calc_quality_vector,
    calc_window_quality,
    q_evidence,
    q_feature,
    q_forecast,
    q_fresh,
    q_param,
)


def make_obs(symbol="BTCUSDT", timeframe="15m", o=100, h=105, l=98, c=102,
             v=10, oi=Decimal("500"), ts="2024-01-01T00:15:00.000Z",
             status="CLOSED", availability=None, oi_lag=0.0, delay=1.0,
             completeness=100.0, source_health=1.0, gap=0, expected=1):
    return MarketObservation(
        symbol=symbol, timeframe=timeframe, open=Decimal(o),
        high=Decimal(h), low=Decimal(l), close=Decimal(c), volume=Decimal(v),
        oi=oi, timestamp=ts, sequence=0, status=status, source="TOOBIT",
        availability_time=availability or ts, oi_lag_seconds=oi_lag,
        delay_seconds=delay, completeness_pct=completeness,
        source_health=source_health, gap_count=gap, expected_count=expected)


class TestVector21:
    def test_q_raw_on_clean_observation(self):
        """1m weights: schema .20, time .20, seq .15, ohlc .20, volume .10,
        oi .10, source .05 → all 1.0 → Q_raw = 1.0."""
        obs = make_obs(timeframe="1m", delay=0.0)  # threshold 5s
        q, state, cls = calc_quality_vector(obs)
        assert q == 1.0 and state == "VALID" and cls == "Q1"

    def test_q_raw_partial_values(self):
        """1h row: Q_schema 1, Q_time = 1−min(1, 15/30)=0.5, others 1 →
        Q_raw = .15 + .075 + .15 + .25 + .15 + .10 + .05 = 0.925."""
        obs = make_obs(timeframe="1h", delay=15.0)
        q, state, cls = calc_quality_vector(obs)
        assert abs(q - 0.925) < 1e-9

    def test_gates_quarantine(self):
        cases = [
            (dict(symbol="DOTUSDT"), "QUARANTINED_SYMBOL"),
            (dict(timeframe="3d"), "QUARANTINED_TIMEFRAME"),
            (dict(ts=""), "QUARANTINED_TIMESTAMP"),
            (dict(h=98, l=99), "QUARANTINED_OHLC"),
            (dict(v=-1), "QUARANTINED_VOLUME_NEG"),
            (dict(delay=99999), "QUARANTINED_FRESHNESS"),
            (dict(completeness=50.0), "QUARANTINED_VETO"),
            (dict(source_health=0.1), "QUARANTINED_VETO"),
            (dict(oi_lag=99999), "QUARANTINED_VETO"),
        ]
        for kwargs, reason in cases:
            obs = make_obs(**kwargs)
            q, state, cls = calc_quality_vector(obs)
            assert state == reason, f"{kwargs} → {state}"
            assert cls == "QX"

    def test_flags_gates(self):
        obs = make_obs()
        q, state, cls = calc_quality_vector(obs, QualityFlags(schema_valid=False))
        assert state == "QUARANTINED_SCHEMA"
        q, state, cls = calc_quality_vector(obs, QualityFlags(ordering_valid=False))
        assert state == "QUARANTINED_ORDERING"
        q, state, cls = calc_quality_vector(
            obs, QualityFlags(duplicate_hash_exists=True))
        assert state == "QUARANTINED_DUPLICATE"
        q, state, cls = calc_quality_vector(
            obs, QualityFlags(sequence_hash_valid=False))
        assert state == "QUARANTINED_SEQUENCE"
        q, state, cls = calc_quality_vector(
            obs, QualityFlags(replay_hash_valid=False))
        assert state == "QUARANTINED_REPLAY"

    def test_q_min_quarantine(self):
        """15m Q_min = 0.54, freshness threshold 20s: Q_time=0 (delay=20s),
        Q_seq=0 (gaps), Q_volume=0.5 (zero volume), Q_oi=0 (missing OI) →
        Q_raw = .17 + 0 + 0 + .23 + .065 + 0 + .05 = 0.515 < 0.54."""
        obs = make_obs(timeframe="15m", delay=20.0, gap=10, expected=10,
                       v=0, source_health=0.9, oi=None)
        q, state, cls = calc_quality_vector(obs)
        assert state == "QUARANTINED_Q_MIN" and cls == "QX"

    def test_q_oi_states(self):
        assert calc_quality_vector(make_obs(oi=None))[0] is not None  # Q_oi=0 label, not veto
        # STALE = 0.5 canonical (1m threshold 10s; lag 20s ≤ 5·thr → STALE)
        obs = make_obs(oi=Decimal("100"), oi_lag=20.0, timeframe="1m",
                       delay=0.0)
        q, state, cls = calc_quality_vector(obs)
        assert abs(q - (1.0 - 0.10 * 0.5)) < 1e-9  # only Q_oi reduced
        # DEGRADED (lag > 5·thr) → hard veto (Ch.7: not soft)
        obs2 = make_obs(oi=Decimal("100"), oi_lag=100.0, timeframe="1m",
                        delay=0.0)
        q2, state2, cls2 = calc_quality_vector(obs2)
        assert state2 == "QUARANTINED_VETO" and cls2 == "QX"

    def test_q_window_minimum_veto(self):
        """19×0.97 + 1×0.3 → INVALID even though the plain average ≈0.93."""
        qualities = [(0.97, float(i)) for i in range(19)] + [(0.3, 19.0)]
        q, state, cls = calc_window_quality(qualities)
        assert state == "INVALID_MIN_Q_THR" and cls == "QX"

    def test_q_window_weighted_score(self):
        """Q_window = Σ Q·exp(−λ·age)/Σ exp(−λ·age); all-equal Q → Q."""
        qualities = [(0.8, 0.0), (0.8, 5.0), (0.8, 10.0)]
        q, state, cls = calc_window_quality(qualities)
        assert abs(q - 0.8) < 1e-9 and state == "VALID"

    def test_q_window_empty(self):
        q, state, cls = calc_window_quality([])
        assert state == "INVALID_EMPTY" and cls == "QX"

    def test_derived_measures(self):
        # Q_feature(1,1,1) = 0.5·1 × 0.3·1 × 0.2·1 = 0.03 (§2.1 formula)
        assert abs(q_feature(1.0, 1.0, 1.0) - 0.03) < 1e-9
        assert abs(q_feature(1.0, 1.0, 0.0) - 0.0) < 1e-9
        assert abs(q_evidence(1.0, 1.0, 1.0, 1.0, "1m")
                   - (0.3 * 0.3 * 0.2 * 0.2)) < 1e-9
        with pytest.raises(ValueError):
            q_evidence(1.0, 1.0, 1.0, 1.0, "5m")  # undocumented TF → fail-closed
        value, degraded = q_param(0.1, 0.2, 0.1)
        assert abs(value - 0.6) < 1e-9 and degraded is False
        value, degraded = q_param(0.3, 0.3, 0.2)
        assert degraded is True
        value, blocked = q_forecast(0.2, 0.2, 0.2)
        assert abs(value - 0.4) < 1e-9 and blocked is True
        assert abs(q_fresh(0) - 1.0) < 1e-9

    def test_weights_from_params_only(self):
        """Tables come from params/quality_weights_v1.yaml (copy-exact)."""
        qw = load_params()["quality_weights"]
        obs = make_obs(timeframe="1m", delay=0.0)
        q, _, _ = calc_quality_vector(obs)
        assert q == sum(qw["q_raw_weights_by_tf"]["1m"].values())


class TestNumerical22:
    def test_two_tier_epsilon_frozen(self):
        assert EPS_TIER1 == Decimal("1e-12")
        assert EPS_TIER2 == Decimal("1e-8")
        assert ATR_FLOOR == Decimal("1e-8")

    def test_engine_eps_table_frozen(self):
        assert ENGINE_EPS == {
            "E01": "SCALED", "E02": "1e-8", "E03": "1e-8", "E04": "1e-12",
            "E05": "1e-8", "E06": "1e-8", "E07": "1e-8", "E08": "1e-8",
            "E09": "1e-12", "E10": "1e-8", "E11": "1e-8", "E12": "1e-12"}
        assert eps_for_engine("E04") == Decimal("1e-12")
        assert eps_for_engine("E02") == Decimal("1e-8")
        assert eps_for_engine("E01", Decimal("0.01"),
                              [Decimal("100")] * 20) == Decimal("0.005")
        with pytest.raises(KeyError):
            eps_for_engine("E13")
        with pytest.raises(ValueError):
            eps_for_engine("E01")  # missing scaled inputs → fail-closed

    def test_precision_table_frozen(self):
        assert PRECISION == {"price": 10, "volume": 8, "quality": 4,
                             "strength": 4, "confidence": 4, "fee": 10,
                             "atr": 10, "return": 10, "body_ratio": 6}
        with pytest.raises(KeyError):
            quantize_field("invented", Decimal(1))

    def test_quantize_round_half_up(self):
        assert quantize(Decimal("1.234567"), 4) == Decimal("1.2346")
        assert quantize(Decimal("1.234544"), 4) == Decimal("1.2345")
        assert quantize(Decimal("2.5"), 0) == Decimal("3")  # HALF_UP

    def test_division_guards(self):
        assert guarded_div(Decimal(1), Decimal(0)) == Decimal(1) / EPS_TIER1
        assert guarded_div(Decimal(1), Decimal("1e-15")) == \
            Decimal(1) / EPS_TIER1
        assert guarded_div(Decimal("-1"), Decimal(0)) < 0
        with pytest.raises(ValueError):
            guarded_div(Decimal("NaN"), Decimal(1))
        with pytest.raises(ValueError):
            guarded_div(Decimal(1), Decimal("Infinity"))

    def test_numerical_contract_example(self):
        """C=105, O=100, H=110, L=98 → body 5/12=0.416667; upper
        (110−105)/12=0.416667; lower (100−98)/12=0.166667; close_position
        (105−98)/12=0.5833; ATR_n=12 → normalized_range=1.0000."""
        out, state, cls = calc_numerical_contract(
            C=Decimal(105), O=Decimal(100), H=Decimal(110), L=Decimal(98),
            V=Decimal(10), ATR_n=Decimal(12), tick_size=Decimal("0.01"),
            quantity_step=Decimal("0.001"), timeframe="15m")
        assert state == "VALID" and cls == "Q1"
        assert out["body_ratio"] == Decimal("0.416667")
        assert out["upper_wick"] == Decimal("0.416667")
        assert out["lower_wick"] == Decimal("0.166667")
        assert out["close_position"] == Decimal("0.5833")
        assert out["normalized_range"] == Decimal("1.0000")
        assert out["eps_price"] == Decimal("1e-12")   # 1e-10 × 0.01
        assert out["eps_volume"] == Decimal("1e-15")  # 1e-12 × 0.001
        assert out["eps_range"] == Decimal("1.2e-8")  # 1e-9 × 12
        assert out["eps_momentum"] == Decimal("1e-12")

    def test_h_lt_l_quarantined(self):
        out, state, cls = calc_numerical_contract(
            C=Decimal(100), O=Decimal(100), H=Decimal(99), L=Decimal(101),
            V=Decimal(1), ATR_n=Decimal(1), tick_size=Decimal("0.01"),
            quantity_step=Decimal("0.001"))
        assert state == "QUARANTINED_H_LT_L" and cls == "QX"

    def test_doji_range_guarded(self):
        """H−L=0 doji → max(H−L, ε_range) keeps ratios finite."""
        v, q = formula_body_ratio(Decimal(100), Decimal(100),
                                  Decimal(100), Decimal(100))
        assert v == Decimal("0.000000") and q == 1.0

    def test_core_formulas(self):
        v, q = formula_volume_ratio(Decimal(20), Decimal(10))
        assert v == Decimal("2.00000000") and q == 1.0
        v, q = formula_volume_ratio(Decimal(20), Decimal(0))
        assert v is None and q == 0.0
        v, q = formula_return_k(Decimal(110), Decimal(100))
        assert v == Decimal("0.1000000000")
        v, q = formula_return_k(Decimal(110), Decimal(0))
        assert v is None and q == 0.0
        v, q = formula_normalized_range(Decimal(110), Decimal(98),
                                        Decimal(12))
        assert v == Decimal("1.0000")


class TestPit23:
    def _obs(self, symbol="BTCUSDT", tf="1h", avail="2024-01-01T14:00:03.000Z",
             ts="2024-01-01T14:00:00.000Z", status="CLOSED"):
        return make_obs(symbol=symbol, timeframe=tf, ts=ts,
                        availability=avail, status=status)

    def test_as_of_max_availability(self):
        obs = [self._obs(), self._obs(avail="2024-01-01T14:05:10.000Z",
                                      ts="2024-01-01T14:05:00.000Z")]
        snap, state, cls = calc_snapshot_pit_window(
            obs, ["1h"], minimum_bars=1)
        assert state == "VALID"
        assert snap["snapshot_id"] and len(snap["snapshot_id"]) == 64

    def test_missing_availability_fail_closed(self):
        obs = self._obs(avail=None)
        obs = MarketObservation(
            symbol=obs.symbol, timeframe=obs.timeframe, open=obs.open,
            high=obs.high, low=obs.low, close=obs.close, volume=obs.volume,
            oi=obs.oi, timestamp=obs.timestamp, sequence=obs.sequence,
            status=obs.status, source=obs.source,
            availability_time=None, oi_lag_seconds=obs.oi_lag_seconds,
            delay_seconds=obs.delay_seconds,
            completeness_pct=obs.completeness_pct,
            source_health=obs.source_health)
        with pytest.raises(ValueError) as ei:
            calc_snapshot_pit_window([obs], ["1h"], minimum_bars=1)
        assert "MISSING_AVAILABILITY_TIME_QX" in str(ei.value)

    def test_insufficient_bars(self):
        snap, state, cls = calc_snapshot_pit_window(
            [self._obs()], ["1h"], minimum_bars=100)
        assert state == "INSUFFICIENT_BARS" and cls == "QX"

    def test_mtf_states(self):
        obs = [self._obs(tf="1h")] * 3 + [self._obs(tf="4h")]
        snap, state, cls = calc_snapshot_pit_window(
            obs, ["1h", "4h"], minimum_bars=3)
        assert snap["mtf_states"]["1h"] == "ALIGNED"
        assert snap["mtf_states"]["4h"] == "INSUFFICIENT"
        assert snap["overall_mtf"] == "INSUFFICIENT"

    def test_closed_only(self):
        open_obs = self._obs(status="PARTIAL")
        snap, state, cls = calc_snapshot_pit_window(
            [open_obs, self._obs()], ["1h"], minimum_bars=1)
        assert state == "VALID"  # only CLOSED observations counted

    def test_deterministic_snapshot_id(self):
        obs = [self._obs(), self._obs(avail="2024-01-01T14:05:10.000Z")]
        s1, _, _ = calc_snapshot_pit_window(obs, ["1h"], minimum_bars=1)
        s2, _, _ = calc_snapshot_pit_window(obs, ["1h"], minimum_bars=1)
        assert s1["snapshot_id"] == s2["snapshot_id"]

    def test_tf_duration_table(self):
        assert TF_DURATION_SECONDS["1m"] == 60
        assert TF_DURATION_SECONDS["1h"] == 3600
        assert TF_DURATION_SECONDS["1w"] == 604800
        assert TF_DURATION_SECONDS["1mo"] == 2592000  # 30-day interval
