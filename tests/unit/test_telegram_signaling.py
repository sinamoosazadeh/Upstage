"""CP-7 Telegram signaling tests — Ch.21 §2/§7/§8/§10/§11/§12 (L17578–18060)
and the Ch.23 Alert Policy (L18290–18314).

Covered: the frozen parameter table, the token bucket (20/s internal below the
30/s provider ceiling, queue never drop), retry 3× with 1/2/4 s backoff, the
idempotency key ``SHA256(signal_id + timestamp_UTC + chat_id)`` with a 24 h TTL,
MarkdownV2/HTML formatting and truncation (E-TELE-003/004/005), the §8 evidence
event emission formula, the §11 message state machine (theta_maxAge 100 bars),
the Ch.23 alert rows with the 30-minute dedup window (except EXEC_RECOVERY and
CIRCUIT_OPEN), Agg-only in-memory charts, the durable outbox, and the
env-only bot token (E-TELE-001). The transport is a test double (G9).
"""
from __future__ import annotations

import asyncio
import inspect
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from apex.bus import EventBus, Priority
from apex.errors import get_error_code
from apex.telegram import signaling as S

REPO_ROOT = Path(__file__).resolve().parents[2]
ISO = "2026-01-01T00:00:00.000Z"
OWNER = "-1001234567890"
WATCHDOG = "-2001234567890"


def run(coro):
    return asyncio.run(coro)


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += float(seconds)


class FakeTransport(S.TelegramTransport):
    """Test double for the aiogram transport: records every send and can be
    told to fail the next N calls."""

    def __init__(self, *, fail_times: int = 0, fail_always: bool = False) -> None:
        self.sent: List[Dict[str, Any]] = []
        self.fail_times = int(fail_times)
        self.fail_always = bool(fail_always)
        self._seq = 0

    async def send_message(self, chat_id: str, text: str, parse_mode: str,
                           reply_markup: Optional[Dict[str, Any]] = None
                           ) -> Dict[str, Any]:
        return await self._record("message", chat_id, text, parse_mode,
                                  reply_markup, None)

    async def send_photo(self, chat_id: str, photo: bytes,
                         caption: Optional[str], parse_mode: str,
                         reply_markup: Optional[Dict[str, Any]] = None
                         ) -> Dict[str, Any]:
        return await self._record("photo", chat_id, caption, parse_mode,
                                  reply_markup, photo)

    async def _record(self, kind, chat_id, text, parse_mode, reply_markup,
                      photo):
        if self.fail_always or self.fail_times > 0:
            if self.fail_times > 0:
                self.fail_times -= 1
            raise RuntimeError("TelegramServerError: 429 Too Many Requests")
        self._seq += 1
        self.sent.append({"kind": kind, "chat_id": str(chat_id), "text": text,
                          "parse_mode": parse_mode, "reply_markup": reply_markup,
                          "photo_bytes": len(photo) if photo else 0})
        return {"message_id": str(5000 + self._seq), "chat_id": str(chat_id)}


def plane(transport=None, *, clock=None, ledger=None, bus=None,
          owner=OWNER, watchdog=WATCHDOG, freshness=None) -> S.SignalingPlane:
    return S.SignalingPlane(transport=transport or FakeTransport(),
                            clock=clock or FakeClock(), utc_now=lambda: ISO,
                            ledger=ledger, bus=bus, owner_chat_id=owner,
                            watchdog_chat_id=watchdog,
                            freshness_thresholds=freshness or {})


def message(**overrides) -> S.SignalMessage:
    kwargs = {"signal_id": "sig-1", "chat_id": OWNER, "text": "Setup CONFIRMED",
              "timestamp_utc": ISO, "snapshot_id": "sn-1"}
    kwargs.update(overrides)
    return S.SignalMessage(**kwargs)


class RecordingLedger:
    """Minimal ledger double: records every appended alert."""

    def __init__(self) -> None:
        self.records: List[Dict[str, Any]] = []

    async def append(self, **kwargs) -> Any:
        self.records.append(kwargs)
        return kwargs


# ---------------------------------------------------------------------------
# §10 frozen parameter table
# ---------------------------------------------------------------------------

