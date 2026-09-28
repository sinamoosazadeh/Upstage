from common import stable_bars,obs
from datetime import datetime,timedelta,timezone
from apex.engines.e04_volatility.engine import VolatilityEngineV4
xs=stable_bars(55); e=VolatilityEngineV4()
for b in xs: e.ingest_bar(b)
last=dict(xs[-1]); print('valid_input_count=55; stored=',len(e.bars),'seen_keys=',len(e._seen_keys))
ts=(datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(hours=54)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
corrected=obs(56,open_=last['o'],close=last['c'],high=last['h']+0.25,low=last['l'],volume=last['v'],timestamp=ts)
from apex.data_catalog.contracts import parse_utc_ms
changed=dict(last); changed['h']=float(corrected.high); changed['availability_time_ms']=int(parse_utc_ms(ts).timestamp()*1000)+1000
out=e.ingest_bar(changed)
print('both_original_and_changed_OHLC_valid=',last['h']>=max(last['o'],last['c']) and changed['h']>=max(changed['o'],changed['c']))
print('changed_wick_same_ts_close_volume_return=',out,'stored_after=',len(e.bars),'seen_keys_after=',len(e._seen_keys))
