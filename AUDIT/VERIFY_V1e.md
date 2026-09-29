# Independent Verification V1e — Execution FSM and venue adapter

Baseline verified: `85b2c155d7b054a468379ddfd802eb239d0801f9` (`85b2c15 Merge pull request #25 from sinamoosazadeh/arena/01a0d98b-upstage`). Verification date: 2026-09-29 UTC. This verification uses real repository code with synthetic inputs and temporary/in-memory SQLite only; it neither proves real-device/database/model behavior nor contacts an exchange or Telegram.

## Summary

| ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option |
|---|---|---:|---:|---|---|---|
| E-001 | CONFIRMED | S1 | S1 | No | D58 (separate simulator scope); X-V1d-002 | A: durable non-terminal lifecycle registry |
| E-002 | CONFIRMED | S1 | S1 | No | — | A: reconstruct/hydrate before READY |
| E-004 | Pending | S1 | Pending | No | — | Pending |
| E-005 | Pending | S1 | Pending | No | X-V1d-002 | Pending |
| E-006 | Pending | S1 | Pending | No | D58; X-V1d-002 | Pending |
| E-007 | Pending | S1 | Pending | No | X-V1d-002 | Pending |
| E-008 | Pending | S1 | Pending | No | — | Pending |
| E-009 | Pending | S1 | Pending | No | — | Pending |
| E-010 | Pending | S1 | Pending | No | — | Pending |
| E-011 | Pending | S1 | Pending | No | — | Pending |

## E-001

### Auditor claim (short quote)
“After three polls without a fill the FSM is not retained in `working`; only fills are added, and the run path never applies timeout or recovery.”

### What I read (files, line ranges, functions, callers)
I read the full reported row from `/tmp/AUDIT.md:194`, `apex/execution/fsm.py` (1–1362; especially `ExecutionFSM.submit`, `apply_adapter_result`, `check_timeouts`/`apply_timeouts` at 530–668), `apex/ops/paper_loop.py` (1–1192; `PaperRuntime.__init__` 351–410, `execute_plan` 692–745, `_observe_fill` 762–801, `run_cycle` 956–1064), and the required complete test/fake files named in the scope. The mandatory consumer search `grep -RInE 'ExecutionFSM|apply_timeouts|working|execute_plan|manage_positions' apex tests scripts` located production construction only in `paper_loop.py` and the demo script; `run_cycle` calls `manage_positions`, but neither calls `apply_timeouts` or a recovery API for an unfilled entry. The direct relevant test is `tests/integration/test_ops_paper_loop.py:480–500`, whose name says “stays working” but asserts `working == {}`. I also read V1b’s E-003 and V1d’s X-V1d-002 sections: the former establishes the real accepted literal is `NEW`; the latter establishes cached duplicate markers are ignored by `apply_adapter_result`.

### Reproduction (command, probe file, actual result)
`python3 -u -B AUDIT/probes_V1e/E-001.py` (raw `AUDIT/probes_V1e/E-001.out`) runs the real `PaperRuntime`, `ExecutionFSM`, `ToobitAdapter`, SQLite store/ledger and repository fake responder against a temporary database. It reports `submit_outcome ACKNOWLEDGED`, `poll_query_count 3`, `fsm_state ACKNOWLEDGED`, `adapter_order_status NEW`, and `working_keys []`. Thus the venue has an accepted working order after all polls while the runtime has lost its machine. Focused existing test command `python3 -m pytest -q -p no:cacheprovider tests/integration/test_ops_paper_loop.py -k 'unfilled_entry_stays_working or matching_boot_reaches_ready_with_open_intents'` is saved as `E-001_E-002-pytest.out`: `1 passed, 22 deselected`; it proves the erroneous empty-working assertion is currently accepted, not safety. This synthetic test-double result proves repository control flow only, not actual venue/device behavior.

### Verdict and reasoning
**CONFIRMED, S1.** `execute_plan` retains a machine only in the `if observed.get("filled")` branch. Its unfilled, acknowledged branch returns an ordinary trade record and leaves the accepted order outside all future runtime state; neither the poll loop nor the cycle timeout/recovery path subsequently owns it. An unknown or delayed venue outcome is therefore not reconcile-first in the long-running composition root. S1 is appropriate for an untracked possible order/exposure, but not S0: boot itself remains fail-closed and the defect needs a submitted accepted order that does not fill in the three immediate polls.

