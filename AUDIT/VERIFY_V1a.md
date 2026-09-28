# V1a independent verification — INCOMPLETE CHECKPOINT

ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option
--- | --- | --- | --- | --- | --- | ---
C-002 | INCOMPLETE — no verdict | S0 | Not assigned | Reviewed composition/adapter/FSM paths are non-frozen | = ISSUE-075; = user-provided D58 (see naming caveat below); related ISSUE-077/078 | Finish verification; do not add network transport to PAPER
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

**This is not completion of the requested 17-row verification.** INCOMPLETE/NOT VERIFIED are workflow labels, not additional audit verdicts. No row meets the entire mandatory-depth checklist yet. Narrow reproducible evidence for C-002 is preserved below rather than promoted to a completed verdict. No claim of complete source/caller/callee reading, test coverage, device acceptance, or measured performance verification is made.

Baseline was checked before any repository work: `85b2c155d7b054a468379ddfd802eb239d0801f9`; `git log -1 --oneline` returned `85b2c15 Merge pull request #25 from sinamoosazadeh/arena/01a0d98b-upstage`. Work remains on `arena/01a0e911-upstage`. Input was fetched by the supplied SHA `690e2d8899319a7c7a96456f92c3008878e59346`, without checking it out. Its full report was read for C-002 from `/tmp/AUDIT.md`; the saved full row and input digest are in `probes_V1a/provenance.out`. The report at `015d19bd6ec1956b853fd566157a929f9f95f260` was not separately compared; the supplied combined-fetch procedure was used.

Dependencies were installed successfully with the requested lockfile and pytest; `dependencies.out` is empty because quiet pip succeeded without diagnostics. The native probe reports NumPy 1.26.0. No pytest suite has been run. Only new AUDIT files were authored. No CLI `main`, `_boot`, or `_serve` was executed, no device database/model inspected, no order submitted, no exchange/Telegram endpoint contacted, no `.env` loaded and no actual credential used. Probe configuration is an actual `Config` instance with only a synthetic dictionary assigned, deliberately bypassing its environment loader. Audit hooks reject network operations and `.env`/repository `data/` access; the probe records zero blocked attempts. GitHub fetch/push is separate from application network activity.

## C-002 — partial evidence only

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

## New findings not in the audit

None established at mandatory depth. No X-V1a IDs assigned. The limited ledger SCAN observation and decision-label caveat above are retained as follow-up notes, not promoted to completed new findings. Full audit duplication checks have not been performed.

## Rows not verified or incomplete

All 17: **C-001, C-002, C-003, C-004, C-005, C-006, C-007, C-008, C-009, C-010, C-011, C-012, C-013, C-014, C-015, O-006, V-003**.

C-002 has native partial reproduction, but incomplete mandatory source/caller/callee/contract closure, pytest, fix-impact and full boot/serve tracing. The other 16 have no independent row verification. Index severity extraction is not verification. Required measured reproductions for C-003/C-004/C-006/C-008/C-010/C-012/C-013, the C-006 ↔ ISSUE-079/gather analysis, and the other specified complete files/tests remain outstanding. No coverage claims are made. This checkpoint must not be used as a completed audit or an operational readiness sign-off.

## Final counts

- CONFIRMED: **0**
- PARTIAL: **0**
- REJECTED: **0**
- DEVICE-EVIDENCE-NEEDED: **0**
- Incomplete/not verified: **17** (C-002 partial evidence; 16 unverified)
- Established new findings: **0**
