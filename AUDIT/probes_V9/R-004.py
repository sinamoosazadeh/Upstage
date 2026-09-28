"""R-004: the duplicate-close_time short-circuit runs BEFORE
_validate_candle, so a CORRECTED candle (same close_time, different OHLCV)
is silently swallowed: the engine returns the stale cached state and never
sees the correction."""
from apex.engines.e10_momentum.engine import (MomentumEngine, get_params,
                                              candle_from_bar)

eng = MomentumEngine(get_params())
px = 100.0
for i in range(60):
    px *= 1.001
    st = eng.update(candle_from_bar(
        {"ts": i * 3600_000, "o": px / 1.001, "h": px * 1.001,
         "l": px / 1.001 * 0.999, "c": px, "v": 1000.0}))
orig_close = eng.candles[-1].close
# corrected candle: same close_time, wildly different close
corrected = candle_from_bar({"ts": 59 * 3600_000, "o": px, "h": px * 2,
                             "l": px * 0.5, "c": px * 1.9, "v": 9999.0})
out = eng.update(corrected)
print("duplicate flag:", out.get("pit", {}).get("duplicate"))
print("engine last close after 'correction': %.4f (corrected close was "
      "%.4f)" % (eng.candles[-1].close, corrected.close))
print("returned mz unchanged:", out["momentum"]["momentum_z"]
      == st["momentum"]["momentum_z"])
assert out["pit"]["duplicate"] is True
assert eng.candles[-1].close == orig_close        # buffer untouched
# even an INVALID duplicate (H<L) is returned as cached state, not Q0:
bad = candle_from_bar({"ts": 59 * 3600_000, "o": px, "h": 1.0,
                       "l": 100.0, "c": px, "v": -1.0})
out2 = eng.update(bad)
print("invalid duplicate returned as:", out2.get("q_tag"),
      "(validation never ran)")
assert "q_tag" in out2 and out2.get("error") is None
print("R-004 CONFIRMED: dedup precedes validation; corrections on the "
      "same close_time are unobservable")
