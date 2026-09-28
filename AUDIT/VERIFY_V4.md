# V4 independent verification — baseline 85b2c155d7b054a468379ddfd802eb239d0801f9

Read-only source/contract examination; probes used synthetic identities, injected faults and disposable SQLite with the repository migrations and triggers. No venue, Telegram, device database, or secret value was intentionally accessed. **Protocol limitation:** `ls -la .env` in repository root returned `ls: cannot access '.env': No such file or directory` (exit code 2; no contents read). The prior exploratory default-Config invocation therefore had no repository-root `.env` to parse in this sandbox; environment variables, if any, were not inspected. **Original disclosure:** an early exploratory G-009 invocation constructed default `Config()` before the committed probe was corrected; this could have parsed a local `.env` if one existed. No value was printed, retained or used intentionally; the logs cannot establish whether that file existed. All committed probes inject synthetic configuration. This possible accidental access does not meet the requested no-`.env` assurance. Baseline command `git rev-parse HEAD && git log -1 --oneline` returned the full baseline SHA and `85b2c15 Merge pull request #25 ...`. Report source: `/tmp/AUDIT.md` (fetched 690e2d88); index is not evidence. Commands below assume `PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1`. All measured results are **fixture-only**, not evidence of trades or device latency. A green test suite does not discharge the counterexamples.

| ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option |
|---|---|---|---|---|---|---|
| G-009 | CONFIRMED | S0 | S0 | No | D-002 distinct; ISSUE-073 distinct | A: durable admission gate |
| F-001 | CONFIRMED | S1 | S1 | No | D58 PAPER simulator pending | A: actual-fill accounting |
| F-002 | CONFIRMED (conditional shared DB) | S1 | S1 | No | D4 separate PAPER/LIVE | A: scoped projection |
| F-003 | CONFIRMED | S1 | S1 | No | — | A: current cost basis |
| F-004 | CONFIRMED | S1 | S1 | DDL frozen | — | A: atomic writer envelope |
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
| G-022 | CONFIRMED (latent writer impact) | S2 | S2 | No | = ISSUE-073 for noop only | A: canonical contained path |
| G-015 | CONFIRMED | S1 | S1 | No | — | A: rolling window |
| G-016 | CONFIRMED | S1 | S1 | No | — | A: atomic in-flight reservation |
| G-017 | CONFIRMED | S1 | S1 | No | — | A: delivery-aware dedup |
| G-018 | PARTIAL | S1 | S1 | No | — | A: separate delivery from protection |
| G-023 | CONFIRMED (synthetic timing) | S1 | S1 | No | — | A: priority admission |
| G-001 | CONFIRMED | S2 | S2 | No | D17 | A: central redaction |
| G-003 | CONFIRMED | S1 | S1 | No | D57 distinct; D-002 distinct | A: atomic recovery |
| G-004 | CONFIRMED | S2 | S2 | No | — | A: typed delivery result |
| G-008 | CONFIRMED | S1 | S1 | No | G-009 distinct | A: OWNER auth |
| G-010 | CONFIRMED | S1 | S1 | No | D57 distinct | A: pending vs committed |
| G-011 | CONFIRMED | S2 | S2 | No | G-013 distinct | A: durable unique nonce |
| G-012 | CONFIRMED | S1 | S1 | No | = D57 L1/L2; beyond: lock/rehydration | A: durable state |
| G-013 | CONFIRMED | S1 | S1 | No | G-011/012 distinct | A: durable receipt/effect |
| G-014 | CONFIRMED | S1 | S1 | No | — | A: durable outbox |
| G-020 | CONFIRMED | S2 | S2 | No | — | B: truthful close-only |
| G-027 | CONFIRMED | S2 | S2 | No | D9 veto10-12 distinct | A: manual alert type |
| G-006 | CONFIRMED | S1 | S1 | No | G-024/025 interactions | A: keyboard codec + transport |
| G-007 | CONFIRMED (group configuration conditional) | S1 | S1 | No | D17/D20 | A: sender+private auth |
| G-024 | CONFIRMED (callback reachability unverified) | S1 | S1 | No | G-006/G-013 | A: per-update isolation |
| G-025 | CONFIRMED | S2 | S2 | No | G-006/G-024 | A: callback ack |
| G-028 | PARTIAL | S2 | S2 | No | G-004 distinct | A: split provider/internal receipt |
| G-029 | CONFIRMED (provider rejection unverified) | S2 | S2 | No | G-014/017 interactions | A: safe formatting |
| G-026 | PARTIAL | S2 | S2 | No | D17 retention | A: typed provenance |
| G-019 | CONFIRMED (composition scope) | S1 | S1 | No | D9; D-007 distinct | A: typed policy subscriber |
| G-005 | CONFIRMED (composition scope) | S1 | S1 | research/bootstrap.py | D5/D22 distinct | A: durable job control |

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
`APEX_GEN5.md:16875-16883`: reconciliation invariant and immutable ledger; `16915-16923`: unique fill identities and partial fills permitted. D4 (`PHASE2_DECISION_LOG.md:197`) binds PAPER exposure/realized loss to ledger, overriding any interpretation that the displayed balance alone is accounting. No owner decision authorizes using plan size as filled size.
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
`APEX_GEN5.md:17085-17090`: “single source of truth for position state (the ledger, reconciled against exchange)”; D4 `PHASE2_DECISION_LOG.md:197` ledger-fed exposure/loss. Owner D4 has precedence over generic prose if inconsistent; neither specifies stale lot basis.
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
`APEX_GEN5.md:16879-16891`: “T_LEDGER (covert insert/modify ... breaks hash chain)”; `19075-19083` integrity gate includes event sequence and parents; `19106-19107` IDs/parents acceptance. No owner decision in `PHASE2_DECISION_LOG.md` explicitly weakens these checks; later decisions override prose if any are adopted.
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
`APEX_GEN5.md:18168-18173`: P0 never drop; `18476-18480`: dedup except EXEC_RECOVERY and CIRCUIT_OPEN with logged alerts; `PHASE2_DECISION_LOG.md:194-210` has no authorization to mark failed delivery successful.
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
`APEX_GEN5.md:17835-17840`: Export path → “Send/Share the resulting file”; `17892-17895` Lab Backtest stays active. `PHASE2_DECISION_LOG.md:194-210` D4 separates PAPER/LIVE displayed/exported balances; no later owner authorization for noop-success. ISSUE-073 schedules CP-16; owner decision/log takes precedence over generic promise of readiness.
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

## G-022
### Auditor claim (short quote)
Path validator accepts sibling prefix and `..` escape although EXPORT currently noop.
### What I read (files, line ranges, functions, callers)
`control_plane.py:360-390,879-891` (`validate_export_request`, callback/dispatch), `scripts/run_apex.py:728-733,827-838` (noop composition), `test_telegram_control_plane.py:391-430,775-792`; grep `validate_export_request` in apex/scripts/tests.
### Reproduction (command, probe file, actual result)
`G-022.py/.out`: actual validator returns valid=True/errors=() for `/Download/APEX_Reports_evil/x.csv` and `/Download/APEX_Reports/../escape.csv`, as well as a valid in-root path. No file is created and no export is executed.
### Verdict and reasoning
CONFIRMED S2 for validator boundary defect; actual out-of-root write is **not** confirmed, because runtime EXPORT uses noop (= ISSUE-073). Its future impact is conditional on wiring a real exporter.
### Root cause
Raw `str(path).startswith(root.rstrip('/'))` rather than normalized ancestor validation and writer-bound file descriptor.
### Direct impact
Validator's alleged export-root guarantee is false.
### Secondary effects and interactions (upstream/downstream)
Upstream Telegram export request may include malformed path; downstream real writer is presently absent, so no proven file leak; future exporter/replay identity must consume validated canonical path, not unvalidated input. Symlink and TOCTOU concerns require separate filesystem policy.
### Contract and decisions
`APEX_GEN5.md:17837-17844`: “Browse to path `/Download/APEX_Reports/` ... Send/Share the resulting file”; D17 `PHASE2_DECISION_LOG.md:205` forbids printing/committing secrets. No owner decision allows writing outside export root. ISSUE-073 covers noop handler only and does not excuse validation; owner decisions take precedence.
### Frozen status and non-frozen alternative
Non-frozen control-plane/export adapter; frozen research/store untouched.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: canonicalize root and candidate, use relative-to-root/path-handle safe writer (symlinks refused or constrained); tests currently accepting raw prefix change, future export metadata/hash and replay path IDs may change; migration of existing export metadata only if any exists, no model retraining. B: reject all caller-supplied paths and write generated files solely under root; simpler but changes wizard UX and still must prevent symlink escapes.
### My recommendation
B until an approved filesystem-safe writer can implement A; keep G-002 explicit refusal meanwhile.
### Acceptance and regression tests
Sibling root, `..`, absolute/relative, Unicode, symlink and directory swap before write all refused/contained; valid path generated and atomically opened under root, not merely validated; real device path policy still needs confirmation.

