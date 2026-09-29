"""V3c L-012 probe: Gate13 + adjudicate accept impossible calibration metrics.

REAL code: apex.quality.vector (_clip01/bounded_model_quality),
apex.setup.gates.gate13_parameter_package, apex.risk.kernel.adjudicate,
apex.ops.engine_context.paper_package_binding (boundary: native PAPER
package carries NO metrics). Synthetic package + risk input only.
"""
from apex.ops.engine_context import paper_package_binding
from apex.quality.vector import _clip01, bounded_model_quality
from apex.risk.kernel import adjudicate
from apex.setup.gates import gate13_parameter_package

INF = float("inf")


def bad_package(log_loss, brier=0.0, cal=0.0):
    return {"package_version": 1, "parameter_package_id": "pkg-synthetic-live",
            "rolling_calibration_error": cal, "brier": brier,
            "log_loss": log_loss}


def risk_input(package):
    return {
        "snapshot_id": "0" * 64, "timeframe": "1h", "capital": 10000.0,
        "environment": "PAPER", "package": package,
        "q_raw": 1.0, "qx_state": False, "failed_setup_gate": False,
        "pit_violation": False, "portfolio_exposure": 0.0,
        "proposed_notional": 0.0, "capital_hard_cap": 10000.0,
        "circuit_breaker_engaged": False, "emergency_state": "NORMAL",
        "per_symbol_exposure": 0.0, "symbol_cap": 5000.0,
        "portfolio_cap": 9000.0, "conflict_state": "NONE",
        "staleness_seconds": 0.0, "freshness_sla_seconds": 60.0,
        "oi_lag_seconds": 0.0, "oi_lag_threshold_seconds": 60.0,
        "is_risk_increase": False, "uncertainty_is_rising": False,
        "realized_daily_loss_fraction": 0.0, "realized_weekly_loss_fraction": 0.0,
        "consecutive_losses": 0,
        "time_to_expiry_days": {"applicable": False, "contract_type": "PERPETUAL"},
        "margin_health_fraction": 1.0,
        "stop_distance": 20.0, "min_quantity": 0.1,
        "contract_multiplier": 1.0, "risk_state": "LowRisk",
    }


def main():
    print(f"_clip01(+inf)={_clip01(INF)} _clip01(-100)={_clip01(-100.0)}")
    try:
        _clip01(float("nan"))
        print("_clip01(nan): RETURNED (unexpected)")
    except ValueError as exc:
        print(f"_clip01(nan): ValueError ({exc})")

    for label, pkg in (("log_loss=+inf", bad_package(INF)),
                       ("log_loss=-100", bad_package(-100.0)),
                       ("brier=-100", bad_package(0.69, brier=-100.0))):
        score = bounded_model_quality(float(pkg["rolling_calibration_error"]),
                                      float(pkg["brier"]), float(pkg["log_loss"]))
        g13 = gate13_parameter_package(pkg, environment="LIVE")
        print(f"{label:14s} bounded_score={score:.4f} gate13 passed={g13.passed} "
              f"reason={g13.reason}")
    nan_pkg = bad_package(float("nan"))
    g13n = gate13_parameter_package(nan_pkg, environment="LIVE")
    print(f"log_loss=NaN    gate13 passed={g13n.passed} reason={g13n.reason}")

    for label, pkg in (("log_loss=+inf", bad_package(INF)),
                       ("log_loss=-100", bad_package(-100.0))):
        out = adjudicate(risk_input(pkg))
        print(f"adjudicate [{label}]: decision={out['decision']} "
              f"sized_quantity={out['sized_quantity']} reason={out['reason']}")

    native = paper_package_binding(environment="PAPER")
    print(f"native PAPER package keys: {sorted(native)} "
          f"(calibration={native.get('calibration')})")


if __name__ == "__main__":
    main()
