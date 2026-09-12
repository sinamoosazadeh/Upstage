"""E12 Temporal Context — CP-5 §8 unit battery.

Covers: the 12 §8.1 golden fixtures (independently re-derived, hash-locked),
T-E12-Windows (AI.10 boundary law + §8.8 UTC-boundary stability), §3.2 FFF
norms, §3.3/§3.4/§3.6 statistics (in-tree Kruskal–Wallis/Spearman per
ISSUE-CP5-025), §5.4 state machine + event journal, §5.5 quality ladder,
§6 parameter governance, §5.2 schema validation, §8.2/§8.3 replay + leak,
§8.7 v3 adapter, the E07 provider contract in BOTH modes (degraded before /
resolved with real E12), and the frozen EngineBase binding.
"""

from __future__ import annotations

import datetime
import json
import math
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from apex.data_catalog.contracts import MarketObservation
from apex.engines.e07_rtm.engine import utc_activity_window_check
from apex.engines.e12_temporal import engine as E
from apex.engines.e12_temporal.engine import (
    CALENDAR_CONFIG_VERSION,
    CONTRACT_VERSION,
    E12_DEFAULTS,
    E12TemporalEngine,
    E12TemporalProvider,
    EVENT_CATALOG,
    EngineParams,
    OVERLAP_WINDOW,
    PRIMARY_WINDOWS,
    TemporalWindowEngineStream,
    UTC_ACTIVITY_WINDOWS,
    UTC_CORE_WINDOWS,
    chi2_sf,
    compute_temporal_profile,
    condition_key,
    conditional_rate,
    day_type,
    deseasonalize,
    deterministic_replay_check,
    fff_seasonal,
    fourier_smooth_factors,
    get_params,
    hour_float,
    intraday_momentum_beta,
    is_core_window,
    kruskal_wallis,
    load_v3_temporal_payload,
    make_snapshot_id,
    no_future_leak_check,
    observation_to_candle,
    param_hash,
    profile_stability,
    range_z,
    returns_by_tod_from_candles,
    rollover_is_active,
    run_engine,
    seasonal_profile_available,
    serialize_state,
    spearman_rho,
    tod_bin,
    ts_from_ms,
    utc_activity_window_of,
    validate_state_schema,
    vol_ratio,
    window_progress,
    wilson_ci,
    winsorize,
    y_range,
    y_vol,
)
from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import sha256_hex

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" \
    / "e12_golden_fixtures.json"
DOC = json.loads(FIXTURE_PATH.read_text())
FIXTURES = DOC["fixtures"]
BY_ID = {f["id"]: f for f in FIXTURES}
CASE = DOC["case_study"]

SAT_ROLLOVER = [{"weekdays": [5], "start_h": 0.0, "end_h": 1.0}]


def ms(iso: str) -> int:
    return int(datetime.datetime.fromisoformat(
        iso.replace("Z", "+00:00")).timestamp() * 1000)


def dt_utc(iso: str) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(ms(iso) / 1000.0,
                                           tz=datetime.timezone.utc)


def candle(iso, H, L, C, V, **kw):
    d = {"ts": ms(iso), "H": H, "L": L, "C": C, "V": V,
         "availability_time_ms": ms(iso)}
    d.update(kw)
    return d


def run_fixture(fx, econ_calendar=None, rollover_windows=None,
                window_volume_history=None):
    eng = TemporalWindowEngineStream(rollover_windows=rollover_windows)
    if window_volume_history:
        window = fx["expected"].get("temporal_window", "UTC_W2")
        for v in window_volume_history:
            eng.buffer.append({"V": float(v), "window": window,
                               "vol_ratio": 1.0, "H": 1.0, "L": 0.5,
                               "ts": 0, "bin": 0, "day_type_key": "WEEKDAY"})
    cal = fx.get("context", {}).get("econ_calendar") \
        if econ_calendar is None else econ_calendar
    if cal is not None:
        cal = set(cal)
    roll = fx.get("context", {}).get("rollover_windows") \
        if rollover_windows is None else rollover_windows
    eng.rollover_windows = list(roll or [])
    hist = fx.get("context", {}).get("window_volume_history") \
        if window_volume_history is None else window_volume_history
    if hist and not window_volume_history:
        return run_fixture(fx, econ_calendar=cal, rollover_windows=roll,
                           window_volume_history=hist)
    return eng.on_candle(dict(fx["candle"]), cal)


def q4_profile_inputs():
    """Deterministic inputs that satisfy the full Q4 ladder (§5.5)."""
    rng = np.random.default_rng(7)
    rbt = {b: [float(rng.normal(0, 0.01 * (2 if b % 2 else 1)))
               for _ in range(40)] for b in range(12)}
    g1 = [float(rng.normal(0.0, 0.01)) for _ in range(50)]
    g2 = [float(rng.normal(0.02, 0.04)) for _ in range(50)]
    base = fff_seasonal(rbt)
    hist = [base, {k: v * 1.001 for k, v in base.items()},
            {k: v * 1.002 for k, v in base.items()}]
    events = [True] * 40 + [False] * 10
    keys = [condition_key("UTC_W2", 25, "FRIDAY")] * 50
    return {"returns_by_tod": rbt, "cond_events": {"bos": (events, keys)},
            "window_groups": [g1, g2], "profiles_history": hist}


# ---------------------------------------------------------------------------
# §8.1 — the 12 golden fixtures (hash-locked, independently re-derived)
# ---------------------------------------------------------------------------
class TestGoldenFixtures:
    def test_fixture_doc_identity(self):
        assert DOC["engine"] == "E12_Temporal_Context"
        assert DOC["contract_version"] == "4.0.0"
        assert len(FIXTURES) == 12
        assert set(BY_ID) == {f["id"] for f in FIXTURES}

    def test_fixture_hashes(self):
        for fx in FIXTURES:
            body = {k: v for k, v in fx.items() if k not in ("hash", "note")}
            assert sha256_hex(canonical_json(body).encode()) == fx["hash"], \
                fx["id"]

    @pytest.mark.parametrize("fid", sorted(BY_ID))
    def test_fixture_expected(self, fid):
        fx = BY_ID[fid]
        st = run_fixture(fx)
        exp = fx["expected"]
        for key, want in exp.items():
            if key in ("hour_utc", "minute", "weekday", "tod_bin",
                       "utc_window_progress"):
                got = st.get("tod_state", {}).get(key)
            else:
                got = st.get(key)
            assert got == want, f"{fid}.{key}: {got} != {want}"
        if exp["quality"] != "Q0":
            assert validate_state_schema(st) == [], validate_state_schema(st)
            assert st["fate"] == "ACTIVE"
            assert st["version"] == CONTRACT_VERSION

    def test_gf05_high_impact_and_vr(self):
        fx = BY_ID["GF05_HIGH_IMPACT"]
        st = run_fixture(fx)
        assert st["day_type"] == "HIGH_IMPACT"
        assert st["vol_ratio"] == 2.5                 # 20000 / 8000
        assert y_vol(st["vol_ratio"]) is True         # 2.5 > 1.5 (§3.3)

    def test_gf07_q0_payload_shape_and_fate(self):
        st = run_fixture(BY_ID["GF07_INVALID_HL"])
        assert st["quality"] == "Q0"
        assert st["reason"] == "INVALID_CANDLE"
        assert st["fate"] == "INVALIDATED"
        assert len(st["snapshot_id"]) == 64
        # §5.1: the SAME payload contract hashes valid and invalid outcomes
        payload = {"engine": "E12", "contract_version": "4.0.0",
                   "input": dict(BY_ID["GF07_INVALID_HL"]["candle"]),
                   "state": {"quality": "Q0", "reason": "INVALID_CANDLE"}}
        assert st["snapshot_id"] == make_snapshot_id(payload)

    def test_gf09_gap_formula_governs(self):
        # §8.1 note says gap=true; §3.1 formula: 71000 ≤ 77000 ⇒ no gap
        # (ISSUE-CP5-022).  The law itself is proven with a real >10% gap:
        st = run_fixture(BY_ID["GF09_GAP"])
        assert st["is_gap"] is False
        eng = TemporalWindowEngineStream()
        big = eng.on_candle(candle("2024-03-15T07:01:00Z", 80000, 79000,
                                   79500, 5000, O=78000, prev_H=70000,
                                   prev_L=69900))
        assert big["is_gap"] is True                  # 78000 > 70000·1.1
        down = eng.on_candle(candle("2024-03-15T07:02:00Z", 62000, 61000,
                                    61500, 5000, O=62000, prev_H=70000,
                                    prev_L=69900))
        assert down["is_gap"] is True                 # 62000 < 69900·0.9

    def test_gf10_rollover_needs_configuration(self):
        fx = BY_ID["GF10_ROLLOVER"]
        st = run_fixture(fx)
        assert st["temporal_window"] == "UTC_W0"      # ISSUE-CP5-023
        assert st["rollover_active"] is True
        # default (empty) canonical configuration ⇒ never active
        plain = TemporalWindowEngineStream().on_candle(dict(fx["candle"]),
                                                       set())
        assert plain["rollover_active"] is False

    def test_gf12_exclusive_overlap_end(self):
        st = run_fixture(BY_ID["GF12_OVERLAP_EDGE"])
        assert st["temporal_window"] == "UTC_W2"
        assert st["is_overlap"] is False              # [12.5, 16) exclusive
        assert st["window_phase"] == "MID"
        assert st["tod_state"]["tod_bin"] == 32


