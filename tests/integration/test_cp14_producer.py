"""Real SQLite/native-engine G1 proof. No runtime classifier or context fixture.

OHLCV and unsigned venue responses are test inputs. The test-only classifier
is loaded through the production loader; it is NOT training/fallback evidence.
"""
import asyncio
import copy
import math
import random
from decimal import Decimal
from dataclasses import fields, replace
from pathlib import Path
import pytest
from apex.ops import engine_context as E
from apex.ops.plan_bridge import PaperPlanBridge, BridgeError, REQUIRED_CONTEXT_KEYS, REQUIRED_RISK_KEYS
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.data_catalog.contracts import MarketObservation, EvidenceEvent
from apex.ledger.store import LedgerWriter
from apex.quality.vector import QualityFlags
from apex.risk.kernel import apply_ladder_state_migration, append_ladder_revision, ladder_revision
from tests.unit.test_engine_context import _PublicFactsFixture, FIXTURE

ASOF = "2026-01-08T00:00:00.001Z"

def raw_observations():
    base=E._iso_to_ms("2026-01-08T00:00:00.000Z")-120*86400000
    tail=[(107,108,106,107),(106,107,105,106),(104,105,103,104),(101,102,100,101),(96,97,95,96),
     (93,94,91,92),(90,91,87,90),(91,92,90,91),(92,93,91,92),(91,92,90,91),
     (90,91,87.05,90),(100,101,99,100),(100,101,99.5,100),(95,96,94,95),(91.5,92,91,91.5),(91.5,94.5,86,94)]
    rng=random.Random(0);bars=[];p=80.
    for i in range(120-len(tail)):
     o=p;p=80+i*.26+math.sin(i*.55)*.3
     bars.append((o,max(o,p)+rng.uniform(.1,.8),min(o,p)-rng.uniform(.1,.8),p))
    bars+=tail
    raw=[MarketObservation('BTCUSDT','1d',*[Decimal(str(v)) for v in b],Decimal(str(1000+300*math.sin(i))),Decimal(str(10000+70*i+100*math.sin(i))),E._ms_to_iso(base+i*86400000),i,'CLOSED',availability_time='1970-01-01T00:00:00.000Z',oi_timestamp=E._ms_to_iso(base+(i+1)*86400000)) for i,b in enumerate(bars)]
    return raw

