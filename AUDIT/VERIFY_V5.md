# Independent verification — APEX_GEN5 audit, Session V5

## Summary table

| ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option |
|---|---|---:|---:|---|---|---|
| H-001 | CONFIRMED | S1 | S1 | No | = ISSUE-076; delta: required per-cell G-PAPER-001 receipt/envelope details | A — implement the normative replay CLI as a non-network, read-only runner; CP-15 owns it. No frozen file change if composed outside backtest; acceptance hashes change only when replay outcome changes. |
| H-002 | CONFIRMED | S1 | S1 | Partial | = D21; independent producer persistence gap; R-019 is separate | A — preserve prior confirmed E11 state across chronologically ordered calls/restarts, keyed by symbol/timeframe/artifact and PIT; separately test journal vs EvidenceEvent so R-019 is not conflated. Non-frozen producer/state adapter; no frozen engine edit. Re-run deterministic replay and restart/correction tests. |
| H-003 | CONFIRMED | S1 | S1 | Yes | = D21 + E11 §3.8 shock-gap; training/inference projection parity delta | A — share the governed gap-adjusted projection before training X/rule0 and runtime EWMA/softmax, or obtain an explicit owner ruling for divergence. E11 engine is frozen: no edit without authorization; training-side alternative changes labels/features and invalidates cache, fitted W/b, and replay evidence. |
| H-004 | PARTIAL | S1 | S2 | Partial | E11 §§1.2, 3.4–3.9, 8.5; D21/D23/D49 do not identify runtime source | A — obtain owner decision on the PIT T and outcome/BaseRate source; until then represent unavailable separately and do not synthesize counts. E11 engine is frozen; adapter-only provider option, or owner-approved schema contract. Revalidate quality/replay if inputs change. |
| H-005 | CONFIRMED | S1 | S1 | Partial | = D35 cache compatibility; D47 digest is artifact-only, not cache identity | A — add governed code/feature-policy identity to cache namespace/input manifest only with owner approval; preserve D35 resume behavior and prove old cache invalidation. Non-frozen changes; invalidates cache files and affected samples/artifacts, not raw data. |
| H-006 | CONFIRMED | S2 | S2 | No | = D47 hash scope; provenance sidecar absent | A — retain D47 artifact_sha256 meaning, add independently authenticated provenance manifest binding sample count, query, cell scope and time window; reject mismatches. New schema/identity needs owner approval and invalidates downstream fit evidence, not the frozen E11 code. |
| H-007 | CONFIRMED | S1 | S1 | Partial | = D21 PIT t−48 + D47 schema; historical version selection absent | A — publish model fit/deploy/label-maturity time and select only a version available at the requested as_of; replay must use walk-forward versions. Non-frozen loader/producer adapter; no D47 hash redefinition. Historical decisions and replay hashes require recomputation. |
| H-008 | PARTIAL | S1 | S2 | No | = D23; PAPER context refuses when latest OI is absent, before risk input | A — retain named OI-unavailable refusal; add producer/bridge regression proving no risk decision with missing OI, while preserving D23 E11 partial-quality behavior. Non-frozen producer/adapter only; do not relax refusal or change frozen engines. |
| H-009 | CONFIRMED | S1 | S2 | Yes | D6/P4 (Phase-2 entry gate) | A — validate structured replay receipt and critical failures before defaults_active; persist a receipt. Non-frozen bootstrap adapter/service alternative; existing tests expecting arbitrary callbacks to activate will need tightening. |
| H-010 | PARTIAL | S1 | S2 | No | = D30 effective/requested scope is not a per-cell yield guarantee | A — keep selected-scope semantics; expose per-cell contributing sample counts in the final report/provenance if owners require realized coverage. No E11/frozen change; preserve the 20-cell default and nine-class refusal. |
| H-011 | CONFIRMED | S1 | S1 | Partial | = D35 cache resume; distinct from H-005 identity | A — validate/attest cached sample payload against recomputation or an owner-approved manifest before it can enter fit; malformed or tampered-but-well-shaped payload must miss/refuse. Preserve D35 resume only for verified payloads; recompute affected cells and invalidate affected model evidence. |
| H-012 | PARTIAL | S1 | S2 | Partial | = D35 bar cap; CP-15 ISSUE-076 owns index work, not caller-side cap pushdown | A — pass the cap into the non-frozen training read path before window/lineage materialization, while retaining latest-N semantics and cache identity. Frozen SQLiteStore stays untouched; re-run parity/cache tests. |
| H-013 | CONFIRMED | S2 | S2 | No | = D49 governed threshold; research-only | A — remove silent legacy fallback; fail with named configuration status or mark report INVALID with fallback source explicitly identified. Research-only change; does not change runtime classifier or frozen files, but invalidates affected fit-study reports and human decisions based on them. |
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
| H-024 | PARTIAL | S2 | S2 | No | = W.1 scope enforcement gap; W.5 RED LINE is a pre-paper-trial validation contract, not proof of live bypass | A — reject grid keys outside the selected optimizer scope before evaluation; validate RED LINE fields before candidate/paper-trial handoff. Optimizer/tests only; suggestions remain research-only and frozen params untouched. |
| H-025 | CONFIRMED | S1 | S1 | No | — | A — pass per-trade exposure/limit evidence and enforce all trades, and require finite five-regime metrics. Non-frozen objective API; callers/tests and candidate identity change; no order path should consume prior summary-only approvals. |
| H-026 | CONFIRMED | S1 | S1 | Partial | = W.5 / Z.9 gates are caller-asserted summaries; probe reaches DRAFTED, owner approval still required | A — bind promotion flags to recomputed metrics or verified provenance; fail closed on contradictions before `PROMOTE`/draft. Non-frozen promotion adapter only; frozen backtest untouched, old promotion evidence invalidated. |
| H-027 | CONFIRMED | S1 | S1 | No | — | A — assert family equality across candidate, pool, WFO, PBO, DSR, benchmark and package. Non-frozen promotion layer; reject cross-family cached evidence and re-run affected candidates. |
| H-028 | CONFIRMED | S1 | S1 | Partial | — | A — derive outcome and R from fills/price/stop and dedupe stable event identity. `Trade` is in frozen backtest; an outside promotion validator can reject inconsistent outcomes but cannot fix untrusted construction. Recompute pooled stats and promotion artifacts. |
| H-029 | CONFIRMED | S2 | S2 | No | — | A — define n=0 shrinkage as family prior/unavailable and explicitly wire only under approved protocol. Non-frozen promotion; tests/consumer behavior change; no model retraining unless this enters runtime decisions. |
| H-030 | PARTIAL | S1 | S2 | Partial | = W.5/Z.6 action contract; checkpoint monitor-log API exists but is not wired to LiveFamilyMonitor/runtime | A — connect family SPRT verdicts to durable logging and authorized halt/position-management actions; do not equate the returned string or in-memory flag with execution. Separate from D57 watchdog escalation. |
| H-031 | CONFIRMED | S2 | S2 | Partial | = W.4 schedule/continuous contract; BootstrapRunner returns a Phase-3 plan only, no optimizer loop | A — add a non-frozen persistent scheduler/runner with checkpointed restart and owner-controlled start/stop; bootstrap.py is frozen, so compose outside it. No device scheduler was inspected. |
| H-032 | CONFIRMED | S2 | S2 | Partial | — | A — serialize ATR-normalized risk from existing Trade fields, not nonexistent property. `Trade` class is in frozen backtest, but the non-frozen serializer can derive from `abs(entry-stop)` and ATR. Update serialization tests and no training needed. |
| H-033 | CONFIRMED | S1 | S2 | Partial | = W.6 cursor never rewinds; CP9-007 mirror exists, but status/payload lack stale-generation guards | A — add per-run generation/CAS protection for status and payload while retaining monotone cursor; preserve intentional resume transitions and CP13 evidence carry-forward. Non-frozen checkpoint/wiring only. |
| H-034 | CONFIRMED | S2 | S2 | No | = D58 for NOT_WIRED; delta: standalone estimate accepts incomplete components | A — validate complete component provenance/quality and make insufficient data unavailable; keep composite unwired per D58. Non-frozen logistic implementation but adapter alternative exists; forecast identities/calibration outputs change, no DB migration until persistence is added. |
| H-035 | PARTIAL | S2 | S2 | No | = Ch.13 §13.1/T_FORECAST_INV; forecast object is serializable but invalidation has no production caller or durable lifecycle | A — retain the immutable invalidation rule and wire an owner-approved forecast lifecycle adapter with durable lineage; do not imply current PaperPlanBridge traces are persistent. D54 remains open and is not silently resolved. |
| H-036 | CONFIRMED | S2 | S2 | Yes | = APEX_GEN5 §15 tail-risk contract; signed return-tail statistic is not the positive portfolio-loss fraction consumed by Risk Kernel | A — keep frozen backtest helper semantics unchanged; add an approved adapter that derives/validates positive portfolio-loss CVaR from current positions/correlation/window and records provenance before passing it to the Risk Kernel. No current PAPER risk input is wired. |
| H-037 | PARTIAL | S2 | S2 | No | — | A — document independence as an assumption or use dependence-aware effective sample/cluster interval. Promotion protocol is non-frozen but contract Z.2 is normative; owner decision required before changing statistical acceptance, recompute all family gates and do not treat ATR as proof. |
| I-001 | PARTIAL | S2 | S2 | No | = CP-1 config/parameter-loader checks and D24 missing-artifact behavior; test binds directly to the gitignored runtime artifact path | A — preserve D24 absent/present semantics but run the assertion against an isolated temporary params root; no production fallback or classifier commit. The test is filesystem-sensitive and does not prove run_apex→PaperRuntime composition. |
| I-002 | PARTIAL | S2 | S2 | No | = CP-1 Part I tests prove pinned metadata/literals, not parser rejection, installation, or immutable Params; CP-14 separately covers fixture boundary | A — add hermetic parser/immutability/install assertions; retain CP-14 fixture separation and do not broaden matrix claims beyond asserted scope. No source/frozen change in this audit. |
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

Audit source-line baseline is `85b2c155d7b054a468379ddfd802eb239d0801f9` (`85b2c15 Merge pull request #25 from sinamoosazadeh/arena/01a0d98b-upstage`); it remains present and all source line references in this report are against that baseline. At this continuation the audit branch HEAD before these edits was `12d917f0626b90e76ddc1863ebb3c6da59d3b540`; this is not the source-line baseline. No product/source/config/test file was modified. Audit source: commit `015d19bd6ec1956b853fd566157a929f9f95f260`; index commit `690e2d8899319a7c7a96456f92c3008878e59346`.

Scope note: this is a read-only, evidence-bounded verification. Synthetic probes prove only the invoked code path, not device/database/model/exchange behavior. No `.env`, secret, `data/`, model artifact, network endpoint, or real trading operation was accessed. `requirements.lock` was installed only into the execution environment; no tracked dependency file changed.

## Evidence and method

Baseline source files were not changed. Selected actual-repository probes are in `AUDIT/probes_V5/`. Recorded commands/results:

- `phase2_forecast.py` with real `BootstrapRunner`, real forecast functions and a disposable temp SQLite checkpoint; raw output `phase2_forecast.out`.
- `backtest_research_claims.py` imports actual backtest/optimizer/promotion code and uses synthetic in-memory values; raw output `backtest_research_claims.out`.
- `training_e11_claims.py` calls real E11 hysteresis/vector/inference, cache hash/read/write, classifier validation, and research fit-study functions using synthetic fixture/rows; raw output `training_e11_claims.out`. It creates no production cache or model artifact and makes no device/data claim.
- Targeted tests: `pytest_research.out` (316 passed, 1 failed; existing governance test invokes unavailable git object `f14be36`); `pytest_context_integration.out` (22 passed, 13 warnings). These green tests are not a device/model/data acceptance result.
- The engine-context/store-source relevant suite was run as `python3 -m pytest -q -p no:cacheprovider tests/unit/test_engine_context.py tests/integration/test_context_to_trade_paper.py tests/integration/test_cp14_producer.py`: 249 passed, 13 warnings, 1129.21 s (tool raw output was not persisted as a separate file). It is test evidence only.
- No SQL-per-row/cell/bar query performance audit was completed in V5; no performance claims about actual device data are made.

