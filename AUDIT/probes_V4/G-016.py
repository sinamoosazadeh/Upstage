import asyncio
from signals_common import plane, message, Transport
class Barrier(Transport):
    def __init__(self):
        super().__init__()
        self.started=asyncio.Event()
        self.release=asyncio.Event()
    async def send_message(self, **kwargs):
        self.calls+=1
        if self.calls==2: self.started.set()
        await self.release.wait()
        return {'message_id':str(self.calls)}
async def main():
    t=Barrier(); p=plane(t); msg=message(1)
    tasks=[asyncio.create_task(p.send(msg)) for _ in range(2)]
    await asyncio.wait_for(t.started.wait(),2)
    print('transport_calls_before_release=',t.calls)
    t.release.set()
    r=await asyncio.gather(*tasks)
    print('sent_results=',[v.sent for v in r],'key_count=',len(p.idempotency._keys) if hasattr(p.idempotency,'_keys') else 'see registry')
asyncio.run(main())
