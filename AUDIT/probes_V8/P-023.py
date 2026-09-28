import json
from pathlib import Path
from apex.engines.e05_fvg.engine import FVGEngine,get_params
from decimal import Decimal
from apex.data_catalog.contracts import MarketObservation,validate_market_observation
x=next(v for v in json.loads(Path('tests/fixtures/e05_golden_fixtures.json').read_text())['fixtures'] if v['name']=='VALID_BULL_CONVENTIONAL')
bars=[dict(b) for b in x['bars']]; bars[2]['o']=103.
for j,b in enumerate(bars):
    t=f'2026-01-01T{j:02d}:00:00.000Z'
    obs=MarketObservation('BTCUSDT','1h',Decimal(str(b['o'])),Decimal(str(b['h'])),Decimal(str(b['l'])),Decimal(str(b['c'])),Decimal(str(b.get('v',100))),None,t,j+1,'CLOSED',availability_time=t)
    validate_market_observation(obs,prev_sequence=j if j else None)
p=get_params({'mtf_required':True}); e=FVGEngine(p,tick_size=.01,symbol='BTCUSDT')
ev=e.process_bar(bars,2,htf_fvgs=None)
print('validated_ohlc_bars=',len(bars),'mtf_required=',p['mtf_required'],'htf_fvgs=None','events=',[v['type'] for v in ev])
print('active_zones=',[(z.ftype,z.quality_tag,z.snapshot_id) for z in e.active_fvgs.values()])