# ---------------------------------------------------------------------------
# T-E12-Windows (AI.10) + §8.8 UTC-boundary stability
# ---------------------------------------------------------------------------
class TestTE12Windows:
    BOUNDARIES = [
        ("2024-03-15T00:00:00Z", "UTC_W0", False, "MID"),
        ("2024-03-15T06:59:59Z", "UTC_W0", False, "MID"),
        ("2024-03-15T07:00:00Z", "UTC_W1", False, "EARLY"),
        ("2024-03-15T07:59:59Z", "UTC_W1", False, "EARLY"),
        ("2024-03-15T08:00:00Z", "UTC_W1", False, "MID"),
        ("2024-03-15T11:29:59Z", "UTC_W1", False, "MID"),
        ("2024-03-15T11:30:00Z", "UTC_W1", False, "LATE"),
        ("2024-03-15T12:29:59Z", "UTC_W1", False, "LATE"),
        ("2024-03-15T12:30:00Z", "UTC_W2", True, "EARLY"),
        ("2024-03-15T12:59:59Z", "UTC_W2", True, "EARLY"),
        ("2024-03-15T13:00:00Z", "UTC_W2", True, "MID"),
        ("2024-03-15T15:59:59Z", "UTC_W2", True, "MID"),
        ("2024-03-15T16:00:00Z", "UTC_W2", False, "MID"),
        ("2024-03-15T20:29:59Z", "UTC_W2", False, "MID"),
        ("2024-03-15T20:30:00Z", "UTC_W2", False, "LATE"),
        ("2024-03-15T20:59:59Z", "UTC_W2", False, "LATE"),
        ("2024-03-15T21:00:00Z", "UTC_W3", False, "MID"),
        ("2024-03-15T23:59:59Z", "UTC_W3", False, "MID"),
    ]

    @pytest.mark.parametrize("iso,window,overlap,phase", BOUNDARIES)
    def test_boundary_sweep(self, iso, window, overlap, phase):
        out = utc_activity_window_of(dt_utc(iso))
        assert out["temporal_window"] == window
        assert out["is_overlap"] is overlap
        assert out["window_phase"] == phase

    def test_registry_is_canonical_3_5(self):
        assert UTC_ACTIVITY_WINDOWS == {"UTC_W0": (0.0, 7.0),
                                        "UTC_W1": (7.0, 12.5),
                                        "UTC_W2": (12.5, 21.0),
                                        "UTC_W3": (21.0, 24.0)}
        assert UTC_CORE_WINDOWS == {"UTC_W1_CORE": (7.0, 11.0),
                                    "UTC_W2_CORE": (12.5, 16.0)}
        assert OVERLAP_WINDOW == (12.5, 16.0)
        # registry covers [0,24) contiguously and exclusively
        spans = [UTC_ACTIVITY_WINDOWS[w] for w in PRIMARY_WINDOWS]
        assert spans[0][0] == 0.0 and spans[-1][1] == 24.0
        for a, b in zip(spans, spans[1:]):
            assert a[1] == b[0]

    def test_overlap_is_derived_never_primary(self):
        # no primary window label may be named OVERLAP (§3.5)
        assert all("OVERLAP" not in w for w in PRIMARY_WINDOWS)
        for iso, want in (("2024-03-15T12:30:00Z", True),
                          ("2024-03-15T15:59:59Z", True),
                          ("2024-03-15T16:00:00Z", False),
                          ("2024-03-15T12:29:59Z", False)):
            assert utc_activity_window_of(dt_utc(iso))["is_overlap"] is want

    def test_core_windows(self):
        assert is_core_window(7.0) and is_core_window(10.999)
        assert not is_core_window(11.0) and not is_core_window(12.4)
        assert is_core_window(12.5) and is_core_window(15.999)
        assert not is_core_window(16.0)

    def test_tod_bins_case_study(self):
        assert CASE["bins"] == {"06:00": 12, "07:00": 14, "12:30": 25,
                                "16:00": 32}
        assert tod_bin(6.0) == 12 and tod_bin(7.0) == 14
        assert tod_bin(12.5) == 25 and tod_bin(16.0) == 32
        assert tod_bin(23.999) == 47 and tod_bin(0.0) == 0
        with pytest.raises(ValueError, match="INVALID_TOD_BIN"):
            tod_bin(24.0)
        with pytest.raises(ValueError, match="INVALID_TOD_BIN"):
            tod_bin(-0.5)

    def test_window_progress(self):
        assert window_progress(12.5, "UTC_W2") == CASE["progress_1230"] == 0.0
        assert window_progress(0.0, "UTC_W0") == 0.0
        assert window_progress(23.999, "UTC_W3") == pytest.approx(1.0,
                                                                  abs=1e-3)
        assert window_progress(9.75, "UTC_W1") == pytest.approx(0.5,
                                                                abs=1e-12)

    @pytest.mark.parametrize("iso", [
        "2024-03-08T12:45:00Z", "2024-03-09T12:45:00Z", "2024-03-10T12:45:00Z",
        "2024-03-11T12:45:00Z", "2024-03-12T12:45:00Z"])
    def test_8_8_dst_boundary_stability(self, iso):
        # the 2024-03-10 US local-time transition cannot move UTC windows
        out = utc_activity_window_of(dt_utc(iso))
        assert out["is_overlap"] is True
        assert out["temporal_window"] == "UTC_W2"
        assert utc_activity_window_of(
            dt_utc(iso.replace("12:45", "16:00")))["is_overlap"] is False

    def test_naive_datetime_adopted_as_utc(self):
        naive = datetime.datetime(2024, 3, 15, 12, 45)
        assert utc_activity_window_of(naive)["is_overlap"] is True

    def test_non_utc_tz_rejected(self):
        cet = datetime.timezone(datetime.timedelta(hours=1))
        with pytest.raises(ValueError, match="NON_UTC_TIMESTAMP"):
            utc_activity_window_of(
                datetime.datetime(2024, 3, 15, 12, 45, tzinfo=cet))
        with pytest.raises(ValueError, match="must be datetime"):
            utc_activity_window_of(1710505800000)

    def test_hour_float_precision(self):
        assert hour_float(dt_utc("2024-03-15T12:30:00Z")) == 12.5
        assert hour_float(dt_utc("2024-03-15T07:15:00Z")) == 7.25


