"""N-001 / N-002 / N-003 — real apex.engines.e01_structure.engine only.

No re-implementation: every call below is a direct call into the frozen
engine module.  Synthetic candles only (no data/, no device).
"""
import copy
import sys

sys.path.insert(0, "/home/user/Upstage")

sys.path.insert(0, "/home/user/Upstage/AUDIT/probes_V7")
from _synth import zig
from apex.engines.e01_structure import engine as E01

TREND = 0.20   # trend value that makes E01 actually emit BOS/RETEST


def mk(n=140, **kw):
    """Deterministic synthetic OHLCV dicts in the engine's candle shape."""
    kw.setdefault("trend", TREND)
    return zig(n, **kw)


print("=" * 78)
print("N-001  no_future_leak_check() is vacuous + future candle rewrites history")
print("=" * 78)

candles = mk(90)
params = E01.get_params()
LONG = mk(300)   # part (b) needs a long enough series to grow the window

# (a) Show the mutation is sliced away: run the check's two inner pipelines
#     on the identical list, then prove the mutated element is never passed.
t = 61
mutated = [dict(c) for c in candles[:t + 2]]   # exactly the engine's own slice
before_c = [dict(c) for c in candles[:t + 1]]
mutated[t + 1]["H"] = mutated[t + 1]["H"] + 999.0
after_c = mutated[:t + 1]
print(f"  mutated index            : {t + 1}")
print(f"  len(before)              : {len(before_c)}  (last index {len(before_c) - 1})")
print(f"  len(after = mutated[:t+1]): {len(after_c)}  (last index {len(after_c) - 1})")
print(f"  is the mutated element inside `after`? "
      f"{t + 1 in range(len(after_c))}")
print(f"  before == after elementwise? {before_c == after_c}")
print("  -> the +10*ATR mutation of candles[t+1] is DISCARDED by the slice "
      "mutated[:t+1];")
print("     `before` and `after` are the same input, so the equality can "
      "never fail.")
leak = E01.no_future_leak_check(candles, params)
print(f"  E01.no_future_leak_check(candles) -> {leak}")

# (b) The real leak: does appending FUTURE bars change the already-emitted
#     historical output?  (merge_and_prune_swings uses len(candles) for age.)
base = LONG[:70]
out70 = E01.run_pipeline(base, params)
ids70 = {e["snapshot_id"] for e in out70["events"]
         if e.get("snapshot_id") and e.get("candle_index") is not None}
print(f"\n  window len=70 : events={len(out70['events'])} "
      f"active_swings={len(out70['swings'])} pruned={len(out70['pruned'])}")
for extra in (30, 60, 130):
    grown = E01.run_pipeline(LONG[:70 + extra], params)
    ids = {e["snapshot_id"] for e in grown["events"]
           if e.get("snapshot_id") and e.get("candle_index") is not None}
    hist70 = {e["snapshot_id"] for e in grown["events"]
              if e.get("snapshot_id") is not None
              and e.get("candle_index") is not None
              and e["candle_index"] <= 69}
    lost = ids70 - hist70
    bos70 = {e["snapshot_id"] for e in out70["events"]
             if e["event_type"].startswith(("EV_STR_007", "EV_STR_008"))}
    bos_lost = bos70 - {e["snapshot_id"] for e in grown["events"]
                        if e["event_type"].startswith(("EV_STR_007", "EV_STR_008"))
                        and e.get("candle_index") is not None
                        and e["candle_index"] <= 69}
    print(f"  window len={70 + extra:3d}: events={len(grown['events'])} "
          f"active_swings={len(grown['swings'])} "
          f"pruned={len(grown['pruned'])} | "
          f"events with candle_index<=69 that DISAPPEARED: {len(lost)}")
    print(f"     of which HISTORICAL BOS (candle_index<=69) that vanished: "
          f"{len(bos_lost)} / {len(bos70)}")
    if bos_lost:
        gone = sorted({(e['candle_index'], e['price_level'])
                       for e in out70["events"]
                       if e.get("snapshot_id") in bos_lost})[:4]
        print(f"     e.g. vanished (candle_index, price_level): {gone}")
print("  -> theta_maxAge=120 prunes on len(candles); detect_bos filters "
      "fate!=PRUNED;")
print("     therefore HISTORICAL output is a function of the FUTURE window "
      "length.")

print()
print("=" * 78)
print("N-002  detect_bos re-fires the same level on every subsequent close")
print("=" * 78)
# The auditor's scenario: one swing HIGH at 101, three rising closes above it.
sw = [{"type": "HIGH", "price": 101.0, "index": 10, "method": "WILLIAMS",
       "q_tag": "Q2", "snapshot_id": "a" * 64, "fate": "ACTIVE"}]
cs = mk(40)
# force closes above 101 at indices 20/21/22 with ample break magnitude
for i in (20, 21, 22):
    cs[i].update({"O": 101.5, "C": 102.0 + 0.4 * (i - 20), "H": 103.0, "L": 101.2,
                  "V": 500.0})
evs = E01.detect_bos(cs, sw, atr_n=14, break_policy="CLOSE",
                    break_min_mag=0.3, disp_min=1.5, tick=0.01, max_levels=3)
bull = [e for e in evs if e["event_type"] == "EV_STR_007_BOS_BULLISH"
        and e["price_level"] == 101.0]
print(f"  BOS_BULLISH events on price_level=101.0 : {len(bull)}")
for e in bull:
    print(f"    candle_index={e['candle_index']}  break_price={e['break_price']}"
          f"  break_mag={e['break_mag']:.4f}  S={e['strength']['S']:.4f}"
          f"  q={e['q_tag']}")
