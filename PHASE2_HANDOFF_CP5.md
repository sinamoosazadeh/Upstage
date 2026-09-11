# PHASE2 HANDOFF — CP-5 (Forecast→Decision→Risk→Execution→Ledger→Scheduler + Economic Gate logic) → consumed by AGENT-08, AGENT-09, AGENT-10

Author: AGENT-07. Hard cap 400 lines.

## STATUS
## DELIVERED
## INTERFACES
(Trade Plan object; veto result shape (ALLOW/REDUCE/REJECT + vetoes_applied); ledger writer API + event stream topics/priorities; FSM public transitions; adapter public operations (5) + error mapping table; scheduler entrypoint + stop/restart semantics; trade_plan/outcome/ladder-state table names; PAPER-mode config matrix; where the CVaR advisory input is consumed (for A09 producer) and where ECONOMIC_GATE state is read (for A08 checklist screen))
## DATA-CHANGES
(trade_plan, outcome, apex_risk_ladder_state — migration ids; ADR-P2-004 note)
## TESTS
## DEVIATIONS
## OPEN-ISSUES
## HOW-TO-RUN
## REMAINING WORK LEDGER
