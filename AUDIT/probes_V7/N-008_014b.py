"""N-008..N-014 (corrected constructions) + N-015..N-021 + timing.

Real apex.engines.e02_liquidity.engine only; synthetic Candle objects.
"""
import math
import sys
import time

sys.path.insert(0, "/home/user/Upstage")
sys.path.insert(0, "/home/user/Upstage/AUDIT/probes_V7")

from apex.engines.e02_liquidity import engine as E02
from apex.engines.e02_liquidity.engine import Candle, Level, LiquidityEngineV4

BAR0 = 1704067200
TF = 3600


def candles(n=300, trend=0.0, amp=6.0, leg=7, jitter=0.0):
    """Deterministic candles straight from the E02 Candle dataclass."""
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


def lvl(price, side="SELL_SIDE", **kw):
    d = dict(lid=f"L{price}", price=price, side=side, ltype="SWING_EXTREME",
             instances=2, first_seen=0, last_touch=0, touch_count=2,
             salience=0.8, fate="ACTIVE", Q="Q2", members=[price, price])
    d.update(kw)
    return Level(**d)


print("=" * 78)
print("N-008  ONE feed_touches() record is enough to form (and promote) a level")
print("=" * 78)
eng = LiquidityEngineV4()
for c in candles(30):
    eng.on_new_closed_candle(c)
before = len(eng.events)
eng.feed_touches([{"price": 250.0, "bar_index": 3, "type": "HIGH",
                   "confirmed": True}])
new = eng.events[before:]
print(f"  new events: {[(e['event_type'], e['level_id'], e['Q']) for e in new]}")
lv = eng.levels.get(new[0]["level_id"]) if new else None
if lv is not None:
    print(f"  level: instances={lv.instances} Q={lv.Q} fate={lv.fate} "
          f"ltype={lv.ltype} first_seen={lv.first_seen} members={lv.members}")
print("  record carried NO source proof (no E01 swing id, no UTC window, no")
print("  bar-index validation). Contract Q1 wants >= 2 instances from a")
print("  confirmed swing / UTC source; a single dict yields instances=1.")

# and the closed/open flag of a fed touch is not consulted
eng2 = LiquidityEngineV4()
for c in candles(30):
    eng2.on_new_closed_candle(c)
b2 = len(eng2.events)
eng2.feed_touches([{"price": 250.0, "bar_index": 9999, "type": "HIGH",
                    "confirmed": True}])   # bar_index far in the future
print(f"  touch with bar_index=9999 (FUTURE) accepted: "
      f"{[(e['event_type'], e['payload']) for e in eng2.events[b2:]]}")

print()
print("=" * 78)
print("N-009  is_closed is never read by on_new_closed_candle")
print("=" * 78)
eng3 = LiquidityEngineV4()
for i, c in enumerate(candles(25)):
    eng3.on_new_closed_candle(c)
atr0 = eng3._atr_wilder14_last()
n_lv, n_ev = len(eng3.levels), len(eng3.events)
openc = Candle(112.0, 120.0, 80.0, 118.0, 50_000.0, 25,
              False,          # <-- is_closed = False
              BAR0 + 26 * TF)
evs = eng3.on_new_closed_candle(openc)
print(f"  fed Candle(is_closed=False) -> appended to candles: "
      f"{any(x.bar_index == 25 for x in eng3.candles)}")
print(f"  new levels={len(eng3.levels) - n_lv}  new events={len(eng3.events) - n_ev}")
print(f"  ATR {atr0:.6f} -> {eng3._atr_wilder14_last():.6f} "
      f"(wilder state advanced on an UNCLOSED bar)")
print(f"  event types emitted for bar 25: "
      f"{sorted({e['event_type'] for e in eng3.events if e['at_bar'] == 25})}")
print(f"  liquidity_inputs() in engine_context.py filters on bar.is_closed, but")
print(f"  the engine has already used the bar; Candle.is_closed occurrences in "
      f"the engine module:")
import subprocess
print(subprocess.run(["grep", "-n", "is_closed",
                      "apex/engines/e02_liquidity/engine.py"],
                     capture_output=True, text=True).stdout.rstrip() or "  (none)")

print()
print("=" * 78)
print("N-010  streaming merge does not apply §3.3 chain-preventing split")
print("=" * 78)
eng4 = LiquidityEngineV4()
for c in candles(120, trend=0.25, leg=6):
    eng4.on_new_closed_candle(c)
