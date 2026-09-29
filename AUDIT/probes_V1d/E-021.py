"""V1d probe E-021 — ExecutionFSM.reconcile divergence does not engage the
LedgerWriter's durable new-entries gate; terminal RECONCILED survives a
contrary recheck; require_reconciled passes on ANY historical RECONCILED
record. READ-ONLY verification with the REAL ExecutionFSM + real
LedgerWriter + repository FakeToobitResponder on temporary SQLite."""
import asyncio
import os
import sys
import tempfile

os.environ.setdefault("APEX_ENV", "PAPER")
os.environ.setdefault("APEX_ALLOW_SIGNED", "1")
os.environ.setdefault("TOOBIT_API_KEY", "TEST_KEY_CP7")
os.environ.setdefault("TOOBIT_API_SECRET", "TEST_SECRET_CP7")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tests"))

from apex.config import Config
from apex.data_catalog.store import sqlite_store as ss
from apex.execution import fsm as F
from apex.execution.toobit_adapter import ToobitAdapter
from apex.ledger import store as LS
from fake_toobit_responder import FakeToobitResponder

ISO = "2026-01-01T00:00:00.000Z"


class FakeProposal:
    def to_dict(self):
        return {"proposal_id": "pr-0001", "setup_id": "su-0001",
                "direction": "LONG", "stop": 99.0, "targets": [103.0],
                "entry_logic_ref": "E-01/BOS", "snapshot_id": "sn-0001"}


async def main() -> None:
    tmp = tempfile.mkdtemp(prefix="v1d_e021_")
    store = ss.SQLiteStore(os.path.join(tmp, "apex.sqlite3"))
    await store.open()
    ledger = LS.LedgerWriter(store, clock=lambda: ISO)
    await ledger.initialize()
    responder = FakeToobitResponder(api_key="TEST_KEY_CP7",
                                    api_secret="TEST_SECRET_CP7")
    adapter = ToobitAdapter(config=Config(), transport=responder,
                            utc_now=lambda: ISO, clock=lambda: 1000.0)
    try:
        await ledger.start()
        plan = F.build_trade_plan(
            proposal=FakeProposal(),
            adjudication={"decision": "ALLOW", "sized_quantity": "0.10",
                          "vetoes_applied": [], "sizing": {"R_allowed": 10.0},
                          "snapshot_id": "sn-0001"},
            symbol="BTCUSDT", timeframe="1h", environment="PAPER", as_of=ISO,
            capital=10000.0, contract_multiplier=1.0, risk_state="LowRisk",
            package_version="4.0.0", created_utc=ISO)
        machine = F.ExecutionFSM(intent_id="i-e021", ledger=ledger,
                                 adapter=adapter, environment="PAPER",
                                 utc_now=lambda: ISO, clock=lambda: 1000.0)
        await machine.submit(plan, price="100")
        await machine.record_fill(fill_id="f-1", price="100", quantity="0.10")
        await machine.advance("FULL_FILL")

        # --- (1a) divergence from a LIVE state (FILLED): mismatch = 9 -------
        responder.seed_position("BTCUSDT", "LONG", "9")
        bad_live = await machine.reconcile()
        print("(1a) divergence from FILLED -> agree=%s state=%s action=%s "
              "new_entries_blocked=%s" %
              (bad_live["agree"], machine.state, bad_live["action"],
               bad_live.get("new_entries_blocked")))
        print("     ledger.blocked after FSM divergence:", ledger.blocked)
        e = await ledger.append_fill(intent_id="i-other", fill_id="f-2",
                                     price="100", quantity="0.10",
                                     symbol="BTCUSDT", side="BUY_OPEN")
        print("     append_fill in the SAME writer while FSM says blocked ->",
              e.event_type, "| ledger.blocked still:", ledger.blocked)

        # --- (1b) resolve: match from RECOVERY_REQUIRED -> RECONCILED -------
        responder.seed_position("BTCUSDT", "LONG", "0.20")
        good = await machine.reconcile()
        print("(1b) match     -> agree=%s state=%s action=%s" %
              (good["agree"], machine.state, good["action"]))

        # --- (2) a CONTRARY recheck: venue now reports 9 -------------------
        responder.seed_position("BTCUSDT", "LONG", "9")
        bad = await machine.reconcile()
        corrections = [e for e in await ledger.read_ledger()
                       if e.event_type == "CORRECTION_EVENT"]
        print("(2) recheck divergence -> agree=%s state=%s action=%s "
              "new_entries_blocked=%s note=%s" %
              (bad["agree"], machine.state, bad["action"],
               bad.get("new_entries_blocked"), bad.get("note")))
        print("    corrections appended:", len(corrections))
        print("    ledger.blocked:", ledger.blocked, "| blocked_reason:",
              ledger.blocked_reason)
        # T-LR-002 gate for THIS intent still passes on the historical record
        req = await machine.require_reconciled()
        print("    require_reconciled after divergent recheck:", req)

        # --- (3) the direct LedgerWriter path DOES set the gate ------------
        via_writer = await ledger.reconcile_against_exchange(
            [{"symbol": "BTCUSDT", "quantity": "9"}])
        print("(4) reconcile_against_exchange -> agree=%s blocked=%s" %
              (via_writer["agree"], ledger.blocked))
        try:
            await ledger.append_fill(intent_id="i-other2", fill_id="f-3",
                                     price="100", quantity="0.10",
                                     symbol="BTCUSDT", side="BUY_OPEN")
            print("    append_fill after writer-gate: SUCCEEDED (unexpected)")
        except LS.LedgerError as exc:
            print("    append_fill after writer-gate refused:", exc.reason)
        # resolve the block again so the rest of the probe can proceed
        await ledger.reconcile_against_exchange(
            [{"symbol": "BTCUSDT", "quantity": "0.20"}])
        print("    block resolved:", not ledger.blocked)

        # --- (5) FILL(result=RECONCILED) alone satisfies require_reconciled -
        await ledger.append(event_type="FILL", intent_id="i-lone",
                            fill_id="f-lone", price="100", quantity="1",
                            symbol="ETHUSDT", side="BUY_OPEN",
                            result="RECONCILED")
        lone = await ledger.require_reconciled("i-lone")
        print("(5) require_reconciled on an intent whose ONLY record is a "
              "FILL with result=RECONCILED:", lone)
    except Exception as exc:  # pragma: no cover - probe diagnostics
        print("probe step raised:", type(exc).__name__, exc)
    finally:
        await ledger.stop()
        await store.close()
    print("tmpdir:", tmp)


if __name__ == "__main__":
    asyncio.run(main())
