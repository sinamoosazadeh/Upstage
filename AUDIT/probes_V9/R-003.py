"""R-003: the snapshot payload is only {v,a,mz,mvz,rsi,as_of,symbol,
interval,q}: impulse/exhaustion flags, divergence, params (impulse_z) are
outside the identity, so two engines with different impulse_z produce the
SAME snapshot_id while firing different EV_MOM catalog events."""
from apex.engines.e10_momentum.engine import run_engine

bars = []
px = 100.0
for i in range(70):
    r = 0.0005 if i < 67 else 0.025         # fresh 3-bar impulse at the end
    px *= 1 + r
    bars.append({"ts": i * 3600_000, "o": px / (1 + r), "h": px * 1.001,
                 "l": px / (1 + r) * 0.999, "c": px, "v": 1000.0})

r_low = run_engine(bars, params={"impulse_z": 2.0})
r_high = run_engine(bars, params={"impulse_z": 99.0})
s1, s2 = r_low["state"], r_high["state"]
print("mz = %.3f" % s1["momentum"]["momentum_z"])
print("impulse_z=2 : events=%s snapshot=%s" % (
    [e["code"] for e in r_low["events"]], s1["snapshot_id"]))
print("impulse_z=99: events=%s snapshot=%s" % (
    [e["code"] for e in r_high["events"]], s2["snapshot_id"]))
print("param_hash differs:", s1["param_hash"] != s2["param_hash"])
assert s1["events"]["impulse_bull"] != s2["events"]["impulse_bull"]
assert s1["snapshot_id"] == s2["snapshot_id"]
assert s1["param_hash"] != s2["param_hash"]
print("R-003 CONFIRMED: snapshot identity blind to event flags and "
      "parameters — same snapshot_id, different emitted events")
