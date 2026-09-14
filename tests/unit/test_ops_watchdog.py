"""CP-8 — AI.9 / Ch.23 safeguards: heartbeat-loss escalation, the CRITICAL-only
send-only Gmail isolation, the hash-chained recovery log, the fail-closed drive
and the timeout rows (MATRIX Part III CP-8 rows C8-WD|1..16)."""

from __future__ import annotations

import asyncio

import pytest

from apex.ops import watchdog as wd


def _run(coro):
    return asyncio.run(coro)


class _FakePlane:
    """Stands in for the CP-7 SignalingPlane public contract only."""

    def __init__(self):
        self.calls = []

    async def check_heartbeat(self, *, missed: int, snapshot_id: str = ""):
        self.calls.append({"missed": missed, "snapshot_id": snapshot_id})
        return {"alert": "HOST_DOWN", "channel": "TELEGRAM", "missed": missed}


def _channel(*, credential="token", transport=None, to="owner@example.com"):
    return wd.SendOnlyGmailChannel(
        credential_provider=(lambda: credential) if credential else None,
        transport=transport, to_address=to)


# --------------------------------------------------------------------------
# Constants frozen from Ch.17 §17.1 / Ch.23
# --------------------------------------------------------------------------

class TestConstants:
    def test_heartbeat_cadence(self):
        assert wd.HEARTBEAT_INTERVAL_SECONDS == 60
        assert wd.HEARTBEAT_MISS_LIMIT == 3

    def test_timeout_rows(self):
        assert wd.DECISION_TIMEOUT_SECONDS == 60
        assert wd.RECOVERY_PROGRESS_TIMEOUT_SECONDS == 300

    def test_gmail_is_critical_only(self):
        assert wd.GMAIL_MIN_SEVERITY == "CRITICAL"
        assert set(wd.GMAIL_ALLOWED_ALERTS) == {"HOST_DOWN", "FAIL_CLOSED"}

    def test_summary_adds_no_environment_name(self):
        summary = wd.watchdog_summary()
        assert summary["env_names_added"] == []
        assert summary["states"] == list(wd.WATCHDOG_STATES)

    def test_recovery_migration_is_m204(self):
        names = [name for name, _ in wd.OPS_MIGRATIONS]
        assert names == ["M204_ops_recovery_log"]


# --------------------------------------------------------------------------
# The independent channel
# --------------------------------------------------------------------------

class TestSendOnlyGmailChannel:
    def test_host_down_critical_is_accepted(self):
        channel = _channel()
        record = channel.send(wd.OutboundMail(alert="HOST_DOWN",
                                             severity="CRITICAL",
                                             subject="s", body="b"))
        assert record["alert"] == "HOST_DOWN"
        assert record["result"]["delivered"] is True
        assert len(channel.sent) == 1

    def test_non_critical_severity_is_refused(self):
        channel = _channel()
        with pytest.raises(wd.WatchdogError) as err:
            channel.send(wd.OutboundMail(alert="HOST_DOWN", severity="HIGH",
                                         subject="s", body="b"))
        assert err.value.reason == "GMAIL_SEVERITY_REFUSED"
        assert channel.refused[0]["reason"] == "GMAIL_CRITICAL_ONLY_ISOLATION"

    @pytest.mark.parametrize("alert", ["HEARTBEAT", "STORAGE", "VETO",
                                       "STALE_DATA", "DRAWDOWN"])
    def test_non_independent_alerts_never_travel_on_gmail(self, alert):
        channel = _channel()
        with pytest.raises(wd.WatchdogError) as err:
            channel.send(wd.OutboundMail(alert=alert, severity="CRITICAL",
                                         subject="s", body="b"))
        assert err.value.reason == "GMAIL_SEVERITY_REFUSED"

    def test_absent_credential_fails_closed_without_inventing_one(self):
        channel = _channel(credential=None)
        with pytest.raises(wd.GmailChannelUnavailable) as err:
            channel.send(wd.OutboundMail(alert="FAIL_CLOSED", severity="CRITICAL",
                                         subject="s", body="b"))
        assert err.value.reason == "INDEPENDENT_CHANNEL_CREDENTIAL_ABSENT"
        assert channel.sent == []

    def test_channel_exposes_no_read_capability(self):
        channel = _channel()
        public = {name for name in dir(channel) if not name.startswith("_")}
        assert not {name for name in public
                    if any(word in name for word in ("read", "fetch", "poll",
                                                     "inbox", "get_updates"))}

    def test_custom_transport_receives_the_injected_credential(self):
        seen = {}

        def transport(mail, credential):
            seen["credential"] = credential
            return {"delivered": True}

        channel = _channel(credential="secret-token", transport=transport)
        channel.send(wd.OutboundMail(alert="HOST_DOWN", severity="CRITICAL",
                                     subject="s", body="b"))
        assert seen["credential"] == "secret-token"


