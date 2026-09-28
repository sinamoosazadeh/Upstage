from apex.engines.e05_fvg.engine import E05FVGEngine,FVGObject
from apex.data_catalog.contracts import LifecycleState
f=FVGObject(fid='f',direction='UP',lower=100,upper=102,mid=101,width=2,created_at_ts=1767225600000,created_at_idx=2,fate='EXPIRED',quality_tag='QX_EXPIRED')
f.update_snapshot(); out=E05FVGEngine()._to_evidence(f,'BTCUSDT','1h',1.)
print('native_expired_event=',out.condition_state,'validity=',out.validity,'resolution=',out.resolution_class,'fate_state=',out.fate_state.value,'event_time=',out.event_time,'availability=',out.availability_time)
