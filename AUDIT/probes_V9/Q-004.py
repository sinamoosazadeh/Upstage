"""Q-004: mss_confirmed / mss_proximity_check (the §3.3 proximity rule
|p_sweep - p_choch| <= 0.5*ATR20) are exported but never invoked by the
bundle path: an RTM.MSS.v1 bundle is emitted even when proximity fails."""
import datetime, subprocess
from apex.engines.e07_rtm.engine import (run_engine, expected_components,
                                         mss_confirmed, mss_proximity_check)

ts0 = int(datetime.datetime(2026, 3, 2, 0, 0,
                            tzinfo=datetime.timezone.utc).timestamp() * 1000)
bars = [{"ts": ts0 + i * 3600_000, "o": 100, "h": 101, "l": 99, "c": 100.5,
         "v": 1000.0} for i in range(60)]
as_of = bars[-1]["ts"]
fw = "RTM.MSS.v1"
# sweep at price 100, CHoCH at price 200 -> |diff|=100 >> 0.5*ATR20 (~1)
confs = [{"cid": "sweep", "t_confirm_ms": as_of - 120000, "p_confirm": 100.0},
         {"cid": "choch", "t_confirm_ms": as_of - 60000, "p_confirm": 200.0}]
atr20 = 2.0
print("mss_proximity_check(100,200,atr=2) =",
      mss_proximity_check(100.0, 200.0, atr20))
print("mss_confirmed(100,200,atr=2,integrity=1.0) =",
      mss_confirmed(100.0, 200.0, atr20, 1.0))
res = run_engine(bars, events=confs, framework_id=fw, as_of_ms=as_of)
b = res["bundle"]
print("MSS bundle emitted =", b is not None,
      "| integrity=%.3f class=%s" % (b.integrity, b.resolution_class))
assert b is not None, "bundle should be emitted despite failed proximity"

grep = subprocess.run(["grep", "-rn", "mss_confirmed\\|mss_proximity_check",
                       "apex/"], capture_output=True, text=True
                      ).stdout.strip().splitlines()
callers = [l for l in grep if "def mss_" not in l and "__init__.py" not in l
           and "engine.py" not in l.split(":")[0].rsplit("/", 1)[-1]]
print("apex/ references outside definitions/re-exports:", callers)
assert callers == []
print("Q-004 CONFIRMED: MSS proximity/confirmation rule dead code; bundle "
      "emitted with |p_sweep-p_choch| = 50*ATR20")
