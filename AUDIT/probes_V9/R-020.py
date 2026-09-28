"""R-020: quality_score never sees the transition status — a SUSPECTED
(unconfirmed, mid-hysteresis) regime can still be labelled Q5, the highest
statistical grade; no cap ties quality to hysteresis state."""
import inspect
import numpy as np
from apex.engines.e11_regime.engine import (RegimeEngine, get_params,
                                            quality_score)

sig = inspect.signature(quality_score)
print("quality_score signature:", sig)
assert "transition" not in str(sig) and "status" not in str(sig)

HIST = {k: [0.1 + 0.8 * ((i * 37) % 100) / 100.0 for i in range(40)]
        for k in ("trend", "vol", "exp", "liq", "part", "sq")}
W = np.zeros((9, 8)); b = np.zeros(9); b[3] = 50.0    # H ~ 0 < Q5 gate
IC = dict(trendiness_raw=0.1, vol_ratio=0.5, expansion_raw=0.1,
          level_density=0.5, participation_raw=0.4, structure_score=0.5,
          momentum_state_raw="NEUTRAL",
          bias_per_TF={"H4": 0.0, "H1": 0.0, "M15": 0.0}, atr_z=0.0)
eng = RegimeEngine(get_params(), W=W, b=b, history=HIST)
ts = 1_700_000_000_000
for t in range(4):                                    # settle on a state
    out = eng.update({"o": 100, "h": 101, "l": 99, "c": 100, "v": 1000.0,
                      "as_of": ts + t * 3600_000, "ic_inputs": dict(IC)})
    st = out["regime_state"]
    print("bar %d: state=%s transition=%s Q=%s H=%.4f Tur=%.3f" % (
        t, st["state"], st["regime_transition"], st["Q"], st["entropy"],
        st["turbulence"]))
# now flip the raw label (crank trendiness to the top of the history range)
ic2 = dict(IC, trendiness_raw=0.7)          # raw label flips to TREND
out = eng.update({"o": 100, "h": 101, "l": 99, "c": 100, "v": 1000.0,
                  "as_of": ts + 4 * 3600_000, "ic_inputs": ic2})
st = out["regime_state"]
print("flip bar: state=%s state_raw=%s transition=%s Q=%s H=%.4f "
      "Tur=%.3f" % (st["state"], st["state_raw"], st["regime_transition"],
                    st["Q"], st["entropy"], st["turbulence"]))
assert st["regime_transition"] == "SUSPECTED"
assert st["Q"] == "Q5", "SUSPECTED bar graded Q5"
print("R-020 CONFIRMED: SUSPECTED transition carries Q5; hysteresis "
      "uncertainty is invisible to the quality cascade")
