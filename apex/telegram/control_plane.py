"""Telegram control plane — Ch.21 §2/§5/§6 (APEX_GEN5.md L17578–17600,
L17622–17782): screens and menu structure, the 4-step Trading wizard, the
5-step Portfolio export wizard, Lab/Research (OWNER-only), Info, Settings
(5 options), Emergency (5 levels, OWNER-only, ratchet-guarded), Help (6 items),
roles OWNER/USER only (no ADMIN), binding Yes/No confirmations with a
90-second nonce (``o-<hex>``), Busy Guard ``MAX_CONCURRENT = 1`` →
``E-VAL-020`` + Stop, callback data ≤ 64 bytes, and auditable (never silent)
access denials.

Telegram is a downstream control/reporting interface: it never becomes market
truth, portfolio truth or Risk authority, and no control-plane action mutates
market state directly — every effect goes through an injected handler seam
(execution/ledger/risk), and a missing handler fails closed instead of
pretending success (L17570–17578).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import (Any, Awaitable, Callable, Dict, FrozenSet, List, Mapping,
                    Optional, Sequence, Tuple)

from apex.bus import EventBus, Priority
from apex.config import Config
from apex.data_catalog.contracts import CORE10_SYMBOLS, TIMEFRAMES_14
from apex.errors import get_error_code
from apex.identity.hashes import sha256_hex
from apex.telegram.signaling import (CALLBACK_DATA_MAX_BYTES, INLINE_KEYBOARD_MAX_BUTTONS,
                                     INLINE_KEYBOARD_MAX_ROWS, SignalMessage,
                                     SignalingPlane, build_inline_keyboard,
                                     comma_format, format_markdown_v2)

CONTRACT_VERSION = "4.0.0"

# ---------------------------------------------------------------------------
# Frozen control-plane literals (Ch.21 §5/§6; no YAML home — ISSUE-CP7-003)
# ---------------------------------------------------------------------------
ROLES: Tuple[str, ...] = ("OWNER", "USER")     # no ADMIN role exists
ENVS: Tuple[str, ...] = ("PAPER", "LIVE", "RESEARCH", "BACKTEST")   # no SHADOW

#: §5.2 Busy Guard.
MAX_CONCURRENT = 1
BUSY_GUARD_STATE_TABLE: Tuple[str, ...] = ("IDLE", "BUSY", "IDLE")

#: §5.2 Confirm Yes/No with a 90-second nonce; key format ``o-<hex>``.
CONFIRMATION_NONCE_SECONDS = 90.0
NONCE_KEY_FORMAT = "o-<hex>"

#: §5.7 Emergency L3 cancels all open orders (up to 12).
EMERGENCY_CANCEL_ALL_MAX_ORDERS = 12
EMERGENCY_LEVELS: Tuple[str, ...] = ("L1", "L2", "L3", "L4", "L5")
EMERGENCY_SEMANTICS: Dict[str, str] = {
    "L1": "PAUSE",
    "L2": "DISABLE_NEW — no new positions",
    "L3": "CANCEL_ALL — cancels all open orders (up to 12)",
    "L4": "CLOSE_ALL",
    "L5": "SAFE_MODE — preserves evidence, sends notifications, halts trading, "
          "sets read-only, closes all positions, turns safe mode ON",
}

#: §5.3 Portfolio export wizard (CSV/JSON only; PDF is not core runtime).
EXPORT_FORMATS: Tuple[str, ...] = ("CSV", "JSON")
EXPORT_TIME_RANGES: Tuple[str, ...] = ("1h", "12h", "24h", "7d", "Custom")
EXPORT_ENVIRONMENTS: Tuple[str, ...] = ("PAPER", "LIVE")
EXPORT_MAX_ITEMS = 25
EXPORT_DEFAULT_PATH = "/Download/APEX_Reports/"
EXPORT_EXAMPLE_SIZE_KB = 2.3

#: §5.6 Settings (5 options).
SETTINGS_OPTIONS: Tuple[str, ...] = ("Language", "Confirmations", "Users",
                                     "Export Path", "Timezone")
LANGUAGES: Tuple[str, ...] = ("EN", "FA")
TIMEZONE_DISPLAY = "UTC"        # local-device timezone is NEVER used

#: §5.8 Help (6 items).
HELP_ITEMS: Tuple[str, ...] = ("Getting Started", "Main Menu Guide", "Glossary",
                               "FAQ", "Support", "About")
MAIN_MENU_GUIDE_WALKTHROUGHS: Tuple[str, ...] = ("Trading", "Portfolio", "Lab",
                                                 "Info", "Settings", "Emergency")
GLOSSARY_TERMS: Tuple[str, ...] = ("PF", "Sharpe", "Drawdown")
FAQ_COUNT = 10

#: §5.5 Info.
INFO_SECTIONS: Tuple[str, ...] = ("Market", "Data Coverage", "System Status")
INFO_COVERAGE_CELLS = len(CORE10_SYMBOLS) * len(TIMEFRAMES_14)     # 140

#: §5.2 Trading wizard (4 steps) + supported timeframes (3d NOT supported).
TRADING_WIZARD_STEPS: Tuple[str, ...] = ("Symbol", "Timeframe",
                                         "Max Leverage/Risk", "Confirm")
UNSUPPORTED_TIMEFRAMES: FrozenSet[str] = frozenset({"3d"})
MONTHLY_CANONICAL_ID = "1mo"

#: §5.1 Main Menu (pseudo-render, 2 domain buttons per row).
MAIN_MENU_ROWS: Tuple[Tuple[str, ...], ...] = (
    ("📈 Trading", "💼 Portfolio"),
    ("🔬 Lab", "📊 Info"),
    ("⚙️ Settings", "🚨 Emergency"),
    ("🔄 Refresh", "❓ Help"),
)

#: Commands (§5.7 Panic Lock /lock /unlock; §5.8 Support /myid).
COMMANDS: Tuple[str, ...] = ("/start", "/myid", "/lock", "/unlock", "/help")

PANIC_LOCK_BROADCAST: Dict[str, str] = {
    "EN": "APEX PANIC LOCK ENGAGED — trading halted, positions preserved. "
          "OWNER: send /unlock to release.",
    "FA": "قفل اضطراری APEX فعال شد — معاملات متوقف و موقعیت‌ها حفظ شدند. "
          "فقط OWNER می‌تواند با /unlock قفل را باز کند.",
}
PANIC_UNLOCK_BROADCAST: Dict[str, str] = {
    "EN": "APEX PANIC LOCK RELEASED by OWNER — normal operation resumed.",
    "FA": "قفل اضطراری APEX توسط OWNER باز شد — فعالیت عادی از سر گرفته شد.",
}

SCREENS: Tuple[str, ...] = ("MAIN_MENU", "TRADING", "PORTFOLIO", "LAB",
                            "LAB_RESEARCH", "INFO", "SETTINGS", "EMERGENCY",
                            "HELP", "RUNNING_STATUS", "ACCESS_DENIED",
                            "CONFIRMATION")

#: Every screen carries global Back and Home controls (§5.1).
GLOBAL_CONTROLS: Tuple[str, ...] = ("🔙 Back", "🏠 Home")


class ControlPlaneError(RuntimeError):
    """Fail-closed control-plane violation with a deterministic reason."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}" + (f": {detail}" if detail else ""))