# --------------------------------------------------------------------------
# Recovery log
# --------------------------------------------------------------------------

class TestRecoveryLog:
    def test_append_only_chain_is_intact(self):
        log = wd.RecoveryLog()
        _run(log.append(kind="HOST_DOWN", reason="3 missed",
                        snapshot_id="snap-1", recovery_state="NORMAL"))
        _run(log.append(kind="STATE_TRANSITION", reason="NORMAL -> RECOVERY",
                        snapshot_id="snap-2", recovery_state="RECOVERY"))
        verdict = log.verify()
        assert verdict["intact"] is True
        assert verdict["records"] == 2
        assert len(log) == 2

    def test_ids_are_content_hashes(self):
        log = wd.RecoveryLog()
        row = _run(log.append(kind="HOST_DOWN", reason="r", snapshot_id="s"))
        assert row["log_id"] == "rec-" + row["payload_hash"][:32]

    def test_tampering_breaks_the_chain(self):
        log = wd.RecoveryLog()
        _run(log.append(kind="HOST_DOWN", reason="r", snapshot_id="s"))
        log.rows()[0]["reason"] = "rewritten"
        assert log.verify()["intact"] is False

    def test_durable_rows_survive_reopen(self, tmp_path):
        path = str(tmp_path / "ops.sqlite3")

        async def _write():
            log = await wd.RecoveryLog(path=path).open()
            await log.append(kind="HOST_DOWN", reason="r", snapshot_id="s")
            await log.close()

        async def _read():
            log = await wd.RecoveryLog(path=path).open()
            rows = log.rows()
            await log.close()
            return rows

        _run(_write())
        rows = _run(_read())
        assert len(rows) == 1
        # and the reloaded chain still verifies + keeps extending
        async def _extend():
            log = await wd.RecoveryLog(path=path).open()
            assert log.verify()["intact"] is True
            await log.append(kind="STATE_TRANSITION", reason="r2",
                             snapshot_id="s2")
            verdict = log.verify()
            await log.close()
            return verdict

        verdict = _run(_extend())
        assert verdict["intact"] is True
        assert verdict["records"] == 2


# --------------------------------------------------------------------------
# Fail-closed + timeouts
# --------------------------------------------------------------------------

