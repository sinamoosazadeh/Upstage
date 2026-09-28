# Independent verification — APEX_GEN5 audit, Session V5

## Summary table

| ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option |
|---|---|---:|---:|---|---|---|
| H-001 | CONFIRMED | S1 | S1 | No | = ISSUE-076; delta: required per-cell G-PAPER-001 receipt/envelope details | A — implement the normative replay CLI as a non-network, read-only runner; CP-15 owns it. No frozen file change if composed outside backtest; acceptance hashes change only when replay outcome changes. |
| H-002 | UNVERIFIED | S1 | — | Partial | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-003 | UNVERIFIED | S1 | — | Yes | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-004 | UNVERIFIED | S1 | — | Partial | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-005 | UNVERIFIED | S1 | — | Partial | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-006 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-007 | UNVERIFIED | S1 | — | Partial | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-008 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-009 | CONFIRMED | S1 | S2 | Yes | D6/P4 (Phase-2 entry gate) | A — validate structured replay receipt and critical failures before defaults_active; persist a receipt. Non-frozen bootstrap adapter/service alternative; existing tests expecting arbitrary callbacks to activate will need tightening. |
| H-010 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-011 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-012 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-013 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-014 | CONFIRMED | S1 | S2 | No | = D58; delta: minimal non-null package accepted as LIVE calibrated | A — require a governed, schema-validated, versioned calibration artifact and bind p_hat to it; retain D58 fail-closed until supplied. Adapter/schema outside frozen logistic code is possible; invalidates only calibration package identities and related forecast caches. |
| H-015 | CONFIRMED | S1 | S1 | Yes | — | A — supply PIT order notional and ADV to a cost adapter; do not patch the frozen backtest module without owner ruling. B10 notional/slippage tests must be reconciled to avoid double count; cost changes invalidate backtest metrics, caches, WFO and promotion evidence. |
| H-016 | CONFIRMED | S1 | S1 | Yes | — | A — compute portfolio/account equity returns from actual risk fraction and costs separately from R expectancy. Frozen `backtest.py` is directly implicated; outside-file adapter can only fix downstream WFO metrics if every caller uses it. Existing golden metrics and promotion thresholds need re-baselining; invalidate research artifacts. |
| H-017 | CONFIRMED | S1 | S1 | Yes | — | A — implement gap-aware fill/entry rejection in a non-frozen replay wrapper or obtain owner ruling to change frozen exit path. Tests/golden trades, PnL, hashes and promotion evidence change; no DB migration, but rerun research. |
| H-018 | CONFIRMED | S1 | S1 | Yes | — | A — distinguish `oos is None` (no reserved block) from explicit empty OOS and require split provenance. Frozen file direct; wrapper can prevalidate but cannot safely infer caller intent. Update WFO tests and invalidate candidate verdicts. |
| H-019 | CONFIRMED | S2 | S2 | Yes | — | A — replace return-only named stress with typed market/order scenarios at the replay boundary; keep current transform only as explicitly labelled approximation. Frozen engine changes need owner approval; existing scenario outputs and replay hashes change. |
| H-020 | CONFIRMED | S1 | S2 | Yes | — | A — use a predeclared paired Sharpe-difference method on aligned period returns (or rename the current test honestly). Frozen backtest function implicated; benchmark/WFO outputs and promotion receipts require recompute. |
| H-021 | CONFIRMED | S1 | S1 | No | — | A — rank only finite feasible results; return NO_FEASIBLE when none. Non-frozen optimizer; update optimizer tests and stored suggestion identity/checkpoint semantics; no training or DB migration required. |
| H-022 | PARTIAL | S1 | S1 | No | — | A — persist canonical grid, seed, input, code and protocol manifest; verify on resume and restore results. Non-frozen optimizer/checkpoint layer; change checkpoint schema/migration and rerun any incompatible incomplete run. |
| H-023 | CONFIRMED | S1 | S2 | No | — | A — re-check workload/time at each cell and checkpoint a named halt. Non-frozen scheduler/optimizer; interruption changes may affect expected run completion and need resume tests, no frozen change. |
| H-024 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-025 | CONFIRMED | S1 | S1 | No | — | A — pass per-trade exposure/limit evidence and enforce all trades, and require finite five-regime metrics. Non-frozen objective API; callers/tests and candidate identity change; no order path should consume prior summary-only approvals. |
| H-026 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-027 | CONFIRMED | S1 | S1 | No | — | A — assert family equality across candidate, pool, WFO, PBO, DSR, benchmark and package. Non-frozen promotion layer; reject cross-family cached evidence and re-run affected candidates. |
| H-028 | CONFIRMED | S1 | S1 | Partial | — | A — derive outcome and R from fills/price/stop and dedupe stable event identity. `Trade` is in frozen backtest; an outside promotion validator can reject inconsistent outcomes but cannot fix untrusted construction. Recompute pooled stats and promotion artifacts. |
| H-029 | CONFIRMED | S2 | S2 | No | — | A — define n=0 shrinkage as family prior/unavailable and explicitly wire only under approved protocol. Non-frozen promotion; tests/consumer behavior change; no model retraining unless this enters runtime decisions. |
| H-030 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-031 | UNVERIFIED | S2 | — | Partial | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-032 | CONFIRMED | S2 | S2 | Partial | — | A — serialize ATR-normalized risk from existing Trade fields, not nonexistent property. `Trade` class is in frozen backtest, but the non-frozen serializer can derive from `abs(entry-stop)` and ATR. Update serialization tests and no training needed. |
| H-033 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-034 | CONFIRMED | S2 | S2 | No | = D58 for NOT_WIRED; delta: standalone estimate accepts incomplete components | A — validate complete component provenance/quality and make insufficient data unavailable; keep composite unwired per D58. Non-frozen logistic implementation but adapter alternative exists; forecast identities/calibration outputs change, no DB migration until persistence is added. |
| H-035 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-036 | UNVERIFIED | S2 | — | Yes | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-037 | PARTIAL | S2 | S2 | No | — | A — document independence as an assumption or use dependence-aware effective sample/cluster interval. Promotion protocol is non-frozen but contract Z.2 is normative; owner decision required before changing statistical acceptance, recompute all family gates and do not treat ATR as proof. |
| I-001 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-002 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-003 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-004 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-005 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-006 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-007 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-008 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-009 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-010 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-011 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-012 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-013 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-014 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-015 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-016 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-017 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |

Baseline check: `git rev-parse HEAD` = `85b2c155d7b054a468379ddfd802eb239d0801f9`; `git log -1 --oneline` = `85b2c15 Merge pull request #25 from sinamoosazadeh/arena/01a0d98b-upstage`. All source line references are against that commit. Audit source: commit `015d19bd6ec1956b853fd566157a929f9f95f260`; index commit `690e2d8899319a7c7a96456f92c3008878e59346`.

Scope note: this is a read-only, evidence-bounded verification. Synthetic probes prove only the invoked code path, not device/database/model/exchange behavior. No `.env`, secret, `data/`, model artifact, network endpoint, or real trading operation was accessed. `requirements.lock` was installed only into the execution environment; no tracked dependency file changed.

## Evidence and method

Baseline source files were not changed. Selected actual-repository probes are in `AUDIT/probes_V5/`. Recorded commands/results:

- `phase2_forecast.py` with real `BootstrapRunner`, real forecast functions and a disposable temp SQLite checkpoint; raw output `phase2_forecast.out`.
- `backtest_research_claims.py` imports actual backtest/optimizer/promotion code and uses synthetic in-memory values; raw output `backtest_research_claims.out`.
- Targeted tests: `pytest_research.out` (316 passed, 1 failed; existing governance test invokes unavailable git object `f14be36`); `pytest_context_integration.out` (22 passed, 13 warnings). These green tests are not a device/model/data acceptance result.
- The engine-context/store-source relevant suite was run as `python3 -m pytest -q -p no:cacheprovider tests/unit/test_engine_context.py tests/integration/test_context_to_trade_paper.py tests/integration/test_cp14_producer.py`: 249 passed, 13 warnings, 1129.21 s (tool raw output was not persisted as a separate file). It is test evidence only.
- No SQL-per-row/cell/bar query performance audit was completed in V5; no performance claims about actual device data are made.

