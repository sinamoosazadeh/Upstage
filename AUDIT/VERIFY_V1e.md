# Independent Verification V1e — Execution FSM and venue adapter

Baseline verified: `85b2c155d7b054a468379ddfd802eb239d0801f9` (`85b2c15 Merge pull request #25 from sinamoosazadeh/arena/01a0d98b-upstage`). Verification date: 2026-09-29 UTC. This verification uses real repository code with synthetic inputs and temporary/in-memory SQLite only; it neither proves real-device/database/model behavior nor contacts an exchange or Telegram.

## Summary

| ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option |
|---|---|---:|---:|---|---|---|
| E-001 | CONFIRMED | S1 | S1 | No | D58 (separate simulator scope); X-V1d-002 | A: durable non-terminal lifecycle registry |
| E-002 | CONFIRMED | S1 | S1 | No | — | A: reconstruct/hydrate before READY |
| E-004 | CONFIRMED | S1 | S1 | No | — | A: cumulative fill/residual authority |
| E-005 | PARTIAL | S1 | S1 | No | X-V1d-002; D50 | A: lawful exit mapping + residual accounting |
| E-006 | PARTIAL | S1 | S1 | Mixed (catalog frozen) | D58; ISSUE-076; X-V1d-002 | A: CP-15 simulator/state + index deployment |
| E-007 | PARTIAL | S1 | S1 | No | D50; X-V1d-002 | A: durable child exit lifecycle |
| E-008 | CONFIRMED | S1 | S1 | No | — | A: canonical inverse symbol map |
| E-009 | CONFIRMED | S1 | S1 | No | — | A: require successful/schema-valid boot queries |
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

## E-004

### Auditor claim (short quote)
“Partial entry is protected at full plan quantity; a repeated PARTIAL triggers an undefined PARTIAL→PARTIAL_FILL transition, and partial protection failure has no legal transition.”

### What I read (files, line ranges, functions, callers)
I read `/tmp/AUDIT.md:197` in full; the complete required FSM, adapter, ledger, fake responder and tests; plus direct caller `PaperRuntime.execute_plan`/`_observe_fill` (`apex/ops/paper_loop.py:692–801`) and direct callees `ExecutionFSM.record_fill`/`place_protection` (`fsm.py:671–757`) and adapter submit/query code (`toobit_adapter.py:402–550`). Mandatory consumer search was `grep -RInE 'PARTIAL_FILL|place_protection|record_fill|_observe_fill|apply_adapter_result' apex tests scripts`. The transition matrix has no `PARTIAL,PARTIAL_FILL` edge and no `PARTIAL,PROTECTION_FAILED` edge (`fsm.py:130–162`); `place_protection` defaults `qty` to `self._plan.sized_quantity` (`710`) and `advance` refuses absent edges (`451–495`).

### Reproduction (command, probe file, actual result)
`python3 -u -B AUDIT/probes_V1e/E-004.py` (raw `AUDIT/probes_V1e/E-004.out`) uses the real FSM, adapter, ledger and temporary SQLite with a repository fake responder configured before adapter construction. The real partial entry reports `venue_executed 0.1 plan_quantity 0.2`; its repeated venue PARTIAL raises `ILLEGAL_FSM_TRANSITION state PARTIAL`; after recording the actual 0.1 fill, protection succeeds with `stop_quantity 0.2 target_quantity 0.2`; a business-code `-1022` stop rejection then raises `partial_protection_failure_exception ILLEGAL_FSM_TRANSITION state PARTIAL`. `E-004_E-005-pytest.out` records the focused existing command and `6 passed, 152 deselected`; the passing synthetic tests do not cover this real partial transition. The output demonstrates control flow against a fake venue only, not a real partial-fill feed/device.

### Verdict and reasoning
**CONFIRMED, S1.** All three reported mechanisms hold. A full-plan pair of protective reduce-only orders is created for half the actual entry quantity; a repeated status is not idempotent; and the failure escalation itself throws when starting at PARTIAL. Any is enough to make partial entry handling unsafe. S1 reflects potential protection/exposure loss after a partial venue execution, rather than a universal S0 startup blocker.

### Root cause
The FSM holds individual fills but exposes neither cumulative filled quantity nor remaining quantity as the protection sizing authority. The runtime treats any PARTIAL as a fresh state transition, and the frozen transition map omitted idempotent observation/failure edges needed by the caller’s behavior.

