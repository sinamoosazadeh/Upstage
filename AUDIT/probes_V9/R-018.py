"""R-018: Q4 ('STATISTICAL') is granted purely by method==BOTH plus
len(candles)>=100 — no Wilson CI, no divergence_success outcome tracking,
no calibration_report is consulted anywhere at runtime."""
import math, subprocess
from apex.engines.e10_momentum.engine import (MomentumEngine, get_params,
                                              candle_from_bar)

eng = MomentumEngine(get_params())
px = 100.0
last = None
for i in range(130):
    r = 0.004 * math.exp(-i / 60.0) + 0.0025 * math.sin(i / 2.5)
    px *= (1 + r)
    st = eng.update(candle_from_bar(
        {"ts": i * 3600_000, "o": px / (1 + r), "h": px * 1.001,
         "l": px / (1 + r) * 0.999, "c": px, "v": 1000.0 + 10 * i}))
    if "events" in st:
        last = st
div = last["events"]["divergence"]
print("q_tag=%s method=%s kind=%s candles=%d" % (
    last["q_tag"], div["method"], div["kind"], len(eng.candles)))
assert last["q_tag"] == "Q4" and div["method"] == "BOTH"

for fn in ("wilson_ci", "divergence_success", "calibration_report"):
    g = subprocess.run(["grep", "-rn", fn, "apex/"],
                       capture_output=True, text=True).stdout.splitlines()
    callers = [l for l in g if "e10_momentum" in l and f"def {fn}" not in l
               and f'"{fn}"' not in l and "__init__" not in l
               and not l.split(":", 2)[2].strip().startswith("#")]
    print(f"{fn}: runtime callers in e10 = {callers}")
print("R-018 CONFIRMED: Q4 without any statistical out-of-sample gate; "
      "the §8 statistical machinery is dead code at runtime")