### Root cause
The `working` collection is used as a managed-position collection rather than the contract’s non-terminal intent registry. `execute_plan` creates the FSM locally, performs bounded polling, and discards it unless a fill was observed; `run_cycle` has no independent persistent order/work queue or timeout sweep.

### Direct impact
A `NEW` entry can remain at the venue after the third poll while no in-process FSM applies `FILL_TIMEOUT`, queries it, cancels it, reconciles it, or records a later fill. A restart does not repair that in-memory loss (E-002).

### Secondary effects and interactions (upstream/downstream)
Upstream, this requires accepted entry state and a delayed/no fill. Downstream it can produce unrecorded exposure, absent protection after a later fill, ledger/venue divergence, duplicate materialization pressure and invalid accounting/training outcomes. It is independent of the D58/CP-15 missing PAPER simulator: D58 explains why the current PAPER transport is incomplete, while this finding is a runtime lifecycle loss even with the present adapter/fake surface. V1d X-V1d-002 worsens a retry path because an identical cached ACK is indistinguishable to the FSM. No real fill, exchange, model, database scale or device result was tested.

### Contract and decisions
Binding `APEX_GEN5.md:16874–16880` says reconciliation is “a first-class invariant, not a background task” and divergence forces `RECOVERY_REQUIRED`; `16898–16904` requires partial until fill timeout ⇒ recovery; `16958–16962` requires working orders reconstructed before trading resumes. The adapter contract at `16972–16983` makes UNKNOWN reconcile-before-action and says timeouts force `RECOVERY_REQUIRED`. Later D50 (`PHASE2_DECISION_LOG.md:1159`) requires a duplicate id never be resent and preserves the recorded outcome. D58/CP-15 is a known separate simulator gap, not an override of these lifecycle requirements. Contract plus later D50 govern; no later owner ruling permits dropping an ACKNOWLEDGED order.

### Frozen status and non-frozen alternative
`apex/ops/paper_loop.py` and `apex/execution/fsm.py` are not in the supplied frozen-file list; frozen Ch.16 state values and D50 identity must not change. A non-frozen runtime-owned durable intent/work registry or ledger-derived adapter layer can implement the fix without touching engines, data catalog, original YAMLs, research frozen files or `requirements.lock`.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A (recommended):** retain every non-terminal FSM in a durable work registry immediately after submit; on each cycle query/reconcile it and call `apply_timeouts`; remove only on terminal reconciled state. Side effects: restart restoration must be added with E-002; `working` changes from positions-only to order-plus-position state; test expectations and notifications change; no identity/hash or schema migration is required if ledger records are the source, but an added table would require migration. **B:** make `execute_plan` synchronously block until terminal. Rejected: it can stall cells and still loses crash recovery. **C:** cancel after exactly three polls. Rejected: a cancellation result can also be UNKNOWN and must be reconciled; it changes governed timeout semantics.

### My recommendation
A, combined with E-002 reconstruction and an explicit persistent state model (`entry-working`, `partial`, `managed`, `recovery`) rather than a fill-only dictionary.

### Acceptance and regression tests
A real FSM/adapter/fake test must show ACK→three `NEW` polls remains durable and is queried on the next cycle; timeout transitions exactly once to `RECOVERY_REQUIRED`; a later `FILLED` query writes one fill then installs protection; UNKNOWN never disappears; a restart restores the order without re-submission. Existing submit/fill tests and D50 identical-retry behavior must remain valid.

## E-002

### Auditor claim (short quote)
“Driver construction starts `working={}`; boot returns open intents but does not turn them into managed FSMs or load prior positions.”

### What I read (files, line ranges, functions, callers)
I read the full row at `/tmp/AUDIT.md:195`, the complete mandatory scope files, and `PaperRuntime.__init__/boot` (`apex/ops/paper_loop.py:351–430`) together with `StartupReconciliation.reconcile_boot` (`apex/execution/fsm.py:1163–1218`). The caller search described in E-001 found `PaperRuntime.boot` is the production runtime bridge and that only `run_cycle` later calls `manage_positions` over `self.working`; no caller hydrates `_open_intents` into FSMs. `tests/unit/test_execution_fsm.py` boot tests confirm that startup reports open intents but do not test runtime restoration. V1b/V1d were read first as instructed; their cited facts are used without repeating their E-003/E-016 verification.