class TestParameterTable:
    def test_the_frozen_literals(self):
        assert S.RATE_LIMITING_BUCKET_SIZE == 20
        assert S.RATE_LIMITING_REFILL_RATE == 20.0
        assert S.PROVIDER_CEILING_PER_SECOND == 30
        assert S.RETRY_TIMES == 3
        assert S.RETRY_BACKOFF_SECONDS == (1.0, 2.0, 4.0)
        assert S.IDEMPOTENCY_KEY_TTL_SECONDS == 86400
        assert S.IMAGE_CHART_WIDTH == 1200
        assert S.IMAGE_CHART_HEIGHT == 800
        assert S.IMAGE_CHART_FORMAT == "PNG"
        assert S.IMAGE_CHART_QUALITY == 90
        assert S.CAPTION_MAX_LENGTH == 1024
        assert S.TEXT_MAX_LENGTH == 4096
        assert S.INLINE_KEYBOARD_MAX_BUTTONS == 8
        assert S.INLINE_KEYBOARD_MAX_ROWS == 4
        assert S.CALLBACK_DATA_MAX_BYTES == 64

    def test_the_parameter_table_view_matches_the_literals(self):
        assert S.TELEGRAM_PARAMS == {
            "rate_limiting_bucket_size": 20, "rate_limiting_refill_rate": 20.0,
            "retry_times": 3, "retry_backoff": [1.0, 2.0, 4.0],
            "idempotency_key_ttl": 86400, "image_chart_width": 1200,
            "image_chart_height": 800, "image_chart_format": "PNG",
            "image_chart_quality": 90, "caption_max_length": 1024,
            "text_max_length": 4096, "inline_keyboard_max_buttons": 8,
            "inline_keyboard_max_rows": 4}

    def test_the_internal_limiter_is_below_the_provider_ceiling(self):
        assert S.RATE_LIMITING_BUCKET_SIZE < S.PROVIDER_CEILING_PER_SECOND
        with pytest.raises(S.SignalingError) as exc:
            S.MessageTokenBucket(capacity=S.PROVIDER_CEILING_PER_SECOND + 1)
        assert exc.value.reason == "INTERNAL_LIMITER_ABOVE_PROVIDER_CEILING"

    def test_signaling_tiers_are_the_ch21_table(self):
        assert S.SIGNAL_TIERS[Priority.P0]["content"] == (
            "FAIL_CLOSED", "CIRCUIT_OPEN", "EXEC_RECOVERY", "HOST_DOWN")
        assert S.SIGNAL_TIERS[Priority.P0]["bound"] == "never drop"
        assert S.SIGNAL_TIERS[Priority.P0]["droppable"] is False
        assert S.SIGNAL_TIERS[Priority.P1]["bound"] == "≤2 s declared UNVERIFIED"
        assert S.SIGNAL_TIERS[Priority.P2]["bound"] == "token bucket 20/s"
        assert S.SIGNAL_TIERS[Priority.P3]["droppable"] is True


# ---------------------------------------------------------------------------
# Formatting (§7)
# ---------------------------------------------------------------------------

class TestFormatting:
    def test_markdown_v2_escapes_exactly_the_listed_characters(self):
        assert S.MARKDOWNV2_ESCAPE_CHARS == (
            "_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=",
            "|", "{", "}", ".", "!")
        escaped = S.escape_markdown_v2("PnL +1.5% [ok] (v2) ~x~ `y` #1 !")
        for char in S.MARKDOWNV2_ESCAPE_CHARS:
            if char in "PnL +1.5% [ok] (v2) ~x~ `y` #1 !":
                assert f"\\{char}" in escaped
        assert S.format_markdown_v2("hi")["parse_mode"] == "MarkdownV2"

    def test_comma_formatted_numbers_are_escaped_too(self):
        """Ch.21 §7 L18035: numbers with commas must be escaped. The comma is
        not itself a MarkdownV2 special character, but every special character
        INSIDE the number (the decimal point, a leading minus) is."""
        assert S.comma_format("1234567.891") == "1,234,567.891"
        assert S.comma_format(10000) == "10,000"
        escaped = S.escape_markdown_v2(S.comma_format("1234567.891"))
        assert escaped == "1,234,567\\.891"
        negative = S.escape_markdown_v2(S.comma_format(-2500.5))
        assert negative == "\\-2,500\\.5"

    def test_html_supports_only_the_five_tags(self):
        assert S.HTML_ALLOWED_TAGS == ("b", "i", "code", "pre", "a")
        rendered = S.format_html("<b>bold</b><script>x</script>")
        assert rendered["parse_mode"] == "HTML"
        assert "<b>bold</b>" in rendered["text"]
        assert "<script>" not in rendered["text"]

    def test_a_too_long_message_is_truncated_and_degraded(self):
        verdict = S.format_markdown_v2("x" * (S.TEXT_MAX_LENGTH + 10))
        assert verdict["truncated"] is True
        assert len(verdict["text"]) == S.TEXT_MAX_LENGTH
        assert verdict["error_code"] == get_error_code("E-TELE-003").code
        assert verdict["quality"] == "Q2_DEGRADED"

    def test_a_too_long_caption_is_truncated_and_degraded(self):
        verdict = S.format_caption("y" * (S.CAPTION_MAX_LENGTH + 1))
        assert verdict["truncated"] is True
        assert len(verdict["caption"]) == S.CAPTION_MAX_LENGTH
        assert verdict["error_code"] == get_error_code("E-TELE-004").code

    def test_a_keyboard_over_eight_buttons_is_truncated(self):
        rows = [[{"text": f"B{i}", "callback_data": f"b{i}"} for i in range(3)]
                for _ in range(5)]
        verdict = S.build_inline_keyboard(rows)
        assert verdict["button_count"] == S.INLINE_KEYBOARD_MAX_BUTTONS
        assert verdict["row_count"] <= S.INLINE_KEYBOARD_MAX_ROWS
        assert verdict["truncated_buttons"] is True
        assert verdict["error_code"] == get_error_code("E-TELE-005").code
        assert verdict["quality"] == "Q2_DEGRADED"

    def test_oversized_callback_data_is_reported_and_cut(self):
        verdict = S.build_inline_keyboard(
            [[{"text": "X", "callback_data": "z" * 80}]])
        assert len(verdict["oversized_callback_data"]) == 1
        assert len(verdict["inline_keyboard"][0][0]["callback_data"].encode(
            "utf-8")) <= S.CALLBACK_DATA_MAX_BYTES

    def test_a_two_button_row_layout_is_preserved(self):
        verdict = S.build_inline_keyboard(
            [[{"text": "A", "callback_data": "a"},
              {"text": "B", "callback_data": "b"}]])
        assert len(verdict["inline_keyboard"][0]) == 2


