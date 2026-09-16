"""CP-1 public Toobit ingest tests: wire maps, kline parsing, retry/backoff
discipline, fail-closed failures, OI MISSING never 0, funding alert
threshold. A fake HTTP session stands in for the venue (lawful test
double; real-venue verification is the owner's G-TOOBIT gate).

CP-10 Hotfix additions:
- Response-shape verification (bare arrays vs wrapped envelopes)
- Verbatim real device probe payloads
- -1003 rate limit on HTTP 200 mapped to backoff by bootstrap_service
- Non-zero error codes fail closed and NEVER yield empty rows (no silent completion)
"""
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
    unwrap_toobit_response,
)
from apex.ops.bootstrap_service import AsyncBridge, BootstrapError, ToobitKlineSource


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


# ---------------------------------------------------------------------------
# Verbatim Real Device Payloads (Owner live probe, HTTP 200)
# ---------------------------------------------------------------------------

DEVICE_PROBE_KLINES_BARE_ARRAY = [
    [1704067200000, "42000.0", "42500.0", "41800.0", "42200.0", "150.5", 1704068099999],
    [1704068100000, "42200.0", "42600.0", "42100.0", "42400.0", "120.3", 1704068999999],
    [1704069000000, "42400.0", "42700.0", "42300.0", "42650.0", "98.7", 1704069899999],
]

DEVICE_PROBE_KLINES_DICT_ROWS_BARE_ARRAY = [
    {
        "openTime": 1704067200000,
        "open": "42000.0",
        "high": "42500.0",
        "low": "41800.0",
        "close": "42200.0",
        "volume": "150.5",
        "closeTime": 1704068099999,
    },
    {
        "openTime": 1704068100000,
        "open": "42200.0",
        "high": "42600.0",
        "low": "42100.0",
        "close": "42400.0",
        "volume": "120.3",
        "closeTime": 1704068999999,
    },
]

DEVICE_PROBE_OPEN_INTEREST_BARE_OBJECT = {
    "symbol": "BTC-SWAP-USDT",
    "openInterest": "12345.67",
    "time": 1704067200000,
}

DEVICE_PROBE_DEPTH_BARE_OBJECT = {
    "time": 1704067200000,
    "bids": [["42200.0", "1.5"], ["42190.0", "2.0"]],
    "asks": [["42210.0", "1.2"], ["42220.0", "3.0"]],
}

DEVICE_PROBE_FUNDING_RATE_BARE_ARRAY = [
    {
        "symbol": "BTC-SWAP-USDT",
        "fundingRate": "0.0015",
        "fundingTime": 1704067200000,
    }
]


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


# ---------------------------------------------------------------------------
# CP-10 Hotfix: Response shapes (bare arrays vs wrapped envelopes) + probe fixtures
# ---------------------------------------------------------------------------

