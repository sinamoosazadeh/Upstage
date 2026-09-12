"""CP-3 cross-engine integration battery (E04/E05/E06).

Covers the §8 clauses that span engines and the CP-3 EXIT-box checks:
  - E04 → E05/E06 evidence chain: E04's governed ATR series is consumed
    by E05 (Gate_D) and E06 (I_Volatility_v4) — never recomputed.
  - E05 → E06 chain: a live E05 FVG zone feeds E06's I_FVG_v4 Context
    term (fvg_same_dir) and can carry an OB to Q3 without Disp_high.
  - E01 → E06 chain: structural BOS events feed E06's structural gate
    (I_Structure_v4 shape {kind, direction, valid_at_idx}).
  - §8.6 redundancy guard: an E05 zone and an E06 zone with IoU > 0.6
    and midpoint distance < 0.2·ATR are flagged redundant (test-side
    cross-engine check; the keep-best rule belongs to the context chain).
  - Emission rows validate against the store DDL: engine EvidenceEvents
    insert through the frozen SQLiteStore.insert_evidence.
  - T-DR-001 re-run for all three CP-3 engines over one shared window.
"""
import asyncio
from decimal import Decimal

import pytest

from apex.data_catalog.contracts import MarketObservation
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.engines.e04_volatility import ATR_FLOOR, E04VolatilityEngine
from apex.engines.e04_volatility import run_engine as run_e04


def e04_atr_series(bars, timeframe="1h"):
    """E04-governed ATR, left-padded with the §2.2 ATR floor for the
    first bar (no evidence exists before the first closed candle) —
    the same pad rule as E04VolatilityEngine.atr_series_for."""
    out = run_e04(bars, timeframe=timeframe)
    atr = list(out["atr_series"])
    while len(atr) < len(bars):
        atr.insert(0, ATR_FLOOR)
    return out, atr
from apex.engines.e05_fvg import E05FVGEngine
from apex.engines.e05_fvg import run_engine as run_e05
from apex.engines.e06_orderblock import E06OrderBlockEngine
from apex.engines.e06_orderblock import (
    OrderBlockEngine,
    iou_zones,
    run_engine as run_e06,
)


# ---------------------------------------------------------------------------
# shared deterministic window (LCG — same discipline as CP-2 integration)
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
# E04 → E05 / E06 evidence chain
# ---------------------------------------------------------------------------
class TestE04FeedsDownstream:
    def test_e04_atr_series_drives_e05_gate_d(self):
        bars = lcg_window(80)
        _, atr_series = e04_atr_series(bars)
        assert len(atr_series) == len(bars)
        assert all(a > 0 for a in atr_series)
        # E05 consumes the E04 ATR pathway (atr_by_idx) — zones whose
        # width clears 0.2·ATR(E04) are created; none below it
        r = run_e05(bars, tick_size=0.01, symbol="BTCUSDT",
                    atr_by_idx={i: atr_series[i] for i in range(len(bars))})
        zones = r["active"] + r["history"]
        for z in zones:
            i = z.created_at_idx
            assert z.width >= 0.2 * atr_series[i] - 1e-9

    def test_e04_atr_as_e06_volatility_evidence(self):
        bars = lcg_window(60)
        _, atr_series = e04_atr_series(bars)
        vol_evidence = [{"snapshot_id": f"e04_{i}", "as_of": bars[i]["ts"],
                         "atr_n": atr_series[i],
                         "tr_method": "E04_I_Volatility_v4"}
                        for i in range(len(bars))]
        vol_volume = [{"snapshot_id": f"e03_{i}", "as_of_ts": bars[i]["ts"],
                       "availability_time_ms": bars[i]["ts"],
                       "volume_sma": 1500.0,
                       "volume_ratio": bars[i]["v"] / 1500.0}
                      for i in range(len(bars))]
        res = run_e06(bars, volume_evidence=vol_volume,
                      volatility_evidence=vol_evidence)
        # E06 ran to completion on E04-supplied ATR (no internal
        # recomputation path exists — see unit consumption lint)
        assert res["engine"].atr == pytest.approx(atr_series)


