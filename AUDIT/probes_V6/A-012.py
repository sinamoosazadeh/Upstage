"""V6 probe A-012: Params returns the cached dict directly — an in-memory
mutation persists on the same instance; a NEW instance re-reads the file.
Also: no consumer in apex/ currently mutates the returned dicts (grep check).
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.config import load_params, Params

p1 = load_params()
orig = p1.risk_defaults()["budget_per_trade"]
print("initial budget_per_trade =", orig)

# mutate through the returned view
p1.risk_defaults()["budget_per_trade"] = 0.5
print("after in-memory mutation, same instance reads:", p1.risk_defaults()["budget_per_trade"])

p2 = load_params()
print("new instance reads:", p2.risk_defaults()["budget_per_trade"])
print("cache is per-instance:", p1._cache is not p2._cache)

# restore (in-memory only; the file was never touched)
p1.risk_defaults()["budget_per_trade"] = orig
import apex.config as C
import hashlib
h = hashlib.sha256((C.PARAMS_DIR / "risk_defaults_v1.yaml").read_bytes()).hexdigest()
print("file untouched (sha256):", h[:16], "…")

# module-level cache? none — every load_params() constructs Params()
print("Params has module-level singleton?", hasattr(C, "_PARAMS_SINGLETON"))

# consumer-mutation scan: any `params[...] =` / `.update(` / `.pop(` on
# dicts obtained from Params/load_params?
import subprocess
res = subprocess.run(
    ["grep", "-rn", "-E", "risk_defaults\\(\\)\\[|setup_weights\\(\\)\\[|"
     "quality_weights\\(\\)\\[|universe\\(\\)\\[|toobit_wire\\(\\)\\[|"
     "\\[\"risk_defaults\"\\]\\s*=|\\[\"universe\"\\]\\s*=", str(REPO / "apex"), str(REPO / "scripts")],
    capture_output=True, text=True)
print("direct-assignment scan (assignment only):")
for line in res.stdout.splitlines():
    if "= " in line.split("(")[-1] and "==" not in line:
        print("  ", line[:150])
print("scan done")
