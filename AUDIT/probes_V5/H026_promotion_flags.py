"""H-026: compare supplied gate booleans with contradictory reported metrics."""
import json
from apex.research import promotion as pr
from tests.unit.test_research_promotion import _candidate

candidate = _candidate(
    wfo={"decision": "PROMOTED", "oos_sharpe": -2.0,
         "profit_factor": 0.2, "max_drawdown": 0.95,
         "checks": {"oos_sharpe_gt_1_0": False, "pf_gt_1_2": False,
                     "drawdown_lt_15pct": False}},
    pbo={"flagged_high": False, "pbo": 0.99},
    deflated_sharpe={"passes": True, "deflated_sharpe": -100.0,
                     "dsr_pvalue": 0.999},
    benchmark={"outperforms": True, "strategy_return": -0.9,
               "benchmark_return": 3.0, "z": -20.0},
)
verdict = pr.evaluate_promotion(candidate)
proposal = {"reason": "probe", "pit_backtest_180d": 180,
            "forward_observation_30d": 30,
            "out_of_sample_evaluation": "probe-oos",
            "parameter_board_approval": "probe-board"}
draft = pr.draft_package(
    candidate=candidate, values={"correlation_cap": 0.6}, version="1.0.0",
    code_revision="b" * 40, feature_version="4.0.0", model_version="4.0.0",
    seed=1, reason="controlled contradictory flags probe",
    proposals={"correlation_cap": proposal})
print(json.dumps({"wfo_metrics_contradict_flag": True,
                  "pbo_metric": candidate.pbo.get("pbo"),
                  "dsr_metric": candidate.deflated_sharpe.get("deflated_sharpe"),
                  "benchmark_metrics_contradict_flag": True,
                  "gate_decision": verdict["decision"],
                  "checks": verdict["checks"],
                  "paper_trial_required": verdict["paper_trial_required"],
                  "draft_decision": draft["decision"],
                  "draft_next_step": draft.get("next_step")},
                 sort_keys=True, indent=2))
