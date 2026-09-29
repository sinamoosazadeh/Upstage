# V1a independent verification — retained scope complete

ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option
--- | --- | --- | --- | --- | --- | ---
C-002 | CONFIRMED | S0 | S0 | No (factory/adapter/FSM); additive migration needed for fix | = ISSUE-075; = user-provided D58; D1/D2; related ISSUE-077/078 | A: governed simulator factory; never private network transport in PAPER
C-001 | NOT VERIFIED | S3 (index only) | Not assigned | Not assessed | Not assessed | Reassigned to V1c; no V1a work
C-003 | CONFIRMED | S1 | S1 | No for runtime/producer retention; catalog frozen | ISSUE-076/077/079 interactions; D50 | A: durable history + bounded views and cache generations
C-004 | CONFIRMED | S1 | S1 | No (scheduler/loop); catalog frozen | D50/D53; distinct from ISSUE-076/077/079 | A: durable close dispositions + deadline-driven wakeup
C-005 | NOT VERIFIED | S2 (index only) | Not assigned | Not assessed | Not assessed | Reassigned to V1c; no V1a work
C-006 | CONFIRMED | S1 | S1 | Runtime/producer non-frozen; catalog frozen | = ISSUE-079; overlaps ISSUE-076/077 | A: isolate control/protection + bounded preparation; exact-parity SQL repair
C-007 | NOT VERIFIED | S2 (index only) | Not assigned | Not assessed | Not assessed | Reassigned to V1c; no V1a work
C-008 | CONFIRMED | S1 | S1 | No (ops); frozen dependencies | CP11–13; ISSUE-076/077/079 interactions | A: bounded durable source spool + filtered repair
C-009 | NOT VERIFIED | S1 (index only) | Not assigned | Not assessed | Not assessed | Reassigned to V1c; no V1a work
C-010 | CONFIRMED | S1 | S1 | Runner/store frozen; service wrapper non-frozen | W.6; D57; ISSUE-076/077/079 interactions | A: periodic bounded resource admission and safe pause
C-011 | NOT VERIFIED | S2 (index only) | Not assigned | Not assessed | Not assessed | Reassigned to V1c; no V1a work
C-012 | CONFIRMED | S1 | S1 | Runner/client frozen; supervisory wiring non-frozen | W.6/CP11–13; ISSUE-076/077/079 distinctions | A: whole-invocation retry budget + durable resumable pause
C-013 | CONFIRMED | S1 | S1 | No (bus/harness/composition) | T-NFR-004; ISSUE-076/077/079 interactions | A: bounded P1 admission + truthful end-to-end capacity tests
C-014 | NOT VERIFIED | S2 (index only) | Not assigned | Not assessed | Not assessed | Reassigned to V1c; no V1a work
C-015 | NOT VERIFIED | S2 (index only) | Not assigned | Not assessed | Not assessed | Reassigned to V1c; no V1a work
O-006 | NOT VERIFIED | Not extracted | Not assigned | Not assessed | Not assessed | Reassigned to V1c; no V1a work
V-003 | NOT VERIFIED | S4 | Not assigned | Not assessed | Not assessed | Reassigned to V1c; no V1a work

**Current status: 8 retained rows verified; 0 retained rows unverified; 9 rows reassigned to V1c.** Each appended formal-verdict section supersedes its initial placeholder/evidence section. The eight retained rows are complete: C-002, C-006, C-003, C-004, C-008, C-010, C-012, C-013. Nine other rows were reassigned, not verified. There is no real-data/device readiness claim.

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

## C-004 — initial placeholder (superseded below)

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

## C-008 — initial placeholder (superseded below)

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

## C-010 — initial placeholder (superseded below)

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

## C-012 — initial placeholder (superseded below)

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

## C-013 — initial placeholder (superseded below)

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

## C-004 — formal verdict

### Auditor claim (short quote)

“due_cells فقط آخرین boundary هر TF را می‌دهد” — due_cells returns only the latest boundary per TF. Full row also distinguishes catch-up **data** from replay of every decision, identifies post-work sleep, and recommends explicit backlog/disposition without blindly trading stale signals. Full row read from `/tmp/AUDIT.md`; auditor S1.

### What I read (files, line ranges, functions, callers)

Full `Scheduler.due_cells`/run_due/run_cell and cursor update flow (clock.py:501–606), constructor/cell fields 442–499, all calendar helpers `latest_close_boundary`, `_next_month_ms`, `tf_close_times`, `next_close` (189–253), FixtureClock and conversion methods (97–170). Full direct caller PaperRuntime.run_cycle (956–1067), run/_paused/_stopped (1103–1143), cursor DDL/load/upsert (218–269), real ingest 476–494 and constructor; complete CLI serve including interval/default/control wiring was already read for C-002. Complete BootstrapService.catch_up (1456–1565) was read for C-006; it catches up source bars and publishes quality, not scheduler decision records for each historical close. Native store DDL/get_window and content hashes are the shared reviewed callees. Consumers grep is saved in `C-004-consumers.out`.

Read complete test functions: scheduler due ordering (test_scheduler_clock.py:428–435), cursor monotonic persistence (test_cp146.py:144–164), calendar 400-day enumeration (215–265), and integration pause/run-loop tests (test_ops_paper_loop.py:667–703). The three unit tests named below were executed; the integration pair was only read here. No claim of full-suite/full integration-file coverage.

### Reproduction (command, probe file, actual result)

`PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V1a/C-004.py`, raw `C-004.out`, exit 0. The native repository-DDL fixture has **200,000 market rows + 200,000 raw rows**, 1,000 PIT facts and 100 ledger records. The real PaperRuntime, Scheduler, native ingest/get_window, cursor migration/read/upsert and restart filtering execute; downstream signal/order stages are explicit inert fixtures and public publishers disabled. No exchange/Telegram/secrets/model used; guard attempts zero.

One BTC:1m cell runs at minute 1, then the real fixture clock advances to minute 4. Repeat with neither device index and with **both** exact supplied indexes:

| Device indexes | Selected decision minutes | Durable cursor | Fresh driver at minute 4 | Three-call elapsed |
| --- | --- | --- | --- | --- |
| Neither | [1,4] | 4 | due=0, already-decided=1 | 0.101569 s |
| Both | [1,4] | 4 | due=0, already-decided=1 | 0.008418 s |

No decision runs/dispositions at minutes 2/3 are created. Restart is an actual fresh driver reading the persisted cursor, not a manually copied Python dictionary. It cannot recover these skipped closes from the maximum cursor at minute 4.

