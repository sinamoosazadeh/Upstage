"""V1d new finding X-V1d-001 — StartupReconciliation._ai9_risk_recheck's ONLY
implemented sub-check (leverage vs cap) is dead code: it reads `leverage` from
LedgerWriter.trade_plans(), whose projection is the frozen trade_plan DDL —
a table with NO leverage column. The leverage value DOES exist in the ledger
TRADE_PLAN record payload, but the check never looks there.
READ-ONLY verification against temporary SQLite with the repository DDL."""
import asyncio
import os
import sys
import tempfile

os.environ.setdefault("APEX_ENV", "PAPER")
os.environ.setdefault("APEX_ALLOW_SIGNED", "1")
os.environ.setdefault("TOOBIT_API_KEY", "TEST_KEY_CP7")
os.environ.setdefault("TOOBIT_API_SECRET", "TEST_SECRET_CP7")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from apex.data_catalog.store import sqlite_store as ss
from apex.execution import fsm as F
from apex.ledger.store import LedgerWriter, TRADE_PLAN_COLUMNS

ISO = "2026-01-01T00:00:00.000Z"


async def main() -> None:
    tmp = tempfile.mkdtemp(prefix="v1d_x001_")
    store = ss.SQLiteStore(os.path.join(tmp, "apex.sqlite3"))
    await store.open()
    ledger = LedgerWriter(store, clock=lambda: ISO)
    await ledger.initialize()
    try:
        await ledger.start()
        # a plan carrying an ABSURD leverage (well above every cap) — the
        # ledger TRADE_PLAN record preserves it in its payload
        await ledger.append_trade_plan({
            "proposal_id": "pr-lev", "setup_id": "su-1", "symbol": "BTCUSDT",
            "timeframe": "1h", "direction": "LONG", "entry_ref": "E-01/BOS",
            "stop_price": 99.0, "target_price": 103.0, "sized_quantity": 1.0,
            "risk_amount": 10.0, "contract_multiplier": 1.0,
            "decision": "ALLOW", "vetoes_applied": [], "risk_state": "LowRisk",
            "package_version": "4", "snapshot_id": "sn", "as_of": ISO,
            "created_utc": ISO, "lineage": "t", "payload_hash": "h" * 64,
            "environment": "PAPER", "leverage": 125.0})
        rows = await ledger.trade_plans(environment="PAPER")
        print("trade_plan table columns:", len(TRADE_PLAN_COLUMNS),
              "| 'leverage' among them:", "leverage" in TRADE_PLAN_COLUMNS)
        print("trade_plans() row has 'leverage' key:",
              "leverage" in rows[0])
        rec = [e for e in await ledger.read_ledger()
               if e.event_type == "TRADE_PLAN"][0]
        print("ledger TRADE_PLAN record payload leverage:",
              dict(rec.raw)["payload"]["trade_plan"].get("leverage"))
        machine = F.StartupReconciliation(ledger=ledger, adapter=None,
                                          clock=lambda: 0.0,
                                          utc_now=lambda: ISO,
                                          environment="PAPER",
                                          drift_seconds=0.0)
        check = await machine._ai9_risk_recheck()
        print("risk_recheck on a plan with leverage=125 (1h cap=4):",
              check.name, check.passed, check.status, "|", check.detail)
    finally:
        await ledger.stop()
        await store.close()
    print("tmpdir:", tmp)


if __name__ == "__main__":
    asyncio.run(main())
