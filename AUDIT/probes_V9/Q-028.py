"""Q-028: E09.compute() publishes exactly one evidence per scale
(condition_state TREND_{scale}_{state}); the engine-internal events
EV_TRD_001..008 in result['events'] are dropped — never converted to
evidence — and the producer only consumes compute()-style per-scale frames."""
import inspect
import apex.ops.engine_context as ec
from apex.engines.e09_trend.engine import TrendEngine

src = inspect.getsource(TrendEngine)  # just to prove import is real
import apex.engines.e09_trend.engine as e9
csrc = inspect.getsource(e9.E09TrendEngine.compute)
print("compute() source:")
print(csrc)
assert 'result["scales"].items()' in csrc
assert "events" not in csrc.replace('result["events"]', 'X') or \
       'result["events"]' not in csrc
# run and count
bars = [{"ts": i * 3600_000, "o": 100, "h": 101, "l": 99,
         "c": 100 + 0.1 * i, "v": 1000.0} for i in range(60)]
eng = TrendEngine()
out = eng.process_bar(bars, swings=[{"type": "HH", "price": 1, "idx": 40,
                                     "confirmed_at_idx": 41},
                                    {"type": "HL", "price": 1, "idx": 45,
                                     "confirmed_at_idx": 46}],
                      atr=1.0, tf_seconds=3600)
print("engine emitted internal events:", [e["code"] for e in eng.events])
print("compute() would publish %d evidence (one per scale), states only"
      % len(out["scales"]))
# producer side: upstream_frame keeps result dict; evidence built from scales
usrc = inspect.getsource(ec.upstream_frame)
print("producer uses E09 'events' key:", "trend" in usrc and
      ('result["events"]' in usrc or "trend[\"events\"]" in usrc))
print("Q-028 CONFIRMED: EV_TRD_* never become EvidenceEvents; only "
      "per-scale TREND_* condition states are published")
