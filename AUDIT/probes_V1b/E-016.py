"""Real SQLiteStore/LedgerWriter projection probe; temporary DB only."""
import asyncio, tempfile, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.ledger.store import LedgerWriter
from apex.ops.engine_context import paper_account_state, BridgeError
from apex.ops.paper_loop import intent_id_for
from apex.execution.fsm import TradePlan

async def main():
  with tempfile.TemporaryDirectory() as d:
    s=await SQLiteStore(d+'/x.sqlite').open(); l=LedgerWriter(s,clock=lambda:'2026-01-01T00:00:00.000Z'); await l.initialize(); await l.start()
    row={'proposal_id':'plan-000000000001','setup_id':'setup-1','symbol':'BTCUSDT','timeframe':'1h','direction':'LONG','entry_ref':'x','stop_price':99,'target_price':103,'sized_quantity':1,'risk_amount':1,'contract_multiplier':1,'decision':'ALLOW','vetoes_applied':[],'risk_state':'LowRisk','package_version':'4','snapshot_id':'sn','as_of':'2026-01-01T00:00:00.000Z','created_utc':'2026-01-01T00:00:00.000Z','lineage':'x','payload_hash':'x','environment':'PAPER','leverage':1,'owner_leverage_cap':1}
    await l.append_trade_plan(row); plan=TradePlan(**row); iid=intent_id_for(plan,1767225600000)
    await l.append_fsm_transition(intent_id=iid,from_state='READY',to_state='SUBMITTING',reason='probe',trigger='SUBMIT_ORDER',environment='PAPER',evidence={'symbol':'BTCUSDT','quantity':'1','price':'100'})
    print('proposal_id=',row['proposal_id']); print('d50_intent=',iid); print('legacy_candidate=','i-'+row['proposal_id'][-12:])
    try: print(await paper_account_state(l,marks={'BTCUSDT':100},contract_specs={'BTCUSDT':{'contract_multiplier':1}},environment='PAPER'))
    except BridgeError as e: print(type(e).__name__,str(e))
    await l.stop(); await s.close()
asyncio.run(main())