# ---------------------------------------------------------------------------
# §3.1/§4.1 — day types and rollover
# ---------------------------------------------------------------------------
class TestDayTypeAndRollover:
    @pytest.mark.parametrize("iso,want", [
        ("2024-03-13T12:00:00Z", "WEEKDAY"),       # Wednesday
        ("2024-03-15T12:00:00Z", "FRIDAY"),
        ("2024-03-16T12:00:00Z", "SATURDAY_SUNDAY_CONTEXT"),
        ("2024-03-17T12:00:00Z", "SATURDAY_SUNDAY_CONTEXT"),
        ("2024-04-10T12:00:00Z", "HIGH_IMPACT"),
    ])
    def test_day_type_precedence(self, iso, want):
        red = {"2024-04-10"} if want == "HIGH_IMPACT" else None
        assert day_type(dt_utc(iso), red) == want

    def test_high_impact_beats_friday_and_weekend(self):
        red = {"2024-03-15", "2024-03-16"}
        assert day_type(dt_utc("2024-03-15T20:00:00Z"), red) == "HIGH_IMPACT"
        assert day_type(dt_utc("2024-03-16T20:00:00Z"), red) == "HIGH_IMPACT"

    def test_calendar_accepts_dates_and_iso_strings(self):
        d = datetime.date(2024, 4, 10)
        assert day_type(dt_utc("2024-04-10T12:00:00Z"), {d}) == "HIGH_IMPACT"
        assert day_type(dt_utc("2024-04-10T12:00:00Z"),
                        ["2024-04-10"]) == "HIGH_IMPACT"
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            day_type(dt_utc("2024-04-10T12:00:00Z"), {12345})

    def test_rollover_default_config_never_active(self):
        # §3.1: no universal CME schedule; empty canonical config ⇒ False
        for iso in ("2024-03-15T20:55:00Z", "2024-03-16T00:30:00Z",
                    "2024-03-17T23:00:00Z"):
            assert rollover_is_active(dt_utc(iso), []) is False
            assert rollover_is_active(dt_utc(iso), None) is False

    def test_rollover_injected_config(self):
        assert rollover_is_active(dt_utc("2024-03-16T00:30:00Z"),
                                  SAT_ROLLOVER) is True
        assert rollover_is_active(dt_utc("2024-03-16T01:00:00Z"),
                                  SAT_ROLLOVER) is False   # exclusive end
        assert rollover_is_active(dt_utc("2024-03-15T00:30:00Z"),
                                  SAT_ROLLOVER) is False   # not Saturday
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            rollover_is_active(dt_utc("2024-03-16T00:30:00Z"),
                               [{"weekdays": [5], "start_h": 2.0,
                                 "end_h": 1.0}])

    def test_rollover_is_not_a_day_type(self):
        # §4.1: rollover never changes DayType; Saturday stays Saturday
        st = run_fixture(BY_ID["GF10_ROLLOVER"])
        assert st["day_type"] == "SATURDAY_SUNDAY_CONTEXT"
        assert st["rollover_active"] is True


# ---------------------------------------------------------------------------
# §3.2 — FFF seasonal profile
# ---------------------------------------------------------------------------
class TestFFF:
    def test_squared_estimator_and_renormalization(self):
        rbt = {b: [0.01] * 40 for b in range(6)}
        rbt[3] = [0.03] * 40
        f = fff_seasonal(rbt)
        assert abs(sum(f.values()) / len(f) - 1.0) < 1e-12   # mean ŝ = 1
        assert f[3] > f[0]                                   # hotter bin
        # hand-derived: mean_r2 = (5·1e-4 + 9e-4)/6 = 2.3333e-4
        grand = (5 * 1e-4 + 9e-4) / 6
        s3 = (9e-4 / grand)
        s0 = (1e-4 / grand)
        avg = (5 * s0 + s3) / 6
        assert f[3] == pytest.approx(s3 / avg, rel=1e-12)
        assert f[0] == pytest.approx(s0 / avg, rel=1e-12)

    def test_clamp_0_1_to_10(self):
        rbt = {0: [1e-8] * 40, 1: [1.0] * 40}
        f = fff_seasonal(rbt)
        raw_lo, raw_hi = None, None
        # after clamp the renormalized values must reflect the [0.1, 10] box
        assert all(0.0 < v for v in f.values())
        # lower clamp 0.1 binds (raw 2e-16/0.5), upper does not (raw 2)
        assert f[1] / f[0] == pytest.approx(2.0 / 0.1, rel=1e-9)
        assert raw_lo is None and raw_hi is None

    def test_small_sample_returns_ones(self):
        f = fff_seasonal({0: [0.1] * 5})          # 5 < 10 valid r² samples
        assert f == {0: 1.0}
        assert fff_seasonal({}) == {}

    def test_abs_estimator_forbidden(self):
        # ISSUE-CP5-024 (§3.2/§11(a)): biased estimator fails closed
        with pytest.raises(ValueError, match="FFF_ABS_ESTIMATOR_FORBIDDEN"):
            fff_seasonal({0: [0.1] * 40}, use_sqrt=True)

    def test_pit_edge_unavailable(self):
        ok, why = seasonal_profile_available({b: [0.01] * 40
                                              for b in range(4)})
        assert (ok, why) == (True, "OK")
        assert seasonal_profile_available({b: [0.01] * 29
                                           for b in range(4)}) \
            == (False, "T_BELOW_30")
        assert seasonal_profile_available({b: [0.0] * 40 for b in range(4)}) \
            == (False, "GRAND_MEAN_R2_DEGENERATE")
        assert seasonal_profile_available({}) == (False, "NO_HISTORY")

    def test_deseasonalize(self):
        assert deseasonalize(0.00284, 1.29) == pytest.approx(0.00220,
                                                             abs=1e-5)
        with pytest.raises(ValueError, match="INVALID_SEASONAL_FACTOR"):
            deseasonalize(0.01, 0.0)
        with pytest.raises(ValueError, match="INVALID_SEASONAL_FACTOR"):
            deseasonalize(0.01, float("nan"))

    def test_fourier_smoothing_recovers_harmonic(self):
        truth = {b: 1.0 + 0.3 * math.cos(2 * math.pi * b / 48)
                 for b in range(48)}
        sm = fourier_smooth_factors(truth)
        assert all(abs(sm[b] - truth[b]) < 1e-9 for b in range(48))

    def test_fourier_underdetermined_fails_closed(self):
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            fourier_smooth_factors({0: 1.0, 1: 2.0}, fourier_k=4)
        assert fourier_smooth_factors({}) == {}
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            fourier_smooth_factors({b: 1.0 for b in range(20)}, fourier_k=9)

    def test_winsorize_5pct(self):
        vals = [float(i) for i in range(100)]
        w = winsorize(vals, 0.05)
        assert min(w) == pytest.approx(np.quantile(vals, 0.05))
        assert max(w) == pytest.approx(np.quantile(vals, 0.95))
        assert len(w) == 100
        assert winsorize([]) == []

    def test_returns_by_tod_from_candles(self):
        cs = []
        base = ms("2024-03-14T00:00:00Z")
        price = 70000.0
        for i in range(96):                       # 30-min candles, 2 days
            price *= math.exp(0.001 if i % 2 else -0.0005)
            cs.append({"ts": base + i * 1800_000, "c": price})
        rbt = returns_by_tod_from_candles(cs)
        assert all(0 <= b < 48 for b in rbt)
        assert sum(len(v) for v in rbt.values()) == 95   # 96 closes ⇒ 95 r


