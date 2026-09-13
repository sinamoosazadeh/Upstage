"""CP-6 battery — Pattern Intelligence (Ch.9 §9.0/§9.1/§9.2) and the
golden-fixture schema lock (`GF_SC_01` / `GF_SC_02`).

Every fixture expectation is re-derived here from the frozen E08 detectors —
the fixture file is never trusted blindly (ADR-P2-007/ADR-P2-014).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from apex.engines.e08_wyckoff import (EngineParams, atr14, detect_spring,
                                      detect_ut, range_z, spring_recovered)
from apex.errors import WaveOutError
from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import sha256_hex
from apex.pattern.detect import (
    AC1_FAMILIES,
    CATALOGUE,
    CATALOGUE_BY_NAME,
    DETECTORS,
    EXCLUDED_PAT_DER,
    PROVENANCE_CLASSES,
    RESEARCH_ONLY_PATTERNS,
    PatternEntity,
    PatternHit,
    assert_scoring_admissible,
    detect_all,
    detect_broadening,
    detect_double_bottom,
    detect_double_top,
    detect_falling_wedge,
    detect_flag,
    detect_head_and_shoulders,
    detect_inverse_head_and_shoulders,
    detect_quasimodo,
    detect_rectangle,
    detect_rising_wedge,
    detect_triangle_ascending,
    detect_triangle_descending,
    detect_triangle_symmetrical,
    entity_for,
    from_e08_spring,
    from_e08_upthrust,
    get_params,
    is_invalidated,
    swings,
)
from apex.quality.numerical import formula_volume_ratio

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"
P = EngineParams()


def bars_from(doc):
    return doc["fixtures"][0]["bars"]


def load(name):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def derive(bars, idx=16, kind="spring"):
    """Re-derivation of the fixture's expected block (independent recompute)."""
    if kind == "spring":
        lvl = min(b["l"] for b in bars[:idx])
    else:
        lvl = max(b["h"] for b in bars[:idx])
    atr = atr14(bars)
    sma = sum(b["v"] for b in bars[:idx]) / idx
    vr = float(formula_volume_ratio(Decimal(repr(bars[idx]["v"])),
                                    Decimal(repr(sma)))[0])
    rz = range_z([b["h"] - b["l"] for b in bars[:idx + 1]])
    if kind == "spring":
        sc = bool(detect_spring(bars[idx]["l"], lvl, bars[idx]["c"], atr, vr,
                                0.0, params=P)) and bool(
            spring_recovered(bars, lvl, idx, P.spring_bars))
    else:
        sc = bool(detect_ut(bars[idx]["h"], lvl, bars[idx]["c"], atr, vr,
                            params=P))
    return {"sc": sc, "vol_ratio": vr, "range_z": rz}


# ---------------------------------------------------------------------------
# The golden fixtures (Ch.9 §9.1 schema lock)
# ---------------------------------------------------------------------------

