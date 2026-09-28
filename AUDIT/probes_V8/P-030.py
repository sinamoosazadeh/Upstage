from apex.engines.e06_orderblock.engine import E06OrderBlockEngine,OB,e06_snapshot_id
from apex.fabric.evidence import fabric_from_events
x=OB('candidate','UP',99,101,1767225600000,0,1,2,'NONE',.3,quality='Q2',fate='CANDIDATE',confirmed_at=1767225600000,width=2)
x.snapshot_id=e06_snapshot_id(x); ev=E06OrderBlockEngine()._to_evidence(x,'BTCUSDT','1h',1.)
f=fabric_from_events([ev],symbol='BTCUSDT',timeframe='1h',as_of=1767230000000,data_trust=1.)
print('native_candidate=',ev.condition_state,ev.validity,ev.resolution_class,ev.fate_state.value)
print('fabric_members=',[(m.state,m.resolution_class) for m in f.members],'excluded=',f.excluded)
