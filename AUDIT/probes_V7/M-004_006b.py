"""M-004 / M-005 / M-006 — targeted fixtures against the real detectors."""
import sys

sys.path.insert(0, "/home/user/Upstage")

from apex.pattern import detect as D


def bar(o, h, l, c, v=1000.0):
    return {"o": o, "h": h, "l": l, "c": c, "v": v}


print("=" * 78)
print("M-004  neckline = SUM(troughs)/len(troughs), not a 2-pivot line")
print("=" * 78)
# Explicit anchors: shoulders at 100 (left, idx 1) / 102 (right, idx 9),
# head 105 (idx 5); THREE troughs 97.0 / 97.5 / 98.0 between the shoulders.
sh_anchor = [(1, 100.0), (5, 105.0), (9, 102.0)]
sl_anchor = [(2, 97.0), (4, 97.5), (6, 98.0)]
bars = [bar(99.0, 99.5, 98.5, 99.0) for _ in range(4)]
bars += [bar(99.0, 100.0, 98.0, 99.5)]        # 4
bars += [bar(100.0, 101.0, 98.4, 100.5)]      # 5
bars += [bar(100.0, 101.0, 98.9, 100.8)]      # 6
bars += [bar(100.0, 101.0, 99.0, 100.6)]      # 7
bars += [bar(100.0, 101.0, 99.0, 100.6)]      # 8
bars += [bar(101.0, 102.0, 99.5, 101.5)]      # 9
bars += [bar(100.0, 100.0, 96.0, 97.0)]       # 10 close 97.0 < 97.5
bars += [bar(97.0, 100.0, 96.0, 100.0)]       # 11
bars += [bar(100.0, 100.0, 96.0, 100.0)]      # 12
hit = D._hsh_variant(bars, 2.0, inverse=False,
                     swing_anchor=(sh_anchor, sl_anchor))
print(f"  anchors: shoulders {sh_anchor}, head 105, troughs "
      f"{[t[1] for t in sl_anchor]}")
print(f"  _hsh_variant -> {hit}")
if hit:
    n = hit.anchors["neckline"]
    print(f"  reported neckline = {n}")
    print(f"  mean of 3 troughs (97+97.5+98)/3 = {(97 + 97.5 + 98) / 3:.6f}")
    print(f"  2-pivot reading (the first and last trough) = "
          f"{(97.0 + 98.0) / 2:.6f}")
    below_rep = [i for i, b in enumerate(bars) if b["c"] < n - 1e-8]
    below_2pv = [i for i, b in enumerate(bars) if b["c"] < 98.0 - 1e-8]
    print(f"  closes below the REPORTED neckline {n:.4f}: {below_rep}")
    print(f"  closes below the 2-pivot neckline 98.0   : {below_2pv}")
    print(f"  -> a real breakdown hidden by the 3-trough mean: "
          f"{sorted(set(below_2pv) - set(below_rep))}")
    print(f"  hit.index={hit.index} direction={hit.direction} "
          f"strength={hit.strength:.4f} (1.0 when |head-neck| >= 3*ATR)")

print()
print("=" * 78)
print("M-005  is_invalidated(hit, hit's OWN confirming close)")
print("=" * 78)
cases = []
# ---- bullish flag: pole up, tight consolidation, continuation up
fb = [bar(100.0, 100.5, 99.5, 100.0) for _ in range(2)]
fb += [bar(100.0, 110.0, 99.8, 109.5) for _ in range(6)]      # pole
fb += [bar(109.0, 110.0, 108.5, 109.5) for _ in range(6)]     # consolidation
fb += [bar(111.0, 112.0, 110.5, 111.5)]                       # break out
h_f = D.detect_flag(fb, atr=1.0, direction=+1)
if h_f:
    cases.append(("Flag +1", h_f, fb))
# ---- bullish rectangle
rb = [bar(100.0, 105.0, 95.0, 100.0) for _ in range(3)]
rb += [bar(100.0, 105.0, 95.0, 100.0) for _ in range(3)]
rb += [bar(100.0, 106.0, 95.0, 105.5)]
h_r = D.detect_rectangle(rb, atr=1.0)
if h_r:
    cases.append(("Rectangle +1", h_r, rb))
for name, h, bs in cases:
    c = bs[h.index]["c"]
    print(f"  {name:14} index={h.index} dir={h.direction:+d} "
          f"invalidation={h.invalidation_level}/{h.invalidation_side} "
          f"confirming close={c}")
    print(f"     is_invalidated(hit, its OWN confirming close) -> "
          f"{D.is_invalidated(h, c)}")
# ---- Quasimodo bearish
qb = [bar(100.0, 100.5, 99.5, 100.0) for _ in range(2)]
qb += [bar(100.0, 110.0, 99.0, 109.0), bar(100.0, 92.0, 91.0, 92.0),
       bar(92.0, 108.0, 91.5, 107.0), bar(100.0, 106.0, 99.0, 100.0),
       bar(100.0, 100.0, 96.0, 96.0)]