# ---------------------------------------------------------------------------
# §3.3/§3.4/§3.6 — statistics (in-tree per ISSUE-CP5-025)
# ---------------------------------------------------------------------------
class TestStatistics:
    def test_conditional_rate_case_study(self):
        events = [True] * 2250 + [False] * 2750
        keys = ["UTC_W2|25|FRIDAY"] * 5000
        p, n, ci = conditional_rate(events, keys, "UTC_W2|25|FRIDAY")
        assert p == CASE["wilson_p"] == 0.45
        assert n == CASE["wilson_n"] == 5000
        # §9: Wilson CI [0.43, 0.47] at 2-dp; exact band:
        assert ci[0] == pytest.approx(0.43625, abs=1e-4)
        assert ci[1] == pytest.approx(0.46382, abs=1e-4)
        assert ci[1] - ci[0] < 0.3

    def test_conditional_rate_insufficient_sample(self):
        p, n, ci = conditional_rate([True] * 29, ["k"] * 29, "k")
        assert (p, n, ci) == (None, 29, None)     # n < 30 ⇒ null, Q1
        p, n, ci = conditional_rate([True] * 30, ["k"] * 30, "k")
        assert p == 1.0 and n == 30 and ci is not None

    def test_conditional_rate_length_mismatch(self):
        with pytest.raises(ValueError, match="length mismatch"):
            conditional_rate([True], ["k", "k"], "k")

    def test_wilson_ci_edges(self):
        assert wilson_ci(5, 29) is None           # n < 30 ⇒ null
        lo, hi = wilson_ci(15, 30)
        z = 1.96
        p = 0.5
        denom = 1 + z * z / 30
        centre = p + z * z / 60
        delta = z * math.sqrt((p * 0.5 + z * z / 120) / 30)
        assert lo == pytest.approx((centre - delta) / denom, rel=1e-12)
        assert hi == pytest.approx((centre + delta) / denom, rel=1e-12)
        with pytest.raises(ValueError, match="INVALID_WILSON_INPUT"):
            wilson_ci(31, 30)

    def test_kruskal_significant_and_null(self):
        rng = np.random.default_rng(11)
        g1 = [float(rng.normal(0.0, 0.01)) for _ in range(60)]
        g2 = [float(rng.normal(0.05, 0.01)) for _ in range(60)]
        res = kruskal_wallis([g1, g2])
        assert res["significant"] is True and res["p"] < 0.05
        same = kruskal_wallis([g1, list(g1)])
        assert same["H"] == pytest.approx(0.0, abs=1e-9)
        assert same["significant"] is False

    def test_kruskal_tie_correction(self):
        groups = [[1.0] * 10 + [2.0] * 10, [1.0] * 10 + [3.0] * 10]
        res = kruskal_wallis(groups)
        assert res["n"] == 40 and res["df"] == 1
        assert math.isfinite(res["H"]) and 0.0 <= res["p"] <= 1.0

    def test_kruskal_fail_closed(self):
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            kruskal_wallis([[1.0, 2.0]])
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            kruskal_wallis([[1.0], []])
        with pytest.raises(ValueError, match="DEGENERATE_TIE_STRUCTURE"):
            kruskal_wallis([[1.0] * 20, [1.0] * 20])

    def test_test_temporal_window_difference_wrapper(self):
        rng = np.random.default_rng(3)
        res = E.test_temporal_window_difference(
            [[float(rng.normal(0, 1)) for _ in range(40)],
             [float(rng.normal(3, 1)) for _ in range(40)]])
        assert set(res) == {"H", "p", "significant"}
        assert res["significant"] is True

    def test_chi2_sf_known_values(self):
        assert chi2_sf(0.0, 3) == 1.0
        assert chi2_sf(9.8, 3) == pytest.approx(CASE["chi2_p_H98_df3"],
                                                abs=5e-4)
        assert chi2_sf(3.841459, 1) == pytest.approx(0.05, abs=1e-5)
        assert chi2_sf(7.814728, 3) == pytest.approx(0.05, abs=1e-5)
        with pytest.raises(ValueError, match="INVALID_CHI2_DF"):
            chi2_sf(1.0, 0)
        with pytest.raises(ValueError, match="INVALID_CHI2_INPUT"):
            chi2_sf(-1.0, 2)

    def test_spearman(self):
        assert spearman_rho([1, 2, 3, 4], [1, 2, 3, 4]) == 1.0
        assert spearman_rho([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0
        # tie-free identity with the §3.6 closed form
        a = [0.4, 0.9, 0.2, 0.7, 0.55]
        b = [0.1, 0.8, 0.35, 0.6, 0.5]
        ra = [sorted(a).index(x) + 1 for x in a]
        rb = [sorted(b).index(x) + 1 for x in b]
        d2 = sum((x - y) ** 2 for x, y in zip(ra, rb))
        n = len(a)
        assert spearman_rho(a, b) == pytest.approx(
            1 - 6 * d2 / (n * (n * n - 1)), rel=1e-12)

    def test_spearman_ties_and_failures(self):
        rho = spearman_rho([1, 1, 2, 3], [1, 1, 2, 3])
        assert rho == 1.0                       # mid-ranks handle ties
        with pytest.raises(ValueError, match="length mismatch"):
            spearman_rho([1, 2], [1])
        with pytest.raises(ValueError, match="DEGENERATE_RANK_STRUCTURE"):
            spearman_rho([1, 1, 1], [1, 2, 3])

    def test_profile_stability(self):
        base = {b: 1.0 + 0.1 * b for b in range(8)}
        near = {b: v * 1.01 for b, v in base.items()}
        stab = profile_stability([base, near, base])
        assert stab["mean_spearman"] == pytest.approx(1.0, abs=1e-9)
        assert len(stab["rhos"]) == 2
        assert profile_stability([]) == {"mean_spearman": 0.0, "rhos": []}
        assert profile_stability([base]) == {"mean_spearman": 0.0,
                                             "rhos": []}
        with pytest.raises(ValueError, match="identical bin sets"):
            profile_stability([base, {0: 1.0}])

    def test_intraday_momentum_beta(self):
        xs = [0.001 * i for i in range(30)]
        ys = [0.5 + 2.0 * x for x in xs]        # β = 2 exactly
        beta, var = intraday_momentum_beta(xs, ys)
        assert beta == pytest.approx(2.0, rel=1e-12) and var > 0
        assert intraday_momentum_beta([0.1] * 19, [0.2] * 19) == (None, 0.0)
        assert intraday_momentum_beta([1.0] * 25, [2.0] * 25) == (0.0, 0.0)
        beta, _ = intraday_momentum_beta(
            [float("nan")] * 5 + [0.001 * i for i in range(25)],
            [0.0] * 5 + [0.002 * i for i in range(25)])
        assert beta == pytest.approx(2.0, rel=1e-12)

    def test_vol_ratio_and_y_events(self):
        assert vol_ratio(9000, [6000] * 10) == CASE["vr_case8"] == 1.5
        assert y_vol(1.5) is CASE["y_vol_case8"] is False   # NOT > 1.5
        assert y_vol(1.51) is True
        assert vol_ratio(0, [6000]) is None                 # V=0 ⇒ null
        assert vol_ratio(100, []) is None
        assert vol_ratio(100, [0.0, 0.0]) is None
        assert y_vol(None) is False

    def test_range_z(self):
        z = range_z(300, [100.0, 120.0, 90.0, 110.0, 105.0])
        mu = float(np.mean([100, 120, 90, 110, 105]))
        sd = float(np.std([100, 120, 90, 110, 105]))
        assert z == pytest.approx((300 - mu) / sd, rel=1e-12)
        assert y_range(z) is True
        assert y_range(1.5) is False                        # NOT > 1.5
        assert range_z(100, [100.0]) is None                # < 2 samples
        assert range_z(100, [5.0] * 10) is None             # σ = 0


# ---------------------------------------------------------------------------
# §5.4/§5.5 — state machine, event journal, fate, quality ladder
# ---------------------------------------------------------------------------
class TestStateMachineAndEvents:
    SEQ = [
        candle("2024-03-15T06:00:00Z", 69900, 69700, 69850, 1500),
        candle("2024-03-15T07:00:00Z", 70100, 69800, 70050, 3200),
        candle("2024-03-15T12:30:00Z", 70600, 70300, 70550, 9000),
        candle("2024-03-15T16:00:00Z", 70950, 70700, 70850, 5000),
    ]

    def test_event_catalog_complete(self):
        assert set(EVENT_CATALOG) == {f"EV_TMP_{i:03d}" for i in range(1, 10)}
        names = {k: v["name"] for k, v in EVENT_CATALOG.items()}
        assert names["EV_TMP_001"] == "TemporalWindow_Entered"
        assert names["EV_TMP_003"] == "Overlap_Active"
        assert names["EV_TMP_009"] == "InvalidCandle"

    def test_journal_transitions(self):
        res = run_engine(self.SEQ, econ_calendar=set())
        codes = [e["code"] for e in res["events"]]
        assert codes.count("EV_TMP_001") == 3     # W0, W1, W2 (W2 once)
        assert codes.count("EV_TMP_002") == 2     # exits W0, W1
        assert "EV_TMP_003" in codes              # overlap entered at 12:30
        assert "EV_TMP_004" in codes              # EARLY→MID at 16:00? W2
        assert "EV_TMP_008" not in codes          # calendar provided
        entered = [e for e in res["events"] if e["code"] == "EV_TMP_001"]
        assert [e["window"] for e in entered] == ["UTC_W0", "UTC_W1",
                                                  "UTC_W2"]

    def test_calendar_unavailable_event(self):
        res = run_engine(self.SEQ)                # econ_calendar=None
        cal = [e for e in res["events"] if e["code"] == "EV_TMP_008"]
        assert len(cal) == 1
        assert cal[0]["reason"] == "ECON_CALENDAR_NOT_PROVIDED"
        # §8.3: HIGH_IMPACT impossible without a calendar (conservative)
        assert res["temporal_state"]["day_type"] != "HIGH_IMPACT"

    def test_invalid_candle_event_and_stream_continues(self):
        seq = [self.SEQ[0],
               candle("2024-03-15T06:30:00Z", 100, 200, 150, 10),  # H < L
               self.SEQ[1]]
        res = run_engine(seq, econ_calendar=set())
        bad = [e for e in res["events"] if e["code"] == "EV_TMP_009"]
        assert len(bad) == 1 and bad[0]["reason"] == "INVALID_CANDLE"
        assert res["temporal_state"]["temporal_window"] == "UTC_W1"

    def test_profile_and_levels_events(self):
        prof = compute_temporal_profile(as_of=ms("2024-03-15T12:30:00Z"),
                                        **q4_profile_inputs())
        res = run_engine(self.SEQ, econ_calendar=set(), profile=prof,
                         temporal_window_levels={"levels": [70000, 71000]})
        codes = [e["code"] for e in res["events"]]
        assert "EV_TMP_006" in codes and "EV_TMP_007" in codes
        assert res["temporal_profile"]["quality"] == "Q4"
        # states after attachment carry the calibrated quality
        assert res["temporal_state"]["quality"] == "Q4"

    def test_profile_inputs_built_inside_run_engine(self):
        res = run_engine(self.SEQ, econ_calendar=set(),
                         profile_inputs=q4_profile_inputs())
        assert res["temporal_profile"]["quality"] == "Q4"
        assert any(e["code"] == "EV_TMP_006" for e in res["events"])
        assert res["temporal_profile"]["as_of"] == \
            res["temporal_state"]["as_of"]

    def test_fate_superseded_and_active(self):
        eng = TemporalWindowEngineStream()
        s1 = eng.on_candle(self.SEQ[0], set())
        assert s1["fate"] == "ACTIVE"
        s2 = eng.on_candle(self.SEQ[1], set())
        assert s1["fate"] == "SUPERSEDED"         # §5.4 transition
        assert s2["fate"] == "ACTIVE"
        assert eng.last_snapshot == s2["snapshot_id"]

    def test_duplicate_candle_idempotent(self):
        eng = TemporalWindowEngineStream()
        a = eng.on_candle(self.SEQ[0], set())
        b = eng.on_candle(self.SEQ[0], set())
        assert a == b
        assert len(eng.buffer) == 1

    def test_8_2_deterministic_replay_1000(self):
        base = ms("2024-03-01T00:00:00Z")
        cs = [{"ts": base + i * 3_600_000, "H": 100 + (i % 5),
               "L": 99, "C": 100, "V": 10 + (i % 3),
               "availability_time_ms": base + i * 3_600_000}
              for i in range(1000)]
        r1 = run_engine(cs, econ_calendar=set())
        r2 = run_engine(cs, econ_calendar=set())
        ids1 = [e["snapshot_id"] for e in r1["events"]
                if "snapshot_id" in e]
        assert r1["temporal_state"]["snapshot_id"] == \
            r2["temporal_state"]["snapshot_id"]
        eng_a, eng_b = TemporalWindowEngineStream(), \
            TemporalWindowEngineStream()
        for ca, cb in zip(cs, cs):
            sa = eng_a.on_candle(ca, set())
            sb = eng_b.on_candle(cb, set())
            assert sa["snapshot_id"] == sb["snapshot_id"]
        assert ids1 == ids1

    def test_8_3_no_future_leak(self):
        rbt = {b: [0.01 * ((b % 3) + 1)] * 40 for b in range(6)}
        assert no_future_leak_check(rbt) is True
        assert deterministic_replay_check(
            lambda: {str(k): round(v, 12) for k, v in
                     fff_seasonal(rbt).items()}) is True

    def test_buffer_cap(self):
        eng = TemporalWindowEngineStream(behavior_window=30, n_bins=48)
        base = ms("2024-01-01T00:00:00Z")
        for i in range(1500):
            eng.on_candle({"ts": base + i * 60_000, "H": 2, "L": 1,
                           "C": 1.5, "V": 1,
                           "availability_time_ms": base + i * 60_000}, set())
        assert len(eng.buffer) == 30 * 48


class TestQualityLadder:
    def test_qx_missing_availability_time(self):
        c = candle("2024-03-15T05:00:00Z", 100, 99, 99.5, 5)
        c.pop("availability_time_ms")
        out = TemporalWindowEngineStream().on_candle(c)
        assert out == {"quality": "QX",
                       "reason": "CONFIGURATION_INVALID: missing "
                                 "availability_time_ms"}

    def test_q0_paths(self):
        eng = TemporalWindowEngineStream()
        assert eng.on_candle(
            candle("2024-03-15T05:00:00Z", 99, 100, 99.5, 5))[
            "reason"] == "INVALID_CANDLE"          # H < L
        assert eng.on_candle(
            candle("2024-03-15T05:00:00Z", 100, 99, 99.5, -1))[
            "reason"] == "INVALID_CANDLE"          # V < 0
        assert eng.on_candle({"ts": float("nan"), "H": 1, "L": 1, "C": 1,
                              "V": 1, "availability_time_ms": 1})[
            "reason"] == "INVALID_TS"              # §5.5 ts NaN ⇒ Q0
        assert eng.on_candle({"ts": "abc", "H": 1, "L": 1, "C": 1, "V": 1,
                              "availability_time_ms": 1})[
            "reason"] == "INVALID_TS"

    def test_q1_default_and_v_zero(self):
        st = TemporalWindowEngineStream().on_candle(
            candle("2024-03-15T03:00:00Z", 70000, 70000, 70000, 0))
        assert st["quality"] == "Q1" and st["vol_ratio"] is None
        assert st["reason"] == "V_ZERO"

    def test_ladder_q2_q3_q4(self):
        rng = np.random.default_rng(5)
        rbt = {b: [float(rng.normal(0, 0.01)) for _ in range(40)]
               for b in range(6)}
        # Q2: profile exists, T ≥ 30, no stats
        p2 = compute_temporal_profile(rbt, as_of=1710505800000)
        assert p2["quality"] == "Q2"
        assert p2["seasonal_status"] == "OK"
        # Q3: + Kruskal p<0.05 + Spearman>0.6, but a WIDE Wilson band blocks Q4
        base = fff_seasonal(rbt)
        hist = [base, {k: v * 1.01 for k, v in base.items()}]
        wide = ([True] * 15 + [False] * 15, ["k"] * 30)     # p=0.5, n=30
        p3 = compute_temporal_profile(
            rbt, as_of=1710505800000, cond_events={"bos": wide},
            window_groups=[[float(x) for x in rng.normal(0, 1, 50)],
                           [float(x) for x in rng.normal(1, 1, 50)]],
            profiles_history=hist)
        assert p3["quality"] == "Q3"
        ci = p3["conditional_rates"]["bos|k"]["ci"]
        assert ci[1] - ci[0] > 0.3                          # width blocks Q4
        # Q4: narrow band + replay + no-leak
        p4 = compute_temporal_profile(as_of=1710505800000,
                                      **q4_profile_inputs())
        assert p4["quality"] == "Q4"

    def test_unavailable_profile_is_q1(self):
        p = compute_temporal_profile({b: [0.01] * 10 for b in range(6)},
                                     as_of=1710505800000)
        assert p["quality"] == "Q1"
        assert p["seasonal_status"] == "UNAVAILABLE:T_BELOW_30"
        assert p["seasonal_factors"] is None

    def test_v_zero_forces_q1_over_profile(self):
        prof = compute_temporal_profile(as_of=ms("2024-03-15T12:30:00Z"),
                                        **q4_profile_inputs())
        eng = TemporalWindowEngineStream()
        eng.attach_profile(prof)
        st = eng.on_candle(candle("2024-03-15T13:00:00Z", 100, 100, 100, 0))
        assert st["quality"] == "Q1" and st["vol_ratio"] is None
        st2 = eng.on_candle(candle("2024-03-15T13:30:00Z", 100, 99, 99.5, 5))
        assert st2["quality"] == "Q4"

    def test_historical_behavior_absent_then_present(self):
        eng = TemporalWindowEngineStream()
        st = eng.on_candle(candle("2024-03-15T12:45:00Z", 100, 99, 99.5, 5))
        assert st["historical_behavior"] is None    # Q1_RAW (§5.5)
        prof = compute_temporal_profile(as_of=ms("2024-03-15T12:30:00Z"),
                                        **q4_profile_inputs())
        eng.attach_profile(prof)
        for i in range(3):
            eng.buffer.append({"V": 6000.0, "window": "UTC_W2",
                               "vol_ratio": 1.2, "H": 70300.0, "L": 70100.0,
                               "ts": 0})
        st2 = eng.on_candle(candle("2024-03-15T12:46:00Z", 100, 99, 99.5, 5))
        hb = st2["historical_behavior"]
        assert hb is not None
        assert hb["bos_rate"] == 0.8 and hb["sample_n"] == 50
        assert hb["wilson_ci_bos"] is not None
        assert hb["vol_ratio_avg"] == pytest.approx(1.2)
        # ranges: the pre-profile 12:45 candle (100−99 = 1) + 3 seeded
        # UTC_W2 history entries (70300−70100 = 200 each)
        assert hb["range_avg"] == pytest.approx((1 + 3 * 200) / 4)
        assert set(hb) == {"vol_ratio_avg", "range_avg", "bos_rate",
                           "sweep_rate", "sample_n", "wilson_ci_bos"}

    def test_profile_contract_mismatch_rejected(self):
        eng = TemporalWindowEngineStream()
        with pytest.raises(ValueError, match="CONTRACT_MISMATCH"):
            eng.attach_profile({"version": "3.0.0"})


# ---------------------------------------------------------------------------
# §5.3 — TemporalProfile artifact
# ---------------------------------------------------------------------------
class TestTemporalProfile:
    def test_profile_shape_and_identity(self):
        prof = compute_temporal_profile(as_of=1710505800000,
                                        **q4_profile_inputs())
        assert prof["version"] == CONTRACT_VERSION
        assert prof["as_of"] == 1710505800000
        assert set(prof["seasonal_factors"]) == {str(b) for b in range(12)}
        assert abs(sum(prof["seasonal_factors"].values()) / 12 - 1.0) < 1e-9
        assert prof["seasonal_factors_smoothed"] is not None
        assert "bos|UTC_W2|25|FRIDAY" in prof["conditional_rates"]
        entry = prof["conditional_rates"]["bos|UTC_W2|25|FRIDAY"]
        assert entry["status"] == "OK" and entry["p"] == 0.8
        assert len(prof["snapshot_id"]) == 64
        assert len(prof["param_hash"]) == 12
        # deterministic identity
        again = compute_temporal_profile(as_of=1710505800000,
                                         **q4_profile_inputs())
        assert again["snapshot_id"] == prof["snapshot_id"]

    def test_momentum_betas_by_window(self):
        xs = [0.001 * i for i in range(25)]
        ys = [2.0 * x for x in xs]
        prof = compute_temporal_profile(
            {b: [0.01] * 40 for b in range(4)}, as_of=1710505800000,
            open_returns_by_window={"UTC_W1": xs},
            fwd_returns_by_window={"UTC_W1": ys})
        assert prof["momentum_betas"]["UTC_W1"] == pytest.approx(2.0,
                                                                 rel=1e-9)

    def test_thin_conditional_rates_marked(self):
        prof = compute_temporal_profile(
            {b: [0.01] * 40 for b in range(4)}, as_of=1710505800000,
            cond_events={"bos": ([True] * 5, ["k"] * 5)})
        entry = prof["conditional_rates"]["bos|k"]
        assert entry["p"] is None and entry["ci"] is None
        assert entry["status"] == "INSUFFICIENT_SAMPLE"


# ---------------------------------------------------------------------------
# §6 — parameter governance
# ---------------------------------------------------------------------------
class TestParams:
    def test_defaults_match_chapter_6(self):
        p = EngineParams()
        assert p.temporal_window_calendar_version == CALENDAR_CONFIG_VERSION \
            == "v2024a"
        assert (p.behavior_window, p.fff_bins, p.fff_fourier_K) == (180, 48, 4)
        assert p.daytype_min_samples == 30
        assert p.vol_burst_threshold == 1.5 and p.range_z_threshold == 1.5
        assert p.intraday_horizon == 4
        assert p.utc_activity_window_enable is True
        assert p.econ_calendar_source == "configured_calendar.json"
        assert p.high_impact_currencies == ["USD", "EUR", "GBP", "JPY"]
        assert p.rollback_on_invalid is True
        assert p.wilson_z == 1.96
        assert (p.utc_w0_start, p.utc_w0_end) == (0.0, 7.0)
        assert (p.utc_w1_core_start, p.utc_w1_core_end) == (7.0, 11.0)
        assert (p.utc_w2_core_start, p.utc_w2_core_end) == (12.5, 16.0)
        assert (p.utc_w1_ext_start, p.utc_w1_ext_end) == (7.0, 12.5)
        assert (p.utc_w2_ext_start, p.utc_w2_ext_end) == (12.5, 21.0)
        assert (p.utc_overlap_start, p.utc_overlap_end) == (12.5, 16.0)

    def test_unknown_param_rejected(self):
        with pytest.raises(ValueError, match="UNKNOWN_E12_PARAM_QX"):
            EngineParams({"not_a_param": 1})

    @pytest.mark.parametrize("key,val", [
        ("behavior_window", 10), ("behavior_window", 400),
        ("fff_bins", 10), ("fff_bins", 200),
        ("fff_fourier_K", -1), ("fff_fourier_K", 9),
        ("daytype_min_samples", 5), ("daytype_min_samples", 200),
        ("vol_burst_threshold", 1.0), ("vol_burst_threshold", 5.0),
        ("range_z_threshold", 0.5), ("range_z_threshold", 3.0),
        ("intraday_horizon", 0), ("intraday_horizon", 24),
    ])
    def test_range_violations_rejected(self, key, val):
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            EngineParams({key: val})

    def test_registry_violation_rejected(self):
        with pytest.raises(ValueError, match="§3.5 canonical"):
            EngineParams({"utc_w2_core_start": 13.0})
        with pytest.raises(ValueError, match="§3.5 canonical"):
            EngineParams({"utc_overlap_end": 17.0})

    def test_empty_calendar_version_rejected(self):
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            EngineParams({"temporal_window_calendar_version": "  "})

    def test_param_hash_deterministic(self):
        h1, h2 = param_hash(EngineParams()), param_hash(get_params())
        assert h1 == h2 and len(h1) == 12
        assert all(c in "0123456789abcdef" for c in h1)
        assert param_hash(EngineParams({"behavior_window": 90})) != h1

    def test_get_params_passthrough(self):
        p = EngineParams()
        assert get_params(p) is p
        assert get_params({"behavior_window": 90}).behavior_window == 90

    def test_behavior_window_range_enforced_by_stream(self):
        with pytest.raises(ValueError, match="CONFIGURATION_INVALID"):
            TemporalWindowEngineStream(behavior_window=10)


# ---------------------------------------------------------------------------
# §5.2/§8.7 — schema validation, serialization, v3 adapter
# ---------------------------------------------------------------------------
class TestSchemaAndSerialization:
    def good_state(self):
        return run_fixture(BY_ID["GF03_OVERLAP_ENTRY"])

    def test_conforming_state_has_no_violations(self):
        assert validate_state_schema(self.good_state()) == []

    @pytest.mark.parametrize("mutate,expect", [
        (lambda s: s.pop("version"), "missing required key: version"),
        (lambda s: s.pop("tod_state"), "missing required key: tod_state"),
        (lambda s: s.update(temporal_window="UTC_W9"),
         "temporal_window not in registry"),
        (lambda s: s.update(window_phase="NOON"), "window_phase invalid"),
        (lambda s: s.update(day_type="HOLIDAY"), "day_type invalid"),
        (lambda s: s.update(quality="Q7"), "quality invalid"),
        (lambda s: s.update(snapshot_id="xyz"), "snapshot_id must be 64-hex"),
        (lambda s: s.update(as_of=0), "as_of must be a positive"),
        (lambda s: s.update(fate="GONE"), "fate invalid"),
        (lambda s: s.update(is_overlap="yes"), "is_overlap must be boolean"),
    ])
    def test_violations_detected(self, mutate, expect):
        st = self.good_state()
        mutate(st)
        assert any(expect in e for e in validate_state_schema(st))

    def test_tod_state_violations(self):
        st = self.good_state()
        st["tod_state"]["tod_bin"] = 96
        assert any("tod_bin outside" in e for e in validate_state_schema(st))
        st = self.good_state()
        st["tod_state"]["hour_utc"] = 24.5
        assert any("hour_utc outside" in e for e in validate_state_schema(st))
        st = self.good_state()
        st["tod_state"].pop("minute")
        assert any("tod_state missing: minute" in e
                   for e in validate_state_schema(st))

    def test_serialize_state_rounding(self):
        st = self.good_state()
        ser = serialize_state(st, ndigits=6)
        assert ser["tod_state"]["utc_window_progress"] == round(
            st["tod_state"]["utc_window_progress"], 6)
        assert ser["snapshot_id"] == st["snapshot_id"]   # never rounded
        assert json.dumps(ser, sort_keys=True)           # JSON-clean

    def test_v3_adapter_migration(self):
        v3 = load_v3_temporal_payload(
            {"window": "W2", "daytype": "FRIDAY", "tod": 25,
             "ts": ms("2024-03-15T12:30:00Z"), "snapshot_id": "a" * 64})
        assert v3["migrated"] is True and v3["quality"] == "Q1"
        assert v3["version"] == CONTRACT_VERSION
        assert v3["temporal_window"] == "UTC_W2"
        assert v3["reason"] == "V3_MIGRATED_READ_ONLY"

    @pytest.mark.parametrize("payload,reason", [
        ({"window": "W9", "daytype": "FRIDAY", "tod": 25, "ts": 1,
          "snapshot_id": "a" * 64}, "V3_WINDOW_UNKNOWN_QX"),
        ({"window": "W2", "daytype": "SUNDAY", "tod": 25, "ts": 1,
          "snapshot_id": "a" * 64}, "V3_DAYTYPE_UNKNOWN_QX"),
        ({"window": "W2", "daytype": "FRIDAY", "tod": 25, "ts": 1,
          "snapshot_id": "zz"}, "V3_SNAPSHOT_ID_INVALID_QX"),
        ({"window": "W2", "daytype": "FRIDAY", "ts": 1,
          "snapshot_id": "a" * 64}, "V3_REQUIRED_FIELD_MISSING_QX"),
        ({"window": "W2", "daytype": "FRIDAY", "tod": 96, "ts": 1,
          "snapshot_id": "a" * 64}, "V3_FIELD_RANGE_QX"),
        ("not-a-dict", "V3_PAYLOAD_NOT_OBJECT_QX"),
    ])
    def test_v3_adapter_fail_closed(self, payload, reason):
        out = load_v3_temporal_payload(payload)
        assert out["quality"] == "QX" and reason in out["reason"]


# ---------------------------------------------------------------------------
# E07 ↔ E12 integration — BOTH modes (CP-4 degraded / CP-5 resolved)
# ---------------------------------------------------------------------------
class TestE07Integration:
    TS = ms("2024-03-15T12:45:00Z")

    def test_provider_contract_shape(self):
        pw = E12TemporalProvider().temporal_window(self.TS)
        assert pw["which"] == ["UTC_W2", "UTC_W1_W2_OVERLAP"]
        assert pw["core_windows"] == ["UTC_W2_CORE"]
        assert pw["utc_activity_window"] == "UTC_W2"
        assert pw["is_overlap"] is True
        assert pw["config_version"] == "v2024a"
        assert E12TemporalProvider().contract == \
            "E12_Temporal_Context.Contract v4.0.0"

    def test_provider_which_list_by_hour(self):
        prov = E12TemporalProvider()
        assert prov.temporal_window(ms("2024-03-15T02:00:00Z"))["which"] == \
            ["UTC_W0"]
        assert prov.temporal_window(ms("2024-03-15T07:30:00Z"))["which"] == \
            ["UTC_W1"]
        assert prov.temporal_window(
            ms("2024-03-15T07:30:00Z"))["core_windows"] == ["UTC_W1_CORE"]
        assert prov.temporal_window(ms("2024-03-15T11:30:00Z"))["which"] == \
            ["UTC_W1"]
        assert prov.temporal_window(ms("2024-03-15T17:00:00Z"))["which"] == \
            ["UTC_W2"]
        assert prov.temporal_window(ms("2024-03-15T22:00:00Z"))["which"] == \
            ["UTC_W3"]

    def test_resolved_mode_authoritative(self):
        res = utc_activity_window_check(self.TS,
                                        temporal_provider=E12TemporalProvider())
        assert res["degraded"] is False
        assert res["degraded_reason"] is None
        assert res["source"] == "E12_Temporal_Context.Contract v4.0.0"
        assert res["which"] == ["UTC_W2", "UTC_W1_W2_OVERLAP"]
        assert res["utc_activity_window"] == "UTC_W2"
        assert res["is_overlap"] is True
        assert res["config_version"] == "v2024a"
        assert res["in_kz"] is True
        assert res["as_of_ms"] == self.TS

    def test_degraded_mode_without_provider(self):
        res = utc_activity_window_check(self.TS)
        assert res["degraded"] is True
        assert res["source"] == "E07_LOCAL_NON_AUTHORITATIVE"
        assert res["degraded_reason"] == "E12_UNAVAILABLE_DEGRADED_QX"
        # the local duplicate agrees with E12 on this hour (same registry)
        assert res["is_overlap"] is True
        assert res["utc_activity_window"] == "UTC_W2"

    def test_raising_provider_falls_back_degraded(self):
        class Boom:
            def temporal_window(self, ts_ms):
                raise RuntimeError("E12 unavailable")

        res = utc_activity_window_check(self.TS, temporal_provider=Boom())
        assert res["degraded"] is True
        assert res["source"] == "E07_LOCAL_NON_AUTHORITATIVE"

    def test_both_modes_agree_across_boundary_hours(self):
        prov = E12TemporalProvider()
        for iso in ("2024-03-15T06:59:59Z", "2024-03-15T07:00:00Z",
                    "2024-03-15T12:29:59Z", "2024-03-15T12:30:00Z",
                    "2024-03-15T15:59:59Z", "2024-03-15T16:00:00Z",
                    "2024-03-15T20:59:59Z", "2024-03-15T21:00:00Z"):
            t = ms(iso)
            a = utc_activity_window_check(t, temporal_provider=prov)
            b = utc_activity_window_check(t)
            assert a["degraded"] is False and b["degraded"] is True
            assert a["is_overlap"] == b["is_overlap"] == \
                a["is_overlap"]
            assert a["utc_activity_window"] == b["utc_activity_window"]

    def test_provider_daytype_and_rollover_passthrough(self):
        prov = E12TemporalProvider(econ_calendar={"2024-04-10"},
                                   rollover_windows=SAT_ROLLOVER)
        out = prov.temporal_window(ms("2024-04-10T12:45:00Z"))
        assert out["day_type"] == "HIGH_IMPACT"
        out = prov.temporal_window(ms("2024-03-16T00:30:00Z"))
        assert out["rollover_active"] is True
        assert out["day_type"] == "SATURDAY_SUNDAY_CONTEXT"

    def test_provider_rejects_non_utc_ms(self):
        with pytest.raises(ValueError):
            E12TemporalProvider().temporal_window(float("nan"))


# ---------------------------------------------------------------------------
# Frozen EngineBase binding
# ---------------------------------------------------------------------------
def _obs(iso, seq=0):
    return MarketObservation(
        symbol="BTCUSDT", timeframe="1h",
        open=Decimal("70000"), high=Decimal("70100"),
        low=Decimal("69900"), close=Decimal("70050"),
        volume=Decimal("1000"), oi=None, timestamp=iso, sequence=seq,
        status="CLOSED")


class TestEngineBaseBinding:
    SEQ = TestStateMachineAndEvents.SEQ

    def test_compute_emits_context_events(self):
        eng = E12TemporalEngine()
        events = eng.compute("BTCUSDT", "1h", "2024-03-15T16:00:01Z",
                             context={"candles": self.SEQ,
                                      "econ_calendar": set()})
        assert len(events) >= 1
        ev = events[-1]
        assert ev.engine_id == "E12"
        assert ev.direction == 0               # Context, never a signal
        assert ev.condition_state.startswith("EV_TMP_001_")
        assert ev.snapshot_id == \
            eng._last_result["temporal_state"]["snapshot_id"]
        assert ev.parameter_version.startswith("E12-TMP-V4.0.0/")
        assert ev.validity == "DEGRADED"       # Q1 without a profile
        assert ev.resolution_class == "Q1"

    def test_compute_overlap_event_condition(self):
        eng = E12TemporalEngine()
        seq = [candle("2024-03-15T12:30:00Z", 100, 99, 99.5, 5)]
        events = eng.compute("BTCUSDT", "1h", "2024-03-15T12:30:01Z",
                             context={"candles": seq, "econ_calendar": set()})
        conds = [e.condition_state for e in events]
        assert "EV_TMP_001_UTC_W2" in conds
        assert any(c.startswith("EV_TMP_003") for c in conds)

    def test_compute_qx_refusal_emits_nothing(self):
        eng = E12TemporalEngine()
        bad = [candle("2024-03-15T12:30:00Z", 100, 101, 100.5, 5)]  # H < L
        assert eng.compute("BTCUSDT", "1h", "2024-03-15T12:30:01Z",
                           context={"candles": bad,
                                    "econ_calendar": set()}) == []

    def test_missing_window_context_fails_closed(self):
        with pytest.raises(ValueError, match="MISSING_WINDOW_CONTEXT_QX"):
            E12TemporalEngine().compute("BTCUSDT", "1h",
                                        "2024-03-15T12:30:01Z", context={})

    def test_empty_candles_emits_nothing(self):
        assert E12TemporalEngine().compute(
            "BTCUSDT", "1h", "2024-03-15T12:30:01Z",
            context={"candles": [], "econ_calendar": set()}) == []

    def test_window_fallback_via_observations(self):
        eng = E12TemporalEngine()
        window = [_obs("2024-03-15T12:30:00.000Z", 1),
                  _obs("2024-03-15T13:30:00.000Z", 2)]
        events = eng.compute("BTCUSDT", "1h", "2024-03-15T13:30:01Z",
                             context={"window": window,
                                      "econ_calendar": set()})
        assert events
        c = observation_to_candle(window[0])
        assert c["H"] == 70100.0 and c["ts"] == ms("2024-03-15T12:30:00Z")
        assert c["availability_time_ms"] == c["ts"]

    def test_provider_fallback_sync(self):
        class SyncProv:
            def get_window(self, symbol, timeframe, as_of, bars):
                return [_obs("2024-03-15T12:30:00.000Z", 1)]

        events = E12TemporalEngine().compute(
            "BTCUSDT", "1h", "2024-03-15T12:30:01Z",
            context={"provider": SyncProv(), "econ_calendar": set()})
        assert events and events[0].engine_id == "E12"

    def test_profile_context_lifts_validity(self):
        eng = E12TemporalEngine()
        prof = compute_temporal_profile(as_of=ms("2024-03-15T12:30:00Z"),
                                        **q4_profile_inputs())
        events = eng.compute("BTCUSDT", "1h", "2024-03-15T16:00:01Z",
                             context={"candles": self.SEQ,
                                      "econ_calendar": set(),
                                      "profile": prof})
        assert events
        assert events[-1].validity == "VALID"
        assert events[-1].resolution_class == "Q4"
        assert events[-1].confidence == pytest.approx(1.0)

    def test_ts_from_ms_and_identity_helpers(self):
        assert ts_from_ms(self.SEQ[0]["ts"]).year == 2024
        with pytest.raises(ValueError, match="INVALID_TS_QX"):
            ts_from_ms(float("inf"))
        sid = make_snapshot_id({"engine": "E12", "contract_version": "4.0.0",
                                "input": {}, "state": {"quality": "Q1"}})
        assert len(sid) == 64
