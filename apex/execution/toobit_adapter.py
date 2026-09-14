"""Toobit venue adapter — Ch.16 "Toobit Adapter Contract (normative)"
(APEX_GEN5.md L16846–16870) + the merged wire block (L16872–16900) + AI.8
idempotency/rate-limit contract (L18747–18812).

Exactly FIVE exchange operations exist (Ch.16 L16852): submit order, cancel
order, query order state, query open positions, query account/margin health —
each mapped to exactly one exchange endpoint by ``apex.execution.toobit_map``.
A sixth operation raises; a forbidden operation (withdraw / transfer /
flashClose / reversePosition / auto_add_margin) raises ``WaveOutError``
(§9.5-9); an unlisted path raises.

No silent retries: every attempt carries a unique idempotency key, is written
to the immutable audit trail, and retries happen ONLY for the governed backoff
class (−1003 / transient transport fault) — 3 attempts, 1/2/4 s (Ch.16 L16806,
L16898). An UNKNOWN or unmapped outcome NEVER resubmits: it forces
reconcile-before-action (Ch.16 L16860, AI.8 L18779–18790).

Adapter-owned state (token buckets, audit trail, duplicate registry, disabled
interval registry) is READ-ONLY to callers: views are frozen, and any attempt
to mutate adapter state from outside raises ``AdapterStateMutationError``.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import (Any, Awaitable, Callable, Dict, List, Mapping, Optional,
                    Sequence, Tuple)

from apex.config import Config
from apex.errors import WaveOutError
from apex.execution.toobit_map import (
    BASE_URL,
    CODE_ABORT,
    CODE_BACKOFF,
    CODE_INTERVAL_UNSUPPORTED,
    CODE_OK,
    CODE_UNKNOWN,
    CODE_UNMAPPED,
    FIVE_OPERATIONS,
    INTERVAL_UNSUPPORTED_CODE,
    RETRY_ATTEMPTS,
    RETRY_BACKOFF_SECONDS,
    ToobitMapError,
    assert_account_mode,
    assert_order_type_permited,
    check_min_notional,
    classify_business_code,
    endpoint_for,
    exchange_status_to_outcome,
    execution_idempotency_key,
    interval_disabled_record,
    order_defaults,
    quantize_price,
    quantize_quantity,
    resolve_leverage,
    side_for,
    signed_request,
    to_wire_symbol,
)
from apex.identity.uuid_v7 import uuid_v7

CONTRACT_VERSION = "4.0.0"

# ---------------------------------------------------------------------------
# Governed adapter parameters. AI.8 L18772–18774 (Toobit: 1000 requests per
# 10 s = 100 req/s average; burst capacity 200 requests in 1 s) and Ch.17
# L17010–17011 (submission_timeout 5 s, fill_timeout 5 s — dynamic/governed).
# These values have no home in the six frozen params YAMLs and CP-7's WRITE SET
# excludes params/*.yaml (PHASE2_CHECKPOINTS §CP-7); they are frozen here
# verbatim from their blueprint lines and asserted literal-by-literal by
# tests/unit/test_toobit_adapter.py (ISSUE-CP7-003).
# ---------------------------------------------------------------------------
TOOBIT_BUCKET_CAPACITY = 200               # AI.8 burst capacity
TOOBIT_BUCKET_REFILL_PER_SECOND = 100.0    # AI.8 1000 requests / 10 s
SUBMISSION_TIMEOUT_SECONDS = 5.0           # Ch.17 governed default
FILL_TIMEOUT_SECONDS = 5.0                 # Ch.17 governed default
RATE_LIMIT_QUEUE_TIMEOUT_SECONDS = 5.0     # bounded queueing (AI.8 L18775)

#: Documented response envelope (Ch.16 L16856: "Endpoint paths, parameter
#: names, and response fields are recorded in the adapter's conformance
#: fixtures"). A response without a recognizable business code is UNMAPPED →
#: UNKNOWN + RECOVERY_REQUIRED — never guessed.
BUSINESS_CODE_FIELDS: Tuple[str, ...] = ("code", "retCode")
DATA_FIELD = "data"


class AdapterError(RuntimeError):
    """Fail-closed adapter violation with a deterministic reason code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}" + (f": {detail}" if detail else ""))


class AdapterStateMutationError(AdapterError):
    """Raised when a caller attempts to mutate adapter-owned state."""


class AdapterTimeout(AdapterError):
    """Submission timeout (Ch.16 L16867–16868): forces RECOVERY_REQUIRED
    (E-EXEC-001) — never a blind resubmit."""

    def __init__(self, detail: str = "") -> None:
        super().__init__("SUBMISSION_TIMEOUT", detail)


# ---------------------------------------------------------------------------
# Frozen records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TokenBucketState:
    endpoint: str
    capacity: float
    tokens: float
    refill_per_second: float
    last_refill: float
    queued: int


