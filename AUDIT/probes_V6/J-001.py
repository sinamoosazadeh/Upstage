"""V6 probe J-001: README.md vs the actual CLI command surface; and where a
run procedure DOES exist (handoffs). Read-only checks.
"""
import pathlib
import re
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[2]

readme = (REPO / "README.md").read_text()
cmds = subprocess.run(
    ["python3", "-B", str(REPO / "scripts" / "run_apex.py"), "--help"],
    capture_output=True, text=True, cwd=str(REPO))
help_text = cmds.stdout + cmds.stderr
choices = re.search(r"\{([^}]*)\}", help_text)
cli_commands = sorted(choices.group(1).split(",")) if choices else []
print("CLI commands (argparse choices):", cli_commands)

print()
print("README documents these run_apex commands:")
for c in cli_commands:
    in_readme = ("run_apex.py %s" % c) in readme
    print("  %-24s in README: %s" % (c, in_readme))

print()
print("Where is a serve/bootstrap run procedure documented?")
for f in ("PHASE2_HANDOFF_CP9.md", "PHASE2_HANDOFF_CP14.md"):
    path = REPO / f
    if not path.exists():
        print(f, "MISSING")
        continue
    text = path.read_text()
    hits = []
    for pat in ("run_apex.py serve", "run_apex.py bootstrap", "run_apex.py status",
                "train-e11", "repair-partial", "publish-quality-backfill"):
        if pat in text:
            hits.append(pat)
    print(f, "->", hits)

print()
print("G16 (PHASE2_GLOBAL_DIRECTIVES.md): 'ONE clear run procedure' clause:")
gd = (REPO / "PHASE2_GLOBAL_DIRECTIVES.md").read_text()
for line in gd.splitlines():
    if "ONE clear run procedure" in line:
        print("  ", line.strip()[:160])
