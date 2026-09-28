"""Q-021 (+Q-028 producer half): the native producer upstream_frame calls
E09 run_engine WITHOUT mom_series although the E10 momentum result is
computed earlier in the same function -> the divergence branch is natively
always degraded MOMENTUM_UNAVAILABLE and EV_TRD_003 can never fire."""
import inspect, re
import apex.ops.engine_context as ec
from apex.engines.e09_trend.engine import run_engine

src = inspect.getsource(ec.upstream_frame)
i = src.index("E09.run_engine")
call = src[i - 60:i + 240]
print("producer E09 run_engine call site (raw slice):")
print(call)
j = src.index("trend_context = {")
ctx = src[j:src.index("}", j) + 1]
print("producer E09 compute() context:")
print(ctx)
assert "mom_series" not in call and "mom_series" not in ctx
assert "momentum_result" in src, "E10 momentum IS computed in the same frame"

# replicate the producer-shaped call: no mom_series
bars = []
px = 100.0
for i in range(300):
    px *= 1.001
    bars.append({"ts": i * 3600_000, "o": px / 1.001, "h": px * 1.0005,
                 "l": px / 1.001 * 0.9995, "c": px, "v": 1000.0})
out = run_engine(bars, swings=[{"type": "HH", "price": 1, "idx": 290,
                                "confirmed_at_idx": 291},
                               {"type": "HH", "price": 2, "idx": 295,
                                "confirmed_at_idx": 296}],
                 atr=1.0, tf_seconds=3600)
print("divergence:", out["divergence"])
print("payload degraded=%s reason=%s" % (out["degraded"],
                                         out["degraded_reason"]))
assert out["divergence"]["degraded_reason"] == "MOMENTUM_UNAVAILABLE_DEGRADED_QX"
assert not any(e["code"] == "EV_TRD_003" for e in out["events"])
print("Q-021 CONFIRMED: producer never wires E10 momentum into E09; "
      "divergence natively degraded, EV_TRD_003 unreachable in production")
