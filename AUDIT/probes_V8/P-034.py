from common import bar
from apex.engines.e06_orderblock.engine import OrderBlockEngine, get_params

bars = [bar(0, open_=100.0, close=99.8, high=100.01, low=99.79, volume=100)]
for i in range(1, 7):
    op = 100.0 + (i - 1) * 0.2
    bars.append(bar(i, open_=op, close=op + 0.1, high=op + 0.65,
                    low=op - 0.65, volume=100))
volume = [{'snapshot_id': f'v{i}', 'as_of_ts': b['ts'] + 1000,
           'availability_time_ms': b['ts'], 'volume_sma': 100.0,
           'volume_ratio': 1.5} for i, b in enumerate(bars)]
atr = [{'snapshot_id': f'a{i}', 'as_of': b['ts'] + 1000,
        'atr_n': 2.0} for i, b in enumerate(bars)]
event = {'kind': 'BOS', 'direction': 'UP', 'valid_at_idx': 3,
         'availability_time_ms': bars[3]['ts']}
params = get_params()
direct = OrderBlockEngine(params)
direct.ingest_bars(bars, volume, atr)
ob_direct = direct.detect_at(0, [event], [])
batch = OrderBlockEngine(params)
res_batch = batch.run_full(bars, {3: [event]}, {}, volume, atr)
ob_batch = next((ob for ob in res_batch if ob.origin_idx == 0), None)
for label, ob in [('direct', ob_direct), ('batch', ob_batch)]:
    print(label, 'result=', None if ob is None else
          (ob.quality, ob.structural_event, ob.confirmed_at,
           round(ob.displacement_multi, 5), ob.fate))
print('BOS_valid_at_idx=', event['valid_at_idx'], 'validated_bars=', len(bars),
      'batch_origin0_event_indices=', sorted({i for i in (0, 1, 2)}))
