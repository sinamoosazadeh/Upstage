"""N-008: a level that has exactly ONE confirmed touch is born Q1/ACTIVE and
can emit a Q1 sweep.  Real E02 only."""
import sys

sys.path.insert(0, "/home/user/Upstage")

from apex.engines.e02_liquidity.engine import (
    Candle, LiquidityEngineV4, detect_sweep)


def flat(i, o=100.0, h=100.2, l=99.8, c=100.0, v=1000.0):
    return Candle(open=o, high=h, low=l, close=c, volume=v, bar_index=i,
                  is_closed=True, t_close=1_700_000_000_000 + i * 3_600_000)


print("=" * 78)
print("N-008  ONE confirmed touch -> instances=1, Q1, and a Q1 SWEEP")
print("=" * 78)
eng = LiquidityEngineV4()
# 20 flat bars so ATR(14) exists and is ~0.4; then force ATR to 2.0 by a
# deterministic last-touch so the arithmetic is readable.
for i in range(20):
    eng.on_new_closed_candle(flat(i))
atr = eng._atr_wilder14_last()
print(f"  after 20 flat bars: ATR14 = {atr:.6f}  theta_eq*ATR = "
      f"{eng.theta_eq * atr:.6f}")
print(f"  levels so far: {[(k, round(v.price,4), v.instances, v.Q, v.fate, v.ltype) for k,v in eng.levels.items()]}")

# widen ATR deterministically to exactly 2.0 so the fixture is legible
target = 2.0
eng.candles[-14:] = [flat(i, o=100.0 - (target - atr) * 0, h=101.0,
                          l=99.0, c=100.0, v=1000.0) for i in
                     range(len(eng.candles) - 14, len(eng.candles))]
eng._atr14_memo = None
atr = eng._atr_wilder14_last()
print(f"  ATR after a 2.0 range for 14 bars: {atr:.6f} "
      f"(theta_eq*ATR = {eng.theta_eq * atr:.6f})")

# a SINGLE confirmed touch at 102.00, far from any existing level
n_before = len(eng.levels)
ev = eng._ingest_touch(102.00, eng.candles[-1].bar_index, "SWING_EXTREME")
lv_id = [e["level_id"] for e in ev if e["event_type"] == "EV_LIQ_001"][0]
lv = eng.levels[lv_id]
print(f"  ONE touch ingested at 102.00 -> level {lv_id}")
print(f"    instances={lv.instances}  touch_count={lv.touch_count}  Q={lv.Q}  "
      f"fate={lv.fate}  ltype={lv.ltype}  side={lv.side}  salience={lv.salience:.4f}")
print(f"    levels before={n_before} after={len(eng.levels)}")
print(f"    CONFIRMED: the contract Q1 law (>=2 observations) is not applied at")
print(f"    formation; the code hard-codes Q='Q1', instances=1.")

# next bar -> FORMED becomes ACTIVE
last = len(eng.candles) - 1
eng.on_new_closed_candle(flat(len(eng.candles), o=100.0, h=100.3, l=99.7, c=100.0))
print(f"  one bar later: fate={lv.fate}  Q={lv.Q}  age="
      f"{eng.candles[-1].bar_index - lv.last_touch}")

# now a genuine sweep of that ONE-touch level
i = len(eng.candles)
sw = flat(i, o=100.0, h=103.0, l=99.5, c=100.5, v=1500.0)
atr_now = eng._atr_wilder14_last()
vol_sma = sum(x.volume for x in eng.candles[-20:]) / min(20, len(eng.candles))
kind, prereq, score = detect_sweep(sw, lv, atr_now, vol_sma,
                                   eng.sweep_min_pen, eng.sweep_min_rej)
print(f"  detect_sweep(one-touch Q1 level) -> {kind} score={score:.4f}")
print(f"    prereq {prereq}   all P1..P5 True = {all(prereq.values())}")
out = eng.on_new_closed_candle(sw)
sweeps = [e for e in out if e["event_type"] in ("EV_LIQ_005", "EV_LIQ_006")]
for e in sweeps:
    print(f"    EMITTED {e['event_type']} at_bar={e['at_bar']} Q={e['Q']} "
          f"payload={e['payload']}")
print(f"  sweep events emitted: {len(sweeps)}")
print(f"  level {lv_id} now: instances={lv.instances} Q={lv.Q} fate={lv.fate}")
print()
print("  P1's own test (engine.py:289-292):")
print("   ", [ln.strip() for ln in open(
    "/home/user/Upstage/apex/engines/e02_liquidity/engine.py").read()
    .splitlines()[288:292]])
print("  -> P1 requires only fate in (ACTIVE, STRENGTHENED), Q in (Q1, Q2)")
print("     and first_seen <= bar-1.  A single touch satisfies all three after")
print("     one bar, so a one-observation level is a valid P1 sweep origin.")

print()
print("=" * 78)
print("side note — feed_touches' documented key is `type`, the code reads")
print("`ltype`; and pre-ATR touches are queued as 'SWING_EXTREME' by default")
print("=" * 78)
eng2 = LiquidityEngineV4()
eng2.feed_touches([{"price": 102.0, "bar_index": 0, "type": "HIGH",
                    "confirmed": True}])
print(f"  feed_touches BEFORE any candle -> _pending_touches="
      f"{eng2._pending_touches}")
print(f"  (queued, not yet a level: {len(eng2.levels)} levels)")
