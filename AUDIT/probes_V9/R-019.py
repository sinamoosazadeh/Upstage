"""R-019 (D49-adjacent hysteresis/event semantics): (1) the first candle is
CONFIRMED immediately (no 3-candle hysteresis at cold start); (2)
catalog_events maps regime_transition==CONFIRMED to EV_RGM_003 ('regime
change confirmed') on EVERY stable candle, while the engine journal emits
EV_RGM_003 only on an actual change — compute() publishes the catalog
view, so downstream sees a confirmed regime CHANGE every bar."""
import numpy as np
from apex.engines.e11_regime.engine import (RegimeEngine, get_params,
                                            catalog_events,
                                            hysteresis_manager)

print("hysteresis_manager([], 'TREND') ->",
      hysteresis_manager([], "TREND"))
assert hysteresis_manager([], "TREND") == ("TREND", "CONFIRMED")

HIST = {k: [0.1 + 0.8 * ((i * 37) % 100) / 100.0 for i in range(40)]
        for k in ("trend", "vol", "exp", "liq", "part", "sq")}
W = np.zeros((9, 8)); b = np.zeros(9); b[3] = 50.0
IC = dict(trendiness_raw=0.1, vol_ratio=1.0, expansion_raw=0.1,
          level_density=0.5, participation_raw=0.0, structure_score=0.5,
          momentum_state_raw="NEUTRAL",
          bias_per_TF={"H4": 0.0, "H1": 0.0, "M15": 0.0}, atr_z=0.0)
eng = RegimeEngine(get_params(), W=W, b=b, history=HIST)
for t in range(3):                        # identical stable candles
    out = eng.update({"o": 100, "h": 101, "l": 99, "c": 100, "v": 1000.0,
                      "as_of": 1_700_000_000_000 + t * 3600_000,
                      "ic_inputs": dict(IC)})
    st = out["regime_state"]
    journal = [e["type"] for e in out["events"]]
    catalog = [e["code"] for e in catalog_events(st, eng.p)]
    print("bar %d: state=%s transition=%s | journal=%s | catalog=%s" % (
        t, st["state"], st["regime_transition"], journal, catalog))
    assert st["regime_transition"] == "CONFIRMED"
    assert "EV_RGM_003" not in journal          # no actual change
    assert "EV_RGM_003" in catalog              # yet published as change
print("R-019 CONFIRMED: cold-start CONFIRMED without hysteresis; catalog/"
      "journal EV_RGM_003 semantics diverge — every stable bar publishes "
      "a 'regime change confirmed' evidence")