### Direct impact
A partial fill can create over-sized protective orders, crash processing on its next unchanged poll, or crash while processing a rejected stop. The partial exposure is then not reliably protected/reconciled.

### Secondary effects and interactions (upstream/downstream)
E-001 discards unfilled/partial lifecycle objects; E-002 cannot rebuild them after restart. Over-sized reduce-only stops/targets can produce venue rejection or quantities inconsistent with ledger position. E-005’s residual-close issue is a distinct exit-stage analogue. Resulting fill/accounting/outcome data can corrupt risk limits, replay and training labels. Fixture/fake success is not proof of exchange semantics, position-mode handling or real database data.

### Contract and decisions
The governing Ch.16 table at `APEX_GEN5.md:16920–16928` says entry IOC permits partial fill and “PARTIAL until `fill_timeout` ⇒ RECOVERY_REQUIRED”; `16874–16880` requires reconcile-first rather than silent failure. The immutable Ch.16 state vocabulary governs the names, but it does not authorize an exception as a partial-fill policy. D50 governs identity/duplicate behavior (`PHASE2_DECISION_LOG.md:1159`) and does not supersede partial-fill safety. Contract then D50 take precedence; no conflicting later owner decision was found.

### Frozen status and non-frozen alternative
`fsm.py`/`paper_loop.py` are non-frozen under the supplied list, but frozen lifecycle names and Ch.16 values must remain unchanged. A non-frozen producer/runtime projection of cumulative ledger fills can size protection correctly. No change to frozen engine/data-catalog files, YAMLs, research files or `requirements.lock` is needed.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A (recommended):** make `record_fill`/ledger cumulative filled and remaining quantities authoritative; make repeated same-order status observational/idempotent; add lawful partial failure handling that transitions to recovery without throwing; submit/resize/cancel protection only for actual residual exposure. Side effects: tests pinning the transition matrix need revision; protection/order identity and ledger audit entries increase; existing cached duplicate logic must remain distinguishable (X-V1d-002); no DB migration is needed if fills are replayed, but persisted protection linkage would need one. **B:** reject/cancel every partial entry. This is legal only after reconcile and changes the governed “partial fill permitted” behavior; it still needs partial accounting. **C:** protect full quantity and rely on venue reduce-only clipping. Rejected: unsound, venue-dependent, and not traceable.

### My recommendation
A, with a single cumulative fill/remainder calculator shared by polling, protection, reconciliation and exit accounting.

### Acceptance and regression tests
Test initial partial, repeated identical partial, increasing partial then full, partial timeout, and stop/target rejection. Assert every protection quantity equals current live exposure, repeated polls create neither transition nor duplicate fill, and failure yields named recovery rather than an exception. Retain fresh ACK/FILLED behavior, D50 duplicate semantics and ledger fill-id idempotency.

## E-005

### Auditor claim (short quote)
“A PARTIAL exit is closed like a full exit and removed from `working` even when `reconciled=False`.”

### What I read (files, line ranges, functions, callers)
I read the complete row at `/tmp/AUDIT.md:198`, all required scope files and `PaperRuntime.manage_positions` (`apex/ops/paper_loop.py:803–870`) end-to-end. Its fill branch records `fill[quantity]`, computes P/L using the full `plan.sized_quantity`, calls `close_position`, calls `reconcile`, appends an action, then unconditionally `self.working.pop(intent_id, None)`. Direct callees are `ExecutionFSM.record_fill`, `close_position`, `reconcile` (`fsm.py:671–910`) and `last_closed_price`; the caller is `run_cycle` (`paper_loop.py:1052`). Consumer search was `grep -RInE 'manage_positions|close_position|kind="exit"|DUPLICATE_CLIENT_ORDER_ID|cached' apex tests scripts`. I also read V1d X-V1d-002 rather than re-verifying it: `apply_adapter_result` does not inspect `cached`/`DUPLICATE_CLIENT_ORDER_ID`.

