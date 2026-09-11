# APEX_GEN5 — PHASE 2 CHECKPOINT STATUS BOARD (Rev-2)

Rules (binding): each CP section is edited ONLY by its owning agent role, inside its own fenced block (CP-5: per-stage fenced blocks). The OWNER-VERIFIED lines are edited only by the owner. An agent must not start if the predecessor CP block does not show `[x] ALL EXIT BOXES PASS` + `[x] HANDOFF WRITTEN`. Parallelism is not required by this rev; if two stages of CP-5 ever overlap, they write disjoint stage blocks. Do not reformat others' blocks; rebase conflicts in this file keep BOTH blocks verbatim.

Legend: PENDING · IN-PROGRESS · DELIVERED (agent self-checked & pushed) · OWNER-VERIFIED · REOPENED (audit finding).

---

## CP-0 · Owner bootstrap — STATUS: PENDING (owner checks at upload)
- [ ] All 21 `PHASE2_*` files present at repo root (master, global-directives, protocol, checkpoints, salvage, status, traceability, decision-log, final-report = 9 · handoffs CP1..CP6 = 6 · prompts 01..06 = 6)
- [ ] `APEX_GEN5.md`, `PROMPT.md`, `AI_SUGGESTION_PLAN.md` present, untouched (frozen inputs)
- [ ] Owner read `PHASE2_MASTER_PLAN.md` §7 runbook
- [ ] Legacy reference repo confirmed frozen: owner makes no changes in `sinamoosazadeh/APEX_GEN5` while Phase 2 runs

## CP-1 · AGENT-01 Foundation + Feature Fabric + Salvage audit — STATUS: PENDING
```
[ ] ALL EXIT BOXES PASS
[ ] Tree files (CP-1 WRITE SET) exist, non-empty, import-clean (integration import-chain test)
[ ] Ch.4/Ch.5 DDL verbatim-equivalence rows filled in TRACEABILITY Part I (Result col)
[ ] params/*.yaml == §9.5/Ch.10/Ch.2.1/Ch.5 frozen literals (assertion test green)
[ ] requirements.lock == the nine SBOM pins; pytest dev-extra only; no python-dotenv import
[ ] 74/74 feature registry + §3.13 enforcement + tier-cache rules + guards green
[ ] base.py frozen; §INTERFACES complete in HANDOFF_CP1
[ ] SALVAGE rows §A01 all dispositioned (adopted rows carry in-repo proving tests)
[ ] T-DC-001..004, T-PIT-001..004, T-ID-001..002, T-CL-001..003, T-OM-001..003, T-RS-001..003, T-DR-001(feature tier), T-MON-001 green
[ ] HANDOFF_CP1 written ≤400 lines, all nine headings
[ ] OPEN-ISSUES mirrored into DECISION_LOG (or none)
[ ] Pushed; commit range recorded below; owner board check next
COMMIT-RANGE: ____  HANDOFF: PHASE2_HANDOFF_CP1.md  ISSUES-OPEN: ____
OWNER-VERIFIED: [ ]  date: ____  notes: ____
```

## CP-2 · AGENT-02 Engines E01–E06 — STATUS: PENDING
```
[ ] ALL EXIT BOXES PASS
[ ] Stage-1 §[STAGE-1 E01–E04]: conform/rewrite dispositions done; E01..E04 §8 batteries green; T-E01-001 green
[ ] Stage-2 §[STAGE-2 E05–E06]: E05/E06 §8 batteries green; E06 consumes pushed E01/E03/E04 evidence via interfaces only (no internal SMA/ATR)
[ ] SALVAGE rows §A02 dispositioned
[ ] HANDOFF_CP2 ≤400/section; §INTERFACES complete for A03; pushed
COMMIT-RANGE: ____  ISSUES-OPEN: ____
OWNER-VERIFIED: [ ]  date: ____  notes: ____
```

## CP-3 · AGENT-03 Engines E07–E12 — STATUS: PENDING
```
[ ] ALL EXIT BOXES PASS
[ ] Stage-1 §[STAGE-1 E07–E09]: §8 batteries green (E07↔E12 wired incl. degradation branch; E08 ch.2–4 Wave-Out respected)
[ ] Stage-2 §[STAGE-2 E10–E12]: §8 batteries green; T-E11-K9; T-E12-Windows; E11 live-gate flag default-off
[ ] §CP-3-INTEGRATION-NOTES appended (12-engine topic/version map)
[ ] HANDOFF_CP3 ≤400/section; pushed
COMMIT-RANGE: ____  ISSUES-OPEN: ____
OWNER-VERIFIED: [ ]  date: ____  notes: ____
```

