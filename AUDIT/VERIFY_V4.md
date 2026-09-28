# V4 independent verification — baseline 85b2c155d7b054a468379ddfd802eb239d0801f9

Read-only source/contract examination; probes used synthetic identities, injected faults and disposable SQLite with the repository migrations and triggers. No venue, Telegram, device database, secrets, or `.env` were accessed deliberately. Baseline command `git rev-parse HEAD && git log -1 --oneline` returned the full baseline SHA and `85b2c15 Merge pull request #25 ...`. Report source: `/tmp/AUDIT.md` (fetched 690e2d88); index is not evidence. Commands below assume `PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1`. All measured results are **fixture-only**, not evidence of trades or device latency. A green test suite does not discharge the counterexamples.

| ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option |
|---|---|---|---|---|---|---|
| G-009 | CONFIRMED | S0 | S0 | No | D-002 distinct; ISSUE-073 distinct | A: durable admission gate |
| F-001 | CONFIRMED | S1 | S1 | No | D58 PAPER simulator pending | A: actual-fill accounting |
| F-002 | CONFIRMED (conditional shared DB) | S1 | S1 | No | D4 separate PAPER/LIVE | A: scoped projection |
| F-003 | CONFIRMED | S1 | S1 | No | — | A: current cost basis |
| F-004 | CONFIRMED | S1 | S1 | DDL frozen | A: atomic writer envelope |
| F-005 | CONFIRMED | S1 | S1 | DDL frozen | — | A: queue-side dedup + ownership |
| F-006 | CONFIRMED | S1 | S1 | DDL frozen | — | A: rollback and poison writer |
| F-007 | CONFIRMED (tamper precondition) | S1 | S1 | DDL frozen | — | A: stronger verifier |
| F-008 | CONFIRMED | S1 | S1 | No | D57 durable ladder is distinct | A: durable reconcile gate |
| F-009 | CONFIRMED (valid complete response assumed) | S2 | S2 | No | ISSUE-075 boot reconcile distinct | A: uniform tolerance |
| F-010 | CONFIRMED (synthetic orphan exit) | S1 | S1 | No | — | A: validate projection |
| F-011 | PARTIAL | S2 | S2 | No | — | A: typed parent validation |
| F-012 | PARTIAL | S2 | S2 | No | — | A: owner resolves conflicting ID contract |
| G-002 | CONFIRMED | S1 | S1 | No | = ISSUE-073 (no additional owner item) | A: explicit refusal until wired |
| G-021 | PARTIAL | S2 | S2 | No | D30: training 20, not coverage 140 | A: distinguish capacity from observed status |
| G-015 | CONFIRMED | S1 | S1 | No | — | A: rolling window |
| G-016 | CONFIRMED | S1 | S1 | No | — | A: atomic in-flight reservation |
| G-017 | CONFIRMED | S1 | S1 | No | — | A: delivery-aware dedup |
| G-018 | PARTIAL | S1 | S1 | No | — | A: separate delivery from protection |
| G-023 | CONFIRMED (synthetic timing) | S1 | S1 | No | — | A: priority admission |
| G-001, G-003..G-008, G-010..G-014, G-019..G-020, G-022, G-024..G-029 | NOT VERIFIED | per source row | unassigned | unassessed | see end | defer |

**Shared test execution:** `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/unit/test_ledger_store.py tests/unit/test_telegram_control_plane.py tests/unit/test_ops_telegram_gateway.py tests/unit/test_telegram_signaling.py tests/unit/test_identity.py > AUDIT/probes_V4/TARGETED_TESTS.out 2>&1`: **286 passed, 13 warnings**. For individual probes use `PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V4/<ID>.py`; output is the sibling `.out`. `QUERY-PLAN.py/.out` run against the real schema with/without the two device-only indexes. Scope of assertions below is the cited implementation behavior, not end-to-end or device acceptance. Owner decisions in PHASE2_DECISION_LOG.md supersede conflicting blueprint prose. No source changes proposed here are authorized.

## G-009
### Auditor claim (short quote)
“Panic Lock says trading halted” but only changes `locked` and broadcasts.
### What I read (files, line ranges, functions, callers)
`control_plane.py:97-116,446-487,728-795` (`handle_command`, `_command`, `_broadcast`, `locked_verdict`); `paper_loop.py:620-650,955-1040,1103-1140` (`_stage_execution`, `run_cycle`, `run`, `_control_paused`); `scripts/run_apex.py:711-765,815-856` (composition); `gateway.py:277-309` (poll). `grep -Rn` of `.locked`, `_control_paused`, `_stage_execution` in apex/scripts/tests finds no execution consumer of `locked`: the one gate in `_control_paused` reads only `paused/new_positions_disabled`, while `_stage_execution` checks boot and decision. Callback/command lock guard blocks *Telegram UI*, not execution.
### Reproduction (command, probe file, actual result)
`python3 AUDIT/probes_V4/G-009.py` → `G-009.out`: `/lock ok=True locked=True`, four halt flags False; real `PaperRuntime._control_paused()` False; new ControlPlane `locked=False`. Synthetic OWNER, no notifier/order. It does not demonstrate a placed trade.
### Verdict and reasoning
CONFIRMED S0: incident containment is falsely acknowledged. Independent evidence distinguishes an operator-message lock from order admission. S0 is justified by a safety control that cannot enforce its promise even if boot later permits entries.
### Root cause
Ephemeral presentation-state boolean is not passed into runtime admission nor persisted; command acknowledges before any verified protective effect.
### Direct impact
New entries are not barred by the lock itself; the UI reports halted trading.
### Secondary effects and interactions (upstream/downstream)
Upstream OWNER Telegram update may be accepted; downstream run-cycle decision, budget and `execute_plan` see only readiness and plan. Restart discards the flag. Existing `BOOT_NOT_READY` (ISSUE-075) may block trading for another reason but cannot be mistaken for a working lock. Emergency L3-L5 no-op (D-002/ISSUE-073) is a different seam. Risk/ledger/identity are not mutated by the lock.
### Contract and decisions
`APEX_GEN5.md:1170-1174`: “trigger Emergency L4 CLOSE_ALL ... or via the Panic Lock `/lock` command”; `17924-17927`: “Panic Lock supports `/lock` and `/unlock` commands with broadcast messages”; `18321`: contain via L4 or `/lock`. Security fail-closed at 1164-1168 blocks new trades on anomaly. `PHASE2_DECISION_LOG.md:194-210` D1 PAPER transport separate and D4 separates account inputs; neither authorizes a fake containment acknowledgement. Owner decisions take precedence; D-002 is an audit row, not a decision in the log.
### Frozen status and non-frozen alternative
Control-plane, gateway, PaperRuntime, composition and a new durable control-state table are non-frozen; no edit to apex/engines or frozen store DDL required (additive migration outside it).
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: Persist/recover lock and check at final pre-submit plus every entry/retry boundary; preserve reduce-only and enforce OWNER/health/reconcile on unlock. Adds migration and restart tests, changes admission/ack tests and may invalidate replay/order-decision hashes if lock is incorporated in decision identity; never rewrite frozen DDL. B: Until A, refuse `/lock` with explicit NOT_WIRED instead of “halted”; fixes misleading success but **not containment**, cannot be final solution. Avoid simply setting `paused`: `run()` skips cycles and may skip protective position management.
### My recommendation
A, with B as temporary truth-in-advertising; incident containment requires a separate verified reduce-only policy.
### Acceptance and regression tests
Authorized lock during ALLOW and concurrent submit, then restart: zero new entry submits, exit/management still runs, no false success on persistence failure; unlock requires health/OWNER reconciliation, update replay cannot reopen. Full device acceptance still needed.

