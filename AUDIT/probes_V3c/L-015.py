"""V3c L-015 probe (MEASURED): despite INCREMENTAL_ONLY=True, B01/B02/B03
and the rolling proxies re-scan full history on every call: per-call wall
time grows with history length (O(n)/call), and a per-bar loop over growing
history shows rising per-bar cost. No state/update API exists.

REAL code: apex.research.proxies (INCREMENTAL_ONLY, NUMBA_USED,
corwin_schultz_spread/abdi_ranaldo_spread/roll_spread/amihud_illiquidity/
kyle_lambda/liquidity_regime_composite/cvd/information_ratio).
Synthetic deterministic series only. Absolute ms are sandbox-specific; the
scaling law is the transferable finding (AA.7 demands O(1) state updates).
"""
import inspect
import math
import time

import apex.research.proxies as px


def series(n, seed=7.0):
    out = []
    for i in range(n):
        base = 100.0 + 5.0 * math.sin(i / 9.0 + seed) + 0.01 * i
        out.append({"high": base * 1.002, "low": base * 0.998,
                    "close": base * (1.0 + 0.0005 * math.sin(i * 1.7))})
    return out


def rets(n):
    return [0.001 * math.sin(i / 5.0) + 0.0002 * math.cos(i / 13.0)
            for i in range(n)]


def vols(n):
    return [1000.0 + 200.0 * math.sin(i / 7.0) for i in range(n)]


def bench(fn, *args, repeats=5, **kw):
    fn(*args, **kw)  # warmup
    ts = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn(*args, **kw)
        ts.append((time.perf_counter() - t0) * 1000.0)
    return min(ts)


def main():
    print(f"INCREMENTAL_ONLY={px.INCREMENTAL_ONLY} NUMBA_USED={px.NUMBA_USED}")
    for name in ("corwin_schultz_spread", "abdi_ranaldo_spread",
                 "roll_spread", "kyle_lambda", "amihud_illiquidity",
                 "liquidity_regime_composite", "cvd", "information_ratio"):
        print(f"{name}{inspect.signature(getattr(px, name))}")
    print("--- per-call ms vs history length (min of 5, sandbox CPU) ---")
    bars5k, r5k, v5k = series(5000), rets(5000), vols(5000)
    hdr = f"{'n':>6} {'B01':>9} {'B02':>9} {'B03':>9} {'B07':>9} {'B08':>9}"
    print(hdr)
    for n in (200, 1000, 5000):
        b, r, v = bars5k[:n], r5k[:n], v5k[:n]
        t_b01 = bench(px.corwin_schultz_spread, b)
        t_b02 = bench(px.abdi_ranaldo_spread, b)
        t_b03 = bench(px.roll_spread, r)
        t_b07 = bench(px.amihud_illiquidity, returns=r, volumes=v)
        t_b08 = bench(px.liquidity_regime_composite, amihud=r, obi=r, kyle=r)
        print(f"{n:>6} {t_b01:>9.3f} {t_b02:>9.3f} {t_b03:>9.3f} "
              f"{t_b07:>9.3f} {t_b08:>9.3f}")
    print("--- per-bar loop, growing history (B01+B02+B03+B07 per new bar) ---")
    bars = series(900)
    first, last = [], []
    for step in range(200, 700):
        window = bars[:step]
        rr = [math.log(window[i]["close"] / window[i - 1]["close"])
              for i in range(1, len(window))]
        t0 = time.perf_counter()
        px.corwin_schultz_spread(window)
        px.abdi_ranaldo_spread(window)
        px.roll_spread(rr)
        px.amihud_illiquidity(returns=rr, volumes=vols(len(rr)))
        dt = (time.perf_counter() - t0) * 1000.0
        (first if step < 210 else last if step >= 690 else []).append(dt)
    f = sum(first) / len(first)
    last_mean = sum(last) / len(last)
    print(f"bars 200-209 mean {f:.3f} ms/bar; bars 690-699 mean "
          f"{last_mean:.3f} ms/bar; ratio {last_mean / f:.2f}x "
          f"(history ratio 3.45x)")


if __name__ == "__main__":
    main()
