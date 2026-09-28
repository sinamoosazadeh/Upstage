"""V6 probe A-005: huge float literal -> Infinity through the real parser and
the public _load_yaml path; check whether the loader layer rejects it and what
real consumers (risk kernel size()) would do with inf.
"""
import math
import sys
import tempfile
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import apex.config as C
from apex.config import _YamlSubsetParser, _parse_scalar

print("== 1) scalar overflow ==")
v = _parse_scalar("1e9999")
print("1e9999 ->", repr(v), "isinf:", math.isinf(v) if isinstance(v, float) else "n/a")
v2 = _parse_scalar("-1e9999")
print("-1e9999 ->", repr(v2))
print("nan spelling:", repr(_parse_scalar("nan")), repr(_parse_scalar("NaN")))

print("== 2) full document + public loader ==")
print(_YamlSubsetParser("x: 1e9999\n").parse())
with tempfile.TemporaryDirectory() as td:
    tmp = pathlib.Path(td)
    (tmp / "risk_defaults_v1.yaml").write_text("budget_per_trade: 1e9999\nk_attn: 0.25\n")
    orig = C.PARAMS_DIR
    C.PARAMS_DIR = tmp
    try:
        data = C._load_yaml("risk_defaults")
        print("public _load_yaml ->", data, "| no rejection at loader layer")
        # 3) what does the REAL risk kernel do with an inf budget?
        #    (feed it via Params cache, in-process only)
        p = C.Params()
        p._cache["risk_defaults"] = data
        from apex.risk import kernel as RK
        import inspect
        sig = inspect.signature(RK.RiskKernel.size) if hasattr(RK, "RiskKernel") else None
        print("RiskKernel.size signature:", sig)
        try:
            k = RK.RiskKernel(p)
            out = k.size(capital=10000.0, atr=100.0, stop_distance=100.0,
                         confidence=0.9, symbol="BTCUSDT", timeframe="1h")
            print("size() with inf budget ->", out)
        except Exception as e:
            print("size() with inf budget raised:", type(e).__name__, str(e)[:200])
    finally:
        C.PARAMS_DIR = orig