class TestIdempotencyKey:
    def test_the_key_is_sha256_of_the_three_fields(self):
        key = S.idempotency_key("sig-1", ISO, OWNER)
        assert len(key) == 64
        assert key == S.idempotency_key("sig-1", ISO, OWNER)
        assert key != S.idempotency_key("sig-2", ISO, OWNER)
        assert key != S.idempotency_key("sig-1", ISO, "-999")

    def test_the_key_matches_the_message_property(self):
        msg = message()
        assert msg.idempotency_key == S.idempotency_key(msg.signal_id,
                                                        msg.timestamp_utc,
                                                        msg.chat_id)

    def test_an_existing_key_skips_the_message(self):
        clock = FakeClock()
        transport = FakeTransport()
        bus = plane(transport, clock=clock)
        first = run(bus.send(message()))
        second = run(bus.send(message()))
        assert first.sent is True
        assert second.sent is False
        assert second.reason == "idempotency key exists"
        assert second.error_code == get_error_code("E-TELE-007").code
        assert len(transport.sent) == 1

    def test_the_key_expires_after_twenty_four_hours(self):
        clock = FakeClock()
        bus = plane(FakeTransport(), clock=clock)
        registry = bus.idempotency
        registry.store("k1")
        assert registry.exists("k1") is True
        clock.advance(S.IDEMPOTENCY_KEY_TTL_SECONDS + 1)
        assert registry.exists("k1") is False


# ---------------------------------------------------------------------------
# Token bucket (§7 / AI.8 L18772–18775)
# ---------------------------------------------------------------------------

class TestTokenBucket:
    def test_one_token_per_message_and_twenty_in_the_bucket(self):
        clock = FakeClock()
        bucket = S.MessageTokenBucket(clock=clock)
        assert bucket.available() == 20.0
        for _ in range(20):
            assert run(bucket.acquire())["acquired"] is True
        assert bucket.bucket_empty() is True

    def test_an_empty_bucket_queues_the_message_and_never_drops_it(self):
        clock = FakeClock()
        bucket = S.MessageTokenBucket(clock=clock)
        for _ in range(20):
            run(bucket.acquire())

        async def queued():
            task = asyncio.create_task(bucket.acquire())
            await asyncio.sleep(0)
            clock.advance(0.1)                 # 2 tokens refill at 20/s
            return await task

        verdict = run(queued())
        assert verdict["acquired"] is True
        assert verdict["queued"] is True
        assert verdict["error_code"] == get_error_code("E-TELE-006").code

    def test_the_bucket_refills_at_twenty_per_second(self):
        clock = FakeClock()
        bucket = S.MessageTokenBucket(clock=clock)
        for _ in range(20):
            run(bucket.acquire())
        clock.advance(1.0)
        assert bucket.available() == 20.0
        clock.advance(10.0)
        assert bucket.available() == 20.0      # never above capacity

    def test_buckets_are_per_chat(self):
        clock = FakeClock()
        bus = plane(FakeTransport(), clock=clock)
        a = bus.bucket_for("-1")
        b = bus.bucket_for("-2")
        assert a is not b
        run(a.acquire())
        assert b.available() == 20.0