## Row-by-row review
| H-001 | CONFIRMED | S1 | S1 | No | = ISSUE-076; delta: required per-cell G-PAPER-001 receipt/envelope details | A — implement the normative replay CLI as a non-network, read-only runner; CP-15 owns it. No frozen file change if composed outside backtest; acceptance hashes change only when replay outcome changes. |
| H-002 | UNVERIFIED | S1 | — | Partial | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-003 | UNVERIFIED | S1 | — | Yes | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-004 | UNVERIFIED | S1 | — | Partial | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-005 | UNVERIFIED | S1 | — | Partial | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-006 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-007 | UNVERIFIED | S1 | — | Partial | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-008 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-009 | CONFIRMED | S1 | S2 | Yes | D6/P4 (Phase-2 entry gate) | A — validate structured replay receipt and critical failures before defaults_active; persist a receipt. Non-frozen bootstrap adapter/service alternative; existing tests expecting arbitrary callbacks to activate will need tightening. |
| H-010 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-011 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-012 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-013 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-014 | CONFIRMED | S1 | S2 | No | = D58; delta: minimal non-null package accepted as LIVE calibrated | A — require a governed, schema-validated, versioned calibration artifact and bind p_hat to it; retain D58 fail-closed until supplied. Adapter/schema outside frozen logistic code is possible; invalidates only calibration package identities and related forecast caches. |
| H-015 | CONFIRMED | S1 | S1 | Yes | — | A — supply PIT order notional and ADV to a cost adapter; do not patch the frozen backtest module without owner ruling. B10 notional/slippage tests must be reconciled to avoid double count; cost changes invalidate backtest metrics, caches, WFO and promotion evidence. |
| H-016 | CONFIRMED | S1 | S1 | Yes | — | A — compute portfolio/account equity returns from actual risk fraction and costs separately from R expectancy. Frozen `backtest.py` is directly implicated; outside-file adapter can only fix downstream WFO metrics if every caller uses it. Existing golden metrics and promotion thresholds need re-baselining; invalidate research artifacts. |
| H-017 | CONFIRMED | S1 | S1 | Yes | — | A — implement gap-aware fill/entry rejection in a non-frozen replay wrapper or obtain owner ruling to change frozen exit path. Tests/golden trades, PnL, hashes and promotion evidence change; no DB migration, but rerun research. |
| H-018 | CONFIRMED | S1 | S1 | Yes | — | A — distinguish `oos is None` (no reserved block) from explicit empty OOS and require split provenance. Frozen file direct; wrapper can prevalidate but cannot safely infer caller intent. Update WFO tests and invalidate candidate verdicts. |
| H-019 | CONFIRMED | S2 | S2 | Yes | — | A — replace return-only named stress with typed market/order scenarios at the replay boundary; keep current transform only as explicitly labelled approximation. Frozen engine changes need owner approval; existing scenario outputs and replay hashes change. |
| H-020 | CONFIRMED | S1 | S2 | Yes | — | A — use a predeclared paired Sharpe-difference method on aligned period returns (or rename the current test honestly). Frozen backtest function implicated; benchmark/WFO outputs and promotion receipts require recompute. |
| H-021 | CONFIRMED | S1 | S1 | No | — | A — rank only finite feasible results; return NO_FEASIBLE when none. Non-frozen optimizer; update optimizer tests and stored suggestion identity/checkpoint semantics; no training or DB migration required. |
| H-022 | PARTIAL | S1 | S1 | No | — | A — persist canonical grid, seed, input, code and protocol manifest; verify on resume and restore results. Non-frozen optimizer/checkpoint layer; change checkpoint schema/migration and rerun any incompatible incomplete run. |
| H-023 | CONFIRMED | S1 | S2 | No | — | A — re-check workload/time at each cell and checkpoint a named halt. Non-frozen scheduler/optimizer; interruption changes may affect expected run completion and need resume tests, no frozen change. |
| H-024 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-025 | CONFIRMED | S1 | S1 | No | — | A — pass per-trade exposure/limit evidence and enforce all trades, and require finite five-regime metrics. Non-frozen objective API; callers/tests and candidate identity change; no order path should consume prior summary-only approvals. |
| H-026 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-027 | CONFIRMED | S1 | S1 | No | — | A — assert family equality across candidate, pool, WFO, PBO, DSR, benchmark and package. Non-frozen promotion layer; reject cross-family cached evidence and re-run affected candidates. |
| H-028 | CONFIRMED | S1 | S1 | Partial | — | A — derive outcome and R from fills/price/stop and dedupe stable event identity. `Trade` is in frozen backtest; an outside promotion validator can reject inconsistent outcomes but cannot fix untrusted construction. Recompute pooled stats and promotion artifacts. |
| H-029 | CONFIRMED | S2 | S2 | No | — | A — define n=0 shrinkage as family prior/unavailable and explicitly wire only under approved protocol. Non-frozen promotion; tests/consumer behavior change; no model retraining unless this enters runtime decisions. |
| H-030 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-031 | UNVERIFIED | S2 | — | Partial | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-032 | CONFIRMED | S2 | S2 | Partial | — | A — serialize ATR-normalized risk from existing Trade fields, not nonexistent property. `Trade` class is in frozen backtest, but the non-frozen serializer can derive from `abs(entry-stop)` and ATR. Update serialization tests and no training needed. |
| H-033 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-034 | CONFIRMED | S2 | S2 | No | = D58 for NOT_WIRED; delta: standalone estimate accepts incomplete components | A — validate complete component provenance/quality and make insufficient data unavailable; keep composite unwired per D58. Non-frozen logistic implementation but adapter alternative exists; forecast identities/calibration outputs change, no DB migration until persistence is added. |
| H-035 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-036 | UNVERIFIED | S2 | — | Yes | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| H-037 | PARTIAL | S2 | S2 | No | — | A — document independence as an assumption or use dependence-aware effective sample/cluster interval. Promotion protocol is non-frozen but contract Z.2 is normative; owner decision required before changing statistical acceptance, recompute all family gates and do not treat ATR as proof. |
| I-001 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-002 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-003 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-004 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-005 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-006 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-007 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-008 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-009 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-010 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-011 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-012 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-013 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-014 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-015 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-016 | UNVERIFIED | S1 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |
| I-017 | UNVERIFIED | S2 | — | No | — | No recommendation until the row is independently verified; do not apply an audit proposal based on this incomplete review. |

## Evidence and method

Baseline source files were not changed. Selected actual-repository probes are in `AUDIT/probes_V5/`. Recorded commands/results:

- `phase2_forecast.py` with real `BootstrapRunner`, real forecast functions and a disposable temp SQLite checkpoint; raw output `phase2_forecast.out`.
- `backtest_research_claims.py` imports actual backtest/optimizer/promotion code and uses synthetic in-memory values; raw output `backtest_research_claims.out`.
- Targeted tests: `pytest_research.out` (316 passed, 1 failed; existing governance test invokes unavailable git object `f14be36`); `pytest_context_integration.out` (22 passed, 13 warnings). These green tests are not a device/model/data acceptance result.
- The engine-context/store-source relevant suite was run as `python3 -m pytest -q -p no:cacheprovider tests/unit/test_engine_context.py tests/integration/test_context_to_trade_paper.py tests/integration/test_cp14_producer.py`: 249 passed, 13 warnings, 1129.21 s (tool raw output was not persisted as a separate file). It is test evidence only.
- No SQL-per-row/cell/bar query performance audit was completed in V5; no performance claims about actual device data are made.

## Row-by-row review

## H-001

### Auditor claim (short quote)
The required `run_apex.py replay` command and whole-store deterministic replay envelope are absent.

### What I read (files, line ranges, functions, callers)
I read `scripts/run_apex.py` command registration/parser at 1071–1185, `apex/research/backtest.py` completely (618–630), `apex/research/bootstrap.py::BootstrapRunner.run_phase2` (360–381), service wrapper `BootstrapService.run_phase2` (1567–1574), and grep callers. `COMMANDS` contains boot/grid/demo/alerts/bootstrap/status/serve/repair-partial/train-e11/publish-quality-backfill; no `replay`. The only `deterministic_double_run` consumers found are its definition and unit tests. Contract: APEX_GEN5 §18.2 W.6 Session-A P4 (around 17257–17268) requires whole-local-store per-cell canonical hashes, zero exceptions and an envelope. CP9 handoff line 457 assigns it to CP-15. This is also ISSUE-076; extra point here is the precise G-PAPER-001 envelope, not a new duplicate defect.