# ---------------------------------------------------------------------------
# E05 → E06 chain: FVG evidence lifts the OB Context term
# ---------------------------------------------------------------------------
def _chain_scenario_bars():
    bars = []
    for i in range(5):
        bars.append({"o": 100.0, "h": 100.2, "l": 99.8, "c": 100.1,
                     "v": 1000, "ts": i * 3600000})
    bars.append({"o": 100.5, "h": 101.0, "l": 98.5, "c": 98.8, "v": 1500,
                 "ts": 5 * 3600000})                     # bearish origin
    bars.append({"o": 98.8, "h": 101.9, "l": 98.7, "c": 101.6, "v": 3000,
                 "ts": 6 * 3600000})                     # displacement UP
    for j in range(12):
        bars.append({"o": 101.6 + 0.1 * j, "h": 102.2 + 0.1 * j,
                     "l": 101.4 + 0.1 * j, "c": 101.9 + 0.1 * j,
                     "v": 1200, "ts": (7 + j) * 3600000})
    return bars


class TestE05FeedsE06:
    def test_fvg_same_dir_supplies_context_or_term(self):
        bars = _chain_scenario_bars()
        atr = 2.0
        vol = [{"snapshot_id": f"v{i}", "as_of_ts": bars[i]["ts"],
                "availability_time_ms": bars[i]["ts"], "volume_sma": 1000.0,
                "volume_ratio": 2.0 if i == 6 else 1.0}
               for i in range(len(bars))]
        vola = [{"snapshot_id": f"a{i}", "as_of": bars[i]["ts"],
                 "atr_n": atr, "tr_method": "E04"} for i in range(len(bars))]
        struct = {5: [{"kind": "BOS", "direction": "UP",
                       "valid_at_idx": 6}]}
        # Disp_multi = 3.2/2 = 1.6 < 1.8 ⇒ the Context OR-term can only
        # be satisfied through an FVG
        no_fvg = run_e06(bars, struct_events_by_idx=struct, fvg_by_idx={},
                         volume_evidence=vol, volatility_evidence=vola)
        q_no_fvg = [e for e in no_fvg["events"]
                    if e["code"] == "EV_OBK_001"][0]["quality"]
        assert q_no_fvg != "Q3"
        # a live E05-style FVG next to the origin supplies the OR-term
        fvg = {6: [{"present": True, "direction": "UP",
                    "lower": 98.8, "upper": 99.5,
                    "type": "CONVENTIONAL"}]}
        with_fvg = run_e06(bars, struct_events_by_idx=struct,
                           fvg_by_idx=fvg, volume_evidence=vol,
                           volatility_evidence=vola)
        q_fvg = [e for e in with_fvg["events"]
                 if e["code"] == "EV_OBK_001"][0]["quality"]
        assert q_fvg == "Q3"

    def test_live_e05_zones_roundtrip_into_e06_shape(self):
        # E05 run on the shared window; every active zone maps cleanly
        # into the I_FVG_v4 consumption shape used by E06
        bars = lcg_window(90)
        _, atr_series = e04_atr_series(bars)
        r = run_e05(bars, tick_size=0.01, symbol="BTCUSDT",
                    atr_by_idx={i: atr_series[i] for i in range(len(bars))})
        shapes = [{"present": True, "direction": z.direction,
                   "lower": z.lower, "upper": z.upper, "type": z.ftype}
                  for z in r["active"]]
        for s in shapes:
            assert s["direction"] in ("UP", "DOWN")
            assert s["lower"] < s["upper"]


# ---------------------------------------------------------------------------
# §8.6 cross-engine redundancy guard (E05 zone vs E06 zone)
# ---------------------------------------------------------------------------
class TestCrossEngineRedundancy:
    def test_iou_and_midpoint_gate_flags_redundant_pair(self):
        atr = 2.0
        fvg_lo, fvg_hi = 100.0, 102.0           # E05 zone
        ob_lo, ob_hi = 100.2, 102.2             # E06 zone
        iou = iou_zones(fvg_lo, fvg_hi, ob_lo, ob_hi)
        mid_dist = abs((fvg_lo + fvg_hi) / 2 - (ob_lo + ob_hi) / 2)
        assert iou > 0.6 and mid_dist < 0.2 * atr   # redundant pair
        # a distant pair is not redundant
        iou2 = iou_zones(fvg_lo, fvg_hi, 110.0, 112.0)
        assert iou2 == 0.0