Actual SELECTs were captured and EXPLAINed with/without both indexes: native market window changes full **SCAN market_observation** + sort to **SEARCH ... idx_mo_sym_tf_open** + bounded outer sort. Schema migration lookup uses its covering PK; cursor loading is a full **SCAN cell_decision_cursor** (one row in this test, naturally one row per cell, not the 200k table). No PIT SELECT is issued by these isolated scheduling/ingest paths, so the PIT index does not affect this experiment. Unlike C-006, no raw metadata join is needed here. Indexes improve query time but do not change missing-decision semantics.

Actual `PaperRuntime.run(cycles=2,interval=.05,sleep=waiter)` then uses a local catch-up workload sleeping 80 ms and advancing the fixture clock by 120 s; the supplied sleep records its argument, sleeps 50 ms and advances the fixture by 60 s. Work ends at **0.081288 s**, interval sleep starts **0.090522 s**, ends **0.140950 s**, then next work begins **0.140988 s**. Total **0.238562 s**. Decision minutes are **[5,8]**. The simulated clock jumps illustrate work-plus-interval, not a measured 120-second production catch-up. The CLI default interval remains 60 seconds; the test intentionally scales its real wait down.

Calendar control: real `due_cells` at Jan 1 and Apr 1 selects only those endpoints; real `tf_close_times` enumerates Jan/Feb/Mar/Apr. Therefore this is not a missing D53 helper or a 30-day-month bug; enumeration exists but due_cells does not use it for missed closes.

Existing regression command (same sanitized network-denying environment as C-002): `python3 -m pytest -q -p no:cacheprovider tests/unit/test_scheduler_clock.py::TestPriorityLanes::test_due_cells_are_ordered_by_close_then_symbol_then_timeframe tests/unit/test_cp146.py::test_d50_cell_cursor_survives_a_new_reader tests/unit/test_cp146.py::test_d53_week_and_month_boundaries_match_the_calendar_for_400_days`. `C-004-pytest.out`: **3 passed in 0.70s**, guard attempts **[]**. These establish calendar/order/no-rewind invariants, not backlog acceptance.

### Verdict and reasoning

**CONFIRMED / S1.** Latest-boundary selection plus max cursor can silently omit per-close decision invocations across a pause/slow cycle. A fixed sleep *after* work compounds drift. Neither faster queries nor restart makes the omitted closes available to this selection logic.

The qualification matters: native feature_timeline may still consume historical bars and reconstruct historical feature state. The proof is not that intervening market data is absent or every engine-derived event is lost. It proves the missing **per-close scheduler decision/disposition** and its persistence across restart. Financial loss, missed profitable signal and exact phone latency are not established.

### Root cause

`due_cells` computes one `latest_close_boundary(moment,tf)` and compares it to one last-close value; it does not enumerate the interval. PaperRuntime additionally filters that one value by durable cursor and stores a monotone maximum after processing. No gap ledger records older boundaries. `run` sleeps the full configured interval after a completed cycle rather than waking against a fixed next deadline.

### Direct impact

For a gap spanning multiple boundaries, only the newest close is offered. Even bars already present in the native store do not trigger older decision invocations. A monotone max cursor prevents reprocessing completed closes (correct D50 behavior) but cannot represent missing earlier dispositions. This is a coverage/accounting gap, not permission to execute stale orders as a remedy.

### Secondary effects and interactions (upstream/downstream)

**ISSUE-076:** data replay/backfill can fill candles and quality, but does not create per-close runtime decisions; fixing replay CLI/row commits alone does not fix selection. **ISSUE-079:** long fingerprint/window work increases the chance of crossing close boundaries; its index repair reduces trigger frequency, not this cause. **ISSUE-077:** gather-before-persist can delay/lose cursor progress on interruption and cause repeated work; C-004 is the different case where the cursor successfully advances **over** unrepresented closes. Both need coherent recovery semantics rather than resetting the maximum blindly.

Upstream catch-up follows a source frontier and availability policy; any historical evaluation must retain that PIT law and distinguish decision time from late receipt time. Downstream risk admission, identity/dedup, expiry, position management and budget cannot be treated as if old opportunities are current. Time-based exit checks may be delayed across a slow cycle (C-006), but no actual missed exit/loss is reproduced here. A historical replay can differ in decision invocation count without proving engine output mismatch.

### Contract and decisions

APEX_GEN5.md:20507: “on each TF close, ingest→quality→features→engines→setup→gates→risk→decision→execution for that (symbol,TF).” Normative per-close catch-up at 20512–20517 requires completed closed-bar catch-up before computation; it does not say the newest close may silently stand for all missed decision closes. D50 (PHASE2_DECISION_LOG.md:1159) requires durable last processed close and no repeated cell-close on restart; the existing maximum correctly satisfies no-rewind but is insufficient to certify completeness.

D53 at 1165 expressly mandates Monday/month-start venue boundaries and a 400-day enumeration; preserve that later decision rather than use fixed seconds for calendar months. D22 same-close retry remains binding for preparation/catch-up failures. No later decision identified here authorizes silent missed-close disposal or retroactive live execution. **Owner policy is needed for stale-close disposition**, especially what is historical analysis versus current protection/execution; the audit cannot invent this policy.

### Frozen status and non-frozen alternative

Scheduler, PaperRuntime and additive runtime cursor/disposition migrations are non-frozen. Existing D53 helpers can implement a non-frozen enumerator; no frozen catalog/engine/backtest rewrite is necessary. Store append-only evidence and a bounded work queue in a non-frozen module. Changing historical engine/research semantics would cross frozen boundaries and require permission; it is not required just to make missing closes explicit.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

**A — durable per-close disposition, bounded backlog, deadline-based wakeup.** Enumerate from a durable contiguous frontier using native calendar helpers; record processed, deferred or explicitly policy-skipped closes. Prioritize current protection/control separately (C-006). Requires additive schema/migration, startup reconciliation of old max cursors with unknown history, backlog metrics and disk-floor/backpressure controls. Do not infer old gaps were decided when migrating. Per-close retries must preserve D50 identities and D22 failures; intermediate outcomes may only advance a contiguous frontier once their disposition is durable. Tests expecting one due cell after arbitrary jumps need explicit selected policy; calendar/no-rewind and no-duplicate tests must remain valid.

**B — governed latest-only decisions with explicit gap records.** May keep current trading behavior and minimize backlog computation, but requires an owner-approved contract/policy and named durable skip reasons. It cannot be described as full per-close replay. Persist gap ranges with actual calendar semantics; classification affects compliance/metrics, not historical order hashes. Less compute than A but deliberately omits historical decisions.