class TestGoldenFixtures:
    def test_gf_sc_01_exists_and_matches_the_locked_shape(self):
        doc = load("gf_sc_01.json")
        assert doc["kind"] == "SYNTHETIC"
        assert doc["symbol"] == "SYNTH"
        assert doc["timeframe"] == "6h"
        assert doc["pattern_id"] == "GF_SC_01_SPRING_SHAPE"
        f = doc["fixtures"][0]
        assert set(f) == {"id", "bars", "expected", "hash"}    # Ch.13 §8 shape
        assert set(f["expected"]) == {"sc", "vol_ratio", "range_z"}
        # documented: 12 bars around 100 … candidate index 4 — the documented
        # 12-bar tail is present and the candidate is its 4th-from-last bar.
        assert len(f["bars"]) == 20
        assert f["bars"][-12:][0]["l"] >= 99.0
        spring_bar = f["bars"][16]
        assert spring_bar["l"] == 98.0                  # documented L=98.0
        assert spring_bar["c"] == pytest.approx(99.4)   # documented close
        assert spring_bar["c"] > 99.3                   # "back above 99.3"

    def test_gf_sc_01_expected_values_re_derive_and_fire(self):
        doc = load("gf_sc_01.json")
        bars = bars_from(doc)
        got = derive(bars, 16, "spring")
        assert got == doc["fixtures"][0]["expected"]
        assert got["sc"] is True                        # fixture FIRES

    def test_gf_sc_01_hash_lock(self):
        doc = load("gf_sc_01.json")
        bars = bars_from(doc)
        assert doc["fixtures"][0]["hash"] == "sha256:" + sha256_hex(
            canonical_json(bars))

    def test_gf_sc_02_shape_re_derivation_and_fire(self):
        doc = load("gf_sc_02.json")
        bars = bars_from(doc)
        assert len(bars) == 20
        ut_bar = bars[16]
        assert ut_bar["h"] == 102.5                     # documented H=102.5
        assert ut_bar["c"] < max(b["h"] for b in bars[:16])   # back inside
        got = derive(bars, 16, "upthrust")
        assert got == doc["fixtures"][0]["expected"]
        assert got["sc"] is True
        assert doc["fixtures"][0]["hash"] == "sha256:" + sha256_hex(
            canonical_json(bars))

    def test_negative_control_no_recovery_no_spring(self):
        """Without the 3-bar return the shape is NOT a Spring (the fixture is
        not tautological)."""
        bars = bars_from(load("gf_sc_01.json"))
        lvl = min(b["l"] for b in bars[:16])
        broken = [dict(b) for b in bars]
        for i in (17, 18, 19):
            broken[i]["c"] = 98.5          # never closes back above the range low
        broken[17]["h"] = min(broken[17]["h"], 99.0)
        broken[17]["l"] = min(broken[17]["l"], 98.4)
        broken[18]["h"] = min(broken[18]["h"], 99.0)
        broken[18]["l"] = min(broken[18]["l"], 98.4)
        broken[19]["h"] = min(broken[19]["h"], 99.0)
        broken[19]["l"] = min(broken[19]["l"], 98.4)
        assert spring_recovered(broken, lvl, 16, P.spring_bars) is False
        assert derive(broken, 16, "spring")["sc"] is False

    @pytest.mark.parametrize("i", range(3, 13))
    def test_gf_sc_03_12_are_schema_only_wave_out(self, i):
        # Wave-Out until bars exist (§9.1): tests may assert schema only.
        from apex.errors import wave_out
        with pytest.raises(WaveOutError) as ei:
            raise wave_out("gf_sc_03_12", f"GF_SC_{i:02d}_BARS_NOT_IN_FREEZE")
        assert ei.value.feature == "gf_sc_03_12"

    def test_fixture_bars_are_closed_and_in_order(self):
        for name, kind in (("gf_sc_01.json", "spring"), ("gf_sc_02.json", "upthrust")):
            for bar in bars_from(load(name)):
                assert bar["h"] >= max(bar["o"], bar["c"])
                assert bar["l"] <= min(bar["o"], bar["c"])
                assert bar["h"] >= bar["l"]


# ---------------------------------------------------------------------------
# E08-backed Spring / Upthrust delegation (never a re-derivation of E08)
# ---------------------------------------------------------------------------

class TestWyckoffDelegation:
    def test_spring_hit_carries_row_level_evidence(self):
        bars = bars_from(load("gf_sc_01.json"))
        lvl = min(b["l"] for b in bars[:16])
        hit = from_e08_spring(bars, lvl, 16, atr14(bars),
                              derive(bars, 16, "spring")["vol_ratio"])
        assert hit is not None and hit.pattern_id == "PAT-WYC-001"
        assert hit.direction == +1 and hit.anchors["spring_low"] == 98.0
        ev = hit.to_evidence(symbol="SYNTH", timeframe="6h", as_of=1,
                             snapshot_id="e" * 64, lineage=("obs-1",))
        assert ev["invalidation"] == {"level": 98.0, "side": "DOWN"}

    def test_upthrust_hit(self):
        bars = bars_from(load("gf_sc_02.json"))
        lvl = max(b["h"] for b in bars[:16])
        hit = from_e08_upthrust(bars, lvl, 16, atr14(bars),
                                derive(bars, 16, "upthrust")["vol_ratio"])
        assert hit is not None and hit.pattern_id == "PAT-WYC-002"
        assert hit.direction == -1 and hit.invalidation_side == "UP"

    def test_no_e08_no_hit(self):
        bars = [dict(b) for b in bars_from(load("gf_sc_01.json"))]
        bars[16]["l"] = 99.6          # no penetration at all
        lvl = min(b["l"] for b in bars[:16])
        assert from_e08_spring(bars, lvl, 16, atr14(bars), 2.0) is None


