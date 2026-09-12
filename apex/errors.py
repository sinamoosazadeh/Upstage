"""APEX_GEN5 error registry — every row of Ch.7 Error Codes (APEX_GEN5.md
L14643-L14671), verbatim semantics, plus the Wave-Out / fail-closed plumbing
required by §9.5-7/G6.

Rules implemented:
* Every Ch.7 row is present with its code, meaning, and handling text.
* Wave-Out items RAISE :class:`WaveOutError` with a deterministic reason
  code — they are never implemented (§9.5-9, G6).
* Unspecified behavior is FAIL_CLOSED, never guessed (§6/G6): unknown error
  lookups raise :class:`UnknownErrorCode`.
* Secrets never appear in error strings (§2.5/G16): the base class
  forbids arbitrary free-form secret material by construction (callers pass
  codes and structured context keys only).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

__all__ = [
    "ApexError",
    "WaveOutError",
    "FailClosedError",
    "UnknownErrorCode",
    "ErrorSpec",
    "ERROR_REGISTRY",
    "get_error",
    "raise_for",
    "WAVE_OUT_REASONS",
]


@dataclass(frozen=True)
class ErrorSpec:
    """One row of the Ch.7 error-code table (code | meaning | handling)."""

    code: str
    meaning: str
    handling: str


# Ch.7 Error Codes — verbatim rows (order of the table preserved).
ERROR_REGISTRY: Mapping[str, ErrorSpec] = {
    "E-VAL-020": ErrorSpec(
        "E-VAL-020",
        "Busy Guard MAX_CONCURRENT=1",
        "If second request comes -> E-VAL-020 + Stop button - State table IDLE -> BUSY -> IDLE",
    ),
    "E-VAL-021": ErrorSpec(
        "E-VAL-021",
        "Invalid Symbol Not in Core-10",
        "Linter if not in Core-10 Fail",
    ),
    "E-VAL-022": ErrorSpec(
        "E-VAL-022",
        "Invalid Timeframe Not in 14",
        "Linter if not in 14 Fail - Timeframes 14 - 1m,3m,5m,15m,30m,1h,2h,4h,6h,8h,12h,1d,1w,1mo 8h SUPPORTED 3d NOT SUPPORTED",
    ),
    "E-NUM-001": ErrorSpec(
        "E-NUM-001",
        "NaN",
        "Q_formula_valid 0 + degraded + log - BLOCK if NaN - NaN/Inf -> Q_formula_valid 0 + degraded + log - Missing state If H-L missing -> CandleState QUARANTINED - If volume missing -> Q_volume=0 + degraded",
    ),
    "E-NUM-002": ErrorSpec(
        "E-NUM-002",
        "Inf",
        "Same as NaN",
    ),
    "E-NUM-003": ErrorSpec(
        "E-NUM-003",
        "-0",
        "Comparison abs(a-b) <= ε => equal",
    ),
    "E-Q-001": ErrorSpec(
        "E-Q-001",
        "Q_schema Fail",
        "Q_schema 1 if valid schema else 0 -> QUARANTINED without Q",
    ),
    "E-Q-002": ErrorSpec(
        "E-Q-002",
        "Q_time Expired",
        "Q_time(tf) = 1 - min(1, delay/threshold(tf)) threshold=5s 30s 5m - Q_time exp(-λ*age) λ=0.1 Not binary",
    ),
    "E-PIT-001": ErrorSpec(
        "E-PIT-001",
        "availability_time > as_of Future Leak",
        "PIT rule: for each decision, all artifacts availability_time <= as_of - If violates -> BLOCK",
    ),
    "E-EXEC-001": ErrorSpec(
        "E-EXEC-001",
        "Fill Timeout",
        "Execution FSM RECOVERY_REQUIRED",
    ),
    "E-TELE-001": ErrorSpec(
        "E-TELE-001",
        "Bot Token Invalid",
        "Secrets env var only never .env Memory-only",
    ),
    "E-TELE-002": ErrorSpec(
        "E-TELE-002",
        "Chat ID Invalid",
        "Idempotency key SHA256(signal_id+timestamp_UTC+chat_id)",
    ),
    "E-TELE-003": ErrorSpec(
        "E-TELE-003",
        "Message Too Long >4096",
        "text_max 4096 - caption_max 1024 - inline_keyboard_max_buttons 8 max_rows 4",
    ),
    "E-TELE-004": ErrorSpec(
        "E-TELE-004",
        "Caption Too Long >1024",
        "caption_max 1024",
    ),
    "E-TELE-005": ErrorSpec(
        "E-TELE-005",
        "Inline Keyboard Too Many Buttons >8",
        "max_buttons 8 max_rows 4",
    ),
    "E-TELE-006": ErrorSpec(
        "E-TELE-006",
        "Rate Limit Bucket Empty",
        "TokenBucket bucket size 20 tokens refill 20/s consume 1 per message queue if empty retry 3 times exponential backoff 1s,2s,4s Idempotency key TTL 24h",
    ),
    "E-TELE-007": ErrorSpec(
        "E-TELE-007",
        "Idempotency Key Exists",
        "If exists skip - TTL 24h - Procedure SHA256(signal_id+timestamp_UTC+chat_id) with example real signal_id=BTCUSDT_15m_BOS_... timestamp=2024-01-01T00:15:00Z chat_id=123456 -> key=a3f2...",
    ),
    "RSK-ERR-506": ErrorSpec(
        "RSK-ERR-506",
        "Ratchet",
        "Only upgrade allowed - Downgrade blocked - L1 PAUSE -> Normal resume allowed - L2->L1 blocked - L3->L2 blocked - L4->L3 blocked - L5->L4 blocked - Ratchet",
    ),
    "QX INVALID": ErrorSpec(
        "QX INVALID",
        "QX INVALID",
        "QX Degraded - High<Low -> QX INVALID - (high-low)<1e-12 -> DEGRADED - NaN Inf -0 missing -> BLOCK QX",
    ),
    "VETO_FRESHNESS_SLA": ErrorSpec(
        "VETO_FRESHNESS_SLA",
        "Freshness SLA Veto",
        "Hard veto - Data stale -> REJECT even P=0.99",
    ),
    "VETO_OI_LAG": ErrorSpec(
        "VETO_OI_LAG",
        "OI Lag Veto",
        "Hard veto - OI lag -> QUARANTINED - Q_oi AVAILABLE=1.0 STALE=0.5 Not 0.9 - veto_OI_lag hard quarantine Not soft",
    ),
    "TOO_MAUTC_W2_REQUESTS": ErrorSpec(
        "TOO_MAUTC_W2_REQUESTS",
        "Too Many Requests",
        "TokenBucket queue - Retry exponential 1s,2s,4s max 3",
    ),
    "UNAUTHORIZED": ErrorSpec(
        "UNAUTHORIZED",
        "Unauthorized",
        "IP whitelist HMAC SHA256 recvWindow 5000ms",
    ),
}

# §9.5-9 / G6 Wave-Out list — raise WaveOutError, do NOT implement.
WAVE_OUT_REASONS: frozenset[str] = frozenset(
    {
        "E11_NEXT_REGIME_FORECAST",
        "ADAPTIVE_ATR_E04_E11",
        "DYNAMIC_WILLIAMS_K",
        "LIVE_OFI_VPIN",
        "MARKET_PROFILE_UNAVAILABLE",
        "E08_ENCYCLOPEDIA_CH2_4",
        "EXTRA_FAMILIES_PLAYBOOKS",
        "OPTIMIZER_WRITING_LIVE_YAML",
        "GF_SC_03_12",
        "FLASHCLOSE_REVERSE_WITHDRAW_TRANSFER",
        "HEDGE_MODE",
        "CROSS_MARGIN",
        "SHADOW_ENVIRONMENT",
        "PHYSICAL_POSTGRESQL",
        "NETWORKED_EVENT_BUS",
        "NUMBA",
    }
)


class ApexError(Exception):
    """Base error: carries a deterministic Ch.7 code + structured context.

    Free-form messages are disallowed by construction; only the registry
    meaning/handling texts and non-secret context keys are rendered.
    """

    def __init__(self, code: str, context: Mapping[str, object] | None = None) -> None:
        if code not in ERROR_REGISTRY:
            raise UnknownErrorCode(code)
        self.code = code
        self.context = dict(context or {})
        spec = ERROR_REGISTRY[code]
        super().__init__(f"{code}: {spec.meaning}")


class WaveOutError(ApexError):
    """Raised when a Wave-Out capability is requested (§9.5-9).

    Wave-Out items are never implemented; requesting one is a deterministic
    error, not a degraded path. Carries the Wave-Out reason in context.
    """

    def __init__(self, reason: str, context: Mapping[str, object] | None = None) -> None:
        if reason not in WAVE_OUT_REASONS:
            raise UnknownErrorCode(f"WAVE_OUT:{reason}")
        ctx = dict(context or {})
        ctx["wave_out_reason"] = reason
        super().__init__("QX INVALID", ctx)
        self.reason = reason


class FailClosedError(ApexError):
    """Explicit fail-closed stop for unspecified/undecidable behavior (§6/G6).

    Stops unsafe execution, preserves integrity, records the reason code.
    """

    def __init__(self, code: str, context: Mapping[str, object] | None = None) -> None:
        super().__init__(code, context)
        self.context.setdefault("disposition", "FAIL_CLOSED")


class UnknownErrorCode(KeyError):
    """Requested error code is not in the frozen Ch.7 registry — fail closed."""


def get_error(code: str) -> ErrorSpec:
    """Registry access (handoff §INTERFACES: error registry access)."""
    try:
        return ERROR_REGISTRY[code]
    except KeyError:
        raise UnknownErrorCode(code) from None


def raise_for(code: str, context: Mapping[str, object] | None = None) -> None:
    """Raise the ApexError for a Ch.7 code (never returns)."""
    raise ApexError(code, context)
