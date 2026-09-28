from common import obs
from apex.engines.e03_volume.engine import detect_oi_stale
from apex.data_catalog.contracts import parse_utc_ms
xs=[obs(i,oi=1000+i) for i in range(5)]
ms=[int(parse_utc_ms(x.oi_timestamp).timestamp()*1000) for x in xs]
print('validated_observations=5; increasing_oi=',[str(x.oi) for x in xs])
print('oi_timestamp_units=epoch_ms; consecutive_gap_ms=',ms[-1]-ms[-2])
print('timeframe_sec=3600; result=',detect_oi_stale([float(x.oi) for x in xs],ms,3600))
