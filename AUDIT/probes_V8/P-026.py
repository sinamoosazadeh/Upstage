from common import bar
from apex.engines.e06_orderblock.engine import OrderBlockEngine,get_params
bars=[]
for i in range(7):
 op=100+i*.1; cl=op+(.2 if i else -1.0)
 if i==0: op=100.; cl=99.; hi=100.5; lo=99.
 else: hi=max(op,cl)+.2; lo=min(op,cl)-.2
 bars.append(bar(i,open_=op,close=cl,high=hi,low=lo,volume=100))
vol=[{'snapshot_id':f'v{i}','as_of_ts':b['ts']+100000,'availability_time_ms':b['ts']+50000,'volume_sma':100.,'volume_ratio':2.} for i,b in enumerate(bars)]
atr=[{'snapshot_id':f'a{i}','as_of':b['ts']+100000,'atr_n':2.} for i,b in enumerate(bars)]
e=OrderBlockEngine(get_params()); e.ingest_bars(bars,vol,atr)
struct=[{'kind':'BOS','direction':'UP','valid_at_idx':5}]
future={'direction':'UP','lower':98.9,'upper':99.1,'present':True,'created_at_ts':bars[6]['ts']+500000,'availability_time_ms':bars[6]['ts']+600000,'parent_id':'future'}
a=e.detect_at(0,struct,[]); b=e.detect_at(0,struct,[future])
print('validated_OHLC_bars=',len(bars),'future_fvg_created_after_confirmation=',future['created_at_ts']>bars[5]['ts'])
print('without_fvg=',(a.quality,a.fate,a.confirmed_at) if a else None)
print('with_future_fvg=',(b.quality,b.fate,b.confirmed_at) if b else None)