async def seed(path, artifact):
 store=await SQLiteStore(path).open();ledger=LedgerWriter(store,clock=lambda:'2026-01-01T00:00:00.000Z');await ledger.initialize();await ledger.start()
 try:
  source=E.EngineContextProducer(store,ledger=ledger,classifier_path=artifact,environment='PAPER')
  end=E._iso_to_ms('2026-01-08T00:00:00.000Z');base=end-120*86400000
  raw=raw_observations()
  async def ingest(obs, quality=False):
   await store.ingest_raw(obs,oi_state='AVAILABLE')
   if quality:
    receipt=E.close_time_ms(E._iso_to_ms(obs.timestamp),obs.timeframe)+1
    await E.publish_quality_observation(store,obs,flags=QualityFlags(True,True,False,True,True),measurements={'source_health':.95,'gap_count':0,'expected_count':1,'completeness_pct':100.},receipt_time_ms=receipt,measured_at=E._ms_to_iso(receipt),measurement_source='G1-native-fixture-observed')
  for obs in raw:
   await ingest(obs, True)
  for tf,step in [('15m',900000),('1h',3600000),('4h',14400000)]:
   for i in range(70):
    stamp=base-(70-i)*step;p=70+.1*i+math.sin(i)*.3
    obs=MarketObservation('BTCUSDT',tf,*[Decimal(str(x)) for x in (p,p+1,p-1,p+.2,1000+200*math.sin(i),10000+10*i)],E._ms_to_iso(stamp),i,'CLOSED',availability_time='1970-01-01T00:00:00.000Z',oi_timestamp=E._ms_to_iso(stamp+step))
    await ingest(obs)
  stamp=E._iso_to_ms('2020-03-01T00:00:00.000Z');i=0
  while stamp < E._iso_to_ms('2026-01-01T00:00:00.000Z'):
   p=70+.1*i+math.sin(i)*.3;close=E.close_time_ms(stamp,'1mo')
   await ingest(MarketObservation('BTCUSDT','1mo',*[Decimal(str(x)) for x in (p,p+1,p-1,p+.2,1000+200*math.sin(i),10000+10*i)],E._ms_to_iso(stamp),i,'CLOSED',availability_time='1970-01-01T00:00:00.000Z',oi_timestamp=E._ms_to_iso(close)),True)
   stamp=close;i+=1
  for i in range(31*24):
   stamp=end-31*86400000+i*3600000;p=90+.01*i+math.sin(i)*.3
   await ingest(MarketObservation('BTCUSDT','1h',*[Decimal(str(x)) for x in (p,p+1,p-1,p+.2,1000+200*math.sin(i),10000+10*i)],E._ms_to_iso(stamp),1000+i,'CLOSED',availability_time='1970-01-01T00:00:00.000Z',oi_timestamp=E._ms_to_iso(stamp+3600000)))
  venue=_PublicFactsFixture();venue.record['volumeUnit']='BASE';venue.funding_schedule={'fundingIntervalHours':'4','nextFundingTime':str(end+14400000)}
  now=lambda:E._iso_to_ms('2026-01-01T00:00:00.000Z')/1000
  await E.persist_public_venue_facts(store,'BTCUSDT',environment='PAPER',client=venue.client,now=now)
  await E.persist_public_funding_schedule(store,'BTCUSDT',client=venue.client,now=now)
  await apply_ladder_state_migration(store.db)
  await append_ladder_revision(store.db,ladder_revision(revision_id='fixture-native-ladder',applied_at='2026-01-01T00:00:00.000Z',state='NoRisk',emergency_state='NORMAL',consumed_budget=0,reason='verified empty fixture account',snapshot_id='fixture-empty-ledger'))
  with pytest.raises(BridgeError, match="UNCERTAINTY_TREND_UNAVAILABLE"):
   await source.get_bridge_context('BTCUSDT','1d','2026-01-07T00:00:00.001Z')
  ctx=await source.get_bridge_context('BTCUSDT','1d',ASOF)
  assert len(ctx)==38 and len(ctx['risk'])==23
  assert E.canonical_json(ctx)==E.canonical_json(await source.get_bridge_context('BTCUSDT','1d',ASOF))
  return ctx
 finally:await ledger.stop();await store.close()

@pytest.fixture(scope="module")
def real_context(tmp_path_factory):
    folder=tmp_path_factory.mktemp("producer")
    artifact=E.load_classifier(FIXTURE)
    # Fixture only: native low-entropy admission, not synthetic training members.
    artifact['b'][0]=8.
    artifact['artifact_sha256']=E.classifier_hash(artifact['W'],artifact['b'],artifact['seed'])
    classifier=folder/'loader-fixture.yaml'
    E.write_classifier(artifact,classifier)
    path=folder/'source.sqlite'
    phase={"active":False}; calls=[]; batches=[]
    patch=pytest.MonkeyPatch()
    complete=E.complete_engine_bundle
    def bundle(*args,**kwargs):
        phase['active']=True; calls.clear()
        try:
            result=complete(*args,**kwargs)
            batches.append(tuple(calls))
            return result
        finally: phase['active']=False
    patch.setattr(E,'complete_engine_bundle',bundle)
    for code,cls in (("E01",E.E01.E01StructureEngine),("E02",E.E02.E02LiquidityEngine),
                     ("E12",E.E12.E12TemporalEngine),("E03",E.E03.E03VolumeEngine),
                     ("E09",E.E09.E09TrendEngine),("E06",E.E06.E06OrderBlockEngine),
                     ("E11",E.E11.E11RegimeEngine),("E07",E.E07.E07RTMEngine),
                     ("E08",E.E08.E08WyckoffEngine)):
        original=cls.compute
        def tracked(self,*args,_code=code,_original=original,**kwargs):
            if phase['active']: calls.append(_code)
            return _original(self,*args,**kwargs)
        patch.setattr(cls,'compute',tracked)
    fvg=E.E05.run_engine
    def tracked_fvg(*args,**kwargs):
        if phase['active']: calls.append('E05')
        return fvg(*args,**kwargs)
    patch.setattr(E.E05,'run_engine',tracked_fvg)
    for code,cls in (("E04",E.E04.E04VolatilityEngine),("E10",E.E10.E10MomentumEngine)):
        original=cls._window_quality
        def tracked(window,_code=code,_original=original):
            if phase['active']: calls.append(_code)
            return _original(window)
        patch.setattr(cls,'_window_quality',staticmethod(tracked))
    try: context=asyncio.run(seed(str(path),classifier))
    finally: patch.undo()
    return path,classifier,context,batches

