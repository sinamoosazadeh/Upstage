"""Q-001: E07 Q5 gate never checks kz_info['degraded']; the degraded local
registry marks 12:30-16:00 UTC as overlap, so a bundle can reach Q5 while
E12 is entirely absent (temporal_provider=None) or failing."""
import datetime
from apex.engines.e07_rtm.engine import (
    utc_activity_window_check, expected_components, build_order_map,
    build_bundle_pipeline, quality_class_caps)

# 13:00 UTC is inside the degraded-registry overlap 12:30-16:00
ts = int(datetime.datetime(2026, 3, 2, 13, 0, tzinfo=datetime.timezone.utc)
         .timestamp() * 1000)

# 1) No provider at all -> degraded branch
kz = utc_activity_window_check(ts, econ_events=None, temporal_provider=None)
print("no-provider kz: degraded=%s reason=%s is_overlap=%s source=%s" % (
    kz["degraded"], kz["degraded_reason"], kz["is_overlap"], kz["source"]))

# 2) Provider that raises -> exception swallowed, same degraded branch
class Boom:
    def temporal_window(self, ts_ms):
        raise RuntimeError("E12 down")
kz2 = utc_activity_window_check(ts, temporal_provider=Boom())
print("raising-provider kz: degraded=%s is_overlap=%s" % (
    kz2["degraded"], kz2["is_overlap"]))

# 3) Full PO3 chain, perfect order, high p_confirm quality -> bundle
fw = "RTM.PO3.v1"
expected = expected_components(fw)
confs = [{"cid": c.cid, "t_confirm_ms": ts - (5 - i) * 60000,
          "p_confirm": 100.0 + i} for i, c in enumerate(expected)]
om = build_order_map(expected, confs)
present = [c["cid"] for c in confs]
b = build_bundle_pipeline(expected, present, om, avg_q=1.0, mtf_align=1.0,
                          kz_info=kz, framework_id=fw, direction="UP",
                          as_of_ms=ts)
print("bundle: integrity=%.3f conf=%.3f class=%s degraded=%s authority=%s" % (
    b.integrity, b.confidence, b.resolution_class, b.degraded,
    b.temporal_authority))
assert b.resolution_class == "Q5" and b.degraded is True, "claim not reproduced"

# 4) Direct gate check: Q5 gate inputs contain no 'degraded' key access.
#    Feed a kz dict that is degraded but overlap=True -> Q5 kept.
label = quality_class_caps("Q5", conf=0.99, avg_q=1.0, mtf_align=1.0,
                           kz_info={"is_overlap": True, "degraded": True,
                                    "econ_conflict": False})
print("quality_class_caps with degraded=True kz ->", label)
assert label == "Q5"
print("Q-001 CONFIRMED: Q5 reachable in degraded (E12-absent/failing) mode")
