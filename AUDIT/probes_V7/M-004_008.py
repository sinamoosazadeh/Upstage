"""M-004..M-009 — real apex.pattern.detect only."""
import sys

sys.path.insert(0, "/home/user/Upstage")

from apex.pattern import detect as D


def bar(o, h, l, c, v=1000.0):
    return {"o": o, "h": h, "l": l, "c": c, "v": v}


print("=" * 78)
print("M-004  H&S neckline = mean of ALL troughs between the shoulders")
print("=" * 78)
# 3 real troughs 97 / 97.5 / 98 strictly between the shoulders
bars = [
    bar(99.0, 99.4, 97.0, 97.4),    # 0  trough 97.0
    bar(99.0, 100.0, 98.4, 99.6),   # 1  rise
    bar(100.0, 100.2, 97.5, 97.8),  # 2  trough 97.5
    bar(99.0, 101.0, 98.9, 100.6),  # 3  rise
    bar(101.0, 105.0, 100.6, 104.6),  # 4  HEAD
    bar(101.0, 100.8, 97.5, 98.0),  # 5  trough 98.0 -> avg(97,97.5,98)=97.5
    bar(100.0, 101.0, 99.0, 100.4),  # 6  rise
    bar(100.0, 102.5, 99.6, 102.0),  # 7  RIGHT SHOULDER (== 102.0 - head)
    bar(102.0, 102.2, 99.0, 100.0),  # 8
    bar(100.0, 100.0, 97.0, 97.2),  # 9  close 97.2 -> BELOW 97.5? no, 97.2<97.5
    bar(97.0, 100.0, 96.5, 100.0),  # 10
    bar(100.0, 100.0, 96.0, 100.0),  # 11
    bar(100.0, 100.0, 96.0, 100.0),  # 12
    bar(100.0, 100.0, 96.0, 100.0),  # 13
    bar(100.0, 100.0, 96.0, 100.0),  # 14
    bar(100.0, 100.0, 96.0, 100.0),  # 15
]
highs = [b["h"] for b in bars]
lows = [b["l"] for b in bars]
sh, sl = D.swings(highs, lows, 2)
print(f"  swing highs: {sh}")
print(f"  swing lows : {sl}")
hit = D.detect_head_and_shoulders(bars, atr=2.0)
print(f"  detect_head_and_shoulders -> {hit}")
if hit:
    print(f"    neckline={hit.anchors.get('neckline')}  index={hit.index} "
          f"direction={hit.direction} strength={hit.strength}")
    n = hit.anchors.get("neckline")
    if n is not None:
        print(f"    mean of the 3 real troughs 97/97.5/98 = "
              f"{(97 + 97.5 + 98) / 3:.4f}  <-> reported neckline {n}")
        below = [i for i, b in enumerate(bars) if b["c"] < n - 1e-8]
        print(f"    bars closing below the reported neckline: {below}")
        below_true = [i for i, b in enumerate(bars) if b["c"] < 97.5 - 1e-8]
        print(f"    bars closing below the TRUE neckline 97.5  : {below_true}")
        print(f"    -> a real breakdown that the mean-neckline hides: "
              f"{sorted(set(below_true) - set(below))}")
all_hits = D.detect_all(bars, 2.0)["hits"]
print(f"  detect_all -> { {k: (v.name, v.index, v.direction, round(v.strength,3)) for k, v in all_hits.items()} }")

print()
print("=" * 78)
print("M-005  invalidation metadata contradicts the confirming close")
print("=" * 78)
for name, hit2, close in (
        ("Flag UP (consolidation below, continuation up)", None, None),):
    pass
fl = D.detect_flag(bars, 2.0, direction=+1)
print(f"  detect_flag(+1) -> {None if not fl else (fl.pattern_id, fl.name, fl.index, fl.invalidation_level, fl.invalidation_side)}")
if fl:
    for c in (fl.invalidation_level - 0.01, fl.invalidation_level + 0.01):
        print(f"    is_invalidated(close={c:.4f}) -> {D.is_invalidated(fl, c)}  "
              f"(the confirming close was {bars[fl.index]['c']})")
rec = D.detect_rectangle(bars, 2.0)
print(f"  detect_rectangle -> {None if not rec else (rec.pattern_id, rec.index, rec.invalidation_level, rec.invalidation_side)}")
if rec:
    print(f"    confirming close {bars[rec.index]['c']} vs invalidation "
          f"{rec.invalidation_level}/{rec.invalidation_side} -> "
          f"is_invalidated={D.is_invalidated(rec, bars[rec.index]['c'])}")
qd = D.detect_quasimodo(bars, 2.0)
print(f"  detect_quasimodo -> {None if not qd else (qd.pattern_id, qd.index, qd.invalidation_level, qd.invalidation_side, qd.direction)}")
if qd:
    print(f"    confirming close {bars[qd.index]['c']} -> is_invalidated="
          f"{D.is_invalidated(qd, bars[qd.index]['c'])}")
