from common import obs
from apex.engines.e03_volume.engine import E03VolumeEngine
from datetime import datetime, timedelta, timezone
from decimal import Decimal

def window(include_oi):
    rows=[]
    start=datetime(2026,1,1,tzinfo=timezone.utc)
    for i in range(55):
        t=(start+timedelta(hours=i)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        o=100+i*.02; c=o+.1
        oi=Decimal(str(1000+i)) if include_oi else None
        from apex.data_catalog.contracts import MarketObservation,validate_market_observation
        x=MarketObservation('BTCUSDT','1h',Decimal(str(o)),Decimal(str(c+.5)),Decimal(str(o-.5)),Decimal(str(c)),Decimal('100'),oi,t,i+1,'CLOSED',availability_time=t,oi_timestamp=t if include_oi else None)
        validate_market_observation(x,prev_sequence=i if i else None); rows.append(x)
    return rows
eng=E03VolumeEngine()
ctx={'window':window(False),'atr_prev':2.0}
a=eng.compute('BTCUSDT','1h','2026-01-03T06:00:00.000Z',ctx)
ctx2={'window':window(True),'atr_prev':2.0}
b=eng.compute('BTCUSDT','1h','2026-01-03T06:00:00.000Z',ctx2)
fresh=E03VolumeEngine().compute('BTCUSDT','1h','2026-01-03T06:00:00.000Z',ctx2)
print('validated_observations_per_run=55; cached_outputs=',len(a),len(b),'fresh_changed_input=',len(fresh))
print('same_result_object=',a is b,'same_ids=',[x.evidence_id for x in a]==[x.evidence_id for x in b])
print('first_oi_state_embedded_in_explanation=',a[-1].explanation if a else None)
print('second_replay_returns_cached_same_payload=',bool(a and b and a[-1].explanation==b[-1].explanation))
print('cached_last_snapshot=',a[-1].snapshot_id if a else None,'fresh_last_snapshot=',fresh[-1].snapshot_id if fresh else None)
print('cached_last_state_vs_fresh_differs=',bool(a and fresh and a[-1].snapshot_id!=fresh[-1].snapshot_id))
print('fresh_last_feature_dependencies=',fresh[-1].feature_dependencies if fresh else None)
