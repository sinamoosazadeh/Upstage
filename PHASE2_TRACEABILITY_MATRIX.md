# APEX_GEN5 — PHASE 2 TRACEABILITY MATRIX (frozen blueprint ⇄ code ⇄ evidence) — Rev-3

Editing rules: Part I & Part II ownership rows are PRE-SEEDED by the plan — executors never change the CP column, only fill Result rows of their own CP (Result format `PASS(<date>, <test file>)`). Part III (per-CP detail rows) is written ONLY by the owning stage in its section. A row without a concrete test file name is not evidence. Blueprint refs = chapter/section + line anchor of `APEX_GEN5.md`. Stages: CP-1 foundation+fabric+base · CP-2 E01–E03 · CP-3 E04–E06 · CP-4 E07–E09 · CP-5 E10–E12 · CP-6 context chain + forecast/decision/risk · CP-7 execution/ledger/scheduler + telegram/alerts · CP-8 research/governance/ops + closeout.

## Part I — Normative tree file → owning stage → verifying test (from §9.5, lines 20156–20213; "create every file; do not rename")

| Tree file | Owner | Verifying test (owner fills) | Result |
|---|---|---|---|
| pyproject.toml · requirements.lock | CP-1 | test_cp1_foundations::test_packaging + test_sbom_pins_exact (nine pins; pytest dev-extra only; no python-dotenv) | |
| README.md (run procedure) | CP-1 skeleton → CP-7 final → CP-8 verified | test_cp8_closeout::test_readme_run_blocks | |
| .gitignore (ADR-P2-013) | CP-1 | test_import_graph + git status hygiene | |
| apex/__init__.py · apex/errors.py | CP-1 | test_cp1::test_error_registry_ch7_complete (every Ch.7 row) | |
| apex/bus.py | CP-1 | test_cp1::test_bus_p0_sync_and_bounds | |
| apex/config.py | CP-1 | test_cp1::test_env_names_exact_no_shadow + test_no_dotenv_bypass | |
| apex/identity/{canonical_json,uuid_v7,snapshot,hashes}.py | CP-1 | T-PIT-001..004 + T-ID-001/002 + test_uuid7_single_implementation_grep | |
| apex/data_catalog/contracts.py · catalog.py | CP-1 | T-DC-001/002 + registration API test | |
| apex/data_catalog/store/sqlite_store.py | CP-1 | T-RS-001..003, T-CL-001..003 + DDL verbatim-equivalence rows vs Ch.4 L14383–14544 / Ch.5 L14545–14642 | |
| apex/data_catalog/ingest/toobit_public.py | CP-1 | T-DC-003/004, T-OM-001..003 | |
| apex/data_catalog/{atomic,molecular,organismic,math,performance}/ + 74-feature registry (§3.12; additive tiers per ADR-P2-006) | CP-1 | §3.13 completeness suite (74==74, F49 absent-by-design, F56 UNAVAILABLE, unregistered-id hook, tier-cache rules) | |
| apex/quality/{vector,numerical,pit}.py | CP-1 | §2.1 seven hard gates + Q tables copy-exact · §2.2 two-tier eps + quantize + division guards · §2.3 as-of windows/MTF + T-PIT-003 | |
| apex/engines/base.py (frozen contract; streaming+idempotency; emission→24-field validation) | CP-1 | test_cp1_base_contract suite; later engine stages assert consumption, never edit | |
| apex/engines/e01_structure/ · e02_liquidity/ · e03_volume/ | CP-2 | each engine's FULL §8 battery + T-E01-001 + T-DR-001 re-run + fixtures | |
| apex/engines/e04_volatility/ · e05_fvg/ · e06_orderblock/ | CP-3 | §8 batteries (E04 ε=1e-12; E05 min_width 0.2; E06 evidence-consumption lint) | |
| apex/engines/e07_rtm/ · e08_wyckoff/ · e09_trend/ | CP-4 | §8 batteries (E07 degradation branch both modes; E08 ch.2–4 Wave-Out stub raises) | |
| apex/engines/e10_momentum/ · e11_regime/ · e12_temporal/ | CP-5 | §8 batteries + T-E11-K9 + T-E12-Windows + E07↔E12 integration + E11 live-gate-off default | |
| params/{universe_v1,risk_defaults_v1,setup_weights_v1,quality_weights_v1,toobit_wire_v1,e11_params_v4}.yaml | CP-1 (values §9.5/Ch.10/§2.1/Ch.16) | test_params_frozen_values (literal-by-literal; CP-5 re-asserts e11 vs §6) | |
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
| tests/unit/ · tests/integration/ · tests/fixtures/{gf_sc_01,gf_sc_02}.json | owning stage per file (fixtures: CP-6) | named in each row above | |
| scripts/run_all_tests.sh | CP-1 | must run everything; CP-8 verifies from clean clone | |

Additive-file rule: any file outside §9.5's list traces to a DECISION_LOG ADR or a handoff DELIVERED line; the CP-8 closeout sweep reconciles both directions.

## Part II — AI.10 matrix (L18906–18975) + chapter acceptance ids → owning stage → result

| Test id | Owner | Result |
|---|---|---|
| T-DC-001..004 · T-PIT-001..004 · T-ID-001/002 · T-CL-001..003 · T-OM-001..003 · T-RS-001..003 · T-MON-001 | CP-1 | |
| T-DR-001 (per-engine data-availability contract) | CP-1 (feature tier) + re-run by CP-2…CP-5 per engine | |
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
(minimum one row per: §2.1 component/table, §2.2 rule, §2.3 clause, each Ch.4/Ch.5 DDL block, each Ch.7 error row, identity clauses (canonical/uuid/snapshot/as_of), bus clause, config clause (9 env names), §3.12 per-tier group + §3.13 global rules, each §9.5 params YAML + frozen-number row)
### CP-2 / CP-3 / CP-4 / CP-5 — one row per engine §3 formula group, §5 schema, §6 params, §8 clause
(fill per stage; engine id prefix each row: `E0n|…`)
### CP-6 — one row per: SL-14 lifecycle rule, context weight/decay/threshold, conflict rule, pattern definition, gate 1–13, family AD/AC contracts, playbook X.4/X.6, forecast formulas, decision ranking/eligibility, each of 14 vetoes, each sizing-machine boundary, each §9.5 FROZEN_BOOTSTRAP number
### CP-7 — one row per: FSM transition group, wire-map row, adapter operation/error class, ledger mutation path, scheduler rule, telegram screen/callback, bucket/dedup/idempotency rule, alert policy row
### CP-8 — research capability per W/Z/AA section, ops per Ch.20 clause, plus CLOSEOUT SWEEP table: (tree conformance · completeness · numerics · PIT/identity single-source · config · secrets-history · docs) each with command + result
