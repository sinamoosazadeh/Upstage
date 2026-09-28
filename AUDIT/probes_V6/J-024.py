"""V6 probe J-024: §17.1 SL-12 table (budget_per_trade 1.0%, k_attn 0.05) vs
frozen YAML (0.005 / 0.25). D8/ISSUE-CP8-001 make the YAML the runtime
authority; assert_yaml_consistency only records doc_inconsistency; size()
loads the YAML values.
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.research.governance import assert_yaml_consistency, GOVERNED_DEFAULTS
from apex.risk.kernel import frozen_risk_params, size

for row in GOVERNED_DEFAULTS:
    if row.name in ("budget_per_trade", "k_attn"):
        print("governance §17.1 row:", row.name, "=", row.l1_default,
              "| yaml_ref:", row.yaml_ref)

print()
print("YAML (runtime source of record):")
r = frozen_risk_params()
print("  budget_per_trade =", r["budget_per_trade"], "| k_attn =", r["k_attn"])

print()
print("assert_yaml_consistency divergences:")
for d in assert_yaml_consistency():
    print("  ", d["name"], "| blueprint:", d["blueprint"],
          "| yaml:", d["yaml"], "| note:", d["note"])

print()
out = size(capital=10_000.0, stop_distance=100.0, min_quantity=0.001)
print("size() R_allowed =", out["R_allowed"],
      "(= 0.005 * 10000 -> YAML budget, NOT the §17.1 1.0%)")
out2 = size(capital=10_000.0, stop_distance=100.0, min_quantity=0.001,
            atr_cap=50.0)
print("size() attention bound with atr_cap=50:", out2["q_attention_bound"],
      "(= 0.25 * 50 -> YAML k_attn, NOT the §17.1 0.05)")
