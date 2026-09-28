"""R-012: in run_engine the profile from profile_inputs is built AFTER the
candle loop: every per-candle state (including the returned final
temporal_state) was graded WITHOUT the profile (Q1), while the same
result dict carries the freshly built profile (Q2+) — inconsistent
output; the profile benefits only a NEXT call that passes it back in."""
from apex.engines.e12_temporal.engine import run_engine

t0 = 1_600_000_000_000
candles = [{"O": 100, "H": 101, "L": 99, "C": 100 + 0.1 * (i % 7),
            "V": 1000.0, "ts": t0 + i * 3600_000,
            "availability_time_ms": t0 + (i + 1) * 3600_000}
           for i in range(200)]
returns_by_tod = {b: [0.001 * (b % 5) + 0.0001 * (i % 7)
                      for i in range(35)] for b in range(48)}
res = run_engine(candles,
                 profile_inputs={"returns_by_tod": returns_by_tod})
st, prof = res["temporal_state"], res["temporal_profile"]
print("temporal_state.quality = %s | temporal_profile.quality = %s" % (
    st["quality"], prof["quality"]))
print("EV_TMP_006 (profile attached) journaled at as_of=%s, AFTER the "
      "last state" % [e["as_of"] for e in res["events"]
                      if e["code"] == "EV_TMP_006"])
assert st["quality"] == "Q1" and prof["quality"] in ("Q2", "Q3", "Q4")

# passing the SAME profile up front changes every state's grade:
res2 = run_engine(candles, profile=prof)
print("second pass with profile pre-attached: state quality = %s"
      % res2["temporal_state"]["quality"])
assert res2["temporal_state"]["quality"] == prof["quality"]
print("R-012 CONFIRMED: same-call state/profile quality mismatch; profile "
      "built post-loop never grades the states it shipped with")