@dataclass(frozen=True)
class AttemptRecord:
    """One audited attempt (AI.8 L18806: every retry, deduplication or cache
    hit is logged with timestamp, key, result_source and actor)."""
    attempt_no: int
    operation: str
    endpoint: str
    idempotency_key: str
    timestamp_utc: str
    classification: str
    business_code: Optional[int]
    http_status: Optional[int]
    result_source: str        # TRANSPORT | CACHE | RATE_LIMIT | REFUSED
    actor: str
    outcome: str
    error: Optional[str] = None


@dataclass(frozen=True)
class AdapterResult:
    """Immutable result of one adapter operation."""
    operation: str
    endpoint: str
    ok: bool
    classification: str
    outcome: str      # ACKNOWLEDGED|PARTIAL|FILLED|REJECTED|CANCELLED|UNKNOWN
    business_code: Optional[int]
    http_status: Optional[int]
    data: Mapping[str, Any]
    client_order_id: Optional[str]
    order_id: Optional[str]
    idempotency_key: str
    reconcile_required: bool
    resubmitted: bool
    cached: bool
    interval_disabled: Optional[Mapping[str, Any]]
    attempts: Tuple[AttemptRecord, ...]
    error_code: Optional[str]
    rule: str
    contract_version: str = CONTRACT_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation, "endpoint": self.endpoint,
            "ok": self.ok, "classification": self.classification,
            "outcome": self.outcome, "business_code": self.business_code,
            "http_status": self.http_status, "data": dict(self.data),
            "client_order_id": self.client_order_id, "order_id": self.order_id,
            "idempotency_key": self.idempotency_key,
            "reconcile_required": self.reconcile_required,
            "resubmitted": self.resubmitted, "cached": self.cached,
            "interval_disabled": (dict(self.interval_disabled)
                                  if self.interval_disabled else None),
            "attempts": [dict(a.__dict__) for a in self.attempts],
            "error_code": self.error_code, "rule": self.rule,
            "contract_version": self.contract_version,
        }


@dataclass(frozen=True)
class AdapterState:
    """Read-only snapshot of adapter-owned state (callers may never mutate)."""
    buckets: Mapping[str, TokenBucketState]
    disabled_intervals: Mapping[str, Tuple[str, ...]]
    known_client_order_ids: Tuple[str, ...]
    audit_entries: int
    signed_allowed: bool
    environment: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "buckets", MappingProxyType(dict(self.buckets)))
        object.__setattr__(
            self, "disabled_intervals",
            MappingProxyType({k: tuple(v) for k, v in
                              self.disabled_intervals.items()}))
        object.__setattr__(self, "known_client_order_ids",
                           tuple(self.known_client_order_ids))


# ---------------------------------------------------------------------------
# Token bucket per endpoint (sliding window, AI.8 L18775)
# ---------------------------------------------------------------------------

