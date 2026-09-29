"""V1e E-006 — real manager/FSM/ledger with repo test fake for the documented
synthetic fill seam, plus real adapter duplicate cache and real-DLL SQLite EXPLAIN.
No network, repo data, secrets, or Config lookup."""
import asyncio
import pathlib
import sys
import tempfile
from decimal import Decimal
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from fake_toobit_responder import FakeToobitResponder, TEST_API_KEY, TEST_API_SECRET
from integration.test_ops_paper_loop import FakeAdapter
from apex.data_catalog.contracts import MarketObservation
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.execution.fsm import ExecutionFSM, TradePlan
from apex.execution.toobit_adapter import ToobitAdapter
from apex.ledger.store import LedgerWriter
from apex.ops.paper_loop import PaperRuntime, fill_from_result

CFG = SimpleNamespace(allow_signed=True, toobit_api_key=TEST_API_KEY,
                      toobit_api_secret=TEST_API_SECRET, apex_env="PAPER",
                      sqlite_path=".")
ISO = "2026-01-01T00:00:00.000Z"
PLAN = TradePlan("pr-e006", "su-e006", "BTCUSDT", "1h", "LONG", "probe",
                 99.0, 103.0, 0.2, 10.0, 1.0, "ALLOW", (), "LowRisk", "4.0.0",
                 "sn-e006", ISO, ISO, "lin", "hash", "PAPER", 4.0, None)
WINDOW_SQL = "SELECT * FROM (SELECT observation_id, symbol, timeframe, open_price, high_price, low_price, close_price, volume, open_interest, open_time, retrieved_at, candle_status, quality_state, source, raw_payload_hash FROM market_observation WHERE symbol=? AND timeframe=? AND candle_status IN ('CLOSED','CORRECTED') AND open_time<=? ORDER BY open_time DESC LIMIT ?) ORDER BY open_time ASC"

async def setup_candidate(store):
    await store.db.execute("INSERT INTO setup_candidate (setup_id,timestamp,symbol,timeframe,pattern_ids,direction,entry_price,stop_loss,take_profit,risk_reward,confidence,quality,validity,snapshot_id,parent_ids,payload_hash,regime,utc_activity_window_id,lineage,authority,authority_scope) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("su-e006", ISO,"BTCUSDT","1h","[]","BULLISH","100","99","103",2,0.6,"Q3",1,"sn-e006","[]","h","TREND","aw","[]","SETUP_ENGINE","cell"))
    await store.db.commit()

async def main():
    with tempfile.TemporaryDirectory(prefix="apex-v1e-e006-") as tmp:
        store = SQLiteStore(str(pathlib.Path(tmp) / "probe.sqlite3")); await store.open()
        ledger = LedgerWriter(store); await ledger.initialize(); await ledger.start()
        await setup_candidate(store)
        obs = MarketObservation(symbol="BTCUSDT", timeframe="1h", open=Decimal("104"),
                                high=Decimal("105"), low=Decimal("94"), close=Decimal("94"),
                                volume=Decimal("10"), oi=Decimal("500"), timestamp=ISO,
                                sequence=0, status="CLOSED", source="TOOBIT",
                                availability_time=ISO)
        await store.ingest_raw(obs, "AVAILABLE")
        fake = FakeAdapter(entry_price="100", exit_price="94", fill_entry=True, exit_fills=True)
        runtime = PaperRuntime(config=CFG, store=store, ledger=ledger, adapter=fake)
        machine = ExecutionFSM(intent_id="i-e006", ledger=ledger, adapter=fake,
                               utc_now=lambda: ISO, clock=lambda: 1000.0)
        await machine.submit(PLAN, price="100", quantity="0.2")
        entry = fill_from_result(machine.last_adapter_result, PLAN)
        await machine.record_fill(fill_id=entry["fill_id"], price=entry["price"],
                                  quantity=entry["quantity"], symbol="BTCUSDT")
        await machine.place_protection(stop_price=99, target_price=103)
        await machine.activate_management(); runtime.working[machine.intent_id] = machine
        actions = await runtime.manage_positions(as_of=ISO)
        print("manager_action", actions[0]["exit_reason"], "filled", actions[0]["filled"],
              "stop_gap", actions[0]["stop_gap"], "working", sorted(runtime.working))
        cur = await store.db.execute("EXPLAIN QUERY PLAN " + WINDOW_SQL, ("BTCUSDT", "1h", ISO, 1))
        print("plan_without_device_indexes", [tuple(x) for x in await cur.fetchall()])
        await store.db.execute("CREATE INDEX idx_mo_sym_tf_open ON market_observation(symbol,timeframe,open_time)")
        await store.db.execute("CREATE INDEX idx_pit_scope_asof ON snapshot_pit(source_state,symbol_scope,timeframe_scope,as_of)")
        cur = await store.db.execute("EXPLAIN QUERY PLAN " + WINDOW_SQL, ("BTCUSDT", "1h", ISO, 1))
        print("plan_with_device_indexes", [tuple(x) for x in await cur.fetchall()])
        responder = FakeToobitResponder(api_key=TEST_API_KEY, api_secret=TEST_API_SECRET)
        adapter = ToobitAdapter(config=CFG, transport=responder, utc_now=lambda: ISO, clock=lambda: 1000.0)
        await adapter.submit_order(intent_id="i-e006-cache", symbol="BTCUSDT", timeframe="1h", direction="LONG", quantity="0.2", price="100", leverage=4.0)
        cached = await adapter.submit_order(intent_id="i-e006-cache", symbol="BTCUSDT", timeframe="1h", direction="LONG", quantity="0.2", price="100", leverage=4.0)
        print("real_adapter_cached", cached.cached, cached.error_code, cached.outcome)
        await ledger.stop(); await store.close()

asyncio.run(main())