## Row-by-row review
| H-001 | CONFIRMED | S1 | S1 | No | = ISSUE-076; delta: required per-cell G-PAPER-001 receipt/envelope details | A — implement the normative replay CLI as a non-network, read-only runner; CP-15 owns it. No frozen file change if composed outside backtest; acceptance hashes change only when replay outcome changes. |
| H-002 | CONFIRMED | S1 | S1 | Partial | = D21; independent producer persistence gap; R-019 is separate | A — preserve prior confirmed E11 state across chronologically ordered calls/restarts, keyed by symbol/timeframe/artifact and PIT; separately test journal vs EvidenceEvent so R-019 is not conflated. Non-frozen producer/state adapter; no frozen engine edit. Re-run deterministic replay and restart/correction tests. |
| H-003 | CONFIRMED | S1 | S1 | Yes | = D21 + E11 §3.8 shock-gap; training/inference projection parity delta | A — share the governed gap-adjusted projection before training X/rule0 and runtime EWMA/softmax, or obtain an explicit owner ruling for divergence. E11 engine is frozen: no edit without authorization; training-side alternative changes labels/features and invalidates cache, fitted W/b, and replay evidence. |
| H-004 | PARTIAL | S1 | S2 | Partial | E11 §§1.2, 3.4–3.9, 8.5; D21/D23/D49 do not identify runtime source | A — obtain owner decision on the PIT T and outcome/BaseRate source; until then represent unavailable separately and do not synthesize counts. E11 engine is frozen; adapter-only provider option, or owner-approved schema contract. Revalidate quality/replay if inputs change. |
| H-005 | CONFIRMED | S1 | S1 | Partial | = D35 cache compatibility; D47 digest is artifact-only, not cache identity | A — add governed code/feature-policy identity to cache namespace/input manifest only with owner approval; preserve D35 resume behavior and prove old cache invalidation. Non-frozen changes; invalidates cache files and affected samples/artifacts, not raw data. |
| H-006 | CONFIRMED | S2 | S2 | No | = D47 hash scope; provenance sidecar absent | A — retain D47 artifact_sha256 meaning, add independently authenticated provenance manifest binding sample count, query, cell scope and time window; reject mismatches. New schema/identity needs owner approval and invalidates downstream fit evidence, not the frozen E11 code. |
| H-007 | CONFIRMED | S1 | S1 | Partial | = D21 PIT t−48 + D47 schema; historical version selection absent | A — publish model fit/deploy/label-maturity time and select only a version available at the requested as_of; replay must use walk-forward versions. Non-frozen loader/producer adapter; no D47 hash redefinition. Historical decisions and replay hashes require recomputation. |
| H-008 | PARTIAL | S1 | S2 | No | = D23; PAPER context refuses when latest OI is absent, before risk input | A — retain named OI-unavailable refusal; add producer/bridge regression proving no risk decision with missing OI, while preserving D23 E11 partial-quality behavior. Non-frozen producer/adapter only; do not relax refusal or change frozen engines. |
| H-009 | CONFIRMED | S1 | S2 | Yes | D6/P4 (Phase-2 entry gate) | A — validate structured replay receipt and critical failures before defaults_active; persist a receipt. Non-frozen bootstrap adapter/service alternative; existing tests expecting arbitrary callbacks to activate will need tightening. |
| H-010 | PARTIAL | S1 | S2 | No | = D30 effective/requested scope is not a per-cell yield guarantee | A — keep selected-scope semantics; expose per-cell contributing sample counts in the final report/provenance if owners require realized coverage. No E11/frozen change; preserve the 20-cell default and nine-class refusal. |
| H-011 | CONFIRMED | S1 | S1 | Partial | = D35 cache resume; distinct from H-005 identity | A — validate/attest cached sample payload against recomputation or an owner-approved manifest before it can enter fit; malformed or tampered-but-well-shaped payload must miss/refuse. Preserve D35 resume only for verified payloads; recompute affected cells and invalidate affected model evidence. |
| H-012 | PARTIAL | S1 | S2 | Partial | = D35 bar cap; CP-15 ISSUE-076 owns index work, not caller-side cap pushdown | A — pass the cap into the non-frozen training read path before window/lineage materialization, while retaining latest-N semantics and cache identity. Frozen SQLiteStore stays untouched; re-run parity/cache tests. |
| H-013 | CONFIRMED | S2 | S2 | No | = D49 governed threshold; research-only | A — remove silent legacy fallback; fail with named configuration status or mark report INVALID with fallback source explicitly identified. Research-only change; does not change runtime classifier or frozen files, but invalidates affected fit-study reports and human decisions based on them. |
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
| H-024 | PARTIAL | S2 | S2 | No | = W.1 scope enforcement gap; W.5 RED LINE is a pre-paper-trial validation contract, not proof of live bypass | A — reject grid keys outside the selected optimizer scope before evaluation; validate RED LINE fields before candidate/paper-trial handoff. Optimizer/tests only; suggestions remain research-only and frozen params untouched. |
| H-025 | CONFIRMED | S1 | S1 | No | — | A — pass per-trade exposure/limit evidence and enforce all trades, and require finite five-regime metrics. Non-frozen objective API; callers/tests and candidate identity change; no order path should consume prior summary-only approvals. |
| H-026 | CONFIRMED | S1 | S1 | Partial | = W.5 / Z.9 gates are caller-asserted summaries; probe reaches DRAFTED, owner approval still required | A — bind promotion flags to recomputed metrics or verified provenance; fail closed on contradictions before `PROMOTE`/draft. Non-frozen promotion adapter only; frozen backtest untouched, old promotion evidence invalidated. |
| H-027 | CONFIRMED | S1 | S1 | No | — | A — assert family equality across candidate, pool, WFO, PBO, DSR, benchmark and package. Non-frozen promotion layer; reject cross-family cached evidence and re-run affected candidates. |
| H-028 | CONFIRMED | S1 | S1 | Partial | — | A — derive outcome and R from fills/price/stop and dedupe stable event identity. `Trade` is in frozen backtest; an outside promotion validator can reject inconsistent outcomes but cannot fix untrusted construction. Recompute pooled stats and promotion artifacts. |
| H-029 | CONFIRMED | S2 | S2 | No | — | A — define n=0 shrinkage as family prior/unavailable and explicitly wire only under approved protocol. Non-frozen promotion; tests/consumer behavior change; no model retraining unless this enters runtime decisions. |
| H-030 | PARTIAL | S1 | S2 | Partial | = W.5/Z.6 action contract; checkpoint monitor-log API exists but is not wired to LiveFamilyMonitor/runtime | A — connect family SPRT verdicts to durable logging and authorized halt/position-management actions; do not equate the returned string or in-memory flag with execution. Separate from D57 watchdog escalation. |
| H-031 | CONFIRMED | S2 | S2 | Partial | = W.4 schedule/continuous contract; BootstrapRunner returns a Phase-3 plan only, no optimizer loop | A — add a non-frozen persistent scheduler/runner with checkpointed restart and owner-controlled start/stop; bootstrap.py is frozen, so compose outside it. No device scheduler was inspected. |
| H-032 | CONFIRMED | S2 | S2 | Partial | — | A — serialize ATR-normalized risk from existing Trade fields, not nonexistent property. `Trade` class is in frozen backtest, but the non-frozen serializer can derive from `abs(entry-stop)` and ATR. Update serialization tests and no training needed. |
| H-033 | CONFIRMED | S1 | S2 | Partial | = W.6 cursor never rewinds; CP9-007 mirror exists, but status/payload lack stale-generation guards | A — add per-run generation/CAS protection for status and payload while retaining monotone cursor; preserve intentional resume transitions and CP13 evidence carry-forward. Non-frozen checkpoint/wiring only. |
| H-034 | CONFIRMED | S2 | S2 | No | = D58 for NOT_WIRED; delta: standalone estimate accepts incomplete components | A — validate complete component provenance/quality and make insufficient data unavailable; keep composite unwired per D58. Non-frozen logistic implementation but adapter alternative exists; forecast identities/calibration outputs change, no DB migration until persistence is added. |
| H-035 | PARTIAL | S2 | S2 | No | = Ch.13 §13.1/T_FORECAST_INV; forecast object is serializable but invalidation has no production caller or durable lifecycle | A — retain the immutable invalidation rule and wire an owner-approved forecast lifecycle adapter with durable lineage; do not imply current PaperPlanBridge traces are persistent. D54 remains open and is not silently resolved. |
| H-036 | CONFIRMED | S2 | S2 | Yes | = APEX_GEN5 §15 tail-risk contract; signed return-tail statistic is not the positive portfolio-loss fraction consumed by Risk Kernel | A — keep frozen backtest helper semantics unchanged; add an approved adapter that derives/validates positive portfolio-loss CVaR from current positions/correlation/window and records provenance before passing it to the Risk Kernel. No current PAPER risk input is wired. |
| H-037 | PARTIAL | S2 | S2 | No | — | A — document independence as an assumption or use dependence-aware effective sample/cluster interval. Promotion protocol is non-frozen but contract Z.2 is normative; owner decision required before changing statistical acceptance, recompute all family gates and do not treat ATR as proof. |
| I-001 | PARTIAL | S2 | S2 | No | = CP-1 config/parameter-loader checks and D24 missing-artifact behavior; test binds directly to the gitignored runtime artifact path | A — preserve D24 absent/present semantics but run the assertion against an isolated temporary params root; no production fallback or classifier commit. The test is filesystem-sensitive and does not prove run_apex→PaperRuntime composition. |
| I-002 | PARTIAL | S2 | S2 | No | = CP-1 Part I tests prove pinned metadata/literals, not parser rejection, installation, or immutable Params; CP-14 separately covers fixture boundary | A — add hermetic parser/immutability/install assertions; retain CP-14 fixture separation and do not broaden matrix claims beyond asserted scope. No source/frozen change in this audit. |
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

### What I read (baseline line references; complete functions and callers)
`apex/ops/engine_context.py:1623–1633` creates the one-candle context and a new `E11RegimeEngine()` per completed bundle; the preparation path calls that bundle from `prepare_engine_bundle` (`:2283–2335`). `apex/engines/e11_regime/engine.py:675–701` is the complete `hysteresis_manager`; `run_engine` uses engine-local `hist_raw_states`/`last_confirmed` at `:937–940`; events are emitted at `:1016–1036`; the complete `E11RegimeEngine.compute` path is `:1450–1610`. Its constructor initializes those state fields for the instance. `feature_timeline` (`engine_context.py:2380–2540`) maintains normalization/EWMA history but does not carry the E11 engine's raw-label confirmation state. `grep -rn` consumer/caller search was run over `apex/`, `scripts/`, and `tests/unit/test_engine_context.py`; `prepare_engine_bundle` is the PAPER composition path, while timeline state is a distinct data structure. No product file changed.

### Reproduction (probe and actual result)
`PYTHONPATH=. python3 AUDIT/probes_V5/training_e11_claims.py`; raw output: `AUDIT/probes_V5/training_e11_claims.out`. The real helper returned persistent prior `RANGE` → (`RANGE`, `SUSPECTED`) for a new `CRISIS`, versus empty/fresh history → (`CRISIS`, `CONFIRMED`). This proves state-reset semantics, not a real market occurrence or downstream order.

