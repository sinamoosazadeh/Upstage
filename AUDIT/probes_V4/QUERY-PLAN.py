"""Query plans on empty real schema, before/after the two device-only indexes."""
import asyncio
from common import scenario
QUERIES={
 'find_by_fill': ('SELECT ledger_id FROM ledger WHERE fill_id=?', ('f',)),
 'find_by_intent': ('SELECT ledger_id FROM ledger WHERE intent_id=? ORDER BY rowid', ('i',)),
 'read_ledger': ('SELECT ledger_id FROM ledger ORDER BY rowid',()),
 'head': ('SELECT payload_hash FROM ledger ORDER BY rowid DESC LIMIT 1',()),
 'trade_plans': ('SELECT proposal_id FROM trade_plan WHERE environment=? ORDER BY created_utc, proposal_id',('PAPER',)),
 'market_scope': ('SELECT observation_id FROM market_observation WHERE symbol=? AND timeframe=? AND open_time<=? ORDER BY open_time DESC LIMIT 1', ('BTCUSDT','1h','2026-01-01')),
 'pit_scope': ('SELECT snapshot_id FROM snapshot_pit WHERE source_state=? AND symbol_scope=? AND timeframe_scope=? AND as_of<=?',('VALID','BTCUSDT','1h','2026-01-01')),
}
async def main(store,w,path):
 for label in ('repository_DDL','with_device_indexes'):
    if label=='with_device_indexes':
        await store.db.execute('CREATE INDEX idx_mo_sym_tf_open ON market_observation(symbol,timeframe,open_time)')
        await store.db.execute('CREATE INDEX idx_pit_scope_asof ON snapshot_pit(source_state,symbol_scope,timeframe_scope,as_of)')
    print(label)
    for name,(q,args) in QUERIES.items():
        cur=await store.db.execute('EXPLAIN QUERY PLAN '+q,args)
        print(name,[tuple(row)[3] for row in await cur.fetchall()])
asyncio.run(scenario(main))
