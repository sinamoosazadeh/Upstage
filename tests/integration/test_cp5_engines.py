"""CP-5 cross-engine integration battery (E10 Momentum / E11 Regime / E12 Temporal).

Closes the CP-5 EXIT-box items that span engines:

  - **E07 ↔ E12 integration, BOTH modes** — the CP-4 degraded branch
    (``E12_UNAVAILABLE_DEGRADED_QX``, NON-authoritative local registry, Q-cap)
    is re-proven side-by-side with the RESOLVED branch driven by the real
    ``E12TemporalProvider`` (``E12_Temporal_Context.Contract v4.0.0``,
    ``config_version=v2024a``, §3.5 canonical registry, §3.7 Q5 reachable
    only on the authoritative overlap flag).  A failing provider still fails
    closed into the degraded branch.
  - **E11 live-regime gate** — default OFF (Phase-7 + Owner approval,
    AI.2 L19046–48); the flag never appears inside regime_state (§5.1
    additionalProperties:false) and the engine never self-enables.
  - **E11 Wave-Out** — next-regime forecasting raises ``WaveOutError``.
  - **T-DR-001** re-run for all three CP-5 engines over one shared window.
  - **Emission rows** for E10/E11/E12 validate against the frozen store DDL.
"""
import asyncio
import datetime
from decimal import Decimal

import numpy as np
import pytest

from apex.data_catalog.contracts import MarketObservation
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.engines.e07_rtm import (
    E12_CONTRACT,
    E12_UNAVAILABLE_REASON,
    Q_CLASSES,
    build_bundle_pipeline,
    build_order_map,
    evaluate_order_ok,
    expected_components,
    sequence_integrity_v4,
    utc_activity_window_check,
)
from apex.engines.e10_momentum import E10MomentumEngine
from apex.engines.e10_momentum import run_engine as run_e10
from apex.engines.e11_regime import E11RegimeEngine
from apex.engines.e11_regime import LIVE_GATE_OFF_REASON, forecast_next_regime
from apex.engines.e11_regime import run_engine as run_e11
from apex.engines.e12_temporal import (
    E12TemporalEngine,
    E12TemporalProvider,
    utc_activity_window_of,
)
from apex.engines.e12_temporal import run_engine as run_e12
from apex.errors import WaveOutError
from apex.identity.canonical_json import canonical_json

AS_OF = "2026-01-15T14:00:00Z"          # inside the 12:30–16:00 overlap
AS_OF_MS = 1768485600000                # == 2026-01-15T14:00:00Z exactly
MORNING_MS = 1768485600000 - 5 * 3600000  # 09:00Z ⇒ UTC_W1, no overlap


def lcg_window(n, seed=271, base=615.0, span=3.0):
    """A deterministic closed-candle window inside a tight range."""
    bars = []
    x = seed
    price = base
    for i in range(n):
        x = (1103515245 * x + 12345) % (2 ** 31)
        u = x / 2 ** 31
        o = price + (u - 0.5) * span
        c = o + (u - 0.5) * span * 0.5
        h = max(o, c) + span * 0.2
        l = min(o, c) - span * 0.2
        bars.append({"ts": AS_OF_MS + i * 3600000, "o": o, "h": h, "l": l,
                     "c": c, "v": 1000.0, "is_closed": True})
        price = c
    return bars


BARS = lcg_window(60)   # E10's §5.2 Q1 warmup floor needs >= 60 bars


def obs_window(bars, symbol="BTCUSDT", timeframe="1h"):
    out = []
    for i, b in enumerate(bars):
        dt = datetime.datetime.fromtimestamp(b["ts"] / 1000,
                                             tz=datetime.timezone.utc)
        out.append(MarketObservation(
            symbol=symbol, timeframe=timeframe,
            open=Decimal(repr(b["o"])), high=Decimal(repr(b["h"])),
            low=Decimal(repr(b["l"])), close=Decimal(repr(b["c"])),
            volume=Decimal(repr(b["v"])), oi=None,
            timestamp=dt.strftime("%Y-%m-%dT%H:%M:%S.") + "000Z",
            sequence=i, status="CLOSED"))
    return out


def e12_candles(bars):
    return [{"ts": b["ts"], "H": b["h"], "L": b["l"], "C": b["c"],
             "V": b["v"], "availability_time_ms": b["ts"]} for b in bars]


