"""Synthetic result/price; invokes real PaperRuntime.manage_positions, no exchange."""
import asyncio
from types import SimpleNamespace
from unittest.mock import patch
from apex.ops.paper_loop import PaperRuntime
import apex.ops.paper_loop as pl

class Machine:
    state='MANAGED'
    def __init__(self):
        self._plan=SimpleNamespace(symbol='BTCUSDT',timeframe='1h',direction='LONG',sized_quantity='10',stop_price=90,target_price=105,setup_id='s')
        self._fills=[{'price':'100'}]
        self.booked=None
    async def record_fill(self, **kw): self.fill=kw
    async def close_position(self, **kw): self.booked=kw; return {'stop_gap':None}
    async def reconcile(self): return {'agree':True}
class Adapter:
    async def submit_order(self, **kw):
        return SimpleNamespace(outcome='FILLED',data={'avgPrice':'110','executedQty':'2','tradeId':'t'},order_id='o')
async def main():
    r=object.__new__(PaperRuntime)
    m=Machine(); r.working={'i':m}; r.adapter=Adapter(); r.store=None
    with patch.object(pl,'last_closed_price',new=async_return):
        out=await r.manage_positions(as_of='2026-01-01T00:00:00.000Z')
    print('exit_filled_quantity=',m.fill['quantity'],'booked_quantity=',m.booked['quantity'],'booked_pnl=',m.booked['pnl'],'gross_at_actual_quantity=',(110-100)*2,'outcome=',out)
async def async_return(*a, **kw): return '110'
asyncio.run(main())
