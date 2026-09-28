"""Q-008: econ_events defaults to None and the native producer never passes
an economic calendar, so econ_conflict is structurally always False and the
x0.7 kz penalty + the Q5 'calendar clear' gate are vacuous in production."""
import datetime, inspect, subprocess
from apex.engines.e07_rtm.engine import utc_activity_window_check
import apex.ops.engine_context as ec

ts = int(datetime.datetime(2026, 3, 2, 13, 0,
                           tzinfo=datetime.timezone.utc).timestamp() * 1000)
kz = utc_activity_window_check(ts)                    # producer-shaped call
print("default call: econ_conflict =", kz["econ_conflict"])
kz_hi = utc_activity_window_check(
    ts, econ_events=[{"time_ms": ts, "impact": "HIGH"}])
print("with HIGH event: econ_conflict =", kz_hi["econ_conflict"],
      "(mechanism works when fed)")

# The native producer call site: grep engine_context for the E07 context
grep = subprocess.run(
    ["grep", "-n", "econ_events\\|E07RTMEngine\\|e07", 
     "apex/ops/engine_context.py"], capture_output=True, text=True
    ).stdout.strip().splitlines()
print("engine_context.py lines mentioning econ_events/E07:")
for line in grep:
    print("  ", line)
econ_feeds = [l for l in grep if "econ_events" in l]
print("producer lines passing econ_events:", econ_feeds)
assert econ_feeds == [], "producer does pass econ_events somewhere"
print("Q-008 CONFIRMED: no econ calendar source wired anywhere in the "
      "producer; econ_conflict is constant False natively")
