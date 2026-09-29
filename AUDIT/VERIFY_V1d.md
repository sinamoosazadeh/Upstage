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

## E-017

### Auditor claim (short quote)
"the X.2 rule 'EXTREME ⇒ trail off' is applied only in the trail_atr_mult=None branch. With entry=100,stop=98,current=110,EXTREME, the fallback stayed inactive but the playbook's explicit coefficient of 1 gave activated=True,stop=109. The existing test measures EXTREME only without an explicit coefficient."

### What I read (files, line ranges, functions, callers)
`apex/playbook/pb_fvg_sweep_rev_a.py` completely: `TRAIL_FACTOR_BY_VOLATILITY` (83–90, `"EXTREME": None` — "trailing DISABLED; fixed stops only"), `trail_factor_for` (201–219 — returns `trailing_enabled: regime != "EXTREME"` on both the fallback and the package path), `trailing_state` (458–508 — the branch under test), `PLAYBOOK_PARAMS` (74–86, `trail_after_r=1.5`, `trail_atr_mult=1.0`), the module docstring's X.2 summary ("volatility Extreme disables trailing and reverts to the fixed stop") and the ISSUE-CP6-003 conflict note (instantiated playbook values override the generic X.1–X.3 tables for BE trigger / trail distance / max_hold). Callers (mandatory grep): `trailing_state` has NO production consumer — only `apex/playbook/__init__.py` re-export and `tests/unit/test_playbook_pb_fvg_sweep_rev_a.py`; `paper_loop.manage_positions` (803–899) never calls it (that gap is E-006's scope). Test `test_trail_activation_and_extreme_disable` (311–325): the EXTREME case (`ext`) is constructed WITHOUT `trail_atr_mult`, so only the fallback path is asserted.

### Reproduction (command, probe file, actual result)
`python3 -B AUDIT/probes_V1d/E-017.py` (raw output `AUDIT/probes_V1d/E-017.out`), real `trailing_state` with `entry=100, current_stop=98, atr=1, trail_after_r=1.5`:
- fallback (`trail_atr_mult=None`), EXTREME, current=110 → `activated=False, trailing_disabled_by_regime=True, stop=98.0, reason=VOLATILITY_EXTREME_FIXED_STOP` (contract behaviour).
- explicit `trail_atr_mult=1.0` (the frozen playbook coefficient), EXTREME, current=110 → **`activated=True, trailing_disabled_by_regime=False, stop=109.0, distance=1.0`** — exactly the auditor's numbers; the EXTREME rule is bypassed.
- package path (`package={"trail_factor":2.0}`, no explicit mult), EXTREME → disabled (this path honours the regime).
- SHORT mirror with explicit mult under EXTREME → `activated=True, stop=91.0` — both directions affected.
- `trail_factor_for("EXTREME")` itself correctly returns `trailing_enabled=False`; only the explicit-mult branch ignores it.

### Verdict and reasoning
**CONFIRMED, S2.** In `trailing_state`, `tf_info` defaults to `{"trailing_enabled": True, ...}` and is only replaced by `trail_factor_for(regime, package)` when `trail_atr_mult is None`; the EXTREME gate therefore never runs for an explicit multiplier — precisely the frozen playbook coefficient (`trail_atr_mult=1.0`), which is the value any faithful wiring of the instantiated playbook would pass. The auditor's scoping is accurate: the helper is not yet consumed by PAPER exit management (E-006), so today's impact is on the helper's own contract correctness and on any future/research consumer; S2 (limited current impact) is right.

### Root cause
The regime gate lives inside the factor-resolution helper rather than in `trailing_state` itself, so the "instantiated coefficient" code path (`trail_atr_mult is not None`) skips the volatility-regime evaluation entirely.

### Direct impact
If/when the helper drives real stop management, a volatility regime classified EXTREME would still ratchet the trailing stop — the exact "protective reflex" X.2 disables (trailing degrades in extreme volatility; the system must revert to fixed/breakeven stops only).

