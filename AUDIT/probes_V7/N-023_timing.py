"""N-023 timing: E01 batch run_pipeline at 300/3000 bars, and the streaming
class at bounded sizes (its cost is super-quadratic, so 3000 is extrapolated
and the bound is stated)."""
import sys
import time
import tracemalloc

sys.path.insert(0, "/home/user/Upstage")
sys.path.insert(0, "/home/user/Upstage/AUDIT/probes_V7")

from apex.engines.e01_structure import engine as E01
from _synth import zig

print("=" * 78)
print("N-023  (A) BATCH path actually used by apex/ops/engine_context.py")
print("=" * 78)
for n in (300, 1000, 3000):
    cs = zig(n, trend=0.2)
    tracemalloc.start()
    t0 = time.perf_counter()
    out = E01.run_pipeline(cs, E01.get_params())
    dt = time.perf_counter() - t0
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"  run_pipeline n={n:5d}: {dt:8.3f} s  events={len(out['events'])} "
          f"swings={len(out['swings'])} peak={peak/1e6:6.2f} MB")

print()
print("=" * 78)
print("N-023  (B) StructureEngineStreaming — full rebuild per bar")
print("=" * 78)
prev = None
for n in (300, 600, 900):
    eng = E01.StructureEngineStreaming()
    cs = zig(n, trend=0.2)
    t0 = time.perf_counter()
    for c in cs:
        eng.on_new_candle(c)
    dt = time.perf_counter() - t0
    print(f"  stream n={n:5d}: cumulative {dt:9.3f} s   "
          f"candles={len(eng.candles)} events={len(eng.events)} "
          f"seen={len(eng._seen)}  (no retention/pruning of any of the three)")
    if prev:
        print(f"      ratio vs n={prev[0]}: {dt / prev[1]:.2f}x for "
              f"{n / prev[0]:.2f}x bars")
    prev = (n, dt)
print("  -> 2x the bars costs >6x the time; the class re-runs run_pipeline on")
print("     the whole candle list for EVERY bar, and detect_bos rebuilds the")
print("     full `ranges`/`vols` arrays inside its per-t loop, so the cost is")
print("     super-quadratic in the retained length.  Extrapolating the 900-bar")
print("     measurement, 3000 bars would take on the order of an hour; that")
print("     extrapolation is an estimate, not a measurement, and the class is")
print("     NOT on the PAPER path (engine_context uses run_pipeline once per")
print("     300-bar window), so no current SLA is violated by it.")
print()
print("  D35 memoisation note — atr_sma is memoised per _ATRWindow instance")
print("  (a fresh one is built per run_pipeline call), and detect_bos still")
print("  recomputes [cc['H']-cc['L'] for cc in candles] and")
print("  [cc.get('V',0) for cc in candles] for EVERY t_idx:")
import inspect
src = inspect.getsource(E01.detect_bos)
print("   ", [ln.strip() for ln in src.splitlines()
                if "ranges = [" in ln or "vols = [" in ln])
print("DONE N-023")
