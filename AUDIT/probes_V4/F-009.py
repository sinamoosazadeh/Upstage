import asyncio
from common import scenario
async def main(store,w,path):
    await w.append_fill(intent_id='i',fill_id='f',price='100',quantity='.25',symbol='BTCUSDT',side='BUY_OPEN')
    a=await w.reconcile_against_exchange([dict(symbol='BTCUSDT',quantity='0')]); print('present_zero=',a['delta_count'],w.blocked)
    b=await w.reconcile_against_exchange([]); print('absent=',b['delta_count'],w.blocked,b['deltas'])
asyncio.run(scenario(main))
