import asyncio
from common import scenario
async def main(store,w,path):
    await w.append(event_type='SEED')
    await w.append(event_type='DERIVED',parents=('ev-00000000-0000-7000-8000-000000000000',))
    print('orphan_accepted=',await w.verify_chain())
asyncio.run(scenario(main))
