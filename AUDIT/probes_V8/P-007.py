from common import stable_bars
from apex.engines.e03_volume.engine import VolumeEngineV4, get_params
import tracemalloc,time
bars=stable_bars(3000)
e=VolumeEngineV4(get_params())
tracemalloc.start(); t0=time.perf_counter()
for b in bars: e.ingest_bar(b)
elapsed=time.perf_counter()-t0; current,peak=tracemalloc.get_traced_memory(); tracemalloc.stop()
print('validated_synthetic_OHLC_bars=',len(bars),'processed=',len(e.history_bars),'elapsed_seconds=',round(elapsed,3))
print('retained_history_bars=',len(e.history_bars),'closes=',len(e.history_closes),'volumes=',len(e.history_vols),'obv=',len(e.history_obv))
print('tracemalloc_current_bytes=',current,'peak_bytes=',peak)
