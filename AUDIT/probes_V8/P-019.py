from apex.engines.e05_fvg.engine import FVGEngine,FVGObject,get_params
from common import stable_bars,bar
p=get_params({'max_age_bars':1,'fresh_thr':0.0,'fill_depth_thr':0.99,'mit_activate':0.5})
e=FVGEngine(p,tick_size=.01,symbol='BTCUSDT')
f=FVGObject(fid='f',direction='UP',lower=100,upper=102,mid=101,width=2,created_at_ts=0,created_at_idx=0)
f.update_snapshot(); e.active_fvgs['f']=f
xs=stable_bars(2); xs[1]=bar(1,open_=99.,high=103.,low=99.,close=102.,volume=100.)
ev=e.process_bar(xs,1)
print('event_types=',[x['type'] for x in ev])
print('history_fate=',e.history[0].fate if e.history else None,'age=',e.history[0].age_bars if e.history else None)
print('snapshot_old=',f.snapshot_id,'snapshot_recomputed=',end=' ')
f.update_snapshot(); print(f.snapshot_id)
