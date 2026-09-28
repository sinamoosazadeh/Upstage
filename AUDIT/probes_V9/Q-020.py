"""Q-020: ADX warmup (t < 2n) sets degraded_reason=ADX_WARMUP_QX but
scale_state() never receives it: the scale can still be VALID and the
evidence validity is VALID / fate ACTIVE — the warmup flag is cosmetic."""
from apex.engines.e09_trend.engine import (TrendEngine, E09TrendEngine,
                                           compute_adx_wilder)

bars = []
px = 100.0
for i in range(24):                        # < 2n = 28 -> warmup_2n True
    px *= 1.01
    bars.append({"ts": i * 3600_000, "o": px / 1.01, "h": px * 1.001,
                 "l": px / 1.01 * 0.999, "c": px, "v": 1000.0})
adx_res = compute_adx_wilder(bars, 14)
print("warmup=%s warmup_2n=%s adx=%.2f" % (
    adx_res["warmup"], adx_res["warmup_2n"], adx_res["adx"]))
assert adx_res["warmup_2n"]

swings = [{"type": "HH", "price": 100 + i, "idx": 3 + 5 * i,
           "confirmed_at_idx": 4 + 5 * i} for i in range(4)]
eng = TrendEngine()
out = eng.process_bar(bars, swings=swings, atr=1.0, tf_seconds=3600)
for s in ("MICRO", "SHORT"):
    d = out["scales"][s]
    print("%s: state=%s degraded_reason=%s adx=%.2f evidence_count=%d" % (
        s, d["state"], d["degraded_reason"], d["adx"], d["evidence_count"]))
sh = out["scales"]["SHORT"]
assert sh["degraded_reason"] == "ADX_WARMUP_QX" and sh["state"] == "VALID"
ev = E09TrendEngine()._to_evidence("SHORT", sh, "BTCUSDT", "1h", 0.9, out)
print("evidence: condition_state=%s validity=%s fate=%s" % (
    ev.condition_state, ev.validity, ev.fate_state))
assert ev.validity == "VALID"
print("Q-020 CONFIRMED: ADX_WARMUP_QX co-exists with state=VALID and "
      "validity=VALID evidence; warmup never gates the state")
