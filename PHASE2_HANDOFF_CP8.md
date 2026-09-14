# PHASE2 HANDOFF — CP-8 → terminal record of the plan; consumed by the OWNER (and any later review phase)
Stage: CP-8 — Research/Governance (Ch.17,18,W/Z/AA) + Ops (Ch.20) + CLOSEOUT sweep + FINAL REPORT assembly
Rules (PROTOCOL P16): author = CP-8 executor (or its continuation session — state which, first line of STATUS). ≤400 lines, nine headings below in order. Successors read ONLY this file + their own prompt/law/checkpoint sections; interfaces listed here are the public contract they may code against. First STATUS line: `LAW-ACK: G1..G20 + P1..P21 read <UTC>`.

## STATUS
LAW-ACK: G1..G20 + P1..P21 read 2026-09-14T11:58:00Z

- **complete — the stage is fully closed; no CONTINUE-NEEDED item.** This file is the terminal record: there is no CP-9.
- Author: the CP-8 **executor session** (single session, author of every commit below).
- Board claim: `46b6ab5` `[CP-8] docs(board): CP-8 IN-PROGRESS — entry gate re-verified, blueprint hash re-checked`. Code commits, one per module (all green before the commit): `0957633` proxies → `96ef4b3` governance → `259df71` backtest → `ed025b2` promotion → `b257348` checkpoints → `bdda20c` optimizer → `06edb15` bootstrap → `a9d8e20` adapter_conformance → `5c87bf4` ops/watchdog → `0b20c09` ops/backup → `8470bd3` scripts/run_adapter_conformance → `41deb78` scripts/run_nfr_harness (+ the closeout commit carrying the board, MATRIX, DECISION_LOG and this file). **CP-8 code range = `0957633..41deb78`.**
- ENV NOTE (session pinned to `arena/01a09fcd-upstage`): everything is pushed to that branch (`46b6ab5..0b20c09` and `8470bd3`, `41deb78`, then the closeout commit); the owner merges with a **plain merge** (never squash), exactly as CP-3…CP-7; the stage is open as **PR #9** (main ← arena/01a09fcd-upstage).
- Suite: **2553 passed / 0 failed / 0 skipped**, executed **twice** in this session (`./scripts/run_all_tests.sh -q -p no:warnings`: 64.73 s and 65.67 s — identical counts, no nondeterminism finding) and once from a **fresh clone** of the branch (2553 passed, 71.18 s). CP-8's own share is **368 tests** (35+50+39+46+20+43+42+38+23+9+12+11).
- Environment: CPython 3.11.2 in `.venv/` at the repo root (`.venv` is not persisted by the sandbox; recreate it as in HOW-TO-RUN), Linux x86-64, the nine SBOM pins from `requirements.lock`, SQLite WAL, matplotlib Agg. No network was used anywhere: the venue is `tests/fake_toobit_responder.py` (a test double) and the adapters run on synthetic/self-derived fixtures.
- Blueprint integrity re-checked at entry: `sha256(APEX_GEN5.md) = 216bcc9e5f3e54c7567303bea7b642a9f5ccf482d2282d05dc78c2f7cb0fbd9e` (match); `PROMPT.md`/`APEX_GEN5.md` untouched; the deleted earlier attempt was never sought (ADR-P2-001/015).
- Budget: the session ends with a green push, an empty remaining-work ledger and no open executor item.

