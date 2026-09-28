# V1a independent verification — in progress

ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option
--- | --- | --- | --- | --- | --- | ---
C-002 | CONFIRMED | S0 | S0 | No (factory/adapter/FSM); additive migration needed for fix | = ISSUE-075; = user-provided D58; D1/D2; related ISSUE-077/078 | A: governed simulator factory; never private network transport in PAPER
C-001 | NOT VERIFIED | S3 (index only) | Not assigned | Not assessed | Not assessed | Verify full row
C-003 | CONFIRMED | S1 | S1 | No for runtime/producer retention; catalog frozen | ISSUE-076/077/079 interactions; D50 | A: durable history + bounded views and cache generations
C-004 | NOT VERIFIED | S1 (index only) | Not assigned | Not assessed | Not assessed | Verify and measure
C-005 | NOT VERIFIED | S2 (index only) | Not assigned | Not assessed | Not assessed | Verify full row
C-006 | CONFIRMED | S1 | S1 | Runtime/producer non-frozen; catalog frozen | = ISSUE-079; overlaps ISSUE-076/077 | A: isolate control/protection + bounded preparation; exact-parity SQL repair
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

**Current status: C-002 CONFIRMED/S0; C-006 and C-003 CONFIRMED/S1; 5 retained performance rows remain unverified; 9 rows are reassigned to V1c.** The appended C-002 formal-verdict section supersedes its retained initial evidence section. The full V1a scope is not complete; there is no real-data/device readiness claim.

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

## C-003 — initial placeholder (superseded below)

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

## C-006 — initial placeholder (superseded below)

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

## C-006 — formal verdict

### Auditor claim (short quote)

“catch-up و آماده‌سازی همهٔ سلول‌ها به‌ترتیب await می‌شوند؛ مدیریت پوزیشن پس از همهٔ آن‌هاست.” Catch-up and cell preparation are awaited sequentially; position management follows them. The full row (including Telegram polling before preparation, absent per-prepare deadline, semaphore limitation, recommendations and conditional safety effects) was read from `/tmp/AUDIT.md`, not merely its index. Auditor S1.

### What I read (files, line ranges, functions, callers)

Cumulative reading includes the entire `scripts/run_apex.py` and the boot/runtime material listed under C-002. For this row: complete `PaperRuntime.run_cycle` (paper_loop.py:956–1067), `run`/pause/stop (1103–1143), `_refresh_publishers` (873–949), storage/report/helper paths through 1192, `_load_cursor`, cursor migration/upsert (218–269), constructor/boot/stage dispatch (352–480), stages and provider resolution (480–689), complete execute/fill/management methods (692–869). The beginning 1–350 includes PlanQueue, normalization, intent identity and publisher classification. No inference from the stale DECLARED_SKIP docstring is used.

Full named producer methods: `_input_fingerprint`, `prepare`, `get_bridge_context`, `_compose_bridge_context`, `quality_window`, `mtf_inputs`, `paper_marks`, `adv_input`, `ladder_input`, `paper_account_inputs`, `prepare_engine_bundle`, `decision_inputs`, `_raw_content_hash`, `window`, `training_dep_window`, `_frame_at`, `feature_timeline` (engine_context.py:1759–2548). Relevant direct consumer: PaperPlanBridge.prepare/__call__ (plan_bridge.py:530–560), bound in serve (run_apex.py:748–770). Scheduler constructor/due/run_cell/inner/burst/serialization (clock.py:442–650) provides the actual semaphore and stage timestamps. Native store get_window/_row_to_obs (sqlite_store.py:497–559) and real DDL/migrations (1–383), ledger initialization/DDL/read paths from C-002. BootstrapService.catch_up (1456–1565) was read completely: serial TF/symbol/page loops, per-row prior-hash lookup, await ingest/publish, named failure isolation, final counts and boundary update. Synthetic tests isolate this external catch-up seam rather than contact its source.

`grep -rn` consumers search is saved in `C-006-consumers.out`. Read both relevant complete integration test functions at test_ops_paper_loop.py:865–925 (preparation outside-budget ordering and failed-preparation retry). Other complete engine formula bodies, unrelated tests and device artifacts are not certified by this scheduling verdict. The numerical engine chain was not reimplemented, executed on invented model weights, or accepted as correct.

### Reproduction (command, probe file, actual result)

