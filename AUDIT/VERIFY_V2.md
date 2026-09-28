# APEX_GEN5 independent verification V2

| ID | Independent classification | Independent severity | Result in one line | Probe/raw output | Known owner cross-reference |
|---|---|---:|---|---|---|
| D-001 | **CONFIRMED** | S0 | PAPER composition permits the signed private Toobit path; the mandated simulator is not wired. | `probes_V2/D-001.py`, `.out` | D58 (PAPER fill simulator not wired) |
| D-002 | **CONFIRMED** | S0 | Emergency effects are connected to truthful-looking `_noop_handler` responses; L3 has no orders supplied by the gateway. | `D-002.py`, `.out` | ISSUE-073 |
| D-003 | **CONFIRMED** | S1 | Pause/disable-new stops the entire loop, including management and polling. | `D-003.py`, `.out` | ISSUE-077; D57 |
| D-004 | **CONFIRMED** | S1 | `_stage_execution` submits with both control flags set because it only checks the boot verdict. | `D-004.py`, `.out` | ISSUE-077 |
| D-005 | **CONFIRMED** | S1 | The storage guard reports PAUSE, but `run_cycle` performs catch-up before the guard and does not make the verdict an admission gate. | `D-005.py`, `.out` | D57 |
| D-006 | **CONFIRMED** | S1 | Drift is measured at boot, while the scheduler/runtime instance is not refreshed periodically. | `D-006.py`, `.out` | ISSUE-078 |
| D-007 | **CONFIRMED** | S1 | The in-process watchdog has no scheduled `check`/independent monitor in `serve`; no-heartbeat state stays normal. | `D-007.py`, `.out` | D57 |
| D-008 | **PARTIAL** | S1 | The claimed single-plan ALLOW above the 60% hard cap did not reproduce: the real kernel rejected 6,500 > 6,000. The unproven multi-cell atomic-reservation gap remains. | `D-008.py`, `.out`, `D-008-EQP.out` | ISSUE-079; D57 |
| D-009 | **CONFIRMED** | S1 | Symbol exposure compares the previous exposure, not the proposed post-plan exposure; a 4,000 proposal passed a 2,000 symbol cap. | `D-009.py`, `.out` | — |
| D-010 | **CONFIRMED** | S1 | Native producer risk input has no correlation field; the standalone sizing path can reject, but that does not establish runtime wiring. | `D-010.py`, `.out` | — |
| D-011 | **CONFIRMED** | S1 | Equal opposing same-engine evidence produces agreement 1.0 and `CONSENSUS`. | `D-011.py`, `.out` | D56 (quality-weight lambda, related weighting governance) |
| D-012 | **CONFIRMED** | S2 | Weekly rollover returns `reset=True` while also declaring owner review required. | `D-012.py`, `.out` | — |
| D-013 | **CONFIRMED** | S1 | Two-sided fabric disagreement reached 0.454545, below the 0.60 HARD threshold; only independent MTF conflict can produce HARD here. | `D-013.py`, `.out` | — |
| D-014 | **CONFIRMED** | S2 | Producer penalties 0.4/0.3 pass gates whose code thresholds are 0.5/0.3; the 0.5 conflict boundary conflicts with the traceability clause. | `D-014.py`, `.out` | — |
| D-015 | **CONFIRMED** | S1 | A real family evaluation emitted and passed all gates with confidence 0.39951172547 and collapsed propagation. | `D-015.py`, `.out` | D55 (confidence floor) |
| D-016 | **CONFIRMED** | S1 | `Watchdog.resolve` permits direct `FAIL_CLOSED → NORMAL` and `NORMAL → MANUAL_OVERRIDE` without its own recovery/owner proof. | `D-016.py`, `.out` | D57 |
| D-017 | **CONFIRMED** | S1 | A credential plus no transport returns `delivered=True`; this is not device SMTP evidence. | `D-017.py`, `.out` | D57 |
| D-018 | **CONFIRMED** | S1 | A recovery-log exception propagates before independent sending; zero independent sends occurred. | `D-018.py`, `.out` | D57 |
| D-019 | **CONFIRMED** | S1 | The in-memory recovery head advances while a temporary SQLite file remains empty after reopen. | `D-019.py`, `.out` | D57 |
| D-020 | **CONFIRMED** | S1 | The serve-style watchdog has an unopened recovery log: one RAM row, no DB file. | `D-020.py`, `.out` | D57 |
| D-021 | **CONFIRMED** | S1 | Backup cadence/drill helpers exist, but no scheduler or `serve` consumer was found. | `D-021.py`, `.out` | D57 |
| D-022 | **CONFIRMED** | S1 | Real temporary SQLite drill passed despite `rpo_within_limit=false`; `passed` does not include RPO. | `D-022.py`, `.out` | — |
| D-023 | **CONFIRMED** | S1 | Real temporary-file restore reports `restored=True` for non-SQLite bytes with `integrity_ok=false`. | `D-023.py`, `.out` | — |
| D-024 | **CONFIRMED** | S1 | Missing-path verification created a new SQLite file and accepted zero records as an intact chain. | `D-024.py`, `.out` | — |
| D-025 | **CONFIRMED** | S1 | Plain backup is the default; encryption request fails closed because no primitive is supplied, while device at-rest protection is unknown. | `D-025.py`, `.out` | — |
| D-026 | **CONFIRMED** | S1 | Real `adjudicate` returns ALLOW for missing/NaN quality, staleness, or proposed-notional carriers in the tested direct-input cases. | `D-026.py`, `.out` | D55 (related confidence-floor governance) |
| D-027 | **CONFIRMED** | S1 | Caller-provided loss/margin thresholds change governed veto results in direct `adjudicate` calls. | `D-027.py`, `.out` | — |
| D-028 | **CONFIRMED** | S1 | With real SQLite, ledger, L3 ladder revisions, installed dependencies, and a venue double, boot returned READY and allowed new trades. | `D-028.py`, `.out` | ISSUE-077 |
| D-029 | **CONFIRMED** | S1 | Real ladder writes accept a missing `previous_state`; one later NORMAL revision masks the earlier unauthorized downgrade from the two-row reader. | `D-029.py`, `.out` | — |
| D-030 | **CONFIRMED** | S1 | Real YAML values give `(10,000−8,100)/10,000=0.19` and Emergency L3, but no cancel-all consumer is wired. | `D-030.py`, `.out` | D29; D58 |
| D-031 | **CONFIRMED** | S2 | The CVaR helper runs only in research code; no `cvar_bootstrap` call exists in `apex/` or `scripts/` execution consumers. | `D-031.py`, `.out` | — |

## Verification basis, authority, and limits

The authoritative row wording was taken from `/tmp/AUDIT.md`, not from the compact index. Each row was treated as a hypothesis, including rows labelled reproduced or S0. Source inspection followed the requested files, functions/classes, direct callers/callees, and consumer searches with `grep -rn`; the focused command was:

```text
python3 -m pytest -q -p no:cacheprovider tests/unit/test_risk_kernel.py tests/unit/test_ops_watchdog.py tests/unit/test_ops_backup.py tests/unit/test_fabric_context.py tests/unit/test_setup_gates.py tests/unit/test_execution_fsm.py tests/unit/test_engine_context.py tests/integration/test_ops_paper_loop.py
```

Result: **620 passed, 13 warnings, 0 failed** in 1073.01 seconds. The probes use repository code and repository DDL. All temporary SQLite files were created under `/tmp` and removed; `data/`, secrets, `.env`, a venue, Telegram, and a real device were not accessed. A fixture, a fake transport, or a temporary SQLite file is evidence of code/API behavior only, never real-venue or real-device evidence.

