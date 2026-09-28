"""Q-026: the §8.2 idempotency cache key is only f"{ts}_{close}" of the
last bar: a second call with DIFFERENT swings/atr/mom/oi_state (or even a
different bar history) silently returns the first cached payload."""
from apex.engines.e09_trend.engine import TrendEngine

bars = [{"ts": i * 3600_000, "o": 100, "h": 101, "l": 99,
         "c": 100 + 0.1 * i, "v": 1000.0} for i in range(60)]
eng = TrendEngine()
out1 = eng.process_bar(bars, swings=[{"type": "HH", "price": 1, "idx": 40,
                                      "confirmed_at_idx": 41}],
                       atr=1.0, tf_seconds=3600, oi_state="MISSING")
# radically different inputs, same (ts, close) of last bar:
bars2 = [dict(b, c=50.0, h=55.0, l=45.0, o=50.0) for b in bars[:-1]]
bars2.append(bars[-1])                     # same last bar
out2 = eng.process_bar(bars2,
                       swings=[{"type": "LL", "price": 9, "idx": 40,
                                "confirmed_at_idx": 41},
                               {"type": "LH", "price": 9, "idx": 45,
                                "confirmed_at_idx": 46}],
                       atr=250.0, tf_seconds=60, oi_state="AVAILABLE")
print("same object returned:", out1 is out2)
print("out2 oi_state:", out2["oi_state"], "(caller passed AVAILABLE)")
print("out2 SHORT seq_score:", out2["scales"]["SHORT"]["seq_score"],
      "(bearish swings ignored)")
assert out1 is out2
assert out2["oi_state"] == "MISSING"
print("Q-026 CONFIRMED: cache key {ts}_{close} ignores every other input; "
      "stale state served for changed swings/atr/oi_state/history")