bd = D.detect_broadening(bars, 2.0)
print(f"  detect_broadening -> {None if not bd else (bd.pattern_id, bd.index, bd.direction, bd.invalidation_level, bd.invalidation_side)}")
if bd:
    c = bars[bd.index]["c"]
    print(f"    confirming close {c} -> is_invalidated={D.is_invalidated(bd, c)}")
    print(f"    any bar after index {bd.index} that DOES invalidate: "
          f"{[i for i in range(bd.index, len(bars)) if D.is_invalidated(bd, bars[i]['c'])]}")
print("  select_native_pattern evaluates is_invalidated for every bar from")
print("  hit.index onward, so an immediately-invalidated hit is discarded:")
import inspect
import apex.ops.engine_context as EC
print("   ", [ln.strip() for ln in
            inspect.getsource(EC.select_native_pattern).splitlines()
            if "is_invalidated" in ln])

print()
print("=" * 78)
print("M-006  triangle / double-top confirmations are backdated before the")
print("       pattern exists")
print("=" * 78)
tb = []
for i in range(24):
    if i in (4, 8, 12, 16):
        tb.append(bar(100.0, 110.0, 99.0, 109.0))      # 4 equal swing highs
    elif i in (5, 9, 13, 17):
        tb.append(bar(100.0, 101.0, 90.0, 91.0))       # 4 rising swing lows
    else:
        tb.append(bar(100.0, 101.0, 99.0, 100.0))
sh2, sl2 = D.swings([b["h"] for b in tb], [b["l"] for b in tb], 2)
print(f"  swing highs: {sh2}")
print(f"  swing lows : {sl2}")
ta = D.detect_triangle_ascending(tb, atr=5.0)
print(f"  detect_triangle_ascending(24 bars) -> "
      f"{None if not ta else (ta.pattern_id, 'index=' + str(ta.index), ta.direction)}")
if ta:
    print(f"    bars available: {len(tb)}; the triangle's own swings are at "
          f"indices {[i for i, _ in sh2]}")
    print(f"    hit.index={ta.index} -> a breakout at index {ta.index} is "
          f"reported even though the LAST swing high is at index "
          f"{max(i for i, _ in sh2)} and confirmation needs k=2 closed bars")
    print(f"    close at hit.index = {tb[ta.index]['c']}  "
          f"(flat boundary ~110)")
for n in (18, 20, 22, 24):
    h = D.detect_triangle_ascending(tb[:n], atr=5.0)
    print(f"    prefix of {n:2d} bars -> "
          f"{'hit index=' + str(h.index) if h else 'None'}")
dt = D.detect_double_top(tb, atr=5.0)
print(f"  detect_double_top(24 bars) -> {None if not dt else dt.index}")

print()
print("=" * 78)
print("M-007/M-008  E08 wrappers have no caller; detect_all skips E08 rows;")
print("             detect_flag is shared by PAT-STR-008 and PAT-STR-009")
print("=" * 78)
import subprocess
print(subprocess.run(["grep", "-rn", "from_e08_spring\|from_e08_upthrust",
                      "--include=*.py", "apex/", "scripts/"],
                     capture_output=True, text=True).stdout or "  (no caller in apex/ or scripts/)")
print(subprocess.run(["grep", "-rn", "from_e08_spring\|from_e08_upthrust",
                      "--include=*.py", "tests/"],
                     capture_output=True, text=True).stdout)
print("  detect_all skips rows whose engines != ('E01','E04'):")
print("   ", [ln.strip() for ln in inspect.getsource(D.detect_all).splitlines()
                if "E01" in ln or "E08" in ln])
print("  catalogue rows pointing at detect_flag:")
for r in D.CATALOGUE:
    if r.detector == "detect_flag":
        print(f"    {r.pattern_id} {r.name:10} detector={r.detector} "
              f"lifecycle={r.lifecycle_status}")
fl2 = D.detect_flag(tb, atr=5.0, direction=+1)
print(f"  detect_flag(..., direction=+1) returns pattern_id="
      f"{None if not fl2 else fl2.pattern_id} name={None if not fl2 else fl2.name}")
h2 = D.detect_all(tb, 5.0)["hits"]
print(f"  detect_all keys: {sorted(h2)}")
print(f"  PAT-STR-009 (Pennant) ever produced? {'PAT-STR-009' in h2}")
print(f"  n_admitted_rows={D.detect_all(tb,5.0)['n_admitted_rows']} "
      f"n_run_here={D.detect_all(tb,5.0)['n_run_here']} "
      f"ACTIVE rows with a detector = "
      f"{sum(1 for r in D.CATALOGUE if r.lifecycle_status=='ACTIVE' and r.detector)}")
print("DONE M-004..M-008")
