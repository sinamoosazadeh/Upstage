# APEX_GEN5 — PHASE 2 CHECKPOINT DEFINITIONS (binding contracts for every slot)

One section per checkpoint. An agent reads ITS OWN section (plus predecessor handoffs). "Read set" = what you must read (and the maximum you may read, per PROTOCOL P15). "Write set" = the only paths you may create/modify, plus listed extension points. "Exit gate" = the boxes you check in `PHASE2_CHECKPOINT_STATUS.md`; all must be true before STATUS=COMPLETE.

Conventions: line ranges in `APEX_GEN5.md` are navigation aids; heading text is canonical. `tests/unit/<file>.py` and `tests/integration/<file>.py` file names within a slot are your choice, following `test_<area>_*.py`; every file you create goes in your DELIVERED table. Fixture files go under `tests/fixtures/` prefixed by their owner (`gf_sc_*.json` belongs to AGENT-06; engine fixtures are `e0N_FIX_*.json`).

---

## CP-1 — AGENT-01 — Foundation: identity, contracts, storage, quality, config

Entry: CP-0 checked by owner; repo contains the 3 frozen blueprint inputs (`APEX_GEN5.md`, `PROMPT.md`, `AI_SUGGESTION_PLAN.md`) + all 24 `PHASE2_*` control files.

READ SET (complete, then nothing else except targeted greps):
- `PHASE2_PROTOCOL.md`, this section, `PHASE2_DECISION_LOG.md`
- `APEX_GEN5.md` lines 1–1197 (preamble, Ch.1 all, Ch.2 all)
- lines 4104–4158 (GLOBAL IDENTITY / PIT UTILITY CONTRACT v1.0.0)
- lines 14383–14671 (Ch.4 Data Plane, Ch.5 Trading Universe, Ch.6 pointer, Ch.7 Error Codes)
- lines 18221–18314 (Ch.23 — for config/deployment context only)
- lines 18364–18539 (AI.2 engine contract table, AI.3 canonical time/identity/replay, AI.4 lifecycle)
- lines 18540–18678 (AI.5 Raw Store, AI.6 Missing-Data/OI policy)
- lines 18747–18812 (AI.8 idempotency/replay/rate-limit)
- lines 20128–20247 (§9.5 Execution-team directives — tree, params YAML specs, env names, Wave-Out, FROZEN_BOOTSTRAP)
- `requirements` facts: Ch.1 SBOM lines 97–160.

WRITE SET (exact normative tree files; create every file; do not rename; additive only where listed):
- `pyproject.toml`, `requirements.lock`, `README.md`, `.gitignore` (ADR-P2-013)
- `apex/__init__.py`, `apex/errors.py`, `apex/bus.py`, `apex/config.py`
- `apex/identity/{__init__.py,canonical_json.py,uuid_v7.py,snapshot.py,hashes.py}`
- `apex/data_catalog/{__init__.py,contracts.py,catalog.py}`; `apex/data_catalog/store/{__init__.py,sqlite_store.py}`; `apex/data_catalog/ingest/{__init__.py,toobit_public.py}`
- `apex/quality/{__init__.py,vector.py,numerical.py,pit.py}`
- `params/{universe_v1,risk_defaults_v1,setup_weights_v1,quality_weights_v1,toobit_wire_v1,e11_params_v4}.yaml` — values copied verbatim from §9.5 and Ch.5/Ch.10 frozen numbers ("do not re-interpolate")
- `tests/unit/…` foundation suites; `tests/integration/test_cp1_foundations.py`
- Control files: your sections in HANDOFF_CP1 / TRACEABILITY / STATUS / DECISION_LOG.

