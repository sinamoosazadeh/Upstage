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