# ---------------------------------------------------------------------------
# The 20-row frozen catalogue and its governance
# ---------------------------------------------------------------------------

class TestCatalogueGovernance:
    def test_exactly_twenty_rows_in_document_order(self):
        assert len(CATALOGUE) == 20
        assert [r.name for r in CATALOGUE][:5] == [
            "Double Top", "Double Bottom", "Head & Shoulders", "Inverse H&S",
            "Triangle Ascending"]
        assert CATALOGUE[-1].name == "Upthrust"

    def test_three_harmonics_are_research_only(self):
        assert RESEARCH_ONLY_PATTERNS == ("PAT-STR-011", "PAT-HAR-001",
                                         "PAT-HAR-002", "PAT-HAR-003")
        for row in CATALOGUE:
            if row.name in ("Three Drives", "Gartley", "Bat"):
                assert row.lifecycle_status == "RESEARCH_ONLY"
                assert row.provenance == "Harmonic (research-only)"

    def test_research_only_entity_cannot_carry_scoring(self):
        row = CATALOGUE_BY_NAME["Gartley"]
        ent = entity_for(row)
        assert ent.setup_score_contribution_class == "advisory"
        with pytest.raises(ValueError, match="PATTERN_RESEARCH_SCORING_QX"):
            PatternEntity(**{**ent.__dict__,
                             "setup_score_contribution_class": "s_i_component"})

    def test_research_only_never_enters_the_permission_path(self):
        for row in CATALOGUE:
            ent = entity_for(row)
            if ent.lifecycle_status != "ACTIVE":
                with pytest.raises(WaveOutError):
                    assert_scoring_admissible(ent)
            else:
                assert_scoring_admissible(ent)

    def test_advisory_active_rows_are_still_not_scorable(self):
        with pytest.raises(WaveOutError, match="PATTERN_ADVISORY_NO_SCORING"):
            assert_scoring_admissible(entity_for(CATALOGUE_BY_NAME["Wolfe Wave"]))

    def test_pat_der_exclusions_are_recorded(self):
        assert EXCLUDED_PAT_DER == ("PAT-DER-002", "PAT-DER-007", "PAT-DER-008")

    def test_provenance_classes_are_the_ac1_enum(self):
        assert PROVENANCE_CLASSES == ("RESEARCH_ONLY", "ACTIVE", "DEPRECATED",
                                      "harmonic_demotion_round_2")

    def test_legacy_rows_have_no_pat_id_by_narrative_reference(self):
        # AC.5 #1: the catalogue does not auto-materialize AC.1 — an entity
        # must be built explicitly (which is exactly what entity_for does).
        with pytest.raises(ValueError, match="PATTERN_ID_QX"):
            PatternEntity(pattern_id="Double Top", family="Price Action",
                          formation_sequence="x", required_context=(),
                          evidence_dependencies=("E01",),
                          invalidation_rules=("r",), provenance_class="ACTIVE",
                          lifecycle_status="ACTIVE",
                          setup_score_contribution_class="s_i_component",
                          template_reconciliation="AB.3")