Precedence applied throughout:

1. A binding owner decision in `PHASE2_DECISION_LOG.md` is highest for an unresolved product choice (for example D1 PAPER isolation and D29’s PAPER reservation formula).
2. The normative `APEX_GEN5.md` clause controls the contract when there is no later binding owner decision; its explicit hierarchy is Owner > Risk > Decision > Forecast > Evidence (`APEX_GEN5.md:16755–16757`).
3. A relevant later decision-log amendment/traceability entry explains how a code/doc conflict was resolved; it cannot silently relax a frozen contract.
4. Source code and tests establish implementation behavior, not authority. A test passing against an incorrect implementation does not overrule the governing clause.

The most relevant governing clauses are quoted here. For the rows below, these quotes take precedence over implementation comments and fixture assertions:

- PAPER isolation: “in `APEX_ENV=PAPER` the transport is a deterministic simulator ... sends NO packet to the venue” (`PHASE2_DECISION_LOG.md:194`). The audit’s CP-15 handoff also says the simulator must have durable state.
- Emergency safety: “The ladder is ratchet-only: a downgrade to a less-restrictive level is blocked” and L3 is “Cancel all pending orders” (`APEX_GEN5.md:300`, `320–328`). Protective reflexes include “margin-health auto-cancel-all at the 20% threshold,” while automatic ladder escalation is manual (`APEX_GEN5.md:330–335`).
- Context: “Context is never an order and never a permission” and confidence below 0.40 is “excluded from composition; never a permission” (`APEX_GEN5.md:14809–14815`, `14845–14851`).
- Risk: each of the 14 registry vetoes is independently sufficient to reject, and owner > risk > decision > forecast > evidence (`APEX_GEN5.md:16713–16717`, `16755–16757`). Veto 3 is `portfolio_exposure + proposed > capital_hard_cap` (`16766–16770`).
- Tail risk/margin: weekly portfolio CVaR uses a 1000-path Monte Carlo and is advisory; margin health is polled every reconciliation cycle, with 40% action and 20% automatic L3 (`APEX_GEN5.md:16851–16863`).
- Paper D29: `C` is YAML capital plus realized PAPER P/L, `N` is marked open notional plus full unfilled risk-increasing notional, and the fraction is `(C-N)/C`; missing inputs fail closed (`APEX_GEN5.md:20484–20486`, `PHASE2_DECISION_LOG.md:455`).
- Recovery/backup: startup reconciliation has seven checks and “If any check fails, halt recovery and escalate to manual; do not resume automatic operation” (`APEX_GEN5.md:19063–19085`). RTO/RPO are 30 minutes/5 minutes and hash-chain validation is required before resumption (`APEX_GEN5.md:18905–18917`). The higher-level backup policy requires encrypted incremental backup hourly and on every FSM transition plus quarterly drills (`APEX_GEN5.md:1184–1189`).
- AI.9: fail-closed blocks entries, preserves protective orders, allows only reduce-only management, sends an independent alert, and records state in an immutable recovery log (`APEX_GEN5.md:18996–19005`).

All rows below state the applicable precedence again, along with frozen-file impact, alternatives, and acceptance tests.

## D-001 — PAPER simulator isolation

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** PAPER execution should be an in-process deterministic simulator with durable `paper_sim_state`, while the signed Toobit adapter must not construct or send private venue requests. The current composition instead permits the adapter path and has no wired simulator.

**Independent evidence and result.** **CONFIRMED, S0.** `D-001.out` shows the real `ToobitAdapter.submit_order` captured `POST /api/v1/futures/order`, a signed request, and private-operation query fields using synthetic credentials. No network call was made. `PHASE2_DECISION_LOG.md:194` is binding and says PAPER sends no packet; `APEX_GEN5.md` also separates PAPER/LIVE. This is a code/composition confirmation, not a claim that the owner’s device currently sends packets.

**Contract/decision precedence.** D1 owner decision > the PAPER clauses > adapter implementation/tests. Enabling a session or adding credentials would violate the decision rather than fix it.

**Known owner item.** D58: PAPER fill simulator not wired. D-001 is the isolation boundary that must be fixed before any lower-level PAPER execution evidence is accepted.

**Frozen status and alternatives.** `apex/engines/**`, `apex/data_catalog/**`, `apex/research/bootstrap.py`, `apex/research/backtest.py`, the six original parameter YAMLs, and `requirements.lock` are frozen. Implement the simulator transport, durable state migration, and PAPER composition outside those files; the non-frozen alternative is a hard network-deny adapter seam in PAPER until CP-15 exists. Do not alter the frozen adapter contract or use a real demo account.

**Fix side effects.** A simulator changes fill, fee, pending-order, reconciliation, ledger, identity, and replay behavior. It requires a new state-table identity/hash namespace, restart/reconcile tests, and invalidation of any PAPER artifacts produced by the signed path; no model retraining is inherently required. A parameter/package change would invalidate package and snapshot hashes; this fix should avoid one.

**Acceptance tests.** Assert every private adapter operation raises a named PAPER network-deny or uses only the simulator; run restart with durable fills/pending orders; reconcile simulator positions/orders/fills through the same FSM and ledger; prove no socket/session/private packet is created. LIVE must retain its separate signed path.

## D-002 — emergency handler effects

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** L1–L5 Telegram emergency effects are no-ops or memory flags, and the gateway does not supply L3 open orders, so a successful response can falsely imply cancel/close/safe-mode execution.

**Independent evidence and result.** **CONFIRMED, S0.** The real `_noop_handler` returned `ok=True, recorded=True` for L3 and L5. The real control plane reported L3 batches for three supplied orders, but the handler performed no cancel; gateway composition supplies no actual open-order list. L5 returned protective-looking fields without closing positions.

**Contract/decision precedence.** `APEX_GEN5.md:320–335` requires the named ladder effect and manual owner control; fail-closed/independent evidence clauses outrank a truthful-looking handler result. ISSUE-073 is an owner tracking reference, not permission to keep `ok=True`.

**Known owner item.** ISSUE-073 Telegram emergency handlers no-op.

**Frozen status and alternatives.** Keep frozen engines/data/catalog/research/backtest/params/lock unchanged. The non-frozen alternative is to register real execution/FSM/ledger handlers in `scripts/run_apex.py`, with unavailable handlers returning refusal; do not alter emergency semantics in frozen files.

**Fix side effects.** Real effects create cancel/close intents, ledger events, broker reconciliation, idempotency identities, and possibly ladder revisions. Existing synthetic “success” audit rows and cached readiness/Telegram reports must be invalidated; no retraining is needed. Hashes of emergency payloads and ledger heads change on actual execution.

**Acceptance tests.** Gateway → confirmation → FSM/adapter/simulator → ledger must be tested for L1–L5, partial failures, idempotency, restart, actual open-order input, and post-action reconciliation. `ok=True` is forbidden unless the requested protective effect and durable evidence are confirmed.

## D-003 — pause/disable-new stops protection

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** `PaperRuntime.run` skips the whole cycle when paused or new positions are disabled, stopping gateway, heartbeat, position management, and recovery work rather than only new-entry admission.

**Independent evidence and result.** **CONFIRMED, S1.** The real runtime control predicate returned true for `new_positions_disabled=True`, and the source loop sleeps before `run_cycle`. The existing integration test also proves paused runtime has zero cycles. This is code/fixture evidence, not a device uptime claim.

