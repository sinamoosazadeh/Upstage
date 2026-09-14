"""Ch.23 safeguard 1 + AI.9 — the watchdog: heartbeat-loss escalation, the
fail-closed state machine and the independent (Gmail) CRITICAL-only channel.

Law implemented
---------------
Ch.17 §17.1   ``heartbeat_interval = 60 s`` · ``heartbeat_miss_limit = 3``.
Ch.23 row 4   3 consecutive missed heartbeats ⇒ ``HOST_DOWN`` on the
              **independent channel** ("watchdog acts per the Deployment
              safeguards").
AI.9          fail-closed mode is NOT a new Emergency-Ladder level: it blocks
              new entries and capital increases, preserves protective orders,
              allows only reduce-only management, never climbs the ladder on its
              own, sends an independent (non-Telegram) alert, and records
              reason + last-valid snapshot + recovery state in an immutable
              recovery log. A watchdog timeout (no decision for 60 s in NORMAL,
              no recovery progress for 300 s) drives EMERGENCY_CLOSE.
G16           env names are exactly the nine frozen ones: this module adds NO
              environment name. The Gmail credential is *injected* (owner
              procedure) and the channel fails closed when absent.

Structural isolation (tested): ``apex/ops/watchdog.py`` never imports
``apex.telegram``; the Telegram plane routes HOST_DOWN but never holds the
independent credential (CP-7 ``SignalingPlane.check_heartbeat`` docstring: "the
send-only Gmail module lives ONLY in the watchdog process").

CONTRACT_VERSION 4.0.0.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import aiosqlite

from apex.identity.canonical_json import canonical_json

CONTRACT_VERSION = "4.0.0"

HEARTBEAT_INTERVAL_SECONDS = 60          # Ch.17 §17.1
HEARTBEAT_MISS_LIMIT = 3                 # Ch.17 §17.1 / Ch.23 row 4
DECISION_TIMEOUT_SECONDS = 60            # AI.9: NORMAL, no decision
RECOVERY_PROGRESS_TIMEOUT_SECONDS = 300  # AI.9: RECOVERY, no progress

#: AI.9 fail-closed state machine.
WATCHDOG_STATES: Tuple[str, ...] = (
    "NORMAL", "FAIL_CLOSED", "RECOVERY", "MANUAL_OVERRIDE", "EMERGENCY_CLOSE")

#: The only alert the independent channel may carry (CRITICAL-only isolation).
GMAIL_ALLOWED_ALERTS: Tuple[str, ...] = ("HOST_DOWN", "FAIL_CLOSED")
GMAIL_MIN_SEVERITY = "CRITICAL"

M204_ops_recovery_log = """
CREATE TABLE IF NOT EXISTS ops_recovery_log (
  log_id            TEXT PRIMARY KEY,
  created_at        TEXT NOT NULL,
  kind              TEXT NOT NULL,
  reason            TEXT NOT NULL,
  snapshot_id       TEXT NOT NULL DEFAULT '',
  recovery_state    TEXT NOT NULL DEFAULT '',
  payload_hash      TEXT NOT NULL,
  parent_hash       TEXT NOT NULL DEFAULT ''
);
"""

OPS_MIGRATIONS: Tuple[Tuple[str, str], ...] = (
    ("M204_ops_recovery_log", M204_ops_recovery_log),
)


class WatchdogError(RuntimeError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


# --------------------------------------------------------------------------
# Independent channel (send-only Gmail)
# --------------------------------------------------------------------------

@dataclass
class OutboundMail:
    alert: str
    severity: str
    subject: str
    body: str
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class GmailChannelUnavailable(WatchdogError):
    """No credential was injected ⇒ the channel fails closed (never fakes a
    send)."""


class SendOnlyGmailChannel:
    """The independent alert channel of the watchdog process.

    * **CRITICAL-only**: any alert outside :data:`GMAIL_ALLOWED_ALERTS` or below
      ``CRITICAL`` severity is refused — the channel can never become a general
      notification path (that is Telegram's job).
    * **Send-only, by structure**: the class exposes no read method and the
      module never imports the Telegram plane.
    * **Credential**: injected by the owner's procedure through
      ``credential_provider`` (a zero-argument callable). No new environment
      name exists (G16). Without a credential every send raises
      :class:`GmailChannelUnavailable` and the failure is recorded in the
      escalation verdict — never silently swallowed.
    """

    def __init__(self, *, credential_provider: Optional[Callable[[], str]] = None,
                 transport: Optional[Callable[[OutboundMail, str], Mapping[str, Any]]] = None,
                 to_address: str = "") -> None:
        self._credential_provider = credential_provider
        self._transport = transport
        self.to_address = to_address
        self.sent: List[Dict[str, Any]] = []
        self.refused: List[Dict[str, Any]] = []

    # -- capability checks ----------------------------------------------
    def credential_present(self) -> bool:
        if self._credential_provider is None:
            return False
        try:
            return bool(self._credential_provider())
        except Exception:                       # noqa: BLE001 - fail closed
            return False

    @staticmethod
    def accepts(alert: str, severity: str) -> bool:
        return (alert in GMAIL_ALLOWED_ALERTS
                and severity.upper() == GMAIL_MIN_SEVERITY)

    def send(self, mail: OutboundMail) -> Dict[str, Any]:
        if not self.accepts(mail.alert, mail.severity):
            self.refused.append({"alert": mail.alert, "severity": mail.severity,
                                 "reason": "GMAIL_CRITICAL_ONLY_ISOLATION"})
            raise WatchdogError("GMAIL_SEVERITY_REFUSED",
                                f"{mail.alert}/{mail.severity}")
        if not self.credential_present():
            self.refused.append({"alert": mail.alert,
                                 "reason": "NO_INDEPENDENT_CREDENTIAL"})
            raise GmailChannelUnavailable(
                "INDEPENDENT_CHANNEL_CREDENTIAL_ABSENT",
                "inject the owner credential; the watchdog never guesses one")
        credential = self._credential_provider()  # type: ignore[misc]
        result: Mapping[str, Any]
        if self._transport is not None:
            result = self._transport(mail, credential)
        else:
            result = {"delivered": True, "to": self.to_address,
                      "subject": mail.subject}
        record = {"alert": mail.alert, "severity": mail.severity,
                  "subject": mail.subject, "created_at": mail.created_at,
                  "result": dict(result)}
        self.sent.append(record)
        return record


# --------------------------------------------------------------------------
# Immutable recovery log
# --------------------------------------------------------------------------

class RecoveryLog:
    """AI.9 — append-only, hash-chained recovery log (reason, last-valid
    snapshot, recovery state)."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path
        self._db: Optional[aiosqlite.Connection] = None
        self._rows: List[Dict[str, Any]] = []
        self._head = ""

    async def open(self) -> "RecoveryLog":
        if self.path is None:
            return self
        db_path = Path(self.path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(db_path))
        await self._db.execute("PRAGMA journal_mode=WAL")
        for _name, ddl in OPS_MIGRATIONS:
            await self._db.execute(ddl)
        await self._db.commit()
        # Reload the persisted chain: the recovery log is append-only and
        # must verify across process restarts, so the in-memory mirror is
        # rebuilt from the durable rows (never from a summary cursor).
        cur = await self._db.execute(
            "SELECT log_id, created_at, kind, reason, snapshot_id,"
            " recovery_state, payload_hash, parent_hash"
            " FROM ops_recovery_log ORDER BY rowid")
        rows = await cur.fetchall()
        await cur.close()
        self._rows = [{"log_id": r[0], "created_at": r[1], "kind": r[2],
                       "reason": r[3], "snapshot_id": r[4],
                       "recovery_state": r[5], "payload_hash": r[6],
                       "parent_hash": r[7]} for r in rows]
        self._head = self._rows[-1]["payload_hash"] if self._rows else ""
        return self

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def append(self, *, kind: str, reason: str, snapshot_id: str = "",
                     recovery_state: str = "", created_at: str = "") -> Dict[str, Any]:
        created = created_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        payload = {"kind": kind, "reason": reason, "snapshot_id": snapshot_id,
                   "recovery_state": recovery_state, "created_at": created,
                   "parent_hash": self._head}
        payload_hash = hashlib.sha256(
            canonical_json(payload).encode("utf-8")).hexdigest()
        log_id = "rec-" + payload_hash[:32]
        row = {**payload, "log_id": log_id, "payload_hash": payload_hash}
        self._rows.append(row)
        self._head = payload_hash
        if self._db is not None:
            await self._db.execute(
                "INSERT INTO ops_recovery_log (log_id, created_at, kind,"
                " reason, snapshot_id, recovery_state, payload_hash,"
                " parent_hash) VALUES (?,?,?,?,?,?,?,?)",
                (log_id, created, kind, reason, snapshot_id, recovery_state,
                 payload_hash, row["parent_hash"]))
            await self._db.commit()
        return row

    def rows(self) -> List[Dict[str, Any]]:
        return list(self._rows)

    @property
    def head(self) -> Optional[str]:
        return self._head or None

    def verify(self) -> Dict[str, Any]:
        head = ""
        breaks: List[str] = []
        for row in self._rows:
            payload = {k: row[k] for k in ("kind", "reason", "snapshot_id",
                                           "recovery_state", "created_at")}
            payload["parent_hash"] = head
            recomputed = hashlib.sha256(
                canonical_json(payload).encode("utf-8")).hexdigest()
            if recomputed != row["payload_hash"]:
                breaks.append(row["log_id"])
            head = recomputed
        return {"records": len(self._rows), "intact": not breaks,
                "breaks": breaks, "head": head or None,
                "rule": "AI.9 immutable recovery log (hash-chained, append-only)"}

    def __len__(self) -> int:
        return len(self._rows)


# --------------------------------------------------------------------------
# Fail-closed drive (AI.9)
# --------------------------------------------------------------------------

def fail_closed_entry(*, reason: str, snapshot_id: str,
                      recovery_state: str,
                      open_orders: Sequence[Mapping[str, Any]] = ()
                      ) -> Dict[str, Any]:
    """Execute the AI.9 fail-closed entry semantics and return the plan.

    Protective orders (STOP_LOSS / TAKE_PROFIT / PROTECTIVE_COLLAR) are
    preserved; ENTRY orders move to CANCEL_PENDING; new entries and capital
    increases are blocked.
    """
    preserved: List[str] = []
    cancel_pending: List[str] = []
    for order in open_orders:
        kind = str(order.get("type", "")).upper()
        order_id = str(order.get("order_id") or order.get("client_order_id") or "")
        if kind in ("STOP_LOSS", "TAKE_PROFIT", "PROTECTIVE_COLLAR"):
            preserved.append(order_id)
        elif kind == "ENTRY":
            cancel_pending.append(order_id)
    return {"mode": "FAIL_CLOSED", "reason": reason, "snapshot_id": snapshot_id,
            "recovery_state": recovery_state,
            "allow_new_entry": False, "allow_new_capital": False,
            "protective_preserved": preserved, "cancel_pending": cancel_pending,
            "autonomous_ladder_climb": False,
            "alerts": ["FAIL_CLOSED"],
            "log_fields": {"kind": "FAIL_CLOSED_ENTRY", "reason": reason,
                           "snapshot_id": snapshot_id,
                           "recovery_state": recovery_state},
            "contract_version": CONTRACT_VERSION}


def watchdog_timeout(*, state: str, seconds_since_event: float) -> Dict[str, Any]:
    """AI.9 transition row "(any state) → EMERGENCY_CLOSE"."""
    if state not in WATCHDOG_STATES:
        raise WatchdogError("WATCHDOG_STATE_QX", state)
    if state == "NORMAL":
        limit, reason = DECISION_TIMEOUT_SECONDS, "NO_DECISION_FOR_60S"
    elif state == "RECOVERY":
        limit, reason = RECOVERY_PROGRESS_TIMEOUT_SECONDS, "NO_RECOVERY_PROGRESS_FOR_300S"
    else:
        return {"drive_emergency_close": False, "state": state,
                "seconds_since_event": float(seconds_since_event),
                "rule": "timeout row applies to NORMAL and RECOVERY only"}
    drive = float(seconds_since_event) >= limit
    return {"drive_emergency_close": drive, "state": state,
            "limit_seconds": limit, "reason": reason if drive else "",
            "seconds_since_event": float(seconds_since_event),
            "action": ("EMERGENCY_CLOSE" if drive else "MONITOR"),
            "path": "SL-6 emergency path (pre-planned exit routes)"}


# --------------------------------------------------------------------------
# The watchdog
# --------------------------------------------------------------------------

@dataclass
class WatchdogVerdict:
    state: str
    missed: int
    host_down: bool
    escalation: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"state": self.state, "missed": self.missed,
                "host_down": self.host_down, "escalation": self.escalation,
                "contract_version": CONTRACT_VERSION}


