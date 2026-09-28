"""Q-015: _quality tops out at Q4 (no Q5 branch exists) and even Q4 needs a
brier score that no runtime path ever supplies (process_bar brier defaults
to None; run_full never passes it), so native quality is capped at Q3."""
import re
from apex.engines.e08_wyckoff.engine import WyckoffEngineV4

src = open("apex/engines/e08_wyckoff/engine.py").read()
qsrc = src[src.index("def _quality"):src.index("def _advance")]
print("_quality source labels:", sorted(set(re.findall(r'"Q\d"', qsrc))))
assert '"Q5"' not in qsrc

eng = WyckoffEngineV4()
# best possible inputs WITH brier -> Q4 is the ceiling
q = eng._quality(atr=1.0, structure="BULL", vol_ratio=1.5,
                 entropy_h=0.1, brier=0.01)
print("best case with brier supplied:", q)
assert q == "Q4"

# run_full path: brier is never forwarded
callsite = re.findall(r"self\.process_bar\([^)]*\)", src)
print("run_full call site:", callsite)
assert all("brier" not in c for c in callsite)
bars = [{"ts": i, "o": 100, "h": 100.6, "l": 99.4, "c": 100, "v": 1000}
        for i in range(30)]
recs = eng.run_full(bars, atr_by_idx={i: 1.0 for i in range(30)},
                    vol_ratio_by_idx={i: 1.0 for i in range(30)},
                    evr_by_idx={i: 0.0 for i in range(30)},
                    structure_by_idx={i: "BULL" for i in range(30)})
quals = sorted({r.get("quality") for r in recs})
print("qualities over run (structure+volume supplied):", quals)
assert max(quals) <= "Q3"
print("Q-015 CONFIRMED: Q5 label does not exist in _quality; Q4 gate "
      "requires a brier no runtime caller provides -> native cap Q3")