## CP-4 · AGENT-04 Context chain — STATUS: PENDING
```
[ ] ALL EXIT BOXES PASS
[ ] Gates 1–13 boundary matrix green; weights/Q_min_setup assertion green; ×0.6 conflict multiplier & |ρ|>0.85 redundancy rules green
[ ] GF_SC_01/02 constructed with re-derived values + real hashes; GF_SC_03..12 schema-only
[ ] MTF relative algorithm + vacuous-pass test green; playbook exit-precedence (X.4) suite green
[ ] T-DR-002 green; end-to-end synthetic chain runs without decision/risk imports (seam proof)
[ ] HANDOFF_CP4 ≤400 lines; §INTERFACES complete for A05; pushed
COMMIT-RANGE: ____  ISSUES-OPEN: ____
OWNER-VERIFIED: [ ]  date: ____  notes: ____
```

## CP-5 · AGENT-05 Runtime core → Telegram/Ops → Research/Governance — STATUS: PENDING
```
[ ] §[RUNTIME] ALL PASS: T-DR-003; T_VETO ×14; T-VETO-SIZE; T-MON-002/T_MONOTONE; T-LR-001..003; T_MATCH; T_RECONCILE; T_LEDGER; T_ADAPTER_SUBMIT/DUPLICATE/LOST_ACK; E-EXEC-001; RSK-ERR-506; FSM illegal-transition matrix; leverage min() table; scheduler order/semaphore4; PAPER full-loop boot on fixture clock; trade_plan/outcome/ladder-state migrations logged
[ ] §[TELEGRAM-OPS] ALL PASS: T-FB-001..003; T-NFR-004; E-TELE-001..007 suite; idempotency replay; busy-guard; watchdog heartbeat-loss; dedup; backup+restore tempdir drill; Agg headless; README final run section present & copy-pasteable
[ ] §[RESEARCH] ALL PASS: T-AD-001/002; T-PKG-001; red-line rejection suite; YAML-immutability watch; Z.8 re-derived; determinism double-run; bootstrap pause/resume; CVaR boundary; registry-38 + rejected-6 absent; 10-day replay-equivalence harness green (labels honest)
[ ] HANDOFF_CP5: three stage sections ≤400 each; §[RESEARCH] carries final HOW-TO-RUN (full boot)
[ ] OPEN-ISSUES mirrored; pushed at each stage
COMMIT-RANGES: ____  ISSUES-OPEN: ____
OWNER-VERIFIED: [ ]  date: ____  notes: ____
```

## CP-6 · AGENT-06 Independent audit — STATUS: PENDING
```
[ ] Full suite green (unit+integration+§8 batteries+gate runner)
[ ] Every AI.10 T-id + AI.12 acceptance item ↔ real test + recorded result (MATRIX Part I/II complete)
[ ] Tree conformance + additive-file ↔ log reconciliation; salvage dispositions consistent
[ ] Completeness/Wave-Out/secrets-history/snapshot-envelope/uuid-single/single-writer sweeps reported
[ ] §9.9 readiness checklists evaluated box-by-box (owner-side items labeled OWNER-PENDING with harness pointer)
[ ] DECISION_LOG: every issue CLOSED-with-evidence or ESCALATED-TO-OWNER verbatim; false-greens reopened if found
[ ] PHASE2_FINAL_REPORT.md complete (PROMPT §18 structure + compliance declaration + owner action list)
[ ] No feature diffs beyond corrective patches (git diff --stat proof recorded)
COMMIT-RANGE: ____  REOPENED-CPs: ____
OWNER-VERIFIED: [ ]  date: ____  notes: ____
```

## CP-7 · Board closure (owner stamp; no code scope)
```
[ ] CP-0..CP-6 all DELIVERED + OWNER-VERIFIED
[ ] Owner read FINAL REPORT incl. escalation list; decided on the six external measurements + ECONOMIC_GATE
[ ] Phase-2 (coding) declared COMPLETE by owner — this line is the only lawful "done" signal
STAMP: ____  date: ____
```

## RESUME BLOCKS (append under the CP you resume; format: `RESUME @ <date> <AGENT-nn> [stage]: <ledger in handoff>` + the resuming session's completion line)
(none)
