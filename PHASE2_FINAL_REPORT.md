# APEX_GEN5 — PHASE 2 FINAL REPORT (assembled by the CP-8 executor at closeout)

Structure preserved from `PROMPT.md` §18 (Final Engineering Report); every row
below cites an executed command, a green test or a named artifact. Numbers are
measurements of **this repository in this sandbox** unless a row says
otherwise; every external gate is an owner procedure and is never claimed.

- Date of assembly: **2026-09-14** (UTC)
- Branch / commits: `arena/01a09fcd-upstage` — board claim `46b6ab5` + twelve code commits
  **0957633..41deb78** + the docs/closeout commit at branch HEAD (per-module list in §1, full
  list in `PHASE2_HANDOFF_CP8.md` §STATUS)
- Blueprint: `APEX_GEN5.md`, sha256 `216bcc9e5f3e54c7567303bea7b642a9f5ccf482d2282d05dc78c2f7cb0fbd9e`
  (re-verified at CP-8 entry — match)
- Suite: **2553 passed / 0 failed / 0 skipped**, executed **twice** in this
  session (64.73 s and 65.67 s) and once from a **fresh clone** (71.18 s)

---

## 1. Repository Report

**Final structure.** The §9.5 normative tree (APEX_GEN5 L20156–20213, 61
entries) is complete: **61/61 paths present and non-empty, every package
directory carries `__init__.py`, 0 missing / 0 empty** (sweep row SW1).
Tracked files: **202** — 96 `apex/**` modules, 59 `tests/**` modules, 6
`params/*.yaml`, 4 scripts, 18 control/handoff documents.

**Additive files (86 outside the tree, all attributable — SW13):** 33
`__init__.py` markers; 6 additive feature modules
(`apex/data_catalog/{atomic,molecular,organismic,math,performance}/features.py`,
`apex/forecast/registry.py`; ADR-P2-006 additive tiers); 10 CP-8 modules
(`apex/research/*` per ADR-P2-005, `apex/ops/__init__.py`, `apex/ops/watchdog.py`
+ `backup.py` are in-tree); 4 scripts (`run_all_tests.sh`, `run_apex.py`, the two
CP-8 harness runners); `.gitignore` (ADR-P2-013); 2 test-support files
(`tests/conftest.py`, `tests/fake_toobit_responder.py`); 13 fixtures (12 engine
golden files + the CP-7 hash-locked conformance fixture); 18 Phase-2
control/handoff documents. **No orphan file.**

**Files created per stage (from TRACEABILITY Part I + handoffs).**

| Stage | Delivered surface | Suite at stage end |
|---|---|---|
| CP-1 | `apex/{__init__,errors,bus,config}.py`, `apex/identity/*` (4), `apex/data_catalog/*` + additive feature tiers, `apex/quality/*` (3), `apex/engines/base.py`, 6 `params/*.yaml`, packaging, `.gitignore` | 158 passed |
| CP-2 | `e01_structure`, `e02_liquidity`, `e03_volume` engines + fixtures; 147 CP-2 tests | 305 passed |
| CP-3 | `e04_volatility`, `e05_fvg`, `e06_orderblock` + fixtures; 176 tests | 481 passed |
| CP-4 | `e07_rtm`, `e08_wyckoff`, `e09_trend` + fixtures; 245 tests | 726 passed |
| CP-5 | `e10_momentum`, `e11_regime`, `e12_temporal` + fixtures; 322 tests | 1048 passed |
| CP-6 | `apex/fabric/*`, `apex/pattern/*`, `apex/setup/*`, `apex/playbook/*`, `apex/forecast/{logistic,registry}.py`, `apex/decision/pipeline.py`, `apex/risk/kernel.py`; 502 tests | 1550 passed |
| CP-7 | `apex/execution/*`, `apex/ledger/store.py`, `apex/scheduler/clock.py`, `apex/telegram/*`, `scripts/run_apex.py`, `tests/fake_toobit_responder.py`, the 19-case conformance fixture; 635 tests | 2185 passed |
| CP-8 | `apex/research/*` (9 modules), `apex/ops/{__init__,watchdog,backup}.py`, `scripts/run_adapter_conformance.py`, `scripts/run_nfr_harness.py`, 10 test modules; **368 tests** | **2553 passed** |

