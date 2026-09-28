import asyncio
from common import scenario, FaultDB, count
from apex.ledger.store import LedgerWriter

PLAN = dict(proposal_id='p-test',setup_id='s-test',symbol='BTCUSDT',timeframe='1h',direction='LONG',sized_quantity='1',decision='ALLOW',environment='PAPER')
OUTCOME = dict(outcome_id='o-test',setup_id='s-test',entry_price='100',exit_price='110',pnl='10')
async def main(store,w,path):
    await store.db.execute("INSERT INTO setup_candidate (setup_id) VALUES ('s-test')")
    await store.db.commit()
    for table,payload,method in [('trade_plan',PLAN,'append_trade_plan'),('outcome',OUTCOME,'append_outcome')]:
        w._db = FaultDB(store.db, 'INSERT INTO ledger (')
        try: await getattr(w, method)(payload)
        except OSError as e: print(table,'fault=',str(e))
        print(table,'rows=',await count(store.db,table),'ledger=',await count(store.db,'ledger'))
        w._db = store.db
asyncio.run(scenario(main))
