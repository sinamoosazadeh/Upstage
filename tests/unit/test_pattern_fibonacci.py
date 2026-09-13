"""CP-6 battery — in-repo Fibonacci (Ch.9 §9.0 level contract + §9.5-15).

Includes the "not a network service" seam test: the module (and its package)
must never import a transport library.
"""

from __future__ import annotations

import ast
import math
import pathlib
import re

import pytest

from apex.pattern.fibonacci import (
    CONTRACT_VERSION,
    EXTENSION_RATIOS,
    EXPANSION_RATIOS,
    GOLDEN_CONJUGATE,
    GOLDEN_RATIO,
    HARMONIC_RATIOS,
    PROJECTION_RATIOS,
    RETRACE_RATIOS,
    FibLevel,
    confluence,
    extensions,
    expansion,
    get_params,
    golden_identities,
    harmonic_prz,
    ladder,
    level,
    ote_zone,
    projections,
    retracements,
)

FORBIDDEN_IMPORTS = (
    "socket", "ssl", "http", "urllib", "httpx", "requests", "aiohttp",
    "asyncio", "subprocess", "shutil", "telnetlib", "ftplib", "smtplib",
)


class TestFrozenLevelLaw:
    def test_level_formula_is_the_frozen_line(self):
        # Level(r) = A + r·(B − A)
        assert level(100.0, 200.0, 0.0) == 100.0
        assert level(100.0, 200.0, 1.0) == 200.0
        assert level(100.0, 200.0, 0.618) == pytest.approx(161.8)
        assert level(200.0, 100.0, 0.618) == pytest.approx(138.2)
        assert level(100.0, 200.0, 1.618) == pytest.approx(261.8)

    def test_non_finite_and_degenerate_inputs_fail_closed(self):
        with pytest.raises(ValueError, match="FIB_NAN_QX"):
            level(100.0, 200.0, float("nan"))
        with pytest.raises(ValueError, match="FIB_SEGMENT_QX"):
            retracements(float("inf"), 200.0)
        with pytest.raises(ValueError, match="FIB_DEGENERATE_LEG_QX"):
            retracements(100.0, 100.0)
        with pytest.raises(ValueError, match="FIB_DEGENERATE_LEG_QX"):
            projections(100.0, 100.0)

    def test_retracement_ladder_is_within_the_leg(self):
        got = retracements(100.0, 200.0)
        assert set(got) == set(RETRACE_RATIOS)
        for r, v in got.items():
            assert 100.0 - 1e-9 <= v <= 200.0 + 1e-9
        assert got[0.618] == pytest.approx(138.2)
        assert got[0.5] == pytest.approx(150.0)
        # monotone: deeper retracement ⇒ price closer to A
        vals = [got[r] for r in sorted(got)]
        assert all(x >= y for x, y in zip(vals, vals[1:]))

    def test_projection_uses_the_frozen_formula_directly(self):
        got = projections(100.0, 200.0, ratios=(0.618, 1.0))
        assert got[0.618] == pytest.approx(161.8)
        assert got[1.0] == pytest.approx(200.0)

    def test_extensions_lie_beyond_b(self):
        got = extensions(100.0, 200.0)
        assert set(got) == set(EXTENSION_RATIOS)
        for r, v in got.items():
            assert r >= 1.0 and v >= 200.0 - 1e-9
        assert got[1.618] == pytest.approx(261.8)
        assert got[2.0] == pytest.approx(300.0)
        with pytest.raises(ValueError, match="FIB_EXTENSION_RATIO_QX"):
            extensions(100.0, 200.0, ratios=(0.5,))

    def test_down_leg_extensions_go_down(self):
        got = extensions(200.0, 100.0)
        assert all(v <= 100.0 + 1e-9 for v in got.values())

    def test_expansion_uses_the_ab_leg_from_c(self):
        got = expansion(100.0, 150.0, 120.0)
        assert got[1.0] == pytest.approx(170.0)
        assert got[0.618] == pytest.approx(150.9)
        assert set(got) == set(EXPANSION_RATIOS)
        with pytest.raises(ValueError, match="FIB_SEGMENT_QX"):
            expansion(100.0, 150.0, float("nan"))
        with pytest.raises(ValueError, match="FIB_KIND_QX"):
            ladder(100.0, 200.0, kinds=("expansion",))
        with pytest.raises(ValueError, match="FIB_KIND_QX"):
            ladder(100.0, 200.0, kinds=("magic",))

    def test_ladder_records_are_typed_and_serializable(self):
        rows = ladder(100.0, 200.0, kinds=("retrace", "extension"))
        assert all(isinstance(r, FibLevel) for r in rows)
        assert len(rows) == len(RETRACE_RATIOS) + len(EXTENSION_RATIOS)
        d = rows[0].to_dict()
        assert d["contract_version"] == CONTRACT_VERSION
        assert d["source_leg"] == [100.0, 200.0]
        assert set(d) == {"ratio", "price", "kind", "source_leg",
                          "contract_version"}