### Reproduction (command, probe file, actual result)
`python3 -u -B AUDIT/probes_V1e/E-005.py` (raw `AUDIT/probes_V1e/E-005.out`) exercises the real adapter and repository fake responder. One normal submit then the same id produces `first ACKNOWLEDGED False cached ACKNOWLEDGED True DUPLICATE_CLIENT_ORDER_ID post_count 1`; applying that cached receipt yields `cached_apply_state ACKNOWLEDGED duplicate_exposed False reconcile_required False`, independently confirming the relevant consumer-side path noted by V1d. Crucially, the real exit seam reports `actual_exit_exception ORDER_KIND_QX`: `manage_positions` passes `kind="exit"`, but `order_defaults` has no `exit` kind. Thus I could not reproduce an actual partial exit through the current real adapter; the source branch itself is nevertheless directly reachable if a fill-shaped exit result is supplied by the test-only `FakeAdapter`. The focused pytest output is `E-004_E-005-pytest.out` (6 passed), which uses that synthetic adapter and cannot prove real-adapter exit behavior.

### Verdict and reasoning
**PARTIAL, S1.** The claimed *branch* is proven: if `fill_from_result(exit_result)` returns a partial quantity, code closes the full lifecycle, calculates full-plan P/L and removes it regardless of `reconciled.get("agree")`. However, the claim overstates current executable behavior: the actual shipped adapter raises before an exit can ACK or partially fill because `kind="exit"` is unsupported. This is not a rejection of the dangerous dead branch; it is a partial verdict because the report’s concrete runtime scenario is unreachable at this baseline. S1 remains appropriate: making exit mapping reachable without fixing the branch can abandon residual exposure; current management’s exception is also serious.

### Root cause
`manage_positions` equates “a fill result exists” with “the position is flat.” It does not compare exit quantity/cumulative ledger residual to exposure and does not gate removal on reconciliation. Separately, its invented `kind="exit"` conflicts with the adapter’s governed defaults; V1b/V1d already recorded that wire-map fact.

### Direct impact
If the exit branch becomes executable, a 2-of-10 exit books a terminal outcome/P&L at 10 and discards the remaining 8 even after reconciliation says false. At present, triggered exit management instead raises `ORDER_KIND_QX`, so no exit is submitted at all through the real adapter.

### Secondary effects and interactions (upstream/downstream)
The partial/remnant problem interacts with E-004 partial entries, E-006 stop/target management and E-007 repeated exit intent. It can understate open margin/exposure, distort P/L and loss limits, leave protective orders mismatched, and contaminate outcome/replay/training data. V1d X-V1d-002 means a cached exit acknowledgement would be treated like fresh progress if an exit mapping is later added. Fake/test-double observations cannot prove real exchange reduce-only behavior, fills, accounting or device recovery.

### Contract and decisions
`APEX_GEN5.md:16874–16880` requires reconciliation before downstream reconciliation state; `16919–16928` makes partial fill a governed lifecycle state until timeout/recovery. `16958–16962` requires working orders/positions reconstruction. D50 (`PHASE2_DECISION_LOG.md:1159`) requires repeated IDs be named `DUPLICATE_CLIENT_ORDER_ID`, never resent, with original outcome preserved; V1d proves the consumer does not use that marker. No owner decision permits terminal closure solely because one partial fill record exists. Contract and D50 therefore prevail.

### Frozen status and non-frozen alternative
No affected source file is listed frozen; frozen wire defaults must not be edited casually, and the six original YAMLs are frozen. A non-frozen adapter/fabric mapping can give exits a governed existing kind/semantics, while a runtime/ledger residual calculator fixes closure. Changing frozen `order_defaults` would require explicit owner ruling; an outside adapter operation mapping is preferable.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A (recommended):** first establish a lawful non-frozen exit adapter path using existing governed flatten semantics; then calculate remaining exposure from ledger/venue fills, retain/rescale protection and `working` until flat **and** reconciled. Side effects: exit identity/order linkage and test fixtures change; old outcomes/caches are not rewritten but may require correction records; current exact action tests change; no retraining is automatic but corrected outcomes affect later training data. **B:** reject partial exits and require manual recovery. Conservative but harms normal partial target policy and still needs reconciliation. **C:** alter frozen `order_defaults` with an `exit` key. Requires owner ruling and broad wire/fixture conformance review; do not choose absent that ruling.

### My recommendation
A, landing the adapter mapping and residual accounting together; do not merely enable `kind="exit"` and expose the existing full-close branch.

