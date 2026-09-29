"""V1e E-011 — real per-intent reconciliation with real adapter responses
classified REJECTED (-1022); temporary SQLite/repository fake only."""
import asyncio
import pathlib
import sys
import tempfile
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from fake_toobit_responder import FakeToobitResponder, TEST_API_KEY, TEST_API_SECRET
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.execution.fsm import ExecutionFSM
from apex.execution.toobit_adapter import ToobitAdapter
from apex.ledger.store import LedgerWriter

CFG = SimpleNamespace(allow_signed=True, toobit_api_key=TEST_API_KEY,
                      toobit_api_secret=TEST_API_SECRET, apex_env="PAPER")
ISO = "2026-01-01T00:00:00.000Z"

async def main():
    with tempfile.TemporaryDirectory(prefix="apex-v1e-e011-") as tmp:
        store = SQLiteStore(str(pathlib.Path(tmp) / "probe.sqlite3")); await store.open()
        ledger = LedgerWriter(store); await ledger.initialize(); await ledger.start()
        responder = FakeToobitResponder(api_key=TEST_API_KEY, api_secret=TEST_API_SECRET)
        responder.fail_next(-1022, times=2)  # documented ABORT -> REJECTED
        adapter = ToobitAdapter(config=CFG, transport=responder, utc_now=lambda: ISO,
                                clock=lambda: 1000.0)
        machine = ExecutionFSM(intent_id="i-e011", ledger=ledger, adapter=adapter,
                               utc_now=lambda: ISO, clock=lambda: 1000.0)
        await machine.advance("SUBMIT_ORDER")
        await machine.advance("FULL_FILL")
        await machine.advance("POSITION_CLOSED")
        verdict = await machine.reconcile()
        print("agree", verdict["agree"], "state", machine.state,
              "delta", verdict["delta"], "order_state_in_evidence", machine.history[-1].evidence["order_state"])
        print("adapter_audit", [(x.operation,x.classification,x.outcome,x.business_code)
                                 for x in adapter.audit_trail()])
        await ledger.stop(); await store.close()

asyncio.run(main())
