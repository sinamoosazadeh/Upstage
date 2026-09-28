"""Q-003: PIT filter is only t_confirm_ms <= as_of with no max-age; stale
confirmations (days old) build a fresh bundle with age_bars=0, and
update_bundle_fate (the ageing/expiry machine) has no in-tree caller."""
import datetime, subprocess
from apex.engines.e07_rtm.engine import (run_engine, expected_components,
                                         update_bundle_fate)

ts0 = int(datetime.datetime(2026, 3, 2, 0, 0,
                            tzinfo=datetime.timezone.utc).timestamp() * 1000)
bars = [{"ts": ts0 + i * 3600_000, "o": 100, "h": 101, "l": 99, "c": 100.5,
         "v": 1000.0} for i in range(60)]
as_of = bars[-1]["ts"]
WEEK = 7 * 24 * 3600 * 1000
fw = "RTM.PO3.v1"
# confirmations one WEEK old (>> bundle_expiry_bars=20 on 1h)
confs = [{"cid": c.cid, "t_confirm_ms": as_of - WEEK - (5 - i) * 60000,
          "p_confirm": 100.0 + i}
         for i, c in enumerate(expected_components(fw))]
res = run_engine(bars, events=confs, framework_id=fw, as_of_ms=as_of)
b = res["bundle"]
print("bundle from week-old confirmations:", b is not None)
print("fate=%s age_bars=%s integrity=%.3f" % (b.fate, b.age_bars, b.integrity))
assert b is not None and b.age_bars == 0 and b.fate == "active"

# update_bundle_fate exists and would expire it, but nothing calls it:
b2 = update_bundle_fate(b, bars_since=21)
print("update_bundle_fate(bars_since=21) ->", b2.fate)
grep = subprocess.run(
    ["grep", "-rn", "update_bundle_fate", "apex/"],
    capture_output=True, text=True).stdout.strip().splitlines()
print("in-tree references to update_bundle_fate:")
for line in grep:
    print("  ", line)
callers = [l for l in grep if "def update_bundle_fate" not in l
           and "__init__.py" not in l and "\"update_bundle_fate\"" not in l]
print("non-definition, non-reexport callers in apex/:", callers)
assert callers == []
print("Q-003 CONFIRMED: no staleness bound on confirmations; fate machine "
      "never driven (no caller of update_bundle_fate)")
