"""R-007: when a classifier artifact is supplied, snapshot param_hash is
ONLY the artifact sha256 (`self._phash = classifier_artifact_sha256 or
param_hash(p)`): two engines with DIFFERENT governed EngineParams but the
same artifact produce identical snapshot_ids when the numeric outputs
coincide — the parameter set is outside the snapshot identity."""
import numpy as np
from apex.engines.e11_regime.engine import (RegimeEngine, get_params,
                                            param_hash)

HIST = {k: [0.1 + 0.8 * ((i * 37) % 100) / 100.0 for i in range(40)]
        for k in ("trend", "vol", "exp", "liq", "part", "sq")}
W = np.zeros((9, 8))
b = np.zeros(9); b[3] = 50.0                     # near-one-hot -> tiny H
IC = dict(trendiness_raw=0.1, vol_ratio=1.0, expansion_raw=0.1,
          level_density=0.5, participation_raw=0.0, structure_score=0.5,
          momentum_state_raw="NEUTRAL",
          bias_per_TF={"H4": 0.0, "H1": 0.0, "M15": 0.0}, atr_z=0.0)
CANDLE = {"o": 100, "h": 101, "l": 99, "c": 100, "v": 1000.0,
          "as_of": 1_700_000_000_000, "ic_inputs": IC}
ART = "ab" * 32

pA = get_params({"quality_Tur_Q3": 15.5})          # default
pB = get_params({"quality_Tur_Q3": 15.0})          # governed change
print("param_hash(A)=%s param_hash(B)=%s (differ: %s)" % (
    param_hash(pA), param_hash(pB), param_hash(pA) != param_hash(pB)))
outs = []
for p in (pA, pB):
    eng = RegimeEngine(p, W=W, b=b, history={k: list(v)
                                             for k, v in HIST.items()},
                       classifier_artifact_sha256=ART)
    outs.append(eng.update(dict(CANDLE)))
sA = outs[0]["regime_state"]; sB = outs[1]["regime_state"]
print("A: state=%s Q=%s turb=%.3f sid=%s" % (sA["state"], sA["Q"],
                                             sA["turbulence"],
                                             sA["snapshot_id"][:16]))
print("B: state=%s Q=%s turb=%.3f sid=%s" % (sB["state"], sB["Q"],
                                             sB["turbulence"],
                                             sB["snapshot_id"][:16]))
assert param_hash(pA) != param_hash(pB)
assert sA["snapshot_id"] == sB["snapshot_id"], "identical sid across params"
print("R-007 CONFIRMED: artifact sha replaces (not augments) the param "
      "digest; different governed params -> same snapshot identity")