### Acceptance and regression tests
Using a real adapter/fake configured before construction, prove exit ACK, PARTIAL, FILLED, rejected and cached duplicate paths. A 2/10 exit must retain residual 8 with correctly sized protective cover, no outcome until flat/reconciled, and correct P/L only on closed quantity. A reconcile failure must retain recovery state. Assert real adapter wire construction never raises `ORDER_KIND_QX` on the approved exit path and V1d duplicate marker behavior remains explicit.

## E-006

### Auditor claim (short quote)
“Management compares only the close of the last reader row to stop/target; it omits high/low, gaps, intervening closed candles, time stop and sibling cancellation, and STOP exits omit intended/actual stop attribution.”

### What I read (files, line ranges, functions, callers)
I read `/tmp/AUDIT.md:199` in full, all required source/test files, `last_closed_price` (`apex/ops/paper_loop.py:305–313`), `manage_positions` (803–870), `SQLiteStore.get_window` and its DDL (data catalog `1–672`, query 497–522), FSM closure/protection methods (`fsm.py:695–910`) and ledger outcome/stop-gap helpers (`ledger/store.py:435–489, 763–868`). Mandatory consumer search was `grep -RInE 'last_closed_price|manage_positions|stop_gap_slippage|intended_stop|actual_fill|cancel\(' apex tests scripts`; it found the manager is invoked from `run_cycle`, and no sibling-order cancellation in this exit path. I read V1b/V1d first and cite V1d X-V1d-002 for the duplicate-marker consumer defect; I do not repeat its verdict.

### Reproduction (command, probe file, actual result)
`python3 -u -B AUDIT/probes_V1e/E-006.py` (raw `AUDIT/probes_V1e/E-006.out`) runs the real runtime/FSM/ledger/store using the repository’s test-only fill double for the currently unreachable exit seam. A closed bar with high 105, low 94, close 94 triggers `manager_action STOP filled True stop_gap None working []`: only its close selects STOP and `close_position` receives neither stop argument. The same probe uses real DDL and exactly the `get_window` query in `EXPLAIN QUERY PLAN`: without the two named device indexes it records `SCAN market_observation` and two temp B-trees; after `idx_mo_sym_tf_open(symbol,timeframe,open_time)` plus `idx_pit_scope_asof(...)`, it records indexed `SEARCH market_observation ...` (one outer temp B-tree remains). This query occurs once per managed intent each cycle. It also records real adapter duplicate output `real_adapter_cached True DUPLICATE_CLIENT_ORDER_ID ACKNOWLEDGED`, as required; V1d establishes that the FSM does not consume the marker. The focused pytest output is `E-006_E-007-pytest.out` (`2 passed`), based on synthetic test behavior. The synthetic manager fill does not establish any real PAPER/device fill law.

### Verdict and reasoning
**PARTIAL, S1.** The manager’s actual decision algorithm indisputably reads one latest close, has only stop/target close comparisons, no time condition, no inter-bar loop, no sibling cancel, and passes no intended/actual stop values. The probe demonstrates the missing attribution and confirms the per-active-intent unindexed scan absent the known manual index. But the auditor overstates current executable PAPER behavior: real adapter exit submission is blocked by `kind="exit"` (`ORDER_KIND_QX`, E-005/E-007), and D58 says the governed CP-15 simulator is not yet wired. Therefore no actual current venue/PAPER stop/target fill, gap or missed intrabar touch was reproduced. S1 is retained because this manager becomes a direct safety/accounting defect if the exit path is made reachable; the current exit failure itself is already serious.

### Root cause
The runtime contains a minimal close-price convenience manager instead of the binding D1/F3 PAPER simulator/order-lifecycle reconciler. It samples `get_window(..., bars=1)`, not an unconsumed-bar frontier, and treats a manager-generated direct exit as sufficient without modelling protective orders or a cancellation/reconciliation transaction.

### Direct impact
Once exits are enabled, a stop/target touched intrabar then recovered by close, an adverse gap, simultaneous stop/target touch, a time limit, or a fill between polls can be missed or mispriced. STOP outcome records lack `STOP_GAP_SLIPPAGE` inputs; sibling orders can remain live. The current actual adapter instead throws before any exit request.

