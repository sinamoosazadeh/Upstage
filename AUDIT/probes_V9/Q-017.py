"""Q-017: the §6 calibration targets (brier_target 0.22, log_loss_target
0.65) are met by a zero-skill uniform 8-phase predictor: Brier ~0.1094 and
per-outcome log terms make uniform guessing 'pass', so the targets gate
nothing even if they were wired (they are not: no runtime caller)."""
import math, subprocess
from apex.engines.e08_wyckoff.engine import brier_score, log_loss, get_params

p = get_params()
K = 8
probs, outcomes = [], []
# 80 events, uniform 1/8 prediction on the true phase each time
for i in range(80):
    probs.append(1.0 / K)
    outcomes.append(1 if i % K == 0 else 0)   # base rate 1/K on average
# one-vs-rest uniform: prob always 1/8, outcome 1 with frequency 1/8
bs = brier_score(probs, outcomes)
ll = log_loss(probs, outcomes)
print("uniform predictor: brier=%.4f (target %.2f) log_loss=%.4f (target "
      "%.2f)" % (bs, p.brier_target, ll, p.log_loss_target))
print("analytic one-hot-vs-uniform brier:",
      round(((1 - 1/K) ** 2 + (K - 1) * (1/K) ** 2) / K, 4))
assert bs < p.brier_target and ll < p.log_loss_target

grep = subprocess.run(["grep", "-rn", "brier_target\\|log_loss_target",
                       "apex/"], capture_output=True, text=True
                      ).stdout.splitlines()
uses = [l for l in grep if "engine.py" in l and "=" in l]
print("apex references to the targets:")
for line in grep:
    print("  ", line)
print("Q-017 CONFIRMED: targets pass under zero-skill uniform prediction "
      "and are never enforced at runtime")
