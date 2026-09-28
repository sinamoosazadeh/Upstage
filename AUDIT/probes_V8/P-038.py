from apex.engines.e05_fvg.engine import FVGEngine, FVGObject, get_params

def zone(fid, lower, upper, idx, age):
    obj = FVGObject(fid=fid, direction='UP', lower=lower, upper=upper,
        mid=(lower + upper) / 2, width=upper - lower,
        created_at_ts=1000 + idx, created_at_idx=idx,
        ftype='CONVENTIONAL', quality_tag='Q2', fate='ACTIVE',
        age_bars=age, salience_0=0.7, salience=0.5, freshness=0.7,
        atr_at_creation=2.0)
    obj.update_snapshot()
    return obj

older = zone('fid_older', 100.0, 102.0, 0, 10)
newer = zone('fid_newer', 100.3, 102.3, 1, 1)
old_snapshot = older.snapshot_id
iou = (102.0 - 100.3) / ((102.0 - 100.0) + (102.3 - 100.3)
                            - (102.0 - 100.3))
e = FVGEngine(get_params(), tick_size=0.01, symbol='BTCUSDT')
e.active_fvgs = {older.fid: older, newer.fid: newer}
events = e._merge_overlaps()
merged = next(iter(e.active_fvgs.values()))
retained_id = merged.snapshot_id
merged.update_snapshot()
print('object_only_probe_no_candle_ingress=True', 'IoU=', round(iou, 6),
      'threshold=', e.params['iou_merge_thr'],
      'event_types=', [x['type'] for x in events])
print('merged_bounds=', (merged.lower, merged.upper),
      'retained_fid=', merged.fid, 'retained_age=', merged.age_bars,
      'expected_min_age=', 1, 'retained_snapshot=', retained_id,
      'recomputed_snapshot=', merged.snapshot_id,
      'snapshot_was_stale=', retained_id != merged.snapshot_id,
      'source_A_snapshot=', old_snapshot,
      'removed_B_still_in_active=', newer in e.active_fvgs.values())