## DELIVERED
| file | purpose | blueprint section | rows into MATRIX Part III |
| --- | --- | --- | --- |
| `apex/research/__init__.py` | package doc + the research-plane red line stated at the boundary | ADR-P2-005 | R-CP8&#124;1 |
| `apex/research/proxies.py` | Ch.20 liquidity-proxy layer: **38 concepts = 25 L1 / 10 L2P / 3 L3P**, the six AA.5 formal rejections (provably absent), formula-bearing proxies, `NUMBA_USED=False`, `INCREMENTAL_ONLY=True` | Ch.20 AA.1–AA.7 (L17449–17560); §9.5-9 | R-CP8&#124;1–2 |
| `apex/research/governance.py` | SL-12 governance: 4 parameter classes, 3 tiers, the 34-row §17.1 governed-default table, `θ′ = Π_[L,U](θ+Δ)`, the 5-item change proposal (180-d PIT backtest / 30-d forward / OOS / board approval / reason), EC register (APPROVED-only), Sobol `S1/ST < 0.05` removal-candidate rule, the RED LINE package validator + `InjectionLedger` (T-PKG-001) | Ch.17 §17.1 (L16937–17022); W.5 | R-CP8&#124;3–4 |
| `apex/research/backtest.py` | deterministic PIT replay (next-bar-open fill, stop-first exit precedence, time stop, costs/slippage), metrics, **deflated Sharpe** (Acklam ppf), WFO 70/30, SplitMix64 Monte-Carlo, `cvar_bootstrap`, the seven stress scenarios, BTC buy-and-hold benchmark + paired z-test, `deterministic_double_run` | Ch.18 §18.1/§18.4 (L17023–17149); Z.9 | R-CP8&#124;5 |
| `apex/research/promotion.py` | Z.1–Z.9 + W.5: thesis registry, family pool (ATR-normalised, 10-symbol union), Wilson-95 lower-bound gate with the absolute floor of 30 trades **first**, Bayesian shrinkage `λ=n/(n+var)`, SPRT monitor with the four rollback actions, PBO, deflated-Sharpe band 0.5–1.0, the **re-derived Z.8 worked example**, the five-gate `evaluate_promotion` + `draft_package` | Ch.18 W.5 + Z (L17150–17283) | R-CP8&#124;6 |
| `apex/research/checkpoints.py` | W.4/W.6/W.8 research persistence: additive migrations **M201–M203**, WAL, resume-never-rewind cursor arithmetic, incomplete-cell listing, durable monitor log | Ch.18 W.4/W.6/W.8 (L17046–17149) | R-CP8&#124;7 |
| `apex/research/optimizer.py` | W.1–W.4/W.8 dual optimizer: disjoint Signal/Risk scopes, exhaustive-grid default (`FULL_GRID_THRESHOLD 500`), owner-only random search, Signal/Risk objectives with their constraints, the 03:00–05:00 UTC window + `LIVE_WORKLOAD_HALT` first, per-cell checkpointing, `write_suggestion()` that can only write `apex/research/params_suggestions/` | Ch.18 W.1–W.4/W.8 | R-CP8&#124;8 |
| `apex/research/bootstrap.py` | W.6/W.8 three-phase runner: hardware preflight (disk < 512 MB pause; battery < 15 % unplugged skip; < 5 % unplugged continuous pause; absent battery API never skips), the eight owner commands, −1003 backoff that never skips, page-cursor paging with `CURSOR_NOT_ADVANCING` failure, 24-h pause recheck, Phase-2 determinism veto, Phase-3 hand-off | Ch.18 W.6/W.8 | R-CP8&#124;9 |
| `apex/research/adapter_conformance.py` | AI.10 harness core: **T-AD-001** v2/v3→v4.0.0 translation over the read-only E05/E06 adapters (+ owner-export path, `real_data_gate` OPEN/UNVERIFIED per ADR-P2-009) and **T-AD-002** stable retry key + duplicate cache, registry rename map | AI.10 (L18906–18975); AI.2; ADR-P2-009 | R-CP8&#124;11 |
| `apex/ops/__init__.py` · `apex/ops/watchdog.py` | AI.9 watchdog: heartbeat 60 s × 3 misses ⇒ `HOST_DOWN` on the **send-only, CRITICAL-only Gmail channel first** (no read capability, no new env name, credential injected, absent credential ⇒ visible fail-closed), recovery log **M204** (hash-chained, append-only, reloaded intact after restart), fail-closed drive (protective legs preserved), 60 s/300 s timeout rows | AI.9 (L18813–18905); Ch.23 safeguards; Ch.17 §17.1 ops rows | R-CP8&#124;10 |
| `apex/ops/backup.py` | 15-minute SQLite online backup (WAL-safe, `PRAGMA integrity_check`), storage floor 15 % / >80 % STORAGE alert, restore with RTO ≤ 1800 s, chain validation through CP-1 store + CP-7 ledger writer, **T-RESTORE-001 drill** end-to-end in a tempdir, 90-day drill cadence, encryption request fails closed | AI.7; AI.5/AI.13 G-RESTORE-001; Ch.17 §17.1 | R-CP8&#124;10–11 |
| `scripts/run_adapter_conformance.py` | AI.10 harness runner: fixture hash seal checked **before any case runs**, all 19 golden cases against the real adapter + fake responder, T-AD-001/T-AD-002 in one verdict, exit codes 0/1/2 | AI.10; PHASE2_CHECKPOINTS §CP-8 | R-CP8&#124;11 |
| `scripts/run_nfr_harness.py` | AI.10 NFR harness: T-NFR-004 asserted in-process; T-NFR-001/002 measured and labelled SANDBOX-PARTIAL; T-NFR-003 labelled OWNER-VERIFY with the 60-minute owner gate named | AI.7; AI.10 rule 5; ADR-P2-010 | R-CP8&#124;11 |
| `tests/unit/test_research_*.py` (7 files, 275) · `tests/unit/test_ops_*.py` (2 files, 61) · `tests/unit/test_ai10_harness.py` (9) · `tests/unit/test_ai10_nfr_harness.py` (12) · `tests/integration/test_cp8_adapters.py` (11) | unit + integration proof of every row above | AI.10 id names | Part II CP-8 row |
| `PHASE2_TRACEABILITY_MATRIX.md` (Part I CP-8 rows, Part II CP-8 + external-gate rows, Part III CP-8 section with the **SW1–SW13 sweep table**) · `PHASE2_DECISION_LOG.md` §B/CP-8 (ISSUE-CP8-001…006) · `PHASE2_FINAL_REPORT.md` · this file · `PHASE2_CHECKPOINT_STATUS.md` | closeout record | PHASE2_CHECKPOINTS §CP-8 EXIT | — |

