"""CP-1 errors tests — MATRIX Part I: test_error_registry_ch7_complete
(every Ch.7 row) + Wave-Out plumbing (§9.5-9/G6)."""
from __future__ import annotations

import pathlib
import re

import pytest

from apex.errors import (
    ERROR_REGISTRY,
    WAVE_OUT_REASONS,
    ApexError,
    ErrorSpec,
    FailClosedError,
    UnknownErrorCode,
    WaveOutError,
    get_error,
    raise_for,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Ch.7 rows extracted from APEX_GEN5.md L14645-L14669 (code -> meaning).
CH7_CODES = [
    "E-VAL-020",
    "E-VAL-021",
    "E-VAL-022",
    "E-NUM-001",
    "E-NUM-002",
    "E-NUM-003",
    "E-Q-001",
    "E-Q-002",
    "E-PIT-001",
    "E-EXEC-001",
    "E-TELE-001",
    "E-TELE-002",
    "E-TELE-003",
    "E-TELE-004",
    "E-TELE-005",
    "E-TELE-006",
    "E-TELE-007",
    "RSK-ERR-506",
    "QX INVALID",
    "VETO_FRESHNESS_SLA",
    "VETO_OI_LAG",
    "TOO_MAUTC_W2_REQUESTS",
    "UNAUTHORIZED",
]


def _blueprint_ch7_rows() -> set[str]:
    """Parse Ch.7 table rows straight out of the frozen blueprint so the
    registry is verified against the source of truth, not a copy."""
    text = (REPO_ROOT / "APEX_GEN5.md").read_text(encoding="utf-8")
    section = text.split("## 7. Error Codes", 1)[1]
    section = section.split("\n## ", 1)[0]
    codes = set()
    for line in section.splitlines():
        m = re.match(r"^\|\s*([A-Za-z0-9 _\-]+?)\s*\|", line)
        if m and m.group(1) not in ("Code", "------", ""):
            codes.add(m.group(1))
    return codes


def test_error_registry_ch7_complete() -> None:
    assert set(ERROR_REGISTRY) == set(CH7_CODES) == _blueprint_ch7_rows()
    for code in CH7_CODES:
        spec = ERROR_REGISTRY[code]
        assert isinstance(spec, ErrorSpec)
        assert spec.code == code and spec.meaning and spec.handling


def test_registry_matches_blueprint_meanings() -> None:
    text = (REPO_ROOT / "APEX_GEN5.md").read_text(encoding="utf-8")
    section = text.split("## 7. Error Codes", 1)[1].split("\n## ", 1)[0]
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0] in ERROR_REGISTRY:
            spec = ERROR_REGISTRY[cells[0]]
            assert spec.meaning == cells[1], cells[0]
            assert spec.handling == cells[2], cells[0]


def test_unknown_code_fails_closed() -> None:
    with pytest.raises(UnknownErrorCode):
        get_error("E-NOPE-999")
    with pytest.raises(UnknownErrorCode):
        ApexError("E-NOPE-999")


def test_raise_for() -> None:
    with pytest.raises(ApexError) as exc:
        raise_for("E-PIT-001", {"artifact": "oi"})
    assert exc.value.code == "E-PIT-001"
    assert exc.value.context["artifact"] == "oi"
    assert "E-PIT-001" in str(exc.value)


def test_wave_out_error_plumbing() -> None:
    with pytest.raises(WaveOutError) as exc:
        raise WaveOutError("MARKET_PROFILE_UNAVAILABLE")
    assert exc.value.reason == "MARKET_PROFILE_UNAVAILABLE"
    assert exc.value.context["wave_out_reason"] == "MARKET_PROFILE_UNAVAILABLE"
    # Wave-Out is a deterministic error, never a degraded implementation
    assert isinstance(exc.value, ApexError)
    with pytest.raises(UnknownErrorCode):
        WaveOutError("SOME_INVENTED_CAPABILITY")


def test_wave_out_list_covers_9_5_items() -> None:
    # §9.5-9 enumerates these Wave-Out capabilities (deterministic reasons).
    assert {"SHADOW_ENVIRONMENT", "PHYSICAL_POSTGRESQL", "NETWORKED_EVENT_BUS",
            "NUMBA", "HEDGE_MODE", "CROSS_MARGIN", "GF_SC_03_12",
            "MARKET_PROFILE_UNAVAILABLE", "E08_ENCYCLOPEDIA_CH2_4"} <= WAVE_OUT_REASONS


def test_fail_closed_disposition() -> None:
    err = FailClosedError("E-NUM-001", {"where": "quality"})
    assert err.context["disposition"] == "FAIL_CLOSED"
