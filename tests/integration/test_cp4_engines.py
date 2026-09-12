"""CP-4 cross-engine integration battery (E07 RTM / E08 Wyckoff / E09 Trend).

Covers the §8 clauses that span engines and the CP-4 EXIT-box checks:

  - **E07 E12 branch** — with no temporal provider the engine reports
    ``degraded=True`` / ``E12_UNAVAILABLE_DEGRADED_QX`` and caps at Q4; with a
    stub ``E12_Temporal_Context.Contract v4.0.0`` surface the same code path is
    non-degraded and Q5 becomes reachable. The real E07↔E12 integration is
    scheduled at **CP-5** (recorded in the CP-4 handoff ledger).
  - **E08 encyclopedia Wave-Out** — chapter 1 is normative and served;
    chapters 2–4 raise ``WaveOutError`` with a deterministic reason.
  - **E09 AD-line and multi-TF** — the four-scale stack is emitted with the
    Wilder DI+/DI−/DX/ADX line and a governed alignment label.
  - **Consumed foundation** — E04's governed ATR drives E07/E08/E09 (never
    recomputed) and E01 swings/BOS drive E09's sequence term under PIT.
  - **Emission rows** validate against the frozen store DDL.
  - **T-DR-001** re-run for all three CP-4 engines over one shared window.
"""
import asyncio
import json
from decimal import Decimal

import pytest

from apex.data_catalog.contracts import MarketObservation
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.engines.e04_volatility import run_engine as run_e04
from apex.engines.e07_rtm import (
    E12_CONTRACT,
    E07RTMEngine,
    E12_UNAVAILABLE_REASON,
    Q_CLASSES,
    build_bundle_pipeline,
    build_order_map,
    expected_components,
    resolution_class,
    sequence_integrity_v4,
    utc_activity_window_check,
)
from apex.engines.e08_wyckoff import (
    E08WyckoffEngine,
    ENCYCLOPEDIA_CH1,
    ENCYCLOPEDIA_WAVE_OUT_CHAPTERS,
    K_PHASES,
    WyckoffEngineV4,
    WaveOutError,
    encyclopedia_chapter,
)
from apex.engines.e09_trend import (
    ALIGNMENTS,
    E09TrendEngine,
    QUALITY_LABELS,
    SCALES,
    TREND_SCALE_REQUIRED,
    TREND_STACK_REQUIRED,
    run_engine as run_e09,
)
from apex.errors import WAVE_OUT_FEATURES

AS_OF = "2026-01-15T14:00:00Z"          # inside the 12:30–16:00 overlap
AS_OF_MS = 1768485600000 + 14 * 3600000
RANGE_LO, RANGE_HI, ATR = 608.2, 628.4, 4.2


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


def obs_window(bars, symbol="BTCUSDT", timeframe="1h"):
    """Closed-candle window on the catalog surface, timestamped from each
    bar's own ``ts`` so the PIT filters see the real timeline."""
    import datetime
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
    from apex.engines.e07_rtm import evaluate_order_ok
    evaluate_order_ok(exp, order, om)
    kz = utc_activity_window_check(conf[-1]["t_confirm_ms"],
                                   temporal_provider=temporal_provider)
    return build_bundle_pipeline(exp, order, om, avg_q, mtf_align, kz,
                                 framework, direction, conf[-1]["t_confirm_ms"])


class StubE12:
    """The versioned ``E12_Temporal_Context.Contract v4.0.0`` surface.

    A stub, not E12: CP-4 ships E07's *contract-conformant* branch so the
    degraded path is provably distinguishable; the real engine lands at CP-5.
    """

    config_version = "E12-WINDOWS-CORRECTED-v1"

    def __init__(self, is_overlap=True, raise_=False):
        self.is_overlap = is_overlap
        self.raise_ = raise_
        self.calls = []

    def temporal_window(self, ts_ms):
        self.calls.append(ts_ms)
        if self.raise_:
            raise RuntimeError("E12 unavailable")
        which = ["UTC_W2", "UTC_W1_W2_OVERLAP"] if self.is_overlap else ["UTC_W1"]
        return {"which": which, "is_overlap": self.is_overlap,
                "utc_activity_window": "UTC_W2" if self.is_overlap else "UTC_W1",
                "config_version": self.config_version}


