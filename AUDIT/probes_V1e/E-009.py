"""V1e E-009 — boot reconciliation with three real adapter calls classified
as REJECTED by documented business code -1022. Temporary SQLite/fake venue only."""
import asyncio
import pathlib
import sys
import tempfile
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from fake_toobit_responder import FakeToobitResponder, TEST_API_KEY, TEST_API_SECRET
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.execution.fsm import StartupReconciliation
from apex.execution.toobit_adapter import ToobitAdapter
from apex.ledger.store import LedgerWriter

CFG = SimpleNamespace(allow_signed=True, toobit_api_key=TEST_API_KEY,
                      toobit_api_secret=TEST_API_SECRET, apex_env="PAPER")
ISO = "2026-01-01T00:00:00.000Z"

async def main():
    with tempfile.TemporaryDirectory(prefix="apex-v1e-e009-") as tmp:
        store = SQLiteStore(str(pathlib.Path(tmp) / "probe.sqlite3")); await store.open()
        ledger = LedgerWriter(store); await ledger.initialize(); await ledger.start()
        responder = FakeToobitResponder(api_key=TEST_API_KEY, api_secret=TEST_API_SECRET)
        responder.fail_next(-1022, times=3)  # toobit_map: ABORT -> REJECTED
        adapter = ToobitAdapter(config=CFG, transport=responder, utc_now=lambda: ISO,
                                clock=lambda: 1000.0)
        boot = StartupReconciliation(ledger=ledger, adapter=adapter, utc_now=lambda: ISO,
                                     clock=lambda: 1000.0)
        verdict = await boot.reconcile_boot()
        audit = [(x.operation, x.classification, x.outcome, x.business_code)
                 for x in adapter.audit_trail()]
        print("agree", verdict["agree"], "open_intents", verdict["open_intents"])
        print("adapter_audit", audit)
        print("check", boot.checks[-1].status, boot.checks[-1].detail)
        await ledger.stop(); await store.close()

asyncio.run(main())