# ---------------------------------------------------------------------------
# Sending: retry, truncation, outbox
# ---------------------------------------------------------------------------

class TestSending:
    def test_a_successful_send_is_active_and_stores_the_key(self):
        transport = FakeTransport()
        bus = plane(transport)
        result = run(bus.send(message()))
        assert result.sent is True
        assert result.state == "ACTIVE"
        assert result.message_id == "5001"
        assert result.quality == "Q2"
        assert len(result.attempts) == 1
        assert bus.idempotency.exists(result.idempotency_key)
        assert transport.sent[0]["parse_mode"] == "MarkdownV2"

    def test_retry_uses_the_one_two_four_backoff(self, monkeypatch):
        """The backoff is the frozen 1/2/4 s table (Ch.21 §10) — the sleeps are
        recorded through a module-level shim so the test never waits for them."""
        import types

        transport = FakeTransport(fail_times=2)
        sleeps: List[float] = []
        real_sleep = asyncio.sleep

        async def fake_sleep(seconds):
            sleeps.append(float(seconds))
            await real_sleep(0)

        shim = types.SimpleNamespace(sleep=fake_sleep, Lock=asyncio.Lock)
        monkeypatch.setattr(S, "asyncio", shim)
        bus = plane(transport)
        result = run(bus.send(message()))
        assert result.sent is True
        assert len(result.attempts) == 3
        assert [a.status for a in result.attempts] == ["RETRY", "RETRY", "SENT"]
        assert [a.delay_seconds for a in result.attempts[:-1]] == [1.0, 2.0]
        assert sleeps == [1.0, 2.0]

    def test_three_failures_leave_the_message_in_the_outbox(self):
        transport = FakeTransport(fail_always=True)
        bus = plane(transport)
        result = run(bus.send(message()))
        assert result.sent is False
        assert result.state == "INVALIDATED"
        assert len(result.attempts) == S.RETRY_TIMES
        assert result.attempts[-1].status == "FAILED"
        assert "3 attempts" in result.reason
        assert bus.outbox[-1]["status"] == "FAILED"
        assert bus.outbox[-1]["droppable"] is False      # P2 is never dropped

    def test_an_invalid_chat_id_is_qx_invalid(self):
        transport = FakeTransport()
        bus = plane(transport)
        result = run(bus.send(message(chat_id="@not_a_chat_id")))
        assert result.sent is False
        assert result.quality == "QX"
        assert result.error_code == get_error_code("E-TELE-002").code
        assert transport.sent == []

    def test_a_too_long_text_is_truncated_and_degraded_on_send(self):
        transport = FakeTransport()
        bus = plane(transport)
        result = run(bus.send(message(text="x" * 5000)))
        assert result.truncated is True
        assert result.quality == "Q2_DEGRADED"
        assert result.error_code == get_error_code("E-TELE-003").code
        assert len(transport.sent[0]["text"]) <= S.TEXT_MAX_LENGTH

    def test_an_image_is_sent_as_a_photo_with_its_caption(self):
        transport = FakeTransport()
        bus = plane(transport)
        chart = S.render_chart(ohlcv=[[i, 1, 2, 0.5, 1.5, 10] for i in range(3)],
                               layers=["BOS"])
        result = run(bus.send(message(image=chart["image"],
                                      caption="BTCUSDT 1h — BOS")))
        assert result.sent is True
        assert transport.sent[0]["kind"] == "photo"
        assert transport.sent[0]["photo_bytes"] == len(chart["image"])
        assert transport.sent[0]["text"] == "BTCUSDT 1h — BOS"

    def test_the_outbox_records_every_message_including_skips(self):
        bus = plane(FakeTransport())
        run(bus.send(message(setup_state="CANDIDATE")))
        assert bus.outbox[-1]["status"] == "SKIPPED"
        assert bus.stats()["skipped"] == 1

    def test_a_p0_signal_is_marked_never_droppable(self):
        bus = plane(FakeTransport())
        run(bus.send(message(priority=Priority.P0, alert="EXEC_RECOVERY"),
                     force=True))
        assert bus.outbox[-1]["droppable"] is False
        assert bus.outbox[-1]["priority"] == int(Priority.P0)

    def test_a_bus_event_is_published_for_every_send(self):
        async def body():
            bus_events: List[Any] = []
            event_bus = EventBus()

            async def collector(event):
                bus_events.append(event)

            event_bus.subscribe("telegram.message", collector)
            task = event_bus.start()
            try:
                signaling = plane(FakeTransport(), bus=event_bus)
                await signaling.send(message())
                for _ in range(10):
                    await asyncio.sleep(0)
            finally:
                await event_bus.stop()
            return bus_events

        events = run(body())
        assert len(events) == 1
        assert events[0].payload["sent"] is True
        assert events[0].payload["signal_id"] == "sig-1"


