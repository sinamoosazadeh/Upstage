"""N-010, N-015..N-021 — real apex.engines.e02_liquidity.engine only."""
import sys
import time

sys.path.insert(0, "/home/user/Upstage")

from apex.engines.e02_liquidity import engine as E02
from apex.engines.e02_liquidity.engine import (Candle, Level,
                                              LiquidityEngineV4,
                                              generate_snapshot_id, run_engine,
                                              sweep_outcomes, detect_sweep)
from apex.engines.base import REPLAY_TTL_MAX_SECONDS

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
print("N-010  streaming merge: auditor's exact touch sequence (ATR=2, th=0.15)")
print("=" * 78)
eng = LiquidityEngineV4()
# force ATR to exactly 2.0 by feeding a flat-range series
flat = [Candle(100.0, 101.0, 99.0, 100.0, 1000.0, i, True, BAR0 + i * TF)
        for i in range(20)]
for c in flat[:15]:
    eng.on_new_closed_candle(c)
atr = eng._atr_wilder14_last()
print(f"  ATR14 = {atr:.6f}  (target 2.0)  theta_eq*ATR = "
      f"{eng.theta_eq * atr:.6f}  D_max = {2 * eng.theta_eq * atr:.6f}")
eng.levels.clear()
eng2 = LiquidityEngineV4(theta_eq=eng.theta_eq)
eng2.levels = {}
seq = [100.0, 100.2, 100.4, 100.5, 100.68]
for i, p in enumerate(seq):
    eng2._ingest_touch(p, 100 + i, "SWING_EXTREME")
for l in eng2.levels.values():
    print(f"    level {l.lid} price(median)={l.price:.6f} "
          f"instances={l.instances} Q={l.Q} members={l.members} "
          f"diameter={max(l.members) - min(l.members):.6f}")
print(f"  levels formed: {len(eng2.levels)}  "
      f"(§3.3 helper would split them:)")
groups = E02.group_equal_levels_hierarchical(seq, atr, theta_eq=eng2.theta_eq)
print(f"    group_equal_levels_hierarchical -> {len(groups)} groups: "
      f"{[[round(x, 4) for x in g['members']] for g in groups]}")
# now a maximal chain the engine WILL accept
eng3 = LiquidityEngineV4(theta_eq=eng.theta_eq)
eng3.levels = {}
tol = eng3.theta_eq * atr
seq2 = [100.0]
p = 100.0
for _ in range(12):
    p = p + 0.999 * tol          # always within tol of the running median?
    seq2.append(round(p, 6))
    eng3._ingest_touch(round(p, 6), 100 + len(seq2), "SWING_EXTREME")
for l in eng3.levels.values():
    print(f"    maximal chain -> level instances={l.instances} "
          f"members={len(l.members)} diameter="
          f"{max(l.members) - min(l.members):.6f}  "
          f"(D_max = {2 * eng3.theta_eq * atr:.6f})  Q={l.Q}")
    print(f"      max |member - median| = "
          f"{max(abs(m - l.price) for m in l.members):.6f}  "
          f"(contract: <= theta_eq*ATR = {eng3.theta_eq * atr:.6f})")
g2 = E02.group_equal_levels_hierarchical(seq2, atr, theta_eq=eng3.theta_eq)
print(f"    contract helper on the same touches -> {len(g2)} groups: "
      f"{[len(g['members']) for g in g2]}")
print(f"  NOTE: _ingest_touch rewrites lv.price to the running median, so the")
print(f"  next test is against the MOVING median, never the level origin, and")
print(f"  no check compares max(member)-min(member) with 2*theta_eq*ATR.")

print()
print("=" * 78)
print("N-015  sweep_outcomes: SELL_SIDE counts an UP move as genuine")
print("=" * 78)
base_close = 100.0
cs = [Candle(100.0, 100.5, 99.5, base_close, 1000.0, 0, True, BAR0)]
for i, cl in enumerate([99.0] * 5, start=1):
    cs.append(Candle(100.0, 100.2, cl - 0.1, cl, 1000.0, i, True, BAR0 + i * TF))
log_down = [{"level_id": "L", "side": "SELL_SIDE", "at_bar": 0, "score": 0.5}]
print(f"  SELL_SIDE sweep at bar 0, next 5 closes all 99.0 (price FELL back "
      f"under the level = the contract's 'genuine')")
