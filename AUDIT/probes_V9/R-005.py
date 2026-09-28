"""R-005: _validate_candle checks H<L, non-positive open/close, NaN and
interval only: negative volume, +inf prices (isnan(inf)=False), and
C>H / C<L incoherent bars are all accepted into the buffers."""
import math
from apex.engines.e10_momentum.engine import (MomentumEngine, get_params,
                                              candle_from_bar)

eng = MomentumEngine(get_params())
checks = []
# 1) negative volume
c1 = candle_from_bar({"ts": 0, "o": 100, "h": 101, "l": 99, "c": 100,
                      "v": -500.0})
print("negative volume rejected? ->", eng._validate_candle(c1))
checks.append(eng._validate_candle(c1) is None)
# 2) close above high
c2 = candle_from_bar({"ts": 3600_000, "o": 100, "h": 101, "l": 99,
                      "c": 250.0, "v": 100.0})
print("close>high rejected? ->", eng._validate_candle(c2))
checks.append(eng._validate_candle(c2) is None)
# 3) infinite close (isnan(inf) is False)
c3 = candle_from_bar({"ts": 7200_000, "o": 100, "h": math.inf, "l": 99,
                      "c": math.inf, "v": 100.0})
print("inf close rejected? ->", eng._validate_candle(c3))
checks.append(eng._validate_candle(c3) is None)
assert all(checks), "all three invalid candles pass validation"
# and they are really ingested by update():
for c in (c1, c2, c3):
    out = eng.update(c)
    print("update() accepted candle, error =", out.get("error"),
          "| reason =", out.get("reason"))
print("buffer size:", len(eng.candles), "(3 bad candles ingested)")
assert len(eng.candles) == 3
print("R-005 CONFIRMED: no volume>=0, no C within [L,H], no isinf guard; "
      "corrupt bars poison velocity/volume buffers silently")
