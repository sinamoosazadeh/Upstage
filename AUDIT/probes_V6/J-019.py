"""V6 probe J-019: margin-health band semantics — Ch.15/D29 (warning 0.60,
action 0.40, liquidation 0.20) vs Y.2 ('60% comfortable, 40% warning,
20% critical'). The runtime has TWO boundary modes: PAPER strict-below (D29)
and default/LIVE inclusive. The CP-6 integration test flips veto14 at exactly
0.40 WITHOUT environment/margin_model keys -> it exercises the inclusive
(default/LIVE) branch, not the PAPER D29 branch.
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.risk.kernel import margin_health_state, adjudicate

for v in (0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1):
    p = margin_health_state(v, environment="PAPER")
    d = margin_health_state(v, environment="LIVE")
    print("fraction %.2f | PAPER(D29 strict-below): %-20s veto=%s | "
          "default/LIVE(inclusive): %-20s veto=%s"
          % (v, p["level"], p["veto"], d["level"], d["veto"]))

print()
print("== the CP-6 test input (margin_health_fraction=0.40, no environment/margin_model) ==")
base = {
    "snapshot_id": "s", "timeframe": "1h", "capital": 10_000.0, "q_raw": 0.9,
    "qx_state": False, "failed_setup_gate": False, "pit_violation": False,
    "availability_time": 1, "portfolio_exposure": 100.0,
    "proposed_notional": 50.0, "capital_hard_cap": 1_000_000.0,
    "circuit_breaker_engaged": False, "emergency_state": "NORMAL",
    "per_symbol_exposure": 100.0, "symbol_cap": 1_000.0,
    "portfolio_cap": 1_000_000.0, "conflict_state": "CONSENSUS",
    "staleness_seconds": 1.0, "freshness_sla_seconds": 30.0,
    "oi_lag_seconds": 5.0, "oi_lag_threshold_seconds": 60.0,
    "is_risk_increase": False, "uncertainty_is_rising": False,
    "realized_daily_loss_fraction": 0.0, "realized_weekly_loss_fraction": 0.0,
    "consecutive_losses": 0, "time_to_expiry_days": 40.0,
    "margin_health_fraction": 0.40, "stop_distance": 100.0,
    "min_quantity": 0.001, "risk_state": "LowRisk",
}
out_default = adjudicate(dict(base))
out_paper = adjudicate(dict(base, environment="PAPER",
                            margin_model="PAPER_RESERVATION_PROXY_D29"))
print("adjudicate(0.40) default (CP-6 test shape):", out_default["decision"],
      "| vetoes:", out_default["vetoes_applied"])
print("adjudicate(0.40) with PAPER/D29 identity:  ", out_paper["decision"],
      "| vetoes:", out_paper["vetoes_applied"])
print()
print("=> the CP-6 test asserts REJECT at 0.40, which only the DEFAULT/"
      "LIVE inclusive branch produces; D29 PAPER at exactly 0.40 does NOT",
      "fire veto 14 (strictly below).")
