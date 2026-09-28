import asyncio
from common import scenario, FaultDB
async def main(store,w,path):
    # Fault injection: an upstream close arrives without the corresponding OPEN.
    row=await w.append_fill(intent_id='orphan',fill_id='exit-1',price='100',quantity='2',symbol='ETHUSDT',side='SELL_CLOSE')
    p=await w.positions_from_ledger()
    print('event=',row.event_type,'net=',p['ETHUSDT']['net_quantity'],'direction=',p['ETHUSDT']['direction'])
    print('chain_intact=',(await w.verify_chain())['intact'])
asyncio.run(scenario(main))
