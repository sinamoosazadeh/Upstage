"""V1d probe E-018 — trail activation threshold recomputed from the CURRENT
stop instead of the fixed initial R. READ-ONLY verification of the REAL
apex.playbook.pb_fvg_sweep_rev_a.trailing_state."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from apex.playbook.pb_fvg_sweep_rev_a import trailing_state

# long, entry=100, initial stop=98 => initial R = 2, trail_after_r = 1.5
# first call at 104: progress 4 >= 1.5*2 = 3 -> activated, stop ratchets to 103
first = trailing_state(entry=100.0, current_stop=98.0, direction=1, current=104.0,
                       atr=1.0, volatility_regime="NORMAL", trail_after_r=1.5,
                       trail_atr_mult=1.0)
print("call 1 (current=104, stop=98): activated=%s stop=%s (R used=%s)" %
      (first["activated"], first["stop"], abs(100.0 - 98.0)))

# second call at 104.2 with the CURRENT stop 103: R is recomputed as 3,
# threshold 1.5*3 = 4.5 > 4.2 -> activation LOST although price never fell
second = trailing_state(entry=100.0, current_stop=first["stop"], direction=1,
                        current=104.2, atr=1.0, volatility_regime="NORMAL",
                        trail_after_r=1.5, trail_atr_mult=1.0)
print("call 2 (current=104.2, stop=%s): activated=%s stop=%s (R recomputed=%s, "
      "threshold=%.2f, progress=%.2f)" %
      (first["stop"], second["activated"], second["stop"],
       abs(100.0 - first["stop"]), 1.5 * abs(100.0 - first["stop"]), 4.2))

# what the contract's fixed initial R would give on the same call:
print("with the INITIAL R=2 the threshold is %.2f <= progress 4.2 -> "
      "activation would persist" % (1.5 * 2.0))

# a later price of 105 revives activation — the flag flickers with price
third = trailing_state(entry=100.0, current_stop=first["stop"], direction=1,
                       current=105.0, atr=1.0, volatility_regime="NORMAL",
                       trail_after_r=1.5, trail_atr_mult=1.0)
print("call 3 (current=105, stop=103): activated=%s stop=%s" %
      (third["activated"], third["stop"]))

# short mirror: entry=100, initial stop=103 => R=3; first call 95.2
s1 = trailing_state(entry=100.0, current_stop=103.0, direction=-1, current=95.2,
                    atr=1.0, volatility_regime="NORMAL", trail_after_r=1.5,
                    trail_atr_mult=1.0)
s2 = trailing_state(entry=100.0, current_stop=s1["stop"], direction=-1,
                    current=95.4, atr=1.0, volatility_regime="NORMAL",
                    trail_after_r=1.5, trail_atr_mult=1.0)
print("SHORT call1 (95.2): activated=%s stop=%s | call2 (95.4): activated=%s "
      "stop=%s" % (s1["activated"], s1["stop"], s2["activated"], s2["stop"]))
