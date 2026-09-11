# APEX_GEN5 — PHASE 2 DECISION LOG, CONTRADICTION REGISTER & PRE-ADJUDICATIONS

Purpose: the ONLY place where interpretation happens. Agents must (a) read the pre-adjudications before starting, (b) never re-litigate an ADR, (c) file new findings in their own CP section using the issue format, (d) implement the stated interim behavior. Silent resolution of contradictions is a PROTOCOL P13 violation.

Issue format (append under your CP heading):
```
[ISSUE-CPn-xxx] severity: CRITICAL|MAJOR|MINOR | status: OPEN|CLOSED|ESCALATED
  A: "quote" (APEX_GEN5.md Lnnn)
  B: "quote" (APEX_GEN5.md Lnnn)   # the conflicting passage / gap
  Rule applied: <which precedence clause resolved it, or "UNRESOLVED → fail-closed interim">
  Interim behavior: <exactly what the code does now>
  Needs from owner: <decision/measurement, or "none">
```

---

## A. Pre-adjudications ADR-P2-001..014 (binding for all agents; from plan analysis, 2026-09-11)

- **ADR-P2-001 — Repository identity.** PROMPT.md START-EXECUTION cites `sinamoosazadeh/APEX_GEN5`; the actual project repo is `sinamoosazadeh/Upstage` holding `APEX_GEN5.md`. All Phase-2 work, cloning, and pushing targets `https://github.com/sinamoosazadeh/Upstage` only. ("APEX_GEN5 repository" in PROMPT.md §7 means this repo.)
- **ADR-P2-002 — Test tooling.** Runtime deps stay exactly the Ch.1 SBOM (requirements.lock = the nine pins). pytest is allowed as a dev-only extra in pyproject (`tests = ["pytest>=7,<9"]`), never in requirements.lock, never imported by `apex/**` runtime code.
- **ADR-P2-003 — Tree = minimum + canonical.** §9.5 "create every file; do not rename" binds exact names/paths; additional files are permitted only where a blueprint chapter requires them (fixtures, tests, tier modules, ops/research additions, __init__.py), and each must appear in the agent's handoff DELIVERED table + a one-line note here under that agent's CP.
- **ADR-P2-004 — Emergency-ladder persistence.** Ch.1 L1–L5 + Ch.23 require persisted ladder state, but Ch.4 DDL has no such table. Resolution: AGENT-07 adds `apex_risk_ladder_state` (append-only revisions; single-writer via ledger queue) as a migration entry; frozen semantics = ratchet-only (RSK-ERR-506). No new operational states may be introduced beyond L1–L5 + the existing DEGRADED/RECOVERY_REQUIRED vocabulary.
- **ADR-P2-005 — Packages absent from the tree.** Research/ops support modules (backtest/optimizer/promotion; deploy scripts) are AI.12 Phase-8/9 deliverables with no tree entries: created as `apex/research/**`, `scripts/**` (new paths only — not renames), logged here by AGENT-09/08. The normative tree files remain the contract surface.
- **ADR-P2-006 — §3.12 "module layout" vs flat tree.** Tree wins for its named files (`contracts.py`, `catalog.py`, `store/sqlite_store.py`, `ingest/toobit_public.py`); the tier packages (`atomic/`, `molecular/`, `organismic/`, `math/`, `performance/`) are added UNDER `apex/data_catalog/` exactly as §3.12 names them. No duplicate catalog module: registration flows through the single `catalog.py` public API.
- **ADR-P2-007 — Illustrative hashes/values.** E01 §8.1 FIX_001 hash `e3b0c442…` is the empty-string SHA-256 (a placeholder of record); all engines' §9 case-study numbers are illustrative per §9.5-2. Agents construct fixtures, re-derive expected values from formulas, and compute REAL hashes after fixture creation (no-hash rule). Never copy a document hash or case value into code as truth.
- **ADR-P2-008 — E11 YAML vs §6 tension.** `params/e11_params_v4.yaml` values are §9.5-canonical (K:9, θ_H:0.65, λ_ewma:0.94, hyst 3, dirichlet 0.1, delay 48, W=4320). Engine §6 tables govern formula internals/sensitivity. If AGENT-05 finds a real numeric conflict between §6 and the YAML, the YAML value loads at runtime, the conflict is filed [ISSUE-CP3-*] and the engine chapter's formula semantics are otherwise untouched (preamble rule).
- **ADR-P2-009 — v2/v3 adapter conformance without legacy data.** This repo contains no v2/v3 code or datasets; G-ADAPTER-001's "100 legacy samples" cannot be sourced without fabrication. Resolution: AGENT-09 implements the adapter INTERFACES (AI.2 adapter column, read-only, no state mutation) + a conformance harness operating on any user-provided legacy export + synthetic v4-derived self-checks. The real-data gate remains OPEN/UNVERIFIED for the owner (recorded, never faked).
- **ADR-P2-010 — NFR/device measurements.** T-NFR-001..004 and G-CAPACITY/G-TOOBIT/G-PAPER require the owner's device/live market. Agents deliver executable harnesses and run what is runnable in-sandbox; results in-sandbox are labeled `SANDBOX-PARTIAL`; `TARGET-DEVICE` rows stay OPEN until owner measurement (AI.13 status vocabulary: OPEN/CLOSED/BLOCKED only).
- **ADR-P2-011 — Dangling "Chapter 5, SL-N" citations.** §9.9/R.3 cite an older "Chapter 5 (SL-0..SL-15)" contract registry. Resolution: each SL-n contract's content IS defined in its owning runtime chapter — SL-1 Evidence/Context Fabric (Ch.8), SL-2 conflict/monotonicity (Ch.8 §8.1), SL-3 forecast (Ch.13), SL-4 capital ceiling (Ch.19 + Ch.15), SL-5 Canonical Risk Veto Registry (Ch.15), SL-6 execution FSM/adapter/ledger (Ch.16), SL-7 divergence transport (Ch.8/9), SL-8 MTF (Ch.8 §8.3), SL-9 semantic levels Feature→…→Strategy (Ch.6/8/9/10/11/12 ladder), SL-10 evidence-event bus (Ch.4 + AI.12), SL-11 redundancy (Ch.8/§10 redundancy rule), SL-12 parameter governance (Ch.17), SL-13 shared validation battery (Ch.18 §18.4), SL-14 evidence lifecycle/quality resolution ladder (Ch.8 §8.0 + Ch.2 §2.1), SL-15 case-study discipline (Ch.16 §/§9.5-2). Never invent content to fill a dangling SL reference; cite the owning chapter.
- **ADR-P2-012 — Single-branch baton chain.** All slots push to `main` with pull-rebase; parallel slots keep disjoint paths so rebase never conflicts except on control files (append-merge rule P14). No feature branches are used; history linear-ish by discipline. If the owner prefers branch-per-agent + PR review, it is an operational variant only — path ownership and handoff duties are unchanged.
- **ADR-P2-013 — Runtime data & hygiene.** `.gitignore` (created by AGENT-01): `data/`, `*.sqlite3*`, `.env`, `__pycache__/`, `.pytest_cache/`, chart artifacts (none expected — in-memory rule), `dist/`, `build/`. DBs and `.env` never enter git; nothing else may be added to `.gitignore` by later agents without a log note.
- **ADR-P2-014 — Fixture canonicality split.** Engine §8 golden fixtures (FIX_*) are engine-canonical; §9 case studies are illustrative; GF_SC_01/02 shapes are Ch.9-canonical but their bar arrays must be constructed by AGENT-06 (source has none — PHASE 79/C-3 record); GF_SC_03..12 exist only as schema assertions (Wave-Out). Tests must assert shape+semantics for 03..12 and full behavior for 01/02.

## B. Open issues (agents append under their CP; owner reads this on every verification)

### CP-1
(none yet)
### CP-2
(none yet)
### CP-3
(none yet)
### CP-4
(none yet)
### CP-5
(none yet)
### CP-6
(none yet)
### CP-7 (triage ledger — A10 writes final dispositions here)
(none yet)
