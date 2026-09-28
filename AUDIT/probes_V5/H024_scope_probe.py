"""H-024: exercise real optimizer API with an out-of-scope/red-line grid key.
No checkpoints or repository suggestion files are created."""
import asyncio
import json
import tempfile
from pathlib import Path

from apex.research.optimizer import (
    DualOptimizer, ParameterGrid, ParameterRange, SIGNAL_SCOPE,
)

async def main():
    seen = []
    def evaluate(optimizer, params, cell_id):
        seen.append({"optimizer": optimizer, "cell": cell_id, "params": dict(params)})
        return {"feasible": True, "value": 1.0}

    grid = ParameterGrid([ParameterRange("capital_hard_cap", 0.5, 0.5, 1.0)])
    optimizer = DualOptimizer()
    result = await optimizer.run_run(
        run_id="h024-probe", cells=["BTCUSDT-1h"],
        grids={"BTCUSDT-1h": grid}, evaluate=evaluate,
        optimizer="SIGNAL", utc_hhmm="03:30", live_workload=False)

    with tempfile.TemporaryDirectory(prefix="h024-suggestion-") as temp:
        path = Path(temp) / "suggestions"
        written = DualOptimizer(suggestions_dir=path).write_suggestion(
            run_id="h024-probe", cell_id="BTCUSDT-1h", optimizer="SIGNAL",
            params={"capital_hard_cap": 0.5}, reason="controlled probe")
        saved = json.loads((path / "h024-probe" / "BTCUSDT-1h-signal.json").read_text())

    print(json.dumps({
        "signal_scope": list(SIGNAL_SCOPE),
        "grid_names": list(grid.names),
        "red_line_name": "capital_hard_cap",
        "evaluate_calls": len(seen),
        "evaluate_received": seen,
        "run_status": result["status"],
        "returned_best_params": result["results"][0]["best_params"],
        "suggestion_written_outside_repo": written["written"],
        "suggestion_params": saved["params"],
        "package_validation_invoked": False,
    }, sort_keys=True, indent=2))

asyncio.run(main())
