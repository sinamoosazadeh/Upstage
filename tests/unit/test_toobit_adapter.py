"""CP-7 venue adapter tests — T_ADAPTER_SUBMIT / T_ADAPTER_DUPLICATE /
T_ADAPTER_LOST_ACK, the five-operations law, "no silent retries", the wire-map
conformance fixture, adapter-owned state immutability, signed-endpoint
fail-closed gating and the AI.8 rate bucket.

The venue is a TEST DOUBLE (``tests/fake_toobit_responder.py``): no network, no
real credentials, nothing outside the sandbox (G9).
"""
from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
from pathlib import Path

import pytest

from apex.errors import WaveOutError
from apex.execution import toobit_adapter as A
from apex.execution import toobit_map as M
from apex.identity.canonical_json import canonical_json

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / \
    "toobit_adapter_conformance.json"

TEST_KEY = "TEST_KEY_CP7"
TEST_SECRET = "TEST_SECRET_CP7"
UTC = lambda: "2026-01-01T00:00:00.000Z"          # noqa: E731 (fixture clock)


def run(coro):
    return asyncio.run(coro)


def load_fixture():
    return json.loads(FIXTURE.read_text())


def make_adapter(monkeypatch, responder, *, allow_signed=True, key=TEST_KEY,
                 secret=TEST_SECRET, clock=None):
    monkeypatch.setenv("APEX_ENV", "PAPER")
    monkeypatch.setenv("APEX_ALLOW_SIGNED", "1" if allow_signed else "0")
    if key:
        monkeypatch.setenv("TOOBIT_API_KEY", key)
    else:
        monkeypatch.delenv("TOOBIT_API_KEY", raising=False)
    if secret:
        monkeypatch.setenv("TOOBIT_API_SECRET", secret)
    else:
        monkeypatch.delenv("TOOBIT_API_SECRET", raising=False)
    from apex.config import Config
    from fake_toobit_responder import FakeToobitResponder
    assert isinstance(responder, FakeToobitResponder)
    return A.ToobitAdapter(config=Config(), transport=responder, utc_now=UTC,
                           clock=clock if clock is not None else (lambda: 1000.0))


def apply_scenario(responder, scenario):
    from fake_toobit_responder import FakeToobitResponder
    assert isinstance(responder, FakeToobitResponder)
    if "fill_mode" in scenario:
        responder.set_fill_mode(scenario["fill_mode"],
                                price=scenario.get("fill_price"))
    if scenario.get("timeouts"):
        responder.lose_next_ack(scenario["timeouts"],
                                record=scenario.get("record_before_timeout",
                                                   True))
    if scenario.get("fail_with") is not None:
        responder.fail_next(scenario["fail_with"], scenario.get("fail_times", 1))
    for order in scenario.get("seed_orders", []):
        responder.seed_order(**order)
    if scenario.get("seed_position"):
        responder.seed_position(**scenario["seed_position"])


OPERATION_CALLS = {
    "submit_order": lambda adapter, call: adapter.submit_order(**call),
    "cancel_order": lambda adapter, call: adapter.cancel_order(**call),
    "query_order_state": lambda adapter, call: adapter.query_order_state(**call),
    "query_open_positions": lambda adapter, call:
        adapter.query_open_positions(**call),
    "query_account_margin_health": lambda adapter, call:
        adapter.query_account_margin_health(**call),
}


# ---------------------------------------------------------------------------
# Golden conformance fixture
# ---------------------------------------------------------------------------

