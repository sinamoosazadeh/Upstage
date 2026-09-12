# APEX_GEN5 — PHASE 2 MASTER PLAN — Rev-3 (FINAL)

Status: ACTIVE. Rev-3 (2026-09-12) supersedes Rev-2 per the owner's model correction: the real execution substrate is **a serial chain of isolated chat sessions — one freshly-registered account = one fixed, non-extendable context window = one stage**. There are no "agents", no parallelism, no multi-session products, no shared memory. The previous partial-attempt repository is **deleted by the owner and is NOT part of this plan in any way** (ADR-P2-015): Phase 2 runs 100% from zero; its only legacy use was capacity calibration (ADR-P2-016). A review/audit phase is the owner's separate later decision and is deliberately NOT part of this plan.

---

## 1. Mission
Convert the frozen blueprint `APEX_GEN5.md` (20,551 lines; sha256 `216bcc9e…fbd9e`) in `https://github.com/sinamoosazadeh/Upstage` into the complete production implementation of the normative tree (§9.5), stage by stage, with zero deviation, full tests, and file-based handoffs. The blueprint is the sole truth; `PROMPT.md` is the standing Chief-Engineer directive; this plan's control files are the only coordination medium.

## 2. Capacity model (why eight stages)
Measured anchor: the solo prior attempt burned one full window producing ~6.7k mostly-thin lines after ~5–7k spec lines of reading, dying around E03/E04 of twelve engines — with no tests. Full-fidelity work costs more per line (real math + §8 batteries + fixtures + params). Therefore: total remaining work ≈ 55–65k work-lines (≈17k blueprint reading + ≈36k code/tests + control-file bookkeeping) → **8 stages sized at ~6–11k work-lines each (≈60–75% of measured ceiling)**, each ending in a green push with its gate boxes provably checked. Six stages would require ~13k-line windows — the exact profile that already died once. Stage count is a derived quantity, not a preference; if any stage overflows, the OVERFLOW ledger (P18/G19) absorbs it with one continuation account for that stage, which is cheaper and safer than overloading a window.

## 3. Stage table (one fresh account per row, strictly serial; never run two accounts before the predecessor's board boxes are all checked)

| Stage | Subsystems (blueprint ranges) | Main writes (normative tree) | Est. read+write |
|---|---|---|---|
| CP-1 | Ch.1–2 (L87–1197) · identity contract (L4104–4158) · §3.12/3.13 (L13529–14382) · Ch.4/5 DDL (L14383–14642) · Ch.7 (L14643–14671) · §9.5 (L20128–20247) | packaging, config, errors, bus, identity×4, data_catalog (contracts/catalog/store/ingest + tier registry), quality×3, 6 params YAMLs, `engines/base.py`, tests, README skeleton | ~3.3k + 6.2k |
| CP-2 | E01 (L1205–2789) · E02 (L2790–3871) · E03 (L3872–4954) | `apex/engines/e01..e03/` full §3/§5/§6/§8 incl. all Phase-correction clauses + fixtures + batteries | ~3.8k + 3.6k |
| CP-3 | E04 (L4955–5601) · E05 (L5602–6859) · E06 (L6860–8292) | `e04..e06/` + evidence-consumption through base contract | ~3.4k + 3.5k |
| CP-4 | E07 (L8293–9085) · E08 (L9086–9466) · E09 (L9467–10275) | `e07..e09/` (E07 degradation branch for absent E12; E08 ch.2–4 Wave-Out raises) | ~2.0k + 3.3k |
| CP-5 | E10 (L10276–11670) · E11 (L11671–12732) · E12 (L12733–13528) | `e10..e12/` + E07↔E12 integration tests + 12-engine interface map (handoff §CP-5-INTEGRATION-NOTES) | ~3.3k + 3.2k |
| CP-6 | Ch.8–12 (L14672–15971) · Ch.13–15 (L15972–16749) | `fabric/×3`, `pattern/×2`, `setup/×2`, `playbook/`, `forecast/`, `decision/`, `risk/kernel.py`, GF_SC fixtures, 13-gate + 14-veto suites | ~2.1k + 6.6k |
| CP-7 | Ch.16 (L16750–16936) · Ch.19 (L17357–17445) · Ch.21 (L17562–18220) · Ch.23 (L18221–18314) · AI.3 | `execution/×3`, `ledger/`, `scheduler/`, `telegram/×2` + alerts, PAPER-loop integration suite, README run finalization | ~1.2k + 7.0k |
| CP-8 | Ch.17 (L16937–17022) · Ch.18 (L17023–17356) · Ch.20 (L17446–17561) · Ch.24 W/Z/AA (L18581–18905) · AI.12/13/14 · §9.9 (L19212–19400) | `research/**`, `ops/×2`, governance service, harnesses, FULL-SUITE closeout sweep, `PHASE2_FINAL_REPORT.md` | ~0.9k + 5.2k |

