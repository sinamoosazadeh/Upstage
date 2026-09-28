import asyncio
from unittest.mock import patch
from common import scenario
import apex.identity.uuid_v7 as u
from apex.ledger import store as ls
async def main(store,w,path):
    with patch.object(u.time,'time',return_value=1780000000.123),patch.object(u.secrets,'randbits',side_effect=[4095,(1<<62)-1,0,0]):
        a,b=u.uuid_v7(),u.uuid_v7()
    print('uuid_a=',a,'uuid_b=',b,'strictly_ascending=',a<b)
    # Save deterministic event-id sequence using the actual writer (UUID source only patched).
    with patch.object(ls,'uuid_v7',side_effect=['01a0e8b2-585d-7fff-bfff-ffffffffffff','01a0e8b2-585d-7001-8000-000000000001','01a0e8b2-585d-7002-8000-000000000002','01a0e8b2-585d-7000-8000-000000000000','01a0e8b2-585d-7003-8000-000000000003','01a0e8b2-585d-7004-8000-000000000004']):
        try:
            await w.append(event_type='FIRST',timestamp='2026-01-01T00:00:00.000Z')
            await w.append(event_type='SECOND',timestamp='2026-01-01T00:00:00.000Z')
        except Exception as e: print('writer_probe_error=',type(e).__name__,str(e))
    print('stored_event_ids=',[e.event_id for e in await w.read_ledger()])
    print('verification=',await w.verify_chain())
asyncio.run(scenario(main))