**Major modules (one line each, from the eight handoffs + this session's runs).**

- `apex/config.py` — frozen nine env names, `.env` fill with no-shadow, six YAML loaders; green.
- `apex/identity/*` — single `canonical_json`, `uuid_v7`, `canonical_snapshot_id`, `replay_key`; green (single-source sweep SW4).
- `apex/data_catalog/*` — DDL verbatim-equivalence, append-only store, 74-slot registry (F49 removed-by-design, F56 UNAVAILABLE); green.
- `apex/engines/*` — 12 engines on the frozen base contract, each with its §8 battery; green.
- `apex/fabric|pattern|setup|playbook|forecast|decision|risk` — the decision chain, 14 vetoes, RSK-ERR-506 ratchet; green.
- `apex/execution|ledger|scheduler|telegram` — 5-operation adapter, single-writer ledger, 140-cell scheduler, alert policy; green.
- `apex/research/*` — new this stage: proxies, governance, backtest, promotion, checkpoints, optimizer, bootstrap, adapter conformance; green (368 tests).
- `apex/ops/*` — new this stage: heartbeat watchdog with the CRITICAL-only send-only Gmail channel, SQLite backup + restore drill; green.

---

## 2. Implementation Report

| Subsystem | Purpose | Location | Status | Integration state |
|---|---|---|---|---|
| Foundation, Feature Fabric, Engine Base (CP-1) | contracts, identity, store, quality gates, frozen base | `apex/identity`, `apex/data_catalog`, `apex/quality`, `apex/engines/base.py` | COMPLETE | frozen surfaces; every later stage consumes, never patches (grep-verified) |
| Engines E01–E03 (CP-2) | structure / liquidity / volume | `apex/engines/e01..e03` | COMPLETE | feed the fabric via 24-field evidence events; T-DR-001 re-runs per engine |
| Engines E04–E06 (CP-3) | volatility / FVG / order block | `apex/engines/e04..e06` | COMPLETE | E04 `atr_series` → E05 Gate_D ∧ E06 context; consumption lint enforced |
| Engines E07–E09 (CP-4) | RTM / Wyckoff / trend | `apex/engines/e07..e09` | COMPLETE | E07 E12-both-modes inherited and re-tested by CP-5 |
| Engines E10–E12 (CP-5) | momentum / regime (K=9) / temporal | `apex/engines/e10..e12` | COMPLETE | E11 live gate default OFF; E12 is the temporal authority |
| Context chain + Forecast/Decision/Risk (CP-6) | SL-14 fabric, patterns, 13 setup gates, playbook, logistic forecast, P/U/C, 14 vetoes | `apex/fabric`, `apex/pattern`, `apex/setup`, `apex/playbook`, `apex/forecast`, `apex/decision`, `apex/risk` | COMPLETE | hands the CP-6 proposal + adjudication to CP-7's FSM |
| Execution/Ledger/Scheduler + Telegram (CP-7) | reconcile-first FSM, adapter, single-writer ledger, 140-cell scheduler, alerts/control plane | `apex/execution`, `apex/ledger`, `apex/scheduler`, `apex/telegram`, `scripts/run_apex.py` | COMPLETE | the paper loop runs end-to-end on the fixture clock + fake responder |
| Research + Governance + Ops (CP-8) | W/AA/Z research plane, SL-12 governance, watchdog, backup | `apex/research/*`, `apex/ops/*`, `scripts/run_{adapter_conformance,nfr_harness}.py` | COMPLETE | consumes the CP-7 adapter seam and the CP-1 store; **writes nothing outside `apex/research/params_suggestions/`** |

---

## 3. Engine Report (E01–E12)

All twelve engines are implemented against the frozen `apex/engines/base.py`
contract, emit the 24-field evidence schema, and carry their full §8 battery
(replay, no-future-leak, ablation, Wilson calibration, redundancy,
serialization). Formula groups and parameter tables were verified
literal-by-literal by each engine's own test module; sources: the CP-2…CP-5
handoffs and TRACEABILITY Parts I–III.

| Engine | Implementation | Formula groups | §8 battery |
|---|---|---|---|
| E01 Structure | COMPLETE | BOS/CHoCH/displacement + fixed Williams k=2 (dynamic k = Wave-Out) | 50-candle v4.0.0 schema (T-E01-001) + GF fixtures + T-DR-001 |
| E02 Liquidity | COMPLETE | sweep/wick/pool five-prerequisite model, ISR levels | GF_LIQ_001–012 |
| E03 Volume | COMPLETE | OBV/volume phases, six-phase classification | 12 fixtures + Phase 67/79/80/88 quotes |
| E04 Volatility | COMPLETE | ATR/ATR-percentile, regime ladder, ε=1e-12 | F01–F12 re-derived (66 tests) |
| E05 FVG | COMPLETE | gates A–D, classification tree, salience, merge/lifecycle | 10 fixtures + case study (49 tests) |
| E06 OrderBlock | COMPLETE | origin/disp/context, Q0–Q4 ladder, lifecycle, breaker | 12 fixtures + consumption lint (53 tests) |
| E07 RTM | COMPLETE | PO3/raid/sequence, E12 temporal windows (both modes) | 15 fixtures + UTC windows (83 tests) |
| E08 Wyckoff | COMPLETE | three laws, phase matrix, six-parameter events; encyclopedia ch. 2–4 = Wave-Out | 12 fixtures (74 tests) |
| E09 Trend | COMPLETE | EMA structure, ADX/AD-line, multi-TF stack | 11 fixtures (65 tests) |
| E10 Momentum | COMPLETE | ROC/RSI-family, divergence, statistics | GF01–GF17 (63 tests) |
| E11 Regime | COMPLETE | softmax rule tree, **K=9** (T-E11-K9), hysteresis | GF_01–GF_18 (78 tests) |
| E12 Temporal | COMPLETE | UTC activity windows, phase rules, DST stability | GF01–GF12 + E07 integration (165 tests) |

Validation status for all twelve: **§8 battery PASS**; T-DR-001 re-run per
engine and once per shared window in the four integration modules.

---

## 4. Runtime Report

| Item | Result | Evidence |
|---|---|---|
| PAPER boot on the fixture clock | `boot_state=READY`, zero orders before READY, startup reconciliation 0.00 delta | `tests/integration/test_cp7_paper_loop.py` (33 tests); clean-clone `demo` exit 0 |
| Whole-loop PAPER demo (no network, no capital) | READY → ACK → PROTECTED → MANAGED → CLOSED/OUTCOME → RECONCILED; ledger 11 records, chain intact, 0 signature violations | clean-clone run: exit 0 |
| Real boot without credentials | **DEGRADED, exit 2** (clock sync UNAVAILABLE — never assumed), no broker call before RECONCILING | clean-clone run |
| Alert-policy self-check without a token | **exit 2 with `E-TELE-001`** — the trading loop is unaffected | clean-clone run |
| Scheduler loop | 140-cell grid, semaphore peak ≤ 4, HTF last-closed only, leverage = min over ALL caps | `test_scheduler_clock.py` (73) + loop suite |
| Watchdog heartbeat | 60 s cadence, 3 consecutive misses ⇒ `HOST_DOWN` on the independent channel **before** the Telegram plane; CRITICAL-only Gmail; recovery log hash-chained and reloaded intact after a restart | `tests/unit/test_ops_watchdog.py` (38) |
| Fail-closed drill | protective legs preserved, ENTRY → `CANCEL_PENDING`, no new entry/capital, ladder climb disabled, 60 s/300 s timeout rows | `test_ops_watchdog.py::TestFailClosedDrive` |
| Restore drill (T-RESTORE-001) | backup → restore in a tempdir: 25 records, chain intact before+after, **0 mismatches**, RTO within 1800 s | `tests/unit/test_ops_backup.py::TestRestoreDrillT001` |
| Determinism | research double-run byte-identical; the CP-6/CP-7 chain reproduces proposal ids and P/U/C; the paper loop is deterministic over two runs | `test_research_backtest.py::TestDeterminism`, `test_context_to_trade_paper.py::TestDeterminism`, loop suite |
| Telegram transport | implemented (aiogram pin), charts Agg-only in-memory, zero display calls; **manual on-device smoke = owner-pending** | `test_telegram_signaling.py` (71) + `test_telegram_control_plane.py` (102) |

---

## 5. Testing Report

**Executed.** Full suite twice in this session — **2553 passed / 0 failed /
0 skipped** (64.73 s, 65.67 s) — plus once from a fresh clone (2553 passed,
71.18 s) and repeatedly at module granularity during the build.

| Suite run | Result | Notes |
|---|---|---|
| Session run 1 | 2553 passed in 64.73 s | includes the 368 CP-8 tests |
| Session run 2 | 2553 passed in 65.67 s | identical counts ⇒ **no nondeterminism finding** |
| Fresh clone (branch `arena/01a09fcd-upstage`, 41deb78) | 2553 passed in 71.18 s | README commands executed with their documented exit codes |
| Closeout-tree run (this PR's head, docs-only diff) | 2553 passed in 66.65 s | re-confirms the green state at the commit that carries this report |
| CP-8 module slice | 368 passed in 3.91 s | 11 test modules |

**CP-8 test inventory (368 tests):** `test_research_proxies.py` 35 ·
`test_research_governance.py` 50 · `test_research_backtest.py` 39 ·
`test_research_promotion.py` 46 · `test_research_checkpoints.py` 20 ·
`test_research_optimizer.py` 43 · `test_research_bootstrap.py` 42 ·
`test_ops_watchdog.py` 38 · `test_ops_backup.py` 23 ·
`test_ai10_harness.py` 9 · `test_ai10_nfr_harness.py` 12 ·
`tests/integration/test_cp8_adapters.py` 11.

**Corrective patches.** No predecessor file was modified (zero corrective
patches outside CP-8's own write set). Five defects were found while the CP-8
modules were still uncommitted, each fixed together with the test that exposed
it; every fix is inside its module's first commit, so no red state ever entered
git history. The fixes (all verifiable in the committed source):

| Module | Defect found during the build | Fix now in the tree | Final |
|---|---|---|---|
| `promotion.FamilyPool.add` | the ATR-normalised risk unit was missing, so a pool could union trades whose R-multiples were not comparable | `ATR_NORMALIZATION_QX` check on the trade's ATR/risk unit at `promotion.py:133` | 46 passed |
| `watchdog.RecoveryLog.open()` | a restart restored the rows but not the validated chain | the log is reloaded and re-verified (`verify()["intact"]` after reopen) | 38 passed |
| `backup.integrity_check` | a non-database file must be *reported*, not raised | `sqlite3.DatabaseError` ⇒ `False` (documented at `backup.py:145`) | 23 passed |
| `optimizer` suggestion guard | validation pointed at the module's real suggestions directory, which breaks relocated runs | the guard takes a relocatable `research_root` (`optimizer.py:436/451`) while the `params/` refusal stays absolute | 43 passed |
| `bootstrap.pending_cells()` | never-checkpointed cells were invisible in "what is left" | `pending_cells()` counts any cell not COMPLETE/SKIPPED as pending (`bootstrap.py:337–345`) | 42 passed |

**AI.10 id → test mapping (all 43 ids).** The CP-8-owned ids were executed and
their bodies read in this session; the CP-1…CP-7 ids are re-run by the two full
suites and are recorded in TRACEABILITY Part II with the node that carries
them.

| AI.10 id | Owning stage | Test (executed; full suite green) |
|---|---|---|
| T-DC-001..004 | CP-1 | `tests/unit/test_catalog.py` + `tests/integration/test_store_integration.py` (incl. T-DC-004 never OI=0) |
| T-PIT-001..004 | CP-1 | `tests/unit/test_identity.py` (canonical/byte-identical/content_id/replay_key/snapshot_id) |
| T-DR-001..003 | CP-1/2–5/6 | per-engine re-runs + `tests/integration/test_context_to_trade_paper.py::TestDeterminism` |
| T-ID-001/002 | CP-1 | `tests/unit/test_identity.py` (UUIDv7 monotonic, lineage) |
| T-CL-001..003 | CP-1 | `tests/unit/test_catalog.py` (SUPERSEDED/revision/cascade) |
| T-OM-001..003 | CP-1 | `tests/unit/test_catalog.py` (state machine, OI-missing blocking) |
| T-E01-001 | CP-2 | `tests/unit/test_e01_structure.py::TestTE01001Schema` |
| T-E11-K9 / T-E12-Windows | CP-5 | `test_e11_regime.py::TestTE11K9` / `test_e12_temporal.py::TestTE12Windows` |
| T-AD-001 / T-AD-002 | **CP-8** | `tests/integration/test_cp8_adapters.py` (**body read**) + `scripts/run_adapter_conformance.py` |
| T-RS-001..003 | CP-1 | `tests/integration/test_store_integration.py` |
| T-LR-001..003 | CP-7 | `tests/unit/test_ledger_store.py::TestTLR001/002/003` |
| T-MON-001 / T-MON-002 | CP-1 / CP-7 | `test_catalog.py` (monotonic quality) / `test_execution_fsm.py::TestTMon002` |
| T-FB-001..003 | CP-7 + **CP-8** | `test_execution_fsm.py` (fail-closed, startup reconciliation) + `test_ops_watchdog.py::TestFailClosedDrive` (**body read**) |
| T-NFR-001..004 | **CP-8** | `scripts/run_nfr_harness.py` + `tests/unit/test_ai10_nfr_harness.py` (**body read**; 004 asserted, 001–003 labelled) |
| T-TOOBIT-001/002 | owner gates | harness = `scripts/run_nfr_harness.py` owner-gate list (venue measurements are **owner procedures**) |
| T-RESTORE-001 | **CP-8** | `tests/unit/test_ops_backup.py::TestRestoreDrillT001` (**body read**) |
| T-PKG-001 | **CP-8** | `tests/unit/test_research_governance.py::TestInjectionLedger` (**body read**) |

**AI.12 directive mapping (Phase 7 + Phase 2 rows that CP-8 owns).**
Research & Backtest (backtest engine / WFO / Monte-Carlo / stress tools; “no
synthetic data”, “all backtests cited with date+parameters”) →
`apex/research/backtest.py` + `tests/unit/test_research_backtest.py` (the
engine never invents a statistic: a caller must supply the signal function and
the fixture data). Parameter Package Promotion (T-PKG-001, idempotent packages,
no ad-hoc tweaks) → `apex/research/governance.py`
(`validate_package`, `InjectionLedger`). Adapters (read-only v2/v3→v4.0.0) →
`apex/research/adapter_conformance.py`. Backup/restore (Phase 2 dependency) →
`apex/ops/backup.py`. All four are executed in this session's suites.

**Honest-fail list:** none — no failing or skipped test exists at closeout.
**Harness-open list (owner measurements, not failures):** T-NFR-001/002/003 on
the target device, T-TOOBIT-001/002, G-ADAPTER-001 (0/100 legacy samples),
G-PAPER-*/G-CAPACITY-*/G-RISK-*/G-FALLBACK-*/G-LEDGER-*/G-TARGET-DEVICE-* —
see §7.

---

## 6. Deployment Report

**Required environment.** Termux-first Android device; Python 3.11; the nine
frozen SBOM pins installed from `requirements.lock` (12-line lock = pins +
header); **no `python-dotenv`, no Numba, no PostgreSQL, no networked bus** —
all Wave-Out items absent (verified by the module/import sweeps).

**Installation (README, verbatim):**
```bash
pip install -r requirements.lock
pip install -e ".[tests]"   # developers only
```

**Final run commands (README §Run).** Nine env names → `python scripts/run_apex.py
grid|demo|boot|alerts` → `./scripts/run_all_tests.sh -q`; CP-8 adds
`python scripts/run_adapter_conformance.py` and
`python scripts/run_nfr_harness.py [--minutes N]`.

**Clean-clone verification (this session, label SANDBOX).** Fresh clone of
`arena/01a09fcd-upstage` → `python3 -m venv .venv` → `pip install -r
requirements.lock` (pins import OK) → `bash scripts/run_all_tests.sh -q`
⇒ **2553 passed / 71.18 s**; `grid` exit 0; `demo` exit 0 (READY, chain intact,
0 signature violations); `boot` (no credentials) exit **2 DEGRADED**; `alerts`
(no token) exit **2 `E-TELE-001`**; `run_adapter_conformance.py` 19/19 exit 0;
`run_nfr_harness.py` MEASURED_IN_BOUNDS.

**Device row (ADR-P2-010):** every number above is a **sandbox** measurement.
The target-device installation and its acceptance runs are **owner procedures**
(§7, G-TARGET-DEVICE-001 / G-CAPACITY-001/002).

---

## 7. External Gates Ledger (AI.13)

No gate below is marked CLOSED by this executor: an agent may build harnesses
and record measurements, but AI.13's evidence requirements (venue snapshots,
target-device runs, PAPER windows) belong to the owner.

| Gate | Harness in-repo | Executed in-sandbox | Label | Status | Owner procedure |
|---|---|---|---|---|---|
| G-TOOBIT-001 (listing) | `scripts/run_nfr_harness.py` owner-gate list + `apex/execution/toobit_map.py` Core-10 map | no venue call made | — | **OPEN/UNVERIFIED** | one-hour timestamped snapshot per symbol, 1 h before deployment |
| G-TOOBIT-002 (depth > 500k USDT) | same | no | — | **OPEN/UNVERIFIED** | REST `/depth` snapshot + hash per symbol |
| G-TOOBIT-003 (rate headroom > 120 req/s) | `apex/execution/toobit_adapter.py` token bucket (in-repo) + `scripts/run_nfr_harness.py` | bucket laws asserted; no venue load test | — | **OPEN/UNVERIFIED** | 10-minute production-like load run |
| G-TARGET-DEVICE-001 | — | no | — | **OPEN/UNVERIFIED** | record device model/OS/compiler |
| G-CAPACITY-001 (p95 ≤ 400 ms) | `scripts/run_nfr_harness.py` (`--decisions`) | yes — sandbox p95 **0.74 ms** | SANDBOX-PARTIAL | **OPEN/UNVERIFIED** | 1000+ decisions on the target device with 30 % headroom |
| G-CAPACITY-002 (CPU < 20 %, heap < 400 MB, 60 min) | `scripts/run_nfr_harness.py --minutes` | short sample only (CPU 0.08 %, RSS 25.3 MB) | OWNER-VERIFY | **OPEN/UNVERIFIED** | 60-minute steady-state on-device run |
| G-ADAPTER-001 (100 legacy samples) | `apex/research/adapter_conformance.py` + `scripts/run_adapter_conformance.py` | synthetic self-checks PASS; **0/100 real samples** | — | **OPEN/UNVERIFIED** (ADR-P2-009) | supply a v2/v3 export; the harness then reports translated/failed counts |
| G-RESTORE-001 | `apex/ops/backup.py` (`restore_drill`) | yes — tempdir drill, 0 mismatches, RTO within 1800 s | SANDBOX-PARTIAL | **OPEN/UNVERIFIED** | production-volume backup → restore ≤ 30 min, weekly |
| G-PAPER-001 (10-day replay) | paper loop + `scripts/run_apex.py demo` | loop demo green; no 10-day data set in-repo | — | **OPEN/UNVERIFIED** | 10-day PAPER replay vs deterministic replay, delta 0 |
| G-PAPER-002 (5-day drift/uptime) | drift block + clock tests | drift-block path green; no 5-day run | — | **OPEN/UNVERIFIED** | 5-day continuous PAPER run, 5-min clock snapshots |
| G-RISK-001 (veto autonomy, 20 scenarios) | `apex/risk/kernel.py` + `tests/unit/test_risk_kernel.py` (14 vetoes, order + boundaries) | yes (unit + chain) | — | **OPEN/UNVERIFIED** | 20 forced-proposal veto scenarios on the owner's system |
| G-FALLBACK-001 (fail-closed drill < 5 s) | `apex/ops/watchdog.py` + FSM fail-closed paths | yes (unit) | — | **OPEN/UNVERIFIED** | inject corruption/lineage loss on the owner's system |
| G-LEDGER-001 (overwrite rejected) | `apex/ledger/store.py` + `tests/unit/test_ledger_store.py::TestTLedger` | yes | — | **OPEN/UNVERIFIED** | SQL-level UPDATE attempt on the production ledger |

**Release states (AI.13).** `DOCUMENT_COMPLETE` ✓ · `CODING_READY` ✓ (2553
green, twice + fresh clone) · `PAPER_READY` **harness-ready / owner window
pending** · `LIVE_ELIGIBLE` ✗ (all AI.13 gates above) · `PUBLIC_RELEASE_READY` ✗.

---

## 8. Open-Item Dispositions (DECISION_LOG)

Full text in `PHASE2_DECISION_LOG.md` §B `### CP-8`.

| Issue | Disposition | Evidence |
|---|---|---|
| ISSUE-CP1-004 | **CLOSED-with-evidence** | CP-2/CP-3 supplied the chapter formulas; remaining §3.12 slots stay UNAVAILABLE by design — `test_catalog.py::TestRegistryCompleteness`, E02/E03 suites |
| ISSUE-CP1-005 | **CLOSED-with-evidence** | the missing producers (E12, fabric) now exist; AI.6 permission model keeps context-gated features UNAVAILABLE only while data is absent — `TestTE12Windows`, `test_fabric_context.py`, `TestTierCacheRules` |
| ISSUE-CP2-006 | **CLOSED-by-CP-8-decision** | the six `params/*.yaml` stay the only YAML set; a seventh file would require patching frozen `apex/config.py` — engine §6 tables remain single-source + literal-tested |
| ISSUE-CP2-016 | **CLOSED-by-CP-8-decision** | undefined `formula_k_*`/`theta_*` slots stay UNAVAILABLE (fail-closed); F74 pathway stays open for a future producer |
| ISSUE-CP4-005 | **CLOSED-with-evidence** | CP-5 re-tested both E07 modes — `test_e07_rtm.py::TestUTCWindows`, `test_cp5_engines.py::TestE07E12BothModes` |
| ISSUE-CP8-001 | **CLOSED (documented divergence)** | Ch.17 `budget_per_trade 1.0 %` / `k_attn 0.05` vs the frozen YAML `0.005` / `0.25`; YAML wins at runtime, the divergence is *reported* not reconciled — `test_research_governance.py::TestRegistry::test_yaml_backed_values_match_or_are_recorded`. **Owner question escalated** (confirm §9.5-11 supersedes Ch.17) |
| ISSUE-CP8-002 | **CLOSED** | Numba = Wave-Out (AA.7-2); `NUMBA_USED=False`, no numba import possible |
| ISSUE-CP8-003 | **CLOSED (citation correction)** | ISSUE-CP7-001 cites cases C-16/C-17; the −1021/−2026 pins are actually **C-09/C-10** in the hash-locked fixture (verified by the harness run) |
| ISSUE-CP8-004 | **CLOSED (disclosed)** | `APEX_DOTENV_PATH` is a documented 10th name (path pointer only, never a secret) — kept under G4; owner may retire it |
| ISSUE-CP8-005 | **CLOSED** | the five predecessor opens all carry final dispositions (above) |
| ISSUE-CP8-006 | **ESCALATED-TO-OWNER (verbatim)** | ISSUE-CP6-002 prompt-number confirm/retire · ISSUE-CP6-004 `CIRCUIT_OPEN` registry · ISSUE-CP7-001 −1021/−2026 semantics · ISSUE-CP7-003 verbatim-literal relocation · ISSUE-CP7-008 NULL-for-absent-money DDL · all AI.13 gates |

---

## 9. Blueprint Compliance Declaration

- [x] **No required component was omitted.** — §9.5 tree 61/61 present and
  non-empty (SW1); TRACEABILITY Parts I–III complete (Part I rows + Part II
  ids + Part III per-stage detail incl. the CP-8 sweep table SW1–SW13).
- [x] **No unauthorized behavior was introduced.** — Wave-Out audit clean (no
  Numba, no PostgreSQL, no networked bus, no SHADOW, no hedge/CROSS margin, no
  optimizer writing live YAML, no adaptive-ATR/dynamic-k, no extra
  family/playbook; the §9.5-9 list is enforced by `WaveOutError` sites and by
  module-level guards); CP-8 wrote only its authorized surfaces.
- [x] **No placeholder implementation remains.** — completeness grep (SW2) shows
  8 hits, all allowlisted abstract seams (each with ≥1 concrete implementation)
  or the mandated Wave-Out notes; 0 Wave-In stubs; no `pass`-only bodies outside
  cancellation handling.
- [x] **No specification deviation occurred beyond logged & accepted items.** —
  deviations are exactly: ADR-P2-003 (additive handoffs), ADR-P2-005
  (research/ops paths), ADR-P2-009 (adapter conformance = synthetic + owner
  export; real gate OPEN), ADR-P2-010 (sandbox/device labels), ADR-P2-013
  (frozen `.gitignore`), plus the logged issues in §8 (ISSUE-CP8-001…006 and
  the predecessor entries they close).

**Honest limits of this declaration.** It covers the repository as measured in
this sandbox: no venue was called, no capital was risked, no target-device
measurement was taken, and no AI.13 external gate is claimed closed. The
`HARNESS-READY` label applies to G-PAPER-*/G-CAPACITY-*/G-ADAPTER-*; the rest
are owner procedures listed in §7.

`CP-8 closeout complete — 2026-09-14T12:49Z — commits 0957633..41deb78 + the closeout commit at branch HEAD (arena/01a09fcd-upstage) — suite: 2553 passed / 0 failed / 3 harness-open (T-NFR-001..003 are owner target-device measurements; every other external gate is an owner procedure per §7)`