# ---------------------------------------------------------------------------
# EngineBase emissions insert through the frozen store DDL
# ---------------------------------------------------------------------------
class TestEmissionsInsertIntoStore:
    def test_e04_e05_e06_events_insert(self):
        bars = lcg_window(120)
        window = obs_window(bars)
        _, atr_series = e04_atr_series(bars)
        vol = [{"snapshot_id": f"v{i}", "as_of_ts": bars[i]["ts"],
                "availability_time_ms": bars[i]["ts"], "volume_sma": 1000.0,
                "volume_ratio": 2.0 if i == 6 else 1.0}
               for i in range(len(bars))]
        vola = [{"snapshot_id": f"a{i}", "as_of": bars[i]["ts"],
                 "atr_n": atr_series[i], "tr_method": "E04"}
                for i in range(len(bars))]
        evs = []
        evs += E04VolatilityEngine().compute(
            "BTCUSDT", "1h", "2026-01-06T00:00:00Z", {"window": window})
        evs += E05FVGEngine().compute(
            "BTCUSDT", "1h", "2026-01-06T00:00:00Z",
            {"window": window, "tick_size": 0.01,
             "atr_series": atr_series})
        evs += E06OrderBlockEngine().compute(
            "BTCUSDT", "1h", "2026-01-06T00:00:00Z",
            {"window": window, "volume_evidence": vol,
             "volatility_evidence": vola,
             "struct_events_by_idx": {5: [{"kind": "BOS",
                                           "direction": "UP",
                                           "valid_at_idx": 6}]}})
        assert evs
        engine_ids = {ev.engine_id for ev in evs}
        assert {"E04", "E05", "E06"} <= engine_ids
        for ev in evs:
            ev.validate_24_fields()

        async def scenario():
            store = SQLiteStore(path=":memory:")
            await store.open()
            try:
                for ev in evs[:30]:
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
        assert count == min(30, len(evs))
        assert set(engines) <= {"E04", "E05", "E06"} and engines


# ---------------------------------------------------------------------------
# T-DR-001 across all three CP-3 engines (one shared window)
# ---------------------------------------------------------------------------
class TestTDR001CP3:
    def test_double_run_byte_identical_all_engines(self):
        bars = lcg_window(100)

        def run_all():
            e04, atr_series = e04_atr_series(bars)
            r05 = run_e05(bars, tick_size=0.01, symbol="BTCUSDT",
                          atr_by_idx={i: atr_series[i]
                                      for i in range(len(bars))})
            vol = [{"snapshot_id": f"v{i}", "as_of_ts": bars[i]["ts"],
                    "availability_time_ms": bars[i]["ts"],
                    "volume_sma": 1000.0,
                    "volume_ratio": 2.0 if i == 6 else 1.0}
                   for i in range(len(bars))]
            vola = [{"snapshot_id": f"a{i}", "as_of": bars[i]["ts"],
                     "atr_n": atr_series[i], "tr_method": "E04"}
                    for i in range(len(bars))]
            r06 = run_e06(bars, struct_events_by_idx={
                5: [{"kind": "BOS", "direction": "UP", "valid_at_idx": 6}]},
                fvg_by_idx={}, volume_evidence=vol,
                volatility_evidence=vola)
            return e04, r05, r06

        e04_a, r05_a, r06_a = run_all()
        e04_b, r05_b, r06_b = run_all()
        # E04: canonical state series identical
        ids_a = [s.snapshot_id for s in e04_a["states"]]
        ids_b = [s.snapshot_id for s in e04_b["states"]]
        assert ids_a == ids_b and ids_a
        # E05: fid + snapshot identical
        f05_a = sorted((o.fid, o.snapshot_id)
                       for o in r05_a["active"] + r05_a["history"])
        f05_b = sorted((o.fid, o.snapshot_id)
                       for o in r05_b["active"] + r05_b["history"])
        assert f05_a == f05_b
        # E06: canonical OB list identical
        c06_a = sorted(o.snapshot_id for o in r06_a["obs"])
        c06_b = sorted(o.snapshot_id for o in r06_b["obs"])
        assert c06_a == c06_b

    def test_e06_fail_closed_without_upstream_evidence(self):
        bars = lcg_window(40)
        with pytest.raises(ValueError, match="MISSING_EVIDENCE_QX"):
            run_e06(bars)                       # no volume/volatility feed
        with pytest.raises(ValueError, match="MISSING_EVIDENCE_QX"):
            E06OrderBlockEngine().compute(
                "BTCUSDT", "1h", "2026-01-02T00:00:00Z",
                {"window": obs_window(bars)})
