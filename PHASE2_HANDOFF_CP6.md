# PHASE2 HANDOFF — CP-6 → consumed by CP-7 (and CP-8 closeout)
Stage: CP-6 — Context chain (Ch.8–12) + Forecast/Decision/Risk (Ch.13–15)
Rules (PROTOCOL P16): author = CP-6 executor (or its continuation session — state which, first line of STATUS). ≤400 lines, nine headings below in order. Successors read ONLY this file + their own prompt/law/checkpoint sections; interfaces listed here are the public contract they may code against. First STATUS line: `LAW-ACK: G1..G20 + P1..P21 read <UTC>`.

## STATUS
LAW-ACK: G1..G20 + P1..P21 read 2026-09-13T11:38Z (author: the CP-6 session in Arena Agent Mode, branch `arena/01a097fa-upstage`; ADR-P2-015 from-zero — no prior implementation attempt was read, referenced, or reused).
complete — stage fully closed. Suite totals: **1550 passed / 0 failed** (`bash scripts/run_all_tests.sh`; 502 of them CP-6: unit 489 + integration 13). Entry gate re-verified at session start (CP-5 close 1048/0); `sha256(APEX_GEN5.md) == 216bcc9e…bd9e` verified at session start. Environment: Linux sandbox, Python 3.11 `.venv` with the nine SBOM pins from `requirements.lock` (+ pytest dev-only, ADR-P2-002); no other third-party imports in CP-6 code (numpy NOT used by this stage).
ENV NOTE (push): all CP-6 commits are on `origin/arena/01a097fa-upstage` and open as **PR #7** (`arena/01a097fa-upstage` → `main`); the mid-session GitHub-token expiry was resolved by the owner reconnecting — commits `6e27169..HEAD` are pushed. Owner merges into main with a plain merge commit (never squash, per the ENV NOTE of this stage).
Blueprint reading: Ch.8 L14672–15011 · Ch.9 L15012–15532 · Ch.10 L15533–15750 · Ch.11 L15751–15847 · Ch.12 L15848–15971 · Ch.13 L15972–16517 · Ch.14 L16518–16590 · Ch.15 L16591–16749 — read IN FULL, in chapter order, before implementation; the six build groups landed in the mandated order (fabric → context/conflict → pattern/fibonacci → setup/gates → playbook → forecast/decision/risk).

## DELIVERED
(file | purpose | blueprint section | rows into MATRIX Part III)

