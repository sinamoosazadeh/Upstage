"""Measure the exact CP-4/CP-5 emission fixtures and insertion prefixes."""
from collections import Counter
from pathlib import Path
import runpy
ROOT=Path(__file__).resolve().parents[2]
for name in ("cp4","cp5"):
    ns=runpy.run_path(str(ROOT/"tests"/"integration"/f"test_{name}_engines.py"))
    cls=ns[f"Test{name.upper()}EmissionsInsertIntoStore"]
    events=cls()._events()
    prefix=events[:40]
    print(f"{name.upper()}: full_events={len(events)} engines={dict(sorted(Counter(e.engine_id for e in events).items()))}")
    print(f"  prefix40={len(prefix)} engines={dict(sorted(Counter(e.engine_id for e in prefix).items()))}")
    print(f"  all_event_ids_validated_by_target={all(e.validate_24_fields() is None for e in events)}")
    print(f"  full_engine_id_set={sorted({e.engine_id for e in events})}")
    print("  target call-path: test helper constructors -> EngineBase.compute/real run_engine -> SQLiteStore.insert_evidence; no run_apex, PaperRuntime or EngineContextProducer call")
