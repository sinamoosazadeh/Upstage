"""N-010 / N-016 / N-017 (corrected) and N-019 / N-020 / N-021."""
import sys

sys.path.insert(0, "/home/user/Upstage")

from apex.engines.e02_liquidity import engine as E02
from apex.engines.e02_liquidity.engine import (Candle, LiquidityEngineV4,
                                              run_engine, detect_sweep)

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


def warm(eng, n=18, amp=2.0):
    """Feed a constant-range series so ATR14 settles at exactly amp."""
    for i in range(n):
        eng.on_new_closed_candle(Candle(100.0, 100 + amp / 2, 100 - amp / 2,
                                        100.0, 1000.0, i, True, BAR0 + i * TF))
    return eng._atr_wilder14_last()


print("=" * 78)
print("N-010  streaming merge vs §3.3 diameter/median (auditor's exact numbers)")
print("=" * 78)
eng = LiquidityEngineV4()
atr = warm(eng)
tol = eng.theta_eq * atr
print(f"  ATR14={atr:.6f}  theta_eq*ATR={tol:.6f}  D_max=2*theta_eq*ATR="
      f"{2 * tol:.6f}")
seq = [100.0, 100.2, 100.4, 100.5, 100.68]
eng.levels.clear()
for i, p in enumerate(seq):
    eng._ingest_touch(p, 50 + i, "SWING_EXTREME")
print(f"  streaming levels after touches {seq}: {len(eng.levels)}")
for l in eng.levels.values():
    print(f"    {l.lid}: median={l.price:.6f} instances={l.instances} Q={l.Q} "
          f"members={l.members} diameter={max(l.members) - min(l.members):.6f}")
g = E02.group_equal_levels_hierarchical(seq, atr, theta_eq=eng.theta_eq)
print(f"  §3.3 helper on the same touches -> {len(g)} groups "
      f"{[[round(x, 4) for x in q['members']] for q in g]}")
# maximal chain the engine WILL accept
eng2 = LiquidityEngineV4()
atr2 = warm(eng2)
tol2 = eng2.theta_eq * atr2
eng2.levels.clear()
p = 100.0
eng2._ingest_touch(p, 50, "SWING_EXTREME")
touch = [p]
for i in range(1, 10):
    lv = list(eng2.levels.values())[0]
    p = lv.price + 0.999 * tol2          # just inside tol of the RUNNING median
    eng2._ingest_touch(round(p, 8), 50 + i, "SWING_EXTREME")
    touch.append(round(p, 8))
l = list(eng2.levels.values())[0]
print(f"\n  maximal accepted chain touches: {touch}")
print(f"    -> levels={len(eng2.levels)} instances={l.instances} "
      f"Q={l.Q} diameter={max(l.members) - min(l.members):.6f} "
      f"(D_max={2 * tol2:.6f})")
print(f"    max |member - median| = {max(abs(m - l.price) for m in l.members):.6f} "
      f"(§3.3 allows theta_eq*ATR = {tol2:.6f})")
g2 = E02.group_equal_levels_hierarchical(touch, atr2, theta_eq=eng2.theta_eq)
print(f"    §3.3 helper on the same touches -> {len(g2)} groups "
      f"of sizes {[len(q['members']) for q in g2]}")
print(f"  VERDICT INPUT: diameter {'>' if max(l.members)-min(l.members) > 2*tol2 else '<='}"
      f" D_max; the engine has NO diameter test at all (only"
      f" |new - running_median| <= tol).")

print()
print("=" * 78)
print("N-016  Q3 assigned at bar 7 and never reverted (auditor: bar 4 -> bar 20)")
print("=" * 78)
eng3 = LiquidityEngineV4()
traj = []
for i, c in enumerate(candles(40, leg=5, amp=6.0)):
    eng3.on_new_closed_candle(c)
    if i in (3, 4, 6, 7, 9, 13, 14, 19, 20, 30, 39):
        traj.append((i, [(l.lid, l.instances, l.Q, l.fate)
                         for l in eng3.levels.values()]))
for i, lv in traj:
    print(f"  bar {i:3d}: {lv}")
