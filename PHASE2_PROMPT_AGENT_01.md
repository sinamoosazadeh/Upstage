# KICKOFF PROMPT — AGENT-01 — CP-1 FOUNDATION
(Owner: paste this entire file as the first message. Do not modify it. This prompt is for AGENT-01 only.)

You are AGENT-01 of the APEX_GEN5 Phase-2 implementation chain (CP-1, Foundation).

## 0. Immediate first actions (exact order)
1. `git clone https://github.com/sinamoosazadeh/Upstage.git && cd Upstage && git checkout main`
2. Read `PHASE2_PROTOCOL.md` IN FULL (it is law; every rule applies to you).
3. Read `PHASE2_CHECKPOINTS.md` section `## CP-1` IN FULL (your scope contract).
4. Read `PHASE2_DECISION_LOG.md` section A (pre-adjudications) — binding.
5. Read your READ SET ranges from `APEX_GEN5.md` as listed in the CP-1 section. Only those ranges. No repository-wide exploration.
6. Begin implementing. You have NO predecessor: do not wait on or consult any handoff.

## 1. Mission statement
Build the complete, production-grade FOUNDATION of APEX_GEN5 per blueprint Chapters 1–2, 4–7, the GLOBAL IDENTITY / PIT UTILITY CONTRACT (L4104–4158), AI.3/AI.5/AI.6/AI.8, and §9.5 execution directives — i.e., the exact normative files: `pyproject.toml`, `requirements.lock`, `README.md` (run skeleton), `.gitignore`, `apex/{__init__,errors,bus,config}.py`, `apex/identity/*` (4 files + __init__), `apex/data_catalog/{contracts,catalog,store/sqlite_store,ingest/toobit_public}(+__init__)`, `apex/quality/{vector,numerical,pit}(+__init__)`, all six `params/*.yaml` with frozen values, plus unit/integration tests listed in CP-1.

## 2. Non-negotiable highlights for YOUR wave (full law = PROTOCOL; do not skip it)
- Blueprint numbers are law: Q_min/Q_raw tables (§2.1), two-tier epsilon (§2.2: floor 1e-12, per-engine EPS, ATR floor 1e-8; E04 ε=1e-12 per GC-D4), snapshot identity = `SHA256(canonical_json(canonical_snapshot_payload))`, UUIDv7 in-tree RFC 9562 with identity-separation rule (UUIDv7 never inside canonical payloads), PIT `as_of = max(availability_time)`, availability_time missing → fail-closed ValueError, `catalog.get` is the ONLY public read path (unknown id → INVALID; future as_of → INVALID; statuses OK/MISSING/STALE/UNAVAILABLE/INVALID), engines never SQL the store, `get_ohlcv` outside `apex/data_catalog` = build-breaking lint (write this lint test), Q_oi STALE weight = 0.5 (0.9 is historical — never use), OI missing → MISSING never 0, requirements.lock = the nine SBOM pins verbatim, pytest = dev-extra only (ADR-P2-002), env names = the nine listed names exactly, parse `.env` stdlib-only, no SHADOW/POSTGRES/withdraw/transfer anywhere, params YAML values copied exactly from §9.5 (do not re-interpolate quality weights).
- Store DDL: verbatim from Ch.4 + Ch.5 (all CHECK constraints, WAL PRAGMAs, indices, `bootstrap_progress` P1–P3 semantics). Single logical DB at `APEX_SQLITE_PATH`.
- Bus: in-process asyncio.Queue only; bounded; P0 synchronous; order preserved (AI.8 + AI.12 Phase-3 rule).
- Toobit public ingest: exactly the public endpoints of the Ch.16 wire block (time, exchangeInfo, quote klines limit 1000, depth, openInterest, fundingRate alert-only |rate|≥0.001); `−1120` → disable that TF for that symbol only; backoff 1/2/4s ×3; timeouts → UNKNOWN, reconcile semantics, no blind resubmit (your public client cannot be blind-retried into duplicates — content_hash dedup per store).
- README: precise Termux install/run/test instructions for what exists after CP-1 (AGENTS 02..09 will not rewrite it; A08 finalizes). One clear run procedure block; APEX_SQLITE_PATH default `data/apex.sqlite3`; never a value of any secret.

## 3. Quality bar (production, not scaffolding)
Every function has: full type hints; Decimal-first numerics with the §2.2 rounding rules; docstrings citing the blueprint section+line; explicit exception types carrying error codes from `apex/errors.py`; no bare excepts; no prints (logging only, with redaction for anything secret-shaped); deterministic behavior; idempotent ingest (content_hash UNIQUE per Ch.5). Tests must be real (no tautologies): include negative tests (NaN/Inf/−0, future as_of, malformed schema, H<L, H−L<ε, missing OI timestamp, oversized klines page, −1120 disable, second-write of same content_hash, catalog INVALID statuses, YAML value equality against §9.5 quoted literals).

## 4. Exit sequence (exactly; PROTOCOL P16)
Fill `PHASE2_HANDOFF_CP1.md` (all headings; INTERFACES must be complete enough that AGENT-02 never opens your file bodies) → fill TRACEABILITY Part III CP-1 rows (one row per contract/formula/param table) → check CP-1 boxes in `PHASE2_CHECKPOINT_STATUS.md` honestly → append any issues to DECISION_LOG §B/CP-1 → run `pytest tests/unit tests/integration -q` (must be green) → commits `[CP-1][AGENT-01] <module>: <what>` → `git pull --rebase origin main && git push origin main` → final ≤10-line chat message (status, commit range, open-issue count, resume flag).
If your token budget runs low: STOP feature work; execute PROTOCOL P16 with STATUS=RESUME-NEEDED and a precise REMAINING WORK LEDGER (file-level, blueprint-anchored); push everything; tell the owner to relaunch this same prompt in RESUME mode.

## 5. Prohibitions
Do not touch: engines, base.py, features, fabric, pattern, setup, playbook, forecast, decision, risk, execution, ledger consumers, scheduler, telegram, ops, research, `APEX_GEN5.md`, `PROMPT.md`, `AI_SUGGESTION_PLAN.md`, others' control sections. Do not create any file outside CP-1 WRITE SET (+ADR-logged .gitignore). Do not "help" later waves with placeholder logic — absent is absent, present is real.
Begin.
