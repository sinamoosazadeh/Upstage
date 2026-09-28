"""M-004 / M-005 / M-006 — exact reproductions."""
import sys; sys.path.insert(0, "/home/user/Upstage")
from apex.pattern import detect as D
def bar(o,h,l,c,v=1000.0): return {"o":o,"h":h,"l":l,"c":c,"v":v}

print("="*78)
print("M-004  neckline = sum(troughs)/2.0  --  it scales with the COUNT, not")
print("       the location, of the troughs between the shoulders")
print("="*78)
sh=[(1,88.0),(5,100.0),(9,88.5)]
bars=[bar(87.0,87.5,86.5,87.0) for _ in range(1)]
bars=[bar(87.0,87.5,86.5,87.0) for _ in range(1)]
bars += [bar(87.0,88.0,86.0,87.5)]           # 1  left shoulder 88
bars += [bar(86.0,86.2,85.0,85.2)]           # 2  trough 85
bars += [bar(86.0,86.2,85.5,85.7)]           # 3
bars += [bar(86.0,86.2,86.0,86.0)]           # 4  trough 86
bars += [bar(87.0,100.0,86.5,99.0)]          # 5  HEAD 100
bars += [bar(87.0,87.2,86.5,87.0)]           # 6  trough 86.5
bars += [bar(87.0,87.4,87.0,87.2)]           # 7  trough 87
bars += [bar(87.0,87.2,86.8,87.0)]           # 8
bars += [bar(87.0,88.5,86.0,88.0)]          # 9  right shoulder 88.5
bars += [bar(88.0,88.0,70.0,71.0)]           # 10 CLOSE 71 -- a real collapse
for label, anchors in (
    ("2 troughs  85 / 86", [(2,85.0),(4,86.0)]),
    ("3 troughs  85 / 86 / 86.5", [(2,85.0),(4,86.0),(6,86.5)]),
    ("4 troughs  85 / 86 / 86.5 / 87", [(2,85.0),(4,86.0),(6,86.5),(7,87.0)]),
):
    h = D._hsh_variant(bars, 2.0, inverse=False, swing_anchor=(sh, anchors))
    n2 = sum(v for _, v in anchors) / 2.0
    if h is None:
        print(f"  {label:32} -> None  neckline would be {n2:.4f}; bar 10 "
              f"closed 71.0 and can never break it")
    else:
        print(f"  {label:32} -> hit index={h.index} neckline="
              f"{h.anchors['neckline']:.4f} strength={h.strength:.4f}")
print()
print("  the same three troughs re-scored by the formula the code uses:")
for lbl, vals in (("2",[85.0,86.0]),("3",[85.0,86.0,86.5]),("4",[85.0,86.0,86.5,87.0])):
    print(f"    {lbl} troughs: sum/2.0 = {sum(vals)/2.0:8.4f}   "
          f"true mean = {sum(vals)/len(vals):8.4f}   "
          f"head 100 minus it = {100-sum(vals)/2.0:8.4f}")
print("  -> with 3 or more inter-shoulder troughs the neckline is ABOVE the")
print("     head, so `closes[j] < neckline` can never be satisfied and the")
print("     detector silently returns None for the rest of the run.  The")
print("     auditor's phrasing ('mean of all troughs') understates it: the")
print("     divisor is a hard-coded 2.0, not len(between).")

print(); print("="*78)
print("M-005  invalidation_level/side contradict the confirming close")
print("="*78)
fb=[bar(100.0,100.5,99.5,100.0) for _ in range(2)]
fb+=[bar(100.0,110.0,99.8,109.5) for _ in range(6)]
fb+=[bar(109.0,110.0,108.5,109.5) for _ in range(6)]
fb+=[bar(111.0,112.0,110.5,111.5)]
h=D.detect_flag(fb, atr=1.0, direction=+1)
c=fb[h.index]["c"]
print(f"  Flag +1: index={h.index} direction={h.direction:+d} "
      f"invalidation={h.invalidation_level}/{h.invalidation_side} "
      f"invalidation_side={h.invalidation_side} confirming close={c}")
