"""Reproduce CP-7 fake ACK vs manually appended fills, using temp SQLite only."""
import os
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(root), str(root / "tests"), str(root / "tests" / "integration")]
import test_cp7_paper_loop as cp7
from apex.data_catalog.store import sqlite_store as ss

# Explicit CP-7 fixture values; no .env/secret reads and all adapter calls use FakeToobitResponder.
os.environ.update({
    "APEX_ENV": "PAPER",
    "APEX_ALLOW_SIGNED": "1",
    "TOOBIT_API_KEY": cp7.TEST_KEY,
    "TOOBIT_API_SECRET": cp7.TEST_SECRET,
})

async def exercise(store, tmp_path):
    paper = cp7.PaperLoop(store, tmp_path, fill_mode="none")
    await paper.start()
    try:
        await paper.boot()
        record = await paper.trade_cell(cp7.C.BundleCell("BTCUSDT", "1h"))
        await paper.drain()
        rows = await paper.ledger_rows()
        chain = await paper.ledger.verify_chain()
        order = paper.responder.orders.get(record["intent_id"], {})
        return {
            "paper": paper,
            "record": record,
            "rows": rows,
            "chain": chain,
            "entry_order": dict(order),
            "fake_fill_count": len(paper.responder.fills),
            "fake_position_count": len(paper.responder.positions),
        }
    finally:
        await paper.stop()

with tempfile.TemporaryDirectory(prefix="i016-") as tmp:
    base = Path(tmp)
    store = ss.SQLiteStore(str(base / "apex.sqlite3"))
    cp7.run(store.open())
    try:
        result = cp7.run(exercise(store, base))
    finally:
        cp7.run(store.close())

record = result["record"]
print(f"adapter_outcome={record['outcome']}")
print(f"entry_order_status={result['entry_order'].get('status')}")
print(f"entry_order_executedQty={result['entry_order'].get('executedQty')}")
print(f"fake_responder_fills={result['fake_fill_count']}")
print(f"fake_responder_positions={result['fake_position_count']}")
print(f"ledger_fill_events={sum(row.event_type == 'FILL' for row in result['rows'])}")
print(f"ledger_outcome_events={sum(row.event_type == 'OUTCOME' for row in result['rows'])}")
print(f"trade_record_filled={record['filled']}")
print(f"trade_record_closed={record['closed']}")
print(f"trade_record_reconciled={record['reconciled']}")
print(f"reconcile_agree={record['reconcile']['agree']}")
print(f"ledger_hash_chain_intact={result['chain']['intact']}")