**Contract/decision precedence.** The ladder contract says L1/L2 preserve and manage existing positions (`APEX_GEN5.md:320–326`); that governs over the loop’s broad sleep branch.

**Known owner item.** ISSUE-077 covers boot/migration/serve/run_cycle composition; D57 covers the watchdog/storage protection family.

**Frozen status and alternatives.** Fix `paper_loop.py`/control composition outside frozen files. A non-frozen alternative is a read-only protection tick that excludes only entry stages while continuing gateway, heartbeat, cancel/close management, and recovery.

**Fix side effects.** Reordering cycles changes timing, scheduler cursor writes, ledger management events, Telegram event order, and replay traces; cycle hashes and cached reports change. No retraining is required and frozen engine outputs remain unchanged.

**Acceptance tests.** Inject L1 and L2 between cycles and during a cycle; assert no new entry, but heartbeat, gateway polling, protection, reconciliation, and emergency handling continue; verify durable cursor and ledger behavior after restart.

## D-004 — control race before execution

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** A control command can set pause/disable-new during a cycle, but `_stage_execution` checks only the boot verdict and can submit in the same cycle.

**Independent evidence and result.** **CONFIRMED, S1.** The direct real `_stage_execution` probe used both `paused=True` and `new_positions_disabled=True`, a READY boot verdict, a valid real `TradePlan`, and a controlled execution seam; it returned an intent submission. The stage never read current control flags.

**Contract/decision precedence.** Owner emergency control and L1/L2 effects in `APEX_GEN5.md:320–335` outrank a stale boot flag; risk/decision cannot authorize after a current owner stop.

**Known owner item.** ISSUE-077.

**Frozen status and alternatives.** Patch the non-frozen paper loop at the last admission point, or use an atomic control-plane admission token/version. Do not change frozen engines or risk formulas.

**Fix side effects.** A control-version check can turn prepared plans into refusals, alter per-cycle budgets, cursor/ledger events, and intent identities; invalidate prepared plan caches for the affected control revision, but not model artifacts or parameter hashes unless contract fields change.

**Acceptance tests.** Inject pause/disable-new after preparation and immediately before submit; require named refusal, zero adapter/simulator call, no entry ledger event, and continued reduce-only management. Test concurrent command ordering and restart.

## D-005 — storage guard admission/order

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** `storage_guard` reports PAUSE below 15% free space but `run_cycle` runs catch-up first and stores/alerts the result without stopping admission or prior writes.

**Independent evidence and result.** **CONFIRMED, S1.** The real guard returns `PAUSE` at 10% free, while `run_cycle` source order is catch-up, heartbeat, then storage guard. No early hard gate exists before catch-up or entry.

**Contract/decision precedence.** The 15% storage floor is the normative safety clause and D57 owner item; implementation order cannot make a post-write observation an admission decision.

**Known owner item.** D57 disk floor/L1–L2/watchdog/L3–L5 scheduled CP-15/16.

**Frozen status and alternatives.** Change only non-frozen runtime/ops composition. A non-frozen alternative is a preflight storage gate before catch-up plus a minimal emergency/recovery writer exception, with explicit policy for alerts when the disk is already full.

**Fix side effects.** Earlier refusal changes raw catch-up, quality facts, cursor, ledger, snapshot and alert timing; any interrupted writes need idempotency/replay handling. No retraining; new storage-state fields would change context/package hashes only if included in identity.

**Acceptance tests.** Inject 10%, 15%, and 20% free space; prove no nonessential write or entry below the strict boundary, while the protective path remains available; restart after refusal and verify chain integrity.

## D-006 — periodic drift propagation

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** Clock drift is measured at boot but not refreshed or propagated to the scheduler/admission during a long-running serve process.

**Independent evidence and result.** **CONFIRMED, S1.** The real clock utility distinguishes 0.05 and 0.6 seconds, but the runtime constructs its scheduler with the default and retains the boot verdict. No periodic check/refresh consumer was found.

**Contract/decision precedence.** `APEX_GEN5.md:18905–18907` requires ±100 ms and pauses trading over 500 ms; ISSUE-078 is an implementation owner item. These rules outrank a one-time READY result.

**Known owner item.** ISSUE-078 clock drift latency.

**Frozen status and alternatives.** Add a periodic clock provider/admission state in non-frozen scheduler/runtime files. Do not modify frozen engines or the backtest clock. An alternative is a watchdog-owned freshness token that blocks entries when expired and drives recovery without changing historical replay.

**Fix side effects.** Drift state changes schedule eligibility, timing, snapshot/as-of values, plan identities, and replay determinism; invalidate decisions made after an untrusted measurement, not model training. Record provider/version in the context identity if it is consumed.

**Acceptance tests.** Start READY, inject drift and provider unavailability between closes, require immediate no-entry/degraded state, preserve reduce-only/emergency paths, then prove controlled recovery only after a fresh measurement.

## D-007 — watchdog wiring/independence

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** `serve` constructs a watchdog and records heartbeat but does not schedule `check`/observe or inject an independent channel; an object in the same process cannot independently detect host death.

**Independent evidence and result.** **CONFIRMED, S1.** A real watchdog with no heartbeat at a far-future observation returned `missed=0, host_down=False`; source search found no `check` schedule in `serve`. External phone monitoring was not tested.

**Contract/decision precedence.** AI.9 requires an independent alert and immutable log (`APEX_GEN5.md:18996–19005`); device monitoring, if any, is external evidence and cannot be inferred from the object.

**Known owner item.** D57.

**Frozen status and alternatives.** Wire a separate process/service or a device scheduler in non-frozen ops/deployment files. The non-frozen in-process fallback can improve heartbeat checks but is not an independent host-death detector and must be labelled as such.

**Fix side effects.** A second writer/channel affects recovery-log locking, alert IDs, network credentials, retention, and restart semantics; no model retraining. Existing uptime claims and heartbeat cache need revalidation.

**Acceptance tests.** Kill/hang the runtime, stop Telegram, and stop before first heartbeat; an independent monitor must alert with durable evidence, bounded retries, and no false normal baseline.

## D-008 — stale/non-atomic exposure admission

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** Context preparation is concurrent and risk is not re-adjudicated against exposure created by other plans, allowing multiple plans to exceed capital/reservation ceilings.

**Independent evidence and result.** **PARTIAL, S1.** The audit’s quoted single-plan example did not reproduce at the stated values: the real kernel evaluated `portfolio_exposure + proposed_notional = 6,500` against `capital_hard_cap = 6,000` and returned `REJECT`/veto 3. This rejects the over-cap individual plan. The remaining hypothesis is still supported structurally: `run_cycle` prepares all due cells and `_stage_risk` validates plan shape rather than creating an atomic exposure reservation; no multi-cell race/real order was run. Therefore this row is not confirmed in its original broad form.

The SQLite planner probe is additional evidence. Without the two requested device indexes, raw/facts/prior/ledger queries include scans. With `idx_mo_sym_tf_open` and `idx_pit_scope_asof`, the market-symbol and prior queries improve, but the raw join still scans `raw_observation`, facts still scans through the snapshot primary-key index, and ledger still scans. `D-008-EQP.out` records both plans with `PRAGMA automatic_index=OFF`.

**Contract/decision precedence.** Veto 3’s exact carrier is normative (`APEX_GEN5.md:16766–16770`); D51’s decision-log rule reserves only a valid trade immediately before admission, but it is not a full exposure reservation. The contract controls the missing multi-plan proof; the rejected single-plan counterexample is not evidence of a defect.