| file | purpose | blueprint section | MATRIX Part III rows |
|---|---|---|---|
| `apex/fabric/evidence.py` | SL-14 lifecycle machine + engine-local crosswalk (emitted≡ACTIVE, expired≡EXPIRED, superseded≡SUPERSEDED; unknown label raises), expiry 5×TF law, freshness decay, `FabricEvidenceRef`, `EvidenceFabric.assemble` (admission = ACTIVE ∧ scope ∧ PIT ∧ freshness; exclusions carry reasons, never repairs), `fabric_from_events` adapter for frozen 24-field events | Ch.8 §8.0 (L14672–) + Ch.2 §2.1 | `C6-SL14\|1..3` |
| `apex/fabric/context.py` | twelve frozen context weights asserted FROM `params/setup_weights_v1.yaml`, `context_confidence` sigmoid combiner (solvency collapse < 0.30 data_trust / q_raw below per-TF Q_min), bands 0.70/0.50/0.30 as CLASSIFICATION only, `build_context` (confidence is produced, never injected), the single `setup_score`/`raw_setup_score` authority with the vacuous-pass guard, MTF multipliers, R_penalty ladder | Ch.8 §8.0 + Ch.10 §10.1 (L15237 weights table) + Global Contracts | `C6-CTX\|1..4` |
| `apex/fabric/conflict.py` | `resolve` → exactly 4 terminals; the seven §8.1 invariants; ×0.6 conflict multiplier; ρ>0.85 ⇒ 0.50× halving on the lower-Q component (measured ρ never conflated with the Gate-4 penalty); `monotone_ok`; §8.2 records (Conflict/Divergence/SMT/Correlation); `correlation_exposure` strict `rho > cap 0.70` ⇒ REDUCE scaled to cap | Ch.8 §8.1–§8.3 | `C6-CFL\|1..3` |
| `apex/pattern/detect.py` | 20-row legacy catalogue → AC.1 `PatternEntity` (research-only rows can NEVER carry a scoring class), 13 deterministic detectors on `{o,h,l,c}` bars, Spring/Upthrust DELEGATION to frozen E08 `detect_spring`/`spring_recovered`/`detect_ut`, `detect_all` battery entry, invalidation-as-removal | Ch.9 §9.1–§9.2 | `C6-PAT\|1..3` |
| `apex/pattern/fibonacci.py` | in-repo Fibonacci suite (Level(r)=A+r(B−A), retracements/extensions/expansion, OTE 0.62–0.79, 0.886 PRZ, golden identities) — NO network (AI.12; source-scan tested) | Ch.9 (fibonacci section) | `C6-FIB\|1` |
| `apex/setup/gates.py` | all 13 hard gates as individually callable functions (`gate1..gate13`, `evaluate(n, …)`, `run_all`), each with its ±1-unit boundary; Gate 11 = snapshot/lineage integrity ONLY (recomputes `sha256(canonical_json(payload))`, well-formed lineage tokens down to raw observation_id); Gate 10 refuses the bootstrap prior for LIVE | Ch.10 §10.1 (L15232–15260) | `C6-G01…C6-G13` |
| `apex/setup/family_sf_fvg_sweep_rev.py` | the ONLY Wave-In family over the full 140-cell (10 symbols × 14 TFs) grid: `EL_SWEEP_RECLAIM_FVG` steps 1–6 in normative order, relative-MTF law (documented vacuous pass at 1mo; missing ≠ vacuous), S_struct ≥ 0.55 inclusive, `evaluate_cell` → `SetupEvaluation.to_setup_event()` = setup_candidate's 21 frozen DDL columns + AD.1 additive field 22 `family_id`; second family ⇒ `WaveOutError` | Ch.10 §10.2 AD.1–AD.8 | `C6-FAM\|1..3` |
| `apex/playbook/pb_fvg_sweep_rev_a.py` | PB_FVG_SWEEP_REV_A: AE.1 16-field template with field-level fail-closed validation, AE.2 lifecycle (owner-gated DEPRECATED), AE.5 literals (BE 1.0R, trail_after 1.5R, 1.0×ATR, max_hold 16 bars — ISSUE-CP6-003), X.1 stop buffer, X.2 extreme-regime disable, X.4 exhaustive exit precedence, X.6 partial exits, scale-OUT only, never-widened stop | Ch.11 (AE.1–AE.5, X.1–X.6) | `C6-PB\|1..3` |
| `apex/forecast/logistic.py` + `registry.py` | bootstrap `p_raw = σ(β0+β·x)`, β=β0=0 ⇒ EXACTLY 0.5, complete 12-feature vector enforced; P/U/C record (both U/C laws), composite estimator (shrinkage + ensemble redistribution, refuses vacuous input), 7 immutable invalidation reasons, horizon/decay (λ=0.1), `build_forecast` refuses LIVE for bootstrap-only (`FORECAST_BOOTSTRAP_NOT_LIVE_ELIGIBLE`), `ForecastRecord.invalidate`, platt/isotonic OOS = Wave-Out; AG registry: 12 models bound to q_i only, E11-AG research-only with no consumer | Ch.13 §13.1–§13.3 + registry | `C6-FC\|1..2`, `C6-AG\|1` |
| `apex/decision/pipeline.py` | EU strictly in units of R (RR floored 0.5, R=0 fails closed), ADV-slippage model, 8-condition eligibility (P/C shortfall ⇒ INSUFFICIENT_EVIDENCE, never a guess-based entry), `generate_candidates` (monotone_ok BEFORE ranking — SL-2), deterministic rank + tie-breakers, `select` caps at governed 3, `arbitrate` (AF.3 hard regime-window boundary + family-status filter + opposite-direction gap > 0.15 else NO-TRADE first-class), `StrategyProposal` (the §INTERFACES shape) | Ch.12 AF.3/AF.4 + Ch.14 §14.1–§14.3 | `C6-DC\|1..3` |
| `apex/risk/kernel.py` | Canonical Risk Veto Registry: exactly 14 vetoes evaluated IN NUMBERED ORDER before any sizing (incomplete registry raises), the Ch.15 §15.3 sizing machine in its exact order (Capital≤0 / StopDistance≤0 / multiplier≤0 guards BEFORE any division; ladder bands 25/50/75 % inclusive with multipliers 1.0/0.5/0.25/0; Q-floor; Q==0 ⇒ PORTFOLIO_CAPACITY), margin health 60/40/20, Y.2 leverage caps, CVaR advisory-only, circuit-breaker resets, RSK-ERR-506 ratchet (4 blocked downgrades, owner-gated L1→NORMAL resume), `apex_risk_ladder_state` DDL + M100 migration hook (ADR-P2-004), `adjudicate` = the Trade Plan builder | Ch.15 (registry L15972–? adjudication + L14664 ratchet row) + Ch.19 ceiling law | `C6-V01…C6-V14`, `C6-SZ\|1..3`, `C6-FB\|1`, `C6-RSC\|1`, `C6-SEAM\|1` |
| `params/setup_weights_v1.yaml` (appended keys only) | governed CP-6 numbers: `context_bands {0.70,0.50,0.30}`, `propagation_confirmatory_threshold 0.40`, `data_trust_floor 0.30`, `context_decay_per_bar 0.05`, `evidence_decay_per_bar 0.02`, `gate_score_unit 0.01`, `gate_quality_min_class 2`, `gate_forecast_q_min 0.5`, `family_s_struct_min 0.55` — every frozen CP-1 value untouched | §9.5 + Ch.8/§10.1 | cited in `C6-CTX\|1..2`, `C6-FB\|1` |
| `tests/fixtures/gf_sc_01.json` · `gf_sc_02.json` | hand-built 20-bar Spring/Upthrust fixtures per ADR-P2-007/014: documented extremes preserved exactly, `expected {sc, vol_ratio, range_z}` RE-DERIVED from E08 at test time, `sha256:` hash computed after the fixture exists; GF_SC_03..12 = schema-only assertions (no bar data invented) | Ch.9 §9.1 golden cases | cited in `C6-PAT\|3` |
| `tests/unit/test_fabric_evidence.py` (43) · `test_fabric_context.py` (63) · `test_pattern_detect.py` (50) · `test_pattern_fibonacci.py` (19) · `test_setup_gates.py` (29) · `test_setup_family_sf_fvg_sweep_rev.py` (92) · `test_playbook_pb_fvg_sweep_rev_a.py` (42) · `test_forecast_logistic.py` (41) · `test_decision_pipeline.py` (34) · `test_risk_kernel.py` (76) | the stage batteries (all rows above) | Ch.8–§15 acceptance law | all C6-* rows |
| `tests/integration/test_context_to_trade_paper.py` (13) | **the PAPER end-to-end chain** (real E08 evidence → SL-14 → fabrics → pattern → family+gates → forecast → arbitration → proposal → adjudication → sized plan; veto flip; stub-execution seam) + **T-DR-001/002/003** byte-identical re-runs over the whole CP-6 stack | CP-6 EXIT + AI.10 L18920–18922 | `X-10`, `X-11` |