h_q = D.detect_quasimodo(qb, atr=2.0)
if h_q:
    c = qb[h_q.index]["c"]
    print(f"  Quasimodo -1   index={h_q.index} dir={h_q.direction:+d} "
          f"invalidation={h_q.invalidation_level}/{h_q.invalidation_side} "
          f"confirming close={c} -> is_invalidated={D.is_invalidated(h_q, c)}")
    cases.append(("Quasimodo -1", h_q, qb))
# ---- Broadening bearish
bb = [bar(100.0, 100.5, 99.5, 100.0) for _ in range(2)]
bb += [bar(100.0, 110.0, 99.0, 109.0), bar(100.0, 112.0, 95.0, 96.0),
       bar(96.0, 113.0, 94.0, 112.0), bar(100.0, 100.0, 93.0, 94.0)]
h_b = D.detect_broadening(bb, atr=2.0)
if h_b:
    c = bb[h_b.index]["c"]
    print(f"  Broadening -1  index={h_b.index} dir={h_b.direction:+d} "
          f"invalidation={h_b.invalidation_level}/{h_b.invalidation_side} "
          f"confirming close={c} -> is_invalidated={D.is_invalidated(h_b, c)}")
    print(f"     anchors={h_b.anchors}  (invalidates UP from the LAST LOW)")
    print(f"     any later close that invalidates: "
          f"{[i for i in range(h_b.index, len(bb)) if D.is_invalidated(h_b, bb[i]['c'])]}")
    cases.append(("Broadening -1", h_b, bb))
print("  -> select_native_pattern() rejects a hit when ANY bar from hit.index")
print("     onward invalidates it, so a self-invalidating hit is unreachable.")

print()
print("=" * 78)
print("M-006  _triangle scans j from 1, so a breakout can predate the pattern")
print("=" * 78)
tb = [bar(100.0, 101.0, 99.0, 100.0)]
tb += [bar(100.0, 110.0, 99.5, 109.0)]        # 1 close 109 already > 110? no
tb += [bar(100.0, 101.0, 99.0, 100.0)]
tb += [bar(100.0, 101.0, 99.0, 100.0)]
tb += [bar(100.0, 110.0, 99.5, 109.0)]        # 4 high 110
tb += [bar(100.0, 101.0, 90.0, 91.0)]         # 5 low 90
tb += [bar(100.0, 101.0, 99.0, 100.0)]
tb += [bar(100.0, 101.0, 99.0, 100.0)]
tb += [bar(100.0, 110.0, 99.5, 109.0)]        # 8 high 110
tb += [bar(100.0, 101.0, 92.0, 93.0)]         # 9 low 92 (rising)
tb += [bar(100.0, 101.0, 99.0, 100.0)]
tb += [bar(100.0, 101.0, 99.0, 100.0)]
tb += [bar(100.0, 110.0, 99.5, 109.0)]        # 12 high 110
tb += [bar(100.0, 101.0, 94.0, 95.0)]         # 13 low 94 (rising)
tb += [bar(100.0, 101.0, 99.0, 100.0)]
tb += [bar(100.0, 101.0, 99.0, 100.0)]
tb += [bar(100.0, 110.0, 99.5, 109.0)]        # 16 high 110
tb += [bar(100.0, 101.0, 96.0, 97.0)]         # 17 low 96 (rising)
sh, sl = D.swings([b["h"] for b in tb], [b["l"] for b in tb], 2)
print(f"  swing highs {sh}")
print(f"  swing lows  {sl}")
tb[-1] = bar(100.0, 112.0, 99.0, 111.5)       # 19 breakout close 111.5 > 110
h = D.detect_triangle_ascending(tb, atr=5.0)
print(f"  detect_triangle_ascending -> {None if not h else (h.pattern_id, 'index=' + str(h.index), h.direction)}")
if h:
    print(f"  hit.index={h.index}  last flat-side swing index="
          f"{max(i for i, _ in sh)}  k=2 -> the pattern is only confirmable at "
          f"bar {max(i for i, _ in sh) + 2}")
    print(f"  close at hit.index = {tb[h.index]['c']} (flat level 110)")
    if h.index < max(i for i, _ in sh) + 2:
        print("  -> the reported hit predates the pattern's own confirmation")
import inspect
src = inspect.getsource(D._triangle)
print("  the loop bound in _triangle:",
      [ln.strip() for ln in src.splitlines() if "for j in range" in ln])
print("  `max(flat_vals and 1, 1)` evaluates to max(1,1)=1 whenever flat_vals")
print("  is a non-empty list, so the scan starts at bar 1, not after formation.")
# prefix determinism: does a LONGER window change the hit index?
tb2 = tb + [bar(111.0, 112.0, 110.0, 111.0) for _ in range(6)]
h2 = D.detect_triangle_ascending(tb2, atr=5.0)
print(f"  19-bar window hit index={None if not h else h.index} | "
      f"25-bar window hit index={None if not h2 else h2.index}")
print("DONE M-004/M-005/M-006")
