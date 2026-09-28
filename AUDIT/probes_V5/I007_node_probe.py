from __future__ import annotations

import subprocess
import sys

BAD = [
    "tests/unit/test_cp1_foundations.py::test_all_cp1_files_exist_non_empty",
    "tests/unit/test_cp1_foundations.py::test_gitignore_adr_p2_013",
    "tests/unit/test_cp1_foundations.py::test_run_all_tests_script",
    "tests/unit/test_catalog.py::test_tdr_001_feature_replay_byte_identical",
    "tests/unit/test_identity.py::test_governed_as_of_max_and_fail_closed",
    "tests/unit/test_cp1_foundations.py::test_quality_weights_copy_exact_21",
    "tests/unit/test_cp1_foundations.py::test_universe_v1_literals",
    "tests/unit/test_cp1_foundations.py::test_risk_defaults_literals",
    "tests/unit/test_cp1_foundations.py::test_setup_weights_literals",
    "tests/unit/test_cp1_foundations.py::test_toobit_wire_literals",
    "tests/unit/test_cp1_foundations.py::test_e11_params_literals",
    "tests/unit/test_research_proxies.py::TestIncrementalAndWaveOut",
    "tests/unit/test_ops_bootstrap_service.py::test_complete_run_mirrors_canonical_done_and_cursor",
]
GOOD = [
    "tests/unit/test_cp1_foundations.py::TestNormativeTree::test_all_cp1_files_exist_non_empty",
    "tests/unit/test_cp1_foundations.py::TestPackaging::test_gitignore_adr_p2_013",
    "tests/unit/test_cp1_foundations.py::TestPackaging::test_run_all_tests_script",
    "tests/unit/test_catalog.py::TestReplayAndMonotonic::test_tdr_001_feature_replay_byte_identical",
    "tests/unit/test_identity.py::TestSnapshot::test_governed_as_of_max_and_fail_closed",
    "tests/unit/test_cp1_foundations.py::TestParamsFrozenValues::test_quality_weights_copy_exact_21",
    "tests/unit/test_cp1_foundations.py::TestParamsFrozenValues::test_universe_v1_literals",
    "tests/unit/test_cp1_foundations.py::TestParamsFrozenValues::test_risk_defaults_literals",
    "tests/unit/test_cp1_foundations.py::TestParamsFrozenValues::test_setup_weights_literals",
    "tests/unit/test_cp1_foundations.py::TestParamsFrozenValues::test_toobit_wire_literals",
    "tests/unit/test_cp1_foundations.py::TestParamsFrozenValues::test_e11_params_literals",
    "tests/unit/test_research_proxies.py::TestWilsonAndAA7::test_numba_is_not_used",
    "tests/unit/test_research_proxies.py::TestWilsonAndAA7::test_incremental_only_flag",
    "tests/unit/test_ops_bootstrap_service.py::TestService::test_complete_run_mirrors_canonical_done_and_cursor",
]


def run(label: str, args: list[str], expected: int) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False,
    )
    print(f"===== {label}; expected exit={expected}; actual exit={result.returncode} =====")
    print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    assert result.returncode == expected, f"{label}: {result.returncode} != {expected}"


run("matrix selectors exactly as written (collection only)",
    ["--collect-only", "-q", "-p", "no:cacheprovider", *BAD], expected=4)
run("corrected class-qualified selectors (execute tests)",
    ["-q", "-p", "no:cacheprovider", *GOOD], expected=0)
print("probe=PASS; selectors and local test doubles only; no network/device/data access")