print(f"  distinct snapshot_ids: {len({e['snapshot_id'] for e in bull})}")
print("  -> no level consumption / re-arm: one break yields N BOS events.")

print()
print("=" * 78)
print("N-003  compute() documents context['htf_swings'] but never passes it")
print("=" * 78)
import inspect

src = inspect.getsource(E01.run_pipeline)
print("  run_pipeline signature :", inspect.signature(E01.run_pipeline))
print("  run_pipeline passes htf_swings to merge_and_prune_swings? ",
      "htf_swings" in src)
src2 = inspect.getsource(E01.merge_and_prune_swings)
print("  merge_and_prune_swings accepts htf_swings? "
      "htf_swings" in inspect.signature(
          E01.merge_and_prune_swings).parameters)
src3 = inspect.getsource(E01.E01StructureEngine.compute)
used = sorted(k for k in ("htf_swings", "window", "provider", "bars", "tick_size",
                          "e01_params", "states_by_tf")
              if ('"%s"' % k) in src3 or ("'%s'" % k) in src3)
print(f"  context keys actually read by E01StructureEngine.compute: {used}")
print(f"  'htf_swings' read by compute? {'htf_swings' in src3}")
print("  run_pipeline() call inside compute:",
      [ln.strip() for ln in src3.splitlines() if "run_pipeline(" in ln])

print()
print("=" * 78)
print("N-004  catalogue event types that run_pipeline never emits")
print("=" * 78)
out = E01.run_pipeline(mk(200), params)
emitted = {e["event_type"] for e in out["events"]}
declared = set(E01.STRUCTURE_EVENT_TYPES)
never = sorted(declared - emitted)
print(f"  declared in STRUCTURE_EVENT_TYPES: {len(declared)}")
print(f"  emitted by run_pipeline(200 bars): {sorted(emitted)}")
print(f"  NEVER emitted: {never}")
# EV_STR_020 is emitted only when context['states_by_tf'] is supplied
print("  EV_STR_020_BIAS_UPDATE only when context['states_by_tf'] set ->",
      "EV_STR_020" in emitted)

print()
print("=" * 78)
print("N-005  availability_time is the candle close_time, not max input time")
print("=" * 78)
ev = dict(out["events"][0])
print("  sample event:", {k: ev.get(k) for k in
                          ("event_type", "candle_index", "timestamp")})
src4 = inspect.getsource(E01.E01StructureEngine._to_evidence)
print("  _to_evidence availability line:",
      [ln.strip() for ln in src4.splitlines() if "availability" in ln][:3])
print("  swings carry 'confirmed_at' but no availability:",
      sorted(out["swings"][0].keys()) if out["swings"] else "no swings")
print("  gap event timestamp field:",
      [ln.strip() for ln in inspect.getsource(E01.detect_gaps).splitlines()
       if '"timestamp"' in ln])

print()
print("=" * 78)
print("N-006  false_break_rate counts a PARTIAL outcome window (n=1)")
print("=" * 78)
cs2 = mk(60)
bos = [{"candle_index": 58, "event_type": "EV_STR_007_BOS_BULLISH",
        "price_level": 100.0, "break_price": 100.0}]
rate, n = E01.false_break_rate(bos, cs2, atr_now=0.5, h=8)
print(f"  BOS at t=58, window=len=60, h=8 -> only 1 of 8 future candles exists")
print(f"  false_break_rate -> p_fail={rate}, n={n}   (docstring: events "
      "without a FULL outcome window are NOT counted)")
rate2, n2 = E01.false_break_rate(bos, cs2[:59], atr_now=0.5, h=8)  # 0 future
print(f"  same BOS with t at the last index (no future bar) -> p={rate2}, n={n2}")

print()
print("=" * 78)
print("N-007  run_pipeline re-numbers candle_index after dropping H<L bars")
print("=" * 78)
cs3 = mk(70)
cs3[30].update({"O": 50.0, "H": 40.0, "L": 45.0, "C": 42.0})   # H < L
o3 = E01.run_pipeline(cs3, params)
ev3 = [e for e in o3["events"] if e.get("candle_index") is not None
       and e["event_type"].startswith(("EV_STR_007", "EV_STR_008",
                                       "EV_STR_009", "EV_STR_010"))]
print(f"  input bars = {len(cs3)} (index 30 is invalid H<L)")
print(f"  invalid-candle events: "
      f"{[e['event_type'] for e in o3['events'] if e['event_type'].startswith('EV_STR_000')]}")
print(f"  event candle_index values are indexes into the FILTERED list: "
      f"min={min((e['candle_index'] for e in ev3), default=None)}")
idxs = sorted({e["candle_index"] for e in ev3})
print(f"  distinct structural candle_index: {idxs[:12]}{' ...' if len(idxs) > 12 else ''}")
# prove: a bar at original index 31 (right after the invalid one) is reported
# at index 30 by comparing timestamps against the filtered list
clean = [c for i, c in enumerate(cs3) if not cs3[i]["H"] < cs3[i]["L"]]
ts_clean = [c["close_time"] for c in clean]
for e in ev3[:6]:
    t2 = e["timestamp"]
    print(f"    event idx={e['candle_index']:3d} ts={t2} -> "
          f"index in filtered list = "
          f"{ts_clean.index(t2) if t2 in ts_clean else 'N/A'}")
print("  -> an index reported as 30 is the bar that was originally at 31.")

print()
print("DONE N-001..N-007")