Handler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


def _audit_id(payload: str) -> str:
    """``o-a1b2c3d4``-style audit id (§5.4 Access Denied example)."""
    return "o-" + sha256_hex(payload)[:8]


def nonce_key(action: str, chat_id: Any, issued_at: str) -> str:
    """The confirmation key format ``o-<hex>`` (§5.2)."""
    return "o-" + sha256_hex(f"{action}|{chat_id}|{issued_at}")[:16]


# ---------------------------------------------------------------------------
# Access control (§6: OWNER/USER only; every denial auditable)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AccessVerdict:
    allowed: bool
    role: str
    required: Optional[str]
    chat_id: str
    audit_id: str
    reason: Optional[str]
    rule: str


class AccessControl:
    """Roles are keyed by ``chat_id`` (§5.6 Users). An unknown chat_id is a
    USER — never an implicit OWNER (fail-closed)."""

    def __init__(self, *, owner_chat_ids: Sequence[str] = (),
                 user_chat_ids: Sequence[str] = ()) -> None:
        self._owner: Dict[str, bool] = {str(c): True for c in owner_chat_ids}
        self._users: Dict[str, bool] = {str(c): True for c in user_chat_ids}
        self.denials: List[AccessVerdict] = []

    def role_of(self, chat_id: Any) -> str:
        return "OWNER" if str(chat_id) in self._owner else "USER"

    def add_user(self, chat_id: Any, *, caution: bool = False) -> Dict[str, Any]:
        self._users[str(chat_id)] = True
        return {"chat_id": str(chat_id), "listed": True,
                "caution": bool(caution), "role": self.role_of(chat_id)}

    def remove_user(self, chat_id: Any) -> Dict[str, Any]:
        removed = self._users.pop(str(chat_id), None) is not None
        return {"chat_id": str(chat_id), "removed": removed,
                "role": self.role_of(chat_id)}

    def listed_users(self) -> Tuple[Dict[str, Any], ...]:
        return tuple({"chat_id": c, "role": "OWNER" if c in self._owner else "USER"}
                     for c in sorted(set(self._users) | set(self._owner)))

    def check(self, chat_id: Any, *, required: Optional[str] = None,
              action: str = "") -> AccessVerdict:
        role = self.role_of(chat_id)
        audit = _audit_id(f"{chat_id}|{role}|{required}|{action}")
        if required is None or role == required:
            return AccessVerdict(True, role, required, str(chat_id), audit, None,
                                 "§6 roles OWNER/USER only; no ADMIN role")
        # The reason is the canonical machine token (§5.4/§5.7 "OWNER-only" and
        # "RESEARCH_ONLY + BLOCK"); the human phrasing lives in `rule`.
        verdict = AccessVerdict(False, role, required, str(chat_id), audit,
                                f"{required or 'OWNER'}_ONLY"
                                + (" + RESEARCH_ONLY + BLOCK"
                                   if action == "RESEARCH" else ""),
                                "§5.4 the denial is auditable, never silent")
        self.denials.append(verdict)
        return verdict


# ---------------------------------------------------------------------------
# Confirmation nonce (§5.2/§5.7/§6: binding Yes/No, 90 s, irreversible)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Nonce:
    key: str
    action: str
    chat_id: str
    issued_at: str
    issued_monotonic: float
    ttl_seconds: float = CONFIRMATION_NONCE_SECONDS
    consumed: bool = False


class ConfirmationRegistry:
    """Yes/No confirmations bound to a nonce. An expired, foreign or already
    consumed nonce never authorizes an action (fail-closed)."""

    def __init__(self, *, clock: Optional[Callable[[], float]] = None,
                 utc_now: Optional[Callable[[], str]] = None) -> None:
        self._clock = clock if clock is not None else _monotonic
        self._utc_now = utc_now if utc_now is not None else _utc_now_ms
        self._nonces: Dict[str, Nonce] = {}

    def issue(self, action: str, chat_id: Any) -> Nonce:
        ts = self._utc_now()
        key = nonce_key(action, chat_id, ts)
        nonce = Nonce(key=key, action=action, chat_id=str(chat_id), issued_at=ts,
                      issued_monotonic=self._clock())
        self._nonces[key] = nonce
        return nonce

    def consume(self, key: str, *, action: str, chat_id: Any, choice: str
                ) -> Dict[str, Any]:
        nonce = self._nonces.get(str(key))
        if nonce is None:
            return {"authorized": False, "reason": "NONCE_UNKNOWN",
                    "key_format": NONCE_KEY_FORMAT}
        if nonce.chat_id != str(chat_id):
            return {"authorized": False, "reason": "NONCE_CHAT_MISMATCH",
                    "audit_id": _audit_id(f"{key}|{chat_id}")}
        if nonce.action != action:
            return {"authorized": False, "reason": "NONCE_ACTION_MISMATCH"}
        if nonce.consumed:
            # §5.7: confirmation is irreversible — a replay never re-authorizes.
            return {"authorized": False, "reason": "NONCE_ALREADY_CONSUMED",
                    "rule": "irreversible Yes/No confirmation"}
        age = self._clock() - nonce.issued_monotonic
        if age > nonce.ttl_seconds:
            return {"authorized": False, "reason": "NONCE_EXPIRED",
                    "age_seconds": age, "ttl_seconds": nonce.ttl_seconds}
        if str(choice).upper() not in ("YES", "NO"):
            return {"authorized": False, "reason": "CHOICE_NOT_YES_NO"}
        self._nonces[key] = Nonce(**{**nonce.__dict__, "consumed": True})
        return {"authorized": str(choice).upper() == "YES", "reason": None,
                "nonce": key, "age_seconds": age, "ttl_seconds": nonce.ttl_seconds,
                "irreversible": True}

    def pending(self, chat_id: Any) -> Tuple[Nonce, ...]:
        return tuple(n for n in self._nonces.values() if n.chat_id == str(chat_id))


