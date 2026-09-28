from common import bar
from apex.engines.e06_orderblock.engine import OrderBlockEngine,OB,get_params,e06_snapshot_id
b=bar(0,open_=101,close=102,high=102.2,low=100.5,volume=100)
vol=[{'snapshot_id':'v','as_of_ts':b['ts']+1000,'availability_time_ms':b['ts'],'volume_sma':100.,'volume_ratio':0.}]
atr=[{'snapshot_id':'a','as_of':b['ts']+1000,'atr_n':2.}]
e=OrderBlockEngine(get_params());e.ingest_bars([b],vol,atr)
old=OB('old','UP',100,101,b['ts']-3600000,0,1,2,'BOS',1.,quality='QX',fate='INVALIDATED',width=1);old.snapshot_id=e06_snapshot_id(old);e.history=[old]
e._detect_breaker_conversion(0)
print('validated_reclaim_OHLC=True; no_structural_feed; volume_ratio=0')
print('new_objects=',[(x.quality,x.structural_event,x.vol_ratio,x.fate,x.otype) for x in e.active_obs])