Native probe: `PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V1a/C-006.py`; raw `C-006.out`, exit 0. Shared fixture builder `perf_support.py` initializes the repository's real SQLiteStore and LedgerWriter DDL in a temporary file, then bulk inserts **200,000 market rows + 200,000 matching raw rows**, 1,000 PIT facts, 100 native ledger records. Ten symbols × two TFs, 10,000 observations per cell; content hashes come from real MarketObservation.content_hash. This is a performance corpus, not real market evidence or an ingestion-throughput benchmark. Temporary DB was removed on exit. SQLite 3.40.1; no model or secrets read.

Real `_input_fingerprint` and `window(...,300)` were called, with only classifier **metadata** stubbed for fingerprinting, not a classifier/engine computation. Exact executed SELECTs were captured at runtime and EXPLAINed in both index configurations, not extracted/reimplemented from AST. The native window returned 300 identity-validated rows without device indexes.

| Native operation | No device indexes | Both device indexes |
| --- | --- | --- |
| `_input_fingerprint` | 0.851625 s, complete | interrupted at 2.000442 s |
| `window(...,300)` | 0.233038 s, complete | interrupted at 2.000260 s |

An audit-only SQLite progress handler bounds each operation at two seconds. **Interrupted timings are lower bounds, not completion latencies.** Without device indexes, join plan is SCAN r + PK SEARCH m. With them, fingerprint becomes SEARCH m by symbol + SCAN r, and metadata window becomes SEARCH m by symbol/TF/time range + SCAN r. This independently reproduces ISSUE-079's problematic planner direction at 200k rows, not its device seven-hour duration. The ordinary market get_window query improves from table SCAN to index SEARCH; therefore simply dropping the useful market index is not a general repair.

Other query plans: global PIT facts still scan the snapshot PK index in both modes; prior-cell PIT improves to `idx_pit_scope_asof`; full ledger remains `SCAN ledger`; ladder and sqlite_master scans persist. Those are explicit performance observations: full-input fingerprint cost grows with retained facts/ledger; the small schema scan is not a claimed material bottleneck. Subquery scan over a LIMIT-300 result is bounded and not confused with scanning the whole market table.

Actual `PaperRuntime.run_cycle`, real Scheduler and cursor persistence were then exercised on the same populated store. Public publishers and all order-bearing stages were replaced by declared offline observation seams; this isolates scheduling, not trading correctness. Catch-up slept 40 ms, two prepare calls slept 120 ms each:

- Management began at **0.293971 s**, strictly after serial preparation; cycle took **0.294403 s**. Fixture-clock stage durations were `[0,0]` despite measured wall delay. This proves stage timing excludes preparation, not a real-device p95 violation.
- Never-returning prepare: at **0.552771 s**, one gateway poll and heartbeat, zero scheduler runs, zero management, zero completed cycles. Audit cancellation ended the test; no production timeout ended the wait.
- Separate stuck second scheduled cell: at **0.552340 s**, first cell already appears in Scheduler.runs, but **zero durable cursor rows and zero completed cycles** until the second cell is released. This is the gather barrier associated with ISSUE-077.

Related pytest command used the existing offline guard/environment wrapper documented under C-002, with the two node IDs `test_cp14_context_preparation_is_outside_budget_and_before_source` and `test_cp14_preparation_failure_isolated_retry_same_close_and_no_stale_source`. Raw `C-006-pytest.out`: **2 passed, 13 warnings in 4.05s**. Unlike the native probe (zero guard attempts), these existing tests attempted six DNS resolutions in publisher work, all **blocked before network contact**. Their PASS includes conservative publisher refusal induced by the guard; it is not public-endpoint acceptance.

### Verdict and reasoning

**CONFIRMED / S1.** A slow or stuck prepare blocks subsequent preparations, scheduled cells and position management, and the next Telegram poll/heartbeat. A completed asynchronous SQL operation can leave the Python event loop available to other tasks, yet the single driver does not schedule another gateway/management pass. CPU-bound native work can additionally block the loop itself. Neither scenario is fixed by the later semaphore of four. The test does not claim venue-resident stop orders cease functioning or that an actual loss occurred.

The auditor's conditional claim holds. However, outside-plan-budget preparation is expressly authorized by the later G1 decision; its location alone is not a contract violation and must not be “fixed” by deceptively moving timestamps. Operational wait/isolation is the defect.

### Root cause

