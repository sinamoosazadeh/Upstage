# KICKOFF PROMPT — AGENT-03 — CP-3a ENGINES E01–E04
(Owner: paste as the first message to the 3rd coding agent. AGENT-03 only. Entry: CP-1 & CP-2 boxes checked. If CP-3b/3c already pushed (out-of-order start), rebase and proceed — your files are disjoint.)

You are AGENT-03 (slot 3 of 10; CP-3 partial: engines E01 Structure, E02 Liquidity, E03 Volume/Participation, E04 Volatility).

## 0. First actions
1. Clone `https://github.com/sinamoosazadeh/Upstage`, checkout main, pull.
2. Read: `PHASE2_PROTOCOL.md` (full), `PHASE2_CHECKPOINTS.md` §CP-3 (shared part + your anchors), `PHASE2_DECISION_LOG.md` §A (esp. ADR-P2-007/008/014), `PHASE2_HANDOFF_CP2.md` (base.py contract + feature ids), `PHASE2_HANDOFF_CP1.md` §INTERFACES only as needed.
3. Blueprint read set: E01 L1205–2789; E02 L2790–3871; E03 L3872–4954 (skip L4104–4158 body — CP-1 owns it; your §4 code imports `apex.identity.*`); E04 L4955–5601. Plus: AI.2/AI.11 rows for your four engines; §2.1 Q-tagging + §2.2 epsilon tables; §9.5 directives 2,3,4,9,10. That is all you read from the blueprint.

## 1. Mission (per engine, four times)
For each of E01–E04 produce exactly `apex/engines/eNN_*/{__init__.py,engine.py}` (+ engine-local modules only if that engine's §4 architecture demands, logged) implementing: §1 mission/boundary (zero scope creep), §2 vocabulary, §3 formulas verbatim incl. correction notes, §4 reference algorithm ported to production Python (streaming, idempotent, Decimal per §2.2, complexity per chapter), §5 objects/FSMs/events/JSON schemas/versioned contract (`contract_version v4.0.0`; snapshot_id via canonical envelope — SINGLE envelope only, per Phase 67A rule), §6 params wired to the engine's governed keys (no magic numbers inline), §7 encyclopedia → docstring citations only, §8 validation battery fully coded (golden fixtures constructed at `tests/fixtures/e0N_FIX_*.json` from §8.1 shapes with REAL re-derived values + computed hashes; deterministic replay; no-future-leak; ablation; Wilson-CI calibration harness (UNVERIFIED flag until owner data path exists); redundancy threshold; serialization compat), §9 case study → optional example test, values re-derived only (ADR-P2-007).
Engine-specific musts:
- E01: Williams k=2 frozen (dynamic k = WaveOutError hook), Gann single-fractal handling, pruning by depth+age, BreakMag absolute-value rule (L1447 area), CHoCH four PIT conditions, 0.15×ATR HTF tolerance, retest/invalidation/expiry, OOS weights for S_struct exactly as tabulated.
- E02: Q0–QX tagging per §1.5 (complete definition), hierarchical equal-level chain prevention, salience incl. `proximity_HTF`, 1-D DBSCAN O(n log n) `epsilon=θ_eq·ATR`, sweep five prerequisites P1–P5, Merton jump-diffusion hit probability (not plain Brownian), Cont-OFI/BVC-VPIN computed per §3.8 from OHLCV-derivable inputs with LIVE depth UNAVAILABLE (Wave-Out honored), volume-profile LVN void, PIT reference table.
- E03: uses governed `as_of = max(availability_time_ms)` via CP-1 helper; `availability_time_ms` missing → fail-closed (Phase 67.5); `ParticipationEvidence.as_of_ts` = governed as_of (Phase 67.6); structured last_error classification with fail-closed None return (67.7); reference-window t−1 exclusion is a statistical-history rule not global PIT (67.8); expose governed PIT-safe `volume_sma` in ParticipationEvidence (Phase 80); 14-TF registry incl. 8h, no 3d (Phase 79/88); zero-volume/OI-stale stresses survive as DEGRADED never silent-FAILED.
- E04: ε=1e-12 per R.8/GC-D4, stable ATR usage per §2.2, NO adaptive ATR (E04↔E11 deferred item → WaveOutError hook), Parkinson/GK/RS/GARCH-family formulas exactly per its §3/§4.

## 2. Rules of engagement
- Emit evidence via CP-2 base contract only; consume sibling engines via versioned interface registry + degradation branches; your engines are PRODUCERS (E06 etc. will consume E03/E04 evidence — your INTERFACES section must be complete for AGENT-04/05).
- Wave-Out list applies (P6); no new gates/thresholds/vetoes; no invented events beyond the engine's §5 event catalog.
- Traceability: one row per §3 formula group + §5 schema + §6 param-table row into MATRIX CP-3 (your fenced sub-part).

## 3. Exit sequence (P16)
HANDOFF_CP3 §[AGENT-03] (all 9 sub-headings; ≤400 lines; INTERFACES = per-engine emitted event schemas + registry keys + params keys + fixture paths) → STATUS CP-3 block for your slot only → DECISION_LOG issues → `pytest tests/unit/test_e0[1-4]* tests/integration -q` green → commits `[CP-3][AGENT-03] E0N: <what>` → `git pull --rebase origin main && git push origin main` → ≤10-line report. RESUME protocol if budget runs low (per-engine granularity in the ledger; finish whole engines rather than half of each).
Begin.
