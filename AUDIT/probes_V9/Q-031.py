"""Q-031: resolve_conflicting_bundles exists but has no caller; every
production path passes has_conflict=False (default), so the Q5 'no
conflict' gate can never trip and opposing bundles co-exist untouched."""
import datetime, subprocess
from apex.engines.e07_rtm.engine import (
    expected_components, build_order_map, build_bundle_pipeline,
    utc_activity_window_check, resolve_conflicting_bundles)

ts = int(datetime.datetime(2026, 3, 2, 13, 0,
                           tzinfo=datetime.timezone.utc).timestamp() * 1000)
fw = "RTM.PO3.v1"
exp = expected_components(fw)
confs = [{"cid": c.cid, "t_confirm_ms": ts - (5 - i) * 60000,
          "p_confirm": 100.0 + i} for i, c in enumerate(exp)]
om = build_order_map(exp, confs)
present = [c["cid"] for c in confs]
kz = utc_activity_window_check(ts)
b_up = build_bundle_pipeline(exp, present, om, 1.0, 1.0, kz, fw, "UP", ts)
b_dn = build_bundle_pipeline(exp, present, om, 1.0, 1.0, kz, fw, "DOWN", ts)
print("two opposing bundles built, classes:", b_up.resolution_class,
      b_dn.resolution_class, "fates:", b_up.fate, b_dn.fate)
res = resolve_conflicting_bundles([b_up, b_dn])
print("resolver WOULD produce fates:", [(b.direction, b.fate) for b in res])

grep = subprocess.run(["grep", "-rn", "resolve_conflicting_bundles", "apex/"],
                      capture_output=True, text=True).stdout.splitlines()
callers = [l for l in grep if "def resolve" not in l
           and "__init__.py" not in l
           and '"resolve_conflicting_bundles"' not in l]  # __all__ literal
print("apex/ callers outside definition/re-export:", callers)
assert callers == []
grep2 = subprocess.run(["grep", "-rn", "has_conflict", "apex/"],
                       capture_output=True, text=True).stdout.splitlines()
passers = [l for l in grep2 if "has_conflict=True" in l]
print("apex/ sites passing has_conflict=True:", passers)
assert passers == []
print("Q-031 CONFIRMED: conflict resolver dead; has_conflict constant False")
