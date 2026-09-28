# V1a independent verification — in progress

ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option
--- | --- | --- | --- | --- | --- | ---
C-002 | CONFIRMED | S0 | S0 | No (factory/adapter/FSM); additive migration needed for fix | = ISSUE-075; = user-provided D58; D1/D2; related ISSUE-077/078 | A: governed simulator factory; never private network transport in PAPER
C-001 | NOT VERIFIED | S3 (index only) | Not assigned | Not assessed | Not assessed | Verify full row
C-003 | NOT VERIFIED | S1 (index only) | Not assigned | Not assessed | Not assessed | Verify and measure
C-004 | NOT VERIFIED | S1 (index only) | Not assigned | Not assessed | Not assessed | Verify and measure
C-005 | NOT VERIFIED | S2 (index only) | Not assigned | Not assessed | Not assessed | Verify full row
C-006 | NOT VERIFIED | S1 (index only) | Not assigned | Not assessed | ISSUE-079/077 comparison outstanding | Verify and measure
C-007 | NOT VERIFIED | S2 (index only) | Not assigned | Not assessed | Not assessed | Verify full row
C-008 | NOT VERIFIED | S1 (index only) | Not assigned | Not assessed | Not assessed | Verify and measure
C-009 | NOT VERIFIED | S1 (index only) | Not assigned | Not assessed | Not assessed | Verify full row
C-010 | NOT VERIFIED | S1 (index only) | Not assigned | Not assessed | Not assessed | Verify and measure
C-011 | NOT VERIFIED | S2 (index only) | Not assigned | Not assessed | Not assessed | Verify full row
C-012 | NOT VERIFIED | S1 (index only) | Not assigned | Not assessed | Not assessed | Verify and measure
C-013 | NOT VERIFIED | S1 (index only) | Not assigned | Not assessed | Not assessed | Verify and measure
C-014 | NOT VERIFIED | S2 (index only) | Not assigned | Not assessed | Not assessed | Verify full row
C-015 | NOT VERIFIED | S2 (index only) | Not assigned | Not assessed | Not assessed | Verify full row
O-006 | NOT VERIFIED | Not extracted | Not assigned | Not assessed | Not assessed | Verify full row
V-003 | NOT VERIFIED | S4 | Not assigned | Not assessed | Not assessed | Verify full row

**Current status: C-002 CONFIRMED/S0; 16 rows remain unverified.** The appended C-002 formal-verdict section supersedes its retained initial evidence section. The full V1a scope is not complete; there is no real-data/device readiness claim.

Source baseline remains `85b2c155d7b054a468379ddfd802eb239d0801f9`. On continuation the sandbox had reconstructed baseline HEAD with the six prior AUDIT files untracked. I fetched this session's branch, staged only those AUDIT files, verified the entire staged tree was identical to remote checkpoint `7affafc5654027fc3a5c1a8bef0e8a9e39beb75f`, then restored this branch pointer with `git reset --soft origin/arena/01a0e911-upstage`. No source/worktree reset occurred, and no other branch was used. Report input was fetched again using the supplied SHA. All following source line numbers refer to the unchanged baseline.

Only AUDIT files are changed. Original provenance is retained in `probes_V1a/provenance.out`; continuation commands/results are recorded in the formal section. The initial section describes the earlier run, not the present coverage. No real credentials, `.env`, repository `data/`, exchange/Telegram calls or actual orders are used. Synthetic SQLite writes are restricted to in-memory/temp stores. Application network guards are distinct from permitted GitHub fetch/push.

## C-002 — initial partial evidence (historical; superseded below)

### Auditor claim (short quote)

“آداپتر مسیر boot/serve بدون session و transport ساخته می‌شود.” Translation: the boot/serve adapter is constructed without a session or transport. The full row additionally claims an offline real-adapter `UNKNOWN / TRANSPORT_SESSION_MISSING` reproduction, inability to reconcile, and recommends an environment-specific factory rather than attaching venue transport to PAPER. Auditor severity: S0. Full original row: `probes_V1a/provenance.out` (report line 139).

### What I read (files, line ranges, functions, callers)

The following ranges were actually inspected; **this is not the mandated complete-file/dependency-closure reading**:

- `scripts/run_apex.py`: opening documentation/imports and runtime factory through line 188; complete `_boot` (195–236), `_grid` (243–269), complete `_serve` (695–812), main/dispatch tail as displayed by an initially truncated whole-file read. Other excerpts were displayed, but no completeness is claimed for the file (1,172 lines).
- `Runtime.adapter` (183–188): credentials/allow flag gate, then `ToobitAdapter(config=self.cfg)`. `Runtime.start/stop` (156–181): repository SQLite store, ledger initialization/writer, event bus and cleanup.
- `apex/execution/fsm.py`: `StartupReconciliation` 964–1349 inspected, including `run`, all boot self-test checks, `reconcile_boot` and recovery helpers through `_ai9_fsm_state`; the final ladder-availability portion and the rest of the file remain unread.
- `apex/execution/toobit_adapter.py`: opening records/documentation; transport and constructor/credential paths 276–399; query-order/query-position paths 514–559; `_execute` 624–735. Whole class, submit/cancel/helper closure remain incomplete. The relevant path uses the real class, not AST extraction.
- `apex/ops/paper_loop.py`: exception definitions 90–100, `PaperRuntime` construction 352–409, boot/initial ladder 412–452, trading-enabled property, ingest excerpt, risk/decision/execution 598–645, `_state` 687–689. The remainder was not completely read.
- `apex/config.py`: configuration definition/accessors/validation through 207, including the environment loader. Reading the loader source did not execute it or read `.env`. Parser tail appeared in a truncated output; no complete-file claim.
- `apex/ledger/store.py`: `initialize`/`applied_migrations` 256–284 and `read_ledger`, lookup helpers, `trade_plans`, `positions_from_ledger` 492–571. `apex/data_catalog/store/sqlite_store.py`: lifecycle/migration opening 337–375. Other DDL text was executed by the actual store initialization, not fully read.
- `APEX_GEN5.md` 17020–17062, 18424–18435, 18898–18912; `PHASE2_DECISION_LOG.md` 1156–1177; `PHASE2_HANDOFF_CP9.md` 627–636.
- Consumer search was performed with `grep -rn` across scripts/apex/tests; raw matches are in `probes_V1a/C-002-consumers.out`. It identifies `_boot`, `_demo`, `PaperRuntime.boot`, FSM tests and both integration suites. Search matches are **not** a claim that their functions/tests were read completely.

