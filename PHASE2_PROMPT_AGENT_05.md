# KICKOFF PROMPT — AGENT-05 — CP-3c ENGINES E09–E12
(Owner: paste as the first message to the 5th coding agent. AGENT-05 only. Entry: CP-1, CP-2 checked; CP-3 slots [AGENT-03] and [AGENT-04] delivered+pushed (parallel variant: code against their HANDOFF §INTERFACES + AI.2, never against absent files).)

You are AGENT-05 (slot 5 of 10; CP-3 partial: E09 Trend, E10 Momentum, E11 Regime, E12 Temporal Context).

## 0. First actions
1. Clone `https://github.com/sinamoosazadeh/Upstage`, main, pull.
2. Read: PROTOCOL (full), CHECKPOINTS §CP-3, DECISION_LOG §A (esp. ADR-P2-008), HANDOFF_CP2, HANDOFF_CP3 §[AGENT-03]+§[AGENT-04].
3. Blueprint read set: E09 L9467–10275; E10 L10276–11670; E11 L11671–12732; E12 L12733–13528. Plus AI.2/AI.11 rows for E09–E12; §2.1/§2.2 targeted; §9.5 (incl. `params/e11_params_v4.yaml` frozen values), E12 consumer-notes tail (L13520–13528).

## 1. Mission
Same per-engine scope as defined in CHECKPOINTS §CP-3 "Shared SCOPE per engine" (applies verbatim).
Engine-specific musts:
- E09: OLS/slope-angle machinery per §3–§4 exactly; data-gap ≥10×ATR stress → explicit open-data availability states, degrade never fabricate (§8 note).
- E10: momentum ensemble + divergence machinery; fixtures must cover all four normative divergence kinds + CONVERGENCE + NONE; O(1) amortized EMA/RMA, O(W) OLS, O(k) pivot per §4 complexity notes; DivergenceRecord transport per §5 (SL-7) + DivergenceRecord consumed via SL-8-aligned channel.
- E11: **K=9 classes / d=8 input features — never conflate** (T-E11-K9 asserts vector length 9 everywhere: logits, probabilities, transition matrices, entropy bounds, schemas, adapters); params load from `params/e11_params_v4.yaml` (θ_H=0.65 forces TRANSITION inside E11 only; Dirichlet α; hysteresis 3; EWMA λ; 48-candle delay; W=4320); consumes aligned v4 projections from E09/E10/E04/E03/E02 ONLY (no macro gating; sentiment optional non-gating); missing required inputs/incompatible config → CONFIGURATION_INVALID / FAIL_CLOSED — never uniform/random fallback (AI.11); next-regime forecast hook = WaveOutError; research-only live gate flag implemented default-off (owner approval flow, per AI.12 Phase-7 gate).
- E12: UTC windows canonicalization EXACTLY per AI.2 rule 1–5 (UTC_W0/W1/W2/W3 primary, derived cores, OVERLAP flag [12:30,16:00), orthogonal ROLLOVER flag, DOW analytic-only, DST-ignore decree, versioned window registry); clock-drift>500ms → DEGRADED + new-entries-blocked signal (consumer rule; your output carries the state); E12 is consumed by E07 (already pushed — supply its documented interface) and Ch.16 execution — expose the canonical window API in your INTERFACES with exact function signatures.

## 2. Duties
You CLOSE CP-3: after your push, the CP-3 status block is complete across three slots — ensure HANDOFF_CP3 §[AGENT-05] also records a 5-line "CP-3 integration notes" subsection (what A06 must know to assemble the fabric: all 12 engines' event topics + version registry contents, deduplicated from the three slots — you read the two sibling handoff sections and merge the list; touch no sibling files).
Traceability: MATRIX CP-3 sub-part rows for E09–E12.

## 3. Exit (P16): handoff → STATUS [AGENT-05] → issues → pytest (your engines + T-E11-K9, T-E12-Windows) → `[CP-3][AGENT-05]` commits → pull --rebase + push → ≤10-line report. RESUME whole-engine granularity.
Begin.