print(f"  is_invalidated(hit, hit's OWN confirming close) -> {D.is_invalidated(h, c)}")
print(f"  source of invalidation_level: "
      f"{[ln.strip() for ln in open('/home/user/Upstage/apex/pattern/detect.py').read().splitlines() if 'invalidation_level=' in ln][:3]}")
bb=[bar(100.0,100.5,99.5,100.0) for _ in range(2)]
bb+=[bar(100.0,110.0,99.0,109.0), bar(100.0,112.0,95.0,96.0),
     bar(96.0,113.0,94.0,112.0), bar(100.0,100.0,93.0,94.0)]
hb=D.detect_broadening(bb, atr=2.0)
if hb:
    cbb=bb[hb.index]["c"]
    print(f"  Broadening -1: index={hb.index} direction={hb.direction:+d} "
          f"invalidation={hb.invalidation_level}/{hb.invalidation_side} "
          f"confirming close={cbb} -> is_invalidated={D.is_invalidated(hb, cbb)}")
    print(f"    anchors={hb.anchors}")
    print(f"    bar {hb.index} close {cbb} is {'ABOVE' if cbb>hb.invalidation_level else 'below'}"
          f" {hb.invalidation_level} but a DOWN invalidation is required")
    print(f"    closes after the hit that invalidate: "
          f"{[(i, bb[i]['c']) for i in range(hb.index, len(bb)) if D.is_invalidated(hb, bb[i]['c'])]}")

print(); print("="*78)
print("M-006  the ASC/DESC breakout scan starts at j=1")
print("="*78)
tb=[bar(100.0,101.0,99.0,100.0) for _ in range(20)]
tb[1]=bar(100.0,101.0,99.0,111.5)      # close 111.5 at bar 1, far above
tb[-1]=bar(100.0,101.0,99.0,100.0)
sh_a=[(4,110.0),(8,110.0),(12,110.0),(16,110.0)]
sl_a=[(6,90.0),(10,92.0),(14,94.0),(18,96.0)]
print(f"  swing_anchor highs {sh_a} (all equal 110 -> flat side)")
print(f"  swing_anchor lows  {sl_a} (strictly rising -> ASCENDING)")
print(f"  bar 1 close = {tb[1]['c']}  (already beyond the flat level 110)")
h=D.detect_triangle_ascending(tb, atr=5.0, swing_anchor=(sh_a,sl_a))
print(f"  detect_triangle_ascending -> "
      f"{None if not h else (h.pattern_id, 'index='+str(h.index), 'dir='+str(h.direction), 'boundary='+str(h.anchors['boundary']))}")
if h:
    print(f"  hit.index={h.index} but the pattern's swings live at indices "
          f"{[i for i,_ in sh_a]} / {[i for i,_ in sl_a]}")
    print(f"  -> the reported breakout ({h.index}) PREDATES every swing the")
    print(f"     detector used to define the pattern; the confirming close at")
    print(f"     bar {h.index} is {tb[h.index]['c']}, above every other bar.")
tb2=list(tb)
tb2[1]=bar(100.0,101.0,99.0,100.0)     # remove the early breakout
tb2[19]=bar(100.0,112.0,99.0,111.5)     # real breakout at the end
h2=D.detect_triangle_ascending(tb2, atr=5.0, swing_anchor=(sh_a,sl_a))
print(f"  with the early close removed and a late breakout instead -> "
      f"index={None if not h2 else h2.index}")
hs=[(4,110.0),(8,108.0),(12,106.0)]; ls=[(6,90.0),(10,92.0),(14,94.0)]
h3=D.detect_triangle_symmetrical(tb, atr=5.0, swing_anchor=(hs,ls))
print(f"  SYMMETRICAL uses `for j in range(len(closes)-1, -1, -1)` -> "
      f"index={None if not h3 else h3.index} (scans BACKWARD, newest first)")
print("DONE M-004/M-005/M-006 exact")
