"""CP-7 ledger tests — T-LR-001 (append-only, 1000 writes, monotonic, unique),
T-LR-002 (reconcile-first: no advance without RECONCILED), T-LR-003 (10
broker-ledger deltas detected and logged as CORRECTION_EVENT), T_LEDGER (a
covert insert/modify breaks the hash chain), T_MATCH (position recomputed from
the ledger == exchange-reported), the AI.7 single-writer law (enforced at
runtime AND by a repository-wide grep), and the TEXT-Decimal money boundary.

Ch.16 L16745–16790, L16912–16936; AI.7 L18715–18719; AI.9 L18820–18840.

Every scenario runs inside ONE event loop with ONE writer: the writer task and
its queue are loop-bound, exactly as they are in the runtime composition root
(Ch.23 L18253–18260: one event loop, one ledger writer queue).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from apex.data_catalog.contracts import CORE10_SYMBOLS
from apex.data_catalog.store import sqlite_store as ss
from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import sha256_hex
from apex.ledger import store as LS
from apex.risk.kernel import LADDER_STATE_MIGRATION

REPO_ROOT = Path(__file__).resolve().parents[2]


class TickingClock:
    """A monotonic ISO-8601 UTC clock (millisecond precision) for tests."""

    def __init__(self, start_ms: int = 1767225600000) -> None:
        self.ms = start_ms

    def __call__(self) -> str:
        self.ms += 1
        moment = dt.datetime.fromtimestamp(self.ms / 1000.0, dt.timezone.utc)
        return moment.strftime("%Y-%m-%dT%H:%M:%S.") + \
            f"{moment.microsecond // 1000:03d}Z"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def store(tmp_path):
    sqlite = ss.SQLiteStore(str(tmp_path / "apex.sqlite3"))
    run(sqlite.open())
    yield sqlite
    run(sqlite.close())


def ledger_scenario(body, store, *, clock=None):
    """Open ONE writer, run ``body(ledger)``, then drain and release the slot."""

    async def _run():
        ledger = LS.LedgerWriter(store, clock=clock or TickingClock())
        await ledger.initialize()
        await ledger.start()
        try:
            return await body(ledger)
        finally:
            if not ledger.closed:
                await ledger.stop()

    return asyncio.run(_run())


PLAN = {
    "proposal_id": "pr-0001", "setup_id": "su-0001", "symbol": "BTCUSDT",
    "timeframe": "1h", "direction": "LONG", "entry_ref": "E-01/BOS",
    "stop_price": "99.0", "target_price": "103.0", "sized_quantity": "0.10",
    "risk_amount": "10.0", "contract_multiplier": "1", "decision": "ALLOW",
    "vetoes_applied": [], "risk_state": "LowRisk", "package_version": "4.0.0",
    "snapshot_id": "sn-0001", "as_of": "2026-01-01T00:00:00.000Z",
    "created_utc": "2026-01-01T00:00:00.000Z", "lineage": "SL-5→SL-6",
    "environment": "PAPER",
}


async def seed_fills(ledger, symbols, quantity="2", price="100",
                     side="BUY_OPEN"):
    for index, symbol in enumerate(symbols):
        await ledger.append_fill(intent_id=f"i-{index}", fill_id=f"f-{index}",
                                 price=price, quantity=quantity, symbol=symbol,
                                 side=side)
    return await ledger.positions_from_ledger()


# ---------------------------------------------------------------------------
# Migrations (CP-7 adds M101/M102 on top of CP-1's frozen DDL)
# ---------------------------------------------------------------------------

class TestMigrations:
    def test_cp7_migrations_are_applied_and_recorded(self, store):
        async def body(ledger):
            cur = await store.db.execute(
                "SELECT migration_name FROM schema_migrations ORDER BY "
                "migration_name")
            return [r[0] for r in await cur.fetchall()], \
                ledger.applied_migrations()

        applied, declared = ledger_scenario(body, store)
        assert LS.TRADE_PLAN_MIGRATION in applied
        assert LS.LEDGER_AUDIT_MIGRATION in applied
        assert LADDER_STATE_MIGRATION in applied
        assert declared == (LS.TRADE_PLAN_MIGRATION, LS.LEDGER_AUDIT_MIGRATION,
                            LADDER_STATE_MIGRATION)

    def test_migration_is_idempotent(self, store):
        async def body(ledger):
            await ledger.initialize()
            await ledger.initialize()
            cur = await store.db.execute("SELECT COUNT(*) FROM schema_migrations")
            return (await cur.fetchone())[0]

        assert ledger_scenario(body, store) >= 3

    def test_trade_plan_columns_match_the_frozen_ch16_ddl(self, store):
        async def body(ledger):
            cur = await store.db.execute("PRAGMA table_info(trade_plan)")
            return [r[1] for r in await cur.fetchall()]

        assert ledger_scenario(body, store) == list(LS.TRADE_PLAN_COLUMNS)

    def test_trade_plan_ddl_is_the_verbatim_chapter_16_block(self):
        """The DDL is copied verbatim (Ch.16 L16814–16840), never paraphrased."""
        ddl = LS.TRADE_PLAN_DDL
        assert "CREATE TABLE IF NOT EXISTS trade_plan" in ddl
        assert "proposal_id TEXT PRIMARY KEY" in ddl
        assert "sized_quantity REAL NOT NULL" in ddl
        assert "CHECK(direction IN ('LONG','SHORT','FLAT'))" in ddl
        assert "CHECK(decision IN ('ALLOW','REDUCE','REJECT'))" in ddl
        assert "CHECK(environment IN ('PAPER','LIVE','RESEARCH','BACKTEST'))" \
            in ddl

    def test_ledger_audit_is_append_only_at_the_schema_level(self, store):
        async def body(ledger):
            cur = await store.db.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND "
                "tbl_name='ledger_audit'")
            return {r[0]: r[1] for r in await cur.fetchall()}

        found = ledger_scenario(body, store)
        assert set(found) == {"ledger_audit_no_update", "ledger_audit_no_delete"}
        for sql in found.values():
            assert "AUDIT_APPEND_ONLY" in sql


# ---------------------------------------------------------------------------
# Single-writer law (AI.7 L18715–18719)
# ---------------------------------------------------------------------------

class TestSingleWriter:
    def test_a_second_writer_on_the_same_database_is_refused(self, store):
        async def body(ledger):
            try:
                LS.LedgerWriter(store)
                return "ALLOWED"
            except LS.LedgerSingleWriterError as exc:
                return exc.reason

        assert ledger_scenario(body, store) == "LEDGER_SINGLE_WRITER_VIOLATION"

    def test_active_writer_registry_reports_the_one_writer(self, store):
        async def body(ledger):
            return LS.active_writer(str(store.path)) is ledger

        assert ledger_scenario(body, store) is True

    def test_the_slot_is_released_after_stop(self, store):
        async def body(ledger):
            await ledger.stop()
            replacement = LS.LedgerWriter(store, clock=TickingClock())
            await replacement.initialize()
            await replacement.start()
            try:
                return (LS.active_writer(str(store.path)) is replacement,
                        replacement is not ledger)
            finally:
                await replacement.stop()

        assert ledger_scenario(body, store) == (True, True)

    def test_two_databases_may_each_have_one_writer(self, tmp_path):
        async def scenario():
            stores, writers = [], []
            try:
                for name in ("a.sqlite3", "b.sqlite3"):
                    sqlite = ss.SQLiteStore(str(tmp_path / name))
                    await sqlite.open()
                    stores.append(sqlite)
                    ledger = LS.LedgerWriter(sqlite, clock=TickingClock())
                    await ledger.initialize()
                    await ledger.start()
                    writers.append(ledger)
                await writers[0].append(event_type="PING", result="OK")
                await writers[1].append(event_type="PING", result="OK")
                return (len(await writers[0].read_ledger()),
                        len(await writers[1].read_ledger()),
                        writers[0] is not writers[1])
            finally:
                for ledger in writers:
                    await ledger.stop()
                for sqlite in stores:
                    await sqlite.close()

        assert run(scenario()) == (1, 1, True)

    def test_only_the_ledger_module_writes_ledger_rows(self):
        """Grep-enforced single writer: no other module in the tree may contain
        a ledger write statement (AI.7 L18715)."""
        pattern = re.compile(
            r"(INSERT\s+INTO\s+ledger\b|INSERT\s+INTO\s+ledger_audit\b|"
            r"UPDATE\s+ledger\b|DELETE\s+FROM\s+ledger\b)", re.IGNORECASE)
        offenders = []
        for path in sorted((REPO_ROOT / "apex").rglob("*.py")):
            hits = []
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith(("#", '"""', "*", "``")):
                    continue          # prose in a docstring is not a write
                if pattern.search(line):
                    hits.append(lineno)
            if hits and not (path.parent.name == "ledger"
                             and path.name == "store.py"):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{hits}")
        assert offenders == []

    def test_no_test_or_script_writes_ledger_rows_directly(self):
        """Tests and scripts must go through the writer, never around it."""
        pattern = re.compile(r"(INSERT\s+INTO\s+ledger\b|UPDATE\s+ledger\b|"
                             r"DELETE\s+FROM\s+ledger\b)", re.IGNORECASE)
        allowed = {"tests/unit/test_ledger_store.py"}    # T_LEDGER tamper probe
        offenders = []
        for root in ("scripts", "tests"):
            for path in sorted((REPO_ROOT / root).rglob("*.py")):
                relative = str(path.relative_to(REPO_ROOT))
                if relative in allowed:
                    continue
                if pattern.search(path.read_text()):
                    offenders.append(relative)
        assert offenders == []