One sequential driver orders catch-up → heartbeat/storage/control poll → publishers → per-cell prepare → gather(all scheduled cells) → cursor commits → manage_positions → reporting. There is no prepare deadline and no independent loop for gateway/management in this composition. Producer hashing reads all symbol history across TFs, global facts and ledger; a non-indexable expression on the raw PK adds the measured join hazard. These are distinct causes: query repair shortens work but does not bound a never-returning preparer.

### Direct impact

Delayed next operator poll, delayed local exit management, delayed heartbeat and whole-cycle observability; one analytical cell can stall unrelated cells. The query and scheduling reproductions are independent controls: neither synthetic sleeps nor empty model metadata is presented as evidence for native feature accuracy. Severity S1 reflects serious protection/control coupling, not guaranteed S0 deadlock on every dataset.

### Secondary effects and interactions (upstream/downstream)

**ISSUE-079:** exact fingerprint/window join and all-history read overlap; no duplicate new issue. The two device indexes can worsen this join order while improving other readers. **ISSUE-076:** indexed ordinary market/PIT reads improve; per-row catch-up/quality commits happen upstream of the same barrier and can lengthen it. Missing replay CLI is not causal to this scheduling failure. **ISSUE-077:** gather delays cursor/cycle publication even after a cell has finished; importantly scheduler events/runs can already exist, so it is too broad to say literally all possible evidence is absent. The DB-lock boot issue is separate from this probe.

Upstream data growth/index state/classifier-package binding changes preparation cost and cache identity. D22 preparation failure must preserve same-close retry and prohibit stale-success fallback. Downstream delayed management can use an older cycle as_of (recorded before awaits), while C-004 governs skipped intervening close decisions. No replay outcome, monetary loss, model accuracy, phone RSS or live latency is inferred. D30 remains 20 default training cells, not the 140 data/runtime cells.

### Contract and decisions

APEX_GEN5.md:18435–18443: “single event loop for all input/output ... with a bounded worker pool for computation”; contention is serialized by the one ledger writer. 18897–18899: P0 “must never be dropped or delayed”; P1 “within 2 seconds”. 18869–18872 defines analysis p95 400 ms including native feature/context/forecast/decision but excluding network; these are declared targets, not measured acceptance. Lifecycle stages have no millisecond budget (153–158), so a 294-ms synthetic management delay alone is not a numeric lifecycle SLA breach; the unbounded analytical dependency is the safety issue.

Later owner implementation direction at PHASE2_DECISION_LOG.md:802 binds source/preparer “outside scheduler budgets”; 573–575 explicitly orders prepare before cell clocks and retains D22 failure isolation. 944 repeats that binding. **Precedence:** preserve that explicit seam; add separate truthful operational latency and responsiveness controls rather than retroactively alleging the approved seam was unauthorized. D50 (1159) requires durable no-repeat closes; D51 (1161) atomic budget; preserve both under any concurrency change. CP9 handoff 629–631 confirms separate preparer/source and named per-cell catch-up failures, not permission for indefinite control starvation.

### Frozen status and non-frozen alternative

paper_loop, engine_context, scheduler and bridge are non-frozen. The catalog/store and engine bodies are frozen. The problematic join is in non-frozen engine_context, so a validated identity-aware query/producer adapter can repair it without touching frozen catalog DDL. Additive indexes must live in an authorized non-frozen migration; never silently mutate device schema during verification. CPU offload can be a non-frozen producer boundary with one ledger writer retained.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

**A — isolate control/protection servicing, bound analytical preparation, repair exact SQL separately.** Preserve single event loop I/O and serialized ledger writes; move CPU work to bounded workers with cooperative shutdown or process isolation. An asyncio timeout alone cannot preempt synchronous CPU work and may leave SQLite work queued; cancellation/late-result policy must be explicit. New interleavings require immutable as_of/generation binding, no stale cache resurrection, same-close retry and budget/no-duplicate tests. Existing outside-budget ordering tests should remain semantically valid; tests assuming BTC/ETH serial completion may require new scheduling-aware expectations. Worker completion must not publish a timed-out generation. No retraining is inherently needed if values/order/hash canonicalization stay identical; prove parity on cold/warm/restart paths.

**B — exact-parity query/cache optimization first plus truthful duration reporting.** May greatly reduce measured delays but cannot resolve an indefinitely blocked external prepare. Fix both fingerprint and window joins; validate `obs-` identity grammar, duplicate/correction/PIT rows, output order and hash parity. Restricting the fingerprint to only a timeframe or recent bars is **not automatically parity-preserving**: it changes invalidation semantics and may miss cross-TF/PIT/ledger dependencies. Identity-preserving SQL rewrites require no model retraining; changed cache-key scheme needs versioning/invalidation, not historical hash rewrites. An additive index migration costs disk/write overhead and planner regression tests; no migration is necessary for a pure query rewrite.