## INTERFACES
Everything below is the public contract a later review phase may code against. `CONTRACT_VERSION = "4.0.0"` in every CP-8 module. Nothing is invented: each row carries its blueprint cite in DELIVERED.

| module | class/function | signature | semantics | version |
| --- | --- | --- | --- | --- |
| `apex.research.proxies` | `registry_summary` | `() -> Dict[str, Any]` | `{total: 38, by_layer: {L1: 25, L2P: 10, L3P: 3}, rejected: 6, complete: True, ...}` | 4.0.0 |
| " | `assert_rejected_absent` | `(*, root: Optional[Path] = None) -> Dict[str, Any]` | scans the tree for the six rejected concept names; `{rejected_absent: True, probes_checked: 12, hits: []}` | 4.0.0 |
| " | `concept(id)` / `by_layer(layer)` | `(str) -> Dict` / `(str) -> List[Dict]` | registry rows (never a fabricated row: unknown id ⇒ `ProxyError`) | 4.0.0 |
| `apex.research.governance` | `GOVERNED_DEFAULTS`, `FORBIDDEN_FIELDS`, `SENSITIVITY_REMOVAL_THRESHOLD` | constants | the 34 §17.1 rows; the 14 veto names + owner-static fields; **0.05** | 4.0.0 |
| " | `constrained_update` | `(name, current, delta) -> Dict` | θ′ = Π_[L,U](θ+Δ) with `{proposed, projected, clamped, bounds}`; non-finite delta ⇒ `ResearchRedLineError` | 4.0.0 |
| " | `validate_proposal` / `validate_package` | `(Mapping) -> Dict` / `(ParameterPackage) -> Dict` | the five mandatory proposal items (180-d FLOOR, 30-d FLOOR); package red line (`red_line_clean`) | 4.0.0 |
| " | `assert_live_params_untouched` | `(package, target, *, research_root=None) -> None` | raises `LIVE_PARAMS_WRITE_FORBIDDEN` for any target inside `params/` (paths resolved first, `..` included); the relocation knob never weakens that | 4.0.0 |
| " | `InjectionLedger(path=None, *, research_root=None)` → `.inject(package, package_dir)` | `-> Dict` | T-PKG-001: first injection writes one suggestion; re-injection is a no-op (`already_injected: True`); restart-stable | 4.0.0 |
| " | `ECRegister` · `sensitivity_candidate(s1_over_st, threshold=0.05)` | `.add/.get` · `-> Dict` | APPROVED entries gain an active value; the Sobol rule marks candidates only, never removes | 4.0.0 |
| `apex.research.backtest` | `BacktestEngine(symbol, timeframe, *, fee, alpha_spread, max_hold, start_index, slippage_fn)` → `.run(bars, signal_fn)` / `.run_with_metrics(...)` | `-> Dict[str, Any]` | PIT window `bars[:index+1]`; next-bar-open fill; STOP before TARGET; `TIME_STOP`; costs = 2×fee + slippage | 4.0.0 |
| " | `walk_forward(n, *, train_fraction=0.70, oos_fraction=None)` · `evaluate_wfo(train, test)` | `-> Dict` | 70/30 (optionally carving OOS); PROMOTED requires OOS Sharpe > 1.0 ∧ PF > 1.2 ∧ MaxDD < 15 % | 4.0.0 |
| " | `monte_carlo(trades, *, paths=1000, seed)` · `cvar_bootstrap(returns, *, paths, seed)` · `stress_battery(returns)` · `apply_stress(name, returns)` | `-> Dict` | SplitMix64, seed-deterministic; 7 scenarios; `crisis_factor = 0.5` | 4.0.0 |
| " | `deflated_sharpe_ratio(...)` · `buy_and_hold(bars)` · `benchmark_outperformance(...)` · `deterministic_double_run(fn)` | `-> Dict` | trial-count deflation (1 trial ⇒ SR0 = 0); B&H net of fees; paired z-test; byte-identical double run | 4.0.0 |
| `apex.research.promotion` | `FamilyPool(family_id)` → `.add(trade)` · `family_pool_gate(pool)` | `-> Dict` | floor 30 **first** (`BELOW_ABSOLUTE_FLOOR_30`), then Wilson LB > p_breakeven (`WILSON_LOWER_BELOW_BREAKEVEN`); ATR risk-unit check | 4.0.0 |
| " | `wilson_gate(n, k, p_breakeven)` · `shrinkage_factor` · `shrink_cell_rate` | `-> Dict` | Wilson-95 lower bound; λ = n/(n+var); shrunk rate with `used_in_isolation: False` while small | 4.0.0 |
| " | `SPRTState(p0, p_min)` · `sprt_step` · `sprt_monitor` · `LiveFamilyMonitor` | `-> Dict` | LLR thresholds `log((1−α)/α)`; verdicts ACCEPT_H1 / REJECT_H1 / CONTINUE; halt ⇒ `HALT_AND_ROLLBACK` with four actions | 4.0.0 |
| " | `probability_of_backtest_overfitting(matrix, *, rank_below_median=0.5)` · `deflated_sharpe_gate(...)` | `-> Dict` | PBO over fold pairs; flagged when > 0.5; DSR gate accepts only thresholds inside [0.5, 1.0] | 4.0.0 |
| " | `z8_scenarios()` · `canonical_decision(state)` · `evaluate_promotion(candidate)` · `draft_package(**kw)` | `-> Dict` | re-derived Z.8 (A 27/42 → LB 0.4917 = ALLOWED; B_initial 11/18 → LB 0.3862 = below floor; B_3months 22/35 → LB 0.4634 = still blocked; B_6months 31/48 → LB 0.5044 = ALLOWED; every quoted/recomputed decision consistent); 5 gates; a blocked candidate is `REFUSED` | 4.0.0 |
| `apex.research.checkpoints` | `ResearchCheckpointStore(path=None)` (async ctx) → `.save_bootstrap/.load_bootstrap/.bootstrap_rows/.incomplete_bootstrap_cells/.save_optimizer/.load_optimizer/.optimizer_rows/.log_monitor/.monitor_rows/.applied_migrations` | async | M201–M203, WAL; cursor `MAX()` (never rewinds); bars additive; `PHASE_QX`/`OPTIMIZER_QX` fail closed | 4.0.0 |
| `apex.research.optimizer` | `ParameterRange(name, minimum, maximum, step)` · `ParameterGrid(ranges)` → `.size/.states()/.enumerate()/.random_search(budget, seed, owner_authorized)/.generate(...)` | `-> List[Dict[str, float]]` | full grid is the default; random search needs `owner_authorized=True` **and** a domain > 500 states, else `OWNER_AUTHORIZATION_REQUIRED_D3` | 4.0.0 |
| " | `OptimizerSchedule(start, end, continuous=False)` → `.in_window/.may_run/.set_continuous` · `DualOptimizer(schedule=None, checkpoint_store=None, suggestions_dir=None)` → `.run_run(...)/.write_suggestion(...)` | `-> Dict` | `LIVE_WORKLOAD_HALT` precedes the window check; `continuous on` is owner-gated; suggestions land only under the research directory | 4.0.0 |
| `apex.research.bootstrap` | `hardware_preflight(free_disk_mb, battery=None, continuous=False)` · `parse_battery_json(text)` · `BootstrapRunner(fetcher, ingest, store, cells, phase1_verifier=None, phase2_replay=None, now=None)` → `.command/.run_phase1/.run_phase2/.phase3_plan/.progress/.eta/.pending_cells/.health_recheck_required` | `-> Dict` | `PAUSE`/`SKIP_NIGHTLY`/`PROCEED` verdicts; eight owner commands; `ingest` is async (production `SQLiteStore.ingest_raw`) | 4.0.0 |
| `apex.research.adapter_conformance` | `t_ad_001(*, export_path=None)` · `t_ad_002(*, retries=100, submit=None)` · `translate_legacy(*, engine_id, payload, version)` · `stable_retry_key(**parts)` · `run_legacy_export(records)` · `rename_registry_entry(old)` | `-> Dict` | T-AD-001/T-AD-002 tokens; adapters are read-only (`read_only=True`); `export_path` absent ⇒ `EXPORT_PATH_ABSENT` | 4.0.0 |
| `apex.ops.watchdog` | `Watchdog(independent=None, telegram_plane=None, recovery_log=None, interval_seconds=60, miss_limit=3, now=None)` → `.heartbeat/.observe/.check/.enter_fail_closed/.resolve` | async where noted | 3 consecutive misses ⇒ `HOST_DOWN`; the independent send happens before the Telegram plane; `telegram_plane` is used via its public `check_heartbeat` only | 4.0.0 |
| " | `SendOnlyGmailChannel(credential_provider=None, transport=None, to_address="")` → `.send(OutboundMail)` | `-> Dict` | CRITICAL-only, `HOST_DOWN`/`FAIL_CLOSED` only; no read method; absent credential ⇒ `GmailChannelUnavailable` | 4.0.0 |
| " | `RecoveryLog(path=None)` → `.append/.rows/.head/.verify` · `fail_closed_entry(...)` · `watchdog_timeout(state, seconds_since_event)` | async where noted | M204; `verify()["intact"]` after a restart; timeout rows only for NORMAL (60 s) and RECOVERY (300 s) | 4.0.0 |
| `apex.ops.backup` | `SQLiteBackupManager(db_path, backup_dir, now=None)` → `.backup(label="auto", encrypt=False)` · `.integrity_check(path)` | `-> BackupResult` / `-> bool` | online backup + integrity check; `encrypt=True` ⇒ `ENCRYPTION_UNAVAILABLE_IN_SBOM` | 4.0.0 |
| " | `restore(*, backup_path, target_path, overwrite=False)` · `verify_restored_ledger(path)` · `restore_drill(*, workdir, records=25, rpo_limit_seconds=300)` · `storage_guard(*, free_fraction, used_fraction=None)` · `next_drill_due(*, last_drill_at, now=None)` | (async for `verify_restored_ledger`/`restore_drill`) | T-RESTORE-001 verdict with `mismatches`, `zero_data_loss`, RTO/RPO; floor/alert arithmetic | 4.0.0 |
| `scripts.run_adapter_conformance` | `main(argv=None)` | `-> int` | 0 green · 1 conformance failure · 2 fixture integrity failure (nothing runs) | — |
| `scripts.run_nfr_harness` | `run_harness(*, decisions=200, orders=100, minutes=1.0)` · `main` | `-> Dict` / `-> int` | `measured_in_bounds` + `owner_gates_open`; labels SANDBOX-PARTIAL / OWNER-VERIFY | — |