# ---------------------------------------------------------------------------
# E07 — the E12-unavailable degraded branch (and its authoritative counterpart)
# ---------------------------------------------------------------------------
class TestE07TemporalBranches:
    def test_e12_absent_is_degraded_and_never_canonical(self):
        info = utc_activity_window_check(AS_OF_MS)
        assert info["degraded"] is True
        assert info["degraded_reason"] == E12_UNAVAILABLE_REASON
        assert info["source"] == "E07_LOCAL_NON_AUTHORITATIVE"
        assert info["source"] != E12_CONTRACT

    def test_stub_e12_clears_the_degradation(self):
        stub = StubE12(is_overlap=True)
        info = utc_activity_window_check(AS_OF_MS, temporal_provider=stub)
        assert info["degraded"] is False and info["degraded_reason"] is None
        assert info["source"] == E12_CONTRACT
        assert info["config_version"] == stub.config_version
        assert info["is_overlap"] is True
        assert stub.calls == [AS_OF_MS]          # E12 is the one consulted

    def test_a_failing_provider_fails_closed(self):
        info = utc_activity_window_check(AS_OF_MS,
                                        temporal_provider=StubE12(raise_=True))
        assert info["degraded"] is True
        assert info["degraded_reason"] == E12_UNAVAILABLE_REASON

    def test_degradation_caps_the_quality_class_at_q4(self):
        """§3.7's Q5 gate needs the overlap flag; at CP-4 (E12 absent, a
        non-overlap timestamp) the cascade is capped and Q5 is unreachable."""
        conf = po3_confirmations(t0=1768485600000 + 9 * 3600000)   # 09:00Z
        degraded_bundle = bundle_from(conf)
        assert degraded_bundle is not None
        assert degraded_bundle.resolution_class == "Q4"
        # Same evidence, authoritative overlap window ⇒ Q5 is reachable.
        overlap = bundle_from(conf, temporal_provider=StubE12(is_overlap=True))
        assert overlap.resolution_class == "Q5"
        assert Q_CLASSES.index(overlap.resolution_class) == \
            Q_CLASSES.index("Q5")

    def test_both_branches_agree_on_integrity(self):
        """The degradation changes provenance and the Q gate, never the
        §3.1 sequence arithmetic."""
        conf = po3_confirmations()
        a = bundle_from(conf)
        b = bundle_from(conf, temporal_provider=StubE12(is_overlap=True))
        from apex.engines.e07_rtm import evaluate_order_ok
        exp = expected_components("RTM.PO3.v1")
        order = [c["cid"] for c in conf]
        om_a = build_order_map(exp, conf)
        evaluate_order_ok(exp, order, om_a)      # same pipeline as bundle_from
        integrity, coverage, _missing = sequence_integrity_v4(exp, order, om_a)
        assert a.integrity == pytest.approx(integrity)
        assert b.integrity == pytest.approx(integrity)
        assert a.weight_coverage == pytest.approx(coverage)
        # Only the provenance differs between the two branches.
        assert a.degraded is True and b.degraded is False
        assert a.temporal_authority != b.temporal_authority
        assert b.temporal_authority == E12_CONTRACT

    def test_engine_emits_valid_evidence_without_e12(self):
        bars = lcg_window(30)
        evs = E07RTMEngine().compute(
            "BNBUSDT", "15m", AS_OF,
            {"window": obs_window(bars), "events": po3_confirmations(),
             "direction": "UP"})
        assert evs
        for ev in evs:
            ev.validate_24_fields()
            assert ev.engine_id == "E07"
            assert "E12_UNAVAILABLE_DEGRADED_QX" in ev.explanation


# ---------------------------------------------------------------------------
# E08 — encyclopedia chapter 1 normative, chapters 2–4 Wave-Out
# ---------------------------------------------------------------------------
class TestE08WaveOut:
    def test_chapter_1_served_normatively(self):
        ch1 = encyclopedia_chapter(1)
        assert ch1["normative"] is True
        assert len(ch1["content"]) == 16

    @pytest.mark.parametrize("chapter", ENCYCLOPEDIA_WAVE_OUT_CHAPTERS)
    def test_chapters_2_to_4_wave_out(self, chapter):
        with pytest.raises(WaveOutError) as exc:
            encyclopedia_chapter(chapter)
        assert exc.value.feature in WAVE_OUT_FEATURES
        assert "DEFERRED_NON_NORMATIVE" in exc.value.reason

    def test_wave_out_does_not_leak_into_the_event_stream(self):
        """A Wave-Out is a contract boundary, not a runtime failure of the
        chapter-1 engine: the same engine still emits evidence."""
        eng = WyckoffEngineV4()
        bars = lcg_window(14, base=615.0)
        states = eng.run_full(
            bars, atr_by_idx={i: ATR for i in range(len(bars))},
            vol_ratio_by_idx={i: 1.0 for i in range(len(bars))},
            evr_by_idx={i: 0.5 for i in range(len(bars))})
        assert len(states) == 14
        assert len(states[-1]["phase_hypotheses"]) == K_PHASES
        assert all(e["code"].startswith("EV_WYK_") for e in eng.events)

    def test_chapter1_dimensions_are_the_declared_axes(self):
        from apex.engines.e08_wyckoff import ENCYCLOPEDIA_CH1_DIMENSIONS
        # The chapter declares 16 numbered dimensions; all 16 are carried.
        assert ENCYCLOPEDIA_CH1_DIMENSIONS == len(ENCYCLOPEDIA_CH1) == 16
        assert set(ENCYCLOPEDIA_CH1) == {str(i) for i in range(1, 17)}
        assert all(isinstance(v, str) and v for v in ENCYCLOPEDIA_CH1.values())


