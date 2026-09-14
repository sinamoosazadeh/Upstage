"""The inbound Telegram gateway (`apex.telegram.gateway`).

No test here reaches Telegram: the transport is the `UpdateSource` seam (G9)
and the reply transport is an injected notifier. What is asserted is the
control law: OWNER-only bearer commands, the Panic Lock, the update_id replay
guard, routing to the CP-7 ControlPlane, and the fail-closed refusals.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Mapping, Optional

import pytest

from apex.config import Config
from apex.telegram import control_plane as CP
from apex.telegram import gateway as GW

OWNER = "111111"
USER = "222222"


def run(coro):
    return asyncio.run(coro)


class FakeSource(GW.UpdateSource):
    def __init__(self, updates: List[Mapping[str, Any]],
                 fail: Optional[GW.GatewayError] = None) -> None:
        self.updates = list(updates)
        self.fail = fail
        self.offsets: List[Optional[int]] = []
        self.closed = False

    async def get_updates(self, *, offset=None, timeout=25.0, limit=100):
        self.offsets.append(offset)
        if self.fail is not None:
            raise self.fail
        return list(self.updates)

    async def aclose(self):
        self.closed = True


class FakeModel:
    """An aiogram-shaped model (pydantic v2 ``model_dump``)."""

    def __init__(self, **fields: Any) -> None:
        self._fields = fields

    def model_dump(self, **kwargs: Any) -> Dict[str, Any]:
        """aiogram's ``model_dump`` is recursive — this fake mirrors that."""
        out: Dict[str, Any] = {}
        for key, value in self._fields.items():
            if value is None:
                continue
            out[key] = (value.model_dump() if isinstance(value, FakeModel)
                        else value)
        return out


class FakeService:
    """The W.8-2 runner seam (a BootstrapService stand-in)."""

    def __init__(self) -> None:
        self.commands: List[str] = []

    async def command(self, text: str, *, caller: str = "OWNER"):
        self.commands.append(text)
        return {"command": text, "accepted": text in (
            "start", "pause", "resume", "stop", "progress", "eta",
            "continuous on", "continuous off"), "caller": caller,
            "state": {"paused": text == "pause", "stopped": False,
                      "continuous": text == "continuous on"}}


@pytest.fixture()
def plane():
    return CP.ControlPlane(access=CP.AccessControl(owner_chat_ids=[OWNER],
                                                   user_chat_ids=[USER]))


@pytest.fixture()
def replies():
    sent: List[Mapping[str, Any]] = []

    async def notifier(chat_id: str, text: str):
        sent.append({"chat_id": chat_id, "text": text})
        return {"sent": True}

    return sent, notifier


def make_gateway(plane, notifier, *, service: Optional[Any] = None,
                 source: Optional[Any] = None, register: bool = True,
                 **kwargs):
    if service is None:
        service = FakeService()
    if register:
        async def handler(payload: Dict[str, Any]):
            verdict = await service.command(str(payload.get("command", "")),
                                            caller=str(payload.get("chat_id")))
            return {"ok": bool(verdict.get("accepted")), "result": verdict}
        plane.register(GW.BOOTSTRAP_ACTION, handler)
    return GW.TelegramGateway(control=plane, source=source, notifier=notifier,
                              bootstrap=service, **kwargs)


def message(update_id: int, chat_id: str, text: str) -> Dict[str, Any]:
    return {"update_id": update_id,
            "message": {"message_id": update_id, "text": text,
                        "chat": {"id": chat_id, "type": "private"},
                        "from": {"id": chat_id}}}


def callback(update_id: int, chat_id: str, data: str) -> Dict[str, Any]:
    return {"update_id": update_id,
            "callback_query": {"id": f"cb-{update_id}", "data": data,
                               "from": {"id": chat_id},
                               "message": {"chat": {"id": chat_id}}}}


# ---------------------------------------------------------------------------
# normalisation
# ---------------------------------------------------------------------------

