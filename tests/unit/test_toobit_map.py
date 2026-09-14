"""CP-7 wire map tests — T_MATCH (Ch.16 L16843–16910 + params/toobit_wire_v1).

Every literal asserted here is copied from the blueprint: the Core-10 symbol
map, the 14-interval map (``1mo → 1M``, all others identical), the FOUR sides,
exactly five adapter operations (never a sixth), the Wave-Out forbidden
operations, the order-type/TIF table (MARKET forbidden), the business-code
classification table (0/200 success, −1003 backoff 1/2/4 s, −1022 abort,
−1120 interval-unsupported for that symbol/TF only, timeout/−1006/−1007/−1146/
−1147 → UNKNOWN + reconcile + NO resubmit), the unmapped-code fail-closed rule
(−1021 and −2026 are NOT in the blueprint ⇒ UNKNOWN + RECOVERY_REQUIRED,
ISSUE-CP7-001), the leverage min-over-ALL-caps law, and the Y.3 numerical
floor (quantize, never round up).
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from apex.data_catalog.contracts import CORE10_SYMBOLS, TIMEFRAMES_14
from apex.errors import WaveOutError
from apex.execution import toobit_map as M


class TestSymbolAndIntervalMap:
    """Ch.16 L16866–16872 + params/toobit_wire_v1 symbol/interval tables."""

    @pytest.mark.parametrize("internal,wire", sorted(M.SYMBOL_MAP.items()))
    def test_symbol_map_exact(self, internal, wire):
        assert M.to_wire_symbol(internal) == wire
        assert M.to_internal_symbol(wire) == internal

    def test_symbol_map_is_exactly_core10(self):
        assert set(M.SYMBOL_MAP) == set(CORE10_SYMBOLS)
        assert len(M.SYMBOL_MAP) == 10

    def test_all_wire_symbols_are_swap_usdt(self):
        for wire in M.SYMBOL_MAP.values():
            assert wire.endswith("-SWAP-USDT")

    def test_unknown_symbol_fails_closed(self):
        with pytest.raises(M.ToobitMapError) as exc:
            M.to_wire_symbol("DOGEUSD")
        assert "E-VAL-021" in str(exc.value)

    def test_interval_map_is_only_1mo(self):
        """Only ``1mo → 1M`` differs; every other TF is wire-identical."""
        assert M.INTERVAL_MAP == {"1mo": "1M"}
        assert M.to_wire_interval("1mo") == "1M"
        for tf in TIMEFRAMES_14:
            expected = "1M" if tf == "1mo" else tf
            assert M.to_wire_interval(tf) == expected

    def test_fourteen_timeframes_supported(self):
        assert len(TIMEFRAMES_14) == 14
        assert "3d" not in TIMEFRAMES_14

    def test_3d_is_rejected_not_invented(self):
        """3d is unsupported everywhere (Ch.21 §5.2) — never mapped."""
        with pytest.raises(M.ToobitMapError) as exc:
            M.to_wire_interval("3d")
        assert "E-VAL-022" in str(exc.value)


class TestFiveOperations:
    """Ch.16 L16843–16856: exactly five operations, no sixth."""

    def test_exactly_five_operations(self):
        assert M.FIVE_OPERATIONS == (
            "submit_order", "cancel_order", "query_order_state",
            "query_open_positions", "query_account_margin_health")
        assert len(M.FIVE_OPERATIONS) == 5

    @pytest.mark.parametrize("operation", sorted(M.FIVE_OPERATIONS))
    def test_one_endpoint_per_operation(self, operation):
        method, path = M.endpoint_for(operation)
        assert M.OPERATION_ENDPOINT[operation] == (method, path)

    def test_primary_endpoints_exact(self):
        assert M.OPERATION_ENDPOINT == {
            "submit_order": ("POST", "/api/v1/futures/order"),
            "cancel_order": ("DELETE", "/api/v1/futures/order"),
            "query_order_state": ("GET", "/api/v1/futures/order"),
            "query_open_positions": ("GET", "/api/v1/futures/positions"),
            "query_account_margin_health": ("GET", "/api/v1/futures/balance")}

    def test_auxiliary_paths_bound_to_operations_only(self):
        """ISSUE-CP7-002: the 11 signed Wave-In paths exist, but each
        auxiliary path is bound to one of the five operations — never exposed
        as a sixth operation."""
        assert M.auxiliary_paths_for("cancel_order") == (
            ("DELETE", "/api/v1/futures/batchOrders"),)
        assert M.auxiliary_paths_for("query_order_state") == (
            ("GET", "/api/v1/futures/openOrders"),
            ("GET", "/api/v1/futures/userTrades"))
        assert M.auxiliary_paths_for("query_account_margin_health") == (
            ("POST", "/api/v1/futures/leverage"),
            ("POST", "/api/v1/futures/marginType"),
            ("GET", "/api/v1/futures/commissionRate"))
        assert M.auxiliary_paths_for("submit_order") == ()
        assert M.auxiliary_paths_for("query_open_positions") == ()
        with pytest.raises(M.ToobitMapError):
            M.auxiliary_paths_for("sixth_operation")

    def test_wire_lists_are_6_public_and_11_signed(self):
        assert len(M.PUBLIC_ENDPOINTS) == 6
        assert len(M.SIGNED_ENDPOINTS) == 11
        wire = M.wire_endpoints()
        assert wire["base_url"] == "https://api.toobit.com"
        assert wire["header_api_key"] == "X-BB-APIKEY"
        assert wire["recv_window_ms"] == 5000
        assert wire["auth_scheme"] == "HMAC-SHA256"

    def test_unlisted_path_is_never_requested(self):
        with pytest.raises(M.ToobitMapError) as exc:
            M.assert_path_permitted("POST", "/api/v1/futures/withdraw")
        assert "TOOBIT_PATH_NOT_LISTED" in str(exc.value)

    @pytest.mark.parametrize("operation", sorted(M.FORBIDDEN_OPERATIONS))
    def test_forbidden_operations_are_wave_out(self, operation):
        with pytest.raises(WaveOutError):
            M.endpoint_for(operation)

    def test_unknown_operation_fails_closed(self):
        with pytest.raises(M.ToobitMapError) as exc:
            M.endpoint_for("place_iceberg")
        assert "ADAPTER_OPERATION_UNKNOWN" in str(exc.value)


class TestSidesAndOrderDefaults:
    """Ch.16 L16873–16896 side map + order type/TIF table."""

    def test_four_sides_exactly(self):
        assert M.SIDES == frozenset({"BUY_OPEN", "SELL_OPEN", "BUY_CLOSE",
                                     "SELL_CLOSE"})
        assert M.SIDE_MAP == {"LONG_entry": "BUY_OPEN",
                              "SHORT_entry": "SELL_OPEN",
                              "LONG_flatten": "SELL_CLOSE",
                              "SHORT_flatten": "BUY_CLOSE"}

    @pytest.mark.parametrize("direction,phase,side", [
        ("LONG", "entry", "BUY_OPEN"), ("SHORT", "entry", "SELL_OPEN"),
        ("LONG", "flatten", "SELL_CLOSE"), ("SHORT", "flatten", "BUY_CLOSE")])
    def test_side_for(self, direction, phase, side):
        assert M.side_for(direction, phase) == side

    def test_order_defaults_governed_table(self):
        """Ch.16 L16896–16905 governed defaults (Entry LIMIT/IOC at INPUT
        price; Stop STOP/MARKET; Target LIMIT/GTC)."""
        assert M.order_defaults("entry") == {"type": "LIMIT", "tif": "IOC",
                                             "price_type": "INPUT"}
        assert M.order_defaults("stop") == {"type": "STOP",
                                            "price_type": "MARKET"}
        assert M.order_defaults("target") == {"type": "LIMIT", "tif": "GTC"}

    def test_market_order_type_is_forbidden(self):
        assert M.FORBIDDEN_ORDER_TYPE == "MARKET"
        with pytest.raises(M.ToobitMapError) as exc:
            M.assert_order_type_permited("MARKET")
        assert "ORDER_TYPE_FORBIDDEN" in str(exc.value)

    def test_account_mode_isolated_oneway_only(self):
        assert M.MARGIN_MODE == "ISOLATED"
        assert M.POSITION_MODE == "ONE_WAY"
        assert M.assert_account_mode("ISOLATED", "ONE_WAY") is None
        with pytest.raises(WaveOutError):
            M.assert_account_mode("CROSS", "ONE_WAY")
        with pytest.raises(WaveOutError):
            M.assert_account_mode("ISOLATED", "HEDGE")


class TestBusinessCodeClassification:
    """Ch.16 L16861–16898 classification table (T_MATCH)."""

    @pytest.mark.parametrize("code", [0, 200])
    def test_success_requires_code_and_http_200(self, code):
        verdict = M.classify_business_code(code, http_status=200)
        assert verdict["classification"] == M.CODE_OK
        assert verdict["fsm_effect"] == "ACKNOWLEDGED"
        assert verdict["resubmit"] is False
        assert verdict["reconcile"] is False

    def test_success_code_with_non_200_http_is_unknown(self):
        """L16898: success = HTTP 200 **and** business code ∈ {0,200}."""
        verdict = M.classify_business_code(0, http_status=500)
        assert verdict["classification"] == M.CODE_UNKNOWN
        assert verdict["reconcile"] is True
        assert verdict["resubmit"] is False

    def test_backoff_code_is_1003_with_1_2_4(self):
        assert M.BACKOFF_CODE == -1003
        verdict = M.classify_business_code(-1003, http_status=429)
        assert verdict["classification"] == M.CODE_BACKOFF
        assert verdict["backoff_seconds"] in (1.0, [1.0, 2.0, 4.0])
        assert verdict["resubmit"] is True
        assert M.RETRY_ATTEMPTS == 3
        assert M.RETRY_BACKOFF_SECONDS == (1.0, 2.0, 4.0)

    def test_retry_policy_is_never_silent(self):
        policy = M.retry_policy()
        assert policy["attempts"] == 3
        assert policy["backoff_seconds"] == [1.0, 2.0, 4.0]
        assert policy["unique_key_per_attempt"] is True
        assert policy["silent"] is False
        assert policy["never_resubmit_on"] == ("UNKNOWN", "UNMAPPED", "ABORT")

    def test_abort_code_is_1022_no_retry(self):
        assert M.ABORT_CODE == -1022
        verdict = M.classify_business_code(-1022, http_status=400)
        assert verdict["classification"] == M.CODE_ABORT
        assert verdict["fsm_effect"] == "REJECTED"
        assert verdict["resubmit"] is False

    def test_interval_unsupported_code_is_1120(self):
        assert M.INTERVAL_UNSUPPORTED_CODE == -1120
        verdict = M.classify_business_code(-1120, http_status=400)
        assert verdict["classification"] == M.CODE_INTERVAL_UNSUPPORTED
        assert verdict["fsm_effect"] == "REJECTED"
        record = M.interval_disabled_record("BTCUSDT", "1mo", -1120)
        assert record["scope"] == "SYMBOL_TIMEFRAME_ONLY"
        assert record["symbol"] == "BTCUSDT"
        assert record["timeframe"] == "1mo"
        assert record["universe_cells_remaining"] == 139

    @pytest.mark.parametrize("code", sorted(M.UNKNOWN_OUTCOME_CODES))
    def test_unknown_outcome_codes_never_resubmit(self, code):
        """−1006/−1007/−1146/−1147 + timeout → UNKNOWN, reconcile, no
        resubmit (L16898)."""
        verdict = M.classify_business_code(code, http_status=400)
        assert verdict["classification"] == M.CODE_UNKNOWN
        assert verdict["reconcile"] is True
        assert verdict["resubmit"] is False
        assert verdict["fsm_effect"] == "RECOVERY_REQUIRED"

    def test_timeout_is_unknown_and_never_resubmits(self):
        verdict = M.classify_business_code(None, timeout=True)
        assert verdict["classification"] == M.CODE_UNKNOWN
        assert verdict["resubmit"] is False
        assert verdict["reconcile"] is True

    @pytest.mark.parametrize("code", sorted(M.UNDOCUMENTED_CODES))
    def test_undocumented_codes_fail_closed(self, code):
        """ISSUE-CP7-001: −1021 and −2026 appear nowhere in the blueprint, so
        they are UNMAPPED → UNKNOWN + RECOVERY_REQUIRED. Invented semantics are
        prohibited (L16861–16863)."""
        assert M.UNDOCUMENTED_CODES == (-1021, -2026)
        verdict = M.classify_business_code(code, http_status=400)
        assert verdict["classification"] == M.CODE_UNMAPPED
        assert verdict["fsm_effect"] == "RECOVERY_REQUIRED"
        assert verdict["resubmit"] is False
        assert verdict["reconcile"] is True

    def test_arbitrary_unmapped_code_fails_closed(self):
        verdict = M.classify_business_code(-99999, http_status=400)
        assert verdict["classification"] == M.CODE_UNMAPPED
        assert verdict["resubmit"] is False

    def test_outcome_classes_are_exactly_six(self):
        assert M.ADAPTER_OUTCOMES == frozenset(
            {"ACKNOWLEDGED", "PARTIAL", "FILLED", "REJECTED", "CANCELLED",
             "UNKNOWN"})

    @pytest.mark.parametrize("status,outcome", sorted(
        M.EXCHANGE_STATUS_MAP.items()))
    def test_exchange_status_map(self, status, outcome):
        assert M.exchange_status_to_outcome(status)["outcome"] == outcome

    def test_unmapped_exchange_status_is_unknown_reconcile(self):
        verdict = M.exchange_status_to_outcome("SOMETHING_NEW")
        assert verdict["outcome"] == "UNKNOWN"
        assert verdict["reconcile_before_action"] is True


class TestLeverageMinOverAllCaps:
    """Ch.16 L16900 + Y.2 L17405–17423 (T_MONOTONE)."""

    def test_tf_caps_exact(self):
        assert M.LEVERAGE_CAP_BY_TF == {
            "1m": 2, "3m": 2, "5m": 2, "15m": 3, "30m": 3, "1h": 4, "2h": 4,
            "4h": 4, "6h": 5, "8h": 5, "12h": 5, "1d": 5, "1w": 5, "1mo": 5}

    def test_exchange_max_per_symbol(self):
        assert M.EXCHANGE_MAX_LEVERAGE["BTCUSDT"] == 125
        assert M.EXCHANGE_MAX_LEVERAGE["ETHUSDT"] == 100

    def test_leverage_is_min_over_all_caps_not_last_writer(self):
        resolved = M.resolve_leverage("1mo", symbol="BTCUSDT", owner_cap=3)
        assert resolved["leverage"] == 3.0
        assert resolved["binding_cap"] == "owner_cap"
        assert set(resolved["caps"]) == {"y2_tf_cap", "exchange_max", "owner_cap"}
        # A last-writer policy would end at the LAST cap evaluated; min over
        # ALL caps cannot exceed any single one.
        assert resolved["leverage"] <= min(resolved["caps"].values())

    def test_owner_cap_can_only_lower(self):
        base = M.resolve_leverage("1h", symbol="BTCUSDT")["leverage"]
        tighter = M.resolve_leverage("1h", symbol="BTCUSDT",
                                     owner_cap=base + 10)["leverage"]
        assert tighter == base          # raising the owner cap changes nothing

    def test_never_125x(self):
        for tf in TIMEFRAMES_14:
            for symbol in CORE10_SYMBOLS:
                assert M.resolve_leverage(tf, symbol=symbol)["leverage"] < 125

    def test_unknown_timeframe_fails_closed(self):
        with pytest.raises(M.ToobitMapError):
            M.resolve_leverage("3d", symbol="BTCUSDT")


class TestNumericalFloorAndSigning:
    """Y.3 L17425 numerical floor + Ch.16 L16873 signing."""

    def test_quantity_floors_to_step_never_rounds_up(self):
        assert M.quantize_quantity("BTCUSDT", "0.1239") == Decimal("0.123")
        assert M.quantize_quantity("XRPUSDT", "1.9") == Decimal("1")
        assert M.QUANTITY_STEP["BTCUSDT"] == "0.001"

    def test_price_floors_to_tick(self):
        assert M.quantize_price("BTCUSDT", "100.19") == Decimal("100.1")
        assert M.TICK_SIZE["BTCUSDT"] == "0.1"

    def test_min_notional_gate(self):
        assert M.MIN_NOTIONAL["BTCUSDT"] == "5"
        ok = M.check_min_notional("BTCUSDT", "100", "0.10")
        assert ok["passes"] is True
        bad = M.check_min_notional("BTCUSDT", "100", "0.01")
        assert bad["passes"] is False
        assert bad["reason"] is not None

    def test_money_stays_decimal_text(self):
        assert isinstance(M.quantize_quantity("BTCUSDT", "1"), Decimal)
        assert str(M.quantize_quantity("BTCUSDT", "1")) == "1"

    def test_signed_query_is_hmac_sha256_with_recv_window(self):
        query = M.build_signed_query({"symbol": "BTC-SWAP-USDT"},
                                     timestamp_ms=1767225600000)
        assert "timestamp=1767225600000" in query
        assert "recvWindow=5000" in query
        signature = M.sign_query("secret", query)
        assert len(signature) == 64
        assert signature == M.sign_query("secret", query)   # deterministic
        assert signature != M.sign_query("other", query)

    def test_signed_request_descriptor_never_carries_the_secret(self):
        request = M.signed_request("POST", "/api/v1/futures/order",
                                   {"symbol": "BTC-SWAP-USDT",
                                    "side": "BUY_OPEN"},
                                   api_key="KEY", api_secret="SECRET",
                                   timestamp_ms=1767225600000)
        assert request["url"] == "https://api.toobit.com/api/v1/futures/order"
        assert request["headers"]["X-BB-APIKEY"] == "KEY"
        assert request["query"].endswith(f"signature={request['signature']}")
        assert "SECRET" not in str(request)

    def test_idempotency_key_is_sha256_of_four_fields(self):
        key = M.execution_idempotency_key("intent", "order", "ts", "nonce")
        assert len(key) == 64
        assert key == M.execution_idempotency_key("intent", "order", "ts",
                                                  "nonce")
        assert key != M.execution_idempotency_key("intent2", "order", "ts",
                                                  "nonce")
        with pytest.raises(M.ToobitMapError):
            M.execution_idempotency_key("", None, "ts", "nonce")

    def test_order_submission_ttl_is_60_seconds(self):
        assert M.ORDER_SUBMISSION_TTL_SECONDS == 60
        assert M.POSITION_TRANSITION_TTL_SECONDS == 30
        assert M.TELEGRAM_IDEMPOTENCY_TTL_SECONDS == 86400
        assert M.KLINE_LIMIT == 1000


class TestRolloverAndFunding:
    """Ch.16 rollover guard (7 days) + funding alert threshold."""

    def test_rollover_blocks_inside_seven_days(self):
        assert M.ROLLOVER_MIN_DAYS == 7
        blocked = M.rollover_entry_allowed(2)
        assert blocked["allowed"] is False
        assert blocked["reason"] == "CONTRACT_EXPIRY"
        assert blocked["veto"] == 13

    def test_rollover_allowed_outside_seven_days(self):
        assert M.rollover_entry_allowed(9)["allowed"] is True

    def test_perpetual_has_no_expiry(self):
        assert M.rollover_entry_allowed(None)["reason"] == "PERPETUAL_NO_EXPIRY"

    def test_funding_alert_threshold(self):
        assert M.FUNDING_ALERT_THRESHOLD == 0.001
        assert M.funding_alert(0.0009)["alert"] is False
        extreme = M.funding_alert(0.02)
        assert extreme["alert"] is True
        assert extreme["is_veto"] is False      # a cost alert, not a veto
