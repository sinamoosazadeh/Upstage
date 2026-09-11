# APEX_GEN5 — PHASE 2 TRACEABILITY MATRIX (frozen blueprint ⇄ code ⇄ evidence)

Editing rules: Part I & Part II ownership rows are PRE-SEEDED (planning artifact) — agents never change ownership, only fill Result columns for their own rows. Part III (per-CP detail rows) is written ONLY by the owning agent in its own section. A row without a concrete test file name is not evidence. Blueprint refs: chapter/section + line anchor of `APEX_GEN5.md`.

## Part I — Normative tree file → owner → test (from §9.5, lines 20156–20213; "create every file; do not rename")

| Tree file | Owner | Verifying test (owner fills) | Result |
|---|---|---|---|
| pyproject.toml | AGENT-01 | test_cp1_foundations::test_packaging | |
| requirements.lock | AGENT-01 | test_cp1_foundations::test_sbom_pins_exact | |
| README.md (run procedure) | AGENT-01 skeleton → AGENT-08 final | test_cp7_release_gates::test_readme_run_blocks | |
| apex/__init__.py | AGENT-01 | test_cp1_foundations::test_import_graph | |
| apex/errors.py | AGENT-01 | test_cp1_foundations::test_error_registry_ch7_complete | |
| apex/bus.py | AGENT-01 | test_cp1_foundations::test_bus_p0_sync_and_bounds | |
| apex/config.py | AGENT-01 | test_cp1_foundations::test_env_names_exact_no_shadow | |
| apex/identity/canonical_json.py | AGENT-01 | T-PIT-001 (+test_identity_canonical_json) | |
| apex/identity/uuid_v7.py | AGENT-01 | T-ID-001 (+test_uuid7_rfc9562) | |
| apex/identity/snapshot.py | AGENT-01 | T-PIT-004 (+test_snapshot_id_envelope_single) | |
| apex/identity/hashes.py | AGENT-01 | T-PIT-002 | |
| apex/data_catalog/contracts.py | AGENT-01 | T-DC-001 | |
| apex/data_catalog/catalog.py | AGENT-01 (+AGENT-02 via registration API) | T-DC-002, test_catalog_get_status_matrix | |
| apex/data_catalog/store/sqlite_store.py | AGENT-01 | T-RS-001..003, T-CL-001..003 | |
| apex/data_catalog/ingest/toobit_public.py | AGENT-01 | T-DC-003/004, T-OM-001..003 | |
| apex/quality/vector.py | AGENT-01 | test_quality_vector_seven_hard (§2.1) | |
| apex/quality/numerical.py | AGENT-01 | test_epsilon_two_tier (§2.2, GC-D4 E04 1e-12) | |
| apex/quality/pit.py | AGENT-01 | T-PIT-003, test_as_of_max_availability (§2.3) | |
| apex/engines/base.py | AGENT-02 | test_cp2_base_contract_streaming_idempotent | |
| apex/engines/e01_structure/engine.py | AGENT-03 | E01 §8 battery + T-E01-001 | |
| apex/engines/e02_liquidity/engine.py | AGENT-03 | E02 §8 battery | |
| apex/engines/e03_volume/engine.py | AGENT-03 | E03 §8 battery | |
| apex/engines/e04_volatility/engine.py | AGENT-03 | E04 §8 battery | |
| apex/engines/e05_fvg/engine.py | AGENT-04 | E05 §8 battery | |
| apex/engines/e06_orderblock/engine.py | AGENT-04 | E06 §8 battery + evidence-consumption lint | |
| apex/engines/e07_rtm/engine.py | AGENT-04 | E07 §8 battery | |
| apex/engines/e08_wyckoff/engine.py | AGENT-04 | E08 §8 battery (Ch.1 logic only) | |
| apex/engines/e09_trend/engine.py | AGENT-05 | E09 §8 battery | |
| apex/engines/e10_momentum/engine.py | AGENT-05 | E10 §8 battery (4 divergence kinds + CONVERGENCE + NONE) | |
| apex/engines/e11_regime/engine.py | AGENT-05 | T-E11-K9 + E11 §8 battery | |
| apex/engines/e12_temporal/engine.py | AGENT-05 | T-E12-Windows + E12 §8 battery | |
| apex/fabric/evidence.py | AGENT-06 | test_fabric_lifecycle_sl14 | |
| apex/fabric/context.py | AGENT-06 | test_context_confidence_combiner (§8.0) | |
| apex/fabric/conflict.py | AGENT-06 | test_conflict_policy_seven_invariants | |
| apex/pattern/detect.py | AGENT-06 | test_pattern_20_legacy + GF_SC fixtures | |
| apex/pattern/fibonacci.py | AGENT-06 | test_fibonacci_inrepo (directive 15) | |
| apex/setup/family_sf_fvg_sweep_rev.py | AGENT-06 | test_family_AD8_registry | |
| apex/setup/gates.py | AGENT-06 | test_gates_1_13_boundary_matrix | |
| apex/playbook/pb_fvg_sweep_rev_a.py | AGENT-06 | test_playbook_exit_precedence (X.4) | |
| apex/decision/pipeline.py | AGENT-07 | test_decision_eu_units + ranking | |
| apex/forecast/logistic.py | AGENT-07 | T-DR-003, test_bootstrap_p_model_p05 | |
| apex/risk/kernel.py | AGENT-07 | T_VETO 14× + sizing machine boundaries | |
| apex/execution/fsm.py | AGENT-07 | FSM transition matrix + E-EXEC-001 | |
| apex/execution/toobit_adapter.py | AGENT-07 | T_ADAPTER_SUBMIT/DUPLICATE/LOST_ACK | |
| apex/execution/toobit_map.py | AGENT-07 | test_wire_map_exact (§16 wire block) | |
| apex/ledger/store.py | AGENT-07 | T-LR-001..003, T_LEDGER | |
| apex/scheduler/clock.py | AGENT-07 | test_scheduler_order_semaphore4 | |
| apex/telegram/control_plane.py | AGENT-08 | test_screens_callbacks_busyguard | |
| apex/telegram/signaling.py | AGENT-08 | test_signaling_limits_idempotency | |
| apex/ops/watchdog.py | AGENT-08 | test_watchdog_heartbeats_gmail_isolation | |
| apex/ops/backup.py | AGENT-08 | T-RESTORE-001 | |
| params/universe_v1.yaml | AGENT-01 | test_params_frozen_values | |
| params/risk_defaults_v1.yaml | AGENT-01 | test_params_frozen_values (incl. §9.5-11) | |
| params/setup_weights_v1.yaml | AGENT-01 (values Ch.10) | test_setup_weights_sum1_frozen | |
| params/quality_weights_v1.yaml | AGENT-01 (values §2.1) | test_quality_tables_copy_exact | |
| params/toobit_wire_v1.yaml | AGENT-01 (values §16/SL-6) | test_wire_yaml_matches_ch16 | |
| params/e11_params_v4.yaml | AGENT-01 (values §9.5) | test_e11_yaml (AGENT-05 asserts §6-consistency) | |
| tests/unit/ (dir) | all (per-slot files) | — | |
| tests/integration/ (dir) | all (per-slot files) + AGENT-10 gate runner | — | |
| tests/fixtures/gf_sc_01.json | AGENT-06 | test_gf_sc_01_spring_shape | |
| tests/fixtures/gf_sc_02.json | AGENT-06 | test_gf_sc_02_upthrust_shape | |