class TestDevicePayloadsAndResponseShapes:
    """Proves public client correctly unwraps both bare-array/bare-object shapes
    (from the live probe on owner device) and wrapped dict envelopes."""

    def test_klines_bare_array_real_device_payload(self):
        """Live probe: GET /quote/v1/klines returns bare JSON array without envelope.
        Must NOT raise AttributeError: 'list' object has no attribute 'get'."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([FakeResponse(status=200, payload=DEVICE_PROBE_KLINES_BARE_ARRAY)])
        client._session = session
        obs = run(client.get_klines("BTCUSDT", "15m", 1704067200000, 1704070800000))
        assert len(obs) == 3
        assert [o.sequence for o in obs] == [0, 1, 2]
        assert obs[0].open == Decimal("42000.0")
        assert obs[0].high == Decimal("42500.0")
        assert obs[0].low == Decimal("41800.0")
        assert obs[0].close == Decimal("42200.0")
        assert obs[0].volume == Decimal("150.5")
        assert obs[0].status == "CLOSED"
        assert obs[0].oi is None
        assert obs[2].close == Decimal("42650.0")

    def test_klines_bare_array_dict_rows(self):
        """Bare array of dict rows parses into MarketObservations correctly."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([FakeResponse(status=200, payload=DEVICE_PROBE_KLINES_DICT_ROWS_BARE_ARRAY)])
        client._session = session
        obs = run(client.get_klines("BTCUSDT", "15m", 1704067200000, 1704070800000))
        assert len(obs) == 2
        assert obs[0].close == Decimal("42200.0")
        assert obs[1].close == Decimal("42400.0")

    def test_klines_wrapped_dict_code_zero(self):
        """Wrapped envelope with code 0 unwraps and parses rows."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        payload = {"code": 0, "msg": "success", "data": DEVICE_PROBE_KLINES_BARE_ARRAY}
        session = FakeSession([FakeResponse(status=200, payload=payload)])
        client._session = session
        obs = run(client.get_klines("BTCUSDT", "15m", 1704067200000, 1704070800000))
        assert len(obs) == 3
        assert obs[0].close == Decimal("42200.0")

    def test_klines_wrapped_dict_without_code(self):
        """Wrapped envelope with data only unwraps and parses rows."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        payload = {"data": DEVICE_PROBE_KLINES_BARE_ARRAY}
        session = FakeSession([FakeResponse(status=200, payload=payload)])
        client._session = session
        obs = run(client.get_klines("BTCUSDT", "15m", 1704067200000, 1704070800000))
        assert len(obs) == 3

    def test_klines_wrapped_dict_nested_list_key(self):
        """Wrapped envelope with data containing list dict unwraps correctly."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        payload = {"code": 0, "data": {"list": DEVICE_PROBE_KLINES_BARE_ARRAY}}
        session = FakeSession([FakeResponse(status=200, payload=payload)])
        client._session = session
        obs = run(client.get_klines("BTCUSDT", "15m", 1704067200000, 1704070800000))
        assert len(obs) == 3

    def test_klines_legitimate_empty_bare_array_200(self):
        """Legitimate HTTP 200 with bare [] indicates end-of-history for cell."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([FakeResponse(status=200, payload=[])])
        client._session = session
        obs = run(client.get_klines("BTCUSDT", "15m", 1704067200000, 1704070800000))
        assert obs == []

    def test_klines_legitimate_wrapped_empty_data_200(self):
        """Legitimate HTTP 200 with {"data": []} indicates end-of-history for cell."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([FakeResponse(status=200, payload={"code": 0, "data": []})])
        client._session = session
        obs = run(client.get_klines("BTCUSDT", "15m", 1704067200000, 1704070800000))
        assert obs == []

    def test_open_interest_bare_object_real_device_payload(self):
        """Live probe: GET /quote/v1/openInterest returns bare object without envelope."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([FakeResponse(status=200, payload=DEVICE_PROBE_OPEN_INTEREST_BARE_OBJECT)])
        client._session = session
        oi = run(client.get_open_interest("BTCUSDT", "15m"))
        assert oi == Decimal("12345.67")

    def test_open_interest_bare_object_oi_key(self):
        """Bare object with 'oi' key parses correctly."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([FakeResponse(status=200, payload={"oi": "9876.54"})])
        client._session = session
        oi = run(client.get_open_interest("BTCUSDT", "15m"))
        assert oi == Decimal("9876.54")

    def test_open_interest_wrapped_dict(self):
        """Wrapped envelope for openInterest unwraps correctly."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([FakeResponse(status=200, payload={"code": 0, "data": {"openInterest": "9876.54"}})])
        client._session = session
        oi = run(client.get_open_interest("BTCUSDT", "15m"))
        assert oi == Decimal("9876.54")

    def test_depth_bare_object_real_device_payload(self):
        """GET /quote/v1/depth bare object returns dict."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([FakeResponse(status=200, payload=DEVICE_PROBE_DEPTH_BARE_OBJECT)])
        client._session = session
        depth = run(client.get_depth("BTCUSDT"))
        assert depth["bids"] == [["42200.0", "1.5"], ["42190.0", "2.0"]]
        assert depth["asks"] == [["42210.0", "1.2"], ["42220.0", "3.0"]]

    def test_depth_wrapped_dict(self):
        """GET /quote/v1/depth wrapped dict unwraps data."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([FakeResponse(status=200, payload={"code": 0, "data": DEVICE_PROBE_DEPTH_BARE_OBJECT})])
        client._session = session
        depth = run(client.get_depth("BTCUSDT"))
        assert depth["bids"] == [["42200.0", "1.5"], ["42190.0", "2.0"]]

    def test_funding_rate_bare_array_real_device_payload(self):
        """GET /api/v1/futures/fundingRate bare array returns rate and alert."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([FakeResponse(status=200, payload=DEVICE_PROBE_FUNDING_RATE_BARE_ARRAY)])
        client._session = session
        rate, alert = run(client.get_funding_rate("BTCUSDT"))
        assert rate == Decimal("0.0015")
        assert alert is True

    def test_funding_rate_bare_dict(self):
        """GET /api/v1/futures/fundingRate bare dict returns rate."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        session = FakeSession([FakeResponse(status=200, payload={"fundingRate": "0.0002"})])
        client._session = session
        rate, alert = run(client.get_funding_rate("BTCUSDT"))
        assert rate == Decimal("0.0002")
        assert alert is False


# ---------------------------------------------------------------------------
# CP-10 Hotfix: Rate limit -1003 on 200 + Non-zero error codes fail closed
# ---------------------------------------------------------------------------

