"""Ch.21 §5–§7 + Ch.18 W.8-2 — the INBOUND Telegram gateway.

CP-7 left two halves on purpose: the signaling plane SENDS (token bucket,
idempotency, durable outbox, Agg-only charts) and :class:`ControlPlane` is the
pure policy core (roles, Busy Guard, Emergency ratchet, Panic Lock, update_id
replay). Nothing polled Telegram, so no owner command could ever arrive. This
module is that missing half — and nothing else:

    aiogram Bot.get_updates  (long polling, offset = update_id + 1)
        → TelegramGateway.handle_update
              · mapping/object normalisation (aiogram models → plain mappings)
              · the ControlPlane's own update_id dedup and Panic Lock ALWAYS
                run first (they are policy, not transport)
              · `/start` `/help` `/myid` `/lock` `/unlock` → ControlPlane
              · callback queries            → ControlPlane.handle_callback
              · W.8-2 owner words
                (`start|pause|resume|stop|progress|eta|continuous on|off`)
                  → OWNER-only role check, then the injected BOOTSTRAP_CONTROL
                    handler (registered by the bootstrap service/paper loop)
        → the reply goes back through the signaling plane (bucket, idempotency,
          outbox) — and when there is no bot token the send is REFUSED with
          ``E-TELE-001`` and the refusal is returned, never hidden.

Transport seam (G9): the gateway never imports aiogram itself; the production
source does (:class:`AiogramUpdateSource`), tests inject a scripted source with
the same interface. A poll failure is contained and reported — the gateway does
not die because Telegram blinked, and it never invents an update.

CONTRACT_VERSION 4.0.0.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Sequence

from apex.config import Config
from apex.telegram import control_plane as CP

CONTRACT_VERSION = "4.0.0"

#: The W.8-2 / W.6 owner words that control the first-run bootstrap.
BOOTSTRAP_COMMANDS: Sequence[str] = (
    "start", "pause", "resume", "stop", "progress", "eta",
    "continuous on", "continuous off")
#: The control-plane action that carries one of the words above.
BOOTSTRAP_ACTION = "BOOTSTRAP_CONTROL"

#: Reply ceiling: Telegram rejects > 4096 characters; the plane truncates too.
REPLY_MAX_CHARS = 3500


class GatewayError(RuntimeError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class UpdateSource:
    """The transport seam: ``get_updates(offset, timeout) -> [update, ...]``."""

    async def get_updates(self, *, offset: Optional[int] = None,
                          timeout: float = 25.0, limit: int = 100
                          ) -> List[Mapping[str, Any]]:   # pragma: no cover
        raise NotImplementedError

    async def aclose(self) -> None:                      # pragma: no cover
        return None


class AiogramUpdateSource(UpdateSource):
    """Production long polling over the frozen SBOM pin (aiogram 3.7.0).

    ``Bot.get_updates`` is deliberately used instead of a Dispatcher: this
    gateway owns the control laws (the ControlPlane), so the transport must not
    introduce a second routing layer. The token comes from the environment
    only; without it the constructor raises ``E-TELE-001`` (never a fake bot).
    """

    def __init__(self, *, token: Optional[str] = None,
                 config: Optional[Config] = None, bot: Any = None) -> None:
        cfg = config or Config()
        token = token if token is not None else cfg.telegram_bot_token
        self._bot = bot
        if self._bot is None:
            if not token:
                raise GatewayError(
                    "E-TELE-001",
                    "TELEGRAM_BOT_TOKEN is env-only and is not set — the "
                    "gateway refuses to start (fail-closed, never faked)")
            from aiogram import Bot
            self._bot = Bot(token=token)
        self.offset: Optional[int] = None

    async def get_updates(self, *, offset: Optional[int] = None,
                          timeout: float = 25.0, limit: int = 100
                          ) -> List[Mapping[str, Any]]:
        effective = self.offset if offset is None else offset
        try:
            updates = await self._bot.get_updates(
                offset=effective, timeout=int(timeout), limit=int(limit))
        except Exception as exc:                     # network/poll failure
            raise GatewayError("POLL_FAILED", f"{type(exc).__name__}: "
                              f"{str(exc)[:200]}") from exc
        out: List[Mapping[str, Any]] = []
        for update in updates or ():
            plain = _as_mapping(update)
            if plain is not None:
                out.append(plain)
        return out

    async def aclose(self) -> None:
        session = getattr(self._bot, "session", None)
        close = getattr(session, "close", None)
        if callable(close):
            await close()


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _as_mapping(value: Any) -> Optional[Dict[str, Any]]:
    """aiogram model / pydantic model / plain mapping → a plain mapping."""
    if value is None:
        return None
    if isinstance(value, Mapping):
        return dict(value)
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            return dict(dump(exclude_none=True))
        except Exception:                            # pragma: no cover
            return None
    return None


def extract_update(update: Mapping[str, Any]) -> Dict[str, Any]:
    """One Telegram update → ``{update_id, chat_id, text, callback, kind}``.

    Unknown shapes yield ``kind="UNSUPPORTED"`` with ``chat_id=None`` — the
    gateway then reports it instead of guessing a sender.
    """
    update_id = update.get("update_id")
    if "callback_query" in update:
        query = _as_mapping(update.get("callback_query")) or {}
        message = _as_mapping(query.get("message")) or {}
        chat = _as_mapping(message.get("chat")) or {}
        sender = _as_mapping(query.get("from")) or {}
        return {"update_id": update_id, "kind": "CALLBACK",
                "chat_id": _chat_id(chat) or sender.get("id"),
                "text": None, "callback": query.get("data"),
                "callback_id": query.get("id")}
    for key in ("message", "edited_message", "channel_post"):
        if key in update:
            message = _as_mapping(update.get(key)) or {}
            chat = _as_mapping(message.get("chat")) or {}
            sender = _as_mapping(message.get("from")) or {}
            text = message.get("text")
            if text is None:
                caption = message.get("caption")
                text = caption
            return {"update_id": update_id, "kind": "MESSAGE",
                    "chat_id": _chat_id(chat) or sender.get("id"),
                    "text": text, "callback": None}
    return {"update_id": update_id, "kind": "UNSUPPORTED", "chat_id": None,
            "text": None, "callback": None}


def _chat_id(chat: Mapping[str, Any]) -> Optional[str]:
    if "id" not in chat:
        return None
    return str(chat["id"])


def normalize_command(text: Optional[str]) -> str:
    """``/Start@apex_bot extra`` → ``/start``; plain words are lower-cased and
    whitespace-collapsed so ``continuous   on`` matches the W.8-2 surface."""
    raw = (text or "").strip()
    if not raw:
        return ""
    if raw.startswith("/"):
        head = raw.split()[0]
        head = head.split("@", 1)[0]
        return head.lower()
    return " ".join(raw.lower().split())


def render_screen(screen: Mapping[str, Any]) -> str:
    """A tolerant plain-text render of a ControlPlane screen dict.

    Only fields that exist are printed — nothing is invented, and an unknown
    screen shape falls back to its own key/value lines.
    """
    lines: List[str] = []
    title = screen.get("title") or screen.get("screen")
    if title:
        lines.append(str(title))
    for key in ("rows", "items", "steps", "main_menu_guide", "glossary"):
        value = screen.get(key)
        if not value:
            continue
        if isinstance(value, Mapping):
            for name, entry in value.items():
                lines.append(f"• {name}: {_flatten(entry)}")
            continue
        for entry in value:
            lines.append(f"• {_flatten(entry)}")
    controls = screen.get("global_controls")
    if controls:
        lines.append("Controls: " + ", ".join(_flatten(c) for c in controls))
    if len(lines) == 1:
        for key, value in screen.items():
            if key in ("screen", "title", "rule"):
                continue
            lines.append(f"{key} = {_flatten(value)}")
    return "\n".join(lines)[:REPLY_MAX_CHARS]


def _flatten(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return " | ".join(_flatten(v) for v in value)
    if isinstance(value, Mapping):
        return ", ".join(f"{k}={_flatten(v)}" for k, v in value.items())
    return str(value)


# ---------------------------------------------------------------------------
# The gateway
# ---------------------------------------------------------------------------

class TelegramGateway:
    """Poll → authorise → route → reply, with every refusal recorded."""

    def __init__(self, *, control: CP.ControlPlane,
                 source: Optional[UpdateSource] = None,
                 notifier: Optional[Callable[[str, str], Awaitable[Any]]] = None,
                 bootstrap: Any = None,
                 clock: Optional[Callable[[], float]] = None,
                 utc_now: Optional[Callable[[], str]] = None,
                 poll_timeout: float = 25.0,
                 poll_limit: int = 100,
                 name: str = "gateway") -> None:
        self.control = control
        self.source = source
        self.bootstrap = bootstrap
        self._notifier = notifier
        self._clock = clock or time.monotonic
        self._utc_now = utc_now or _utc_now_ms
        self.poll_timeout = float(poll_timeout)
        self.poll_limit = int(poll_limit)
        self.offset: Optional[int] = None
        self.name = name
        self.handled: List[Dict[str, Any]] = []
        self.poll_errors: List[Dict[str, Any]] = []
        self.refusals: List[Dict[str, Any]] = []
        self._stopped = False

    # -- reply path ----------------------------------------------------------
    async def reply(self, chat_id: Any, text: str) -> Dict[str, Any]:
        if self._notifier is None:
            record = {"delivered": False, "reason": "NO_NOTIFIER_ENV_ONLY"}
            self.refusals.append({"chat_id": str(chat_id), **record})
            return record
        try:
            result = await self._notifier(str(chat_id), text)
        except Exception as exc:
            record = {"delivered": False,
                      "reason": f"{type(exc).__name__}: {str(exc)[:200]}"}
            self.refusals.append({"chat_id": str(chat_id), **record})
            return record
        return {"delivered": True, "result": _plain(result)}

    # -- one update ----------------------------------------------------------
    async def handle_update(self, update: Mapping[str, Any]) -> Dict[str, Any]:
        parsed = extract_update(update)
        update_id = parsed["update_id"]
        chat_id = parsed["chat_id"]
        base = {"update_id": update_id, "kind": parsed["kind"],
                "chat_id": None if chat_id is None else str(chat_id)}
        if parsed["kind"] == "UNSUPPORTED" or chat_id is None:
            record = {**base, "ok": False, "reason": "UNSUPPORTED_UPDATE"}
            self.handled.append(record)
            return record

        if parsed["kind"] == "CALLBACK":
            result = await self.control.handle_callback(
                chat_id, str(parsed["callback"]), update_id=update_id)
            record = {**base, "route": "CALLBACK", **result}
            self.handled.append(record)
            await self._reply_from(chat_id, result)
            return record

        command = normalize_command(parsed["text"])
        if command in BOOTSTRAP_COMMANDS:
            record = {**base, "route": "BOOTSTRAP", **await self._bootstrap(
                chat_id, command, update_id)}
            self.handled.append(record)
            await self._reply_from(chat_id, record)
            return record

        result = await self.control.handle_command(chat_id, command or "",
                                                   update_id=update_id)
        record = {**base, "route": "COMMAND", **result}
        self.handled.append(record)
        await self._reply_from(chat_id, result)
        return record

    async def _bootstrap(self, chat_id: Any, command: str,
                         update_id: Any) -> Dict[str, Any]:
        """W.8-2 owner words are OWNER-only and go through the handler seam —
        an unwired handler is refused by ControlPlane.dispatch, never faked."""
        verdict = self.control.access.check(chat_id, required="OWNER",
                                            action="BOOTSTRAP_CONTROL")
        if not verdict.allowed:
            self.refusals.append({"chat_id": str(chat_id), "command": command,
                                  "reason": "OWNER_ONLY",
                                  "audit_id": verdict.audit_id})
            return {"ok": False, "reason": "OWNER_ONLY", "command": command,
                    "audit_id": verdict.audit_id,
                    "rule": "W.8-2 owner control contract"}
        # §5.7: while the Panic Lock is engaged every bearer command is refused
        # (the lock is checked before anything is dispatched to the runner).
        lock = self.control.locked_verdict(command)
        if lock["blocked"]:
            self.refusals.append({"chat_id": str(chat_id), "command": command,
                                  "reason": lock["reason"]})
            return {"ok": False, "command": command, **lock}
        if update_id is not None:
            replay = self.control.updates.replay_of(update_id)
            if replay is not None:
                return {"replayed": True, **replay}
        dispatched = await self.control.dispatch(
            BOOTSTRAP_ACTION, {"chat_id": str(chat_id), "command": command})
        result = {"ok": bool(dispatched.get("ok")), "command": command,
                  **dispatched}
        if update_id is not None:
            self.control.updates.record(update_id, _plain(result))
        return result

    async def _reply_from(self, chat_id: Any, result: Mapping[str, Any]
                          ) -> None:
        text = self._render(result)
        if text:
            await self.reply(chat_id, text)

    @staticmethod
    def _render(result: Mapping[str, Any]) -> str:
        """One plain-text reply for one handled update.

        A handler verdict nested under ``result`` (the dispatch seam) is folded
        in so the owner sees the same facts the dispatcher returned.
        """
        facts: Dict[str, Any] = dict(result)
        nested = result.get("result")
        if isinstance(nested, Mapping):
            for key, value in nested.items():
                facts.setdefault(key, value)
        if facts.get("screen"):
            return render_screen(facts)
        if facts.get("supported"):
            return ("Unknown command. Supported: "
                    + ", ".join(str(c) for c in facts["supported"]))
        if facts.get("replayed"):
            return "Duplicate update ignored (update_id replay guard)."
        if not facts.get("ok", False) and facts.get("reason"):
            detail = facts.get("detail")
            return f"Refused: {facts['reason']}" + (
                f" — {detail}" if detail else "")
        bits: List[str] = []
        if facts.get("command"):
            bits.append(str(facts["command"]))
        for key in ("accepted", "note", "state", "percent_complete",
                    "eta_seconds", "cells_completed", "cells_remaining",
                    "bars_ingested", "trades", "effect", "label"):
            if facts.get(key) is not None:
                bits.append(f"{key}={_flatten(facts[key])}")
        if bits:
            return " · ".join(bits)[:REPLY_MAX_CHARS]
        return "OK" if facts.get("ok") else ""

    # -- polling -------------------------------------------------------------
    async def run_once(self) -> Dict[str, Any]:
        if self.source is None:
            raise GatewayError("NO_UPDATE_SOURCE")
        try:
            updates = await self.source.get_updates(
                offset=self.offset, timeout=self.poll_timeout,
                limit=self.poll_limit)
        except GatewayError as exc:
            self.poll_errors.append({"reason": exc.reason, "detail": exc.detail,
                                     "at": self._utc_now()})
            return {"polled": 0, "handled": 0, "error": exc.reason,
                    "detail": exc.detail}
        handled = 0
        for update in updates:
            record = await self.handle_update(update)
            handled += 1
            update_id = record.get("update_id")
            if isinstance(update_id, int):
                self.offset = max(self.offset or 0, update_id + 1)
        return {"polled": len(updates), "handled": handled,
                "offset": self.offset}

    async def run(self, *, stop: Optional[Callable[[], bool]] = None,
                  sleep: Optional[Callable[[float], Awaitable[None]]] = None
                  ) -> Dict[str, Any]:
        """The polling loop. Every poll failure is contained and reported."""
        waiter = sleep or asyncio.sleep
        rounds = 0
        while not self._stopped and not (stop is not None and stop()):
            outcome = await self.run_once()
            rounds += 1
            if outcome.get("error"):
                await waiter(1.0)          # bounded backoff, never a hot loop
        return {"rounds": rounds, "handled": len(self.handled),
                "poll_errors": len(self.poll_errors),
                "refusals": len(self.refusals), "offset": self.offset,
                "contract_version": CONTRACT_VERSION}

    def stop(self) -> None:
        self._stopped = True

    async def aclose(self) -> None:
        self.stop()
        if self.source is not None:
            await self.source.aclose()


def _utc_now_ms() -> str:
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


__all__ = [
    "AiogramUpdateSource", "BOOTSTRAP_ACTION", "BOOTSTRAP_COMMANDS",
    "CONTRACT_VERSION", "GatewayError", "REPLY_MAX_CHARS", "TelegramGateway",
    "UpdateSource", "extract_update", "normalize_command", "render_screen",
]
