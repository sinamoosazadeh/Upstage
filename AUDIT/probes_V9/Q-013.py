"""Q-013: the §4 idempotency set `_seen` is write-only — process_bar adds
the key but never checks membership, so replaying the identical closed bar
re-runs detection, double-emits events and advances bar_idx."""
import re
from apex.engines.e08_wyckoff.engine import WyckoffEngineV4

src = open("apex/engines/e08_wyckoff/engine.py").read()
uses = re.findall(r"_seen[^\n]*", src)
print("all _seen references:")
for u in uses:
    print("  ", u.strip())
reads = [u for u in uses if ".add(" not in u and "= set()" not in u
         and "self._seen:" in u or " in self._seen" in u]
print("membership checks:", reads)
assert reads == []

eng = WyckoffEngineV4()
bar = {"ts": 100, "o": 100, "h": 100.6, "l": 99.4, "c": 100, "v": 1000}
warm = [{"ts": i, "o": 100, "h": 100.6, "l": 99.4, "c": 100, "v": 1000}
        for i in range(14)]
sc = {"ts": 14, "o": 100.5, "h": 100.6, "l": 96.0, "c": 97.5, "v": 5000}
seq = warm + [sc, sc]                     # identical SC bar replayed
n = len(seq)
eng.run_full(seq, atr_by_idx={i: 1.0 for i in range(n)},
             vol_ratio_by_idx={i: (3.0 if i >= n - 2 else 1.0)
                               for i in range(n)},
             evr_by_idx={i: 0.0 for i in range(n)})
codes = [(e["code"], e["ts"]) for e in eng.events]
print("events after replaying identical bar:", codes)
sc_events = [c for c in codes if c[0] == "EV_WYK_002"]
print("EV_WYK_002 count:", len(sc_events), "| bar_idx:", eng.bar_idx,
      "| _seen size:", len(eng._seen))
assert eng.bar_idx == n - 1        # bar_idx starts at -1: replay advanced the clock
assert len(eng._seen) == n - 1     # duplicate key silently collapsed in the set
assert len(sc_events) == 2         # SC double-emitted
print("Q-013 CONFIRMED: _seen never consulted; duplicate closed bar is "
      "fully reprocessed (no idempotent short-circuit)")