**C — per-cell cursor publication before gather completes.** Reduces the ISSUE-077 crash/repeat/observability window but not pre-stage preparation blocking. Changes commit ordering and timestamp/ledger interleavings; must preserve D50/D22, transactional state and not certify a cell before relevant durable effects. No retraining; DB schema need not change. The new gather-barrier regression intentionally changes after a correct fix, whereas retry/no-stale-source regression must not break.

### My recommendation

A with B, and treat C as the separately linked ISSUE-077 work. Do not weaken data quality, risk vetoes, offline PAPER isolation or owner-approved timing separation to obtain a fast fake PASS. No implementation changes are made by this audit.

### Acceptance and regression tests

Retain 200k fixture with both index sets and record all full scans; assert identical ordered rows, fingerprints and lineage for any SQL rewrite (including invalid identity and correction cases). Inject bounded, failing, cancelled and indefinitely pending prep and synchronous CPU work while measuring independent control/protection service. Assert no orders from timed-out/stale generations, no duplicated closes or budget reservations, D22 retry preserved, and durable completed-cell publication under one stalled sibling. Run both read integration regressions under network denial and record guard refusals explicitly. Device evidence still required for actual p95/RSS/throughput and real model/data outcomes; synthetic results prove mechanism only.

## C-003 — formal verdict

### Auditor claim (short quote)

“events، cycles با همهٔ cell_runs، scheduler._runs، trades/refusals و audit آداپتر بدون retention انباشته می‌شوند.” Histories accumulate without retention; the same full row also identifies unbounded producer `_ready`, `_failed`, `_raw_lineage`, **and correctly excludes bounded `_frames` (32) and `_content_hashes` (4096)**. It explicitly does not claim measured device OOM. Full expanded row was read from `/tmp/AUDIT.md`. Auditor S1.

### What I read (files, line ranges, functions, callers)

The complete referenced runtime factory and adapter were read under C-002; the complete paper-loop accumulation/consumption paths were read under C-006. C-003 rechecks Runtime collector 155–171 and serve's producer lifetime 748–770; PaperRuntime constructor 401–405, execute_plan 692–745, publisher refusals 917/938, run_cycle 956–1067, `_plain` 1169–1182 and final run totals 1127–1133; Scheduler constructor and both append branches in run_cell/inner 442–606; adapter constructor, audit views, `_execute`, `_cached_result`, `_refused`, and interval registry 322–840. Producer constructor/prepare/get_bridge_context 1759–1841, raw content hash/window/frame 2350–2441 and full feature_timeline 2444–2549 were read, including the actual prune/pop conditions.

Mandatory consumers/retention grep over these files is saved as `C-003-retention.out`; C-006's wider consumer search covers callers. It shows every listed insertion, read and removal in these owners. `_ready.pop` and `_failed.pop` clear **only the exact next preparation key**, not old as_of keys. `_raw_lineage` has insertion and consumers but no deletion. `_frames` explicitly evicts >32; `_content_hashes` evicts at 4096. `_timelines` has bounded cell keys but variable-length signatures/evidence; no separate verdict on that additional retention surface is assigned here.

SQL callees use the real store DDL/get_window/row conversion and native content hash reviewed for C-006. Governing memory/retention/idempotency clauses and decision-log bounded memo/D50 records below were read. No source/config/frozen file is modified.

### Reproduction (command, probe file, actual result)

`PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V1a/C-003.py`, raw `C-003.out`, exit 0. Native fixture: **200,000 market + 200,000 raw rows**, 1,000 PIT facts, 100 ledger records in a temporary repository-DDL SQLite store; same native content hashing as C-006. The idle bus was stopped **only during seeding**, then restarted before the runtime soak. No network/model/order was used; guard attempts were zero.

Native lineage-window read of 5,000 bars: **0.873325 s** without device indexes, retaining **5,000 raw-lineage entries but only 4,096 content-hash entries**. With both indexes, native metadata join interrupted at **2.000630 s** (lower bound). Both actual SELECTs were EXPLAINed: ordinary market reader changes SCAN to indexed SEARCH; raw identity join changes SCAN r + PK SEARCH m into range SEARCH m + SCAN r. The bounded outer subquery scan is distinguished from a full-table scan. This is the same ISSUE-079 SQL hazard as C-006, not a new issue count.

