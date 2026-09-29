"""V3c L-014 probe: liquidity_regime_composite standardizes each series'
MEAN against itself, so every component (and the composite) is always 0.

REAL code: apex.research.proxies.liquidity_regime_composite. Three
regime-distinct synthetic windows.
"""
from apex.research.proxies import liquidity_regime_composite


def main():
    windows = {
        "calm   ": ([0.01] * 20, [0.1] * 20, [0.05] * 20),
        "trending": ([0.01 * i for i in range(1, 21)],
                     [0.02 * i for i in range(1, 21)],
                     [0.03 * i for i in range(1, 21)]),
        "volatile": ([0.5 if i % 2 else 0.01 for i in range(20)],
                     [0.9 if i % 3 == 0 else -0.4 for i in range(20)],
                     [1.5 if i % 2 else 0.02 for i in range(20)]),
    }
    for name, (amihud, obi, kyle) in windows.items():
        try:
            out = liquidity_regime_composite(amihud=amihud, obi=obi, kyle=kyle)
            print(f"{name} composite={out['liquidity_regime_composite']!r} "
                  f"components={out['components']}")
        except Exception as exc:  # noqa: BLE001
            print(f"{name} RAISED {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
