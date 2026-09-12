"""CP-1 public Toobit ingest tests: wire maps, kline parsing, retry/backoff
discipline, fail-closed failures, OI MISSING never 0, funding alert
threshold. A fake HTTP session stands in for the venue (lawful test
double; real-venue verification is the owner's G-TOOBIT gate)."""
from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from apex.data_catalog.ingest.toobit_public import (
    ToobitPublicClient,
    ToobitPublicError,
    parse_kline_to_observation,
    to_wire_interval,
    to_wire_symbol,
)


def run(coro):
    return asyncio.run(coro)


class FakeResponse:
    def __init__(self, status=200, payload=None, exc=None):
        self.status = status
        self._payload = payload
        self._exc = exc

    async def __aenter__(self):
        if self._exc is not None:
            raise self._exc
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self, content_type=None):
        return self._payload


class FakeSession:
    """Scripted fake aiohttp-like session: queues responses per call."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.sleeps = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params))
        response = self.responses.pop(0) if self.responses else \
            FakeResponse(status=500, payload={})
        if isinstance(response, Exception):
            raise response  # connection-level failure raised at call time
        return response


class TestWireMaps:
    def test_symbol_map(self):
        assert to_wire_symbol("BTCUSDT") == "BTC-SWAP-USDT"
        assert to_wire_symbol("LTCUSDT") == "LTC-SWAP-USDT"
        with pytest.raises(ValueError):
            to_wire_symbol("DOTUSDT")

    def test_interval_map(self):
        assert to_wire_interval("1mo") == "1M"
        assert to_wire_interval("15m") == "15m"


class TestKlineParsing:
    def test_parse_list_row(self):
        row = [1704067200000, "100", "110", "98", "105", "10", 1704068100000]
        obs = parse_kline_to_observation("BTCUSDT", "15m", row, 3)
        assert obs.symbol == "BTCUSDT"
        assert obs.open == Decimal("100") and obs.close == Decimal("105")
        assert obs.high == Decimal("110") and obs.low == Decimal("98")
        assert obs.volume == Decimal("10")
        assert obs.oi is None  # klines carry no OI → MISSING, never 0
        assert obs.status == "CLOSED"
        assert obs.sequence == 3

    def test_parse_dict_row(self):
        row = {"open_time": 1704067200000, "open": "100", "high": "110",
               "low": "98", "close": "105", "volume": "10",
               "close_time": 1704068100000}
        obs = parse_kline_to_observation("BTCUSDT", "15m", row, 0)
        assert obs.close == Decimal("105")

    def test_bad_row_fails_closed(self):
        with pytest.raises(ToobitPublicError):
            parse_kline_to_observation("BTCUSDT", "15m", ["x"], 0)


class TestRetryDiscipline:
    def test_retry_then_success_with_backoff(self):
        import aiohttp
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([
            FakeResponse(status=500, payload={}),
            aiohttp.ClientConnectionError("conn refused"),
            FakeResponse(status=200, payload={"serverTime": 1704067200000}),
        ])
        client._session = session
        # override sleep to record backoff instead of sleeping
        sleeps = []
        async def fake_sleep(sec):
            sleeps.append(sec)
        orig = asyncio.sleep
        try:
            asyncio.sleep = fake_sleep
            body = run(client.get_server_time())
        finally:
            asyncio.sleep = orig
        assert body == {"serverTime": 1704067200000}
        assert len(session.calls) == 3
        assert sleeps == [1.0, 2.0]  # frozen 1s/2s/4s backoff

    def test_retry_exhausted_fails_closed(self):
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([
            FakeResponse(status=500, payload={}) for _ in range(3)])
        client._session = session
        async def fake_sleep(sec):
            pass
        orig = asyncio.sleep
        try:
            asyncio.sleep = fake_sleep
            with pytest.raises(ToobitPublicError) as ei:
                run(client.get_server_time())
        finally:
            asyncio.sleep = orig
        assert "RETRY_EXHAUSTED" in str(ei.value)

    def test_429_too_many_requests(self):
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([
            FakeResponse(status=429, payload={}) for _ in range(3)])
        client._session = session
        async def fake_sleep(sec):
            pass
        orig = asyncio.sleep
        try:
            asyncio.sleep = fake_sleep
            with pytest.raises(ToobitPublicError) as ei:
                run(client.get_server_time())
        finally:
            asyncio.sleep = orig
        assert "TOO_MAUTC_W2_REQUESTS" in str(ei.value)


class TestEndpoints:
    def test_open_interest_missing_never_zero(self):
        """OI endpoint failure → OI MISSING (None), never 0 (T-DC-004)."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([FakeResponse(status=500, payload={})])
        client._session = session
        async def fake_sleep(sec):
            pass
        orig = asyncio.sleep
        try:
            asyncio.sleep = fake_sleep
            assert run(client.get_open_interest("BTCUSDT", "15m")) is None
        finally:
            asyncio.sleep = orig

    def test_open_interest_value(self):
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([FakeResponse(
            status=200, payload={"data": {"openInterest": "1234.5"}})])
        client._session = session
        assert run(client.get_open_interest("BTCUSDT", "15m")) == \
            Decimal("1234.5")

    def test_funding_rate_alert_threshold(self):
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([FakeResponse(
            status=200, payload={"data": {"fundingRate": "0.002"}})])
        client._session = session
        rate, alert = run(client.get_funding_rate("BTCUSDT"))
        assert rate == Decimal("0.002") and alert is True  # |rate| ≥ 0.001

    def test_funding_rate_no_alert(self):
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([FakeResponse(
            status=200, payload={"data": {"fundingRate": "0.0005"}})])
        client._session = session
        rate, alert = run(client.get_funding_rate("BTCUSDT"))
        assert alert is False

    def test_klines_limit_cap(self):
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        with pytest.raises(ToobitPublicError):
            run(client.get_klines("BTCUSDT", "15m", 0, 1, limit=2000))