# ---------------------------------------------------------------------------
# Busy Guard (§5.2: MAX_CONCURRENT = 1 → E-VAL-020 + Stop)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BusyGuardVerdict:
    allowed: bool
    state: str                     # IDLE | BUSY
    active_run_id: Optional[str]
    reason: Optional[str]
    error_code: Optional[str]
    stop_button: bool
    rule: str


class BusyGuard:
    """State table ``IDLE → BUSY → IDLE`` with ``MAX_CONCURRENT = 1``. A second
    request while a run is active is rejected with ``E-VAL-020`` and a Stop
    button — never queued silently."""

    def __init__(self, *, max_concurrent: int = MAX_CONCURRENT) -> None:
        if int(max_concurrent) != MAX_CONCURRENT:
            raise ControlPlaneError("MAX_CONCURRENT_CHANGED",
                                    f"{max_concurrent} != {MAX_CONCURRENT}")
        self.max_concurrent = int(max_concurrent)
        self._active: Optional[str] = None
        self.rejections: List[Dict[str, Any]] = []

    @property
    def state(self) -> str:
        return "BUSY" if self._active else "IDLE"

    @property
    def active_run_id(self) -> Optional[str]:
        return self._active

    def try_acquire(self, run_id: str) -> BusyGuardVerdict:
        if self._active is not None:
            verdict = BusyGuardVerdict(
                allowed=False, state="BUSY", active_run_id=self._active,
                reason=f"MAX_CONCURRENT={MAX_CONCURRENT} reached — run "
                       f"{self._active} is active",
                error_code=get_error_code("E-VAL-020").code, stop_button=True,
                rule="§5.2 Busy Guard; errors table E-VAL-020 "
                     "(IDLE → BUSY → IDLE, Stop button)")
            self.rejections.append({"run_id": run_id, **verdict.__dict__})
            return verdict
        self._active = str(run_id)
        return BusyGuardVerdict(True, "BUSY", self._active, None, None, False,
                                "§5.2 Busy Guard MAX_CONCURRENT=1")

    def release(self) -> BusyGuardVerdict:
        finished, self._active = self._active, None
        return BusyGuardVerdict(True, "IDLE", None,
                                f"released {finished}" if finished else "idle",
                                None, False, "§5.2 IDLE → BUSY → IDLE")


# ---------------------------------------------------------------------------
# Update de-duplication (Telegram retries the same update_id)
# ---------------------------------------------------------------------------

class UpdateDeduplicator:
    """``update_id`` replay guard: a duplicated inbound update is answered with
    the recorded result and NEVER re-executed (Ch.21 §7 idempotency law)."""

    def __init__(self, *, max_entries: int = 4096) -> None:
        self._seen: Dict[Any, Dict[str, Any]] = {}
        self._max = int(max_entries)

    def is_replay(self, update_id: Any) -> bool:
        return update_id in self._seen

    def record(self, update_id: Any, result: Mapping[str, Any]) -> None:
        self._seen[update_id] = dict(result)
        if len(self._seen) > self._max:
            for stale in list(self._seen)[:len(self._seen) - self._max]:
                del self._seen[stale]

    def replay_of(self, update_id: Any) -> Optional[Dict[str, Any]]:
        return dict(self._seen[update_id]) if update_id in self._seen else None

    def __len__(self) -> int:
        return len(self._seen)


# ---------------------------------------------------------------------------
# Export wizard validation (§5.3)
# ---------------------------------------------------------------------------

def validate_export_request(*, items: Sequence[str], time_range: str,
                            environment: str, fmt: str, path: str,
                            create_folder: bool = False) -> Dict[str, Any]:
    """CSV/JSON only; up to 25 items; 1h/12h/24h/7d/Custom; PAPER or LIVE;
    path under ``/Download/APEX_Reports/``. Anything else fails closed — PDF is
    not part of the core runtime."""
    errors: List[str] = []
    if str(fmt).upper() not in EXPORT_FORMATS:
        errors.append(f"FORMAT_UNSUPPORTED:{fmt} (CSV/JSON only; PDF is not "
                      "part of the core runtime)")
    if str(time_range) not in EXPORT_TIME_RANGES:
        errors.append(f"TIME_RANGE_UNSUPPORTED:{time_range}")
    if str(environment).upper() not in EXPORT_ENVIRONMENTS:
        errors.append(f"ENVIRONMENT_UNSUPPORTED:{environment} (PAPER or LIVE)")
    if len(items) > EXPORT_MAX_ITEMS:
        errors.append(f"TOO_MANY_ITEMS:{len(items)} > {EXPORT_MAX_ITEMS}")
    if not items:
        errors.append("NO_ITEMS_SELECTED")
    if not str(path).startswith(EXPORT_DEFAULT_PATH.rstrip("/")):
        errors.append(f"PATH_OUTSIDE_EXPORT_ROOT:{path}")
    return {"valid": not errors, "errors": tuple(errors),
            "format": str(fmt).upper(), "items": tuple(items),
            "item_count": len(items), "time_range": str(time_range),
            "environment": str(environment).upper(), "path": str(path),
            "create_folder": bool(create_folder),
            "example_output_size_kb": EXPORT_EXAMPLE_SIZE_KB,
            "rule": "§5.3 5-step export wizard (CSV/JSON only)"}


# ---------------------------------------------------------------------------
# Emergency ratchet (§5.7: downgrading is forbidden → RSK-ERR-506)
# ---------------------------------------------------------------------------

