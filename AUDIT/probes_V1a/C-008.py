"""Native source with lazy offline venue, plus native repair at 200k rows."""
from perf_support import *
from apex.ops import bootstrap_service as BS, partial_bar_repair as PR
from apex.data_catalog.ingest.toobit_public import parse_kline_to_observation
import gc, tracemalloc
from unittest.mock import patch

class Venue:
    def __init__(self,n): self.n=n;self.calls=0
    async def get_klines(self,symbol,tf,start,end,limit):
        self.calls+=1
        last=min(self.n-1,(end-BS.DEEP_START_MS)//60000)
        return [parse_kline_to_observation(symbol,tf,[BS.DEEP_START_MS+i*60000,'100','101','99','100','10',BS.DEEP_START_MS+(i+1)*60000-1],i)
                for i in range(max(0,last-int(limit)+1),last+1)]

def source_measure(n,symbols,budget=None):
    bridge=BS.AsyncBridge().start();v=Venue(n)
    src=BS.ToobitKlineSource(client=v,bridge=bridge,max_pages=budget)
    tracemalloc.start();gc.collect();base=tracemalloc.get_traced_memory()[0]
    try:
        for symbol in symbols:
            t=time.perf_counter();p=src(symbol,'1m',BS.DEEP_START_MS,BS.DEEP_START_MS+n*60000)
            gc.collect();cur,peak=tracemalloc.get_traced_memory()
            emit(case='first_page',n=n,cells=len(src._history),calls=v.calls,served=len(p['rows']),
                 retained_bars=sum(map(len,src._history.values())),heap_delta=cur-base,peak=peak,seconds=time.perf_counter()-t)
        if budget:
            try:src(symbols[-1],'1m',p['next_cursor_ms'],BS.DEEP_START_MS+n*60000)
            except BS.BootstrapError as exc:emit(budget_refusal=exc.reason,calls=v.calls)
        else:
            original=BS._iso_to_ms;visits=0
            def counted(s):
                nonlocal visits
                visits+=1;return original(s)
            # Native scan with a delegating parse counter (no AST extraction).
            tracemalloc.stop();t=time.perf_counter()
            with patch.object(BS,'_iso_to_ms',counted):
                for i in range(5):p=src(symbols[-1],'1m',p['next_cursor_ms'],BS.DEEP_START_MS+n*60000)
            emit(case='five_cached_pages',n=n,parse_calls=visits,seconds=time.perf_counter()-t,calls=v.calls)
            assert visits==5*(n+2)
    finally:
        if tracemalloc.is_tracing():tracemalloc.stop()
        bridge.close()

async def repair_measure():
    with tempfile.TemporaryDirectory(prefix='v1a-repair-') as d:
        cfg=SAFE['config'](False);cfg._env['APEX_SQLITE_PATH']=d+'/scratch.sqlite'
        runtime=await Runtime(cfg).start()
        try:
            await runtime.bus.stop();await corpus(runtime)
            for enabled in (False,True):
                await indexes(runtime.store.db,enabled);queries=[]
                await runtime.store.db.set_trace_callback(lambda q:queries.append(q) if q.lstrip().upper().startswith('SELECT') else None)
                tracemalloc.start();t=time.perf_counter()
                rows=await PR.find_candidates(runtime.store,[('BTCUSDT','1m')])
                cur,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                emit(case='repair_one_cell',device_indexes=enabled,returned=len(rows),seconds=time.perf_counter()-t,heap_current=cur,heap_peak=peak)
                await runtime.store.db.set_trace_callback(None);await plans(runtime.store.db,queries,str(enabled))
                assert len(rows)==10000 and 'BTCUSDT' not in queries[0]
            emit(guard_blocked_attempts=SAFE['blocked']);assert not SAFE['blocked']
        finally:await runtime.stop()

for n in (10000,20000):source_measure(n,['BTCUSDT'],budget=1)
source_measure(100000,['BTCUSDT','ETHUSDT'])
asyncio.run(repair_measure())
print('PASS native source traffic/cache growth and unfiltered native repair')