**C — deadline-based wakeup and faster preparation alone.** Removes avoidable post-work drift and helps normal throughput with no necessary schema or training change, but outages/long tasks still produce gaps. Suitable only as a partial mitigation, not closure. Never enqueue an unbounded RAM backlog to hide this defect; C-003 would worsen.

For A/B, retaining original `as_of`, input snapshot/hash and proposal identity is essential; current receipt time cannot be rewritten into historical availability. Pure scheduling/accounting changes need no model retraining. Retraining becomes a separate governed question only if someone changes input history/label/sample semantics; that is not recommended. D51 budget is per cycle, so draining many historical closes in one cycle must not multiply allowed orders or reserve slots for stale analytical results.

### My recommendation

A with owner-approved stale-close disposition and current-protection priority; adopt C as an independent mitigation. Do not solve an observability/coverage defect by retroactively sending old trades or weakening D50's durable dedup.

### Acceptance and regression tests

Keep native ≥200k market-row tests and both index plans. Inject gaps of minutes, days, Monday boundaries, varying-length months and restarts mid-backlog. Every enumerated boundary must have durable processed/deferred/policy-skipped status, with no silent holes and no duplicate identity/order after restart. Preserve D22 retries, D53 calendar tests and D51 atomic budget. Measure deadline wakeups separately from cycle/feature timings; long work must not starve control/protection. Verify PIT receipt/correction parity during historical evaluation and named refusal of unauthorized stale execution. Device p95/phone behavior remains unmeasured.

## C-008 — formal verdict

### Auditor claim (short quote)

“پیش از تحویل اولین صفحه ... همهٔ تاریخچهٔ سلول” — the whole cell history is collected before the first delivered page. The full row also alleges repeated full-history filtering per delivered page, retained histories across cells, and repair's unfiltered fetchall even with `--cells`; it explicitly disclaims phone OOM evidence. Full row read from `/tmp/AUDIT.md`, not an index. Auditor S1.

### What I read (files, line ranges, functions, callers)

Complete ToobitKlineSource and its helper closure (bootstrap_service.py:1–826), service construction/open/fetch/ingest/run/status/report and frontier/checkpoint wrappers (827–1455); catch_up (1456–1565) was fully read for C-006; reporting tail 1566–1680 read across bounded chunks. Complete partial_bar_repair.py:1–544, including find_candidates, run_repair, live/evidence fallback and correct_raw call boundary. Complete frozen BootstrapRunner module (research/bootstrap.py:1–438); checkpoint DDL/lifecycle/bootstrap save/read methods (checkpoints.py:1–203). Native store DDL/ingest/get_window were reviewed under C-006 and ingest rechecked here. CLI bootstrap/repair callers were read under C-002; consumer grep saved in `remaining-consumers.out`. Relevant complete test functions: bootstrap tests at 228–244, 339–355 and tail-aligned venue/helper definitions; both entire related test files were executed, not claimed entirely line-by-line reviewed.

### Reproduction (command, probe file, actual result)

`PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V1a/C-008.py`; `C-008.out`, exit 0. Real imported source, AsyncBridge thread and frozen wire parser; a **lazy async venue double** synthesizes only each requested page, avoiding an independently growing venue-side list. No AST source extraction, no venue contact. Measurements include tracemalloc overhead and are not phone timings.

- 10,000 bars: first 1,000-row delivery requires **10** client calls; cache 10,000; retained traced heap delta **9,748,050 B**, first-page time **4.215 s**.
- 20,000 bars: **20** client calls; cache 20,000; heap **19,097,088 B**, **8.585 s**. Both use max_pages=1; the *second* delivered-page request correctly refuses PAGE_BUDGET_REACHED after the full first walk. No extra empty HTTP page is needed because this fixture ends exactly at DEEP_START.
- 100,000 bars × **two cells**: 100 then 200 total client calls; retained histories 100,000 then **200,000** observations, heap **95,402,820 then 190,796,168 B** after GC. First deliveries take **39.741/38.205 s** with tracing. There is no global history eviction between these cells.
- Five subsequent pages from the cached 100k cell make no new client calls but invoke the real timestamp parser **500,010** times (100k history visits + two boundary parses per page), **3.885 s** without tracemalloc. A delegating counter calls the original parser; it does not reimplement source logic. This measures O(N) traversal per delivered page; O(N²/1000) complete-drain traversal follows from N/1000 pages, not a claimed measured full-drain time.

Repair uses **repository DDL with 200,000 market + 200,000 raw rows**, 1,000 PIT facts and 100 ledger records, all temporary. Actual `find_candidates(store,[('BTCUSDT','1m')])` returns 10,000 candidates but its captured SQL has no symbol/TF filter and materializes the entire CLOSED join first. Without/with both exact device indexes: **4.634/4.832 s**, peak traced allocation **159,103,868/158,716,615 B**. Both EQPs: **SCAN r → PK SEARCH m**. The market symbol/TF/open index cannot serve a missing predicate; the PIT index is irrelevant here. These allocation peaks are not permanent post-GC leak measurements. No repair/apply or external fetch occurs.

Guarded `python3 -m pytest -q -p no:cacheprovider tests/unit/test_ops_bootstrap_service.py tests/unit/test_ops_partial_bar_repair.py`: **97 passed in 4.51s**, raw `C-008-pytest.out`. Native and pytest guard attempts **[]**.

### Verdict and reasoning

**CONFIRMED / S1.** Native measurements replace the auditor's AST-only source experiment and demonstrate first-page traffic, history growth and repeated scanning. Later owner direction explicitly makes max-pages a **runner-page** budget: exceeding it in HTTP calls is not itself a breach of that approved definition. The confirmed defect is absent independent resource/traffic bounding, not an allegation that the current budget implementation contradicts its documented meaning. Synthetic 100k/cell is a stress case, not a claim that today's venue actually retains that much per cell.

### Root cause

_walk_backward accumulates a dict and seen set, then sorted history; __call__ scans history and builds eligible on every request. Histories survive cell completion. `begin_catch_up` clears the selected cell on a new catch-up; increasing end replaces that cell history, neither is a fixed global bar/memory bound. Repair fetchall precedes Python cell selection and skew predicates.

### Direct impact

