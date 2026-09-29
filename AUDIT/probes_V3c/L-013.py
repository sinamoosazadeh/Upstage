"""V3c L-013 probe: temporal_window_validity carries weight 0.0, so it
cannot move context_confidence; Gate8 consumes only the Q-class label.

REAL code: apex.fabric.context (DEFAULT_COMBINER_WEIGHTS/CombinerInputs/
context_confidence), apex.setup.gates.gate8, engine_context.
temporal_validity_projection. Synthetic inputs only.
"""
import inspect

from apex.fabric.context import (DEFAULT_COMBINER_WEIGHTS, CombinerInputs,
                                 context_confidence)
from apex.ops.engine_context import temporal_validity_projection
from apex.setup.gates import gate8_temporal_window_quality


def main():
    print(f"DEFAULT_COMBINER_WEIGHTS = {DEFAULT_COMBINER_WEIGHTS}")
    base = dict(data_trust=0.9, mtf_state="ALIGNED", evidence_agreement=0.8,
                regime_confidence=0.7, regime_uncertainty=0.3,
                divergence_magnitude=0.2)
    res0 = context_confidence(CombinerInputs(**base, temporal_window_validity=0.0),
                              timeframe="1h", q_raw=1.0)
    res1 = context_confidence(CombinerInputs(**base, temporal_window_validity=1.0),
                              timeframe="1h", q_raw=1.0)
    print(f"validity=0 -> confidence={res0['context_confidence']!r} z={res0['z']!r}")
    print(f"validity=1 -> confidence={res1['context_confidence']!r} z={res1['z']!r}")
    print(f"identical: {res0['context_confidence'] == res1['context_confidence']}")
    g8 = gate8_temporal_window_quality("Q2")
    print(f"gate8('Q2'): passed={g8.passed} reason={g8.reason}")
    print(f"temporal_validity_projection('DEGRADED') = "
          f"{temporal_validity_projection('DEGRADED')}")
    print(f"gate8 signature: {inspect.signature(gate8_temporal_window_quality)} "
          f"(no validity parameter)")


if __name__ == "__main__":
    main()
