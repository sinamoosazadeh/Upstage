"""Fake Toobit responder — a TEST DOUBLE only (G9: mocks/fakes are lawful only
behind test code; they never ship in ``apex/**``).

It implements the adapter's transport seam
``Transport(method, url, query, headers) -> {"http_status": int, "body": dict}``
and keeps a tiny in-memory venue state (orders, fills, positions, balances) so
the CP-7 tests can exercise:

* ``T_ADAPTER_SUBMIT``   — a signed submit that the venue acknowledges;
* ``T_ADAPTER_DUPLICATE``— the same ``clientOrderId`` twice;
* ``T_ADAPTER_LOST_ACK`` — the venue RECORDS the order but the response is lost
  (timeout) ⇒ UNKNOWN + reconcile-required + NO resubmit;
* ``−1003`` backoff-and-retry, ``−1022`` abort, ``−1120`` interval unsupported,
  and the unmapped ``−1021`` / ``−2026`` fail-closed paths;
* the reconciliation queries (``positions``, ``openOrders``, ``userTrades``,
  ``balance``) with an injectable divergence.

It also VERIFIES every signed request (HMAC-SHA256 over the query string,
``X-BB-APIKEY`` header, ``recvWindow``) so a signing regression fails loudly.
No network is ever touched.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qsl, urlsplit

from apex.execution.toobit_adapter import AdapterTimeout
from apex.execution.toobit_map import (BASE_URL, HEADER_API_KEY,
                                       RECV_WINDOW_MS, sign_query)

TEST_API_KEY = "TEST_KEY_CP7"
TEST_API_SECRET = "TEST_SECRET_CP7"


@dataclass
class RecordedCall:
    seq: int
    method: str
    path: str
    params: Dict[str, str]
    headers: Dict[str, str]
    signature_ok: bool
    recv_window_ok: bool
    api_key_present: bool
    responded: bool
    note: str = ""


class FakeToobitResponder:
    """Deterministic in-memory Toobit futures responder."""

    def __init__(self, *, api_key: str = TEST_API_KEY,
                 api_secret: str = TEST_API_SECRET,
                 server_time_ms: int = 1767225600000,
                 balance: str = "10000.00000000",
                 clock: Optional[Callable[[], int]] = None) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.server_time_ms = int(server_time_ms)
        self._clock = clock if clock is not None else (lambda: self.server_time_ms)
        self.calls: List[RecordedCall] = []
        self.orders: Dict[str, Dict[str, Any]] = {}     # by clientOrderId
        self.orders_by_id: Dict[str, Dict[str, Any]] = {}
        self.fills: List[Dict[str, Any]] = []
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.balance = balance
        self.margin_type: Dict[str, str] = {}
        self.leverage: Dict[str, str] = {}
        self.commission_rate: Dict[str, str] = {
            "symbol": "BTCUSDT", "makerCommissionRate": "0.0002",
            "takerCommissionRate": "0.0005"}
        # scenario knobs
        self.timeouts_remaining = 0          # lost-ack / transport fault
        self.record_before_timeout = True    # lost ack ⇒ the order IS recorded
        self.fail_with: Optional[int] = None  # business code to return
        self.fail_times = 0
        self.fill_mode: str = "none"          # none | immediate | partial
        self.fill_price: Optional[str] = None
        self.divergence: Optional[str] = None  # inject a reconcile divergence
        self._seq = 0
        self._order_seq = 0
        self._fill_seq = 0

    # -- scenario helpers ---------------------------------------------------
    def lose_next_ack(self, count: int = 1, *, record: bool = True) -> None:
        self.timeouts_remaining = int(count)
        self.record_before_timeout = bool(record)

    def fail_next(self, business_code: int, times: int = 1) -> None:
        self.fail_with = int(business_code)
        self.fail_times = int(times)

    def set_fill_mode(self, mode: str, *, price: Optional[str] = None) -> None:
        if mode not in ("none", "immediate", "partial"):
            raise ValueError(mode)
        self.fill_mode = mode
        self.fill_price = price

    def seed_order(self, *, intent_id: str, symbol: str, timeframe: str,
                   direction: str, quantity: str, price: str) -> Dict[str, Any]:
        """Place a working order directly in venue state (no adapter call)."""
        from apex.execution.toobit_map import side_for, to_wire_symbol
        return self._accept_order({
            "clientOrderId": intent_id, "symbol": to_wire_symbol(symbol),
            "side": side_for(direction, "entry"), "positionSide": "BOTH",
            "type": "LIMIT", "timeInForce": "IOC", "price": price,
            "quantity": quantity, "reduceOnly": "false"})

    def seed_position(self, symbol: str, side: str, quantity: str,
                      entry_price: str = "100.0") -> None:
        self.positions[symbol] = {"symbol": symbol, "positionSide": side.upper(),
                                  "positionAmt": quantity,
                                  "entryPrice": entry_price,
                                  "unRealizedProfit": "0.00000000",
                                  "leverage": self.leverage.get(symbol, "5")}

    # -- transport seam -----------------------------------------------------
    async def __call__(self, method: str, url: str, query: str,
                       headers: Dict[str, str]) -> Dict[str, Any]:
        self._seq += 1
        split = urlsplit(url)
        path = split.path
        if not url.startswith(BASE_URL):
            return self._record_and_return(method, path, {}, headers, False,
                                           {"http_status": 404,
                                            "body": {"code": -1003,
                                                     "msg": "unknown host"}})
        params = dict(parse_qsl(query, keep_blank_values=True))
        signature_ok = self._verify_signature(params, query)
        recv_ok = params.get("recvWindow") in (None, str(RECV_WINDOW_MS))
        api_key_present = bool(headers.get(HEADER_API_KEY))
        call = RecordedCall(seq=self._seq, method=method.upper(), path=path,
                            params=params, headers=dict(headers),
                            signature_ok=signature_ok, recv_window_ok=recv_ok,
                            api_key_present=api_key_present, responded=False)
        self.calls.append(call)
        self.server_time_ms = int(self._clock())
        if self.timeouts_remaining > 0:
            self.timeouts_remaining -= 1
            if self.record_before_timeout and path == "/api/v1/futures/order" \
                    and method.upper() == "POST":
                # The venue accepted the order; only the RESPONSE was lost.
                self._accept_order(params, note="ACK_LOST")
            call.responded = False
            call.note = "TIMEOUT_INJECTED"
            raise AdapterTimeout(f"{method} {path}")
        if self.fail_with is not None and self.fail_times > 0:
            self.fail_times -= 1
            code = self.fail_with
            if self.fail_times == 0:
                self.fail_with = None
            call.responded = True
            call.note = f"BUSINESS_CODE_{code}"
            return {"http_status": 400 if code < 0 else 200,
                    "body": {"code": code, "msg": f"injected {code}"}}
        return self._route(call, method.upper(), path, params)

    def _record_and_return(self, method: str, path: str, params: Dict[str, str],
                           headers: Dict[str, str], signature_ok: bool,
                           response: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append(RecordedCall(self._seq, method.upper(), path, params,
                                       headers, signature_ok, True,
                                       bool(headers.get(HEADER_API_KEY)), True))
        return response

    def _verify_signature(self, params: Dict[str, str],
                          raw_query: str = "") -> bool:
        """Recompute the HMAC over the query EXACTLY as it was sent.

        A real venue signs the raw query string; re-encoding the parsed values
        would silently change any percent-encoded character (a ``:`` in a
        clientOrderId, for instance) and report a false signature violation.
        """
        signature = params.get("signature")
        if signature is None:
            return True            # public (unsigned) path
        if raw_query:
            parts = [p for p in raw_query.split("&")
                     if p and not p.startswith("signature=")]
            query = "&".join(parts)
        else:
            body = {k: v for k, v in params.items() if k != "signature"}
            query = "&".join(f"{k}={v}" for k, v in body.items())
        expected = sign_query(self.api_secret, query)
        return hmac.compare_digest(expected, signature)

    # -- routes -------------------------------------------------------------
    def _route(self, call: RecordedCall, method: str, path: str,
               params: Dict[str, str]) -> Dict[str, Any]:
        call.responded = True
        if path == "/api/v1/time" and method == "GET":
            return {"http_status": 200, "body": {"code": 0, "msg": "success",
                                                 "data": {"serverTime":
                                                          self.server_time_ms}}}
        if path == "/api/v1/futures/order" and method == "POST":
            order = self._accept_order(params)
            return {"http_status": 200, "body": {"code": 0, "msg": "success",
                                                 "data": order}}
        if path == "/api/v1/futures/order" and method == "GET":
            key = params.get("clientOrderId") or params.get("orderId")
            order = (self.orders.get(key) or self.orders_by_id.get(key))
            if order is None:
                return {"http_status": 400,
                        "body": {"code": -2013, "msg": "Order does not exist"}}
            return {"http_status": 200, "body": {"code": 0, "msg": "success",
                                                 "data": order}}
        if path == "/api/v1/futures/order" and method == "DELETE":
            return self._cancel(params, single=True)
        if path == "/api/v1/futures/batchOrders" and method == "DELETE":
            return self._cancel(params, single=False)
        if path == "/api/v1/futures/openOrders" and method == "GET":
            open_orders = [o for o in self.orders.values()
                           if o["status"] in ("NEW", "PARTIALLY_FILLED")]
            return {"http_status": 200, "body": {"code": 0, "msg": "success",
                                                 "data": open_orders}}
        if path == "/api/v1/futures/userTrades" and method == "GET":
            symbol = params.get("symbol")
            fills = [f for f in self.fills if not symbol or f["symbol"] == symbol]
            return {"http_status": 200, "body": {"code": 0, "msg": "success",
                                                 "data": fills}}
        if path == "/api/v1/futures/positions" and method == "GET":
            data = list(self.positions.values())
            if self.divergence:
                data = [dict(p, positionAmt=self.divergence) for p in data]
            return {"http_status": 200, "body": {"code": 0, "msg": "success",
                                                 "data": data}}
        if path == "/api/v1/futures/balance" and method == "GET":
            data = [{"asset": "USDT", "balance": self.balance,
                     "availableBalance": self.balance,
                     "crossWalletBalance": self.balance,
                     "marginBalance": self.balance}]
            return {"http_status": 200, "body": {"code": 0, "msg": "success",
                                                 "data": data}}
        if path == "/api/v1/futures/marginType" and method == "POST":
            self.margin_type[params.get("symbol", "")] = params.get(
                "marginType", "ISOLATED")
            return {"http_status": 200, "body": {"code": 0, "msg": "success",
                                                 "data": {"symbol":
                                                          params.get("symbol"),
                                                          "marginType":
                                                          self.margin_type[
                                                              params.get("symbol", "")]}}}
        if path == "/api/v1/futures/leverage" and method == "POST":
            self.leverage[params.get("symbol", "")] = str(params.get("leverage"))
            return {"http_status": 200, "body": {"code": 0, "msg": "success",
                                                 "data": {"symbol":
                                                          params.get("symbol"),
                                                          "leverage":
                                                          self.leverage[
                                                              params.get("symbol", "")]}}}
        if path == "/api/v1/futures/commissionRate" and method == "GET":
            return {"http_status": 200, "body": {"code": 0, "msg": "success",
                                                 "data": self.commission_rate}}
        if path == "/api/v1/futures/exchangeInfo" and method == "GET":
            return {"http_status": 200, "body": {"code": 0, "msg": "success",
                                                 "data": {"symbols": []}}}
        if path == "/api/v1/futures/klines" and method == "GET":
            return {"http_status": 200, "body": {"code": 0, "msg": "success",
                                                 "data": self._klines(params)}}
        # Unlisted path: the venue would refuse it; the adapter must never ask.
        call.note = "UNLISTED_PATH"
        return {"http_status": 404, "body": {"code": -1003,
                                             "msg": f"unlisted path {path}"}}

    def _klines(self, params: Dict[str, str]) -> List[List[Any]]:
        limit = int(params.get("limit", 5))
        interval = params.get("interval", "1h")
        start = int(params.get("startTime", self.server_time_ms - limit * 3600_000))
        rows: List[List[Any]] = []
        for i in range(limit):
            open_time = start + i * 3600_000
            price = 100.0 + i
            rows.append([open_time, f"{price:.2f}", f"{price + 1:.2f}",
                         f"{price - 1:.2f}", f"{price + 0.5:.2f}", "10.0",
                         open_time + 3599_999, "1000.0", 5, "5.0", "500.0", "0"])
        return rows

    # -- venue state --------------------------------------------------------
    def _accept_order(self, params: Dict[str, str], note: str = "") -> Dict[str, Any]:
        client_order_id = params.get("clientOrderId", "")
        existing = self.orders.get(client_order_id)
        if existing is not None:
            existing["duplicate_submission"] = True
            return existing
        self._order_seq += 1
        order_id = f"{900000 + self._order_seq}"
        quantity = params.get("quantity", "0")
        price = params.get("price") or self.fill_price or "100.0"
        status = "NEW"
        executed = "0"
        order = {"orderId": order_id, "clientOrderId": client_order_id,
                 "symbol": params.get("symbol"), "side": params.get("side"),
                 "positionSide": params.get("positionSide", "BOTH"),
                 "type": params.get("type"), "timeInForce":
                 params.get("timeInForce"), "price": price,
                 "origQty": quantity, "executedQty": executed,
                 "status": status, "reduceOnly":
                 params.get("reduceOnly") in ("true", "True"),
                 "updateTime": self.server_time_ms, "note": note}
        self.orders[client_order_id] = order
        self.orders_by_id[order_id] = order
        if self.fill_mode == "immediate":
            self._fill(order, quantity, self.fill_price or price)
        elif self.fill_mode == "partial":
            partial = _half(quantity)
            self._fill(order, partial, self.fill_price or price)
        return order

    def _fill(self, order: Dict[str, Any], quantity: str, price: str) -> None:
        self._fill_seq += 1
        executed = _decimal_add(order["executedQty"], quantity)
        order["executedQty"] = executed
        from decimal import Decimal
        order["status"] = "FILLED" if Decimal(executed) == Decimal(
            str(order["origQty"])) else "PARTIALLY_FILLED"
        fill = {"id": str(700000 + self._fill_seq), "symbol": order["symbol"],
                "orderId": order["orderId"], "clientOrderId":
                order["clientOrderId"], "side": order["side"],
                "price": price, "qty": quantity, "quoteQty":
                _decimal_mul(price, quantity), "commission": "0.01000000",
                "commissionAsset": "USDT", "time": self.server_time_ms,
                "maker": False, "realizedPnl": "0.00000000"}
        self.fills.append(fill)
        self._update_position(order, quantity, price)

    def _update_position(self, order: Dict[str, Any], quantity: str,
                         price: str) -> None:
        symbol = order["symbol"]
        side = str(order.get("side", "")).upper()
        signed = quantity if side.startswith("BUY") else f"-{quantity}"
        current = self.positions.get(symbol)
        if current is None:
            self.positions[symbol] = {"symbol": symbol,
                                      "positionSide": order.get("positionSide",
                                                                "BOTH"),
                                      "positionAmt": signed,
                                      "entryPrice": price,
                                      "unRealizedProfit": "0.00000000",
                                      "leverage": self.leverage.get(symbol, "5")}
        else:
            current["positionAmt"] = _decimal_add(current["positionAmt"], signed)

    def _cancel(self, params: Dict[str, str], *, single: bool) -> Dict[str, Any]:
        if single:
            key = params.get("clientOrderId") or params.get("orderId")
            order = self.orders.get(key) or self.orders_by_id.get(key or "")
            if order is None:
                return {"http_status": 400,
                        "body": {"code": -2011, "msg": "Cancel rejected"}}
            order["status"] = "CANCELED"
            return {"http_status": 200, "body": {"code": 0, "msg": "success",
                                                 "data": order}}
        raw = params.get("clientOrderId") or "[]"
        try:
            keys = json.loads(raw)
        except ValueError:
            keys = [k for k in re.split(r"[,\[\]\"']+", raw) if k]
        cancelled = []
        for key in keys:
            order = self.orders.get(str(key)) or self.orders_by_id.get(str(key))
            if order is not None:
                order["status"] = "CANCELED"
                cancelled.append(order)
        return {"http_status": 200, "body": {"code": 0, "msg": "success",
                                             "data": cancelled}}

    # -- assertions helpers -------------------------------------------------
    def calls_to(self, path: str, method: Optional[str] = None
                 ) -> List[RecordedCall]:
        return [c for c in self.calls if c.path == path
                and (method is None or c.method == method.upper())]

    def signature_violations(self) -> List[RecordedCall]:
        return [c for c in self.calls if not c.signature_ok
                or not c.recv_window_ok or not c.api_key_present]

    def open_order_count(self) -> int:
        return len([o for o in self.orders.values()
                    if o["status"] in ("NEW", "PARTIALLY_FILLED")])


# ---------------------------------------------------------------------------
# decimal-string helpers (money/prices stay TEXT at the boundary)
# ---------------------------------------------------------------------------

def _decimal_add(left: str, right: str) -> str:
    from decimal import Decimal
    value = Decimal(str(left)) + Decimal(str(right))
    return f"{value:.8f}".rstrip("0").rstrip(".") or "0"


def _decimal_mul(left: str, right: str) -> str:
    from decimal import Decimal
    return f"{Decimal(str(left)) * Decimal(str(right)):.8f}"


def _half(quantity: str) -> str:
    from decimal import Decimal
    value = Decimal(str(quantity)) / Decimal(2)
    return f"{value:.8f}".rstrip("0").rstrip(".") or "0"


__all__ = ["FakeToobitResponder", "RecordedCall", "TEST_API_KEY",
           "TEST_API_SECRET"]