No runner-page checkpoint can be reached before the initial source walk returns; traffic and memory scale with retained source history, not max-pages. A restricted repair still pays the full CLOSED join/materialization cost. An initial IN_PROGRESS checkpoint can already exist before walking, so “no checkpoint at all” would be too broad.

### Secondary effects and interactions (upstream/downstream)

Upstream tail alignment and CP-12 poison evidence forbid blindly taking a forward venue window or truncating at a guessed cap. Downstream runner cursor, CP-13 store frontier/served_upto and empty-page completion must remain coherent. Replacing an exhausted resource budget by `rows=[]` would falsely certify completion. Repair must preserve calendar close/skew checks, immutable raw revisions, evidence matching and idempotency.

**ISSUE-076:** per-row ingestion/quality commits are downstream, additive costs; neither batching nor market/PIT indexes bounds this source cache. **ISSUE-077:** boot/migration locks and gather-before-persist are separate; this source can delay first progress before that gather stage is even reached. **ISSUE-079:** repair shares the expression-join identity pattern, but its measured plan remains raw-scan→market-PK in both modes; do not assume C-006's indexed nested-raw plan here. This is resource behavior of an already audited row, not a new X finding.

### Contract and decisions

APEX_GEN5.md:17251–17279 requires all available history, per-page checkpoints, “Resume from cursor, never rewind”, and “−1003 backoff, do not skip”; hardware estimates are not start requirements. PHASE2_DECISION_LOG.md:176 (CP11-001) expressly mandates backward adaptation and **runner-facing** max-pages. CP12 owner decision (181) accepts OHLC-drop-with-evidence; CP13 (183) replaces cursor-only serving with frontier/closed-bar semantics; CP13.1 (189–190) preserves still-open repair protection. Those later decisions take precedence over the earlier simple forward-paging interpretation. Memory/latency acceptance still needs target-device evidence (contract 18445–18451, 18883–18885).

### Frozen status and non-frozen alternative

Source/repair/service are non-frozen. Research bootstrap and catalog/parser/store are frozen; do not edit them without owner permission. A bounded non-frozen disk spool/source adapter and SQL-filtered repair can retain the runner and correction APIs. Any new spool schema belongs to an explicitly additive non-frozen migration, not the frozen store migration list.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

**A — bounded durable backward spool, ascending delivery cursor, independent traffic/time budget; filtered keyset repair.** Preserves coverage while reducing memory and repeated traversal. Adds disk/write load, staging identity/version, crash/resume recovery and migration/cleanup policy; cannot purge spool until ingestion/checkpoint acknowledgement. Retain invalid-bar evidence and fresh re-fetch of formerly open bars. Repair ordering must be stable through corrections, with exactly-once event identity and equivalent candidate output. Tests asserting runner-page budgets stay valid; add independent walk-budget tests rather than silently reinterpret max-pages.

**B — index cached open times / ascending delivery offset and release completed cell caches.** Non-frozen, no required DB migration, reduces repeated traversal/cross-cell retention but leaves the first walk and one large cell unbounded. Reuse must account for changing end, frontier reset and failed-ingest retry; stale open snapshots must never become final data. SQL filtering helps repair but does not bound a huge selected cell unless batched.

Neither pure parity option changes native values, content/replay hashes or training protocol; no retraining is required. If historical coverage is deliberately reduced, owner permission and new completeness/input identities are necessary; training/default D30 scope (20 cells, not 140) must not silently change. Regressions must include warm/cold/restart equality, poison counts, dedup and correction lineage.

### My recommendation

A, with B only as a measured interim reduction. Preserve CP11–13 semantics, introduce named resumable exhaustion rather than empty-page completion, and budget disk spool as well as RAM.

### Acceptance and regression tests

Retain ≥200k-row repair EQPs in both index modes and two-cell 200k-bar venue stress; verify fixed working-memory/traffic bounds and exact coverage with interrupted walks/resume. Enforce no false COMPLETE on resource/rate-limit stop, no duplicate/omitted observations, valid open-to-closed refresh and all existing 97 regression tests. Measure actual target-device heap/RSS, first-checkpoint delay and operator responsiveness separately; no OOM threshold/time is inferred here.

## C-010 — formal verdict

### Auditor claim (short quote)

“free-disk و battery تنها هنگام شروع run() سنجیده” — disk and battery are measured only at run entry, not repeatedly during ingestion. The full row names per-observation commits, distinguishes PAPER's 15% storage guard, and makes physical exhaustion conditional. Read full row from `/tmp/AUDIT.md`. Auditor S1.

### What I read (files, line ranges, functions, callers)

Complete BootstrapService lifecycle/run and direct `_fetch`, `_ingest`, probes, checkpoint mirror/report/status closure (bootstrap_service.py:827–1455), full source and helper class (1–826), full frozen research/bootstrap.py (1–438). In particular service.run:1410–1424 calls disk **twice at entry**, battery once; run_phase1:249–302 receives scalar/snapshot values. Full ingest_observations/_count_raw:1040–1076 and frozen SQLiteStore.ingest_raw:383–445; repository DDL and checkpoint bootstrap DDL/save/load/open:1–203 reviewed. CLI bootstrap composition was read for C-002; full PAPER storage/control path for C-006. Shared consumers search: `remaining-consumers.out`. Complete relevant test classes/functions read: TestProbes (bootstrap service tests:539–563), TestHardwarePreflight (research tests:24–85), initial disk/battery tests (292–313). Entire related test files were run, not claimed fully line-by-line reviewed.

### Reproduction (command, probe file, actual result)

`PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V1a/C-010.py`; `C-010.out`, exit 0. Native **BootstrapService → BootstrapRunner → ingest_observations → SQLiteStore.ingest_raw** plus actual research/canonical checkpoint writes. Repository-DDL fixture begins with **200,000 market and 200,000 raw rows**, 1,000 PIT facts and 100 ledger records; three new rows per scenario are really committed. The only resource/venue seams are local injected probe values and parsed synthetic pages. No real disk exhaustion, battery command, external network or orders.

Each scenario starts with 513 MB and 50% battery unplugged, continuous mode explicitly on. Immediately before page two is returned, the resource source changes either to **511 MB** or **4% battery**. Three one-row data pages and one terminal empty page execute. Repeat both cases with neither device index and with both exact indexes:

- Every run: **disk probe count 2, battery count 1**; **3 bars ingested, status COMPLETE**, durable checkpoint bars=3 at the terminal cursor.
- The last two data writes occur after the injected low-resource transition. Re-evaluating the **actual native hardware_preflight** against current values returns **PAUSE**, reason FREE_DISK_BELOW_512MB or CONTINUOUS_BATTERY_BELOW_5PCT.
- A new invocation with the same low resource returns **PAUSED** with no additional source call. The entry guard exists and works; it is stale within an invocation.

