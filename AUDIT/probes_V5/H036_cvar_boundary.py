"""H-036: compare signed research CVaR output with risk-kernel input contract."""
import json
from apex.research.backtest import cvar_bootstrap
from apex.risk.kernel import size

returns = [0.01, -0.02, 0.03, -0.01, 0.02]
research = cvar_bootstrap(returns, paths=300, seed=7, level=0.95)
common = dict(capital=10000.0, stop_distance=20.0, min_quantity=0.001,
              risk_state="MediumRisk")
negative_input = size(**common, cvar_fraction=-0.05)
positive_input = size(**common, cvar_fraction=0.05)
missing_input = size(**common)
print(json.dumps({
    "research_cvar": research,
    "risk_kernel_risk_state_negative_input": negative_input["risk_state"],
    "risk_kernel_risk_state_positive_input": positive_input["risk_state"],
    "risk_kernel_risk_state_missing_input": missing_input["risk_state"],
}, sort_keys=True, indent=2))
