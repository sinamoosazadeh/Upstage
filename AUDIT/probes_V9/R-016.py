"""R-016: evidence conversion and the state projection ignore run-time
parameter overrides: _to_evidence normalizes strength with
p_default().impulse_z / stamps parameter_version 'DEFAULTS-v1', and
momentum_state_projection hardcodes th_imp = 2.0 — an engine run with
impulse_z=4.0 is misrepresented downstream."""
import inspect
from apex.engines.e10_momentum.engine import (run_engine,
                                              momentum_state_projection,
                                              E10MomentumEngine)

bars = []
px = 100.0
for i in range(70):
    r = 0.0005 if i < 60 else 0.018       # mz ends up between 2 and 4
    px *= 1 + r
    bars.append({"ts": i * 3600_000, "o": px / (1 + r), "h": px * 1.001,
                 "l": px / (1 + r) * 0.999, "c": px, "v": 1000.0})
res = run_engine(bars, params={"impulse_z": 4.0})
st = res["state"]
mz = st["momentum"]["momentum_z"]
print("mz=%.3f with impulse_z=4.0 -> impulse_bull=%s (engine says NO "
      "impulse)" % (mz, st["events"]["impulse_bull"]))
proj = momentum_state_projection(st)
print("projection:", proj)
psrc = inspect.getsource(momentum_state_projection)
assert "th_imp = 2.0" in psrc
print("projection hardcodes th_imp=2.0 (source check: True)")

# _to_evidence: strength normalized by DEFAULT impulse_z & versioned as
# DEFAULTS-v1 regardless of the overridden run
e = E10MomentumEngine()
e._last_n_bars = res["n_bars"]
# fabricate a neutral catalog item routed through the impulse branch
ev = e._to_evidence({"code": "EV_MOM_008", "as_of": st["as_of"]},
                    "BTCUSDT", "1h", 0.9, st)
print("evidence: strength=%.4f parameter_version=%s" % (
    ev.strength, ev.parameter_version))
print("expected under override impulse_z=4: %.4f" % min(1, abs(mz) / 8.0))
assert ev.parameter_version.endswith("DEFAULTS-v1")
assert abs(ev.strength - min(1.0, abs(mz) / 4.0)) < 1e-12  # 2*default(2.0)
print("R-016 CONFIRMED: evidence layer and projection use frozen defaults "
      "(2.0), not the parameters the engine actually ran with")
