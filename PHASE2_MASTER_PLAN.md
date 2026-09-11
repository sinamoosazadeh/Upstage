# APEX_GEN5 — PHASE 2 MULTI-AGENT IMPLEMENTATION PLAN (MASTER, REV-2)

Status: ACTIVE. Rev-2 (2026-09-12) supersedes Rev-1 after the owner's constraints review: agent count compressed to **5 implementation agents + 1 independent audit session (≤5 accounts)**, per-agent prompts now embed the **full text of all global directives** (PART G), and the **previous partial implementation is formally salvaged through an audited worksheet** (`PHASE2_SALVAGE.md`).

---

## 1. Purpose

Convert the frozen blueprint `APEX_GEN5.md` (20,551 lines, repo `https://github.com/sinamoosazadeh/Upstage`) into a complete, production-grade implementation, executed by a chain of mutually independent AI sessions. Each agent implements exactly one checkpoint; writes its completion/handoff report into pre-created control files; commits and pushes into the normative repository tree; stops. The successor reads the control files and its own blueprint ranges — never predecessors' code wholesale. The failure mode of the first attempt (one agent, token exhaustion at ~E04 of twelve engines) is engineered out in two ways: (a) coupling-driven checkpoint cuts sized per measured session capacity; (b) the RESUME protocol: an over-budget agent pushes partial work + a file-level remaining-work ledger, and a FRESH SESSION OF THE SAME ROLE (same prompt file) continues — roles stay 5, sessions may exceed 5, and independence comes from empty context, not from distinct accounts.

Empirical calibration used for sizing: the previous single session (same blueprint, same platform class) produced ~6.7K LoC — foundation + 74-registry + base + E01–E04 drafting — before stopping. Rev-2 therefore targets ~6–9K LoC written per agent, with the engine waves being the heaviest and explicitly resume-chained.

## 2. Source of truth and precedence (binding; full text in each agent prompt, PART G)

1. Owner decree (as recorded in the blueprint) > 14 hard vetoes (Ch.15 registry) > runtime Chapters 1–24 + GLOBAL IDENTITY/PIT UTILITY CONTRACT (L4104–4158) > engine chapters for engine formulas > diagrams.
2. Part R = history, EXCEPT §9.5 Execution-team directives (L20128–20247: normative repo tree, params YAML, env names, Wave-Out list, FROZEN_BOOTSTRAP values) — execution-team law.
3. `PROMPT.md`'s binding global sections (1,2,3,4,5,6,7,8,9,11,12,13,14,15,16,17,18,19) are preserved — embedded verbatim-adapted into every agent prompt (PART G), not deleted, not referenced-only.
4. The previous attempt's repo `sinamoosazadeh/APEX_GEN5` is REFERENCE MATERIAL ONLY (its `APEX_GEN5.md` copy is byte-identical to this repo's — verified SHA-256 — so it was built on the same frozen spec; its code may be salvaged ONLY through `PHASE2_SALVAGE.md` dispositions with per-line re-verification).
5. Known defects pre-adjudicated (DECISION_LOG ADR-P2-001..017): PROMPT.md's wrong repo URL (001); pytest dev-only (002); tree minimum+canonical (003); ladder-state table (004); research/ops packages additive (005); 3.12-tier modules under data_catalog (006); illustrative hashes re-computed (007); E11 YAML precedence (008); adapter conformance honesty (009); device/NFR gates as harnesses (010); SL-reference mapping (011); single-branch chain (012); .gitignore (013); fixture canonicality (014); salvage-is-audit-not-import (015); audit-session account reuse allowed, fresh-context required (016); engine seam E06↔E07 chosen to keep E06's dependencies (E01–E05) and E07's dependency (E12) inside slots (017).

## 3. Coupling analysis (why these five cut lines, no others)

Inseparable cores (never split): ① identity+contracts+store+quality+config+bus (everything imports them; corrections PHASE 67/67A unified exactly this layer); ② 74-feature registry + `engines/base.py` (the frozen engine contract — engines read features ONLY via `catalog.get`); ③ Risk(14 vetoes)+FSM+single-writer ledger+scheduler chain (blueprint forbids any bypass beneath Risk; all FSM mutations queue through one writer); ④ Evidence→Pattern→Setup→Playbook→Arbitration (shared 13-gate semantics and scoring formula).
Weak seams (safe cuts): the twelve engines are versioned-interface coupled with documented degradation (e.g., E06 without E01→Q2 fallback; E07 without E12→time-sync QX) → split at exactly ONE seam, E06|E07, chosen because: E06 consumes E01–E05 (all ≤E06 → same agent), and E07/E11 consume E12/E09/E10 (all ≥E07 → same agent). Runtime chain (Ch.13–16,19) consumes engines+context via frozen schemas. Ops (Ch.21,23) and Research (Ch.17,18,20) consume runtime events only — appended to the same slot with a stage split inside the handoff, never a new role.

