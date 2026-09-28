"""R-015: the governed §6 parameter mom_window (14) is declared in
E10_DEFAULTS but never read by any computation: two engines with
mom_window 5 vs 14 produce bit-identical states (except param_hash)."""
import json, re, subprocess
from apex.engines.e10_momentum.engine import run_engine

src = open("apex/engines/e10_momentum/engine.py").read()
uses = [m for m in re.finditer(r"mom_window", src)]
lines = [src[:m.start()].count("\n") + 1 for m in uses]
print("mom_window occurrences at lines:", lines)
ctx = [src.splitlines()[l - 1].strip() for l in lines]
for c in ctx:
    print("  ", c)
reads = [c for c in ctx if "E10_DEFAULTS" not in c and '"mom_window": 14'
         not in c and "p.mom_window" in c]
print("computational reads:", reads)
assert reads == []
g = subprocess.run(["grep", "-rn", "mom_window", "apex/"],
                   capture_output=True, text=True).stdout.splitlines()
others = [l for l in g if "e10_momentum" not in l]
print("uses outside e10:", others)

bars = []
px = 100.0
for i in range(80):
    px *= 1.0 + (0.003 if i % 3 else -0.002)
    bars.append({"ts": i * 3600_000, "o": px, "h": px * 1.002,
                 "l": px * 0.998, "c": px, "v": 1000.0 + i})
r5 = run_engine(bars, params={"mom_window": 5})
r14 = run_engine(bars, params={"mom_window": 14})
s5, s14 = dict(r5["state"]), dict(r14["state"])
ph5, ph14 = s5.pop("param_hash"), s14.pop("param_hash")
same = json.dumps(s5, sort_keys=True, default=str) == \
       json.dumps(s14, sort_keys=True, default=str)
print("states identical apart from param_hash:", same,
      "| param_hash differ:", ph5 != ph14)
assert same and ph5 != ph14
print("R-015 CONFIRMED: mom_window is a dead governed parameter; only "
      "param_hash moves")