**Known owner item.** ISSUE-079 engine-context fingerprint/window performance; D57 risk/runtime scheduling. 

**Frozen status and alternatives.** Do not change frozen engines/catalog/backtest. A non-frozen alternative is a single writer/admission reservation table or serialized risk gate over filled plus reserved notional, with explicit release on cancel/refusal and a bounded context cache.

**Fix side effects.** Reservation adds durable rows, transaction ordering, intent identities, cache invalidation, ledger/replay events, and possible contention/latency. Context fingerprints and snapshot/package hashes must include any risk-state revision used for a decision; retraining is not required. Adding the two indexes is a schema/performance migration and changes query plans, not model outputs.

**Acceptance tests.** Run two or more due cells concurrently with known pending/filled exposure; the sum of reservations plus filled exposure must never exceed cap. Exercise rollback, partial fill, cancel, restart, and old database migration. Re-run every EQP with and without both indexes and record remaining scans.

## D-009 — post-plan symbol cap

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** Veto 5 tests prior per-symbol exposure, not the exposure after adding the proposed order, so a plan can exceed the 20% symbol cap.

**Independent evidence and result.** **CONFIRMED, S1.** The real `adjudicate` with 4,000 proposed notional, prior symbol exposure 0, symbol cap 2,000, and hard cap 6,000 returned `ALLOW` with quantity 40. The post-plan 4,000 is above the symbol cap. This is direct kernel behavior; no device/venue claim is made.

**Contract/decision precedence.** The exposure registry carrier and owner risk ceiling outrank the current-vs-proposed implementation (`APEX_GEN5.md:16770`).

**Known owner item.** None specifically mapped; D-009 is independent of D-008’s multi-cell reservation issue.

**Frozen status and alternatives.** Patch the non-frozen risk input/admission seam. A non-frozen alternative is a final post-sizing exposure projection before submit; do not alter frozen engines or parameter YAMLs.

**Fix side effects.** Rejection/reduction changes plan quantities, intent IDs, hashes, ledger events, and downstream forecast/decision audit records; any cached plan must be invalidated. No retraining; frozen package files remain unchanged.

**Acceptance tests.** Test current + pending + proposed exposure at below, equal, and above cap, including partial fills, reduce-only orders, symbol aliases, restart, and replay. Require rejection/reduction before any adapter/simulator call.

## D-010 — correlation wiring and units

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** The native producer does not pass correlation into risk; naively connecting it would mix notional units with a dimensionless cap and can reject valid trades.

**Independent evidence and result.** **CONFIRMED, S1.** The real standalone sizing call with rho 0.95 returned `REJECT/PORTFOLIO_CAPACITY` under the supplied correlation cap, while source inspection of the native producer’s risk mapping found no correlation field. Thus the current runtime omission is confirmed; the standalone result is not proof of native execution.

**Contract/decision precedence.** The owner risk hierarchy and correlation/exposure contract outrank a raw field connection. A later fix must reconcile units before wiring; it must not silently substitute `rho × dollars` for a dimensionless cap.

**Known owner item.** None directly listed.

**Frozen status and alternatives.** Keep frozen engine formulas. Add a non-frozen typed correlation projection containing unit, PIT timestamp, symbol scope, and denominator; or conservatively refuse correlation-dependent sizing until that projection is present.

**Fix side effects.** REDUCE/REJECT changes quantity, plan/intent hashes, exposure reservations, replay outputs and risk audit. Correlation feature cache identity must include window/package/version; retraining is needed only if model features change, not for a risk projection.

**Acceptance tests.** Test rho below/equal/above limit with dollar units and known capital, missing/stale rho, multiple symbols, and the exact `resolve → risk → plan` path. Preserve the 14-veto-before-sizing order.

## D-011 — equal opposing evidence

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** Opposing same-group evidence can cancel to zero; the reducer skips the zero dominant direction and reports perfect agreement/consensus.

**Independent evidence and result.** **CONFIRMED, S1.** Two real ACTIVE E05 refs with equal quality and opposite direction returned agreement `1.0`, disagreement `0.0`, and `resolve(...)=CONSENSUS`. This confirms the reducer defect only; all gates and an order were not claimed.

**Contract/decision precedence.** `APEX_GEN5.md:14809–14815` says context is not permission, while the conflict contract and owner risk hierarchy require conflict to be conservative. D56 quality-weight governance is related but cannot make a tie positive evidence.

**Known owner item.** D56 quality-weight lambda, as a related weighting decision; D-011 itself needs a conflict-law decision.

**Frozen status and alternatives.** Fix the non-frozen fabric/conflict reducer. A non-frozen alternative is to map a zero dominant sum to `INSUFFICIENT_EVIDENCE`/material conflict without changing engine formulas or weights.

**Fix side effects.** Context confidence, penalties, setup IDs, plan decisions, identity hashes, caches, and replay outputs change for affected evidence; invalidate derived snapshots and retrain nothing unless evidence becomes a model-label input.

**Acceptance tests.** Property-test equal and near-equal opposing votes, same-engine duplicates, multi-engine groups, zero members, and MTF conflict. No balanced opposition may yield CONSENSUS or a permission.

## D-012 — weekly circuit-breaker reset

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** The reset helper returns weekly reset true on UTC rollover without requiring the owner review it declares required; the current PAPER account path has a separate guard.

**Independent evidence and result.** **CONFIRMED, S2.** The real helper returned `reset=True, owner_review_required=True` for weekly rollover with `owner_reviewed=False`. The native PAPER consumer’s additional check prevents claiming that the current runtime bypasses the breaker.

**Contract/decision precedence.** The owner/risk clause says resets are time-based or owner-review-based only (`APEX_GEN5.md:16845–16849`); the helper’s output is not a permission to override that clause.

**Known owner item.** None.

**Frozen status and alternatives.** Fix the helper in non-frozen risk code. An alternative is returning `eligible_by_time=True` rather than `reset=True` until owner review is supplied.

**Fix side effects.** Reset-state and cached circuit reports change; event/head hashes may change when a reset is recorded. No retraining or frozen-file change is needed.

**Acceptance tests.** Rollover alone must not reset weekly loss; rollover plus valid owner review after the breach may; daily and consecutive-loss rules remain independent and persistent through restart/replay.

## D-013 — fabric HARD conflict reachability

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** With nonnegative weights, a purely two-sided fabric disagreement cannot reach the 0.60 HARD threshold; ties are separately mishandled by D-011, while explicit MTF conflict can still be HARD.

**Independent evidence and result.** **CONFIRMED, S1.** Real E05-positive/E06-negative evidence returned disagreement `0.454545...` and `MATERIAL_CONFLICT`, not HARD. The mathematical maximum for this reducer is at most one-half for a two-sided tie/opposition; `mtf_conflict=CONFLICTING` remains an independent HARD route.

**Contract/decision precedence.** The normative `resolve` table at `APEX_GEN5.md:14911–14912` and the owner risk registry control the threshold. This is a contract reachability mismatch, not grounds to silently lower the threshold.

**Known owner item.** None.

**Frozen status and alternatives.** Change the non-frozen conflict projection or obtain an owner decision on threshold/group law. A safe alternative is explicit `HARD_CONFLICT` for a governed severe two-sided state at the producer boundary, without modifying frozen engines.

**Fix side effects.** Conflict classifications alter penalties, gates, veto 6, plan hashes, caches and replay; no retraining unless the conflict is a training feature. Preserve the independent MTF path.

