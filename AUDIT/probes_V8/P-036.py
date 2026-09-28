from common import bar
from apex.engines.e06_orderblock.engine import OrderBlockEngine, get_params

bars = [bar(0, open_=100.0, close=99.986, high=100.0, low=99.979,
            volume=100)]
for i in range(1, 7):
    op = 100.0 + (i - 1) * 1.0
    bars.append(bar(i, open_=op, close=op + 1.0, high=op + 2.0,
                    low=op - 2.0, volume=100))
volume = [{'snapshot_id': f'v{i}', 'as_of_ts': b['ts'] + 1000,
           'availability_time_ms': b['ts'], 'volume_sma': 100.0,
           'volume_ratio': 1.5} for i, b in enumerate(bars)]
atr = [{'snapshot_id': f'a{i}', 'as_of': b['ts'] + 1000,
        'atr_n': 10.0} for i, b in enumerate(bars)]
e = OrderBlockEngine(get_params())
e.ingest_bars(bars, volume, atr)
ob = e.detect_at(0, [{'kind': 'BOS', 'direction': 'UP', 'valid_at_idx': 5}], [])
origin = bars[0]
origin_range = origin['h'] - origin['l']
body_ratio = abs(origin['c'] - origin['o']) / origin_range
print('validated_ohlc_bars=', len(bars), 'theta_min_range_parameter=',
      'absent', 'origin_range=', origin_range, 'ATR=', e.atr[0],
      'R_origin_over_ATR=', origin_range / e.atr[0],
      'body_ratio=', body_ratio)
print('native_result=', None if ob is None else
      (ob.quality, ob.structural_event, ob.displacement_multi,
       ob.zone_lo, ob.zone_hi, ob.fate))
