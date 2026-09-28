import json
from pathlib import Path
from decimal import Decimal
from apex.data_catalog.contracts import MarketObservation, validate_market_observation
from apex.engines.e05_fvg.engine import FVGEngine, get_params

fixture = json.loads(Path('tests/fixtures/e05_golden_fixtures.json').read_text())['fixtures']
x = next(v for v in fixture if v['name'] == 'VALID_BULL_CONVENTIONAL')
bars = [dict(b) for b in x['bars']]
# Repair the fixture's open bound while retaining the bullish gap geometry.
bars[2]['o'] = 103.0
for j, b in enumerate(bars):
    t = f'2026-01-01T{j:02d}:00:00.000Z'
    o = MarketObservation('BTCUSDT', '1h', Decimal(str(b['o'])),
        Decimal(str(b['h'])), Decimal(str(b['l'])), Decimal(str(b['c'])),
        Decimal(str(b.get('v', 100))), None, t, j + 1, 'CLOSED',
        availability_time=t)
    validate_market_observation(o, prev_sequence=j if j else None)
params = get_params({'inverse_enabled': True})
engine = FVGEngine(params, tick_size=0.01, symbol='BTCUSDT')
future_bos = {'dir': 'DOWN', 'idx': 4,
              'availability_time_ms': 5000}
events = engine.process_bar(bars, 2, trend_htf='DOWN',
                            bos_events=[future_bos])
obj = next(iter(engine.active_fvgs.values()), None)
print('validated_ohlc_bars=', len(bars), 'fvg_index=2',
      'inverse_enabled=', params['inverse_enabled'],
      'future_BOS_idx=', future_bos['idx'], 'event_types=',
      [e['type'] for e in events])
print('result=', None if obj is None else
      (obj.ftype, obj.quality_tag, obj.created_at_idx, obj.created_at_ts,
       obj.snapshot_id))
