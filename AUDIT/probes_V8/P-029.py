from apex.engines.e06_orderblock.engine import OB,e06_snapshot_id
x=OB('id','UP',99,101,1000,0,1,2,'BOS',1.,quality='Q3',fate='ACTIVE',confirmed_at=2000,width=2)
x.snapshot_id=e06_snapshot_id(x); initial=x.snapshot_id
x.age+=1;x.touch_count+=1;x.fate='MITIGATED'; recomputed=e06_snapshot_id(x)
print('initial_snapshot=',initial,'stored_after_mutation=',x.snapshot_id,'canonical_after_mutation=',recomputed)
print('stale_identity_after_lifecycle_change=',initial!=recomputed,'included_mutation_fields=',list(x.to_canonical().keys()))
