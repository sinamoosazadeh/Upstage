"""C-006 native scheduling + native producer SQL at 200k rows; offline."""
from perf_support import *
from unittest.mock import patch
from types import SimpleNamespace

async def scheduling(runtime, mode):
    # Seams are external work, not copied/reimplemented run_cycle logic.
    timeline=[]; start=time.perf_counter(); gate=asyncio.Event()
    def note(name): timeline.append((name,round(time.perf_counter()-start,6)))
    async def catchup(now):
        note('catchup_start'); await asyncio.sleep(.04); note('catchup_end')
        return {'failures': [], 'cells_checked':2,'cells_updated':0,'bars_ingested':0}
    async def poll(): note('gateway_poll'); return {}
    def heartbeat(): note('heartbeat'); return {}
    async def prepare(s,t,a):
        note('prepare_start:'+s)
        if mode=='stuck': await gate.wait()
        else: await asyncio.sleep(.12)
        note('prepare_end:'+s)
    provider=SimpleNamespace(prepare=prepare)
    driver=PL.PaperRuntime(config=runtime.cfg, store=runtime.store, ledger=runtime.ledger,
        clock=C.FixtureClock(ASOF), environment='PAPER', plan_provider=provider, catch_up=catchup,
        gateway=SimpleNamespace(run_once=poll),watchdog=SimpleNamespace(heartbeat=heartbeat),
        cells=[C.BundleCell('BTCUSDT','1m'),C.BundleCell('ETHUSDT','1m')])
    async def no_public(due): return {'failures':[], 'quality_facts_written':0}
    driver._refresh_publishers=no_public  # explicitly no public HTTP work
    real_manage=driver.manage_positions
    async def observe_manage(**kw): note('manage_positions'); return await real_manage(**kw)
    driver.manage_positions=observe_manage
    async def stage(payload):
        if payload['stage']=='ingest':
            note('stage_start:'+payload['symbol'])
            if mode=='gather' and payload['symbol']=='ETHUSDT': await gate.wait()
        return {'detail':'AUDIT_NO_ORDER_STAGE'}
    for name in C.PIPELINE_STAGES: driver.scheduler.register(name,stage)
    await runtime.store.db.execute('DELETE FROM cell_decision_cursor')
    await runtime.store.db.commit()
    task=asyncio.create_task(driver.run_cycle())
    if mode in ('stuck','gather'):
        await asyncio.sleep(.55)
        cursor_count=(await (await runtime.store.db.execute('SELECT COUNT(*) FROM cell_decision_cursor')).fetchone())[0]
        emit(case=mode,sampled_after_seconds=time.perf_counter()-start,task_done=task.done(),
             scheduler_runs=len(driver.scheduler.runs),durable_cursor_rows=cursor_count,
             completed_cycles=len(driver.cycles),timeline=timeline)
        if mode=='stuck':
            assert not task.done() and not any(n=='manage_positions' for n,_ in timeline)
            task.cancel()
            try: await task
            except asyncio.CancelledError: pass
        else:
            assert len(driver.scheduler.runs)==1 and cursor_count==0
            gate.set(); await task
    else:
        await task
        emit(case=mode,wall_seconds=time.perf_counter()-start,timeline=timeline,
             cell_stage_ms=[sum(s.finished_ms-s.started_ms for s in r.stages) for r in driver.scheduler.runs])
        assert next(v for n,v in timeline if n=='manage_positions') >= .24
    assert sum(n=='gateway_poll' for n,_ in timeline)==1

async def main():
    import sqlite3
    emit(sqlite=sqlite3.sqlite_version,N=N,scope='synthetic performance only, no device/model acceptance')
    with tempfile.TemporaryDirectory(prefix='v1a-perf-') as directory:
        cfg=SAFE['config'](False); cfg._env['APEX_SQLITE_PATH']=directory+'/scratch.sqlite'
        runtime=await Runtime(cfg).start()
        try:
            producer=EC.EngineContextProducer(runtime.store,ledger=runtime.ledger,environment='PAPER')
            # Capture every SQL in the actual fingerprint on the empty store,
            # before a large first-query timeout can hide subsequent statements.
            captured=[]
            with patch.object(EC,'load_classifier',return_value={'artifact_sha256':'AUDIT_METADATA_ONLY'}):
                await bounded(runtime.store.db,'fingerprint_empty_capture',lambda:producer._input_fingerprint('BTCUSDT','1m',ASOF),captured)
                await corpus(runtime)
                for enabled in (False,True):
                    await indexes(runtime.store.db,enabled)
                    q=list(captured)
                    await bounded(runtime.store.db,f'fingerprint_device_indexes={enabled}',lambda:producer._input_fingerprint('BTCUSDT','1m',ASOF),q)
                    await bounded(runtime.store.db,f'window300_device_indexes={enabled}',lambda:producer.window('BTCUSDT','1m',ASOF,300),q)
                    await plans(runtime.store.db,q,f'device_indexes={enabled}')
            await PL.apply_cell_cursor_migration(runtime.store.db)
            for mode in ('slow','stuck','gather'): await scheduling(runtime,mode)
            emit(guard_blocked_attempts=SAFE['blocked'])
            assert not SAFE['blocked']
        finally: await runtime.stop()
    print('PASS: measured serial delay/stall/gather barrier; SQL timings may be lower bounds when interrupted')

asyncio.run(main())
