"""N-008..N-021 — real apex.engines.e02_liquidity.engine only.

Synthetic Candle objects in the engine's own dataclass; no data/, no device.
"""
import sys
import time

sys.path.insert(0, "/home/user/Upstage")
sys.path.insert(0, "/home/user/Upstage/AUDIT/probes_V7")

from _synth import zig
from apex.engines.e02_liquidity import engine as E02
from apex.engines.e02_liquidity.engine import Candle, Level, LiquidityEngineV4

BAR0 = 1704067200          # 2024-01-01T00:00:00Z, fixed epoch (no wall clock)


def candles(n=300, trend=0.0, **kw):
    cs = zig(n, trend=trend, **kw)
    return [Candle(open=c["O"], high=c["H"], low=c["L"], close=c["C"],
                   volume=c["V"], bar_index=i, is_closed=True,
                   t_close=BAR0 + i * 3600) for i, c in enumerate(cs)], cs


def lvl(price, side, **kw):
    d = dict(lid="L", price=price, side=side, ltype="SWING_EXTREME", instances=2,
             first_seen=0, last_touch=0, touch_count=2, salience=0.8,
             fate="ACTIVE", Q="Q2", members=[price, price])
    d.update(kw)
    return Level(**d)


print("=" * 78)
print("N-008  feed_touches accepts a level with instances=1, no swing/UTC proof")
print("=" * 78)
cs, _ = candles(30)
eng = LiquidityEngineV4()
for c in cs:                      # build ATR so touches are not queued
    eng.on_new_closed_candle(c)
print(f"  levels before: {len(eng.levels)}")
eng.feed_touches([{"price": 110.0, "bar_index": 3, "type": "HIGH",
                   "confirmed": True}])          # ONE touch only
lv = next(iter(eng.levels.values()))
print(f"  after ONE feed_touches() call: levels={len(eng.levels)} "
      f"lid={lv.lid} instances={lv.instances} Q={lv.Q} fate={lv.fate} "
      f"ltype={lv.ltype}")
ev = eng.events[-1]
print(f"  emitted event: {ev['event_type']} Q={ev['Q']} payload={ev['payload']}")
print("  -> Q1 level formed from a SINGLE touch; no source-type / confirmed /")
print("     UTC validation of the SwingInput.v1 record is performed.")

print()
print("=" * 78)
print("N-009  on_new_closed_candle never checks Candle.is_closed")
print("=" * 78)
eng2 = LiquidityEngineV4()
base = Candle(open=100, high=101, low=99, close=100.5, volume=1000,
              bar_index=0, is_closed=True, t_close=BAR0)
for i in range(1, 25):
    eng2.on_new_closed_candle(Candle(100, 100.4, 99.6, 100.2, 900, i, True,
                                    BAR0 + i * 3600))
n_before = len(eng2.levels)
n_ev_before = len(eng2.events)
gap_open = Candle(open=112.0, high=120.0, low=80.0, close=118.0, volume=50_000,
                  bar_index=25, is_closed=False,      # <-- explicitly OPEN
                  t_close=BAR0 + 26 * 3600)
atr_before = eng2._atr_wilder14_last()
evs = eng2.on_new_closed_candle(gap_open)
print(f"  Candle(is_closed=False, H=120 L=80 gap) fed to on_new_closed_candle")
print(f"  bar appended to engine.candles? "
      f"{any(x.bar_index == 25 for x in eng2.candles)}")
print(f"  new levels formed: {len(eng2.levels) - n_before}, "
      f"new events: {len(ev2 := eng2.events) - n_ev_before}")
print(f"  ATR recomputed on the OPEN candle: {atr_before:.6f} -> "
      f"{eng2._atr_wilder14_last():.6f}")
print(f"  sweep/touch events on the open bar: "
      f"{[e['event_type'] for e in eng2.events if e['at_bar'] == 25][:6]}")
