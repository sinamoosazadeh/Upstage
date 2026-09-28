from common import bar
from apex.engines.e06_orderblock.engine import OrderBlockEngine, get_params

def inputs(n):
    bars = [bar(0, open_=100.0, close=99.8, high=100.01, low=99.79, volume=100)]
    for i in range(1, n):
        op = 100.0 + (i - 1) * 0.2
        bars.append(bar(i, open_=op, close=op + 0.1, high=op + 0.4,
                        low=op - 0.4, volume=100))
    volume = [{'snapshot_id': f'v{i}', 'as_of_ts': b['ts'] + 1000,
               'availability_time_ms': b['ts'], 'volume_sma': 100.0,
               'volume_ratio': 1.5} for i, b in enumerate(bars)]
    atr = [{'snapshot_id': f'a{i}', 'as_of': b['ts'] + 1000,
            'atr_n': 2.0} for i, b in enumerate(bars)]
    return bars, volume, atr

for n in (6, 7):
    bars, volume, atr = inputs(n)
    e = OrderBlockEngine(get_params())
    result = e.run_full(bars, {}, {}, volume, atr)
    at_origin = [ob for ob in result if ob.origin_idx == 0]
    print('validated_closed_bars=', n, 'disp_max_k=', e.p.disp_max_k,
          'origin0_count=', len(at_origin))
    if at_origin:
        ob = at_origin[0]
        print('no_BOS K reported in event=', next((ev.get('K') for ev in e.events
              if ev['code'] == 'EV_OBK_002'), None),
              'confirmed_at=', ob.confirmed_at,
              'bar1_ts=', bars[1]['ts'], 'bar5_ts=', bars[5]['ts'],
              'disp_multi=', ob.displacement_multi, 'quality=', ob.quality,
              'fate=', ob.fate)
