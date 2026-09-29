"""V1d probe E-020 — FSM.submit sends a caller-supplied `quantity` to the wire
without any cap against plan.sized_quantity. READ-ONLY verification with the
REAL ExecutionFSM + real ToobitAdapter + repository FakeToobitResponder +
real LedgerWriter on temporary SQLite (repository DDL)."""
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
from apex.ledger.store import LedgerWriter
from fake_toobit_responder import FakeToobitResponder

ISO = "2026-01-01T00:00:00.000Z"


class FakeProposal:
    def __init__(self, pid="pr-0001"):
        self.pid = pid
    def to_dict(self):
        return {"proposal_id": self.pid, "setup_id": "su-0001",
                "direction": "LONG", "stop": 99.0, "targets": [103.0],
                "entry_logic_ref": "E-01/BOS", "snapshot_id": "sn-0001"}


async def main() -> None:
    tmp = tempfile.mkdtemp(prefix="v1d_e020_")
    store = ss.SQLiteStore(os.path.join(tmp, "apex.sqlite3"))
    await store.open()
    ledger = LedgerWriter(store, clock=lambda: ISO)
    await ledger.initialize()
    responder = FakeToobitResponder(api_key="TEST_KEY_CP7",
                                    api_secret="TEST_SECRET_CP7")
    adapter = ToobitAdapter(config=Config(), transport=responder,
                            utc_now=lambda: ISO, clock=lambda: 1000.0)
    try:
        await ledger.start()
        # Risk Kernel sized this plan at 1.0 (the ceiling; HANDOFF_CP6:
        # "treat as the ceiling; never size above it")
        plan = F.build_trade_plan(
            proposal=FakeProposal(),
            adjudication={"decision": "ALLOW", "sized_quantity": 1.0,
                          "vetoes_applied": [], "sizing": {"R_allowed": 10.0},
                          "snapshot_id": "sn-0001"},
            symbol="BTCUSDT", timeframe="1h", environment="PAPER", as_of=ISO,
            capital=10000.0, contract_multiplier=1.0, risk_state="LowRisk",
            package_version="4.0.0", created_utc=ISO)
        machine = F.ExecutionFSM(intent_id="i-e020", ledger=ledger,
                                 adapter=adapter, environment="PAPER",
                                 utc_now=lambda: ISO, clock=lambda: 1000.0)
        result = await machine.submit(plan, price="100", quantity=100)
        print("submit(quantity=100, plan.sized_quantity=%s) ->" %
              plan.sized_quantity, result)
        print("FSM state:", machine.state)

        rows = await ledger.trade_plans(environment="PAPER")
        print("materialized trade_plan.sized_quantity:",
              rows[0]["sized_quantity"])
        sent = responder.calls_to("/api/v1/futures/order", "POST")[-1].params
        print("wire quantity sent to venue:", sent["quantity"],
              "| side:", sent["side"], "| type:", sent["type"])
        trans = [e for e in await ledger.read_ledger()
                 if e.event_type == "FSM_TRANSITION"]
        ev0 = dict(trans[0].raw)["payload"]["evidence"]
        print("SUBMITTING transition evidence quantity:", ev0["quantity"])
        print("venue booked order:", responder.orders["i-e020"]["origQty"])

        # contrast: the too-SMALL override is refused by the adapter's own
        # min-notional guard (the only case the existing test covers)
        m2 = F.ExecutionFSM(intent_id="i-e020b", ledger=ledger,
                            adapter=adapter, environment="PAPER",
                            utc_now=lambda: ISO, clock=lambda: 1000.0)
        plan2 = F.build_trade_plan(
            proposal=FakeProposal("pr-0002"),
            adjudication={"decision": "ALLOW", "sized_quantity": 1.0,
                          "vetoes_applied": [], "sizing": {"R_allowed": 10.0},
                          "snapshot_id": "sn-0001"},
            symbol="BTCUSDT", timeframe="1h", environment="PAPER", as_of=ISO,
            capital=10000.0, contract_multiplier=1.0, risk_state="LowRisk",
            package_version="4.0.0", created_utc=ISO)
        r2 = await m2.submit(plan2, price="100", quantity="0.0001")
        print("too-small override (0.0001):", r2["outcome"],
              r2.get("classification"), "| posts:",
              len(responder.calls_to("/api/v1/futures/order", "POST")) - 1)
    finally:
        await ledger.stop()
        await store.close()
    print("tmpdir:", tmp)


if __name__ == "__main__":
    asyncio.run(main())