### Secondary effects and interactions (upstream/downstream)
Downstream: trail attribution records (`trailing_activated`, `trailing_distance_final`) become contract-inconsistent; outcome/learning-loop and Risk-Optimizer inputs inherit the wrong stop trajectory; backtest attribution (Ch.11 X.2 "recorded in the trade Outcome record") is polluted. Upstream: none. Interactions: E-006 (management not wired), E-018 (activation flicker in the same function). ISSUE-CP6-003 gives the INSTANTIATED VALUES precedence over the generic tables for the trail DISTANCE — it does not and cannot waive the EXTREME-disable rule, which is a separate normative clause of X.2, not a table value.

### Contract and decisions
Binding: APEX_GEN5.md Ch.11 §11.2 X.2 (in this checkout ~L15763–15778): the regime table row "Extreme (top 10th percentile) | Trailing DISABLED; fixed stops only (protective reflex)" and "If volatility enters the Extreme regime while a position is held, trailing-stop management is immediately disabled, and the stop reverts to fixed-stop behavior (either initial stop or breakeven-adjusted stop, whichever is current); no new trailing adjustments occur until volatility returns to High or lower." `PHASE2_DECISION_LOG.md` ISSUE-CP6-003 (L143) applies the playbook-specific instantiation only to the BE/trail/max_hold VALUES conflict. Precedence: the EXTREME clause is unconditional contract prose; ISSUE-CP6-003 does not mention it, so the contract governs.

### Frozen status and non-frozen alternative
`apex/playbook/pb_fvg_sweep_rev_a.py` is not on the V1d frozen list. The AE.5 literal values (`trail_after_r=1.5`, `trail_atr_mult=1.0`) are contract-frozen and must not change — but the fix changes WHEN trailing applies, not the values. A caller-side guard (a wrapper that checks the regime before calling with an explicit mult) is possible outside the module.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A (recommended):** evaluate the EXTREME gate in `trailing_state` itself, before factor resolution, independent of the coefficient source (explicit mult, package, or fallback): if the regime is EXTREME, return the disabled record with the current (or breakeven) stop and no trailing adjustment. Side effects: `test_trail_activation_and_extreme_disable` must be extended with an explicit-mult EXTREME case (existing cases keep passing — they already expect disable on the fallback path); `test_trail_never_widens_and_follows_price_up` unaffected (NORMAL); no identity/hash/migration impact; backtests that used the helper with explicit mults under EXTREME would need re-running for attribution correctness (no model retraining). **B:** make the explicit-mult path also consult `trail_factor_for` for the enabled flag only — same effect as A with slightly more coupling. **C:** document that the instantiated playbook overrides the EXTREME rule — rejected: contradicts the unconditional contract clause and the module's own docstring.

### My recommendation
A, and keep the coefficient provenance (`source`) in the record for attribution.

### Acceptance and regression tests
For LONG and SHORT, EXTREME with (i) explicit mult, (ii) package factor, (iii) fallback must all return `trailing_disabled_by_regime=True` with the stop unchanged; NORMAL/HIGH/LOW with explicit mult must retain current behaviour (activation, ratchet, never-widen); the existing playbook tests must pass unchanged except for the new EXTREME-with-mult case. Re-run the CP-6 chain test (which uses `build_stops`/`instantiate_playbook` only) to confirm no regression.

## E-018

### Auditor claim (short quote)
"the trail activation threshold is recomputed from abs(entry-current_stop), not the fixed initial R. long with entry=100,initial_stop=98,current=104 activated and stop=103 became; a subsequent call at 104.2 with current stop 103 incorrectly gave activated=False. The test only checks stop monotonicity, not persistence of the activation state."

### What I read (files, line ranges, functions, callers)
`apex/playbook/pb_fvg_sweep_rev_a.py::trailing_state` (458–508) completely: `R = abs(entry - current_stop) if current_stop else 0.0`; `activated = progress >= trail_after_r * R - 1e-12`; the ratchet `new_stop = max(current_stop, candidate)`/`min(...)`. The function is STATELESS between calls — the caller must pass `current_stop`, and nothing carries the initial R or the activation latch. `breakeven_state` (413–456) for the X.1 contrast (its docstring and the contract both fix R at inception). Callers (grep): no production consumer (same as E-017); test `test_trail_never_widens_and_follows_price_up` (327–339) asserts only `second["stop"] >= first["stop"]` on the second call — exactly the monotonicity-only assertion the audit names.

