# APEX_GEN5 — PHASE 2 MULTI-AGENT IMPLEMENTATION PLAN (MASTER)

Status: ACTIVE — this file governs the Phase 2 (implementation/coding) execution.
Owner of this plan: the project owner (human). Readers: all implementation agents (as orientation) and the owner (as operations manual).

---

## 1. Purpose

This plan converts the frozen blueprint `APEX_GEN5.md` (20,551 lines; repo `https://github.com/sinamoosazadeh/Upstage`) into a complete production implementation, executed by a chain of mutually independent AI agents. Each agent implements exactly one checkpoint, writes its completion/handoff report into pre-created control files, commits and pushes into the normative repository tree, and stops. The next agent starts from the control files only — never from the previous agents' chat history and never by re-reading all prior code.

Why a chain and not one agent: the single-agent attempt failed on token budget. The blueprint's engine block (Chapter 3) alone is ~13,000 lines (~220K tokens). This plan's partitioning is therefore **coupling-driven and token-aware**, not page-driven: inseparable cores stay with one agent; loosely-coupled satellites get their own agent; every handoff is a bounded artifact.

## 2. Source of truth and precedence (binding for every agent)

1. Owner written decree, as recorded in the blueprint.
2. The 14 hard risk vetoes (Canonical Risk Veto Registry, Chapter 15 §15.1 / SL-5).
3. `APEX_GEN5.md` runtime text — Chapters 1–24 (and the GLOBAL IDENTITY / PIT UTILITY CONTRACT embedded in the E03 section, lines 4104–4158).
4. Engine chapters over runtime chapters **for engine formulas** (preamble rule).
5. Diagrams (narrative only; e.g., the Chapter-1 execution diagram defers to the canonical SL-6 FSM list).
- Part R (`# Part R — Document Record`, lines 19401–20551) is history — **with one exception**: `§9.5 Execution-team directives` (lines 20128–20247) is normative for the execution team (repository tree, params YAML, env names, Wave-Out list, FROZEN_BOOTSTRAP values). It was frozen by owner decree as directives, not as history.
- `PROMPT.md` is the Phase-1 chief-engineer directive. Its sections 1, 4, 5, 6, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18 are preserved, re-based and re-scoped for per-agent use in `PHASE2_PROTOCOL.md`. Where PROMPT.md and this plan differ on process (single-agent assumptions), this plan wins; where either differs from APEX_GEN5.md on design, APEX_GEN5.md wins.
- Known defect, pre-adjudicated (ADR-P2-001): PROMPT.md "START EXECUTION" cites repo `sinamoosazadeh/APEX_GEN5`; the actual repository is `sinamoosazadeh/Upstage`. All Phase-2 files use `https://github.com/sinamoosazadeh/Upstage` exclusively.

## 3. Blueprint map (reading ranges; line numbers are navigation aids — heading text is canonical)

