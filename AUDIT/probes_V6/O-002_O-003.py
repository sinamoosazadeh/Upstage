"""V6 probes O-002 and O-003: evidence limits — device-only artifacts and the
lock/environment manifest. Read-only checks.
"""
import hashlib
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]

print("== O-002: device-only artifacts ==")
for p in ("data/", "params/e11_classifier_v1.yaml"):
    path = REPO / p
    print("%-32s exists: %s" % (p, path.exists()))
gi = (REPO / ".gitignore").read_text()
print(".gitignore lines mentioning them:",
      [l for l in gi.splitlines() if l in ("data/", "/params/e11_classifier_v1.yaml")])
readme = (REPO / "README.md").read_text()
print("README RUNTIME_ARTIFACTS sentence present:",
      "RUNTIME_ARTIFACTS" in readme and "never committed" in readme)
e11 = (REPO / "params" / "e11_params_v4.yaml").read_text()
print("e11_params_v4.yaml references device-only report:",
      "data/e11_train_report_20260924T181954Z.json" in e11)

print()
print("== O-003: lock completeness ==")
lock = (REPO / "requirements.lock").read_text()
pins = [l for l in lock.splitlines() if "==" in l]
print("direct pins:", len(pins))
for p in pins:
    print("  ", p)
print("any package hashes recorded:", any(
    l.startswith("#") and len(l.split(":")) == 2 and len(l) > 80
    for l in lock.splitlines()))
print("transitive pins (e.g. aiofiles, multidict, pyarrow):",
      [p for p in pins if any(t in p for t in ("multidict", "aiofiles", "idna", "attrs", "pyarrow"))])
pyproject = (REPO / "pyproject.toml").read_text()
build_line = [l for l in pyproject.splitlines() if "requires" in l and "setuptools" in l]
print("pyproject build-system:", build_line)
apex_md = (REPO / "APEX_GEN5.md").read_text()
print("Ch.1 self-declares hashes UNVERIFIED:",
      "hashes UNVERIFIED until first `pip freeze`" in apex_md)
print()
print("== environment actually installed in THIS session (for comparison) ==")
import subprocess
r = subprocess.run(["python3", "-m", "pip", "list", "--format=freeze"],
                   capture_output=True, text=True)
installed = [l for l in r.stdout.splitlines() if any(
    k in l.lower() for k in ("numpy", "pandas", "pydantic", "aiohttp", "aiogram",
                             "aiosqlite", "matplotlib", "dateutil", "pytz", "pytest"))]
for l in sorted(installed):
    print("  ", l)