async def reopened(real_context, operation):
    path,classifier,context,_=real_context
    store=await SQLiteStore(str(path)).open()
    ledger=LedgerWriter(store);await ledger.initialize();await ledger.start()
    try:
        source=E.EngineContextProducer(store,ledger=ledger,classifier_path=classifier,environment='PAPER')
        return await operation(store,source,context)
    finally: await ledger.stop();await store.close()

def test_g1_exact_38_23_and_unchanged_native_validators(real_context):
    context=real_context[2]
    assert set(context)==set(REQUIRED_CONTEXT_KEYS)
    assert set(context['risk'])==set(REQUIRED_RISK_KEYS)
    E.validate_produced_context(context)
    for event in context['events']: event.validate_24_fields()
    for key in REQUIRED_CONTEXT_KEYS:
        altered=copy.deepcopy(context);altered[key]=None
        with pytest.raises(BridgeError): E.validate_produced_context(altered)
    for key in REQUIRED_RISK_KEYS:
        altered=copy.deepcopy(context);altered['risk'][key]=None
        with pytest.raises(BridgeError): E.validate_produced_context(altered)

def test_g1_full_24_field_public_store_readback_every_emitter(real_context):
    async def check(store,source,context):
        restored=await E.read_complete_evidence(store,[e.evidence_id for e in context['events']])
        assert {e.engine_id for e in restored}=={e.engine_id for e in context['events']}
        assert {e.engine_id for e in restored}=={'E01','E02','E03','E04','E05','E09','E11','E12'}
        # Native E06/E07/E08/E10 emit no event for these observations; they
        # still execute in the measured order. No placeholder members.
        assert len(fields(EvidenceEvent))==24
        for before,after in zip(context['events'],restored):
            for field in fields(EvidenceEvent):
                assert getattr(before,field.name)==getattr(after,field.name)
    asyncio.run(reopened(real_context,check))

def test_g1_actual_twelve_native_call_order(real_context):
    assert real_context[3]==[E.ENGINE_ORDER,E.ENGINE_ORDER]

def test_g1_canonical_json_twice_same_asof_and_cold_recovery(real_context):
    async def check(store,source,context):
        a=await source.get_bridge_context('BTCUSDT','1d',ASOF)
        await source.prepare('BTCUSDT','1d',ASOF)
        b=await source.get_bridge_context('BTCUSDT','1d',ASOF)
        assert E.canonical_json(a)==E.canonical_json(b)==E.canonical_json(context)
    asyncio.run(reopened(real_context,check))

def test_g1_pit_late_available_bar_excluded(real_context,tmp_path):
    import shutil
    path,classifier,context,batches=real_context
    isolated=tmp_path/'late.sqlite';shutil.copyfile(path,isolated)
    async def check(store,source,context):
        before=await source.window('BTCUSDT','1d',ASOF,300)
        late=replace(raw_observations()[-1],timestamp='2026-01-08T00:00:00.000Z',
                     availability_time='2026-01-10T00:00:00.000Z',sequence=1001)
        await store.ingest_raw(late,oi_state='AVAILABLE')
        after=await source.window('BTCUSDT','1d',ASOF,300)
        assert before==after
        assert E.canonical_json(await source.get_bridge_context('BTCUSDT','1d',ASOF))==E.canonical_json(context)
    asyncio.run(reopened((isolated,classifier,context,batches),check))

