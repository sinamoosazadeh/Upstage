from common import stable_bars
from apex.engines.e03_volume.engine import E03VolumeEngine, ParticipationEvidence
x=ParticipationEvidence(snapshot_id='s',as_of_ts=1767225600000,volume_ratio=3.,
 volume_sma=100.,oi_state='MISSING',quality='Q1',events=['EV_VOL_001 Volume_Spike','EV_VOL_011 OI_Unavailable'])
e=E03VolumeEngine()
out=e._to_evidence(x,'BTCUSDT','1h','2026-01-01T00:00:00.000Z',1.,0.)
print('source_engine_state=DEGRADED by ingest rule for OI MISSING; source_quality=',x.quality)
print('event_names=',x.events)
print('emitted condition_state=',out.condition_state,'resolution_class=',out.resolution_class,'validity=',out.validity,'fate=',out.fate_state.value,'confidence=',out.confidence)
print('all event names present in condition_state=',all(k in out.condition_state for k in x.events))
