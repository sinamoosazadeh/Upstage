"""V1d new finding X-V1d-003 — re-materializing an already-materialized plan
raises a RAW sqlite3.IntegrityError out of LedgerWriter.append_trade_plan /
ExecutionFSM.submit, instead of a named LedgerError/CellRefusal (the G6
named-refusal discipline every other ledger failure follows).
READ-ONLY verification against temporary SQLite with the repository DDL."""
import asyncio
import os
import sys
import tempfile

os.environ.setdefault("APEX_ENV", "PAPER")
os.environ.setdefault("APEX_ALLOW_SIGNED", "1")
os.environ.setdefault("TOOBIT_API_KEY", "TEST_KEY_CP7")
os.environ.setdefault("TOOBIT_API_SECRET", "TEST_SECRET_CP7")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from apex.data_catalog.store import sqlite_store as ss
from apex.execution import fsm as F
from apex.ledger.store import LedgerWriter

ISO = "2026-01-01T00:00:00.000Z"


class FakeProposal:
    def to_dict(self):
        return {"proposal_id": "pr-dup", "setup_id": "su-1",
                "direction": "LONG", "stop": 99.0, "targets": [103.0],
                "entry_logic_ref": "E-01/BOS", "snapshot_id": "sn-0001"}


def build(ledger_clock):
    return F.build_trade_plan(
        proposal=FakeProposal(),
        adjudication={"decision": "ALLOW", "sized_quantity": 0.10,
                      "vetoes_applied": [], "sizing": {"R_allowed": 10.0},
                      "snapshot_id": "sn-0001"},
        symbol="BTCUSDT", timeframe="1h", environment="PAPER", as_of=ISO,
        capital=10000.0, contract_multiplier=1.0, risk_state="LowRisk",
        package_version="4.0.0", created_utc=ISO)


async def main() -> None:
    tmp = tempfile.mkdtemp(prefix="v1d_x003_")
    store = ss.SQLiteStore(os.path.join(tmp, "apex.sqlite3"))
    await store.open()
    ledger = LedgerWriter(store, clock=lambda: ISO)
    await ledger.initialize()
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tests"))
    from apex.config import Config
    from apex.execution.toobit_adapter import ToobitAdapter
    from fake_toobit_responder import FakeToobitResponder
    adapter = ToobitAdapter(config=Config(),
                            transport=FakeToobitResponder(
                                api_key="TEST_KEY_CP7",
                                api_secret="TEST_SECRET_CP7"),
                            utc_now=lambda: ISO, clock=lambda: 1000.0)
    try:
        await ledger.start()
        machine = F.ExecutionFSM(intent_id="i-x003-a", ledger=ledger,
                                 adapter=adapter, environment="PAPER",
                                 utc_now=lambda: ISO, clock=lambda: 1000.0)
        await machine.submit(build(ledger), price="100")
        print("first submit: OK (plan materialized, proposal_id=pr-dup)")
        machine2 = F.ExecutionFSM(intent_id="i-x003-b", ledger=ledger,
                                  adapter=adapter, environment="PAPER",
                                  utc_now=lambda: ISO, clock=lambda: 1000.0)
        try:
            await machine2.submit(build(ledger), price="100")
            print("second submit with same proposal_id: ACCEPTED (unexpected)")
        except Exception as exc:
            print("second submit raised:", type(exc).__module__ + "."
                  + type(exc).__name__)
            print("  message:", exc)
            print("  is a named LedgerError/FsmError with .reason?:",
                  isinstance(exc, (LedgerWriter.__module__ and Exception,)))
            from apex.ledger.store import LedgerError
            print("  isinstance LedgerError:", isinstance(exc, LedgerError),
                  "| isinstance FsmError:", isinstance(exc, F.FsmError),
                  "| has .reason:", hasattr(exc, "reason"))
        print("machine2 state after the raw failure:", machine2.state,
              "| ledger intact, machine untouched pre-submission)")
    finally:
        await ledger.stop()
        await store.close()
    print("tmpdir:", tmp)


if __name__ == "__main__":
    asyncio.run(main())
