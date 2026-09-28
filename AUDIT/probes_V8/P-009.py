from common import stable_bars, bar
from apex.engines.e04_volatility.engine import VolatilityEngineV4,get_params
p=get_params(); print('defaults gap_atr_mult=',p['gap_atr_mult'])
e=VolatilityEngineV4(p,timeframe='1h')
xs=stable_bars(55)
# Constant validated range 2 gives ATR≈2; the 56th bar gaps upward by 20.
for b in xs:
    op=b['o']; cl=b['c']; b['h']=op+1.0; b['l']=op-1.0
    e.ingest_bar(b)
prev=e.atr_s.atr
last=bar(55,open_=xs[-1]['c']+20,close=xs[-1]['c']+20.1,high=xs[-1]['c']+21,low=xs[-1]['c']+19,volume=100)
out=e.ingest_bar(last)
print('prev_ATR=',prev,'opening_gap=',last['o']-xs[-1]['c'])
print('last_state_ATR=',out.state.atr14_wilder if out else None)
print('last_events=',[x.get('event_type') for x in out.events] if out else None)
print('last_error=',e.last_error)