print(f"    sweep_outcomes -> {sweep_outcomes(log_down, cs, atr_now=1.0, horizon=5)}")
cs2 = [Candle(100.0, 100.5, 99.5, base_close, 1000.0, 0, True, BAR0)]
for i, cl in enumerate([101.0] * 5, start=1):
    cs2.append(Candle(100.0, 101.2, cl - 0.1, cl, 1000.0, i, True, BAR0 + i * TF))
print(f"  same sweep, next 5 closes all 101.0 (price ROSE through the level = "
      f"NOT a reversal)")
print(f"    sweep_outcomes -> {sweep_outcomes(log_down, cs2, atr_now=1.0, horizon=5)}")
print("  source: `move = max(f.close - base ...)` for SELL_SIDE — a HIGHER close")
print("         is scored as the successful outcome.")
log_buy = [{"level_id": "L", "side": "BUY_SIDE", "at_bar": 0, "score": 0.5}]
print(f"  BUY_SIDE mirror, closes falling to 99.0 -> "
      f"{sweep_outcomes(log_buy, cs, atr_now=1.0, horizon=5)}  (mirrored too)")
# partial horizon
cs3 = [Candle(100.0, 100.5, 99.5, 100.0, 1000.0, 0, True, BAR0),
       Candle(100.0, 100.2, 98.9, 99.0, 1000.0, 1, True, BAR0 + TF)]
print(f"  only t+1 of horizon=5 exists -> n counted: "
      f"{sweep_outcomes(log_down, cs3, atr_now=1.0, horizon=5)[1]} "
      f"(1, not 0 — partial horizon still scored)")

print()
print("=" * 78)
print("N-016  E02 min_candles=50 never reaches the stream; Q3 never reverts")
print("=" * 78)
import inspect
src = inspect.getsource(run_engine)
print("  run_engine body mentions min_candles? ", "min_candles" in src)
print("  LiquidityEngineV4.__init__ mentions min_candles? ",
      "min_candles" in inspect.getsource(LiquidityEngineV4.__init__))
print("  E02_DEFAULTS['min_candles'] =", E02.E02_DEFAULTS["min_candles"])
eng4 = LiquidityEngineV4()
first_formed = None
first_q3 = None
for i, c in enumerate(candles(60, leg=5, amp=8.0)):
    eng4.on_new_closed_candle(c)
    if first_formed is None and eng4.levels:
        first_formed = (i, [(l.lid, l.instances, l.Q) for l in eng4.levels.values()])
    if first_q3 is None and any(l.Q == "Q3" for l in eng4.levels.values()):
        first_q3 = (i, [(l.lid, l.instances, l.Q) for l in eng4.levels.values()])
print(f"  first bar with ANY level: {first_formed[0]}  {first_formed[1]}")
print(f"  first bar with a Q3 level: {first_q3[0]}  {first_q3[1]}")
q3 = [l for l in eng4.levels.values() if l.Q == "Q3"]
print(f"  at bar 59: levels={len(eng4.levels)}  still Q3={len(q3)}  "
      f"{[(l.lid, l.instances, l.Q) for l in q3][:5]}")
print("  _update_fates only assigns Q2 and, while len(candles) < 14, Q3.")
print("  There is NO Q3 -> Q1 path: a level tagged Q3 before bar 14 keeps Q3")
print("  forever (Q3 is not in the P1 valid set of detect_sweep).")
src2 = inspect.getsource(E02.detect_sweep)
print("  detect_sweep P1 valid Q set:",
      [ln.strip() for ln in src2.splitlines() if 'lv.Q in' in ln])

print()
print("=" * 78)
print("N-017  E02 replay key omits t_close and every parameter but theta/kappa")
print("=" * 78)
print("  compute() replay construction:")
s = inspect.getsource(E02.E02LiquidityEngine.compute)
print("   ", [ln.strip() for ln in s.splitlines()
                if "input_hash" in ln or "build_replay_key" in ln
                or "replay_lookup" in ln or "_canon({" in ln])
print("  observation_to_candle -> Candle.to_dict keys:",
      sorted(Candle(1, 1, 1, 1, 1, 0, True, 0).to_dict().keys()))
print("  (t_close is NOT in to_dict, so the input_hash ignores bar times)")
# demonstrate cache aliasing on ONE instance
cs4 = candles(120, trend=0.2, leg=5, amp=8.0)


class FakeObs:
    def __init__(self, c):
        self.open, self.high, self.low, self.close = c.open, c.high, c.low, c.close
        self.volume, self.sequence = c.volume, c.bar_index
        self.timestamp = "2026-01-01T00:00:00.000Z"
        self.availability_time = self.timestamp
        self.completeness_pct = 100.0
        self.symbol, self.timeframe, self.status = "BTCUSDT", "1h", "CLOSED"

    def content_hash(self):
        return "a" * 64


