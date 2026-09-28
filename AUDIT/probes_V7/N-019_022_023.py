"""N-019 (Gate11 with a correct hash) + N-022 + N-023 timing on 300 / 3000."""
import sys
import time
import tracemalloc

sys.path.insert(0, "/home/user/Upstage")
sys.path.insert(0, "/home/user/Upstage/AUDIT/probes_V7")

from apex.engines.e01_structure import engine as E01
from apex.engines.e02_liquidity import engine as E02
from apex.engines.e02_liquidity.engine import Candle
from apex.setup import gates
from apex.identity.hashes import sha256_hex
from apex.identity.canonical_json import canonical_json
from _synth import zig

BAR0 = 1704067200
TF = 3600


def candles(n=300, trend=0.0, amp=6.0, leg=7):
    x, d, out = 100.0, 1, []
    for i in range(n):
        if i % leg == 0 and i:
            d = -d
        c = x + d * amp / leg + trend
        o = x
        h, l = max(o, c) + amp * 0.12, min(o, c) - amp * 0.12
        out.append(Candle(round(o, 6), round(h, 6), round(l, 6), round(c, 6),
                          round(900.0 * (1.0 + 0.25 * (i % 5)), 4), i, True,
                          BAR0 + i * TF))
        x = c
    return out


print("=" * 78)
print("N-019  Gate 11 lineage check on a CORRECTLY hashed payload")
print("=" * 78)
payload = {"k": 1}
sid = sha256_hex(canonical_json(payload))
for lin in (["candle_19"], ["a" * 64], ["obs-abc"], ["ev_x-1"],
            ["0" * 64]):
    g = gates.gate11_snapshot_lineage(sid, payload, lin)
    print(f"  lineage={lin!r:>18} passed={g.passed} reason={g.reason!r}")
print("  -> E02's own `candle_<bar_index>` tokens do NOT match _ID_TOKEN, so")
print("     a raw engine_event lineage is REJECTED by Gate 11; the PAPER")
print("     producer therefore only passes because plan_bridge derives the")
print("     gate lineage from the FABRIC (raw observation ids), not from the")
print("     engine event's own lineage field.")
from apex.fabric.evidence import EvidenceFabric, FabricEvidenceRef
raw_ids = ["obs-" + "a" * 8, "obs-" + "b" * 8]
ref = FabricEvidenceRef(evidence_id="ev-1", engine_id="E02", symbol="BTCUSDT",
                        timeframe="1h", state="ACTIVE", direction=0,
                        quality=0.9, resolution_class="Q2", age_bars=0.0,
                        as_of=1, snapshot_id="c" * 64,
                        lineage=("candle_19", "obs-" + "a" * 8))
fab = EvidenceFabric.assemble(symbol="BTCUSDT", timeframe="1h", as_of=1,
                              evidence=[ref], data_trust=0.9,
                              raw_observation_ids=raw_ids)
print(f"  fabric admits a member whose own lineage is 'candle_19' as long as")
print(f"  ONE token intersects the raw set: members={len(fab.members)} "
      f"excluded={fab.excluded}")

print()
print("=" * 78)
print("N-022  what the CP-2 E01/E02 tests actually assert")
print("=" * 78)
import subprocess
print(subprocess.run(
    ["grep", "-rn", "no_future_leak_check\|seed", "tests/unit/test_e01_structure.py"],
    capture_output=True, text=True).stdout)
print("---- traceability matrix rows for E01/E02 ----")
out = subprocess.run(["grep", "-nE", r"E01-1[01]|E02-1[01]", "PHASE2_TRACEABILITY_MATRIX.md"],
                     capture_output=True, text=True).stdout
print(out)
print("---- CP-2 status ----")
print(subprocess.run(["grep", "-nE", "CP-2", "PHASE2_CHECKPOINT_STATUS.md"],
                     capture_output=True, text=True).stdout[:900])

print()
print("=" * 78)
print("N-023  StructureEngineStreaming: growth + O(n^2) rebuild; 300 vs 3000")
print("=" * 78)
print("  the streaming class is referenced ONLY by tests:")
print(subprocess.run(["grep", "-rn", "StructureEngineStreaming", "--include=*.py",
                      "apex/", "scripts/", "tests/"],
                     capture_output=True, text=True).stdout)
print("  run_pipeline is re-run on the WHOLE candle list on every bar:")
import inspect
src = inspect.getsource(E01.StructureEngineStreaming.on_new_candle)
print("   ", [ln.strip() for ln in src.splitlines()
                if "run_pipeline" in ln or "self.candles" in ln])
print("  the three growing containers:")
print("   ", [ln.strip() for ln in inspect.getsource(
    E01.StructureEngineStreaming.__init__).splitlines()
    if "self." in ln and "=" in ln])
for n in (300, 600, 1200, 3000):
    eng = E01.StructureEngineStreaming()
    tracemalloc.start()
    t0 = time.perf_counter()
    cs = zig(n, trend=0.2)
    for c in cs:
        eng.on_new_candle(c)
    dt = time.perf_counter() - t0
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"  n={n:5d} bars: {dt:8.3f} s | candles={len(eng.candles)} "
          f"events={len(eng.events)} seen={len(eng._seen)} "
          f"peak={peak/1e6:7.2f} MB")
print("  single full run_pipeline on the same n (the batch path the producer")
print("  actually uses):")
for n in (300, 600, 1200, 3000):
    cs = zig(n, trend=0.2)
    t0 = time.perf_counter()
    E01.run_pipeline(cs, E01.get_params())
    print(f"  n={n:5d} bars: {time.perf_counter() - t0:8.3f} s (ONE call)")
print("DONE N-019,N-022,N-023")
