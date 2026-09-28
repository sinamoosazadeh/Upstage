"""R-009: the §6 behavior_window is defined in DAYS (180, range 30-365)
but the stream buffer cap is behavior_window * n_bins RECORDS
(180*48 = 8640) with no time cutoff: on 1h candles that is 360 days
(2x the mandate), on 4h candles ~4 years, on 1m candles only 6 days —
and _vol_ratio_for/_historical_behavior average over whatever is there."""
from apex.engines.e12_temporal.engine import (TemporalWindowEngineStream,
                                              get_params)

p = get_params()
eng = TemporalWindowEngineStream(behavior_window=int(p.behavior_window),
                                 min_samples=30, params=p,
                                 n_bins=int(p.fff_bins))
cap = eng.behavior_window * eng.n_bins
print("behavior_window=%d days | n_bins=%d | buffer cap=%d RECORDS" % (
    eng.behavior_window, eng.n_bins, cap))
assert cap == 8640

# feed 9000 hourly candles (375 days) — buffer keeps 8640 = 360 days
t0 = 1_600_000_000_000
for i in range(9000):
    eng.on_candle({"O": 100, "H": 101, "L": 99, "C": 100, "V": 1000.0,
                   "ts": t0 + i * 3600_000,
                   "availability_time_ms": t0 + (i + 1) * 3600_000})
span_ms = eng.buffer[-1]["ts_ms"] - eng.buffer[0]["ts_ms"]
print("1h feed: buffer=%d records spanning %.1f days (mandate: 180)" % (
    len(eng.buffer), span_ms / 86_400_000))
assert len(eng.buffer) == 8640
assert span_ms / 86_400_000 > 300               # far beyond 180 days

# 4h candles: the same cap covers ~4 years of history
eng4 = TemporalWindowEngineStream(behavior_window=180, min_samples=30,
                                  params=p, n_bins=48)
for i in range(9000):
    eng4.on_candle({"O": 100, "H": 101, "L": 99, "C": 100, "V": 1000.0,
                    "ts": t0 + i * 4 * 3600_000,
                    "availability_time_ms": t0 + (i + 1) * 4 * 3600_000})
span4 = (eng4.buffer[-1]["ts_ms"] - eng4.buffer[0]["ts_ms"]) / 86_400_000
print("4h feed: buffer=%d records spanning %.1f days" % (
    len(eng4.buffer), span4))
assert span4 > 1000
# no timestamp-based eviction exists anywhere in the stream class:
src = open("apex/engines/e12_temporal/engine.py").read()
seg = src[src.index("class TemporalWindowEngineStream"):
          src.index("TemporalContextEngine =")]
print("time-based eviction in stream class ('86400' or 'days' cutoff):",
      "86400" in seg)
assert "86400" not in seg
print("R-009 CONFIRMED: record-count cap masquerades as a day window; "
      "retention is timeframe-dependent (360d@1h, ~4y@4h, 6d@1m)")
