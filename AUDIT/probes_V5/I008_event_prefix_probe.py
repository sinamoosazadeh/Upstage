from __future__ import annotations

import asyncio
import runpy
from collections import Counter

from apex.data_catalog.store.sqlite_store import SQLiteStore

# Reuse the exact CP-3 fixture and event construction from the target test.
ns = runpy.run_path("tests/integration/test_cp3_engines.py")
lcg_window = ns["lcg_window"]
obs_window = ns["obs_window"]
e04_atr_series = ns["e04_atr_series"]
E04 = ns["E04VolatilityEngine"]
E05 = ns["E05FVGEngine"]
E06 = ns["E06OrderBlockEngine"]

bars = lcg_window(120)
window = obs_window(bars)
_, atr_series = e04_atr_series(bars)
vol = [{"snapshot_id": f"v{i}", "as_of_ts": bars[i]["ts"],
        "availability_time_ms": bars[i]["ts"], "volume_sma": 1000.0,
        "volume_ratio": 2.0 if i == 6 else 1.0} for i in range(len(bars))]
vola = [{"snapshot_id": f"a{i}", "as_of": bars[i]["ts"],
         "atr_n": atr_series[i], "tr_method": "E04"} for i in range(len(bars))]
evs = []
evs += E04().compute("BTCUSDT", "1h", "2026-01-06T00:00:00Z", {"window": window})
evs += E05().compute("BTCUSDT", "1h", "2026-01-06T00:00:00Z",
                     {"window": window, "tick_size": 0.01,
                      "atr_series": atr_series})
evs += E06().compute("BTCUSDT", "1h", "2026-01-06T00:00:00Z",
                     {"window": window, "volume_evidence": vol,
                      "volatility_evidence": vola,
                      "struct_events_by_idx": {5: [{"kind": "BOS",
                          "direction": "UP", "valid_at_idx": 6}]}})

all_counts = Counter(ev.engine_id for ev in evs)
prefix_counts = Counter(ev.engine_id for ev in evs[:30])
first_non_e04 = next((i for i, ev in enumerate(evs) if ev.engine_id != "E04"), None)
print("exact fixture event counts:", dict(sorted(all_counts.items())))
print("exact first-30 counts:", dict(sorted(prefix_counts.items())))
print("first non-E04 event index:", first_non_e04)
print("full event IDs:", sorted({ev.engine_id for ev in evs}))
assert {"E04", "E05", "E06"} <= set(all_counts)
assert prefix_counts == {"E04": 30}
assert first_non_e04 is not None and first_non_e04 >= 30

async def persist(events, label):
    store = SQLiteStore(path=":memory:")
    await store.open()
    try:
        for ev in events:
            await store.insert_evidence(ev)
        counts = await (await store.db.execute(
            "SELECT engine_id,COUNT(*) FROM evidence_event GROUP BY engine_id "
            "ORDER BY engine_id")).fetchall()
        print(f"{label} inserted rows by engine:", [tuple(row) for row in counts])
    finally:
        await store.close()

asyncio.run(persist(evs[:30], "test's first 30"))
asyncio.run(persist(evs, "all concatenated events"))
print("probe=PASS; exact test composition; SQLite :memory: only; no data/ or network")