obs = [FakeObs(c) for c in cs4]
engA = E02.E02LiquidityEngine()
engB = E02.E02LiquidityEngine()
ctx = {"window": obs}
rA = engA.compute("BTCUSDT", "1h", "2026-01-01T00:00:00.000Z", ctx)
print(f"  run 1: {len(rA)} evidence events, cache entries="
      f"{len(engA._replay_cache)}")
kA = list(engA._replay_cache)
# same OHLCV, DIFFERENT level_expiry_bars -> different engine state
engB2 = E02.E02LiquidityEngine()
from apex.engines.e02_liquidity.engine import LiquidityEngineV4 as L4
fresh = run_engine(cs4, E02.get_params({"level_expiry_bars": 96}))
fresh0 = run_engine(cs4, E02.get_params({"level_expiry_bars": 0}))
print(f"  run_engine(level_expiry_bars=96) events={len(fresh.events)}  "
      f"level_expiry_bars=0 events={len(fresh0.events)}  "
      f"expired={sum(1 for e in fresh0.events if e['event_type'] == 'EV_LIQ_011')}")
# replay_lookup of engA with the key engB would build
replayB = engB.build_replay_key(
    "BTCUSDT", "1h", "2026-01-01T00:00:00.000Z",
    E02._sha_of(E02._canon([c.to_dict() for c in
                            [E02.observation_to_candle(o) for o in obs]])),
    "E02-LIQ-V4.0.0-DEFAULTS", E02._canon({"theta_eq": 0.15, "kappa": 1.0}))
print(f"  engA cache keys == engB computed key ? {kA == [replayB]}")
print(f"  engA.replay_lookup(key_from_other_instance) -> "
      f"{engA.replay_lookup(replayB) is not None}")
print("  -> the key contains engine_version, contract_version, symbol, tf,")
print("     as_of, input_hash (no t_close), parameter_package_id (a CONSTANT")
print("     string) and _canon({theta_eq, kappa}) only.  level_expiry_bars,")
print("     sweep_min_pen/rej, lambda_decay, raid_window, htf, l2_snapshots")
print("     are all absent; TTL is {0:.0f}-{1:.0f}s (base.REPLAY_*).".format(
    __import__("apex.engines.base", fromlist=["x"]).REPLAY_TTL_MIN_SECONDS,
    REPLAY_TTL_MAX_SECONDS))

print()
print("=" * 78)
print("N-018  E02 snapshot identity collides across different states")
print("=" * 78)
e1 = LiquidityEngineV4()
for c in candles(60, leg=5, amp=8.0, trend=0.2):
    e1.on_new_closed_candle(c)
e1.levels.clear()
e1.events.clear()
e1.pools.clear()
e2 = LiquidityEngineV4()
for c in candles(60, leg=5, amp=8.0, trend=0.2):
    e2.on_new_closed_candle(c)
e2.levels.clear()
e2.events.clear()
e2.pools.clear()
e1._ingest_touch(100.0, 5, "SWING_EXTREME")
e2._ingest_touch(100.0, 5, "SWING_EXTREME")
e1._ingest_touch(101.0, 6, "SWING_EXTREME")
e2._ingest_touch(140.0, 6, "SWING_EXTREME")     # different price!
o1, o2 = e1.output(), e2.output()
print(f"  engine1 levels={[ (l['lid'], l['price']) for l in o1['levels'] ]}")
print(f"  engine2 levels={[ (l['lid'], l['price']) for l in o2['levels'] ]}")
print(f"  output() snapshot_id 1 = {o1['snapshot_id']}")
print(f"  output() snapshot_id 2 = {o2['snapshot_id']}")
print(f"  COLLISION: {o1['snapshot_id'] == o2['snapshot_id']}")
src3 = inspect.getsource(LiquidityEngineV4.output)
print("  output() snapshot payload:",
      [ln.strip() for ln in src3.splitlines() if '"levels"' in ln][:2])
# level snapshot_id frozen at formation
lid = o1["levels"][0]["lid"]
lv = e1.levels[lid]
snap0 = lv.snapshot_id
e1._ingest_touch(100.05, 9, "SWING_EXTREME")
print(f"  Level.snapshot_id after a new member: {lv.snapshot_id == snap0} "
      f"(unchanged)  price now {lv.price}  members {lv.members}")
print("DONE N-010,N-015..N-018")
