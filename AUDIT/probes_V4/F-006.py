import asyncio
from common import scenario, FaultDB, count
async def main(store,w,path):
    w._db=FaultDB(store.db,'INSERT INTO ledger_audit')
    try: await w.append(event_type='A')
    except OSError as e: print('fault=',str(e))
    print('before_next=',await count(store.db,'ledger'),await count(store.db,'ledger_audit'),'head=',w.head)
    w._db=store.db
    await w.append(event_type='B')
    print('after_next=',await count(store.db,'ledger'),await count(store.db,'ledger_audit'),'chain=',await w.verify_chain())
asyncio.run(scenario(main))