## 4. Checkpoint architecture (Rev-2: 5 agents + 1 audit; CP-1..CP-7 board)

| CP | Agent | Account | Subsystems (blueprint) | Session expectation | Hard-stop gate (AI.12/§9.9 + plan) |
|---|---|---|---|---|---|
| CP-1 | AGENT-01 Foundation+Fabric | #1 | Ch.1,2,4,5,6,7 + identity contract + AI.3/5/6/8 + §3.12/13 + `engines/base.py` + params YAML + packaging/README-skeleton + **salvage audit of ALL A01 worksheet rows** | 1–2 | T-DC-001..004, T-PIT-001..004, T-ID-001..002, T-CL-001..003, T-OM-001..003, T-RS-001..003, T-DR-001(feature tier), T-MON-001 green; 74/74 registry; DDL verbatim; SALVAGE rows §A01 all dispositioned |
| CP-2 | AGENT-02 Engines E01–E06 | #2 | E01..E06 full §1–§10; **salvage audit of E01–E04 worksheet rows (complete/rewrite, no "simplified" inheritance)**; fixtures+§8 batteries | 2 (stage-1: E01–E04 conform+test; stage-2: E05–E06 fresh) | T-E01-001 + every engine's §8 suite; interface publication for A03 |
| CP-3 | AGENT-03 Engines E07–E12 | #3 | E07..E12 full §1–§10; fresh from blueprint; consumes A02's real modules via versioned interfaces | 2 (stage-1: E07–E09; stage-2: E10–E12) | per-engine §8 batteries; T-E11-K9; T-E12-Windows; CP-3 integration-notes block |
| CP-4 | AGENT-04 Context chain | #4 | Ch.8,9,10,11,12 (fabric, conflict, pattern+AC, setup 13-gates+AD, playbook AE/X.1–X.5, arbitration AF) + gf_sc_01/02 fixtures | 1–2 | T-DR-002; gate-1..13 boundary matrix; chain green end-to-end synthetic |
| CP-5 | AGENT-05 Decision→Risk→Execution→Ledger→Scheduler→Ops→Research | #5 | Ch.13(AG),14,15,16,19 + scheduler + store extensions; THEN stage-2: Ch.21,23 (Telegram/Ops) + Ch.17,18,20 (Governance/Research/Proxies) | 2–3 (stage-1 runtime core [must finish]; stage-2 telegram/ops; stage-3 research/governance) | T-DR-003, T_VETO, T-LR-001..003, T_MATCH/RECONCILE/LEDGER/ADAPTER-*, T-MON-002/T_MONOTONE, then T-FB-001..003, T-NFR-004, T-RESTORE-001, then T-AD-001/002, T-PKG-001, red-line suite; README run procedure complete |
| CP-6 | AGENT-06 Audit (independent) | reuse #1 or #2 as a FRESH CHAT (ADR-P2-016) | Ch.24 (AI.10 full + §9.9 checklists) + tree conformance + completeness/Wave-Out/secrets sweeps + matrix completion + triage + FINAL report assembly; corrective patches only, never redesign | 1–2 | board fully reconciled; every OPEN issue CLOSED-with-evidence or ESCALATED verbatim; `PHASE2_FINAL_REPORT.md` complete |
| CP-7 | — | — | board-closure checkpoint (owner): audit's exit boxes checked; Phase-2-coding declaration | — | per §7 below |

CP-7 is a board marker only: the owner's closure stamp after CP-6's exit boxes are checked; the audit's own gate rows live in CP-6 and there is no CP-7 code scope.

Rules: agents never start unless predecessor CP exit boxes are checked (entry gate); a CP is complete only with handoff ≤400-line per slot + traceability rows + green tests + pushed commits; partial budget ⇒ RESUME ledger, never silent truncation; CP-5's stages are intra-role handoffs written into `PHASE2_HANDOFF_CP5.md` sections §[RUNTIME], §[TELEGRAM-OPS], §[RESEARCH] so each successor stage session (same prompt) continues from exactly one section — the same mechanism the audit uses on CP-5's output.