**Acceptance tests.** Property-test all nonnegative engine weights and group combinations, verify the maximum reachable disagreement against the governing table, test the corrected severe state, and retain MTF HARD behavior.

## D-014 — conflict/redundancy hard gates

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** The producer emits conflict 0.4 and redundancy 0.3, while Gate 3 blocks only above 0.5 and Gate 4 only above 0.3; the traceability matrix says conflict above 0.4 blocks and gives 0.5 as failing.

**Independent evidence and result.** **CONFIRMED, S2.** Real `penalties` returned 0.4/0.3. Gate 3 passed 0.4 at threshold 0.5; Gate 4 passed 0.3 at threshold 0.3. The score penalty remains active and MTF Gate 5 is separate. This confirms a governance/code mismatch, not that every setup passes.

**Contract/decision precedence.** The traceability/owner decision must resolve the conflict; current source comments cannot overrule `APEX_GEN5.md`’s governed penalty law. Until decided, do not silently change frozen YAMLs.

**Known owner item.** None directly; record as a contract decision required before patching.

**Frozen status and alternatives.** `params/setup_weights_v1.yaml` and the frozen engine/data files remain untouched. A non-frozen alternative is a versioned gate projection that explicitly declares these ranges nonblocking, or changes only the non-frozen gate threshold after owner approval.

**Fix side effects.** Gate outcomes alter setup emission, setup IDs, downstream forecasts/plans, caches, replay and evidence hashes; retraining is not inherently required. Any threshold change changes parameter-package identity if governed values are involved.

**Acceptance tests.** Enumerate every producer penalty value, assert the intended block/pass and reason, and test `penalties → run_all → bridge → risk` with the traceability matrix updated.

## D-015 — collapsed context propagation

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** Family and bridge carry scalar confidence but do not enforce `COLLAPSED`/confidence below 0.40 as a no-emission condition.

**Independent evidence and result.** **CONFIRMED, S1.** A real `evaluate_cell` call with confidence `0.39951172547`, propagation explicitly reported as `COLLAPSED`, required synthetic ACTIVE refs, valid close-shaped bars, and otherwise passing inputs returned `status=EMITTED`, `reason=ALL_GATES_PASS`, final score 0.9000000000000002. No missing-close excuse applies to this probe. Native full producer/venue wiring was not claimed.

**Contract/decision precedence.** The explicit collapsed rule (`APEX_GEN5.md:14845–14851`) outranks the family API’s scalar-only behavior. D55 confidence-floor ownership is relevant; the implementation cannot turn the scalar into a permission.

**Known owner item.** D55 confidence floor.

**Frozen status and alternatives.** Do not modify frozen engines/data/catalog. Add a non-frozen propagation-band field with context identity/as-of and a hard pre-scoring refusal in family/bridge; alternatively refuse any context lacking an explicit admissible/confirmatory band.

**Fix side effects.** Existing setup/family/plan IDs and snapshot/context hashes for collapsed inputs become invalid; forecast/risk/ledger downstream rows may disappear or become named refusals. No retraining unless training consumes setup emissions; package identity changes only if a governed parameter changes.

**Acceptance tests.** With all required closes present, test confidence below 0.40, exactly 0.40, 0.399999, and data trust below 0.30; collapsed must not emit, confirmatory must be non-permission, and admissible may proceed only with complete lineage.

## D-016 — watchdog state transitions

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** `Watchdog.resolve` changes state based mainly on a target enum and does not require cause resolution, reconciliation, owner authorization, or a durable success log.

**Independent evidence and result.** **CONFIRMED, S1.** Real calls moved `FAIL_CLOSED → NORMAL` and `NORMAL → MANUAL_OVERRIDE` directly, with `require_startup_reconciliation=False` for both. The method was not found wired into serve; that limits current occurrence, not the API defect.

**Contract/decision precedence.** AI.9 exact transitions require FAIL_CLOSED → RECOVERY or owner MANUAL_OVERRIDE, and recovery → NORMAL only after startup reconciliation (`APEX_GEN5.md:19063–19085`).

**Known owner item.** D57.

**Frozen status and alternatives.** Patch non-frozen watchdog state machine and route recovery through FSM/ledger. A non-frozen alternative is to make `resolve` a proposal requiring a durable attestation consumed by the FSM.

**Fix side effects.** State transitions/logs, recovery IDs, readiness, caches and replay traces change; invalidating prior false recovery events is required. No retraining or frozen-file changes.

**Acceptance tests.** Direct illegal transitions must fail; valid owner/reconciliation transitions must append and commit a chain record; restart must not reopen normal state from an unverified row.

## D-017 — independent alert delivery

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** `SendOnlyGmailChannel` reports successful delivery when a credential exists but no transport is injected; current serve does not inject the channel.

**Independent evidence and result.** **CONFIRMED, S1.** With synthetic credentials and `transport=None`, real `send` returned `delivered=True` and appended to `sent`; no SMTP/network evidence exists. This is an API false positive, not a device-delivery claim.

**Contract/decision precedence.** AI.9 requires an independent alert; a credential alone is not an ACK. D57’s independent watchdog work remains open.

**Known owner item.** D57.

**Frozen status and alternatives.** Add a transport-required seam in non-frozen ops/deployment code; until configured, return `delivered=False`/named refusal. Do not read or add secrets in this verification.

**Fix side effects.** Alert IDs, recovery log state, retries, owner notification timing, and caches change; no model retraining or frozen-file update. Existing “sent” records need a migration/semantic reclassification.

**Acceptance tests.** Transport success must return an authenticated delivery/ACK; transport missing, timeout, rejection, and invalid recipient must fail closed with bounded retries and durable evidence.

## D-018 — logging before alert

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** `Watchdog.check` and `enter_fail_closed` append to the recovery log before attempting independent/Telegram alerts, so a log exception can suppress the alert.

**Independent evidence and result.** **CONFIRMED, S1.** A real `check` with a failing log raised `OSError:synthetic-log-failure`; independent calls were zero. This did not claim an actual disk outage.

**Contract/decision precedence.** AI.9 requires both immutable recording and independent alert; one failed side must not silently erase the other. Fail-closed remains mandatory.

**Known owner item.** D57.

**Frozen status and alternatives.** Patch non-frozen watchdog ordering/error handling. The alternative is a durable outbox/alert attempt that is independent of the recovery-log commit, with later reconciliation.

**Fix side effects.** Event ordering, retry IDs, alert/log hashes, and recovery replay change; no retraining. Existing logs cannot prove delivery and must be labelled accordingly.

**Acceptance tests.** Inject log failure, transport failure, both, and recovery; state remains protective, the independent send is attempted independently, failures are bounded and visible, and later log reconciliation is durable.

## D-019 — recovery-log atomicity and verification

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** `RecoveryLog.append` advances RAM rows/head before SQLite INSERT/commit, and verification does not compare stored parent hash to the recomputed parent.

**Independent evidence and result.** **CONFIRMED, S1.** With a real temporary SQLite file, a row appended while the DB handle was unavailable appeared in RAM/head but disappeared after reopen. Source review also confirms memory mutation precedes commit and `verify` recomputes from its in-memory parent rather than validating the stored `parent_hash` field.

**Contract/decision precedence.** AI.9’s immutable recovery-log clause and the hash-chain/backup clauses outrank this implementation ordering.

**Known owner item.** D57.

**Frozen status and alternatives.** Fix non-frozen watchdog log transaction ordering and triggers. A non-frozen alternative is a single durable append worker that owns both the mirror and head; no frozen file or model changes.

