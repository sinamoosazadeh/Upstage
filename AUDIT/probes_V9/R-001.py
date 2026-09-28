"""R-001: Method-B pivot divergence pairs the last two PRICE pivots with
the last two MOMENTUM pivots independently per side — there is no
index/time pairing constraint, so a price pivot from bar ~i1 is compared
with a momentum pivot from a completely different bar i2."""
import math
from apex.engines.e10_momentum.engine import (MomentumEngine, get_params,
                                              candle_from_bar)

eng = MomentumEngine(get_params())
px = 100.0
last = None
for i in range(130):
    r = 0.004 * math.exp(-i / 60.0) + 0.0025 * math.sin(i / 2.5)
    px *= (1 + r)
    bar = {"ts": i * 3600_000, "o": px / (1 + r), "h": px * 1.001,
           "l": px / (1 + r) * 0.999, "c": px, "v": 1000.0 + 10 * i}
    st = eng.update(candle_from_bar(bar))
    if "events" in st:
        last = st
div = last["events"]["divergence"]
print("kind=%s method=%s" % (div["kind"], div["method"]))
print("price pivot count:", len(eng.price_high_pivots),
      "| momentum pivot count:", len(eng.mom_high_pivots))
proof = div["pit_proof"]
print("pit_proof p_idx=%s m_idx=%s (28 mom pivots vs 6 price pivots: "
      "any coincidence of indices is luck, not a checked invariant)"
      % (proof.get("p_idx"), proof.get("m_idx")))

# Unit-level proof with the REAL Pivot dataclass and the REAL detector:
# price pivots from bars 10/40, momentum pivots from bars 90/118 —
# the engine still pairs them and reports a divergence.
from apex.engines.e10_momentum.engine import Pivot
eng.price_high_pivots = [
    Pivot(index=10, time=10 * 3600_000, price=100.0, value=100.0,
          type="HIGH", indicator="PRICE", confirmed_at=15),
    Pivot(index=40, time=40 * 3600_000, price=105.0, value=105.0,
          type="HIGH", indicator="PRICE", confirmed_at=45)]
eng.mom_high_pivots = [
    Pivot(index=90, time=90 * 3600_000, price=1.0, value=80.0,
          type="HIGH", indicator="RSI", confirmed_at=95),
    Pivot(index=118, time=118 * 3600_000, price=1.0, value=60.0,
          type="HIGH", indicator="RSI", confirmed_at=123)]
ev = eng._detect_divergence_pivot()
print("cross-epoch pairing accepted:", ev.kind, "method:", ev.method,
      "p_idx:", ev.pit_proof["p_idx"], "m_idx:", ev.pit_proof["m_idx"])
assert ev is not None and ev.pit_proof["p_idx"] != ev.pit_proof["m_idx"]
# and the detector source contains no index/time pairing constraint:
src = open("apex/engines/e10_momentum/engine.py").read()
seg = src[src.index("def _detect_divergence_pivot"):
          src.index("def update")]
print("pairing-constraint tokens in _detect_divergence_pivot:",
      [t for t in ("p1.index", "m1.index", "abs(") if t in seg])
assert "abs(" not in seg
print("R-001 CONFIRMED: last-two-per-side pairing with unrelated bar "
      "indices; no temporal pairing constraint exists")
