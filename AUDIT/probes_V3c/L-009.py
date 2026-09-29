"""V3c L-009 probe: calc_numerical_contract promises QUARANTINED_NAN_INF for
NaN/Inf but guards AFTER arithmetic.

REAL code: apex.quality.numerical.calc_numerical_contract. Each Decimal
input (C,O,H,L,V,ATR_n,tick,step) is set to NaN / +Inf in turn.
"""
from decimal import Decimal

from apex.quality.numerical import calc_numerical_contract

BASE = dict(C=Decimal(105), O=Decimal(100), H=Decimal(110), L=Decimal(98),
            V=Decimal(10), ATR_n=Decimal(12), tick_size=Decimal("0.01"),
            quantity_step=Decimal("0.001"))


def attempt(label, **kw):
    args = dict(BASE)
    args.update(kw)
    try:
        out, state, cls = calc_numerical_contract(**args)
        print(f"{label:22s} -> state={state} class={cls}")
    except Exception as exc:  # noqa: BLE001 - probe reports, not hides
        print(f"{label:22s} -> RAISED {type(exc).__name__}: {exc}")


def main():
    nan = Decimal("NaN")
    inf = Decimal("Infinity")
    attempt("baseline (all finite)")
    for key in ("C", "O", "H", "L", "V", "ATR_n", "tick_size", "quantity_step"):
        attempt(f"{key}=NaN", **{key: nan})
    for key in ("C", "H", "ATR_n"):
        attempt(f"{key}=+Inf", **{key: inf})
    attempt("H<L (finite)", H=Decimal(99), L=Decimal(101))


if __name__ == "__main__":
    main()