**Fix side effects.** Append failures may change caller retry behavior and recovery IDs; existing broken chains require quarantine/migration, and verification/head caches must be invalidated. No retraining.

**Acceptance tests.** Fail first INSERT, fail commit, restart, mutate parent/hash, and attempt UPDATE/DELETE. Only committed rows advance memory; verification must reject mismatch before recovery.

## D-020 — serve recovery-log lifecycle

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** `serve` constructs a path-bearing `RecoveryLog` but does not open/close it; fail-closed records stay RAM-only.

**Independent evidence and result.** **CONFIRMED, S1.** The real serve-style object had `db_bound=false`, no path file, and one in-memory fail-closed row after `enter_fail_closed`.

**Contract/decision precedence.** AI.9 immutable recovery-log persistence and startup reconciliation prevail over composition convenience.

**Known owner item.** D57.

**Frozen status and alternatives.** Add lifecycle open/verify before watchdog use and close after commit in non-frozen `scripts/run_apex.py`/ops code. An external append-only recovery service is a non-frozen alternative, provided ownership and restart semantics are explicit.

**Fix side effects.** DB migration, writer ownership, WAL files, lock contention, recovery IDs, startup latency, and close/error paths change; no model retraining. Existing RAM-only evidence cannot be promoted to durable evidence.

**Acceptance tests.** Open a real temporary file, append through the serve composition, restart, verify chain, and fail closed when open/migration/commit fails.

## D-021 — backup/drill scheduling

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** Backup interval and 90-day drill helpers are constants/functions only; no periodic backup or restore-drill scheduler is wired to serve.

**Independent evidence and result.** **CONFIRMED, S1.** Real helpers reported 15-minute/90-day policy, but repository consumer search found no `SQLiteBackupManager`/`restore_drill` scheduler in serve. Owner device scheduling is unknown.

**Contract/decision precedence.** The higher-level APEX policy requires hourly and FSM-transition backups plus quarterly drill (`APEX_GEN5.md:1184–1189`); this is stricter than the module’s 15-minute constant and must be reconciled by owner decision rather than guessed.

**Known owner item.** D57.

**Frozen status and alternatives.** Implement scheduler/procedure in non-frozen ops/deployment files. A documented external phone scheduler is a non-frozen alternative, but it needs a durable last-success record, destination, retention, key custody, and drill evidence.

**Fix side effects.** Backup files, encryption keys, disk use, retention, timestamps, and operational identity change; schema/ledger hashes should not. No retraining; storage/index performance may change.

**Acceptance tests.** Use a real temporary SQLite file for interval, FSM-transition, failure, restart, retention, and quarterly-drill simulations; then obtain separate device evidence for the actual scheduler and off-device destination.

## D-022 — restore-drill verdict

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** `restore_drill` fixes RPO at zero, checks counts/breaks only, and does not make RPO or backup integrity a pass criterion.

**Independent evidence and result.** **CONFIRMED, S1.** The real temporary SQLite drill created 25 ledger records, backed up/restored them, and returned `passed=true` while `rpo_within_limit=false` because the probe set `rpo_limit_seconds=-1`. The code’s `passed` expression includes zero data loss, integrity, and RTO, but not RPO. This does not prove a production-volume drill.

**Contract/decision precedence.** `APEX_GEN5.md:18909–18917` makes RPO ≤5 minutes and chain validation mandatory; G-RESTORE-001 is not satisfied by a count-only pass.

**Known owner item.** None; D-021 scheduling is separate.

**Frozen status and alternatives.** Patch non-frozen backup/restore verdict logic; do not change frozen DDL. Alternative: a wrapper gate can refuse resumption unless it independently validates RPO, full digest/state, and backup integrity, while the low-level API remains descriptive.

**Fix side effects.** Existing drill reports change schema/meaning and may invalidate gate artifacts; hashes of restore reports change, but ledger/model hashes need not. No retraining.

**Acceptance tests.** Real temporary database with same-count/different-head, non-ledger corruption, old backup beyond RPO, failed integrity, and power/copy faults must fail; a valid T0/T0+30-minute drill must pass only with complete state and chain.

## D-023 — restore integrity gate

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** `restore` copies a source even when its integrity flag/SHA is bad and reports restored success without a pre-restore trust gate or atomic staging.

**Independent evidence and result.** **CONFIRMED, S1.** A real temporary file containing non-SQLite bytes returned `restored=true` and `integrity_ok=false`; source and target SHA matched only because the invalid bytes were copied. No live resume consumer was claimed.

**Contract/decision precedence.** Hash verification before resumption and fail-closed security (`APEX_GEN5.md:18909–18917`, `18996–19005`) outrank the API’s copy result.

**Known owner item.** None.

**Frozen status and alternatives.** Add staging, source integrity/SHA/manifest verification, atomic replace, and refusal in non-frozen backup code. Alternative wrapper gate: never treat `restored` as trusted until a separate read-only verifier passes, while preserving the old copy API only for tooling.

**Fix side effects.** Destination file replacement, WAL/journal files, backup identity, restore report hashes, and operator rollback change; no retraining or frozen-file impact.

**Acceptance tests.** Bad SQLite, SHA mismatch, failed integrity, target exists, mid-copy fault, and power-loss simulations must preserve the prior good target and report failure; valid restore must verify chain/state before resumption.

## D-024 — missing/empty restore verification

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** `verify_restored_ledger` can create a missing/new SQLite DB through writable migrations and regard zero records as an intact chain.

**Independent evidence and result.** **CONFIRMED, S1.** On a real temporary missing path, verification changed `before_exists=false` to `after_exists=true` and returned `records=0, intact=true, positions=0`. This directly confirms the API behavior; no owner database was touched.

**Contract/decision precedence.** Read-only/full-state verification and the restore-before-resumption clause prevail; an empty newly created DB is not a valid restored ledger.

**Known owner item.** None.

**Frozen status and alternatives.** Make verification open an existing file read-only with expected schema/manifest/count/head, in non-frozen backup/ledger code. Alternative wrapper: precheck path and immutable expected digest before calling the current verifier, but a writable verifier should not be used for acceptance.

**Fix side effects.** Read-only opening and migration separation affect schema version handling, WAL locks, verification hashes, and restore tooling. Existing empty-file reports must be invalidated; no retraining.

**Acceptance tests.** Missing path, no-ledger schema, empty DB, wrong head/count/digest, and valid restored DB; assert no file creation or schema mutation in negative cases.

## D-025 — encryption at rest

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** Default backup is plaintext and encryption is unavailable in the supplied dependency set; the actual device’s at-rest encryption is unknown.

**Independent evidence and result.** **CONFIRMED, S1.** A real temporary SQLite backup returned `encrypted=false`; `encrypt=True` failed with `ENCRYPTION_UNAVAILABLE_IN_SBOM`. This proves the API does not provide encryption, not that the owner’s filesystem lacks it.

**Contract/decision precedence.** `APEX_GEN5.md:1155–1158` requires encryption at rest; “allowed” is not “implemented.” The implementation must fail closed or use an approved external encryption policy.

**Known owner item.** None.

**Frozen status and alternatives.** Do not modify `requirements.lock` or frozen files. A non-frozen alternative is an approved OS/device encrypted volume plus an external encryption tool/key-custody procedure; otherwise refuse backup destination rather than label plaintext secure.

**Fix side effects.** Encryption changes backup bytes/SHA, key rotation/custody, retention, restore dependencies, and cache/report identities; no model retraining. Existing plaintext copies require discovery/retention handling, not silent relabelling.

