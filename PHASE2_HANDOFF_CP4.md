# PHASE2 HANDOFF — CP-4 → consumed by CP-5 (and CP-8 closeout)
Stage: CP-4 — Engines E07 RTM, E08 Wyckoff, E09 Trend
Rules (PROTOCOL P16): author = CP-4 executor (or its continuation session — state which, first line of STATUS). ≤400 lines, nine headings below in order. Successors read ONLY this file + their own prompt/law/checkpoint sections; interfaces listed here are the public contract they may code against. First STATUS line: `LAW-ACK: G1..G20 + P1..P21 read <UTC>`.

## STATUS

LAW-ACK: G1..G20 + P1..P21 read 2026-09-12T10:45Z (single-executor session; continuation of the same session that executed CP-4 from the entry gate).

**COMPLETE.** CP-4 fully closed: E07 RTM/ICT v4.0.0, E08 Wyckoff/Auction v4.0.0, E09 Trend v4.0.0 built from zero against the frozen blueprint (chapter order §2→§3→§4→§5→§6→§7→§8 mirrored in each engine file), every §8 battery clause executed as a real test, all golden fixtures re-derived (ADR-P2-007/014).

- Suite: **726 passed / 0 failed** (`tests/unit` + `tests/integration`; baseline 481 CP-1/CP-2/CP-3 + 245 new CP-4 tests: E07 83, E08 74, E09 65, integration 23) via `PYTHON=/home/user/apex-venv/bin/python bash scripts/run_all_tests.sh -q`.
- Branch: `arena/01a0953f-upstage` (pinned by the environment; the owner merges to `main` plain-merge per the ENV NOTE). Commits, format `[CP-4] <module>: <what changed>`: `1d06481` board IN-PROGRESS → `83a651c` E07 → `55e90e7` E08 → `8426680` E09 → `7957bc2` integration → the branch-HEAD docs commit (handoff/MATRIX/board/DECISION_LOG). Full range: `git log --oneline main..arena/01a0953f-upstage`.
- **Push state (verified 2026-09-12T18:25Z):** the complete CP-4 range `1d06481..9b2bf58` is pushed to `origin/arena/01a0953f-upstage`; `git ls-remote` reports `9b2bf583325472e59507900e184e4185bf5fa781`. The sandbox `GH_TOKEN` expired mid-stage, then GitHub auth was restored and the pending commits (`8426680`, `7957bc2`, `9b2bf58`) were pushed after `git pull --rebase origin main`. This was an environment credential outage, not a branch-pin conflict; no CP-4 push work remains.
- Environment: Python 3.11.2, Linux (sandbox); dev venv `/home/user/apex-venv` (the nine SBOM runtime pins from `requirements.lock` + pytest 8.4.2 dev-only; ADR-P2-002). Runtime deps unchanged — **no new pins**.
- Environment notes (honest): (1) the checkout is **shallow**, so predecessor commit ranges (CP-1…CP-3) are not SHA-verifiable here; contents + the green 481-test entry gate were verified instead (CP-3 precedent). (2) The sandbox was **re-created mid-stage**: the venv was rebuilt from `requirements.lock` and the local git history was re-anchored onto the already-pushed remote tip `1d06481` before the engine commits (no work lost; `sha256(APEX_GEN5.md)` re-verified `216bcc9e…fbd9e` after the re-creation). (3) A `GH_TOKEN` expiry caused one failed push between the E07 and E08 commits; the token was refreshed by the platform and every commit is pushed. (4) `sha256(APEX_GEN5.md) == 216bcc9e5f3e54c7567303bea7b642a9f5ccf482d2282d05dc78c2f7cb0fbd9e` — exact, checked at session start and again after the re-creation.

## DELIVERED

