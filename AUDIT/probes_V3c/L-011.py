"""V3c L-011 probe: non-finite inputs across the Fibonacci API.

REAL code: apex.pattern.fibonacci (level/extensions/retracements/ladder/
confluence/harmonic_prz). NaN is refused in most places; +-inf mostly is not.
"""
from apex.pattern.fibonacci import (confluence, extensions, harmonic_prz,
                                    ladder, level, retracements)


def attempt(label, fn, *args, **kwargs):
    try:
        print(f"{label:42s} -> {fn(*args, **kwargs)}")
    except Exception as exc:  # noqa: BLE001 - probe reports, not hides
        print(f"{label:42s} -> RAISED {type(exc).__name__}: {exc}")


def main():
    inf = float("inf")
    attempt("level(100,200,inf)", level, 100.0, 200.0, inf)
    attempt("level(100,200,nan)", level, 100.0, 200.0, float("nan"))
    attempt("extensions(100,200,ratios=(inf,))", extensions, 100.0, 200.0,
            ratios=(inf,))
    attempt("retracements(100,200,ratios=(inf,))", retracements, 100.0, 200.0,
            ratios=(inf,))
    attempt("ladder(100,200) finite control", ladder, 100.0, 200.0)
    attempt("confluence inf level", confluence, {"a": [inf, 100.0]}, atr=1.0)
    attempt("confluence two inf levels", confluence, {"a": [inf], "b": [inf]},
            atr=1.0)
    attempt("confluence atr=inf", confluence, {"a": [100.0], "b": [500.0]},
            atr=inf)
    attempt("confluence NaN level (control)", confluence, {"a": [float("nan")]},
            atr=1.0)
    attempt("harmonic_prz BAT inf legs", harmonic_prz, inf, 200.0, 150.0,
            pattern="BAT")


if __name__ == "__main__":
    main()