### Reproduction (command, probe file, actual result)
`git grep -n 'deterministic_double_run' -- apex scripts tests`; inspect COMMANDS; `PYTHONPATH=. python3 AUDIT/probes_V5/phase2_forecast.py`. Probe reports replay_cli_registered=false. The probe does not open the store or run replay. No actual DB touched.

### Verdict and reasoning
CONFIRMED for absent CLI/wiring. Not evidence that the real store fails replay; it proves the prescribed gate cannot be invoked through this CLI. Independent severity S1: an acceptance gate before PAPER is unavailable, but no live order or paper simulator behavior is inferred.

### Root cause
The CLI dispatch surface does not register an adapter for the double-run helper; helper is a generic callback comparator, not a whole-store replay runner.

### Direct impact
G-PAPER-001 receipt absent; replay-vs-ledger/cost/exit comparison is not currently established through the command. Downstream promotion/research result quality remains unmeasured; upstream store contents are unknown.

### Secondary effects and interactions (upstream/downstream)
W.6 P4 requires whole-store deterministic double-run envelope; G-PAPER-001 remains OPEN/UNVERIFIED. CP9 assigns implementation to CP-15. ISSUE-076 already records missing `replay`; reference it, and do not double count the baseline omission.

### Contract and decisions
No freeze impact for CLI wiring; `backtest.py` is frozen so do not alter its deterministic path absent ruling. Outside alternative: non-frozen CLI/composition adapter invoking frozen path read-only.

### Frozen status and non-frozen alternative
See single option in summary. Acceptance: two separate runs against a fixed SQLite snapshot, all expected cells explicitly reported including empty-data status, identical per-cell hashes, zero exceptions, stable canonical receipt; network-deny and no writes/orders.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — implement the normative replay CLI as a non-network, read-only runner; CP-15 owns it. No frozen file change if composed outside backtest; acceptance hashes change only when replay outcome changes.

### My recommendation
Independent severity S1; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-002

### Auditor claim (short quote)
A fresh one-candle E11 engine per close resets hysteresis/history state.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-003

### Auditor claim (short quote)
Training feature/label construction omits the shock-gap projection used at inference.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-004

### Auditor claim (short quote)
The producer supplies neither the E11 transition matrix T nor regime base rates.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-005

### Auditor claim (short quote)
Training cache identity omits upstream engine/code and effective feature/label policy versions.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-006

### Auditor claim (short quote)
Artifact digest does not bind training provenance metadata and accepts arbitrary well-shaped query hashes.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-007

### Auditor claim (short quote)
Historical producer queries may use a currently available classifier trained with future labels.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-008

### Auditor claim (short quote)
Kline-only PAPER source leaves OI lag unavailable for the risk decision despite E11 partial-quality training.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-009

### Auditor claim (short quote)
Phase 2 marks defaults active on deterministic callbacks without checking their exception/critical-failure fields.

### What I read (files, line ranges, functions, callers)
Read full `BootstrapRunner.run_phase2` (bootstrap.py:360–381), full service delegator at 1567–1574, CLI serve/bootstrap dispatch and the cited unit test slice. Direct consumer grep shows service calls runner and reports `_phase2_line`; `serve` does not gate on a persisted Phase2 receipt. The function only compares canonicalized callback outputs. Contract W.6 Phase 2 requires replay and health-check before defaults activate; Session-A P4 defines the stronger whole-store envelope. D6 says this is the PAPER entry gate. Frozen `bootstrap.py` is involved.

### Reproduction (command, probe file, actual result)
`PYTHONPATH=. python3 AUDIT/probes_V5/phase2_forecast.py`; real BootstrapRunner + temporary SQLite checkpoint DB, callback returns `{exceptions:999, critical_failures:[FATAL], ledger_reconciled:false}` identically twice. Raw output: `status=COMPLETE`, `defaults_active=true`, `critical_failures=[]`, `deterministic=true`. Synthetic callback only; no real store/model/device.

### Verdict and reasoning
CONFIRMED for callback validation semantics. It does not establish that serve currently activates PAPER or that a real replay passed. Independent severity S2 rather than S1: false in-memory phase status, but serve gate absence and PAPER wiring remain separate findings.

### Root cause
Determinism is treated as the sole acceptance predicate; callback's domain-level failures are not inspected and the result is not bound to a validated receipt.

### Direct impact
A caller can mislabel its deterministic report as defaults active. No actual defaults or orders are changed by this unit function; serve composition must be separately gated.

### Secondary effects and interactions (upstream/downstream)
Upstream callback contract and Phase-1/store readiness are not checked; downstream service reports the status only, and no durable receipt/serve gate is evidenced. H-001 is separate CLI gap.

### Contract and decisions
APEX_GEN5 §18.2 W.6 requires Phase-2 deterministic validation and health check; D6/P4 requires the stronger whole-store envelope. Later D6 controls; code callback test cannot supersede it.

### Frozen status and non-frozen alternative
`apex/research/bootstrap.py` frozen. Alternative non-frozen service/orchestration adapter may validate receipt before reporting/serve; changing frozen runner requires explicit owner ruling. No hash change if only receipt wrapper, but receipt schema/version would need to be recorded.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — validate structured replay receipt and critical failures before defaults_active; persist a receipt. Non-frozen bootstrap adapter/service alternative; existing tests expecting arbitrary callbacks to activate will need tightening.

### My recommendation
Independent severity S2; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-010

### Auditor claim (short quote)
Training can report all ten symbols although only a subset of the 20 default base cells contributes samples.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-011

### Auditor claim (short quote)
A structurally valid training cache payload can alter labels/vectors without changing input_hash.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-012

### Auditor claim (short quote)
The training bar cap is applied after full-window reads and lineage preparation.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-013

### Auditor claim (short quote)
Research fit-study falls back silently to historical theta 0.65 on parameter-load error.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-014

### Auditor claim (short quote)
A minimal non-null forecast mapping can be treated as calibrated and eligible for LIVE.

### What I read (files, line ranges, functions, callers)
Read all `apex/forecast/logistic.py` (504 lines), cited unit-test section and `git grep` consumers of `build_forecast`, `require_calibrated_package`, `composite_estimate`, and `.invalidate()`. Production callers are engine_context and plan_bridge; tests explicitly accept `{p_hat:0.6}` in `require_calibrated_package` and `{p_hat:0.62,q_forecast:0.71}` for LIVE. APEX_GEN5 Ch.13 §13.1 lines 16068, 16095 says bootstrap prior is not LIVE-eligible; D58 (decision log 1175–1177) says calibrated WFO package and composite wiring are not implemented. D58 is later and binding.

### Reproduction (command, probe file, actual result)
`PYTHONPATH=. python3 AUDIT/probes_V5/phase2_forecast.py`; actual `build_forecast` with package `{p_hat:.61}`, conflicting caller p_hat `.99`, zero 12-vector and explicit synthetic uncertainty. Output: `bootstrap_prior=false`, returned p_hat `.99`, `eligible_environments` includes LIVE, `is_admissible_live=true`. This proves API acceptance only, not actual calibrated package nor LIVE wiring.

### Verdict and reasoning
CONFIRMED at API boundary; current production eligibility is over-permissive if an untrusted mapping is supplied. Downgrade independent severity to S2 because D58 says calibrated path is NOT_WIRED and no actual LIVE execution was established. Do not say a real trade occurred.

### Root cause
`require_calibrated_package` only copies a non-None mapping; `build_forecast` requires key `p_hat` but does not validate schema/provenance/calibration or bind caller `p_hat` to package. Any non-null mapping is marked non-bootstrap and receives LIVE eligibility.

### Direct impact
Potentially false LIVE-admissible forecast record for an uncalibrated package. It is not proof a plan/order consumes it; normal runtime path and economic gate are separate.

### Secondary effects and interactions (upstream/downstream)
Input package provenance is not established upstream; downstream bridge consumes produced record but no LIVE transaction traced. D58/ISSUE-CP14-070 specifically keeps composite estimate unwired; do not confuse this finding with wired forecast calibration.

### Contract and decisions
Ch.13 §13.1 prohibits bootstrap for LIVE. D58 later states calibration package absent/unwired and bad non-null package should be rejected without fallback. Apply D58 precedence; reported behavior fails the intended package validation seam, not proof a package exists.

