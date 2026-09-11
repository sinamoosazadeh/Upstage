# APEX_GEN5 — PHASE 2 TRACEABILITY MATRIX (frozen blueprint ⇄ code ⇄ evidence) — Rev-2

Editing rules: Part I & Part II ownership rows are PRE-SEEDED (planning artifact) — agents never change ownership, only fill Result columns for their own rows (one agent may fill several CP-5 stage rows if roles merge under the RESUME protocol — always under the SAME owning-agent column value; the Result text carries the session stamp). Part III (per-CP detail rows) is written ONLY by the owning role in its section. A row without a concrete test file name is not evidence. Blueprint refs: chapter/section + line anchor of `APEX_GEN5.md`. Salvage dispositions live in `PHASE2_SALVAGE.md`; every `ADOPTED-*` row must appear here as its replacement row with a proving test.

## Part I — Normative tree file → owner → test (from §9.5, lines 20156–20213; "create every file; do not rename")

| Tree file | Owner | Verifying test (owner fills) | Result |
|---|---|---|---|
| pyproject.toml | AGENT-01 | test_cp1_foundations::test_packaging | |
| requirements.lock | AGENT-01 | test_cp1_foundations::test_sbom_pins_exact | |
| README.md (run procedure) | AGENT-01 skeleton → AGENT-05[TELEGRAM-OPS] final | test_cp6_release_gates::test_readme_run_blocks | |
| apex/__init__.py | AGENT-01 | test_cp1_foundations::test_import_graph | |
| apex/errors.py | AGENT-01 | test_cp1_foundations::test_error_registry_ch7_complete | |
| apex/bus.py | AGENT-01 | test_cp1_foundations::test_bus_p0_sync_and_bounds | |
| apex/config.py | AGENT-01 | test_cp1_foundations::test_env_names_exact_no_shadow + test_dotenv_absent | |
| apex/identity/canonical_json.py | AGENT-01 | T-PIT-001 (+test_identity_canonical_json) | |
| apex/identity/uuid_v7.py | AGENT-01 | T-ID-001 (+test_uuid7_single_implementation_repo_grep) | |
| apex/identity/snapshot.py | AGENT-01 | T-PIT-004 (+test_snapshot_id_single_envelope) | |
| apex/identity/hashes.py | AGENT-01 | T-PIT-002 | |
| apex/data_catalog/contracts.py | AGENT-01 | T-DC-001 | |
| apex/data_catalog/catalog.py | AGENT-01 | T-DC-002 + test_catalog_get_status_matrix + test_registration_api | |
| apex/data_catalog/store/sqlite_store.py | AGENT-01 | T-RS-001..003, T-CL-001..003 | |
| apex/data_catalog/ingest/toobit_public.py | AGENT-01 | T-DC-003/004, T-OM-001..003 | |
| apex/data_catalog/{atomic,molecular,organismic,math,performance}/ (tier modules per §3.12 layout; additive, ADR-P2-006) | AGENT-01 | registry completeness suite (§3.13: 74==74; F49 absent-by-design; F56 UNAVAILABLE; unregistered-id hook) | |
| apex/quality/vector.py | AGENT-01 | test_quality_vector_seven_hard (§2.1) | |
| apex/quality/numerical.py | AGENT-01 | test_epsilon_two_tier (§2.2; GC-D4 E04 1e-12) + test_no_placeholder_sma_path | |
| apex/quality/pit.py | AGENT-01 | T-PIT-003, test_as_of_max_availability (§2.3) | |
| apex/engines/base.py | AGENT-01 | test_cp1_base_contract_streaming_idempotent + emission→24-field DDL validation | |
| apex/engines/e01_structure/engine.py | AGENT-02 | E01 §8 battery + T-E01-001 | |
| apex/engines/e02_liquidity/engine.py | AGENT-02 | E02 §8 battery (Merton/DBSCAN/salience present) | |
| apex/engines/e03_volume/engine.py | AGENT-02 | E03 §8 battery + Phase 67/79/80/88 clause checks | |
| apex/engines/e04_volatility/engine.py | AGENT-02 | E04 §8 battery (ε=1e-12; no adaptive ATR) | |
| apex/engines/e05_fvg/engine.py | AGENT-02 | E05 §8 battery (min_width 0.2) | |
| apex/engines/e06_orderblock/engine.py | AGENT-02 | E06 §8 battery + evidence-consumption lint (no internal SMA/ATR) | |
| apex/engines/e07_rtm/engine.py | AGENT-03 | E07 §8 battery + E12-degraded branch test | |
| apex/engines/e08_wyckoff/engine.py | AGENT-03 | E08 §8 battery (Ch.1 logic; ch.2–4 Wave-Out) | |
| apex/engines/e09_trend/engine.py | AGENT-03 | E09 §8 battery | |
| apex/engines/e10_momentum/engine.py | AGENT-03 | E10 §8 battery (4 divergence kinds + CONVERGENCE + NONE) | |
| apex/engines/e11_regime/engine.py | AGENT-03 | T-E11-K9 + E11 §8 battery + live-gate-off default test | |
| apex/engines/e12_temporal/engine.py | AGENT-03 | T-E12-Windows + E12 §8 battery + §8.8 UTC-boundary test | |
| apex/fabric/evidence.py | AGENT-04 | test_fabric_lifecycle_sl14 + crosswalk (emitted≡ACTIVE etc.) | |
| apex/fabric/context.py | AGENT-04 | test_context_confidence_combiner (§8.0 weights/decay/thresholds) | |
| apex/fabric/conflict.py | AGENT-04 | test_conflict_policy_four_outputs + seven invariants | |
| apex/pattern/detect.py | AGENT-04 | test_pattern_legacy20 + GF_SC_01/02 fire + AC admission gates | |
| apex/pattern/fibonacci.py | AGENT-04 | test_fibonacci_inrepo (directive 15: no network) | |
| apex/setup/family_sf_fvg_sweep_rev.py | AGENT-04 | test_family_AD8_registry (only Wave-In family; all 140 cells) | |
| apex/setup/gates.py | AGENT-04 | test_gates_1_13_boundary_matrix (Gate 11 = lineage/snapshot only) | |
| apex/playbook/pb_fvg_sweep_rev_a.py | AGENT-04 | test_playbook_exit_precedence (X.4) + AE.1 16-field template | |
| apex/decision/pipeline.py | AGENT-05[RUNTIME] | test_decision_eu_units + ranking key + eligibility conjunction | |
| apex/forecast/logistic.py | AGENT-05[RUNTIME] | T-DR-003, test_bootstrap_p05_paper_only, U/C formulas | |
| apex/risk/kernel.py | AGENT-05[RUNTIME] | T_VETO 14× + sizing machine boundaries + breakers + margin 60/40/20 | |
| apex/execution/fsm.py | AGENT-05[RUNTIME] | FSM transition matrix + E-EXEC-001 + reconcile-first | |
| apex/execution/toobit_adapter.py | AGENT-05[RUNTIME] | T_ADAPTER_SUBMIT/DUPLICATE/LOST_ACK; forbidden-op boundary test | |
| apex/execution/toobit_map.py | AGENT-05[RUNTIME] | test_wire_map_exact (symbols, 1mo→1M, −1120, side maps) | |
| apex/ledger/store.py | AGENT-05[RUNTIME] | T-LR-001..003, T_LEDGER, single-writer proof | |
| apex/scheduler/clock.py | AGENT-05[RUNTIME] | test_scheduler_order_semaphore4 + drift block | |
| apex/telegram/control_plane.py | AGENT-05[TELEGRAM-OPS] | test_screens_callbacks_busyguard | |
| apex/telegram/signaling.py | AGENT-05[TELEGRAM-OPS] | test_signaling_limits_idempotency + Agg chart test | |
| apex/ops/watchdog.py | AGENT-05[TELEGRAM-OPS] | test_watchdog_heartbeats_gmail_isolation | |
| apex/ops/backup.py | AGENT-05[TELEGRAM-OPS] | T-RESTORE-001 | |
| params/universe_v1.yaml | AGENT-01 | test_params_frozen_values | |
| params/risk_defaults_v1.yaml | AGENT-01 | test_params_frozen_values (§9.5-11 literals) | |
| params/setup_weights_v1.yaml | AGENT-01 (values Ch.10) | test_setup_weights_sum1_frozen | |
| params/quality_weights_v1.yaml | AGENT-01 (values §2.1) | test_quality_tables_copy_exact (Q_raw/Q_min/OI-lag; STALE=0.5) | |
| params/toobit_wire_v1.yaml | AGENT-01 (values Ch.16/SL-6) | test_wire_yaml_matches_ch16 | |
| params/e11_params_v4.yaml | AGENT-01 (values §9.5) | test_e11_yaml (AGENT-03 asserts §6-consistency, ADR-P2-008) | |
| tests/unit/ (dir) | all (per-stage files) | — | |
| tests/integration/ (dir) | all + AGENT-06 gate runner | — | |
| tests/fixtures/gf_sc_01.json | AGENT-04 | test_gf_sc_01_spring_shape | |
| tests/fixtures/gf_sc_02.json | AGENT-04 | test_gf_sc_02_upthrust_shape | |

