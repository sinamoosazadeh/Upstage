# Independent Verification V1b — Execution FSM, Venue Adapter, Order Lifecycle

Baseline: `85b2c155d7b054a468379ddfd802eb239d0801f9`. Verification date: 2026-09-28. Synthetic/fake results below do not establish behavior on the real device, database, model, or venue.

## Summary

| ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option |
|---|---|---:|---:|---|---|---|
| E-003 | CONFIRMED | S0 | S0 | Yes (`apex/execution/fsm.py`) | none | A: invoke a real fail-closed emergency-close coordinator |



## E-003

### Auditor claim (short quote)
“Protection-installation failure only creates an event and transitions to `RECOVERY_REQUIRED`; emergency flatten is not executed.”

### What I read (files, line ranges, functions, callers)
I read `apex/execution/fsm.py` completely (1–1362), particularly `ExecutionFSM.advance`, `submit`, `apply_adapter_result`, and `place_protection` (476–756); `apex/execution/toobit_adapter.py` completely (1–905), particularly immutable transport construction and `_execute` (319–725); the order/fill/position/protection portions of `apex/ledger/store.py` (385–390, 573–643, 763–868); `apex/ops/paper_loop.py` execution callers (692–870); `scripts/run_apex.py` demo caller (331–359); `tests/fake_toobit_responder.py` completely (1–410); and both protection tests at `tests/unit/test_execution_fsm.py:897–941`. Mandatory consumer search (`grep -RIn 'ExecutionFSM|PROTECTION_FAILED|install_protection|protection' apex tests scripts`) found production callers only in `paper_loop.py` and `run_apex.py`; neither consumes `emergency_path` by issuing an exit. `protection_failed_event` only returns descriptive fields.

### Reproduction (command, probe file, actual result)
`python3 AUDIT/probes_V1b/E-003.py` uses the real FSM and adapter with the repository fake responder constructed up front. Raw output is `AUDIT/probes_V1b/E-003.out`. Injecting business code `-1022` for the STOP produced adapter `REJECTED`/`ok=False`; `place_protection` returned `protected=false`, state `RECOVERY_REQUIRED`, and a descriptive emergency path. Three POSTs were observed: entry LIMIT, rejected STOP, and target LIMIT. There was **no fourth flatten POST**. Thus the prior suggestion that a rejected stop is reported protected because `ok` means classification success is refuted: `ok` is true only for `CODE_OK`. The accepted-order venue literal is `NEW`; adapter maps it to `ACKNOWLEDGED`. The focused existing test command in `E-003-pytest.out` passed (`1 passed`), but it merely asserts the returned label/event/state and does not assert a flatten request.

### Verdict and reasoning
**CONFIRMED, S0.** The contract requires an actual market close when protective cover cannot be established. Real code only records/escalates that requested action. The business-rejection variant correctly enters failure rather than falsely reporting protection, but still leaves the target working and performs no flatten. This can leave real exposure uncovered; that blocks safe operation. `X-V1b-001` is not opened because its stated predicate is disproved.

### Root cause
`place_protection` treats `protection_failed_event(...)["action"]` as a report value, not an executable command. No injected emergency coordinator/callback exists. It also submits the target after stop rejection and has no cleanup transaction.

### Direct impact
After an entry fill and failed stop placement, the FSM reaches `RECOVERY_REQUIRED` without reducing exposure. `PaperLoop.manage_positions` handles only `MANAGED`, so this machine receives no ordinary exit management.

### Secondary effects and interactions (upstream/downstream)
Upstream causes include business rejection, unknown response, or either leg failing. Downstream, the ledger and P0 signal can imply escalation while venue state still contains exposure and possibly one orphan protective leg; restart/reconciliation must discover it. Order identity, fill accounting, outcomes, risk budgets, and training labels remain incomplete. This synthetic fake-venue result proves control flow, not real venue behavior or device alert delivery.

### Contract and decisions
Binding `APEX_GEN5.md:17078–17080`: “If the stop protection fails to place (PROTECTION_FAILED), the position is closed at market by the Playbook emergency path and the event escalates to the OWNER.” `APEX_GEN5.md:19002` likewise requires watchdog/emergency close when protective cover cannot be established. `PHASE2_DECISION_LOG.md:150` (ISSUE-CP7-005) governs STOP/GTC/reduce-only wire fields but does not waive emergency close. No later decision overrides the close requirement; the contract therefore governs.

### Frozen status and non-frozen alternative
`apex/execution/fsm.py` is frozen. A direct fix needs explicit owner ruling. A non-frozen alternative is an execution coordinator in `apex/ops/paper_loop.py` that consumes a typed failure result and performs reconcile → cancel surviving protection → reduce-only emergency exit through the existing adapter, while globally blocking admission. This must not mutate adapter transport or bypass FSM authority.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A (recommended):** owner-approved frozen-FSM callback/coordinator protocol, durable saga states, and idempotent cleanup/flatten. Side effects: transition fixtures and hashes of serialized FSM evidence change; existing tests expecting only three operations need extension; ledger migration may be needed for saga state; no model retraining is intrinsically required, but corrected outcomes invalidate downstream evaluation/training caches. **B:** non-frozen `PaperLoop` coordinator executes the same saga after `protected=false`. It avoids a frozen edit but does not protect direct FSM callers and must persist crash-safe state externally. **C:** watchdog-only repair is rejected as too late and does not satisfy immediate contract semantics.

### My recommendation
Choose A with explicit owner approval, and use B only as an interim PAPER admission blocker. Do not mark a position protected unless both legs are venue-accepted; on either failure, reconcile first, cancel any surviving leg, issue an idempotent reduce-only flatten, verify flat, and keep global admission blocked until durable reconciliation succeeds.

### Acceptance and regression tests
Add stop `-1022`, target rejection, UNKNOWN/lost ACK, and partial-leg scenarios. Assert: `protected=false`; no “protected” projection; exactly one idempotent emergency exit; accepted status `NEW` is followed by query/reconcile; surviving target/stop is cancelled; venue and ledger become flat; P0 delivery is acknowledged; restart resumes the saga without duplicate exit; new entries remain blocked. Run against fake and temporary SQLite DDL, then require separate read-only device evidence—order/fill/position/ledger traces—before claiming operational success.
