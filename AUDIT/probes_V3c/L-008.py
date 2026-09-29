"""V3c L-008 probe: formula_volume_ratio SMA=0 branch vs §2.2 epsilon formula.

REAL code: apex.quality.numerical.formula_volume_ratio. Contract formula
evaluated inline for comparison: V/max(SMA_prev, eps_volume).
"""
from decimal import Decimal

from apex.quality.numerical import EPS_TIER1, formula_volume_ratio


def main():
    print("formula_volume_ratio(20, 0) =", formula_volume_ratio(Decimal(20), Decimal(0)))
    print("formula_volume_ratio(20, 10) =", formula_volume_ratio(Decimal(20), Decimal(10)))
    contract_value = Decimal(20) / max(Decimal(0), EPS_TIER1)
    print(f"§2.2 V/max(SMA,eps) with eps={EPS_TIER1}: {contract_value}")
    print(f"helper docstring promises: 'SMA=0 -> large-but-finite via the "
          f"epsilon floor (never NaN)'")


if __name__ == "__main__":
    main()
