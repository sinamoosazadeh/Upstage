"""V6 probe X-V6-002: tests/unit/test_research_governance.py
TestLiveParamsWriteForbidden::test_frozen_params_files_are_untouched_by_this_suite
runs `git show f14be36:params/<name>` with check=True. In a SHALLOW clone
(the default Arena checkout, and the audit's environment) that object is
absent -> CalledProcessError -> the test FAILS. Demonstrated on a temporary
shallow clone in /tmp; the repository itself is untouched.
"""
import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]

with tempfile.TemporaryDirectory() as td:
    clone = pathlib.Path(td) / "shallow"
    r = subprocess.run(
        ["git", "clone", "--depth", "1",
         "file://" + str(REPO), str(clone)],
        capture_output=True, text=True)
    print("shallow clone (depth=1, the Arena checkout shape) exit:", r.returncode)
    sh = subprocess.run(["git", "-C", str(clone), "rev-parse",
                         "--is-shallow-repository"],
                        capture_output=True, text=True).stdout.strip()
    print("clone is shallow:", sh)
    g = subprocess.run(["git", "-C", str(clone), "show",
                        "f14be36:params/risk_defaults_v1.yaml"],
                       capture_output=True, text=True)
    print("git show f14be36:params/risk_defaults_v1.yaml exit:", g.returncode)
    print("stderr:", g.stderr.strip().splitlines()[-1] if g.stderr.strip() else "")
    # the test's own subprocess call, replicated:
    import subprocess as sp
    try:
        sp.run(["git", "show", "f14be36:params/risk_defaults_v1.yaml"],
               capture_output=True, text=True, check=True, cwd=str(clone))
        print("replicated test subprocess: OK")
    except sp.CalledProcessError as e:
        print("replicated test subprocess: CalledProcessError (returncode",
              e.returncode, ") -> pytest test FAILS in a shallow clone")

# and in the full (unshallowed) session checkout it passes:
g2 = subprocess.run(["git", "-C", str(REPO), "show",
                     "f14be36:params/risk_defaults_v1.yaml"],
                    capture_output=True, text=True)
print()
print("full session checkout: git show f14be36 exit:", g2.returncode,
      "| first line:", g2.stdout.splitlines()[0] if g2.stdout else "")
print()
print("session observation (before unshallow): 1 failed / 95 passed;")
print("after unshallow: 96 passed. The failing test was exactly")
print("TestLiveParamsWriteForbidden::test_frozen_params_files_are_untouched_by_this_suite.")