| Block | Content | Lines | Used by |
|---|---|---|---|
| Preamble + reading path + Contents | precedence, 5 stations, TOC | 1–86 | all |
| Ch.1 System Overview | SBOM, latency budget, architecture, FSMs, quality gates, PIT flow, parameter dependency graph, risk ladder | 87–417 | A01; A07 (FSM/ladder); A08 (wizard) |
| Ch.2 Global Contracts | 2.1 Quality Q0–QX (429), 2.2 Numerical (734), 2.3 PIT windows (899), 2.4 Lineage (1100), 2.5 Security (1135), 2.6 Retention/backup (1175) | 418–1197 | A01 (all); engines cite 2.1/2.2 |
| Ch.3 Twelve Analysts | E01 1205–2789; E02 2790–3871; E03 3872–4954 (GLOBAL IDENTITY/PIT contract at 4104–4158 belongs to A01); E04 4955–5601; E05 5602–6859; E06 6860–8292; E07 8293–9085; E08 9086–9466; E09 9467–10275; E10 10276–11670; E11 11671–12732; E12 12733–13528 | 1198–13528 | A03 (E01–E04); A04 (E05–E08); A05 (E09–E12) |
| §3.12 Candle Intelligence — 74-feature registry; §3.13 completeness | ATOM/MOLECULAR/ORGANISMIC tiers, catalog keys, cache rules | 13529–14382 | A02 |
| Ch.4 Data Plane and Persistence | logical DDL (8 tables) | 14383–14544 | A01 |
| Ch.5 Trading Universe | raw_observation + bootstrap_progress DDL, `catalog.get`, symbol table, chapter epsilon convention | 14545–14637 | A01 |
| Ch.6 Feature Catalogue | pointer to 3.12/3.13 | 14638–14642 | A02 |
| Ch.7 Error Codes | normative error table | 14643–14671 | A01 (registry), all (consume) |
| Ch.8 Evidence Fabric, Conflict, Cross-Domain | fabric/context schemas, 7 invariants, MTF, inter-symbol | 14672–14907 | A06 |
| Ch.9 Pattern Intelligence (+AC.1–AC.5) | hierarchy, detector catalogue, registry governance, GF_SC_01/02 spec (15019–15021) | 14908–15208 | A06 |
| Ch.10 Setup Engine (+AD.1–AD.8) | 13 hard gates (15213), scoring, MTF rule, family SF_FVG_SWEEP_REV | 15209–15476 | A06 |
| Ch.11 Playbook and Position Management (+AE, +X.1–X.8) | playbook PB_FVG_SWEEP_REV_A, BE/trail/time-stop, exit precedence, risk-optimizer param catalog | 15477–15859 | A06 (playbook), A09 (X catalog) |
| Ch.12 Strategy Arbitration (+AF) | gatekeeper rules, NO-TRADE output | 15860–15971 | A06 |
| Ch.13 Statistical Forecast P/U/C (+AG models) | forecast contract, bootstrap P model (p_raw=0.5), U/C formulas, AG registry | 15972–16517 | A07 |
| Ch.14 Decision Engine | EU formula, eligibility, ranking | 16518–16590 | A07 |
| Ch.15 Risk Kernel | 14 vetoes + Canonical registry, sizing machine, ladder mapping, circuit breakers, margin health | 16591–16749 | A07 |
| Ch.16 Execution, Venue Adapter, Ledger | SL-6 FSM, trade_plan DDL, idempotency keys, Toobit wire, adapter contract, rollover, stop-gap | 16750–16936 | A07 |
| Ch.17 Parameter Governance | classes, dependency/redundancy (SL-12 umbrella) | 16937–17022 | A09 |
| Ch.18 Research, Optimizer, Promotion (+W, +Z) | dual optimizer, first-run bootstrap W.6, promotion gates (Wilson/SPRT), shared walk-forward/stress | 17023–17356 | A09 |
| Ch.19 Economic Gate and Leverage (+Y.1–Y.4) | five-item checklist, leverage guardrail min(Y.2, owner, exchange) | 17357–17445 | A07 (gate logic), A08 (checklist UI) |
| Ch.20 Liquidity Proxy Models (+AA) | 38-concept registry, rejections, deployment rules | 17446–17561 | A09 |
| Ch.21 Telegram Control and Signaling | screens/wizard, callbacks, busy guard, token bucket, chart renderer, 24-field evidence display contract | 17562–18086 | A08 |
| Ch.22 Glossary | vocabulary; §22.1 semantic mapping | 18087–18220 | all (reference) |
| Ch.23 Deployment, Redundancy, Recovery | Termux model, watchdog peer + Gmail, startup reconciliation, single event loop + bounded pool + single ledger writer, load/capacity, runbooks, Monitoring and Alert Policy | 18221–18314 | A08 (ops), A01 (config context) |
| Ch.24 Integration and Release Gates (AI.0–AI.15) | canonical contract table AI.2, replay model AI.3, lifecycle AI.4, raw store AI.5, OI policy AI.6, NFR AI.7, idempotency AI.8, fallback AI.9, test matrix AI.10, ownership AI.11, **binding phase plan AI.12**, external gates AI.13, open items AI.14 | 18315–19211 | all (per topic); A10 (audit) |
| §9.9 Final Integration Pass | status summary, contradiction resolutions, execution readiness checklists | 19212–19400 | A10; all (pre-decided resolutions) |
| Part R | R.0–R.9; §9.5 execution directives 20128–20247 (normative for this team) | 19401–20551 | A01 (tree, params, env); all (Wave-Out) |

## 4. Coupling analysis — why the checkpoints cut where they cut

