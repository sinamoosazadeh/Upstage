"""Q-005: RTM.CHAIN.v1 without the 'retest' component still passes both
thresholds (coverage 0.833 >= th_weight 0.6, integrity 0.833 >= th_int 0.7)
and emits a bundle + EV_RTM_011, although §5.3.1 defines the hunt chain as
sweep -> CHoCH -> FVG -> retest -> volume."""
import datetime
from apex.engines.e07_rtm.engine import run_engine, expected_components

ts0 = int(datetime.datetime(2026, 3, 2, 0, 0,
                            tzinfo=datetime.timezone.utc).timestamp() * 1000)
bars = [{"ts": ts0 + i * 3600_000, "o": 100, "h": 101, "l": 99, "c": 100.5,
         "v": 1000.0} for i in range(60)]
as_of = bars[-1]["ts"]
fw = "RTM.CHAIN.v1"
exp = expected_components(fw)
print("expected chain:", [(c.cid, c.weight) for c in exp])
# omit 'retest' only
confs = [{"cid": c.cid, "t_confirm_ms": as_of - (6 - i) * 60000,
          "p_confirm": 100.0 + i}
         for i, c in enumerate(exp) if c.cid != "retest"]
res = run_engine(bars, events=confs, framework_id=fw, as_of_ms=as_of)
b = res["bundle"]
print("integrity=%.4f weight_coverage=%.4f missing=%s" % (
    res["integrity"], res["weight_coverage"], res["missing"]))
print("bundle emitted =", b is not None, "| events =", res["events"])
assert b is not None and "EV_RTM_011" in res["events"]
assert "retest" in b.components_missing
print("Q-005 CONFIRMED: retest-less CHAIN bundle emitted "
      "(integrity %.3f >= 0.7, coverage %.3f >= 0.6)" % (
          res["integrity"], res["weight_coverage"]))
