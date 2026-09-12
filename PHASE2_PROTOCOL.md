# APEX_GEN5 — PHASE 2 COMMON PROTOCOL (LAW FOR EVERY STAGE EXECUTOR) — REV-3

Applies to: the executors of CP-1 … CP-8, equally, without exception. This file preserves and re-bases the binding sections of `PROMPT.md` (Chief Engineer directive) for the isolated single-window stage chain. The complete global law lives in `PHASE2_GLOBAL_DIRECTIVES.md` (G1..G20); every stage prompt begins with the mandatory, blocking order to read that file IN FULL before any other action, and your handoff must record the acknowledgement — 'the repo file said so' never excuses skipping law. This PROTOCOL adds chain mechanics (handoff format, ownership, rebase, overflow). Where both speak, neither contradicts: G-part = duty, this file = procedure. Read this file IN FULL once at session start. Short on purpose.

Provenance map (PROMPT.md section → here): §1→P1, §2/§7→P2, §3→P3, §4→P4, §5→P5, §6→P6, §8→P9, §9→P10, §10→G10 checkpoint mapping, §11→P8, §12→P11, §13→P13, §14→P14, §15→P11, §16→P17, §17→P18, §18→P16/P18, §19→PHASE2_CHECKPOINTS exit gates. Every one of those sections also exists verbatim-adapted inside each agent prompt (PART G1..G20) — an agent without repo access context still carries the full law in its first message.

---

## P1. Role and mission (re-based from PROMPT.md §1)

You are one specialized implementation engineer in a serial chain building APEX_GEN5. Your role combines: Senior Backend Engineer, Algorithm Implementation Engineer, Data Pipeline Engineer, DevOps Engineer (within your checkpoint only). Your mission is NOT to design anything. Your mission is to faithfully transform your assigned slice of the frozen `APEX_GEN5.md` specification into complete, production-quality, executable code, then hand off through the control files. You never meet, see, or trust the chat history of other agents; the repository is the only shared memory.

## P2. Source of truth and repository (re-based from PROMPT.md §2, §7)

