from common import obs
from apex.engines.e04_volatility.engine import E04VolatilityEngine
w=[obs(i,volume=100+i) for i in range(55)]
asof='2026-01-03T06:00:00.000Z'; e=E04VolatilityEngine()
a=e.compute('BTCUSDT','1h',asof,{'window':w,'e04_params':{'boll_k':2.0}})
b=e.compute('BTCUSDT','1h',asof,{'window':w,'e04_params':{'boll_k':3.0}})
f=E04VolatilityEngine().compute('BTCUSDT','1h',asof,{'window':w,'e04_params':{'boll_k':3.0}})
print('validated_window=55; counts=',len(a),len(b),len(f))
print('same_instance_result_object=',a is b,'same_snapshot_ids=',[x.snapshot_id for x in a]==[x.snapshot_id for x in b])
print('fresh_param3_snapshot_ids_differ=',bool(a and f and a[-1].snapshot_id!=f[-1].snapshot_id))
print('active_parameter_missing_from_replay_key=', 'boll_k' not in ('atr_short','atr_long','hv_window','ewma_lambda','ljung_m'))