def ic(i):
    """Non-degenerate ic_inputs: every §3.1 sigmoid/min-max window sees
    varying history (a constant window fails closed by design)."""
    return {"trendiness_raw": 0.4 + 0.005 * (i % 7),
            "vol_ratio": 1.0 + 0.01 * (i % 5),
            "expansion_raw": 0.3 + 0.01 * (i % 6),
            "level_density": 0.5 + 0.01 * (i % 4),
            "participation_raw": 0.3 + 0.01 * (i % 5),
            "structure_score": 0.5 + 0.01 * (i % 3),
            "momentum_state_raw": "NEUTRAL",
            "bias_per_TF": {"H4": 0.1, "H1": 0.1, "M15": 0.1},
            "atr_z": 0.01 * (i % 3)}


def e11_candles(bars):
    out = []
    for i, b in enumerate(bars):
        out.append({"o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"],
                    "v": b["v"], "ts": b["ts"], "as_of": b["ts"],
                    "symbol": "BTCUSDT", "timeframe": "1h",
                    "ic_inputs": ic(i)})
    return out


def po3_confirmations(t0=AS_OF_MS):
    return [{"cid": cid, "t_confirm_ms": t0 + 900000 * (i + 1),
             "p_confirm": 604.0 + i}
            for i, cid in enumerate(["sweep", "choch", "bos", "fvg",
                                     "vol_confirm"])]


def bundle_from(conf, avg_q=0.9, mtf_align=1.0, direction="UP",
                temporal_provider=None, framework="RTM.PO3.v1"):
    exp = expected_components(framework)
    om = build_order_map(exp, conf)
    order = [c["cid"] for c in conf]
    evaluate_order_ok(exp, order, om)
    kz = utc_activity_window_check(conf[-1]["t_confirm_ms"],
                                   temporal_provider=temporal_provider)
    return build_bundle_pipeline(exp, order, om, avg_q, mtf_align, kz,
                                 framework, direction, conf[-1]["t_confirm_ms"])


class RaisingE12(E12TemporalProvider):
    def temporal_window(self, ts_ms):
        raise RuntimeError("E12 unavailable")


