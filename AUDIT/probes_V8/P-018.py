import json
from pathlib import Path
from apex.engines.e05_fvg.engine import FVGEngine,get_params
from apex.data_catalog.contracts import MarketObservation,validate_market_observation
from decimal import Decimal
f=json.loads(Path('tests/fixtures/e05_golden_fixtures.json').read_text())['fixtures']
x=next(v for v in f if v['name']=='VALID_BULL_CONVENTIONAL'); bars=[dict(b) for b in x['bars']]; i=x['i']
# Keep the gap shape but repair the fixture's open/low bound for this validated probe.
bars[2]['o']=103.0
for j,b in enumerate(bars):
    o=MarketObservation('BTCUSDT','1h',Decimal(str(b['o'])),Decimal(str(b['h'])),Decimal(str(b['l'])),Decimal(str(b['c'])),Decimal(str(b.get('v',100))),None,'2026-01-%02dT%02d:00:00.000Z'%(1+j//24,j%24),j+1,'CLOSED',availability_time='2026-01-%02dT%02d:00:00.000Z'%(1+j//24,j%24))
    validate_market_observation(o,prev_sequence=j if j else None)
for label,be in [('none',[]),('up',[{'dir':'UP','idx':i}]),('down',[{'dir':'DOWN','idx':i}])]:
    e=FVGEngine(get_params(),tick_size=.01,symbol='BTCUSDT')
    e.process_bar(bars,i,bos_events=be)
    obj=next(iter(e.active_fvgs.values()),None)
    print(label,'type=',obj.ftype if obj else None,'role=',obj.structural_role if obj else None,'salience0=',obj.salience_0 if obj else None)
print('validated_fixture_OHLC_count=',len(bars),'mtf_required_default=',get_params()['mtf_required'])