## DATA-CHANGES
Research-plane tables created by `apex/research/checkpoints.py` (additive, ADR-P2-003; the frozen CP-1 migration list is never touched):
`M201_bootstrap_progress` (`cell_id` PK, symbol, timeframe, phase CHECK(1,2,3), status CHECK(PENDING/IN_PROGRESS/PAUSED/COMPLETE/SKIPPED), cursor_ms CHECK(≥0), bars_ingested, oi_available, updated_at, payload_json) ·
`M202_optimizer_checkpoint` (`run_id`+`cell_id`+`optimizer` PK, optimizer CHECK(SIGNAL/RISK), status CHECK(…/LIVE_WORKLOAD_HALT), combination_index CHECK(≥0), best_value, best_params_json, sru_hash, updated_at) ·
`M203_research_monitor_log` (`log_id` PK, family_id, kind, verdict, stats_json, created_at).
Ops table created by `apex/ops/watchdog.py`: `M204_ops_recovery_log` (`log_id` PK, created_at, kind, reason, snapshot_id, recovery_state, payload_hash, parent_hash).
No existing table, column, YAML or DDL is altered; no data is written outside `apex/research/params_suggestions/` (created at first `write_suggestion`) and the operator's own SQLite path.

## TESTS
| test file | ids covered | result |
| --- | --- | --- |
| `tests/unit/test_research_proxies.py` (35) | AA.2–AA.5 (registry 38, six rejections, rejected-absent), AA.7 (incremental/Numba Wave-Out) | PASS(2026-09-14) |
| `tests/unit/test_research_governance.py` (50) | §17.1 classes/tiers/defaults, θ′ projection, proposal protocol, EC register, Sobol rule, RED LINE + `params/` write refusal, **T-PKG-001** | PASS(2026-09-14) |
| `tests/unit/test_research_backtest.py` (39) | §18.1/§18.4 PIT, fills, exits, metrics, DSR, WFO, Monte-Carlo, stress ×7, B&H benchmark, determinism double-run | PASS(2026-09-14) |
| `tests/unit/test_research_promotion.py` (46) | Z.1–Z.9 + W.5 incl. the re-derived **Z.8** and PBO 0.667 | PASS(2026-09-14) |
| `tests/unit/test_research_checkpoints.py` (20) | W.4/W.6/W.8, M201–M203, WAL, resume-never-rewind | PASS(2026-09-14) |
| `tests/unit/test_research_optimizer.py` (43) | W.1–W.4/W.8, grid default, owner-only random, window/halt, checkpointed resume, suggestion-only output | PASS(2026-09-14) |
| `tests/unit/test_research_bootstrap.py` (42) | W.6/W.8 preflight branches, owner commands, −1003 backoff, cursor law, 24-h recheck, Phase-2 veto, Phase-3 hand-off | PASS(2026-09-14) |
| `tests/unit/test_ops_watchdog.py` (38) | AI.9 heartbeat/timeout/fail-closed, Gmail CRITICAL-only isolation, recovery-log chain across restarts | PASS(2026-09-14) |
| `tests/unit/test_ops_backup.py` (23) | storage guard 15 %/>80 %, online backup + integrity, RTO, **T-RESTORE-001** drill, 90-day cadence | PASS(2026-09-14) |
| `tests/unit/test_ai10_harness.py` (9) | T-AD-001/T-AD-002 through the harness runner; fixture-seal tamper ⇒ exit 2 before any case | PASS(2026-09-14) |
| `tests/unit/test_ai10_nfr_harness.py` (12) | T-NFR-004 asserted; T-NFR-001/002/003 labels + owner-gate list | PASS(2026-09-14) |
| `tests/integration/test_cp8_adapters.py` (11) | T-AD-002 against the **real CP-7 adapter** + fake responder (100 retries ⇒ 1 venue POST, 99 cached, 0 signature violations); T-AD-001 synthetic/owner-export paths | PASS(2026-09-14) |
| full suite ×2 (this session) + fresh clone | all 43 AI.10 ids re-run | **2553 passed / 0 failed** each time |