### Frozen status and non-frozen alternative
`apex/forecast/logistic.py` not listed frozen. A non-frozen calibration-artifact validator/producer adapter can enforce contract before existing API, avoiding direct edit; if the record semantics change, forecast canonical identities/cache receipts must be versioned and recalibrated. No DB migration currently required.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — require a governed, schema-validated, versioned calibration artifact and bind p_hat to it; retain D58 fail-closed until supplied. Adapter/schema outside frozen logistic code is possible; invalidates only calibration package identities and related forecast caches.

### My recommendation
Independent severity S2; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-015

### Auditor claim (short quote)
Backtest slippage uses quantity instead of order_size/ADV.

### What I read (files, line ranges, functions, callers)
Read `apex/research/backtest.py` completely, including `_cost` and `BacktestEngine.run`; searched consumers of `BacktestEngine`, `_cost`, and `evaluate_wfo`. Contract APEX_GEN5 §16.6 / §17 slippage formula (line 16664; parameter table around 17142) is `α_spread * |order_size/ADV|`, with α=.25. Frozen file directly implicated; no decision log authorizes changing it.

### Reproduction (command, probe file, actual result)
`PYTHONPATH=. python3 AUDIT/probes_V5/backtest_research_claims.py`; real BacktestEngine: `_cost(2,1)=0.2504`; `_cost(2,.01)=0.0029`. Source sets quantity=1 in `run` and passes it as notional_fraction; no ADV is accepted. Synthetic only; no PAPER simulator or market data.

### Verdict and reasoning
CONFIRMED that the frozen backtest default applies α to quantity/notional_fraction and cannot implement the contractual size/ADV ratio absent an injected slippage function. The exact numerical impact depends on the intended units/order size/ADV; no real-data impact measured.

### Root cause
Backtest cost API lacks ADV/notional ratio and the default sets quantity to 1.0. Slippage callback can override costs, so claim is limited to default path.

### Direct impact
R/PF/Sharpe and WFO inputs vary with default cost. No current optimizer caller of BacktestEngine was found in direct grep, so live promotion effect is a possible downstream integration, not an observed one.

### Secondary effects and interactions (upstream/downstream)
Upstream ADV is not supplied by API; downstream metrics/promotion inherit costs if this engine is used. B10 and any external slippage_fn could avoid or double-count costs, so integration must define one source.

### Contract and decisions
Contract line 16664 and §18.1 cost-adjusted research criteria govern. §18.2 W.2 requires costs; no later owner decision authorizes removal of ADV term. File is frozen.

### Frozen status and non-frozen alternative
Frozen `apex/research/backtest.py`. Prefer a non-frozen wrapper injecting the proper PIT slippage_fn and explicit units; wrapper must avoid double counting B10. Cost changes invalidate historical metrics, replay hashes, WFO, fit-study/promotion reports; no DB migration/retraining unless training inputs consume these results.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — supply PIT order notional and ADV to a cost adapter; do not patch the frozen backtest module without owner ruling. B10 notional/slippage tests must be reconciled to avoid double count; cost changes invalidate backtest metrics, caches, WFO and promotion evidence.

### My recommendation
Independent severity S1; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-016

### Auditor claim (short quote)
Metrics compound R-multiples directly as if they were account returns for drawdown.

### What I read (files, line ranges, functions, callers)
Read full `backtest.py`, especially `metrics_from_trades`, `max_drawdown`, WFO criterion and `Trade.r_multiple`; contract §18.1 table around 17189–17202 declares drawdown <15%, while W.2 defines expected risk-unit R. No later decision located changing the unit mapping.

### Reproduction (command, probe file, actual result)
`PYTHONPATH=. python3 AUDIT/probes_V5/backtest_research_claims.py`; real `metrics_from_trades` over +1R,-1R reports `max_drawdown:1.0`, `expectancy_r:0`. This demonstrates R multiples are compounded as return fractions. It does not use account capital or risk fraction.

### Verdict and reasoning
CONFIRMED unit mismatch in this API. The correct account drawdown depends on position risk sizing and compounding, not simply 0.5% in all cases; the auditor's 0.5% example is a specific sizing assumption. Severity S1 because the value gates WFO, but no real portfolio equity impact measured.

### Root cause
`metrics_from_trades` passes r_multiple directly to `max_drawdown`, which initializes equity=1 and compounds `1+r`; no capital/risk fraction exists on `Trade`.

### Direct impact
Could flag candidates as >15% DD or otherwise misstate portfolio risk. Direction/magnitude varies with R path and risk fraction; this probe's 100% trough is not real account DD.

### Secondary effects and interactions (upstream/downstream)
Upstream backtest supplies trade R, downstream WFO checks max_drawdown <.15 and promotion trusts WFO decision. Real cost and position-size mapping absent. No ledger/orders are connected by this metric function.

### Contract and decisions
APEX_GEN5 §18.1 requires Max Drawdown and §18.2 W.2 defines risk unit/owner DD. No owner decision found reconciling R-multiple series to account-equity percentage. Frozen file applies.

### Frozen status and non-frozen alternative
Frozen backtest directly. A non-frozen portfolio-equity adapter could calculate a separate account DD only if all consumers use it; otherwise owner ruling needed. Changing unit alters metric fixtures, WFO/promotion outcomes and replay identities; recompute research, no model training inherently.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — compute portfolio/account equity returns from actual risk fraction and costs separately from R expectancy. Frozen `backtest.py` is directly implicated; outside-file adapter can only fix downstream WFO metrics if every caller uses it. Existing golden metrics and promotion thresholds need re-baselining; invalidate research artifacts.

### My recommendation
Independent severity S1; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-017

### Auditor claim (short quote)
Backtest stop fills ignore gap-through prices at entry and exit.

### What I read (files, line ranges, functions, callers)
Read entire frozen BacktestEngine `_resolve_exit` and `run`; contract gap behavior lines 17055–17060/17099–17108 requires stop-gap slippage intended/actual price and worst loss. No later decision changing the replay precedence found.

### Reproduction (command, probe file, actual result)
Probe `AUDIT/probes_V5/backtest_research_claims.py` uses real `_resolve_exit`; long entry bar opens 98 below stop 99 and returns `(1,99,'STOP')`. Code also returns stop price on later gap. Synthetic bars only; no venue or PAPER execution.

### Verdict and reasoning
CONFIRMED for replay exit price at stop despite gap-through. Entry gap specifically resolves at stop even though open is already through it; probe proves the source behavior. Actual frequency/severity depends on market data.

### Root cause
Exit resolver checks high/low touch but never compares gap open with stop nor records intended vs actual fill/slippage. Entry opens beyond stop yet assigns stop fill.

### Direct impact
Understates adverse loss, may even convert invalid entry into positive R after algebra/cost assumptions. Promotions and risk updates consume biased trade outcome if using this engine; actual PAPER simulator D58 remains separate.

### Secondary effects and interactions (upstream/downstream)
Upstream OHLC feeds the resolver; downstream metrics/family pool/WFO use its `Trade`. No order, ledger, or paper fill exists in this probe.

### Contract and decisions
APEX_GEN5 §16 stop-gap rule requires intended_stop, actual_fill, STOP_GAP_SLIPPAGE and realized worst loss. Frozen backtest behavior conflicts in the gap path.

### Frozen status and non-frozen alternative
Frozen backtest file. A wrapper could reject entry-through-stop but cannot alter subsequent stop fill unless it transforms bars/results; correct fix is in frozen exit core with owner ruling. Golden replay hashes/trades/metrics/promotion reports change and need recompute.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — implement gap-aware fill/entry rejection in a non-frozen replay wrapper or obtain owner ruling to change frozen exit path. Tests/golden trades, PnL, hashes and promotion evidence change; no DB migration, but rerun research.

### My recommendation
Independent severity S1; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-018

### Auditor claim (short quote)
An explicitly empty OOS block is silently replaced by test metrics and can promote.

### What I read (files, line ranges, functions, callers)
Read full `evaluate_wfo` and `walk_forward` in frozen backtest.py. Contract §18.1 requires OOS Sharpe/PF/DD; docstring says test is OOS only when no separate OOS window was carved.