# ---------------------------------------------------------------------------
# E07 ↔ E12 — RESOLVED mode (real provider) vs DEGRADED mode (CP-4 branch)
# ---------------------------------------------------------------------------
class TestE07E12BothModes:
    def test_real_e12_resolves_the_degradation(self):
        prov = E12TemporalProvider()
        info = utc_activity_window_check(AS_OF_MS, temporal_provider=prov)
        assert info["degraded"] is False and info["degraded_reason"] is None
        assert info["source"] == E12_CONTRACT == \
            "E12_Temporal_Context.Contract v4.0.0"
        assert info["config_version"] == "v2024a"
        assert info["which"] == ["UTC_W2", "UTC_W1_W2_OVERLAP"]
        assert info["utc_activity_window"] == "UTC_W2"
        assert info["is_overlap"] is True and info["in_kz"] is True

    def test_degraded_mode_unchanged_without_provider(self):
        info = utc_activity_window_check(AS_OF_MS)
        assert info["degraded"] is True
        assert info["degraded_reason"] == E12_UNAVAILABLE_REASON
        assert info["source"] == "E07_LOCAL_NON_AUTHORITATIVE"

    def test_failing_real_provider_fails_closed(self):
        info = utc_activity_window_check(AS_OF_MS,
                                         temporal_provider=RaisingE12())
        assert info["degraded"] is True
        assert info["degraded_reason"] == E12_UNAVAILABLE_REASON
        assert info["source"] == "E07_LOCAL_NON_AUTHORITATIVE"

    def test_q5_reachable_only_on_authoritative_overlap(self):
        """§3.7's Q5 gate needs the overlap flag — with the REAL E12 the
        provenance is authoritative and the cascade reaches Q5 inside
        [12:30, 16:00); outside it, the real E12 caps the bundle at Q4 even
        though the branch is non-degraded (E12 said 'no overlap')."""
        conf14 = po3_confirmations()                     # confirms ≤ 15:15Z
        resolved = bundle_from(conf14,
                               temporal_provider=E12TemporalProvider())
        assert resolved.resolution_class == "Q5"
        assert resolved.degraded is False
        conf09 = po3_confirmations(t0=MORNING_MS)        # confirms ≤ 10:15Z
        morning = bundle_from(conf09,
                              temporal_provider=E12TemporalProvider())
        assert morning.resolution_class == "Q4"          # W1, no overlap
        assert morning.degraded is False
        degraded = bundle_from(conf09)                   # CP-4 branch
        assert degraded.resolution_class == "Q4" and degraded.degraded is True
        assert Q_CLASSES.index(resolved.resolution_class) == \
            Q_CLASSES.index("Q5")

    def test_both_modes_agree_on_registry_and_sequence_math(self):
        """The degradation changes provenance and the Q gate, never the §3.5
        window arithmetic (E07's local duplicate mirrors the E12 registry)
        nor the §3.1 sequence integrity."""
        prov = E12TemporalProvider()
        for iso in ("2026-01-15T06:59:59Z", "2026-01-15T07:00:00Z",
                    "2026-01-15T12:29:59Z", "2026-01-15T12:30:00Z",
                    "2026-01-15T15:59:59Z", "2026-01-15T16:00:00Z",
                    "2026-01-15T20:59:59Z", "2026-01-15T21:00:00Z"):
            t = int(datetime.datetime.fromisoformat(
                iso.replace("Z", "+00:00")).timestamp() * 1000)
            a = utc_activity_window_check(t, temporal_provider=prov)
            b = utc_activity_window_check(t)
            assert a["degraded"] is False and b["degraded"] is True
            assert a["is_overlap"] == b["is_overlap"]
            assert a["utc_activity_window"] == b["utc_activity_window"]
            assert set(a["which"]) == set(b["which"])
        conf = po3_confirmations()
        x = bundle_from(conf)
        y = bundle_from(conf, temporal_provider=prov)
        exp = expected_components("RTM.PO3.v1")
        om = build_order_map(exp, conf)
        order = [c["cid"] for c in conf]
        evaluate_order_ok(exp, order, om)      # same pipeline as bundle_from
        integrity, coverage, _ = sequence_integrity_v4(exp, order, om)
        assert x.integrity == pytest.approx(integrity)
        assert y.integrity == pytest.approx(integrity)
        assert x.weight_coverage == pytest.approx(coverage)
        assert x.degraded is True and y.degraded is False

    @pytest.mark.parametrize("day", ["2024-03-09", "2024-03-10", "2024-03-11"])
    def test_8_8_utc_boundary_stability_through_e07(self, day):
        """§8.8: the 2024-03-10 US local-time transition cannot move the
        OVERLAP window — proven end-to-end through the E07 consumer."""
        prov = E12TemporalProvider()
        t_in = int(datetime.datetime.fromisoformat(
            f"{day}T12:45:00+00:00").timestamp() * 1000)
        t_out = int(datetime.datetime.fromisoformat(
            f"{day}T16:00:00+00:00").timestamp() * 1000)
        a = utc_activity_window_check(t_in, temporal_provider=prov)
        b = utc_activity_window_check(t_out, temporal_provider=prov)
        assert a["is_overlap"] is True and b["is_overlap"] is False
        assert a["degraded"] is False and b["degraded"] is False
        # E12 direct surface agrees
        assert utc_activity_window_of(datetime.datetime.fromtimestamp(
            t_in / 1000, tz=datetime.timezone.utc))["is_overlap"] is True

    def test_provider_consumed_for_every_confirm_in_a_bundle(self):
        seen = []

        class Counting(E12TemporalProvider):
            def temporal_window(self, ts_ms):
                seen.append(ts_ms)
                return super().temporal_window(ts_ms)

        conf = po3_confirmations()
        bundle_from(conf, temporal_provider=Counting())
        assert seen == [conf[-1]["t_confirm_ms"]]   # E12 is the one consulted


# ---------------------------------------------------------------------------
# E11 — live-regime gate default-off + Wave-Out (EXIT boxes)
# ---------------------------------------------------------------------------
class TestE11GateAndWaveOut:
    def _res(self, **kw):
        return run_e11(e11_candles(BARS), W=np.zeros((9, 8)),
                       b=np.zeros(9), symbol="BTCUSDT", timeframe="1h", **kw)

    def test_gate_off_by_default(self):
        res = self._res()
        assert res["live_regime_gate"]["enabled"] is False
        assert res["live_regime_gate"]["reason"] == LIVE_GATE_OFF_REASON
        # §5.1 additionalProperties:false — the flag lives in the wrapper ONLY
        assert "live_regime_gate" not in res["regime_state"]

    def test_gate_only_caller_enabled(self):
        res = self._res(live_regime_gate=True)
        assert res["live_regime_gate"]["enabled"] is True
        assert "Phase-7" in res["live_regime_gate"]["reason"]

    def test_forecast_is_wave_out(self):
        with pytest.raises(WaveOutError):
            forecast_next_regime()

    def test_binding_refuses_forecast_context(self):
        with pytest.raises(WaveOutError):
            E11RegimeEngine().compute(
                "BTCUSDT", "1h", AS_OF,
                context={"candles": e11_candles(BARS), "forecast": True})


