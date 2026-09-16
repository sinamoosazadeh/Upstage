"""APEX_GEN5 public Toobit ingest client (Ch.16 wire, public side).

Public endpoints, exactly as listed in the wire map (copied to
params/toobit_wire_v1.yaml):
- GET /api/v1/time
- GET /api/v1/exchangeInfo (live filters win vs the Trading Universe for
  quantization)
- GET /quote/v1/depth
- GET /quote/v1/klines (limit 1000)
- GET /quote/v1/openInterest (failure → OI MISSING — never 0, T-DC-004)
- GET /api/v1/futures/fundingRate (alert only if |rate| ≥ 0.001; not a
  15th veto, Ch.16)

Base https://api.toobit.com, header X-BB-APIKEY. Internal symbol → wire
symbol (BTCUSDT → BTC-SWAP-USDT); interval 1mo → 1M; others identical. If
8h returns −1120 the caller disables THAT TF for THAT symbol only.

Retry discipline: 3 attempts, exponential backoff 1s/2s/4s
(TOO_MAUTC_W2_REQUESTS); every failure fails closed with
ToobitPublicError — no fabricated data, no silent substitutes. The
signed Wave-In surface belongs to the execution adapter (CP-7); this
module never sends signed requests.

Response-Shape Documentation (CP-10 Hotfix):
--------------------------------------------
Live probes on the target device verify:
1. GET /quote/v1/klines returns a bare JSON array `[[...], ...]`, NOT wrapped
   in a `{"code": ..., "data": ...}` envelope on HTTP 200 success.
2. GET /quote/v1/openInterest returns a bare JSON object `{"openInterest": ...}`,
   NOT wrapped in a `{"code": ..., "data": ...}` envelope on HTTP 200 success.
3. Errors on HTTP 200 or 4xx return an object containing a non-zero "code" and
   "msg", e.g. `{"code": -1003, "msg": "Too many requests"}`.

Client choke-point unwrap rule (`unwrap_toobit_response`):
- Bare list: it IS the data (returned as-is, including legitimate empty list `[]`
  signaling end of history for that cell).
- Dict with non-zero "code": fails closed by raising `ToobitPublicError` whose
  message includes the numeric code and error msg. This preserves the `-1003`
  rate limit marker so `bootstrap_service` executes its backoff path, and ensures
  any other non-zero code causes a named failure rather than collapsing into empty
  rows (which would cause silent completion).
- Dict with "data": unwraps and returns `data` (handles wrapped success envelopes).
- Bare dict without "data" or error "code": it IS the data.
- Tolerant row parsing accepts both list rows and dict rows in klines.
- HTTP 429 folding and retry discipline remain intact.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from apex.config import load_params
from apex.data_catalog.contracts import CORE10_SYMBOLS, MarketObservation

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = (1.0, 2.0, 4.0)
REQUEST_TIMEOUT_SECONDS = 10.0


class ToobitPublicError(RuntimeError):
    """Fail-closed public-ingest failure (never swallowed, never faked)."""

    def __init__(self, endpoint: str, detail: str) -> None:
        super().__init__(f"TOOBIT_PUBLIC {endpoint}: {detail}")
        self.endpoint = endpoint
        self.detail = detail


def unwrap_toobit_response(body: Any, endpoint: str = "") -> Any:
    """Unwrap Toobit public response at the client choke point.

    Handles both bare-array/bare-object shapes and wrapped envelopes:
    - bare list -> it IS the data;
    - dict with non-zero "code" -> ToobitPublicError whose message contains
      the numeric code and msg (so RATE_LIMIT_MARKERS "-1003" keeps matching
      for bootstrap backoff; any other non-zero code raises a named failure
      and never empty rows);
    - dict with "data" -> data;
    - bare dict without "data" or error "code" -> it IS the data.
    """
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        if "code" in body and body["code"] is not None:
            code = body["code"]
            try:
                num_code = int(code)
            except (ValueError, TypeError):
                num_code = None
            if num_code is not None:
                if num_code != 0:
                    msg = body.get("msg") or body.get("message") or ""
                    raise ToobitPublicError(
                        endpoint, f"code={num_code} msg={msg}")
            elif str(code).strip() not in ("0", ""):
                msg = body.get("msg") or body.get("message") or ""
                raise ToobitPublicError(
                    endpoint, f"code={code} msg={msg}")
        if "data" in body:
            return body["data"]
        return body
    return body


def to_wire_symbol(symbol: str) -> str:
    """Internal symbol → wire symbol (Ch.16 map). Unknown symbol → fail-
    closed ValueError (E-VAL-021 discipline)."""
    symbol_map = load_params()["toobit_wire"]["symbol_map"]
    if symbol not in symbol_map:
        raise ValueError(f"E-VAL-021: {symbol} not in Core-10 wire map")
    return symbol_map[symbol]


def to_wire_interval(interval: str) -> str:
    """Interval map: 1mo → 1M; others identical (Ch.16)."""
    interval_map = load_params()["toobit_wire"]["interval_map"]
    return interval_map.get(interval, interval)


def parse_kline_to_observation(symbol: str, interval: str, row: Any,
                               seq: int) -> MarketObservation:
    """Parse one Toobit kline row → MarketObservation (CLOSED candles
    only; the klines endpoint is PIT-safe by construction).

    Accepted row shapes (fail-closed on anything else):
    - list [open_time, open, high, low, close, volume, close_time, ...]
    - dict {open_time/openTime, open, high, low, close, volume, ...}
    OI is not part of klines; oi=None (MISSING — never 0).
    """
    def _dec(value: Any, field: str) -> Decimal:
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ToobitPublicError(
                "klines", f"non-decimal {field}={value!r}") from exc

    if isinstance(row, (list, tuple)):
        if len(row) < 6:
            raise ToobitPublicError("klines", f"short kline row {row!r}")
        open_time_ms, o, h, l, c, v = row[0], row[1], row[2], row[3], row[4], row[5]
        close_time_ms = row[6] if len(row) > 6 else open_time_ms
    elif isinstance(row, dict):
        key_ot = "open_time" if "open_time" in row else "openTime"
        key_ct = "close_time" if "close_time" in row else "closeTime"
        open_time_ms = row.get(key_ot)
        close_time_ms = row.get(key_ct, open_time_ms)
        o, h, l, c, v = row["open"], row["high"], row["low"], row["close"], row["volume"]
    else:
        raise ToobitPublicError("klines", f"unexpected row type {type(row)}")

    def _ts(ms: Any) -> str:
        try:
            import datetime as _dt
            ts = _dt.datetime.fromtimestamp(int(ms) / 1000.0,
                                            tz=_dt.timezone.utc)
            return ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(ms) % 1000:03d}Z"
        except (ValueError, TypeError, OSError) as exc:
            raise ToobitPublicError("klines", f"bad timestamp {ms!r}") from exc

    obs = MarketObservation(
        symbol=symbol, timeframe=interval,
        open=_dec(o, "open"), high=_dec(h, "high"),
        low=_dec(l, "low"), close=_dec(c, "close"),
        volume=_dec(v, "volume"), oi=None,
        timestamp=_ts(open_time_ms), sequence=seq,
        status="CLOSED", source="TOOBIT",
        availability_time=_ts(close_time_ms),
    )
    return obs


class ToobitPublicClient:
    """Public (unsigned) Toobit HTTP client. ``session`` may be injected
    (tests use a fake Toobit HTTP responder — lawful test double, G9);
    production uses the default aiohttp session."""

    def __init__(self, session: Any = None) -> None:
        self._session = session
        wire = load_params()["toobit_wire"]
        self.base_url = wire["base_url"]
        self.api_key_header = wire["header_api_key"]
        self.klines_limit = int(wire["klines_limit"])
        self._attempts = int(wire.get("retry_attempts", RETRY_ATTEMPTS))
        self._backoff = tuple(
            float(x) for x in wire.get("retry_backoff_seconds",
                                       RETRY_BACKOFF_SECONDS))

    async def _session_or_new(self):
        if self._session is not None:
            return self._session
        import aiohttp
        return aiohttp.ClientSession()

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None,
                   ) -> Any:
        """GET with the frozen retry discipline (3 attempts, 1s/2s/4s
        backoff). Persistent failure → ToobitPublicError (fail-closed)."""
        import aiohttp
        session = await self._session_or_new()
        last_exc: Optional[Exception] = None
        for attempt in range(self._attempts):
            try:
                async with session.get(
                        self.base_url + path, params=params,
                        headers={self.api_key_header: ""},
                        timeout=aiohttp.ClientTimeout(
                            total=REQUEST_TIMEOUT_SECONDS)) as resp:
                    if resp.status == 429:
                        raise ToobitPublicError(
                            path, "TOO_MAUTC_W2_REQUESTS (HTTP 429)")
                    if resp.status != 200:
                        raise ToobitPublicError(
                            path, f"HTTP {resp.status}")
                    body = await resp.json(content_type=None)
                    return unwrap_toobit_response(body, endpoint=path)
            except (aiohttp.ClientError, asyncio.TimeoutError,
                    ToobitPublicError, ValueError) as exc:
                last_exc = exc
                if attempt < self._attempts - 1:
                    await asyncio.sleep(self._backoff[attempt])
        # Persistent failure: the final error always carries RETRY_EXHAUSTED
        # AND the last failure code (e.g. TOO_MAUTC_W2_REQUESTS) — never a
        # generic mask (fail-closed, AI.8 audit discipline).
        raise ToobitPublicError(
            path, f"RETRY_EXHAUSTED after {self._attempts} attempts; "
                  f"last failure: {last_exc}")

    # -- endpoints ----------------------------------------------------------
    async def get_server_time(self) -> Dict[str, Any]:
        """GET /api/v1/time."""
        data = await self._get("/api/v1/time")
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
            return data["data"]
        return data

    async def get_exchange_info(self) -> Dict[str, Any]:
        """GET /api/v1/exchangeInfo — live filters win vs the Trading
        Universe for quantization (Ch.16)."""
        data = await self._get("/api/v1/exchangeInfo")
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
            return data["data"]
        return data

    async def get_depth(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """GET /quote/v1/depth (wire symbol)."""
        data = await self._get("/quote/v1/depth",
                               params={"symbol": to_wire_symbol(symbol),
                                       "limit": limit})
        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], dict):
                data = data["data"]
            return data
        raise ToobitPublicError(
            "depth", f"unexpected response shape: {type(data).__name__}")

    async def get_klines(self, symbol: str, interval: str,
                         start_ms: int, end_ms: int,
                         limit: Optional[int] = None,
                         ) -> List[MarketObservation]:
        """GET /quote/v1/klines (limit 1000). Returns CLOSED candles as
        MarketObservations with strictly increasing sequences."""
        if limit is None:
            limit = self.klines_limit
        if limit > self.klines_limit:
            raise ToobitPublicError(
                "klines", f"limit {limit} exceeds {self.klines_limit}")
        raw = await self._get("/quote/v1/klines", params={
            "symbol": to_wire_symbol(symbol),
            "interval": to_wire_interval(interval),
            "startTime": start_ms, "endTime": end_ms, "limit": limit,
        })
        rows = raw
        if isinstance(rows, dict):
            if "code" in rows and rows["code"] is not None:
                try:
                    num_code = int(rows["code"])
                except (ValueError, TypeError):
                    num_code = None
                if num_code is not None and num_code != 0:
                    msg = rows.get("msg") or rows.get("message") or ""
                    raise ToobitPublicError(
                        "klines", f"code={num_code} msg={msg}")
            if "data" in rows:
                rows = rows["data"]
            if isinstance(rows, dict):
                rows = rows.get("list", rows.get("klines"))
        if not isinstance(rows, list):
            raise ToobitPublicError(
                "klines", f"unexpected response shape: {type(rows).__name__}")
        result: List[MarketObservation] = []
        for i, row in enumerate(rows):
            result.append(parse_kline_to_observation(symbol, interval, row, i))
        return result

    async def get_open_interest(self, symbol: str, interval: str,
                                ) -> Optional[Decimal]:
        """GET /quote/v1/openInterest. Failure → OI MISSING (returns
        None — NEVER 0; T-DC-004/T-OM-001)."""
        try:
            body = await self._get("/quote/v1/openInterest", params={
                "symbol": to_wire_symbol(symbol),
                "interval": to_wire_interval(interval),
            })
        except ToobitPublicError:
            return None  # OI MISSING (fail-closed, never substituted)
        data = body
        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], (dict, list, str, int, float, Decimal)):
                data = data["data"]
            if isinstance(data, dict):
                data = data.get("openInterest", data.get("oi"))
        elif isinstance(data, list) and data:
            data = data[-1]
            if isinstance(data, dict):
                data = data.get("openInterest", data.get("oi"))
        if data is None or data == "":
            return None
        try:
            return Decimal(str(data))
        except InvalidOperation:
            return None  # OI INVALID → MISSING label at ingest

    async def get_funding_rate(self, symbol: str,
                               ) -> Tuple[Optional[Decimal], bool]:
        """GET /api/v1/futures/fundingRate. Returns (rate, alert_flag);
        alert_only: |rate| ≥ 0.001 → alert (not a 15th veto, Ch.16)."""
        data = await self._get("/api/v1/futures/fundingRate", params={
            "symbol": to_wire_symbol(symbol)})
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        if isinstance(data, list) and data:
            data = data[-1]
        if isinstance(data, dict):
            rate_raw = data.get("fundingRate", data.get("rate"))
        else:
            rate_raw = data
        if rate_raw is None or rate_raw == "":
            return None, False
        try:
            rate = Decimal(str(rate_raw))
        except InvalidOperation:
            return None, False
        return rate, abs(rate) >= Decimal("0.001")