### Reproduction (command, probe file, actual result)
`python3 -B AUDIT/probes_V1d/E-018.py` (raw output `AUDIT/probes_V1d/E-018.out`), real `trailing_state`, LONG `entry=100, initial_stop=98` (initial R=2), `trail_after_r=1.5`, `atr=1`, `trail_atr_mult=1.0`:
- call 1 at current=104: `activated=True, stop=103.0` (progress 4 ≥ 1.5×2=3).
- call 2 at current=104.2 with the ratcheted stop 103: `activated=False, stop=103.0` — R recomputed as 3, threshold 4.5 > progress 4.2. With the initial R=2 the threshold would be 3.0 ≤ 4.2 and activation would persist (printed side by side in the .out).
- call 3 at current=105: `activated=True, stop=104.0` — the flag flickers back on with price, so activation is a function of the current stop, not a latched state.
- SHORT mirror (entry=100, stop=103, R=3): call 1 at 95.2 → `activated=True, stop=96.2`; call 2 at 95.4 → `activated=False` — both directions affected.

### Verdict and reasoning
**CONFIRMED, S2.** The code recomputes the risk unit from the CURRENT stop on every call, so each ratchet raises the activation threshold (for a winner, `trail_after_r × R_new`), and the activated flag can turn off although price never retreated — the trailing mechanism can silently stop following price after the first ratchet, leaving the stop stale. The contract fixes R "at trade inception … does not change" (X.1) and X.2's activation is "a minimum of 1.0R of profit" against that same risk unit; the code violates both. The auditor's numbers reproduce exactly. S2 is right: the helper is not wired into PAPER management yet (E-006), so the impact is on the helper's correctness, backtest/attribution fidelity, and any future consumer.

### Root cause
`trailing_state` derives R from the mutable `current_stop` argument instead of requiring the immutable initial stop (or a persisted activation state); it is a pure function asked to implement a stateful rule.

### Direct impact
After the first ratchet, subsequent trail adjustments can be suppressed (activated=False) while price advances; the stop stays at a stale level until price rises far enough to clear the inflated threshold — i.e. LESS protection locked in than the contract's trail, and non-monotone activation behaviour that no test pins.

### Secondary effects and interactions (upstream/downstream)
Downstream: attribution records (`trailing_activated` flickering), Risk-Optimizer backtests and outcome labels inherit a trail trajectory that differs from the contract; if wired later into `manage_positions`, live stops lag. Upstream: the caller must supply `current_stop` — no API even accepts the initial stop. Interactions: E-017 (same function, EXTREME bypass), E-006 (management path unwired), breakeven X.1 (its `R = abs(entry - initial_stop)` is correct — the defect is trail-specific).

### Contract and decisions
Binding: APEX_GEN5.md Ch.11 §11.2 X.1 (in this checkout ~L15744–15748): "R is the risk unit defined as the absolute difference between entry price and the initial stop-loss price (|entry − initial_stop|). This R is fixed at trade inception and does not change"; X.2 (~L15760–15763): "Trailing-stop protection activates only after the trade has progressed a minimum of 1.0R in the favorable direction" — the same fixed R. No decision addresses trail activation state. Precedence: contract governs.

### Frozen status and non-frozen alternative
`apex/playbook/pb_fvg_sweep_rev_a.py` is not on the V1d frozen list; the AE.5 literals are contract values and are untouched by this fix. A non-module alternative: a stateful management wrapper (in `apex/ops/`) that persists the initial R and the activated latch and calls the pure function with the initial R semantics — but the function's signature would still invite the misuse.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A (recommended):** change `trailing_state` to take the INITIAL stop (or the inception R) plus an explicit `activated` latch: activation is evaluated once against the initial R and then persists (ratchet-only thereafter); keep `current_stop` for the never-widen ratchet. Side effects: signature change — the existing tests (311–339) call it with `current_stop=98` as the initial stop and would keep passing if `current_stop` is interpreted as the initial stop on the first call, but the second-call test would need the new `activated=True` input; the `record` gains a stable `trailing_activated`; no migration/retraining; backtests that used the flickering semantics must be re-run for attribution. **B:** keep the signature, derive R from `entry` and a new REQUIRED `initial_stop` parameter, and treat activation as latched once true — same effect, clearer API. **C:** document the current behaviour as "threshold scales with the ratchet" — rejected: contradicts X.1/X.2.

