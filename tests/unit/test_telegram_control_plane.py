"""CP-7 Telegram control-plane tests — Ch.21 §5.1–§5.8, §6, §7 (L17602–18060)
and the errors table E-VAL-020 / E-TELE-005.

Covered: the frozen screens and literals, OWNER/USER roles with NO ADMIN role,
auditable denials, the Trading wizard (4 steps, Core-10 single page, 14 TFs,
``3d`` unsupported, ``1mo`` canonical, 140 bundles), the Busy Guard
(MAX_CONCURRENT = 1 → E-VAL-020 + Stop), the Portfolio export wizard (CSV/JSON
only, ≤25 items, PAPER/LIVE, export root), Settings (5 options, EN/FA, UTC),
Info (four parts, 140 coverage), Help (6 items, 6 walkthroughs, glossary, FAQ 10,
/myid support, About without W-8), Emergency L1–L5 (OWNER-only, Yes/No
confirmation with a 90 s ``o-<hex>`` nonce, irreversible, ratchet-down refused
with RSK-ERR-506, L3 batching at 12, L5 safe mode, OWNER-only recovery), the
Panic Lock (/lock broadcast EN+FA, /unlock OWNER-only, only /myid and /unlock
served while locked), update_id replay protection, callback data ≤64 bytes and
the handler seam (a missing handler is refused, never faked).
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from apex.data_catalog.contracts import CORE10_SYMBOLS, TIMEFRAMES_14
from apex.errors import get_error_code
from apex.telegram import control_plane as P
from apex.telegram.signaling import CALLBACK_DATA_MAX_BYTES, SignalMessage

OWNER = "-1001234567890"
USER = "-1009999999999"
UNKNOWN = "-1005555555555"
WATCHDOG = "-2001234567890"


def run(coro):
    return asyncio.run(coro)


class FakeClock:
    def __init__(self, start: float = 500.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += float(seconds)


class FakeSignaling:
    """Test double for the signaling plane (G9): records sends and alerts."""

    def __init__(self, owner_chat_id: str = OWNER) -> None:
        self.owner_chat_id = owner_chat_id
        self.sent: List[SignalMessage] = []
        self.alerts: List[Dict[str, Any]] = []

    async def send(self, message: SignalMessage, *, force: bool = False):
        self.sent.append(message)
        return {"sent": True, "message_id": "7001", "state": "ACTIVE"}

    async def emit_alert(self, **kwargs):
        self.alerts.append(kwargs)
        return {"emitted": True, **kwargs}


def recorder(calls: List[Dict[str, Any]], name: str, *, ok: bool = True,
             fail: bool = False):
    async def handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        calls.append({"action": name, **payload})
        if fail:
            raise RuntimeError(f"{name} exploded")
        return {"ok": ok, "effect": name, "detail": f"{name} applied"}

    return handler


def plane(*, handlers: Optional[Dict[str, Any]] = None,
          signaling: Optional[FakeSignaling] = None,
          clock: Optional[FakeClock] = None,
          calls: Optional[List[Dict[str, Any]]] = None,
          environment: str = "PAPER",
          balance: Any = "10000") -> P.ControlPlane:
    log = calls if calls is not None else []
    wired = dict(handlers or {})
    for action in ("EMERGENCY_PAUSE", "EMERGENCY_DISABLE_NEW",
                   "EMERGENCY_CANCEL_ALL", "EMERGENCY_CLOSE_ALL",
                   "EMERGENCY_SAFE_MODE", "EXPORT", "BACKTEST_RUN",
                   "TRADING_WIZARD_RUN"):
        wired.setdefault(action, recorder(log, action))
    return P.ControlPlane(
        signaling=signaling if signaling is not None else FakeSignaling(),
        access=P.AccessControl(owner_chat_ids=[OWNER], user_chat_ids=[USER]),
        clock=clock or FakeClock(), utc_now=lambda: "2026-01-01T00:00:00.000Z",
        handlers=wired, environment=environment, paper_balance=balance)


# ---------------------------------------------------------------------------
# Frozen literals (Ch.21 §5/§6)
# ---------------------------------------------------------------------------

class TestFrozenLiterals:
    def test_roles_are_owner_and_user_only(self):
        assert P.ROLES == ("OWNER", "USER")
        assert "ADMIN" not in P.ROLES

    def test_no_admin_role_anywhere_in_the_module(self):
        source = Path(P.__file__).read_text()
        assert '"ADMIN"' not in source.replace("# no ADMIN role", "")

    def test_environments_have_no_shadow_mode(self):
        assert P.ENVS == ("PAPER", "LIVE", "RESEARCH", "BACKTEST")
        assert "SHADOW" not in P.ENVS

    def test_busy_guard_is_one_concurrent_run(self):
        assert P.MAX_CONCURRENT == 1
        assert P.BUSY_GUARD_STATE_TABLE == ("IDLE", "BUSY", "IDLE")

    def test_confirmation_nonce_is_ninety_seconds_and_o_hex(self):
        assert P.CONFIRMATION_NONCE_SECONDS == 90.0
        assert P.NONCE_KEY_FORMAT == "o-<hex>"

    def test_emergency_levels_and_semantics(self):
        assert P.EMERGENCY_LEVELS == ("L1", "L2", "L3", "L4", "L5")
        assert P.EMERGENCY_SEMANTICS["L1"] == "PAUSE"
        assert P.EMERGENCY_SEMANTICS["L2"] == "DISABLE_NEW — no new positions"
        assert P.EMERGENCY_SEMANTICS["L3"].startswith(
            "CANCEL_ALL — cancels all open orders (up to 12)")
        assert P.EMERGENCY_SEMANTICS["L4"] == "CLOSE_ALL"
        for phrase in ("preserves evidence", "sends notifications",
                       "halts trading", "read-only", "closes all positions",
                       "safe mode ON"):
            assert phrase in P.EMERGENCY_SEMANTICS["L5"]
        assert P.EMERGENCY_CANCEL_ALL_MAX_ORDERS == 12

    def test_export_wizard_literals(self):
        assert P.EXPORT_FORMATS == ("CSV", "JSON")
        assert P.EXPORT_TIME_RANGES == ("1h", "12h", "24h", "7d", "Custom")
        assert P.EXPORT_ENVIRONMENTS == ("PAPER", "LIVE")
        assert P.EXPORT_MAX_ITEMS == 25
        assert P.EXPORT_DEFAULT_PATH == "/Download/APEX_Reports/"
        assert P.EXPORT_EXAMPLE_SIZE_KB == 2.3

    def test_settings_languages_and_timezone(self):
        assert P.SETTINGS_OPTIONS == ("Language", "Confirmations", "Users",
                                      "Export Path", "Timezone")
        assert P.LANGUAGES == ("EN", "FA")
        assert P.TIMEZONE_DISPLAY == "UTC"

    def test_help_literals(self):
        assert len(P.HELP_ITEMS) == 6
        assert P.HELP_ITEMS == ("Getting Started", "Main Menu Guide", "Glossary",
                               "FAQ", "Support", "About")
        assert len(P.MAIN_MENU_GUIDE_WALKTHROUGHS) == 6
        assert P.GLOSSARY_TERMS == ("PF", "Sharpe", "Drawdown")
        assert P.FAQ_COUNT == 10

    def test_info_coverage_is_the_full_grid(self):
        assert P.INFO_COVERAGE_CELLS == 140
        assert P.INFO_SECTIONS == ("Market", "Data Coverage", "System Status")

    def test_trading_wizard_literals(self):
        assert P.TRADING_WIZARD_STEPS == ("Symbol", "Timeframe",
                                          "Max Leverage/Risk", "Confirm")
        assert P.UNSUPPORTED_TIMEFRAMES == frozenset({"3d"})
        assert P.MONTHLY_CANONICAL_ID == "1mo"

    def test_main_menu_is_eight_domain_buttons_two_per_row(self):
        assert len(P.MAIN_MENU_ROWS) == 4
        assert all(len(row) == 2 for row in P.MAIN_MENU_ROWS)
        assert sum(len(row) for row in P.MAIN_MENU_ROWS) == 8
        assert P.GLOBAL_CONTROLS == ("🔙 Back", "🏠 Home")

    def test_commands_and_panic_broadcasts(self):
        assert set(P.COMMANDS) == {"/start", "/myid", "/lock", "/unlock", "/help"}
        assert set(P.PANIC_LOCK_BROADCAST) == {"EN", "FA"}
        assert "/unlock" in P.PANIC_LOCK_BROADCAST["EN"]
        assert "/unlock" in P.PANIC_LOCK_BROADCAST["FA"]
        assert set(P.PANIC_UNLOCK_BROADCAST) == {"EN", "FA"}

    def test_callback_data_budget(self):
        assert P.CALLBACK_DATA_MAX_BYTES == CALLBACK_DATA_MAX_BYTES == 64

    def test_callback_slugs_stay_inside_the_budget(self):
        for label in ("📈 Trading", "🧪 Research Estimators 🔒 OWNER only",
                      "Max Leverage/Risk", "🔙 Back"):
            data = P._callback_for(label, "MAIN_MENU")
            assert len(data.encode("utf-8")) <= P.CALLBACK_DATA_MAX_BYTES


# ---------------------------------------------------------------------------
# §6 access control
# ---------------------------------------------------------------------------

class TestAccessControl:
    def test_an_unknown_chat_is_a_user_never_an_owner(self):
        access = P.AccessControl(owner_chat_ids=[OWNER], user_chat_ids=[USER])
        assert access.role_of(OWNER) == "OWNER"
        assert access.role_of(USER) == "USER"
        assert access.role_of(UNKNOWN) == "USER"

    def test_an_owner_passes_an_owner_only_check(self):
        access = P.AccessControl(owner_chat_ids=[OWNER])
        verdict = access.check(OWNER, required="OWNER", action="EMERGENCY")
        assert verdict.allowed is True
        assert verdict.role == "OWNER"
        assert verdict.audit_id.startswith("o-")

    def test_a_user_denial_is_auditable_and_recorded(self):
        access = P.AccessControl(owner_chat_ids=[OWNER], user_chat_ids=[USER])
        verdict = access.check(USER, required="OWNER", action="EMERGENCY")
        assert verdict.allowed is False
        assert verdict.reason == "OWNER_ONLY"
        assert verdict.audit_id.startswith("o-")
        assert len(access.denials) == 1
        assert access.denials[0] is verdict

    def test_a_research_denial_carries_research_only_and_block(self):
        access = P.AccessControl(owner_chat_ids=[OWNER], user_chat_ids=[USER])
        verdict = access.check(USER, required="OWNER", action="RESEARCH")
        assert verdict.reason == "OWNER_ONLY + RESEARCH_ONLY + BLOCK"

    def test_an_unrestricted_check_allows_any_role(self):
        access = P.AccessControl(owner_chat_ids=[OWNER])
        assert access.check(UNKNOWN, required=None).allowed is True

    def test_users_are_listed_and_removed(self):
        access = P.AccessControl(owner_chat_ids=[OWNER])
        access.add_user(USER)
        access.add_user(WATCHDOG, caution=True)
        listed = access.listed_users()
        assert {row["chat_id"] for row in listed} == {OWNER, USER, WATCHDOG}
        assert access.remove_user(USER)["removed"] is True
        assert USER not in {row["chat_id"] for row in access.listed_users()}

    def test_audit_ids_are_deterministic(self):
        access = P.AccessControl(owner_chat_ids=[OWNER], user_chat_ids=[USER])
        first = access.check(USER, required="OWNER", action="EMERGENCY").audit_id
        second = access.check(USER, required="OWNER", action="EMERGENCY").audit_id
        assert first == second


# ---------------------------------------------------------------------------
# §5.2/§5.7 confirmation nonce
# ---------------------------------------------------------------------------

class TestConfirmationNonce:
    def test_the_nonce_key_has_the_o_hex_format(self):
        key = P.nonce_key("EMERGENCY_L1", OWNER, "2026-01-01T00:00:00.000Z")
        assert key.startswith("o-")
        assert len(key) == 18
        int(key[2:], 16)

    def test_a_yes_confirmation_authorizes_once(self):
        clock = FakeClock()
        registry = P.ConfirmationRegistry(clock=clock, utc_now=lambda: "T0")
        nonce = registry.issue("EMERGENCY_L1", OWNER)
        verdict = registry.consume(nonce.key, action="EMERGENCY_L1",
                                   chat_id=OWNER, choice="YES")
        assert verdict["authorized"] is True
        assert verdict["irreversible"] is True
        assert verdict["ttl_seconds"] == 90.0

    def test_the_confirmation_is_irreversible_a_replay_never_re_authorizes(self):
        registry = P.ConfirmationRegistry(clock=FakeClock(), utc_now=lambda: "T0")
        nonce = registry.issue("EMERGENCY_L1", OWNER)
        registry.consume(nonce.key, action="EMERGENCY_L1", chat_id=OWNER,
                         choice="YES")
        replay = registry.consume(nonce.key, action="EMERGENCY_L1",
                                  chat_id=OWNER, choice="YES")
        assert replay["authorized"] is False
        assert replay["reason"] == "NONCE_ALREADY_CONSUMED"

    def test_a_no_confirmation_does_not_authorize(self):
        registry = P.ConfirmationRegistry(clock=FakeClock(), utc_now=lambda: "T0")
        nonce = registry.issue("EMERGENCY_L2", OWNER)
        verdict = registry.consume(nonce.key, action="EMERGENCY_L2",
                                   chat_id=OWNER, choice="NO")
        assert verdict["authorized"] is False
        assert verdict["reason"] is None

    def test_the_nonce_expires_after_ninety_seconds(self):
        clock = FakeClock()
        registry = P.ConfirmationRegistry(clock=clock, utc_now=lambda: "T0")
        nonce = registry.issue("EMERGENCY_L3", OWNER)
        clock.advance(P.CONFIRMATION_NONCE_SECONDS + 1)
        verdict = registry.consume(nonce.key, action="EMERGENCY_L3",
                                   chat_id=OWNER, choice="YES")
        assert verdict["authorized"] is False
        assert verdict["reason"] == "NONCE_EXPIRED"

    def test_a_foreign_chat_can_never_consume_someone_elses_nonce(self):
        registry = P.ConfirmationRegistry(clock=FakeClock(), utc_now=lambda: "T0")
        nonce = registry.issue("EMERGENCY_L4", OWNER)
        verdict = registry.consume(nonce.key, action="EMERGENCY_L4",
                                   chat_id=USER, choice="YES")
        assert verdict["authorized"] is False
        assert verdict["reason"] == "NONCE_CHAT_MISMATCH"
        assert verdict["audit_id"].startswith("o-")

    def test_an_unknown_key_or_action_is_refused(self):
        registry = P.ConfirmationRegistry(clock=FakeClock(), utc_now=lambda: "T0")
        assert registry.consume("o-deadbeefdeadbeef", action="EMERGENCY_L1",
                                chat_id=OWNER, choice="YES")["reason"] == \
            "NONCE_UNKNOWN"
        nonce = registry.issue("EMERGENCY_L1", OWNER)
        assert registry.consume(nonce.key, action="EMERGENCY_L5",
                                chat_id=OWNER, choice="YES")["reason"] == \
            "NONCE_ACTION_MISMATCH"

    def test_a_choice_that_is_neither_yes_nor_no_is_refused(self):
        registry = P.ConfirmationRegistry(clock=FakeClock(), utc_now=lambda: "T0")
        nonce = registry.issue("EMERGENCY_L1", OWNER)
        assert registry.consume(nonce.key, action="EMERGENCY_L1", chat_id=OWNER,
                                choice="MAYBE")["reason"] == "CHOICE_NOT_YES_NO"

    def test_pending_nonces_are_per_chat(self):
        registry = P.ConfirmationRegistry(clock=FakeClock(), utc_now=lambda: "T0")
        registry.issue("EMERGENCY_L1", OWNER)
        registry.issue("EMERGENCY_L2", USER)
        assert len(registry.pending(OWNER)) == 1
        assert len(registry.pending(USER)) == 1


# ---------------------------------------------------------------------------
# §5.2 Busy Guard
# ---------------------------------------------------------------------------

class TestBusyGuard:
    def test_the_state_table_is_idle_busy_idle(self):
        guard = P.BusyGuard()
        assert guard.state == "IDLE"
        assert guard.try_acquire("BT-1").allowed is True
        assert guard.state == "BUSY"
        assert guard.active_run_id == "BT-1"
        guard.release()
        assert guard.state == "IDLE"

    def test_a_second_concurrent_run_is_refused_with_e_val_020_and_a_stop(self):
        guard = P.BusyGuard()
        guard.try_acquire("BT-1")
        verdict = guard.try_acquire("BT-2")
        assert verdict.allowed is False
        assert verdict.error_code == get_error_code("E-VAL-020").code
        assert verdict.stop_button is True
        assert verdict.active_run_id == "BT-1"
        assert len(guard.rejections) == 1

    def test_the_concurrency_bound_cannot_be_changed(self):
        with pytest.raises(P.ControlPlaneError) as exc:
            P.BusyGuard(max_concurrent=2)
        assert exc.value.reason == "MAX_CONCURRENT_CHANGED"


# ---------------------------------------------------------------------------
# §7 update_id de-duplication
# ---------------------------------------------------------------------------

class TestUpdateDedup:
    def test_a_replayed_update_is_answered_and_never_re_executed(self):
        calls: List[Dict[str, Any]] = []
        cp = plane(calls=calls)

        async def body():
            first = await cp.handle_command(OWNER, "/myid", update_id=11)
            second = await cp.handle_command(OWNER, "/myid", update_id=11)
            return first, second

        first, second = run(body())
        assert first["ok"] is True
        assert second["replayed"] is True
        assert second["chat_id"] == OWNER
        assert cp.updates.is_replay(11) is True

    def test_the_deduplicator_is_bounded(self):
        dedup = P.UpdateDeduplicator(max_entries=2)
        for uid in (1, 2, 3):
            dedup.record(uid, {"ok": True, "update_id": uid})
        assert len(dedup) == 2
        assert dedup.is_replay(1) is False
        assert dedup.replay_of(3)["update_id"] == 3


# ---------------------------------------------------------------------------
# §5.3 export wizard validation
# ---------------------------------------------------------------------------

class TestExportWizard:
    def test_a_valid_csv_export(self):
        verdict = P.validate_export_request(
            items=["Positions", "Trades"], time_range="24h",
            environment="PAPER", fmt="CSV", path="/Download/APEX_Reports/x.csv")
        assert verdict["valid"] is True
        assert verdict["errors"] == ()
        assert verdict["example_output_size_kb"] == 2.3

    def test_json_is_valid_and_pdf_is_refused(self):
        assert P.validate_export_request(
            items=["Positions"], time_range="1h", environment="LIVE",
            fmt="JSON", path="/Download/APEX_Reports/x.json")["valid"] is True
        pdf = P.validate_export_request(
            items=["Positions"], time_range="1h", environment="PAPER",
            fmt="PDF", path="/Download/APEX_Reports/x.pdf")
        assert pdf["valid"] is False
        assert any(e.startswith("FORMAT_UNSUPPORTED:PDF") for e in pdf["errors"])

    def test_more_than_twenty_five_items_is_refused(self):
        verdict = P.validate_export_request(
            items=[f"i{n}" for n in range(26)], time_range="7d",
            environment="PAPER", fmt="CSV",
            path="/Download/APEX_Reports/x.csv")
        assert verdict["valid"] is False
        assert "TOO_MANY_ITEMS:26 > 25" in verdict["errors"]

    @pytest.mark.parametrize("kwargs,expected", [
        ({"time_range": "3d"}, "TIME_RANGE_UNSUPPORTED:3d"),
        ({"environment": "SHADOW"}, "ENVIRONMENT_UNSUPPORTED:SHADOW (PAPER or LIVE)"),
        ({"environment": "RESEARCH"},
         "ENVIRONMENT_UNSUPPORTED:RESEARCH (PAPER or LIVE)"),
        ({"path": "/tmp/leak.csv"}, "PATH_OUTSIDE_EXPORT_ROOT:/tmp/leak.csv"),
        ({"items": ()}, "NO_ITEMS_SELECTED")])
    def test_every_other_axis_fails_closed(self, kwargs, expected):
        request = {"items": ["Positions"], "time_range": "24h",
                   "environment": "PAPER", "fmt": "CSV",
                   "path": "/Download/APEX_Reports/x.csv"}
        request.update(kwargs)
        verdict = P.validate_export_request(**request)
        assert verdict["valid"] is False
        assert expected in verdict["errors"]


# ---------------------------------------------------------------------------
# §5.7 Emergency ratchet
# ---------------------------------------------------------------------------

class TestEmergencyRatchet:
    def test_a_level_ratchets_up(self):
        ratchet = P.EmergencyRatchet()
        assert ratchet.level is None
        assert ratchet.request("L1")["allowed"] is True
        assert ratchet.request("L3")["allowed"] is True
        assert ratchet.request("L5")["allowed"] is True
        assert ratchet.level == "L5"
        assert [h["requested"] for h in ratchet.history] == ["L1", "L3", "L5"]

    def test_ratcheting_down_is_refused_with_rsk_err_506(self):
        ratchet = P.EmergencyRatchet()
        ratchet.request("L4")
        verdict = ratchet.request("L2")
        assert verdict["allowed"] is False
        assert verdict["reason"] == "RATCHET_DOWN_FORBIDDEN"
        assert verdict["error_code"] == get_error_code("RSK-ERR-506").code
        assert ratchet.level == "L4"          # unchanged

    def test_the_same_level_is_idempotent_not_a_downgrade(self):
        ratchet = P.EmergencyRatchet()
        ratchet.request("L3")
        assert ratchet.request("L3")["allowed"] is True

    def test_only_the_owner_can_recover(self):
        ratchet = P.EmergencyRatchet()
        ratchet.request("L5")
        denied = ratchet.recover(role="USER")
        assert denied["recovered"] is False
        assert denied["reason"] == "OWNER_ONLY_RECOVERY"
        assert denied["error_code"] == get_error_code("RSK-ERR-506").code
        assert ratchet.level == "L5"
        recovered = ratchet.recover(role="OWNER")
        assert recovered["recovered"] is True
        assert recovered["previous"] == "L5"
        assert ratchet.level is None

    def test_an_unknown_level_is_refused(self):
        with pytest.raises(P.ControlPlaneError) as exc:
            P.EmergencyRatchet().request("L9")
        assert exc.value.reason == "EMERGENCY_LEVEL_UNKNOWN"


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------

class TestScreens:
    def test_the_main_menu_is_fully_unlocked_and_shows_utc(self):
        cp = plane(environment="PAPER", balance="12345.6")
        screen = cp.screen_main_menu()
        assert screen["full_unlock"] is True
        assert "Full Unlock" in screen["title"]
        assert "PAPER" in screen["title"]
        assert "12,345.6 USDT" in screen["title"]
        assert screen["title"].endswith("UTC")
        assert "UTC+3:30" not in screen["title"]       # ISSUE-CP7-007
        assert screen["rows"] == P.MAIN_MENU_ROWS

    def test_every_rendered_screen_ends_with_the_global_controls(self):
        cp = plane()
        for screen in ("MAIN_MENU", "TRADING", "PORTFOLIO", "LAB",
                       "LAB_RESEARCH", "INFO", "SETTINGS", "EMERGENCY", "HELP"):
            rendered = cp.render(screen, OWNER)
            assert rendered["rows"][-1] == P.GLOBAL_CONTROLS, screen
            assert rendered["global_controls_row"][0]["text"] == "🔙 Back"
            assert rendered["global_controls_row"][1]["text"] == "🏠 Home"
            assert rendered["markdown_v2"] == "MarkdownV2"

    def test_domain_buttons_stay_inside_the_ten_parameter_budget(self):
        cp = plane()
        for screen in ("MAIN_MENU", "TRADING", "PORTFOLIO", "LAB",
                       "LAB_RESEARCH", "INFO", "SETTINGS", "EMERGENCY", "HELP"):
            rendered = cp.render(screen, OWNER)
            assert rendered["domain_button_count"] <= 8, screen
            assert rendered["domain_row_count"] <= 4, screen
            for row in rendered["inline_keyboard"]:
                for button in row:
                    assert len(button["callback_data"].encode("utf-8")) <= 64

    def test_an_unknown_screen_is_refused(self):
        with pytest.raises(P.ControlPlaneError) as exc:
            plane().render("GALLERY", OWNER)
        assert exc.value.reason == "SCREEN_UNKNOWN"

    def test_the_lab_shows_research_to_the_owner_and_a_lock_to_a_user(self):
        cp = plane()
        owner = cp.screen_lab(OWNER)
        user = cp.screen_lab(USER)
        assert owner["research_visible"] is True
        assert owner["research_locked_label"] is False
        assert user["research_visible"] is False
        assert user["research_locked_label"] is True
        assert any("OWNER only" in label for row in user["rows"]
                   for label in row)
        # Backtest stays fully active for every user (§5.4)
        assert any("Backtest" in label for row in user["rows"]
                   for label in row)

    def test_a_user_opening_research_gets_an_auditable_denial(self):
        cp = plane()
        denied = cp.screen_research(USER)
        assert denied["screen"] == "ACCESS_DENIED"
        assert denied["reason"] == "RESEARCH_ONLY + BLOCK"
        assert denied["audit_id"].startswith("o-")

    def test_research_compare_produces_a_report_only_never_a_trade_plan(self):
        screen = plane().screen_research(OWNER)
        assert screen["screen"] == "LAB_RESEARCH"
        assert screen["status"] == "BLOCK for LIVE — Comparison only in BACKTEST"
        compare = screen["compare_in_backtest"]
        assert compare["produces"] == "Report only"
        assert compare["trade_plan"] is False
        assert compare["routed_to_live"] is False
        assert compare["data_source"] == "RESEARCH"
        assert [e["id"] for e in screen["estimators"]] == \
            ["R-ATR-002", "R-ATR-003", "R-ATR-007"]

    def test_the_info_screen_is_four_part_with_full_coverage(self):
        screen = plane().screen_info()
        assert set(screen["sections"]) == {"Market", "Data Coverage",
                                           "System Status"}
        assert screen["sections"]["Data Coverage"] == 140
        assert screen["sections"]["System Status"] == "HEALTHY"
        assert screen["sections"]["Market"]["top10"] == tuple(CORE10_SYMBOLS)
        assert screen["sections"]["Market"]["core10"] == tuple(CORE10_SYMBOLS)
        assert len(screen["sections"]["Market"]["levels"]) == 4

    def test_settings_are_five_options_en_fa_and_utc(self):
        screen = plane().screen_settings()
        assert screen["options"] == P.SETTINGS_OPTIONS
        assert screen["languages"] == ("EN", "FA")
        assert screen["timezone"] == "UTC"
        assert screen["values"]["Timezone"] == "UTC"
        assert screen["values"]["Language"] == "EN"
        assert screen["export_path"] == "/Download/APEX_Reports/"

    def test_the_emergency_screen_is_owner_only(self):
        cp = plane()
        owner = cp.screen_emergency(OWNER)
        assert owner["levels"] == ("L1", "L2", "L3", "L4", "L5")
        assert owner["confirmation"] == {"type": "Yes/No", "irreversible": True,
                                         "nonce_seconds": 90.0,
                                         "key_format": "o-<hex>"}
        assert owner["ratchet_down_error"] == get_error_code("RSK-ERR-506").code
        assert owner["cancel_all_max_orders"] == 12
        assert owner["panic_lock_commands"] == ("/lock", "/unlock")
        denied = cp.screen_emergency(USER)
        assert denied["screen"] == "ACCESS_DENIED"
        assert denied["reason"] == "OWNER_ONLY"
        assert denied["audit_id"].startswith("o-")

    def test_the_help_screen_is_six_items_with_support_and_no_w8(self):
        screen = plane().screen_help()
        assert len(screen["items"]) == 6
        assert len(screen["main_menu_guide"]) == 6
        assert screen["glossary"] == ("PF", "Sharpe", "Drawdown")
        assert screen["faq_count"] == 10
        assert screen["support_command"] == "/myid"
        assert "W-8" not in screen["about"].replace("no W-8 form content", "")
        assert "quant" in screen["about"]

    def test_the_trading_wizard_is_four_steps_over_the_full_grid(self):
        screen = plane().screen_trading()
        assert screen["steps"] == P.TRADING_WIZARD_STEPS
        assert screen["symbols"] == tuple(CORE10_SYMBOLS)
        assert screen["single_page"] is True
        assert screen["timeframes"] == tuple(TIMEFRAMES_14)
        assert screen["unsupported_timeframes"] == ("3d",)
        assert screen["monthly_canonical_id"] == "1mo"
        assert screen["bundles"] == 140
        assert screen["max_leverage_rule"] == "ceiling, not a fixed final value"
        assert screen["busy_guard"]["max_concurrent"] == 1
        assert screen["busy_guard"]["error_code"] == \
            get_error_code("E-VAL-020").code

    def test_3d_is_unsupported_in_the_wizard(self):
        with pytest.raises(P.ControlPlaneError) as exc:
            plane().screen_trading(symbol="BTCUSDT", timeframe="3d")
        assert exc.value.reason == "TIMEFRAME_UNSUPPORTED"

    def test_the_running_status_has_no_progress_bar(self):
        screen = plane().screen_running_status(uptime_seconds=3600, signals=2,
                                               exposure=1234.5,
                                               last_signal="BTCUSDT 1h")
        assert screen["progress_bar"] is False
        assert screen["uptime"] == 3600
        assert screen["exposure"] == "1,234.5"
        assert screen["last_signal"] == "BTCUSDT 1h"

    def test_the_portfolio_screen_is_csv_json_only(self):
        screen = plane().render("PORTFOLIO", OWNER)
        assert screen["pdf_supported"] is False
        assert screen["formats"] == ("CSV", "JSON")
        assert screen["max_items"] == 25
        assert screen["steps"] == ("Positions", "Orders", "Wallet", "Export",
                                   "Send/Share")


# ---------------------------------------------------------------------------
# Commands + Panic Lock
# ---------------------------------------------------------------------------

class TestCommands:
    def test_myid_returns_the_chat_id_and_role(self):
        result = run(plane().handle_command(USER, "/myid"))
        assert result["ok"] is True
        assert result["chat_id"] == USER
        assert result["role"] == "USER"

    def test_start_renders_the_main_menu(self):
        result = run(plane().handle_command(OWNER, "/start"))
        assert result["screen"] == "MAIN_MENU"
        assert result["role"] == "OWNER"

    def test_help_renders_the_help_screen(self):
        assert run(plane().handle_command(USER, "/help"))["screen"] == "HELP"

    def test_an_unknown_command_is_refused(self):
        result = run(plane().handle_command(USER, "/trade"))
        assert result["ok"] is False
        assert result["reason"] == "COMMAND_UNKNOWN"
        assert set(result["supported"]) == set(P.COMMANDS)

    def test_lock_engages_and_broadcasts_in_english_and_farsi(self):
        signaling = FakeSignaling()
        cp = plane(signaling=signaling)
        result = run(cp.handle_command(OWNER, "/lock"))
        assert result["locked"] is True
        assert cp.locked is True
        assert [m.priority for m in signaling.sent] == [0, 0]
        assert {m.text for m in signaling.sent} == set(
            P.PANIC_LOCK_BROADCAST.values())
        assert [m.alert for m in signaling.sent] == \
            ["PANIC_LOCK_ENGAGED", "PANIC_LOCK_ENGAGED"]

    def test_while_locked_only_myid_and_unlock_are_served(self):
        cp = plane()
        run(cp.handle_command(OWNER, "/lock"))
        assert run(cp.handle_command(OWNER, "/myid"))["ok"] is True
        blocked = run(cp.handle_command(OWNER, "/start"))
        assert blocked["ok"] is False
        assert blocked["reason"] == "PANIC_LOCK_ENGAGED"
        assert blocked["allowed_commands"] == ("/myid", "/unlock")
        callback = run(cp.handle_callback(OWNER, "SCREEN:TRADING"))
        assert callback["ok"] is False
        assert callback["reason"] == "PANIC_LOCK_ENGAGED"

    def test_unlock_is_owner_only(self):
        cp = plane()
        run(cp.handle_command(OWNER, "/lock"))
        denied = run(cp.handle_command(USER, "/unlock"))
        assert denied["ok"] is False
        assert denied["reason"] == "OWNER_ONLY"
        assert denied["locked"] is True
        assert denied["audit_id"].startswith("o-")
        released = run(cp.handle_command(OWNER, "/unlock"))
        assert released["ok"] is True
        assert cp.locked is False

    def test_a_broadcast_without_a_signaling_plane_is_audited_not_faked(self):
        cp = P.ControlPlane(signaling=None,
                            access=P.AccessControl(owner_chat_ids=[OWNER]),
                            clock=FakeClock(), utc_now=lambda: "T0")
        run(cp.handle_command(OWNER, "/lock"))
        assert cp.locked is True
        assert cp.audit[-1]["reason"] == "NO_SIGNALING_PLANE"


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

class TestCallbacks:
    def test_a_screen_callback_renders_that_screen(self):
        result = run(plane().handle_callback(OWNER, "SCREEN:TRADING"))
        assert result["ok"] is True
        assert result["screen"] == "TRADING"

    def test_back_and_home_return_to_the_main_menu(self):
        cp = plane()
        assert run(cp.handle_callback(OWNER, "BACK"))["screen"] == "MAIN_MENU"
        assert run(cp.handle_callback(USER, "HOME"))["screen"] == "MAIN_MENU"

    def test_an_unknown_action_is_refused(self):
        result = run(plane().handle_callback(OWNER, "LAUNCH_MISSILES"))
        assert result["ok"] is False
        assert result["reason"] == "ACTION_UNKNOWN"

    def test_callback_data_over_sixty_four_bytes_is_refused(self):
        result = run(plane().handle_callback(OWNER, "SCREEN:" + "x" * 80))
        assert result["ok"] is False
        assert result["reason"] == "CALLBACK_DATA_TOO_LONG"
        assert result["error_code"] == get_error_code("E-TELE-005").code
        assert result["max_bytes"] == 64

    def test_a_user_opening_research_by_callback_is_denied(self):
        result = run(plane().handle_callback(USER, "RESEARCH"))
        assert result["screen"] == "ACCESS_DENIED"
        assert result["reason"] == "RESEARCH_ONLY + BLOCK"
        assert result["audit_id"].startswith("o-")

    def test_a_backtest_run_is_refused_while_another_is_active(self):
        """§5.2 Busy Guard: the second concurrent run gets E-VAL-020 + Stop."""
        cp = plane()
        cp.busy.try_acquire("BT-1")
        result = run(cp.handle_callback(OWNER, "BACKTEST_RUN:BT-2"))
        assert result["ok"] is False
        assert result["error_code"] == get_error_code("E-VAL-020").code
        assert result["stop_button"] is True
        assert result["active_run_id"] == "BT-1"

    def test_a_backtest_run_acquires_and_releases_the_guard(self):
        calls: List[Dict[str, Any]] = []
        cp = plane(calls=calls)
        result = run(cp.handle_callback(OWNER, "BACKTEST_RUN:BT-9"))
        assert result["ok"] is True
        assert calls[0]["action"] == "BACKTEST_RUN"
        assert calls[0]["run_id"] == "BT-9"
        assert cp.busy.state == "IDLE"           # released after the run

    def test_a_missing_handler_is_refused_never_pretended(self):
        cp = plane(handlers={})
        cp._handlers = {}
        result = run(cp.handle_callback(OWNER, "BACKTEST_RUN:BT-3"))
        assert result["ok"] is False
        assert result["reason"] == "ACTION_HANDLER_UNAVAILABLE"
        assert result["error_code"] == get_error_code("E-VAL-020").code
        assert cp.busy.state == "IDLE"           # the guard is still released

    def test_a_failing_handler_is_reported_not_swallowed(self):
        cp = plane(handlers={"BACKTEST_RUN": recorder([], "BACKTEST_RUN",
                                                      fail=True)})
        result = run(cp.handle_callback(OWNER, "BACKTEST_RUN:BT-4"))
        assert result["ok"] is False
        assert result["reason"] == "RuntimeError"
        assert "exploded" in result["detail"]

    def test_an_export_callback_validates_before_dispatching(self):
        calls: List[Dict[str, Any]] = []
        cp = plane(calls=calls)
        good = run(cp.handle_callback(
            OWNER, "EXPORT", export={"items": ["Positions"], "time_range": "24h",
                                     "environment": "PAPER", "format": "CSV",
                                     "path": "/Download/APEX_Reports/p.csv"}))
        assert good["ok"] is True
        assert calls[-1]["action"] == "EXPORT"
        bad = run(cp.handle_callback(
            OWNER, "EXPORT", export={"items": ["Positions"], "time_range": "24h",
                                     "environment": "PAPER", "format": "PDF",
                                     "path": "/Download/APEX_Reports/p.pdf"}))
        assert bad["ok"] is False
        assert any(e.startswith("FORMAT_UNSUPPORTED") for e in bad["errors"])
        assert calls[-1]["action"] == "EXPORT"      # the bad one never ran

    def test_a_replayed_callback_is_not_re_executed(self):
        calls: List[Dict[str, Any]] = []
        cp = plane(calls=calls)
        first = run(cp.handle_callback(OWNER, "BACKTEST_RUN:BT-5", update_id=77))
        second = run(cp.handle_callback(OWNER, "BACKTEST_RUN:BT-5", update_id=77))
        assert first["ok"] is True
        assert second["replayed"] is True
        assert len([c for c in calls if c["action"] == "BACKTEST_RUN"]) == 1


# ---------------------------------------------------------------------------
# Emergency flow end to end
# ---------------------------------------------------------------------------

class TestEmergencyFlow:
    def test_an_unconfirmed_level_issues_a_nonce_and_does_not_act(self):
        calls: List[Dict[str, Any]] = []
        cp = plane(calls=calls)
        result = run(cp.handle_callback(OWNER, "EMERGENCY:L1"))
        assert result["awaiting_confirmation"] is True
        assert result["nonce"].startswith("o-")
        assert result["nonce_ttl_seconds"] == 90.0
        assert result["irreversible"] is True
        assert result["semantics"] == "PAUSE"
        assert calls == []
        assert cp.paused is False

    def test_yes_confirmation_executes_the_effect_once(self):
        calls: List[Dict[str, Any]] = []
        cp = plane(calls=calls)
        pending = run(cp.handle_callback(OWNER, "EMERGENCY:L1"))
        nonce = pending["nonce"]
        confirmed = run(cp.handle_callback(
            OWNER, f"CONFIRM:{nonce}:YES:EMERGENCY_L1"))
        assert confirmed["ok"] is True
        assert confirmed["authorized"] is True
        assert cp.paused is True
        assert [c["action"] for c in calls] == ["EMERGENCY_PAUSE"]
        replay = run(cp.handle_callback(
            OWNER, f"CONFIRM:{nonce}:YES:EMERGENCY_L1"))
        assert replay["ok"] is False
        assert replay["reason"] == "NONCE_ALREADY_CONSUMED"
        assert len([c for c in calls if c["action"] == "EMERGENCY_PAUSE"]) == 1

    def test_no_confirmation_leaves_the_system_untouched(self):
        calls: List[Dict[str, Any]] = []
        cp = plane(calls=calls)
        nonce = run(cp.handle_callback(OWNER, "EMERGENCY:L2"))["nonce"]
        result = run(cp.handle_callback(OWNER, f"CONFIRM:{nonce}:NO:EMERGENCY_L2"))
        assert result["ok"] is False
        assert result["authorized"] is False
        assert cp.new_positions_disabled is False
        assert calls == []

    def test_an_expired_nonce_never_authorizes(self):
        clock = FakeClock()
        cp = plane(clock=clock)
        nonce = run(cp.handle_callback(OWNER, "EMERGENCY:L4"))["nonce"]
        clock.advance(91)
        result = run(cp.handle_callback(OWNER, f"CONFIRM:{nonce}:YES:EMERGENCY_L4"))
        assert result["ok"] is False
        assert result["reason"] == "NONCE_EXPIRED"

    def test_a_malformed_confirmation_is_refused(self):
        result = run(plane().handle_callback(OWNER, "CONFIRM:o-abc:YES"))
        assert result["ok"] is False
        assert result["reason"] == "CONFIRMATION_MALFORMED"
        assert result["key_format"] == "o-<hex>"

    def test_a_user_cannot_raise_any_emergency_level(self):
        for level in P.EMERGENCY_LEVELS:
            result = run(plane().handle_callback(USER, f"EMERGENCY:{level}"))
            assert result["ok"] is False
            assert result["reason"] == "OWNER_ONLY"
            assert result["screen"] == "ACCESS_DENIED"
            assert result["audit_id"].startswith("o-")

    def test_l3_cancels_in_batches_of_at_most_twelve(self):
        calls: List[Dict[str, Any]] = []
        cp = plane(calls=calls)
        nonce = run(cp.handle_callback(OWNER, "EMERGENCY:L3"))["nonce"]
        result = run(cp.handle_callback(
            OWNER, f"CONFIRM:{nonce}:YES:EMERGENCY_L3",
            open_orders=[f"o{n}" for n in range(25)]))
        assert result["ok"] is True
        assert result["batches"] == 3
        assert result["orders"] == 25
        assert [len(c["orders"]) for c in calls] == [12, 12, 1]
        assert all(c["max_orders_per_batch"] == 12 for c in calls)

    def test_l5_sets_every_safe_mode_flag_and_preserves_evidence(self):
        calls: List[Dict[str, Any]] = []
        cp = plane(calls=calls)
        nonce = run(cp.handle_callback(OWNER, "EMERGENCY:L5"))["nonce"]
        result = run(cp.handle_callback(OWNER, f"CONFIRM:{nonce}:YES:EMERGENCY_L5"))
        assert result["ok"] is True
        assert result["safe_mode"] is True
        assert result["read_only"] is True
        assert result["halts_trading"] is True
        assert result["closes_all_positions"] is True
        assert result["preserves_evidence"] is True
        assert result["sends_notifications"] is True
        assert (cp.safe_mode, cp.read_only, cp.paused,
                cp.new_positions_disabled) == (True, True, True, True)

    def test_l4_and_l5_raise_a_p0_alert_to_the_owner(self):
        signaling = FakeSignaling()
        cp = plane(signaling=signaling)
        for level, alert in (("L4", "EXEC_RECOVERY"), ("L5", "EXEC_RECOVERY")):
            nonce = run(cp.handle_callback(OWNER, f"EMERGENCY:{level}"))["nonce"]
            run(cp.handle_callback(OWNER,
                                   f"CONFIRM:{nonce}:YES:EMERGENCY_{level}"))
        assert [a["alert"] for a in signaling.alerts] == [alert, alert]
        assert signaling.alerts[0]["threshold"] == P.EMERGENCY_SEMANTICS["L4"]

    def test_l1_to_l3_raise_a_circuit_open_alert(self):
        signaling = FakeSignaling()
        cp = plane(signaling=signaling)
        nonce = run(cp.handle_callback(OWNER, "EMERGENCY:L1"))["nonce"]
        run(cp.handle_callback(OWNER, f"CONFIRM:{nonce}:YES:EMERGENCY_L1"))
        assert signaling.alerts[-1]["alert"] == "CIRCUIT_OPEN"

    def test_recovery_from_an_emergency_state_is_owner_only(self):
        cp = plane()
        run(cp.handle_callback(OWNER, "EMERGENCY:L5"))
        denied = run(cp.handle_callback(USER, "RECOVER"))
        assert denied["ok"] is False
        assert denied["reason"] == "OWNER_ONLY"
        recovered = run(cp.handle_callback(OWNER, "RECOVER"))
        assert recovered["ok"] is True
        assert recovered["recovered"] is True
        assert recovered["previous"] == "L5"

    def test_a_ratchet_down_through_the_callback_is_refused(self):
        cp = plane()
        run(cp.handle_callback(OWNER, "EMERGENCY:L4"))
        result = run(cp.handle_callback(OWNER, "EMERGENCY:L2"))
        assert result["ok"] is False
        assert result["reason"] == "RATCHET_DOWN_FORBIDDEN"
        assert result["error_code"] == get_error_code("RSK-ERR-506").code
        assert cp.ratchet.level == "L4"

    def test_an_unknown_emergency_level_is_refused(self):
        with pytest.raises(P.ControlPlaneError) as exc:
            run(plane().handle_callback(OWNER, "EMERGENCY:L9"))
        assert exc.value.reason == "EMERGENCY_LEVEL_UNKNOWN"


# ---------------------------------------------------------------------------
# Guardrails on the control plane itself
# ---------------------------------------------------------------------------

class TestControlPlaneGuardrails:
    def test_no_secret_material_is_hardcoded(self):
        source = Path(P.__file__).read_text()
        for token in ("bot_token", "api_secret", "apiKey", "password"):
            assert token not in source

    def test_the_control_plane_has_no_direct_venue_or_ledger_write_path(self):
        """Every effect goes through the injected handler seam; the plane never
        touches the adapter or appends to the ledger itself."""
        source = Path(P.__file__).read_text()
        assert "ToobitAdapter" not in source
        assert "ledger.append" not in source
        assert not hasattr(P.ControlPlane, "submit_order")
        assert not hasattr(P.ControlPlane, "cancel_order")

    def test_an_unregistered_environment_falls_back_to_paper(self):
        assert plane(environment="SHADOW").environment == "PAPER"

    def test_the_environment_and_balance_are_displayed_from_the_settings(self):
        cp = plane(environment="LIVE", balance="987654.321")
        assert "LIVE" in cp.screen_main_menu()["title"]
        assert "987,654.321 USDT" not in cp.screen_main_menu()["title"]
        cp = plane(environment="PAPER", balance="987654.321")
        assert "987,654.321 USDT" in cp.screen_main_menu()["title"]

    def test_every_dispatch_is_audited(self):
        cp = plane()
        run(cp.handle_callback(OWNER, "BACKTEST_RUN:BT-1"))
        assert cp.audit[-1]["action"] == "BACKTEST_RUN"
        assert cp.audit[-1]["ok"] is True

    def test_the_handler_seam_accepts_a_late_registration(self):
        cp = plane()
        calls: List[Dict[str, Any]] = []
        cp.register("TRADING_WIZARD_RUN", recorder(calls, "TRADING_WIZARD_RUN"))
        result = run(cp.dispatch("TRADING_WIZARD_RUN", {"symbol": "BTCUSDT"}))
        assert result["ok"] is True
        assert calls[0]["symbol"] == "BTCUSDT"
