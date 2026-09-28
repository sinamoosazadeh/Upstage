"""Q-023: the §8.3 PIT guard only checks confirmed_at_idx <= current-1;
the swing's own idx is unconstrained upward, so a swing with idx in the
FUTURE (idx > current_idx) but an early confirmed_at_idx passes the guard
and counts in seq_score. The golden fixture only covers the confirmed_at
side (FIX_01)."""
import json
from apex.engines.e09_trend.engine import compute_seq_score

current = 100
window = 60
# future-indexed swing, 'confirmed' long ago (inconsistent input accepted)
phantom = {"type": "HH", "price": 123.0, "idx": 10_000,
           "confirmed_at_idx": 5}
legit = {"type": "LL", "price": 90.0, "idx": 80, "confirmed_at_idx": 81}
score, n = compute_seq_score([legit], window, current)
print("legit only: score=%.3f n=%d" % (score, n))
score2, n2 = compute_seq_score([legit, phantom], window, current)
print("with idx=10000 phantom: score=%.3f n=%d" % (score2, n2))
assert n2 == n + 1 and score2 != score, "future-indexed swing was counted"

# PIT violation on confirmed_at_idx DOES raise (the guard that exists):
try:
    compute_seq_score([{"type": "HH", "price": 1, "idx": 90,
                        "confirmed_at_idx": 100}], window, current)
    print("no raise (unexpected)")
except ValueError as exc:
    print("confirmed_at guard raises:", str(exc)[:70])

fx = json.load(open("tests/fixtures/e09_golden_fixtures.json"))
fix01 = [f for f in fx["fixtures"] if "FIX_01" in str(f.get("id", ""))]
print("FIX_01 fixture present:", bool(fix01),
      "| keys:", sorted(fix01[0].keys()) if fix01 else None)
if fix01:
    print("FIX_01 swings:", json.dumps(fix01[0].get("input", {}).get(
        "swings", fix01[0].get("swings")))[:300])
print("Q-023 CONFIRMED: idx>current accepted whenever confirmed_at_idx "
      "passes; no idx<=current consistency check")
