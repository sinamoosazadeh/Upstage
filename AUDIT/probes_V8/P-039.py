from common import obs
from apex.data_catalog.contracts import parse_utc_ms
from apex.engines.e03_volume.engine import (E03VolumeEngine,
    observation_to_bar)

window = [obs(i, open_=100 + i * 0.03, close=100 + i * 0.03 + 0.1,
              high=100 + i * 0.03 + 0.6, low=100 + i * 0.03 - 0.5,
              volume=100 + (i % 4) * 10, oi=None)
          for i in range(51)]
# Deliberately omit both availability arrays. ATR is present as a scalar;
# MarketObservation has no OI and no oi_timestamp.
atr = 2.0
bar = observation_to_bar(window[-1], '1h', atr, None, None)
receipt = int(parse_utc_ms(window[-1].availability_time).timestamp() * 1000)
print('validated_closed_observations=', len(window),
      'has_OI=', window[-1].oi is not None,
      'has_OI_timestamp=', window[-1].oi_timestamp is not None,
      'atr_availability_arg=None', 'oi_availability_arg=None')
print('adapter_bar_ohlcv_availability=', bar['availability_time_ms'],
      'oi_availability=', bar['oi_availability_time_ms'],
      'atr_availability=', bar['atr_availability_time_ms'],
      'OHLC_receipt_ms=', receipt,
      'both_dependencies_defaulted_to_OHLC=',
      bar['oi_availability_time_ms'] == receipt and
      bar['atr_availability_time_ms'] == receipt)
engine = E03VolumeEngine()
events = engine.compute('BTCUSDT', '1h', window[-1].timestamp,
    {'window': window, 'atr_prev': atr})
print('emitted_count=', len(events))
if events:
    ev = events[-1]
    print('event_time=', ev.event_time, 'availability_time=', ev.availability_time,
          'quality_resolution=', ev.resolution_class,
          'validity=', ev.validity, 'condition_state=', ev.condition_state)
# Compare with producer context construction: it supplies ATR availability
# explicitly at the current closed bar boundary, using a lagged E04 ATR.
print('producer_pattern_atr_availability_ms=', receipt,
      'source_value_is_lagged_ATR=True',
      'producer_explicit_list_present=True')
