"""V3c L-010 probe: confluence clusters by neighbor gaps, ignores source
independence and total diameter.

REAL code: apex.pattern.fibonacci.confluence. tol = 0.15 * ATR.
"""
from apex.pattern.fibonacci import confluence


def main():
    print("tol for ATR=1.0 is 0.15")
    out = confluence({"only_source": [100.0, 100.1, 100.2]}, atr=1.0)
    print(f"single source [100,100.1,100.2] -> {len(out)} cluster(s)")
    for c in out:
        print(f"  count={c['count']} spread={c['spread']} centre={c['centre']} "
              f"sources={[m['source'] for m in c['members']]}")
    chain = [100.0 + 0.1 * i for i in range(6)]
    out2 = confluence({"a": chain}, atr=1.0)
    print(f"single-source chain {chain} -> {len(out2)} cluster(s)")
    for c in out2:
        print(f"  count={c['count']} spread={c['spread']}")
    two = confluence({"a": [100.0], "b": [100.1]}, atr=1.0)
    print(f"two sources [100],[100.1] -> {len(two)} cluster(s), "
          f"spread={two[0]['spread'] if two else None}")


if __name__ == "__main__":
    main()