**Inseparable cores (never split across agents):**
1. **Foundation core** — Ch.2 global contracts + GLOBAL IDENTITY/PIT utility contract + Ch.4/Ch.5 storage + quality engine + config/errors/bus. Every other block imports it; splitting the identity layer from the store or the quality engine would fork the two-tier epsilon and snapshot semantics that the correction records (PHASE 67/67A, R.7) specifically unified. One agent (A01) owns it end-to-end.
2. **Feature registry + engine base** — §3.12/3.13 (74 features, tier caching, `catalog.get` only) plus `apex/engines/base.py`. Engines may only read features through the catalog; the base class IS the engine contract (streaming, idempotency, snapshot_id, evidence emission). One agent (A02) freezes it; engine agents code against the frozen base, not against each other.
3. **Risk–Execution–Ledger** — Ch.15 + Ch.16 + single ledger writer + scheduler chain. Veto autonomy (veto independence), reconcile-first, hash-chained ledger and the SL-6 FSM form one behavioral unit; the blueprint makes it explicit that nothing below Risk may bypass a veto and that every FSM mutation passes through the one writer queue (Ch.23). One agent (A07).
4. **Setup chain** — Ch.8→9→10→11→12 is one evidence→context→pattern→setup→playbook→arbitration flow with shared gates (13 hard gates), scoring formula, MTF rule, and the single Wave-In family/playbook. Splitting mid-chain would fork the gate semantics. One agent (A06).

**Loosely coupled satellites (separate agents; interface = frozen v4.0.0 schema + graceful degradation per AI.2):**
- Engines E01–E12 are the token mass of the blueprint (~13K lines). Inter-engine dependencies are all versioned contracts with explicit downgrade behavior (e.g., E06 on Structure <4.0 → `structural_event=None`, quality Q2; PHASE 80/82 records: E06 consumes E03 volume evidence and E04 volatility evidence — never recomputes them internally). Therefore engines split 3×4 by formula affinity: A03 (E01–E04: structure/liquidity/volume/volatility), A04 (E05–E08: fvg/orderblock/rtm/wyckoff), A05 (E09–E12: trend/momentum/regime/temporal). Each reads its predecessor's 2 KB interface handoff, not its predecessor's code.
- Telegram/ops (A08) and research/governance (A09) are consumers of frozen runtime events, never owners of trading semantics; they run after CP-5, in either order.
- Integration audit (A10) writes no features: it executes the AI.10 matrix, sweeps completeness, and closes the ledger.

**Cross-cutting rules verified in the blueprint and enforced by the plan:**
- All consumers read features only via `catalog.get()`; `get_ohlcv` outside `apex/data_catalog` is a build-breaking lint (Ch.5) — enforced at CP-1 with a repo-wide lint test authored by A01 and re-run by A10.
- Scheduler (directive 14): per TF close `ingest→quality→features→engines→setup→gates→risk→decision→execution`, semaphore 4, HTF last-closed only — the full chain only assembles at CP-5 (A07 owns `apex/scheduler/clock.py`).
- The repository tree (§9.5, lines 20156–20213) is minimum and canonical: "create every file; do not rename." Additive files are permitted ONLY where a blueprint chapter requires them (per-engine fixtures/tests, 3.12 tier modules, ops scripts, research package); every addition is logged in `PHASE2_DECISION_LOG.md`.

## 5. Checkpoint architecture (7 checkpoints, 10 agent slots, single linear chain)

Waves W1–W6 run one agent each except as noted; A03→A04→A05 run in that order (baton chain; each reads the prior handoff). A08/A09 may run in either order or in parallel (disjoint paths). Full definitions: `PHASE2_CHECKPOINTS.md`.