print(f"  detect_sweep P1 requires level.Q in ('Q1','Q2'): "
      f"{E02.detect_sweep.__doc__ is not None}")
import inspect
src = inspect.getsource(detect_sweep)
print(f"  source line: {[ln.strip() for ln in src.splitlines() if 'lv.Q in' in ln]}")
print(f"  _update_fates Q assignments: "
      f"{[ln.strip() for ln in inspect.getsource(LiquidityEngineV4._update_fates).splitlines() if '.Q =' in ln]}")

print()
print("=" * 78)
print("N-017  same instance, same OHLCV, different params -> cache aliasing")
print("=" * 78)


class FakeObs:
    def __init__(self, c):
        self.open, self.high, self.low, self.close = (c.open, c.high, c.low,
                                                      c.close)
        self.volume, self.sequence = c.volume, c.bar_index
        self.timestamp = "2026-01-01T00:00:00.000Z"
        self.availability_time = self.timestamp
        self.completeness_pct = 100.0
        self.symbol, self.timeframe, self.status = "BTCUSDT", "1h", "CLOSED"

    def content_hash(self):
        return "a" * 64


obs = [FakeObs(c) for c in candles(120, leg=5, amp=8.0, trend=0.2)]
eng4 = E02.E02LiquidityEngine()
AS_OF = "2026-01-01T00:00:00.000Z"
r1 = eng4.compute("BTCUSDT", "1h", AS_OF,
                  {"window": obs, "e02_params": {"level_expiry_bars": 96}})
print(f"  call 1 (level_expiry_bars=96): {len(r1)} events; "
      f"cache={len(eng4._replay_cache)}")
r2 = eng4.compute("BTCUSDT", "1h", AS_OF,
                  {"window": obs, "e02_params": {"level_expiry_bars": 0}})
print(f"  call 2 (level_expiry_bars=0)  : {len(r2)} events; "
      f"cache={len(eng4._replay_cache)}")
print(f"  call 2 returned call 1's object? {r2 is r1}  "
      f"identical content? {r2 == r1}")
fresh = run_engine([E02.observation_to_candle(o) for o in obs],
                   E02.get_params({"level_expiry_bars": 0}))
print(f"  a FRESH engine with level_expiry_bars=0 would give "
      f"{len(fresh.events)} raw events")
print(f"  -> within the {E02.REPLAY_TTL_MAX_SECONDS if hasattr(E02,'REPLAY_TTL_MAX_SECONDS') else 300}s")
print(f"     TTL the second parameter set is never evaluated.")

print()
print("=" * 78)
print("N-019  E01/E02 lineage tokens are index-derived, not raw parent ids")
print("=" * 78)
eng5 = E02.E02LiquidityEngine()
res = eng5.compute("BTCUSDT", "1h", AS_OF, {"window": obs})
raw = {o.content_hash() for o in obs}
print(f"  raw observation content_hashes: {len(raw)} distinct")
lins = set()
for ev in res:
    lins.update(ev.lineage)
print(f"  E02 lineage tokens emitted ({len(lins)}): {sorted(lins)[:6]} ...")
print(f"  any token equal to a raw content_hash? "
      f"{bool(lins & raw)}")
print(f"  token pattern: 'candle_<bar_index>' (E02 _to_evidence lineage=)")
src6 = inspect.getsource(E02.E02LiquidityEngine._to_evidence)
print(f"  source: {[ln.strip() for ln in src6.splitlines() if 'lineage=' in ln]}")
# Gate 11 only validates the TOKEN FORMAT
from apex.setup import gates
g11 = gates.gate11_snapshot_lineage("a" * 64, {"k": 1}, ["candle_19"])
print(f"  Gate11 with lineage=['candle_19'] -> passed={g11.passed} "
      f"reason={g11.reason!r}")
g11b = gates.gate11_snapshot_lineage("a" * 64, {"k": 1}, ["not-a-real-id"])
print(f"  Gate11 with lineage=['not-a-real-id'] -> passed={g11b.passed} "
      f"reason={g11b.reason!r}")
