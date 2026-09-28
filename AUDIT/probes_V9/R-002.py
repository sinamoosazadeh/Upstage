"""R-002: the auxiliary reference series is appended BEFORE _build_state,
so 'volume' mode reads vz_hist[-1] = the z-score of the PREVIOUS bar
(1-bar lag) and 'participation' mode reads last_mv_z (previous bar), while
'RSI' mode reads the CURRENT bar's RSI — asymmetric time alignment."""
from apex.engines.e10_momentum.engine import (MomentumEngine, get_params,
                                              candle_from_bar)

def run(mode, n=80):
    eng = MomentumEngine(get_params({"reference_mode": mode}))
    px = 100.0
    for i in range(n):
        px *= 1.0 + (0.003 if i % 2 else -0.001)
        bar = {"ts": i * 3600_000, "o": px, "h": px * 1.002,
               "l": px * 0.998, "c": px,
               "v": 1000.0 * (1 + (i % 7))}       # varying volume
        st = eng.update(candle_from_bar(bar))
    return eng, st

eng_v, st_v = run("volume")
# vz_hist gets appended inside _build_state (AFTER aux_by_bar.append),
# so aux_by_bar[t] must equal vz_hist as it stood at t-1:
vz = list(eng_v.vz_hist)
aux = [a for a in eng_v.aux_by_bar if a is not None]
print("volume mode: aux tail =", [round(x, 4) for x in aux[-4:]])
print("             vz  tail =", [round(x, 4) for x in vz[-4:]])
lag1 = all(abs(aux[-i] - vz[-i - 1]) < 1e-12 for i in range(1, 4))
sync = all(abs(aux[-i] - vz[-i]) < 1e-12 for i in range(1, 4))
print("aux == vz shifted by 1 bar:", lag1, "| aux == vz same bar:", sync)
assert lag1 and not sync

eng_r, st_r = run("RSI")
rsi = list(eng_r.rsi_hist)
aux_r = [a for a in eng_r.aux_by_bar if a is not None]
cur = all(abs(aux_r[-i] - rsi[-i]) < 1e-12 for i in range(1, 4))
print("RSI mode: aux == current-bar rsi:", cur)
assert cur
print("R-002 CONFIRMED: volume/participation aux modes lag one bar; RSI "
      "mode is current-bar — inconsistent alignment across modes")