## G-001
### Auditor claim (short quote)
“owner/watchdog chat id” appears unmasked in boot and Config repr despite D17.
### What I read (files, line ranges, functions, callers)
`apex/config.py:32-80,121-200` (`ENV_NAMES`, `_SENSITIVE`, `_load_env`, `Config.__repr__` and accessors), `scripts/run_apex.py:106-124,192-209,504-509,615-621,1127-1141` (`_redacted`, `_boot`, bootstrap/status/main); `grep -Rn '_redacted\|repr(cfg)\|Config(' scripts apex` shows boot, bootstrap and status print `_redacted`, other constructors default to Config. No real Config was constructed in the probe.
### Reproduction (command, probe file, actual result)
`PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V4/G-001.py > AUDIT/probes_V4/G-001.out 2>&1`: synthetic `Config` allocated via `__new__`, `_env` populated with test-only identifiers; `owner/watchdog repr_contains=True boot_contains=True`, synthetic bot token both False. No `.env` opened.
### Verdict and reasoning
CONFIRMED S2: explicit disclosure of contact IDs, not API tokens; log disclosure is limited observability/privacy impact, severity matches auditor. Device logs/access policy not assessed.
### Root cause
`Config._SENSITIVE` masks three credentials but not the two chat identifiers; `_redacted` deliberately echoes both, contrary to later D17.
### Direct impact
IDs appear in `Config` repr and CLI environment-surface print, potentially copied to diagnostics.
### Secondary effects and interactions (upstream/downstream)
Upstream owner-approved chat identity comes from environment; downstream boot/bootstrap/status stdout, logs and support exports may carry IDs. Not evidence of compromised Telegram authorization or venue orders; makes G-007 identity mistakes more consequential only if IDs are exposed to another actor.
### Contract and decisions
`APEX_GEN5.md:1150-1155`: “Runtime env names (values never in this document)” includes TELEGRAM_OWNER_CHAT_ID; `PHASE2_DECISION_LOG.md:205` D17 explicitly says “Secrets (bot token, chat id, venue key/secret) ... never printed by any command”. D17 is later binding owner decision and wins over any earlier boot-display convention.
### Frozen status and non-frozen alternative
`apex/config.py` and `scripts/run_apex.py` non-frozen; no frozen params/DDL changes needed.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: central redaction policy for IDs across repr, CLI and exception payloads (SET/UNSET); changes literal-output tests/operator debugging, no DB migration/retraining or trading hash change. B: redact only boot output leaves repr/support leak, insufficient. IDs must remain available internally for routing, so do not remove from config.
### My recommendation
A; add integration stdout checks with synthetic canaries across boot/status/bootstrap without contacting services.
### Acceptance and regression tests
Sentinel owner/watchdog IDs never appear in repr/boot/bootstrap/status or exception logs, tokens stay masked, internal equality/routing still uses correct ID; read-only device logs require separate authorized review.

## G-003
### Auditor claim (short quote)
“RECOVER only clears ratchet”, while `paused/new_positions_disabled/safe_mode/read_only` persist.
### What I read (files, line ranges, functions, callers)
`control_plane.py:393-439,450-487,800-850,898-977` (`EmergencyRatchet`, `_action`, `_emergency_effect`); `gateway.py:276-320` callback dispatch; `paper_loop.py:1103-1140` (`run`, `_control_paused`); `scripts/run_apex.py:725-735` handler registration; `test_telegram_control_plane.py:814-923`. Grep `RECOVER`, `.paused`, `new_positions_disabled` across apex/scripts/tests shows no clearing outside this callback and initialization.
### Reproduction (command, probe file, actual result)
`PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V4/G-003.py` → `.out`: real L1 confirmation via synthetic successful handler, `before=('L1',True,False,False,False)`; OWNER RECOVER `ok=True recovered=True`, `after=(None,True,False,False,False)`, real `PaperRuntime._control_paused()=True`. No order or Telegram connection.
### Verdict and reasoning
CONFIRMED S1: in-process UI says recovered but `run()` still skips cycles. It does not prove safe resumption would be appropriate without health/reconcile; indiscriminate clearing would be unsafe. Related G-012 is restart durability, not same-process inconsistency.
### Root cause
`_action('RECOVER')` delegates only to `ratchet.recover`; the control flags are separate mutable attributes without a state transition protocol.
### Direct impact
Operator-facing recovery acknowledgement disagrees with runtime pause gate.
### Secondary effects and interactions (upstream/downstream)
Upstream OWNER/nonce state and handler success do not run readiness checks; downstream `run()` may skip `run_cycle`, including position management. Risk ladder is independent of these control flags (D57); D-002/ISSUE-073 noop emergency handlers limit whether real venue protective effects occur. G-009 lock is separate state. No replay/ledger transition is recorded for this recovery.
### Contract and decisions
`APEX_GEN5.md:17922-17926`: “Only OWNER can recover from an Emergency state”; `19068-19072`: RECOVERY→NORMAL only after startup reconciliation; `18424-18434`: restore emergency-ladder state and refuse new trade before READY. `PHASE2_DECISION_LOG.md:194-210` D1 same PAPER FSM/ledger; D57 recorded/not implemented (`1173`), does not authorize unsafe unpause. Binding owner decision supersedes earlier generic UI language.
### Frozen status and non-frozen alternative
Control-plane/runtime and additive state migration non-frozen; do not change frozen risk engines/DDL or frozen YAML. Adapter/fabric gate can reconcile risk state without modifying frozen files.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: durable atomic RECOVER state transition after independent health/broker/ledger checks, flags updated together and confirmation returns actual status; requires migration/restart tests, changes existing tests expecting immediate `recovered=True`, new control-state hashes/replay/backup identity may change, no model retraining. B: interim explicit `RECOVERY_PENDING` refusal, retaining flags; safer than falsely claiming success but delays legitimate restart.
### My recommendation
A with B until health+reconcile is implemented; do not clear pause on unaudited callback alone.
### Acceptance and regression tests
L1/L2/L5→OWNER recover with healthy and unhealthy broker/boot, fault during persist, process restart, reduce-only position exits while new entries blocked, UI/runtime/ledger all agree; USER denied.

## G-004
### Auditor claim (short quote)
Gateway/BootstrapService mark returned `{sent: False}` as delivered.
### What I read (files, line ranges, functions, callers)
`gateway.py:230-275,308-355` (`reply`, `_reply_from`, handle_update); `scripts/run_apex.py:839-857` (`_telegram_reply`); `bootstrap_service.py:1229-1276,1400-1460,1570-1609` (`report`, `SignalingNotifier`); `signaling.py:666-782` (`send` returning `SendResult.sent`); grep `\.report(` and `reply(` in apex/scripts/tests and gateway bootstrap tests.
### Reproduction (command, probe file, actual result)
`G-004.py/.out`: real `TelegramGateway.reply` with notifier returning `{sent:False}` yields `delivered=True`; real `BootstrapService.report` on a synthetic instance also yields `delivered=True`; real `SignalingNotifier.__call__` passes actual `sent=False` from injected plane back to caller. No network.
### Verdict and reasoning
CONFIRMED S2; limited to delivery acknowledgement, not evidence all messages fail or trading decisions change. When notifier raises instead, both methods correctly return delivered=False.
### Root cause
Success is defined as “notifier returned without raising”, not its `sent` result.
### Direct impact
False delivery receipts for failed sends.
### Secondary effects and interactions (upstream/downstream)
Upstream SignalingPlane returns `sent=False` for known failure and can supply a reason; downstream gateway replies, bootstrap progress and UI/operator assurance misstate it. G-028 (fabricated receipt when transport returns `{}`) is a distinct upstream false-positive. No impact on risk authorization by Telegram delivery per contract.
### Contract and decisions
`APEX_GEN5.md:17747-17753`: Telegram is downstream, delivery is not execution prerequisite; `18168-18175`: P0 “never drop”, signaling failure never blocks protective execution; `PHASE2_DECISION_LOG.md:194-210` D1 routes PAPER FSM/ledger/Telegram, D17 protects identifiers but does not redefine “delivered”. Owner decisions prevail; no decision permits claiming receipt without `sent`.
### Frozen status and non-frozen alternative
Gateway, BootstrapService, SignalingNotifier non-frozen; no engine/store/params edit needed.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: typed notifier result with sent/unknown/error, propagate reason, keep reply-status separate from command execution; tests expecting delivered=True on any normal return change, delivery caches/reporting metrics and persisted notification status may need versioning, no DB migration unless durable outbox introduced, no retraining. B: throw on `sent=False` in notifier, works with current exception handling but loses structured error and creates inconsistent call contracts.
### My recommendation
A; never turn “not raised” into delivery proof.
### Acceptance and regression tests
Stub returns sent=False/True/UNKNOWN, raises, times out: gateway and bootstrap delivery statuses reflect actual receipt; downstream retries do not re-execute inbound action; real provider evidence required for device delivery.

## G-008
### Auditor claim (short quote)
An unknown USER can `/lock`; only OWNER can `/unlock`.
### What I read (files, line ranges, functions, callers)
`control_plane.py:103-115,162-211,725-795` (`AccessControl.check`, `handle_command`, `_command`, `_broadcast`, `locked_verdict`), `gateway.py:147-179,276-309` update/command route, `test_telegram_control_plane.py:660-710`; `grep -Rn '/lock\|handle_command'` in scripts/apex/tests. The control path does not call OWNER check for `/lock` but does for `/unlock`.
### Reproduction (command, probe file, actual result)
`G-008.py/.out`: actual ControlPlane with synthetic OWNER=123 and unknown USER=456, no signaling endpoint: USER `/lock` returns `ok=True state=True`; same USER `/unlock` returns `OWNER_ONLY`, OWNER unlocks. No venue/Telegram traffic.
### Verdict and reasoning
CONFIRMED S1 for unauthorized operator-control denial-of-service; no proven trading halt because G-009 independently found lock lacks execution gating. Severity reflects operator UI disruption and security contract, not claimed market impact.
### Root cause
Asymmetric authorization of two state-mutating commands; role assignment uses synthetic chat ID, and lock branch skips `access.check` entirely.
### Direct impact
Non-owner blocks `/start`, screen callbacks and bootstrap commands until owner unlocks.
### Secondary effects and interactions (upstream/downstream)
Upstream G-007 group chat sender ambiguity can widen principal misuse; downstream gateway refuses operational interactions; lock doesn't protect entry (G-009), so incident operator may lose control while execution continues. No ledger/canonical hash changes on command.
### Contract and decisions
`APEX_GEN5.md:1158-1161`: USER “cannot ... operate the Emergency Ladder”; `17913-17926`: “Emergency (5 levels, OWNER-only)” and Panic Lock commands in §5.7; `1170-1174` `/lock` as incident response. `PHASE2_DECISION_LOG.md:205` D17 restricts chat identifiers; no owner decision grants USER lock authority. Later owner decision prevails, but §5.7 does not literally state an independent `/lock` OWNER-only sentence; interpret incident containment and least privilege together.
### Frozen status and non-frozen alternative
ControlPlane/Gateway non-frozen; no changes to frozen risk engines/schema/params.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: check verified human OWNER before `/lock`, audit denials, and protect role against group identity confusion G-007; tests relying on permissive USER lock change; no migration/retraining or existing hash rewrite, future audit identity/response changes. B: allow USER lock only under an explicit owner-approved emergency policy, with rate limit/recovery; not currently authorized and exacerbates DoS.
### My recommendation
A, coordinated with G-007 principal validation and G-009 real execution gate.
### Acceptance and regression tests
Known/unknown USER, group USER with owner destination and callback/command cannot lock; OWNER in authenticated private channel can; denial audited, no state change; exercise repeated/restart cases.

