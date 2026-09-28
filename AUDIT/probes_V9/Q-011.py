"""Q-011: EV_WYK_002 (SC) is emitted on the SC bar itself; there is no AR
(reaction) requirement before publishing the selling-climax event, and the
state machine advances RANGE_DETECTED -> SC immediately."""
from apex.engines.e08_wyckoff.engine import WyckoffEngineV4

eng = WyckoffEngineV4()
bars = [{"ts": i, "o": 100, "h": 100.6, "l": 99.4, "c": 100, "v": 1000}
        for i in range(14)]
# SC bar: huge volume, wide range, close in lower band, bearish body,
# low is 5-bar extremum
bars.append({"ts": 14, "o": 100.5, "h": 100.6, "l": 96.0, "c": 97.5,
             "v": 5000})
n = len(bars)
recs = eng.run_full(bars,
                    atr_by_idx={i: 1.0 for i in range(n)},
                    vol_ratio_by_idx={i: (3.0 if i == n - 1 else 1.0)
                                      for i in range(n)},
                    evr_by_idx={i: 0.0 for i in range(n)})
codes = [(e["code"], e["ts"]) for e in eng.events]
print("events:", codes)
print("state after SC bar:", eng.state)
sc = [e for e in eng.events if e["code"] == "EV_WYK_002"]
ar = [e for e in eng.events if e["code"] == "EV_WYK_003"]
assert sc and sc[0]["ts"] == 14, "SC emitted on the same bar"
assert not ar, "no AR anywhere, yet SC already published"
print("Q-011 CONFIRMED: EV_WYK_002 published same-bar, no AR confirmation "
      "gate before emission")