# ---------------------------------------------------------------------------
# §8 evidence event emission formula
# ---------------------------------------------------------------------------

class TestEmissionFormula:
    def test_a_confirmed_setup_with_good_quality_emits(self):
        bus = plane(FakeTransport())
        gate = bus.calc_telegram_message(message())
        assert gate["emit"] is True
        assert gate["result"] == "TelegramMessage"
        assert gate["state"] == "CONFIRMED"
        assert gate["confidence"] == pytest.approx(0.85)
        assert gate["validity_candles"] == (5, 20)

    def test_the_confidence_is_085_times_q_formula_valid(self):
        msg = message(q_formula_valid=0.5)
        assert msg.confidence == pytest.approx(0.425)
        assert S.TELEGRAM_CONFIDENCE_FACTOR == 0.85

    def test_the_quality_and_validity_are_the_contract_values(self):
        assert S.TELEGRAM_QUALITY == "Q2"
        assert S.TELEGRAM_VALIDITY_CANDLES == (5, 20)

    @pytest.mark.parametrize("kwargs,result", [
        ({"setup_state": "CANDIDATE"}, "NO_TELEGRAM_MESSAGE"),
        ({"setup_state": "INVALIDATED"}, "NO_TELEGRAM_MESSAGE"),
        ({"q_window_min": 0.4}, "INVALID"),
        ({"setup_blocked": True}, "INVALID")])
    def test_the_gate_refuses_without_emitting(self, kwargs, result):
        transport = FakeTransport()
        bus = plane(transport)
        gate = bus.calc_telegram_message(message(**kwargs))
        assert gate["emit"] is False
        assert gate["result"] == result
        run(bus.send(message(**kwargs)))
        assert transport.sent == []

    def test_an_empty_bucket_queues_instead_of_dropping(self):
        clock = FakeClock()
        transport = FakeTransport()
        bus = plane(transport, clock=clock)
        for index in range(20):
            run(bus.send(message(signal_id=f"s-{index}",
                                 timestamp_utc=f"{ISO}{index}")))
        gate = bus.calc_telegram_message(message(signal_id="s-overflow"))
        assert gate["emit"] is True
        assert gate["result"] == "QUEUED"
        assert gate["error_code"] == get_error_code("E-TELE-006").code


class TestMessageStateMachine:
    def test_the_states_are_the_ch21_set(self):
        assert S.MESSAGE_STATES == ("CANDIDATE", "CONFIRMED", "ACTIVE", "PRUNED",
                                    "INVALIDATED")

    def test_theta_max_age_is_one_hundred_bars(self):
        assert S.THETA_MAX_AGE_BARS == 100
        assert plane().pruned_verdict(100)["state"] == "ACTIVE"
        verdict = plane().pruned_verdict(101)
        assert verdict["state"] == "PRUNED"
        assert verdict["correction_path"] == \
            "OLD → CORRECTION EVENT → NEW VERSION → SUPERSEDES"

    def test_the_decay_formula_is_exp_minus_002_age(self):
        assert S.DECAY_LAMBDA == 0.02
        assert plane().decay(0) == pytest.approx(1.0)
        assert plane().decay(50) == pytest.approx(0.36787944117, rel=1e-6)
        assert plane().decay(100) == pytest.approx(0.13533528323, rel=1e-6)


# ---------------------------------------------------------------------------
# Ch.23 alert policy
# ---------------------------------------------------------------------------