## 5. Why not 3–4 agents (and why 5 is the floor)

3–4 would force either (a) one role reading >9K blueprint lines (E01–E12 in a single context ≈ 220K+ tokens of spec reading alone → the exact first-attempt failure) or (b) mid-core splits across roles (engine|fabric or risk|ledger boundaries — forbidden by §3's inseparability). The 5+1 architecture keeps every hard dependency inside a role and puts seams only where the blueprint itself defines graceful degradation. If any role needs more sessions, the RESUME mechanism adds sessions, not roles — the anti-drift property the owner is protecting is role-boundary discipline, not session count.

## 6. Control files (21 `PHASE2_*` files total; all upload-ready)

| File | Written by | Read by |
|---|---|---|
| `PHASE2_MASTER_PLAN.md` | Rev-2 planning | owner; agents (orientation only) |
| `PHASE2_GLOBAL_DIRECTIVES.md` | Rev-2 planning | canonical copy of PART G (each prompt embeds the same text; on divergence the prompt copy + this file are equivalent, the PROTOCOL's adjudications win) |
| `PHASE2_PROTOCOL.md` | Rev-2 planning | every agent (chain mechanics: rebase, ownership, handoff template, status law, reading budget details) |
| `PHASE2_CHECKPOINTS.md` | Rev-2 planning | every agent — own CP section (write sets, read sets, gates) |
| `PHASE2_SALVAGE.md` | Rev-2 planning | A01, A02 (worksheet above); A06 audits dispositions |
| `PHASE2_CHECKPOINT_STATUS.md` | each agent, own section only | every agent (entry gate); owner board |
| `PHASE2_TRACEABILITY_MATRIX.md` | each agent, pre-seeded sections | successors (their inputs); A06 completes |
| `PHASE2_DECISION_LOG.md` | each agent, own CP heading | every agent (§A before coding); A06 triages |
| `PHASE2_HANDOFF_CP1..CP6.md` | owning agent (CP-5/CP-6 multi-section) | the next role only (mandated) |
| `PHASE2_PROMPT_AGENT_01..06.md` | Rev-2 planning | pasted as the FIRST MESSAGE of each agent session; also the RESUME entry |
| `PHASE2_FINAL_REPORT.md` | A06 (+stage inputs) | owner |

## 7. Operating procedure (owner runbook, Rev-2)

1. **CP-0**: upload all 21 `PHASE2_*` files to the repo root (they sit beside `APEX_GEN5.md`, `PROMPT.md`, `AI_SUGGESTION_PLAN.md`). Commit: `PHASE2 CP-0 (rev2): control files`.
2. For each role 01→06: open a fresh AI session (account per table; role 06 = fresh chat on account 1 or 2); paste the ENTIRE content of `PHASE2_PROMPT_AGENT_0N.md`; send nothing else. Wait for push; verify the CP block on the STATUS board (boxes + handoff present). On RESUME-NEEDED: fresh session, SAME prompt file, which resumes from the remaining-work ledger. Repeat until the role reports COMPLETE.
3. Role 05 expects 2–3 sequential sessions (runtime → telegram/ops → research/governance) by design — that is stage-discipline inside ONE role, not new agents.
4. After CP-6: read `PHASE2_FINAL_REPORT.md`; reconcile the board (CP-7 row); the six external measurement procedures (Toobit depth listing/rate-limit, target-device spec + capacity, restore drill, paper-trading windows, ECONOMIC_GATE checklist) are owner-side executions of delivered harnesses — Phase-2 CODING completion does not wait on them; LIVE capital deployment does (AI.13/AI.14).
5. Never let two roles touch the same file: the ownership map in `PHASE2_CHECKPOINTS.md` + the rebase rules in PROTOCOL P14 make parallelism safe, but the recommended cadence is strictly serial.

## 8. What remains from Rev-1 unchanged (deliberate)

Blueprint reading map (§3 of Rev-1, reproduced inside CHECKPOINTS per-role), the ten cross-checkpoint invariants, the "no silent contradiction" law (G13), fixture/hashing integrity (G11), Wave-In/Wave-Out discipline (G6), the AI.12/AI.13/§9.9 gate binding, naming/numbering integrity (P20/G19), and the assessment of `AI_SUGGESTION_PLAN.md` (Rev-1 §9) — all carried into the agents' PART G and CHECKPOINTS. Rev-2's only structural changes: role compression with intra-role staging, salvage law, directive embedding.