Captured actual ingest SELECT EQPs in both configurations: `_count_raw` uses **covering idx_raw_sym_tf_asof SEARCH**; content_hash dedup uses **unique raw content-hash index SEARCH**. No unindexed large-table SELECT appears in this measured ingestion path. The count still traverses the matching cell's indexed entries. Neither supplied market/PIT index participates in these raw predicates. Checkpoint methods use primary-key lookup/upsert and ordered small progress tables; the detailed captured EQPs are for the main store connection, not a falsely claimed trace of its separate checkpoint connection. Results are resource-control evidence, not ingestion throughput claims.

Guarded command: `python3 -m pytest -q -p no:cacheprovider tests/unit/test_research_bootstrap.py tests/unit/test_ops_bootstrap_service.py::TestProbes`; raw `C-010-pytest.out`: **46 passed in 0.43s**, guard attempts **[]**. Native guard attempts also **[]**. Existing tests assert initial thresholds and probe parsing; they do not test a resource transition during a run.

### Verdict and reasoning

**CONFIRMED / S1.** Two near-simultaneous disk reads are not periodic monitoring. The native ingestion path continues committing after a transition that the existing preflight would pause if refreshed. This confirms the audit's conditional long-run safety gap, not a measured disk-full failure, battery-drain rate, corruption or lost row. Exact probe cadence/reserve policy is not specified by W.6 and needs an explicit implementation/owner policy; do not invent a contractual per-row sampling interval.

### Root cause

Mutable device resources are converted to run-entry values. Neither the frozen paging loop nor non-frozen ingestion wrapper samples them again. Individual raw observations commit before the containing page's checkpoint. The separate PAPER cycle storage guard is not called by standalone bootstrap.

### Direct impact

A long successful run may continue writing below the operational pause threshold until it ends or an actual storage/process failure occurs. Initial successful preflight in the report can conceal later deterioration. This experiment observes continued successful writes under simulated low-resource readings, not physical exhaustion.

### Secondary effects and interactions (upstream/downstream)

C-008's long first walk can consume time/resources before a runner page returns; a guard only at page-write boundaries would not supervise that walk. Downstream, a mid-page stop must not advance the page cursor over an uncommitted suffix. Already committed raw rows need duplicate-safe replay and accurate counters, not deletion or fabricated completion.

**ISSUE-076:** per-row commits and quality backfill amplify write/resource cost; batching must preserve coverage and checkpoint semantics. **ISSUE-077:** durable state/lock contention matters to a pause that must persist before disk fills; this probe does not reproduce boot lock or gather failures. **ISSUE-079:** fingerprint/read stalls can delay independent operational monitoring, but its expression join is not the cause here. User D57's disk-floor PAUSE/durable L1/L2 roadmap does not show that this bootstrap invocation already has periodic W.6 monitoring; do not substitute PAPER's percentage guard for the bootstrap absolute floor.

### Contract and decisions

APEX_GEN5.md:17276–17279: per-page checkpoint and never-rewind; “pause if free disk < 512 MB”, continuous pause below 5% unplugged; missing battery API “do not skip”. Nightly 15% skip is a distinct policy; the test deliberately uses continuous mode, not an assumption that Phase 1 is a nightly job. W.7's 20 GB is explicitly an estimate, not a hard start requirement. W.8 (17302–17314) requires persistent state/owner controls. Later CP11–13 frontier/closed-bar decisions preserve ingestion identity and coverage; none identified authorizes ignoring a later threshold breach. Frozen module status constrains the repair, not the verdict.

### Frozen status and non-frozen alternative

Research/bootstrap.py and catalog/store are frozen; owner permission required for edits there. Service/probe/wrapper code is non-frozen. A non-frozen resource supervisor/admission wrapper can pause or stop safely at a durable boundary using the existing command surface; an additive progress reason may require a separate governed state field, not a silent change to frozen status CHECK constraints.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

**A — fresh bounded resource checks before page admission/write plus independent walk supervision.** Cache probes only for a documented short interval; sample actual DB/WAL/spool filesystem, not an arbitrary current directory. Reserve enough headroom to commit a pause/checkpoint; a sampled free-space number cannot guarantee an arbitrarily large page fits. Blocking Termux probes have cost/timeouts and must not starve controls. Pause at an acknowledged page boundary, or abort before its uncommitted suffix with durable retry semantics. If a source page was fetched but not ingested, served_upto must reset to persisted frontier on resume. Tests need resource-transition injection; no existing threshold/absent-battery/parity test should weaken.

**B — bounded invocation/page chunks with fresh entry preflight between them.** Can reduce the stale interval without editing frozen runner, but max-pages is delivered pages, not C-008 walk traffic; not complete coverage during a long fetch. Repeated source initialization increases HTTP, hash lookups and checkpoint writes. A reused source's cumulative pages_served must not make every subsequent chunk refuse immediately. No DB schema necessarily needed, but restart/resume coverage proof is mandatory.

Both options must keep original raw/PIT hashes, canonical correction identities and training inputs; no retraining is inherently required. New pause metadata should be additive/versioned and not rewrite historical checksums. Changing frozen transaction/runner behavior needs owner authorization; a safe wrapper is preferable. Battery API absence stays unknown/proceed, never fabricated zero.

### My recommendation

A, with separately bounded fetch/walk work and explicit safe persistence reserve. B is an interim only. Preserve exact W.6 thresholds and separate continuous/nightly meanings; do not silently elevate the W.7 hardware estimate into policy.

### Acceptance and regression tests

Re-run these native ≥200k-row tests in both index modes: threshold transition before page two must produce a named safe pause without writing that next page, while prior rows/cursor remain valid. Add partial-page failure, retry dedup, storage-pressure during pause persistence, charging changes, absent/malformed battery and bounded probe timeout. Verify state after restart, no skipped suffix, unchanged hashes and no false COMPLETE. Keep initial floor/battery tests and measure real device probe overhead/WAL headroom separately. No real storage fault or battery life has been measured here.

## C-012 — formal verdict

### Auditor claim (short quote)

“runner تا ابد همان cursor را ... retry می‌کند” — persistent rate-limit responses cause uncapped retries at the same cursor. The full row distinguishes bounded walk retries from the outer loop, capped delay from capped attempts, and successful-page budget from request/time budget. Full row read from `/tmp/AUDIT.md`. Auditor S1.