| file | purpose | blueprint section | MATRIX Part III rows |
|---|---|---|---|
| `apex/engines/e07_rtm/engine.py` (1342 L) + `__init__.py` | E07 RTM/ICT v4.0.0: order_map + Integrity_v4, Po3/MSS/OTE/Judas/CHAIN chains, UTC-fixed activity windows, RTM_Bundle.v4 + conflict law, streaming idempotency, **E12-unavailable degraded branch** | APEX_GEN5.md L8293–9085 (§2 L8354 · §3 L8374 · §4 L8493 · §5 L8753 · §6 L8860 · §7 L8887 · §8 L8957) | `E07\|1 … E07\|10` |
| `apex/engines/e08_wyckoff/engine.py` (1342 L) + `__init__.py` | E08 Wyckoff v4.0.0: the three laws (TR/RMA/ATR14, VolumeZ/RangeZ, corrected EVR, Effort/Result, Cause→Effect, P&F), 5×8 phase score matrix → softmax → entropy, Dirichlet transition matrix, six-parameter event contract (SC/AR/ST/Spring/SOS/UT/UTAD/LPS/LPSY), forward-only state machine + cycle_state, **encyclopedia ch.1 normative / ch.2–4 WaveOutError** | APEX_GEN5.md L9086–9466 (§3 L9144 · §4 L9225 · §5 L9322 · §6 L9346 · §7 L9370 · §8 L9410) | `E08\|1 … E08\|8` |
| `apex/engines/e09_trend/engine.py` (1223 L) + `__init__.py` | E09 Trend v4.0.0: four-scale stack (MICRO 5/SHORT 20/INTER 60/MACRO 240), pos/seq/direction-strength/quality, Mann–Kendall with tie correction, Newey–West HAC OLS, Hurst R/S (Anis–Lloyd corrected), **Wilder ADX AD-line (DI+/DI−/DX/ADX)**, divergence/exhaustion, **multi-TF bias + alignment**, TrendScale/TrendStack schemas, EV_TRD_001–008 | APEX_GEN5.md L9467–10275 (§3 L9574 · §4 L9695 · §5 L9994 · §6 L10072 · §7 L10103 · §8 L10173) | `E09\|1 … E09\|10` |
| `tests/unit/test_e07_rtm.py` (83) · `test_e08_wyckoff.py` (74) · `test_e09_trend.py` (65) | the three §8 batteries | §8.1–§8.7 of each chapter | `E07\|9`, `E08\|7`, `E09\|9` |
| `tests/integration/test_cp4_engines.py` (23) | cross-engine chains, E07 both temporal modes, E08 Wave-Out at the surface, E09 AD-line/multi-TF, store DDL, T-DR-001 shared-window | CP-4 EXIT boxes | `X-4`, `X-5`, `X-6` |
| `tests/fixtures/e07_golden_fixtures.json` (15) · `e08_golden_fixtures.json` (12) · `e09_golden_fixtures.json` (11) | golden fixtures; every expected value re-derived; per-fixture `sha256(canonical_json(…))` computed **after** the fixture exists (§9.5-3) | §8.1 of each chapter | `E07\|9`, `E08\|7`, `E09\|9` |

Foundation (`base.py`, store, quality, catalog, identity, config, errors, bus, `params/*.yaml`) was **consumed, never patched**; no foundation file appears in this stage's diff.

## INTERFACES

Public contract CP-5 (and CP-6) may code against. Signatures are copied from the shipped modules — nothing invented.

**E07 — `apex.engines.e07_rtm`** (ε = 1e-8, `CONTRACT_VERSION = "4.0.0"`, `ANALYST_VERSION = "4.0.0" + 40×"0"`)

