import json
from pathlib import Path
from decimal import Decimal
from datetime import datetime,timedelta,timezone
from apex.data_catalog.contracts import MarketObservation,validate_market_observation
from apex.engines.e05_fvg.engine import E05FVGEngine
from apex.engines.e04_volatility.engine import E04VolatilityEngine
x=next(v for v in json.loads(Path('tests/fixtures/e05_golden_fixtures.json').read_text())['fixtures'] if v['name']=='VALID_BULL_CONVENTIONAL')
bars=[dict(b) for b in x['bars']]; bars[2]['o']=103.; start=datetime(2026,1,1,tzinfo=timezone.utc)
def make(j,b,status):
 t=(start+timedelta(hours=j)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
 o=MarketObservation('BTCUSDT','1h',Decimal(str(b['o'])),Decimal(str(b['h'])),Decimal(str(b['l'])),Decimal(str(b['c'])),Decimal(str(b['v'])),None,t,j+1,status,availability_time=t)
 validate_market_observation(o,prev_sequence=j if j else None); return o
obs=[make(j,b,'OPEN') for j,b in enumerate(bars)]
e05=E05FVGEngine().compute('BTCUSDT','1h','2026-01-01T02:00:00.000Z',{'window':obs})
print('validated_open_observations=',len(obs),'all_status_open=',all(o.status=='OPEN' for o in obs),'E05_events=',len(e05),'E05_condition=',e05[0].condition_state if e05 else None)
long=[]
for i in range(40):
 op=100+i*.03; cl=op+.1; b={'o':op,'h':cl+.5,'l':op-.5,'c':cl,'v':100+i*3}
 long.append(make(i,b,'OPEN'))
e04=E04VolatilityEngine().compute('BTCUSDT','1h','2026-01-02T15:00:00.000Z',{'window':long})
print('validated_open_observations=',len(long),'E04_events=',len(e04),'first_event=',e04[0].condition_state if e04 else None)
