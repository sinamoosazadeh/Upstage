"""V6 probe J-009: Session-A F3 (PAPER simulator) fills entries at the last
CLOSED bar's close; the frozen BacktestEngine fills at the NEXT bar's open.
Same inputs -> different entry prices. The simulator itself is CP-15 (D58).
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.research.backtest import BacktestEngine, SignalProposal, FEE_FRACTION

print("FEE_FRACTION =", FEE_FRACTION)

bars = [
    {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 10.0},
    {"open": 110.0, "high": 112.0, "low": 108.0, "close": 111.0, "volume": 10.0},
    {"open": 111.0, "high": 115.0, "low": 110.0, "close": 114.0, "volume": 10.0},
    {"open": 114.0, "high": 116.0, "low": 113.0, "close": 115.0, "volume": 10.0},
]

def signal_fn(window, index):
    if index == 0:
        return SignalProposal(direction=1, stop_price=98.0, target_price=104.0,
                                stop_distance=2.0)
    return None

eng = BacktestEngine(symbol="BTCUSDT", timeframe="1h")
out = eng.run(bars, signal_fn, start_index=0)
t = out["trades"][0]
print("backtest entry_price:", t.entry_price, "(signal bar close was 100.0, next open 110.0)")
print("backtest exit:", t.exit_price, t.exit_reason)
print()
print("F3 semantics would fill the same entry at close=100.0 -> difference =",
      t.entry_price - 100.0)
print()
# is the PAPER fill simulator present in the run path yet? (D58)
import subprocess
r = subprocess.run(["grep", "-rn", "-l", "-e", "PaperSimulator", "-e", "paper_fill",
                    "-e", "FillSimulator", str(REPO / "apex")],
                   capture_output=True, text=True)
print("files mentioning a paper fill simulator:", r.stdout or "(none)")
r2 = subprocess.run(["grep", "-rn", "simulator", str(REPO / "apex" / "execution"),
                    ], capture_output=True, text=True)
print("apex/execution simulator mentions:", (r2.stdout or "(none)")[:400])