### Reproduction (command, probe file, actual result)
Probe real API `evaluate_wfo(train={}, test={sharpe:2,PF:2,DD:.01}, oos={})` returns PROMOTED and copies test into oos. Explicit-empty and omitted `oos` are indistinguishable. Synthetic metrics only.

### Verdict and reasoning
CONFIRMED for explicit-empty ambiguity. The function's fallback is consistent only when caller means no separate OOS; its signature cannot distinguish the reported invalid reserved-empty case. No genuine WFO dataset checked.

### Root cause
Truthiness test `dict(oos) if oos else dict(test)` conflates None and empty mapping and accepts missing/empty train without manifest.

### Direct impact
Caller can submit no actual OOS block but pass test statistics as OOS; downstream candidate may treat it as promoted. No claim any real candidate did so.

### Secondary effects and interactions (upstream/downstream)
Upstream split/provenance not consumed by evaluator; downstream promotion accepts decision string. H-026 separately covers trust in flags.

### Contract and decisions
APEX_GEN5 §18.1 WFO thresholds and `walk_forward` docstring permit test=OOS only absent a reserved OOS window. Explicit empty reserved OOS must not be silently reinterpreted. Frozen file.

### Frozen status and non-frozen alternative
Frozen backtest. Non-frozen adapter can require explicit split manifest but cannot distinguish intent in existing call absent API change. Existing tests/fixtures and any WFO verdicts must be updated/recomputed; no retraining.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — distinguish `oos is None` (no reserved block) from explicit empty OOS and require split provenance. Frozen file direct; wrapper can prevalidate but cannot safely infer caller intent. Update WFO tests and invalidate candidate verdicts.

### My recommendation
Independent severity S1; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-019

### Auditor claim (short quote)
Stress labels do not implement volume, correlation, and execution-fill stresses they name.

### What I read (files, line ranges, functions, callers)
Read all stress definitions/transforms in frozen backtest.py and contract §18.4 around 17459. The public transform accepts return series, not OHLCV, covariance, positions, order rejects or fills.

### Reproduction (command, probe file, actual result)
Probe real `apply_stress`: Volume [0.1,-0.1] becomes [0.01,-0.01]; CorrelationBreakdown becomes [0.3,-0.3]; ExtremeFill changes numeric return only to [0.048,-0.152]. It creates no volume/correlation/order/fill events. Synthetic transform, not system resilience test.

### Verdict and reasoning
CONFIRMED that named stress functions transform returns, rather than implementing the named physical market/execution mechanics. Severity S2: research validity/coverage; no live protective behavior inferred.

### Root cause
Stress API's only input is a return sequence and its transforms are scalar formulas; scenario labels/specs describe richer events than the model represents.

### Direct impact
W.5 stress test can overstate liquidity/execution resilience if caller treats names as full scenarios. No actual portfolio or adapter tested.

### Secondary effects and interactions (upstream/downstream)
Upstream receives only returns; downstream battery metrics are descriptive and could be used in promotion. No volume/order/fill pipeline is invoked.

### Contract and decisions
APEX_GEN5 §18.1 scenario table and §18.4 shared walk-forward/stress require volume -90%, correlation-to-1 and extreme-fill rejects/partial fills. Frozen module under scope.

### Frozen status and non-frozen alternative
Frozen backtest. Alternative scenario harness outside file can generate OHLCV/order fixtures and pass resulting outcomes to metrics; existing named scalar output should be labelled approximation. If core changes, golden stress outputs and hashes change; no DB migration/training.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — replace return-only named stress with typed market/order scenarios at the replay boundary; keep current transform only as explicitly labelled approximation. Frozen engine changes need owner approval; existing scenario outputs and replay hashes change.

### My recommendation
Independent severity S2; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-020

### Auditor claim (short quote)
The benchmark routine tests mean paired excess returns but calls the outcome Sharpe outperformance.

### What I read (files, line ranges, functions, callers)
Read `benchmark_outperformance` completely and its direct callers; contract §18.2 W.2 requires net return exceeds BTC buy-and-hold, while §18.1 names Sharpe. No caller proving alternative method found.

### Reproduction (command, probe file, actual result)
Probe real function with strategy [.01,.02,.03,.04] and benchmark [.10,.08,.11,.07] returns mean_excess=-.065, Sharpe strategy≈1.936, benchmark≈4.930, outperforms=false. Source computes z from mean paired differences, not Sharpe difference; auditor's proposed false-positive numerical case was not repeated.

### Verdict and reasoning
CONFIRMED semantic mismatch (test statistic is mean paired excess, output also reports Sharpes); not confirming the auditor's specific outperforms=true counterexample or period-alignment claim. Severity S2.

### Root cause
Function labels output `outperforms` as strategy Sharpe better in docstring but z-tests mean return difference; it does not check calendar identifiers, only vector length.

### Direct impact
A false or wrong-kind benchmark gate may alter promotion eligibility. The probe happens to correctly reject weaker strategy, so no false positive reproduced here.

### Secondary effects and interactions (upstream/downstream)
Upstream vectors lack timestamps/period manifests; downstream signal objective uses net return benchmark field separately. No production optimizer connection observed.

### Contract and decisions
W.2 requires net return exceeding same-period BTC buy-and-hold; §18.1 reports Sharpe. Function's described inferential claim needs a defined same-period return method; no explicit owner ruling found.

### Frozen status and non-frozen alternative
Frozen backtest. Non-frozen wrapper can require dates and separately compute objective; code change alters benchmark outputs and promotion receipts, necessitating re-run.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — use a predeclared paired Sharpe-difference method on aligned period returns (or rename the current test honestly). Frozen backtest function implicated; benchmark/WFO outputs and promotion receipts require recompute.

### My recommendation
Independent severity S2; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-021

### Auditor claim (short quote)
Optimizer ranks infeasible results by objective value and can report an infeasible winner COMPLETE.

### What I read (files, line ranges, functions, callers)
Read complete `DualOptimizer.run_run` and evaluator contract. Grep callers of `run_run`; no composition into PAPER was established. APEX_GEN5 W.2/W.3 requires feasible constraints and only suggestions.

### Reproduction (command, probe file, actual result)
Real-code probe in `backtest_research_claims.py`: two-state grid; evaluator returns feasible=false,value=100 for both. Output status COMPLETE, feasible_fraction 0, best_value 100, best_params x=0. No file written, no device workload.

### Verdict and reasoning
CONFIRMED. `feasible` increments a counter but is not part of best-result ranking; even all-infeasible results create a COMPLETE best candidate. Severity S1 for invalid research suggestions, not an order bypass.

### Root cause
`best_value` compares all result values after float conversion, independent of feasibility and finiteness; no NO_FEASIBLE branch.

### Direct impact
An infeasible candidate can be suggested or checkpointed as completed. Subsequent validator may still refuse it; no actual package injection proved.

### Secondary effects and interactions (upstream/downstream)
Inputs from evaluator/objective; output enters result/checkpoint/suggestion surface. Governance write guard prevents direct live YAML mutation; promotion acceptance is separate.

### Contract and decisions
APEX_GEN5 §18.2 W.2 constraints require infeasible combinations discarded; optimizer is non-frozen and output suggestion only. No owner exception found.

### Frozen status and non-frozen alternative
Non-frozen optimizer fix; update tests and invalidate incomplete/COMPLETE optimizer checkpoint identities; no model retraining or DB migration if status schema stays same.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — rank only finite feasible results; return NO_FEASIBLE when none. Non-frozen optimizer; update optimizer tests and stored suggestion identity/checkpoint semantics; no training or DB migration required.

### My recommendation
Independent severity S1; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-022

### Auditor claim (short quote)
Optimizer resume identity uses combo count, not grid/seed/data/code; COMPLETE state is trusted.

### What I read (files, line ranges, functions, callers)
Read full `DualOptimizer.run_run` and `CellResult` identity in optimizer.py (347–421, 300–340); checkpoint store details/tests were not read completely. Grep run_run callers. Contract W.8 requires persistent checkpoint/resume.

### Reproduction (command, probe file, actual result)
Probe same-size grids [0,1] and [10,11] under real optimizer returns identical `sru_hash` (same run/cell/optimizer/count). Source also `continue`s on COMPLETE without reconstructing CellResult from saved state. Synthetic in-memory run; no SQLite restart tested.

### Verdict and reasoning
CONFIRMED for hash collision across different grid values. COMPLETE resume's missing returned results is visible in code, but not reproduced against real SQLite; that subclaim remains incomplete. Severity S1 because stale/wrong completed research can be reused.