Adoptive-file audit line (AGENT-06): every additive file (tiers, tests, fixtures, scripts, research package, migrations) must trace to a DECISION_LOG/SALVAGE row: [ ] complete. Engine fixtures e0N_FIX_*.json listed with their engines' §8 rows above (one Result row per fixture file set, by the owning agent).

## Part II — AI.10 test matrix (lines 18906–18975) + chapter acceptance ids → owner → result

| Test id | Owning stage | Result (`PASS(<date>, <test file>)` / `HARNESS-READY/OWNER-MEASURE-PENDING`) |
|---|---|---|
| T-DC-001..004 | AGENT-01 | |
| T-PIT-001..004 | AGENT-01 | |
| T-DR-001 | AGENT-01 (feature tier) + each engine §8 battery re-runs it (A02/A03) | |
| T-DR-002 | AGENT-04 | |
| T-DR-003 | AGENT-05[RUNTIME] | |
| T-ID-001, T-ID-002 | AGENT-01 | |
| T-CL-001..003 | AGENT-01 | |
| T-OM-001..003 | AGENT-01 | |
| T-E01-001 | AGENT-02 | |
| T-E02..T-E10 contract conformance (per-engine §8 acceptance) | AGENT-02 (E02–E06), AGENT-03 (E07–E10) | |
| T-E11-K9 | AGENT-03 | |
| T-E12-Windows | AGENT-03 | |
| T-AD-001, T-AD-002 | AGENT-05[RESEARCH] | |
| T-RS-001..003 | AGENT-01 | |
| T-LR-001..003 | AGENT-05[RUNTIME] | |
| T-MON-001 | AGENT-01 | |
| T-MON-002 | AGENT-01 (store) + AGENT-05[RUNTIME] (FSM) | |
| T-FB-001..003 | AGENT-05[RUNTIME] (core) + AGENT-05[TELEGRAM-OPS] (startup drill) | |
| T-NFR-001..004 | harness A05[TELEGRAM-OPS]; sandbox run A06; target-device = OWNER (honest labels per ADR-P2-010) | |
| T-TOOBIT-001..002 | harness A01 (public) / A05[RUNTIME] (signed discipline); measurement = OWNER pre-deploy | |
| T-RESTORE-001 | AGENT-05[TELEGRAM-OPS] | |
| T-PKG-001 | AGENT-05[RESEARCH] | |
| T_VETO | AGENT-05[RUNTIME] | |
| T_MATCH, T_RECONCILE, T_LEDGER, T_ADAPTER_SUBMIT, T_ADAPTER_DUPLICATE, T_ADAPTER_LOST_ACK, T_MONOTONE | AGENT-05[RUNTIME] | |
| engine §8 batteries (golden/replay/leak/ablation/Wilson/redundancy/serialization; +E12 §8.8) | AGENT-02 / AGENT-03 | |
| GF_SC_01/02 fire tests; GF_SC_03..12 schema-only asserts | AGENT-04 / engines | |
| E-VAL-020/021/022 lint behaviors | AGENT-01 (021/022), AGENT-05[TELEGRAM-OPS] (020 busy guard) | |
| RSK-ERR-506 ratchet | AGENT-05[RUNTIME] | |
| E-TELE-001..007 boundaries | AGENT-05[TELEGRAM-OPS] | |
| External gates G-TOOBIT-*, G-TARGET-DEVICE-*, G-CAPACITY-*, G-ADAPTER-*, G-RESTORE-*, G-PAPER-*, G-RISK-*, G-FALLBACK-* (AI.13) | harnesses AGENT-05[RUNTIME/TELEGRAM-OPS/RESEARCH] as assigned; evidence recorded by AGENT-06; measurements = OWNER procedures (never agent-claimed) | |

