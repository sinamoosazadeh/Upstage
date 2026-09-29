"""V1d probe E-015 — fill_from_result fallbacks.
READ-ONLY verification of the REAL apex.ops.paper_loop.fill_from_result and the
REAL ledger fill path (temporary SQLite, repository DDL). Shows:
 (a) PARTIAL/FILLED response without executedQty -> the ORDER quantity is
     recorded as the executed quantity;
 (b) executedQty=0 as a JSON NUMBER -> same fallback (0 is falsy); the string
     "0" is kept verbatim (a zero-quantity fill);
 (c) missing fill id -> order_id becomes the fill identity, so a SECOND
     partial of the same order is silently deduplicated by fill_id;
 (d) non-finite price/quantity are not validated and poison the position."""
import asyncio
import os
import sys
import tempfile
from decimal import Decimal
from types import MappingProxyType

os.environ.setdefault("APEX_ENV", "PAPER")
os.environ.setdefault("APEX_ALLOW_SIGNED", "1")
os.environ.setdefault("TOOBIT_API_KEY", "TEST_KEY_CP7")
os.environ.setdefault("TOOBIT_API_SECRET", "TEST_SECRET_CP7")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from apex.data_catalog.store import sqlite_store as ss
from apex.execution import fsm as F
from apex.execution.toobit_adapter import AdapterResult
from apex.ledger.store import LedgerWriter

ISO = "2026-01-01T00:00:00.000Z"


def venue_result(outcome, inner, order_id="900001"):
    return AdapterResult(
        operation="query_order_state", endpoint="GET /api/v1/futures/order",
        ok=True, classification="OK", outcome=outcome, business_code=0,
        http_status=200, data=MappingProxyType({"data": inner}),
        client_order_id="i-1", order_id=order_id, idempotency_key="k" * 64,
        reconcile_required=False, resubmitted=False, cached=False,
        interval_disabled=None, attempts=(), error_code=None, rule="probe")


def make_plan():
    from apex.identity.canonical_json import canonical_json
    from apex.identity.hashes import sha256_hex
    return F.TradePlan(
        proposal_id="pr-0001", setup_id="su-0001", symbol="BTCUSDT",
        timeframe="1h", direction="LONG", entry_ref="E-01/BOS",
        stop_price=99.0, target_price=103.0, sized_quantity=10.0,
        risk_amount=4.0, contract_multiplier=1.0, decision="ALLOW",
        vetoes_applied=(), risk_state="LowRisk", package_version="4",
        snapshot_id="sn-0001", as_of=ISO, created_utc=ISO, lineage="t",
        payload_hash=sha256_hex(canonical_json({"p": 1})), environment="PAPER")


async def main() -> None:
    from apex.ops.paper_loop import fill_from_result
    plan = make_plan()

    # (a) PARTIAL without executed quantity, order quantity 10
    r_a = venue_result("PARTIAL", {"avgPrice": "100", "quantity": "10"})
    print("(a) PARTIAL no executedQty      ->", fill_from_result(r_a, plan))
    # (b) executedQty = 0 (JSON number) and as string
    r_b = venue_result("PARTIAL", {"avgPrice": "100", "quantity": "10",
                                   "executedQty": 0})
    print("(b) PARTIAL executedQty=0 (int) ->", fill_from_result(r_b, plan))
    r_b2 = venue_result("PARTIAL", {"avgPrice": "100", "quantity": "10",
                                    "executedQty": "0"})
    print("    PARTIAL executedQty='0' (str)->", fill_from_result(r_b2, plan))
    # (c) no tradeId/fillId -> identity falls back to order_id, then proposal
    r_c = venue_result("PARTIAL", {"avgPrice": "100", "executedQty": "3"},
                       order_id="900007")
    print("(c) PARTIAL executedQty=3, no fill id ->", fill_from_result(r_c, plan))
    r_c2 = venue_result("PARTIAL", {"avgPrice": "101", "executedQty": "2"},
                        order_id="900007")
    print("(c2) SECOND partial, same order  ->", fill_from_result(r_c2, plan))

    # (d) full ledger path: two partials of one order -> one deduped FILL;
    #     then a NaN-priced fill poisons the ledger position.
    tmp = tempfile.mkdtemp(prefix="v1d_e015_")
    store = ss.SQLiteStore(os.path.join(tmp, "apex.sqlite3"))
    await store.open()
    ledger = LedgerWriter(store, clock=lambda: ISO)
    await ledger.initialize()
    try:
        await ledger.start()
        machine = F.ExecutionFSM(intent_id="i-1", ledger=ledger,
                                 environment="PAPER")
        machine._plan = plan
        f1 = fill_from_result(r_c, plan)
        f2 = fill_from_result(r_c2, plan)
        await machine.record_fill(fill_id=f1["fill_id"], price=f1["price"],
                                  quantity=f1["quantity"], symbol="BTCUSDT")
        await machine.record_fill(fill_id=f2["fill_id"], price=f2["price"],
                                  quantity=f2["quantity"], symbol="BTCUSDT")
        fills = [e for e in await ledger.read_ledger()
                 if e.event_type == "FILL"]
        print("(d) two venue partials (3 + 2) -> ledger FILL rows:", len(fills),
              "quantities:", [f.quantity for f in fills])
        positions = await ledger.positions_from_ledger()
        print("    ledger position after both partials:",
              positions.get("BTCUSDT", {}).get("net_quantity"),
              "(venue truth: 5)")

        # (e) non-finite numbers pass straight through
        r_nan = venue_result("FILLED", {"avgPrice": "NaN", "executedQty": "1"})
        print("(e) FILLED with avgPrice=NaN  ->", fill_from_result(r_nan, plan))
        await machine.record_fill(fill_id="f-nan", price="NaN", quantity="1",
                                  symbol="ETHUSDT", side="BUY_OPEN")
        positions2 = await ledger.positions_from_ledger()
        print("    ledger position after NaN fill:",
              positions2.get("ETHUSDT", {}).get("net_quantity"),
              "| avg entry:",
              positions2.get("ETHUSDT", {}).get("average_entry_price"))
        delta = Decimal("1") - Decimal(
            str(positions2["ETHUSDT"]["net_quantity"]))
        print("    |1 - net_quantity| <= 1 (reconcile agree?):",
              abs(delta) <= Decimal("1"))
    finally:
        await ledger.stop()
        await store.close()
    print("tmpdir:", tmp)


if __name__ == "__main__":
    asyncio.run(main())