### Root cause
Hash manifest records `combos:len(combos)` but omits combinations, seed, data and code; complete checkpoint is trusted solely by status.

### Direct impact
Different grids can share identity and skip evaluation; suggestions/results may be absent or stale after restart. No claim device checkpoint corruption.

### Secondary effects and interactions (upstream/downstream)
Upstream grid/seed/data/code not bound; downstream artifacts can inherit a stale status. checkpoint stale-write details H-033 not checked.

### Contract and decisions
APEX_GEN5 §18.2 W.8 persistent checkpoint discipline; D3 exhaustive grid defaults. No later decision authorizes count-only identity.

### Frozen status and non-frozen alternative
Optimizer non-frozen; checkpoint store non-frozen but schema/migration and old resume behavior need tests. Results/hashes/checkpoint IDs invalidate prior runs; no training.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — persist canonical grid, seed, input, code and protocol manifest; verify on resume and restore results. Non-frozen optimizer/checkpoint layer; change checkpoint schema/migration and rerun any incompatible incomplete run.

### My recommendation
Independent severity S1; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-023

### Auditor claim (short quote)
Live-workload and schedule status are checked only once before the cell loop.

### What I read (files, line ranges, functions, callers)
Read full optimizer method. It computes one `schedule.may_run` before entering `for cell_id in cells`; no in-loop provider. No device/scheduler caller examined beyond grep.

### Reproduction (command, probe file, actual result)
Source-backed reproduction is direct control-flow read in optimizer.py:347–421; a changing workload after the initial check cannot be observed by this method because it receives a bool value, not provider. No actual live workload was started.

### Verdict and reasoning
CONFIRMED for one invocation's snapshot guard; not evidence real scheduler invokes it during active LIVE. Severity S2.

### Root cause
The public API accepts fixed `utc_hhmm` and `live_workload` values and checks them once before evaluating cells.

### Direct impact
If workload begins mid-run, remaining cells continue in this call. Potential resource contention only; no trading side effects shown.

### Secondary effects and interactions (upstream/downstream)
Upstream schedule state is not refreshed; outputs are research-only suggestions/checkpoints. Any external owner supervisor could still stop the process, unexamined.

### Contract and decisions
APEX_GEN5 §18.2 W.4 says optimization immediately halts when live workload detected. D3 does not weaken that. No later ruling found.

### Frozen status and non-frozen alternative
Non-frozen optimizer/supervisor adapter; add async provider at safe points and preserve checkpoint semantics. Existing expected completion tests change; no DB migration unless persisting halt cause.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — re-check workload/time at each cell and checkpoint a named halt. Non-frozen scheduler/optimizer; interruption changes may affect expected run completion and need resume tests, no frozen change.

### My recommendation
Independent severity S2; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-024

### Auditor claim (short quote)
Grid parameter names are not checked against optimizer scope/RED LINE before evaluation.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-025

### Auditor claim (short quote)
Risk objective trusts aggregate inputs and does not enforce per-trade capital/leverage limits.

### What I read (files, line ranges, functions, callers)
Read complete risk_objective function in optimizer.py. It receives aggregate max drawdown, a single leverage_adherence scalar, and regime mapping; no per-trade inputs. Caller composition not proven.

### Reproduction (command, probe file, actual result)
Real function probe with five regimes each zero, drawdown 0, adherence 1 returns `feasible=true`, value=1.0. Source checks only scalar adherence and presence of regime names, not finite values. Synthetic objective only.

### Verdict and reasoning
CONFIRMED for absence of per-trade enforcement in this function. This function may rely on evaluator to compute truthful summaries; a full bypass of W.2 is not proven. Severity S1 because objective can accept claimed summary without evidence.

### Root cause
API shape cannot inspect each trade or capital exposure; regime check only checks keys, accepts None/non-finite values after no conversion on them.

### Direct impact
Risk candidate may be declared feasible from optimistic aggregate data despite an individual bound violation; no actual candidate or order was made.

### Secondary effects and interactions (upstream/downstream)
Upstream evaluator owns unvalidated summarization; downstream optimizer H-021 may choose infeasible result. Governance cap checks might still block injection, not read here.

### Contract and decisions
APEX_GEN5 §18.2 W.2 requires 100% adherence each trade and five regime stability. No owner decision found allowing aggregate-only evidence.

### Frozen status and non-frozen alternative
Non-frozen objective/evaluator seam; retain owner hard ceilings and add traceable per-trade receipt. Callers and test fixtures change; cached objective results/promotion records invalidated, no DB migration if stored payload expands compatibly.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — pass per-trade exposure/limit evidence and enforce all trades, and require finite five-regime metrics. Non-frozen objective API; callers/tests and candidate identity change; no order path should consume prior summary-only approvals.

### My recommendation
Independent severity S1; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-026

### Auditor claim (short quote)
Promotion gate trusts caller flags even when underlying reported metrics contradict them.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-027

### Auditor claim (short quote)
Promotion candidate family is not required to match the FamilyPool family.

### What I read (files, line ranges, functions, callers)
Read full `PromotionCandidate.gates` and `FamilyPool` implementation. FamilyPool itself rejects a trade whose family differs from its own ID.

### Reproduction (command, probe file, actual result)
Probe uses 30 accepted Family-A trades and PromotionCandidate family B with positive other gate flags. Real `candidate.gates()` returns decision PROMOTE and family_id B. No package write or live operation.

### Verdict and reasoning
CONFIRMED for candidate-vs-pool family mismatch. Promotion verdict is pre-paper and not owner approval. Severity S1 because evidence can cross family boundaries.

### Root cause
Candidate.gates passes its pool to family_pool_gate but never compares `candidate.family_id` with `pool.family_id`; returned verdict labels candidate family.

### Direct impact
Family-A wins/counts can qualify Family-B package; downstream draft may be misattributed. No actual package injection proven.

### Secondary effects and interactions (upstream/downstream)
Trade family is validated inside pool; bridge from pool to candidate is missing; governance/owner approval remains a later barrier.

### Contract and decisions
APEX_GEN5 §§18.3 Z.1–Z.4 define a single setup family as the sample unit; W.5 validates candidate package. No decision permits cross-family pooling.

### Frozen status and non-frozen alternative
Promotion non-frozen. Add equality guard and propagate family ID in evidence; update tests and invalidate every affected promotion verdict/package draft; no DB migration unless persisted family receipt changes.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — assert family equality across candidate, pool, WFO, PBO, DSR, benchmark and package. Non-frozen promotion layer; reject cross-family cached evidence and re-run affected candidates.

### My recommendation
Independent severity S1; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-028

### Auditor claim (short quote)
FamilyPool trusts caller-supplied r_multiple and accepts non-deduplicated outcomes.

### What I read (files, line ranges, functions, callers)
Read entire frozen `Trade` definition, BacktestEngine result construction, and FamilyPool.add/wins/gate. Direct consumers found in promotion, unit tests, optimizer pathways; actual fills not supplied.

### Reproduction (command, probe file, actual result)
Probe creates 30 real `Trade` objects with entry 100, exit 90, long direction, stop 99, but r_multiple=+1; FamilyPool accepts all and reports n=30,wins=30,eligible=true. Synthetic inconsistent dataclass objects only.

### Verdict and reasoning
CONFIRMED that pool trusts supplied r_multiple and does not recompute outcome or deduplicate identities. It does not prove real producer emits such inconsistent trades; severity S1 because pooling gate uses those fields.

### Root cause
`Trade.win` returns `r_multiple>0`; FamilyPool.add checks family, ATR>0 and entry-stop distance only. It does not reconcile price/direction/cost or event identity.

### Direct impact
Inconsistent or duplicate outcomes can inflate trade count and Wilson lower bound, qualifying pool. Real source frequency not measured.

### Secondary effects and interactions (upstream/downstream)
BacktestEngine creates trades from its own formula; alternate callers can construct Trade directly. Promotion trusts the pool; upstream fill identity lineage absent in Trade schema.

### Contract and decisions
APEX_GEN5 §18.3 Z.2/Z.3/Z.4 requires real entry/exit/fill/cost outcomes and cost-adjusted success; no owner exception.