## Part III — Per-checkpoint requirement detail (each role fills ONLY its section)

### CP-1 rows (AGENT-01) — Requirement | Blueprint ref | Component | Test evidence | Status
(to be filled — minimum: one row per §2.1 component + Q_min/Q_raw tables, §2.2 epsilon/rounding rule, §2.3 window/MTF clause, Ch.4/Ch.5 DDL block, Ch.7 error row group, identity-clause (canonical/uuid/snapshot/as_of), bus clause, config clause, §3.12 per-tier group + each §3.12 global rule, §9.5 params/env/frozen-number row)

### CP-2 rows (AGENT-02, both stages)
(to be filled — one row per engine §3 formula group, §5 schema, §6 param row, §8 clause; salvage rows referenced by legacy path + disposition)

### CP-3 rows (AGENT-03, both stages)
(to be filled — same shape as CP-2; +E11 dimensionality proof row; +E12 window rule 1–5)

### CP-4 rows (AGENT-04)
(to be filled — one row per gate 1–13, per fabric/conflict/context clause, per AC/AD/AE/AF contract, per GF fixture)

### CP-5 rows (AGENT-05; three sub-tables §[RUNTIME] §[TELEGRAM-OPS] §[RESEARCH])
(to be filled — runtime: per veto 1–14, per Ch.13/14 formula, per FSM transition group, per wire-map row, per scheduler clause; ops: per screen/callback/busy-guard/bucket/watchdog/backup/alert-policy clause; research: per W/Z/AA/X.6 governance capability)

### CP-6 audit ledger (AGENT-06)
(to be filled — T-id completion summary; sweep findings; corrective patch list; reopen entries; final dispositions)
