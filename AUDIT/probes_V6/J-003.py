"""V6 probe J-003: F70 temporal_window and F71 utc_activity_window share ONE
full_id; the registry has 74 aliases but 73 distinct full_ids; lookup by that
full_id returns F71 only.
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.data_catalog.catalog import build_registry

registry, computers = build_registry()

full_ids = {}
for c in registry.all():
    full_ids.setdefault(c.id.full_id, []).append(c.id.alias)

print("registry count (aliases):", registry.count())
print("distinct full_ids:", len(full_ids))
dupes = {k: v for k, v in full_ids.items() if len(v) > 1}
print("full_ids used by more than one alias:", dupes)

fid = "APEX.L00.ORGN.CTXT.UTC_ACTIVITY_WINDOW.SCORE.V1"
got = registry.lookup(fid)
print("lookup(%r) ->" % fid, "alias=%s" % got.id.alias)

f70 = registry.lookup("temporal_window")
f71 = registry.lookup("utc_activity_window")
print("F70 alias lookup:", f70.id.alias, f70.id.full_id)
print("F71 alias lookup:", f71.id.alias, f71.id.full_id)
print("F70.full_id == F71.full_id:", f70.id.full_id == f71.id.full_id)

# registry index bookkeeping: _by_num is keyed by full_id (not a number)
print("_by_num keys are full_ids, not numbers:",
      all(isinstance(k, str) for k in registry._by_num.keys()))

# are both context-gated/UNAVAILABLE currently?
import inspect
src70 = inspect.getsource(computers["temporal_window"])
src71 = inspect.getsource(computers["utc_activity_window"])
print("F70 computer mentions UNAVAILABLE/context:",
      "UNAVAILABLE" in src70 or "context" in src70.lower())
print("F71 computer mentions UNAVAILABLE/context:",
      "UNAVAILABLE" in src71 or "context" in src71.lower())

# who consumes 'temporal_window' vs 'utc_activity_window' downstream?
import subprocess
r = subprocess.run(["grep", "-rn", "-e", "temporal_window", "-e", "utc_activity_window",
                    str(REPO / "apex")], capture_output=True, text=True)
consumers = {}
for line in r.stdout.splitlines():
    if "data_catalog" in line or "__pycache__" in line:
        continue
    if "utc_activity_window" in line:
        consumers.setdefault("utc_activity_window (outside catalog)", []).append(line.split(":")[0])
    elif "temporal_window" in line:
        consumers.setdefault("temporal_window (outside catalog)", []).append(line.split(":")[0])
for k, v in consumers.items():
    print(k, "->", sorted(set(v))[:8])
if not consumers:
    print("no downstream consumers outside apex/data_catalog")
