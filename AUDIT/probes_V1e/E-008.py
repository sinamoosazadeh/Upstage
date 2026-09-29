"""V1e E-008 — real boot reconciliation and the real position-row selector,
with temporary SQLite/repository fake venue only."""
import asyncio
import pathlib
import sys
import tempfile
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from fake_toobit_responder import FakeToobitResponder, TEST_API_KEY, TEST_API_SECRET
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.execution.fsm import StartupReconciliation, _position_row_for
from apex.execution.toobit_adapter import ToobitAdapter
from apex.ledger.store import LedgerWriter

CFG = SimpleNamespace(allow_signed=True, toobit_api_key=TEST_API_KEY,
                      toobit_api_secret=TEST_API_SECRET, apex_env="PAPER")
ISO = "2026-01-01T00:00:00.000Z"

async def main():
    with tempfile.TemporaryDirectory(prefix="apex-v1e-e008-") as tmp:
        store = SQLiteStore(str(pathlib.Path(tmp) / "probe.sqlite3")); await store.open()
        ledger = LedgerWriter(store); await ledger.initialize(); await ledger.start()
        await ledger.append_fill(intent_id="i-e008", fill_id="f-e008", price="100",
                                 quantity="2", symbol="BTCUSDT", side="BUY_OPEN")
        responder = FakeToobitResponder(api_key=TEST_API_KEY, api_secret=TEST_API_SECRET)
        responder.seed_position("BTC-SWAP-USDT", "LONG", "2")
        adapter = ToobitAdapter(config=CFG, transport=responder, utc_now=lambda: ISO,
                                clock=lambda: 1000.0)
        boot = StartupReconciliation(ledger=ledger, adapter=adapter, utc_now=lambda: ISO,
                                     clock=lambda: 1000.0)
        verdict = await boot.reconcile_boot()
        direct = _position_row_for([{ "symbol": "BTC-SWAP-USDT", "quantity": "2" }], "BTCUSDT")
        print("boot_agree", verdict["agree"])
        print("deltas", verdict["deltas"])
        print("position_row_for_BTCUSDT", direct)
        await ledger.stop(); await store.close()

asyncio.run(main())
