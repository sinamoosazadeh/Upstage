# Independent Verification V1d — Execution FSM and order lifecycle (session 2)

Baseline: `85b2c155d7b054a468379ddfd802eb239d0801f9` (verified with `git rev-parse HEAD` before any work). Verification date: 2026-09-29. Session scope (mandatory): E-012, E-013, E-014, E-015, E-017, E-018, E-019, E-020, E-021, E-022. Continuation of V1b (`AUDIT/VERIFY_V1b.md`, branch `arena/01a0e9b8-upstage`), whose facts (venue accepted-status literal `NEW`; `kind="exit"` is not in the wire `order_defaults`; `_transport` is mutation-guarded so a position-aware fake must be built up front; E-003/E-016 both CONFIRMED S0) are cited, not redone.

Every reproduction below runs the REAL repository code (`apex.execution.fsm`, `apex.execution.toobit_adapter`, `apex.ledger.store`, `apex.ops.paper_loop`, `apex.playbook.pb_fvg_sweep_rev_a`) against in-memory objects, temporary-file SQLite built with the repository's own DDL, or `tests/fake_toobit_responder.py`. No network, no real venue, no `data/`, no secrets beyond synthetic test keys. Synthetic results do NOT establish behavior on the real device, database, model, or venue.

Frozen-file note for this session: the V1d frozen list is `apex/engines/**`, `apex/data_catalog/**`, `apex/research/bootstrap.py`, `apex/research/backtest.py`, the six params YAMLs, `requirements.lock`. None of `apex/execution/**`, `apex/ledger/**`, `apex/ops/**`, `apex/playbook/**` is on that list, so rows below are marked "No" in the Frozen column; however these modules implement contract-FROZEN values (the SL-6 transition matrix, the Ch.16 wire map/DDL, the AE.5 playbook literals), which tests pin literally — any fix must change behaviour without altering those frozen values. (V1b marked `apex/execution/fsm.py` "frozen" in its E-003 row; that marking is not derivable from the V1d frozen list and is flagged here as a discrepancy for the owner.)

## Summary

| ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option |
|---|---|---:|---:|---|---|---|
| E-012 | CONFIRMED | S1 | S1 | No | none | A: real chain/manifest + risk/FSM verification, UNAVAILABLE not PASS |
| E-013 | CONFIRMED | S1 | S1 | No | none | A: extras allowlist + final payload validation |
| E-014 | CONFIRMED | S1 | S2 | No | E-022, F-005 | A: per-intent in-flight reserve (asyncio lock) |
| E-015 | CONFIRMED | S1 | S1 | No | I-016 | A: require executedQty/unique fill id; reconcile-required otherwise |
| E-017 | CONFIRMED | S2 | S2 | No | E-006 | A: EXTREME gate before factor resolution |
| E-018 | CONFIRMED | S2 | S2 | No | E-006 | A: persist initial R + activated flag |
| E-019 | CONFIRMED | S2 | S2 | No | E-005, F-001 | A: finite/non-negative weights + initial-quantity semantics |
| E-020 | CONFIRMED | S1 | S1 | No | D-008, D-009 | A: reject quantity != plan.sized_quantity (quantized) |
| E-021 | CONFIRMED | S1 | S1 | No | E-005, F-008 | A: route FSM divergence through the ledger gate |
| E-022 | PARTIAL | S2 | S2 | No | D50, J-018 | A: payload-hash compare + explicit collision refusal |

(Sections follow in ID order. The twelve mandatory headings appear under each ID.)

## E-012

### Auditor claim (short quote)
"three AI.9 controls are weaker than their names: raw_hash_chain only takes COUNT; risk_recheck only checks existing leverage, not capital/concentration/protection; fsm_state always PASSes and does not even extract the last state of each intent. raw probe with two count=10, PASS gave. … the full recovery path is also not invoked in the current serve."

