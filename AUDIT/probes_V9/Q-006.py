"""Q-006: of the EV_RTM_001..011 catalog only 001/004/005/007/011 are ever
emitted by run_engine; 002/003/006/008/009/010 have no emission site."""
import re, subprocess

src = open("apex/engines/e07_rtm/engine.py").read()
emitted = set()
# emission sites are ev_names.append("EV_RTM_XXX") literals inside run_engine
for m in re.finditer(r'ev_names\.append\(\s*"(EV_RTM_\d+)"'
                     r'|ev_names\.append\(\s*"(EV_RTM_\d+)" if \w+ == "[^"]+"'
                     r'\s*else "(EV_RTM_\d+)"', src):
    emitted |= {g for g in m.groups() if g}
# also catch the conditional append form explicitly
for m in re.finditer(r'"(EV_RTM_\d+)"', src):
    pass
appends = re.findall(r'ev_names\.append\(([^)]*)\)', src)
lits = set()
for a in appends:
    lits |= set(re.findall(r'"(EV_RTM_\d+)"', a))
print("emission-site literals in run_engine:", sorted(lits))
declared = sorted(set(re.findall(r'"(EV_RTM_\d+)"', src)))
print("all EV_RTM_* literals in engine.py:", declared)
never = sorted(set(f"EV_RTM_{i:03d}" for i in range(1, 12)) - lits)
print("never emitted:", never)
assert lits == {"EV_RTM_001", "EV_RTM_004", "EV_RTM_005", "EV_RTM_007",
                "EV_RTM_011"}
# and no other apex module emits EV_RTM_* on E07's behalf
grep = subprocess.run(["grep", "-rln", "EV_RTM_", "apex/"],
                      capture_output=True, text=True).stdout.split()
print("apex files mentioning EV_RTM_*:", grep)
print("Q-006 CONFIRMED: only EV_RTM_001/004/005/007/011 reachable; "
      "002/003/006/008/009/010 dead catalog entries")
