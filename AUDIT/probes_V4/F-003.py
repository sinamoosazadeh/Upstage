import asyncio
from common import scenario
async def main(store,w,path):
    for name,side,price in [('open1','BUY_OPEN','100'),('exit','SELL_CLOSE','100'),('open2','BUY_OPEN','200')]:
        await w.append_fill(intent_id=name,fill_id=name,price=price,quantity='1',symbol='BTCUSDT',side=side)
    p=(await w.positions_from_ledger())['BTCUSDT']
    print('net=',p['net_quantity'],'average_entry_price=',p['average_entry_price'],'expected_current_basis=200')
asyncio.run(scenario(main))