### Frozen status and non-frozen alternative
Trade type is frozen. Non-frozen FamilyPool validator can enforce price/R consistency and dedupe by a stable receipt; direct Trade correction requires owner ruling. Pool stats/promotion reports invalidated and recomputed; no retraining.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — derive outcome and R from fills/price/stop and dedupe stable event identity. `Trade` is in frozen backtest; an outside promotion validator can reject inconsistent outcomes but cannot fix untrusted construction. Recompute pooled stats and promotion artifacts.

### My recommendation
Independent severity S1; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-029

### Auditor claim (short quote)
Zero-sample shrinkage returns full cell weight; helper is not connected to promotion.

### What I read (files, line ranges, functions, callers)
Read complete shrinkage helpers and family promotion gate in promotion.py. Search within file shows `shrink_cell_rate` is not used by `family_pool_gate` or `evaluate_promotion`.

### Reproduction (command, probe file, actual result)
Probe real functions with cell_n=0, variance=0, rate=1, family_rate=.3 returns lambda=1.0 and shrunk_rate=1.0; family pool decision path is separate. No consumer/runtime tested.

### Verdict and reasoning
CONFIRMED at helper API and confirmed this helper is not wired into promotion path in the source searched. Severity S2 because isolated helper is not current promotion decision path.

### Root cause
Zero denominator has special case lambda=1, and no active path invokes shrinkage helper.

### Direct impact
An external consumer could overtrust a zero-observation cell; current family-pool gate does not call it, limiting present effect.

### Secondary effects and interactions (upstream/downstream)
No upstream cell count verification or downstream pooling consumer identified. Must not claim live or current promotion impact.

### Contract and decisions
APEX_GEN5 §18.3 Z.5 requires shrinkage toward family rate. Source helper implements edge opposite to prior, but active promotion wiring is absent; design intent does not imply currently executed.

### Frozen status and non-frozen alternative
Non-frozen promotion. Explicit n=0 prior/unavailable behavior and approved consumer; tests/consumers change. No hashes unless shrinkage outputs persist; no DB migration/retraining currently.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — define n=0 shrinkage as family prior/unavailable and explicitly wire only under approved protocol. Non-frozen promotion; tests/consumer behavior change; no model retraining unless this enters runtime decisions.

### My recommendation
Independent severity S2; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-030

### Auditor claim (short quote)
SPRT rollback action strings are not connected to durable halt/close/rollback operations.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-031

### Auditor claim (short quote)
No persistent nightly/continuous orchestration path was found in examined research/bootstrap consumers.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-032

### Auditor claim (short quote)
FamilyPool serialization references nonexistent Trade.stop_distance.

### What I read (files, line ranges, functions, callers)
Read complete `FamilyPool.to_dict`, `Trade` fields and property set. The direct serializer caller search is limited to grep, no actual runtime caller identified.

### Reproduction (command, probe file, actual result)
Probe calls `pool.to_dict()` on a nonempty pool. Real result: `AttributeError: 'Trade' object has no attribute 'stop_distance'`. Empty pool avoids generator expression. Synthetic trade only.

### Verdict and reasoning
CONFIRMED for nonempty serializer failure; report correctly notes evaluate_promotion does not require this serializer. Independent severity S2, not all promotion broken.

### Root cause
Serializer's generator refers to a nonexistent Trade property; Trade stores stop_price, entry_price and atr.

### Direct impact
Audit export of nonempty FamilyPool fails; promotion gates may still run. Provenance/audit output could be missing if this method is used.

### Secondary effects and interactions (upstream/downstream)
Upstream pool valid; downstream serialization consumer unknown. No DB or runtime route proven.

### Contract and decisions
APEX_GEN5 §18.3 Z.2 requires pooled-family reporting; no later decision specifies this serializer. Frozen Trade type means prefer adapter-side calculation.

### Frozen status and non-frozen alternative
Promotion serializer is not frozen; derive normalized risk from actual available fields in serializer. No Trade schema/hash changes if output meaning retained, but serializer golden tests/reports need update; no migration/retraining.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — serialize ATR-normalized risk from existing Trade fields, not nonexistent property. `Trade` class is in frozen backtest, but the non-frozen serializer can derive from `abs(entry-stop)` and ATR. Update serialization tests and no training needed.

### My recommendation
Independent severity S2; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-033

### Auditor claim (short quote)
Checkpoint upserts allow stale writes to regress status/payload while retaining a higher cursor.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-034

### Auditor claim (short quote)
Composite forecast estimate accepts missing component-quality metadata and yields an active estimate.

### What I read (files, line ranges, functions, callers)
Read full logistic.py, especially composite_estimate, build_forecast and D58 comments; grep shows production callers of build_forecast are engine_context and plan_bridge, while no production caller of composite_estimate. Contract Ch.13 §13.1 requires component n_obs/minimum and quality-weighted U/C; PHASE2_DECISION_LOG D58 (1175–1177) later explicitly leaves composite NOT_WIRED.

### Reproduction (command, probe file, actual result)
Command `PYTHONPATH=. python3 AUDIT/probes_V5/backtest_research_claims.py`; real `composite_estimate` with one synthetic f component p=.99,n_obs=1 returns p_hat=.99, weights f=1, shrinkage=[], U=.2,C=.8,state ACTIVE. Raw output in `backtest_research_claims.out`. This demonstrates only the standalone API, not real-data use; D58 says not wired.

### Verdict and reasoning
CONFIRMED for exposed standalone API accepting missing metadata and returning ACTIVE. PARTIAL in operational significance: D58 says it is NOT_WIRED, so no current trade effect proven. Severity S2.

### Root cause
Optional metadata defaults to zero and shrinkage only executes if Bayesian component b is present; API returns active regardless of sample count when b absent.

### Direct impact
Potential overconfident standalone forecast estimate; no current downstream plan uses this function, as direct grep found none.

### Secondary effects and interactions (upstream/downstream)
Inputs unverified; outputs are not consumed by build_forecast or production callers. Do not infer calibrated LIVE or PAPER use.

### Contract and decisions
Ch.13 §13.1 composite rules require small-sample weight shift toward Bayesian and component quality. D58 is later/binding and explicitly leaves this formula unwired; severity is bounded accordingly.

### Frozen status and non-frozen alternative
Non-frozen logistic file. Keep D58 unwired; add validated producer/adapter schema before wiring, avoiding direct path. If API semantics/output change, version identity and regression tests; no DB migration or training before persistence/wiring.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — validate complete component provenance/quality and make insufficient data unavailable; keep composite unwired per D58. Non-frozen logistic implementation but adapter alternative exists; forecast identities/calibration outputs change, no DB migration until persistence is added.

### My recommendation
Independent severity S2; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## H-035

### Auditor claim (short quote)
Forecast invalidation is an in-memory method with no production consumer/persistence path.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-036

### Auditor claim (short quote)
Bootstrap CVaR is a signed tail mean, not positive portfolio loss validated at the risk boundary.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## H-037

### Auditor claim (short quote)
ATR scaling is treated as proof that pooled family trades are independent observations.

### What I read (files, line ranges, functions, callers)
Read full promotion family pooling/Wilson code and contract Z.2/Z.3. Code accepts each trade and applies ordinary Wilson to n/wins; no cluster/time dependence adjustment. No real outcomes reviewed.

### Reproduction (command, probe file, actual result)
The report supplies a synthetic six-cluster comparison; I did not recreate its precise Wilson values. Source-only evidence confirms the implementation counts every trade as one observation. No market/device proof.

### Verdict and reasoning
PARTIAL: code and contract establish ATR-scale normalization and pooled Wilson count, but ATR normalization does not by itself demonstrate statistical independence. Contract Z.2 itself asserts independent samples from scale invariance; the empirical correlation structure is unknown. Do not claim actual promotion was false or real trades are dependent. Severity S2.

### Root cause
Scale normalization solves price-unit comparability, not sampling dependence; code has no cluster/time correlation model.

### Direct impact
Reported Wilson interval may be overconfident if trades are dependent; only a theoretical/data-dependent risk in this checkout, not measured on actual outcomes.

### Secondary effects and interactions (upstream/downstream)
Upstream trades/outcome IDs and timestamps are not clustered here; downstream family promotion uses Wilson gate. Other gate evidence still applies.

### Contract and decisions
APEX_GEN5 §18.3 Z.2 explicitly calls 42 trades independent because ATR normalized; Z.3 applies Wilson. No later owner decision found replacing it. Contract is normative but its statistical justification is a separate assumption.

