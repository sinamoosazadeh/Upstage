"""V6 probe A-014: validate_change_proposal checks PRESENCE of the five keys,
not their quality. approval/OOS = False, zero-length windows, and formal
string evidence pass as APPROVED; draft_package then DRAFTs the package.
Temp dirs only; the real params/ is never touched.
"""
import sys
import pathlib
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.research import backtest as bt
from apex.research import promotion as pr
from apex.research import governance as gov

print("== 1) formal/garbage proposal values are APPROVED ==")
bad = {
    "reason": "x",                       # single character
    "pit_backtest_180d": 0,              # zero days
    "forward_observation_30d": 0,        # zero days
    "out_of_sample_evaluation": False,   # falsy? -> 0 == False is int 0... check
    "parameter_board_approval": False,   # False is not None/''/{}/[] -> kept
}
v = gov.validate_change_proposal(bad)
print("decision:", v["decision"], "| missing:", v["missing"])

print("== 2) same with 'NA' strings and empty-string windows ==")
bad2 = {
    "reason": "NA",
    "pit_backtest_180d": "NA",
    "forward_observation_30d": "NA",
    "out_of_sample_evaluation": "NA",
    "parameter_board_approval": "NA",
}
v2 = gov.validate_change_proposal(bad2)
print("decision:", v2["decision"], "| missing:", v2["missing"])

print("== 3) windows of 1 day (numeric, < 180 / < 30) ==")
bad3 = dict(bad2, pit_backtest_180d=1, forward_observation_30d=1)
v3 = gov.validate_change_proposal(bad3)
print("decision:", v3["decision"], "| missing:", v3["missing"])

print("== 4) full draft_package flow with the formal proposal ==")

def _trade(r, symbol="BTCUSDT"):
    return bt.Trade(symbol=symbol, timeframe="15m", family_id="SF_FVG_SWEEP_REV",
                    direction=1, entry_index=1, exit_index=2, entry_price=100.0,
                    exit_price=100.0 + r, stop_price=99.0, target_price=103.0,
                    quantity=1.0, r_multiple=r, costs=0.0004,
                    exit_reason="TARGET", atr=1.0)

pool = pr.FamilyPool(family_id="SF_FVG_SWEEP_REV")
symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
           "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT"]
for i in range(35):
    pool.add(_trade(1.5, symbol=symbols[i % 10]))
for i in range(5):
    pool.add(_trade(-1.0, symbol=symbols[i % 10]))

candidate = pr.PromotionCandidate(
    family_id="SF_FVG_SWEEP_REV", pool=pool,
    wfo={"decision": "PROMOTED"},
    pbo={"flagged_high": False},
    deflated_sharpe={"passes": True},
    benchmark={"outperforms": True})
print("promotion gate:", candidate.gates()["decision"])

out = pr.draft_package(
    candidate=candidate,
    values={"alpha_spread": 0.3, "some_unknown_key": 1},
    version="1.0.0", code_revision="a" * 40, feature_version="4.0.0",
    model_version="4.0.0", seed=1, reason="formal",
    proposals={"alpha_spread": bad2, "some_unknown_key": bad2})
print("draft_package decision:", out["decision"])
print("validation:", {k: out["validation"][k] for k in ("decision", "red_line_clean", "violations")})
print()
print("NOTE: no file was written (draft_package returns the package only);")
print("injection is a separate, explicit InjectionLedger.inject step.")
