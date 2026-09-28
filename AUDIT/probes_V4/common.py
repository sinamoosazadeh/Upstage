"""Read-only verifier fixtures: repository DDL, temporary SQLite, no data/, network or credentials."""
import asyncio
import tempfile
from pathlib import Path
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.ledger.store import LedgerWriter

class FaultDB:
    def __init__(self, real, token):
        self.real, self.token, self.hit = real, token, False
    def __getattr__(self, key):
        return getattr(self.real, key)
    async def execute(self, sql, parameters=None):
        if not self.hit and self.token in sql:
            self.hit = True
            raise OSError('INJECTED_' + self.token)
        return await self.real.execute(sql, parameters or ())

async def scenario(body):
    with tempfile.TemporaryDirectory(prefix='apex_verify_v4_') as d:
        path = str(Path(d)/'fixture.sqlite3')
        store = SQLiteStore(path)
        await store.open()
        writer = LedgerWriter(store)
        await writer.initialize()
        await writer.start()
        try:
            await body(store, writer, path)
        finally:
            if not writer.closed:
                await writer.stop()
            await store.close()

async def count(db, table):
    cur = await db.execute('SELECT count(*) FROM ' + table)
    return (await cur.fetchone())[0]
