"""V6 probe B-001: packaging completeness.
Builds the wheel from pyproject.toml into a TEMP directory (never dist/ in the
repo), lists its contents, and checks whether subpackages and params/ are
delivered. Sandbox setuptools is 66.1.1 (< the declared >=68 backend).
"""
import glob
import os
import pathlib
import subprocess
import sys
import tempfile
import zipfile

REPO = pathlib.Path(__file__).resolve().parents[2]

print("== build environment ==")
import setuptools
print("setuptools", setuptools.__version__, "(pyproject requires >=68)")

with tempfile.TemporaryDirectory() as td:
    outdir = os.path.join(td, "wheels")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
         "-w", outdir, str(REPO)],
        capture_output=True, text=True, cwd=td)
    print("pip wheel exit:", r.returncode)
    if r.returncode != 0:
        print(r.stdout[-2000:])
        print(r.stderr[-2000:])
    wheels = glob.glob(os.path.join(outdir, "*.whl"))
    print("wheels:", [os.path.basename(w) for w in wheels])
    if wheels:
        names = zipfile.ZipFile(wheels[0]).namelist()
        py = [n for n in names if n.endswith(".py")]
        print("total files in wheel:", len(names), "| .py files:", len(py))
        print("--- all .py files in the wheel ---")
        for n in sorted(py):
            print("  ", n)
        print("--- non-py files ---")
        for n in sorted(n for n in names if not n.endswith(".py")):
            print("  ", n)
        # repository reference counts
        repo_py = [p for p in (REPO / "apex").rglob("*.py")]
        print()
        print("repo apex/**/_modules_: python files =", len(repo_py),
              "| distinct python dirs =", len({str(p.parent) for p in repo_py}))
        print("subpackages delivered:",
              len({n.rsplit("/", 1)[0] for n in py if "/" in n}) )
        print("params/ in wheel:", any(n.startswith("params") for n in names))
        print("requirements/lock in wheel:", any("requirements" in n for n in names))