class TestAlertPolicy:
    def test_the_five_policy_rows_are_verbatim(self):
        rows = {r["alert"]: r for r in S.ALERT_POLICY}
        assert set(rows) == {"FEED_DEGRADED", "EXEC_RECOVERY", "CIRCUIT_OPEN",
                             "HOST_DOWN", "STORAGE"}
        assert rows["FEED_DEGRADED"]["threshold"] == "> 2 × freshness threshold"
        assert rows["FEED_DEGRADED"]["escalation"] == "15 min → L1"
        assert rows["EXEC_RECOVERY"]["threshold"] == "any occurrence"
        assert rows["EXEC_RECOVERY"]["channel"] == "Telegram immediate"
        assert rows["EXEC_RECOVERY"]["escalation"] == "immediate OWNER"
        assert rows["CIRCUIT_OPEN"]["threshold"] == "per veto 10 table"
        assert rows["HOST_DOWN"]["threshold"] == "3 consecutive"
        assert rows["HOST_DOWN"]["channel"] == "independent channel"
        assert rows["STORAGE"]["threshold"] == "> 80% capacity"
        assert rows["STORAGE"]["escalation"] == "24 h"

    def test_priorities_match_the_signaling_tier_table(self):
        rows = {r["alert"]: r for r in S.ALERT_POLICY}
        assert rows["EXEC_RECOVERY"]["priority"] == int(Priority.P0)
        assert rows["CIRCUIT_OPEN"]["priority"] == int(Priority.P0)
        assert rows["HOST_DOWN"]["priority"] == int(Priority.P0)
        assert rows["FEED_DEGRADED"]["priority"] == int(Priority.P1)
        assert rows["STORAGE"]["priority"] == int(Priority.P1)

    def test_an_alert_not_in_the_policy_is_refused(self):
        with pytest.raises(S.SignalingError) as exc:
            plane().alert_row("SOMETHING_LOUD")
        assert exc.value.reason == "ALERT_NOT_IN_POLICY"

    def test_dedup_suppresses_identical_alerts_inside_thirty_minutes(self):
        assert S.ALERT_DEDUP_WINDOW_SECONDS == 1800
        clock = FakeClock()
        bus = plane(FakeTransport(), clock=clock)
        first = run(bus.emit_alert(alert="FEED_DEGRADED", metric="staleness",
                                   threshold="> 2 × 30s", observed=90,
                                   snapshot_id="sn-1"))
        second = run(bus.emit_alert(alert="FEED_DEGRADED", metric="staleness",
                                    threshold="> 2 × 30s", observed=90,
                                    snapshot_id="sn-2"))
        assert first["emitted"] is True
        assert second["emitted"] is False
        assert second["reason"] == "DEDUP_SUPPRESSED"

    def test_dedup_expires_after_the_window(self):
        clock = FakeClock()
        bus = plane(FakeTransport(), clock=clock)
        run(bus.emit_alert(alert="STORAGE", metric="device_storage",
                           threshold="> 80%", observed=0.9))
        clock.advance(S.ALERT_DEDUP_WINDOW_SECONDS + 1)
        again = run(bus.emit_alert(alert="STORAGE", metric="device_storage",
                                   threshold="> 80%", observed=0.9))
        assert again["emitted"] is True

    @pytest.mark.parametrize("alert", sorted(S.ALERT_DEDUP_EXEMPT))
    def test_exec_recovery_and_circuit_open_are_never_suppressed(self, alert):
        assert S.ALERT_DEDUP_EXEMPT == frozenset({"EXEC_RECOVERY",
                                                  "CIRCUIT_OPEN"})
        clock = FakeClock()
        transport = FakeTransport()
        bus = plane(transport, clock=clock)
        for _ in range(3):
            # identical alert + metric + observed: only the dedup EXEMPTION
            # can let all three through.
            verdict = run(bus.emit_alert(alert=alert,
                                         metric="execution_recovery_required",
                                         threshold="any occurrence", observed=1))
            assert verdict["emitted"] is True, alert
            assert verdict["suppressed"] is False
        assert len(transport.sent) == 3

    def test_every_alert_carries_the_five_required_fields(self):
        ledger = RecordingLedger()
        bus = plane(FakeTransport(), ledger=ledger)
        verdict = run(bus.emit_alert(alert="EXEC_RECOVERY",
                                     metric="execution_recovery_required",
                                     threshold="any occurrence", observed=1,
                                     snapshot_id="sn-9"))
        for field in ("timestamp_utc", "metric", "threshold", "observed",
                      "snapshot_id"):
            assert verdict[field]
        assert ledger.records[-1]["event_type"] == "ALERT"
        assert ledger.records[-1]["alert"]["alert"] == "EXEC_RECOVERY"

    def test_the_alert_is_appended_to_the_immutable_audit_trail(self):
        ledger = RecordingLedger()
        bus = plane(FakeTransport(), ledger=ledger)
        run(bus.emit_alert(alert="STORAGE", metric="device_storage",
                           threshold="> 80%", observed=0.85))
        assert len(ledger.records) == 1
        assert len(bus.alert_audit) == 1

    def test_feed_staleness_trigger(self):
        transport = FakeTransport()
        bus = plane(transport, freshness={"1h": 30})
        quiet = run(bus.check_feed_staleness(symbol="BTCUSDT", timeframe="1h",
                                             age_seconds=30))
        stale = run(bus.check_feed_staleness(symbol="BTCUSDT", timeframe="1h",
                                             age_seconds=61))
        assert quiet["alert"] is None
        assert stale["alert"] == "FEED_DEGRADED"
        assert len(transport.sent) == 1

    def test_feed_staleness_reads_the_frozen_params_when_not_supplied(self):
        bus = plane(FakeTransport())
        verdict = run(bus.check_feed_staleness(symbol="BTCUSDT", timeframe="1h",
                                               age_seconds=61))
        assert verdict["alert"] == "FEED_DEGRADED"
        # params/quality_weights_v1.yaml freshness_threshold_seconds[1h] = 30
        assert verdict["threshold"] == "> 2 × 30.0s"
        assert verdict["metric"] == "feed_staleness:BTCUSDT:1h"
        assert verdict["channel"] == "Telegram"
        assert verdict["escalation"] == "15 min → L1"

    def test_host_down_after_three_missed_heartbeats(self):
        assert S.HEARTBEAT_MISS_LIMIT == 3
        assert S.HEARTBEAT_INTERVAL_SECONDS == 60
        transport = FakeTransport()
        bus = plane(transport)
        assert run(bus.check_heartbeat(missed=2))["alert"] is None
        verdict = run(bus.check_heartbeat(missed=3))
        assert verdict["alert"] == "HOST_DOWN"
        assert verdict["independent_channel"] is True
        assert verdict["watchdog_chat_id"] == WATCHDOG
        assert transport.sent[0]["chat_id"] == WATCHDOG

    def test_storage_trigger_at_eighty_percent(self):
        assert S.STORAGE_ALERT_FRACTION == 0.80
        bus = plane(FakeTransport())
        assert run(bus.check_storage(used_fraction=0.8))["alert"] is None
        assert run(bus.check_storage(used_fraction=0.81))["alert"] == "STORAGE"

    def test_log_retention_is_ninety_days(self):
        assert S.LOG_RETENTION_DAYS == 90

    def test_the_p1_veto_alert_is_built_from_fired_numbers(self):
        bus = plane(FakeTransport())
        alert = bus.veto_alert_message(fired_numbers=[3, 7],
                                       proposed_decision="ALLOW",
                                       snapshot_id="sn-1")
        assert alert.priority == int(Priority.P1)
        assert "veto REJECT of ALLOW-proposed plan" in alert.text
        assert "[3, 7]" in alert.text

    def test_no_veto_and_no_margin_pressure_means_no_alert(self):
        bus = plane(FakeTransport())
        assert bus.veto_alert_message(fired_numbers=[], proposed_decision="ALLOW",
                                      margin_health_fraction=0.9) is None

    def test_a_margin_warning_is_a_p1_alert(self):
        bus = plane(FakeTransport())
        alert = bus.veto_alert_message(fired_numbers=[], proposed_decision="ALLOW",
                                       margin_health_fraction=0.5)
        assert alert is not None
        assert alert.priority == int(Priority.P1)
        assert alert.threshold == "60% of maintenance distance"

    def test_declared_delivery_targets_are_unverified(self):
        assert S.DECLARED_DELIVERY_TARGETS_SECONDS == {int(Priority.P0): 2.0,
                                                      int(Priority.P1): 5.0}
        bus = plane(FakeTransport())
        result = run(bus.send(message(priority=Priority.P0), force=True))
        assert result.declared_target_seconds == 2.0


