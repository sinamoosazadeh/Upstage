"""CP-6 battery — the only Wave-In setup family (Ch.10 §10.1 + §10.2 AD.8).

Covers: the 140-cell universality, the ``EL_SWEEP_RECLAIM_FVG`` steps, the
relative-MTF law (including the documented vacuous pass and the "cell does not
emit" rule), required/optional evidence, conflict ×0.6, redundancy, the frozen
S_struct ≥ 0.55, no-second-family Wave-Out, and the SetupEvent materialization
with the additive AD.1 field 22 (``family_id``).
"""

from __future__ import annotations

import pytest

from apex.data_catalog.contracts import CORE10_SYMBOLS, TIMEFRAMES_14
from apex.errors import WaveOutError
from apex.fabric.context import q_min_setup
from apex.fabric.evidence import EvidenceFabric, FabricEvidenceRef
from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import sha256_hex
from apex.setup.family_sf_fvg_sweep_rev import (
    EMITTED,
    ENTRY_LOGIC_REF,
    FAMILY_ID,
    FORBIDDEN_REGIMES,
    FVG_LOOKBACK_BARS,
    HORIZON_BARS,
    NOT_EMITTED,
    OPTIONAL_EVIDENCE,
    PLAYBOOK_ID,
    QUARANTINED,
    REQUIRED_EVIDENCE,
    SWEEP_LOOKBACK,
    SetupEvaluation,
    all_cells,
    atr_gate,
    evaluate_cell,
    family_params,
    fvg_gate,
    mtf_gate,
    register_family,
    relative_mtf,
    regime_gate,
    structure_gate,
    sweep_and_reclaim,
)
from apex.setup.gates import run_all

ENGINE_SET = REQUIRED_EVIDENCE + OPTIONAL_EVIDENCE
SCORED = ("structure", "liquidity", "fvg", "trend", "regime", "temporal",
          "orderblock", "momentum")


