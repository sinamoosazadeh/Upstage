"""V1d probe E-012 — are the three AI.9 controls (raw_hash_chain, risk_recheck,
fsm_state) real checks?  READ-ONLY verification: runs the REAL
apex.execution.fsm.StartupReconciliation methods against a temporary-file
SQLite database created with the repository's own DDL. No repo file is
modified, no data/ is touched, no network is used."""
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

from apex.data_catalog.store import sqlite_store as ss
from apex.ledger.store import LedgerWriter
from apex.execution import fsm as F

ISO = "2026-01-01T00:00:00.000Z"


async def main() -> None:
    tmp = tempfile.mkdtemp(prefix="v1d_e012_")
    store = ss.SQLiteStore(os.path.join(tmp, "apex.sqlite3"))
    await store.open()
    ledger = LedgerWriter(store, clock=lambda: ISO)
    await ledger.initialize()
    await ledger.start()

    # ---- corrupt the raw store: 10 manifests whose hashes are garbage and
    # ---- whose chain is broken, 10 observations whose content_hash does not
    # ---- match their payload. AI.9 step 2 must halt on this ("re-compute
    # ---- payload hashes; compare against stored hashes; halt if mismatch").
    for i in range(10):
        await store.db.execute(
            "INSERT INTO raw_manifest (manifest_id, manifest_hash, period_start,"
            " period_end, observation_count, content_hashes_included,"
            " parent_manifest_hash, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (f"man-{i}", f"corrupt-hash-{i}", ISO, ISO, 1,
             '["does-not-match-anything"]',
             None if i == 0 else "WRONG-PARENT-NO-SUCH-HASH", ISO))
    for i in range(10):
        await store.db.execute(
            "INSERT INTO raw_observation (event_id, as_of, symbol, timeframe,"
            " open, high, low, close, volume, oi, oi_timestamp, oi_state,"
            " status, content_hash, source, availability_time, quality_vector,"
            " created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"obs-corrupt-{i}", ISO, "BTCUSDT", "1h", "100", "101", "99",
             "100", "10", None, None, "MISSING", "CLOSED",
             f"garbage-content-hash-{i}", "TOOBIT", ISO, None, ISO))
    await store.db.commit()

    # ---- a materialized plan whose sized_quantity is an absurd capital
    # ---- breach, and an open ledger position of 100000 BTC with NO
    # ---- protective orders anywhere (AI.9 step 6 must catch both).
    await ledger.append_trade_plan({
        "proposal_id": "pr-cap-breach", "setup_id": "su-1", "symbol": "BTCUSDT",
        "timeframe": "1h", "direction": "LONG", "entry_ref": "E-01/BOS",
        "stop_price": 99.0, "target_price": 103.0, "sized_quantity": 1_000_000.0,
        "risk_amount": 10.0, "contract_multiplier": 1.0, "decision": "ALLOW",
        "vetoes_applied": [], "risk_state": "LowRisk", "package_version": "4",
        "snapshot_id": "sn-1", "as_of": ISO, "created_utc": ISO, "lineage": "t",
        "payload_hash": "h" * 64, "environment": "PAPER"})
    await ledger.append_fill(intent_id="i-open-1", fill_id="f-open-1",
                             price="100", quantity="100000",
                             symbol="BTCUSDT", side="BUY_OPEN")
    # a second symbol to break any concentration limit
    await ledger.append_fill(intent_id="i-open-2", fill_id="f-open-2",
                             price="100", quantity="50000",
                             symbol="ETHUSDT", side="BUY_OPEN")

    # ---- contradictory FSM ledger state: intent A is RECONCILED (terminal)
    # ---- but an "open" SUBMITTING/ACKNOWLEDGED pair exists for intent B and
    # ---- the broker has no such state at all (no adapter is wired).
    await ledger.append_fsm_transition(intent_id="i-A", from_state="READY",
                                       to_state="SUBMITTING", reason="t",
                                       trigger="SUBMIT_ORDER")
    await ledger.append_fsm_transition(intent_id="i-A", from_state="SUBMITTING",
                                       to_state="ACKNOWLEDGED", reason="t",
                                       trigger="EXCHANGE_ACK")
    await ledger.append_fsm_transition(intent_id="i-B", from_state="CLOSED",
                                       to_state="RECONCILED", reason="t",
                                       trigger="RECONCILE_MATCH")

    machine = F.StartupReconciliation(ledger=ledger, adapter=None,
                                      clock=lambda: 0.0, utc_now=lambda: ISO,
                                      environment="PAPER", drift_seconds=0.0)
    raw = await machine._ai9_raw_hash_chain()
    risk = await machine._ai9_risk_recheck()
    fsmc = await machine._ai9_fsm_state()
    print("raw_hash_chain :", raw.name, raw.passed, raw.status, "|", raw.detail)
    print("risk_recheck   :", risk.name, risk.passed, risk.status, "|", risk.detail)
    print("fsm_state      :", fsmc.name, fsmc.passed, fsmc.status, "|", fsmc.detail)

    # what the trade_plans() projection actually returns (leverage sub-check):
    plans = await ledger.trade_plans(environment="PAPER")
    print("trade_plan row keys:", sorted(plans[0].keys()))
    print("'leverage' in any plan row:", any("leverage" in p for p in plans))
    positions = await ledger.positions_from_ledger()
    print("ledger positions (capital/concentration breach, no protection):",
          {s: p["net_quantity"] for s, p in positions.items()})
    print("protective orders in ledger:",
          len([e for e in await ledger.read_ledger()
               if e.event_type == "PROTECTION_FAILED" or
               (e.event_type == "FSM_TRANSITION" and
                dict(e.raw).get("trigger") == "PROTECTION_PLACED")]))
    await ledger.stop()
    await store.close()
    print("tmpdir:", tmp)


if __name__ == "__main__":
    asyncio.run(main())
