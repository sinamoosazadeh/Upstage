"""Live-invocation resource changes, native runner + real SQLite ingestion."""
from perf_support import *
from apex.ops import bootstrap_service as BS
from apex.data_catalog.ingest.toobit_public import parse_kline_to_observation
from unittest.mock import patch

async def main():
    with tempfile.TemporaryDirectory(prefix='v1a-resource-') as d:
        cfg=SAFE['config'](False);cfg._env['APEX_SQLITE_PATH']=d+'/scratch.sqlite'
        runtime=await Runtime(cfg).start()
        try:
            await runtime.bus.stop();await corpus(runtime)
            for enabled in (False,True):
                await indexes(runtime.store.db,enabled)
                for case in ('disk','battery'):
                    n=0;probes={'disk':0,'battery':0};resource={'disk':513.,'battery':50}
                    start=BS._iso_to_ms('2026-09-01T00:00:00.000Z')+(int(enabled)*2+(case=='battery'))*600000
                    def disk():probes['disk']+=1;return resource['disk']
                    def battery():probes['battery']+=1;return {'percentage':resource['battery'],'plugged':False}
                    def source(sym,tf,cursor,end,limit):
                        nonlocal n
                        n+=1
                        if n==2:resource[case]=511 if case=='disk' else 4
                        if n>3:return {'rows':[],'next_cursor_ms':end}
                        stamp=start+(n-1)*60000
                        obs=parse_kline_to_observation(sym,tf,[stamp,'100','101','99','100','10',stamp+59999],n)
                        return {'rows':[obs],'next_cursor_ms':stamp+60000,'oi_available':False}
                    service=BS.BootstrapService(config=cfg,store=runtime.store,source=source,cells=[('BTCUSDT','1m')],checkpoint_path=d+f'/cp-{enabled}-{case}.sqlite')
                    await service.open();service.runner.command('continuous on')
                    queries=[]
                    await runtime.store.db.set_trace_callback(lambda q:queries.append(q) if q.lstrip().upper().startswith('SELECT') else None)
                    try:
                        with patch.object(BS,'free_disk_mb',disk),patch.object(BS,'read_battery',battery):
                            result=await service.run(start_ms=start,end_ms=start+4*60000,announce=False)
                            saved=await service._checkpoints.load_bootstrap('BTCUSDT:1m')
                            emit(case=case,device_indexes=enabled,status=result['status'],bars=result['bars_ingested'],
                                 source_calls=n,probe_counts=dict(probes),resource=resource,checkpoint=saved,
                                 refreshed_verdict=BS.hardware_preflight(free_disk_mb=resource['disk'],battery={'percentage':resource['battery'],'plugged':False},continuous=True))
                            assert result['bars_ingested']==3 and probes=={'disk':2,'battery':1}
                            # Same low-resource state at a new invocation is detected.
                            again=await service.run(start_ms=start,end_ms=start+5*60000,announce=False)
                            emit(case=case,reentry_status=again['status'],source_calls=n)
                            assert again['status']=='PAUSED' and n==4
                    finally:
                        await runtime.store.db.set_trace_callback(None);await service.close()
                    await plans(runtime.store.db,queries,f'{enabled}-{case}')
            emit(guard_blocked_attempts=SAFE['blocked']);assert not SAFE['blocked']
        finally:await runtime.stop()
    print('PASS: initial resource checks exist, mid-run changes are not sampled')
asyncio.run(main())
