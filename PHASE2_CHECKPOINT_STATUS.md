# APEX_GEN5 — PHASE 2 CHECKPOINT STATUS BOARD

Rules (binding): each CP section is edited ONLY by its owning agent slot(s), inside its own fenced block. The Owner-verification line is edited only by the owner. An agent must not start if the predecessor CP block below does not carry `[x] ALL EXIT BOXES PASS` and `[x] HANDOFF FILE WRITTEN`. Parallel slots (CP-3, CP-6) write disjoint blocks. Do not reformat others' blocks; git rebase conflicts in this file are resolved by keeping both blocks verbatim.

Legend: PENDING = not started · IN-PROGRESS = agent working · DELIVERED = agent pushed & self-checked · OWNER-VERIFIED = owner reviewed · REOPENED = audit found a violation.

---

## CP-0 · Owner bootstrap (files uploaded)
- [x] `APEX_GEN5.md`, `PROMPT.md`, `AI_SUGGESTION_PLAN.md` present, untouched (frozen inputs)
- [ ] All 24 `PHASE2_*` files present at repo root (1 master + 1 protocol + 1 checkpoints + 1 status + 1 traceability + 1 decision-log + 1 final-report + 7 handoffs + 10 prompts = 24)
- [x] Owner read `PHASE2_MASTER_PLAN.md` §7 runbook
- AGENT-NOTES: CP-0 is checked by the owner at upload time; first agent flips nothing here.

## CP-1 · AGENT-01 Foundation — STATUS: PENDING
```
[ ] ALL EXIT BOXES PASS (see PHASE2_CHECKPOINT.md CP-1 EXIT GATE; box-by-box copies below)
[ ] Every WRITE-SET file exists, non-empty, import-clean
[ ] DDL verbatim-equivalence rows present in TRACEABILITY Part I
[ ] params/*.yaml frozen-value assertions pass
[ ] T-DC-001..004, T-PIT-001..004, T-ID-001..002, T-CL-001..003, T-OM-001..003, T-RS-001..003 green
[ ] HANDOFF_CP1 written ≤400 lines, all mandatory headings
[ ] OPEN-ISSUES mirrored into DECISION_LOG (or `none`)
[ ] Pushed to main; commit range recorded below
OWNER-VERIFIED: [ ]   date: ____  notes: ____
```

## CP-2 · AGENT-02 Feature Fabric — STATUS: PENDING
```
[ ] ALL EXIT BOXES PASS
[ ] 74/74 registry complete + enforcement hook active + tier-cache rules tested
[ ] base.py API frozen and fully documented in HANDOFF_CP2 §INTERFACES
[ ] T-DR-001(feature tier), T-MON-001 green
[ ] HANDOFF_CP2 ≤400 lines; DECISION_LOG mirrored; pushed
OWNER-VERIFIED: [ ]   date: ____  notes: ____
```

## CP-3 · AGENT-03 (E01–E04) — STATUS: PENDING
```
[ ] ALL EXIT BOXES PASS; per-engine §8 batteries green; T-E01-001 green
[ ] HANDOFF_CP3 §[AGENT-03] ≤400 lines; pushed
```
## CP-3 · AGENT-04 (E05–E08) — STATUS: PENDING
```
[ ] ALL EXIT BOXES PASS; §8 batteries green; E06 evidence-consumption checks (no internal SMA/ATR) green
[ ] HANDOFF_CP3 §[AGENT-04] ≤400 lines; pushed
```
## CP-3 · AGENT-05 (E09–E12) — STATUS: PENDING
```
[ ] ALL EXIT BOXES PASS; §8 batteries green; T-E11-K9, T-E12-Windows green; E11 live-gate flag default-off
[ ] HANDOFF_CP3 §[AGENT-05] ≤400 lines; pushed
```

## CP-4 · AGENT-06 Context & Setup Chain — STATUS: PENDING
```
[ ] ALL EXIT BOXES PASS; gates 1–13 boundary matrix green; GF_SC_01/02 built with computed hashes
[ ] T-DR-002 green; chain runs end-to-end synthetic without decision/risk imports
[ ] HANDOFF_CP4 ≤400 lines; pushed
OWNER-VERIFIED: [ ]   date: ____  notes: ____
```

## CP-5 · AGENT-07 Decision→Risk→Execution→Ledger→Scheduler — STATUS: PENDING
```
[ ] ALL EXIT BOXES PASS; T_VETO(14×boundaries), T-LR-001..003, T_MATCH, T_RECONCILE, T_LEDGER, T_ADAPTER_* green
[ ] Scheduler boots full PAPER loop on fixture clock; single ledger writer proven
[ ] FSM illegal-transition matrix green; SHADOW/ADMIN/withdraw keyword absence green
[ ] HANDOFF_CP5 ≤400 lines; pushed
OWNER-VERIFIED: [ ]   date: ____  notes: ____
```

## CP-6 · AGENT-08 Control & Ops — STATUS: PENDING
```
[ ] ALL EXIT BOXES PASS; T-FB-001..003, T-NFR-004 green; watchdog + backup/restore drill green locally
[ ] README final run procedure complete and copy-pasteable (Termux)
[ ] HANDOFF_CP6 §[AGENT-08] ≤400 lines; pushed
```
## CP-6 · AGENT-09 Research & Governance — STATUS: PENDING
```
[ ] ALL EXIT BOXES PASS; T-AD-001/002, T-PKG-001, red-line rejection suite, YAML-immutability watch green
[ ] 10-day replay-equivalence harness runs green on fixture data (results honestly labeled)
[ ] HANDOFF_CP6 §[AGENT-09] ≤400 lines; pushed
OWNER-VERIFIED: [ ]   date: ____  notes: ____
```

## CP-7 · AGENT-10 Integration Audit & Release Verification — STATUS: PENDING
```
[ ] Full suite green; every AI.10 T-id mapped + result recorded in TRACEABILITY Part II
[ ] Tree conformance + completeness sweep + Wave-Out keyword audit + secrets scan green
[ ] DECISION_LOG: every OPEN-ISSUE CLOSED (evidence) or ESCALATED-TO-OWNER (verbatim)
[ ] PHASE2_FINAL_REPORT.md complete per PROMPT §18 structure incl. Blueprint Compliance Declaration
[ ] No new subsystems introduced (self-check: zero feature diffs; only corrective patches + tests + report)
[ ] STATUS board fully reconciled; pushed
OWNER-VERIFIED: [ ]   date: ____  notes: ____
```

## RESUME BLOCKS (used only by resume agents; append below the CP you resume)
(none)