# ---------------------------------------------------------------------------
# T-LR-001 — 1000 writes, append-only, monotonic, unique
# ---------------------------------------------------------------------------

class TestTLR001:
    def test_one_thousand_concurrent_writes_are_appended_in_order(self, store):
        async def body(ledger):
            await asyncio.gather(*[
                ledger.append(event_type="TEST_WRITE", intent_id=f"i-{n}",
                              result="OK", sequence=n) for n in range(1000)])
            rows = await ledger.read_ledger()
            chain = await ledger.verify_chain()
            return rows, chain, ledger.written, ledger.queue_size

        rows, chain, written, queued = ledger_scenario(body, store)
        assert len(rows) == 1000
        assert written == 1000
        assert queued == 0                       # the queue is fully drained
        assert len({r.ledger_id for r in rows}) == 1000
        assert len({r.event_id for r in rows}) == 1000
        assert chain["records"] == 1000
        assert chain["intact"] is True
        assert chain["event_ids_unique"] is True
        assert chain["sequence_monotonic"] is True

    def test_no_overwrite_update_or_delete_is_possible(self, store):
        async def body(ledger):
            entry = await ledger.append(event_type="IMMUTABLE", result="OK")
            outcomes = {}
            for sql, args, label in (
                    ("UPDATE ledger SET price=? WHERE ledger_id=?",
                     ("1", entry.ledger_id), "update"),
                    ("DELETE FROM ledger WHERE ledger_id=?",
                     (entry.ledger_id,), "delete")):
                try:
                    await store.db.execute(sql, args)
                    await store.db.commit()
                    outcomes[label] = "ALLOWED"
                except Exception as exc:                    # the trigger fires
                    outcomes[label] = type(exc).__name__
            return outcomes, len(await ledger.read_ledger())

        outcomes, count = ledger_scenario(body, store)
        assert outcomes["update"] != "ALLOWED"
        assert outcomes["delete"] != "ALLOWED"
        assert count == 1                      # the record is still there

    def test_append_only_triggers_exist_on_the_ledger_table(self, store):
        async def body(ledger):
            cur = await store.db.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND "
                "tbl_name='ledger'")
            return {r[0] for r in await cur.fetchall()}

        assert ledger_scenario(body, store) == {"ledger_no_update",
                                                "ledger_no_delete"}

    def test_a_stopped_writer_refuses_writes(self, store):
        async def body(ledger):
            await ledger.stop()
            try:
                await ledger.append(event_type="AFTER_STOP")
                return "ALLOWED"
            except LS.LedgerError as exc:
                return exc.reason

        assert ledger_scenario(body, store) == "LEDGER_WRITER_CLOSED"

    def test_an_append_without_an_event_type_is_refused(self, store):
        async def body(ledger):
            try:
                await ledger.append(event_type="")
                return "ALLOWED"
            except LS.LedgerError as exc:
                return exc.reason

        assert ledger_scenario(body, store) == "EVENT_TYPE_REQUIRED"