Adoptive-file audit line (AGENT-10 fills): every additive file not listed above must have a DECISION_LOG entry: [ ] complete.

## Part II — AI.10 test matrix (lines 18906–18975) → owner → result

| Test id | Owning slot(s) | Result (owner fills `PASS(<date>, <test file>)` or `HARNESS-READY/OWNER-MEASURE-PENDING`) |
|---|---|---|
| T-DC-001..004 | A01 | |
| T-PIT-001..004 | A01 | |
| T-DR-001 | A02 + each engine slot (per engine) | |
| T-DR-002 | A06 | |
| T-DR-003 | A07 | |
| T-ID-001, T-ID-002 | A01 | |
| T-CL-001..003 | A01 | |
| T-OM-001..003 | A01 | |
| T-E01-001 | A03 | |
| (E02–E10 contract conformance per §8) | A03/A04/A05 | |
| T-E11-K9 | A05 | |
| T-E12-Windows | A05 | |
| T-AD-001, T-AD-002 | A09 | |
| T-RS-001..003 | A01 | |
| T-LR-001..003 | A07 | |
| T-MON-001 | A02 | |
| T-MON-002 | A01 (store-level) + A07 (FSM-level) | |
| T-FB-001..003 | A07 (fail-closed core) + A08 (startup reconciliation drill) | |
| T-NFR-001..004 | harnesses A08; in-sandbox run A10; target-device measurement = OWNER (honest label) | |
| T-TOOBIT-001..002 | harness A01 (public) / A07 (signed discipline); measurement = OWNER pre-deploy | |
| T-RESTORE-001 | A08 | |
| T-PKG-001 | A09 | |
| T_VETO | A07 | |
| T_MATCH, T_RECONCILE, T_LEDGER, T_ADAPTER_SUBMIT, T_ADAPTER_DUPLICATE, T_ADAPTER_LOST_ACK, T_MONOTONE | A07 | |
| engine §8 batteries (per engine: golden/replay/leak/ablation/Wilson/redundancy/serialization) | A03/A04/A05 | |
| GF_SC_01/02 (fire tests) + GF_SC_03..12 schema-only | A06 (01/02) + engines (03..12 assertions only) | |
| E-VAL-020/021/022 lint behaviors | A01 (021/022), A08 (020 busy guard) | |
| RSK-ERR-506 ratchet | A07 | |
| E-TELE-001..007 boundaries | A08 | |
| External gates G-TOOBIT-*, G-TARGET-DEVICE-*, G-CAPACITY-*, G-ADAPTER-*, G-RESTORE-*, G-PAPER-*, G-RISK-*, G-FALLBACK-* (AI.13) | A08/A09 harnesses; A10 records evidence; measurements = OWNER procedures (never agent-claimed) | |

## Part III — Per-checkpoint requirement detail (each agent fills ONLY its section)

### CP-1 rows (A01) — columns: Requirement | Blueprint ref | Component | Test evidence | Status
(to be filled)

### CP-2 rows (A02)
(to be filled — minimum one row per feature tier group + registry-completeness + base contract clauses)

### CP-3 rows (A03/A04/A05)
(to be filled — minimum one row per engine §3 formula group, §5 schema, §6 param table)

### CP-4 rows (A06)
(to be filled — one row per gate 1–13, per fabric rule, per AC/AD/AE/AF contract)

### CP-5 rows (A07)
(to be filled — one row per veto 1–14, per FSM transition group, per Ch.13/14 formula, per wire-map row)

### CP-6 rows (A08)
(to be filled — one row per screen/callback/busy-guard/bucket/watchdog/backup/alert-policy clause)

### CP-6 rows (A09)
(to be filled — one row per W/Z/AA/X.6 clause, per governance capability)

### CP-7 audit ledger (A10)
(to be filled — T-id completion summary, sweep findings, triage results)