| symbol | signature | semantics |
|---|---|---|
| `E07RTMEngine` | `(catalog_=None, bus=None, params=None)`; `.compute(symbol, timeframe, as_of, context) -> List[EvidenceEvent]` | frozen `EngineBase` binding; emits one 24-field event per produced bundle. Context keys: `window` (MarketObservation seq) **or** `provider`; `events` (confirmations `[{cid, t_confirm_ms, p_confirm}]`); `framework_id` (`RTM.PO3.v1` \| `RTM.CHAIN.v1` \| …); `direction` (`UP`/`DOWN`); `as_of_ms`; `avg_quality`; `mtf_align`; `econ_events`; **`temporal_provider`**; `e07_params`. Missing window + missing provider ⇒ `MISSING_WINDOW_CONTEXT_QX`; empty window ⇒ `[]`. |
| `RTMEngineStreaming` | `(params=None)`; `.process_at(as_of_ms, bars, econ=None, framework_id="RTM.PO3.v1", direction="UP", avg_q=0.9, mtf_align=1.0, temporal_provider=None) -> List[RTMBundle]` | idempotent per `as_of_ms // idem_bucket_ms`; repeat call for the same bucket returns `[]`. |
| `run_engine` | `(bars, events=None, framework_id="RTM.PO3.v1", direction="UP", as_of_ms=None, avg_q=0.9, mtf_align=1.0, econ_events=None, temporal_provider=None, params=None) -> dict` | payload keys: `bundle, integrity, weight_coverage, missing, range, kz, events, degraded, degraded_reason, as_of_ms, engine, contract_version`. `bundle` is `None` below either threshold. |
| `utc_activity_window_check` | `(ts, econ_events=None, kz_config_version="KZ.v2.1.1", temporal_provider=None, params=None) -> dict` | keys `in_kz, which, utc_activity_window, is_overlap, econ_conflict, rollover_active, config_version, source, degraded, degraded_reason, as_of_ms`. **CP-5 contract:** `temporal_provider.temporal_window(ts_ms) -> {"which": [...], "is_overlap": bool, "utc_activity_window": str, "config_version": str}`. No provider / provider raises ⇒ `source="E07_LOCAL_NON_AUTHORITATIVE"`, `degraded=True`, `degraded_reason="E12_UNAVAILABLE_DEGRADED_QX"`, Q5 gate off. Conforming provider ⇒ `source="E12_Temporal_Context.Contract v4.0.0"`, `degraded=False`, Q5 reachable. Non-UTC timestamp ⇒ `NON_UTC_TIMESTAMP_QX`. |
| `RTMBundle` | dataclass, 23 fields: `bid, framework_id, components_present, components_missing, integrity, weight_coverage, confidence, direction, resolution_class, explanation, as_of_ms, snapshot_id, version, fate, utc_window_aligned, mtf_align_score, conflict_with, order_map, temporal_authority, degraded, degraded_reason, age_bars, created_at_ms`; `.validate_schema()` | `bid` matches `^bnd_[a-f0-9]{12}$` (48 random bits of UUIDv7 — ISSUE-CP4-004) and never enters `snapshot_id`. `resolution_class ∈ Q0..Q5`. |
| `build_bundle_pipeline` | `(expected, present, order_map, avg_q, mtf_align, kz_info, framework_id, direction, as_of_ms, params=None, has_conflict=False) -> Optional[RTMBundle]` | returns `None` when `Integrity < θ_int` or `WeightCoverage < θ_weight`. |
| `sequence_integrity_v4` | `(expected, present, order_map) -> (integrity, weight_coverage, missing)` | §3.1; Integrity keeps the ε denominator, coverage is exact (ISSUE-CP4-021); out-of-order component ⇒ score 0.5. |
| `expected_components` / `build_order_map` / `evaluate_order_ok` | `(framework_id, params=None)` / `(components, confirmations) -> {cid: OrderMapEntry}` / `(expected, present, order_map) -> None` | `OrderMapEntry` carries `weight, exp_seq, present, score, order_ok`. |
| `bundle_confidence` · `quality_class_cascade` · `quality_class_caps` · `resolution_class` | `(integrity, avg_q, mtf_align, kz_align, alpha=0.4, beta=0.25, gamma=0.2, delta=0.15)` · `(integrity, conf)` · `(integrity, conf, avg_q, mtf_align, kz_info, has_conflict=False)` | §3.7; the cascade is **capped** by the conjunctive gates (ISSUE-CP4-006). |
| `atr_ratio_detect` | `(bars, atr_short_period=10, atr_long_period=100, params=None) -> dict` | keys `is_range, ratio, hl_range, sigma_ratio, vol_ratio, atr_short, atr_long, gap_reset, gap_edge, degraded, reason, n_bars`. Range needs ratio<0.75 ∧ vol<0.9 ∧ HL<2.5·ATR_l ∧ **σ(C)/ATR_l<0.6**. |
| `ote_zone_calc` · `mss_proximity_check` · `mss_confirmed` · `judas_swing_detect` | `(a, b, r_lo=0.62, r_hi=0.79, r_star=0.705) -> Optional[{lo,hi,star}]` · `(p_sweep, p_choch, atr20, thresh=0.5) -> bool` · `(…) -> bool` · `(bars, expected_dir, atr20, max_pen=0.25, params=None) -> Optional[dict]` | §3.3–§3.4. |
| `resolve_conflicting_bundles` | `(bundles, params=None) -> List[RTMBundle]` | §10 conflict law: a newer bundle supersedes only when it exceeds the older by `conflict_conf_margin = 0.1`; otherwise it is invalidated. |
| `redundancy_halve_weights` · `wilson_ci` · `pearson` | `(components, series, threshold=0.85)` · `(p_hat, n, z=1.96) -> (lo, hi)` · `(x, y) -> float` | §8.4–§8.6. |
| `new_bundle_id` · `make_snapshot_id` · `to_utc_ms` · `kz_align_score` · `window_overlap` | `() -> str` · `(payload) -> 64-hex` · `(ts) -> int` · `(kz_info) -> float` · `(a, b) -> Optional[(lo, hi)]` | identity helpers; `to_utc_ms` raises `NON_UTC_TIMESTAMP_QX` on a non-Z timestamp. |
| `get_params` / `E07_DEFAULTS` / `EngineParams` | `get_params(overrides=None)`; 37 keys | unknown key ⇒ `UNKNOWN_E07_PARAM_QX`. Six-YAML law honoured in-package (no new YAML). |

**E08 — `apex.engines.e08_wyckoff`** (ε = 1e-8, `CONTRACT_LABEL = "APEX-CONTRACT-WYCKOFF-V4.0.0"`)