# ---------------------------------------------------------------------------
# T_LEDGER — tampering breaks the hash chain
# ---------------------------------------------------------------------------

class TestTLedger:
    def test_a_clean_chain_verifies(self, store):
        async def body(ledger):
            for n in range(5):
                await ledger.append(event_type="CHAIN", result="OK", n=n)
            return await ledger.verify_chain(), ledger.head

        chain, head = ledger_scenario(body, store)
        assert chain["intact"] is True
        assert chain["breaks"] == []
        assert chain["head"] == head
        assert chain["records"] == 5

    def test_a_covert_insert_breaks_the_parent_linkage(self, store):
        async def body(ledger):
            await ledger.append(event_type="CHAIN", result="OK")
            # a covert row bypassing the single writer: no parent link, no hash
            await store.db.execute(
                "INSERT INTO ledger (" + ",".join(LS.LEDGER_COLUMNS) +
                ") VALUES (" + ",".join("?" * len(LS.LEDGER_COLUMNS)) + ")",
                # the frozen DDL CHECKs typeof(fee/price/quantity)='text', so
                # even a covert row must carry TEXT (empty) money columns
                ("lg-covert", None, None, None, None, "deadbeef", "[]", None,
                 "{}", "", "", "", "", "2026-01-01T00:00:00.000Z"))
            await store.db.commit()
            return await ledger.verify_chain()

        chain = ledger_scenario(body, store)
        assert chain["intact"] is False
        kinds = {b["kind"] for b in chain["breaks"]}
        assert "PARENT_LINK_BROKEN" in kinds
        assert "PAYLOAD_HASH_MISMATCH" in kinds      # "deadbeef" ≠ sha256("{}")

    def test_a_covert_modify_is_blocked_and_would_break_the_hash(self, store):
        async def body(ledger):
            entry = await ledger.append(event_type="CHAIN", result="OK",
                                        price="100")
            blocked = None
            try:
                await store.db.execute(
                    "UPDATE ledger SET price=? WHERE ledger_id=?",
                    ("999", entry.ledger_id))
                await store.db.commit()
            except Exception as exc:
                blocked = type(exc).__name__
            tampered = dict(entry.raw)
            tampered["price"] = "999"
            return blocked, sha256_hex(canonical_json(tampered)) != \
                entry.payload_hash

        blocked, hash_would_break = ledger_scenario(body, store)
        assert blocked is not None          # the CP-1 trigger aborts the UPDATE
        assert hash_would_break is True     # T_LEDGER: a modify breaks the chain

    def test_payload_hash_is_sha256_of_the_canonical_record(self, store):
        async def body(ledger):
            return await ledger.append(event_type="HASH", intent_id="i-h",
                                       result="OK", price=Decimal("100.5"))

        entry = ledger_scenario(body, store)
        assert entry.payload_hash == sha256_hex(canonical_json(dict(entry.raw)))
        assert len(entry.payload_hash) == 64

    def test_the_chain_head_survives_a_writer_restart(self, store):
        async def first_boot():
            ledger = LS.LedgerWriter(store, clock=TickingClock())
            await ledger.initialize()
            await ledger.start()
            try:
                entry = await ledger.append(event_type="CHAIN", result="OK")
                return ledger.head, entry.payload_hash
            finally:
                await ledger.stop()

        head, entry_hash = run(first_boot())

        async def second_boot():
            ledger = LS.LedgerWriter(store, clock=TickingClock())
            recovered = await ledger.initialize()
            await ledger.start()
            try:
                follow = await ledger.append(event_type="CHAIN", result="OK")
                return recovered["chain_head"], follow.parent_ids, \
                    (await ledger.verify_chain())["intact"]
            finally:
                await ledger.stop()

        recovered, parents, intact = run(second_boot())
        assert head == entry_hash
        assert recovered == entry_hash
        assert parents == (entry_hash,)       # the chain continues, never forks
        assert intact is True


