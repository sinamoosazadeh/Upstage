"""V6 probe J-008: PHASE2_HANDOFF_CP8.md INTERFACES table vs the real API.
Checks, by IMPORT of the real modules:
  - apex.research.proxies.concept / by_layer  (documented) — exist?
  - apex.research.governance.validate_proposal (documented) — exists?
  - BacktestEngine(..., start_index=...) constructor param (documented) — exists?
  - ECRegister.add (documented) — exists?
  - sensitivity_candidate(s1_over_st, ...) (documented) — exists?
"""
import inspect
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import apex.research.proxies as px
import apex.research.governance as gov
import apex.research.backtest as bt
import apex.research.promotion as pr

print("proxies has 'concept':", hasattr(px, "concept"))
print("proxies has 'by_layer':", hasattr(px, "by_layer"))
print("proxies public callables:", sorted(n for n in dir(px) if not n.startswith("_")
                                          and callable(getattr(px, n))))
print()
print("governance has 'validate_proposal':", hasattr(gov, "validate_proposal"))
print("governance actual validate* :", [n for n in dir(gov) if n.startswith("validate")])
print()
sig = inspect.signature(bt.BacktestEngine.__init__)
print("BacktestEngine.__init__ params:", list(sig.parameters))
print("start_index in constructor:", "start_index" in sig.parameters)
print("BacktestEngine.run params:", list(inspect.signature(bt.BacktestEngine.run).parameters))
print()
print("ECRegister has 'add':", hasattr(gov.ECRegister, "add"))
print("ECRegister actual methods:", [n for n in dir(gov.ECRegister) if not n.startswith("_")])
print()
print("governance has 'sensitivity_candidate':", hasattr(gov, "sensitivity_candidate"))
print("actual:", [n for n in dir(gov) if "sensitiv" in n.lower()])
print("signature:", inspect.signature(gov.sensitivity_removal_candidate))
print()
print("promotion has 'SPRTState/sprt_step/sprt_monitor':",
      all(hasattr(pr, n) for n in ("SPRTState", "sprt_step", "sprt_monitor")))
print("backtest has walk_forward/evaluate_wfo/monte_carlo/cvar_bootstrap/stress_battery/apply_stress:",
      all(hasattr(bt, n) for n in ("walk_forward", "evaluate_wfo", "monte_carlo",
                                   "cvar_bootstrap", "stress_battery", "apply_stress")))
