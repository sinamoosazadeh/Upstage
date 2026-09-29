"""Bounded observation of unbounded native retry; pause/cancel/recovery controls."""
from perf_support import *
from apex.ops import bootstrap_service as BS
from apex.data_catalog.ingest.toobit_public import ToobitPublicError, parse_kline_to_observation
from unittest.mock import patch
START=BS._iso_to_ms('2026-09-01T00:00:00.000Z');END=START+180000
class Venue:
    def __init__(self,marker):self.marker=marker;self.calls=0
    async def get_klines(self,sym,tf,start,end,limit):
        self.calls+=1
        if self.marker:raise ToobitPublicError('klines',self.marker)
        return [parse_kline_to_observation(sym,tf,[START+i*60000,'100','101','99','100','10',START+(i+1)*60000-1],i)
                for i in range(3) if START+i*60000<=end]

async def main():
    with tempfile.TemporaryDirectory(prefix='v1a-retry-') as d:
        cfg=SAFE['config'](False);cfg._env['APEX_SQLITE_PATH']=d+'/scratch.sqlite'
        runtime=await Runtime(cfg).start()
        try:
            await runtime.bus.stop();await corpus(runtime)
            for enabled in (False,True):
                await indexes(runtime.store.db,enabled)
                for marker,action,symbol in (('code=-1003','pause','BTCUSDT'),('HTTP 429','cancel','ETHUSDT')):
                    bridge=BS.AsyncBridge().start();venue=Venue(marker)
                    source=BS.ToobitKlineSource(client=venue,bridge=bridge,max_pages=1,walk_backoff_seconds=(0,0,0))
                    cp=d+f'/cp-{enabled}-{action}.sqlite'
                    service=BS.BootstrapService(config=cfg,store=runtime.store,source=source,cells=[(symbol,'1m')],checkpoint_path=cp)
                    await service.open();queries=[]
                    await runtime.store.db.set_trace_callback(lambda q:queries.append(q) if q.lstrip().upper().startswith('SELECT') else None)
                    try:
                        with patch.object(BS,'free_disk_mb',lambda:10000),patch.object(BS,'read_battery',lambda:None):
                            task=asyncio.create_task(service.run(start_ms=START,end_ms=END,backoff_seconds=(.01,.02,.03),announce=False))
                            await asyncio.sleep(.32)
                            before=await service._checkpoints.load_bootstrap(f'{symbol}:1m')
                            emit(marker=marker,device_indexes=enabled,still_running=not task.done(),venue_calls=venue.calls,
                                 outer_backoffs=service.runner.state.backoffs,source_pages=source.pages_served,checkpoint_before=before)
                            assert not task.done() and venue.calls>4 and source.pages_served==0
                            if action=='pause':
                                service.runner.command('pause');out=await asyncio.wait_for(task,1);assert out['status']=='PAUSED'
                            else:
                                task.cancel()
                                try:await task
                                except asyncio.CancelledError:pass
                            saved=await service._checkpoints.load_bootstrap(f'{symbol}:1m')
                            emit(action=action,checkpoint_after=saved)
                            assert saved['cursor_ms']==START and saved['bars_ingested']==0
                    finally:
                        await runtime.store.db.set_trace_callback(None);await service.close();bridge.close()
                    await plans(runtime.store.db,queries,f'{enabled}-{marker}')
                    # Recovery on a fresh service/source and same durable checkpoint.
                    # Recovery is measured once per action; both index variants measure refusal independently.
                    if not enabled:
                        b=BS.AsyncBridge().start();v=Venue(None)
                        good=BS.ToobitKlineSource(client=v,bridge=b,max_pages=1)
                        recovered=BS.BootstrapService(config=cfg,store=runtime.store,source=good,cells=[(symbol,'1m')],checkpoint_path=cp)
                        await recovered.open()
                        try:
                            with patch.object(BS,'free_disk_mb',lambda:10000),patch.object(BS,'read_battery',lambda:None):
                                result=await recovered.run(start_ms=START,end_ms=END,announce=False)
                            row=await recovered._checkpoints.load_bootstrap(f'{symbol}:1m')
                            emit(action='recovery',previous=action,status=result['status'],bars=result['bars_ingested'],checkpoint=row,venue_calls=v.calls)
                            assert result['status']=='COMPLETE' and result['bars_ingested']==3 and row['cursor_ms']==END
                        finally:await recovered.close();b.close()
            emit(guard_blocked_attempts=SAFE['blocked']);assert not SAFE['blocked']
        finally:await runtime.stop()
    print('PASS: native inner retries bounded, outer retries not capped; explicit pause/cancel and fresh recovery work')
asyncio.run(main())
