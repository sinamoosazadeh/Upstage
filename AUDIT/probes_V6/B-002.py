"""V6 probe B-002: FSM SELF_TEST dependency check does not verify VERSIONS,
only importability. Runs the REAL _check_dependencies method in a subprocess
where each of the nine modules imports with a MISMATCHED __version__.
"""
import subprocess
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]

CHILD = r'''
import sys, types
sys.path.insert(0, {repo!r})
# fabric the nine SBOM modules with WRONG versions so __import__ succeeds
fake_versions = {{
    "aiohttp": "0.0.1", "aiogram": "0.0.1", "aiosqlite": "0.0.1",
    "matplotlib": "0.0.1", "pandas": "0.0.1", "numpy": "0.0.1",
    "pydantic": "0.0.1", "dateutil": "0.0.1", "pytz": "0.0.1",
}}
for name, ver in fake_versions.items():
    m = types.ModuleType(name)
    m.__version__ = ver
    sys.modules[name] = m
# submodule stubs some code imports transitively
sys.modules["dateutil.parser"] = types.ModuleType("dateutil.parser")
sys.modules["pydantic.dataclasses"] = types.ModuleType("pydantic.dataclasses")

from apex.execution.fsm import StartupReconciliation
import inspect
# locate the class that has _check_dependencies
src_cls = None
import apex.execution.fsm as fsm
for obj in vars(fsm).values():
    if inspect.isclass(obj) and hasattr(obj, "_check_dependencies") and obj.__module__ == "apex.execution.fsm":
        src_cls = obj
        break
print("class with _check_dependencies:", src_cls.__name__)
inst = src_cls.__new__(src_cls)   # skip __init__ (no DB / network)
res = inst._check_dependencies()
print("CheckResult:", res)
print("status:", res.status, "| passed:", res.passed, "| detail:", res.detail)
'''

r = subprocess.run([sys.executable, "-B", "-c", CHILD.format(repo=str(REPO))],
                   capture_output=True, text=True)
print(r.stdout)
if r.returncode != 0:
    print("STDERR:", r.stderr[-1500:])