class TestNormalisation:
    def test_plain_mapping_message(self):
        parsed = GW.extract_update(message(7, OWNER, "/start"))
        assert parsed == {"update_id": 7, "kind": "MESSAGE", "chat_id": OWNER,
                          "text": "/start", "callback": None}

    def test_aiogram_shaped_models(self):
        update = FakeModel(update_id=9, message=FakeModel(
            text="progress", chat=FakeModel(id=OWNER), **{"from": None}))
        parsed = GW.extract_update(GW._as_mapping(update))
        assert parsed["kind"] == "MESSAGE" and parsed["chat_id"] == OWNER
        assert parsed["text"] == "progress"

    def test_callback_query_is_normalised(self):
        parsed = GW.extract_update(callback(3, OWNER, "emergency:pause"))
        assert parsed["kind"] == "CALLBACK" and parsed["callback"] == "emergency:pause"
        assert parsed["chat_id"] == OWNER

    def test_unsupported_shape_is_named(self):
        parsed = GW.extract_update({"update_id": 1, "poll": {}})
        assert parsed["kind"] == "UNSUPPORTED" and parsed["chat_id"] is None

    @pytest.mark.parametrize("text,expected", [
        ("/Start@apex_bot", "/start"),
        ("/HELP extra words", "/help"),
        ("Continuous   ON", "continuous on"),
        ("  progress ", "progress"),
        ("", ""),
    ])
    def test_command_normalisation(self, text, expected):
        assert GW.normalize_command(text) == expected

    def test_screen_rendering_is_tolerant(self):
        text = GW.render_screen({"screen": "MAIN_MENU", "title": "APEX — PAPER",
                                 "rows": [("📊 Trading", "ℹ️ Info")],
                                 "global_controls": ["🛑 HALT"]})
        assert "APEX — PAPER" in text and "Trading" in text
        assert "HALT" in text


# ---------------------------------------------------------------------------
# routing
# ---------------------------------------------------------------------------

class TestRouting:
    def test_start_goes_to_the_control_plane_and_replies(self, plane, replies):
        sent, notifier = replies
        gateway = make_gateway(plane, notifier)
        record = run(gateway.handle_update(message(1, OWNER, "/start")))
        assert record["route"] == "COMMAND" and record["ok"] is True
        assert sent and sent[-1]["chat_id"] == OWNER
        assert "APEX" in sent[-1]["text"]

    def test_bearer_words_are_owner_only(self, plane, replies):
        sent, notifier = replies
        service = FakeService()
        gateway = make_gateway(plane, notifier, service=service)
        record = run(gateway.handle_update(message(2, USER, "pause")))
        assert record["ok"] is False and record["reason"] == "OWNER_ONLY"
        assert service.commands == []          # never reached the runner
        assert gateway.refusals[-1]["reason"] == "OWNER_ONLY"
        assert sent[-1]["text"].startswith("Refused: OWNER_ONLY")

    def test_owner_word_reaches_the_runner(self, plane, replies):
        sent, notifier = replies
        service = FakeService()
        gateway = make_gateway(plane, notifier, service=service)
        record = run(gateway.handle_update(message(3, OWNER, "continuous ON")))
        assert service.commands == ["continuous on"]
        assert record["ok"] is True and record["route"] == "BOOTSTRAP"
        assert sent                                 # the verdict was reported

    def test_all_eight_w8_2_words_route(self, plane, replies):
        _, notifier = replies
        service = FakeService()
        gateway = make_gateway(plane, notifier, service=service)
        for index, word in enumerate(GW.BOOTSTRAP_COMMANDS, start=10):
            run(gateway.handle_update(message(index, OWNER, word)))
        assert service.commands == list(GW.BOOTSTRAP_COMMANDS)

    def test_unwired_handler_is_refused_never_faked(self, plane, replies):
        sent, notifier = replies
        gateway = make_gateway(plane, notifier, register=False)
        record = run(gateway.handle_update(message(4, OWNER, "start")))
        assert record["ok"] is False
        assert record["reason"] == "ACTION_HANDLER_UNAVAILABLE"
        assert "Refused" in sent[-1]["text"]

    def test_panic_lock_blocks_bearer_commands(self, plane, replies):
        _, notifier = replies
        service = FakeService()
        gateway = make_gateway(plane, notifier, service=service)
        run(gateway.handle_update(message(5, OWNER, "/lock")))
        locked = run(gateway.handle_update(message(6, OWNER, "progress")))
        assert locked["ok"] is False and locked["reason"] == "PANIC_LOCK_ENGAGED"
        assert service.commands == []
        run(gateway.handle_update(message(7, OWNER, "/unlock")))
        after = run(gateway.handle_update(message(8, OWNER, "progress")))
        assert after["ok"] is True and service.commands == ["progress"]

    def test_update_id_replay_is_not_re_executed(self, plane, replies):
        _, notifier = replies
        service = FakeService()
        gateway = make_gateway(plane, notifier, service=service)
        first = run(gateway.handle_update(message(11, OWNER, "pause")))
        second = run(gateway.handle_update(message(11, OWNER, "pause")))
        assert first["ok"] is True and second.get("replayed") is True
        assert service.commands == ["pause"]

    def test_unknown_command_lists_the_supported_set(self, plane, replies):
        sent, notifier = replies
        gateway = make_gateway(plane, notifier)
        record = run(gateway.handle_update(message(12, OWNER, "/nonsense")))
        assert record["ok"] is False and record["reason"] == "COMMAND_UNKNOWN"
        assert "/start" in sent[-1]["text"]

    def test_unsupported_update_is_reported_not_guessed(self, plane, replies):
        _, notifier = replies
        gateway = make_gateway(plane, notifier)
        record = run(gateway.handle_update({"update_id": 13, "poll": {}}))
        assert record["ok"] is False and record["reason"] == "UNSUPPORTED_UPDATE"

    def test_reply_without_a_notifier_is_recorded(self, plane):
        gateway = make_gateway(plane, None)
        record = run(gateway.handle_update(message(14, OWNER, "/start")))
        assert record["ok"] is True
        assert gateway.refusals[-1]["reason"] == "NO_NOTIFIER_ENV_ONLY"