Foundation, engine packages, the frozen DDL and all frozen params values were **consumed, never patched** — the only pre-CP-6 file this stage touched is `apex/fabric/context.py`… which is NOT pre-CP-6 (CP-6 owns it): the mid-stage integration found and fixed a real defect there (`setup_score` raised KeyError for a fabric member whose component is present in the engine map but unscored — the established law "absent components contribute nothing" now governs; unit regression `test_unscored_engine_in_fabric_contributes_nothing` pinned). No foundation file appears in this stage's diff.

## INTERFACES
(module | class/function | signature | semantics | version) — per the board's stage rule, CP-6's public contract to CP-7 is EXACTLY the three shapes: **StrategyProposal**, the **Trade Plan** (adjudicated sizing), and the **veto-result**. CP-7 must NOT open CP-6 bodies; nothing else here is a contract. All three are `contract_version "4.0.0"`.

### 1 · StrategyProposal — `apex.decision.pipeline`
`StrategyProposal(setup_id, direction, entry_logic_ref, stop, targets, sizing_request, EU, PUC, conflict_state, snapshot_id, arbitration_reason?, contract_version)` — frozen dataclass; `PORTFOLIO_PROPOSAL_FIELDS` = the first ten names above.

| field | type | semantics for the consumer |
|---|---|---|
| `setup_id` | str | `setup-<32hex>` identity of the Ch.10 cell that produced the plan; join key back to setup_candidate materialization |
| `direction` | str | `"LONG" \| "SHORT" \| "NO_TRADE"` — NO_TRADE proposals carry `stop=None, targets=()` and are final (never retry them) |
| `entry_logic_ref` | str | `"EL_SWEEP_RECLAIM_FVG"` — provenance only; CP-7 must not re-evaluate entry logic |
| `stop` | float | absolute price level (already includes the X.1 buffer: `min(sweep_low, fvg_low) − 0.25·ATR` for LONG, mirrored SHORT) |
| `targets` | tuple[float, …] | absolute price levels, in play order (the playbook's staged exits; `target_r 3.0` pinned at inception) |
| `sizing_request` | dict | `{requested, R_unit, RR, stop_distance, target_distance}` — a REQUEST, never a forced fill; `FORBIDDEN_FIELDS = ("order","order_type","client_order_id","leverage","margin_mode","position_id")` — an exception (`DecisionError PROPOSAL_AUTHORITY_QX`) if any appears (the guard is re-asserted at the stub seam; CP-7 must keep requests out of proposals) |
| `EU` | float | expected utility in units of R (already net of cost + R_penalty); informational for CP-7 |
| `PUC` | dict | `{P, U, C}` — the forecast triple behind the proposal (bootstrap P=0.5 means PAPER-only; see §4 note) |
| `conflict_state` | str | one of the four Ch.8 terminals — CP-7 never re-adjudicates conflicts |
| `snapshot_id` | str | 64-hex identity of the fabric payload every scored object shares; ledger rows must store it (lineage, P6) |
| `proposal_id` | property | `"sp-" + sha256(canonical_json(to_dict()))[:32]` — idempotency key for the execution dedup law (same bytes ⇒ same id; do not recompute from `to_dict()` additions) |

Build ONLY via `apex.decision.pipeline.build_proposal(...)` (constructor validates field-by-field). `to_dict()` = the ten fields + `arbitration_reason` + `contract_version`.

### 2 · Trade Plan — `apex.risk.kernel.adjudicate`
`adjudicate(risk_input: Mapping) -> Dict` — required input keys (missing ⇒ `RiskError RISK_INPUT_QX`): `snapshot_id`, `timeframe`, `capital`; sizing needs `stop_distance`, `min_quantity`; optional `package`, `risk_state`, `q_raw`, `atr_cap`, `correlation`, `cvar_fraction` and the 14-veto evidence fields (per-veto names as in `apex/risk/kernel.py` docstrings/tests).

| output key | type | semantics |
|---|---|---|
| `decision` | str | `"ALLOW" \| "REDUCE" \| "REJECT"` — REDUCE only from the correlation path; REJECT carries `sized_quantity 0.0` |
| `sized_quantity` | float | exchange-quantity ALREADY floor-stepped by `min_quantity`; treat as the ceiling — never size above it |
| `selected_parameter_package` | dict \| None | the governed package the plan was sized under (None on REJECT-before-sizing only if input carried none) |
| `vetoes_applied` | list[int] | fired veto numbers (empty on ALLOW); **ordering law: the 14 vetoes were all evaluated BEFORE any sizing arithmetic** — proven by the next two keys |
| `veto_evaluation_order` | list[int] | always `[1..14]` (the registry guard `VETO_REGISTRY_INCOMPLETE` makes a short evaluation impossible) |
| `sized_after_all_vetoes` | bool | `False` exactly on the veto-REJECT path (no sizing object was produced — `veto_detail` replaces `sizing`) |
| `snapshot_id` | str | echoed from input — bind it to every ledger row |
| `sizing` | dict | on non-veto paths: `{R_allowed, multiplier, q_risk_bound, q_attention_bound, min_quantity, notes, correlation, risk_state, decision, sized_quantity, reason}` — for audit/ledger detail only; quantity math is already applied |
| `reason` | str | `SIZED` or the machine's reason (`CAPITAL_NON_POSITIVE`, `STOP_DISTANCE_INVALID`, `CONTRACT_MULTIPLIER_INVALID`, `PORTFOLIO_CAPACITY`, `HARD_VETO`, `PARAMETER_PACKAGE_INVALID::…`, `LADDER_CRITICAL_RISK` override) |

### 3 · Veto result — `apex.risk.kernel.evaluate_vetoes`
`evaluate_vetoes(risk_input) -> {"fired": [{number, name, measured, error_code}, …], "fired_numbers": […], "evaluated_in_order": [1..14], "veto_count": 14, "any": bool, "note": str}`. `fired[i].error_code` is `None` for vetoes 3/5/6/9/10/11/12/13/14 (ISSUE-CP6-004: the Ch.15 `CIRCUIT_OPEN (Alert Policy)` string is NOT in the frozen Ch.7 registry — do not invent it); codes that exist are Ch.7 `ErrorCode` strings via `apex.errors.get_error_code`. Alert policy rows in Ch.23 must key off `fired_numbers`, never off the absent code. Names via `apex.risk.kernel.veto_definition(n)` (registry string is built through the frozen registry).

### 4 · Notes bound to all three shapes
- Environment law (Ch.13 §13.1, asserted at build time): a bootstrap prior (`P=0.5`, no calibrated WFO package) is RESEARCH/PAPER/BACKTEST only — CP-7 wires LIVE execution to NO source that lacks a calibrated package; refusal is `ForecastError FORECAST_BOOTSTRAP_NOT_LIVE_ELIGIBLE` raised upstream.
- CP-7 never imports `apex.fabric/apex.pattern/apex.setup/apex.playbook/apex.forecast` internals; the SetupEvent row (frozen `setup_candidate` + `family_id`) is available in the store for display/ledger joins only.
- Ratchet state (Ch.15 / ADR-P2-004): CP-7's store must call `apex.risk.kernel.apply_ladder_state_migration(conn)` at schema init and `append_ladder_revision(...)` for state writes (table `apex_risk_ladder_state`, append-only — see DATA-CHANGES); the ladder is displayed/queried through it, never written elsewhere.

## DATA-CHANGES
- **New table** `apex_risk_ladder_state` (ADR-P2-004): single-row-per-revision, append-only (UPDATE/DELETE blocked by triggers), columns per `LADDER_STATE_DDL` in `apex/risk/kernel.py`. Delivered as migration id `M100_cp6_risk_ladder_state` with helper `apply_ladder_state_migration(conn)` that records into the frozen `schema_migrations` bookkeeping table. The frozen CP-1 `MIGRATIONS` list in `apex/data_catalog/store/sqlite_store.py` was NOT edited — the CP-7 store invokes the hook (see INTERFACES §4).
- **No other schema change.** `setup_candidate` rows are materialized by CP-6 code into the existing frozen Ch.4 DDL (the AD.1 `family_id` is the contract-level additive field, stored per Ch.4's payload JSON + as emitted by `to_setup_event()`); `evidence_event` untouched.
- `params/setup_weights_v1.yaml`: nine governed additive keys appended (listed in DELIVERED); every frozen value re-asserted unchanged by `tests/unit/test_cp1_foundations.py::TestParamsFrozenValues` (still green).
- New data files: `tests/fixtures/gf_sc_01.json`, `gf_sc_02.json` (repo, not DB).

## TESTS
(test file | ids covered | result) — 502 CP-6 cases, one row per component.

| test file | ids covered | result |
|---|---|---|
| `tests/unit/test_fabric_evidence.py` (43) | SL-14 lifecycle + crosswalk, expiry 5×TF, freshness decay, fabric admission/exclusions, 24-field event adaptation, identity rules | PASS(2026-09-13) 43/0 |
| `tests/unit/test_fabric_context.py` (63) | twelve weights + Q_min 0.55 from YAML, combiner law, bands/propagation, solvency, agreement, **vacuous-pass assert (fails on deliberately empty evidence)**, unscored-component regression, ContextRecord | PASS(2026-09-13) 63/0 |
| `tests/unit/test_pattern_detect.py` (50) | **GF_SC_01/02** fire (re-derived + hash-lock + negative control), catalogue governance/AC.1, 13 detectors, E08 delegation both ways | PASS(2026-09-13) 50/0 |
| `tests/unit/test_pattern_fibonacci.py` (19) | level law/retracements/extensions, OTE 0.62–0.79, 0.886 PRZ, golden identities, no-network seam | PASS(2026-09-13) 19/0 |
| `tests/unit/test_setup_gates.py` (29) | **13-gate matrix ±1 unit** (Gate 1 …13 each), Gate 11 integrity-only scope, run_all | PASS(2026-09-13) 29/0 |
| `tests/unit/test_setup_family_sf_fvg_sweep_rev.py` (92) | family contract + **140 cells**, entry-logic steps, relative-MTF (vacuous law), conflict/redundancy/score, SetupEvent into the frozen store DDL, Wave-Out second family | PASS(2026-09-13) 92/0 |
| `tests/unit/test_playbook_pb_fvg_sweep_rev_a.py` (42) | AE.1 16-field template, AE.2 lifecycle, **X.4 precedence (32 combinations)**, X.1/X.2/X.3 math, AE.5 literals, scale-out only | PASS(2026-09-13) 42/0 |
| `tests/unit/test_forecast_logistic.py` (41) | bootstrap p=0.5 exact, 12-feature vector, U/C both laws, composite + vacuous refusal, invalidation ×7, **T-DR-003 (unit part)**, **paper-only prior + LIVE refusal**, AG registry | PASS(2026-09-13) 41/0 |
| `tests/unit/test_decision_pipeline.py` (34) | EU units-of-R, eligibility 8-conj., monotone-before-rank, tie-breakers, cap 3, AF.3/AF.4 incl. NO-TRADE, proposal guard, **seam: arbitration never imports execution** | PASS(2026-09-13) 34/0 |
| `tests/unit/test_risk_kernel.py` (76) | **T_VETO ×14** (per-veto boundary each), **14-before-sizing order**, sizing machine (100/50/25/30/15/8/12/7/3/60/40/20 + guards), §9.5 **FROZEN_BOOTSTRAP literals from YAMLs**, CVaR advisory, margin bands, breakers, **RSK-ERR-506 ratchet + ladder-table immutability (sync + aiosqlite)**, authority seam | PASS(2026-09-13) 76/0 |
| `tests/integration/test_context_to_trade_paper.py` (13) | **PAPER end-to-end chain** (engine evidence→sized plan) + ALLOW→REJECT veto flip + stub seam authority; **T-DR-001/002/003** byte-identical replay of the whole CP-6 stack | PASS(2026-09-13) 13/0 |
| full suite | `bash scripts/run_all_tests.sh` | **1550 passed / 0 failed** (2026-09-13) |

## DEVIATIONS
- `ADR-P2-003 applied:` additive `__init__.py` per new package, `tests/**`, `tests/fixtures/gf_sc_0{1,2}.json`, and the CP-6 governed keys appended to `params/setup_weights_v1.yaml` — each listed above; no tree file renamed, none invented outside this rule.
- `ADR-P2-004 applied:` `apex_risk_ladder_state` + M100 migration hook in `apex/risk/kernel.py` (frozen MIGRATIONS list untouched).
- `ADR-P2-007 applied:` GF_SC_01/02 expected values and hashes re-derived from formulas/E08 at build time and re-verified at test time; no document value copied as truth.
- `ADR-P2-014 applied:` GF_SC_01/02 fully behavioral, GF_SC_03..12 schema-only assertions in `tests/unit/test_pattern_detect.py` (no invented bars).
- No other deviations — silent deviation is a breach (G4). The `setup_score` fix is a stage-owned defect repair (see DELIVERED), not a deviation.

## OPEN-ISSUES
Format per PROTOCOL P13; full text mirrored to `PHASE2_DECISION_LOG.md §B/CP-6` (all four severity/status dispositions there):
- `[ISSUE-CP6-001]` severity: MINOR | status: CLOSED | §8.1 prose "redundancy_penalty 0.25" vs Ch.10 §10.1 Gate 4 `> 0.3` + frozen YAML 0.3 → YAML wins (params authority); 0.25 documented, never used.
- `[ISSUE-CP6-002]` severity: MAJOR | status: CLOSED | stage-mandate decay 0.05/0.02 + bands 0.70/0.50/0.30 absent from Ch.8 (blueprint: propagation 0.70/0.40, λ=0.1 laws) → prompt numbers implemented as governed YAML freshness factors + classification bands; blueprint tables kept normative. Owner: confirm/retire at CP-8 triage.
- `[ISSUE-CP6-003]` severity: MINOR | status: CLOSED | AE.5 instantiated playbook (BE 1.0R / trail 1.5R / 1.0×ATR / max_hold 16) vs generic X.1–X.3 tables → specific instantiation applies; generic table = `fallback_source` metadata only.
- `[ISSUE-CP6-004]` severity: MINOR | status: CLOSED | Ch.15 vetoes 10–12 cite `CIRCUIT_OPEN (Alert Policy)`, absent from the frozen Ch.7 registry → rows carry `error_code=None`; CP-7 alert rows key off `fired_numbers`; registry extension is an owner decision (CP-8 triage).

## HOW-TO-RUN
```bash
cd /home/user/Upstage                      # repo root
python3 -m venv .venv                     # skip if present
.venv/bin/pip install -r requirements.lock   # the nine runtime pins
.venv/bin/pip install "pytest>=7,<9"         # dev-only (ADR-P2-002)
bash scripts/run_all_tests.sh                # full suite: 1550 passed / 0 failed
```
This increment's batteries and demo entry (the integration test IS the runnable end-to-end demo of the PAPER chain — it drives engine evidence to a sized plan and asserts every hop):
```bash
.venv/bin/python -m pytest tests/integration/test_context_to_trade_paper.py -q   # 13 passed
.venv/bin/python -m pytest tests/unit/test_setup_gates.py tests/unit/test_risk_kernel.py -q  # gates + T_VETO/RSK-ERR-506
```
CP-7 consumption (no CP-6 internals needed — these are the only three surfaces):
```python
from apex.decision.pipeline import StrategyProposal, build_proposal   # proposal shape
from apex.risk.kernel import adjudicate, evaluate_vetoes              # trade plan + veto result
from apex.risk.kernel import apply_ladder_state_migration, append_ladder_revision
```

## REMAINING WORK LEDGER
none — stage fully closed. (All EXIT boxes checked on the board; MATRIX Parts I/II/III CP-6 rows filled; four `[ISSUE-CP6-*]` mirrored; PR #7 carries `6e27169..HEAD` for the owner's plain merge into main.)
