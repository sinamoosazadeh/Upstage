"""Actual EventBus dispatcher, retained queue growth and slow-consumer latency."""
from perf_support import SAFE, emit
import asyncio, gc, time, tracemalloc
from apex.bus import EventBus, RawCandleQueue, make_event, Priority
from scripts.run_nfr_harness import _queue_bounds_probe

async def main():
    bus=EventBus(lane_maxsize=10)
    tracemalloc.start();base=tracemalloc.get_traced_memory()[0]
    for i in range(4000):
        await bus.publish(make_event(Priority.P1,'audit',{'i':i,'text':str(i)+'x'*1024}))
        if i+1 in (1000,2000,4000):
            gc.collect();emit(case='growth_without_dispatch',published=i+1,p1_qsize=bus._p1_lane.qsize(),
                p1_maxsize=bus._p1_lane.maxsize,shared_qsize=bus._shared_lane.qsize(),heap_delta=tracemalloc.get_traced_memory()[0]-base)
    tracemalloc.stop();assert bus._p1_lane.qsize()==4000
    del bus;gc.collect()
    bus=EventBus(lane_maxsize=10);seen=[];done=asyncio.Event();started=time.perf_counter()
    async def consumer(event):
        entry=time.perf_counter()-event.payload['sent']
        if event.priority==Priority.P1:await asyncio.sleep(.04)
        seen.append((int(event.priority),event.payload['i'],entry,time.perf_counter()-event.payload['sent']))
        if event.priority==Priority.P2:done.set()
    bus.subscribe('audit',consumer);bus.start()
    try:
        for i in range(75):
            await bus.publish(make_event(Priority.P1,'audit',{'i':i,'sent':time.perf_counter()}))
        emit(case='slow_dispatch_enqueued',p1=bus._p1_lane.qsize(),shared=bus._shared_lane.qsize())
        await bus.publish(make_event(Priority.P2,'audit',{'i':0,'sent':time.perf_counter()}))
        await asyncio.sleep(.005)
        t=time.perf_counter();await bus.publish(make_event(Priority.P0,'audit',{'i':0,'sent':t}));p0=time.perf_counter()-t
        await asyncio.wait_for(done.wait(),6)
        p1=[x for x in seen if x[0]==1];p2=[x for x in seen if x[0]==2]
        emit(case='slow_dispatch_complete',p1_delivered=len(p1),fifo=[x[1] for x in p1]==list(range(75)),
             max_p1_start_delay=max(x[2] for x in p1),max_p1_completion_delay=max(x[3] for x in p1),
             p1_start_over_2s=sum(x[2]>2 for x in p1),p0_publish_seconds=p0,p2_start_delay=p2[0][2],
             evictions=bus.counts['evicted'],wall_seconds=time.perf_counter()-started)
        assert len(p1)==75 and max(x[2] for x in p1)>2 and bus.counts['p0_delivered']==1
    finally:await bus.stop()
    shared=EventBus(lane_maxsize=10)
    for i in range(15):await shared.publish(make_event(Priority.P2,'audit',i))
    emit(case='shared_control',qsize=shared._shared_lane.qsize(),evicted=shared.counts['evicted'])
    feature=EventBus()
    for i in range(501):await feature.publish(make_event(Priority.P2,'feature.evidence',i))
    emit(case='generic_bus_feature_topic',queued=feature._shared_lane.qsize(),capacity=feature._shared_lane.maxsize,
         note='Not a claim that an independent feature queue is wired; generic bus does not enforce its 500-item contract')
    raw=RawCandleQueue()
    for i in range(1001):await raw.put(i,event_id=f'audit-{i}',topic='raw')
    emit(case='raw_control',qsize=raw.qsize(),oldest=await raw.get(),drops=len(raw.drop_log))
    result=await _queue_bounds_probe();emit(case='existing_native_nfr_queue_probe',result=result)
    assert result['bounded'] and result['all_p0_processed'] and result['some_p2_evicted']
    emit(guard_blocked_attempts=SAFE['blocked']);assert not SAFE['blocked']
    print('PASS: actual dispatcher exhibits P1 backlog/delay; existing queue probe still reports bounded shared lane')
asyncio.run(main())
