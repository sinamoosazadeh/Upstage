"""Telegram signaling + alert policy — Ch.21 (APEX_GEN5.md L17562–18220) and
Ch.23 "Monitoring and Alert Policy (Normative)" (L18290–18314).

Outbound plane only: the signaling tier table (L17995–18001), the Ch.23 alert
policy rows, de-duplication, the token bucket (20 tokens, 20/s refill, 1 per
message, queue when empty), the 3-attempt exponential backoff (1 s, 2 s, 4 s),
the idempotency key ``SHA256(signal_id + timestamp_UTC + chat_id)`` with a 24 h
TTL, MarkdownV2 escaping, the §12 failure-mode table (E-TELE-001..007), the
§11 message state machine, the §8 evidence-event emission formula and the
Agg-only in-memory chart renderer (Ch.1 L118–124, Ch.21 §7/§10).

Telegram is downstream: it never becomes market truth, portfolio truth or Risk
authority, and signaling failure NEVER blocks protective execution
(L17570–17578, L18007). The bot token comes from the environment ONLY
(§9.5-12/13) and never appears in a message, an exception string or the repo.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import (Any, Awaitable, Callable, Dict, FrozenSet, List, Mapping,
                    Optional, Sequence, Tuple)

from apex.bus import EventBus, Priority, make_event
from apex.config import Config
from apex.errors import ErrorCode, get_error_code
from apex.identity.hashes import sha256_hex
from apex.identity.uuid_v7 import uuid_v7

CONTRACT_VERSION = "4.0.0"

# ---------------------------------------------------------------------------
# Ch.21 §10 parameter table (L17846–17861) — frozen verbatim. No YAML home
# exists and CP-7's WRITE SET excludes params/*.yaml; asserted literal-by-
# literal in tests/unit/test_telegram_signaling.py (ISSUE-CP7-003).
# ---------------------------------------------------------------------------
RATE_LIMITING_BUCKET_SIZE = 20          # messages/second/chat (internal)
RATE_LIMITING_REFILL_RATE = 20.0        # tokens/second
PROVIDER_CEILING_PER_SECOND = 30        # Ch.21 §2 L17588 (never exceeded)
RETRY_TIMES = 3
RETRY_BACKOFF_SECONDS: Tuple[float, ...] = (1.0, 2.0, 4.0)
IDEMPOTENCY_KEY_TTL_SECONDS = 86400     # 24 h
IMAGE_CHART_WIDTH = 1200                # px
IMAGE_CHART_HEIGHT = 800                # px
IMAGE_CHART_FORMAT = "PNG"
IMAGE_CHART_QUALITY = 90
CAPTION_MAX_LENGTH = 1024
TEXT_MAX_LENGTH = 4096
INLINE_KEYBOARD_MAX_BUTTONS = 8
INLINE_KEYBOARD_MAX_ROWS = 4
CALLBACK_DATA_MAX_BYTES = 64            # Ch.21 §6 L17775
TELEGRAM_PARAMS: Dict[str, Any] = {
    "rate_limiting_bucket_size": RATE_LIMITING_BUCKET_SIZE,
    "rate_limiting_refill_rate": RATE_LIMITING_REFILL_RATE,
    "retry_times": RETRY_TIMES,
    "retry_backoff": list(RETRY_BACKOFF_SECONDS),
    "idempotency_key_ttl": IDEMPOTENCY_KEY_TTL_SECONDS,
    "image_chart_width": IMAGE_CHART_WIDTH,
    "image_chart_height": IMAGE_CHART_HEIGHT,
    "image_chart_format": IMAGE_CHART_FORMAT,
    "image_chart_quality": IMAGE_CHART_QUALITY,
    "caption_max_length": CAPTION_MAX_LENGTH,
    "text_max_length": TEXT_MAX_LENGTH,
    "inline_keyboard_max_buttons": INLINE_KEYBOARD_MAX_BUTTONS,
    "inline_keyboard_max_rows": INLINE_KEYBOARD_MAX_ROWS,
}

#: Ch.21 §7 L17833 — MarkdownV2 escapes exactly these characters.
MARKDOWNV2_ESCAPE_CHARS: Tuple[str, ...] = (
    "_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|",
    "{", "}", ".", "!")
#: Ch.21 §7 L17834 — HTML formatting supports exactly these tags.
HTML_ALLOWED_TAGS: Tuple[str, ...] = ("b", "i", "code", "pre", "a")

#: Ch.21 §11 message state machine (L17893–17906).
MESSAGE_STATES: Tuple[str, ...] = ("CANDIDATE", "CONFIRMED", "ACTIVE", "PRUNED",
                                   "INVALIDATED")
THETA_MAX_AGE_BARS = 100                # Ch.21 §11 PRUNED
TELEGRAM_VALIDITY_CANDLES: Tuple[int, int] = (5, 20)   # Ch.21 §8 L17888
TELEGRAM_QUALITY = "Q2"                 # Ch.21 §8 L17871
TELEGRAM_CONFIDENCE_FACTOR = 0.85       # 0.85 * Q_formula_valid
DECAY_LAMBDA = 0.02                     # Ch.21 §14: exp(-0.02 * age)

#: Ch.21 signaling tier table (L17995–18001).
SIGNAL_TIERS: Dict[int, Dict[str, Any]] = {
    Priority.P0: {"content": ("FAIL_CLOSED", "CIRCUIT_OPEN", "EXEC_RECOVERY",
                              "HOST_DOWN"),
                  "transport": "Telegram + watchdog", "bound": "never drop",
                  "droppable": False},
    Priority.P1: {"content": ("veto REJECT of ALLOW-proposed plan",
                              "margin warning"),
                  "transport": "Telegram",
                  "bound": "≤2 s declared UNVERIFIED", "droppable": False},
    Priority.P2: {"content": ("Setup CONFIRMED", "fills"),
                  "transport": "Telegram", "bound": "token bucket 20/s",
                  "droppable": False},
    Priority.P3: {"content": ("research", "charts"), "transport": "Telegram",
                  "bound": "droppable", "droppable": True},
}

#: Ch.23 Monitoring and Alert Policy (L18292–18302) — VERBATIM rows.
ALERT_POLICY: Tuple[Dict[str, Any], ...] = (
    {"metric": "feed_staleness", "threshold": "> 2 × freshness threshold",
     "alert": "FEED_DEGRADED", "channel": "Telegram",
     "escalation": "15 min → L1", "priority": Priority.P1,
     "dedup_exempt": False},
    {"metric": "execution_recovery_required", "threshold": "any occurrence",
     "alert": "EXEC_RECOVERY", "channel": "Telegram immediate",
     "escalation": "immediate OWNER", "priority": Priority.P0,
     "dedup_exempt": True},
    {"metric": "daily_realized_loss", "threshold": "per veto 10 table",
     "alert": "CIRCUIT_OPEN", "channel": "Telegram immediate",
     "escalation": "immediate OWNER", "priority": Priority.P0,
     "dedup_exempt": True},
    {"metric": "watchdog_heartbeat_miss", "threshold": "3 consecutive",
     "alert": "HOST_DOWN", "channel": "independent channel",
     "escalation": "watchdog acts per the Deployment safeguards",
     "priority": Priority.P0, "dedup_exempt": True},
    {"metric": "device_storage", "threshold": "> 80% capacity",
     "alert": "STORAGE", "channel": "Telegram", "escalation": "24 h",
     "priority": Priority.P1, "dedup_exempt": False},
)
ALERT_NAMES: FrozenSet[str] = frozenset(r["alert"] for r in ALERT_POLICY)

#: Ch.23 L18304–18306: identical alerts within a governed window (default
#: 30 min) are suppressed EXCEPT EXEC_RECOVERY and CIRCUIT_OPEN.
ALERT_DEDUP_WINDOW_SECONDS = 1800
ALERT_DEDUP_EXEMPT: FrozenSet[str] = frozenset({"EXEC_RECOVERY", "CIRCUIT_OPEN"})

#: Ch.23 L18307–18310 log retention (on-device, encrypted).
LOG_RETENTION_DAYS = 90

#: AI.12 Phase 8 acceptance: P0 < 2 s, P1 < 5 s (declared targets, UNVERIFIED).
DECLARED_DELIVERY_TARGETS_SECONDS: Dict[int, float] = {Priority.P0: 2.0,
                                                      Priority.P1: 5.0}

STORAGE_ALERT_FRACTION = 0.80            # Ch.23 alert policy row 5
HEARTBEAT_INTERVAL_SECONDS = 60          # Ch.23 safeguard 1 / Ch.17 L16998
HEARTBEAT_MISS_LIMIT = 3                 # Ch.23 safeguard 1 / Ch.17 L16999


class SignalingError(RuntimeError):
    """Fail-closed signaling violation with a deterministic reason code."""

    def __init__(self, reason: str, detail: str = "",
                 error_code: Optional[str] = None) -> None:
        self.reason = reason
        self.detail = detail
        self.error_code = error_code
        super().__init__(f"{reason}" + (f": {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Formatting (Ch.21 §7)
# ---------------------------------------------------------------------------

_ESCAPE_RE = re.compile("(" + "|".join(re.escape(c)
                                       for c in MARKDOWNV2_ESCAPE_CHARS) + ")")


def escape_markdown_v2(text: str) -> str:
    """Escape exactly the Ch.21 §7 character set ``_ * [ ] ( ) ~ ` > # + - = |
    { } . !`` (numbers with commas must be escaped too — L18035)."""
    return _ESCAPE_RE.sub(r"\\\1", str(text))


def format_markdown_v2(text: str) -> Dict[str, Any]:
    escaped = escape_markdown_v2(text)
    truncated = len(escaped) > TEXT_MAX_LENGTH
    return {"parse_mode": "MarkdownV2",
            "text": escaped[:TEXT_MAX_LENGTH] if truncated else escaped,
            "truncated": truncated,
            "error_code": get_error_code("E-TELE-003").code if truncated else None,
            "quality": "Q2_DEGRADED" if truncated else "Q2",
            "escaped_chars": MARKDOWNV2_ESCAPE_CHARS}


def format_html(text: str) -> Dict[str, Any]:
    """HTML formatting supports ``<b> <i> <code> <pre> <a>`` only (Ch.21 §7)."""
    stripped = re.sub(r"</?(?!/?(?:%s)\b)[a-zA-Z0-9]+[^>]*>" %
                      "|".join(HTML_ALLOWED_TAGS), "", str(text))
    truncated = len(stripped) > TEXT_MAX_LENGTH
    return {"parse_mode": "HTML",
            "text": stripped[:TEXT_MAX_LENGTH] if truncated else stripped,
            "truncated": truncated, "allowed_tags": HTML_ALLOWED_TAGS,
            "error_code": get_error_code("E-TELE-003").code if truncated else None}


def format_caption(caption: Optional[str]) -> Dict[str, Any]:
    if caption is None:
        return {"caption": None, "truncated": False, "error_code": None,
                "quality": "Q2"}
    text = str(caption)
    truncated = len(text) > CAPTION_MAX_LENGTH
    return {"caption": text[:CAPTION_MAX_LENGTH] if truncated else text,
            "truncated": truncated,
            "error_code": get_error_code("E-TELE-004").code if truncated else None,
            "quality": "Q2_DEGRADED" if truncated else "Q2",
            "max_length": CAPTION_MAX_LENGTH}


def comma_format(value: Any) -> str:
    """Ch.21 §6 L17776: numeric values are comma-formatted for display (then
    MarkdownV2-escaped, L18035)."""
    dec = Decimal(str(value))
    if dec == dec.to_integral_value():
        return f"{int(dec):,}"
    sign, digits, exponent = dec.as_tuple()
    frac = -exponent if exponent < 0 else 0
    return f"{dec:,.{frac}f}"


def build_inline_keyboard(buttons: Sequence[Sequence[Mapping[str, Any]]]
                          ) -> Dict[str, Any]:
    """Ch.21 §5.1 layout rule: max 2 domain buttons per row; §10: max 8
    buttons and 4 rows; §6: callback data ≤ 64 bytes."""
    rows: List[List[Dict[str, str]]] = []
    total = 0
    truncated_buttons = False
    truncated_rows = False
    oversized_callbacks: List[str] = []
    for row in buttons:
        if len(rows) >= INLINE_KEYBOARD_MAX_ROWS:
            truncated_rows = True
            break
        rendered: List[Dict[str, str]] = []
        for button in row:
            if total >= INLINE_KEYBOARD_MAX_BUTTONS:
                truncated_buttons = True
                break
            data = str(button.get("callback_data", button.get("text", "")))
            if len(data.encode("utf-8")) > CALLBACK_DATA_MAX_BYTES:
                oversized_callbacks.append(data)
                data = data[:CALLBACK_DATA_MAX_BYTES].encode("utf-8")[:CALLBACK_DATA_MAX_BYTES].decode(
                    "utf-8", "ignore")
            rendered.append({"text": str(button.get("text", "")),
                             "callback_data": data})
            total += 1
        if rendered:
            rows.append(rendered)
    degraded = truncated_buttons or truncated_rows or bool(oversized_callbacks)
    codes = []
    if truncated_buttons or truncated_rows:
        codes.append(get_error_code("E-TELE-005").code)
    return {"inline_keyboard": rows, "button_count": total, "row_count": len(rows),
            "truncated_buttons": truncated_buttons, "truncated_rows": truncated_rows,
            "oversized_callback_data": tuple(oversized_callbacks),
            "quality": "Q2_DEGRADED" if degraded else "Q2",
            "error_code": codes[0] if codes else None,
            "max_buttons": INLINE_KEYBOARD_MAX_BUTTONS,
            "max_rows": INLINE_KEYBOARD_MAX_ROWS,
            "callback_data_max_bytes": CALLBACK_DATA_MAX_BYTES}


def idempotency_key(signal_id: str, timestamp_utc: str, chat_id: Any) -> str:
    """Ch.21 §2/§7 (L17590, L17831): ``SHA256(signal_id + timestamp_UTC +
    chat_id)`` → a 64-character hex digest; TTL 24 h (L18058)."""
    joined = f"{signal_id}{timestamp_utc}{chat_id}"
    return sha256_hex(joined)


# ---------------------------------------------------------------------------
# Chart rendering — Agg only, in-memory only (Ch.1 L118–124; Ch.21 §7/§10)
# ---------------------------------------------------------------------------

def _matplotlib_agg() -> Any:
    """``matplotlib.use('Agg')`` BEFORE any pyplot import; headless failover to
    Agg rather than an error (Ch.1 L118–124)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


#: Ch.21 §7 L17836–17846 chart overlay layers (the frozen list).
CHART_LAYERS: Tuple[str, ...] = (
    "Swing High/Low", "BOS", "CHoCH", "FVG", "OrderBlock", "Equal Highs/Lows",
    "Sweep", "Liquidity Pool", "Stop Hunt", "Volume Spike", "VolumeZ",
    "VolRatio", "VWAP Dev", "OBV", "CVD", "Delta", "Footprint",
    "Volume Profile", "Market Profile", "Taker Buy/Sell", "Liquidation", "ATR",
    "Parkinson", "Garman-Klass", "Rogers-Satchell", "GARCH",
    "Normalized Range", "RangeZ", "Slope", "Hurst", "Squeeze",
    "Volatility Regime", "Trend", "Momentum Divergence", "Regime",
    "TemporalWindow", "Killzone", "News Event")


def render_chart(*, ohlcv: Sequence[Sequence[float]],
                 layers: Optional[Sequence[str]] = None,
                 quality: str = "Q2", snapshot_id: str = "",
                 lineage: str = "", title: str = "APEX") -> Dict[str, Any]:
    """In-memory PNG chart, 1200×800, quality 90 — NEVER filesystem-stored
    (Ch.1 L120–124; Ch.21 §10). ``market_profile`` is always UNAVAILABLE
    (§9.5-9 Wave-Out) and is reported as such, never drawn from invented data.

    The Ch.21 "chart rendering" snippet (L18062–18082) shows ``dpi=150`` with a
    ``quality=90`` savefig kwarg; the §10 frozen parameter table (1200×800 PNG,
    quality 90) is normative, so the figure is rendered at exactly 1200×800 px
    (figsize 12×8 at dpi 100) and the quality parameter is carried in the
    message metadata — PNG is lossless and has no encoder quality knob
    (ISSUE-CP7-006).
    """
    requested = tuple(layers or CHART_LAYERS)
    unknown = [l for l in requested if l not in CHART_LAYERS]
    if unknown:
        raise SignalingError("CHART_LAYER_UNKNOWN", ", ".join(unknown))
    unavailable = [l for l in requested if l == "Market Profile"]
    plt = _matplotlib_agg()
    fig, ax = plt.subplots(figsize=(IMAGE_CHART_WIDTH / 100.0,
                                    IMAGE_CHART_HEIGHT / 100.0), dpi=100)
    closes = [float(row[3]) for row in ohlcv] if ohlcv else []
    if closes:
        ax.plot(range(len(closes)), closes, linewidth=1.0)
    ax.set_title(f"{title} · {quality}"[:120], fontsize=8)
    ax.tick_params(labelsize=6)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)     # in-memory ONLY (no path)
    plt.close(fig)
    buf.seek(0)
    png = buf.getvalue()
    width, height = _png_size(png)
    return {"image": png, "format": IMAGE_CHART_FORMAT, "width": width,
            "height": height, "declared_width": IMAGE_CHART_WIDTH,
            "declared_height": IMAGE_CHART_HEIGHT, "quality": IMAGE_CHART_QUALITY,
            "layers": requested, "layers_unavailable": tuple(unavailable),
            "resolution_class": quality, "snapshot_id": snapshot_id,
            "lineage": lineage, "backend": "Agg",
            "filesystem_stored": False,
            "note": "market_profile is always UNAVAILABLE (§9.5-9)"
                    if unavailable else None}


def _png_size(png: bytes) -> Tuple[int, int]:
    """Read the IHDR width/height (no third-party image dependency)."""
    if len(png) < 24 or png[:8] != b"\x89PNG\r\n\x1a\n":
        return (0, 0)
    width = int.from_bytes(png[16:20], "big")
    height = int.from_bytes(png[20:24], "big")
    return (width, height)


# ---------------------------------------------------------------------------
# Token bucket + idempotency registry (Ch.21 §7; AI.8 L18772)
# ---------------------------------------------------------------------------

class MessageTokenBucket:
    """Internal limiter = 20 messages/second/chat, below the provider ceiling
    of 30 (Ch.21 §2 L17588). 1 token per message; if the bucket is empty the
    message is QUEUED (never dropped). No burst is permitted by the
    application limiter (AI.8 L18774)."""

    def __init__(self, *, capacity: int = RATE_LIMITING_BUCKET_SIZE,
                 refill_per_second: float = RATE_LIMITING_REFILL_RATE,
                 clock: Optional[Callable[[], float]] = None) -> None:
        if capacity > PROVIDER_CEILING_PER_SECOND:
            raise SignalingError("INTERNAL_LIMITER_ABOVE_PROVIDER_CEILING",
                                 f"{capacity} > {PROVIDER_CEILING_PER_SECOND}")
        self.capacity = float(capacity)
        self.refill_per_second = float(refill_per_second)
        self._clock = clock if clock is not None else _monotonic
        self._tokens = float(capacity)
        self._last = float(self._clock())
        self._queued = 0
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = float(self._clock())
        self._tokens = min(self.capacity,
                           self._tokens + max(0.0, now - self._last)
                           * self.refill_per_second)
        self._last = now

    def available(self) -> float:
        self._refill()
        return self._tokens

    def bucket_empty(self) -> bool:
        return self.available() < 1.0

    async def acquire(self) -> Dict[str, Any]:
        async with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return {"acquired": True, "queued": False, "tokens": self._tokens}
            self._queued += 1
            wait = (1.0 - self._tokens) / self.refill_per_second
            try:
                await asyncio.sleep(wait)
                self._refill()
                self._tokens -= 1.0
                return {"acquired": True, "queued": True,
                        "waited_seconds": wait, "tokens": self._tokens,
                        "error_code": get_error_code("E-TELE-006").code}
            finally:
                self._queued -= 1

    @property
    def queued(self) -> int:
        return self._queued


class IdempotencyRegistry:
    """``SHA256(signal_id + timestamp_UTC + chat_id)`` with a 24 h TTL; if the
    key exists the message is SKIPPED (E-TELE-007, Ch.21 §7/§12)."""

    def __init__(self, *, ttl_seconds: int = IDEMPOTENCY_KEY_TTL_SECONDS,
                 clock: Optional[Callable[[], float]] = None) -> None:
        self.ttl_seconds = int(ttl_seconds)
        self._clock = clock if clock is not None else _monotonic
        self._seen: Dict[str, float] = {}

    def exists(self, key: str) -> bool:
        self._expire()
        return key in self._seen

    def store(self, key: str) -> None:
        self._seen[key] = float(self._clock())

    def _expire(self) -> None:
        now = float(self._clock())
        for stale in [k for k, t in self._seen.items()
                      if now - t > self.ttl_seconds]:
            del self._seen[stale]

    def __len__(self) -> int:
        self._expire()
        return len(self._seen)


# ---------------------------------------------------------------------------
# Messages and results
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SignalMessage:
    """One outbound Telegram message (Ch.21 §8 TELEGRAM_MESSAGE event)."""
    signal_id: str
    chat_id: str
    text: str
    priority: int = Priority.P2
    caption: Optional[str] = None
    image: Optional[bytes] = None
    inline_keyboard: Tuple[Tuple[Dict[str, str], ...], ...] = ()
    timestamp_utc: str = ""
    snapshot_id: str = ""
    quality: str = TELEGRAM_QUALITY
    validity_candles: Tuple[int, int] = TELEGRAM_VALIDITY_CANDLES
    q_formula_valid: float = 1.0
    q_window_min: float = 1.0
    setup_state: str = "CONFIRMED"
    setup_blocked: bool = False
    alert: Optional[str] = None
    metric: Optional[str] = None
    threshold: Optional[str] = None
    observed: Optional[str] = None
    lineage: str = ""

    @property
    def idempotency_key(self) -> str:
        return idempotency_key(self.signal_id, self.timestamp_utc, self.chat_id)

    @property
    def confidence(self) -> float:
        """Ch.21 §8 L17871: confidence = 0.85 * Q_formula_valid."""
        return TELEGRAM_CONFIDENCE_FACTOR * float(self.q_formula_valid)


@dataclass(frozen=True)
class SendAttempt:
    attempt_no: int
    timestamp: str
    status: str            # SENT | FAILED | RETRY | SKIPPED | QUEUED
    detail: str
    delay_seconds: Optional[float] = None


@dataclass(frozen=True)
class SendResult:
    signal_id: str
    chat_id: str
    sent: bool
    state: str             # ACTIVE | INVALIDATED | PRUNED (Ch.21 §11)
    reason: Optional[str]
    error_code: Optional[str]
    message_id: Optional[str]
    idempotency_key: str
    priority: int
    quality: str
    attempts: Tuple[SendAttempt, ...]
    queued: bool
    truncated: bool
    delivery_seconds: Optional[float] = None
    declared_target_seconds: Optional[float] = None
    audit: Mapping[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Transport seam: production = aiogram; tests inject a double (G9)
# ---------------------------------------------------------------------------

class TelegramTransport:
    """Transport interface (``send_message`` / ``send_photo``)."""

    async def send_message(self, chat_id: str, text: str,
                           parse_mode: str,
                           reply_markup: Optional[Mapping[str, Any]] = None
                           ) -> Dict[str, Any]:     # pragma: no cover - interface
        raise NotImplementedError

    async def send_photo(self, chat_id: str, photo: bytes,
                         caption: Optional[str],
                         parse_mode: str,
                         reply_markup: Optional[Mapping[str, Any]] = None
                         ) -> Dict[str, Any]:       # pragma: no cover - interface
        raise NotImplementedError


class AiogramTransport(TelegramTransport):
    """The production transport: aiogram 3.7.0 (a frozen SBOM pin).

    The bot token is read from ``TELEGRAM_BOT_TOKEN`` ONLY (E-TELE-001:
    "Secrets env var only never .env Memory-only") and is never logged, never
    put in a message and never persisted.
    """

    def __init__(self, bot: Any) -> None:
        self._bot = bot

    @classmethod
    def from_env(cls, config: Optional[Config] = None) -> "AiogramTransport":
        cfg = config or Config()
        token = cfg.telegram_bot_token
        if not token:
            raise SignalingError(get_error_code("E-TELE-001").code,
                                 "TELEGRAM_BOT_TOKEN is not set (env only)",
                                 error_code=get_error_code("E-TELE-001").code)
        from aiogram import Bot
        return cls(Bot(token=token))

    async def send_message(self, chat_id: str, text: str, parse_mode: str,
                           reply_markup: Optional[Mapping[str, Any]] = None
                           ) -> Dict[str, Any]:
        message = await self._bot.send_message(
            chat_id=chat_id, text=text, parse_mode=parse_mode,
            reply_markup=_aiogram_keyboard(reply_markup))
        return {"message_id": str(getattr(message, "message_id", "")),
                "chat_id": chat_id}

    async def send_photo(self, chat_id: str, photo: bytes,
                         caption: Optional[str], parse_mode: str,
                         reply_markup: Optional[Mapping[str, Any]] = None
                         ) -> Dict[str, Any]:
        message = await self._bot.send_photo(
            chat_id=chat_id, photo=photo, caption=caption,
            parse_mode=parse_mode,
            reply_markup=_aiogram_keyboard(reply_markup))
        return {"message_id": str(getattr(message, "message_id", "")),
                "chat_id": chat_id}


def _aiogram_keyboard(reply_markup: Optional[Mapping[str, Any]]) -> Any:
    if not reply_markup:
        return None
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    rows = [[InlineKeyboardButton(text=b["text"], callback_data=b["callback_data"])
             for b in row] for row in reply_markup.get("inline_keyboard", [])]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# The signaling plane
# ---------------------------------------------------------------------------

class SignalingPlane:
    """Outbound signaling + Ch.23 alert policy.

    Failure here NEVER blocks protective execution (Ch.21 L18007): a transport
    fault is recorded, alerted and the outbox keeps the item — the execution
    path is never awaited on a delivery.
    """

    def __init__(self, *, transport: Optional[TelegramTransport] = None,
                 config: Optional[Config] = None,
                 clock: Optional[Callable[[], float]] = None,
                 utc_now: Optional[Callable[[], str]] = None,
                 bus: Optional[EventBus] = None,
                 ledger: Any = None,
                 owner_chat_id: Optional[str] = None,
                 watchdog_chat_id: Optional[str] = None,
                 freshness_thresholds: Optional[Mapping[str, float]] = None) -> None:
        self._config = config or Config()
        self._transport = transport
        self._clock = clock if clock is not None else _monotonic
        self._utc_now = utc_now if utc_now is not None else _utc_now_ms
        self.bus = bus
        self.ledger = ledger
        self.owner_chat_id = owner_chat_id or self._config.telegram_owner_chat_id
        self.watchdog_chat_id = watchdog_chat_id or \
            self._config.telegram_watchdog_chat_id
        self.buckets: Dict[str, MessageTokenBucket] = {}
        self.idempotency = IdempotencyRegistry(clock=self._clock)
        self.outbox: List[Dict[str, Any]] = []
        self.alert_audit: List[Dict[str, Any]] = []
        self._last_alert: Dict[str, float] = {}
        self._sent = 0
        self._skipped = 0
        self._failed = 0
        self._freshness = dict(freshness_thresholds or {})

    # -- transport ----------------------------------------------------------
    def transport(self) -> TelegramTransport:
        if self._transport is None:
            # Bot token from env ONLY; a missing token is E-TELE-001 (QX
            # INVALID), never a hardcoded or invented credential.
            self._transport = AiogramTransport.from_env(self._config)
        return self._transport

    def bucket_for(self, chat_id: str) -> MessageTokenBucket:
        if chat_id not in self.buckets:
            self.buckets[chat_id] = MessageTokenBucket(clock=self._clock)
        return self.buckets[chat_id]

    # -- Ch.21 §8 emission formula -----------------------------------------
    def calc_telegram_message(self, message: SignalMessage) -> Dict[str, Any]:
        """Ch.21 §8 (L17872–17891): emit ONLY if Setup is CONFIRMED,
        ``Q_window.min >= 0.5``, Setup is not BLOCKed, a rate-limiting token is
        available and the idempotency key does not already exist."""
        key = message.idempotency_key
        if message.setup_state != "CONFIRMED":
            return {"emit": False, "state": "INVALIDATED",
                    "result": "NO_TELEGRAM_MESSAGE",
                    "reason": f"setup_state={message.setup_state}",
                    "error_code": None, "idempotency_key": key}
        if message.q_window_min < 0.5:
            return {"emit": False, "state": "INVALIDATED", "result": "INVALID",
                    "reason": f"Q_window.min {message.q_window_min} < 0.5",
                    "error_code": None, "idempotency_key": key,
                    "note": "Setup BLOCK"}
        if message.setup_blocked:
            return {"emit": False, "state": "INVALIDATED", "result": "INVALID",
                    "reason": "setup BLOCKed", "error_code": None,
                    "idempotency_key": key}
        if self.idempotency.exists(key):
            return {"emit": False, "state": "INVALIDATED", "result": "SKIPPED",
                    "reason": "idempotency key exists",
                    "error_code": get_error_code("E-TELE-007").code,
                    "idempotency_key": key}
        bucket = self.bucket_for(message.chat_id)
        if bucket.bucket_empty():
            return {"emit": True, "state": "CONFIRMED", "result": "QUEUED",
                    "reason": "rate-limit bucket empty → queue_message()",
                    "error_code": get_error_code("E-TELE-006").code,
                    "idempotency_key": key}
        return {"emit": True, "state": "CONFIRMED",
                "result": "TelegramMessage", "reason": None, "error_code": None,
                "idempotency_key": key,
                "confidence": message.confidence,
                "validity_candles": message.validity_candles}

    # -- sending ------------------------------------------------------------
    async def send(self, message: SignalMessage, *,
                   force: bool = False) -> SendResult:
        """Send one message through the full Ch.21 pipeline: emission gate →
        idempotency → token bucket → formatting/truncation → retry (3 attempts,
        1/2/4 s) → idempotency-key store → durable outbox record."""
        started = self._clock()
        ts = message.timestamp_utc or self._utc_now()
        msg = SignalMessage(**{**{f: getattr(message, f)
                                  for f in message.__dataclass_fields__},
                               "timestamp_utc": ts})
        key = msg.idempotency_key
        gate = self.calc_telegram_message(msg)
        attempts: List[SendAttempt] = []
        if not gate["emit"] and not force:
            self._skipped += 1
            self._record_outbox(msg, "SKIPPED", gate["reason"], key)
            return SendResult(signal_id=msg.signal_id, chat_id=msg.chat_id,
                              sent=False, state=gate["state"],
                              reason=gate["reason"],
                              error_code=gate["error_code"], message_id=None,
                              idempotency_key=key, priority=msg.priority,
                              quality=msg.quality, attempts=tuple(attempts),
                              queued=False, truncated=False,
                              audit={"gate": gate})
        if not self._validate_identity(msg):
            self._failed += 1
            return SendResult(signal_id=msg.signal_id, chat_id=msg.chat_id,
                              sent=False, state="INVALIDATED",
                              reason="chat id invalid",
                              error_code=get_error_code("E-TELE-002").code,
                              message_id=None, idempotency_key=key,
                              priority=msg.priority, quality="QX",
                              attempts=tuple(attempts), queued=False,
                              truncated=False, audit={"gate": gate})
        formatted = format_markdown_v2(msg.text)
        caption = format_caption(msg.caption)
        keyboard = build_inline_keyboard(
            [tuple(r) for r in msg.inline_keyboard]) if msg.inline_keyboard else None
        quality = msg.quality
        error_code = gate.get("error_code")
        if formatted["truncated"]:
            quality, error_code = "Q2_DEGRADED", formatted["error_code"]
        if caption["truncated"]:
            quality = "Q2_DEGRADED"
            error_code = error_code or caption["error_code"]
        if keyboard and keyboard["error_code"]:
            quality = "Q2_DEGRADED"
            error_code = error_code or keyboard["error_code"]
        bucket = self.bucket_for(msg.chat_id)
        acquired = await bucket.acquire()
        if acquired.get("queued"):
            attempts.append(SendAttempt(0, self._utc_now(), "QUEUED",
                                        "rate-limit bucket empty → queued",
                                        acquired.get("waited_seconds")))
        transport = self.transport()
        sent = False
        message_id: Optional[str] = None
        detail = ""
        for attempt in range(1, RETRY_TIMES + 1):
            try:
                if msg.image:
                    response = await transport.send_photo(
                        chat_id=msg.chat_id, photo=msg.image,
                        caption=caption["caption"],
                        parse_mode=formatted["parse_mode"],
                        reply_markup=keyboard)
                else:
                    response = await transport.send_message(
                        chat_id=msg.chat_id, text=formatted["text"],
                        parse_mode=formatted["parse_mode"],
                        reply_markup=keyboard)
                message_id = str(response.get("message_id") or uuid_v7())
                sent = True
                attempts.append(SendAttempt(attempt, self._utc_now(), "SENT",
                                            f"message_id={message_id}"))
                break
            except Exception as exc:
                detail = f"{type(exc).__name__}: {exc}"
                if attempt < RETRY_TIMES:
                    delay = RETRY_BACKOFF_SECONDS[attempt - 1]
                    attempts.append(SendAttempt(attempt, self._utc_now(), "RETRY",
                                                detail, delay))
                    await asyncio.sleep(delay)
                else:
                    attempts.append(SendAttempt(attempt, self._utc_now(), "FAILED",
                                                detail))
        if sent:
            self.idempotency.store(key)
            self._sent += 1
            state = "ACTIVE"
            reason = None
        else:
            self._failed += 1
            state = "INVALIDATED"
            reason = f"network error after {RETRY_TIMES} attempts: {detail}"
            error_code = error_code or get_error_code("E-TELE-006").code
        elapsed = self._clock() - started
        self._record_outbox(msg, "SENT" if sent else "FAILED", reason, key,
                            message_id=message_id, attempts=attempts)
        if self.bus is not None:
            await self.bus.publish(make_event(
                int(Priority.P0 if sent and msg.priority == Priority.P0
                    else Priority.P3), "telegram.message",
                {"signal_id": msg.signal_id, "chat_id": msg.chat_id,
                 "sent": sent, "state": state, "priority": int(msg.priority),
                 "message_id": message_id, "delivery_seconds": elapsed}))
        return SendResult(signal_id=msg.signal_id, chat_id=msg.chat_id, sent=sent,
                          state=state, reason=reason, error_code=error_code,
                          message_id=message_id or str(uuid_v7()) if sent else None,
                          idempotency_key=key, priority=int(msg.priority),
                          quality=quality, attempts=tuple(attempts),
                          queued=bool(acquired.get("queued")),
                          truncated=bool(formatted["truncated"]
                                         or caption["truncated"]),
                          delivery_seconds=elapsed,
                          declared_target_seconds=DECLARED_DELIVERY_TARGETS_SECONDS.get(
                              int(msg.priority)),
                          audit={"gate": gate, "keyboard": keyboard,
                                 "caption": caption})

    def _validate_identity(self, msg: SignalMessage) -> bool:
        """Ch.21 §12: Bot Token invalid / Chat ID invalid / Message ID invalid
        ⇒ QX INVALID."""
        chat = str(msg.chat_id or "")
        if not chat or not re.fullmatch(r"-?\d+", chat):
            return False
        return True

    def _record_outbox(self, msg: SignalMessage, status: str,
                       reason: Optional[str], key: str, *,
                       message_id: Optional[str] = None,
                       attempts: Optional[Sequence[SendAttempt]] = None) -> None:
        """AI.12 Phase 8: durable outbox, no silent drop. P0/P1 items are never
        evicted (AI.8 L18801–18805)."""
        self.outbox.append({
            "signal_id": msg.signal_id, "chat_id": msg.chat_id,
            "priority": int(msg.priority), "status": status, "reason": reason,
            "idempotency_key": key, "message_id": message_id,
            "timestamp_utc": msg.timestamp_utc, "alert": msg.alert,
            "droppable": bool(SIGNAL_TIERS.get(int(msg.priority), {}).get(
                "droppable", True)),
            "attempts": len(attempts or ())})

    # -- Ch.23 alert policy -------------------------------------------------
    def alert_row(self, alert: str) -> Dict[str, Any]:
        for row in ALERT_POLICY:
            if row["alert"] == alert:
                return dict(row)
        raise SignalingError("ALERT_NOT_IN_POLICY", str(alert))

    def dedup_verdict(self, alert: str, fingerprint: str, *,
                      now: Optional[float] = None) -> Dict[str, Any]:
        """Ch.23 L18304–18306: identical alerts within the governed 30-minute
        window are suppressed EXCEPT EXEC_RECOVERY and CIRCUIT_OPEN."""
        t = self._clock() if now is None else float(now)
        exempt = alert in ALERT_DEDUP_EXEMPT
        last = self._last_alert.get(fingerprint)
        suppressed = (not exempt and last is not None
                      and (t - last) <= ALERT_DEDUP_WINDOW_SECONDS)
        return {"alert": alert, "fingerprint": fingerprint, "suppressed": suppressed,
                "exempt": exempt, "window_seconds": ALERT_DEDUP_WINDOW_SECONDS,
                "last_seen": last,
                "rule": "Ch.23 L18304–18306 — dedup except EXEC_RECOVERY and "
                        "CIRCUIT_OPEN"}

    async def emit_alert(self, *, alert: str, metric: str, threshold: str,
                         observed: Any, snapshot_id: str = "",
                         chat_id: Optional[str] = None,
                         signal_id: Optional[str] = None,
                         timestamp_utc: Optional[str] = None,
                         escalation_note: str = "") -> Dict[str, Any]:
        """Emit one Ch.23 policy alert. Every alert carries timestamp, metric,
        threshold, observed value and snapshot id, and is appended to the
        immutable audit trail (Ch.23 L18306–18309)."""
        row = self.alert_row(alert)
        ts = timestamp_utc or self._utc_now()
        target_chat = str(chat_id or self.owner_chat_id or "")
        fingerprint = sha256_hex(f"{alert}|{metric}|{observed}|{target_chat}")
        dedup = self.dedup_verdict(alert, fingerprint)
        record = {"alert": alert, "metric": metric, "threshold": threshold,
                  "observed": str(observed), "snapshot_id": snapshot_id,
                  "timestamp_utc": ts, "chat_id": target_chat,
                  "channel": row["channel"], "escalation": row["escalation"],
                  "priority": int(row["priority"]),
                  "suppressed": dedup["suppressed"],
                  "escalation_note": escalation_note,
                  "independent_channel": alert == "HOST_DOWN",
                  "watchdog_chat_id": self.watchdog_chat_id
                  if alert == "HOST_DOWN" else None}
        self._last_alert[fingerprint] = self._clock()
        self.alert_audit.append(record)
        if self.ledger is not None:
            await self.ledger.append(event_type="ALERT", actor="TELEGRAM_SIGNALING",
                                     result=alert, **{
                                         "metric": metric, "threshold": threshold,
                                         "observed": str(observed),
                                         "snapshot_id": snapshot_id,
                                         "alert": record})
        if dedup["suppressed"]:
            return {"emitted": False, "reason": "DEDUP_SUPPRESSED", **record}
        message = SignalMessage(
            signal_id=signal_id or f"{alert}_{metric}_{ts}",
            chat_id=target_chat, priority=int(row["priority"]),
            text=(f"{alert} — {metric} {observed} (threshold {threshold})"
                  + (f" · {escalation_note}" if escalation_note else "")),
            caption=None, timestamp_utc=ts, snapshot_id=snapshot_id,
            alert=alert, metric=metric, threshold=threshold,
            observed=str(observed), setup_state="CONFIRMED", q_window_min=1.0,
            lineage=f"alert:{alert}")
        result = await self.send(message, force=True)
        return {"emitted": result.sent, "reason": result.reason,
                "message_id": result.message_id, "state": result.state,
                "delivery_seconds": result.delivery_seconds,
                "declared_target_seconds": result.declared_target_seconds,
                **record}

    # -- policy triggers ----------------------------------------------------
    async def check_feed_staleness(self, *, symbol: str, timeframe: str,
                                   age_seconds: float, snapshot_id: str = ""
                                   ) -> Dict[str, Any]:
        """Ch.23 row 1: feed staleness > 2 × freshness threshold ⇒
        FEED_DEGRADED (Telegram; 15 min → L1)."""
        threshold = self._freshness.get(timeframe)
        if threshold is None:
            from apex.config import load_params
            threshold = float(load_params()["quality_weights"]
                              ["freshness_threshold_seconds"][timeframe])
        stale = float(age_seconds) > 2.0 * float(threshold)
        if not stale:
            return {"alert": None, "stale": False, "age_seconds": age_seconds,
                    "threshold_seconds": threshold}
        emitted = await self.emit_alert(
            alert="FEED_DEGRADED", metric=f"feed_staleness:{symbol}:{timeframe}",
            threshold=f"> 2 × {threshold}s", observed=age_seconds,
            snapshot_id=snapshot_id, escalation_note="15 min → Emergency L1")
        return {"alert": "FEED_DEGRADED", "stale": True, **emitted}

    async def check_heartbeat(self, *, missed: int, snapshot_id: str = ""
                              ) -> Dict[str, Any]:
        """Ch.23 row 4 + safeguard 1: 3 consecutive missed heartbeats ⇒
        HOST_DOWN on the independent channel (the send-only Gmail module lives
        ONLY in the watchdog process — CP-8's ``apex/ops/watchdog.py``; this
        plane routes the alert and never holds that credential)."""
        if int(missed) < HEARTBEAT_MISS_LIMIT:
            return {"alert": None, "missed": missed,
                    "limit": HEARTBEAT_MISS_LIMIT}
        emitted = await self.emit_alert(
            alert="HOST_DOWN", metric="watchdog_heartbeat_miss",
            threshold=f"{HEARTBEAT_MISS_LIMIT} consecutive", observed=missed,
            snapshot_id=snapshot_id, chat_id=self.watchdog_chat_id or None,
            escalation_note="watchdog acts per the Deployment safeguards")
        return {"alert": "HOST_DOWN", **emitted}

    async def check_storage(self, *, used_fraction: float, snapshot_id: str = ""
                            ) -> Dict[str, Any]:
        """Ch.23 row 5: device storage > 80% capacity ⇒ STORAGE (24 h)."""
        if float(used_fraction) <= STORAGE_ALERT_FRACTION:
            return {"alert": None, "used_fraction": used_fraction,
                    "threshold": STORAGE_ALERT_FRACTION}
        emitted = await self.emit_alert(
            alert="STORAGE", metric="device_storage",
            threshold=f"> {int(STORAGE_ALERT_FRACTION * 100)}% capacity",
            observed=used_fraction, snapshot_id=snapshot_id,
            escalation_note="24 h")
        return {"alert": "STORAGE", **emitted}

    def veto_alert_message(self, *, fired_numbers: Sequence[int],
                           proposed_decision: str, snapshot_id: str = "",
                           margin_health_fraction: Optional[float] = None
                           ) -> Optional[SignalMessage]:
        """Ch.21 tier P1: "veto REJECT of ALLOW-proposed plan, margin warning".

        Per HANDOFF_CP6 §INTERFACES 3 + ISSUE-CP6-004, alert rows key off
        ``fired_numbers`` — never off an absent Ch.7 error code.
        """
        fired = [int(n) for n in fired_numbers]
        if proposed_decision == "ALLOW" and not fired:
            if margin_health_fraction is not None and \
                    float(margin_health_fraction) <= 0.60:
                return SignalMessage(
                    signal_id=f"margin_warning_{snapshot_id}",
                    chat_id=str(self.owner_chat_id or ""), priority=Priority.P1,
                    text=f"margin warning — health {margin_health_fraction}",
                    snapshot_id=snapshot_id, alert=None, metric="margin_health",
                    threshold="60% of maintenance distance",
                    observed=str(margin_health_fraction), lineage="risk:veto")
            return None
        if not fired:
            return None
        return SignalMessage(
            signal_id=f"veto_reject_{sha256_hex(str(tuple(fired)))[:12]}",
            chat_id=str(self.owner_chat_id or ""), priority=Priority.P1,
            text=f"veto REJECT of ALLOW-proposed plan — vetoes {fired}",
            snapshot_id=snapshot_id, metric="veto_reject",
            threshold="any of the 14 hard vetoes", observed=str(fired),
            lineage="risk:vetoes")

    # -- views --------------------------------------------------------------
    def stats(self) -> Dict[str, Any]:
        return {"sent": self._sent, "skipped": self._skipped,
                "failed": self._failed, "outbox": len(self.outbox),
                "idempotency_keys": len(self.idempotency),
                "alerts": len(self.alert_audit),
                "buckets": {k: v.available() for k, v in self.buckets.items()}}

    def pruned_verdict(self, age_bars: int) -> Dict[str, Any]:
        """Ch.21 §11: PRUNED when older than ``theta_maxAge`` = 100 bars;
        transitions OLD → CORRECTION EVENT → NEW VERSION → SUPERSEDES."""
        pruned = int(age_bars) > THETA_MAX_AGE_BARS
        return {"state": "PRUNED" if pruned else "ACTIVE",
                "age_bars": int(age_bars), "theta_max_age": THETA_MAX_AGE_BARS,
                "correction_path": "OLD → CORRECTION EVENT → NEW VERSION → "
                                   "SUPERSEDES" if pruned else None}

    def decay(self, age_bars: int) -> float:
        """Ch.21 §14: decay formula ``exp(-0.02 * age)``."""
        import math
        return math.exp(-DECAY_LAMBDA * float(age_bars))


def _monotonic() -> float:
    import time as _time
    return _time.monotonic()


def _utc_now_ms() -> str:
    now = _dt.datetime.now(_dt.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


__all__ = [
    "ALERT_DEDUP_EXEMPT", "ALERT_DEDUP_WINDOW_SECONDS", "ALERT_NAMES",
    "ALERT_POLICY", "AiogramTransport", "CALLBACK_DATA_MAX_BYTES",
    "CAPTION_MAX_LENGTH", "CHART_LAYERS", "CONTRACT_VERSION",
    "DECAY_LAMBDA", "DECLARED_DELIVERY_TARGETS_SECONDS", "HTML_ALLOWED_TAGS",
    "HEARTBEAT_INTERVAL_SECONDS", "HEARTBEAT_MISS_LIMIT",
    "IDEMPOTENCY_KEY_TTL_SECONDS", "IMAGE_CHART_FORMAT", "IMAGE_CHART_HEIGHT",
    "IMAGE_CHART_QUALITY", "IMAGE_CHART_WIDTH", "INLINE_KEYBOARD_MAX_BUTTONS",
    "INLINE_KEYBOARD_MAX_ROWS", "LOG_RETENTION_DAYS", "MARKDOWNV2_ESCAPE_CHARS",
    "MESSAGE_STATES", "MessageTokenBucket", "PROVIDER_CEILING_PER_SECOND",
    "RATE_LIMITING_BUCKET_SIZE", "RATE_LIMITING_REFILL_RATE", "RETRY_BACKOFF_SECONDS",
    "RETRY_TIMES", "SendAttempt", "SendResult", "SignalMessage", "SignalingError",
    "SignalingPlane", "STORAGE_ALERT_FRACTION", "TELEGRAM_CONFIDENCE_FACTOR",
    "TELEGRAM_PARAMS", "TELEGRAM_QUALITY", "TELEGRAM_VALIDITY_CANDLES",
    "TEXT_MAX_LENGTH", "THETA_MAX_AGE_BARS", "TelegramTransport",
    "build_inline_keyboard", "comma_format", "escape_markdown_v2",
    "format_caption", "format_html", "format_markdown_v2", "idempotency_key",
    "render_chart",
]