# ---------------------------------------------------------------------------
# E09 — AD-line and the multi-TF stack
# ---------------------------------------------------------------------------
class TestE09StackAndADLine:
    def test_four_scales_with_the_full_schema(self):
        bars = lcg_window(60)
        res = run_e09(bars, atr=ATR,
                      swings=[{"type": "HH", "idx": 10, "confirmed_at_idx": 11},
                              {"type": "HL", "idx": 20, "confirmed_at_idx": 21},
                              {"type": "HH", "idx": 30, "confirmed_at_idx": 31}])
        assert set(res["scales"]) == set(SCALES)
        for scale, data in res["scales"].items():
            assert data["scale"] == scale
            missing = [k for k in TREND_SCALE_REQUIRED if k not in data]
            assert missing == []
            assert data["direction"] in (-1, 0, 1)
            assert data["quality_label"] in QUALITY_LABELS
            assert len(data["snapshot_id"]) == 64
        missing = [k for k in TREND_STACK_REQUIRED if k not in res]
        assert missing == []
        assert res["alignment"] in ALIGNMENTS

    def test_ad_line_is_the_wilder_chain(self):
        """DI+/DI−/DX/ADX are published per scale; a warm-up window degrades
        instead of presenting an untrustworthy ADX (§3.5)."""
        # Each window gets swings inside its own MICRO window (PIT-legal):
        # the 8-bar run evaluates idx 7, the 60-bar run evaluates idx 59.
        short_swings = [{"type": "HH", "idx": 3, "confirmed_at_idx": 4},
                        {"type": "HL", "idx": 4, "confirmed_at_idx": 5},
                        {"type": "HH", "idx": 5, "confirmed_at_idx": 6}]
        warm_swings = [{"type": "HH", "idx": 55, "confirmed_at_idx": 56},
                       {"type": "HL", "idx": 56, "confirmed_at_idx": 57},
                       {"type": "HH", "idx": 57, "confirmed_at_idx": 58}]
        short = run_e09(lcg_window(8), atr=ATR, swings=short_swings)
        warm = run_e09(lcg_window(60), atr=ATR, swings=warm_swings)
        assert short["scales"]["MICRO"]["degraded_reason"] == "ADX_WARMUP_QX"
        assert warm["scales"]["MICRO"]["degraded_reason"] is None
        micro = warm["scales"]["MICRO"]
        assert 0.0 <= micro["adx"] <= 100.0
        assert 0.0 <= micro["di_plus"] <= 100.0
        assert 0.0 <= micro["di_minus"] <= 100.0
        assert micro["adx"] >= 0.0

    def test_alignment_follows_the_governed_bias_bands(self):
        aligned = run_e09(lcg_window(60, span=1.0), atr=ATR)
        assert -1.0 <= aligned["bias"] <= 1.0
        if abs(aligned["bias"]) > 0.7 and aligned["alignment"] == "ALIGNED_BULL":
            assert all(aligned["scales"][s]["direction"] == 1 for s in SCALES)

    def test_e04_governed_atr_is_consumed_not_recomputed(self):
        """The pos term is ATR-normalised; E09 uses the supplied E04 ATR and
        never derives one of its own."""
        bars = lcg_window(40)
        atr_val = float(run_e04(bars)["atr_series"][-1])
        assert atr_val > 0.0
        a = run_e09(bars, atr=atr_val)
        b = run_e09(bars, atr=atr_val * 2)
        assert a["scales"]["MICRO"]["pos"] != b["scales"]["MICRO"]["pos"]
        assert a["scales"]["MICRO"]["pos"] == pytest.approx(
            2 * b["scales"]["MICRO"]["pos"], rel=1e-9)

    def test_e01_swings_drive_the_sequence_term_under_pit(self):
        bars = lcg_window(40)
        # The swings sit inside the MICRO window (last 5 bars of 40).
        swings = [{"type": "HH", "idx": 35, "confirmed_at_idx": 36},
                  {"type": "HL", "idx": 36, "confirmed_at_idx": 37},
                  {"type": "HH", "idx": 37, "confirmed_at_idx": 38}]
        with_swings = run_e09(bars, atr=ATR, swings=swings)
        without = run_e09(bars, atr=ATR, swings=None)
        assert with_swings["scales"]["MICRO"]["seq_score"] == pytest.approx(1.0)
        assert without["scales"]["MICRO"]["seq_score"] == pytest.approx(0.0)
        assert without["degraded"] is True
        # A look-ahead swing is refused, not silently ignored.
        leak = [{"type": "HH", "idx": 35, "confirmed_at_idx": 999}]
        with pytest.raises(ValueError, match="PIT_SWING_VIOLATION_QX"):
            run_e09(bars, atr=ATR, swings=leak)

    def test_bos_confirmation_can_initiate_a_trend(self):
        bars = lcg_window(60, span=6.0)
        swings = [{"type": "HH", "idx": 40, "confirmed_at_idx": 41},
                  {"type": "HL", "idx": 45, "confirmed_at_idx": 46},
                  {"type": "HH", "idx": 50, "confirmed_at_idx": 51}]
        res = run_e09(bars, atr=ATR, swings=swings,
                      bos_event={"kind": "BOS", "direction": "UP",
                                 "valid_at_idx": 55})
        codes = [e["code"] for e in res["events"]]
        assert codes                                  # at least a stack event
        assert all(c.startswith("EV_TRD_") for c in codes)


