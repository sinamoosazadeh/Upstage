"""Q-027: TrendScale.to_canonical == TREND_SCALE_REQUIRED minus
snapshot_id; state / continuity_break / degraded_reason are NOT in
TREND_SCALE_REQUIRED, so a VALID scale and the same scale flipped to
INVALID/broken/degraded share one snapshot_id."""
import dataclasses
from apex.engines.e09_trend import engine as e9
from apex.engines.e09_trend.engine import TrendEngine

print("TREND_SCALE_REQUIRED:", e9.TREND_SCALE_REQUIRED)
for k in ("state", "continuity_break", "degraded_reason"):
    print("  %s in canonical set: %s" % (k, k in e9.TREND_SCALE_REQUIRED))
    assert k not in e9.TREND_SCALE_REQUIRED

bars = [{"ts": i * 3600_000, "o": 100, "h": 101, "l": 99,
         "c": 100 + 0.1 * i, "v": 1000.0} for i in range(60)]
eng = TrendEngine()
out = eng.process_bar(bars, swings=[{"type": "HH", "price": 1, "idx": 40,
                                     "confirmed_at_idx": 41},
                                    {"type": "HL", "price": 1, "idx": 45,
                                     "confirmed_at_idx": 46}],
                      atr=1.0, tf_seconds=3600)
d = out["scales"]["SHORT"]
obj = e9.TrendScale(**{f.name: d[f.name]
                       for f in dataclasses.fields(e9.TrendScale)})
sid1 = obj.update_snapshot().snapshot_id
obj2 = dataclasses.replace(obj, state="INVALID", continuity_break=True,
                           degraded_reason="ANYTHING_QX")
sid2 = obj2.update_snapshot().snapshot_id
print("VALID   sid:", sid1)
print("INVALID sid:", sid2)
assert sid1 == sid2
print("Q-027 CONFIRMED: lifecycle/degradation fields excluded from the "
      "snapshot identity — indistinguishable snapshots")
