from apex.engines.e06_orderblock.engine import E06OrderBlockEngine,OB,e06_snapshot_id
from apex.fabric.evidence import fabric_from_events
for fate in ('INVALIDATED','EXPIRED'):
 x=OB('terminal'+fate,'UP',99,101,1767225600000,0,1,2,'BOS',1.,quality='QX',fate=fate,confirmed_at=1767225600000,width=2)
 x.snapshot_id=e06_snapshot_id(x); ev=E06OrderBlockEngine()._to_evidence(x,'BTCUSDT','1h',1.)
 f=fabric_from_events([ev],symbol='BTCUSDT',timeframe='1h',as_of=1767230000000,data_trust=1.)
 print(fate,'event=',ev.condition_state,ev.validity,ev.resolution_class,ev.fate_state.value,'fabric=',len(f.members),f.excluded)