### Secondary effects and interactions (upstream/downstream)
This is **= D58** only as to the known unimplemented PAPER fill simulator/CP-15 schedule; beyond D58, the present manager concretely performs a one-close direct-exit algorithm and omits ledger stop attribution/cancellation. It interacts with E-004/005 residual quantity, E-007 exit lifecycle and F-001 P/L (not re-adjudicated here). The unindexed `market_observation` scan is **= ISSUE-076** (manual device index known); beyond that owner item, this verification identifies `manage_positions → last_closed_price` as a per-managed-intent/cycle consumer and records the real-DLL plans. Downstream risk marks, ledger outcomes, replay and training labels may diverge. No actual market data/device scale was tested.

### Contract and decisions
Binding D1/F3, `APEX_GEN5.md:17034–17066`, specifies CP-15’s simulator: every subsequent CLOSED bar, hard-stop→target→time-stop precedence, stop/target price fills, gap-through at bar open, durable simulator state and reconciliation. `17074–17080` requires both `intended_stop` and `actual_fill`, `STOP_GAP_SLIPPAGE`, realized worst-loss input and market emergency close on protection failure. Ch.16 `16874–16880` also requires reconcile-first. D58/CP-15 is a later owner scheduling item but does not waive F3’s binding behavior; it explains incompleteness. Contract governs design; D58 governs implementation sequence.

### Frozen status and non-frozen alternative
`apex/ops/paper_loop.py` is non-frozen; `apex/data_catalog/**` including the stock DDL/query are frozen absent owner ruling. A non-frozen CP-15 simulator transport/state layer can consume bars and maintain an execution cursor without changing catalog code; an outside cache/adapter can avoid per-position last-window reads. Adding the missing stock DDL index would touch frozen data catalog, though ISSUE-076 records manual device indexes already exist.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A (recommended):** implement the owner-scheduled CP-15 simulator as the authoritative PAPER five-operation transport, with durable per-order bar cursor, F3 precedence/gap law, sibling cancellation/reconciliation, stop attribution and close/outcome only after confirmed fill. Side effects: new simulator state migration, event/order identities and ledger/outcome data change; PAPER replay/caches/training data need versioning or regeneration; tests using fake direct exits change; no frozen source change required. **B:** enhance `manage_positions` alone to scan windows and cancel siblings. Rejected: duplicates the simulator’s five-operation state and leaves query/restart semantics split. **C:** only add `idx_mo_sym_tf_open` to frozen DDL. It fixes the observed scan but not fill correctness; requires owner ruling/migration or retained device manual-index procedure.

### My recommendation
A, using F3 exactly and retaining the manual device index guidance from ISSUE-076 until an owner authorizes a frozen DDL migration.

### Acceptance and regression tests
With durable simulated state, test multiple unprocessed bars, intrabar stop/target precedence, gap fill at open, touch/recover, time exit, sibling cancellation, partial exit and restart replay. Assert STOP outcome carries intended stop/actual fill/slippage and next-risk attribution; no orphan order remains. Run `EXPLAIN QUERY PLAN` for the actual last-price/window query with and without the device indexes; assert the deployment path has no unindexed `market_observation` scan.

## E-007

### Auditor claim (short quote)
“If an exit first ACKs, the next cycle submits the same intent again; the cache returns the ACK and the manager never queries `intent-exit`.”

### What I read (files, line ranges, functions, callers)
I read the full row `/tmp/AUDIT.md:200`, the complete mandatory scope and direct caller/callees: `manage_positions` (paper loop 803–870), `ToobitAdapter.submit_order`, `_cached_result` and `query_order_state` (adapter 402–550, 623–819), `order_defaults`/wire defaults and classification map (`toobit_map.py:90–112, 250–289, 320–411`). Mandatory search was `grep -RInE 'kind="exit"|intent_id.*-exit|query_order_state|_cached_result|DUPLICATE_CLIENT_ORDER_ID' apex tests scripts`. The V1b/V1d reports were read first as required: V1b confirms accepted venue state literal `NEW`; V1d X-V1d-002 confirms the cached marker is ignored by the FSM.

### Reproduction (command, probe file, actual result)
`python3 -u -B AUDIT/probes_V1e/E-007.py` (raw `AUDIT/probes_V1e/E-007.out`) uses a real adapter and repository fake responder configured before adapter construction. It shows identical normal entry retries return `cache ACKNOWLEDGED ACKNOWLEDGED True DUPLICATE_CLIENT_ORDER_ID posts 1`, then the exact exit call used by the manager reports `manager_exit_kind ORDER_KIND_QX transport_posts_after_exit_attempt 1`; no exit POST occurs. This is the required duplicate/cached path, but it disproves the reported first-ACK premise for the current real adapter. Focused relevant tests are recorded in `E-006_E-007-pytest.out` (`2 passed`); their fake-exit success does not prove the real adapter path.