print("  -> the method's own name and the dedup guard only use bar_index;")
print("     is_closed is stored on the Candle and never read.")

print()
print("=" * 78)
print("N-010  streaming _ingest_touch vs. the §3.3 / §3.5 contract helper")
print("=" * 78)
eng3 = LiquidityEngineV4()
cs3, _ = candles(40, trend=0.2)
for c in cs3:
    eng3.on_new_closed_candle(c)
print(f"  streaming levels: {len(eng3.levels)}  pools: {len(eng3.pools)}")
for lid, l in list(eng3.levels.items())[:8]:
    print(f"    {lid:>22} price={l.price:10.4f} instances={l.instances} "
          f"members={l.members}")
prices = sorted(l.price for l in eng3.levels.values())
if len(prices) >= 2:
    atr = eng3._atr_wilder14_last()
    grp = E02.group_equal_levels_hierarchical(prices, atr, theta_eq=eng3.theta_eq)
    print(f"  contract helper group_equal_levels_hierarchical -> {len(grp)} groups "
          f"(diameter<=2*theta_eq*ATR and every member within theta_eq*ATR of median)")
    for g in grp:
        print(f"    members={len(g['members'])} median={g['median']:.4f} "
              f"diameter={g['diameter']:.6f}")
    eps_pool = 2 * eng3.theta_eq * atr * eng3.kappa
    print(f"  eps_pool used by _update_pools = 2*theta_eq*ATR*kappa = {eps_pool:.6f}"
          f" ; theta_eq*ATR = {eng3.theta_eq * atr:.6f}")
    mem = [l.members for l in eng3.levels.values()]
    widest = max((max(m) - min(m) for m in mem if len(m) > 1), default=0.0)
    print(f"  widest intra-level member spread = {widest:.6f}  "
          f"(contract allows theta_eq*ATR = {eng3.theta_eq * atr:.6f})")
print("  -> _ingest_touch merges on |price - lv.price| <= theta_eq*ATR against the")
print("     RUNNING MEDIAN (lv.price is rewritten each touch); it never re-runs")
print("     the chain-preventing complete-linkage split of §3.3.")

print()
print("=" * 78)
print("N-011  dbscan_1d_optimal expands from NON-core members (border chaining)")
print("=" * 78)
eps, min_pts = 1.0, 3
pts = [100.0, 100.5, 101.0, 1.9, 2.4, 2.9, 3.4, 3.9]
lvls = [lvl(p, "SELL_SIDE", lid=f"L{i}", instances=2) for i, p in enumerate(pts)]
clusters = E02.dbscan_1d_optimal(lvls, eps, min_pts)
print(f"  eps={eps} min_pts={min_pts}  prices={pts}")
for c in clusters:
    print(f"    cluster -> {[round(x.price, 3) for x in c]}")
core = [x for x in clusters if len(x) >= min_pts]
print(f"  true DBSCAN core points (>= {min_pts} neighbours incl. self): "
      f"{[p for p in pts if sum(1 for q in pts if abs(q - p) <= eps) >= min_pts]}")
# single-link chain: each point has >=3 neighbours only in the dense block;
# 3.9 has neighbours 2.9,3.4 => 3 total; chain from 3.4 reaches 2.4
print("  -> queue is seeded with the window of the FIRST core point but the")
print("     inner l2/r2 expansion uses sorted_levels[idx] for EVERY dequeued")
print("     member, so a border point drags in its own neighbours (border")
print("     chaining), which standard DBSCAN forbids.")

print()
print("=" * 78)
print("N-012  dbscan_1d_optimal is NOT O(n log n) — timing on 300 / 3000 levels")
print("=" * 78)
import cProfile
import pstats
import io as _io

for n in (300, 3000, 9000):
    ls = [lvl(100.0 + i * 0.37, "SELL_SIDE", lid=f"L{i}", instances=2)
          for i in range(n)]
    t0 = time.perf_counter()
    cl = E02.dbscan_1d_optimal(ls, eps=0.80, min_pts=3)
    dt = time.perf_counter() - t0
    print(f"  n={n:5d} eps=0.80 min_pts=3 -> {len(cl):4d} clusters  "
          f"{dt*1000:8.2f} ms")
