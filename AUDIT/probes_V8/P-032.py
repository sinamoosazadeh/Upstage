from common import bar
from apex.engines.e06_orderblock.engine import OrderBlockEngine,get_params
bars=[]
for i in range(7):
 op=100+i*.1; cl=op+(.2 if i else -1.0)
 if i==0: op=100.;cl=99.;hi=100.5;lo=99.
 else: hi=max(op,cl)+.2;lo=min(op,cl)-.2
 bars.append(bar(i,open_=op,close=cl,high=hi,low=lo,volume=100))
future=[]
for i,b in enumerate(bars):
 future.append(({'snapshot_id':f'v{i}','as_of_ts':b['ts']+100000,'availability_time_ms':b['ts']+50000,'volume_sma':100.,'volume_ratio':2.},
                {'snapshot_id':f'a{i}','as_of':b['ts']+100000,'atr_n':2.}))
struct=[{'kind':'BOS','direction':'UP','valid_at_idx':5}]
for atrval in (2.,20.):
 vol=[dict(x[0]) for x in future]; atr=[dict(x[1],atr_n=atrval) for x in future]
 e=OrderBlockEngine(get_params());e.ingest_bars(bars,vol,atr);o=e.detect_at(0,struct,[])
 print('ATR=',atrval,'future_as_of_accepted=',atr[0]['as_of']>bars[0]['ts'],'OB=',(o.quality,o.displacement_multi) if o else None)