Next, 40 actual cycles, each advancing the fixture clock to a new monthly boundary so **all 140 scheduler cells** are due. Real run_cycle, Scheduler, cursor writes, event bus/collector and cycle copy paths run. Analytical/order stages are explicit no-order fixtures, public publishers are disabled, and actual producer.prepare receives a named missing-model exception at its classifier loader seam; this exercises native failure retention without building a fictitious model/context. Ten real sessionless adapter **queries** per cycle grow audit records; execute_plan's native pre-submission-refusal branch is exercised with only FSM.submit replaced by a local refusal, never a venue submission.

After explicit `gc.collect()` at each sample:

| Cycles | Scheduler runs / collected events / failed-context keys (each) | Adapter audit | Trades / refusals (each) | Retained traced heap delta |
| --- | --- | --- | --- | --- |
| 10 | 1,400 | 100 | 10 | 12,850,293 bytes |
| 20 | 2,800 | 200 | 20 | 25,602,176 bytes |
| 40 | 5,600 | 400 | 40 | 51,071,454 bytes |

Soak elapsed at 40 cycles: **70.168949 s**. `_raw_lineage` remains 5,000 (only one historical window was loaded); bounded content hashes remain 4,096. `_ready` remains zero in the failure-only experiment: **success-context retention is established by its read code, not falsely claimed as measured native success**. Tracemalloc is Python allocation evidence, not RSS, Android memory, or a real-time slope. Forty accelerated month boundaries are not forty months of continuous market activity.

### Verdict and reasoning

**CONFIRMED / S1, same severity as auditor.** Actual persistent runtime containers and surviving traced heap increase with new cycles/as_of values; garbage collection cannot free reachable history. The producer failure path alone suffices even with no accepted plan. The full row already acknowledges bounded caches and unmeasured phone OOM, so PARTIAL is not warranted merely because those limitations remain true.

No claim is made that every container is unbounded, every refusal increments PaperRuntime.refusals, or an exact 400-MB breach/Android kill time follows from this fixture. Producer failures live in `_failed`, whereas runtime.refusals uses particular publisher/execution branches; the experiment distinguishes them.

### Root cause

Long-lived collector, scheduler, driver and adapter histories are list appends without pruning. Cycle dictionaries additionally copy dataclass run records into JSON-like views, keeping a second historical representation. Producer keys include as_of, so replacing/removing only a same-key success/failure does not release earlier timestamps. Raw lineage is keyed per observed content identity and kept indefinitely in that producer. These objects stay referenced by serve throughout the run.

### Direct impact

Growing retained heap and increasing histories/views; no hardware-specific OOM threshold is needed to prove the retention defect. The memory target is finite while the number of fresh keys/events is not. Full tuple views (scheduler.runs, adapter.audit_trail) also allocate copies when inspected. Actual loss of a process/position is a possible secondary consequence, not an observed trading event.

### Secondary effects and interactions (upstream/downstream)

Upstream source changes/new as_of values generate new keys. The D50 trade budget correctly uses `_budget_taken`, not history length; bounding history must not accidentally change admission accounting or cycle numbering (`len(cycles)+1`). Failed-context entries must still prevent stale source resurrection. Downstream status/serve prints, tests and exports currently read whole histories or lengths; naïvely truncating them loses totals and diagnostics. Persistent event/ledger identities and dedup cannot be forgotten merely to reduce RAM.

**ISSUE-076:** better indexes/per-row commit batching address throughput, not retained Python objects; increased throughput may reach a memory problem sooner. **ISSUE-077:** delayed cycle publication does not mean no memory is retained: Scheduler.runs/events can survive while gather blocks; restart recovery becomes more important if resource pressure kills the process. **ISSUE-079:** producer history reads and raw-lineage retention share the window path; index changes do not prune caches. The new benchmark reproduces the same join hazard. No separate device-performance/kill claim is added.

Training/replay: discarding only redundant runtime caches should reproduce the same native results from authoritative store state. Truncating actual engine normalization/signature/history inputs would change state, hashes and possibly training labels; that is not an authorized cache fix. D30 remains 20 default training cells.

### Contract and decisions

APEX_GEN5.md:18883–18885 declares memory target “< 400 MB sustained heap” including feature vectors, recent candles, registry and model cache; 18444–18451 requires target-device capacity validation. 18479–18481 requires minimum 90-day on-device log retention/archive; 18734 says ledger “never purged (permanent audit trail)”. None requires unlimited RAM mirrors. Durable retention and bounded in-memory views must coexist.

