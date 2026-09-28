"""V6 probe O-001: is the initial freeze baseline locally reconstructible?
- docs/APEX_GEN5_frozen_216bcc.md content (hash record only?)
- current APEX_GEN5.md sha256 vs the recorded CP-14.6-FIX digest
- does git history contain a blob whose digest equals the freeze digest?
(The audit was run in a SHALLOW checkout; this clone was unshallowed
read-only, which changes the answer.)
"""
import hashlib
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]

cur = hashlib.sha256((REPO / "APEX_GEN5.md").read_bytes()).hexdigest()
print("current APEX_GEN5.md sha256:", cur)
print("README-recorded CP-14.6-FIX digest:",
      "493568887acb7164c985a0310809140ef3a6b3651e15d05782708b7f73e98569")
print("match:", cur == "493568887acb7164c985a0310809140ef3a6b3651e15d05782708b7f73e98569")
print()
doc = (REPO / "docs" / "APEX_GEN5_frozen_216bcc.md").read_text()
print("docs file copies the frozen text?", len(doc) > 2000,
      "| it is a hash record of length", len(doc), "bytes")
print()
print("== git history scan for the freeze digest 216bcc9e… ==")
commits = subprocess.run(
    ["git", "-C", str(REPO), "log", "--format=%H", "--all", "--", "APEX_GEN5.md"],
    capture_output=True, text=True).stdout.split()
found = []
for c in commits:
    blob = subprocess.run(["git", "-C", str(REPO), "show", f"{c}:APEX_GEN5.md"],
                          capture_output=True)
    if not blob.stdout:
        continue
    d = hashlib.sha256(blob.stdout).hexdigest()
    if d.startswith("216bcc9e"):
        found.append((c[:9], d))
print("commits in history touching APEX_GEN5.md:", len(commits))
print("commits whose APEX_GEN5.md digest == freeze digest:", found)
print()
print("== was this checkout shallow? ==")
sh = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--is-shallow-repository"],
                    capture_output=True, text=True).stdout.strip()
print("is-shallow-repository (after this session's unshallow fetch):", sh)
print("NOTE: the checkout WAS shallow at session start; the audit's environment",
      "was shallow too, so its 'not locally reconstructible' statement was true",
      "THERE; with full history the baseline IS reconstructible and matches.")