## F-001
### Auditor claim (short quote)
“P/L equals price move × full sized_quantity”, not actual exit fill and multiplier/costs.
### What I read (files, line ranges, functions, callers)
`paper_loop.py:746-874` (`_record_submit_fill`, `_observe_fill`, `manage_positions`, `fill_from_result`); `fsm.py:760-802` (`close_position`, outcome write), `ledger/store.py:435-478`; grep consumers `manage_positions` in `paper_loop.py:1050-1064`; risk/account input D4 in `PHASE2_DECISION_LOG.md:194-208`.
### Reproduction (command, probe file, actual result)
`F-001.py/.out` calls actual `PaperRuntime.manage_positions` with stub venue fill qty 2 at 110, entry 100 and plan qty 10. Output `booked_quantity=2 booked_pnl=100 gross_at_actual_quantity=20`. Stub is not a device fill.
### Verdict and reasoning
CONFIRMED S1 for quantity/gross mismatch; fee/slippage are not passed in these two callsites, but no actual cost model execution is asserted.
### Root cause
P/L calculation uses `plan.sized_quantity` rather than `fill['quantity']`; entry/exit fees and multiplier absent from recorded accounting inputs.
### Direct impact
Wrong booked P/L on partial exits or non-unit multiplier.
### Secondary effects and interactions (upstream/downstream)
Upstream price comes from last CLOSED bar, actual exit result from adapter; `fsm.close_position` writes `outcome` and ledger; downstream PAPER balance/risk/realized loss and research outcome may be wrong once wired. D58 pending simulator is not a waiver for accounting correctness; no real training or account consequence demonstrated.
### Contract and decisions
`APEX_GEN5.md:16875-16883`: reconciliation invariant and immutable ledger; `16915-16921`: unique fill identities and partial fills permitted. D4 (`PHASE2_DECISION_LOG.md:197`) binds PAPER exposure/realized loss to ledger, overriding any interpretation that the displayed balance alone is accounting. No owner decision authorizes using plan size as filled size.
### Frozen status and non-frozen alternative
Execution FSM and runtime are non-frozen. Cost model parameter changes in original YAML or engines would be frozen; compute fill attribution in a non-frozen accounting producer instead.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: Decimal lot-level realized gross/net from actual entry/exit quantities, multiplier, fee/slippage provenance; tests using current plan-sized oracle must change, historical outcomes/caches and training labels need versioned recomputation (never silently rewrite immutable ledger), migration if durable lots added. B: reject partial/non-unit fills until accounting implemented; safe temporary fail-closed but loses valid exits unless reduce-only reconciles.
### My recommendation
A; gate incompatible fill states meanwhile without blocking emergency reduction.
### Acceptance and regression tests
2/10 and full close, partial entry, gap, multiplier ≠1 and both fees against independent Decimal oracle; reconcile outcome/ledger/replay by version; device evidence separate.

## F-002
### Auditor claim (short quote)
“All FILLs” are projected without environment filtering.
### What I read (files, line ranges, functions, callers)
`ledger/store.py:435-446,514-571,573-643`; `fsm.py:860-875,1158-1175,1295-1310`; `ops/backup.py:194-204`; grep of `positions_from_ledger` in apex/execution/ops/scripts. Plan has environment (`ledger/store.py:51-74`) but the projection accepts no environment argument.
### Reproduction (command, probe file, actual result)
`F-002.py/.out`: actual writer with PAPER BUY_OPEN 2 and LIVE SELL_OPEN 2 for BTC in one temporary DB returns net 0/FLAT, although the two synthetic account exposures are separate.
### Verdict and reasoning
CONFIRMED conditional S1: no physical shared account/device configuration verified; the dangerous mixed-DB behavior is reproducible if shared.
### Root cause
Unscoped FILL scan lacks validated fill→intent→plan ownership.
### Direct impact
PAPER/LIVE exposures may cancel in a shared database.
### Secondary effects and interactions (upstream/downstream)
Upstream writer accepts arbitrary fill payload environment; downstream FSM/bootstrap reconciliation and backup view consume unscoped projection. Ambiguous attribution must not default to LIVE; risk, identity and outcome lineage require explicit account scope.
### Contract and decisions
`APEX_GEN5.md:16877-16883`: “Reconciliation is a first-class invariant”; `PHASE2_DECISION_LOG.md:197` D4: “PAPER and LIVE are separate everywhere they are measured or displayed”. D4 overrides any generic unscoped projection interpretation.
### Frozen status and non-frozen alternative
Projection in non-frozen ledger module; no frozen DDL alteration required. Versioned non-frozen mapping/projection can join existing trade_plan where valid.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: versioned account-scoped fill linkage and explicit ambiguity refusal; existing mixed fixture expectations change, migration/backfill of historical ambiguous fills and reconcile-before-resume needed; hashes and replay cache for derived position states change, not original immutable raw entries. B: separate physical stores per environment, still reject ambiguous fills and preserve reconciliation when archives merge; multi-DB backup/migration cost.
### My recommendation
A plus physical separation defense in depth; never infer account solely from untrusted fill payload.
### Acceptance and regression tests
Opposing PAPER/LIVE fills in one DB, orphan fill, same intent reused and restart; independent per-account projection and no invented READY; validate device DB ownership read-only before migration.

