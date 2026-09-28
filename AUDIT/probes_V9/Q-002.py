"""Q-002: run_engine computes range_info (atr_ratio_detect) but the bundle
pipeline is unconditional: a PO3 bundle (EV_RTM_004) is emitted even when
is_range=False, i.e. the RTM premise 'inside a range' is never enforced."""
import datetime
from apex.engines.e07_rtm.engine import run_engine, expected_components

ts0 = int(datetime.datetime(2026, 3, 2, 0, 0,
                            tzinfo=datetime.timezone.utc).timestamp() * 1000)
# 120 strongly trending bars -> definitely NOT a range
bars = []
px = 100.0
for i in range(120):
    o = px
    c = px * 1.01           # +1% every bar, monotone trend
    bars.append({"ts": ts0 + i * 3600_000, "o": o, "h": c * 1.002,
                 "l": o * 0.998, "c": c, "v": 1000.0 + i})
    px = c
as_of = bars[-1]["ts"]
fw = "RTM.PO3.v1"
confs = [{"cid": c.cid, "t_confirm_ms": as_of - (5 - i) * 60000,
          "p_confirm": 100.0 + i}
         for i, c in enumerate(expected_components(fw))]
res = run_engine(bars, events=confs, framework_id=fw, as_of_ms=as_of)
print("is_range =", res["range"]["is_range"])
print("bundle emitted =", res["bundle"] is not None,
      "| class =", res["bundle"].resolution_class if res["bundle"] else None)
print("events =", res["events"])
assert res["range"]["is_range"] is False
assert res["bundle"] is not None and "EV_RTM_004" in res["events"]
print("Q-002 CONFIRMED: bundle + EV_RTM_004 emitted with is_range=False; "
      "range gate is informational only")
