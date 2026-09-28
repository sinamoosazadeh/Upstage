from common import stable_bars
from apex.engines.e03_volume.engine import VolumeEngineV4, get_params

def run(gap):
    e=VolumeEngineV4(get_params())
    xs=stable_bars(51)
    for j,b in enumerate(xs): b['v']=100.0+j
    if gap: xs[-1]['ts'] += 11*3600*1000
    out=None
    for b in xs: out=e.ingest_bar(b)
    return len(e.history_bars), len(set(b['ts'] for b in e.history_bars)), out.volume_sma if out else None, out.pit_meta.get('history_len') if out else None
print('validated_ohlc=51 each run; no_gap=',run(False))
print('validated_ohlc=51 each run; final_bar_12h_gap=',run(True))