## G-010
### Auditor claim (short quote)
Selecting L5 before YES ratchets state; NO leaves lower levels forbidden.
### What I read (files, line ranges, functions, callers)
`control_plane.py:212-265,393-439,800-858,902-975` (`ConfirmationRegistry`, `EmergencyRatchet.request`, `_action`, `_emergency`, `_emergency_effect`); `gateway.py:277-309` callback entry; tests `test_telegram_control_plane.py:802-860` (NO asserts flags but not ratchet). Grep `ratchet.request` in apex/tests finds `_emergency` call pre-confirmation.
### Reproduction (command, probe file, actual result)
`G-010.py/.out`: synthetic OWNER selects L5 with no handler/send; `unconfirmed_level=L5`, `safe_mode=False`; NO consumes nonce but level remains L5; L1 now refused `RATCHET_DOWN_FORBIDDEN`. Real policy functions, no venue/device.
### Verdict and reasoning
CONFIRMED S1: confirmed operator intent and ratchet state diverge. Not evidence a genuine L5 protective action occurred. Severity accounts for inability to select safer intended L1 without recovery.
### Root cause
`_emergency` calls `ratchet.request(level)` before confirmation, regardless of NO/expiry/handler result.
### Direct impact
A cancelled or expired high-level request prevents lower-level requests.
### Secondary effects and interactions (upstream/downstream)
Upstream nonce UI has pending vs committed ambiguity; downstream operator safety controls and G-003 RECOVER may be used to clear stale level but leave other flags. G-012 restart loses this RAM state; D-002/ISSUE-073 downstream L3-L5 noops do not justify ratchet changes.
### Contract and decisions
`APEX_GEN5.md:17915-17926`: ratchet downgrades forbidden and Yes/No confirmation “irreversible” with 90-second nonce; the prohibition presupposes *confirmed* emergency level, not an unconfirmed request. `PHASE2_DECISION_LOG.md:194-210` D1 controls PAPER path, `1173` D57 deferred durability; no owner decision authorizes NO to escalate. Later owner decision takes precedence over earlier blueprint prose.
### Frozen status and non-frozen alternative
Control-plane policy non-frozen; risk engines/schema/frozen params untouched, optional additive durable pending-state migration outside frozen store.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: separate pending proposal and committed level; commit only after authorized YES and success or explicitly classified partial outcome; tests asserting ratchet state at request time change, control-state replay/audit hashes and persisted migration may change, no model retraining. B: revert ratchet after NO/timeout is racy with concurrent YES and other higher-level requests unless serialized/durable; unsafe shortcut.
### My recommendation
A, with serialized per-principal transition and safe handling of partial protective effects; do not roll back a real confirmed higher level.
### Acceptance and regression tests
L5→NO/expiry then L1 allowed; handler failure and cancellation not reported as completed; L1→YES commits once; interleaved L2/L5 proposals and restart preserve only confirmed level; risk/order/ledger evidence separately checked.

## G-011
### Auditor claim (short quote)
Reissuing confirmation in same millisecond resets a consumed nonce and lets an old click authorize again.
### What I read (files, line ranges, functions, callers)
`control_plane.py:137-146,212-265,800-858,901-937,1001-1005` (`nonce_key`, registry issue/consume, `_action`, `_emergency`), `gateway.py:277-309` callback route, tests `test_telegram_control_plane.py:251-319,817-861`. Grep `nonce_key`, `confirmations.issue` and `consume` in apex/scripts/tests shows no independent idempotent approval record.
### Reproduction (command, probe file, actual result)
`G-011.py/.out`: actual ConfirmationRegistry with fixed UTC millisecond/monotonic clock: issue→YES→issue same action/chat→YES with *old* key returns both authorized=True, `same_key=True`, one stored nonce. No real Telegram click or venue effect.
### Verdict and reasoning
CONFIRMED S2 as deterministic replay vulnerability at registry boundary, but probability of two human clicks within one ms unknown; in-process `update_id` dedup only blocks repeated identical update, not a new update carrying the same key. Severity limited without actual operational exploitation.
### Root cause
`nonce_key` deterministically hashes only action/chat/millisecond; issuing overwrites even consumed `_nonces[key]` with `consumed=False`.
### Direct impact
Old confirmation identifier can be reused after rapid re-issue.
### Secondary effects and interactions (upstream/downstream)
Upstream user-visible nonce binding and G-006 keyboard delivery; downstream `_execute_confirmed` may re-invoke emergency/other handler. G-013 update replay after restart and G-010 early ratchet compound risk. No proof of twice-executed order; no durable audit of individual confirmation lineage.
### Contract and decisions
`APEX_GEN5.md:17922-17926`: “Confirmation is Yes/No, irreversible, with a 90-second nonce”; `PHASE2_DECISION_LOG.md:194-210` D1 shared PAPER path; none overrides single-use law. Later owner decision wins; a synthetic same-ms counterexample defeats the present interpretation.
### Frozen status and non-frozen alternative
Control-plane registry non-frozen; additive durable nonce store outside frozen CP-1 DDL optional; no engine/params edit.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: cryptographically unique per-issue nonce plus atomic consumed registry and retention across restart, callback binds principal/action/expiry; tests for deterministic nonce hashes change, new persistence/migration and approval-audit identities/caches change, no retraining or historic ledger rewrite. B: add incrementing process counter; closes same-ms collision in process but restart reuse/durability remains.
### My recommendation
A, with durable single-use approval for capital/emergency actions.
### Acceptance and regression tests
Frozen millisecond issue→YES→issue→old key refused; concurrent issue keys distinct; wrong chat/action, expiry, cancellation, restart, duplicate update ID all fail closed; verify downstream handler exactly once.

## G-012
### Auditor claim (short quote)
Process restart forgets lock, emergency level and all containment flags.
### What I read (files, line ranges, functions, callers)
`control_plane.py:393-487,758-775,902-975` (`EmergencyRatchet`, `ControlPlane.__init__`, `_command`, `_emergency_effect`); `scripts/run_apex.py:711-765` new service/control on serve; `paper_loop.py:351-455` constructor/boot (initializes risk-ladder DB, does not hydrate control flags), `gateway.py:230-262` offset initialization; grep `apex_risk_ladder_state`, `control.` and `ControlPlane(` in apex/scripts/tests.
### Reproduction (command, probe file, actual result)
`G-012.py/.out`: real control plane with synthetic successful L5 handler and OWNER `/lock`; old state `locked=True level=L5 paused=True disabled=True safe_mode=True read_only=True`; new instance all False/None. No real crash, broker or Telegram; synthetic handler does not close positions.
### Verdict and reasoning
CONFIRMED S1 for missing persistence/reconstitution of UI/control state, but no evidence that device runtime reached L5 or subsequent trades happened. Risk ladder DB migration is separate and does not rehydrate ControlPlane.
### Root cause
State/ratchet/lock live solely as instance attributes; serve reconstructs fresh instance and boot never binds state to ledger/recovery record.
### Direct impact
Previously acknowledged control state disappears when process restarts.
### Secondary effects and interactions (upstream/downstream)
Upstream Emergency/lock confirmations can appear successful (D-002 limits real effects); downstream `PaperRuntime._control_paused()` no longer blocks cycles. F-008 ledger reconcile gate durability, G-003 in-process recovery and G-013 offset replay are distinct; order admission still has independent boot verdict (ISSUE-075). Control-state hash/replay/audit cannot be reconstructed.
### Contract and decisions
`APEX_GEN5.md:18424-18434`: SELF_TEST “emergency-ladder state restored from the latest backup”, no new trades before READY; `1170-1177` incident containment/recovery; `17915-17926` OWNER emergency semantics. `PHASE2_DECISION_LOG.md:1173` D57 schedules durable L1/L2 state for CP-15 and higher watchdog levels CP-16, **overrides any reading that all are already implemented**; this row flags beyond D57 the missing ControlPlane lock/safe-mode rehydration and acknowledgement coherence, not a duplicate owner item. D-002/ISSUE-073 are separate no-op handlers.
### Frozen status and non-frozen alternative
Control-plane/serve/PaperRuntime migration path non-frozen. Frozen risk kernel and CP-1 DDL should not be rewritten; additive table/adapter outside frozen files.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: durable versioned control transition log with atomic ack and boot reconcile to risk ladder/ledger, fail closed on ambiguity; migration, backup/restart tests and derived control/replay hashes change, no E11 retraining; historical state cannot be inferred from absent records. B: refuse state-changing commands until durable store exists, protects against false ack but operator loses incident tool (requires independent watchdog).
### My recommendation
A staged alongside D57, with B truthful refusal until persistence exists; never auto-unpause uncertain state.
### Acceptance and regression tests
L1/L2/L5 and lock across new process with file SQLite, mid-write fault, same update replay and broker reconciliation; no new order until confirmed control/boot state; reduce-only exits continue; device backup drill still required.