### What I read (files, line ranges, functions, callers)

Full ToobitKlineSource including __call__, backward walk, _get_klines_with_walk_backoff, _get_klines and AsyncBridge (bootstrap_service.py:245–818); entire frozen research/bootstrap.py:1–438 including command/pause/resume/run_phase1; full service caller/exception/report/checkpoint closure described under C-008/C-010. Direct frozen client constructor/session/_get/get_klines (toobit_public.py:174–295) and wire parser (122–172) reviewed, without constructing a network client. Checkpoint DDL/bootstrap methods: checkpoints.py:1–203. Consumers: `remaining-consumers.out`. Complete referenced persistent-limiter test (bootstrap tests:228–244), finite-recovery runner test and fixture (research tests:206–245), no-rewind/pause tests (246–280) read. CLI/bootstrap caller already read under C-002.

### Reproduction (command, probe file, actual result)

`PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V1a/C-012.py`; raw `C-012.out`, exit 0. Native service, runner, source, AsyncBridge, actual checkpoint/canonical writes and frozen parser/store recovery. Async venue double raises ToobitPublicError with **code=-1003** or **HTTP 429**. Inner retry tuple `(0,0,0)` preserves four attempts per walk while removing real delays; outer delays `.01,.02,.03` preserve last-slot saturation. Source max_pages=1.

On the repository-DDL **200,000 market + 200,000 raw-row** fixture, repeat each refusal with neither/both supplied device indexes:

- At 0.32 seconds, all four scenarios still run: **48 client calls = 12 outer backoffs × 4 inner attempts**, **0 source pages**, zero ingested bars; checkpoint **IN_PROGRESS** at the original cursor `1788220800000`.
- Explicit native `runner.command('pause')` ends the -1003 case and saves **PAUSED** at the same cursor. The loop is not claimed unstoppable.
- Explicit task cancellation ends the 429 case during an async backoff; checkpoint remains **IN_PROGRESS**, same cursor, zero bars. This is external audit cancellation, not a production retry timeout or automatic PAUSED state.
- Fresh service/source on each same checkpoint, with the refusal removed, ingests **all three** fixture bars and returns **COMPLETE**, cursor `1788220980000`, two client calls for the backward walk. Recovery is measured once per action (without device indexes); both index configurations independently reproduce uncapped refusal behavior.

Captured refusal-path SQL: per-cell frontier `MAX(as_of)` uses **covering idx_raw_sym_tf_asof SEARCH** in both modes; no unindexed large-table scan occurs here. No market/PIT query is needed for a rejected page. The index pair cannot cap a Python retry loop. Recovery ingest/checkpoint behavior is native; its detailed SQL plan coverage is in C-010 rather than falsely presented as traced here. No model, order, secret, real venue rate limit or battery drain.

Guarded `python3 -m pytest -q -p no:cacheprovider tests/unit/test_ops_bootstrap_service.py::TestKlineSource::test_rate_limit_surfaces_when_walk_retries_exhaust tests/unit/test_research_bootstrap.py::TestPhase1::test_rate_limit_backs_off_and_never_skips`: **2 passed in 0.30s**, `C-012-pytest.out`; native and pytest guard attempts **[]**.

### Verdict and reasoning

**CONFIRMED / S1.** Bounded observation plus complete loop reading proves there is no intrinsic attempt/deadline termination while rate limits persist. A finite experiment cannot literally observe infinity; it demonstrates repeated outer cycles beyond the inner bound and then is deliberately terminated. No device/network duration is extrapolated from scaled delays. Explicit pause/stop checks do exist, and asynchronous backoff is cancellable; lack of an automatic bound is not lack of all control mechanisms.

### Root cause

Source returns -1003 after exhausting its own attempts without incrementing pages_served. Runner increments backoffs, selects `backoff_seconds[min(count-1,last)]`, awaits that delay, and continues without advancing cursor or successful-page count. A saturated delay is not a global retry budget. A fresh source call begins another walk. The public client's own finite retry layer can add attempts underneath this loop but cannot terminate the outer one.

### Direct impact

Persistent throttling can keep acquisition pending indefinitely despite max-pages=1, with no completed-page progress and no automatic named retry-later result. Existing durable cursor is retained. Real request load/time depends on client, walk and outer delay settings; the 48 synthetic **client-method** calls are not claimed to be 48 actual HTTP requests.

### Secondary effects and interactions (upstream/downstream)

C-008 full backward walks may restart after a failed walk because no completed history is cached; traffic budget must include partial walks. C-010 resource checks stay stale during those repeated retries. Normal control routing must remain reachable during synchronous bridge/walk sleeps; the probe only proves controls during async outer waits, not production Telegram responsiveness.

**ISSUE-076:** ingestion/backfill costs follow a successful page; no data replay or row batching cap ends the rate-limit branch. **ISSUE-077:** lack of progress resembles that symptom but is not the DB-lock/ladder or gather cause; explicit persisted pause should not be confused with cancellation leaving IN_PROGRESS. **ISSUE-079:** fingerprint joins are unrelated to this refusal loop; reducing their latency will not change retry termination. No new X finding is assigned.

### Contract and decisions

APEX_GEN5.md:17276 requires “−1003 backoff, do not skip”, page checkpoints and resume-never-rewind; W.8 requires owner controls/persistent state. It does **not** mandate infinite retry in one invocation or give a numeric total retry cap. PHASE2_DECISION_LOG.md:176 authorizes bounded **walk-internal** backoff and runner-facing max-pages, not a global HTTP cap; CP13 frontier semantics remain later authority. A named resumable pause at unchanged cursor is consistent with never-skip; marking the cell COMPLETE/SKIPPED or advancing its cursor on throttle is not.

### Frozen status and non-frozen alternative

Outer runner and public catalog client are frozen. A change there needs owner permission. Service/source wrappers are non-frozen and can enforce an end-to-end wall/attempt budget, issue an existing pause command and preserve a pending cursor, with a named owner-facing reason. Retry-After exposure may require an authorized frozen-client change if no current interface carries it; do not pretend the string-only marker already provides headers.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

**A — governed global attempt/elapsed-time budget and named resumable pause in non-frozen wiring.** Count all relevant attempt layers, scope/reset explicitly by run/cell/progress, surface reason and retry-not-before without returning a fake empty success page. Existing PAUSED/checkpoint payload can represent state without changing frozen status enums; new durable policy metadata may need versioning, not raw data migration. Cancellation must not leave bridge work writing/publishing after its generation is obsolete. Adds counters/telemetry and possible scheduling delays; finite transient-recovery tests must remain valid below the cap, persistent-source tests should now assert bounded pause and same cursor.

