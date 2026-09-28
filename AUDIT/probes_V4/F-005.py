import asyncio
from common import scenario, count
async def main(store,w,path):
    a,b = await asyncio.gather(*[w.append_fill(intent_id='intent-a',fill_id='fill-x',price='100',quantity='1',symbol='BTCUSDT',side='BUY_OPEN') for _ in range(2)])
    print('concurrent_fill_ids=',a.fill_id,b.fill_id,'ledger_ids_different=',a.ledger_id!=b.ledger_id)
    print('fills=',await count(store.db,'ledger'),'net=',(await w.positions_from_ledger())['BTCUSDT']['net_quantity'])
    c=await w.append_fill(intent_id='intent-b',fill_id='fill-x',price='300',quantity='7',symbol='ETHUSDT',side='BUY_OPEN')
    print('conflicting_replay_returned_original=',c.intent_id,c.quantity,'intent_b_entries=',len(await w.find_by_intent('intent-b')))
asyncio.run(scenario(main))