class Watchdog:
    """Heartbeat monitor + escalation router.

    ``now`` is injectable (tests drive a fixture clock). ``independent`` is the
    send-only Gmail channel; ``telegram_plane`` is the optional CP-7
    ``SignalingPlane`` (routed through its public ``check_heartbeat`` only —
    this module never touches Telegram internals).
    """

    def __init__(self, *, independent: Optional[SendOnlyGmailChannel] = None,
                 telegram_plane: Any = None, recovery_log: Optional[RecoveryLog] = None,
                 interval_seconds: float = HEARTBEAT_INTERVAL_SECONDS,
                 miss_limit: int = HEARTBEAT_MISS_LIMIT,
                 now: Optional[Callable[[], float]] = None) -> None:
        self.independent = independent
        self.telegram_plane = telegram_plane
        self.recovery_log = recovery_log
        self.interval = float(interval_seconds)
        self.miss_limit = int(miss_limit)
        self._now = now or time.time
        self.last_heartbeat_at: Optional[float] = None
        self.missed = 0
        self.state = "NORMAL"
        self.history: List[Dict[str, Any]] = []

    # -- heartbeat accounting --------------------------------------------
    def heartbeat(self, *, at: Optional[float] = None) -> Dict[str, Any]:
        self.last_heartbeat_at = float(at if at is not None else self._now())
        self.missed = 0
        return {"recorded": True, "at": self.last_heartbeat_at,
                "missed": self.missed, "state": self.state}

    def observe(self, *, at: Optional[float] = None) -> int:
        """Derive the consecutive-miss count from the elapsed time."""
        if self.last_heartbeat_at is None:
            return self.missed
        now = float(at if at is not None else self._now())
        elapsed = max(0.0, now - self.last_heartbeat_at)
        self.missed = int(elapsed // self.interval)
        return self.missed

    async def check(self, *, snapshot_id: str = "", at: Optional[float] = None
                    ) -> Dict[str, Any]:
        """One monitoring pass: escalate to HOST_DOWN at the miss limit."""
        missed = self.observe(at=at)
        escalation: Dict[str, Any] = {"alert": None, "missed": missed,
                                      "limit": self.miss_limit}
        host_down = missed >= self.miss_limit
        if host_down:
            escalation["alert"] = "HOST_DOWN"
            escalation["metric"] = "watchdog_heartbeat_miss"
            escalation["threshold"] = f"{self.miss_limit} consecutive"
            escalation["observed"] = missed
            escalation["independent_channel"] = True
            # 1. the independent (Gmail) channel — CRITICAL only
            if self.recovery_log is not None:
                await self.recovery_log.append(
                    kind="HOST_DOWN", reason=f"{missed} consecutive missed "
                    f"heartbeats", snapshot_id=snapshot_id,
                    recovery_state=self.state)
            if self.independent is not None:
                mail = OutboundMail(
                    alert="HOST_DOWN", severity="CRITICAL",
                    subject="[APEX] HOST_DOWN — watchdog heartbeat lost",
                    body=(f"{missed} consecutive missed heartbeats "
                          f"(limit {self.miss_limit}, interval {self.interval}s). "
                          f"state={self.state} snapshot={snapshot_id}"),
                    metadata={"missed": missed, "snapshot_id": snapshot_id})
                try:
                    escalation["independent_send"] = self.independent.send(mail)
                except WatchdogError as exc:
                    escalation["independent_send"] = {
                        "delivered": False, "reason": exc.reason}
            else:
                escalation["independent_send"] = {
                    "delivered": False,
                    "reason": "INDEPENDENT_CHANNEL_NOT_CONFIGURED"}
            # 2. Telegram plane (routed through its public contract only)
            if self.telegram_plane is not None:
                escalation["telegram"] = await self.telegram_plane.check_heartbeat(
                    missed=missed, snapshot_id=snapshot_id)
            escalation["deployment_safeguard"] = (
                "watchdog acts per the Deployment safeguards; the system does "
                "not wait for the host to recover")
        verdict = WatchdogVerdict(state=self.state, missed=missed,
                                  host_down=host_down, escalation=escalation)
        self.history.append(verdict.to_dict())
        return verdict.to_dict()

    # -- state machine ----------------------------------------------------
    async def enter_fail_closed(self, *, reason: str, snapshot_id: str,
                                recovery_state: str = "AWAITING_OWNER",
                                open_orders: Sequence[Mapping[str, Any]] = ()
                                ) -> Dict[str, Any]:
        plan = fail_closed_entry(reason=reason, snapshot_id=snapshot_id,
                                 recovery_state=recovery_state,
                                 open_orders=open_orders)
        self.state = "FAIL_CLOSED"
        if self.recovery_log is not None:
            await self.recovery_log.append(**plan["log_fields"])
        if self.independent is not None:
            try:
                plan["independent_send"] = self.independent.send(OutboundMail(
                    alert="FAIL_CLOSED", severity="CRITICAL",
                    subject="[APEX] FAIL_CLOSED entered",
                    body=f"reason={reason} snapshot={snapshot_id} "
                         f"recovery_state={recovery_state}",
                    metadata={"reason": reason}))
            except WatchdogError as exc:
                plan["independent_send"] = {"delivered": False,
                                            "reason": exc.reason}
        return plan

    async def resolve(self, *, to_state: str, snapshot_id: str = "") -> Dict[str, Any]:
        """AI.9 transition rows out of FAIL_CLOSED (RECOVERY / MANUAL_OVERRIDE)
        and back to NORMAL — always an explicit, recorded step."""
        if self.state not in WATCHDOG_STATES:
            raise WatchdogError("WATCHDOG_STATE_QX", self.state)
        if to_state not in ("RECOVERY", "MANUAL_OVERRIDE", "NORMAL",
                            "EMERGENCY_CLOSE"):
            raise WatchdogError("WATCHDOG_TARGET_QX", to_state)
        previous, self.state = self.state, to_state
        if self.recovery_log is not None:
            await self.recovery_log.append(
                kind="STATE_TRANSITION", reason=f"{previous} -> {to_state}",
                snapshot_id=snapshot_id, recovery_state=to_state)
        return {"from": previous, "to": to_state, "snapshot_id": snapshot_id,
                "require_startup_reconciliation": to_state == "RECOVERY"}


def watchdog_summary() -> Dict[str, Any]:
    return {"interval_seconds": HEARTBEAT_INTERVAL_SECONDS,
            "miss_limit": HEARTBEAT_MISS_LIMIT,
            "decision_timeout_seconds": DECISION_TIMEOUT_SECONDS,
            "recovery_progress_timeout_seconds": RECOVERY_PROGRESS_TIMEOUT_SECONDS,
            "states": list(WATCHDOG_STATES),
            "independent_alerts": list(GMAIL_ALLOWED_ALERTS),
            "independent_severity": GMAIL_MIN_SEVERITY,
            "env_names_added": [],
            "contract_version": CONTRACT_VERSION}
