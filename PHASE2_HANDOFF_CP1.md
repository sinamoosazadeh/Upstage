# PHASE2 HANDOFF — CP-1 (Foundation) → consumed by AGENT-02 (+A07/A08 for interfaces)

Author: AGENT-01. Hard cap 400 lines (PROTOCOL P16). Mandatory headings below, in order. Consumers read ONLY: this file + their own prompt + PROTOCOL + CHECKPOINTS section + DECISION_LOG.

## STATUS
(PENDING until AGENT-01 fills: COMPLETE | RESUME-NEEDED | PUSH-BLOCKED + commit range)

## DELIVERED
(path → one-line role → blueprint section satisfied; one row per file)

## INTERFACES
(exact public API: module path, symbol, signature, returns, raises — canonical_json/uuid_v7/canonical_snapshot_id/governed_as_of_ms; errors registry access; bus pub/sub; config keys; catalog.get + registration API; store migration hook API; quality vector entry points (compute_vector, Q_min(tf), veto predicates); numerical helpers (eps tiers, quantize, division guards); PIT helpers; public ingest API; lint-guard usage)

## DATA-CHANGES
(tables + DDL names, PRAGMA set, migration ids, retention mechanics)

## TESTS
(run command; counts pass/fail; per-T-id results row)

## DEVIATIONS
(none expected beyond P5-allowed; list each with ADR ref)

## OPEN-ISSUES
(issue ids from DECISION_LOG CP-1 section, or: none)

## HOW-TO-RUN
(what already runs at CP-1: init commands, tests; nothing more claimed)

## REMAINING WORK LEDGER
(only if RESUME-NEEDED; else: `none`)
