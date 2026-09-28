from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
items = {
    "tests/unit/test_cp1_foundations.py::test_all_cp1_files_exist_non_empty": "tests/unit/test_cp1_foundations.py::TestNormativeTree::test_all_cp1_files_exist_non_empty",
    "tests/unit/test_cp1_foundations.py::test_gitignore_adr_p2_013": "tests/unit/test_cp1_foundations.py::TestPackaging::test_gitignore_adr_p2_013",
    "tests/unit/test_cp1_foundations.py::test_run_all_tests_script": "tests/unit/test_cp1_foundations.py::TestPackaging::test_run_all_tests_script",
    "tests/unit/test_catalog.py::test_tdr_001_feature_replay_byte_identical": "tests/unit/test_catalog.py::TestReplayAndMonotonic::test_tdr_001_feature_replay_byte_identical",
    "tests/unit/test_identity.py::test_governed_as_of_max_and_fail_closed": "tests/unit/test_identity.py::TestSnapshot::test_governed_as_of_max_and_fail_closed",
    "tests/unit/test_cp1_foundations.py::test_quality_weights_copy_exact_21": "tests/unit/test_cp1_foundations.py::TestParamsFrozenValues::test_quality_weights_copy_exact_21",
    "tests/unit/test_cp1_foundations.py::test_universe_v1_literals": "tests/unit/test_cp1_foundations.py::TestParamsFrozenValues::test_universe_v1_literals",
    "tests/unit/test_cp1_foundations.py::test_risk_defaults_literals": "tests/unit/test_cp1_foundations.py::TestParamsFrozenValues::test_risk_defaults_literals",
    "tests/unit/test_cp1_foundations.py::test_setup_weights_literals": "tests/unit/test_cp1_foundations.py::TestParamsFrozenValues::test_setup_weights_literals",
    "tests/unit/test_cp1_foundations.py::test_toobit_wire_literals": "tests/unit/test_cp1_foundations.py::TestParamsFrozenValues::test_toobit_wire_literals",
    "tests/unit/test_cp1_foundations.py::test_e11_params_literals": "tests/unit/test_cp1_foundations.py::TestParamsFrozenValues::test_e11_params_literals",
    "tests/unit/test_ops_bootstrap_service.py::test_complete_run_mirrors_canonical_done_and_cursor": "tests/unit/test_ops_bootstrap_service.py::TestService::test_complete_run_mirrors_canonical_done_and_cursor",
}
collected = set((ROOT / "AUDIT/probes_V5/I007_collect.out").read_text().splitlines())
print("Exact node-id correction map for unique nonexistent matrix selectors")
for wrong, right in items.items():
    print(f"MISSING {wrong}")
    print(f"  COLLECTED {right}: {right in collected}")
wrong_class = "tests/unit/test_research_proxies.py::TestIncrementalAndWaveOut"
actual = [
    "tests/unit/test_research_proxies.py::TestWilsonAndAA7::test_numba_is_not_used",
    "tests/unit/test_research_proxies.py::TestWilsonAndAA7::test_incremental_only_flag",
]
print(f"MISSING {wrong_class} (class is absent)")
for right in actual:
    print(f"  RELATED COLLECTED {right}: {right in collected}")
print(f"unique malformed selectors={len(items)+1}; bare-method selectors={len(items)}; absent-class selector=1")
