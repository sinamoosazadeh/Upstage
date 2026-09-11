# KICKOFF PROMPT — AGENT-09 — CP-6b RESEARCH PLANE & PARAMETER GOVERNANCE
(Owner: paste as the first message to the 9th coding agent. AGENT-09 only. Entry: CP-1..CP-5 checked+pushed. CP-6a independent — do not wait for, read, or import Telegram code.)

You are AGENT-09 (slot 9 of 10; CP-6b). Scope = CHECKPOINTS §CP-6b items 1–8, complete.

## 0. First actions
1. Clone `https://github.com/sinamoosazadeh/Upstage`, main, pull.
2. Read: PROTOCOL, CHECKPOINTS §CP-6b, DECISION_LOG §A (ADR-P2-005/009/010/014), HANDOFF_CP5 (all), HANDOFF_CP4 targeted (family registry hooks), HANDOFF_CP1 §INTERFACES (params/catalog/store).
3. Blueprint read set: Ch.17 L16937–17022; Ch.18 L17023–17356; Ch.20 L17446–17561; Ch.11 L15750–15859 (X.6–X.8 as optimizer parameter catalog); Ch.13 AG rows you bind (16462–16517 targeted); AI.12 Phase-7/9 + AI.13 G-ADAPTER/G-CAPACITY/G-PAPER rows; Ch.1 L370–399 (parameter dependency graph); §9.5-9 (optimizer-live-yaml ban).

## 1. Precision list
Governance service: parameter classes per Ch.17 (frozen/governed/research), change-proposal lifecycle, versioned ParameterPackage objects (id via identity utils, validity window, drift watch >10% auto-rollback), bound to snapshot lineage; params/*.yaml are bootstrap inputs and IMMUTABLE at runtime (enforce + test file-hash watch).
Backtest/walk-forward/stress: reuse the CP-5 scheduler code path (determinism not duplication — a parallel engine IS a deviation); stress battery per §18.4 incl. named cases (zero-volume, OI-stale, gap≥10×ATR, crash/flash); Wilson CI + SPRT numerics implemented per Ch.18 §Z exactly (z-quantile, floor accumulation, shrinkage, pooling rule Z.2, sampling unit = family per AD.1; live-loser SPRT halt automatic; demotion OWNER-confirm — you expose the confirm-state surface consumed by A08 screens, never a Telegram import).
Dual optimizer per W.1–W.9: objectives verbatim; W.3 exhaustive-grid within declared budgets; nightly 03:00–05:00 UTC + continuous-run flag via config/bus events; W.5 RED-LINE validator (any package touching vetoes/caps/circuit-breakers/owner ceilings → rejected at validation BEFORE paper — implement as first-touch check); live yaml NEVER written (Wave-Out; test asserts immutability); W.6 bootstrap 3 phases against bootstrap_progress (cursor, pause/resume, DEEP 2020→2026 config); W.7 estimates surfaced as projections labeled UNVERIFIED.
Monte-Carlo: weekly CVaR_95 1000 paths producer, records computation+window+assumptions, emits advisory input consumed by risk (interface from HANDOFF_CP5); "addition never replacement" enforced at your emission (advisory-only channel).
Promotion: T-PKG-001 idempotent version-locked injection; UNPOOLED rows never promotable (construction + tests); "no populate until real evidence" invariant: promotion writes a result only from stored hash-bound evidence artifacts.
Liquidity proxies AA: registry as data (38 concepts + 6 rejected), L2/L3 degrade UNAVAILABLE per class, rejected concepts absent from code (grep test), AA.6 symmetry (no symbol tiering anywhere), AA.7 performance rules (no synthetic stats).
Legacy adapters per ADR-P2-009: interfaces + read-only translators (AI.2 adapter column), conformance harness accepts owner-provided legacy exports, self-check mode on v4-derived synthetic inputs, G-ADAPTER-001 recorded OPEN/UNVERIFIED; T-AD-002 cache-discard-on-code_version test.
G-PAPER harnesses: 10-day deterministic replay harness + 5-day live-paper observation harness runnable by owner (A08 ops surface executes on-device); results labeled honestly (A09 sandbox partial = `SANDBOX-PARTIAL` at most).

## 2. Files/exit
WRITE SET per CHECKPOINTS §CP-6b incl. ADR-P2-005 log note. Tests: T-AD-001/002, T-PKG-001, red-line rejection suite, Z.8 worked example re-derived, determinism double-run, bootstrap resume, CVaR boundary, proxy registry completeness, YAML immutability. Exit (P16): HANDOFF_CP6 §[AGENT-09] (package format + loader API explicit) → STATUS → issues → pytest → `[CP-6][AGENT-09]` commits → pull --rebase + push → ≤10-line report. RESUME splits: governance / backtest+stress / optimizer+bootstrap / promotion / proxies / adapters.
Begin.
