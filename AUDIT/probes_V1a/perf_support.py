"""Offline native-DDL synthetic corpus. No source/AST substitutions."""
import runpy
from pathlib import Path
SAFE = runpy.run_path(str(Path(__file__).with_name('C-002.py')))
import asyncio
import datetime as dt
import hashlib
import json
import tempfile
import time
from decimal import Decimal
from apex.data_catalog.contracts import MarketObservation, CORE10_SYMBOLS
from scripts.run_apex import Runtime
from apex.ops import engine_context as EC
from apex.ops import paper_loop as PL
from apex.scheduler import clock as C

ASOF = '2026-09-28T00:00:00.000Z'
N = 200_000

def emit(**kw):
    print(json.dumps(kw, sort_keys=True), flush=True)

async def corpus(runtime):
    """Bulk seed performance fixture, NOT a production ingestion benchmark.
    The real store open/ledger initialize applies all repository DDL. Native
    content_hash values preserve window's actual lineage validation.
    """
    db = runtime.store.db
    start = time.perf_counter()
    base = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)
    for offset in range(0, N, 2000):
        market, raw = [], []
        for i in range(offset, min(offset+2000, N)):
            symbol = CORE10_SYMBOLS[i % 10]
            tf = '1m' if (i // 10) % 2 == 0 else '1h'
            seq = i // 20
            seconds = 60 if tf == '1m' else 3600
            stamp = (base + dt.timedelta(seconds=seq*seconds)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
            receipt = (base + dt.timedelta(seconds=(seq+1)*seconds)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
            obs = MarketObservation(symbol=symbol, timeframe=tf, open=Decimal('100'), high=Decimal('101'),
                low=Decimal('99'), close=Decimal('100'), volume=Decimal('10'), oi=None,
                timestamp=stamp, sequence=seq, status='CLOSED', availability_time=receipt)
            digest = obs.content_hash()
            eid = f'audit-{i}'
            raw.append((eid,stamp,symbol,tf,'100','101','99','100','10',None,None,'MISSING','CLOSED',digest,'TOOBIT',receipt,receipt))
            market.append(('obs-'+eid,symbol,tf,'100','101','99','100','10','MISSING',stamp,receipt,receipt,'CLOSED','Q2','TOOBIT','4.0.0',hashlib.sha256(digest.encode()).hexdigest()))
        await db.executemany('INSERT INTO raw_observation(event_id,as_of,symbol,timeframe,open,high,low,close,volume,oi,oi_timestamp,oi_state,status,content_hash,source,availability_time,created_at) VALUES ('+','.join('?'*17)+')',raw)
        await db.executemany('INSERT INTO market_observation VALUES ('+','.join('?'*17)+')',market)
    await db.executemany('INSERT INTO snapshot_pit(snapshot_id,as_of,symbol_scope,timeframe_scope,source_state) VALUES (?,?,?,?,?)',
        [(f'fact-{i}',ASOF,'BTCUSDT','1m','AUDIT_SYNTHETIC') for i in range(1000)])
    await db.commit()
    for i in range(100):
        await runtime.ledger.append(event_type='AUDIT_SYNTHETIC', timestamp=ASOF, ordinal=i)
    emit(corpus_market_rows=(await (await db.execute('SELECT COUNT(*) FROM market_observation')).fetchone())[0],
         corpus_raw_rows=(await (await db.execute('SELECT COUNT(*) FROM raw_observation')).fetchone())[0],
         facts=1000,ledger_rows=100,seed_seconds=time.perf_counter()-start)

async def indexes(db, enabled):
    for name in ('idx_mo_sym_tf_open','idx_pit_scope_asof'):
        await db.execute('DROP INDEX IF EXISTS '+name)
    if enabled:
        await db.execute('CREATE INDEX idx_mo_sym_tf_open ON market_observation(symbol,timeframe,open_time)')
        await db.execute('CREATE INDEX idx_pit_scope_asof ON snapshot_pit(source_state,symbol_scope,timeframe_scope,as_of)')
    await db.commit()

async def bounded(db, label, operation, queries, seconds=2.0):
    start=time.perf_counter()
    await db.set_trace_callback(lambda sql: queries.append(sql) if sql.lstrip().upper().startswith('SELECT') else None)
    await db.set_progress_handler(lambda: int(time.perf_counter()-start >= seconds), 10000)
    try:
        result = await operation()
        emit(operation=label,status='COMPLETE',seconds=time.perf_counter()-start,
             result_length=len(result) if hasattr(result,'__len__') else None)
    except Exception as exc:
        emit(operation=label,status=type(exc).__name__,detail=str(exc),seconds=time.perf_counter()-start,
             bound_seconds=seconds)
    finally:
        await db.set_progress_handler(None,0)
        await db.set_trace_callback(None)

async def plans(db, queries, label):
    for sql in dict.fromkeys(queries):
        rows = await (await db.execute('EXPLAIN QUERY PLAN '+sql)).fetchall()
        emit(plan_group=label,sql=sql,plan=rows)