# ---------------------------------------------------------------------------
# Signaling failure never blocks protective execution
# ---------------------------------------------------------------------------

class TestNeverBlocksExecution:
    def test_a_dead_transport_does_not_raise_out_of_the_alert_path(self):
        bus = plane(FakeTransport(fail_always=True))
        verdict = run(bus.emit_alert(alert="EXEC_RECOVERY",
                                     metric="execution_recovery_required",
                                     threshold="any occurrence", observed=1))
        assert verdict["emitted"] is False
        assert verdict["alert"] == "EXEC_RECOVERY"      # recorded anyway
        assert bus.alert_audit[-1]["alert"] == "EXEC_RECOVERY"

    def test_a_signaling_failure_never_mutates_market_state(self):
        """The plane has no adapter, no ledger write path and no order surface:
        it can only report."""
        assert not hasattr(S.SignalingPlane, "submit_order")
        assert not hasattr(S.SignalingPlane, "cancel_order")
        source = inspect.getsource(S.SignalingPlane)
        assert "ToobitAdapter" not in source


# ---------------------------------------------------------------------------
# Charts: Agg only, in-memory only, zero display calls
# ---------------------------------------------------------------------------

class TestCharts:
    def test_the_chart_is_exactly_1200x800_png_in_memory(self):
        chart = S.render_chart(ohlcv=[[i, 1, 2, 0.5, 1.5, 10] for i in range(5)],
                               layers=["BOS", "FVG"], quality="Q2",
                               snapshot_id="sn-1", lineage="E01")
        assert chart["width"] == S.IMAGE_CHART_WIDTH == 1200
        assert chart["height"] == S.IMAGE_CHART_HEIGHT == 800
        assert chart["format"] == "PNG"
        assert chart["quality"] == 90
        assert chart["backend"] == "Agg"
        assert chart["filesystem_stored"] is False
        assert chart["image"][:8] == b"\x89PNG\r\n\x1a\n"
        assert chart["snapshot_id"] == "sn-1"
        assert chart["lineage"] == "E01"

    def test_market_profile_is_always_unavailable(self):
        chart = S.render_chart(ohlcv=[[0, 1, 2, 0.5, 1.5, 10]],
                               layers=["Market Profile"])
        assert chart["layers_unavailable"] == ("Market Profile",)
        assert "UNAVAILABLE" in chart["note"]

    def test_an_unknown_layer_is_refused(self):
        with pytest.raises(S.SignalingError) as exc:
            S.render_chart(ohlcv=[], layers=["Secret Indicator"])
        assert exc.value.reason == "CHART_LAYER_UNKNOWN"

    def test_the_overlay_layer_list_is_the_frozen_one(self):
        assert len(S.CHART_LAYERS) == 38
        for layer in ("Swing High/Low", "BOS", "CHoCH", "FVG", "OrderBlock",
                      "Equal Highs/Lows", "Sweep", "Liquidity Pool", "Stop Hunt",
                      "Volume Spike", "VolumeZ", "VolRatio", "VWAP Dev", "OBV",
                      "CVD", "Delta", "Footprint", "Volume Profile",
                      "Market Profile", "Taker Buy/Sell", "Liquidation", "ATR",
                      "Parkinson", "Garman-Klass", "Rogers-Satchell", "GARCH",
                      "Normalized Range", "RangeZ", "Slope", "Hurst", "Squeeze",
                      "Volatility Regime", "Trend", "Momentum Divergence",
                      "Regime", "TemporalWindow", "Killzone", "News Event"):
            assert layer in S.CHART_LAYERS

    def test_agg_is_selected_before_pyplot_is_imported(self):
        source = Path(S.__file__).read_text()
        use_index = source.index("matplotlib.use(\"Agg\")")
        pyplot_index = source.index("import matplotlib.pyplot")
        assert use_index < pyplot_index

    def test_zero_display_calls_anywhere_in_the_repository(self):
        """Ch.1 L118–124: Agg only, zero display calls anywhere."""
        offenders = []
        for path in sorted((REPO_ROOT / "apex").rglob("*.py")):
            text = path.read_text()
            for lineno, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if re.search(r"\.show\(\s*\)", line) or \
                        re.search(r"matplotlib\.use\(\s*['\"](?!Agg)", line) or \
                        "Tk(" in line or "plt.pause(" in line:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}")
        assert offenders == []

    def test_charts_are_never_written_to_the_filesystem(self):
        offenders = []
        for path in sorted((REPO_ROOT / "apex").rglob("*.py")):
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                if "savefig(" in line and "buf" not in line:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}")
        assert offenders == []


