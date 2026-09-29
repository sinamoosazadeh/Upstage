"""V1d probe E-019 — apply_partial_exit ladder validation.
READ-ONLY verification of the REAL
apex.playbook.pb_fvg_sweep_rev_a.apply_partial_exit / PLAYBOOK_PARAMS."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from apex.playbook.pb_fvg_sweep_rev_a import (
    PLAYBOOK_PARAMS, apply_partial_exit)

print("frozen ladder:", PLAYBOOK_PARAMS["staged_exit_ratios"])

# (1) negative weight passes the sum>0 gate and INCREASES size and risk
got = apply_partial_exit(sized_quantity=10.0, reserved_risk=4.0,
                         ladder_weights=(-0.5, 1.5), taken_index=0,
                         current_stop=99.0, direction=1)
print("(1) weights (-0.5, 1.5), take idx 0 -> qty=%s risk=%s share=%s" %
      (got["sized_quantity"], got["reserved_risk"], got["closed_fraction"]))

# (2) NaN weight passes (NaN comparisons are False) and yields NaN size
got_nan = apply_partial_exit(sized_quantity=10.0, reserved_risk=4.0,
                            ladder_weights=(float("nan"), 1.0), taken_index=0,
                            current_stop=99.0, direction=1)
print("(2) weights (nan, 1.0), take idx 0 -> qty=%s risk=%s share=%s" %
      (got_nan["sized_quantity"], got_nan["reserved_risk"],
       got_nan["closed_fraction"]))

# (3) sequential 30/40/30 on the REMAINDER leaves qty behind
qty, risk = 10.0, 4.0
for i, w in enumerate((0.3, 0.4, 0.3)):
    r = apply_partial_exit(sized_quantity=qty, reserved_risk=risk,
                           ladder_weights=(0.3, 0.4, 0.3), taken_index=i,
                           current_stop=99.0, direction=1)
    qty, risk = r["sized_quantity"], r["reserved_risk"]
    print("(3) step %d (weight %.1f) -> remaining qty=%.4f risk=%.4f" %
          (i, w, qty, risk))
print("    after all three ladder steps: qty=%s (expected 0 if weights sum "
      "to 1 over the initial size)" % qty)

# (4) repeated take of the SAME index is not refused
r4a = apply_partial_exit(sized_quantity=10.0, reserved_risk=4.0,
                         ladder_weights=(0.5, 0.5), taken_index=0,
                         current_stop=99.0, direction=1)
r4b = apply_partial_exit(sized_quantity=r4a["sized_quantity"],
                         reserved_risk=r4a["reserved_risk"],
                         ladder_weights=(0.5, 0.5), taken_index=0,
                         current_stop=99.0, direction=1)
print("(4) take idx 0 twice -> qty=%s risk=%s (no duplicate-index refusal)" %
      (r4b["sized_quantity"], r4b["reserved_risk"]))

# (5) the frozen single-rung ladder (1.0,) still zeroes out correctly
r5 = apply_partial_exit(sized_quantity=10.0, reserved_risk=4.0,
                        ladder_weights=(1.0,), taken_index=0,
                        current_stop=99.0, direction=1)
print("(5) frozen ladder (1.0,) -> qty=%s risk=%s" %
      (r5["sized_quantity"], r5["reserved_risk"]))
print("    math.floor check:", math.isclose(r5["sized_quantity"], 0.0))