### My recommendation
B (explicit `initial_stop` + latched activation), with restart/partial-exit semantics (E-019's remainder bookkeeping) defined in the same state object.

### Acceptance and regression tests
LONG and SHORT: two or more consecutive closes beyond 1.5R (audit's 104 then 104.2 case) must keep `activated=True` and ratchet monotonically; a price retreat must never lower the stop; activation must never flip off once set; the existing monotonicity test must still pass; a restart of the manager from persisted state must reproduce the same latch. Re-run attribution/backtest smoke tests after the change.

## E-019

### Auditor claim (short quote)
"apply_partial_exit only validates a positive sum: weights (-0.5,1.5) from qty=10/risk=4 make qty=15/risk=6, despite the scaling-in prohibition. Also sequential execution of (0.3,0.4,0.3) on the remainder leaves qty=2.94 after all three steps; the meaning of weight relative to total/remainder must be made explicit."

### What I read (files, line ranges, functions, callers)
`apex/playbook/pb_fvg_sweep_rev_a.py::apply_partial_exit` (593–619) completely: the only gates are `not weights or sum(weights) <= 0` (PB_LADDER_QX), `taken_index` range (PB_LADDER_INDEX_QX) and `sized_quantity < 0 or reserved_risk < 0` (PB_POSITION_QX); `share = weights[taken_index]/sum(weights)`; `qty = max(0, sized_quantity*(1-share))`; `risk = max(0, reserved_risk*(1-share))`; stop never widened (max/min with `proposed_new_stop`). `PLAYBOOK_PARAMS["staged_exit_ratios"] = (1.0,)` (92). `pyramiding_policy` (621–630) and the module docstring's Ch.9 §9.0 summary ("scaling-in DISABLED … every partial exit reduces sized_quantity and the reserved risk proportionally"). Callers (grep): no production consumer (only `apex/playbook/__init__.py` re-export and tests); tests `test_partial_exit_reduces_quantity_and_risk_proportionally` (371–379), `test_stop_is_never_widened_by_a_partial_exit` (381–402), `test_ladder_validation` (404–414) — none use negative/NaN weights or repeat an index.

### Reproduction (command, probe file, actual result)
`python3 -B AUDIT/probes_V1d/E-019.py` (raw output `AUDIT/probes_V1d/E-019.out`), real `apply_partial_exit`:
- (1) `ladder_weights=(-0.5, 1.5)`, `taken_index=0`, from qty=10/risk=4 → **`qty=15.0, risk=6.0, closed_fraction=-0.5`** — a "partial exit" that INCREASES position size and reserved risk, i.e. scaling-in, which Ch.9 §9.0 and `pyramiding_policy` forbid. Exactly the auditor's numbers.
- (2) `ladder_weights=(nan, 1.0)`, `taken_index=0` → passes the gates (NaN comparisons are False) and yields `closed_fraction=nan`, `qty=0.0, risk=0.0` (NaN arithmetic collapsing through `max(0.0, nan)`).
- (3) sequential 30/40/30 applied to the REMAINDER: 10 → 7.0 → 4.2 → **2.94** remaining after all three steps (risk 1.176), where a ladder summing to 1 over the initial size should leave 0.
- (4) taking the SAME index twice is not refused (10 → 5 → 2.5).
- (5) the frozen single-rung ladder `(1.0,)` still reduces to qty=0/risk=0 — the currently frozen configuration is unaffected.

### Verdict and reasoning
**CONFIRMED, S2.** All three claims reproduce with the real function: negative weights pass the `sum > 0` gate and grow the position (forbidden scaling-in); the weight semantics relative to total-vs-remainder are undefined in code (each step divides the CURRENT remainder, so a full ladder leaves residue (1−w₀)(1−w₁)(1−w₂)); and per my probe the validation is weaker still — NaN weights and repeated indices also pass. The frozen ladder `(1.0,)` and the absence of any production caller keep this at S2 today, exactly as the auditor scoped it ("the current ladder is only (1.0,) and PAPER does not consume it").

### Root cause
The validation checks only `sum(weights) > 0` rather than each weight being finite and non-negative (and the ladder being index-disjoint); and the reduction applies `share` to the CURRENT remainder without carrying the initial quantity or the set of already-taken rungs, leaving the total/remainder semantics implicit.

### Direct impact
Any future multi-rung ladder (or a package injecting one) can, on a negative weight, INCREASE size and reserved risk through the "partial exit" API — inverting the Ch.9 §9.0 law that partial exits only reduce — or silently leave 29.4% of the position open after a "complete" ladder, or zero it out on a NaN weight.

### Secondary effects and interactions (upstream/downstream)
Downstream once wired to the FSM/ledger (E-006's gap): position and reserved-risk bookkeeping diverge from fills and caps; the never-widen stop rule still holds (verified in the same function) but on the wrong quantity; outcome/risk-attribution records inherit wrong sizes. Upstream: parameter packages (Risk Optimizer X.6) are the plausible source of a multi-rung ladder. Interactions: E-005 (partial treated as full close in `manage_positions` — independent), F-001 (fill accounting — independent), Ch.9 §9.0 (the governing scaling law).

### Contract and decisions
Binding: APEX_GEN5.md Ch.9 §9.0 "Position scaling policy (normative)" (in this checkout ~L15055–15061): "Scaling-in (pyramiding) is disabled: one trade plan maps to exactly one position per (symbol, timeframe, direction) until CLOSED. Scaling-out is permitted only through the Playbook target ladder (partial target takes), and every partial exit reduces `sized_quantity` and the reserved risk amount proportionally; the stop for the remainder is never widened." Ch.11 AE.5 freeze pins the current single target `staged_exit_ratios (1.0,)` (target 100% at 3R). No decision defines total-vs-remainder weight semantics. Precedence: contract governs; the frozen `(1.0,)` ladder is the only lawful configuration today, which is why current impact is contained.

### Frozen status and non-frozen alternative
`apex/playbook/pb_fvg_sweep_rev_a.py` is not on the V1d frozen list; the AE.5 `staged_exit_ratios=(1.0,)` literal IS a frozen contract value and must not change — the fix tightens validation of CALLER-supplied ladders, not the frozen ladder. A wrapper that validates ladder packages before they reach the function can live outside the module.

### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A (recommended):** validate `math.isfinite(w) and w >= 0` for every weight, refuse duplicate/repeated `taken_index` consumption via carried state (initial quantity + taken set, or a rung bitmask), and define weights as shares of the INITIAL size (documenting the choice against Ch.9 §9.0's "reduces … proportionally"), computing each step's exit quantity as `initial*weight` rather than `remainder*(weight/…)`. Side effects: the existing test's arithmetic (10 → 7.0 for a 0.3 share of the initial size) is unchanged when weights are interpreted over the initial size and steps are disjoint; the sequential 30/40/30 case then correctly reaches 0; tests for negative/NaN/duplicate rungs must be added; no migration/retraining; any research/backtest code that fed ad-hoc ladders would now be refused (correctly). **B:** keep remainder semantics and require `sum(weights) == 1` with explicit "remainder share" documentation — smaller change but leaves the drift-toward-residue behaviour. **C:** only add the non-negativity gate — rejected: leaves the residue and duplicate-index holes.

### My recommendation
A, with the taken-rung state carried by the position-management state object proposed in E-018's fix (one stateful manager for BE, trail, ladder).

### Acceptance and regression tests
Weights with any negative or non-finite member → `PB_LADDER_QX`-style refusal by name; repeated consumption of one rung → refusal; 30/40/30 over the initial size ends at qty=0 and risk=0; the frozen `(1.0,)` ladder unchanged (qty=0, risk=0, stop never widened); the existing three scaling tests keep passing; the never-widen assertions (LONG and SHORT, proposed stop loosening) keep passing.