| CP | Wave | Agent slot(s) | Subsystems (blueprint) | Gate (hard stop; from AI.12 + §9.9 checklists) |
|---|---|---|---|---|
| CP-0 | — | Owner (human) | Upload control files; verify repo clean; no code | Files present, APEX_GEN5.md untouched |
| CP-1 | W1 | A01 Foundation | Ch.1, Ch.2, Ch.4, Ch.5, Ch.7, identity contract, AI.3/5/6/8, §9.5 (tree, params, env), pyproject, requirements.lock, README run skeleton, engine-lint guard | T-DC-001..004, T-PIT-001..004, T-ID-001..002, T-CL-001..003, T-OM-001..003, T-RS-001..003 pass |
| CP-2 | W2 | A02 Feature Fabric | §3.12, §3.13, Ch.6, `apex/engines/base.py`, feature catalog registration, tier caching, EvidenceEvent model | All 74 features registered; registry count == catalogue count; T-DR-001 (feature tier) + T-MON-001 pass |
| CP-3 | W3 | A03 (E01–E04), A04 (E05–E08), A05 (E09–E12) | Ch.3 engine blocks §1–§10; per-engine schemas, params tables, golden fixtures, validation suites | T-E01-001, T-E11-K9, T-E12-Windows + every engine §8 suite passes; E11 K=9≠d=8 proven; Wave-Out items raise, never implemented |
| CP-4 | W4 | A06 Context & Setup Chain | Ch.8, 9, 10, 11(playbook), 12; gf_sc_01/02 fixtures; 13 gates; SF_FVG_SWEEP_REV; PB_FVG_SWEEP_REV_A; arbitration | T-DR-002 passes; gates 1–13 unit-proven; conflict/redundancy penalties (0.4/0.25) exact |
| CP-5 | W5 | A07 Decision → Risk → Execution → Ledger → Scheduler | Ch.13 (+bootstrap P model), 14, 15, 16, 19 (gate logic), scheduler; trade_plan DDL; Toobit adapter+map | T-DR-003, T_VETO (all 14 vetoes on boundaries), T-LR-001..003, T-MON/T_MONOTONE, T_ADAPTER_SUBMIT/DUPLICATE/LOST_ACK, T_MATCH, T_RECONCILE, T_LEDGER pass |
| CP-6 | W6 | A08 Control & Ops (Ch.21, 23, wizard, watchdog, backup, README final); A09 Research & Governance (Ch.17, 18, 20, X.6, promotion, bootstrap, parameter governance service) | G-PAPER harnesses, T-RESTORE-001, T-PKG-001, T-FB-001..003, T-AD-001/002 conformance-as-spec'd; optimizer never writes live yaml |
| CP-7 | W7 | A10 Integration Audit & Release Verification | Ch.24 full matrix execution, §9.9 checklists, completeness sweep (no TODO/placeholder/stub module), tree conformance, secrets scan, FINAL report | Every T-ID mapped to a test file with a result; every open item in DECISION_LOG either closed or escalated to owner verbatim |

Checkpoint rule: an agent **must not start** unless the predecessor CP section in `PHASE2_CHECKPOINT_STATUS.md` shows all exit boxes checked and the predecessor handoff file exists and is non-empty. If an agent exhausts its budget mid-CP, it executes the RESUME protocol (§16 PROTOCOL): push partial work, write the "REMAINING WORK LEDGER" section in its handoff; the owner launches a fresh agent from the SAME prompt file in RESUME mode. No checkpoint is ever skipped or partially merged forward.

## 6. Control files (all pre-created; upload-ready; do not edit their content before wave 0)

| File | Written by | Read by |
|---|---|---|
| `PHASE2_MASTER_PLAN.md` (this file) | planning pass | owner; agents (orientation only) |
| `PHASE2_PROTOCOL.md` | planning pass | EVERY agent, in full (the only common-law file) |
| `PHASE2_CHECKPOINTS.md` | planning pass | every agent (its own CP section) |
| `PHASE2_CHECKPOINT_STATUS.md` | each agent updates ONLY its own CP section | every agent (predecessor sections); owner board |
| `PHASE2_TRACEABILITY_MATRIX.md` | each agent fills ONLY its pre-seeded tables | successor agents (their inputs); A10 completes |
| `PHASE2_DECISION_LOG.md` | each agent appends ONLY under its CP heading | every agent (open-issues section); A10 triages |
| `PHASE2_HANDOFF_CP1..CP7.md` (7 files) | owning agent(s) of that CP, under their slot heading | the next wave's agents (mandated reading); nothing else |
| `PHASE2_PROMPT_AGENT_01..10.md` (10 files) | planning pass | pasted as the kickoff message to that agent; also its resumption |
| `PHASE2_FINAL_REPORT.md` | A10 (+A08/A09 runtime sections) | owner |