class EmergencyRatchet:
    """The Emergency level only ever ratchets UP. A "ratchet down" raises
    ``RSK-ERR-506`` and only OWNER can recover from an Emergency state."""

    def __init__(self) -> None:
        self._level: Optional[str] = None
        self.history: List[Dict[str, Any]] = []

    @property
    def level(self) -> Optional[str]:
        return self._level

    @property
    def index(self) -> int:
        return EMERGENCY_LEVELS.index(self._level) if self._level else -1

    def request(self, level: str) -> Dict[str, Any]:
        if level not in EMERGENCY_LEVELS:
            raise ControlPlaneError("EMERGENCY_LEVEL_UNKNOWN",
                                    f"{level} not in {EMERGENCY_LEVELS}")
        target = EMERGENCY_LEVELS.index(level)
        if self._level is not None and target < self.index:
            record = {"allowed": False, "requested": level, "current": self._level,
                      "reason": "RATCHET_DOWN_FORBIDDEN",
                      "error_code": get_error_code("RSK-ERR-506").code,
                      "semantics": EMERGENCY_SEMANTICS[level],
                      "rule": "§5.7 downgrading a level is forbidden → "
                              "RSK-ERR-506; only OWNER can recover"}
            self.history.append(record)
            return record
        self._level = level
        record = {"allowed": True, "requested": level, "current": self._level,
                  "reason": None, "error_code": None,
                  "semantics": EMERGENCY_SEMANTICS[level],
                  "rule": "§5.7 Emergency levels L1–L5 (OWNER-only)"}
        self.history.append(record)
        return record

    def recover(self, *, role: str) -> Dict[str, Any]:
        if role != "OWNER":
            return {"recovered": False, "reason": "OWNER_ONLY_RECOVERY",
                    "error_code": get_error_code("RSK-ERR-506").code,
                    "rule": "§5.7 only OWNER can recover from an Emergency state"}
        previous, self._level = self._level, None
        return {"recovered": True, "previous": previous, "current": None,
                "reason": None, "error_code": None,
                "rule": "§5.7 OWNER recovery"}


# ---------------------------------------------------------------------------
# The control plane
# ---------------------------------------------------------------------------