### Verdict and reasoning
**PARTIAL, S1.** The latent manager logic is as claimed: if a substituted adapter returns an exit ACK without fill, no durable exit FSM/order state is saved; next price-triggered cycle calls submit again with the same `intent_id-exit`, and it does not query that ID. The real adapter cache would return a named cached ACK and V1d proves it is not surfaced by the FSM. However, at this baseline the first real exit cannot ACK: `kind="exit"` is absent from the governed default map and throws pre-transport. The auditor’s asserted current ACK→cached-ACK reproduction is therefore overstated. S1 reflects the existing inability to execute managed exits and the latent duplicate/lost-fill issue if a mapping is added.

### Root cause
`manage_positions` is stateless about exit orders and reuses a deterministic suffix as a submission action, not an order lifecycle. It also calls an unsupported ad-hoc order kind rather than a governed flatten operation. The adapter correctly caches repeated IDs, but consumer code does not distinguish cache evidence (V1d X-V1d-002).

### Direct impact
Current price-triggered management errors before submitting any exit. If the kind is enabled without lifecycle persistence, a delayed/filled exit can remain ACKNOWLEDGED in runtime records forever, receive no query after price moves away, and be replayed as a cached ACK rather than ledgered exactly once.

### Secondary effects and interactions (upstream/downstream)
E-005 shares the unsupported kind/residual closure defect; E-006 shows all price exit management is incomplete; E-001/002 lose non-terminal lifecycle across cycles/restart. D50’s duplicate semantics prevent an extra POST but are not a substitute for fill query/reconciliation. Downstream exposure, protective orders, P/L, loss limits and training outcomes can be false. The fake cache proves repository behavior only, not venue semantics or a device run.

### Contract and decisions
Ch.16 `APEX_GEN5.md:16891–16904` requires repeat key returns original response without resubmit, state mapping and UNKNOWN reconcile-before-action; `16970–16983` makes client order identity the reconciliation key and requires adapter conformance. D50 (`PHASE2_DECISION_LOG.md:1159`) specifically requires named `DUPLICATE_CLIENT_ORDER_ID`, never resent, original outcome preserved. D1/F3 requires durable simulator order state (`17034–17066`). No later owner decision authorizes a fire-and-forget exit. Contract plus D50 govern; V1d X-V1d-002 remains a cited consumer-side finding.

### Frozen status and non-frozen alternative
The runtime/adapter are non-frozen, while original wire YAML/default values are frozen. Do not add an `exit` default in frozen YAML without an owner ruling. A non-frozen adapter-level `submit_flatten` implementation composed solely of an existing governed flatten semantic, plus durable runtime exit state, is an alternative outside frozen config; it still must pass conformance/wire review.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A (recommended):** model entry/protection/exit as durable child order records under one parent intent; after exit submit, query/reconcile that child until terminal and record each fill once; make duplicate/cached status explicit per V1d before advancing. Side effects: state/ledger linkage and tests change, old in-flight records require recovery migration/adapter, and D50 cache behavior becomes visible; hashes/identity scheme should remain unchanged. **B:** have each management cycle issue a fresh exit ID. Rejected: can create overlapping reduce-only exits and violates deterministic/reconcile-first identity. **C:** map `kind="exit"` directly in frozen defaults. Requires owner ruling and still does not solve state/query behavior.

### My recommendation
A, coordinated with E-005-A and V1d X-V1d-002-A; make the adapter path lawful before exposing it.

### Acceptance and regression tests
Use real adapter/fake responder with a lawful flatten path to assert first ACK produces one durable child record, subsequent cycles query rather than POST, later FILLED records one exit fill and terminal reconciliation, cached duplicate reports its marker, and price reversion does not abandon the outstanding exit. Verify unsupported ad-hoc kinds remain rejected and no new frozen wire literal changes without ruling.

## E-008

### Auditor claim (short quote)
“`BTC-SWAP-USDT` is reduced to `BTC`, not `BTCUSDT`; boot and `_position_row_for` create false ±2 deltas at tolerance 1.”