## F-003
### Auditor claim (short quote)
“Average entry” includes historical OPENs after flat/reopen.
### What I read (files, line ranges, functions, callers)
`ledger/store.py:525-571` entire projection; `fsm.py:866-869,1168,1302` position consumers; `backup.py:200`; `tests/unit/test_ledger_store.py:525-654` position tests. Grep `average_entry_price` in apex/tests to check display consumers.
### Reproduction (command, probe file, actual result)
`F-003.py/.out`: real writer BUY 1@100, SELL_CLOSE 1, BUY 1@200; current net 1 and average entry 150 rather than 200.
### Verdict and reasoning
CONFIRMED S1 as financial position basis defect; no evidence any particular unrealized-P/L consumer actually reads this field at runtime.
### Root cause
`open_cost/open_quantity` only increase for `*_OPEN`; neither decrements/resets on closes.
### Direct impact
Current-position reported entry price is wrong after close/reopen.
### Secondary effects and interactions (upstream/downstream)
Upstream historical fills remain immutable; downstream projection/backup and any future margin or risk consumer would inherit wrong basis. F-010 malformed CLOSE is independent, so do not mask it by only resetting at net zero.
### Contract and decisions
`APEX_GEN5.md:16919-16921`: “SINGLE SOURCE OF TRUTH for position state — the ledger, reconciled against the exchange”; D4 `PHASE2_DECISION_LOG.md:197` ledger-fed exposure/loss. Owner D4 has precedence over generic prose if inconsistent; neither specifies stale lot basis.
### Frozen status and non-frozen alternative
Non-frozen ledger projection; use adapter-side lot accounting if changing any frozen execution kernel were contemplated.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: Decimal running cost basis with partial closes, flat reset, reversal validation; existing tests asserting lifetime-open average change, derived balance/replay hashes and caches invalidate, historical derived reports may require versioned recomputation; no frozen DDL rewrite. B: publish only net and mark average UNAVAILABLE until correct; prevents wrong value but loses position basis.
### My recommendation
A after choosing FIFO vs weighted average with owner; B as interim display mitigation.
### Acceptance and regression tests
Flat/reopen 200, partial close, short, reversal/orphan exit refusal, restart and persisted replay vs independent lot oracle.