### What I read (files, line ranges, functions, callers)
`apex/execution/fsm.py` completely (1–1362): `run_recovery_reconciliation` (1213–1237), `_ai9_ledger_integrity` (1239–1248), `_ai9_raw_hash_chain` (1250–1267), `reconcile_boot` (1180–1211), `_ai9_feature_replay`/`_ai9_pattern_reevaluation` (1269–1289), `_ai9_risk_recheck` (1291–1311), `_ai9_fsm_state` (1298–1311 region; exact lines below), `StartupReconciliation.run` (1078–1127) and `self_test` (1129–1138). `apex/ledger/store.py` completely: `verify_chain` (real, recomputes payload hashes + parent linkage), `trade_plans()` (728–744 — `SELECT` of `TRADE_PLAN_COLUMNS` only), `positions_from_ledger` (745–800), `append_fill`/`append_trade_plan`. `apex/data_catalog/store/sqlite_store.py` DDL for `raw_manifest` (258–268) and `raw_observation` (208–226). Callers (mandatory grep `grep -RIn "run_recovery_reconciliation" --include="*.py"`): only `tests/unit/test_execution_fsm.py` (5 sites) and `tests/integration/test_cp7_paper_loop.py:794` — NO production caller. `scripts/run_apex.py::_serve` (692–820) calls `driver.boot(...)` (boot machine: SELF_TEST + `reconcile_boot`) and `driver.run(...)`; it never calls `run_recovery_reconciliation`. Tests `TestRecoveryReconciliation` (test_execution_fsm.py:1378–1440) assert `raw_hash_chain`/`risk_recheck`/`fsm_state` reach PASS with matching venue — i.e. the weak behaviour is enshrined as PASS by the suite.

### Reproduction (command, probe file, actual result)
`python3 -B AUDIT/probes_V1d/E-012.py` (raw output `AUDIT/probes_V1d/E-012.out`): real `StartupReconciliation` methods against a temporary SQLite store seeded with (a) 10 `raw_manifest` rows whose `manifest_hash` values are garbage, whose `content_hashes_included` match nothing, and whose `parent_manifest_hash` chain points at non-existent hashes; (b) 10 `raw_observation` rows whose `content_hash` does not match their payload; (c) a materialized plan with `sized_quantity=1,000,000` (capital breach), ledger positions of 100000 BTCUSDT + 50000 ETHUSDT (capital + concentration breach), and ZERO protective orders; (d) contradictory FSM ledger state (intent A stuck ACKNOWLEDGED, intent B RECONCILED) with no broker wired. Results: `raw_hash_chain True PASS | 10 manifest(s), 10 raw observation(s)`; `risk_recheck True PASS | 2 position(s), 1 plan(s)`; `fsm_state True PASS | 2 non-terminal FSM record(s) re-validated against broker state`. Additionally the probe prints that `trade_plans()` rows contain NO `leverage` key (the frozen `trade_plan` DDL has no such column), so `plan.get("leverage")` in `_ai9_risk_recheck` is always `None` — the leverage sub-check is dead code and can never fire either. Focused existing tests: `python3 -m pytest -q -p no:cacheprovider tests/unit/test_execution_fsm.py::TestRecoveryReconciliation` → `5 passed` (`E-012-pytest.out`), confirming the suite blesses these three PASS verdicts.

### Verdict and reasoning
**CONFIRMED, S1.** Every element of the claim is proven by my own probe against the real methods: (1) `_ai9_raw_hash_chain` executes only `SELECT COUNT(*) FROM raw_manifest` and `SELECT COUNT(*) FROM raw_observation` — no manifest-hash validation, no payload-hash recomputation, no parent-chain check, no halt-on-mismatch; corrupted raw state yields PASS. (2) `_ai9_risk_recheck` validates neither capital ceiling, nor concentration, nor protective orders (the `positions` result is used only inside the detail string), and its single sub-check (leverage) can never fire because `trade_plans()` projections never carry `leverage` — this is slightly WORSE than the auditor's wording ("checks existing leverage"), and I record the difference as new finding X-V1d-001. (3) `_ai9_fsm_state` counts non-terminal `FSM_TRANSITION` records and unconditionally returns `CheckResult(..., True, "PASS", ...)` — it never extracts the last state per intent, never compares with the broker, never advances to RECONCILED. (4) `run_recovery_reconciliation` has no production caller; `serve` boots via `StartupReconciliation.run()` only. Fixture success on the real device is not claimed — the probe uses synthetic corruption.

### Root cause
The three checks were implemented as presence/counting stubs rather than verifications; the two genuinely fail-closed checks (`ledger_integrity` via `verify_chain`, `broker_reconciliation` via `reconcile_boot`) show the intended pattern was available. For `risk_recheck`, the code reads `leverage` from a table whose frozen DDL has no `leverage` column, so the only implemented sub-check is structurally dead.

