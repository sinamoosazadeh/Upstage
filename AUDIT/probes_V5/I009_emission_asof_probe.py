"""Re-run exact CP-4/CP-5 emission fixtures and compare persisted event times to AS_OF."""
import datetime as dt
import runpy
from pathlib import Path
from collections import Counter
ROOT = Path(__file__).resolve().parents[2]

def ms(iso):
    return int(dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp() * 1000)
def show(value):
    if value is None: return None
    return dt.datetime.fromtimestamp(ms(value)/1000,dt.timezone.utc).isoformat()
for name in ("cp4", "cp5"):
    ns=runpy.run_path(str(ROOT/"tests"/"integration"/f"test_{name}_engines.py"))
    events=ns[f"Test{name.upper()}EmissionsInsertIntoStore"]()._events()
    cutoff=ms(ns["AS_OF"])
    print(f"{name.upper()} stated AS_OF={ns['AS_OF']} ({cutoff}); event_count={len(events)}")
    print("  counts_by_engine="+repr(dict(sorted(Counter(e.engine_id for e in events).items()))) )
    for engine in sorted({e.engine_id for e in events}):
        rows=[e for e in events if e.engine_id==engine]
        event_ms=[ms(e.event_time) for e in rows]
        availability_ms=[ms(e.availability_time) for e in rows if e.availability_time]
        print(f"  {engine}: event_time_min={show(min(e.event_time for e in rows))}; "
              f"event_time_max={show(max(e.event_time for e in rows))}; "
              f"event_time_after_AS_OF={sum(t>cutoff for t in event_ms)}/{len(rows)}; "
              f"availability_after_AS_OF={sum(t>cutoff for t in availability_ms)}/{len(availability_ms)}")
    print()