## G-013
### Auditor claim (short quote)
Update replay guard and poll offset are RAM-only, so a repeated update can invoke handler again after restart.
### What I read (files, line ranges, functions, callers)
`control_plane.py:332-357,450-487,725-743,800-827` (`UpdateDeduplicator`, command/callback), `gateway.py:84-114,230-342,385-405` (`AiogramUpdateSource`, `TelegramGateway`), `scripts/run_apex.py:724-735` new gateway each serve; tests `test_ops_telegram_gateway.py:215-240,261-281`. Grep `updates.record`/`.offset` in apex/scripts/tests; no durable update checkpoint observed.
### Reproduction (command, probe file, actual result)
`G-013.py/.out`: real `TelegramGateway.run_once` and ControlPlane, synthetic Source returns update_id=91 twice across two fresh gateway/control instances; first and second each `handled=1 offset=92`, handler `calls=['pause','pause']`. Synthetic polling, not Telegram replay behavior proof.
### Verdict and reasoning
CONFIRMED S1 for restart replay possibility and absent durable exactly-once gate. Telegram may redeliver if prior offset was not confirmed; same-instance guard works, but user device replay occurrence remains unverified.
### Root cause
`UpdateDeduplicator._seen` bounded RAM dictionary and both gateway/source offsets initialized None on each construction; effect and offset not atomically persisted.
### Direct impact
Previously accepted command can run twice when update is redelivered after restart.
### Secondary effects and interactions (upstream/downstream)
Upstream poll delivery/ack semantics unknown without device; downstream bootstrap effects, future emergency/export jobs and audit may duplicate. G-011 nonce reuse and G-012 state reset compound uncertainty; G-016 outbound idempotency is a different key/transport. Ledger/trade identity requires separate idempotency independent of Telegram update IDs.
### Contract and decisions
`APEX_GEN5.md:17922-17926`: irreversible Yes/No confirmation; `18943-18951` cached result/stable key semantics (“On receipt of request with key K”); `PHASE2_DECISION_LOG.md:194-210` D1 same FSM/ledger path, no override allowing repeated OWNER actions. Owner decisions take precedence; idempotency of action must be anchored beyond client offset.
### Frozen status and non-frozen alternative
Gateway/control-plane non-frozen; additive inbound receipt/effect table in non-frozen migration rather than changing frozen CP-1 store/engines.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: durable update_id→result/effect idempotency checkpoint in same transaction as action where possible; external effects need their own stable idempotency key and UNKNOWN reconciliation; DB migration, response/cache/approval hash versioning and restart tests change, no training. B: persist only offset, faster but can lose an unexecuted update if offset committed first or repeat effect if committed after.
### My recommendation
A, with explicit acknowledgement ordering and idempotent downstream handler; do not treat offset alone as exactly-once proof.
### Acceptance and regression tests
Effect→crash before next poll/ack, restart same update, exactly one durable effect with prior result replay; 4097 updates eviction, out-of-order updates, handler exception and network timeout; no live Telegram test without owner permission.

## G-014
### Auditor claim (short quote)
“Durable outbox” is a RAM list lost on object recreation and failed messages have no recovery worker.
### What I read (files, line ranges, functions, callers)
`signaling.py:407-441,579-626,666-807` (registry/outbox/send), `scripts/run_apex.py:717-725,839-856` plane construction/reply, `gateway.py:261-274`; `test_telegram_signaling.py:350-410,470-520`; `PHASE2_TRACEABILITY_MATRIX.md:318-321`. Grep `outbox`/`idempotency`/`replay_outbox` throughout apex/scripts/tests: `self.outbox.append` only, no durable reload/retry worker.
### Reproduction (command, probe file, actual result)
`G-014.py/.out`: real signaling send with synthetic P0 and transport 3 injected failures returns sent=False, in-memory outbox has FAILED entry (droppable=False); new plane outbox empty, registry empty and no `replay_outbox` API. No actual process crash, provider or persistent DB.
### Verdict and reasoning
CONFIRMED S1 for lack of persistence/recovery, not a claim that Telegram actually lost any message on device. Alert ledger optional append is not a pending outbound message log with attempt/ack.
### Root cause
Outbox and idempotency solely per-object lists/dicts; `_record_outbox` is append-only RAM and no pending worker exists.
### Direct impact
Pending/failed notification evidence and retries disappear across restart.
### Secondary effects and interactions (upstream/downstream)
Upstream risk/decision/ledger alert producers may record an ALERT independently; downstream G-017 suppression, G-016 in-flight race, G-023 P0 priority and G-028 receipt semantics complicate safe resend. Replaying messages without durable provider receipt may duplicate sends; do not assume exactly-once Telegram delivery.
### Contract and decisions
`APEX_GEN5.md:18168-18175`: P0 “never drop”, P3 droppable; `18980-18983`: P0/P1 preservation; `19214` explicitly “durable outbox/no silent drop”; `PHASE2_DECISION_LOG.md:194-210` D1 routes PAPER Telegram, no owner override downgrading durability. Traceability PASS refers to tests, not recovery proof; owner decisions supersede prose.
### Frozen status and non-frozen alternative
Signaling/ops persistence non-frozen; additive outbox table via non-frozen migration; leave frozen CP-1 store and original params untouched.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: durable pending/attempt/receipt outbox with stable identity and retry worker, UNKNOWN for ambiguous send; DB migration/disk writes, tests expecting RAM-only state change, delivery/replay identities/cache versioning needed, no model retraining. B: event-log-derived outbox from ledger ALERT alone misses arbitrary signal/reply and lacks receipt; insufficient without expanding event payload/version.
### My recommendation
A, with P0 reservation and per-chat rolling ceiling, and no blind resend after uncertain provider acknowledgement.
### Acceptance and regression tests
Pending→network fail→process restart and recovery, receipt absent/late/duplicate and exhausted retries; exactly one durable logical message, delivery outcome honest, no P0/P1 eviction; temporary file SQLite with repository DDL and fault injection.

## G-020
### Auditor claim (short quote)
Chart plots OHLCV low as close and advertises layers not drawn.
### What I read (files, line ranges, functions, callers)
`signaling.py:267-344` (`_matplotlib_agg`, `CHART_LAYERS`, `render_chart`, `_png_size`), `test_telegram_signaling.py:700-772`, `tests/integration/test_cp7_paper_loop.py:935-979,1088-1096`; grep `render_chart(` apex/scripts/tests finds no runtime production render caller outside tests (chart readiness distinct). `APEX_GEN5.md:17962-17972,18235-18256` charts contract.
### Reproduction (command, probe file, actual result)
`G-020.py/.out`: actual `render_chart` and Agg PNG (1200×800, 28,218 bytes), instrumentation wraps real `Axes.plot` without replacing chart logic. Supplied OHLCV low [0.5,0.7], close [1.5,2.6]; only plotted y=[0.5,0.7], returned `layers=('BOS','FVG')`, unavailable empty. Synthetic candles, no user screen/provider.
### Verdict and reasoning
CONFIRMED S2 at callable boundary; no claim any production operator has viewed this chart, since runtime usage was not found by grep. Metadata advertisement does not prove overlays were rendered.
### Root cause
`row[3]` interpreted as closes for six-column OHLCV while close is index 4; requested layers copied to result without implementation of overlay rendering.
### Direct impact
Wrong price curve and misleading layer claims if chart delivered.
### Secondary effects and interactions (upstream/downstream)
Upstream schema/quality supplied by caller must be explicit; downstream Telegram image/G-029 formatting and operator interpretation, not risk/order decisions. Snapshot/lineage metadata is passed through but says nothing about plotted data; rendering caches/identity could change after correction.
### Contract and decisions
`APEX_GEN5.md:17962-17972`: “Charts overlay OHLCV, Swing High/Low, BOS ... [layers], and carry quality ... snapshot_id ... lineage”; `18243-18248` chart function shows overlay intent. `PHASE2_DECISION_LOG.md:194-210` D1 PAPER path and `148` ISSUE-CP7-003 module-frozen literals, neither authorizes advertising unrendered layers. Later owner decisions take precedence over illustrative PNG quality/dpi example.
### Frozen status and non-frozen alternative
Signaling/chart renderer non-frozen; do not change frozen engines/formulas to fake overlays. Adapter may supply governed plotted layers from read-only evidence.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: bind documented OHLCV schema, draw verified close and only computed overlays, unavailable for missing layers; breaks visual golden PNG/metadata tests, changes image hashes/caches/replay attachments, no DB migration/training if purely display. B: close-only graph plus explicitly unavailable overlays until governed inputs exist; smaller scope, avoids false claims but limits functionality.
### My recommendation
B immediately for honest output, then A per layer with provenance tests.
### Acceptance and regression tests
OHLCV low≠close, instrument artist data + PNG; each requested layer actually drawn or unavailable; no display/file writes, verify operator image via test double, real-data evidence remains unverified.

