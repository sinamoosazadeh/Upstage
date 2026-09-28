"""V6 probe J-006: Z.8 Scenario A mixes '27 wins/42' (raw) with p_hat=0.58
(cost-adjusted) inside the same Wilson computation. Check what the REAL code
does (z8_scenarios uses k=27, n=42), and what Wilson(0.58, n=42) would give.
"""
import math
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.research.promotion import z8_scenarios, wilson_gate, family_pool_gate

z8 = z8_scenarios()
for name, s in z8["scenarios"].items():
    print(name, "->", {k: (round(v, 4) if isinstance(v, float) else v)
                       for k, v in s.items() if k in
                       ("n", "wins", "quoted_lower", "recomputed_lower", "delta",
                        "consistent", "quoted_decision", "recomputed_decision",
                        "decision_consistent")})
print("all_lower_bounds_consistent:", z8["all_lower_bounds_consistent"])
print("all_decisions_consistent:", z8["all_decisions_consistent"])

print()
print("== direct Wilson for the DOCUMENT's stated p_hat=0.58, n=42 ==")


def wilson_lower(n, k, z=1.96):
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - margin) / denom


print("Wilson(k=27,n=42)  =", round(wilson_lower(42, 27), 4), "(code's k; p_hat=27/42=0.643)")
print("Wilson(p_hat=.58 -> k=24.36,n=42) not an integer count")
print("Wilson(k=24,n=42)  =", round(wilson_lower(42, 24), 4), "<- 24/42 = 0.571")
print("Wilson(k=25,n=42)  =", round(wilson_lower(42, 25), 4), "<- 25/42 = 0.595")
print("Wilson(0.58 exact, n=42):", round(
    ((0.58 + 1.96**2/84 - 1.96*math.sqrt(0.58*0.42/42 + 1.96**2/(4*42**2)))
     / (1 + 1.96**2/42)), 4))
print()
print("verdict at 0.48 breakeven with k=24 (24<25 needed):",
      "ALLOWED" if wilson_lower(42, 24) > 0.48 else "BLOCKED")
print("verdict with k=25:",
      "ALLOWED" if wilson_lower(42, 25) > 0.48 else "BLOCKED")
print()
print("0.58 * 42 =", 0.58 * 42, "(not an integer win count)")
print()
print("== B_3months row: doc says 22/35 adjusted 0.58 LB≈46% still blocked ==")
print("Wilson(k=22,n=35) =", round(wilson_lower(35, 22), 4))
print("code's recomputed decision:", z8["scenarios"]["B_3months"]["recomputed_decision"])
print()
print("== who consumes z8_scenarios? ==")
import subprocess
r = subprocess.run(["grep", "-rn", "z8_scenarios", str(REPO)], capture_output=True, text=True)
print(r.stdout if r.stdout else "(only definition/tests)")
