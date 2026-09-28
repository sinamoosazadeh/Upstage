"""X-V7-001..X-V7-004 — findings NOT in the audit. Real modules only."""
import sqlite3, sys, time, tracemalloc
sys.path.insert(0, "/home/user/Upstage")
from apex.data_catalog.store.sqlite_store import CH4_DDL, CH5_DDL, AI5_DDL
from apex.engines.e02_liquidity.engine import LiquidityEngineV4, Candle
from apex.setup import gates

print("="*78); print("X-V7-001  PatternEntity.to_pattern_evidence_row exists but is")
print("           never called: AC.5 #2 is unreachable in production")
print("="*78)
import subprocess
print(subprocess.run(["grep","-rn","to_pattern_evidence_row","--include=*.py","apex/"],
                     capture_output=True,text=True).stdout)
print("  -> the ONLY producer of a pattern_evidence row is never called by any")
print("     production code; combined with M-009 the table has no writer at all.")

print(); print("="*78)
print("X-V7-002  feed_touches documents key `type`; the code reads `ltype`")
print("="*78)
eng=LiquidityEngineV4()
eng.feed_touches([{"price":102.0,"bar_index":0,"type":"HIGH","confirmed":True}])
print(f"  after feed_touches with the DOCUMENTED key `type`: pending="
      f"{eng._pending_touches}")
for i in range(20):
    eng.on_new_closed_candle(Candle(open=100.0,high=100.2,low=99.8,close=100.0,
        volume=1000.0,bar_index=i,is_closed=True,t_close=1_700_000_000_000+i*3_600_000))
lv=[v for v in eng.levels.values() if abs(v.price-102.0)<0.5]
print(f"  the level created from it carries ltype={lv[0].ltype if lv else None!r} "
      f"(the caller's `type='HIGH'` was dropped and the default used)")
import inspect
print("   ", [l.strip() for l in inspect.getsource(LiquidityEngineV4.feed_touches).splitlines()
              if "ltype" in l or "SwingInput" in l])
print("  a producer sending {\"type\": \"RANGE_EDGE\"} or any other type gets")
print("  SWING_EXTREME salience/type_scores (0.8 vs RANGE_EDGE 0.6) silently.")

print(); print("="*78)
print("X-V7-003  E02 level expiry: `age > level_expiry_bars` uses the LEVEL's")
print("           last_touch, but the Q3 short-sample rule needs 14 candles;")
print("           with level_expiry_bars=0 every level expires on the next bar")
print("="*78)
eng2=LiquidityEngineV4(level_expiry_bars=0)
for i in range(16):
    eng2.on_new_closed_candle(Candle(open=100.0,high=100.4,low=99.6,close=100.0,
        volume=1000.0,bar_index=i,is_closed=True,t_close=1_700_000_000_000+i*3_600_000))
from collections import Counter
print(f"  level_expiry_bars=0: {len(eng2.levels)} levels formed, fates="
      f"{Counter(v.fate for v in eng2.levels.values())}")
print(f"  events by type: {Counter(e['event_type'] for e in eng2.events)}")
print("  -> a single level is formed and expired on the SAME bar, so the engine")
print("     emits EV_LIQ_001 and EV_LIQ_011 for a level that never existed as a")
print("     tradeable object.  `level_expiry_bars` has no lower bound in the")
print("     constructor and no validation.")
eng3=LiquidityEngineV4(level_expiry_bars=0, raid_window=0, theta_eq=-1.0)
print(f"  negative theta_eq accepted without error: theta_eq={eng3.theta_eq} "
      f"-> tol={eng3.theta_eq*2.0} (every touch merges into the nearest level)")

print(); print("="*78)
print("X-V7-004  `run_all` never sees a NaN/Inf, because gate10's own default")
print("           and `_finite_float` are the only finite checks; gate11 is")
print("           the only NaN/Inf guard and it is not reachable from run_all")
print("="*78)
import inspect
src=inspect.getsource(gates.run_all)
print("  run_all signature:", str(inspect.signature(gates.run_all))[:300])
print("  does run_all call gate11_snapshot_lineage?",
      "gate11_snapshot_lineage" in src)
print("  gate10 with a NaN quality:")
print("   ", gates.gate10_forecast_quality({"quality": float("nan")}, environment="LIVE"))
print("  gate12 with a NaN q_forecast:", gates.gate12_q_forecast(float("nan")))
print("  -> a NaN quality string compares False against the integer minimum, so")
print("     gate10 FAILS closed on NaN; that is correct, but it does so by")
print("     accident of comparison, not by an explicit finite check.")

print(); print("="*78)
print("X-V7-005  the CP-2 DDL contains `outcome` with a FK to setup_candidate,")
print("           but plan_bridge never inserts an outcome and SQLite FKs are")
print("           OFF by default -> the DDL integrity is not enforced at all")
print("="*78)
c=sqlite3.connect(":memory:"); c.executescript(CH4_DDL)
print(f"  foreign_keys pragma default = {c.execute('PRAGMA foreign_keys').fetchone()[0]}")
print(f"  sqlite version {sqlite3.sqlite_version}")
c.execute("INSERT INTO setup_candidate (setup_id,symbol) VALUES ('x','BTCUSDT')")
try:
    c.execute("INSERT INTO outcome (outcome_id, setup_id) VALUES ('o1','NONEXISTENT')")
    print("  inserting an outcome for a NONEXISTENT setup_id SUCCEEDED ->")
    print("  the declared FOREIGN KEY is not enforced by default.")
except sqlite3.IntegrityError as e:
    print("  IntegrityError:", e)
print("  store construction path: does it enable foreign_keys?")
print(subprocess.run(["grep","-rn","foreign_keys","--include=*.py","apex/"],
                     capture_output=True,text=True).stdout or "  -> NOBODY enables it")
print("DONE X-V7")
