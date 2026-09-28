"""V6 probe J-007: W.2 signal objective demands >=100 trades per test window,
while Z.1 assumes <100 trades per cell over the ENTIRE history and Z.4
promotes pooled families at >=30. A synthetic 42-trade pool (27 wins) is
eligible under family_pool_gate but infeasible under signal_objective.
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.research import backtest as bt
from apex.research import promotion as pr
from apex.research.optimizer import signal_objective, SIGNAL_MIN_TRADES_PER_WINDOW

print("SIGNAL_MIN_TRADES_PER_WINDOW =", SIGNAL_MIN_TRADES_PER_WINDOW)

def _trade(r, symbol):
    return bt.Trade(symbol=symbol, timeframe="15m", family_id="SF_FVG_SWEEP_REV",
                    direction=1, entry_index=1, exit_index=2, entry_price=100.0,
                    exit_price=100.0 + r, stop_price=99.0, target_price=103.0,
                    quantity=1.0, r_multiple=r, costs=0.0004,
                    exit_reason="TARGET", atr=1.0)

symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
           "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT"]
pool = pr.FamilyPool(family_id="SF_FVG_SWEEP_REV")
for i in range(27):
    pool.add(_trade(1.5, symbols[i % 10]))
for i in range(15):
    pool.add(_trade(-1.0, symbols[i % 10]))

gate = pr.family_pool_gate(pool)
print("family_pool_gate(42 trades, 27 wins) -> eligible:", gate["eligible"],
      "| reason:", gate["reason"], "| wilson_lower:", round(gate["wilson_lower"], 4))

obj = signal_objective(deflated_sharpe=1.2, trades=42, net_return=0.30,
                       btc_buy_and_hold=0.10, calibration_error=0.01,
                       staleness_threshold=0.05)
print("signal_objective(trades=42) -> feasible:", obj["feasible"],
      "| value:", obj["value"], "| constraints:", obj["constraints"])

# per-cell view: a cell with the whole history < 100 cannot have any
# test window with >= 100 (a window is a subset of history)
cell_total = 42
print("cell full history = 42 < 100 => every test window <= 42 < 100:",
      cell_total < 100)

# and the Z.4 floor:
print("Z.4 family floor =", pr.FAMILY_POOL_MIN_TRADES)
