"""H-010: use real temp/in-memory store/cache path; stub only the optimizer.
No repository data/, file artifact, live store, or fitted classifier."""
import asyncio, json, tempfile
from pathlib import Path
from decimal import Decimal
import numpy as np
from apex.data_catalog.contracts import MarketObservation, CORE10_SYMBOLS
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.ops import engine_context as ec

async def run():
  with tempfile.TemporaryDirectory(prefix="h010-") as td:
    store=await SQLiteStore(":memory:").open()
    try:
      obs=MarketObservation("BTCUSDT","1h",Decimal("100"),Decimal("102"),Decimal("99"),Decimal("101"),Decimal("10"),None,
        "2026-01-02T00:00:00.000Z",1,"CLOSED",availability_time="2026-01-02T00:00:00.000Z")
      await store.ingest_raw(obs,oi_state="MISSING")
      producer=ec.EngineContextProducer(store)
      window=await producer.window("BTCUSDT","1h","2026-01-03T00:00:00.000Z",1)
      protocol=ec.training_protocol_hash(ec.DEFAULT_TRAINING_TIMEFRAMES,tuple(CORE10_SYMBOLS),None)
      input_hash=ec.cell_input_hash(window,{"4h":[],"15m":[]},None)
      samples=[{"as_of":"2026-01-02T00:00:00.000Z","label":label,"vector":[float(i)/10.0 for i in range(8)]}
               for i,label in enumerate(ec.FIT_REQUIRED_CLASSES)]
      payload={"format":ec.E11_TRAIN_CACHE_FORMAT,"cell":"BTCUSDT:1h","training_query_sha256":protocol,
        "input_hash":input_hash,"closed_bars":1,"max_bars_per_cell":None,"vector_keys":list(ec.E11.VECTOR_KEYS),
        "samples":samples,"excluded":{},"window_start":obs.timestamp,"window_end":obs.timestamp}
      cache=Path(td)/protocol/"BTCUSDT_1h.json";ec.write_cell_cache(cache,payload)
      captured={}
      def no_fit(X,labels,seed,*,protocol):
        captured["labels"]=list(labels)
        return np.zeros((9,8)).tolist(),np.zeros(9).tolist()
      original=ec.fit_multinomial;ec.fit_multinomial=no_fit
      progress=[]
      try:
        artifact,report=await ec.train_classifier(store,timeframes=ec.DEFAULT_TRAINING_TIMEFRAMES,
          symbols=CORE10_SYMBOLS,max_bars_per_cell=None,cache_dir=td,
          now=lambda: 1767398400.0,progress=progress.append)
      finally:ec.fit_multinomial=original
      complete=[x for x in progress if x.get("kind")=="cell"]
      print(json.dumps({"selected_cells":20,"nonempty_market_cells":1,
        "contributing_cache_cells":[x["cell"] for x in complete if x.get("eligible_samples",0)>0],
        "reported_training_symbols":artifact["training_window"]["symbols"],
        "reported_timeframes":artifact["training_window"]["timeframes"],
        "class_counts":report["per_class_counts"],"captured_labels":len(captured["labels"]),
        "optimizer_stubbed":True,"artifact_persisted":False,"cache_root":td},sort_keys=True,indent=2))
    finally:await store.close()
asyncio.run(run())