print(f"  _ID_TOKEN regex: {gates._ID_TOKEN.pattern}")

print()
print("=" * 78)
print("N-020  _update_pools ignores member REMOVAL for an existing pid")
print("=" * 78)
eng6 = LiquidityEngineV4()
atr6 = warm(eng6, n=20, amp=2.0)
eps_pool = 2 * eng6.theta_eq * atr6 * eng6.kappa
print(f"  ATR14={atr6:.4f} eps_pool={eps_pool:.4f}")
for p in (100.0, 100.1, 100.2, 100.3):
    eng6.levels[f"x{p}"] = E02.Level(
        lid=f"x{p}", price=p, side="SELL_SIDE", ltype="SWING_EXTREME",
        instances=2, first_seen=0, last_touch=19, touch_count=2,
        salience=0.9, fate="ACTIVE", Q="Q2", members=[p, p])
eng6.pools.clear()
eng6.events.clear()
eng6.candles = candles(25)
eng6._update_pools(atr6)
for pid, pool in eng6.pools.items():
    print(f"  pool {pid}: members={pool.member_level_ids} weight={pool.weight:.4f}")
# now sweep the middle level
eng6.levels["x100.1"].fate = "SWEPT"
eng6.events.clear()
eng6._update_pools(atr6)
for pid, pool in eng6.pools.items():
    print(f"  after sweeping x100.1 -> pool members={pool.member_level_ids} "
          f"weight={pool.weight:.4f}")
    print(f"     events emitted this bar: {[e['event_type'] for e in eng6.events]}")
act = [l for l in eng6.levels.values() if l.fate in ("ACTIVE", "STRENGTHENED")]
w = E02.compute_pool_weight(act, eps_pool)
print(f"  actually ACTIVE levels now: {sorted(l.lid for l in act)}")
print(f"  recomputed weight from the live members: {w:.4f}")
print(f"  stale weight on the pool object      : "
      f"{list(eng6.pools.values())[0].weight:.4f}")
print(f"  the guard is `if not new_member_sets[pid].issubset(old)` — a strict")
print(f"  SUBSET (member loss) takes the no-op branch.")

print()
print("=" * 78)
print("N-021  accepted E02 parameters never reach detect_sweep")
print("=" * 78)
p = E02.get_params({"sweep_weights": [0.9, 0.05, 0.02, 0.02, 0.01],
                    "sweep_cooldown_bars": 99, "T_hit": 7,
                    "utc_activity_windows": [("UTC_W0", 0.0, 24.0)]})
eng7 = run_engine(candles(80, leg=5, amp=8.0, trend=0.2), p)
print(f"  get_params accepted the overrides: {p['sweep_weights']}, "
      f"sweep_cooldown_bars={p['sweep_cooldown_bars']}, T_hit={p['T_hit']}")
print(f"  engine.sweep_weights actually stored: {eng7.sweep_weights}")
print(f"  engine.raid_window={eng7.raid_window} (the cooldown the sweeps use)")
src7 = __import__("inspect").getsource(detect_sweep)
sig = [ln.strip() for ln in src7.splitlines() if "sweep_weights" in ln]
print(f"  detect_sweep mentions sweep_weights? {bool(sig)} -> {sig}")
print(f"  weights are hard-coded in the score line: "
      f"{[ln.strip() for ln in src7.splitlines() if 'w_p, w_r' in ln]}")
call = [ln.strip() for ln in __import__("inspect").getsource(
    LiquidityEngineV4._detect_sweeps).splitlines() if "detect_sweep(" in ln
    or "self.sweep_min_pen" in ln]
print(f"  _detect_sweeps call site: {call}")
print(f"  volume_profile_ok is passed as: "
      f"{[ln.strip() for ln in __import__('inspect').getsource(LiquidityEngineV4._detect_sweeps).splitlines() if 'volume_profile_ok' in ln]}")
print(f"  utc_activity_windows override honoured? module constant used: "
      f"{E02.utc_window_of(3.0)} vs params {p['utc_activity_windows']}")
print("DONE N-010,N-016,N-017,N-019,N-020,N-021")