**Acceptance tests.** On the target device, prove file and backup ciphertext/permissions, key-unavailable failure, rotation, restore, and off-device transport; temporary fixture success is insufficient.

## D-026 — nonfinite/missing risk carriers

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** Direct `adjudicate` accepts missing or NaN quality, staleness, and proposed-notional values because comparisons with `None`/NaN do not fire the relevant vetoes.

**Independent evidence and result.** **CONFIRMED, S1.** Real direct calls for `q_raw=None`, `q_raw=NaN`, `staleness_seconds=NaN`, and `proposed_notional=NaN` returned ALLOW in the tested clean-input combinations. The native producer has separate finite guards, so this does not prove native bypass; it proves the kernel boundary is permissive.

**Contract/decision precedence.** The QX/NaN/Inf fail-closed rule (`APEX_GEN5.md:14741`) and the 14-veto contract outrank producer-only validation.

**Known owner item.** D55 is related confidence-floor governance; D-026 is the broader kernel schema-boundary problem.

**Frozen status and alternatives.** Add complete finite/type/range validation at the non-frozen kernel seam. Alternative: an immutable typed risk-input constructor used by every caller, while keeping a defensive kernel guard; no frozen-file change.

**Fix side effects.** Previously accepted direct plans become refusals; plan/intent/ledger/replay identities and caches change, requiring invalidation of affected decisions. No retraining unless data availability changes model training.

**Acceptance tests.** Every critical carrier, absent/None, NaN, Inf, wrong type, and boundary must refuse before veto evaluation; valid native input must preserve the exact 14-order and sizing result.

## D-027 — caller-controlled governed thresholds

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** `adjudicate` accepts daily-loss, consecutive-loss, and margin action thresholds from the risk input, allowing the caller to soften governed vetoes; the native producer does not currently emit the override keys.

**Independent evidence and result.** **CONFIRMED, S1.** Real direct calls changed daily 0.05 from REJECT to ALLOW with cap 0.9, five losses from REJECT to ALLOW with halt 99, and margin 0.2 from veto 14 to ALLOW with action threshold 0.01 on the non-PAPER-proxy path. No live/native bypass was claimed.

**Contract/decision precedence.** Owner > Risk and the governed threshold rule (`APEX_GEN5.md:16755–16757`, `16845–16849`) mean a caller cannot self-authorize a relaxation. D8 keeps risk defaults authoritative; any approved change must be versioned.

**Known owner item.** None directly; this is a kernel authority seam.

**Frozen status and alternatives.** Bind thresholds to the governed parameter loader in non-frozen kernel/config code; alternative is a signed owner-approved parameter object with provenance and monotonic-tightening checks. Do not change the six frozen YAMLs or lock.

**Fix side effects.** Threshold/package changes invalidate parameter package, snapshot, decision, risk, and replay hashes; existing accepted plans need review. Retraining is not required unless threshold labels are part of training.

**Acceptance tests.** Same violation with untrusted override must remain REJECT; only a valid versioned/owner-approved package may change it, with provenance, range, identity, restart, and replay tests.

## D-028 — READY while L3 is active

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** Boot reads and passes an active `HighRisk/L3_CANCEL_ALL` ladder revision and returns READY/new-trades-allowed, rather than preserving the emergency restriction; native submit does not re-adjudicate.

**Independent evidence and result.** **CONFIRMED, S1.** Unlike the earlier constrained probe, this probe used the real installed dependency checks, real temporary/in-memory SQLite store and ledger, real ladder migration, two legal revisions (`NORMAL → L3_CANCEL_ALL`), real startup FSM, and an async venue double returning equal empty state. `StartupReconciliation.run` returned `boot_state=READY`, `new_trades_allowed=true`, and ladder check PASS. It did not use a dependency mock. The venue double is not a real exchange, and the probe did not claim a native order.

**Contract/decision precedence.** L3 means CANCEL_ALL and the ratchet is restrictive (`APEX_GEN5.md:300–328`); AI.9 requires reconciliation before resumption. A READY result therefore conflicts with the contract when the ladder remains L3.

**Known owner item.** ISSUE-077.

**Frozen status and alternatives.** Patch boot/readiness/admission in non-frozen FSM/runtime code. Alternative: keep boot degraded/read-only for non-NORMAL ladder and allow only explicit protective management until owner-authenticated recovery writes a valid NORMAL revision.

**Fix side effects.** Readiness, plan admission, UI, ladder state, reconciliation events, identity hashes, and replay outcomes change; invalidate READY health caches and any plans admitted under L3. No retraining or frozen-file change.

**Acceptance tests.** For durable L1–L5 revisions, boot must never allow new entries; it must preserve cancel/close/reduce-only management. Only NORMAL plus all seven recovery checks and durable owner/reconciliation evidence may become READY. Test restart and equal/divergent broker state.

## D-029 — ladder write/read ratchet bypass

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** `ladder_revision` can omit `previous_state`, `append_ladder_revision` does not validate current state/owner, and `EngineContextProducer.ladder_input` reads only the latest two rows, allowing an invalid downgrade to be hidden by a later NORMAL row.

**Independent evidence and result.** **CONFIRMED, S1.** Real SQLite migration/append calls accepted r3 NORMAL with parent r2 but no previous state. The real producer reader rejected after r3 with `CIRCUIT_RESET_UNAVAILABLE`; after another accepted r4 NORMAL parented to r3, the two-row reader returned r4. This is a full real-code probe, not AST extraction.

**Contract/decision precedence.** The ratchet rule `RSK-ERR-506` and owner D29/ladder contract require durable authenticated downgrade evidence; parent linkage alone is not owner review.

**Known owner item.** None specifically mapped.

**Frozen status and alternatives.** Add transactional writer validation/owner attestation and full-history or signed-state validation in non-frozen risk/ops code. Keep frozen engine/data/catalog files unchanged. A conservative alternative is refusal on every downgrade and an explicit recovery command that appends an authenticated review.

**Fix side effects.** Ladder revisions, state hashes, risk veto 4, readiness, package/context fingerprints, replay and caches change; invalid historical revisions require quarantine/migration. No retraining.

**Acceptance tests.** Reject r3 before commit, reject r4 masking it, verify parent/owner/state after restart and concurrent writes, and test all L1–L5 upgrade/downgrade transitions with ledger ownership.

## D-030 — PAPER margin action is not an L3 consumer

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** With real PAPER capital/notional values, the proxy reports Emergency L3 at health below 0.20, but the computed `margin_status` is not consumed by reconciliation/emergency execution, and veto 14 is not cancel-all.

**Independent evidence and result.** **CONFIRMED, S1.** The real YAML loaded `capital_usdt=10000.0` and strict PAPER fractions warning 0.60/action 0.40/liquidation 0.20. With open notional 8,100, `(10,000−8,100)/10,000=0.19`; real `margin_health_state(..., environment="PAPER")` returned `EMERGENCY_L3_CANCEL_ALL`, while real proxy `adjudicate` returned only `REJECT` with veto 14. Consumer search/source tracing found no cancel-all call from `margin_status`, no FSM margin query in boot reconciliation, and context computation occurs only along setup/due-cell work. This is not device or simulator evidence.

**Contract/decision precedence.** D29 owner decision (`PHASE2_DECISION_LOG.md:455`) is binding for the formula and strict PAPER boundaries; Ch.15 `APEX_GEN5.md:16859–16863` requires polling every reconciliation cycle and automatic L3 cancel-all. D58’s simulator absence means the durable simulator-side proof is still unavailable.