| symbol | signature | semantics |
|---|---|---|
| `E08WyckoffEngine` | `(catalog_=None, bus=None, params=None)`; `.compute(symbol, timeframe, as_of, context) -> List[EvidenceEvent]` | one event per §5 cycle event; context keys `window`/`provider`, `atr_by_idx`, `vol_ratio_by_idx`, `evr_by_idx`, `structure_by_idx`, `bos_by_idx`, `e08_params`. No governed ATR ⇒ every bar is Q0_INVALID (never a substitute ATR). |
| `WyckoffEngineV4` | `(params=None)`; `.process_bar(bar, atr, vol_ratio, close_pos, evr_value, structure=None, bos_event=None, ts=None) -> dict`; `.run_full(bars, atr_by_idx=None, vol_ratio_by_idx=None, evr_by_idx=None, structure_by_idx=None, bos_by_idx=None) -> List[dict]` | `.events` accumulates `EV_WYK_001…012`; `.state` is the forward-only state machine; `.low_sc/.high_sos/.range_lo/.range_hi/.range_age` hold the **latched** range (ISSUE-CP4-022). |
| cycle-state record | `{range, phase_hypotheses, entropy, confirmed_events, fate, snapshot_id, as_of, version, quality}` + operational `idempotency_key, state, degraded, degraded_reason` | exactly the §5 JSON shape plus observability extras (ISSUE-CP4-024); `snapshot_id` derives from the canonical payload only. `fate ∈ ACTIVE\|AMBIGUOUS\|INVALIDATED\|EXPIRED`; `quality ∈ Q0..Q5`. |
| `run_engine` | `(bars, atr_by_idx=None, vol_ratio_by_idx=None, evr_by_idx=None, structure_by_idx=None, bos_by_idx=None, params=None) -> dict` | keys `states, final, state, events, engine, contract_version`. |
| `encyclopedia_chapter` | `(chapter: int) -> dict` | **ch.1** ⇒ `{"chapter":1,"normative":True,"dimensions":16,"content":{...16...}}`. **ch.2/3/4** ⇒ raises `WaveOutError(feature="e08_encyclopedia_ch2_4", reason=E08_CH2_THE_THREE_LAWS_DEFERRED_NON_NORMATIVE \| E08_CH3_MARKET_CYCLES_DEFERRED_NON_NORMATIVE \| E08_CH4_WYCKOFF_EVENTS_DEFERRED_NON_NORMATIVE)`. Anything else ⇒ `ENCYCLOPEDIA_CHAPTER_QX`. **CP-5/CP-8 must not catch-and-ignore this**; if a chapter becomes Wave-In, replace the raise, do not wrap it. |
| `phase_score_matrix` | `(close, range_lo, range_hi, evr_value, vol_ratio, structure, age_bars, params=None) -> (scores[5][8], provenance[phase][component])` | components `(position, evr, volume, structure, age)`; unspecified cells = 0.5 with provenance `UNSPECIFIED_NEUTRAL` (ISSUE-CP4-012). |
| `phase_probabilities` | `(scores, w, phases=PHASES) -> (probs{phase:p}, H)` | `z_i = Σ w_k score_{k,i}` → softmax; `H` in nats; θ_H = 0.85 ⇒ AMBIGUOUS. |
| `phase_weights` · `softmax` · `entropy` · `transition_matrix` | `(params=None) -> [0.25,0.25,0.20,0.15,0.15]` · `(z) -> [p]` · `(p, floor=1e-12) -> float` · `(counts=None, alpha=0.1, K=9, phases=PHASES) -> {i:{j:T}}` | K = 9 vs 8 phases ⇒ rows never sum to 1 (ISSUE-CP4-014). |
| detectors | `detect_sc(bar, vol_ratio, range_z_, close_pos, body_ratio_, params=None)` · `detect_sc_full(bar, bars, vol_ratio, range_z_, params=None)` · `detect_ar(bar, sc_low, atr, bars_since_sc, params=None)` · `detect_st(bar, sc_low, atr, vol_ratio, params=None)` · `detect_spring(low, range_lo, close, atr, vol_ratio, evr_value, bars_since_st=None, params=None)` · `detect_sos(bar, range_hi, atr, vol_ratio, bos_confirmed_idx, current_idx, params=None)` · `detect_ut(low/high args per §3.3)` · `detect_utad(bar, range_hi, atr, vol_ratio, params=None)` · `detect_lps(bar, high_sos, range_lo, atr, vol_ratio, structure, params=None)` · `detect_lpsy(bar, range_hi, range_lo, atr, vol_ratio, params=None)` · `detect_range(bars, atr, min_bars=12, atr_mult=1.5, eps=1e-8)` | §3.3 six-parameter contract; `detect_sos` enforces the BOS-at-`t−1` PIT rule. |
| metrics | `evr(volume_z, range_z_, close, prev_close, eps=1e-8)` · `effort_without_result(rho, threshold=0.2)` · `cause_effect_target(range_cause, duration, k=0.42, gamma=0.71, breakout=0.0)` · `point_figure_target(…) · pf_box_size(atr)` · `atr14(bars, period=14)` · `true_range(h,l,prev_c)` · `volume_z(seq)` · `range_z(seq)` · `close_position(bar)` · `body_ratio(bar)` · `brier_score(probs, outcomes)` · `log_loss(probs, outcomes, eps=1e-12)` · `wilson_ci(p_hat, n, z=1.96)` | EVR is the **corrected** `VZ·RZ·sgn(ΔC)`; RangeZ/VolumeZ are z-scores (ISSUE-CP4-010); an H<L bar contributes no own TR. |
| `get_params` / `E08_DEFAULTS` | 52 keys | unknown key ⇒ `UNKNOWN_E08_PARAM_QX`. |

