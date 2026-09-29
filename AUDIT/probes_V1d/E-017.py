"""V1d probe E-017 — X.2 "EXTREME => trailing disabled" vs an explicit
trail_atr_mult. READ-ONLY verification of the REAL
apex.playbook.pb_fvg_sweep_rev_a.trailing_state / trail_factor_for."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from apex.playbook.pb_fvg_sweep_rev_a import (
    PLAYBOOK_PARAMS, trail_factor_for, trailing_state)

COMMON = dict(entry=100.0, current_stop=98.0, direction=1, atr=1.0,
              trail_after_r=PLAYBOOK_PARAMS["trail_after_r"])

print("PLAYBOOK_PARAMS trail:", PLAYBOOK_PARAMS["trail_after_r"],
      PLAYBOOK_PARAMS["trail_atr_mult"])

# fallback path (no explicit multiplier): EXTREME disables trailing
fb = trailing_state(current=110.0, volatility_regime="EXTREME",
                    trail_atr_mult=None, **COMMON)
print("fallback (mult=None), EXTREME ->", {k: fb[k] for k in
      ("activated", "trailing_disabled_by_regime", "stop", "reason")})

# explicit playbook multiplier 1.0: EXTREME does NOT disable trailing
ex = trailing_state(current=110.0, volatility_regime="EXTREME",
                    trail_atr_mult=1.0, **COMMON)
print("explicit mult=1.0,    EXTREME ->", {k: ex.get(k) for k in
      ("activated", "trailing_disabled_by_regime", "stop", "reason", "distance")})

# package path: EXTREME still disables (trail_factor_for handles it)
pk = trailing_state(current=110.0, volatility_regime="EXTREME",
                    trail_atr_mult=None, package={"trail_factor": 2.0}, **COMMON)
print("package trail_factor=2, EXTREME ->", {k: pk.get(k) for k in
      ("activated", "trailing_disabled_by_regime", "stop", "reason")})

# sanity: NORMAL with explicit multiplier activates (existing behaviour)
nm = trailing_state(current=110.0, volatility_regime="NORMAL",
                    trail_atr_mult=1.0, **COMMON)
print("explicit mult=1.0,    NORMAL  ->", {k: nm.get(k) for k in
      ("activated", "stop", "distance")})

# short mirror with explicit multiplier under EXTREME
sh = trailing_state(entry=100.0, current_stop=102.0, direction=-1, atr=1.0,
                    current=90.0, volatility_regime="EXTREME",
                    trail_after_r=1.5, trail_atr_mult=1.0)
print("SHORT explicit mult=1.0, EXTREME ->", {k: sh.get(k) for k in
      ("activated", "trailing_disabled_by_regime", "stop")})

print("trail_factor_for('EXTREME') ->", trail_factor_for("EXTREME"))