### Frozen status and non-frozen alternative
Promotion code non-frozen; contract §18.3 is normative, so changing acceptance requires owner ruling. Can add dependence diagnostics outside core first; changing CI invalidates family verdicts and requires revalidation, no training/migration.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A — document independence as an assumption or use dependence-aware effective sample/cluster interval. Promotion protocol is non-frozen but contract Z.2 is normative; owner decision required before changing statistical acceptance, recompute all family gates and do not treat ATR as proof.

### My recommendation
Independent severity S2; bounded to the evidence described above.

### Acceptance and regression tests
Run row-specific regression tests against the contract and ensure the proposed fix does not alter frozen hashes/schema unintentionally. Real-device/data evidence, if required, remains a separate acceptance gate.


## I-001

### Auditor claim (short quote)
Config tests assume the classifier artifact is absent, making results sensitive to device artifacts.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## I-002

### Auditor claim (short quote)
Config/foundation tests leave parser, installation, immutability, and fixture boundary gaps.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## I-003

### Auditor claim (short quote)
Paper harness injects fake adapter/clock and labels weak ACK/pause behavior as success.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## I-004

### Auditor claim (short quote)
Integration tests do not establish a fully native, validated evidence-to-plan composition.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## I-005

### Auditor claim (short quote)
CP-3 historical status does not prove current tests cover reported engine edge cases.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## I-006

### Auditor claim (short quote)
Several nominal CP-3 OHLC fixtures violate candle geometry but bypass production validation.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## I-007

### Auditor claim (short quote)
Traceability matrix references several nonexistent pytest node IDs.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## I-008

### Auditor claim (short quote)
CP-3 store test inserts only the first 30 concatenated events, all from E04.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## I-009

### Auditor claim (short quote)
CP-4/5 integration fixtures include bars later than their stated as_of.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## I-010

### Auditor claim (short quote)
Snapshot duplicate tests prove evidence_id uniqueness, not snapshot uniqueness.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## I-011

### Auditor claim (short quote)
CP-4/5 tests exercise helper paths and vacuous fixtures rather than native gates.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## I-012

### Auditor claim (short quote)
Adapter conformance can report closure from repeated synthetic records without real export provenance.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## I-013

### Auditor claim (short quote)
Adapter harness verdict ignores a failed supplied legacy export when synthetic tests pass.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## I-014

### Auditor claim (short quote)
RED LINE test refuses an absent proposal rather than a complete proposal touching a veto.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## I-015

### Auditor claim (short quote)
NFR harness may return measured-in-bounds despite injected failed queue/resource results.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## I-016

### Auditor claim (short quote)
CP-7 test double acknowledges orders without fills while test logic writes full fills/closed ledger.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.


## I-017

### Auditor claim (short quote)
Fake venue accepts unsigned private requests and shares signing implementation with SUT.

### What I read (files, line ranges, functions, callers)
Incomplete. I extracted the complete audit row from `/tmp/AUDIT.md` (source report commit 015d19b). I did not read all cited source/test files, complete functions and callers/callees, governing clauses and decisions, or the composition-root trace required for a verdict. No source finding is adopted.

### Reproduction (command, probe file, actual result)
Not reproduced. No command/probe result is claimed for this ID. A test suite pass, fixture, or auditor-supplied reproduction is not independent proof.

### Verdict and reasoning
UNVERIFIED. This is not a rejection, confirmation, or device-evidence verdict. Severity is not independently assigned.

### Root cause
Not determined; do not infer from the report title or code names.

### Direct impact
Not determined.

### Secondary effects and interactions (upstream/downstream)
Not traced upstream or downstream; no claim regarding decision/risk/order/ledger/hash/training/replay path.

### Contract and decisions
Governing clause and owner-decision precedence were not fully located/quoted for this row; no contract conclusion.

### Frozen status and non-frozen alternative
Frozen status is a preliminary path-based estimate only where shown in summary; no fix authorization. Required alternative outside frozen code not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
No fix recommendation until verified. Do not apply auditor proposal based on this incomplete review.

### My recommendation
My recommendation is to leave source untouched and complete the mandated review before making a change.

### Acceptance and regression tests
No acceptance criteria validated; requires full function/caller/callee, contract/decision, relevant test/probe, and effect tracing.

## New findings not in the audit

### X-V5-001

### Auditor claim (short quote)
Observed targeted test execution depends on a historical Git object unavailable in the supplied baseline checkout (`f14be36:params/...`).

### What I read (files, line ranges, functions, callers)
`tests/unit/test_research_governance.py::TestLiveParamsWriteForbidden::test_frozen_params_files_are_untouched_by_this_suite` and its direct test invocation; `git cat-file -e f14be36^{commit}`. The test references six YAML files in that base revision. I did not read the complete test file; this finding is strictly about the observed failure.

### Reproduction (command, probe file, actual result)
Command: `python3 -m pytest -q -p no:cacheprovider tests/unit/test_research_backtest.py tests/unit/test_research_optimizer.py tests/unit/test_research_promotion.py tests/unit/test_research_governance.py tests/unit/test_research_checkpoints.py tests/unit/test_research_bootstrap.py tests/unit/test_research_proxies.py tests/unit/test_forecast_logistic.py`. Raw result `AUDIT/probes_V5/pytest_research.out`: 316 passed, 1 failed at `git show f14be36:params/universe_v1.yaml`; `git cat-file` says invalid object name. No source/config file was changed.

### Verdict and reasoning
CONFIRMED as a test-environment reproducibility issue only. It does not prove production defect or frozen-file mutation. Severity S2 for validation portability/reproducibility.

### Root cause
The test hardcodes a base commit that is not present/reachable in this shallow/limited-history checkout; assertion cannot run before parsing current files.

### Direct impact
The governance test suite exits nonzero despite other tests passing, so a clean test signal cannot be obtained from this checkout without the object or a test adjustment.

### Secondary effects and interactions (upstream/downstream)
Upstream checkout history is incomplete; downstream CI verdict/test reliability is affected. No source runtime behavior is inferred.

### Contract and decisions
No contract clause requires this commit SHA; owner decision/frozen-file policy not checked. This does not override any freeze.

### Frozen status and non-frozen alternative
Test-only, non-frozen. Best alternative is pin the base fixture content/hash in a test fixture or explicitly fetch the immutable test base in CI. Do not change frozen YAML. Existing baseline-comparison coverage must remain equivalent; test snapshot updates need review.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
Single path: make the test independent of unadvertised local object availability while preserving frozen-file comparison.

### My recommendation
Recommend as a reproducibility issue, not as a product defect; no further fix applied.

### Acceptance and regression tests
Acceptance: on a fresh checkout without f14be36, the test can execute deterministically and still detects unauthorized changes to each of six files; validate both clean and deliberate changed fixture cases.

## Rows not verified or incomplete

No coverage claim is made for the following 35 IDs. Each was extracted in full from the audit row, but the mandatory full-file/function/test read, consumer search, governing clause/decision precedence, reproduction and two-way effect trace was not completed; therefore each remains UNVERIFIED:

`H-002, H-003, H-004, H-005, H-006, H-007, H-008, H-010, H-011, H-012, H-013, H-024, H-026, H-030, H-031, H-033, H-035, H-036, I-001, I-002, I-003, I-004, I-005, I-006, I-007, I-008, I-009, I-010, I-011, I-012, I-013, I-014, I-015, I-016, I-017`.

Rows with a non-UNVERIFIED status were independently evidenced only to the exact scope stated in their sections. Synthetic tests do not establish real data/device/model behavior. In particular, H-022 and H-034 have a partial caller/governance/integration review caveat in their individual sections; their verdicts are limited to the function-level behavior reproduced/read. Full V5 acceptance requires completing all unverified rows, mandatory caller/callee and test reads, and relevant SQLite plan checks where applicable.

## Final counts

| Verdict | Count |
|---|---:|
| CONFIRMED | 17 |
| PARTIAL | 2 |
| REJECTED | 0 |
| UNVERIFIED / incomplete | 35 |
| DEVICE-EVIDENCE-NEEDED | 0 (no real-device dependent claim was assigned this verdict; device evidence was not obtained) |

New finding: `X-V5-001` (test reproducibility dependency on unavailable base commit).
