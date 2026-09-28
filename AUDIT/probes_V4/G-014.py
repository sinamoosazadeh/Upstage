import asyncio
from signals_common import plane,Transport,message
from apex.bus import Priority
async def main():
 t=Transport(fail=3)
 p=plane(t)
 r=await p.send(message('outage',Priority.P0))
 print('first_sent=',r.sent,'transport_calls=',t.calls,'first_outbox=',p.outbox,'registry_size=',len(p.idempotency))
 fresh=plane(Transport())
 print('recreated_outbox=',fresh.outbox,'registry_size=',len(fresh.idempotency))
 print('outbox_has_restart_api=',hasattr(fresh,'replay_outbox'))
asyncio.run(main())
