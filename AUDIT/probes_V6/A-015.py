"""V6 probe A-015: validate_package RED LINE checks TOP-LEVEL names only.
A veto nested one level down (values={'risk': {'VETO_FRESHNESS_SLA': 0}}) is
VALIDATED with red_line_clean=True; unknown keys are accepted; proposals=None
drops the proposal requirement entirely.
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.research import governance as gov

formal = {
    "reason": "NA", "pit_backtest_180d": "NA", "forward_observation_30d": "NA",
    "out_of_sample_evaluation": "NA", "parameter_board_approval": "NA",
}

def pkg(values):
    return gov.ParameterPackage(
        package_id="pkg-probe", version="1.0.0", values=values,
        code_revision="a" * 40, feature_version="4.0.0", model_version="4.0.0",
        seed=1, reason="probe")

print("== 1) top-level veto (control: must be REJECTED) ==")
v = gov.validate_package(pkg({"VETO_FRESHNESS_SLA": 0}),
                         proposals={"VETO_FRESHNESS_SLA": formal})
print(v["decision"], "red_line_clean=", v["red_line_clean"], v["violations"][0]["kind"])

print("== 2) the SAME veto nested under 'risk' ==")
v2 = gov.validate_package(pkg({"risk": {"VETO_FRESHNESS_SLA": 0}}),
                          proposals={"risk": formal})
print(v2["decision"], "red_line_clean=", v2["red_line_clean"], "violations=", v2["violations"])

print("== 3) nested alias spellings of forbidden rows ==")
v3 = gov.validate_package(pkg({"m": {"margin_warning": 0.1, "capital_hard_cap": 0.99,
                                     "system_leverage_cap_by_tf": {"1m": 50},
                                     "daily_loss_limit": 0.9}}),
                          proposals={"m": formal})
print(v3["decision"], "red_line_clean=", v3["red_line_clean"], "violations=", v3["violations"])

print("== 4) unknown top-level key accepted ==")
v4 = gov.validate_package(pkg({"totally_unknown_key": 42}),
                          proposals={"totally_unknown_key": formal})
print(v4["decision"], "violations=", v4["violations"])

print("== 5) proposals=None drops the proposal requirement ==")
v5 = gov.validate_package(pkg({"alpha_spread": 0.3}))          # no proposals arg
print("alpha_spread w/o proposals:", v5["decision"], "violations=", v5["violations"])
v6 = gov.validate_package(pkg({"alpha_spread": 0.3}), proposals=None)
print("alpha_spread proposals=None:", v6["decision"], "violations=", v6["violations"])

print("== 6) out-of-bounds value IS checked for known governed rows (control) ==")
v7 = gov.validate_package(pkg({"alpha_spread": 99.0}), proposals={"alpha_spread": formal})
print(v7["decision"], [x["kind"] for x in v7["violations"]])