atr = eng4._atr_wilder14_last()
print(f"  ATR14={atr:.6f} theta_eq={eng4.theta_eq} "
      f"theta_eq*ATR={eng4.theta_eq * atr:.6f}")
print(f"  streaming levels={len(eng4.levels)} pools={len(eng4.pools)}")
multi = [l for l in eng4.levels.values() if len(l.members) > 1]
print(f"  levels with >1 member: {len(multi)}")
for l in sorted(multi, key=lambda x: x.price)[:6]:
    print(f"    {l.lid:>24} median_price={l.price:10.4f} members={l.members} "
          f"spread={max(l.members) - min(l.members):.6f}")
worst = max((max(l.members) - min(l.members) for l in eng4.levels.values()
             if len(l.members) > 1), default=0.0)
print(f"  widest member spread inside ONE level = {worst:.6f}")
print(f"  §3.3 requires every member within theta_eq*ATR of the cluster median "
      f"= {eng4.theta_eq * atr:.6f} and diameter <= {2 * eng4.theta_eq * atr:.6f}")
# a >2-tol chain: feed three prices that chain but violate the median rule
eng5 = LiquidityEngineV4()
for c in candles(30):
    eng5.on_new_closed_candle(c)
atr5 = eng5._atr_wilder14_last()
tol5 = eng5.theta_eq * atr5
print(f"\n  deliberate chain test (ATR={atr5:.4f}, tol={tol5:.4f}, "
      f"2*tol={2 * tol5:.4f}):")
eng5.levels.clear()
base = 100.0
eng5._ingest_touch(base, 1, "SWING_EXTREME")
eng5._ingest_touch(base + 1.4 * tol5, 2, "SWING_EXTREME")
eng5._ingest_touch(base + 2.8 * tol5, 3, "SWING_EXTREME")
for l in eng5.levels.values():
    print(f"    lid={l.lid} price={l.price:.6f} instances={l.instances} "
          f"members={[round(m, 5) for m in l.members]} "
          f"diameter={max(l.members) - min(l.members):.6f}")
grp = E02.group_equal_levels_hierarchical(
    [base, base + 1.4 * tol5, base + 2.8 * tol5], atr5, theta_eq=eng5.theta_eq)
print(f"  contract helper group_equal_levels_hierarchical on the same 3 prices "
      f"-> {len(grp)} group(s): "
      f"{[[round(x, 5) for x in g['members']] for g in grp]}")

print()
print("=" * 78)
print("N-011  DBSCAN border chaining: a point reachable only through a border")
print("=" * 78)
pts = [0.0, 0.5, 1.0, 2.0, 2.9]
eps, min_pts = 1.0, 3
core = [p for p in pts
        if sum(1 for q in pts if abs(q - p) <= eps) >= min_pts]
print(f"  prices={pts} eps={eps} min_pts={min_pts}")
print(f"  standard-DBSCAN CORE points: {core}")
print(f"  2.0 has {sum(1 for q in pts if abs(q-2.0) <= eps)} neighbours (BORDER);")
print(f"  2.9 has {sum(1 for q in pts if abs(q-2.9) <= eps)} neighbours and is "
      f"NOT within eps of any core point -> standard DBSCAN: NOISE")
ls = [lvl(p, lid=f"L{i}", instances=2) for i, p in enumerate(pts)]
cl = E02.dbscan_1d_optimal(ls, eps, min_pts)
for c in cl:
    print(f"  engine cluster -> {sorted(round(x.price, 3) for x in c)}")
got = sorted(round(x.price, 3) for cc in cl for x in cc)
print(f"  engine included 2.9 (a NOISE point) ? {2.9 in got}")
print("  -> the BFS re-derives l2/r2 for EVERY dequeued member, so 2.0 (border)")
print("     expands its own neighbourhood and pulls 2.9 into the cluster.")

print()
print("=" * 78)
print("N-012  dbscan timing: sparse vs ONE DENSE cluster (300 / 3000)")
print("=" * 78)
print("  (a) sparse, eps smaller than the spacing (1 cluster per 3 points)")
for n in (300, 3000):
    ls = [lvl(100.0 + i * 0.37, lid=f"L{i}", instances=2) for i in range(n)]
    t0 = time.perf_counter()
    cl = E02.dbscan_1d_optimal(ls, 0.80, 3)
    print(f"      n={n:5d} -> {len(cl):5d} clusters  "
          f"{(time.perf_counter() - t0) * 1000:9.2f} ms")
