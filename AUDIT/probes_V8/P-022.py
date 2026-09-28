import json
from pathlib import Path
from decimal import Decimal
from apex.data_catalog.contracts import MarketObservation,validate_market_observation
from apex.engines.e05_fvg.engine import FVGEngine,get_params
x=next(v for v in json.loads(Path('tests/fixtures/e05_golden_fixtures.json').read_text())['fixtures'] if v['name']=='VALID_BULL_CONVENTIONAL')
xs=[dict(b) for b in x['bars']]; xs[2]['o']=103.0
for j,b in enumerate(xs):
 t='2026-01-%02dT%02d:00:00.000Z'%(1+j//24,j%24)
 o=MarketObservation('BTCUSDT','1h',Decimal(str(b['o'])),Decimal(str(b['h'])),Decimal(str(b['l'])),Decimal(str(b['c'])),Decimal(str(b['v'])),None,t,j+1,'CLOSED',availability_time=t)
 validate_market_observation(o,prev_sequence=j if j else None)
e=FVGEngine(get_params(),tick_size=.01,symbol='BTCUSDT')
first=e.process_bar(xs,2); before=next(iter(e.active_fvgs.values()),None)
corrected=[dict(b) for b in xs]; corrected[2]['h']+=0.25
# Preserve event timestamp, close and volume while correcting only a valid wick.
ob=MarketObservation('BTCUSDT','1h',Decimal(str(corrected[2]['o'])),Decimal(str(corrected[2]['h'])),Decimal(str(corrected[2]['l'])),Decimal(str(corrected[2]['c'])),Decimal(str(corrected[2]['v'])),None,'2026-01-01T02:00:00.000Z',3,'CLOSED',availability_time='2026-01-01T02:00:00.000Z')
validate_market_observation(ob,prev_sequence=2)
again=e.process_bar(corrected,2); after=next(iter(e.active_fvgs.values()),None)
print('all_initial_and_corrected_OHLC_valid=True; first_events=',[v['type'] for v in first])
print('initial_fvg_bounds=',(before.lower,before.upper) if before else None)
print('corrected_valid_same_index_ts_return=',again,'retained_bounds=',(after.lower,after.upper) if after else None)
print('processed_identity=',(2,xs[2]['ts_close']),'cached=',(2,xs[2]['ts_close']) in e._processed)