## 7. Operating procedure (owner runbook)

1. **CP-0**: upload all `PHASE2_*` files to repo root (they arrive alongside `APEX_GEN5.md`, `PROMPT.md`, `AI_SUGGESTION_PLAN.md`). Do not edit them. Commit message: `PHASE2 CP-0: control files`.
2. **For each wave W1→W7**: open a FRESH session with one AI account; paste the entire content of that agent's `PHASE2_PROMPT_AGENT_NN.md`; nothing else. (For W3, order: 03, then 04, then 05. For W6, order: 08 then 09, or parallel.)
3. Wait for push. Verify `PHASE2_CHECKPOINT_STATUS.md` shows the CP checked and CI/tests green in the report. If the agent reported RESUME-NEEDED, repeat step 2 with the same prompt file (RESUME mode).
4. After CP-7 push, read `PHASE2_FINAL_REPORT.md`. Phase 2 (coding) is complete when its completion declaration is affirmative and no OPEN-ISSUE blocks remain triaged as unresolved; external measurement gates (AI.13: Toobit depth, device p95, restore drill, paper trading, owner checklist) are owner-side obligations with delivered harnesses — they are NOT code gaps and are never "passed" by an agent's self-claim.

## 8. What this plan explicitly does NOT allow

- Any agent reading "all previous code" (token economy in PROTOCOL §15 with hard limits).
- Silent conflict resolution: real contradictions go to `PHASE2_DECISION_LOG.md` + fail-closed behavior; the agent that spots it must not improvise new rules.
- Any new file name/number not defined by the normative tree or the blueprint chapter that requires it.
- Any implementation of Wave-Out items (full list, §9.5 directive 9) — raise `WaveOutError`, never fake it.
- Fabricated numbers anywhere: fixture hashes (hash only after fixture exists), case-study values (re-derive), p95/depth/Sharpe statistics (declare UNVERIFIED unless actually measured in that run).
- Editing `APEX_GEN5.md`, `PROMPT.md`, `AI_SUGGESTION_PLAN.md`, or any file owned by another agent.

## 9. Assessment of the prior AI suggestion (`AI_SUGGESTION_PLAN.md`)

Adopted: handoff-through-artifacts (not code re-reading); per-agent completion reports; checkpoint status board; audit-before-completion. Rejected with reasons: (a) layer-block partitioning L1–L5 / L6–L8 / L9–L12 / L13–L15 — bundles 12 engines + candle intelligence (≈14K spec lines) into one agent, which is exactly the token failure mode that killed the first attempt; (b) a "Controller agent that writes no code" adds a session without adding throughput — replaced here by control files + CP-7 audit agent; (c) no path-ownership, no reading budget, no resume protocol, no pre-adjudications — the three main sources of cross-agent drift; all three are core mechanisms of this plan.

## 10. Hazards found during analysis, pre-adjudicated here (full text: PHASE2_DECISION_LOG.md ADR-P2-001..014)

PROMPT.md repo-URL mismatch (001); pytest as dev-only dependency, runtime SBOM untouched (002); §9.5 tree is the minimum+canonical file inventory, additive files need a log entry (003); emergency-ladder persistence table is unspecified — additive table under `apex/` with log entry (004); research/ops packages have no tree entries but AI.12 demands them — additive `apex/research/**`, `scripts/**`, logged (005); 3.12 tier-module wording vs flat tree files — tree wins for named files, tier modules additive (006); illustrative fixture hashes in the document (e.g., E01 FIX_001 carries the empty-string SHA-256) must be RE-COMPUTED, never copied (007); `e11_params_v4.yaml` values are §9.5-canonical, engine §6 tables govern formula internals; mismatch → OPEN issue (008); v2/v3 adapter conformance has no legacy data in this repo — interfaces implemented, conformance on real legacy data stays owner-side OPEN gate (009); NFR/device gates deliver harnesses, measurements remain honest OPEN/UNVERIFIED (010); dangling "Chapter 5, SL-0..SL-15" citations resolve to each contract's owning chapter (011); single linear baton chain with rebase-on-push for races (012); `.gitignore` for runtime data added by A01, logged (013); engine §9 case studies are illustrative, §8 golden fixtures are canonical, GF_SC bars must be constructed per spec (014).