## G-027
### Auditor claim (short quote)
Confirmed L1/L2/L3 manual action emits `CIRCUIT_OPEN`, which policy reserves for daily loss/veto 10.
### What I read (files, line ranges, functions, callers)
`control_plane.py:902-975` (`_emergency`, `_emergency_effect`), `signaling.py:90-133,816-880` (`ALERT_POLICY`, dedup/emit), `tests/unit/test_telegram_control_plane.py:900-919`; `grep -Rn 'CIRCUIT_OPEN' apex/telegram apex/risk scripts/tests` shows control-plane manual trigger and risk error name; no real daily-loss subscriber established by this row.
### Reproduction (command, probe file, actual result)
`G-027.py/.out`: real ControlPlane L1 confirm with synthetic successful handler and recording signaling: alert `CIRCUIT_OPEN`, `metric=emergency_L1`, `threshold=PAUSE`; real `ALERT_POLICY` defines CIRCUIT_OPEN metric `daily_realized_loss`, threshold `per veto 10 table`. No venue or real Telegram send.
### Verdict and reasoning
CONFIRMED S2 for mislabelled alert semantics; not proof of market loss or a working veto-10 alert. Existing unit test explicitly expects mislabeled L1 alert.
### Root cause
Generic emergency callback maps L1–L3 into loss-circuit alert type instead of distinct manual-control event.
### Direct impact
Owner may interpret a manual pause as a daily-loss circuit trip.
### Secondary effects and interactions (upstream/downstream)
Upstream no loss metric required; downstream P0 priority and dedup exemption accrue wrong alert counts/audit interpretation. G-019 missing real loss subscriber is separate; D-002/ISSUE-073 noop handlers mean downstream effects not guaranteed. No direct order decision or training change proved.
### Contract and decisions
`APEX_GEN5.md:18468-18477`: “Daily realized loss | per veto 10 table | CIRCUIT_OPEN”; `17915-17926`: distinct manual Emergency semantics. `PHASE2_DECISION_LOG.md:204-205` D9 adds CIRCUIT_OPEN to error registry for vetoes 10–12; this later owner decision broadens error-code use, but does **not** classify manual L1 as a loss circuit. D9 precedence does not rescue manual metric mislabelling.
### Frozen status and non-frozen alternative
Control-plane/signaling alert adapter non-frozen; risk engine frozen and need not be altered. New message type requires owner policy approval, not edits to frozen YAML.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: distinct MANUAL_EMERGENCY/PAUSE notification and reserve CIRCUIT_OPEN for governed veto policy; changes tests `test_l1_to_l3_raise_a_circuit_open_alert`, alert IDs/metrics, reporting/audit caches and replay classification; no DB migration unless alert schema enum restricted, no retraining. B: send plain operator reply without policy alert, simpler but may lose urgent visibility unless approved channel established.
### My recommendation
A after owner settles policy name/priority; retain independent veto10 alert generation.
### Acceptance and regression tests
L1–L3 with no loss never emit CIRCUIT_OPEN; veto10 daily realized-loss event does emit policy-matched metric/threshold; dedup/priority and audit logs checked without sending Telegram.

## G-006
### Auditor claim (short quote)
Menu keyboards are not sent; their own callback payloads would be rejected as ACTION_UNKNOWN.
### What I read (files, line ranges, functions, callers)
`control_plane.py:575-725,800-896,980-1007` (`render`, `_callback_for`, `_action`); `gateway.py:191-225,260-382` (`render_screen`, `_reply_from`, `reply`); `signaling.py:215-249,506-568,666-739` (inline keyboard and transport seam); `scripts/run_apex.py:839-856` `_telegram_reply` builds `SignalMessage` without inline_keyboard; tests `test_telegram_control_plane.py:493-520`, `test_ops_telegram_gateway.py:167-237`; `grep -Rn 'inline_keyboard\|render_screen\|reply_markup'` apex/scripts/tests.
### Reproduction (command, probe file, actual result)
`G-006.py/.out`: real gateway `/start` calls injected notifier with exactly 2 args (chat/text), no markup; real `ControlPlane.render('MAIN_MENU')` first/back buttons `MAIN_MENU:TRADING`, `MAIN_MENU:BACK`; real handle_callback returns ACTION_UNKNOWN for both. Synthetic OWNER, no Telegram network.
### Verdict and reasoning
CONFIRMED S1: linked runtime path cannot deliver generated keyboard, and if independently delivered its callbacks aren't recognized. Direct `SCREEN:TRADING` tests inject a callback the renderer does not produce; no claim real users can send forged callbacks or click absent buttons.
### Root cause
Renderer produces keyboard data but gateway flattens screen to text; callback serializer uses `screen:slug` whereas dispatcher accepts `SCREEN`, `BACK`, `HOME`, etc. `SignalMessage.inline_keyboard` remains empty in composition reply.
### Direct impact
Screen/wizard navigation and emergency menu unavailable through generated Telegram replies.
### Secondary effects and interactions (upstream/downstream)
Upstream operator receives `/start` text; downstream G-024 malformed callback exception path can surface once keyboards are wired. G-025 callback ack also absent. No market/ledger/identity impact until command actions are reachable; manually typed `/lock` still operates separately (G-008/009).
### Contract and decisions
`APEX_GEN5.md:17802-17816` main menu/navigation with Back/Home; `17821-17830` trading wizard and Yes/No nonce; `17913-17926` emergency controls. `PHASE2_DECISION_LOG.md:148` ISSUE-CP7-003 freezes module literals only, not a license to omit actual keyboard; `194-210` D1 PAPER path. Owner decisions override earlier UI prose but none resolves this wiring.
### Frozen status and non-frozen alternative
Gateway/control-plane/signaling adapters non-frozen; do not touch frozen engine/DDL or original YAML. Reply interface can carry keyboard as typed metadata.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: unify one action→callback codec with dispatcher and pass `reply_markup` end-to-end via notifier/transport; tests using synthetic SCREEN payloads must add generated-button roundtrips, callback/approval identities and delivery caches may change, no DB migration unless pending callbacks persisted, no retraining. B: text-only slash commands for all actions avoids keyboards but violates approved screen UX/confirmation.
### My recommendation
A with generated-keyboard acceptance tests before enabling capital-affecting buttons.
### Acceptance and regression tests
Bot double inspects actual reply_markup from `/start`; click every generated button, Back/Home/wizards and YES/NO, see valid screen/action; reject oversized data and unauthorized principal, retain existing callback ack G-025 follow-up.

## G-007
### Auditor claim (short quote)
Group destination chat ID takes precedence over human sender ID for OWNER authorization.
### What I read (files, line ranges, functions, callers)
`gateway.py:128-183,276-342` (`extract_update`, `_chat_id`, `handle_update`, `_bootstrap`), `control_plane.py:162-211,450-487,725-775,800-938` (`AccessControl`, command/callback), `config.py:163-175` chat ID accessors; `test_telegram_control_plane.py:28-33`, `test_ops_telegram_gateway.py:160-240`. Grep `extract_update`, `access.check`, `role_of` apex/scripts/tests; there is no private-chat or verified sender check.
### Reproduction (command, probe file, actual result)
`G-007.py/.out`: group `-1001234567890` in synthetic OWNER allowlist, different sender=987654321; real gateway `pause` reaches injected handler (`accepted=True`, call count1). Callback `EMERGENCY:L1` from same foreign sender is treated OWNER, gives nonce/raises ratchet (G-010). No Telegram/network or device owner config.
### Verdict and reasoning
CONFIRMED S1 **conditional on an OWNER group chat ID being configured**; if owner chat is exclusively private and sender verified, this particular group exploit is not established. Test fixture’s group-shaped negative IDs show API permits configuration, not that real device uses it.
### Root cause
Authorization principal conflated with reply destination (`chat.id` prioritized over `from.id`) and chat type not checked.
### Direct impact
Any sender in allowed group can invoke group-OWNER commands at policy seam.
### Secondary effects and interactions (upstream/downstream)
Upstream D17 secrecy of owner ID does not establish human identity; downstream bootstrap/ratchet and, if D-002 noop fixed, capital-protective actions could be triggered by non-owner. G-008 USER `/lock` separately lacks even group check; G-011 nonce binding to chat rather than sender compounds shared-group risk. No real order effect demonstrated.
### Contract and decisions
`APEX_GEN5.md:1159-1163`: USER cannot operate emergency state, human capital actions need two-factor-protected account; `17913-17926`: Emergency OWNER-only. `PHASE2_DECISION_LOG.md:205` D17 chat IDs held only on phone and D20 watchdog chat = owner chat; neither permits using a group *destination* as verified human identity. Owner decision prevails over any UI convenience.
### Frozen status and non-frozen alternative
Gateway/access policy/config adapter non-frozen; no frozen engines, original params or store DDL change. OWNER mapping migration may need identity-confirmation on device (not secret disclosure).
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: bind authorized sender principal (`from.id`) plus private chat requirement for capital/emergency, destination remains reply target, reject channel_post/anonymous sender; tests with group OWNER IDs must change, existing group config may be denied pending owner re-enrolment, identity/audit hashes and cache keys change, no training/DB migration unless durable roles added. B: group policy with sender-specific allowlist and per-action MFA, more complexity and anonymity risk.
### My recommendation
A; first obtain device policy evidence without exposing chat IDs, then fail closed for non-private actions.
### Acceptance and regression tests
Group owner destination with foreign sender denied for message/callback/channel_post; private owner sender allowed; forward/anonymous malformed sender denied and logged; test group real Telegram semantics only with owner permission.