def test_g1_real_bridge_consumes_context_without_fabricated_plan(real_context):
    async def check(store,source,context):
        bridge=PaperPlanBridge(store=store,environment='PAPER',context_source=source.get_bridge_context)
        result=await bridge('BTCUSDT','1d',ASOF)
        assert result is None
        assert bridge.refusals['BTCUSDT:1d']['reason']=='SETUP_NOT_EMITTED'
        assert 'GATE5_MTF_CONFLICTING' in bridge.refusals['BTCUSDT:1d']['detail']
    asyncio.run(reopened(real_context,check))

def test_g1_missing_classifier_and_scope_are_named_refusals(real_context,tmp_path):
    async def check(store,source,context):
        source.classifier_path=tmp_path/'absent.yaml'
        bridge=PaperPlanBridge(store=store,environment='PAPER',context_source=source.get_bridge_context)
        assert await bridge('BTCUSDT','1d',ASOF) is None
        assert bridge.refusals['BTCUSDT:1d']['reason']=='CONFIGURATION_INVALID'
        with pytest.raises(BridgeError,match='CELL_OUT_OF_UNIVERSE'):
            await source.prepare('UNKNOWN','1d',ASOF)
        source.environment='LIVE'
        with pytest.raises(BridgeError,match='PAPER_ONLY_EXECUTION'):
            await source.prepare('BTCUSDT','1d',ASOF)
    asyncio.run(reopened(real_context,check))


def test_bound_producer_existing_paper_loop_one_cycle_json(real_context,monkeypatch):
    import json
    from apex.bus import EventBus
    from apex.config import Config
    from apex.ops.bootstrap_service import BootstrapService
    from apex.ops.paper_loop import PaperRuntime
    from apex.scheduler.clock import FixtureClock, BundleCell
    from tests.integration.test_ops_paper_loop import FakeAdapter
    monkeypatch.setenv('APEX_ENV','PAPER')
    monkeypatch.setenv('APEX_ALLOW_SIGNED','1')
    class EmptyVenuePage:
        # Native catch-up, an already-caught-up real fixture store.
        def begin_catch_up(self,symbol,timeframe,frontier):
            assert frontier==E._iso_to_ms('2026-01-07T00:00:00.000Z')
        def __call__(self,symbol,timeframe,start,end,limit):
            return {'rows':[],'next_cursor_ms':end,'code':None}
    async def check(store,source,context):
        service=BootstrapService(config=Config(),store=store,source=EmptyVenuePage(),
                                 cells=[('BTCUSDT','1d')])
        bus=EventBus();bus.start();notices=[]
        async def telegram_stub(text): notices.append(text);return {'sent':True}
        bridge=PaperPlanBridge(store=store,environment='PAPER',context_source=source.get_bridge_context,
                               context_preparer=source.prepare)
        runtime=PaperRuntime(config=Config(),store=store,ledger=source.ledger,bus=bus,
            adapter=FakeAdapter(),clock=FixtureClock(ASOF),environment='PAPER',
            cells=[BundleCell('BTCUSDT','1d')],notifier=telegram_stub,
            plan_provider=bridge,catch_up=service.catch_up)
        try:
            await runtime.boot(drift_seconds=0.)
            await runtime.run(cycles=1,interval=0)
            cycle=json.loads(json.dumps(runtime.cycles[-1],default=str))
            assert cycle['catch_up']['cells_checked']==1
            assert cycle['catch_up']['failures']==[]
            assert cycle['context_preparation']['cells_prepared']==1
            assert cycle['decision_as_of']['BTCUSDT:1d']==ASOF
            assert cycle['halt_reasons']=={'SETUP_NOT_EMITTED':1}
            assert cycle['cell_runs']
            assert notices
            print(json.dumps(cycle,sort_keys=True))
        finally:
            await service.close();await bus.stop()
    asyncio.run(reopened(real_context,check))
