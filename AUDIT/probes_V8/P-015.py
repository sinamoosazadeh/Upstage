from common import bar
from apex.engines.e04_volatility.engine import VolatilityEngineV4,get_params
import math
p=get_params({'drift_consec_days':3,'nondir_corr_thr':-1.0,'nondir_p_thr':1.0})
e=VolatilityEngineV4(p,timeframe='1h')
for i in range(65):
    op=100+i*0.03; cl=op+math.sin(i*1.71)*0.45
    lo=min(op,cl)-0.3-(i%3)*0.07; hi=max(op,cl)+0.4+(i%4)*0.05
    b=bar(i,open_=op,close=cl,high=hi,low=lo,volume=100+(i*17)%73)
    x=e.ingest_bar(b)
    if x:
        found=[z['event_type'] for z in x.events if z['event_type']=='EV_VLT_002']
        if found: print('hourly_bars_processed=',len(e.bars),'drift_streak=',e.drift_streak,'event=',found)
print('total_hourly_bars=',len(e.bars),'drift_streak=',e.drift_streak)