# ---------------------------------------------------------------------------
# T-LR-002 — reconcile-first
# ---------------------------------------------------------------------------

class TestTLR002:
    def test_advance_without_reconciled_is_rejected(self, store):
        async def body(ledger):
            await ledger.append(event_type="FILL", intent_id="i-1",
                                fill_id="f-1", price="100", quantity="0.1",
                                result="FILLED", symbol="BTCUSDT",
                                side="BUY_OPEN")
            try:
                await ledger.require_reconciled("i-1")
                return "ALLOWED"
            except LS.LedgerNotReconciled as exc:
                return exc.reason

        assert ledger_scenario(body, store) == "T-LR-002_NOT_RECONCILED"

    def test_advance_after_reconciled_is_allowed(self, store):
        async def body(ledger):
            await ledger.append_fsm_transition(intent_id="i-2",
                                               from_state="FILLED",
                                               to_state="RECONCILED",
                                               reason="T_MATCH",
                                               trigger="RECONCILE_MATCH",
                                               result="RECONCILED")
            return await ledger.require_reconciled("i-2")

        verdict = ledger_scenario(body, store)
        assert verdict["reconciled"] is True
        assert "RECONCILED" in verdict["states"]

    def test_a_blocked_ledger_rejects_every_advance(self, store):
        async def body(ledger):
            await ledger.append(event_type="FILL", intent_id="i-3",
                                fill_id="f-3", price="100", quantity="5",
                                result="RECONCILED", symbol="BTCUSDT",
                                side="BUY_OPEN")
            await ledger.reconcile_against_exchange(
                [{"symbol": "BTCUSDT", "quantity": "50"}])
            try:
                await ledger.require_reconciled("i-3")
                return "ALLOWED"
            except LS.LedgerNotReconciled as exc:
                return exc.reason

        assert ledger_scenario(body, store) == "T-LR-002_LEDGER_BLOCKED"


# ---------------------------------------------------------------------------
# T-LR-003 + T_MATCH + T_RECONCILE
# ---------------------------------------------------------------------------

