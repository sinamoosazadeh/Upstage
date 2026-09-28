"""R-011: attach_profile validates ONLY profile['version']=='4.0.0';
snapshot, quality enum, factors, as_of, param_hash are never checked — a
fabricated 'Q4' profile is accepted and its quality is republished on
every subsequent temporal state."""
from apex.engines.e12_temporal.engine import (TemporalWindowEngineStream,
                                              get_params)

p = get_params()
eng = TemporalWindowEngineStream(behavior_window=180, min_samples=30,
                                 params=p, n_bins=48)
bogus = {"version": "4.0.0",              # the only checked key
         "quality": "Q4",                 # unearned statistical badge
         "as_of": 9_999_999_999_999,      # far future — accepted
         "seasonal_factors": None,        # nothing behind the badge
         "conditional_rates": {},
         "snapshot_id": "not-a-real-snapshot"}
eng.attach_profile(bogus)
print("bogus Q4 profile attached without error")
st = eng.on_candle({"O": 100, "H": 101, "L": 99, "C": 100, "V": 1000.0,
                    "ts": 1_700_000_000_000,
                    "availability_time_ms": 1_700_000_003_000})
print("state quality=%s (inherited from the fabricated profile)"
      % st["quality"])
assert st["quality"] == "Q4"
# version is the only gate:
try:
    eng.attach_profile({"version": "3.0.0", "quality": "Q4"})
    print("v3 accepted (unexpected)")
except ValueError as exc:
    print("only version is rejected:", exc)
print("R-011 CONFIRMED: version-string-only validation; forged quality "
      "propagates into every state")