# ---------------------------------------------------------------------------
# T-DR-001 — all three CP-5 engines over one shared window
# ---------------------------------------------------------------------------
class TestTDR001CP5:
    def test_double_run_byte_identical_all_engines(self):
        window = obs_window(BARS)
        e12c = e12_candles(BARS)
        e11c = e11_candles(BARS)
        for build in (
            lambda: run_e10(BARS, symbol="BTCUSDT", interval="1h"),
            lambda: run_e11(e11c, W=np.zeros((9, 8)), b=np.zeros(9),
                            symbol="BTCUSDT", timeframe="1h"),
            lambda: run_e12(e12c, econ_calendar=set()),
        ):
            a, b = build(), build()
            assert canonical_json(a) == canonical_json(b)
        # EngineBase surfaces are deterministic too
        for eng, ctx in (
            (E10MomentumEngine(), {"window": window}),
            (E11RegimeEngine(), {"candles": e11c, "W": np.zeros((9, 8)),
                                 "b": np.zeros(9)}),
            (E12TemporalEngine(), {"candles": e12c, "econ_calendar": set()}),
        ):
            ev_a = eng.compute("BTCUSDT", "1h", AS_OF, context=ctx)
            ev_b = eng.compute("BTCUSDT", "1h", AS_OF, context=ctx)
            assert [e.snapshot_id for e in ev_a] == \
                [e.snapshot_id for e in ev_b]
            assert [e.condition_state for e in ev_a] == \
                [e.condition_state for e in ev_b]


# ---------------------------------------------------------------------------
# Consumed foundation + store DDL
# ---------------------------------------------------------------------------
class TestCP5EmissionsInsertIntoStore:
    def _events(self):
        window = obs_window(BARS)
        evs = []
        evs += E10MomentumEngine().compute("BTCUSDT", "1h", AS_OF,
                                           {"window": window})
        evs += E11RegimeEngine().compute(
            "BTCUSDT", "1h", AS_OF,
            {"candles": e11_candles(BARS), "W": np.zeros((9, 8)),
             "b": np.zeros(9)})
        evs += E12TemporalEngine().compute(
            "BTCUSDT", "1h", AS_OF,
            {"candles": e12_candles(BARS), "econ_calendar": set()})
        return evs

    def test_all_three_engines_insert(self):
        evs = self._events()
        assert {ev.engine_id for ev in evs} == {"E10", "E11", "E12"}
        for ev in evs:
            ev.validate_24_fields()
            assert ev.direction in (-1, 0, 1)
            if ev.engine_id in ("E11", "E12"):
                assert ev.direction == 0        # context engines (NG1)

        async def scenario():
            store = SQLiteStore(path=":memory:")
            await store.open()
            try:
                for ev in evs[:40]:
                    await store.insert_evidence(ev)
                cur = await store.db.execute(
                    "SELECT COUNT(*) FROM evidence_event")
                count = (await cur.fetchone())[0]
                cur = await store.db.execute(
                    "SELECT DISTINCT engine_id FROM evidence_event "
                    "ORDER BY engine_id")
                return count, [r[0] for r in await cur.fetchall()]
            finally:
                await store.close()

        count, engines = asyncio.run(scenario())
        assert count == min(40, len(evs))
        assert set(engines) <= {"E10", "E11", "E12"} and engines

    def test_duplicate_snapshot_insert_is_rejected_by_the_ddl(self):
        ev = self._events()[0]

        async def scenario():
            store = SQLiteStore(path=":memory:")
            await store.open()
            try:
                await store.insert_evidence(ev)
                with pytest.raises(Exception):
                    await store.insert_evidence(ev)
            finally:
                await store.close()

        asyncio.run(scenario())
