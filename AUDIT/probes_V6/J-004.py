"""V6 probe J-004: verify_completeness claims to check §3.13 closure item (2)
(F73 Parameters/Validity/Consumers/Tests) but the loop `for field …: _ = field`
checks nothing; the runtime FeatureContract does not even carry
parameters/consumers/tests fields. Mutating an in-memory contract to drop
formula/outputs/confidence_equation still leaves the gate PASS.
"""
import dataclasses
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.data_catalog import catalog as cat_mod
from apex.data_catalog.catalog import build_registry
from apex.data_catalog.contracts import FeatureContract

registry, computers = build_registry()
c = cat_mod.Catalog()

# 1) fields the runtime contract actually has
print("FeatureContract fields:", [f.name for f in dataclasses.fields(FeatureContract)])
print("has 'parameters' field:", any(f.name == "parameters" for f in dataclasses.fields(FeatureContract)))
print("has 'consumers' field:", any(f.name == "consumers" for f in dataclasses.fields(FeatureContract)))
print("has 'tests' field:", any(f.name == "tests" for f in dataclasses.fields(FeatureContract)))

# 2) the no-op loop in verify_completeness
import inspect
src = inspect.getsource(cat_mod.Catalog.verify_completeness)
for line in src.splitlines():
    if "_ = field" in line or "for field" in line:
        print("verbatim:", line.strip())

def with_replaced(alias, **changes):
    reg = cat_mod.FeatureRegistry()
    for contract in registry.all():
        reg.register(dataclasses.replace(contract, **changes)
                     if contract.id.alias == alias else contract)
    cat = cat_mod.Catalog()
    cat._registry = reg            # in-memory swap; no repository change
    return cat

# 3) in-memory mutation: blank out formula/outputs/confidence_equation of F73
out = with_replaced("volatility_regime", formula="", outputs=(),
                    confidence_equation="").verify_completeness()
print("verify_completeness with gutted F73:", out)

# 4) same for F74
out3 = with_replaced("sweep", formula="", outputs=(),
                     confidence_equation="").verify_completeness()
print("verify_completeness with gutted F74:", out3)

# 5) control: an actually-enforced check — F73 validity emptied DOES fail
try:
    out4 = with_replaced("volatility_regime", validity=None).verify_completeness()
    print("gutted validity still PASS:", out4)
except ValueError as e:
    print("control: gutted validity -> ValueError:", e)

# 6) control: F73 dependencies emptied fails
try:
    out5 = with_replaced("volatility_regime", dependencies=()).verify_completeness()
    print("gutted dependencies still PASS:", out5)
except ValueError as e:
    print("control: gutted dependencies -> ValueError:", e)