class TestAC1Entity:
    def test_all_ten_mandatory_fields_required(self):
        with pytest.raises((TypeError, ValueError)):
            PatternEntity(pattern_id="PAT-STR-099", family="Price Action")

    def test_orphan_pattern_rejected(self):
        with pytest.raises(ValueError, match="PATTERN_ORPHAN_QX"):
            entity = entity_for(CATALOGUE_BY_NAME["Double Top"])
            object.__setattr__(entity, "evidence_dependencies", ())
            entity.__post_init__()

    def test_dependency_must_be_a_frozen_engine(self):
        with pytest.raises(ValueError, match="PATTERN_DEPENDENCY_QX"):
            e = entity_for(CATALOGUE_BY_NAME["Double Top"])
            object.__setattr__(e, "evidence_dependencies", ("E13",))
            e.__post_init__()

    def test_family_outside_medium_scope_rejected(self):
        with pytest.raises(ValueError, match="PATTERN_FAMILY_QX"):
            e = entity_for(CATALOGUE_BY_NAME["Double Top"])
            object.__setattr__(e, "family", "Multi-Timeframe Composite")
            e.__post_init__()
        assert "Futures-Derivatives" in AC1_FAMILIES

    def test_pattern_evidence_row_materializes_the_ddl_columns(self):
        row = entity_for(CATALOGUE_BY_NAME["Double Top"]).to_pattern_evidence_row()
        required = {"pattern_id", "family", "formation_sequence",
                    "evidence_dependencies", "invalidation_rules",
                    "provenance_class", "lifecycle_status",
                    "setup_score_contribution_class"}
        assert required <= set(row)
        assert all(row[k] for k in required)
        # store CHECK constraints expect these exact enums
        assert row["provenance_class"] in ("RESEARCH_ONLY", "ACTIVE", "DEPRECATED")
        assert row["lifecycle_status"] in ("ACTIVE", "RESEARCH_ONLY", "DEPRECATED")
        assert row["setup_score_contribution_class"] in (
            "s_i_component", "q_i_component", "convergence_weight", "advisory")

    def test_harmonic_provenance_row_class_is_the_demotion_record(self):
        row = entity_for(CATALOGUE_BY_NAME["Bat"])
        assert row.provenance_class == "harmonic_demotion_round_2"


# ---------------------------------------------------------------------------
# T_PATTERN — each family on its fixture: deterministic, no look-ahead
# ---------------------------------------------------------------------------

def series(pairs):
    highs = [p[0] for p in pairs]
    lows = [p[1] for p in pairs]
    closes = [p[2] for p in pairs]
    return highs, lows, closes

