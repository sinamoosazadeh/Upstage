"""Q-025: EV_TRD_003 carries the constant params.divergence_score (0.8),
never the §3.7 ExhaustionScore = Div*(1-strength)*(1-ADX/100); the
exhaustion_score function has no caller."""
import subprocess
from apex.engines.e09_trend.engine import TrendEngine, exhaustion_score

import math
bars = []
for i in range(60):                          # choppy market -> weak strength
    c = 100 + math.sin(i * 0.9) * 2
    bars.append({"ts": i * 3600_000, "o": c, "h": c + 2.5, "l": c - 2.5,
                 "c": c, "v": 1000.0})
mom = [0.5] * 59 + [0.1]                     # momentum lower high
# mixed swing types (seq_score ~ 0) but ascending last-two prices
swings = [{"type": "HH", "price": 95.0, "idx": 40, "confirmed_at_idx": 41},
          {"type": "LL", "price": 90.0, "idx": 44, "confirmed_at_idx": 45},
          {"type": "HH", "price": 100.0, "idx": 50, "confirmed_at_idx": 51},
          {"type": "LL", "price": 110.0, "idx": 54, "confirmed_at_idx": 55}]
eng = TrendEngine()
out = eng.process_bar(bars, swings=swings, atr=50.0, mom_series=mom,
                      tf_seconds=3600)
ev3 = [e for e in eng.events if e["code"] == "EV_TRD_003"]
print("EV_TRD_003:", ev3)
assert ev3, "divergence event expected"
short = out["scales"]["SHORT"]
true_score = exhaustion_score(1.0, short["strength"], short["adx"])
print("emitted score=%.3f | §3.7 exhaustion_score=%.4f (strength=%.3f "
      "adx=%.2f)" % (ev3[0]["score"], true_score, short["strength"],
                     short["adx"]))
assert ev3[0]["score"] == 0.8 and abs(true_score - 0.8) > 1e-6

g = subprocess.run(["grep", "-rn", "exhaustion_score", "apex/"],
                   capture_output=True, text=True).stdout.splitlines()
callers = [l for l in g if "def exhaustion_score" not in l
           and "__init__.py" not in l and '"exhaustion_score"' not in l]
print("exhaustion_score callers:", callers)
assert callers == []
print("Q-025 CONFIRMED: constant 0.8 emitted; §3.7 formula dead code")