class _TokenBucket:
    def __init__(self, endpoint: str, capacity: float, refill_per_second: float,
                 clock: Callable[[], float]) -> None:
        self.endpoint = endpoint
        self.capacity = float(capacity)
        self.refill_per_second = float(refill_per_second)
        self._clock = clock
        self._tokens = float(capacity)
        self._last = float(clock())
        self._queued = 0
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = float(self._clock())
        elapsed = max(0.0, now - self._last)
        self._tokens = min(self.capacity,
                           self._tokens + elapsed * self.refill_per_second)
        self._last = now

    async def acquire(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Consume one token; if the bucket is empty the request is QUEUED
        (never dropped — AI.8 L18775) until a token refills or the bounded wait
        expires. A token is only ever consumed when the refill actually
        produced one: an exhausted bucket never hands out a negative token."""
        bound = (RATE_LIMIT_QUEUE_TIMEOUT_SECONDS if timeout is None
                 else float(timeout))
        async with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return {"acquired": True, "queued": False, "tokens": self._tokens}
            self._queued += 1
            deadline = time.monotonic() + bound
            try:
                while True:
                    wait = (1.0 - self._tokens) / self.refill_per_second
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return {"acquired": False, "queued": True,
                                "reason": "RATE_LIMIT_QUEUE_TIMEOUT",
                                "wait_seconds": wait, "bound_seconds": bound}
                    await asyncio.sleep(min(wait, remaining))
                    self._refill()
                    if self._tokens >= 1.0:
                        self._tokens -= 1.0
                        return {"acquired": True, "queued": True,
                                "tokens": self._tokens,
                                "waited_seconds": bound - remaining}
            finally:
                self._queued -= 1

    def snapshot(self) -> TokenBucketState:
        self._refill()
        return TokenBucketState(endpoint=self.endpoint, capacity=self.capacity,
                                tokens=self._tokens,
                                refill_per_second=self.refill_per_second,
                                last_refill=self._last, queued=self._queued)


# ---------------------------------------------------------------------------
# Transport seam: production = aiohttp; tests inject a fake Toobit responder
# (a test double — lawful only behind test code, G9).
# ---------------------------------------------------------------------------

Transport = Callable[[str, str, str, Dict[str, str]], Awaitable[Dict[str, Any]]]


def aiohttp_transport(session: Any, *,
                      timeout: float = SUBMISSION_TIMEOUT_SECONDS) -> Transport:
    """Real transport (production path). A timeout raises
    :class:`AdapterTimeout` → UNKNOWN, reconcile, NO resubmit."""
    async def _call(method: str, url: str, query: str,
                    headers: Dict[str, str]) -> Dict[str, Any]:
        if session is None:
            raise AdapterError("TRANSPORT_SESSION_MISSING",
                               "no aiohttp session was supplied (fail-closed)")
        import json as _json
        target = f"{url}?{query}" if query else url
        try:
            async with session.request(
                    method, target, headers=headers,
                    timeout=aiohttp_timeout(session, timeout)) as resp:
                text = await resp.text()
                try:
                    body = _json.loads(text) if text else {}
                except ValueError:
                    body = {"raw": text}
                return {"http_status": int(resp.status), "body": body}
        except asyncio.TimeoutError as exc:
            raise AdapterTimeout(f"{method} {url}") from exc
    return _call


def aiohttp_timeout(session: Any, default: float) -> Any:
    """``aiohttp.ClientTimeout`` for the governed submission timeout."""
    import aiohttp
    return aiohttp.ClientTimeout(total=default)


# ---------------------------------------------------------------------------
# The adapter
# ---------------------------------------------------------------------------

_STATE_ATTRS = frozenset({"_buckets", "_audit", "_duplicates", "_disabled",
                          "_config", "_clock", "_utc_now", "_transport"})


class ToobitAdapter:
    """Exactly five operations; no silent retries; duplicate/lost-ack
    semantics per AI.3/AI.8; adapter-owned state immutable to callers."""

    OPERATIONS: Tuple[str, ...] = FIVE_OPERATIONS

    def __init__(self, *, config: Optional[Config] = None,
                 transport: Optional[Transport] = None,
                 session: Any = None,
                 clock: Optional[Callable[[], float]] = None,
                 utc_now: Optional[Callable[[], str]] = None,
                 actor: str = "EXECUTION_ADAPTER") -> None:
        object.__setattr__(self, "_initialized", False)
        self._config = config if config is not None else Config()
        self._clock = clock if clock is not None else time.time
        self._utc_now = utc_now if utc_now is not None else system_utc_ms
        self._actor = actor
        if transport is not None:
            self._transport: Transport = transport
        else:
            self._transport = aiohttp_transport(session)
        self._buckets: Dict[str, _TokenBucket] = {}
        self._audit: List[AttemptRecord] = []
        self._duplicates: Dict[str, AdapterResult] = {}
        self._disabled: Dict[str, List[str]] = {}
        object.__setattr__(self, "_initialized", True)

    # -- state protection ---------------------------------------------------
    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_initialized", False) and name in _STATE_ATTRS:
            raise AdapterStateMutationError(
                "ADAPTER_STATE_IMMUTABLE",
                f"{name} is adapter-owned state — callers may read it through "
                "the frozen views, never mutate it (Ch.16 L16846: the execution "
                "state machine is the only path to Toobit)")
        object.__setattr__(self, name, value)

    @property
    def state(self) -> AdapterState:
        return AdapterState(
            buckets={k: b.snapshot() for k, b in self._buckets.items()},
            disabled_intervals={k: tuple(v) for k, v in self._disabled.items()},
            known_client_order_ids=tuple(self._duplicates),
            audit_entries=len(self._audit),
            signed_allowed=bool(self._config.allow_signed),
            environment=self._config.apex_env,
        )

    def audit_trail(self) -> Tuple[AttemptRecord, ...]:
        """Immutable audit trail (AI.8 L18806–18810)."""
        return tuple(self._audit)

    def disabled_intervals(self) -> Mapping[str, Tuple[str, ...]]:
        return MappingProxyType({k: tuple(v) for k, v in self._disabled.items()})

    def is_interval_disabled(self, symbol: str, timeframe: str) -> bool:
        """Ch.16 L16877: −1120 disables that TF for that symbol ONLY."""
        return timeframe in tuple(self._disabled.get(symbol, ()))

    def rate_bucket_state(self, endpoint: str) -> TokenBucketState:
        return self._bucket(endpoint).snapshot()

    # -- rate limiting ------------------------------------------------------
    def _bucket(self, endpoint: str) -> _TokenBucket:
        if endpoint not in self._buckets:
            self._buckets[endpoint] = _TokenBucket(
                endpoint, TOOBIT_BUCKET_CAPACITY,
                TOOBIT_BUCKET_REFILL_PER_SECOND, self._clock)
        return self._buckets[endpoint]

    # -- signed gating ------------------------------------------------------
    def _credentials(self) -> Tuple[str, str]:
        key = self._config.toobit_api_key
        secret = self._config.toobit_api_secret
        if not self._config.allow_signed:
            raise AdapterError(
                "SIGNED_NOT_ALLOWED",
                "APEX_ALLOW_SIGNED=0 — signed endpoints are refused fail-closed "
                "(§9.5-12); never silently downgraded")
        if not key or not secret:
            raise AdapterError(
                "TOOBIT_CREDENTIALS_MISSING",
                "TOOBIT_API_KEY / TOOBIT_API_SECRET are env-only (§9.5-12/13)")
        return key, secret

    # -- OPERATION 1/5 ------------------------------------------------------
    async def submit_order(self, *, intent_id: str, symbol: str,
                           timeframe: str, direction: str, quantity: Any,
                           price: Any, phase: str = "entry", kind: str = "entry",
                           order_type: Optional[str] = None,
                           reduce_only: bool = False,
                           leverage: Optional[float] = None,
                           owner_leverage_cap: Optional[float] = None,
                           extra_params: Optional[Mapping[str, Any]] = None,
                           timestamp_utc: Optional[str] = None,
                           nonce: Optional[str] = None) -> AdapterResult:
        """submit order → ``POST /api/v1/futures/order``.

        ``intent_id`` (UUIDv7) is sent as ``clientOrderId``; no order may be
        submitted without one (Ch.16 L16848–16851). A duplicate
        ``clientOrderId`` returns the ORIGINAL recorded result and never
        resubmits (T_ADAPTER_DUPLICATE; Ch.16 L16796–16798).
        """
        if not intent_id:
            raise AdapterError("INTENT_ID_REQUIRED",
                               "no order may be submitted without a client order id")
        if self.is_interval_disabled(symbol, timeframe):
            return self._refused("submit_order", intent_id,
                                 "TF_DISABLED_FOR_SYMBOL",
                                 f"{symbol}/{timeframe} disabled after "
                                 f"{INTERVAL_UNSUPPORTED_CODE} (Ch.16 L16877)")
        cached = self._duplicates.get(intent_id)
        if cached is not None:
            return self._cached_result(cached, intent_id)
        defaults = order_defaults(kind)
        effective_type = str(order_type or defaults["type"])
        assert_order_type_permited(effective_type)
        wire_symbol = to_wire_symbol(symbol)
        qty = quantize_quantity(symbol, quantity)
        px = quantize_price(symbol, price)
        notional = check_min_notional(symbol, px, qty)
        if not notional["passes"]:
            return self._refused("submit_order", intent_id, notional["reason"],
                                 f"notional {notional['notional']} < min "
                                 f"{notional['min_notional']}")
        if Decimal(str(qty)) <= 0:
            return self._refused("submit_order", intent_id, "QUANTITY_ZERO",
                                 f"quantity {quantity} floors to 0 at the "
                                 "exchange quantity_step (Y.3 L17425)")
        params: Dict[str, Any] = {
            "symbol": wire_symbol,
            "side": side_for(direction, phase),
            "type": effective_type,
            "quantity": str(qty),
            "price": str(px),
            "clientOrderId": intent_id,
            "positionMode": "ONE_WAY",
        }
        if "tif" in defaults:
            params["timeInForce"] = defaults["tif"]
        if "price_type" in defaults:
            params["priceType"] = defaults["price_type"]
        if reduce_only:
            params["reduceOnly"] = "true"
        if leverage is not None:
            resolved = resolve_leverage(timeframe, symbol=symbol,
                                        owner_cap=owner_leverage_cap)
            if float(leverage) > float(resolved["leverage"]):
                return self._refused(
                    "submit_order", intent_id, "LEVERAGE_ABOVE_MIN_CAP",
                    f"requested {leverage} > min(all caps) "
                    f"{resolved['leverage']} (Ch.16 L16900)")
            params["leverage"] = str(resolved["leverage"])
        if extra_params:
            params.update(dict(extra_params))
        return await self._execute("submit_order", params=params,
                                   client_order_id=intent_id,
                                   interval_context=(symbol, timeframe),
                                   timestamp_utc=timestamp_utc, nonce=nonce)

    # -- OPERATION 2/5 ------------------------------------------------------
    async def cancel_order(self, *, symbol: Optional[str] = None,
                           client_order_id: Optional[str] = None,
                           order_id: Optional[str] = None, scope: str = "single",
                           cancel_id: Optional[str] = None,
                           timestamp_utc: Optional[str] = None,
                           nonce: Optional[str] = None) -> AdapterResult:
        """cancel order → ``DELETE /api/v1/futures/order``
        (``clientOrderId=intent_id``, Ch.16 L16886).

        ``scope='all'`` uses the protective cancel-all path
        ``DELETE /api/v1/futures/batchOrders`` (Ch.21 §5.7 L3 CANCEL_ALL "up to
        12"; wire list L16887) — still ONE operation (ISSUE-CP7-002).
        """
        if scope not in ("single", "all"):
            raise AdapterError("CANCEL_SCOPE_QX", str(scope))
        if scope == "single" and not (client_order_id or order_id):
            raise AdapterError("CANCEL_IDENTITY_REQUIRED",
                               "client_order_id or order_id is required")
        identity = cancel_id or client_order_id or order_id or uuid_v7()
        params: Dict[str, Any] = {}
        override: Optional[Tuple[str, str]] = None
        if symbol:
            params["symbol"] = to_wire_symbol(symbol)
        if scope == "single":
            if client_order_id:
                params["clientOrderId"] = client_order_id
            if order_id:
                params["orderId"] = order_id
        else:
            override = ("DELETE", "/api/v1/futures/batchOrders")
        return await self._execute("cancel_order", params=params,
                                   path_override=override,
                                   client_order_id=str(identity),
                                   timestamp_utc=timestamp_utc, nonce=nonce)

    # -- OPERATION 3/5 ------------------------------------------------------
    async def query_order_state(self, *, symbol: Optional[str] = None,
                                client_order_id: Optional[str] = None,
                                order_id: Optional[str] = None,
                                scope: str = "single",
                                timestamp_utc: Optional[str] = None,
                                nonce: Optional[str] = None) -> AdapterResult:
        """query order state → ``GET /api/v1/futures/order``; every reconcile
        query is keyed by ``clientOrderId`` (Ch.16 L16849).

        ``scope='open'`` reads the working-order book
        (``GET /api/v1/futures/openOrders``) and ``scope='fills'`` reads
        ``GET /api/v1/futures/userTrades`` — the RECONCILING queries Ch.23
        L18247–18249 requires, bound to this one operation (ISSUE-CP7-002).
        """
        if scope not in ("single", "open", "fills"):
            raise AdapterError("QUERY_SCOPE_QX", str(scope))
        params: Dict[str, Any] = {}
        override = None
        if symbol:
            params["symbol"] = to_wire_symbol(symbol)
        if scope == "single":
            if not (client_order_id or order_id):
                raise AdapterError("QUERY_IDENTITY_REQUIRED",
                                   "client_order_id or order_id is required")
            if client_order_id:
                params["clientOrderId"] = client_order_id
            if order_id:
                params["orderId"] = order_id
        elif scope == "open":
            override = ("GET", "/api/v1/futures/openOrders")
        else:
            override = ("GET", "/api/v1/futures/userTrades")
        return await self._execute("query_order_state", params=params,
                                   path_override=override,
                                   client_order_id=client_order_id,
                                   timestamp_utc=timestamp_utc, nonce=nonce)

    # -- OPERATION 4/5 ------------------------------------------------------
    async def query_open_positions(self, *, symbol: Optional[str] = None,
                                   timestamp_utc: Optional[str] = None,
                                   nonce: Optional[str] = None) -> AdapterResult:
        """query open positions → ``GET /api/v1/futures/positions``."""
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = to_wire_symbol(symbol)
        return await self._execute("query_open_positions", params=params,
                                   timestamp_utc=timestamp_utc, nonce=nonce)

    # -- OPERATION 5/5 ------------------------------------------------------
    async def query_account_margin_health(
            self, *, margin_type_symbols: Optional[Sequence[str]] = None,
            leverage_requests: Optional[Sequence[Mapping[str, Any]]] = None,
            commission_symbols: Optional[Sequence[str]] = None,
            timestamp_utc: Optional[str] = None,
            nonce: Optional[str] = None) -> AdapterResult:
        """query account/margin health → ``GET /api/v1/futures/balance``.

        The account-setup calls the chapter requires (``POST …/marginType``
        value ISOLATED, ``POST …/leverage`` at min(all caps),
        ``GET …/commissionRate`` — "store; do not invent a fee", wire list
        L16892–16895) are bound to this ONE operation and are never a sixth
        operation (ISSUE-CP7-002).
        """
        primary = await self._execute("query_account_margin_health", params={},
                                      timestamp_utc=timestamp_utc, nonce=nonce)
        setup: List[AdapterResult] = []
        for sym in tuple(margin_type_symbols or ()):
            assert_account_mode("ISOLATED", "ONE_WAY")
            setup.append(await self._execute(
                "query_account_margin_health",
                params={"symbol": to_wire_symbol(sym), "marginType": "ISOLATED"},
                path_override=("POST", "/api/v1/futures/marginType"),
                timestamp_utc=timestamp_utc, nonce=nonce))
        for req in tuple(leverage_requests or ()):
            resolved = resolve_leverage(str(req["timeframe"]),
                                        symbol=str(req["symbol"]),
                                        owner_cap=req.get("owner_cap"))
            setup.append(await self._execute(
                "query_account_margin_health",
                params={"symbol": to_wire_symbol(str(req["symbol"])),
                        "leverage": str(int(resolved["leverage"]))},
                path_override=("POST", "/api/v1/futures/leverage"),
                timestamp_utc=timestamp_utc, nonce=nonce))
        for sym in tuple(commission_symbols or ()):
            setup.append(await self._execute(
                "query_account_margin_health",
                params={"symbol": to_wire_symbol(sym)},
                path_override=("GET", "/api/v1/futures/commissionRate"),
                timestamp_utc=timestamp_utc, nonce=nonce))
        if not setup:
            return primary
        return AdapterResult(
            operation="query_account_margin_health",
            endpoint=" | ".join([primary.endpoint] + [r.endpoint for r in setup]),
            ok=all(r.ok for r in [primary] + setup),
            classification=primary.classification, outcome=primary.outcome,
            business_code=primary.business_code, http_status=primary.http_status,
            data=MappingProxyType({"balance": dict(primary.data),
                                   "account_setup": [r.to_dict() for r in setup],
                                   "margin_mode": "ISOLATED",
                                   "position_mode": "ONE_WAY"}),
            client_order_id=None, order_id=None,
            idempotency_key=primary.idempotency_key,
            reconcile_required=any(r.reconcile_required
                                   for r in [primary] + setup),
            resubmitted=False, cached=False, interval_disabled=None,
            attempts=tuple(a for r in [primary] + setup for a in r.attempts),
            error_code=primary.error_code, rule=primary.rule)

    # -- internals ----------------------------------------------------------
    async def _execute(self, operation: str, *, params: Dict[str, Any],
                       client_order_id: Optional[str] = None,
                       path_override: Optional[Tuple[str, str]] = None,
                       interval_context: Optional[Tuple[str, str]] = None,
                       timestamp_utc: Optional[str] = None,
                       nonce: Optional[str] = None) -> AdapterResult:
        method, path = (path_override if path_override is not None
                        else endpoint_for(operation))
        endpoint = f"{method} {path}"
        api_key, api_secret = self._credentials()
        attempts: List[AttemptRecord] = []
        last: Dict[str, Any] = {}
        for attempt_no in range(1, RETRY_ATTEMPTS + 1):
            ts_utc = timestamp_utc or self._utc_now()
            # a UNIQUE key per attempt (Ch.16 L16806) — never a silent retry
            attempt_nonce = f"{nonce or 'n'}:{attempt_no}"
            idem = execution_idempotency_key(
                client_order_id or operation, last.get("order_id"), ts_utc,
                attempt_nonce)
            acquired = await self._bucket(endpoint).acquire()
            if not acquired["acquired"]:
                attempts.append(AttemptRecord(
                    attempt_no=attempt_no, operation=operation,
                    endpoint=endpoint, idempotency_key=idem,
                    timestamp_utc=ts_utc, classification=CODE_UNKNOWN,
                    business_code=None, http_status=None,
                    result_source="RATE_LIMIT", actor=self._actor,
                    outcome="UNKNOWN", error=acquired.get("reason")))
                last = {"classification": CODE_UNKNOWN, "outcome": "UNKNOWN",
                        "reconcile_required": True, "idem": idem, "error":
                        acquired.get("reason"),
                        "rule": "AI.8 L18775 queue on exhaustion; the bounded "
                                "wait expired → UNKNOWN + reconcile, never "
                                "dropped and never sent without a token"}
                break
            request = signed_request(method, path, params, api_key=api_key,
                                     api_secret=api_secret,
                                     timestamp_ms=ms_from_iso(ts_utc))
            classification = CODE_UNMAPPED
            business_code: Optional[int] = None
            http_status: Optional[int] = None
            body: Dict[str, Any] = {}
            error: Optional[str] = None
            verdict: Dict[str, Any] = classify_business_code(None)
            try:
                response = await self._transport(method, request["url"],
                                                 request["query"],
                                                 request["headers"])
                http_status = int(response.get("http_status") or 0) or None
                body = dict(response.get("body") or {})
                business_code = _business_code_of(body)
                verdict = classify_business_code(business_code,
                                                 http_status=http_status)
                classification = verdict["classification"]
            except AdapterTimeout as exc:
                verdict = classify_business_code(None, timeout=True)
                classification, error = verdict["classification"], exc.reason
            except (ToobitMapError, AdapterError) as exc:
                classification, error = CODE_UNMAPPED, exc.reason
                verdict = classify_business_code(None)
            except WaveOutError:
                raise
            except Exception as exc:                       # transport fault
                verdict = classify_business_code(None, timeout=True)
                classification = verdict["classification"]
                error = type(exc).__name__
            outcome = _outcome_for(classification, body)
            attempts.append(AttemptRecord(
                attempt_no=attempt_no, operation=operation, endpoint=endpoint,
                idempotency_key=idem, timestamp_utc=ts_utc,
                classification=classification, business_code=business_code,
                http_status=http_status, result_source="TRANSPORT",
                actor=self._actor, outcome=outcome, error=error))
            last = {"classification": classification, "outcome": outcome,
                    "business_code": business_code, "http_status": http_status,
                    "body": body, "idem": idem, "rule": verdict["rule"],
                    "reconcile_required": bool(verdict["reconcile"]),
                    "resubmit": bool(verdict["resubmit"]), "error": error,
                    "order_id": _order_id_of(body)}
            if classification == CODE_BACKOFF and attempt_no < RETRY_ATTEMPTS:
                await asyncio.sleep(float(RETRY_BACKOFF_SECONDS[min(
                    attempt_no - 1, len(RETRY_BACKOFF_SECONDS) - 1)]))
                continue
            break
        self._audit.extend(attempts)
        result = AdapterResult(
            operation=operation, endpoint=endpoint,
            ok=last.get("classification") == CODE_OK,
            classification=last.get("classification", CODE_UNMAPPED),
            outcome=last.get("outcome", "UNKNOWN"),
            business_code=last.get("business_code"),
            http_status=last.get("http_status"),
            data=MappingProxyType(last.get("body") or {}),
            client_order_id=client_order_id, order_id=last.get("order_id"),
            idempotency_key=last.get("idem", ""),
            reconcile_required=bool(last.get("reconcile_required")),
            resubmitted=len(attempts) > 1, cached=False,
            interval_disabled=None, attempts=tuple(attempts),
            error_code=last.get("error"), rule=last.get("rule", ""))
        if operation == "submit_order" and client_order_id:
            # intent_id is unique and permanent: a repeated key returns the
            # previously recorded response and never resubmits (L16796–16798).
            self._duplicates[client_order_id] = result
        if result.business_code == INTERVAL_UNSUPPORTED_CODE:
            result = self._with_interval_disabled(result, client_order_id,
                                                  interval_context)
        return result

    def _with_interval_disabled(self, result: AdapterResult,
                                client_order_id: Optional[str],
                                interval_context: Optional[Tuple[str, str]] = None
                                ) -> AdapterResult:
        """−1120 ⇒ disable that TF for that symbol ONLY (Ch.16 L16877).

        The (symbol, timeframe) are the ones THIS submission carried — the code
        came back for that cell, so exactly that cell is disabled and no other
        cell is touched. When neither the call context nor the response can
        identify the cell, nothing is disabled blindly (G6 fail-closed).
        """
        symbol = timeframe = None
        if interval_context:
            symbol, timeframe = str(interval_context[0]), str(interval_context[1])
        data = dict(result.data)
        raw = str(data.get("msg") or data.get("message") or "")
        if not (symbol and timeframe) and "|" in raw:
            symbol, _, timeframe = raw.partition("|")
        if symbol and timeframe:
            record = interval_disabled_record(symbol, timeframe,
                                              INTERVAL_UNSUPPORTED_CODE)
            self.disable_interval(symbol, timeframe, INTERVAL_UNSUPPORTED_CODE)
        else:
            record = {"business_code": INTERVAL_UNSUPPORTED_CODE,
                      "handling": "DISABLE_TF_FOR_SYMBOL_ONLY",
                      "scope": "SYMBOL_TIMEFRAME_ONLY",
                      "symbol": symbol, "timeframe": timeframe,
                      "note": "symbol/timeframe not resolvable from the "
                              "response — no cell is disabled blindly (G6)"}
        self._audit.append(AttemptRecord(
            attempt_no=0, operation="interval_disable", endpoint=result.endpoint,
            idempotency_key=result.idempotency_key,
            timestamp_utc=self._utc_now(),
            classification=CODE_INTERVAL_UNSUPPORTED,
            business_code=INTERVAL_UNSUPPORTED_CODE, http_status=None,
            result_source="REFUSED", actor=self._actor, outcome="REJECTED"))
        return AdapterResult(**{**{f: getattr(result, f) for f in
                                   result.__dataclass_fields__
                                   if f not in ("interval_disabled",)},
                                "interval_disabled": MappingProxyType(record)})

    def disable_interval(self, symbol: str, timeframe: str,
                         business_code: int = INTERVAL_UNSUPPORTED_CODE
                         ) -> Dict[str, Any]:
        """Adapter-owned bookkeeping for Ch.16 L16877 (called by the runtime
        when a kline/order response carries −1120). Callers may READ the
        registry (:meth:`disabled_intervals`) but never write it."""
        record = interval_disabled_record(symbol, timeframe, business_code)
        bucket = self._disabled.setdefault(symbol, [])
        if timeframe not in bucket:
            bucket.append(timeframe)
        self._audit.append(AttemptRecord(
            attempt_no=0, operation="interval_disable", endpoint="NONE",
            idempotency_key=f"{symbol}|{timeframe}|{business_code}",
            timestamp_utc=self._utc_now(),
            classification=CODE_INTERVAL_UNSUPPORTED,
            business_code=business_code, http_status=None,
            result_source="REFUSED", actor=self._actor, outcome="REJECTED"))
        return record

    def _cached_result(self, original: AdapterResult,
                       intent_id: str) -> AdapterResult:
        record = AttemptRecord(
            attempt_no=0, operation=original.operation,
            endpoint=original.endpoint,
            idempotency_key=original.idempotency_key,
            timestamp_utc=self._utc_now(),
            classification=original.classification,
            business_code=original.business_code,
            http_status=original.http_status, result_source="CACHE",
            actor=self._actor, outcome=original.outcome)
        self._audit.append(record)
        return AdapterResult(
            operation=original.operation, endpoint=original.endpoint,
            ok=original.ok, classification=original.classification,
            outcome=original.outcome, business_code=original.business_code,
            http_status=original.http_status, data=original.data,
            client_order_id=intent_id, order_id=original.order_id,
            idempotency_key=original.idempotency_key,
            reconcile_required=original.reconcile_required,
            resubmitted=False, cached=True,
            interval_disabled=original.interval_disabled, attempts=(record,),
            error_code=None,
            rule="Ch.16 L16796–16798 a repeated key returns the previously "
                 "recorded response and never resubmits (T_ADAPTER_DUPLICATE)")

    def _refused(self, operation: str, client_order_id: str, reason: str,
                 detail: str) -> AdapterResult:
        """Fail-closed refusal BEFORE any exchange call (no order is created)."""
        now = self._utc_now()
        record = AttemptRecord(
            attempt_no=0, operation=operation, endpoint="NONE",
            idempotency_key=execution_idempotency_key(client_order_id, None,
                                                      now, "refused"),
            timestamp_utc=now, classification="REFUSED", business_code=None,
            http_status=None, result_source="REFUSED", actor=self._actor,
            outcome="REJECTED", error=reason)
        self._audit.append(record)
        return AdapterResult(
            operation=operation, endpoint="NONE", ok=False,
            classification="REFUSED", outcome="REJECTED", business_code=None,
            http_status=None,
            data=MappingProxyType({"reason": reason, "detail": detail}),
            client_order_id=client_order_id, order_id=None,
            idempotency_key=record.idempotency_key, reconcile_required=False,
            resubmitted=False, cached=False, interval_disabled=None,
            attempts=(record,), error_code=reason,
            rule="G6 fail-closed: refused before submission, never guessed")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _business_code_of(body: Mapping[str, Any]) -> Optional[int]:
    for key in BUSINESS_CODE_FIELDS:
        if body.get(key) is not None:
            try:
                return int(body[key])
            except (TypeError, ValueError):
                return None
    return None


def _order_id_of(body: Mapping[str, Any]) -> Optional[str]:
    data = body.get(DATA_FIELD)
    if isinstance(data, Mapping) and data.get("orderId") is not None:
        return str(data["orderId"])
    if body.get("orderId") is not None:
        return str(body["orderId"])
    return None


def _outcome_for(classification: str, body: Mapping[str, Any]) -> str:
    """Exchange status → exactly one outcome class (Ch.16 L16858–16860)."""
    if classification == CODE_OK:
        data = body.get(DATA_FIELD)
        status = data.get("status") if isinstance(data, Mapping) else None
        if status is None:
            status = body.get("status")
        if status is None:
            return "ACKNOWLEDGED"       # acceptance without a status literal
        return exchange_status_to_outcome(status)["outcome"]
    if classification in (CODE_INTERVAL_UNSUPPORTED, CODE_ABORT):
        return "REJECTED"
    return "UNKNOWN"                    # UNKNOWN → reconcile-before-action


def ms_from_iso(timestamp_utc: str) -> int:
    from apex.data_catalog.contracts import parse_utc_ms
    try:
        return int(parse_utc_ms(timestamp_utc).timestamp() * 1000)
    except (ValueError, AttributeError, TypeError):
        return int(time.time() * 1000)


def system_utc_ms() -> str:
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


__all__ = [
    "AdapterError", "AdapterResult", "AdapterState", "AdapterStateMutationError",
    "AdapterTimeout", "AttemptRecord", "BUSINESS_CODE_FIELDS",
    "CONTRACT_VERSION", "DATA_FIELD", "FILL_TIMEOUT_SECONDS",
    "RATE_LIMIT_QUEUE_TIMEOUT_SECONDS", "SUBMISSION_TIMEOUT_SECONDS",
    "TOOBIT_BUCKET_CAPACITY", "TOOBIT_BUCKET_REFILL_PER_SECOND",
    "TokenBucketState", "ToobitAdapter", "aiohttp_transport", "ms_from_iso",
    "system_utc_ms",
]