class TestConfluence:
    def test_levels_within_tolerance_cluster(self):
        out = confluence({"retrace": [138.2], "proj": [138.3, 138.4],
                          "ext": [261.8]}, atr=1.0)
        assert len(out) == 1
        c = out[0]
        assert c["count"] == 3
        assert c["spread"] == pytest.approx(0.2)
        assert {m["source"] for m in c["members"]} == {"retrace", "proj"}
        assert 138.2 < c["centre"] < 138.4

    def test_isolated_levels_are_not_a_confluence(self):
        out = confluence({"a": [100.0], "b": [200.0]}, atr=0.1)
        assert out == []

    def test_nan_level_fails_closed(self):
        with pytest.raises(ValueError, match="FIB_NAN_QX"):
            confluence({"a": [float("nan")]}, atr=1.0)

    def test_missing_atr_fails_closed(self):
        for bad in (0.0, float("nan"), None):
            with pytest.raises(ValueError, match="FIB_ATR_QX"):
                confluence({"a": [1.0]}, atr=bad)


class TestOteAndHarmonics:
    def test_ote_band_numbers_match_the_frozen_law(self):
        got = ote_zone(0.0, 100.0)
        assert got["band"] == (0.62, 0.79)
        assert got["star"] == pytest.approx(29.5)
        assert got["hi"] > got["lo"]
        # the OTE band is the 62–79 % retracement of the leg (Ch.7 §8309 row)
        assert got["lo"] == pytest.approx(100.0 - 79.0)
        assert got["hi"] == pytest.approx(100.0 - 62.0)

    def test_harmonic_prz_records_the_tolerance_never_perfection(self):
        # X=0, A=100, B=61.8 → AB/XA = 0.382 → inside the Bat band 0.382–0.5
        bat = harmonic_prz(0.0, 100.0, 61.8, pattern="BAT")
        assert bat["ab_ratio"] == pytest.approx(0.382)
        assert bat["in_band"] is True
        assert bat["prz"] == pytest.approx(88.6)          # 0.886·XA
        assert bat["lifecycle_status"] == "RESEARCH_ONLY"
        # X=0, A=100, B=38.2 (AB = 0.618 of XA) ⇒ D = 2B − A = −23.6
        g = harmonic_prz(0.0, 100.0, 38.2, pattern="GARTLEY")
        assert g["ab_ratio"] == pytest.approx(0.618)
        assert g["in_band"] is True
        assert g["prz"] == pytest.approx(-23.6)  # AB = CD ⇒ D = 2B − A
        out = harmonic_prz(0.0, 100.0, 20.0, pattern="GARTLEY")
        assert out["in_band"] is False and out["deviation"] > 0
        with pytest.raises(ValueError, match="FIB_HARMONIC_PATTERN_QX"):
            harmonic_prz(0.0, 100.0, 50.0, pattern="BUTTERFLY")
        with pytest.raises(ValueError, match="FIB_HARMONIC_LEG_QX"):
            harmonic_prz(100.0, 100.0, 50.0, pattern="BAT")
        assert HARMONIC_RATIOS["bat_prz"] == 0.886

    def test_golden_ratio_identities_are_the_documented_ones(self):
        ids = golden_identities()
        assert ids["phi"] == GOLDEN_RATIO
        assert ids["phi_conjugate"] == GOLDEN_CONJUGATE
        # φ − 1 = 1/φ (golden ratio) and 0.786 = √0.618 (the frozen note)
        assert math.isclose(ids["phi_conjugate"], ids["one_over_phi"],
                            rel_tol=1e-12)
        assert math.isclose(ids["sqrt_0618"], 0.786, abs_tol=1e-3)
        assert math.isclose(GOLDEN_RATIO, (1 + math.sqrt(5)) / 2, rel_tol=1e-15)

    def test_params_are_bounded_and_unknown_keys_fail(self):
        p = get_params()
        assert p["confluence_atr_mult"] == 0.15
        assert p["ote_low"] == 0.62 and p["ote_high"] == 0.79
        assert p["ote_star"] == 0.705
        with pytest.raises(ValueError, match="UNKNOWN_FIB_PARAM_QX"):
            get_params({"phi2": 2.0})


class TestNoNetworkSeam:
    """§9.5-15: "Fibonacci is apex/pattern/fibonacci.py (not a network
    service)". No CP-6 pattern module may import a transport library."""

    PKG = pathlib.Path(__file__).resolve().parents[2] / "apex" / "pattern"

    def _imported_names(self, path: pathlib.Path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        out = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                out.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    out.add(node.module.split(".")[0])
        return out

    def test_no_transport_imports_anywhere_in_the_package(self):
        files = sorted(self.PKG.glob("*.py"))
        assert files, "apex/pattern must contain the module files"
        for f in files:
            mods = self._imported_names(f)
            assert not (mods & set(FORBIDDEN_IMPORTS)), (
                f"{f.name} imports {sorted(mods & set(FORBIDDEN_IMPORTS))} — "
                f"pattern intelligence must stay in-repo (no network)")

    def test_no_url_literals(self):
        for f in sorted(self.PKG.glob("*.py")):
            text = f.read_text(encoding="utf-8")
            assert not re.search(r"https?://|wss?://", text), (
                f"{f.name} contains a network URL literal")

    def test_module_is_pure_arithmetic(self):
        # determinism (I2): the same inputs give the same outputs, twice
        a = ladder(100.0, 200.0)
        b = ladder(100.0, 200.0)
        assert [x.to_dict() for x in a] == [x.to_dict() for x in b]
        assert [x.to_dict() for x in a] != [x.to_dict() for x in
                                            ladder(200.0, 100.0)]
