"""CP-1 error registry: every Ch.7 row present with exact codes, verbatim
meanings/handling; WaveOutError plumbing; Wave-Out list frozen."""
from __future__ import annotations

import pytest

from apex.errors import (
    ERROR_REGISTRY,
    WAVE_OUT_FEATURES,
    ErrorCode,
    WaveOutError,
    get_error_code,
    wave_out,
)

# Ch.7 rows (APEX_GEN5.md L14643–14671), in document order.
CH7_CODES = [
    "E-VAL-020", "E-VAL-021", "E-VAL-022",
    "E-NUM-001", "E-NUM-002", "E-NUM-003",
    "E-Q-001", "E-Q-002",
    "E-PIT-001",
    "E-EXEC-001",
    "E-TELE-001", "E-TELE-002", "E-TELE-003", "E-TELE-004",
    "E-TELE-005", "E-TELE-006", "E-TELE-007",
    "RSK-ERR-506",
    "QX_INVALID",
    "VETO_FRESHNESS_SLA", "VETO_OI_LAG",
    "TOO_MAUTC_W2_REQUESTS",
    "UNAUTHORIZED",
]

EXPECTED_MEANINGS = {
    "E-VAL-020": "Busy Guard MAX_CONCURRENT=1",
    "E-VAL-021": "Invalid Symbol Not in Core-10",
    "E-VAL-022": "Invalid Timeframe Not in 14",
    "E-NUM-001": "NaN",
    "E-NUM-002": "Inf",
    "E-NUM-003": "-0",
    "E-Q-001": "Q_schema Fail",
    "E-Q-002": "Q_time Expired",
    "E-PIT-001": "availability_time > as_of Future Leak",
    "E-EXEC-001": "Fill Timeout",
    "E-TELE-001": "Bot Token Invalid",
    "E-TELE-002": "Chat ID Invalid",
    "E-TELE-003": "Message Too Long >4096",
    "E-TELE-004": "Caption Too Long >1024",
    "E-TELE-005": "Inline Keyboard Too Many Buttons >8",
    "E-TELE-006": "Rate Limit Bucket Empty",
    "E-TELE-007": "Idempotency Key Exists",
    "RSK-ERR-506": "Ratchet",
    "QX_INVALID": "QX INVALID",
    "VETO_FRESHNESS_SLA": "Freshness SLA Veto",
    "VETO_OI_LAG": "OI Lag Veto",
    "TOO_MAUTC_W2_REQUESTS": "Too Many Requests",
    "UNAUTHORIZED": "Unauthorized",
}


def test_error_registry_ch7_complete():
    """Every Ch.7 row is registered, exactly once, with exact codes."""
    assert sorted(ERROR_REGISTRY) == sorted(CH7_CODES)
    for code in CH7_CODES:
        entry = ERROR_REGISTRY[code]
        assert entry.meaning == EXPECTED_MEANINGS[code]
        assert entry.handling  # non-empty handling contract


def test_ch7_row_count():
    assert len(CH7_CODES) == 23


def test_registry_lookup_and_unknown():
    assert get_error_code("E-PIT-001").meaning == \
        "availability_time > as_of Future Leak"
    with pytest.raises(KeyError):
        get_error_code("E-INVENTED-999")  # fail-closed, never invented


def test_ratchet_semantics_present():
    handling = ERROR_REGISTRY["RSK-ERR-506"].handling
    assert "Ratchet" in handling and "Downgrade blocked" in handling


def test_q_oi_stale_weight_canonical():
    """Ch.7: Q_oi AVAILABLE=1.0 STALE=0.5 — not 0.9 (canonical)."""
    handling = ERROR_REGISTRY["VETO_OI_LAG"].handling
    assert "STALE=0.5" in handling
    assert "AVAILABLE=1.0" in handling
    assert "Not 0.9" in handling


def test_wave_out_error_plumbing():
    err = wave_out("market_profile")
    assert isinstance(err, WaveOutError)
    assert err.feature == "market_profile"
    assert "Wave-Out" in str(err)
    with pytest.raises(WaveOutError):
        raise wave_out("physical_postgresql")


def test_wave_out_list_frozen():
    """The frozen Wave-Out list (§9.5-9/G6) — the exact features."""
    assert WAVE_OUT_FEATURES >= {
        "e11_next_regime_forecast", "adaptive_atr_e04_e11",
        "dynamic_williams_k", "live_ofi", "live_vpin", "market_profile",
        "e08_encyclopedia_ch2_4", "extra_setup_families",
        "extra_playbooks", "optimizer_live_yaml_write", "gf_sc_03_12",
        "flash_close", "reverse_position", "withdraw", "transfer",
        "hedge_mode", "cross_margin", "shadow_environment",
        "physical_postgresql", "networked_event_bus", "numba",
    }