class TestRateLimitAndErrorHandling:
    """Verifies -1003-on-200 preserves error markers for bootstrap backoff,
    and non-zero error codes fail closed without returning empty rows."""

    def test_rate_limit_1003_on_200_raises_toobit_public_error_with_marker(self):
        """HTTP 200 with code -1003 must raise ToobitPublicError whose message
        contains -1003 and the error msg."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        payload = {"code": -1003, "msg": "Too many requests"}
        session = FakeSession([FakeResponse(status=200, payload=payload) for _ in range(3)])
        client._session = session
        async def fake_sleep(sec):
            pass
        orig = asyncio.sleep
        try:
            asyncio.sleep = fake_sleep
            with pytest.raises(ToobitPublicError) as excinfo:
                run(client.get_klines("BTCUSDT", "15m", 1704067200000, 1704070800000))
        finally:
            asyncio.sleep = orig
        err_msg = str(excinfo.value)
        assert "-1003" in err_msg
        assert "Too many requests" in err_msg

    def test_rate_limit_1003_on_200_bootstrap_maps_to_backoff(self):
        """Assert bootstrap_service.ToobitKlineSource catches -1003 from HTTP 200
        and maps it to rate limit backoff (W.6: -1003 backoff, never a skip)."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        client._attempts = 1
        payload = {"code": -1003, "msg": "Too many requests"}
        session = FakeSession([FakeResponse(status=200, payload=payload)])
        client._session = session

        bridge = AsyncBridge().start()
        try:
            source = ToobitKlineSource(client=client, bridge=bridge)
            result = source("BTCUSDT", "1h", 1704067200000, 1704070800000)
            assert result["code"] == -1003
            assert result["rows"] == []
            assert result["next_cursor_ms"] is None
            assert result["oi_available"] is False
            assert source.rate_limited >= 1
        finally:
            bridge.close()

    def test_non_zero_error_code_never_yields_empty_rows(self):
        """Non-zero business code (e.g. -1120) must fail closed as named error
        and NEVER collapse into empty rows (which would mark cell COMPLETE)."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        client._attempts = 1
        payload = {"code": -1120, "msg": "Invalid interval"}
        session = FakeSession([FakeResponse(status=200, payload=payload)])
        client._session = session

        # 1. Direct call raises ToobitPublicError with -1120 in message
        with pytest.raises(ToobitPublicError) as excinfo:
            run(client.get_klines("BTCUSDT", "15m", 1704067200000, 1704070800000))
        assert "-1120" in str(excinfo.value)
        assert "Invalid interval" in str(excinfo.value)

        # 2. Seam: ToobitKlineSource must raise BootstrapError(FETCH_FAILED), NEVER return empty rows
        bridge = AsyncBridge().start()
        try:
            client._session = FakeSession([FakeResponse(status=200, payload=payload)])
            source = ToobitKlineSource(client=client, bridge=bridge)
            with pytest.raises(BootstrapError) as b_exc:
                source("BTCUSDT", "1h", 1704067200000, 1704070800000)
            assert b_exc.value.reason == "FETCH_FAILED"
            assert "-1120" in str(b_exc.value)
        finally:
            bridge.close()

    def test_positive_error_code_never_yields_empty_rows(self):
        """Positive error code (e.g. 1001) must fail closed, never return empty rows."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        client._attempts = 1
        payload = {"code": 1001, "msg": "Internal venue error"}
        session = FakeSession([FakeResponse(status=200, payload=payload)])
        client._session = session

        bridge = AsyncBridge().start()
        try:
            source = ToobitKlineSource(client=client, bridge=bridge)
            with pytest.raises(BootstrapError) as b_exc:
                source("BTCUSDT", "1h", 1704067200000, 1704070800000)
            assert b_exc.value.reason == "FETCH_FAILED"
            assert "1001" in str(b_exc.value)
        finally:
            bridge.close()

    def test_unexpected_shape_fails_closed(self):
        """Dict without list/klines or data raises ToobitPublicError, never empty rows."""
        client = ToobitPublicClient()
        client.base_url = "http://fake"
        client._attempts = 1
        session = FakeSession([FakeResponse(status=200, payload={"unexpected_key": 123})])
        client._session = session
        with pytest.raises(ToobitPublicError) as excinfo:
            run(client.get_klines("BTCUSDT", "15m", 1704067200000, 1704070800000))
        assert "unexpected response shape" in str(excinfo.value)

    def test_unwrap_toobit_response_all_shapes(self):
        """Direct unit verification of unwrap_toobit_response helper."""
        # Bare list
        assert unwrap_toobit_response([1, 2, 3]) == [1, 2, 3]
        assert unwrap_toobit_response([]) == []
        # Bare dict
        assert unwrap_toobit_response({"openInterest": "100"}) == {"openInterest": "100"}
        # Wrapped dict with code 0
        assert unwrap_toobit_response({"code": 0, "data": [1, 2]}) == [1, 2]
        # Wrapped dict with "data" only
        assert unwrap_toobit_response({"data": {"val": 1}}) == {"val": 1}
        # Error dict with non-zero code
        with pytest.raises(ToobitPublicError) as e1:
            unwrap_toobit_response({"code": -1003, "msg": "Too many requests"}, "test")
        assert "-1003" in str(e1.value)
        assert "Too many requests" in str(e1.value)
        with pytest.raises(ToobitPublicError) as e2:
            unwrap_toobit_response({"code": -1120, "msg": "Invalid interval"}, "test")
        assert "-1120" in str(e2.value)
