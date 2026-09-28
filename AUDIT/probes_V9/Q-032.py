"""Q-032: the EV_TRD_001 gate uses bos_ok = bool(bos_event): any non-empty
dict — a bearish BOS, a CHoCH, or pure garbage — arms a bullish trend-start
event; direction/kind of the structural confirmation is never inspected."""
from apex.engines.e09_trend.engine import TrendEngine

def run(bos):
    eng = TrendEngine()
    bars = []
    px = 100.0
    for i in range(60):
        px *= 1.01                          # strong up trend
        bars.append({"ts": i * 3600_000, "o": px / 1.01, "h": px * 1.001,
                     "l": px / 1.01 * 0.999, "c": px, "v": 1000.0})
    swings = [{"type": "HH", "price": 100 + i, "idx": 30 + 5 * i,
               "confirmed_at_idx": 31 + 5 * i} for i in range(4)]
    eng.process_bar(bars, swings=swings, atr=1.0, tf_seconds=3600,
                    bos_event=bos)
    return [e for e in eng.events if e["code"] == "EV_TRD_001"]

no_bos = run(None)
down_bos = run({"direction": "DOWN", "kind": "BOS"})
garbage = run({"foo": "bar"})
print("bos=None            -> EV_TRD_001:", no_bos)
print("bos=DOWN (opposite) -> EV_TRD_001:",
      [(e["scale"], e["direction"]) for e in down_bos])
print("bos={'foo':'bar'}   -> EV_TRD_001:",
      [(e["scale"], e["direction"]) for e in garbage])
assert not no_bos and down_bos and garbage
assert all(e["direction"] == 1 for e in down_bos)
print("Q-032 CONFIRMED: opposite-direction/garbage bos_event validates a "
      "bullish trend-start; only truthiness is checked")
