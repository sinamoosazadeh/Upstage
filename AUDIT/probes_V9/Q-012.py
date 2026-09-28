"""Q-012: detect_spring only enforces BarCount_since_ST <= 20 when
bars_since_st is not None; with no ST ever recorded the check is skipped
entirely and the state machine jumps RANGE_DETECTED -> SPRING (skipping
SC/AR/ST), emitting EV_WYK_005."""
from apex.engines.e08_wyckoff.engine import WyckoffEngineV4, detect_spring

print("detect_spring with bars_since_st=None:",
      detect_spring(low=99.2, range_lo=99.4, close=99.8, atr=1.0,
                    vol_ratio=1.5, evr_value=0.0, bars_since_st=None))
print("detect_spring with bars_since_st=999:",
      detect_spring(low=99.2, range_lo=99.4, close=99.8, atr=1.0,
                    vol_ratio=1.5, evr_value=0.0, bars_since_st=999))

eng = WyckoffEngineV4()
bars = [{"ts": i, "o": 100, "h": 100.6, "l": 99.4, "c": 100, "v": 1000}
        for i in range(14)]
# spring bar: penetrates lo by 0.2 (<= 0.3*ATR), closes back above lo
bars.append({"ts": 14, "o": 99.6, "h": 100.0, "l": 99.2, "c": 99.8,
             "v": 2000})
n = len(bars)
eng.run_full(bars, atr_by_idx={i: 1.0 for i in range(n)},
             vol_ratio_by_idx={i: (1.5 if i == n - 1 else 1.0)
                               for i in range(n)},
             evr_by_idx={i: 0.0 for i in range(n)})
codes = [e["code"] for e in eng.events]
print("events:", codes, "| final state:", eng.state)
assert "EV_WYK_005" in codes and "EV_WYK_004" not in codes
assert eng.state == "SPRING"
print("Q-012 CONFIRMED: SPRING reached from RANGE_DETECTED with no ST; "
      "since-ST cap skipped when no ST exists")
