# PHASE2 HANDOFF — CP-5 (Runtime core → Telegram/Ops → Research/Governance) → consumed by AGENT-06

Author: AGENT-05, across up to three sessions (one per stage). Three stage sections, ≤400 lines each, identical heading order (PROTOCOL P16). Successor sessions of THIS role read only the prior stage sections (REMAINING WORK LEDGER first). The audit reads all three.

## [RUNTIME]
### STATUS
### DELIVERED
### INTERFACES
(Trade Plan object; veto result shape (ALLOW/REDUCE/REJECT + vetoes_applied); ledger writer API + event stream topics/priorities; FSM public transitions; adapter public operations (5) + error mapping table; scheduler entrypoint + stop/restart semantics; trade_plan/outcome/ladder-state table names; PAPER-mode config matrix; CVaR advisory consumption point (for stage-3 producer); ECONOMIC_GATE read surface (for stage-2 checklist screen))
### DATA-CHANGES
(trade_plan, outcome, apex_risk_ladder_state — migration ids; ADR-P2-004 note)
### TESTS
### DEVIATIONS
### OPEN-ISSUES
### HOW-TO-RUN
### REMAINING WORK LEDGER

## [TELEGRAM-OPS]
### STATUS
### DELIVERED
### INTERFACES
(handler entrypoints; callback table; manual smoke procedure for owner; watchdog process launch command; backup/restore commands; README final run block — quote the exact lines; A06 verifies verbatim)
### DATA-CHANGES
### TESTS
### DEVIATIONS
### OPEN-ISSUES
### HOW-TO-RUN
### REMAINING WORK LEDGER

## [RESEARCH]
### STATUS
### DELIVERED
### INTERFACES
(package file format + loader API; governance service API; harness run commands (G-ADAPTER-001, replay-equivalence, NFR))
### DATA-CHANGES
(research-plane tables, logged)
### TESTS
### DEVIATIONS
### OPEN-ISSUES
### HOW-TO-RUN (FINAL ROLE SUMMARY — the complete system boot/run/test surface)
### REMAINING WORK LEDGER (should read `none` at CP-5 exit; otherwise the role is not COMPLETE)
