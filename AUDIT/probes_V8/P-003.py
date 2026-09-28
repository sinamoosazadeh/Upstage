from common import stable_bars
from apex.engines.e03_volume.engine import VolumeEngineV4, get_params
valid=stable_bars(1)[0]
e=VolumeEngineV4(get_params())
for _ in range(50):
    e.ingest_bar(dict(valid))
print('input rows=50; unique ts=',len({b['ts'] for b in e.history_bars}), 'history=',len(e.history_bars),'emitted=',len(e.emitted))
next_bar=dict(valid); next_bar['ts']+=3600000; next_bar['o']+=1; next_bar['h']+=1; next_bar['l']+=1; next_bar['c']+=1
for key in ('availability_time_ms','oi_availability_time_ms','atr_availability_time_ms'): next_bar[key]+=3600000
out=e.ingest_bar(next_bar)
print('after one distinct bar: unique ts=',len({b['ts'] for b in e.history_bars}), 'history=',len(e.history_bars),'emission=',out is not None,'reported_prior_history=',out.pit_meta['history_len'] if out else None)