class TestFailClosedDrive:
    def test_protective_orders_are_preserved_and_entries_cancelled(self):
        plan = wd.fail_closed_entry(
            reason="VETO_STALE_DATA", snapshot_id="snap-1",
            recovery_state="AWAITING_OWNER",
            open_orders=[{"order_id": "o1", "type": "STOP_LOSS"},
                         {"order_id": "o2", "type": "ENTRY"},
                         {"order_id": "o3", "type": "TAKE_PROFIT"}])
        assert plan["mode"] == "FAIL_CLOSED"
        assert plan["allow_new_entry"] is False
        assert plan["allow_new_capital"] is False
        assert plan["protective_preserved"] == ["o1", "o3"]
        assert plan["cancel_pending"] == ["o2"]
        assert plan["autonomous_ladder_climb"] is False

    def test_log_fields_carry_reason_snapshot_and_state(self):
        plan = wd.fail_closed_entry(reason="VETO_X", snapshot_id="snap-9",
                                    recovery_state="MANUAL_OVERRIDE")
        assert plan["log_fields"] == {"kind": "FAIL_CLOSED_ENTRY",
                                      "reason": "VETO_X", "snapshot_id": "snap-9",
                                      "recovery_state": "MANUAL_OVERRIDE"}

    def test_normal_state_timeout_is_60s(self):
        assert wd.watchdog_timeout(state="NORMAL",
                                   seconds_since_event=59.9)["drive_emergency_close"] \
            is False
        out = wd.watchdog_timeout(state="NORMAL", seconds_since_event=60.0)
        assert out["drive_emergency_close"] is True
        assert out["action"] == "EMERGENCY_CLOSE"
        assert out["reason"] == "NO_DECISION_FOR_60S"

    def test_recovery_state_timeout_is_300s(self):
        assert wd.watchdog_timeout(state="RECOVERY",
                                   seconds_since_event=299.0)["drive_emergency_close"] \
            is False
        out = wd.watchdog_timeout(state="RECOVERY", seconds_since_event=300.0)
        assert out["reason"] == "NO_RECOVERY_PROGRESS_FOR_300S"

    def test_fail_closed_state_has_no_timeout_row(self):
        out = wd.watchdog_timeout(state="FAIL_CLOSED",
                                  seconds_since_event=10_000.0)
        assert out["drive_emergency_close"] is False

    def test_unknown_state_refused(self):
        with pytest.raises(wd.WatchdogError) as err:
            wd.watchdog_timeout(state="SLEEPY", seconds_since_event=1.0)
        assert err.value.reason == "WATCHDOG_STATE_QX"


# --------------------------------------------------------------------------
# The watchdog loop
# --------------------------------------------------------------------------

class TestWatchdogHeartbeat:
    def _watchdog(self, *, channel=None, plane=None, log=None, clock=None):
        return wd.Watchdog(independent=channel, telegram_plane=plane,
                           recovery_log=log,
                           now=(clock if clock is not None else None))

    def test_three_missed_heartbeats_raise_host_down(self):
        clock = {"t": 1_000.0}
        dog = self._watchdog(clock=lambda: clock["t"])
        dog.heartbeat(at=1_000.0)
        verdict = _run(dog.check(snapshot_id="snap-1", at=1_000.0 + 180.0))
        assert verdict["missed"] == 3
        assert verdict["host_down"] is True
        assert verdict["escalation"]["alert"] == "HOST_DOWN"
        assert verdict["escalation"]["metric"] == "watchdog_heartbeat_miss"
        assert verdict["escalation"]["threshold"] == "3 consecutive"
        assert verdict["escalation"]["observed"] == 3

    def test_two_missed_heartbeats_stay_quiet(self):
        dog = self._watchdog()
        dog.heartbeat(at=1_000.0)
        verdict = _run(dog.check(snapshot_id="snap-1", at=1_000.0 + 120.0))
        assert verdict["missed"] == 2
        assert verdict["host_down"] is False
        assert verdict["escalation"]["alert"] is None

    def test_a_new_heartbeat_resets_the_counter(self):
        dog = self._watchdog()
        dog.heartbeat(at=1_000.0)
        _run(dog.check(at=1_000.0 + 180.0))
        dog.heartbeat(at=1_000.0 + 200.0)
        assert dog.missed == 0
        verdict = _run(dog.check(at=1_000.0 + 230.0))
        assert verdict["missed"] == 0
        assert verdict["host_down"] is False

    def test_no_heartbeat_yet_never_escalates(self):
        dog = self._watchdog()
        verdict = _run(dog.check(at=9_999_999.0))
        assert verdict["missed"] == 0
        assert verdict["host_down"] is False

    def test_host_down_travels_on_the_independent_channel_first(self):
        channel = _channel()
        plane = _FakePlane()
        log = wd.RecoveryLog()
        dog = self._watchdog(channel=channel, plane=plane, log=log)
        dog.heartbeat(at=1_000.0)
        verdict = _run(dog.check(snapshot_id="snap-1", at=1_000.0 + 180.0))
        assert verdict["escalation"]["independent_send"]["alert"] == "HOST_DOWN"
        assert verdict["escalation"]["independent_channel"] is True
        # the Telegram plane is routed through its public contract only
        assert plane.calls == [{"missed": 3, "snapshot_id": "snap-1"}]
        assert verdict["escalation"]["telegram"]["alert"] == "HOST_DOWN"
        # the recovery log recorded the incident with the snapshot id
        assert log.rows()[0]["kind"] == "HOST_DOWN"
        assert log.rows()[0]["snapshot_id"] == "snap-1"

    def test_missing_independent_channel_is_recorded_not_faked(self):
        dog = self._watchdog()
        dog.heartbeat(at=1_000.0)
        verdict = _run(dog.check(snapshot_id="snap-1", at=1_000.0 + 180.0))
        record = verdict["escalation"]["independent_send"]
        assert record["delivered"] is False
        assert record["reason"] == "INDEPENDENT_CHANNEL_NOT_CONFIGURED"

    def test_credential_less_channel_fails_closed_visibly(self):
        dog = self._watchdog(channel=_channel(credential=None))
        dog.heartbeat(at=1_000.0)
        verdict = _run(dog.check(snapshot_id="snap-1", at=1_000.0 + 180.0))
        record = verdict["escalation"]["independent_send"]
        assert record["delivered"] is False
        assert record["reason"] == "INDEPENDENT_CHANNEL_CREDENTIAL_ABSENT"

    def test_history_records_every_pass(self):
        dog = self._watchdog()
        dog.heartbeat(at=1_000.0)
        _run(dog.check(at=1_000.0 + 60.0))
        _run(dog.check(at=1_000.0 + 240.0))
        assert [row["missed"] for row in dog.history] == [1, 4]

    def test_interval_and_limit_are_configurable_by_construction(self):
        dog = wd.Watchdog(interval_seconds=10, miss_limit=2)
        dog.heartbeat(at=100.0)
        assert _run(dog.check(at=125.0))["host_down"] is True