PHASE2_DECISION_LOG.md:1025–1027 approves bounded consumer-local timestamp/native hash memo while preserving values/errors; specifically 4096 entries and exact typed hash payload. D50 at 1159 rejects duplicate client order IDs without resending, preserving recorded outcomes and durable close locks. These later decisions take precedence over any older TTL-only reading that would allow a forgotten intent to submit twice. No owner decision found here authorizes losing permanent audit evidence or engine-history semantics to meet a memory target.

### Frozen status and non-frozen alternative

All reported retention owners are non-frozen (ops producer/loop, scheduler, adapter, composition root). Use non-frozen durable journal/index/migration plus bounded read views rather than altering frozen catalog methods or engine internals. If an optimization proposes trimming native engine state/history or changing frozen backtest logic, explicit owner ruling is required. No such edit is necessary to bound redundant observer histories.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

**A — durable histories plus bounded views and cache generations.** Persist full required audit, keep bounded recent cycles/events/trades/refusals, independent monotone counters, and evict obsolete success/failure as_of entries only after no in-flight consumer references them. Reload lineage and contexts with unchanged PIT/content binding; keep typed native hash memo bounded as already implemented. This adds write load and possibly an additive journal migration; need disk-floor/backpressure policy, restart evidence and graceful shutdown. Existing tests that assert all cycles/audit items remain in memory must instead inspect durable history or a configured test-sized view. Short tests inspecting the latest cycle and bounded hash parity must still pass. Do not call this schema-free if a new durable table is selected.

**B — bounded caches plus explicit bounded-session operation pending durable history.** Could reduce producer failure/lineage retention without touching frozen files; eviction may increase SQL work and trigger ISSUE-079 more frequently. Session restarts alone lose in-memory diagnostic and dedup state, so this is not safe unattended operation or a complete fix. Cold/warm/recovery parity must be established before deployment.

Both: no model retraining or identity/hash change is required for a pure cache/view fix. Persisted source corrections must invalidate cached successes exactly as now. A cache format/version change invalidates cache entries, not historical ledger hashes. **Never simply drop `_duplicates`**: durable query/reconcile/no-resend semantics must replace it. Do not bound native model history by guessing a recent window or silently change D30 scope.

### My recommendation

A, with producer failure/lineage retention and duplicate-safe durable audit treated separately from UI history. Keep 32/4096 bounds as evidence of existing controls, not targets for unnecessary replacement. Co-verify with C-006 and the known SQL issues, since cache eviction can expose repeated expensive reads.

### Acceptance and regression tests

Use this 140-cell soak with growing as_of and explicit GC; after the retention policy's warmup, require a stable bounded heap and container-size envelope while durable counts continue increasing. Test success and failure generations, active readers during eviction, exact-context reload after correction, bounded typed-hash precision/error parity, full ledger/audit retrieval after rotation, and duplicate client IDs after process restart. Budget/cycle totals must not reset when a deque rotates. SQL plans must be measured with both device indexes at ≥200k market rows. Native failure/observer retention was measured here; full-model context size, phone RSS and OOM remain device evidence, not extrapolated numbers.

## New findings not in the audit

None established at mandatory depth. No X-V1a IDs assigned. The limited ledger SCAN observation and decision-label caveat above are retained as follow-up notes, not promoted to completed new findings. Full audit duplication checks have not been performed.

## Rows not verified or incomplete

Retained, unverified: **C-004, C-008, C-010, C-012, C-013**.

**Reassigned to V1c:** C-001, C-005, C-007, C-009, C-011, C-014, C-015, O-006, V-003. No V1a verdict or further verification is claimed for these nine IDs.

Retained order: C-006, C-003, C-004, C-008, C-010, C-012, C-013. Some shared runtime source has been read for C-002; that is not a verdict on these rows. Their full-row comparisons, mandated complete files/tests, measured reproductions, per-cell/bar SQL EXPLAIN and fix-side-effect analyses remain outstanding. No coverage or readiness sign-off for those rows.

## Final counts

- CONFIRMED: **3** (C-002 S0; C-006 and C-003 S1)
- PARTIAL: **0**
- REJECTED: **0**
- DEVICE-EVIDENCE-NEEDED: **0**
- Retained unverified: **5**
- Reassigned to V1c: **9**
- Established new findings: **0**
