# Independent Verification V1b — Execution FSM, Venue Adapter, Order Lifecycle

Baseline: `85b2c155d7b054a468379ddfd802eb239d0801f9`. Verification date: 2026-09-28. Synthetic/fake results below do not establish behavior on the real device, database, model, or venue.

## Summary

| ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option |
|---|---|---:|---:|---|---|---|
| E-016 | CONFIRMED | S0 | S0 | Mixed | D50 | A: durable proposal→intent mapping |
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

## E-016

### Auditor claim (short quote)
“D50 intent identity is not joined to the plan identity in the PAPER account projection.”

### What I read (files, line ranges, functions, callers)
I read the full row, `paper_loop.py:180–230,680–710` (`intent_id_for`, `execute_plan`), `engine_context.py:662–833,2186–2280` (`paper_account_state` and its producer), `fsm.py:530–596`, ledger plan/transition readers and writers, and the cited tests. Consumer search `grep -RIn 'paper_account_state|PAPER_ORDER_STATE_UNAVAILABLE|intent_id_for' apex tests scripts` shows native execution uses D50 while projection recognizes only proposal ID and `i-` plus its last 12 characters.

### Reproduction (command, probe file, actual result)
`python3 AUDIT/probes_V1b/E-016.py` used real repository SQLite DDL, `LedgerWriter`, D50 `intent_id_for`, and `paper_account_state` in a temporary DB. `E-016.out` records D50 `i-db49c28b87dd3e69a00dd15a`, legacy candidate `i-000000000001`, then `PAPER_ORDER_STATE_UNAVAILABLE: materialized plan lacks order state` despite a valid transition under the D50 ID.

### Verdict and reasoning
**CONFIRMED, S0.** The first native allowed plan can make subsequent account projection fail closed. This blocks basic PAPER progression; synthetic success does not prove device state.

### Root cause
No durable proposal→intent key is stored/read. Projection retains the superseded 12-character naming convention while D50 deliberately hashes five content fields.

### Direct impact
Valid materialized PAPER plans become unjoinable to their FSM transitions and fills, preventing account/risk context generation.

### Secondary effects and interactions (upstream/downstream)
Upstream identity includes close time unavailable in the stored plan row. Downstream marks, reserved notional, margin vetoes, decisions, replay, and training/outcome lineage fail or become unavailable. A heuristic relaxation could misattribute fills.

### Contract and decisions
`PHASE2_DECISION_LOG.md:1159` D50 explicitly requires `i-` plus 24 hex characters of the canonical content hash and “never the tail of proposal_id.” It is later and more specific than older contract identity prose, so D50 prevails. The execution FSM remains the sole venue path under Ch.16; this does not authorize guessed joins.

### Frozen status and non-frozen alternative
The defect spans non-frozen producers/projection plus frozen `fsm.py` and ledger storage code. A non-frozen adapter/projection table can durably bind proposal, close, and intent without changing FSM; changing ledger schema APIs needs owner review appropriate to frozen `apex/ledger/store.py`.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A:** additive durable proposal→intent mapping written before submission and consumed by projection. Requires migration/backfill policy; identity hashes stay unchanged; account/cache outputs change; tests using legacy IDs need dual-read coverage; no model retraining, though derived account artifacts should be invalidated. **B:** add `intent_id`/`close_ms` to the trade-plan schema (cleaner but frozen ledger change and migration). **C:** recompute only when all exact D50 inputs are durably present; current plan lacks `close_ms`, so guessing is forbidden.

### My recommendation
A now, with collision rejection and explicit legacy dual-read; B at the next owner-approved ledger revision.

### Acceptance and regression tests
Use native `intent_id_for` through plan→FSM→fill→projection before/after restart; assert exact one-to-one joins, pending/fill values, orphan and ambiguous refusal, legacy read compatibility, and no 12-tail inference for new records. Run temporary SQLite migration/replay tests and separately inspect a read-only device copy before any operational claim.