**E09 — `apex.engines.e09_trend`** (ε = 1e-12, `CONTRACT_LABEL = "E09_Trend.Contract v4.0.0"`)

| symbol | signature | semantics |
|---|---|---|
| `E09TrendEngine` | `(catalog_=None, bus=None, params=None)`; `.compute(symbol, timeframe, as_of, context) -> List[EvidenceEvent]` | **one event per scale** (4), `condition_state = "TREND_{SCALE}_{STATE}"`; context keys `window`/`provider`, `swings` (E01), `atr` (E04), `mom_series` (E10 — lands CP-5), `tf_seconds`, `bos_event`, `choch_event`, `oi_state`, `e09_params`. |
| `run_engine` | `(bars, swings=None, atr=0.0, mom_series=None, tf_seconds=3600, bos_event=None, choch_event=None, oi_state="MISSING", params=None) -> dict` | keys `scales{MICRO,SHORT,INTER,MACRO}, stack, bias, alignment, quality_agg, stack_snapshot, snapshot_id, as_of, as_of_bar, divergence, oi_state, degraded, degraded_reason, events, engine, contract_version`. |
| per-scale record | all 18 `TREND_SCALE_REQUIRED` keys: `scale, direction, strength, quality, quality_label, seq_score, slope_z, pos, r2, adx, di_plus, di_minus, hurst, mk_z, evidence_count, as_of, snapshot_id, contract_version` (+ `pit_lag, dx, beta, state, continuity_break, degraded_reason`) | `direction ∈ {-1,0,1}`; `quality_label ∈ Q0..Q5`; `state ∈ UNKNOWN\|CALCULATING\|VALID\|DEGRADED\|INVALID`. |
| `compute_adx_wilder` | `(bars, n=14, eps=1e-12) -> {adx, di_plus, di_minus, dx, warmup, warmup_2n}` | the **AD-line**; `warmup` = t<n, `warmup_2n` = t<2n (ISSUE-CP4-018); either ⇒ `ADX_WARMUP_QX` on the scale. |
| `compute_pos_scale` · `compute_seq_score` · `trend_direction_and_strength` · `compute_trend_quality` · `quality_label` | `(bars, window, atr_val, eps=1e-12) -> float` · `(swings, window, current_idx, strict_pit=True) -> (score, n)` · `(seq_score, slope_z, pos, w=(0.4,0.35,0.25), th=0.5, deadband=0.05) -> (dir, strength, raw_z)` · `(r2, adx, hurst, h_clip_max=1.2) -> float` · `(q, r2, adx, hurst) -> "Q0..Q5"` | `compute_seq_score(None, …) -> (0.0, 0)`; a PIT violation raises `PIT_SWING_VIOLATION_QX` unless `strict_pit=False`. |
| `mann_kendall_with_tie_correction` · `ols_slope_newey_west` · `newey_west_lag` · `hurst_rs_anis_lloyd_corrected` · `anis_lloyd_expected_rs` | `(x, tie_eps=1e-12) -> (S, VarS, z)` · `(ts, ys, lag_auto=True, eps=1e-12) -> (beta, se_NW, r2)` · `(n) -> int` · `(x, min_len=8, max_len=None, eps=1e-12) -> (H, r2)` · `(n) -> float` | degenerate OLS ⇒ `(0.0, inf, 0.0)`; `L = max(1, ⌊4(n/100)^{2/9}⌋)`; n < 2·min_len ⇒ H = 0.5, r² = 0. |
| `stack_bias` · `stack_alignment` · `quality_aggregate` · `scale_state` · `scale_windows` | `(scale_directions, weights=None) -> float` · `(bias, scale_directions, prev_alignment=None, params=None) -> str` · `(scale_qualities, weights=None) -> float` · `(quality_label_, evidence_count, adx, strength, continuity_broken, valid, adx_valid_min=10.0) -> str` · `(params=None) -> {MICRO:5, SHORT:20, INTER:60, MACRO:240}` | weights `{MICRO:0.1, SHORT:0.2, INTER:0.3, MACRO:0.4}`; a partial scale map raises `TREND_STACK_QX`; bands: `>0.5` ALIGNED_BULL, `<−0.5` ALIGNED_BEAR, `|B|≤0.3` SIDEWAYS/CONFLICTING, else TRANSITIONING. |
| `divergence_exhaustion_check` · `exhaustion_score` · `continuity_break` · `dedup_swings` · `validate_bar` | `(price_swings, mom_series, current_idx, lookback=20, delta=0.1, score=0.8) -> {is_exhaustion, type, score, degraded, degraded_reason}` · `(div_binary, strength, adx) -> float` · `(bars, tf_seconds, mult=2.0) -> bool` · `(swings, min_distance=2)` · `(bar, eps=1e-12) -> bool` | `mom_series=None` ⇒ `MOMENTUM_UNAVAILABLE_DEGRADED_QX` (E10 lands at CP-5); `oi_state="MISSING"` ⇒ `EV_TRD_008` + `OI_MISSING_DEGRADED_QX`; unknown `oi_state` ⇒ `OI_STATE_QX`. |
| `TrendScale` / `TrendStack` | dataclasses with `.to_canonical()`, `.to_dict()`, `.update_snapshot()`, `.validate_schema()` | validators raise `TREND_SCALE_QX` / `TREND_STACK_QX`. |
| `get_params` / `E09_DEFAULTS` | 37 keys | unknown key ⇒ `UNKNOWN_E09_PARAM_QX`. |