def mkbars(n=25, *, low_t=95.0, high_t=105.0, close=None):
    bars = [{"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0, "v": 1000.0}
            for _ in range(n - 1)]
    bars.append({"o": 100.0, "h": 100.5, "l": low_t,
                 "c": 99.7 if close is None else close, "v": 2000.0})
    return bars


def fabric_for(timeframe="1h", *, engines=ENGINE_SET, direction=1,
               symbol="BTCUSDT", quality=0.9):
    refs = []
    for i, eng in enumerate(engines):
        d = direction
        if isinstance(direction, dict):
            d = direction.get(eng, 1)
        refs.append(FabricEvidenceRef(
            evidence_id=f"ev_{i}", engine_id=eng, symbol=symbol,
            timeframe=timeframe, state="ACTIVE", direction=d,
            quality=quality, resolution_class="Q3", age_bars=0, as_of=1000,
            snapshot_id="a" * 64, lineage=(f"obs-{i}",)))
    return EvidenceFabric.assemble(symbol=symbol, timeframe=timeframe,
                                   as_of=1000, evidence=refs, data_trust=0.9)


def base_kwargs(timeframe="1h", **over):
    kw = dict(symbol="BTCUSDT", timeframe=timeframe, as_of=1000,
              fabric=fabric_for(timeframe), bars=mkbars(), atr=1.0,
              direction=1,
              fvg_zones=[{"index": 24, "filled": False}],
              bos={"s_struct": 0.6, "direction": 1}, regime_state="TREND",
              q_forecast=0.6, forecast={"quality": "Q3", "h_norm": 0.4},
              package={"package_version": 1, "parameter_package_id": "pkg-1"},
              lineage=tuple(f"obs-{i}" for i in range(len(ENGINE_SET))),
              s_i={c: 1.0 for c in SCORED},
              q_i={c: 0.9 for c in SCORED})
    kw.update(over)
    return kw


def run(**over):
    timeframe = over.pop("timeframe", "1h")
    return evaluate_cell(**base_kwargs(timeframe, **over))


class TestFamilyContract:
    def test_identity_and_membership_literals(self):
        p = family_params()
        assert p["family_id"] == FAMILY_ID == "SF_FVG_SWEEP_REV"
        assert p["playbook_id"] == PLAYBOOK_ID == "PB_FVG_SWEEP_REV_A"
        assert p["entry_logic_ref"] == ENTRY_LOGIC_REF == "EL_SWEEP_RECLAIM_FVG"
        assert p["required_evidence"] == ("E01", "E02", "E05", "E09", "E11",
                                        "E12")
        assert p["optional_evidence"] == ("E06", "E10")
        assert p["forbidden_regimes"] == FORBIDDEN_REGIMES == ("SHOCK",)
        assert p["horizon_bars"] == HORIZON_BARS == 16
        assert p["Q_min_setup"] == q_min_setup() == 0.55
        assert p["s_struct_min"] == 0.55
        assert SWEEP_LOOKBACK == 20 and FVG_LOOKBACK_BARS == 12

    def test_exactly_one_family_exists(self):
        with pytest.raises(WaveOutError) as ei:
            register_family("SF_SECOND_FAMILY")
        assert ei.value.feature == "extra_setup_families"
        assert "SETUP_FAMILY_NOT_IN_FREEZE" in ei.value.reason

    def test_universality_140_cells(self):
        cells = all_cells()
        assert len(cells) == 140
        assert len(set(cells)) == 140
        assert {s for s, _t in cells} == set(CORE10_SYMBOLS)
        assert {t for _s, t in cells} == set(TIMEFRAMES_14)

    @pytest.mark.parametrize("symbol", list(CORE10_SYMBOLS))
    @pytest.mark.parametrize("timeframe", ["1m", "15m", "1h", "4h", "1mo"])
    def test_the_family_runs_on_every_representative_cell(self, symbol,
                                                          timeframe):
        ev = run(symbol=symbol, timeframe=timeframe)
        assert ev.status in (EMITTED, QUARANTINED)
        assert ev.family_id == FAMILY_ID
        assert ev.playbook_id == PLAYBOOK_ID

    @pytest.mark.parametrize("timeframe", list(TIMEFRAMES_14))
    def test_no_gate_is_15m_only(self, timeframe):
        # the gate matrix runs identically on every TF; the 15m cell is not
        # special (Ch.10 §10.1 "Universality").
        ev = run(timeframe=timeframe)
        assert set(ev.gate_block["results"]) <= set(range(1, 14))
        assert ev.reason in ("ALL_GATES_PASS",) or ev.status != EMITTED


class TestRelativeMtf:
    def test_selection_law(self):
        # setup 1h is index 5: timing L[4]=30m, intermediate L[7]=4h (i+2),
        # HTF L[9]=8h (i+4)
        got = relative_mtf("1h")
        assert got["timing"] == "30m" and got["intermediate"] == "4h"
        assert got["htf"] == "8h" and got["vacuous"] is False

    def test_intermediate_falls_back_to_i_plus_1_when_i_plus_2_absent(self):
        # 1w (index 12): i+2 = 1mo exists → intermediate 1mo; HTF: i+4 absent →
        # coarsest above T = 1mo
        got = relative_mtf("1w")
        assert got["intermediate"] == "1mo" and got["htf"] == "1mo"

    def test_no_coarser_tf_is_the_documented_vacuous_pass(self):
        got = relative_mtf("1mo")
        assert got["intermediate"] is None and got["htf"] is None
        assert got["vacuous"] is True
        assert got["timing"] == "1w"
        res = mtf_gate("1mo", {})
        assert res["ok"] is True and res["reason"] == "VACUOUS_NO_COARSER_TF"

    def test_missing_required_coarser_bar_means_no_emission(self):
        res = mtf_gate("1h", {"4h": None, "8h": None})
        assert res["ok"] is False
        assert res["reason"] == "MISSING_REQUIRED_COARSER_BAR"
        assert set(res["missing"]) == {"4h", "8h"}

    def test_coarsest_tf_boundary_is_exclusive(self):
        with pytest.raises(Exception, match="TIMEFRAME_NOT_FROZEN"):
            relative_mtf("2d")


class TestEntryLogicSteps:
    def test_step1_atr_gate_rejects_unavailable(self):
        assert atr_gate(None) == {"ok": False, "reason": "ATR_UNAVAILABLE"}
        assert atr_gate(float("nan"))["ok"] is False
        assert atr_gate(0.0)["ok"] is False
        assert atr_gate(1.5) == {"ok": True, "reason": "ATR_GOVERNED",
                                "atr": 1.5}
        # and the family refuses before scoring (no fabricated ATR)
        ev = run(atr=None)
        assert ev.status == NOT_EMITTED and ev.reason == "ATR_UNAVAILABLE"

    def test_step2_sweep_long_and_short(self):
        got = sweep_and_reclaim(mkbars(25, low_t=95.0), direction=+1,
                               lookback=SWEEP_LOOKBACK)
        assert got["ok"] is True and got["extreme"] == 99.0
        assert got["reclaim_level"] == 99.7
        # no sweep (the low equals the prior minimum) ⇒ no signal
        assert sweep_and_reclaim(mkbars(25, low_t=99.0), direction=+1)[
            "reason"] == "NO_SWEEP"
        # sweep without reclaim ⇒ no signal
        assert sweep_and_reclaim(
            mkbars(25, low_t=95.0, close=98.5), direction=+1)["reason"] == \
            "NO_RECLAIM"
        # SHORT is the exact mirror
        short_bars = [{"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0,
                       "v": 1000.0} for _ in range(24)]
        short_bars.append({"o": 100.0, "h": 105.0, "l": 100.5, "c": 99.5,
                           "v": 2000.0})
        s = sweep_and_reclaim(short_bars, direction=-1)
        assert s["ok"] is True and s["extreme"] == 101.0

    def test_step2_lookback_is_bounded_to_20_bars(self):
        # a low beyond the 20-bar lookback does NOT count as a sweep
        bars = [{"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0, "v": 1000.0}
                for _ in range(30)]
        bars[5] = {"o": 100.0, "h": 101.0, "l": 90.0, "c": 100.0, "v": 1.0}
        bars.append({"o": 100.0, "h": 100.5, "l": 95.0, "c": 99.7, "v": 1.0})
        # t = last; lookback window excludes bar 5 ⇒ min = 99.0 ⇒ sweep
        got = sweep_and_reclaim(bars, direction=+1, lookback=SWEEP_LOOKBACK)
        assert got["ok"] is True
        assert got["lookback_used"] == SWEEP_LOOKBACK

    def test_step4_fvg_window_and_fill_state(self):
        assert fvg_gate([]) == {"ok": False, "reason": "NO_FVG_EVIDENCE"}
        assert fvg_gate([{"index": 24, "filled": True}], current_index=24)[
            "reason"] == "NO_UNFILLED_FVG_IN_WINDOW"
        ok = fvg_gate([{"index": 24, "filled": False}], current_index=24)
        assert ok["ok"] is True and ok["fvg_index"] == 24
        # outside the 12-bar window ⇒ too old
        assert fvg_gate([{"index": 0, "filled": False}],
                        current_index=20)["reason"] == \
            "NO_UNFILLED_FVG_IN_WINDOW"
        # and it is the zone's own index that ages, not the caller's cursor
        assert fvg_gate([{"index": 0, "filled": False}], current_index=11)[
            "ok"] is True
        # a future zone is a PIT violation, not a convenience
        with pytest.raises(Exception, match="FVG_PIT_VIOLATION"):
            fvg_gate([{"index": 30, "filled": False}], current_index=20)
        # the default cursor (last zone) rejects a zone beyond it
        with pytest.raises(Exception, match="FVG_PIT_VIOLATION"):
            fvg_gate([{"index": 24, "filled": True},
                      {"index": 30, "filled": False}], current_index=0)

    def test_step5_s_struct_boundary_is_inclusive(self):
        assert structure_gate(None)["reason"] == "NO_BOS_EVIDENCE"
        assert structure_gate({"s_struct": 0.54, "direction": 1})[
            "reason"] == "S_STRUCT_BELOW_MIN"
        assert structure_gate({"s_struct": 0.55, "direction": 1})["ok"] is True
        assert structure_gate({"s_struct": 0.9, "direction": 0})[
            "reason"] == "BOS_DIRECTION_MISSING"
        assert structure_gate({"direction": 1})["reason"] == \
            "S_STRUCT_UNAVAILABLE"

    def test_regime_gate_blocks_only_the_forbidden_state(self):
        assert regime_gate("SHOCK")["ok"] is False
        assert regime_gate("shock")["ok"] is False      # case-normalized
        assert regime_gate("TREND")["ok"] is True
        assert regime_gate(None)["reason"] == "REGIME_UNAVAILABLE"
        ev = run(regime_state="SHOCK")
        assert ev.status == NOT_EMITTED and ev.reason == "FORBIDDEN_REGIME"

    def test_step6_entry_is_limit_ioc_at_the_close(self):
        ev = run()
        step = ev.entry_logic_steps["6_entry"]
        assert step["ok"] is True and step["entry"] == 99.7
        assert "MARKET" not in step["fill_policy"].split("never")[0]
        assert "no chase" in step["fill_policy"]
        assert ev.risk_reference == 99.0      # swept extreme = risk reference


class TestEvidenceAndScoring:
    def test_missing_required_evidence_does_not_emit(self):
        ev = run(fabric=fabric_for(engines=("E01", "E02", "E05", "E09",
                                            "E11")))
        assert ev.status == NOT_EMITTED
        assert ev.reason.startswith("REQUIRED_EVIDENCE_MISSING::E12")

    def test_optional_evidence_absence_still_emits(self):
        ev = run(fabric=fabric_for(engines=REQUIRED_EVIDENCE))
        # E06/E10 are optional; the required six alone score below Q_min and
        # are therefore QUARANTINED by Gate 1 — a *real* verdict, not an
        # invention.
        assert ev.status == QUARANTINED
        assert ev.gate_block["blocked_by"] == [1]
        assert ev.final_score < q_min_setup()

    def test_required_conflict_applies_the_060_multiplier(self):
        plain = run()
        conflict_dir = {e: 1 for e in REQUIRED_EVIDENCE}
        conflict_dir["E02"] = -1                 # E01(+1) · E02(−1) = −1
        conflicted = run(fabric=fabric_for(direction=conflict_dir))
        assert conflicted.entry_logic_steps["conflict"]["required_conflict"] \
            is True
        assert conflicted.entry_logic_steps["conflict"]["multiplier"] == \
            pytest.approx(0.6)
        if plain.status == EMITTED and conflicted.status == QUARANTINED:
            assert conflicted.final_score < plain.final_score
        assert conflicted.final_score < plain.final_score + 1e-12

    def test_redundancy_is_measured_not_assumed(self):
        # no supplied series ⇒ no penalty is invented
        plain = run()
        assert plain.entry_logic_steps["redundancy"]["rho"] is None
        assert plain.entry_logic_steps["redundancy"]["reason"] == \
            "NO_REDUNDANCY"
        # two perfectly correlated component series ⇒ ρ>0.85 ⇒ the lower-Q
        # engine's contribution is halved and the redundancy penalty applies
        n = 48
        series = [float(i % 7) for i in range(n)]
        red = run(component_series={"structure": series,
                                   "liquidity": [x * 2.0 for x in series]},
                  q_i={**{c: 0.9 for c in SCORED}, "liquidity": 0.4})
        assert red.entry_logic_steps["redundancy"]["dropped"] == "liquidity"
        assert abs(red.entry_logic_steps["redundancy"]["rho"]) > 0.85
        assert red.entry_logic_steps["redundancy"]["penalty_multiplier"] == \
            pytest.approx(0.7)
        assert red.gate_block["results"][4]["measured"] == pytest.approx(0.3)
        assert red.gate_block["results"][4]["passed"] is True   # 0.3 ≤ 0.3

    def test_empty_fabric_is_vacuous_and_blocked(self):
        """An empty fabric must never reach a score: the family refuses before
        scoring (fail-closed, one step earlier than the vacuous guard in the
        combiner — both are blocking, neither is a permission)."""
        empty = EvidenceFabric.assemble(symbol="BTCUSDT", timeframe="1h",
                                       as_of=1000, evidence=[],
                                       data_trust=0.9)
        ev = run(fabric=empty, lineage=["obs-1"])
        assert ev.status == NOT_EMITTED
        assert ev.reason.startswith("REQUIRED_EVIDENCE_MISSING")
        assert ev.final_score == 0.0 and ev.raw == 0.0
        assert ev.gate_block["action"] == "DO_NOT_EMIT"
        # the combiner's own guard, reached directly, is the same verdict
        from apex.fabric.context import setup_score
        s = setup_score(empty, s_i={}, q_i={})
        assert s["reason"] == "VACUOUS_NO_EVIDENCE" and s["final"] < q_min_setup()


class TestSetupEventMaterialization:
    def test_setup_event_carries_the_ddl_columns_and_field_22(self):
        ev = run().to_setup_event()
        ddl = {"setup_id", "timestamp", "symbol", "timeframe", "pattern_ids",
               "direction", "entry_price", "stop_loss", "take_profit",
               "risk_reward", "confidence", "quality", "validity",
               "snapshot_id", "parent_ids", "payload_hash", "regime",
               "utc_activity_window_id", "lineage", "authority",
               "authority_scope"}
        assert ddl <= set(ev)
        assert ev["family_id"] == FAMILY_ID           # AD.1 field 22
        assert ev["direction"] in ("BULLISH", "BEARISH")
        assert ev["quality"] == "Q1" and ev["validity"] == 1
        # Decimal/text at the store boundary (AI.1)
        assert isinstance(ev["entry_price"], str)
        assert isinstance(ev["stop_loss"], str)
        assert len(ev["snapshot_id"]) == 64

    def test_row_satisfies_the_frozen_store_checks(self):
        import sqlite3
        from apex.data_catalog.store.sqlite_store import CH4_DDL
        db = sqlite3.connect(":memory:")
        db.executescript(CH4_DDL)
        ev = run().to_setup_event()
        cols = ("setup_id", "timestamp", "symbol", "timeframe", "pattern_ids",
                "direction", "entry_price", "stop_loss", "take_profit",
                "risk_reward", "confidence", "quality", "validity",
                "snapshot_id", "parent_ids", "payload_hash", "regime",
                "utc_activity_window_id", "lineage", "authority",
                "authority_scope")
        db.execute(f"INSERT INTO setup_candidate ({','.join(cols)}) VALUES "
                   f"({','.join('?' * len(cols))})",
                   tuple(str(ev[c]) if c == "timestamp" else ev[c]
                         for c in cols))
        db.commit()
        assert db.execute("SELECT COUNT(*) FROM setup_candidate").fetchone()[0] == 1
        # pattern_evidence accepts the materialized AC.1 row too
        from apex.pattern.detect import CATALOGUE_BY_NAME, entity_for
        row = entity_for(CATALOGUE_BY_NAME["Double Top"]).to_pattern_evidence_row()
        names = [d[1] for d in db.execute("PRAGMA table_info(pattern_evidence)")]
        unknown = sorted(set(row) - set(names))
        assert unknown == []
        db.execute("INSERT INTO pattern_evidence (" + ",".join(row) + ") "
                   "VALUES (" + ",".join("?" * len(row)) + ")",
                   tuple(None if v is None else (str(v) if isinstance(v, (dict, list)) else v)
                         for v in row.values()))
        db.commit()

    def test_family_id_is_immutable_once_recorded(self):
        import dataclasses
        ev = run()
        with pytest.raises(dataclasses.FrozenInstanceError):
            ev.family_id = "FAM-OTHER"          # type: ignore[misc]
        # and the recorded value is stable across materializations
        assert ev.to_setup_event()["family_id"] == ev.to_setup_event()["family_id"]

    def test_rejection_still_carries_the_family_identity(self):
        ev = run(atr=None).to_setup_event()
        assert ev["family_id"] == FAMILY_ID
        assert ev["status"] == NOT_EMITTED
        assert ev["quality"] == "QX" and ev["validity"] == 0

    def test_determinism_replay_is_byte_identical(self):
        a = run()
        b = run()
        assert a == b                                    # frozen dataclass eq
        ea, eb = a.to_setup_event(), b.to_setup_event()
        assert ea["setup_id"].startswith("setup-")
        # the store payload must be canonically serializable: gate maps are
        # projected into ordered lists of dicts (no int keys, no GateResult)
        payload = {k: v for k, v in ea.items() if k not in ("gates",)}
        payload["gates"] = [dict(v) for v in
                           sorted(ea["gates"]["results"].values(),
                                  key=lambda r: r["gate"])]
        text = canonical_json(payload)
        assert text == canonical_json({k: v for k, v in eb.items()
                                      if k not in ("gates",)} | {
            "gates": [dict(v) for v in sorted(eb["gates"]["results"].values(),
                                             key=lambda r: r["gate"])]})
        assert '"gates":[' in text.replace(" ", "")
        with pytest.raises(Exception):
            canonical_json({"nested": {"bad": {1: "int key"}}})


class TestGateIntegration:
    def test_a_bad_snapshot_blocks_without_touching_other_gates(self):
        """The family always records a self-consistent snapshot, so a tampered
        pair is proven at the gate matrix itself (Gate 11 only — the other
        twelve are untouched)."""
        from apex.setup.gates import gate11_snapshot_lineage, gate1_final_score
        good = {"a": 1}
        good_snap = sha256_hex(canonical_json(good))
        assert gate11_snapshot_lineage(good_snap, good, ["obs-1"]).passed
        tampered = gate11_snapshot_lineage(good_snap, {"a": 2}, ["obs-1"])
        assert tampered.passed is False
        assert tampered.reason == "GATE11_SNAPSHOT_HASH_MISMATCH"
        assert gate1_final_score(0.60).passed is True     # unaffected
        # a fabricated fabric hash is refused before scoring
        fake = fabric_for("1h")
        object.__setattr__(fake, "hash", "0" * 64)
        ev = run(fabric=fake)
        assert ev.status == NOT_EMITTED
        assert ev.reason == "FABRIC_HASH_MISMATCH"

    def test_gate_context_is_the_same_matrix_as_the_standalone_gates(self):
        ev = run(mtf_state="CONFLICTING")
        assert ev.gate_block["blocked_by"] == [5]
        # and the same input through run_all() gives the same verdict
        ctx = dict(final_score=0.6, window_qualities=[(0.9, 0.0)],
                   conflict_penalty=0.0, redundancy_penalty=0.0,
                   mtf_state="CONFLICTING", h_norm=0.4, temporal_quality="Q3",
                   volatility_quality="Q2", forecast={"quality": "Q3"},
                   snapshot_id="0" * 64, payload={"x": 1},
                   lineage=["obs-1"], q_forecast=0.6,
                   package={"package_version": 1,
                            "parameter_package_id": "p"},
                   timeframe="1h")
        ctx["snapshot_id"] = sha256_hex(canonical_json(ctx["payload"]))
        assert run_all(ctx)["blocked_by"] == [5]

    def test_evaluation_type_is_stable(self):
        assert isinstance(run(), SetupEvaluation)
