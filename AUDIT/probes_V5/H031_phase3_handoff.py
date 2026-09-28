"""H-031: inspect real bootstrap Phase-3 handoff versus orchestration."""
import json
from apex.research.bootstrap import BootstrapRunner
from apex.research.optimizer import DualOptimizer, OptimizerSchedule

runner = BootstrapRunner(fetcher=lambda *a: {}, ingest=lambda *a: None,
                         store=object(), cells=[("BTCUSDT", "15m")])
plan = runner.phase3_plan()
continuous = runner.command("continuous on")
print(json.dumps({
    "phase3_plan": plan,
    "bootstrap_phase_methods": [name for name in dir(runner)
                                 if name.startswith("run_phase") or name.startswith("phase3")],
    "continuous_command_sets_state_only": continuous["state"]["continuous"],
    "optimizer_run_method_is_single_run": hasattr(DualOptimizer, "run_run"),
    "schedule_exposes_periodic_loop": any("loop" in name or "daemon" in name
                                           for name in dir(OptimizerSchedule)),
}, sort_keys=True, indent=2))