## G-024
### Auditor claim (short quote)
Invalid callback handler error escapes `run_once`, outside poll-error handling, and interrupts cycle.
### What I read (files, line ranges, functions, callers)
`control_plane.py:664-695,800-827,834-859` (render unknown-screen raises, handle_callback dispatch), `gateway.py:277-309,385-422` (handler then offset update, catches only GatewayError around source poll), `paper_loop.py:955-985` (await gateway before position management), `test_ops_telegram_gateway.py:261-320`. Grep `SCREEN_UNKNOWN`, `poll_errors`, `run_once` apex/ops/scripts/tests. No generated callback is currently sent via keyboard (G-006).
### Reproduction (command, probe file, actual result)
`G-024.py/.out`: synthetic source yields `SCREEN:NOT_A_SCREEN` followed by `/myid`; actual gateway `run_once` raises `ControlPlaneError(SCREEN_UNKNOWN)`, `handled=[]`, `poll_errors=[]`, `offset=None`; second message unprocessed. No actual provider or venue.
### Verdict and reasoning
CONFIRMED S1 for uncontained handler exception and potential cycle interruption. Exploitability from real Telegram remains unverified because G-006 omits buttons and provider callback shape may restrict arbitrary payload; a stale/changed UI callback is still possible after wiring.
### Root cause
`try/except GatewayError` surrounds only `source.get_updates`; per-update `handle_update` and `_reply_from` are outside handler-error containment.
### Direct impact
One bad update aborts processing of subsequent updates, can abort `run_cycle` before manage_positions.
### Secondary effects and interactions (upstream/downstream)
Upstream malformed/stale callback or handler failure; downstream offset remains old, so G-013 replay risk increases; `paper_loop.run_cycle` may skip later position management; G-025 callback ack unavailable. No actual order cancellation or fill evidence.
### Contract and decisions
`APEX_GEN5.md:17747-17753`: Telegram failure/delay “must not block protective execution”; `18985-18987`: failed callback should be MESSAGE_UNACKED. `PHASE2_DECISION_LOG.md:194-210` D1 PAPER FSM/Telegram path, no override permitting exception to stop protection. Owner decision precedence intact.
### Frozen status and non-frozen alternative
Gateway/ControlPlane/PaperRuntime non-frozen; no risk engines/store DDL edits.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: isolate each update, audit/refuse expected ControlPlaneError, alert unexpected errors, continue protective cycle, advance durable offset only with recorded resolution; changes tests expecting propagated exception, introduces durable checkpoint if combined G-013, changes inbound audit/replay identity, no retraining. B: catch at `paper_loop.run_cycle` and continue position management, protects exits but leaves later updates/offset unresolved; temporary containment only.
### My recommendation
A plus B as defense in depth; never mark update acknowledged before an auditable refusal or safe recovery.
### Acceptance and regression tests
Invalid callback followed by valid update, synthetic handler raises, notifier fails; next update processed and management runs; poll_errors vs handler_errors separated; durable offset/restart semantics proven.

## G-025
### Auditor claim (short quote)
Callback ID parsed but not acknowledged with Telegram callback-query API.
### What I read (files, line ranges, functions, callers)
`gateway.py:77-115,140-180,230-310,385-405` (`AiogramUpdateSource`, `extract_update`, `handle_update`, `run_once`), `signaling.py:506-568` (TelegramTransport only send_message/send_photo), `scripts/run_apex.py:839-856` reply notifier; `test_ops_telegram_gateway.py:166-240,261-320`; `grep -Rn 'answerCallbackQuery\|answer_callback_query\|callback_id\|MESSAGE_UNACKED' apex/telegram scripts/tests` yields only callback_id extraction, no ack/UNACKED consumer.
### Reproduction (command, probe file, actual result)
`G-025.py/.out`: real `AiogramUpdateSource` and Gateway with injected fake Bot whose `get_updates` returns valid `SCREEN:INFO` callback and whose `answer_callback_query` records calls: processed INFO and offset3, `callback_ack_calls=[]`. No real Telegram endpoint.
### Verdict and reasoning
CONFIRMED S2 for absent acknowledgement path; actual Telegram client spinner/timeout depends on provider, not measured. G-006 absent buttons limits current UI reachability, not correctness of callback handling once introduced.
### Root cause
Callback id extracted by normalizer but omitted from parsed record/transport action; notifier creates separate text message only.
### Direct impact
No explicit callback-query acknowledgement for success/refusal/error.
### Secondary effects and interactions (upstream/downstream)
Upstream clicks may remain pending; downstream repeated clicks can interact with G-011 nonce, G-013 replay and G-024 handler exceptions. A text reply delivery (G-004) is not callback ack; no order effects proven.
### Contract and decisions
`APEX_GEN5.md:18985-18987`: “Telegram callback: 1 callback per message; if callback fails, mark MESSAGE_UNACKED”; `17747-17753` Telegram downstream and must not block protective execution. `PHASE2_DECISION_LOG.md:194-210` D1 shared FSM path and D17 secret custody, no override of callback ack. Decisions prevail over contract prose if later revised.
### Frozen status and non-frozen alternative
Gateway/transport non-frozen, add ack method to injected bot/source adapter; no frozen engine/store/params.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: ack every callback exactly once with callback_id; distinguish ack from handler effect and sent text reply, persist/alert MESSAGE_UNACKED on failure; tests with fake bot/receipt change, durable ack state migration if persisted, identity/replay keys change, no model retraining. B: reply text only; does not fulfil provider callback protocol, insufficient.
### My recommendation
A coordinated with G-024 per-update containment and G-013 durable effect, avoid acknowledging unprocessed capital action as completed.
### Acceptance and regression tests
Bot double verifies ack for success/denial/invalid/replay and failure outcome MESSAGE_UNACKED; callback effect remains at-most-once across restart; actual provider behavior requires authorized device test.

## G-028
### Auditor claim (short quote)
Empty transport response becomes synthetic message ID and `sent=True`.
### What I read (files, line ranges, functions, callers)
`signaling.py:506-568,666-807` (`TelegramTransport`, `AiogramTransport`, `send`, `_record_outbox`); `scripts/run_apex.py:839-856` `_telegram_reply` consumes `SendResult.sent`; `gateway.py:261-275` delivery; `test_telegram_signaling.py:352-372`; grep `message_id`, `sent` consumers in apex/telegram/scripts.
### Reproduction (command, probe file, actual result)
`G-028.py/.out`: real SignalingPlane with injected transport responding `{}`: calls1, sent=True, state ACTIVE, quality Q2, UUIDv7 fallback message_id, outbox status SENT. `{}` is a deliberately incomplete test-double response, not an observed aiogram response or proof Telegram rejected the send.
### Verdict and reasoning
PARTIAL S2: absent provider receipt is mislabeled successful in the public adapter contract, but blueprint §9 also uses UUIDv7 for an internal `message_id`; an internally generated ID is not inherently invalid *if it is clearly separate from provider receipt*. Here that separation/receipt validation is absent. Real provider delivery remains device-evidence-needed, not rejected.
### Root cause
`response.get('message_id') or uuid_v7()` conflates provider acknowledgement and internal operational identity, sets success unconditionally if call does not raise.
### Direct impact
No receipt can be reported as delivered with fabricated ID.
### Secondary effects and interactions (upstream/downstream)
Upstream fake/real provider response schema; downstream G-004 delivered flag, G-014 outbox and G-017 dedup may trust invented success. No trading instruction or order changed; replay of ambiguous provider outcome requires UNKNOWN rather than blind retry.
### Contract and decisions
`APEX_GEN5.md:18029-18031`: return UUIDv7 message ID *if success*; `18089-18091`: “Message ID invalid | QX INVALID”; later row expects verification of invalid receipt and earlier example names internal UUIDv7, so owner should clarify dual identity. `PHASE2_DECISION_LOG.md:194-210` D1/17 do not override receipt semantics; decisions take precedence.
### Frozen status and non-frozen alternative
Signaling adapter/result non-frozen, no engine/store/params changes required; durable outbox migration G-014 could add distinct provider receipt column.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: distinguish immutable internal event UUIDv7 from optional provider receipt, validate provider schema, return UNKNOWN/INVALID on missing receipt with no invented success; changes tests/metrics/outbox identifiers, schema migration if receipts persisted, invalidates delivery caches not trading/model hashes; no retraining. B: treat empty response as transport success but mark receipt unknown; cannot claim `sent=True` confirmed, requires timeout reconciliation.
### My recommendation
A, preserving independent internal ID while reporting provider receipt truthfully.
### Acceptance and regression tests
`{}`, missing/null/invalid/valid receipt from synthetic transport, ack-after-timeout ambiguity, retry without duplicate send; provider-specific device behavior must be checked only through authorized read-only logs.