## DEVIATIONS
- `ADR-P2-003 applied: additive handoffs` — this file follows the nine-heading template; predecessor entries were never rewritten.
- `ADR-P2-005 applied: research/ops paths` — `apex/research/**` and `apex/ops/{watchdog,backup}.py` are the authorized CP-8 write set (plus `scripts/` harnesses).
- `ADR-P2-009 applied: adapter conformance` — T-AD-001 runs synthetic self-checks over the real adapters and keeps `real_data_gate` OPEN/UNVERIFIED (0/100 legacy samples): no legacy data was invented.
- `ADR-P2-010 applied: sandbox-partial labels` — every sandbox number (latency, resource sample, restore drill) is labelled; target-device acceptance stays with the owner.
- `ADR-P2-013 applied: frozen .gitignore` — `.venv/` was deliberately **not** added to it and was never committed.
- No other deviation: the CP-8 write set is exactly the checkpoint's; no predecessor file was edited (zero corrective patches outside CP-8, see FINAL_REPORT §5).

## OPEN-ISSUES
Mirrored into `PHASE2_DECISION_LOG.md` §B `### CP-8` (full text there):
- `[ISSUE-CP8-001]` severity: MAJOR | status: CLOSED — the Ch.17 §17.1 example numbers (`budget_per_trade 1.0 %`, `k_attn 0.05`) disagree with the frozen `params/risk_defaults_v1.yaml` (`0.005`, `0.25`); the YAML wins at runtime, the divergence is reported (`doc_inconsistency`), never reconciled. **Owner question: confirm §9.5-11 supersedes the Ch.17 example.**
- `[ISSUE-CP8-002]` severity: INFO | status: CLOSED — Numba is Wave-Out (§9.5-9/AA.7-2); `NUMBA_USED = False`.
- `[ISSUE-CP8-003]` severity: MINOR | status: CLOSED — ISSUE-CP7-001 cites cases C-16/C-17 for the −1021/−2026 pins; they are **C-09/C-10** in the hash-locked fixture. Citation corrected here, predecessor entry untouched.
- `[ISSUE-CP8-004]` severity: MINOR | status: CLOSED — `APEX_DOTENV_PATH` is a documented 10th env name (a `.env` path pointer, never a credential). Kept under G4; **owner may retire it**.
- `[ISSUE-CP8-005]` severity: INFO | status: CLOSED — final dispositions for the five predecessor opens (CP1-004, CP1-005, CP2-006, CP2-016, CP4-005): four closed with evidence, two by explicit CP-8 decision, all with named tests.
- `[ISSUE-CP8-006]` severity: INFO | status: **ESCALATED-TO-OWNER** — the six owner-only questions are repeated verbatim (CP6-002, CP6-004, CP7-001, CP7-003, CP7-008, plus all AI.13 gates). No code change is blocked on them.

