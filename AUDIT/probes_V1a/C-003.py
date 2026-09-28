"""C-003 real retention paths; timings and heap are synthetic, not phone RSS."""
from perf_support import *
import gc
import tracemalloc
from unittest.mock import patch

async def main():
    with tempfile.TemporaryDirectory(prefix='v1a-retention-') as directory:
        cfg=SAFE['config'](True); cfg._env['APEX_SQLITE_PATH']=directory+'/scratch.sqlite'
        runtime=await Runtime(cfg).start()
        try:
            # Seed without the bus's idle dispatcher consuming the measurement
            # thread's scheduling time; restore production bus before the soak.
            await runtime.bus.stop()
            await corpus(runtime)
            runtime.bus.start()
            producer=EC.EngineContextProducer(runtime.store,ledger=runtime.ledger,environment='PAPER')
            for enabled in (False,True):
                await indexes(runtime.store.db,enabled); q=[]
                await bounded(runtime.store.db,f'lineage_window_device_indexes={enabled}',lambda:producer.window('BTCUSDT','1m',ASOF,5000),q)
                await plans(runtime.store.db,q,f'device_indexes={enabled}')
                emit(device_indexes=enabled,raw_lineage=len(producer._raw_lineage),content_hash_cache=len(producer._content_hashes))
            await indexes(runtime.store.db,False)
            clock=C.FixtureClock(ASOF)
            driver=PL.PaperRuntime(config=cfg,store=runtime.store,ledger=runtime.ledger,
                                  bus=runtime.bus,clock=clock,environment='PAPER')
            async def no_public(due): return {'failures':[], 'quality_facts_written':0}
            driver._refresh_publishers=no_public
            # Actual run_cycle, Scheduler, cursor writes, bus delivery and
            # _plain copies. Handlers cannot submit orders or contact sources.
            async def no_order_stage(payload): return {'detail':'AUDIT_NO_ORDER_STAGE'}
            for name in C.PIPELINE_STAGES: driver.scheduler.register(name,no_order_stage)
            adapter=runtime.adapter()  # sessionless, synthetic credentials only
            def unavailable(*args,**kwargs):
                raise EC.BridgeError('AUDIT_MODEL_UNAVAILABLE','failure-path retention')
            tracemalloc.start(); gc.collect(); base=tracemalloc.get_traced_memory()[0]
            started=time.perf_counter()
            with patch.object(EC,'load_classifier',unavailable):
                for cycle in range(1,41):
                    # One calendar month per iteration makes all 140 TFs due.
                    clock.advance_to_next_close('1mo')
                    await driver.run_cycle()
                    for cell in driver.scheduler.cells:
                        try: await producer.prepare(cell.symbol,cell.timeframe,clock.utc_now())
                        except EC.BridgeError: pass
                    # Query only; missing session means zero socket activity.
                    for j in range(10): await adapter.query_open_positions(timestamp_utc=clock.utc_now(),nonce=f'{cycle}-{j}')
                    # Same real refusal-return branch, but no order submission:
                    # replace external submit work with a pre-submission refusal.
                    async def refused(*args,**kwargs): return {'reason':'AUDIT_PRE_SUBMISSION_REFUSAL'}
                    plan=__import__('types').SimpleNamespace(proposal_id=f'audit-{cycle}',symbol='BTCUSDT',
                          timeframe='1m',direction='LONG')
                    with patch.object(PL.F.ExecutionFSM,'submit',refused):
                        await driver.execute_plan(plan,price='100',timestamp_utc=clock.utc_now(),close_ms=clock.now_ms())
                    await asyncio.sleep(0)
                    if cycle in (10,20,40):
                        gc.collect(); current,peak=tracemalloc.get_traced_memory()
                        emit(cycles=len(driver.cycles),scheduler_runs=len(driver.scheduler.runs),events=len(runtime.events),
                            failed_contexts=len(producer._failed),ready_contexts=len(producer._ready),
                            raw_lineage=len(producer._raw_lineage),content_hash_cache=len(producer._content_hashes),
                            adapter_audit=len(adapter.audit_trail()),trades=len(driver.trades),refusals=len(driver.refusals),
                            heap_delta_bytes=current-base,peak_traced_bytes=peak,elapsed_seconds=time.perf_counter()-started)
            assert len(producer._failed)==5600 and len(driver.scheduler.runs)==5600
            assert len(driver.trades)==len(driver.refusals)==40
            assert len(adapter.audit_trail())==400
            assert len(producer._content_hashes)==4096 and len(producer._raw_lineage)==5000
            tracemalloc.stop()
            emit(guard_blocked_attempts=SAFE['blocked'])
            assert not SAFE['blocked']
        finally: await runtime.stop()
    print('PASS: surviving heap/containers increase after GC; success-context growth is separately static evidence')

asyncio.run(main())