### What I read (files, line ranges, functions, callers)
I read full row `/tmp/AUDIT.md:201`, all required scope files, `fsm.py` position normalization at 917–926 and boot reconciliation 1163–1218, and the complete wire map including `to_internal_symbol` at `apex/execution/toobit_map.py:90–112`. The relevant direct callers are `ExecutionFSM.reconcile` and `StartupReconciliation.reconcile_boot`; both consume venue position rows. Mandatory search was `grep -RInE '_position_row_for|SWAP-USDT|to_internal_symbol|query_open_positions' apex tests scripts`. It finds the canonical inverse exists in `toobit_map.py` but neither FSM caller uses it. I also read the requested fake responder and its `seed_position`/position query behavior.

### Reproduction (command, probe file, actual result)
`python3 -u -B AUDIT/probes_V1e/E-008.py` (raw `AUDIT/probes_V1e/E-008.out`) uses real startup reconciliation/ledger/adapter over temporary SQLite and a fake venue position `BTC-SWAP-USDT=2` matching a ledger `BTCUSDT=2` entry. Result: `boot_agree False`; deltas are `BTCUSDT: exchange 0 ledger 2 delta -2` and `BTC: exchange 2 ledger 0 delta 2`; direct `_position_row_for(..., "BTCUSDT")` returns `{}`. Focused test output `E-008_E-009-pytest.out` has `14 passed, 194 deselected`; it does not cover this inverse map. The fake proves code conversion and its result only, not real venue symbol payloads.

### Verdict and reasoning
**CONFIRMED, S1.** The string replacement strips the entire `-SWAP-USDT` suffix and creates the wrong internal key. The repository’s own bijective map has the proper answer but is bypassed in both boot and per-intent reconciliation. A matching position is treated as two divergences, yields corrections and blocks readiness/recovery. S1 is warranted because this affects boot/reconciliation and can create a false recovery stop or misleading correction record.

### Root cause
Ad-hoc suffix removal was used instead of the canonical inverse `to_internal_symbol`; `_position_row_for` repeats the same lossy matching rule.

### Direct impact
Known Core-10 wire positions do not match ledger symbols. Boot can enter `RECOVERY_REQUIRED` and append false `BOOT_BROKER_LEDGER_DELTA` corrections; per-intent reconciliation reads no matching position as quantity zero.

### Secondary effects and interactions (upstream/downstream)
E-002 boot restoration is undermined by false divergence; E-010 boot order/fill matching is separately incomplete; E-011 per-intent reconcile can falsely see zero. False correction events pollute the immutable ledger and recovery/audit/replay evidence, but do not themselves place/cancel orders. The actual device symbol response format was not tested.

### Contract and decisions
Binding wire prose at `APEX_GEN5.md:16901–16904` says internal `BTCUSDT…LTCUSDT` maps to wire `BTC-SWAP-USDT…LTC-SWAP-USDT`; Ch.16 `16874–16880` requires matching ledger/exchange state and divergence recovery. Ch.23 `18246–18250` requires positions be reconciled before READY. No later decision overrides this mapping; the contract controls.

### Frozen status and non-frozen alternative
The original wire YAML/map values are frozen, but `fsm.py` is non-frozen. Do not alter symbol literals: import/use the existing inverse map in the non-frozen consumer and fail closed with its named unknown-symbol error. An adapter-side producer normalization is possible but has broader response-contract effects.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A (recommended):** replace both lossy conversions with `to_internal_symbol`, catching its named unknown symbol refusal and keeping unknown rows explicit. Side effects: matching valid symbols changes correction/boot outcomes; existing tests that implicitly expect suffix stripping change; historical false correction records stay immutable and need append-only remediation if acted upon; no migration/retraining/hash invalidation. **B:** build a reverse dict local to FSM. Rejected: duplicates frozen mapping and risks drift. **C:** accept both guessed forms. Rejected: hides unknown symbols and can collide.

### My recommendation
A, with a round-trip test over all ten frozen symbol-map members and an unknown wire symbol fail-closed test.

### Acceptance and regression tests
For every map entry, wire→internal→wire must preserve exactly; zero/nonzero matching ledger positions must have zero delta in boot and per-intent reconciliation. Unknown/malformed wire symbol must fail/recovery rather than be treated as zero. Retain tolerance behavior only for genuine numeric deltas.

## E-009

