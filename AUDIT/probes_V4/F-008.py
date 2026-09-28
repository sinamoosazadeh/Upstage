import asyncio
from common import scenario, FaultDB
from apex.ledger.store import LedgerWriter
async def main(store,w,path):
    await w.append_fill(intent_id='i',fill_id='f',price='100',quantity='3',symbol='BTCUSDT',side='BUY_OPEN')
    r=await w.reconcile_against_exchange([dict(symbol='BTCUSDT',quantity='0')])
    print('divergence=',r['delta_count'],'blocked=',w.blocked)
    await w.stop()
    w2=LedgerWriter(store); await w2.initialize(); await w2.start()
    try:
        print('restart_blocked=',w2.blocked)
        await w2.append(event_type='FILL',intent_id='unreconciled')
        print('restart_fill_accepted=True')
        await w2.reconcile_against_exchange([dict(symbol='BTCUSDT',quantity='0')])
        w2._db=FaultDB(store.db,'INSERT INTO ledger (')
        try: await w2.reconcile_against_exchange([dict(symbol='BTCUSDT',quantity='3')])
        except OSError as e: print('resolve_fault=',e)
        print('post_fault_blocked=',w2.blocked)
        w2._db=store.db
        await w2.append(event_type='FILL',intent_id='post-fault')
        print('post_fault_fill_accepted=True')
    finally: await w2.stop()
asyncio.run(scenario(main))
