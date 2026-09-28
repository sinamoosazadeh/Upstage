"""Q-029: PIT/as_of discipline is not enforced at the engine boundary:
E11._resolve_candles applies NO as_of filter to context candles, and
E10.run_engine(as_of_ms=t) computes the state from bars closing AFTER t
and then simply restamps state['as_of'] = t."""
import numpy as np
from apex.engines.e11_regime.engine import E11RegimeEngine, get_params
from apex.engines.e10_momentum.engine import run_engine as e10_run

# ---- E11: candles a year past as_of are consumed silently
HIST = {k: [0.1 + 0.8 * ((i * 37) % 100) / 100.0 for i in range(40)]
        for k in ("trend", "vol", "exp", "liq", "part", "sq")}
W = np.zeros((9, 8)); b = np.zeros(9); b[3] = 50.0
IC = dict(trendiness_raw=0.1, vol_ratio=1.0, expansion_raw=0.1,
          level_density=0.5, participation_raw=0.0, structure_score=0.5,
          momentum_state_raw="NEUTRAL",
          bias_per_TF={"H4": 0.0, "H1": 0.0, "M15": 0.0}, atr_z=0.0)
FUTURE = 1_790_000_000_000                     # ~2026-09-21... far ahead
AS_OF = "2024-01-01T00:00:00Z"                 # query time long before
eng = E11RegimeEngine()
evs = eng.compute("BTCUSDT", "1h", AS_OF, context={
    "candles": [{"o": 100, "h": 101, "l": 99, "c": 100, "v": 1000.0,
                 "as_of": FUTURE, "ic_inputs": dict(IC)}],
    "W": W, "b": b, "history": HIST})
print("E11: query as_of=%s -> %d evidence, event_time=%s" % (
    AS_OF, len(evs), evs[0].event_time if evs else None))
assert evs and evs[0].event_time.startswith("2026")
print("E11 evidence dated ~2.7 years after the query as_of: accepted")

# ---- E10: as_of_ms earlier than every bar; state built from later bars
bars = []
px = 100.0
for i in range(70):
    px *= 1.001
    bars.append({"ts": FUTURE + i * 3600_000, "o": px / 1.001,
                 "h": px * 1.001, "l": px / 1.001 * 0.999, "c": px,
                 "v": 1000.0})
EARLY = 1_704_067_200_000                      # 2024-01-01 in ms
res = e10_run(bars, as_of_ms=EARLY)
st = res["state"]
print("E10: state as_of restamped to %s while pit.last_closed=%s "
      "(future bar)" % (st["as_of"], st["pit"]["last_closed"]))
assert st["as_of"] == EARLY and st["pit"]["last_closed"] > EARLY
print("Q-029 CONFIRMED: engines trust the caller for PIT; as_of is a "
      "label, not a filter (E11 no filter; E10 restamps)")
