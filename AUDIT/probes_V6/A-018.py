"""V6 probe A-018: ECEntry checks only PRESENCE of the 12 fields and the
status literal. An APPROVED entry with value=2 outside allowed_bounds=[0,1],
sample=0 and required_test=False still yields active_value() == 2.
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.research import governance as gov

sem = {
    "semantic_question": "q", "unit": "ratio", "scope": "global",
    "allowed_bounds": [0, 1], "measurement_method": "none",
    "dataset": "NA", "sample": 0, "uncertainty": "NA",
    "required_test": False, "fallback": "conservative",
    "behavior_if_unresolved": "conservative", "status": "APPROVED",
    "value": 2,           # outside allowed_bounds [0,1]
}
e = gov.ECEntry(name="ec_probe", semantics=sem, status="APPROVED")
reg = gov.ECRegister()
reg.register(e)
print("has_active_value:", e.has_active_value)
print("active_value:", reg.active_value("ec_probe"), "(allowed_bounds were [0,1])")
print("conservative():", e.conservative())

print()
print("== missing field is caught (control) ==")
try:
    gov.ECEntry(name="bad", semantics={k: v for k, v in sem.items() if k != "sample"},
                status="OPEN")
    print("missing field NOT caught")
except gov.GovernanceError as ex:
    print("caught:", ex.reason, "|", ex.detail)

print()
print("== who consumes ECRegister.active_value at runtime? ==")
import subprocess
r = subprocess.run(["grep", "-rn", "active_value\\|ECRegister", str(REPO / "apex")],
                   capture_output=True, text=True)
print(r.stdout if r.stdout else "no consumer outside governance.py itself")
r2 = subprocess.run(["grep", "-rn", "active_value\\|ECRegister", str(REPO / "tests")],
                    capture_output=True, text=True)
print("tests referencing it:", len(r2.stdout.splitlines()), "lines")
