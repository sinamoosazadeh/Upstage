"""Toobit wire map — Ch.16 "Toobit wire (merged)" + the Toobit Adapter
Contract (APEX_GEN5.md L16846–16900) + Y.2/Y.3 (L17405–17437) + AI.8
(L18747–18812).

Every value in this module is LOADED from the frozen params YAMLs
(``params/toobit_wire_v1.yaml``, ``params/universe_v1.yaml``,
``params/risk_defaults_v1.yaml``) — code never hardcodes a governed value
(§9.5-10, cross-stage invariant). Where the blueprint freezes a rule rather
than a number (the five-operation contract, the side map semantics, the
signing scheme, the unmapped-code law), the rule is implemented here with its
line citation.

Fail-closed discipline (G6/P6): an unmapped symbol, interval, operation,
order type or business code never silently degrades — it raises or maps to
``UNKNOWN`` + ``RECOVERY_REQUIRED`` exactly as Ch.16 L16861–16863 orders.
"""

from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlencode

from apex.config import load_params
from apex.data_catalog.contracts import CORE10_SYMBOLS, TIMEFRAMES_14
from apex.errors import WaveOutError, get_error_code, wave_out

CONTRACT_VERSION = "4.0.0"

# ---------------------------------------------------------------------------
# Frozen wire parameters (params/toobit_wire_v1.yaml — Ch.16 L16872–16900)
# ---------------------------------------------------------------------------

_PARAMS = load_params()
_WIRE: Dict[str, Any] = dict(_PARAMS["toobit_wire"])
_UNIVERSE: Dict[str, Any] = dict(_PARAMS["universe"])
_RISK: Dict[str, Any] = dict(_PARAMS["risk_defaults"])

BASE_URL: str = str(_WIRE["base_url"])                       # L16873
HEADER_API_KEY: str = str(_WIRE["header_api_key"])           # X-BB-APIKEY
RECV_WINDOW_MS: int = int(_WIRE["recv_window_ms"])           # 5000 (L16873)
AUTH_SCHEME: str = str(_WIRE["auth_scheme"])                 # HMAC-SHA256
SYMBOL_MAP: Dict[str, str] = dict(_WIRE["symbol_map"])       # L16877
INTERVAL_MAP: Dict[str, str] = dict(_WIRE["interval_map"])   # 1mo -> 1M
KLINE_LIMIT: int = int(_WIRE["klines_limit"])                # 1000
PUBLIC_ENDPOINTS: Tuple[str, ...] = tuple(_WIRE["public_endpoints"])
SIGNED_ENDPOINTS: Tuple[str, ...] = tuple(_WIRE["signed_wave_in_endpoints"])
BUSINESS_CODES_OK: Tuple[int, ...] = tuple(int(c) for c in _WIRE["business_codes_ok"])
UNKNOWN_OUTCOME_CODES: Tuple[int, ...] = tuple(
    int(c) for c in _WIRE["unknown_outcome_codes"])
ABORT_CODE: int = int(_WIRE["abort_code"])                   # −1022 abort
BACKOFF_CODE: int = int(_WIRE["backoff_code"])               # −1003 backoff 1/2/4s
INTERVAL_UNSUPPORTED_CODE: int = int(_WIRE["interval_unsupported_code"])  # −1120
RETRY_ATTEMPTS: int = int(_WIRE["retry_attempts"])           # 3
RETRY_BACKOFF_SECONDS: Tuple[float, ...] = tuple(
    float(s) for s in _WIRE["retry_backoff_seconds"])        # 1, 2, 4
SIDE_MAP: Dict[str, str] = dict(_WIRE["side_map"])
ORDER_DEFAULTS: Dict[str, Dict[str, str]] = {
    k: dict(v) for k, v in _WIRE["order_defaults"].items()}
FORBIDDEN_OPERATIONS: Tuple[str, ...] = tuple(_WIRE["forbidden_operations"])
FORBIDDEN_ORDER_TYPE: str = str(_WIRE["forbidden_order_type"])   # MARKET
MARGIN_TYPE_VALUE: str = str(_WIRE["margin_type_value"])         # ISOLATED
ROLLOVER_MIN_DAYS: int = int(_WIRE["rollover_min_days"])         # 7 (veto 13)
FUNDING_ALERT_THRESHOLD: float = float(_WIRE["funding_rate_alert_threshold"])
INTERVAL_UNSUPPORTED_HANDLING: str = str(_WIRE["interval_unsupported_handling"])

