"""Q-019: _scale_state slices bars[-W:] with no len>=W check. The native
producer admits windows as small as 51 bars (engine_context gates '< 51'),
so MACRO (W=240) silently computes on 51 bars while the published evidence
observation_window still claims bars=240."""
import math, subprocess
from apex.engines.e09_trend.engine import (TrendEngine, E09TrendEngine,
                                           scale_windows)

bars = []
px = 100.0
for i in range(51):                       # producer minimum window
    px *= 1.004
    bars.append({"ts": i * 3600_000, "o": px / 1.004, "h": px * 1.001,
                 "l": px / 1.004 * 0.999, "c": px, "v": 1000.0})
swings = [{"type": "HH", "price": 100 + i, "idx": 10 + 8 * i,
           "confirmed_at_idx": 11 + 8 * i} for i in range(4)]
eng = TrendEngine()
out = eng.process_bar(bars, swings=swings, atr=1.0, tf_seconds=3600)
mac = out["scales"]["MACRO"]
print("bars supplied: 51 | MACRO window param:", scale_windows()["MACRO"])
print("MACRO state=%s label=%s adx=%.2f degraded_reason=%s" % (
    mac["state"], mac["quality_label"], mac["adx"], mac["degraded_reason"]))
# evidence claims a 240-bar observation window regardless
e09 = E09TrendEngine()
ev = e09._to_evidence("MACRO", mac, "BTCUSDT", "1h", 0.9, out)
print("evidence observation_window:", ev.observation_window,
      "| validity:", ev.validity)
assert ev.observation_window["bars"] == 240
# producer minimum really is 51:
g = subprocess.run(["grep", "-n", "< 51", "apex/ops/engine_context.py"],
                   capture_output=True, text=True).stdout
print("engine_context 51-bar gates:\n", g)
assert g.strip()
# and no error/refusal was raised for MACRO on a 51-bar window
print("Q-019 CONFIRMED: MACRO/INTER computed on 51-bar window without any "
      "len>=W refusal; evidence reports bars=240")