print("  (b) ONE dense cluster: every point within eps of every other "
      "(the")
print("      case a real 'equal highs' wall produces)")
for n in (300, 600, 1200, 2000):
    ls = [lvl(100.0 + (i % 50) * 0.02, lid=f"L{i}", instances=2) for i in range(n)]
    t0 = time.perf_counter()
    cl = E02.dbscan_1d_optimal(ls, 0.80, 3)
    dt = (time.perf_counter() - t0) * 1000
    print(f"      n={n:5d} -> {len(cl):5d} clusters  {dt:9.2f} ms  "
          f"({dt / n * 1000:.2f} us/level)", flush=True)
import cProfile
import pstats
import io as _io
ls = [lvl(100.0 + (i % 50) * 0.02, lid=f"L{i}", instances=2) for i in range(1200)]
pr = cProfile.Profile()
pr.enable()
E02.dbscan_1d_optimal(ls, 0.80, 3)
pr.disable()
sio = _io.StringIO()
pstats.Stats(pr, stream=sio).sort_stats("tottime").print_stats(4)
print("\n".join(sio.getvalue().splitlines()[4:10]))

print()
print("=" * 78)
print("N-013  p_htf_nearest_cache is keyed by SIDE, not by level price")
print("=" * 78)
eng6 = LiquidityEngineV4()
eng6.set_htf([{"price": 100.0}, {"price": 130.0}], 5.0)
for c in candles(25):
    eng6.on_new_closed_candle(c)
atr6 = eng6._atr_wilder14_last()
cbar = candles(26)[25]
eng6.levels.clear()
# two SELL_SIDE levels far apart; dict order guarantees 102.0 is seen first
eng6.levels["A"] = lvl(102.0, "SELL_SIDE", last_touch=24, first_seen=1)
eng6.levels["B"] = lvl(150.0, "SELL_SIDE", last_touch=24, first_seen=1)
eng6._update_fates(cbar, atr6)
w = eng6.salience_weights
ts = eng6.type_scores
for lid in ("A", "B"):
    l = eng6.levels[lid]
    own = E02.proximity_htf(l.price, eng6._nearest_htf(l.price), eng6.atr_htf)
    shared = E02.proximity_htf(l.price, 100.0, eng6.atr_htf)  # A's HTF price
    exp_own = w["w_t"] * ts.get(l.ltype, .5) + w["w_i"] * min(l.instances / 3, 1) \
        + w["w_f"] * E02.freshness(cbar.bar_index - l.last_touch,
                                   eng6.lambda_decay) + w["w_p"] * own
    exp_shared = w["w_t"] * ts.get(l.ltype, .5) + w["w_i"] * min(l.instances / 3, 1) \
        + w["w_f"] * E02.freshness(cbar.bar_index - l.last_touch,
                                   eng6.lambda_decay) + w["w_p"] * shared
    print(f"  level {lid} price={l.price}: salience={l.salience:.9f}")
    print(f"     with its OWN nearest HTF  ({eng6._nearest_htf(l.price):.1f}) "
          f"-> {exp_own:.9f}  match={abs(exp_own - l.salience) < 1e-9}")
    print(f"     with A's HTF price (100.0)          -> {exp_shared:.9f}  "
          f"match={abs(exp_shared - l.salience) < 1e-9}")

print()
print("=" * 78)
print("N-014  EV_LIQ_008 raid re-fires on later bars from the SAME two sweeps")
print("=" * 78)
eng7 = LiquidityEngineV4(raid_window=3)
cs = candles(200, trend=0.3, amp=9.0, leg=4)
allev = []
for c in cs:
    allev.extend(eng7.on_new_closed_candle(c))
sw = [e for e in allev if e["event_type"] in ("EV_LIQ_005", "EV_LIQ_006")]
rd = [e for e in allev if e["event_type"] == "EV_LIQ_008"]
print(f"  sweeps emitted at bars: {[(e['at_bar'], e['level_id']) for e in sw]}")
print(f"  EV_LIQ_008 raid events: {[(e['at_bar'], e['payload']['side'], e['payload']['count']) for e in rd]}")
if len(rd) > 1:
    print(f"  -> {len(rd)} raid events for {len(sw)} sweeps; the raid window is a")
    print(f"     lookback over sweep_log with no expiry, so one qualifying pair")
    print(f"     keeps re-qualifying on every subsequent bar.")
print()
print("DONE N-008..N-014")
