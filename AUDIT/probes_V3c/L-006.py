"""V3c L-006 probe: NaN window quality stays VALID/Q1; non-finite gate
measured values pass score gates; native-producer and payload guards (boundary).

REAL code: apex.quality.vector.calc_window_quality, apex.setup.gates
(gate2/run_all), apex.ops.engine_context.window_quality_projection,
apex.identity.canonical_json. Synthetic inputs only.
"""
import math

from apex.identity.canonical_json import CanonicalJsonError, canonical_json
from apex.identity.hashes import sha256_hex
from apex.ops.engine_context import window_quality_projection
from apex.ops.plan_bridge import BridgeError
from apex.quality.vector import calc_window_quality
from apex.setup.gates import gate2_window_quality, run_all


def main():
    nan = float("nan")
    inf = float("inf")

    # Part 1 (§7): NaN inside the window.
    print("calc_window_quality([(0.9,0),(nan,1)]):",
          calc_window_quality([(0.9, 0.0), (nan, 1.0)]))
    g2 = gate2_window_quality([(0.9, 0.0), (nan, 1.0)], timeframe="1h")
    print(f"gate2 same input: passed={g2.passed} measured={g2.measured} "
          f"reason={g2.reason}")

    # Part 2 (§15): run_all with non-finite measured values, finite payload.
    payload = {"cell": "BTCUSDT:1h", "score": 0.9}
    snap = sha256_hex(canonical_json(payload))
    ctx = {"final_score": inf, "window_qualities": [(0.9, 0.0)],
           "conflict_penalty": -inf, "redundancy_penalty": -inf,
           "mtf_state": "ALIGNED", "has_coarser_bars": True, "h_norm": -inf,
           "temporal_quality": "Q2", "volatility_quality": "Q2",
           "forecast": {"quality": "Q2"}, "snapshot_id": snap,
           "payload": payload, "lineage": ["obs-test1", "0" * 64],
           "q_forecast": inf,
           "package": {"package_version": 1, "parameter_package_id": "pkg",
                       "calibration": "BOOTSTRAP_UNCALIBRATED"},
           "environment": "PAPER", "timeframe": "1h"}
    res = run_all(ctx)
    print(f"run_all all_pass={res['all_pass']} action={res['action']} "
          f"blocked_by={res['blocked_by']}")
    for n in (1, 2, 3, 4, 7, 11, 12):
        r = res["results"][n]
        print(f"  gate{n:2d} {r['name']:28s} passed={r['passed']} "
              f"measured={r['measured']} reason={r['reason']}")

    # Boundary A: native producer path refuses non-finite BEFORE calc_window_quality.
    try:
        window_quality_projection([(0.9, 0.0), (nan, 1.0)])
        print("window_quality_projection(NaN): RETURNED (unexpected)")
    except BridgeError as exc:
        print(f"window_quality_projection(NaN): BridgeError {exc.reason}: {exc.detail}")
    try:
        window_quality_projection([(0.9, 0.0), (inf, 1.0)])
        print("window_quality_projection(+inf): RETURNED (unexpected)")
    except BridgeError as exc:
        print(f"window_quality_projection(+inf): BridgeError {exc.reason}")

    # Boundary B: the payload guard (gate11) rejects non-finite payloads.
    try:
        canonical_json({"x": inf})
        print("canonical_json(+inf): RETURNED (unexpected)")
    except CanonicalJsonError as exc:
        print(f"canonical_json(+inf): CanonicalJsonError ({exc})")


if __name__ == "__main__":
    main()