## F-004
### Auditor claim (short quote)
Plan/outcome derivative tables commit before the ledger event.
### What I read (files, line ranges, functions, callers)
`ledger/store.py:256-359,448-478,761-830`; `paper_loop.py:106-160,572-590`; `fsm.py:550-560,785-800`; `data_catalog/store/sqlite_store.py:140-200,290-310` for real DDL/trigger/FK. Grep `append_trade_plan`, `append_outcome` across apex/scripts/tests. Outcome fixture inserted a valid setup_candidate FK first.
### Reproduction (command, probe file, actual result)
`F-004.py/.out` on a real temporary SQLite file with migrations: injected OSError on ledger INSERT after each earlier commit; `trade_plan rows=1 ledger=0` and `outcome rows=1 ledger=0`.
### Verdict and reasoning
CONFIRMED S1: demonstrated both windows (unlike original auditor's plan-only fault); failure injection is not a device crash.
### Root cause
Direct table writes/commit outside writer queue before the chain/audit transaction.
### Direct impact
Orphan plan or outcome survives failed append.
### Secondary effects and interactions (upstream/downstream)
`PlanQueue.materialized_ids` may suppress retries; FSM outcome and ledger reconcile disagree; replay identity and cache cannot treat derivative-table presence as proof of chain append. See F-006 for different open-transaction failure.
### Contract and decisions
`APEX_GEN5.md:16879-16883` immutability; `18438-18442`: “ledger has a single writer, and every state mutation of the execution FSM passes through that one writer queue”; `PHASE2_DECISION_LOG.md:194-209` D1 same FSM/ledger path for PAPER; no decision permits orphan materialization. Owner decisions supersede prose.
### Frozen status and non-frozen alternative
CP-1 table DDL frozen; write service/queue and transaction envelope are non-frozen.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: Queue atomic table+chain+audit in one SQLite transaction with rollback/commit confirmation; changes tests that inspect intermediate table rows and transaction timing; reconcile existing orphans before migration, re-version derived hashes/plan caches where identities depend on materialization; no frozen DDL edit. B: detect orphans on boot and quarantine, not a substitute for A because pre-crash orders may be ambiguous.
### My recommendation
A plus B on existing databases before permitting retries.
### Acceptance and regression tests
Inject failure after every write/commit for plan and outcome on file SQLite with triggers/FK, reopen connection, assert all-or-nothing and no duplicate submission.

## F-005
### Auditor claim (short quote)
Two concurrent `append_fill` calls with same fill ID can create two FILL records; conflicting reuse returns prior record.
### What I read (files, line ranges, functions, callers)
`ledger/store.py:314-359,435-446,499-571`, `data_catalog/store/sqlite_store.py:165-180` (no UNIQUE fill_id), `fsm.py:670-695`; `tests/unit/test_ledger_store.py:655-673`. Grep all `append_fill`, `find_by_fill` callers.
### Reproduction (command, probe file, actual result)
`F-005.py/.out`: real temp SQLite, `asyncio.gather` twice with same ID → `ledger_ids_different=True fills=2 net=2`; conflicting `intent-b/qty=7` returns old `intent-a/qty=1`, `intent_b_entries=0`.
### Verdict and reasoning
CONFIRMED S1 for concurrency and ownership collision. The duplicate interleaving is possible, not guaranteed every invocation.
### Root cause
Lookup happens before queue serialization; no DB uniqueness nor payload equivalence check.
### Direct impact
Double counted positions or silent fill misattribution.
### Secondary effects and interactions (upstream/downstream)
Producer FSM can regard a foreign fill as completed; reconciliation, realized P/L, hashes and replay evidence inherit corrupt record; E-014 adapter idempotency is a separate boundary.
### Contract and decisions
`APEX_GEN5.md:16915-16921`: “fill_id ... unique; a repeated key returns the previously recorded response and never resubmits”; `18439-18442` single writer serializes concurrent fills. `PHASE2_DECISION_LOG.md:1159` D50 addresses client order IDs, not fill IDs; no overriding owner exception.
### Frozen status and non-frozen alternative
Frozen CP-1 ledger DDL cannot be edited without owner; queue-side lookup/validation and an additive unique index migration outside frozen file (after collision cleanup) are available.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: Queue-side atomic lookup + strict canonical payload/intent comparison, append-only refusal/audit on mismatch; tests assuming merely ID-based replay change, duplicates need reconciliation/migration before adding unique index; derived positions/replay caches may change; no frozen source edit. B: physically separate writer per account alone does not fix same-account races.
### My recommendation
A with unique-index backstop authorized as an additive migration, not rewritten DDL.
### Acceptance and regression tests
2 and 10 concurrent identical IDs, mismatched payload/intent, restart and duplicate legacy DB; exactly one financial effect and explicit refusal, never rewrite existing fill.

## F-006
### Auditor claim (short quote)
Failed audit insert leaves ledger row in open transaction; a later append commits it without audit and breaks chain.
### What I read (files, line ranges, functions, callers)
`ledger/store.py:256-359` (`_writer_loop`, `_apply`, `append`); `data_catalog/store/sqlite_store.py:165-180,290-310` triggers; `tests/unit/test_ledger_store.py:902-946`; grep `verify_chain` consumers in `fsm.py:1244-1252`, `backup.py:199`, `run_apex.py:366`.
### Reproduction (command, probe file, actual result)
`F-006.py/.out` file SQLite with injected audit INSERT OSError: before next append `ledger=1 audit=0 head=None` (same connection, uncommitted); after next successful append `ledger=2 audit=1 chain.intact=False PARENT_LINK_BROKEN`.
### Verdict and reasoning
CONFIRMED S1; first row's durability is demonstrated only after the next commit. Not a physical disk-fault proof.
### Root cause
No rollback or poisoned-writer state on `_apply` failure; head remains old while transaction retains first INSERT.
### Direct impact
An earlier failed event is later committed without audit/valid parent link.
### Secondary effects and interactions (upstream/downstream)
FSM gets exception but ledger may later contain its event; boot/recovery, outcome, identity and order attribution become inconsistent. F-004 is the early-commit counterpart.
### Contract and decisions
`APEX_GEN5.md:16879-16883`: immutable/hash-chained ledger; `18438-18442`: one writer serializes state; `19075-19083`: recovery validates sequence/parents. No owner decision in `PHASE2_DECISION_LOG.md:194-210,1155-1175` licenses a half-committed record; decisions take precedence if later policy appears.
### Frozen status and non-frozen alternative
Frozen ledger DDL unchanged; fix writer transaction/error handling in non-frozen `apex/ledger/store.py`.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: explicit rollback on any write/commit exception and poison writer until head/DB verified; tests expecting continued writes without recovery change; new failures may require recovery migrations for historical unaudited rows, no raw hash rewrite. B: rollback and continue only after independent integrity verification, faster recovery but greater ambiguity on COMMIT-unknown; cannot assume commit failure equals no commit.
### My recommendation
A, with explicit COMMIT-unknown state and restart reconciliation.
### Acceptance and regression tests
Audit insert, ledger insert and COMMIT fault; use second read-only SQLite connection after restart; compare count/chain/audit and gate all next entries until verified.

## F-007
### Auditor claim (short quote)
Hash binds only raw; column tamper/validly linked duplicate event can leave `intact=True`.
### What I read (files, line ranges, functions, callers)
`ledger/store.py:96-99,168-185,336-359,397-422,645-673,703-709`; frozen `sqlite_store.py:165-180,291-307` (ledger_no_update/delete triggers); `fsm.py:1244-1252`, `backup.py:199`, tests `test_ledger_store.py:349-396`. Grep verify-chain consumers in apex/scripts.
### Reproduction (command, probe file, actual result)
`F-007.py/.out`: normal UPDATE rejected `LEDGER_APPEND_ONLY`; **only in disposable fixture** drop update trigger, set quantity 1→9, `net=9`, `intact=True`; add synthetically well-linked row with duplicate raw event_id without dropping INSERT guard: `records=2 intact=True event_ids_unique=False ledger=2 audits=1`.
### Verdict and reasoning
CONFIRMED S1 for insufficient verifier despite ordinary trigger protection. Does not prove an attacker can bypass the production trigger or forge an independently anchored hash.
### Root cause
`verify_chain` checks `raw` and prior hash only, not row↔raw financial columns, event uniqueness, audit completeness, typed parent integrity or external anchor.
### Direct impact
Verifier can report green on financially inconsistent rows and unaudited inserts.
### Secondary effects and interactions (upstream/downstream)
FSM recovery, backups, ledger projection and downstream account/risk may trust `intact` and wrong quantity; distinguishing immutability prevention from detection matters.
### Contract and decisions
`APEX_GEN5.md:16879-16885`: “T_LEDGER (covert insert/modify ... breaks hash chain)”; `19075-19083` integrity gate includes event sequence and parents; `19106-19107` IDs/parents acceptance. No owner decision in `PHASE2_DECISION_LOG.md` explicitly weakens these checks; later decisions override prose if any are adopted.
### Frozen status and non-frozen alternative
Frozen CP-1 schema/triggers retain protection. Add verification/sidecar metadata in non-frozen ledger or backup layer; do not silently alter frozen columns.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: versioned verification binding all persisted money/identity fields plus event uniqueness/audit linkage; legacy chain hashes cannot be recomputed in place, so require versioned compatibility and attested migration/sidecar; recovery tests and cache/hash consumers change, no historical ledger rewrite. B: rely on triggers only; cannot detect missing audits/direct inserts and is insufficient.
### My recommendation
A with explicit legacy status and external integrity anchor for adversarial threat model.
### Acceptance and regression tests
Normal UPDATE blocked; in disposable fixture bypass trigger and tamper stored quantity/price, direct duplicate event insert, delete audit after controlled trigger bypass; all fail new integrity verdict while valid historical versions remain distinguishable.

## F-008
### Auditor claim (short quote)
`_blocked` is RAM-only; restart or failed `RECONCILE_RESOLVED` write loses the gate.
### What I read (files, line ranges, functions, callers)
`ledger/store.py:220-242,256-359,385-390,573-643,675-700`; `fsm.py:860-875,1160-1210`; `tests/unit/test_ledger_store.py:486-549`, `tests/integration/test_cp7_paper_loop.py:479-530` (caller coverage); grep `reconcile_against_exchange`, `blocked`, `require_reconciled` in apex/scripts.
### Reproduction (command, probe file, actual result)
`F-008.py/.out`: temp SQLite divergence `delta_count=1 blocked=True`, stopped writer/recreated writer on same connection → `restart_blocked=False`, fresh FILL accepted. Re-diverge; injected resolve INSERT fault → `post_fault_blocked=False`, FILL accepted. This tests writer restart, not whole-process/device crash.
### Verdict and reasoning
CONFIRMED S1 for the ledger gate. Boot separately may refuse trading (ISSUE-075); does not make this gate durable.
### Root cause
Non-durable `_blocked`, cleared before successful append of resolve event.
### Direct impact
Reconcile-first ledger entry block disappears without proof of resolution.
### Secondary effects and interactions (upstream/downstream)
Existing CORRECTION_EVENT remains in chain but is not rehydrated into block; FSM/order and account could advance if other guards permit. D57 durable risk ladder is separate state.
### Contract and decisions
`APEX_GEN5.md:19010-19023`: “Reconciliation uncertainty ... Block new entries; audit delta”; `16877-16880`: divergence forces RECOVERY_REQUIRED. `PHASE2_DECISION_LOG.md:194-210` D1 same FSM/ledger path; later owner decisions would win, none permits premature unblock.
### Frozen status and non-frozen alternative
Ledger writer/recovery non-frozen; additive non-frozen migration or derive state from immutable reconcile events; frozen CP-1 DDL unchanged.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: transactionally durable gate and recover outstanding correction/resolve with broker confirmation; new migration and boot tests, replay/state hashes/caches may change; historical unresolved records need quarantine, not auto-resolve. B: derive blocked state by scanning ledger at startup; avoids schema migration but expensive/unindexed and must distinguish matched broker state from merely appended resolve.
### My recommendation
A plus reconciliation on boot; no unlock before successful committed resolve and verified broker match.
### Acceptance and regression tests
Mismatch→restart, resolve INSERT and COMMIT faults, rollback, match without evidence, match with durable resolved event; allow only latter, never block reduce-only exits.

## F-009
### Auditor claim (short quote)
Missing symbol bypasses ±1 tolerance applied to present symbols.
### What I read (files, line ranges, functions, callers)
`ledger/store.py:112-115,525-643`; `fsm.py:1190-1210` reconciliation consumer; `tests/unit/test_ledger_store.py:560-587`; grep `reconcile_against_exchange` in apex/scripts and boot implementation; `APEX_GEN5.md:19010-19023`.
### Reproduction (command, probe file, actual result)
`F-009.py/.out`: ledger .25, broker response containing zero → `delta_count=0 blocked=False`; empty broker response → `delta_count=1 blocked=True delta=-0.25`. This is a synthetic **complete** response assumption, not evidence a real empty response means zero.
### Verdict and reasoning
CONFIRMED S2 for inconsistent tolerance; do not convert transport errors or incomplete broker responses into “flat”. Limited false-block impact under valid complete response explains S2.
### Root cause
Second loop for unseen symbols checks `!=0` instead of `abs(qty)>tolerance`.
### Direct impact
Small absent positions falsely trigger RECOVERY_REQUIRED.
### Secondary effects and interactions (upstream/downstream)
Upstream response completeness must be verified; downstream FSM block/audit and boot reconcile semantics can diverge; blind unblocking could worsen E-011 incomplete-fetch hazard.
### Contract and decisions
`APEX_GEN5.md:19010-19019`: broker uncertainty “delta > ±1 unit” blocks entries; `16877-16880` no reconcile on disagreement. `PHASE2_DECISION_LOG.md:194-210` PAPER broker/ledger path, no exemption; owner decisions prevail if conflict.
### Frozen status and non-frozen alternative
Non-frozen reconcile method; no frozen DDL edit needed.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: same tolerance for verified-absent and present-zero after completeness proof; existing missing-symbol tests with >1 remain, new small-quantity assertions change; prior correction records immutable; replay/derived verdict caches may change; no DB migration. B: treat all absent symbols as UNKNOWN requiring manual reconcile; safer on incomplete responses but causes more false blocks.
### My recommendation
A only with explicit completeness bit, B for unknown response.
### Acceptance and regression tests
.25 present zero vs absent verified zero match; 2 absent diverges; timeout/partial page refuses without inferred zero; read-only device response schema evidence required.

## F-010
### Auditor claim (short quote)
Orphan `SELL_CLOSE` projects as SHORT instead of raising position-integrity error.
### What I read (files, line ranges, functions, callers)
`ledger/store.py:435-446,525-571`, `fsm.py:670-695,860-875`, tests `test_ledger_store.py:525-654`; grep of `positions_from_ledger` in apex/ops, apex/execution, scripts. Frozen DDL `sqlite_store.py:165-180` permits side in raw without close constraint.
### Reproduction (command, probe file, actual result)
`F-010.py/.out`: fault injected as synthetic missing OPEN upstream; real writer persists a standalone `SELL_CLOSE` qty2; projection returns `net=-2 direction=SHORT`, chain intact. File-backed SQLite with triggers, no real venue.
### Verdict and reasoning
CONFIRMED S1 for malformed fill projection, not evidence that production venue actually sends orphan exits. Unchecked close quantities can compromise recovery accounting.
### Root cause
Projection treats any `SELL_*` as subtraction and does not compare CLOSE to current net/direction; writer does not validate account position.
### Direct impact
Phantom opposite exposure from a close with no open.
### Secondary effects and interactions (upstream/downstream)
Upstream adapter/FSM may have additional guards but this API permits malformed entries; downstream reconciliation, backup and risk account state consume it. F-001 actual-fill P/L and F-003 stale basis are separate faults.
### Contract and decisions
`APEX_GEN5.md:16877-16883`: “Reconciliation is a first-class invariant”; `16919-16921`: position ledger single source of truth; D4 `PHASE2_DECISION_LOG.md:197` binds PAPER exposure to ledger. Later owner decision takes precedence, but none licenses inventing a SHORT on CLOSE.
### Frozen status and non-frozen alternative
Ledger projection and FSM non-frozen; leave frozen CP-1 schema untouched, validate in a versioned projection/adapter.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: preserve raw venue fill but quarantine invalid close in derived position/recovery, explicit correction after broker match; existing tests assuming signed sum may change, derived identity/replay hashes invalidate, legacy orphan rows require migration/quarantine (not ledger rewrite). B: reject at append before persist; simpler but loses raw external evidence during uncertainty and can block protective exits.
### My recommendation
A with strict admission check at FSM too; protect reduce-only evidence even when projection flags invalidity.
### Acceptance and regression tests
Orphan, over-close, wrong direction, partial valid close, independently authorized reversal, restart and broker mismatch; invalid CLOSE must not create position.

## F-011
### Auditor claim (short quote)
Unknown event parent is accepted and `verify_chain.intact=True`.
### What I read (files, line ranges, functions, callers)
`ledger/store.py:336-359,397-422,645-673`; `test_identity.py:219-247`; `PHASE2_HANDOFF_CP1.md:129`, `PHASE2_TRACEABILITY_MATRIX.md:15,47`; grep `parents=` and `verify_chain` in apex. Parent list also contains hash link/supersedes, not only event IDs.
### Reproduction (command, probe file, actual result)
`F-011.py/.out`: append SEED then DERIVED with nonexistent `ev-...`; real writer accepts, verifier reports `records=2 intact=True breaks=[]` on temp file.
### Verdict and reasoning
PARTIAL S2: orphan *event-typed* parent is provably accepted; indiscriminately requiring every parent string to match an event_id would wrongly reject legitimate hash/correction links. T-ID-002 end-to-end recovery not proved by this isolated API.
### Root cause
Untyped `parent_ids` mixes references, verifier checks only predecessor hash.
### Direct impact
A missing event parent can be reported as intact.
### Secondary effects and interactions (upstream/downstream)
Upstream producer can supply typed/untagged parents; downstream provenance/recovery fails to distinguish references, without proving an orphan occurred on device. F-007 integrity coverage distinct.
### Contract and decisions
`APEX_GEN5.md:19075-19083`: “check all parent_event_ids exist”; `19107`: “500 derived events; all parent_event_ids exist in ledger”. `PHASE2_DECISION_LOG.md:194-210,1155-1175` contains no override of event-parent acceptance; owner decisions take precedence over general contract prose.
### Frozen status and non-frozen alternative
Non-frozen writer/producer and additive typed-reference sidecar; frozen store DDL need not change.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: separate typed event/hash/correction links and validate only event links, version lineage; migration of legacy ambiguous parents, test oracle and derived hash/replay cache invalidation required. B: document verifier as hash-only and enforce parent existence upstream; less protection against direct append/recovery.
### My recommendation
A after owner decides legacy reference typing, reject ambiguous new events.
### Acceptance and regression tests
500 derived events with valid event parents and negative orphan; valid hash/supersedes accepted; restart verifier checks typed references and marks orphan non-intact.

## F-012
### Auditor claim (short quote)
Same-millisecond UUIDv7 may descend while verifier reports monotonic.
### What I read (files, line ranges, functions, callers)
`uuid_v7.py:1-38` (random rand_a/rand_b), `ledger/store.py:391-422,668-709`, `tests/unit/test_identity.py:209-229`, `APEX_GEN5.md:4114-4132,18626-18649,19105-19107`; grep `uuid_v7` consumers in apex/identity/ledger and tests.
### Reproduction (command, probe file, actual result)
`F-012.py/.out`: patched actual `uuid_v7` time/random returns descending same-ms IDs (`strictly_ascending=False`). Patch UUID source for real LedgerWriter and append two events with same timestamp in descending event-id order; `verify_chain.sequence_monotonic=True intact=True`. No fabricated algorithm substituted for repository UUID generator.
### Verdict and reasoning
PARTIAL S2: acceptance T-ID-001 demands strictly ascending event IDs, but blueprint's random UUIDv7 implementation example allows non-monotonic same-ms ordering. A contract/acceptance conflict needs owner resolution, not an assertion UUIDv7 itself is invalid.
### Root cause
Random same-ms bits; verifier `_monotonic` checks ledger IDs differ and timestamps nondecrease, not event_id ordering.
### Direct impact
T-ID-001 strict-ID assertion can fail in bursts while verifier reports healthy.
### Secondary effects and interactions (upstream/downstream)
Event identities/lineage and recovery sequence proofs may be affected, not a proven duplicate or order misroute. Any new ID scheme changes future UUIDs, fixtures, replay identities and audit logs but must not rewrite historical rows.
### Contract and decisions
`APEX_GEN5.md:19106`: “event_id strictly increasing; no duplicates”; `19075-19083`: startup validates sequence. `PHASE2_DECISION_LOG.md:1159` D50 governs deterministic *content* identities/intent hash but does not override operational UUID event ordering; owner decision wins over conflicting blueprint example after recorded ruling.
### Frozen status and non-frozen alternative
Non-frozen UUID helper/verifier; no frozen engine or store DDL edit. Sidecar sequence index in adapter possible without changing frozen UUID module.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: versioned monotonic UUIDv7 generation + verifier compares event IDs; concurrency/process restart/time reversal policy required, existing random-ID expectation tests change and future hash/identity caches may invalidate. B: owner explicitly redefines T-ID-001 to ledger-order/timestamp, verifier reports both; no identity migration, but strict event-ID promise withdrawn transparently.
### My recommendation
Seek owner A/B ruling before editing; use separate ledger sequence as ordering authority meanwhile.
### Acceptance and regression tests
Fixed ms 1000 IDs, concurrent creators, restart/clock rollback; verifier rejects whichever property the approved contract mandates, historical IDs treated version-aware.

## G-015
### Auditor claim (short quote)
20-token initial burst plus refill admits 39 sends in 0.95 s.
### What I read (files, line ranges, functions, callers)
`signaling.py:350-403,579-625,629-782`, `test_telegram_signaling.py:272-323`; grep `bucket_for`/`acquire`/`available` in apex/tests. Internal vs provider ceilings in blueprint.
### Reproduction (command, probe file, actual result)
`G-015.py/.out`: actual `MessageTokenBucket` with injected clock: `sent_between_t0_and_t0.95=39`. No network, provider behavior not claimed.
### Verdict and reasoning
CONFIRMED S1: algorithm fails both internal 20/s rolling window and 30/s provider ceiling in this constructed burst; actual 429 depends on real service.
### Root cause
Capacity 20 at t=0 and refill 20/s implement long-run rate, not no-burst sliding-window limit.
### Direct impact
Throttling risk and misleading claimed per-chat guarantee.
### Secondary effects and interactions (upstream/downstream)
Upstream P3 floods share bucket with P0; downstream retries, outbox/delivery and emergency alerts can be delayed. Separate from priority ordering G-023; no venue order impact demonstrated.
### Contract and decisions
`APEX_GEN5.md:17766`: “internal limiter = 20 messages per second per chat; provider ceiling = 30”; `18960-18961`: “No burst is permitted ... Implement sliding-window token bucket”. `PHASE2_DECISION_LOG.md:194-210,1155-1175` does not override those limits; owner decisions precede prose if later changed.
### Frozen status and non-frozen alternative
Non-frozen signaling limiter; no frozen params file should change. Policy logic can live in non-frozen scheduler.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: exact rolling-window per chat + bounded priority queue; tests assuming 20 immediate sends after idle change, timing/outbox and delivery metrics change; if persisted queue introduced add DB migration; no order/research retraining, but delivery/replay timing identities may differ. B: low-capacity leaky bucket with no burst (≤20/s), lower throughput and potential P0 starvation without separate lane.
### My recommendation
A with provider-ceiling backstop and G-023 priority design.
### Acceptance and regression tests
200 concurrent and sequential sends around 0, 0.95, 1.0 seconds; every trailing 1s interval ≤20, provider never >30; real provider acceptance remains unverified.

## G-016
### Auditor claim (short quote)
Concurrent identical sends bypass idempotency gate before key is stored.
### What I read (files, line ranges, functions, callers)
`signaling.py:411-442,629-665,666-782`, `test_telegram_signaling.py:221-249`; grep `send(` consumers in gateway/control_plane/scripts; `send(force=True)` bypasses gate explicitly.
### Reproduction (command, probe file, actual result)
`G-016.py/.out`: two concurrent real `SignalingPlane.send` calls, synthetic barrier transport holds both, output `transport_calls_before_release=2`, both sent True. No Telegram requests.
### Verdict and reasoning
CONFIRMED S1 for in-flight race; the probe intentionally synchronized the gap. Sequential dedup tests do not test concurrency.
### Root cause
Idempotency `exists` checked before first await; `store` occurs only after I/O.
### Direct impact
Duplicate messages from one signal identity.
### Secondary effects and interactions (upstream/downstream)
Consumes extra rate tokens, can amplify alert storm/retries, outbox has two entries. In-memory registry reset/replay durability is a separate audit item (G-014), not proved here.
### Contract and decisions
`APEX_GEN5.md:17768`: “Idempotency key: SHA-256(signal_id + timestamp_UTC + chat_id)”; `18168-18173`: P0 never drop; `PHASE2_DECISION_LOG.md:194-210` has no idempotency exception, owner decisions take precedence.
### Frozen status and non-frozen alternative
Non-frozen signaling/queue; no frozen DDL change. An additive outbox/reservation table can be outside frozen store.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: atomic per-key in-flight reservation and same-result waiters, define retry/UNKNOWN/cancel and durable state; duplicate/retry tests change, DB migration if durable, signal hash formula unchanged but delivery/outbox replay changes. B: coarse per-chat lock prevents race but also blocks P0 behind P3 (G-023).
### My recommendation
A integrated with durable priority outbox; avoid B.
### Acceptance and regression tests
2/10 simultaneous same-key sends → one transport call; mismatched payload same key refusal; failure/cancel/restart lead to exactly-once-or-UNKNOWN reconciliation, not blind resend.

## G-017
### Auditor claim (short quote)
Failed alert is deduplicated for 30 minutes even after transport recovers.
### What I read (files, line ranges, functions, callers)
`signaling.py:816-880` (`dedup_verdict`, `emit_alert`), `666-782` (`send` retries); `test_telegram_signaling.py:538-573`; grep runtime `emit_alert` in paper_loop/control_plane/scripts.
### Reproduction (command, probe file, actual result)
`G-017.py/.out`: synthetic transport fails three times; first STORAGE `emitted=False transport_calls=3`, second same trigger `DEDUP_SUPPRESSED transport_calls=3` despite fourth call configured to succeed. No real delivery assertion.
### Verdict and reasoning
CONFIRMED S1: suppression based on attempted, not delivered, alert can silence important non-exempt alert.
### Root cause
`_last_alert` set before ledger append/send, independent of outcome.
### Direct impact
Loss of retry opportunity inside 30-minute window.
### Secondary effects and interactions (upstream/downstream)
Storage/feed monitoring and operator escalation can be silent; exempt EXEC_RECOVERY/CIRCUIT_OPEN are not suppressed by this rule, but may fail for other reasons. Outbox durability separate.
### Contract and decisions
`APEX_GEN5.md:18168-18173`: P0 never drop; `18304-18309`: dedup except EXEC_RECOVERY and CIRCUIT_OPEN with logged alerts; `PHASE2_DECISION_LOG.md:194-210` has no authorization to mark failed delivery successful.
### Frozen status and non-frozen alternative
Non-frozen signaling; persistence can be additive migration outside frozen DDL.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: dedup on confirmed delivery or durable pending record and retry failed alerts; behavior of tests expecting attempt-based suppression changes, outbox DB migration if persisted, delivery/replay timeline changes but trading hashes/retraining do not. B: exempt STORAGE/FEED from dedup, smaller mitigation but floods on real failures.
### My recommendation
A, with honest UNKNOWN receipt handling.
### Acceptance and regression tests
Three failures then recovery gives fourth transport send; successful duplicates suppress; concurrent alerts, restart and exempt P0 behave as policy.

## G-018
### Auditor claim (short quote)
Ledger append/transport construction failures escape before alert delivery and can interrupt the cycle.
### What I read (files, line ranges, functions, callers)
`signaling.py:666-782,831-880`, `paper_loop.py:960-978,1060-1083`, `control_plane.py:920-937`; tests `test_telegram_signaling.py:352-372,538-573`; grep `emit_alert`, `check_storage` callers.
### Reproduction (command, probe file, actual result)
`G-018.py/.out`: injected ledger OSError → no transport calls, `alert_audit=1`; injected `transport()` factory OSError → `outbox_count=0`, exception escapes. Synthetic adapter, not an actual invalid token or disk fault.
### Verdict and reasoning
PARTIAL S1: exception boundaries proven, but actual serve without bot token constructs no signaling plane; cannot claim that particular missing-token path fires in ordinary serve. Cycle interruption depends on which callers await the alert, as shown by code, not a live outage.
### Root cause
Synchronous ledger append before transport; factory outside retry try; mutable audit appended before delivery outcome.
### Direct impact
Important alert can fail before attempt while audit records initiation.
### Secondary effects and interactions (upstream/downstream)
Potentially aborts a cycle before `manage_positions` where awaited; DB integrity failure must still prevent new entries, while Telegram outage must not block reduce-only. No bypass of ledger failure is safe.
### Contract and decisions
`APEX_GEN5.md:17748-17757`: “Telegram outage or delivery delay must not block protective execution”; `18168-18173`: signaling failure never blocks protective execution. D1 `PHASE2_DECISION_LOG.md:194` PAPER follows FSM/ledger/Telegram path; no owner override authorizes ignoring ledger write faults.
### Frozen status and non-frozen alternative
Non-frozen signaling/runtime; independent emergency delivery pending channel can be additive without changing frozen ledger DDL.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: separate ledger fail-closed admission from best-effort independently queued alert; catch transport-factory faults, durable unknown/pending state; affects exception-expecting tests, outbox migration and audit timing, no training change. B: catch all errors and continue is unsafe for ledger corruption; not recommended.
### My recommendation
A; protective exits must continue if only Telegram fails, new entries must stop if integrity cannot be recorded.
### Acceptance and regression tests
Inject ledger/transport factory/send failures before and after send; assert no new entry on ledger failure, continued reduce-only handling, honest pending/error records, no false delivery proof.

## G-023
### Auditor claim (short quote)
P0 waits behind queued P3 on one shared FIFO bucket/lock.
### What I read (files, line ranges, functions, callers)
`signaling.py:350-403,629-782`; `test_telegram_signaling.py:272-323`; grep `bucket_for`, `force`, `send` consumers in gateway/control_plane/scripts.
### Reproduction (command, probe file, actual result)
`G-023.py/.out`: after 20 initial P3, queue 44 P3; actual `SignalingPlane.send` P0 at tail → `urgent_queued=True`, `urgent_delivery_seconds` ≈2.2s with immediate synthetic transport. Value is scheduler/environment-specific, not a real Telegram latency measurement.
### Verdict and reasoning
CONFIRMED S1 for priority inversion; real P0 SLO remains **UNVERIFIED**. P0 is not given reserved admission, and `force` bypasses emission gate only.
### Root cause
All priorities share one per-chat token bucket and FIFO lock held during sleep.
### Direct impact
Emergency alert dispatch delayed by lower-priority traffic.
### Secondary effects and interactions (upstream/downstream)
G-015 burst and G-017 retries can worsen the queue; downstream operator containment feedback may arrive late, no proof of delayed venue orders.
### Contract and decisions
`APEX_GEN5.md:18168-18173`: P0 “never drop”, P3 “droppable”; `18963-18971`: P0 highest, P3 lowest. `PHASE2_DECISION_LOG.md:194-210` no override; owner decisions take precedence over blueprint.
### Frozen status and non-frozen alternative
Non-frozen signaling queue and limiter; frozen params not necessary to change.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: priority-aware bounded queue with P0 capacity reservation under global 20/s and provider 30/s; drop/degrade P3 by policy; timing tests change, possible durable outbox migration, delivery/replay metric behavior changes, no model retraining. B: separate per-priority buckets without aggregate ceiling risks 429, unacceptable alone.
### My recommendation
A integrated with G-015 rolling ceiling; no P0 bypass of provider safety.
### Acceptance and regression tests
Under 44 queued P3, failed/retried transport and 200 mixed messages, P0 admitted ahead of P3 within enforced rolling provider limit; device SLO measured separately.

## G-002
### Auditor claim (short quote)
EXPORT/BACKTEST_RUN handlers succeed without export or backtest.
### What I read (files, line ranges, functions, callers)
`scripts/run_apex.py:711-765,827-838` (`serve`, `_noop_handler`); `control_plane.py:488-515,866-891` (`register`, `dispatch`, callback), `gateway.py:277-309`; grep `BACKTEST_RUN`/`EXPORT` apex/scripts/tests, `test_telegram_control_plane.py:743-790` only supplied handlers.
### Reproduction (command, probe file, actual result)
`G-002.py/.out`: register actual `_noop_handler` on real ControlPlane; `dispatch('EXPORT')` and `dispatch('BACKTEST_RUN')` return `ok=True recorded=True` with no job/file. Synthetic configuration without env/credentials; no actual gateway traffic.
### Verdict and reasoning
CONFIRMED S1 for falsely reported success, entirely = ISSUE-073 known owner item (no beyond-known claim). Severity remains serious operator-facing missing function, not a claim that research backend is broken.
### Root cause
Composition registers `_noop_handler` as successful effect in serve.
### Direct impact
Accepted operator action has no product.
### Secondary effects and interactions (upstream/downstream)
Research/backtest and export are not called; downstream report/replay absent, but no exchange/order path. G-022 unsafe path validation becomes consequential only after real exporter wired.
### Contract and decisions
`APEX_GEN5.md:17837-17848`: Export path → “Send/Share the resulting file”; `17892-17904` Lab Backtest stays active. `PHASE2_DECISION_LOG.md:194-210` D4 separates PAPER/LIVE displayed/exported balances; no later owner authorization for noop-success. ISSUE-073 schedules CP-16; owner decision/log takes precedence over generic promise of readiness.
### Frozen status and non-frozen alternative
Run composition/control-plane non-frozen; backtest engine frozen and need not be changed to report NOT_WIRED or call existing read-only job API.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: until CP-16, register refusal handler instead of success; changes tests/gateway acknowledgements, no hash/training/migration. B: integrate background jobs and exact audited output path, introduces queue/job persistence, migration and output identity/hash/replay contract; keep frozen research backtest via non-frozen adapter.
### My recommendation
A immediately for truthful status, B in authorized CP-16 with tested job contract.
### Acceptance and regression tests
Without worker, explicit refusal; with worker, returned durable job/file and error outcome, no cross-environment export; never assert `recorded=True` as actual completion.

## G-021
### Auditor claim (short quote)
Info always displays `HEALTHY` and “Data Coverage=140” without real health/coverage.
### What I read (files, line ranges, functions, callers)
`control_plane.py:97-102,450-487,576-587,675-695`; `test_telegram_control_plane.py:548-563`; grep `screen_info` in gateway/control_plane/tests; `APEX_GEN5.md:17897-17904`, D30 `PHASE2_DECISION_LOG.md:523-532`.
### Reproduction (command, probe file, actual result)
`G-021.py/.out`: instantiate ControlPlane without store/health; `screen_info()` returns `{'System Status': 'HEALTHY', 'Data Coverage': 140}`. This is constant output, not a claim about device data.
### Verdict and reasoning
PARTIAL S2: constants are confirmed, but blueprint §5.5 **literally** prescribes the 140-combination Info screen and “HEALTHY”, so a bare claim that those literals violate this UI contract is overstated. In an operational screen, labeling capacity as observed coverage and health as live is misleading; newer fail-closed safety principles and D30 disambiguate training scope (20), not data capacity (140).
### Root cause
Info method does not depend on measured boot/feed/data state; screen template conflates capacity with observation.
### Direct impact
False impression of live health/coverage if shown as measurements.
### Secondary effects and interactions (upstream/downstream)
Upstream actual boot/store quality absent; downstream operator confidence, not automatic order or model training; D30 20 base training cells never equal 140 available symbol/timeframe combinations.
### Contract and decisions
`APEX_GEN5.md:17897-17904`: “full data coverage (140 symbol/timeframe combinations), and System Status (HEALTHY)”; `PHASE2_DECISION_LOG.md:523-532` D30: “train-e11 ... 1h and 4h ... (20 cells), never over all 14 timeframes”. Later D30 wins for training, does not imply observed data coverage; owner should clarify UI literal versus measured-status obligation.
### Frozen status and non-frozen alternative
Non-frozen control-plane/status producer; frozen engines and store DDL untouched.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: show “capacity 140” separately from measured cells/boot state with timestamp/quality, UNAVAILABLE on absent evidence; fixture tests of hardcoded fields change, live reporting cache/identity version may change, no DB migration unless status snapshots persisted. B: relabel current constants as “example/capacity”, do not assert operational HEALTHY; smaller interim UI fix, no retraining.
### My recommendation
A after owner clarifies §5.5 literal; B until a measured status producer exists.
### Acceptance and regression tests
Store absent, 0/partial/140 measured cells, DEGRADED boot and stale feed: accurate labels and timestamps; no implication 20 trained cells equals 140 data cells; device coverage still needs read-only evidence.