### Auditor claim (short quote)
“Boot rejects only UNKNOWN-and-not-ok; three `REJECTED`/`ok=False` `-1022` queries with an empty ledger give `agree=True`.”

### What I read (files, line ranges, functions, callers)
I read complete `/tmp/AUDIT.md:202`, all required scope files, `StartupReconciliation.reconcile_boot` (`fsm.py:1163–1218`), adapter query execution/classification (`toobit_adapter.py:513–731, 849–879`) and `classify_business_code` (`toobit_map.py:320–378`). The mandatory consumer search `grep -RInE 'reconcile_boot|EXCHANGE_UNKNOWN|outcome == "UNKNOWN"|business_code' apex tests scripts` establishes this is the boot consumer and no surrounding caller revalidates REJECTED results. The classification table makes `-1022` `ABORT`, outcome `REJECTED`, `ok=False`, `reconcile_required=False`; this is a documented business code, not an invented envelope.

### Reproduction (command, probe file, actual result)
`python3 -u -B AUDIT/probes_V1e/E-009.py` (raw `AUDIT/probes_V1e/E-009.out`) invokes real boot reconciliation with a real adapter, temporary SQLite and fake responder configured for three `-1022` responses. It prints `agree True open_intents ()`; adapter audit is three `(..., 'ABORT', 'REJECTED', -1022)` entries and boot appends `check PASS 1 exchange position row(s), 0 working order(s), 0 divergence(s)`. `E-008_E-009-pytest.out` records 14 focused passing tests; none asserts REJECTED boot queries fail. This proves implementation behavior with a synthetic response, not actual authentication/device failure.

### Verdict and reasoning
**CONFIRMED, S1.** Boot only returns failure for `r.outcome == "UNKNOWN" and not r.ok`. It treats three explicit abort/rejection responses as empty-ish response data, calculates no deltas on the empty ledger, and reports PASS/agree. This violates fail-closed reconciliation and can reach READY without account state.

### Root cause
The boot result validation confuses “not UNKNOWN” with successful/schema-valid result. It neither requires `ok`/`classification == OK` for each of the three required queries nor validates expected response shape before parsing rows.

### Direct impact
A rejected credentials/authorization/business response can be accepted as no positions/orders/fills, allowing false reconciliation and later trading readiness when the actual account is unknown.

### Secondary effects and interactions (upstream/downstream)
E-010 then ignores orders/fills even when calls succeed; E-011 repeats weak query validation per intent; E-002 may hydrate nothing after false boot. Downstream risk, protection, accounting and recovery depend on a false account view. No real credential, exchange or device endpoint was used or inspected.

### Contract and decisions
Ch.23 `APEX_GEN5.md:18246–18250` requires queries for open positions, working orders and recent fills before transitions to READY. Ch.16 `16972–16983` maps errors deterministically and makes UNKNOWN reconcile-first; the more general `16874–16880` invariant prohibits reconcile while states disagree. AI.9 `18894–18903` says any failed check halts/escalates. The documented `-1022 abort` at `16927–16933` cannot lawfully mean a successful empty account. No conflicting later decision exists; contract has precedence.

### Frozen status and non-frozen alternative
FSM/adapter code is non-frozen; business-code values/wire defaults must remain frozen. A non-frozen boot response validator can require all queries be successful, expected-scope and schema-valid before parsing, without DDL, engine, YAML or requirements changes.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A (recommended):** require `ok`, classification `OK`, appropriate operation/scope and valid list/object schema for positions/open/fills; any rejection, UNKNOWN, malformed body or transport uncertainty yields named boot failure/DEGRADED. Side effects: current tests/fixtures that pass sparse success bodies need explicit valid envelopes; boot becomes more conservative; no hash/migration/retraining change. **B:** accept REJECTED only when ledger is empty. Rejected: credentials/account knowledge remains absent. **C:** map `-1022` to UNKNOWN. Rejected: loses meaningful classification and does not fix all `ok=False` classes.

### My recommendation
A, shared with E-011 in one query-validation helper so boot and per-intent reconcile cannot drift.

### Acceptance and regression tests
For each positions/open/fills call independently inject `-1022`, `-1120`, unknown code, timeout, non-200 code 0, malformed data and valid empty response; only schema-valid successful empties may agree. Repeat with non-empty ledger/venue state and assert boot never reaches READY on any failed call.

