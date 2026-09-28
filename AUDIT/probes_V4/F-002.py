import asyncio
from common import scenario
async def main(store,w,path):
    await w.append_fill(intent_id='paper-i',fill_id='paper-f',price='100',quantity='2',symbol='BTCUSDT',side='BUY_OPEN',environment='PAPER')
    await w.append_fill(intent_id='live-i',fill_id='live-f',price='100',quantity='2',symbol='BTCUSDT',side='SELL_OPEN',environment='LIVE')
    print('mixed_environments_position=',(await w.positions_from_ledger())['BTCUSDT'])
asyncio.run(scenario(main))