class TestTLR003:
    def test_ten_broker_ledger_deltas_are_all_detected_and_logged(self, store):
        symbols = list(CORE10_SYMBOLS)
        assert len(symbols) == 10

        async def body(ledger):
            await seed_fills(ledger, symbols, quantity="2")
            verdict = await ledger.reconcile_against_exchange(
                [{"symbol": s, "quantity": "9"} for s in symbols])
            return verdict, await ledger.read_ledger()

        verdict, rows = ledger_scenario(body, store)
        assert verdict["agree"] is False
        assert verdict["delta_count"] == 10
        assert verdict["action"] == "RECOVERY_REQUIRED"
        assert verdict["new_entries_blocked"] is True
        assert all(d["alert"] == "RECONCILE_FAILURE" for d in verdict["deltas"])
        corrections = [r for r in rows if r.event_type == "CORRECTION_EVENT"]
        assert len(corrections) == 10
        assert all(r.raw["payload"]["reason"] == "BROKER_LEDGER_DELTA"
                   for r in corrections)
        assert {r.raw["payload"]["symbol"] for r in corrections} == set(symbols)

    def test_new_entries_are_blocked_while_divergent(self, store):
        symbols = list(CORE10_SYMBOLS)[:3]

        async def body(ledger):
            await seed_fills(ledger, symbols)
            await ledger.reconcile_against_exchange(
                [{"symbol": s, "quantity": "99"} for s in symbols])
            blocked_flag = ledger.blocked
            try:
                await ledger.append(event_type="FILL", intent_id="i-new",
                                    result="FILLED")
                blocked = "ALLOWED"
            except LS.LedgerError as exc:
                blocked = exc.reason
            correction = await ledger.append_correction(
                supersedes=ledger.head, reason="MANUAL_NOTE")
            return blocked_flag, blocked, correction.event_type, \
                ledger.blocked_reason

        blocked_flag, blocked, event_type, reason = ledger_scenario(body, store)
        assert blocked_flag is True
        assert blocked == "LEDGER_BLOCKED_PENDING_RECONCILE"
        assert event_type == "CORRECTION_EVENT"
        assert "delta" in str(reason)

    def test_a_matching_reconcile_clears_the_block(self, store):
        symbols = list(CORE10_SYMBOLS)[:2]

        async def body(ledger):
            await seed_fills(ledger, symbols, quantity="2")
            await ledger.reconcile_against_exchange(
                [{"symbol": s, "quantity": "99"} for s in symbols])
            assert ledger.blocked is True
            verdict = await ledger.reconcile_against_exchange(
                [{"symbol": s, "quantity": "2"} for s in symbols])
            after = await ledger.append(event_type="FILL", intent_id="i-ok",
                                        result="FILLED")
            rows = await ledger.read_ledger()
            return verdict, ledger.blocked, after.event_type, \
                [r.event_type for r in rows].count("RECONCILE_RESOLVED")

        verdict, blocked, event_type, resolved = ledger_scenario(body, store)
        assert verdict["agree"] is True
        assert blocked is False
        assert event_type == "FILL"
        assert resolved == 1                  # the resolution is itself audited

    def test_t_match_ledger_position_equals_exchange_position(self, store):
        async def body(ledger):
            await seed_fills(ledger, ["BTCUSDT", "ETHUSDT"], quantity="2")
            verdict = await ledger.reconcile_against_exchange(
                [{"symbol": "BTCUSDT", "quantity": "2"},
                 {"symbol": "ETHUSDT", "quantity": "2"}])
            return verdict, await ledger.positions_from_ledger()

        verdict, positions = ledger_scenario(body, store)
        assert verdict["agree"] is True
        assert verdict["delta_count"] == 0
        assert positions["BTCUSDT"]["net_quantity"] == "2"
        assert positions["BTCUSDT"]["direction"] == "LONG"

    def test_a_delta_inside_the_one_unit_tolerance_is_not_a_divergence(self,
                                                                      store):
        assert LS.RECONCILE_DELTA_TOLERANCE_UNITS == 1.0

        async def body(ledger):
            await seed_fills(ledger, ["BTCUSDT"], quantity="2")
            inside = await ledger.reconcile_against_exchange(
                [{"symbol": "BTCUSDT", "quantity": "2.5"}])
            outside = await ledger.reconcile_against_exchange(
                [{"symbol": "BTCUSDT", "quantity": "4"}])
            return inside, outside

        inside, outside = ledger_scenario(body, store)
        assert inside["agree"] is True
        assert outside["agree"] is False
        assert outside["deltas"][0]["delta"] == "2"

    def test_a_ledger_position_missing_from_the_exchange_is_a_divergence(self,
                                                                        store):
        async def body(ledger):
            await seed_fills(ledger, ["SOLUSDT"], quantity="3")
            return await ledger.reconcile_against_exchange([])

        verdict = ledger_scenario(body, store)
        assert verdict["agree"] is False
        assert verdict["deltas"][0]["symbol"] == "SOLUSDT"
        assert verdict["deltas"][0]["exchange_quantity"] == "0"

    def test_a_flat_ledger_never_reports_a_phantom_position(self, store):
        async def body(ledger):
            await ledger.append_fill(intent_id="i-open", fill_id="f-open",
                                     price="100", quantity="1",
                                     symbol="BTCUSDT", side="BUY_OPEN")
            await ledger.append_fill(intent_id="i-close", fill_id="f-close",
                                     price="101", quantity="1",
                                     symbol="BTCUSDT", side="SELL_CLOSE")
            positions = await ledger.positions_from_ledger()
            return positions, await ledger.reconcile_against_exchange([])

        positions, verdict = ledger_scenario(body, store)
        assert positions["BTCUSDT"]["net_quantity"] == "0"
        assert positions["BTCUSDT"]["direction"] == "FLAT"
        assert verdict["agree"] is True


