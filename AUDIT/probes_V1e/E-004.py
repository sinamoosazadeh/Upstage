"""V1e E-004 — real FSM/adapter/ledger on temp SQLite and repository fake venue.
No network or secret/config lookup."""
import asyncio
import pathlib
import sys
import tempfile
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from fake_toobit_responder import FakeToobitResponder, TEST_API_KEY, TEST_API_SECRET
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.execution.fsm import ExecutionFSM, IllegalTransitionError, TradePlan
from apex.execution.toobit_adapter import ToobitAdapter
from apex.ledger.store import LedgerWriter
from apex.ops.paper_loop import fill_from_result

CFG = SimpleNamespace(allow_signed=True, toobit_api_key=TEST_API_KEY,
                      toobit_api_secret=TEST_API_SECRET, apex_env="PAPER")
ISO = "2026-01-01T00:00:00.000Z"
PLAN = TradePlan("pr-e004", "su-e004", "BTCUSDT", "1h", "LONG", "probe",
                 99.0, 103.0, 0.2, 10.0, 1.0, "ALLOW", (), "LowRisk", "4.0.0",
                 "sn-e004", ISO, ISO, "lin", "hash", "PAPER", 4.0, None)

async def main():
    with tempfile.TemporaryDirectory(prefix="apex-v1e-e004-") as tmp:
        store = SQLiteStore(str(pathlib.Path(tmp) / "probe.sqlite3")); await store.open()
        ledger = LedgerWriter(store); await ledger.initialize(); await ledger.start()
        responder = FakeToobitResponder(api_key=TEST_API_KEY, api_secret=TEST_API_SECRET)
        responder.set_fill_mode("partial", price="100")  # set before adapter construction
        adapter = ToobitAdapter(config=CFG, transport=responder, utc_now=lambda: ISO,
                                clock=lambda: 1000.0)
        machine = ExecutionFSM(intent_id="i-e004", ledger=ledger, adapter=adapter,
                               utc_now=lambda: ISO, clock=lambda: 1000.0)
        submitted = await machine.submit(PLAN, price="100", quantity="0.2")
        first = machine.last_adapter_result
        print("submit_outcome", submitted["outcome"], "state", machine.state)
        print("venue_executed", responder.orders["i-e004"]["executedQty"],
              "plan_quantity", PLAN.sized_quantity)
        repeated = await adapter.query_order_state(symbol="BTCUSDT", client_order_id="i-e004")
        try:
            await machine.apply_adapter_result(repeated)
        except IllegalTransitionError as exc:
            print("repeat_partial_exception", exc.reason, "state", machine.state)
        fill = fill_from_result(first, PLAN)
        await machine.record_fill(fill_id=fill["fill_id"], price=fill["price"],
                                  quantity=fill["quantity"], symbol="BTCUSDT")
        protection = await machine.place_protection(stop_price=99, target_price=103)
        print("protection", protection["protected"], "state", machine.state)
        print("stop_quantity", responder.orders["i-e004-stop"]["origQty"],
              "target_quantity", responder.orders["i-e004-target"]["origQty"])
        plan2 = TradePlan("pr-e004b", "su-e004b", "BTCUSDT", "1h", "LONG", "probe",
                          99.0, 103.0, 0.2, 10.0, 1.0, "ALLOW", (), "LowRisk", "4.0.0",
                          "sn-e004b", ISO, ISO, "lin", "hash-b", "PAPER", 4.0, None)
        failure_machine = ExecutionFSM(intent_id="i-e004-failure", ledger=ledger, adapter=adapter,
                                       utc_now=lambda: ISO, clock=lambda: 1000.0)
        await failure_machine.submit(plan2, price="100", quantity="0.2")
        responder.fail_next(-1022)  # classification table's ABORT -> REJECTED
        try:
            await failure_machine.place_protection(stop_price=99, target_price=103)
        except IllegalTransitionError as exc:
            print("partial_protection_failure_exception", exc.reason,
                  "state", failure_machine.state)
        await ledger.stop(); await store.close()

asyncio.run(main())
