"""CP-4 cross-engine integration battery (E07/E08/E09).

Covers the §8 clauses that span engines and the CP-4 EXIT-box checks:
  - E09 consumes E01 swing points + E04-governed ATR (never recomputed).
  - E07 assembles a Bundle from E04/E05/E06 evidence and degrades to its
    UTC-fixed config when E12 temporal windows are ABSENT (the E07↔E12
    resolved-mode integration test lands at CP-5, when E12 exists).
  - E08 produces phase hypotheses from E04-governed ATR.
  - Emission rows validate against the store DDL via SQLiteStore.
  - T-DR-001 re-run for all three CP-4 engines over one shared window.
"""
from decimal import Decimal

import pytest

from apex.data_catalog.contracts import MarketObservation
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.engines.e07_rtm import E07RTMEngine
from apex.engines.e07_rtm import run_engine as run_e07
from apex.engines.e08_wyckoff import E08WyckoffEngine
from apex.engines.e08_wyckoff import run_engine as run_e08
from apex.engines.e09_trend import E09TrendEngine
from apex.engines.e09_trend import run_engine as run_e09
from apex.engines.e04_volatility import run_engine as run_e04
from apex.engines.e04_volatility import ATR_FLOOR


# ---------------------------------------------------------------------------
# shared deterministic window (LCG — same discipline as CP-2/CP-3)
# ---------------------------------------------------------------------------
def lcg_window(n, seed=131, base=600.0):
    state = seed
    out = []
    price = base
    for i in range(n):
        state = (state * 1103515245 + 12345) % (2 ** 31)
        r1 = state / 2 ** 31
        state = (state * 1103515245 + 12345) % (2 ** 31)
        r2 = state / 2 ** 31
        o = price
        c = o + (r1 - 0.5) * 6.0
        h = max(o, c) + r2 * 2.0
        lo = min(o, c) - (1 - r2) * 2.0
        out.append({"o": o, "h": h, "l": lo, "c": c,
                    "v": 500 + int(r1 * 2500), "ts": i * 3600000})
        price = c
    return out


def e04_atr_series(bars, timeframe="1h"):
    out = run_e04(bars, timeframe=timeframe)
    atr = list(out["atr_series"])
    while len(atr) < len(bars):
        atr.insert(0, ATR_FLOOR)
    return out, atr