**Known owner item.** D29 formula; D58 PAPER fill simulator not wired.

**Frozen status and alternatives.** `apex/risk/kernel.py` is not in the explicit frozen-file list, but this read-only verification made no source change; the safest non-frozen fix is an independent reconciliation consumer around the existing proxy that preserves the kernel API. Do not modify frozen engines/catalog/backtest/bootstrap/params/lock. 

**Fix side effects.** L3 state transitions, cancel intents, broker/simulator calls, ledger/reconciliation events, margin/context hashes and restart behavior change; plans/caches computed under critical health become invalid. No retraining unless margin becomes a model feature.

**Acceptance tests.** With no due setup/cell, health below 0.20 must persist L3, cancel all pending orders through a real simulator/venue adapter, verify results and reconcile. Health below 0.40 must independently block new entries; missing marks/order state/C≤0/out-of-range must fail closed.

## D-031 — CVaR helper not connected to runtime risk

### Auditor claim

### What I read

### Reproduction

### Verdict and reasoning

### Root cause

### Direct impact

### Secondary effects and interactions

### Contract and decisions

### Frozen status and non-frozen alternative

### Fix options

### My recommendation

### Acceptance and regression tests

**Audit hypothesis (English translation).** Ch.15 requires weekly portfolio CVaR from a 1000-path Monte Carlo for a one-level advisory downgrade, but the runtime risk input does not carry it and execution code never calls the research helper.

**Independent evidence and result.** **CONFIRMED, S2.** The real `cvar_bootstrap` helper produced a result in `apex.research.backtest`; source consumer search found only its definition in `apex/research/backtest.py`, with zero calls in `apex/` or `scripts/`. The registry claiming A10 in `apex.risk.kernel` does not establish a call. This verifies a missing connection only, not CVaR model validity or market behavior.

**Contract/decision precedence.** Ch.15 requires weekly portfolio CVaR using current positions/correlation and an advisory downgrade (`APEX_GEN5.md:16851–16857`), and the symbol symmetry decree requires all ten symbols/hourly 1000-path CVaR (`17710–17712`). The helper’s availability cannot overrule the missing runtime carrier.

**Known owner item.** None specifically mapped; D58 is a separate simulator gap.

**Frozen status and alternatives.** `apex/research/backtest.py` is frozen. Add a non-frozen research-to-runtime projection that computes a PIT portfolio carrier from durable positions/correlation, records window/seed/paths/unit/package, and passes only the advisory fraction into risk. Alternative: explicit fail-closed/no-downgrade status until the carrier is implemented; never silently treat absent CVaR as safe.

**Fix side effects.** Risk ladder state, sizing, plan/snapshot/replay hashes and caches change when CVaR crosses 4%; a new carrier requires provenance and possibly migration. No retraining is required for the connection, but model/research artifacts must be versioned if the estimator changes.

**Acceptance tests.** Use a deterministic weekly 1000-path ten-symbol portfolio fixture with CVaR above 4% and below/equal 4%; assert exactly one advisory downgrade before sizing, hard veto precedence, missing-carrier behavior, PIT cutoff, correlation inputs, seed/path identity, restart and replay determinism.

## New findings not in the audit

1. **D-008 is overclaimed at the stated single-plan numbers.** The audit text says 6,500 exposure passed a 6,000 hard cap. The current real `adjudicate` probe rejected it with veto 3. D-008 remains PARTIAL because multi-cell atomic reservation was not established, but the quoted ALLOW result is rejected as a reproduction.
2. **The requested index comparison found residual scans even after both device indexes.** `idx_mo_sym_tf_open` improves the market-symbol lookup and `idx_pit_scope_asof` improves the prior snapshot query, but the raw join still scans `raw_observation`, the facts query still scans `snapshot_pit` via its primary-key index, and the ledger query scans `ledger`. This is a concrete performance finding beyond the binary “indexes exist” question.
3. **D-022’s pass gate demonstrably ignores RPO.** With a real 25-row temporary SQLite drill and an intentionally failing `rpo_within_limit=false`, the returned `passed` remained true. This makes the omitted RPO operand independently observable without pretending that a negative limit is an operational RPO scenario.
4. **D-028 no longer depends on the earlier dependency mock.** All nine dependency imports passed in the current environment, while the real SQLite/ledger/ladder/boot path still returned READY under L3. This strengthens the readiness defect and removes the earlier probe’s dependency limitation; it still does not establish device/venue behavior.
5. **D-015’s exact score is not stable across fixture construction.** The independent real call emitted at 0.9000000000000002 rather than the prior audit’s approximately 0.732857. The invariant finding is emission under collapsed confidence, not a particular score; numeric score comparisons must bind the complete context fixture and versions.

## Rows not verified or incomplete

| Row(s) | Incomplete boundary | What is still required |
|---|---|---|
| D-001, D-002, D-017, D-020 | No real device, private venue, Telegram, SMTP, or simulator transport was used. | Owner/device run with network-deny/ACK evidence and durable restart/reconcile proof. |
| D-003–D-007 | Runtime behavior was exercised with controlled objects; no long-lived phone process or host-death test. | Target-device kill/hang, drift, storage, watchdog, and management-cycle evidence. |
| D-008 | No multi-cell real simulator/venue race was run; single-plan audit example was not reproduced. | Atomic reservation integration test and device/PAPER proof. |
| D-009–D-016 | Direct real functions and source paths were tested, but no native setup-to-plan-to-venue run was established for each condition. | Full producer/bridge/risk integration with complete PIT evidence. |
| D-021–D-025 | Temporary SQLite proves API behavior, not the owner’s backup scheduler, volume, encryption, key custody, RPO/RTO, or device filesystem. | Real production-volume dry-run, external schedule, off-device encrypted destination, and restore sign-off. |
| D-026–D-027 | Direct kernel inputs proved API permissiveness; native caller provenance/authorization was not tested with a live device. | Typed risk-input integration, owner-approved threshold provenance, and regression/replay evidence. |
| D-028–D-030 | The boot/proxy/ladder probes used real repository code and temporary SQLite but a venue double; no real PAPER simulator exists and no device order/recovery was attempted. | CP-15 simulator plus device-level restart, margin, ladder, cancel-all, and reconciliation evidence. |
| D-031 | No production portfolio CVaR was calculated; the finding is only absent runtime connection. | Governed PIT portfolio carrier, deterministic 1000-path integration, and pre-plan advisory downgrade evidence. |

No row is classified DEVICE-EVIDENCE-NEEDED as its primary classification: each classification above is about a source/API proposition that was independently tested. The table records where device evidence is still required; absence of that evidence was not converted into a product failure claim.

## Final counts

| Classification | Count |
|---|---:|
| CONFIRMED | 30 |
| PARTIAL | 1 (D-008) |
| REJECTED | 0 |
| DEVICE-EVIDENCE-NEEDED | 0 as primary classification |
| **Total mandatory rows** | **31** |

| Independent severity | Count |
|---|---:|
| S0 | 2 (D-001, D-002) |
| S1 | 26 |
| S2 | 3 (D-012, D-014, D-031) |
| S3/S4 | 0 |

Final severity counts are **S0=2, S1=26, S2=3, S3=0, S4=0**; total 31.

Verification verdict: the audit’s central safety concerns are independently supported in source/API behavior, with D-008 narrowed from CONFIRMED to PARTIAL because its stated over-cap ALLOW did not reproduce. No source, configuration, test, documentation, frozen file, lock file, data file, secret, or device state was modified.