# ---------------------------------------------------------------------------
# Consumed foundation + store DDL
# ---------------------------------------------------------------------------
class TestCP4EmissionsInsertIntoStore:
    def _events(self):
        bars = lcg_window(30)
        window = obs_window(bars)
        evs = []
        evs += E07RTMEngine().compute(
            "BTCUSDT", "1h", AS_OF,
            {"window": window, "events": po3_confirmations(),
             "direction": "UP"})
        evs += E08WyckoffEngine().compute(
            "BTCUSDT", "1h", AS_OF,
            {"window": window, "atr_by_idx": {i: ATR for i in range(len(bars))},
             "vol_ratio_by_idx": {i: 1.0 for i in range(len(bars))},
             "evr_by_idx": {i: 0.5 for i in range(len(bars))}})
        evs += E09TrendEngine().compute(
            "BTCUSDT", "1h", AS_OF, {"window": window, "atr": ATR})
        return evs

    def test_all_three_engines_insert(self):
        evs = self._events()
        assert {ev.engine_id for ev in evs} == {"E07", "E08", "E09"}
        for ev in evs:
            ev.validate_24_fields()

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
        assert set(engines) <= {"E07", "E08", "E09"} and engines

    def test_duplicate_snapshot_insert_is_rejected_by_the_ddl(self):
        evs = self._events()
        ev = evs[0]

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


# ---------------------------------------------------------------------------
# T-DR-001 across all three CP-4 engines (one shared window)
# ---------------------------------------------------------------------------
class TestTDR001CP4:
    def test_double_run_byte_identical_all_engines(self):
        bars = lcg_window(30)
        ctx_e07 = {"window": obs_window(bars), "events": po3_confirmations(),
                   "direction": "UP"}
        ctx_e08 = {"window": obs_window(bars),
                   "atr_by_idx": {i: ATR for i in range(len(bars))},
                   "vol_ratio_by_idx": {i: 1.0 for i in range(len(bars))},
                   "evr_by_idx": {i: 0.5 for i in range(len(bars))}}
        ctx_e09 = {"window": obs_window(bars), "atr": ATR}
        runs = []
        for _ in range(2):
            batch = []
            batch += E07RTMEngine().compute("BTCUSDT", "1h", AS_OF, ctx_e07)
            batch += E08WyckoffEngine().compute("BTCUSDT", "1h", AS_OF, ctx_e08)
            batch += E09TrendEngine().compute("BTCUSDT", "1h", AS_OF, ctx_e09)
            runs.append([(ev.engine_id, ev.snapshot_id, ev.condition_state,
                          ev.direction, ev.strength, ev.resolution_class)
                         for ev in batch])
        assert runs[0] == runs[1]
        assert len(runs[0]) >= 5

    def test_streaming_replay_is_deterministic_too(self):
        bars = lcg_window(30)
        kw = dict(atr_by_idx={i: ATR for i in range(len(bars))},
                  vol_ratio_by_idx={i: 1.0 for i in range(len(bars))},
                  evr_by_idx={i: 0.5 for i in range(len(bars))})
        a = WyckoffEngineV4().run_full(bars, **kw)
        b = WyckoffEngineV4().run_full(bars, **kw)
        assert json.dumps(a, sort_keys=True, default=str) == json.dumps(
            b, sort_keys=True, default=str)

    def test_e09_stack_replay_is_deterministic(self):
        bars = lcg_window(45)
        swings = [{"type": "HH", "idx": 10, "confirmed_at_idx": 11},
                  {"type": "HL", "idx": 20, "confirmed_at_idx": 21}]
        a = run_e09(bars, atr=ATR, swings=swings)
        b = run_e09(bars, atr=ATR, swings=swings)
        assert json.dumps(a, sort_keys=True, default=str) == json.dumps(
            b, sort_keys=True, default=str)
