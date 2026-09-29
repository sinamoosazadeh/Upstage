"""V3c L-007 probe: redundancy_rho drops NaNs per-series, then zips tails.

REAL code: apex.fabric.context.redundancy_rho (default n=48, min_points=20).
50 truly anti-correlated points (a=t%2, b=1-t%2), NaN in a at t=2, NaN in b
at t=49 (two different times). Time-aligned reference computed inline.
Boundary: stored producer s_i cannot carry NaN (canonical_json rejects it).
"""
import math

from apex.fabric.context import redundancy_rho
from apex.identity.canonical_json import CanonicalJsonError, canonical_json


def main():
    nan = float("nan")
    a = [float(t % 2) for t in range(50)]
    b = [float(1 - t % 2) for t in range(50)]
    a[2] = nan   # inside the n=48 window (t=2..49)
    b[49] = nan  # inside the n=48 window, different time

    got = redundancy_rho(a, b)
    print(f"redundancy_rho -> rho={got['rho']} points={got['points']} "
          f"skipped={got['skipped']} reason={got['reason']}")

    # Time-aligned reference: pairwise-complete over common valid times.
    pairs = [(x, y) for x, y in zip(a, b) if x == x and y == y]
    n = len(pairs)
    ma = sum(x for x, _ in pairs) / n
    mb = sum(y for _, y in pairs) / n
    cov = sum((x - ma) * (y - mb) for x, y in pairs) / n
    va = sum((x - ma) ** 2 for x, _ in pairs) / n
    vb = sum((y - mb) ** 2 for _, y in pairs) / n
    ref = cov / math.sqrt(va * vb)
    print(f"time-aligned reference -> rho={ref} pairs={n}")

    # Control: no NaNs at all.
    ac = [float(t % 2) for t in range(50)]
    bc = [float(1 - t % 2) for t in range(50)]
    ctl = redundancy_rho(ac, bc)
    print(f"control (complete series) -> rho={ctl['rho']} points={ctl['points']}")

    # Boundary: producer history rows pass through canonical_json on write.
    try:
        canonical_json({"s_i": {"structure": nan}})
        print("canonical_json(NaN s_i): RETURNED (unexpected)")
    except CanonicalJsonError as exc:
        print(f"canonical_json(NaN s_i): CanonicalJsonError ({exc})")


if __name__ == "__main__":
    main()
