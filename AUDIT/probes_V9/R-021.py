"""R-021 (D23): the D23 participation path (direct sigmoid + Q4 cap when
oi_state != AVAILABLE) is keyed on the PRESENCE of the 'oi_state' key in
ic_inputs. The canonical producer always includes it, but the fixture/
direct path (E11 golden fixtures incl. GF_03, any caller omitting the
key) silently falls back to the legacy rolling-sigmoid mapping with NO
D23 cap — Q5 is reachable with OI wholly unaccounted."""
import json
import numpy as np
from apex.engines.e11_regime.engine import (RegimeEngine, get_params,
                                            compute_state_vector)

HIST = {k: [0.1 + 0.8 * ((i * 37) % 100) / 100.0 for i in range(40)]
        for k in ("trend", "vol", "exp", "liq", "part", "sq")}
IC = dict(trendiness_raw=0.1, vol_ratio=0.5, expansion_raw=0.1,
          level_density=0.5, participation_raw=0.4, structure_score=0.5,
          momentum_state_raw="NEUTRAL",
          bias_per_TF={"H4": 0.0, "H1": 0.0, "M15": 0.0}, atr_z=0.0)
# same raw inputs, with and without the oi_state key:
v_no, _ = compute_state_vector(dict(IC), HIST, 0.5)
v_oi, _ = compute_state_vector(dict(IC, oi_state="MISSING"), HIST, 0.5)
print("x_part without oi_state key (legacy rolling norm): %.6f" %
      v_no["participation"])
print("x_part with oi_state=MISSING (D23 sigmoid):          %.6f" %
      v_oi["participation"])
assert v_no["participation"] != v_oi["participation"]

W = np.zeros((9, 8)); b = np.zeros(9); b[3] = 50.0
def run(ic):
    eng = RegimeEngine(get_params(), W=W, b=b,
                       history={k: list(v) for k, v in HIST.items()})
    ts = 1_700_000_000_000
    for t in range(4):                       # settle turbulence below 8
        st = eng.update({"o": 100, "h": 101, "l": 99, "c": 100,
                         "v": 1000.0, "as_of": ts + t * 3600_000,
                         "ic_inputs": dict(ic)})["regime_state"]
    return st
s_no = run(dict(IC))
s_miss = run(dict(IC, oi_state="MISSING"))
print("no key       : Q=%s (no D23 cap applied)" % s_no["Q"])
print("oi_state=MISS: Q=%s (D23 Q4 cap)" % s_miss["Q"])
assert s_no["Q"] == "Q5" and s_miss["Q"] == "Q4"

# fixtures never carry oi_state -> they exercise ONLY the legacy path
doc = json.load(open("tests/fixtures/e11_golden_fixtures.json"))
fx = doc["fixtures"]
gf03 = next(f for f in fx if "GF_03" in str(f.get("id")))
ics = json.dumps(gf03).count("oi_state")
print("GF_03 id=%s | 'oi_state' occurrences in fixture: %d | expected: %s"
      % (gf03["id"], ics, gf03.get("expected")))
alloi = json.dumps(fx).count("oi_state")
print("'oi_state' occurrences across ALL %d E11 fixtures: %d"
      % (len(fx), alloi))
assert alloi == 0
print("R-021 CONFIRMED: D23 branch is key-presence-gated; fixture/direct "
      "callers bypass both the sigmoid mapping and the Q4 cap (train/"
      "serve + test/runtime skew)")