## HOW-TO-RUN
```bash
# 0. Environment (the sandbox does not persist .venv)
cd /path/to/repo
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock          # nine SBOM pins
.venv/bin/pip install pytest                        # dev only (README: pip install -e ".[tests]")

# 1. Full suite (must be green before anything else)
PYTHON=.venv/bin/python bash scripts/run_all_tests.sh -q -p no:warnings
#    expected: 2553 passed

# 2. CP-8 unit slices
.venv/bin/python -m pytest tests/unit/test_research_*.py tests/unit/test_ops_*.py -q   # 336 passed
.venv/bin/python -m pytest tests/unit/test_ai10_harness.py tests/unit/test_ai10_nfr_harness.py -q  # 21 passed
.venv/bin/python -m pytest tests/integration/test_cp8_adapters.py -q                  # 11 passed

# 3. AI.10 harnesses (runnable, no network)
.venv/bin/python scripts/run_adapter_conformance.py          # 19/19 + T-AD-001/002; exit 0
.venv/bin/python scripts/run_adapter_conformance.py --json    # machine verdict
.venv/bin/python scripts/run_nfr_harness.py                   # T-NFR-004 PASS + labelled probes
.venv/bin/python scripts/run_nfr_harness.py --minutes 60 --json   # the owner's on-device form

# 4. Closures and drills
.venv/bin/python - <<'PY'                                     # T-RESTORE-001 in a tempdir
import asyncio, tempfile; from apex.ops import backup as bk
print(asyncio.run(bk.restore_drill(workdir=tempfile.mkdtemp()))["passed"])
PY
.venv/bin/python - <<'PY'                                     # registry + rejected-absent
from apex.research.proxies import registry_summary, assert_rejected_absent
print(registry_summary()); print(assert_rejected_absent())
PY

# 5. The CP-8 closeout sweep (tree · completeness · numerics · identity · env · secrets)
#    SW1–SW13 are reproduced row-by-row in PHASE2_TRACEABILITY_MATRIX.md Part III §CP-8;
#    every row names the exact command and the observed result.
```