**B — externally bounded jobs with fresh service restart at durable cursor.** No frozen edit and possibly no schema change; can bound process duration but wastes partial backward walks, loses process-local diagnostics and does not automatically produce a clean PAUSED receipt. Requires a supervisor, explicit termination/report policy and no concurrent writers. Safer than unbounded unattended retry but not complete in-process handling.

Reducing sleep to zero or skipping a throttled cell is not an acceptable fix. Global budgets must respect venue cooldown rather than amplify a 429 storm. No training/model changes or retraining are required; successful recovered rows, content hashes and PIT availability must remain identical. Preserve dedup, correction lineage and CP13 frontier semantics; never forge availability timestamps to disguise retry latency.

### My recommendation

A, using existing pause semantics and explicit audit reason; define budget/cooldown with owner approval rather than invent a numeric SLA. Keep bounded walk retries as a separate local defense and test the full layered path.

### Acceptance and regression tests

Always-limited -1003 and 429 fixtures must reach named resumable PAUSED/RETRY_LATER within the configured whole-invocation budget, with unchanged cursor and no false COMPLETE. Remove the limit and verify all rows exactly once after restart. Test pause, stop, cancellation during async waits and synchronous bridge activity, partial-walk recovery, Retry-After where exposed, and resource-pressure interaction. Keep native ≥200k-store frontier plans in both modes; no device throttle duration or battery impact is certified here.

## C-013 — formal verdict

### Auditor claim (short quote)

“_p1_lane صف بدون maxsize است” — P1 is an unbounded queue. The full row alleges shared-lane eviction does not bound it, the existing NFR probe misses P1/slow consumers and the 500-item feature/evidence queue, and device consumption/latency was not measured. Full row read from `/tmp/AUDIT.md`. Auditor S1.

### What I read (files, line ranges, functions, callers)

Complete apex/bus.py:1–241 (events/identity creation, subscriptions, all priority paths, eviction, dispatch/start/stop, metrics and RawCandleQueue); complete scripts/run_nfr_harness.py:1–277 including queue probe and aggregate/printed verdict; complete tests/unit/test_bus.py:1–150 and test_ai10_nfr_harness.py:1–end. Direct composition/collector Runtime.start/stop (run_apex.py:145–181), full FSM publisher (fsm.py:506–528), boot publication (1055–1063; complete containing boot method previously read for C-002), scheduler publication/call chain already read for C-006, and complete SignalingPlane.send (signaling.py:666–784) to distinguish transport from bus observation. Consumers grep: `C-013-consumers.out`. This is not a claim to have re-audited all Telegram internals or frozen engine formulas.

### Reproduction (command, probe file, actual result)

`PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V1a/C-013.py`; raw `C-013.out`, exit 0. Native EventBus, event factory, **real dispatcher and asynchronous consumer**, RawCandleQueue and the original imported `_queue_bounds_probe`. No network, transport, orders or AST extraction.

1. With lane_maxsize=10, retained P1 queued events grow **1,000 → 2,000 → 4,000**, after GC traced heap delta **1,506,646 → 3,028,638 → 6,073,006 B**; shared queue stays zero. Actual `_p1_lane.maxsize=0`. Each payload includes about 1 KiB of unique text. No dispatcher in this growth subcase, explicitly; this models backlog, not a post-drain memory leak.
2. With dispatcher running and a 40-ms async P1 consumer, enqueue **75 P1** then one P2; queue snapshot P1=75 despite bound=10. All **75 delivered FIFO**, zero evictions. Last P1 starts **2.981292 s** after publication, completes **3.021564 s**; **25** P1 events wait over two seconds even before their consumer starts. P2 starts after **3.021482 s**. A concurrently published P0 completes inline in **0.000030 s** with its deliberately fast consumer. This is local queue/consumer latency, not Telegram transmission latency or a phone benchmark.
3. Shared control: 15 P2 at capacity 10 yields queue 10, evicted 5. Raw control: 1001 inputs at capacity 1000 yields queue 1000, one drop, oldest remaining item 1. These bounds do work.
4. Publishing 501 P2 messages under a feature/evidence topic to the generic bus returns without backpressure and leaves 501 queued under capacity 1000. This does not invent or prove wiring of an independent feature output queue; it shows this API is not that distinct 500-item blocking queue.
5. Original native NFR queue probe still reports **bounded=true, P0 delivered 2000/2000, shared queue 1000, P2 evicted 100**. Its own workload publishes **no P1**, starts no dispatcher, and measures no P1 latency.

This row's operations issue **no SQLite queries** and have no per-cell/per-row database path. Repository DDL/200k corpus and device-index EXPLAIN are therefore **not applicable**, not omitted measurements of a hidden SQL path. The neighboring rows contain actual 200k-store comparisons where SQL is causal.

Guarded command: `python3 -m pytest -q -p no:cacheprovider tests/unit/test_bus.py tests/unit/test_ai10_nfr_harness.py::TestBounds tests/unit/test_ai10_nfr_harness.py::TestTNFR004QueueBounds::test_p0_delivery_is_synchronous_not_buffered`; **12 passed in 0.08s**, `C-013-pytest.out`. Both guards **[]**. The full NFR harness/order-latency fixture was deliberately not invoked; only its queue probe and no-order tests ran.

### Verdict and reasoning

**CONFIRMED / S1.** The P1 lane has no intrinsic capacity or publisher backpressure. Evicting a different queue does not free a bounded P1 slot; after that queue empties P1 still accumulates. The real dispatcher counterexample establishes local latency >2 seconds under a declared slow-consumer workload, beyond the auditor's enqueue-only reproduction. It does not prove a production Telegram alert missed its SLA: the current Runtime subscriber is an in-memory collector, and signaling publishes its bus receipt **after** transport, rather than using this lane as its outbound message queue.

The published T-NFR-004 test mix really is 2000 P0 + 1000 P2; implementing that narrow mix is not falsification. Treating its PASS as proof of **all** queue/capacity/P1 guarantees is the coverage gap. Device capacity remains unverified.

### Root cause

An asyncio.Queue without maxsize accepts unlimited P1 puts. `_lane_maxsize` only triggers best-effort shared eviction. Dispatch awaits each subscriber serially and drains P1 preferentially; no admission-rate bound, per-consumer deadline or durable overflow path controls backlog. Deque eviction diagnostics already have a 4096 bound and are not an unbounded structure in this row. Successfully drained queues release events; the defect is unbounded backlog under insufficient service, not retention forever after delivery.

