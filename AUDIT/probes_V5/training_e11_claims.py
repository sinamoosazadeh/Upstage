"""Synthetic, real-function probes for selected H-002..H-013 claims.
No real data, classifier artifact, model training campaign, device, or network."""
import json
import tempfile
from pathlib import Path

import numpy as np
from apex.ops import engine_context as ec
from apex.engines.e11_regime import engine as e11
from apex.data_catalog.contracts import MarketObservation
from decimal import Decimal


def artifact():
    fp = {"iterations": 1, "learning_rate": .2, "l2": 0., "class_weights": False}
    W = np.zeros((9, 8)).tolist()
    b = np.zeros(9).tolist()
    window = {"start": "2026-01-01T00:00:00.000Z", "end": "2026-01-02T00:00:00.000Z",
        "timeframes": ["1h"], "symbols": list(ec.CORE10_SYMBOLS),
        "default_timeframes": list(ec.DEFAULT_TRAINING_TIMEFRAMES),
        "default_symbols": list(ec.CORE10_SYMBOLS), "max_bars_per_cell": None}
    body = {"W":W,"b":b,"K":9,"label_delay_candles":48,"seed":5,
        "fit_protocol":fp,"training_window":window,"sample_count":1,
        "training_query_sha256":"a"*64}
    body["artifact_sha256"] = ec.classifier_hash(W,b,5,fp)
    return body


