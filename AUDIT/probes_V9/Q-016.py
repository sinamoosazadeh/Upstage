"""Q-016: transition_matrix (§3.2 Dirichlet transition prior) is exported
but never called by process_bar/run_full/compute or any apex module: phase
probabilities are memoryless softmax scores; with counts=None the matrix
would be the uniform prior 1/9 anyway."""
import subprocess
from apex.engines.e08_wyckoff.engine import transition_matrix

tm = transition_matrix()          # no dataset in repo -> Dirichlet prior
row = tm["ACCUMULATION"]
print("prior row ACCUMULATION:", {k: round(v, 4) for k, v in row.items()})
vals = {round(v, 10) for r in tm.values() for v in r.values()}
print("distinct prior values:", vals)
assert vals == {round(1.0 / 9.0, 10)}

grep = subprocess.run(["grep", "-rn", "transition_matrix", "apex/"],
                      capture_output=True, text=True).stdout.splitlines()
print("apex references:")
for line in grep:
    print("  ", line)
callers = [l for l in grep
           if "def transition_matrix" not in l
           and "__init__.py" not in l
           and '"transition_matrix"' not in l
           and "e11_regime" not in l]  # E11 has its OWN state-dict key of
                                       # the same name; it never calls E08's
print("real callers:", callers)
assert callers == []
print("Q-016 CONFIRMED: transition matrix dead code (uniform 1/9 prior, "
      "never consulted by any runtime path)")
