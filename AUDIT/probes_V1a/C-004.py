"""Native scheduler/cursor gap and post-work sleep probe, 200k-row store."""
from perf_support import *

async def driver_for(runtime, clock):
    driver=PL.PaperRuntime(config=runtime.cfg,store=runtime.store,ledger=runtime.ledger,
        clock=clock,environment='PAPER',cells=[C.BundleCell('BTCUSDT','1m')])
    async def no_public(due): return {'failures':[], 'quality_facts_written':0}
    driver._refresh_publishers=no_public
    async def no_order(payload): return {'detail':'AUDIT_NO_ORDER_STAGE'}
    # Keep native ingest/get_window. All downstream analytical/order work is
    # explicitly inert; claim concerns selection and persistence, not signals.
    for name in C.PIPELINE_STAGES:
        if name != 'ingest': driver.scheduler.register(name,no_order)
    return driver

async def main():
    with tempfile.TemporaryDirectory(prefix='v1a-closes-') as directory:
        cfg=SAFE['config'](False);cfg._env['APEX_SQLITE_PATH']=directory+'/scratch.sqlite'
        runtime=await Runtime(cfg).start()
        try:
            await runtime.bus.stop();await corpus(runtime)
            await PL.apply_cell_cursor_migration(runtime.store.db)
            for enabled in (False,True):
                await indexes(runtime.store.db,enabled)
                await runtime.store.db.execute('DELETE FROM cell_decision_cursor');await runtime.store.db.commit()
                clock=C.FixtureClock('2020-01-01T00:01:00.000Z');base=clock.now_ms()-60000
                driver=await driver_for(runtime,clock)
                captured=[]
                await runtime.store.db.set_trace_callback(lambda sql:captured.append(sql) if sql.lstrip().upper().startswith('SELECT') else None)
                start=time.perf_counter()
                await driver.run_cycle()
                clock.advance(180)
                await driver.run_cycle()
                cursor=await PL.load_cell_cursor(runtime.store.db)
                closed=[(r.close_ms-base)//60000 for r in driver.scheduler.runs]
                # A fresh runtime sees the same durable maximum and cannot
                # recover skipped 2/3 by simply restarting at minute four.
                fresh=await driver_for(runtime,clock)
                replay=await fresh.run_cycle()
                await runtime.store.db.set_trace_callback(None)
                emit(device_indexes=enabled,selected_minutes=closed,durable_cursor_minute=(cursor['BTCUSDT:1m']-base)//60000,
                     restart_due=replay['cells_due'],restart_skipped=replay['cells_skipped_already_decided'],
                     elapsed_seconds=time.perf_counter()-start)
                assert closed==[1,4] and replay['cells_due']==0
                await plans(runtime.store.db,captured,f'device_indexes={enabled}')
            await runtime.store.db.execute('DELETE FROM cell_decision_cursor');await runtime.store.db.commit()
            clock=C.FixtureClock('2020-01-01T00:05:00.000Z');base=clock.now_ms()-5*60000
            driver=await driver_for(runtime,clock); timeline=[];start=time.perf_counter()
            async def work(now):
                timeline.append(('work_start',time.perf_counter()-start))
                await asyncio.sleep(.08);clock.advance(120)
                timeline.append(('work_end',time.perf_counter()-start))
                return {'failures':[], 'cells_checked':1,'cells_updated':0,'bars_ingested':0}
            async def waiter(seconds):
                timeline.append(('sleep_start',time.perf_counter()-start,seconds))
                await asyncio.sleep(seconds);clock.advance(60)
                timeline.append(('sleep_end',time.perf_counter()-start))
            driver.catch_up=work
            await driver.run(cycles=2,interval=.05,sleep=waiter)
            selected=[(r.close_ms-base)//60000 for r in driver.scheduler.runs]
            emit(case='work_plus_post_cycle_sleep',selected_minutes=selected,timeline=timeline,wall_seconds=time.perf_counter()-start)
            assert selected==[5,8]
            # D53 calendar control, actual native helpers (not 30-day month).
            m=C.FixtureClock('2026-01-01T00:00:00.000Z');sched=C.Scheduler(clock=m,cells=[C.BundleCell('BTCUSDT','1mo')])
            first=sched.due_cells()[0][1];m.advance_to('2026-04-01T00:00:00.000Z');last=sched.due_cells()[0][1]
            enum=C.tf_close_times('1mo',start_ms=first,end_ms=last+1)
            emit(calendar_selected=[C._ms_to_iso(first),C._ms_to_iso(last)],calendar_all_closes=[C._ms_to_iso(x) for x in enum])
            assert len(enum)==4
            emit(guard_blocked_attempts=SAFE['blocked']);assert not SAFE['blocked']
        finally:await runtime.stop()
    print('PASS: missing intermediate decisions persist across restart, independent of market/PIT indexes')

asyncio.run(main())
