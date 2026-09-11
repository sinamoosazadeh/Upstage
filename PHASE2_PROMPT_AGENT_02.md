# KICKOFF PROMPT — AGENT-02 — CP-2 FEATURE FABRIC
(Owner: paste this entire file as the first message. Do not modify it. AGENT-02 only. Entry gate: CP-1 boxes checked in PHASE2_CHECKPOINT_STATUS.md; if not, stop and report.)

You are AGENT-02 of the APEX_GEN5 Phase-2 implementation chain (CP-2, Feature Fabric + engine base contract).

## 0. First actions (exact order)
1. Clone `https://github.com/sinamoosazadeh/Upstage`, `git checkout main`, pull.
2. Read IN FULL: `PHASE2_PROTOCOL.md`; `PHASE2_CHECKPOINTS.md` §CP-2; `PHASE2_DECISION_LOG.md` §A; `PHASE2_HANDOFF_CP1.md`.
3. Read blueprint READ SET of CP-2 ONLY (§3.12 full L13529–14382, §3.13, Ch.6, AI.4 L18470–18539, plus targeted §2.2/§2.3 lines your features cite).
4. Consume CP-1 ONLY through HANDOFF_CP1 §INTERFACES; when a signature detail is missing, read the interface surface of the module (def line + docstring), never implementation bodies.

## 1. Mission
Implement the 74-feature Candle Intelligence Mother Layer (§3.12) exactly: full entry template per feature (IDs `APEX.L00.ATOM.CNDL.*.V1` / `...ORGN.CTXT...V1` / `...MOLE.LIQ.SWEEP.STRENGTH.V1` as registered), ATOM/MOLECULAR/ORGANISMIC tiers with the declared caching rules (ATOM never cached; MOLECULAR 5 bars; ORGANISMIC 50+ LRU-100), fixed recomputation schedule, unidirectional flow, decay `exp(-0.02*age)` where declared, universal guards (H<L→QX INVALID, H−L<ε→DEGRADED, open bar→CANDIDATE), ATOM failure stops pipeline. Register all 74 into `apex/data_catalog/catalog.py` through its registration API (no store bypass; feature 49 absent-by-design; feature 56 always UNAVAILABLE). Implement §3.13 completeness as enforced tests. Then freeze `apex/engines/base.py`: the engine base contract per CP-2 scope (streaming on_closed_bar engine lifecycle, idempotent re-apply, superseded/correction hooks per AI.4, evidence-event emission to the Ch.4 24-field `evidence_event` shape, Q-tag attach, versioned interface registry + consumer degradation plumbing, WaveOutError gate helper). Base carries ZERO trading formulas.

## 2. Hard rules for your wave
- Determinism: same inputs + code_revision → byte-identical feature values (Decimal quantization per §2.2; canonical serialization for hashing via CP-1 identity — never reimplement canonical_json/uuid_v7).
- PIT: every feature carries availability_time + snapshot_id; a feature consumed at as_of must satisfy availability≤as_of (test with a deliberate future row → must raise/refuse).
- No zero-substitution anywhere; QX propagates as QX.
- Do not "simplify" the 74 features into shared helpers beyond what §3.12 formulas literally share (e.g., ATR/TR/Wilder utilities live in `apex/data_catalog/math/` per §3.12 module layout, ADR-P2-006).
- Re-derive every numeric example in each feature entry (BTC 100/105/110/98) as a test — computed by your code and asserted against the document's stated value; if the document's illustrative value disagrees with the frozen formula, formula wins and you file an ISSUE (ADR-P2-007 semantics).
- GF_SC_03..12: no implementation (schema assertions only). GF_SC_01/02 belong to AGENT-06 — do not create them.

## 3. Mandatory tests
T-DR-001 (feature tier replay), T-MON-001 (monotonic quality), registry completeness (§3.13: 74==74, unregistered-id enforcement, feature 49/56 rules), tier-cache policy tests, decay formula spot checks, serialization compatibility (canonical round-trip of every tier payload), guard-matrix tests (QX/DEGRADED/CANDIDATE), catalog.get status matrix against CP-1 store, `apex/engines/base.py` contract tests (emit → Ch.4 row validation; idempotent re-apply; correction cascade hook fires). Full suite green via `pytest tests/unit tests/integration -q`.

## 4. Exit sequence (PROTOCOL P16, binding order)
HANDOFF_CP2 (INTERFACES section = complete base.py API + engine-emission contract + feature-id table + consumer matrix; this is the contract all three engine agents will code against — precision here saves the project) → TRACEABILITY CP-2 rows (one per tier-group and per §3.12 clause) → STATUS boxes CP-2 → DECISION_LOG notes (additive files logged: tier packages under apex/data_catalog/) → commit per module `[CP-2][AGENT-02] <module>: <what>` → `git pull --rebase origin main && git push origin main` → ≤10-line chat report. Budget low → RESUME-NEEDED + REMAINING WORK LEDGER (per-feature granularity).

## 5. Prohibitions
No engine formulas (E01–E12 = CP-3), no fabric/pattern/setup (CP-4), no changes to CP-1 frozen behavior except via a logged DECISION_LOG issue + minimal additive extension point you NEED; never rename tree files; never touch `APEX_GEN5.md`/`PROMPT.md`/`AI_SUGGESTION_PLAN.md`/other agents' control sections.
Begin.
