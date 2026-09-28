"""Q-022: atr defaults to 0.0 and pos = (C - SMA)/max(ATR, EPS) has no
positive-ATR guard or magnitude bound: with the default the pos term
explodes to ~1e12 and single-handedly saturates direction/strength."""
from apex.engines.e09_trend.engine import (TrendEngine, compute_pos_scale,
                                           trend_direction_and_strength)

bars = [{"ts": i * 3600_000, "o": 100, "h": 100.7, "l": 99.3,
         "c": 100 + 0.01 * i, "v": 1000.0} for i in range(60)]
pos = compute_pos_scale(bars, 20, 0.0)
print("pos with atr=0.0: %.6g" % pos)
assert abs(pos) > 1e6

d, s, z = trend_direction_and_strength(0.0, 0.0, pos)
print("direction=%d strength=%.3f z=%.6g (seq=0, slope_z=0!)" % (d, s, z))
assert d != 0 and s == 1.0

# whole-engine effect via default-atr call (context without 'atr')
eng = TrendEngine()
out = eng.process_bar(bars, swings=[{"type": "HH", "price": 1, "idx": 40,
                                     "confirmed_at_idx": 41},
                                    {"type": "HL", "price": 1, "idx": 50,
                                     "confirmed_at_idx": 51}],
                      tf_seconds=3600)   # atr omitted -> 0.0
for sc in ("MICRO", "SHORT"):
    data = out["scales"][sc]
    print("%s pos=%.4g direction=%d strength=%.3f" % (
        sc, data["pos"], data["direction"], data["strength"]))
assert abs(out["scales"]["SHORT"]["pos"]) > 1e6
print("Q-022 CONFIRMED: no ATR floor/guard; default atr=0.0 turns pos into "
      "a ~1e12 dominating term")
