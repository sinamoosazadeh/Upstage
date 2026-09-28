from common import bar
from apex.engines.e06_orderblock.engine import (OB, OrderBlockEngine,
    e06_snapshot_id, get_params)

# Validated closed OHLC is the bar seen by update_with_bar. No structure-event
# feed is accepted by this method or supplied to this update call.
next_bar = bar(1, open_=102.0, close=102.5, high=102.7, low=101.9,
               volume=100)
e = OrderBlockEngine(get_params())
e.bars = [next_bar]
e.atr = [2.0]
old = OB(oid='ob_parent', direction='UP', zone_lo=100.0, zone_hi=101.0,
         origin_ts=next_bar['ts'] - 7200000, origin_idx=0,
         displacement_mag=2.0, displacement_multi=2.0,
         structural_event='BOS', structural_strength=1.0,
         otype='ENTRY', age=3, salience=0.8, vol_ratio=1.5,
         quality='Q3', fate='MITIGATED',
         confirmed_at=next_bar['ts'] - 3600000, width=1.0)
old.snapshot_id = e06_snapshot_id(old)
e.active_obs.append(old)
e.update_with_bar(0)
new = next((ob for ob in e.active_obs if ob.otype == 'MITIGATION_BLOCK'), None)
print('validated_bar_ts=', next_bar['ts'], 'structural_feed_supplied=False')
print('parent_fate=', old.fate, 'parent_in_history=', old in e.history)
print('reactivation=', None if new is None else
      (new.otype, new.quality, new.fate, new.structural_event,
       new.origin_idx, new.confirmed_at, new.oid))
