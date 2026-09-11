# KICKOFF PROMPT — AGENT-04 — CP-3b ENGINES E05–E08
(Owner: paste as the first message to the 4th coding agent. AGENT-04 only. Entry: CP-1, CP-2 checked AND CP-3 slot [AGENT-03] delivered+pushed (if running the parallel variant, start anyway but code strictly against HANDOFF_CP3 §[AGENT-03] INTERFACES + AI.2, never against absent files).)

You are AGENT-04 (slot 4 of 10; CP-3 partial: E05 Imbalance/FVG, E06 Order Block, E07 RTM/ICT, E08 Wyckoff/Auction).

## 0. First actions
1. Clone `https://github.com/sinamoosazadeh/Upstage`, main, pull (you inherit A03's pushes — pull again before EVERY push).
2. Read: PROTOCOL (full), CHECKPOINTS §CP-3, DECISION_LOG §A, HANDOFF_CP2, HANDOFF_CP3 §[AGENT-03].
3. Blueprint read set: E05 L5602–6859; E06 L6860–8292; E07 L8293–9085; E08 L9086–9466. Plus AI.2/AI.11 rows for E05–E08; §2.1/§2.2 targeted; §9.5 directives 2,3,4,9,10; Ch.9 lines 15019–15021 (GF_SC shape — you only assert schema compatibility; fixture files are A06's).

## 1. Mission
Identical per-engine scope to AGENT-03's mission text (it applies to you verbatim: §1–§10 contract, fixtures with re-derived values, §8 battery, single canonical_snapshot_id envelope, no magic numbers, docstring citations, §9 illustrative-only).
Engine-specific musts:
- E05: min_width frozen 0.2 (CP-E05-001 proposal 0.25 NOT applied — do not "fix" this); negative-width detection fix; BodyRatio>0.1 classification; salience & premium definitions exact; streaming idempotency per its §4 full-reference block.
- E06: frozen 0.55 (not 0.65/0.68 — those are quarantined, §9.4/9.3); body-vs-range zone definition per frozen text; I_Volume_v4 = aligned E03 evidence ONLY (volume_sma, vol_ratio, snapshot_id, as_of — Phase 80/81: NO internal SMA; the previous local SMA is test-only and must not appear in engine path); I_Volatility_v4 = aligned E04 ATR evidence (Phase 82: no internal ATR recomputation); versioned-interface downgrade (structure <4.0.0 → structural_event=None + Q2).
- E07: streaming + idempotency block honored; RTM/ICT definitions per its §2–§4 (breaker blocks, intent classification); E12-window permission consumed via versioned interface (E12 arrives in A05; until then your degradation branch = the documented one; code it exactly and never invent a substitute).
- E08: implement the calibrated probabilistic phase machine per Ch.1 logic ONLY (8-phase probability vector, T_ij transitions, entropy scoring, Cause→Effect chain, explicit INVALIDATED/EXPIRED transitions; encyclopedia ch.2–4 = Wave-Out reference); OI missing → volume-only PARTIAL never blocking; failure-table values engine-authoritative.

## 2. Interface duty
You consume A03 engines (E01–E04) as real pushed code via their §5 schemas + your registry lookups; you PRODUCE for A05/A06/A07 (FVG zones, OB clusters, RTM states, Wyckoff phase). HANDOFF_CP3 §[AGENT-04] INTERFACES must let A05 finish E09–E12 without opening your files.
Traceability: MATRIX CP-3 sub-part rows for your four engines.

## 3. Exit sequence (P16, identical to A03): handoff section → STATUS block [AGENT-04] → issues → pytest green for your engines (+ integration against A03's real evidence) → `[CP-3][AGENT-04] E0N: <what>` commits → pull --rebase + push → ≤10-line report. RESUME at whole-engine granularity.
Begin.