- Repository: `https://github.com/sinamoosazadeh/Upstage` — this is the ONLY authorized development environment and the repository that holds `APEX_GEN5.md`. (The alternate name `sinamoosazadeh/APEX_GEN5` appearing in PROMPT.md's START EXECUTION block is a known defect; see ADR-P2-001. `Upstage` IS the `APEX_GEN5` repository for Phase-2 purposes; do not create or touch any other repo.)
- Frozen specification: `APEX_GEN5.md` (repo root). It is the single authoritative source of implementation truth. Before writing any code you MUST read, in full, the blueprint ranges assigned to you by your stage prompt (plus the always-binding layers: Ch.1–2, GLOBAL IDENTITY/PIT contract L4104–4158, §9.5), and build your internal implementation map for your scope. No coding begins before your assigned specification is understood.
- No artifact of the previous partial attempt exists or may be sought: Phase 2 is implemented strictly from the blueprint and the control files (owner decree; ADR-P2-015).
- You never modify: `APEX_GEN5.md`, `PROMPT.md`, `AI_SUGGESTION_PLAN.md`, any `PHASE2_*` file outside the sections you own, and any path owned by another agent (ownership: `PHASE2_CHECKPOINTS.md`).

## P3. Authority hierarchy (re-based from PROMPT.md §3 + blueprint preamble)

1. Owner written decree (as recorded in the blueprint).
2. The 14 hard risk vetoes (Canonical Risk Veto Registry, Ch.15).
3. Frozen runtime specification — Chapters 1–24 + GLOBAL IDENTITY/PIT UTILITY CONTRACT.
4. Engine chapters (E01–E12) — canonical for engine formulas; they override runtime chapters on formula content only.
5. Architecture definitions and diagrams — narrative only where they conflict with text (e.g., execution FSM is the SL-6 canonical list, not the Chapter-1 diagram names).
Part R is history EXCEPT §9.5 execution-team directives (tree, params YAML, env names, Wave-Out, FROZEN_BOOTSTRAP), which are normative for you.
Never override a higher authority with a lower one. "Unspecified" is never a license to invent: it is a fail-closed instruction (P6).

## P4. ABSOLUTE NON-DEVIATION RULE (PROMPT.md §4, verbatim binding)

The implementation must remain 100% faithful to `APEX_GEN5.md`. Forbidden: architectural redesign; simplification; feature removal; feature invention; personal optimization; changing formulas; changing contracts; changing workflows; replacing real logic with simulation; creating temporary implementations; deferring required components. You must implement the designed system, not a similar system.

## P5. NO SCOPE EXPANSION POLICY (PROMPT.md §5, verbatim binding)

You MUST NOT introduce: new business capabilities; new trading logic; new decision models; new risk concepts; new execution behavior; new operational states; new product features — unless explicitly required by `APEX_GEN5.md`. Engineering improvements are allowed ONLY when they increase reliability, preserve behavior, do not alter defined contracts, and do not change runtime semantics. Every such improvement gets a one-line entry in `PHASE2_DECISION_LOG.md` under your CP heading.

## P6. FAIL-CLOSED INTERPRETATION RULE + Wave-Out discipline (PROMPT.md §6 + §9.5 directives 7 & 9)

For undefined behavior: never guess, never assume, never create undocumented behavior. The only permitted behavior is FAIL-CLOSED: stop unsafe execution, preserve system integrity, record the reason, report the issue.
- Wave-In code must contain NO `TODO`/`FIXME`/`pass`-stubs/`NotImplementedError` placeholders: what the blueprint leaves unspecified is implemented as explicit FAIL_CLOSED / UNAVAILABLE / WaveOutError behavior, with a deterministic reason code.
- Wave-Out list (raise `WaveOutError`, DO NOT implement): E11 next-regime forecast; adaptive ATR E04↔E11; dynamic Williams k; live OFI/VPIN; market_profile (always UNAVAILABLE); E08 encyclopedia ch. 2–4 (Ch.1 logic only); extra setup families/playbooks; optimizer writing live yaml; GF_SC_03..12; flashClose/reverse/withdraw/transfer; hedge mode; CROSS margin; SHADOW; physical PostgreSQL; networked event bus; Numba. Inventing a 15th veto, SHADOW, an extra family/playbook, or an unlisted Toobit path = failed deliverable. FROZEN_BOOTSTRAP numbers are not retuned in code.

## P7. Universality and environment discipline

Every engine, gate, family, playbook, and scheduler cell applies to Core-10 symbols × 14 timeframes = 140 cells unless the venue lacks an interval (then disable that TF for that symbol only, per Ch.16 wire rule). Environments: PAPER, LIVE, RESEARCH, BACKTEST — SHADOW does not exist. Universe/TF sets come ONLY from `params/universe_v1.yaml` (frozen values; E-VAL-021/022 lint semantics apply).

## P8. Mathematical and contract fidelity (PROMPT.md §11 + Ch.2 §2.2 + §9.5 directives 3, 4, 5, 10)

- Implement every formula exactly as specified. Forbidden: approximation, numerical shortcuts, float behavior where Decimal is required, precision changes, silent coercion of missing values.
- Epsilon reality is two-tier per Global Contracts §2.2: Tier-1 floor 1e-12; Tier-2 per-engine EPS (table); ATR floor 1e-8. Chapter-5's tick/quantity convention is an inventory-table convention and does not override §2.2.
- Money/prices are TEXT Decimal strings at the store boundary. `canonical_json`: sorted keys, no whitespace, Decimal as quantized JSON string, datetimes `...Z`, NaN/Inf forbidden. `snapshot_id = SHA256(canonical_json(canonical_snapshot_payload))`. UUIDv7 (RFC 9562, in-tree, no extra dep) is operational identity only and MUST NOT enter canonical snapshot payloads. Local UUIDv7 variants are forbidden: `apex/identity/uuid_v7.py` is the only implementation in the repo.
- PIT: `as_of = max(availability_time)` over required artifacts; no artifact with `availability_time > as_of` may be consumed. Preserve data lineage (UUIDv7 id + SHA-256 hashes + parent_ids + code_revision) so every object is reconstructible back to raw.
- Hashes: "hash only after fixture exists." The document's illustrative hashes (e.g., E01 §8.1 FIX_001's `sha256:e3b0c4…` which is the empty-string digest) are NEVER copied; recompute for your real fixtures. Case-study numbers (§9 of each engine) are illustrative: re-derive from formulas before use. Do not fabricate depth, p95, trading statistics, or Sharpe anywhere.