def main():
    out={}
    # H-002: real E11 hysteresis helper: state carried vs newly empty history.
    out["H002_hysteresis"]={
      "persistent":e11.hysteresis_manager(["RANGE"],"CRISIS",3,confirmed_prev="RANGE"),
      "fresh":e11.hysteresis_manager([],"CRISIS",3,confirmed_prev=None)}

    # H-003: same synthetic E11 fixture through training projection vs native inference.
    fixture={x["id"]:x for x in json.load(open("tests/fixtures/e11_golden_fixtures.json"))["fixtures"]}["GF_09_GAP_EDGE"]
    hist=fixture["history"]
    v_train,_=e11.compute_state_vector(fixture["inputs"],hist,fixture["prev_mom"])
    c={"o":100.,"h":101.,"l":99.,"c":100.5,"v":1000.,"ts":1768485600000,"as_of":1768485600000,
       "symbol":"BNBUSDT","timeframe":"1h","ic_inputs":fixture["inputs"],"is_gap":True}
    inf=e11.run_engine([c],W=np.asarray(fixture["W"]),b=np.asarray(fixture["b"]),history=hist,
        Sigma0=np.asarray(fixture["Sigma0"]),prev_mom=fixture["prev_mom"],symbol="BNBUSDT",timeframe="1h")
    out["H003_gap"]={"training_expansion":v_train["expansion"],"training_structure_quality":v_train["structure_quality"],
      "inference_expansion":inf["regime_state"].get("vector",{}).get("expansion"),
      "inference_structure_quality":inf["regime_state"].get("vector",{}).get("structure_quality"),
      "training_rule0":ec.training_rule0(v_train,turbulence=0.),"inference_state":inf["regime_state"].get("state")}

    # H-005: real cache-identity functions do not accept a code/parameter revision.
    obs=MarketObservation("BTCUSDT","1h",*map(Decimal,["100","102","99","101","5"]),None,
      "2026-01-02T00:00:00.000Z",1,"CLOSED",availability_time="2026-01-02T01:00:00.000Z")
    proto_before=ec.training_protocol_hash(("1h",),("BTCUSDT",),None)
    cell_before=ec.cell_input_hash([obs],{},None)
    old=e11.E11_DEFAULTS.get("trend_threshold")
    try:
      e11.E11_DEFAULTS["trend_threshold"]=float(old)+.001
      proto_after=ec.training_protocol_hash(("1h",),("BTCUSDT",),None)
      cell_after=ec.cell_input_hash([obs],{},None)
    finally: e11.E11_DEFAULTS["trend_threshold"]=old
    cache_proto=ec.training_protocol_hash(("1h",),("BTCUSDT",),None)
    cache_payload={"format":ec.E11_TRAIN_CACHE_FORMAT,"cell":"BTCUSDT:1h","training_query_sha256":cache_proto,
      "input_hash":cell_before,"closed_bars":1,"max_bars_per_cell":None,"vector_keys":list(e11.VECTOR_KEYS),
      "samples":[{"as_of":"2026-01-02T00:00:00.000Z","label":"RANGE","vector":[0.0]*8}],
      "excluded":{},"window_start":obs.timestamp,"window_end":obs.timestamp}
    with tempfile.TemporaryDirectory() as td:
      cache_path=Path(td)/"cell.json";ec.write_cell_cache(cache_path,cache_payload)
      cache_hit_after_policy_change=ec.read_cell_cache(cache_path,cell="BTCUSDT:1h",
          protocol_hash=proto_after,input_hash=cell_after) is not None
    out["H005_cache_identity"]={"same_protocol_hash_after_engine_parameter_change":proto_before==proto_after,
      "same_cell_input_hash_after_engine_parameter_change":cell_before==cell_after,
      "same_cache_entry_hits_after_engine_parameter_change":cache_hit_after_policy_change,
      "protocol_hash":proto_before,"cell_hash":cell_before}

    # H-006/H-007: actual validator checks shape/digest but not provenance/query semantics.
    a=artifact(); validated=ec.validate_classifier(a)
    tampered=dict(a); tampered["training_query_sha256"]="f"*64
    tampered["training_window"]={**a["training_window"],"start":"2020-01-01T00:00:00.000Z","end":"2020-01-01T00:00:00.000Z"}
    accepted=ec.validate_classifier(tampered)
    out["H006_H007_validator"]={"valid_baseline":bool(validated),"tampered_query_and_window_accepted":bool(accepted),
      "artifact_hash_unchanged":tampered["artifact_sha256"]==a["artifact_sha256"],
      "label_delay_candles":accepted["label_delay_candles"],"declared_training_end":accepted["training_window"]["end"]}

    # H-011: altered but schema-valid sample is accepted under same correct input hash.
    proto=ec.training_protocol_hash(("1h",),("BTCUSDT",),None)
    payload={"format":ec.E11_TRAIN_CACHE_FORMAT,"cell":"BTCUSDT:1h","training_query_sha256":proto,
      "input_hash":"b"*64,"closed_bars":60,"max_bars_per_cell":None,"vector_keys":list(e11.VECTOR_KEYS),
      "samples":[{"as_of":"2026-01-02T00:00:00.000Z","label":"RANGE","vector":[float(i) for i in range(8)]}],
      "excluded":{},"window_start":"2026-01-01T00:00:00.000Z","window_end":"2026-01-02T00:00:00.000Z"}
    with tempfile.TemporaryDirectory() as td:
      cache=Path(td)/"cell.json";ec.write_cell_cache(cache,payload)
      written=json.loads(cache.read_text())
      written["samples"][0]["label"]="CRISIS" # tamper only derived payload; keep identities fixed
      cache.write_text(json.dumps(written),encoding="utf-8")
      loaded=ec.read_cell_cache(cache,cell="BTCUSDT:1h",protocol_hash=proto,input_hash="b"*64)
    out["H011_cache_tamper"]={"accepted_label":loaded["samples"][0]["label"],"cache_hit":loaded is not None}

    # H-013: actual research function silently falls back when governed loader fails.
    old_get=e11.get_params
    try:
      e11.get_params=lambda *args,**kwargs: (_ for _ in ()).throw(ValueError("synthetic bad config"))
      labels=list(ec.FIT_REQUIRED_CLASSES)
      X=[[float(i==j) for j in range(8)] for i in range(8)]
      study=ec.run_fit_study(X,labels,seed=4,variants=({"variant":"probe","iterations":1,
          "learning_rate":.2,"l2":0.,"class_weights":False,"standardise":False},))
    finally:e11.get_params=old_get
    out["H013_fit_study"]={"theta_H":study["theta_H"],"variant_count":len(study["variants"]),
      "state":"research-only synthetic fit, not a real training artifact"}
    print(json.dumps(out,sort_keys=True,indent=2,default=str))

if __name__=="__main__":main()
