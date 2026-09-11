# KICKOFF PROMPT — AGENT-10 — CP-7 INTEGRATION AUDIT & RELEASE VERIFICATION
(Owner: paste as the first message to the 10th and FINAL coding agent. AGENT-10 only. Entry: every CP-1..CP-6 block DELIVERED and pushed. Exception right of this plan: if a predecessor gate is unchecked, your first deliverable is a REOPEN report — not code.)

You are AGENT-10 (slot 10 of 10; CP-7). You write NO new subsystems. You verify everything, repair only contract violations, and produce the terminal evidence package. Scope = CHECKPOINTS §CP-7 items 1–6, exhaustively.

## 0. First actions
1. Clone `https://github.com/sinamoosazadeh/Upstage`, main, pull.
2. Read IN FULL (they are all small by law): PROTOCOL; CHECKPOINTS (every CP section — you audit against all of them); DECISION_LOG (A + all open issues); ALL seven HANDOFF files; STATUS board; TRACEABILITY Parts I–II.
3. Blueprint read set: Ch.24 L18315–19211 FULL; §9.9 L19212–19400; §9.5 L20128–20247; Ch.7; Ch.16/15 targeted re-verification anchors; Ch.21 §14–15 targeted; Ch.23 targeted.
4. Then — and only now — repository-wide reading rights (you are the sole auditor): `apex/**`, `tests/**`, `params/**`, packaging files, README.

## 1. Audit execution order (each produces written evidence in your report sections)
a. Tree conformance: every §9.5 file at exact path, non-empty, importable; `git log --name-status` proves zero renames/deletions; additive files ↔ DECISION_LOG rows one-to-one.
b. Full-suite run: `pytest tests/unit tests/integration -q` + per-engine §8 batteries + your `tests/integration/test_cp7_release_gates.py` (unified runner encoding AI.10's six fail-closed release rules + the ten cross-checkpoint invariants from CHECKPOINTS tail).
c. Matrix completion: every AI.10 T-id ↔ real test + recorded result in TRACEABILITY Part II (Part I Results column); anything unowned by Part II ownership rows = defect of the owning CP → reopen with a 3-line finding (file, anchor, what's missing), fix yourself ONLY if trivial-and-contract-preserving.
d. Completeness sweep: grep/AST for TODO|FIXME|NotImplementedError|placeholder stubs; `random(`/time.time( in decision paths without determinism discipline; NaN/Inf tolerances in numerics; float money; direct get_ohlcv outside data_catalog; duplicate canonical_json/uuid_v7/snapshot implementations; Wave-Out keywords (withdraw, transfer, flashClose, reversePosition, hedge, CROSS, SHADOW, postgres, Numba, networked bus) absent from runtime paths; `requirements.lock` == nine pins; pyproject dev-extra-only pytest; env-name set exact; ledger single-writer (one instantiation site); E06 no internal SMA/ATR; E11 K=9 everywhere + live-gate default-off; E12 windows canonical; snapshot single-envelope; fixture hashes = real digests; YAMLs == §9.5 frozen values; §9.5-11 numbers asserted in tests; p_raw=0.5 bootstrap + Gates-10/12 LIVE block; leverage min() table; FSM == SL-6 list; `.gitignore` per ADR-P2-013; secrets scan over full history (`git log -p` grep for token/secret shapes — if found: CRITICAL report + rotation notice per §2.5, never silent).
e. §9.9 Execution Readiness Checklists: every checkbox line-by-line against real test results (Phase-0 owner items marked OWNER-PENDING).
f. Gates ledger: each AI.13 G-* → harness file + sandbox result (label SANDBOX-PARTIAL) + owner procedure; statuses strictly OPEN/CLOSED/BLOCKED per ADR-P2-009/010; LIVE_ELIGIBLE/PUBLIC_RELEASE_READY = OPEN by construction.
g. DECISION_LOG triage: every OPEN issue CLOSED-with-evidence or ESCALATED verbatim (owner action list); reopen any CP whose exit boxes were checked falsely (say so bluntly — false-green at CP level is the chain's worst failure mode).
h. Corrective patches: minimal, contract-preserving, own commits `[CP-7][AGENT-10] fix AGENT-nn: <what>`; anything larger = reopen entry + stop (owner decides), never a redesign by the auditor.
i. `PHASE2_FINAL_REPORT.md` completed per its template incl. worded compliance declaration (only what Parts I–III + your sweeps prove).
j. Exit: STATUS CP-7 boxes + board reconciliation; pull --rebase; push; ≤10-line chat report with the owner action list count.

## 2. Behavior under pressure
You are likely the most context-loaded agent in the chain: prioritize evidence-generating commands over reading code bodies; the handoffs + matrix are your map, the test runner is your probe; document findings as you go (append to your report file as you go — if you run out of budget, RESUME mode with a REMAINING-AUDIT LEDGER in the same file; the owner relaunches this prompt in RESUME state).
Begin.
