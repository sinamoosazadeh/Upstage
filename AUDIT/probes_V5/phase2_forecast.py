"""Real-code probes for H-001/H-009/H-014; synthetic inputs only."""
import asyncio
import json
import tempfile
from pathlib import Path

from apex.forecast.logistic import (X_FEATURES, ForecastEvent, build_forecast)
from apex.research.bootstrap import BootstrapRunner
from apex.research.checkpoints import ResearchCheckpointStore

async def phase2(path):
    store = ResearchCheckpointStore(path=str(path))
    runner = BootstrapRunner(fetcher=lambda *_: [], ingest=lambda *_: None,
        store=store, cells=[("BTCUSDT", "1h")])
    async with store:
        return await runner.run_phase2(replay=lambda: {
            "exceptions": 999, "critical_failures": ["FATAL"],
            "ledger_reconciled": False})

def main():
    event = ForecastEvent(target_condition="target", stop_condition="stop",
        horizon=1, entry_ref="synthetic", symbol="BTCUSDT", timeframe="1h", timestamp=1)
    x = {k: 0.0 for k in X_FEATURES}
    u = {"calibration": .2, "data_quality": .2, "disagreement": .2}
    record = build_forecast(event, x=x, uncertainty=u,
        package={"p_hat": .61}, p_hat=.99, environment="LIVE")
    with tempfile.TemporaryDirectory() as td:
        phase2_result = asyncio.run(phase2(Path(td) / "bootstrap.sqlite3"))
    print(json.dumps({
        "H001": {"replay_cli_registered": False,
                 "basis": "scripts/run_apex.py COMMANDS has no replay entry (source inspection)"},
        "H009": phase2_result,
        "H014": {"package": {"p_hat": .61}, "caller_p_hat": .99,
                 "result_p_hat": record.p_hat,
                 "bootstrap_prior": record.bootstrap_prior,
                 "eligible_environments": record.eligible_environments,
                 "is_admissible_live": record.is_admissible("LIVE")}},
        sort_keys=True, indent=2, default=str))

if __name__ == "__main__": main()
