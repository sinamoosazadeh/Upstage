import asyncio
from common import scenario, count
import json
from apex.ledger.store import LEDGER_COLUMNS
from apex.identity.hashes import sha256_hex
from apex.identity.canonical_json import canonical_json
async def main(store,w,path):
    e=await w.append_fill(intent_id='i',fill_id='f',price='100',quantity='1',symbol='BTCUSDT',side='BUY_OPEN')
    try:
        await store.db.execute("UPDATE ledger SET quantity='9' WHERE ledger_id=?",(e.ledger_id,))
    except Exception as exc: print('trigger_reject=',str(exc))
    await store.db.execute('DROP TRIGGER ledger_no_update')
    await store.db.execute("UPDATE ledger SET quantity='9' WHERE ledger_id=?",(e.ledger_id,))
    await store.db.commit()
    print('modified_net=',(await w.positions_from_ledger())['BTCUSDT']['net_quantity'],'chain=',await w.verify_chain())
    raw=dict(e.raw)
    raw['ledger_id']='lg-synthetic-clone'
    raw['parent_ids']=[e.payload_hash]
    h=sha256_hex(canonical_json(raw))
    row=list(e.to_row())
    for key,value in {'ledger_id':'lg-synthetic-clone','payload_hash':h,
                      'parent_ids':json.dumps([e.payload_hash]),
                      'raw':canonical_json(raw)}.items():
        row[LEDGER_COLUMNS.index(key)]=value
    await store.db.execute('INSERT INTO ledger ('+','.join(LEDGER_COLUMNS)+') VALUES ('+','.join('?'*len(row))+')',row)
    await store.db.commit()
    print('after_direct_insert=',await w.verify_chain(),
          'ledger=',await count(store.db,'ledger'),'audits=',await count(store.db,'ledger_audit'))
asyncio.run(scenario(main))