class TestPositionsFromLedger:
    def test_sides_sign_the_net_quantity(self, store):
        async def body(ledger):
            await ledger.append_fill(intent_id="i-1", fill_id="f-1",
                                     price="100", quantity="3",
                                     symbol="BTCUSDT", side="BUY_OPEN")
            await ledger.append_fill(intent_id="i-1", fill_id="f-2",
                                     price="110", quantity="1",
                                     symbol="BTCUSDT", side="SELL_CLOSE")
            await ledger.append_fill(intent_id="i-2", fill_id="f-3",
                                     price="50", quantity="4",
                                     symbol="ETHUSDT", side="SELL_OPEN")
            await ledger.append_fill(intent_id="i-2", fill_id="f-4",
                                     price="45", quantity="1",
                                     symbol="ETHUSDT", side="BUY_CLOSE")
            return await ledger.positions_from_ledger()

        positions = ledger_scenario(body, store)
        assert positions["BTCUSDT"]["net_quantity"] == "2"
        assert positions["BTCUSDT"]["direction"] == "LONG"
        assert positions["BTCUSDT"]["average_entry_price"] == "100.000000000000"
        assert positions["BTCUSDT"]["open_quantity"] == "3"
        assert positions["ETHUSDT"]["average_entry_price"] == "50.000000000000"
        assert positions["ETHUSDT"]["net_quantity"] == "-3"
        assert positions["ETHUSDT"]["direction"] == "SHORT"
        assert positions["ETHUSDT"]["fills"] == 2

    def test_an_unknown_side_is_never_guessed(self, store):
        async def body(ledger):
            await ledger.append_fill(intent_id="i-1", fill_id="f-1",
                                     price="100", quantity="1",
                                     symbol="BTCUSDT", side="BUY_OPEN")
            await ledger.append_fill(intent_id="i-2", fill_id="f-2",
                                     price="100", quantity="1",
                                     symbol="BTCUSDT", side="SIDEWAYS")
            try:
                await ledger.positions_from_ledger()
                return "ALLOWED"
            except LS.LedgerError as exc:
                return exc.reason

        assert ledger_scenario(body, store) == "FILL_SIDE_QX"

    def test_fills_are_idempotent_under_fill_id(self, store):
        async def body(ledger):
            first = await ledger.append_fill(intent_id="i-1", fill_id="f-dup",
                                             price="100", quantity="1",
                                             symbol="BTCUSDT", side="BUY_OPEN")
            second = await ledger.append_fill(intent_id="i-1", fill_id="f-dup",
                                              price="100", quantity="1",
                                              symbol="BTCUSDT", side="BUY_OPEN")
            rows = await ledger.read_ledger()
            return first.ledger_id, second.ledger_id, len(rows), \
                (await ledger.find_by_fill("f-dup")).fill_id

        first_id, second_id, count, found = ledger_scenario(body, store)
        assert first_id == second_id
        assert count == 1
        assert found == "f-dup"

    def test_find_by_intent_returns_the_whole_trail(self, store):
        async def body(ledger):
            await ledger.append(event_type="SUBMIT", intent_id="i-trail",
                                result="ACKNOWLEDGED")
            await ledger.append(event_type="FILL", intent_id="i-trail",
                                fill_id="f-9", result="FILLED")
            await ledger.append_fsm_transition(intent_id="i-trail",
                                               from_state="FILLED",
                                               to_state="RECONCILED",
                                               reason="T_MATCH",
                                               trigger="RECONCILE_MATCH",
                                               result="RECONCILED")
            return await ledger.find_by_intent("i-trail")

        trail = ledger_scenario(body, store)
        assert [e.event_type for e in trail] == ["SUBMIT", "FILL",
                                                 "FSM_TRANSITION"]
        assert trail[-1].raw["payload"]["to_state"] == "RECONCILED"

    def test_find_by_intent_is_empty_for_an_unknown_intent(self, store):
        async def body(ledger):
            return await ledger.find_by_intent("nope")

        assert ledger_scenario(body, store) == []


# ---------------------------------------------------------------------------
# Money stays TEXT Decimal at the store boundary
# ---------------------------------------------------------------------------