class ControlPlane:
    """Screens, commands, callbacks and guardrails. Every effect is dispatched
    to an injected handler seam; a missing handler is refused (never faked)."""

    def __init__(self, *, signaling: Optional[SignalingPlane] = None,
                 access: Optional[AccessControl] = None,
                 config: Optional[Config] = None,
                 clock: Optional[Callable[[], float]] = None,
                 utc_now: Optional[Callable[[], str]] = None,
                 handlers: Optional[Mapping[str, Handler]] = None,
                 bus: Optional[EventBus] = None,
                 environment: str = "PAPER",
                 paper_balance: Any = "10000") -> None:
        self._config = config or Config()
        self.signaling = signaling
        cfg_owner = self._config.telegram_owner_chat_id
        self.access = access or AccessControl(
            owner_chat_ids=[cfg_owner] if cfg_owner else [],
            user_chat_ids=[self._config.telegram_watchdog_chat_id]
            if self._config.telegram_watchdog_chat_id else [])
        self._clock = clock if clock is not None else _monotonic
        self._utc_now = utc_now if utc_now is not None else _utc_now_ms
        self.confirmations = ConfirmationRegistry(clock=self._clock,
                                                  utc_now=self._utc_now)
        self.busy = BusyGuard()
        self.ratchet = EmergencyRatchet()
        self.updates = UpdateDeduplicator()
        self._handlers: Dict[str, Handler] = dict(handlers or {})
        self.bus = bus
        self.environment = environment if environment in ENVS else "PAPER"
        self.paper_balance = comma_format(paper_balance)
        self.locked = False
        self.settings: Dict[str, Any] = {"Language": "EN", "Confirmations": True,
                                         "Users": self.access.listed_users(),
                                         "Export Path": EXPORT_DEFAULT_PATH,
                                         "Timezone": TIMEZONE_DISPLAY}
        self.audit: List[Dict[str, Any]] = []
        self.safe_mode = False
        self.read_only = False
        self.new_positions_disabled = False
        self.paused = False

    # -- handler seam -------------------------------------------------------
    def register(self, action: str, handler: Handler) -> None:
        self._handlers[action] = handler

    def handler_for(self, action: str) -> Optional[Handler]:
        return self._handlers.get(action)

    async def dispatch(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        handler = self._handlers.get(action)
        if handler is None:
            # Fail-closed: a control-plane action without a wired effect is
            # refused, never reported as done (G6; §1 mission).
            record = {"action": action, "ok": False,
                      "reason": "ACTION_HANDLER_UNAVAILABLE",
                      "error_code": get_error_code("E-VAL-020").code
                      if action == "BACKTEST_RUN" else None,
                      "detail": "no handler registered — the action is refused, "
                                "never silently pretended"}
            self.audit.append(record)
            return record
        try:
            result = dict(await handler(payload))
            record = {"action": action, "ok": True, "reason": None, **result}
        except Exception as exc:
            record = {"action": action, "ok": False,
                      "reason": f"{type(exc).__name__}", "detail": str(exc)[:200]}
        self.audit.append(record)
        return record

    # -- screens ------------------------------------------------------------
    def screen_main_menu(self) -> Dict[str, Any]:
        # §5.1's pseudo-render header reads "… — UTC+3:30" while §5.6 mandates
        # "UTC for both internal processing and display; local-device timezone
        # is never used" (and Y.3 L17437 bans local offsets from normative
        # runtime logic). The normative settings rule wins: the header shows UTC
        # (ISSUE-CP7-007).
        return {"screen": "MAIN_MENU",
                "title": f"APEX — Full Unlock — {self.environment} "
                         f"{self.paper_balance} USDT — {TIMEZONE_DISPLAY}",
                "rows": MAIN_MENU_ROWS, "global_controls": GLOBAL_CONTROLS,
                "full_unlock": True,
                "rule": "§5.1 two domain buttons per row; no environment-based "
                        "restriction on which buttons are visible"}

    def screen_lab(self, chat_id: Any) -> Dict[str, Any]:
        verdict = self.access.check(chat_id, required="OWNER", action="RESEARCH")
        rows: List[Tuple[str, ...]] = [("📊 Backtest", "⚙️ Optimize")]
        rows.append(("🧪 Research Estimators",) if verdict.allowed
                    else ("🧪 Research Estimators 🔒 OWNER only",))
        rows.append(("📜 Backtest History",))
        return {"screen": "LAB", "title": "🔬 Lab — Select Action", "rows": rows,
                "research_visible": verdict.allowed,
                "research_locked_label": not verdict.allowed,
                "global_controls": GLOBAL_CONTROLS,
                "rule": "§5.4 Research lives inside Lab, OWNER only; Backtest "
                        "(PAPER) stays fully active for all users"}

    def screen_research(self, chat_id: Any) -> Dict[str, Any]:
        verdict = self.access.check(chat_id, required="OWNER", action="RESEARCH")
        if not verdict.allowed:
            return {"screen": "ACCESS_DENIED",
                    "title": "⛔ Access Denied — RESEARCH_ONLY",
                    "text": "OWNER-only and empirical closure required.",
                    "reason": "RESEARCH_ONLY + BLOCK",
                    "audit_id": verdict.audit_id,
                    "global_controls": GLOBAL_CONTROLS,
                    "rule": "§5.4 the denial is auditable, never silent; no "
                            "global environment switch exists"}
        return {"screen": "LAB_RESEARCH",
                "title": "🧪 Research Estimators — RESEARCH_ONLY — No Capital",
                "status": "BLOCK for LIVE — Comparison only in BACKTEST",
                "estimators": (
                    {"id": "R-ATR-002", "name": "ZLSMA", "state": "OPEN",
                     "note": "Fallback Wilder",
                     "impact": "theta_sweep +15% whipsaw RANGE"},
                    {"id": "R-ATR-003", "name": "Kalman Q,R", "state": "OPEN",
                     "note": "Needs Q,R closure", "impact": "battery drain"},
                    {"id": "R-ATR-007", "name": "Yang-Zhang", "state": "OPEN",
                     "note": "best vol estimator", "impact": None}),
                "actions": ("📊 Compare in Backtest", "📄 View Token bucket"),
                "compare_in_backtest": {"opens": "Backtest Wizard",
                                        "data_source": "RESEARCH",
                                        "produces": "Report only",
                                        "trade_plan": False, "routed_to_live": False},
                "global_controls": GLOBAL_CONTROLS,
                "rule": "§5.4 Compare in Backtest produces a Report only — "
                        "never a Trade Plan, never routed to LIVE"}

    def screen_info(self) -> Dict[str, Any]:
        return {"screen": "INFO",
                "sections": {"Market": {"top10": tuple(CORE10_SYMBOLS),
                                        "core10": tuple(CORE10_SYMBOLS),
                                        "levels": ("plain-language", "technical",
                                                   "philosophical",
                                                   "second-order-effects")},
                             "Data Coverage": INFO_COVERAGE_CELLS,
                             "System Status": "HEALTHY"},
                "global_controls": GLOBAL_CONTROLS,
                "rule": "§5.5 four-part Info screen; 140 symbol/timeframe "
                        "combinations"}

    def screen_settings(self) -> Dict[str, Any]:
        return {"screen": "SETTINGS", "options": SETTINGS_OPTIONS,
                "values": dict(self.settings), "languages": LANGUAGES,
                "timezone": TIMEZONE_DISPLAY,
                "export_path": self.settings["Export Path"],
                "global_controls": GLOBAL_CONTROLS,
                "rule": "§5.6 five options; UTC for internal processing AND "
                        "display — local-device timezone is never used"}

    def screen_emergency(self, chat_id: Any) -> Dict[str, Any]:
        verdict = self.access.check(chat_id, required="OWNER", action="EMERGENCY")
        if not verdict.allowed:
            return {"screen": "ACCESS_DENIED",
                    "title": "⛔ Access Denied — Emergency is OWNER-only",
                    "reason": "OWNER_ONLY", "audit_id": verdict.audit_id,
                    "global_controls": GLOBAL_CONTROLS,
                    "rule": "§5.7 USER receives Access Denied for all Emergency "
                            "actions"}
        return {"screen": "EMERGENCY", "levels": EMERGENCY_LEVELS,
                "semantics": dict(EMERGENCY_SEMANTICS),
                "current_level": self.ratchet.level,
                "confirmation": {"type": "Yes/No", "irreversible": True,
                                 "nonce_seconds": CONFIRMATION_NONCE_SECONDS,
                                 "key_format": NONCE_KEY_FORMAT},
                "ratchet_down_error": get_error_code("RSK-ERR-506").code,
                "cancel_all_max_orders": EMERGENCY_CANCEL_ALL_MAX_ORDERS,
                "panic_lock_commands": ("/lock", "/unlock"),
                "global_controls": GLOBAL_CONTROLS,
                "rule": "§5.7 five levels, OWNER-only; ratchet down forbidden"}

    def screen_help(self) -> Dict[str, Any]:
        return {"screen": "HELP", "items": HELP_ITEMS,
                "main_menu_guide": MAIN_MENU_GUIDE_WALKTHROUGHS,
                "glossary": GLOSSARY_TERMS, "faq_count": FAQ_COUNT,
                "support_command": "/myid",
                "about": "minimal, quant-focused, no W-8 form content",
                "global_controls": GLOBAL_CONTROLS,
                "rule": "§5.8 six Help items"}

    def screen_trading(self, *, symbol: Optional[str] = None,
                       timeframe: Optional[str] = None) -> Dict[str, Any]:
        """§5.2 Trading wizard. ``3d`` is unsupported everywhere in Telegram
        flows; the monthly canonical id is ``1mo``."""
        if timeframe in UNSUPPORTED_TIMEFRAMES:
            raise ControlPlaneError("TIMEFRAME_UNSUPPORTED",
                                    f"{timeframe} — 3d is not supported (§5.2)")
        return {"screen": "TRADING", "steps": TRADING_WIZARD_STEPS,
                "symbols": tuple(CORE10_SYMBOLS), "single_page": True,
                "timeframes": tuple(TIMEFRAMES_14),
                "unsupported_timeframes": tuple(UNSUPPORTED_TIMEFRAMES),
                "monthly_canonical_id": MONTHLY_CANONICAL_ID,
                "bundles": INFO_COVERAGE_CELLS,
                "max_leverage_rule": "ceiling, not a fixed final value",
                "confirmation": {"type": "Yes/No",
                                 "nonce_seconds": CONFIRMATION_NONCE_SECONDS,
                                 "key_format": NONCE_KEY_FORMAT},
                "selected": {"symbol": symbol, "timeframe": timeframe},
                "busy_guard": {"max_concurrent": MAX_CONCURRENT,
                               "state": self.busy.state,
                               "active_run_id": self.busy.active_run_id,
                               "error_code": get_error_code("E-VAL-020").code},
                "global_controls": GLOBAL_CONTROLS,
                "rule": "§5.2 4-step wizard; Running-status view shows Uptime, "
                        "Signals, Exposure, Last Signal — not a progress bar "
                        "(progress bars are Lab-only)"}

    def screen_running_status(self, *, uptime_seconds: float = 0.0,
                              signals: int = 0, exposure: Any = "0",
                              last_signal: Optional[str] = None) -> Dict[str, Any]:
        return {"screen": "RUNNING_STATUS",
                "uptime": uptime_seconds, "signals": signals,
                "exposure": comma_format(exposure), "last_signal": last_signal,
                "progress_bar": False,
                "rule": "§5.2 no progress bar — progress bars are Lab-only"}

    def render(self, screen: str, chat_id: Any, **kwargs: Any) -> Dict[str, Any]:
        builders = {
            "MAIN_MENU": self.screen_main_menu,
            "TRADING": lambda: self.screen_trading(**kwargs),
            "RUNNING_STATUS": lambda: self.screen_running_status(**kwargs),
            "PORTFOLIO": lambda: {"screen": "PORTFOLIO",
                                  "steps": ("Positions", "Orders", "Wallet",
                                            "Export", "Send/Share"),
                                  "formats": EXPORT_FORMATS,
                                  "time_ranges": EXPORT_TIME_RANGES,
                                  "environments": EXPORT_ENVIRONMENTS,
                                  "max_items": EXPORT_MAX_ITEMS,
                                  "default_path": EXPORT_DEFAULT_PATH,
                                  "pdf_supported": False,
                                  "global_controls": GLOBAL_CONTROLS,
                                  "rule": "§5.3 5-step export wizard"},
            "LAB": lambda: self.screen_lab(chat_id),
            "LAB_RESEARCH": lambda: self.screen_research(chat_id),
            "INFO": self.screen_info,
            "SETTINGS": self.screen_settings,
            "EMERGENCY": lambda: self.screen_emergency(chat_id),
            "HELP": self.screen_help,
        }
        if screen not in builders or screen not in SCREENS:
            raise ControlPlaneError("SCREEN_UNKNOWN", str(screen))
        rendered = builders[screen]()
        rows = rendered.get("rows")
        if rows is None:
            items = list(rendered.get("items") or rendered.get("options")
                         or rendered.get("levels") or rendered.get("estimators")
                         or rendered.get("actions") or [])
            rows = _pair_rows([_label(i) for i in items])
        # ISSUE-CP7-009: Ch.21 §10 caps an inline keyboard at 8 buttons / 4
        # rows while §5.1 shows eight DOMAIN buttons plus the global Back/Home
        # controls on every screen. The §10 budget is applied to the domain
        # buttons (overflow is truncated and reported as E-TELE-005 /
        # Q2_DEGRADED — never silently dropped) and the two global controls are
        # rendered as their own final row so Back/Home is ALWAYS reachable.
        domain_rows = list(rows)
        keyboard = build_inline_keyboard(
            [[{"text": label, "callback_data": _callback_for(label, screen)}
              for label in row] for row in domain_rows])
        global_keyboard = build_inline_keyboard(
            [[{"text": label, "callback_data": _callback_for(label, screen)}
              for label in GLOBAL_CONTROLS]])
        rendered["rows"] = tuple(domain_rows) + (GLOBAL_CONTROLS,)
        rendered["inline_keyboard"] = (keyboard["inline_keyboard"]
                                       + global_keyboard["inline_keyboard"])
        rendered["domain_button_count"] = keyboard["button_count"]
        rendered["domain_row_count"] = keyboard["row_count"]
        rendered["global_controls_row"] = global_keyboard["inline_keyboard"][0]
        rendered["callback_data_max_bytes"] = CALLBACK_DATA_MAX_BYTES
        rendered["keyboard_quality"] = keyboard["quality"]
        rendered["keyboard_error_code"] = keyboard["error_code"]
        rendered["keyboard_truncated"] = bool(
            keyboard["truncated_buttons"] or keyboard["truncated_rows"])
        rendered["markdown_v2"] = format_markdown_v2(
            rendered.get("title", screen))["parse_mode"]
        return rendered

    # -- commands -----------------------------------------------------------
    async def handle_command(self, chat_id: Any, text: str,
                             update_id: Optional[Any] = None) -> Dict[str, Any]:
        """Command entry point with update_id replay protection and the Panic
        Lock (§5.7)."""
        if update_id is not None and self.updates.is_replay(update_id):
            replay = self.updates.replay_of(update_id) or {}
            return {"replayed": True, **replay}
        command = str(text).split()[0].lower() if str(text).strip() else ""
        if self.locked and command not in ("/myid", "/unlock"):
            # §5.7: while the Panic Lock is engaged only /myid and /unlock are
            # served — every other command is refused (never silently ignored).
            lock = self.locked_verdict(command)
            result = {"command": command, "ok": False, **lock}
            if update_id is not None:
                self.updates.record(update_id, result)
            return result
        result = await self._command(chat_id, command)
        if update_id is not None:
            self.updates.record(update_id, result)
        return result

    async def _command(self, chat_id: Any, command: str) -> Dict[str, Any]:
        role = self.access.role_of(chat_id)
        if command == "/myid":
            return {"command": command, "ok": True, "chat_id": str(chat_id),
                    "role": role, "rule": "§5.8 Support (/myid)"}
        if command == "/start":
            return {"command": command, "ok": True, "role": role,
                    **self.screen_main_menu()}
        if command == "/help":
            return {"command": command, "ok": True, "role": role,
                    **self.screen_help()}
        if command == "/lock":
            self.locked = True
            await self._broadcast(PANIC_LOCK_BROADCAST, alert="PANIC_LOCK_ENGAGED")
            return {"command": command, "ok": True, "locked": True,
                    "broadcast": PANIC_LOCK_BROADCAST,
                    "rule": "§5.7 Panic Lock /lock + broadcast in EN and FA"}
        if command == "/unlock":
            verdict = self.access.check(chat_id, required="OWNER", action="UNLOCK")
            if not verdict.allowed:
                return {"command": command, "ok": False, "locked": self.locked,
                        "reason": "OWNER_ONLY", "audit_id": verdict.audit_id,
                        "rule": "§5.7 only OWNER can recover"}
            self.locked = False
            await self._broadcast(PANIC_UNLOCK_BROADCAST,
                                  alert="PANIC_LOCK_RELEASED")
            return {"command": command, "ok": True, "locked": False,
                    "broadcast": PANIC_UNLOCK_BROADCAST}
        return {"command": command, "ok": False, "reason": "COMMAND_UNKNOWN",
                "supported": COMMANDS}

    async def _broadcast(self, messages: Mapping[str, str], *, alert: str) -> None:
        if self.signaling is None or not self.signaling.owner_chat_id:
            self.audit.append({"action": f"BROADCAST_{alert}", "ok": False,
                               "reason": "NO_SIGNALING_PLANE"})
            return
        for language in LANGUAGES:
            text = messages[language]
            await self.signaling.send(SignalMessage(
                signal_id=f"{alert}_{language}_{self._utc_now()}",
                chat_id=str(self.signaling.owner_chat_id),
                priority=Priority.P0, text=text, timestamp_utc=self._utc_now(),
                alert=alert, metric="panic_lock", threshold="/lock or /unlock",
                observed=language, lineage=f"telegram:{alert}"), force=True)

    def locked_verdict(self, action: str) -> Dict[str, Any]:
        """While the Panic Lock is engaged only /myid and /unlock are served."""
        if not self.locked:
            return {"blocked": False, "action": action}
        return {"blocked": True, "action": action, "reason": "PANIC_LOCK_ENGAGED",
                "allowed_commands": ("/myid", "/unlock"),
                "rule": "§5.7 Panic Lock"}

    # -- callbacks ----------------------------------------------------------
    async def handle_callback(self, chat_id: Any, data: str,
                              update_id: Optional[Any] = None,
                              **context: Any) -> Dict[str, Any]:
        """Callback-query entry point: replay guard → panic lock → role check →
        guardrails (busy guard, ratchet, nonce) → handler seam."""
        if update_id is not None and self.updates.is_replay(update_id):
            return {"replayed": True, **(self.updates.replay_of(update_id) or {})}
        raw = str(data)
        if len(raw.encode("utf-8")) > CALLBACK_DATA_MAX_BYTES:
            result = {"ok": False, "reason": "CALLBACK_DATA_TOO_LONG",
                      "bytes": len(raw.encode("utf-8")),
                      "max_bytes": CALLBACK_DATA_MAX_BYTES,
                      "error_code": get_error_code("E-TELE-005").code}
            if update_id is not None:
                self.updates.record(update_id, result)
            return result
        lock = self.locked_verdict(raw)
        if lock["blocked"]:
            result = {"ok": False, **lock}
            if update_id is not None:
                self.updates.record(update_id, result)
            return result
        action, _, arg = raw.partition(":")
        result = await self._action(chat_id, action, arg, **context)
        if update_id is not None:
            self.updates.record(update_id, result)
        return result

    async def _action(self, chat_id: Any, action: str, arg: str,
                      **context: Any) -> Dict[str, Any]:
        role = self.access.role_of(chat_id)
        if action in ("BACK", "HOME"):
            return {"ok": True, "action": action, "role": role,
                    **self.screen_main_menu()}
        if action in ("SCREEN", "MENU"):
            screen = (arg or context.get("screen") or "MAIN_MENU").upper()
            return {"ok": True, "action": action, "role": role,
                    **self.render(screen, chat_id)}
        if action == "RESEARCH":
            return {"ok": True, "action": action, "role": role,
                    **self.screen_research(chat_id)}
        if action == "EMERGENCY":
            return await self._emergency(chat_id, arg, **context)
        if action == "RECOVER":
            verdict = self.access.check(chat_id, required="OWNER", action="RECOVER")
            if not verdict.allowed:
                return {"ok": False, "action": action, "reason": "OWNER_ONLY",
                        "audit_id": verdict.audit_id}
            return {"ok": True, "action": action,
                    **self.ratchet.recover(role=role)}
        if action == "CONFIRM":
            # arg = "<nonce>:<YES|NO>:<action>"
            parts = arg.split(":")
            if len(parts) != 3:
                return {"ok": False, "action": action,
                        "reason": "CONFIRMATION_MALFORMED",
                        "key_format": NONCE_KEY_FORMAT}
            key, choice, target = parts
            consumed = self.confirmations.consume(key, action=target,
                                                  chat_id=chat_id, choice=choice)
            if not consumed["authorized"]:
                return {"ok": False, "action": action, "target": target,
                        **consumed}
            return {"ok": True, "action": action, "target": target,
                    **consumed,
                    **await self._execute_confirmed(chat_id, target, context)}
        if action == "BACKTEST_RUN":
            run_id = arg or context.get("run_id") or "BT-00000"
            verdict = self.busy.try_acquire(run_id)
            if not verdict.allowed:
                return {"ok": False, "action": action, "run_id": run_id,
                        **verdict.__dict__}
            try:
                dispatched = await self.dispatch("BACKTEST_RUN",
                                                 {"run_id": run_id, **context})
            finally:
                self.busy.release()
            return {"ok": bool(dispatched.get("ok")), "action": action,
                    "run_id": run_id, **dispatched}
        if action == "EXPORT":
            request = dict(context.get("export") or {})
            validated = validate_export_request(
                items=request.get("items", ()),
                time_range=request.get("time_range", ""),
                environment=request.get("environment", self.environment),
                fmt=request.get("format", ""),
                path=request.get("path", EXPORT_DEFAULT_PATH),
                create_folder=bool(request.get("create_folder", False)))
            if not validated["valid"]:
                return {"ok": False, "action": action, **validated}
            return {"ok": True, "action": action, **validated,
                    **await self.dispatch("EXPORT", validated)}
        return {"ok": False, "action": action, "reason": "ACTION_UNKNOWN",
                "role": role}

    async def _execute_confirmed(self, chat_id: Any, target: str,
                                 context: Mapping[str, Any]) -> Dict[str, Any]:
        if target.startswith("EMERGENCY_"):
            return await self._emergency(chat_id, target.split("_", 1)[1],
                                         confirmed=True, **context)
        return await self.dispatch(target, {"chat_id": str(chat_id), **context})

    # -- emergency ----------------------------------------------------------
    async def _emergency(self, chat_id: Any, level: str, *,
                         confirmed: bool = False, **context: Any) -> Dict[str, Any]:
        verdict = self.access.check(chat_id, required="OWNER", action="EMERGENCY")
        if not verdict.allowed:
            return {"ok": False, "action": "EMERGENCY", "level": level,
                    "reason": "OWNER_ONLY", "audit_id": verdict.audit_id,
                    "screen": "ACCESS_DENIED",
                    "rule": "§5.7 USER receives Access Denied for all Emergency "
                            "actions; the denial is auditable"}
        level = str(level).upper()
        ratchet = self.ratchet.request(level)
        if not ratchet["allowed"]:
            return {"ok": False, "action": "EMERGENCY", **ratchet,
                    "screen": "EMERGENCY"}
        if not confirmed:
            nonce = self.confirmations.issue(f"EMERGENCY_{level}", chat_id)
            return {"ok": True, "action": "EMERGENCY", "level": level,
                    "awaiting_confirmation": True, "nonce": nonce.key,
                    "nonce_ttl_seconds": CONFIRMATION_NONCE_SECONDS,
                    "key_format": NONCE_KEY_FORMAT, "irreversible": True,
                    "semantics": EMERGENCY_SEMANTICS[level],
                    "rule": "§5.7 Yes/No confirmation with a 90-second nonce"}
        effect = await self._emergency_effect(level, context)
        if self.signaling is not None and self.signaling.owner_chat_id:
            await self.signaling.emit_alert(
                alert="EXEC_RECOVERY" if level in ("L4", "L5") else "CIRCUIT_OPEN",
                metric=f"emergency_{level}",
                threshold=EMERGENCY_SEMANTICS[level], observed=level,
                snapshot_id=str(context.get("snapshot_id", "")),
                escalation_note="immediate OWNER")
        return {"ok": bool(effect.get("ok", False)), "action": "EMERGENCY",
                "level": level, "confirmed": True, **effect}

    async def _emergency_effect(self, level: str,
                                context: Mapping[str, Any]) -> Dict[str, Any]:
        if level == "L1":
            self.paused = True
            return await self.dispatch("EMERGENCY_PAUSE",
                                       {"level": level, **context})
        if level == "L2":
            self.new_positions_disabled = True
            return await self.dispatch("EMERGENCY_DISABLE_NEW",
                                       {"level": level, **context})
        if level == "L3":
            open_orders = list(context.get("open_orders") or [])
            batches = [open_orders[i:i + EMERGENCY_CANCEL_ALL_MAX_ORDERS]
                       for i in range(0, len(open_orders),
                                      EMERGENCY_CANCEL_ALL_MAX_ORDERS)] or [[]]
            results = []
            for batch in batches:
                results.append(await self.dispatch(
                    "EMERGENCY_CANCEL_ALL",
                    {"level": level, "orders": batch, "batch_size": len(batch),
                     "max_orders_per_batch": EMERGENCY_CANCEL_ALL_MAX_ORDERS,
                     **context}))
            return {"ok": all(r.get("ok") for r in results),
                    "batches": len(batches), "orders": len(open_orders),
                    "results": tuple(results)}
        if level == "L4":
            return await self.dispatch("EMERGENCY_CLOSE_ALL",
                                       {"level": level, **context})
        if level == "L5":
            self.safe_mode = True
            self.read_only = True
            self.paused = True
            self.new_positions_disabled = True
            preserved = await self.dispatch("EMERGENCY_SAFE_MODE",
                                            {"level": level, **context})
            return {"ok": bool(preserved.get("ok")), "safe_mode": True,
                    "read_only": True, "halts_trading": True,
                    "closes_all_positions": True, "preserves_evidence": True,
                    "sends_notifications": True, **preserved}
        raise ControlPlaneError("EMERGENCY_LEVEL_UNKNOWN", level)


def _label(item: Any) -> str:
    if isinstance(item, Mapping):
        return str(item.get("name") or item.get("id") or item.get("label") or "")
    return str(item)


def _pair_rows(labels: Sequence[str]) -> List[Tuple[str, ...]]:
    """§5.1 layout rule: max 2 domain buttons per row."""
    return [tuple(labels[i:i + 2]) for i in range(0, len(labels), 2)]


def _callback_for(label: str, screen: str) -> str:
    """Callback data ≤ 64 bytes (§6); deterministic and ASCII-safe."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_").upper()[:24]
    data = f"{screen}:{slug}"
    return data.encode("utf-8")[:CALLBACK_DATA_MAX_BYTES].decode("utf-8", "ignore")


def _monotonic() -> float:
    import time as _time
    return _time.monotonic()


def _utc_now_ms() -> str:
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


__all__ = [
    "AccessControl", "AccessVerdict", "BusyGuard", "BusyGuardVerdict",
    "CALLBACK_DATA_MAX_BYTES", "COMMANDS", "CONFIRMATION_NONCE_SECONDS",
    "CONTRACT_VERSION", "ConfirmationRegistry", "ControlPlane",
    "ControlPlaneError", "EMERGENCY_CANCEL_ALL_MAX_ORDERS", "EMERGENCY_LEVELS",
    "EMERGENCY_SEMANTICS", "ENVS", "EXPORT_DEFAULT_PATH", "EXPORT_ENVIRONMENTS",
    "EXPORT_FORMATS", "EXPORT_MAX_ITEMS", "EXPORT_TIME_RANGES", "GLOBAL_CONTROLS",
    "HELP_ITEMS", "INFO_COVERAGE_CELLS", "LANGUAGES", "MAIN_MENU_ROWS",
    "MAX_CONCURRENT", "MONTHLY_CANONICAL_ID", "NONCE_KEY_FORMAT", "Nonce",
    "PANIC_LOCK_BROADCAST", "PANIC_UNLOCK_BROADCAST", "ROLES", "SCREENS",
    "SETTINGS_OPTIONS", "TIMEZONE_DISPLAY", "TRADING_WIZARD_STEPS",
    "UNSUPPORTED_TIMEFRAMES", "UpdateDeduplicator", "EmergencyRatchet",
    "nonce_key", "validate_export_request",
]