## G-029
### Auditor claim (short quote)
Truncation leaves a lone MarkdownV2 backslash, and photo caption is unescaped under MarkdownV2 mode.
### What I read (files, line ranges, functions, callers)
`signaling.py:162-211,666-741` (`escape_markdown_v2`, `format_markdown_v2`, `format_caption`, `send`), `AiogramTransport.send_photo:548-567`; `tests/unit/test_telegram_signaling.py:180-199,376-407`; grep `format_caption`, `format_markdown_v2`, `send_photo` in apex/scripts/tests, including `scripts/run_apex.py:839-856` text replies.
### Reproduction (command, probe file, actual result)
`G-029.py/.out`: actual formatter on `'x'*4095+'.'` yields 4096-char output ending in unpaired `\`; actual SignalingPlane.send with fake photo transport receives caption `'[BTC] +1.5%'` unchanged and `parse_mode='MarkdownV2'`. Fake image bytes/test transport **do not** validate Telegram parsing; provider rejection unproven.
### Verdict and reasoning
CONFIRMED S2 for format invariant/transport mismatch; consequences depend on Telegram parser/client. Existing tests only assert length/plain photo caption, not valid MarkdownV2 syntax.
### Root cause
Escaping before naive character-count truncation splits escape pair; caption is truncated raw and never escaped while parse_mode selected from text formatter.
### Direct impact
Potential malformed text/caption rejected by provider or rendered misleadingly.
### Secondary effects and interactions (upstream/downstream)
Upstream signal text/chart caption; downstream three retries repeat same malformed data, G-014 outbox and G-017 alert dedup can record failure; not a proved risk/order impact. Unicode/UTF-16 provider limits may require separate measurement beyond Python len.
### Contract and decisions
`APEX_GEN5.md:17959-17961`: MarkdownV2 escapes punctuation; `18093-18096`: length/caption degradation and retries; `PHASE2_DECISION_LOG.md:148` ISSUE-CP7-003 permits frozen module literals but no permission for broken escaping; owner decisions supersede any earlier formatter prose.
### Frozen status and non-frozen alternative
Signaling formatter non-frozen; no engine, DDL, locked requirements or original YAML edit.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: escape text and caption under same parse mode, truncate at safe token/escape boundary or split numbered messages within provider length, using measured provider units; changes exact escaped-text/length/quality tests and message hashes, idempotency/cache/outbox IDs may invalidate, no DB migration unless durable outbox G-014, no retraining. B: disable parse mode and send plain text/caption, avoids escape failures but loses intentional formatting and changes UX.
### My recommendation
A with parser/test-double validation; B interim on malformed/unknown input.
### Acceptance and regression tests
4095+punctuation boundary, caption `[BTC] +1.5%`, Unicode, mixed escaping, provider limit and retry; no trailing orphan escape, caption safe under selected parse mode; device delivery remains unverified.

## G-026
### Auditor claim (short quote)
Outbox omits snapshot/text/lineage and operator reply uses `snapshot_id='gateway'`, not a SHA-256 source identity.
### What I read (files, line ranges, functions, callers)
`signaling.py:440-495,629-665,666-807` (`SignalMessage`, `send`, `_record_outbox`), `scripts/run_apex.py:839-856` (`_telegram_reply`); `gateway.py:276-377` source/reply routing, `test_telegram_signaling.py:200-250,350-410`; grep `SignalMessage(` / `snapshot_id=` across apex/telegram, paper_loop and scripts identifies runtime sentinels and optional empty defaults.
### Reproduction (command, probe file, actual result)
`G-026.py/.out`: actual `_telegram_reply` through real SignalingPlane with synthetic transport succeeds; outbox contains signal ID/status/time but `snapshot_id`, text, lineage absent. `SignalMessage` has default empty snapshot/lineage and no `confirmed_at` field. No device evidence or real model snapshot.
### Verdict and reasoning
PARTIAL S2: inability to reconstruct text/lineage from *outbox* and non-hash `gateway` marker confirmed. But §3 “Every output” quality/provenance/snapshot may refer to market evidence, whereas an operator reply should have an explicitly distinct N/A identity; not proof that every market setup signal lacks its own valid snapshot. No 24-field evidence-event audit performed.
### Root cause
Generic `SignalMessage` permits missing provenance/time and outbox records only delivery metadata, while composition inserts a fixed fake snapshot-like string.
### Direct impact
Operator response cannot be causally reconstructed from its outbox entry alone; `gateway` is not valid 64-hex SHA-256.
### Secondary effects and interactions (upstream/downstream)
Upstream actual market/fabric snapshot and decisions not bound into replies; downstream replay, incident analysis, G-014 durable outbox and G-028 receipt proof lose attribution. Storing raw full text may create secrets/privacy retention exposure (D17); hash/encrypted content or references preferred, not blind plaintext persistence.
### Contract and decisions
`APEX_GEN5.md:17786-17787`: “Every output carries quality, provenance, and a deterministic SHA-256 snapshot_id, and confirmed_at”; `17976-17987`: TELEGRAM_MESSAGE output includes text and callback details. `PHASE2_DECISION_LOG.md:205` D17 forbids secret material in chat/logs, takes precedence over naive full-text audit; design separate operator-reply identity and protected content reference.
### Frozen status and non-frozen alternative
Signaling/composition and additive outbox schema non-frozen; frozen engines/store schema unchanged; producer/adapter can bind valid market identity without engine edit.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: version message types and bind market setup messages to canonical snapshot/confirmed_at/provenance, operator reply to explicit N/A plus referenced inbound update, durable encrypted/hash-only content audit; migrations, delivery/replay hashes/caches change, tests expecting `gateway` change, no retraining unless training consumes message identities. B: keep outbox metadata-only but store immutable content hash/ref elsewhere, less sensitive but reconstruction requires separate protected source.
### My recommendation
A with D17-safe retention and owner clarification of §3 scope for operator replies.
### Acceptance and regression tests
Synthetic market setup with known 64-hex hash and operator reply N/A, verified timestamp/quality/lineage across send/outbox/replay; no secret sentinel stored or printed; real message provenance requires device evidence separately.

## G-019
### Auditor claim (short quote)
Runtime wires STORAGE alerts, not feed-staleness, veto-10 or FSM RECOVERY_REQUIRED producers/subscribers.
### What I read (files, line ranges, functions, callers)
`signaling.py:107-127,831-963` (`ALERT_POLICY`, `check_feed_staleness`, `veto_alert_message`, `check_storage`, `emit_alert`); `scripts/run_apex.py:150-180,711-765` (Runtime bus collector and serve composition); `paper_loop.py:955-985,1065-1082`; `control_plane.py:922-935`; `apex/bus.py:96-170` subscription/publish; grep `check_feed_staleness\|veto_alert_message\|emit_alert\|check_storage\|CIRCUIT_OPEN\|EXEC_RECOVERY` apex/scripts excluding tests. Only `check_storage` has PaperRuntime production call; manual Emergency alert is not automatic veto/recovery producer.
### Reproduction (command, probe file, actual result)
`G-019.py/.out`: actual `scripts.run_apex.Runtime.start()` with temporary SQLite, real bus and synthetic plane bound to that same bus; subscriptions only collector topics execution.fsm.transition/boot/scheduler.cell/telegram.message. Publishing synthetic `RECOVERY_REQUIRED` event is collected but emits no alert; synthetic risk.veto event has no subscriber/transport call. This is not a true FSM/risk end-to-end execution or device proof.
### Verdict and reasoning
CONFIRMED S1 for missing runtime subscription/producer wiring in examined composition, limited to event paths named. Actual occurrence of stale feed/loss/recovery without device notification is not demonstrated. D-007 HOST_DOWN is a separate independent watchdog path, excluded here.
### Root cause
Alert helper functions have tests but no callsite/subscriber for feed/risk/FSM transitions, only storage guard and manual emergency.
### Direct impact
Contract alerts can be omitted when relevant runtime state changes.
### Secondary effects and interactions (upstream/downstream)
Upstream quality feed/risk veto/FSM transition available on other paths but not bound to alert policy; downstream operator escalation/audit/no-drop guarantees unenforced. G-027 mislabelled manual CIRCUIT_OPEN cannot substitute for real loss alert; G-018 Telegram failure still must not halt protective execution. No conclusion about venue order execution.
### Contract and decisions
`APEX_GEN5.md:18466-18478`: FEED_DEGRADED on staleness, EXEC_RECOVERY on recovery, CIRCUIT_OPEN on daily realized loss; `17747-17753`: downstream signaling must not block protection. `PHASE2_DECISION_LOG.md:203-205` D9 registers CIRCUIT_OPEN code for vetoes 10–12, not subscription; owner decisions take precedence and no later decision marks alert wiring complete. D-007 watchdog HOST_DOWN remains separate.
### Frozen status and non-frozen alternative
Signaling bus/ops/producer adapters non-frozen; risk kernel/engines frozen, consume their existing outputs rather than changing formulas. Additive outbox migration only if G-014 addressed.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: subscribe/wire typed feed-quality, veto result and FSM transition to policy dispatcher, with idempotency and failure isolation; tests expecting no alerts change, alert/audit IDs and replay caches change, durable outbox migration and delivery costs possible, no retraining. B: periodic polling of state could miss transitions or duplicate messages; weaker unless versioned cursor and ledger evidence.
### My recommendation
A, with first-class event identity, independent watchdog HOST_DOWN and G-018 safe exception containment.
### Acceptance and regression tests
Actual runtime quality staleness/veto10/RECOVERY_REQUIRED on temporary store produce exactly matching alert and audit in synthetic transport, no event→no alert, provider failure leaves protective management active; device evidence separately required.

## G-005
### Auditor claim (short quote)
`bootstrap` CLI has outbound notifications but no inbound gateway; `serve` commands control another runner, not Phase-1 CLI job; pause/stop do not gate catch-up and >24h resume only returns a health-recheck flag.
### What I read (files, line ranges, functions, callers)
`/tmp/AUDIT.md` full G-005 row, `scripts/run_apex.py:504-570,711-765,815-824,1071-1100` (CLI/bootstrap/serve composition), `gateway.py:310-376` (owner word dispatch), `bootstrap_service.py:1120-1179,1260-1275,1456-1565` (runner ownership, command/catch-up), `research/bootstrap.py:153-242` (frozen runner state), `paper_loop.py:955-977,1103-1142` (catch-up before gateway; control pause only checks ControlPlane). Searched cross-references of `health_recheck`, `catch_up`, `runner.state` and gateway in apex/scripts; no shared job lease, restart hydration of state, or check invocation by `resume` found.
### Reproduction (command, probe file, actual result)
`G-005.py/.out`: real `BootstrapService.open/command/catch_up` through real `_bootstrap_handler` on temp SQLite, fake empty-page source, synthetic clock. `pause` accepted and `paused=True`, yet catch-up checks 1 cell and invokes source. After 25h `resume` accepted with `health_recheck.required=True` but no health-check call. `stop` accepted yet catch-up again checks 1 cell/invokes source. Newly opened service on same temp DB reports `stopped=False,paused=False`. `_bootstrap` function has no `TelegramGateway` reference; `_serve` does. No real CLI bootstrap subprocess, provider or venue tested; empty page means no ingestion proved.
### Verdict and reasoning
CONFIRMED S1, bounded to composition and source-invocation checks. Owner pause/stop are not effective for the `serve` catch-up function, and CLI bootstrap has no incoming gateway. Distinct checkpoint persistence for bar cursors works independently; no device loss or live page beyond pause demonstrated.
### Root cause
Separate per-instance in-memory runner states and independent command/poll/catch-up processes; service catch-up never consults runner paused/stopped; resume returns check advice but does not enforce it.
### Direct impact
Accepted W.8 control words do not reliably govern the acquisition job and may leave catch-up polling; restart loses control flags.
### Secondary effects and interactions (upstream/downstream)
Upstream OWNER authentication via gateway is separate from job identity; downstream page accounting/quality publishing may proceed while an operator believes acquisition stopped. PaperRuntime performs catch-up *before* inbound gateway polling each cycle, so even a future same-cycle pause check needs defined ordering. Broadly stopping PaperRuntime would also stop protective management/watchdog and violate D5/D22 isolation. No orders, actual data ingest or trade effects observed.
### Contract and decisions
`APEX_GEN5.md:17300-17316` W.8 pause after current cell with persisted state, stop bootstrap, >24h data-health recheck before resume; `PHASE2_DECISION_LOG.md:198,284` D5 per-cycle catch-up and D22 per-cell failure isolation are binding, so W.8 control must distinguish historical bootstrap from independent fresh-catch-up rather than silently blanket-halt risk/positions. Owner decisions outrank conflicting W.8 prose; no decision permits a false accepted status.
### Frozen status and non-frozen alternative
`apex/research/bootstrap.py` frozen; add non-frozen command adapter/job registry/persistent control state/`BootstrapService` admission before page, leaving frozen runner unchanged; no original YAML or frozen schema edits.
### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: bound owner commands to durable job ID/lease and process IPC with ack after target job takes control; gate historical fetch after current cell/page per chosen W.8 boundary and perform true health recheck before resume. Requires new durable state/IPC migration, lock lifecycle/restart tests, alert changes and possibly delayed pause acknowledgement; no model retraining, but replay/cursor semantics must be revalidated. B: explicitly reject commands in `serve` when no matching Phase-1 job and document catch-up as independently controlled; safer than false success, yet requires a dedicated catch-up policy/command if owner needs it. Neither option should pause position protection.
### My recommendation
A for actual Phase-1 job control plus B-style honest refusal where no job exists; make D5 catch-up policy explicit with owner approval.
### Acceptance and regression tests
Synthetic two-process/job-lease integration using real temp checkpoint: authorized command reaches correct running job, persists across restart, page boundary respected, unrelated job unchanged; >24h resume blocks until actual health check passes; serve catch-up either obeys explicit control or refuses independent stop unambiguously, while position protection continues. Separate device acceptance on real scheduler and provider.

## New findings not in the audit

No additional independent X-ID arose from G-005/G-019/G-026/G-029; their new bounded observations are incorporated in those audit IDs and the final counts. X-V4-001 remains the independent finding.

### X-V4-001 — repeated ledger queries have no selective indexes (S2, CONFIRMED plan shape; latency DEVICE-EVIDENCE-NEEDED)
#### Auditor claim (short quote)
Not an audit row: independently discovered via required query-plan check.
#### What I read (files, line ranges, functions, callers)
`ledger/store.py:435-446,492-525,525-571,633-641,645-679` (find_by_fill, find_by_intent, read_ledger, trade_plans, verify_chain, head); `data_catalog/store/sqlite_store.py:46-92,165-180,290-340` real DDL and migrations; `fsm.py:671-693,1302-1324`, `paper_loop.py:106-160`, `ops/engine_context.py:645-650,746-750,2197-2201`. `grep -Rn` of all these query methods in apex/scripts shows per-fill lookup and repeated per-intent/per-cycle projection and boot scans. `QUERY-PLAN.py` uses repository DDL; no device database touched.
#### Reproduction (command, probe file, actual result)
`python3 AUDIT/probes_V4/QUERY-PLAN.py` → `.out`: before and after adding exactly `idx_mo_sym_tf_open` and `idx_pit_scope_asof`, `find_by_fill: SCAN ledger`, `find_by_intent: SCAN ledger`, `trade_plans: SCAN trade_plan; USE TEMP B-TREE FOR ORDER BY`. `read_ledger/head: SCAN ledger` are full-history operations (head can reverse-walk without sorting). The two device indexes make their *own* market/PIT scope queries SEARCH, but do not index the ledger. Plan on empty fixture is structural, not a device p95 proof.
#### Verdict and reasoning
CONFIRMED S2 for missing selective indexes on frequently invoked lookups; severity only S2 until row counts/latency measured. Full-history scans are deliberate for verification/projection, not all defects; per-fill/per-intent scans scale poorly as ledger grows.
#### Root cause
Frozen CP-1 ledger has PK only on ledger_id; no index on fill_id or intent_id; CP-7 trade_plan PK only on proposal_id.
#### Direct impact
Linear per-fill and per-intent reads and sort cost in trade-plan listing as history grows.
#### Secondary effects and interactions (upstream/downstream)
Upstream F-005 race becomes slower; downstream FSM reconciliation and repeated positions/replay may delay admission or recovery. G-023 Telegram rate is unrelated; ISSUE-079 market/raw join is separate. No device stall inferred. Read-only evidence command **for owner only**, pointed at device file without running here: `python3 -c "import sqlite3; c=sqlite3.connect('file:data/apex.sqlite3?mode=ro',uri=True); print(c.execute('SELECT count(*) FROM ledger').fetchone()); print(c.execute('EXPLAIN QUERY PLAN SELECT ledger_id FROM ledger WHERE fill_id=?',('synthetic',)).fetchall()); print(c.execute('EXPLAIN QUERY PLAN SELECT ledger_id FROM ledger WHERE intent_id=? ORDER BY rowid',('synthetic',)).fetchall())"` plus device p95 measured on authorized read-only copy. Do not copy data into Git.
#### Contract and decisions
`APEX_GEN5.md:18438-18447`: single writer and pre-LIVE target-device load test with CPU/RAM headroom; `18922-18933`: p50/p95/p99 per station and fail-closed on failed measured SLO. `PHASE2_DECISION_LOG.md:194-210` D1 PAPER same FSM/ledger path; no owner override of lookup performance; decisions take precedence. ISSUE-076 two device indexes are market/PIT, **not ledger**.
#### Frozen status and non-frozen alternative
Store schema file is frozen; additive `CREATE INDEX IF NOT EXISTS` migration in non-frozen ledger module, after duplicate cleanup (F-005) and owner review, avoids modifying frozen DDL.
#### Fix options (A/B/C… each with side effects, or "single path" with justification)
A: non-frozen additive partial/unique index on `(fill_id)` (after duplicate reconciliation), index on `(intent_id)`, `(environment,created_utc,proposal_id)` for trade plans; migration adds disk/storage/write amplification, changes query plans and could fail on existing duplicates, no change to chain hashes/training, but derived caches may need revalidation after duplicate cleanup. B: batch/read cache for fill lookup; stale/racing cache risks F-005 and needs durable invalidation; not sufficient alone.
#### My recommendation
A after device read-only count/plan and duplicate scan; use queue-side correctness (F-005) independently of indexes.
#### Acceptance and regression tests
EXPLAIN on real DDL before/after migration with device indexes both absent/present; collision scan, unique enforcement and transaction fault/restart tests; device p95 on read-only snapshot, real dataset size and concurrency required to assert SLO.

## Rows not verified or incomplete

**Not verified: none of the 41 requested IDs remain without a bounded verdict.** G-005, G-019 and G-026 have now been assessed on real imported code with synthetic boundaries; G-026 is PARTIAL, not a full provenance certification. ISSUE-073 overlaps G-002 only; it does not discharge other G rows. No device, Telegram provider, venue, model or actual long-running Phase-1 job was exercised. Synthetic evidence cannot certify device behavior or complete acceptance.

**Depth limits across all 41 bounded findings:** per-row function slices and grep consumers are recorded, but an exhaustive end-to-end semantic review of every referenced file, the entire 21k-line contract, every complete test file and every transitive caller/callee was not completed. These are **bounded direct-behavior conclusions, not complete mandatory-depth closure**. The source report's Persian rows cited in their individual sections were read; no device DB, actual model fixture, external provider or venue was available. Query plans were on empty real schema with/without the two specified indexes; optimizer choices and p95 on device are unverified. No L1/L2 risk ladder or order placements were executed. A further source and device review must precede any patch or operational approval; this report is not approval to trade or change frozen files.

## Final counts

Of 41 requested audit IDs: **35 CONFIRMED** (bounded direct behavior), **6 PARTIAL**, **0 REJECTED**, **0 DEVICE-EVIDENCE-NEEDED as sole verdict**, **0 NOT VERIFIED**. One additional finding X-V4-001: plan shape CONFIRMED, device impact pending. Newly tested interactions: G-005 accepted W.8 commands do not gate synthetic catch-up or survive service restart; G-019 subscribed transition events do not trigger alerts; G-026 operator replies lose provenance fields in the in-memory outbox (scope PARTIAL), and G-029 text/caption formatting may be invalid for MarkdownV2 without a real provider test. No row is claimed fully closed at the mandatory exhaustive-depth standard. These counts exclude tests and known-owner items outside the 41-ID scope.