## REMAINING WORK LEDGER
none — the stage is fully closed; there is no successor stage. Every CP-8 RULES item and EXIT condition is met: registry 38 + rejected-6 absent, Z.8 re-derived, determinism double-run, T-AD/T-PKG/T-RESTORE/T-NFR harnesses executed, red-line suite green, watchdog + backup drills executed, the SW1–SW13 sweep table complete with commands and results, the full suite green **twice** (plus once from a fresh clone), `PHASE2_FINAL_REPORT.md` assembled with the compliance declaration, this handoff written, and the board boxes checked.

**Owner procedures that remain (they are NOT executor debt):**
1. Merge `arena/01a09fcd-upstage` into `main` with a **plain merge** (never squash).
2. Answer ISSUE-CP8-006's six questions (Ch.17 numbers, `CIRCUIT_OPEN`, −1021/−2026, verbatim literals vs a YAML revision, NULL-for-absent-money DDL, and whether `APEX_DOTENV_PATH` should be retired).
3. Supply a v2/v3 legacy export (≥100 samples) to close **G-ADAPTER-001** (`--legacy-export`).
4. Run the target-device acceptance measurements: **T-NFR-001/002/003** (60-minute run, 30 % headroom), **G-TARGET-DEVICE-001**, **G-CAPACITY-001/002**.
5. Run the venue gates **G-TOOBIT-001/002/003** and the PAPER window gates **G-PAPER-001/002**, **G-RISK-001**, **G-FALLBACK-001**, **G-LEDGER-001**, plus the production-volume **G-RESTORE-001** drill.
6. Perform the Telegram on-device manual smoke (no message was ever sent by an agent).
7. Tick the board's owner closure block (the only non-agent check on the board).