Dependency proof: base/registry precede all engines (CP-1); E10/E11 consume E01–E09 (CP-2..4 done); chain consumes engines (CP-2..5 done); risk consumes setup candidates (same stage CP-6, sequenced fabric→…→risk in commits); execution consumes risk decisions (CP-7); telegram consumes execution events (CP-7); research/governance consume everything + are last (CP-8). E07's only forward dependency (E12) is handled by the blueprint's own degradation branch + a CP-5 integration test.

## 4. Execution model (owner runbook)
1. Upload the 16 control files (this plan §6) to `Upstage` root — exactly as named; verify `APEX_GEN5.md` sha256 == `216bcc9e5f3e54c7567303bea7b642a9f5ccf482d2282d05dc78c2f7cb0fbd9e`.
2. For stage n = 1..8: register a fresh account (new Gmail) on the chat-bot, connect it to GitHub with write access to `Upstage` ONLY (fine-grained PAT limited to that repo; no other repo, no org rights), then paste the stage-n prompt text (delivered to the owner in chat by the plan author — NOT stored in the repo) as the first and only instruction. Type nothing else.
3. Watch: the executor reads law → verifies predecessor gate → claims board → builds → tests → pushes → writes handoff → fills traceability → closes boxes → stops. Verify on the board that every CP-n exit box is `[x]` with named evidence, and `PHASE2_HANDOFF_CPn.md` is complete.
4. If a stage reports CONTINUE-NEEDED (overflow): register ONE more account and paste the generic CONTINUE prompt (delivered alongside the stage prompts); it finishes only the ledger of that CP, closes it, then normal chain resumes at stage n+1.
5. NEVER run two stages concurrently, never paste a stage prompt into the same chat twice, never edit predecessors' control blocks except at listed extension points.
6. After CP-8: board shows CODE-COMPLETE candidate; owner runs the external-measurement procedures named in the final report; a separate review/audit phase is decided afterward by the owner (out of this plan).

## 5. Failure modes engineered against (each has a mechanical defense above)
Solo-window overload → stage sizing + OVERFLOW ledger · silent simplification → §8 battery exit gates + G4 no-"Simplified" rule · invented tables/paths → tree-conformance Part I + verbatim DDL rows · cross-stage interface drift → interface blocks in handoffs; successors code against handoff+blueprint, not predecessors' file bodies · board lies → boxes need test-name evidence; closeout re-runs everything · two writers → serial execution rule (no parallel accounts) · context amnesia of the plan → prompts are self-contained orderings; law is mandatory first read with acknowledgement line · legacy temptation → ADR-P2-015 (repo deleted; nothing to salvage) · secrets → G16 + closeout history grep.

## 6. Control files in the repo (16; nothing else may exist at root beyond frozen inputs + normative tree)
`PHASE2_MASTER_PLAN.md` (this file) · `PHASE2_GLOBAL_DIRECTIVES.md` (common law G1..G20 — first mandatory read of every stage) · `PHASE2_PROTOCOL.md` (mechanics P1..P21) · `PHASE2_CHECKPOINTS.md` (per-stage contracts) · `PHASE2_CHECKPOINT_STATUS.md` (board; claim/claim-close only in own block) · `PHASE2_TRACEABILITY_MATRIX.md` (Parts I/II pre-seeded; Part III per stage) · `PHASE2_DECISION_LOG.md` (ADRs 001..017 + open issues) · `PHASE2_HANDOFF_CP1.md`…`PHASE2_HANDOFF_CP8.md` (nine-heading template pre-created) · `PHASE2_FINAL_REPORT.md` (filled at CP-8). Stage prompts are chat-side only by owner decree.

## 7. Rev-3 change log
Removed: whole salvage apparatus (`PHASE2_SALVAGE.md`, P14-bis, SALVAGE handoff section, audit-oriented agent prompts in repo), the internal audit stage (CP-6/AGENT-06 of Rev-2), the RESUME/multi-session-role mechanics, all parallelism language. Restated: 8 stages = 8 accounts serial (capacity-derived), overflow via continuation account, law delivery = repo `PHASE2_GLOBAL_DIRECTIVES.md` with blocking first-read + acknowledgement (the shared prompt part), prompts written in chat only, traceability/status/decision-log renumbered CP-1..CP-8, ADRs 001/015/016/017 rewritten to owner decrees.