## DATA-CHANGES

none. No table, column or migration was created or altered; all three engines read the consumed catalog surface (`MarketObservation`) and emit rows through the frozen `SQLiteStore.insert_evidence` DDL (verified in `tests/integration/test_cp4_engines.py::TestCP4EmissionsInsertIntoStore`). No new `params/*.yaml` (six-YAML law; defaults live in-package).

## TESTS

| test file | ids / clauses covered | result |
|---|---|---|
| `tests/unit/test_e07_rtm.py` | §8.1 golden fixtures (15: PO3_COMPLETE_VALID, PO3_RANGE_FAIL_VOL_HIGH, MSS_NEAR_TRUE/FALSE, OTE_VALID/INVALID, JUDAS_VALID_REV100_IN3, JUDAS_FAIL_REV_SMALL, UTC_ACTIVITY_WINDOW_OVERLAP_CANONICAL_INSIDE, UTC_ACTIVITY_WINDOW_UTC_W1_CORE_INSIDE_OVERLAP_OUTSIDE, INTEGRITY_ORDER_WRONG_PENALTY_0.5, CONFLICT_RESOLUTION, EDGE_H_L_INVALID, EDGE_V_ZERO, LIQUIDITY_GRAB_CHAIN_VALID) · §8.2 deterministic replay · §8.3 no-future-leak/PIT + non-UTC rejection · §8.4 ablation + Wilson [48%,76%] · §8.5 calibration · §8.6 redundancy r>0.85 halving · §8.7 serialization · §6 params · EngineBase binding · T-DR-001 · Wave-Out discipline | **83 passed** |
| `tests/unit/test_e08_wyckoff.py` | §8.1 FIX_E08_01–12 (SC canonical + 3 negative + H<L + ATR=0 + range boundary + Spring + SOS + ST + UTAD + phase vector) · §8.2 replay (identical `snapshot_id` + `phase_hypotheses`) · §8.3 no-future-leak (High=10000 injection) · §8.4 calibration (Brier/log-loss targets 0.22/0.65) · §8.5 ablation ordering (`position` dominates) · §8.6 redundancy Spring/Sweep ≤ 0.45 · §8.7 serialization stability · §3.1 three laws · §3.2 phase matrix/entropy/Dirichlet · §3.3 six-parameter events · §5 state machine + cycle schema · §6 params · **ch.2–4 WaveOutError** · EngineBase binding · T-DR-001 | **74 passed** |
| `tests/unit/test_e09_trend.py` | §8.1 FIX_01–11 (uptrend, downtrend, sideways, ADX known, MK tie, Hurst trending/mean-reverting, exhaustion divergence, stack aligned, quality formula, H<L) · §3.1 pos/seq/direction/quality · §3.2 MK + Newey–West · §3.3 OLS · §3.4 Hurst R/S + E[R/S] table · §3.5 **ADX AD-line** + warm-up · §3.6 divergence/exhaustion · §3.7 **multi-TF stack** · §4 continuity · §5 TrendScale/TrendStack schemas · §6 params · EV_TRD_001–008 · PIT violation · T-DR-001 | **65 passed** |
| `tests/integration/test_cp4_engines.py` | E07 degraded + authoritative temporal branches (6, incl. Q4-cap vs Q5-reachable) · E08 Wave-Out at the engine surface (4) · E09 AD-line + four-scale schema + governed bias bands (6) · E04 ATR consumed-not-recomputed · E01 swings/BOS under PIT · store DDL insert + duplicate rejection · T-DR-001 shared-window double run for all three engines | **23 passed** |
| full suite | `scripts/run_all_tests.sh` (unit + integration) | **726 passed / 0 failed** |

## DEVIATIONS