ls = [lvl(100.0 + i * 0.37, "SELL_SIDE", lid=f"L{i}", instances=2)
      for i in range(9000)]
pr = cProfile.Profile()
pr.enable()
E02.dbscan_1d_optimal(ls, eps=0.80, min_pts=3)
pr.disable()
sio = _io.StringIO()
pstats.Stats(pr, stream=sio).sort_stats("tottime").print_stats(6)
print("\n".join(sio.getvalue().splitlines()[4:14]))
print("  per-cluster the seed scan re-walks `left` from 0 and re-derives the")
print("  window; the inner BFS re-derives l2/r2 per member.  Complexity is")
print("  O(n * cluster_reach) in practice, not O(n log n) as the docstring says.")

print()
print("=" * 78)
print("N-013  _update_fates caches the nearest HTF level per SIDE, not per level")
print("=" * 78)
eng4 = LiquidityEngineV4()
eng4.set_htf([{"price": 100.0}, {"price": 130.0}], atr_htf=5.0)
eng4.atr_htf = 5.0
cs4, _ = candles(30)
for c in cs4[:20]:
    eng4.on_new_closed_candle(c)
# force two SELL_SIDE levels at very different prices
eng4.levels.clear()
eng4._ingest_touch(150.0, 18, "SWING_EXTREME")
eng4.levels.clear()
eng4._ingest_touch(102.0, 19, "SWING_EXTREME")
eng4.levels.clear()
import math
for p in (150.0, 102.0, 128.0, 104.0):
    eng4.levels[p] = lvl(p, "SELL_SIDE", lid=f"L{p}", first_seen=0, last_touch=19)
eng4.events.clear()
eng4._update_fates(cs4[20], eng4._atr_wilder14_last())
for p, l in sorted(eng4.levels.items()):
    true_prox = E02.proximity_htf(l.price,
                                  min((abs(l.price - float(h["price"])),
                                       float(h["price"])) for h in eng4.htf_levels)[1],
                                  5.0)
    print(f"    level {p:7.2f}  salience={l.salience:.6f}")
print(f"  proximity_htf(150.0, nearest=130.0) = "
      f"{E02.proximity_htf(150.0, 130.0, 5.0):.6f}")
print(f"  proximity_htf(102.0, nearest=100.0) = "
      f"{E02.proximity_htf(102.0, 100.0, 5.0):.6f}")
print("  -> p_htf_nearest_cache is keyed by lv.side, so the FIRST level of a")
print("     side in dict order fixes the HTF reference price for every other")
print("     level of that side in the same bar.")

print()
print("=" * 78)
print("N-014  a raid keeps re-emitting on later bars with no fresh sweep")
print("=" * 78)
eng5 = LiquidityEngineV4(raid_window=3)
cs5, _ = candles(60, trend=0.2, amp=8.0, leg=5)
all_ev = []
for c in cs5:
    all_ev.extend(eng5.on_new_closed_candle(c))
raids = [e for e in all_ev if e["event_type"] == "EV_LIQ_008"]
sweeps = [e for e in all_ev if e["event_type"] in ("EV_LIQ_005", "EV_LIQ_006")]
print(f"  sweeps={len(sweeps)} bars={[(e['at_bar'], e['level_id']) for e in sweeps][:8]}")
print(f"  EV_LIQ_008 raid events = {len(raids)}")
for r in raids:
    print(f"    raid at_bar={r['at_bar']} side={r['payload']['side']} "
          f"count={r['payload']['count']}")
print("  -> the raid window is `c.bar_index - s['at_bar'] <= raid_window` over")
print("     sweep_log, which never expires, so the same 2 old sweeps re-qualify")
print("     on every bar until a third sweep enters the window.")