def obs_window(bars, symbol="BTCUSDT", timeframe="1h"):
    obs = []
    for i, b in enumerate(bars):
        ts = "2026-01-%02dT%02d:00:00.000Z" % (1 + i // 24, i % 24)
        obs.append(MarketObservation(
            symbol=symbol, timeframe=timeframe,
            open=Decimal(str(round(b["o"], 8))),
            high=Decimal(str(round(b["h"], 8))),
            low=Decimal(str(round(b["l"], 8))),
            close=Decimal(str(round(b["c"], 8))),
            volume=Decimal(str(b["v"])), oi=None, timestamp=ts,
            sequence=i, status="CLOSED"))
    return obs


# ---------------------------------------------------------------------------
# E09 consumes E04 ATR + E01 swings
# ---------------------------------------------------------------------------
class TestE09ConsumesUpstream:
    def test_e09_trendstack_over_e04_atr(self):
        bars = lcg_window(90)
        _out, atr = e04_atr_series(bars)
        # derive swing points from the bar stream (E01-shaped input)
        swings = _swings_from(bars)
        r = run_e09(bars, swings=swings, atr=atr[-1])
        assert set(r["scales"]) == {"MICRO", "SHORT", "INTER", "MACRO"}
        assert -1.0 <= r["bias"] <= 1.0
        assert r["alignment"] in ("ALIGNED_BULL", "ALIGNED_BEAR",
                                  "CONFLICTING", "SIDEWAYS")


def _swings_from(bars):
    swings = []
    for i in range(2, len(bars) - 1):
        if bars[i]["h"] > bars[i - 1]["h"] and bars[i]["h"] > bars[i + 1]["h"]:
            swings.append({"type": "HH", "price": bars[i]["h"], "idx": i,
                           "confirmed_at_idx": i + 1})
        elif bars[i]["l"] < bars[i - 1]["l"] and bars[i]["l"] < bars[i + 1]["l"]:
            swings.append({"type": "LL", "price": bars[i]["l"], "idx": i,
                           "confirmed_at_idx": i + 1})
    return swings


# ---------------------------------------------------------------------------
# E07 assembles a bundle from E04/E05/E06 evidence; E12 degraded branch
# ---------------------------------------------------------------------------
class TestE07Bundle:
    def test_e07_chain_bundle_without_e12(self):
        bars = lcg_window(120)
        sweep = [{"valid_at_idx": 1, "ts": 3600000, "p_confirm": 0.9}]
        structure = [{"kind": "CHoCH", "valid_at_idx": 2, "ts": 7200000},
                     {"kind": "BOS", "valid_at_idx": 3, "ts": 10800000}]
        fvg = [{"present": True, "valid_at_idx": 4, "ts": 14400000,
                "touch_count": 1}]
        vol = [{"valid_at_idx": 5, "ts": 18000000, "p_confirm": 0.9}]
        r = run_e07(bars, structure_events=structure, sweep_events=sweep,
                    fvg_events=fvg, volume_events=vol, mtf_align=1.0,
                    as_of_ms=18000000)
        # E12 absent → degraded, never fabricated
        assert r["temporal_source"] == "E07_UTC_FIXED_DEGRADED"
        chain = next((b for b in r["bundles"]
                      if b.framework_id == "RTM.CHAIN.v1"), None)
        assert chain is not None
        assert chain.integrity >= 0.7

    def test_e07_e12_present_consumed(self):
        bars = lcg_window(120)
        r = run_e07(bars, mtf_align=1.0, as_of_ms=0,
                    temporal_windows=[{"in_kz": True,
                                       "config_version": "KZ.v2.1.1"}])
        assert r["temporal_source"] == "E12"


# ---------------------------------------------------------------------------
# E08 produces phase hypotheses from E04 ATR
# ---------------------------------------------------------------------------
class TestE08Phase:
    def test_e08_phase_over_e04_atr(self):
        bars = lcg_window(90)
        _out, atr = e04_atr_series(bars)
        r = run_e08(bars, atr_series=atr)
        cs = r["cycle_state"]
        assert set(cs["phase_hypotheses"]) == set([
            "ACCUMULATION", "MARKUP", "DISTRIBUTION", "MARKDOWN",
            "RE-ACCUMULATION", "RE-DISTRIBUTION", "RANGE", "TRANSITION"])
        assert abs(sum(cs["phase_hypotheses"].values()) - 1.0) < 1e-9
        assert cs["entropy"] >= 0.0


# ---------------------------------------------------------------------------
# Emissions through store DDL
# ---------------------------------------------------------------------------
class TestStoreEmission:
    def test_engines_insert_evidence(self):
        bars = lcg_window(90)
        obs = obs_window(bars)
        _, atr = e04_atr_series(bars)
        engines = [
            E07RTMEngine(),
            E08WyckoffEngine(),
            E09TrendEngine(),
        ]
        contexts = [
            {"window": obs, "sweep_events": [{"valid_at_idx": 1,
                                              "ts": 3600000,
                                              "p_confirm": 0.9}],
             "structure_events": [{"kind": "BOS", "valid_at_idx": 3,
                                   "ts": 10800000}],
             "fvg_events": [{"present": True, "valid_at_idx": 4,
                             "ts": 14400000, "touch_count": 1}],
             "volume_events": [{"valid_at_idx": 5, "ts": 18000000,
                                "p_confirm": 0.9}],
             "mtf_align": 1.0},
            {"window": obs, "atr_series": atr},
            {"window": obs, "atr": atr[-1],
             "swings": _swings_from(bars)},
        ]
        all_events = []
        for eng, ctx in zip(engines, contexts):
            events = eng.compute("BTCUSDT", "1h", "2026-01-01T00:00:00Z",
                                 ctx)
            assert events
            for e in events:
                e.validate_24_fields()
                all_events.append(e)

        import asyncio

        async def scenario():
            store = SQLiteStore(path=":memory:")
            await store.open()
            try:
                for ev in all_events:
                    await store.insert_evidence(ev)
                cur = await store.db.execute(
                    "SELECT COUNT(*) FROM evidence_event")
                count = (await cur.fetchone())[0]
                cur = await store.db.execute(
                    "SELECT DISTINCT engine_id FROM evidence_event "
                    "ORDER BY engine_id")
                engines = [r[0] for r in await cur.fetchall()]
                return count, engines
            finally:
                await store.close()

        count, engines = asyncio.run(scenario())
        assert count == len(all_events)
        assert set(engines) <= {"E07", "E08", "E09"} and engines


# ---------------------------------------------------------------------------
# T-DR-001 (all three CP-4 engines, double-run byte identical)
# ---------------------------------------------------------------------------
class TestTDR001:
    def test_double_run_byte_identical_all_engines(self):
        bars = lcg_window(90)
        obs = obs_window(bars)
        _, atr = e04_atr_series(bars)
        swings = _swings_from(bars)
        e7 = E07RTMEngine()
        e8 = E08WyckoffEngine()
        e9 = E09TrendEngine()
        c7 = {"window": obs, "sweep_events": [{"valid_at_idx": 1,
                                               "ts": 3600000,
                                               "p_confirm": 0.9}],
              "structure_events": [{"kind": "BOS", "valid_at_idx": 3,
                                    "ts": 10800000}],
              "fvg_events": [{"present": True, "valid_at_idx": 4,
                              "ts": 14400000, "touch_count": 1}],
              "volume_events": [{"valid_at_idx": 5, "ts": 18000000,
                                 "p_confirm": 0.9}], "mtf_align": 1.0}
        c8 = {"window": obs, "atr_series": atr}
        c9 = {"window": obs, "atr": atr[-1], "swings": swings}
        r1 = [
            [e.snapshot_id for e in e7.compute("BTCUSDT", "1h",
                                               "2026-01-01T00:00:00Z", c7)],
            [e.snapshot_id for e in e8.compute("BTCUSDT", "1h",
                                               "2026-01-01T00:00:00Z", c8)],
            [e.snapshot_id for e in e9.compute("BTCUSDT", "1h",
                                               "2026-01-01T00:00:00Z", c9)],
        ]
        r2 = [
            [e.snapshot_id for e in e7.compute("BTCUSDT", "1h",
                                               "2026-01-01T00:00:00Z", c7)],
            [e.snapshot_id for e in e8.compute("BTCUSDT", "1h",
                                               "2026-01-01T00:00:00Z", c8)],
            [e.snapshot_id for e in e9.compute("BTCUSDT", "1h",
                                               "2026-01-01T00:00:00Z", c9)],
        ]
        assert r1 == r2