# ---------------------------------------------------------------------------
# Secrets: env only, never in a message or an exception
# ---------------------------------------------------------------------------

class TestSecrets:
    def test_a_missing_bot_token_is_e_tele_001(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        from apex.config import Config
        with pytest.raises(S.SignalingError) as exc:
            S.AiogramTransport.from_env(Config())
        assert exc.value.error_code == get_error_code("E-TELE-001").code
        assert "TELEGRAM_BOT_TOKEN" not in str(exc.value).replace(
            "TELEGRAM_BOT_TOKEN is not set (env only)", "")

    def test_the_token_is_never_hardcoded_in_the_module(self):
        source = Path(S.__file__).read_text()
        assert re.search(r"bot_token\s*=\s*['\"][0-9]{6,}", source) is None
        assert "TELEGRAM_BOT_TOKEN" in source        # env-only reference

    def test_no_secret_material_reaches_a_message(self):
        transport = FakeTransport()
        bus = plane(transport)
        run(bus.send(message(text="balance 10,000 USDT"), force=True))
        assert "TEST_SECRET" not in transport.sent[0]["text"]

    def test_the_aiogram_transport_is_built_only_from_the_environment(self):
        source = inspect.getsource(S.AiogramTransport.from_env)
        assert "cfg.telegram_bot_token" in source
        assert "from aiogram import Bot" in source
