"""V6 probe J-013: Ch.13 contains BOTH C=1-U (weighted, D34) and C=1-max(U)
(P/U/C binding). The code computes ONLY the weighted form; the module
docstring claims both laws are computed/reported — check whether a max-form
value is produced anywhere in the builder output.
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.forecast.logistic import build_forecast, ForecastEvent, X_FEATURES

ev = ForecastEvent(target_condition="target", stop_condition="stop",
                    horizon=12, entry_ref="close", symbol="BTCUSDT",
                    timeframe="1h", timestamp=1756684800)
rec = build_forecast(ev, x={k: 0.0 for k in X_FEATURES}, uncertainty={
    "calibration": .5, "data_quality": .5, "disagreement": .2,
    "sampling": .1, "regime_shift": .1, "tail_risk": .1},
    environment="PAPER")
print("u (weighted) =", rec.u)
print("c (1-u)      =", rec.c)
print("1 - max(U)   =", 1.0 - max(.5, .5, .2, .1, .1, .1))
print("max-form anywhere in record?",
      any("max" in str(k).lower() for k in rec.components))
print("components keys:", sorted(rec.components))
print()
print("D34 test expectation (tests/unit/test_forecast_logistic.py): u==0.44, c==0.56")
print("observed:", rec.u, rec.c, "-> matches D34:", abs(rec.u - .44) < 1e-9 and abs(rec.c - .56) < 1e-9)