SCOPE (what "done" means — everything listed here is YOURS; nothing unlisted):
1. Canonical identity stack exactly per GLOBAL IDENTITY/PIT contract + AI.3: `canonical_json` (sorted keys, separators, Decimal-as-quantized-string encoder, `...Z` datetimes, NaN/Inf forbidden — raise, never sanitize), `uuid_v7` (RFC 9562 in-tree, the repo's ONLY UUIDv7), `canonical_snapshot_id(engine, contract_version, payload)` = SHA-256 over `{"engine","contract_version","payload"}`, `governed_as_of_ms(required_artifacts)` (max availability_time; missing → ValueError `MISSING_AVAILABILITY_TIME_QX`), `hashes.py` for payload/source hashing.
2. `apex/errors.py`: the full Ch.7 error-code registry as machine-checkable constants + the WaveIn/WaveOut discipline helpers (`WaveOutError`), deterministic reason codes; every Ch.7 row present.
3. `apex/config.py`: env parsing per §9.5-12 names ONLY (stdlib .env parser, no python-dotenv), secrets policy enforcement (§2.5: secrets never logged/persisted — provide redaction helper used by all layers), `.env` discovery, APEX_ENV ∈ {PAPER,LIVE,RESEARCH,BACKTEST}, no SHADOW keyword accepted anywhere.
4. `apex/bus.py`: in-process asyncio.Queue bus — bounded queues, P0 synchronous semantics per AI.8/AI.12 (P0 = synchronous), ordering preserved, no event loss on graceful stop; priority honored.
5. Data catalog per Ch.4+Ch.5: `contracts.py` (typed contracts for Observation/QualityVector/Snapshot/MarketTick etc. matching the DDL fields exactly), `catalog.py` (`catalog.get(feature_id, symbol, timeframe, as_of, lookback=1)`; unknown feature_id → INVALID; future as_of → INVALID; statuses OK/MISSING/STALE/UNAVAILABLE/INVALID; engines never SQL the store; registration API for AGENT-02 with frozen id template `APEX.Lxx.TIER.NAME.UNIT.Vn`), `sqlite_store.py` (WAL/PRAGMAs per Ch.5, all Ch.4 tables DDL verbatim incl. CHECK constraints and indices; migrations ledger table of your design logged in DECISION_LOG per ADR-P2-004 — additive), `toobit_public.py` (public endpoints per Ch.16 wire: time, exchangeInfo, klines limit 1000, depth, openInterest, fundingRate alert-only; −1120 per-symbol-TF disable rule; retries with token bucket + exponential backoff per AI.8; OI fail → MISSING never 0; `bootstrap_progress` phases P1–P3 cursor logic per Ch.5 DDL).
6. Quality per Ch.2 §2.1: seven hard components (Q_schema, Q_time, Q_seq, Q_ohlc, Q_volume, Q_oi, Q_source), Q_raw formula, Q_min(tf) table (bootstrap, SL-12 governed — read-only copy), four independent vetoes, derived measures, dynamic re-evaluation, state machine, failure modes exactly as tabulated; `numerical.py` per §2.2 (two-tier epsilon, rounding/quantization, Decimal everywhere, division guards, signed-zero rule E-NUM-003); `pit.py` per §2.3 (as_of, observation windows per consumer incl. MTF alignment states, multi-symbol scope, snapshot binding, parameter table).
7. Cross-cutting enforcement: the build-breaking lint rule "no direct `get_ohlcv` outside `apex/data_catalog`" as a test that greps the repo (it must pass trivially now, and will guard every later wave).
8. README run skeleton: environment init (Termux), `pip install -r requirements.lock`, test command, `.env` example (names only, no values), status "CP-1 of 7". Final run procedure completed by AGENT-08.
9. SBOM integrity: `requirements.lock` contains exactly the nine pins from Ch.1; `pyproject.toml` declares package `apex`, python `>=3.10`, dev extra for pytest (ADR-P2-002); no other runtime dependency (no Numba, no pandas misuse beyond pins).

MANDATORY TESTS (all green before push): T-DC-001..004; T-PIT-001..004; T-ID-001..002; T-CL-001..003 (correction lifecycle at store level: CLOSED immutable, CORRECTION_EVENT + SUPERSEDED, cascade hook point); T-OM-001..003; T-RS-001..003 (retention window mechanics per AI.5, implemented as governed purge query); plus: uuid_v7 format/timestamp monotonicity; canonical_json determinism incl. Decimal quantization and NaN rejection; Q_raw/Q_min table equality vs blueprint values; config refuses SHADOW; lint-guard test.

EXIT GATE (boxes in STATUS file):
[ ] All WRITE SET files exist, non-empty, and import cleanly (`python -c "import ..."` chain test included in integration suite)
[ ] Every Ch.4/Ch.5 DDL statement appears verbatim-equivalent in store migrations (traceability rows prove it)
[ ] All §9.5 params YAML files carry frozen values; a test asserts the risk numbers against §9.5-11 (budget_per_trade 0.005 etc.)
[ ] All mandatory T-ids implemented and passing; test log in handoff
[ ] Traceability matrix CP-1 section filled (no TODOs)
[ ] Handoff CP-1 written ≤400 lines with all mandatory headings
[ ] Commits per P14; pushed; no ownership violations in `git log` diff

DO NOT: engines, features, fabric, pattern, setup, decision, risk, execution, telegram, research (each is a later checkpoint; your interfaces must not pre-implement them). Do not add an `apex/engines/base.py` (AGENT-02 owns it).

---

## CP-2 — AGENT-02 — Feature Fabric: 74-feature candle intelligence + engine base contract

Entry: CP-1 exit boxes checked; read `PHASE2_HANDOFF_CP1.md` §INTERFACES (your only view of CP-1 code).

READ SET:
- PROTOCOL, this section, DECISION_LOG, HANDOFF_CP1
- `APEX_GEN5.md` 13529–14382 (§3.12 all 74 entries + §3.13), 14638–14642 (Ch.6), 14371–14382, Ch.2 §2.2 reread only where features cite EPS (targeted)
- 18470–18539 (AI.4 unified validation/lifecycle — you implement its feature-tier half), 4104–4158 (identity contract — import, never reimplement)
- 20156–20213 (tree), 9.5 directive 4/5/10 reread.

WRITE SET:
- Feature tier modules under `apex/data_catalog/` per §3.12 "Module layout" (ADR-P2-006): `apex/data_catalog/atomic/`, `molecular/`, `organismic/`, `math/`, `performance/` packages + `__init__.py` each; registration wired through `apex/data_catalog/catalog.py` ONLY via its public registration API (extension point from CP-1; if the API is insufficient, record DECISION_LOG and extend minimally)
- `apex/engines/{__init__.py,base.py}` — the frozen engine base contract
- `tests/unit/test_features_*.py`, `tests/integration/test_cp2_feature_fabric.py`
- Control files: your sections.

SCOPE:
1. All 74 features, each with the full entry template: ID, alias, formulas (as documented), numeric example, Decimal code path, validity window, `exp(-0.02*age)` decay where declared, consumers, quality contribution, lineage. Tiering rules: ATOM never cached; MOLECULAR cached 5 candles; ORGANISMIC cached 50+ with LRU-100; fixed recomputation schedule (ATOM per candle, MOLECULAR per 5, ORGANISMIC on demand); unidirectional flow; a guard that ATOM failure stops the pipeline (no silent continue).
2. §3.13 closure contract as tests: registry count == 74 == catalogue count; no engine may reference an unregistered id (implement the enforcement hook in catalog for later waves); feature 49 funding_rate remains REMOVED/OUT-OF-CONTRACT (any reference = build failure test); feature 56 market_profile always UNAVAILABLE (Wave-Out honored); features 57–61/68–71 temporal ids exposed for E12 consumption per §3.12.
3. Universal guards: `H<L` → QX INVALID; `H-L<ε` → DEGRADED; `is_closed=false` → CANDIDATE (never final); QX never zero-substituted.
4. `apex/engines/base.py` — the contract every engine agent will implement (this is THE freeze artifact of CP-2; keep it formula-free): engine lifecycle (warmup → streaming `on_closed_bar(bar|batch, as_of, snapshot)` → idempotent re-apply; superseded/correction cascade hook per AI.4; `snapshot_id` via CP-1 identity; evidence-event emission producing the 24-field `evidence_event` row shape of Ch.4 (engine_id enum, price_level TEXT Decimal, quality/validity, lineage, until, raw, authority, authority_scope, event_type, strength, confidence, regime, utc_activity_window_id, snapshot_id, payload_hash/source_hash, epsilon, atr, volume, oi)); quality-tag attach point (Q0–QX per engine §1.5); versioned interface registry helper (`I_Structure_v4` style labels + consumer fallback-with-Q2-downgrade plumbing, per E06 §1.5 generalization and AI.2 adapter column); a `WaveOutError` gate helper reused by all engines.
5. Feature→consumer matrix table generated as a test artifact (74 features × declared consumers) into your handoff INTERFACES section.

MANDATORY TESTS: T-DR-001 (feature tier: byte-identical recompute over fixture candles — construct candles, no future leak; per AI.10 acceptance), T-MON-001 (quality never improves with fewer inputs), registry-completeness suite (§3.13), serialization compatibility (canonical_json round-trip of every feature payload type), decay-window numeric checks against §3.12 examples (re-derive the BTC 100/105/110/98 example for each feature class, per P8 — recompute, never copy illustrative results), cache-policy tests (ATOM no cache, MOL 5, ORG 50+/LRU-100), catalog.get status matrix tests.

EXIT GATE:
[ ] 74/74 registered, template-complete; enforcement hook active
[ ] base.py frozen: publish its full API in handoff (engine agents build only against that text + AI.2, per P19)
[ ] mandatory T-ids green; handoff ≤400 lines; traceability CP-2 filled; pushed per P14

DO NOT: implement any engine formula (E01–E12 are CP-3), any fabric/pattern/setup (CP-4).

---

## CP-3 — AGENTS 03/04/05 — Twelve Analysts (three serial slots)

Shared entry: CP-2 checked. A03 reads HANDOFF_CP2. A04 reads HANDOFF_CP2 + HANDOFF_CP3 §[AGENT-03]. A05 reads HANDOFF_CP2 + HANDOFF_CP3 §[AGENT-03] + §[AGENT-04] (E11 consumes E02–E04 evidence; already-pushed modules may also be inspected at signature level per P15). (Parallel execution is permitted only if the owner accepts cross-slot integration risk; interfaces are frozen well enough for it — but serial is the recommendation of this plan.)

Shared READ SET skeleton: PROTOCOL, this section, DECISION_LOG, HANDOFF_CP2 (+predecessor slot section), your engines' full blocks (ranges below), AI.2 (your engines' rows), AI.11 (your engines' rows), Ch.2 §2.1/§2.2 targeted (quality tags + epsilon), §9.5 directives 2,3,4,9,10, AI.4 (lifecycle for emitted objects).
Shared WRITE SET: `apex/engines/<eXX_dir>/{__init__.py,engine.py}` + engine-local extra modules ONLY if that engine's §4 pseudocode architecture requires them (named after engine sections; logged in handoff) + `tests/unit/test_eXX_*.py` + `tests/fixtures/eXX_FIX_*.json` + control sections.
Shared SCOPE per engine (never generalize across engines — each §5 schema is canonical):
- Implement §1 mission/boundary (no goals beyond it), §2 vocabulary, §3 formulas EXACTLY incl. corrected/edge-case notes, §4 reference algorithm (it is normative pseudocode — port to production Python: Decimal per §2.2, streaming, idempotent, O-annotations honored), §5 objects/FSM/events/JSON schema/snapshot_id/versioning (emit via CP-2 base), §6 parameters (governed; wire into `params/` values where §9.5 pins them), §7 encyclopedia = documentation only (no code; E08 ch.2–4 Wave-Out honored), §8 validation suite fully implemented (golden fixtures constructed from the §8.1 sample shapes with real re-derived numbers; deterministic replay; no-future-leak; ablation; Wilson-CI calibration harness reading a data path parameter (no fabricated stats — UNVERIFIED flag until data exists; harness itself is production); redundancy threshold numeric test; serialization compatibility), §9 case study as an EXAMPLE test only where the document itself declares the numbers reproducible — re-derive, never paste; §10 references (cite in module docstrings).
- Cross-engine: consume sibling evidence ONLY via the versioned interface registry + AI.2 table + each producer's §5 schema; implement the specified degradation branch (e.g., E06: structure missing/below-4.0 → `structural_event=None`, Q2; I_Volume_v4/I_Volatility_v4 aligned-evidence rules per PHASE 80/82 records — internal SMA/ATR recomputation is test-only forbidden).
- Wave-Out internal to engines: E11 next-regime forecast (raise WaveOutError at the hook); dynamic Williams k in E01 (k=2 fixed, GC-D12); live OFI/VPIN in E02 (proxies per §3.8 with the stated non-live constraint — implement formulas over OHLCV-derivable inputs exactly as the frozen chapter defines, mark live-depth paths UNAVAILABLE); E04 adaptive ATR (deferred; raise at hook); `market_profile` feature in E03 stays UNAVAILABLE; GF_SC_03..12 schema-only assertions where referenced.
Slot-specific anchors:
- AGENT-03: E01 1205–2789; E02 2790–3871; E03 3872–4954 (skip the 4104–4158 contract — CP-1 owns it; E03 §4 imports it); E04 4955–5601. Watch: E01 BreakMag absolute-value rule, 0.15×ATR HTF tolerance, pruning by depth/age, CHoCH four conditions; E02 Merton jump-diffusion hit probability, DBSCAN O(n log n) with epsilon=θ_eq·ATR, equal-level chain-prevention; E03 as_of governed-max + availability_time_ms fail-closed (Phase 67 items), volume_sma exposed in ParticipationEvidence (Phase 80); E04 ε=1e-12 per R.8/GC-D4, no adaptive ATR.
- AGENT-04: E05 5602–6859 (min_width 0.2 frozen, CP-E05-001 not applied); E06 6860–8292 (0.55 frozen, not 0.65/0.68; body-vs-range per frozen definition; I_Volume/I_Volatility evidence rules PHASE 80/81/82); E07 8293–9085 (streaming + E12-window permission; breaker/RTM definitions exact); E08 9086–9466 (chapter-1 logic only; ch.2–4 non-blocking reference; GF_SC_01/02 SHAPE comes from Ch.9 15019–15021 — fixture files themselves are AGENT-06's, you only assert schema compatibility in your tests).
- AGENT-05: E09 9467–10275 (no E11 coupling beyond published projections); E10 10276–11670 (four divergence kinds + CONVERGENCE + NONE in fixtures); E11 11671–12732 (**K=9 classes, d=8 input features — never conflate (T-E11-K9); params from `params/e11_params_v4.yaml`; research-only live-gate flag per AI.12/owner approval is a runtime CONFIG gate, implemented but default-off; no next-regime forecast**); E12 12733–13528 (UTC windows UTC_W0..W3 + derived cores + OVERLAP flag + orthogonal ROLLOVER per AI.2 canonicalization rule 1–5; DST-ignore decree; window registry versioned).
MANDATORY TESTS: every engine's §8 battery; T-E01-001 (A03); T-E11-K9 (A05); T-E12-Windows (A05); T-DR-001 extension per engine (byte-identical replay); no-future-leak per engine (availability discipline); plus a CP-3 integration smoke (each engine consumes its required upstream v4 interfaces from pushed siblings or documented contract).
EXIT GATE (per slot): engines assigned to you: code + schema + params wiring + fixture files + §8 battery green; handoff slot ≤400 lines with per-engine rows; traceability CP-3 rows; Wave-Out grep (no forbidden keywords implemented: withdraw/transfer/flashClose/hedge/CROSS/SHADOW/Numba in your scope); pushed.

---

## CP-4 — AGENT-06 — Evidence fabric, pattern, setup, playbook, arbitration (the context chain)

Entry: CP-3 all slots checked. Read HANDOFF_CP3 (interfaces rows) + HANDOFF_CP2 §base.py.

READ SET: PROTOCOL, this section, DECISION_LOG, HANDOFF_CP2/CP3, `APEX_GEN5.md` 14672–15971 (Ch.8, 9, 10, 11, 12 fully), AI.4 reread, Ch.2 §2.3 reread for window consumption, §9.5 (setup weights note), AI.11 (consumers rows), Ch.16 §16.1 top half only for what Setup must expose to Risk (targeted 16750–16790).

WRITE SET: `apex/fabric/{__init__.py,evidence.py,context.py,conflict.py}`; `apex/pattern/{__init__.py,detect.py,fibonacci.py}`; `apex/setup/{__init__.py,family_sf_fvg_sweep_rev.py,gates.py}`; `apex/playbook/{__init__.py,pb_fvg_sweep_rev_a.py}`; `tests/fixtures/gf_sc_01.json`, `gf_sc_02.json`; `tests/unit/test_{fabric,pattern,setup,playbook,arbitration}_*.py`; `tests/integration/test_cp4_context_chain.py`; control sections.

SCOPE:
1. Evidence Fabric per Ch.8 §8.0: fabric assembly per (symbol, TF, as_of), lifecycle state machine SL-14 (CANDIDATE→CONFIRMED→ACTIVE→{MITIGATED, INVALIDATED, EXPIRED, SUPERSEDED}), engine-lifecycle crosswalk per E03 §5 (created/emitted/consumed/expired 5×TF/superseded mapping), read-only rule for engines (fabric mutation is impossible by construction), full lineage down to `observation_id`.
2. Context Fabric + `context_confidence` bounded combiner exactly (7 terms, default weights .35/.20/.15/.15/.10/.05 normalized to sum 1 via SL-12 governed table; solvency rule: data_trust<0.30 or Q_raw<Q_min ⇒ context_confidence=0 with FULL evidence removal, never zero-substitute); propagation thresholds 0.70/0.40 exactly (blocking/confirmatory-only/excluded).
3. Conflict policy per §8.1: ConflictRecord schema; exactly four structured outputs; safe monotonicity (permission-monotone downward); seven invariants as enforced assertions (PIT, monotonic quality, fail-closed, veto autonomy reference, ledger immutability reference, idempotency, capital ceiling reference); MTF alignment states per §8.3 (relative rule of Ch.10); inter-symbol layer per §8.2 (portfolio constraint, never a directional signal).
4. Pattern Intelligence per Ch.9: hierarchy, detector catalogue (legacy 20 rows locked), firing rules with tolerances, AC.1–AC.5 extension governance (schema-level; extension entries research-only; admission gates implemented as registry validation); `fibonacci.py` is an in-repo computation (directive 15 — no network service); GF_SC_01/02 constructed per 15019–15021 (synthetic bar arrays you construct; hash computed after construction per no-hash rule).
5. Setup Engine per Ch.10: 13 hard gates exactly (incl. Gate 11 = lineage/snapshot integrity ONLY, not "any of the 13"; Gate 7 `H/ln(9)>0.85` distinct from E11 θ_H); frozen bootstrap weights (sum=1, listed in §9.5 params — assert loaded values match; Q_min_setup=0.55); conflict/redundancy numerics (×0.6 required-conflict multiplier on raw; Pearson |ρ|>0.85 drop-lower-Q, tie→higher engine id, <20 OK-points skip); relative-MTF selection algorithm per the chapter's index rules incl. vacuous-pass rule and "no coarser bar → cell does not emit"; family registry AD.2 + evolution AD.3 + AD.8 `SF_FVG_SWEEP_REV` (the only Wave-In family, all 140 cells); setup_candidate row persistence per Ch.4 DDL.
6. Playbook per Ch.11 §AE + X.1–X.4/X.5: PB_FVG_SWEEP_REV_A instantiated (universal); 16-field template exact; BE/trailing/time-stop management semantics with exit precedence; X.6 parameter catalog wired as governed ranges (X.7 owner-static: never optimized — encode as non-injectable); X.8 owner-absence two-step gating (implemented as state; nothing auto-escalates).
7. Arbitration per Ch.12 §AF: gatekeeper semantics (regime-window hard boundary, never a score decrement), advisory composite ranking, NO-TRADE first-class output, StrategyProposal contract unchanged; it never issues orders/capital.
MANDATORY TESTS: T-DR-002 (50 historical setups re-run: same gates fire — fixture-driven synthetic history acceptable), gates 1–13 boundary matrix (each gate independently triggers QUARANTINED BLOCK), monotonicity anti-pattern test (extra disagreement never grants permission), context thresholds table test, GF_SC_01/02 pattern-fire tests, MTF rule incl. vacuous pass on 1mo cell, playbook exit-precedence tests (BE→trail→time under X.4), family registry governance tests, serialization compatibility for setup_candidate/pattern rows.
EXIT GATE: chain E01–E12 evidence → fabric → pattern → setup(gates) → playbook → arbitration runs end-to-end in a synthetic test with NO decision/risk imports; handoff lists every public API CP-5 will consume (setup candidate object, conflict state, context_confidence, regime-window gate input, playbook interface); traceability filled; pushed.

---

## CP-5 — AGENT-07 — Forecast → Decision → Risk → Execution → Ledger → Scheduler (safety core)

Entry: CP-4 checked; read HANDOFF_CP4 + HANDOFF_CP1 (store/ledger/bus) + HANDOFF_CP3 rows for consumed engine fields.

READ SET: PROTOCOL, this section, DECISION_LOG, HANDOFF_CP1/CP4(+CP3 targeted), `APEX_GEN5.md` 15972–16517 (Ch.13+AG), 16518–16936 (Ch.14, 15, 16), 17357–17445 (Ch.19 Y.1–Y.4), Ch.1 targeted reread: 253–297 (FSM narrative→canonical mapping), 337–355 (quality gates), 400–417 (risk ladder), AI.7 (queues), AI.8, AI.9 (fallback — implement its runtime half), AI.11 rows, §9.5-11/-14, Ch.7 rows for E-EXEC/E-PIT.

WRITE SET: `apex/forecast/{__init__.py,logistic.py}`; `apex/decision/{__init__.py,pipeline.py}`; `apex/risk/{__init__.py,kernel.py}`; `apex/execution/{__init__.py,fsm.py,toobit_adapter.py,toobit_map.py}`; `apex/ledger/{__init__.py,store.py}`; `apex/scheduler/{__init__.py,clock.py}`; store migration additions: `trade_plan` DDL verbatim (Ch.16), `outcome` per Ch.4, emergency-ladder state table (ADR-P2-004); tests incl. `tests/integration/test_cp5_runtime_chain.py`, `tests/integration/test_cp5_fail_closed.py`; control sections.

SCOPE:
1. Forecast per Ch.13: event definition exact; bootstrap P (β=β0=0 ⇒ p_raw=0.5, Q_forecast=0.5) eligible PAPER/RESEARCH only — LIVE gated via Setup Gates 10/12 (implement the gate check, not a workaround); x-vector (12 terms) assembled from pushed engine outputs; p_hat Platt/isotonic interface (calibration on OOS packages, never on the decision bar); U/C separation formulas; statistical paths (conditional frequency, Bayesian (wins+α)/(wins+losses+α+β), regime base rates, Kaplan–Meier research-only Q6, optional AI-ensemble contract with the seven metadata fields and future-independent weights); AG model bindings where q_i enter setup scoring per AG.5 (register, don't re-derive).
2. Decision per Ch.14: EU unit arithmetic exactly (R-multiples, G=RR·R, L=R, C=fee+half_spread+slippage_model with slippage_model=α_spread·|size/ADV|, R_penalty scale), eligibility conjunction exact (incl. P≥P_min(tf), C≥C_min, data_trust≥0.30, Q_raw≥Q_min(tf), conflict≠HARD_CONFLICT), ranking/tie-breakers EXACT (`-EU,-P,-C,U_sum,RR`), max_candidates=3 (FROZEN), INSUFFICIENT_EVIDENCE behavior; Portfolio Proposal schema; monotonicity check `monotone_ok` (SL-2).
3. Risk per Ch.15: 14-veto Canonical Registry — registry is the single normative source, all fourteen evaluated independently, each REJECT is final for the turn; sizing machine lines-by-line (R_allowed ladder multipliers 1.0/1.0/0.75/0.50/0.0, k_attn cap, floor to min_quantity, Q==0 ⇒ REJECT PORTFOLIO_CAPACITY, StopDistance<=0 ⇒ deterministic reject, Capital<=0 ⇒ reject first); REDUCE correlation path (cap 0.70); ratchet semantics (upgrades only, RSK-ERR-506); circuit breakers 10–12 from ledger realized+unrealized, reset only time/OWNER; margin health 60/40/20 thresholds incl. auto-cancel-all at 20%; CVaR_95 advisory downgrade hook (computation lives in CP-6 research; you consume a versioned advisory input with the "never replaces a veto" constraint enforced); authority hierarchy tests (nothing below Risk may override; Owner changes caps but never vetoes).
4. Execution per Ch.16: FSM exactly the SL-6 list + RECOVERY_REQUIRED; nested-READY substate ARMED/TRIGGERED per Ch.1 mapping note; single-writer ledger queue; reconcile-first invariant (no downstream advance past divergence; RECONCILED only on ledger↔exchange agreement); idempotency key `SHA-256(intent_id||order_id||fill_id||cancel_id||timestamp_UTC||nonce)` pattern per chapter with governed TTL; order types/TIF/retry table; Toobit adapter contract (five operations, one endpoint each; state mapping incl. UNKNOWN→reconcile; error map; per-endpoint token bucket; timeout→RECOVERY_REQUIRED; `client_order_id`=`intent_id` UUIDv7); `toobit_map.py` = wire map exactly (BTC-SWAP-USDT…, 1mo→1M, −1120 per-cell disable, side maps, LIMIT IOC/STOP MARKET, forbidden list enforced by validation); `trade_plan` persistence; ledger table append-only + revision corrections; rollover policy; stop-gap handling (STOP_GAP_SLIPPAGE attribution, emergency close + OWNER escalation on PROTECTION_FAILED); startup reconcile sequence hook consumed by ops.
5. Ledger store per Ch.4 `ledger` DDL: hash-chained, immutable, corrections-as-revisions; event stream to bus (P0 priority for protective).
6. Economic Gate logic per Ch.19: Y.1 five-item checklist state machine (gates capital, never environment existence), Y.2 leverage min(exchange filter, Y.2 TF cap 2/3/4/5, owner cap) enforced at sizing boundary — "a 125x cell never authorizes 125x"; Y.3/Y.4 terminology register.
7. Scheduler per §9.5-14 + Ch.23 execution model: on each TF close, per (symbol,TF): ingest→quality→features→engines→setup→gates→risk→decision→execution; semaphore 4; HTF last-closed only; bounded pool; P0 synchronous; clock via NTP-drift check (drift>500ms ⇒ temporal DEGRADED + new entries blocked per E12 fallback); graceful shutdown preserves queues to store per retention rules.
8. Fallback per AI.9 runtime half: fail-closed modes, protective-order preservation on degrade, degradation never silent.
MANDATORY TESTS: T-DR-003; T_VETO (each of 14 boundaries allow/reject), T-VETO-SIZE (sizing machine incl. zero/negative guards), T-MON-002/T_MONOTONE (decision monotonicity), T-LR-001..003, T_MATCH, T_RECONCILE, T_LEDGER, T_ADAPTER_SUBMIT/DUPLICATE/LOST_ACK (against a local fake exchange responding per wire contract — the FAKE IS A TEST DOUBLE, not production behavior: production adapter is real HTTP via aiohttp), E-EXEC-001 fill-timeout test, leverage min() table test across 4 TF groups, FSM illegal-transition matrix (no skipping), scheduler ordering + semaphore test, gate-11 lineage corruption blocks, env SHADOW rejection end-to-end.
EXIT GATE: `python -m apex.scheduler.clock`-equivalent boots the full loop in PAPER with a fixture clock and synthetic market (no Telegram required yet — bus events observable); all above green; handoff lists every consumer-facing API for CP-6; pushed.

---

## CP-6a — AGENT-08 — Control plane & operations: Telegram, watchdog, backup, deployment, README completion

Entry: CP-5 checked; read HANDOFF_CP5 (§INTERFACES) + HANDOFF_CP1 config/bus.

READ SET: PROTOCOL, this section, DECISION_LOG, HANDOFF_CP1/CP5 (+CP4 targeted for context fields), `APEX_GEN5.md` 17562–18086 (Ch.21 full), 18221–18314 (Ch.23 full reread incl. Monitoring and Alert Policy), Ch.1 282–337 (wizard + ladder), §2.5+§2.6 (1135–1197), AI.9 reread, AI.13 rows G-RESTORE/G-PAPER (harness ownership), Ch.7 E-TELE rows.

WRITE SET: `apex/telegram/{__init__.py,control_plane.py,signaling.py}`; `apex/ops/{__init__.py,watchdog.py,backup.py}`; `scripts/deploy_termux.sh`, `scripts/restore_drill.sh`, `scripts/nfr_harness.py` (additive, logged ADR-P2-005); `README.md` final run section (extension point granted by CP-1 handoff); `tests/unit/test_telegram_*.py`, `tests/unit/test_ops_*.py`, `tests/integration/test_cp6a_control_plane.py`; control sections.

SCOPE:
1. Telegram Control Plane per Ch.13 of the chapter (full 15 sections): screens & menu (main, 4-step trading wizard, 5-step portfolio export, Lab, Info, Settings×5, Emergency L1–L5 OWNER-only, Help×6) exactly as tabulated; callback table; busy-guard state machine (IDLE→BUSY→IDLE, E-VAL-020 + Stop button); roles OWNER/USER only, no ADMIN, auditable denials; confirmation & guardrails incl. APEX_ALLOW_SIGNED flows.
2. Signaling per Ch.12/§9.5 signaling P0–P3: message composition from ledger/risk/decision events, idempotency key SHA-256(signal_id+timestamp_UTC+chat_id) TTL 24h (E-TELE-007), rate discipline (internal 20/s < provider 30/s, token bucket per E-TELE-006 with 3-retry 1/2/4s), text ≤4096, caption ≤1024, keyboards ≤8×4 (E-TELE-003/004/005), aiogram 3.7.0, charts per §18060 (Agg, in-memory PNG 1200×800 q90, send_photo, Agg failover), 24-field evidence display contract, Telegram NEVER blocks protective execution (transport failure is logged-degraded, P0 alerts durable outbox, no silent drop).
3. Watchdog per Ch.23 + Monitoring table: 60s signed heartbeat; 3 missed → HOST_DOWN independent channel + reduce-only/cancel-all with restricted key (adapter operations only — withdraw/transfer forbidden at code level); primary: 3 unreachable watchdog intervals → DEGRADED + new entries blocked; independent send-only Gmail module (SMTP app password) living ONLY in the watchdog process with zero access to trading path/keys/ledger; alert table thresholds verbatim (FEED_DEGRADED 2×freshness; EXEC_RECOVERY any → immediate OWNER; CIRCUIT_OPEN per vetoes 10–12; STORAGE >80%; 30-min dedup except EXEC_RECOVERY/CIRCUIT_OPEN); every alert carries timestamp/metric/threshold/observed/snapshot_id and appends to the immutable audit trail; `termux-battery-status` signal consumption (merged R.9 item).
4. Backup/restore per §2.6 + Ch.23: hourly + on every FSM state transition, encrypted, hash-verified; restore procedure script + drill harness (G-RESTORE-001 / T-RESTORE-001 executable in PAPER on-device); plaintext key dump forbidden (code path absent).
5. Startup reconciliation sequence (Ch.23) wired to ledger/exchange adapter from CP-5; SELF_TEST checks deps/schema/clock/ladder-state; DEGRADED semantics.
6. README finalization: one clear run procedure — Termux init (pkg install python rust-bin? — NO: exactly the SBOM; document `proot-distro`-free Termux setup per pins), env file names, `pip install -r requirements.lock`, run command, verify-healthy steps; document the six external measurement gates as OWNER procedures (not code claims).
MANDATORY TESTS: T-FB-001..003 (fail-closed entry, protective preservation, startup reconciliation on 5 scenarios), T-NFR-004 (queue priorities: 2000 P0 + 1000 P2 → P2 eviction, no P0 loss), E-TELE-* boundary suite, idempotency replay test, busy-guard concurrency test (aiogram handler mocked transport), watchdog heartbeat-loss simulation (clock injection), backup hash-chain verify + restore drill in tempdir, alert-dedup window test, chart-render Agg headless test (no display available in CI = the Agg failover assertion).
EXIT GATE: bot connects against a mocked transport in tests and a documented manual smoke procedure exists for the owner; watchdog runs standalone process entrypoint; backup/restore drill green locally; README run procedure copy-pasteable; pushed.

---

## CP-6b — AGENT-09 — Research plane & governance: parameters, optimizer, bootstrap, promotion, proxies, adapters

Entry: CP-5 checked (CP-6a may run in any order relative to you; you do NOT depend on Telegram code).

READ SET: PROTOCOL, this section, DECISION_LOG, HANDOFF_CP5 + HANDOFF_CP1/CP4 targeted, `APEX_GEN5.md` 16937–17022 (Ch.17), 17023–17356 (Ch.18 W+Z all), 17446–17561 (Ch.20 AA), 15750–15859 (X.6–X.8 reread as the optimizer parameter catalog), AI.13 rows G-ADAPTER/G-CAPACITY (harness specs), W.6 (bootstrap phases), §9.5-9 (optimizer writing live yaml is Wave-Out).

WRITE SET: `apex/research/` package (ADR-P2-005, logged; suggested internal: `backtest.py`, `walkforward.py`, `montecarlo.py`, `stress.py`, `optimizer.py`, `bootstrap.py`, `promotion.py`, `packages.py`, `parameter_governance.py`, `liquidity_proxies.py`, `legacy_adapters.py`) + `tests/unit/test_research_*.py`, `tests/integration/test_cp6b_research.py` (backtest == live-replay equivalence on fixture data) + `docs/research/` generated notes (optional) + control sections.

SCOPE:
1. Parameter governance service per Ch.17: parameter classes, dependency/redundancy map (Ch.1 §370–399), SL-12 change-proposal machinery: governed ranges, versioned ParameterPackage objects (id, hash, binding to snapshot), drift watch (>10% auto-rollback per R.3-4 discipline), read-only live params (`params/*.yaml` are bootstrap; injection path writes NEW package versions — optimizer never mutates live yaml).
2. Research plane per Ch.18 + AI.12 Phase 9: backtest engine on the SQLite store (same scheduler code path — determinism, not a parallel implementation), shared walk-forward + stress battery (§18.4) incl. named stress cases (zero-volume, OI-stale, gap ≥10×ATR, crash/flash), Monte-Carlo 1000-path weekly CVaR_95 producer for the risk advisory input (interface published; consumption already implemented by CP-5), outcome/attribution ingestion per reading-path 5.
3. Dual optimizer per W.1–W.9: signal optimizer + risk optimizer domains exactly (W/X bounds; nothing outside), full exhaustive grid generation per W.3 within declared budgets, nightly 03:00–05:00 UTC schedule + continuous-run enablement flag, objective functions verbatim, injection & rollback cycle with the RED LINE validator (any package touching vetoes/caps/circuit-breakers/owner ceilings → immediate rejection at validation), permanence statement honored.
4. First-run bootstrap W.6 three phases against `bootstrap_progress` table (cursor per symbol/TF, DEEP config 2020→2026, pause/resume, easy-hardware assumptions), honest duration estimates per W.7 surfaced as progress reporting (no fabricated claims).
5. Promotion per Z.1–Z.9: Wilson-score + cost-adjusted gate (exact z-quantile, floor accumulation below-floor rule), Bayesian shrinkage for small cells, SPRT live monitoring (automatic live-loser halt remains automatic; demotion needs OWNER confirm — state machine honors both), pool rule Z.2, sampling-unit = setup family (AD.1) enforcement, "no population until real backtest evidence" rule: family rows stay UNPOOLED/UNVERIFIED by construction (validation test: a promotable claim requires a stored, hash-bound evidence artifact).
6. Liquidity proxy models per Ch.20: 38-concept registry as data (A01–A25, B01–B10, D01–D03, C01–C06 rejected), AA.7 performance/deployment rules; runtime proxies degrade to UNAVAILABLE exactly as each concept's class dictates (L1 real, L2/L3 proxy/research); C-rejected concepts have NO code path (grep test).
7. Legacy adapter surface per AI.2/AI.12-7/G-ADAPTER-001: read-only v2/v3→v4.0.0 translation INTERFACES + conformance harness (fixture: v4-shaped synthetic legacy inputs; real legacy-data conformance remains owner-side OPEN — do not fabricate samples claiming provenance); idempotency adapter per T-AD-002 (cache discard on code_version change).
8. Package promotion injection: T-PKG-001 semantics — idempotent injection, version-locked, re-inject no-op; packages stored with lineage + validity window; runtime loader consumed by engines/scheduler.
MANDATORY TESTS: T-AD-001/002; T-PKG-001; optimizer-red-line rejection suite (construct a package touching veto → rejected before paper trial); Wilson/SPRT numeric conformance against worked example Z.8 (re-derived, not copied); walk-forward determinism (two runs byte-identical); bootstrap pause/resume/cursor recovery; CVaR advisory downgrade boundary; proxy registry completeness (38 rows) + rejected-6 absence; live-yaml immutability test (optimizer run cannot touch `params/*.yaml` — file-hash watch).
EXIT GATE: research plane runs the 10-day historical replay equivalence test (G-PAPER-001 semantics) on fixture data in CI; handoff lists package format + loader API for A10 verification; pushed.

---

## CP-7 — AGENT-10 — Integration audit & release verification (no new features)

Entry: CP-1..CP-6 all checked; read ALL handoffs (they are small by law) + DECISION_LOG fully.

READ SET: PROTOCOL, this section, ALL PHASE2_HANDOFF_CP1..CP6 (+CP7 self), DECISION_LOG, `APEX_GEN5.md`: 18315–19400 (Ch.24 AI.0–AI.15 + §9.9 fully), 20128–20247 (§9.5 reread), Ch.7, Ch.21 §14/§15 (targeted), Ch.23 (targeted); then — uniquely to you — repository-wide: `apex/**` structure, all `tests/**`, `params/**`, `pyproject.toml`, `requirements.lock`, `README.md`, `.gitignore` (you may read code broadly; your job is verification, and you write almost none).

WRITE SET: `tests/integration/test_cp7_release_gates.py` (the unified gate runner), `PHASE2_FINAL_REPORT.md`, completion rows/fixes in ALL control files' audit sections, minimal corrective patches ONLY where a predecessor violated its contract (each patch = own commit `[CP-7][AGENT-10] fix <agent>: <what>`, never a redesign — if a fix is bigger, reopen the CP via STATUS and instruct owner), no new subsystems ever.

SCOPE (the no-holes guarantee):
1. Tree conformance: every file of §9.5 tree exists at exact path, non-empty, importable; `git log --diff-filter` proves no renames/deletions; every additive file traced to a DECISION_LOG entry.
2. Test-matrix closure: execute the complete suite (`pytest tests/unit tests/integration` + module §8 batteries + your gate runner); EVERY AI.10 T-id maps to a real test with a recorded result (traceability Part II completed); the six fail-closed release rules of AI.10 enforced as assertions in your runner; T-NFR gates run in-sandbox with honest result labeling (sandbox ≠ target device → record "harness green; device measurement OPEN for owner", never claim device p95).
3. Completeness sweep across the repo (grep + AST): zero TODO/FIXME/NotImplementedError/`pass # stub`/mock-in-production; no fake venue responses outside test doubles; no `random` in decision paths without seeded determinism; import-lint passes (catalog-only access rule held across all waves); Wave-Out keyword audit (withdraw/transfer/flashClose/reversePosition/hedge/CROSS/SHADOW/Numba/PostgreSQL/networked-bus absent from runtime code); config env-name set exact; secrets scan (no key material in git/strings; `.env` ignored).
4. Cross-checks of the danger zones this plan flagged: E06 internal-SMA/ATR recomputation absence (PHASE 80/82); E11 K=9 everywhere; E12 window canonicalization; snapshot-id single-envelope (Phase 67A rule); fixture hashes = real digests of existing files (no-hash rule); p_raw=0.5 bootstrap + LIVE-gate via Gates 10/12 (not bypassable); leverage never 125; ledger single-writer (static analysis of writer instantiation sites == 1); scheduler semaphore 4; FSM state list exactly SL-6; params YAML == §9.5 frozen values; requirements.lock == SBOM nine pins; pytest dev-extra only.
5. Release-state ledger: per AI.13, record CODING_READY / PAPER_READY candidate state; every gate G-* = evidence-harness-delivered + owner-run-pending (or measured-and-logged if A08/A09 ran it for real); DOCUMENT_COMPLETE is pre-existing; LIVE_ELIGIBLE and PUBLIC_RELEASE_READY stay OPEN by definition (owner checklist + measurements) — declaring them closed is fabrication and forbidden.
6. DECISION_LOG triage: each OPEN-ISSUE → CLOSED (with evidence) or ESCALATED-TO-OWNER (verbatim, with both citations); nothing silently dropped. Final report assembled per P18/PROMPT §18 sections with the Blueprint Compliance Declaration worded exactly against real evidence.
EXIT GATE: unified gate runner green in-repo; final report complete; STATUS board CP-7 checked; push. The Phase-2 chain ends with you; you start no new feature work under any circumstances.

---

## Cross-checkpoint invariants (every agent re-asserts these in their tests)

1. `catalog.get` only; raw SQL confined to `apex/data_catalog/store`.
2. Identity: one uuid_v7, one canonical_json, one snapshot id formula.
3. Fail-closed everywhere: unspecified → refuse + record, never proceed.
4. Wave-Out list is law (P6).
5. Frozen numbers unretuned: §9.5-11, Ch.10 weights, θ_H=0.65, k=2, min_width=0.2, 0.55, caps table, 2/3/4/5 leverage.
6. Decimal/Text money; NaN/Inf never stored.
7. Ledger append-only, hash-chained, single writer.
8. No SHADOW, no ADMIN, no withdraw/transfer endpoints, no MARKET entry orders.
9. 140-cell universality; lints for symbol/TF membership.
10. Deterministic replay: same inputs + code_version ⇒ byte-identical outputs.
