import asyncio
from signals_common import plane, message, Transport
from apex.bus import Priority
async def main():
    t=Transport(); p=plane(t)
    await asyncio.gather(*(p.send(message(i)) for i in range(20)))
    work=[asyncio.create_task(p.send(message(i+20))) for i in range(44)]
    await asyncio.sleep(0.02)
    urgent=await p.send(message(999,Priority.P0))
    await asyncio.gather(*work)
    print('urgent_queued=',urgent.queued,'urgent_delivery_seconds=',round(urgent.delivery_seconds,3),'transport_calls=',t.calls)
asyncio.run(main())
