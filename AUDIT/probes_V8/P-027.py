from common import bar
from apex.engines.e06_orderblock.engine import OrderBlockEngine,OB,get_params,e06_snapshot_id
b=bar(0,open_=100,close=100.1,high=101,low=99,volume=100)
vol=[{'snapshot_id':'v','as_of_ts':b['ts']+1000,'availability_time_ms':b['ts'],'volume_sma':100.,'volume_ratio':1.5}]
atr=[{'snapshot_id':'a','as_of':b['ts']+1000,'atr_n':2.}]
def mk(i,lo,hi):
 o=OB(f'ob{i}','UP',lo,hi,b['ts'],i,1,2,'BOS',1.,quality='Q2',fate='ACTIVE',width=hi-lo); o.snapshot_id=e06_snapshot_id(o); return o
e=OrderBlockEngine(get_params());e.ingest_bars([b],vol,atr);e.active_obs=[mk(1,100,102),mk(2,100.2,102.2)];e._detect_confluence(0)
print('valid_bar=True; active_OBs=2; FVG_inputs=0; events=',[x for x in e.events if x['code']=='EV_OBK_008'])
e2=OrderBlockEngine(get_params());e2.ingest_bars([b],vol,atr);e2.active_obs=[mk(3,100,102)];e2._detect_confluence(0)
print('active_OBs=1; FVG_not_consumed_by_method; confluence_events=',[x for x in e2.events if x['code']=='EV_OBK_008'])