- ADR-P2-002 applied: pytest 8.4.2 is a dev-only extra in the session venv; `requirements.lock` (nine runtime pins) untouched.
- ADR-P2-003 applied: only blueprint-named paths were created (`apex/engines/e0{7,8,9}_*/`, `tests/fixtures/e0{7,8,9}_golden_fixtures.json`, the three unit batteries, `tests/integration/test_cp4_engines.py`).
- ADR-P2-007 applied: every §8.1 expected value and every §9 case-study number was re-derived from the chapter's own formulas; no document hash or case number was copied. Non-reproducible document values are asserted as recomputations with the divergence recorded (E08 §9 0.71/0.18/0.11 + H=0.52; E09 §9 ADX≈45 on 10 bars; E07 §8.1 `which` at 14:00Z).
- ADR-P2-014 applied: §8.1 fixtures are engine-canonical and kept verbatim even where a re-derivation disagrees (E09 FIX_01 `Q_min`, FIX_03 `MICRO_dir`); §9 case studies are treated as illustrative.
- ADR-P2-015 applied: built from zero; no prior implementation was read, cloned or referenced.
- ADR-P2-017 applied: E07↔E12 stays a *deferred* integration (E12 is CP-5); no CP-5 code was written.
- No other deviation. Every other divergence from the document text is logged as `[ISSUE-CP4-0NN]` below and in DECISION_LOG §B/CP-4.

## OPEN-ISSUES

Mirrored verbatim in `PHASE2_DECISION_LOG.md` §B/CP-4 (001–007, 010–025; 008/009 withdrawn pre-commit, numbering left gapped).