### Direct impact

Growing queued-event memory and P1/P2 observation delay under overload or a slow subscriber. P1 is not silently dropped by the measured queue path; making it bounded must not replace that property with silent loss. No actual capital loss, target-device OOM or Telegram transport delay is observed.

### Secondary effects and interactions (upstream/downstream)

FSM noncritical transitions and non-recovery boot events publish P1; their await currently means enqueued, not all subscribers completed. Runtime's collector then keeps delivered events (C-003), so draining the queue does not fix that independent history growth. A blocking P1 publish could stall FSM advancement if consumers rely on work that the publisher still holds, requiring deadlock/lock-order tests. P0 bypasses dispatcher, but inline slow consumers can still delay its caller; the fast P0 control does not prove universal zero delay.

**ISSUE-076:** heavier replay/backfill traffic may increase workload but SQL indexes/commit batching do not bound P1. **ISSUE-077:** an unyielding/stalled analytical driver or DB consumer can reduce service; gather/cursor persistence is a distinct failure mechanism. **ISSUE-079:** synchronous fingerprint/preparation work can starve the same event loop, making backlog/latency worse; fixing that join is necessary for throughput but not a queue admission policy. No separate new X finding is claimed.

### Contract and decisions

APEX_GEN5.md:18891–18901 defines inbound raw 1000/drop-oldest, feature/evidence output **500/blocking producer**, synchronous ledger, dedicated P0/P1, P0 never dropped/delayed and P1 transmitted within **2 s**. T-NFR-004 at 19133 prescribes the narrow P0/P2 mix; release rule at 19146 requires target-device/headroom acceptance. The specific raw and feature policies must not be flattened into one generic drop-oldest queue. Reviewed decision-log/consumer search found no later owner permission to discard P0/P1 or treat shared-lane size as all-queue acceptance. User frozen-path instructions govern edit permissions even though the harness docstring casually calls the bus frozen.

### Frozen status and non-frozen alternative

apex/bus.py and the harness are **not** in the user's frozen set. Fix via non-frozen bus/composition/supervisor boundaries and additive durable outbox/journal if selected; frozen engine producers/catalog/research need not change. Preserve the in-process asyncio bus contract rather than introduce a networked broker as an unapproved workaround.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

**A — governed admission/capacity, bounded P1 work, explicit latency/escalation and durable overflow where appropriate.** Keep P0 inline and no silent P1 loss; separately provision the actual feature/evidence 500-item blocking queue and raw queue. A bounded queue alone cannot guarantee a two-second deadline under an arbitrarily slow consumer: arrival/service capacity, consumer isolation and timeout/escalation must be specified. Durable overflow adds disk/serialization overhead, restart/dedup and possibly an additive schema; it prevents loss but does not by itself make late delivery timely. Maintain one writer/ordered identities, and avoid deadlock when publisher and consumer share locks.

**B — subscriber isolation and realistic admission-rate limits plus truthful NFR reporting first.** Can reduce stalls and expose overload with no required migration, but an unbounded queue remains a resource risk if the limit is not enforced. Unrestricted parallel dispatch breaks per-lane/subscriber order; use explicit ordered partitions if approved. Never drop/coalesce critical events merely by topic without a governed semantic equivalence rule.

Existing `test_p1_never_dropped_evicts_shared` explicitly expects two P1 entries at capacity one and no blocking; a correct capacity/backpressure policy must replace that expectation with deterministic completion/backpressure assertions, while FIFO, no-loss, raw drop-oldest and synchronous P0 controls remain. Transport idempotency/restart identities must survive any spill/retry; UUID event identities are operational, not snapshot hashes. Pure queue plumbing requires no retraining and must not alter model inputs/decisions or canonical historical hashes. Changed delivery ordering can affect upstream/downstream scheduling and must be parity-tested, not assumed harmless.

### My recommendation

A, retaining truthful separation between enqueue, consumer completion and actual transmission. Extend T-NFR-004 instead of claiming the current narrow PASS closes P1/feature-output/device acceptance. Owner-approved overload/escalation policy is necessary where finite resources, lossless preservation and strict timeliness conflict.

### Acceptance and regression tests

Keep actual-dispatch slow-consumer tests, growth samples and P0/P2/raw controls. Test bounded P1 publication, no loss/duplicate IDs, FIFO or explicitly approved ordering, cancellation/shutdown, spill/restart, queue-full escalation, deadlock freedom and downstream latency. Exercise the **real wired** 500-item output queue with blocking producers, not just a topic name, and separately measure send receipts. Run target-device burst/sustained capacity and 30% headroom tests before acceptance; no finite queue test can certify arbitrary unbounded load.

## New findings not in the audit

**None established at mandatory depth; no X-V1a IDs assigned.** Confirmed mechanisms are attributed to the eight retained audit rows and the explicitly linked owner issues, not counted again as new findings. Other source/test observations outside the retained scope are not promoted without their own complete verification and duplicate review. No verification of the nine V1c rows is implied.

## Rows not verified or incomplete

Retained rows: **none unverified**. Device performance acceptance is not asserted; see individual limitations.

**Reassigned to V1c:** C-001, C-005, C-007, C-009, C-011, C-014, C-015, O-006, V-003. No V1a verification or verdict on these nine IDs.

Completed rows have twelve-heading formal sections and native offline evidence. Full test-suite or real-device readiness is not certified. Read coverage is itemized per row; execution of a test file is not represented as a complete line-by-line review of every unrelated test.

## Final counts

- CONFIRMED: **8** — C-002 S0; C-006, C-003, C-004, C-008, C-010, C-012, C-013 S1
- PARTIAL: **0**
- REJECTED: **0**
- DEVICE-EVIDENCE-NEEDED: **0**
- Retained unverified: **0**
- Reassigned to V1c: **9**
- Established new findings: **0**

Final scope check: only `AUDIT/` differs from source baseline `85b2c155d7b054a468379ddfd802eb239d0801f9`. Native corpus evidence is synthetic, using repository DDL. SQL paths have both specified device-index configurations; C-013 is a no-SQL bus path. No repair/apply, real orders, exchange/Telegram contact, secret or repository `data/` access was performed. Existing C-006 tests had six DNS attempts blocked by the audit guard, as disclosed in that section; the four final-row native probes and their targeted pytest runs recorded zero guard attempts.
