"""H-004 synthetic E11 optional-input/quality-cap probe; no external data."""
import json
from pathlib import Path
import numpy as np
from apex.engines.e11_regime.engine import run_engine

fixture = {x["id"]: x for x in json.loads(Path("tests/fixtures/e11_golden_fixtures.json").read_text())["fixtures"]}["GF_09_GAP_EDGE"]
candle = {"o":100.0,"h":101.0,"l":99.0,"c":100.5,"v":1000.0,
          "ts":1768485600000,"as_of":1768485600000,"symbol":"BNBUSDT",
          "timeframe":"1h","ic_inputs":fixture["inputs"],"is_gap":True}
common = dict(candles=[candle], W=np.asarray(fixture["W"]), b=np.asarray(fixture["b"]),
              history=fixture["history"], Sigma0=np.asarray(fixture["Sigma0"]),
              prev_mom=fixture["prev_mom"], symbol="BNBUSDT", timeframe="1h")
absent = run_engine(**common)
explicit_no_counts = run_engine(**common, base_rates={"EXPANSION":{"n":0,"k":0,"p":None,"wilson_ci":None}})
print(json.dumps({
  "producer_context_keys_from_source": ["candles","W","b","classifier_artifact_sha256","history","mu0","Sigma0","prev_mom"],
  "absent": {"state":absent["regime_state"]["state"],"Q":absent["regime_state"]["Q"],
             "T":absent["regime_state"]["transition_matrix"],"base_rates":absent["regime_state"]["base_rates"],
             "xi":absent["xi_filtered"]},
  "explicit_n0": {"state":explicit_no_counts["regime_state"]["state"],"Q":explicit_no_counts["regime_state"]["Q"],
                   "T":explicit_no_counts["regime_state"]["transition_matrix"],
                   "base_rates":explicit_no_counts["regime_state"]["base_rates"]}
}, sort_keys=True, indent=2))