- [ISSUE-CP4-001] MINOR/CLOSED — E07 §2's σ(C)/ATR_l < 0.6 term is absent from §3.2's range condition. Both enforced; `sigma_ratio` reported; isolated in the battery. Needs from owner: none.
- [ISSUE-CP4-002] MINOR/CLOSED — E07 §4's `or recent_vol == 0` shortcut would turn missing volume into a range authorization. §3.2 edge case wins ⇒ `VOL_UNAVAILABLE_QX`, not authorized. Needs from owner: none.
- [ISSUE-CP4-003] MINOR/CLOSED — 3·ATR resets the range window; 5·ATR flags `gap_edge`; the two effects are kept distinct. Needs from owner: none.
- [ISSUE-CP4-004] MINOR/CLOSED — `bid` minted from UUIDv7's **random** 48 bits (a timestamp prefix collides within a millisecond); `uuid4` in §4 replaced per the identity single-source law. Needs from owner: none.
- [ISSUE-CP4-005] INFO/**OPEN-UNTIL-CP-5** — E12 is CP-4-absent ⇒ E07's degraded branch is the CP-4 behaviour; **CP-5 must re-test both modes** (`temporal_provider=None` and a conforming `temporal_window`). Needs from owner: none.
- [ISSUE-CP4-006] MINOR/CLOSED — §4's Q5 cascade is capped by §3.7's conjunctive gates ⇒ the §9 case is Q4, not Q5. Needs from owner: none.
- [ISSUE-CP4-007] MINOR/CLOSED — CHAIN.v1 `retest` weight absent from the list; Σw = 4.8 is authoritative ⇒ 0.8. Needs from owner: none.
- [ISSUE-CP4-010] MINOR/CLOSED — E08 RangeZ/VolumeZ are z-scores (§3.1), not the `(H−L)/ATR` ratio in §4's call site. Needs from owner: none.
- [ISSUE-CP4-011] MINOR/CLOSED — `score_position` clamped to the stated [0,1] domain. Needs from owner: none.
- [ISSUE-CP4-012] MINOR/CLOSED — unspecified phase-score cells = neutral 0.5 with provenance, always appended (a missing cell makes the matrix ragged). Needs from owner: none.
- [ISSUE-CP4-013] MINOR/CLOSED — 8 phases + θ_H = 0.85 kept; §9's 3-phase softmax example is not reproducible (recomputed [0.428,0.347,0.226], H = 1.066). Needs from owner: none.
- [ISSUE-CP4-014] MINOR/CLOSED — Dirichlet K = 9 vs 8 phases ⇒ rows sum to 8/9 (N=0). Formula implemented verbatim. **Needs from owner: confirm whether K should be 8 (CP-8 triage).**
- [ISSUE-CP4-015] MINOR/CLOSED — E09 §4's ADX early return referenced unbound `di_plus`; canonical seeding with always-bound outputs. Needs from owner: none.
- [ISSUE-CP4-016] MINOR/CLOSED — Hurst clip: §4's executable form implemented (identical to §2's `min(H,1.2)` for H ≤ 1.2). Needs from owner: none.
- [ISSUE-CP4-017] MINOR/CLOSED — redundancy threshold 0.85 (§8.4 and §8.6 agree on the value). Needs from owner: none.
- [ISSUE-CP4-018] MINOR/CLOSED — ADX `warmup_2n` (t < 2n) added per §3.5's "NaN until t ≥ 2n"; either warm-up flag degrades the scale. Needs from owner: none.
- [ISSUE-CP4-019] MINOR/CLOSED — E09 FIX_03 `MICRO_dir`: doc 0 vs re-derived +1 (z = 0.3827 > deadband 0.05); sideways diagnosis carried by EV_TRD_007. **Needs from owner: confirm whether the deadband applies to z or to strength (CP-8 triage).**
- [ISSUE-CP4-020] MINOR/CLOSED — E09 FIX_01 `Q_min = Q2` unreachable on 5 bars (ADX needs ≥ 2n) ⇒ re-derived Q0 asserted. Needs from owner: none.
- [ISSUE-CP4-021] MINOR/CLOSED — E07 WeightCoverage uses the exact §3.1 ratio (no ε) while Integrity keeps the ε denominator. Needs from owner: none.
- [ISSUE-CP4-022] MINOR/CLOSED — E08's range boundary is **latched** on detection (§5's one-way state machine; re-deriving drops the range at the SOS breakout). Needs from owner: none.
- [ISSUE-CP4-023] MINOR/CLOSED — E09 publishes the whole validated TrendScale/TrendStack objects (all required keys), not the subset the stack reads. Needs from owner: none.
- [ISSUE-CP4-024] MINOR/CLOSED — E08's cycle state publishes `degraded`/`degraded_reason` as operational extras (the §5 wire shape has no such key) so a degraded cycle is never silent. Needs from owner: none.
- [ISSUE-CP4-025] MINOR/CLOSED — E07 §8.1's `which` at 14:00Z lists UTC_W1 although §3.6 defines W1 = 07:00–12:30; geometric truth + the derived overlap tag are emitted. Needs from owner: none.

Fixture-quality note (no issue number): E09 FIX_06/FIX_07 originally stored a *prose descriptor* of the Hurst series instead of the series itself — not replayable. Both were materialized as explicit 128-point deterministic series (monotone `60000+7i`; ±5 alternation), H/r² re-derived, and the hashes recomputed.

## HOW-TO-RUN

```bash
cd /home/user/Upstage
# 1. Environment (the nine SBOM runtime pins + pytest as a dev-only extra)
python3 -m venv /home/user/apex-venv
/home/user/apex-venv/bin/pip install -r requirements.lock
/home/user/apex-venv/bin/pip install pytest==8.4.2

# 2. Whole suite (unit + integration)
PYTHON=/home/user/apex-venv/bin/python bash scripts/run_all_tests.sh -q
#    -> 726 passed

# 3. CP-4 batteries individually
/home/user/apex-venv/bin/python -m pytest tests/unit/test_e07_rtm.py -q          # 83
/home/user/apex-venv/bin/python -m pytest tests/unit/test_e08_wyckoff.py -q      # 74
/home/user/apex-venv/bin/python -m pytest tests/unit/test_e09_trend.py -q        # 65
/home/user/apex-venv/bin/python -m pytest tests/integration/test_cp4_engines.py -q  # 23

# 4. Demo entry — one call per engine (no network, no data files)
/home/user/apex-venv/bin/python - <<'PY'
from apex.engines.e07_rtm import utc_activity_window_check
from apex.engines.e08_wyckoff import run_engine as e08, encyclopedia_chapter
from apex.engines.e09_trend import run_engine as e09
print(utc_activity_window_check("2026-01-15T14:00:00Z"))          # degraded: E12 absent
bars = [{"ts": 1768485600000 + i*21600000, "o": 610.0, "h": 611.0,
         "l": 609.0, "c": 610.5, "v": 1000.0, "is_closed": True} for i in range(30)]
print(e08(bars, atr_by_idx={i: 4.2 for i in range(30)})["final"]["fate"])
print(e09(bars, atr=4.2)["alignment"], e09(bars, atr=4.2)["bias"])
try:
    encyclopedia_chapter(3)
except Exception as exc:
    print(type(exc).__name__, exc)                                 # Wave-Out, ch.3
PY
```

## REMAINING WORK LEDGER

**none — stage fully closed.** All three §8 batteries are green, the handoff/MATRIX/board/DECISION_LOG deliverables are written, and the complete CP-4 commit range is pushed to `origin/arena/01a0953f-upstage` (verified at `9b2bf58`). No CP-4 code, test, fixture, documentation, or push work remains.

Hand-off to CP-5 (not CP-4 work):
1. **E07↔E12 integration** — re-run `tests/integration/test_cp4_engines.py::TestE07TemporalBranches` with the real `E12_Temporal_Context.Contract v4.0.0` provider in place of `StubE12`; both modes (absent ⇒ `E12_UNAVAILABLE_DEGRADED_QX` + Q4 cap; present ⇒ `source = E12_Temporal_Context.Contract v4.0.0` + Q5 reachable) must hold. [ISSUE-CP4-005]
2. **E09 ← E10 momentum** — `mom_series` currently degrades with `MOMENTUM_UNAVAILABLE_DEGRADED_QX`; feeding E10's series must light the divergence/exhaustion branch (`EV_TRD_003`) without touching the §3.6 formula.
3. **E08 Wave-Out** — if any of chapters 2–4 becomes Wave-In, replace the `raise` in `encyclopedia_chapter`, never wrap it; the three reason codes are frozen strings in `WAVE_OUT_REASONS`.
4. Triage requests to the owner: [ISSUE-CP4-014] (Dirichlet K = 9 vs 8 phases) and [ISSUE-CP4-019] (deadband applies to z or to strength).