class TestConformanceFixture:
    def test_fixture_is_hash_sealed(self):
        """The golden file is tamper-evident: its ``cases`` array must hash to
        the recorded SHA-256 (Ch.4/Ch.16 hash-chain law applied to fixtures)."""
        payload = load_fixture()
        digest = hashlib.sha256(
            canonical_json(payload["cases"]).encode("utf-8")).hexdigest()
        assert digest == payload["_meta"]["cases_sha256"]
        assert payload["_meta"]["case_count"] == len(payload["cases"])

    def test_fixture_covers_every_operation(self):
        operations = {c["operation"] for c in load_fixture()["cases"]}
        assert operations == set(M.FIVE_OPERATIONS)

    @pytest.mark.parametrize("case", load_fixture()["cases"],
                             ids=[c["id"] for c in load_fixture()["cases"]])
    def test_case(self, case, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        apply_scenario(responder, case.get("scenario", {}))
        calls = case.get("calls") or [case["call"]]
        posts_before = len(responder.calls_to("/api/v1/futures/order", "POST"))
        result = None
        for call in calls:
            result = run(OPERATION_CALLS[case["operation"]](adapter, call))
        observed = result.to_dict()
        for key, expected in case["expect"].items():
            if key == "attempts":
                assert len(result.attempts) == expected, case["id"]
            elif key == "attempt_sources":
                assert [a.result_source for a in result.attempts] == expected, \
                    case["id"]
            elif key == "unique_idempotency_keys":
                keys = [a.idempotency_key for a in result.attempts]
                assert expected is (len(set(keys)) == len(keys)), case["id"]
            elif key == "interval_disabled":
                assert dict(result.interval_disabled or {}) == expected, case["id"]
            else:
                assert observed[key] == expected, f"{case['id']}.{key}"
        venue = case.get("expect_venue")
        if venue:
            if "posts_to_order_endpoint" in venue:
                assert len(responder.calls_to("/api/v1/futures/order", "POST")) \
                    - posts_before == venue["posts_to_order_endpoint"], case["id"]
            if "signature_violations" in venue:
                assert len(responder.signature_violations()) == \
                    venue["signature_violations"], case["id"]
            if "request_params" in venue:
                sent = responder.calls_to("/api/v1/futures/order", "POST")[-1].params
                for key, value in venue["request_params"].items():
                    assert sent.get(key) == value, f"{case['id']}.{key}"
            if "venue_recorded_client_order_id" in venue:
                assert venue["venue_recorded_client_order_id"] in responder.orders
            if "leverage_sent_for_BTCUSDT" in venue:
                assert responder.leverage["BTC-SWAP-USDT"] == \
                    venue["leverage_sent_for_BTCUSDT"], case["id"]
        state = case.get("expect_state")
        if state and "disabled_intervals" in state:
            assert {k: list(v) for k, v in
                    adapter.disabled_intervals().items()} == \
                state["disabled_intervals"], case["id"]


# ---------------------------------------------------------------------------
# Exactly five operations
# ---------------------------------------------------------------------------

class TestFiveOperationsLaw:
    def test_adapter_exposes_exactly_five_operations(self):
        assert A.ToobitAdapter.OPERATIONS == M.FIVE_OPERATIONS
        assert len(A.ToobitAdapter.OPERATIONS) == 5

    @pytest.mark.parametrize("operation", sorted(M.FIVE_OPERATIONS))
    def test_each_operation_is_a_public_coroutine(self, operation):
        method = getattr(A.ToobitAdapter, operation)
        assert asyncio.iscoroutinefunction(method)

    @pytest.mark.parametrize("forbidden", sorted(M.FORBIDDEN_OPERATIONS))
    def test_no_forbidden_operation_exists_on_the_adapter(self, forbidden):
        """withdraw / transfer / flashClose / reversePosition /
        auto_add_margin are Wave-Out: the adapter must not even have them."""
        for alias in (forbidden, forbidden.lower(),
                      forbidden.replace("flashClose", "flash_close")
                      .replace("reversePosition", "reverse_position")
                      .replace("auto_add_margin", "auto_add_margin")):
            assert not hasattr(A.ToobitAdapter, alias)

    def test_no_sixth_operation_method(self):
        public = {name for name in dir(A.ToobitAdapter)
                  if not name.startswith("_")
                  and asyncio.iscoroutinefunction(getattr(A.ToobitAdapter, name))}
        assert public == set(M.FIVE_OPERATIONS)

    def test_unlisted_path_is_never_requested(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        run(adapter.submit_order(intent_id="i-1", symbol="BTCUSDT",
                                 timeframe="1h", direction="LONG",
                                 quantity="0.1", price="100"))
        listed = set(M.PUBLIC_ENDPOINTS) | set(M.SIGNED_ENDPOINTS)
        for call in responder.calls:
            assert f"{call.method} {call.path}" in listed


# ---------------------------------------------------------------------------
# No silent retries
# ---------------------------------------------------------------------------

class TestNoSilentRetries:
    def test_backoff_retries_are_audited_with_unique_keys(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        responder.fail_next(-1003, 2)
        result = run(adapter.submit_order(intent_id="i-retry", symbol="BTCUSDT",
                                          timeframe="1h", direction="LONG",
                                          quantity="0.1", price="100"))
        assert len(result.attempts) == A.RETRY_ATTEMPTS == 3
        assert [a.attempt_no for a in result.attempts] == [1, 2, 3]
        keys = [a.idempotency_key for a in result.attempts]
        assert len(set(keys)) == 3          # a unique key per attempt
        assert all(a.actor for a in result.attempts)
        assert result.resubmitted is True
        assert len(responder.calls_to("/api/v1/futures/order", "POST")) == 3

    def test_never_more_than_three_attempts(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        responder.fail_next(-1003, 99)      # a persistent backoff code
        result = run(adapter.submit_order(intent_id="i-many", symbol="BTCUSDT",
                                          timeframe="1h", direction="LONG",
                                          quantity="0.1", price="100"))
        assert len(result.attempts) == 3
        assert len(responder.calls_to("/api/v1/futures/order", "POST")) == 3
        assert result.ok is False

    def test_unknown_and_abort_never_retry(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        for code in (-1022, -1021, -2026, -1006, -1146):
            responder.fail_next(code, 1)
            result = run(adapter.submit_order(
                intent_id=f"i-{abs(code)}", symbol="BTCUSDT", timeframe="1h",
                direction="LONG", quantity="0.1", price="100"))
            assert len(result.attempts) == 1, code
            assert result.resubmitted is False, code

    def test_audit_trail_is_an_immutable_tuple_view(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        run(adapter.submit_order(intent_id="i-audit", symbol="BTCUSDT",
                                 timeframe="1h", direction="LONG",
                                 quantity="0.1", price="100"))
        trail = adapter.audit_trail()
        assert isinstance(trail, tuple) and trail
        with pytest.raises(TypeError):
            trail[0] = None


# ---------------------------------------------------------------------------
# Adapter-owned state is immutable to callers
# ---------------------------------------------------------------------------

class TestAdapterStateProtection:
    @pytest.mark.parametrize("attribute", sorted(A._STATE_ATTRS))
    def test_callers_cannot_mutate_adapter_state(self, attribute, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        with pytest.raises(A.AdapterStateMutationError):
            setattr(adapter, attribute, {})

    def test_state_view_is_read_only(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        state = adapter.state
        with pytest.raises(dataclasses.FrozenInstanceError):
            state.environment = "LIVE"
        with pytest.raises(TypeError):
            state.disabled_intervals["BTCUSDT"] = ("1h",)
        assert state.environment == "PAPER"
        assert state.signed_allowed is True

    @pytest.mark.parametrize("cls", [A.AdapterResult, A.AttemptRecord,
                                     A.AdapterState, A.TokenBucketState])
    def test_result_types_are_frozen(self, cls):
        assert cls.__dataclass_params__.frozen is True

    def test_interval_registry_is_written_only_by_the_adapter(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        responder.fail_next(-1120, 1)
        run(adapter.submit_order(intent_id="i-1120", symbol="BTCUSDT",
                                 timeframe="1mo", direction="LONG",
                                 quantity="0.1", price="100"))
        assert adapter.is_interval_disabled("BTCUSDT", "1mo") is True
        assert adapter.is_interval_disabled("BTCUSDT", "1h") is False
        assert adapter.is_interval_disabled("ETHUSDT", "1mo") is False
        with pytest.raises(TypeError):
            adapter.disabled_intervals()["BTCUSDT"] = ("1h",)
        # the disabled cell is refused LOCALLY — never sent again
        posts = len(responder.calls_to("/api/v1/futures/order", "POST"))
        refused = run(adapter.submit_order(intent_id="i-1120b", symbol="BTCUSDT",
                                           timeframe="1mo", direction="LONG",
                                           quantity="0.1", price="100"))
        assert refused.classification == "REFUSED"
        assert refused.error_code == "TF_DISABLED_FOR_SYMBOL"
        assert len(responder.calls_to("/api/v1/futures/order", "POST")) == posts


# ---------------------------------------------------------------------------
# Signed-endpoint gating (fail-closed) + secrets
# ---------------------------------------------------------------------------

class TestSignedGating:
    def test_allow_signed_off_refuses_every_signed_call(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder, allow_signed=False)
        with pytest.raises(A.AdapterError) as exc:
            run(adapter.submit_order(intent_id="i-1", symbol="BTCUSDT",
                                     timeframe="1h", direction="LONG",
                                     quantity="0.1", price="100"))
        assert exc.value.reason == "SIGNED_NOT_ALLOWED"
        assert responder.calls == []          # nothing left the process

    @pytest.mark.parametrize("key,secret", [(None, TEST_SECRET),
                                            (TEST_KEY, None), (None, None)])
    def test_missing_credentials_fail_closed(self, monkeypatch, key, secret):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder, key=key, secret=secret)
        with pytest.raises(A.AdapterError) as exc:
            run(adapter.query_open_positions())
        assert exc.value.reason == "TOOBIT_CREDENTIALS_MISSING"
        assert responder.calls == []

    def test_secrets_never_appear_in_results_or_errors(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        result = run(adapter.submit_order(intent_id="i-secret", symbol="BTCUSDT",
                                          timeframe="1h", direction="LONG",
                                          quantity="0.1", price="100"))
        for blob in (json.dumps(result.to_dict(), default=str),
                     str(adapter.audit_trail()), str(adapter.state)):
            assert TEST_SECRET not in blob
            assert TEST_KEY not in blob
        closed = make_adapter(monkeypatch, responder, allow_signed=False)
        with pytest.raises(A.AdapterError) as exc:
            run(closed.query_open_positions())
        assert TEST_SECRET not in str(exc.value)
        assert TEST_KEY not in str(exc.value)

    def test_every_signed_request_is_correctly_signed(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        run(adapter.submit_order(intent_id="i-sign", symbol="BTCUSDT",
                                 timeframe="1h", direction="LONG",
                                 quantity="0.1", price="100"))
        run(adapter.query_open_positions())
        run(adapter.query_account_margin_health())
        assert responder.calls
        assert responder.signature_violations() == []
        for call in responder.calls:
            assert call.params.get("recvWindow") == str(M.RECV_WINDOW_MS)
            assert call.headers[M.HEADER_API_KEY] == TEST_KEY
            assert len(call.params["signature"]) == 64


# ---------------------------------------------------------------------------
# Rate bucket (AI.8 L18749–18775)
# ---------------------------------------------------------------------------

class TestRateBucket:
    def test_bucket_constants_are_the_governed_literals(self):
        assert A.TOOBIT_BUCKET_CAPACITY == 200
        assert A.TOOBIT_BUCKET_REFILL_PER_SECOND == 100.0
        assert A.SUBMISSION_TIMEOUT_SECONDS == 5.0
        assert A.FILL_TIMEOUT_SECONDS == 5.0
        assert A.RATE_LIMIT_QUEUE_TIMEOUT_SECONDS == 5.0

    def test_exhausted_bucket_is_never_dropped_and_never_sends(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        monkeypatch.setattr(A, "RATE_LIMIT_QUEUE_TIMEOUT_SECONDS", 0.02)
        adapter = make_adapter(monkeypatch, responder, clock=lambda: 1000.0)
        endpoint = "POST /api/v1/futures/order"
        for index in range(A.TOOBIT_BUCKET_CAPACITY):
            run(adapter.submit_order(intent_id=f"i-drain-{index}",
                                     symbol="BTCUSDT", timeframe="1h",
                                     direction="LONG", quantity="0.1",
                                     price="100"))
        state = adapter.rate_bucket_state(endpoint)
        assert state.tokens == pytest.approx(0.0, abs=1e-9)
        assert state.capacity == 200.0
        sent = len(responder.calls_to("/api/v1/futures/order", "POST"))
        assert sent == A.TOOBIT_BUCKET_CAPACITY
        exhausted = run(adapter.submit_order(intent_id="i-exhausted",
                                             symbol="BTCUSDT", timeframe="1h",
                                             direction="LONG", quantity="0.1",
                                             price="100"))
        assert exhausted.ok is False
        assert exhausted.classification == "UNKNOWN"
        assert exhausted.outcome == "UNKNOWN"
        assert exhausted.reconcile_required is True
        assert exhausted.error_code == "RATE_LIMIT_QUEUE_TIMEOUT"
        # the request was QUEUED, never sent without a token, never dropped
        assert len(responder.calls_to("/api/v1/futures/order", "POST")) == sent

    def test_bucket_refills_with_the_clock(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        now = [1000.0]
        adapter = make_adapter(monkeypatch, responder, clock=lambda: now[0])
        run(adapter.submit_order(intent_id="i-refill", symbol="BTCUSDT",
                                 timeframe="1h", direction="LONG",
                                 quantity="0.1", price="100"))
        before = adapter.rate_bucket_state("POST /api/v1/futures/order").tokens
        now[0] += 1.0                          # one second ⇒ 100 tokens refilled
        after = adapter.rate_bucket_state("POST /api/v1/futures/order").tokens
        assert after == min(200.0, before + 100.0)


# ---------------------------------------------------------------------------
# Pre-submission refusals (never reach the venue)
# ---------------------------------------------------------------------------

class TestPreSubmissionRefusals:
    def test_intent_id_is_mandatory(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        with pytest.raises(A.AdapterError) as exc:
            run(adapter.submit_order(intent_id="", symbol="BTCUSDT",
                                     timeframe="1h", direction="LONG",
                                     quantity="0.1", price="100"))
        assert exc.value.reason == "INTENT_ID_REQUIRED"
        assert responder.calls == []

    def test_market_order_type_is_refused(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        with pytest.raises(M.ToobitMapError):
            run(adapter.submit_order(intent_id="i-mkt", symbol="BTCUSDT",
                                     timeframe="1h", direction="LONG",
                                     quantity="0.1", price="100",
                                     order_type="MARKET"))
        assert responder.calls == []

    def test_flat_direction_has_no_side(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        with pytest.raises(M.ToobitMapError):
            run(adapter.submit_order(intent_id="i-flat", symbol="BTCUSDT",
                                     timeframe="1h", direction="FLAT",
                                     quantity="0.1", price="100"))
        assert responder.calls == []

    def test_cancel_scope_vocabulary(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        with pytest.raises(A.AdapterError) as exc:
            run(adapter.cancel_order(scope="everything"))
        assert exc.value.reason == "CANCEL_SCOPE_QX"
        assert responder.calls == []

    def test_single_query_needs_an_identity(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        with pytest.raises(A.AdapterError) as exc:
            run(adapter.query_order_state(scope="single"))
        assert exc.value.reason == "QUERY_IDENTITY_REQUIRED"

    def test_query_scope_vocabulary(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        with pytest.raises(A.AdapterError) as exc:
            run(adapter.query_order_state(scope="history"))
        assert exc.value.reason == "QUERY_SCOPE_QX"

    def test_money_and_prices_stay_text_at_the_boundary(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        run(adapter.submit_order(intent_id="i-text", symbol="BTCUSDT",
                                 timeframe="1h", direction="LONG",
                                 quantity="0.1239", price="100.19"))
        sent = responder.calls_to("/api/v1/futures/order", "POST")[-1].params
        assert sent["quantity"] == "0.123"      # Y.3 floor, never round up
        assert sent["price"] == "100.1"
        assert isinstance(sent["quantity"], str)


# ---------------------------------------------------------------------------
# Transport seam
# ---------------------------------------------------------------------------

class TestTransportSeam:
    def test_no_session_is_fail_closed(self):
        transport = A.aiohttp_transport(None)
        with pytest.raises(A.AdapterError) as exc:
            run(transport("POST", "https://api.toobit.com/api/v1/futures/order",
                          "", {}))
        assert exc.value.reason == "TRANSPORT_SESSION_MISSING"

    def test_timeout_becomes_unknown_never_an_exception_to_the_caller(
            self, monkeypatch):
        async def timeout_transport(method, url, query, headers):
            raise A.AdapterTimeout(f"{method} {url}")

        monkeypatch.setenv("APEX_ENV", "PAPER")
        monkeypatch.setenv("APEX_ALLOW_SIGNED", "1")
        monkeypatch.setenv("TOOBIT_API_KEY", TEST_KEY)
        monkeypatch.setenv("TOOBIT_API_SECRET", TEST_SECRET)
        from apex.config import Config
        adapter = A.ToobitAdapter(config=Config(), transport=timeout_transport,
                                  utc_now=UTC, clock=lambda: 1000.0)
        result = run(adapter.submit_order(intent_id="i-timeout", symbol="BTCUSDT",
                                          timeframe="1h", direction="LONG",
                                          quantity="0.1", price="100"))
        assert result.classification == "UNKNOWN"
        assert result.outcome == "UNKNOWN"
        assert result.reconcile_required is True
        assert result.resubmitted is False
        assert len(result.attempts) == 1

    def test_unexpected_transport_fault_is_unknown_not_a_crash(self, monkeypatch):
        async def broken_transport(method, url, query, headers):
            raise RuntimeError("connection reset by peer")

        monkeypatch.setenv("APEX_ENV", "PAPER")
        monkeypatch.setenv("APEX_ALLOW_SIGNED", "1")
        monkeypatch.setenv("TOOBIT_API_KEY", TEST_KEY)
        monkeypatch.setenv("TOOBIT_API_SECRET", TEST_SECRET)
        from apex.config import Config
        adapter = A.ToobitAdapter(config=Config(), transport=broken_transport,
                                  utc_now=UTC, clock=lambda: 1000.0)
        result = run(adapter.query_open_positions())
        assert result.ok is False
        assert result.outcome == "UNKNOWN"
        assert result.reconcile_required is True


class TestWaveOutSurface:
    def test_forbidden_operation_is_wave_out_at_the_map(self):
        with pytest.raises(WaveOutError):
            M.endpoint_for("withdraw")

    def test_adapter_never_calls_a_forbidden_operation(self, monkeypatch):
        from fake_toobit_responder import FakeToobitResponder
        responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET)
        adapter = make_adapter(monkeypatch, responder)
        for operation in M.FORBIDDEN_OPERATIONS:
            assert not hasattr(adapter, operation)
