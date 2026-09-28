"""R-010: the Q4 gate 'every Wilson width < 0.3' is vacuously true when
there are NO conditional rates at all (all() over empty), and
no_future_leak_check only reshuffles the same lists — Q4 ('validated')
is reachable with zero conditional-rate evidence."""
import inspect, random
from apex.engines.e12_temporal.engine import (compute_temporal_profile,
                                              no_future_leak_check)

random.seed(7)
# strong per-bin seasonal separation, >=30 samples per bin
returns_by_tod = {b: [0.001 * (b % 5) + 0.0001 * ((i * 13) % 7)
                      for i in range(35)] for b in range(48)}
groups = [[0.001 + 0.0001 * (i % 5) for i in range(40)],
          [0.010 + 0.0001 * (i % 5) for i in range(40)]]   # Kruskal p ~ 0
stable = [{b: 0.001 * (b % 5) for b in range(48)} for _ in range(3)]

prof = compute_temporal_profile(returns_by_tod, as_of=1_700_000_000_000,
                                cond_events=None,          # NO rates at all
                                window_groups=groups,
                                profiles_history=stable)
print("quality=%s | conditional_rates=%s | kruskal_p=%s | mean_rho=%s" % (
    prof["quality"], prof["conditional_rates"],
    prof["stability"]["kruskal_p"], prof["stability"]["mean_spearman"]))
assert prof["conditional_rates"] == {} and prof["quality"] == "Q4"

# under-sampled rates (ci None) are skipped by the width gate too:
prof2 = compute_temporal_profile(
    returns_by_tod, as_of=1_700_000_000_000,
    cond_events={"bos": ([True] * 5, ["UTC_W1|3|WEEKDAY"] * 5)},  # n=5 < 30
    window_groups=groups, profiles_history=stable)
entry = list(prof2["conditional_rates"].values())[0]
print("n=5 rate entry:", entry, "-> quality:", prof2["quality"])
assert entry["ci"] is None and prof2["quality"] == "Q4"

src = inspect.getsource(no_future_leak_check)
print("no_future_leak_check source:")
print(src)
assert "shuffle" in src or "sample" in src or "sorted" in src
print("R-010 CONFIRMED: Q4 'statistical' badge with zero (or all-refused) "
      "conditional rates; leak check is a permutation self-test")