class TestDetectors:
    ATR = 1.0

    @staticmethod
    def _bars(triples):
        """(high, low, close) triples → the {o,h,l,c} bar shape of Ch.13 §8."""
        return [{"o": c, "h": h, "l": l, "c": c, "v": 1000.0}
                for h, l, c in triples]

    def test_double_top_and_bottom(self):
        r = self._bars([(101.0, 100.0, 100.5)] * 6 + [(101.0, 100.0, 97.0)])
        hit = detect_double_top(r, self.ATR,
                                swing_anchor=([(2, 102.0), (5, 102.05)],
                                              [(3, 98.0)]))
        assert hit is not None and hit.pattern_id == "PAT-STR-001"
        assert hit.direction == -1
        assert hit.anchors["h1"] == 102.0 and hit.anchors["h2"] == 102.05
        assert hit.invalidation_level == 102.05 and hit.invalidation_side == "UP"
        # equality tolerance |H1−H2| ≤ 0.15·ATR — a 0.5·ATR gap never fires
        assert detect_double_top(r, self.ATR,
                                 swing_anchor=([(2, 102.0), (5, 102.5)],
                                               [(3, 98.0)])) is None
        bot = detect_double_bottom(
            self._bars([(100.0, 99.0, 99.5)] * 6 + [(102.0, 99.0, 101.8)]),
            self.ATR,
            swing_anchor=([(3, 101.0)], [(1, 96.0), (5, 96.05)]))
        assert bot is not None and bot.pattern_id == "PAT-STR-002"
        assert bot.direction == +1 and bot.invalidation_side == "DOWN"

    def test_double_top_derives_swings_locally_too(self):
        h = [100.0, 101.0, 102.0, 101.2, 101.6, 101.3, 102.05, 101.4, 101.0,
             100.9, 101.0]
        l = [99.0, 99.6, 100.0, 99.4, 98.6, 99.5, 100.1, 99.6, 99.2, 98.9, 99.4]
        c = [99.5, 100.5, 101.5, 100.0, 99.9, 100.8, 101.6, 100.2, 100.6,
             98.0, 100.0]
        bars = [{"o": ci, "h": hi, "l": li, "c": ci, "v": 1000.0}
                for hi, li, ci in zip(h, l, c)]
        derived = detect_double_top(bars, self.ATR)
        assert derived is not None and derived.index == 9
        assert derived.anchors["pivot_low"] == 98.6

    def test_detectors_require_a_governed_atr(self):
        with pytest.raises(ValueError, match="PATTERN_ATR_QX"):
            detect_double_top(self._bars([(1.0, 1.0, 1.0)]), float("nan"))
        with pytest.raises(ValueError, match="PATTERN_ATR_QX"):
            detect_double_top(self._bars([(1.0, 1.0, 1.0)]), 0.0)

    def test_malformed_bar_fails_closed(self):
        with pytest.raises(ValueError, match="PATTERN_BAR_QX"):
            detect_double_top([{"o": 1.0, "h": 0.5, "l": 1.2, "c": 1.0,
                                "v": 1.0}], 1.0)

    def test_head_and_shoulders_and_inverse(self):
        h = [100.0, 100.5, 102.0, 100.8, 100.6, 104.0, 101.0, 100.9, 102.1,
             100.6, 100.4]
        l = [99.0, 99.6, 100.0, 99.2, 98.8, 100.2, 99.4, 99.1, 100.1, 99.0, 98.4]
        c = [99.5, 100.0, 101.5, 99.8, 99.5, 103.5, 100.5, 99.9, 101.6, 99.2,
             98.5]
        l_t = [99.2] * len(l)          # the two troughs that form the neckline
        mk = lambda H, L, C: [{"o": ci, "h": hi, "l": li, "c": ci, "v": 1.0}
                              for hi, li, ci in zip(H, L, C)]
        hit = detect_head_and_shoulders(mk(h, l_t, c), self.ATR)
        assert hit is not None and hit.pattern_id == "PAT-STR-003"
        assert hit.direction == -1
        assert abs(hit.anchors["left"] - hit.anchors["right"]) <= 0.25 * self.ATR
        h_wide = list(h)
        h_wide[8] = 102.4
        assert h_wide[8] - h[2] > 0.25 * self.ATR
        assert detect_head_and_shoulders(mk(h_wide, l_t, c), self.ATR) is None
        inv = detect_inverse_head_and_shoulders(
            self._bars([(100.6, 100.0, 100.5), (100.6, 98.0, 98.5),
                        (100.6, 97.0, 98.0), (100.6, 98.5, 99.0),
                        (100.6, 95.5, 96.5), (100.6, 94.0, 95.0),
                        (100.6, 96.0, 97.0), (100.6, 99.0, 99.5),
                        (100.6, 98.1, 98.4), (100.6, 100.5, 101.5),
                        (100.6, 100.5, 101.6), (100.6, 100.5, 101.6)]),
            self.ATR,
            swing_anchor=([(2, 100.6), (7, 100.6)],
                          [(1, 98.0), (4, 94.0), (8, 98.1)]))
        assert inv is not None and inv.pattern_id == "PAT-STR-004"
        assert inv.direction == +1

    def test_triangles(self):
        asc = detect_triangle_ascending(
            self._bars([(101.5, 99.0, 100.5), (101.6, 99.2, 100.6),
                        (101.7, 99.4, 100.7), (101.8, 99.6, 100.8),
                        (101.9, 99.8, 100.9), (102.0, 100.0, 101.0),
                        (102.1, 100.2, 101.1), (102.2, 100.4, 101.2),
                        (102.3, 100.6, 102.5), (102.4, 100.8, 102.6)]),
            self.ATR,
            swing_anchor=([(1, 102.0), (3, 102.01), (5, 102.0), (7, 101.99)],
                          [(2, 99.6), (4, 99.9), (6, 100.1), (8, 100.3)]))
        assert asc is not None and asc.pattern_id == "PAT-STR-005"
        assert asc.direction == +1
        # fewer than 4 boundary touches ⇒ no triangle (§9.1 tolerance row)
        assert detect_triangle_ascending(
            self._bars([(101.0, 99.0, 100.5)] * 10), self.ATR,
            swing_anchor=([(1, 102.0), (3, 102.01)],
                          [(2, 99.6), (4, 99.9), (6, 100.1), (8, 100.3)])) is None
        # a falling sloping side is not "Higher Lows"
        assert detect_triangle_ascending(
            self._bars([(101.0, 99.0, 100.5)] * 10), self.ATR,
            swing_anchor=([(1, 102.0), (3, 102.01), (5, 102.0), (7, 101.99)],
                          [(2, 100.3), (4, 100.1), (6, 99.9), (8, 99.6)])) is None
        desc = detect_triangle_descending(
            self._bars([(101.0, 98.5, 100.0)] * 8
                       + [(100.9, 98.4, 97.9), (100.8, 98.3, 97.5)]),
            self.ATR,
            swing_anchor=([(1, 100.0), (3, 99.8), (5, 99.6), (7, 99.4)],
                          [(2, 98.01), (4, 98.0), (6, 98.02), (8, 98.0)]))
        assert desc is not None and desc.pattern_id == "PAT-STR-006"
        assert desc.direction == -1
        sym = detect_triangle_symmetrical(
            self._bars([(101.0, 99.0, 100.0)] * 8
                       + [(103.0, 100.0, 102.4)]), self.ATR,
            swing_anchor=([(1, 102.0), (5, 101.5)], [(3, 99.0), (7, 99.6)]))
        assert sym is not None and sym.pattern_id == "PAT-STR-007"
        assert sym.direction == +1

    def test_flag_and_pennant_share_one_detector(self):
        bars = self._bars([(100.5, 99.5, 100.0), (101.5, 100.5, 101.0),
                           (102.5, 101.5, 102.0), (103.5, 102.5, 103.0),
                           (104.5, 103.5, 104.0), (104.6, 103.8, 104.2),
                           (104.7, 103.7, 103.6), (104.8, 103.8, 104.3),
                           (104.9, 103.9, 104.2), (106.0, 105.0, 105.9)])
        hit = detect_flag(bars, 1.0, direction=+1, flag_bars=3, pole_end_idx=5)
        assert hit is not None and hit.pattern_id == "PAT-STR-008"
        assert hit.direction == +1
        # consolidation taller than 0.5·pole ⇒ not a flag
        tall = self._bars([(100.5, 99.5, 100.0), (101.5, 100.5, 101.0),
                           (102.5, 101.5, 102.0), (103.5, 102.5, 103.0),
                           (104.5, 103.5, 104.0), (106.0, 103.0, 104.2),
                           (106.2, 103.1, 104.0), (106.1, 102.9, 104.3),
                           (106.0, 103.0, 104.2), (106.5, 105.0, 106.4)])
        assert detect_flag(tall, 1.0, direction=+1, flag_bars=3,
                           pole_end_idx=5) is None
        with pytest.raises(ValueError, match="PATTERN_DIRECTION_QX"):
            detect_flag(bars, 1.0, direction=0, flag_bars=3)
        # the Pennant row shares the detector and keeps its own catalogue id
        assert CATALOGUE_BY_NAME["Pennant"].detector == "detect_flag"

    def test_quasimodo(self):
        closes = [100.0, 99.0, 100.5, 103.0, 100.0, 96.0, 98.5, 100.2, 99.0,
                  100.8, 96.4, 97.0]
        bars = [{"o": c, "h": c + 0.5, "l": c - 0.5, "c": c, "v": 1.0}
                for c in closes]
        hit = detect_quasimodo(bars, 1.0,
                               swing_anchor=([(1, 102.0), (3, 104.0), (9, 101.2)],
                                             [(5, 95.0), (7, 97.0)]))
        assert hit is not None and hit.pattern_id == "PAT-STR-010"
        assert hit.direction == -1
        assert hit.anchors["hh"] == 104.0 and hit.anchors["ll"] == 95.0
        # depth below θ_depth·ATR is not a quasimodo
        assert detect_quasimodo(bars, 1.0,
                                swing_anchor=([(1, 102.0), (3, 104.0),
                                               (9, 101.2)],
                                              [(5, 103.5), (7, 97.0)])) is None

    def test_wedges(self):
        rw = detect_rising_wedge(
            self._bars([(101.0, 99.0, 100.0)] * 5
                       + [(101.0, 99.0, 99.4), (101.0, 99.0, 96.0)]), 1.0,
            swing_anchor=([(1, 102.0), (3, 103.0)], [(2, 100.5), (4, 101.6)]))
        assert rw is not None and rw.pattern_id == "PAT-STR-012"
        assert rw.direction == -1
        assert rw.invalidation_side == "UP"    # "close above the last HH invalidates"
        # no convergence (widening) ⇒ not a wedge
        assert detect_rising_wedge(
            self._bars([(101.0, 99.0, 100.0)] * 7), 1.0,
            swing_anchor=([(1, 102.0), (3, 103.0)],
                          [(2, 100.5), (4, 99.0)])) is None
        fw = detect_falling_wedge(
            self._bars([(101.0, 99.0, 100.0)] * 5
                       + [(102.0, 100.5, 101.9)]), 1.0,
            swing_anchor=([(1, 101.0), (3, 100.0)], [(2, 98.0), (4, 97.4)]))
        assert fw is not None and fw.pattern_id == "PAT-STR-013"
        assert fw.direction == +1

    def test_rectangle_and_broadening(self):
        rect = detect_rectangle(
            self._bars([(101.0, 99.0, 100.0)] * 8
                       + [(102.6, 101.9, 102.5), (103.0, 102.4, 102.9)]), 0.5,
            swing_anchor=([(1, 102.0), (3, 102.02), (5, 101.99), (7, 102.01)],
                          [(2, 99.0), (4, 98.99), (6, 99.02), (8, 99.0)]))
        assert rect is not None and rect.pattern_id == "PAT-STR-014"
        assert rect.direction == +1
        # equal-level tolerance 0.15·ATR = 0.075 — a 0.2 gap is not "equal"
        assert abs(102.2 - 102.0) > 0.15 * 0.5
        assert detect_rectangle(
            self._bars([(101.0, 99.0, 100.0)] * 8
                       + [(102.8, 102.1, 101.0), (103.0, 102.4, 101.1)]), 0.5,
            swing_anchor=([(1, 102.0), (3, 102.02), (5, 101.99), (7, 102.2)],
                          [(2, 99.0), (4, 98.99), (6, 99.02), (8, 99.0)])) is None
        br = detect_broadening(
            self._bars([(101.0, 99.0, 100.0)] * 6 + [(98.0, 96.5, 97.0)]),
            1.0,
            swing_anchor=([(1, 101.0), (3, 102.0), (5, 103.0)],
                          [(2, 99.0), (4, 98.0), (6, 97.0)]))
        assert br is not None and br.pattern_id == "PAT-STR-015"
        assert br.direction == -1

    def test_detect_all_only_runs_admitted_rows(self):
        h = [100.0, 101.0, 102.0, 101.2, 101.6, 101.3, 102.05, 101.4, 101.0,
             100.9, 101.0]
        l = [99.0, 99.6, 100.0, 99.4, 98.6, 99.5, 100.1, 99.6, 99.2, 98.9, 99.4]
        c = [99.5, 100.5, 101.5, 100.0, 99.9, 100.8, 101.6, 100.2, 100.6,
             98.0, 100.0]
        bars = [{"o": ci, "h": hi, "l": li, "c": ci, "v": 1000.0}
                for hi, li, ci in zip(h, l, c)]
        res = detect_all(bars, 1.0)
        # admitted = ACTIVE rows that carry a detector (14 price-action rows
        # + the 2 E08-backed Wyckoff rows, which run through their own API)
        assert res["n_admitted_rows"] == len(
            [r for r in CATALOGUE if r.lifecycle_status == "ACTIVE"
             and r.detector is not None])
        assert res["n_admitted_rows"] == 16
        assert res["n_run_here"] == 14
        assert list(res["hits"]) == ["PAT-STR-001"]
        for pid in res["hits"]:
            assert pid not in RESEARCH_ONLY_PATTERNS

    def test_no_look_ahead_truncation_is_stable(self):
        h = [100.0, 101.0, 102.0, 101.2, 101.6, 101.3, 102.05, 101.4, 101.0,
             100.9, 101.0]
        l = [99.0, 99.6, 100.0, 99.4, 98.6, 99.5, 100.1, 99.6, 99.2, 98.9, 99.4]
        c = [99.5, 100.5, 101.5, 100.0, 99.9, 100.8, 101.6, 100.2, 100.6,
             98.0, 100.0]
        mk = lambda H, L, C: [{"o": ci, "h": hi, "l": li, "c": ci, "v": 1.0}
                              for hi, li, ci in zip(H, L, C)]
        full = detect_double_top(mk(h, l, c), self.ATR)
        part = detect_double_top(mk(h[:10], l[:10], c[:10]), self.ATR)
        assert (part.index, part.pattern_id, part.invalidation_level) == (
            full.index, full.pattern_id, full.invalidation_level)
        for idx, _v in list(swings(h, l, k=2)[0]) + list(swings(h, l, k=2)[1]):
            assert idx <= len(h) - 1 - 2       # never a swing on an unconfirmed bar

    def test_golden_shaped_spring_bars_also_fire_the_detector(self):
        """The same detector law as the golden fixture, on the documented
        12-bar-tail shape (L=98.9≈98.0 family, close back above the range
        low)."""
        trip = [(105.0, 99.5, 100.5), (104.5, 99.6, 100.8),
                (105.2, 99.4, 100.4), (104.6, 99.7, 100.9),
                (105.3, 99.5, 100.6), (104.7, 99.8, 100.7),
                (105.1, 99.6, 100.5), (104.8, 99.9, 100.8),
                (99.9, 98.9, 99.6), (103.0, 99.5, 100.6),
                (102.2, 99.7, 100.9), (101.5, 100.0, 101.1),
                (101.8, 100.2, 101.2), (102.0, 100.5, 101.4),
                (102.2, 100.8, 101.6), (102.4, 101.0, 101.8)]
        bars = [{"o": 100.5, "h": h, "l": l, "c": c,
                 "v": (2000.0 if i == 8 else 1000.0)}
                for i, (h, l, c) in enumerate(trip)]
        hit = from_e08_spring(bars, 99.5, 8, atr14(bars), 2.0)
        assert hit is not None and hit.pattern_id == "PAT-WYC-001"
        assert hit.anchors["spring_low"] == 98.9
        assert hit.direction == +1

    def test_swing_detection_is_local_and_deterministic(self):
        h = [1.0, 5.0, 2.0, 6.0, 1.0]
        l = [0.0, 1.0, 0.5, 1.2, 0.2]
        sh, sl = swings(h, l, k=1)
        assert sh == [(1, 5.0), (3, 6.0)]
        assert swings(h, l, k=1) == (sh, sl)

    def test_invalidation_is_removal_not_permission(self):
        hit = PatternHit("PAT-STR-001", "Double Top", -1, 3, 102.0, "UP",
                         {}, 0.5)
        assert is_invalidated(hit, 102.5) is True
        assert is_invalidated(hit, 101.9) is False

    def test_detector_registry_matches_the_catalogue_rows(self):
        for row in CATALOGUE:
            if row.detector is not None:
                assert row.detector in DETECTORS
        # every row without a detector is research-only (no silent detection)
        for row in CATALOGUE:
            if row.detector is None:
                assert row.lifecycle_status == "RESEARCH_ONLY"

    def test_governed_params_are_bounded_and_unknown_keys_fail(self):
        p = get_params()
        assert p["theta_eq_atr"] == 0.15 and p["theta_shoulder_atr"] == 0.25
        assert p["pole_min_atr"] == 1.5 and p["flag_max_ratio"] == 0.5
        assert p["triangle_min_touches"] == 4 and p["rect_min_touches"] == 3
        with pytest.raises(ValueError, match="UNKNOWN_PATTERN_PARAM_QX"):
            get_params({"theta_eq_atr_twice": 0.2})
