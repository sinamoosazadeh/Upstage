"""V1e E-001 — real PAPER runtime, real FSM/adapter/ledger, test-only fake venue.
No network, no repository data, and no Config/environment/secret lookup."""
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
from apex.execution.fsm import TradePlan
from apex.execution.toobit_adapter import ToobitAdapter
from apex.ledger.store import LedgerWriter
from apex.ops.paper_loop import PaperRuntime

CFG = SimpleNamespace(allow_signed=True, toobit_api_key=TEST_API_KEY,
                      toobit_api_secret=TEST_API_SECRET, apex_env="PAPER",
                      sqlite_path=".")
ISO = "2026-01-01T00:00:00.000Z"


def plan():
    return TradePlan("pr-e001", "su-e001", "BTCUSDT", "1h", "LONG", "probe",
                     99.0, 103.0, 0.1, 10.0, 1.0, "ALLOW", (), "LowRisk", "4.0.0",
                     "sn-e001", ISO, ISO, "lin", "hash", "PAPER", 4.0, None)


async def main():
    with tempfile.TemporaryDirectory(prefix="apex-v1e-e001-") as tmp:
        store = SQLiteStore(str(pathlib.Path(tmp) / "probe.sqlite3"))
        await store.open()
        ledger = LedgerWriter(store)
        await ledger.initialize(); await ledger.start()
        responder = FakeToobitResponder(api_key=TEST_API_KEY, api_secret=TEST_API_SECRET)
        adapter = ToobitAdapter(config=CFG, transport=responder, utc_now=lambda: ISO,
                                clock=lambda: 1000.0)
        runtime = PaperRuntime(config=CFG, store=store, ledger=ledger, adapter=adapter,
                               fill_poll_attempts=3, fill_poll_delay=0.0)
        result = await runtime.execute_plan(plan(), price="100", timestamp_utc=ISO,
                                            close_ms=1767225600000)
        order_queries = [c for c in responder.calls if c.path == "/api/v1/futures/order" and c.method == "GET"]
        print("submit_outcome", result["outcome"])
        print("fill", result["fill"])
        print("fsm_state", result["state"])
        print("poll_query_count", len(order_queries))
        print("working_keys", sorted(runtime.working))
        print("adapter_order_status", responder.orders[result["intent_id"]]["status"])
        await ledger.stop(); await store.close()

asyncio.run(main())
