"""APEX_GEN5 error registry — Ch.7 Error Codes, verbatim (APEX_GEN5.md L14643–14671).

Every row of the Ch.7 table exists here with its exact code, meaning, and
handling contract. This module is the single registry access point used by
every other module; no module may define its own copy of a Ch.7 code.
`WaveOutError` (G6 / §9.5-9) is defined here: Wave-Out paths raise it and
MUST NOT be implemented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet


@dataclass(frozen=True)
class ErrorCode:
    code: str          # exact Ch.7 identifier (verbatim, incl. odd spellings)
    meaning: str       # Ch.7 "Meaning" column
    handling: str      # Ch.7 "Handling" column (condensed verbatim)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.code}: {self.meaning}"


# Ch.7 rows in document order. The Ch.7 row 'QX INVALID' is normalized to the
# identifier QX_INVALID; the row 'TOO_MAUTC_W2_REQUESTS' keeps its document
# spelling (naming integrity, P20).
_CH7_ROWS = [
    ("E-VAL-020", "Busy Guard MAX_CONCURRENT=1",
     "If second request comes -> E-VAL-020 + Stop button - State table IDLE -> BUSY -> IDLE"),
    ("E-VAL-021", "Invalid Symbol Not in Core-10",
     "Linter if not in Core-10 Fail"),
    ("E-VAL-022", "Invalid Timeframe Not in 14",
     "Linter if not in 14 Fail - Timeframes 14 - 1m,3m,5m,15m,30m,1h,2h,4h,6h,8h,12h,1d,1w,1mo 8h SUPPORTED 3d NOT SUPPORTED"),
    ("E-NUM-001", "NaN",
     "Q_formula_valid 0 + degraded + log - BLOCK if NaN - Missing state: H-L missing -> CandleState QUARANTINED; volume missing -> Q_volume=0 + degraded"),
    ("E-NUM-002", "Inf",
     "Same as NaN"),
    ("E-NUM-003", "-0",
     "Comparison abs(a-b) <= eps => equal"),
    ("E-Q-001", "Q_schema Fail",
     "Q_schema 1 if valid schema else 0 -> QUARANTINED without Q"),
    ("E-Q-002", "Q_time Expired",
     "Q_time(tf) = 1 - min(1, delay/threshold(tf)) threshold=5s 30s 5m - Q_time exp(-lambda*age) lambda=0.1 Not binary"),
    ("E-PIT-001", "availability_time > as_of Future Leak",
     "PIT rule: for each decision, all artifacts availability_time <= as_of - If violates -> BLOCK"),
    ("E-EXEC-001", "Fill Timeout",
     "Execution FSM RECOVERY_REQUIRED"),
    ("E-TELE-001", "Bot Token Invalid",
     "Secrets env var only never .env Memory-only"),
    ("E-TELE-002", "Chat ID Invalid",
     "Idempotency key SHA256(signal_id+timestamp_UTC+chat_id)"),
    ("E-TELE-003", "Message Too Long >4096",
     "text_max 4096 - caption_max 1024 - inline_keyboard_max_buttons 8 max_rows 4"),
    ("E-TELE-004", "Caption Too Long >1024",
     "caption_max 1024"),
    ("E-TELE-005", "Inline Keyboard Too Many Buttons >8",
     "max_buttons 8 max_rows 4"),
    ("E-TELE-006", "Rate Limit Bucket Empty",
     "TokenBucket bucket size 20 tokens refill 20/s consume 1 per message queue if empty retry 3 times exponential backoff 1s,2s,4s Idempotency key TTL 24h"),
    ("E-TELE-007", "Idempotency Key Exists",
     "If exists skip - TTL 24h - Procedure SHA256(signal_id+timestamp_UTC+chat_id)"),
    ("RSK-ERR-506", "Ratchet",
     "Only upgrade allowed - Downgrade blocked - L1 PAUSE -> Normal resume allowed - L2->L1 blocked - L3->L2 blocked - L4->L3 blocked - L5->L4 blocked - Ratchet"),
    ("QX_INVALID", "QX INVALID",
     "QX Degraded - High<Low -> QX INVALID - (high-low)<1e-12 -> DEGRADED - NaN Inf -0 missing -> BLOCK QX"),
    ("VETO_FRESHNESS_SLA", "Freshness SLA Veto",
     "Hard veto - Data stale -> REJECT even P=0.99"),
    ("VETO_OI_LAG", "OI Lag Veto",
     "Hard veto - OI lag -> QUARANTINED - Q_oi AVAILABLE=1.0 STALE=0.5 Not 0.9 - veto_OI_lag hard quarantine Not soft"),
    ("TOO_MAUTC_W2_REQUESTS", "Too Many Requests",
     "TokenBucket queue - Retry exponential 1s,2s,4s max 3"),
    ("UNAUTHORIZED", "Unauthorized",
     "IP whitelist HMAC SHA256 recvWindow 5000ms"),
]

ERROR_REGISTRY: Dict[str, ErrorCode] = {
    row[0]: ErrorCode(*row) for row in _CH7_ROWS
}

CH7_CODES: FrozenSet[str] = frozenset(ERROR_REGISTRY)


def get_error_code(code: str) -> ErrorCode:
    """Registry access. Unknown code -> fail-closed KeyError (never invented)."""
    return ERROR_REGISTRY[code]


class WaveOutError(RuntimeError):
    """Wave-Out discipline (G6 / §9.5-9): the requested capability is
    intentionally NOT implemented per the frozen Wave-Out list. Raising this
    is the ONLY lawful handling; implementing the capability is a failed
    deliverable.

    Attributes:
        feature: Wave-Out feature name (e.g. 'market_profile').
        reason: deterministic reason code (human-stable).
    """

    def __init__(self, feature: str, reason: str) -> None:
        self.feature = feature
        self.reason = reason
        super().__init__(
            f"Wave-Out: {feature} is out of contract ({reason})"
        )


# The frozen Wave-Out list (§9.5-9 / G6), as stable identifiers.
WAVE_OUT_FEATURES: FrozenSet[str] = frozenset({
    "e11_next_regime_forecast",
    "adaptive_atr_e04_e11",
    "dynamic_williams_k",
    "live_ofi",
    "live_vpin",
    "market_profile",
    "e08_encyclopedia_ch2_4",
    "extra_setup_families",
    "extra_playbooks",
    "optimizer_live_yaml_write",
    "gf_sc_03_12",
    "flash_close",
    "reverse_position",
    "withdraw",
    "transfer",
    "hedge_mode",
    "cross_margin",
    "shadow_environment",
    "physical_postgresql",
    "networked_event_bus",
    "numba",
})


def wave_out(feature: str, reason: str = "OUT_OF_CONTRACT") -> "WaveOutError":
    """Construct a WaveOutError (helper for Wave-Out raise sites)."""
    return WaveOutError(feature, reason)
