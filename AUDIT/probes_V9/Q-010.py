"""Q-010: detect_sos requires BOS confirmed_at_idx <= current_idx-1, but the
native producer (engine_context.complete_engine_bundle) builds
bos_by_idx = {i: {"confirmed_at_idx": i, ...}} (same bar), so SOS/EV_WYK_006
can never fire in production; direction of the BOS is also never checked."""
import subprocess
from apex.engines.e08_wyckoff.engine import WyckoffEngineV4, detect_sos

def mk(n):
    return WyckoffEngineV4()

def stream(bos_by_idx):
    eng = WyckoffEngineV4()
    bars = [{"ts": i, "o": 100, "h": 100.6, "l": 99.4, "c": 100, "v": 1000}
            for i in range(14)]
    # breakout bar: close 102 > hi(100.6) + 0.2*1.0, strong volume, high close
    bars.append({"ts": 14, "o": 100.4, "h": 102.3, "l": 100.3, "c": 102.2,
                 "v": 3000})
    n = len(bars)
    recs = eng.run_full(
        bars, atr_by_idx={i: 1.0 for i in range(n)},
        vol_ratio_by_idx={i: (1.5 if i == n - 1 else 1.0) for i in range(n)},
        evr_by_idx={i: 0.0 for i in range(n)}, bos_by_idx=bos_by_idx)
    return eng, [e["code"] for e in eng.events]

# producer shape: confirmed_at_idx == same bar index (bar_idx is 1-based)
eng1, ev1 = stream({14: {"confirmed_at_idx": 14, "direction": "UP"}})
print("producer-shaped bos (confirmed_at_idx == current):", ev1,
      "-> SOS fired:", "EV_WYK_006" in ev1)
# PIT-correct shape: confirmed at t-1 (engine bar_idx == list index)
eng2, ev2 = stream({14: {"confirmed_at_idx": 13, "direction": "UP"}})
print("t-1 confirmed bos:", ev2, "-> SOS fired:", "EV_WYK_006" in ev2)
assert "EV_WYK_006" not in ev1 and "EV_WYK_006" in ev2

# direction never checked: a DOWN (bearish) BOS also validates bullish SOS
bar = {"o": 100.4, "h": 102.3, "l": 100.3, "c": 102.2}
print("detect_sos with bearish BOS idx ok:",
      detect_sos(bar, 100.6, 1.0, 1.5, 13, 14))
# show the producer really builds the same-bar mapping:
out = subprocess.run(["grep", "-n", "confirmed_at_idx",
                      "apex/ops/engine_context.py"],
                     capture_output=True, text=True).stdout
print("engine_context.py confirmed_at_idx sites:\n", out)
assert "\"confirmed_at_idx\": i" in out or "'confirmed_at_idx': i" in out
print("Q-010 CONFIRMED: native bos_by_idx is same-bar -> SOS structurally "
      "unreachable in production; BOS direction unchecked")
