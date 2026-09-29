"""V1e E-010 — real adapter/FSM boot reconciliation on temp SQLite. It proves
that a recorded lost-ACK working order, and separately a venue fill, do not make
boot disagreement; no network/config/secret lookup."""
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

async def boot_with(responder, action):
    with tempfile.TemporaryDirectory(prefix="apex-v1e-e010-") as tmp:
        store = SQLiteStore(str(pathlib.Path(tmp) / "probe.sqlite3")); await store.open()
        ledger = LedgerWriter(store); await ledger.initialize(); await ledger.start()
        adapter = ToobitAdapter(config=CFG, transport=responder, utc_now=lambda: ISO,
                                clock=lambda: 1000.0)
        result = await action(adapter)
        boot = StartupReconciliation(ledger=ledger, adapter=adapter, utc_now=lambda: ISO,
                                     clock=lambda: 1000.0)
        verdict = await boot.reconcile_boot()
        print("submit", result.outcome, "reconcile", verdict["agree"],
              "open_intents", verdict["open_intents"],
              "venue_orders", [(k, v["status"]) for k,v in responder.orders.items()],
              "venue_fills", len(responder.fills))
        await ledger.stop(); await store.close()

async def main():
    lost = FakeToobitResponder(api_key=TEST_API_KEY, api_secret=TEST_API_SECRET)
    lost.lose_next_ack(record=True)
    async def lost_submit(adapter):
        return await adapter.submit_order(intent_id="i-lost-new", symbol="BTCUSDT", timeframe="1h",
                                          direction="LONG", quantity="0.2", price="100", leverage=4.0)
    await boot_with(lost, lost_submit)
    filled = FakeToobitResponder(api_key=TEST_API_KEY, api_secret=TEST_API_SECRET)
    filled.set_fill_mode("immediate", price="100")  # before adapter construction
    async def fill_submit(adapter):
        return await adapter.submit_order(intent_id="i-unledgered-fill", symbol="BTCUSDT", timeframe="1h",
                                          direction="LONG", quantity="0.2", price="100", leverage=4.0)
    await boot_with(filled, fill_submit)

asyncio.run(main())
