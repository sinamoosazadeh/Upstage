"""M-004 addendum: an inflated neckline makes H&S fire with NO breakdown."""
import sys; sys.path.insert(0,"/home/user/Upstage")
from apex.pattern import detect as D
def bar(o,h,l,c,v=1000.0): return {"o":o,"h":h,"l":l,"c":c,"v":v}
# SAME shoulders/head, only the NUMBER of inter-shoulder troughs changes.
# After the right shoulder the market simply CONTINUES (close 89 -> 87), never
# breaking even the true 85.8 mean.
bars=[bar(87.0,87.5,86.5,87.0),
      bar(87.0,88.0,86.0,87.5),    # 1  left shoulder 88.0
      bar(86.0,86.2,85.0,85.2),    # 2  trough
      bar(86.0,86.2,85.5,85.7),    # 3
      bar(86.0,86.2,86.0,86.0),    # 4  trough
      bar(87.0,100.0,86.5,99.0),   # 5  HEAD 100
      bar(87.0,87.2,86.5,87.0),    # 6  trough
      bar(87.0,87.4,87.0,87.2),    # 7  trough
      bar(87.0,87.2,86.8,87.0),    # 8
      bar(87.0,88.5,86.0,88.0),    # 9  right shoulder 88.5
      bar(88.0,88.2,87.0,87.5),    # 10 no breakdown, close 87.5
      bar(87.5,88.0,87.0,87.6),    # 11
      bar(87.6,88.0,87.2,87.8)]    # 12
sh=[(1,88.0),(5,100.0),(9,88.5)]
for lbl,anc in (("2 troughs",[(2,85.0),(4,86.0)]),
                ("3 troughs",[(2,85.0),(4,86.0),(6,86.5)]),
                ("4 troughs",[(2,85.0),(4,86.0),(6,86.5),(7,87.0)])):
    h=D._hsh_variant(bars,2.0,inverse=False,swing_anchor=(sh,anc))
    n = sum(v for _,v in anc)/2.0
    if h is None:
        print(f"  {lbl}: neckline would be {n:8.4f} -> NO hit (correct: nothing")
        print(f"          closed below it; the market only drifted to 87.5)")
    else:
        print(f"  {lbl}: neckline {h.anchors['neckline']:8.4f} -> HIT at bar "
              f"{h.index} with close {bars[h.index]['c']}  (true mean of the")
        print(f"          troughs = {sum(v for _,v in anc)/len(anc):.4f}; the "
              f"close never approached it)")
        print(f"          strength={h.strength:.4f} direction={h.direction:+d} "
              f"invalidation={h.invalidation_level}/{h.invalidation_side}")
print()
print("  with THREE or more inter-shoulder troughs the neckline is pushed")
print("  ABOVE the head, so `closes[j] < neckline` is satisfied by the first")
print("  bar after the right shoulder even when the structure is unbroken.")