### Direct impact
If the AI.9 recovery sequence is ever wired (it is the contract's gate for resumption from fail-closed), a resume decision can be made on false PASS evidence: trading can resume over a corrupted raw store, a capital/concentration-breached book with no protective orders, and FSM states that disagree with the broker. Today the impact is latent because no production caller exists, but the checks and their PASS verdicts are exposed API and are asserted by the test suite.

### Secondary effects and interactions (upstream/downstream)
Upstream: none — the inputs (raw store, trade_plan, ledger) are exactly the ones the contract names. Downstream: `run_recovery_reconciliation`'s verdict `action` flips from `HALT_AND_ESCALATE_MANUAL` to `RESUME` only on all-PASS; with 3 of 7 checks hollow, `RESUME` can be reached on unhealthy state. E-003/V1b's RECOVERY_REQUIRED positions and E-016's projection failures would be "re-validated" by a check that validates nothing. The feature_replay/pattern_reevaluation checks are correctly UNAVAILABLE-without-provider (fail-closed) — not in dispute.

### Contract and decisions
Binding: APEX_GEN5.md AI.9 "Startup reconciliation (run before resumption from fail-closed)" (in this checkout at ~L19076–19086; the audit's L18894–18903 offset): step 2 "**Raw store hash chain:** for each symbol+timeframe, validate manifest hashes; re-compute payload hashes; compare against stored hashes; halt if mismatch"; step 6 "**Risk re-check:** validate no position violates capital ceiling, leverage limit, or concentration limit; confirm all protective orders are in place"; step 7 "**Execution FSM state:** validate current trade state machine state matches broker state; advance FSM to RECONCILED if checks pass"; closing rule "If any check fails, halt recovery and escalate to manual". Ch.23 Startup Reconciliation Sequence (~L18424–18431) governs the boot machine (implemented faithfully). No decision in `PHASE2_DECISION_LOG.md` waives any of the seven checks (D54–D58 concern other matters). Precedence: contract governs; no conflicting owner decision.

### Frozen status and non-frozen alternative
`apex/execution/fsm.py` is NOT on the V1d frozen list (see header note; V1b marked it frozen — discrepancy flagged). A fix therefore needs no frozen-file ruling, but must not alter the frozen SL-6 matrix/boot machine values that the same file carries and tests pin literally. The raw-store hash verification itself belongs to `apex/data_catalog/**` semantics — a verifier can be added in a NON-frozen module (e.g. `apex/ops/` or `apex/execution/`) that READS the CP-1 store and computes the manifest chain, avoiding any edit to `apex/data_catalog/store/sqlite_store.py`.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A (recommended):** implement real checks — recompute manifest/payload hashes from the CP-1 store DDL, evaluate capital ceiling/concentration/protective orders from ledger + plans (leverage from a lawful source, e.g. the plan payload in the ledger `TRADE_PLAN` record which does carry `leverage`), and derive the last state per intent from `find_by_intent` then compare against the venue via the adapter; when a required verifier/provider is absent, return UNAVAILABLE (fail-closed) instead of PASS. Side effects: `TestRecoveryReconciliation` tests that assert PASS for these three checks must be extended with corrupted-state FAIL cases; boot/recovery verdicts change (more HALT/UNAVAILABLE); no schema migration needed if the verifier reads existing tables; hashes/identities unchanged; no retraining. **B:** leave the checks but rename them (e.g. `raw_store_count`) so no false claim is made — rejected: it silently weakens the AI.9 gate the contract mandates. **C:** wire `run_recovery_reconciliation` into serve first and fix later — rejected: wiring a hollow gate increases risk.

### My recommendation
A, plus (separately) the X-V1d-001 dead-leverage-sub-check fix: source leverage from the ledger `TRADE_PLAN` record payload (which carries `leverage`) rather than the `trade_plan` table projection.

### Acceptance and regression tests
Corrupt-manifest / broken-parent / wrong-content-hash fixtures must FAIL `raw_hash_chain`; a capital-breached position, a concentration breach, and a missing protective order must each FAIL `risk_recheck`; an intent whose last ledger state disagrees with the venue must FAIL `fsm_state`; absent verifier/provider must yield UNAVAILABLE and `HALT_AND_ESCALATE_MANUAL`; clean store with matching venue must still PASS and the existing 5 `TestRecoveryReconciliation` tests must keep passing for the checks that are genuinely implemented. Run on temporary SQLite with the repository DDL; device evidence (read-only `SELECT` on the real raw store + a real venue query) is required before claiming the recovery gate is trustworthy in production.

## E-013

### Auditor claim (short quote)
"`extra_params` after validation updates all parameters. A valid LIMIT/reduceOnly with extra_params turned into MARKET, quantity=999 and reduceOnly=false in the outgoing request. Abuse in the current caller is not proven; the current protection caller only sends TIF."

### What I read (files, line ranges, functions, callers)
`apex/execution/toobit_adapter.py::submit_order` (402–474) completely, especially the ordering: `order_defaults(kind)` → `assert_order_type_permited(effective_type)` → `quantize_quantity`/`quantize_price` → `check_min_notional` → `params` construction (side/type/quantity/price/clientOrderId/positionMode, TIF, priceType, `reduceOnly`, `leverage` after `resolve_leverage` min-over-caps) → **`if extra_params: params.update(dict(extra_params))` (469–470)** → `_execute`. `apex/execution/toobit_map.py` completely: `assert_order_type_permited` (raises on `MARKET`), `quantize_*`, `check_min_notional`, `resolve_leverage`, `side_for`, `order_defaults`. `_execute` (623–725) signs whatever `params` holds (`signed_request`) and records the result under `client_order_id` = the `intent_id` argument. Callers (mandatory grep `grep -RIn "extra_params" apex scripts`): exactly one production caller — `apex/execution/fsm.py:722` `place_protection` stop leg sends `extra_params={"timeInForce": "GTC"}`; `tests/.../FakeAdapter` records but ignores it. `tests/fake_toobit_responder.py` `_accept_order` books the order under `params["clientOrderId"]`.

### Reproduction (command, probe file, actual result)
`python3 -B AUDIT/probes_V1d/E-013.py` (raw output `AUDIT/probes_V1d/E-013.out`), real `ToobitAdapter` + repository `FakeToobitResponder`:
1. Production shape (stop leg, `extra_params={"timeInForce":"GTC"}`): accepted; wire carries `type=STOP, quantity=0.1, price=99, reduceOnly=true, timeInForce=GTC` — the lawful TIF extra works.
2. Valid LIMIT/GTC reduce-only target (`i-target-good`, 0.1 @ 103): wire carries `type=LIMIT, quantity=0.1, reduceOnly=true, side=SELL_CLOSE`.
3. The SAME call as (2) with `extra_params={"type":"MARKET","quantity":"999","reduceOnly":"false","side":"BUY_OPEN","clientOrderId":"i-evil","leverage":"125"}`: accepted (`ok=True outcome=ACKNOWLEDGED`) and the SIGNED WIRE REQUEST contains `type=MARKET, quantity=999, reduceOnly=false, side=BUY_OPEN, clientOrderId=i-evil, leverage=125`. The venue books the order under `i-evil` while the adapter caches the result under the intent `i-target-bad`.
4. The same `order_type="MARKET"` passed as a real parameter IS refused: `ToobitMapError ORDER_TYPE_FORBIDDEN: type=MARKET (Ch.16 L16895)` — proving the guard exists but runs before the `params.update`.

### Verdict and reasoning
**CONFIRMED, S1.** The mechanism is exactly as claimed: every validation (order-type law, quantity/price lattice, min-notional, reduce-only, leverage min-over-caps, ONE_WAY side map, intent identity) executes on the pre-update `params`, and `extra_params` then overwrites arbitrary keys on the payload that is actually signed and sent. My probe reproduces the auditor's exact triple (MARKET / quantity=999 / reduceOnly=false) and additionally shows `side` can flip a reduce-only flatten into an OPENING order, `leverage` can bypass the caps law, and `clientOrderId` can be replaced — the last one desynchronising the adapter's duplicate registry from the venue's order identity, which also breaks the Ch.16 "reconcile query keyed by clientOrderId" law. The auditor's scoping is correct: the only production caller (`fsm.place_protection`) sends a TIF key only, so no abuse exists in the current call graph; the defect is the API's own bypass surface.

### Root cause
`params.update(dict(extra_params))` is an unrestricted merge applied AFTER all validation, with no allowlist and no re-validation of the final payload.

### Direct impact
Any future caller, wrapper, or polluted input that forwards user/config-derived keys into `extra_params` can place an order whose type, size, side, reduce-only flag, leverage and identity violate every governed wire law the adapter is supposed to enforce — while the adapter reports `ok=True`.

### Secondary effects and interactions (upstream/downstream)
Upstream: none today (single TIF-only caller). Downstream if abused: a `MARKET`/`BUY_OPEN`/non-reduce order reaches the venue; the ledger records the plan's quantity while the venue fills 999; reconcile-by-`clientOrderId` (query/cancel use `intent_id`) targets an id the venue never saw, forcing UNKNOWN → RECOVERY_REQUIRED; the duplicate cache (E-014/E-022) keys on an intent that no longer matches the booked order. Interacts with E-020 (quantity already has a separate override path there).

### Contract and decisions
Binding: APEX_GEN5.md Ch.16 wire block — order types table (in this checkout ~L16918–16927: entry LIMIT/IOC, stop STOP/GTC, target LIMIT/GTC), the forbidden `type=MARKET` law, the ONE_WAY side map, leverage `min(Y.2 cap, owner cap, exchange max)` (~L16900 audit numbering), and the Adapter Contract (~L16960–16970): "each exchange error code maps to a single FSM transition … unmapped codes map to UNKNOWN" and identity mapping `intent_id` sent as `client_order_id`; "No order may be submitted without a client order id". `params/toobit_wire_v1.yaml` (frozen) fixes the wire parameter set. No decision licenses overriding validated fields. Precedence: contract governs.

### Frozen status and non-frozen alternative
`apex/execution/toobit_adapter.py` is NOT on the V1d frozen list; `params/toobit_wire_v1.yaml` IS frozen but needs no change (the allowlist lives in code). A wrapper/producer-layer restriction (a guard object that only ever passes TIF) is possible without touching the adapter, but defence-in-depth belongs in the adapter itself.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A (recommended):** allowlist extras (e.g. `timeInForce`, `priceType` only), reject any key in the protected set (`symbol, side, type, quantity, price, clientOrderId, positionMode, reduceOnly, leverage, timestamp, recvWindow, signature`) and any unknown key; re-run `assert_order_type_permited`/lattice/min-notional/leverage checks on the FINAL payload before signing. Side effects: `tests/unit/test_toobit_adapter.py` conformance fixture cases that pass extras must be checked (the fixture's submit cases carry no extras; the FSM stop-leg TIF keeps working, as my probe step 1 shows); the FSM's GTC extra is unaffected; no identity/hash/migration impact; future legitimate extras require an explicit allowlist entry. **B:** forbid `extra_params` entirely and add a dedicated `tif` parameter. Cleaner but changes the FSM call site (still non-frozen) and loses the conformance-fixture shape. **C:** validate `extra_params` values only (not keys) — rejected: `type=MARKET` with a valid-looking value still bypasses the order-type law.

### My recommendation
A, with the final-payload re-validation (so the invariant "what was validated is what was signed" holds structurally, not per-key).

### Acceptance and regression tests
Assert: extras containing any protected key are REFUSED before transport (no POST, REFUSED classification with a named code); `timeInForce`/`priceType` extras still reach the wire; the final signed payload re-passes type/lattice/min-notional/leverage/side checks; the existing `test_stop_and_target_are_placed_with_the_governed_defaults` and adapter conformance fixture keep passing; an attempt to replace `clientOrderId` is refused by name. Run against the fake responder (no network); no device evidence is needed for this code-level invariant, but the real venue's acceptance of the protected-field set should be confirmed read-only before LIVE.

## E-014

### Auditor claim (short quote)
"the duplicate cache is only populated after the transport returns; two coroutines with one intent both pass the check. In the concurrent experiment, transport was called twice."

### What I read (files, line ranges, functions, callers)
`apex/execution/toobit_adapter.py::submit_order` (402–474): the duplicate guard `cached = self._duplicates.get(intent_id); if cached is not None: return self._cached_result(...)` (427–429) is a plain dict read with NO lock/in-flight registry; the cache write `self._duplicates[client_order_id] = result` happens in `_execute` (668–670) only AFTER the awaited transport round-trip completes. Between check and write there is an arbitrary await window (`_bucket(endpoint).acquire()`, `signed_request`, `await self._transport(...)`, backoff sleeps). `_TokenBucket.acquire` serialises only its own lock and does not key on intent. `_cached_result` (712–742) and `_refused` read for context. Callers (grep `submit_order`): `fsm.submit` (one FSM per intent, awaited sequentially), `fsm.place_protection` (suffixed intents, sequential awaits), `paper_loop.manage_positions` exit leg, `scripts/run_apex.py` demo — no current production caller submits the same intent concurrently; the race is reachable by any future/parallel caller of the shared adapter.

### Reproduction (command, probe file, actual result)
`python3 -B AUDIT/probes_V1d/E-014.py` (raw output `AUDIT/probes_V1d/E-014.out`). Part 1: real `ToobitAdapter` with a gated in-memory transport that blocks the first submit until the second coroutine has also entered `_execute`; `asyncio.gather` of two `submit_order(intent_id="i-race", ...)` → **transport invoked 2 times**, both results `ok=True outcome=ACKNOWLEDGED cached=False attempts=1` with the audit trail showing `['TRANSPORT', 'TRANSPORT', 'CACHE']` (the CACHE entry is the third, sequential re-submit, which correctly makes no new transport call). Part 2: the same race against the repository's real `FakeToobitResponder` (50 ms delay) → **2 POSTs to `/api/v1/futures/order` for one intent, and the venue's order book flags `duplicate_submission: True`** with neither result marked cached.

### Verdict and reasoning
**CONFIRMED as a mechanism, S2 (auditor said S1).** The race is real and deterministically reproducible with the real adapter: the check-then-act window spans an await, so two same-intent submissions both reach the transport, violating the module's own law ("a repeated key returns the previously recorded response and never resubmits", Ch.16 L16915–16917 / T_ADAPTER_DUPLICATE) and D50 ("never resent"). I lower severity to S2 relative to the auditor because in the current call graph no two production paths can submit the same `intent_id` concurrently: the FSM is constructed per intent and `submit` is awaited once; protection uses suffixed intents; native plan re-sends are blocked upstream by `PLAN_ALREADY_MATERIALIZED` and the durable cell cursor (D50). The defect is a missing local guarantee on a shared venue surface — a latent concurrency hazard for future parallel callers (and for any wrapper that retries a timed-out submit on a new coroutine), not a defect that today's PAPER path can trigger. This is a severity judgement, not a refutation; the auditor's own evidence column also notes venue-side dedup uncertainty.

### Root cause
Check-then-act on `self._duplicates` without an in-flight registry: the cache entry is written only after the transport future resolves, so concurrent submissions with the same key both observe a miss.

### Direct impact
Two signed POSTs for one `intent_id` (two venue orders, two audit trails, two idempotency keys) where the contract guarantees exactly one; the second caller receives a fresh venue answer rather than "the previously recorded response", so a lost-ack retry implemented naively around the adapter would double-execute.

### Secondary effects and interactions (upstream/downstream)
Upstream: none today. Downstream: the venue may reject or double-book the duplicate; ledger/FSM state can then diverge from the venue's actual order set (which of the two orders does `query_order_state(clientOrderId=...)` return?); reconcile-first recovery inherits the ambiguity. Related rows: E-022 (same registry, staleness/collision semantics), F-005 (a different check-outside-queue race in `append_fill`), D50 (binding rule "never resent").

### Contract and decisions
Binding: APEX_GEN5.md Ch.16 "Execution-layer idempotency (explicit)" (in this checkout L16910–16917): "`intent_id / order_id / fill_id / cancel_id` are unique; a repeated key returns the previously recorded response and never resubmits", and the Adapter Contract's `T_ADAPTER_DUPLICATE`. `PHASE2_DECISION_LOG.md` D50 (L1163): "A repeated client order id … is never resent." No decision authorises concurrent double-send. Precedence: contract + D50 govern.

### Frozen status and non-frozen alternative
`apex/execution/toobit_adapter.py` is not on the V1d frozen list. No frozen file needs to change: the registry can be extended inside the adapter, or a per-intent reserve can live in a wrapper layer outside it (though only the adapter can make the guarantee universal).

### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A (recommended):** per-intent in-flight map of `asyncio.Future` in the adapter: first caller creates the future and executes; concurrent same-intent callers await and return the SAME result (marked cached/duplicate); the map entry is removed only after a durable record exists. Side effects: concurrent-duplicate tests must assert exactly one transport call and a shared result; the audit trail gains a WAIT/DEDUP result_source (AI.8 L18806 requires every dedup to be logged — currently only CACHE hits are); crash-durability of "in-flight" is NOT covered by an in-memory map — a process crash between the two POSTs still needs the existing reconcile-first path, which is contractually correct (UNKNOWN → reconcile, never resubmit). **B:** serialise ALL submissions behind one global `asyncio.Lock` — simpler, but couples unrelated symbols/timeframes and adds latency under the semaphore-4 scheduler. **C:** rely on venue-side dedup — rejected: the contract requires a local guarantee, and venue behaviour is unverifiable from here.

### My recommendation
A (with the in-flight registry keyed by `client_order_id`), plus an audit record for the joined caller. Keep D50's "never resent" outcome for the post-completion duplicate path unchanged.

### Acceptance and regression tests
Two concurrent same-intent submits → exactly one transport call, both callers receive an identical result, audit shows one TRANSPORT + one WAIT/CACHE entry; sequential duplicate still returns the recorded response with `cached=True`; different intents still run concurrently (no cross-intent serialisation); after a simulated crash mid-flight, the next submit of the same intent still refuses to blind-resend (reconcile path). Existing `TestNoSilentRetries` and the conformance fixture's DUPLICATE case must keep passing.

## E-015

### Auditor claim (short quote)
"for PARTIAL/FILLED, missing executedQty/filledQty is compensated with the generic quantity field and missing fill ID is replaced by order/proposal ID. A PARTIAL response with price and quantity=10 but no executed value made a fill of 10; cumulative/incremental is also not distinguished. … the claim 'a fill is never inferred' does not hold."

### What I read (files, line ranges, functions, callers)
`apex/ops/paper_loop.py::fill_from_result` (277–302) completely, with its docstring ("Extract the EXECUTED price/quantity … Returns None when the venue did not report both numbers — a fill is never inferred"): the fallback chains `price = avgPrice or price or fillPrice`, `quantity = executedQty or quantity or filledQty`, `fill_id = tradeId or fillId or result.order_id or plan.proposal_id`. Callers (grep `fill_from_result`): `_record_submission_fill` (747–760, source SUBMIT_RESULT) and `_observe_fill` (762–800, source VENUE_QUERY) and `manage_positions` (830–843, exit leg with `suffix="-exit"`); all three feed `machine.record_fill` → `LedgerWriter.append_fill` (Ch.16 fill_id idempotency) → `positions_from_ledger` (the T_MATCH single source of truth). `apex/ledger/store.py::append_fill`/`find_by_fill`/`positions_from_ledger`/`_decimal_str` read completely. `tests/integration/test_ops_paper_loop.py::FakeAdapter` (120–146): every FILLED/PARTIAL response it produces carries `avgPrice` AND `executedQty` AND `tradeId` — the fallback branches are never exercised by the wired tests; `tests/fake_toobit_responder.py` order/query responses also always carry `executedQty` (0 while NEW, cumulative while partially filled).

### Reproduction (command, probe file, actual result)
`python3 -B AUDIT/probes_V1d/E-015.py` (raw output `AUDIT/probes_V1d/E-015.out`), real `fill_from_result` + real `ExecutionFSM.record_fill` + real `LedgerWriter` on temporary SQLite:
- (a) PARTIAL response `{avgPrice:100, quantity:10}` (no executed value) → fill `{'fill_id':'900001','price':'100','quantity':'10'}` — the ORDER quantity is recorded as executed. Exactly the auditor's scenario.
- (b) `executedQty: 0` as a JSON number → falls through `0 or quantity` to the ORDER quantity 10 (falsy-zero bug); as the string `"0"` → a zero-quantity fill is recorded verbatim.
- (c/c2/d) two genuine partials of one order (`executedQty 3 @100`, then `2 @101`, no `tradeId`): both map to `fill_id="900007"`; `append_fill`'s fill_id idempotency then DROPS the second partial — the ledger holds ONE FILL of 3 and `positions_from_ledger` reports net 3 where the venue truth is 5 (and nothing flags the loss).
- (e) FILLED with `avgPrice="NaN"` → recorded verbatim; the ledger position's `average_entry_price` becomes `NaN`, poisoning entry-dependent P/L, outcome records and attribution (quantity reconcile still agrees, so no divergence alert fires).

### Verdict and reasoning
**CONFIRMED, S1.** Every element of the claim is reproduced against the real functions: the missing-executed-quantity fallback to the order `quantity` (contra the function's own "never inferred" docstring and the fail-closed law), the missing-fill-id fallback to `order_id`/`proposal_id` with the resulting silent dedup of subsequent partials, the absence of cumulative-vs-incremental distinction (a cumulative `executedQty` would be double-counted by two polls), and the absence of finite/positive validation. The impact lands directly on the Ch.16 §16.2 single-source-of-truth invariant (T_MATCH): the ledger position silently diverges from the venue. S1 (accounting/reconciliation integrity) is justified: the trigger is a venue response shape the adapter/API accepts, and the code chooses to guess rather than refuse.

### Root cause
`fill_from_result` treats venue fields as interchangeable (`or`-chains with falsy-zero semantics) and synthesises fill identity from non-fill fields, instead of requiring the executed-amount and fill-identity fields the contract's fill model assumes; `record_fill`/`append_fill` then apply fill_id idempotency to the synthesised identity.

### Direct impact
Over-recording (order qty recorded on an unfilled/partial order → phantom position, premature protection sizing), under-recording (real partials deduplicated away → ledger < venue), zero-quantity fills, and NaN money values in the ledger — each silently, with `FILL_DATA_INCOMPLETE` never raised because `price`/`quantity` were "present".

### Secondary effects and interactions (upstream/downstream)
Downstream: `positions_from_ledger` (T_MATCH), `reconcile` deltas, protection quantities, `manage_positions` P/L and outcome records, risk exposure vetoes and the training/outcome lineage all consume the corrupted numbers. Upstream: any venue/adapter response lacking the exact field names (`avgPrice`/`executedQty`/`tradeId`) — the FakeAdapter-based tests always supply them, so the suite cannot catch this. Cross-refs: I-016 (the CP-7 integration test hand-builds FILL and close, consistent with the fake never exercising partial fill data); E-006 (exit management reads only the last close — independent); F-005 (append_fill race — independent).

### Contract and decisions
Binding: APEX_GEN5.md Ch.16 §16.2 "Matching and ledger tests" (in this checkout L17083–17088): "Matching is a first-class invariant: a single source of truth for position state (the ledger, reconciled against exchange), and fills are idempotent under `fill_id`" — fill identity must therefore BE a fill identity, not an order/proposal id. Ch.16 order/identity law (L16910–16917 region): "`intent_id / order_id / fill_id / cancel_id` are unique". G6/P6 fail-closed (an undecidable value refuses, never guesses) governs the missing-field case; P8/G11 (money TEXT-Decimal at boundaries) is violated in spirit by unvalidated NaN text. No decision waives any of this.

### Frozen status and non-frozen alternative
`apex/ops/paper_loop.py` and `apex/ledger/store.py` are not on the V1d frozen list (note: `apex/ledger/store.py` implements the frozen Ch.4/Ch.16 `ledger`/`trade_plan` DDL — a schema change there would need owner review, but this fix needs no schema change). A producer-side strict parser (a wrapper that refuses responses without `executedQty`+fill identity) can live entirely in `apex/ops/`.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A (recommended):** in `fill_from_result`, require a positive finite `executedQty`/`filledQty` (never fall back to order `quantity`), a positive finite price, and a genuine fill identity (`tradeId`/`fillId`); return `None` (→ `FILL_DATA_INCOMPLETE` / reconcile-required) otherwise; treat `executedQty` as cumulative and convert to per-fill deltas by differencing against the last recorded executed amount for that order. Side effects: `manage_positions`/`_observe_fill` currently treat `fill_from_result → None` as "not filled / stays working" — a strict parser therefore parks more orders in ACKNOWLEDGED until reconciliation, which is the contract-correct behaviour but changes cycle outcomes in tests whose fakes omit the fields (the current fakes all supply the fields, so the wired suites stay green); the delta conversion needs the last executed amount per order (ledger query or in-FSM state); no migration, no retraining; old ledger rows written with synthesised ids remain (they are append-only) and need a reconciliation pass to re-derive truth from the venue. **B:** keep the fallbacks but mark such fills `INFERRED` and force reconcile-required. Weaker: the ledger still contains the guessed numbers. **C:** do nothing, rely on the venue always sending `executedQty` — rejected: unverifiable and contradicts fail-closed.

### My recommendation
A. Fill data is accounting data; absence must be a named refusal (reconcile-required), never a guess.

### Acceptance and regression tests
PARTIAL without executedQty, executedQty=0 (number and string), NaN/inf price or quantity, missing tradeId with multiple partials, cumulative executedQty across polls — each must produce NO fabricated fill (named refusal `FILL_DATA_INCOMPLETE` / reconcile-required), no zero/NaN ledger row, and no silent dedup of a genuine second partial; a well-formed partial pair must still sum to the venue truth. Existing CP-7/CP-9 integration tests (which supply well-formed fills) must pass unchanged. Before any LIVE claim, read-only device evidence is needed: sample real venue order-query/userTrades responses to confirm they always carry `avgPrice`/`executedQty`/`tradeId` and whether `executedQty` is cumulative.
