"""V6 probe A-013: .gitignore coverage of custom-named env/secret files.
Uses `git check-ignore` (read-only) — no files are created.
"""
import subprocess
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]

CASES = [
    ".env",                 # the documented default name
    ".env.paper",
    ".env.live",
    ".env.production",
    "config/production.env",
    "secrets/env.txt",
    "params/env.local",
    "prod.env",
    ".envrc",
]

for c in CASES:
    r = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-v", c],
                       capture_output=True, text=True)
    if r.returncode == 0:
        print("%-24s IGNORED   (%s)" % (c, r.stdout.strip().split("\t")[0]))
    else:
        print("%-24s NOT IGNORED  -> could be added to git" % c)

print()
print("== .env-file flag help text (scripts/run_apex.py) ==")
r = subprocess.run(["python3", "-B", str(REPO / "scripts" / "run_apex.py"), "--help"],
                   capture_output=True, text=True, cwd=str(REPO))
for line in (r.stdout + r.stderr).splitlines():
    if "env-file" in line:
        print(line.strip())
