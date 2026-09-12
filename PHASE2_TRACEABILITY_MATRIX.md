# APEX_GEN5 — PHASE 2 TRACEABILITY MATRIX (frozen blueprint ⇄ code ⇄ evidence) — Rev-3

Editing rules: Part I & Part II ownership rows are PRE-SEEDED by the plan — executors never change the CP column, only fill Result rows of their own CP (Result format `PASS(<date>, <test file>)`). Part III (per-CP detail rows) is written ONLY by the owning stage in its section. A row without a concrete test file name is not evidence. Blueprint refs = chapter/section + line anchor of `APEX_GEN5.md`. Stages: CP-1 foundation+fabric+base · CP-2 E01–E03 · CP-3 E04–E06 · CP-4 E07–E09 · CP-5 E10–E12 · CP-6 context chain + forecast/decision/risk · CP-7 execution/ledger/scheduler + telegram/alerts · CP-8 research/governance/ops + closeout.

## Part I — Normative tree file → owning stage → verifying test (from §9.5, lines 20156–20213; "create every file; do not rename")

| Tree file | Owner | Verifying test (owner fills) | Result |
|---|---|---|---|
| pyproject.toml · requirements.lock | CP-1 | test_cp1_foundations::test_packaging + test_sbom_pins_exact (nine pins; pytest dev-extra only; no python-dotenv) |  PASS(2026-09-12, tests/unit/test_cp1_foundations.py) |
| README.md (run procedure) | CP-1 skeleton → CP-7 final → CP-8 verified | test_cp8_closeout::test_readme_run_blocks |  PASS(2026-09-12, tests/unit/test_cp1_foundations.py::test_all_cp1_files_exist_non_empty) — skeleton; run blocks finalized by CP-7 |
| .gitignore (ADR-P2-013) | CP-1 | test_import_graph + git status hygiene |  PASS(2026-09-12, tests/unit/test_cp1_foundations.py::test_gitignore_adr_p2_013) |
| apex/__init__.py · apex/errors.py | CP-1 | test_cp1::test_error_registry_ch7_complete (every Ch.7 row) |  PASS(2026-09-12, tests/unit/test_errors.py::test_error_registry_ch7_complete + test_cp1_foundations import-chain) |
| apex/bus.py | CP-1 | test_cp1::test_bus_p0_sync_and_bounds |  PASS(2026-09-12, tests/unit/test_bus.py — P0 sync/never-dropped; P1 lane; drop-oldest+QUEUE_OVERFLOW_DROP; raw queue 1000) |
| apex/config.py | CP-1 | test_cp1::test_env_names_exact_no_shadow + test_no_dotenv_bypass |  PASS(2026-09-12, tests/unit/test_config.py — env names exact, no-shadow, no-dotenv) |
| apex/identity/{canonical_json,uuid_v7,snapshot,hashes}.py | CP-1 | T-PIT-001..004 + T-ID-001/002 + test_uuid7_single_implementation_grep |  PASS(2026-09-12, tests/unit/test_identity.py — T-PIT-001..004, T-ID-001/002, uuid7 single-implementation grep) |
| apex/data_catalog/contracts.py · catalog.py | CP-1 | T-DC-001/002 + registration API test |  PASS(2026-09-12, tests/unit/test_catalog.py::TestTDC + registration API) |
| apex/data_catalog/store/sqlite_store.py | CP-1 | T-RS-001..003, T-CL-001..003 + DDL verbatim-equivalence rows vs Ch.4 L14383–14544 / Ch.5 L14545–14642 |  PASS(2026-09-12, tests/integration/test_store_integration.py — T-RS-001..003, T-CL-001..003, DDL verbatim-equivalence) |
| apex/data_catalog/ingest/toobit_public.py | CP-1 | T-DC-003/004, T-OM-001..003 |  PASS(2026-09-12, tests/unit/test_catalog.py T-DC-003/004 + T-OM-001..003; tests/unit/test_toobit_public.py) |
| apex/data_catalog/{atomic,molecular,organismic,math,performance}/ + 74-feature registry (§3.12; additive tiers per ADR-P2-006) | CP-1 | §3.13 completeness suite (74==74, F49 absent-by-design, F56 UNAVAILABLE, unregistered-id hook, tier-cache rules) |  PASS(2026-09-12, tests/unit/test_catalog.py::TestRegistryCompleteness + TestTierCacheRules — 74==74, F49 REMOVED-slot, F56 always-UNAVAILABLE, unregistered→INVALID, tier caches) |
| apex/quality/{vector,numerical,pit}.py | CP-1 | §2.1 seven hard gates + Q tables copy-exact · §2.2 two-tier eps + quantize + division guards · §2.3 as-of windows/MTF + T-PIT-003 |  PASS(2026-09-12, tests/unit/test_quality.py — §2.1 gates+Q tables copy-exact, §2.2 two-tier eps+quantize+guards, §2.3 as_of/MTF) |
| apex/engines/base.py (frozen contract; streaming+idempotency; emission→24-field validation) | CP-1 | test_cp1_base_contract suite; later engine stages assert consumption, never edit |  PASS(2026-09-12, tests/unit/test_base_contract.py — FROZEN base suite) |
| apex/engines/e01_structure/ · e02_liquidity/ · e03_volume/ | CP-2 | each engine's FULL §8 battery + T-E01-001 + T-DR-001 re-run + fixtures | |
| apex/engines/e04_volatility/ · e05_fvg/ · e06_orderblock/ | CP-3 | §8 batteries (E04 ε=1e-12; E05 min_width 0.2; E06 evidence-consumption lint) | |
| apex/engines/e07_rtm/ · e08_wyckoff/ · e09_trend/ | CP-4 | §8 batteries (E07 degradation branch both modes; E08 ch.2–4 Wave-Out stub raises) | |
| apex/engines/e10_momentum/ · e11_regime/ · e12_temporal/ | CP-5 | §8 batteries + T-E11-K9 + T-E12-Windows + E07↔E12 integration + E11 live-gate-off default | |
| params/{universe_v1,risk_defaults_v1,setup_weights_v1,quality_weights_v1,toobit_wire_v1,e11_params_v4}.yaml | CP-1 (values §9.5/Ch.10/§2.1/Ch.16) | test_params_frozen_values (literal-by-literal; CP-5 re-asserts e11 vs §6) |  PASS(2026-09-12, tests/unit/test_cp1_foundations.py::TestParamsFrozenValues — literal-by-literal) |
| apex/fabric/{evidence,context,conflict}.py | CP-6 | SL-14 lifecycle+crosswalk · context weights .16/.12/.10/.08/.12/.10/.06/.06/.08/.06/.04/.02 + Q_min_setup .55 + vacuous-pass assert · conflict 4-output+7-invariants | |
| apex/pattern/{detect,fibonacci}.py | CP-6 | legacy-20 patterns + GF_SC_01/02 fire (re-derived values) + GF_SC_03..12 schema-only + in-repo fib (no network) | |
| apex/setup/{family_sf_fvg_sweep_rev,gates}.py | CP-6 | 13-gate boundary matrix ±1 unit + only-Wave-In-family + 140 cells + AC admission | |
| apex/playbook/pb_fvg_sweep_rev_a.py | CP-6 | X.4 exit precedence + AE.1 16-field template | |
| apex/forecast/logistic.py · apex/decision/pipeline.py | CP-6 | T-DR-003 + bootstrap-p0.5-paper-only + EU units + ranking key | |
| apex/risk/kernel.py | CP-6 | T_VETO ×14 + machine boundaries (100/50/25/30/15/8/12/7/3/60/40/20) + FROZEN_BOOTSTRAP literals + RSK-ERR-506 | |
| apex/execution/{fsm,toobit_adapter,toobit_map}.py | CP-7 | FSM matrix+E-EXEC-001 · adapter 5-ops+reconcile-first+T_ADAPTER_* · wire map exact (−1120/−1021/−1022/−1003/−2026, 1mo→1M) | |
| apex/ledger/store.py · apex/scheduler/clock.py | CP-7 | T-LR-001..003 + T_LEDGER + single-writer grep · scheduler order+semaphore4+drift-block+T_MONOTONE | |
| apex/telegram/{control_plane,signaling}.py + alerts (Ch.23) | CP-7 | screens+callbacks+busy-guard · rate buckets+dedup+idempotent · E-TELE-001..007 · Agg-only charting grep | |
| apex/ops/{watchdog,backup}.py | CP-8 | heartbeat-loss escalation + Gmail-CRITICAL-only isolation · T-RESTORE-001 tempdir drill | |
| apex/research/** (backtest/optimizer/promotion/adapter-conformance/bootstrap; ADR-P2-005) | CP-8 | T-AD-001/002, T-PKG-001, Z.8 re-derived, determinism double-run, red-line rejection suite, registry-38 + rejected-6-absent, YAML-immutability watch | |
| tests/unit/ · tests/integration/ · tests/fixtures/{gf_sc_01,gf_sc_02}.json | owning stage per file (fixtures: CP-6) | named in each row above |  PASS(2026-09-12, full suite 158 passed via scripts/run_all_tests.sh) |
| scripts/run_all_tests.sh | CP-1 | must run everything; CP-8 verifies from clean clone |  PASS(2026-09-12, tests/unit/test_cp1_foundations.py::test_run_all_tests_script + full run: 158 passed) |

Additive-file rule: any file outside §9.5's list traces to a DECISION_LOG ADR or a handoff DELIVERED line; the CP-8 closeout sweep reconciles both directions.

## Part II — AI.10 matrix (L18906–18975) + chapter acceptance ids → owning stage → result

| Test id | Owner | Result |
|---|---|---|
| T-DC-001..004 · T-PIT-001..004 · T-ID-001/002 · T-CL-001..003 · T-OM-001..003 · T-RS-001..003 · T-MON-001 | CP-1 | PASS(2026-09-12, tests/unit/test_catalog.py, test_identity.py, tests/integration/test_store_integration.py) |
| T-DR-001 (per-engine data-availability contract) | CP-1 (feature tier) + re-run by CP-2…CP-5 per engine | PASS(2026-09-12 feature tier, tests/unit/test_catalog.py::test_tdr_001_feature_replay_byte_identical; per-engine re-runs = CP-2…CP-5) |
| T-E01-001 · E01–E03 §8 batteries | CP-2 | |
| E04–E06 §8 batteries | CP-3 | |
| E07–E09 §8 batteries | CP-4 | |
| T-E11-K9 · T-E12-Windows · E10–E12 §8 batteries | CP-5 | |
| T-DR-002 (arbitration lineage) · GF_SC_01/02 · 13-gate matrix · T_VETO · T-DR-003 · RSK-ERR-506 | CP-6 | |
| T_MATCH · T_RECONCILE · T_LEDGER · T_ADAPTER_SUBMIT/DUPLICATE/LOST_ACK · T-LR-001..003 · T-MON-002 (FSM half) · E-EXEC-001 · T-FB-001..003 (runtime part) · E-TELE-001..007 · E-VAL-020 | CP-7 | |
| T-AD-001/002 · T-PKG-001 · T-RESTORE-001 · NFR harnesses (T-NFR-001..004 per ADR-P2-010) · §9.9 boxes · E-VAL-021/022 sweep re-run | CP-8 | |
| External gates AI.13 (G-TOOBIT-*, G-TARGET-DEVICE-*, G-CAPACITY-*, G-ADAPTER-*, G-RESTORE-*, G-PAPER-*, G-RISK-*, G-FALLBACK-*) | harness built by owning stage (CP-1/6/7/8); MEASUREMENTS = OWNER procedures; status recorded honestly (never agent-claimed) | |

## Part III — Per-stage requirement detail (each executor fills ONLY its section)

### CP-1 — Requirement | Blueprint ref | Component | Test evidence | Status

| Requirement | Blueprint ref | Component | Test evidence | Status |
|---|---|---|---|---|
| P1 | Ch.1 L1218–1221 (SBOM) | nine runtime pins exact; pytest dev-only; no python-dotenv | tests/unit/test_cp1_foundations.py::TestPackaging | PASS(2026-09-12) |
| P2 | §9.5 L20156–20213 (tree) | normative tree: all CP-1 files exist, non-empty, importable; no TODO/FIXME/stub sweep | tests/unit/test_cp1_foundations.py::TestNormativeTree | PASS(2026-09-12) |
| P3 | ADR-P2-013 | .gitignore hygiene (data/, *.sqlite3*, .env, __pycache__/, .pytest_cache/, dist/, build/) | tests/unit/test_cp1_foundations.py::test_gitignore_adr_p2_013 | PASS(2026-09-12) |
| CFG1 | §9.5-12 + §2.5 | nine env names EXACT (APEX_ENV, APEX_ALLOW_SIGNED, APEX_ECONOMIC_GATE_SIGNED, TOOBIT_API_KEY, TOOBIT_API_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID, TELEGRAM_WATCHDOG_CHAT_ID, APEX_SQLITE_PATH) | tests/unit/test_config.py::test_env_names_exact | PASS(2026-09-12) |
| CFG2 | §9.5-12 + G16 | stdlib .env parsing; real env never shadowed; SHADOW rejected; secrets masked; defaults RESEARCH/0/0/data/apex.sqlite3 | tests/unit/test_config.py (no-shadow, valid-environments, secrets-masked) | PASS(2026-09-12) |
| ERR1 | Ch.7 L14643–14671 | every Ch.7 row (23 codes) verbatim + WaveOutError + frozen Wave-Out list | tests/unit/test_errors.py::test_error_registry_ch7_complete + test_wave_out_list_frozen | PASS(2026-09-12) |
| BUS1 | §9.5-10 + AI.12 | in-process asyncio.Queue only; P0 synchronous; P1 dedicated lane; P2/P3 shared; ordering preserved | tests/unit/test_bus.py (p0 sync/ordered, p1 lane) | PASS(2026-09-12) |
| BUS2 | AI.8/AI.9 + Ch.23 | P0/P1 never dropped (evict oldest P3/P2, logged); P2/P3 drop-oldest QUEUE_OVERFLOW_DROP; raw queue 1000 no-backpressure | tests/unit/test_bus.py (p0 never dropped, evict-shared, raw queue) | PASS(2026-09-12) |
| ID1 | GLOBAL IDENTITY L4104–4158 + AI.3 | canonical_json: sorted keys, no whitespace, Decimal fixed-point string, datetime ...Z, NaN/Inf forbidden | tests/unit/test_identity.py::TestCanonicalJson | PASS(2026-09-12) |
| ID2 | GLOBAL IDENTITY + G11 | ONE uuid_v7 RFC 9562 (48-bit ms/ver7/rand_a/variant/rand_b); operational-only | tests/unit/test_identity.py::TestUuidV7 (shape, single-implementation grep) | PASS(2026-09-12) |
| ID3 | GLOBAL IDENTITY + §2.3 | snapshot_id = SHA256(canonical_json(payload)); envelope rules; scope>10/>14 BLOCK; created_at excluded | tests/unit/test_identity.py::TestSnapshot | PASS(2026-09-12) |
| ID4 | GLOBAL IDENTITY + G11 | as_of = max(availability_time); MISSING_REQUIRED_ARTIFACTS_QX / MISSING_AVAILABILITY_TIME_QX fail-closed | tests/unit/test_identity.py::test_governed_as_of_max_and_fail_closed | PASS(2026-09-12) |
| ID5 | AI.3 | content_id + replay_key determinism (T-PIT-002/003) | tests/unit/test_identity.py::TestContentId/TestReplayKey | PASS(2026-09-12) |
| DC1 | AI.4 | MarketObservation 10 fields + fail-fast validation order (T-DC-001/002) | tests/unit/test_catalog.py::TestTDC | PASS(2026-09-12) |
| DC2 | Ch.5 + L18185 | catalog.get result shape; statuses OK/MISSING/STALE/UNAVAILABLE/INVALID; unregistered→INVALID; future as_of→INVALID; 24-field EvidenceEvent | tests/unit/test_catalog.py::TestCatalogGetContract + tests/integration TestEvidenceContract | PASS(2026-09-12) |
| FB1 | §3.13 L14371–14382 | registry count == catalogue count (74); ATOM/MOLE/ORGN all non-empty; F74 full template; F73 complete | tests/unit/test_catalog.py::TestRegistryCompleteness | PASS(2026-09-12) |
| FB2 | §3.12 + ADR-P2-006 | 74 features registered as tier packages under apex/data_catalog/; exact full_ids; F49 REMOVED-slot; F56 always-UNAVAILABLE | tests/unit/test_catalog.py (f49/f56/exact ids) | PASS(2026-09-12) |
| FB3 | §3.12 operating rules | tier caches: ATOM never cached; MOLE 5 candles; ORGN 50+ LRU-100; ATOM failure halts pipeline | tests/unit/test_catalog.py::TestTierCacheRules + TestAtomFailureHaltsPipeline | PASS(2026-09-12) |
| FB4 | §3.12 + §2.2 | ATOM formulas implemented (body_ratio 6dp, upper/lower wick 6dp, close_position 4dp, volume_ratio 8dp SMA_20 on t−1, return_k 10dp, normalized_range 4dp, ATR_14, TR, SMA/EMA/RMA/Wilder, VWAP, OBV, RSI_14, z, slope, Hurst, Parkinson, GK, RS, theta_maxAge=100); unnamed-formula slots → UNAVAILABLE (ISSUE-CP1-004/011) | tests/unit/test_catalog.py (result shape, T-DR-001) + tests/unit/test_quality.py::TestNumerical22 | PASS(2026-09-12) |
| ST1 | Ch.4 L14383–14544 | 8 Data-Plane tables verbatim (names/columns/CHECK enums) | tests/integration/test_store_integration.py::TestDDLVerbatim::test_ch4_tables_and_columns | PASS(2026-09-12) |
| ST2 | Ch.5 L14545–14642 | raw_observation + bootstrap_progress verbatim + idx_raw_sym_tf_asof; WAL/FULL/FK/5000 pragmas | tests/integration/test_store_integration.py (ch5 + wal pragmas) | PASS(2026-09-12) |
| ST3 | AI.5 + §2.6 | raw_revision/raw_manifest append-only + hash chain (T-RS-001/002); 12-month rolling purge with retention_event audit (T-RS-003); ledger never purged | tests/integration/test_store_integration.py::TestRawStore | PASS(2026-09-12) |
| ST4 | AI.4 correction model | corrections append; original SUPERSEDED; lineage in raw_revision (T-CL-001..003) | tests/integration/test_store_integration.py::TestRawStore (cl_001/003) | PASS(2026-09-12) |
| IN1 | Ch.16 L16750–16936 | public endpoints ×6; wire maps (BTC-SWAP-USDT, 1mo→1M); 3×1s/2s/4s retry; OI failure→MISSING never 0; funding alert |0.001| | tests/unit/test_toobit_public.py | PASS(2026-09-12) |
| Q1 | §2.1 | 13 hard gates + 7 components + 4 vetoes + Q_min(tf) + Q_oi STALE=0.5 canonical | tests/unit/test_quality.py::TestVector21 | PASS(2026-09-12) |
| Q2 | §2.1 tables | Q_min / freshness / OI-lag / Q_raw weights / Q_thr copy-exact from params (never re-interpolated) + Q_window min-veto & exp-decay | tests/unit/test_cp1_foundations.py::test_quality_weights_copy_exact_21 + test_quality.py Q_window | PASS(2026-09-12) |
| Q3 | §2.2 | two-tier eps 1e-12/1e-8; ATR floor 1e-8; per-engine EPS table; ROUND_HALF_UP; digit plan; division guards; NaN/Inf→Q_formula_valid=0; -0→0 | tests/unit/test_quality.py::TestNumerical22 | PASS(2026-09-12) |
| Q4 | §2.3 | as_of=max(availability); missing availability fail-closed; MTF ALIGNED/PARTIALLY_ALIGNED/CONFLICTING/INSUFFICIENT; closed-only; deterministic snapshot_id | tests/unit/test_quality.py::TestPit23 | PASS(2026-09-12) |
| EB1 | AI.2/AI.11/AI.12 | FROZEN base: contract_version v4.0.0; lifecycle forward-only (T-MON-002); engine_id E01..E12; catalog-only access | tests/unit/test_base_contract.py (versioned/lifecycle/data-access) | PASS(2026-09-12) |
| EB2 | AI.3 + §2.2 + §9.5-9 | replay_key idempotency + cache invalidated on code_revision change; emission→24-field validation; Wave-Out plumbing; frozen EPS (E01 scaled variant) | tests/unit/test_base_contract.py (replay/emission/wave-out/eps) | PASS(2026-09-12) |
| PR1 | §9.5 L20228–20231 | universe_v1.yaml literals (symbols/timeframes/setup_timeframes/nightly 03:00–05:00) + Ch.5 table keys (ADR-P2-003) | tests/unit/test_cp1_foundations.py::test_universe_v1_literals | PASS(2026-09-12) |
| PR2 | §9.5-11 | risk_defaults_v1.yaml FROZEN_BOOTSTRAP numbers (0.005/0.25/0.03/0.06/4/ISOLATED/ONE_WAY/0.05/0.10/0.25/3/0.70) + Y.2 2/3/4/5 by TF group | tests/unit/test_cp1_foundations.py::test_risk_defaults_literals | PASS(2026-09-12) |
| PR3 | §9.5 + Ch.10 | setup_weights_v1.yaml 12 weights sum=1 + Q_min_setup 0.55 + gate7 0.85 + penalties 0.4/0.3 + SF_FVG_SWEEP_REV/PB_FVG_SWEEP_REV_A | tests/unit/test_cp1_foundations.py::test_setup_weights_literals | PASS(2026-09-12) |
| PR4 | §2.1 + §9.5 | quality_weights_v1.yaml Q_min/freshness/OI-lag/Q_raw/Q_thr tables copy-exact; Q_feature 0.5/0.3/0.2; Q_evidence rows 1m/1h/1d; λ=0.1 | tests/unit/test_cp1_foundations.py::test_quality_weights_copy_exact_21 | PASS(2026-09-12) |
| PR5 | Ch.16 + §9.5 | toobit_wire_v1.yaml SL-6 wire maps/paths copy-exact (base/header/recvWindow/symbol map/interval map/endpoints/forbidden/business codes/side map) | tests/unit/test_cp1_foundations.py::test_toobit_wire_literals | PASS(2026-09-12) |
| PR6 | §9.5 + ADR-P2-008 | e11_params_v4.yaml canonical (K 9 / theta_H 0.65 / lambda_ewma 0.94 / hyst 3 / dirichlet 0.1 / delay 48 / W_180d_H1 4320) | tests/unit/test_cp1_foundations.py::test_e11_params_literals | PASS(2026-09-12) |
| TS1 | AI.10 | T-DC/T-PIT/T-ID/T-CL/T-OM/T-RS/T-MON-001 + §2.x rules + DDL verbatim + import-chain — full suite 158 passed | scripts/run_all_tests.sh (full run) | PASS(2026-09-12) |
(minimum one row per: §2.1 component/table, §2.2 rule, §2.3 clause, each Ch.4/Ch.5 DDL block, each Ch.7 error row, identity clauses (canonical/uuid/snapshot/as_of), bus clause, config clause (9 env names), §3.12 per-tier group + §3.13 global rules, each §9.5 params YAML + frozen-number row)
### CP-2 / CP-3 / CP-4 / CP-5 — one row per engine §3 formula group, §5 schema, §6 params, §8 clause
(fill per stage; engine id prefix each row: `E0n|…`)
### CP-6 — one row per: SL-14 lifecycle rule, context weight/decay/threshold, conflict rule, pattern definition, gate 1–13, family AD/AC contracts, playbook X.4/X.6, forecast formulas, decision ranking/eligibility, each of 14 vetoes, each sizing-machine boundary, each §9.5 FROZEN_BOOTSTRAP number
### CP-7 — one row per: FSM transition group, wire-map row, adapter operation/error class, ledger mutation path, scheduler rule, telegram screen/callback, bucket/dedup/idempotency rule, alert policy row
### CP-8 — research capability per W/Z/AA section, ops per Ch.20 clause, plus CLOSEOUT SWEEP table: (tree conformance · completeness · numerics · PIT/identity single-source · config · secrets-history · docs) each with command + result