def _walk(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk(item)
    else:
        yield value


class TestMoneyBoundary:
    def test_decimal_inputs_are_stored_as_text(self, store):
        async def body(ledger):
            entry = await ledger.append(event_type="FILL", intent_id="i-money",
                                        fill_id="f-money",
                                        price=Decimal("100.10"),
                                        quantity=Decimal("0.001"),
                                        fee=Decimal("0.02"),
                                        slippage=Decimal("-0.5"),
                                        symbol="BTCUSDT", side="BUY_OPEN")
            cur = await store.db.execute(
                "SELECT typeof(price), typeof(quantity), typeof(fee), "
                "typeof(slippage) FROM ledger WHERE ledger_id=?",
                (entry.ledger_id,))
            return entry, await cur.fetchone()

        entry, kinds = ledger_scenario(body, store)
        assert kinds == ("text", "text", "text", "text")
        assert entry.price == "100.10"
        assert entry.quantity == "0.001"
        assert isinstance(entry.price, str)

    def test_no_floats_inside_the_raw_record(self, store):
        async def body(ledger):
            return await ledger.append(event_type="FILL", intent_id="i-float",
                                       fill_id="f-float", price=Decimal("1.5"),
                                       quantity=Decimal("2.5"),
                                       pnl=Decimal("-3.25"), symbol="BTCUSDT",
                                       side="BUY_OPEN")

        entry = ledger_scenario(body, store)
        assert isinstance(entry.raw["pnl"], str)
        assert "-3.25" in json.dumps(dict(entry.raw))
        for value in _walk(entry.raw):
            assert not isinstance(value, float)

    def test_a_string_number_is_normalized_through_decimal(self, store):
        async def body(ledger):
            return await ledger.append(event_type="FILL", intent_id="i-str",
                                       fill_id="f-str", price="100.500",
                                       quantity="0.10", symbol="BTCUSDT",
                                       side="BUY_OPEN")

        entry = ledger_scenario(body, store)
        assert entry.price == "100.500"
        assert entry.quantity == "0.10"


# ---------------------------------------------------------------------------
# Trade plan / outcome / stop-gap / protection-failed
# ---------------------------------------------------------------------------

class TestTradePlan:
    def test_a_trade_plan_is_materialized_with_every_ch16_column(self, store):
        async def body(ledger):
            entry = await ledger.append_trade_plan(PLAN)
            return entry, await ledger.trade_plans()

        entry, rows = ledger_scenario(body, store)
        assert entry.event_type == "TRADE_PLAN"
        assert entry.raw["result"] == "TRADE_PLAN_MATERIALIZED"
        assert len(rows) == 1
        row = rows[0]
        assert set(row) == set(LS.TRADE_PLAN_COLUMNS)
        assert row["proposal_id"] == "pr-0001"
        assert row["setup_id"] == "su-0001"
        assert row["direction"] == "LONG"
        assert row["decision"] == "ALLOW"
        assert row["environment"] == "PAPER"
        assert row["sized_quantity"] == pytest.approx(0.10)
        assert len(row["payload_hash"]) == 64

    def test_environment_filter(self, store):
        async def body(ledger):
            await ledger.append_trade_plan(PLAN)
            await ledger.append_trade_plan({**PLAN, "proposal_id": "pr-0002",
                                            "environment": "BACKTEST"})
            return (await ledger.trade_plans(environment="PAPER"),
                    await ledger.trade_plans(environment="BACKTEST"))

        paper, backtest = ledger_scenario(body, store)
        assert [r["proposal_id"] for r in paper] == ["pr-0001"]
        assert [r["proposal_id"] for r in backtest] == ["pr-0002"]

    @pytest.mark.parametrize("mutation,reason", [
        ({"environment": "SHADOW"}, "ENVIRONMENT_QX"),
        ({"direction": "SIDEWAYS"}, "DIRECTION_QX"),
        ({"decision": "MAYBE"}, "DECISION_QX"),
        ({"sized_quantity": None}, "SIZED_QUANTITY_REQUIRED"),
        ({"proposal_id": ""}, "TRADE_PLAN_IDENTITY_REQUIRED"),
        ({"setup_id": None}, "TRADE_PLAN_IDENTITY_REQUIRED")])
    def test_invalid_plans_fail_closed(self, store, mutation, reason):
        async def body(ledger):
            try:
                await ledger.append_trade_plan({**PLAN, **mutation})
                return "ALLOWED"
            except LS.LedgerError as exc:
                return exc.reason

        assert ledger_scenario(body, store) == reason

    def test_no_shadow_environment_exists(self):
        assert LS.ENVIRONMENTS == ("PAPER", "LIVE", "RESEARCH", "BACKTEST")


class TestOutcome:
    def test_an_outcome_is_appended_with_the_frozen_columns(self, store):
        async def body(ledger):
            # outcome.setup_id is an FK to setup_candidate (Ch.5 L14540) and
            # PRAGMA foreign_keys=ON — the parent row must exist first.
            await store.db.execute(
                "INSERT INTO setup_candidate (setup_id, timestamp, symbol, "
                "timeframe, direction, quality, snapshot_id) VALUES "
                "('su-0001','2026-01-01T00:00:00.000Z','BTCUSDT','1h',"
                "'BULLISH','Q2','sn-0001')")
            await store.db.commit()
            entry = await ledger.append_outcome({
                "setup_id": "su-0001", "entry_price": "100", "exit_price": "103",
                "pnl": "3", "fees": "0.04", "mfe": "4", "mae": "-1",
                "duration": 3600, "exit_reason": "TARGET_1", "risk_used": "10",
                "regime": "TREND", "intended_stop": "99", "actual_fill": "99.6"})
            cur = await store.db.execute(
                "SELECT slippage, exit_reason FROM outcome WHERE setup_id=?",
                ("su-0001",))
            return entry, await cur.fetchone()

        entry, row = ledger_scenario(body, store)
        assert entry.event_type == "OUTCOME"
        assert row[0] == "0.6"        # actual_fill − intended_stop (stop gap)
        assert row[1] == "TARGET_1"

    def test_outcome_requires_the_setup_fk(self, store):
        async def body(ledger):
            try:
                await ledger.append_outcome({"entry_price": "100"})
                return "ALLOWED"
            except LS.LedgerError as exc:
                return exc.reason

        assert ledger_scenario(body, store) == "OUTCOME_SETUP_ID_REQUIRED"

    def test_an_outcome_with_a_missing_setup_parent_is_refused_by_the_fk(self,
                                                                        store):
        """PRAGMA foreign_keys=ON (Ch.5 L14554): a dangling setup_id is a hard
        failure, never a silently orphaned outcome."""
        async def body(ledger):
            try:
                await ledger.append_outcome({"setup_id": "su-does-not-exist",
                                             "pnl": "1"})
                return "ALLOWED"
            except Exception as exc:
                return type(exc).__name__

        assert ledger_scenario(body, store) == "IntegrityError"

    def test_outcome_columns_are_the_frozen_cp1_set(self):
        assert LS.OUTCOME_COLUMNS == (
            "outcome_id", "entry_price", "exit_price", "pnl", "fees",
            "slippage", "mfe", "mae", "duration", "exit_reason", "risk_used",
            "forecast", "setup_id", "regime", "context")


class TestStopGapAndProtection:
    @pytest.mark.parametrize("direction,intended,actual,gap,exceeded", [
        ("LONG", "100", "98.5", "1.5", True),
        ("LONG", "100", "100.5", "-0.5", False),
        ("SHORT", "100", "101.5", "1.5", True),
        ("SHORT", "100", "99.5", "-0.5", False)])
    def test_stop_gap_slippage_sign_law(self, direction, intended, actual, gap,
                                        exceeded):
        verdict = LS.stop_gap_slippage(intended_stop=intended,
                                       actual_fill=actual, direction=direction)
        assert verdict["stop_gap"] == gap
        assert verdict["exceeded"] is exceeded
        assert verdict["attribution"] == (
            "STOP_GAP_SLIPPAGE" if exceeded else None)
        assert verdict["next_risk_input"] == (
            "REALIZED_WORST_LOSS" if exceeded else "MODELED_R")

    def test_an_unknown_direction_is_refused(self):
        with pytest.raises(LS.LedgerError) as exc:
            LS.stop_gap_slippage(intended_stop="100", actual_fill="99",
                                 direction="FLAT")
        assert exc.value.reason == "DIRECTION_QX"

    def test_protection_failed_escalates_to_owner_at_p0(self):
        event = LS.protection_failed_event(intent_id="i-1",
                                           reason="STOP_ORDER_REJECTED")
        assert event["event_type"] == "PROTECTION_FAILED"
        assert event["action"] == "PLAYBOOK_EMERGENCY_CLOSE_AT_MARKET"
        assert event["escalation"] == "OWNER"
        assert event["alert"] == "EXEC_RECOVERY"
        assert event["priority"] == "P0"

    def test_protection_failure_is_written_to_the_ledger(self, store):
        async def body(ledger):
            event = LS.protection_failed_event(intent_id="i-prot",
                                               reason="STOP_ORDER_REJECTED")
            rule = event.pop("rule")
            return await ledger.append(**event, rule=rule,
                                       result="PROTECTION_FAILED")

        entry = ledger_scenario(body, store)
        assert entry.event_type == "PROTECTION_FAILED"
        assert entry.raw["result"] == "PROTECTION_FAILED"
        assert entry.raw["payload"]["alert"] == "EXEC_RECOVERY"
        assert entry.raw["payload"]["escalation"] == "OWNER"


class TestAuditTrail:
    def test_every_append_is_mirrored_into_ledger_audit(self, store):
        async def body(ledger):
            await ledger.append(event_type="SUBMIT", intent_id="i-audit",
                                result="ACKNOWLEDGED")
            await ledger.append(event_type="FILL", intent_id="i-audit",
                                fill_id="f-audit", result="FILLED")
            cur = await store.db.execute(
                "SELECT actor, action FROM ledger_audit ORDER BY rowid")
            return await cur.fetchall()

        rows = ledger_scenario(body, store)
        assert [r[1] for r in rows] == ["SUBMIT", "FILL"]
        assert all(r[0] == "LEDGER" for r in rows)

    def test_actor_can_be_named_per_append(self, store):
        async def body(ledger):
            await ledger.append(event_type="FSM_TRANSITION",
                                actor="EXECUTION_FSM", intent_id="i-actor",
                                result="ACKNOWLEDGED")
            cur = await store.db.execute(
                "SELECT actor FROM ledger_audit ORDER BY rowid DESC LIMIT 1")
            return (await cur.fetchone())[0]

        assert ledger_scenario(body, store) == "EXECUTION_FSM"


class TestWalAndReadPath:
    def test_the_database_is_in_wal_mode(self, store):
        async def mode():
            cur = await store.db.execute("PRAGMA journal_mode")
            return (await cur.fetchone())[0]

        assert run(mode()) == "wal"

    def test_reads_are_ordered_and_limited(self, store):
        async def body(ledger):
            for n in range(10):
                await ledger.append(event_type="READ", result="OK", n=n)
            return await ledger.read_ledger(limit=3)

        rows = ledger_scenario(body, store)
        assert len(rows) == 3
        assert [r.raw["payload"]["n"] for r in rows] == [0, 1, 2]

    def test_canonical_json_is_stable_for_the_same_payload(self):
        left = canonical_json({"b": 1, "a": [1, 2]})
        right = canonical_json({"a": [1, 2], "b": 1})
        assert left == right
        assert sha256_hex(left) == sha256_hex(right)
