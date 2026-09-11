# APEX_GEN5 — PHASE 2 SALVAGE WORKSHEET (previous attempt: `https://github.com/sinamoosazadeh/APEX_GEN5`, commit 1efe203, 6,707 LoC)

Status: reference inventory produced by plan analysis on 2026-09-12 (full clone read). Consumers: AGENT-01 (foundation rows) and AGENT-02 (engine rows). Rules: this worksheet is NOT a source of truth — `APEX_GEN5.md` is. Every row's disposition must be re-derived by the owning agent against the blueprint ranges cited; adoption of a line without verification is prohibited (G4/G7). Where a salvaged file is adopted, the owning agent moves it to the NORMATIVE tree path, conforms it, and marks the row `ADOPTED-CONFORMED(<commit>)`; where rewritten, `REWRITTEN(reason)`; where the draft is sound, `ADOPTED-AS-IS` is allowed ONLY if the verification evidence (tests) exists in this repo afterward.

## 1. What the previous attempt actually contains (verified facts)

| Path (legacy repo) | LoC | Normative tree target | Pre-audit finding (verified) | Disposition | Owner |
|---|---|---|---|---|---|
| `apex/identity/canonical_json.py` | 204 | same | correct family; but contains a SECOND UUID-like generator (os.urandom clock_seq/node) → violates single-UUIDv7 rule (PHASE 67/67A corrections) | conform: strip any id-generation from this module; keep serialization | A01 |
| `apex/identity/uuid_v7.py` | 71 | same | RFC-9562-shaped, in-tree; add `12-bit rand_a` semantics exactly per contract block | verify vs L4104–4158; adopt after fix | A01 |
| `apex/identity/snapshot.py` | 264 | same | SnapshotBarrier/SnapshotBuilder; check single-envelope rule (no double engine/contract wrap) | verify vs AI.3 + §2.3; adopt after fix | A01 |
| `apex/identity/hashes.py` | 70 | same | SHA-256 utils | verify vs §2.4 lineage fields | A01 |
| `apex/errors.py` | 257 | same | "complete error code hierarchy, 14 canonical vetoes" claimed — must be diffed against Ch.7 table rows and Ch.15 registry names | re-verify line-by-line vs L14643–14671 + L16591–16749 | A01 |
| `apex/config.py` | 210 | same | os.environ only → NO `.env`-file parsing (directive 12 requires stdlib .env parsing); secrets handling present-ish | rewrite loader; keep nine env names exactly | A01 |
| `apex/__init__.py` | 214 | same | frozen constants embedded (Core-10, TFs, Q weights, risk defaults, E11 params) → conflicts with params/*.yaml single-source governance (§9.5: params files are the copy target; "do not re-interpolate") | move values to YAML loaders; __init__ stays thin | A01 |
| `apex/data_catalog/contracts.py` | 456 | same | MarketObservation/CandleFeature/ObservationQuality/EvidenceEvent classes | field-check against Ch.4 DDL columns | A01 |
| `apex/data_catalog/catalog.py` | 193 | same | catalog.get + registration | must match Ch.5 signature/status enum + §3.13 enforcement; registration API for tier modules | A01 |
| `apex/data_catalog/store/sqlite_store.py` | 1156 | same | DDL DIVERGES: tables `market_observations, observation_quality, candle_features, evidence_events, snapshots, parameter_packages, trade_plans, setup_events, decisions, emergency_state, daily_losses, parameter_history` vs blueprint Ch.4/5 canonical set `market_observation, quality_vector, snapshot_pit, evidence_event, pattern_evidence, setup_candidate, ledger, outcome, raw_observation, bootstrap_progress` (with the exact CHECK constraints/PRAGMAs) | REWRITE DDL verbatim to Ch.4+Ch.5 (names, columns, CHECKs, indices); prior invented tables → migration or deletion by A01 with DECISION_LOG entry | A01 |
| `apex/candle_intelligence/registry.py` | 779 | NOT IN TREE — §3.12 places features in `apex/data_catalog/` tier modules; registry content maps to catalog registration | tier enum wrong (MOLECULAR/AGGREGATE/ANALYTICAL/EVIDENCE vs ATOM/MOLECULAR/ORGANISMIC); entries use short F01 names without the canonical `APEX.L00...V1` ids/validity/decay/lineage per §3.12 template; F73/F74 return `None` placeholders; cross-engine note "Requires E02" (boundary leak) | RESTRUCTURE into `apex/data_catalog/{atomic,molecular,organismic,math,performance}` per §3.12 + ADR-P2-006; salvage formula text only where it matches the blueprint's 74 entries | A01 |
| `apex/quality/vector.py` | 323 | same | Q0–QX, 7 components, 4 vetoes claimed | verify every formula/table vs §2.1 L429–733; no placeholder tolerance | A01 |
| `apex/quality/numerical.py` | 376 | same | CONTAINS LIVE PLACEHOLDER: `SMA_V_20 = Decimal("0")  # placeholder` inside volume-ratio path → silently wrong numbers (G4/G9 violation) | REWRITE; two-tier ε per §2.2 exactly | A01 |
| `apex/quality/pit.py` | 413 | same | as_of/windows/MTF states | verify vs §2.3 L899–1099 | A01 |
| `apex/engines/base.py` | 267 | same | EngineBase/StreamingEngine; imports `UuidV7` from canonical_json (double identity path) + imports candle_intelligence (off-tree) | conform to single identity + catalog-only access | A01 |
| `apex/engines/e01_structure/engine.py` | 720 | same | ~13 methods covering williams/gann/merge-prune/gaps/BOS/CHoCH/retest/wick/bias — partial vs §4 reference (~850 LoC of complete pseudocode incl. multi-level BOS matrix, retest full, stats/quality tagging); NO §5 schemas/state machines wiring, NO fixtures | A02 re-audits vs L1205–2789 §3/§4/§5; complete + fixtures + §8 battery | A02 |
| `apex/engines/e02_liquidity/engine.py` | 302 | same | "Simplified VPIN" (explicit G4 violation); no Merton jump-diffusion; no DBSCAN clustering; no salience proximity_HTF | REWRITE vs L2790–3871 (full §3/§4) | A02 |
| `apex/engines/e03_volume/engine.py` | 210 | same | thin; run_full()==run() façade; float-typed internals in places; Phase 67/79/80/88 corrections (availability_time_ms fail-closed, as_of via governed max, volume_sma exposure, structured last_error) NOT evidenced | REWRITE vs L3872–4954 | A02 |
| `apex/engines/e04_volatility/engine.py` | 222 | same | ATR/Parkinson/GK only; spec's fuller framework not covered | REWRITE vs L4955–5601 | A02 |
| `pyproject.toml` | — | same | nine pins present ✓; dev extras add pytest-asyncio (NOT adjudicated — ADR-P2-002 admits pytest only) | A01 adjusts extras; runtime pins untouched | A01 |
| `APEX_GEN5.md` (legacy copy) | 20,551 | n/a | SHA-256-IDENTICAL to Upstage's copy (verified) — so the previous code was built against the same frozen spec | ignore (this repo's copy is canonical) | — |
| ABSENT vs normative tree | — | `apex/bus.py`; `apex/data_catalog/ingest/toobit_public.py`; all six `params/*.yaml`; `requirements.lock`; `README.md`; `tests/unit/`, `tests/integration/`, `tests/fixtures/` (zero test files exist); `__init__.py` for every package; `.gitignore` | these are exactly what made the prior attempt unusable as a "checkpoint" — no evidence layer existed | A01 creates | A01 |

## 2. Honest progress assessment (for the owner's calibration)

Structural reach of the prior attempt ≈ 14 of the tree's 57 named files (24%), but conformance-weighted completion is materially lower: zero tests of 60+ T-ids; DDL/registry/paths deviate from the normative design; several engines are simplified skeletons. Use it as **accelerated drafting** (naming, module shapes, partial formulas) — never as trusted foundation. Re-doing CP-1 from scratch without salvage ≈ 1–1.5× the salvage-audit cost, so salvage is worth exactly that much: speed, not skip.

## 3. Rules for using this worksheet (binding on A01/A02)

1. Clone the legacy repo READ-ONLY into your sandbox (`git clone https://github.com/sinamoosazadeh/APEX_GEN5.git /tmp/legacy_apex` or equivalent); never import it into Upstage's history via copy of commits — copy file content only, inside YOUR own conforming commits, message-tagged `[CP-n][AGENT-nn] salvage(...)` inside the normal commit format (a dedicated trailer line: `Salvaged: <legacy-path> @1efe203`).
2. For each adopted file: (a) re-read the blueprint sections cited in your row; (b) diff behavior clause-by-clause; (c) fix or rewrite; (d) add the proving tests in THIS repo before marking a row `ADOPTED-*`; (e) fill the row's disposition.
3. Any line you cannot conform within budget → REWRITE decision, not a compromise.
4. Legacy `git log`/branches/issues are irrelevant; the only inherited fact is file content at 1efe203.
5. Do not create or push anything in the legacy repository. It stays frozen reference.