MARGIN_MODE: str = str(_RISK["margin_mode"])          # ISOLATED (never CROSS)
POSITION_MODE: str = str(_RISK["position_mode"])      # ONE_WAY (never hedge)
LEVERAGE_CAP_BY_TF: Dict[str, int] = {
    str(k): int(v) for k, v in _RISK["system_leverage_cap_by_tf"].items()}

TICK_SIZE: Dict[str, str] = {k: str(v) for k, v in _UNIVERSE["tick_size"].items()}
QUANTITY_STEP: Dict[str, str] = {k: str(v) for k, v in _UNIVERSE["quantity_step"].items()}
MIN_NOTIONAL: Dict[str, str] = {k: str(v) for k, v in _UNIVERSE["min_notional"].items()}
EXCHANGE_MAX_LEVERAGE: Dict[str, int] = {
    str(k): int(v) for k, v in _UNIVERSE["exchange_max_leverage"].items()}


class ToobitMapError(ValueError):
    """Fail-closed wire-map violation (deterministic reason code)."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}" + (f": {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Symbol / interval mapping (Ch.16 L16877; E-VAL-021/022)
# ---------------------------------------------------------------------------

def to_wire_symbol(symbol: str) -> str:
    """Internal ``BTCUSDT``…``LTCUSDT`` → wire ``BTC-SWAP-USDT``…``LTC-SWAP-USDT``.

    A symbol outside Core-10 is ``E-VAL-021`` (fail-closed, never guessed).
    """
    if symbol not in CORE10_SYMBOLS:
        raise ToobitMapError(get_error_code("E-VAL-021").code, str(symbol))
    try:
        return SYMBOL_MAP[symbol]
    except KeyError:  # pragma: no cover - guarded by the frozen YAML test
        raise ToobitMapError("WIRE_SYMBOL_MAP_MISSING", symbol) from None


def to_internal_symbol(wire_symbol: str) -> str:
    """Inverse of :func:`to_wire_symbol` (reconcile responses carry wire names)."""
    for internal, wire in SYMBOL_MAP.items():
        if wire == wire_symbol:
            return internal
    raise ToobitMapError("WIRE_SYMBOL_UNKNOWN", str(wire_symbol))


def to_wire_interval(interval: str) -> str:
    """``1mo`` → ``1M``; every other interval is identical (Ch.16 L16877).

    ``3d`` and any other interval outside the frozen 14 is ``E-VAL-022``.
    """
    if interval not in TIMEFRAMES_14:
        raise ToobitMapError(get_error_code("E-VAL-022").code, str(interval))
    return INTERVAL_MAP.get(interval, interval)


def interval_disabled_record(symbol: str, interval: str,
                             business_code: int) -> Dict[str, Any]:
    """Ch.16 L16877: "If 8h returns −1120, disable **that TF for that symbol
    only**." The record is the deterministic decision; the registry that holds
    it is adapter-owned state (callers may read, never mutate)."""
    if symbol not in CORE10_SYMBOLS:
        raise ToobitMapError(get_error_code("E-VAL-021").code, str(symbol))
    if interval not in TIMEFRAMES_14:
        raise ToobitMapError(get_error_code("E-VAL-022").code, str(interval))
    if int(business_code) != INTERVAL_UNSUPPORTED_CODE:
        raise ToobitMapError("INTERVAL_DISABLE_CODE_MISMATCH",
                             f"{business_code} != {INTERVAL_UNSUPPORTED_CODE}")
    return {
        "symbol": symbol,
        "timeframe": interval,
        "business_code": int(business_code),
        "handling": INTERVAL_UNSUPPORTED_HANDLING,   # DISABLE_TF_FOR_SYMBOL_ONLY
        "scope": "SYMBOL_TIMEFRAME_ONLY",            # never universe-wide
        "universe_cells_remaining": len(CORE10_SYMBOLS) * len(TIMEFRAMES_14) - 1,
    }


# ---------------------------------------------------------------------------
# Endpoint coverage — exactly five operations (Ch.16 L16852–16858)
# ---------------------------------------------------------------------------

#: The adapter maps EXACTLY five exchange operations, each to exactly one
#: exchange endpoint (Ch.16 L16852). A sixth operation does not exist.
FIVE_OPERATIONS: Tuple[str, ...] = (
    "submit_order",
    "cancel_order",
    "query_order_state",
    "query_open_positions",
    "query_account_margin_health",
)

OPERATION_ENDPOINT: Dict[str, Tuple[str, str]] = {
    "submit_order": ("POST", "/api/v1/futures/order"),
    "cancel_order": ("DELETE", "/api/v1/futures/order"),
    "query_order_state": ("GET", "/api/v1/futures/order"),
    "query_open_positions": ("GET", "/api/v1/futures/positions"),
    "query_account_margin_health": ("GET", "/api/v1/futures/balance"),
}

#: Auxiliary wire paths bound to one of the five operations. Ch.16 L16852
#: freezes the OPERATION surface at five; the merged wire block (L16884–16895)
#: freezes the permitted PATH set at eleven signed paths and forbids "any
#: unlisted path". The intersection rule (ISSUE-CP7-002): every auxiliary path
#: is reachable only *inside* one of the five operations — it is never exposed
#: as a sixth operation, and no path outside the wire list is ever requested.
OPERATION_AUXILIARY_PATHS: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "cancel_order": (
        # Ch.21 §5.7 L3 CANCEL_ALL "cancels all open orders (up to 12)";
        # wire list L16887 "cancel-all protective".
        ("DELETE", "/api/v1/futures/batchOrders"),
    ),
    "query_order_state": (
        # Ch.23 RECONCILING: "query the exchange for open positions, working
        # orders, and recent fills" (L18247–18249).
        ("GET", "/api/v1/futures/openOrders"),
        ("GET", "/api/v1/futures/userTrades"),
    ),
    "query_account_margin_health": (
        # wire list L16892–16894: account is ISOLATED/ONE_WAY, leverage is
        # min(Y.2 cap, owner cap, exchange max); commissionRate is stored,
        # never invented ("store; do not invent a fee").
        ("POST", "/api/v1/futures/leverage"),
        ("POST", "/api/v1/futures/marginType"),
        ("GET", "/api/v1/futures/commissionRate"),
    ),
    "submit_order": (),
    "query_open_positions": (),
}


def wire_endpoints() -> Dict[str, Any]:
    """The complete permitted wire surface (read-only view)."""
    return {
        "base_url": BASE_URL,
        "header_api_key": HEADER_API_KEY,
        "recv_window_ms": RECV_WINDOW_MS,
        "auth_scheme": AUTH_SCHEME,
        "public": tuple(PUBLIC_ENDPOINTS),
        "signed_wave_in": tuple(SIGNED_ENDPOINTS),
        "operations": dict(OPERATION_ENDPOINT),
        "auxiliary_paths": {k: tuple(v) for k, v in
                            OPERATION_AUXILIARY_PATHS.items()},
        "forbidden_operations": tuple(FORBIDDEN_OPERATIONS),
        "forbidden_order_type": FORBIDDEN_ORDER_TYPE,
    }


def endpoint_for(operation: str) -> Tuple[str, str]:
    """Exactly one endpoint per operation; unknown/forbidden → fail-closed."""
    if operation in FORBIDDEN_OPERATIONS:
        feature = {
            "withdraw": "withdraw",
            "transfer": "transfer",
            "flashClose": "flash_close",
            "reversePosition": "reverse_position",
        }.get(operation, operation)
        raise wave_out(feature, "TOOBIT_WIRE_FORBIDDEN_OPERATION")
    if operation not in FIVE_OPERATIONS:
        raise ToobitMapError("ADAPTER_OPERATION_UNKNOWN", str(operation))
    return OPERATION_ENDPOINT[operation]


def assert_path_permitted(method: str, path: str) -> None:
    """No unlisted path is ever requested (Ch.16 L16895: forbidden = "any
    unlisted path"). Public + signed Wave-In lists only."""
    token = f"{method.upper()} {path}"
    if token in PUBLIC_ENDPOINTS or token in SIGNED_ENDPOINTS:
        return
    raise ToobitMapError("TOOBIT_PATH_NOT_LISTED", token)


def auxiliary_paths_for(operation: str) -> Tuple[Tuple[str, str], ...]:
    if operation not in FIVE_OPERATIONS:
        raise ToobitMapError("ADAPTER_OPERATION_UNKNOWN", str(operation))
    return tuple(OPERATION_AUXILIARY_PATHS[operation])


# ---------------------------------------------------------------------------
# Side map + order defaults (Ch.16 L16897 ONE_WAY; L16800–16812 order table)
# ---------------------------------------------------------------------------

SIDES: FrozenSet[str] = frozenset({"BUY_OPEN", "SELL_OPEN", "SELL_CLOSE", "BUY_CLOSE"})


def side_for(direction: str, phase: str) -> str:
    """ONE_WAY side map (Ch.16 L16897): LONG entry ``BUY_OPEN``; SHORT entry
    ``SELL_OPEN``; LONG flatten ``SELL_CLOSE``; SHORT flatten ``BUY_CLOSE``.

    ``direction`` ∈ {LONG, SHORT}; ``phase`` ∈ {entry, flatten}. Hedge mode and
    CROSS margin are Wave-Out (§9.5-9) and cannot be expressed here.
    """
    key = f"{direction}_{phase}"
    try:
        return SIDE_MAP[key]
    except KeyError:
        raise ToobitMapError("SIDE_MAP_QX", key) from None


def order_defaults(kind: str) -> Dict[str, str]:
    """Governed order-type/TIF defaults (Ch.16 L16800–16812).

    entry → LIMIT/IOC/priceType INPUT (partial fill permitted); stop → STOP +
    priceType MARKET; target → LIMIT/GTC. ``type=MARKET`` is forbidden
    (L16895) — the aggressive flatten after IOC-0 is LIMIT + priceType MARKET
    (L16899), which is a *price type*, never an order type.
    """
    if kind == "aggressive_flatten":
        return {"type": "LIMIT", "price_type": "MARKET", "tif": "IOC"}
    try:
        return dict(ORDER_DEFAULTS[kind])
    except KeyError:
        raise ToobitMapError("ORDER_KIND_QX", str(kind)) from None


def assert_order_type_permited(order_type: str) -> None:
    if str(order_type).upper() == FORBIDDEN_ORDER_TYPE:
        raise ToobitMapError("ORDER_TYPE_FORBIDDEN",
                             f"type={FORBIDDEN_ORDER_TYPE} (Ch.16 L16895)")


def assert_account_mode(margin_mode: str, position_mode: str) -> None:
    """Account is ISOLATED, ONE_WAY (Ch.16 L16900). CROSS margin and hedge
    mode are Wave-Out (§9.5-9)."""
    if str(margin_mode).upper() != MARGIN_MODE:
        raise wave_out("cross_margin", f"margin_mode={margin_mode}")
    if str(position_mode).upper() != POSITION_MODE:
        raise wave_out("hedge_mode", f"position_mode={position_mode}")


# ---------------------------------------------------------------------------
# Business-code classification (Ch.16 L16898 + adapter error mapping L16861)
# ---------------------------------------------------------------------------

#: Deterministic classification of an exchange business code.
#: ``OK`` · ``UNKNOWN`` (reconcile, NO resubmit) · ``ABORT`` · ``BACKOFF`` ·
#: ``INTERVAL_UNSUPPORTED`` · ``UNMAPPED`` (→ UNKNOWN + RECOVERY_REQUIRED).
CODE_OK = "OK"
CODE_UNKNOWN = "UNKNOWN"
CODE_ABORT = "ABORT"
CODE_BACKOFF = "BACKOFF"
CODE_INTERVAL_UNSUPPORTED = "INTERVAL_UNSUPPORTED"
CODE_UNMAPPED = "UNMAPPED"

#: Codes the stage prompt names that the frozen blueprint does NOT define
#: (ISSUE-CP7-001): −1021 and −2026 appear nowhere in APEX_GEN5.md. Ch.16
#: L16861–16863 orders "unmapped codes map to UNKNOWN + RECOVERY_REQUIRED", so
#: they are handled by that law — never by invented semantics.
UNDOCUMENTED_CODES: Tuple[int, ...] = (-1021, -2026)


def classify_business_code(code: Optional[int], *,
                           http_status: Optional[int] = None,
                           timeout: bool = False) -> Dict[str, Any]:
    """Map one exchange outcome to exactly one classification + FSM effect.

    Ch.16 L16898: success = HTTP 200 AND business code ∈ {0, 200};
    timeout/−1006/−1007/−1146/−1147 → UNKNOWN, reconcile, **no resubmit**;
    −1022 abort; −1003 backoff 1/2/4 s. L16877: −1120 disables that TF for
    that symbol only. L16861–16863: unmapped codes → UNKNOWN +
    RECOVERY_REQUIRED.
    """
    if timeout:
        return {"classification": CODE_UNKNOWN, "business_code": None,
                "fsm_effect": "RECOVERY_REQUIRED", "resubmit": False,
                "reconcile": True, "backoff_seconds": None,
                "rule": "Ch.16 L16898 timeout → UNKNOWN, reconcile, no resubmit"}
    if code is None:
        return {"classification": CODE_UNMAPPED, "business_code": None,
                "fsm_effect": "RECOVERY_REQUIRED", "resubmit": False,
                "reconcile": True, "backoff_seconds": None,
                "rule": "Ch.16 L16861–16863 unmapped → UNKNOWN + RECOVERY_REQUIRED"}
    c = int(code)
    if http_status is not None and int(http_status) != 200 and c in BUSINESS_CODES_OK:
        # "Success HTTP 200 and business code in {0,200}" — both must hold.
        return {"classification": CODE_UNKNOWN, "business_code": c,
                "fsm_effect": "RECOVERY_REQUIRED", "resubmit": False,
                "reconcile": True, "backoff_seconds": None,
                "rule": f"Ch.16 L16898 http_status={http_status} ≠ 200"}
    if c in BUSINESS_CODES_OK:
        return {"classification": CODE_OK, "business_code": c,
                "fsm_effect": "ACKNOWLEDGED", "resubmit": False,
                "reconcile": False, "backoff_seconds": None,
                "rule": "Ch.16 L16898 success = HTTP 200 + code ∈ {0,200}"}
    if c == INTERVAL_UNSUPPORTED_CODE:
        return {"classification": CODE_INTERVAL_UNSUPPORTED, "business_code": c,
                "fsm_effect": "REJECTED", "resubmit": False,
                "reconcile": False, "backoff_seconds": None,
                "rule": "Ch.16 L16877 −1120 → disable that TF for that symbol only"}
    if c == ABORT_CODE:
        return {"classification": CODE_ABORT, "business_code": c,
                "fsm_effect": "REJECTED", "resubmit": False,
                "reconcile": False, "backoff_seconds": None,
                "rule": "Ch.16 L16898 −1022 abort (no retry)"}
    if c == BACKOFF_CODE:
        return {"classification": CODE_BACKOFF, "business_code": c,
                "fsm_effect": "SUBMITTING", "resubmit": True,
                "reconcile": False, "backoff_seconds": list(RETRY_BACKOFF_SECONDS),
                "rule": "Ch.16 L16898 −1003 backoff 1/2/4s"}
    if c in UNKNOWN_OUTCOME_CODES:
        return {"classification": CODE_UNKNOWN, "business_code": c,
                "fsm_effect": "RECOVERY_REQUIRED", "resubmit": False,
                "reconcile": True, "backoff_seconds": None,
                "rule": "Ch.16 L16898 −1006/−1007/−1146/−1147 → UNKNOWN, "
                        "reconcile, no resubmit"}
    return {"classification": CODE_UNMAPPED, "business_code": c,
            "fsm_effect": "RECOVERY_REQUIRED", "resubmit": False,
            "reconcile": True, "backoff_seconds": None,
            "documented_in_blueprint": False,
            "rule": "Ch.16 L16861–16863 unmapped → UNKNOWN + RECOVERY_REQUIRED"}


#: Exchange order-status literals → exactly one adapter outcome class
#: (Ch.16 L16858–16860: acceptance → ACKNOWLEDGED; every terminal or
#: unexpected response → exactly one of REJECTED / CANCELLED / UNKNOWN).
EXCHANGE_STATUS_MAP: Dict[str, str] = {
    "NEW": "ACKNOWLEDGED",
    "PARTIALLY_FILLED": "PARTIAL",
    "FILLED": "FILLED",
    "CANCELED": "CANCELLED",
    "CANCELLED": "CANCELLED",
    "REJECTED": "REJECTED",
    "EXPIRED": "UNKNOWN",
    "PENDING_CANCEL": "UNKNOWN",
    "PARTIALLY_CANCELED": "UNKNOWN",
}

ADAPTER_OUTCOMES: FrozenSet[str] = frozenset(
    {"ACKNOWLEDGED", "PARTIAL", "FILLED", "REJECTED", "CANCELLED", "UNKNOWN"})


def exchange_status_to_outcome(status: Optional[str]) -> Dict[str, Any]:
    """Map an exchange status literal; anything unexpected → UNKNOWN, which
    always leads to reconcile-before-action, never to blind retry."""
    if status is None:
        return {"outcome": "UNKNOWN", "reconcile_before_action": True,
                "rule": "Ch.16 L16858–16860 unexpected → UNKNOWN"}
    key = str(status).upper()
    outcome = EXCHANGE_STATUS_MAP.get(key, "UNKNOWN")
    return {"outcome": outcome,
            "reconcile_before_action": outcome == "UNKNOWN",
            "mapped_from": key,
            "rule": "Ch.16 L16858–16860"}


# ---------------------------------------------------------------------------
# Leverage — min over ALL caps, never last-writer (Ch.16 L16900; Y.2 L17405)
# ---------------------------------------------------------------------------

def resolve_leverage(timeframe: str, *,
                     owner_cap: Optional[float] = None,
                     exchange_max: Optional[float] = None,
                     symbol: Optional[str] = None) -> Dict[str, Any]:
    """``min(Y.2 TF cap, owner cap, exchange max)`` — computed over ALL caps at
    once (T_MONOTONE): the result is permutation-invariant and can only fall
    when a cap tightens. "Never send 125x" (Ch.16 L16900) is a consequence: the
    exchange maximum is a *filter*, never a permission (Y.2 L17359).

    The owner may only LOWER a ceiling (Y.2 L17407–17411); an owner cap above
    the declared TF maximum is therefore clamped, never honoured.
    """
    if timeframe not in TIMEFRAMES_14:
        raise ToobitMapError(get_error_code("E-VAL-022").code, str(timeframe))
    system_cap = float(LEVERAGE_CAP_BY_TF[timeframe])
    caps: Dict[str, float] = {"y2_tf_cap": system_cap}
    if symbol is not None:
        if symbol not in CORE10_SYMBOLS:
            raise ToobitMapError(get_error_code("E-VAL-021").code, str(symbol))
        caps["exchange_max"] = float(
            exchange_max if exchange_max is not None
            else EXCHANGE_MAX_LEVERAGE[symbol])
    elif exchange_max is not None:
        caps["exchange_max"] = float(exchange_max)
    if owner_cap is not None:
        if float(owner_cap) <= 0:
            raise ToobitMapError("OWNER_CAP_NON_POSITIVE", str(owner_cap))
        caps["owner_cap"] = float(owner_cap)
    resolved = min(caps.values())          # ALL caps, single min — never a
    applied = dict(caps)                   # sequential last-writer override
    return {
        "leverage": resolved,
        "caps": applied,
        "binding_cap": min(applied, key=lambda k: (applied[k], k)),
        "monotone": True,
        "never_send_125x": resolved < 125.0,
        "rule": "Ch.16 L16900 min(Y.2 TF cap, owner cap, exchange max); Y.2 "
                "L17405 owner may lower only",
    }


# ---------------------------------------------------------------------------
# Quantity / price lattice (Y.3 L17425–17431; Ch.16 L16880 live filters win)
# ---------------------------------------------------------------------------

def quantize_price(symbol: str, price: Any, *,
                   tick_size: Optional[Any] = None) -> Decimal:
    """Round DOWN onto the price lattice (never a better-looking price).

    ``tick_size`` may be supplied from the live ``exchangeInfo`` filters:
    "live filters win vs the Trading Universe for quantization" (Ch.16 L16880).
    """
    if symbol not in CORE10_SYMBOLS:
        raise ToobitMapError(get_error_code("E-VAL-021").code, str(symbol))
    step = Decimal(str(tick_size if tick_size is not None else TICK_SIZE[symbol]))
    if step <= 0:
        raise ToobitMapError("TICK_SIZE_NON_POSITIVE", str(step))
    value = Decimal(str(price))
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def quantize_quantity(symbol: str, quantity: Any, *,
                      quantity_step: Optional[Any] = None) -> Decimal:
    """Floor onto ``quantity_step`` (Y.3 L17425: the minimum permitted increment
    of order quantity; ``LOT_SIZE`` is adapter metadata only, never a Forex
    100,000-unit convention — Y.4 L17447)."""
    if symbol not in CORE10_SYMBOLS:
        raise ToobitMapError(get_error_code("E-VAL-021").code, str(symbol))
    step = Decimal(str(quantity_step if quantity_step is not None
                      else QUANTITY_STEP[symbol]))
    if step <= 0:
        raise ToobitMapError("QUANTITY_STEP_NON_POSITIVE", str(step))
    value = Decimal(str(quantity))
    if value < 0:
        raise ToobitMapError("QUANTITY_NEGATIVE", str(quantity))
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def check_min_notional(symbol: str, price: Any, quantity: Any,
                       *, min_notional: Optional[Any] = None) -> Dict[str, Any]:
    """``min_notional`` filter (Ch.5 Trading Universe; live filters win)."""
    if symbol not in CORE10_SYMBOLS:
        raise ToobitMapError(get_error_code("E-VAL-021").code, str(symbol))
    floor = Decimal(str(min_notional if min_notional is not None
                        else MIN_NOTIONAL[symbol]))
    notional = Decimal(str(price)) * Decimal(str(quantity))
    ok = notional >= floor
    return {"symbol": symbol, "notional": str(notional), "min_notional": str(floor),
            "passes": ok,
            "reason": None if ok else "MIN_NOTIONAL_QX"}


# ---------------------------------------------------------------------------
# Signing + idempotency (Ch.16 L16873, L16786–16798; AI.8 L18753)
# ---------------------------------------------------------------------------

def sign_query(secret: str, query_string: str) -> str:
    """HMAC-SHA256 over the query string (Ch.16 L16873). The secret never
    leaves this function's scope and is never logged (G16/§9.5-13)."""
    if not secret:
        raise ToobitMapError("SIGNING_SECRET_MISSING",
                             "TOOBIT_API_SECRET is empty (env only, §9.5-12)")
    return hmac.new(secret.encode("utf-8"), query_string.encode("utf-8"),
                    hashlib.sha256).hexdigest()


def build_signed_query(params: Mapping[str, Any], *, timestamp_ms: int,
                       recv_window: int = RECV_WINDOW_MS) -> str:
    """Deterministic query string: the caller's parameters plus ``timestamp``
    and ``recvWindow`` (5000), URL-encoded in insertion order."""
    items: List[Tuple[str, Any]] = [(k, v) for k, v in params.items()]
    items.append(("timestamp", int(timestamp_ms)))
    items.append(("recvWindow", int(recv_window)))
    return urlencode(items)


def signed_request(method: str, path: str, params: Mapping[str, Any], *,
                   api_key: str, api_secret: str,
                   timestamp_ms: int) -> Dict[str, Any]:
    """Build one signed request descriptor (no I/O here).

    Header ``X-BB-APIKEY``; ``recvWindow`` 5000; HMAC-SHA256 over the query
    string, appended as ``signature`` (Ch.16 L16873). The descriptor never
    contains the secret (G16: secrets never in exception strings or logs).
    """
    assert_path_permitted(method, path)
    query = build_signed_query(params, timestamp_ms=timestamp_ms)
    signature = sign_query(api_secret, query)
    return {
        "method": method.upper(),
        "url": f"{BASE_URL}{path}",
        "query": f"{query}&signature={signature}",
        "headers": {HEADER_API_KEY: api_key, "Content-Type":
                    "application/x-www-form-urlencoded"},
        "signature": signature,
        "recv_window_ms": RECV_WINDOW_MS,
        "auth_scheme": AUTH_SCHEME,
    }


def execution_idempotency_key(intent_id: str, order_id: Optional[str],
                              timestamp_utc: str, nonce: str) -> str:
    """Ch.16 L16793: ``idempotency_key = SHA-256(intent_id || order_id ||
    timestamp_UTC || nonce)`` with a governed TTL; a repeated key returns the
    previously recorded response and never resubmits (L16796–16798).

    AI.8 L18753 fixes the order-submission TTL at 60 s and the ledger-write key
    at ``event_id`` (permanent).
    """
    if not intent_id:
        raise ToobitMapError("INTENT_ID_REQUIRED",
                             "no order may be submitted without a client order id")
    joined = "||".join([str(intent_id), str(order_id or ""), str(timestamp_utc),
                        str(nonce)])
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


ORDER_SUBMISSION_TTL_SECONDS = 60        # AI.8 L18753
POSITION_TRANSITION_TTL_SECONDS = 30     # AI.8 L18755
TELEGRAM_IDEMPOTENCY_TTL_SECONDS = 86400  # Ch.21 §10 (24 h)


def retry_policy() -> Dict[str, Any]:
    """Governed retry: 3 attempts, exponential backoff 1/2/4 s, a UNIQUE key
    per attempt (Ch.16 L16806). Retries are never silent: every attempt is
    audited (AI.8 L18806–18810) and an UNKNOWN outcome is never resubmitted."""
    return {"attempts": RETRY_ATTEMPTS,
            "backoff_seconds": list(RETRY_BACKOFF_SECONDS),
            "unique_key_per_attempt": True,
            "silent": False,
            "never_resubmit_on": (CODE_UNKNOWN, CODE_UNMAPPED, CODE_ABORT)}


def rollover_entry_allowed(days_to_expiry: Optional[float]) -> Dict[str, Any]:
    """Ch.16 L16903–16910: no new entry when time-to-expiry < the governed
    threshold (default 7 days, veto 13 ``CONTRACT_EXPIRY``). Perpetuals carry
    no expiry ⇒ always allowed (funding-rate monitoring is separate and is an
    alert only, never a 15th veto — Ch.16 L16883)."""
    if days_to_expiry is None:
        return {"allowed": True, "reason": "PERPETUAL_NO_EXPIRY",
                "threshold_days": ROLLOVER_MIN_DAYS}
    allowed = float(days_to_expiry) >= float(ROLLOVER_MIN_DAYS)
    return {"allowed": allowed,
            "reason": None if allowed else "CONTRACT_EXPIRY",
            "veto": None if allowed else 13,
            "days_to_expiry": float(days_to_expiry),
            "threshold_days": ROLLOVER_MIN_DAYS,
            "roll_requires": "new trade plan with a new idempotency key"}


def funding_alert(rate: Optional[float]) -> Dict[str, Any]:
    """Ch.16 L16883: alert only if |rate| ≥ 0.001; NOT a 15th veto."""
    if rate is None:
        return {"alert": False, "reason": "FUNDING_RATE_MISSING"}
    fired = abs(float(rate)) >= FUNDING_ALERT_THRESHOLD
    return {"alert": fired, "rate": float(rate),
            "threshold": FUNDING_ALERT_THRESHOLD,
            "is_veto": False,
            "cost_model_effect": "extreme funding emits a cost alert into the "
                                 "Decision Engine's cost model" if fired else None}


__all__ = [
    "ABORT_CODE", "ADAPTER_OUTCOMES", "AUTH_SCHEME", "BACKOFF_CODE",
    "BASE_URL", "BUSINESS_CODES_OK", "CONTRACT_VERSION", "EXCHANGE_MAX_LEVERAGE",
    "EXCHANGE_STATUS_MAP", "FIVE_OPERATIONS", "FORBIDDEN_OPERATIONS",
    "FORBIDDEN_ORDER_TYPE", "FUNDING_ALERT_THRESHOLD", "HEADER_API_KEY",
    "INTERVAL_MAP", "INTERVAL_UNSUPPORTED_CODE", "KLINE_LIMIT",
    "LEVERAGE_CAP_BY_TF", "MARGIN_MODE", "MARGIN_TYPE_VALUE", "MIN_NOTIONAL",
    "OPERATION_AUXILIARY_PATHS", "OPERATION_ENDPOINT", "ORDER_DEFAULTS",
    "ORDER_SUBMISSION_TTL_SECONDS", "POSITION_MODE", "POSITION_TRANSITION_TTL_SECONDS",
    "PUBLIC_ENDPOINTS", "QUANTITY_STEP", "RECV_WINDOW_MS", "RETRY_ATTEMPTS",
    "RETRY_BACKOFF_SECONDS", "ROLLOVER_MIN_DAYS", "SIDES", "SIDE_MAP",
    "SIGNED_ENDPOINTS", "SYMBOL_MAP", "TELEGRAM_IDEMPOTENCY_TTL_SECONDS",
    "TICK_SIZE", "ToobitMapError", "UNDOCUMENTED_CODES", "UNKNOWN_OUTCOME_CODES",
    "assert_account_mode", "assert_order_type_permited", "assert_path_permitted",
    "auxiliary_paths_for", "build_signed_query", "check_min_notional",
    "classify_business_code", "endpoint_for", "exchange_status_to_outcome",
    "execution_idempotency_key", "funding_alert", "interval_disabled_record",
    "order_defaults", "quantize_price", "quantize_quantity", "resolve_leverage",
    "retry_policy", "rollover_entry_allowed", "side_for", "sign_query",
    "signed_request", "to_internal_symbol", "to_wire_interval", "to_wire_symbol",
    "wire_endpoints",
]
