# PHASE2 HANDOFF — CP-3 → consumed by CP-4 (and CP-8 closeout)
Stage: CP-3 — Engines E04 Volatility, E05 FVG, E06 OrderBlock
Rules (PROTOCOL P16): author = CP-3 executor (or its continuation session — state which, first line of STATUS). ≤400 lines, nine headings below in order. Successors read ONLY this file + their own prompt/law/checkpoint sections; interfaces listed here are the public contract they may code against. First STATUS line: `LAW-ACK: G1..G20 + P1..P21 read <UTC>`.

## STATUS
(complete / CONTINUE-NEEDED+ledger-ref; commits pushed; suite totals: x passed/y failed; environment note incl. python/OS)

## DELIVERED
(file | purpose | blueprint section | rows into MATRIX Part III)

## INTERFACES
(module | class/function | signature | semantics | version) — exhaustive for everything CP-4 consumes; nothing invented, everything cited.

## DATA-CHANGES
(tables/columns/migrations created or altered; if none: "none")

## TESTS
(test file | ids covered | result) — one row per delivered component; ids exactly as AI.10/§8/acceptance names.

## DEVIATIONS
(only pre-adjudicated ADRs applied, each as `ADR-P2-0NN applied: <where>`; otherwise: none — silent deviation is a breach (G4))

## OPEN-ISSUES
(exact [ISSUE-CP3-0NN] format from PROTOCOL P13; mirrored to DECISION_LOG §B/CP-3; or "none")

## HOW-TO-RUN
(exact commands to use THIS increment: install, run tests, demo entry; copy-pasteable, nothing implied)

## REMAINING WORK LEDGER
(none — stage fully closed / otherwise per-file table: remaining items | blueprint ranges to read | interface contracts already emitted | estimated lines; CONTINUE-NEEDED set on the board when non-empty)