# ---------------------------------------------------------------------------
# polling loop + the production source
# ---------------------------------------------------------------------------

class TestPolling:
    def test_offset_advances_past_the_last_update(self, plane, replies):
        _, notifier = replies
        source = FakeSource([message(21, OWNER, "/myid"),
                             message(22, OWNER, "/help")])
        gateway = make_gateway(plane, notifier, source=source)
        outcome = run(gateway.run_once())
        assert outcome["polled"] == 2 and outcome["handled"] == 2
        assert gateway.offset == 23
        assert source.offsets == [None]               # first poll: no offset yet
        second = run(gateway.run_once())
        assert source.offsets[-1] == 23 and second["polled"] == 2

    def test_poll_failure_is_contained_and_counted(self, plane, replies):
        _, notifier = replies
        source = FakeSource([], fail=GW.GatewayError("POLL_FAILED", "timeout"))
        gateway = make_gateway(plane, notifier, source=source)
        outcome = run(gateway.run_once())
        assert outcome["error"] == "POLL_FAILED" and outcome["handled"] == 0
        assert gateway.poll_errors and gateway.poll_errors[-1]["reason"] == "POLL_FAILED"

    def test_run_loop_stops_on_request(self, plane, replies):
        _, notifier = replies
        source = FakeSource([message(31, OWNER, "/myid")])
        gateway = make_gateway(plane, notifier, source=source)
        checks = {"n": 0}

        def stop() -> bool:
            checks["n"] += 1
            return checks["n"] > 1                    # one clean round, then stop

        outcome = run(gateway.run(stop=stop))
        assert outcome["rounds"] == 1 and outcome["handled"] == 1

    def test_run_loop_backs_off_on_failure(self, plane, replies):
        _, notifier = replies
        source = FakeSource([], fail=GW.GatewayError("POLL_FAILED", "timeout"))
        gateway = make_gateway(plane, notifier, source=source)
        slept: List[float] = []

        async def sleep(seconds: float) -> None:
            slept.append(seconds)
            gateway.stop()

        outcome = run(gateway.run(sleep=sleep))
        assert outcome["rounds"] == 1 and slept == [1.0]

    def test_run_without_a_source_is_refused(self, plane, replies):
        _, notifier = replies
        gateway = make_gateway(plane, notifier)
        with pytest.raises(GW.GatewayError) as excinfo:
            run(gateway.run_once())
        assert excinfo.value.reason == "NO_UPDATE_SOURCE"

    def test_aiogram_source_requires_the_env_token(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.setenv("APEX_DOTENV_PATH", "/nonexistent/.env")
        with pytest.raises(GW.GatewayError) as excinfo:
            GW.AiogramUpdateSource(config=Config())
        assert excinfo.value.reason == "E-TELE-001"

    def test_aiogram_source_normalises_a_fake_bot(self):
        class FakeBot:
            def __init__(self):
                self.calls: List[Dict[str, Any]] = []

            async def get_updates(self, *, offset=None, timeout=25, limit=100):
                self.calls.append({"offset": offset, "timeout": timeout,
                                   "limit": limit})
                return [FakeModel(update_id=41, message=FakeModel(
                    text="/myid", chat=FakeModel(id=OWNER), **{"from": None}))]

        bot = FakeBot()
        source = GW.AiogramUpdateSource(token=None, bot=bot,
                                        config=Config())
        updates = run(source.get_updates(offset=40, timeout=5.0, limit=10))
        assert updates[0]["update_id"] == 41
        assert updates[0]["message"]["text"] == "/myid"
        assert bot.calls == [{"offset": 40, "timeout": 5, "limit": 10}]
        assert source.offset is None     # the gateway owns offset advancement

    def test_aclose_closes_the_source(self, plane, replies):
        _, notifier = replies
        source = FakeSource([])
        gateway = make_gateway(plane, notifier, source=source)
        run(gateway.aclose())
        assert source.closed is True and gateway._stopped is True