### Verdict and independently assigned severity
**CONFIRMED, S1.** The producer recreates the engine at each one-close call, so ordinary E11 hysteresis does not see earlier raw states. Contract §2/§5.2 expects three consecutive raw labels for a changed confirmed regime (the implementation's helper explicitly enforces this). A fresh first candle is deliberately CONFIRMED by the helper, which is the reset edge. This finding concerns runtime's missing persisted/replayed prior state; it does not subsume R-019's distinct false EvidenceEvent catalog behavior, and the existence of another state store is not proof it preserves these labels.

### Root cause, direct impact, upstream/downstream
The composition root supplies no prior E11 confirmation journal/state in `regime_context`; the new engine starts with empty history. Consequently a one-candle regime change can become the bundle state and influence forecast/fabric and bridge risk decisions. I found no proof that a real order executed or that every plan becomes unsafe; PAPER has further gates. R-019 (first/unchanged EV_RGM_003 catalog entries) remains independent.

### Contract, decisions, and frozen status
E11 §2/§5.2 three-candle hysteresis and D21's PIT training label horizon apply; neither is overridden by D30 (which only sets 20 default base cells). E11 engine is frozen; only a non-frozen producer/state adapter or separately authorized engine change can address this. Preserve correction/restart semantics and distinguish journal transitions from catalog events.

### Fix options and side effects
A: replay/persist prior E11 state in timestamp order keyed by symbol/timeframe/model version, with deterministic recovery after restart/correction. Side effects: new state lineage/storage and historical replay identity; no fabricated transition on warm start. B: explicitly fail closed for state-dependent PAPER use when prior state is unavailable; safer but reduces availability. Do not remove the three-bar confirmation rule. Tests must separately assert E11 journal and EvidenceEvent outputs.

### Acceptance and regression tests
Synthetic prior RANGE→single CRISIS, CRISIS×3, transient CRISIS→RANGE, gap and clock discontinuity, correction, restart, artifact version change; compare uninterrupted and replayed confirmed state/event sequence exactly. Verify no false event or duplicated journal transition and no change to frozen files.


## H-003

### What I read (baseline line references; complete functions and callers)
`engine_context.py:836–857` is the full D21 `training_rule0`; `feature_timeline` projection/vector/update path is `:2380–2540` and computes `compute_state_vector` at `:2526–2531`; the runtime composition at `:1624–1632` builds its final one-candle context. In `apex/engines/e11_regime/engine.py`, the complete `compute_state_vector` is `:386–434`; runtime gap detection/override is `:907–913` and `_gap_detected` is `:1077–1089`; the remaining inference path then uses the adjusted vector for turbulence, logits and tree (`:914–940`). `grep -rn` was run for both training and E11 consumers in `apex/`, `scripts/`, and tests.

### Reproduction
Same synthetic baseline fixture GF_09_GAP_EDGE from `tests/fixtures/e11_golden_fixtures.json` was sent to real `compute_state_vector`, `training_rule0` and `run_engine` via `AUDIT/probes_V5/training_e11_claims.py`. Raw output shows training expansion `0.6899744803`, structure quality `0.3486451423`; inference gap-adjusted values are `1.0` and `0.2440515996`. Fixture's training rule0 is EXPANSION here; result proves vectors differ, not that every row's class changes. No real-data occurrence asserted.

### Verdict and independently assigned severity
**CONFIRMED, S1.** D21 says training uses §2 X_t and rule0 with the entropy branch removed; E11 §3.8 separately defines inference shock-gap adjustment. Current training projection has no equivalent adjustment, while runtime transforms expansion and structure quality before its E11 calculations. It is a feature-distribution mismatch on the gap path. The audit's stronger class-flip illustration is not generalized from this single fixture.

### Root cause, direct impact, upstream/downstream
The training timeline creates X/rule0 before runtime-only shock-gap projection. Training samples/cache and fitted W/b can therefore differ from runtime input for gaps; turbulence/EWMA also consumes the adjusted vector at runtime. This can impair calibration/decision quality during gap conditions. No device evidence, model quality result, or realized risk/order is established.

### Contract and decisions; frozen status
D21 (APEX_GEN5.md:11889–11894) governs training rule0/48-close delayed labels and PIT; E11 §3.8 (engine contract around the shock-gap edge) governs inference. The gap rule is in frozen `apex/engines/e11_regime/engine.py`; no product edit is authorized. No later owner decision reviewed overrides these clauses.

### Fix options and side effects
A: factor the governed projection into a shared, non-frozen feature adapter consumed by training and runtime only if this does not require modifying frozen E11; verify exact parity. B: obtain owner authorization to change frozen engine code. Either changes training features and possibly delayed labels; flush/recompute D35 cell cache, retrain from approved data, and invalidate model/replay/evaluation hashes. Do not casually edit the frozen six-file set.

### Acceptance and regression tests
Use same OHLCV/ATR/candle flags and clock in training and runtime; assert all 8 features, turbulence, tree input and label semantics match where contracts demand parity, including gap threshold just below/equal/above 2 ATR, no-gap, missing ATR and non-finite data. Verify new cache namespace and cold/warm parity.


## H-004

### Auditor claim (short quote)
The production producer supplies neither the E11 transition matrix T nor regime base rates.

### What I read (baseline line references, full functions, direct callers)
Read the full production assembly `apex/ops/engine_context.py:1557–1640`; it builds `regime_context` at `:1628–1630` without `T` or `base_rates`. Read `E11RegimeEngine.compute` (`apex/engines/e11_regime/engine.py:1476–1511`) and its complete `run_engine` call mapping, the complete Hamilton/base-rate functions and gates (`:614–650`, `:749–770`, `:937–965`, `:988–1009`), state schema validation (`:1120–1190`), and calibration reporting (`:1282–1300`). `grep -Rn` consumers/callers for `transition_matrix`, `base_rates`, `base_rate_quality_cap`, and `hamilton_filter_step` across `apex scripts tests` is saved at `AUDIT/probes_V5/H004_consumers.out`; no production caller outside E11 passes or consumes these values. Read normative E11 §§1.2, 3.4–3.9, 5.1 and D21/D23/D49 entries; no later decision found that supplies a T/base-rate source to this PAPER assembly. No frozen source was changed.

### Reproduction (command, probe, actual result)
Ran `PYTHONPATH=. /tmp/upstage-audit-venv/bin/python AUDIT/probes_V5/H004_e11_inputs.py`; raw output is `H004_e11_inputs.out`. Real `run_engine` on synthetic GF_09 input with omitted args produced `transition_matrix=null`, `base_rates={}`, uniform untouched `xi_filtered`, Q4. Supplying a structurally valid zero-count EXPANSION row produced Q3 under the §8.5 cap. The test selection `python -m pytest ... tests/unit/test_e11_regime.py -k 'hamilton or base_rates'` passed 2 tests (output in `H004_pytest.out`); those tests exercise mathematical helper/report functions, not production wiring. No device or store data used.

### Verdict and reasoning
**PARTIAL, independent severity S2.** The factual omission in the producer is confirmed, and empty `base_rates` bypasses the low-sample Q3 cap. However, schema permits `transition_matrix: null`, §3.9 conditions BaseRate on a defined outcome Y, and the binding text does not clearly define which outcome or data source the PAPER producer must populate; the global Gaussian Hamilton emission is explicitly regime-independent. Thus I do not confirm a mandatory T/Hamilton runtime decision defect. The matrix/base-rate output and unavailable-vs-empty quality behavior remain a contract gap requiring owner clarification.

### Root cause
The store-backed composition builds classifier/normalization state only; it has no PIT transition-count stream or defined continuation-outcome reporter. `run_engine` defaults T/base rates to None/empty; Hamilton executes only with a T mapping, and base-rate cap only applies when a row exists.

### Direct impact
PAPER E11 state carries no transition matrix or base-rate rows from this producer. An empty row set does not trigger Q3 under the existing helper, whereas explicit n=0 does. The resulting Q4 on the synthetic fixture is proven; downstream trade acceptance is not.

### Secondary effects and interactions (upstream/downstream)
E11 state/evidence is passed into the native bridge/forecast/risk chain, but `grep -Rn` found no explicit downstream T/base_rates consumer outside E11. Do not infer an order bypass. D23 already limits Q5 when OI is unavailable; this row is a separate BaseRate/T omission. No effect on ledger/order proven.

### Contract and decisions
APEX_GEN5 E11 §1.2 names T and BaseRate among outputs; §§3.4–3.5 require delayed transition statistics/Hamilton, §3.9 defines BaseRate for a specified Y with 48-bar PIT, and §8.5 says n_r<30 caps Q3. The RegimeState schema allows a null T; no owner decision inspected defines the event Y or a PAPER source. D21 is training labels only; D23 is OI only; D49 governs entropy thresholds and does not resolve this. Therefore partial, not a blanket confirmation.

### Frozen status and non-frozen alternative
`engine_context.py` producer is non-frozen; `apex/engines/e11_regime/engine.py` is frozen. Any fix should be a governed, non-frozen PIT provider/context binding unless owner explicitly authorizes frozen changes. Do not fabricate a transition matrix or outcome counts.

### Fix options (side effects)
A: owner specifies T estimation window, label source, Y event, maturity/availability rule, and required behavior when unavailable; pass those versioned inputs and mark unavailable distinctly. B: owner confirms null/empty is an allowed PAPER diagnostic-only state and removes the expectation of cap absent counts. Either changes quality/evidence and needs replay/quality validation; only option A alters feature cache/model if label/features change, which is not assumed here.

### My recommendation
Keep PAPER fail-closed/unavailable for any future decision explicitly requiring T or BaseRate until owner defines their source; avoid treating absent rows as evidence of n≥30. Do not change the frozen engine in this audit.

### Acceptance and regression tests
Add producer-level tests for T absent/valid and base rates absent, n=0, n=29, n=30 with PIT timestamps, and assert availability/Q behavior through `complete_engine_bundle` and `PaperPlanBridge`. Preserve existing formula tests; if owner rules out runtime use, assert schema null/empty is visibly diagnostic-only. Confirm no unrelated cache/hash defaults change.


## H-005

### What I read (baseline line references; complete functions and callers)
`engine_context.py:3010–3033` fully defines `training_protocol_hash` and `cell_input_hash`; `read_cell_cache`/`write_cell_cache` are `:3036–3100`; training caller and hit path are `:3160–3248`. The fixed `TRAINING_QUERY` declaration is at `:1716–1725`. `grep -rn` for protocol/cell hashes and cache readers/writers/callers was performed in `apex/`, `scripts/`, tests. Relevant tests `test_d36_cache_hashes_equal_main_constants_reuse_phone_namespaces` (`tests/unit/test_engine_context.py:2500–2539`) and `test_cp144_cache_compatibility_byte_identical` (`:3184–3215`) were read; D35 cache-resume tests are referenced in the report. No SQL row query was part of this identity probe.

### Reproduction
Probe `training_e11_claims.py` changes the in-memory E11 trend threshold while holding synthetic market/dependency rows constant, calls the real hash functions, writes/reads a disposable cache, and returns identical protocol/input hashes and a cache hit. Raw hashes and outcome are in `.out`. This is controlled monkeypatching only; no governed YAML/product file or repository cache was modified.

### Verdict and independently assigned severity
**CONFIRMED, S1.** Code identity and effective E11 feature/label policy do not enter either hash. `training_protocol_hash` hashes fixed query text, selected scope and cap; `cell_input_hash` hashes market/dependency observations and cap. The probe demonstrates a changed in-memory E11 policy does not invalidate an otherwise matching cell cache. It does not claim that a production policy was changed or that existing on-disk cache is corrupted.

### Root cause, direct impact, upstream/downstream
Cache namespace lacks source/engine/policy version; cell identity is market-only. A future non-market feature/label change can therefore reuse old samples, then feed `train_classifier` and produce an artifact/replay whose sample generation policy differs from current runtime. D35 intentionally preserves byte-identical cache compatibility, so this requires owner-aware versioning, not silently changing frozen cache semantics.

### Contract/decisions and frozen status
D35 (APEX_GEN5.md:11896) governs cache reuse/input invalidation; D47 governs `artifact_sha256`, not a code identity for each cache cell. D30 default remains 20 E11 base cells and is not 140 data cells. No frozen engine/data-catalog change proposed; `engine_context.py` is non-frozen. CP-15/CP-16/C-008 overlap is not claimed: this is specifically training cache identity.

### Fix options and side effects
A: approved policy-manifest digest in protocol/cache identity; old cache misses and affected cells recompute. B: explicitly accept a pinned training implementation version and reject cache on version mismatch. Preserve data/scope defaults and D35 resume; do not redefine D47 model checksum. Side effects: cache invalidation, longer training and newly fitted artifacts requiring downstream validation.

### Acceptance
With raw inputs fixed, mutate each governed feature/label implementation version and require cache miss; unchanged version/input must hit and reproduce samples bitwise. Verify dependency rows, correction/availability, cap and train CLI paths. No live-cache or device conclusion.


## H-006

### What I read (baseline line references; complete functions and callers)
`engine_context.py:515–518` defines D47 `classifier_hash`; `validate_classifier` is fully at `:527–591`; loader at `:594–601`; artifact construction at `:3250–3272`. The producer consumes the artifact in `:1628–1632`, and `prepare`/fingerprinting load it at `:1775–1796`. `grep -rn` across `apex/`, `scripts/`, tests for validator/hash/loader callers was performed. Binding contract APEX_GEN5.md:11852–11894 and D47 owner clause in PHASE2_DECISION_LOG.md:1155–1159 were read; D30 scope is unchanged.

### Reproduction
`training_e11_claims.py` builds a disposable schema-valid artifact; changes its query hash and training window while leaving W/b/seed/fit_protocol and `artifact_sha256` unchanged; calls real `validate_classifier`. Baseline and tampered artifact both validate. The validator verifies query is lowercase 64-hex and checks window scope/order, not correspondence to digest or training evidence. Raw result in `.out`; no real artifact used.

### Verdict and independently assigned severity
**CONFIRMED, S2.** D47 explicitly defines the artifact hash over `{W,b,seed,fit_protocol}`. Thus omitting provenance is not a violation of that hash's specified formula; independently, provenance fields remain schema-valid and unbound. The claim is confirmed as an assurance gap, not as a broken checksum implementation or proof of falsified provenance.

### Root cause, impact and interactions
`training_window`, `sample_count`, and `training_query_sha256` are outside the D47 checksum. A consumer that trusts these metadata fields can misstate what data/scope trained W/b. It affects provenance, audit and walk-forward validation; it does not itself change logits or prove a forged production model. H-007 covers temporal availability; H-010 covers cell participation and is not inferred here.

### Contract, decisions, frozen status
D47 hash formula and classifier schema (APEX_GEN5.md:11852–11894; PHASE2_DECISION_LOG.md:1155–1159); D30 limits default runtime fit to 20 cells. Keep the D47 formula unchanged unless owner revises it. Validator is non-frozen. No secret/device/model files read.

### Fix and side effects
Add a separately versioned/authenticated provenance manifest binding exact query, effective scope, time range, counts and per-cell/input identities; validate it before research/promotion. This requires approved schema/lineage, and invalidates prior provenance claims/downstream fit evaluations; weights need not change solely to add metadata. Do not claim manifest authenticity until a trusted producer/signature exists.

### Acceptance
Change each provenance field independently and require manifest validation failure; regenerated manifest over identical evidence must be deterministic. Confirm D47 model digest stays defined exactly as owner specified and model loading remains fail-closed.


## H-007

### What I read (baseline line references; complete functions and callers)
`validate_classifier` at `engine_context.py:527–591` validates only schema, 48-candle constant, ordering/scope and a 64-hex query hash; `load_classifier` is `:594–601`. `_input_fingerprint` loads the current artifact at `:1775–1796`; prepare/composition eventually consumes it at `:2283–2335`, with `complete_engine_bundle` loading once for the requested `as_of`. Artifact metadata is formed from sample stamps at `:3250–3272`. `grep -rn` over `apex/`, `scripts/`, tests for loader and prepare callers was performed. D21 and D47 contract/decisions read.

### Reproduction
The combined real-validator probe changes `training_window.end` to 2020 while retaining `label_delay_candles=48` and other valid fields; `validate_classifier` accepts it. Source trace confirms the producer loads a current classifier without selecting by query time. The probe shows acceptance of inconsistent historical metadata, not that a real historical replay was executed.

### Verdict and independently assigned severity
**CONFIRMED, S1 (conditional on historical use).** D21 requires each label's t+48 confirmation to be CLOSED and training PIT through window-end minus 48. Current loader/producer has no fit/deploy or last-label-available timestamp and no model version selection by requested `as_of`. Thus a historical request can consume a current model with future labels. No claim that current-time PAPER has this leakage or that historical API use has occurred.

### Root cause and impact trace
Artifact carries a training window of sample timestamps and a 48-bar delay but no publication/maturity timestamp. `prepare_engine_bundle(as_of)` loads the current path. Historical replay/backtest can therefore backcast knowledge unavailable at that time, biasing forecast/decision evidence and replay metrics. This is distinct from H-001 CLI absence and H-006 metadata integrity. Runtime order impact not established.

### Contract/decisions and frozen status
D21 (APEX_GEN5.md:11889–11894) owns delayed labels/PIT; D47 owns artifact shape/hash; neither authorizes latest model for historical time. `engine_context.py` is non-frozen; no frozen code change necessary, but model schema/provenance changes need owner decision. Preserve D30 default 20 cells.

### Fix and side effects
Add fit completion, latest label-maturity and publish times to approved provenance; select only artifacts available by query `as_of`, fail closed when absent. Historical replay becomes walk-forward and old replay results/hashes need recomputation; live newest-artifact behavior may remain unchanged. Do not rewrite D47 hash.

### Acceptance
Build synthetic models with different publish/maturity times; query before fit/maturity must refuse or select earlier eligible artifact, after publish selects expected digest. Test boundary t+47/t+48 and timestamp timezone, restart/cache, and prove no future model in historical replay. Device evidence not needed to establish API behavior.


## H-008

### Auditor claim (short quote)
Kline-only PAPER source leaves OI lag unavailable for the risk decision despite E11 partial-quality training.

### What I read (baseline line references; complete functions and callers)
Against baseline `85b2c155d7b054a468379ddfd802eb239d0801f9`: `bootstrap_service.py:620–644` Kline page result/oi_available contract and its caller at `:1043–1069`; `engine_context.py:1230–1241` `participation_input`, `:1829–2010` `get_bridge_context` (including latest-OI validation and risk assembly), and `:2337–2510` decision-input quality hydration and `feature_timeline`; `plan_bridge.py:155–165` required risk inputs; `risk/kernel.py:247–260` OI-lag veto; `paper_loop.py:518–525,545–670` engine skip, plan resolution and named-refusal propagation; `scripts/run_apex.py:748–765` production producer/bridge/runtime composition. `grep -Rn` for `oi_state`, `oi_lag_seconds`, and `contributing_features` across `apex/ops`, `apex/decision`, `apex/risk`, `apex/forecast`, and `scripts` is saved in `H008_consumers.out`. Referenced D23 and the E11 missing-OI contract were read. No SQL row-scan/index claim is made, so no query-plan experiment applies.

### Reproduction (command, probe file, actual result)
Ran `PYTHONPATH=. /tmp/upstage-audit-venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_engine_context.py::test_d23_formula_marker_and_only_q5_cap tests/unit/test_engine_context_store_sources.py::test_native_bundle_without_injected_quality_or_mtf`; six parametrized/test cases passed in 35.64s (`H008_pytest.out`). The D23 cases assert missing OI uses VolumeZ only, records `oi_state`/PARTIAL, and cannot reach Q5. The real store-backed producer test seeds OI-missing observations and executes `prepare_engine_bundle` through all native engines, but does not assert what `get_bridge_context` or `PaperPlanBridge` does with missing OI; therefore those tests alone do not prove the risk/order claim. Source trace supplies that missing composition evidence: `get_bridge_context` raises `OI_LAG_UNAVAILABLE` if the latest bar has no OI timestamp or value, before constructing its `risk` mapping. No exchange, device, or `data/` access.

### Verdict and independently assigned severity
**PARTIAL, independent severity S2.** D23's training/runtime E11 partial participation behavior is present. The Kline-only stream does not provide an OI series, but in the production PAPER composition this does not reach risk with an implicit zero lag: the producer refuses context with `OI_LAG_UNAVAILABLE` before the required risk field is formed. The narrow availability/producer test is missing, so the end-to-end fail-closed behavior is code-traced, not test-proven. A blocked cell is established; no order bypass is established.

### Root cause
Kline ingestion deliberately labels OI `MISSING` and carries no OI values/timestamps. D23 makes that acceptable for E11 participation by removing the OI term and limiting quality, while the PAPER decision context has the stricter requirement of an actual latest OI timestamp/value to calculate seconds of lag. Those are distinct consumers/contracts, not a train/serve formula mismatch.

### Direct impact
For Kline-only latest observations, `get_bridge_context` raises before producing the risk input (`oi_lag_seconds` and its threshold), so `PaperPlanBridge` cannot return a trade plan through this path. The production PAPER loop receives that named refusal and halts that cell; it does not proceed to execution. An alternate or standalone caller that fabricates the required risk field is outside this composition and is not proven safe by these tests.

### Secondary effects and interactions (upstream/downstream)
Upstream: Kline bootstrap/catch-up marks OI missing; E03/E11 still compute PARTIAL participation as D23 requires, with no sample exclusion. Downstream: `plan_bridge.REQUIRED_RISK_KEYS` includes `oi_lag_seconds`; the risk kernel vetoes when the supplied lag exceeds its governed threshold; the producer currently refuses earlier when the value cannot be derived. `PaperRuntime._resolve_plan` forwards the PAPER bridge refusal into its cell-stage halt, and execution is therefore not reached for that cell. No ledger/order is emitted by the refusal path. No training artifact, replay, cache, or hash impact is established; changing D23 would require retraining/replay validation and is not proposed.

### Contract and decisions
APEX_GEN5 E11 §2 and binding D23 (`PHASE2_DECISION_LOG.md:343`; summarized in `APEX_GEN5.md:11765`) require non-AVAILABLE OI to have zero weight, renormalize to `VolumeZ`, retain `oi_state` and `participation=PARTIAL`, prohibit Q5, and make no other quality change. This is not a promise that OI lag is optional for risk. In the producer, latest missing OI explicitly raises `OI_LAG_UNAVAILABLE`; the required risk schema requires the lag, and `risk/kernel.py` compares it with the required threshold. D23 does not override that risk contract. Owner items D58/D57 do not resolve or supersede this OI-context behavior; no overlap beyond preserving D23's existing policy is claimed.

### Frozen status and non-frozen alternative
The implicated composition is non-frozen (`bootstrap_service.py`, `engine_context.py`, `plan_bridge.py`, `paper_loop.py`, `scripts/run_apex.py`); no file in the frozen list needs modification. Do not fabricate OI=0, a timestamp, or zero lag. A producer-level regression can be added in non-frozen tests and, if owner-approved, a clearer named refusal/diagnostic can be added in the non-frozen bridge. No E03/E11 engine change is needed.

### Fix options and side effects
A: preserve the current fail-closed behavior and add an integration assertion that missing latest OI produces `OI_LAG_UNAVAILABLE`, no risk mapping/plan, and a PaperRuntime cell halt without execution. B: if PAPER is intended to trade with Kline-only data, obtain an owner-approved alternative OI source and PIT/availability contract; then calculate and bind its lag through the existing required risk field. Do not default missing lag to zero. Option A is test-only; option B changes context provenance, risk veto outcomes, and requires replay/decision validation and possibly schema/provenance work.

### My recommendation
Keep the named fail-closed refusal, preserve D23's E11 PARTIAL behavior, and add a producer→bridge→PaperRuntime regression before representing this as proven by tests. Do not treat a D23 Q4 cap as a substitute for risk freshness and do not infer an order bypass from the audit claim.

### Acceptance and regression tests
With isolated SQLite/test fixtures only, ingest a Kline-only closed bar with `oi_state=MISSING`, `oi=None`, and `oi_timestamp=None`; assert `prepare_engine_bundle` still follows D23 and cannot report Q5, then assert `get_bridge_context` raises `OI_LAG_UNAVAILABLE` before risk construction. Drive the production `PaperPlanBridge` and `PaperRuntime` with that producer; assert named cell halt and no setup, plan materialization, ledger intent, adapter submission, or order. Add the positive control with a real PIT OI timestamp/value and verify derived lag reaches the risk kernel and its threshold veto. Keep all D23 formula tests and confirm no fabricated OI or change to training sample inclusion.

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

### What I read (baseline line references; complete functions and callers)
Against baseline `85b2c155d7b054a468379ddfd802eb239d0801f9`: `engine_context.py:2984–3026` scope/hash functions and `:3111–3280` complete `train_classifier` (cell discovery, per-cell window/cache/sample aggregation, class refusal and report/artifact construction); `:3281–3410` bounded worker/supervisor caller; `scripts/run_apex.py:944–1037` `_train_e11` CLI and output/persistence; tests `test_d30_default_scope_and_progress_are_exactly_twenty_base_cells`, `test_d30_subset_is_canonical_and_excludes_other_training_cells`, and parametrized `test_d30_scope_rejects_nonbase_or_ambiguous_selection`. `grep -Rn` for trainer, CLI and scope consumers across `scripts`, `apex`, and `tests` is saved in `H010_consumers.out`. D30 and its later D35 cache refinement were checked. Source line refs are against the requested baseline, not current branch HEAD.

### Reproduction (command, probe file, actual result)
Real-code controlled probe `H010_one_cell_scope.py` (raw JSON in `.out`) ran `train_classifier` with an isolated temporary cache and stubbed only the optimizer to avoid creating a classifier. Exactly 1 of 20 selected cells had nonempty market data and a contributing cached sample (`BTCUSDT:1h`); output reported all ten selected symbols and timeframes `1h`,`4h`. Eight of nine labels had one sample and derived `TRANSITION` had zero; no optimizer fit or artifact persistence occurred. The cache key included empty dependency entries after the initial cache-miss correction. Then ran the three D30 tests above: 6 passed in 0.72s (`H010_pytest.out`). The tests prove exact default 20-cell enumeration, requested scope reporting, subset canonicalization, and invalid-scope rejection; they do not require a minimum number of contributing cells. No repository cache, `data/`, device, or live store was used.

### Verdict and independently assigned severity
**PARTIAL, independent severity S2.** The premise is reproduced: the effective/requested scope in `training_window` lists all ten symbols and both timeframes when only one cell contributes any cached training samples. However, D30 governs which cells are selected, records effective/default scope, and requires per-cell progress; it does not require every selected cell to contain bars or samples. Thus no training-scope or model defect is confirmed. The final artifact/JSON's scope list is not itself a realized-contribution manifest, which is a bounded provenance/interpretation ambiguity.

### Root cause
`train_classifier` loops the Cartesian product of selected symbols and timeframes, and empty cells are reported/excluded then skipped. `training_window` intentionally stores the configured/effective symbol and timeframe lists, while sample arrays aggregate across contributing cells; the final artifact and CLI result do not carry per-cell contributing sample counts. Per-cell eligible counts exist only in progress messages. The probe's optimizer stub and absent artifact mean this finding does not claim a production model was fitted from this distribution.

### Direct impact
Consumers of `training_window.symbols/timeframes` can read them as requested training scope, but cannot infer realized cell-level coverage from those fields. The H010 probe proves one contributing cell, not a broken default scope. This does not prove underfit, invalid classifier, wrong artifact identity, or trade/order impact. All eight required rule-tree classes still gate fit; `TRANSITION` may be empty under D36.

### Secondary effects and interactions (upstream/downstream)
Upstream: D30 limits training cells to the 1h/4h base timeframes × Core-10 (20 by default); permitted dependency reads do not add training cells. D35 may resume a cell's finalized samples from cache but hashes current inputs. Downstream: successful samples feed the shared E11 fit; classifier/artifact hash, runtime E11 state and later decisions could reflect uneven realized coverage, but this controlled probe did not fit or persist an artifact, so no such downstream effect is measured. Existing per-cell stderr progress displays eligible counts during CLI runs; no risk/order/ledger bypass is shown. Keep distinct from D30's 140-cell data scope or higher-timeframe dependency reads.

### Contract and decisions
Binding D30 is transcribed in `PHASE2_DECISION_LOG.md:523–533` and `APEX_GEN5.md:11894`: 1h/4h only, Core-10, 20 default cells, flags/defaults, effective/default scope in `training_window`, one progress line per cell, hard deadline, unchanged nine-class refusal, one shared classifier. D35 (`APEX_GEN5.md:11896`) governs resume cache and bar cap. These clauses specify selected scope and observability but no per-cell contribution minimum or requirement that all ten symbols yield labels. Therefore the claim is only partial; do not reinterpret D30 as a 140-cell scope or as a promise of 20 populated cells.

### Frozen status and non-frozen alternative
`engine_context.py` trainer, `scripts/run_apex.py`, and tests are non-frozen; no frozen engine, data-catalog, bootstrap, backtest, original six YAML, or lockfile change is implicated. Preserve D30's exact defaults and D36's class refusal. If desired by owners, add per-cell counts to a non-frozen report/provenance layer; avoid changing the meaning of the existing `training_window` fields without a decision.

### Fix options and side effects
A: no behavior change; document that `training_window` is selected scope and retain existing per-cell `TRAIN_CELL` progress. B: add a per-cell manifest containing closed-bar count, eligible-sample count, cache hit/miss, and exclusion counts to the final report/artifact provenance, with owner approval if artifact schema changes. Option B improves reproducibility and makes sparse cells explicit but changes report/artifact shape and may require schema/hash and downstream consumer compatibility tests; it must not alter training scope, cache identity, optimizer inputs, or class thresholds. Do not impose a contribution minimum without an owner decision; that could turn currently valid sparse-store runs into refusals.

### My recommendation
Treat the reproduced fact as a report-scope clarity gap, not a D30 violation. Keep the default at 20 selected base cells and preserve existing fit/refusal behavior. If the report is used to claim sample coverage, append actual per-cell contribution counts to the report; never infer realized coverage from the selected scope alone.

### Acceptance and regression tests
Retain the exact-20/default, subset, invalid-scope, cache and class-refusal tests. Add a sparse isolated store with one nonempty cell and assert both configured scope and realized per-cell counts are separately named in the final report (if the optional manifest is approved), with empty cells explicitly zero. Assert no implicit minimum/expansion to 140 cells, no change to D30 default scope or D36 refusal, and no artifact written on degenerate required classes. Re-run D35 cache-hit parity and verify the report preserves requested scope plus actual contribution totals.

## H-011

### What I read (baseline line references; complete functions and callers)
`engine_context.py:3036–3084` is complete `read_cell_cache`; atomic `write_cell_cache` follows at `:3087–3100`; caller and training cache-hit path are `:3196–3209`, cache construction at `:3238–3248`. `grep -rn` for cache consumers and writers was performed in `apex/`, `scripts/`, tests. Read relevant cache tests: `test_cp144_cache_compatibility_byte_identical` (`tests/unit/test_engine_context.py:3184–3215`) and D36 cache hash test (`:2500–2539`); test file is large and this is not a claim of a full independent suite rerun.

### Reproduction
Real `write_cell_cache`/`read_cell_cache` with a disposable temp file and correct unchanged input/protocol hashes; well-shaped sample label altered to `CRISIS` is returned as a hit. `training_e11_claims.py` / `.out`. Reader verifies format, cell, hashes, vector-key order, label membership, as_of string, finite 8-vector and excluded counts; it has no digest or rederivation check over `samples`.

### Verdict and independently assigned severity
**CONFIRMED, S1.** A schema-valid changed sample can be accepted under the same raw-input digest. The result is a demonstrated trust-boundary weakness/cache tamper acceptance, not evidence that the repository's gitignored production cache was manipulated or that model weights were trained from a tampered file. D35 byte-compatible reuse explains why simple schema changes have side effects; H-005 separately addresses missing code/policy version identity.

### Root cause and upstream/downstream
`input_hash` attests consumed source observations, not the derived label/vector payload. The training caller trusts cache samples on a matching input hash, then aggregates them into X/labels and trains W/b. A changed but valid label/vector can therefore affect class counts and artifact. No raw data, `data/`, or actual cache was accessed.

### Contract, decisions, frozen status
D35 (APEX_GEN5.md:11896) requires resume and changed-input recomputation; D47 governs resulting artifact hash, not cache sample payload digest. `engine_context.py` is non-frozen; no product edit made. Maintain cache compatibility only under an owner-approved trust design.

### Fix and side effects
Verify payload by canonical digest plus trusted per-cell producer/manifest, or recompute feature/label derivations from raw/dependency evidence before training; reject mismatches. A bare adjacent checksum is not authenticity if it can be edited with the payload. Side effects: schema/version and invalidation of existing cache; warm/cold parity and resume performance must be retested; affected fit evidence must be rebuilt.

### Acceptance
Change a valid label, timestamp or finite vector while preserving input hash and require refusal/recompute. Correct cache remains byte-identical on warm resume and equals cold derived samples. Verify all eight required classes and D36 TRANSITION semantics without claiming real-model acceptance.


## H-012

### Auditor claim (short quote)
The training bar cap is applied after full-window reads and lineage preparation.

### What I read (baseline line references; complete functions and callers)
Against baseline `85b2c155d7b054a468379ddfd802eb239d0801f9`: `engine_context.py:3001–3007` cap validation; `:3111–3280` full `train_classifier`, especially row counts/window call, cap slice, dependency reads, label timeline/cache and report construction; `:2367–2420` complete `EngineContextProducer.window` and `training_dep_window`; `sqlite_store.py:497–521` frozen `SQLiteStore.get_window`; `scripts/run_apex.py:944–1037` trainer CLI/artifact caller. `grep -Rn` for cap, window and dependency consumers across `apex`, `scripts`, and tests is saved in `H012_consumers.out`. D35 and ISSUE-076 index ownership were checked. No repository/device DB was touched.

### Reproduction (command, probe file, actual result)
In-memory SQLite probe `H012_read_cap_explain.py` (raw output `.out`) used repository DDL and real producer/query text. With three closed bars and cap=1, `train_classifier`'s ordering is: cell count=3 → `producer.window(..., bars=3)` reads and lineage-hydrates 3 rows → Python `window[-1:]` retains 1 for feature/label processing. `get_window` uses SQL `LIMIT 3`, while the subsequent lineage metadata query spans the returned first/last timestamps. The baseline DDL has no market-observation device index: `EXPLAIN QUERY PLAN` reports scans for cell discovery and `get_window`, and a raw-observation scan for lineage. A candidate composite index was created only in the same in-memory DB: discovery becomes a covering-index scan and `get_window` a bounded index search; lineage still scans `raw_observation`. Full before/after plans are saved in the probe output. Then ran `test_d35_bar_cap_validation`, `test_d35_bar_cap_caps_window_and_namespace`, and `test_d35_cli_bar_cap_records_window_and_rejects_invalid`: 3 passed in 12.01s (`H012_pytest.out`). These assert positive-int validation, latest 100 of 120 bars and namespace separation, and report/invalid-CLI behavior; they do not assert how many rows were read before slicing. No persistent index or `data/` access.

### Verdict and independently assigned severity
**PARTIAL, independent severity S2.** The literal ordering claim is confirmed for the base training cell: cap is applied only after all counted rows have been fetched and lineage-prepared. The cap still limits the rows passed into feature/label processing and changes the cache namespace, matching the D35 latest-N semantic. D35 does not explicitly promise bounded prefetch/I/O or lineage work, so this is a resource-efficiency gap, not a proven D35 semantic violation or sample correctness defect. Severity S2 reflects wasted I/O/memory/runtime under phone-scale stores; no real-device timing was obtained.

### Root cause
`train_classifier` asks `CELL_QUERY` for per-cell total counts, passes that full count to `EngineContextProducer.window`, which calls the frozen `SQLiteStore.get_window` and then reads raw lineage for the returned window, and only then applies `window[-max_bars:]`. HTF dependencies are also prefetched using their full stored counts. The cache/hash and label timeline operate on the capped base window, so sample computation is capped while source materialization is not.

### Direct impact
A capped run can still materialize all CLOSED/CORRECTED base-cell rows (and the corresponding lineage range) before discarding earlier rows in Python. The cap bounds later feature-timeline/label work and the cached finalized sample set, but does not bound this query's row return or lineage preparation. The query-plan probe confirms a full scan with repository DDL for the tested schema; it does not establish wall time, memory exhaustion, device failure, or a real store's index state.

### Secondary effects and interactions (upstream/downstream)
Upstream: `CELL_QUERY` counts stored cell rows; `get_window` selects those rows PIT/closed and `window` verifies immutable raw content/availability before the cap. Downstream: the capped suffix is used for D21 label generation and cached under the D35 protocol/input identity; changing fetch limits must preserve exact suffix, lineage and cache parity. HTF dependency prefetch remains a separate feature-history need and is not shown capped by the base cell's N. Index work overlaps CP-15 ISSUE-076; this probe adds only that caller-side cap pushdown can reduce rows reaching the lineage preparation. No decision/risk/order/ledger/hash/training-output correctness defect is proven.

### Contract and decisions
D35 in `APEX_GEN5.md:11896` says `--max-bars-per-cell N` caps each cell at its latest N CLOSED bars and records N in `training_window` and the protocol hash. D35 tests confirm the resulting 100-bar window from 120 and distinct capped/uncapped namespaces. It does not state that all reads, cell-count discovery, or HTF dependencies are themselves bounded to N. D30 defaults and scope remain unchanged. `SQLiteStore.get_window` is frozen and already parameterized by `bars`; the caller can potentially request the latest N without changing the store API. ISSUE-076 owns broader replay query/index work; no index installation or frozen DDL modification is proposed.

### Frozen status and non-frozen alternative
`apex/data_catalog/**` including `SQLiteStore.get_window` is frozen, as are the original data catalog contracts/engines and backtest; do not edit them. The non-frozen trainer can pass `min(count, max_bars)` to its base-cell window read before lineage hydration while preserving the same latest-N closed suffix. That would not by itself eliminate the full-table `CELL_QUERY` count scan or govern HTF dependency needs; index/DDL changes would require the existing owner path.

### Fix options and side effects
A: keep current behavior and describe `--max-bars-per-cell` as a downstream feature/label cap, not an I/O or memory ceiling. B: pass the base-cell cap into `producer.window` before materialization (and assess equivalent dependency policy separately), with an owner-approved resource contract. B reduces returned rows and lineage work, but may change PIT/correction/read behavior if count and suffix selection are not equivalent; re-run exact feature timeline, training/cache hit parity, query-plan and capped/uncapped tests. Do not change D35 cap hash semantics or freeze constraints. A schema/index alternative overlaps ISSUE-076 and is not proposed without ownership.

### My recommendation
Treat as a bounded resource optimization opportunity, not a model-data correctness failure. Keep frozen `SQLiteStore` untouched; if D35 is intended as a phone memory/I/O guard, push the base cap into the non-frozen query caller and separately measure `CELL_QUERY` and dependency costs. Do not claim it has been device-validated.

### Acceptance and regression tests
Instrument the real store/query boundary in an isolated SQLite fixture with >N closed bars. Assert the trainer requests/materializes at most N base bars when capped, gets exactly the same latest-N observations, raw-lineage identities and samples as current post-slice behavior, and uses a distinct cap cache namespace; uncapped behavior remains identical. Re-run D35 cap, cache, PIT/correction and training parity tests. Include EXPLAIN plans for discovery/window/lineage with repository DDL and temporary candidate indexes; verify any new optimization does not alter D30 scope, D21 labels or the frozen data-catalog tree. Real-device claims require separate device evidence.

## H-013

### What I read (baseline line references; complete functions and callers)
Complete `run_fit_study` is `engine_context.py:2909–2940`; `fit_multinomial_study` is `:2840–2906`; `training_validation` default governance path is `:2805–2818`. `grep -rn` over `run_fit_study` callers found research/report paths; it is separate from `train_classifier` runtime artifact write. Read D49 / governing theta declaration and cited test reference; source line `APEX_GEN5.md:20976` appears in auditor row, with later D49 decisions taking precedence.

### Reproduction
The actual `run_fit_study` is called on eight tiny synthetic rows with one explicitly bounded iteration and real `E11.get_params` monkeypatched to raise. Probe restores the original function in `finally`; no file/artifact is written. Output returns `theta_H=0.65`, one variant. This is a research-only synthetic fit, not a deployed or real model.

### Verdict and independently assigned severity
**CONFIRMED, S2.** Any exception loading governed entropy threshold silently selects legacy `E11.THETA_H`; `training_validation` then receives it explicitly. Governed D49 YAML value is `1.105878`, not `0.65`. Finding is confined to research fit-study diagnostics/report and is not a PAPER decision-path bypass.

### Root cause, impact and interactions
Broad exception fallback hides missing/invalid governed settings. Entropy shares/variant comparisons in report can be materially different and inform human policy/model choices; actual runtime classifier training path uses `load_e11_training_protocol` and `train_classifier`, not this fallback. No model artifact, production decision or order is implicated by this probe.

### Contract/decisions and frozen status
D49's governed threshold supersedes historical prose/default; `run_fit_study` is non-frozen. No E11 engine/YAML change. Research report identity should surface governed threshold/source and invalidity; not an authorization to change D49.

### Fix and side effects
Fail with named configuration error on missing/invalid threshold, or mark report INVALID and include explicit non-governed fallback source; never emit an ordinary fit-study result with silent 0.65. Existing research comparisons using fallback must be rerun and marked superseded; no runtime retraining automatically follows.

### Acceptance
Valid D49 config returns governed threshold/source; loader error or invalid value yields refusal/INVALID status and no ordinary study report. Run every research variant and tests under valid configuration; ensure no fallback leaks into runtime train-e11.


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

### What I read (baseline line references; complete functions and callers)
Against baseline `85b2c155d7b054a468379ddfd802eb239d0801f9`: complete `optimizer.py` including `ParameterGrid` `:94–165`, `DualOptimizer.run_run` `:347–421`, `write_suggestion` `:424–462`, and scope constants/disjoint check `:50–87`; `governance.py` `validate_package` `:494–532` and `assert_live_params_untouched` `:535–558`; `promotion.py` package-validation handoff; optimizer test classes `TestScopes`, `TestGrids`, `TestDualOptimizerRun`, and `TestSuggestionOutput`. `grep -Rn` for `ParameterGrid`, `run_run`, `DualOptimizer`, `write_suggestion`, and `validate_package` consumers is saved in `H024_consumers.out`: no production optimizer caller outside the optimizer API/promotion code was found; direct `run_run` call sites are tests. Read APEX_GEN5 W.1/W.5 (`:17208–17247`) and matrix row `R-CP8|8` (`PHASE2_TRACEABILITY_MATRIX.md:346`). No external/device optimizer run or package injection was attempted.

### Reproduction (command, probe file, actual result)
Ran `H024_scope_probe.py` against the real API with `optimizer="SIGNAL"` and a one-state `ParameterGrid` named `capital_hard_cap` (not in `SIGNAL_SCOPE`, and listed in governance `FORBIDDEN_FIELDS`). `run_run` returned `COMPLETE`, called the evaluator once with that key, and returned it as `best_params`; the probe also persisted only a temporary suggestion under `/tmp`, without a `ParameterPackage` or package validation. Raw output is `H024_scope_probe.out`. Then ran the complete referenced `tests/unit/test_research_optimizer.py`: 43 passed in 0.14s (`H024_pytest.out`). Those tests prove the scope constants are disjoint, grid enumeration and schedule/checkpoint/write-path behavior, but do not assert each supplied grid's names belong to its selected optimizer scope or are screened for RED LINE fields before evaluation. No repository suggestions, `params/`, checkpoint DB, or exchange endpoints were touched.

### Verdict and independently assigned severity
**PARTIAL, independent severity S2.** The scope-enforcement portion is confirmed at the standalone optimizer API: `ParameterGrid` validates only nonempty/unique names and range bounds; `run_run` validates the optimizer enum, schedule and checkpoints, then calls the evaluator without comparing `grid.names` to `SIGNAL_SCOPE`/`RISK_SCOPE`. The RED LINE wording is narrower than the auditor's timing: W.5 requires forbidden candidate packages to be rejected at validation before paper trial, not necessarily before research evaluation. However, this optimizer path does not itself enforce that boundary before evaluating or writing a suggestion. No production caller or paper-trial/injection path was found, so no current order/live-parameter effect is established. S2: governance/research integrity gap with a suggestion-only boundary, not a demonstrated live safety bypass.

### Root cause
Scope constants are used only by `assert_scopes_disjoint`, which checks overlap between the two declared sets, not membership of each grid. `ParameterGrid` accepts arbitrary string names; `run_run` sends every generated combination to the supplied evaluator. `validate_package` checks forbidden field names and governed bounds when it is called, but `run_run` does not call it. `write_suggestion` protects the target path, and calls `validate_package` only when an optional package is supplied; it records that result but still writes the suggestion. A bare `params` mapping is not independently checked. Promotion has a later package-validation handoff, but `grep` found no wired optimizer→paper-trial production caller in this checkout.

### Direct impact
A caller can ask the SIGNAL optimizer to evaluate a grid for a risk-only or RED LINE parameter and receive a completed result and `best_params` for it. This violates the declared W.1 separation at the API boundary and can contaminate research evaluation/suggestion metadata. The demonstrated file is only a temporary suggestion; `assert_live_params_untouched` prevents writing live `params/*.yaml`. No live package injection, paper trial, runtime config change, or order is demonstrated.

### Secondary effects and interactions (upstream/downstream)
Upstream range construction is caller-supplied; there is no registry or configuration source binding each range to optimizer type. Downstream, the evaluator/backtest receives the unchecked key; results/checkpoints record optimizer and best params, and suggestion serialization may carry it forward. `validate_package` provides a later forbidden-field check if explicitly invoked with a package, while W.5/promotion are intended to gate candidate trial. The standalone `run_run` caller may use custom evaluation logic; no connection to frozen `backtest.py`, PAPER runtime `scripts/run_apex.py`, ledger, or orders is present in production consumer search. Any fix should reject before invoking caller code and avoid changing objective/replay arithmetic, checkpoint identity or suggestion-path guarantees.

### Contract and decisions
APEX_GEN5 W.1 (`:17208–17216`) assigns disjoint Signal and Risk scopes and says no parameter belongs to both. W.3 (`:17223–17230`) governs exhaustive grid generation; D3 only authorizes random-search exceptions and does not relax scope. W.5 (`:17237–17247`) says forbidden fields are rejected at package validation before paper trial. The matrix row `R-CP8|8` reports tests for scope disjointness, grid size, owner-only random search, schedule and checkpointing; current tests' assertions match that limited coverage, not per-grid key admission. No later owner decision was found that authorizes cross-scope names. Accordingly, the scope claim is confirmed; the stronger “RED LINE must be checked before evaluation” timing is not the W.5 contract as written, though validation must precede paper trial.

### Frozen status and non-frozen alternative
`apex/research/optimizer.py`, `governance.py`, `promotion.py` and associated tests are non-frozen; `apex/research/backtest.py` and `bootstrap.py` are frozen, as are original parameter YAMLs and `requirements.lock`. A validator in the non-frozen optimizer can enforce `grid.names ⊆ SIGNAL_SCOPE` or `RISK_SCOPE` before any evaluate callback and reject forbidden names before producing candidates. Retain independent governance/package validation before paper trial. No frozen file, live YAML, config value, research output, or runtime artifact needs alteration.

### Fix options and side effects
A: add fail-closed `validate_grid_scope(optimizer, grid)` at `run_run` entry (before evaluation/checkpoint completion); reject any unknown/out-of-scope or RED LINE key with a named error. Update tests to cover both optimizer directions, unknown names, every `FORBIDDEN_FIELDS` family, and prove evaluator call count stays zero. Side effect: previously accepted custom/private optimizer grids will refuse and require explicit classification/owner approval. B: keep a generic research grid API but require typed scope metadata and enforce W.1 at a separate authorized runner; this is more flexible but leaves direct `run_run` callers vulnerable unless the raw method is explicitly marked low-level and gated. In either option, leave exhaustive enumeration, objective formulas, frozen replay code, suggestion directory and W.5 paper-trial authority unchanged; rerun optimizer/promotion/checkpoint tests.

### My recommendation
Implement option A in the non-frozen optimizer: validate every parameter name against the selected optimizer's declared scope, and reject any RED LINE field before the evaluator is called. Keep W.5 package validation at the later paper-trial boundary as a separate defense. Until then, treat the standalone API as research-only and do not infer an operational order bypass.

### Acceptance and regression tests
Use real `ParameterGrid`/`DualOptimizer.run_run` with one in-scope Signal key and one in-scope Risk key as positives. For each cross-scope, unknown, and RED LINE key, assert a named refusal before the evaluator is called, before a COMPLETE checkpoint is stored, and before a suggestion is emitted. Assert package validation still rejects forbidden values before paper trial; preserve suggestion-path refusal, full-grid defaults, schedule, W.8 resume and deterministic identities. Run `tests/unit/test_research_optimizer.py`, governance and promotion suites; no frozen files or live `params/` may change.

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

### What I read (baseline line references; complete functions and callers)
Against baseline `85b2c155d7b054a468379ddfd802eb239d0801f9`: complete `PromotionCandidate.gates`, `evaluate_promotion`, and `draft_package` in `promotion.py:497–563`; `probability_of_backtest_overfitting` and `deflated_sharpe_gate` in `promotion.py:360–437`; frozen `evaluate_wfo` in `backtest.py:280–304`; `validate_package` in `governance.py:494–532`; and tests `TestPromotionDecision` / `TestDraftPackage` in `tests/unit/test_research_promotion.py:306–389`. `grep -Rn` for `PromotionCandidate`, `evaluate_promotion`, and `draft_package` across `apex`/`scripts` is saved in `H026_consumers.out`; no production caller was found. W.5/Z.9 validation language and matrix promotion rows were reviewed. No backtest dataset, device, or persisted package was used.

### Reproduction (command, probe file, actual result)
`H026_promotion_flags.py` constructs a real `PromotionCandidate` with contradictory summaries: WFO says `PROMOTED` while its reported Sharpe/PF/drawdown fail the stated criteria; PBO says `flagged_high=False` with `pbo=0.99`; DSR says `passes=True` with `deflated_sharpe=-100`; benchmark says `outperforms=True` while reported strategy/benchmark returns contradict it. Real `evaluate_promotion` returns `PROMOTE` with all five checks true and `paper_trial_required=true`; `draft_package` then returns `DRAFTED` after package-value/proposal validation. Raw output is `H026_promotion_flags.out`. Ran full `tests/unit/test_research_promotion.py`: 46 passed in 0.08s (`H026_pytest.out`). Tests exercise boolean gating and package RED LINE, but their candidate fixture contains sparse summary mappings and no contradiction/recomputation assertion. The probe creates only in-memory objects; no package file is written.

### Verdict and independently assigned severity
**CONFIRMED, independent severity S1.** The public promotion gate bases WFO/PBO/DSR/benchmark decisions on caller-supplied boolean/label fields and does not recompute or bind them to the accompanying metrics. The controlled contradiction returns `PROMOTE`, and the package draft proceeds to the declared paper-trial/owner-approval next step. This is a promotion-evidence integrity defect; it does not prove that any actual candidate, paper trial, owner approval, injection, or trade was affected. I assign S1 because the gate can accept internally contradictory mandatory promotion evidence, while explicitly bounding the finding to the exposed API and research path.

### Root cause
`PromotionCandidate` stores arbitrary mappings. `gates()` checks only `wfo["decision"] == "PROMOTED"`, `not pbo["flagged_high"]`, `bool(deflated_sharpe["passes"])`, and `bool(benchmark["outperforms"])`; reported numerical metrics and any `checks` fields are ignored. `draft_package` consumes that verdict and only then validates candidate parameter values/proposals, not the provenance or arithmetic of performance evidence.

### Direct impact
A caller can pass contradictory WFO, PBO, DSR and benchmark metrics with favorable flags; the gate can report PROMOTE and `draft_package` can return DRAFTED. This is not live injection: `draft_package` returns an object, its declared next step remains paper trial → owner approval → versioned injection, and the existing package path is suggestion-only. No value in `params/` was modified.

### Secondary effects and interactions (upstream/downstream)
Upstream, frozen `backtest.evaluate_wfo`, `promotion.probability_of_backtest_overfitting`, and `deflated_sharpe_gate` can compute legitimate outputs, but there is no consumer-side identity binding to prove the mappings came from those functions or that flags match metrics. Downstream, W.5 promotion/drafting can accept an invalid evidence summary; any later human paper trial or package decision might rely on it. The repository consumer search found tests and the separate package-validation path, not an optimizer→promotion runtime composition. No risk/order/ledger, training/cache/hash, or model-runtime effect is established. Existing W.5 RED LINE package-value validation remains distinct and cannot repair performance-evidence mismatch.

### Contract and decisions
APEX_GEN5 §18.1/W.5 requires WFO, stress, and promotion-protocol validation before paper trial; Z.9 defines PBO/DSR gates, and WFO criteria in §18.4 require OOS Sharpe >1.0, profit factor >1.2 and max drawdown <15%. `evaluate_wfo` computes those thresholds from the supplied OOS metrics; PBO/DSR helpers likewise compute fields. But `PromotionCandidate.gates` does not call or bind to those producers. Existing matrix row `R-CP8|6` claims Z.1–Z.9 promotion gate and related tests, whose current bodies prove flag pass/block and package validation, not internal metric consistency. No later owner decision authorizes treating contradictory evidence as valid; this is not the separate frozen backtest calculation defect and must not be fixed inside `backtest.py` without ownership.

### Frozen status and non-frozen alternative
`promotion.py` and its tests are non-frozen. `apex/research/backtest.py` is frozen and directly supplies `evaluate_wfo`; no edit to it is needed. Add a non-frozen immutable evidence envelope/digest or a promotion adapter that recomputes WFO/PBO/DSR/benchmark checks from the metric inputs before evaluating flags. Keep `draft_package` and owner approval gates. No YAML, DB schema, engine, or runtime order path change is necessary.

### Fix options and side effects
A: in the non-frozen promotion layer, require canonical metric-bearing structures and recompute/compare each decision, returning named `EVIDENCE_MISMATCH` on any conflict; bind to the actual OOS block, PBO matrix, DSR inputs and benchmark return pair. B: require independently signed/content-hashed receipts from the metric producers and validate all flags against receipt fields before promotion; this requires a new evidence schema and provenance generation across callers. Both options invalidate previously emitted promotion verdicts/drafts whose metrics are unbound and require regression of WFO/PBO/DSR/Z.9 and package proposal gates. Do not change frozen backtest formulas or reinterpret a pass flag alone as authority.

### My recommendation
Implement option A as the minimal non-frozen repair, with typed inputs that preserve metric provenance and explicit recomputation at the promotion boundary. Until then, treat `PROMOTE` as unverified when a caller can construct arbitrary mappings; preserve the separate paper-trial and owner-approval gates and make no claim of live impact.

### Acceptance and regression tests
Build a consistent positive candidate from actual WFO/PBO/DSR/benchmark helper outputs and assert PROMOTE. Mutate each summary flag and each reported metric independently so they contradict; assert BLOCK/`EVIDENCE_MISMATCH` before `draft_package` can return DRAFTED. Test missing/malformed metrics, non-finite values, changed OOS block, PBO threshold boundary, DSR threshold boundary, benchmark direction, package RED LINE and required owner proposal. Confirm no frozen backtest diff, no suggestion/live param file write, and rerun the promotion/backtest suites.

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

### What I read (baseline line references; complete functions and callers)
Against baseline `85b2c155d7b054a468379ddfd802eb239d0801f9`: `promotion.py:241–353` complete `SPRTState`, `sprt_step`, `sprt_monitor`, `rollback_actions`, and `LiveFamilyMonitor.on_trade`; `checkpoints.py:75–90,256–270` M203 durable research monitor table and writer/reader; tests `TestSPRT` (`test_research_promotion.py:155–208`) and `TestMonitorLog` (`test_research_checkpoints.py:206–238`); and matrix rows `R-CP8|6`/`R-CP8|7` (`PHASE2_TRACEABILITY_MATRIX.md:344–345`). `grep -Rn` for `LiveFamilyMonitor`, SPRT actions and their consumers is saved in `H030_consumers.out`; only promotion definitions and tests consume the monitor, while the checkpoint logger has separate direct tests. No connection to `PaperRuntime`, the execution FSM, adapter, or order path was found. No SQLite row/cell/bar selection or production DB query is in this claim, so no query-plan experiment applies.

### Reproduction (command, probe file, actual result)
`H030_sprt_actions.py` runs real `LiveFamilyMonitor` with a sequence of losses. It sets `halted=True` in memory on the 27th outcome, appends 27 entries to its in-memory `log`, and returns `HALT_AND_ROLLBACK`; `sprt_monitor` returns four descriptive strings, including a claim that log statistics are persisted. The monitor object has only `family_id`, `state`, `halted`, and `log`; the probe has no executor, persistent store, callback, or file write. Raw output: `H030_sprt_actions.out`. `tests/unit/test_research_promotion.py -k 'SPRT or live_monitor_halts_and_records'`: 7 passed, 39 deselected (`H030_pytest.out`); these assert statistical stopping/action text and the in-memory flag/log. Separately, `tests/unit/test_research_checkpoints.py::TestMonitorLog`: 2 passed (`H030_checkpoint_log_pytest.out`), proving the generic `ResearchCheckpointStore.log_monitor` can commit and reload a row. That API is not invoked by either SPRT function or `LiveFamilyMonitor`.

### Verdict and independently assigned severity
**PARTIAL, independent severity S2.** The runtime action list is descriptive only: no new-entry gate, position close, package rollback, or durable log call is wired from the SPRT monitor. `LiveFamilyMonitor` does set an object-local `halted` bit, and a separate durable research-monitor table/API exists, so the claim is too broad if read as “no halt state or durable log facility exists anywhere.” But neither state nor facility is connected to a live family execution path. No current live impact is demonstrated because repository-wide consumers contain no production monitor caller.

### Root cause
The SPRT implementation is a pure statistics helper plus an in-memory wrapper. `rollback_actions()` returns strings; `LiveFamilyMonitor.on_trade()` updates `SPRTState`, appends a Python list entry and sets `halted`. `ResearchCheckpointStore.log_monitor()` provides an independent persistence API, but no constructor dependency or call path connects it to the monitor. There are no executor/position-manager/package-registry dependencies in the monitor.

### Direct impact
Calling the exposed helper produces an action description but does not itself block entries, close open positions, change the live playbook/package, or persist a reason/timestamp/statistics row. The only implemented halt is the monitor instance's in-memory boolean. This is a contract-to-code integration gap, not evidence that an active PAPER/LIVE process ignored an SPRT result.

### Secondary effects and interactions (upstream/downstream)
Upstream, caller-supplied boolean trade outcomes advance a family SPRT. Downstream, no production consumer reads the monitor's `halted` flag, invokes an execution/close API, or rolls back a `ParameterPackage`; separate `ResearchCheckpointStore.log_monitor` could persist a record but does not trigger an action and is not called here. The matrix's CP-8 SPRT tests demonstrate stop thresholds and returned strings, not end-to-end protection. The existing D57 watchdog/L3–L5 escalation is a distinct supervision path; ISSUE-077's generic persistence/migration concerns do not by themselves supply family-specific entry gating or position closes. D58's PAPER fill simulator is pending CP-15 and does not establish this integration. No ledger/order trace or actual position was used.

### Contract and decisions
APEX_GEN5 Z.6 (`:17390–17405`) states every promoted family is monitored continuously after injection and an SPRT failure immediately blocks entries, closes open positions, rolls back the setup/package, and logs reason/timestamp/statistics. The checkpoint monitor-log table is a generic persistence mechanism, not proof those actions occur. Matrix `R-CP8|6` lists “SPRT halt/rollback” alongside statistical tests, but its named unit assertions cover the in-memory `halted` state/action strings; `R-CP8|7` separately proves durable generic log rows. These later implementation/matrix facts do not override the normative Z.6 operational outcome. No owner decision was found waiving the action requirement.

### Frozen status and non-frozen alternative
`promotion.py`, `checkpoints.py`, and tests are non-frozen. `apex/research/backtest.py` and `bootstrap.py` are frozen, but no change to either is needed. A non-frozen orchestrator/adapter can consume the SPRT verdict, durably log it with idempotent identity, engage a per-family entry gate, request approved close/rollback operations, and record acknowledgments. Do not let a research-only state machine directly issue exchange orders; any live close path must compose through the authorized risk/execution FSM and owner’s environment controls.

### Fix options and side effects
A: introduce a typed `SPRTAction`/orchestrator interface with injected durable logger, family entry gate, position manager and package registry; return completion/failure receipts and fail closed on missing/failed critical action. B: if Z.6 is intentionally advisory at this stage, obtain an explicit owner decision and amend the operational contract rather than presenting string output as a live halt. Option A affects execution control, idempotency, position-management and restart recovery; must test duplicates, crash/restart between halt/close/rollback, partial close/failure, and environment separation. It overlaps only in broad persistence terminology with ISSUE-077, and specifically goes beyond that item's generic gather persistence; it also does not replace D57 watchdog. CP-15 simulator/close behavior must be reconciled before claiming PAPER fill outcomes.

### My recommendation
Do not describe the current string/in-memory flag as an automatic live safety mechanism. Preserve current research-only arithmetic; route any future execution through an owner-approved non-frozen orchestration layer and test durable restart plus actual plan/position gates before asserting Z.6 completion.

### Acceptance and regression tests
Drive a real SPRT failure through the composed monitor and assert a committed, reloadable log row; after process restart, a family-specific entry gate remains blocked and the prior package identity remains known. Assert exactly-once/idempotent handling and an execution-FSM/position-manager close request, receipt/ledger identity, rollback/no-trade state, and named fail-closed outcomes for logger/close/rollback failure. Verify no new entry can bypass the family halt, no cross-family effect occurs, and no direct venue call bypasses the authorized adapter. Keep existing SPRT formula tests; distinguish helper-only output from end-to-end PAPER/ LIVE execution evidence.

## H-031

### Auditor claim (short quote)
No persistent nightly/continuous orchestration path was found in examined research/bootstrap consumers.

### What I read (baseline line references; complete functions and callers)
Against baseline `85b2c155d7b054a468379ddfd802eb239d0801f9`: `optimizer.py:261–296` full `OptimizerSchedule`, `:331–421` complete one-run `DualOptimizer.run_run`; `bootstrap.py:163–239` command/state handling, `:361–399` complete Phase-2 and Phase-3 handoff; tests `TestPhase2Phase3` (`test_research_bootstrap.py:349–408`) and `TestSchedule` / `TestDualOptimizerRun` (`test_research_optimizer.py:196–314`). `grep -Rn` for `DualOptimizer`, `OptimizerSchedule`, Phase-3 methods and callers across `apex`, `scripts`, and `tests` is saved in `H031_consumers.out`. Also checked matrix rows `R-CP8|8–9` and W.3/W.4 contract. This is a source-repository claim; no phone/OS scheduler or device service was inspected.

### Reproduction (command, probe file, actual result)
`H031_phase3_handoff.py` imports the real `BootstrapRunner`, `OptimizerSchedule`, and `DualOptimizer`. `phase3_plan()` returns metadata (`requires: DualOptimizer`, promotion function, window string and continuous flag); bootstrap methods include only `run_phase1`/`run_phase2` plus the metadata-only `phase3_plan`. `command("continuous on")` sets a boolean in bootstrap state. `OptimizerSchedule` provides predicates and `DualOptimizer.run_run` processes one supplied cell sequence once; no periodic loop/daemon method is present. Raw output is `H031_phase3_handoff.out`. Targeted tests for Phase-3 handoff and all schedule cases: 8 passed in 0.08s (`H031_pytest.out`). The handoff test asserts the `requires` string and schedule label, not a running optimizer. No scheduler process, network, or persistent bootstrap DB was created.

### Verdict and independently assigned severity
**CONFIRMED, independent severity S2 (repository scope).** The code exposes scheduling decisions, continuous-mode state and a Phase-3 plan, but no persistent nightly/continuous runner invokes `DualOptimizer` and `evaluate_promotion` on that schedule. The claim is confirmed for the examined repository composition; an external phone/OS job is not ruled out or tested. Severity S2 because this is an absent research orchestration feature, not an observed PAPER/LIVE order defect.

### Root cause
`OptimizerSchedule.may_run` is a guard, and `DualOptimizer.run_run` is a one-shot async method whose caller supplies cells/evaluator/time/live-workload. `BootstrapRunner.phase3_plan()` returns a dictionary of requirements instead of invoking either. Its `continuous on` command toggles `BootstrapState.continuous`, but no worker/loop consumes it to schedule optimization. Repository consumer search shows only tests call `run_run`; no CLI/script composition invokes it.

### Direct impact
The repository does not autonomously start a nightly optimizer, repeat it on subsequent windows, or resume a long-running continuous optimization service after restart. Calling the Phase-3 plan does not sweep cells. Manual calls to `DualOptimizer.run_run` remain possible and are subject to its in-call time/workload checks. No live parameter injection or order is produced by the missing scheduler.

### Secondary effects and interactions (upstream/downstream)
Upstream, Phase-1 data acquisition and Phase-2 replay can complete and BootstrapRunner can report defaults active. Downstream, no persistent process consumes the plan's cell list, schedules W.4 windows, repeatedly invokes the optimizer, forwards candidates to promotion, or persists a Phase-3 run cursor. Optimizer's separate per-run checkpoints persist cell progress if a caller runs it, but do not create a scheduler. `apex/scheduler` paper-cycle scheduling is a separate runtime path and has no optimizer caller. This is distinct from H-030's absent SPRT action integration and from device watchdog D57; no same-cell or order effect is inferred. No real phone scheduler, external cron, or owner command was examined.

### Contract and decisions
APEX_GEN5 Ch.18 W.3–W.4 (`:17223–17241`) requires per-cell isolated optimization in the default 03:00–05:00 UTC window, immediate halt on live workload, and an owner-enabled continuous run; W.8 defines checkpointing. `BootstrapRunner.phase3_plan` explicitly calls itself a hand-off and its test checks descriptive metadata only. Matrix `R-CP8|8` validates schedule predicates and one-shot per-cell optimizer/checkpoint behavior, not recurring orchestration; `R-CP8|9` records bootstrap phases and a Phase-3 hand-off. No later owner decision was found that marks the Phase-3 scheduler delivered. The file `apex/research/bootstrap.py` is frozen, so the absence cannot be closed by editing its implementation under current constraints.

### Frozen status and non-frozen alternative
`apex/research/bootstrap.py` is frozen; `optimizer.py` and new non-frozen runner/CLI/service code are not. Preserve the metadata contract and build a separate scheduler/orchestrator outside bootstrap that owns persistent schedule state, invokes the optimizer and promotion path, and obeys owner start/stop/continuous controls. Avoid editing frozen backtest/bootstrap or original YAML. Device-resident periodic execution remains device evidence, not source proof.

### Fix options and side effects
A: add a non-frozen scheduler service/CLI with explicit one-shot and continuous modes, UTC clock source, live-workload admission, durable next-run/checkpoint state, restart reconciliation and named pause/error outcomes. This adds persistent state and operational controls and must not wake during live workload or infer owner approval. B: keep the current component as a manual research library and amend the delivery/status contract to say Phase 3 is a plan only; this avoids runtime behavior but leaves W.4 optimization unavailable. Either option must preserve W.3 full-grid rules, W.8 checkpoint semantics, promotion/owner gates, and D57 separation. Hardware battery/disk safeguards are separate from the missing scheduler and require owner/device acceptance.

### My recommendation
Treat Phase 3 as a hand-off only, not an implemented nightly/continuous service. Add orchestration outside frozen `bootstrap.py` only when its owner-controlled run policy, persistence, and live-workload interaction are specified; do not claim phone automation from the existing unit tests.

### Acceptance and regression tests
Use a fake clock and persistent temporary checkpoint store to prove due-run starts at the configured UTC boundary, one complete pass invokes optimizer/promotion once per cell, no work begins during live workload, continuous mode repeats only while owner-enabled, pause/stop survive restart, and expired/restarted runs resume without duplicate cell evaluation. Verify optimizer/promotion outcomes remain suggestion-only and no live `params/` write or order path is reachable. Separately require the exact owner-device service/boot evidence before claiming 24/7 phone scheduling.

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

### What I read (baseline line references; complete functions and callers)
Against baseline `85b2c155d7b054a468379ddfd802eb239d0801f9`: full `ResearchCheckpointStore.save_bootstrap`, `load_bootstrap`, `bootstrap_rows`, and `incomplete_bootstrap_cells` in `checkpoints.py:37–52,148–201`; complete `BootstrapRunner.run_phase1` and `pending_cells` in frozen `bootstrap.py:241–343`; complete `CanonicalMirroredCheckpoints.save_bootstrap`, `_canonical_upsert`, and `BootstrapService.open` in `bootstrap_service.py:832–1011,1155–1179`; and tests `TestBootstrapCursor` plus the bootstrap service mirror tests. `grep -Rn` for save/read/status consumers is saved in `H033_consumers.out`. DDL primary keys and W.6/W.8 resume requirements were read, together with CP9-007's canonical mirror decision. `EXPLAIN QUERY PLAN` for per-cell `load_bootstrap` lookup against in-memory repository migrations reports `SEARCH research_bootstrap_progress USING INDEX sqlite_autoindex_research_bootstrap_progress_1 (cell_id=?)` (`H033_checkpoint_stale.out`). This checkpoint table has a primary-key index; no market/device index is applicable. No persistent DB or `data/` access.

### Reproduction (command, probe file, actual result)
`H033_checkpoint_stale.py` uses actual `ResearchCheckpointStore`, `CanonicalMirroredCheckpoints`, and repository SQLite DDL in two `:memory:` databases. It writes a `COMPLETE` checkpoint at cursor 900 with payload generation `new`, then simulates a stale lower-cursor `PENDING` write at 400 with different payload. Research row becomes `status=PENDING`, cursor remains 900, and generic payload is replaced by `stale`; bars are additively 13. The canonical mirrored `bootstrap_progress` row also becomes `PENDING` while its ISO cursor remains 900ms and bars_written increases to 13. The wiring wrapper preserves its two CP13 evidence keys (`invalid_bars_dropped`, `invalid_reasons`) on non-COMPLETE saves, but does not preserve arbitrary payload fields or status ordering. Query plan and full output are in `.out`. Ran full `tests/unit/test_research_checkpoints.py`: 20 passed in 0.15s; full `tests/unit/test_ops_bootstrap_service.py`: 71 passed in 2.33s (`H033_pytest.out`, `H033_service_pytest.out`). Existing `test_resume_never_rewinds_the_cursor` asserts only that cursor stays at 900 and bars add; it does not assert status/payload monotonicity. Service tests exercise normal mirror behavior, not stale-generation conflict. Both suites pass while the controlled stale-write behavior remains.

### Verdict and independently assigned severity
**CONFIRMED, independent severity S2.** The SQL intentionally applies `MAX` only to cursor, adds bars, and overwrites status/phase/metadata/payload from the latest arriving call. A stale lower-cursor call therefore retains the high-water cursor yet regresses status and generic payload. CP13 has a targeted merge for two invalid-bar evidence keys through the wiring wrapper, which narrows but does not eliminate payload regression. No raw market row is rewound or order path affected. Severity S2: false pending/progress and lost checkpoint metadata can force rework or hide evidence, but the cursor itself remains monotone and real operational loss was not observed.

### Root cause
Neither checkpoint row has a generation/run sequence or compare-and-set predicate. `save_bootstrap` always updates `status`, `phase`, `oi_available`, `updated_at`, and `payload_json` from the incoming write, while protecting cursor with `MAX` and making `bars_ingested` additive. `_canonical_upsert` uses the same `MAX(cursor_open_time)` but overwrites status and increments bars. `updated_at` is assigned at write time, not the source task's logical sequence, so a delayed older operation appears newly updated.

### Direct impact
A completed research cell can be marked PENDING/IN_PROGRESS by a late older save while retaining its completed cursor. `BootstrapRunner.pending_cells` and progress counts use status, so the cell may appear unfinished and be revisited; generic payload metadata may be lost. Cursor high-water does not regress, preventing a backward resume, and the wrapper protects only `invalid_bars_dropped`/`invalid_reasons` on its non-COMPLETE path. Duplicate raw ingestion, data loss, and user-device consequences are not established by the probe.

### Secondary effects and interactions (upstream/downstream)
Upstream, Phase-1 status writes come through `BootstrapRunner` → `CanonicalMirroredCheckpoints` → research table plus canonical Ch.5 mirror. Downstream, `pending_cells`, `progress_async`, `incomplete_bootstrap_cells`, and owner status readers treat durable status as completion truth; stale regression may trigger a repeat walk, though it resumes from the preserved high cursor. Existing CP9-007 supplies the canonical mirror but repeats the same overwrite policy. ISSUE-077 overlaps generic progress/persistence; this finding is specifically missing stale-generation protection, not missing DDL or a lock timeout. No training artifact, engine, decision/risk/order, ledger, or replay impact proven. No device run.

### Contract and decisions
APEX_GEN5 W.6 (`:17276`) says checkpoint Phase-1 progress and resume from cursor without rewinding; W.8-1 (`:17300–17305`) requires durable per-cell state and resume at the next uncompleted cell. CP9-007 (PHASE2_DECISION_LOG.md:170) requires mirroring the cursor into canonical `bootstrap_progress`; it specifies max cursor but does not make status/payload monotone. The current regression preserves cursor but can falsify completed/uncompleted state, so it only partially satisfies the broader durable-resume intent. CP13's evidence merge protects two fields by name. ISSUE-077's progress/persistence scope overlaps; delta is stale-write ordering across status and the rest of payload. No owner decision authorizes stale completion regressions.

### Frozen status and non-frozen alternative
`apex/research/checkpoints.py` and `apex/ops/bootstrap_service.py` are non-frozen. `apex/research/bootstrap.py` and `apex/data_catalog/**` are frozen; do not edit the runner or store DDL. Add a logical run/generation token and conditional upsert/CAS in the non-frozen checkpoint/wiring layer, mirrored consistently to the canonical row. Keep cursor MAX behavior, additive bar semantics where valid, and CP13 carry-forward. Because intentional re-runs can transition COMPLETE→IN_PROGRESS→COMPLETE, do not impose a simplistic monotone status rank; reject only writes older than the current generation/sequence.

### Fix options and side effects
A: add a per-cell run generation or monotone write sequence, supplied by the owning runner and stored in the additive checkpoint row or non-frozen envelope; update research and canonical status/payload only when generation is current. B: serialize all writes through a single writer/lock and discard stale task messages before `save_bootstrap`; this needs an in-process and restart boundary guarantee and may not protect multiple processes. Both require migration/version handling, preserving W.6 cursor MAX, CP13 evidence keys, CP9 canonical mirror and legitimate restart/re-run transitions. Older incomplete checkpoint rows need a safe migration/default generation. Do not delete persisted progress or alter frozen Ch.5 DDL.

### My recommendation
Add generation-aware conditional writes at the non-frozen checkpoint boundary and mirror only accepted writes. Retain the high cursor, but do not let cursor monotonicity stand in for status/payload consistency. Keep `bootstrap.py` and catalog DDL untouched.

### Acceptance and regression tests
Against in-memory repository DDL, apply a current COMPLETE write followed by delayed lower-generation PENDING/IN_PROGRESS and assert status/payload remain current in both research and canonical tables while cursor never decreases. A newer generation must be allowed to perform the intended COMPLETE→IN_PROGRESS→COMPLETE cycle and advance cursor; payload merge must preserve CP13 invalid-bar evidence and current metadata. Reopen DB and verify pending/progress/incomplete-cell decisions match durable accepted generation. Include EXPLAIN for per-cell reads, two-writer/process ordering if supported, locked-write retry behavior, and full checkpoint/bootstrap-service suites. No edits to frozen bootstrap/store schema or `data/`.


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

### What I read (baseline line references; complete functions and callers)
Against baseline `85b2c155d7b054a468379ddfd802eb239d0801f9`: `ForecastRecord.invalidate`, `is_admissible`, `to_dict`, and `build_forecast` in `forecast/logistic.py:133–214,386–482`; all direct callers found by `grep -Rn` for `ForecastRecord`, `.invalidate(`, `build_forecast`, and invalidation reasons are saved in `H035_consumers.out`. Read store/ledger schema for forecast persistence and composition in `engine_context.py:1829–2010`, `plan_bridge.py:760–785,912–975`, production composition in `scripts/run_apex.py` and `PaperRuntime` plan consumption. Tests read: `TestInvalidation` in `tests/unit/test_forecast_logistic.py:263–294`, plus paper-chain forecast and T_DR_003 integration tests. Read APEX_GEN5 §13.1 invalidation and T_FORECAST_INV. No SQLite forecast lifecycle table/query or caller of `.invalidate()` was found; no SQL row query applies.

### Reproduction (command, probe file, actual result)
`H035_forecast_invalidation.py` calls real `build_forecast` and `ForecastRecord.invalidate("REGIME_SHIFT",...)`. State and `to_dict()` become INVALIDATED with the supplied trigger observation ID on that object; the dataclass has no store/database/persistence handle. Raw output is `H035_forecast_invalidation.out`. Full `tests/unit/test_forecast_logistic.py`: 42 passed in 0.10s (`H035_pytest.out`); these prove reason validation, lineage requirement, immutability and inadmissibility on the same object. Production integration checks `test_forecast_is_bootstrap_paper_only` and `test_t_dr_003_forecast_p_u_c_replay_byte_identical`: 2 passed in 0.34s (`H035_production_pytest.out`), proving forecast is rebuilt/consumed for the plan chain and deterministic, not invalidation lifecycle. `grep` finds `build_forecast` in the real producer/bridge but no `.invalidate()` call outside tests. The bridge's `traces` dictionary is in-memory; it serializes `forecast.to_dict()` there, but no forecast-record table/append path exists in the inspected store/ledger DDL. No device, live package, or order was used.

### Verdict and independently assigned severity
**PARTIAL, independent severity S2.** The API method is a local mutation and has no production caller or durable write path; this part is confirmed. But the existing PAPER plan bridge creates a forecast per bridge invocation, uses P/U/C to gate/build that invocation's plan, and stores its diagnostic trace only in memory. No stale forecast reuse or order bypass from failure to invalidate was demonstrated, and §13.1's “never silently deleted” does not by itself specify a durable storage mechanism. Thus this is an implementation/lifecycle gap with potential operational significance, not a proven current trade defect.

### Root cause
`ForecastRecord` is a mutable dataclass; `invalidate()` changes its own `state`/`invalidation` and returns `self`. `build_forecast` returns it to callers. Production bridge uses `forecast.to_dict()` only in `PaperPlanBridge.traces`; the live return shape is a plan dictionary and does not maintain a forecast-record registry that later regime, quality, package, horizon, or source events can address. `grep` found no persistent forecast-record schema and no event-bus subscriber invoking the method.

### Direct impact
In the exposed standalone forecast API, a caller can invalidate an object and see the immutable reason/lineage in its serialization, but it must retain that object itself. In the production PAPER bridge, the forecast is used to evaluate setup/eligibility and copied into an in-memory trace; no persistent forecast record is subsequently invalidated, and the trace is not a lifecycle store. The current bridge builds fresh forecast context per call, so this does not establish that a stale forecast is reused to authorize a later order. Nor does the audit show a trade being opened under an invalidated record.

### Secondary effects and interactions (upstream/downstream)
Upstream sources include E11 confirmed regime, quality, package version, and source freshness. Downstream plan bridge consumes `p_hat`, `u`, `c`, `q_forecast` for eligibility and risk inputs, then returns a plan; `PaperRuntime` consumes/persists plans and execution ledger events, not the ForecastRecord/invalidation envelope. A future stale-source/regime/quality invalidation needs a forecast-ID/lineage map plus downstream revalidation or cancellation/position policy. No D57 watchdog or D58 PAPER fill simulator currently supplies this linkage. D54 is recorded OPEN/not implemented; its broad evidence-expiry scope must not be mistaken for an approved forecast invalidation implementation. No training/cache/hash effect is established.

### Contract and decisions
APEX_GEN5 §13.1 (`:16115–16132`) specifies seven immutable reasons and says an invalidated forecast record receives `{state, reason, at, trigger_observation_id}` and is never silently deleted; T_FORECAST_INV requires all reasons unique, traceable and immutable on fixtures. Current tests establish precisely those local-object properties, and matrix C6-FC|1 / X-11 establish forecast P/U/C construction and deterministic chain replay, not durable invalidation. Section 18.7's cascade text (`:18716–18720`) says downstream consumers are notified via event bus and revalidate; repository search found no ForecastRecord invalidation consumer. D54 remains open and does not override/complete §13.1. No later decision was found authorizing omission of forecast lifecycle behavior.

### Frozen status and non-frozen alternative
`apex/forecast/logistic.py`, `apex/ops/engine_context.py`, `plan_bridge.py`, and `paper_loop.py` are non-frozen; `apex/data_catalog/**` and `apex/research/backtest.py` are frozen. A non-frozen forecast lifecycle service can retain stable forecast IDs, connect invalidation triggers, persist immutable invalidation records using an owner-approved existing append-only schema or additive non-frozen storage, and notify downstream consumers. Do not edit frozen catalog DDL/store or assume the in-memory `PaperPlanBridge.traces` is durable.

### Fix options and side effects
A: keep `ForecastRecord` a pure value object and add an owner-approved lifecycle registry/adapter that stores created forecast identity and each accepted invalidation, handles duplicate triggers idempotently, and publishes a revalidation event to the current plan/position boundary. This requires persistence schema/version, restart reconstruction, event-bus and consumer semantics, and a decision about already-materialized plans/open positions. B: if §13.1 is diagnostic-only until a future wave, obtain a documented owner ruling and label invalidation explicitly unwired; do not advertise automatic invalidation. Option A may alter setup/plan admission and cancel/close policy, requiring replay/decision and PAPER FSM tests; option B preserves current per-cycle fresh forecast behavior but leaves persistent forecasts unsupported. Neither requires a frozen-file change.

### My recommendation
Treat invalidation as implemented only for an explicitly held `ForecastRecord`, not as a production lifecycle. Keep its immutable local-object contract, and do not claim automatic regime/source invalidation. Before wiring, resolve D54 separately and specify ID, persistence, trigger publication, restart, and downstream action/owner authority; leave source and frozen DDL untouched in this audit.

### Acceptance and regression tests
Retain all seven reason/immutability tests. Compose producer → PaperPlanBridge → PaperRuntime with a stable forecast ID and trigger each reason from its authoritative source; assert one durable invalidation row with observation lineage, no silent deletion/relabel, duplicate idempotency and recovery after restart. Verify the bridge/plan consumer rejects or revalidates an invalidated forecast before plan materialization; define separate behavior for an already-open position through authorized Risk Kernel/Execution FSM (do not assume close). Exercise no-match/future-PIT/missing lineage fail-closed, and prove ordinary T_DR_003 byte-identical replay remains unchanged when no invalidation occurs. Any persistence must use an approved non-frozen schema path; no data-catalog DDL edit or live endpoint test.

## H-036

### Auditor claim (short quote)
Bootstrap CVaR is a signed tail mean, not positive portfolio loss validated at the risk boundary.

### What I read (baseline line references; complete functions and callers/callees)
Against baseline `85b2c155d7b054a468379ddfd802eb239d0801f9`: complete frozen `cvar_bootstrap` in `apex/research/backtest.py:354–375`; complete Risk Kernel `size`, `adjudicate`, and `cvar_advisory` in `apex/risk/kernel.py:365–430,468–503,607–621`; full production context construction in `apex/ops/engine_context.py:1829–2001`, full forecast/risk/plan segment in `apex/ops/plan_bridge.py:912–975`, `scripts/run_apex.py` composition at `:745–765`, and `PaperRuntime._resolve_plan`/`execute_plan` at `paper_loop.py:644–695`. `grep -RIn` for `cvar_bootstrap`, `cvar_fraction`, and `cvar_advisory` across `apex`, `scripts`, and `tests` is saved in `H036_consumers.out`. Tests read in full: `TestMonteCarlo.test_cvar_is_the_left_tail`, `TestSizingMachine.test_cvar_advisory_downgrade_reaches_sizing`, and `TestMarginAndTail.test_cvar_is_advisory_only`. Normative APEX_GEN5 §15 tail-risk contract `:16851–16857` and relevant Risk Kernel interface were checked. No SQL row/cell/bar query or database persistence is implicated.

### Reproduction (command, probe file, actual result)
`H036_cvar_boundary.py` uses the real frozen helper on `[0.01,-0.02,0.03,-0.01,0.02]` with seed 7 and 300 paths; it returns `cvar=-0.0088`, a signed mean of bootstrapped lower-tail period returns. The real Risk Kernel `size()` leaves the state at `MediumRisk` for `cvar_fraction=-0.05` and missing input, but downgrades it to `HighRisk` for positive `0.05`. Raw output: `H036_cvar_boundary.out`. The helper test only asserts `cvar <= 0` and path count; the risk tests pass a positive scalar and check the 4% threshold/downgrade, not origin, sign, portfolio positions, correlation, or window. All 121 tests in `tests/unit/test_research_backtest.py` and `tests/unit/test_risk_kernel.py` pass (`H036_pytest_full.out`). There are no cvar references in `scripts/run_apex.py`, `paper_loop.py`, `engine_context.py`, or `plan_bridge.py`; the production context’s risk mapping contains no `cvar_fraction`, and the plan bridge forwards the supplied risk mapping to `adjudicate`. No device/account/order was used.

### Verdict and independently assigned severity
**CONFIRMED, independent severity S2.** `cvar_bootstrap` returns a signed return-series tail mean. The risk interface expects a separate caller-supplied positive `cvar_fraction`; `size()` compares it with the threshold but does not reject negative/nonfinite values or bind it to the frozen bootstrap result. The audit confirms an interface/meaning and validation gap. However, the production PAPER composition does not supply a CVaR value at all, and no production consumer of the research helper was found. Therefore no active PAPER/LIVE sizing failure or order consequence is established; the finding is bounded to the helper/API contract.

### Root cause
The frozen helper bootstraps means of resampled raw return observations, sorts them, and returns the mean of the lower `(1-level)` tail under the key `cvar`. This is a signed return statistic, not a loss fraction of capital for the current portfolio. Separately, Risk Kernel `size`/`cvar_advisory` accept optional `cvar_fraction` and treat values above the 4% cap as a one-level downgrade; no adapter converts, validates, or provenance-binds the research helper output. In current production context, the risk map omits this optional key entirely.

### Direct impact
A consumer that mislabels the negative research return-tail as a positive loss fraction would pass a negative number and receive no downgrade; an arbitrary positive scalar would trigger one regardless of source. The unit tests demonstrate those separated semantics. No current production call does this, so the probe demonstrates the exposed API gap only, not an actual under-sized or over-sized production plan.

### Secondary effects and interactions (upstream/downstream)
Research input is a sequence of returns and a bootstrap seed/path count; it does not model current positions and their correlation records as specified in the risk contract. Downstream, production EngineContextProducer builds a risk mapping from live PAPER account/market/context fields without `cvar_fraction`; `PaperPlanBridge` passes that map to Risk Kernel adjudication and PaperRuntime only consumes its resulting TradePlan. The absent CVaR wiring means there is no present training/cache/hash, ledger, execution, or order consequence proved. Adding it could change ladder multiplier and quantity, which would affect plan identity, replay, and PAPER sizing evidence. No device query-plan evidence applies.

### Contract and decisions
APEX_GEN5 §15 (`:16851–16857`) requires weekly portfolio `CVaR_95` from the Monte-Carlo battery using current positions and correlation records; above the governed fraction of capital (default 4%) it downgrades the risk ladder one level, and computation/window/assumptions are recorded. `backtest.py:cvar_bootstrap` instead defines A10 over a return series and returns the signed tail mean; its unit test checks left-tail sign only. Risk Kernel tests prove behavior only after a positive `cvar_fraction` is supplied. No owner decision was found redefining the return-tail mean as portfolio loss or authorizing the missing production connection. The frozen backtest constraint bars changing the helper in this audit.

### Frozen status and non-frozen alternative
`apex/research/backtest.py` is frozen. Risk Kernel, `engine_context.py`, and `plan_bridge.py` are non-frozen, while `scripts/run_apex.py` and `paper_loop.py` are also editable but should remain composition-only. Keep the research helper’s signed statistic unchanged. A non-frozen portfolio-CVaR provider/adapter can consume current position exposure and correlation records, compute positive loss/capital semantics with governed weekly PIT boundaries, validate finite/nonnegative values, persist computation/window/assumptions, and pass a typed result to the risk boundary. Do not imply current PAPER is already connected.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: add a distinct `portfolio_cvar_fraction` result type/provider in the non-frozen risk integration layer, explicitly deriving positive loss fraction from current positions/correlation and binding to the weekly window and seed/assumptions; have the kernel reject missing provenance, negative, NaN, or infinity before sizing. This introduces account/position dependencies, persistent evidence and replay identity changes, and may lower risk state/quantity; verify the exact current-position and denominator semantics with the owner. B: document the current bootstrap helper as a research-only return-tail utility and leave the normative risk CVaR marked unwired until the portfolio provider is approved. Neither option changes frozen `backtest.py`; option A requires PAPER risk/plan replay updates and downstream sizing acceptance.

### My recommendation
Preserve the frozen helper’s signed return-tail meaning. Do not pass it directly as `cvar_fraction`. Track normative portfolio CVaR as unwired in the current production composition; implement a separately named, owner-approved portfolio-loss provider before claiming the §15 control is active. Keep source read-only in this audit.

### Acceptance and regression tests
Retain both helper left-tail and Risk Kernel threshold tests, then test a full synthetic portfolio with explicit positions, correlation, capital denominator, weekly PIT window, bootstrap seed, and persisted assumptions. Assert positive loss fraction, exact 4% boundary, one-level downgrade only above the boundary, and fail-closed behavior for negative/NaN/infinite/missing provenance. Compose EngineContextProducer → PaperPlanBridge → Risk Kernel and prove the typed result reaches sizing once; assert no downgrade when the provider is explicitly unavailable only under an approved policy, and no live venue call. Re-run backtest/risk suites and deterministic replay with/without the portfolio-CVaR receipt; no frozen file diff.

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

### What I read (baseline line references; complete functions and callers/callees)
Against baseline `85b2c155d7b054a468379ddfd802eb239d0801f9`: complete `Config`/`Params` loader and `_load_yaml` in `apex/config.py:38–146,437–504`; `load_classifier`, `EngineContextProducer.__init__` and `_input_fingerprint` in `apex/ops/engine_context.py:594–604,1760–1783`; the run_apex status/serve composition at `scripts/run_apex.py:570–599,745–779`; and `PaperRuntime._resolve_plan`/`execute_plan` in `apex/ops/paper_loop.py:644–695`. `grep -RIn` for `e11_classifier`, `load_classifier`, and `PARAMS_DIR` across `apex`, `scripts`, and `tests` is in `I001_consumers.out`. Read `tests/unit/test_config.py::test_params_loader_reads_only` and the full config test file. The referenced matrix coverage is Part I's `apex/config.py` env/security contract and frozen parameter-tree row, not an end-to-end runtime artifact test. Read APEX_GEN5 §9.5 artifact path and Session CP-14, plus D24/D47 in the decision log. No secret or `.env` was read.

### Reproduction (command, probe file, actual result)
`I001_classifier_artifact_presence.py` redirects the actual `config.PARAMS_DIR` to a disposable temporary directory: no `e11_classifier_v1.yaml` yields `FileNotFoundError`; adding a test-only YAML mapping at the same filename makes `load_params()["e11_classifier"]` return it. It does not touch repository `params/`. Output: `I001_classifier_artifact_presence.out`. `test_config.py` passed 14/14 (`I001_config_pytest.out`), and the exact `test_params_loader_reads_only` node passed (`I001_params_test.out`): its assertion specifically expects `FileNotFoundError` for `e11_classifier`. The production code uses fixed `PARAMS_DIR = repo_root/params`; `load_classifier()` uses that same default `params/e11_classifier_v1.yaml`. The broader CP14 producer integration node was not used as evidence: its fixture tried to obtain public exchangeInfo and collection stopped at missing optional `aiohttp`; no endpoint was contacted. That failed attempt is recorded in `I001_pytest.out`, and was not retried to honor the no-exchange constraint.

### Verdict and independently assigned severity
**PARTIAL, independent severity S2.** The test’s absent-artifact assumption is confirmed: it queries the repository’s fixed, gitignored classifier path rather than an isolated test path, so a phone-generated runtime artifact present there changes the test result. The normative D24 behavior does require fail-closed behavior when the runtime artifact is absent, so the absent assertion is not itself a product defect. This test proves only the loader’s current checkout-path behavior and not the composed runtime behavior. No device artifact was inspected.

### Root cause
`test_params_loader_reads_only` calls `load_params()` against the module-global `PARAMS_DIR`, then unconditionally expects that accessing `e11_classifier` raises. The runtime classifier is an optional phone-generated YAML in that same directory and gitignored rather than committed. `load_classifier()` also defaults to that path and converts missing/unreadable artifact to `CONFIGURATION_INVALID`. Thus test result can depend on a local device-generated artifact even though the test intends to cover the missing-file branch.

### Direct impact
On the clean checkout, the assertion passes. If the phone-generated artifact is present in the working tree, the parameter-loader test fails even if the artifact is valid. In production, missing classifier is named/fail-closed for E11 context generation: the run_apex status path displays `E11_ARTIFACT` or a refusal; the PAPER composition wires `EngineContextProducer` to `PaperPlanBridge`, and a provider request reaches `_input_fingerprint`/`load_classifier` before producing a context, so missing artifact does not silently produce a plan. The test does not execute this route or prove any plan/order behavior.

### Secondary effects and interactions (upstream/downstream)
Upstream, `train-e11` can create the gitignored classifier artifact; the same path is deliberately used by runtime. Downstream, `run_apex.py` wires producer → plan bridge → PaperRuntime, while `paper_loop._resolve_plan` accepts only the provider's mapping and fails closed if no plan/refusal is returned. Therefore device-artifact presence can affect test reproducibility and product availability (artifact missing → named fail-closed), but no invalid plan, ledger, order, or actual device behavior was observed. Matrix CP-1 config tests verify env/default/no-shadow/no-dotenv properties, and Part I lists committed governed parameter files; this individual assertion is not evidence of full production composition. No query-plan/database effect.

### Contract and decisions
APEX_GEN5 §9.5 tree (`:20415–20435`) lists `params/e11_classifier_v1.yaml` as phone-generated/gitignored/never committed and separately names `tests/fixtures/e11_classifier_v1.yaml` as test-only, never runtime fallback. D24 in `PHASE2_DECISION_LOG.md:296` explicitly requires the absent-artifact case to fail closed only when the E11/plan path is requested, with valid fixture loading as a separate case; D47 (`:1115`) binds the artifact to fit protocol/hash, and D28 (`:440`) includes it in package identity when present. Those decisions confirm both branches and reinforce that a test of absence should not accidentally depend on a device’s runtime artifact. No later decision waives artifact provenance or authorizes a test fallback.

### Frozen status and non-frozen alternative
`apex/config.py` is not among the listed frozen paths, but the artifact path is governed and `apex/research/backtest.py` is frozen/irrelevant. Keep all runtime parameter/model paths unchanged. Make the test hermetic by directing `PARAMS_DIR`/loader path to `tmp_path` for the absent case, and test present/valid loading using the explicitly test-only fixture in an isolated temporary path. Do not copy the fixture into production `params/`, commit the phone artifact, or change runtime fallback semantics.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: isolate the loader test’s params root and assert both missing and present-artifact cases; this preserves D24 while removing device state from test outcome. It changes only tests, but fixture schema/hash assertions must remain meaningful. B: retain the repo-path assertion as an integration check but explicitly skip/mark it when the ignored artifact exists and add a separate hermetic unit test; this adds environment branching and can conceal invalid local artifacts. Do not add a fixture fallback in `load_classifier`; that would violate D24 and could change runtime model identity.

### My recommendation
Keep the missing-artifact fail-closed production contract. Replace the test’s implicit dependency on the working-tree artifact with an isolated path and explicit fixture case. Count the current matrix’s config tests only for the behaviors actually asserted; they do not prove that production `run_apex`/`PaperRuntime` has a valid device classifier or a real device outcome.

### Acceptance and regression tests
In `tmp_path`, assert `Params()["e11_classifier"]` fails when the runtime filename is absent; add a valid test-only artifact at that path and assert the loader returns the expected mapping; reject malformed/hash-invalid artifacts through `load_classifier`. Separately compose producer → plan bridge → PaperRuntime with an explicit test artifact and with a missing artifact: present artifact can proceed only through native inputs, absent artifact yields named `CONFIGURATION_INVALID`/no plan, and neither path reaches an exchange adapter. Run `tests/unit/test_config.py`, the relevant engine-context tests, and no public endpoint. Confirm the ignored runtime file is not committed and frozen YAMLs are unchanged.

## I-002

### Auditor claim (short quote)
Config/foundation tests leave parser, installation, immutability, and fixture boundary gaps.

### What I read (baseline line references; complete functions and callers/callees)
Against baseline `85b2c155d7b054a468379ddfd802eb239d0801f9`: full stdlib `.env`/YAML parser, `_load_yaml`, `Params.__getitem__`, and `load_params` in `apex/config.py:87–147,190–462,463–511`; package tests and `TestNormativeTree` / `TestParamsFrozenValues` in `tests/unit/test_cp1_foundations.py:25–295`; the full `tests/unit/test_config.py`; fixture/artifact tests and D28 temporary-params tests in `tests/unit/test_engine_context.py:19–72,683–766`; run_apex composition `scripts/run_apex.py:745–779`; and paper plan boundary/consumer in `apex/ops/paper_loop.py:644–695`. Grep consumer inventory is in `I002_consumers.out`; production composition and exact matrix Part I rows are in `I002_composition.out`. Read APEX_GEN5 §9.5 parser/tree/artifact clauses and D24/D28. The tests do not call the production run_apex root or execute PaperRuntime as a composed runtime test.

### Reproduction (command, probe file, actual result)
Ran `tests/unit/test_config.py`, `tests/unit/test_cp1_foundations.py`, and three focused engine-context classifier/package tests: **33 passed in 5.66s** (`I002_pytest.out`). These prove exact lock/pyproject text, collect-only/full-suite discoverability, tree/import/literal checks, `.env` parsing cases, plus later CP-14 fixture/missing-artifact and temporary package-hash behavior. `I002_config_boundaries.py` mutates a real `Params` instance’s nested `risk_defaults` mapping: the same object returns the mutation, while a new `load_params()` returns the original YAML value. The `Params` API is not actually immutable. The same probe shows valid flow sequence parsing, but YAML anchors/aliases are silently accepted as the literal strings `&anchor 1` and `*anchor`; block scalar and multi-document examples raise `ValueError`. Raw output is `I002_config_boundaries.out`. `test_run_all_tests_runs_full_suite` invokes `pytest --collect-only`; packaging tests check exact pins/metadata but do not install them. Test output is recorded in `I002_pytest.out`; no network/device or database operation was used.

### Verdict and independently assigned severity
**PARTIAL, independent severity S2.** The CP-1 evidence has confirmed gaps: no CP-1 test proves real package installation; YAML-subset negative-boundary tests are absent and the real parser treats anchor/alias markers as ordinary strings; and `Params` returns mutable cached dictionaries despite “read-only view” documentation. But the broader fixture-boundary portion is not wholly missing: CP-14 engine-context tests explicitly load a test-only classifier, exercise missing artifact refusal, and bind package hashes using temporary copied params. Matrix Part I’s narrower claims (nine pins, config env/no-dotenv behavior, frozen YAML literals) are supported by the named tests; they do not claim parser/immutability or production composition. No product config/file mutation was observed. Severity S2 reflects test/validation and mutable-view boundaries, not a demonstrated order defect.

### Root cause
The CP-1 suite checks declared dependency pins and literal values, while the loader tests focus on valid current files and `.env` grammar. It does not assert `pip install` success or unsupported-YAML rejection. `Params.__getitem__` memoizes and returns the parser’s mutable `dict` directly; mutation persists within that `Params` instance. Separate CP-14 tests added explicit artifact-fixture isolation, so the initial blanket fixture-gap claim overstates the full repository test set.

### Direct impact
An invalid YAML anchor/alias can be accepted as a plain string and then fail later at consumer schema/use, instead of failing at parse time as the loader documentation promises. A caller can mutate a parameter mapping and alter subsequent reads from that same `Params` instance; fresh `load_params()` calls reread their own cache and repository files remain unchanged. A dependency set may satisfy textual pin tests without those packages being installable together, although the matrix separately records a prior clean-clone install/run procedure. There is no evidence that run_apex or PaperRuntime mutates shared params in a live process.

### Secondary effects and interactions (upstream/downstream)
Upstream the matrix Part I config tests (`PHASE2_TRACEABILITY_MATRIX.md:9,14`) prove exact package metadata and env security; the frozen-parameter row `:26` proves specified YAML values. They do not establish unsupported YAML syntax rejection, mapping immutability, or actual install. CP-14 `test_classifier_loader_and_real_bridge_tensor_validation`, `test_artifact_missing_is_lazy_and_has_no_fixture_fallback`, and D28 temp package tests cover fixture boundary/identity separately. Downstream, run_apex wires `EngineContextProducer → PaperPlanBridge → PaperRuntime`; `paper_loop._resolve_plan` accepts only a provider mapping or named refusal, but none of these CP-1/CP-14 unit tests executes that full runtime composition. Mutable params could affect a consumer only if the same `Params` object is passed and mutated; no such production path was found. No data/ledger/order/training/hash side effect was demonstrated. SQLite query plans are not applicable.

### Contract and decisions
APEX_GEN5 §9.5-7 (configuration/parser) documents the supported APEX YAML subset and fail-closed unsupported syntax; the matrix Part I rows record only exact package pins, env names/no-dotenv, required tree and frozen literal values. D24 (`PHASE2_DECISION_LOG.md:296`) requires lazy fail-closed behavior when the runtime classifier artifact is absent and separate valid fixture loading; D28 (`:440`) specifies temp/package binding semantics including the optional classifier file. The tree states the runtime artifact is phone-generated/gitignored/never committed and the test fixture is not a runtime fallback (`APEX_GEN5.md:20415–20435`). These later decisions override no CP-1 test claims; they demonstrate the fixture boundary is covered by CP-14 tests, not by CP-1 alone. No decision was found making returned nested dictionaries immutable by enforcement.

### Frozen status and non-frozen alternative
`apex/config.py` and tests are non-frozen; the six original parameter YAML files remain frozen. Add hermetic tests using a temporary params root for parser syntax and mutation boundaries. If an immutable API is required, freeze nested mappings or return defensive deep copies in a non-frozen wrapper; check callers that currently expect plain dicts before changing shape. Packaging should be verified in a throwaway venv using the exact lock, without changing the lock or installed environment in the repository. Preserve the CP-14 fixture file as test-only and never add it as a production fallback.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: add tests for anchors, aliases, tags, block scalars, multi-documents and malformed flow syntax, and reject unsupported syntax at parser boundary. This may reject previously accepted but invalid parameter documents; revalidate every governed YAML. B: make `Params` return defensive recursive copies or immutable nested mappings and add mutation tests. Copying costs memory and could alter identity/mutation assumptions; recursive immutability can break call sites requiring dict/list. C: add a clean temporary-venv install smoke test for `requirements.lock` and runtime import/startup checks, while preserving pytest as dev-only. These are non-frozen tests/loader work; do not alter the six frozen YAMLs, model artifact, or live composition during this audit.

### My recommendation
Record the matrix’s narrow CP-1 claims as proven by their actual assertions, but do not infer parser/install/immutability/runtime-composition acceptance from them. Add isolated parser, read-only-view, and lock-install checks. Count fixture separation as covered by CP-14 tests, not a gap, and keep all runtime classifier artifacts outside Git.

### Acceptance and regression tests
Test every supported and unsupported YAML form directly against the config parser (including anchor/alias rejection), prove `Params` callers cannot mutate cached state or explicitly relabel the API mutable, and verify a fresh venv can install exact lock pins and import the runtime. Keep CP-14 tests proving valid fixture loading, missing-artifact refusal, and package hashing with optional classifier only in a temporary params directory. Add a composition test for run_apex’s actual producer/bridge/Runtime seam with fake store/clock/adapter and no network, assert missing artifact fails closed and fixture never becomes fallback. Re-run the named matrix CP-1 tests and CP-14 tests; no frozen file or device artifact may change.

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

No coverage claim is made for the following 15 IDs. Each remains UNVERIFIED because the remaining mandatory source/test reads, consumer search, governing clause/decision precedence, reproduction and two-way effect trace were not completed:

`I-003, I-004, I-005, I-006, I-007, I-008, I-009, I-010, I-011, I-012, I-013, I-014, I-015, I-016, I-017`.

Rows with a non-UNVERIFIED status were independently evidenced only to the exact scope stated in their sections. Synthetic tests do not establish real data/device/model behavior. H-002/H-003/H-005/H-006/H-007/H-011/H-013 have new bounded real-function probe evidence in this continuation; untested integration/device assertions remain explicitly excluded. H-004 is PARTIAL as above; H-022 and H-034 retain their prior partial caller/governance/integration review caveat. Full V5 acceptance requires completing all remaining unverified rows, mandatory caller/callee and test reads, and relevant SQLite plan checks where applicable.

## Final counts

| Verdict | Count |
|---|---:|
| CONFIRMED | 28 |
| PARTIAL | 11 |
| REJECTED | 0 |
| UNVERIFIED / incomplete | 15 |
| DEVICE-EVIDENCE-NEEDED | 0 (no real-device dependent claim was assigned this verdict; device evidence was not obtained) |

New findings: `X-V5-001` (test reproducibility depends on unavailable base commit); H-010 (selected scope and realized per-cell contribution are distinct report quantities, without a D30 violation); H-026 (promotion accepts internally contradictory metric/flag summaries at the exposed API); H-030 (SPRT action strings/in-memory halt are not wired to durable or execution actions); H-031 (Phase-3 schedule metadata has no repository runner); H-033 (stale checkpoint writes regress status/payload while preserving cursor); H-035 (forecast invalidation is local-object only; the PAPER trace is in-memory, not a durable lifecycle); H-036 (signed return-series CVaR helper is not positive portfolio-loss CVaR and is unwired from production sizing); I-001 (classifier-absence unit assertion reads the gitignored runtime artifact path and can vary with device state; it does not prove runtime composition); I-002 (CP-1 lacks direct YAML-negative, install, and immutable-view assertions; later CP-14 tests do cover fixture separation).