class TestWatchdogStates:
    def test_enter_fail_closed_sets_state_and_alerts(self):
        channel = _channel()
        log = wd.RecoveryLog()
        dog = wd.Watchdog(independent=channel, recovery_log=log)
        plan = _run(dog.enter_fail_closed(reason="VETO_STALE_DATA",
                                          snapshot_id="snap-1",
                                          open_orders=[]))
        assert dog.state == "FAIL_CLOSED"
        assert plan["mode"] == "FAIL_CLOSED"
        assert plan["independent_send"]["alert"] == "FAIL_CLOSED"
        assert log.rows()[0]["kind"] == "FAIL_CLOSED_ENTRY"
        assert log.verify()["intact"] is True

    def test_resolve_to_recovery_requires_reconciliation(self):
        log = wd.RecoveryLog()
        dog = wd.Watchdog(recovery_log=log)
        _run(dog.enter_fail_closed(reason="r", snapshot_id="s"))
        out = _run(dog.resolve(to_state="RECOVERY", snapshot_id="snap-2"))
        assert out["require_startup_reconciliation"] is True
        assert dog.state == "RECOVERY"
        assert log.rows()[-1]["kind"] == "STATE_TRANSITION"

    def test_resolve_to_a_bogus_state_is_refused(self):
        dog = wd.Watchdog()
        with pytest.raises(wd.WatchdogError) as err:
            _run(dog.resolve(to_state="WHATEVER"))
        assert err.value.reason == "WATCHDOG_TARGET_QX"

    def test_manual_override_is_a_recorded_transition(self):
        dog = wd.Watchdog()
        _run(dog.enter_fail_closed(reason="r", snapshot_id="s"))
        out = _run(dog.resolve(to_state="MANUAL_OVERRIDE"))
        assert out["to"] == "MANUAL_OVERRIDE"
        assert out["require_startup_reconciliation"] is False
