"""R-013: two disjoint event surfaces: run_engine journals EV_TMP_001..009
(with EV_TMP_008 stamped as_of=0), but E12TemporalEngine.compute()
publishes ONLY catalog_events(final state) = EV_TMP_001 (+ 003 on
overlap): window-exit/phase-change/day-type/calendar/invalid events never
become EvidenceEvents."""
from apex.engines.e12_temporal.engine import (E12TemporalEngine, run_engine,
                                              catalog_events)

t0 = 1_700_000_000_000                       # 2023-11-14 22:13 UTC
# stretch across several windows to force EV_TMP_001/002/004 transitions
candles = [{"O": 100, "H": 101, "L": 99, "C": 100, "V": 1000.0,
            "ts": t0 + i * 3600_000,
            "availability_time_ms": t0 + (i + 1) * 3600_000}
           for i in range(30)]
res = run_engine(candles)                    # econ_calendar=None
codes = [(e["code"], e["as_of"]) for e in res["events"]]
print("journal codes:", sorted({c for c, _ in codes}))
ev8 = [e for e in res["events"] if e["code"] == "EV_TMP_008"]
print("EV_TMP_008 record:", ev8)
assert ev8 and ev8[0]["as_of"] == 0          # dateless calendar event
assert any(c == "EV_TMP_002" for c, _ in codes)

eng = E12TemporalEngine()
evs = eng.compute("BTCUSDT", "1h", "2023-11-16T00:00:00Z",
                  context={"candles": candles})
pub = sorted({e.condition_state.split("_Window")[0] for e in evs})
print("published evidence condition_states:",
      [e.condition_state for e in evs])
allowed = {"EV_TMP_001", "EV_TMP_003"}
got = {e.condition_state.split("_", 3)[0] + "_" +
       e.condition_state.split("_", 3)[1] + "_" +
       e.condition_state.split("_", 3)[2] for e in evs}
print("published codes:", got)
assert got <= allowed
# catalog_events itself can never yield anything else:
import inspect
src = inspect.getsource(catalog_events)
for dead in ("EV_TMP_002", "EV_TMP_004", "EV_TMP_005", "EV_TMP_008",
             "EV_TMP_009"):
    assert dead not in src
print("R-013 CONFIRMED: journal-only events are unpublishable; calendar "
      "refusal EV_TMP_008 carries as_of=0 (dateless, unjoinable)")
