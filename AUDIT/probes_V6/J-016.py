"""V6 probe J-016: EV_MOM_007 (<0.2 D_mag filter) applies ONLY to the OLS
same-sign path; the PIVOT divergence path emits events with D_mag < 0.2 with
no 0.2 gate (its own D_mag_min is 0.05). Uses the repo's own golden fixtures.
"""
import json
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.engines.e10_momentum.engine import (
    classify_pivot_pair, divergence_mag_pivot, divergence_mag_ols,
    EngineParams)

fx = json.loads((REPO / "tests" / "fixtures" / "e10_golden_fixtures.json")
                .read_text())
BY_ID = {f["id"]: f for f in fx["fixtures"]}

p = EngineParams()
print("engine params: convergence_dmag_max =", p.convergence_dmag_max,
      "| price_delta_pct =", p.price_delta_pct, "| mom_delta =", p.mom_delta)

print()
print("== pivot path: the document's own BNBUSDT example (D_mag 0.078) ==")
f7 = BY_ID["GF07_Div_Regular_Bearish_Pivot"]
p1, p2 = f7["price_pivots"]
m1, m2 = f7["mom_pivots"]
kind, proof = classify_pivot_pair(p1["price"], p2["price"], m1["value"],
                                  m2["value"], "HIGH")
dm = divergence_mag_pivot(p1["price"], p2["price"], m1["value"], m2["value"])
print("GF07 classify_pivot_pair -> kind:", kind, "| D_mag:", round(dm, 6))
print("fixture expected:", f7["expected"])
print("D_mag", round(dm, 4), "< 0.2 but kind is a VALID divergence event:",
      kind is not None and dm < 0.2)
print("=> the 0.2 filter does NOT gate the pivot path (its own min is",
      f7["expected"]["D_mag_min"], ")")

print()
print("== OLS path: same-sign low D_mag => CONVERGENCE + EV_MOM_007 ==")
f11 = BY_ID["GF11_OLS_Slope"]
from apex.engines.e10_momentum.engine import ols_slope
bp, _ = ols_slope(f11["price_series"])
bm, _ = ols_slope(f11["mom_series"])
print("GF11 beta_price:", bp, "beta_mom:", bm, "(opposite signs -> divergence)")

# same-sign low-magnitude OLS case per engine code:
d_ols = divergence_mag_ols(0.001, 0.0011)
print("divergence_mag_ols(same-sign small) =", d_ols, "-> would be <",
      p.convergence_dmag_max, "=> CONVERGENCE/EV_MOM_007 path")
print()
print("ISSUE-CP5-006 CLOSED text says generally: 'D_mag < 0.2 => filtered + EV_MOM_007'")
print("E10 §9 Risk scopes it to 'strongly range-bound market' (L11431-11432)")
print("E10 §11 examples treat D_mag 0.078/0.09 as VALID pivot divergences (L11435-11437)")
