"""Q-024: divergence_exhaustion_check ignores current_idx entirely (any
value gives the same answer), compares arbitrarily old swings against the
latest momentum values, and divergence_min_peak_distance is never used."""
import subprocess
from apex.engines.e09_trend.engine import divergence_exhaustion_check

mom = [0.5] * 19 + [0.1]
swings = [{"type": "HH", "price": 100.0, "idx": 3,
           "confirmed_at_idx": 4},          # ancient swings
          {"type": "HH", "price": 110.0, "idx": 4,
           "confirmed_at_idx": 5}]
for cur in (-999, 0, 5, 10_000):
    r = divergence_exhaustion_check(swings, mom, cur)
    print("current_idx=%6d -> %s score=%s" % (cur, r["type"], r["score"]))
r0 = divergence_exhaustion_check(swings, mom, 0)
r1 = divergence_exhaustion_check(swings, mom, 10_000)
assert r0 == r1 and r0["is_exhaustion"], "current_idx is a dead parameter"
# swings at idx 3,4 (adjacent, distance 1 < min_peak_distance 5) still pair
print("adjacent peaks (distance 1) produced divergence:",
      r0["type"])
g = subprocess.run(["grep", "-rn", "divergence_min_peak_distance", "apex/"],
                   capture_output=True, text=True).stdout.splitlines()
print("divergence_min_peak_distance references:")
for line in g:
    print("  ", line)
uses = [l for l in g if "engine.py" in l and ":" in l
        and "int = 5" not in l and '"' not in l.split(":", 2)[2]]
uses = [l for l in uses if "divergence_min_peak_distance" in l.split(":", 2)[2]
        and "=" not in l.split(":", 2)[2].replace("min_peak_distance", "")]
print("consuming lines (excluding declaration):", uses)
print("Q-024 CONFIRMED: current_idx dead, no peak-distance or recency "
      "constraint; min_peak_distance param declared but never read")