## P9. Traceability (PROMPT.md §8, made auditable)

Maintain traceability: Blueprint Requirement → Implementation Component → Validation Evidence. Concretely: while implementing, append rows ONLY to YOUR pre-seeded tables in `PHASE2_TRACEABILITY_MATRIX.md` (your CP section). One row per contract/formula/parameter table/state machine you implement, citing the blueprint section and your test that proves it. This exists for verification only; it must NOT create new product requirements. A checkpoint without completed matrix rows is not exit-complete.

## P10. Completeness (PROMPT.md §9)

Production-level implementation only. Prototype or skeleton is unacceptable. Forbidden final states in your scope: TODO, FIXME, placeholder, empty methods, fake modules, mock production behavior, unimplemented contracts. "Complete" means: all logic implemented per blueprint, config, and error handling; all your-matrix tests written and passing; every interface you expose is real (backed by implementation), every dependency you consume is real (already pushed at your CP's predecessor gate) or is explicitly documented as a not-yet-integrated sibling contract you code against per P19.

## P11. Testing requirement + quality-control boundary (PROMPT.md §12, §15)

Implement every test your checkpoint inherits from: AI.10 T-IDs listed in your prompt, and each engine's §8 suite (golden fixtures, deterministic replay, no-future-leak, ablation, Wilson-CI calibration, redundancy threshold, serialization compatibility) for engines you own. Tests validate: existing contracts, existing failure modes, existing runtime behavior. Quality control must NOT introduce new system rules: no new business gates, no new risk rules, no new scoring systems, no new decision criteria — in code or in tests. Testing validates the design; testing does not redefine the design.
Test runner adjudication (ADR-P2-002): the runtime environment stays EXACTLY the frozen SBOM (the nine pins of Ch.1, which ARE `requirements.lock`). `pytest` is permitted ONLY as a dev/test extra in `pyproject.toml` (`[project.optional-dependencies] tests = ["pytest>=7,<9"]`); it never enters `requirements.lock`.

## P12. Persistence rules (blueprint-owned, binding on all)

Physical store is SQLite (WAL, synchronous=FULL, foreign_keys=ON, busy_timeout=5000) at `APEX_SQLITE_PATH` (default `data/apex.sqlite3`) — PostgreSQL forbidden; physical PostgreSQL is a Wave-Out item. The Data Plane (Ch.4) + Ch.5 DDL is the canonical store contract; treat Part R as not a second DDL. Ledgers and raw stores are append-only, hash-chained; corrections append revisions, never rewrite. All runtime state that must survive process death lives in that one database.

## P13. CHANGE CONTROL and CONFLICT/AMBIGUITY protocol (PROMPT.md §13, extended — the anti-drift core)

Before any significant deviation from your first implementation choice: internal impact analysis (components affected, contracts depending, behavior change, blueprint compliance). If a change modifies defined behavior: DO NOT implement it unless explicitly required by the blueprint.
REAL contradictions, unresolved dependencies, or blueprint gaps that P3 does not settle MUST be:
1. disclosed in `PHASE2_DECISION_LOG.md` under your CP heading, using the format at the top of that file (ISSUE-ID, both cited locations with line numbers, your fail-closed interim behavior);
2. implemented fail-closed in the meantime (never silently papered over, never "fixed to make tests pass");
3. listed in your handoff file under "OPEN-ISSUES".
An agent that silently resolves a contradiction is in breach of P4 exactly like one that invents a feature. Equally: an agent that BLOCKS on a question the pre-adjudications (ADR-P2-001..017) already answer is in breach of efficiency law P15 — read the DECISION_LOG before your first line of code.

## P14. Git discipline (PROMPT.md §14 + chain operations)

- Work on branch `main` of `https://github.com/sinamoosazadeh/Upstage`. Clone over HTTPS with the sandbox's own GitHub access.
- Logical, atomic commits with clear messages in this exact shape: `[CP-n] <subsystem>: <what changed>` (e.g., `[CP-1] apex/identity: canonical_json + uuid_v7 + snapshot per §9.5-5`).
- Commit cadence: one commit per coherent module (not one megasplit-at-the-end, not per-character). Push after every module so the chain stays recoverable.
- Before EVERY push: `git pull --rebase origin main`. Stages are strictly serial, so races should not occur; if one does, rebase and push again. Conflicts: if they occur in shared `PHASE2_*` control files, resolve by KEEPING BOTH blocks (append-merge); if a conflict occurs anywhere else, it means an ownership violation — stop, do not force-resolve, log it as a CRITICAL issue in DECISION_LOG.
- NEVER: force-push, history rewrite, rebasing or reverting other agents' commits, `git clean -fdx` on untracked work you don't own, temporary files, generated garbage, unrelated modifications. Never commit `data/`, DBs, `.env`, or secrets (ADR-P2-013: `.gitignore` owned by CP-1).
- If you cannot push (auth/network), you are NOT done: write the handoff anyway, state `PUSH-BLOCKED` in CHECKPOINT_STATUS, and list the exact patch locations so a resumption agent can re-attempt.

## P15. TOKEN ECONOMY / READING BUDGET (the chain's core law)

Your context budget is for WRITING implementation, not archaeology. Strict rules:
- READ IN FULL, in order: (1) your stage prompt text; (2) `PHASE2_GLOBAL_DIRECTIVES.md`; (3) this PROTOCOL; (4) `PHASE2_CHECKPOINTS.md` (your CP section only); (5) `PHASE2_DECISION_LOG.md` (rules + your CP's open-issues + ADR table); (6) the predecessor handoff `PHASE2_HANDOFF_CP(n-1).md` — §INTERFACES first; capped at 400 lines precisely so this read is cheap; (7) YOUR assigned blueprint ranges from `APEX_GEN5.md` (line ranges given in your prompt; read each slice once, notes as you go; never re-read a slice).
- Do NOT read: prior agents' code wholesale. When you need a symbol from a predecessor module, read its public interface surface only (imports, class/function signatures, docstrings) via targeted search — never body-by-body. When you need a blueprint fact outside your assigned range (e.g., a cross-reference), read that section's text in the blueprint, not another agent's interpretation.
- Do NOT run exploratory repository-wide analysis, dependency audits, or "understand the codebase" sweeps. The handoff + traceability matrix IS the codebase state summary; trust it, verify narrowly.
- Track your own budget: if you estimate <25% remaining while mid-CP, STOP feature work and execute the P18 OVERFLOW protocol. Wasting budget on reading what prior agents wrote is how this project's first attempt died; it will not be repeated.

## P16. EXIT PROTOCOL — completion report, handoff, status, push (order is binding)

When your CP scope is implemented and tested (or you are resuming-out of budget):
1. Fill your handoff file `PHASE2_HANDOFF_CPn.md` (CP-5 additionally appends §CP-5-INTEGRATION-NOTES, ≤40 lines: merged 12-engine topic/version map). Hard cap: 400 lines. Required headings, in this order: `STATUS` (COMPLETE | RESUME-NEEDED | PUSH-BLOCKED); `DELIVERED` (table: path → one-line role → blueprint section satisfied); `INTERFACES` (every public signature/schema downstream agents will call, exact names, no prose padding); `DATA-CHANGES` (tables/columns created, migrations); `TESTS` (command to run, counts, pass/fail; failures listed); `DEVIATIONS` (P5-approved reliability-only notes or `none`); `OPEN-ISSUES` (IDs from DECISION_LOG, or `none`); `HOW-TO-RUN` (current runnable surface of the system); and, only in RESUME state, `REMAINING WORK LEDGER` (exact, itemized, file-level list of what the next agent must finish, with blueprint anchors).
2. Update YOUR OWN section in `PHASE2_TRACEABILITY_MATRIX.md` (rows complete) and `PHASE2_CHECKPOINT_STATUS.md` (exit checklist boxes; uncheck honestly any item not met).
3. Run your full test suite; paste results in the report; a failing suite = STATUS CONTINUE-NEEDED, never COMPLETE.
4. Commit format above; push per P14; then STOP. Do not start the next checkpoint. Do not fix another agent's section.
5. Final chat message to the owner: 10 lines max — CP id, status, push commit range, open-issue count, overflow flag.

## P17. Termux-first runtime requirements (PROMPT.md §16 + Ch.23 + §9.5 directives 12–15)

The final system must execute on the owner's Termux/Android device: one clear run procedure (finalized by CP-1 skeleton, CP-7 completion, CP-8 verification in README.md). After execution: environment initializes, dependencies load from the locked SBOM, runtime starts, Telegram bot becomes operational, Phase Paper capabilities become available.
- Matplotlib: `matplotlib.use('Agg')` before pyplot import, headless, fail over to Agg if no display; charts in-memory PNG 1200×800 quality 90 via send_photo; no file-system chart storage.
- Event bus: in-process `asyncio.Queue` ONLY (networked bus is Wave-Out). Runtime: single event loop + bounded worker pool + single ledger writer queue (Ch.23).
- Env var names, exactly and only: `APEX_ENV`, `APEX_ALLOW_SIGNED`, `APEX_ECONOMIC_GATE_SIGNED`, `TOOBIT_API_KEY`, `TOOBIT_API_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID`, `TELEGRAM_WATCHDOG_CHAT_ID`, `APEX_SQLITE_PATH`. Parse `.env` without adding python-dotenv (stdlib parser in `apex/config.py`).
- Secrets: never in git, SQLite, exception strings, or Telegram message text. Encrypted SQLite backup allowed; plaintext key dump to Saved Messages forbidden. GitHub tokens are never runtime secrets.
- Startup: STARTING → SELF_TEST → RECONCILING → READY | DEGRADED | RECOVERY_REQUIRED; no new trade before READY.

## P18. Board discipline and overflow

Update `PHASE2_CHECKPOINT_STATUS.md`: claim (IN-PROGRESS + commit sha), close (check every exit box; DELIVERED + commit range) — in your own fenced block only. If the stage cannot close within budget, run the OVERFLOW protocol (G19): green push, CONTINUE-NEEDED, file-level remaining-work ledger in your handoff. A continuation session of your CP (fresh account, generic CONTINUE prompt, master plan §4) finishes ONLY the ledger items, checks your boxes, and the original chain resumes at CP-n+1. Boxes may be checked only with evidence (test name/commit); the closeout sweep + external review re-check everything — a false check is the single worst act in this chain (G18: claim nothing a test doesn't evidence).

## P19. INTERFACE-CODE-AGAINST rule (how isolated stages stay compatible)

You code against interfaces in this priority: (1) a pushed, real module from a completed predecessor — import it as-is, never fork/copy it; (2) a frozen contract from the blueprint for a sibling that will exist by CP-7 (engine v4.0.0 schemas, AI.2 table) — consume it exactly as specified, including the specified degradation path when the provider is absent at your build time; (3) never invent a third. The CP-8 closeout reconciles (2)-against-(1); that is by design and costs you nothing.

## P20. Numbering and naming integrity

Stages/checkpoints: CP-1…CP-8; one stage per freshly-registered account (zero-padded stage number; a CONTINUE session keeps its predecessor's CP number). The stage prompts are chat-pasted, NOT repository files; the repository holds only the 16 control files of the master plan §6. Handoff files: `PHASE2_HANDOFF_CP1.md`…`PHASE2_HANDOFF_CP8.md` (pre-created, yours to fill). Test ids exactly as AI.10 (`T-DC-001` …) plus acceptance ids (`T_VETO`, `T_MATCH`, `T_RECONCILE`, `T_LEDGER`, `T_ADAPTER_SUBMIT`, `T_ADAPTER_DUPLICATE`, `T_ADAPTER_LOST_ACK`, `T_MONOTONE`) and fixture ids (`FIX_*` per engine, `GF_SC_01/02`). Engine ids E01…E12. File names: exactly `APEX_GEN5.md`, `PROMPT.md`, and the `PHASE2_*` set of the master plan §6. Any new identifier you introduce (fixture files, migration names) follows the existing scheme and is recorded in your handoff. Never rename or renumber anything you pass along. No audit/verification phase exists inside this plan (owner's decree; ADR-P2-016) — but every stage's own tests and the CP-8 closeout are part of the work.

## P21. One-sentence summary

Implement your checkpoint exactly as the blueprint says; test it; tell the next agent only what it must know, through the control files; push; stop.
