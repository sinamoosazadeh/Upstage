"""Q-007: RTMBundle.to_canonical (the snapshot_id payload) is only
{framework_id, present, integrity, as_of_ms}: two bundles with opposite
direction (UP vs DOWN) — and different symbol/timeframe contexts — collide
on the same snapshot_id."""
import datetime
from apex.engines.e07_rtm.engine import (expected_components, build_order_map,
                                         build_bundle_pipeline,
                                         utc_activity_window_check)

ts = int(datetime.datetime(2026, 3, 2, 13, 0,
                           tzinfo=datetime.timezone.utc).timestamp() * 1000)
fw = "RTM.PO3.v1"
exp = expected_components(fw)
confs = [{"cid": c.cid, "t_confirm_ms": ts - (5 - i) * 60000,
          "p_confirm": 100.0 + i} for i, c in enumerate(exp)]
om = build_order_map(exp, confs)
present = [c["cid"] for c in confs]
kz = utc_activity_window_check(ts)

b_up = build_bundle_pipeline(exp, present, om, 0.9, 1.0, kz, fw, "UP", ts)
b_dn = build_bundle_pipeline(exp, present, om, 0.9, 1.0, kz, fw, "DOWN", ts)
print("canonical payload keys:", sorted(b_up.to_canonical().keys()))
print("UP  snapshot_id:", b_up.snapshot_id)
print("DOWN snapshot_id:", b_dn.snapshot_id)
assert b_up.direction != b_dn.direction
assert b_up.snapshot_id == b_dn.snapshot_id
# also different avg_q/mtf (=> different confidence & class) collide:
b_q = build_bundle_pipeline(exp, present, om, 0.2, 0.0, kz, fw, "UP", ts)
print("different avg_q/mtf: conf %.3f vs %.3f, class %s vs %s, same sid: %s"
      % (b_up.confidence, b_q.confidence, b_up.resolution_class,
         b_q.resolution_class, b_up.snapshot_id == b_q.snapshot_id))
assert b_up.snapshot_id == b_q.snapshot_id
print("Q-007 CONFIRMED: snapshot identity excludes direction/confidence/"
      "class/symbol/timeframe")
