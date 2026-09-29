"""V1e E-002 — boot reconciliation finds an existing exchange order; real
PaperRuntime does not rebuild a working FSM. Test-only fake venue, temp SQLite."""
import asyncio
import pathlib
import sys
import tempfile
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from fake_toobit_responder import FakeToobitResponder, TEST_API_KEY, TEST_API_SECRET
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.execution.toobit_adapter import ToobitAdapter
from apex.ledger.store import LedgerWriter
from apex.ops.paper_loop import PaperRuntime

CFG = SimpleNamespace(allow_signed=True, toobit_api_key=TEST_API_KEY,
                      toobit_api_secret=TEST_API_SECRET, apex_env="PAPER",
                      sqlite_path=".")
ISO = "2026-01-01T00:00:00.000Z"


async def main():
    with tempfile.TemporaryDirectory(prefix="apex-v1e-e002-") as tmp:
        store = SQLiteStore(str(pathlib.Path(tmp) / "probe.sqlite3"))
        await store.open()
        ledger = LedgerWriter(store)
        await ledger.initialize(); await ledger.start()
        responder = FakeToobitResponder(api_key=TEST_API_KEY, api_secret=TEST_API_SECRET)
        responder.seed_order(intent_id="i-prior", symbol="BTCUSDT", timeframe="1h",
                             direction="LONG", quantity="0.1", price="100")
        adapter = ToobitAdapter(config=CFG, transport=responder, utc_now=lambda: ISO,
                                clock=lambda: 1000.0)
        runtime = PaperRuntime(config=CFG, store=store, ledger=ledger, adapter=adapter)
        verdict = await runtime.boot(drift_seconds=0.0)
        recon = verdict["reconciliation"]
        print("boot_state", verdict["boot_state"])
        print("reconcile_agree", recon["agree"])
        print("open_intents", recon["open_intents"])
        print("runtime_working", sorted(runtime.working))
        print("prior_order_status", responder.orders["i-prior"]["status"])
        await ledger.stop(); await store.close()

asyncio.run(main())