The traceability matrix, checkpoint status, other handoffs, mandatory full files and three mandatory test files remain unreviewed. Some initial tool output was truncated; unseen portions are explicitly not counted as read.

### Reproduction (command, probe file, actual result)

Command from repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V1a/C-002.py
```

Probe: `AUDIT/probes_V1a/C-002.py`; unedited stdout/stderr: `AUDIT/probes_V1a/C-002.out`. Exit status 0. It imports actual repository code, uses `Runtime.start()` and repository migrations in two in-memory SQLite stores, obtains the adapter from the unmodified `Runtime.adapter()`, invokes real `PaperRuntime.boot()` and the real execution-stage readiness guard. No submit/cancel operation is invoked. The dummy `plan_obj` is a sentinel used solely to reach the readiness guard, not a valid trade plan or end-to-end decision.

Observed matrix:

| Synthetic credentials | Injected drift | Adapter / reconciliation | Boot | Execution guard |
| --- | --- | --- | --- | --- |
| Absent | None | None; reconciliation not entered | DEGRADED | BOOT_NOT_READY |
| Absent | 0.0 | ADAPTER_UNAVAILABLE | DEGRADED | BOOT_NOT_READY |
| Present | None | ToobitAdapter; reconciliation not entered | DEGRADED | BOOT_NOT_READY |
| Present | 0.0 | EXCHANGE_UNKNOWN | RECOVERY_REQUIRED | BOOT_NOT_READY |

A direct real-adapter position query returned `ok=false`, `outcome=UNKNOWN`, `error=TRANSPORT_SESSION_MISSING`, one attempt. Self-test dependency/schema/ladder checks passed in this synthetic setup. The probe's later zero-drift call shares the same per-credential in-memory database with the earlier None-drift call; its ladder has consequently already been initialized by `PaperRuntime.boot`. This is not four independent fresh-device boots.

EXPLAIN against the actual initialized DDL was run for the exact `read_ledger` SELECT, before and after creating both supplied device indexes. Both returned `SCAN ledger`; those indexes target market/PIT tables, not ledger. This is **limited planner evidence**, not a measured regression or completed performance finding. The boot query is once per reconciliation here, not a per-cell timing benchmark. The mandated broader per-row/cell/bar query review remains incomplete.

### Verdict and reasoning

**No formal verdict yet: mandatory reading and verification are incomplete.** The narrow missing-session claim is independently reproduced. A wired factory adapter with valid-shaped synthetic credentials cannot reconcile in this probe even when drift is explicitly zero. This is a sufficient **code-path cause** of the ISSUE-075 readiness symptom, not proof that it is the sole cause of the owner's observed device run.

More precisely, absent credentials select no adapter and the CLI chooses `_no_venue_time`; unknown drift already degrades SELF_TEST before reconciliation. With credentials, the CLI selects the public server-time function; if drift is acceptable, the sessionless private adapter causes EXCHANGE_UNKNOWN/RECOVERY_REQUIRED. Other failures can produce the same readiness symptom. The probe injected drift instead of exercising a server-time call. No device cause attribution is asserted.

The observed behavior is consistent with an S0 basic-PAPER-operation blocker, but final independent severity is withheld until the required review is complete. The fail-closed denial itself is a safety control, not a reason to remove reconciliation.

### Root cause

In the inspected path the composition root constructs `ToobitAdapter(config=...)` without either supported transport dependency. Constructor defaults select `aiohttp_transport(None)`. Its closure raises `TRANSPORT_SESSION_MISSING` before `session.request`; `_execute` records UNKNOWN, and `reconcile_boot` returns EXCHANGE_UNKNOWN. There is no PAPER simulator selection in this factory. Separately, `_credentials_present` and the CLI time-source selection couple PAPER readiness to venue credentials and venue time.

### Direct impact

The reproduced boot states all have `new_trades_allowed=False`. `_stage_execution` raises BOOT_NOT_READY before checking the plan decision, price, reservation budget or execution call. This is not proof every real cell reaches that stage: upstream ingest/context/risk may refuse first. No account damage, missing fill, or actual order is claimed.

### Secondary effects and interactions (upstream/downstream)

- Upstream: `_serve` has an allow-signed gate and LIVE capital gate, then constructs runtime/store/service, notifier/control/watchdog, producer/bridge and driver. The actual notification/bootstrap initialization subgraphs are not fully audited. They were not executed by the probe.
- Boot: `_serve` obtains drift then calls `driver.boot`; `PaperRuntime.boot` runs the FSM then loads its cursor and ensures initial ladder. `Runtime.start` already calls `LedgerWriter.initialize`, which invokes the ladder migration. The probe cannot establish the device-specific ISSUE-077 lock/migration failure, and it would be wrong to infer from `PaperRuntime.boot` ordering alone that the composition root always lacks ladder migrations.
- Downstream: `_serve` continues into `driver.run` even when boot is not READY. The readiness gate refuses new execution. Full cycle persistence, gather behavior, protective-order handling and replay were not traced here.
- ISSUE-078 remains an independent time-measurement concern; response-latency drift was not measured. ISSUE-079, C-006 and gather-delayed cell persistence were not investigated.
- The existing signed-request code is reached before the missing transport raises. Merely attaching an aiohttp session to PAPER is not acceptable under the simulator contract. No packet was sent in the probe.
- Runtime identity/hash/cache, training and replay consequences of a simulator implementation remain unverified. Nothing in this reproduction changes the D30 20-base-cell training scope into the 140-cell data scope.

### Contract and decisions

Actual baseline line numbers differ from stale line labels embedded in code comments. Governing excerpts read at this commit:

- `APEX_GEN5.md:17020–17032`: “in PAPER the venue wire above is replaced by the **PAPER simulator**”; “no network packet and no signature”; “Constructing a signed packet in PAPER is a defect”.
- `APEX_GEN5.md:17045–17047`: simulator query operations answer from durable state, “so `reconcile_boot` reaches READY without any network”. Lines 17059–17062 require `paper_sim_state` in the same SQLite file and preserve LIVE signed transport.
- `APEX_GEN5.md:18424–18435`: startup sequence and “No new trade may be created before READY”. The PAPER-specific simulator rule qualifies the generic exchange-query prose; it does not waive reconciliation.
- `APEX_GEN5.md:18905–18907`: UTC/NTP synchronization and “if drift > 500 ms, E12 status = DEGRADED and trading pauses”. This does not by itself specify a complete new offline PAPER clock-source implementation; owner policy must be made explicit rather than setting unmeasured drift to zero.
- `PHASE2_HANDOFF_CP9.md:633`: “This checkpoint does not build the CP-15 simulator/table/transport/replay CLI.” This supports known scheduled work, not acceptance of current PAPER operation.
- `PHASE2_DECISION_LOG.md:1163` D52 A3: initial NoRisk/NORMAL revision follows the ladder migration. Later owner decisions override conflicting older prose; no contrary permission to sign PAPER requests was found in the limited ranges read.

**Cross-reference naming caveat, not a new adjudicated finding:** the user labels the missing simulator “D58”; baseline `PHASE2_DECISION_LOG.md:1175` instead says “D58 — the calibrated walk-forward package and `composite_estimate` wiring.” This report uses “user-provided D58” specifically for the supplied known-item cross-reference, without misquoting the repository's D58 as a simulator decision. Simulator authority is the cited normative contract/handoff. Reconcile naming with the owner before updating any decision record. No decision file was changed.

### Frozen status and non-frozen alternative

The immediate factory/adapter/FSM/paper-loop files are not in the supplied frozen set. The SQLite catalog DDL and frozen backtest cost model are frozen. A future additive simulator migration and environment-specific execution adapter outside `apex/data_catalog/**` can avoid editing frozen DDL; reuse governed cost values without altering the frozen backtest. Exact interfaces/migration compatibility have not been designed or validated here. No frozen edit is recommended or made.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

Provisional design choices only; comprehensive fix-side-effect analysis is outstanding.

- **A — implement the governed durable PAPER adapter/factory and separately own LIVE session lifecycle.** PAPER must bypass signed-packet construction, not merely replace the final transport after signing. Retain reconcile-first and explicit clock readiness. Requires an additive simulator-state migration, restart/reconciliation tests, cost/exit/accounting parity tests, and defined order/position serialization. Tests relying on PAPER's current missing-credential/missing-session behavior would need separation from production PAPER expectations; exact failing tests have not been enumerated. Simulator identities, ledger compatibility and cache implications require review; no claim of zero invalidation or retraining is made.
- **B — explicitly retain fail-closed unavailability until CP-15 and improve operational diagnostics in non-frozen entry-point code.** Does not make PAPER operational; no simulator DB migration is implied. CLI output snapshots/exit expectations may change. No model retraining is implied by diagnostics alone, but no regression suite has been run.
- **Rejected shortcut — supply a real venue session to the current PAPER adapter.** It would allow the already-built signed query to leave the process and violate the cited PAPER transport contract. Do not weaken readiness or assume zero drift to mask the failure. LIVE session ownership is a separate review, not a tested fix here.

### My recommendation

Treat the reproduced mechanism as additional evidence attached to **ISSUE-075 / user-provided D58**, not a new independent issue count. Finish the mandatory C-002 review before giving a formal verdict. Keep PAPER fail-closed pending the governed simulator; do not attach private venue transport as a quick repair. Preserve explicit diagnostics distinguishing clock UNAVAILABLE from adapter UNKNOWN and self-test failure. No production patch is authorized by this checkpoint.

### Acceptance and regression tests

Completed: only the saved offline probe's assertions, including native boot/admission refusal and both index configurations for one ledger query.

Outstanding: complete all required source/caller/callee and contract/decision reading; inspect/run the relevant existing integration and unit tests with `python3 -m pytest -q -p no:cacheprovider <path>` under guards that prevent real endpoints, secrets and `data/` access. The specifically requested `tests/integration/test_ops_paper_loop.py`, `tests/integration/test_cp7_paper_loop.py` and `tests/unit/test_ops_bootstrap_service.py` have not been run or fully read.

For a future fix: production-composition PAPER boot without venue credentials; no signature or packet for any of the five operations; durable restart with fills/working orders and ledger comparison; discrepancy remains fail-closed; unknown/out-of-tolerance clock remains fail-closed; LIVE session lifecycle via a local test transport only; initial and migrated ladder state; cancellation and exception cleanup. Native fixture success must not be represented as real-data/model/device acceptance.

Device attribution would require sanitized **already-existing** boot checks/reconciliation output from the affected invocation; do not rerun the current boot/serve CLI against an exchange to diagnose it. No known device log path was supplied, so no speculative read command is offered. The present incompleteness is verifier work outstanding, not a DEVICE-EVIDENCE-NEEDED verdict.

## C-001 — not verified

### Auditor claim (short quote)

No claim accepted; full-row verification not performed.

### What I read (files, line ranges, functions, callers)

No complete per-row reading recorded. Any shared C-002 excerpts do not establish this row.

### Reproduction (command, probe file, actual result)

Not performed; no probe or pytest result for this ID.

### Verdict and reasoning

NOT VERIFIED. No verdict or independent severity assigned.

### Root cause

Not established.

### Direct impact

Not independently established.

### Secondary effects and interactions (upstream/downstream)

Not traced for this row.

### Contract and decisions

Governing clauses and decision precedence not established for this row.

### Frozen status and non-frozen alternative

Not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

No independently supported fix options or side-effect assessment.

### My recommendation

Complete mandatory verification before accepting or rejecting the claim.

### Acceptance and regression tests

Not defined or run for this row; required performance probes, where applicable, remain outstanding.

## C-003 — not verified

### Auditor claim (short quote)

No claim accepted; full-row verification not performed.

### What I read (files, line ranges, functions, callers)

No complete per-row reading recorded. Any shared C-002 excerpts do not establish this row.

### Reproduction (command, probe file, actual result)

Not performed; no probe or pytest result for this ID.

### Verdict and reasoning

NOT VERIFIED. No verdict or independent severity assigned.

### Root cause

Not established.

### Direct impact

Not independently established.

### Secondary effects and interactions (upstream/downstream)

Not traced for this row.

### Contract and decisions

Governing clauses and decision precedence not established for this row.

### Frozen status and non-frozen alternative

Not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

No independently supported fix options or side-effect assessment.

### My recommendation

Complete mandatory verification before accepting or rejecting the claim.

### Acceptance and regression tests

Not defined or run for this row; required performance probes, where applicable, remain outstanding.

## C-004 — not verified

### Auditor claim (short quote)

No claim accepted; full-row verification not performed.

### What I read (files, line ranges, functions, callers)

No complete per-row reading recorded. Any shared C-002 excerpts do not establish this row.

### Reproduction (command, probe file, actual result)

Not performed; no probe or pytest result for this ID.

### Verdict and reasoning

NOT VERIFIED. No verdict or independent severity assigned.

### Root cause

Not established.

### Direct impact

Not independently established.

### Secondary effects and interactions (upstream/downstream)

Not traced for this row.

### Contract and decisions

Governing clauses and decision precedence not established for this row.

### Frozen status and non-frozen alternative

Not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

No independently supported fix options or side-effect assessment.

### My recommendation

Complete mandatory verification before accepting or rejecting the claim.

### Acceptance and regression tests

Not defined or run for this row; required performance probes, where applicable, remain outstanding.

## C-005 — not verified

### Auditor claim (short quote)

No claim accepted; full-row verification not performed.

### What I read (files, line ranges, functions, callers)

No complete per-row reading recorded. Any shared C-002 excerpts do not establish this row.

### Reproduction (command, probe file, actual result)

Not performed; no probe or pytest result for this ID.

### Verdict and reasoning

NOT VERIFIED. No verdict or independent severity assigned.

### Root cause

Not established.

### Direct impact

Not independently established.

### Secondary effects and interactions (upstream/downstream)

Not traced for this row.

### Contract and decisions

Governing clauses and decision precedence not established for this row.

### Frozen status and non-frozen alternative

Not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

No independently supported fix options or side-effect assessment.

### My recommendation

Complete mandatory verification before accepting or rejecting the claim.

### Acceptance and regression tests

Not defined or run for this row; required performance probes, where applicable, remain outstanding.

## C-006 — not verified

### Auditor claim (short quote)

No claim accepted; full-row verification not performed.

### What I read (files, line ranges, functions, callers)

No complete per-row reading recorded. Any shared C-002 excerpts do not establish this row.

### Reproduction (command, probe file, actual result)

Not performed; no probe or pytest result for this ID.

### Verdict and reasoning

NOT VERIFIED. No verdict or independent severity assigned.

### Root cause

Not established.

### Direct impact

Not independently established.

### Secondary effects and interactions (upstream/downstream)

Not traced for this row.

### Contract and decisions

Governing clauses and decision precedence not established for this row.

### Frozen status and non-frozen alternative

Not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

No independently supported fix options or side-effect assessment.

### My recommendation

Complete mandatory verification before accepting or rejecting the claim.

### Acceptance and regression tests

Not defined or run for this row; required performance probes, where applicable, remain outstanding.

## C-007 — not verified

### Auditor claim (short quote)

No claim accepted; full-row verification not performed.

### What I read (files, line ranges, functions, callers)

No complete per-row reading recorded. Any shared C-002 excerpts do not establish this row.

### Reproduction (command, probe file, actual result)

Not performed; no probe or pytest result for this ID.

### Verdict and reasoning

NOT VERIFIED. No verdict or independent severity assigned.

### Root cause

Not established.

### Direct impact

Not independently established.

### Secondary effects and interactions (upstream/downstream)

Not traced for this row.

### Contract and decisions

Governing clauses and decision precedence not established for this row.

### Frozen status and non-frozen alternative

Not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

No independently supported fix options or side-effect assessment.

### My recommendation

Complete mandatory verification before accepting or rejecting the claim.

### Acceptance and regression tests

Not defined or run for this row; required performance probes, where applicable, remain outstanding.

## C-008 — not verified

### Auditor claim (short quote)

No claim accepted; full-row verification not performed.

### What I read (files, line ranges, functions, callers)

No complete per-row reading recorded. Any shared C-002 excerpts do not establish this row.

### Reproduction (command, probe file, actual result)

Not performed; no probe or pytest result for this ID.

### Verdict and reasoning

NOT VERIFIED. No verdict or independent severity assigned.

### Root cause

Not established.

### Direct impact

Not independently established.

### Secondary effects and interactions (upstream/downstream)

Not traced for this row.

### Contract and decisions

Governing clauses and decision precedence not established for this row.

### Frozen status and non-frozen alternative

Not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

No independently supported fix options or side-effect assessment.

### My recommendation

Complete mandatory verification before accepting or rejecting the claim.

### Acceptance and regression tests

Not defined or run for this row; required performance probes, where applicable, remain outstanding.

## C-009 — not verified

### Auditor claim (short quote)

No claim accepted; full-row verification not performed.

### What I read (files, line ranges, functions, callers)

No complete per-row reading recorded. Any shared C-002 excerpts do not establish this row.

### Reproduction (command, probe file, actual result)

Not performed; no probe or pytest result for this ID.

### Verdict and reasoning

NOT VERIFIED. No verdict or independent severity assigned.

### Root cause

Not established.

### Direct impact

Not independently established.

### Secondary effects and interactions (upstream/downstream)

Not traced for this row.

### Contract and decisions

Governing clauses and decision precedence not established for this row.

### Frozen status and non-frozen alternative

Not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

No independently supported fix options or side-effect assessment.

### My recommendation

Complete mandatory verification before accepting or rejecting the claim.

### Acceptance and regression tests

Not defined or run for this row; required performance probes, where applicable, remain outstanding.

## C-010 — not verified

### Auditor claim (short quote)

No claim accepted; full-row verification not performed.

### What I read (files, line ranges, functions, callers)

No complete per-row reading recorded. Any shared C-002 excerpts do not establish this row.

### Reproduction (command, probe file, actual result)

Not performed; no probe or pytest result for this ID.

### Verdict and reasoning

NOT VERIFIED. No verdict or independent severity assigned.

### Root cause

Not established.

### Direct impact

Not independently established.

### Secondary effects and interactions (upstream/downstream)

Not traced for this row.

### Contract and decisions

Governing clauses and decision precedence not established for this row.

### Frozen status and non-frozen alternative

Not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

No independently supported fix options or side-effect assessment.

### My recommendation

Complete mandatory verification before accepting or rejecting the claim.

### Acceptance and regression tests

Not defined or run for this row; required performance probes, where applicable, remain outstanding.

## C-011 — not verified

### Auditor claim (short quote)

No claim accepted; full-row verification not performed.

### What I read (files, line ranges, functions, callers)

No complete per-row reading recorded. Any shared C-002 excerpts do not establish this row.

### Reproduction (command, probe file, actual result)

Not performed; no probe or pytest result for this ID.

### Verdict and reasoning

NOT VERIFIED. No verdict or independent severity assigned.

### Root cause

Not established.

### Direct impact

Not independently established.

### Secondary effects and interactions (upstream/downstream)

Not traced for this row.

### Contract and decisions

Governing clauses and decision precedence not established for this row.

### Frozen status and non-frozen alternative

Not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

No independently supported fix options or side-effect assessment.

### My recommendation

Complete mandatory verification before accepting or rejecting the claim.

### Acceptance and regression tests

Not defined or run for this row; required performance probes, where applicable, remain outstanding.

## C-012 — not verified

### Auditor claim (short quote)

No claim accepted; full-row verification not performed.

### What I read (files, line ranges, functions, callers)

No complete per-row reading recorded. Any shared C-002 excerpts do not establish this row.

### Reproduction (command, probe file, actual result)

Not performed; no probe or pytest result for this ID.

### Verdict and reasoning

NOT VERIFIED. No verdict or independent severity assigned.

### Root cause

Not established.

### Direct impact

Not independently established.

### Secondary effects and interactions (upstream/downstream)

Not traced for this row.

### Contract and decisions

Governing clauses and decision precedence not established for this row.

### Frozen status and non-frozen alternative

Not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

No independently supported fix options or side-effect assessment.

### My recommendation

Complete mandatory verification before accepting or rejecting the claim.

### Acceptance and regression tests

Not defined or run for this row; required performance probes, where applicable, remain outstanding.

## C-013 — not verified

### Auditor claim (short quote)

No claim accepted; full-row verification not performed.

### What I read (files, line ranges, functions, callers)

No complete per-row reading recorded. Any shared C-002 excerpts do not establish this row.

### Reproduction (command, probe file, actual result)

Not performed; no probe or pytest result for this ID.

### Verdict and reasoning

NOT VERIFIED. No verdict or independent severity assigned.

### Root cause

Not established.

### Direct impact

Not independently established.

### Secondary effects and interactions (upstream/downstream)

Not traced for this row.

### Contract and decisions

Governing clauses and decision precedence not established for this row.

### Frozen status and non-frozen alternative

Not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

No independently supported fix options or side-effect assessment.

### My recommendation

Complete mandatory verification before accepting or rejecting the claim.

### Acceptance and regression tests

Not defined or run for this row; required performance probes, where applicable, remain outstanding.

## C-014 — not verified

### Auditor claim (short quote)

No claim accepted; full-row verification not performed.

### What I read (files, line ranges, functions, callers)

No complete per-row reading recorded. Any shared C-002 excerpts do not establish this row.

### Reproduction (command, probe file, actual result)

Not performed; no probe or pytest result for this ID.

### Verdict and reasoning

NOT VERIFIED. No verdict or independent severity assigned.

### Root cause

Not established.

### Direct impact

Not independently established.

### Secondary effects and interactions (upstream/downstream)

Not traced for this row.

### Contract and decisions

Governing clauses and decision precedence not established for this row.

### Frozen status and non-frozen alternative

Not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

No independently supported fix options or side-effect assessment.

### My recommendation

Complete mandatory verification before accepting or rejecting the claim.

### Acceptance and regression tests

Not defined or run for this row; required performance probes, where applicable, remain outstanding.

## C-015 — not verified

### Auditor claim (short quote)

No claim accepted; full-row verification not performed.

### What I read (files, line ranges, functions, callers)

No complete per-row reading recorded. Any shared C-002 excerpts do not establish this row.

### Reproduction (command, probe file, actual result)

Not performed; no probe or pytest result for this ID.

### Verdict and reasoning

NOT VERIFIED. No verdict or independent severity assigned.

### Root cause

Not established.

### Direct impact

Not independently established.

### Secondary effects and interactions (upstream/downstream)

Not traced for this row.

### Contract and decisions

Governing clauses and decision precedence not established for this row.

### Frozen status and non-frozen alternative

Not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

No independently supported fix options or side-effect assessment.

### My recommendation

Complete mandatory verification before accepting or rejecting the claim.

### Acceptance and regression tests

Not defined or run for this row; required performance probes, where applicable, remain outstanding.

## O-006 — not verified

### Auditor claim (short quote)

No claim accepted; full-row verification not performed.

### What I read (files, line ranges, functions, callers)

No complete per-row reading recorded. Any shared C-002 excerpts do not establish this row.

### Reproduction (command, probe file, actual result)

Not performed; no probe or pytest result for this ID.

### Verdict and reasoning

NOT VERIFIED. No verdict or independent severity assigned.

### Root cause

Not established.

### Direct impact

Not independently established.

### Secondary effects and interactions (upstream/downstream)

Not traced for this row.

### Contract and decisions

Governing clauses and decision precedence not established for this row.

### Frozen status and non-frozen alternative

Not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

No independently supported fix options or side-effect assessment.

### My recommendation

Complete mandatory verification before accepting or rejecting the claim.

### Acceptance and regression tests

Not defined or run for this row; required performance probes, where applicable, remain outstanding.

## V-003 — not verified

### Auditor claim (short quote)

No claim accepted; full-row verification not performed.

### What I read (files, line ranges, functions, callers)

No complete per-row reading recorded. Any shared C-002 excerpts do not establish this row.

### Reproduction (command, probe file, actual result)

Not performed; no probe or pytest result for this ID.

### Verdict and reasoning

NOT VERIFIED. No verdict or independent severity assigned.

### Root cause

Not established.

### Direct impact

Not independently established.

### Secondary effects and interactions (upstream/downstream)

Not traced for this row.

### Contract and decisions

Governing clauses and decision precedence not established for this row.

### Frozen status and non-frozen alternative

Not assessed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

No independently supported fix options or side-effect assessment.

### My recommendation

Complete mandatory verification before accepting or rejecting the claim.

### Acceptance and regression tests

Not defined or run for this row; required performance probes, where applicable, remain outstanding.

## C-002 — formal verdict (continuation)

### Auditor claim (short quote)

“آداپتر مسیر boot/serve بدون session و transport ساخته می‌شود.” The production boot/serve adapter is built without session/transport, cannot reconcile, and blocks PAPER readiness. Full row re-read from `/tmp/AUDIT.md` at report line 139, with its original text retained in `probes_V1a/provenance.out`. Auditor S0.

### What I read (files, line ranges, functions, callers)

Completed the previously missing reads rather than inferring from names:

- `scripts/run_apex.py:1–1172`, entire file across this and the initial pass: factory 121–188; complete boot 195–236; demo alternative 274–401; notifier 466–475; full serve 695–812 including initialization, drift choice, boot, artifact diagnostic, run and cleanup; control-handler helpers 815–855; complete main/COMMANDS 1056–1172. Demo supplies a transport explicitly; production boot and serve do not.
- `apex/execution/toobit_adapter.py:1–905`, entire file across both passes: five operations, token bucket, transport, credential checks, request execution/classification, dedup/refusal/interval helpers and result records. No lazy session factory or later session assignment rescues `aiohttp_transport(None)`.
- `apex/execution/fsm.py:964–1336`, complete `StartupReconciliation`, including recovery helpers and ladder availability, plus `CheckResult` 955–961, boot matrix 175–195 and `_rows_of` 1339–1349. This is a full read of the requested startup class, not a claim that unrelated order-FSM logic has been fully verified.
- Query-path callees: `toobit_map.py` endpoint/path selection 200–247, complete response classification 320–410, signing/query/idempotency functions 514–574; adapter-local helpers through 905. `clock.py` SystemClock 136–149 and complete drift functions 260–308. No equation was reconstructed from AST.
- Direct runtime caller/consumer functions: `paper_loop.py` constructor 352–409, boot and initial ladder 412–452, trading-enabled property, execution stage 620–645, `_state` 687–689, cursor migration/load 218–254 and 951–954, full `run_cycle` 956–1067, and `run`/pause/stop 1103–1143. Reading the full cycle establishes it runs despite non-READY boot; preparation can refuse earlier than BOOT_NOT_READY. Other paper-loop functions/global mandatory files will be completed with their assigned rows.
- Initialization and shutdown callees: SQLite DDL/migration/lifecycle 1–383; ledger DDL/records/lifecycle 1–327, writer/append 329–422, correction/read/position projection 480–571, verify-chain/head 645–679 and row helpers 704–754; risk ladder migration/revision functions 652–799; BootstrapService constructor/open/source-laziness/close 1112–1203; ResearchCheckpointStore constructor/open/close 106–150; EventBus 1–255; control-plane constructor/register 450–490; Watchdog constructor 335–365 and RecoveryLog constructor 173–182; EngineContextProducer constructor 1759–1773; PaperPlanBridge constructor 512–528; paper_balance 642–665. Optional Telegram handlers were inspected in the composition root, not exercised or accepted as operational.
- Existing boot/recovery test classes read in full: `tests/unit/test_execution_fsm.py:1210–1455`, plus their store/env fixtures and harness 1–77, 113–215. Read the integration BOOT_NOT_READY regression `tests/integration/test_ops_paper_loop.py:618–633`. The full three globally requested test files are not claimed completed by this row.
- Governing source: contract 17020–17062, 18424–18435, 18905–18907; decision log D1–D20 and Session-A reconciliation of signed-flag wording, 193–241; D52/D58 1163/1175; handoff CP9 627–636; traceability P3/P4 518–519; checkpoint status CP7 boot evidence at 73. Historical PASS claims were read as claims, not reused as proof.

Mandatory `grep -rn` consumers search was repeated; results: `C-002-consumers-continuation.out`. It includes both production factory call sites, fixture/demo callers, startup-class consumers and transport callers. The verdict concerns the production dependency omission, not certification of every unrelated method in those modules.

### Reproduction (command, probe file, actual result)

All commands below ran from repository root. Dependency installation with the requested lockfile and pytest exited 0 (`dependencies-continuation.out`, empty quiet-pip output).

```sh
PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V1a/C-002.py
PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V1a/C-002-root.py
env -i PATH=/usr/local/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 APEX_DOTENV_PATH='' PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/home/user/Upstage/AUDIT/probes_V1a/guard MPLCONFIGDIR=/tmp/v1a-mpl python3 -m pytest -q -p no:cacheprovider tests/unit/test_execution_fsm.py::TestBootMachine tests/unit/test_execution_fsm.py::TestRecoveryReconciliation
```

Raw outputs, respectively: `C-002-repeat.out`, `C-002-root.out`, `C-002-pytest.out`. All exit 0. Existing tests: **18 passed, 13 warnings in 3.55s**, guard `blocked_attempts=[]`.

New probe invokes the **actual `_boot` and `_serve(cycles=0)`**, with the actual Runtime factory, store, migrations, FSM, boot checks, driver and cleanup. Only public time is substituted with a local fixture and the optional classifier diagnostic deliberately returns `AUDIT_MODEL_NOT_LOADED`; it does not read a model. Submit/cancel are trapped as forbidden. No factory/adapter injection occurs in the principal experiment. Separate fresh in-memory stores are used by each invocation:

| Configuration | Actual `_boot` | Actual zero-cycle `_serve` |
| --- | --- | --- |
| PAPER, allow flag 1, no credentials | DEGRADED / exit 2; clock UNAVAILABLE | DEGRADED / exit 2 |
| PAPER, allow flag 1, synthetic credentials, locally synchronized time | RECOVERY_REQUIRED / exit 3; EXCHANGE_UNKNOWN; TRANSPORT_SESSION_MISSING | RECOVERY_REQUIRED / exit 2; same broker check failure |

Counterfactual control changes **only** the adapter transport to an empty local GET responder with no network and observes READY from the same startup FSM/DDL. It records exactly positions/openOrders/userTrades queries. It is a diagnostic test double, **not** a compliant simulator or acceptance evidence for fills/restarts/accounting.

The original native probe also exercises the actual execution-stage guard and observes BOOT_NOT_READY for both failed boot states. It reran successfully under NumPy 1.26.0. Native DDL EXPLAIN, with/without both supplied device indexes, remains `SCAN ledger` for the exact full-ledger projection. Performance observation: reconciliation and PAPER balance construction are linear full-ledger reads; neither market/PIT index addresses them. C-002's query is once per boot, not per bar/cell. No device latency or repeated-cell performance conclusion is inferred from the empty fixture.

### Verdict and reasoning

**CONFIRMED, independent S0 (same as auditor).** The unmodified production factory omits a required dependency, and the real boot/serve composition cannot reach READY in PAPER. A hypothetical successful server-time request does not cure this: with synchronized time, actual reconciliation reaches the sessionless adapter and returns UNKNOWN. When no credentials are present, the CLI instead fails earlier on its credential-coupled time source.

**Is C-002 the root cause of ISSUE-075? Yes, at the production composition/code level:** the missing PAPER execution backend, implemented as an unavailable or sessionless venue adapter plus credential-coupled clock selection, is a sufficient root cause of PAPER BOOT_NOT_READY. The absent-session mechanism is the additional concrete explanation for why supplying credentials/time still cannot make that composition ready. **It is not established as the sole cause of the owner's particular device invocation.** BOOT_NOT_READY is a downstream generic guard and may also reflect independent self-test/clock/DB failures. Fixing the backend cannot by itself certify OI/model/context readiness or a usable plan.

No permission to trade is inferred from the counterfactual READY. S0 here means basic PAPER operation blocked, not a proven loss of funds; retaining fail-closed admission is correct.

### Root cause

`Runtime.adapter()` gates on allow/key/secret but never selects an environment-specific execution backend. It constructs `ToobitAdapter(config=cfg)`. Defaults choose `aiohttp_transport(session=None)`, whose closure raises before `session.request`. `_execute` signs the synthetic query first, catches AdapterError as UNMAPPED, emits UNKNOWN with reconcile-required, and does not retry. `StartupReconciliation` makes all three queries, then detects the UNKNOWN and transitions to RECOVERY_REQUIRED. With no adapter, `_no_venue_time` makes drift unavailable, preventing entry into reconciliation.

### Direct impact

`new_trades_allowed=False`; real execution guard raises BOOT_NOT_READY before price lookup, budget reservation or order execution. `_boot` distinguishes RECOVERY_REQUIRED (3) from DEGRADED (2), while `_serve` returns 2 for either non-READY state after its run ends. The full serve path can still initialize, print the refusal and run market-data/context work; lack of an early loop abort does not authorize an order.

### Secondary effects and interactions (upstream/downstream)

Upstream allow-signed remains necessary under current flag semantics but is never permission to sign PAPER requests. The public-time coroutine creates its own local aiohttp session; it is unrelated to the private adapter's missing session and cannot supply one indirectly. The binding D1 simulator requirement overrides the older generic venue reading.

Downstream decision/risk computation occurs before execution admission; a context/data refusal may mask BOOT_NOT_READY. No new fill/order-ledger transition is made by the reproduced guard, so no execution-derived training/replay history is produced by this attempt. Boot migration/initial ladder writes are separate synthetic state changes, not fills. The fix should leave proposal/intent hash rules and the E11 training protocol untouched; any changed execution outcomes belong in new append-only records, not rewritten historical hashes.

ISSUE-077: actual `Runtime.start -> LedgerWriter.initialize` performs ladder migrations before SELF_TEST; the pure `PaperRuntime.boot` call ordering does not prove the composition root always lacks migrations. Separate device lock/migration faults remain possible. ISSUE-078: measured latency-dependent drift is independent of this session omission. D58/CP-15 is the known missing simulator, not a newly discovered second blocker. Beyond that known item, this row proves the exact missing-session composition mechanism (also present in the shared factory used for LIVE), rather than alleging any new observed LIVE incident.

### Contract and decisions

`APEX_GEN5.md:17020–17032`: PAPER replaces venue transport with the simulator, “no network packet and no signature”; “Constructing a signed packet in PAPER is a defect”. Lines 17044–17047 require queries from durable simulator state so reconciliation reaches READY without network. Lines 17059–17062 require additive `paper_sim_state` and preserve LIVE transport.

`APEX_GEN5.md:18424–18435`: “No new trade may be created before READY”. `18905–18907`: synchronized clock and drift >500 ms pauses trading. No clause permits treating unmeasurable drift as zero; an offline PAPER clock policy needs an explicit trustworthy source, not fabricated synchronization.

**Owner precedence:** `PHASE2_DECISION_LOG.md:193–207`, D1, says “PAPER execution mode = in-process PAPER simulator transport”, “sends NO packet to the venue”, same FSM/ledger path; D2 authorizes the normative clarification. The explicit resolution at 237–241 says the allow flag permits the loop, “it never authorizes a packet.” This later owner-specific instruction wins over older generic exchange-reconcile and signed-order language. The simulator still reconciles real durable simulated state.

`PHASE2_TRACEABILITY_MATRIX.md:518` agrees; `PHASE2_HANDOFF_CP9.md:633` explicitly defers simulator/table/transport/replay implementation to CP-15. CP7 historical fixture PASS at `PHASE2_CHECKPOINT_STATUS.md:73` tests an injected fake responder, not this factory. Baseline decision-log D58 means calibrated walk-forward wiring; **user-provided D58** is retained solely as the user's known-item label for the simulator, with D1/D2 cited as actual repository authority.

### Frozen status and non-frozen alternative

Factory, adapter, startup FSM and ops runtime are outside the supplied frozen set. Frozen store DDL need not be edited: add a non-frozen simulator-owned migration through existing additive bookkeeping, as ladder/cursor code already does. Preserve frozen backtest cost constants and engine/catalog contracts. If a proposed fix changes frozen backtest/catalog/schema text, it needs explicit owner authorization; no such change is necessary for backend injection itself.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

**A — governed environment-specific factory (recommended).** PAPER gets durable simulator operations with signing bypassed entirely; LIVE gets an explicitly owned session/transport and shutdown. Maintain readiness guard and trusted-clock refusal. Additive DB migration is needed for simulator state and restart reconciliation. No E11 retraining or classifier/cache invalidation is inherently required by backend selection: do not modify engine inputs, parameters, existing event identity or hash algorithms. New fills/outcomes necessarily create new ledger/history identities; pre-existing signed/fake PAPER history must be reconciled or refused, never relabelled or rewritten. A future implementation must test compatibility rather than assume existing test-double state can become simulator state.

Regression effects: `TestBootMachine.test_a_boot_without_an_adapter_is_degraded_never_ready` and the unmeasurable-clock tests **must remain passing** for explicitly unavailable dependencies. They should not be weakened to implement credential-free production PAPER boot. The production failure assertions in `C-002-root.py` will intentionally fail after a correct fix and must be replaced by production-PAPER READY/no-signature/no-packet tests. `test_a_degraded_boot_refuses_to_trade` must still refuse explicit failed readiness. LIVE adapter missing-session tests should continue guarding bad construction. Session lifecycle adds cancellation/exception cleanup obligations; simulator persistence adds schema upgrade, reconciliation and cost/exit parity obligations. No hidden risk-threshold or 20-cell/140-cell scope change is justified.

**B — retain safe refusal until CP-15, improve diagnostics only.** No simulator migration, hash/cache invalidation or retraining is required; CLI message assertions may need updates. Basic PAPER remains unavailable, so this is mitigation/deferment, not resolution. Preserve explicit differences between missing backend, unknown clock and DB/self-test failure.

**Not a viable option:** attach a private venue session to the current PAPER adapter, waive reconciliation, or set drift to zero. First violates no-packet/no-signature; latter choices misrepresent readiness. Injecting an empty-success responder is likewise only a test control, not a fix.

### My recommendation

Option A as the known CP-15/ISSUE-075 work, with B only as an honest interim. Do not duplicate the owner's simulator issue; attach the saved factory/root-cause reproduction to it. No source/config/test/document implementation outside AUDIT is changed. Resolving C-002 does not resolve upstream evidence, replay, emergency handling or long-loop performance findings.

### Acceptance and regression tests

Executed: both native probes and 18 existing startup/recovery tests, all successful as **defect reproductions / invariant checks**, not device acceptance. The production-root probe uses zero serve cycles to avoid real market/network work; full long-loop/device acceptance is expressly not claimed.

Fix acceptance: (1) actual production PAPER factory without venue credentials produces no signature/packet across all five operations; (2) durable empty and nonempty simulator restart reconciles correctly, including mismatched state refusal; (3) unknown clock remains blocked; (4) known-good clock plus valid simulator becomes READY and can pass only authorized plans; (5) LIVE session closure on normal/exception/cancellation paths using a local responder, with no order to a venue; (6) existing startup/no-adapter/no-ledger/drift/divergence/ladder tests remain green; (7) simulator fee/slippage/exit/accounting parity and replay identities are tested separately against the governed contract. Run the remaining mandated integration files with isolated temporary databases and network/secret guards during their row reviews. Synthetic PASS cannot establish real market-data, model, device latency or accounting acceptance.

## New findings not in the audit

None established at mandatory depth. No X-V1a IDs assigned. The limited ledger SCAN observation and decision-label caveat above are retained as follow-up notes, not promoted to completed new findings. Full audit duplication checks have not been performed.

## Rows not verified or incomplete

16 IDs remain: **C-001, C-003, C-004, C-005, C-006, C-007, C-008, C-009, C-010, C-011, C-012, C-013, C-014, C-015, O-006, V-003**.

Next required order: C-006, C-003, C-004, C-008, C-010, C-012, C-013, C-001, C-005, C-007, C-009, C-011, C-014, C-015, O-006, V-003. Some shared runtime source has been read for C-002; that is not a verdict on these rows. Their full-row comparisons, mandated complete files/tests, measured reproductions, per-cell/bar SQL EXPLAIN and fix-side-effect analyses remain outstanding. No coverage or readiness sign-off for those rows.

## Final counts

- CONFIRMED: **1** (C-002, S0)
- PARTIAL: **0**
- REJECTED: **0**
- DEVICE-EVIDENCE-NEEDED: **0**
- Unverified: **16**
- Established new findings: **0**
