"""Probe W.5 package vetoes with complete proposals, using real validator code."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from apex.research import governance as gov

proposal = {
    "reason": "adversarial test only",
    "pit_backtest_180d": 180,
    "forward_observation_30d": 30,
    "out_of_sample_evaluation": "OOS-test",
    "parameter_board_approval": "board-test",
}
print(f"proposal_validation={gov.validate_change_proposal(proposal)['decision']}")
print(f"registered_veto_names={len(gov.VETO_FIELD_NAMES)}")
rejected = 0
for name in gov.VETO_FIELD_NAMES:
    package = gov.ParameterPackage(
        package_id="i014-probe", version="1.0.0", values={name: 1},
        code_revision="a" * 40, feature_version="4.0.0",
        model_version="4.0.0", seed=7, reason="synthetic probe")
    verdict = gov.validate_package(package, proposals={name: proposal})
    kinds = [item["kind"] for item in verdict["violations"]]
    ok = verdict["decision"] == "REJECTED" and "RED_LINE_FIELD" in kinds
    ok = ok and "PROPOSAL_ABSENT" not in kinds
    ok = ok and "PROPOSAL_INCOMPLETE" not in kinds
    print(f"{name}: decision={verdict['decision']} kinds={','.join(kinds)} complete_proposal_rejected={ok}")
    rejected += int(ok)
print(f"complete_proposal_veto_rejections={rejected}/{len(gov.VETO_FIELD_NAMES)}")
# Mirror the test's proposals=None setup: the optional proposal check is skipped.
name = gov.VETO_FIELD_NAMES[0]
package = gov.ParameterPackage(
    package_id="i014-probe-no-proposals", version="1.0.0", values={name: 1},
    code_revision="a" * 40, feature_version="4.0.0",
    model_version="4.0.0", seed=7)
verdict = gov.validate_package(package)
print(f"test_style_no_proposals={verdict['decision']}:{','.join(v['kind'] for v in verdict['violations'])}")
legacy_name = "VETO_STALE_DATA"
print(f"VETO_STALE_DATA_in_registry={legacy_name in gov.VETO_FIELD_NAMES}")
print(f"VETO_STALE_DATA_in_forbidden_fields={legacy_name in gov.FORBIDDEN_FIELDS}")
legacy_package = gov.ParameterPackage(
    package_id="i014-test-alias", version="1.0.0", values={legacy_name: 1},
    code_revision="a" * 40, feature_version="4.0.0",
    model_version="4.0.0", seed=7)
legacy_verdict = gov.validate_package(legacy_package, proposals={})
print(f"promotion_test_alias_empty_proposals={legacy_verdict['decision']}:{','.join(v['kind'] for v in legacy_verdict['violations'])}")