### Reproduction (command, probe file, actual result)
`python3 -u -B AUDIT/probes_V1e/E-002.py` (raw `AUDIT/probes_V1e/E-002.out`) uses the real `PaperRuntime.boot`, `StartupReconciliation`, real adapter/ledger/temporary SQLite and a fake responder seeded before adapter construction. Actual result: `boot_state READY`, `reconcile_agree True`, `open_intents ('i-prior',)`, `runtime_working []`, `prior_order_status NEW`. The same focused pytest invocation/output is `AUDIT/probes_V1e/E-001_E-002-pytest.out`; it does not cover runtime hydration. The fake venue and empty temporary ledger demonstrate this code path, not actual account state or restart behavior on a device.

### Verdict and reasoning
**CONFIRMED, S1.** A clean boot can declare READY even while its reconciliation result contains an existing working venue order. `PaperRuntime.boot` stores only `boot_verdict`, then cursor/ladder data; its independently initialized `working` remains empty. Because `manage_positions` iterates that collection, the prior order/any reconstructed position has no long-run owner. The contract’s reconstruct-before-trading language is not met merely by returning IDs in a diagnostic dict.

### Root cause
`StartupReconciliation` gathers open client IDs as diagnostics only. It has no state/plan/fill/protection reconstruction interface, and `PaperRuntime` does not consume `reconciliation.open_intents` or ledger state to build machines before setting trading availability.

### Direct impact
After a restart, an acknowledged entry, partial order, or managed position can be absent from runtime management despite boot becoming READY. Stops, targets, time exits, timeout/reconcile handling and later outcome tracking cannot be driven by the process that just booted.

### Secondary effects and interactions (upstream/downstream)
E-001 turns a normal in-process unfilled order into precisely this restart class. E-004 partial-fill/protection problems, E-005 residual exits, E-006 management behavior and E-010 incomplete boot matching all become harder to correct if identity/state is not reconstructed. New entries can compete with hidden prior orders, disturbing risk/exposure, ledger accounting, replay and training labels. The synthetic response cannot establish the real database’s recoverable lineage or device order set.

### Contract and decisions
`APEX_GEN5.md:16958–16962` is explicit: “After any crash or restart, open positions and working orders are reconstructed from the exchange before trading resumes” and no new trade precedes READY. Ch.23 `18246–18250` directs boot to reconcile open positions, working orders and recent fills before normal execution; AI.9 `18894–18903` says any failed recovery check halts. D50’s persistent intent identity and durable per-cell lock (decision log `1159`) reinforce stable identity, but do not replace runtime reconstruction. No later decision overrides the contract, which has precedence.

### Frozen status and non-frozen alternative
The affected runtime/FSM files are non-frozen under the supplied list; preserve frozen state vocabulary, Ch.16 DDL and D50 content identity. A non-frozen reconstructor in `paper_loop` can derive machines from ledger + queried venue records. If data not carried by the ledger (protection/order linkage) is needed, an additive runtime table/migration is an alternative, with migration/backfill implications.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A (recommended):** fail boot READY unless every open intent/position is reconstructed from ledger lineage and exchange state into a durable runtime record, then hydrate `working`; unresolved records remain `RECOVERY_REQUIRED`. Side effects: boot may now pause current clean-but-unlinked historical rows; tests expecting READY with `open_intents` need new state fixtures; no hash invalidation, but an additive persistence schema needs migration. **B:** do not become READY whenever any open order/position exists; require manual recovery. Safer and simpler but loses autonomous recovery. **C:** reconstruct only `MANAGED` positions. Rejected: it abandons ACK/PARTIAL timeout and protection paths.

### My recommendation
A, sequenced with E-001-A: one durable lifecycle registry reconstructed at boot and used in every cycle.

### Acceptance and regression tests
Seed ACKNOWLEDGED, PARTIAL, FILLED/PROTECTED/MANAGED and RECOVERY_REQUIRED lineage plus matching fake venue records; restart must hydrate exactly one object per intent, make no duplicate POST, and query/reconcile each correct state. Missing plan/protection/fill lineage, rejected query and mismatched quantity must leave boot non-READY. The existing clean boot and no-adapter fail-closed tests must continue passing.

